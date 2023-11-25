from utils.models.models import User
from nonebot_plugin_alconna import AlconnaMatcher
from utils.formant import select_list, select_formant
from utils.models.depends import (
    add_college,
    get_college,
    delete_college,
    get_college_list,
)

from .commands import add_college_cmd, del_college_cmd, show_college_cmd


@add_college_cmd.handle()
async def handle(matcher: AlconnaMatcher, name: str, user: User):
    name = name.strip()
    if college := await get_college(name):
        await matcher.finish(f"院系 {college.college} 已存在")
    else:
        await add_college(name, user)
        await matcher.finish(f"院系 {name} 添加成功")


@show_college_cmd.handle()
async def _(matcher: AlconnaMatcher):
    if colleges := await get_college_list():
        await matcher.finish(
            select_list(
                "存在的学院如下",
                (select_formant(college.id, college.college) for college in colleges),
            )
        )
    else:
        await matcher.finish("还没有添加过院系呢！")


@del_college_cmd.handle()
async def _(matcher: AlconnaMatcher, name: str):
    name = name.strip()
    if 0 < await delete_college(int(name) if name.isdigit() else name):
        await matcher.finish("删除成功！")
    await matcher.finish("没有这个院系哦！")
