from __future__ import annotations

from collections.abc import Iterable


def ensure_service_helper(
    command: str,
    description: str,
    *,
    aliases: Iterable[str] = (),
    roles=None,
    scopes=None,
    risk_level: str = "low",
):
    """为 Agent 测试构造一条符合新架构的 service 命令 Helper。"""

    from utils.commands import CommandResult, CommandSpec, command_executor, command_registry
    from utils.commands.renderers.helper import command_spec_to_helper

    alias_set = {str(alias) for alias in aliases}
    spec = command_registry.get(command)
    if spec is None:
        spec = CommandSpec(
            name=command,
            description=description,
            aliases=alias_set,
            roles=set(roles or set()),
            scopes=set(scopes or set()),
            risk_level=risk_level,
            agent_callable=True,
            execution_mode="service",
            plugin_module="tests.autogpt",
        )
        command_registry.register(spec)
    else:
        spec.description = description or spec.description
        spec.aliases.update(alias_set)
        if roles is not None:
            spec.roles = set(roles)
        if scopes is not None:
            spec.scopes = set(scopes)
        spec.risk_level = risk_level
        spec.agent_callable = True
        spec.execution_mode = "service"

    if not command_executor.has_handler(spec.name):
        @command_executor.handler(spec.name)
        async def _test_service_handler(params, context):
            return CommandResult.ok(f"{spec.name} 测试命令已执行。")

    return command_spec_to_helper(spec)
