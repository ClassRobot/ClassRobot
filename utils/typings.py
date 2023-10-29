from typing import TypeAlias

from strenum import StrEnum
from utils.models import User, Student, Teacher

UserType: TypeAlias = User | Student | Teacher


class UserRole(StrEnum):
    """用户身份权限"""

    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"
    USER = "user"
