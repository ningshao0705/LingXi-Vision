"""应用主循环。

职责边界：本模块只做编排——取帧、推理、判定、评分、事件、渲染、上报、
落盘的时序都在这里，具体算法分别落在 rules / events / score / proto /
render / logger 中。这样调阈值不必碰主循环，改主循环也不至于动算法。
"""

from . import config
from . import render
from . import proto
from .compat import ticks_ms, ticks_diff
from .events import EventEngine
from .logger import create as create_logger
from .rules import classify_all, count_people
from .score import FocusScorer


class Monitor(object):
    """课堂行为监测应用。"""

    def __init__(self, model, camera, leds, logger,
                 engine=None, scorer=None, verbose=True):
        self.model = model
        self.camera = camera
        self.leds = leds
        self.logger = logger
        self.engine = engine or EventEngine()
        self.scorer = scorer or FocusScorer()
        self.verbose = verbose

        self.peak = 0
        self.frames = 0
        self.started_ms = ticks_ms()
        self._last_json = ticks_ms()
        self._last_text = ticks_ms()
        self._last_blink = ticks_ms()
        self._blink_state = False

    # ---------------- 单帧处理 ----------------
    def step(self, img, now=None, fps=0.0):
        """处理一帧，返回本帧的状态字典与触发的事件列表。"""
        now = ticks_ms() if now is None else now
        height = img.height()
        people = self.model.predict([img])

        counter, details = classify_all(people, height)
        count = count_people(counter)
        if count > self.peak:
            self.peak = count

        focus = self.scorer.update(counter)
        fired = self.engine.update(now, counter.get("RAISE", 0),
                                   counter.get("DOWN", 0))

        for name, num in fired:
            self.logger.log(now, name, num, count, focus)
            if self.verbose:
                print(proto.encode_event(
                    proto.build_event(now, name, num, count, focus)))

        render.render_frame(img, details, counter, count, focus, fps,
                            self.engine)
        self._update_leds(now, counter)

        self.frames += 1
        status = proto.build_status(now, count, fps, counter, focus,
                                    self.engine, self.peak)
        return status, fired

    # ---------------- LED ----------------
    def _update_leds(self, now, counter):
        if self.leds is None:
            return
        if ticks_diff(now, self._last_blink) >= config.HEARTBEAT_MS:
            self._last_blink = now
            self._blink_state = not self._blink_state
            self.leds.set("heartbeat", self._blink_state)
        self.leds.set("alert", self.engine.alert)
        self.leds.set("raise", counter.get("RAISE", 0) > 0)

    # ---------------- 周期上报 ----------------
    def _maybe_report(self, now, status):
        if ticks_diff(now, self._last_json) >= config.REPORT_JSON_MS:
            print(proto.encode_status(status))
            self._last_json = now
        if self.verbose and ticks_diff(now, self._last_text) >= config.REPORT_TEXT_MS:
            print("People:%d Raise:%d Down:%d Stand:%d Sit:%d Focus:%d FPS:%.1f"
                  % (status["count"], status["raise"], status["down"],
                     status["stand"], status["sit"], status["focus"],
                     status["fps"]))
            self._last_text = now

    # ---------------- 主循环 ----------------
    def run(self, clock=None, max_frames=None):
        """进入主循环。max_frames 用于自检模式限制运行帧数。"""
        print("=== Classroom Behavior Monitor v%s Started ==="
              % proto.SCHEMA_VERSION)
        count = 0
        while True:
            if max_frames is not None and count >= max_frames:
                break
            if clock is not None:
                clock.tick()
            img = self.camera.capture()
            if img is None:
                break
            now = ticks_ms()
            fps = clock.fps() if clock is not None else 0.0
            status, _fired = self.step(img, now, fps)
            self._maybe_report(now, status)
            count += 1
        return count

    def shutdown(self):
        """收尾：关灯、关日志。"""
        if self.leds is not None:
            self.leds.all_off()
        self.logger.close()

    def summary(self):
        """运行摘要。"""
        return {
            "frames": self.frames,
            "peak": self.peak,
            "uptime_ms": ticks_diff(ticks_ms(), self.started_ms),
            "focus_peak": round(self.scorer.peak, 1),
            "focus_valley": round(self.scorer.valley, 1),
            "events": self.engine.snapshot(),
            "logger": self.logger.stats(),
        }


def build(ml_module, csi_module, machine_module, clock=None):
    """按依赖组装一个 Monitor 实例。

    这是板端入口与自检脚本共用的装配函数，保证两条路径的初始化顺序
    完全一致——自检通过就等于主循环能跑。
    """
    from .hal import Camera, StatusLED, Storage
    from .pose import load_model

    model, _decoder = load_model(ml_module)
    camera = Camera(csi_module)
    camera.open()
    storage = Storage()
    sd_ok = storage.probe()
    leds = StatusLED(machine_module)
    logger = create_logger(sd_ok)
    return Monitor(model, camera, leds, logger)
