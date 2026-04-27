import hashlib
from asyncio import wait
from pathlib import Path

import numpy as np
from PIL import Image
from filetype import guess
from httpx import AsyncClient
from utils.tools.sync import run_sync
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
    """将文档统一转换为图片并上传，供 OCR 与多模态流程复用。"""

    def __init__(self, file: Path | str | bytes, save_path: Path | None = None) -> None:
        """初始化文件转图实例。

        参数:
            file (Path | str | bytes): 本地文件路径、远程文件地址或原始字节内容。
            save_path (Path | None): 临时落盘目录；当输入不是本地路径时必须提供。
        """
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
        """计算当前输入文件内容的 MD5 值。

        返回:
            str: 文件内容对应的 MD5 摘要。
        """
        file_bytes = await self.read_bytes()
        return hashlib.md5(file_bytes).hexdigest()

    async def mime(self):
        """识别当前文件的 MIME 类型。

        返回:
            Any: `filetype.guess` 返回的类型对象。
        """
        file_bytes = await self.read_bytes()
        return guess(file_bytes)

    async def read_bytes(self) -> bytes:
        """读取字节数据。"""
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
        """判断当前文件是否属于支持转换的文档类型。

        返回:
            bool: 如果文件可被转换为图片则返回 `True`。
        """
        mime = await self.mime()
        return isinstance(mime, DOCUMENTS) if mime else False

    async def await_init(self):
        """执行异步初始化，完成文件读取、转图与上传。

        返回:
            File2Image: 初始化完成后的当前实例。
        """
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
        # Group all derived images under a content-addressed directory so downstream
        # upload and cleanup logic can treat one document as a single working set.
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
            # Large documents are merged before upload so later multimodal prompts do
            # not explode into dozens of per-page images.
            upload_tasks = [self.upload_image(img) for img in await run_sync(self.merge_images_if_needed)(images)]
            await wait(upload_tasks)

        return self

    def merge_images_if_needed(self, images: list[Path]) -> list[Path]:
        """在图片过多时纵向合并分页图片。

        参数:
            images (list[Path]): 原始分页图片路径列表。

        返回:
            list[Path]: 控制数量后的图片路径列表。
        """

        if len(images) <= 20:
            return images

        # Calculate how many images to combine per group
        total_images = len(images)
        images_per_group = int(np.ceil(total_images / 20))

        merged_images = []

        for i in range(0, total_images, images_per_group):
            group = images[i : i + images_per_group]

            if len(group) == 1:
                merged_images.append(group[0])
                continue

            # Open images and determine the required dimensions
            pil_images = [Image.open(img) for img in group]
            max_width = max(img.width for img in pil_images)
            total_height = sum(img.height for img in pil_images)

            # Create a new image with the combined dimensions
            merged_image = Image.new("RGB", (max_width, total_height), (255, 255, 255))

            # Paste images vertically
            y_offset = 0
            for img in pil_images:
                merged_image.paste(img, (0, y_offset))
                y_offset += img.height
                img.close()

            # Save the merged image
            output_path = group[0].parent / f"merged_{i//images_per_group}.png"
            merged_image.save(output_path)
            merged_images.append(output_path)
        for img in (i for i in images if i not in merged_images):
            img.unlink(missing_ok=True)
        return merged_images

    async def upload_image(self, file_path: Path):
        """上传转换后的图片，并记录可访问链接。

        参数:
            file_path (Path): 需要上传的图片文件路径。
        """
        self.images.append(await upload_file(file_path, file_path.parent.name + file_path.name))

    def __await__(self):
        """允许通过 `await File2Image(...)` 直接触发初始化流程。"""
        return self.await_init().__await__()
