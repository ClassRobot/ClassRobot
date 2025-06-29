from utils import Emoji
from nonebot_plugin_alconna import AlconnaMatcher

from .schema import edu_logins
from .commands import login_edu_cmd

try:
    from . import login_hide as login_hide  # noqa: F401
except ImportError:
    ...


@login_edu_cmd.handle()
async def _(matcher: AlconnaMatcher, username: str, password: str):
    print(username, password)
    for login in edu_logins.values():
        await login(account=username, password=password).login()
    await matcher.send(Emoji.error + "暂不支持该学校")
