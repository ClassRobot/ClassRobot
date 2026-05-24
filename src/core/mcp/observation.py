from __future__ import annotations

import json

from src.core.agent.runtime.schema import Param, CommandObservation

from .schema import MCPCallResult


def params_to_arguments(params: list[Param]) -> dict:
    """把 AutoTask/Workflow 参数转换为 MCP tool 参数。

    MCP tool 参数天然是 JSON object；如果模型只给了一个文本参数且内容是
    JSON object，则按对象传入，否则按 `arg1`、`arg2` 方式保留原始值。
    """

    if len(params) == 1:
        value = params[0].value.strip()
        if value.startswith("{"):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                return parsed
    return {f"arg{index}": param.value for index, param in enumerate(params, start=1)}


def mcp_result_to_observation(trace_id: str, params: list[Param], result: MCPCallResult) -> CommandObservation:
    """把 MCP 调用结果转换为现有 workflow observation。"""

    display_text = result.display_text.strip()
    context_summary = result.context_summary.strip() or display_text
    return CommandObservation(
        trace_id=trace_id,
        command=result.tool_name,
        params=params,
        dispatch_type="mcp_tool",
        success=result.success,
        message=display_text or ("MCP 工具执行完成。" if result.success else "MCP 工具执行失败。"),
        outputs=[display_text] if display_text else [],
        context_outputs=[context_summary] if context_summary else [],
        outputs_sent_to_user=False,
    )
