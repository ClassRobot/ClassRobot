from utils import tip
from utils.config import priority, comp_config
from nonebot_plugin_alconna import Args, Field, Image, Alconna, MultiVar, on_alconna

leave_cmd = on_alconna(
    Alconna(
        "请假",
        Args[
            "leave_reason",
            MultiVar(str | Image, "+"),
            Field(completion=tip("请告诉我请假原因,时间等信息,如果有请假条也可以直接发请假条照片给我,一张图片即可!")),
        ],
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

leave_list_cmd = on_alconna(
    Alconna("请假列表"),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)
