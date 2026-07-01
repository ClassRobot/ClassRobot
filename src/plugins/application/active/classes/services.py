from __future__ import annotations

from typing import Any

from src.shared import Emoji
from src.platform.session import EventSession
from nonebot_plugin_alconna import AlconnaMatcher
from src.platform.commands import CommandResult, CommandExecutionContext, command_executor
from src.core.auth import StudentRole, StudentRoleLang, TeacherRoleLang, TeacherClassesRole
from src.models import User, Major, School, Classes, College, Student, Teacher, TeacherClasses

from .presenters import render_classes_card

CLASS_MANAGER_ROLES = {TeacherClassesRole.counselor, TeacherClassesRole.homeroom}
"""允许管理班级成员和班级教师的教师班级岗位。"""

TEACHER_CLASS_ROLE_ALIASES = {
    TeacherClassesRole.counselor: {"counselor", "辅导员"},
    TeacherClassesRole.homeroom: {"homeroom", "班主任"},
    TeacherClassesRole.teacher: {"teacher", "任课老师", "教师", "老师"},
}
"""教师班级岗位输入别名。"""

STUDENT_ROLE_ALIASES = {
    StudentRole.monitor: {"monitor", "班长"},
    StudentRole.vice_monitor: {"vice_monitor", "副班长"},
    StudentRole.secretary: {"secretary", "团支书"},
    StudentRole.study: {"study", "学习委员"},
    StudentRole.life: {"life", "生活委员"},
    StudentRole.sports: {"sports", "体育委员"},
    StudentRole.organization: {"organization", "组织委员"},
    StudentRole.mental: {"mental", "心理委员"},
    StudentRole.publicity: {"publicity", "宣传委员"},
    StudentRole.arts: {"arts", "文艺委员"},
    StudentRole.assistant: {"assistant", "助教", "班助", "班助/助教"},
    StudentRole.student: {"student", "学生", "普通学生"},
}
"""学生班级岗位输入别名。"""


def parse_teacher_class_role(value: str) -> TeacherClassesRole:
    """解析教师在班级中的岗位。

    Args:
        value: 用户输入的岗位名称，支持中文和枚举值。

    Returns:
        TeacherClassesRole: 解析后的教师班级岗位。

    Raises:
        ValueError: 岗位无法识别时抛出。
    """

    normalized = value.strip().lower()
    for role, aliases in TEACHER_CLASS_ROLE_ALIASES.items():
        if normalized in aliases:
            return role
    raise ValueError("班级教师岗位只支持：班主任、辅导员、任课老师。")


def get_teacher_class_role_label(role: TeacherClassesRole | str) -> str:
    """获取教师班级岗位中文名称。"""

    try:
        return str(TeacherRoleLang[TeacherClassesRole(role).name])
    except Exception:
        return str(role)


def parse_student_role(value: str) -> StudentRole:
    """解析学生在班级中的岗位。

    Args:
        value: 用户输入的岗位名称，支持中文和枚举值。

    Returns:
        StudentRole: 解析后的学生岗位。

    Raises:
        ValueError: 岗位无法识别时抛出。
    """

    normalized = value.strip().lower()
    for role, aliases in STUDENT_ROLE_ALIASES.items():
        if normalized in aliases:
            return role
    raise ValueError("学生岗位不支持，请使用班长、副班长、团支书、学习委员、班助/助教或学生等岗位。")


def get_student_role_label(role: StudentRole | str) -> str:
    """获取学生岗位中文名称。"""

    try:
        return str(StudentRoleLang[StudentRole(role).name])
    except Exception:
        return str(role)


async def can_manage_class(user: User, classes: Classes) -> bool:
    """判断用户是否可以管理指定班级。

    Args:
        user: 当前操作用户。
        classes: 目标班级。

    Returns:
        bool: 具备管理权限时返回 ``True``。
    """

    if user.is_admin:
        return True
    teacher = user.teacher
    if teacher is None:
        return False
    if await teacher.manages_college(classes.college_id):
        return True
    relation = await TeacherClasses.filter(teacher_id=teacher.id, classes_id=classes.id).first()
    return relation is not None and TeacherClassesRole(relation.role) in CLASS_MANAGER_ROLES


async def can_manage_student(user: User, student: Student) -> bool:
    """判断用户是否可以管理指定学生。"""

    return await can_manage_class(user, student.classes)


async def ensure_can_manage_class(matcher: AlconnaMatcher, user: User, classes: Classes) -> None:
    """校验用户是否可以管理班级，不允许时结束命令。"""

    if not await can_manage_class(user, classes):
        await matcher.finish(Emoji.error + "您没有权限管理该班级。")


async def ensure_can_manage_student(matcher: AlconnaMatcher, user: User, student: Student) -> None:
    """校验用户是否可以管理学生，不允许时结束命令。"""

    if not await can_manage_student(user, student):
        await matcher.finish(Emoji.error + "您没有权限管理该学生。")


async def manager_teacher_count(classes: Classes) -> int:
    """统计班级中的管理教师数量。"""

    return await TeacherClasses.filter(
        (TeacherClasses.classes_id == classes.id) & (TeacherClasses.role.in_(list(CLASS_MANAGER_ROLES)))
    ).count()


@command_executor.handler("查询班级")
async def execute_query_classes(params: dict[str, Any], context: CommandExecutionContext) -> CommandResult:
    """执行统一的“查询班级”命令。

    Args:
        params: 统一命令参数，支持 ``班级ID`` 或 ``classes_id``。
        context: 命令执行上下文。

    Returns:
        CommandResult: 标准化班级查询结果。
    """

    if context.user_id is None:
        return CommandResult.fail("缺少用户 ID，无法查询班级信息。")

    user = await User.get_user(context.user_id)
    if user is None or user.teacher is None:
        return CommandResult.fail("当前账号还不是教师，无法查询管理的班级。")

    teacher = user.teacher
    if not teacher.classes:
        return CommandResult.fail("您还未创建班级！！")

    try:
        classes_id = parse_optional_classes_id(params)
    except ValueError:
        return CommandResult.fail("班级ID必须为数字。")
    if classes_id is not None:
        classes = await teacher.get_classes(classes_id)
        if classes is None:
            return CommandResult.fail(f"班级[{classes_id}]不存在，或不属于您管理。")
        classes_list = [classes]
        title = "班级详情"
    else:
        classes_list = list(teacher.classes)
        title = "您所管理的班级如下"

    card = await render_classes_card(title, classes_list)
    return CommandResult.ok(
        "已查询班级信息。",
        visible_outputs=[card],
        context_outputs=[card],
        data={
            "classes": [
                {
                    "id": classes.id,
                    "name": classes.name,
                    "school_id": classes.school_id,
                    "college_id": classes.college_id,
                    "major_id": classes.major_id,
                    "group_id": classes.group_id,
                }
                for classes in classes_list
            ],
        },
    )


def parse_optional_classes_id(params: dict[str, Any]) -> int | None:
    """从统一命令参数中解析可选班级 ID。

    Args:
        params: 统一命令参数字典。

    Returns:
        int | None: 解析后的班级 ID；未提供时返回 ``None``。

    Raises:
        ValueError: 当班级 ID 无法转换为整数时抛出。
    """

    value = params.get("班级ID", params.get("classes_id"))
    if value is None or value == "":
        return None
    return int(value)


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
