"""跨平台兼容层。

板端 MicroPython 提供 time.ticks_ms() / time.ticks_diff()，二者基于
32 位回绕计数器实现，不受系统时钟调整影响；CPython 没有这两个函数，
单元测试中退化为 time.monotonic()。

之所以保留两层实现而不是直接改用 ticks_ms：事件引擎的全部时间判断
都建立在 ticks_diff 的回绕安全语义上，板端不可妥协；而 PC 端只用于
验证状态迁移逻辑是否正确，语义等价即可。
"""

try:
    from time import ticks_ms, ticks_diff, sleep_ms          # MicroPython
    RUNNING_ON_BOARD = True
except ImportError:                                          # CPython
    import time as _time

    def ticks_ms():
        return int(_time.monotonic() * 1000)

    def ticks_diff(a, b):
        return a - b

    def sleep_ms(ms):
        _time.sleep(ms / 1000.0)

    RUNNING_ON_BOARD = False

try:
    from math import exp, log, sqrt
except ImportError:
    from math import exp, log
    sqrt = None


def clamp(value, low, high):
    """把数值限制在 [low, high] 区间内。"""
    if value < low:
        return low
    if value > high:
        return high
    return value


def lerp(a, b, t):
    """线性插值，t 取 0~1。"""
    return a + (b - a) * t


def ema_update(previous, sample, alpha):
    """指数滑动平均。

    alpha 越小越平滑，但跟踪延迟越大。专注度评分取 0.15，实测在
    21 FPS 下约 0.3 秒收敛，既能压住单帧抖动又不至于迟钝。
    """
    if previous is None:
        return sample
    return previous + alpha * (sample - previous)


def safe_div(numerator, denominator, default=0.0):
    """除法保护：分母为 0 时返回默认值而不是抛异常。

    关键点置信度为 0 时坐标可能全零，直接相除会产生 inf/NaN，
    进而污染后续的 EMA 评分。
    """
    if not denominator:
        return default
    return numerator / denominator
