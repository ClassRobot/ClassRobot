from __future__ import annotations

import sys
from typing import Any

from sqlalchemy import text
from nonebot import get_driver
from nonebot_plugin_orm import get_session

from utils.config import cache_dir, config_dir, data_dir, prompts_dir, project_root, skills_dir
from utils.cache.config import plugin_config as cache_config
from utils.llm.config import plugin_config as llm_config
from utils.tools.cos.config import plugin_config as cos_config
from utils.models import User, Files, UserBind, AgentWorkflowRun, AgentWorkflowCheckpoint

from .service import path_payload


async def check_database() -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "ok", "tables": {}}
    try:
        async with get_session() as session:
            version = await session.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
            payload["alembic_version"] = version
        for model in (User, UserBind, Files, AgentWorkflowRun, AgentWorkflowCheckpoint):
            payload["tables"][model.__tablename__] = await model.filter().count()
    except Exception as error:  # noqa: BLE001
        payload["status"] = "error"
        payload["message"] = str(error)
    return payload


async def check_cache() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "ok",
        "host": cache_config.cache_host,
        "port": cache_config.cache_port,
    }
    try:
        from utils.cache import get_cache

        async with get_cache() as cache:
            await cache.ping()
    except Exception as error:  # noqa: BLE001
        payload["status"] = "warning"
        payload["message"] = str(error)
    return payload


def check_paths() -> dict[str, Any]:
    return {
        "project_root": path_payload(project_root),
        "data_dir": path_payload(data_dir),
        "cache_dir": path_payload(cache_dir),
        "config_dir": path_payload(config_dir),
        "prompts_dir": path_payload(prompts_dir),
        "skills_dir": path_payload(skills_dir),
    }


def check_models() -> dict[str, Any]:
    configs = llm_config.llm_configs
    return {
        "status": "ok" if configs else "not_configured",
        "configured": len(configs),
        "timeout": llm_config.llm_timeout,
        "names": [config.name for config in configs],
    }


def check_cos() -> dict[str, Any]:
    configured = bool(cos_config)
    return {
        "status": "configured" if configured else "not_configured",
        "region": cos_config.region,
        "bucket": cos_config.bucket,
        "scheme": cos_config.scheme,
    }


def check_ragflow() -> dict[str, Any]:
    config = get_driver().config
    ragflow_url = getattr(config, "ragflow_url", None)
    ragflow_key = getattr(config, "ragflow_key", None)
    return {
        "status": "configured" if ragflow_url and ragflow_key else "not_configured",
        "url": ragflow_url,
        "has_key": bool(ragflow_key),
    }


def check_runtime() -> dict[str, Any]:
    driver = get_driver()
    return {
        "status": "ok",
        "python_version": sys.version.split()[0],
        "driver": str(driver.config.driver),
        "environment": getattr(driver.config, "environment", None),
        "host": getattr(driver.config, "host", None),
        "port": getattr(driver.config, "port", None),
    }


async def get_status(targets: list[str] | None = None) -> dict[str, Any]:
    selected = set(targets or [])
    all_targets = not selected
    payload: dict[str, Any] = {}

    if all_targets or "runtime" in selected:
        payload["runtime"] = check_runtime()
    if all_targets or "database" in selected:
        payload["database"] = await check_database()
    if all_targets or "cache" in selected:
        payload["cache"] = await check_cache()
    if all_targets or "paths" in selected:
        payload["paths"] = check_paths()
    if all_targets or "models" in selected:
        payload["models"] = check_models()
    if all_targets or "cos" in selected:
        payload["cos"] = check_cos()
    if all_targets or "ragflow" in selected:
        payload["ragflow"] = check_ragflow()

    return payload
