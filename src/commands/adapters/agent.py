from __future__ import annotations

from typing import Any

from ..context import CommandExecutionContext
from ..executor import CommandExecutor, command_executor
from ..result import CommandResult


class AgentCommandAdapter:
    """Adapter used by Agent workflows to call service-style commands first."""

    def __init__(self, executor: CommandExecutor | None = None) -> None:
        """Create an adapter bound to the shared command executor."""

        self.executor = executor or command_executor

    def can_execute(self, command: str) -> bool:
        """Return whether the command has a service handler."""

        return self.executor.has_handler(command)

    async def execute(
        self,
        command: str,
        params: dict[str, Any] | None = None,
        context: CommandExecutionContext | None = None,
    ) -> CommandResult:
        """Execute a command through the unified executor."""

        context = context or CommandExecutionContext(invoker="agent_workflow")
        return await self.executor.execute(command, params=params, context=context)
