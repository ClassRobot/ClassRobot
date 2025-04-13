from utils import tip
from utils.config import priority, comp_config
from utils.helper import Param, Helper, ParamMode
from nonebot_plugin_alconna import Args, Field, Alconna, MultiVar, on_alconna

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

add_curricula = on_alconna(
    Alconna(
        "添加课表",
        Args[
            "values",
            MultiVar(str, flag="+"),
            Field(completion=tip("课表内容不能为空" + input_help)),
        ],
    ),
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)
del_curricula = on_alconna(
    Alconna(
        "删除课表",
        Args[
            "values",
            MultiVar(str, flag="+"),
            Field(completion=tip("请输入课表ID")),
        ],
    ),
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)
query_curricula = on_alconna(
    Alconna("查询课表", Args["classes?", str | None], Args["day?", int, Field(default=0)]),
    aliases={"查看课表", "课表查询", "我的课表"},
    block=True,
    priority=priority,
)
share_curricula = on_alconna(
    Alconna(
        "分享课表",
        Args["share_id?", str | None],
    ),
    aliases={"分享课程表", "分享课程", "共享课程", "共享课表", "绑定课表"},
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

set_week_cmd = on_alconna(
    Alconna(
        "设置当前周",
        Args["week", int],
        Args["classes_id?", int | None],
    ),
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

__helpers__ = [
    Helper(
        command="添加课表",
        description="添加学生自己的的课表,一条命令只能写入一次课表" + input_help,
        ai_description="添加学生自己的的课表,一条命令只能写入一次课表,如果机器人要加两次课表请分开两次命令执行.",
        params=[
            Param(name="课表内容", mode=ParamMode.ONE_OR_MORE),
        ],
    ),
    Helper(
        command="删除课表",
        description="删除自己的课表,一次可以删除多个课表,只需要输入课表ID即可",
        params=[
            Param(name="课表ID", mode=ParamMode.ONE_OR_MORE),
        ],
    ),
    Helper(
        command="查询课表",
        aliases={"查看课表", "课表查询", "我的课表"},
        params=[
            Param(name="班级名称", mode=ParamMode.OPTIONAL),
            Param(name="天数", mode=ParamMode.OPTIONAL),
        ],
        description=(
            "可以通过班级名称日期来查询课表,在不写班级名称的情况下查询的是本人课表,班级名称后面携带数字，如果是正数表示后面几天，如果是复数表示前面几天。\n"
            "例如: 查询课表 // 表示查询本人当天课表\n"
            "查询课表 软件1班 // 表示查询软件1班当天课表\n"
            "查询课表 软件1班 1 // 表示查询软件1班明天的课表\n"
            "查询课表 1 // 表示查询本人明天课表"
        ),
    ),
    Helper(
        command="分享课表",
        aliases={"分享课程表", "分享课程", "共享课程", "共享课表", "绑定课表"},
        description="分享自己的课表给其他人,如果没有参数则生成自己的share_id,如果有参数则获取指定的课表",
        params=[
            Param(name="分享ID/班级名称", mode=ParamMode.OPTIONAL),
        ],
    ),
]
