from __future__ import annotations

from collections import defaultdict
from typing import Any

from nonebot_plugin_orm import get_session
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from utils.storage import storage_manager
from utils.models import (
    Classes,
    ClassesJoinRequest,
    Group,
    GroupBind,
    Student,
    Teacher,
    TeacherClasses,
    User,
)


def _group_load_options():
    """返回群组中心查询共用的预加载关系配置。

    Returns:
        tuple[Any, ...]: SQLAlchemy ``selectinload`` 选项集合。
    """
    return (
        selectinload(Group.creator),
        selectinload(Group.settings),
        selectinload(Group.classes).selectinload(Classes.school),
        selectinload(Group.classes).selectinload(Classes.college),
        selectinload(Group.classes).selectinload(Classes.major_ref),
        selectinload(Group.classes).selectinload(Classes.teacher).selectinload(Teacher.user),
        selectinload(Group.classes).selectinload(Classes.teacher).selectinload(Teacher.school),
        selectinload(Group.classes).selectinload(Classes.teacher).selectinload(Teacher.college),
        selectinload(Group.classes).selectinload(Classes.students).selectinload(Student.user),
        selectinload(Group.classes).selectinload(Classes.students).selectinload(Student.school),
    )


def _stringify(value: Any) -> str | None:
    """把枚举或任意值统一转换成字符串。

    Args:
        value: 原始字段值。

    Returns:
        str | None: 字符串值；原值为 ``None`` 时返回 ``None``。
    """
    if value is None:
        return None
    return str(value)


def _user_brief(user: User | None) -> dict[str, Any] | None:
    """构造群组中心内联用户摘要。

    Args:
        user: 用户模型实例或 ``None``。

    Returns:
        dict[str, Any] | None: 头像、昵称、用户名等简要信息。
    """
    if user is None:
        return None
    return {
        "id": user.id,
        "nickname": user.nickname,
        "username": user.username,
        "avatar": user.avatar,
    }


def _bind_payload(bind: GroupBind) -> dict[str, Any]:
    """序列化群组平台绑定记录。

    Args:
        bind: 群组绑定模型实例。

    Returns:
        dict[str, Any]: 平台绑定展示字段。
    """
    return {
        "id": bind.id,
        "name": bind.name,
        "platform_id": bind.platform_id,
        "channel_id": bind.channel_id,
        "guild_id": bind.guild_id,
        "created_at": bind.created_at,
        "updated_at": bind.updated_at,
    }


def _class_identity(classes: Classes | None) -> dict[str, Any] | None:
    """构造班级基础信息。

    Args:
        classes: 班级模型实例或 ``None``。

    Returns:
        dict[str, Any] | None: 班级基础字段；不存在时返回 ``None``。
    """
    if classes is None:
        return None
    major_name = classes.major_ref.name if classes.major_ref else classes.major
    return {
        "id": classes.id,
        "name": classes.name,
        "school_id": classes.school_id,
        "school_name": classes.school.name if classes.school else None,
        "college_id": classes.college_id,
        "college_name": classes.college.name if classes.college else None,
        "major_id": classes.major_id,
        "major_name": major_name,
        "created_at": classes.created_at,
        "updated_at": classes.updated_at,
    }


def _class_summary(classes: Classes | None, pending_join_count: int = 0) -> dict[str, Any] | None:
    """构造带计数信息的班级摘要。

    Args:
        classes: 班级模型实例或 ``None``。
        pending_join_count: 待处理入班申请数。

    Returns:
        dict[str, Any] | None: 班级基础字段加成员/申请计数。
    """
    identity = _class_identity(classes)
    if identity is None or classes is None:
        return None
    identity.update(
        {
            "student_count": len(classes.students),
            "teacher_count": len(classes.teacher),
            "pending_join_count": pending_join_count,
        }
    )
    return identity


def _group_summary(group: Group, binds: list[GroupBind], pending_join_count: int = 0) -> dict[str, Any]:
    """构造群组列表行摘要。

    Args:
        group: 群组模型实例。
        binds: 该群组关联的平台绑定列表。
        pending_join_count: 待处理入班申请数。

    Returns:
        dict[str, Any]: 群组中心列表行数据。
    """
    classes = getattr(group, "classes", None)
    platforms = sorted({bind.platform_id for bind in binds})
    return {
        "id": group.id,
        "name": group.name,
        "creator": _user_brief(group.creator),
        "join_method": _stringify(group.settings.join_method if group.settings else None),
        "class_info": _class_summary(classes, pending_join_count),
        "bind_count": len(binds),
        "platforms": platforms,
        "student_count": len(classes.students) if classes else 0,
        "teacher_count": len(classes.teacher) if classes else 0,
        "pending_join_count": pending_join_count,
        "created_at": group.created_at,
        "updated_at": group.updated_at,
    }


def _matches_query(group: Group, binds: list[GroupBind], q_lower: str) -> bool:
    """判断群组是否命中搜索词。

    Args:
        group: 群组模型实例。
        binds: 群组绑定列表。
        q_lower: 已转小写的搜索词。

    Returns:
        bool: 命中任一可搜索字段时返回 ``True``。
    """
    classes = getattr(group, "classes", None)
    haystacks = [
        group.name,
        group.creator.nickname if group.creator else "",
        group.creator.username if group.creator else "",
        classes.name if classes else "",
        classes.school.name if classes and classes.school else "",
        classes.college.name if classes and classes.college else "",
        classes.major_ref.name if classes and classes.major_ref else "",
        classes.major if classes else "",
        *[bind.platform_id for bind in binds],
        *[bind.channel_id for bind in binds],
        *[(bind.guild_id or "") for bind in binds],
    ]
    return any(q_lower in (item or "").lower() for item in haystacks)


async def _load_group_context() -> tuple[list[Group], dict[int, list[GroupBind]], dict[int, int]]:
    """加载群组中心列表需要的全部上下文数据。

    Returns:
        tuple[list[Group], dict[int, list[GroupBind]], dict[int, int]]:
            群组列表、按群组聚合的平台绑定、按班级聚合的申请计数。
    """
    async with get_session() as session:
        groups = list(await session.scalars(select(Group).options(*_group_load_options())))
        group_ids = [group.id for group in groups]

        binds_by_group: dict[int, list[GroupBind]] = defaultdict(list)
        if group_ids:
            binds_result = await session.scalars(
                select(GroupBind).where(GroupBind.group_id.in_(group_ids)).order_by(GroupBind.id)
            )
            for bind in binds_result:
                binds_by_group[bind.group_id].append(bind)

        class_ids = [
            group.classes.id
            for group in groups
            if getattr(group, "classes", None) is not None
        ]
        pending_by_class: dict[int, int] = defaultdict(int)
        if class_ids:
            join_requests = await session.scalars(
                select(ClassesJoinRequest).where(ClassesJoinRequest.classes_id.in_(class_ids))
            )
            for request in join_requests:
                pending_by_class[request.classes_id] += 1

    return groups, binds_by_group, pending_by_class


async def list_groups(
    *,
    q: str | None = None,
    platform_id: str | None = None,
    join_method: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """列出群组中心表格数据。

    Args:
        q: 可选的群组、班级、平台等模糊搜索词。
        platform_id: 可选的平台过滤条件。
        join_method: 可选的入群方式过滤条件。
        page: 页码，从 1 开始。
        page_size: 每页条目数。

    Returns:
        dict[str, Any]: 标准分页结果。
    """
    groups, binds_by_group, pending_by_class = await _load_group_context()

    if q:
        q_lower = q.lower()
        groups = [group for group in groups if _matches_query(group, binds_by_group[group.id], q_lower)]

    if platform_id:
        groups = [
            group
            for group in groups
            if any(bind.platform_id == platform_id for bind in binds_by_group[group.id])
        ]

    if join_method:
        groups = [
            group
            for group in groups
            if _stringify(group.settings.join_method if group.settings else None) == join_method
        ]

    groups.sort(key=lambda item: item.id, reverse=True)
    total = len(groups)
    start = max(page - 1, 0) * page_size
    end = start + page_size
    items = []
    for group in groups[start:end]:
        classes = getattr(group, "classes", None)
        pending_count = pending_by_class.get(classes.id, 0) if classes else 0
        items.append(_group_summary(group, binds_by_group[group.id], pending_count))

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


async def get_group_detail(group_id: int) -> dict[str, Any]:
    """读取单个群组详情。

    Args:
        group_id: 群组 ID。

    Returns:
        dict[str, Any]: 群组、班级、成员、绑定和申请详情。

    Raises:
        KeyError: 当群组不存在时抛出。
    """
    async with get_session() as session:
        group = await session.scalar(
            select(Group)
            .where(Group.id == group_id)
            .options(*_group_load_options())
        )
        if group is None:
            raise KeyError(str(group_id))

        binds = list(await session.scalars(select(GroupBind).where(GroupBind.group_id == group.id).order_by(GroupBind.id)))
        classes = getattr(group, "classes", None)
        teacher_roles: dict[int, str] = {}
        join_requests: list[ClassesJoinRequest] = []
        if classes is not None:
            role_rows = await session.scalars(
                select(TeacherClasses).where(TeacherClasses.classes_id == classes.id)
            )
            teacher_roles = {item.teacher_id: _stringify(item.role) or "" for item in role_rows}
            join_requests = list(
                await session.scalars(
                    select(ClassesJoinRequest)
                    .where(ClassesJoinRequest.classes_id == classes.id)
                    .options(selectinload(ClassesJoinRequest.user))
                    .order_by(ClassesJoinRequest.created_at.desc())
                )
            )

    pending_count = len(join_requests)
    summary = _group_summary(group, binds, pending_count)
    class_detail = _class_summary(classes, pending_count)

    teachers = []
    students = []
    if classes is not None:
        teachers = [
            {
                "id": teacher.id,
                "name": teacher.name,
                "role": _stringify(teacher.role),
                "class_role": teacher_roles.get(teacher.id),
                "school_name": teacher.school.name if teacher.school else None,
                "college_name": teacher.college.name if teacher.college else None,
                "user": _user_brief(teacher.user),
            }
            for teacher in classes.teacher
        ]
        students = [
            {
                "id": student.id,
                "name": student.name,
                "role": _stringify(student.role),
                "school_name": student.school.name if student.school else None,
                "user": _user_brief(student.user),
            }
            for student in classes.students
        ]

    summary.update(
        {
            "group": {
                "id": group.id,
                "name": group.name,
                "creator": _user_brief(group.creator),
                "join_method": _stringify(group.settings.join_method if group.settings else None),
                "created_at": group.created_at,
                "updated_at": group.updated_at,
            },
            "class_detail": class_detail,
            "binds": [_bind_payload(bind) for bind in binds],
            "teachers": teachers,
            "students": students,
            "join_requests": [
                {
                    "id": request.id,
                    "user": _user_brief(request.user),
                    "join_method": _stringify(request.join_method),
                    "describe": request.describe,
                    "created_at": request.created_at,
                }
                for request in join_requests
            ],
        }
    )
    return summary


async def delete_group(group_id: int) -> dict[str, Any]:
    """删除群组及其挂载班级、绑定与群文件空间。

    Args:
        group_id: 群组 ID。

    Returns:
        dict[str, Any]: 删除结果摘要。

    Raises:
        KeyError: 当群组不存在时抛出。
    """

    async with get_session() as session:
        group = await session.scalar(
            select(Group)
            .where(Group.id == group_id)
            .options(*_group_load_options())
        )
        if group is None:
            raise KeyError(str(group_id))
        binds = list(
            await session.scalars(
                select(GroupBind).where(GroupBind.group_id == group.id).order_by(GroupBind.id)
            )
        )

    group_name = group.name
    channel_owner_ids = sorted({bind.channel_id for bind in binds if bind.channel_id})
    await group.delete_group(manager=storage_manager)
    storage_manager.delete_group_space(group_id)
    for channel_owner_id in channel_owner_ids:
        storage_manager.delete_group_space(channel_owner_id)
    return {
        "deleted": True,
        "group_id": group_id,
        "group_name": group_name,
    }
