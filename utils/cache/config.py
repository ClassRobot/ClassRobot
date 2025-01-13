from nonebot import get_driver
from pydantic import Extra, BaseModel


class CacheConfig(BaseModel, extra=Extra.ignore):
    cache_host: str = "localhost"
    cache_port: int = 6379


plugin_config = CacheConfig.parse_obj(get_driver().config.dict())
