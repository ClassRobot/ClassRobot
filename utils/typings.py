from typing import NamedTuple

from strenum import StrEnum
from nonebot.adapters import Bot as BaseBot
from nonebot.adapters import Event as BaseEvent


class UserType(StrEnum):
    """用户身份权限"""

    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"
    USER = "user"


class UserTypeChinese(StrEnum):
    """用户身份权限中文名"""

    admin = "管理员"
    teacher = "教师"
    student = "学生"
    user = "用户"


class Platform(NamedTuple):
    id: int
    bot: type[BaseBot]
    event: type[BaseEvent] | tuple[type[BaseEvent], ...]
