from src.shared import Emoji
from nonebot_plugin_alconna import AlconnaMatcher
from src.models import User, School, College, Teacher
from src.platform.session.depends import TeacherDepends, UserOrCreatedDepends

from .presenters import render_teacher_card
from .services import can_manage_teacher, resolve_teacher_scope, get_teacher_column_key, validate_teacher_scope_change
from .commands import (
    set_teacher_cmd,
    query_teacher_cmd,
    add_teacher_profile_cmd,
    set_teacher_profile_cmd,
    query_teacher_profile_cmd,
    delete_teacher_profile_cmd,
)


@add_teacher_profile_cmd.handle()
async def _(
    matcher: AlconnaMatcher,
    user: UserOrCreatedDepends,
    user_id: int,
    name: str,
    school_name: str | None,
    college_name: str | None,
):
    """按权限添加教师档案。"""
    target_user = await User.get_user(user_id)
    if target_user is None:
        await matcher.finish(Emoji.error + f"用户[{user_id}]不存在。")
    if target_user.student is not None:
        await matcher.finish(Emoji.error + "该用户已经是学生身份，不能创建教师档案。")
    if target_user.teacher is not None:
        await matcher.finish(Emoji.error + "该用户已经绑定教师档案。")
    try:
        school, college = await resolve_teacher_scope(school_name, college_name)
    except ValueError as error:
        await matcher.finish(Emoji.error + str(error))
    if not user.is_admin:
        if user.teacher is None or college is None or not await user.teacher.manages_college(college.id):
            await matcher.finish(Emoji.error + "学院负责人只能在自己负责的学院内添加教师档案。")
    teacher = await Teacher.create_teacher(
        name.strip(),
        target_user,
        school_id=school.id if school else None,
        college_id=college.id if college else None,
    )
    await matcher.finish(Emoji.success + "教师档案创建成功！\n" + await render_teacher_card(teacher))


@set_teacher_profile_cmd.handle()
async def _(matcher: AlconnaMatcher, user: UserOrCreatedDepends, teacher_id: int, values: list[str]):
    """按权限修改教师档案。"""
    teacher = await Teacher.filter(id=teacher_id).first()
    if teacher is None:
        await matcher.finish(Emoji.error + f"教师[{teacher_id}]不存在。")

    options: dict[str, str] = {}
    for item in values:
        key_value = item.split("=", 1)
        if len(key_value) != 2:
            await matcher.finish(Emoji.error + f"参数 {item} 格式错误，应采用 姓名=张老师 的形式。")
        raw_key, raw_value = key_value
        if column := get_teacher_column_key(raw_key):
            value = raw_value.strip()
            if value:
                options[column] = value
    if not options:
        await matcher.finish(Emoji.error + "未找到可修改的教师字段，支持：姓名、学校、学院。")
    if not user.is_admin and ({"school", "college"} & set(options)):
        await matcher.finish(Emoji.error + "学院负责人只能修改本学院教师的基础信息，不能调整学校或学院归属。")

    school_name = options.get("school")
    college_name = options.get("college")
    try:
        school, college = await resolve_teacher_scope(school_name, college_name, teacher.school)
    except ValueError as error:
        await matcher.finish(Emoji.error + str(error))
    target_college_id = college.id if college else (teacher.college_id if college_name is None else None)
    if not await can_manage_teacher(user, teacher, target_college_id=target_college_id):
        await matcher.finish(Emoji.error + "您没有权限修改该教师档案。")

    await validate_teacher_scope_change(matcher, teacher, school if school_name is not None else None, college)
    payload = {}
    if "name" in options and options["name"] != teacher.name:
        payload["name"] = options["name"]
    if school_name is not None:
        payload["school_id"] = school.id if school else None
        if college_name is None and (teacher.college is None or teacher.college.school_id != school.id):
            payload["college_id"] = None
    if college_name is not None:
        payload["college_id"] = college.id
    if not payload:
        await matcher.finish(Emoji.warning + "教师档案没有变化。")
    teacher = await teacher.update(**payload)
    await matcher.finish(Emoji.success + "教师档案修改成功！\n" + await render_teacher_card(teacher))


@delete_teacher_profile_cmd.handle()
async def _(matcher: AlconnaMatcher, user: UserOrCreatedDepends, teacher_id: int):
    """按权限删除教师档案。"""
    teacher = await Teacher.filter(id=teacher_id).first()
    if teacher is None:
        await matcher.finish(Emoji.error + f"教师[{teacher_id}]不存在。")
    if user.teacher is not None and user.teacher.id == teacher.id and not user.is_admin:
        await matcher.finish(Emoji.error + "学院负责人不能删除自己的教师档案。")
    if not await can_manage_teacher(user, teacher):
        await matcher.finish(Emoji.error + "您没有权限删除该教师档案。")
    await teacher.delete()
    await matcher.finish(Emoji.success + f"教师[{teacher_id}]档案已删除。")


@set_teacher_cmd.handle()
async def _(matcher: AlconnaMatcher, values: list[str], user: UserOrCreatedDepends):
    """修改教师信息。"""
    teacher = user.teacher
    if teacher is None and user.student is not None:
        await matcher.finish(Emoji.error + "您当前是学生身份，不能直接创建教师信息。")

    options: dict[str, str] = {}
    for item in values:
        key_value = item.split("=", 1)
        if len(key_value) != 2:
            await matcher.finish(Emoji.error + f"参数 {item} 格式错误，应采用 姓名=张老师 的形式。")
        raw_key, raw_value = key_value
        if column := get_teacher_column_key(raw_key):
            value = raw_value.strip()
            if value:
                options[column] = value

    if not options:
        await matcher.finish(Emoji.error + "未找到可修改的教师字段，支持：姓名、学校、学院。")

    school = teacher.school if teacher and teacher.school_id else None
    college = teacher.college if teacher and teacher.college_id else None
    school_name = options.get("school")
    college_name = options.get("college")

    if school_name is not None:
        school = await School.filter(name=school_name).first()
        if school is None:
            await matcher.finish(Emoji.error + f"学校`{school_name}`不存在！")
        if college and college.school_id != school.id:
            college = None

    if college_name is not None:
        if school is None:
            await matcher.finish(Emoji.error + "指定学院前请先提供学校名称，或先为教师绑定学校。")
        college = await College.filter(name=college_name, school_id=school.id).first()
        if college is None:
            await matcher.finish(Emoji.error + f"学院`{college_name}`不存在于学校`{school.name}`下！")

    if teacher is None:
        teacher = await Teacher.create_teacher(
            options.get("name", user.nickname),
            user,
            school_id=school.id if school else None,
            college_id=college.id if college else None,
        )
        await matcher.finish(Emoji.success + "教师信息创建成功！\n" + await render_teacher_card(teacher))

    await validate_teacher_scope_change(matcher, teacher, school if school_name is not None else None, college)

    payload = {}
    if "name" in options and options["name"] != teacher.name:
        payload["name"] = options["name"]
    if school_name is not None:
        payload["school_id"] = school.id if school else None
        if college_name is None and (teacher.college is None or teacher.college.school_id != school.id):
            payload["college_id"] = None
    if college_name is not None:
        payload["college_id"] = college.id

    if not payload:
        await matcher.finish(Emoji.warning + "教师信息没有变化。")

    teacher = await teacher.update(**payload)
    await matcher.finish(Emoji.success + "教师信息修改成功！\n" + await render_teacher_card(teacher))
