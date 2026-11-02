"""Small, scrollable curses picker with a numeric fallback."""
from typing import Optional, List
import unicodedata


def fit(text, columns):
    output, used = [], 0
    for char in text.replace('\n', ' ').replace('\r', ' '):
        width = 0 if unicodedata.combining(char) else 2 if unicodedata.east_asian_width(char) in 'WF' else 1
        if used + width > columns:
            break
        output.append(char)
        used += width
    return ''.join(output)


def select_menu(tasks: List, prompt='请选择任务:') -> Optional[int]:
    if not tasks:
        print('没有可用的任务')
        return None
    while True:
        print('\n' + prompt)
        for i, task in enumerate(tasks, 1):
            print('  {}. {}'.format(i, task.title))
        try:
            choice = input('\n输入编号 (0 取消): ').strip()
            if choice == '0':
                return None
            index = int(choice) - 1
            if 0 <= index < len(tasks):
                return index
            print('无效的编号，请重试')
        except ValueError:
            print('请输入数字')
        except (KeyboardInterrupt, EOFError):
            return None


def curses_wrapper(stdscr, tasks, title):
    import curses
    if not tasks:
        return None
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.keypad(True)
    current = 0
    while True:
        height, width = stdscr.getmaxyx()
        stdscr.erase()
        def draw(row, text, attr=0):
            if 0 <= row < height and width > 1:
                try:
                    stdscr.addstr(row, 0, fit(text, width - 1), attr)
                except curses.error:
                    pass
        draw(0, title, curses.A_BOLD)
        visible = max(1, height - 3)
        start = max(0, current - visible + 1)
        for row, index in enumerate(range(start, min(start + visible, len(tasks))), 1):
            draw(row, '{} {}. {}'.format('>' if index == current else ' ', index + 1, tasks[index].title),
                 curses.A_REVERSE if index == current else 0)
        draw(height - 1, '↑↓/jk 移动 | Enter 选择 | q 取消 ({}/{})'.format(current + 1, len(tasks)))
        stdscr.refresh()
        key = stdscr.getch()
        if key in (curses.KEY_UP, ord('k')):
            current = max(0, current - 1)
        elif key in (curses.KEY_DOWN, ord('j')):
            current = min(len(tasks) - 1, current + 1)
        elif key == curses.KEY_NPAGE:
            current = min(len(tasks) - 1, current + visible)
        elif key == curses.KEY_PPAGE:
            current = max(0, current - visible)
        elif key in (10, 13, curses.KEY_ENTER):
            return current
        elif key in (ord('q'), ord('Q'), 27):
            return None


def select_task_curses(tasks: List, title='选择任务') -> Optional[int]:
    if not tasks:
        return None
    try:
        import curses
        return curses.wrapper(curses_wrapper, tasks, title)
    except (ImportError, OSError):
        return select_menu(tasks, title)
    except Exception as exc:
        # Some terminals provide curses but cannot initialize a screen.
        import curses
        if isinstance(exc, curses.error):
            return select_menu(tasks, title)
        raise


__all__ = ['select_task_curses', 'select_menu']
