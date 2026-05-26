from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, BaseModel
from src.core.agent.runtime.context import ContextPack, ContextLayer

AgentKind = Literal[
    "conversation",
    "knowledge",
    "execution",
    "realtime_lookup",
    "workflow_supervisor",
    "reply_synthesis",
]
DelegationStatus = Literal["planned", "running", "completed", "failed", "skipped"]


class SpecializedAgentDescriptor(BaseModel):
    """Describes a Host-controlled specialized agent and its context boundary."""

    name: str
    display_name: str
    kind: AgentKind
    description: str = ""
    when_to_use: str = ""
    context_requirements: list[ContextLayer] = Field(default_factory=list)
    allowed_tool_sources: list[str] = Field(default_factory=list)
    permission_scope: str = "host_controlled"
    fallback_behavior: str = "return_to_host"
    allow_delegate: bool = False

    def prompt_summary(self) -> str:
        tools = ", ".join(self.allowed_tool_sources) if self.allowed_tool_sources else "none"
        return (
            f"- {self.name}: {self.description} | kind={self.kind} | "
            f"context={','.join(self.context_requirements)} | tools={tools}"
        )


class AgentDelegationDecision(BaseModel):
    """Records why the Host selected a specialized agent."""

    target_agent: str
    reason: str = ""
    user_goal: str = ""
    required: bool = False
    context_layers: list[ContextLayer] = Field(default_factory=list)


class AgentResultEnvelope(BaseModel):
    """Standard result returned from a specialized agent to the Host."""

    agent_name: str
    status: DelegationStatus = "completed"
    summary: str = ""
    observations: list[dict[str, Any]] = Field(default_factory=list)
    error: str = ""


class AgentHandoffRecord(BaseModel):
    """Auditable handoff record for Host-controlled multi-agent execution."""

    trace_id: str = ""
    source_agent: str = "agent_host"
    target_agent: str
    status: DelegationStatus = "planned"
    reason: str = ""
    context_summary: str = ""
    context_layers: list[ContextLayer] = Field(default_factory=list)
    result_summary: str = ""
    error: str = ""
    created_at: datetime = Field(default_factory=datetime.now)


class AgentCatalog(BaseModel):
    """Catalog of specialized agents visible to the Agent Host."""

    agents: list[SpecializedAgentDescriptor] = Field(default_factory=list)

    @classmethod
    def default(cls) -> "AgentCatalog":
        return cls(
            agents=[
                SpecializedAgentDescriptor(
                    name="workflow_supervisor",
                    display_name="Workflow Supervisor Agent",
                    kind="workflow_supervisor",
                    description="Routes goals, chooses capabilities, and decides whether to delegate or execute.",
                    when_to_use="Use for every non-trivial turn before tool execution.",
                    context_requirements=["turn_context", "session_context", "workflow_context", "tool_state_context"],
                    allowed_tool_sources=[],
                    allow_delegate=True,
                ),
                SpecializedAgentDescriptor(
                    name="conversation_agent",
                    display_name="Conversation Agent",
                    kind="conversation",
                    description="Handles direct chat, lightweight explanations, and follow-up replies.",
                    when_to_use="Use when no tool execution is needed or the user asks about previous results.",
                    context_requirements=["turn_context", "session_context", "tool_state_context"],
                ),
                SpecializedAgentDescriptor(
                    name="knowledge_agent",
                    display_name="Knowledge Agent",
                    kind="knowledge",
                    description="Retrieves local or external knowledge and summarizes source-backed answers.",
                    when_to_use="Use for school rules, files, chat history, RAG, and source-backed questions.",
                    context_requirements=["turn_context", "session_context", "knowledge_context"],
                    allowed_tool_sources=["local_knowledge", "external_rag"],
                ),
                SpecializedAgentDescriptor(
                    name="realtime_lookup_agent",
                    display_name="Realtime Lookup Agent",
                    kind="realtime_lookup",
                    description="Uses realtime public external tools such as MCP web search.",
                    when_to_use="Use for news, hot topics, weather-now, and other fresh public information.",
                    context_requirements=["turn_context", "tool_state_context"],
                    allowed_tool_sources=["mcp_tool"],
                ),
                SpecializedAgentDescriptor(
                    name="execution_agent",
                    display_name="Execution Agent",
                    kind="execution",
                    description="Executes approved command, MCP, skill, schedule, or delegate actions.",
                    when_to_use="Use when a TaskWorkflow contains executable steps.",
                    context_requirements=["turn_context", "workflow_context", "tool_state_context"],
                    allowed_tool_sources=["command", "mcp_tool", "skill", "schedule", "delegate"],
                ),
                SpecializedAgentDescriptor(
                    name="reply_synthesis_agent",
                    display_name="Reply Synthesis Agent",
                    kind="reply_synthesis",
                    description="Turns observations, handoffs, and failure reasons into the final user reply.",
                    when_to_use="Use before any final user-facing response after execution or delegation.",
                    context_requirements=["turn_context", "session_context", "workflow_context", "tool_state_context"],
                ),
            ]
        )

    def get(self, name: str) -> SpecializedAgentDescriptor | None:
        return next((agent for agent in self.agents if agent.name == name), None)

    def to_prompt(self) -> str:
        return "\n".join(agent.prompt_summary() for agent in self.agents)

    def select_for_turn(
        self, *, context_pack: ContextPack, route: Any = None, plan: Any = None, workflow: Any = None
    ) -> list[AgentDelegationDecision]:
        """Build deterministic Host-level handoff records from current turn state."""

        decisions = [
            AgentDelegationDecision(
                target_agent="workflow_supervisor",
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
                AgentDelegationDecision(
                    target_agent="knowledge_agent",
                    reason="The turn requires controlled knowledge retrieval or source-backed context.",
                    context_layers=["turn_context", "session_context", "knowledge_context"],
                    required=True,
                )
            )
        if candidate_mcp:
            decisions.append(
                AgentDelegationDecision(
                    target_agent="realtime_lookup_agent",
                    reason="Planner selected MCP tools for realtime or external lookup.",
                    context_layers=["turn_context", "tool_state_context"],
                    required=True,
                )
            )
        if has_steps:
            decisions.append(
                AgentDelegationDecision(
                    target_agent="execution_agent",
                    reason="The workflow contains executable steps.",
                    context_layers=["turn_context", "workflow_context", "tool_state_context"],
                    required=True,
                )
            )
        if intent == "chat" and not has_steps:
            decisions.append(
                AgentDelegationDecision(
                    target_agent="conversation_agent",
                    reason="The turn can be answered through conversation or prior context.",
                    context_layers=["turn_context", "session_context", "tool_state_context"],
                )
            )
        decisions.append(
            AgentDelegationDecision(
                target_agent="reply_synthesis_agent",
                reason="Every user-visible final answer must pass through reply synthesis policy.",
                context_layers=["turn_context", "session_context", "workflow_context", "tool_state_context"],
                required=True,
            )
        )
        return decisions
