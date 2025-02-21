from nonebot import logger
from utils.models import User, Group
from nonebot.adapters import Bot, Event, ntchat, onebot
from nonebot_plugin_alconna import Target, UniMessage, SupportAdapter, get_bot


# 推送给用户消息
async def push_user_message(
    user: User, message: UniMessage, skip_after_first: bool = False
):
    """推送给用户所绑定的所有平台发送消息"""
    for bind in user.binds:
        adapter_name = SupportAdapter[bind.platform_id.split(".")[0]]
        for bot in await get_bot(adapter=adapter_name):
            try:
                await Target(bind.account_id, private=True).send(message, bot)
                if skip_after_first:
                    return
            except Exception as e:
                logger.exception(e)


async def push_group_message(
    group: Group, message: UniMessage, skip_after_first: bool = False
):
    """推送给群所绑定的所有平台发送消息"""
    for bind in group.group_binds:
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
    if isinstance(bot, onebot.v11.Bot) and isinstance(event, onebot.v11.Event):
        if isinstance(event, onebot.v11.GroupMessageEvent):
            await bot.upload_group_file(group_id=event.group_id, file=file, name=name)
            return True
        elif isinstance(event, onebot.v11.PrivateMessageEvent):
            await bot.upload_private_file(user_id=event.user_id, file=file, name=name)
            return True
    elif isinstance(bot, ntchat.Bot) and isinstance(event, ntchat.Event):
        await bot.send(event, ntchat.MessageSegment.file(file))
        return True
    return False
