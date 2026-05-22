import pytest_asyncio
from sqlalchemy import delete


@pytest_asyncio.fixture
async def workflow_checkpoint_table(loaded_plugins):
    """为需要持久化校验的 AutoGPT 测试准备工作流状态表。"""

    from nonebot_plugin_orm import get_session
    from src.models.models import AgentWorkflowCheckpoint, AgentWorkflowRun

    async with get_session() as session:
        bind = session.bind
        assert bind is not None

    async with bind.begin() as connection:
        await connection.run_sync(AgentWorkflowCheckpoint.__table__.create, checkfirst=True)
        await connection.run_sync(AgentWorkflowRun.__table__.create, checkfirst=True)

    async with get_session() as session:
        await session.execute(delete(AgentWorkflowCheckpoint))
        await session.execute(delete(AgentWorkflowRun))
        await session.commit()

    yield

    async with get_session() as session:
        await session.execute(delete(AgentWorkflowCheckpoint))
        await session.execute(delete(AgentWorkflowRun))
        await session.commit()
