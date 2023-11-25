from typing import Any

from arclet.alconna import Alconna
from utils.typings import UserType
from utils.params import get_group_id
from utils.models import Base as ORMModel
from nonebot.adapters import Bot as BaseBot
from nonebot.adapters import Event as BaseEvent
from utils.session.platform import Platform, get_platform
from utils.models import User, Student, Teacher, UserModel
from nonebot_plugin_alconna.uniseg import Target, UniMessage
from nonebot_plugin_alconna.extension import Extension, Interface
from utils.models.depends import get_user, get_student, get_teacher, get_class_table

from .config import ClassCadre


class BaseAuthExtension(Extension):
    before: list[UserType | str] | None = None

    @property
    def id(self) -> str:
        return "auth"

    @property
    def priority(self) -> int:
        return 100

    async def catch(self, interface: Interface) -> ORMModel | None:
        interface.state.update(self.params)
        return self.params.get(interface.name)

    def before_catch(self, name: str, annotation: Any, default: Any):
        if self.before is not None:
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

    role: UserType = UserType.USER  # 用户类型
    before = [role]

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
            self.params[UserType.USER] = user
            self.params[self.role] = user
            self.user = user
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

    role = UserType.ADMIN
    before = [UserType.USER, role]

    @property
    def id(self) -> str:
        return str(UserType.ADMIN)

    async def admin_permission_check(self) -> bool:
        return self.is_admin()


class TeacherExtension(UserExtension):
    """教师认证扩展"""

    role = UserType.TEACHER
    before = [UserType.USER, UserType.ADMIN, role]

    @property
    def id(self) -> str:
        return str(UserType.TEACHER)

    async def teacher_permission_check(self) -> bool:
        if self.is_teacher() or self.is_admin():
            if teacher := await get_teacher(self.user.id):
                self.params[UserType.TEACHER] = teacher
                self.teacher = teacher
                return True
        return False


class StudentExtension(UserExtension):
    """学生认证扩展"""

    role = UserType.STUDENT
    before = [UserType.USER, UserType.ADMIN, role]

    @property
    def id(self) -> str:
        return str(UserType.STUDENT)

    async def student_permission_check(self) -> bool:
        if self.is_student() or self.is_admin():
            if student := await get_student(self.user.id):
                self.params[UserType.STUDENT] = student
                self.student = student
                return True
        return False


class ClassCadreExtension(StudentExtension):
    """班干部认证扩展"""

    @property
    def id(self) -> str:
        return "class_cadre"

    def is_class_cadre(self) -> bool:
        return self.student.position in ClassCadre.__members__.values()

    async def class_cadre_permission_check(self) -> bool:
        return self.is_class_cadre()


class ClassTableExtension(GroupExtension):
    """班级群认证扩展"""

    before = ["class_table"]

    @property
    def id(self) -> str:
        return "class_table"

    async def class_table_permission_check(self) -> bool:
        if class_table := await get_class_table(
            self.group_id, platform_id=self.platform.id
        ):
            self.class_table = class_table
            self.params["class_table"] = class_table
            return True
        return False


class StudentClassTableExtension(StudentExtension, ClassTableExtension):
    """学生班级群认证扩展"""

    before = [UserType.USER, UserType.ADMIN, UserType.STUDENT, "class_table"]

    @property
    def id(self) -> str:
        return "student_class_table"

    async def student_class_table_permission_check(self) -> bool:
        return self.student.class_table_id == self.class_table.id


class TeacherClassTableExtension(TeacherExtension, ClassTableExtension):
    """教师班级群认证扩展"""

    before = [UserType.USER, UserType.ADMIN, UserType.TEACHER, "class_table"]

    @property
    def id(self) -> str:
        return "teacher_class_table"

    async def teacher_class_table_permission_check(self) -> bool:
        return self.teacher.id == self.class_table.teacher_id
