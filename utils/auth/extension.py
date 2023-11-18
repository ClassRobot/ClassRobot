from typing import Any

from arclet.alconna import Alconna
from utils.typings import UserType
from utils.models.depends import get_user
from utils.session import get_platform_id
from nonebot.adapters import Bot as BaseBot
from nonebot.adapters import Event as BaseEvent
from utils.models import User, Student, Teacher, UserModel
from nonebot_plugin_alconna.extension import Interface, DefaultExtension

from .config import ClassCadre


class BaseAuthExtension(DefaultExtension):
    current_user: User  # 当前用户
    role: UserType = UserType.USER  # 用户类型
    before: list[UserType] | None = None  # 依赖的用户类型

    @property
    def user(self) -> UserModel:
        """获取身份对应的用户，具体是什么身份由role决定

        Returns:
            UserType: 用户
        """
        return self.params[self.role]

    @user.setter
    def user(self, user: UserModel):
        self.params[self.role] = user

    def is_admin(self) -> bool:
        """是否为管理员"""
        return self.current_user.user_type == UserType.ADMIN

    def is_teacher(self) -> bool:
        """是否为教师"""
        return self.current_user.user_type == UserType.TEACHER

    def is_student(self) -> bool:
        """是否为学生"""
        return self.current_user.user_type == UserType.STUDENT

    def __init__(self, user_only: bool = False):
        """认证扩展

        Args:
            user_only (bool, optional): 仅限认证的用户可用，管理员不可用. Defaults to False.

            当user_only为True时, 仅限认证的用户可用，管理员不可用
        """
        super().__init__()
        self.user_only: bool = user_only
        self.params: dict[str, UserModel] = {}

    @property
    def priority(self) -> int:
        return 100

    def before_catch(self, name: str, annotation: Any, default: Any):
        return name in ([UserType.USER, UserType.ADMIN] + (self.before or []))

    async def catch(self, interface: Interface) -> UserModel | None:
        return self.params.get(interface.name)

    async def permission_check(
        self, bot: BaseBot, event: BaseEvent, command: Alconna
    ) -> bool:
        return False

    async def _permission_check(self) -> bool:
        return True


class UserExtension(BaseAuthExtension):
    """基本用户认证扩展"""

    async def permission_check(
        self, bot: BaseBot, event: BaseEvent, command: Alconna
    ) -> bool:
        await super().permission_check(bot, event, command)
        platform_id = get_platform_id(bot, event)
        account_id = event.get_user_id()
        if user := await get_user(platform_id, account_id, self.role):
            self.current_user = user
            self.params[UserType.USER] = user
            return (await self._permission_check()) or (
                self.user_only is False and self.is_admin()
            )
        return False


class AdminExtension(UserExtension):
    """管理员认证扩展"""

    role = UserType.ADMIN

    async def _permission_check(self) -> bool:
        if self.is_admin():
            self.user = self.current_user
            return True
        return False


class TeacherExtension(UserExtension):
    """教师认证扩展"""

    role = UserType.TEACHER
    user: Teacher
    before = [UserType.TEACHER]

    async def _permission_check(self) -> bool:
        if self.is_teacher():
            self.user = self.current_user.teacher[0]
            return True
        return False


class StudentExtension(UserExtension):
    """学生认证扩展"""

    role = UserType.STUDENT
    user: Student
    before = [UserType.STUDENT]

    async def _permission_check(self) -> bool:
        if self.is_student():
            self.user = self.current_user.student[0]
            return True
        return False


class ClassCadreExtension(StudentExtension):
    """班干部认证扩展"""

    def is_class_cadre(self) -> bool:
        return self.user.position in ClassCadre.__members__.values()

    async def _permission_check(self) -> bool:
        if (await super()._permission_check()) and self.is_class_cadre():
            self.user = self.current_user.student[0]
            return True
        return False
