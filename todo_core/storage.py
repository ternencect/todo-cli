"""Atomic JSON storage with a previous-good backup and optimistic concurrency."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from contextlib import contextmanager
from .model import Task


class ConflictError(RuntimeError):
    pass


class StorageError(RuntimeError):
    pass


@contextmanager
def file_lock(path):
    """Serialize cooperating writers; OS releases locks if a process exits."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b'\0')
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def atomic_write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class TaskStorage:
    def __init__(self, filepath='tasks.json'):
        self.filepath = Path(filepath)
        self._revision = None
        self._loaded = False

    def _read(self):
        try:
            return self.filepath.read_bytes()
        except FileNotFoundError:
            return None

    @staticmethod
    def _digest(raw):
        return hashlib.sha256(raw).hexdigest() if raw is not None else None

    def load(self):
        raw = self._read()
        try:
            data = json.loads(raw) if raw is not None else []
            if not isinstance(data, list):
                raise ValueError('顶层必须是任务数组')
            tasks = [Task.from_dict(item) for item in data]
            if len({task.id for task in tasks}) != len(tasks):
                raise ValueError('存在重复任务 ID')
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise StorageError('无法读取 {}: {}；原文件未修改，请检查或从 .bak 恢复'.format(self.filepath, exc)) from exc
        self._revision = self._digest(raw)
        self._loaded = True
        return tasks

    def save(self, tasks):
        for task in tasks:
            task.validate()
        payload = (json.dumps([t.to_dict() for t in tasks], ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        with file_lock(self.filepath.with_name(self.filepath.name + '.lock')):
            current = self._read()
            if not self._loaded or self._digest(current) != self._revision:
                raise ConflictError('任务已被其他进程修改，请重新读取后重试')
            if current is not None:
                atomic_write(self.filepath.with_name(self.filepath.name + '.bak'), current)
            atomic_write(self.filepath, payload)
            self._revision = self._digest(payload)

    def backup(self):
        with file_lock(self.filepath.with_name(self.filepath.name + '.lock')):
            raw = self._read()
            if raw is None:
                return None
            path = self.filepath.with_name(self.filepath.name + '.bak')
            atomic_write(path, raw)
            return str(path)

    def get_backup_files(self):
        return [str(p) for p in sorted(self.filepath.parent.glob(self.filepath.name + '*.bak'))]
