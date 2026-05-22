from __future__ import annotations

from typing import Any

from src.core.skills.registry import skill_registry

from ..service import relative_to_project


def list_skills() -> dict[str, Any]:
    """列出全部 Skill 清单。

    Returns:
        dict[str, Any]: Skill 列表及运行时加载状态。
    """
    items = []
    loaded_names = set(skill_registry._classes)  # noqa: SLF001
    for manifest in sorted(skill_registry.manifests.values(), key=lambda item: item.name):
        runtime_path = skill_registry.resolve_runtime_dir(manifest.root) / "runtime.py"
        items.append(
            {
                "name": manifest.name,
                "description": manifest.description,
                "path": relative_to_project(manifest.root),
                "has_runtime": runtime_path.exists(),
                "loaded": manifest.name in loaded_names,
                "updated_at": manifest.skill_file.stat().st_mtime if manifest.skill_file.exists() else None,
            }
        )
    return {"items": items}


def get_skill(name: str) -> dict[str, Any]:
    """读取单个 Skill 详情。

    Args:
        name: Skill 名称。

    Returns:
        dict[str, Any]: Skill 详情，包括 manifest 正文。

    Raises:
        KeyError: 当 Skill 不存在时抛出。
    """
    manifest = skill_registry.manifests.get(name)
    if manifest is None:
        raise KeyError(f"Skill `{name}` not found")
    runtime_path = skill_registry.resolve_runtime_dir(manifest.root) / "runtime.py"
    return {
        "name": manifest.name,
        "description": manifest.description,
        "path": relative_to_project(manifest.root),
        "skill_file": relative_to_project(manifest.skill_file),
        "has_runtime": runtime_path.exists(),
        "loaded": name in skill_registry._classes,  # noqa: SLF001
        "body": manifest.body,
    }


def reload_skills() -> dict[str, Any]:
    """重新加载 Skill 并返回最新清单。

    Returns:
        dict[str, Any]: 重载结果和最新 Skill 列表。
    """
    loaded = skill_registry.load_skills()
    return {
        "reloaded": True,
        "loaded_classes": [cls.__name__ for cls in loaded],
        "skills": list_skills()["items"],
    }
