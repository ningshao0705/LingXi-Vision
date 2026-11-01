"""示例 5：串口数据桥接。

把状态流以固定周期从指定 UART 发出，而不占用 USB CDC。用于把板子接到
外部网关（如教室里的 ESP32 / 树莓派），由网关再转发到校园网。

注意：UART(1) 在本 BSP 下被 RT-Thread 控制台占用，MicroPython 层拒绝
再次打开；若要使用真实硬件串口，需先在 RT-Thread 侧把控制台迁移到
其它端口，并确认对应排针已焊接。

本示例默认把 USB CDC 作为输出（machine.UART 不可用时自动回退 print），
以保证在标准固件下可直接运行。
"""

import time

import csi
import ml

from lxt.pose import load_model
from lxt.hal import Camera, StatusLED, Storage
from lxt.rules import classify_all, count_people
from lxt.events import EventEngine
from lxt.score import FocusScorer
from lxt.logger import create as create_logger
from lxt import config, proto


def open_uart():
    """尝试打开硬件串口，失败则回退到标准输出。"""
    try:
        from machine import UART
        uart = UART(2, config.UART_BAUDRATE)
        print("[bridge] UART2 opened @%d" % config.UART_BAUDRATE)
        return uart
    except Exception as exc:
        print("[bridge] UART unavailable, fallback to stdout:", exc)
        return None


def emit(uart, text):
    if uart is not None:
        try:
            uart.write(text + "\r\n")
            return
        except Exception:
            pass
    print(text)


def main():
    model, _decoder = load_model(ml)
    camera = Camera(csi)
    camera.open()
    leds = StatusLED(__import__("machine"))
    storage = Storage()
    logger = create_logger(storage.probe())

    engine = EventEngine()
    scorer = FocusScorer()
    uart = open_uart()

    clock = time.clock()
    peak = 0
    last = time.ticks_ms()

    while True:
        clock.tick()
        img = camera.snapshot()
        people = model.predict([img])

        counter, details = classify_all(people, img.height())
        count = count_people(counter)
        if count > peak:
            peak = count
        focus = scorer.update(counter)

        now = time.ticks_ms()
        fired = engine.update(now, counter.get("RAISE", 0),
                              counter.get("DOWN", 0))
        for name, num in fired:
            logger.log(now, name, num, count, focus)
            emit(uart, proto.encode_event(
                proto.build_event(now, name, num, count, focus)))

        leds.set("alert", engine.alert)
        leds.set("raise", counter.get("RAISE", 0) > 0)

        if time.ticks_diff(now, last) >= config.REPORT_JSON_MS:
            payload = proto.build_status(now, count, clock.fps(), counter,
                                         focus, engine, peak)
            emit(uart, proto.encode_status(payload))
            last = now

        del details      # 本示例不渲染，及时释放引用


if __name__ == "__main__":
    main()
