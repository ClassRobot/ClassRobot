from __future__ import annotations

import shlex
from typing import Any
from dataclasses import dataclass

from .result import CommandResult
from .executor import CommandExecutor, command_executor
from .registry import CommandRegistry, command_registry
from .context import CommandParams, CommandExecutionContext


@dataclass(slots=True)
class CommandCLIInvocation:
    """一次 CLI 风格命令调用。"""

    command: str
    params: CommandParams


class CommandCLI:
    """把统一命令封装成类似 CLI 的调用入口。

    开发者仍然通过 ``on_agent_command`` / ``on_command`` 声明命令；CLI
    入口只消费 ``CommandRegistry`` 中的元数据，把文本或 argv 转换为
    ``CommandParams`` 后交给 ``CommandExecutor``。这样用户直发命令和
    Agent 调命令共享同一鉴权与 service handler。
    """

    def __init__(
        self,
        *,
        registry: CommandRegistry | None = None,
        executor: CommandExecutor | None = None,
    ) -> None:
        self.registry = registry if registry is not None else command_registry
        self.executor = executor if executor is not None else command_executor

    async def run_text(
        self,
        text: str,
        context: CommandExecutionContext | None = None,
    ) -> CommandResult:
        """执行一段 CLI 文本。"""

        invocation = self.parse_text(text)
        return await self.run_invocation(invocation, context)

    async def run_command(
        self,
        command: str,
        params: dict[str, Any] | CommandParams | None = None,
        context: CommandExecutionContext | None = None,
    ) -> CommandResult:
        """按命令名和结构化参数执行命令。"""

        return await self.run_invocation(
            CommandCLIInvocation(command=command, params=CommandParams(params or {})),
            context,
        )

    async def run_invocation(
        self,
        invocation: CommandCLIInvocation,
        context: CommandExecutionContext | None = None,
    ) -> CommandResult:
        """执行已解析的 CLI 调用。"""

        context = context or CommandExecutionContext(invoker="agent_workflow")
        return await self.executor.execute(invocation.command, params=invocation.params, context=context)

    def parse_text(self, text: str) -> CommandCLIInvocation:
        """从 CLI 文本解析命令名和参数。"""

        tokens = shlex.split(str(text or "").strip(), posix=False)
        if not tokens:
            return CommandCLIInvocation(command="", params=CommandParams())

        command = self.resolve_command_name(tokens)
        consumed = len(command.split()) if command else 1
        if not command:
            command = tokens[0]
        return CommandCLIInvocation(
            command=command,
            params=self.params_from_tokens(command, tokens[consumed:]),
        )

    def resolve_command_name(self, tokens: list[str]) -> str:
        """按最长匹配解析命令名或别名。"""

        text = " ".join(tokens)
        for spec in sorted(self.registry, key=lambda item: max(len(name) for name in item.commands), reverse=True):
            for command_name in sorted(spec.commands, key=len, reverse=True):
                if text == command_name or text.startswith(command_name + " "):
                    return command_name
        return ""

    def params_from_tokens(self, command: str, tokens: list[str]) -> CommandParams:
        """按命令元数据把 argv 参数转换为 ``CommandParams``。"""

        spec = self.registry.get(command)
        if spec is None:
            return CommandParams({f"arg{index}": value for index, value in enumerate(tokens)})

        params = CommandParams()
        cursor = 0
        for index, param in enumerate(spec.params):
            key = param.name
            source_name = param.source_name or key
            if param.multiple:
                value: Any = tokens[cursor:]
                cursor = len(tokens)
            elif index == len(spec.params) - 1:
                value = " ".join(tokens[cursor:]) if tokens[cursor:] else ""
                cursor = len(tokens)
            else:
                value = tokens[cursor] if cursor < len(tokens) else ""
                cursor += 1
            value = self.coerce_value(value, param.value_type)
            params[key] = value
            if source_name != key:
                params[source_name] = value
        return params

    @staticmethod
    def coerce_value(value: Any, value_type: str) -> Any:
        """按命令参数类型做最小转换。"""

        if isinstance(value, list):
            return value
        if value_type == "integer" and value != "":
            try:
                return int(value)
            except (TypeError, ValueError):
                return value
        if value_type == "number" and value != "":
            try:
                return float(value)
            except (TypeError, ValueError):
                return value
        if value_type == "boolean" and isinstance(value, str):
            return value.lower() in {"1", "true", "yes", "y", "是", "开启"}
        return value


command_cli = CommandCLI()

__all__ = ["CommandCLI", "CommandCLIInvocation", "command_cli"]
