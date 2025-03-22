import cv2 as cv
import numpy as np
from PIL import Image

# from .dbnet.dbnet_infer import DBNET
from .crnn import CRNNHandle

# dbnet_model = DBNET()
crnn_model = CRNNHandle()


def read_code(image):
    textimg_uint8 = np.clip(image, 0, 255).astype(np.uint8)
    pil_img = Image.fromarray(cv.cvtColor(textimg_uint8, cv.COLOR_BGR2RGB))
    text = crnn_model.predict_rbg(pil_img)
    return text.replace(" ", "")
