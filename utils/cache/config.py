from typing import Literal
from nonebot import get_driver
from pydantic import BaseModel, Extra


class CacheConfig(BaseModel, extra=Extra.ignore):
    """描述缓存服务连接与回退行为的配置项。

    Attributes:
        cache_host: Redis 服务主机名。
        cache_port: Redis 服务端口。
        cache_backend: 缓存后端模式。
            - ``"auto"``: 优先 Redis，失败时按配置回退到本地 SQLite。
            - ``"redis"``: 仅使用 Redis，不做本地回退。
            - ``"local"``: 强制使用本地 SQLite 缓存。
        cache_fallback_enabled: 当 ``cache_backend`` 为 ``"auto"`` 时，
            是否允许回退到本地 SQLite。
        cache_connect_timeout: Redis 连接与读写探测超时时间，单位秒。
        cache_path: 缓存模块使用的统一持久化路径配置。
            当前主要用于本地 SQLite 存储，同时也是 Redis 模式下的
            统一兜底路径语义。
        cache_local_path: 兼容旧配置名，语义等同于 ``cache_path``。
    """

    cache_host: str = "localhost"
    cache_port: int = 6379
    cache_backend: Literal["auto", "redis", "local"] = "auto"
    cache_fallback_enabled: bool = True
    cache_connect_timeout: float = 0.5
    cache_path: str | None = None
    cache_local_path: str | None = None

    @property
    def storage_path(self) -> str | None:
        """Return the effective cache storage path.

        Returns:
            str | None: 优先返回 ``cache_path``，否则回退到旧配置
            ``cache_local_path``。
        """

        return self.cache_path or self.cache_local_path


plugin_config = CacheConfig.parse_obj(get_driver().config.dict())
