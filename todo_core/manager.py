"""Task workflows, dependency validation and auditable agent handoffs."""
from copy import deepcopy
from functools import wraps
from datetime import date
import json
from .model import Task, TaskStatus, TaskPriority, now, normalize_due
from .storage import TaskStorage


class NotFoundError(ValueError):
    pass


def mutation(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        before = deepcopy(self.tasks)
        try:
            return method(self, *args, **kwargs)
        except Exception:
            self.tasks = before
            raise
    return wrapped


class TaskManager:
    def __init__(self, storage=None, actor='user'):
        self.storage = storage or TaskStorage()
        self.tasks = self.storage.load()
        self.actor = actor

    def save(self):
        self.storage.save(self.tasks)

    def get(self, task_id):
        exact = [t for t in self.tasks if t.id == task_id]
        if exact:
            return exact[0]
        matches = [t for t in self.tasks if len(task_id) >= 4 and t.id.startswith(task_id)]
        if len(matches) > 1:
            raise ValueError('任务 ID 前缀有歧义: ' + ', '.join(t.id for t in matches))
        return matches[0] if matches else None

    def require(self, task_id):
        task = self.get(task_id)
        if task is None:
            raise NotFoundError('未找到任务: ' + task_id)
        return task

    def _event(self, task, action, **details):
        task.updated_at = now()
        task.history.append(dict(at=task.updated_at, actor=self.actor, action=action, **details))

    def _writable(self, task, force=False):
        if task.owner and task.owner != self.actor and not force:
            raise ValueError('任务由 {} 认领；使用独立 --actor，或 --force 显式接管'.format(task.owner))

    def _references(self, task):
        task.dependencies = list(dict.fromkeys(self.require(x).id for x in task.dependencies))
        if task.parent_id:
            task.parent_id = self.require(task.parent_id).id
        # A parent waits for its children, not the other way around.
        graph = {t.id: t.dependencies + [child.id for child in self.tasks if child.parent_id == t.id]
                 for t in self.tasks}
        visiting, visited = set(), set()
        def visit(node):
            if node in visiting:
                raise ValueError('任务依赖或父子关系存在循环')
            if node in visited:
                return
            visiting.add(node)
            for other in graph.get(node, []):
                visit(other)
            visiting.remove(node)
            visited.add(node)
        for node in graph:
            visit(node)

    def blockers(self, task):
        references = task.dependencies + [t.id for t in self.tasks if t.parent_id == task.id]
        return [dep for dep in dict.fromkeys(references)
                if not self.get(dep) or self.get(dep).status != TaskStatus.DONE]

    @mutation
    def add(self, title, description=None, priority='medium', tags=None, due_date=None,
            branches=None, acceptance=None, dependencies=None, parent_id=None,
            links=None, request_id=None):
        if not isinstance(title, str) or not isinstance(priority, str):
            raise ValueError('标题和优先级必须是字符串')
        task = Task(title=title.strip(), description=description,
                    priority=TaskPriority.from_string(priority), tags=[] if tags is None else tags,
                    due_date=normalize_due(due_date), branches=[] if branches is None else branches,
                    acceptance=[] if acceptance is None else acceptance,
                    dependencies=[] if dependencies is None else dependencies,
                    parent_id=parent_id, links=[] if links is None else links, request_id=request_id)
        task.validate()
        # Resolve references before comparing retried requests (prefix vs full UUID).
        task.dependencies = list(dict.fromkeys(self.require(x).id for x in task.dependencies))
        if parent_id:
            task.parent_id = self.require(parent_id).id
        if request_id:
            existing = next((t for t in self.tasks if t.request_id == request_id), None)
            if existing:
                initial = next((e.get('input') for e in existing.history if e['action'] == 'add'), None)
                if initial != self._input(task):
                    raise ValueError('request-id 已用于不同的任务内容')
                return existing
        self.tasks.append(task)
        self._references(task)
        self._event(task, 'add', input=self._input(task))
        self.save()
        return task

    @staticmethod
    def _input(task):
        return {key: task.to_dict()[key] for key in ('title', 'description', 'priority', 'tags', 'due_date',
                'branches', 'acceptance', 'dependencies', 'parent_id', 'links')}

    @mutation
    def edit(self, task_id, title=None, description=None, status=None, priority=None,
             tags=None, due_date=None, force=False, **fields):
        task = self.require(task_id)
        self._writable(task, force)
        before = task.to_dict()
        allowed = {'branches', 'acceptance', 'dependencies', 'parent_id', 'links', 'result', 'next_step'}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError('不支持的编辑字段: ' + ', '.join(sorted(unknown)))
        for key, value in dict(title=title, description=description, tags=tags, **fields).items():
            if value is not None:
                setattr(task, key, value.strip() if key == 'title' else value)
        if task.parent_id == '':
            task.parent_id = None
        if priority is not None:
            task.priority = TaskPriority.from_string(priority)
        if due_date is not None:
            task.due_date = normalize_due(due_date)
        task.validate()
        self._references(task)
        if status is not None:
            target = TaskStatus.from_string(status)
            if target in (TaskStatus.IN_PROGRESS, TaskStatus.REVIEW, TaskStatus.DONE) and self.blockers(task):
                raise ValueError('前置任务尚未完成: ' + ', '.join(self.blockers(task)))
            if target == TaskStatus.BLOCKED:
                raise ValueError('请使用 block 命令并说明阻塞原因')
            if target == TaskStatus.DONE:
                if task.acceptance and not (task.result and task.result.strip()):
                    raise ValueError('有验收条件的任务需要 --result 记录验证结果')
                if task.status != TaskStatus.DONE:
                    task.mark_done()
            else:
                task.completed_at = None
            task.status = target
            task.blocked_reason = None
            if target == TaskStatus.IN_PROGRESS:
                task.owner = self.actor
            elif target == TaskStatus.TODO:
                task.owner = None
                task.result = None
        task.validate()
        changes = {k: {'before': before[k], 'after': v} for k, v in task.to_dict().items()
                   if before[k] != v}
        if changes:
            self._event(task, 'edit', changes=changes, forced=force)
            self.save()
        return True

    @mutation
    def note(self, task_id, text, next_step=None):
        task = self.require(task_id)
        if not text.strip():
            raise ValueError('进展备注不能为空')
        task.notes.append({'at': now(), 'actor': self.actor, 'text': text})
        if next_step is not None:
            self._writable(task)
            task.next_step = next_step
        self._event(task, 'note', text=text, next_step=next_step)
        self.save()
        return task

    @mutation
    def block(self, task_id, reason, force=False):
        task = self.require(task_id)
        self._writable(task, force)
        if task.status == TaskStatus.DONE:
            raise ValueError('已完成任务需要先 undo')
        if not reason.strip():
            raise ValueError('阻塞原因不能为空')
        task.status = TaskStatus.BLOCKED
        task.blocked_reason = reason
        self._event(task, 'block', reason=reason, forced=force)
        self.save()
        return task

    @mutation
    def delete(self, task_id, force=False):
        task = self.require(task_id)
        self._writable(task, force)
        if any(task.id in t.dependencies or t.parent_id == task.id for t in self.tasks):
            raise ValueError('任务仍被依赖或包含子任务，请先解除关联')
        self.tasks.remove(task)
        self.save()
        return True

    def list(self, status=None, priority=None, tags=None, sort_by=None, branch=None, owner=None, include_done=True):
        tasks = [t for t in self.tasks if (include_done or t.status != TaskStatus.DONE)
                 and (not status or t.status.value == status)
                 and (not priority or t.priority.value == priority)
                 and (not tags or any(tag in t.tags for tag in tags))
                 and (branch is None or branch in t.branches)
                 and (not owner or t.owner == owner)]
        if sort_by == 'created':
            tasks.sort(key=lambda t: t.created_at, reverse=True)
        elif sort_by == 'due':
            tasks.sort(key=lambda t: (t.due_day() or date.max, t.due_date or ''))
        elif sort_by == 'priority':
            tasks.sort(key=lambda t: t.priority.rank(), reverse=True)
        elif sort_by == 'status':
            order = {'in_progress': 0, 'todo': 1, 'blocked': 2, 'review': 3, 'done': 4}
            tasks.sort(key=lambda t: order[t.status.value])
        return tasks

    def next_tasks(self):
        tasks = [t for t in self.tasks if t.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS)
                 and not self.blockers(t)]
        return sorted(tasks, key=lambda t: (t.status != TaskStatus.IN_PROGRESS,
                      not t.is_overdue(), -t.priority.rank(), t.due_day() or date.max, t.created_at))

    def today(self):
        return [t for t in self.list(include_done=False, sort_by='priority')
                if t.status == TaskStatus.IN_PROGRESS or (t.due_day() and t.due_day() <= date.today())]

    def search(self, keyword):
        needle = keyword.lower()
        return [t for t in self.tasks if needle in json.dumps(t.to_dict(), ensure_ascii=False).lower()]

    def get_overdue_tasks(self):
        return [t for t in self.tasks if t.is_overdue()]

    def get_due_soon_tasks(self, days=1):
        return [t for t in self.tasks if t.is_due_soon(days)]

    def get_summary_tasks(self, date=None):
        target = normalize_due(date or 'today')[:10]
        return [t for t in self.tasks if t.status != TaskStatus.DONE and t.created_at[:10] <= target]

    def continue_task(self, task_id, new_date):
        self.edit(task_id, due_date=new_date)
        return self.require(task_id)

    @mutation
    def reschedule(self, task_ids, due_date):
        due = normalize_due(due_date)
        tasks = [self.require(task_id) for task_id in task_ids]
        for task in tasks:
            self._writable(task)
            task.due_date = due
            self._event(task, 'postpone', due_date=due)
        if tasks:
            self.save()
        return tasks

    @mutation
    def import_tasks(self, records):
        incoming = [Task.from_dict(record) for record in records]
        ids = {t.id for t in self.tasks}
        keys = {t.request_id for t in self.tasks if t.request_id}
        for task in incoming:
            if task.id in ids or (task.request_id and task.request_id in keys):
                raise ValueError('导入包含重复 ID 或 request-id: ' + task.id)
            ids.add(task.id)
            if task.request_id:
                keys.add(task.request_id)
        self.tasks.extend(incoming)
        for task in incoming:
            self._references(task)
            self._event(task, 'import')
        self.save()
        return incoming

    def handoff(self, task_id=None):
        selected = [self.require(task_id)] if task_id else self.list(include_done=False, sort_by='status')
        return {'schema_version': 1, 'tasks': [dict(t.to_dict(), unresolved_dependencies=self.blockers(t)) for t in selected],
                'dependencies': [t.to_dict() for t in self.tasks
                                 if any(t.id in chosen.dependencies or t.parent_id == chosen.id for chosen in selected)],
                'next': [t.id for t in self.next_tasks()]}
