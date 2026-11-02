"""
todo_core - 任务管理核心模块
"""
from .model import Task, TaskStatus, TaskPriority
from .manager import TaskManager

__version__ = '2.0.0'

__all__ = ['Task', 'TaskStatus', 'TaskPriority', 'TaskManager', '__version__']
