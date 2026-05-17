from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .. import audit
from ..identity import users as user_service
from ..schemas import AdminPatchRequest
from ..security import manager_auth

router = APIRouter()


@router.get("/users")
async def list_users(
    q: str | None = None,
    role: str | None = None,
    is_admin: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _=Depends(manager_auth),
):
    """列出用户中心表格数据。"""

    return await user_service.list_users(q=q, role=role, is_admin=is_admin, page=page, page_size=page_size)


@router.get("/users/{user_id}")
async def get_user(user_id: int, _=Depends(manager_auth)):
    """读取单个用户详情。"""

    try:
        return await user_service.get_user_detail(user_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from error


@router.patch("/users/{user_id}/admin")
async def patch_user_admin(user_id: int, payload: AdminPatchRequest, session=Depends(manager_auth)):
    """修改用户管理员状态。"""

    try:
        result = await user_service.set_user_admin(user_id, payload.is_admin)
        audit.log_event(
            "users",
            "patch_user_admin",
            "completed",
            detail={"user_id": user_id, "is_admin": payload.is_admin},
            session=session,
        )
        return result
    except KeyError as error:
        audit.log_event(
            "users",
            "patch_user_admin",
            "failed",
            detail={"user_id": user_id, "error": "User not found"},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from error


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, session=Depends(manager_auth)):
    """删除用户账号及其可安全清理的关联数据。"""

    try:
        result = await user_service.delete_user_account(user_id)
        audit.log_event(
            "users",
            "delete_user",
            "completed",
            detail={"user_id": user_id},
            session=session,
        )
        return result
    except KeyError as error:
        audit.log_event(
            "users",
            "delete_user",
            "failed",
            detail={"user_id": user_id, "error": "User not found"},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from error
    except user_service.UserMutationError as error:
        payload = error.to_payload()
        audit.log_event(
            "users",
            "delete_user",
            "failed",
            detail={"user_id": user_id, "error": payload},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=payload) from error


@router.delete("/users/{user_id}/binds/{bind_id}")
async def delete_user_bind(user_id: int, bind_id: int, session=Depends(manager_auth)):
    """删除用户的一条平台绑定。"""

    try:
        result = await user_service.delete_user_bind(user_id, bind_id)
        audit.log_event(
            "users",
            "delete_user_bind",
            "completed",
            detail={"user_id": user_id, "bind_id": bind_id},
            session=session,
        )
        return result
    except KeyError as error:
        audit.log_event(
            "users",
            "delete_user_bind",
            "failed",
            detail={"user_id": user_id, "bind_id": bind_id, "error": "Bind not found"},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bind not found") from error
