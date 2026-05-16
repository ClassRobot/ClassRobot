"""`utils.llm` 已降级为兼容路径，新代码请统一从 `core.llm` 导入。"""

from __future__ import annotations

import sys
from importlib import import_module
from types import ModuleType

LEGACY_SUBMODULE_ALIASES = {
    "utils.llm.config": "core.llm.config",
    "utils.llm.exceptions": "core.llm.exceptions",
    "utils.llm.functools": "core.llm.functools",
    "utils.llm.gateway": "core.llm.gateway",
    "utils.llm.message": "core.llm.message",
    "utils.llm.session": "core.llm.session",
    "utils.llm.typings": "core.llm.typings",
    "utils.llm.util": "core.llm.util",
}


def register_legacy_aliases() -> ModuleType:
    """把旧的 `utils.llm.*` 子模块映射到 `core.llm.*`。"""

    package = sys.modules[__name__]
    core_module = import_module("core.llm")
    for legacy_name, target_name in LEGACY_SUBMODULE_ALIASES.items():
        target_module = import_module(target_name)
        sys.modules[legacy_name] = target_module
        setattr(package, legacy_name.rsplit(".", 1)[-1], target_module)
    return core_module


core_module = register_legacy_aliases()

from core.llm import *  # noqa: F403

__all__ = list(getattr(core_module, "__all__", ()))
