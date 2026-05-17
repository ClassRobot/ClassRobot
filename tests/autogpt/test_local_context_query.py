import pytest
from datetime import datetime, timedelta


def build_helpers_with_self_info():
    """构造包含“我的信息”的最小命令目录。"""

    from utils.helper import HelperScope, Helpers, UserRole
    from tests.autogpt.command_tool_helpers import ensure_service_helper

    helpers = Helpers()
    helpers.append(
        ensure_service_helper(
            "我的信息",
            "查看自己的账号信息、当前角色、是否为管理员、是否为教师或学生",
            aliases={"个人信息", "用户信息"},
            roles={UserRole.user},
            scopes={HelperScope.user},
        )
    )
    return helpers


def build_helpers_with_local_queries():
    """构造常见本地状态查询命令目录。"""

    from utils.helper import HelperScope, Helpers, UserRole
    from tests.autogpt.command_tool_helpers import ensure_service_helper

    helpers = Helpers()
    helpers.extend(
        [
            ensure_service_helper(
                "我的信息",
                "查看自己的账号信息、当前角色、是否为管理员、是否为教师或学生",
                aliases={"个人信息", "用户信息"},
                roles={UserRole.user},
                scopes={HelperScope.user},
            ),
            ensure_service_helper(
                "查询班级",
                "查询自己管理的班级",
                aliases={"我的班级", "班级列表"},
                roles={UserRole.teacher},
                scopes={HelperScope.teacher},
            ),
            ensure_service_helper(
                "查询课表",
                "查询本人课表",
                aliases={"我的课表", "查看课表"},
                roles={UserRole.user},
                scopes={HelperScope.user},
            ),
        ]
    )
    return helpers


@pytest.mark.asyncio
async def test_self_admin_query_routes_to_self_info_command_without_llm(loaded_plugins, monkeypatch):
    from core.llm.message import Content, Messages
    from core.agent.runtime import pipeline as pipeline_module
    from core.agent.runtime.schema import ChatMessage

    async def fail_client_create(*args, **kwargs):
        raise AssertionError("self identity queries should use local command routing before LLM planning")

    monkeypatch.setattr(pipeline_module, "client_create", fail_client_create)

    pipeline = pipeline_module.MessageProcessingPipeline(
        build_helpers_with_self_info(),
        Messages(),
        trace_id="self-admin-query",
    )

    result = await pipeline.process(ChatMessage(message=[Content(type="text", value="我的身份是管理员吗")]))

    assert result.route is not None
    assert result.route.intent == "command"
    assert result.route.requires_command is True
    assert result.route.requires_rag is False
    assert result.auto_tasks is not None
    assert result.auto_tasks.need_confirm is False
    assert [task.command for task in result.auto_tasks.tasks] == ["我的信息"]


def test_self_identity_query_does_not_match_mutating_requests(loaded_plugins):
    from core.llm.message import Content
    from core.agent.runtime.pipeline import MessageProcessingPipeline

    assert MessageProcessingPipeline.is_self_identity_query([Content(type="text", value="我想成为管理员")]) is False
    assert MessageProcessingPipeline.is_self_identity_query([Content(type="text", value="我的身份是管理员吗")]) is True


@pytest.mark.asyncio
async def test_owned_class_query_routes_to_query_class_without_llm(loaded_plugins, monkeypatch):
    from core.llm.message import Content, Messages
    from core.agent.runtime import pipeline as pipeline_module
    from core.agent.runtime.schema import ChatMessage

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
    from core.llm.message import Content, Messages
    from core.agent.runtime import pipeline as pipeline_module
    from core.agent.runtime.schema import ChatMessage

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
    from core.llm.message import Content, Messages
    from core.agent.runtime import pipeline as pipeline_module
    from core.agent.runtime.schema import ChatMessage

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
    from core.llm.message import Content, Messages
    from core.agent.runtime import pipeline as pipeline_module
    from core.agent.runtime.schema import ChatMessage

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


def test_local_chat_statistics_query_only_matches_self_or_current_group(loaded_plugins):
    from core.agent.runtime.pipeline import MessageProcessingPipeline

    self_query = MessageProcessingPipeline.parse_local_chat_statistics_query("我们聊了几条消息")
    group_query = MessageProcessingPipeline.parse_local_chat_statistics_query("这个群今天聊了多少条消息")

    assert self_query is not None
    assert self_query.scope == "user"
    assert group_query is not None
    assert group_query.scope == "group"
    assert MessageProcessingPipeline.parse_local_chat_statistics_query("张三和你聊了几条消息") is None
    assert MessageProcessingPipeline.parse_local_chat_statistics_query("别人今天聊了多少条消息") is None


@pytest.mark.asyncio
async def test_user_chat_statistics_query_routes_to_local_summary_without_llm(loaded_plugins, monkeypatch, tmp_path):
    from core.storage import ChatHistoryStore, MessageActorRole, StorageManager
    from core.llm.message import Content, Messages
    from core.agent.runtime import pipeline as pipeline_module
    from core.agent.runtime.knowledge import RuntimeContext
    from core.agent.runtime.schema import ChatMessage

    async def fail_client_create(*args, **kwargs):
        raise AssertionError("chat statistics queries should use deterministic local summaries before LLM planning")

    monkeypatch.setattr(pipeline_module, "client_create", fail_client_create)

    store = ChatHistoryStore(StorageManager(tmp_path / "storage"))
    now = datetime.now().replace(microsecond=0)

    await store.record_user_chat_message(
        user_id="42",
        user_name="测试用户",
        plain_text="你好",
        raw_text="你好",
        message_id="u1",
        actor_role=MessageActorRole.user,
        created_at=now - timedelta(minutes=3),
    )
    await store.record_user_chat_message(
        user_id="42",
        user_name="测试用户",
        plain_text="你好，我在",
        raw_text="你好，我在",
        message_id="a1",
        actor_role=MessageActorRole.assistant,
        actor_id="bot-1",
        actor_name="机器人",
        created_at=now - timedelta(minutes=2),
    )
    await store.record_user_chat_message(
        user_id="99",
        user_name="其他用户",
        plain_text="别人的聊天",
        raw_text="别人的聊天",
        message_id="other-user-message",
        actor_role=MessageActorRole.user,
        created_at=now - timedelta(minutes=2),
    )
    await store.record_user_chat_message(
        user_id="42",
        user_name="测试用户",
        plain_text="我们聊了几条消息",
        raw_text="我们聊了几条消息",
        message_id="ask",
        actor_role=MessageActorRole.user,
        created_at=now - timedelta(minutes=1),
    )

    pipeline = pipeline_module.MessageProcessingPipeline(
        build_helpers_with_local_queries(),
        Messages(),
        trace_id="user-chat-statistics",
        runtime_context=RuntimeContext(user_id=42, message_id="ask"),
        chat_store=store,
    )

    result = await pipeline.process(ChatMessage(message=[Content(type="text", value="我们聊了几条消息")]))

    assert result.route is not None
    assert result.route.intent == "knowledge"
    assert result.auto_tasks is not None
    assert result.auto_tasks.tasks == []
    assert (
        result.auto_tasks.reply == "按当前保存的聊天记录统计，我们一共聊了 2 条消息。其中你发了 1 条，我回复了 1 条。"
    )


@pytest.mark.asyncio
async def test_group_chat_statistics_query_only_reads_current_group_without_llm(
    loaded_plugins,
    monkeypatch,
    tmp_path,
):
    from core.storage import ChatHistoryStore, StorageManager
    from core.llm.message import Content, Messages
    from core.agent.runtime import pipeline as pipeline_module
    from core.agent.runtime.knowledge import RuntimeContext
    from core.agent.runtime.schema import ChatMessage

    async def fail_client_create(*args, **kwargs):
        raise AssertionError(
            "group chat statistics queries should use deterministic local summaries before LLM planning"
        )

    monkeypatch.setattr(pipeline_module, "client_create", fail_client_create)

    store = ChatHistoryStore(StorageManager(tmp_path / "storage"))
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    store._record_group_message_sync(
        "group-1",
        "u1",
        "张三",
        "第一条群消息",
        "第一条群消息",
        "g1",
        today + timedelta(hours=8),
    )
    store._record_group_message_sync(
        "group-1",
        "u2",
        "李四",
        "第二条群消息",
        "第二条群消息",
        "g2",
        today + timedelta(hours=9),
    )
    store._record_group_message_sync(
        "group-1",
        "u1",
        "张三",
        "这个群今天聊了多少条消息",
        "这个群今天聊了多少条消息",
        "ask",
        today + timedelta(hours=10),
    )
    store._record_group_message_sync(
        "group-2",
        "u9",
        "隔壁群用户",
        "不应该被统计进来",
        "不应该被统计进来",
        "other-group",
        today + timedelta(hours=10),
    )

    pipeline = pipeline_module.MessageProcessingPipeline(
        build_helpers_with_local_queries(),
        Messages(),
        trace_id="group-chat-statistics",
        runtime_context=RuntimeContext(
            user_id=42,
            group_id="group-1",
            channel_id="channel-1",
            message_id="ask",
        ),
        chat_store=store,
    )

    result = await pipeline.process(ChatMessage(message=[Content(type="text", value="这个群今天聊了多少条消息")]))

    assert result.route is not None
    assert result.route.intent == "knowledge"
    assert result.auto_tasks is not None
    assert result.auto_tasks.tasks == []
    assert result.auto_tasks.reply == "按今天的群聊记录统计，这个群一共聊了 2 条消息。 共有 2 位成员发过言。"
