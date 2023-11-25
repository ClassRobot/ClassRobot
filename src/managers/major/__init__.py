from utils.models.models import User
from nonebot_plugin_alconna import AlconnaMatcher
from utils.formant import select_list, select_formant
from utils.models.depends import (
    add_major,
    get_major,
    get_college,
    delete_major,
    get_major_list,
)

from .commands import add_major_cmd, del_major_cmd, show_major_cmd


@add_major_cmd.handle()
async def _(matcher: AlconnaMatcher, name: str, college_name: str, user: User):
    if college := await get_college(college_name):
        if await get_major(name):
            await matcher.finish(f"专业 {name} 已存在")
        else:
            await add_major(name, college, user)
            await matcher.finish(f"专业 {name} 添加成功")
    else:
        await matcher.finish(f"院系 {college_name} 不存在")


@show_major_cmd.handle()
async def _(matcher: AlconnaMatcher, college_name: str):
    if college := await get_college(college_name):
        if major := await get_major_list(college):
            await matcher.finish(
                select_list("存在的专业如下", (select_formant(m.id, m.major) for m in major))
            )
        else:
            await matcher.finish("没有这个学院吧！")
    await matcher.finish("没有这个学院吧！")


@del_major_cmd.handle()
async def _(matcher: AlconnaMatcher, name: str):
    if await delete_major(name):
        await matcher.finish("删除成功！")
    await matcher.finish("没有这个专业哦！")
