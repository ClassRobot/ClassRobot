from typing import Any

from nonebot_plugin_alconna import UniMessage
from nonebot.params import Depends, CommandArg


def _command_arg_str(message: UniMessage = CommandArg()) -> str | None:
    if text := message.extract_plain_text().strip():
        return text


def CommandArgStr() -> Any:
    """消息命令文本"""
    return Depends(_command_arg_str)
