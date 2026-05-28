from __future__ import annotations


def preview_text(text: str | None, limit: int = 180) -> str:
    """生成适合 Agent 日志和 trace 输出的短文本预览。"""

    if not text:
        return ""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."
