from __future__ import annotations

from fastapi import Query, Depends, APIRouter, HTTPException, status

from ..security import manager_auth
from ..runtime import logs as log_service

router = APIRouter()


@router.get("/logs")
async def list_log_items(_=Depends(manager_auth)):
    """列出可读取的日志文件。"""

    return log_service.list_logs()


@router.get("/logs/read")
async def read_log(
    path: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
    _=Depends(manager_auth),
):
    """按偏移量读取日志。"""

    try:
        return log_service.read_log(path, offset=offset, limit=limit)
    except PermissionError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/logs/tail")
async def tail_log(
    path: str,
    lines: int = Query(300, ge=1, le=2000),
    _=Depends(manager_auth),
):
    """读取日志末尾若干行。"""

    try:
        return log_service.tail_log(path, lines=lines)
    except PermissionError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
