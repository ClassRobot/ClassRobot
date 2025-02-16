import json
from uuid import uuid4

from utils import Emoji, cache
from utils.tools import StringCard
from nonebot_plugin_alconna import UniMessage, AlconnaMatcher

from .util import range_parser
from . import interval as interval  # noqa
from .commands import (
    set_week_cmd,
    add_curriculum,
    del_curriculum,
    query_curriculum,
    share_curriculum,
)
from .depends import (
    AddCurriculumDepends,
    QueryCurriculumDepends,
    ShareCurriculumDepends,
    DeleteCurriculumDepends,
    SetCurriculumWeekDepends,
)


@add_curriculum.handle()
async def _(
    matcher: AlconnaMatcher, add_curriculum: AddCurriculumDepends, values: list[str]
):
    value_length = len(values)
    if value_length < 4:
        await matcher.finish(
            Emoji.error + "至少具备[周期] [星期几] [第几节课] [课程名称]四个参数,其次[教室(可选)] [老师(可选)]"
        )
    if not (weeks := range_parser(values[0])):
        await matcher.finish(Emoji.error + "周期参数错误")
    if not (weekdays := range_parser(values[1])):
        # 范围应该在1-7之间
        if min(weekdays) < 1 or max(weekdays) > 7:
            await matcher.finish(Emoji.error + "星期参数错误,范围应该在1-7之间")
        await matcher.finish(Emoji.error + "星期参数错误")
    if not (lessons := range_parser(values[2])):
        await matcher.finish(Emoji.error + "课程节数参数错误")
    course_name = values[3]

    classroom = values[4] if value_length > 4 else None
    teacher = values[5] if value_length > 5 else None

    curriculum = await add_curriculum.add(
        weeks, weekdays, lessons, course_name, classroom, teacher
    )

    await matcher.finish(
        Emoji.success + f"[{curriculum.id}: {curriculum.course}]添加成功\n"
    )


@query_curriculum.handle()
async def _(matcher: AlconnaMatcher, query_curriculum: QueryCurriculumDepends):
    # await matcher.finish(await query_curriculum.render())
    await matcher.finish(UniMessage.image(raw=await query_curriculum.render_pic()))


@del_curriculum.handle()
async def _(
    matcher: AlconnaMatcher,
    values: list[int],
    delete_curriculum: DeleteCurriculumDepends,
):
    # 拿到无法删除的id
    ids = await delete_curriculum.delete(values)

    if ids:
        await matcher.finish(
            Emoji.error + f"以下由于不是您创建的课程无法删除: {', '.join(str(i) for i in ids)}"
        )
    await matcher.finish(Emoji.success + "删除成功")


@set_week_cmd.handle()
async def _(
    matcher: AlconnaMatcher,
    set_week_cmd: SetCurriculumWeekDepends,
    week: int,
    classes_id: int | None = None,
):
    if await set_week_cmd.set_week(week, classes_id):
        await matcher.finish(Emoji.success + f"设置成功,当前周为第{week}周")
    await matcher.finish(Emoji.error + "设置失败,可能并不是您创建的课表")


@share_curriculum.handle()
async def _(
    matcher: AlconnaMatcher,
    share_curriculum: ShareCurriculumDepends,
    share_id: str | None,
):
    # 如果有share_id则分享指定课表,如果没有则生成自己的share_id,缓存时间为5分钟
    if share_id is None:
        share_id = uuid4().hex.replace("-", "")
        if user_config := await share_curriculum.get_config():
            await cache.set(share_id, str(user_config.id), ex=180)
        else:
            await matcher.finish(Emoji.error + "您没有自己的课表可以分享")
        await matcher.finish(
            Emoji.success + f"您的课表分享ID为: {share_id}\n对方输入: `分享课表+ID`即可获取,有效期为3分钟"
        )
    elif config_id := await cache.get(share_id):
        config_id = int(config_id)
        result = await share_curriculum.share(config_id)
        if result:
            await matcher.finish(Emoji.success + "获取成功")
        elif result is False:
            await matcher.finish(Emoji.error + "获取失败,您已经拥有该课表")
        else:
            await matcher.finish(Emoji.error + "获取失败,课表不存在")
    else:
        await matcher.finish(Emoji.error + "获取失败,分享ID不存在或已过期")
