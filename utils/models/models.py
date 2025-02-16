import json
from hashlib import md5
from datetime import datetime
from typing import List, Literal, Optional

from utils.config import task_dir
from nonebot_plugin_orm import Model, get_session
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy import Text, String, Integer, DateTime, ForeignKey, select, update

from .filters import FilterModel
from .columns import CreateAt, UpdateAt, PrimaryKeyInteger
from .enums import UserRole, JoinMethod, StudentRole, TeacherRole, PoliticalStatus


class User(FilterModel, Model):
    """用户表"""

    __tablename__ = "user"
    id: Mapped[PrimaryKeyInteger]
    nickname: Mapped[str] = mapped_column(String(255), nullable=False)
    """用户昵称"""
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    """用户名"""
    password: Mapped[str] = mapped_column(String(255), nullable=True)
    """用户密码"""
    email: Mapped[str] = mapped_column(String(255), nullable=True, unique=True)
    """邮箱"""
    avatar: Mapped[str] = mapped_column(String(255), nullable=True)
    """头像"""
    phone: Mapped[str] = mapped_column(String(11), nullable=True, unique=True)
    """手机号"""
    role: Mapped[UserRole] = mapped_column(
        String(32), nullable=False, server_default=UserRole.user
    )
    """用户角色"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    teacher: Mapped["Teacher"] = relationship(
        "Teacher", lazy=False, back_populates="user"
    )
    student: Mapped[Optional["Student"]] = relationship(
        "Student", lazy=False, back_populates="user"
    )
    """一个用户绑定一个学生"""
    binds: Mapped[List["Bind"]] = relationship(
        "Bind", lazy="selectin", back_populates="user"
    )
    """一个用户可以绑定多个表"""

    async def get_join_requests(self) -> List["ClassesJoinRequest"]:
        """获取到用户的所有申请加入班级的请求"""
        return await ClassesJoinRequest.filter(user_id=self.id).all()

    async def get_groups(self) -> List["Group"]:
        """获取到用户创建的所有群组"""
        return await Group.filter(creator_id=self.id).all()

    @property
    def is_admin(self) -> bool:
        """是否是管理员"""
        return self.role == UserRole.admin

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

    async def get_bind(self, platform_id: str) -> Optional["Bind"]:
        """获取用户绑定信息

        Args:
            platform_id (str): 平台ID

        Returns:
            Optional[Bind]: 绑定信息
        """
        return await Bind.filter(user_id=self.id, platform_id=platform_id).first()

    async def get_notices(self) -> List["ScheduledNotice"]:
        """获取用户的通知任务"""
        return await ScheduledNotice.filter(user_id=self.id).all()

    async def get_curriculum_config(self) -> Optional["CurriculumConfig"]:
        return await CurriculumConfig.filter(user_id=self.id).first()


class Bind(FilterModel, Model):
    """用户与平台绑定表

    - 用户与平台是一对多关系
    """

    __tablename__ = "bind"
    id: Mapped[PrimaryKeyInteger]
    platform_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    """平台ID"""
    account_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    """平台关联ID"""
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False
    )
    """绑定的用户ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    user: Mapped[User] = relationship(lazy=False, back_populates="binds")

    @classmethod
    async def get_bind(
        cls,
        platform_id: str,
        account_id: str,
    ) -> Optional["Bind"]:
        """获取绑定信息

        Args:
            platform_id (str): 平台ID
            account_id (str): 平台用户ID

        Returns:
            Optional[Bind]: 绑定信息
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
    ) -> "Bind":
        """平台与用户之间的绑定

        Args:
            platform_id (str): 平台ID
            account_id (str): 平台用户ID
            user (User): 绑定的用户

        Returns:
            Bind: 绑定信息
        """
        async with get_session() as session:
            where_and = (Bind.platform_id == platform_id) & (
                Bind.account_id == account_id
            )
            if bind := await session.scalar(select(Bind).where(where_and)):
                # 查看之前绑定的用户是否是当前用户
                if bind.user_id == user.id:
                    return bind
                # 查看之前绑定的用户是否只有这一次绑定，如果是只有一次绑定则删除该用户
                old_user = bind.user  # 获取之前绑定的用户的id
                await session.execute(update(Bind).where(where_and).values(user=user))
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

    async def delete(self):
        """删除绑定"""
        async with get_session() as session:
            await session.delete(self)
            await session.commit()


class Group(FilterModel, Model):
    """群组表"""

    __tablename__ = "group"
    id: Mapped[PrimaryKeyInteger]
    creator_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(User.id), nullable=False
    )
    """创建者ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    creator: Mapped[User] = relationship(lazy="selectin")
    """创建者信息"""
    group_binds: Mapped[List["GroupBind"]] = relationship(
        "GroupBind", lazy="selectin", back_populates="group"
    )
    """一个组绑定多个平台"""

    classes: Mapped["Classes"] = relationship(
        "Classes", lazy="selectin", back_populates="group"
    )
    """组与班级一对一关系"""

    @classmethod
    async def create_group(cls, creator: User) -> "Group":
        """创建群组

        Args:
            creator (User): 创建者信息

        Returns:
            Group: 群组信息
        """
        return await cls(creator=creator).create()


class GroupBind(FilterModel, Model):
    """群组绑定表

    - 群组与平台是一对多关系
    """

    __tablename__ = "group_bind"
    id: Mapped[PrimaryKeyInteger]
    platform_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    channel_id: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False, default=None
    )
    """频道中的子频道ID或群ID"""
    guild_id: Mapped[str] = mapped_column(String(64), index=True, nullable=True)
    """频道ID"""
    group_id = mapped_column(
        Integer, ForeignKey(Group.id, ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    group: Mapped[Group] = relationship(
        "Group", lazy="selectin", back_populates="group_binds"
    )
    """群组信息,一个平台绑定一个群组"""

    @classmethod
    async def bind_group(
        cls, platform_id: str, channel_id: str, guild_id: Optional[str], group: Group
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
            guild_id=guild_id,
            group_id=group.id,
        ).create()
        return group_bind


class Teacher(FilterModel, Model):
    """教师表

    - 教师与用户是一对一关系
    - 教师与班级是多对多关系
    """

    __tablename__ = "teacher"
    id: Mapped[PrimaryKeyInteger]
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    """教师姓名"""
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    """用户ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    user: Mapped[User] = relationship("User", lazy=False, back_populates="teacher")

    classes: Mapped[List["Classes"]] = relationship(
        "Classes",
        secondary="teacher_classes",
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
        teacher = await cls(name=name, user=user).create()
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
            condition &= Classes.name == platform_id
            if channel_id:
                condition &= GroupBind.channel_id == channel_id
            if guild_id:
                condition &= GroupBind.guild_id == guild_id
        return (
            await Classes.select.join(TeacherClasses)
            .join(Group)
            .join(GroupBind)
            .where(condition)
            .first()
        )

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
        students = (
            await Student.select.join(Classes)
            .join(TeacherClasses)
            .where(TeacherClasses.teacher_id == self.id)
        )
        return list(students)


class Classes(FilterModel, Model):
    """班级表

    - 班级与教师是多对多关系
    - 班级与群组是一对一关系
    """

    __tablename__ = "classes"
    id: Mapped[PrimaryKeyInteger]
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    """班级名称"""
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("group.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    join_method: Mapped[JoinMethod] = mapped_column(
        String(32), nullable=True, server_default=JoinMethod.direct
    )
    """群组ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    group: Mapped[Group] = relationship(lazy="selectin", back_populates="classes")
    """班级与群组一对一关系"""
    teacher: Mapped[List[Teacher]] = relationship(
        "Teacher",
        secondary="teacher_classes",
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

        condition = (GroupBind.platform_id == platform_id) & (
            GroupBind.channel_id == channel_id
        )
        if guild_id:
            condition &= GroupBind.guild_id == guild_id
        if group_bind := await GroupBind.filter(condition).first():
            return group_bind.group.classes

    @classmethod
    async def create_classes(
        cls,
        name: str,
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
        group = await Group.create_group(user)  # 创建群组
        await GroupBind.bind_group(platform_id, channel_id, guild_id, group)  # 绑定群组
        return await cls(name=name, group=group).create()  # 创建班级

    async def bind_teacher(self, teacher: Teacher, role: TeacherRole | None = None):
        """绑定教师

        Args:
            teacher (Teacher): 教师信息
        """
        await TeacherClasses.association(teacher, self)

    async def update_teacher_role(self, teacher: Teacher, role: TeacherRole):
        """更新教师角色

        Args:
            teacher (Teacher): 教师信息
            role (TeacherRole): 教师角色
        """

        await TeacherClasses.filter(teacher_id=teacher.id, classes_id=self.id).update(
            role=role
        )


class ClassesJoinRequest(FilterModel, Model):
    id: Mapped[PrimaryKeyInteger]
    classes_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Classes.id, ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False
    )
    join_method: Mapped[JoinMethod] = mapped_column(String(32), nullable=False)
    describe: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[CreateAt]

    classes: Mapped[Classes] = relationship(lazy="selectin")
    user: Mapped[User] = relationship(lazy="selectin")


# 教师与班级多对多关系
class TeacherClasses(FilterModel, Model):
    """教师与班级关联表"""

    __tablename__ = "teacher_classes"
    id: Mapped[PrimaryKeyInteger]
    teacher_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Teacher.id, ondelete="CASCADE"), nullable=False
    )
    """教师ID"""
    classes_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Classes.id, ondelete="CASCADE"), nullable=False
    )
    """班级ID"""
    role: Mapped[TeacherRole] = mapped_column(
        String(32), nullable=False, server_default=TeacherRole.teacher
    )
    """教师角色"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    @classmethod
    async def association(
        cls,
        teacher: Teacher,
        classes: Classes,
    ):
        """教师与班级关联

        Args:
            teacher (Teacher): 教师
            classes (Classes): 班级
        """
        teacher_classes = await cls(
            teacher_id=teacher.id, classes_id=classes.id
        ).create()
        return teacher_classes


class Student(FilterModel, Model):
    """学生表"""

    __tablename__ = "student"
    id: Mapped[PrimaryKeyInteger]
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    """学生姓名"""
    classes_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Classes.id, ondelete="CASCADE"), nullable=False
    )
    user_id = mapped_column(
        Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False, unique=True
    )
    role: Mapped[StudentRole] = mapped_column(
        String(32), nullable=False, server_default=StudentRole.student
    )
    """班级ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    classes: Mapped[Classes] = relationship(lazy="selectin")
    """学生与班级一对多关系"""
    user: Mapped[User] = relationship(lazy=False, back_populates="student")
    """学生与用户一对一关系"""
    extra: Mapped["StudentExtra"] = relationship(
        lazy="selectin", back_populates="student", uselist=False
    )
    """学生额外信息"""

    @classmethod
    async def create_student(cls, name: str, classes: Classes, user: User) -> "Student":
        """创建学生

        Args:
            name (str): 学生姓名
            classes (Classes): 班级信息
            user (User): 用户信息

        Returns:
            Student: 学生信息
        """
        student = await cls(name=name, classes=classes, user=user).create()
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


class StudentExtra(FilterModel, Model):
    """学生额外信息表"""

    __tablename__ = "student_extra"
    id: Mapped[PrimaryKeyInteger]
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Student.id, ondelete="CASCADE"), nullable=False, unique=True
    )
    sex: Mapped[str] = mapped_column(String(32), nullable=True)
    student_code: Mapped[str] = mapped_column(String(32), index=True, nullable=True)
    """学号"""
    dormitory: Mapped[str] = mapped_column(String(32), nullable=True)
    """寝室号"""
    political_status: Mapped[PoliticalStatus] = mapped_column(String(32), nullable=True)
    """政治面貌"""
    family_contact: Mapped[str] = mapped_column(String(11), nullable=True)
    """家庭联系方式"""
    updated_at: Mapped[UpdateAt]

    student: Mapped[Student] = relationship(lazy="selectin", back_populates="extra")


class Tasks(FilterModel, Model):
    """任务表"""

    __tablename__ = "tasks"
    id: Mapped[PrimaryKeyInteger]
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    """任务名称"""
    classes_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Classes.id, ondelete="CASCADE"), nullable=False
    )
    """班级ID"""
    creator_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False
    )
    """创建者ID"""
    creator_role: Mapped[TeacherRole] = mapped_column(
        String(32), nullable=False, server_default=TeacherRole.teacher
    )
    """创建者角色"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    classes: Mapped[Classes] = relationship(lazy="selectin")
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
            commit.read_path.unlink(missing_ok=True)
        return await self.filter(id=self.id).delete()

    # 检查学生是否已提交
    async def check_commit(self, student: Student) -> bool:
        return await TaskCommits.filter(task_id=self.id, student_id=student.id).exists()

    async def commit(self, student: Student, file_data: bytes):
        file_md5 = md5(file_data).hexdigest()
        file_path = self.classes.name
        task_commit = await TaskCommits(
            task_id=self.id,
            file_md5=file_md5,
            file_path=file_path,
            student_id=student.id,
        ).create()
        task_commit.save_data(file_data)
        return task_commit

    async def get_commit(self, student: Student) -> Optional["TaskCommits"]:
        return await TaskCommits.filter(task_id=self.id, student_id=student.id).first()


class TaskCommits(FilterModel, Model):
    """任务文件表"""

    __tablename__ = "task_files"
    id: Mapped[PrimaryKeyInteger]
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Tasks.id, ondelete="CASCADE"), nullable=False
    )
    """任务ID"""
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    """文件ID"""
    file_md5: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    """文件MD5校验"""
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Student.id, ondelete="CASCADE"), nullable=False
    )
    """学生ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    task: Mapped[Tasks] = relationship(lazy="selectin")
    """任务信息"""
    student: Mapped[Student] = relationship(lazy="selectin")
    """学生信息"""

    async def update_file(self, data: bytes):
        """更新文件"""
        file_md5 = md5(data).hexdigest()
        if file_md5 == self.file_md5:
            return
        res = await self.update(file_md5=file_md5)
        self.save_data(data)
        return res

    def save_data(self, data: bytes):
        """保存文件

        Args:
            data (bytes): 文件数据
        """
        if not self.read_path.parent.exists():
            self.read_path.parent.mkdir(parents=True, exist_ok=True)
        self.read_path.write_bytes(data)

    def read_data(self) -> bytes:
        """读取文件"""
        return self.read_path.read_bytes()

    @property
    def read_path(self):
        """文件路径"""
        return task_dir / self.file_path / self.file_md5


class ScheduledNotice(FilterModel, Model):
    id: Mapped[PrimaryKeyInteger]
    creator_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False
    )
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


# 班级或学生课表配置项
class CurriculumConfig(FilterModel, Model):
    id: Mapped[PrimaryKeyInteger]
    classes_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey(Classes.id, ondelete="CASCADE"), nullable=True, unique=True
    )
    """班级ID"""
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=True, unique=True
    )
    """用户ID"""
    current_week: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    """当前周"""
    is_notify: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    """是否开启课前通知"""
    curriculums: Mapped[List["Curriculum"]] = relationship(
        "Curriculum", lazy="selectin", back_populates="config"
    )
    """课表信息"""
    create_at: Mapped[CreateAt]
    update_at: Mapped[UpdateAt]

    user: Mapped[User | None] = relationship(lazy=False)
    classes: Mapped[Classes | None] = relationship(lazy=False)
    share_config: Mapped[list["CurriculumConfig"]] = relationship(
        "ShareCurriculumConfig", lazy="selectin"
    )


# 共享课表
class ShareCurriculumConfig(FilterModel, Model):
    id: Mapped[PrimaryKeyInteger]
    config_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(CurriculumConfig.id, ondelete="CASCADE"), nullable=False
    )
    """用户ID"""
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False
    )
    """用户ID"""
    create_at: Mapped[CreateAt]
    update_at: Mapped[UpdateAt]

    user: Mapped[User] = relationship(lazy=False)
    config: Mapped[CurriculumConfig] = relationship(
        lazy=False, back_populates="share_config"
    )


# 课表
class Curriculum(FilterModel, Model):
    id: Mapped[PrimaryKeyInteger]
    config_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(CurriculumConfig.id, ondelete="CASCADE"),
        nullable=False,
    )
    """用户ID"""
    week: Mapped[str] = mapped_column(String(255), nullable=False)
    """周几"""
    weekday: Mapped[str] = mapped_column(String(255), nullable=False)
    """星期几"""
    lesson: Mapped[str] = mapped_column(String(255), nullable=False)
    """第几节课"""
    course: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    """课程名称"""
    teacher: Mapped[str] = mapped_column(String(255), nullable=True)
    """教师"""
    classroom: Mapped[str] = mapped_column(String(255), nullable=True)
    """教室"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]
    config: Mapped["CurriculumConfig"] = relationship(
        lazy=False, back_populates="curriculums"
    )

    async def get_teacher(self) -> Teacher | None:
        return await Teacher.filter(name=self.teacher).first()

    def loads(self) -> dict[Literal["week", "weekday", "lesson"], list[int]]:
        return {
            "week": json.loads(self.week),
            "weekday": json.loads(self.weekday),
            "lesson": json.loads(self.lesson),
        }
