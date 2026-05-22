from __future__ import annotations

from typing import Any

from ..context import CommandExecutionContext
from ..executor import CommandExecutor, command_executor
from ..result import CommandResult


class AgentCommandAdapter:
    """Agent 工作流调用统一 service 命令的适配器。"""

    def __init__(self, executor: CommandExecutor | None = None) -> None:
        """创建绑定共享命令执行器的适配器。"""

        self.executor = executor or command_executor

    def can_execute(self, command: str) -> bool:
        """判断命令是否已有 service handler。"""

        return self.executor.has_handler(command)

    async def execute(
        self,
        command: str,
        params: dict[str, Any] | None = None,
        context: CommandExecutionContext | None = None,
    ) -> CommandResult:
        """通过统一执行器调用命令。"""

        context = context or CommandExecutionContext(invoker="agent_workflow")
        return await self.executor.execute(command, params=params, context=context)
