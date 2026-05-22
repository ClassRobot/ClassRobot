from src.platform.config import priority
from src.platform.commands import CommandBinding, on_agent_command
from src.platform.helper import HelperScope, UserRole
from nonebot_plugin_alconna import Args, Alconna, MultiVar

from .util import columns_chinese

find_student_cmd = on_agent_command(
    Alconna("查找学生", Args["items", MultiVar(str, "+")]),
    aliases={"查询学生", "搜索学生"},
    binding=CommandBinding(
        description=(
            "查找自己班级的学生或同学，可以通过多个关键信息进行搜索。"
            "支持姓名、班级、宿舍等组合条件：" + "\\".join(columns_chinese)
        ),
        roles={UserRole.teacher, UserRole.student},
        scopes={HelperScope.student, HelperScope.teacher},
        param_labels={"items": "搜索条件"},
    ),
    priority=priority + 10,
    block=True,
)

at_cmd = on_agent_command(
    Alconna("at", Args["items", MultiVar(str, "+")]),
    aliases={"艾特"},
    binding=CommandBinding(
        description="根据关键信息搜索对应用户并 at 他们，搜索条件与“查找学生”一致。",
        roles={UserRole.teacher, UserRole.student},
        scopes={HelperScope.student, HelperScope.teacher},
        param_labels={"items": "搜索条件"},
    ),
    priority=priority,
    block=True,
)

__helpers__ = [
    find_student_cmd.__helper__,
    at_cmd.__helper__,
]
