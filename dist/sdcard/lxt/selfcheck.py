"""开机自检。

上电时依次检查模型、摄像头、SD 卡、LED，把结果打印到串口并写入
日志。现场部署时这一步能省掉大量排查时间——四类故障里任意一种
都会让系统"看起来在跑实则没输出"，自检把沉默失败变成显式报错。
"""

from . import config

PASS = "OK"
FAIL = "FAIL"
SKIP = "SKIP"


class Result(object):
    """单项自检结果。"""

    def __init__(self, name, status, detail=""):
        self.name = name
        self.status = status
        self.detail = detail

    def __str__(self):
        if self.detail:
            return "%-10s %-4s %s" % (self.name, self.status, self.detail)
        return "%-10s %-4s" % (self.name, self.status)

    @property
    def ok(self):
        return self.status != FAIL


class SelfCheck(object):
    """自检执行器。"""

    def __init__(self, ml_module=None, csi_module=None,
                 machine_module=None, storage=None):
        self.ml = ml_module
        self.csi = csi_module
        self.machine = machine_module
        self.storage = storage
        self.results = []

    # ---- 各检查项 ----
    def _check_model(self):
        if self.ml is None:
            return Result("model", SKIP, "ml module absent")
        try:
            from .pose import load_model
            model, decoder = load_model(self.ml)
            return Result("model", PASS,
                          "%s in=%s" % (config.MODEL_PATH,
                                        tuple(model.input_shape[0])))
        except Exception as exc:
            return Result("model", FAIL, str(exc))

    def _check_camera(self):
        if self.csi is None:
            return Result("camera", SKIP, "csi module absent")
        try:
            from .hal import Camera
            cam = Camera(self.csi)
            cam.open()
            frame = cam.capture()
            size = (frame.width(), frame.height()) if frame else (0, 0)
            return Result("camera", PASS, "%dx%d" % size)
        except Exception as exc:
            return Result("camera", FAIL, str(exc))

    def _check_storage(self):
        if self.storage is None:
            return Result("storage", SKIP, "not configured")
        ok = self.storage.probe()
        return Result("storage", PASS if ok else FAIL, self.storage.path)

    def _check_led(self):
        if self.machine is None:
            return Result("led", SKIP, "machine module absent")
        try:
            from .hal import StatusLED
            led = StatusLED(self.machine)
            if not led.enabled:
                return Result("led", FAIL, "no led handle")
            led.all_off()
            return Result("led", PASS, "%d channels" % len(led.leds))
        except Exception as exc:
            return Result("led", FAIL, str(exc))

    # ---- 执行 ----
    def run(self, verbose=True):
        self.results = [self._check_model(), self._check_camera(),
                        self._check_storage(), self._check_led()]
        if verbose:
            print("=== SelfCheck ===")
            for item in self.results:
                print(item)
            print("=== SelfCheck done: %d/%d passed ==="
                  % (self.passed(), len(self.results)))
        return self.results

    def passed(self):
        return sum(1 for item in self.results if item.status == PASS)

    @property
    def critical_ok(self):
        """模型与摄像头是硬门槛，缺任一都不应进入主循环。"""
        target = {"model", "camera"}
        for item in self.results:
            if item.name in target and item.status == FAIL:
                return False
        return True
