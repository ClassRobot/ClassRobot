from src.shared import Emoji
from src.models import User, Classes, Student
from src.models.depends import StudentDepends, UserOrCreatedDepends
from nonebot_plugin_alconna import AlconnaMatcher
from src.models.params.student import is_user_key, get_column_key, is_student_key, is_student_extra_key

from .commands import (
    query_cmd,
    set_cmd,
    query_student_profile_cmd,
    add_student_profile_cmd,
    set_student_profile_cmd,
    delete_student_profile_cmd,
)
from .presenters import render_student_card
from .services import can_manage_student, apply_student_updates, parse_student_update_values
from src.plugins.application.active.classes.services import can_manage_class
# 导入统一命令 service，确保插件加载时完成 command_executor 注册。
from . import services as _


@query_cmd.handle()
async def _(matcher: AlconnaMatcher, student: StudentDepends):
    """查询学生信息。"""
    if student is None:
        await matcher.finish(Emoji.error + "您还未绑定学生信息！！")
    await matcher.finish(await render_student_card(student))


@query_student_profile_cmd.handle()
async def _(matcher: AlconnaMatcher, user: UserOrCreatedDepends, student_id: int | None):
    """按权限查询学生档案。"""
    if student_id is not None:
        student = await Student.filter(id=student_id).first()
        if student is None:
            await matcher.finish(Emoji.error + f"学生[{student_id}]不存在。")
        if not await can_manage_student(user, student):
            await matcher.finish(Emoji.error + "您没有权限查看该学生档案。")
        await matcher.finish(await render_student_card(student))

    if user.is_admin:
        students = await Student.filter().all()
    elif user.teacher is not None:
        college_ids = await user.teacher.get_managed_college_ids()
        if college_ids:
            students = [student for student in await Student.filter().all() if student.classes.college_id in college_ids]
        else:
            class_ids = [classes.id for classes in user.teacher.classes]
            students = await Student.filter(Student.classes_id.in_(class_ids)).all() if class_ids else []
    else:
        students = []
    if not students:
        await matcher.finish(Emoji.warning + "当前没有可查看的学生档案。")
    lines = [Emoji.info + "学生档案列表"] + [
        f"[{student.id}] {student.name} / 班级:{student.classes.name} / 学校:{student.school.name if student.school else '未设置'}"
        for student in students
    ]
    await matcher.finish("\n".join(lines))


@add_student_profile_cmd.handle()
async def _(
    matcher: AlconnaMatcher,
    user: UserOrCreatedDepends,
    user_id: int,
    classes_id: int,
    name: str,
):
    """按权限添加学生档案。"""
    target_user = await User.get_user(user_id)
    if target_user is None:
        await matcher.finish(Emoji.error + f"用户[{user_id}]不存在。")
    if target_user.teacher is not None:
        await matcher.finish(Emoji.error + "该用户已经是教师身份，不能创建学生档案。")
    if target_user.student is not None:
        await matcher.finish(Emoji.error + "该用户已经绑定学生档案。")
    classes = await Classes.filter(id=classes_id).first()
    if classes is None:
        await matcher.finish(Emoji.error + f"班级[{classes_id}]不存在。")
    if not await can_manage_class(user, classes):
        await matcher.finish(Emoji.error + "您没有权限向该班级添加学生。")
    student = await Student.create_student(name.strip(), classes, target_user, school_id=classes.school_id)
    await matcher.finish(Emoji.success + "学生档案创建成功！\n" + await render_student_card(student))


@set_student_profile_cmd.handle()
async def _(matcher: AlconnaMatcher, user: UserOrCreatedDepends, student_id: int, values: list[str]):
    """按权限修改学生档案。"""
    student = await Student.filter(id=student_id).first()
    if student is None:
        await matcher.finish(Emoji.error + f"学生[{student_id}]不存在。")
    if not await can_manage_student(user, student):
        await matcher.finish(Emoji.error + "您没有权限修改该学生档案。")
    try:
        options = parse_student_update_values(values)
    except ValueError as error:
        await matcher.finish(Emoji.error + str(error))
    student = await apply_student_updates(student, options)
    await matcher.finish(Emoji.success + "学生档案修改成功！\n" + await render_student_card(student))


@delete_student_profile_cmd.handle()
async def _(matcher: AlconnaMatcher, user: UserOrCreatedDepends, student_id: int):
    """按权限删除学生档案。"""
    student = await Student.filter(id=student_id).first()
    if student is None:
        await matcher.finish(Emoji.error + f"学生[{student_id}]不存在。")
    if not await can_manage_student(user, student):
        await matcher.finish(Emoji.error + "您没有权限删除该学生档案。")
    await student.delete()
    await matcher.finish(Emoji.success + f"学生[{student_id}]档案已删除。")


@set_cmd.handle()
async def _(matcher: AlconnaMatcher, values: list[str], student: StudentDepends):
    """处理当前命令或事件逻辑。"""
    if student is None:
        await matcher.finish(Emoji.error + "您还未绑定学生信息！！")

    options = {}
    for value in values:
        value_split = value.split("=")
        if len(value_split) != 2:
            await matcher.finish(Emoji.error + f"参数 {value} 格式错误！！\n应该采用 名字=张三 的形式")
        key, value = value_split
        if column := get_column_key(key):
            options[column] = value

    if not options:
        await matcher.finish(Emoji.error + "未找到有效参数！！")
    if "role" in options:
        await matcher.finish(Emoji.error + "学生不能自行修改班级岗位，请联系班主任、辅导员或学院负责人设置。")

    for key, value in options.items():
        if is_student_key(key):
            await student.update(**{key: value})
        elif is_student_extra_key(key):
            if not student.extra:
                await student.create_extra()
            await student.extra.update(**{key: value})  # type: ignore
        elif is_user_key(key):
            await student.user.update(**{key: value})

    await matcher.finish(Emoji.success + "设置成功！！")
