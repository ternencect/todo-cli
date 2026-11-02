"""Versioned, backwards-compatible task records and date handling."""
from dataclasses import dataclass, field, fields, asdict
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Optional, List
import re
import uuid


def now():
    return datetime.now().astimezone().isoformat()


def normalize_due(value):
    if value is None or value == '':
        return None
    if not isinstance(value, str):
        raise ValueError('截止日期必须是字符串')
    value = value.strip()
    if value in ('today', 'tomorrow'):
        return (date.today() + timedelta(days=value == 'tomorrow')).isoformat()
    if re.fullmatch(r'\+\d+d', value):
        return (date.today() + timedelta(days=int(value[1:-1]))).isoformat()
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            return date.fromisoformat(value).isoformat()
        return datetime.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError('日期格式应为 YYYY-MM-DD、ISO 时间、today、tomorrow 或 +3d')


class TaskStatus(str, Enum):
    TODO = 'todo'
    IN_PROGRESS = 'in_progress'
    BLOCKED = 'blocked'
    REVIEW = 'review'
    DONE = 'done'

    @classmethod
    def from_string(cls, value):
        aliases = {'doing': 'in_progress', 'completed': 'done', 'finished': 'done'}
        return cls(aliases.get(value.lower(), value.lower()))


class TaskPriority(str, Enum):
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'

    @classmethod
    def from_string(cls, value):
        aliases = {'h': 'high', 'm': 'medium', 'med': 'medium', 'l': 'low'}
        return cls(aliases.get(value.lower(), value.lower()))

    def rank(self):
        return {'high': 3, 'medium': 2, 'low': 1}[self.value]


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ''
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    tags: List[str] = field(default_factory=list)
    due_date: Optional[str] = None
    created_at: str = field(default_factory=now)
    completed_at: Optional[str] = None
    is_continued: bool = False
    updated_at: str = field(default_factory=now)
    branches: List[str] = field(default_factory=list)
    acceptance: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    owner: Optional[str] = None
    blocked_reason: Optional[str] = None
    result: Optional[str] = None
    next_step: Optional[str] = None
    links: List[str] = field(default_factory=list)
    notes: List[dict] = field(default_factory=list)
    history: List[dict] = field(default_factory=list)
    request_id: Optional[str] = None
    schema_version: int = 2

    def to_dict(self):
        data = asdict(self)
        data['status'] = self.status.value
        data['priority'] = self.priority.value
        return data

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError('任务记录必须是对象')
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError('不支持的任务字段: ' + ', '.join(sorted(unknown)))
        if data.get('schema_version', 1) not in (1, 2):
            raise ValueError('不支持的任务版本')
        values = dict(data)
        values['status'] = TaskStatus(data.get('status', 'todo'))
        values['priority'] = TaskPriority(data.get('priority', 'medium'))
        task = cls(**values)
        task.validate()
        return task

    def validate(self):
        if not isinstance(self.id, str) or not self.id or not isinstance(self.title, str) or not self.title.strip():
            raise ValueError('任务 ID 和标题不能为空')
        for name in ('tags', 'branches', 'acceptance', 'dependencies', 'links'):
            value = getattr(self, name)
            if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
                raise ValueError(name + ' 必须是非空字符串列表')
        for name in ('description', 'parent_id', 'owner', 'blocked_reason', 'result', 'next_step', 'request_id', 'completed_at'):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(name + ' 必须是字符串或 null')
        for name in ('notes', 'history'):
            value = getattr(self, name)
            if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
                raise ValueError(name + ' 必须是对象列表')
            required = ('at', 'actor', 'text') if name == 'notes' else ('at', 'actor', 'action')
            if any(any(not isinstance(item.get(key), str) for key in required) for item in value):
                raise ValueError(name + ' 缺少必要的时间、操作者或内容字段')
        for name in ('created_at', 'updated_at', 'completed_at'):
            value = getattr(self, name)
            if name == 'completed_at' and value is None:
                continue
            if not isinstance(value, str):
                raise ValueError(name + ' 必须是 ISO 时间字符串')
            datetime.fromisoformat(value)
        if self.due_date is not None:
            if not isinstance(self.due_date, str) or normalize_due(self.due_date) != self.due_date:
                raise ValueError('存储的截止日期必须是规范的 ISO 日期或时间')

    def mark_done(self):
        self.status = TaskStatus.DONE
        self.completed_at = now()

    def due_day(self):
        if not self.due_date:
            return None
        due = datetime.fromisoformat(self.due_date)
        if due.tzinfo:
            due = due.astimezone()
        return due.date()

    def is_overdue(self):
        if not self.due_date or self.status == TaskStatus.DONE:
            return False
        if len(self.due_date) == 10:
            return self.due_day() < date.today()
        due = datetime.fromisoformat(self.due_date)
        return datetime.now(due.tzinfo) > due

    def is_due_soon(self, days=1):
        return bool(self.due_date and self.status != TaskStatus.DONE and not self.is_overdue()
                    and 0 <= (self.due_day() - date.today()).days <= days)
