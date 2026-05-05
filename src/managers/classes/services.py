from __future__ import annotations

from utils import Emoji
from utils.session import EventSession
from utils.models import School, Classes, College, Major, Teacher
from nonebot_plugin_alconna import AlconnaMatcher


async def resolve_teacher_request_scope(
    matcher: AlconnaMatcher,
    teacher: Teacher | None,
    platform: EventSession,
    classes_id: int | None,
) -> list[Classes]:
    """解析教师查看入班申请时的班级范围。

    Args:
        matcher: 当前命令 matcher，用于在校验失败时结束会话。
        teacher: 当前用户的教师身份。
        platform: 当前事件平台信息。
        classes_id: 用户显式指定的班级 ID。

    Returns:
        list[Classes]: 教师可查看入班申请的班级列表。
    """

    if teacher is None or not teacher.classes:
        await matcher.finish(Emoji.warning + "您还未创建班级！！")

    if classes_id is not None:
        classes = await teacher.get_classes(classes_id)
        if classes is None:
            await matcher.finish(Emoji.error + f"班级[{classes_id}]不存在，或不属于您管理。")
        return [classes]

    if platform.is_group:
        classes = await teacher.get_classes(platform.platform, platform.channel_id, platform.guild_id)
        if classes is not None:
            return [classes]

    return list(teacher.classes)


async def resolve_class_scope(
    matcher: AlconnaMatcher,
    teacher: Teacher | None,
    school_name: str | None,
    college_name: str | None,
    major_name: str | None,
) -> tuple[School | None, College | None, Major | None]:
    """解析创建或绑定班级时指定的学校、学院和专业范围。

    Args:
        matcher: 当前命令 matcher，用于在校验失败时结束会话。
        teacher: 当前用户已有的教师身份。
        school_name: 用户输入的学校名称。
        college_name: 用户输入的学院名称。
        major_name: 用户输入的专业名称。

    Returns:
        tuple[School | None, College | None, Major | None]: 解析后的学校、学院和专业对象。
    """

    school = teacher.school if teacher and teacher.school_id else None
    college = teacher.college if teacher and teacher.college_id else None
    major = None

    if school_name:
        school_name = school_name.strip()
        school = await School.filter(name=school_name).first()
        if school is None:
            await matcher.finish(Emoji.error + f"学校`{school_name}`不存在！")
        if teacher and teacher.school_id and teacher.school_id != school.id:
            await matcher.finish(Emoji.error + f"您的教师归属学校为`{teacher.school.name}`，不能跨学校创建班级！")

    if college_name:
        college_name = college_name.strip()
        if school is None:
            await matcher.finish(Emoji.error + "指定学院前请先提供学校名称，或先为教师设置学校归属。")
        college = await College.filter(name=college_name, school_id=school.id).first()
        if college is None:
            await matcher.finish(Emoji.error + f"学院`{college_name}`不存在于学校`{school.name}`下！")
        if teacher and teacher.college_id and teacher.college_id != college.id:
            await matcher.finish(Emoji.error + f"您的教师归属学院为`{teacher.college.name}`，不能跨学院创建班级！")
    elif college and school and college.school_id != school.id:
        college = None

    if major_name:
        major_name = major_name.strip()
        if college is None:
            await matcher.finish(Emoji.error + "指定专业前请先提供学院名称，或先为教师设置学院归属。")
        major = await Major.filter(name=major_name, college_id=college.id).first()
        if major is None:
            await matcher.finish(Emoji.error + f"专业`{major_name}`不存在于学院`{college.name}`下，请先添加专业。")

    return school, college, major


async def ensure_teacher_scope(teacher: Teacher, school: School | None, college: College | None) -> Teacher:
    """尽量把教师归属补齐到指定学校和学院。

    Args:
        teacher: 待补齐归属的教师对象。
        school: 已解析的学校对象。
        college: 已解析的学院对象。

    Returns:
        Teacher: 更新后的教师对象。
    """

    payload = {}
    if school and teacher.school_id is None:
        payload["school_id"] = school.id
    if college and teacher.college_id is None:
        payload["college_id"] = college.id
    if payload:
        teacher = await teacher.update(**payload)
    return teacher
