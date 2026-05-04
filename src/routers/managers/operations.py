from __future__ import annotations

import sys
import time
import asyncio
from typing import Any

from sqlalchemy.schema import CreateTable
from nonebot_plugin_orm import Model

from utils.config import config_dir, project_root

from . import prompts, skills, status

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


def list_actions() -> dict[str, Any]:
    return {
        "items": [
            {"action_id": action_id, "title": item["title"], "risk": item["risk"]}
            for action_id, item in ACTION_REGISTRY.items()
        ]
    }


async def run_action(action_id: str) -> dict[str, Any]:
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

    return {
        "action_id": action_id,
        "status": status_text,
        "exit_code": exit_code,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "error": error,
        "result": result,
    }
