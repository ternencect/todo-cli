import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import types
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from todo_core import Task, TaskManager, TaskStatus
from todo_core.model import normalize_due
from todo_core.storage import TaskStorage, StorageError, ConflictError
from todo_core.tui import fit, curses_wrapper


def competing_writer(path, barrier, results, title):
    manager = TaskManager(TaskStorage(path))
    barrier.wait(timeout=10)
    try:
        manager.add(title)
        results.put('ok')
    except ConflictError:
        results.put('conflict')


class Workflows(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'tasks.json'
        self.manager = TaskManager(TaskStorage(self.path), actor='agent-a')

    def fresh(self, actor='agent-a'):
        return TaskManager(TaskStorage(self.path), actor=actor)

    def test_claim_handoff_review_and_completion(self):
        task = self.manager.add('修复登录', acceptance=['回归测试通过'], branches=['fix/login'])
        self.manager.edit(task.id[:8], status='in_progress')
        self.manager.note(task.id, '已定位原因', next_step='添加回归测试')
        self.manager.edit(task.id, status='review', result='pytest: 12 passed', links=['commit:abc'])
        handoff = self.fresh().handoff(task.id)
        self.assertEqual(handoff['tasks'][0]['next_step'], '添加回归测试')
        self.assertEqual(handoff['tasks'][0]['notes'][0]['actor'], 'agent-a')
        self.manager.edit(task.id, status='done')
        self.assertTrue(self.fresh().require(task.id).completed_at)
        self.manager.edit(task.id, status='todo')
        reopened = self.fresh().require(task.id)
        self.assertIsNone(reopened.owner)
        self.assertIsNone(reopened.completed_at)
        self.assertIsNone(reopened.result)
        with self.assertRaisesRegex(ValueError, 'result'):
            self.manager.edit(task.id, status='done')

    def test_owner_conflict_and_explicit_takeover_are_audited(self):
        task = self.manager.add('owned')
        self.manager.edit(task.id, status='in_progress')
        other = self.fresh('agent-b')
        with self.assertRaisesRegex(ValueError, '认领'):
            other.edit(task.id, status='in_progress')
        other.edit(task.id, status='in_progress', force=True)
        task = self.fresh().require(task.id)
        self.assertEqual(task.owner, 'agent-b')
        self.assertTrue(task.history[-1]['forced'])

    def test_dependency_and_parent_completion_gates(self):
        parent = self.manager.add('parent')
        child = self.manager.add('child', parent_id=parent.id)
        followup = self.manager.add('followup', dependencies=[parent.id[:8]])
        self.assertEqual([t.id for t in self.manager.next_tasks()], [child.id])
        with self.assertRaisesRegex(ValueError, '前置'):
            self.manager.edit(parent.id, status='done')
        with self.assertRaisesRegex(ValueError, '前置'):
            self.manager.edit(followup.id, status='in_progress')
        self.manager.edit(child.id, status='done')
        self.manager.edit(parent.id, status='done')
        self.assertEqual([t.id for t in self.manager.next_tasks()], [followup.id])

    def test_cycles_and_dangling_references_do_not_modify_disk(self):
        a = self.manager.add('a')
        b = self.manager.add('b', dependencies=[a.id])
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, '循环'):
            self.manager.edit(a.id, dependencies=[b.id])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.manager.require(a.id).dependencies, [])
        with self.assertRaises(ValueError):
            self.manager.add('missing', dependencies=['missing'])
        with self.assertRaisesRegex(ValueError, '关联'):
            self.manager.delete(a.id)

    def test_parent_can_explicitly_depend_on_child(self):
        parent = self.manager.add('parent')
        child = self.manager.add('child', parent_id=parent.id)
        self.manager.edit(parent.id, dependencies=[child.id])
        with self.assertRaisesRegex(ValueError, '循环'):
            self.manager.edit(child.id, dependencies=[parent.id])

    def test_prefix_ambiguity_rejected(self):
        records = [Task(id='abcd1111', title='a').to_dict(), Task(id='abcd2222', title='b').to_dict()]
        self.manager.import_tasks(records)
        with self.assertRaisesRegex(ValueError, '歧义'):
            self.manager.get('abcd')
        self.assertEqual(self.manager.get('abcd1111').title, 'a')
        self.assertIsNone(self.manager.get('abc'))

    def test_idempotency_survives_edits(self):
        task = self.manager.add('a', request_id='request-1')
        self.manager.edit(task.id, title='renamed')
        retried = self.manager.add('a', request_id='request-1')
        self.assertEqual(retried.id, task.id)
        self.assertEqual(len(self.manager.tasks), 1)
        with self.assertRaisesRegex(ValueError, 'request-id'):
            self.manager.add('different', request_id='request-1')

    def test_old_records_load_and_reschedule_without_duplicates(self):
        legacy = {'id': 'old-task', 'title': 'legacy', 'status': 'todo', 'priority': 'medium',
                  'created_at': '2026-01-01T12:00:00', 'due_date': '2026-01-02'}
        self.path.write_text(json.dumps([legacy]))
        manager = self.fresh()
        manager.continue_task('old-task', 'tomorrow')
        self.assertEqual(len(manager.tasks), 1)
        self.assertEqual(self.fresh().require('old-task').due_date, normalize_due('tomorrow'))

    def test_date_only_not_overdue_on_due_day(self):
        task = self.manager.add('today', due_date='today')
        self.assertFalse(task.is_overdue())
        self.assertTrue(task.is_due_soon())
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        late = self.manager.add('late', due_date=yesterday)
        self.assertTrue(late.is_overdue())
        self.assertFalse(late.is_due_soon())
        past = (datetime.now().astimezone() - timedelta(seconds=5)).isoformat()
        timed = self.manager.add('timed', due_date=past)
        self.assertTrue(timed.is_overdue())
        self.assertEqual(normalize_due('+3d'), (date.today() + timedelta(days=3)).isoformat())
        with self.assertRaises(ValueError):
            self.manager.add('bad', due_date='2026-02-30')

    def test_ready_today_and_blocked_views(self):
        task = self.manager.add('work', due_date='today')
        self.manager.block(task.id, '等待接口')
        self.assertEqual(self.manager.next_tasks(), [])
        self.assertEqual(len(self.manager.today()), 1)
        self.manager.edit(task.id, status='todo')
        self.assertIsNone(self.fresh().require(task.id).blocked_reason)
        self.assertEqual(len(self.manager.next_tasks()), 1)

    def test_corrupt_storage_is_never_silently_overwritten(self):
        for content in ('{broken', '{}', '[{"title": "x", "due_date": 12}]',
                        '[{"title":"x", "unknown":true}]'):
            self.path.write_text(content)
            with self.assertRaises(StorageError):
                self.fresh()
            self.assertEqual(self.path.read_text(), content)

    def test_future_version_and_duplicate_ids_rejected(self):
        self.path.write_text(json.dumps([{'title': 'x', 'schema_version': 999}]))
        with self.assertRaises(StorageError):
            self.fresh()
        record = Task(title='a').to_dict()
        self.path.write_text(json.dumps([record, record]))
        with self.assertRaises(StorageError):
            self.fresh()

    def test_stale_writer_cannot_overwrite(self):
        stale = self.fresh()
        self.manager.add('first')
        with self.assertRaises(ConflictError):
            stale.add('lost update')
        self.assertEqual(stale.tasks, [])
        self.assertEqual([t.title for t in self.fresh().tasks], ['first'])

    def test_real_process_writers_detect_conflict(self):
        ctx = multiprocessing.get_context('spawn')
        barrier, queue = ctx.Barrier(2), ctx.Queue()
        processes = [ctx.Process(target=competing_writer, args=(str(self.path), barrier, queue, str(i))) for i in range(2)]
        try:
            for process in processes:
                process.start()
            results = sorted(queue.get(timeout=20) for _ in processes)
            self.assertEqual(results, ['conflict', 'ok'])
            self.assertEqual(len(self.fresh().tasks), 1)
        finally:
            for process in processes:
                process.join(timeout=5)
                if process.is_alive():
                    process.terminate()
                    process.join()
            queue.close()

    def test_failed_replace_preserves_original(self):
        self.manager.add('first')
        before = self.path.read_bytes()
        real_replace = os.replace
        def fail_target(source, target):
            if Path(target) == self.path:
                raise OSError('simulated disk failure')
            return real_replace(source, target)
        with patch('todo_core.storage.os.replace', side_effect=fail_target):
            with self.assertRaises(OSError):
                self.manager.add('second')
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.path.with_name('tasks.json.bak').read_bytes(), before)
        self.assertFalse(list(self.path.parent.glob('.tasks.json.*')))

    def test_import_is_all_or_nothing(self):
        original = self.manager.add('existing')
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.manager.import_tasks([Task(title='new').to_dict(), original.to_dict()])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(len(self.manager.tasks), 1)
        with self.assertRaises(ValueError):
            self.manager.import_tasks([Task(title='bad', dependencies=['missing']).to_dict()])
        self.assertEqual(self.path.read_bytes(), before)

    def test_batch_reschedule_ownership_failure_is_atomic(self):
        a = self.manager.add('a')
        b = self.manager.add('b')
        self.manager.edit(b.id, status='in_progress')
        other = self.fresh('agent-b')
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            other.reschedule([a.id, b.id], 'tomorrow')
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIsNone(other.require(a.id).due_date)

    def test_invalid_inputs_are_rejected(self):
        for kwargs in ({'title': ' '}, {'title': 'a', 'tags': ''}, {'title': 'a', 'priority': 'unknown'},
                       {'title': 'a', 'dependencies': [12]}, {'title': 'a', 'acceptance': ['']}):
            with self.assertRaises(ValueError):
                self.manager.add(**kwargs)
        self.assertFalse(self.path.exists())

    def test_unicode_picker_width(self):
        self.assertEqual(fit('中文abc', 5), '中文a')
        self.assertEqual(fit('a\nb', 2), 'a ')

    def test_picker_scrolls_to_items_beyond_screen(self):
        fake = types.SimpleNamespace(curs_set=lambda _: None, error=RuntimeError,
                                     A_BOLD=1, A_REVERSE=2, KEY_UP=1000, KEY_DOWN=1001,
                                     KEY_NPAGE=1002, KEY_PPAGE=1003, KEY_ENTER=1004)
        class Screen:
            def __init__(self):
                self.keys = iter([fake.KEY_DOWN] * 9 + [10])
                self.lines = []
            def keypad(self, value):
                pass
            def getmaxyx(self):
                return 6, 30
            def erase(self):
                self.lines = []
            def addstr(self, row, col, text, attr):
                self.lines.append(text)
            def refresh(self):
                pass
            def getch(self):
                return next(self.keys)
        screen = Screen()
        with patch.dict('sys.modules', curses=fake):
            selected = curses_wrapper(screen, [Task(title='任务' + str(i)) for i in range(10)], '选择')
        self.assertEqual(selected, 9)
        self.assertTrue(any('10. 任务9' in line for line in screen.lines))

    def test_corrupt_history_is_rejected(self):
        for field in ('notes', 'history'):
            task = Task(title='x').to_dict()
            task[field] = [{}]
            self.path.write_text(json.dumps([task]))
            with self.assertRaises(StorageError):
                self.fresh()


if __name__ == '__main__':
    unittest.main()
