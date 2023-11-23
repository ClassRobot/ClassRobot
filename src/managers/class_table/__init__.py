from utils.params import GroupId
from utils.session import SessionPlatform
from utils.models.models import User, Teacher
from nonebot_plugin_alconna import AlconnaMatcher
from nonebot_plugin_alconna.uniseg import Target, MsgTarget, MessageTarget
from utils.models.depends import (
    get_major,
    add_class_table,
    get_class_table,
    delete_class_table,
    add_bind_class_table,
    get_class_table_list,
)

from .commands import (
    add_class_table_cmd,
    del_class_table_cmd,
    bind_class_table_cmd,
    show_class_table_cmd,
)


@add_class_table_cmd.handle()
async def _(
    name: str,
    major_name: str,
    teacher: Teacher,
    matcher: AlconnaMatcher,
    session: SessionPlatform,
    group_id: str = GroupId,
):
    if (major := await get_major(major_name)) is None:  # 获取专业
        await matcher.finish(f"[{major_name}]专业不存在")
    elif None is not await get_class_table(name, teacher=teacher):  # 查看班级表是否存在
        await matcher.finish(f"[{name}]班级已存在！")
    class_table = await add_class_table(name, teacher, major, group_id, session.id)
    await matcher.finish(f"[{class_table.name}]班级添加成功！")


@show_class_table_cmd.handle()
async def _(matcher: AlconnaMatcher, teacher: Teacher):
    if class_table_list := await get_class_table_list(teacher):
        await matcher.finish(
            "您所创建的班级如下：\n\t- "
            + "\n\t- ".join(f"{i.id}.{i.name}" for i in class_table_list)
        )
    await matcher.finish("您还没有创建班级噢！")


@del_class_table_cmd.handle()
async def _(matcher: AlconnaMatcher, name: str, teacher: Teacher):
    if await delete_class_table(name, teacher):
        await matcher.finish(f"[{name}]班级删除成功！")
    await matcher.finish(f"[{name}]班级不存在！")


@bind_class_table_cmd.handle()
async def _(
    name: str,
    user: User,
    teacher: Teacher,
    matcher: AlconnaMatcher,
    session: SessionPlatform,
    group_id: str = GroupId,
):
    # 查看此群是否已经绑定了班级
    if class_table := await get_class_table(group_id, platform_id=session.id):
        await matcher.finish(f"此群已绑定了[{class_table.name}]班级！]")
    # 没有绑定则查看班级是否存在
    elif class_table := await get_class_table(name, teacher=teacher):
        await add_bind_class_table(group_id, session.id, class_table, user)
        await matcher.finish(f"[{class_table.name}]班级群绑定成功！")
    await matcher.finish(f"[{name}]班级不存在！")
