"""
JSON 文件存储层
"""
import json
import os
from typing import List, Optional
from pathlib import Path
from .model import Task


class TaskStorage:
    """任务存储管理器"""

    def __init__(self, filepath: str = "tasks.json"):
        """
        初始化存储管理器

        Args:
            filepath: JSON 文件路径，默认为当前目录的 tasks.json
        """
        self.filepath = Path(filepath)
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """确保存储文件存在"""
        if not self.filepath.exists():
            self._save_tasks([])

    def _save_tasks(self, tasks: List[dict]):
        """保存任务列表到文件"""
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)

    def _load_tasks(self) -> List[dict]:
        """从文件加载任务列表"""
        with open(self.filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load(self) -> List[Task]:
        """加载所有任务"""
        try:
            tasks_data = self._load_tasks()
            return [Task.from_dict(data) for data in tasks_data]
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save(self, tasks: List[Task]):
        """保存所有任务"""
        tasks_data = [task.to_dict() for task in tasks]
        self._save_tasks(tasks_data)

    def backup(self) -> Optional[str]:
        """
        创建备份文件

        Returns:
            备份文件路径，失败返回 None
        """
        if not self.filepath.exists():
            return None

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.filepath.with_suffix(f".{timestamp}.bak")

        try:
            import shutil
            shutil.copy2(self.filepath, backup_path)
            return str(backup_path)
        except Exception:
            return None

    def get_backup_files(self) -> List[str]:
        """获取所有备份文件"""
        pattern = f"{self.filepath.stem}.*.bak"
        backups = sorted(
            self.filepath.parent.glob(f"{self.filepath.stem}.*.bak"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        return [str(b) for b in backups]
