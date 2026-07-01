import logging
from pathlib import Path

import pdf2image
from src.shared.tools.sync import run_sync

logger = logging.getLogger(__name__)

powerpoint = None
word = None

try:
    import comtypes.client
except Exception as err:
    logger.exception(err)


async def ppt2img(file_path: Path, output: Path) -> list[Path]:
    """将 PPT 转换为图片。"""
    global powerpoint
    if powerpoint is None:
        powerpoint = comtypes.client.CreateObject("kwpp.Application")
    ppt = powerpoint.Presentations.Open(str(file_path))
    ppt.SaveAs(str(output), 17)
    ppt.Close()
    return list(output.glob("*.jpg"))


async def doc2pdf(file_path: Path, output: Path) -> Path:
    """将 Word 文档转换为 PDF。"""
    global word
    if word is None:
        word = comtypes.client.CreateObject("kwps.Application")
    doc = word.Documents.Open(str(file_path))
    output.mkdir(parents=True, exist_ok=True)
    doc.SaveAs(str(output / output.stem), 17)
    doc.Close()
    return output / f"{output.stem}.pdf"


async def doc2img(file_path: Path, output: Path) -> list[Path]:
    """将 Word 文档转换为图片。"""
    images_path: list[Path] = []
    pdf_path = await doc2pdf(file_path, output)
    images_path = await pdf2img(pdf_path, output)
    pdf_path.unlink(missing_ok=True)
    return images_path


async def pdf2img(file_path: Path, output: Path) -> list[Path]:
    """将 PDF 转换为图片。"""
    images = await run_sync(pdf2image.convert_from_path)(file_path)
    output.mkdir(parents=True, exist_ok=True)
    images_path: list[Path] = []
    for i, image in enumerate(images):
        img_path = output / f"{i}.jpg"
        images_path.append(img_path)
        image.save(img_path, "JPEG")
    return images_path
