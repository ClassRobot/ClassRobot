from __future__ import annotations

from typing import Awaitable, Callable, Protocol

from ..result import CommandResult


class LegacyEventDispatcher(Protocol):
    """Minimal protocol for legacy NoneBot event replay dispatchers."""

    def __call__(self, command: str) -> Awaitable[list[str]]:
        """Dispatch a command through the legacy event system."""


class LegacyEventCommandAdapter:
    """Small wrapper that marks legacy event replay as an explicit adapter."""

    def __init__(self, dispatcher: Callable[[str], Awaitable[list[str]]]) -> None:
        """Create a legacy adapter around an existing dispatcher callback."""

        self.dispatcher = dispatcher

    async def execute(self, command: str) -> CommandResult:
        """Execute a command by delegating to the supplied event dispatcher."""

        outputs = await self.dispatcher(command)
        return CommandResult.ok(
            "命令已通过 NoneBot 事件兼容链路执行。",
            visible_outputs=outputs,
            context_outputs=outputs,
        )
