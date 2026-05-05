import pytest


def test_command_policy_and_availability_share_soft_disable_state(loaded_plugins):
    from src.commands import CommandExecutionContext, CommandSpec
    from src.commands.availability import command_availability
    from src.commands.policy import CommandPolicy
    from src.commands.renderers.helper import command_spec_to_helper
    from utils.helper import Helpers, HelperScope
    from utils.roles import UserRole

    spec = CommandSpec(
        name="测试软关闭命令",
        description="用于测试软关闭",
        roles={UserRole.user},
        scopes={HelperScope.user},
        plugin_module="src.plugins.test_command_core",
    )
    helpers = Helpers()
    helpers.append(command_spec_to_helper(spec))

    try:
        command_availability.set_command_enabled(spec.name, False, "维护中")

        filtered = command_availability.filter_helpers(helpers)
        decision = CommandPolicy().check(spec, CommandExecutionContext(roles={UserRole.user}))

        assert filtered.get_helper(spec.name) is None
        assert decision.allowed is False
        assert "维护中" in decision.reason
    finally:
        command_availability.clear()


@pytest.mark.asyncio
async def test_command_executor_runs_service_handler_with_static_policy():
    from src.commands import CommandExecutionContext, CommandExecutor, CommandParam, CommandRegistry, CommandResult
    from src.commands.spec import CommandSpec
    from utils.roles import UserRole

    registry = CommandRegistry()
    registry.register(
        CommandSpec(
            name="测试服务命令",
            description="执行测试服务",
            params=[CommandParam(name="名称")],
            roles={UserRole.user},
            execution_mode="service",
        )
    )
    executor = CommandExecutor(registry=registry)

    @executor.handler("测试服务命令")
    async def _(params, context):
        assert context.invoker == "agent_workflow"
        return CommandResult.ok(f"服务已处理：{params['名称']}")

    denied = await executor.execute(
        "测试服务命令",
        {"名称": "无权限用户"},
        CommandExecutionContext(invoker="agent_workflow"),
    )
    result = await executor.execute(
        "测试服务命令",
        {"名称": "小明"},
        CommandExecutionContext(roles={UserRole.user}, invoker="agent_workflow"),
    )

    assert denied.success is False
    assert result.success is True
    assert result.summary == "服务已处理：小明"


def test_command_tool_catalog_prefers_registered_spec_and_respects_agent_visibility(loaded_plugins):
    from src.commands import CommandParam, CommandSpec, command_registry
    from src.commands.availability import command_availability
    from src.commands.renderers.helper import command_spec_to_helper
    from src.plugins.autogpt.command_tools import CommandToolCatalog
    from utils.helper import Helpers, HelperScope
    from utils.roles import UserRole

    visible_spec = CommandSpec(
        name="测试Agent工具",
        description="给 Agent 调用的命令",
        params=[CommandParam(name="数量", value_type="integer")],
        roles={UserRole.user},
        scopes={HelperScope.user},
        risk_level="medium",
        plugin_module="src.plugins.test_command_core",
    )
    hidden_spec = CommandSpec(
        name="测试禁止Agent工具",
        description="不允许 Agent 调用的命令",
        roles={UserRole.user},
        scopes={HelperScope.user},
        agent_callable=False,
        plugin_module="src.plugins.test_command_core",
    )
    command_registry.register(visible_spec)
    command_registry.register(hidden_spec)
    helpers = Helpers()
    helpers.extend([command_spec_to_helper(visible_spec), command_spec_to_helper(hidden_spec)])

    try:
        catalog = CommandToolCatalog.from_helpers(helpers)
        tool = catalog.get("测试Agent工具")

        assert tool is not None
        assert tool.params[0].value_type == "integer"
        assert tool.risk_level == "medium"
        assert catalog.get("测试禁止Agent工具") is None

        command_availability.set_command_enabled("测试Agent工具", False, "临时关闭")
        disabled_catalog = CommandToolCatalog.from_helpers(helpers)
        assert disabled_catalog.get("测试Agent工具") is None
    finally:
        command_availability.clear()
