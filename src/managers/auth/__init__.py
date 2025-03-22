from utils import Emoji
from nonebot_plugin_alconna import AlconnaMatcher

from .scheme import edu_logins
from .commands import login_edu_cmd


@login_edu_cmd.handle()
async def _(matcher: AlconnaMatcher, username: str, password: str):
    for login in edu_logins:
        await login(account=username, password=password).login()
    await matcher.send(Emoji.error + "暂不支持该学校")
