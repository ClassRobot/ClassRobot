"""Host-controlled specialized agent delegation primitives."""

from .catalog import (
    AgentCatalog,
    AgentHandoffRecord,
    AgentResultEnvelope,
    AgentDelegationDecision,
    SpecializedAgentDescriptor,
)

__all__ = [
    "AgentCatalog",
    "AgentDelegationDecision",
    "AgentHandoffRecord",
    "AgentResultEnvelope",
    "SpecializedAgentDescriptor",
]
