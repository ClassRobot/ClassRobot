from qcloud_cos import CosConfig
from pydantic import Extra, BaseModel
from nonebot import logger, get_driver


class Config(BaseModel, extra=Extra.ignore):
    """描述对象存储上传所需的配置项。"""
    cos_secret_id: str | None = None
    cos_secret_key: str | None = None
    region: str | None = None
    bucket: str | None = None
    scheme: str = "https"

    def __bool__(self) -> bool:
        """返回布尔值。"""
        return all([self.cos_secret_id, self.cos_secret_key, self.region, self.bucket])


plugin_config = Config(**get_driver().config.dict())
try:
    cos_config = CosConfig(
        Region=plugin_config.region,
        SecretId=plugin_config.cos_secret_id,
        SecretKey=plugin_config.cos_secret_key,
        Scheme=plugin_config.scheme,
    )
except Exception as e:
    cos_config = None
    logger.exception(e)
