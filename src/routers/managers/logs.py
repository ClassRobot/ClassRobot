from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.config import data_dir, project_root

from .service import relative_to_project


LOG_GLOBS = ("*.log", "*.txt")
LOG_ROOTS = (
    project_root / ".codex" / "tmp",
    project_root / "logs",
    data_dir / "logs",
    project_root / "deploy",
)


def _iter_log_files() -> list[Path]:
    files: list[Path] = []
    for root in LOG_ROOTS:
        if not root.exists():
            continue
        for pattern in LOG_GLOBS:
            files.extend(path for path in root.rglob(pattern) if path.is_file())
    return sorted(set(files), key=lambda item: str(item).lower())


def _resolve_allowed_log(path_text: str) -> Path:
    target = Path(path_text).resolve()
    allowed = {path.resolve() for path in _iter_log_files()}
    if target not in allowed:
        raise PermissionError("Log path is not allowed")
    return target


def list_logs() -> dict[str, Any]:
    items = []
    for path in _iter_log_files():
        stat = path.stat()
        items.append(
            {
                "path": str(path.resolve()),
                "name": path.name,
                "relative_path": relative_to_project(path),
                "size": stat.st_size,
                "updated_at": stat.st_mtime,
            }
        )
    return {"items": items}


def read_log(path: str, *, offset: int = 0, limit: int = 500) -> dict[str, Any]:
    log_path = _resolve_allowed_log(path)
    lines = log_path.read_text("utf-8", errors="replace").splitlines()
    safe_offset = max(offset, 0)
    safe_limit = min(max(limit, 1), 2000)
    selected = lines[safe_offset : safe_offset + safe_limit]
    return {
        "path": str(log_path),
        "offset": safe_offset,
        "limit": safe_limit,
        "total_lines": len(lines),
        "lines": selected,
    }
