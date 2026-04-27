from nonebot import get_driver
from pydantic import Extra, BaseModel


class CacheConfig(BaseModel, extra=Extra.ignore):
    """描述缓存服务连接与行为的配置项。"""

    cache_host: str = "localhost"
    cache_port: int = 6379


plugin_config = CacheConfig.parse_obj(get_driver().config.dict())
