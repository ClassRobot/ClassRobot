from hashlib import md5
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, List, Literal, Optional

from nonebot import logger
from utils.tools import get_file_suffix
from utils.config import data_dir, task_dir
from core.storage.files import StorageManager, storage_manager
from nonebot_plugin_orm import Model, get_session
from sqlalchemy.orm import Mapped, relationship, mapped_column, selectinload
from sqlalchemy import (
    JSON,
    Text,
    String,
    Boolean,
    Integer,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    and_,
    delete as sql_delete,
    select,
    update,
)
from utils.roles import UserRole, JoinMethod, LeaveStatus, StudentRole, TeacherRole, PoliticalStatus, TeacherClassesRole

from .filters import FilterModel
from .columns import CreateAt, UpdateAt


async def _delete_fk_descendants(
    session,
    target_table,
    pk_values: dict[str, Any],
    seen: set[tuple[str, tuple[tuple[str, Any], ...]]],
) -> None:
    """递归删除依赖指定主键的子表记录。

    Args:
        session: 当前数据库会话。
        target_table: 需要清理子记录的主表。
        pk_values: 主表主键值映射。
        seen: 已访问过的 ``table + pk`` 集合，用于避免递归环。
    """

    identity = (target_table.fullname, tuple(sorted(pk_values.items())))
    if identity in seen:
        return
    seen.add(identity)

    for child_table in target_table.metadata.tables.values():
        for constraint in child_table.foreign_key_constraints:
            elements = list(constraint.elements)
            if not elements or any(element.column.table is not target_table for element in elements):
                continue

            target_columns = [element.column.name for element in elements]
            if any(column_name not in pk_values for column_name in target_columns):
                continue

            where_clause = and_(*(element.parent == pk_values[element.column.name] for element in elements))
            pk_columns = list(child_table.primary_key.columns)
            child_rows: list[dict[str, Any]] = []

            if pk_columns:
                result = await session.execute(select(*pk_columns).where(where_clause))
                child_rows = [
                    {column.name: value for column, value in zip(pk_columns, row)} for row in result.fetchall()
                ]

            for child_pk in child_rows:
                await _delete_fk_descendants(session, child_table, child_pk, seen)

            await session.execute(sql_delete(child_table).where(where_clause))


def _cleanup_storage_safely(action: Callable[[], bool], *, description: str) -> None:
    """尽力清理文件空间，失败时只记录日志。

    数据库删除已经成功提交后，文件系统属于附属清理步骤，不应因为磁盘、
    占用或权限等异常把业务删除结果重新判定为失败。

    Args:
        action: 具体的文件空间清理动作。
        description: 用于日志输出的清理对象描述。
    """

    try:
        action()
    except Exception:
        logger.exception("%s 清理失败。", description)


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
        """返回当前用户拥有的全部角色。"""
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

    async def get_organizations(self) -> List["Organization"]:
        """获取用户参与的组织。"""
        organizations = []
        if self.student:
            organizations.extend(await self.student.get_organizations())
        if self.teacher:
            organizations.extend(await self.teacher.get_organizations())
        dedup = {}
        for organization in organizations:
            dedup[organization.id] = organization
        return list(dedup.values())

    def check_password(self, password: str) -> bool:
        """检查密码

        参数:
            password (str): 密码

        返回:
            bool: 是否匹配
        """
        return self.password == password

    @classmethod
    async def login(cls, username: str, password: str) -> Optional["User"]:
        """用户登录

        参数:
            username (str): 用户名
            password (str): 用户密码

        返回:
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

        参数:
            nickname (str): 用户昵称
            username (str): 用户名
            password (str | None, optional): 用户密码. Defaults to None.
            email (str | None, optional): 用户邮箱. Defaults to None.
            avatar (str | None, optional): 用户头像. Defaults to None.

        返回:
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

        参数:
            user_id (int): 用户ID

        返回:
            Optional[User]: 用户信息
        """
        return await cls.filter(id=user_id).first()

    async def get_bind(self, platform_id: str) -> Optional["UserBind"]:
        """获取用户绑定信息

        参数:
            platform_id (str): 平台ID

        返回:
            Optional[UserBind]: 绑定信息
        """
        return await UserBind.filter(user_id=self.id, platform_id=platform_id).first()

    async def get_notices(self) -> List["ScheduledNotice"]:
        """获取用户的通知任务"""
        return await ScheduledNotice.filter(user_id=self.id).all()

    async def get_curricula_config(self) -> Optional["CurriculaConfig"]:
        """获取课表配置。"""
        return await CurriculaConfig.filter(user_id=self.id).first()

    async def get_approvals(self) -> List["StudentLeaveApproval"]:
        """获取需要审批人审批的信息"""
        return await StudentLeaveApproval.filter(approver_id=self.id).all()

    async def delete_account(self, manager: StorageManager | None = None) -> None:
        """删除用户账号，并同步清理业务数据与个人文件空间。

        说明:
            1. 先在数据库中递归删除所有依赖当前用户的业务记录。
            2. 再额外清理没有外键约束的 Agent 工作流状态表。
            3. 最后尽力删除该用户的 ``storage/users/{user_id}`` 整个空间。

        Args:
            manager: 可选的存储管理器，未提供时使用全局 ``storage_manager``。
        """

        cleanup_manager = manager or storage_manager

        async with get_session() as session:
            exists = await session.scalar(select(User.id).where(User.id == self.id))
            if exists is None:
                _cleanup_storage_safely(
                    lambda: cleanup_manager.delete_user_space(self.id),
                    description=f"用户[{self.id}]文件空间",
                )
                return

            await _delete_fk_descendants(session, User.__table__, {"id": self.id}, set())
            await session.execute(
                sql_delete(AgentWorkflowCheckpoint.__table__).where(AgentWorkflowCheckpoint.user_id == self.id)
            )
            await session.execute(sql_delete(AgentWorkflowRun.__table__).where(AgentWorkflowRun.user_id == self.id))
            await session.execute(sql_delete(User.__table__).where(User.id == self.id))
            await session.commit()

        _cleanup_storage_safely(
            lambda: cleanup_manager.delete_user_space(self.id),
            description=f"用户[{self.id}]文件空间",
        )


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

        参数:
            platform_id (str): 平台ID
            account_id (str): 平台用户ID

        返回:
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

        参数:
            platform_id (str): 平台ID
            account_id (str): 平台用户ID

        返回:
            Optional[User]: 用户信息
        """
        if bind := await cls.get_bind(platform_id, account_id):
            user = await User.get_user(bind.user_id)
            if user is not None:
                return user
            # 某些删除路径下可能遗留失效绑定，这里顺手清理，避免后续把脏关系
            # 误判成“账号仍然存在”。
            await bind.delete()

    @classmethod
    async def bind_user(
        cls,
        platform_id: str,
        account_id: str,
        user: User,
    ) -> "UserBind":
        """平台与用户之间的绑定

        参数:
            platform_id (str): 平台ID
            account_id (str): 平台用户ID
            user (User): 绑定的用户

        返回:
            UserBind: 绑定信息
        """
        orphan_user_id: int | None = None
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
                remaining_bind = await session.scalar(select(UserBind.id).where(UserBind.user_id == old_user.id))
                if remaining_bind is None:
                    orphan_user_id = old_user.id
            else:
                bind = cls(platform_id=platform_id, account_id=account_id, user=user)
                session.add(bind)
            await session.commit()
            await session.refresh(user)
            await session.refresh(bind)

        if orphan_user_id is not None and (orphan_user := await User.get_user(orphan_user_id)) is not None:
            await orphan_user.delete_account()
        return bind


class AgentWorkflowCheckpoint(FilterModel, Model):
    """保存每个用户最近一次 Agent 工作流的检查点。

    当前阶段只持久化“最新状态”，用于解决待确认工作流在进程重启后丢失的问题。
    更细粒度的历史运行记录和事件流审计可以在后续阶段继续补充。
    """

    user_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    """内部用户 ID。这里不做外键约束，避免 Agent 运行态存储和业务用户生命周期强耦合。"""
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    """最近一次写入该检查点时对应的 trace_id。"""
    kind: Mapped[str] = mapped_column(String(32), nullable=False, server_default="chat")
    """工作流类型。"""
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="planned")
    """工作流当前状态。"""
    goal: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    """用户最终目标。"""
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    """工作流摘要。"""
    playbook_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """命中的 playbook 标识。"""
    playbook_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    """命中的 playbook 名称。"""
    workflow_data: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    """完整工作流快照，使用 JSON 便于恢复 Pydantic 模型。"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]


class AgentWorkflowRun(FilterModel, Model):
    """保存每次 Agent 工作流运行的历史记录。"""

    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    """内部用户 ID。"""
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    """该次工作流运行的唯一 trace_id。"""
    source_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """如果该运行由上一条待确认工作流恢复而来，记录来源 trace_id。"""
    kind: Mapped[str] = mapped_column(String(32), nullable=False, server_default="chat")
    """工作流类型。"""
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="planned")
    """工作流当前状态。"""
    goal: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    """用户最终目标。"""
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    """工作流摘要。"""
    playbook_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """命中的 playbook 标识。"""
    playbook_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    """命中的 playbook 名称。"""
    approval_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="none")
    """审批类型。"""
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="not_required")
    """审批状态。"""
    approval_reason: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    """审批原因。"""
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    """工作流开始执行时间。"""
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    """工作流结束时间。"""
    workflow_data: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    """完整工作流快照。"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]


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
    majors: Mapped[List["Major"]] = relationship("Major", lazy="selectin", back_populates="school")
    """学校与专业一对多关系"""
    classes: Mapped[List["Classes"]] = relationship("Classes", lazy="selectin", back_populates="school")
    """学校与班级一对多关系"""
    teachers: Mapped[List["Teacher"]] = relationship("Teacher", lazy="selectin", back_populates="school")
    """学校与教师一对多关系"""
    students: Mapped[List["Student"]] = relationship("Student", lazy="selectin", back_populates="school")
    """学校与学生一对多关系"""
    organizations: Mapped[List["Organization"]] = relationship("Organization", lazy="selectin", back_populates="school")
    """学校与组织一对多关系"""


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
    majors: Mapped[List["Major"]] = relationship("Major", lazy="selectin", back_populates="college")
    """学院与专业一对多关系"""
    classes: Mapped[List["Classes"]] = relationship("Classes", lazy="selectin", back_populates="college")
    """学院与班级一对多关系"""
    teachers: Mapped[List["Teacher"]] = relationship("Teacher", lazy="selectin", back_populates="college")
    """学院与教师一对多关系"""


class Major(FilterModel, Model):
    """专业表"""

    __table_args__ = (UniqueConstraint("college_id", "name", name="uq_bot_major_college_id_name"),)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    """专业名称"""
    college_id: Mapped[int] = mapped_column(Integer, ForeignKey(College.id, ondelete="CASCADE"), nullable=False)
    """所属学院ID"""
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey(School.id, ondelete="CASCADE"), nullable=False)
    """所属学校ID"""
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    """专业描述"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    college: Mapped[College] = relationship("College", lazy="selectin", back_populates="majors")
    """专业与学院一对多关系"""
    school: Mapped[School] = relationship("School", lazy="selectin", back_populates="majors")
    """专业与学校一对多关系"""
    classes: Mapped[List["Classes"]] = relationship("Classes", lazy="selectin", back_populates="major_ref")
    """专业与班级一对多关系"""

    @classmethod
    async def get_or_create_major(cls, name: str, college: College) -> "Major":
        """按学院获取或创建专业。"""
        name = name.strip()
        if major := await cls.filter(name=name, college_id=college.id).first():
            return major
        return await cls(name=name, college_id=college.id, school_id=college.school_id).create()


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
        参数:
            creator (User): 创建者信息

        返回:
            Group: 群组信息
        """
        return await cls(name=name, creator=creator, settings=await GroupSettings().create()).create()

    async def get_binds(self) -> List["GroupBind"]:
        """获取群组绑定信息"""
        return await GroupBind.filter(group_id=self.id).all()

    async def delete_group(self, manager: StorageManager | None = None) -> None:
        """删除系统群组，并清理班级挂载、群设置与群文件空间。

        当前项目中系统群组与班级是一对一挂载关系，所以删除群组时如果仍有
        班级主体，会优先走班级侧的删除流程，避免触发
        ``bot_classes.group_id`` 的非空约束问题。

        Args:
            manager: 可选的存储管理器，未提供时使用全局 ``storage_manager``。
        """

        classes = getattr(self, "classes", None)
        if classes is None:
            classes = await Classes.filter(group_id=self.id).first()
        if classes is not None:
            await classes.delete_related_group(manager=manager)
            return

        cleanup_manager = manager or storage_manager
        settings_id = self.settings_id

        async with get_session() as session:
            await session.execute(sql_delete(GroupBind.__table__).where(GroupBind.group_id == self.id))
            await session.execute(sql_delete(Group.__table__).where(Group.id == self.id))
            if settings_id is not None:
                await session.execute(sql_delete(GroupSettings.__table__).where(GroupSettings.id == settings_id))
            await session.commit()

        _cleanup_storage_safely(
            lambda: cleanup_manager.delete_group_space(self.id),
            description=f"群组[{self.id}]文件空间",
        )


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
    async def get_bind(
        cls,
        platform_id: str,
        channel_id: str,
        guild_id: str | None = None,
    ) -> Optional["GroupBind"]:
        """获取平台群组绑定信息。"""

        condition = (GroupBind.platform_id == platform_id) & (GroupBind.channel_id == channel_id)
        if guild_id:
            condition &= GroupBind.guild_id == guild_id
        return await cls.filter(condition).first()

    @classmethod
    async def get_group(
        cls,
        platform_id: str,
        channel_id: str,
        guild_id: str | None = None,
    ) -> Optional[Group]:
        """获取平台群绑定的系统群组，并顺手清理失效绑定。"""

        if bind := await cls.get_bind(platform_id, channel_id, guild_id):
            if group := await Group.filter(id=bind.group_id).first():
                return group
            await bind.delete()

    @classmethod
    async def bind_group(
        cls, platform_name: str, platform_id: str, channel_id: str, guild_id: Optional[str], group: Group
    ) -> "GroupBind":
        """平台与群组之间的绑定

        参数:
            platform_id (str): 平台ID
            channel_id (str): 频道ID或群ID
            guild_id (Optional[str]): 群组ID
            group (Group): 绑定的群组

        返回:
            GroupBind: 绑定信息
        """
        async with get_session() as session:
            condition = (GroupBind.platform_id == platform_id) & (GroupBind.channel_id == channel_id)
            if guild_id:
                condition &= GroupBind.guild_id == guild_id

            if bind := await session.scalar(select(GroupBind).where(condition)):
                old_group_id = bind.group_id
                values = {
                    "name": platform_name or bind.name,
                    "guild_id": guild_id,
                }

                if old_group_id != group.id:
                    old_group = await session.scalar(
                        select(Group)
                        .where(Group.id == old_group_id)
                        .options(
                            selectinload(Group.classes),
                            selectinload(Group.settings),
                        )
                    )
                    if old_group is not None and getattr(old_group, "classes", None) is not None:
                        raise ValueError("当前平台群已绑定其他班级群组，不能重复绑定。")
                    values["group_id"] = group.id

                await session.execute(update(GroupBind).where(GroupBind.id == bind.id).values(**values))
                await session.commit()
                await session.refresh(bind)

                if old_group_id != group.id:
                    old_group = await session.scalar(
                        select(Group)
                        .where(Group.id == old_group_id)
                        .options(
                            selectinload(Group.classes),
                            selectinload(Group.settings),
                        )
                    )
                    remaining_bind = await session.scalar(select(GroupBind).where(GroupBind.group_id == old_group_id))
                    if old_group is not None and getattr(old_group, "classes", None) is None and remaining_bind is None:
                        await session.delete(old_group)
                        if old_group.settings is not None:
                            await session.delete(old_group.settings)
                        await session.commit()
                return bind

            bind = cls(
                platform_id=platform_id,
                channel_id=channel_id,
                name=platform_name or None,
                guild_id=guild_id,
                group_id=group.id,
            )
            session.add(bind)
            await session.commit()
            await session.refresh(bind)
            return bind


class Files(FilterModel, Model):
    """表示文件模型。"""

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
        """检查文件是否重复

        参数:
            file_md5 (str): 文件MD5 值。

        返回:
            bool: 表示是否成功。
        """
        return await cls.filter(file_md5=file_md5).exists()

    @classmethod
    async def get_file(cls, file_md5: str) -> Optional["Files"]:
        """获取文件信息

        参数:
            file_md5 (str): 文件MD5 值。

        返回:
            Optional['Files']: 返回处理结果。
        """
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

        参数:
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

        参数:
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
        """返回当前文件的本地存储路径。"""
        return data_dir / self.file_path / self.file_name

    @property
    def file_name(self) -> str:
        """返回当前文件的显示名称。"""
        return f"{self.name}.{self.suffix.lstrip('.')}" if self.suffix else self.name

    def read_bytes(self) -> bytes:
        """读取字节数据。"""
        return self.path.read_bytes()

    def read_text(self, encoding: str | None = None) -> str:
        """读取文本内容。

        参数:
            encoding (str | None): encoding。

        返回:
            str: 返回字符串结果。
        """
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
    school: Mapped[Optional[School]] = relationship("School", lazy="selectin", back_populates="teachers")
    """教师与学校多对一关系"""
    college: Mapped[Optional[College]] = relationship("College", lazy="selectin", back_populates="teachers")
    """教师与学院多对一关系"""

    classes: Mapped[List["Classes"]] = relationship(
        "Classes",
        secondary="bot_teacher_classes",
        lazy="selectin",
        back_populates="teacher",
    )
    """教师与班级多对多关系"""
    organization_memberships: Mapped[List["OrganizationMember"]] = relationship(
        "OrganizationMember",
        lazy="selectin",
        back_populates="teacher",
    )
    """教师与组织成员关系一对多"""

    @classmethod
    async def create_teacher(
        cls,
        name: str,
        user: User,
        school_id: int | None = None,
        college_id: int | None = None,
    ) -> "Teacher":
        """创建教师

        参数:
            name (str): 教师姓名
            user (User): 用户信息

        返回:
            Teacher: 教师信息
        """
        assert user.student is None, "teacher role is not student"
        teacher = await cls(name=name, user=user, school_id=school_id, college_id=college_id).create()
        await user.update(role=UserRole.teacher)
        return teacher

    @classmethod
    async def get_teacher(cls, user: User) -> Optional["Teacher"]:
        """获取教师信息

        参数:
            user (User): 用户信息

        返回:
            Optional[Teacher]: 教师信息
        """
        return await cls.filter(user_id=user.id).first()

    @classmethod
    async def get_or_create_teacher(cls, name: str, user: User) -> "Teacher":
        """获取或创建教师信息

        参数:
            user (User): 用户信息
            name (str): 教师姓名

        返回:
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

        参数:
            platform_id (str | int): 平台id
                当为int时为classes.id
                当为str时判断channel_id
                    None时表示classes.name搜索
            channel_id (str | None, optional): 群或子频道id. Defaults to None.
            guild_id (str | None, optional): 群组id. Defaults to None.

        返回:
            Optional["Classes"]: 班级信息
        """
        condition = TeacherClasses.teacher_id == self.id
        if isinstance(platform_id, int):
            condition &= TeacherClasses.classes_id == platform_id
        else:
            if channel_id is None:
                condition &= Classes.name == platform_id
                return await Classes.select.join(TeacherClasses).where(condition).first()
            condition &= GroupBind.platform_id == platform_id
            if channel_id:
                condition &= GroupBind.channel_id == channel_id
            if guild_id:
                condition &= GroupBind.guild_id == guild_id
        return await Classes.select.join(TeacherClasses).join(Group).join(GroupBind).where(condition).first()

    async def bind_classes(self, classes: "Classes"):
        """绑定班级

        参数:
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

    async def get_organizations(self) -> List["Organization"]:
        """获取教师参与的组织。"""
        memberships = await OrganizationMember.filter(teacher_id=self.id).all()
        return [membership.organization for membership in memberships]


class Classes(FilterModel, Model):
    """班级表

    - 班级与教师是多对多关系
    - 班级与群组是一对一关系
    """

    name: Mapped[str] = mapped_column(__name_pos=String(64), nullable=False)
    """班级名称"""
    major: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """兼容旧结构保留的专业名称"""
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Group.id, ondelete="CASCADE"), nullable=False, unique=True
    )
    """群组ID"""
    school_id: Mapped[int | None] = mapped_column(Integer, ForeignKey(School.id, ondelete="CASCADE"), nullable=True)
    """学校ID"""
    college_id: Mapped[int | None] = mapped_column(Integer, ForeignKey(College.id, ondelete="CASCADE"), nullable=True)
    """学院ID"""
    major_id: Mapped[int | None] = mapped_column(Integer, ForeignKey(Major.id, ondelete="SET NULL"), nullable=True)
    """专业ID"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    group: Mapped[Group] = relationship(lazy=False, back_populates="classes")
    """班级与群组一对一关系"""
    school: Mapped[Optional[School]] = relationship("School", lazy="selectin", back_populates="classes")
    """班级与学校多对一关系"""
    college: Mapped[Optional[College]] = relationship("College", lazy="selectin", back_populates="classes")
    """班级与学院多对一关系"""
    major_ref: Mapped[Optional[Major]] = relationship("Major", lazy="selectin", back_populates="classes")
    """班级与专业多对一关系"""
    teacher: Mapped[List[Teacher]] = relationship(
        "Teacher",
        secondary="bot_teacher_classes",
        lazy="selectin",
        back_populates="classes",
    )
    """班级与教师多对多关系"""
    students: Mapped[List["Student"]] = relationship("Student", lazy="selectin", back_populates="classes")
    """班级与学生一对多关系"""

    async def get_task(self, task_id: int | str) -> Optional["Tasks"]:
        """获取任务信息

        参数:
            task_id (int | str): 任务ID或任务名称

        返回:
            Optional["Tasks"]: 任务信息
        """

        if isinstance(task_id, str):
            return await Tasks.filter(classes=self, name=task_id).first()
        return await Tasks.filter(classes=self, id=task_id).first()

    async def get_tasks(self) -> List["Tasks"]:
        """获取任务。"""
        return await Tasks.filter(classes=self).all()

    async def get_join_requests(self) -> List["ClassesJoinRequest"]:
        """获取入班申请列表。"""
        return await ClassesJoinRequest.filter(classes_id=self.id).all()

    async def get_students(self) -> List["Student"]:
        """获取学生。"""
        return await Student.filter(classes_id=self.id).all()

    async def student_count(self) -> int:
        """获取班级学生数量"""
        return await Student.filter(classes_id=self.id).count()

    async def delete_related_group(self, manager: StorageManager | None = None) -> None:
        """删除班级，并清理其挂载群组、群设置与聊天/文件空间。

        删除顺序必须保持为“班级 -> 群组 -> 群设置”，否则某些 ORM 删除路径
        会先尝试把 ``bot_classes.group_id`` 置空，进而触发数据库非空约束错误。

        Args:
            manager: 可选的存储管理器，未提供时使用全局 ``storage_manager``。
        """

        cleanup_manager = manager or storage_manager
        group_id = self.group_id
        settings_id = None

        group = getattr(self, "group", None)
        if group is None and group_id is not None:
            group = await Group.filter(id=group_id).first()
        if group is not None:
            settings_id = group.settings_id

        async with get_session() as session:
            await session.execute(sql_delete(Classes.__table__).where(Classes.id == self.id))
            if group_id is not None:
                await session.execute(sql_delete(GroupBind.__table__).where(GroupBind.group_id == group_id))
                await session.execute(sql_delete(Group.__table__).where(Group.id == group_id))
            if settings_id is not None:
                await session.execute(sql_delete(GroupSettings.__table__).where(GroupSettings.id == settings_id))
            await session.commit()

        if group_id is not None:
            _cleanup_storage_safely(
                lambda: cleanup_manager.delete_group_space(group_id),
                description=f"群组[{group_id}]文件空间",
            )
        _cleanup_storage_safely(
            lambda: cleanup_manager.delete_class_space(self.id),
            description=f"班级[{self.id}]文件空间",
        )

    async def user_join_classes(self, user: User):
        """用户加入班级

        参数:
            user (User): 用户信息
        """
        if user.student is None:  # 创建学生
            await Student.create_student(user.nickname, self, user)
        else:  # 如果已经是学生则更新班级
            await user.student.update_classes(self)

    async def apply_join_classes(self, user: User, describe: str | None = None):
        """申请加入班级

        参数:
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

        参数:
            platform_id (str): 平台ID 或 classes.id
            channel_id (str): 频道ID
            guild_id (str | None, optional): 群组ID. Defaults to None.

        返回:
            Optional[Classes]: 班级信息
        """
        if isinstance(platform_id, int):
            return await cls.filter(id=platform_id).first()

        assert channel_id is not None, "channel_id is None"

        condition = (GroupBind.platform_id == platform_id) & (GroupBind.channel_id == channel_id)
        if guild_id:
            condition &= GroupBind.guild_id == guild_id
        if group_bind := await GroupBind.filter(condition).first():
            return getattr(group_bind.group, "classes", None)

    @classmethod
    async def create_classes(
        cls,
        name: str,
        platform_name: str,
        platform_id: str,
        channel_id: str,
        guild_id: str | None,
        user: User,
        school_id: int | None = None,
        college_id: int | None = None,
        major: str | None = None,
        major_id: int | None = None,
    ) -> "Classes":
        """创建班级

        先创建组然后将组与平台绑定，最后创建班级

        参数:
            name (str): 班级名称
            platform_id (str): 平台ID
            channel_id (str): 频道ID
            guild_id (str | None): 群组ID
            user (User): 用户信息

        返回:
            Classes: 班级信息
        """
        group = await GroupBind.get_group(platform_id, channel_id, guild_id)
        if group is None:
            group = await Group.create_group(name, user)  # 创建群组
        else:
            group = await group.update(name=name, creator_id=user.id)
        await GroupBind.bind_group(platform_name, platform_id, channel_id, guild_id, group)  # 绑定群组
        return await cls(
            name=name,
            group=group,
            school_id=school_id,
            college_id=college_id,
            major=major,
            major_id=major_id,
        ).create()

    async def bind_teacher(self, teacher: Teacher, role: TeacherRole | None = None):
        """绑定教师

        参数:
            teacher (Teacher): 教师信息
        """
        await TeacherClasses.association(teacher, self)

    async def update_teacher_role(self, teacher: Teacher, role: TeacherClassesRole):
        """更新教师角色

        参数:
            teacher (Teacher): 教师信息
            role (TeacherRole): 教师角色
        """

        await TeacherClasses.filter(teacher_id=teacher.id, classes_id=self.id).update(role=role)

    async def get_leaves(self) -> list["StudentLeave"]:
        """获取请假。"""
        return await StudentLeave.filter(classes_id=self.id).all()


class ClassesJoinRequest(FilterModel, Model):
    """表示班级joinrequest模型。"""

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

        参数:
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

    classes: Mapped[Classes] = relationship(lazy=False, back_populates="students")
    """学生与班级一对一关系"""
    school: Mapped[Optional[School]] = relationship("School", lazy="selectin", back_populates="students")
    """学生与学校多对一关系"""
    user: Mapped[User] = relationship(lazy=False, back_populates="student")
    """学生与用户一对一关系"""
    extra: Mapped["StudentExtra"] = relationship(lazy=False, back_populates="student")
    """学生与额外信息一对一关系"""
    organization_memberships: Mapped[List["OrganizationMember"]] = relationship(
        "OrganizationMember",
        lazy="selectin",
        back_populates="student",
    )
    """学生与组织成员关系一对多"""

    @classmethod
    async def create_student(
        cls, name: str, classes: Classes, user: User, school_id: int | None = None, **kwargs
    ) -> "Student":
        """创建学生

        参数:
            name (str): 学生姓名
            classes (Classes): 班级信息
            user (User): 用户信息
            school_id (int | None): 学校ID
            **kw参数: 额外信息

        返回:
            Student: 学生信息
        """

        resolved_school_id = school_id if school_id is not None else classes.school_id
        student = await cls(name=name, classes=classes, user=user, school_id=resolved_school_id).create()
        await StudentExtra(student=student).create()  # 创建学生额外信息
        if user.teacher is None:
            await user.update(role=UserRole.student)
        return student

    async def update_classes(self, classes: Classes):
        """更新班级信息

        参数:
            classes (Classes): 班级信息
        """
        await self.update(
            classes=classes,
            role=StudentRole.student,
        )

    async def get_classmates(self) -> list["Student"]:
        """获取同班同学列表。"""
        return await Student.filter(classes_id=self.classes_id).all()

    async def get_leaves(self) -> List["StudentLeave"]:
        """获取请假。"""
        return await StudentLeave.filter(student_id=self.id).all()

    async def get_organizations(self) -> List["Organization"]:
        """获取学生参与的组织。"""
        memberships = await OrganizationMember.filter(student_id=self.id).all()
        return [membership.organization for membership in memberships]


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
        """更新学生额外信息

        参数:
            kwargs (**Any): 可变关键字参数。
        """
        await self.update(**kwargs)


class Organization(FilterModel, Model):
    """组织表

    组织是学校域下独立于班级的成员型组织。
    """

    __table_args__ = (
        UniqueConstraint("school_id", "organization_type", "name", name="uq_bot_organization_school_type_name"),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    """组织名称"""
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey(School.id, ondelete="CASCADE"), nullable=False)
    """所属学校ID"""
    organization_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="general")
    """组织类型"""
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    """组织描述"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    school: Mapped[School] = relationship("School", lazy="selectin", back_populates="organizations")
    """组织与学校多对一关系"""
    members: Mapped[List["OrganizationMember"]] = relationship(
        "OrganizationMember",
        lazy="selectin",
        back_populates="organization",
    )
    """组织与成员关系一对多"""

    @classmethod
    async def get_or_create_organization(
        cls,
        name: str,
        school: School,
        organization_type: str = "general",
        description: str | None = None,
    ) -> "Organization":
        """获取或创建组织。"""
        if organization := await cls.filter(
            name=name.strip(),
            school_id=school.id,
            organization_type=organization_type,
        ).first():
            return organization
        return await cls(
            name=name.strip(),
            school_id=school.id,
            organization_type=organization_type,
            description=description,
        ).create()

    async def get_students(self) -> List["Student"]:
        """获取组织内学生成员。"""
        members = await OrganizationMember.filter(organization_id=self.id).all()
        return [member.student for member in members if member.student is not None]

    async def get_teachers(self) -> List["Teacher"]:
        """获取组织内教师成员。"""
        members = await OrganizationMember.filter(organization_id=self.id).all()
        return [member.teacher for member in members if member.teacher is not None]

    async def add_student(self, student: "Student", position: str | None = None) -> "OrganizationMember":
        """为组织添加学生成员。"""
        if member := await OrganizationMember.filter(organization_id=self.id, student_id=student.id).first():
            if position and member.position != position:
                member = await member.update(position=position)
            return member
        return await OrganizationMember(
            organization_id=self.id,
            student_id=student.id,
            position=position,
        ).create()

    async def add_teacher(self, teacher: "Teacher", position: str | None = None) -> "OrganizationMember":
        """为组织添加教师成员。"""
        if member := await OrganizationMember.filter(organization_id=self.id, teacher_id=teacher.id).first():
            if position and member.position != position:
                member = await member.update(position=position)
            return member
        return await OrganizationMember(
            organization_id=self.id,
            teacher_id=teacher.id,
            position=position,
        ).create()


class OrganizationMember(FilterModel, Model):
    """组织成员关系表

    成员主体只能是学生或教师，不能是普通用户。
    """

    __table_args__ = (
        CheckConstraint(
            "(student_id IS NOT NULL AND teacher_id IS NULL) OR " "(student_id IS NULL AND teacher_id IS NOT NULL)",
            name="ck_bot_organization_member_subject",
        ),
        UniqueConstraint("organization_id", "student_id", name="uq_bot_organization_member_student"),
        UniqueConstraint("organization_id", "teacher_id", name="uq_bot_organization_member_teacher"),
    )

    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Organization.id, ondelete="CASCADE"), nullable=False
    )
    """组织ID"""
    student_id: Mapped[int | None] = mapped_column(Integer, ForeignKey(Student.id, ondelete="CASCADE"), nullable=True)
    """学生成员ID"""
    teacher_id: Mapped[int | None] = mapped_column(Integer, ForeignKey(Teacher.id, ondelete="CASCADE"), nullable=True)
    """教师成员ID"""
    position: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """组织内岗位"""
    created_at: Mapped[CreateAt]
    updated_at: Mapped[UpdateAt]

    organization: Mapped[Organization] = relationship("Organization", lazy="selectin", back_populates="members")
    """成员关系与组织多对一关系"""
    student: Mapped[Optional[Student]] = relationship(
        "Student",
        lazy="selectin",
        back_populates="organization_memberships",
    )
    """成员关系与学生多对一关系"""
    teacher: Mapped[Optional[Teacher]] = relationship(
        "Teacher",
        lazy="selectin",
        back_populates="organization_memberships",
    )
    """成员关系与教师多对一关系"""


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

        参数:
            name (str): 任务名称
            classes (Classes): 班级信息
            creator (User): 创建者信息
            creator_role (Literal["teacher", "student"]): 创建者角色

        返回:
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
        """检查提交记录。

        参数:
            student (Student): 当前学生对象。

        返回:
            bool: 表示是否成功。
        """
        return await TaskCommits.filter(task_id=self.id, student_id=student.id).exists()

    async def commit(self, student: Student, file_data: bytes) -> "TaskCommits":
        """处理提交记录相关逻辑。

        参数:
            student (Student): 当前学生对象。
            file_data (bytes): 文件数据对象。

        返回:
            'TaskCommits': 返回处理结果。
        """
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
        """获取提交记录。

        参数:
            student (Student): 当前学生对象。

        返回:
            Optional['TaskCommits']: 返回处理结果。
        """
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
        """更新文件

        参数:
            file (Files | bytes): 文件对象。
        """
        await self.file.delete()  # 删除旧的文件
        if isinstance(file, bytes):  # 如果是bytes则解析文件
            file = await Files.parse_data(file, task_dir)
        await self.filter(id=self.id).update(file=file)  # 更新文件信息


class ScheduledNotice(FilterModel, Model):
    """表示scheduled通知模型。"""

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
    """描述用户课表的基础配置。"""

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
        """处理query相关逻辑。

        参数:
            name (str): 名称。
        """
        return await cls.filter(name=name, user_id=None).first()

    async def get_curricula(self) -> list["Curricula"]:
        """获取配置项中的所有课表"""
        return await Curricula.filter(config_id=self.id).all()


# 共享课表
class ShareCurriculaConfig(FilterModel, Model):
    """描述课表共享功能的配置。"""

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
    """表示课表模型。"""

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
        """获取教师。"""
        return await Teacher.filter(name=self.teacher).first()


class LeaveConfig(FilterModel, Model):
    """描述请假流程相关的配置。"""

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
        """对用户进行排序。"""
        users = []
        for uid in self.order:
            if user := await User.filter(id=uid).first():
                users.append(user)
            else:
                raise ValueError("用户不存在")
        return users


class StudentLeave(FilterModel, Model):
    """表示学生请假模型。"""

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
