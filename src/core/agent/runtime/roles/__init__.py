"""Host-controlled runtime role tracing primitives."""

from .catalog import (
    RuntimeRoleResult,
    RuntimeRoleCatalog,
    RuntimeRoleDecision,
    RuntimeRoleDescriptor,
    RuntimeRoleTraceRecord,
)

__all__ = [
    "RuntimeRoleCatalog",
    "RuntimeRoleDecision",
    "RuntimeRoleDescriptor",
    "RuntimeRoleResult",
    "RuntimeRoleTraceRecord",
]
