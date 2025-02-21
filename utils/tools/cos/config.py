from nonebot import get_driver
from qcloud_cos import CosConfig
from pydantic import Extra, BaseModel


class Config(BaseModel, extra=Extra.ignore):
    cos_secret_id: str | None = None
    cos_secret_key: str | None = None
    region: str | None = None
    bucket: str | None = None
    scheme: str = "https"
    
    def __bool__(self) -> bool:
        return all([self.cos_secret_id, self.cos_secret_key, self.region, self.bucket])


plugin_config = Config(**get_driver().config.dict())
cos_config = CosConfig(
    Region=plugin_config.region,
    SecretId=plugin_config.cos_secret_id,
    SecretKey=plugin_config.cos_secret_key,
    Scheme=plugin_config.scheme,
)
