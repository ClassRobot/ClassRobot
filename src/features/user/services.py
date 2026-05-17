from __future__ import annotations

from utils.commands import CommandExecutionContext, CommandResult, command_executor
from utils.models import User

from .presenters import render_user_card


@command_executor.handler("我的信息")
async def execute_self_info(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行统一的“我的信息”查询命令。

    Args:
        params: 统一命令参数。
        context: 命令执行上下文。

    Returns:
        CommandResult: 标准化命令执行结果。
    """

    if context.user_id is None:
        return CommandResult.fail("缺少用户 ID，无法查询当前账号信息。")

    user = await User.get_user(context.user_id)
    if user is None:
        return CommandResult.fail("未找到当前用户信息，请先完成账号绑定。")

    card = await render_user_card(user)
    return CommandResult.ok(
        "已查询当前账号信息。",
        visible_outputs=[card],
        context_outputs=[card],
        data={
            "user_id": user.id,
            "nickname": user.nickname,
            "username": user.username,
            "roles": [role.value for role in user.roles],
        },
    )
