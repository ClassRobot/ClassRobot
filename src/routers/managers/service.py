from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from utils.config import cache_dir, config_dir, data_dir, project_root


def now_iso() -> str:
    return datetime.now().isoformat()


def mask_secret(value: Any) -> Any:
    """Mask secrets while preserving empty values and non-string data."""

    if value is None:
        return None
    text = str(value)
    if not text:
        return text
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}****{text[-4:]}"


def path_payload(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
    }


def manager_config_path(name: str) -> Path:
    path = config_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def allowed_runtime_paths() -> dict[str, Path]:
    return {
        "project_root": project_root,
        "data_dir": data_dir,
        "cache_dir": cache_dir,
        "config_dir": config_dir,
    }


def relative_to_project(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)
