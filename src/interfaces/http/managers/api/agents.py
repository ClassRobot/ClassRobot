from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .. import audit
from ..agent import service as agent_service
from ..schemas import AgentDesignerUpdateRequest
from ..security import manager_auth

router = APIRouter()


@router.get("/agents/overview")
async def get_agent_overview(_=Depends(manager_auth)):
    """读取 Agent 模块、编排、配置和运行数据概览。"""

    return await agent_service.get_overview()


@router.get("/agents/designer")
async def get_agent_designer(_=Depends(manager_auth)):
    """读取 Agent 可视化编排设计器草稿。"""

    return agent_service.get_designer()


@router.put("/agents/designer")
async def save_agent_designer(payload: AgentDesignerUpdateRequest, session=Depends(manager_auth)):
    """保存 Agent 可视化编排设计器草稿，可选择同步热更新运行时。"""

    try:
        result = agent_service.save_designer(payload, apply_to_runtime=payload.apply_to_runtime)
        audit.log_event(
            "agents",
            "save_designer",
            "completed",
            detail={
                "nodes": len(payload.nodes),
                "edges": len(payload.edges),
                "applied_to_runtime": result.get("applied_to_runtime", False),
                "apply_to_runtime": payload.apply_to_runtime,
            },
            session=session,
        )
        return result
    except ValueError as error:
        audit.log_event(
            "agents",
            "save_designer",
            "failed",
            detail={"error": str(error), "apply_to_runtime": payload.apply_to_runtime},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/agents/runs")
async def list_agent_runs(
    status: str | None = None,
    kind: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _=Depends(manager_auth),
):
    """列出 Agent 运行记录。"""

    return await agent_service.list_runs(status=status, kind=kind, q=q, page=page, page_size=page_size)


@router.get("/agents/runs/{trace_id}")
async def get_agent_run(trace_id: str, _=Depends(manager_auth)):
    """读取单个 Agent 运行详情。"""

    try:
        return await agent_service.get_run(trace_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found") from error


@router.get("/agents/checkpoints")
async def list_agent_checkpoints(
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _=Depends(manager_auth),
):
    """列出 Agent 工作流检查点。"""

    return await agent_service.list_checkpoints(status=status, page=page, page_size=page_size)


@router.get("/agents/checkpoints/{user_id}")
async def get_agent_checkpoint(user_id: int, _=Depends(manager_auth)):
    """读取指定用户的 Agent 检查点。"""

    try:
        return await agent_service.get_checkpoint(user_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent checkpoint not found") from error


@router.delete("/agents/checkpoints/{user_id}")
async def delete_agent_checkpoint(user_id: int, _=Depends(manager_auth)):
    """删除指定用户的 Agent 检查点。"""

    try:
        return await agent_service.delete_checkpoint(user_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent checkpoint not found") from error
