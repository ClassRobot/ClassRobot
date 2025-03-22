from utils import tip
from utils.config import priority, comp_config
from nonebot_plugin_alconna import Args, Text, Field, Alconna, on_alconna

login_edu_cmd = on_alconna(
    Alconna(
        "登录教务系统",
        Args["username", Text, Field(completion=tip("输入学号/账号"))],
        Args["password", Text, Field(completion=tip("输入密码"))],
    ),
    aliases={"教务系统登录", "登录教务"},
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)
