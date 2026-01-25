#!/usr/bin/env python3
"""
todo-cli - 命令行待办事项管理工具
"""
import argparse
import sys
from datetime import datetime
from todo_core import TaskManager, TaskStatus, TaskPriority


# ANSI 颜色代码
class Colors:
    """ANSI 颜色代码"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # 前景色
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # 明亮版本
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # 背景
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


def colorize(text: str, color: str) -> str:
    """为文本添加颜色"""
    return f"{color}{text}{Colors.RESET}"


def get_priority_color(priority: TaskPriority) -> str:
    """获取优先级对应的颜色"""
    return {
        TaskPriority.HIGH: Colors.BRIGHT_RED,
        TaskPriority.MEDIUM: Colors.BRIGHT_YELLOW,
        TaskPriority.LOW: Colors.BRIGHT_GREEN,
    }.get(priority, Colors.WHITE)


def get_status_color(status: TaskStatus) -> str:
    """获取状态对应的颜色"""
    return {
        TaskStatus.TODO: Colors.WHITE,
        TaskStatus.IN_PROGRESS: Colors.BRIGHT_BLUE,
        TaskStatus.DONE: Colors.DIM,
    }.get(status, Colors.WHITE)


def format_task(task, show_id: bool = True) -> str:
    """格式化任务显示"""
    priority_color = get_priority_color(task.priority)
    status_color = get_status_color(task.status)

    # 状态标记
    status_symbols = {
        TaskStatus.TODO: "[ ]",
        TaskStatus.IN_PROGRESS: "[~]",
        TaskStatus.DONE: "[x]",
    }
    status_symbol = status_symbols.get(task.status, "[?]")

    # 优先级标记
    priority_symbols = {
        TaskPriority.HIGH: "!!!",
        TaskPriority.MEDIUM: "!!",
        TaskPriority.LOW: "!",
    }
    priority_symbol = priority_symbols.get(task.priority, "!")

    # 构建输出
    parts = []

    # ID
    if show_id:
        id_str = task.id[:8]
        parts.append(colorize(f"#{id_str}", Colors.CYAN))

    # 状态
    parts.append(colorize(status_symbol, status_color))

    # 优先级
    parts.append(colorize(priority_symbol, priority_color))

    # 标题
    title = task.title
    if task.status == TaskStatus.DONE:
        title = colorize(title, status_color)
    parts.append(title)

    # 标签
    if task.tags:
        tags_str = " ".join(f"#{t}" for t in task.tags)
        # 延续任务标签用紫色
        if any(t.startswith("continued:") for t in task.tags):
            tags_str = colorize(tags_str, Colors.BRIGHT_MAGENTA)
        else:
            tags_str = colorize(tags_str, Colors.CYAN)
        parts.append(tags_str)

    # 截止日期
    if task.due_date:
        due_str = task.due_date
        if task.is_overdue():
            due_str = colorize(f"{due_str} 过期!", Colors.BRIGHT_RED)
        elif task.is_due_soon():
            due_str = colorize(f"{due_str} 即将到期", Colors.BRIGHT_YELLOW)
        else:
            due_str = colorize(due_str, Colors.GREEN)
        parts.append(f"@{due_str}")

    return " ".join(parts)


def cmd_add(args):
    """添加任务"""
    manager = TaskManager()
    task = manager.add(
        title=args.title,
        description=args.description,
        priority=args.priority,
        tags=args.tags,
        due_date=args.due,
    )
    print(colorize("✓ 已添加任务:", Colors.BRIGHT_GREEN))
    print(f"  {format_task(task)}")


def cmd_list(args):
    """列出任务"""
    manager = TaskManager()
    tasks = manager.list(
        status=args.status,
        priority=args.priority,
        tags=args.tags,
        sort_by=args.sort,
    )

    if not tasks:
        print(colorize("没有找到任务", Colors.DIM))
        return

    print(colorize(f"\n找到 {len(tasks)} 个任务:\n", Colors.BRIGHT_CYAN))

    for i, task in enumerate(tasks, 1):
        prefix = f"{i}. "
        print(f"{prefix}{format_task(task)}")


def cmd_show(args):
    """显示任务详情"""
    manager = TaskManager()
    task = manager.get(args.id)

    if not task:
        print(colorize(f"未找到任务: {args.id}", Colors.BRIGHT_RED))
        return

    print(colorize("\n任务详情:\n", Colors.BRIGHT_CYAN))
    print(f"  ID:          {task.id}")
    print(f"  标题:        {task.title}")
    if task.description:
        print(f"  描述:        {task.description}")
    print(f"  状态:        {colorize(task.status.value, get_status_color(task.status))}")
    print(f"  优先级:      {colorize(task.priority.value, get_priority_color(task.priority))}")
    if task.tags:
        print(f"  标签:        {', '.join(task.tags)}")
    if task.due_date:
        print(f"  截止日期:    {task.due_date}")
    print(f"  创建时间:    {task.created_at}")
    if task.completed_at:
        print(f"  完成时间:    {task.completed_at}")


def cmd_edit(args):
    """编辑任务"""
    manager = TaskManager()
    success = manager.edit(
        task_id=args.id,
        title=args.title,
        description=args.description,
        status=args.status,
        priority=args.priority,
        tags=args.tags,
        due_date=args.due,
    )

    if success:
        task = manager.get(args.id)
        print(colorize("✓ 任务已更新:", Colors.BRIGHT_GREEN))
        print(f"  {format_task(task)}")
    else:
        print(colorize(f"未找到任务: {args.id}", Colors.BRIGHT_RED))


def cmd_delete(args):
    """删除任务"""
    manager = TaskManager()
    task = manager.get(args.id)

    if not task:
        print(colorize(f"未找到任务: {args.id}", Colors.BRIGHT_RED))
        return

    # 确认删除
    print(colorize("将删除以下任务:", Colors.BRIGHT_YELLOW))
    print(f"  {format_task(task)}")
    confirm = input("\n确认删除? (y/N): ")

    if confirm.lower() == 'y':
        if manager.delete(args.id):
            print(colorize("✓ 任务已删除", Colors.BRIGHT_GREEN))
        else:
            print(colorize("删除失败", Colors.BRIGHT_RED))
    else:
        print(colorize("已取消", Colors.DIM))


def cmd_search(args):
    """搜索任务"""
    manager = TaskManager()
    tasks = manager.search(args.keyword)

    if not tasks:
        print(colorize(f"未找到匹配 '{args.keyword}' 的任务", Colors.DIM))
        return

    print(colorize(f"\n找到 {len(tasks)} 个匹配任务:\n", Colors.BRIGHT_CYAN))

    for i, task in enumerate(tasks, 1):
        prefix = f"{i}. "
        print(f"{prefix}{format_task(task)}")


def cmd_summary(args):
    """每日总结"""
    manager = TaskManager()

    # 获取指定日期的未完成任务
    date = args.date or datetime.now().strftime("%Y-%m-%d")
    tasks = manager.get_summary_tasks(date)

    if not tasks:
        print(colorize(f"{date} 没有未完成的任务", Colors.BRIGHT_GREEN))
        return

    print(colorize(f"\n{date} 未完成任务 ({len(tasks)} 个):\n", Colors.BRIGHT_CYAN))

    for i, task in enumerate(tasks, 1):
        print(f"{i}. {format_task(task)}")

    # 询问是否延续任务
    if args.continue_task:
        print(colorize(f"\n是否将任务延续到今天? (y/N): ", Colors.BRIGHT_YELLOW), end="")
        confirm = input().strip().lower()

        if confirm == 'y':
            today = datetime.now().strftime("%Y-%m-%d")
            continued = 0
            for task in tasks:
                new_task = manager.continue_task(task.id, today)
                if new_task:
                    continued += 1

            print(colorize(f"\n✓ 已延续 {continued} 个任务到 {today}", Colors.BRIGHT_GREEN))


def cmd_select(args):
    """交互式选择任务"""
    from todo_core.tui import select_task_curses

    manager = TaskManager()
    tasks = manager.list(status=args.status)

    if not tasks:
        print(colorize("没有可选择的任务", Colors.DIM))
        return

    # 使用 TUI 选择任务
    index = select_task_curses(tasks, "选择要查看的任务")

    if index is not None and 0 <= index < len(tasks):
        task = tasks[index]
        print(colorize("\n任务详情:\n", Colors.BRIGHT_CYAN))
        print(f"  ID:          {task.id}")
        print(f"  标题:        {task.title}")
        if task.description:
            print(f"  描述:        {task.description}")
        print(f"  状态:        {colorize(task.status.value, get_status_color(task.status))}")
        print(f"  优先级:      {colorize(task.priority.value, get_priority_color(task.priority))}")
        if task.tags:
            print(f"  标签:        {', '.join(task.tags)}")
        if task.due_date:
            print(f"  截止日期:    {task.due_date}")
        print(f"  创建时间:    {task.created_at}")
        if task.completed_at:
            print(f"  完成时间:    {task.completed_at}")


# 命令别名映射表
COMMAND_ALIASES = {
    "-a": "add",
    "-l": "list",
    "-s": "show",
    "-e": "edit",
    "-d": "delete",
    "/": "search",
    "-S": "search",
    "-m": "summary",
    "-": "select",
}


def preprocess_args():
    """预处理命令行参数，将命令别名转换为完整命令"""
    if len(sys.argv) < 2:
        return

    # 获取第一个非选项参数作为命令
    cmd = sys.argv[1]

    # 如果是别名，转换为完整命令
    if cmd in COMMAND_ALIASES:
        sys.argv[1] = COMMAND_ALIASES[cmd]


def main():
    """主入口"""
    # 预处理命令别名
    preprocess_args()

    parser = argparse.ArgumentParser(
        description="todo-cli - 命令行待办事项管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # add 命令
    add_parser = subparsers.add_parser("add", help="添加新任务 (简写: -a)", aliases=["-a"])
    add_parser.add_argument("title", help="任务标题")
    add_parser.add_argument("-d", "--description", help="任务描述")
    add_parser.add_argument("-p", "--priority", choices=["high", "medium", "low"],
                          default="medium", help="优先级")
    add_parser.add_argument("-t", "--tags", nargs="*", help="标签列表")
    add_parser.add_argument("--due", help="截止日期 (YYYY-MM-DD)")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出任务 (简写: -l)")
    list_parser.add_argument("--status", choices=["todo", "in_progress", "done"],
                           help="按状态过滤")
    list_parser.add_argument("--priority", choices=["high", "medium", "low"],
                           help="按优先级过滤")
    list_parser.add_argument("-t", "--tags", nargs="*", help="按标签过滤")
    list_parser.add_argument("--sort", choices=["created", "due", "priority", "status"],
                           help="排序方式")

    # show 命令
    show_parser = subparsers.add_parser("show", help="显示任务详情 (简写: -s)")
    show_parser.add_argument("id", help="任务 ID")

    # edit 命令
    edit_parser = subparsers.add_parser("edit", help="编辑任务 (简写: -e)")
    edit_parser.add_argument("id", help="任务 ID")
    edit_parser.add_argument("--title", help="新标题")
    edit_parser.add_argument("--description", help="新描述")
    edit_parser.add_argument("--status", choices=["todo", "in_progress", "done"],
                           help="新状态")
    edit_parser.add_argument("--priority", choices=["high", "medium", "low"],
                           help="新优先级")
    edit_parser.add_argument("-t", "--tags", nargs="*", help="新标签列表")
    edit_parser.add_argument("--due", help="新截止日期")

    # delete 命令
    delete_parser = subparsers.add_parser("delete", help="删除任务 (简写: -d)")
    delete_parser.add_argument("id", help="任务 ID")

    # search 命令
    search_parser = subparsers.add_parser("search", help="搜索任务 (简写: / 或 -S)")
    search_parser.add_argument("keyword", help="搜索关键词")

    # summary 命令
    summary_parser = subparsers.add_parser("summary", help="每日总结 (简写: -m)")
    summary_parser.add_argument("--date", help="指定日期 (YYYY-MM-DD)")
    summary_parser.add_argument("--continue", action="store_true", dest="continue_task",
                              help="将未完成任务延续到今天")

    # select 命令
    select_parser = subparsers.add_parser("select", help="交互式选择任务 (简写: -)")
    select_parser.add_argument("--status", choices=["todo", "in_progress", "done"],
                              help="按状态过滤")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 执行命令
    command_handlers = {
        "add": cmd_add,
        "list": cmd_list,
        "show": cmd_show,
        "edit": cmd_edit,
        "delete": cmd_delete,
        "search": cmd_search,
        "summary": cmd_summary,
        "select": cmd_select,
    }

    handler = command_handlers.get(args.command)
    if handler:
        try:
            handler(args)
        except Exception as e:
            print(colorize(f"错误: {e}", Colors.BRIGHT_RED), file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
