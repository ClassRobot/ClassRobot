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


class ClassCadre(StrEnum):
    cc = "班长"  # Class Captain
    yls = "团支书"  # Youth League Secretary
    sc = "学习委员"  # Study Committee Member
    oc = "组织委员"  # Organization Committee Member
    pc = "心理委员"  # Psychological Committee Member
    spc = "宣传委员"  # Propaganda Committee Member
    mc = "男生委员"  # Male Student Committee Member
    fc = "女生委员"  # Female Student Committee Member
    sec = "治保委员"  # Security Committee Member
    hc = "生卫委员"  # Health Committee Member
    ic = "权益委员"  # Interests Committee Member


class_cadres = list(ClassCadre.__members__.values())
default_student_position = "学生"


class Platform(NamedTuple):
    id: int
    bot: type[BaseBot]
    event: type[BaseEvent] | tuple[type[BaseEvent], ...]
