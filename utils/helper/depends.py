from typing import Annotated

from utils.helper import Helpers
from nonebot.params import Depends
from utils.models.depends import UserOrCreatedDepends

from .config import helper_menu


def user_helpers(user: UserOrCreatedDepends) -> Helpers:
    """返回当前用户可使用的帮助信息集合。"""
    return helper_menu.get_roles_helpers(*user.roles)


HelpersDepends = Annotated[Helpers, Depends(user_helpers)]
