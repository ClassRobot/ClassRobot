from __future__ import annotations

from nonebot import on_message
from nonebot.adapters import Bot, Event
from src.platform.config import priority
from src.platform.session import EventSession
from src.platform.session.resolvers import resolve_session_from_event
from src.platform.commands import CommandSpec, register_command_input_recorder
from src.plugins.library.message_history.outbound import install_outbound_message_recorder
from src.plugins.library.message_history.collector import collect_message, record_command_message

install_outbound_message_recorder()


async def record_command_input_for_message_history(bot: Bot, event: Event, spec: CommandSpec) -> None:
    """把显式命令输入写入聊天历史。"""

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


register_command_input_recorder("message_history", record_command_input_for_message_history)

message_history_collector = on_message(priority=max(1, priority - 1), block=False)


@message_history_collector.handle()
async def _(bot: Bot, event: Event, platform: EventSession):
    """采集系统群环境消息和私聊聊天消息。"""

    install_outbound_message_recorder(bot)
    if event.get_user_id() == str(bot.self_id):
        return
    await collect_message(platform, event, bot)


__all__ = ["message_history_collector"]
