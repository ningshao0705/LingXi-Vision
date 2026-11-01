"""姿态模型加载与输出解码。

解码器承接 NPU 的原始输出张量，还原成人框 + 17 个关键点。这部分代码
与模型导出配置严格绑定（张量形状、量化参数、锚点排布），任何一处
改动都会导致坐标错乱，因此常量集中放置并加注释说明来源。

依赖板端 ml 模块，PC 端不可导入。
"""

import math

from . import config
from . import keypoints


class PoseDecoder(object):
    """DFL 框回归 + 关键点解码。

    三阶段：
        1. 按得分从三个检测头的网格中筛出候选锚点（带容量上限的
           插入排序，避免全量排序的内存与时间开销）；
        2. 用 DFL 把 16 通道的距离分布积分成框的四条边，再做 NMS；
        3. 从关键点头还原 17 个点的坐标与可见性，并映射回原图。
    """

    # 输出张量形状，顺序与模型导出一致
    SHAPES = ((1, 144, 64), (1, 576, 64), (1, 36, 1), (1, 756, 51),
              (1, 576, 1), (1, 36, 64), (1, 144, 1))
    # 量化缩放因子
    SCALES = (0.0743677095, 0.0850540623, 0.1490852833, 0.0513033383,
              0.0935444459, 0.0694025531, 0.1864520013)
    # 量化零点
    ZEROS = (-72, -64, 107, 5, 110, -64, 116)
    # (stride, grid, box_output_index, score_output_index, anchor_base)
    HEADS = ((8, 24, 1, 4, 0), (16, 12, 0, 6, 576), (32, 6, 5, 2, 720))

    def __init__(self, threshold=None, nms_threshold=None,
                 max_candidates=60, max_people=None):
        self.threshold = config.PERSON_THRESHOLD if threshold is None else threshold
        self.nms_threshold = (config.NMS_THRESHOLD if nms_threshold is None
                              else nms_threshold)
        self.max_candidates = max_candidates
        self.max_people = config.MAX_PEOPLE if max_people is None else max_people
        self.last_infer_ms = 0.0

    # ---------------- 校验 ----------------
    def validate(self, model):
        """校验模型输入布局是否匹配，避免加载错模型后静默输出垃圾坐标。"""
        if (len(model.input_shape) != 1
                or tuple(model.input_shape[0]) != (1, config.MODEL_INPUT_SIZE,
                                                   config.MODEL_INPUT_SIZE, 3)
                or model.input_dtype[0] != "b"
                or abs(model.input_scale[0] - 1.0 / 255.0) > 1e-8
                or model.input_zero_point[0] != -128):
            raise ValueError("请使用配套的 LingXi-Pose-Tiny 192×192 INT8 模型文件")
        return True

    # ---------------- 数学工具 ----------------
    @staticmethod
    def sigmoid(value):
        if value >= 0:
            return 1.0 / (1.0 + math.exp(-value))
        value = math.exp(value)
        return value / (1.0 + value)

    @staticmethod
    def dfl(tensor, row, offset, scale):
        """把 16 通道的离散距离分布还原为连续距离。

        减去峰值后再取指数，是为了避免 exp 溢出——INT8 反量化后的
        数值范围有限，这一步能稳定在 float 表示范围内。
        """
        peak = max(int(tensor[0, row, offset + k]) for k in range(16))
        total = 0.0
        weighted = 0.0
        for k in range(16):
            value = math.exp((int(tensor[0, row, offset + k]) - peak) * scale)
            total += value
            weighted += k * value
        return weighted / total

    @staticmethod
    def iou(a, b):
        """交并比，用于 NMS。"""
        intersection = (max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
                        * max(0.0, min(a[3], b[3]) - max(a[1], b[1])))
        union = ((a[2] - a[0]) * (a[3] - a[1])
                 + (b[2] - b[0]) * (b[3] - b[1]) - intersection)
        return intersection / union if union > 0 else 0.0

    # ---------------- 主流程 ----------------
    def __call__(self, model, inputs, outputs):
        logit_threshold = math.log(self.threshold / (1.0 - self.threshold))
        candidates = []

        # 1) 候选锚点筛选
        for stride, grid, box_output, score_output, base in self.HEADS:
            scale = model.output_scale[score_output]
            zero = model.output_zero_point[score_output]
            for row in range(grid * grid):
                logit = (int(outputs[score_output][0, row, 0]) - zero) * scale
                if logit >= logit_threshold:
                    candidate = (self.sigmoid(logit), row, stride, grid,
                                 box_output, base + row)
                    if len(candidates) < self.max_candidates:
                        candidates.append(candidate)
                    elif candidate > candidates[-1]:
                        candidates[-1] = candidate
                    else:
                        continue
                    candidates.sort(reverse=True)

        # 2) DFL 解码 + NMS
        kept = []
        for score, row, stride, grid, box_output, anchor in candidates:
            x = row % grid + 0.5
            y = row // grid + 0.5
            distances = [self.dfl(outputs[box_output], row, k * 16,
                                  model.output_scale[box_output])
                         for k in range(4)]
            box = ((x - distances[0]) * stride, (y - distances[1]) * stride,
                   (x + distances[2]) * stride, (y + distances[3]) * stride)
            if any(self.iou(box, item[0]) > self.nms_threshold for item in kept):
                continue
            kept.append((box, score, anchor, x, y, stride))
            if len(kept) >= self.max_people:
                break

        # 3) 坐标映射与关键点还原
        rx, ry, rw, rh = inputs[0].roi
        sx = rw / float(config.MODEL_INPUT_SIZE)
        sy = rh / float(config.MODEL_INPUT_SIZE)
        scale = model.output_scale[3]
        zero = model.output_zero_point[3]
        results = []

        for box, score, anchor, ax, ay, stride in kept:
            x1, y1 = max(0.0, box[0]), max(0.0, box[1])
            x2, y2 = min(float(config.MODEL_INPUT_SIZE), box[2]), \
                     min(float(config.MODEL_INPUT_SIZE), box[3])
            if x2 <= x1 or y2 <= y1:
                continue
            left = rx + int(x1 * sx)
            top = ry + int(y1 * sy)
            right = rx + int(x2 * sx)
            bottom = ry + int(y2 * sy)
            if right <= left or bottom <= top:
                continue

            points = []
            for k in range(17):
                px = (int(outputs[3][0, anchor, k * 3]) - zero) * scale
                py = (int(outputs[3][0, anchor, k * 3 + 1]) - zero) * scale
                confidence = self.sigmoid(
                    (int(outputs[3][0, anchor, k * 3 + 2]) - zero) * scale)
                px = (px * 2.0 + ax - 0.5) * stride
                py = (py * 2.0 + ay - 0.5) * stride
                # 越界点直接判为不可见，避免画出画面外的飞线
                if not (0.0 <= px < config.MODEL_INPUT_SIZE
                        and 0.0 <= py < config.MODEL_INPUT_SIZE):
                    confidence = 0.0
                points.append((rx + int(px * sx), ry + int(py * sy), confidence))

            results.append(((left, top, right - left, bottom - top),
                            score, points))
        return results


def load_model(ml_module):
    """加载模型并完成校验。

    单独抽成函数是为了让自检流程可以先加载模型、打印信息，再决定是否
    进入主循环——模型文件缺失时应该给出明确提示而不是崩溃退出。
    """
    decoder = PoseDecoder()
    model = ml_module.Model(config.MODEL_PATH, postprocess=decoder)
    decoder.validate(model)
    return model, decoder


def keypoint_summary(points):
    """统计一人的可见关键点数量，用于渲染与质量评估。"""
    visible = 0
    for point in points:
        if point[2] >= config.KEYPOINT_THRESHOLD:
            visible += 1
    return visible
