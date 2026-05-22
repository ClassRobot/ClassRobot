from hashlib import md5
from pathlib import Path

from httpx import AsyncClient
from qcloud_cos import CosS3Client
from src.shared.tools.sync import run_sync
from nonebot_plugin_alconna import Image

from .config import cos_config, plugin_config


def md5_filename(file_content: bytes, upper: bool = True) -> str:
    """根据内容生成 MD5 文件名。"""
    return md5(file_content).hexdigest().upper() if upper else md5(file_content).hexdigest()


async def upload_file(file_content: bytes | Path, file_name: str | None = None, suffix: str | None = None) -> str:
    """将文件上传到COS

    参数:
        file_content (bytes): 文件内容
        file_name (str | None, optional): 文件名. Defaults to None.
        suffix (str | None, optional): 文件格式(传入的格式需要手动加.). Defaults to None.

    返回:
        str: 返回上传后的下载链接
    """
    if isinstance(file_content, Path):
        file_name = file_name or file_content.name
        file_content = file_content.read_bytes()
    else:
        file_name = file_name or md5_filename(file_content)
    client = CosS3Client(cos_config)
    if suffix:
        file_name += suffix
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
    """下载链接文件并且上传文件

    参数:
        url (str): 文件链接
        filename (str | None, optional): 文件名. Defaults to None.
        suffix (str, optional): 文件格式. Defaults to "".
        upper (bool, optional): 是否需要大写. Defaults to True.

    返回:
        str: 上传后的下载链接
    """
    async with AsyncClient(headers=headers) as client:
        response = await client.get(url)
        if filename is None:
            filename = md5_filename(response.content, upper)
        filename += suffix
        return await upload_file(response.content, filename)


async def image_message(file_name: str, file_content: bytes) -> Image:
    """生成图片上传后的消息内容。"""
    url: str = await upload_file(file_content, file_name)
    return Image(url=url)
