from utils.session import SessionPlatform
from utils.models.models import User, Teacher
from nonebot_plugin_alconna import Target, AlconnaMatcher
from utils.models.depends import get_major, add_class_table

from .commands import (
    add_class_table_cmd,
    del_class_table_cmd,
    bind_class_table_cmd,
    show_class_table_cmd,
)


@add_class_table_cmd.handle()
async def _(
    matcher: AlconnaMatcher,
    name: str,
    major_name: str,
    teacher: Teacher,
    session: SessionPlatform,
    target: Target,
):
    print(target)
    if major := await get_major(major_name):
        ...
        # await add_class_table(name, teacher, major, session.id)
    await matcher.finish(f"[{major_name}]专业不存在")


@del_class_table_cmd.handle()
async def _(matcher: AlconnaMatcher, name: str):
    ...


@show_class_table_cmd.handle()
async def _(matcher: AlconnaMatcher):
    ...


@bind_class_table_cmd.handle()
async def _(matcher: AlconnaMatcher, name: str):
    ...
