"""消息历史归档能力库。

本包只提供可复用采集、查询和展示能力，不注册 matcher、命令或启动钩子。
NoneBot 入口分别位于：

- `src.plugins.application.passive.message_history_collector`
- `src.plugins.application.active.message_history`
"""

from .outbound import install_outbound_message_recorder
from .collector import collect_message, record_command_message
from .services import query_group_history, normalize_query_values

__all__ = [
    "collect_message",
    "record_command_message",
    "install_outbound_message_recorder",
    "normalize_query_values",
    "query_group_history",
]
