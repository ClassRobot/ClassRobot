from typing import Optional

from src.shared import tip
from src.platform.config import priority, comp_config
from src.platform.commands import CommandBinding, on_agent_command
from src.platform.helper import HelperScope, UserRole
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

query_teacher_profile_cmd = on_agent_command(
    Alconna(
        "查询教师",
        Args["teacher_id?", Optional[int], Field(default=None, completion=tip("可选：教师ID"))],
    ),
    binding=CommandBinding(
        description="按权限查询教师档案；管理员可查全部，学院负责人可查本学院教师。",
        roles={UserRole.admin, UserRole.teacher},
        scopes={HelperScope.teacher, HelperScope.admin},
        tags={"teacher", "query"},
        execution_mode="service",
        param_labels={"teacher_id": "教师ID"},
    ),
    block=True,
    priority=priority,
    comp_config=comp_config,
)

add_teacher_profile_cmd = on_agent_command(
    Alconna(
        "添加教师",
        Args["user_id", int, Field(completion=tip("请输入系统用户ID"))],
        Args["name", str, Field(completion=tip("请输入教师姓名"))],
        Args["school_name?", Optional[str], Field(default=None, completion=tip("可选：学校名称"))],
        Args["college_name?", Optional[str], Field(default=None, completion=tip("可选：学院名称"))],
    ),
    aliases={"添加教师档案"},
    binding=CommandBinding(
        description="为指定系统用户创建教师档案；管理员可全局创建，学院负责人只能创建本学院教师。",
        roles={UserRole.admin, UserRole.teacher},
        scopes={HelperScope.teacher, HelperScope.admin},
        risk_level="medium",
        agent_callable=False,
        param_labels={"user_id": "用户ID", "name": "教师姓名", "school_name": "学校名称", "college_name": "学院名称"},
    ),
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

set_teacher_profile_cmd = on_agent_command(
    Alconna(
        "修改教师档案",
        Args["teacher_id", int, Field(completion=tip("请输入教师ID"))],
        Args["values", MultiVar(str, flag="+"), Field(completion=tip("修改方式如 姓名=张老师 学院=计算机学院"))],
    ),
    binding=CommandBinding(
        description="按权限修改教师档案，采用 key=value 形式传参。",
        roles={UserRole.admin, UserRole.teacher},
        scopes={HelperScope.teacher, HelperScope.admin},
        risk_level="medium",
        agent_callable=False,
        param_labels={"teacher_id": "教师ID", "values": "修改内容"},
    ),
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

delete_teacher_profile_cmd = on_agent_command(
    Alconna("删除教师", Args["teacher_id", int, Field(completion=tip("请输入教师ID"))]),
    aliases={"删除教师档案"},
    binding=CommandBinding(
        description="按权限删除教师档案；不会删除系统用户账号。",
        roles={UserRole.admin, UserRole.teacher},
        scopes={HelperScope.teacher, HelperScope.admin},
        risk_level="high",
        agent_callable=False,
        param_labels={"teacher_id": "教师ID"},
    ),
    block=True,
    priority=priority,
    skip_for_unmatch=False,
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
    query_teacher_profile_cmd.__helper__,
    add_teacher_profile_cmd.__helper__,
    set_teacher_profile_cmd.__helper__,
    delete_teacher_profile_cmd.__helper__,
    set_teacher_cmd.__helper__,
]
