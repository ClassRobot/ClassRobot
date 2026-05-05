from utils import Emoji
from nonebot_plugin_alconna import AlconnaMatcher
from utils.models import School, College, Teacher
from utils.models.depends import TeacherDepends, UserOrCreatedDepends

from .presenters import render_teacher_card
from .services import get_teacher_column_key, validate_teacher_scope_change
from .commands import query_teacher_cmd, set_teacher_cmd


@query_teacher_cmd.handle()
async def _(matcher: AlconnaMatcher, teacher: TeacherDepends):
    """查询教师信息。"""
    if teacher is None:
        await matcher.finish(Emoji.warning + "您还未绑定教师信息，可先使用“修改教师信息 姓名=xxx 学校=xxx”创建。")
    await matcher.finish(await render_teacher_card(teacher))


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
