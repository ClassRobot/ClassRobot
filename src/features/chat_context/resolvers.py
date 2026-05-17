from __future__ import annotations

import re
from uuid import uuid4

from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna import SerializeFailed, SupportAdapter, SupportScope, get_target

from utils.models import Group, GroupBind, User, UserBind
from utils.session import BaseSession

ALCONNA_TARGET_FALLBACK_ERRORS = (SerializeFailed, NotImplementedError, ValueError)
"""alconna target 解析允许兜底的异常类型。

`SerializeFailed` 代表当前适配器没有 uniseg target 支持；`ValueError`
通常来自未知 scope/adapter 枚举；`NotImplementedError` 表示事件本身不
提供标准消息上下文。其他异常应交给调用方处理，避免把真实 bug 当成兼容
问题吞掉。
"""


async def resolve_bound_group_id(platform: BaseSession) -> int | None:
    """把平台群会话解析成系统内 `Group.id`。"""

    if not platform.is_group or platform.channel_id is None:
        return None

    if group := await GroupBind.get_group(platform.platform, platform.channel_id, platform.guild_id):
        return group.id
    return None


async def resolve_or_create_bound_group(platform: BaseSession, event: Event) -> Group | None:
    """把平台群会话解析成系统群组；若不存在则自动创建绑定。"""

    if not platform.is_group or platform.channel_id is None:
        return None

    if group := await GroupBind.get_group(platform.platform, platform.channel_id, platform.guild_id):
        return group

    creator = await _resolve_or_create_bound_user(platform, event)
    group = await Group.create_group(_resolve_group_name(platform, event), creator)
    await GroupBind.bind_group(platform.platform_name, platform.platform, platform.channel_id, platform.guild_id, group)
    return group


async def resolve_or_create_private_user(platform: BaseSession, event: Event) -> User:
    """把私聊会话解析成系统内 `User`，必要时自动创建。"""

    return await _resolve_or_create_bound_user(platform, event)


async def _resolve_or_create_bound_user(platform: BaseSession, event: Event) -> User:
    """把平台用户解析成系统用户；若不存在则自动创建并绑定。"""

    if user := await UserBind.get_user(platform.platform, platform.user_id):
        return user

    nickname = _resolve_sender_name(event).strip() or "user"
    user = await User.create_user(
        nickname=nickname,
        username=uuid4().hex[:16],
    )
    await UserBind.bind_user(platform.platform, platform.user_id, user)
    return user


async def resolve_private_user(platform: BaseSession) -> User | None:
    """解析私聊会话对应的已存在系统用户。

    Args:
        platform: 当前平台会话。

    Returns:
        User | None: 已绑定用户；未绑定时返回 ``None``。
    """

    return await UserBind.get_user(platform.platform, platform.user_id)


def resolve_session_from_event(bot: Bot, event: Event) -> BaseSession | None:
    """从发送事件恢复与 `EventSession` 一致的会话标识。"""

    try:
        target = get_target(event, bot)
        if target.scope and target.adapter:
            scope = SupportScope(target.scope)
            adapter = SupportAdapter(target.adapter)
            return BaseSession(
                user_id=event.get_user_id(),
                platform=".".join((adapter.name, scope.name)),
                platform_name=".".join(target.platform or []),
                guild_id=target.parent_id,
                channel_id=target.id if not target.private else None,
            )
    except ALCONNA_TARGET_FALLBACK_ERRORS:
        pass

    platform = _fallback_platform(bot)
    channel_id = _fallback_channel_id(event)
    return BaseSession(
        user_id=event.get_user_id(),
        platform=platform,
        platform_name="",
        channel_id=channel_id,
        guild_id=_normalize_optional(getattr(event, "guild_id", None)),
    )


def _resolve_sender_name(event: Event) -> str:
    """提取事件发送者名称，用于兜底创建私聊用户。"""

    sender = getattr(event, "sender", None)
    if sender is not None:
        for field in ("card", "nickname", "nick", "name", "display_name"):
            value = getattr(sender, field, None)
            if value:
                return _normalize_text(value)

    for field in ("nickname", "nick", "name", "display_name"):
        value = getattr(event, field, None)
        if value:
            return _normalize_text(value)
    return event.get_user_id()


def _resolve_group_name(platform: BaseSession, event: Event) -> str:
    """推断自动创建系统群组时使用的展示名称。"""

    for field in ("group_name", "channel_name", "guild_name", "name", "title"):
        value = getattr(event, field, None)
        if value:
            return _normalize_text(value)

    platform_name = _normalize_text(platform.platform_name)
    if platform_name and platform.channel_id:
        if platform.guild_id:
            return f"{platform_name} {platform.guild_id}/{platform.channel_id}"
        return f"{platform_name} {platform.channel_id}"

    if platform.guild_id and platform.channel_id:
        return f"group_{platform.guild_id}_{platform.channel_id}"
    if platform.channel_id:
        return f"group_{platform.channel_id}"
    return "group"


def _normalize_text(value: object) -> str:
    """清理昵称中的空白，避免生成脏数据。"""

    return re.sub(r"\s+", " ", str(value)).strip()


def _fallback_platform(bot: Bot) -> str:
    """在无法使用 alconna target 时生成保守平台标识。"""

    adapter = getattr(bot, "adapter", None)
    adapter_name = "unknown"
    get_name = getattr(adapter, "get_name", None)
    if callable(get_name):
        adapter_name = str(get_name()).lower()
    elif adapter is not None:
        adapter_name = adapter.__class__.__name__.lower()

    if adapter_name == "onebot v11":
        adapter_name = "onebot11"
    return f"{adapter_name}.qq_client"


def _fallback_channel_id(event: Event) -> str | None:
    """从常见事件字段中提取频道或群组 ID。"""

    for field in ("group_id", "channel_id"):
        value = getattr(event, field, None)
        if value not in (None, ""):
            return str(value)
    return None


def _normalize_optional(value: object) -> str | None:
    """把可选平台标识转换为字符串。"""

    if value in (None, ""):
        return None
    return str(value)
