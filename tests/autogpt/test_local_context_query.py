import pytest


def build_helpers_with_self_info():
    """构造包含“我的信息”的最小命令目录。"""

    from utils.helper import Helper, HelperScope, Helpers, UserRole

    helpers = Helpers()
    helpers.extend(
        [
            Helper(
                command="我的信息",
                description="查看自己的账号信息、当前角色、是否为管理员、是否为教师或学生",
                aliases={"个人信息", "用户信息"},
                roles={UserRole.user},
                scopes={HelperScope.user},
            )
        ]
    )
    return helpers


def build_helpers_with_local_queries():
    """构造常见本地状态查询命令目录。"""

    from utils.helper import Helper, HelperScope, Helpers, UserRole

    helpers = Helpers()
    helpers.extend(
        [
            Helper(
                command="我的信息",
                description="查看自己的账号信息、当前角色、是否为管理员、是否为教师或学生",
                aliases={"个人信息", "用户信息"},
                roles={UserRole.user},
                scopes={HelperScope.user},
            ),
            Helper(
                command="查询班级",
                description="查询自己管理的班级",
                aliases={"我的班级", "班级列表"},
                roles={UserRole.teacher},
                scopes={HelperScope.teacher},
            ),
            Helper(
                command="查询课表",
                description="查询本人课表",
                aliases={"我的课表", "查看课表"},
                roles={UserRole.user},
                scopes={HelperScope.user},
            ),
        ]
    )
    return helpers


@pytest.mark.asyncio
async def test_self_admin_query_routes_to_self_info_command_without_llm(loaded_plugins, monkeypatch):
    from utils.llm.message import Content, Messages
    from src.plugins.autogpt import pipeline as pipeline_module
    from src.plugins.autogpt.schema import ChatMessage

    async def fail_client_create(*args, **kwargs):
        raise AssertionError("self identity queries should use local command routing before LLM planning")

    monkeypatch.setattr(pipeline_module, "client_create", fail_client_create)

    pipeline = pipeline_module.MessageProcessingPipeline(
        build_helpers_with_self_info(),
        Messages(),
        trace_id="self-admin-query",
    )

    result = await pipeline.process(
        ChatMessage(message=[Content(type="text", value="我的身份是管理员吗")])
    )

    assert result.route is not None
    assert result.route.intent == "command"
    assert result.route.requires_command is True
    assert result.route.requires_rag is False
    assert result.auto_tasks is not None
    assert result.auto_tasks.need_confirm is False
    assert [task.command for task in result.auto_tasks.tasks] == ["我的信息"]


def test_self_identity_query_does_not_match_mutating_requests(loaded_plugins):
    from utils.llm.message import Content
    from src.plugins.autogpt.pipeline import MessageProcessingPipeline

    assert MessageProcessingPipeline.is_self_identity_query(
        [Content(type="text", value="我想成为管理员")]
    ) is False
    assert MessageProcessingPipeline.is_self_identity_query(
        [Content(type="text", value="我的身份是管理员吗")]
    ) is True


@pytest.mark.asyncio
async def test_owned_class_query_routes_to_query_class_without_llm(loaded_plugins, monkeypatch):
    from utils.llm.message import Content, Messages
    from src.plugins.autogpt import pipeline as pipeline_module
    from src.plugins.autogpt.schema import ChatMessage

    async def fail_client_create(*args, **kwargs):
        raise AssertionError("local class queries should use deterministic command routing")

    monkeypatch.setattr(pipeline_module, "client_create", fail_client_create)

    pipeline = pipeline_module.MessageProcessingPipeline(
        build_helpers_with_local_queries(),
        Messages(),
        trace_id="owned-class-query",
    )

    result = await pipeline.process(ChatMessage(message=[Content(type="text", value="我有创建班级吗")]))

    assert result.auto_tasks is not None
    assert result.auto_tasks.need_confirm is False
    assert [task.command for task in result.auto_tasks.tasks] == ["查询班级"]


@pytest.mark.asyncio
async def test_class_membership_query_routes_to_self_info_without_llm(loaded_plugins, monkeypatch):
    from utils.llm.message import Content, Messages
    from src.plugins.autogpt import pipeline as pipeline_module
    from src.plugins.autogpt.schema import ChatMessage

    async def fail_client_create(*args, **kwargs):
        raise AssertionError("class membership queries should use deterministic command routing")

    monkeypatch.setattr(pipeline_module, "client_create", fail_client_create)

    pipeline = pipeline_module.MessageProcessingPipeline(
        build_helpers_with_local_queries(),
        Messages(),
        trace_id="class-membership-query",
    )

    result = await pipeline.process(ChatMessage(message=[Content(type="text", value="我现在在哪个班级")]))

    assert result.auto_tasks is not None
    assert [task.command for task in result.auto_tasks.tasks] == ["我的信息"]


@pytest.mark.asyncio
async def test_schedule_query_routes_to_query_curriculum_with_day_offset_without_llm(loaded_plugins, monkeypatch):
    from utils.llm.message import Content, Messages
    from src.plugins.autogpt import pipeline as pipeline_module
    from src.plugins.autogpt.schema import ChatMessage

    async def fail_client_create(*args, **kwargs):
        raise AssertionError("schedule queries should use deterministic command routing")

    monkeypatch.setattr(pipeline_module, "client_create", fail_client_create)

    pipeline = pipeline_module.MessageProcessingPipeline(
        build_helpers_with_local_queries(),
        Messages(),
        trace_id="schedule-query",
    )

    result = await pipeline.process(ChatMessage(message=[Content(type="text", value="我明天有什么课")]))

    assert result.auto_tasks is not None
    assert [task.command for task in result.auto_tasks.tasks] == ["查询课表"]
    assert [param.value for param in result.auto_tasks.tasks[0].params] == ["1"]


@pytest.mark.asyncio
async def test_short_local_query_aliases_route_without_llm(loaded_plugins, monkeypatch):
    from utils.llm.message import Content, Messages
    from src.plugins.autogpt import pipeline as pipeline_module
    from src.plugins.autogpt.schema import ChatMessage

    async def fail_client_create(*args, **kwargs):
        raise AssertionError("short local query aliases should use deterministic command routing")

    monkeypatch.setattr(pipeline_module, "client_create", fail_client_create)

    class_pipeline = pipeline_module.MessageProcessingPipeline(
        build_helpers_with_local_queries(),
        Messages(),
        trace_id="short-class-query",
    )
    class_result = await class_pipeline.process(ChatMessage(message=[Content(type="text", value="我的班级")]))

    schedule_pipeline = pipeline_module.MessageProcessingPipeline(
        build_helpers_with_local_queries(),
        Messages(),
        trace_id="short-schedule-query",
    )
    schedule_result = await schedule_pipeline.process(ChatMessage(message=[Content(type="text", value="我的课表")]))

    assert class_result.auto_tasks is not None
    assert [task.command for task in class_result.auto_tasks.tasks] == ["查询班级"]
    assert schedule_result.auto_tasks is not None
    assert [task.command for task in schedule_result.auto_tasks.tasks] == ["查询课表"]
