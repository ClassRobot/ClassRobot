from __future__ import annotations

from src.shared import Emoji
from nonebot_plugin_alconna import AlconnaMatcher
from src.models import User, School, College, Teacher
from src.platform.commands import CommandResult, CommandExecutionContext, command_executor

from .presenters import render_teacher_card

TEACHER_COLUMNS = {
    "name": ["姓名", "名字", "昵称"],
    "school": ["学校", "学校名称"],
    "college": ["学院", "学院名称"],
}
"""教师信息命令支持修改的字段和中文别名。"""


async def can_manage_teacher(operator: User, teacher: Teacher, *, target_college_id: int | None = None) -> bool:
    """判断用户是否可以管理指定教师档案。

    Args:
        operator: 当前操作用户。
        teacher: 目标教师。
        target_college_id: 修改后目标学院 ID；为空时使用教师当前学院。

    Returns:
        bool: 具备管理权限时返回 ``True``。
    """

    if operator.is_admin:
        return True
    operator_teacher = operator.teacher
    if operator_teacher is None:
        return False
    college_id = target_college_id if target_college_id is not None else teacher.college_id
    return await operator_teacher.manages_college(college_id)


async def get_teacher_or_error(teacher_id: int) -> Teacher | None:
    """按 ID 获取教师档案。"""

    return await Teacher.filter(id=teacher_id).first()


async def resolve_teacher_scope(
    school_name: str | None,
    college_name: str | None,
    current_school: School | None = None,
) -> tuple[School | None, College | None]:
    """解析教师档案中的学校和学院归属。

    Args:
        school_name: 学校名称。
        college_name: 学院名称。
        current_school: 未提供学校名称时可复用的当前学校。

    Returns:
        tuple[School | None, College | None]: 解析后的学校与学院。

    Raises:
        ValueError: 学校或学院不存在，或参数组合不合法。
    """

    school = current_school
    if school_name is not None:
        school = await School.filter(name=school_name.strip()).first()
        if school is None:
            raise ValueError(f"学校`{school_name}`不存在。")
    college = None
    if college_name is not None:
        if school is None:
            raise ValueError("指定学院前请先提供学校名称，或先为教师绑定学校。")
        college = await College.filter(name=college_name.strip(), school_id=school.id).first()
        if college is None:
            raise ValueError(f"学院`{college_name}`不存在于学校`{school.name}`下。")
    return school, college


@command_executor.handler("查询教师信息")
async def execute_query_teacher(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行统一的“查询教师信息”命令。

    Args:
        params: 统一命令参数。
        context: 命令执行上下文。

    Returns:
        CommandResult: 标准化命令执行结果。
    """

    if context.user_id is None:
        return CommandResult.fail("缺少用户 ID，无法查询教师信息。")

    user = await User.get_user(context.user_id)
    if user is None or user.teacher is None:
        return CommandResult.fail("当前账号还未绑定教师信息。")

    card = await render_teacher_card(user.teacher)
    return CommandResult.ok(
        "已查询教师信息。",
        visible_outputs=[card],
        context_outputs=[card],
        data={
            "teacher_id": user.teacher.id,
            "user_id": user.id,
            "classes_count": len(user.teacher.classes),
        },
    )


@command_executor.handler("查询教师")
async def execute_query_teacher_profile(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行统一的“查询教师”管理命令。"""

    if context.user_id is None:
        return CommandResult.fail("缺少用户 ID，无法查询教师档案。")
    operator = await User.get_user(context.user_id)
    if operator is None:
        return CommandResult.fail("当前账号不存在。")

    teacher_id = params.get("教师ID", params.get("teacher_id"))
    if teacher_id:
        teacher = await Teacher.filter(id=int(teacher_id)).first()
        if teacher is None:
            return CommandResult.fail(f"教师[{teacher_id}]不存在。")
        if not await can_manage_teacher(operator, teacher):
            return CommandResult.fail("您没有权限查看该教师档案。")
        card = await render_teacher_card(teacher)
        return CommandResult.ok("已查询教师档案。", visible_outputs=[card], context_outputs=[card])

    if operator.is_admin:
        teachers = await Teacher.filter().all()
    elif operator.teacher is not None:
        college_ids = await operator.teacher.get_managed_college_ids()
        teachers = await Teacher.filter(Teacher.college_id.in_(college_ids)).all() if college_ids else []
    else:
        teachers = []
    if not teachers:
        return CommandResult.fail("当前没有可查看的教师档案。")
    lines = ["教师档案列表"] + [
        f"- [{teacher.id}] {teacher.name} / 学校:{teacher.school.name if teacher.school else '未设置'} / 学院:{teacher.college.name if teacher.college else '未设置'}"
        for teacher in teachers
    ]
    output = "\n".join(lines)
    return CommandResult.ok(
        "已查询教师档案列表。",
        visible_outputs=[output],
        context_outputs=[output],
        data={"teacher_ids": [teacher.id for teacher in teachers]},
    )


def get_teacher_column_key(value: str) -> str | None:
    """解析教师可修改字段。

    Args:
        value: 用户输入的字段名称。

    Returns:
        str | None: 可更新的模型字段名；无法识别时返回 ``None``。
    """

    value = value.strip()
    for key, aliases in TEACHER_COLUMNS.items():
        if value in aliases:
            return key
    return None


async def validate_teacher_scope_change(
    matcher: AlconnaMatcher,
    teacher: Teacher,
    school: School | None,
    college: College | None,
) -> None:
    """校验教师归属变更是否与已管理班级冲突。

    Args:
        matcher: 当前命令 matcher，用于在校验失败时结束会话。
        teacher: 当前教师对象。
        school: 准备切换到的学校对象；为 ``None`` 时不校验学校。
        college: 准备切换到的学院对象；为 ``None`` 时不校验学院。
    """

    if school is not None:
        invalid_classes = [
            classes for classes in teacher.classes if classes.school_id is not None and classes.school_id != school.id
        ]
        if invalid_classes:
            await matcher.finish(
                Emoji.error
                + f"您已管理其他学校的班级，暂时不能修改归属学校。冲突班级: {'、'.join(classes.name for classes in invalid_classes[:5])}"
            )

    if college is not None:
        invalid_classes = [
            classes
            for classes in teacher.classes
            if classes.college_id is not None and classes.college_id != college.id
        ]
        if invalid_classes:
            await matcher.finish(
                Emoji.error
                + f"您已管理其他学院的班级，暂时不能修改归属学院。冲突班级: {'、'.join(classes.name for classes in invalid_classes[:5])}"
            )
