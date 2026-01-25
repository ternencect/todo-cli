"""
任务管理核心逻辑
"""
from typing import List, Optional, Callable
from datetime import datetime
from .model import Task, TaskStatus, TaskPriority
from .storage import TaskStorage


class TaskManager:
    """任务管理器"""

    def __init__(self, storage: Optional[TaskStorage] = None):
        """
        初始化任务管理器

        Args:
            storage: 存储对象，默认创建新的 TaskStorage
        """
        self.storage = storage or TaskStorage()
        self.tasks: List[Task] = self.storage.load()

    def save(self):
        """保存任务到存储"""
        self.storage.save(self.tasks)

    def add(
        self,
        title: str,
        description: Optional[str] = None,
        priority: str = "medium",
        tags: Optional[List[str]] = None,
        due_date: Optional[str] = None,
    ) -> Task:
        """
        添加新任务

        Args:
            title: 任务标题
            description: 任务描述
            priority: 优先级 (high/medium/low)
            tags: 标签列表
            due_date: 截止日期 (YYYY-MM-DD)

        Returns:
            创建的任务对象
        """
        task = Task(
            title=title,
            description=description,
            priority=TaskPriority.from_string(priority),
            tags=tags or [],
            due_date=due_date,
        )
        self.tasks.append(task)
        self.save()
        return task

    def delete(self, task_id: str) -> bool:
        """
        删除任务

        Args:
            task_id: 任务 ID（支持完整 ID 或前 8 位）

        Returns:
            是否删除成功
        """
        task = self.get(task_id)
        if task:
            self.tasks.remove(task)
            self.save()
            return True
        return False

    def get(self, task_id: str) -> Optional[Task]:
        """
        获取指定任务

        Args:
            task_id: 任务 ID（支持完整 ID 或前 8 位）

        Returns:
            任务对象，不存在返回 None
        """
        # 先尝试完整匹配
        for task in self.tasks:
            if task.id == task_id:
                return task

        # 再尝试前缀匹配（最少 4 位）
        if len(task_id) >= 4:
            for task in self.tasks:
                if task.id.startswith(task_id):
                    return task

        return None

    def edit(
        self,
        task_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[List[str]] = None,
        due_date: Optional[str] = None,
    ) -> bool:
        """
        编辑任务

        Args:
            task_id: 任务 ID
            title: 新标题
            description: 新描述
            status: 新状态
            priority: 新优先级
            tags: 新标签列表
            due_date: 新截止日期

        Returns:
            是否编辑成功
        """
        task = self.get(task_id)
        if not task:
            return False

        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if status is not None:
            task.status = TaskStatus.from_string(status)
            if task.status == TaskStatus.DONE and not task.completed_at:
                task.completed_at = datetime.now().isoformat()
        if priority is not None:
            task.priority = TaskPriority.from_string(priority)
        if tags is not None:
            task.tags = tags
        if due_date is not None:
            task.due_date = due_date

        self.save()
        return True

    def list(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[List[str]] = None,
        sort_by: Optional[str] = None,
    ) -> List[Task]:
        """
        列出任务（支持过滤和排序）

        Args:
            status: 按状态过滤
            priority: 按优先级过滤
            tags: 按标签过滤（匹配任一标签）
            sort_by: 排序字段 (created, due, priority, status)

        Returns:
            过滤后的任务列表
        """
        tasks = self.tasks.copy()

        # 过滤
        if status:
            tasks = [t for t in tasks if t.status.value == status.lower()]
        if priority:
            tasks = [t for t in tasks if t.priority.value == priority.lower()]
        if tags:
            tasks = [t for t in tasks if any(tag in t.tags for tag in tags)]

        # 排序
        if sort_by:
            if sort_by == "created":
                tasks.sort(key=lambda t: t.created_at, reverse=True)
            elif sort_by == "due":
                tasks.sort(key=lambda t: t.due_date or "9999-12-31")
            elif sort_by == "priority":
                tasks.sort(key=lambda t: t.priority.rank(), reverse=True)
            elif sort_by == "status":
                status_order = {
                    TaskStatus.IN_PROGRESS: 0,
                    TaskStatus.TODO: 1,
                    TaskStatus.DONE: 2,
                }
                tasks.sort(key=lambda t: status_order.get(t.status, 3))

        return tasks

    def search(self, keyword: str) -> List[Task]:
        """
        搜索任务

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的任务列表
        """
        keyword_lower = keyword.lower()
        results = []
        for task in self.tasks:
            if (
                keyword_lower in task.title.lower()
                or (task.description and keyword_lower in task.description.lower())
                or any(keyword_lower in tag.lower() for tag in task.tags)
            ):
                results.append(task)
        return results

    def get_overdue_tasks(self) -> List[Task]:
        """获取所有过期任务"""
        return [t for t in self.tasks if t.is_overdue()]

    def get_due_soon_tasks(self, days: int = 1) -> List[Task]:
        """获取即将到期的任务"""
        return [t for t in self.tasks if t.is_due_soon(days)]

    def get_summary_tasks(self, date: Optional[str] = None) -> List[Task]:
        """
        获取指定日期的未完成任务（用于每日总结）

        Args:
            date: 日期 (YYYY-MM-DD)，默认为今天

        Returns:
            未完成任务列表
        """
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        return [
            t for t in self.tasks
            if t.status != TaskStatus.DONE
            and t.created_at <= f"{target_date}T23:59:59"
        ]

    def continue_task(self, task_id: str, new_date: str) -> Optional[Task]:
        """
        将任务延续到新日期

        Args:
            task_id: 原任务 ID
            new_date: 新日期 (YYYY-MM-DD)

        Returns:
            新创建的延续任务
        """
        original_task = self.get(task_id)
        if not original_task:
            return None

        # 创建新任务
        new_task = Task(
            title=original_task.title,
            description=original_task.description,
            priority=original_task.priority,
            tags=original_task.tags + [f"continued:{new_date}"],
            due_date=new_date,
            is_continued=True,
        )
        self.tasks.append(new_task)
        self.save()
        return new_task
