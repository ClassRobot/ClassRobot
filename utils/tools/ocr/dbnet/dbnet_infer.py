from pathlib import Path
from typing import Union, Optional

import cv2
import numpy as np
import onnxruntime as rt

from ..utils import ocr_models_dir
from .decode import SegDetectorRepresenter

mean = (0.485, 0.456, 0.406)
std = (0.229, 0.224, 0.225)


def Singleton(cls):
    """构造单例包装器。"""
    _instance = {}

    def _singleton(*args, **kargs):
        """返回单例实例。"""
        if cls not in _instance:
            _instance[cls] = cls(*args, **kargs)
        return _instance[cls]

    return _singleton


class SingletonType(type):
    """提供 DBNet 推理类复用实例的单例元类。"""
    def __init__(cls, *args, **kwargs):
        """初始化实例。

        参数:
            args (*Any): 可变位置参数。
            kwargs (**Any): 可变关键字参数。
        """
        super(SingletonType, cls).__init__(*args, **kwargs)

    def __call__(cls, *args, **kwargs):
        """调用实例并返回结果。

        参数:
            args (*Any): 可变位置参数。
            kwargs (**Any): 可变关键字参数。
        """
        obj = cls.__new__(cls, *args, **kwargs)  # type: ignore
        cls.__init__(obj, *args, **kwargs)
        return obj


def draw_bbox(img_path, result, color=(255, 0, 0), thickness=2):
    """绘制边界框。"""
    if isinstance(img_path, str):
        img_path = cv2.imread(img_path)
        # img_path = cv2.cvtColor(img_path, cv2.COLOR_BGR2RGB)
    img_path = img_path.copy()
    for point in result:
        point = point.astype(int)

        cv2.polylines(img_path, [point], True, color, thickness)
    return img_path


class DBNET(metaclass=SingletonType):
    """封装 DBNet 文本检测模型的推理流程。"""
    def __init__(self, MODEL_PATH: Optional[Union[str, Path]] = None):
        """初始化实例。

        参数:
            MODEL_PATH (Optional[Union[str, Path]]): 模型路径。
        """
        if MODEL_PATH is None:
            MODEL_PATH = ocr_models_dir / "dbnet.onnx"
        self.sess = rt.InferenceSession(str(MODEL_PATH))

        self.decode_handel = SegDetectorRepresenter()

    def process(self, img, short_size):
        """执行当前处理流程。

        参数:
            img (Any): img。
            short_size (Any): shortsize。
        """
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = img.shape[:2]
        if h < w:
            scale_h = short_size / h
            tar_w = w * scale_h
            tar_w = tar_w - tar_w % 32
            tar_w = max(32, tar_w)
            scale_w = tar_w / w

        else:
            scale_w = short_size / w
            tar_h = h * scale_w
            tar_h = tar_h - tar_h % 32
            tar_h = max(32, tar_h)
            scale_h = tar_h / h

        img = cv2.resize(img, None, fx=scale_w, fy=scale_h)

        img = img.astype(np.float32)

        img /= 255.0
        img -= mean
        img /= std
        img = img.transpose(2, 0, 1)
        transformed_image = np.expand_dims(img, axis=0)
        out = self.sess.run(["out1"], {"input0": transformed_image.astype(np.float32)})
        box_list, score_list = self.decode_handel(out[0][0], h, w)
        if len(box_list) > 0:
            idx = box_list.reshape(box_list.shape[0], -1).sum(axis=1) > 0  # 去掉全为0的框
            box_list, score_list = box_list[idx], score_list[idx]
        else:
            box_list, score_list = [], []
        return box_list, score_list


if __name__ == "__main__":
    text_handle = DBNET(MODEL_PATH=ocr_models_dir / "dbnet.onnx")
    img = cv2.imread("../test_imgs/1.jpg")
    print(img.shape)
    box_list, score_list = text_handle.process(img)  # type: ignore
    img = draw_bbox(img, box_list)
    cv2.imwrite("test.jpg", img)
