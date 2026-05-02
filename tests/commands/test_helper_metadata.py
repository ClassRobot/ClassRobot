import importlib


BASIC_HELPER_MODULES = {
    "src.managers.group.commands": {
        "添加学校",
        "修改学校",
        "删除学校",
        "添加学院",
        "修改学院",
        "删除学院",
        "添加专业",
        "修改专业",
        "删除专业",
        "添加组织",
        "修改组织",
        "删除组织",
        "查询组织架构",
        "查询组织",
        "加入组织",
        "退出组织",
    },
    "src.managers.classes.commands": {
        "添加班级",
        "查询班级",
        "查询入班申请",
        "处理入班申请",
        "加入班级",
        "导入班级",
        "退出班级",
        "删除班级",
        "修改班级加入方式",
    },
    "src.managers.student.commands": {"查询学生信息", "修改学生信息"},
    "src.managers.teacher.commands": {"查询教师信息", "修改教师信息"},
    "src.managers.user.commands": {"我的信息", "绑定用户", "注销"},
    "src.plugins.curriculum.commands": {"添加课表", "删除课表", "查询课表", "分享课表"},
    "src.plugins.campus_map.commands": {"校园地图"},
    "src.plugins.find_at.commands": {"查找学生", "at"},
    "src.plugins.leave.commands": {"请假", "查询请假", "设置请假推送", "删除请假"},
    "src.plugins.tasks.commands": {"提交任务", "创建任务", "删除任务", "导出任务", "查询任务"},
}


def collect_helpers():
    helpers = []
    for module_name in BASIC_HELPER_MODULES:
        module = importlib.import_module(module_name)
        helpers.extend(getattr(module, "__helpers__", []))
    return helpers


def test_basic_command_helpers_are_complete(loaded_plugins):
    for module_name, expected_commands in BASIC_HELPER_MODULES.items():
        module = importlib.import_module(module_name)
        helpers = getattr(module, "__helpers__", [])
        commands = {helper.command for helper in helpers}

        assert commands == expected_commands
        assert all(helper.description for helper in helpers)


def test_basic_command_helpers_can_be_indexed_by_command_and_alias(loaded_plugins):
    from utils.helper import Helpers

    helper_menu = Helpers()
    helper_menu.extend(collect_helpers())

    for helper in collect_helpers():
        assert helper_menu.get_helper(helper.command) is helper
        for alias in helper.aliases:
            assert helper_menu.get_helper(alias) is helper


def test_write_command_helpers_are_marked_by_name(loaded_plugins):
    write_prefixes = ("添加", "修改", "删除", "创建", "提交", "导入", "退出", "加入", "请假", "注销", "设置")
    write_commands = []
    for helper in collect_helpers():
        if helper.command.startswith(write_prefixes):
            write_commands.append(helper.command)

    assert "添加班级" in write_commands
    assert "删除任务" in write_commands
    assert "注销" in write_commands
