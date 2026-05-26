from __future__ import annotations

import json
from typing import Any

from src.core.agent.runtime.schema import Param, CommandObservation
from src.core.agent.runtime.observation_quality import ObservationQualityGate

from .schema import MCPCallResult


def params_to_arguments(
    params: list[Param],
    input_schema: dict[str, Any] | None = None,
    prior_observations: list[CommandObservation] | None = None,
) -> dict:
    """把 AutoTask/Workflow 参数转换为 MCP tool 参数。

    MCP tool 参数天然是 JSON object；如果模型只给了一个文本参数且内容是
    JSON object，则按对象传入，否则按 `arg1`、`arg2` 方式保留原始值。

    Args:
        params: AutoTask 或 WorkflowStep 携带的参数列表。
        input_schema: MCP tool 暴露的 JSON Schema，用于把 `arg1` 这类位置参数映射到真实字段。
        prior_observations: 同一工作流前序 MCP observation，用于补齐 session_id 等链式上下文字段。

    Returns:
        dict: 可直接传给 MCP Client 的 JSON object 参数。
    """

    raw_arguments: dict[str, Any]
    if len(params) == 1:
        value = params[0].value.strip()
        if value.startswith("{"):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                raw_arguments = parsed
                return normalize_arguments_for_schema(raw_arguments, input_schema, prior_observations)
    raw_arguments = {f"arg{index}": param.value for index, param in enumerate(params, start=1)}
    return normalize_arguments_for_schema(raw_arguments, input_schema, prior_observations)


def normalize_arguments_for_schema(
    raw_arguments: dict[str, Any],
    input_schema: dict[str, Any] | None = None,
    prior_observations: list[CommandObservation] | None = None,
) -> dict[str, Any]:
    """按 MCP tool schema 修正模型生成的参数。

    Args:
        raw_arguments: 已解析出的原始参数。
        input_schema: MCP tool 的 JSON Schema。
        prior_observations: 当前工作流前序工具结果。

    Returns:
        dict[str, Any]: 字段名尽量符合 schema 的参数。
    """

    properties = input_schema.get("properties") if isinstance(input_schema, dict) else None
    if not isinstance(properties, dict) or not properties:
        return raw_arguments

    required = input_schema.get("required")
    required_fields = [field for field in required if isinstance(field, str)] if isinstance(required, list) else []
    allowed_fields = {str(field) for field in properties}
    arguments = {key: value for key, value in raw_arguments.items() if key in allowed_fields}

    positional_items = sorted(
        ((key, value) for key, value in raw_arguments.items() if is_positional_arg_key(key)),
        key=lambda item: int(item[0][3:]) if item[0][3:].isdigit() else 0,
    )
    for _, value in positional_items:
        target_field = select_positional_target_field(value, allowed_fields, required_fields, arguments)
        if target_field:
            arguments[target_field] = value

    context_values = collect_observation_context_values(prior_observations or [])
    for field in required_fields:
        if has_argument_value(arguments.get(field)):
            continue
        context_value = context_values.get(field) or context_values.get(field.lower())
        if has_argument_value(context_value):
            arguments[field] = context_value

    return arguments


def is_positional_arg_key(key: str) -> bool:
    """判断字段名是否是 `arg1` 这类位置参数。"""

    return key.startswith("arg") and key[3:].isdigit()


def select_positional_target_field(
    value: Any,
    allowed_fields: set[str],
    required_fields: list[str],
    current_arguments: dict[str, Any],
) -> str:
    """为单个位置参数选择最合适的 schema 字段。"""

    text = str(value or "").strip()
    candidate_fields = [
        field for field in required_fields if field in allowed_fields and field not in current_arguments
    ]
    candidate_fields.extend(
        field for field in allowed_fields if field not in current_arguments and field not in candidate_fields
    )

    if text.startswith(("http://", "https://")):
        for field in candidate_fields:
            if field.lower() in {"url", "uri", "link", "href"} or "url" in field.lower():
                return field

    if len(candidate_fields) == 1:
        return candidate_fields[0]
    return ""


def collect_observation_context_values(observations: list[CommandObservation]) -> dict[str, Any]:
    """从前序 observation 中提取可复用的结构化字段。"""

    values: dict[str, Any] = {}
    for observation in observations:
        for source in (
            observation.raw_result,
            observation.message,
            observation.display_summary,
            observation.context_summary,
            observation.outputs,
            observation.context_outputs,
        ):
            merge_context_values(values, extract_values_from_payload(source))
    return values


def extract_values_from_payload(payload: Any) -> dict[str, Any]:
    """递归提取 JSON/dict/list 中的标量字段。"""

    values: dict[str, Any] = {}
    if isinstance(payload, str):
        text = payload.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return values
            return extract_values_from_payload(parsed)
        return values
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            if isinstance(value, (dict, list)):
                merge_context_values(values, extract_values_from_payload(value))
                continue
            if isinstance(value, str) and (value.strip().startswith("{") or value.strip().startswith("[")):
                merge_context_values(values, extract_values_from_payload(value))
            if has_argument_value(value):
                values[key_text] = value
                values[key_text.lower()] = value
        return values
    if isinstance(payload, list):
        for item in payload:
            merge_context_values(values, extract_values_from_payload(item))
    return values


def merge_context_values(target: dict[str, Any], source: dict[str, Any]) -> None:
    """合并上下文字段，保留最早出现的可用值。"""

    for key, value in source.items():
        if key not in target and has_argument_value(value):
            target[key] = value


def has_argument_value(value: Any) -> bool:
    """判断参数值是否可以作为有效 MCP 入参。"""

    return value is not None and str(value).strip() != ""


def mcp_result_to_observation(trace_id: str, params: list[Param], result: MCPCallResult) -> CommandObservation:
    """把 MCP 调用结果转换为现有 workflow observation。"""

    display_text = result.display_text.strip()
    context_summary = result.context_summary.strip() or display_text
    query = ""
    for param in params:
        query = ObservationQualityGate.extract_query_from_raw(param.value)
        if query:
            break
    return CommandObservation(
        trace_id=trace_id,
        command=result.tool_name,
        source_type="mcp_tool",
        tool_name=result.tool_name,
        query=query,
        params=params,
        dispatch_type="mcp_tool",
        status="succeeded" if result.success else "failed",
        success=result.success,
        relevance="unknown",
        answer_quality="unknown",
        message=display_text or ("MCP 工具执行完成。" if result.success else "MCP 工具执行失败。"),
        display_summary=display_text,
        context_summary=context_summary,
        outputs=[display_text] if display_text else [],
        context_outputs=[context_summary] if context_summary else [],
        raw_result=result.raw_result,
        next_actions=[] if result.success else ["explain_failure"],
        outputs_sent_to_user=False,
    )
