from nonebot_plugin_alconna import on_alconna, Alconna, Args, Field
from typing import Annotated
from utils.config import comp_config
from utils import tip


NameNotNumeric = lambda name: None if name.strip().isdigit() else name

add_classes_cmd = on_alconna(
    Alconna(
        "添加班级",
        Args[
            "class_name",
            NameNotNumeric,
            Field(
                completion=tip("请输入名称"),
                unmatch_tips=tip("名称不能为纯数字"),
            ),
        ],
    ),
    aliases={"创建班级", "绑定班级"},
    comp_config=comp_config,
)

query_classes_cmd = on_alconna(Alconna("查询班级"), aliases={"班级列表", "我的班级"})

join_classes_cmd = on_alconna(
    Alconna("加入班级", Args["class_id", int | None, Field()]),
)
