from typing import TypeAlias

from nonebot.adapters.onebot import v11
from nonebot.adapters.qq import AtMessageCreateEvent, DirectMessageCreateEvent

GroupMessageEvent: TypeAlias = AtMessageCreateEvent | v11.GroupMessageEvent
PrivateMessageEvent: TypeAlias = DirectMessageCreateEvent | v11.PrivateMessageEvent
