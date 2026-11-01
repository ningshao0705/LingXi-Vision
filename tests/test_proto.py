# -*- coding: utf-8 -*-
"""数据协议单元测试。

协议是板端与前端之间唯一的契约，这里的用例同时充当契约说明。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "firmware"))

from lxt import proto                            # noqa: E402
from lxt.events import EventEngine               # noqa: E402


class FakeEngine(object):
    def __init__(self, raise_n=0, down_n=0, alert=False):
        self.events_raise = raise_n
        self.events_down = down_n
        self.down_active = alert

    @property
    def alert(self):
        return self.down_active


COUNTER = {"RAISE": 1, "DOWN": 0, "STAND": 0, "SIT": 2}


class TestBuild(unittest.TestCase):

    def test_status_fields(self):
        payload = proto.build_status(1234, 3, 21.6, COUNTER, 87.4,
                                     FakeEngine(5, 1), 6)
        self.assertEqual(payload["count"], 3)
        self.assertEqual(payload["fps"], 21.6)
        self.assertEqual(payload["focus"], 87)
        self.assertEqual(payload["total_raise"], 5)
        self.assertEqual(payload["peak"], 6)
        self.assertEqual(payload["alert"], 0)
        self.assertEqual(payload["dev"], proto.DEVICE_MODEL)

    def test_status_alert_flag(self):
        payload = proto.build_status(0, 1, 20.0, COUNTER, 50,
                                     FakeEngine(0, 1, alert=True), 1)
        self.assertEqual(payload["alert"], 1)

    def test_event_fields(self):
        payload = proto.build_event(9000, "RAISE", 1, 3, 88)
        self.assertEqual(payload["event"], "RAISE")
        self.assertEqual(payload["t"], 9000)


class TestEncode(unittest.TestCase):

    def test_status_prefix(self):
        line = proto.encode_status(proto.build_status(
            0, 1, 20.0, COUNTER, 90, FakeEngine(), 1))
        self.assertTrue(line.startswith("CBJSON:{"))

    def test_event_prefix(self):
        line = proto.encode_event(proto.build_event(0, "RAISE", 1, 1, 90))
        self.assertTrue(line.startswith("CBEVENT:"))
        self.assertIn("event=RAISE", line)

    def test_roundtrip(self):
        payload = proto.build_status(4321, 2, 19.8, COUNTER, 76.2,
                                     FakeEngine(3, 0), 5)
        parsed = proto.decode_line(proto.encode_status(payload))
        self.assertEqual(parsed["t"], 4321)
        self.assertEqual(parsed["count"], 2)
        self.assertEqual(parsed["sit"], 2)
        self.assertEqual(parsed["total_raise"], 3)

    def test_string_escaping(self):
        payload = {"dev": 'a"b'}
        text = proto.dumps(payload)
        self.assertNotIn('a"b"', text)
        self.assertEqual(proto.loads(text)["dev"], "a'b")

    def test_decode_non_protocol_line(self):
        self.assertIsNone(proto.decode_line("People:1 Raise:0"))
        self.assertIsNone(proto.decode_line(""))

    def test_event_decode(self):
        line = proto.encode_event(proto.build_event(1200, "DOWN_ALERT", 2, 5, 40))
        parsed = proto.decode_line(line)
        self.assertEqual(parsed["event"], "DOWN_ALERT")
        self.assertEqual(parsed["count"], 5)


class TestIntegration(unittest.TestCase):
    """端到端：事件引擎触发的事件应能被前端解析。"""

    def test_engine_output_parsable(self):
        engine = EventEngine()
        fired = []
        for t in range(0, 900, 100):
            fired.extend(engine.update(t, 1, 0))
        self.assertEqual(len(fired), 1)
        name, people = fired[0]
        line = proto.encode_event(
            proto.build_event(800, name, people, 3, 90))
        parsed = proto.decode_line(line)
        self.assertEqual(parsed["event"], "RAISE")
        self.assertEqual(parsed["people"], 1)


if __name__ == "__main__":
    unittest.main()
