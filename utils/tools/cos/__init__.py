from hashlib import md5

from httpx import AsyncClient
from utils.sync import run_sync
from qcloud_cos import CosS3Client
from nonebot_plugin_alconna import Image

from .config import cos_config, plugin_config


def md5_filename(file_content: bytes, upper: bool = True) -> str:
    return (
        md5(file_content).hexdigest().upper()
        if upper
        else md5(file_content).hexdigest()
    )


async def upload_file(file_content: bytes, file_name: str | None = None) -> str:
    client = CosS3Client(cos_config)
    file_name = file_name or md5_filename(file_content)
    await run_sync(client.put_object)(plugin_config.bucket, file_content, file_name)
    object_url = await run_sync(client.get_object_url)(plugin_config.bucket, file_name)
    return object_url


async def download_file_upload(
    url: str,
    filename: str | None = None,
    *,
    suffix: str = "",
    upper: bool = True,
) -> str:
    """下次链接文件并且上传文件

    Args:
        url (str): 文件链接
        filename (str | None, optional): 文件名. Defaults to None.
        suffix (str, optional): 文件格式. Defaults to "".
        upper (bool, optional): 是否需要大写. Defaults to True.

    Returns:
        str: 上传后的下载链接
    """
    async with AsyncClient() as client:
        response = await client.get(url)
        if filename is None:
            filename = md5_filename(response.content, upper)
        filename += suffix
        return await upload_file(response.content, filename)


async def image_message(file_name: str, file_content: bytes) -> Image:
    url: str = await upload_file(file_content, file_name)
    return Image(url=url)
