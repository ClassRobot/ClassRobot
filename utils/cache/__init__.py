from aioredis import Redis

from .config import plugin_config

redis_db: dict[int, Redis] = {}


def get_cache(db: int = 0, decode_responses: bool = True) -> Redis:
    if db in redis_db:
        return redis_db[db]
    return Redis(
        host=plugin_config.cache_host,
        port=plugin_config.cache_port,
        db=db,
        decode_responses=decode_responses,
    )


async def set(key: str, value: str, ex: int = 0, db: int = 0):
    async with get_cache(db) as cache:
        await cache.set(key, value, ex=ex)


async def get(key: str, db: int = 0):
    async with get_cache(db) as cache:
        return await cache.get(key)


async def get_and_delete(key: str, db: int = 0) -> str | None:
    """获取并删除"""
    async with get_cache(db) as cache:
        value = await cache.get(key)
        await cache.delete(key)
        return value
