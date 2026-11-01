"""课堂专注度评分。

把一帧内所有人的行为加权求和，得到"这一刻的课堂专注度"，再做指数
滑动平均平滑输出。

为什么不直接取坐姿占比：
    - 举手发言同样是专注的表现，计入 SIT 之外的正权重；
    - 站立可能是回答问题（正向），也可能是走动（中性），取 0.85 折中；
    - 趴桌直接归零，因为它与专注互斥。

为什么用 EMA 而不是窗口平均：
    端侧内存紧张，维护一个滑动窗口需要额外缓冲；EMA 只需一个浮点状态，
    且天然具备"近期权重更高"的特性，符合课堂专注度的直觉。

本模块 [纯 Python]，可在 PC 端直接测试。
"""

from . import config
from .compat import ema_update, clamp


class FocusScorer(object):
    """课堂专注度评分器。"""

    def __init__(self, alpha=None, weights=None):
        self.alpha = config.FOCUS_EMA_ALPHA if alpha is None else alpha
        self.weights = weights or config.FOCUS_WEIGHT
        self.value = 100.0      # 初始按满专注起算，避免开场瞬间跳变
        self.peak = 100.0
        self.valley = 100.0

    def instant(self, counter):
        """计算未平滑的瞬时专注度（0~100）。

        无人时返回上一次的值而不是 0——空教室不代表专注度归零，
        直接归零会让大屏在下课期间刷出一条刺眼的低谷。
        """
        total = 0.0
        weight_sum = 0.0
        for name, num in counter.items():
            weight_sum += self.weights.get(name, 0.5) * num
            total += num
        if not total:
            return self.value
        return clamp(100.0 * weight_sum / total, 0.0, 100.0)

    def update(self, counter):
        """摄入一帧的行为统计，返回平滑后的专注度。"""
        self.value = ema_update(self.value, self.instant(counter), self.alpha)
        if self.value > self.peak:
            self.peak = self.value
        if self.value < self.valley:
            self.valley = self.value
        return self.value

    def grade(self):
        """分档：good / fair / poor，供大屏配色使用。"""
        if self.value >= config.FOCUS_GOOD:
            return "good"
        if self.value >= config.FOCUS_FAIR:
            return "fair"
        return "poor"

    def reset(self):
        self.value = 100.0
        self.peak = 100.0
        self.valley = 100.0


def evaluate_lesson(focus_series):
    """课后对整节课的专注度序列做一次总评。

    输入为按时间排序的专注度列表，返回统计摘要。端侧只在课后执行
    一次，因此这里可以承担 O(n) 的开销。
    """
    if not focus_series:
        return {"mean": 0.0, "min": 0.0, "max": 0.0,
                "good_ratio": 0.0, "samples": 0}

    total = 0.0
    lowest = focus_series[0]
    highest = focus_series[0]
    good = 0
    for value in focus_series:
        total += value
        if value < lowest:
            lowest = value
        if value > highest:
            highest = value
        if value >= config.FOCUS_GOOD:
            good += 1
    n = len(focus_series)
    return {
        "mean": total / n,
        "min": lowest,
        "max": highest,
        "good_ratio": 100.0 * good / n,
        "samples": n,
    }
