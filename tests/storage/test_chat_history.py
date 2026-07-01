from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_group_chat_history_store_can_record_search_and_build_context(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, GroupChatHistoryStore

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
    assert records[0].model_dump()["user_name"] == "张三"

    context = await store.build_group_history_context("30001", "调课", limit=10, search_window=50)
    assert context is not None
    assert "当前系统群近期相关消息" in context
    assert "张三: 今天下午要不要调课" in context
    assert "王五" not in context


def test_group_chat_history_store_returns_recent_messages_without_query(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, GroupChatHistoryStore

    store = GroupChatHistoryStore(StorageManager(tmp_path / "storage"))
    now = datetime.now()

    store._record_group_message_sync(
        "30001", "u1", "张三", "第一条消息", "第一条消息", "m1", now - timedelta(minutes=3)
    )
    store._record_group_message_sync(
        "30001", "u2", "李四", "第二条消息", "第二条消息", "m2", now - timedelta(minutes=2)
    )
    store._record_group_message_sync(
        "30001", "u3", "王五", "第三条消息", "第三条消息", "m3", now - timedelta(minutes=1)
    )

    records = store._search_group_messages_sync("30001", "", 2, 50, "m3")

    assert [record.user_name for record in records] == ["张三", "李四"]


@pytest.mark.asyncio
async def test_group_search_filters_duplicate_chat_user_records_before_limit(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, ChatHistoryStore, MessageActorRole

    store = ChatHistoryStore(StorageManager(tmp_path / "storage"))
    now = datetime(2026, 6, 30, 12, 0, 0)

    for index in range(3):
        await store.record_group_collect_message(
            group_id="30002",
            user_id=f"u{index}",
            user_name=f"用户{index}",
            plain_text=f"关键词 collect {index}",
            raw_text=f"关键词 collect {index}",
            message_id=f"collect-{index}",
            created_at=now + timedelta(minutes=index),
        )
    for index in range(2):
        await store.record_group_chat_message(
            group_id="30002",
            actor_role=MessageActorRole.user,
            actor_id=f"u{index}",
            actor_name=f"用户{index}",
            plain_text=f"关键词 duplicate chat {index}",
            raw_text=f"关键词 duplicate chat {index}",
            message_id=f"chat-user-{index}",
            created_at=now + timedelta(minutes=10 + index),
        )

    records = await store.search_group_messages("30002", "关键词", limit=2, search_window=5)

    assert [record.plain_text for record in records] == ["关键词 collect 1", "关键词 collect 2"]


@pytest.mark.asyncio
async def test_user_chat_messages_are_stored_under_user_space(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, ChatHistoryStore, MessageActorRole, MessageDirection

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
async def test_user_chat_messages_are_mirrored_to_daily_jsonl(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, ChatHistoryStore, MessageActorRole

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)
    created_at = datetime(2026, 6, 30, 12, 30, 0)

    await store.record_user_chat_message(
        user_id="90002",
        user_name="每日记录用户",
        plain_text="今天需要写进用户聊天时间线",
        raw_text="今天需要写进用户聊天时间线",
        message_id="daily-1",
        actor_role=MessageActorRole.user,
        created_at=created_at,
        platform="onebot11.qq_client",
        platform_name="QQ",
        bot_id="114514",
        platform_user_id="90002",
        metadata={"source": "unit_test"},
    )
    await store.record_user_chat_message(
        user_id="90002",
        user_name="每日记录用户",
        plain_text="今天需要写进用户聊天时间线",
        raw_text="今天需要写进用户聊天时间线",
        message_id="daily-1",
        actor_role=MessageActorRole.user,
        created_at=created_at,
        platform="onebot11.qq_client",
        platform_name="QQ",
        bot_id="114514",
        platform_user_id="90002",
        metadata={"source": "unit_test"},
    )

    daily_path = manager.user_space("90002").chat_dir / "daily" / "2026-06-30.jsonl"
    daily_records = store.read_user_daily_messages("90002", "2026-06-30")

    assert daily_path.is_file()
    assert len(daily_records) == 1
    assert daily_records[0]["plain_text"] == "今天需要写进用户聊天时间线"
    assert daily_records[0]["record_kind"] == "chat"
    assert daily_records[0]["direction"] == "inbound"
    assert daily_records[0]["actor_role"] == "user"
    assert daily_records[0]["platform_user_id"] == "90002"
    assert daily_records[0]["metadata"]["source"] == "unit_test"


@pytest.mark.asyncio
async def test_group_assistant_messages_are_stored_under_group_space(loaded_plugins, tmp_path):
    from src.core.storage import (
        StorageManager,
        ChatHistoryStore,
        MessageActorRole,
        MessageDirection,
        MessageOwnerKind,
        MessageRecordKind,
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


@pytest.mark.asyncio
async def test_chat_history_store_can_summarize_user_chat_messages(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, ChatHistoryStore, MessageActorRole

    store = ChatHistoryStore(StorageManager(tmp_path / "storage"))
    today = datetime(2026, 5, 6, 0, 0, 0)

    await store.record_user_chat_message(
        user_id="90001",
        user_name="测试用户",
        plain_text="你好",
        raw_text="你好",
        message_id="u1",
        actor_role=MessageActorRole.user,
        created_at=today + timedelta(hours=9),
    )
    await store.record_user_chat_message(
        user_id="90001",
        user_name="测试用户",
        plain_text="你好，我在",
        raw_text="你好，我在",
        message_id="a1",
        actor_role=MessageActorRole.assistant,
        actor_id="bot-1",
        actor_name="机器人",
        created_at=today + timedelta(hours=9, minutes=1),
    )
    await store.record_user_chat_message(
        user_id="90001",
        user_name="测试用户",
        plain_text="我们聊了几条消息",
        raw_text="我们聊了几条消息",
        message_id="ask",
        actor_role=MessageActorRole.user,
        created_at=today + timedelta(hours=9, minutes=2),
    )
    await store.record_user_chat_message(
        user_id="90001",
        user_name="测试用户",
        plain_text="昨天的消息",
        raw_text="昨天的消息",
        message_id="old",
        actor_role=MessageActorRole.user,
        created_at=today - timedelta(days=1, minutes=1),
    )

    summary = await store.summarize_user_chat_messages(
        "90001",
        exclude_message_id="ask",
        start_at=today,
        end_at=today + timedelta(days=1),
    )

    assert summary.total == 2
    assert summary.inbound == 1
    assert summary.outbound == 1
    assert summary.distinct_user_count == 2


@pytest.mark.asyncio
async def test_chat_history_store_can_summarize_group_collect_messages(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, ChatHistoryStore

    store = ChatHistoryStore(StorageManager(tmp_path / "storage"))
    today = datetime(2026, 5, 6, 0, 0, 0)

    store._record_group_message_sync(
        "30001",
        "u1",
        "张三",
        "第一条群消息",
        "第一条群消息",
        "g1",
        today + timedelta(hours=10),
    )
    store._record_group_message_sync(
        "30001",
        "u2",
        "李四",
        "第二条群消息",
        "第二条群消息",
        "g2",
        today + timedelta(hours=10, minutes=1),
    )
    store._record_group_message_sync(
        "30001",
        "u1",
        "张三",
        "这个群今天聊了多少条消息",
        "这个群今天聊了多少条消息",
        "ask",
        today + timedelta(hours=10, minutes=2),
    )
    store._record_group_message_sync(
        "30001",
        "u3",
        "王五",
        "昨天的群消息",
        "昨天的群消息",
        "old",
        today - timedelta(days=1, minutes=1),
    )

    summary = await store.summarize_group_messages(
        "30001",
        exclude_message_id="ask",
        start_at=today,
        end_at=today + timedelta(days=1),
    )

    assert summary.total == 2
    assert summary.inbound == 2
    assert summary.outbound == 0
    assert summary.distinct_user_count == 2


def test_chat_history_store_backfills_created_ts_for_legacy_rows(loaded_plugins, tmp_path):
    from src.core.storage import StorageManager, ChatHistoryStore, MessageOwnerKind

    manager = StorageManager(tmp_path / "storage")
    db_path = manager.user_space("legacy-user").chat_dir / "messages.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_key TEXT NOT NULL UNIQUE,
                record_kind TEXT NOT NULL,
                actor_role TEXT NOT NULL,
                message_id TEXT NOT NULL DEFAULT '',
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                plain_text TEXT NOT NULL,
                raw_text TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """)
        connection.execute(
            """
            INSERT INTO messages (
                event_key,
                record_kind,
                actor_role,
                message_id,
                user_id,
                user_name,
                plain_text,
                raw_text,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-event",
                "chat",
                "assistant",
                "legacy-message",
                "legacy-user",
                "旧机器人",
                "历史兼容消息",
                "历史兼容消息",
                "2026-05-06T09:30:00",
            ),
        )

    store = ChatHistoryStore(manager)
    with store._connect(MessageOwnerKind.user, "legacy-user") as connection:  # noqa: SLF001
        columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(messages)").fetchall()}
        row = connection.execute(
            """
            SELECT owner_kind, owner_id, direction, created_ts
            FROM messages
            WHERE event_key = ?
            """,
            ("legacy-event",),
        ).fetchone()

    assert "created_ts" in columns
    assert row is not None
    assert row["owner_kind"] == "user"
    assert row["owner_id"] == "legacy-user"
    assert row["direction"] == "outbound"
    assert int(row["created_ts"]) > 0
