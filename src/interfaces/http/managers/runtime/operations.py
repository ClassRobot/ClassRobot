from __future__ import annotations

import re
import sys
import json
import time
import shutil
import asyncio
from typing import Any
from uuid import uuid4
from pathlib import Path
from datetime import datetime

from nonebot_plugin_orm import Model
from sqlalchemy.schema import CreateTable
from src.core.llm.config import plugin_config
from src.platform.config import config_dir, project_root

from . import status
from .. import audit
from ..catalog import skills, prompts
from ..security import ManagerSession

MANAGER_FRONTEND_ROOT = project_root / "website" / "managers"
AUTOMATION_SCRIPT_PATH = config_dir / "manager_automation_scripts.json"
TERMINAL_OUTPUT_LIMIT = 16000
DEFAULT_COMMAND_TIMEOUT = 300
MAX_COMMAND_TIMEOUT = 600
SCRIPT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{1,63}$")


async def _check_config() -> dict[str, Any]:
    """执行配置健康检查动作。"""
    return await status.get_status(["runtime", "paths", "models", "cos", "ragflow"])


async def _check_database() -> dict[str, Any]:
    """执行数据库健康检查动作。"""
    return await status.check_database()


async def _validate_prompts() -> dict[str, Any]:
    """执行 Prompt 校验动作。"""
    return prompts.validate_all_prompts()


async def _reload_skills() -> dict[str, Any]:
    """执行 Skill 重载动作。"""
    return skills.reload_skills()


async def _test_models() -> dict[str, Any]:
    """逐个测试当前模型配置。"""
    from ..catalog.llm_models import test_model

    results = []
    for config in plugin_config.llm_configs:
        try:
            results.append(await test_model(config.name))
        except Exception as error:  # noqa: BLE001
            results.append({"ok": False, "name": config.name, "message": str(error)})
    return {"items": results, "ok": all(item.get("ok") for item in results) if results else False}


async def _generate_sql() -> dict[str, Any]:
    """根据 ORM 元数据生成建表 SQL 预览文件。"""
    import src.models  # noqa: F401

    output_path = config_dir / "generated_sql_statements.sql"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    statements = [str(CreateTable(table).compile()) for table in Model.metadata.sorted_tables]
    output_path.write_text(";\n\n".join(statements) + ";\n", "utf-8")
    return {
        "path": str(output_path),
        "statement_count": len(statements),
    }


async def _run_unit_tests() -> dict[str, Any]:
    """运行管理端后端测试命令。"""
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
    """列出管理端预置运维动作。

    Returns:
        dict[str, Any]: 动作 ID、标题和风险级别列表。
    """
    return {
        "items": [
            {"action_id": action_id, "title": item["title"], "risk": item["risk"]}
            for action_id, item in ACTION_REGISTRY.items()
        ]
    }


def _command_available(command: list[str]) -> bool:
    """判断命令行程序是否在当前环境可执行。"""
    executable = command[0]
    if executable == sys.executable:
        return True
    return shutil.which(executable) is not None


def list_terminal_commands() -> dict[str, Any]:
    """列出允许直接运行的终端命令模板。

    Returns:
        dict[str, Any]: 终端命令列表及可用性信息。
    """
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


def _now_text() -> str:
    """返回秒级 ISO 时间字符串。"""
    return datetime.now().isoformat(timespec="seconds")


def _normalize_timeout(value: Any) -> int:
    """把超时值限制在允许范围内。"""
    try:
        timeout = int(value)
    except (TypeError, ValueError):
        timeout = DEFAULT_COMMAND_TIMEOUT
    return min(max(timeout, 1), MAX_COMMAND_TIMEOUT)


def _resolve_command_cwd(cwd: str | None) -> Path:
    """解析并校验命令执行目录。

    Args:
        cwd: 前端提交的工作目录。

    Returns:
        Path: 可用的工作目录路径。

    Raises:
        ValueError: 当目录不存在或不是文件夹时抛出。
    """
    if not cwd:
        return project_root
    target = Path(cwd).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        raise ValueError(f"Working directory does not exist: {target}")
    return target


def _unquote_shell_arg(value: str) -> str:
    """去掉包裹参数的对称引号。"""
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def _resolve_cd_target(raw_target: str, cwd: Path) -> Path:
    """解析内建 ``cd`` 命令的目标目录。"""
    target_text = _unquote_shell_arg(raw_target.strip() or str(project_root))
    target = Path(target_text).expanduser()
    if not target.is_absolute():
        target = cwd / target
    target = target.resolve()
    if not target.exists() or not target.is_dir():
        raise ValueError(f"Working directory does not exist: {target}")
    return target


def _handle_terminal_builtin(command: str, cwd: Path) -> dict[str, Any] | None:
    """处理 ``pwd`` / ``cd`` 这类内建终端命令。"""
    stripped = command.strip()
    lowered = stripped.lower()
    if lowered in {"pwd", "cd"}:
        return {
            "exit_code": 0,
            "duration_ms": 0,
            "timed_out": False,
            "stdout": f"{cwd}\n",
            "stderr": "",
            "cwd": str(cwd),
        }
    if lowered.startswith("cd "):
        target_text = stripped[3:].strip()
        if target_text.lower().startswith("/d "):
            target_text = target_text[3:].strip()
        target = _resolve_cd_target(target_text, cwd)
        return {
            "exit_code": 0,
            "duration_ms": 0,
            "timed_out": False,
            "stdout": f"{target}\n",
            "stderr": "",
            "cwd": str(target),
        }
    return None


async def _run_shell_command(command: str, *, cwd: Path, timeout: int) -> dict[str, Any]:
    """通过系统 shell 执行任意命令字符串。

    Args:
        command: 原始命令字符串。
        cwd: 工作目录。
        timeout: 超时秒数。

    Returns:
        dict[str, Any]: 退出码、耗时、超时标记和标准输出结果。
    """
    started = time.perf_counter()
    if sys.platform == "win32":
        shell_executable = shutil.which("pwsh") or shutil.which("powershell")
        if shell_executable:
            powershell_command = f"& {command}" if command.lstrip().startswith(("'", '"')) else command
            process = await asyncio.create_subprocess_exec(
                shell_executable,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                powershell_command,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
    else:
        process = await asyncio.create_subprocess_shell(
            command,
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


async def _run_command(command: list[str], *, cwd, timeout: int) -> dict[str, Any]:
    """以参数数组形式执行命令。

    Args:
        command: 已拆分的可执行命令数组。
        cwd: 工作目录。
        timeout: 超时秒数。

    Returns:
        dict[str, Any]: 退出码、耗时、超时标记和标准输出结果。
    """
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
    """运行预置终端命令。

    Args:
        command_id: 预置命令 ID。
        session: 当前管理端会话，可选。

    Returns:
        dict[str, Any]: 执行结果。

        Raises:
            KeyError: 当命令 ID 不存在时抛出。
    """
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


async def execute_terminal_command(
    command: str,
    *,
    cwd: str | None = None,
    timeout: int = DEFAULT_COMMAND_TIMEOUT,
    session: ManagerSession | None = None,
    action: str = "manual",
    event_type: str = "terminal",
) -> dict[str, Any]:
    """执行前端输入的任意终端命令。

    Args:
        command: 原始命令字符串。
        cwd: 可选工作目录。
        timeout: 可选超时秒数。
        session: 当前管理端会话，可选。
        action: 审计日志中记录的动作名。
        event_type: 审计日志中的事件分类。

    Returns:
        dict[str, Any]: 执行结果。

    Raises:
        ValueError: 当命令为空或工作目录非法时抛出。
    """
    stripped = command.strip()
    if not stripped:
        raise ValueError("Command is required")
    working_dir = _resolve_command_cwd(cwd)
    safe_timeout = _normalize_timeout(timeout)

    try:
        execution = _handle_terminal_builtin(stripped, working_dir)
        if execution is None:
            execution = await _run_shell_command(stripped, cwd=working_dir, timeout=safe_timeout)
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
        event_type,
        action,
        status_text,
        detail={
            "exit_code": execution["exit_code"],
            "duration_ms": execution["duration_ms"],
            "timed_out": execution["timed_out"],
            "cwd": execution.get("cwd", str(working_dir)),
            "command": stripped,
        },
        session=session,
    )
    return {
        "command_id": action,
        "status": status_text,
        "exit_code": execution["exit_code"],
        "duration_ms": execution["duration_ms"],
        "timed_out": execution["timed_out"],
        "error": error,
        "stdout": execution["stdout"],
        "stderr": execution["stderr"],
        "cwd": execution.get("cwd", str(working_dir)),
        "command": stripped,
    }


def _load_automation_scripts() -> list[dict[str, Any]]:
    """从磁盘读取自动化脚本库。"""
    if not AUTOMATION_SCRIPT_PATH.exists():
        return []
    try:
        payload = json.loads(AUTOMATION_SCRIPT_PATH.read_text("utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _save_automation_scripts(items: list[dict[str, Any]]) -> None:
    """把自动化脚本库写回磁盘。"""
    AUTOMATION_SCRIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTOMATION_SCRIPT_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        "utf-8",
    )


def _normalize_script_id(value: str | None) -> str:
    """校验并标准化脚本 ID。"""
    script_id = (value or f"script_{uuid4().hex[:10]}").strip()
    if not SCRIPT_ID_PATTERN.match(script_id):
        raise ValueError("Script id must use 2-64 letters, numbers, dots, underscores, or hyphens")
    return script_id


def _script_payload(payload: dict[str, Any], *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    """标准化自动化脚本 payload。

    Args:
        payload: 前端提交的新脚本或更新数据。
        existing: 旧脚本数据，可选。

    Returns:
        dict[str, Any]: 标准化后的脚本对象。

    Raises:
        ValueError: 当脚本 ID、标题、命令、风险级别或工作目录不合法时抛出。
    """
    current = dict(existing or {})
    now = _now_text()
    script_id = _normalize_script_id(str(payload.get("id") or current.get("id") or ""))
    title = str(payload.get("title", current.get("title", ""))).strip()
    command = str(payload.get("command", current.get("command", ""))).strip()
    if not title:
        raise ValueError("Script title is required")
    if not command:
        raise ValueError("Script command is required")

    risk = str(payload.get("risk", current.get("risk", "medium"))).strip() or "medium"
    if risk not in {"low", "medium"}:
        raise ValueError("Script risk must be low or medium")

    cwd_value = payload.get("cwd", current.get("cwd"))
    cwd_path = _resolve_command_cwd(str(cwd_value) if cwd_value else None)
    return {
        "id": script_id,
        "title": title,
        "description": str(payload.get("description", current.get("description", ""))).strip(),
        "command": command,
        "cwd": str(cwd_path),
        "risk": risk,
        "timeout": _normalize_timeout(payload.get("timeout", current.get("timeout", DEFAULT_COMMAND_TIMEOUT))),
        "enabled": bool(payload.get("enabled", current.get("enabled", True))),
        "created_at": current.get("created_at") or now,
        "updated_at": now,
    }


def list_automation_scripts() -> dict[str, Any]:
    """列出脚本库中的自动化脚本。"""
    items = sorted(_load_automation_scripts(), key=lambda item: item.get("updated_at", ""), reverse=True)
    return {"items": items, "total": len(items), "path": str(AUTOMATION_SCRIPT_PATH)}


def create_automation_script(payload: dict[str, Any], *, session: ManagerSession | None = None) -> dict[str, Any]:
    """创建新的自动化脚本。

    Args:
        payload: 前端提交的脚本数据。
        session: 当前管理端会话，可选。

    Returns:
        dict[str, Any]: 新创建的脚本对象。

    Raises:
        ValueError: 当脚本 ID 已存在或字段不合法时抛出。
    """
    items = _load_automation_scripts()
    script = _script_payload(payload)
    if any(item.get("id") == script["id"] for item in items):
        raise ValueError("Script id already exists")
    items.append(script)
    _save_automation_scripts(items)
    audit.log_event("script", "create_script", "completed", detail={"id": script["id"]}, session=session)
    return script


def update_automation_script(
    script_id: str,
    payload: dict[str, Any],
    *,
    session: ManagerSession | None = None,
) -> dict[str, Any]:
    """更新现有自动化脚本。

    Args:
        script_id: 脚本 ID。
        payload: 需要更新的字段。
        session: 当前管理端会话，可选。

    Returns:
        dict[str, Any]: 更新后的脚本对象。

    Raises:
        KeyError: 当脚本不存在时抛出。
        ValueError: 当更新字段不合法时抛出。
    """
    items = _load_automation_scripts()
    for index, item in enumerate(items):
        if item.get("id") == script_id:
            updated = _script_payload({"id": script_id, **payload}, existing=item)
            items[index] = updated
            _save_automation_scripts(items)
            audit.log_event("script", "update_script", "completed", detail={"id": script_id}, session=session)
            return updated
    raise KeyError(script_id)


def delete_automation_script(script_id: str, *, session: ManagerSession | None = None) -> dict[str, Any]:
    """删除自动化脚本。

    Args:
        script_id: 脚本 ID。
        session: 当前管理端会话，可选。

    Returns:
        dict[str, Any]: 删除结果。

    Raises:
        KeyError: 当脚本不存在时抛出。
    """
    items = _load_automation_scripts()
    next_items = [item for item in items if item.get("id") != script_id]
    if len(next_items) == len(items):
        raise KeyError(script_id)
    _save_automation_scripts(next_items)
    audit.log_event("script", "delete_script", "completed", detail={"id": script_id}, session=session)
    return {"deleted": True, "id": script_id}


async def run_automation_script(script_id: str, *, session: ManagerSession | None = None) -> dict[str, Any]:
    """执行脚本库中的自动化脚本。

    Args:
        script_id: 脚本 ID。
        session: 当前管理端会话，可选。

    Returns:
        dict[str, Any]: 脚本执行结果。

    Raises:
        KeyError: 当脚本不存在时抛出。
        ValueError: 当脚本被禁用时抛出。
    """
    script = next((item for item in _load_automation_scripts() if item.get("id") == script_id), None)
    if script is None:
        raise KeyError(script_id)
    if not script.get("enabled", True):
        raise ValueError("Script is disabled")
    return await execute_terminal_command(
        str(script["command"]),
        cwd=str(script.get("cwd") or project_root),
        timeout=_normalize_timeout(script.get("timeout")),
        session=session,
        action=script_id,
        event_type="script",
    )


async def run_action(
    action_id: str,
    *,
    session: ManagerSession | None = None,
) -> dict[str, Any]:
    """执行预置运维动作。

    Args:
        action_id: 动作 ID。
        session: 当前管理端会话，可选。

    Returns:
        dict[str, Any]: 动作执行结果。

    Raises:
        KeyError: 当动作不存在时抛出。
    """
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
