from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, BaseModel

RiskLevel = Literal["low", "medium", "high"]
MCPTransport = Literal["streamable_http", "sse"]
MCPStatus = Literal["disabled", "configured", "ok", "error"]


class MCPTool(BaseModel):
    """Agent 视角下的远端 MCP tool 摘要。"""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = "medium"
    server_url: str = ""
    enabled: bool = True

    def to_prompt(self) -> str:
        """转换成 Planner 和 Loop 可消费的紧凑能力说明。"""

        params = self.input_schema.get("properties") if isinstance(self.input_schema, dict) else None
        required = self.input_schema.get("required") if isinstance(self.input_schema, dict) else None
        param_names = "无"
        if isinstance(params, dict) and params:
            required_set = set(required if isinstance(required, list) else [])
            names = [f"{name}{'*' if name in required_set else ''}" for name in params]
            param_names = "、".join(names)
        return (
            f"- {self.name}: {self.description or '远端 MCP 工具'}"
            f" | 风险={self.risk_level} | 参数={param_names} | server={self.server_url}"
        )


class MCPCallResult(BaseModel):
    """一次 MCP tool 调用的标准化结果。"""

    tool_name: str
    success: bool
    display_text: str = ""
    context_summary: str = ""
    raw_result: Any = None
    error_code: str | None = None
    risk_level: RiskLevel = "medium"


class MCPHealthStatus(BaseModel):
    """管理端展示 MCP 集成状态所需的结构化结果。"""

    status: MCPStatus
    enabled: bool
    server_url: str
    transport: MCPTransport
    tool_count: int = 0
    tools: list[str] = Field(default_factory=list)
    message: str = ""
