from nonebot import logger
from utils.models import User, Group
from nonebot_plugin_alconna import Target, UniMessage, SupportAdapter, get_bot


# 推送给用户消息
async def push_user_message(user: User, message: UniMessage):
    """推送给用户所绑定的所有平台发送消息"""
    for bind in user.binds:
        adapter_name = SupportAdapter[bind.platform_id.split(".")[0]]
        for bot in await get_bot(adapter=adapter_name):
            try:
                await Target(bind.account_id, private=True).send(message, bot)
            except Exception as e:
                logger.exception(e)


async def push_group_message(group: Group, message: UniMessage):
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
            except Exception as e:
                logger.exception(e)
