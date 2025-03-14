from pathlib import Path

from filetype import guess
from httpx import AsyncClient
from aiofiles import open as async_open
from comtypes.client import CreateObject
from filetype.types import DOCUMENT, document


class File2Image:
    def __init__(self, file: Path | str | bytes) -> None:
        if isinstance(file, bytes):
            self.file_bytes = file
            self.file = None
        elif isinstance(file, (Path, str)):
            self.file_bytes: bytes | None = None
            self.file = file
        else:
            raise TypeError("file must be bytes, str or Path")

    async def read_bytes(self) -> bytes:
        if self.file_bytes:
            return self.file_bytes
        elif isinstance(self.file, Path):
            async with async_open(self.file, "rb") as f:
                self.file_bytes = await f.read()
                return self.file_bytes
        elif isinstance(self.file, str):
            async with AsyncClient() as client:
                response = await client.get(self.file)
                self.file_bytes = response.content
                return self.file_bytes
        else:
            raise TypeError("file must be bytes, str or Path")

    async def await_init(self):
        await self.read_bytes()
        self.mime = guess(self.file_bytes)
        # 检查文件是否是Document类型，否则报错
        if self.mime not in DOCUMENT:
            self.mime = None
        return self

    async def to_image(self):
        if self.mime in (document.Ppt, document.Pptx):
            ...

    def __await__(self):
        return self.await_init().__await__()
