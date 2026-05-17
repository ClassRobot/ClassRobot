from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .. import audit
from ..storage import chat_history as chat_service
from ..security import manager_auth

router = APIRouter()


@router.get("/chat-history/spaces")
async def list_manager_chat_spaces(
    kind: str | None = None,
    q: str | None = None,
    _=Depends(manager_auth),
):
    """列出当前系统中已有聊天记录的空间。"""

    try:
        return await chat_service.list_chat_spaces(kind=kind, q=q)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/chat-history/spaces/{space_kind}/{owner_id}")
async def get_manager_chat_space_detail(
    space_kind: str,
    owner_id: str,
    _=Depends(manager_auth),
):
    """读取单个聊天空间的摘要详情。"""

    try:
        return await chat_service.get_chat_space_detail(space_kind, owner_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/chat-history/spaces/{space_kind}/{owner_id}/messages")
async def list_manager_chat_messages(
    space_kind: str,
    owner_id: str,
    q: str | None = None,
    record_kind: str | None = None,
    actor_role: str | None = None,
    direction: str | None = None,
    message_date: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _=Depends(manager_auth),
):
    """分页读取指定聊天空间中的消息记录。"""

    try:
        return await chat_service.list_chat_messages(
            space_kind,
            owner_id,
            q=q,
            record_kind=record_kind,
            actor_role=actor_role,
            direction=direction,
            message_date=message_date,
            page=page,
            page_size=page_size,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.delete("/chat-history/spaces/{space_kind}/{owner_id}")
async def delete_manager_chat_space(
    space_kind: str,
    owner_id: str,
    session=Depends(manager_auth),
):
    """删除整个聊天记录空间目录。"""

    try:
        result = await chat_service.delete_chat_space(space_kind, owner_id)
        audit.log_event(
            "chat_history",
            "delete_chat_space",
            "completed",
            detail={"kind": space_kind, "owner_id": owner_id},
            session=session,
        )
        return result
    except ValueError as error:
        audit.log_event(
            "chat_history",
            "delete_chat_space",
            "failed",
            detail={"kind": space_kind, "owner_id": owner_id, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except FileNotFoundError as error:
        audit.log_event(
            "chat_history",
            "delete_chat_space",
            "failed",
            detail={"kind": space_kind, "owner_id": owner_id, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
