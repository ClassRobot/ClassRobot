from typing import Annotated

from utils.helper import Helpers
from nonebot.params import Depends
from utils.models.depends import UserOrCreatedDepends

from .config import helper_menu


def user_helpers(user: UserOrCreatedDepends) -> Helpers:
    """返回当前用户可使用的帮助信息集合。"""
    helpers = helper_menu.get_roles_helpers(*user.roles)
    # 命令软关闭需要同时影响 help、Agent 工具目录和统一执行器。
    # 这里放在依赖层做过滤，可以避免每个使用 Helper 的入口重复判断。
    from utils.commands.availability import command_availability

    return command_availability.filter_helpers(helpers)


HelpersDepends = Annotated[Helpers, Depends(user_helpers)]
