from __future__ import annotations

from collections import defaultdict
from typing import Any

from nonebot_plugin_orm import get_session
from sqlalchemy import select
from sqlalchemy.orm import selectinload

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
    if value is None:
        return None
    return str(value)


def _user_brief(user: User | None) -> dict[str, Any] | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "nickname": user.nickname,
        "username": user.username,
        "avatar": user.avatar,
    }


def _bind_payload(bind: GroupBind) -> dict[str, Any]:
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
