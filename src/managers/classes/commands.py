from nonebot_plugin_alconna import on_alconna, Alconna, Args, Field
from utils.config import comp_config
from utils import tip


add_classes_cmd = on_alconna(
    Alconna(
        "添加班级",
        Args["class_name", str, Field(completion=tip("请输入班级名称"))],
    ),
    aliases={"创建班级"},
    comp_config=comp_config,
)

query_classes_cmd = on_alconna(
    Alconna("查询班级"), aliases={"班级列表", "我的班级"}
)

join_classes_cmd = on_alconna(
    Alconna("加入班级", Args["class_id", int | None, Field()]),
)
