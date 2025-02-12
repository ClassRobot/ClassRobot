from nonebot import on_command
from utils.config import priority

notice_cmd = on_command(
    "通知",
    aliases={"定时"},
    priority=priority,
    block=True,
)
