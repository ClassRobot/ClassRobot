from __future__ import annotations

from collections.abc import Callable, Awaitable

from nonebot import logger
from nonebot.adapters import Bot, Event

from .spec import CommandSpec

CommandInputRecorder = Callable[[Bot, Event, CommandSpec], Awaitable[None]]
"""命令输入记录器类型。

记录器由具体业务插件注册，例如聊天上下文插件可以把用户显式命令写入
聊天记录。命令封装层只负责派发，不依赖任何具体 `src` 插件。
"""

_command_input_recorders: dict[str, CommandInputRecorder] = {}


def register_command_input_recorder(name: str, recorder: CommandInputRecorder) -> None:
    """注册命令输入记录器。

    同名记录器会覆盖旧值，避免插件热重载或测试重复导入时出现重复写入。

    Args:
        name: 记录器名称，建议使用业务模块名或插件名。
        recorder: 异步记录函数，接收当前 Bot、Event 与命令元数据。
    """

    _command_input_recorders[name] = recorder


def unregister_command_input_recorder(name: str) -> None:
    """注销命令输入记录器。

    Args:
        name: 需要注销的记录器名称。
    """

    _command_input_recorders.pop(name, None)


def clear_command_input_recorders() -> None:
    """清空所有命令输入记录器。

    该函数主要用于测试隔离，业务代码通常不需要调用。
    """

    _command_input_recorders.clear()


async def dispatch_command_input_recorders(bot: Bot, event: Event, spec: CommandSpec) -> None:
    """派发命令输入记录事件。

    单个记录器失败不会中断命令执行，也不会影响其他记录器继续工作。

    Args:
        bot: 当前 Bot 实例。
        event: 当前事件。
        spec: 当前命令元数据。
    """

    for name, recorder in tuple(_command_input_recorders.items()):
        try:
            await recorder(bot, event, spec)
        except Exception as error:
            logger.warning(f"命令输入记录器 `{name}` 执行失败：{error}")
