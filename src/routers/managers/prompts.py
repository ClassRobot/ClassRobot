from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from jinja2 import Environment

from utils.config import config_dir, prompts_dir

from .service import relative_to_project


def _safe_prompt_path(name: str) -> Path:
    # Reject both POSIX-style and Windows-style path traversal so the
    # validation result stays consistent across Linux CI and Windows dev hosts.
    posix_name = PurePosixPath(name).name
    windows_name = PureWindowsPath(name).name
    if posix_name != name or windows_name != name or name in {"", ".", ".."}:
        raise ValueError("Prompt name must be a file name")
    file_name = name
    if not file_name.endswith(".jinja"):
        file_name = f"{file_name}.jinja"
    path = (prompts_dir / file_name).resolve()
    prompts_root = prompts_dir.resolve()
    if prompts_root != path.parent:
        raise ValueError("Prompt path is outside prompts directory")
    return path


def _validate_content(content: str) -> dict[str, Any]:
    try:
        Environment(enable_async=True).parse(content)
        return {"valid": True, "message": ""}
    except Exception as error:  # noqa: BLE001
        return {"valid": False, "message": str(error)}


def list_prompts() -> dict[str, Any]:
    items = []
    if not prompts_dir.exists():
        return {"items": items}
    for path in sorted(prompts_dir.glob("*.jinja")):
        content = path.read_text("utf-8")
        validation = _validate_content(content)
        items.append(
            {
                "name": path.name,
                "path": relative_to_project(path),
                "size": path.stat().st_size,
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                "valid": validation["valid"],
                "validation_message": validation["message"],
            }
        )
    return {"items": items}


def get_prompt(name: str) -> dict[str, Any]:
    path = _safe_prompt_path(name)
    if not path.exists():
        raise FileNotFoundError(name)
    content = path.read_text("utf-8")
    validation = _validate_content(content)
    return {
        "name": path.name,
        "path": relative_to_project(path),
        "content": content,
        "size": path.stat().st_size,
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
        "valid": validation["valid"],
        "validation_message": validation["message"],
    }


def validate_prompt(name: str) -> dict[str, Any]:
    return {key: value for key, value in get_prompt(name).items() if key != "content"}


def validate_all_prompts() -> dict[str, Any]:
    items = list_prompts()["items"]
    return {
        "valid": all(item["valid"] for item in items),
        "items": items,
    }


def update_prompt(name: str, content: str) -> dict[str, Any]:
    path = _safe_prompt_path(name)
    if not path.exists():
        raise FileNotFoundError(name)

    validation = _validate_content(content)
    if not validation["valid"]:
        return {
            "saved": False,
            "valid": False,
            "validation_message": validation["message"],
        }

    backup_dir = config_dir / "manager-backups" / "prompts"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_name = f"{path.stem}.{datetime.now().strftime('%Y%m%d%H%M%S')}.jinja"
    backup_path = backup_dir / backup_name
    shutil.copy2(path, backup_path)
    path.write_text(content, "utf-8")
    return {
        "saved": True,
        "valid": True,
        "backup_path": str(backup_path),
    }
