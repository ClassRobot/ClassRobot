from nonebot import on_command
from utils.config import priority, comp_config
from nonebot_plugin_alconna import Args, Field, Alconna, on_alconna

notice_cmd = on_command(
    "通知",
    aliases={"定时"},
    priority=priority,
    block=True,
)
query_notice_cmd = on_alconna(
    Alconna("查询通知"),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
)
delete_notice_cmd = on_alconna(
    Alconna("删除通知", Args["notice_id", str, Field(completion=lambda: "请输入通知ID")]),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)
