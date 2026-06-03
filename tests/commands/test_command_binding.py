from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def test_spec_from_alconna_derives_params_and_helper_view(loaded_plugins):
    from arclet.alconna import Args, Alconna, MultiVar, CommandMeta
    from src.platform.helper import UserRole, ParamMode, HelperScope
    from src.platform.commands import CommandBinding, spec_from_alconna
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
    from src.platform.helper import UserRole, ParamMode, HelperScope
    from src.platform.commands import CommandBinding, command_alconna, command_registry

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
    from src.core.auth import UserRole
    from src.platform.helper import HelperScope
    from arclet.alconna import Args, Alconna, CommandMeta
    from src.platform.commands import (
        CommandResult,
        CommandBinding,
        CommandExecutionContext,
        command_executor,
        command_registry,
        on_agent_command,
    )

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
    from src.core.auth import UserRole
    from src.platform.helper import HelperScope
    from src.platform.commands import CommandBinding, CommandExecutionContext, command_executor, on_agent_command

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


@pytest.mark.asyncio
async def test_on_agent_command_supports_unified_handler_auto_user_entry(loaded_plugins):
    from src.core.auth import UserRole
    from src.platform.helper import HelperScope
    from src.platform.commands import CommandBinding, CommandExecutionContext, command_executor, on_agent_command

    matcher = on_agent_command(
        "测试单函数双入口",
        binding=CommandBinding(
            description="测试单函数双入口",
            roles={UserRole.user},
            scopes={HelperScope.user},
        ),
        priority=1,
        block=True,
    )

    @matcher.unified_handler
    async def execute(params, context):
        return f"双入口已处理：{params.get_value('名称', 'name')}"

    result = await command_executor.execute(
        "测试单函数双入口",
        {"name": "小明"},
        CommandExecutionContext(roles={UserRole.user}, invoker="agent_workflow"),
    )

    assert matcher.__command_spec__.execution_mode == "service"
    assert matcher.__command_auto_user_handler_attached__ is True
    assert result.summary == "双入口已处理：小明"


def test_command_params_reads_label_and_source_name():
    from src.platform.commands import CommandParams

    params = CommandParams({"query": "迟到", "范围": "group"})

    assert params.get_value("关键词", "query") == "迟到"
    assert params.get_value("范围", "scope") == "group"
    assert params.get_value("缺失", "missing", "默认") == "默认"


def test_command_params_from_event_text_supports_multiple_and_integer(onebot):
    from src.platform.commands.spec import CommandSpec
    from src.platform.commands.schema import CommandParam
    from src.platform.commands.binding import command_params_from_event_text

    spec = CommandSpec(
        name="测试参数解析",
        description="测试普通命令参数解析",
        params=[
            CommandParam(name="数量", source_name="count", value_type="integer"),
            CommandParam(name="标签", source_name="tags", multiple=True),
        ],
    )
    event = onebot.private_event("测试参数解析 3 甲 乙", user_id=91001, nickname="参数用户")

    params = command_params_from_event_text(event, spec)

    assert params.get_value("数量", "count") == 3
    assert params.get_value("标签", "tags") == ["甲", "乙"]


@pytest.mark.asyncio
async def test_plain_command_auto_user_handler_uses_service_and_creates_user(app, onebot, send_recorder):
    from src.core.auth import UserRole
    from src.models import User, UserBind
    from src.platform.helper import HelperScope
    from src.platform.commands.schema import CommandParam
    from src.platform.commands import CommandResult, CommandBinding, on_agent_command

    seen_contexts = []

    async def execute(params, context):
        seen_contexts.append(context)
        return CommandResult.ok(f"普通命令自动入口：{params.get_value('名称', 'name')} / user={context.user_id}")

    matcher = on_agent_command(
        "测试普通自动入口",
        binding=CommandBinding(
            description="测试普通 on_command 自动入口",
            roles={UserRole.user},
            scopes={HelperScope.user},
            params=[CommandParam(name="名称", source_name="name")],
        ),
        service_handler=execute,
        auto_user_handler=True,
        priority=1,
        block=True,
    )

    async with app.test_matcher(matcher) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("测试普通自动入口 小明", user_id=91901, nickname="新用户昵称")
        ctx.receive_event(bot, event)

    recorder.assert_any("普通命令自动入口", "小明")
    assert seen_contexts
    assert seen_contexts[0].invoker == "user_command"
    assert seen_contexts[0].user_id is not None
    bind = await UserBind.get_bind("onebot11.qq_client", "91901")
    assert bind is not None
    created_user = await User.get_user(seen_contexts[0].user_id)
    assert created_user is not None
    assert created_user.nickname == "新用户昵称"


@pytest.mark.asyncio
async def test_command_executor_emits_live_trace_events(loaded_plugins):
    from src.core.agent.runtime.live_trace import AgentLiveTraceConfig, agent_live_trace_registry
    from src.platform.commands import (
        CommandResult,
        CommandBinding,
        CommandExecutionContext,
        command_executor,
        on_agent_command,
    )

    original_config = agent_live_trace_registry.config
    agent_live_trace_registry.config = AgentLiveTraceConfig(enabled=True)
    agent_live_trace_registry.clear()

    async def execute(params, context):
        return CommandResult.ok(f"trace handled {params.get_value('名称', 'name')}", data={"echo": params.get("name")})

    matcher = on_agent_command(
        "测试命令Trace",
        binding=CommandBinding(description="测试命令 trace"),
        service_handler=execute,
        priority=1,
        block=True,
    )

    try:
        agent_live_trace_registry.start_trace("trace-command-test", user_id=42, message_preview="测试命令 trace")
        result = await command_executor.execute(
            matcher.__command_spec__.name,
            {"name": "小明"},
            CommandExecutionContext(user_id=42, trace_id="trace-command-test", invoker="agent_workflow"),
        )
        trace = agent_live_trace_registry.get_trace("trace-command-test")
    finally:
        agent_live_trace_registry.clear()
        agent_live_trace_registry.config = original_config

    assert result.success
    assert trace is not None
    event_types = [event.event_type for event in trace.events]
    assert "command_dispatch_started" in event_types
    assert "command_dispatch_completed" in event_types
    completed = next(event for event in trace.events if event.event_type == "command_dispatch_completed")
    assert completed.tool_name == "测试命令Trace"
    assert completed.params_preview["params"]["name"] == "小明"
    assert completed.params_preview["result"]["data"]["echo"] == "小明"


def test_application_active_init_files_do_not_register_service_handlers_directly():
    project_root = Path(__file__).resolve().parents[2]
    active_dir = project_root / "src" / "plugins" / "application" / "active"
    forbidden = ("command_executor.handler", "command_executor.execute", "CommandExecutionContext", "def _dispatch")

    offenders: list[str] = []
    for path in active_dir.rglob("__init__.py"):
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            if marker in text:
                offenders.append(f"{path.relative_to(project_root)} contains {marker}")

    assert offenders == []


def test_migrated_file_manager_commands_do_not_keep_duplicate_init_handlers():
    project_root = Path(__file__).resolve().parents[2]
    migrated_by_module = {
        "file_manager": ("pwd_cmd", "ls_cmd", "cd_cmd", "cat_cmd", "find_cmd", "grep_cmd", "tree_cmd"),
        "student": ("query_cmd", "query_student_profile_cmd"),
        "teacher": ("query_teacher_cmd", "query_teacher_profile_cmd"),
        "classes": ("query_classes_cmd",),
    }

    offenders: list[str] = []
    for module, commands in migrated_by_module.items():
        text = (project_root / "src" / "plugins" / "application" / "active" / module / "__init__.py").read_text(
            encoding="utf-8"
        )
        offenders.extend(f"{module}.{command}" for command in commands if f"@{command}.handle()" in text)

    assert offenders == []


def test_runtime_roles_package_replaced_delegation_source_path():
    project_root = Path(__file__).resolve().parents[2]
    checked_roots = [project_root / "src", project_root / "tests", project_root / "docs"]
    old_import = "runtime" + ".delegation"
    old_path = "runtime" + "/delegation"
    offenders: list[str] = []
    for root in checked_roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix in {".pyc", ".pyo"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if old_import in text or old_path in text:
                offenders.append(str(path.relative_to(project_root)))

    assert not (project_root / "src" / "core" / "agent" / "runtime" / "delegation").exists()
    assert offenders == []


def test_bootstrap_helper_runtime_collects_matcher_bound_helpers(loaded_plugins):
    from arclet.alconna import Alconna, CommandMeta
    from src.platform.helper.config import helper_menu
    from src.platform.helper.runtime import bootstrap_helper_runtime
    from src.platform.commands import CommandBinding, command_alconna

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


def test_bootstrap_helper_runtime_keeps_manual_helpers_compatibility(loaded_plugins):
    from src.platform.helper import Helper
    from src.platform.helper.config import helper_menu
    from src.platform.helper.runtime import bootstrap_helper_runtime

    module = ModuleType("tests.fake_manual_helpers")
    module.__helpers__ = [
        Helper(command="测试手写帮助", description="外部命令仍可手写 Helper。"),
    ]

    try:
        bootstrap_helper_runtime([SimpleNamespace(module=module)])

        helper = helper_menu.get_helper("测试手写帮助")
        assert helper is not None
        assert helper.description == "外部命令仍可手写 Helper。"
    finally:
        bootstrap_helper_runtime(loaded_plugins)


@pytest.mark.asyncio
async def test_command_input_recorder_registry_dispatches_without_src_dependency(loaded_plugins):
    from src.platform.commands import (
        CommandSpec,
        register_command_input_recorder,
        dispatch_command_input_recorders,
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
