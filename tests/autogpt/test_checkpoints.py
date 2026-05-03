import pytest


@pytest.mark.asyncio
async def test_workflow_checkpoint_store_roundtrip(loaded_plugins, workflow_checkpoint_table):
    from src.plugins.autogpt.checkpoints import WorkflowCheckpointStore
    from src.plugins.autogpt.schema import AgentWorkflow, WorkflowStep

    store = WorkflowCheckpointStore()
    workflow = AgentWorkflow(
        trace_id="autogpt-persist",
        kind="command_sequence",
        status="needs_confirm",
        goal="创建任务并通知",
        summary="命中工作流模板：创建任务并通知。",
        playbook_id="task_publish_and_notify",
        playbook_name="创建任务并通知",
        need_confirm=True,
        steps=[
            WorkflowStep(step_id="step-1", title="创建任务", command="创建任务"),
            WorkflowStep(step_id="step-2", title="发送任务通知", command="创建通知"),
        ],
    )
    workflow.add_event("workflow_created", "本轮消息已提升为显式工作流。", status="needs_confirm")
    workflow.add_event("approval_requested", "当前任务在执行前需要用户确认。", status="pending")

    await store.save_workflow(user_id=7, workflow=workflow)
    restored = await store.load_pending_workflow(user_id=7)

    assert restored is not None
    assert restored.trace_id == "autogpt-persist"
    assert restored.status == "needs_confirm"
    assert restored.playbook_id == "task_publish_and_notify"
    assert [step.command for step in restored.steps] == ["创建任务", "创建通知"]


@pytest.mark.asyncio
async def test_chat_session_restores_pending_workflow_from_checkpoint(loaded_plugins, workflow_checkpoint_table):
    from utils.helper import Helpers
    from src.plugins.autogpt.util import ChatSession
    from src.plugins.autogpt.schema import AgentWorkflow, WorkflowStep

    first_session = ChatSession(user_id=9, helpers=Helpers())
    workflow = AgentWorkflow(
        trace_id="autogpt-restore",
        kind="command",
        status="needs_confirm",
        goal="删除请假",
        need_confirm=True,
        steps=[WorkflowStep(step_id="step-1", title="删除请假", command="删除请假")],
    )
    workflow.add_event("workflow_created", "本轮消息已提升为显式工作流。", status="needs_confirm")
    workflow.add_event("approval_requested", "当前任务在执行前需要用户确认。", status="pending")
    await first_session.record_workflow(workflow, trace_id="autogpt-restore")

    second_session = ChatSession(user_id=9, helpers=Helpers())
    restored = await second_session.restore_pending_workflow()

    assert restored is not None
    assert second_session.pending_workflow is not None
    assert second_session.pending_workflow.trace_id == "autogpt-restore"
    assert (
        second_session.messages.messages[-1].single_modal().startswith("# 系统工作流状态\ntrace_id: autogpt-restore\n")
    )
    assert [event.event_type for event in second_session.pending_workflow.events] == [
        "workflow_created",
        "approval_requested",
    ]


@pytest.mark.asyncio
async def test_confirming_restored_workflow_updates_checkpoint(loaded_plugins, workflow_checkpoint_table):
    from utils.helper import Helpers
    from src.plugins.autogpt.util import ChatSession
    from src.plugins.autogpt.checkpoints import WorkflowCheckpointStore
    from src.plugins.autogpt.schema import AgentWorkflow, WorkflowStep

    pending_session = ChatSession(user_id=12, helpers=Helpers())
    workflow = AgentWorkflow(
        trace_id="autogpt-pending",
        kind="command_sequence",
        status="needs_confirm",
        goal="创建任务并通知",
        need_confirm=True,
        steps=[
            WorkflowStep(step_id="step-1", title="创建任务", command="创建任务"),
            WorkflowStep(step_id="step-2", title="发送任务通知", command="创建通知"),
        ],
    )
    workflow.add_event("workflow_created", "本轮消息已提升为显式工作流。", status="needs_confirm")
    workflow.add_event("approval_requested", "当前任务在执行前需要用户确认。", status="pending")
    await pending_session.record_workflow(workflow, trace_id="autogpt-pending")

    resumed_session = ChatSession(user_id=12, helpers=Helpers())
    await resumed_session.restore_pending_workflow()
    turn_result = await resumed_session.resolve_pending_workflow_action("确认执行", trace_id="autogpt-resumed")
    persisted = await WorkflowCheckpointStore().load_workflow(user_id=12)

    assert turn_result is not None
    assert turn_result.workflow is not None
    assert persisted is not None
    assert persisted.trace_id == "autogpt-resumed"
    assert persisted.status == "planned"
    assert persisted.need_confirm is False


@pytest.mark.asyncio
async def test_clearing_session_removes_persisted_checkpoint(loaded_plugins, workflow_checkpoint_table):
    from utils.helper import Helpers
    from src.plugins.autogpt.util import ChatSession
    from src.plugins.autogpt.checkpoints import WorkflowCheckpointStore
    from src.plugins.autogpt.schema import AgentWorkflow, WorkflowStep

    session = ChatSession(user_id=20, helpers=Helpers())
    workflow = AgentWorkflow(
        trace_id="autogpt-clear",
        kind="command",
        status="needs_confirm",
        goal="删除请假",
        need_confirm=True,
        steps=[WorkflowStep(step_id="step-1", title="删除请假", command="删除请假")],
    )
    workflow.add_event("workflow_created", "本轮消息已提升为显式工作流。", status="needs_confirm")
    workflow.add_event("approval_requested", "当前任务在执行前需要用户确认。", status="pending")
    await session.record_workflow(workflow, trace_id="autogpt-clear")
    await session.clear()

    restored = await WorkflowCheckpointStore().load_workflow(user_id=20)

    assert restored is None
