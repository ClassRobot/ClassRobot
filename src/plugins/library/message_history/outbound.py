from __future__ import annotations

from typing import Any
from functools import wraps
from inspect import isawaitable

from nonebot import logger
from nonebot.adapters import Bot, Event
from src.platform.session.resolvers import resolve_session_from_event

from .collector import record_assistant_message

SEND_RECORDER_FLAG = "_classrobot_message_history_send_recorder"
ORIGINAL_SEND_ATTR = "_classrobot_message_history_original_send"


def install_outbound_message_recorder(bot: Bot | None = None) -> None:
    """安装全局机器人出站消息记录器。

    NoneBot 的具体适配器通常会覆盖基类 ``Bot.send``，因此这里只 patch
    基类是不够的，需要同时处理当前已经加载的 Bot 子类。nonebug 等测试
    环境也可能在实例上覆盖 ``send``，因此收到真实事件时还会补一次实例级
    patch。

    Args:
        bot: 可选的当前 Bot 实例。
    """

    for bot_class in iter_bot_classes(Bot):
        patch_bot_send(bot_class)
    if bot is not None:
        patch_bot_instance(bot)


def iter_bot_classes(root: type[Bot]) -> list[type[Bot]]:
    """递归列出当前进程中已经加载的 Bot 类。

    Args:
        root: Bot 基类。

    Returns:
        list[type[Bot]]: 包含基类和所有已加载子类的列表。
    """

    classes: list[type[Bot]] = []
    pending = [root]
    seen: set[type[Bot]] = set()
    while pending:
        bot_class = pending.pop()
        if bot_class in seen:
            continue
        seen.add(bot_class)
        classes.append(bot_class)
        pending.extend(bot_class.__subclasses__())
    return classes


def patch_bot_send(bot_class: type[Bot]) -> None:
    """为指定 Bot 类安装发送记录包装器。

    Args:
        bot_class: 需要 patch 的 Bot 类。
    """

    if bot_class is not Bot and "send" not in bot_class.__dict__:
        return
    if bot_class.__dict__.get(SEND_RECORDER_FLAG, False):
        return

    original_send = bot_class.send

    @wraps(original_send)
    async def send_with_history(self: Bot, event: Event, message: Any, **kwargs: Any) -> Any:
        result = original_send(self, event=event, message=message, **kwargs)
        if isawaitable(result):
            result = await result
        await _record_send_result(self, event, message, result, kwargs)
        return result

    setattr(bot_class, ORIGINAL_SEND_ATTR, original_send)
    bot_class.send = send_with_history
    setattr(bot_class, SEND_RECORDER_FLAG, True)


def patch_bot_instance(bot: Bot) -> None:
    """为实例级 ``send`` 覆盖安装记录包装器。

    Args:
        bot: 当前事件使用的 Bot 实例。
    """

    instance_dict = getattr(bot, "__dict__", {})
    if "send" not in instance_dict:
        return
    if getattr(bot, SEND_RECORDER_FLAG, False):
        return

    original_send = bot.send

    @wraps(original_send)
    async def send_with_history(event: Event, message: Any, **kwargs: Any) -> Any:
        result = original_send(event=event, message=message, **kwargs)
        if isawaitable(result):
            result = await result
        await _record_send_result(bot, event, message, result, kwargs)
        return result

    set_instance_attr(bot, ORIGINAL_SEND_ATTR, original_send)
    set_instance_attr(bot, "send", send_with_history)
    set_instance_attr(bot, SEND_RECORDER_FLAG, True)


def set_instance_attr(bot: Bot, name: str, value: Any) -> None:
    """设置 Bot 实例属性，并兼容限制普通赋值的适配器实现。

    Args:
        bot: 当前 Bot 实例。
        name: 属性名。
        value: 属性值。
    """

    try:
        setattr(bot, name, value)
    except Exception:
        object.__setattr__(bot, name, value)


async def _record_send_result(
    bot: Bot,
    event: Event,
    message: Any,
    result: Any,
    kwargs: dict[str, Any],
) -> None:
    """记录一次成功发出的机器人消息，失败只记日志不中断发送。"""

    try:
        platform = resolve_session_from_event(bot, event)
        if platform is None:
            return
        plain_text, raw_text = stringify_outbound_message(message)
        if not plain_text and not raw_text:
            return
        await record_assistant_message(
            platform,
            event,
            plain_text=plain_text or raw_text,
            raw_text=raw_text or plain_text,
            actor_id=str(getattr(bot, "self_id", "") or "bot"),
            actor_name="机器人",
            message_id=extract_sent_message_id(result),
            metadata={
                "source": "bot_send_hook",
                "send_result": compact_metadata(result),
                "send_kwargs": compact_metadata(kwargs),
            },
        )
    except Exception as error:
        logger.warning(f"Record outbound message failed: {error}")


def stringify_outbound_message(message: Any) -> tuple[str, str]:
    """把机器人出站消息转换为纯文本和原始文本。"""

    extract_plain_text = getattr(message, "extract_plain_text", None)
    plain_text = ""
    if callable(extract_plain_text):
        plain_text = str(extract_plain_text() or "").strip()
    elif isinstance(message, str):
        plain_text = message.strip()
    raw_text = str(message or "").strip()
    return plain_text, raw_text


def extract_sent_message_id(result: Any) -> str | None:
    """提取适配器发送结果中的消息 ID。"""

    if isinstance(result, dict):
        for key in ("message_id", "msg_id", "id"):
            value = result.get(key)
            if value not in (None, ""):
                return str(value)

    for key in ("message_id", "msg_id", "id"):
        value = getattr(result, key, None)
        if value not in (None, ""):
            return str(value)
    return None


def compact_metadata(value: Any) -> Any:
    """把发送结果压缩成适合 JSON 存储的简单结构。"""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): compact_metadata(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [compact_metadata(item) for item in value]
    return str(value)
