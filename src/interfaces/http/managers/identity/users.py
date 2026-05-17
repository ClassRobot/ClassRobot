from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from nonebot_plugin_orm import get_session

from utils.models import User, Student, Teacher, UserBind


class UserMutationError(RuntimeError):
    """用户修改失败时抛出的结构化异常。"""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        hint: str | None = None,
        detail: str | None = None,
        blockers: list[dict[str, Any]] | None = None,
    ) -> None:
        """初始化用户修改异常。

        Args:
            code: 机器可读的错误码。
            message: 面向前端展示的错误消息。
            hint: 可选的修复提示。
            detail: 可选的底层错误详情。
            blockers: 阻止本次操作的业务关联项列表。
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.detail = detail
        self.blockers = blockers or []

    def to_payload(self) -> dict[str, Any]:
        """把异常转换成适合 HTTP 返回的结构化 payload。

        Returns:
            dict[str, Any]: 包含错误码、消息和阻塞项的错误结果。
        """
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.hint:
            payload["hint"] = self.hint
        if self.detail:
            payload["detail"] = self.detail
        if self.blockers:
            payload["blockers"] = self.blockers
        return payload


def _user_load_options():
    """返回用户中心查询共用的预加载关系配置。

    Returns:
        tuple[Any, ...]: SQLAlchemy ``selectinload`` 选项集合。
    """
    return (
        selectinload(User.binds),
        selectinload(User.teacher).selectinload(Teacher.school),
        selectinload(User.teacher).selectinload(Teacher.college),
        selectinload(User.teacher).selectinload(Teacher.classes),
        selectinload(User.student).selectinload(Student.school),
        selectinload(User.student).selectinload(Student.classes),
        selectinload(User.student).selectinload(Student.extra),
    )


def _roles(user: User) -> list[str]:
    """提取用户角色列表。

    Args:
        user: 用户模型实例。

    Returns:
        list[str]: 字符串形式的角色名称列表。
    """
    return [str(role) for role in user.roles]


def _user_summary(user: User) -> dict[str, Any]:
    """构造用户列表页与详情页共用的摘要字段。

    Args:
        user: 用户模型实例。

    Returns:
        dict[str, Any]: 用户概要信息。
    """
    return {
        "id": user.id,
        "nickname": user.nickname,
        "username": user.username,
        "email": user.email,
        "avatar": user.avatar,
        "phone": user.phone,
        "roles": _roles(user),
        "is_admin": user.is_admin,
        "bind_count": len(user.binds),
        "has_teacher": user.teacher is not None,
        "has_student": user.student is not None,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _bind_payload(bind: UserBind) -> dict[str, Any]:
    """序列化用户平台绑定记录。

    Args:
        bind: 用户绑定模型实例。

    Returns:
        dict[str, Any]: 平台绑定展示字段。
    """
    return {
        "id": bind.id,
        "name": bind.name,
        "platform_id": bind.platform_id,
        "account_id": bind.account_id,
        "created_at": bind.created_at,
        "updated_at": bind.updated_at,
    }


async def list_users(
    *,
    q: str | None = None,
    role: str | None = None,
    is_admin: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """列出用户中心表格数据。

    Args:
        q: 可选的昵称、用户名、邮箱或手机号搜索词。
        role: 可选的角色过滤条件。
        is_admin: 可选的管理员状态过滤条件。
        page: 页码，从 1 开始。
        page_size: 每页条目数。

    Returns:
        dict[str, Any]: 标准分页结果。
    """
    async with get_session() as session:
        result = await session.scalars(select(User).options(*_user_load_options()))
    users = list(result)
    if q:
        q_lower = q.lower()
        users = [
            user
            for user in users
            if q_lower in user.nickname.lower()
            or q_lower in user.username.lower()
            or q_lower in (user.email or "").lower()
            or q_lower in (user.phone or "").lower()
        ]
    if role:
        users = [user for user in users if role in _roles(user)]
    if is_admin is not None:
        users = [user for user in users if user.is_admin == is_admin]

    users.sort(key=lambda item: item.id, reverse=True)
    total = len(users)
    start = max(page - 1, 0) * page_size
    end = start + page_size
    return {
        "items": [_user_summary(user) for user in users[start:end]],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


async def get_user_detail(user_id: int) -> dict[str, Any]:
    """读取单个用户详情。

    Args:
        user_id: 用户 ID。

    Returns:
        dict[str, Any]: 用户详情，包括教师、学生和绑定信息。

    Raises:
        KeyError: 当用户不存在时抛出。
    """
    async with get_session() as session:
        user = await session.scalar(select(User).where(User.id == user_id).options(*_user_load_options()))
    if user is None:
        raise KeyError(str(user_id))

    payload = _user_summary(user)
    payload.update(
        {
            "avatar": user.avatar,
            "gender": user.gender,
            "birthday": user.birthday,
            "binds": [_bind_payload(bind) for bind in user.binds],
            "teacher": None,
            "student": None,
        }
    )

    if user.teacher is not None:
        payload["teacher"] = {
            "id": user.teacher.id,
            "name": user.teacher.name,
            "role": user.teacher.role,
            "school_id": user.teacher.school_id,
            "school_name": user.teacher.school.name if user.teacher.school else None,
            "college_id": user.teacher.college_id,
            "college_name": user.teacher.college.name if user.teacher.college else None,
            "classes": [{"id": item.id, "name": item.name} for item in user.teacher.classes],
            "created_at": user.teacher.created_at,
            "updated_at": user.teacher.updated_at,
        }

    if user.student is not None:
        extra = user.student.extra
        payload["student"] = {
            "id": user.student.id,
            "name": user.student.name,
            "role": user.student.role,
            "school_id": user.student.school_id,
            "school_name": user.student.school.name if user.student.school else None,
            "classes_id": user.student.classes_id,
            "classes_name": user.student.classes.name,
            "created_at": user.student.created_at,
            "updated_at": user.student.updated_at,
            "extra": {
                "student_code": extra.student_code if extra else None,
                "dormitory": extra.dormitory if extra else None,
                "political_status": extra.political_status if extra else None,
                "family_contact": extra.family_contact if extra else None,
                "family_address": extra.family_address if extra else None,
                "nation": extra.nation if extra else None,
            },
        }

    return payload


async def set_user_admin(user_id: int, is_admin: bool) -> dict[str, Any]:
    """切换用户管理员状态。

    Args:
        user_id: 用户 ID。
        is_admin: 目标管理员状态。

    Returns:
        dict[str, Any]: 更新后的用户摘要。

    Raises:
        KeyError: 当用户不存在时抛出。
    """
    user = await User.filter(id=user_id).first()
    if user is None:
        raise KeyError(str(user_id))
    user = await user.update(is_admin=is_admin)
    return _user_summary(user)


async def delete_user_bind(user_id: int, bind_id: int) -> dict[str, Any]:
    """删除用户的一条平台绑定。

    Args:
        user_id: 用户 ID。
        bind_id: 绑定记录 ID。

    Returns:
        dict[str, Any]: 删除结果。

    Raises:
        KeyError: 当绑定不存在时抛出。
    """
    bind = await UserBind.filter(id=bind_id, user_id=user_id).first()
    if bind is None:
        raise KeyError(str(bind_id))
    await bind.delete()
    return {"deleted": True, "bind_id": bind_id}


async def delete_user_account(user_id: int) -> dict[str, Any]:
    """删除用户账号及其可安全清理的关联数据。

    Args:
        user_id: 用户 ID。

    Returns:
        dict[str, Any]: 删除结果。

    Raises:
        KeyError: 当用户不存在时抛出。
        UserMutationError: 当仍存在班级、群组等业务关联或数据库删除失败时抛出。
    """
    async with get_session() as session:
        user = await session.scalar(select(User).where(User.id == user_id).options(*_user_load_options()))
        if user is None:
            raise KeyError(str(user_id))

        blockers: list[dict[str, Any]] = []

        if user.teacher is not None and user.teacher.classes:
            class_names = [item.name for item in user.teacher.classes[:6]]
            blockers.append(
                {
                    "code": "teacher_has_classes",
                    "message": f"教师身份仍绑定 {len(user.teacher.classes)} 个班级，请先移交或解除班级关联。",
                    "items": class_names,
                }
            )

        owned_groups = await user.get_groups()
        if owned_groups:
            group_names = [item.name for item in owned_groups[:6]]
            blockers.append(
                {
                    "code": "owns_groups",
                    "message": f"当前用户仍创建了 {len(owned_groups)} 个群组，请先处理这些群组后再删除账号。",
                    "items": group_names,
                }
            )

        if blockers:
            raise UserMutationError(
                "user_delete_blocked",
                "删除账号前仍有业务关联数据未清理。",
                hint="请先处理提示中的班级或群组关联，再重新执行删除。",
                blockers=blockers,
            )

        try:
            await user.delete_account()
        except IntegrityError as error:
            raise UserMutationError(
                "user_delete_conflict",
                "删除账号失败，当前用户仍被其他业务数据引用。",
                hint="请先检查群组、班级、组织或审批等关联数据是否已经清理。",
                detail=str(getattr(error, "orig", error)),
            ) from error

    return {"deleted": True, "user_id": user_id}
