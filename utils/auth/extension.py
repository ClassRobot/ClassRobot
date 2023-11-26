from typing import Any

from arclet.alconna import Alconna
from utils.params import get_group_id
from utils.models import Base as ORMModel
from utils.models import Student, Teacher
from nonebot.adapters import Bot as BaseBot
from nonebot.adapters import Event as BaseEvent
from utils.typings import UserType, class_cadres
from utils.session.platform import Platform, get_platform
from nonebot_plugin_alconna.uniseg import Target, UniMessage
from nonebot_plugin_alconna.extension import Extension, Interface
from utils.models.depends import get_user, get_student, get_teacher, get_class_table


class BaseAuthExtension(Extension):
    @property
    def id(self) -> str:
        return "auth"

    @property
    def priority(self) -> int:
        return 100

    @property
    def before(self) -> list[UserType | str]:
        return []

    async def catch(self, interface: Interface) -> ORMModel | None:
        interface.state.update(self.params)
        return self.params.get(interface.name)

    def before_catch(self, name: str, annotation: Any, default: Any):
        if self.before:
            return name in self.before

    async def permission_check(
        self, bot: BaseBot, event: BaseEvent, command: Alconna
    ) -> bool:
        self.params: dict[str, ORMModel] = {}  # 参数
        self.platform: Platform = get_platform(bot, event)  # 平台
        self.account_id: str = event.get_user_id()  # 所在平台的用户id
        self.target: Target = UniMessage.get_target(event, bot)
        dirs = dir(self)
        dirs.reverse()
        for i in (i for i in dirs if i.endswith("_permission_check")):
            check: bool = await getattr(self, i)()
            print("check", i, check)
            if not check:
                return False
        return True


class UserExtension(BaseAuthExtension):
    """基本用户认证扩展"""

    @property
    def before(self) -> list[UserType | str]:
        return super().before + [UserType.USER, UserType.ADMIN]

    @property
    def id(self) -> str:
        return str(UserType.USER)

    def is_admin(self) -> bool:
        """是否为管理员"""
        return self.user.user_type == UserType.ADMIN

    def is_teacher(self) -> bool:
        """是否为教师"""
        return self.user.user_type == UserType.TEACHER

    def is_student(self) -> bool:
        """是否为学生"""
        return self.user.user_type == UserType.STUDENT

    async def user_permission_check(self) -> bool:
        if user := await get_user(self.platform.id, self.account_id):
            self.user = user
            self.params[UserType.USER] = user
            if user.user_type == UserType.ADMIN:
                self.params[UserType.ADMIN] = user
            return True
        return False


class GroupExtension(BaseAuthExtension):
    """群认证扩展"""

    group_id: str

    @property
    def id(self) -> str:
        return "group"

    async def group_permission_check(self) -> bool:
        if group_id := get_group_id(self.target):
            self.group_id = group_id
            return True
        return False


class AdminExtension(UserExtension):
    """管理员认证扩展"""

    @property
    def id(self) -> str:
        return str(UserType.ADMIN)

    async def admin_permission_check(self) -> bool:
        return self.is_admin()


class TeacherExtension(UserExtension):
    """教师认证扩展"""

    @property
    def id(self) -> str:
        return str(UserType.TEACHER)

    @property
    def before(self) -> list[UserType | str]:
        return super().before + [self.id]

    async def teacher_permission_check(self) -> bool:
        if self.is_teacher() or self.is_admin():
            if teacher := await get_teacher(self.user):
                self.params[self.id] = teacher
                self.teacher = teacher
                return True
        return False


class StudentExtension(UserExtension):
    """学生认证扩展"""

    @property
    def id(self) -> str:
        return str(UserType.STUDENT)

    @property
    def before(self) -> list[UserType | str]:
        return super().before + [self.id]

    async def student_permission_check(self) -> bool:
        if self.is_student() or self.is_admin():
            if student := await get_student(self.user):
                self.params[self.id] = student
                self.student = student
                return True
        return False


class TeacherOrStudentExtension(UserExtension):
    """教师或学生认证扩展"""

    @property
    def id(self) -> str:
        return "teacher_or_student"

    @property
    def before(self) -> list[UserType | str]:
        return super().before + [self.id]

    async def teacher_or_student_permission_check(self) -> bool:
        user: Student | Teacher | None = None
        if self.is_teacher() or self.is_admin():
            user = await get_student(self.user.id)
        elif self.is_student() or self.is_admin():
            user = await get_teacher(self.user.id)
        if user:
            self.params[self.id] = user
            return True
        return False


class ClassCadreExtension(StudentExtension):
    """班干部认证扩展"""

    @property
    def id(self) -> str:
        return "class_cadre"

    def is_class_cadre(self) -> bool:
        return self.student.position in class_cadres

    async def class_cadre_permission_check(self) -> bool:
        return self.is_class_cadre()


class ClassTableExtension(GroupExtension):
    """班级群认证扩展"""

    @property
    def before(self) -> list[UserType | str]:
        return super().before + [self.id]

    @property
    def id(self) -> str:
        return "class_table"

    async def class_table_permission_check(self) -> bool:
        if class_table := await get_class_table(
            self.group_id, platform_id=self.platform.id
        ):
            self.class_table = class_table
            self.params[self.id] = class_table
            return True
        return False


class StudentClassTableExtension(StudentExtension, ClassTableExtension):
    """学生班级群认证扩展"""

    @property
    def id(self) -> str:
        return "student_class_table"

    async def student_class_table_permission_check(self) -> bool:
        return self.student.class_table_id == self.class_table.id


class TeacherClassTableExtension(TeacherExtension, ClassTableExtension):
    """教师班级群认证扩展"""

    @property
    def id(self) -> str:
        return "teacher_class_table"

    async def teacher_class_table_permission_check(self) -> bool:
        return self.teacher.id == self.class_table.teacher_id
