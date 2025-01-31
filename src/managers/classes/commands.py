from typing import Optional

from utils import tip
from utils.config import priority, comp_config
from src.plugins.helper.schemas import Param, Helper
from nonebot_plugin_alconna import Args, Field, Alconna, on_alconna

NameNotNumeric = lambda name: None if name.strip().isdigit() else name

add_classes_cmd = on_alconna(
    Alconna(
        "添加班级",
        Args[
            "class_name",
            NameNotNumeric,
            Field(
                completion=tip("请输入班级名称"),
                unmatch_tips=tip("名称不能为纯数字"),
            ),
        ],
    ),
    priority=priority,
    aliases={"创建班级", "绑定班级"},
    comp_config=comp_config,
    block=True,
)

query_classes_cmd = on_alconna(
    Alconna("查询班级"), aliases={"班级列表", "我的班级"}, priority=priority, block=True
)

join_classes_cmd = on_alconna(
    Alconna(
        "加入班级", Args["classes_id?", Optional[int]], Args["describe?", Optional[str]]
    ),
    comp_config=comp_config,
    priority=priority,
    block=True,
)

# 修改加入班级方式
set_join_classes_cmd = on_alconna(
    Alconna(
        "修改班级加入方式",
        Args["classes_id?", Optional[str]],
        Args["join_method?", Optional[str]],
    ),
    comp_config=comp_config,
    priority=priority,
    block=True,
)

# 退出班级
exit_classes_cmd = on_alconna(
    Alconna("退出班级"),
    comp_config=comp_config,
    priority=priority,
    block=True,
)

__helper__ = [
    Helper(
        command="添加班级",
        description="创建一个自己的班级，创建后默认会成为该班级教师，同时也可以将已有班级与群进行绑定",
        aliases={"创建班级", "绑定班级"},
        params=[Param(name="班级名称")],
    ),
    Helper(
        command="查询班级",
        description="查询自己创建的班级",
        aliases={"班级列表", "我的班级"},
    ),
    Helper(
        command="加入班级",
        description="可通过班级ID加入到指定班级中，如果在群聊中执行该命令且不携带班级ID的情况下会自动绑定该群到指定班级",
        params=[Param(name="班级ID", required=False)],
    ),
]
