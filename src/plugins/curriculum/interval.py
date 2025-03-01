import datetime

from nonebot import logger
from utils.models import CurriculumConfig
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_apscheduler import scheduler
from utils.send import push_user_message, push_group_message

from .manager import QueryCurriculum


@scheduler.scheduled_job("cron", hour=0, minute=0)
async def daily_task():
    if datetime.datetime.today().weekday() == 0:
        logger.info("Update current week")
        await CurriculumConfig.filter().update(
            current_week=CurriculumConfig.current_week + 1
        )


@scheduler.scheduled_job("cron", hour=7, minute=0)
async def _():
    if not (configs := await CurriculumConfig.filter().all()):
        return

    for config in configs:
        if not config.is_notify:
            continue

        if config.user:
            query = QueryCurriculum(config.user)
            await push_user_message(
                config.user, UniMessage.image(raw=await query.render_pic())
            )
        elif config.classes and (cc := await config.classes.get_curriculum_config()):
            await push_group_message(
                config.classes.group,
                UniMessage.image(
                    raw=await QueryCurriculum.render_pic_by_curriculums(cc.curriculums)
                ),
            )
