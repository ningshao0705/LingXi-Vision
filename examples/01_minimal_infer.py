"""示例 1：最小推理循环。

只做一件事——取帧、推理、打印人数与耗时。用于确认模型与摄像头链路
通畅，是所有后续调试的起点。

部署：复制到 SD 卡根目录，在 OpenMV IDE 中打开运行，或改名为 main.py
上电自启。
"""

import time

import csi
import ml

from lxt.pose import load_model
from lxt.hal import Camera


def main():
    model, _decoder = load_model(ml)
    camera = Camera(csi)
    camera.open()

    clock = time.clock()
    frames = 0
    total_ms = 0.0

    while True:
        clock.tick()
        img = camera.snapshot()

        started = time.ticks_ms()
        people = model.predict([img])
        elapsed = time.ticks_diff(time.ticks_ms(), started)

        frames += 1
        total_ms += elapsed
        print("frame=%d people=%d infer=%dms fps=%.1f avg=%.1fms"
              % (frames, len(people), elapsed, clock.fps(),
                 total_ms / frames))


if __name__ == "__main__":
    main()
