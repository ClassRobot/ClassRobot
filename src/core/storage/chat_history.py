from __future__ import annotations

import re
import json
import asyncio
import sqlite3
from enum import Enum
from typing import Any
from hashlib import md5
from pathlib import Path
from contextlib import closing
from datetime import date, datetime

from pydantic import Field, BaseModel, ConfigDict

from .files import StorageManager, storage_manager

MESSAGE_DB_NAME = "messages.db"
MESSAGE_TABLE_NAME = "messages"
LEGACY_GROUP_TABLE_NAME = "group_messages"
NON_TEXT_PLACEHOLDER = "[非文本消息]"
RAW_MESSAGE_REPLACEMENTS = (
    (re.compile(r"\[CQ:image[^\]]*\]", re.IGNORECASE), "[图片]"),
    (re.compile(r"\[CQ:file[^\]]*\]", re.IGNORECASE), "[文件]"),
    (re.compile(r"\[CQ:record[^\]]*\]", re.IGNORECASE), "[语音]"),
    (re.compile(r"\[CQ:video[^\]]*\]", re.IGNORECASE), "[视频]"),
    (re.compile(r"\[CQ:at[^\]]*\]", re.IGNORECASE), "@"),
)


class MessageOwnerKind(str, Enum):
    """描述消息存储所属的空间类型。"""

    user = "user"
    group = "group"


class MessageRecordKind(str, Enum):
    """描述一条消息属于采集消息还是聊天消息。"""

    collect = "collect"
    chat = "chat"


class MessageDirection(str, Enum):
    """描述消息相对机器人的流向。"""

    inbound = "inbound"
    outbound = "outbound"


class MessageActorRole(str, Enum):
    """描述消息发送主体在会话中的角色。"""

    user = "user"
    assistant = "assistant"
    system = "system"


class ChatHistoryRecord(BaseModel):
    """表示一条已归档的消息记录。"""

    event_key: str
    owner_kind: MessageOwnerKind
    owner_id: str
    record_kind: MessageRecordKind
    direction: MessageDirection
    actor_role: MessageActorRole
    message_id: str
    user_id: str
    user_name: str
    plain_text: str
    raw_text: str
    created_at: datetime
    platform: str = ""
    platform_name: str = ""
    channel_id: str | None = None
    guild_id: str | None = None
    bot_id: str = ""
    platform_user_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def display_text(self) -> str:
        """返回适合检索展示的文本。"""

        return normalize_message_text(self.plain_text or self.raw_text or NON_TEXT_PLACEHOLDER)

    model_config = ConfigDict(extra="forbid", frozen=True)


class ChatHistorySummary(BaseModel):
    """描述某个消息空间在给定时间窗口内的统计摘要。"""

    owner_kind: MessageOwnerKind
    owner_id: str
    total: int = 0
    inbound: int = 0
    outbound: int = 0
    distinct_user_count: int = 0
    start_at: datetime | None = None
    end_at: datetime | None = None
    model_config = ConfigDict(extra="forbid", frozen=True)


class ChatHistoryStore:
    """负责记录和检索用户空间、群组空间中的消息历史。"""

    def __init__(self, manager: StorageManager | None = None) -> None:
        """初始化消息存储。"""

        self.manager = manager or storage_manager

    async def record_group_collect_message(
        self,
        *,
        group_id: str | int,
        user_id: str | int,
        user_name: str,
        plain_text: str,
        raw_text: str = "",
        message_id: str | int | None = None,
        created_at: datetime | None = None,
        platform: str = "",
        platform_name: str = "",
        channel_id: str | None = None,
        guild_id: str | None = None,
        bot_id: str = "",
        platform_user_id: str | int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """向系统群组空间写入一条采集消息。"""

        await self._record_message(
            owner_kind=MessageOwnerKind.group,
            owner_id=group_id,
            record_kind=MessageRecordKind.collect,
            direction=MessageDirection.inbound,
            actor_role=MessageActorRole.user,
            user_id=user_id,
            user_name=user_name,
            plain_text=plain_text,
            raw_text=raw_text,
            message_id=message_id,
            created_at=created_at,
            platform=platform,
            platform_name=platform_name,
            channel_id=channel_id,
            guild_id=guild_id,
            bot_id=bot_id,
            platform_user_id=platform_user_id,
            metadata=metadata,
        )

    async def record_group_message(
        self,
        *,
        group_id: str | int,
        user_id: str | int,
        user_name: str,
        plain_text: str,
        raw_text: str = "",
        message_id: str | int | None = None,
        created_at: datetime | None = None,
        platform: str = "",
        platform_name: str = "",
        channel_id: str | None = None,
        guild_id: str | None = None,
        bot_id: str = "",
        platform_user_id: str | int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """兼容旧调用方式，等价于写入一条群采集消息。"""

        await self.record_group_collect_message(
            group_id=group_id,
            user_id=user_id,
            user_name=user_name,
            plain_text=plain_text,
            raw_text=raw_text,
            message_id=message_id,
            created_at=created_at,
            platform=platform,
            platform_name=platform_name,
            channel_id=channel_id,
            guild_id=guild_id,
            bot_id=bot_id,
            platform_user_id=platform_user_id,
            metadata=metadata,
        )

    async def record_group_chat_message(
        self,
        *,
        group_id: str | int,
        plain_text: str,
        raw_text: str = "",
        actor_role: MessageActorRole = MessageActorRole.assistant,
        actor_id: str | int | None = None,
        actor_name: str | None = None,
        message_id: str | int | None = None,
        created_at: datetime | None = None,
        platform: str = "",
        platform_name: str = "",
        channel_id: str | None = None,
        guild_id: str | None = None,
        bot_id: str = "",
        platform_user_id: str | int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """向系统群组空间写入一条聊天消息。"""

        actor_id_text = actor_id if actor_id is not None else actor_role.value
        actor_name_text = actor_name if actor_name is not None else str(actor_id_text)

        await self._record_message(
            owner_kind=MessageOwnerKind.group,
            owner_id=group_id,
            record_kind=MessageRecordKind.chat,
            direction=(
                MessageDirection.outbound if actor_role == MessageActorRole.assistant else MessageDirection.inbound
            ),
            actor_role=actor_role,
            user_id=actor_id_text,
            user_name=actor_name_text,
            plain_text=plain_text,
            raw_text=raw_text,
            message_id=message_id,
            created_at=created_at,
            platform=platform,
            platform_name=platform_name,
            channel_id=channel_id,
            guild_id=guild_id,
            bot_id=bot_id,
            platform_user_id=platform_user_id,
            metadata=metadata,
        )

    async def record_user_chat_message(
        self,
        *,
        user_id: str | int,
        user_name: str,
        plain_text: str,
        raw_text: str = "",
        actor_role: MessageActorRole = MessageActorRole.user,
        actor_id: str | int | None = None,
        actor_name: str | None = None,
        message_id: str | int | None = None,
        created_at: datetime | None = None,
        platform: str = "",
        platform_name: str = "",
        channel_id: str | None = None,
        guild_id: str | None = None,
        bot_id: str = "",
        platform_user_id: str | int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """向用户空间写入一条聊天消息。"""

        await self._record_message(
            owner_kind=MessageOwnerKind.user,
            owner_id=user_id,
            record_kind=MessageRecordKind.chat,
            direction=(
                MessageDirection.outbound if actor_role == MessageActorRole.assistant else MessageDirection.inbound
            ),
            actor_role=actor_role,
            user_id=actor_id if actor_id is not None else user_id,
            user_name=actor_name if actor_name is not None else user_name,
            plain_text=plain_text,
            raw_text=raw_text,
            message_id=message_id,
            created_at=created_at,
            platform=platform,
            platform_name=platform_name,
            channel_id=channel_id,
            guild_id=guild_id,
            bot_id=bot_id,
            platform_user_id=platform_user_id,
            metadata=metadata,
        )

    async def search_group_messages(
        self,
        group_id: str | int,
        query: str | None = None,
        *,
        limit: int = 12,
        search_window: int = 200,
        exclude_message_id: str | int | None = None,
    ) -> list[ChatHistoryRecord]:
        """检索系统群组空间中的消息。

        采集消息（``collect``）覆盖群内用户发言，机器人自己的群聊回复写在
        ``chat`` 空间。为了让 Agent 能看到“用户发言 -> 机器人回复”的完整群聊
        闭环，这里同时读取两类记录，但只保留 ``chat`` 中机器人（assistant）那
        部分，避免把已经存在于 ``collect`` 的用户命令消息重复计入。
        """

        return self._search_group_chat_history_records_sync(
            group_id,
            query,
            limit,
            search_window,
            exclude_message_id,
        )

    async def search_user_chat_messages(
        self,
        user_id: str | int,
        query: str | None = None,
        *,
        limit: int = 12,
        search_window: int = 200,
        exclude_message_id: str | int | None = None,
    ) -> list[ChatHistoryRecord]:
        """检索用户空间中的聊天消息。"""

        return await self._search_messages(
            owner_kind=MessageOwnerKind.user,
            owner_id=user_id,
            query=query,
            limit=limit,
            search_window=search_window,
            exclude_message_id=exclude_message_id,
            record_kinds=(MessageRecordKind.chat,),
        )

    async def build_group_history_context(
        self,
        group_id: str | int,
        query: str | None = None,
        *,
        limit: int = 12,
        search_window: int = 200,
        exclude_message_id: str | int | None = None,
    ) -> str | None:
        """构建适合给大模型使用的系统群组消息上下文。"""

        records = await self.search_group_messages(
            group_id,
            query,
            limit=limit,
            search_window=search_window,
            exclude_message_id=exclude_message_id,
        )
        if not records:
            return None

        lines: list[str] = []
        for record in records:
            text = record.display_text
            if len(text) > 120:
                text = text[:117] + "..."
            lines.append(f"[{record.created_at.strftime('%H:%M:%S')}] {record.user_name}: {text}")

        title = "当前系统群近期相关消息"
        if normalize_message_text(query):
            title += f" | 查询: {normalize_message_text(query)}"
        return title + "\n" + "\n".join(lines)

    async def summarize_user_chat_messages(
        self,
        user_id: str | int,
        *,
        exclude_message_id: str | int | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> ChatHistorySummary:
        """统计某个用户空间中的人机聊天消息。"""

        return await self._summarize_messages(
            owner_kind=MessageOwnerKind.user,
            owner_id=user_id,
            exclude_message_id=exclude_message_id,
            start_at=start_at,
            end_at=end_at,
            record_kinds=(MessageRecordKind.chat,),
        )

    async def summarize_group_messages(
        self,
        group_id: str | int,
        *,
        exclude_message_id: str | int | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> ChatHistorySummary:
        """统计某个系统群组空间中的群聊采集消息。"""

        return await self._summarize_messages(
            owner_kind=MessageOwnerKind.group,
            owner_id=group_id,
            exclude_message_id=exclude_message_id,
            start_at=start_at,
            end_at=end_at,
            record_kinds=(MessageRecordKind.collect,),
        )

    async def _record_message(
        self,
        *,
        owner_kind: MessageOwnerKind,
        owner_id: str | int,
        record_kind: MessageRecordKind,
        direction: MessageDirection,
        actor_role: MessageActorRole,
        user_id: str | int,
        user_name: str,
        plain_text: str,
        raw_text: str,
        message_id: str | int | None,
        created_at: datetime | None,
        platform: str,
        platform_name: str,
        channel_id: str | None,
        guild_id: str | None,
        bot_id: str,
        platform_user_id: str | int | None,
        metadata: dict[str, Any] | None,
    ) -> None:
        """异步写入一条消息记录。"""

        await asyncio.to_thread(
            self._record_message_sync,
            owner_kind,
            owner_id,
            record_kind,
            direction,
            actor_role,
            user_id,
            user_name,
            plain_text,
            raw_text,
            message_id,
            created_at,
            platform,
            platform_name,
            channel_id,
            guild_id,
            bot_id,
            platform_user_id,
            metadata,
        )

    async def _search_messages(
        self,
        *,
        owner_kind: MessageOwnerKind,
        owner_id: str | int,
        query: str | None,
        limit: int,
        search_window: int,
        exclude_message_id: str | int | None,
        record_kinds: tuple[MessageRecordKind, ...],
    ) -> list[ChatHistoryRecord]:
        """异步检索指定空间中的消息。"""

        return await asyncio.to_thread(
            self._search_messages_sync,
            owner_kind,
            owner_id,
            query,
            limit,
            search_window,
            exclude_message_id,
            record_kinds,
        )

    async def _summarize_messages(
        self,
        *,
        owner_kind: MessageOwnerKind,
        owner_id: str | int,
        exclude_message_id: str | int | None,
        start_at: datetime | None,
        end_at: datetime | None,
        record_kinds: tuple[MessageRecordKind, ...],
    ) -> ChatHistorySummary:
        """异步统计指定空间中的消息摘要。"""

        return await asyncio.to_thread(
            self._summarize_messages_sync,
            owner_kind,
            owner_id,
            exclude_message_id,
            start_at,
            end_at,
            record_kinds,
        )

    def _record_message_sync(
        self,
        owner_kind: MessageOwnerKind,
        owner_id: str | int,
        record_kind: MessageRecordKind,
        direction: MessageDirection,
        actor_role: MessageActorRole,
        user_id: str | int,
        user_name: str,
        plain_text: str,
        raw_text: str,
        message_id: str | int | None,
        created_at: datetime | None,
        platform: str,
        platform_name: str,
        channel_id: str | None,
        guild_id: str | None,
        bot_id: str,
        platform_user_id: str | int | None,
        metadata: dict[str, Any] | None,
    ) -> None:
        """同步写入一条消息。"""

        plain_text = normalize_message_text(plain_text)
        raw_text = normalize_raw_message(raw_text)
        if not plain_text:
            plain_text = raw_text or NON_TEXT_PLACEHOLDER

        created_at = created_at or datetime.now()
        message_id_text = str(message_id or "")
        user_id_text = str(user_id)
        owner_id_text = str(owner_id)
        metadata_text = json.dumps(metadata or {}, ensure_ascii=False, default=str)
        event_key = build_event_key(
            owner_kind=owner_kind,
            owner_id=owner_id_text,
            record_kind=record_kind,
            direction=direction,
            actor_role=actor_role,
            message_id=message_id_text,
            user_id=user_id_text,
            created_at=created_at,
            plain_text=plain_text,
        )

        with closing(self._connect(owner_kind, owner_id)) as connection:
            cursor = connection.execute(
                f"""
                INSERT OR IGNORE INTO {MESSAGE_TABLE_NAME} (
                    event_key,
                    owner_kind,
                    owner_id,
                    record_kind,
                    direction,
                    actor_role,
                    message_id,
                    user_id,
                    user_name,
                    plain_text,
                    raw_text,
                    created_at,
                    created_ts,
                    platform,
                    platform_name,
                    channel_id,
                    guild_id,
                    bot_id,
                    platform_user_id,
                    metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_key,
                    owner_kind.value,
                    owner_id_text,
                    record_kind.value,
                    direction.value,
                    actor_role.value,
                    message_id_text,
                    user_id_text,
                    normalize_message_text(user_name) or user_id_text,
                    plain_text,
                    raw_text,
                    created_at.isoformat(timespec="seconds"),
                    int(created_at.timestamp()),
                    normalize_message_text(platform),
                    normalize_message_text(platform_name),
                    normalize_message_text(channel_id),
                    normalize_message_text(guild_id),
                    normalize_message_text(bot_id),
                    normalize_message_text(str(platform_user_id) if platform_user_id is not None else None),
                    metadata_text,
                ),
            )
            inserted = cursor.rowcount > 0
            connection.commit()
        if inserted and owner_kind == MessageOwnerKind.user:
            self._append_user_daily_message(
                owner_id=owner_id_text,
                record_kind=record_kind,
                direction=direction,
                actor_role=actor_role,
                message_id=message_id_text,
                user_id=user_id_text,
                user_name=normalize_message_text(user_name) or user_id_text,
                plain_text=plain_text,
                raw_text=raw_text,
                created_at=created_at,
                platform=normalize_message_text(platform),
                platform_name=normalize_message_text(platform_name),
                channel_id=normalize_message_text(channel_id),
                guild_id=normalize_message_text(guild_id),
                bot_id=normalize_message_text(bot_id),
                platform_user_id=normalize_message_text(
                    str(platform_user_id) if platform_user_id is not None else None
                ),
                metadata=metadata or {},
            )

    def _append_user_daily_message(
        self,
        *,
        owner_id: str,
        record_kind: MessageRecordKind,
        direction: MessageDirection,
        actor_role: MessageActorRole,
        message_id: str,
        user_id: str,
        user_name: str,
        plain_text: str,
        raw_text: str,
        created_at: datetime,
        platform: str,
        platform_name: str,
        channel_id: str,
        guild_id: str,
        bot_id: str,
        platform_user_id: str,
        metadata: dict[str, Any],
    ) -> None:
        """把用户聊天消息按日期追加到 JSONL 文件。

        SQLite 仍是结构化检索主索引；每日 JSONL 是面向用户空间的时间线镜像，
        便于后续做按天检索、导出或构建长期记忆。
        """

        daily_dir = self.manager.user_space(owner_id).chat_dir / "daily"
        daily_dir.mkdir(parents=True, exist_ok=True)
        daily_path = daily_dir / f"{created_at.date().isoformat()}.jsonl"
        payload = {
            "record_kind": record_kind.value,
            "direction": direction.value,
            "actor_role": actor_role.value,
            "message_id": message_id,
            "user_id": user_id,
            "user_name": user_name,
            "plain_text": plain_text,
            "raw_text": raw_text,
            "created_at": created_at.isoformat(timespec="seconds"),
            "platform": platform,
            "platform_name": platform_name,
            "channel_id": channel_id,
            "guild_id": guild_id,
            "bot_id": bot_id,
            "platform_user_id": platform_user_id,
            "metadata": metadata,
        }
        with daily_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

    def read_user_daily_messages(self, user_id: str | int, day: date | datetime | str) -> list[dict[str, Any]]:
        """读取指定用户某一天的聊天 JSONL 记录。"""

        if isinstance(day, datetime):
            day_text = day.date().isoformat()
        elif isinstance(day, date):
            day_text = day.isoformat()
        else:
            day_text = str(day)
        daily_path = self.manager.user_space(user_id).chat_dir / "daily" / f"{day_text}.jsonl"
        if not daily_path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in daily_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                records.append(payload)
        return records

    def _record_group_message_sync(
        self,
        group_id: str | int,
        user_id: str | int,
        user_name: str,
        plain_text: str,
        raw_text: str,
        message_id: str | int | None,
        created_at: datetime | None,
    ) -> None:
        """兼容旧调用方式，写入一条群采集消息。"""

        self._record_message_sync(
            MessageOwnerKind.group,
            group_id,
            MessageRecordKind.collect,
            MessageDirection.inbound,
            MessageActorRole.user,
            user_id,
            user_name,
            plain_text,
            raw_text,
            message_id,
            created_at,
            "",
            "",
            None,
            None,
            "",
            user_id,
            None,
        )

    def _search_messages_sync(
        self,
        owner_kind: MessageOwnerKind,
        owner_id: str | int,
        query: str | None,
        limit: int,
        search_window: int,
        exclude_message_id: str | int | None,
        record_kinds: tuple[MessageRecordKind, ...],
    ) -> list[ChatHistoryRecord]:
        """同步执行消息检索。"""

        rows = self._load_recent_rows(owner_kind, owner_id, max(limit, search_window), record_kinds)
        if exclude_message_id is not None:
            exclude_message_id = str(exclude_message_id)
            rows = [row for row in rows if row["message_id"] != exclude_message_id]
        if not rows:
            return []

        query_terms = self._normalize_query_terms(query)
        if not query_terms:
            return [self._row_to_record(row) for row in rows[-limit:]]

        selected_rows = [row for row in rows if self._row_matches_query(row, query_terms)]
        if not selected_rows:
            return []
        return [self._row_to_record(row) for row in selected_rows[-limit:]]

    def _search_group_messages_sync(
        self,
        group_id: str | int,
        query: str | None,
        limit: int,
        search_window: int,
        exclude_message_id: str | int | None,
    ) -> list[ChatHistoryRecord]:
        """兼容旧调用方式，检索群组采集消息。"""

        return self._search_group_chat_history_records_sync(
            group_id,
            query,
            limit,
            search_window,
            exclude_message_id,
        )

    def _search_group_chat_history_records_sync(
        self,
        group_id: str | int,
        query: str | None,
        limit: int,
        search_window: int,
        exclude_message_id: str | int | None,
    ) -> list[ChatHistoryRecord]:
        """同步检索与 ``group_chat_history`` 契约一致的系统群聊天历史。"""

        records = self._search_messages_sync(
            MessageOwnerKind.group,
            group_id,
            query,
            max(limit, search_window),
            search_window,
            exclude_message_id,
            (MessageRecordKind.collect, MessageRecordKind.chat),
        )
        return self._filter_group_chat_history_records(records)[-limit:]

    def _load_group_chat_history_records_sync(
        self,
        group_id: str | int,
        *,
        limit: int,
        exclude_message_id: str | int | None = None,
    ) -> list[ChatHistoryRecord]:
        """读取系统群最近聊天历史，语义与 ``group_chat_history`` 保持一致。"""

        rows = self._load_recent_rows(
            MessageOwnerKind.group,
            group_id,
            limit,
            (MessageRecordKind.collect, MessageRecordKind.chat),
        )
        if exclude_message_id is not None:
            excluded = str(exclude_message_id)
            rows = [row for row in rows if str(row["message_id"] or "") != excluded]
        records = [self._row_to_record(row) for row in rows]
        return self._filter_group_chat_history_records(records)

    def _summarize_messages_sync(
        self,
        owner_kind: MessageOwnerKind,
        owner_id: str | int,
        exclude_message_id: str | int | None,
        start_at: datetime | None,
        end_at: datetime | None,
        record_kinds: tuple[MessageRecordKind, ...],
    ) -> ChatHistorySummary:
        """同步统计指定空间中的消息摘要。"""

        rows = self._load_summary_rows(owner_kind, owner_id, start_at, end_at, record_kinds)
        if exclude_message_id is not None:
            excluded = str(exclude_message_id)
            rows = [row for row in rows if str(row["message_id"] or "") != excluded]

        inbound = 0
        outbound = 0
        distinct_user_ids: set[str] = set()
        for row in rows:
            direction = str(row["direction"] or "")
            if direction == MessageDirection.inbound.value:
                inbound += 1
            elif direction == MessageDirection.outbound.value:
                outbound += 1

            user_id = str(row["user_id"] or "").strip()
            if user_id:
                distinct_user_ids.add(user_id)

        return ChatHistorySummary(
            owner_kind=owner_kind,
            owner_id=str(owner_id),
            total=len(rows),
            inbound=inbound,
            outbound=outbound,
            distinct_user_count=len(distinct_user_ids),
            start_at=start_at,
            end_at=end_at,
        )

    def _load_recent_rows(
        self,
        owner_kind: MessageOwnerKind,
        owner_id: str | int,
        limit: int,
        record_kinds: tuple[MessageRecordKind, ...],
    ) -> list[sqlite3.Row]:
        """读取最近消息并按时间正序返回。"""

        placeholders = ", ".join("?" for _ in record_kinds)
        with closing(self._connect(owner_kind, owner_id)) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM {MESSAGE_TABLE_NAME}
                WHERE record_kind IN ({placeholders})
                ORDER BY created_ts DESC, id DESC
                LIMIT ?
                """,
                tuple(record_kind.value for record_kind in record_kinds) + (limit,),
            ).fetchall()
        rows.reverse()
        return rows

    def _load_summary_rows(
        self,
        owner_kind: MessageOwnerKind,
        owner_id: str | int,
        start_at: datetime | None,
        end_at: datetime | None,
        record_kinds: tuple[MessageRecordKind, ...],
    ) -> list[sqlite3.Row]:
        """读取指定时间窗口内用于统计的消息行。"""

        placeholders = ", ".join("?" for _ in record_kinds)
        where_clauses = [f"record_kind IN ({placeholders})"]
        parameters: list[str | int] = [record_kind.value for record_kind in record_kinds]

        if start_at is not None:
            where_clauses.append("created_ts >= ?")
            parameters.append(int(start_at.timestamp()))
        if end_at is not None:
            where_clauses.append("created_ts < ?")
            parameters.append(int(end_at.timestamp()))

        with closing(self._connect(owner_kind, owner_id)) as connection:
            return connection.execute(
                f"""
                SELECT user_id, direction, message_id
                FROM {MESSAGE_TABLE_NAME}
                WHERE {' AND '.join(where_clauses)}
                ORDER BY created_ts ASC, id ASC
                """,
                tuple(parameters),
            ).fetchall()

    def _connect(self, owner_kind: MessageOwnerKind, owner_id: str | int) -> sqlite3.Connection:
        """打开并初始化指定空间的消息数据库。"""

        db_path = self._db_path(owner_kind, owner_id)
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        self._ensure_schema(connection, owner_kind, owner_id)
        return connection

    def _db_path(self, owner_kind: MessageOwnerKind, owner_id: str | int) -> Path:
        """返回指定空间消息数据库路径。"""

        if owner_kind == MessageOwnerKind.user:
            return self.manager.user_space(owner_id).chat_dir / MESSAGE_DB_NAME
        if owner_kind == MessageOwnerKind.group:
            return self.manager.group_space(owner_id).chat_dir / MESSAGE_DB_NAME
        raise FileSpaceError(f"聊天历史只支持 user/group 空间，当前 owner_kind={owner_kind}")

    @staticmethod
    def _filter_group_chat_history_records(records: list[ChatHistoryRecord]) -> list[ChatHistoryRecord]:
        """过滤出允许进入 ``group_chat_history`` 的记录视图。"""

        return [
            record
            for record in records
            if record.record_kind == MessageRecordKind.collect or record.actor_role == MessageActorRole.assistant
        ]

    @staticmethod
    def _normalize_query_terms(query: str | None) -> list[str]:
        """将检索语句按空白切分为基础匹配词。"""

        normalized = normalize_message_text(query)
        if not normalized:
            return []
        return [term.lower() for term in normalized.split(" ") if term]

    @staticmethod
    def _row_matches_query(row: sqlite3.Row, query_terms: list[str]) -> bool:
        """判断一条消息是否命中当前基础检索条件。"""

        merged_text = " ".join(
            (
                str(row["user_name"] or ""),
                str(row["plain_text"] or ""),
                str(row["raw_text"] or ""),
            )
        ).lower()
        return all(term in merged_text for term in query_terms)

    @classmethod
    def _ensure_schema(
        cls,
        connection: sqlite3.Connection,
        owner_kind: MessageOwnerKind,
        owner_id: str | int,
    ) -> None:
        """确保消息归档表结构存在，并兼容旧版群聊表。"""

        connection.execute(f"""
            CREATE TABLE IF NOT EXISTS {MESSAGE_TABLE_NAME} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_key TEXT NOT NULL UNIQUE,
                owner_kind TEXT NOT NULL DEFAULT '',
                owner_id TEXT NOT NULL DEFAULT '',
                record_kind TEXT NOT NULL,
                direction TEXT NOT NULL DEFAULT 'inbound',
                actor_role TEXT NOT NULL,
                message_id TEXT NOT NULL DEFAULT '',
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                plain_text TEXT NOT NULL,
                raw_text TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                created_ts INTEGER NOT NULL,
                platform TEXT NOT NULL DEFAULT '',
                platform_name TEXT NOT NULL DEFAULT '',
                channel_id TEXT,
                guild_id TEXT,
                bot_id TEXT NOT NULL DEFAULT '',
                platform_user_id TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{{}}'
            )
            """)
        cls._ensure_columns(connection)
        cls._backfill_created_timestamps(connection)
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS idx_messages_record_kind_created_ts ON {MESSAGE_TABLE_NAME} (record_kind, created_ts DESC)"
        )
        connection.execute(f"CREATE INDEX IF NOT EXISTS idx_messages_user_id ON {MESSAGE_TABLE_NAME} (user_id)")
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS idx_messages_platform_channel ON {MESSAGE_TABLE_NAME} (platform, channel_id)"
        )
        cls._migrate_legacy_group_table(connection, owner_kind, owner_id)
        cls._backfill_owner_columns(connection, owner_kind, owner_id)

    @staticmethod
    def _ensure_columns(connection: sqlite3.Connection) -> None:
        """补齐旧版 SQLite 消息表缺失的字段。"""

        existing_columns = {
            str(row["name"]) for row in connection.execute(f"PRAGMA table_info({MESSAGE_TABLE_NAME})").fetchall()
        }
        required_columns = {
            "owner_kind": "TEXT NOT NULL DEFAULT ''",
            "owner_id": "TEXT NOT NULL DEFAULT ''",
            "direction": "TEXT NOT NULL DEFAULT 'inbound'",
            "created_ts": "INTEGER NOT NULL DEFAULT 0",
            "platform": "TEXT NOT NULL DEFAULT ''",
            "platform_name": "TEXT NOT NULL DEFAULT ''",
            "channel_id": "TEXT",
            "guild_id": "TEXT",
            "bot_id": "TEXT NOT NULL DEFAULT ''",
            "platform_user_id": "TEXT NOT NULL DEFAULT ''",
            "metadata": "TEXT NOT NULL DEFAULT '{}'",
        }
        for column_name, column_type in required_columns.items():
            if column_name not in existing_columns:
                connection.execute(f"ALTER TABLE {MESSAGE_TABLE_NAME} ADD COLUMN {column_name} {column_type}")

    @staticmethod
    def _backfill_created_timestamps(connection: sqlite3.Connection) -> None:
        """为旧记录补齐 ``created_ts`` 秒级时间戳。"""

        rows = connection.execute(f"""
            SELECT id, created_at
            FROM {MESSAGE_TABLE_NAME}
            WHERE created_ts IS NULL OR created_ts <= 0
            """).fetchall()
        if not rows:
            return

        updates: list[tuple[int, int]] = []
        for row in rows:
            created_at_text = str(row["created_at"] or "").strip()
            if not created_at_text:
                continue
            try:
                created_ts = int(datetime.fromisoformat(created_at_text).timestamp())
            except ValueError:
                continue
            updates.append((created_ts, int(row["id"])))

        if updates:
            connection.executemany(
                f"UPDATE {MESSAGE_TABLE_NAME} SET created_ts = ? WHERE id = ?",
                updates,
            )

    @staticmethod
    def _migrate_legacy_group_table(
        connection: sqlite3.Connection,
        owner_kind: MessageOwnerKind,
        owner_id: str | int,
    ) -> None:
        """把旧版 `group_messages` 数据迁移到统一消息表。"""

        legacy_exists = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (LEGACY_GROUP_TABLE_NAME,),
        ).fetchone()
        if legacy_exists is None:
            return

        connection.execute(
            f"""
            INSERT OR IGNORE INTO {MESSAGE_TABLE_NAME} (
                event_key,
                owner_kind,
                owner_id,
                record_kind,
                direction,
                actor_role,
                message_id,
                user_id,
                user_name,
                plain_text,
                raw_text,
                created_at,
                created_ts,
                platform_user_id,
                metadata
            )
            SELECT
                event_key,
                ?,
                ?,
                ?,
                ?,
                ?,
                message_id,
                user_id,
                user_name,
                plain_text,
                raw_text,
                created_at,
                created_ts,
                user_id,
                ?
            FROM {LEGACY_GROUP_TABLE_NAME}
            """,
            (
                owner_kind.value,
                str(owner_id),
                MessageRecordKind.collect.value,
                MessageDirection.inbound.value,
                MessageActorRole.user.value,
                "{}",
            ),
        )

    @staticmethod
    def _backfill_owner_columns(
        connection: sqlite3.Connection,
        owner_kind: MessageOwnerKind,
        owner_id: str | int,
    ) -> None:
        """为旧记录补齐空间归属和消息方向字段。"""

        connection.execute(
            f"""
            UPDATE {MESSAGE_TABLE_NAME}
            SET owner_kind = ?, owner_id = ?
            WHERE owner_kind = '' OR owner_id = ''
            """,
            (owner_kind.value, str(owner_id)),
        )
        connection.execute(
            f"""
            UPDATE {MESSAGE_TABLE_NAME}
            SET direction = ?
            WHERE actor_role = ? AND direction != ?
            """,
            (
                MessageDirection.outbound.value,
                MessageActorRole.assistant.value,
                MessageDirection.outbound.value,
            ),
        )
        connection.execute(
            f"""
            UPDATE {MESSAGE_TABLE_NAME}
            SET direction = ?
            WHERE actor_role != ? AND direction NOT IN (?, ?)
            """,
            (
                MessageDirection.inbound.value,
                MessageActorRole.assistant.value,
                MessageDirection.inbound.value,
                MessageDirection.outbound.value,
            ),
        )

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ChatHistoryRecord:
        """把 SQLite 行对象转换为消息记录。"""

        return ChatHistoryRecord(
            event_key=str(row["event_key"]),
            owner_kind=MessageOwnerKind(str(row["owner_kind"])),
            owner_id=str(row["owner_id"]),
            record_kind=MessageRecordKind(str(row["record_kind"])),
            direction=MessageDirection(str(row["direction"])),
            actor_role=MessageActorRole(str(row["actor_role"])),
            message_id=str(row["message_id"]),
            user_id=str(row["user_id"]),
            user_name=str(row["user_name"]),
            plain_text=str(row["plain_text"]),
            raw_text=str(row["raw_text"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            platform=str(row["platform"] or ""),
            platform_name=str(row["platform_name"] or ""),
            channel_id=str(row["channel_id"]) if row["channel_id"] not in (None, "") else None,
            guild_id=str(row["guild_id"]) if row["guild_id"] not in (None, "") else None,
            bot_id=str(row["bot_id"] or ""),
            platform_user_id=str(row["platform_user_id"] or ""),
            metadata=parse_metadata(row["metadata"]),
        )


def normalize_message_text(text: str | None) -> str:
    """清理消息文本中的多余空白和换行。

    参数:
        text (str | None): 原始文本。

    返回:
        str: 归一化后的单行文本。
    """

    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def normalize_raw_message(text: str | None) -> str:
    """将原始消息文本转换为更适合检索的可读文本。"""

    normalized = str(text or "")
    for pattern, replacement in RAW_MESSAGE_REPLACEMENTS:
        normalized = pattern.sub(replacement, normalized)
    return normalize_message_text(normalized)


def parse_metadata(value: object) -> dict[str, Any]:
    """解析消息记录中的扩展元数据。"""

    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_event_key(
    *,
    owner_kind: MessageOwnerKind,
    owner_id: str | int,
    record_kind: MessageRecordKind,
    direction: MessageDirection,
    actor_role: MessageActorRole,
    message_id: str,
    user_id: str,
    created_at: datetime,
    plain_text: str,
) -> str:
    """构造一条消息的稳定唯一键。"""

    owner_prefix = f"{owner_kind.value}:{owner_id}:{record_kind.value}:{direction.value}:{actor_role.value}"
    if message_id:
        return f"{owner_prefix}:{message_id}"
    payload = "|".join((owner_prefix, user_id, created_at.isoformat(timespec="microseconds"), plain_text))
    return md5(payload.encode("utf-8")).hexdigest()


GroupChatHistoryStore = ChatHistoryStore
chat_history_store = ChatHistoryStore()

__all__ = [
    "ChatHistoryRecord",
    "ChatHistoryStore",
    "GroupChatHistoryStore",
    "MESSAGE_DB_NAME",
    "MESSAGE_TABLE_NAME",
    "MessageActorRole",
    "MessageDirection",
    "MessageOwnerKind",
    "MessageRecordKind",
    "NON_TEXT_PLACEHOLDER",
    "build_event_key",
    "chat_history_store",
    "normalize_message_text",
    "normalize_raw_message",
    "parse_metadata",
]
