from pydantic import BaseModel, Extra


class CacheConfig(BaseModel, extra=Extra.ignore):
    cache_host: str = "localhost"
    cache_port: int = 6379
