from __future__ import annotations

from typing import Any

from sqlalchemy import select
from nonebot_plugin_orm import get_session

from utils.models import AgentWorkflowRun, AgentWorkflowCheckpoint


def _run_summary(run: AgentWorkflowRun) -> dict[str, Any]:
    """序列化一条 Agent 运行记录摘要。

    Args:
        run: Agent 工作流运行模型实例。

    Returns:
        dict[str, Any]: 前端列表和详情头部共用的字段。
    """
    return {
        "id": run.id,
        "user_id": run.user_id,
        "trace_id": run.trace_id,
        "source_trace_id": run.source_trace_id,
        "kind": run.kind,
        "status": run.status,
        "goal": run.goal,
        "summary": run.summary,
        "playbook_id": run.playbook_id,
        "playbook_name": run.playbook_name,
        "approval_type": run.approval_type,
        "approval_status": run.approval_status,
        "approval_reason": run.approval_reason,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def _checkpoint_summary(checkpoint: AgentWorkflowCheckpoint) -> dict[str, Any]:
    """序列化一条工作流检查点摘要。

    Args:
        checkpoint: Agent 工作流检查点模型实例。

    Returns:
        dict[str, Any]: 检查点摘要字段。
    """
    return {
        "id": checkpoint.id,
        "user_id": checkpoint.user_id,
        "trace_id": checkpoint.trace_id,
        "kind": checkpoint.kind,
        "status": checkpoint.status,
        "goal": checkpoint.goal,
        "summary": checkpoint.summary,
        "playbook_id": checkpoint.playbook_id,
        "playbook_name": checkpoint.playbook_name,
        "created_at": checkpoint.created_at,
        "updated_at": checkpoint.updated_at,
    }


async def list_runs(
    *,
    status: str | None = None,
    kind: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """按条件列出 Agent 运行记录。

    Args:
        status: 可选的运行状态过滤。
        kind: 可选的工作流类型过滤。
        q: 可选的 trace_id、goal 或 summary 模糊搜索词。
        page: 页码，从 1 开始。
        page_size: 每页条目数。

    Returns:
        dict[str, Any]: 标准分页结果。
    """
    runs = await AgentWorkflowRun.filter().all()
    if status:
        runs = [run for run in runs if run.status == status]
    if kind:
        runs = [run for run in runs if run.kind == kind]
    if q:
        q_lower = q.lower()
        runs = [
            run
            for run in runs
            if q_lower in run.trace_id.lower()
            or q_lower in (run.goal or "").lower()
            or q_lower in (run.summary or "").lower()
        ]

    runs.sort(key=lambda item: item.id, reverse=True)
    total = len(runs)
    start = max(page - 1, 0) * page_size
    end = start + page_size
    return {
        "items": [_run_summary(run) for run in runs[start:end]],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


async def get_run(trace_id: str) -> dict[str, Any]:
    """读取单条 Agent 运行详情。

    Args:
        trace_id: 运行记录的 trace_id。

    Returns:
        dict[str, Any]: 包含 ``workflow_data`` 的运行详情。

    Raises:
        KeyError: 当运行记录不存在时抛出。
    """
    run = await AgentWorkflowRun.filter(trace_id=trace_id).first()
    if run is None:
        raise KeyError(trace_id)
    payload = _run_summary(run)
    payload["workflow_data"] = run.workflow_data
    return payload


async def list_checkpoints(
    *,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """列出 Agent 工作流检查点。

    Args:
        status: 可选的检查点状态过滤。
        page: 页码，从 1 开始。
        page_size: 每页条目数。

    Returns:
        dict[str, Any]: 标准分页结果。
    """
    checkpoints = await AgentWorkflowCheckpoint.filter().all()
    if status:
        checkpoints = [checkpoint for checkpoint in checkpoints if checkpoint.status == status]
    checkpoints.sort(key=lambda item: item.id, reverse=True)
    total = len(checkpoints)
    start = max(page - 1, 0) * page_size
    end = start + page_size
    return {
        "items": [_checkpoint_summary(checkpoint) for checkpoint in checkpoints[start:end]],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


async def get_checkpoint(user_id: int) -> dict[str, Any]:
    """读取指定用户的检查点详情。

    Args:
        user_id: 用户 ID。

    Returns:
        dict[str, Any]: 包含 ``workflow_data`` 的检查点详情。

    Raises:
        KeyError: 当检查点不存在时抛出。
    """
    checkpoint = await AgentWorkflowCheckpoint.filter(user_id=user_id).first()
    if checkpoint is None:
        raise KeyError(str(user_id))
    payload = _checkpoint_summary(checkpoint)
    payload["workflow_data"] = checkpoint.workflow_data
    return payload


async def delete_checkpoint(user_id: int) -> dict[str, Any]:
    """删除指定用户的检查点。

    Args:
        user_id: 用户 ID。

    Returns:
        dict[str, Any]: 删除结果。

    Raises:
        KeyError: 当检查点不存在时抛出。
    """
    async with get_session() as session:
        checkpoint = await session.scalar(
            select(AgentWorkflowCheckpoint).where(AgentWorkflowCheckpoint.user_id == user_id)
        )
        if checkpoint is None:
            raise KeyError(str(user_id))
        await session.delete(checkpoint)
        await session.commit()
    return {"deleted": True, "user_id": user_id}
