from __future__ import annotations

import time
import asyncio
import sqlite3
from typing import Any
from pathlib import Path


def _now() -> float:
    """Return the current Unix timestamp.

    Returns:
        float: 当前时间的 Unix 时间戳，单位秒。
    """

    return time.time()


class LocalCache:
    """Provide a SQLite-backed local cache backend.

    该实现用于 Redis 不可用时的单机兜底场景，能力范围刻意保持在
    当前项目所需的最小集合：``set``、``get``、``delete`` 与 ``ping``。

    Attributes:
        path: SQLite 缓存文件路径。
    """

    def __init__(self, path: Path):
        """Initialize the local cache backend.

        Args:
            path: SQLite 缓存文件路径。
        """

        self.path = path
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the SQLite database if needed.

        该方法会确保数据库文件与表结构存在，并通过锁避免并发初始化。

        Returns:
            None
        """

        if self._initialized:
            return
        async with self._lock:
            if self._initialized:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(self._initialize_sync)
            self._initialized = True

    def _initialize_sync(self) -> None:
        """Create SQLite tables and indexes synchronously.

        Returns:
            None
        """

        with sqlite3.connect(self.path, timeout=30, check_same_thread=False) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    namespace INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    value BLOB NOT NULL,
                    expires_at REAL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (namespace, key)
                )
                """)
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cache_entries_expires_at ON cache_entries (expires_at)")
            connection.commit()

    async def ping(self) -> bool:
        """Check whether the local cache backend is available.

        Returns:
            bool: 本地缓存可用时返回 ``True``。
        """

        await self.initialize()
        await asyncio.to_thread(self._ping_sync)
        return True

    def _ping_sync(self) -> None:
        """Execute a lightweight SQLite health check.

        Returns:
            None
        """

        with sqlite3.connect(self.path, timeout=30, check_same_thread=False) as connection:
            connection.execute("SELECT 1").fetchone()

    async def set(self, namespace: int, key: str, value: Any, ex: int | None = None) -> bool:
        """Store a cache value in SQLite.

        Args:
            namespace: 缓存逻辑分区，对应上层 ``db`` 编号。
            key: 缓存键。
            value: 待写入的值；最终会被序列化为 ``bytes``。
            ex: 过期时间，单位秒；为 ``None`` 时表示不过期。

        Returns:
            bool: 写入成功时返回 ``True``。
        """

        await self.initialize()
        payload = self._serialize(value)
        expires_at = _now() + ex if ex and ex > 0 else None
        async with self._lock:
            await asyncio.to_thread(self._set_sync, namespace, key, payload, expires_at)
        return True

    def _set_sync(self, namespace: int, key: str, value: bytes, expires_at: float | None) -> None:
        """Persist a cache value synchronously.

        Args:
            namespace: 缓存逻辑分区。
            key: 缓存键。
            value: 已序列化后的二进制值。
            expires_at: 绝对过期时间戳；为 ``None`` 时表示不过期。

        Returns:
            None
        """

        now = _now()
        with sqlite3.connect(self.path, timeout=30, check_same_thread=False) as connection:
            self._cleanup_expired_sync(connection, now=now)
            connection.execute(
                """
                INSERT INTO cache_entries (namespace, key, value, expires_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(namespace, key) DO UPDATE SET
                    value = excluded.value,
                    expires_at = excluded.expires_at,
                    updated_at = excluded.updated_at
                """,
                (namespace, key, value, expires_at, now),
            )
            connection.commit()

    async def get(self, namespace: int, key: str, *, decode_responses: bool = True):
        """Read a cache value from SQLite.

        Args:
            namespace: 缓存逻辑分区，对应上层 ``db`` 编号。
            key: 缓存键。
            decode_responses: 是否按 UTF-8 解码为 ``str``。

        Returns:
            str | bytes | None: 命中时返回缓存值；未命中或已过期时返回 ``None``。
        """

        await self.initialize()
        async with self._lock:
            payload = await asyncio.to_thread(self._get_sync, namespace, key)
        return self._deserialize(payload, decode_responses=decode_responses)

    def _get_sync(self, namespace: int, key: str) -> bytes | None:
        """Read a serialized cache value synchronously.

        Args:
            namespace: 缓存逻辑分区。
            key: 缓存键。

        Returns:
            bytes | None: 已序列化的缓存值；不存在时返回 ``None``。
        """

        now = _now()
        with sqlite3.connect(self.path, timeout=30, check_same_thread=False) as connection:
            self._cleanup_expired_sync(connection, now=now)
            row = connection.execute(
                "SELECT value FROM cache_entries WHERE namespace = ? AND key = ?",
                (namespace, key),
            ).fetchone()
            connection.commit()
        if row is None:
            return None
        return bytes(row[0])

    async def delete(self, namespace: int, *keys: str) -> int:
        """Delete one or more cache keys from SQLite.

        Args:
            namespace: 缓存逻辑分区，对应上层 ``db`` 编号。
            *keys: 一个或多个缓存键。

        Returns:
            int: 成功删除的键数量。
        """

        await self.initialize()
        if not keys:
            return 0
        async with self._lock:
            return await asyncio.to_thread(self._delete_sync, namespace, tuple(keys))

    def _delete_sync(self, namespace: int, keys: tuple[str, ...]) -> int:
        """Delete cache keys synchronously.

        Args:
            namespace: 缓存逻辑分区。
            keys: 待删除的缓存键集合。

        Returns:
            int: 成功删除的键数量。
        """

        with sqlite3.connect(self.path, timeout=30, check_same_thread=False) as connection:
            cursor = connection.executemany(
                "DELETE FROM cache_entries WHERE namespace = ? AND key = ?",
                [(namespace, key) for key in keys],
            )
            connection.commit()
            return cursor.rowcount if cursor.rowcount is not None and cursor.rowcount >= 0 else 0

    def _cleanup_expired_sync(self, connection: sqlite3.Connection, *, now: float | None = None) -> None:
        """Remove expired rows from the SQLite store.

        Args:
            connection: 当前 SQLite 连接。
            now: 当前时间戳；为空时内部自动获取。

        Returns:
            None
        """

        current = _now() if now is None else now
        connection.execute(
            "DELETE FROM cache_entries WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (current,),
        )

    @staticmethod
    def _serialize(value: Any) -> bytes:
        """Serialize a Python value into bytes.

        Args:
            value: 待序列化的原始值。

        Returns:
            bytes: 可落盘的二进制表示。
        """

        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        return str(value).encode("utf-8")

    @staticmethod
    def _deserialize(value: bytes | None, *, decode_responses: bool):
        """Deserialize cached bytes into the expected Python type.

        Args:
            value: 已读取出的二进制值。
            decode_responses: 是否按 UTF-8 解码为 ``str``。

        Returns:
            str | bytes | None: 反序列化后的缓存值。
        """

        if value is None:
            return None
        if decode_responses:
            return bytes(value).decode("utf-8")
        return bytes(value)


LocalCacheStore = LocalCache
