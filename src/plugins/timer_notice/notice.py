from nonebot_plugin_apscheduler import scheduler
from nonebot import get_bot
from nonebot.adapters.onebot.v11 import Bot, MessageSegment, Message
import datetime


@scheduler.scheduled_job("cron", hour="20", minute="0")
async def daily_notice():
    bot: Bot = get_bot()    # type: ignore
    await bot.send_group_msg(group_id=123456789, message=Message(
        MessageSegment.at("")
    ))
