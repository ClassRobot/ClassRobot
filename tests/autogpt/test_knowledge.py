from __future__ import annotations

from datetime import datetime

import pytest


def test_skill_catalog_renders_builtin_skill_summaries(loaded_plugins):
    from src.core.agent.runtime.knowledge import SkillCatalog

    prompt = SkillCatalog().to_prompt()

    assert "ocr" in prompt
    assert "markdown-to-image" in prompt
    assert "image-generation" in prompt


def test_skill_catalog_can_render_named_subset(loaded_plugins):
    from src.core.agent.runtime.knowledge import SkillCatalog

    prompt = SkillCatalog().to_prompt(skill_names=["ocr"], limit=1)

    assert "ocr" in prompt
    assert "markdown-to-image" not in prompt
    assert "image-generation" not in prompt


def test_skill_catalog_does_not_filter_by_query(loaded_plugins):
    from src.core.agent.runtime.knowledge import SkillCatalog

    prompt = SkillCatalog().to_prompt()

    assert "ocr" in prompt
    assert "markdown-to-image" in prompt


@pytest.mark.asyncio
async def test_local_knowledge_retriever_reads_user_chat_history(loaded_plugins, tmp_path):
    from src.core.agent.runtime.schema import KnowledgeSourceRequest
    from src.core.storage import StorageManager, ChatHistoryStore, MessageActorRole
    from src.core.agent.runtime.knowledge import RuntimeContext, LocalKnowledgeRetriever

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)
    await store.record_user_chat_message(
        user_id=90001,
        user_name="测试用户",
        plain_text="昨天说过班会材料放在 report.md 里",
        raw_text="昨天说过班会材料放在 report.md 里",
        actor_role=MessageActorRole.user,
        message_id="m1",
        created_at=datetime(2026, 5, 6, 8, 30),
    )

    retriever = LocalKnowledgeRetriever(manager=manager, chat_store=store)
    routed_context = await retriever.retrieve_sources(
        [
            KnowledgeSourceRequest(
                source="user_chat_history",
                query="班会资料 report.md",
                reason="用户询问自己之前聊过的内容",
                required=True,
            )
        ],
        RuntimeContext(user_id=90001),
    )

    assert routed_context is not None
    assert "# 本地知识源检索观察" in routed_context
    assert "## user_chat_history" in routed_context
    assert "status: hit" in routed_context
    assert "班会材料" in routed_context
    assert "scope: private_user" in routed_context
    assert "owner: user:90001" in routed_context


@pytest.mark.asyncio
async def test_local_knowledge_retriever_uses_rag_overlap_recall(loaded_plugins, tmp_path):
    from src.core.agent.runtime.schema import KnowledgeSourceRequest
    from src.core.storage import StorageManager, ChatHistoryStore, MessageActorRole
    from src.core.agent.runtime.knowledge import RuntimeContext, LocalKnowledgeRetriever

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)
    await store.record_user_chat_message(
        user_id=90003,
        user_name="测试用户",
        plain_text="昨天说过班会材料放在 report.md 里",
        raw_text="昨天说过班会材料放在 report.md 里",
        actor_role=MessageActorRole.user,
        message_id="m-rag-1",
        created_at=datetime(2026, 5, 6, 8, 30),
    )

    retriever = LocalKnowledgeRetriever(manager=manager, chat_store=store)
    context = await retriever.retrieve_sources(
        [KnowledgeSourceRequest(source="user_chat_history", query="班会资料", reason="用户追问历史上下文")],
        RuntimeContext(user_id=90003),
    )

    assert context is not None
    assert "本地 RAG" in context
    assert "召回摘要" in context
    assert "班会材料" in context


@pytest.mark.asyncio
async def test_local_knowledge_retriever_keeps_user_chat_history_isolated(loaded_plugins, tmp_path):
    from src.core.agent.runtime.schema import KnowledgeSourceRequest
    from src.core.storage import StorageManager, ChatHistoryStore, MessageActorRole
    from src.core.agent.runtime.knowledge import RuntimeContext, LocalKnowledgeRetriever

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)
    await store.record_user_chat_message(
        user_id=91001,
        user_name="用户A",
        plain_text="奖学金材料放在 scholarship.md",
        raw_text="奖学金材料放在 scholarship.md",
        actor_role=MessageActorRole.user,
        message_id="u-a-1",
        created_at=datetime(2026, 5, 6, 8, 30),
    )
    await store.record_user_chat_message(
        user_id=91002,
        user_name="用户B",
        plain_text="我只聊过食堂菜单。",
        raw_text="我只聊过食堂菜单。",
        actor_role=MessageActorRole.user,
        message_id="u-b-1",
        created_at=datetime(2026, 5, 6, 8, 31),
    )

    retriever = LocalKnowledgeRetriever(manager=manager, chat_store=store)
    context = await retriever.retrieve_sources(
        [KnowledgeSourceRequest(source="user_chat_history", query="奖学金材料", reason="查询历史", required=True)],
        RuntimeContext(user_id=91002, message_id="u-b-current"),
    )

    assert context is not None
    assert "owner: user:91002" in context
    assert "scholarship.md" not in context
    assert "食堂菜单" not in context
    assert "status: miss" in context


@pytest.mark.asyncio
async def test_local_knowledge_retriever_reads_user_file_space(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, ChatHistoryStore
    from src.core.agent.runtime.schema import KnowledgeSourceRequest
    from src.core.agent.runtime.knowledge import RuntimeContext, LocalKnowledgeRetriever

    manager = StorageManager(tmp_path / "storage")
    space = manager.user_space(90002)
    report = space.home_dir / "documents" / "report.md"
    report.write_text("班会材料：周五下午三点开会，带上作业统计。", encoding="utf-8")

    retriever = LocalKnowledgeRetriever(manager=manager, chat_store=ChatHistoryStore(manager))
    routed_context = await retriever.retrieve_sources(
        [KnowledgeSourceRequest(source="user_file_space", query="report", reason="用户询问自己的文件内容")],
        RuntimeContext(user_id=90002),
    )

    assert routed_context is not None
    assert "## user_file_space" in routed_context
    assert "status: hit" in routed_context
    assert "~/documents/report.md" in routed_context


@pytest.mark.asyncio
async def test_local_knowledge_retriever_reads_group_file_space_by_system_group_id(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, ChatHistoryStore
    from src.core.agent.runtime.schema import KnowledgeSourceRequest
    from src.core.agent.runtime.knowledge import RuntimeContext, LocalKnowledgeRetriever

    manager = StorageManager(tmp_path / "storage")
    report = manager.group_space("system-group-92001").home_dir / "documents" / "group-report.md"
    report.write_text("群文件材料：周三晚自习前提交班会记录。", encoding="utf-8")

    retriever = LocalKnowledgeRetriever(manager=manager, chat_store=ChatHistoryStore(manager))
    context = await retriever.retrieve_sources(
        [KnowledgeSourceRequest(source="group_file_space", query="report", reason="用户询问当前群文件")],
        RuntimeContext(
            user_id=90004,
            group_id="system-group-92001",
            platform="onebot11.qq_client",
            channel_id="92001",
        ),
    )

    assert context is not None
    assert "## group_file_space" in context
    assert "status: hit" in context
    assert "群文件空间检索" in context
    assert "~/documents/group-report.md" in context
    assert "群文件材料" in context
    assert not (manager.group_space("92001").home_dir / "documents" / "group-report.md").exists()


@pytest.mark.asyncio
async def test_local_knowledge_retriever_does_not_treat_channel_id_as_system_group_id(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, ChatHistoryStore
    from src.core.agent.runtime.schema import KnowledgeSourceRequest
    from src.core.agent.runtime.knowledge import RuntimeContext, LocalKnowledgeRetriever

    manager = StorageManager(tmp_path / "storage")
    report = manager.group_space("92002").home_dir / "documents" / "channel-only-report.md"
    report.write_text("这份材料只应该在系统群 ID 明确解析后才能读取。", encoding="utf-8")

    retriever = LocalKnowledgeRetriever(manager=manager, chat_store=ChatHistoryStore(manager))
    routed_context = await retriever.retrieve_sources(
        [KnowledgeSourceRequest(source="group_file_space", query="channel only report", reason="用户询问群文件")],
        RuntimeContext(user_id=90005, channel_id="92002"),
    )

    assert routed_context is not None
    assert "## group_file_space" in routed_context
    assert "status: skipped" in routed_context
    assert "channel-only-report.md" not in routed_context


@pytest.mark.asyncio
async def test_local_knowledge_retriever_skips_group_sources_outside_group_context(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, ChatHistoryStore
    from src.core.agent.runtime.schema import KnowledgeSourceRequest
    from src.core.agent.runtime.knowledge import RuntimeContext, LocalKnowledgeRetriever

    manager = StorageManager(tmp_path / "storage")
    retriever = LocalKnowledgeRetriever(manager=manager, chat_store=ChatHistoryStore(manager))

    context = await retriever.retrieve_sources(
        [
            KnowledgeSourceRequest(
                source="group_chat_history",
                query="作业安排",
                reason="用户询问群聊历史",
                required=True,
            )
        ],
        RuntimeContext(user_id=90006),
    )

    assert context is not None
    assert "## group_chat_history" in context
    assert "status: skipped" in context
    assert "不是群聊或频道上下文" in context


@pytest.mark.asyncio
async def test_local_knowledge_retriever_skips_unbound_group_chat_history(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, ChatHistoryStore
    from src.core.agent.runtime.schema import KnowledgeSourceRequest
    from src.core.agent.runtime.knowledge import RuntimeContext, LocalKnowledgeRetriever

    manager = StorageManager(tmp_path / "storage")
    retriever = LocalKnowledgeRetriever(manager=manager, chat_store=ChatHistoryStore(manager))

    context = await retriever.retrieve_sources(
        [
            KnowledgeSourceRequest(
                source="group_chat_history", query="作业安排", reason="用户询问群聊历史", required=True
            )
        ],
        RuntimeContext(user_id=90007, platform="onebot11.qq_client", channel_id="92008", message_id="group-current"),
    )

    assert context is not None
    assert "## group_chat_history" in context
    assert "status: skipped" in context
    assert "未绑定系统群" in context


@pytest.mark.asyncio
async def test_local_knowledge_retriever_group_chat_history_uses_bound_group_contract(loaded_plugins, tmp_path):
    from src.core.agent.runtime.schema import KnowledgeSourceRequest
    from src.core.storage import StorageManager, ChatHistoryStore, MessageActorRole
    from src.core.agent.runtime.knowledge import RuntimeContext, LocalKnowledgeRetriever

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)
    await store.record_group_collect_message(
        group_id="system-group-93001",
        user_id="u1",
        user_name="张三",
        plain_text="今天作业安排是什么",
        raw_text="今天作业安排是什么",
        message_id="group-collect-1",
        created_at=datetime(2026, 5, 6, 8, 30),
    )
    await store.record_group_chat_message(
        group_id="system-group-93001",
        plain_text="今天作业是完成第 3 章习题。",
        raw_text="今天作业是完成第 3 章习题。",
        actor_role=MessageActorRole.assistant,
        actor_id="bot-1",
        actor_name="机器人",
        message_id="group-assistant-1",
        created_at=datetime(2026, 5, 6, 8, 31),
    )
    await store.record_group_chat_message(
        group_id="system-group-93001",
        plain_text="检索群聊记录 作业安排",
        raw_text="检索群聊记录 作业安排",
        actor_role=MessageActorRole.user,
        actor_id="u2",
        actor_name="李四",
        message_id="group-chat-user-1",
        created_at=datetime(2026, 5, 6, 8, 32),
    )

    retriever = LocalKnowledgeRetriever(manager=manager, chat_store=store)
    context = await retriever.retrieve_sources(
        [
            KnowledgeSourceRequest(
                source="group_chat_history", query="作业安排", reason="用户询问群聊历史", required=True
            )
        ],
        RuntimeContext(
            user_id=90008,
            group_id="system-group-93001",
            platform="onebot11.qq_client",
            channel_id="93001",
            message_id="group-current",
        ),
    )

    assert context is not None
    assert "scope: bound_group" in context
    assert "owner: group:system-group-93001" in context
    assert "今天作业安排是什么" in context
    assert "今天作业是完成第 3 章习题" in context
    assert "检索群聊记录 作业安排" not in context


@pytest.mark.asyncio
async def test_local_knowledge_retriever_filters_current_message_from_user_rag(loaded_plugins, tmp_path):
    from src.core.agent.runtime.schema import KnowledgeSourceRequest
    from src.core.storage import StorageManager, ChatHistoryStore, MessageActorRole
    from src.core.agent.runtime.knowledge import RuntimeContext, LocalKnowledgeRetriever

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)
    await store.record_user_chat_message(
        user_id=91003,
        user_name="测试用户",
        plain_text="之前提到奖学金材料在 scholarship.md",
        raw_text="之前提到奖学金材料在 scholarship.md",
        actor_role=MessageActorRole.user,
        message_id="rag-old",
        created_at=datetime(2026, 5, 6, 8, 20),
    )
    await store.record_user_chat_message(
        user_id=91003,
        user_name="测试用户",
        plain_text="我现在这条也提到奖学金材料",
        raw_text="我现在这条也提到奖学金材料",
        actor_role=MessageActorRole.user,
        message_id="rag-current",
        created_at=datetime(2026, 5, 6, 8, 21),
    )

    retriever = LocalKnowledgeRetriever(manager=manager, chat_store=store)
    context = await retriever.retrieve_sources(
        [KnowledgeSourceRequest(source="user_chat_history", query="奖学金材料", reason="查询历史")],
        RuntimeContext(user_id=91003, message_id="rag-current"),
    )

    assert context is not None
    assert "scholarship.md" in context
    assert "我现在这条也提到奖学金材料" not in context


def test_intent_route_accepts_ai_selected_knowledge_sources(loaded_plugins):
    from src.core.agent.runtime.schema import IntentRoute

    route = IntentRoute.model_validate(
        {
            "intent": "knowledge",
            "requires_rag": False,
            "requires_command": False,
            "need_confirm": False,
            "reason": "用户追问之前聊过的信息",
            "knowledge_sources": [
                {
                    "source": "user_chat_history",
                    "query": "之前让我记住的事情",
                    "reason": "需要读取当前用户聊天历史",
                    "required": True,
                }
            ],
        }
    )

    assert route.knowledge_sources[0].source == "user_chat_history"
    assert route.knowledge_sources[0].required is True


def test_external_rag_result_is_wrapped_as_knowledge_observation(loaded_plugins):
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline
    from src.core.agent.runtime.schema import IntentRoute, KnowledgeSourceRequest

    route = IntentRoute(
        intent="knowledge",
        requires_rag=True,
        reason="用户询问学校制度",
        knowledge_sources=[
            KnowledgeSourceRequest(
                source="external_rag",
                query="学校请假制度",
                reason="需要制度知识库",
                required=True,
            )
        ],
    )

    observation = MessageProcessingPipeline.format_external_knowledge_observation(
        "请假需要提前提交申请。",
        route=route,
        fallback_query="请假制度",
    )

    assert "## external_rag" in observation
    assert "query: 学校请假制度" in observation
    assert "status: hit" in observation
    assert "required: true" in observation
    assert "提前提交申请" in observation


def test_extract_search_query_normalizes_router_query(loaded_plugins):
    from src.core.agent.runtime.knowledge import extract_search_query

    assert extract_search_query("班会材料：report.md？") == "班会材料 report md"
