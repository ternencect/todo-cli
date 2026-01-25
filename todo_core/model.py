"""
任务数据模型定义
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List
import uuid


class TaskStatus(str, Enum):
    """任务状态枚举"""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"

    @classmethod
    def from_string(cls, value: str) -> 'TaskStatus':
        """从字符串创建状态枚举"""
        value_map = {
            "todo": cls.TODO,
            "doing": cls.IN_PROGRESS,
            "in_progress": cls.IN_PROGRESS,
            "done": cls.DONE,
            "completed": cls.DONE,
            "finished": cls.DONE,
        }
        return value_map.get(value.lower(), cls.TODO)


class TaskPriority(str, Enum):
    """任务优先级枚举"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def from_string(cls, value: str) -> 'TaskPriority':
        """从字符串创建优先级枚举"""
        value_map = {
            "high": cls.HIGH,
            "h": cls.HIGH,
            "medium": cls.MEDIUM,
            "med": cls.MEDIUM,
            "m": cls.MEDIUM,
            "low": cls.LOW,
            "l": cls.LOW,
        }
        return value_map.get(value.lower(), cls.MEDIUM)

    def rank(self) -> int:
        """返回优先级排序值（值越大优先级越高）"""
        return {self.HIGH: 3, self.MEDIUM: 2, self.LOW: 1}[self]


@dataclass
class Task:
    """任务数据模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    tags: List[str] = field(default_factory=list)
    due_date: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    is_continued: bool = False

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "tags": self.tags,
            "due_date": self.due_date,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "is_continued": self.is_continued,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        """从字典创建任务"""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", ""),
            description=data.get("description"),
            status=TaskStatus(data.get("status", TaskStatus.TODO.value)),
            priority=TaskPriority(data.get("priority", TaskPriority.MEDIUM.value)),
            tags=data.get("tags", []),
            due_date=data.get("due_date"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at"),
            is_continued=data.get("is_continued", False),
        )

    def mark_done(self):
        """标记任务为完成"""
        self.status = TaskStatus.DONE
        self.completed_at = datetime.now().isoformat()

    def is_overdue(self) -> bool:
        """检查任务是否已过期"""
        if not self.due_date or self.status == TaskStatus.DONE:
            return False
        try:
            due = datetime.fromisoformat(self.due_date)
            return datetime.now() > due
        except (ValueError, TypeError):
            return False

    def is_due_soon(self, days: int = 1) -> bool:
        """检查任务是否即将到期（指定天数内）"""
        if not self.due_date or self.status == TaskStatus.DONE:
            return False
        try:
            due = datetime.fromisoformat(self.due_date)
            delta = (due - datetime.now()).days
            return 0 <= delta <= days
        except (ValueError, TypeError):
            return False
