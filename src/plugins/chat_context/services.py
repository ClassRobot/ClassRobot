from __future__ import annotations

from src.commands import CommandExecutionContext, CommandResult, command_executor
from utils.storage import ChatHistoryRecord, chat_history_store, normalize_message_text

from .presenters import render_group_history_card
from .resolvers import resolve_bound_group_id
from utils.session import BaseSession

DEFAULT_RESULT_LIMIT = 12
DEFAULT_SEARCH_WINDOW = 200


def normalize_query_values(value: object) -> str:
    """将命令参数统一归一化为检索关键词文本。"""

    if value is None:
        return ""
    if isinstance(value, str):
        return normalize_message_text(value)
    if isinstance(value, (list, tuple, set)):
        return normalize_message_text(" ".join(str(item) for item in value if str(item).strip()))
    return normalize_message_text(str(value))


async def query_group_history(
    *,
    group_id: str,
    query: str = "",
    exclude_message_id: str | None = None,
) -> tuple[str, list[ChatHistoryRecord]]:
    """查询指定群组的消息历史并返回渲染结果。"""

    records = await chat_history_store.search_group_messages(
        group_id,
        query,
        limit=DEFAULT_RESULT_LIMIT,
        search_window=DEFAULT_SEARCH_WINDOW,
        exclude_message_id=exclude_message_id,
    )
    return render_group_history_card(query=query or None, records=records), records


async def resolve_context_group_id(context: CommandExecutionContext) -> str | None:
    """把命令上下文解析成系统内 `Group.id`。"""

    if not context.platform or not context.channel_id:
        return None

    group_id = await resolve_bound_group_id(
        BaseSession(
            user_id=str(context.user_id or ""),
            platform=context.platform,
            platform_name=str(context.extra.get("platform_name") or ""),
            channel_id=context.channel_id,
            guild_id=context.guild_id,
        )
    )
    if group_id is None:
        return None
    return str(group_id)


@command_executor.handler("检索群聊记录")
async def execute_query_group_history(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行统一的群聊记录检索命令。"""

    group_id = await resolve_context_group_id(context)
    if group_id is None:
        return CommandResult.fail("该命令只能在已绑定系统群组的群聊上下文中调用。")

    query = normalize_query_values(params.get("关键词", params.get("query", "")))
    output, records = await query_group_history(
        group_id=group_id,
        query=query,
        exclude_message_id=str(context.extra.get("message_id") or "") or None,
    )

    if not records:
        return CommandResult.ok(
            "当前系统群暂无可用历史消息。",
            visible_outputs=[output],
            context_outputs=[output],
            data={"records": [], "query": query, "group_id": group_id},
        )

    return CommandResult.ok(
        "已检索当前系统群最近相关消息。",
        visible_outputs=[output],
        context_outputs=[output],
        data={
            "group_id": group_id,
            "query": query,
            "records": [
                {
                    "message_id": record.message_id,
                    "user_id": record.user_id,
                    "user_name": record.user_name,
                    "plain_text": record.plain_text,
                    "created_at": record.created_at.isoformat(timespec="seconds"),
                }
                for record in records
            ],
        },
    )
