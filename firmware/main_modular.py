"""灵犀智眸 LingXi Vision —— 模块化板端入口（方案 B）

部署方式：把 firmware/ 下的 lxt/ 目录与 main.py 一同复制到 SD 卡根目录，
上电后自动执行。目录结构：

    /main.py            本文件的副本
    /lxt/__init__.py
    /lxt/config.py      ... 其余模块

与单文件版（firmware/main.py）的关系：
    单文件版已实机验证、拷贝即用，适合快速演示与现场恢复；
    模块化版结构清晰、可单元测试，适合阅读与二次开发。
    两者算法完全同源，可用 tools/make_single.py 由模块化版生成单文件版。

若 MicroPython 提示内存不足，可用 mpy-cross 把 lxt/ 预编译为 .mpy 后
再拷贝，可显著降低导入期的堆开销。
"""

import time

try:
    import csi
    import ml
    from machine import LED
except ImportError as exc:                     # PC 端导入保护
    raise SystemExit("本入口需在板端 MicroPython 下运行：%s" % exc)

from lxt import config
from lxt.selfcheck import SelfCheck
from lxt.hal import Storage
from lxt.app import Monitor
from lxt.events import EventEngine
from lxt.score import FocusScorer
from lxt.logger import create as create_logger
from lxt.hal import Camera, StatusLED
from lxt.pose import load_model


def main():
    # ---- 1. 自检 ----
    storage = Storage()
    check = SelfCheck(ml_module=ml, csi_module=csi,
                      machine_module=__import__("machine"), storage=storage)
    check.run(verbose=True)
    if not check.critical_ok:
        print("[fatal] self-check failed, halt")
        return

    # ---- 2. 装配 ----
    model, _decoder = load_model(ml)
    camera = Camera(csi)
    camera.open()
    leds = StatusLED(__import__("machine"))
    logger = create_logger(storage.probe())

    monitor = Monitor(model, camera, leds, logger,
                      engine=EventEngine(), scorer=FocusScorer())

    # ---- 3. 运行 ----
    clock = time.clock()
    try:
        monitor.run(clock=clock)
    except KeyboardInterrupt:
        print("[exit] interrupted")
    finally:
        monitor.shutdown()
        print("[exit] summary:", monitor.summary())


if __name__ == "__main__":
    main()
