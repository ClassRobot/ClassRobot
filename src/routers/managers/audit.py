from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .security import ManagerSession
from utils.config import data_dir

AUDIT_LOG_PATH = data_dir / "logs" / "manager_audit.jsonl"
MAX_DETAIL_TEXT = 2000


def _safe_detail(value: Any) -> Any:
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
