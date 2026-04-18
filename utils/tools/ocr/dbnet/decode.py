import cv2
import pyclipper
import numpy as np
from shapely.geometry import Polygon


class SegDetectorRepresenter:
    """将 DBNet 输出结果解码为文本框坐标。"""
    def __init__(self, thresh=0.3, box_thresh=0.5, max_candidates=1000, unclip_ratio=2.0):
        """初始化实例。

        参数:
            thresh (Any): thresh。
            box_thresh (Any): boxthresh。
            max_candidates (Any): maxcandidates。
            unclip_ratio (Any): unclipratio。
        """
        self.min_size = 3
        self.thresh = thresh
        self.box_thresh = box_thresh
        self.max_candidates = max_candidates
        self.unclip_ratio = unclip_ratio

    def __call__(self, pred, height, width):
        """batch: (image, polygons, ignore_tags

        参数:
            pred (Any): pred。
            height (Any): height。
            width (Any): width。
        """

        pred = pred[0, :, :]
        segmentation = self.binarize(pred)

        boxes, scores = self.boxes_from_bitmap(pred, segmentation, width, height)

        return boxes, scores

    def binarize(self, pred):
        """处理binarize相关逻辑。

        参数:
            pred (Any): pred。
        """
        return pred > self.thresh

    def boxes_from_bitmap(self, pred, bitmap, dest_width, dest_height):
        """_bitmap: single map with shape (H, W),

        参数:
            pred (Any): pred。
            bitmap (Any): bitmap。
            dest_width (Any): destwidth。
            dest_height (Any): destheight。
        """

        assert len(bitmap.shape) == 2
        # bitmap = _bitmap.cpu().numpy()  # The first channel
        # pred = pred.cpu().detach().numpy()
        height, width = bitmap.shape
        # print(bitmap)
        # cv2.imwrite("./test/output/test.jpg",(bitmap * 255).astype(np.uint8))
        contours, _ = cv2.findContours((bitmap * 255).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        num_contours = min(len(contours), self.max_candidates)
        boxes = np.zeros((num_contours, 4, 2), dtype=np.int16)
        scores = np.zeros((num_contours,), dtype=np.float32)
        rects = []
        for index in range(num_contours):
            contour = contours[index].squeeze(1)
            points, sside = self.get_mini_boxes(contour)
            if sside < self.min_size:
                continue
            points = np.array(points)
            score = self.box_score_fast(pred, contour)
            if self.box_thresh > score:
                continue
            # print(points)
            box = self.unclip(points, unclip_ratio=self.unclip_ratio).reshape(-1, 1, 2)
            # print(box)
            box, sside = self.get_mini_boxes(box)
            if sside < self.min_size + 2:
                continue
            box = np.array(box)
            if not isinstance(dest_width, int):
                dest_width = dest_width.item()
                dest_height = dest_height.item()

            box[:, 0] = np.clip(np.round(box[:, 0] / width * dest_width), 0, dest_width)
            box[:, 1] = np.clip(np.round(box[:, 1] / height * dest_height), 0, dest_height)
            boxes[index, :, :] = box.astype(np.int16)
            scores[index] = score
        return boxes, scores

    def unclip(self, box, unclip_ratio=1.5):
        """处理unclip相关逻辑。

        参数:
            box (Any): box。
            unclip_ratio (Any): unclipratio。
        """
        poly = Polygon(box)

        distance = poly.area * unclip_ratio / (poly.length)
        offset = pyclipper.PyclipperOffset()  # type: ignore
        offset.AddPath(box, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)  # type: ignore
        expanded = np.array(offset.Execute(distance))
        return expanded

    def get_mini_boxes(self, contour):
        """获取miniboxes。

        参数:
            contour (Any): contour。
        """
        bounding_box = cv2.minAreaRect(contour)
        points = sorted(list(cv2.boxPoints(bounding_box)), key=lambda x: x[0])

        index_1, index_2, index_3, index_4 = 0, 1, 2, 3
        if points[1][1] > points[0][1]:
            index_1 = 0
            index_4 = 1
        else:
            index_1 = 1
            index_4 = 0
        if points[3][1] > points[2][1]:
            index_2 = 2
            index_3 = 3
        else:
            index_2 = 3
            index_3 = 2

        box = [points[index_1], points[index_2], points[index_3], points[index_4]]
        return box, min(bounding_box[1])

    def box_score_fast(self, bitmap, _box):
        """处理boxscorefast相关逻辑。

        参数:
            bitmap (Any): bitmap。
            _box (Any): box。
        """
        h, w = bitmap.shape[:2]
        box = _box.copy()
        xmin = np.clip(np.floor(box[:, 0].min()).astype(np.int_), 0, w - 1)
        xmax = np.clip(np.ceil(box[:, 0].max()).astype(np.int_), 0, w - 1)
        ymin = np.clip(np.floor(box[:, 1].min()).astype(np.int_), 0, h - 1)
        ymax = np.clip(np.ceil(box[:, 1].max()).astype(np.int_), 0, h - 1)

        mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
        box[:, 0] = box[:, 0] - xmin
        box[:, 1] = box[:, 1] - ymin
        cv2.fillPoly(mask, box.reshape(1, -1, 2).astype(np.int32), 1)  # type: ignore
        return cv2.mean(bitmap[ymin : ymax + 1, xmin : xmax + 1], mask)[0]
