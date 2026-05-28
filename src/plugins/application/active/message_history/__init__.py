from __future__ import annotations

from nonebot.adapters import Event
from src.platform.session import EventSession
from nonebot_plugin_alconna import AlconnaMatcher
from src.platform.session.resolvers import resolve_bound_group_id
from src.plugins.library.message_history.services import query_group_history, normalize_query_values

from . import services as _
from .commands import chat_statistics_cmd, query_group_history_cmd


@query_group_history_cmd.handle()
async def _(matcher: AlconnaMatcher, event: Event, platform: EventSession, query: tuple[str, ...] | list[str] = ()):
    """处理群聊记录检索命令。"""

    group_id = await resolve_bound_group_id(platform)
    if group_id is None:
        await matcher.finish("该命令只能在已绑定系统群组的群聊中使用。")

    text, _records = await query_group_history(
        group_id=str(group_id),
        query=normalize_query_values(query),
        exclude_message_id=str(getattr(event, "message_id", "") or "") or None,
    )
    await matcher.finish(text)


__all__ = ["query_group_history_cmd", "chat_statistics_cmd"]
