from importlib import import_module
from typing import Any


def __getattr__(name: str) -> Any:
    """按需暴露管理端主路由。

    新代码应直接从领域子包导入具体 service / router / schema，避免继续
    维护旧模块别名导致目录结构失真。
    """

    if name == "router":
        manager_router = import_module(".router", __name__).router
        globals()["router"] = manager_router
        return manager_router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["router"]
