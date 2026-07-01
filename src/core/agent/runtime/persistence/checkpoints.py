import json

from nonebot import logger
from sqlalchemy import select
from nonebot_plugin_orm import get_session
from sqlalchemy.exc import SQLAlchemyError
from src.models.models import AgentWorkflowCheckpoint

from ..schema import TaskWorkflow


def serialize_workflow(workflow: TaskWorkflow) -> dict:
    """把工作流转换成适合写入 JSON 列的结构。"""

    return workflow.model_dump(mode="json")


class WorkflowCheckpointStore:
    """持久化每个用户最近一次 Agent 工作流状态。

    当前只维护“最新检查点”，优先解决待确认工作流在进程重启后无法恢复的问题。
    如果数据库表尚未迁移完成，这里会自动降级为只记录日志，避免影响主流程。
    """

    async def load_workflow(self, user_id: int) -> TaskWorkflow | None:
        """读取用户最近一次保存的工作流。"""

        checkpoint = await self.get_checkpoint_model(user_id)
        if checkpoint is None:
            return None
        return self.parse_workflow(checkpoint.workflow_data, user_id=user_id, trace_id=checkpoint.trace_id)

    async def load_pending_workflow(self, user_id: int) -> TaskWorkflow | None:
        """读取仍处于待确认状态的工作流。"""

        checkpoint = await self.get_checkpoint_model(user_id)
        if checkpoint is None or checkpoint.status != "needs_confirm":
            return None
        workflow = self.parse_workflow(checkpoint.workflow_data, user_id=user_id, trace_id=checkpoint.trace_id)
        if workflow is None or not workflow.need_confirm:
            return None
        return workflow

    async def save_workflow(self, user_id: int, workflow: TaskWorkflow) -> AgentWorkflowCheckpoint | None:
        """更新用户最近一次工作流检查点。"""

        payload = serialize_workflow(workflow)
        try:
            async with get_session() as session:
                checkpoint = await session.scalar(
                    select(AgentWorkflowCheckpoint).where(AgentWorkflowCheckpoint.user_id == user_id)
                )
                if checkpoint is None:
                    checkpoint = AgentWorkflowCheckpoint(
                        user_id=user_id,
                        trace_id=workflow.trace_id,
                        kind=workflow.kind,
                        status=workflow.status,
                        goal=workflow.goal,
                        summary=workflow.summary,
                        playbook_id=workflow.playbook_id,
                        playbook_name=workflow.playbook_name,
                        workflow_data=payload,
                    )
                    session.add(checkpoint)
                else:
                    checkpoint.trace_id = workflow.trace_id
                    checkpoint.kind = workflow.kind
                    checkpoint.status = workflow.status
                    checkpoint.goal = workflow.goal
                    checkpoint.summary = workflow.summary
                    checkpoint.playbook_id = workflow.playbook_id
                    checkpoint.playbook_name = workflow.playbook_name
                    checkpoint.workflow_data = payload
                await session.commit()
                await session.refresh(checkpoint)
                return checkpoint
        except SQLAlchemyError as error:
            logger.warning(f"AutoGPT workflow checkpoint save skipped for user {user_id}: {error}")
            return None

    async def clear(self, user_id: int) -> None:
        """删除用户最近一次工作流检查点。"""

        try:
            async with get_session() as session:
                checkpoint = await session.scalar(
                    select(AgentWorkflowCheckpoint).where(AgentWorkflowCheckpoint.user_id == user_id)
                )
                if checkpoint is None:
                    return
                await session.delete(checkpoint)
                await session.commit()
        except SQLAlchemyError as error:
            logger.warning(f"AutoGPT workflow checkpoint clear skipped for user {user_id}: {error}")

    async def get_checkpoint_model(self, user_id: int) -> AgentWorkflowCheckpoint | None:
        """按用户读取最新检查点。"""

        try:
            async with get_session() as session:
                return await session.scalar(
                    select(AgentWorkflowCheckpoint).where(AgentWorkflowCheckpoint.user_id == user_id)
                )
        except SQLAlchemyError as error:
            logger.warning(f"AutoGPT workflow checkpoint load skipped for user {user_id}: {error}")
            return None

    @staticmethod
    def parse_workflow(payload: dict, user_id: int, trace_id: str) -> TaskWorkflow | None:
        """从 JSON 快照恢复工作流对象。"""

        try:
            return TaskWorkflow.model_validate(payload)
        except Exception as error:
            logger.warning(
                'AutoGPT workflow checkpoint parse failed for user {} trace "{}": {}'.format(
                    user_id,
                    trace_id,
                    error,
                )
            )
            return None
