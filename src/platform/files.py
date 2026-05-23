from __future__ import annotations

from pathlib import Path
from typing import Any, overload

from nonebot_plugin_alconna import File, Other
from nonebot_plugin_htmlrender import get_new_page


@overload
async def download_file(
    uri: bytes,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    to_path: str | Path,
) -> bytes:
    """下载或落盘文件内容。"""


@overload
async def download_file(
    uri: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    to_path: str | Path | None = None,
) -> bytes:
    """下载或落盘文件内容。"""


async def download_file(
    uri: str | bytes,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    to_path: str | Path | None = None,
) -> bytes:
    """下载远程文件或把已有字节写入目标路径。

    Args:
        uri: 远程文件地址，或已经获得的文件字节。
        headers: 请求头。
        params: 请求参数。
        to_path: 可选落盘路径；当 ``uri`` 是字节时必须提供。

    Returns:
        bytes: 文件字节内容。
    """

    if not isinstance(uri, str):
        if to_path is None:
            raise ValueError("uri 为 bytes 时必须提供 to_path。")
        Path(to_path).write_bytes(uri)
        return uri
    async with get_new_page() as page:
        response = await page.request.get(uri, headers=headers, params=params)
        body = await response.body()
        if to_path:
            Path(to_path).write_bytes(body)
        return body


def file_or_other_file(file: File | Other) -> File:
    """把 Alconna 的 ``File`` 或适配器原始文件段统一转换为 ``File``。"""

    if isinstance(file, File):
        return file
    if isinstance(file, Other):
        return File(
            name=file.origin.data["file_name"],
            url=file.origin.data["url"],
            id=file.origin.data["file_id"],
        )
    raise TypeError(f"不支持的文件消息类型：{type(file)!r}")


FileOrOtherFile = lambda file: file_or_other_file(file)  # noqa: E731
