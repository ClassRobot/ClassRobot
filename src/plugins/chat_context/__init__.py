from __future__ import annotations

from nonebot import on_message
from nonebot.matcher import Matcher
from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna import AlconnaMatcher

from utils.config import priority
from utils.commands import CommandSpec, register_command_input_recorder
from utils.session import EventSession

from .commands import query_group_history_cmd
from .collector import collect_message, record_command_message
from .outbound import install_outbound_message_recorder
from .resolvers import resolve_bound_group_id, resolve_session_from_event
from .services import normalize_query_values, query_group_history
from . import services as _

install_outbound_message_recorder()


async def record_command_input_for_chat_context(bot: Bot, event: Event, spec: CommandSpec) -> None:
    """把显式命令输入写入聊天上下文。

    Args:
        bot: 当前 Bot 实例。
        event: 当前命令事件。
        spec: 命令元数据，用于记录命令名、别名和所属插件模块。
    """

    install_outbound_message_recorder(bot)
    platform = resolve_session_from_event(bot, event)
    if platform is None:
        return

    await record_command_message(
        platform,
        event,
        bot,
        command_name=spec.name,
        command_aliases=spec.aliases,
        plugin_module=spec.plugin_module,
    )


register_command_input_recorder("chat_context", record_command_input_for_chat_context)

message_history_collector = on_message(priority=max(1, priority - 1), block=False)


@message_history_collector.handle()
async def _(bot: Bot, event: Event, platform: EventSession):
    """采集系统群环境消息和私聊聊天消息。"""

    install_outbound_message_recorder(bot)
    if event.get_user_id() == str(bot.self_id):
        return
    await collect_message(platform, event, bot)


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


__all__ = ["message_history_collector", "query_group_history_cmd"]
