from utils import tip
from utils.config import priority, comp_config
from utils.commands import CommandBinding, on_agent_command
from utils.helper import HelperScope, UserRole
from nonebot_plugin_alconna import Args, Field, Alconna, MultiVar, CommandMeta

input_help = """具体输入格式如下:

[周期] [星期几] [第几节课] [课程名称] [教室(可选)] [老师(可选)]

例如:

> 1-12 1 1-2 数学 一教101 张三

其中[周期][星期几][第几节课]可以有多种表示方式:

- 使用`-`表示连续的范围
- 使用`,`表示多个范围
- 使用`+n`表示间隔的范围

例如:

- 1-12 表示1到12
- 1,3,5 表示1,3,5
- 2-6+1 可以表示双数,得到2,4,6
- 1-5+1,6 表示1,3,5,6
"""

add_curricula = on_agent_command(
    Alconna(
        "添加课表",
        Args[
            "values",
            MultiVar(str, flag="+"),
            Field(completion=tip("课表内容不能为空" + input_help)),
        ],
        meta=CommandMeta(description="添加学生自己的的课表,一条命令只能写入一次课表" + input_help),
    ),
    binding=CommandBinding(
        ai_description="添加学生自己的的课表,一条命令只能写入一次课表,如果机器人要加两次课表请分开两次命令执行.",
        roles={UserRole.user},
        scopes={HelperScope.user},
        risk_level="medium",
        param_labels={"values": "课表内容"},
    ),
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)
del_curricula = on_agent_command(
    Alconna(
        "删除课表",
        Args[
            "values",
            MultiVar(str, flag="+"),
            Field(completion=tip("请输入课表ID")),
        ],
        meta=CommandMeta(description="删除自己的课表,一次可以删除多个课表,只需要输入课表ID即可"),
    ),
    binding=CommandBinding(
        roles={UserRole.user},
        scopes={HelperScope.user},
        risk_level="high",
        param_labels={"values": "课表ID"},
    ),
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)
query_curricula = on_agent_command(
    Alconna(
        "查询课表",
        Args["classes?", str | None],
        Args["day?", int, Field(default=0)],
        meta=CommandMeta(
            description=(
                "可以通过班级名称日期来查询课表,在不写班级名称的情况下查询的是本人课表,班级名称后面携带数字，如果是正数表示后面几天，如果是复数表示前面几天。"
            )
        ),
    ),
    aliases={"查看课表", "课表查询", "我的课表"},
    binding=CommandBinding(
        roles={UserRole.user},
        scopes={HelperScope.user},
        param_labels={"classes": "班级名称", "day": "天数"},
    ),
    block=True,
    priority=priority,
)
share_curricula = on_agent_command(
    Alconna(
        "分享课表",
        Args["share_id?", str | None],
        meta=CommandMeta(description="分享自己的课表给其他人,如果没有参数则生成自己的share_id,如果有参数则获取指定的课表"),
    ),
    aliases={"分享课程表", "分享课程", "共享课程", "共享课表", "绑定课表"},
    binding=CommandBinding(
        roles={UserRole.user},
        scopes={HelperScope.user},
        risk_level="medium",
        param_labels={"share_id": "分享ID/班级名称"},
    ),
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

set_week_cmd = on_agent_command(
    Alconna(
        "设置当前周",
        Args["week", int],
        Args["classes_id?", int | None],
        meta=CommandMeta(description="设置自己的课表当前周；若具备班级课表管理能力，也可额外指定班级ID。"),
    ),
    binding=CommandBinding(
        roles={UserRole.user},
        scopes={HelperScope.user},
        risk_level="medium",
        param_labels={"week": "周数", "classes_id": "班级ID"},
    ),
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

__helpers__ = [
    add_curricula.__helper__,
    del_curricula.__helper__,
    query_curricula.__helper__,
    share_curricula.__helper__,
    set_week_cmd.__helper__,
]
