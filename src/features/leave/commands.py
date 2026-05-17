from utils import tip
from utils.config import priority, comp_config
from utils.commands import CommandBinding, on_agent_command
from utils.helper import HelperScope, UserRole
from nonebot_plugin_alconna import Args, Field, Image, Alconna, MultiVar

add_leave_cmd = on_agent_command(
    Alconna(
        "请假",
        Args[
            "leave_reason",
            MultiVar(str | Image, "+"),
            Field(completion=tip("请告诉我请假原因,时间等信息,如果有请假条也可以直接发请假条照片给我,一张图片即可!")),
        ],
    ),
    binding=CommandBinding(
        description="请告诉我请假原因、时间等信息，如果有请假条图片也可以一并发送。",
        roles={UserRole.student},
        scopes={HelperScope.student},
        agent_callable=False,
        execution_mode="interactive",
        param_labels={"leave_reason": "请假内容"},
        param_descriptions={"leave_reason": "请假原因、时间说明以及可选的请假条图片。"},
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

query_leave_cmd = on_agent_command(
    Alconna("请假列表"),
    aliases={"查询请假"},
    binding=CommandBinding(
        description="查询自己发布的请假；班干部或教师可查看自己班级内的请假记录。",
        roles={UserRole.student, UserRole.teacher, UserRole.class_cadre},
        scopes={HelperScope.student, HelperScope.teacher},
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

set_leave_push_cmd = on_agent_command(
    Alconna(
        "设置请假推送",
        Args[
            "push_list",
            MultiVar(str, "+"),
            Field(completion=tip("您希望推送给哪几个班干部")),
        ],
    ),
    binding=CommandBinding(
        description="设置请假消息需要推送给哪些班干部。",
        roles={UserRole.teacher},
        scopes={HelperScope.teacher},
        risk_level="medium",
        agent_callable=False,
        param_labels={"push_list": "推送对象"},
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

delete_leave_cmd = on_agent_command(
    Alconna(
        "删除请假",
        Args[
            "leave_id",
            MultiVar(str, "+"),
            Field(completion=tip("请输入要删除的请假条ID")),
        ],
    ),
    binding=CommandBinding(
        description="删除自己发布的请假；班干部或教师可删除自己有权限管理的请假记录。",
        roles={UserRole.student, UserRole.teacher, UserRole.class_cadre},
        scopes={HelperScope.student, HelperScope.teacher},
        risk_level="high",
        agent_callable=False,
        param_labels={"leave_id": "请假条ID"},
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

__helpers__ = [
    add_leave_cmd.__helper__,
    query_leave_cmd.__helper__,
    set_leave_push_cmd.__helper__,
    delete_leave_cmd.__helper__,
]
