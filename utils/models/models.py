from hashlib import md5
from pathlib import Path
from datetime import datetime
from typing import List, Literal, Optional

from utils.tools import get_file_suffix
from utils.config import data_dir, task_dir
from nonebot_plugin_orm import Model, get_session
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy import JSON, Text, String, Boolean, Integer, DateTime, ForeignKey, select, update
from utils.roles import UserRole, JoinMethod, LeaveStatus, StudentRole, TeacherRole, PoliticalStatus, TeacherClassesRole

from .filters import FilterModel
from .columns import CreateAt, UpdateAt


class User(FilterModel, Model):
    """用户表"""

    nickname: Mapped[str] = mapped_column(String(64), nullable=False)
    """用户昵称"""
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    """用户名"""
    password: Mapped[str | None] = mapped_column(String(128), nullable=True)
    """用户密码"""
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    """邮箱"""
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    """头像"""
    phone: Mapped[str | None] = mapped_column(String(11), nullable=True, unique=True)
    """手机号"""
    role: Mapped[UserRole] = mapped_column(String(32), nullable=False, server_default=UserRole.user)
    """用户角色"""
    gender: Mapped[str | None] = mapped_column(String(8), nullable=True)
    """用户性别"""
    birthday: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    """用户出生日期"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    teacher: Mapped[Optional["Teacher"]] = relationship("Teacher", lazy=False, back_populates="user")
    student: Mapped[Optional["Student"]] = relationship("Student", lazy=False, back_populates="user")
    """一个用户绑定一个学生"""
    binds: Mapped[List["UserBind"]] = relationship("UserBind", lazy="selectin", back_populates="user")
    """一个用户可以绑定多个表"""
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")

    @property
    def roles(self) -> list[UserRole]:
        roles = [UserRole.user]
        if self.is_admin:
            roles.append(UserRole.admin)
        if self.student:
            roles.append(UserRole.student)
        if self.teacher:
            roles.append(UserRole.teacher)
        # 是否为班干部
        if (
            self.student
            and self.student.role in StudentRole._member_names_
            and self.student.role != StudentRole.student
        ):
            roles.append(UserRole.class_cadre)
        return roles

    async def get_join_requests(self) -> List["ClassesJoinRequest"]:
        """获取到用户的所有申请加入班级的请求"""
        return await ClassesJoinRequest.filter(user_id=self.id).all()

    async def get_groups(self) -> List["Group"]:
        """获取到用户创建的所有群组"""
        return await Group.filter(creator_id=self.id).all()

    def check_password(self, password: str) -> bool:
        """检查密码

        Args:
            password (str): 密码

        Returns:
            bool: 是否匹配
        """
        return self.password == password

    @classmethod
    async def login(cls, username: str, password: str) -> Optional["User"]:
        """用户登录

        Args:
            username (str): 用户名
            password (str): 用户密码

        Returns:
            Optional[User]: 用户信息
        """
        if user := await cls.filter(username=username).first():
            if user.check_password(password):
                return user

    @classmethod
    async def create_user(
        cls,
        nickname: str,
        username: str,
        password: str | None = None,
        email: str | None = None,
        avatar: str | None = None,
    ) -> "User":
        """创建用户

        Args:
            nickname (str): 用户昵称
            username (str): 用户名
            password (str | None, optional): 用户密码. Defaults to None.
            email (str | None, optional): 用户邮箱. Defaults to None.
            avatar (str | None, optional): 用户头像. Defaults to None.

        Returns:
            User: 创建后的用户
        """
        user = await cls(
            nickname=nickname,
            username=username,
            password=password,
            email=email,
            avatar=avatar,
        ).create()
        return user

    @classmethod
    async def get_user(cls, user_id: int) -> Optional["User"]:
        """获取用户信息

        Args:
            user_id (int): 用户ID

        Returns:
            Optional[User]: 用户信息
        """
        return await cls.filter(id=user_id).first()

    async def get_bind(self, platform_id: str) -> Optional["UserBind"]:
        """获取用户绑定信息

        Args:
            platform_id (str): 平台ID

        Returns:
            Optional[UserBind]: 绑定信息
        """
        return await UserBind.filter(user_id=self.id, platform_id=platform_id).first()

    async def get_notices(self) -> List["ScheduledNotice"]:
        """获取用户的通知任务"""
        return await ScheduledNotice.filter(user_id=self.id).all()

    async def get_curricula_config(self) -> Optional["CurriculaConfig"]:
        return await CurriculaConfig.filter(user_id=self.id).first()

    async def get_approvals(self) -> List["StudentLeaveApproval"]:
        """获取需要审批人审批的信息"""
        return await StudentLeaveApproval.filter(approver_id=self.id).all()


class UserBind(FilterModel, Model):
    """用户与平台绑定表

    - 用户与平台是一对多关系
    """

    name: Mapped[str] = mapped_column(String(64), nullable=True)
    """平台名称"""
    platform_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    """平台ID"""
    account_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    """平台关联ID"""
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    """绑定的用户ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    user: Mapped[User] = relationship(lazy=False, back_populates="binds")

    @classmethod
    async def get_bind(
        cls,
        platform_id: str,
        account_id: str,
    ) -> Optional["UserBind"]:
        """获取绑定信息

        Args:
            platform_id (str): 平台ID
            account_id (str): 平台用户ID

        Returns:
            Optional[UserBind]: 绑定信息
        """
        return await cls.filter(platform_id=platform_id, account_id=account_id).first()

    @classmethod
    async def get_user(
        cls,
        platform_id: str,
        account_id: str,
    ) -> Optional[User]:
        """获取绑定的用户信息

        Args:
            platform_id (str): 平台ID
            account_id (str): 平台用户ID

        Returns:
            Optional[User]: 用户信息
        """
        if bind := await cls.get_bind(platform_id, account_id):
            return bind.user

    @classmethod
    async def bind_user(
        cls,
        platform_id: str,
        account_id: str,
        user: User,
    ) -> "UserBind":
        """平台与用户之间的绑定

        Args:
            platform_id (str): 平台ID
            account_id (str): 平台用户ID
            user (User): 绑定的用户

        Returns:
            UserBind: 绑定信息
        """
        async with get_session() as session:
            where_and = (UserBind.platform_id == platform_id) & (UserBind.account_id == account_id)
            if bind := await session.scalar(select(UserBind).where(where_and)):
                # 查看之前绑定的用户是否是当前用户
                if bind.user_id == user.id:
                    return bind
                # 查看之前绑定的用户是否只有这一次绑定，如果是只有一次绑定则删除该用户
                old_user = bind.user  # 获取之前绑定的用户的id
                await session.execute(update(UserBind).where(where_and).values(user=user))
                await session.commit()
                # 查看之前用户是否有其他绑定，如果没有则删除该用户
                if len(old_user.binds) == 0:
                    await session.delete(old_user)
            else:
                bind = cls(platform_id=platform_id, account_id=account_id, user=user)
                session.add(bind)
            await session.commit()
            await session.refresh(user)
            await session.refresh(bind)
            return bind


class School(FilterModel, Model):
    """学校表"""

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    """学校名称"""
    address: Mapped[str] = mapped_column(String(255), nullable=True)
    """学校地址"""
    description: Mapped[str] = mapped_column(Text, nullable=True)
    """学校描述"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    colleges: Mapped[List["College"]] = relationship("College", lazy="selectin", back_populates="school")
    """学校与学院一对多关系"""


class College(FilterModel, Model):
    """学院表"""

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    """学院名称"""
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey(School.id, ondelete="CASCADE"), nullable=False)
    """学校ID"""
    description: Mapped[str] = mapped_column(Text, nullable=True)
    """学院描述"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    school: Mapped[School] = relationship(lazy="selectin", back_populates="colleges")
    """学院与学校一对多关系"""


class GroupSettings(FilterModel, Model):
    """群组设置表

    - 群组与设置是一对一关系
    """

    join_method: Mapped[JoinMethod] = mapped_column(String(32), nullable=True, server_default=JoinMethod.direct)
    """群组设置"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]


class Group(FilterModel, Model):
    """群组表"""

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    """群组名称"""
    creator_id: Mapped[int] = mapped_column(Integer, ForeignKey(User.id), nullable=False)
    """创建者ID"""
    settings_id: Mapped[int] = mapped_column(Integer, ForeignKey(GroupSettings.id), nullable=False)
    """群组设置ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    creator: Mapped[User] = relationship(lazy=False)
    """创建者信息"""
    settings: Mapped[GroupSettings] = relationship("GroupSettings", lazy=False)

    classes: Mapped["Classes"] = relationship(lazy=False, back_populates="group")
    """组与班级一对一关系"""

    @classmethod
    async def create_group(cls, name: str, creator: User) -> "Group":
        """创建群组
        Args:
            creator (User): 创建者信息

        Returns:
            Group: 群组信息
        """
        return await cls(name=name, creator=creator, settings=await GroupSettings().create()).create()

    async def get_binds(self) -> List["GroupBind"]:
        """获取群组绑定信息"""
        return await GroupBind.filter(group_id=self.id).all()


class GroupBind(FilterModel, Model):
    """群组绑定表

    - 群组与平台是一对多关系
    """

    name: Mapped[str] = mapped_column(String(64), nullable=True)
    """平台名称"""
    platform_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    """平台ID"""
    channel_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default=None)
    """频道中的子频道ID或群ID"""
    guild_id: Mapped[str] = mapped_column(String(64), index=True, nullable=True)
    """频道ID"""
    group_id = mapped_column(Integer, ForeignKey(Group.id, ondelete="CASCADE"), nullable=False)
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    group: Mapped[Group] = relationship(lazy=False)
    """群组信息,一个平台绑定一个群组"""

    @classmethod
    async def bind_group(
        cls, platform_name: str, platform_id: str, channel_id: str, guild_id: Optional[str], group: Group
    ) -> "GroupBind":
        """平台与群组之间的绑定

        Args:
            platform_id (str): 平台ID
            channel_id (str): 频道ID或群ID
            guild_id (Optional[str]): 群组ID
            group (Group): 绑定的群组

        Returns:
            GroupBind: 绑定信息
        """
        group_bind = await cls(
            platform_id=platform_id,
            channel_id=channel_id,
            name=platform_name,
            guild_id=guild_id,
            group_id=group.id,
        ).create()
        return group_bind


class Files(FilterModel, Model):
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    """文件名称"""
    file_md5: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    """文件MD5校验"""
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    """文件路径"""
    suffix: Mapped[str | None] = mapped_column(String(12), nullable=True)
    """文件后缀"""
    created_at: Mapped[CreateAt]
    """创建时间"""

    @classmethod
    async def file_duplicate(cls, file_md5: str) -> bool:
        """检查文件是否重复"""
        return await cls.filter(file_md5=file_md5).exists()

    @classmethod
    async def get_file(cls, file_md5: str) -> Optional["Files"]:
        """获取文件信息"""
        return await cls.filter(file_md5=file_md5).first()

    @classmethod
    async def new(
        cls,
        file_md5: str,
        file_path: Path,
        *,
        name: str | None = None,
        suffix: str | None = None,
    ):
        """创建文件信息

        Args:
            file_md5 (str): 文件MD5校验
            file_path (Path): 文件路径(包含文件名)
            name (str): 文件名
            suffix (str): 文件后缀
        """
        # 如果名字为None从path.name中获取，并且去掉后缀
        name = name or file_path.stem
        suffix = suffix or file_path.suffix.lstrip(".")
        return await cls(
            name=name,
            file_md5=file_md5,
            file_path=str(file_path.parent.relative_to(data_dir)),
            suffix=suffix,
        ).create()

    @classmethod
    async def parse_data(
        cls,
        file_data: bytes,
        save_path: Path,
        *,
        suffix: str | None = None,
        file_md5: str | None = None,
    ) -> "Files":
        """解析文件数据

        Args:
            file_data (bytes): 文件数据
            save_path (Path): 保存路径(不包含文件名)
            suffix (str): 文件后缀
        """
        file_md5 = file_md5 if file_md5 else md5(file_data).hexdigest()
        save_path.mkdir(parents=True, exist_ok=True)
        suffix = suffix or get_file_suffix(file_data)
        file_path = save_path / (f"{file_md5}.{suffix}" if suffix else file_md5)
        file_path.write_bytes(file_data)
        return await cls.new(file_md5, file_path, suffix=suffix, name=file_md5)

    @property
    def path(self) -> Path:
        return data_dir / self.file_path / self.file_name

    @property
    def file_name(self) -> str:
        return f"{self.name}.{self.suffix.lstrip('.')}" if self.suffix else self.name

    def read_bytes(self) -> bytes:
        return self.path.read_bytes()

    def read_text(self, encoding: str | None = None) -> str:
        return self.path.read_text(encoding=encoding)

    async def delete(self):
        """输出文件，同时删除本地文件"""
        self.path.unlink(True)
        await super().delete()


class Teacher(FilterModel, Model):
    """教师表

    - 教师与用户是一对一关系
    - 教师与班级是多对多关系
    """

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    """教师姓名"""
    role: Mapped[TeacherRole] = mapped_column(String(64), nullable=False, server_default=TeacherRole.teacher)
    """教师角色"""
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False, unique=True)
    """用户ID"""
    school_id: Mapped[int | None] = mapped_column(Integer, ForeignKey(School.id, ondelete="CASCADE"), nullable=True)
    """学校ID"""
    college_id: Mapped[int | None] = mapped_column(Integer, ForeignKey(College.id, ondelete="CASCADE"), nullable=True)
    """学院ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    user: Mapped[User] = relationship("User", lazy=False, back_populates="teacher")

    classes: Mapped[List["Classes"]] = relationship(
        "Classes",
        secondary="bot_teacher_classes",
        lazy="selectin",
        back_populates="teacher",
    )
    """教师与班级多对多关系"""

    @classmethod
    async def create_teacher(cls, name: str, user: User) -> "Teacher":
        """创建教师

        Args:
            name (str): 教师姓名
            user (User): 用户信息

        Returns:
            Teacher: 教师信息
        """
        print(user.role)
        assert user.role != UserRole.student, "teacher role is not student"
        teacher = await cls(name=name, user=user).create()
        await user.update(role=UserRole.teacher)
        return teacher

    @classmethod
    async def get_teacher(cls, user: User) -> Optional["Teacher"]:
        """获取教师信息

        Args:
            user (User): 用户信息

        Returns:
            Optional[Teacher]: 教师信息
        """
        return await cls.filter(user_id=user.id).first()

    @classmethod
    async def get_or_create_teacher(cls, name: str, user: User) -> "Teacher":
        """获取或创建教师信息

        Args:
            user (User): 用户信息
            name (str): 教师姓名

        Returns:
            Teacher: 教师信息
        """
        if teacher := await cls.get_teacher(user):
            return teacher
        return await cls.create_teacher(name, user)

    async def get_classes(
        self,
        platform_id: str | int,
        channel_id: str | None = None,
        guild_id: str | None = None,
    ) -> Optional["Classes"]:
        """查找教师所在的班级

        Args:
            platform_id (str | int): 平台id
                当为int时为classes.id
                当为str时判断channel_id
                    None时表示classes.name搜索
            channel_id (str | None, optional): 群或子频道id. Defaults to None.
            guild_id (str | None, optional): 群组id. Defaults to None.

        Returns:
            Optional["Classes"]: 班级信息
        """
        condition = TeacherClasses.teacher_id == self.id
        if isinstance(platform_id, int):
            condition &= TeacherClasses.classes_id == platform_id
        else:
            condition &= GroupBind.platform_id == platform_id
            if channel_id:
                condition &= GroupBind.channel_id == channel_id
            if guild_id:
                condition &= GroupBind.guild_id == guild_id
        return await Classes.select.join(TeacherClasses).join(Group).join(GroupBind).where(condition).first()

    async def bind_classes(self, classes: "Classes"):
        """绑定班级

        Args:
            classes (Classes): 班级信息
        """
        async with get_session() as session:
            self.classes.append(classes)
            await session.commit()
            await session.refresh(self)

    async def get_students(self):
        """获取教师所在班级的学生信息"""
        students = await Student.select.join(Classes).join(TeacherClasses).where(TeacherClasses.teacher_id == self.id)
        return list(students)


class Classes(FilterModel, Model):
    """班级表

    - 班级与教师是多对多关系
    - 班级与群组是一对一关系
    """

    name: Mapped[str] = mapped_column(__name_pos=String(64), nullable=False)
    """班级名称"""
    major: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """专业名称"""
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Group.id, ondelete="CASCADE"), nullable=False, unique=True
    )
    """群组ID"""
    college_id: Mapped[int | None] = mapped_column(Integer, ForeignKey(College.id, ondelete="CASCADE"), nullable=True)
    """学院ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    group: Mapped[Group] = relationship(lazy=False, back_populates="classes")
    """班级与群组一对一关系"""
    teacher: Mapped[List[Teacher]] = relationship(
        "Teacher",
        secondary="bot_teacher_classes",
        lazy="selectin",
        back_populates="classes",
    )
    """班级与教师多对多关系"""

    async def get_task(self, task_id: int | str) -> Optional["Tasks"]:
        """获取任务信息

        Args:
            task_id (int | str): 任务ID或任务名称

        Returns:
            Optional["Tasks"]: 任务信息
        """

        if isinstance(task_id, str):
            return await Tasks.filter(classes=self, name=task_id).first()
        return await Tasks.filter(classes=self, id=task_id).first()

    async def get_tasks(self) -> List["Tasks"]:
        return await Tasks.filter(classes=self).all()

    async def get_join_requests(self) -> List["ClassesJoinRequest"]:
        return await ClassesJoinRequest.filter(classes_id=self.id).all()

    async def get_students(self) -> List["Student"]:
        return await Student.filter(classes_id=self.id).all()

    async def student_count(self) -> int:
        """获取班级学生数量"""
        return await Student.filter(classes_id=self.id).count()

    async def user_join_classes(self, user: User):
        """用户加入班级

        Args:
            user (User): 用户信息
        """
        if user.student is None:  # 创建学生
            await Student.create_student(user.nickname, self, user)
        else:  # 如果已经是学生则更新班级
            await user.student.update_classes(self)

    async def apply_join_classes(self, user: User, describe: str | None = None):
        """申请加入班级

        Args:
            user (User): 用户信息
            describe (str): 申请描述
        """
        classes_join_request = await ClassesJoinRequest(
            classes_id=self.id,
            user_id=user.id,
            join_method=JoinMethod.apply,
            describe=describe,
        ).create()
        return classes_join_request

    @classmethod
    async def get_classes(
        cls,
        platform_id: str | int,
        channel_id: str | None = None,
        guild_id: str | None = None,
    ) -> Optional["Classes"]:
        """获取班级信息

        这种获取方式为全局查询,无法使用班级名称来查询

        Args:
            platform_id (str): 平台ID 或 classes.id
            channel_id (str): 频道ID
            guild_id (str | None, optional): 群组ID. Defaults to None.

        Returns:
            Optional[Classes]: 班级信息
        """
        if isinstance(platform_id, int):
            return await cls.filter(id=platform_id).first()

        assert channel_id is not None, "channel_id is None"

        condition = (GroupBind.platform_id == platform_id) & (GroupBind.channel_id == channel_id)
        if guild_id:
            condition &= GroupBind.guild_id == guild_id
        if group_bind := await GroupBind.filter(condition).first():
            return group_bind.group.classes

    @classmethod
    async def create_classes(
        cls,
        name: str,
        platform_name: str,
        platform_id: str,
        channel_id: str,
        guild_id: str | None,
        user: User,
    ) -> "Classes":
        """创建班级

        先创建组然后将组与平台绑定，最后创建班级

        Args:
            name (str): 班级名称
            platform_id (str): 平台ID
            channel_id (str): 频道ID
            guild_id (str | None): 群组ID
            user (User): 用户信息

        Returns:
            Classes: 班级信息
        """
        group = await Group.create_group(name, user)  # 创建群组
        await GroupBind.bind_group(platform_name, platform_id, channel_id, guild_id, group)  # 绑定群组
        return await cls(name=name, group=group).create()  # 创建班级

    async def bind_teacher(self, teacher: Teacher, role: TeacherRole | None = None):
        """绑定教师

        Args:
            teacher (Teacher): 教师信息
        """
        await TeacherClasses.association(teacher, self)

    async def update_teacher_role(self, teacher: Teacher, role: TeacherClassesRole):
        """更新教师角色

        Args:
            teacher (Teacher): 教师信息
            role (TeacherRole): 教师角色
        """

        await TeacherClasses.filter(teacher_id=teacher.id, classes_id=self.id).update(role=role)

    async def get_leaves(self) -> list["StudentLeave"]:
        return await StudentLeave.filter(classes_id=self.id).all()


class ClassesJoinRequest(FilterModel, Model):
    classes_id: Mapped[int] = mapped_column(Integer, ForeignKey(Classes.id, ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    join_method: Mapped[JoinMethod] = mapped_column(String(32), nullable=False)
    describe: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[CreateAt]

    classes: Mapped[Classes] = relationship(lazy="selectin")
    user: Mapped[User] = relationship(lazy="selectin")


# 教师与班级多对多关系
class TeacherClasses(FilterModel, Model):
    """教师与班级关联表"""

    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey(Teacher.id, ondelete="CASCADE"), nullable=False)
    """教师ID"""
    classes_id: Mapped[int] = mapped_column(Integer, ForeignKey(Classes.id, ondelete="CASCADE"), nullable=False)
    """班级ID"""
    role: Mapped[TeacherClassesRole] = mapped_column(
        String(32), nullable=False, server_default=TeacherClassesRole.teacher
    )
    """教师在班级中担任的角色"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    @classmethod
    async def association(
        cls,
        teacher: Teacher,
        classes: Classes,
        role: TeacherClassesRole = TeacherClassesRole.teacher,
    ):
        """教师与班级关联

        Args:
            teacher (Teacher): 教师
            classes (Classes): 班级
        """
        teacher_classes = await cls(teacher_id=teacher.id, role=role, classes_id=classes.id).create()
        return teacher_classes


class Student(FilterModel, Model):
    """学生表"""

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    """学生姓名"""
    classes_id: Mapped[int] = mapped_column(Integer, ForeignKey(Classes.id, ondelete="CASCADE"), nullable=False)
    """班级ID"""
    school_id: Mapped[int | None] = mapped_column(Integer, ForeignKey(School.id, ondelete="CASCADE"), nullable=True)
    """学校ID"""
    user_id = mapped_column(Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False, unique=True)
    role: Mapped[StudentRole] = mapped_column(String(32), nullable=False, server_default=StudentRole.student)
    """学生额外信息ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    classes: Mapped[Classes] = relationship(lazy=False)
    """学生与班级一对一关系"""
    user: Mapped[User] = relationship(lazy=False, back_populates="student")
    """学生与用户一对一关系"""
    extra: Mapped["StudentExtra"] = relationship(lazy=False, back_populates="student")
    """学生与额外信息一对一关系"""

    @classmethod
    async def create_student(
        cls, name: str, classes: Classes, user: User, school_id: int | None = None, **kwargs
    ) -> "Student":
        """创建学生

        Args:
            name (str): 学生姓名
            classes (Classes): 班级信息
            user (User): 用户信息
            school_id (int | None): 学校ID
            **kwargs: 额外信息

        Returns:
            Student: 学生信息
        """

        student = await cls(name=name, classes=classes, user=user, school_id=school_id).create()
        await StudentExtra(student=student).create()  # 创建学生额外信息
        return student

    async def update_classes(self, classes: Classes):
        """更新班级信息

        Args:
            classes (Classes): 班级信息
        """
        await self.update(
            classes=classes,
            role=StudentRole.student,
        )

    async def get_classmates(self) -> list["Student"]:
        return await Student.filter(classes_id=self.classes_id).all()

    async def get_leaves(self) -> List["StudentLeave"]:
        return await StudentLeave.filter(student_id=self.id).all()


class StudentExtra(FilterModel, Model):
    """学生额外信息表"""

    student_id: Mapped[int] = mapped_column(Integer, ForeignKey(Student.id, ondelete="CASCADE"), nullable=False)
    """学生ID"""
    student_code: Mapped[str] = mapped_column(String(32), index=True, nullable=True)
    """学号"""
    dormitory: Mapped[str] = mapped_column(String(32), nullable=True)
    """寝室号"""
    political_status: Mapped[PoliticalStatus] = mapped_column(String(32), nullable=True)
    """政治面貌"""
    family_contact: Mapped[str] = mapped_column(String(11), nullable=True)
    """家庭联系方式"""
    family_address: Mapped[str] = mapped_column(String(255), nullable=True)
    """家庭地址"""
    nation: Mapped[str] = mapped_column(String(32), nullable=True)
    """民族"""
    updated_at: Mapped[UpdateAt]

    student: Mapped[Student] = relationship(lazy=False, back_populates="extra")

    async def update_extra(self, **kwargs):
        """更新学生额外信息"""
        await self.update(**kwargs)


class Tasks(FilterModel, Model):
    """任务表"""

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    """任务名称"""
    classes_id: Mapped[int] = mapped_column(Integer, ForeignKey(Classes.id, ondelete="CASCADE"), nullable=False)
    """班级ID"""
    creator_id: Mapped[int] = mapped_column(Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    """创建者ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    classes: Mapped[Classes] = relationship(lazy=False)
    """任务与班级一对多关系"""
    creator: Mapped[User] = relationship(lazy=False)

    async def get_commits(self) -> List["TaskCommits"]:
        """获取任务提交信息"""
        return await TaskCommits.filter(task_id=self.id).all()

    @classmethod
    async def create_task(
        cls,
        name: str,
        classes: Classes,
        creator: User,
        creator_role: Literal["teacher", "student"],
    ) -> "Tasks":
        """创建任务

        Args:
            name (str): 任务名称
            classes (Classes): 班级信息
            creator (User): 创建者信息
            creator_role (Literal["teacher", "student"]): 创建者角色

        Returns:
            Tasks: 任务信息
        """
        task = await cls(
            name=name,
            classes_id=classes.id,
            creator_id=creator.id,
            creator_role=creator_role,
        ).create()
        return task

    async def delete(self):
        """删除任务"""
        for commit in await self.get_commits():
            await commit.file.delete()
        return await self.filter(id=self.id).delete()

    # 检查学生是否已提交
    async def check_commit(self, student: Student) -> bool:
        return await TaskCommits.filter(task_id=self.id, student_id=student.id).exists()

    async def commit(self, student: Student, file_data: bytes) -> "TaskCommits":
        file = await Files.parse_data(
            file_data,
            task_dir,
        )
        task_commit = await TaskCommits(
            file_id=file.id,
            task_id=self.id,
            student_id=student.id,
        ).create()
        return task_commit

    async def get_commit(self, student: Student) -> Optional["TaskCommits"]:
        return await TaskCommits.filter(task_id=self.id, student_id=student.id).first()


class TaskCommits(FilterModel, Model):
    """任务文件表"""

    task_id: Mapped[int] = mapped_column(Integer, ForeignKey(Tasks.id, ondelete="CASCADE"), nullable=False)
    """任务ID"""
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey(Files.id), nullable=False, unique=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey(Student.id, ondelete="CASCADE"), nullable=False)
    """学生ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    file: Mapped[Files] = relationship(lazy=False)
    """文件信息"""
    task: Mapped[Tasks] = relationship(lazy=False)
    """任务信息"""
    student: Mapped[Student] = relationship(lazy=False)
    """学生信息"""

    async def update_file(self, file: Files | bytes):
        """更新文件"""
        await self.file.delete()  # 删除旧的文件
        if isinstance(file, bytes):  # 如果是bytes则解析文件
            file = await Files.parse_data(file, task_dir)
        await self.filter(id=self.id).update(file=file)  # 更新文件信息


class ScheduledNotice(FilterModel, Model):
    creator_id: Mapped[int] = mapped_column(Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    """通知标题"""
    notice_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    """通知时间"""
    recipients: Mapped[str] = mapped_column(Text, nullable=True)
    """通知对象"""
    messages: Mapped[str] = mapped_column(Text, nullable=False)
    """通知内容"""
    creator: Mapped[User] = relationship(lazy=False)
    """创建者信息"""


class CurriculaTimetable(FilterModel, Model):
    """课程表时间表"""

    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=True)
    """用户ID"""
    classes_id: Mapped[int | None] = mapped_column(Integer, ForeignKey(Classes.id, ondelete="CASCADE"), nullable=True)
    """班级ID"""
    school_id: Mapped[int | None] = mapped_column(Integer, ForeignKey(School.id, ondelete="CASCADE"), nullable=True)
    """学校ID"""
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    """周数"""
    timetable: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default="[]")
    """课程表内容"""

    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]


# 班级或学生课表配置项
class CurriculaConfig(FilterModel, Model):
    name: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=False, index=True)
    """课表配置项名称，一般是班级名称"""
    classes_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey(Classes.id, ondelete="CASCADE"), nullable=True, unique=True
    )
    """班级ID"""
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=True, unique=True
    )
    """用户ID"""
    current_week: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    """当前周"""
    is_notify: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    """是否开启课前通知"""
    school_id: Mapped[int | None] = mapped_column(Integer, ForeignKey(School.id, ondelete="CASCADE"), nullable=True)
    """学校ID"""
    create_at: Mapped[CreateAt]
    update_at: Mapped[UpdateAt]

    user: Mapped[User | None] = relationship(lazy=False)
    classes: Mapped[Classes | None] = relationship(lazy=False)
    share_config: Mapped[list["CurriculaConfig"]] = relationship("ShareCurriculaConfig", lazy="selectin")

    @classmethod
    async def query(cls, name: str):
        """查询课表配置项(待修改,后续需要增加学校ID)"""
        return await cls.filter(name=name, user_id=None).first()

    async def get_curricula(self) -> list["Curricula"]:
        """获取配置项中的所有课表"""
        return await Curricula.filter(config_id=self.id).all()


# 共享课表
class ShareCurriculaConfig(FilterModel, Model):
    config_id: Mapped[int] = mapped_column(Integer, ForeignKey(CurriculaConfig.id, ondelete="CASCADE"), nullable=False)
    """用户ID"""
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    """用户ID"""
    create_at: Mapped[CreateAt]
    update_at: Mapped[UpdateAt]

    user: Mapped[User] = relationship(lazy=False)
    config: Mapped[CurriculaConfig] = relationship(lazy=False, back_populates="share_config")


# 课表
class Curricula(FilterModel, Model):
    config_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(CurriculaConfig.id, ondelete="CASCADE"),
        nullable=False,
    )
    weeks: Mapped[list[int]] = mapped_column(JSON, nullable=False, server_default="[]")
    """周几"""
    weekday: Mapped[list[int]] = mapped_column(JSON, nullable=False, server_default="[]")
    """星期几"""
    lesson: Mapped[list[int]] = mapped_column(JSON, nullable=False, server_default="[]")
    """第几节课"""
    course: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    """课程名称"""
    teacher: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """教师"""
    classroom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    """教室"""
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    """地点"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    async def get_teacher(self) -> Teacher | None:
        return await Teacher.filter(name=self.teacher).first()


class LeaveConfig(FilterModel, Model):
    classes_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Classes.id, ondelete="CASCADE"), nullable=True, unique=True
    )
    """班级ID"""
    school_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(School.id, ondelete="CASCADE"), nullable=True, unique=True
    )
    """学校ID"""
    workflow: Mapped[list] = mapped_column(JSON, nullable=False, server_default="[]")
    """审批工作流"""
    create_at: Mapped[CreateAt]
    update_at: Mapped[UpdateAt]


class LeaveWorkflow(FilterModel, Model):
    """请假审批流程
    当用户创建请假申请会从审批流程中获取审批人生成请假审批表
    """

    less_day: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    """小于多少天进入该审批流程"""
    classes_id: Mapped[int] = mapped_column(Integer, ForeignKey(Classes.id, ondelete="CASCADE"), nullable=False)
    """班级的请假申请表"""
    shool_id: Mapped[int] = mapped_column(Integer, ForeignKey(School.id, ondelete="CASCADE"), nullable=False)
    """学校的请假申请表"""
    order: Mapped[list] = mapped_column(JSON, nullable=False, server_default="[]")
    """审批顺序(用户ID)"""

    async def order_users(self) -> list[User]:
        users = []
        for uid in self.order:
            if user := User.filter(id=uid).first():
                users.append(user)
            else:
                raise ValueError("用户不存在")
        return users


class StudentLeave(FilterModel, Model):
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    """请假开始时间"""
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    """请假结束时间"""
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    """请假原因"""
    classes_id: Mapped[int] = mapped_column(Integer, ForeignKey(Classes.id, ondelete="CASCADE"), nullable=False)
    """班级ID"""
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey(Student.id, ondelete="CASCADE"), nullable=False)
    """用户ID"""
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey(Files.id, ondelete="CASCADE"), nullable=False)
    """请假条文件ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    file: Mapped[Files] = relationship(lazy=False)
    student: Mapped[Student] = relationship(lazy=False)
    classes: Mapped[Classes] = relationship(lazy=False)

    @property
    def leave_day(self) -> int:
        """请假天数,只要是超过当天则+1"""
        leave_date = self.end_date - self.start_date
        return leave_date.days

    async def get_approval(self) -> List["StudentLeaveApproval"]:
        """获取请假审批信息"""
        return await StudentLeaveApproval.filter(leave_id=self.id).all()

    async def create_approval(self):
        """创建请假审批信息"""
        leave_approvals = []

        if self.student.school_id:
            leave_workflows = await LeaveWorkflow.filter(shool_id=self.student.school_id).all()
        elif self.student.classes_id:
            leave_workflows = await LeaveWorkflow.filter(classes_id=self.student.classes_id).all()
        else:
            raise ValueError("异常请假申请,没有班级或学校ID")

        if not leave_workflows:
            raise ValueError("没有请假审批流程")
        for workflow in leave_workflows:
            # 如果请假天数大于审批流程的天数则跳过
            if self.leave_day > workflow.less_day:
                continue
            for approver in await workflow.order_users():
                if (
                    leave_approval := await StudentLeaveApproval.filter(
                        leave_id=self.id,
                        approver_id=approver.id,
                    ).first()
                ) is None:
                    leave_approval = await StudentLeaveApproval(
                        leave_id=self.id,
                        approver_id=approver.id,
                        workflow_id=workflow.id,
                        status=LeaveStatus.leave_pending,
                    ).create()
                leave_approvals.append(leave_approval)
            return leave_approvals


class StudentLeaveApproval(FilterModel, Model):
    """请假审批表"""

    workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey(LeaveWorkflow.id, ondelete="CASCADE"), nullable=False)
    """请假审批流程ID"""
    leave_id: Mapped[int] = mapped_column(Integer, ForeignKey(StudentLeave.id, ondelete="CASCADE"), nullable=False)
    """请假ID"""
    approver_id: Mapped[int] = mapped_column(Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    """审批人ID"""
    status: Mapped[LeaveStatus] = mapped_column(String(16), nullable=False)
    """审批状态"""
    comment: Mapped[str] = mapped_column(Text, nullable=True)
    """审批意见"""

    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    leave: Mapped[StudentLeave] = relationship(lazy=False)
    """请假审批表与请假申请表一对多关系"""
    approver: Mapped[User] = relationship(lazy=False)
    """请假审批表与用户一对一关系"""
    workflow: Mapped[LeaveWorkflow] = relationship(lazy=False)
    """请假审批表与请假审批流程一对多关系"""

    @property
    def is_pass(self) -> bool:
        """是否通过"""
        return self.status == LeaveStatus.leave_pass


class EducationSystem(FilterModel, Model):
    """教学系统表"""

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    """关联的用户ID"""
    account: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    """教学系统账号"""
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    """教学系统密码"""
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey(School.id, ondelete="CASCADE"), nullable=True)
    """学校ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    user: Mapped[User] = relationship(lazy=False)
    """关联的用户"""
