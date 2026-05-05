from __future__ import annotations

import hashlib

from ..spec import CommandSpec


def command_spec_to_tool_schema(spec: CommandSpec) -> dict | None:
    """Render a command spec into an OpenAI-compatible function tool schema."""

    if not spec.agent_callable or spec.execution_mode == "disabled":
        return None

    properties: dict[str, dict] = {}
    required: list[str] = []
    for param in spec.params:
        schema: dict = {"type": param.value_type, "description": param.description or param.name}
        if param.multiple:
            schema = {
                "type": "array",
                "items": {"type": param.value_type},
                "description": param.description or param.name,
            }
        properties[param.name] = schema
        if param.required:
            required.append(param.name)

    return {
        "type": "function",
        "function": {
            "name": _safe_tool_name(spec.name),
            "description": spec.ai_description or spec.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def _safe_tool_name(command: str) -> str:
    """Build a stable function name from a human-readable command name."""

    digest = hashlib.md5(command.encode("utf-8")).hexdigest()[:10]
    return f"command_{digest}"
