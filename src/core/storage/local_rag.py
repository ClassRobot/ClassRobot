from __future__ import annotations

import re
import json
import asyncio
import sqlite3
from hashlib import md5
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Literal, Iterable, cast

from pydantic import Field, BaseModel

from .files import FileSpace, StorageManager, storage_manager
from .chat_history import ChatHistoryStore, MessageOwnerKind, ChatHistoryRecord, MessageRecordKind, chat_history_store

LOCAL_RAG_DB_NAME = "local_rag.db"
RAG_CHUNK_TABLE_NAME = "rag_chunks"
RAG_TERM_TABLE_NAME = "rag_terms"
DEFAULT_TEXT_SUFFIXES = {
    ".cfg",
    ".csv",
    ".ini",
    ".json",
    ".log",
    ".md",
    ".py",
    ".text",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
STOP_WORDS = {
    "一个",
    "一些",
    "一下",
    "什么",
    "哪些",
    "怎么",
    "如何",
    "这个",
    "那个",
    "我们",
    "你们",
    "他们",
    "the",
    "and",
    "for",
    "with",
    "from",
}

RagSourceType = Literal["chat", "file"]


class LocalRagChunk(BaseModel):
    """表示本地 RAG 索引中的一个检索片段。"""

    owner_kind: MessageOwnerKind
    owner_id: str
    source_type: RagSourceType
    source_id: str
    chunk_index: int = 0
    title: str = ""
    text: str
    summary: str = ""
    keywords: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    source_updated_at: int = 0

    @property
    def chunk_key(self) -> str:
        """返回片段稳定键。"""

        payload = "|".join(
            (
                self.owner_kind.value,
                self.owner_id,
                self.source_type,
                self.source_id,
                str(self.chunk_index),
            )
        )
        return md5(payload.encode("utf-8")).hexdigest()


class LocalRagSearchResult(BaseModel):
    """表示一次本地 RAG 检索命中的结果。"""

    owner_kind: MessageOwnerKind
    owner_id: str
    source_type: RagSourceType
    source_id: str
    title: str
    text: str
    summary: str
    keywords: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    score: float = 0.0


@dataclass(frozen=True)
class _StoredChunk:
    """SQLite 中读出的片段行。"""

    owner_kind: MessageOwnerKind
    owner_id: str
    source_type: RagSourceType
    source_id: str
    title: str
    text: str
    summary: str
    keywords: list[str]
    metadata: dict
    source_updated_at: int


class LocalRagIndex:
    """一个文件空间内的本地 RAG SQLite 索引。"""

    def __init__(self, space: FileSpace) -> None:
        """初始化索引。"""

        self.space = space
        self.db_path = space.chat_dir / LOCAL_RAG_DB_NAME
        self._ensure_schema()

    def upsert_chunks(self, chunks: Iterable[LocalRagChunk]) -> None:
        """写入或更新一批检索片段。"""

        with self._connect() as connection:
            for chunk in chunks:
                connection.execute(
                    f"""
                    INSERT INTO {RAG_CHUNK_TABLE_NAME} (
                        chunk_key,
                        owner_kind,
                        owner_id,
                        source_type,
                        source_id,
                        chunk_index,
                        title,
                        text,
                        summary,
                        keywords,
                        metadata,
                        source_updated_at,
                        indexed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chunk_key) DO UPDATE SET
                        title = excluded.title,
                        text = excluded.text,
                        summary = excluded.summary,
                        keywords = excluded.keywords,
                        metadata = excluded.metadata,
                        source_updated_at = excluded.source_updated_at,
                        indexed_at = excluded.indexed_at
                    """,
                    (
                        chunk.chunk_key,
                        chunk.owner_kind.value,
                        chunk.owner_id,
                        chunk.source_type,
                        chunk.source_id,
                        chunk.chunk_index,
                        chunk.title,
                        chunk.text,
                        chunk.summary,
                        json.dumps(chunk.keywords, ensure_ascii=False),
                        json.dumps(chunk.metadata, ensure_ascii=False, default=str),
                        chunk.source_updated_at,
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
                connection.execute(f"DELETE FROM {RAG_TERM_TABLE_NAME} WHERE chunk_key = ?", (chunk.chunk_key,))
                connection.executemany(
                    f"""
                    INSERT OR IGNORE INTO {RAG_TERM_TABLE_NAME} (term, chunk_key, source_type, source_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    ((term, chunk.chunk_key, chunk.source_type, chunk.source_id) for term in build_chunk_terms(chunk)),
                )
            connection.commit()

    def delete_source(self, source_type: RagSourceType, source_id: str) -> None:
        """删除某个来源的旧片段。"""

        with self._connect() as connection:
            chunk_keys = [
                str(row["chunk_key"])
                for row in connection.execute(
                    f"SELECT chunk_key FROM {RAG_CHUNK_TABLE_NAME} WHERE source_type = ? AND source_id = ?",
                    (source_type, source_id),
                ).fetchall()
            ]
            self._delete_terms_by_chunk_keys(connection, chunk_keys)
            connection.execute(
                f"DELETE FROM {RAG_CHUNK_TABLE_NAME} WHERE source_type = ? AND source_id = ?",
                (source_type, source_id),
            )
            connection.commit()

    def delete_sources_not_in(self, source_type: RagSourceType, active_source_ids: set[str]) -> None:
        """删除已经不存在的来源片段。"""

        with self._connect() as connection:
            if active_source_ids:
                placeholders = ", ".join("?" for _ in active_source_ids)
                rows = connection.execute(
                    f"""
                    SELECT chunk_key
                    FROM {RAG_CHUNK_TABLE_NAME}
                    WHERE source_type = ? AND source_id NOT IN ({placeholders})
                    """,
                    (source_type, *active_source_ids),
                ).fetchall()
                chunk_keys = [str(row["chunk_key"]) for row in rows]
                self._delete_terms_by_chunk_keys(connection, chunk_keys)
                connection.execute(
                    f"""
                    DELETE FROM {RAG_CHUNK_TABLE_NAME}
                    WHERE source_type = ? AND source_id NOT IN ({placeholders})
                    """,
                    (source_type, *active_source_ids),
                )
            else:
                rows = connection.execute(
                    f"SELECT chunk_key FROM {RAG_CHUNK_TABLE_NAME} WHERE source_type = ?",
                    (source_type,),
                ).fetchall()
                chunk_keys = [str(row["chunk_key"]) for row in rows]
                self._delete_terms_by_chunk_keys(connection, chunk_keys)
                connection.execute(f"DELETE FROM {RAG_CHUNK_TABLE_NAME} WHERE source_type = ?", (source_type,))
            connection.commit()

    def search(
        self,
        query: str,
        *,
        source_types: set[RagSourceType] | None = None,
        limit: int = 8,
        max_candidates: int = 600,
    ) -> list[LocalRagSearchResult]:
        """在本地索引中执行混合召回。"""

        query_terms = tokenize_for_recall(query)
        query_text = normalize_recall_text(query)
        chunks = self._load_candidate_chunks(query_terms, source_types=source_types, limit=max_candidates)
        if not chunks:
            chunks = self._load_recent_chunks(source_types=source_types, limit=max_candidates)
        scored: list[LocalRagSearchResult] = []
        for chunk in chunks:
            score = score_chunk(query_text, query_terms, chunk)
            if query_terms and score <= 0:
                continue
            scored.append(
                LocalRagSearchResult(
                    owner_kind=chunk.owner_kind,
                    owner_id=chunk.owner_id,
                    source_type=chunk.source_type,
                    source_id=chunk.source_id,
                    title=chunk.title,
                    text=chunk.text,
                    summary=chunk.summary,
                    keywords=chunk.keywords,
                    metadata=chunk.metadata,
                    score=round(score, 4),
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:limit]

    def _load_candidate_chunks(
        self,
        query_terms: set[str],
        *,
        source_types: set[RagSourceType] | None,
        limit: int,
    ) -> list[_StoredChunk]:
        """通过倒排词表读取候选片段。"""

        if not query_terms:
            return []

        term_placeholders = ", ".join("?" for _ in query_terms)
        params: list[object] = list(query_terms)
        source_filter = ""
        if source_types:
            source_placeholders = ", ".join("?" for _ in source_types)
            source_filter = f"AND c.source_type IN ({source_placeholders})"
            params.extend(source_types)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT c.*, COUNT(t.term) AS term_hits
                FROM {RAG_TERM_TABLE_NAME} AS t
                JOIN {RAG_CHUNK_TABLE_NAME} AS c ON c.chunk_key = t.chunk_key
                WHERE t.term IN ({term_placeholders})
                {source_filter}
                GROUP BY c.chunk_key
                ORDER BY term_hits DESC, c.source_updated_at DESC, c.indexed_at DESC
                LIMIT ?
                """,
                tuple(params + [limit]),
            ).fetchall()
        return [row_to_chunk(row) for row in rows]

    def _load_recent_chunks(
        self,
        *,
        source_types: set[RagSourceType] | None,
        limit: int,
    ) -> list[_StoredChunk]:
        """读取最近索引片段。"""

        where = ""
        params: tuple = ()
        if source_types:
            placeholders = ", ".join("?" for _ in source_types)
            where = f"WHERE source_type IN ({placeholders})"
            params = tuple(source_types)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM {RAG_CHUNK_TABLE_NAME}
                {where}
                ORDER BY source_updated_at DESC, indexed_at DESC
                LIMIT ?
                """,
                params + (limit,),
            ).fetchall()
        return [row_to_chunk(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        """打开索引数据库。"""

        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        """确保索引表存在。"""

        self.space.chat_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(f"""
                CREATE TABLE IF NOT EXISTS {RAG_CHUNK_TABLE_NAME} (
                    chunk_key TEXT PRIMARY KEY,
                    owner_kind TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL DEFAULT 0,
                    title TEXT NOT NULL DEFAULT '',
                    text TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    keywords TEXT NOT NULL DEFAULT '[]',
                    metadata TEXT NOT NULL DEFAULT '{{}}',
                    source_updated_at INTEGER NOT NULL DEFAULT 0,
                    indexed_at TEXT NOT NULL
                )
                """)
            connection.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_rag_chunks_source
                ON {RAG_CHUNK_TABLE_NAME} (source_type, source_id)
                """)
            connection.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_rag_chunks_updated
                ON {RAG_CHUNK_TABLE_NAME} (source_updated_at DESC)
                """)
            connection.execute(f"""
                CREATE TABLE IF NOT EXISTS {RAG_TERM_TABLE_NAME} (
                    term TEXT NOT NULL,
                    chunk_key TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    PRIMARY KEY (term, chunk_key)
                )
                """)
            connection.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_rag_terms_chunk_key
                ON {RAG_TERM_TABLE_NAME} (chunk_key)
                """)
            connection.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_rag_terms_source
                ON {RAG_TERM_TABLE_NAME} (source_type, source_id)
                """)
            connection.commit()

    @staticmethod
    def _delete_terms_by_chunk_keys(connection: sqlite3.Connection, chunk_keys: list[str]) -> None:
        """按 chunk key 删除倒排词。"""

        if not chunk_keys:
            return
        placeholders = ", ".join("?" for _ in chunk_keys)
        connection.execute(f"DELETE FROM {RAG_TERM_TABLE_NAME} WHERE chunk_key IN ({placeholders})", tuple(chunk_keys))


class LocalRagService:
    """负责把聊天记录和文件空间接成本地 RAG 索引。"""

    def __init__(
        self,
        *,
        manager: StorageManager | None = None,
        chat_store: ChatHistoryStore | None = None,
    ) -> None:
        """初始化本地 RAG 服务。"""

        self.manager = manager or storage_manager
        self.chat_store = chat_store or chat_history_store

    def index_for_owner(self, owner_kind: MessageOwnerKind, owner_id: str | int) -> LocalRagIndex:
        """返回指定空间对应的索引。"""

        if owner_kind == MessageOwnerKind.user:
            return LocalRagIndex(self.manager.user_space(owner_id))
        if owner_kind == MessageOwnerKind.group:
            return LocalRagIndex(self.manager.group_space(owner_id))
        raise ValueError(f"LocalRagService only supports user/group owner indexes, got {owner_kind}")

    async def refresh_user_chat(self, user_id: str | int, *, limit: int = 240) -> int:
        """刷新用户人机聊天记录索引。"""

        return await asyncio.to_thread(
            self._refresh_chat_sync,
            MessageOwnerKind.user,
            user_id,
            (MessageRecordKind.chat,),
            limit=limit,
        )

    async def refresh_group_chat_history(self, group_id: str | int, *, limit: int = 320) -> int:
        """刷新与 ``group_chat_history`` 契约一致的系统群聊天历史索引。"""

        return await asyncio.to_thread(self._refresh_group_chat_history_sync, group_id, limit=limit)

    async def refresh_group_collect(self, group_id: str | int, *, limit: int = 320) -> int:
        """兼容旧命名，转调系统群聊天历史索引刷新。"""

        return await self.refresh_group_chat_history(group_id, limit=limit)

    async def refresh_file_space(self, space: FileSpace, *, max_files: int = 220) -> int:
        """刷新文件空间文本内容索引。"""

        return await asyncio.to_thread(index_file_space_sync, LocalRagIndex(space), space, max_files=max_files)

    async def search_owner(
        self,
        owner_kind: MessageOwnerKind,
        owner_id: str | int,
        query: str,
        *,
        source_types: set[RagSourceType] | None = None,
        limit: int = 8,
    ) -> list[LocalRagSearchResult]:
        """检索指定空间。"""

        return await asyncio.to_thread(
            self.index_for_owner(owner_kind, owner_id).search,
            query,
            source_types=source_types,
            limit=limit,
        )

    def _refresh_chat_sync(
        self,
        owner_kind: MessageOwnerKind,
        owner_id: str | int,
        record_kinds: tuple[MessageRecordKind, ...],
        *,
        limit: int,
    ) -> int:
        """同步刷新聊天记录索引。"""

        rows = self.chat_store._load_recent_rows(owner_kind, owner_id, limit, record_kinds)
        records = [self.chat_store._row_to_record(row) for row in rows]
        index = self.index_for_owner(owner_kind, owner_id)
        chunks: list[LocalRagChunk] = []
        for record in records:
            chunks.extend(chat_record_to_chunks(record))
        index.upsert_chunks(chunks)
        return len(chunks)

    def _refresh_group_chat_history_sync(self, group_id: str | int, *, limit: int) -> int:
        """同步刷新系统群聊天历史索引。"""

        records = self.chat_store._load_group_chat_history_records_sync(group_id, limit=limit)
        index = self.index_for_owner(MessageOwnerKind.group, group_id)
        chunks: list[LocalRagChunk] = []
        for record in records:
            chunks.extend(chat_record_to_chunks(record))
        index.upsert_chunks(chunks)
        return len(chunks)

    @staticmethod
    def build_context(title: str, query: str, results: list[LocalRagSearchResult]) -> str | None:
        """把召回结果渲染成适合 LLM 使用的上下文。"""

        if not results:
            return None
        lines = [f"## {title}", f"查询: {query or '最近内容'}", summarize_results(results)]
        for index, result in enumerate(results, start=1):
            source = result.metadata.get("display_path") or result.metadata.get("created_at") or result.source_id
            keywords = "、".join(result.keywords[:6]) if result.keywords else "无"
            snippet = compact_text(result.text, 260)
            lines.extend(
                [
                    f"{index}. {result.title or result.source_type} | score={result.score}",
                    f"来源: {source}",
                    f"摘要: {result.summary or compact_text(result.text, 120)}",
                    f"关键词: {keywords}",
                    f"片段: {snippet}",
                ]
            )
        return "\n".join(lines)


def chat_record_to_chunks(record: ChatHistoryRecord) -> list[LocalRagChunk]:
    """把聊天记录转换为 RAG 片段。"""

    text = record.display_text
    title = f"{record.user_name} 的消息"
    metadata = {
        "event_key": record.event_key,
        "message_id": record.message_id,
        "user_id": record.user_id,
        "user_name": record.user_name,
        "record_kind": record.record_kind.value,
        "direction": record.direction.value,
        "actor_role": record.actor_role.value,
        "created_at": record.created_at.isoformat(timespec="seconds"),
        "platform": record.platform,
        "channel_id": record.channel_id,
    }
    return build_chunks(
        owner_kind=record.owner_kind,
        owner_id=record.owner_id,
        source_type="chat",
        source_id=record.event_key,
        title=title,
        text=text,
        metadata=metadata,
        source_updated_at=int(record.created_at.timestamp()),
        chunk_size=480,
        overlap=60,
    )


def index_file_space_sync(index: LocalRagIndex, space: FileSpace, *, max_files: int = 220) -> int:
    """同步刷新文件空间文本索引。"""

    indexed_chunks = 0
    indexed_files = 0
    active_source_ids: set[str] = set()
    reached_limit = False
    for path in sorted(space.home_dir.rglob("*"), key=lambda item: item.relative_to(space.home_dir).as_posix()):
        if indexed_files >= max_files:
            reached_limit = True
            break
        if not should_index_file(path, space):
            continue
        relative = path.relative_to(space.home_dir).as_posix()
        source_id = f"file:{relative}"
        active_source_ids.add(source_id)
        index.delete_source("file", source_id)
        text = path.read_text("utf-8", errors="ignore")
        chunks = build_chunks(
            owner_kind=MessageOwnerKind(space.kind),
            owner_id=space.owner_id,
            source_type="file",
            source_id=source_id,
            title=relative,
            text=text,
            metadata={
                "display_path": "~/" + relative,
                "relative_path": relative,
                "size": path.stat().st_size,
                "mtime": int(path.stat().st_mtime),
            },
            source_updated_at=int(path.stat().st_mtime),
            chunk_size=900,
            overlap=120,
        )
        index.upsert_chunks(chunks)
        indexed_files += 1
        indexed_chunks += len(chunks)
    if not reached_limit:
        index.delete_sources_not_in("file", active_source_ids)
    return indexed_chunks


def should_index_file(path: Path, space: FileSpace) -> bool:
    """判断文件是否适合进入本地 RAG 索引。"""

    if not path.is_file():
        return False
    try:
        relative = path.relative_to(space.home_dir)
    except ValueError:
        return False
    if any(part.startswith(".") for part in relative.parts):
        return False
    if path.suffix.lower() not in DEFAULT_TEXT_SUFFIXES:
        return False
    return path.stat().st_size <= 512 * 1024


def build_chunks(
    *,
    owner_kind: MessageOwnerKind,
    owner_id: str | int,
    source_type: RagSourceType,
    source_id: str,
    title: str,
    text: str,
    metadata: dict,
    source_updated_at: int,
    chunk_size: int,
    overlap: int,
) -> list[LocalRagChunk]:
    """构建文本片段。"""

    pieces = split_text_into_chunks(text, chunk_size=chunk_size, overlap=overlap)
    chunks: list[LocalRagChunk] = []
    for index, piece in enumerate(pieces):
        chunks.append(
            LocalRagChunk(
                owner_kind=owner_kind,
                owner_id=str(owner_id),
                source_type=source_type,
                source_id=source_id,
                chunk_index=index,
                title=title,
                text=piece,
                summary=build_summary(piece),
                keywords=extract_keywords(f"{title} {piece}"),
                metadata=metadata,
                source_updated_at=source_updated_at,
            )
        )
    return chunks


def split_text_into_chunks(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    """把长文本切成带少量重叠的 chunk。"""

    normalized = compact_text(text, limit=0)
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append(normalized[start:end].strip())
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return [chunk for chunk in chunks if chunk]


def build_summary(text: str, *, limit: int = 180) -> str:
    """生成轻量摘要。"""

    sentences = [item.strip() for item in re.split(r"(?<=[。！？!?；;\n])", text) if item.strip()]
    base = sentences[0] if sentences else text
    return compact_text(base, limit)


def extract_keywords(text: str, *, limit: int = 12) -> list[str]:
    """提取用于召回的轻量关键词。"""

    tokens = tokenize_for_recall(text)
    counter: dict[str, int] = {}
    for token in tokens:
        if token in STOP_WORDS or len(token) < 2:
            continue
        counter[token] = counter.get(token, 0) + 1
    ordered = sorted(counter, key=lambda token: (-counter[token], -len(token), token))
    return ordered[:limit]


def build_chunk_terms(chunk: LocalRagChunk, *, limit: int = 160) -> list[str]:
    """构建倒排索引用的去重词项。"""

    text = " ".join((chunk.title, chunk.summary, chunk.text, " ".join(chunk.keywords)))
    ordered = sorted(tokenize_for_recall(text), key=lambda token: (-len(token), token))
    return ordered[:limit]


def tokenize_for_recall(text: str) -> set[str]:
    """把文本转换为召回 token 集。"""

    normalized = normalize_recall_text(text)
    tokens: set[str] = set()
    for segment in re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", normalized):
        if not segment:
            continue
        tokens.add(segment)
        if re.fullmatch(r"[\u4e00-\u9fff]+", segment):
            if len(segment) <= 4:
                tokens.add(segment)
            for size in (2, 3):
                for index in range(0, max(len(segment) - size + 1, 0)):
                    tokens.add(segment[index : index + size])
    return {token for token in tokens if token and token not in STOP_WORDS}


def score_chunk(query_text: str, query_terms: set[str], chunk: _StoredChunk) -> float:
    """计算查询与 chunk 的混合相似度。"""

    if not query_terms:
        return 0.1

    title = normalize_recall_text(chunk.title)
    summary = normalize_recall_text(chunk.summary)
    text = normalize_recall_text(chunk.text)
    keywords = {normalize_recall_text(keyword) for keyword in chunk.keywords}
    merged = f"{title} {summary} {text} {' '.join(keywords)}"

    score = 0.0
    for term in query_terms:
        if term in title:
            score += 5.0
        if term in keywords:
            score += 4.0
        if term in summary:
            score += 3.0
        if term in text:
            score += 2.0

    chunk_terms = tokenize_for_recall(merged)
    if chunk_terms:
        score += 5.0 * (len(query_terms & chunk_terms) / max(len(query_terms), 1))
    score += 4.0 * char_ngram_similarity(query_text, merged)
    return score


def char_ngram_similarity(left: str, right: str, *, size: int = 2) -> float:
    """计算字符 ngram Jaccard 相似度。"""

    left_ngrams = char_ngrams(left, size)
    right_ngrams = char_ngrams(right, size)
    if not left_ngrams or not right_ngrams:
        return 0.0
    return len(left_ngrams & right_ngrams) / len(left_ngrams | right_ngrams)


def char_ngrams(text: str, size: int) -> set[str]:
    """生成字符 ngram。"""

    compact = re.sub(r"\s+", "", normalize_recall_text(text))
    if len(compact) < size:
        return {compact} if compact else set()
    return {compact[index : index + size] for index in range(len(compact) - size + 1)}


def normalize_recall_text(text: str | None) -> str:
    """归一化召回文本。"""

    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def compact_text(text: str, limit: int = 260) -> str:
    """压缩文本空白并按长度截断。"""

    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    if limit <= 0 or len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def row_to_chunk(row: sqlite3.Row) -> _StoredChunk:
    """把 SQLite 行转换为内部 chunk 对象。"""

    return _StoredChunk(
        owner_kind=MessageOwnerKind(str(row["owner_kind"])),
        owner_id=str(row["owner_id"]),
        source_type=parse_source_type(row["source_type"]),
        source_id=str(row["source_id"]),
        title=str(row["title"]),
        text=str(row["text"]),
        summary=str(row["summary"]),
        keywords=parse_json_list(row["keywords"]),
        metadata=parse_json_dict(row["metadata"]),
        source_updated_at=int(row["source_updated_at"]),
    )


def parse_source_type(value: object) -> RagSourceType:
    """解析 RAG 来源类型。"""

    text = str(value)
    if text not in {"chat", "file"}:
        text = "chat"
    return cast(RagSourceType, text)


def summarize_results(results: list[LocalRagSearchResult]) -> str:
    """生成一段给模型优先阅读的检索摘要。"""

    source_count = len({(result.source_type, result.source_id) for result in results})
    keywords: list[str] = []
    for result in results:
        for keyword in result.keywords:
            if keyword not in keywords:
                keywords.append(keyword)
            if len(keywords) >= 8:
                break
        if len(keywords) >= 8:
            break
    keyword_text = "、".join(keywords) if keywords else "无"
    top_summaries = "；".join(result.summary for result in results[:3] if result.summary)
    if not top_summaries:
        top_summaries = compact_text(results[0].text, 160)
    return f"召回摘要: 命中 {len(results)} 个片段，来自 {source_count} 个来源；关键词: {keyword_text}；要点: {top_summaries}"


def parse_json_list(value: object) -> list[str]:
    """解析 JSON 列表。"""

    try:
        parsed = json.loads(str(value or "[]"))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def parse_json_dict(value: object) -> dict:
    """解析 JSON 对象。"""

    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


local_rag_service = LocalRagService()

__all__ = [
    "LOCAL_RAG_DB_NAME",
    "RAG_CHUNK_TABLE_NAME",
    "RAG_TERM_TABLE_NAME",
    "LocalRagChunk",
    "LocalRagIndex",
    "LocalRagSearchResult",
    "LocalRagService",
    "build_chunk_terms",
    "build_summary",
    "chat_record_to_chunks",
    "extract_keywords",
    "local_rag_service",
    "summarize_results",
    "split_text_into_chunks",
    "tokenize_for_recall",
]
