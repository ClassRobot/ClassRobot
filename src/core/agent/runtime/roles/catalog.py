from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, BaseModel
from src.core.agent.runtime.context import ContextPack, ContextLayer

RuntimeRoleKind = Literal[
    "conversation",
    "knowledge",
    "execution",
    "realtime_lookup",
    "workflow_supervisor",
    "reply_synthesis",
]
RuntimeRoleStatus = Literal["planned", "running", "completed", "failed", "skipped"]


class RuntimeRoleDescriptor(BaseModel):
    """Describes a Host-controlled runtime role and its context boundary."""

    name: str
    display_name: str
    kind: RuntimeRoleKind
    description: str = ""
    when_to_use: str = ""
    context_layers: list[ContextLayer] = Field(default_factory=list)
    allowed_tool_sources: list[str] = Field(default_factory=list)

    def prompt_summary(self) -> str:
        tools = ", ".join(self.allowed_tool_sources) if self.allowed_tool_sources else "none"
        return (
            f"- {self.name}: {self.description} | kind={self.kind} | "
            f"context={','.join(self.context_layers)} | tools={tools}"
        )


class RuntimeRoleDecision(BaseModel):
    """Records why the Host selected a runtime role."""

    target_role: str
    reason: str = ""
    user_goal: str = ""
    required: bool = False
    context_layers: list[ContextLayer] = Field(default_factory=list)


class RuntimeRoleResult(BaseModel):
    """Standard result returned from a runtime role to the Host."""

    role_name: str
    status: RuntimeRoleStatus = "completed"
    summary: str = ""
    observations: list[dict[str, Any]] = Field(default_factory=list)
    error: str = ""


class RuntimeRoleTraceRecord(BaseModel):
    """Auditable runtime role trace record for Host-controlled turn processing."""

    trace_id: str = ""
    source_role: str = "runtime_host"
    target_role: str
    status: RuntimeRoleStatus = "planned"
    reason: str = ""
    context_summary: str = ""
    context_layers: list[ContextLayer] = Field(default_factory=list)
    result_summary: str = ""
    error: str = ""
    created_at: datetime = Field(default_factory=datetime.now)


class RuntimeRoleCatalog(BaseModel):
    """Catalog of runtime roles visible to the Agent Host."""

    roles: list[RuntimeRoleDescriptor] = Field(default_factory=list)

    @classmethod
    def default(cls) -> "RuntimeRoleCatalog":
        return cls(
            roles=[
                RuntimeRoleDescriptor(
                    name="workflow_supervisor",
                    display_name="Workflow Supervisor Role",
                    kind="workflow_supervisor",
                    description="Routes goals, chooses capabilities, and decides whether to delegate or execute.",
                    when_to_use="Use for every non-trivial turn before tool execution.",
                    context_layers=["turn_context", "session_context", "workflow_context", "tool_state_context"],
                    allowed_tool_sources=[],
                ),
                RuntimeRoleDescriptor(
                    name="conversation",
                    display_name="Conversation Role",
                    kind="conversation",
                    description="Handles direct chat, lightweight explanations, and follow-up replies.",
                    when_to_use="Use when no tool execution is needed or the user asks about previous results.",
                    context_layers=["turn_context", "session_context", "tool_state_context"],
                ),
                RuntimeRoleDescriptor(
                    name="knowledge",
                    display_name="Knowledge Role",
                    kind="knowledge",
                    description="Retrieves local or external knowledge and summarizes source-backed answers.",
                    when_to_use="Use for school rules, files, chat history, RAG, and source-backed questions.",
                    context_layers=["turn_context", "session_context", "knowledge_context"],
                    allowed_tool_sources=["local_knowledge", "external_rag"],
                ),
                RuntimeRoleDescriptor(
                    name="realtime_lookup",
                    display_name="Realtime Lookup Role",
                    kind="realtime_lookup",
                    description="Uses realtime public external tools such as MCP web search.",
                    when_to_use="Use for news, hot topics, weather-now, and other fresh public information.",
                    context_layers=["turn_context", "tool_state_context"],
                    allowed_tool_sources=["mcp_tool"],
                ),
                RuntimeRoleDescriptor(
                    name="execution",
                    display_name="Execution Role",
                    kind="execution",
                    description="Executes approved command, MCP, skill, schedule, or delegate actions.",
                    when_to_use="Use when a TaskWorkflow contains executable steps.",
                    context_layers=["turn_context", "workflow_context", "tool_state_context"],
                    allowed_tool_sources=["command", "mcp_tool", "skill", "schedule", "delegate"],
                ),
                RuntimeRoleDescriptor(
                    name="reply_synthesis",
                    display_name="Reply Synthesis Role",
                    kind="reply_synthesis",
                    description="Turns observations, runtime role traces, and failure reasons into the final user reply.",
                    when_to_use="Use before any final user-facing response after execution or delegation.",
                    context_layers=["turn_context", "session_context", "workflow_context", "tool_state_context"],
                ),
            ]
        )

    def get(self, name: str) -> RuntimeRoleDescriptor | None:
        return next((role for role in self.roles if role.name == name), None)

    def to_prompt(self) -> str:
        return "\n".join(role.prompt_summary() for role in self.roles)

    def select_for_turn(
        self, *, context_pack: ContextPack, route: Any = None, plan: Any = None, workflow: Any = None
    ) -> list[RuntimeRoleDecision]:
        """Build deterministic Host-level role records from current turn state."""

        decisions = [
            RuntimeRoleDecision(
                target_role="workflow_supervisor",
                reason="Host supervisor evaluates the turn and keeps the decision graph auditable.",
                context_layers=["turn_context", "session_context", "workflow_context", "tool_state_context"],
                required=True,
            )
        ]
        intent = getattr(route, "intent", "") if route is not None else ""
        requires_rag = bool(getattr(route, "requires_rag", False) or getattr(plan, "requires_rag", False))
        knowledge_sources = list(getattr(route, "knowledge_sources", []) or [])
        candidate_mcp = list(getattr(plan, "candidate_mcp_tools", []) or [])
        has_steps = bool(getattr(workflow, "steps", []) if workflow is not None else [])
        if requires_rag or knowledge_sources:
            decisions.append(
                RuntimeRoleDecision(
                    target_role="knowledge",
                    reason="The turn requires controlled knowledge retrieval or source-backed context.",
                    context_layers=["turn_context", "session_context", "knowledge_context"],
                    required=True,
                )
            )
        if candidate_mcp:
            decisions.append(
                RuntimeRoleDecision(
                    target_role="realtime_lookup",
                    reason="Planner selected MCP tools for realtime or external lookup.",
                    context_layers=["turn_context", "tool_state_context"],
                    required=True,
                )
            )
        if has_steps:
            decisions.append(
                RuntimeRoleDecision(
                    target_role="execution",
                    reason="The workflow contains executable steps.",
                    context_layers=["turn_context", "workflow_context", "tool_state_context"],
                    required=True,
                )
            )
        if intent == "chat" and not has_steps:
            decisions.append(
                RuntimeRoleDecision(
                    target_role="conversation",
                    reason="The turn can be answered through conversation or prior context.",
                    context_layers=["turn_context", "session_context", "tool_state_context"],
                )
            )
        decisions.append(
            RuntimeRoleDecision(
                target_role="reply_synthesis",
                reason="Every user-visible final answer must pass through reply synthesis policy.",
                context_layers=["turn_context", "session_context", "workflow_context", "tool_state_context"],
                required=True,
            )
        )
        return decisions
