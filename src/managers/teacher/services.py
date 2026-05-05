from __future__ import annotations

from nonebot_plugin_alconna import AlconnaMatcher

from src.commands import CommandExecutionContext, CommandResult, command_executor
from utils import Emoji
from utils.models import College, School, Teacher, User

from .presenters import render_teacher_card

TEACHER_COLUMNS = {
    "name": ["姓名", "名字", "昵称"],
    "school": ["学校", "学校名称"],
    "college": ["学院", "学院名称"],
}
"""教师信息命令支持修改的字段和中文别名。"""


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
