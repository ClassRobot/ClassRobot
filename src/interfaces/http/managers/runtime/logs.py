from __future__ import annotations

from pathlib import Path
from typing import Any

from src.platform.config import data_dir, project_root

from ..service import relative_to_project

LOG_GLOBS = ("*.log", "*.txt")
LOG_ROOTS = (
    project_root / ".codex" / "tmp",
    project_root / "logs",
    data_dir / "logs",
    project_root / "deploy",
)


def _iter_log_files() -> list[Path]:
    """扫描允许目录下的日志文件。

    Returns:
        list[Path]: 已去重并排序的日志文件路径列表。
    """
    files: list[Path] = []
    for root in LOG_ROOTS:
        if not root.exists():
            continue
        for pattern in LOG_GLOBS:
            files.extend(path for path in root.rglob(pattern) if path.is_file())
    return sorted(set(files), key=lambda item: str(item).lower())


def _resolve_allowed_log(path_text: str) -> Path:
    """校验请求的日志路径是否在白名单内。

    Args:
        path_text: 前端传入的日志绝对路径字符串。

    Returns:
        Path: 通过校验后的真实路径。

    Raises:
        PermissionError: 当路径不在允许集合中时抛出。
    """
    target = Path(path_text).resolve()
    allowed = {path.resolve() for path in _iter_log_files()}
    if target not in allowed:
        raise PermissionError("Log path is not allowed")
    return target


def list_logs() -> dict[str, Any]:
    """列出可查看的日志文件。

    Returns:
        dict[str, Any]: 包含日志文件元信息列表的结果。
    """
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
    """按偏移量读取日志内容。

    Args:
        path: 已允许的日志文件路径。
        offset: 起始行偏移量。
        limit: 最多读取的行数。

    Returns:
        dict[str, Any]: 包含所选行和总行数的结果。
    """
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


def tail_log(path: str, *, lines: int = 300) -> dict[str, Any]:
    """读取日志末尾若干行。

    Args:
        path: 已允许的日志文件路径。
        lines: 需要返回的尾部行数。

    Returns:
        dict[str, Any]: 包含尾部日志行和偏移量的结果。
    """
    log_path = _resolve_allowed_log(path)
    all_lines = log_path.read_text("utf-8", errors="replace").splitlines()
    safe_lines = min(max(lines, 1), 2000)
    offset = max(len(all_lines) - safe_lines, 0)
    selected = all_lines[offset:]
    return {
        "path": str(log_path),
        "offset": offset,
        "limit": safe_lines,
        "total_lines": len(all_lines),
        "lines": selected,
    }
