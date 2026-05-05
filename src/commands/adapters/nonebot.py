from __future__ import annotations

from typing import Any

from nonebot.adapters import Event

from ..context import CommandExecutionContext


def context_from_event(event: Event, *, roles=None, trace_id: str = "") -> CommandExecutionContext:
    """Build a best-effort command context from a NoneBot event."""

    return CommandExecutionContext(
        user_id=None,
        roles=set(roles or []),
        platform=getattr(event, "platform", None),
        channel_id=str(getattr(event, "group_id", "") or getattr(event, "channel_id", "") or "") or None,
        guild_id=str(getattr(event, "guild_id", "") or "") or None,
        trace_id=trace_id,
        invoker="user_command",
        extra={"event_type": event.get_type()} if hasattr(event, "get_type") else {},
    )


def normalize_service_params(**kwargs: Any) -> dict[str, Any]:
    """Return kwargs as a plain dict for service command handlers."""

    return dict(kwargs)
