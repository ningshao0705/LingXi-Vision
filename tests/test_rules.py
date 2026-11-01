# -*- coding: utf-8 -*-
"""行为判定规则单元测试。

这些用例把四类行为的几何条件固定下来：以后调整阈值时，若某条用例失败，
说明行为边界被移动了，需要同步更新文档里的阈值表。

运行：
    python -m unittest discover -s tests -p "test_*.py"
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "firmware"))

from lxt import geometry, rules                    # noqa: E402
from lxt.keypoints import COLOR_UNKNOWN           # noqa: E402
from fixtures import person, rect_for, frame, VISIBLE, INVISIBLE  # noqa: E402

FRAME_H = 240


class TestGeometry(unittest.TestCase):

    def test_shoulder_line(self):
        pts = person("SIT")
        y, valid = geometry.shoulder_line(pts)
        self.assertTrue(valid)
        self.assertAlmostEqual(y, 80.0)

    def test_shoulder_line_invalid(self):
        pts = person("UNKNOWN")
        _y, valid = geometry.shoulder_line(pts)
        self.assertFalse(valid)

    def test_torso_length(self):
        pts = person("SIT")
        length, hip_y = geometry.torso_length(pts, 80.0)
        self.assertAlmostEqual(length, 60.0)
        self.assertAlmostEqual(hip_y, 140.0)

    def test_torso_lower_bound(self):
        """髋部塌缩时躯干长不应趋零，否则归一化阈值会被放大。"""
        pts = person("SIT")
        pts[11] = (145, 80, VISIBLE)
        pts[12] = (175, 80, VISIBLE)
        length, _hip = geometry.torso_length(pts, 80.0)
        self.assertGreaterEqual(length, 8.0)

    def test_head_y_fallback_to_eyes(self):
        pts = person("SIT")
        pts[0] = (160, 55, INVISIBLE)      # 鼻子不可见
        self.assertAlmostEqual(geometry.head_y(pts), 52.0)

    def test_head_y_none(self):
        pts = person("SIT")
        pts[0] = (160, 55, INVISIBLE)
        pts[1] = (155, 52, INVISIBLE)
        pts[2] = (165, 52, INVISIBLE)
        self.assertIsNone(geometry.head_y(pts))

    def test_wrist_height_picks_higher(self):
        pts = person("RAISE")
        self.assertEqual(geometry.wrist_height(pts), 60)

    def test_wrist_height_none(self):
        pts = person("SIT")
        pts[9] = (130, 130, INVISIBLE)
        pts[10] = (190, 130, INVISIBLE)
        self.assertIsNone(geometry.wrist_height(pts))

    def test_box_ratio(self):
        self.assertAlmostEqual(geometry.box_height_ratio((0, 0, 80, 120), 240),
                               0.5)


class TestClassify(unittest.TestCase):

    def _check(self, behavior, expected):
        label, _color = rules.classify(person(behavior),
                                       rect_for(behavior), FRAME_H)
        self.assertEqual(label, expected)

    def test_sit(self):
        self._check("SIT", "SIT")

    def test_raise(self):
        self._check("RAISE", "RAISE")

    def test_down(self):
        self._check("DOWN", "DOWN")

    def test_stand(self):
        self._check("STAND", "STAND")

    def test_unknown_when_shoulders_missing(self):
        label, color = rules.classify(person("UNKNOWN"),
                                      rect_for("UNKNOWN"), FRAME_H)
        self.assertEqual(label, "UNKNOWN")
        self.assertEqual(color, COLOR_UNKNOWN)

    def test_head_missing_is_not_down(self):
        """缺少头部信息不能推定趴桌——宁可不判。"""
        pts = person("DOWN")
        pts[0] = (160, 145, INVISIBLE)
        pts[1] = (155, 142, INVISIBLE)
        pts[2] = (165, 142, INVISIBLE)
        label, _c = rules.classify(pts, rect_for("DOWN"), FRAME_H)
        self.assertNotEqual(label, "DOWN")

    def test_raise_takes_priority(self):
        """举手优先于其他判定：举手时头部位置可能偏低。"""
        pts = person("RAISE")
        pts[0] = (160, 150, VISIBLE)      # 头部也低，但手腕已举起
        label, _c = rules.classify(pts, rect_for("RAISE"), FRAME_H)
        self.assertEqual(label, "RAISE")


class TestAggregate(unittest.TestCase):

    def test_classify_all_counts(self):
        people = frame(["SIT", "RAISE", "DOWN"])
        counter, details = rules.classify_all(people, FRAME_H)
        self.assertEqual(counter["SIT"], 1)
        self.assertEqual(counter["RAISE"], 1)
        self.assertEqual(counter["DOWN"], 1)
        self.assertEqual(len(details), 3)

    def test_count_people_excludes_unknown(self):
        counter = {"SIT": 3, "UNKNOWN": 2}
        self.assertEqual(rules.count_people(counter), 3)

    def test_empty_frame(self):
        counter, details = rules.classify_all([], FRAME_H)
        self.assertEqual(details, [])
        self.assertEqual(rules.count_people(counter), 0)


if __name__ == "__main__":
    unittest.main()
