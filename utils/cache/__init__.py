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
