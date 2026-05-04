from __future__ import annotations

from typing import Any

from sqlalchemy import and_, delete as sql_delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from nonebot_plugin_orm import get_session

from utils.models import AgentWorkflowCheckpoint, AgentWorkflowRun, User, Student, Teacher, UserBind


class UserMutationError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        hint: str | None = None,
        detail: str | None = None,
        blockers: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.detail = detail
        self.blockers = blockers or []

    def to_payload(self) -> dict[str, Any]:
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
    return [str(role) for role in user.roles]


def _user_summary(user: User) -> dict[str, Any]:
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
    return {
        "id": bind.id,
        "name": bind.name,
        "platform_id": bind.platform_id,
        "account_id": bind.account_id,
        "created_at": bind.created_at,
        "updated_at": bind.updated_at,
    }


async def _delete_fk_descendants(
    session,
    target_table,
    pk_values: dict[str, Any],
    seen: set[tuple[str, tuple[tuple[str, Any], ...]]],
) -> None:
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
                    {column.name: value for column, value in zip(pk_columns, row)}
                    for row in result.fetchall()
                ]

            for child_pk in child_rows:
                await _delete_fk_descendants(session, child_table, child_pk, seen)

            await session.execute(sql_delete(child_table).where(where_clause))


async def list_users(
    *,
    q: str | None = None,
    role: str | None = None,
    is_admin: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
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
    user = await User.filter(id=user_id).first()
    if user is None:
        raise KeyError(str(user_id))
    user = await user.update(is_admin=is_admin)
    return _user_summary(user)


async def delete_user_bind(user_id: int, bind_id: int) -> dict[str, Any]:
    bind = await UserBind.filter(id=bind_id, user_id=user_id).first()
    if bind is None:
        raise KeyError(str(bind_id))
    await bind.delete()
    return {"deleted": True, "bind_id": bind_id}


async def delete_user_account(user_id: int) -> dict[str, Any]:
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
            await _delete_fk_descendants(session, User.__table__, {"id": user.id}, set())
            await session.execute(sql_delete(AgentWorkflowCheckpoint.__table__).where(AgentWorkflowCheckpoint.user_id == user.id))
            await session.execute(sql_delete(AgentWorkflowRun.__table__).where(AgentWorkflowRun.user_id == user.id))
            await session.execute(sql_delete(User.__table__).where(User.id == user.id))
            await session.commit()
        except IntegrityError as error:
            raise UserMutationError(
                "user_delete_conflict",
                "删除账号失败，当前用户仍被其他业务数据引用。",
                hint="请先检查群组、班级、组织或审批等关联数据是否已经清理。",
                detail=str(getattr(error, "orig", error)),
            ) from error

    return {"deleted": True, "user_id": user_id}
