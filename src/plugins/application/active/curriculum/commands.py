from src.shared import tip
from src.platform.config import priority, comp_config
from src.platform.helper import UserRole, HelperScope
from src.platform.commands import CommandBinding, on_agent_command
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
        meta=CommandMeta(description="添加自己的课表；一次命令只录入一条课程。" + input_help),
    ),
    binding=CommandBinding(
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
        meta=CommandMeta(description="按课表 ID 删除自己的课程，可一次删除多个。"),
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
        meta=CommandMeta(description=("查询本人或指定班级课表；可带天数，正数看未来，负数看过去。")),
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
        meta=CommandMeta(description="分享自己的课表；不带参数生成分享 ID，带参数读取指定分享。"),
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
