from __future__ import annotations

from src.commands import CommandExecutionContext, CommandResult, command_executor
from utils.models import User

from .presenters import render_student_card


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
