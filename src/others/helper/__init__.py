from nonebot import on_command
from nonebot.matcher import Matcher
from utils.params import CommandArgStr

from .schemas import helper_menu as helper_menu

help_cmd = on_command("help", aliases={"帮助"}, priority=100, block=True)


@help_cmd.handle()
async def _(matcher: Matcher, message: str | None = CommandArgStr()):
    if message:
        if helper := helper_menu.get_helper(message):
            await matcher.finish(helper.to_string())
        await matcher.finish("未找到相关命令帮助信息")
    else:
        await matcher.finish(helper_menu.to_string())
