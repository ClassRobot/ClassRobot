from pathlib import Path

import pdf2image
import comtypes.client

powerpoint = comtypes.client.CreateObject("kwpp.Application")  # 使用wps的接口
word = comtypes.client.CreateObject("kwps.Application")  # 使用wps的接口


def ppt2img(file_path: Path, output: Path) -> list[Path]:
    ppt = powerpoint.Presentations.Open(str(file_path))
    ppt.SaveAs(str(output), 17)
    ppt.Close()
    return list(output.glob("*.jpg"))


def word2pdf(file_path: Path, output: Path) -> Path:
    doc = word.Documents.Open(str(file_path))
    output.mkdir(parents=True, exist_ok=True)
    doc.SaveAs(str(output / output.stem), 17)
    doc.Close()
    return output / f"{output.stem}.pdf"


def word2img(file_path: Path, output: Path) -> list[Path]:
    images_path: list[Path] = []
    pdf_path = word2pdf(file_path, output)
    images_path = pdf2img(pdf_path, output)
    pdf_path.unlink(missing_ok=True)
    return images_path


def pdf2img(file_path: Path, output: Path) -> list[Path]:
    images = pdf2image.convert_from_path(file_path)
    output.mkdir(parents=True, exist_ok=True)
    images_path: list[Path] = []
    for i, image in enumerate(images):
        img_path = output / f"{i}.jpg"
        images_path.append(img_path)
        image.save(img_path, "JPEG")
    return images_path
