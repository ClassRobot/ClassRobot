from nonebot.matcher import Matcher
from utils.session import SessionPlatform
from utils.models.models import User, Teacher
from nonebot_plugin_alconna import AlconnaMatcher
from utils.formant import select_list, select_formant
from utils.params import GroupId, UserIdOrAtParams, TeacherClassTableDepends
from utils.models.depends import (
    get_major,
    get_teacher,
    add_class_table,
    get_class_table,
    delete_class_table,
    add_bind_class_table,
    get_class_table_list,
    transfer_class_table,
)

from .commands import (
    add_class_table_cmd,
    del_class_table_cmd,
    bind_class_table_cmd,
    show_class_table_cmd,
    transfer_class_table_cmd,
)


@transfer_class_table_cmd.handle()
async def _(
    matcher: AlconnaMatcher,
    class_table: TeacherClassTableDepends,
    teacher_user: User = UserIdOrAtParams(True),
):
    if new_teacher := await get_teacher(teacher_user):
        await transfer_class_table(class_table, new_teacher)
        await matcher.finish(f"成功将[{class_table.name}]转让给教师用户[{teacher_user.id}]")
    await matcher.finish(f"用户[{teacher_user.id}]不是教师")


@add_class_table_cmd.handle()
async def _(
    name: str,
    major_name: str,
    teacher: Teacher,
    matcher: AlconnaMatcher,
    session: SessionPlatform,
    group_id: str = GroupId,
):
    if name.isdigit():  # 判断班级名是否为数字
        await matcher.finish("班级名不能为纯数字！")
    elif (major := await get_major(major_name)) is None:  # 获取专业
        await matcher.finish(f"[{major_name}]专业不存在")
    elif None is not await get_class_table(name):  # 查看班级表是否存在
        await matcher.finish(f"[{name}]班级已存在！")
    class_table = await add_class_table(name, teacher, major, group_id, session.id)
    await matcher.finish(f"[{class_table.name}]班级添加成功！")


@show_class_table_cmd.handle()
async def _(matcher: AlconnaMatcher, teacher: Teacher):
    if class_table_list := await get_class_table_list(teacher):
        await matcher.finish(
            select_list(
                "您所创建的班级如下",
                (select_formant(i.id, i.name) for i in class_table_list),
            )
        )
    await matcher.finish("您还没有创建班级噢！")


@del_class_table_cmd.handle()
async def _(
    matcher: Matcher,
    teacher_class_table: TeacherClassTableDepends,
):
    if await delete_class_table(teacher_class_table):
        await matcher.finish(f"[{teacher_class_table.name}]班级删除成功！")
    await matcher.finish(f"[{teacher_class_table.name}]班级删除失败！")


@bind_class_table_cmd.handle()
async def _(
    user: User,
    matcher: AlconnaMatcher,
    session: SessionPlatform,
    teacher_class_table: TeacherClassTableDepends,
    group_id: str = GroupId,
):
    # 查看此群是否已经绑定了班级
    if class_table := await get_class_table(group_id, platform_id=session.id):
        await matcher.finish(f"此群已绑定了[{class_table.name}]班级！]")
    await add_bind_class_table(group_id, session.id, teacher_class_table, user)
    await matcher.finish(f"[{teacher_class_table.name}]班级群绑定成功！")
