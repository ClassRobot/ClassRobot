from types import ModuleType, SimpleNamespace

import pytest


def test_spec_from_alconna_derives_params_and_helper_view(loaded_plugins):
    from arclet.alconna import Args, Alconna, MultiVar, CommandMeta
    from src.platform.commands import CommandBinding, spec_from_alconna
    from src.platform.helper import HelperScope, ParamMode, UserRole
    from src.platform.commands.renderers.helper import command_spec_to_helper

    spec = spec_from_alconna(
        Alconna(
            "测试添加课表",
            Args["values", MultiVar(str, flag="+")],
            meta=CommandMeta(description="添加测试课表", example="测试添加课表 1-2 数学"),
        ),
        aliases={"测试新增课表"},
        binding=CommandBinding(
            roles={UserRole.user},
            scopes={HelperScope.user},
            param_labels={"values": "课表内容"},
            param_descriptions={"values": "一条或多条课表片段"},
        ),
    )

    helper = command_spec_to_helper(spec)

    assert spec.name == "测试添加课表"
    assert spec.aliases == {"测试新增课表"}
    assert spec.params[0].name == "课表内容"
    assert spec.params[0].source_name == "values"
    assert spec.params[0].mode == ParamMode.ONE_OR_MORE
    assert spec.params[0].multiple is True
    assert helper.command == spec.name
    assert helper.aliases == spec.aliases
    assert helper.params[0].name == "课表内容"
    assert helper.params[0].mode == ParamMode.ONE_OR_MORE


def test_command_alconna_registers_spec_and_attaches_helper(loaded_plugins):
    from arclet.alconna import Args, Alconna, CommandMeta
    from src.platform.commands import CommandBinding, command_alconna, command_registry
    from src.platform.helper import HelperScope, ParamMode, UserRole

    matcher = command_alconna(
        Alconna(
            "测试查询资料",
            Args["keyword?", str],
            meta=CommandMeta(description="查询测试资料"),
        ),
        aliases={"测试资料查询"},
        binding=CommandBinding(
            roles={UserRole.user},
            scopes={HelperScope.user},
            param_labels={"keyword": "关键词"},
        ),
        priority=1,
        block=True,
    )

    spec = matcher.__command_spec__
    helper = matcher.__helper__

    assert command_registry.get("测试查询资料") is spec
    assert command_registry.get("测试资料查询") is spec
    assert helper.command == "测试查询资料"
    assert helper.params[0].name == "关键词"
    assert helper.params[0].mode == ParamMode.OPTIONAL


@pytest.mark.asyncio
async def test_on_agent_command_registers_alconna_matcher_helper_and_service_handler(loaded_plugins):
    from arclet.alconna import Args, Alconna, CommandMeta
    from src.platform.commands import (
        CommandBinding,
        CommandExecutionContext,
        CommandResult,
        command_executor,
        command_registry,
    )
    from src.platform.commands import on_agent_command
    from src.platform.helper import HelperScope
    from src.core.auth import UserRole

    async def execute(params, context):
        return CommandResult.ok(f"统一入口已处理：{params['关键词']}")

    matcher = on_agent_command(
        Alconna(
            "测试统一入口",
            Args["keyword", str],
            meta=CommandMeta(description="测试统一命令入口"),
        ),
        aliases={"测试Agent入口"},
        binding=CommandBinding(
            roles={UserRole.user},
            scopes={HelperScope.user},
            param_labels={"keyword": "关键词"},
        ),
        service_handler=execute,
        priority=1,
        block=True,
    )

    spec = matcher.__command_spec__
    helper = matcher.__helper__
    result = await command_executor.execute(
        "测试Agent入口",
        {"关键词": "样例"},
        CommandExecutionContext(roles={UserRole.user}, invoker="agent_workflow"),
    )

    assert command_registry.get("测试统一入口") is spec
    assert command_registry.get("测试Agent入口") is spec
    assert spec.execution_mode == "service"
    assert helper.command == "测试统一入口"
    assert helper.params[0].name == "关键词"
    assert result.success is True
    assert result.summary == "统一入口已处理：样例"


@pytest.mark.asyncio
async def test_on_agent_command_supports_decorator_style_agent_handler(loaded_plugins):
    from src.platform.commands import CommandBinding, CommandExecutionContext, command_executor, on_agent_command
    from src.platform.helper import HelperScope
    from src.core.auth import UserRole

    matcher = on_agent_command(
        "测试普通统一入口",
        binding=CommandBinding(
            description="测试普通命令统一入口",
            roles={UserRole.user},
            scopes={HelperScope.user},
        ),
        priority=1,
        block=True,
    )

    @matcher.agent_handler
    async def execute(params, context):
        return {"summary": f"普通入口已处理：{params['名称']}", "name": params["名称"]}

    result = await command_executor.execute(
        "测试普通统一入口",
        {"名称": "小明"},
        CommandExecutionContext(roles={UserRole.user}, invoker="agent_workflow"),
    )

    assert matcher.__command_spec__.execution_mode == "service"
    assert matcher.__helper__.description == "测试普通命令统一入口"
    assert result.success is True
    assert result.summary == "普通入口已处理：小明"
    assert result.data["name"] == "小明"


def test_bootstrap_helper_runtime_collects_matcher_bound_helpers(loaded_plugins):
    from arclet.alconna import Alconna, CommandMeta
    from src.platform.commands import CommandBinding, command_alconna
    from src.platform.helper.config import helper_menu
    from src.platform.helper.runtime import bootstrap_helper_runtime

    matcher = command_alconna(
        Alconna("测试绑定帮助", meta=CommandMeta(description="测试绑定帮助说明")),
        binding=CommandBinding(),
        priority=1,
        block=True,
    )

    module = ModuleType("tests.fake_bound_commands")
    matcher.module_name = module.__name__
    setattr(module, "test_cmd", matcher)

    try:
        bootstrap_helper_runtime([SimpleNamespace(module=module)])

        helper = helper_menu.get_helper("测试绑定帮助")
        assert helper is not None
        assert helper.description == "测试绑定帮助说明"
    finally:
        bootstrap_helper_runtime(loaded_plugins)


@pytest.mark.asyncio
async def test_command_input_recorder_registry_dispatches_without_src_dependency(loaded_plugins):
    from src.platform.commands import (
        CommandSpec,
        dispatch_command_input_recorders,
        register_command_input_recorder,
        unregister_command_input_recorder,
    )

    calls = []
    spec = CommandSpec(name="测试记录器", description="测试命令输入记录器")

    async def recorder(bot, event, command_spec):
        calls.append((bot, event, command_spec.name))

    register_command_input_recorder("tests.command_input_recorder", recorder)
    try:
        bot = SimpleNamespace(self_id="test-bot")
        event = SimpleNamespace()
        await dispatch_command_input_recorders(bot, event, spec)
    finally:
        unregister_command_input_recorder("tests.command_input_recorder")

    assert calls == [(bot, event, "测试记录器")]
