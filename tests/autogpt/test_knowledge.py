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
