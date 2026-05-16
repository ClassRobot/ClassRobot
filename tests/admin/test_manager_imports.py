from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_manager_package_import_does_not_register_old_module_aliases() -> None:
    """管理端包导入只暴露新架构入口，不再注册历史模块别名。"""

    project_root = Path(__file__).resolve().parents[2]
    script = """
import importlib
import src.routers.managers as managers

print("__all__", managers.__all__)
print("has_status_attr", hasattr(managers, "status"))

try:
    importlib.import_module("src.routers.managers.status")
except ModuleNotFoundError as exc:
    print("old_path_missing", exc.name)
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
    assert "has_status_attr False" in output
    assert "old_path_missing src.routers.managers.status" in output


def test_manager_interfaces_http_entry_matches_legacy_router(loaded_plugins) -> None:
    """新接口层入口应桥接到既有管理端主路由。"""

    _ = loaded_plugins
    from src.interfaces.http.manager import router as interface_router
    from src.routers.managers import router as legacy_router

    assert interface_router is legacy_router
