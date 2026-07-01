from __future__ import annotations

from fastapi import Depends, APIRouter, HTTPException, status

from .. import audit
from ..security import manager_auth
from ..catalog import skills as skill_service

router = APIRouter()


@router.get("/skills")
async def list_skill_items(_=Depends(manager_auth)):
    """列出 Skill 清单。"""

    return skill_service.list_skills()


@router.get("/skills/{name}")
async def get_skill(name: str, _=Depends(manager_auth)):
    """读取单个 Skill 详情。"""

    try:
        return skill_service.get_skill(name)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found") from error


@router.post("/skills/reload")
async def reload_skills(session=Depends(manager_auth)):
    """重新加载 Skill。"""

    result = skill_service.reload_skills()
    audit.log_event(
        "skills",
        "reload_skills",
        "completed",
        detail={"loaded_classes": result.get("loaded_classes", [])},
        session=session,
    )
    return result
