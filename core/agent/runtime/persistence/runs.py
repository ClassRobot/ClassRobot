from nonebot import logger
from sqlalchemy import select
from nonebot_plugin_orm import get_session
from sqlalchemy.exc import SQLAlchemyError

from utils.models.models import AgentWorkflowRun

from ..schema import TaskWorkflow
from .checkpoints import serialize_workflow


class WorkflowRunStore:
    """保存工作流运行历史，供后续审计、恢复链路和调试使用。"""

    async def save_run(self, user_id: int, workflow: TaskWorkflow) -> AgentWorkflowRun | None:
        """按 trace_id 创建或更新一条工作流运行记录。"""

        payload = serialize_workflow(workflow)
        try:
            async with get_session() as session:
                run = await session.scalar(
                    select(AgentWorkflowRun).where(AgentWorkflowRun.trace_id == workflow.trace_id)
                )
                if run is None:
                    run = AgentWorkflowRun(
                        user_id=user_id,
                        trace_id=workflow.trace_id,
                        source_trace_id=workflow.source_trace_id,
                        kind=workflow.kind,
                        status=workflow.status,
                        goal=workflow.goal,
                        summary=workflow.summary,
                        playbook_id=workflow.playbook_id,
                        playbook_name=workflow.playbook_name,
                        approval_type=workflow.approval.type,
                        approval_status=workflow.approval.status,
                        approval_reason=workflow.approval.reason,
                        started_at=workflow.started_at,
                        finished_at=workflow.finished_at,
                        workflow_data=payload,
                    )
                    session.add(run)
                else:
                    run.source_trace_id = workflow.source_trace_id
                    run.kind = workflow.kind
                    run.status = workflow.status
                    run.goal = workflow.goal
                    run.summary = workflow.summary
                    run.playbook_id = workflow.playbook_id
                    run.playbook_name = workflow.playbook_name
                    run.approval_type = workflow.approval.type
                    run.approval_status = workflow.approval.status
                    run.approval_reason = workflow.approval.reason
                    run.started_at = workflow.started_at
                    run.finished_at = workflow.finished_at
                    run.workflow_data = payload
                await session.commit()
                await session.refresh(run)
                return run
        except SQLAlchemyError as error:
            logger.warning(f"AutoGPT workflow run save skipped for user {user_id}: {error}")
            return None

    async def get_run(self, trace_id: str) -> AgentWorkflowRun | None:
        """按 trace_id 获取工作流运行记录。"""

        try:
            async with get_session() as session:
                return await session.scalar(select(AgentWorkflowRun).where(AgentWorkflowRun.trace_id == trace_id))
        except SQLAlchemyError as error:
            logger.warning(f'AutoGPT workflow run load skipped for trace "{trace_id}": {error}')
            return None

    async def list_runs(self, user_id: int, limit: int = 20) -> list[AgentWorkflowRun]:
        """获取用户最近的工作流运行记录。"""

        try:
            async with get_session() as session:
                result = await session.scalars(
                    select(AgentWorkflowRun)
                    .where(AgentWorkflowRun.user_id == user_id)
                    .order_by(AgentWorkflowRun.id.desc())
                    .limit(limit)
                )
                return list(result)
        except SQLAlchemyError as error:
            logger.warning(f"AutoGPT workflow run list skipped for user {user_id}: {error}")
            return []
