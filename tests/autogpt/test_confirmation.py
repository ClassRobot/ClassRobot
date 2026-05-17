import pytest


@pytest.mark.asyncio
async def test_confirm_message_resumes_pending_workflow(loaded_plugins):
    from utils.helper import Helpers
    from core.agent.runtime.util import ChatSession
    from core.agent.runtime.schema import TaskWorkflow, WorkflowApproval, WorkflowStep

    session = ChatSession(user_id=1, helpers=Helpers())
    workflow = TaskWorkflow(
        trace_id="autogpt-pending",
        kind="command_sequence",
        status="needs_confirm",
        goal="创建任务并通知",
        need_confirm=True,
        approval=WorkflowApproval(required=True, type="user_confirm", status="pending"),
        steps=[
            WorkflowStep(step_id="step-1", title="创建任务", command="创建任务"),
            WorkflowStep(step_id="step-2", title="发送任务通知", command="创建通知"),
        ],
    )
    workflow.add_event("workflow_created", "本轮消息已提升为显式工作流。", status="needs_confirm")
    workflow.add_event("approval_requested", "当前任务在执行前需要用户确认。", status="pending")
    await session.record_workflow(workflow, trace_id="autogpt-pending")

    turn_result = await session.resolve_pending_workflow_action("确认执行", trace_id="autogpt-resume")

    assert turn_result is not None
    assert turn_result.workflow is not None
    assert turn_result.workflow.trace_id == "autogpt-resume"
    assert turn_result.workflow.status == "planned"
    assert turn_result.workflow.need_confirm is False
    assert [event.event_type for event in turn_result.workflow.events] == [
        "workflow_created",
        "approval_requested",
        "approval_approved",
        "workflow_resumed",
    ]
    assert turn_result.auto_tasks is not None
    assert [task.command for task in turn_result.auto_tasks.tasks] == ["创建任务", "创建通知"]
    assert session.pending_workflow is None


@pytest.mark.asyncio
async def test_cancel_message_clears_pending_workflow(loaded_plugins):
    from utils.helper import Helpers
    from core.agent.runtime.util import ChatSession
    from core.agent.runtime.schema import TaskWorkflow, WorkflowApproval, WorkflowStep

    session = ChatSession(user_id=1, helpers=Helpers())
    workflow = TaskWorkflow(
        trace_id="autogpt-pending",
        kind="command",
        status="needs_confirm",
        goal="删除请假",
        need_confirm=True,
        approval=WorkflowApproval(required=True, type="user_confirm", status="pending"),
        steps=[WorkflowStep(step_id="step-1", title="删除请假", command="删除请假")],
    )
    workflow.add_event("workflow_created", "本轮消息已提升为显式工作流。", status="needs_confirm")
    workflow.add_event("approval_requested", "当前任务在执行前需要用户确认。", status="pending")
    await session.record_workflow(workflow, trace_id="autogpt-pending")

    turn_result = await session.resolve_pending_workflow_action("取消", trace_id="autogpt-cancel")

    assert turn_result is not None
    assert turn_result.workflow is None
    assert turn_result.auto_tasks is not None
    assert turn_result.auto_tasks.reply == "已取消上一条待确认任务。"
    assert session.pending_workflow is None
    assert session.last_workflow is not None
    assert session.last_workflow.status == "cancelled"
    assert [event.event_type for event in session.last_workflow.events] == [
        "workflow_created",
        "approval_requested",
        "approval_rejected",
        "workflow_cancelled",
    ]


@pytest.mark.asyncio
async def test_non_decision_text_keeps_pending_workflow_for_followup(loaded_plugins):
    from utils.helper import Helpers
    from core.agent.runtime.util import ChatSession
    from core.agent.runtime.schema import TaskWorkflow, WorkflowApproval, WorkflowStep

    session = ChatSession(user_id=1, helpers=Helpers())
    workflow = TaskWorkflow(
        trace_id="autogpt-pending",
        kind="command",
        status="needs_confirm",
        goal="删除请假",
        need_confirm=True,
        approval=WorkflowApproval(required=True, type="user_confirm", status="pending"),
        steps=[WorkflowStep(step_id="step-1", title="删除请假", command="删除请假")],
    )
    workflow.add_event("workflow_created", "本轮消息已提升为显式工作流。", status="needs_confirm")
    workflow.add_event("approval_requested", "当前任务在执行前需要用户确认。", status="pending")
    await session.record_workflow(workflow, trace_id="autogpt-pending")

    turn_result = await session.resolve_pending_workflow_action(
        "请帮我先看一下这条请假记录",
        trace_id="autogpt-followup",
    )

    assert turn_result is None
    assert session.pending_workflow is not None
