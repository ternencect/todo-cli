"""
TUI 交互界面 - 使用 curses 实现任务选择
"""
import sys
from typing import Optional, List, Callable


def select_menu(tasks: List, prompt: str = "请选择任务:") -> Optional[int]:
    """
    简单的数字菜单选择（回退方案）

    Args:
        tasks: 任务列表
        prompt: 提示文本

    Returns:
        选中的任务索引，取消返回 None
    """
    if not tasks:
        print("没有可用的任务")
        return None

    while True:
        print(f"\n{prompt}")
        for i, task in enumerate(tasks, 1):
            print(f"  {i}. {task.title[:50]}")

        try:
            choice = input("\n输入编号 (0 取消): ").strip()
            if choice == "0":
                return None

            index = int(choice) - 1
            if 0 <= index < len(tasks):
                return index
            else:
                print("无效的编号，请重试")
        except (ValueError, KeyboardInterrupt):
            print("\n已取消")
            return None


def curses_wrapper(stdscr, tasks, title: str):
    """curses 包装器"""
    import curses

    # 初始化
    curses.curs_set(0)  # 隐藏光标
    stdscr.nodelay(0)  # 阻塞模式

    # 颜色对
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)

    max_y, max_x = stdscr.getmaxyx()
    current_row = 0

    # 显示的起始位置
    start_col = 2
    start_row = 2

    while True:
        stdscr.clear()
        stdscr.addstr(0, start_col, title, curses.color_pair(1) | curses.A_BOLD)

        # 显示任务列表
        visible_count = max_y - start_row - 2
        for i, task in enumerate(tasks):
            if i >= visible_count:
                break

            prefix = "> " if i == current_row else "  "
            line = f"{prefix}{i + 1}. {task.title[:max_x - 10]}"

            if i == current_row:
                stdscr.addstr(start_row + i, start_col, line, curses.color_pair(2))
            else:
                stdscr.addstr(start_row + i, start_col, line)

        # 底部提示
        help_text = "↑↓: 移动 | Enter: 选择 | q: 取消"
        stdscr.addstr(max_y - 1, 2, help_text, curses.A_DIM)

        stdscr.refresh()

        # 处理输入
        key = stdscr.getch()
        if key == curses.KEY_UP and current_row > 0:
            current_row -= 1
        elif key == curses.KEY_DOWN and current_row < len(tasks) - 1:
            current_row += 1
        elif key == ord('\n') or key == ord('\r'):
            return current_row
        elif key == ord('q') or key == ord('Q') or key == 27:  # q, Q, ESC
            return None


def select_task_curses(tasks: List, title: str = "选择任务") -> Optional[int]:
    """
    使用 curses 实现任务选择界面

    Args:
        tasks: 任务列表
        title: 标题

    Returns:
        选中的任务索引，取消返回 None
    """
    try:
        import curses
        return curses.wrapper(curses_wrapper, tasks, title)
    except ImportError:
        # Windows 需要 windows-curses
        return select_menu(tasks, title)
    except Exception:
        # curses 不可用，回退到菜单
        return select_menu(tasks, title)


# 导出函数
__all__ = ['select_task_curses', 'select_menu']
