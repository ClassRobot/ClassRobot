from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.platform.commands import CommandExecutionContext, CommandResult, command_executor
from src.core.storage import ChatHistoryRecord, ChatHistorySummary, chat_history_store, normalize_message_text

from .presenters import render_group_history_card
from src.platform.session.resolvers import resolve_bound_group_id
from src.platform.session import BaseSession

DEFAULT_RESULT_LIMIT = 12
DEFAULT_SEARCH_WINDOW = 200


@dataclass(slots=True)
class ChatStatisticsRequest:
    """描述一次聊天统计命令请求。"""

    scope: str
    window: str
    start_at: datetime | None = None
    end_at: datetime | None = None


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


def parse_chat_statistics_request(params: dict, context: CommandExecutionContext) -> ChatStatisticsRequest:
    """把命令参数解析成受控统计请求，不从自然语言中猜测意图。"""

    scope = normalize_query_values(params.get("范围", params.get("scope", ""))).lower()
    window = normalize_query_values(params.get("时间范围", params.get("window", ""))).lower()
    if not scope:
        scope = "group" if context.channel_id else "user"
    if not window:
        window = "all"

    scope_aliases = {
        "user": "user",
        "用户": "user",
        "个人": "user",
        "我": "user",
        "私聊": "user",
        "group": "group",
        "群": "group",
        "群聊": "group",
        "当前群": "group",
        "班群": "group",
    }
    window_aliases = {
        "all": "all",
        "全部": "all",
        "当前保存的": "all",
        "today": "today",
        "今天": "today",
        "yesterday": "yesterday",
        "昨天": "yesterday",
        "week": "week",
        "this_week": "week",
        "本周": "week",
        "这周": "week",
    }
    normalized_scope = scope_aliases.get(scope)
    normalized_window = window_aliases.get(window)
    if normalized_scope is None:
        raise ValueError("范围只能是 user 或 group。")
    if normalized_window is None:
        raise ValueError("时间范围只能是 all、today、yesterday 或 week。")

    start_at, end_at = resolve_statistics_window(normalized_window)
    return ChatStatisticsRequest(
        scope=normalized_scope,
        window=normalized_window,
        start_at=start_at,
        end_at=end_at,
    )


def resolve_statistics_window(window: str) -> tuple[datetime | None, datetime | None]:
    """把受控时间范围转换为统计窗口。"""

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if window == "today":
        return today, today + timedelta(days=1)
    if window == "yesterday":
        return today - timedelta(days=1), today
    if window == "week":
        start_at = today - timedelta(days=today.weekday())
        return start_at, start_at + timedelta(days=7)
    return None, None


async def summarize_chat_history(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行用户或当前系统群聊天统计。"""

    try:
        request = parse_chat_statistics_request(params, context)
    except ValueError as error:
        return CommandResult.fail(str(error))

    exclude_message_id = str(context.extra.get("message_id") or "") or None
    if request.scope == "group":
        group_id = await resolve_context_group_id(context)
        if group_id is None:
            return CommandResult.fail("该统计只能在已绑定系统群组的群聊上下文中调用。")
        summary = await chat_history_store.summarize_group_messages(
            group_id,
            exclude_message_id=exclude_message_id,
            start_at=request.start_at,
            end_at=request.end_at,
        )
        output = format_group_statistics_reply(request, summary)
        return CommandResult.ok(
            "已统计当前系统群聊天记录。",
            visible_outputs=[output],
            context_outputs=[output],
            data={"scope": request.scope, "window": request.window, "group_id": group_id, **summary.dict()},
        )

    if context.user_id is None:
        return CommandResult.fail("当前会话没有可用用户身份，无法统计用户私聊记录。")
    summary = await chat_history_store.summarize_user_chat_messages(
        context.user_id,
        exclude_message_id=exclude_message_id,
        start_at=request.start_at,
        end_at=request.end_at,
    )
    output = format_user_statistics_reply(request, summary)
    return CommandResult.ok(
        "已统计当前用户私聊记录。",
        visible_outputs=[output],
        context_outputs=[output],
        data={"scope": request.scope, "window": request.window, "user_id": context.user_id, **summary.dict()},
    )


def statistics_window_label(request: ChatStatisticsRequest) -> str:
    """渲染统计窗口名称。"""

    labels = {
        "all": "当前保存的",
        "today": "今天",
        "yesterday": "昨天",
        "week": "本周",
    }
    return labels.get(request.window, "当前保存的")


def format_user_statistics_reply(request: ChatStatisticsRequest, summary: ChatHistorySummary) -> str:
    """渲染用户私聊统计结果。"""

    label = statistics_window_label(request)
    prefix = "按当前保存的聊天记录统计" if label == "当前保存的" else f"按{label}的聊天记录统计"
    if summary.total <= 0:
        return f"{prefix}，我们还没有可用的聊天记录。"
    return f"{prefix}，我们一共聊了 {summary.total} 条消息。其中你发了 {summary.inbound} 条，我回复了 {summary.outbound} 条。"


def format_group_statistics_reply(request: ChatStatisticsRequest, summary: ChatHistorySummary) -> str:
    """渲染当前系统群统计结果。"""

    label = statistics_window_label(request)
    prefix = "按当前保存的群聊记录统计" if label == "当前保存的" else f"按{label}的群聊记录统计"
    if summary.total <= 0:
        return f"{prefix}，这个群还没有可用的聊天记录。"
    reply = f"{prefix}，这个群一共聊了 {summary.total} 条消息。"
    if summary.distinct_user_count > 0:
        reply += f" 共有 {summary.distinct_user_count} 位成员发过言。"
    return reply


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


@command_executor.handler("统计聊天记录")
async def execute_chat_statistics(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行统一聊天统计命令。"""

    return await summarize_chat_history(params, context)
