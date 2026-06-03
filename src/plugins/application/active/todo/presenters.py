from __future__ import annotations

from src.models.models import Todo

from .schema import status_label


def render_todo_line(todo: Todo, *, index: int | None = None) -> str:
    """把单条待办渲染成一行可读文本。

    Args:
        todo: 待办对象。
        index: 可选的列表序号，从 1 开始。

    Returns:
        str: 形如 ``1. [12] 标题 | 待办 | 截止 2026-05-30 14:00 | 备注`` 的文本。
    """

    parts: list[str] = []
    prefix = f"{index}. " if index is not None else ""
    parts.append(f"{prefix}[{todo.id}] {todo.title}")
    parts.append(status_label(todo.status))
    if todo.due_at is not None:
        parts.append(f"截止 {todo.due_at.strftime('%Y-%m-%d %H:%M')}")
    if todo.content:
        parts.append(todo.content)
    return " | ".join(parts)


def render_todo_list(title: str, todos: list[Todo]) -> str:
    """把待办列表渲染成多行卡片文本。

    Args:
        title: 列表标题。
        todos: 待办对象列表。

    Returns:
        str: 标题加逐行待办；列表为空时返回友好提示。
    """

    if not todos:
        return f"{title}\n（暂无记录）"
    lines = [render_todo_line(todo, index=number) for number, todo in enumerate(todos, start=1)]
    return "\n".join([title, *lines])


def render_todo_detail(todo: Todo) -> str:
    """渲染单条待办的详情文本。"""

    return render_todo_line(todo)
