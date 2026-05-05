from types import ModuleType, SimpleNamespace


def test_spec_from_alconna_derives_params_and_helper_view(loaded_plugins):
    from arclet.alconna import Args, Alconna, MultiVar, CommandMeta
    from src.commands import CommandBinding, spec_from_alconna
    from utils.helper import HelperScope, ParamMode, UserRole
    from src.commands.renderers.helper import command_spec_to_helper

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
    from src.commands import CommandBinding, command_alconna, command_registry
    from utils.helper import HelperScope, ParamMode, UserRole

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


def test_bootstrap_helper_runtime_collects_matcher_bound_helpers(loaded_plugins):
    from arclet.alconna import Alconna, CommandMeta
    from src.commands import CommandBinding, command_alconna
    from utils.helper.config import helper_menu
    from utils.helper.runtime import bootstrap_helper_runtime

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
