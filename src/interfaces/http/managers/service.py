from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

def now_iso() -> str:
    """返回当前时间的 ISO 字符串。

    Returns:
        str: 适合写入 JSON payload 的本地时间字符串。
    """
    return datetime.now().isoformat()


def mask_secret(value: Any) -> Any:
    """对敏感值做脱敏展示。

    Args:
        value: 原始配置值，可能是字符串、数字或 ``None``。

    Returns:
        Any: 脱敏后的值；空值保持原样，短字符串统一返回 ``***``。
    """

    if value is None:
        return None
    text = str(value)
    if not text:
        return text
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}****{text[-4:]}"


def path_payload(path: Path) -> dict[str, Any]:
    """构造路径元信息字典。

    Args:
        path: 需要检查的文件或目录路径。

    Returns:
        dict[str, Any]: 包含路径文本、是否存在、是否为目录的 payload。
    """
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
    }


def _runtime_path_map() -> dict[str, Path]:
    """按需读取管理端依赖的运行时路径。

    Returns:
        dict[str, Path]: 项目根目录及常用运行目录映射。
    """

    from src.platform.config import cache_dir, config_dir, data_dir, project_root

    return {
        "project_root": project_root,
        "data_dir": data_dir,
        "cache_dir": cache_dir,
        "config_dir": config_dir,
    }


def manager_config_path(name: str) -> Path:
    """解析管理端专用配置文件路径。

    Args:
        name: 配置文件名或相对路径。

    Returns:
        Path: 位于 ``config_dir`` 下的绝对路径。
    """
    path = _runtime_path_map()["config_dir"] / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def allowed_runtime_paths() -> dict[str, Path]:
    """返回允许在管理端中展示的运行时目录。

    Returns:
        dict[str, Path]: 目录名称到路径对象的映射。
    """
    return _runtime_path_map()


def relative_to_project(path: Path) -> str:
    """尽量把路径转换成相对项目根目录的展示形式。

    Args:
        path: 需要转换的路径。

    Returns:
        str: 项目内路径返回相对路径，项目外路径返回原始绝对路径。
    """
    project_root = _runtime_path_map()["project_root"]
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)
