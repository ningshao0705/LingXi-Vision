"""示例 3：事件流输出。

在最小推理的基础上接入规则引擎与事件引擎，只输出语义事件，不渲染
画面。适合作为"纯数据节点"部署——例如在不需要画面的场合把板子挂在
教室后方，只向上位机吐事件。

串口输出：
    CBEVENT:event=RAISE people=1 count=3 focus=92 ...
"""

import time

import csi
import ml

from lxt.pose import load_model
from lxt.hal import Camera
from lxt.rules import classify_all, count_people
from lxt.events import EventEngine
from lxt.score import FocusScorer
from lxt import proto


def main():
    model, _decoder = load_model(ml)
    camera = Camera(csi)
    camera.open()
    engine = EventEngine()
    scorer = FocusScorer()

    clock = time.clock()
    while True:
        clock.tick()
        img = camera.snapshot()
        people = model.predict([img])

        counter, _details = classify_all(people, img.height())
        count = count_people(counter)
        focus = scorer.update(counter)

        now = time.ticks_ms()
        fired = engine.update(now, counter.get("RAISE", 0),
                              counter.get("DOWN", 0))
        for name, num in fired:
            print(proto.encode_event(
                proto.build_event(now, name, num, count, focus)))


if __name__ == "__main__":
    main()
