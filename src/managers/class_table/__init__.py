from utils.typings import UserType
from nonebot.matcher import Matcher
from utils.session import SessionPlatform
from nonebot_plugin_alconna import AlconnaMatcher
from utils.formant import select_list, select_formant
from utils.params.notes import ValidateNameNotNumeric
from utils.models.models import User, Teacher, ClassTable
from utils.params import (
    GroupId,
    UserIdOrAtParams,
    ClassTableDepends,
    TeacherClassTableDepends,
)
from utils.models.depends import (
    get_major,
    get_student,
    get_teacher,
    create_student,
    add_class_table,
    get_class_table,
    delete_group_bind,
    delete_class_table,
    add_bind_class_table,
    get_class_table_list,
    transfer_class_table,
)

from .commands import (
    add_class_table_cmd,
    del_class_table_cmd,
    bind_class_table_cmd,
    join_class_table_cmd,
    show_class_table_cmd,
    unbind_class_table_cmd,
    transfer_class_table_cmd,
    view_class_table_in_group_cmd,
)


@join_class_table_cmd.handle()
async def _(
    user: User,
    matcher: AlconnaMatcher,
    class_table: ClassTableDepends,
    student_name: str,
):
    match user.user_type:
        case UserType.TEACHER:
            await matcher.finish("教师不能加入班级，只能创建您自己的班级！")
        case UserType.STUDENT:
            await matcher.finish("您已经是学生了，不能加入班级只能切换班级！")
        case UserType.ADMIN:
            if await get_student(user):
                await matcher.finish(f"您已经是学生了，不能加入班级只能切换班级！")

    if teacher := await get_teacher(class_table.teacher_id):
        student = await create_student(student_name, class_table, teacher, user)
        await matcher.finish(f"成功加入到[{class_table.name}]您的学生id为【{student.id}】")
    await matcher.finish(f"班级[{class_table.name}]不存在！请检查班级名称是否正确，或者联系教师！")


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
    class_name: str,
    teacher: Teacher,
    matcher: AlconnaMatcher,
    session: SessionPlatform,
    major_name_or_id: int | str,
    group_id: str = GroupId,
):
    if (major := await get_major(major_name_or_id)) is None:  # 获取专业
        await matcher.finish(
            f"专业[{major_name_or_id}]名称或id不存在，请输入`查询专业`命令来查看具体有哪些专业吧！\n(例如: 查询专业 信息工程)"
        )
    elif None is not await get_class_table(class_name):  # 查看班级表是否存在
        await matcher.finish(f"[{class_name}]班级已存在，您不能重复添加！")
    class_table = await add_class_table(
        class_name, teacher, major, group_id, session.id
    )
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
    await matcher.finish("您还没有添加过班级噢！请使用添加班级命令来添加班级吧！\n(例如: 添加班级 软件1 软件技术)")


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


@unbind_class_table_cmd.handle()
async def _(
    matcher: Matcher,
    class_table: ClassTable,
    teacher: Teacher,
    session: SessionPlatform,
    group_id: str = GroupId,
):
    if class_table.teacher_id != teacher.id:
        await matcher.finish("这不是您的班级哦！")
    await delete_group_bind(session.id, group_id)
    await matcher.finish(f"[{class_table.name}]班级群解绑成功！")


@view_class_table_in_group_cmd.handle()
async def _(matcher: Matcher, session: SessionPlatform, group_id: str = GroupId):
    if class_table := await get_class_table(group_id, platform_id=session.id):
        await matcher.finish(f"此群是[{class_table.name}]班级群！")
    await matcher.finish(f"此群没有绑定班级哦！")
