from __future__ import annotations

from fastapi import Query, Depends, APIRouter, HTTPException, status

from .. import audit
from ..security import manager_auth
from ..storage import files as file_service
from ..schemas import FileSpaceWriteRequest, FileSpaceDirectoryCreateRequest

router = APIRouter()


@router.get("/files/spaces")
async def list_manager_file_spaces(
    kind: str | None = None,
    q: str | None = None,
    _=Depends(manager_auth),
):
    """列出当前系统已存在的文件空间。"""

    try:
        return await file_service.list_file_spaces(kind=kind, q=q)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/files/spaces/{space_kind}/{owner_id}")
async def get_manager_file_space_detail(
    space_kind: str,
    owner_id: str,
    _=Depends(manager_auth),
):
    """读取单个文件空间的摘要与当前目录。"""

    try:
        return await file_service.get_file_space_detail(space_kind, owner_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/files/spaces/{space_kind}/{owner_id}/entries")
async def list_manager_file_space_entries(
    space_kind: str,
    owner_id: str,
    path: str | None = None,
    _=Depends(manager_auth),
):
    """读取文件空间目录条目。"""

    try:
        return await file_service.list_file_space_entries(space_kind, owner_id, path=path)
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except file_service.FileSpaceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/files/spaces/{space_kind}/{owner_id}/read")
async def read_manager_file_space_text(
    space_kind: str,
    owner_id: str,
    path: str,
    limit: int = Query(16384, ge=256, le=65536),
    _=Depends(manager_auth),
):
    """读取文件空间中的文本文件。"""

    try:
        return await file_service.read_file_space_text(space_kind, owner_id, path=path, limit=limit)
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except file_service.FileSpaceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.put("/files/spaces/{space_kind}/{owner_id}/write")
async def write_manager_file_space_text(
    space_kind: str,
    owner_id: str,
    payload: FileSpaceWriteRequest,
    session=Depends(manager_auth),
):
    """写入文件空间中的文本文件。"""

    try:
        result = await file_service.write_file_space_text(space_kind, owner_id, payload.path, payload.content)
        audit.log_event(
            "files",
            "write_file_space_text",
            "completed",
            detail={"kind": space_kind, "owner_id": owner_id, "path": payload.path},
            session=session,
        )
        return result
    except FileNotFoundError as error:
        audit.log_event(
            "files",
            "write_file_space_text",
            "failed",
            detail={"kind": space_kind, "owner_id": owner_id, "path": payload.path, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except file_service.FileSpaceError as error:
        audit.log_event(
            "files",
            "write_file_space_text",
            "failed",
            detail={"kind": space_kind, "owner_id": owner_id, "path": payload.path, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except ValueError as error:
        audit.log_event(
            "files",
            "write_file_space_text",
            "failed",
            detail={"kind": space_kind, "owner_id": owner_id, "path": payload.path, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/files/spaces/{space_kind}/{owner_id}/directories")
async def create_manager_file_space_directory(
    space_kind: str,
    owner_id: str,
    payload: FileSpaceDirectoryCreateRequest,
    session=Depends(manager_auth),
):
    """在文件空间中创建目录。"""

    try:
        result = await file_service.create_file_space_directory(space_kind, owner_id, payload.path)
        audit.log_event(
            "files",
            "create_file_space_directory",
            "completed",
            detail={"kind": space_kind, "owner_id": owner_id, "path": payload.path},
            session=session,
        )
        return result
    except FileNotFoundError as error:
        audit.log_event(
            "files",
            "create_file_space_directory",
            "failed",
            detail={"kind": space_kind, "owner_id": owner_id, "path": payload.path, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except file_service.FileSpaceError as error:
        audit.log_event(
            "files",
            "create_file_space_directory",
            "failed",
            detail={"kind": space_kind, "owner_id": owner_id, "path": payload.path, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except ValueError as error:
        audit.log_event(
            "files",
            "create_file_space_directory",
            "failed",
            detail={"kind": space_kind, "owner_id": owner_id, "path": payload.path, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.delete("/files/spaces/{space_kind}/{owner_id}/entry")
async def delete_manager_file_space_entry(
    space_kind: str,
    owner_id: str,
    path: str,
    recursive: bool = False,
    force: bool = False,
    session=Depends(manager_auth),
):
    """删除文件空间中的文件或目录。"""

    try:
        result = await file_service.delete_file_space_entry(
            space_kind,
            owner_id,
            path,
            recursive=recursive,
            force=force,
        )
        audit.log_event(
            "files",
            "delete_file_space_entry",
            "completed",
            detail={
                "kind": space_kind,
                "owner_id": owner_id,
                "path": path,
                "recursive": recursive,
                "force": force,
            },
            session=session,
        )
        return result
    except FileNotFoundError as error:
        audit.log_event(
            "files",
            "delete_file_space_entry",
            "failed",
            detail={"kind": space_kind, "owner_id": owner_id, "path": path, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except file_service.FileSpaceError as error:
        audit.log_event(
            "files",
            "delete_file_space_entry",
            "failed",
            detail={"kind": space_kind, "owner_id": owner_id, "path": path, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except ValueError as error:
        audit.log_event(
            "files",
            "delete_file_space_entry",
            "failed",
            detail={"kind": space_kind, "owner_id": owner_id, "path": path, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.delete("/files/spaces/{space_kind}/{owner_id}")
async def delete_manager_file_space(
    space_kind: str,
    owner_id: str,
    session=Depends(manager_auth),
):
    """删除整个文件空间。"""

    try:
        result = await file_service.delete_file_space(space_kind, owner_id)
        audit.log_event(
            "files",
            "delete_file_space",
            "completed",
            detail={"kind": space_kind, "owner_id": owner_id},
            session=session,
        )
        return result
    except FileNotFoundError as error:
        audit.log_event(
            "files",
            "delete_file_space",
            "failed",
            detail={"kind": space_kind, "owner_id": owner_id, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except file_service.FileSpaceError as error:
        audit.log_event(
            "files",
            "delete_file_space",
            "failed",
            detail={"kind": space_kind, "owner_id": owner_id, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except ValueError as error:
        audit.log_event(
            "files",
            "delete_file_space",
            "failed",
            detail={"kind": space_kind, "owner_id": owner_id, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
