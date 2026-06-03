from __future__ import annotations

# 导入统一命令 service，确保插件加载时完成 command_executor 注册。
from . import services as services
from .commands import chat_statistics_cmd, query_group_history_cmd

__all__ = ["query_group_history_cmd", "chat_statistics_cmd"]
