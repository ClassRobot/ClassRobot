import json

from utils import Emoji
from utils.tools import StringCard
from nonebot_plugin_alconna import UniMessage, AlconnaMatcher

from .util import range_parser
from .commands import add_curriculum, del_curriculum, query_curriculum
from .depends import (
    DeleteCurriculum,
    AddCurriculumDepends,
    QueryCurriculumDepends,
    DeleteCurriculumDepends,
)


@add_curriculum.handle()
async def _(
    matcher: AlconnaMatcher, add_curriculum: AddCurriculumDepends, values: list[str]
):
    value_length = len(values)
    if value_length < 4:
        await matcher.finish("至少具备[周期] [星期几] [第几节课] [课程名称]四个参数,其次[教室(可选)] [老师(可选)]")
    if not (weeks := range_parser(values[0])):
        await matcher.finish("周期参数错误")
    if not (weekdays := range_parser(values[1])):
        await matcher.finish("星期参数错误")
    if not (lessons := range_parser(values[2])):
        await matcher.finish("课程节数参数错误")
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
