from typing import Any

from nonebot.adapters import Message
from nonebot_plugin_alconna import UniMessage
from nonebot.params import Depends, CommandArg, EventMessage


def _command_arg_str(message: UniMessage = CommandArg()) -> str | None:
    """提取命令参数字符串。"""
    if text := message.extract_plain_text().strip():
        return text


def CommandArgStr() -> Any:
    """消息命令文本"""
    return Depends(_command_arg_str)


def ArgUniMessage(key: str):
    """构建统一消息参数依赖。"""

    async def _arg(msg: Message | UniMessage = EventMessage()) -> UniMessage:
        """构造命令参数解析依赖。"""
        if isinstance(msg, Message):
            return UniMessage.of(message=msg)
        return msg

    return Depends(_arg)
