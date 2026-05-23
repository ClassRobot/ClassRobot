from __future__ import annotations

from hashlib import md5
from pathlib import Path

from httpx import AsyncClient
from nonebot import logger, get_driver
from qcloud_cos import CosConfig, CosS3Client
from pydantic import Extra, BaseModel

from src.shared.tools.sync import run_sync


class ObjectStoreConfig(BaseModel, extra=Extra.ignore):
    """描述对象存储上传所需的配置项。"""

    cos_secret_id: str | None = None
    cos_secret_key: str | None = None
    region: str | None = None
    bucket: str | None = None
    scheme: str = "https"

    def __bool__(self) -> bool:
        """判断对象存储配置是否完整。"""

        return all([self.cos_secret_id, self.cos_secret_key, self.region, self.bucket])


plugin_config = ObjectStoreConfig(**get_driver().config.dict())
try:
    cos_config = CosConfig(
        Region=plugin_config.region,
        SecretId=plugin_config.cos_secret_id,
        SecretKey=plugin_config.cos_secret_key,
        Scheme=plugin_config.scheme,
    )
except Exception as error:
    cos_config = None
    logger.exception(error)


def md5_filename(file_content: bytes, upper: bool = True) -> str:
    """根据文件内容生成 MD5 文件名。"""

    value = md5(file_content).hexdigest()
    return value.upper() if upper else value


async def upload_file(file_content: bytes | Path, file_name: str | None = None, suffix: str | None = None) -> str:
    """把文件上传到 COS 并返回可访问链接。

    Args:
        file_content: 文件字节或本地文件路径。
        file_name: 可选目标文件名；未提供时使用内容 MD5。
        suffix: 可选文件后缀。

    Returns:
        str: 上传后的对象访问地址。
    """

    if isinstance(file_content, Path):
        file_name = file_name or file_content.name
        file_content = file_content.read_bytes()
    else:
        file_name = file_name or md5_filename(file_content)
    if suffix:
        file_name += suffix
    client = CosS3Client(cos_config)
    await run_sync(client.put_object)(plugin_config.bucket, file_content, file_name)
    object_url = await run_sync(client.get_object_url)(plugin_config.bucket, file_name)
    return object_url


async def download_file_upload(
    url: str,
    filename: str | None = None,
    *,
    suffix: str = "",
    headers: dict | None = None,
    upper: bool = True,
) -> str:
    """下载远程文件并上传到对象存储。"""

    async with AsyncClient(headers=headers) as client:
        response = await client.get(url)
        if filename is None:
            filename = md5_filename(response.content, upper)
        filename += suffix
        return await upload_file(response.content, filename)
