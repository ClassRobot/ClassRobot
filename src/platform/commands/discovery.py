from __future__ import annotations

from typing import Any

from src.platform.helper import Helper, ParamMode

from .spec import CommandSpec
from .executor import command_executor
from .registry import command_registry
from .availability import command_availability
from .renderers.tool import command_spec_to_tool_schema


def spec_to_payload(spec: CommandSpec) -> dict[str, Any]:
    """Render a command spec into a management-friendly dictionary."""

    availability = command_availability.check(spec)
    service_handler_registered = command_executor.has_handler(spec.name)
    tool_schema = command_spec_to_tool_schema(spec)
    return {
        "id": f"registry:{spec.plugin_module or 'unknown'}:{spec.name}",
        "command": spec.name,
        "aliases": sorted(spec.aliases),
        "description": spec.description,
        "roles": sorted(map(str, spec.roles)),
        "exclude_roles": sorted(map(str, spec.exclude_roles)),
        "scopes": sorted(map(str, spec.scopes)),
        "params": [
            {
                "name": param.name,
                "description": param.description,
                "mode": str(param.mode) if param.mode else None,
                "value_type": param.value_type,
                "multiple": param.multiple,
                "source_name": param.source_name,
                "required": param.required,
            }
            for param in spec.params
        ],
        "tags": sorted(spec.tags),
        "risk_level": spec.risk_level,
        "agent_callable": spec.agent_callable,
        "execution_mode": spec.execution_mode,
        "plugin_module": spec.plugin_module,
        "documented": True,
        "available": availability.available,
        "availability_reason": availability.reason,
        "service_handler_registered": service_handler_registered,
        "agent_executable": (
            availability.available
            and spec.agent_callable
            and spec.execution_mode == "service"
            and service_handler_registered
        ),
        "tool_name": tool_schema["function"]["name"] if tool_schema else None,
        "metadata_source": "command_registry",
    }


def helper_to_payload(helper: Helper) -> dict[str, Any]:
    """Render a manual helper into the same shape as registry payloads."""

    spec = command_registry.get(helper.command)
    availability = command_availability.check(spec, helper.command)
    service_handler_registered = command_executor.has_handler(helper.command)
    return {
        "id": f"helper:{helper.command}",
        "command": helper.command,
        "aliases": sorted(helper.aliases),
        "description": helper.description,
        "roles": sorted(map(str, helper.roles)),
        "exclude_roles": sorted(map(str, helper.exclude_roles)),
        "scopes": sorted(map(str, helper.display_scopes)),
        "params": [
            {
                "name": param.name,
                "description": param.description or "",
                "mode": str(param.mode) if param.mode else None,
                "value_type": "string",
                "multiple": param.mode in {ParamMode.ONE_OR_MORE, ParamMode.ZERO_OR_MORE},
                "source_name": None,
                "required": param.mode not in {ParamMode.OPTIONAL, ParamMode.ZERO_OR_MORE},
            }
            for param in helper.params
        ],
        "tags": sorted(helper.tags),
        "risk_level": "low",
        "agent_callable": False,
        "execution_mode": "matcher",
        "plugin_module": None,
        "documented": True,
        "available": availability.available,
        "availability_reason": availability.reason,
        "service_handler_registered": service_handler_registered,
        "agent_executable": (
            availability.available
            and bool(spec and spec.agent_callable)
            and bool(spec and spec.execution_mode == "service")
            and service_handler_registered
        ),
        "tool_name": None,
        "metadata_source": "helper",
    }


def registered_command_payloads() -> list[dict[str, Any]]:
    """Return all command-registry payloads in stable order."""

    return [spec_to_payload(spec) for spec in command_registry]


def registered_command_index() -> dict[str, dict[str, Any]]:
    """Build an index by command and alias from registered command specs."""

    index: dict[str, dict[str, Any]] = {}
    for payload in registered_command_payloads():
        command_names = {payload["command"], *payload.get("aliases", [])}
        for command_name in command_names:
            index[str(command_name)] = payload
    return index
