from __future__ import annotations

# 导入统一命令 service，确保插件加载时完成 command_executor 注册。
from . import services as services
from .commands import query_todo_cmd, create_todo_cmd, delete_todo_cmd, complete_todo_cmd

__all__ = [
    "create_todo_cmd",
    "query_todo_cmd",
    "complete_todo_cmd",
    "delete_todo_cmd",
]
