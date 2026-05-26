from __future__ import annotations

from typing import Any, Protocol

from pydantic import Field, BaseModel
from src.core.agent.runtime.auto_task import Param
from src.core.agent.runtime.schema import CommandObservation, ToolObservationSource, ToolObservationStatus


class ActionRequest(BaseModel):
    """Unified request for command, MCP, skill, schedule, knowledge, or delegate actions."""

    trace_id: str = ""
    source_type: ToolObservationSource = "command"
    tool_name: str
    user_goal: str = ""
    query: str = ""
    params: list[Param] = Field(default_factory=list)
    arguments: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "low"


class ActionResult(BaseModel):
    """Unified execution result before quality-gate normalization."""

    request: ActionRequest
    status: ToolObservationStatus = "succeeded"
    success: bool = True
    display_summary: str = ""
    context_summary: str = ""
    raw_result: Any = None
    error: str = ""
    next_actions: list[str] = Field(default_factory=list)

    def to_observation(self) -> CommandObservation:
        message = self.display_summary or self.context_summary or self.error
        return CommandObservation(
            trace_id=self.request.trace_id,
            command=self.request.tool_name,
            source_type=self.request.source_type,
            tool_name=self.request.tool_name,
            user_goal=self.request.user_goal,
            query=self.request.query,
            params=self.request.params,
            dispatch_type="mcp_tool" if self.request.source_type == "mcp_tool" else "command",
            status=self.status,
            success=self.success,
            message=message,
            display_summary=self.display_summary,
            context_summary=self.context_summary,
            raw_result=self.raw_result,
            next_actions=self.next_actions or (["answer"] if self.success else ["explain_failure"]),
            outputs_sent_to_user=False,
        )


class ActionExecutor(Protocol):
    """Executor protocol for the Host action bus."""

    async def execute(self, request: ActionRequest) -> ActionResult:
        ...


class ActionExecutorRegistry:
    """Small registry that routes action requests by source type."""

    def __init__(self) -> None:
        self.executors: dict[str, ActionExecutor] = {}

    def register(self, source_type: str, executor: ActionExecutor) -> None:
        self.executors[source_type] = executor

    def resolve(self, source_type: str) -> ActionExecutor | None:
        return self.executors.get(source_type)

    async def execute(self, request: ActionRequest) -> ActionResult:
        executor = self.resolve(request.source_type)
        if executor is None:
            return ActionResult(
                request=request,
                status="failed",
                success=False,
                display_summary=f"能力 `{request.source_type}` 尚未接入统一执行总线。",
                context_summary=f"Action executor missing for {request.source_type}.",
                error="executor_missing",
                next_actions=["explain_failure"],
            )
        return await executor.execute(request)
