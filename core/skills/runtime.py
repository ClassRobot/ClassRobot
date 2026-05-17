from asyncio import gather
from base64 import b64encode
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeAlias

from .base import BaseProjectSkill, SkillManifest

ImageInput: TypeAlias = Any

if TYPE_CHECKING:
    from utils.tools.docs2img import File2Image


def _load_pil_image(image: ImageInput):
    """将多种输入统一转换为 PIL 图片对象。"""
    import cv2
    import numpy as np
    from PIL import Image

    if isinstance(image, Image.Image):
        return image.convert("RGB")
    if isinstance(image, np.ndarray):
        if image.ndim == 2:
            return Image.fromarray(image).convert("RGB")
        return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    if isinstance(image, bytes):
        return Image.open(BytesIO(image)).convert("RGB")

    path = Path(image)
    return Image.open(path).convert("RGB")


def _load_cv_image(image: ImageInput):
    """将多种输入统一转换为 OpenCV 图片矩阵。"""
    import cv2
    import numpy as np

    if isinstance(image, np.ndarray):
        return image.copy()
    pil_image = _load_pil_image(image)
    return cv2.cvtColor(np.asarray(pil_image), cv2.COLOR_RGB2BGR)


class DocumentToImageSkill(BaseProjectSkill):
    """封装文档转图片相关的 skill 运行时能力。"""

    skill_name = "document-to-image"

    async def convert(self, file: Path | str | bytes, save_path: Path | None = None) -> "File2Image":
        """将文件转换为可上传图片集合。

        参数:
            file (Path | str | bytes): 文档路径、文档链接或原始字节内容。
            save_path (Path | None): 临时保存目录。

        返回:
            File2Image: 转换完成后的文件对象。
        """
        from utils.tools.docs2img import File2Image

        return await File2Image(file, save_path=save_path)

    async def convert_local_file(self, file_path: Path, output_dir: Path) -> list[Path]:
        """将本地文档转换为图片文件。

        参数:
            file_path (Path): 本地文档路径。
            output_dir (Path): 图片输出目录。

        返回:
            list[Path]: 生成的图片文件路径列表。
        """
        from utils.tools.docs2img.to_img import doc2img, pdf2img, ppt2img

        suffix = file_path.suffix.lower()
        if suffix in {".ppt", ".pptx"}:
            return await ppt2img(file_path, output_dir)
        if suffix in {".doc", ".docx"}:
            return await doc2img(file_path, output_dir)
        if suffix == ".pdf":
            return await pdf2img(file_path, output_dir)
        raise ValueError(f"不支持的文档类型: {file_path.suffix}")


class OCRSkill(BaseProjectSkill):
    """封装 OCR 检测与识别相关的 skill 运行时能力。"""

    skill_name = "ocr"

    def __init__(self, manifest: SkillManifest) -> None:
        """初始化 OCR skill。"""
        super().__init__(manifest)
        from utils.tools.ocr.crnn import CRNNHandle
        from utils.tools.ocr.dbnet.dbnet_infer import DBNET

        self.detector = DBNET()
        self.recognizer = CRNNHandle()

    def read_code(self, image: ImageInput) -> str:
        """识别验证码或单行短文本。

        参数:
            image (ImageInput): 输入图片。

        返回:
            str: 识别得到的文本内容。
        """
        import cv2
        import numpy as np
        from PIL import Image

        cv_image = _load_cv_image(image)
        textimg_uint8 = np.clip(cv_image, 0, 255).astype(np.uint8)
        pil_image = Image.fromarray(cv2.cvtColor(textimg_uint8, cv2.COLOR_BGR2RGB))
        return self.recognizer.predict_rbg(pil_image).replace(" ", "")

    def read_lines(self, image: ImageInput, short_size: int = 1024) -> list[str]:
        """识别图片中的多行文本。

        参数:
            image (ImageInput): 输入图片。
            short_size (int): 文本检测时的短边缩放尺寸。

        返回:
            list[str]: 识别出的文本行列表。
        """
        import cv2
        import numpy as np
        from PIL import Image

        from utils.tools.ocr.utils import get_rotate_crop_image, sorted_boxes

        cv_image = _load_cv_image(image)
        boxes, _ = self.detector.process(cv_image, short_size=short_size)
        if len(boxes) == 0:
            return []

        lines: list[str] = []
        for box in sorted_boxes(np.asarray(boxes, dtype=np.float32)):
            cropped = get_rotate_crop_image(cv_image, box.astype(np.float32))
            if cropped is None or cropped.size == 0:
                continue
            pil_image = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
            text = self.recognizer.predict_rbg(pil_image).strip()
            if text:
                lines.append(text)
        return lines

    def read_text(self, image: ImageInput, short_size: int = 1024, joiner: str = "\n") -> str:
        """识别图片中的主要文本内容。

        参数:
            image (ImageInput): 输入图片。
            short_size (int): 文本检测时的短边缩放尺寸。
            joiner (str): 多行文本的拼接分隔符。

        返回:
            str: 识别出的完整文本。
        """
        lines = self.read_lines(image, short_size=short_size)
        if lines:
            return joiner.join(lines)
        return self.read_code(image)


class QRCodeSkill(BaseProjectSkill):
    """封装二维码生成与解析相关的 skill 运行时能力。"""

    skill_name = "qr-code"

    def encode(self, text: str) -> bytes:
        """将文本编码为二维码图片。

        参数:
            text (str): 需要写入二维码的文本。

        返回:
            bytes: 二维码图片字节数据。
        """
        from qrcode import QRCode

        image_bytes = BytesIO()
        code_img = QRCode()
        code_img.add_data(text)
        code_img.make(fit=True)
        image = code_img.make_image()
        image.save(image_bytes)
        return image_bytes.getvalue()

    def decode(self, image: ImageInput) -> list[str]:
        """从图片中解析二维码文本。

        参数:
            image (ImageInput): 输入图片。

        返回:
            list[str]: 识别出的二维码文本列表。
        """
        from pyzbar.pyzbar import decode as decode_qr_image

        pil_image = _load_pil_image(image)
        texts: list[str] = []
        for item in decode_qr_image(pil_image):
            value = item.data.decode("utf-8")
            if value and value not in texts:
                texts.append(value)
        return texts

    def decode_one(self, image: ImageInput) -> str | None:
        """从图片中解析首个二维码文本。"""
        results = self.decode(image)
        return results[0] if results else None


class MarkdownToImageSkill(BaseProjectSkill):
    """封装 Markdown 渲染相关的 skill 运行时能力。"""

    skill_name = "markdown-to-image"

    async def to_html(self, md: str) -> str:
        """将 Markdown 转换为 HTML。

        参数:
            md (str): Markdown 原文。

        返回:
            str: 渲染后的 HTML 字符串。
        """
        from nonebot_plugin_htmlrender.data_source import env, markdown, read_tpl

        template = env.get_template("markdown.html")
        md = markdown.markdown(
            md,
            extensions=[
                "pymdownx.tasklist",
                "tables",
                "fenced_code",
                "codehilite",
                "mdx_math",
                "pymdownx.tilde",
            ],
            extension_configs={"mdx_math": {"enable_dollar_delimiter": True}},
        )

        extra = ""
        if "math/tex" in md:
            katex_css = await read_tpl("katex/katex.min.b64_fonts.css")
            katex_js = await read_tpl("katex/katex.min.js")
            mhchem_js = await read_tpl("katex/mhchem.min.js")
            mathtex_js = await read_tpl("katex/mathtex-script-type.min.js")
            extra = (
                f'<style type="text/css">{katex_css}</style>'
                f"<script defer>{katex_js}</script>"
                f"<script defer>{mhchem_js}</script>"
                f"<script defer>{mathtex_js}</script>"
            )

        css = await read_tpl("github-markdown-light.css") + await read_tpl("pygments-default.css")
        return await template.render_async(md=md, css=css, extra=extra)

    async def to_image(self, md: str) -> bytes:
        """将 Markdown 直接渲染为图片。

        参数:
            md (str): Markdown 原文。

        返回:
            bytes: 渲染后的图片字节数据。
        """
        from nonebot_plugin_htmlrender import md_to_pic

        return await md_to_pic(md)

    async def html_to_image(self, html: str, viewport: dict[str, Any] | None = None) -> bytes:
        """将 HTML 内容渲染为图片。

        参数:
            html (str): HTML 字符串。
            viewport (dict[str, Any] | None): 页面视口配置。

        返回:
            bytes: 渲染后的图片字节数据。
        """
        from nonebot_plugin_htmlrender import html_to_pic

        return await html_to_pic(html, viewport=viewport or {"width": 1080, "height": 10})


class ImageGenerationSkill(BaseProjectSkill):
    """封装文生图、图生图相关的 skill 运行时能力。"""

    skill_name = "image-generation"

    async def generate(self, items: list[Any]) -> list[dict[str, Any]]:
        """根据文本和图片输入生成图片结果。

        参数:
            items (list[Any]): 输入的文本片段或图片对象列表。

        返回:
            list[dict[str, Any]]: 绘图服务返回的响应片段列表。
        """
        from filetype import guess
        from filetype.types import IMAGE
        from httpx import AsyncClient
        from nonebot_plugin_alconna import Image, Text
        from nonebot_plugin_htmlrender import get_new_page

        from utils.config import global_config

        parts: list[dict[str, Any]] = []
        wait_images = []

        async def request_image(item: Image) -> None:
            """将输入图片下载并转换为绘图接口可接受的内联数据。"""
            if item.url is None:
                return
            image_response = await page.request.get(item.url)
            image_bytes = await image_response.body()
            image_b64 = b64encode(image_bytes).decode()
            mime_type = guess(image_bytes)
            if mime_type in IMAGE:
                parts.append({"inline_data": {"mime_type": mime_type.MIME, "data": image_b64}})

        async with get_new_page() as page:
            for item in items:
                if isinstance(item, Text):
                    parts.append({"text": str(item)})
                elif isinstance(item, Image):
                    wait_images.append(request_image(item))
            if wait_images:
                await gather(*wait_images)

        async with AsyncClient(
            base_url="https://generativelanguage.googleapis.com/v1beta",
            proxy=global_config.global_proxy,
            timeout=600,
        ) as client:
            response = await client.post(
                "/models/gemini-2.0-flash-exp-image-generation:generateContent",
                params={"key": global_config.googleapis_key},
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": parts}],
                    "generationConfig": {"responseModalities": ["Text", "Image"]},
                },
            )

        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"]
        except KeyError as error:
            raise ValueError(data) from error
