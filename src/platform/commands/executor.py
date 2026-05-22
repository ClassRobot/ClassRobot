from __future__ import annotations

from inspect import isawaitable
from typing import Any, Awaitable, Callable, Protocol

from .context import CommandExecutionContext
from .policy import CommandPolicy, command_policy
from .registry import CommandRegistry, command_registry
from .result import CommandResult


class CommandHandler(Protocol):
    """service-style 命令处理函数协议。"""

    def __call__(
        self,
        params: dict[str, Any],
        context: CommandExecutionContext,
    ) -> CommandResult | Awaitable[Any] | Any:
        """执行命令并返回可转换为 ``CommandResult`` 的结果。"""


class CommandExecutor:
    """统一 service-style 命令执行器。

    执行器只负责可结构化调用的 service 命令，不回放 NoneBot 事件。
    用户直发命令仍由 matcher 处理，Agent 编排命令必须先注册 handler。
    """

    def __init__(
        self,
        *,
        registry: CommandRegistry | None = None,
        policy: CommandPolicy | None = None,
    ) -> None:
        """创建绑定命令注册表和权限策略的执行器。"""

        self.registry = registry or command_registry
        self.policy = policy or command_policy
        self._handlers: dict[str, CommandHandler] = {}

    def clear_handlers(self) -> None:
        """清空已注册 service handler，主要用于测试隔离。"""

        self._handlers.clear()

    def register(self, command: str, handler: CommandHandler) -> CommandHandler:
        """注册命令的 service handler。"""

        self._handlers[command] = handler
        return handler

    def handler(self, command: str) -> Callable[[CommandHandler], CommandHandler]:
        """以装饰器形式注册命令 handler。"""

        def decorator(func: CommandHandler) -> CommandHandler:
            return self.register(command, func)

        return decorator

    def has_handler(self, command: str) -> bool:
        """判断主命令或别名是否已有 service handler。"""

        spec = self.registry.get(command)
        command_names = spec.commands if spec else {command}
        return any(name in self._handlers for name in command_names)

    async def execute(
        self,
        command: str,
        params: dict[str, Any] | None = None,
        context: CommandExecutionContext | None = None,
    ) -> CommandResult:
        """执行已注册的 service-style 命令。"""

        context = context or CommandExecutionContext()
        spec = self.registry.get(command)
        if spec is None:
            return CommandResult.fail(f"命令 `{command}` 不存在或尚未接入统一注册表。")

        decision = self.policy.check(spec, context)
        if not decision.allowed:
            return CommandResult.fail(f"无权调用 `{spec.name}`：{decision.reason}")

        handler = self._resolve_handler(spec, command)
        if handler is None:
            return CommandResult.fail(f"命令 `{spec.name}` 尚未接入统一 service 执行器，Agent 不能调用该命令。")

        raw_result = handler(params or {}, context)
        if isawaitable(raw_result):
            raw_result = await raw_result
        return self._coerce_result(raw_result)

    def _resolve_handler(self, spec: "CommandSpec", requested_command: str) -> CommandHandler | None:
        """按请求命令、主命令和别名顺序解析 service handler。

        Args:
            spec: 当前命令元数据。
            requested_command: 用户或 Agent 请求的命令名。

        Returns:
            CommandHandler | None: 命中的 service handler。
        """

        candidates = [requested_command]
        if requested_command != spec.name:
            candidates.append(spec.name)
        for command_name in sorted(spec.aliases):
            if command_name not in candidates:
                candidates.append(command_name)
        for command_name in candidates:
            if handler := self._handlers.get(command_name):
                return handler
        return None

    @staticmethod
    def _coerce_result(raw_result: Any) -> CommandResult:
        """把常见 handler 返回值转换为 ``CommandResult``。"""

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
