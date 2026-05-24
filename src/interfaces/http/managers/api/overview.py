from __future__ import annotations

from fastapi import APIRouter, Depends

from ..agent import service as agent_service
from ..catalog import llm_models, prompts, skills
from ..schemas import StatusCheckRequest
from ..security import manager_auth
from ..runtime.status import check_system_metrics, get_status

router = APIRouter()


@router.get("/overview")
async def overview(_=Depends(manager_auth)):
    """返回总览页所需的聚合数据。"""

    status_payload = await get_status()
    runs = await agent_service.list_runs(page=1, page_size=5)
    checkpoints = await agent_service.list_checkpoints(status="needs_confirm", page=1, page_size=5)
    skill_items = skills.list_skills()["items"]
    prompt_items = prompts.list_prompts()["items"]
    model_items = llm_models.list_models()["items"]
    alerts = []
    for key, value in status_payload.items():
        if isinstance(value, dict) and value.get("status") in {"warning", "error", "not_configured"}:
            alerts.append({"source": key, "level": value.get("status"), "message": value.get("message", "")})
    return {
        "runtime": status_payload.get("runtime", {}),
        "assets": {
            "skills": len(skill_items),
            "prompts": len(prompt_items),
            "models": len(model_items),
            "agent_runs": runs["total"],
            "pending_workflows": checkpoints["total"],
        },
        "alerts": alerts,
        "recent_runs": runs["items"],
    }


@router.get("/status")
async def status_overview(_=Depends(manager_auth)):
    """返回完整系统状态。"""

    return await get_status()


@router.post("/status/check")
async def status_check(payload: StatusCheckRequest, _=Depends(manager_auth)):
    """按指定分组执行系统状态检查。"""

    return await get_status(payload.targets)


@router.get("/system/metrics")
async def system_metrics(_=Depends(manager_auth)):
    """返回系统资源监控指标。"""

    return check_system_metrics()


@router.get("/integrations")
async def integrations(_=Depends(manager_auth)):
    """返回集成页所需的第三方能力状态。"""

    status_payload = await get_status(["models", "cos", "ragflow", "mcp"])
    return {
        "mcp": status_payload.get("mcp", {}),
        "ragflow": status_payload.get("ragflow", {}),
        "cos": status_payload.get("cos", {}),
        "models": status_payload.get("models", {}),
    }
