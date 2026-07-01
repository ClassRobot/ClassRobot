from __future__ import annotations

from fastapi import Depends, APIRouter, HTTPException, status

from .. import audit
from ..security import manager_auth
from ..schemas import PromptUpdateRequest
from ..catalog import prompts as prompt_service

router = APIRouter()


@router.get("/prompts")
async def list_prompt_items(_=Depends(manager_auth)):
    """列出 Prompt 清单。"""

    return prompt_service.list_prompts()


@router.get("/prompts/{name}")
async def get_prompt(name: str, _=Depends(manager_auth)):
    """读取单个 Prompt 内容。"""

    try:
        return prompt_service.get_prompt(name)
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.put("/prompts/{name}")
async def update_prompt(name: str, payload: PromptUpdateRequest, session=Depends(manager_auth)):
    """更新单个 Prompt 模板。"""

    try:
        result = prompt_service.update_prompt(name, payload.content)
        audit.log_event(
            "prompts",
            "update_prompt",
            "completed" if result.get("saved") else "failed",
            detail={"name": name, "saved": result.get("saved"), "valid": result.get("valid")},
            session=session,
        )
        return result
    except FileNotFoundError as error:
        audit.log_event(
            "prompts", "update_prompt", "failed", detail={"name": name, "error": str(error)}, session=session
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        audit.log_event(
            "prompts", "update_prompt", "failed", detail={"name": name, "error": str(error)}, session=session
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/prompts/{name}/validate")
async def validate_prompt(name: str, _=Depends(manager_auth)):
    """校验单个 Prompt 模板。"""

    try:
        return prompt_service.validate_prompt(name)
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
