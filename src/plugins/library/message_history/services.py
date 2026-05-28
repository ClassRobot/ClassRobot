from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.core.storage import ChatHistoryRecord, ChatHistorySummary, chat_history_store, normalize_message_text

from .presenters import render_group_history_card

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


def parse_chat_statistics_request(params: dict, *, default_scope: str) -> ChatStatisticsRequest:
    """把命令参数解析成受控统计请求，不从自然语言中猜测意图。"""

    scope = normalize_query_values(params.get("范围", params.get("scope", ""))).lower()
    window = normalize_query_values(params.get("时间范围", params.get("window", ""))).lower()
    if not scope:
        scope = default_scope
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
