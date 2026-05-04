from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from jinja2 import Environment

from utils.config import config_dir, prompts_dir

from .service import relative_to_project


def _safe_prompt_path(name: str) -> Path:
    """解析并校验 Prompt 文件名。

    Args:
        name: 前端传入的 Prompt 名称。

    Returns:
        Path: 对应 Prompt 文件的绝对路径。

    Raises:
        ValueError: 当文件名为空、包含路径穿越或超出 prompts 目录时抛出。
    """
    # 同时拦截 POSIX 和 Windows 风格的路径穿越写法，确保
    # Linux 持续集成环境与 Windows 开发环境中的校验结果一致。
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
    """校验 Jinja 模板语法。

    Args:
        content: Prompt 模板原始文本。

    Returns:
        dict[str, Any]: 包含 ``valid`` 和 ``message`` 的校验结果。
    """
    try:
        Environment(enable_async=True).parse(content)
        return {"valid": True, "message": ""}
    except Exception as error:  # noqa: BLE001
        return {"valid": False, "message": str(error)}


def list_prompts() -> dict[str, Any]:
    """列出 Prompt 文件及其校验状态。

    Returns:
        dict[str, Any]: Prompt 列表结果。
    """
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
    """读取单个 Prompt 的完整内容。

    Args:
        name: Prompt 文件名或不带后缀名称。

    Returns:
        dict[str, Any]: Prompt 详情，包括内容与校验状态。

    Raises:
        FileNotFoundError: 当目标 Prompt 不存在时抛出。
        ValueError: 当 Prompt 名称非法时抛出。
    """
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
    """校验单个 Prompt，但不返回原始内容。

    Args:
        name: Prompt 文件名或不带后缀名称。

    Returns:
        dict[str, Any]: 去除 ``content`` 后的 Prompt 校验结果。
    """
    return {key: value for key, value in get_prompt(name).items() if key != "content"}


def validate_all_prompts() -> dict[str, Any]:
    """批量校验全部 Prompt。

    Returns:
        dict[str, Any]: 包含总体是否合法和每个 Prompt 结果的汇总。
    """
    items = list_prompts()["items"]
    return {
        "valid": all(item["valid"] for item in items),
        "items": items,
    }


def update_prompt(name: str, content: str) -> dict[str, Any]:
    """校验后备份并覆盖写入 Prompt 文件。

    Args:
        name: Prompt 文件名或不带后缀名称。
        content: 新的模板内容。

    Returns:
        dict[str, Any]: 保存结果；如果校验失败则返回 ``saved=False``。

    Raises:
        FileNotFoundError: 当目标 Prompt 不存在时抛出。
        ValueError: 当 Prompt 名称非法时抛出。
    """
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
