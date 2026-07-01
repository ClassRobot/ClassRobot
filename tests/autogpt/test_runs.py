import pytest


@pytest.mark.asyncio
async def test_workflow_run_store_roundtrip(loaded_plugins, workflow_checkpoint_table):
    from src.core.agent.runtime.persistence import WorkflowRunStore
    from src.core.agent.runtime.schema import TaskWorkflow, WorkflowStep, WorkflowApproval

    store = WorkflowRunStore()
    workflow = TaskWorkflow(
        trace_id="autogpt-run",
        source_trace_id="autogpt-parent",
        kind="command_sequence",
        status="planned",
        goal="创建任务并通知",
        summary="命中工作流模板：创建任务并通知。",
        playbook_id="task_publish_and_notify",
        playbook_name="创建任务并通知",
        approval=WorkflowApproval(
            required=True,
            type="high_risk",
            status="approved",
            reason="该任务包含高风险步骤，执行前需要用户确认。",
            prompt="确认执行吗？",
            risk_level="high",
        ),
        steps=[
            WorkflowStep(step_id="step-1", title="创建任务", command="创建任务"),
            WorkflowStep(step_id="step-2", title="发送任务通知", command="创建通知"),
        ],
    )
    workflow.add_event("workflow_created", "本轮消息已提升为显式工作流。", status="planned")
    workflow.add_event("approval_requested", "该任务包含高风险步骤，执行前需要用户确认。", status="approved")

    await store.save_run(user_id=100, workflow=workflow)
    persisted = await store.get_run("autogpt-run")

    assert persisted is not None
    assert persisted.source_trace_id == "autogpt-parent"
    assert persisted.approval_type == "high_risk"
    assert persisted.approval_status == "approved"
    assert persisted.playbook_id == "task_publish_and_notify"
    assert persisted.workflow_data["events"][0]["event_type"] == "workflow_created"


@pytest.mark.asyncio
async def test_resumed_workflow_saves_parent_child_run_history(loaded_plugins, workflow_checkpoint_table):
    from src.platform.helper import Helpers
    from src.core.agent.runtime.util import ChatSession
    from src.core.agent.runtime.persistence import WorkflowRunStore
    from src.core.agent.runtime.schema import TaskWorkflow, WorkflowStep, WorkflowApproval

    pending_session = ChatSession(user_id=102, helpers=Helpers())
    workflow = TaskWorkflow(
        trace_id="autogpt-parent",
        kind="command_sequence",
        status="needs_confirm",
        goal="创建任务并通知",
        need_confirm=True,
        approval=WorkflowApproval(
            required=True,
            type="high_risk",
            status="pending",
            reason="该任务包含高风险步骤，执行前需要用户确认。",
            prompt="确认执行吗？",
            risk_level="high",
        ),
        steps=[
            WorkflowStep(step_id="step-1", title="创建任务", command="创建任务"),
            WorkflowStep(step_id="step-2", title="发送任务通知", command="创建通知"),
        ],
    )
    workflow.add_event("workflow_created", "本轮消息已提升为显式工作流。", status="needs_confirm")
    workflow.add_event("approval_requested", "该任务包含高风险步骤，执行前需要用户确认。", status="pending")
    await pending_session.record_workflow(workflow, trace_id="autogpt-parent")

    resumed_session = ChatSession(user_id=102, helpers=Helpers())
    await resumed_session.restore_pending_workflow()
    turn_result = await resumed_session.resolve_pending_workflow_action("确认执行", trace_id="autogpt-child")
    runs = await WorkflowRunStore().list_runs(user_id=102)

    assert turn_result is not None
    assert turn_result.workflow is not None
    assert len(runs) == 2
    child_run = next(run for run in runs if run.trace_id == "autogpt-child")
    parent_run = next(run for run in runs if run.trace_id == "autogpt-parent")
    assert child_run.source_trace_id == "autogpt-parent"
    assert child_run.approval_status == "approved"
    assert parent_run.status == "needs_confirm"
    assert child_run.workflow_data["events"][-1]["event_type"] == "workflow_resumed"


@pytest.mark.asyncio
async def test_cancelling_pending_workflow_updates_existing_run(loaded_plugins, workflow_checkpoint_table):
    from src.platform.helper import Helpers
    from src.core.agent.runtime.util import ChatSession
    from src.core.agent.runtime.persistence import WorkflowRunStore
    from src.core.agent.runtime.schema import TaskWorkflow, WorkflowStep, WorkflowApproval

    session = ChatSession(user_id=103, helpers=Helpers())
    workflow = TaskWorkflow(
        trace_id="autogpt-cancel-parent",
        kind="command",
        status="needs_confirm",
        goal="删除请假",
        need_confirm=True,
        approval=WorkflowApproval(
            required=True,
            type="user_confirm",
            status="pending",
            reason="当前任务在执行前需要用户确认。",
            prompt="确认删除吗？",
            risk_level="medium",
        ),
        steps=[WorkflowStep(step_id="step-1", title="删除请假", command="删除请假")],
    )
    workflow.add_event("workflow_created", "本轮消息已提升为显式工作流。", status="needs_confirm")
    workflow.add_event("approval_requested", "当前任务在执行前需要用户确认。", status="pending")
    await session.record_workflow(workflow, trace_id="autogpt-cancel-parent")
    await session.resolve_pending_workflow_action("取消", trace_id="autogpt-cancel-message")
    runs = await WorkflowRunStore().list_runs(user_id=103)

    assert len(runs) == 1
    assert runs[0].trace_id == "autogpt-cancel-parent"
    assert runs[0].status == "cancelled"
    assert runs[0].approval_status == "rejected"
    assert runs[0].workflow_data["events"][-1]["event_type"] == "workflow_cancelled"
