#!/usr/bin/python
# encoding: utf-8


import numpy as np
from PIL import Image


class resizeNormalize(object):
    """对 OCR 输入图片执行缩放与归一化处理。"""
    def __init__(self, size, interpolation=Image.BILINEAR):  # type: ignore
        """初始化实例。

        参数:
            size (Any): size。
            interpolation (Any): interpolation。
        """
        self.size = size
        self.interpolation = interpolation

    def __call__(self, img):
        """调用实例并返回结果。

        参数:
            img (Any): img。
        """
        size = self.size
        imgW, imgH = size
        scale = img.size[1] * 1.0 / imgH
        w = img.size[0] / scale
        w = int(w)
        img = img.resize((w, imgH), self.interpolation)
        w, h = img.size
        if w <= imgW:
            newImage = np.zeros((imgH, imgW), dtype="uint8")
            newImage[:] = 255
            newImage[:, :w] = np.array(img)
            img = Image.fromarray(newImage)
        else:
            img = img.resize((imgW, imgH), self.interpolation)

        img = np.array(img, dtype=np.float32)

        img -= 127.5
        img /= 127.5

        img = img.reshape([*img.shape, 1])

        return img


class strLabelConverter(object):
    """在 OCR 文字与索引序列之间进行转换。"""
    def __init__(self, alphabet):
        """初始化实例。

        参数:
            alphabet (Any): alphabet。
        """
        self.alphabet = alphabet + "ç"  # for `-1` index
        self.dict = {}
        for i, char in enumerate(alphabet):
            # NOTE: 0 is reserved for 'blank' required by wrap_ctc
            self.dict[char] = i + 1

    def decode(self, t, length, raw=False):
        """处理解码相关逻辑。

        参数:
            t (Any): t。
            length (Any): length。
            raw (Any): raw。
        """
        t = t[:length]
        if raw:
            return "".join([self.alphabet[i - 1] for i in t])
        else:
            char_list = []
            for i in range(length):
                if t[i] != 0 and (not (i > 0 and t[i - 1] == t[i])):
                    char_list.append(self.alphabet[t[i] - 1])
            return "".join(char_list)


class averager(object):
    """用于累计并计算张量均值。"""
    def __init__(self):
        """初始化实例。"""
        self.reset()

    def add(self, v):
        """处理添加相关逻辑。

        参数:
            v (Any): v。
        """
        self.n_count += v.data.numel()
        # NOTE: not `+= v.sum()`, which will add a node in the compute graph,
        # which lead to memory leak
        self.sum += v.data.sum()

    def reset(self):
        """重置累计状态。"""
        self.n_count = 0
        self.sum = 0

    def val(self):
        """返回当前累计平均值。"""
        res = 0
        if self.n_count != 0:
            res = self.sum / float(self.n_count)
        return res
