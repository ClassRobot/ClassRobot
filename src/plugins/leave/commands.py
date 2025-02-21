from utils import tip
from utils.config import priority, comp_config
from src.plugins.helper.schemas import Param, Helper
from nonebot_plugin_alconna import Args, Field, Image, Alconna, MultiVar, on_alconna

add_leave_cmd = on_alconna(
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

query_leave_cmd = on_alconna(
    Alconna("请假列表"),
    aliases={"查询请假"},
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

set_leave_push_cmd = on_alconna(
    Alconna(
        "设置请假推送",
        Args[
            "push_list",
            MultiVar(str, "+"),
            Field(completion=tip("您希望推送给哪几个班干部")),
        ],
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

delete_leave_cmd = on_alconna(
    Alconna(
        "删除请假",
        Args[
            "leave_id",
            MultiVar(str, "+"),
            Field(completion=tip("请输入要删除的请假条ID")),
        ],
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

__helpers__ = [
    Helper(
        command="请假",
        description="请告诉我请假原因,时间等信息,同时还有请假条照片给我,一张图片即可!",
        params=[Param(name="请假原因"), Param(name="请假条照片")],
    ),
]
