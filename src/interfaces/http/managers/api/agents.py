from __future__ import annotations

import asyncio
from contextlib import suppress

from src.core.agent.runtime.live_trace import agent_live_trace_registry
from fastapi import Query, Depends, APIRouter, WebSocket, HTTPException, WebSocketDisconnect, status

from .. import audit
from ..agent import service as agent_service
from ..schemas import AgentDesignerUpdateRequest
from ..security import token_store, manager_auth

router = APIRouter()


async def send_live_trace_snapshot(websocket: WebSocket, selected_trace_id: str = "") -> None:
    """向 WebSocket 客户端发送 live trace 当前快照。"""

    detail = None
    if selected_trace_id:
        try:
            detail = await agent_service.get_live_trace(selected_trace_id)
        except KeyError:
            detail = None
    await websocket.send_json(
        {
            "type": "snapshot",
            "status": agent_service.get_live_trace_status(),
            "traces": agent_service.list_live_traces(),
            "selected_trace_id": selected_trace_id,
            "detail": detail,
        }
    )


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


@router.get("/agents/live/status")
async def get_agent_live_trace_status(_=Depends(manager_auth)):
    """读取 Agent live trace 开发态观测状态。"""

    return agent_service.get_live_trace_status()


@router.get("/agents/live/traces")
async def list_agent_live_traces(_=Depends(manager_auth)):
    """列出正在执行和最近完成的 Agent live traces。"""

    return agent_service.list_live_traces()


@router.get("/agents/live/traces/{trace_id}")
async def get_agent_live_trace(trace_id: str, _=Depends(manager_auth)):
    """读取单条 Agent live trace 事件时间线。"""

    try:
        return await agent_service.get_live_trace(trace_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent live trace not found") from error


@router.websocket("/agents/live/ws")
async def agent_live_trace_ws(websocket: WebSocket, token: str = ""):
    """通过 WebSocket 推送 Agent live trace 更新。"""

    try:
        token_store.validate_session(token)
    except HTTPException:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    subscriber_id, queue = agent_live_trace_registry.subscribe()
    selected_trace_id = websocket.query_params.get("trace_id", "") or ""
    receive_task: asyncio.Task | None = None
    queue_task: asyncio.Task | None = None
    try:
        await send_live_trace_snapshot(websocket, selected_trace_id=selected_trace_id)
        while True:
            receive_task = asyncio.create_task(websocket.receive_json())
            queue_task = asyncio.create_task(queue.get())
            done, pending = await asyncio.wait(
                {receive_task, queue_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            if receive_task in done:
                message = receive_task.result()
                if isinstance(message, dict) and message.get("type") == "select_trace":
                    selected_trace_id = str(message.get("trace_id") or "")
                await send_live_trace_snapshot(websocket, selected_trace_id=selected_trace_id)
                continue
            if queue_task in done:
                _event = queue_task.result()
                await send_live_trace_snapshot(websocket, selected_trace_id=selected_trace_id)
    except WebSocketDisconnect:
        pass
    finally:
        agent_live_trace_registry.unsubscribe(subscriber_id)
        for task in (receive_task, queue_task):
            if task is not None and not task.done():
                task.cancel()


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
