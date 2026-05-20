from __future__ import annotations

from utils.commands import CommandExecutionContext, CommandResult, command_executor
from utils.models import User, Student
from utils.params.student import is_user_key, get_column_key, is_student_key, is_student_extra_key

from .presenters import render_student_card


async def can_manage_student(operator: User, student: Student) -> bool:
    """判断用户是否可以管理指定学生档案。

    Args:
        operator: 当前操作用户。
        student: 目标学生。

    Returns:
        bool: 具备管理权限时返回 ``True``。
    """

    if operator.is_admin:
        return True
    teacher = operator.teacher
    if teacher is None:
        return False
    if await teacher.manages_college(student.classes.college_id):
        return True
    relation = next((item for item in teacher.classes if item.id == student.classes_id), None)
    if relation is None:
        return False
    from src.features.classes.services import CLASS_MANAGER_ROLES
    from utils.models import TeacherClasses
    from utils.roles import TeacherClassesRole

    teacher_classes = await TeacherClasses.filter(teacher_id=teacher.id, classes_id=student.classes_id).first()
    return teacher_classes is not None and TeacherClassesRole(teacher_classes.role) in CLASS_MANAGER_ROLES


def parse_student_update_values(values: list[str]) -> dict[str, str]:
    """解析学生档案更新参数。

    Args:
        values: 用户输入的 ``key=value`` 参数列表。

    Returns:
        dict[str, str]: 解析后的字段和值。

    Raises:
        ValueError: 参数格式错误或没有可识别字段。
    """

    options: dict[str, str] = {}
    for value in values:
        value_split = value.split("=", 1)
        if len(value_split) != 2:
            raise ValueError(f"参数 {value} 格式错误，应采用 名字=张三 的形式。")
        key, raw_value = value_split
        if column := get_column_key(key):
            normalized_value = raw_value.strip()
            if normalized_value:
                options[column] = normalized_value
    if not options:
        raise ValueError("未找到有效参数。")
    return options


async def apply_student_updates(student: Student, options: dict[str, str]) -> Student:
    """应用学生档案更新。

    Args:
        student: 目标学生。
        options: 已解析的更新字段。

    Returns:
        Student: 更新后的学生对象。
    """

    student_payload = {key: value for key, value in options.items() if is_student_key(key)}
    extra_payload = {key: value for key, value in options.items() if is_student_extra_key(key)}
    user_payload = {key: value for key, value in options.items() if is_user_key(key)}
    if student_payload:
        student = await student.update(**student_payload)
    if extra_payload:
        if not student.extra:
            from utils.models import StudentExtra

            await StudentExtra(student=student).create()
        await student.extra.update(**extra_payload)
    if user_payload:
        await student.user.update(**user_payload)
    return student


@command_executor.handler("查询学生信息")
async def execute_query_student(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行统一的“查询学生信息”命令。

    Args:
        params: 统一命令参数。
        context: 命令执行上下文。

    Returns:
        CommandResult: 标准化命令执行结果。
    """

    if context.user_id is None:
        return CommandResult.fail("缺少用户 ID，无法查询学生信息。")

    user = await User.get_user(context.user_id)
    if user is None or user.student is None:
        return CommandResult.fail("当前账号还未绑定学生信息。")

    card = await render_student_card(user.student)
    return CommandResult.ok(
        "已查询学生信息。",
        visible_outputs=[card],
        context_outputs=[card],
        data={
            "student_id": user.student.id,
            "user_id": user.id,
            "classes_id": user.student.classes_id,
            "role": str(user.student.role),
        },
    )


@command_executor.handler("查询学生档案")
async def execute_query_student_profile(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行统一的“查询学生档案”管理命令。"""

    if context.user_id is None:
        return CommandResult.fail("缺少用户 ID，无法查询学生档案。")
    operator = await User.get_user(context.user_id)
    if operator is None:
        return CommandResult.fail("当前账号不存在。")

    student_id = params.get("学生ID", params.get("student_id"))
    if student_id:
        student = await Student.filter(id=int(student_id)).first()
        if student is None:
            return CommandResult.fail(f"学生[{student_id}]不存在。")
        if not await can_manage_student(operator, student):
            return CommandResult.fail("您没有权限查看该学生档案。")
        card = await render_student_card(student)
        return CommandResult.ok("已查询学生档案。", visible_outputs=[card], context_outputs=[card])

    if operator.is_admin:
        students = await Student.filter().all()
    elif operator.teacher is not None:
        college_ids = await operator.teacher.get_managed_college_ids()
        if college_ids:
            students = await Student.filter().all()
            students = [student for student in students if student.classes.college_id in college_ids]
        else:
            class_ids = [classes.id for classes in operator.teacher.classes]
            students = await Student.filter(Student.classes_id.in_(class_ids)).all() if class_ids else []
    else:
        students = []
    if not students:
        return CommandResult.fail("当前没有可查看的学生档案。")
    lines = ["学生档案列表"] + [
        f"- [{student.id}] {student.name} / 班级:{student.classes.name} / 学校:{student.school.name if student.school else '未设置'}"
        for student in students
    ]
    output = "\n".join(lines)
    return CommandResult.ok(
        "已查询学生档案列表。",
        visible_outputs=[output],
        context_outputs=[output],
        data={"student_ids": [student.id for student in students]},
    )
