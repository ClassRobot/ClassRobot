import hashlib
from asyncio import wait
from pathlib import Path

from filetype import guess
from httpx import AsyncClient
from aiofiles import open as async_open
from utils.tools.cos import upload_file
from filetype.types import archive, document

from .to_img import doc2img, pdf2img, ppt2img

DOCUMENTS = (
    document.Doc,
    document.Docx,
    document.Ppt,
    document.Pptx,
    archive.Pdf,
)


class File2Image:
    def __init__(self, file: Path | str | bytes, save_path: Path | None = None) -> None:
        self.save_path = save_path  # 将数据保存在指定文件夹，之后只从这里读取
        self.images = []
        if isinstance(file, bytes):
            self.file_bytes = file
            self.file = None
        elif isinstance(file, (Path, str)):
            self.file_bytes: bytes | None = None
            self.file = file
        else:
            raise TypeError("file must be bytes, str or Path")

    async def md5(self) -> str:
        file_bytes = await self.read_bytes()
        return hashlib.md5(file_bytes).hexdigest()

    async def mime(self):
        file_bytes = await self.read_bytes()
        return guess(file_bytes)

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

    async def is_processable(self) -> bool:
        """Check if the file type can be processed by this class.

        Returns:
            bool: True if the file can be processed, False otherwise.
        """
        mime = await self.mime()
        return isinstance(mime, DOCUMENTS) if mime else False

    async def await_init(self):
        file_bytes = await self.read_bytes()
        mime = guess(file_bytes)
        file_md5 = await self.md5()
        images: list[Path] = []
        if not isinstance(mime, DOCUMENTS):
            return self

        # save file

        if self.save_path is not None:
            file_path = self.save_path / f"{file_md5}.{mime.extension}"
            file_path.write_bytes(file_bytes)
        elif isinstance(self.file, Path):
            file_path = self.file
        else:
            raise ValueError("save_path must be specified if file is not a Path object")
        print(file_path)
        output_dir = file_path.parent / file_md5
        output_dir.mkdir(exist_ok=True, parents=True)
        if output_dir.exists() or not (images := list(output_dir.iterdir())):
            try:
                if isinstance(mime, (document.Ppt, document.Pptx)):
                    images = await ppt2img(file_path, output_dir)
                elif isinstance(mime, (document.Doc, document.Docx)):
                    images = await doc2img(file_path, output_dir)
                elif isinstance(mime, archive.Pdf):
                    images = await pdf2img(file_path, output_dir)
            except Exception as e:
                output_dir.rmdir()
                raise e

        if images:
            upload_tasks = [self.upload_image(img) for img in images]
            await wait(upload_tasks)

        return self

    async def upload_image(self, file_path: Path):
        self.images.append(await upload_file(file_path, file_path.parent.name + file_path.name))

    def __await__(self):
        return self.await_init().__await__()
