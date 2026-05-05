from __future__ import annotations

import json

from .context import CommandExecutionContext
from .result import CommandResult
from .spec import CommandSpec


class CommandSessionBridge:
    """Write command execution results back into an Agent chat session."""

    @staticmethod
    def build_context_message(spec: CommandSpec, context: CommandExecutionContext, result: CommandResult) -> str:
        """Build a compact JSON-backed message for conversation history."""

        payload = {
            "trace_id": context.trace_id,
            "command": spec.name,
            "invoker": context.invoker,
            "success": result.success,
            "summary": result.summary,
            "context_outputs": result.context_outputs,
            "data": result.data,
        }
        return "# 系统命令执行结果\n" + json.dumps(payload, ensure_ascii=False, default=str)

    @classmethod
    def record_result(cls, session, spec: CommandSpec, context: CommandExecutionContext, result: CommandResult) -> None:
        """Record a command result into a session-like object when possible."""

        message = cls.build_context_message(spec, context, result)
        messages = getattr(session, "messages", None)
        assistant_message = getattr(messages, "assistant_message", None)
        if callable(assistant_message):
            assistant_message(message)
