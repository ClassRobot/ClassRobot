from __future__ import annotations

import hashlib

from ..spec import CommandSpec


def command_spec_to_tool_schema(spec: CommandSpec) -> dict | None:
    """把 service 命令元数据渲染成 OpenAI function tool schema。"""

    if not spec.agent_callable or spec.execution_mode != "service":
        return None
    from ..executor import command_executor

    if not command_executor.has_handler(spec.name):
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
            "name": safe_tool_name(spec.name),
            "description": spec.ai_description or spec.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def safe_tool_name(command: str) -> str:
    """把项目命令名转换成稳定的 function tool 名称。

    Args:
        command: 用户可见的项目命令名。

    Returns:
        str: 可用于 OpenAI function/tool name 的安全名称。
    """

    digest = hashlib.md5(command.encode("utf-8")).hexdigest()[:10]
    return f"command_{digest}"
