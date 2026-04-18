import cv2 as cv
import numpy as np
from PIL import Image

def read_code(image):
    """识别图片中的验证码文本。"""
    from utils.skills import ocr_skill

    if isinstance(image, Image.Image):
        image = cv.cvtColor(np.asarray(image.convert("RGB")), cv.COLOR_RGB2BGR)
    textimg_uint8 = np.clip(image, 0, 255).astype(np.uint8)
    pil_img = Image.fromarray(cv.cvtColor(textimg_uint8, cv.COLOR_BGR2RGB))
    return ocr_skill.read_code(pil_img)
