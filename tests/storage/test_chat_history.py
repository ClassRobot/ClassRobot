from __future__ import annotations

from datetime import datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_group_chat_history_store_can_record_search_and_build_context(loaded_plugins, tmp_path):
    from utils.storage import GroupChatHistoryStore, StorageManager

    store = GroupChatHistoryStore(StorageManager(tmp_path / "storage"))
    now = datetime.now()

    store._record_group_message_sync(
        "30001",
        "u1",
        "张三",
        "今天下午要不要调课",
        "今天下午要不要调课",
        "m1",
        now - timedelta(minutes=3),
    )
    store._record_group_message_sync(
        "30001",
        "u2",
        "李四",
        "我不同意临时调课",
        "我不同意临时调课",
        "m2",
        now - timedelta(minutes=2),
    )
    store._record_group_message_sync(
        "30001",
        "u3",
        "王五",
        "那就先按原计划上课",
        "那就先按原计划上课",
        "m3",
        now - timedelta(minutes=1),
    )

    records = await store.search_group_messages("30001", "调课", limit=10, search_window=50)

    assert [record.user_name for record in records] == ["张三", "李四"]
    assert any("调课" in record.display_text for record in records)
    assert records[0].dict()["user_name"] == "张三"

    context = await store.build_group_history_context("30001", "调课", limit=10, search_window=50)
    assert context is not None
    assert "当前系统群近期相关消息" in context
    assert "张三: 今天下午要不要调课" in context
    assert "王五" not in context


def test_group_chat_history_store_returns_recent_messages_without_query(loaded_plugins, tmp_path):
    from utils.storage import GroupChatHistoryStore, StorageManager

    store = GroupChatHistoryStore(StorageManager(tmp_path / "storage"))
    now = datetime.now()

    store._record_group_message_sync("30001", "u1", "张三", "第一条消息", "第一条消息", "m1", now - timedelta(minutes=3))
    store._record_group_message_sync("30001", "u2", "李四", "第二条消息", "第二条消息", "m2", now - timedelta(minutes=2))
    store._record_group_message_sync("30001", "u3", "王五", "第三条消息", "第三条消息", "m3", now - timedelta(minutes=1))

    records = store._search_group_messages_sync("30001", "", 2, 50, "m3")

    assert [record.user_name for record in records] == ["张三", "李四"]


@pytest.mark.asyncio
async def test_user_chat_messages_are_stored_under_user_space(loaded_plugins, tmp_path):
    from utils.storage import ChatHistoryStore, MessageActorRole, MessageDirection, StorageManager

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)

    await store.record_user_chat_message(
        user_id="90001",
        user_name="测试用户",
        plain_text="你好，机器人",
        raw_text="你好，机器人",
        message_id="pm1",
        actor_role=MessageActorRole.user,
        platform="onebot11.qq_client",
        platform_name="QQ",
        bot_id="114514",
        platform_user_id="90001",
        metadata={"source": "unit_test", "channel": "private"},
    )

    records = await store.search_user_chat_messages("90001", "机器人", limit=10, search_window=50)

    assert len(records) == 1
    assert records[0].record_kind.value == "chat"
    assert records[0].actor_role == MessageActorRole.user
    assert records[0].direction == MessageDirection.inbound
    assert records[0].platform == "onebot11.qq_client"
    assert records[0].metadata["source"] == "unit_test"
    assert manager.user_space("90001").chat_dir.joinpath("messages.db").is_file()


@pytest.mark.asyncio
async def test_group_assistant_messages_are_stored_under_group_space(loaded_plugins, tmp_path):
    from utils.storage import (
        ChatHistoryStore,
        MessageActorRole,
        MessageDirection,
        MessageOwnerKind,
        MessageRecordKind,
        StorageManager,
    )

    store = ChatHistoryStore(StorageManager(tmp_path / "storage"))

    await store.record_group_chat_message(
        group_id="30002",
        plain_text="这是机器人回复",
        raw_text="这是机器人回复",
        actor_role=MessageActorRole.assistant,
        actor_id="114514",
        actor_name="机器人",
        message_id="gm1",
        platform="onebot11.qq_client",
        platform_name="QQ",
        bot_id="114514",
        platform_user_id="114514",
        metadata={"source": "unit_test", "channel": "group"},
    )

    rows = store._load_recent_rows(MessageOwnerKind.group, "30002", 10, (MessageRecordKind.chat,))

    assert len(rows) == 1
    record = store._row_to_record(rows[0])
    assert record.actor_role == MessageActorRole.assistant
    assert record.direction == MessageDirection.outbound
    assert record.user_id == "114514"
    assert record.user_name == "机器人"
    assert record.plain_text == "这是机器人回复"
    assert record.bot_id == "114514"
    assert record.metadata["source"] == "unit_test"
