from nonebot import get_driver
from qcloud_cos import CosConfig
from pydantic import Extra, BaseModel


class Config(BaseModel, extra=Extra.ignore):
    cos_secret_id: str
    cos_secret_key: str
    region: str
    bucket: str
    scheme: str = "https"


plugin_config = Config(**get_driver().config.dict())
cos_config = CosConfig(
    Region=plugin_config.region,
    SecretId=plugin_config.cos_secret_id,
    SecretKey=plugin_config.cos_secret_key,
    Scheme=plugin_config.scheme,
)
