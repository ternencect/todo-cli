import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = str(Path(__file__).resolve().parents[1] / 'todo.py')


class CLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        self.env = dict(os.environ, TODO_CLI_HOME=str(self.base / 'data'), TODO_ACTOR='agent-a',
                        GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                        PYTHONDONTWRITEBYTECODE='1')
        self.git('init', '-q')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.test', '-c', 'commit.gpgsign=false',
                 'commit', '--allow-empty', '-qm', 'initial')

    def git(self, *args, cwd=None):
        return subprocess.run(['git', '-c', 'core.hooksPath=' + os.devnull] + list(args),
                              cwd=str(cwd or self.repo), env=self.env, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()

    def call(self, *args, cwd=None, code=0, stdin=None):
        result = subprocess.run([sys.executable, '-B', SCRIPT] + list(args) + ['--json'],
                                cwd=str(cwd or self.repo), env=self.env, input=stdin,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertFalse(result.stderr, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['ok'], code == 0)
        return data.get('data') if code == 0 else data['error']

    def test_complete_ai_workflow(self):
        self.call('init')
        a = self.call('add', '修复登录', '--acceptance', '回归通过', '--due', 'tomorrow')
        task_id = a['id'][:8]
        self.assertTrue(a['branches'])
        self.call('start', task_id)
        self.call('note', task_id, '定位完成', '--next-step', '补充回归测试')
        self.call('block', task_id, '缺少测试凭证')
        self.assertFalse(self.call('next'))
        self.call('start', task_id)
        self.call('done', task_id, code=2)
        self.call('review', task_id, '--result', 'unittest: passed')
        handoff = self.call('handoff', task_id)
        self.assertEqual(handoff['tasks'][0]['next_step'], '补充回归测试')
        self.call('done', task_id, '--result', '人工确认通过')
        self.assertEqual(self.call('list'), [])
        self.assertEqual(len(self.call('list', '--all')), 1)
        self.call('undo', task_id)
        self.assertIsNone(self.call('show', task_id)['completed_at'])
        self.assertGreater(len(self.call('history', task_id)), 5)

    def test_worktree_branch_and_subdirectory_share_tasks(self):
        original = self.call('add', 'shared')
        branch = original['branches'][0]
        worktree = self.base / 'linked'
        self.git('worktree', 'add', '-qb', 'feature', str(worktree))
        nested = worktree / 'nested'
        nested.mkdir()
        self.assertEqual(self.call('show', original['id'], cwd=nested)['id'], original['id'])
        self.assertEqual(self.call('context', cwd=nested)['root'], str(self.repo.resolve()))
        self.assertEqual(self.call('context', cwd=nested)['branch'], 'feature')
        self.assertEqual(self.call('list', '--current-branch', cwd=nested), [])
        self.call('start', original['id'], cwd=nested)
        self.assertEqual(len(self.call('list', '--current-branch', cwd=nested)), 1)
        self.assertEqual(self.call('show', original['id'])['branches'], [branch, 'feature'])
        self.assertEqual(len(self.call('projects')), 1)

    def test_independent_projects_and_global_view(self):
        first = self.call('add', 'first')
        other = self.base / 'other'
        other.mkdir()
        self.git('init', '-q', cwd=other)
        second = self.call('add', 'second', cwd=other)
        self.assertNotEqual(first['project_id'], second['project_id'])
        self.assertEqual(len(self.call('list')), 1)
        self.assertEqual(len(self.call('list', '--all-projects')), 2)
        self.assertEqual(self.call('list', '--project', second['project_id'])[0]['title'], 'second')

    def test_non_git_init_from_nested_directory(self):
        directory = self.base / 'plain'
        directory.mkdir()
        self.call('init', cwd=directory)
        task = self.call('add', 'plain', cwd=directory)
        child = directory / 'child'
        child.mkdir()
        self.assertEqual(self.call('show', task['id'], cwd=child)['id'], task['id'])
        self.assertEqual(len(self.call('inbox', cwd=child)), 1)
        self.call('list', '--current-branch', cwd=child, code=2)

    def test_explicit_legacy_file_and_migration(self):
        source = self.repo / 'tasks.json'
        legacy = {'id': 'legacy-id', 'title': 'old', 'priority': 'high', 'status': 'todo'}
        source.write_text(json.dumps([legacy]))
        self.assertEqual(self.call('--file', str(source), 'list')[0]['id'], 'legacy-id')
        self.assertEqual(self.call('list'), [])
        self.call('import', str(source))
        self.assertEqual(self.call('show', 'legacy-id')['title'], 'old')
        self.call('import', str(source), code=2)
        self.assertEqual(json.loads(source.read_text()), [legacy])

    def test_export_import_roundtrip(self):
        self.call('add', 'exported', '--acceptance', 'test')
        result = subprocess.run([sys.executable, '-B', SCRIPT, 'export', '--json'],
                                cwd=str(self.repo), env=self.env, stdout=subprocess.PIPE, text=True, check=True)
        destination = str(self.base / 'imported.json')
        self.call('--file', destination, 'import', '-', stdin=result.stdout)
        restored = self.call('--file', destination, 'list')
        self.assertEqual(restored[0]['title'], 'exported')
        self.assertEqual(restored[0]['acceptance'], ['test'])

    def test_json_errors_not_found_and_usage(self):
        self.assertEqual(self.call('show', 'missing', code=3)['code'], 'not_found')
        self.call('list', '--bad', code=2)
        self.call('list', '--limit', '0', code=2)
        self.call('select', code=2)
        self.call('add', '--input-json', '[]', code=2)
        self.call('add', '--input-json', '{"title":"x","unexpected":true}', code=2)
        self.call('add', '--input-json', '{"title":"x","priority":null}', code=2)
        self.call('add', '--input-json', '{broken', code=2)
        self.call('add', '--input-json', '{"title":"x","dependencies":3}', code=2)
        self.call('add', '--input-json', '{"title":"x","tags":""}', code=2)

    def test_json_input_retry_and_global_flags(self):
        body = json.dumps({'title': 'from agent', 'acceptance': ['test'], 'request_id': 'retry'})
        first = self.call('--json', 'add', '--input-json', '-', stdin=body)
        second = self.call('add', '--input-json', body)
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(len(self.call('--actor=agent-b', 'list')), 1)
        self.call('start', first['id'])
        self.call('--actor', 'agent-b', 'start', first['id'], code=2)
        self.call('--actor', 'agent-b', 'start', first['id'], '--force')

    def test_delete_never_prompts_agent(self):
        task = self.call('add', 'delete')
        self.call('delete', task['id'], code=2)
        self.assertEqual(len(self.call('list')), 1)
        self.call('delete', task['id'], '--yes')
        self.assertEqual(self.call('list'), [])

    def test_views_links_and_clear_fields(self):
        a = self.call('add', 'today', '--due', 'today', '--no-branch')
        self.assertEqual(len(self.call('today')), 1)
        self.call('postpone', a['id'], '+3d')
        self.assertEqual(self.call('today'), [])
        self.call('link', a['id'], '--branch', 'feature', '--url', 'commit:abc')
        self.assertEqual(len(self.call('list', '--branch', 'feature')), 1)
        self.call('edit', a['id'], '--clear-due', '--branches')
        self.assertEqual(len(self.call('inbox')), 1)
        self.assertEqual(len(self.call('search', 'commit:abc')), 1)
        self.call('summary', '--continue', '--yes')
        self.assertEqual(len(self.call('list')), 1)
        self.assertEqual(len(self.call('today')), 1)

    def test_handoff_markdown_and_branch_warning(self):
        task = self.call('add', 'handoff', '--branch', 'different', '--acceptance', 'pass')
        self.call('note', task['id'], 'progress', '--next-step', 'test it')
        data = self.call('handoff', task['id'])
        self.assertEqual(len(data['warnings']), 1)
        result = subprocess.run([sys.executable, '-B', SCRIPT, 'handoff', task['id']],
                                cwd=str(self.repo), env=self.env, stdout=subprocess.PIPE, text=True, check=True)
        for text in ('# 项目交接', '验收条件', 'progress', 'test it', task['id']):
            self.assertIn(text, result.stdout)

    def test_legacy_aliases(self):
        task = self.call('-a', 'alias')
        self.assertEqual(self.call('-s', task['id'])['title'], 'alias')
        self.assertEqual(len(self.call('-l')), 1)
        self.assertEqual(len(self.call('/', 'alias')), 1)
        self.call('-e', task['id'], '--title', 'edited')
        self.call('-d', task['id'], '-y')

    def test_corruption_is_machine_readable(self):
        file = self.base / 'broken.json'
        file.write_text('{broken')
        error = self.call('add', 'x', '--file', str(file), code=5)
        self.assertEqual(error['code'], 'storage_error')
        self.assertEqual(file.read_text(), '{broken')

    def test_readonly_calls_do_not_create_storage(self):
        self.call('list')
        self.call('context')
        self.call('projects')
        self.assertFalse((self.base / 'data').exists())

    def test_submodule_uses_its_own_root_and_identity(self):
        source = self.base / 'module-source'
        source.mkdir()
        self.git('init', '-q', cwd=source)
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.test', '-c', 'commit.gpgsign=false',
                 'commit', '--allow-empty', '-qm', 'module', cwd=source)
        self.git('-c', 'protocol.file.allow=always', 'submodule', 'add', '-q', str(source), 'module')
        module = self.repo / 'module'
        parent = self.call('context')
        child = self.call('context', cwd=module)
        self.assertEqual(child['root'], str(module.resolve()))
        self.assertNotEqual(child['id'], parent['id'])
        task = self.call('add', 'module task', cwd=module)
        linked = self.base / 'module-linked'
        self.git('worktree', 'add', '-qb', 'module-feature', str(linked), cwd=module)
        linked_context = self.call('context', cwd=linked)
        self.assertEqual(linked_context['id'], child['id'])
        self.assertEqual(linked_context['root'], child['root'])
        self.assertEqual(self.call('show', task['id'], cwd=linked)['title'], 'module task')

    def test_global_priority_sort_and_limit(self):
        self.call('add', 'low', '-p', 'low')
        other = self.base / 'other'
        other.mkdir()
        self.git('init', '-q', cwd=other)
        self.call('add', 'high', '-p', 'high', cwd=other)
        result = self.call('list', '--all-projects', '--sort', 'priority', '--limit', '1')
        self.assertEqual(result[0]['title'], 'high')
        result = self.call('next', '--all-projects', '--limit', '1')
        self.assertEqual(result[0]['title'], 'high')

    def test_detached_head_context(self):
        self.git('checkout', '--detach', '-q')
        ctx = self.call('context')
        self.assertTrue(ctx['branch'].startswith('detached:'))
        task = self.call('add', 'detached work')
        self.assertEqual(task['branches'], [ctx['branch']])

    def test_conflicting_global_options_and_invalid_edit(self):
        task = self.call('add', 'x')
        self.call('list', '--file', 'tasks.json', '--project', '.', code=2)
        self.call('list', '--all-projects', '--current-branch', code=2)
        self.call('edit', task['id'], '--due', 'today', '--clear-due', code=2)
        self.call('edit', task['id'], '--title', '', code=2)
        self.assertEqual(self.call('show', task['id'])['title'], 'x')

    def test_git_status_preserves_porcelain_columns(self):
        path = self.repo / 'tracked.txt'
        path.write_text('before')
        self.git('add', 'tracked.txt')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.test', '-c', 'commit.gpgsign=false',
                 'commit', '-qm', 'tracked')
        path.write_text('after')
        self.assertEqual(self.call('context')['git_status'], [' M tracked.txt'])


if __name__ == '__main__':
    unittest.main()
