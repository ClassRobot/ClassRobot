from typing import Any

from nonebot.adapters import Message
from nonebot_plugin_alconna import UniMessage
from nonebot.params import Arg, Depends, CommandArg, EventMessage


def _command_arg_str(message: UniMessage = CommandArg()) -> str | None:
    if text := message.extract_plain_text().strip():
        return text


def CommandArgStr() -> Any:
    """消息命令文本"""
    return Depends(_command_arg_str)


def ArgUniMessage(key: str):
    async def _arg(msg: Message | UniMessage = EventMessage()) -> UniMessage:
        print([i for i in msg])
        if isinstance(msg, Message):
            return await UniMessage.generate(message=msg)
        return msg

    return Depends(_arg)
