from nonebot.log import logger
from utils.typings import UserType
from nonebot.adapters import Message
from pydantic import ValidationError
from nonebot.params import CommandArg
from nonebot.internal.matcher import Matcher
from nonebot import get_driver, on_command, get_loaded_plugins

from .helper import HelperMenu
from .typings import Helper, ExampleMessage

helper_menu = HelperMenu()
driver = get_driver()
help_cmd = on_command("帮助", aliases={"help", "菜单"}, block=True, priority=1000)


def add_help(*helper_info: Helper):
    """添加帮助信息"""
    for i in helper_info:
        helper_menu.add(i)


@help_cmd.handle()
async def _(matcher: Matcher, msg: Message = CommandArg()):
    command = msg.extract_plain_text().strip()
    if not command:
        await matcher.finish(helper_menu.to_string())
    elif help_info := helper_menu.get(msg.extract_plain_text()):
        await matcher.finish(help_info.to_string())
    await matcher.finish("没有找到这个命令！")


@driver.on_startup
async def _():
    """获取插件中的帮助信息"""
    for plugin in get_loaded_plugins():
        try:
            if help_info := plugin.module.__getattribute__("__helper__"):
                helper_menu.add(help_info)
        except ValidationError as err:
            logger.warning("__helper__内容存在错误: \n%r" % err)
        except (AttributeError, ValidationError):
            continue


add_help(
    Helper(
        command="帮助",
        description="获取帮助信息",
        usage="帮助 [命令]",
        example=[
            ExampleMessage(user_type=UserType.USER, message="帮助 [命令]"),
            ExampleMessage(user_type="bot", message="[帮助信息]"),
        ],
        aliases={"help", "菜单"},
        category={"help"},
    )
)
