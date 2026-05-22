from types import SimpleNamespace

import pytest


def register_test_service_spec(spec):
    from src.platform.commands import CommandResult, command_executor, command_registry
    from src.platform.commands.renderers.helper import command_spec_to_helper

    command_registry.register(spec)

    @command_executor.handler(spec.name)
    async def _handler(params, context):
        return CommandResult.ok("测试命令已执行。")

    return command_spec_to_helper(spec)


def test_command_tool_catalog_hides_matcher_and_unregistered_service_commands(loaded_plugins):
    from src.platform.helper import Helpers
    from src.platform.commands import CommandSpec, command_registry
    from src.platform.commands.renderers.helper import command_spec_to_helper
    from src.core.agent.runtime.command_tools import CommandToolCatalog

    matcher_spec = CommandSpec(
        name="测试仅用户命令",
        description="只能由用户直接触发",
        execution_mode="matcher",
    )
    service_without_handler_spec = CommandSpec(
        name="测试缺少Handler服务命令",
        description="声明为 service 但没有注册 handler",
        execution_mode="service",
    )
    command_registry.register(matcher_spec)
    command_registry.register(service_without_handler_spec)
    helpers = Helpers()
    helpers.extend([command_spec_to_helper(matcher_spec), command_spec_to_helper(service_without_handler_spec)])

    catalog = CommandToolCatalog.from_helpers(helpers)

    assert catalog.get("测试仅用户命令") is None
    assert catalog.get("测试缺少Handler服务命令") is None


@pytest.mark.asyncio
async def test_dispatch_auto_task_rejects_command_without_service_handler(loaded_plugins):
    from src.plugins.application.active import autogpt as autogpt_module
    from src.core.agent.runtime.schema import AutoTask
    from src.platform.commands import CommandSpec, command_registry

    command_registry.register(
        CommandSpec(
            name="测试未服务化命令",
            description="声明为 service 但未注册 handler 的命令",
            execution_mode="service",
        )
    )

    observations = await autogpt_module.dispatch_auto_task(
        AutoTask(command="测试未服务化命令", params=[]),
        SimpleNamespace(adapter="test", private=True, platform=[]),
        trace_id="autogpt-no-service",
    )

    assert len(observations) == 1
    assert observations[0].success is False
    assert observations[0].dispatch_type == "unsupported_command"
    assert "尚未接入统一 service 执行器" in observations[0].message


def test_command_tool_catalog_builds_safe_tool_schema(loaded_plugins):
    from src.platform.helper import Helpers, ParamMode
    from src.platform.commands import CommandParam, CommandSpec
    from src.core.agent.runtime.command_tools import CommandToolCatalog

    spec = CommandSpec(
        name="测试添加班级工具",
        description="添加一个班级",
        aliases={"测试新增班级工具"},
        params=[
            CommandParam(name="班级名", description="要添加的班级名称"),
            CommandParam(name="备注", description="可选备注", mode=ParamMode.OPTIONAL),
            CommandParam(name="标签", description="显式声明的可选标签", required=False),
        ],
        risk_level="medium",
        execution_mode="service",
    )
    helpers = Helpers()
    helpers.append(register_test_service_spec(spec))

    catalog = CommandToolCatalog.from_helpers(helpers)
    tool = catalog.get("测试添加班级工具")

    assert tool is not None
    assert tool.command == "测试添加班级工具"
    assert tool.name.startswith("command_")
    assert tool.risk_level == "medium"
    assert catalog.get("测试新增班级工具") is tool
    assert catalog.get(tool.name) is tool
    assert catalog.resolve_commands(["测试新增班级工具", tool.name]) == {"测试添加班级工具"}

    openai_tool = tool.to_openai_tool()
    function = openai_tool["function"]
    assert function["name"] == tool.name
    assert function["parameters"]["required"] == ["班级名"]
    assert "备注" in function["parameters"]["properties"]
    assert "标签" in function["parameters"]["properties"]


def test_command_tool_catalog_prompt_is_compact(loaded_plugins):
    from src.platform.helper import Helpers
    from src.platform.commands import CommandSpec
    from src.core.agent.runtime.command_tools import CommandToolCatalog

    spec = CommandSpec(name="测试提示工具", description="添加一个班级", execution_mode="service")
    helpers = Helpers()
    helpers.append(register_test_service_spec(spec))

    catalog = CommandToolCatalog.from_helpers(helpers)
    prompt = catalog.to_prompt()

    assert prompt.startswith("- 测试提示工具: 添加一个班级")
    assert "工具名" not in prompt
    assert "真实命令" not in prompt
    assert "参数=" in prompt
    assert str(catalog) == prompt


def test_command_tool_catalog_does_not_filter_by_query(loaded_plugins):
    from src.platform.helper import Helpers
    from src.platform.commands import CommandSpec
    from src.core.agent.runtime.command_tools import CommandToolCatalog

    specs = [
        CommandSpec(name="测试创建通知工具", description="给班级创建一条通知", execution_mode="service"),
        CommandSpec(name="测试查询课表工具", description="查看当前课表", execution_mode="service"),
        CommandSpec(name="测试我的信息工具", description="查看当前用户身份", execution_mode="service"),
    ]
    helpers = Helpers()
    for spec in specs:
        helpers.append(register_test_service_spec(spec))

    catalog = CommandToolCatalog.from_helpers(helpers)
    prompt = catalog.to_prompt()

    assert "测试创建通知工具" in prompt
    assert "测试查询课表工具" in prompt
    assert "测试我的信息工具" in prompt


def test_command_tool_catalog_candidate_commands_can_narrow_visible_subset(loaded_plugins):
    from src.platform.helper import Helpers
    from src.platform.commands import CommandSpec
    from src.core.agent.runtime.command_tools import CommandToolCatalog

    specs = [
        CommandSpec(name="测试候选创建通知", description="给班级创建一条通知", execution_mode="service"),
        CommandSpec(name="测试候选查询课表", description="查看当前课表", execution_mode="service"),
    ]
    helpers = Helpers()
    for spec in specs:
        helpers.append(register_test_service_spec(spec))

    catalog = CommandToolCatalog.from_helpers(helpers)
    prompt = catalog.to_prompt(
        limit=1,
        candidate_commands=["测试候选查询课表"],
    )

    assert "测试候选查询课表" in prompt
    assert "测试候选创建通知" not in prompt


def test_command_tool_catalog_infers_high_risk_commands(loaded_plugins):
    from src.platform.helper import Helpers
    from src.platform.commands import CommandSpec
    from src.core.agent.runtime.command_tools import CommandToolCatalog

    spec = CommandSpec(
        name="测试清空聊天工具",
        description="清空机器人与用户的聊天内容",
        risk_level="high",
        execution_mode="service",
    )
    helpers = Helpers()
    helpers.append(register_test_service_spec(spec))

    catalog = CommandToolCatalog.from_helpers(helpers)
    tool = catalog.get("测试清空聊天工具")

    assert tool is not None
    assert tool.risk_level == "high"


def test_basic_commands_are_available_to_autogpt_command_tools(loaded_plugins):
    from src.platform.helper import Helpers
    from src.core.agent.runtime.command_tools import CommandToolCatalog
    from tests.commands.test_helper_metadata import collect_helpers

    helper_menu = Helpers()
    helper_menu.extend(collect_helpers())
    catalog = CommandToolCatalog.from_helpers(helper_menu)

    from src.platform.commands.registry import command_registry

    for helper in collect_helpers():
        spec = command_registry.get(helper.command)
        if spec is None or not spec.agent_callable or spec.execution_mode != "service":
            assert catalog.get(helper.command) is None
            continue
        tool = catalog.get(helper.command)
        assert tool is not None
        assert tool.command == helper.command
        assert tool.name.startswith("command_")
        assert helper.command in catalog.resolve_commands([helper.command, tool.name])


def test_write_commands_are_not_marked_low_risk(loaded_plugins):
    from src.platform.helper import Helpers
    from src.core.agent.runtime.command_tools import CommandToolCatalog
    from tests.commands.test_helper_metadata import collect_helpers

    helper_menu = Helpers()
    helper_menu.extend(collect_helpers())
    catalog = CommandToolCatalog.from_helpers(helper_menu)

    from src.platform.commands.registry import command_registry

    write_prefixes = ("添加", "修改", "删除", "创建", "提交", "导入", "退出", "加入", "请假", "注销", "设置")
    for helper in collect_helpers():
        spec = command_registry.get(helper.command)
        if spec is None or not spec.agent_callable or spec.execution_mode != "service":
            continue
        if helper.command.startswith(write_prefixes):
            tool = catalog.get(helper.command)
            assert tool is not None
            assert tool.risk_level in {"medium", "high"}


def test_command_tool_catalog_follows_current_user_visible_helpers(loaded_plugins):
    from src.platform.helper import HelperScope, Helpers, UserRole
    from src.platform.commands import CommandSpec
    from src.core.agent.runtime.command_tools import CommandToolCatalog

    student_spec = CommandSpec(
        name="测试学生可见工具",
        description="查看学生",
        roles={UserRole.student},
        scopes={HelperScope.student},
        execution_mode="service",
    )
    teacher_spec = CommandSpec(
        name="测试教师可见工具",
        description="查看教师",
        roles={UserRole.teacher},
        scopes={HelperScope.teacher},
        execution_mode="service",
    )
    shared_spec = CommandSpec(
        name="测试师生共享工具",
        description="查看请假",
        roles={UserRole.student, UserRole.teacher},
        execution_mode="service",
    )
    helpers = Helpers()
    for spec in (student_spec, teacher_spec, shared_spec):
        helpers.append(register_test_service_spec(spec))

    student_catalog = CommandToolCatalog.from_helpers(helpers.get_roles_helpers(UserRole.user, UserRole.student))
    teacher_catalog = CommandToolCatalog.from_helpers(helpers.get_roles_helpers(UserRole.user, UserRole.teacher))

    assert student_catalog.get("测试学生可见工具") is not None
    assert student_catalog.get("测试师生共享工具") is not None
    assert student_catalog.get("测试教师可见工具") is None

    assert teacher_catalog.get("测试教师可见工具") is not None
    assert teacher_catalog.get("测试师生共享工具") is not None
    assert teacher_catalog.get("测试学生可见工具") is None


def test_query_classes_tool_uses_service_command_spec(loaded_plugins):
    from src.platform.helper import Helpers
    from src.platform.commands.registry import command_registry
    from src.core.agent.runtime.command_tools import CommandToolCatalog
    from tests.commands.test_helper_metadata import collect_helpers

    helper_menu = Helpers()
    helper_menu.extend(collect_helpers())
    catalog = CommandToolCatalog.from_helpers(helper_menu)
    spec = command_registry.get("查询班级")
    tool = catalog.get("我的班级")

    assert spec is not None
    assert spec.execution_mode == "service"
    assert spec.plugin_module == "src.plugins.application.active.classes.commands"
    assert tool is not None
    assert tool.command == "查询班级"
    assert [param.name for param in tool.params] == ["班级ID"]
