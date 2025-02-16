import datetime

from nonebot import logger
from utils.models import CurriculumConfig
from nonebot_plugin_apscheduler import scheduler


@scheduler.scheduled_job("cron", hour=0, minute=0)
async def daily_task():
    if datetime.datetime.today().weekday() == 0:
        logger.info("Update current week")
        await CurriculumConfig.filter().update(
            current_week=CurriculumConfig.current_week + 1
        )
