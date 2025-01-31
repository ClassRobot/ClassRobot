from typing import List, Literal, Optional

from sqlalchemy.sql import and_
from nonebot_plugin_orm import Model, get_scoped_session
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy import String, Integer, ForeignKey, select, update

from .columns import CreateAt, UpdateAt, PrimaryKeyInteger
from .enums import UserRole, JoinMethod, StudentRole, TeacherRole, PoliticalStatus


class User(Model):
    """用户表"""

    __tablename__ = "user"
    id: Mapped[PrimaryKeyInteger]
    nickname: Mapped[str] = mapped_column(String(255), nullable=False)
    """用户昵称"""
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    """用户名"""
    password: Mapped[str] = mapped_column(String(255), nullable=True)
    """用户密码"""
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    """邮箱"""
    avatar: Mapped[str] = mapped_column(String(255), nullable=True)
    """头像"""
    phone: Mapped[str] = mapped_column(String(11), nullable=True)
    """手机号"""
    role: Mapped[UserRole] = mapped_column(
        String(32), nullable=False, server_default=UserRole.user
    )
    """用户角色"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    teacher: Mapped["Teacher"] = relationship(
        "Teacher", lazy="selectin", back_populates="user"
    )
    student: Mapped["Student"] = relationship(
        "Student", lazy="selectin", back_populates="user"
    )
    """一个用户绑定一个学生"""
    binds: Mapped[List["Bind"]] = relationship(
        "Bind", lazy="selectin", back_populates="user"
    )
    """一个用户可以绑定多个表"""
    groups: Mapped[List["Group"]] = relationship(
        "Group", lazy="selectin", back_populates="creator"
    )
    """一个用户可以创建多个群组"""

    join_requests: Mapped[List["ClassesJoinRequest"]] = relationship(
        "ClassesJoinRequest", lazy="selectin", back_populates="user"
    )
    """用户与加入请求一对多关系"""

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
        session = get_scoped_session()
        if user := await session.scalar(select(cls).where(cls.username == username)):
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
        user = cls(
            nickname=nickname,
            username=username,
            password=password,
            email=email,
            avatar=avatar,
        )
        session = get_scoped_session()
        session.add(user)
        await session.commit()
        return user

    @classmethod
    async def get_user(cls, user_id: int) -> Optional["User"]:
        """获取用户信息

        Args:
            user_id (int): 用户ID

        Returns:
            Optional[User]: 用户信息
        """
        session = get_scoped_session()
        return await session.scalar(select(cls).where(cls.id == user_id))


class Bind(Model):
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
        session = get_scoped_session()
        return await session.scalar(
            select(Bind).where(
                and_(Bind.platform_id == platform_id, Bind.account_id == account_id)
            )
        )

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
        session = get_scoped_session()
        where_and = and_(Bind.platform_id == platform_id, Bind.account_id == account_id)
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
        session = get_scoped_session()
        await session.delete(self)
        await session.commit()


class Group(Model):
    """群组表"""

    __tablename__ = "group"
    id: Mapped[PrimaryKeyInteger]
    creator_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(User.id), nullable=False
    )
    """创建者ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    creator: Mapped[User] = relationship(lazy=False, back_populates="groups")
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
        group = cls(creator=creator)
        session = get_scoped_session()
        session.add(group)
        await session.commit()
        await session.refresh(group)
        return group


class GroupBind(Model):
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
        "Group", lazy=False, back_populates="group_binds"
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
        session = get_scoped_session()
        group_bind = cls(
            platform_id=platform_id,
            channel_id=channel_id,
            guild_id=guild_id,
            group_id=group.id,
        )
        session.add(group_bind)
        await session.commit()
        await session.refresh(group_bind)
        return group_bind


class Teacher(Model):
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
        teacher = cls(name=name, user=user)
        session = get_scoped_session()
        session.add(teacher)
        await session.commit()
        await session.refresh(user)
        return teacher

    @classmethod
    async def get_teacher(cls, user: User) -> Optional["Teacher"]:
        """获取教师信息

        Args:
            user (User): 用户信息

        Returns:
            Optional[Teacher]: 教师信息
        """
        session = get_scoped_session()
        return await session.scalar(select(cls).where(cls.user_id == user.id))

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
        session = get_scoped_session()
        condition = [TeacherClasses.teacher_id == self.id]
        if isinstance(platform_id, int):
            condition.append(TeacherClasses.classes_id == platform_id)
        else:
            condition.append(Classes.name == platform_id)
            if channel_id:
                condition.append(GroupBind.channel_id == channel_id)
            if guild_id:
                condition.append(GroupBind.guild_id == guild_id)
        return await session.scalar(
            select(Classes)
            .join(TeacherClasses)
            .join(Group)
            .join(GroupBind)
            .where(and_(*condition))
        )

    async def bind_classes(self, classes: "Classes"):
        """绑定班级

        Args:
            classes (Classes): 班级信息
        """
        session = get_scoped_session()
        self.classes.append(classes)
        await session.commit()
        await session.refresh(self)


class Classes(Model):
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

    group: Mapped[Group] = relationship(lazy=False, back_populates="classes")
    """班级与群组一对一关系"""
    teacher: Mapped[List[Teacher]] = relationship(
        "Teacher",
        secondary="teacher_classes",
        lazy="selectin",
        back_populates="classes",
    )
    """班级与教师多对多关系"""
    students: Mapped[List["Student"]] = relationship(
        "Student", lazy="selectin", back_populates="classes"
    )
    """班级与学生一对多关系"""
    join_requests: Mapped[List["ClassesJoinRequest"]] = relationship(
        "ClassesJoinRequest", lazy="selectin", back_populates="classes"
    )
    """班级与加入请求一对多关系"""

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
        session = get_scoped_session()
        classes_join_request = ClassesJoinRequest(
            classes_id=self.id,
            user_id=user.id,
            join_method=JoinMethod.apply,
            describe=describe,
        )
        session.add(classes_join_request)
        await session.commit()
        await session.refresh(classes_join_request)

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
        session = get_scoped_session()
        if isinstance(platform_id, int):
            return await session.scalar(select(cls).where(cls.id == platform_id))

        assert channel_id is not None, "channel_id is None"

        condition = [
            GroupBind.platform_id == platform_id,
            GroupBind.channel_id == channel_id,
        ]
        if guild_id:
            condition.append(GroupBind.guild_id == guild_id)
        if group_bind := await session.scalar(
            select(GroupBind).where(and_(*condition))
        ):
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
        session = get_scoped_session()
        classes = cls(name=name, group=group)  # 创建班级
        session.add(classes)
        await session.commit()
        await session.refresh(classes)
        return classes

    async def bind_teacher(self, teacher: Teacher, role: TeacherRole | None = None):
        """绑定教师

        Args:
            teacher (Teacher): 教师信息
        """
        session = get_scoped_session()
        self.teacher.append(teacher)
        await session.commit()
        await session.refresh(self)

    async def update_teacher_role(self, teacher: Teacher, role: TeacherRole):
        """更新教师角色

        Args:
            teacher (Teacher): 教师信息
            role (TeacherRole): 教师角色
        """
        session = get_scoped_session()
        if teacher_classes := await session.scalar(
            select(TeacherClasses).where(
                and_(
                    TeacherClasses.teacher_id == teacher.id,
                    TeacherClasses.classes_id == self.id,
                )
            )
        ):
            teacher_classes.role = role
            await session.commit()
            await session.refresh(teacher_classes)
            await session.refresh(teacher)
            await session.refresh(self)


class ClassesJoinRequest(Model):
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

    classes: Mapped[Classes] = relationship(lazy=False, back_populates="join_requests")
    user: Mapped[User] = relationship(lazy=False, back_populates="join_requests")


# 教师与班级多对多关系
class TeacherClasses(Model):
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
        session = get_scoped_session()
        teacher_classes = cls(teacher_id=teacher.id, classes_id=classes.id)
        session.add(teacher_classes)
        await session.commit()
        await session.refresh(teacher_classes)


class Student(Model):
    """学生表"""

    __tablename__ = "student"
    id: Mapped[PrimaryKeyInteger]
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    """学生姓名"""
    classes_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Classes.id, ondelete="CASCADE"), nullable=False
    )
    user_id = mapped_column(
        Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False
    )
    role: Mapped[StudentRole] = mapped_column(
        String(32), nullable=False, server_default=StudentRole.student
    )
    """班级ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    classes: Mapped[Classes] = relationship(lazy=False, back_populates="students")
    """学生与班级一对多关系"""
    user: Mapped[User] = relationship(lazy=False, back_populates="student")
    """学生与用户一对一关系"""
    extra: Mapped["StudentExtra"] = relationship(
        lazy=False, back_populates="student", uselist=False
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
        student = cls(name=name, classes=classes, user=user)
        session = get_scoped_session()
        session.add(student)
        await session.commit()
        await session.refresh(student)
        return student

    async def update_classes(self, classes: Classes):
        """更新班级信息

        Args:
            classes (Classes): 班级信息
        """
        session = get_scoped_session()
        self.classes = classes
        self.role = StudentRole.student
        await session.commit()
        await session.refresh(self)


class StudentExtra(Model):
    """学生额外信息表"""

    __tablename__ = "student_extra"
    id: Mapped[PrimaryKeyInteger]
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Student.id, ondelete="CASCADE"), nullable=False
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

    student: Mapped[Student] = relationship(lazy=False, back_populates="extra")


class Tasks(Model):
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

    commits: Mapped[List["TaskCommits"]] = relationship(
        "TaskCommits", lazy="selectin", back_populates="task"
    )
    """任务与提交文件一对多关系"""

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
        task = cls(
            name=name, classes=classes, creator=creator, creator_role=creator_role
        )
        session = get_scoped_session()
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task


class TaskCommits(Model):
    """任务文件表"""

    __tablename__ = "task_files"
    id: Mapped[PrimaryKeyInteger]
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Tasks.id, ondelete="CASCADE"), nullable=False
    )
    """任务ID"""
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    """文件ID"""
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Student.id, ondelete="CASCADE"), nullable=False
    )
    """学生ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    task: Mapped[Tasks] = relationship(lazy=False, back_populates="commits")
    """任务信息"""

    def save_data(self, data: bytes):
        """保存文件

        Args:
            data (bytes): 文件数据
        """
        from src.plugins.tasks.config import task_dir

        self.read_path.write_bytes(data)

    def read_data(self) -> bytes:
        """读取文件"""
        return self.read_path.read_bytes()

    @property
    def read_path(self):
        """文件路径"""
        from src.plugins.tasks.config import task_dir

        return task_dir / self.file_path
