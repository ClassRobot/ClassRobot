from utils import tip
from utils.config import priority, comp_config
from utils.commands import CommandBinding, on_agent_command
from utils.helper import HelperScope, UserRole
from nonebot_plugin_alconna import Args, Field, Alconna, CommandMeta, MultiVar

query_teacher_cmd = on_agent_command(
    Alconna("查询教师信息", meta=CommandMeta(description="查询当前账号绑定的教师信息和所管理的班级。")),
    aliases={"教师信息", "我的教师信息"},
    binding=CommandBinding(
        roles={UserRole.teacher},
        scopes={HelperScope.teacher},
    ),
    block=True,
    priority=priority,
    comp_config=comp_config,
)

set_teacher_cmd = on_agent_command(
    Alconna(
        "修改教师信息",
        Args[
            "values",
            MultiVar(str, flag="+"),
            Field(completion=tip("修改方式如 姓名=张老师 学校=某大学 学院=计算机学院")),
        ],
        meta=CommandMeta(
            description="修改教师姓名、学校、学院；若当前账号尚未绑定教师身份，则会在校验通过后自动创建教师信息。"
        ),
    ),
    aliases={"修改教师", "设置教师信息"},
    binding=CommandBinding(
        roles={UserRole.user, UserRole.teacher},
        exclude_roles={UserRole.student},
        scopes={HelperScope.teacher},
        risk_level="medium",
        param_labels={"values": "修改内容"},
        param_descriptions={"values": "修改方式如 姓名=张老师 学校=某大学 学院=计算机学院"},
    ),
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)


__helpers__ = [
    query_teacher_cmd.__helper__,
    set_teacher_cmd.__helper__,
]
