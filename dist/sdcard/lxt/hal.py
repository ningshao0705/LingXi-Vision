"""板载外设硬件抽象层。

把摄像头、LED、SD 卡、串口的差异收敛到一层，好处有两点：
    1. 上层逻辑（app.py）不直接碰具体驱动，换板或换 BSP 时改动集中；
    2. PC 端跑逻辑测试时可以用 Dummy 实现顶替，无需真硬件。

依赖板端 csi / machine 模块。
"""

from . import config


class Camera(object):
    """MIPI CSI 摄像头封装。"""

    def __init__(self, csi_module=None, pixformat=None, framesize=None):
        self.csi = csi_module
        self.device = None
        self.pixformat = pixformat or config.CAM_PIXFORMAT
        self.framesize = framesize or config.CAM_FRAMESIZE
        self.ready = False

    def open(self):
        if self.csi is None:
            return False
        fmt = getattr(self.csi, self.pixformat)
        size = getattr(self.csi, self.framesize)
        self.device = self.csi.CSI()
        self.device.reset()
        self.device.pixformat(fmt)
        self.device.framesize(size)
        # 预热若干帧，让自动曝光与白平衡收敛；否则开场前几秒画面偏暗，
        # 关键点置信度普遍偏低，会造成误判
        self.device.snapshot(time=config.CAM_WARMUP_MS)
        self.ready = True
        return True

    def capture(self):
        if not self.ready:
            return None
        return self.device.snapshot()

    def close(self):
        self.ready = False
        self.device = None


class StatusLED(object):
    """三色状态灯。

    LED1 心跳   系统在运行（也用于现场快速判断程序是否卡死）
    LED2 告警   趴桌告警激活，红色常亮
    LED3 提示   检测到举手
    """

    def __init__(self, machine_module=None):
        self.leds = {}
        self.enabled = False
        if machine_module is None:
            return
        try:
            self.leds = {
                "heartbeat": machine_module.LED(config.LED_HEARTBEAT),
                "alert": machine_module.LED(config.LED_ALERT),
                "raise": machine_module.LED(config.LED_RAISE),
            }
            for led in self.leds.values():
                led.off()
            self.enabled = True
        except Exception as exc:                      # 缺少 LED 不应致命
            print("[hal] LED unavailable:", exc)

    def set(self, name, on):
        led = self.leds.get(name)
        if led is None:
            return
        try:
            if on:
                led.on()
            else:
                led.off()
        except Exception:
            pass

    def all_off(self):
        for name in self.leds:
            self.set(name, False)

    def blink(self, name, state):
        """心跳灯按传入状态翻转，返回翻转后的状态。"""
        self.set(name, state)
        return not state


class Storage(object):
    """SD 卡可用性探测。

    CSV 日志依赖 SD 卡，而 SD 卡在教室现场可能被拔走或接触不良。
    这里只做一次性探测，失败时上层自动降级为"不落盘"，而不是让
    整条流水线停摆——这是早期版本踩过的坑（无限等待导致全线阻塞）。
    """

    def __init__(self, path=None):
        self.path = path or config.LOG_PATH
        self.available = False

    def probe(self, open_fn=open):
        try:
            handle = open_fn(self.path, "a")
            handle.close()
            self.available = True
        except Exception as exc:
            print("[hal] SD card unavailable, logging disabled:", exc)
            self.available = False
        return self.available
