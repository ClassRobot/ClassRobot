from utils.config import priority
from nonebot import get_loaded_plugins, get_driver
from nonebot_plugin_alconna import (
    Args,
    Alconna,
    UniMessage,
    AlconnaMatcher,
    on_alconna,
)

from utils.models.depends import UserOrCreatedDepends

from .schemas import helper_menu as helper_menu

driver = get_driver()
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
    user: UserOrCreatedDepends,
):
    helpers = helper_menu.helpers.get_roles_helpers(*user.roles)
    if name:
        if helper := helpers.get_helper(name):
            await matcher.finish(helper.to_string())
        await matcher.finish("未找到相关命令帮助信息")
    else:
        await matcher.finish(UniMessage.image(raw=await helpers.render_pic()))



@driver.on_startup
async def _():
    plugins = get_loaded_plugins()
    
    for plugin in plugins:
        if helpers := getattr(plugin, "__helpers__", None):
            helper_menu.extend(*helpers)

