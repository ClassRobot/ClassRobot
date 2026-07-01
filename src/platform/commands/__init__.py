from .spec import CommandSpec
from .result import CommandResult
from .policy import CommandPolicy, command_policy
from .executor import CommandExecutor, command_executor
from .registry import CommandRegistry, command_registry
from .cli import CommandCLI, CommandCLIInvocation, command_cli
from .schema import CommandParam, CommandRiskLevel, CommandExecutionMode
from .availability import CommandAvailabilityService, command_availability
from .context import CommandParams, CommandInvoker, CommandExecutionContext, normalize_user_roles
from .history import (
    CommandInputRecorder,
    clear_command_input_recorders,
    register_command_input_recorder,
    dispatch_command_input_recorders,
    unregister_command_input_recorder,
)

__all__ = [
    "CommandAvailabilityService",
    "CommandBinding",
    "CommandExecutionMode",
    "CommandExecutionContext",
    "CommandExecutor",
    "CommandCLI",
    "CommandCLIInvocation",
    "CommandInputRecorder",
    "CommandInvoker",
    "CommandParam",
    "CommandParams",
    "CommandPolicy",
    "CommandRegistry",
    "CommandResult",
    "CommandRiskLevel",
    "CommandSpec",
    "CommandUserContextDepends",
    "build_user_command_context",
    "command_alconna",
    "command_availability",
    "command_command",
    "command_cli",
    "command_executor",
    "command_policy",
    "command_result_text",
    "command_registry",
    "clear_command_input_recorders",
    "dispatch_command_input_recorders",
    "normalize_user_roles",
    "on_agent_command",
    "register_command_input_recorder",
    "send_command_result",
    "spec_from_alconna",
    "unregister_command_input_recorder",
]


def __getattr__(name: str):
    """Lazy-export NoneBot-heavy helpers without polluting lightweight imports."""

    if name in {"CommandUserContextDepends", "build_user_command_context"}:
        from .depends import CommandUserContextDepends, build_user_command_context

        globals()["CommandUserContextDepends"] = CommandUserContextDepends
        globals()["build_user_command_context"] = build_user_command_context
        return globals()[name]
    if name in {"command_result_text", "send_command_result"}:
        from .delivery import command_result_text, send_command_result

        globals()["command_result_text"] = command_result_text
        globals()["send_command_result"] = send_command_result
        return globals()[name]
    if name in {"CommandBinding", "command_alconna", "command_command", "on_agent_command", "spec_from_alconna"}:
        from .binding import CommandBinding, command_alconna, command_command, on_agent_command, spec_from_alconna

        globals()["CommandBinding"] = CommandBinding
        globals()["command_alconna"] = command_alconna
        globals()["command_command"] = command_command
        globals()["on_agent_command"] = on_agent_command
        globals()["spec_from_alconna"] = spec_from_alconna
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
