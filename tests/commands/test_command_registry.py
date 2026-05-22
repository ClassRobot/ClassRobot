import importlib
import re

from nonebot.internal.matcher.matcher import MatcherMeta

EXPECTED_COMMAND_OBJECTS = {
    "src.plugins.application.active.classes.commands": {
        "import_classes_cmd": "导入班级",
        "create_classes_cmd": "添加班级",
        "delete_classes_cmd": "删除班级",
        "query_classes_cmd": "查询班级",
        "query_join_request_cmd": "查询入班申请",
        "review_join_request_cmd": "处理入班申请",
        "set_class_teacher_cmd": "设置班级教师",
        "unset_class_teacher_cmd": "取消班级教师",
        "set_student_position_cmd": "设置学生岗位",
        "unset_student_position_cmd": "取消学生岗位",
        "join_classes_cmd": "加入班级",
        "set_join_classes_cmd": "修改班级加入方式",
        "exit_classes_cmd": "退出班级",
    },
    "src.plugins.application.active.group.commands": {
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
        "set_college_manager": "设置学院负责人",
        "unset_college_manager": "取消学院负责人",
    },
    "src.plugins.application.active.student.commands": {
        "query_cmd": "查询学生信息",
        "query_student_profile_cmd": "查询学生档案",
        "add_student_profile_cmd": "添加学生",
        "set_student_profile_cmd": "修改学生档案",
        "delete_student_profile_cmd": "删除学生",
        "set_cmd": "修改学生信息",
    },
    "src.plugins.application.active.teacher.commands": {
        "query_teacher_cmd": "查询教师信息",
        "query_teacher_profile_cmd": "查询教师",
        "add_teacher_profile_cmd": "添加教师",
        "set_teacher_profile_cmd": "修改教师档案",
        "delete_teacher_profile_cmd": "删除教师",
        "set_teacher_cmd": "修改教师信息",
    },
    "src.plugins.application.active.user.commands": {
        "self_info_cmd": "我的信息",
        "bind_user_cmd": "绑定用户",
        "logout_cmd": "注销",
        "token_cmd": "token",
    },
    "src.plugins.application.active.curriculum.commands": {
        "add_curricula": "添加课表",
        "del_curricula": "删除课表",
        "query_curricula": "查询课表",
        "share_curricula": "分享课表",
        "set_week_cmd": "设置当前周",
    },
    "src.plugins.application.active.find_at.commands": {
        "find_student_cmd": "查找学生",
        "at_cmd": "at",
    },
    "src.plugins.application.active.leave.commands": {
        "add_leave_cmd": "请假",
        "query_leave_cmd": "请假列表",
        "set_leave_push_cmd": "设置请假推送",
        "delete_leave_cmd": "删除请假",
    },
    "src.plugins.application.active.notice.commands": {
        "notice_cmd": "创建通知",
        "query_notice_cmd": "查询通知",
        "delete_notice_cmd": "删除通知",
    },
    "src.plugins.application.active.tasks.commands": {
        "push_task_cmd": "提交任务",
        "create_task_cmd": "创建任务",
        "delete_task_cmd": "删除任务",
        "export_task_cmd": "导出任务",
        "query_task_cmd": "查询任务",
    },
    "src.plugins.application.active.file_manager.commands": {
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
    "src.plugins.library.message_history.commands": {
        "query_group_history_cmd": "检索群聊记录",
        "chat_statistics_cmd": "统计聊天记录",
    },
    "src.plugins.application.active.helper.commands": {"help_cmd": "help"},
    "src.plugins.application.active.autogpt.commands": {"clear_chat": "清空聊天"},
}

EXPECTED_RULE_ALIASES = {
    ("src.plugins.application.active.notice.commands", "notice_cmd"): {"创建通知", "定时", "转发"},
    ("src.plugins.application.active.user.commands", "token_cmd"): {"token"},
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


def test_command_param_required_can_be_explicit_or_inferred():
    from src.platform.helper import ParamMode
    from src.platform.commands import CommandParam

    assert CommandParam(name="必填参数").required is True
    assert CommandParam(name="可选参数", mode=ParamMode.OPTIONAL).required is False
    assert CommandParam(name="多值可选参数", mode=ParamMode.ZERO_OR_MORE).required is False
    assert CommandParam(name="显式可选参数", required=False).required is False
