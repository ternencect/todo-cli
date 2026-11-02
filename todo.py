#!/usr/bin/env python3
"""Local project tasks for humans and coding agents. No model credentials required."""
import argparse
import getpass
import json
import os
from pathlib import Path
import sys
from datetime import date
from todo_core import Task, TaskManager, TaskStatus, TaskPriority, __version__
from todo_core.project import discover, register, projects, Project, git
from todo_core.storage import TaskStorage, StorageError, ConflictError
from todo_core.manager import NotFoundError

COMMAND_ALIASES = {'-a': 'add', '-l': 'list', '-s': 'show', '-e': 'edit', '-d': 'delete',
                   '/': 'search', '-S': 'search', '-m': 'summary', '-': 'select'}


class UsageError(ValueError):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def make_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--json', action='store_true', default=argparse.SUPPRESS, help='结构化输出（包括错误）')
    common.add_argument('--file', default=argparse.SUPPRESS, help='显式任务文件；用于旧数据或独立清单')
    common.add_argument('--project', default=argparse.SUPPRESS, help='项目 ID、唯一名称或目录')
    common.add_argument('--actor', default=argparse.SUPPRESS, help='操作者/Agent 名称（或 TODO_ACTOR）')
    parser = Parser(description='todo-cli — 项目任务、AI 上下文与工作交接', parents=[common])
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    subs = parser.add_subparsers(dest='command', parser_class=Parser)
    def command(name, help_text):
        return subs.add_parser(name, help=help_text, parents=[common])
    command('init', '注册当前项目；同仓库分支和 worktree 共享任务')
    command('projects', '列出本机已注册项目')
    command('context', '查看项目、分支、worktree 与存储位置')
    p = command('add', '记录任务及验收条件')
    p.add_argument('title', nargs='?')
    p.add_argument('-d', '--description')
    p.add_argument('-p', '--priority', choices=[x.value for x in TaskPriority])
    p.add_argument('-t', '--tags', nargs='*')
    p.add_argument('--due', help='YYYY-MM-DD / today / tomorrow / +3d / ISO 时间')
    p.add_argument('--acceptance', action='append', help='验收条件，可重复')
    p.add_argument('--branch', action='append', help='关联分支，可重复，默认当前分支')
    p.add_argument('--no-branch', action='store_true')
    p.add_argument('--depends-on', action='append', help='前置任务 ID，可重复')
    p.add_argument('--parent', help='父任务 ID')
    p.add_argument('--link', action='append', help='Issue、PR、提交或产物引用，可重复')
    p.add_argument('--request-id', help='重试去重键，项目内唯一')
    p.add_argument('--input-json', help='任务参数 JSON；- 从 stdin 读取')
    for name, help_text in [('list', '查看任务，默认隐藏已完成'), ('next', '查看可执行任务'),
                            ('today', '今天到期、逾期和进行中的任务'), ('inbox', '未安排日期和分支的待办')]:
        p = command(name, help_text)
        p.add_argument('--status', choices=[x.value for x in TaskStatus])
        p.add_argument('--priority', choices=[x.value for x in TaskPriority])
        p.add_argument('-t', '--tags', nargs='*')
        p.add_argument('--sort', choices=['created', 'due', 'priority', 'status'])
        p.add_argument('--branch')
        p.add_argument('--current-branch', action='store_true')
        p.add_argument('--owner')
        p.add_argument('--all', action='store_true', help='包含已完成任务')
        p.add_argument('--all-projects', action='store_true', help='汇总本机已注册项目')
        p.add_argument('--limit', type=int, help='最多展示数量')
    p = command('show', '查看完整任务上下文')
    p.add_argument('id')
    p = command('edit', '修改任务；列表参数整体替换')
    p.add_argument('id')
    p.add_argument('--title')
    p.add_argument('--description')
    p.add_argument('--status', choices=[x.value for x in TaskStatus if x != TaskStatus.BLOCKED])
    p.add_argument('--priority', choices=[x.value for x in TaskPriority])
    p.add_argument('-t', '--tags', nargs='*')
    p.add_argument('--due')
    p.add_argument('--clear-due', action='store_true')
    for name in ('branches', 'acceptance', 'dependencies', 'links'):
        p.add_argument('--' + name, nargs='*', help='整体替换；不传值则清空')
    p.add_argument('--parent', dest='parent_id', help='空字符串解除父任务')
    p.add_argument('--result')
    p.add_argument('--next-step')
    p.add_argument('--force', action='store_true', help='允许修改其他操作者认领的任务')
    for name, help_text in [('start', '认领并开始任务'), ('done', '完成任务并记录结果'),
                            ('undo', '重新打开任务并解除认领'), ('review', '提交待人工验收')]:
        p = command(name, help_text)
        p.add_argument('id')
        p.add_argument('--result')
        p.add_argument('--branch', help='追加关联分支，start 默认当前分支')
        p.add_argument('--force', action='store_true', help='显式接管其他操作者的任务')
    p = command('block', '记录阻塞原因')
    p.add_argument('id')
    p.add_argument('reason')
    p.add_argument('--force', action='store_true')
    p = command('note', '保存进展与下一步，供下次会话接力')
    p.add_argument('id')
    p.add_argument('text')
    p.add_argument('--next-step')
    p = command('postpone', '调整原任务日期，不复制任务')
    p.add_argument('id')
    p.add_argument('due')
    p.add_argument('--force', action='store_true')
    p = command('link', '追加分支或产物引用')
    p.add_argument('id')
    p.add_argument('--branch', action='append')
    p.add_argument('--url', action='append', help='引用 URL、提交或文件路径')
    p.add_argument('--force', action='store_true')
    p = command('history', '查看任务操作记录')
    p.add_argument('id')
    p = command('delete', '删除任务（被引用的任务不可删除）')
    p.add_argument('id')
    p.add_argument('-y', '--yes', action='store_true')
    p.add_argument('--force', action='store_true')
    p = command('search', '搜索任务及上下文')
    p.add_argument('keyword')
    p = command('summary', '查看指定日期之前创建的当前未完成任务')
    p.add_argument('--date')
    p.add_argument('--continue', dest='continue_task', action='store_true', help='将这些原任务日期调整到今天')
    p.add_argument('-y', '--yes', action='store_true')
    p = command('select', '交互式选择并查看任务')
    p.add_argument('--status', choices=[x.value for x in TaskStatus])
    p = command('handoff', '导出 Markdown/JSON 交接包，不调用模型或执行任务')
    p.add_argument('id', nargs='?', help='省略则包含项目所有未完成任务')
    command('export', '导出完整任务数组（配合 --json）')
    p = command('import', '原子导入旧版/导出文件；冲突时全部拒绝')
    p.add_argument('source', help='JSON 文件，- 从 stdin 读取')
    return parser


def resolve_project(args):
    current = discover()
    selection = getattr(args, 'project', None)
    if selection:
        matches = [p for p in projects() if p['id'] == selection or p['name'] == selection]
        if len(matches) > 1:
            raise ValueError('项目名称有歧义，请使用项目 ID')
        if matches:
            record = matches[0]
            selected = discover(record['root'])
            # When inside a linked worktree, preserve its actual branch and directory.
            if current.id == record['id']:
                selected = current
            selected.id, selected.name, selected.storage = record['id'], record['name'], record['storage']
            current = selected
        elif Path(selection).is_dir():
            current = discover(selection)
        else:
            raise NotFoundError('未找到项目: ' + selection)
    explicit = getattr(args, 'file', None)
    if explicit:
        if selection:
            raise UsageError('--file 与 --project 不能同时使用')
        current.storage = str(Path(explicit).expanduser().resolve())
    return current


def context(project):
    data = project.to_dict()
    status = git(project.worktree, 'status', '--porcelain')
    data['git_status'] = status.splitlines() if status else []
    data['head'] = git(project.worktree, 'rev-parse', 'HEAD')
    return data


def task_data(task, manager, project):
    return dict(task.to_dict(), project_id=project.id, project_name=project.name,
                unresolved_dependencies=manager.blockers(task))


def read_json(source, inline=False):
    try:
        raw = sys.stdin.read() if source == '-' else source if inline else Path(source).read_text(encoding='utf-8')
        return json.loads(raw)
    except (ValueError, OSError) as exc:
        raise ValueError('无法解析 JSON 输入: ' + str(exc)) from exc


def require_confirmation(args, message):
    if getattr(args, 'yes', False):
        return
    if getattr(args, 'json', False) or not sys.stdin.isatty():
        raise UsageError('此操作需要 --yes（非交互调用不会等待输入）')
    if input(message + ' (y/N): ').strip().lower() != 'y':
        raise ValueError('操作已取消')


def run(args):
    if args.command == 'projects':
        return [dict(p, active=len(TaskManager(TaskStorage(p['storage'])).list(include_done=False))) for p in projects()]
    project = resolve_project(args)
    if args.command == 'context':
        return context(project)
    if args.command == 'init':
        if getattr(args, 'file', None):
            raise UsageError('init 不支持 --file；直接用 --file 执行 add/import')
        if not git(project.worktree, 'rev-parse', '--show-toplevel'):
            marker = Path(project.root) / '.todo-project'
            if not marker.exists():
                marker.write_text('Local todo-cli project marker; task data lives outside the repository.\n', encoding='utf-8')
        register(project)
        return context(project)
    actor = getattr(args, 'actor', None) or os.environ.get('TODO_ACTOR') or getpass.getuser()
    if not actor.strip():
        raise ValueError('actor 不能为空')
    manager = TaskManager(TaskStorage(project.storage), actor=actor)
    cmd = args.command
    if cmd in ('list', 'next', 'today', 'inbox'):
        if args.limit is not None and args.limit < 1:
            raise UsageError('--limit 必须大于 0')
        if args.all_projects and (getattr(args, 'file', None) or getattr(args, 'project', None) or args.current_branch):
            raise UsageError('--all-projects 不能与 --file、--project 或 --current-branch 混用')
        branch = args.branch
        if args.current_branch:
            if not project.branch:
                raise UsageError('当前目录没有 Git 分支')
            if branch and branch != project.branch:
                raise UsageError('--branch 与 --current-branch 冲突')
            branch = project.branch
        sources = [(manager, project)]
        if args.all_projects:
            sources = [(TaskManager(TaskStorage(p['storage']), actor), Project(p['id'], p['name'], p['root'], '', p['storage'], p['root']))
                       for p in projects()]
        result = []
        for source, info in sources:
            tasks = source.list(status=args.status, priority=args.priority, tags=args.tags, sort_by=args.sort,
                                branch=branch, owner=args.owner, include_done=args.all or args.status == 'done')
            if cmd == 'next':
                eligible = {t.id for t in tasks}
                tasks = [t for t in source.next_tasks() if t.id in eligible]
            elif cmd == 'today':
                eligible = {t.id for t in source.today()}
                tasks = [t for t in tasks if t.id in eligible]
            elif cmd == 'inbox':
                tasks = [t for t in tasks if t.status == TaskStatus.TODO and not t.due_date and not t.branches]
            result.extend(task_data(t, source, info) for t in tasks)
        if args.all_projects and (args.sort or cmd == 'next'):
            def record_task(item):
                return Task(id=item['id'], title=item['title'], status=TaskStatus(item['status']),
                            priority=TaskPriority(item['priority']), due_date=item['due_date'],
                            created_at=item['created_at'])
            if cmd == 'next':
                def next_key(item):
                    task = record_task(item)
                    return (task.status != TaskStatus.IN_PROGRESS, not task.is_overdue(),
                            -task.priority.rank(), task.due_day() or date.max, task.created_at)
                result.sort(key=next_key)
            elif args.sort == 'priority':
                result.sort(key=lambda item: -TaskPriority(item['priority']).rank())
            elif args.sort == 'created':
                result.sort(key=lambda item: item['created_at'], reverse=True)
            elif args.sort == 'due':
                result.sort(key=lambda item: record_task(item).due_day() or date.max)
            elif args.sort == 'status':
                order = {'in_progress': 0, 'todo': 1, 'blocked': 2, 'review': 3, 'done': 4}
                result.sort(key=lambda item: order[item['status']])
        return result[:args.limit] if args.limit else result
    if cmd == 'add':
        data = {}
        if args.input_json:
            data = read_json(args.input_json, inline=True)
            if not isinstance(data, dict):
                raise UsageError('--input-json 必须是对象')
            allowed = {'title', 'description', 'priority', 'tags', 'due_date', 'branches', 'acceptance',
                       'dependencies', 'parent_id', 'links', 'request_id'}
            if set(data) - allowed:
                raise UsageError('未知输入字段: ' + ', '.join(sorted(set(data) - allowed)))
        for key, value in {'title': args.title, 'description': args.description, 'priority': args.priority,
                           'tags': args.tags, 'due_date': args.due, 'branches': args.branch,
                           'acceptance': args.acceptance, 'dependencies': args.depends_on,
                           'parent_id': args.parent, 'links': args.link, 'request_id': args.request_id}.items():
            if value is not None:
                data[key] = value
        if not isinstance(data.get('title'), str) or not data['title'].strip():
            raise UsageError('请提供任务标题')
        if args.no_branch:
            data['branches'] = []
        data.setdefault('branches', [project.branch] if project.branch else [])
        task = manager.add(**data)
        if not getattr(args, 'file', None):
            register(project)
        return task_data(task, manager, project)
    if cmd == 'show':
        return task_data(manager.require(args.id), manager, project)
    if cmd == 'edit':
        if args.clear_due and args.due:
            raise UsageError('--due 与 --clear-due 不能同时使用')
        changes = {key: getattr(args, key) for key in ('title', 'description', 'status', 'priority', 'tags',
                   'branches', 'acceptance', 'dependencies', 'parent_id', 'links', 'result', 'next_step', 'force')}
        changes['due_date'] = '' if args.clear_due else args.due
        manager.edit(args.id, **changes)
    elif cmd in ('start', 'done', 'undo', 'review'):
        task = manager.require(args.id)
        if cmd == 'start' and task.status == TaskStatus.DONE:
            raise ValueError('已完成任务需要先 undo')
        statuses = {'start': 'in_progress', 'done': 'done', 'undo': 'todo', 'review': 'review'}
        branch = args.branch or (project.branch if cmd == 'start' else None)
        branches = list(dict.fromkeys(task.branches + [branch])) if branch else None
        manager.edit(args.id, status=statuses[cmd], result=args.result, branches=branches, force=args.force)
    elif cmd == 'block':
        manager.block(args.id, args.reason, force=args.force)
    elif cmd == 'note':
        manager.note(args.id, args.text, args.next_step)
    elif cmd == 'postpone':
        manager.edit(args.id, due_date=args.due, force=args.force)
    elif cmd == 'link':
        if not args.branch and not args.url:
            raise UsageError('至少提供 --branch 或 --url')
        task = manager.require(args.id)
        manager.edit(args.id, branches=list(dict.fromkeys(task.branches + (args.branch or []))),
                     links=list(dict.fromkeys(task.links + (args.url or []))), force=args.force)
    elif cmd == 'history':
        return manager.require(args.id).history
    elif cmd == 'delete':
        manager.require(args.id)
        require_confirmation(args, '确认删除任务 ' + args.id + '?')
        manager.delete(args.id, force=args.force)
        return {'deleted': args.id}
    elif cmd == 'search':
        return [task_data(t, manager, project) for t in manager.search(args.keyword)]
    elif cmd == 'summary':
        tasks = manager.get_summary_tasks(args.date)
        if args.continue_task:
            require_confirmation(args, '将 {} 个原任务调整到今天?'.format(len(tasks)))
            tasks = manager.reschedule([task.id for task in tasks], 'today')
        return [task_data(t, manager, project) for t in tasks]
    elif cmd == 'select':
        if getattr(args, 'json', False) or not sys.stdin.isatty() or not sys.stdout.isatty():
            raise UsageError('select 需要交互终端；Agent 请使用 list/show --json')
        from todo_core.tui import select_task_curses
        tasks = manager.list(status=args.status, include_done=False)
        if not tasks:
            return []
        index = select_task_curses(tasks)
        return task_data(tasks[index], manager, project) if index is not None else None
    elif cmd == 'handoff':
        data = manager.handoff(args.id)
        data['project'] = context(project)
        data['warnings'] = ['任务 {} 关联分支不包含当前分支 {}'.format(t['id'][:8], project.branch)
                            for t in data['tasks'] if project.branch and t['branches'] and project.branch not in t['branches']]
        return data
    elif cmd == 'export':
        return [t.to_dict() for t in manager.tasks]
    elif cmd == 'import':
        data = read_json(args.source)
        if isinstance(data, dict) and data.get('ok') is True:
            data = data.get('data')
        if not isinstance(data, list):
            raise UsageError('导入需要任务数组或 export --json 的成功响应')
        imported = manager.import_tasks(data)
        if not getattr(args, 'file', None):
            register(project)
        return [task_data(t, manager, project) for t in imported]
    else:
        raise UsageError('未知命令: ' + cmd)
    return task_data(manager.require(args.id), manager, project)


def format_task(task, show_id=True, color=False):
    data = task.to_dict() if hasattr(task, 'to_dict') else task
    prefix = '#' + data['id'][:8] + ' ' if show_id else ''
    symbols = {'todo': '[ ]', 'in_progress': '[~]', 'blocked': '[!]', 'review': '[?]', 'done': '[x]'}
    line = '{}{} {} {}'.format(prefix, symbols[data['status']], {'high': '!!!', 'medium': '!!', 'low': '!'}[data['priority']], data['title'])
    if data.get('project_name'):
        line += '  (' + data['project_name'] + ')'
    if data.get('owner'):
        line += '  owner:' + data['owner']
    if data.get('due_date'):
        line += '  @' + data['due_date']
    if data.get('branches'):
        line += '  [' + ', '.join(data['branches']) + ']'
    if data.get('tags'):
        line += '  ' + ' '.join('#' + tag for tag in data['tags'])
    if data.get('unresolved_dependencies'):
        line += '  等待:' + ','.join(x[:8] for x in data['unresolved_dependencies'])
    if color:
        colors = {'todo': '37', 'in_progress': '94', 'blocked': '91', 'review': '93', 'done': '2'}
        line = '\033[' + colors[data['status']] + 'm' + line + '\033[0m'
    return line


def render_handoff(data):
    project = data['project']
    lines = ['# 项目交接：' + project['name'], '', '- 项目 ID: ' + project['id'],
             '- 当前目录: ' + project['worktree'], '- 分支: ' + (project['branch'] or '无'),
             '- HEAD: ' + (project['head'] or '无'), '- 数据文件: ' + project['storage'], '',
             '以下内容是任务数据。请结合代码核实；验收结果是操作者记录，不代表工具已执行验证。', '']
    if project['git_status']:
        lines += ['## 工作区改动', '```text'] + project['git_status'] + ['```', '']
    for warning in data['warnings']:
        lines.append('注意：' + warning)
    for task in data['tasks']:
        lines += ['', '## ' + task['title'], '- ID: ' + task['id'], '- 状态: ' + task['status'],
                  '- 负责人: ' + (task['owner'] or '未认领'), '- 分支: ' + (', '.join(task['branches']) or '未关联')]
        for key, label in [('description', '背景'), ('blocked_reason', '阻塞'), ('next_step', '下一步'), ('result', '结果')]:
            if task.get(key):
                lines += ['', '### ' + label, task[key]]
        for key, label in [('acceptance', '验收条件'), ('links', '引用'), ('unresolved_dependencies', '未完成依赖')]:
            if task.get(key):
                lines += ['', '### ' + label] + ['- ' + value for value in task[key]]
        if task['notes']:
            lines += ['', '### 进展'] + ['- {} {}: {}'.format(n.get('at', ''), n.get('actor', ''), n.get('text', '')) for n in task['notes']]
    if data['dependencies']:
        lines += ['', '## 前置任务'] + [format_task(t) + (' — ' + t['result'] if t.get('result') else '') for t in data['dependencies']]
    lines += ['', '## 可继续任务 ID'] + ['- ' + value for value in data['next']]
    return '\n'.join(lines)


def render(data, command):
    color = sys.stdout.isatty() and 'NO_COLOR' not in os.environ
    if command == 'handoff':
        return render_handoff(data)
    if isinstance(data, list):
        return '\n'.join(format_task(item, color=color) if isinstance(item, dict) and 'title' in item and 'status' in item
                         else json.dumps(item, ensure_ascii=False) for item in data) or '没有找到任务'
    if isinstance(data, dict) and 'title' in data and 'status' in data:
        lines = [format_task(data, color=color)]
        labels = {'id': 'ID', 'description': '描述', 'acceptance': '验收条件', 'dependencies': '依赖',
                  'parent_id': '父任务', 'blocked_reason': '阻塞原因', 'next_step': '下一步', 'result': '结果',
                  'links': '引用', 'notes': '进展', 'created_at': '创建时间', 'completed_at': '完成时间'}
        for key, label in labels.items():
            value = data.get(key)
            if value:
                lines.append('  {}: {}'.format(label, json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value))
        return '\n'.join(lines)
    return json.dumps(data, ensure_ascii=False, indent=2)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Legacy command aliases are accepted only at the command position, never in values.
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in ('--file', '--project', '--actor'):
            index += 2
            continue
        if token == '--json' or any(token.startswith(option + '=') for option in ('--file', '--project', '--actor')):
            index += 1
            continue
        if token in COMMAND_ALIASES:
            argv[index] = COMMAND_ALIASES[token]
        break
    json_mode = '--json' in argv
    try:
        parser = make_parser()
        args = parser.parse_args(argv)
        if not args.command:
            if json_mode:
                raise UsageError('请指定命令；使用 --help 查看帮助')
            parser.print_help()
            return 0
        data = run(args)
        if getattr(args, 'json', False):
            print(json.dumps({'ok': True, 'schema_version': 1, 'data': data}, ensure_ascii=False))
        else:
            print(render(data, args.command))
        return 0
    except (ValueError, StorageError, ConflictError, OSError, TypeError) as exc:
        code = 'conflict' if isinstance(exc, ConflictError) else 'storage_error' if isinstance(exc, (StorageError, OSError)) else 'not_found' if isinstance(exc, NotFoundError) else 'invalid_input'
        exit_code = {'conflict': 4, 'storage_error': 5, 'not_found': 3, 'invalid_input': 2}[code]
        if json_mode:
            print(json.dumps({'ok': False, 'schema_version': 1, 'error': {'code': code, 'message': str(exc)}}, ensure_ascii=False))
        else:
            print('错误: ' + str(exc), file=sys.stderr)
        return exit_code
    except (KeyboardInterrupt, EOFError):
        if json_mode:
            print(json.dumps({'ok': False, 'schema_version': 1, 'error': {'code': 'cancelled', 'message': '操作已取消'}}, ensure_ascii=False))
        else:
            print('操作已取消', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
