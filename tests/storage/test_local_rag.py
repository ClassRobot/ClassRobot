from __future__ import annotations

from datetime import datetime

import pytest


@pytest.mark.asyncio
async def test_local_rag_indexes_chat_history_with_overlap_recall(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, LocalRagService, ChatHistoryStore, MessageActorRole, MessageOwnerKind

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)
    service = LocalRagService(manager=manager, chat_store=store)

    await store.record_user_chat_message(
        user_id=91001,
        user_name="测试用户",
        plain_text="昨天说过班会材料放在 report.md，里面有作业统计。",
        raw_text="昨天说过班会材料放在 report.md，里面有作业统计。",
        actor_role=MessageActorRole.user,
        message_id="rag-chat-1",
        created_at=datetime(2026, 5, 6, 9, 0),
    )
    await store.record_user_chat_message(
        user_id=91001,
        user_name="测试用户",
        plain_text="今天午饭想吃番茄炒蛋。",
        raw_text="今天午饭想吃番茄炒蛋。",
        actor_role=MessageActorRole.user,
        message_id="rag-chat-2",
        created_at=datetime(2026, 5, 6, 9, 5),
    )

    indexed = await service.refresh_user_chat(91001)
    results = await service.search_owner(MessageOwnerKind.user, 91001, "班会资料", source_types={"chat"}, limit=3)

    assert indexed >= 2
    assert results
    assert "班会材料" in results[0].text
    assert results[0].score > 0


@pytest.mark.asyncio
async def test_local_rag_indexes_file_space_and_builds_summary_context(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, LocalRagService, MessageOwnerKind

    manager = StorageManager(tmp_path / "storage")
    space = manager.user_space(91002)
    report = space.home_dir / "documents" / "report.md"
    report.write_text("班会材料：周五下午三点开会，带上作业统计和请假名单。", encoding="utf-8")
    service = LocalRagService(manager=manager)

    indexed = await service.refresh_file_space(space)
    results = await service.search_owner(MessageOwnerKind.user, 91002, "作业统计", source_types={"file"}, limit=3)
    context = service.build_context("用户文件空间检索（本地 RAG）", "作业统计", results)

    assert indexed >= 1
    assert results
    assert context is not None
    assert "召回摘要" in context
    assert "~/documents/report.md" in context
    assert "作业统计" in context


@pytest.mark.asyncio
async def test_local_rag_group_chat_history_matches_group_history_contract(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, LocalRagService, ChatHistoryStore, MessageActorRole, MessageOwnerKind

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)
    service = LocalRagService(manager=manager, chat_store=store)

    await store.record_group_collect_message(
        group_id="group-91010",
        user_id="u1",
        user_name="张三",
        plain_text="今天的作业安排已经发了吗",
        raw_text="今天的作业安排已经发了吗",
        message_id="group-rag-collect-1",
        created_at=datetime(2026, 5, 6, 9, 0),
    )
    await store.record_group_chat_message(
        group_id="group-91010",
        plain_text="今天作业是完成第 3 章习题。",
        raw_text="今天作业是完成第 3 章习题。",
        actor_role=MessageActorRole.assistant,
        actor_id="bot-1",
        actor_name="机器人",
        message_id="group-rag-assistant-1",
        created_at=datetime(2026, 5, 6, 9, 1),
    )
    await store.record_group_chat_message(
        group_id="group-91010",
        plain_text="检索群聊记录 作业安排",
        raw_text="检索群聊记录 作业安排",
        actor_role=MessageActorRole.user,
        actor_id="u2",
        actor_name="李四",
        message_id="group-rag-chat-user-1",
        created_at=datetime(2026, 5, 6, 9, 2),
    )

    indexed = await service.refresh_group_chat_history("group-91010")
    results = await service.search_owner(
        MessageOwnerKind.group,
        "group-91010",
        "作业安排",
        source_types={"chat"},
        limit=10,
    )
    texts = [result.text for result in results]

    assert indexed >= 2
    assert any("今天的作业安排已经发了吗" in text for text in texts)
    assert any("今天作业是完成第 3 章习题" in text for text in texts)
    assert all("检索群聊记录 作业安排" not in text for text in texts)


@pytest.mark.asyncio
async def test_local_rag_removes_deleted_file_chunks_after_full_refresh(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, LocalRagService, MessageOwnerKind

    manager = StorageManager(tmp_path / "storage")
    space = manager.user_space(91003)
    secret = space.home_dir / "documents" / "secret.md"
    secret.write_text("秘密计划：下周整理实验报告。", encoding="utf-8")
    service = LocalRagService(manager=manager)

    await service.refresh_file_space(space)
    assert await service.search_owner(MessageOwnerKind.user, 91003, "秘密计划", source_types={"file"})

    secret.unlink()
    await service.refresh_file_space(space)

    assert await service.search_owner(MessageOwnerKind.user, 91003, "秘密计划", source_types={"file"}) == []
