from __future__ import annotations

from contextlib import suppress
from typing import Any

from src.shared.packages.aioredis import Redis
from src.shared.packages.aioredis.exceptions import ConnectionError as RedisConnectionError
from src.shared.packages.aioredis.exceptions import TimeoutError as RedisTimeoutError

RECOVERABLE_REDIS_ERRORS = (RedisConnectionError, RedisTimeoutError, OSError)


def is_recoverable_redis_error(error: BaseException) -> bool:
    """Check whether a Redis error should trigger local fallback.

    Args:
        error: 捕获到的底层异常。

    Returns:
        bool: 属于连接类、超时类或网络类异常时返回 ``True``。
    """

    return isinstance(error, RECOVERABLE_REDIS_ERRORS)


class RedisCache:
    """Provide a Redis-backed cache backend.

    当前实现采用“按次创建、按次关闭”真实 Redis 客户端的方式，
    让上层 `CacheClient` 更专注于后端切换而不是连接生命周期管理。

    Attributes:
        host: Redis 主机名。
        port: Redis 端口。
        db: Redis 逻辑库编号。
        decode_responses: 是否把读取结果按 UTF-8 解码为字符串。
        connect_timeout: 连接与读写探测超时时间，单位秒。
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        db: int = 0,
        decode_responses: bool = True,
        connect_timeout: float = 0.5,
    ):
        """Initialize the Redis cache backend.

        Args:
            host: Redis 主机名。
            port: Redis 端口。
            db: Redis 逻辑库编号。
            decode_responses: 是否把读取结果按 UTF-8 解码为字符串。
            connect_timeout: 连接与读写探测超时时间，单位秒。
        """

        self.host = host
        self.port = port
        self.db = db
        self.decode_responses = decode_responses
        self.connect_timeout = connect_timeout

    def _build_client(self) -> Redis:
        """Build a short-lived Redis client instance.

        Returns:
            Redis: 基于当前后端配置构造出的 Redis 客户端。
        """

        return Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            decode_responses=self.decode_responses,
            socket_timeout=self.connect_timeout,
            socket_connect_timeout=self.connect_timeout,
            retry_on_timeout=False,
        )

    async def probe(self) -> bool:
        """Probe whether Redis is reachable.

        Returns:
            bool: Redis 可用时返回 ``True``，不可用时返回 ``False``。
        """

        try:
            return bool(await self.ping())
        except RECOVERABLE_REDIS_ERRORS:
            return False

    async def ping(self) -> bool:
        """Check whether the Redis backend is available.

        Returns:
            bool: Redis 可用时返回 ``True``。
        """

        client = self._build_client()
        try:
            return bool(await client.ping())
        finally:
            with suppress(Exception):
                await client.close()

    async def set(self, key: str, value: Any, ex: int | None = None) -> bool:
        """Store a value in Redis.

        Args:
            key: 缓存键。
            value: 待写入的原始值。
            ex: 过期时间，单位秒；为 ``None`` 时表示不过期。

        Returns:
            bool: 写入成功时返回 ``True``。
        """

        client = self._build_client()
        try:
            return await client.set(key, value, ex=ex)
        finally:
            with suppress(Exception):
                await client.close()

    async def get(self, key: str):
        """Read a value from Redis.

        Args:
            key: 缓存键。

        Returns:
            str | bytes | None: 命中时返回缓存值；未命中时返回 ``None``。
        """

        client = self._build_client()
        try:
            return await client.get(key)
        finally:
            with suppress(Exception):
                await client.close()

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys from Redis.

        Args:
            *keys: 待删除的一个或多个缓存键。

        Returns:
            int: 成功删除的键数量。
        """

        client = self._build_client()
        try:
            return await client.delete(*keys)
        finally:
            with suppress(Exception):
                await client.close()
