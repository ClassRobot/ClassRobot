from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, BaseModel
from src.core.llm.message import Content
from src.core.agent.runtime.context import ContextPack
from src.core.agent.runtime.reply import ReplyEnvelope
from src.core.agent.runtime.roles import RuntimeRoleTraceRecord

TurnDecisionType = Literal["direct_reply", "delegate", "execute", "confirm", "clarify", "schedule", "stop"]


class TurnEnvelope(BaseModel):
    """Host-owned contract for one user turn."""

    trace_id: str
    user_id: int | None = None
    message_preview: str = ""
    contents: list[Content] = Field(default_factory=list)
    runtime_context: dict[str, Any] = Field(default_factory=dict)
    pending_workflow: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class TurnDecision(BaseModel):
    """Host-level decision before execution or final reply."""

    decision_type: TurnDecisionType = "direct_reply"
    reason: str = ""
    target_role: str = ""
    requires_execution: bool = False
    requires_confirmation: bool = False


class TurnOutputBundle(BaseModel):
    """All user-visible and audit output produced for one turn."""

    trace_id: str
    decision: TurnDecision = Field(default_factory=TurnDecision)
    reply: ReplyEnvelope = Field(default_factory=ReplyEnvelope)
    context_pack: ContextPack | None = None
    runtime_roles: list[RuntimeRoleTraceRecord] = Field(default_factory=list)
    audit_artifacts: dict[str, Any] = Field(default_factory=dict)
