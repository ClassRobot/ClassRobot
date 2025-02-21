from utils.config import priority
from utils.helper.config import helper_menu
from utils.helper.depends import HelpersDepends
from nonebot import get_driver, get_loaded_plugins
from nonebot_plugin_alconna import Args, Alconna, UniMessage, AlconnaMatcher, on_alconna

driver = get_driver()
help_cmd = on_alconna(
    Alconna("help", Args["name?", str | None]),
    aliases={"帮助"},
    priority=priority,
    block=True,
)


@help_cmd.handle()
async def _(
    name: str | None,
    matcher: AlconnaMatcher,
    helpers: HelpersDepends,
):
    if name:
        if helper := helpers.get_helper(name):
            await matcher.finish(helper.to_string())
        await matcher.finish("未找到相关命令帮助信息")
    else:
        await matcher.finish(UniMessage.image(raw=await helpers.render_pic()))


@driver.on_startup
async def _():
    for plugin in get_loaded_plugins():
        if helpers := getattr(plugin.module, "__helpers__", None):
            helper_menu.extend(helpers)
        elif cmd := getattr(plugin.module, "commands", None):
            if helpers := getattr(cmd, "__helpers__", None):
                helper_menu.extend(helpers)
