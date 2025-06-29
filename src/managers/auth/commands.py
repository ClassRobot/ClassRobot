from utils import tip
from utils.config import priority, comp_config
from nonebot_plugin_alconna import Args, Field, Alconna, on_alconna

login_edu_cmd = on_alconna(
    Alconna(
        "登录教务系统",
        Args["username", str, Field(completion=tip("输入学号/账号"))],
        Args["password", str, Field(completion=tip("输入密码"))],
    ),
    aliases={"教务系统登录", "登录教务", "登录"},
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)
