from utils.config import priority
from nonebot_plugin_alconna import (
    Args,
    Alconna,
    MsgTarget,
    UniMessage,
    AlconnaMatcher,
    on_alconna,
)

from .schemas import helper_menu as helper_menu

help_cmd = on_alconna(
    Alconna("help", Args["name?", str | None]),
    aliases={"帮助"},
    priority=priority,
    block=True,
)


@help_cmd.handle()
async def _(
    matcher: AlconnaMatcher,
    name: str | None,
):
    if name:
        if helper := helper_menu.get_helper(name):
            await matcher.finish(helper.to_string())
        await matcher.finish("未找到相关命令帮助信息")
    else:
        await matcher.finish(UniMessage.image(raw=await helper_menu.render_pic()))
