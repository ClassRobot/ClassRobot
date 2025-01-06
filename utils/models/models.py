from typing import List, Optional, Tuple
from nonebot_plugin_orm import Model, get_scoped_session
from sqlalchemy.sql import and_
from sqlalchemy import (
    ForeignKey,
    Integer,
    ScalarResult,
    String,
    select,
    update,
    delete,
    insert,
    Select,
    Update,
    Delete,
    Insert,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .columns import CreateAt, UpdateAt, PrimaryKeyInteger


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
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    teacher: Mapped["Teacher"] = relationship(
        "Teacher", lazy="selectin", back_populates="user"
    )
    binds: Mapped[List["Bind"]] = relationship(
        "Bind", lazy="selectin", back_populates="user"
    )
    """一个用户可以绑定多个表"""
    groups: Mapped[List["Group"]] = relationship(
        "Group", lazy="selectin", back_populates="creator"
    )
    """一个用户可以创建多个群组"""

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


class GroupBind(Model):
    """群组绑定表

    - 群组与平台是一对多关系
    """

    __tablename__ = "group_bind"
    id: Mapped[PrimaryKeyInteger]
    platform_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    channel_id: Mapped[str] = mapped_column(
        String(64), index=True, nullable=True, default=None
    )
    """频道ID"""
    guild_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    """平台的群组ID"""
    group_id = mapped_column(
        Integer, ForeignKey(Group.id, ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    group: Mapped[Group] = relationship(
        "Group", lazy=False, back_populates="group_binds"
    )
    """群组信息,一个平台绑定一个群组"""


class Teacher(Model):
    """教师表

    - 教师与用户是一对一关系
    - 教师与班级是多对多关系
    """

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


class Classes(Model):
    """班级表

    - 班级与教师是多对多关系
    - 班级与群组是一对一关系
    """

    id: Mapped[PrimaryKeyInteger]
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    """班级名称"""
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("group.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    """群组ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    group: Mapped[Group] = relationship(lazy=False, back_populates="classes")
