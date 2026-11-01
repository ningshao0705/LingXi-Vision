"""行为事件引擎：时间防抖 + 边沿触发 + 滞回释放。

为什么要单独做一层事件引擎，而不是直接把每帧计数上报？

逐帧计数在 21 FPS 下会产生大量重复事件：一次举手会被记成几十次发言，
一次趴桌会刷出几十条告警。上层（大屏、教务系统）拿到的是噪声而不是
事实。事件引擎把"持续的姿态状态"压缩成"一次语义事件"，这是从感知
走向可用的关键一步。

三个时间参数的作用：

    CONFIRM   持续时间达到阈值才确认，滤掉误检与短暂动作
    RELEASE   状态消失后继续等待一段时间才复位，避免临界抖动反复触发
    ALERT     告警类事件用更长的确认时间，避免误报打扰课堂

本模块 [纯 Python]，可在 PC 端直接测试。
"""

from . import config
from .compat import ticks_diff


class EventEngine(object):
    """举手 / 趴桌两类事件的双边沿状态机。"""

    def __init__(self,
                 raise_confirm_ms=None, raise_release_ms=None,
                 down_alert_ms=None, down_release_ms=None):
        self.raise_confirm_ms = raise_confirm_ms or config.RAISE_CONFIRM_MS
        self.raise_release_ms = raise_release_ms or config.RAISE_RELEASE_MS
        self.down_alert_ms = down_alert_ms or config.DOWN_ALERT_MS
        self.down_release_ms = down_release_ms or config.DOWN_RELEASE_MS

        self.raise_since = None      # 举手起始时刻
        self.raise_active = False    # 本轮发言事件是否已确认
        self.raise_release = None    # 举手消失时刻（冷却计时）

        self.down_since = None       # 趴桌起始时刻
        self.down_active = False     # 告警是否处于激活状态
        self.down_release = None     # 恢复时刻（滞回计时）

        self.events_raise = 0        # 发言事件累计
        self.events_down = 0         # 趴桌告警累计

    # ---------------- 举手 ----------------
    def _update_raise(self, now, raise_cnt):
        fired = []
        if raise_cnt > 0:
            self.raise_release = None
            if self.raise_since is None:
                self.raise_since = now
            elif (not self.raise_active
                  and ticks_diff(now, self.raise_since) >= self.raise_confirm_ms):
                self.raise_active = True
                self.events_raise += 1
                fired.append(("RAISE", raise_cnt))
        else:
            self.raise_since = None
            if self.raise_active:
                if self.raise_release is None:
                    self.raise_release = now
                elif ticks_diff(now, self.raise_release) >= self.raise_release_ms:
                    self.raise_active = False
                    self.raise_release = None
        return fired

    # ---------------- 趴桌 ----------------
    def _update_down(self, now, down_cnt):
        fired = []
        if down_cnt > 0:
            self.down_release = None
            if self.down_since is None:
                self.down_since = now
            elif (not self.down_active
                  and ticks_diff(now, self.down_since) >= self.down_alert_ms):
                self.down_active = True
                self.events_down += 1
                fired.append(("DOWN_ALERT", down_cnt))
        else:
            self.down_since = None
            if self.down_active:
                if self.down_release is None:
                    self.down_release = now
                elif ticks_diff(now, self.down_release) >= self.down_release_ms:
                    self.down_active = False
                    self.down_release = None
        return fired

    def update(self, now, raise_cnt, down_cnt):
        """推进状态机，返回本帧触发的事件列表 [(名称, 涉及人数)]。"""
        fired = self._update_raise(now, raise_cnt)
        fired.extend(self._update_down(now, down_cnt))
        return fired

    @property
    def alert(self):
        """当前是否处于趴桌告警状态（供 LED 与大屏告警条消费）。"""
        return self.down_active

    def snapshot(self):
        """导出状态快照，便于日志与调试。"""
        return {
            "raise_active": self.raise_active,
            "down_active": self.down_active,
            "events_raise": self.events_raise,
            "events_down": self.events_down,
        }

    def reset(self):
        """清空状态（不清除累计计数，因为那是课堂事实）。"""
        self.raise_since = None
        self.raise_active = False
        self.raise_release = None
        self.down_since = None
        self.down_active = False
        self.down_release = None
