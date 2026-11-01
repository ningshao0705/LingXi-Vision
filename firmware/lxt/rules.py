"""课堂行为判定规则引擎。

设计取舍说明（详见 docs/技术文档.md 第 6 章）：

初期尝试过端到端的"课堂行为分类器"路线，自建标注样本训练一个四分类
头。实测效果不理想——趴桌与低头在俯拍视角下特征高度重合，举手与伸展
动作难以区分，而样本采集与标注成本远超预期。最终改为几何规则：

    1. 判定依据是可解释的显式条件，阈值可按教室场景直接调整；
    2. 不依赖训练数据，换一间教室不需要重新采集标注；
    3. 单帧判定耗时为微秒级，相对 NPU 推理可以忽略。

代价是规则的表达能力弱于模型，对非常规姿态（如侧躺、半蹲）覆盖不足，
这部分属于主动接受的取舍。

本模块 [纯 Python]，可在 PC 端直接测试。
"""

from . import config
from . import geometry
from .keypoints import BEHAVIOR_COLOR, COLOR_UNKNOWN


def classify(points, rect, frame_h):
    """依据 17 个关键点判定单人行为。

    参数
        points  : [(x, y, confidence)] * 17，屏幕坐标
        rect    : (x, y, w, h) 人体框
        frame_h : 画面高度，用于归一化

    返回
        (行为标签, 配色)
    """
    g = geometry.summarize(points, rect, frame_h)
    if not g["valid"]:
        return "UNKNOWN", COLOR_UNKNOWN

    shoulder_y = g["shoulder_y"]
    torso = g["torso"]

    # 1) 举手发言：任一手腕明显高于肩线
    if g["wrist_y"] is not None and g["wrist_y"] < shoulder_y - config.RAISE_WRIST_ABOVE * torso:
        return "RAISE", BEHAVIOR_COLOR["RAISE"]

    # 2) 低头 / 趴桌：头部明显低于肩线
    if g["head_y"] is not None and g["head_y"] > shoulder_y + config.DOWN_HEAD_BELOW * torso:
        return "DOWN", BEHAVIOR_COLOR["DOWN"]

    # 3) 站立：框高占比大且髋踝展开明显
    if (g["box_ratio"] > config.STAND_BOX_RATIO
            and g["leg_span"] > config.STAND_LEG_RATIO):
        return "STAND", BEHAVIOR_COLOR["STAND"]

    # 4) 默认坐姿端正
    return "SIT", BEHAVIOR_COLOR["SIT"]


def classify_all(people, frame_h):
    """对一帧内全部人体做判定并汇总统计。

    返回
        (计数器字典, [(标签, 配色, 框, 得分, 关键点)] 明细列表)
    """
    counter = {name: 0 for name in config.FOCUS_WEIGHT}
    details = []
    for rect, score, points in people:
        label, color = classify(points, rect, frame_h)
        counter[label] = counter.get(label, 0) + 1
        details.append((label, color, rect, score, points))
    return counter, details


def count_people(counter):
    """统计有效人数（不含 UNKNOWN 的占位计数）。"""
    total = 0
    for name in config.FOCUS_WEIGHT:
        if name != "UNKNOWN":
            total += counter.get(name, 0)
    return total
