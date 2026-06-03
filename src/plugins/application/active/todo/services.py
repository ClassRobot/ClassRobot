from __future__ import annotations

from datetime import datetime

from src.models import Todo
from src.models.models import TodoStatus
from src.platform.commands import CommandParams, CommandResult, CommandExecutionContext, command_executor

from .presenters import render_todo_list, render_todo_detail
from .schema import parse_due_at, normalize_text, resolve_query_status, split_due_and_content


def _require_user_id(context: CommandExecutionContext) -> int | None:
    """从命令上下文中取出系统用户 ID。

    Args:
        context: 命令执行上下文。

    Returns:
        int | None: 已解析的系统用户 ID；缺失时返回 ``None``。
    """

    return context.user_id


@command_executor.handler("创建待办")
async def execute_create_todo(params: CommandParams, context: CommandExecutionContext) -> CommandResult:
    """创建一条个人待办。"""

    user_id = _require_user_id(context)
    if user_id is None:
        return CommandResult.fail("缺少用户 ID，无法创建待办。")

    title = normalize_text(params.get_value("标题", "title"))
    if not title:
        return CommandResult.fail("待办标题不能为空。")

    due_raw = params.get_value("截止时间", "due")
    content_raw = params.get_value("备注", "content")
    if not due_raw and not content_raw and "rest" in params:
        due_raw, content_raw = split_due_and_content(params.get("rest"))

    try:
        due_at = parse_due_at(due_raw)
    except ValueError as error:
        return CommandResult.fail(str(error))
    content = normalize_text(content_raw) or None

    todo = await Todo.create_todo(user_id, title, content=content, due_at=due_at)
    detail = render_todo_detail(todo)
    return CommandResult.ok(
        f"已创建待办：{title}",
        visible_outputs=[f"✅ 已创建待办\n{detail}"],
        context_outputs=[f"已创建待办 {detail}"],
        data={
            "todo_id": todo.id,
            "title": todo.title,
            "status": todo.status,
            "due_at": todo.due_at.isoformat() if todo.due_at else None,
        },
    )


@command_executor.handler("查询待办")
async def execute_query_todo(params: CommandParams, context: CommandExecutionContext) -> CommandResult:
    """查询自己的待办列表。"""

    user_id = _require_user_id(context)
    if user_id is None:
        return CommandResult.fail("缺少用户 ID，无法查询待办。")

    try:
        status, title = resolve_query_status(params.get_value("状态", "status"))
    except ValueError as error:
        return CommandResult.fail(str(error))

    todos = await Todo.list_for_owner(user_id, status=status)
    # 排序：待处理优先、按截止时间升序（无截止时间排后）、再按创建时间。
    todos.sort(
        key=lambda item: (
            item.status != TodoStatus.pending,
            item.due_at is None,
            item.due_at or datetime.max,
            item.id,
        )
    )
    output = render_todo_list(title, todos)
    return CommandResult.ok(
        f"已查询待办，共 {len(todos)} 条。",
        visible_outputs=[output],
        context_outputs=[output],
        data={
            "count": len(todos),
            "status": status.value if status else "all",
            "todos": [
                {
                    "todo_id": todo.id,
                    "title": todo.title,
                    "status": todo.status,
                    "due_at": todo.due_at.isoformat() if todo.due_at else None,
                }
                for todo in todos
            ],
        },
    )


@command_executor.handler("完成待办")
async def execute_complete_todo(params: CommandParams, context: CommandExecutionContext) -> CommandResult:
    """把指定待办标记为已完成。"""

    user_id = _require_user_id(context)
    if user_id is None:
        return CommandResult.fail("缺少用户 ID，无法完成待办。")

    todo_id = _parse_todo_id(params.get_value("待办ID", "todo_id"))
    if todo_id is None:
        return CommandResult.fail("待办ID必须为数字。")

    todo = await Todo.get_owned(user_id, todo_id)
    if todo is None:
        return CommandResult.fail(f"待办[{todo_id}]不存在，或不属于您。")
    if todo.status == TodoStatus.done:
        return CommandResult.ok(
            f"待办[{todo_id}]已经是完成状态。",
            visible_outputs=[f"待办[{todo_id}]已经完成，无需重复操作。"],
        )

    updated = await todo.update(status=TodoStatus.done, completed_at=datetime.now())
    detail = render_todo_detail(updated or todo)
    return CommandResult.ok(
        f"已完成待办：{todo.title}",
        visible_outputs=[f"✅ 已完成待办\n{detail}"],
        context_outputs=[f"已完成待办 {detail}"],
        data={"todo_id": todo_id, "status": TodoStatus.done.value},
    )


@command_executor.handler("删除待办")
async def execute_delete_todo(params: CommandParams, context: CommandExecutionContext) -> CommandResult:
    """删除自己的指定待办。"""

    user_id = _require_user_id(context)
    if user_id is None:
        return CommandResult.fail("缺少用户 ID，无法删除待办。")

    todo_id = _parse_todo_id(params.get_value("待办ID", "todo_id"))
    if todo_id is None:
        return CommandResult.fail("待办ID必须为数字。")

    todo = await Todo.get_owned(user_id, todo_id)
    if todo is None:
        return CommandResult.fail(f"待办[{todo_id}]不存在，或不属于您。")

    title = todo.title
    await Todo.filter(id=todo_id, owner_user_id=user_id).delete()
    return CommandResult.ok(
        f"已删除待办：{title}",
        visible_outputs=[f"🗑️ 已删除待办[{todo_id}]：{title}"],
        context_outputs=[f"已删除待办[{todo_id}] {title}"],
        data={"todo_id": todo_id},
    )


def _parse_todo_id(raw: object) -> int | None:
    """把待办 ID 参数解析成整数。

    Args:
        raw: 原始参数值，可能是整数或字符串。

    Returns:
        int | None: 解析出的待办 ID；无法解析时返回 ``None``。
    """

    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    text = normalize_text(raw)
    if not text.lstrip("-").isdigit():
        return None
    return int(text)
