from typing import Union

from nonebot.adapters.onebot import v11, v12


MessageEvent = Union[v11.MessageEvent, v12.MessageEvent]
GroupMessageEvent = Union[v11.GroupMessageEvent, v12.GroupMessageEvent]
PrivateMessageEvent = Union[v11.PrivateMessageEvent, v12.PrivateMessageEvent]
