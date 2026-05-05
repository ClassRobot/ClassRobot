"""兼容旧导入路径的本地缓存封装。

实际实现已经迁移到 :mod:`utils.cache.local_cache`，这里仅保留向后兼容。
"""

from .local_cache import LocalCache, LocalCacheStore, _now

__all__ = ["_now", "LocalCache", "LocalCacheStore"]
