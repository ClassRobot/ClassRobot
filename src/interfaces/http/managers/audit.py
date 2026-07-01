from __future__ import annotations

import json
from typing import Any
from pathlib import Path
from datetime import datetime

from src.platform.config import data_dir

from .security import ManagerSession

AUDIT_LOG_PATH = data_dir / "logs" / "manager_audit.jsonl"
MAX_DETAIL_TEXT = 2000


def _safe_detail(value: Any) -> Any:
    """把任意 detail 数据转换成安全可序列化的内容。

    Args:
        value: 审计详情原始值，可能是字典、列表、元组或其他对象。

    Returns:
        Any: 可写入 JSONL 的裁剪后数据。
    """
    if isinstance(value, dict):
        return {str(key): _safe_detail(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_detail(item) for item in value[:100]]
    if isinstance(value, tuple):
        return [_safe_detail(item) for item in value[:100]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > MAX_DETAIL_TEXT:
            return f"{value[:MAX_DETAIL_TEXT]}..."
        return value
    return str(value)


def log_event(
    event_type: str,
    action: str,
    status: str,
    *,
    detail: dict[str, Any] | None = None,
    session: ManagerSession | None = None,
) -> dict[str, Any]:
    """写入一条管理端审计事件。

    Args:
        event_type: 事件分类，例如 ``settings``、``users``、``terminal``。
        action: 具体动作名称。
        status: 动作结果状态。
        detail: 额外上下文信息。
        session: 当前管理端会话，可选。

    Returns:
        dict[str, Any]: 已写入文件的审计 payload。
    """
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "event_type": event_type,
        "action": action,
        "status": status,
        "actor": "local_manager",
        "session_id": session.token_hash[:12] if session is not None else None,
        "detail": _safe_detail(detail or {}),
    }
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return payload


def list_events(*, limit: int = 100, event_type: str | None = None) -> dict[str, Any]:
    """读取最近的审计事件。

    Args:
        limit: 最多返回的事件数量。
        event_type: 可选的事件分类过滤条件。

    Returns:
        dict[str, Any]: 包含事件列表、总行数和审计文件路径的结果。
    """
    safe_limit = min(max(limit, 1), 500)
    if not AUDIT_LOG_PATH.exists():
        return {"items": [], "total": 0, "path": str(AUDIT_LOG_PATH)}

    lines = AUDIT_LOG_PATH.read_text("utf-8", errors="replace").splitlines()
    items: list[dict[str, Any]] = []
    for line in reversed(lines):
        if len(items) >= safe_limit:
            break
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event_type and item.get("event_type") != event_type:
            continue
        items.append(item)

    return {
        "items": items,
        "total": len(lines),
        "path": str(AUDIT_LOG_PATH),
    }
