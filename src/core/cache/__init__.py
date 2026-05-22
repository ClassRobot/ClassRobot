from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Literal

from nonebot import logger

from src.platform.config import cache_dir

from .config import plugin_config
from .local_cache import LocalCache
from .redis_cache import RedisCache, is_recoverable_redis_error

BackendKind = Literal["redis", "local"]

cache_clients: dict[tuple[int, bool], "CacheClient"] = {}
local_caches: dict[Path, LocalCache] = {}
active_backend_kind: BackendKind | None = None
backend_lock: asyncio.Lock | None = None
backend_warning_logged = False


def get_cache(db: int = 0, decode_responses: bool = True) -> "CacheClient":
    """Return a shared cache client for the given logical database.

    默认会优先尝试 Redis；若当前配置允许兜底且 Redis 不可达，
    则统一切换到本地 SQLite 缓存。

    Args:
        db: Redis 逻辑库编号；在本地兜底模式下会映射为命名空间。
        decode_responses: 是否把读取结果按 UTF-8 解码为字符串。

    Returns:
        CacheClient: 可屏蔽 Redis 与本地缓存差异的统一客户端。
    """

    key = (db, decode_responses)
    if key not in cache_clients:
        cache_clients[key] = CacheClient(db=db, decode_responses=decode_responses)
    return cache_clients[key]


def get_cache_storage_path() -> Path:
    """Return the filesystem path used by the cache module.

    该路径当前主要承载本地 SQLite 缓存与 Redis 故障时的兜底存储，
    因此不再局限于“本地缓存路径”的语义。

    Returns:
        Path: 当前缓存模块实际使用的持久化路径。
    """

    if plugin_config.storage_path:
        return Path(plugin_config.storage_path).expanduser()
    return cache_dir / "cache_fallback.sqlite3"


def get_cache_local_path() -> Path:
    """Return the local cache path for compatibility.

    Returns:
        Path: 与 ``get_cache_storage_path`` 相同的缓存持久化路径。
    """

    return get_cache_storage_path()


def get_cache_backend_hint() -> str:
    """Return a human-readable hint for the active cache backend.

    Returns:
        str: 当前缓存后端提示值，可能为 ``"redis"``、``"local"`` 或 ``"auto"``。
    """

    if plugin_config.cache_backend == "local":
        return "local"
    if plugin_config.cache_backend == "redis":
        return "redis"
    return active_backend_kind or "auto"


def _get_local_cache() -> LocalCache:
    """Return the shared local cache backend for the current configuration.

    Returns:
        LocalCache: 与当前配置路径绑定的本地缓存后端实例。
    """

    path = get_cache_storage_path()
    if path not in local_caches:
        local_caches[path] = LocalCache(path)
    return local_caches[path]


def _get_backend_lock() -> asyncio.Lock:
    """Return the runtime lock used for backend switching.

    Returns:
        asyncio.Lock: 用于保护缓存后端切换的异步锁。
    """

    global backend_lock

    if backend_lock is None:
        backend_lock = asyncio.Lock()
    return backend_lock


async def _probe_redis() -> bool:
    """Probe whether Redis is reachable with the current configuration.

    Returns:
        bool: Redis 可用时返回 ``True``，不可用时返回 ``False``。
    """

    return await RedisCache(
        host=plugin_config.cache_host,
        port=plugin_config.cache_port,
        db=0,
        decode_responses=True,
        connect_timeout=plugin_config.cache_connect_timeout,
    ).probe()


async def _switch_backend(kind: BackendKind, *, reason: BaseException | None = None) -> BackendKind:
    """Switch and record the active cache backend for the current process.

    Args:
        kind: 目标后端类型。
        reason: 触发切换的异常或说明，用于日志记录。

    Returns:
        BackendKind: 切换完成后实际生效的后端类型。
    """

    global active_backend_kind
    global backend_warning_logged

    async with _get_backend_lock():
        if active_backend_kind == kind:
            return kind

        if kind == "local":
            await _get_local_cache().initialize()
            if reason is not None and not backend_warning_logged:
                logger.warning(
                    "Redis 不可用，缓存后端已自动切换到本地 SQLite 兜底存储: {}",
                    reason,
                )
                backend_warning_logged = True

        active_backend_kind = kind
        return kind


async def _resolve_backend() -> BackendKind:
    """Resolve the cache backend to use for the current operation.

    Returns:
        BackendKind: 当前操作应使用的后端类型。

    Raises:
        RuntimeError: 当 Redis 不可用且当前配置不允许本地兜底时抛出。
    """

    configured = plugin_config.cache_backend
    if configured == "local":
        return await _switch_backend("local")
    if configured == "redis":
        return await _switch_backend("redis")
    if active_backend_kind is not None:
        return active_backend_kind
    if await _probe_redis():
        return await _switch_backend("redis")
    if plugin_config.cache_fallback_enabled:
        return await _switch_backend("local", reason=RuntimeError("Redis service unreachable"))
    raise RuntimeError("Redis 不可用，且未启用本地缓存兜底")


class CacheClient:
    """Expose a unified cache interface over Redis and local fallback storage.

    外部调用方只需要面向 `CacheClient` 编程，不需要关心当前缓存后端
    是 Redis 还是本地 SQLite，也不需要自己手动处理兜底切换逻辑。

    Attributes:
        db: 逻辑缓存分区编号。
        decode_responses: 是否把读取结果按 UTF-8 解码为字符串。
        redis_cache: Redis 后端封装。
    """

    def __init__(self, db: int = 0, decode_responses: bool = True):
        """Initialize a cache client wrapper.

        Args:
            db: Redis 逻辑库编号；本地兜底模式下对应命名空间。
            decode_responses: 是否把读取结果按 UTF-8 解码为字符串。
        """

        self.db = db
        self.decode_responses = decode_responses
        self.redis_cache = RedisCache(
            host=plugin_config.cache_host,
            port=plugin_config.cache_port,
            db=db,
            decode_responses=decode_responses,
            connect_timeout=plugin_config.cache_connect_timeout,
        )

    @property
    def local_cache(self) -> LocalCache:
        """Return the shared local cache backend.

        Returns:
            LocalCache: 当前配置下复用的本地缓存后端实例。
        """

        return _get_local_cache()

    async def __aenter__(self) -> "CacheClient":
        """Enter the async context manager.

        Returns:
            CacheClient: 当前统一缓存客户端自身。
        """

        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> bool:
        """Exit the async context manager.

        Args:
            exc_type: 异常类型。
            exc_value: 异常值。
            traceback: 异常回溯。

        Returns:
            bool: 始终返回 ``False``，表示不吞掉异常。
        """

        return False

    async def set(self, key: str, value: Any, ex: int = 0) -> bool:
        """Store a cache value.

        Args:
            key: 缓存键。
            value: 待写入的原始值。
            ex: 过期时间，单位秒；``ex <= 0`` 时表示不设置 TTL。

        Returns:
            bool: 写入成功时返回 ``True``。
        """

        ttl = ex if ex > 0 else None
        return await self._call_backend("set", key, value, ex=ttl)

    async def get(self, key: str):
        """Read a cache value.

        Args:
            key: 缓存键。

        Returns:
            str | bytes | None: 命中时返回缓存值；未命中时返回 ``None``。
        """

        return await self._call_backend("get", key)

    async def delete(self, *keys: str) -> int:
        """Delete one or more cache keys.

        Args:
            *keys: 待删除的一个或多个缓存键。

        Returns:
            int: 成功删除的键数量。
        """

        return await self._call_backend("delete", *keys)

    async def ping(self) -> bool:
        """Check whether the current cache backend is available.

        Returns:
            bool: 当前缓存后端可用时返回 ``True``。
        """

        return await self._call_backend("ping")

    async def _call_backend(self, operation: str, *args, **kwargs):
        """Call the active backend and retry on local fallback when allowed.

        Args:
            operation: 要调用的后端方法名。
            *args: 传递给后端方法的位置参数。
            **kwargs: 传递给后端方法的关键字参数。

        Returns:
            Any: 后端方法的返回值。

        Raises:
            Exception: 当当前配置不允许回退时，透传底层异常。
        """

        backend_name = await _resolve_backend()
        try:
            return await self._invoke_backend(backend_name, operation, *args, **kwargs)
        except Exception as error:
            if not self._can_fallback_to_local(backend_name, error):
                raise
            await _switch_backend("local", reason=error)
            return await self._invoke_backend("local", operation, *args, **kwargs)

    async def _invoke_backend(self, backend_name: BackendKind, operation: str, *args, **kwargs):
        """Invoke a concrete backend operation.

        Args:
            backend_name: 目标后端名称。
            operation: 后端方法名。
            *args: 位置参数。
            **kwargs: 关键字参数。

        Returns:
            Any: 后端方法的返回值。
        """

        if backend_name == "local":
            method = getattr(self.local_cache, operation)
            if operation == "ping":
                return await method()
            if operation == "get":
                kwargs.setdefault("decode_responses", self.decode_responses)
            return await method(self.db, *args, **kwargs)

        method = getattr(self.redis_cache, operation)
        return await method(*args, **kwargs)

    def _can_fallback_to_local(self, backend_name: BackendKind, error: BaseException) -> bool:
        """Check whether the current failure should switch to local cache.

        Args:
            backend_name: 当前执行操作时使用的后端名称。
            error: 捕获到的底层异常。

        Returns:
            bool: 当前配置允许回退且异常属于 Redis 可恢复错误时返回 ``True``。
        """

        return (
            backend_name == "redis"
            and plugin_config.cache_backend == "auto"
            and plugin_config.cache_fallback_enabled
            and is_recoverable_redis_error(error)
        )


async def set(key: str, value: Any, ex: int = 0, db: int = 0) -> None:
    """Store a cache value through the shared cache client.

    Args:
        key: 缓存键。
        value: 待写入的值。
        ex: 过期时间，单位秒；``ex <= 0`` 时表示不设置 TTL。
        db: 逻辑缓存分区编号。

    Returns:
        None
    """

    await get_cache(db).set(key, value, ex=ex)


async def get(key: str, db: int = 0):
    """Read a cache value through the shared cache client.

    Args:
        key: 缓存键。
        db: 逻辑缓存分区编号。

    Returns:
        str | bytes | None: 命中时返回缓存值；未命中时返回 ``None``。
    """

    return await get_cache(db).get(key)


async def get_and_delete(key: str, db: int = 0):
    """Read a cache value and delete it immediately.

    Args:
        key: 缓存键。
        db: 逻辑缓存分区编号。

    Returns:
        str | bytes | None: 命中时返回缓存值；未命中时返回 ``None``。
    """

    cache = get_cache(db)
    value = await cache.get(key)
    await cache.delete(key)
    return value


def _reset_runtime_state() -> None:
    """Reset module-level cache runtime state for tests.

    Returns:
        None
    """

    global active_backend_kind
    global backend_warning_logged
    global backend_lock

    cache_clients.clear()
    local_caches.clear()
    active_backend_kind = None
    backend_lock = None
    backend_warning_logged = False


__all__ = [
    "CacheClient",
    "get_cache",
    "get_cache_backend_hint",
    "get_cache_storage_path",
    "get_cache_local_path",
    "set",
    "get",
    "get_and_delete",
]
