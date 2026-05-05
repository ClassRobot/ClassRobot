from utils import tip
from utils.roles import StudentRoleLang
from utils.config import priority, comp_config
from src.commands import CommandBinding, command_alconna
from utils.params.student import get_columns_chinese
from utils.helper import Param, Helper, HelperScope, UserRole, ParamMode
from nonebot_plugin_alconna import Args, Field, Alconna, CommandMeta, MultiVar

query_cmd = command_alconna(
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

set_cmd = command_alconna(
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
    ),
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)


__helpers__ = [
    Helper(
        command="查询学生信息",
        description="查看当前账号绑定的学生信息、班级、学号和附加资料。",
        aliases={"学生信息", "我的学生信息"},
        roles={UserRole.student},
        scopes={HelperScope.student},
    ),
    Helper(
        command="修改学生信息",
        description=f"修改方式如名字=张三 性别=男\n可以修改的内容:\n {', '.join(get_columns_chinese(['user_id']).values())}\n其中班干部包括:\n"
        + ", ".join(StudentRoleLang._member_names_),
        aliases={"修改学生", "设置学生信息"},
        params=[
            Param(
                name="values",
                mode=ParamMode.ONE_OR_MORE,
                description="修改方式如名字=张三 性别=男",
            ),
        ],
        roles={UserRole.student},
        scopes={HelperScope.student},
    ),
]
