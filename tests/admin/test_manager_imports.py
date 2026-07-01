from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path


def test_manager_interface_imports_stay_light_before_nonebot_init() -> None:
    """接口层包与轻量模块导入不应提前触发管理端初始化副作用。"""

    project_root = Path(__file__).resolve().parents[2]
    script = """
import importlib
import src.interfaces.http.managers as managers

print("__all__", managers.__all__)
print("exports_router", "router" in managers.__all__)

for module_name in (
    "src.interfaces.http.managers.schemas",
    "src.interfaces.http.managers.service",
):
    module = importlib.import_module(module_name)
    print("imported", module.__name__)

for old_module in (
    "src.routers.path",
    "src.managers",
    "src.features",
    "src.others",
    "src.agents",
):
    try:
        importlib.import_module(old_module)
    except ModuleNotFoundError as exc:
        print("old_path_missing", old_module, exc.name)
    else:
        raise AssertionError(f"old module should not be importable: {old_module}")
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}"

    assert result.returncode == 0, output
    assert "ClassRobot 管理后台登录令牌" not in output
    assert "NoneBot has not been initialized" not in output
    assert "__all__ ['router']" in output
    assert "exports_router True" in output
    assert "imported src.interfaces.http.managers.schemas" in output
    assert "imported src.interfaces.http.managers.service" in output
    assert "old_path_missing src.routers.path src.routers" in output
    assert "old_path_missing src.managers src.managers" in output
    assert "old_path_missing src.features src.features" in output
    assert "old_path_missing src.others src.others" in output
    assert "old_path_missing src.agents src.agents" in output
    assert not (project_root / "utils" / "storage").exists()
    assert not (project_root / "utils" / "llm").exists()
    assert not (project_root / "utils" / "skills").exists()


def test_manager_interfaces_http_entry_exposes_router(loaded_plugins) -> None:
    """接口层入口在插件加载后应暴露可挂载的管理端主路由。"""

    _ = loaded_plugins
    from src.interfaces.http.managers import router as interface_router
    from src.interfaces.http.managers.router import router as direct_router

    assert interface_router is direct_router
