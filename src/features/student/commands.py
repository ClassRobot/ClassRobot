from typing import Optional

from utils import tip
from utils.roles import StudentRoleLang
from utils.config import priority, comp_config
from utils.commands import CommandBinding, on_agent_command
from utils.params.student import get_columns_chinese
from utils.helper import HelperScope, UserRole
from nonebot_plugin_alconna import Args, Field, Alconna, CommandMeta, MultiVar

query_cmd = on_agent_command(
    Alconna("查询学生信息", meta=CommandMeta(description="查看当前账号绑定的学生信息、班级、学号和附加资料。")),
    aliases={"学生信息", "我的学生信息"},
    binding=CommandBinding(
        roles={UserRole.student},
        scopes={HelperScope.student},
    ),
    block=True,
    priority=priority,
    comp_config=comp_config,
)

query_student_profile_cmd = on_agent_command(
    Alconna(
        "查询学生档案",
        Args["student_id?", Optional[int], Field(default=None, completion=tip("可选：学生ID"))],
    ),
    binding=CommandBinding(
        description="按权限查询学生档案；管理员可查全部，学院负责人和班级管理教师只能查管辖范围内学生。",
        roles={UserRole.admin, UserRole.teacher},
        scopes={HelperScope.teacher, HelperScope.admin},
        tags={"student", "query"},
        execution_mode="service",
        param_labels={"student_id": "学生ID"},
    ),
    block=True,
    priority=priority,
    comp_config=comp_config,
)

add_student_profile_cmd = on_agent_command(
    Alconna(
        "添加学生",
        Args["user_id", int, Field(completion=tip("请输入系统用户ID"))],
        Args["classes_id", int, Field(completion=tip("请输入班级ID"))],
        Args["name", str, Field(completion=tip("请输入学生姓名"))],
    ),
    aliases={"添加学生档案"},
    binding=CommandBinding(
        description="为指定系统用户创建学生档案并加入班级。",
        roles={UserRole.admin, UserRole.teacher},
        scopes={HelperScope.teacher, HelperScope.admin},
        risk_level="medium",
        agent_callable=False,
        param_labels={"user_id": "用户ID", "classes_id": "班级ID", "name": "学生姓名"},
    ),
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

set_student_profile_cmd = on_agent_command(
    Alconna(
        "修改学生档案",
        Args["student_id", int, Field(completion=tip("请输入学生ID"))],
        Args["values", MultiVar(str, flag="+"), Field(completion=tip("修改方式如 姓名=张三 学号=20250001"))],
    ),
    binding=CommandBinding(
        description="按权限修改学生档案，采用 key=value 形式传参。",
        roles={UserRole.admin, UserRole.teacher},
        scopes={HelperScope.teacher, HelperScope.admin},
        risk_level="medium",
        agent_callable=False,
        param_labels={"student_id": "学生ID", "values": "修改内容"},
    ),
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

delete_student_profile_cmd = on_agent_command(
    Alconna("删除学生", Args["student_id", int, Field(completion=tip("请输入学生ID"))]),
    aliases={"删除学生档案"},
    binding=CommandBinding(
        description="按权限删除学生档案；不会删除系统用户账号。",
        roles={UserRole.admin, UserRole.teacher},
        scopes={HelperScope.teacher, HelperScope.admin},
        risk_level="high",
        agent_callable=False,
        param_labels={"student_id": "学生ID"},
    ),
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

set_cmd = on_agent_command(
    Alconna(
        "修改学生信息",
        Args[
            "values",
            MultiVar(str, flag="+"),
            Field(
                completion=tip(
                    f"修改方式如名字=张三 性别=男\n可以修改的内容:\n {', '.join(get_columns_chinese(['user_id']).values())}"
                )
            ),
        ],
        meta=CommandMeta(
            description="按 键=值 的形式修改当前账号绑定的学生资料，例如姓名、学号、宿舍等。"
        ),
    ),
    aliases={"修改学生", "设置学生信息"},
    binding=CommandBinding(
        roles={UserRole.student},
        scopes={HelperScope.student},
        risk_level="medium",
        param_labels={"values": "修改内容"},
        param_descriptions={
            "values": "修改方式如名字=张三 性别=男，可修改内容包含学生资料和班干部角色。"
        },
    ),
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)


__helpers__ = [
    query_cmd.__helper__,
    query_student_profile_cmd.__helper__,
    add_student_profile_cmd.__helper__,
    set_student_profile_cmd.__helper__,
    delete_student_profile_cmd.__helper__,
    set_cmd.__helper__,
]
