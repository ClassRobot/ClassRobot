def test_command_tool_catalog_builds_safe_tool_schema(loaded_plugins):
    from utils.helper import Helper, Helpers, Param, ParamMode
    from src.plugins.autogpt.command_tools import CommandToolCatalog

    helpers = Helpers()
    helpers.append(
        Helper(
            command="添加班级",
            description="添加一个班级",
            aliases={"新增班级"},
            params=[
                Param(name="班级名", description="要添加的班级名称"),
                Param(name="备注", description="可选备注", mode=ParamMode.OPTIONAL),
            ],
        )
    )

    catalog = CommandToolCatalog.from_helpers(helpers)
    tool = catalog.get("添加班级")

    assert tool is not None
    assert tool.command == "添加班级"
    assert tool.name.startswith("command_")
    assert tool.risk_level == "medium"
    assert catalog.get("新增班级") is tool
    assert catalog.get(tool.name) is tool
    assert catalog.resolve_commands(["新增班级", tool.name]) == {"添加班级"}

    openai_tool = tool.to_openai_tool()
    function = openai_tool["function"]
    assert function["name"] == tool.name
    assert function["parameters"]["required"] == ["班级名"]
    assert "备注" in function["parameters"]["properties"]


def test_command_tool_catalog_infers_high_risk_commands(loaded_plugins):
    from utils.helper import Helper, Helpers
    from src.plugins.autogpt.command_tools import CommandToolCatalog

    helpers = Helpers()
    helpers.append(Helper(command="清空聊天", description="清空机器人与用户的聊天内容"))

    catalog = CommandToolCatalog.from_helpers(helpers)
    tool = catalog.get("清空聊天")

    assert tool is not None
    assert tool.risk_level == "high"


def test_basic_commands_are_available_to_autogpt_command_tools(loaded_plugins):
    from utils.helper import Helpers
    from src.plugins.autogpt.command_tools import CommandToolCatalog
    from tests.commands.test_helper_metadata import collect_helpers

    helper_menu = Helpers()
    helper_menu.extend(collect_helpers())
    catalog = CommandToolCatalog.from_helpers(helper_menu)

    for helper in collect_helpers():
        tool = catalog.get(helper.command)
        assert tool is not None
        assert tool.command == helper.command
        assert tool.name.startswith("command_")
        assert helper.command in catalog.resolve_commands([helper.command, tool.name])


def test_write_commands_are_not_marked_low_risk(loaded_plugins):
    from utils.helper import Helpers
    from src.plugins.autogpt.command_tools import CommandToolCatalog
    from tests.commands.test_helper_metadata import collect_helpers

    helper_menu = Helpers()
    helper_menu.extend(collect_helpers())
    catalog = CommandToolCatalog.from_helpers(helper_menu)

    write_prefixes = ("添加", "修改", "删除", "创建", "提交", "导入", "退出", "加入", "请假", "注销", "设置")
    for helper in collect_helpers():
        if helper.command.startswith(write_prefixes):
            tool = catalog.get(helper.command)
            assert tool is not None
            assert tool.risk_level in {"medium", "high"}


def test_command_tool_catalog_follows_current_user_visible_helpers(loaded_plugins):
    from utils.helper import Helper, HelperScope, Helpers, UserRole
    from src.plugins.autogpt.command_tools import CommandToolCatalog

    helpers = Helpers()
    helpers.extend(
        [
            Helper(
                command="查询学生信息", description="查看学生", roles={UserRole.student}, scopes={HelperScope.student}
            ),
            Helper(
                command="查询教师信息", description="查看教师", roles={UserRole.teacher}, scopes={HelperScope.teacher}
            ),
            Helper(command="查询请假", description="查看请假", roles={UserRole.student, UserRole.teacher}),
        ]
    )

    student_catalog = CommandToolCatalog.from_helpers(helpers.get_roles_helpers(UserRole.user, UserRole.student))
    teacher_catalog = CommandToolCatalog.from_helpers(helpers.get_roles_helpers(UserRole.user, UserRole.teacher))

    assert student_catalog.get("查询学生信息") is not None
    assert student_catalog.get("查询请假") is not None
    assert student_catalog.get("查询教师信息") is None

    assert teacher_catalog.get("查询教师信息") is not None
    assert teacher_catalog.get("查询请假") is not None
    assert teacher_catalog.get("查询学生信息") is None
