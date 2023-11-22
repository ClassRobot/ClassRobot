from hashlib import md5

from httpx import AsyncClient
from utils.sync import run_sync
from qcloud_cos import CosS3Client

from .config import cos_config, plugin_config


async def upload_file(file_name: str, file_content: bytes) -> str:
    client = CosS3Client(cos_config)
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
    async with AsyncClient() as client:
        response = await client.get(url)
        if filename is None:
            filename = (
                md5(response.content).hexdigest().upper()
                if upper
                else md5(response.content).hexdigest()
            )
        filename += suffix
        return await upload_file(filename, response.content)
