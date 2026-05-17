from utils.helper import Helpers
from utils.helper.config import helper_menu
from utils.helper.runtime import bootstrap_helper_runtime
from utils.helper.depends import HelpersDepends
from nonebot import get_driver, get_loaded_plugins
from nonebot_plugin_alconna import UniMessage, AlconnaMatcher

from . import commands
from .commands import __helpers__, help_cmd

driver = get_driver()


@help_cmd.handle()
async def _(
    name: str | None,
    matcher: AlconnaMatcher,
    helpers: HelpersDepends,
):
    """处理当前命令或事件逻辑。"""
    if name:
        if helper := helpers.get_helper(name):
            await matcher.finish(helper.to_string())
        await matcher.finish("未找到相关命令帮助信息")
    else:
        await matcher.finish(UniMessage.image(raw=await helpers.render_pic()))


@driver.on_startup
async def _():
    """启动时构建帮助目录，并把权限元数据同步到 matcher。"""

    bootstrap_helper_runtime(get_loaded_plugins())
