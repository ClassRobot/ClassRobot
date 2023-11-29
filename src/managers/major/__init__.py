from utils.models.models import User
from nonebot_plugin_alconna import AlconnaMatcher
from utils.formant import select_list, select_formant
from utils.params.notes import ValidateNameNotNumeric
from utils.models.depends import (
    add_major,
    get_major,
    get_college,
    delete_major,
    get_major_list,
)

from .commands import add_major_cmd, del_major_cmd, show_major_cmd


@add_major_cmd.handle()
async def _(
    matcher: AlconnaMatcher, major_name: str, college_name_or_id: int | str, user: User
):
    if college := await get_college(college_name_or_id):
        if await get_major(major_name):
            await matcher.finish(f"专业 {major_name} 已存在")
        else:
            await add_major(major_name, college, user)
            await matcher.finish(f"专业 {major_name} 添加成功")
    else:
        await matcher.finish(f"院系 {college_name_or_id} 不存在")


@show_major_cmd.handle()
async def _(matcher: AlconnaMatcher, college_name: str):
    if college := await get_college(college_name):
        if major := await get_major_list(college):
            await matcher.finish(
                select_list("存在的专业如下", (select_formant(m.id, m.major) for m in major))
            )
        await matcher.finish(f"[{college_name}]这个院系目前还没有添加过专业！")
    await matcher.finish(f"[{college_name}]这个院系不存在，使用`查询院系`命令看一下具体有哪些吧！")


@del_major_cmd.handle()
async def _(matcher: AlconnaMatcher, name: str):
    if await delete_major(name):
        await matcher.finish("删除成功！")
    await matcher.finish("没有这个专业哦！")
