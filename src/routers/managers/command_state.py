from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.commands.availability import AvailabilityState, command_availability

from .service import manager_config_path

AVAILABILITY_STATE_PATH = manager_config_path("manager_command_availability.json")
_STATE_LOADED = False


def _state_payload(state: AvailabilityState) -> dict[str, Any]:
    """把可用性状态对象序列化为可持久化的字典。

    Args:
        state: 需要序列化的可用性状态对象。

    Returns:
        dict[str, Any]: 适合写入 JSON 文件的状态数据。
    """

    return {
        "enabled": state.enabled,
        "reason": state.reason,
        "updated_at": state.updated_at.isoformat(timespec="seconds"),
    }


def _parse_state(payload: Any) -> AvailabilityState | None:
    """从 JSON 载荷恢复可用性状态对象。

    Args:
        payload: 从配置文件中读取的原始值。

    Returns:
        AvailabilityState | None: 解析成功返回状态对象，否则返回 ``None``。
    """

    if not isinstance(payload, dict):
        return None
    updated_at_text = str(payload.get("updated_at") or "").strip()
    try:
        updated_at = datetime.fromisoformat(updated_at_text) if updated_at_text else datetime.now()
    except ValueError:
        updated_at = datetime.now()
    return AvailabilityState(
        enabled=bool(payload.get("enabled", True)),
        reason=str(payload.get("reason") or ""),
        updated_at=updated_at,
    )


def load_availability_state(*, force: bool = False) -> None:
    """从磁盘加载命令和插件软开关状态。

    Args:
        force: 为 ``True`` 时忽略缓存并重新加载磁盘状态。
    """

    global _STATE_LOADED

    if _STATE_LOADED and not force:
        return

    command_availability.clear()
    if not AVAILABILITY_STATE_PATH.exists():
        _STATE_LOADED = True
        return

    try:
        payload = json.loads(AVAILABILITY_STATE_PATH.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        _STATE_LOADED = True
        return

    for command_name, raw_state in dict(payload.get("commands") or {}).items():
        state = _parse_state(raw_state)
        if state is None:
            continue
        command_availability.set_command_enabled(str(command_name), state.enabled, state.reason)

    for plugin_module, raw_state in dict(payload.get("plugins") or {}).items():
        state = _parse_state(raw_state)
        if state is None:
            continue
        command_availability.set_plugin_enabled(str(plugin_module), state.enabled, state.reason)

    _STATE_LOADED = True


def save_availability_state() -> Path:
    """把当前软开关状态写回磁盘。

    Returns:
        Path: 已写入的状态文件路径。
    """

    AVAILABILITY_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "commands": {
            command_name: _state_payload(command_availability.command_state(command_name))
            for command_name in sorted(command_availability.command_states_payload())
        },
        "plugins": {
            plugin_module: _state_payload(command_availability.plugin_state(plugin_module))
            for plugin_module in sorted(command_availability.plugin_states_payload())
        },
    }
    AVAILABILITY_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    return AVAILABILITY_STATE_PATH


def availability_payload() -> dict[str, Any]:
    """导出当前命令与插件软开关状态。

    Returns:
        dict[str, Any]: 适合接口响应的可用性状态字典。
    """

    load_availability_state()
    return {
        "commands": command_availability.command_states_payload(),
        "plugins": command_availability.plugin_states_payload(),
        "path": str(AVAILABILITY_STATE_PATH),
    }


def update_command_state(command: str, enabled: bool, reason: str = "") -> dict[str, Any]:
    """更新一条命令的软开关状态并持久化。

    Args:
        command: 主命令名称或别名。
        enabled: 是否启用该命令。
        reason: 关闭或恢复的说明。

    Returns:
        dict[str, Any]: 更新后的状态结果。

    Raises:
        ValueError: 当命令名为空时抛出。
    """

    load_availability_state()
    command_name = command.strip()
    if not command_name:
        raise ValueError("Command name is required")
    state = command_availability.set_command_enabled(command_name, enabled, reason.strip())
    save_availability_state()
    return {
        "target": "command",
        "key": command_name,
        **_state_payload(state),
    }


def update_plugin_state(plugin_module: str, enabled: bool, reason: str = "") -> dict[str, Any]:
    """更新一个插件模块的软开关状态并持久化。

    Args:
        plugin_module: 插件模块路径。
        enabled: 是否启用该插件。
        reason: 关闭或恢复的说明。

    Returns:
        dict[str, Any]: 更新后的状态结果。

    Raises:
        ValueError: 当插件模块名为空时抛出。
    """

    load_availability_state()
    module_name = plugin_module.strip()
    if not module_name:
        raise ValueError("Plugin module is required")
    state = command_availability.set_plugin_enabled(module_name, enabled, reason.strip())
    save_availability_state()
    return {
        "target": "plugin",
        "key": module_name,
        **_state_payload(state),
    }


load_availability_state()
