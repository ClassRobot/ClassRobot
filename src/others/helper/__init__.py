from nonebot import get_loaded_plugins, get_driver, on_command
from nonebot.plugin import get_loaded_plugins
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Message, MessageSegment
from nonebot.internal.matcher import Matcher
from nonebot.params import CommandArg
from pydantic import ValidationError
from .helper import HelperMenu

helper_menu = HelperMenu()
driver = get_driver()
help_cmd = on_command("帮助", aliases={"help"}, block=True, priority=1000)


@help_cmd.handle()
async def _(matcher: Matcher, msg: Message = CommandArg()):
    if helper_msg := helper_menu.get(msg.extract_plain_text()):
        await matcher.finish(MessageSegment.image(await helper_msg.to_image()))
    await matcher.finish("没有找到这个命令！")


@driver.on_startup
async def _():
    """获取插件中的帮助信息"""
    for plugin in get_loaded_plugins():
        try:
            if helper_info := plugin.module.__getattribute__("__helper__"):
                helper_menu.append(helper_info)
        except ValidationError as err:
            logger.warning("__helper__内容存在错误: \n%r" % err)
        except (AttributeError, ValidationError):
            continue


__helper__ = {
    "cmd": "帮助",
    "doc": "获取命令相关帮助信息，你想要获取的帮助信息，可以通过输入命令名称或目录的tag也就是类型来查看。",
    "tags": ["帮助", "help"],
    "params": "命令名称/类型",
}
