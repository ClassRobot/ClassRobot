"""系统层面的用户身份"""

from strenum import StrEnum


class UserRole(StrEnum):
    """用户身份"""

    user = "user"
    """用户"""
    admin = "admin"
    """管理员"""
    superuser = "superuser"
    """超级管理员"""
