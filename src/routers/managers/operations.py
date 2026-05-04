from __future__ import annotations

import sys
import time
import shutil
import asyncio
from typing import Any

from sqlalchemy.schema import CreateTable
from nonebot_plugin_orm import Model

from utils.config import config_dir, project_root

from . import audit, prompts, skills, status
from .security import ManagerSession

MANAGER_FRONTEND_ROOT = project_root / "website" / "managers"
TERMINAL_OUTPUT_LIMIT = 16000


async def _check_config() -> dict[str, Any]:
    return await status.get_status(["runtime", "paths", "models", "cos", "ragflow"])


async def _check_database() -> dict[str, Any]:
    return await status.check_database()


async def _validate_prompts() -> dict[str, Any]:
    return prompts.validate_all_prompts()


async def _reload_skills() -> dict[str, Any]:
    return skills.reload_skills()


async def _test_models() -> dict[str, Any]:
    from .llm_models import test_model
    from utils.llm.config import plugin_config

    results = []
    for config in plugin_config.llm_configs:
        try:
            results.append(await test_model(config.name))
        except Exception as error:  # noqa: BLE001
            results.append({"ok": False, "name": config.name, "message": str(error)})
    return {"items": results, "ok": all(item.get("ok") for item in results) if results else False}


async def _generate_sql() -> dict[str, Any]:
    import utils.models  # noqa: F401

    output_path = config_dir / "generated_sql_statements.sql"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    statements = [str(CreateTable(table).compile()) for table in Model.metadata.sorted_tables]
    output_path.write_text(";\n\n".join(statements) + ";\n", "utf-8")
    return {
        "path": str(output_path),
        "statement_count": len(statements),
    }


async def _run_unit_tests() -> dict[str, Any]:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "pytest",
        "-q",
        cwd=str(project_root),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return {
        "exit_code": process.returncode,
        "stdout": stdout.decode("utf-8", errors="replace")[-12000:],
        "stderr": stderr.decode("utf-8", errors="replace")[-12000:],
    }


ACTION_REGISTRY: dict[str, dict[str, Any]] = {
    "check_config": {"title": "检查配置", "risk": "low", "handler": _check_config},
    "check_database": {"title": "检查数据库", "risk": "low", "handler": _check_database},
    "validate_prompts": {"title": "校验 Prompt", "risk": "low", "handler": _validate_prompts},
    "reload_skills": {"title": "重载 Skill", "risk": "medium", "handler": _reload_skills},
    "test_models": {"title": "测试模型", "risk": "medium", "handler": _test_models},
    "generate_sql": {"title": "生成 SQL", "risk": "medium", "handler": _generate_sql},
    "run_unit_tests": {"title": "运行单元测试", "risk": "medium", "handler": _run_unit_tests},
}

TERMINAL_COMMANDS: dict[str, dict[str, Any]] = {
    "git_status": {
        "title": "查看 Git 状态",
        "description": "执行 git status --short，用于确认当前工作区变更。",
        "risk": "low",
        "cwd": project_root,
        "command": ["git", "status", "--short"],
        "timeout": 15,
    },
    "git_diff_stat": {
        "title": "查看 Git 变更统计",
        "description": "执行 git diff --stat，快速确认变更文件和规模。",
        "risk": "low",
        "cwd": project_root,
        "command": ["git", "diff", "--stat"],
        "timeout": 15,
    },
    "manager_api_tests": {
        "title": "运行管理端接口测试",
        "description": "执行 poetry run pytest tests/admin/test_manager_api.py -q。",
        "risk": "medium",
        "cwd": project_root,
        "command": ["poetry", "run", "pytest", "tests/admin/test_manager_api.py", "-q"],
        "timeout": 120,
    },
    "manager_frontend_build": {
        "title": "构建管理端前端",
        "description": "在 website/managers 下执行 npm run build。",
        "risk": "medium",
        "cwd": MANAGER_FRONTEND_ROOT,
        "command": ["npm", "run", "build"],
        "timeout": 120,
    },
    "list_project_root": {
        "title": "列出项目根目录",
        "description": "使用 Python 列出项目根目录下的一级文件和目录。",
        "risk": "low",
        "cwd": project_root,
        "command": [
            sys.executable,
            "-c",
            "from pathlib import Path; print('\\n'.join(sorted(p.name for p in Path('.').iterdir())))",
        ],
        "timeout": 15,
    },
}


def list_actions() -> dict[str, Any]:
    return {
        "items": [
            {"action_id": action_id, "title": item["title"], "risk": item["risk"]}
            for action_id, item in ACTION_REGISTRY.items()
        ]
    }


def _command_available(command: list[str]) -> bool:
    executable = command[0]
    if executable == sys.executable:
        return True
    return shutil.which(executable) is not None


def list_terminal_commands() -> dict[str, Any]:
    return {
        "items": [
            {
                "command_id": command_id,
                "title": item["title"],
                "description": item["description"],
                "risk": item["risk"],
                "cwd": str(item["cwd"]),
                "command": " ".join(item["command"]),
                "available": _command_available(item["command"]),
                "timeout": item["timeout"],
            }
            for command_id, item in TERMINAL_COMMANDS.items()
        ]
    }


async def _run_command(command: list[str], *, cwd, timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        timed_out = False
    except asyncio.TimeoutError:
        process.kill()
        stdout, stderr = await process.communicate()
        timed_out = True

    stdout_text = stdout.decode("utf-8", errors="replace")
    stderr_text = stderr.decode("utf-8", errors="replace")
    return {
        "exit_code": process.returncode if not timed_out else 124,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "timed_out": timed_out,
        "stdout": stdout_text[-TERMINAL_OUTPUT_LIMIT:],
        "stderr": stderr_text[-TERMINAL_OUTPUT_LIMIT:],
    }


async def run_terminal_command(
    command_id: str,
    *,
    session: ManagerSession | None = None,
) -> dict[str, Any]:
    command = TERMINAL_COMMANDS.get(command_id)
    if command is None:
        raise KeyError(command_id)
    if not _command_available(command["command"]):
        result = {
            "command_id": command_id,
            "status": "failed",
            "exit_code": 127,
            "duration_ms": 0,
            "timed_out": False,
            "error": f"Command executable not found: {command['command'][0]}",
            "stdout": "",
            "stderr": "",
            "cwd": str(command["cwd"]),
            "command": " ".join(command["command"]),
        }
        audit.log_event(
            "terminal",
            command_id,
            "failed",
            detail={"exit_code": 127, "error": result["error"]},
            session=session,
        )
        return result

    try:
        execution = await _run_command(
            command["command"],
            cwd=command["cwd"],
            timeout=command["timeout"],
        )
        status_text = "completed" if execution["exit_code"] == 0 else "failed"
        error = "命令执行超时" if execution["timed_out"] else ""
    except Exception as exc:  # noqa: BLE001
        execution = {
            "exit_code": 1,
            "duration_ms": 0,
            "timed_out": False,
            "stdout": "",
            "stderr": "",
        }
        status_text = "failed"
        error = str(exc)

    audit.log_event(
        "terminal",
        command_id,
        status_text,
        detail={
            "exit_code": execution["exit_code"],
            "duration_ms": execution["duration_ms"],
            "timed_out": execution["timed_out"],
            "cwd": str(command["cwd"]),
            "command": " ".join(command["command"]),
        },
        session=session,
    )
    return {
        "command_id": command_id,
        "status": status_text,
        "exit_code": execution["exit_code"],
        "duration_ms": execution["duration_ms"],
        "timed_out": execution["timed_out"],
        "error": error,
        "stdout": execution["stdout"],
        "stderr": execution["stderr"],
        "cwd": str(command["cwd"]),
        "command": " ".join(command["command"]),
    }


async def run_action(
    action_id: str,
    *,
    session: ManagerSession | None = None,
) -> dict[str, Any]:
    action = ACTION_REGISTRY.get(action_id)
    if action is None:
        raise KeyError(action_id)

    started = time.perf_counter()
    try:
        result = dict(await action["handler"]())
        status_text = "completed"
        exit_code = result.pop("exit_code", 0)
        error = ""
    except Exception as exc:  # noqa: BLE001
        result = {}
        status_text = "failed"
        exit_code = 1
        error = str(exc)

    payload = {
        "action_id": action_id,
        "status": status_text,
        "exit_code": exit_code,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "error": error,
        "result": result,
    }
    audit.log_event(
        "operation",
        action_id,
        status_text,
        detail={
            "exit_code": exit_code,
            "duration_ms": payload["duration_ms"],
            "error": error,
        },
        session=session,
    )
    return payload
