from __future__ import annotations

from datetime import datetime

import pytest


def test_agent_skill_catalog_renders_builtin_skill_summaries(loaded_plugins):
    from src.plugins.autogpt.knowledge import AgentSkillCatalog

    prompt = AgentSkillCatalog().to_prompt()

    assert "ocr" in prompt
    assert "markdown-to-image" in prompt
    assert "image-generation" in prompt


@pytest.mark.asyncio
async def test_local_knowledge_retriever_reads_user_chat_history(loaded_plugins, tmp_path):
    from src.plugins.autogpt.knowledge import AgentRuntimeContext, AgentLocalKnowledgeRetriever

    from utils.storage import StorageManager, ChatHistoryStore, MessageActorRole

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

    retriever = AgentLocalKnowledgeRetriever(manager=manager, chat_store=store)
    context = await retriever.retrieve("查一下聊天记录 report.md", AgentRuntimeContext(user_id=90001))

    assert context is not None
    assert "用户人机聊天记录检索" in context
    assert "班会材料" in context
    assert "report.md" in context


@pytest.mark.asyncio
async def test_local_knowledge_retriever_uses_rag_overlap_recall(loaded_plugins, tmp_path):
    from src.plugins.autogpt.knowledge import AgentRuntimeContext, AgentLocalKnowledgeRetriever

    from utils.storage import StorageManager, ChatHistoryStore, MessageActorRole

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

    retriever = AgentLocalKnowledgeRetriever(manager=manager, chat_store=store)
    context = await retriever.retrieve("查一下聊天记录 班会资料", AgentRuntimeContext(user_id=90003))

    assert context is not None
    assert "本地 RAG" in context
    assert "召回摘要" in context
    assert "班会材料" in context


@pytest.mark.asyncio
async def test_local_knowledge_retriever_reads_user_file_space(loaded_plugins, tmp_path):
    from src.plugins.autogpt.knowledge import AgentRuntimeContext, AgentLocalKnowledgeRetriever

    from utils.storage import StorageManager, ChatHistoryStore

    manager = StorageManager(tmp_path / "storage")
    space = manager.user_space(90002)
    report = space.home_dir / "documents" / "report.md"
    report.write_text("班会材料：周五下午三点开会，带上作业统计。", encoding="utf-8")

    retriever = AgentLocalKnowledgeRetriever(manager=manager, chat_store=ChatHistoryStore(manager))
    context = await retriever.retrieve("查一下文件 report", AgentRuntimeContext(user_id=90002))

    assert context is not None
    assert "用户文件空间检索" in context
    assert "~/documents/report.md" in context
    assert "班会材料" in context


@pytest.mark.asyncio
async def test_local_knowledge_retriever_reads_group_file_space_by_system_group_id(loaded_plugins, tmp_path):
    from src.plugins.autogpt.knowledge import AgentRuntimeContext, AgentLocalKnowledgeRetriever
    from utils.storage import StorageManager, ChatHistoryStore

    manager = StorageManager(tmp_path / "storage")
    report = manager.group_space("system-group-92001").home_dir / "documents" / "group-report.md"
    report.write_text("群文件材料：周三晚自习前提交班会记录。", encoding="utf-8")

    retriever = AgentLocalKnowledgeRetriever(manager=manager, chat_store=ChatHistoryStore(manager))
    context = await retriever.retrieve(
        "查一下文件 report",
        AgentRuntimeContext(
            user_id=90004,
            group_id="system-group-92001",
            platform="onebot11.qq_client",
            channel_id="92001",
        ),
    )

    assert context is not None
    assert "群文件空间检索" in context
    assert "~/documents/group-report.md" in context
    assert "群文件材料" in context
    assert not (manager.group_space("92001").home_dir / "documents" / "group-report.md").exists()


def test_extract_search_query_removes_intent_words(loaded_plugins):
    from src.plugins.autogpt.knowledge import extract_search_query

    assert extract_search_query("帮我查一下聊天记录 report.md") == "report md"
