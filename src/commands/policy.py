from __future__ import annotations

from pydantic import BaseModel
from utils.roles import UserRole

from .availability import CommandAvailabilityService, command_availability
from .context import CommandExecutionContext
from .spec import CommandSpec


class CommandPolicyDecision(BaseModel):
    """Decision returned by command policy checks."""

    allowed: bool
    reason: str = ""


class CommandPolicy:
    """Evaluate static command policy shared by help, Agent and executor."""

    def __init__(self, availability: CommandAvailabilityService | None = None) -> None:
        """Create a policy evaluator."""

        self.availability = availability or command_availability

    def check(self, spec: CommandSpec, context: CommandExecutionContext) -> CommandPolicyDecision:
        """Return whether ``context`` may invoke ``spec``."""

        availability_decision = self.availability.check(spec)
        if not availability_decision.available:
            return CommandPolicyDecision(allowed=False, reason=availability_decision.reason)

        if context.invoker == "agent_workflow" and not spec.agent_callable:
            return CommandPolicyDecision(allowed=False, reason="command is not callable by Agent workflows")

        if spec.exclude_roles and spec.exclude_roles.intersection(context.roles):
            return CommandPolicyDecision(allowed=False, reason="user role is explicitly denied")

        if spec.roles and spec.roles.isdisjoint(context.roles):
            return CommandPolicyDecision(allowed=False, reason="user role is not allowed")

        return CommandPolicyDecision(allowed=True)

    @staticmethod
    def from_roles(*roles: UserRole | str, invoker: str = "user_command") -> CommandExecutionContext:
        """Build a minimal execution context from role values."""

        normalized: set[UserRole] = set()
        for role in roles:
            try:
                normalized.add(role if isinstance(role, UserRole) else UserRole(role))
            except ValueError:
                continue
        return CommandExecutionContext(roles=normalized, invoker=invoker)  # type: ignore[arg-type]


command_policy = CommandPolicy()
