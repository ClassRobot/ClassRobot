import importlib
import re

from nonebot.internal.matcher.matcher import MatcherMeta

EXPECTED_COMMAND_OBJECTS = {
    "src.features.classes.commands": {
        "import_classes_cmd": "导入班级",
        "create_classes_cmd": "添加班级",
        "delete_classes_cmd": "删除班级",
        "query_classes_cmd": "查询班级",
        "query_join_request_cmd": "查询入班申请",
        "review_join_request_cmd": "处理入班申请",
        "join_classes_cmd": "加入班级",
        "set_join_classes_cmd": "修改班级加入方式",
        "exit_classes_cmd": "退出班级",
    },
    "src.features.group.commands": {
        "add_school": "添加学校",
        "set_school": "修改学校",
        "delete_school": "删除学校",
        "add_college": "添加学院",
        "set_college": "修改学院",
        "delete_college": "删除学院",
        "add_major": "添加专业",
        "set_major": "修改专业",
        "delete_major": "删除专业",
        "add_organization": "添加组织",
        "set_organization": "修改组织",
        "delete_organization": "删除组织",
        "query_structure": "查询组织架构",
        "query_organization": "查询组织",
        "join_organization": "加入组织",
        "exit_organization": "退出组织",
    },
    "src.features.student.commands": {
        "query_cmd": "查询学生信息",
        "set_cmd": "修改学生信息",
    },
    "src.features.teacher.commands": {
        "query_teacher_cmd": "查询教师信息",
        "set_teacher_cmd": "修改教师信息",
    },
    "src.features.user.commands": {
        "self_info_cmd": "我的信息",
        "bind_user_cmd": "绑定用户",
        "logout_cmd": "注销",
        "token_cmd": "token",
    },
    "src.features.curriculum.commands": {
        "add_curricula": "添加课表",
        "del_curricula": "删除课表",
        "query_curricula": "查询课表",
        "share_curricula": "分享课表",
        "set_week_cmd": "设置当前周",
    },
    "src.features.find_at.commands": {
        "find_student_cmd": "查找学生",
        "at_cmd": "at",
    },
    "src.features.leave.commands": {
        "add_leave_cmd": "请假",
        "query_leave_cmd": "请假列表",
        "set_leave_push_cmd": "设置请假推送",
        "delete_leave_cmd": "删除请假",
    },
    "src.features.notice.commands": {
        "notice_cmd": "创建通知",
        "query_notice_cmd": "查询通知",
        "delete_notice_cmd": "删除通知",
    },
    "src.features.tasks.commands": {
        "push_task_cmd": "提交任务",
        "create_task_cmd": "创建任务",
        "delete_task_cmd": "删除任务",
        "export_task_cmd": "导出任务",
        "query_task_cmd": "查询任务",
    },
    "src.features.file_manager.commands": {
        "pwd_cmd": "pwd",
        "ls_cmd": "ls",
        "cd_cmd": "cd",
        "mkdir_cmd": "mkdir",
        "touch_cmd": "touch",
        "rm_cmd": "rm",
        "cat_cmd": "cat",
        "find_cmd": "find",
        "grep_cmd": "grep",
        "tree_cmd": "tree",
        "upload_file_cmd": "上传文件",
    },
    "src.features.chat_context.commands": {
        "query_group_history_cmd": "检索群聊记录",
    },
    "src.features.helper.commands": {"help_cmd": "help"},
    "src.features.autogpt.commands": {"clear_chat": "清空聊天"},
}

EXPECTED_RULE_ALIASES = {
    ("src.features.notice.commands", "notice_cmd"): {"创建通知", "定时", "转发"},
    ("src.features.user.commands", "token_cmd"): {"token"},
}


def _iter_matchers(module):
    for name, value in vars(module).items():
        if not isinstance(value, MatcherMeta):
            continue
        if getattr(value, "module_name", None) != module.__name__:
            continue
        command_path = getattr(value, "_command_path", "")
        if command_path or _extract_rule_literals(value):
            yield name, value


def _extract_main_command(matcher) -> str:
    command_path = getattr(matcher, "_command_path", "")
    if isinstance(command_path, str) and command_path:
        return command_path.split("::", 1)[-1]
    raise AssertionError(f"matcher {matcher} 不支持通过 _command_path 提取主命令")


def _extract_rule_literals(matcher) -> set[str]:
    rule_text = str(getattr(matcher, "rule", ""))
    return set(re.findall(r"\('([^']+)',\)", rule_text))


def test_all_command_modules_register_expected_matcher_objects(loaded_plugins):
    for module_name, expected_commands in EXPECTED_COMMAND_OBJECTS.items():
        module = importlib.import_module(module_name)
        actual_matchers = dict(_iter_matchers(module))

        assert set(actual_matchers) == set(expected_commands)
        assert {matcher.module_name for matcher in actual_matchers.values()} == {module_name}
        assert {matcher.plugin_name for matcher in actual_matchers.values()}

        for object_name, expected_command in expected_commands.items():
            matcher = actual_matchers[object_name]
            if hasattr(matcher, "_command_path") and isinstance(getattr(matcher, "_command_path", ""), str):
                assert _extract_main_command(matcher) == expected_command
            else:
                assert expected_command in _extract_rule_literals(matcher)


def test_command_rules_keep_expected_literals(loaded_plugins):
    for (module_name, object_name), expected_literals in EXPECTED_RULE_ALIASES.items():
        module = importlib.import_module(module_name)
        matcher = getattr(module, object_name)
        assert expected_literals.issubset(_extract_rule_literals(matcher))
