from typing import NamedTuple

from nonebot.adapters import Bot as BaseBot
from nonebot.adapters.qq import Bot as QQBot
from nonebot.adapters import Event as BaseEvent
from nonebot.adapters.qq import Event as QQEvent


class Platform(NamedTuple):
    id: int
    bot: type[BaseBot]
    event: type[BaseEvent]


platforms: list[Platform] = [Platform(1, QQBot, QQEvent)]


def get_platform(bot: BaseBot, event: BaseEvent) -> Platform:
    """获取适配器相关平台"""
    for p in platforms:
        if isinstance(bot, p.bot) and isinstance(event, p.event):
            return p
    raise ValueError("platform not found")


def get_platform_id(bot: BaseBot, event: BaseEvent) -> int:
    return get_platform(bot, event).id
