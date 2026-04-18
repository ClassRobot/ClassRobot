from utils import tip
from utils.config import priority, comp_config
from utils.helper import Param, Helper, UserRole, ParamMode
from nonebot_plugin_alconna import Args, Field, Alconna, MultiVar, on_alconna

query_teacher_cmd = on_alconna(
    Alconna("查询教师信息"),
    aliases={"教师信息", "我的教师信息"},
    block=True,
    priority=priority,
    comp_config=comp_config,
)

set_teacher_cmd = on_alconna(
    Alconna(
        "修改教师信息",
        Args[
            "values",
            MultiVar(str, flag="+"),
            Field(completion=tip("修改方式如 姓名=张老师 学校=某大学 学院=计算机学院")),
        ],
    ),
    aliases={"修改教师", "设置教师信息"},
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)


__helpers__ = [
    Helper(
        command="查询教师信息",
        description="查询当前账号绑定的教师信息和所管理的班级。",
        aliases={"教师信息", "我的教师信息"},
        roles={UserRole.teacher},
    ),
    Helper(
        command="修改教师信息",
        description="修改教师姓名、学校、学院；若当前账号尚未绑定教师身份，则会在校验通过后自动创建教师信息。",
        aliases={"修改教师", "设置教师信息"},
        params=[
            Param(
                name="values",
                mode=ParamMode.ONE_OR_MORE,
                description="修改方式如 姓名=张老师 学校=某大学 学院=计算机学院",
            ),
        ],
        roles={UserRole.user, UserRole.teacher},
    ),
]
