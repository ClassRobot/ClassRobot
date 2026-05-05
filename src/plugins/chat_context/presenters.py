from __future__ import annotations

from utils.storage import ChatHistoryRecord
from utils.tools import StringCard


def render_group_history_card(
    *,
    query: str | None,
    records: list[ChatHistoryRecord],
) -> str:
    """将群聊检索结果渲染为文本卡片。

    Args:
        query: 当前检索关键词。
        records: 命中的消息记录列表。

    Returns:
        str: 渲染后的群聊检索结果文本。
    """

    title = "系统群记录检索"
    if query:
        title += f" | {query}"

    card = StringCard(title)
    if not records:
        card.text("当前系统群暂无可用历史消息。")
        return card.render()

    for record in records:
        text = record.display_text
        if len(text) > 120:
            text = text[:117] + "..."
        card.text(f"[{record.created_at.strftime('%H:%M:%S')}] {record.user_name}: {text}")
    return card.render()
