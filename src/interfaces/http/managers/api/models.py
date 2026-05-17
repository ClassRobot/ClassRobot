from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .. import audit
from ..catalog import llm_models as model_service
from ..schemas import ModelSettingsRequest
from ..security import manager_auth

router = APIRouter()


@router.get("/models")
async def list_model_items(_=Depends(manager_auth)):
    """列出模型配置清单。"""

    return model_service.list_models()


@router.put("/models")
async def save_model_items(payload: ModelSettingsRequest, session=Depends(manager_auth)):
    """保存模型配置。"""

    try:
        result = model_service.save_models(payload.dict(exclude_unset=True))
        audit.log_event(
            "models",
            "save_models",
            "completed",
            detail={"model_count": len(result.get("items", [])) if isinstance(result.get("items"), list) else None},
            session=session,
        )
        return result
    except ValueError as error:
        audit.log_event("models", "save_models", "failed", detail={"error": str(error)}, session=session)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except RuntimeError as error:
        audit.log_event("models", "save_models", "failed", detail={"error": str(error)}, session=session)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.post("/models/{name}/test")
async def test_model(name: str, session=Depends(manager_auth)):
    """测试指定模型配置。"""

    try:
        result = await model_service.test_model(name)
        audit.log_event("models", "test_model", "completed", detail={"name": name, "ok": result.get("ok")}, session=session)
        return result
    except KeyError as error:
        audit.log_event(
            "models",
            "test_model",
            "failed",
            detail={"name": name, "error": "Model config not found"},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model config not found") from error
    except Exception as error:  # noqa: BLE001
        audit.log_event("models", "test_model", "failed", detail={"name": name, "error": str(error)}, session=session)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
