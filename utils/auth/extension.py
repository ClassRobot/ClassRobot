from data.main import ClassCadre
from nonebot.adapters import Bot
from arclet.alconna import Alconna
from nonebot.adapters import Event
from utils.session import get_platform_id
from nonebot.adapters import Bot as BaseBot
from utils.typings import UserRole, UserType
from utils.models.methods import get_bind_user
from nonebot.adapters import Event as BaseEvent
from utils.models import User, Student, Teacher
from nonebot_plugin_alconna.extension import Interface, DefaultExtension


class BaseAuthExtension(DefaultExtension):
    current_user: User  # 当前用户
    role: UserRole  # 用户身份

    @property
    def user(self) -> UserType:
        """role对应用户身份"""
        if not self.params:
            raise ValueError("user not found")
        return self.params[self.role]

    def is_admin(self) -> bool:
        return self.current_user.user_type == UserRole.ADMIN

    def is_teacher(self) -> bool:
        return self.current_user.user_type == UserRole.TEACHER

    def is_student(self) -> bool:
        return self.current_user.user_type == UserRole.STUDENT

    @user.setter
    def user(self, user: UserType):
        if isinstance(user, Teacher):
            self.role = UserRole.TEACHER
        elif isinstance(user, Student):
            self.role = UserRole.STUDENT
        elif user.user_type == UserRole.ADMIN:
            self.role = user.user_type
        self.params[self.role] = user

    def __init__(self, user_only: bool = False):
        """认证扩展

        Args:
            user_only (bool, optional): 仅限认证的用户可用，管理员不可用. Defaults to False.
        """
        super().__init__()
        self.user_only: bool = user_only
        self.role = UserRole.USER
        self.params: dict[str, UserType] = {}

    @property
    def priority(self) -> int:
        return 100

    async def catch(self, interface: Interface):
        return self.params.get(interface.name)

    async def permission_check(self, bot: Bot, event: Event, command: Alconna) -> bool:
        return False


class UserExtension(BaseAuthExtension):
    async def permission_check(
        self, bot: BaseBot, event: BaseEvent, command: Alconna
    ) -> bool:
        await super().permission_check(bot, event, command)
        platform_id = get_platform_id(bot, event)
        account_id = event.get_user_id()
        if bind := await get_bind_user(platform_id, account_id):
            self.current_user = bind.user
            self.params[UserRole.USER] = bind.user
            self.user = bind.user  # 将user赋值给self.user会获取当前user的role
            if success := await self._permission_check(bot, event):
                return success
            elif self.user_only is False and self.is_admin():
                return True
        return False

    async def _permission_check(self, bot: BaseBot, event: BaseEvent) -> bool:
        return True


class AdminExtension(UserExtension):
    async def _permission_check(self, bot: Bot, event: Event) -> bool:
        return self.is_admin()


class TeacherExtension(UserExtension):
    async def _permission_check(self, bot: Bot, event: Event, command: Alconna) -> bool:
        if self.is_teacher():
            self.user = self.current_user.teacher[0]
            return True
        return False


class StudentExtension(UserExtension):
    async def _permission_check(self, bot: Bot, event: Event, command: Alconna) -> bool:
        if self.is_student():
            self.user = self.current_user.student[0]
            return True
        return False


class ClassCadreExtension(StudentExtension):
    def is_class_cadre(self) -> bool:
        self.user: Student
        if self.is_student():
            return self.user.position in ClassCadre.__members__.values()
        return False

    async def _permission_check(self, bot: Bot, event: Event, command: Alconna) -> bool:
        if self.is_class_cadre():
            self.user = self.current_user.student[0]
            return True
        return False
