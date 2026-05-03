from utils import tip
from utils.config import priority, comp_config
from utils.helper import Helper, HelperScope, Param
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


__helpers__ = [
    Helper(
        command="登录教务系统",
        aliases={"教务系统登录", "登录教务", "登录"},
        description="登录学校教务系统，供后续课表、成绩或校务场景复用账号信息。",
        params=[Param(name="username", description="学号或教务账号"), Param(name="password", description="登录密码")],
        scopes={HelperScope.user},
    )
]
