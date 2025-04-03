import datetime

from nonebot import logger
from utils.models import CurriculaConfig
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_apscheduler import scheduler
from utils.send import push_user_message, push_group_message

from .schema import CurriculaSchema


@scheduler.scheduled_job("cron", hour=0, minute=0)
async def daily_task():
    if datetime.datetime.today().weekday() == 0:
        logger.info("Update current week")
        await CurriculaConfig.filter().update(current_week=CurriculaConfig.current_week + 1)


@scheduler.scheduled_job("cron", hour=7, minute=0)
async def _():
    if not (configs := await CurriculaConfig.filter().all()):
        return

    for config in configs:
        if not config.is_notify:
            continue

        if config.user and (query := await CurriculaSchema.prase(config)):
            await push_user_message(config.user, UniMessage.image(raw=await query.render()))
        elif config.classes and (query := await CurriculaSchema.prase(config)):
            await push_group_message(
                config.classes.group,
                UniMessage.image(raw=await query.render()),
            )
