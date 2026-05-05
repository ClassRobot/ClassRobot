from __future__ import annotations

from inspect import isawaitable
from typing import Any, Awaitable, Callable, Protocol

from pydantic import BaseModel, Field

from .context import CommandExecutionContext
from .policy import CommandPolicy, command_policy
from .registry import CommandRegistry, command_registry
from .result import CommandResult


class CommandHandler(Protocol):
    """Callable signature used by service-style command handlers."""

    def __call__(
        self,
        params: dict[str, Any],
        context: CommandExecutionContext,
    ) -> CommandResult | Awaitable[Any] | Any:
        """Run a command and return a result-like value."""


class CommandExecutionError(RuntimeError):
    """Raised when unified command execution cannot continue."""


class CommandExecutorStats(BaseModel):
    """Small diagnostic snapshot for management pages and tests."""

    handlers: list[str] = Field(default_factory=list)


class CommandExecutor:
    """Unified service-style command executor.

    The executor is intentionally separate from NoneBot matchers. Existing
    interactive commands can continue through the legacy event path, while new
    or refactored commands register service handlers here.
    """

    def __init__(
        self,
        *,
        registry: CommandRegistry | None = None,
        policy: CommandPolicy | None = None,
    ) -> None:
        """Create an executor bound to a registry and policy evaluator."""

        self.registry = registry or command_registry
        self.policy = policy or command_policy
        self._handlers: dict[str, CommandHandler] = {}

    def clear_handlers(self) -> None:
        """Remove registered service handlers. Mostly useful for tests."""

        self._handlers.clear()

    def register(self, command: str, handler: CommandHandler) -> CommandHandler:
        """Register a service handler for a command name."""

        self._handlers[command] = handler
        return handler

    def handler(self, command: str) -> Callable[[CommandHandler], CommandHandler]:
        """Decorator form of :meth:`register`."""

        def decorator(func: CommandHandler) -> CommandHandler:
            return self.register(command, func)

        return decorator

    def has_handler(self, command: str) -> bool:
        """Return whether a command or alias can be executed as a service."""

        spec = self.registry.get(command)
        command_names = spec.commands if spec else {command}
        return any(name in self._handlers for name in command_names)

    async def execute(
        self,
        command: str,
        params: dict[str, Any] | None = None,
        context: CommandExecutionContext | None = None,
    ) -> CommandResult:
        """Execute a registered service-style command."""

        context = context or CommandExecutionContext()
        spec = self.registry.get(command)
        if spec is None:
            return CommandResult.fail(f"命令 `{command}` 不存在或尚未接入统一注册表。")

        decision = self.policy.check(spec, context)
        if not decision.allowed:
            return CommandResult.fail(f"无权调用 `{spec.name}`：{decision.reason}")

        handler = self._resolve_handler(spec.commands)
        if handler is None:
            return CommandResult.fail(
                f"命令 `{spec.name}` 暂未提供 service handler，当前仍需要走 NoneBot 事件兼容链路。"
            )

        raw_result = handler(params or {}, context)
        if isawaitable(raw_result):
            raw_result = await raw_result
        return self._coerce_result(raw_result)

    def stats(self) -> CommandExecutorStats:
        """Return a small diagnostic snapshot."""

        return CommandExecutorStats(handlers=sorted(self._handlers))

    def _resolve_handler(self, command_names: set[str]) -> CommandHandler | None:
        """Find the first handler bound to a command or alias."""

        for command_name in command_names:
            if handler := self._handlers.get(command_name):
                return handler
        return None

    @staticmethod
    def _coerce_result(raw_result: Any) -> CommandResult:
        """Convert common handler return values into ``CommandResult``."""

        if isinstance(raw_result, CommandResult):
            return raw_result
        if raw_result is None:
            return CommandResult.ok("命令执行完成。")
        if isinstance(raw_result, str):
            return CommandResult.ok(raw_result)
        if isinstance(raw_result, list):
            return CommandResult.ok("命令执行完成。", visible_outputs=[str(item) for item in raw_result])
        if isinstance(raw_result, dict):
            summary = str(raw_result.get("summary") or raw_result.get("message") or "命令执行完成。")
            return CommandResult.ok(summary, data=raw_result)
        return CommandResult.ok(str(raw_result))


command_executor = CommandExecutor()
