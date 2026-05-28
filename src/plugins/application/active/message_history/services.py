from __future__ import annotations

from src.platform.session import BaseSession
from src.platform.session.resolvers import resolve_bound_group_id
from src.plugins.library.message_history import services as history_services
from src.platform.commands import CommandResult, CommandExecutionContext, command_executor


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


async def summarize_chat_history(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行用户或当前系统群聊天统计。"""

    default_scope = "group" if context.channel_id else "user"
    try:
        request = history_services.parse_chat_statistics_request(params, default_scope=default_scope)
    except ValueError as error:
        return CommandResult.fail(str(error))

    exclude_message_id = str(context.extra.get("message_id") or "") or None
    if request.scope == "group":
        group_id = await resolve_context_group_id(context)
        if group_id is None:
            return CommandResult.fail("该统计只能在已绑定系统群组的群聊上下文中调用。")
        summary = await history_services.chat_history_store.summarize_group_messages(
            group_id,
            exclude_message_id=exclude_message_id,
            start_at=request.start_at,
            end_at=request.end_at,
        )
        output = history_services.format_group_statistics_reply(request, summary)
        return CommandResult.ok(
            "已统计当前系统群聊天记录。",
            visible_outputs=[output],
            context_outputs=[output],
            data={"scope": request.scope, "window": request.window, "group_id": group_id, **summary.dict()},
        )

    if context.user_id is None:
        return CommandResult.fail("当前会话没有可用用户身份，无法统计用户私聊记录。")
    summary = await history_services.chat_history_store.summarize_user_chat_messages(
        context.user_id,
        exclude_message_id=exclude_message_id,
        start_at=request.start_at,
        end_at=request.end_at,
    )
    output = history_services.format_user_statistics_reply(request, summary)
    return CommandResult.ok(
        "已统计当前用户私聊记录。",
        visible_outputs=[output],
        context_outputs=[output],
        data={"scope": request.scope, "window": request.window, "user_id": context.user_id, **summary.dict()},
    )


@command_executor.handler("检索群聊记录")
async def execute_query_group_history(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行统一的群聊记录检索命令。"""

    group_id = await resolve_context_group_id(context)
    if group_id is None:
        return CommandResult.fail("该命令只能在已绑定系统群组的群聊上下文中调用。")

    query = history_services.normalize_query_values(params.get("关键词", params.get("query", "")))
    output, records = await history_services.query_group_history(
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


@command_executor.handler("统计聊天记录")
async def execute_chat_statistics(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行统一聊天统计命令。"""

    return await summarize_chat_history(params, context)
