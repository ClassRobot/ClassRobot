from __future__ import annotations

from fastapi import Query, Depends, APIRouter, HTTPException, status

from .. import audit
from ..security import manager_auth
from ..identity import groups as group_service

router = APIRouter()


@router.get("/groups")
async def list_group_items(
    q: str | None = None,
    platform_id: str | None = None,
    join_method: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _=Depends(manager_auth),
):
    """列出群组中心表格数据。"""

    return await group_service.list_groups(
        q=q,
        platform_id=platform_id,
        join_method=join_method,
        page=page,
        page_size=page_size,
    )


@router.get("/groups/{group_id}")
async def get_group_item(group_id: int, _=Depends(manager_auth)):
    """读取单个群组详情。"""

    try:
        return await group_service.get_group_detail(group_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found") from error


@router.delete("/groups/{group_id}")
async def delete_group_item(group_id: int, session=Depends(manager_auth)):
    """删除群组、班级挂载和相关群文件空间。"""

    try:
        result = await group_service.delete_group(group_id)
        audit.log_event(
            "groups",
            "delete_group",
            "completed",
            detail={"group_id": group_id},
            session=session,
        )
        return result
    except KeyError as error:
        audit.log_event(
            "groups",
            "delete_group",
            "failed",
            detail={"group_id": group_id, "error": "Group not found"},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found") from error
