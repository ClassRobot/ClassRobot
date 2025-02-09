import itertools
from typing import TypeVar, Callable

from strenum import StrEnum
from nonebot.adapters import Bot, Event
from nonebot.adapters.ntchat import Bot as NtBot
from nonebot.adapters.ntchat import Event as NtEvent
from nonebot.adapters.onebot.v11 import Bot as V11Bot
from nonebot.adapters.onebot.v11 import Event as V11Event
from nonebot.adapters.ntchat import MessageSegment as NtMessageSegment
from nonebot.adapters.onebot.v11 import GroupMessageEvent as V11GroupMessageEvent
from nonebot.adapters.onebot.v11 import PrivateMessageEvent as V11PrivateMessageEvent

T = TypeVar("T")
special_characters = ("\\", "/", ":", "*", "?", '"', "<", ">", "|")


def validate_name(name: str) -> str | None:
    name = name.strip()
    if name.isdigit():
        return None
    for c in special_characters:
        if c in name:
            return None
    return name


ValidateName = lambda name: validate_name(name)


class Emoji(StrEnum):
    win = "🎉"
    "庆祝"
    error = "❌"
    "错误"
    success = "✅"
    "成功"
    warning = "⚠️"
    "警告"
    info = "ℹ️"
    "信息"
    question = "❓"
    "问题"
    loading = "⏳"
    "加载"
    bulb = "💡"
    "灯泡"

    def __call__(self, *msg: str, sep: str = "") -> str:
        return self + sep + sep.join(msg)


def tip(msg: T) -> Callable[..., T]:
    return lambda *_: msg


def alias_product(*args: list[str]):
    """别名组成
    ```python
    alias(["创建", "添加"], ["任务", "作业])
    ```
    ```
    {"创建任务", "添加任务", "创建作业", "添加作业" }
    ```
    """
    return {"".join(i) for i in itertools.product(*args)}


async def bot_upload_file(bot: Bot, event: Event, name: str, file: str):
    if isinstance(bot, V11Bot) and isinstance(event, V11Event):
        if isinstance(event, V11GroupMessageEvent):
            await bot.upload_group_file(group_id=event.group_id, file=file, name=name)
            return True
        elif isinstance(event, V11PrivateMessageEvent):
            await bot.upload_private_file(user_id=event.user_id, file=file, name=name)
            return True
    elif isinstance(bot, NtBot) and isinstance(event, NtEvent):
        await bot.send(event, NtMessageSegment.file(file))
        return True
    return False
