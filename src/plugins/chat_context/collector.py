from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Iterable

from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna import SerializeFailed, UniMessage
from pydantic import BaseModel, Extra

from utils.session import BaseSession
from utils.storage import MessageActorRole, chat_history_store, normalize_message_text, normalize_raw_message

from .resolvers import (
    resolve_or_create_bound_group,
    resolve_or_create_private_user,
    resolve_private_user,
)

ALCONNA_TEXT_FALLBACK_ERRORS = (SerializeFailed, NotImplementedError, ValueError)
"""alconna 文本解析允许兜底的异常类型。

这些异常表示当前适配器、事件或消息结构无法被 `UniMessage` 正常序列化。
其他异常通常意味着代码错误或依赖行为变化，需要直接暴露出来，避免静默
降级后掩盖真实问题。
"""


class MessageTextSource(str, Enum):
    """描述消息文本解析所使用的来源。"""

    alconna = "alconna"
    event_fallback = "event_fallback"


class MessageTextPayload(BaseModel):
    """描述一条消息经过解析后的文本内容。"""

    plain_text: str
    raw_text: str
    source: MessageTextSource
    fallback_reason: str = ""

    @property
    def has_content(self) -> bool:
        """判断当前解析结果是否包含可落库内容。"""

        return bool(self.plain_text or self.raw_text)

    class Config:
        """定义消息文本模型的运行约束。"""

        extra = Extra.forbid
        allow_mutation = False


def resolve_sender_name(event: Event) -> str:
    """提取事件发送者名称。"""

    sender = getattr(event, "sender", None)
    if sender is not None:
        for field in ("card", "nickname", "nick", "name", "display_name"):
            value = getattr(sender, field, None)
            if value:
                return normalize_message_text(value)

    for field in ("nickname", "nick", "name", "display_name"):
        value = getattr(event, field, None)
        if value:
            return normalize_message_text(value)

    return event.get_user_id()


def extract_message_text(event: Event, bot: Bot | None = None) -> MessageTextPayload:
    """提取事件中的纯文本和原始文本。

    优先使用 `nonebot-plugin-alconna` 的 `UniMessage` 做跨平台消息解析。
    只有当 alconna 明确不支持或无法从事件中取得标准消息时，才回退到
    原生 Event 字段，避免把未知异常盲目当成兼容性问题。

    Args:
        event: 当前 NoneBot 事件。
        bot: 当前 Bot 实例，用于 alconna 识别适配器。

    Returns:
        MessageTextPayload: 归一化后的消息文本。
    """

    try:
        return extract_alconna_message_text(event, bot)
    except ALCONNA_TEXT_FALLBACK_ERRORS as error:
        return extract_event_message_text(event, fallback_reason=error.__class__.__name__)


def extract_alconna_message_text(event: Event, bot: Bot | None = None) -> MessageTextPayload:
    """使用 alconna 统一消息模型提取文本。

    Args:
        event: 当前 NoneBot 事件。
        bot: 当前 Bot 实例。

    Returns:
        MessageTextPayload: alconna 解析后的消息文本。

    Raises:
        SerializeFailed: 当前适配器缺少 uniseg 支持时抛出。
        NotImplementedError: 当前事件没有标准消息实现时抛出。
        ValueError: 当前事件无法提供消息对象时抛出。
    """

    message = event.get_message()
    uni_message = UniMessage.of(message, bot=bot)
    plain_text = normalize_message_text(uni_message.extract_plain_text())
    raw_text = normalize_raw_message(str(uni_message))
    if not raw_text:
        raw_text = normalize_raw_message(str(message))
    if not plain_text:
        plain_text = raw_text
    return MessageTextPayload(
        plain_text=plain_text,
        raw_text=raw_text,
        source=MessageTextSource.alconna,
    )


def extract_event_message_text(event: Event, *, fallback_reason: str = "") -> MessageTextPayload:
    """使用原生 Event 字段提取文本，作为 alconna 不兼容时的兜底。

    Args:
        event: 当前 NoneBot 事件。
        fallback_reason: 触发兜底的原因。

    Returns:
        MessageTextPayload: 原生事件解析后的消息文本。
    """

    plain_text = ""
    get_plaintext = getattr(event, "get_plaintext", None)
    if callable(get_plaintext):
        plain_text = normalize_message_text(get_plaintext())

    raw_text = normalize_raw_message(getattr(event, "raw_message", ""))
    if not raw_text:
        get_message = getattr(event, "get_message", None)
        if callable(get_message):
            raw_text = normalize_raw_message(str(get_message()))

    if not plain_text:
        plain_text = raw_text
    return MessageTextPayload(
        plain_text=plain_text,
        raw_text=raw_text,
        source=MessageTextSource.event_fallback,
        fallback_reason=fallback_reason,
    )


def resolve_created_at(event: Event) -> datetime:
    """解析事件时间。"""

    value = getattr(event, "time", None)
    if isinstance(value, int | float):
        try:
            # 某些适配器或测试场景会把 message_id 复用到 time 字段，
            # 这类值不一定是有效 Unix 时间戳，因此需要兜底回退到当前时间。
            if value >= 946684800:
                return datetime.fromtimestamp(value)
        except (OverflowError, OSError, ValueError):
            pass
    return datetime.now()


def build_event_metadata(event: Event, source: str) -> dict[str, Any]:
    """构造消息归档使用的事件扩展元数据。

    Args:
        event: 当前 NoneBot 事件。
        source: 记录来源标识。

    Returns:
        dict[str, Any]: 可 JSON 序列化的事件基础信息。
    """

    metadata: dict[str, Any] = {
        "source": source,
        "event_class": event.__class__.__name__,
    }
    for field in ("post_type", "message_type", "sub_type", "notice_type", "request_type"):
        value = getattr(event, field, None)
        if value not in (None, ""):
            metadata[field] = str(value)
    return metadata


async def collect_message(platform: BaseSession, event: Event, bot: Bot | None = None) -> None:
    """按系统归属记录当前平台消息。"""

    message_text = extract_message_text(event, bot)
    if not message_text.has_content:
        return

    metadata = build_event_metadata(event, "event_collector")
    metadata["message_source"] = message_text.source.value
    if message_text.fallback_reason:
        metadata["message_fallback_reason"] = message_text.fallback_reason
    if platform.is_group:
        group = await resolve_or_create_bound_group(platform, event)
        if group is None:
            return

        await chat_history_store.record_group_collect_message(
            group_id=group.id,
            message_id=getattr(event, "message_id", None),
            user_id=platform.user_id,
            user_name=resolve_sender_name(event),
            plain_text=message_text.plain_text,
            raw_text=message_text.raw_text,
            created_at=resolve_created_at(event),
            platform=platform.platform,
            platform_name=platform.platform_name,
            channel_id=platform.channel_id,
            guild_id=platform.guild_id,
            bot_id=resolve_bot_id(bot),
            platform_user_id=platform.user_id,
            metadata=metadata,
        )
        return

    user = await resolve_or_create_private_user(platform, event)
    await chat_history_store.record_user_chat_message(
        user_id=user.id,
        user_name=user.nickname,
        message_id=getattr(event, "message_id", None),
        plain_text=message_text.plain_text,
        raw_text=message_text.raw_text,
        created_at=resolve_created_at(event),
        platform=platform.platform,
        platform_name=platform.platform_name,
        channel_id=platform.channel_id,
        guild_id=platform.guild_id,
        bot_id=resolve_bot_id(bot),
        platform_user_id=platform.user_id,
        metadata=metadata,
    )


async def record_command_message(
    platform: BaseSession,
    event: Event,
    bot: Bot | None = None,
    *,
    command_name: str,
    command_aliases: Iterable[str] = (),
    plugin_module: str | None = None,
) -> None:
    """按聊天消息记录一次用户显式命令输入。

    该函数用于命令 matcher 自身的前置记录 hook。普通群消息仍由
    `collect_message` 写入 `collect`，而用户显式命令需要额外写入
    `chat`，这样后台和 Agent 才能看到完整的“用户命令 -> 机器人回复”
    会话链。

    Args:
        platform: 当前平台会话。
        event: 当前 NoneBot 事件。
        bot: 当前 Bot 实例。
        command_name: 命中的项目主命令名。
        command_aliases: 命令别名集合，用于审计。
        plugin_module: 命令所属插件模块。
    """

    message_text = extract_message_text(event, bot)
    if not message_text.has_content:
        return

    metadata = build_event_metadata(event, "command_input_hook")
    metadata.update(
        {
            "command_name": command_name,
            "command_aliases": sorted(str(alias) for alias in command_aliases),
            "command_plugin_module": plugin_module or "",
            "message_source": message_text.source.value,
        }
    )
    if message_text.fallback_reason:
        metadata["message_fallback_reason"] = message_text.fallback_reason

    if platform.is_group:
        group = await resolve_or_create_bound_group(platform, event)
        if group is None:
            return

        await chat_history_store.record_group_chat_message(
            group_id=group.id,
            plain_text=message_text.plain_text,
            raw_text=message_text.raw_text,
            actor_role=MessageActorRole.user,
            actor_id=platform.user_id,
            actor_name=resolve_sender_name(event),
            message_id=getattr(event, "message_id", None),
            created_at=resolve_created_at(event),
            platform=platform.platform,
            platform_name=platform.platform_name,
            channel_id=platform.channel_id,
            guild_id=platform.guild_id,
            bot_id=resolve_bot_id(bot),
            platform_user_id=platform.user_id,
            metadata=metadata,
        )
        return

    user = await resolve_or_create_private_user(platform, event)
    await chat_history_store.record_user_chat_message(
        user_id=user.id,
        user_name=user.nickname,
        message_id=getattr(event, "message_id", None),
        plain_text=message_text.plain_text,
        raw_text=message_text.raw_text,
        created_at=resolve_created_at(event),
        platform=platform.platform,
        platform_name=platform.platform_name,
        channel_id=platform.channel_id,
        guild_id=platform.guild_id,
        bot_id=resolve_bot_id(bot),
        platform_user_id=platform.user_id,
        metadata=metadata,
    )


async def record_assistant_message(
    platform: BaseSession,
    event: Event,
    *,
    plain_text: str,
    raw_text: str = "",
    actor_id: str | int | None = None,
    actor_name: str | None = None,
    message_id: str | int | None = None,
    created_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """按系统归属记录机器人向用户发送的回复。"""

    normalized_plain_text = normalize_message_text(plain_text)
    normalized_raw_text = normalize_raw_message(raw_text or plain_text)
    if not normalized_plain_text and not normalized_raw_text:
        return

    assistant_id = str(actor_id or f"{platform.platform}:assistant")
    assistant_name = normalize_message_text(actor_name) or "机器人"
    created_at = created_at or datetime.now()
    record_metadata = {
        **build_event_metadata(event, "bot_send"),
        "target_platform_user_id": platform.user_id,
        "target_channel_id": platform.channel_id,
        "target_guild_id": platform.guild_id,
        **(metadata or {}),
    }

    if platform.is_group:
        group = await resolve_or_create_bound_group(platform, event)
        if group is None:
            return

        await chat_history_store.record_group_chat_message(
            group_id=group.id,
            plain_text=normalized_plain_text or normalized_raw_text,
            raw_text=normalized_raw_text,
            actor_role=MessageActorRole.assistant,
            actor_id=assistant_id,
            actor_name=assistant_name,
            message_id=message_id,
            created_at=created_at,
            platform=platform.platform,
            platform_name=platform.platform_name,
            channel_id=platform.channel_id,
            guild_id=platform.guild_id,
            bot_id=assistant_id,
            platform_user_id=assistant_id,
            metadata=record_metadata,
        )
        return

    user = await resolve_private_user(platform)
    if user is None:
        return
    await chat_history_store.record_user_chat_message(
        user_id=user.id,
        user_name=user.nickname,
        plain_text=normalized_plain_text or normalized_raw_text,
        raw_text=normalized_raw_text,
        actor_role=MessageActorRole.assistant,
        actor_id=assistant_id,
        actor_name=assistant_name,
        message_id=message_id,
        created_at=created_at,
        platform=platform.platform,
        platform_name=platform.platform_name,
        channel_id=platform.channel_id,
        guild_id=platform.guild_id,
        bot_id=assistant_id,
        platform_user_id=assistant_id,
        metadata=record_metadata,
    )


def resolve_bot_id(bot: Bot | None) -> str:
    """提取机器人自身 ID。"""

    if bot is None:
        return ""
    return str(getattr(bot, "self_id", "") or "")
