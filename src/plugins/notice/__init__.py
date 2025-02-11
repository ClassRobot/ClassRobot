from nonebot.matcher import Matcher
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot_plugin_alconna import UniMsg, UniMessage

from .commands import notice_cmd


@notice_cmd.handle()
async def _(matcher: Matcher, messages: UniMsg):
    print(messages)
