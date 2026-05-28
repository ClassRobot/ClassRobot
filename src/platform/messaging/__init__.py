from nonebot import logger
from src.models import User, Group
from nonebot.adapters import Bot, Event, onebot
from src.platform.bots.providers.wxclaw import WxClawBotProvider
from nonebot_plugin_alconna import Target, UniMessage, SupportScope, SupportAdapter, get_bot

WXCLAW_PRIVATE_PLATFORM = "wxclaw.private"


# 推送给用户消息
async def push_user_message(user: User, message: UniMessage, skip_after_first: bool = False):
    """推送给用户所绑定的所有平台发送消息"""
    for bind in user.binds:
        if bind.platform_id == WXCLAW_PRIVATE_PLATFORM:
            try:
                await push_wxclaw_private_message(bind.account_id, message)
                if skip_after_first:
                    return
            except Exception as e:
                logger.exception(e)
            continue

        adapter_name = SupportAdapter[bind.platform_id.split(".")[0]]
        scope_name = SupportScope[bind.platform_id.split(".")[1]]
        for bot in await get_bot(adapter=adapter_name):
            try:
                target = Target(bind.account_id, adapter=adapter_name, scope=scope_name, private=True)
                await target.send(message, bot)
                if skip_after_first:
                    return
            except Exception as e:
                logger.exception(e)


async def push_group_message(group: Group, message: UniMessage, skip_after_first: bool = False):
    """推送给群所绑定的所有平台发送消息"""
    for bind in await group.get_binds():
        if bind.platform_id.startswith("wxclaw."):
            logger.warning(f"wxclaw 暂不支持系统群组通知投递，已跳过 group_id={group.id}")
            continue

        adapter_name = SupportAdapter[bind.platform_id.split(".")[0]]
        for bot in await get_bot(adapter=adapter_name):
            try:
                await Target(
                    id=bind.channel_id,
                    channel=bool(bind.guild_id),
                    parent_id=bind.guild_id,
                ).send(message, bot)
                if skip_after_first:
                    return
            except Exception as e:
                logger.exception(e)


async def bot_upload_file(bot: Bot, event: Event, name: str, file: str) -> bool:
    """通过机器人上传文件。"""
    if isinstance(bot, onebot.v11.Bot) and isinstance(event, onebot.v11.Event):
        if isinstance(event, onebot.v11.GroupMessageEvent):
            await bot.upload_group_file(group_id=event.group_id, file=file, name=name)
            return True
        elif isinstance(event, onebot.v11.PrivateMessageEvent):
            await bot.upload_private_file(user_id=event.user_id, file=file, name=name)
            return True
        return True
    return False


async def push_wxclaw_private_message(account_id: str, message: UniMessage) -> None:
    """使用 wxclaw 原生能力向微信私聊用户发送文本消息。

    Args:
        account_id: wxclaw 平台用户 ID，对应 `UserBind.account_id`。
        message: 需要发送的统一消息。v1 只保证文本投递。

    Raises:
        RuntimeError: 当前没有可用 wxclaw bot。
    """

    provider = WxClawBotProvider()
    bot = provider.select_bot_for_user(account_id)
    if bot is None:
        raise RuntimeError("当前没有在线 wxclaw bot，无法发送微信私聊通知")

    text = _message_to_text(message)
    if not text:
        raise RuntimeError("wxclaw v1 只支持文本通知，当前消息没有可投递文本")
    await bot.send_text(account_id, text)


def _message_to_text(message: UniMessage) -> str:
    """把 `UniMessage` 转成 wxclaw v1 可发送的文本。"""

    try:
        text = message.extract_plain_text()
    except Exception:
        text = ""
    return text.strip() or str(message).strip()
