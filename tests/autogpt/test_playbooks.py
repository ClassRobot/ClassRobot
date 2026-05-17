def test_workflow_builder_matches_builtin_playbook(loaded_plugins):
    from utils.helper import Helper, Helpers
    from core.agent.runtime.schema import AutoTask, AutoTaskList, Param
    from core.agent.runtime.command_tools import CommandToolCatalog
    from core.agent.runtime.workflow import WorkflowBuilder

    helpers = Helpers()
    helpers.append(Helper(command="创建任务", description="创建一个班级任务"))
    helpers.append(Helper(command="创建通知", description="创建一条通知"))

    workflow = WorkflowBuilder.build(
        trace_id="autogpt-playbook",
        route=None,
        plan=None,
        auto_tasks=AutoTaskList(
            tasks=[
                AutoTask(command="创建任务", params=[Param(type="text", value="数学作业")]),
                AutoTask(command="创建通知", params=[Param(type="text", value="明天交数学作业")]),
            ]
        ),
        command_tools=CommandToolCatalog.from_helpers(helpers),
    )

    assert workflow is not None
    assert workflow.playbook_id == "task_publish_and_notify"
    assert workflow.playbook_name == "创建任务并通知"
    assert workflow.summary == "命中工作流模板：创建任务并通知。"
    assert workflow.steps[0].title == "创建任务"
    assert workflow.steps[1].title == "发送任务通知"


def test_workflow_builder_leaves_playbook_empty_for_unmatched_sequence(loaded_plugins):
    from utils.helper import Helper, Helpers
    from core.agent.runtime.schema import AutoTask, AutoTaskList
    from core.agent.runtime.command_tools import CommandToolCatalog
    from core.agent.runtime.workflow import WorkflowBuilder

    helpers = Helpers()
    helpers.append(Helper(command="查询课表", description="查询当前课表"))

    workflow = WorkflowBuilder.build(
        trace_id="autogpt-no-playbook",
        route=None,
        plan=None,
        auto_tasks=AutoTaskList(tasks=[AutoTask(command="查询课表", params=[])]),
        command_tools=CommandToolCatalog.from_helpers(helpers),
    )

    assert workflow is not None
    assert workflow.playbook_id is None
    assert workflow.playbook_name is None
