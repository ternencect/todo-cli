"""Local project identity, shared by all branches and linked Git worktrees."""
from dataclasses import dataclass, asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
from .storage import atomic_write


def git(cwd, *args):
    try:
        result = subprocess.run(['git', '-C', str(cwd)] + list(args), stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, timeout=5)
        return result.stdout.rstrip('\r\n') if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def data_home():
    if os.environ.get('TODO_CLI_HOME'):
        return Path(os.environ['TODO_CLI_HOME']).expanduser().resolve()
    base = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share')))
    return base / 'todo-cli'


@dataclass
class Project:
    id: str
    name: str
    root: str
    branch: str
    storage: str
    worktree: str

    def to_dict(self):
        return asdict(self)


def discover(cwd=None):
    cwd = Path(cwd or Path.cwd()).resolve()
    top = git(cwd, 'rev-parse', '--show-toplevel')
    common = git(cwd, 'rev-parse', '--git-common-dir') if top else None
    if common:
        identity = (cwd / common).resolve()
        worktrees = git(cwd, 'worktree', 'list', '--porcelain') or ''
        first = next((line[9:] for line in worktrees.splitlines() if line.startswith('worktree ')), top)
        git_dir = git(cwd, 'rev-parse', '--git-dir')
        if git_dir and (cwd / git_dir).resolve() == identity:
            root = Path(top).resolve()
        else:
            # Submodules store their common directory under the parent repo's
            # .git/modules; Git can report that directory as the primary worktree.
            configured = git(cwd, 'config', '--get', 'core.worktree')
            root = (identity / configured).resolve() if configured else Path(first).resolve()
        branch = git(cwd, 'symbolic-ref', '--short', 'HEAD') or 'detached:' + (git(cwd, 'rev-parse', '--short', 'HEAD') or 'unknown')
    else:
        root = cwd
        # Explicit init markers let non-Git projects resolve from subdirectories.
        for candidate in (cwd,) + tuple(cwd.parents):
            marker = candidate / '.todo-project'
            if marker.is_file():
                root = candidate
                break
        identity = root
        branch = ''
    project_id = hashlib.sha256(str(identity).encode()).hexdigest()[:16]
    storage = data_home() / 'projects' / project_id / 'tasks.json'
    return Project(project_id, root.name, str(root), branch, str(storage), str(cwd))


def register(project):
    path = Path(project.storage).parent / 'project.json'
    # Stable metadata only: current branch/worktree belongs to the caller.
    payload = {'id': project.id, 'name': project.name, 'root': project.root, 'storage': project.storage}
    atomic_write(path, (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode())


def projects():
    result = []
    for path in sorted((data_home() / 'projects').glob('*/project.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            # Derive file path from registry location rather than trusting metadata.
            data['storage'] = str(path.parent / 'tasks.json')
            result.append(data)
        except (ValueError, OSError) as exc:
            raise ValueError('项目注册信息损坏: ' + str(path)) from exc
    return result
