from __future__ import annotations

from fastapi import Query, Depends, APIRouter, HTTPException, status

from .. import audit
from ..security import manager_auth
from ..schemas import DatabaseRowUpdateRequest
from ..database import service as database_service

router = APIRouter()


@router.get("/databases")
async def list_database_connections(_=Depends(manager_auth)):
    """列出管理端可用数据库连接。"""

    return await database_service.list_connections()


@router.get("/databases/{database_id}/schema")
async def get_database_schema(
    database_id: str,
    schema: str | None = None,
    refresh: bool = Query(False),
    _=Depends(manager_auth),
):
    """读取数据库表结构和外键关系。"""

    try:
        return await database_service.get_schema(database_id, schema=schema, force_refresh=refresh)
    except database_service.DatabaseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found") from error


@router.get("/databases/{database_id}/tables")
async def list_database_tables(
    database_id: str,
    schema: str | None = None,
    refresh: bool = Query(False),
    _=Depends(manager_auth),
):
    """列出数据库表摘要。"""

    try:
        return await database_service.list_tables(database_id, schema=schema, force_refresh=refresh)
    except database_service.DatabaseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found") from error


@router.get("/databases/{database_id}/tables/{table_name}/rows")
async def get_database_table_rows(
    database_id: str,
    table_name: str,
    schema: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _=Depends(manager_auth),
):
    """分页读取数据表中的数据行。"""

    try:
        return await database_service.get_table_rows(
            database_id,
            table_name,
            schema=schema,
            page=page,
            page_size=page_size,
        )
    except database_service.DatabaseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found") from error
    except database_service.TableNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found") from error


@router.patch("/databases/{database_id}/tables/{table_name}/rows")
async def update_database_table_row(
    database_id: str,
    table_name: str,
    payload: DatabaseRowUpdateRequest,
    schema: str | None = None,
    session=Depends(manager_auth),
):
    """更新数据表中的一行记录。"""

    try:
        result = await database_service.update_table_row(
            database_id,
            table_name,
            pk=payload.pk,
            values=payload.values,
            schema=schema,
        )
        audit.log_event(
            "databases",
            "update_table_row",
            "completed",
            detail={"database_id": database_id, "schema": schema, "table": table_name},
            session=session,
        )
        return result
    except database_service.DatabaseNotFoundError as error:
        audit.log_event(
            "databases",
            "update_table_row",
            "failed",
            detail={"database_id": database_id, "table": table_name, "error": "Database connection not found"},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found") from error
    except database_service.TableNotFoundError as error:
        audit.log_event(
            "databases",
            "update_table_row",
            "failed",
            detail={"database_id": database_id, "table": table_name, "error": "Table not found"},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found") from error
    except database_service.RowUpdateError as error:
        audit.log_event(
            "databases",
            "update_table_row",
            "failed",
            detail={"database_id": database_id, "table": table_name, "error": error.to_payload()},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error.to_payload()) from error
    except ValueError as error:
        audit.log_event(
            "databases",
            "update_table_row",
            "failed",
            detail={"database_id": database_id, "table": table_name, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
