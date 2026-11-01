# -*- coding: utf-8 -*-
"""事件引擎状态机单元测试。

重点验证三件事：确认延时、释放滞回、以及"抖动不会重复计数"。
时间轴用虚拟毫秒推进，不依赖真实时钟，因此测试是确定性的。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "firmware"))

from lxt.events import EventEngine            # noqa: E402
from lxt import config                        # noqa: E402


def drive(engine, timeline):
    """按 [(时刻, raise_cnt, down_cnt)] 推进，收集全部触发事件。"""
    fired = []
    for now, raise_cnt, down_cnt in timeline:
        fired.extend(engine.update(now, raise_cnt, down_cnt))
    return fired


class TestRaiseEvent(unittest.TestCase):

    def test_confirm_after_delay(self):
        engine = EventEngine()
        # 0ms 出现举手，399ms 尚未确认
        fired = drive(engine, [(0, 1, 0), (399, 1, 0)])
        self.assertEqual(fired, [])
        # 400ms 达到确认门限
        fired = engine.update(400, 1, 0)
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0][0], "RAISE")

    def test_no_duplicate_while_held(self):
        """持续举手 10 秒只应计一次。"""
        engine = EventEngine()
        timeline = [(t, 1, 0) for t in range(0, 10000, 100)]
        fired = drive(engine, timeline)
        self.assertEqual(engine.events_raise, 1)

    def test_release_then_re_raise(self):
        engine = EventEngine()
        drive(engine, [(0, 1, 0), (500, 1, 0)])       # 第一次确认
        drive(engine, [(600, 0, 0), (1700, 0, 0)])    # 放下并冷却满 1000ms
        self.assertFalse(engine.raise_active)
        drive(engine, [(1800, 1, 0), (2300, 1, 0)])   # 再次举手
        self.assertEqual(engine.events_raise, 2)

    def test_short_drop_does_not_reset(self):
        """短暂掉检（<RELEASE）不应让下一次举手立即重新计数。"""
        engine = EventEngine()
        drive(engine, [(0, 1, 0), (500, 1, 0)])
        drive(engine, [(600, 0, 0), (900, 0, 0)])     # 只掉 300ms
        self.assertTrue(engine.raise_active)
        fired = drive(engine, [(1000, 1, 0), (1500, 1, 0)])
        self.assertEqual(fired, [])                   # 仍在同一轮内
        self.assertEqual(engine.events_raise, 1)


class TestDownAlert(unittest.TestCase):

    def test_alert_after_two_seconds(self):
        engine = EventEngine()
        fired = drive(engine, [(0, 0, 1), (1999, 0, 1)])
        self.assertEqual(fired, [])
        fired = engine.update(2000, 0, 1)
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0][0], "DOWN_ALERT")
        self.assertTrue(engine.alert)

    def test_hysteresis_release(self):
        """恢复后需持续 RELEASE 时长才解除告警。"""
        engine = EventEngine()
        drive(engine, [(0, 0, 1), (2000, 0, 1)])
        self.assertTrue(engine.alert)
        drive(engine, [(2100, 0, 0), (3000, 0, 0)])   # 只恢复 900ms
        self.assertTrue(engine.alert)                 # 仍在告警
        drive(engine, [(3700, 0, 0)])                 # 累计超过 1500ms
        self.assertFalse(engine.alert)

    def test_flicker_does_not_spam(self):
        """临界抖动不应刷出多条告警。"""
        engine = EventEngine()
        timeline = []
        for i in range(40):
            timeline.append((i * 250, 0, 1 if i % 2 == 0 else 0))
        drive(engine, timeline)
        self.assertLessEqual(engine.events_down, 2)


class TestSnapshot(unittest.TestCase):

    def test_snapshot_fields(self):
        engine = EventEngine()
        drive(engine, [(0, 1, 0), (500, 1, 0)])
        snap = engine.snapshot()
        self.assertTrue(snap["raise_active"])
        self.assertEqual(snap["events_raise"], 1)
        self.assertFalse(snap["down_active"])

    def test_reset_keeps_totals(self):
        engine = EventEngine()
        drive(engine, [(0, 1, 0), (500, 1, 0)])
        engine.reset()
        self.assertFalse(engine.raise_active)
        self.assertEqual(engine.events_raise, 1)   # 累计是课堂事实，不清零

    def test_default_params_from_config(self):
        engine = EventEngine()
        self.assertEqual(engine.raise_confirm_ms, config.RAISE_CONFIRM_MS)
        self.assertEqual(engine.down_alert_ms, config.DOWN_ALERT_MS)


if __name__ == "__main__":
    unittest.main()
