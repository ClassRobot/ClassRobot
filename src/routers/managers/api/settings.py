from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .. import audit
from ..runtime import settings as settings_store
from ..schemas import SettingsPatchRequest
from ..security import manager_auth, token_store

router = APIRouter()


@router.get("/settings")
async def get_settings(_=Depends(manager_auth)):
    """读取设置页完整配置。"""

    return settings_store.get_settings()


@router.get("/settings/runtime-config")
async def get_settings_runtime_config(_=Depends(manager_auth)):
    """读取 ``driver.config`` 的完整运行配置快照。"""

    return settings_store.get_runtime_config_snapshot()


@router.patch("/settings")
async def update_settings(payload: SettingsPatchRequest, session=Depends(manager_auth)):
    """更新本地后台可编辑配置。

    Args:
        payload: 按分组提交的设置更新请求。
        session: 当前管理端会话。

    Returns:
        dict[str, Any]: 设置保存结果。

    Raises:
        HTTPException: 当字段校验失败或缺少依赖时抛出。
    """

    try:
        result = settings_store.update_settings(payload.dict(exclude_unset=True))
        audit.log_event(
            "settings",
            "update_settings",
            "completed",
            detail={"changed_keys": result.get("changed_keys", [])},
            session=session,
        )
        return result
    except ValueError as error:
        audit.log_event("settings", "update_settings", "failed", detail={"error": str(error)}, session=session)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except RuntimeError as error:
        audit.log_event("settings", "update_settings", "failed", detail={"error": str(error)}, session=session)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.post("/settings/security/rotate-token")
async def rotate_token(session=Depends(manager_auth)):
    """轮换后台启动令牌并使现有会话失效。"""

    token_store.rotate_startup_token(log_token=True)
    audit.log_event("settings", "rotate_token", "completed", session=session)
    return {
        "rotated": True,
        "new_token_preview": token_store.preview_startup_token(),
        "message": "New manager token has been printed to the application log.",
    }
