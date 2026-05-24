from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from typing import Any

from sqlalchemy import text
from nonebot import get_driver
from nonebot_plugin_orm import get_session

from src.platform.config import (
    cache_dir,
    config_dir,
    data_dir,
    prompts_dir,
    project_root,
    skill_runtime_dir,
    skills_dir,
)
from src.core.cache.config import plugin_config as cache_config
from src.core.llm.config import plugin_config as llm_config
from src.core.mcp import MCPClient
from src.core.storage.object_store import plugin_config as cos_config
from src.models import User, Files, UserBind, AgentWorkflowRun, AgentWorkflowCheckpoint

from ..service import path_payload

try:
    import psutil
except ImportError:  # pragma: no cover - 正常部署环境会提供 psutil，这里仅保留兜底逻辑。
    psutil = None  # type: ignore[assignment]


async def check_database() -> dict[str, Any]:
    """检查数据库连接和关键表计数。

    Returns:
        dict[str, Any]: 数据库状态、迁移版本和表计数结果。
    """
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
    """检查缓存连接状态。

    Returns:
        dict[str, Any]: 缓存状态和连接元信息。
    """
    payload: dict[str, Any] = {
        "status": "ok",
        "host": cache_config.cache_host,
        "port": cache_config.cache_port,
        "configured_backend": cache_config.cache_backend,
    }
    try:
        from src.core.cache import get_cache, get_cache_backend_hint, get_cache_storage_path

        async with get_cache() as cache:
            await cache.ping()
        payload["backend"] = get_cache_backend_hint()
        payload["path"] = str(get_cache_storage_path())
        if payload["backend"] == "local":
            payload["local_path"] = payload["path"]
    except Exception as error:  # noqa: BLE001
        payload["status"] = "warning"
        payload["message"] = str(error)
    return payload


def check_paths() -> dict[str, Any]:
    """返回关键运行时目录的存在状态。

    Returns:
        dict[str, Any]: 目录名到路径元信息的映射。
    """
    return {
        "project_root": path_payload(project_root),
        "data_dir": path_payload(data_dir),
        "cache_dir": path_payload(cache_dir),
        "config_dir": path_payload(config_dir),
        "prompts_dir": path_payload(prompts_dir),
        "skill_resources_dir": path_payload(skills_dir),
        "skill_runtime_dir": path_payload(skill_runtime_dir),
    }


def check_models() -> dict[str, Any]:
    """汇总当前模型配置状态。

    Returns:
        dict[str, Any]: 模型数量、超时和名称等概要信息。
    """
    configs = llm_config.llm_configs
    return {
        "status": "ok" if configs else "not_configured",
        "configured": len(configs),
        "timeout": llm_config.llm_timeout,
        "names": [config.name for config in configs],
    }


def check_cos() -> dict[str, Any]:
    """检查对象存储配置状态。

    Returns:
        dict[str, Any]: COS 基本配置和是否已配置的结果。
    """
    configured = bool(cos_config)
    return {
        "status": "configured" if configured else "not_configured",
        "region": cos_config.region,
        "bucket": cos_config.bucket,
        "scheme": cos_config.scheme,
    }


def check_ragflow() -> dict[str, Any]:
    """检查 Ragflow 集成配置状态。

    Returns:
        dict[str, Any]: Ragflow URL、密钥存在性和状态信息。
    """
    config = get_driver().config
    ragflow_url = getattr(config, "ragflow_url", None)
    ragflow_key = getattr(config, "ragflow_key", None)
    return {
        "status": "configured" if ragflow_url and ragflow_key else "not_configured",
        "url": ragflow_url,
        "has_key": bool(ragflow_key),
    }


async def check_mcp() -> dict[str, Any]:
    """检查 MCP Client 配置和远端工具目录状态。"""

    status = await MCPClient().health_check()
    return status.dict()


def check_runtime() -> dict[str, Any]:
    """返回 Python 和 NoneBot 运行时基础信息。

    Returns:
        dict[str, Any]: 运行环境、驱动、监听地址等信息。
    """
    driver = get_driver()
    return {
        "status": "ok",
        "python_version": sys.version.split()[0],
        "driver": str(driver.config.driver),
        "environment": getattr(driver.config, "environment", None),
        "host": getattr(driver.config, "host", None),
        "port": getattr(driver.config, "port", None),
    }


def _bytes_payload(value: int | float) -> int:
    """把 psutil 数值统一转换为整数。

    Args:
        value: 原始数值。

    Returns:
        int: 适合 JSON 序列化的整数字节数。
    """
    return int(value)


def _disk_items() -> list[dict[str, Any]]:
    """收集磁盘占用信息。

    Returns:
        list[dict[str, Any]]: 每个可见分区的容量、剩余空间和占用率。
    """
    if psutil is None:
        total, used, free = __import__("shutil").disk_usage(project_root)
        percent = round((used / total) * 100, 2) if total else 0
        return [
            {
                "device": str(project_root.anchor or project_root),
                "mountpoint": str(project_root.anchor or project_root),
                "fstype": "unknown",
                "total": total,
                "used": used,
                "free": free,
                "percent": percent,
            }
        ]

    items = []
    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except (PermissionError, OSError):
            continue
        items.append(
            {
                "device": partition.device,
                "mountpoint": partition.mountpoint,
                "fstype": partition.fstype,
                "total": _bytes_payload(usage.total),
                "used": _bytes_payload(usage.used),
                "free": _bytes_payload(usage.free),
                "percent": round(float(usage.percent), 2),
            }
        )
    return items


def check_system_metrics() -> dict[str, Any]:
    """收集系统资源和当前进程指标。

    Returns:
        dict[str, Any]: CPU、内存、磁盘和当前进程监控结果。
    """
    if psutil is None:
        disks = _disk_items()
        return {
            "status": "warning",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "message": "psutil is not installed; only disk usage is available.",
            "cpu": {"percent": None, "count": os.cpu_count(), "load_average": None},
            "memory": None,
            "swap": None,
            "disks": disks,
            "process": None,
        }

    cpu_percent = psutil.cpu_percent(interval=0)
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    process = psutil.Process(os.getpid())
    with process.oneshot():
        process_payload = {
            "pid": process.pid,
            "cpu_percent": process.cpu_percent(interval=0),
            "memory_rss": _bytes_payload(process.memory_info().rss),
            "memory_percent": round(float(process.memory_percent()), 2),
            "threads": process.num_threads(),
            "started_at": datetime.fromtimestamp(process.create_time()).isoformat(timespec="seconds"),
            "uptime_seconds": round(time.time() - process.create_time()),
        }

    load_average = None
    if hasattr(os, "getloadavg"):
        try:
            load_average = list(os.getloadavg())
        except OSError:
            load_average = None

    disks = _disk_items()
    max_disk_percent = max((item["percent"] for item in disks), default=0)
    status_text = "ok"
    if cpu_percent >= 95 or memory.percent >= 95 or max_disk_percent >= 95:
        status_text = "error"
    elif cpu_percent >= 80 or memory.percent >= 80 or max_disk_percent >= 85:
        status_text = "warning"

    return {
        "status": status_text,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "cpu": {
            "percent": round(float(cpu_percent), 2),
            "count": psutil.cpu_count(logical=True),
            "physical_count": psutil.cpu_count(logical=False),
            "load_average": load_average,
        },
        "memory": {
            "total": _bytes_payload(memory.total),
            "available": _bytes_payload(memory.available),
            "used": _bytes_payload(memory.used),
            "free": _bytes_payload(memory.free),
            "percent": round(float(memory.percent), 2),
        },
        "swap": {
            "total": _bytes_payload(swap.total),
            "used": _bytes_payload(swap.used),
            "free": _bytes_payload(swap.free),
            "percent": round(float(swap.percent), 2),
        },
        "disks": disks,
        "process": process_payload,
    }


async def get_status(targets: list[str] | None = None) -> dict[str, Any]:
    """按需执行状态检查。

    Args:
        targets: 需要执行的状态分组名称列表；为空时执行全部检查。

    Returns:
        dict[str, Any]: 已执行分组的状态结果集合。
    """
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
    if all_targets or "mcp" in selected:
        payload["mcp"] = await check_mcp()
    if all_targets or "system" in selected:
        payload["system"] = check_system_metrics()

    return payload
