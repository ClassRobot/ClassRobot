from __future__ import annotations

from nonebot import logger
from nonebot.adapters import Bot
from nonebot.matcher import Matcher
from nonebot_plugin_alconna import UniMessage
from src.core.skills import markdown_to_image_skill
from src.core.agent.runtime import markdown_to_message
from src.core.agent.runtime.formatting import preview_text


async def send_progress(matcher: Matcher, text: str) -> None:
    """发送 AutoGPT 阶段性进度反馈。"""

    logger.info(f'AutoGPT progress send queued text="{preview_text(text, limit=120)}"')
    await matcher.send(text)


async def send_markdown_reply(matcher: Matcher, bot: Bot, text: str) -> None:
    """发送 Markdown 回复，并在 wxclaw 导出失败时降级为纯文本。"""

    try:
        await matcher.send(await markdown_to_message(text).export(bot=bot))
    except Exception:
        if not is_wxclaw_bot(bot):
            raise
        logger.warning("AutoGPT wxclaw UniMessage 导出失败，已降级为纯文本发送。")
        await matcher.send(text)


async def send_long_markdown_reply(matcher: Matcher, bot: Bot, text: str) -> None:
    """发送较长 Markdown 回复，wxclaw 不支持时降级为纯文本。"""

    try:
        pic = UniMessage.image(raw=await markdown_to_image_skill.to_image(text)) + UniMessage.text(
            "文字太长已转为图片发送"
        )
        await matcher.send(await pic.export(bot=bot))
    except Exception:
        if not is_wxclaw_bot(bot):
            raise
        logger.warning("AutoGPT wxclaw 图片回复导出失败，已降级为纯文本发送。")
        await matcher.send(text)


def is_wxclaw_bot(bot: Bot) -> bool:
    """判断当前 Bot 是否来自 wxclaw adapter。"""

    adapter = getattr(bot, "adapter", None)
    get_name = getattr(adapter, "get_name", None)
    return callable(get_name) and str(get_name()).lower() == "wxclaw"
