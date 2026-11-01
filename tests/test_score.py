# -*- coding: utf-8 -*-
"""专注度评分单元测试。

评分是给老师看的唯一一个"量化结论"，这里的用例锁定了三类边界：
全员专注、全员趴桌、以及空教室不该被判成 0 分。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "firmware"))

from lxt.score import FocusScorer, evaluate_lesson     # noqa: E402
from lxt import config                                 # noqa: E402


class TestInstant(unittest.TestCase):

    def test_all_sit_is_full(self):
        scorer = FocusScorer()
        self.assertAlmostEqual(scorer.instant({"SIT": 4}), 100.0)

    def test_all_down_is_zero(self):
        scorer = FocusScorer()
        self.assertAlmostEqual(scorer.instant({"DOWN": 3}), 0.0)

    def test_mixed(self):
        scorer = FocusScorer()
        # 2 坐姿 + 1 站立 + 1 趴桌 -> (1 + 1 + 0.85 + 0) / 4 * 100
        value = scorer.instant({"SIT": 2, "STAND": 1, "DOWN": 1})
        self.assertAlmostEqual(value, 71.25)

    def test_empty_room_keeps_previous(self):
        """无人时保持上一次的值，避免下课期间出现刺眼低谷。"""
        scorer = FocusScorer()
        scorer.update({"SIT": 2})
        previous = scorer.value
        self.assertAlmostEqual(scorer.instant({}), previous)

    def test_clamped(self):
        scorer = FocusScorer()
        self.assertLessEqual(scorer.instant({"SIT": 1, "RAISE": 1}), 100.0)
        self.assertGreaterEqual(scorer.instant({"DOWN": 1}), 0.0)


class TestSmoothing(unittest.TestCase):

    def test_ema_converges(self):
        scorer = FocusScorer()
        scorer.value = 100.0
        for _ in range(40):
            scorer.update({"DOWN": 5})
        self.assertLess(scorer.value, 5.0)

    def test_ema_damps_single_frame_spike(self):
        """单帧误判不应让分数剧烈跳动。"""
        scorer = FocusScorer()
        scorer.value = 100.0
        scorer.update({"DOWN": 1})
        self.assertGreater(scorer.value, 80.0)

    def test_peak_and_valley_tracked(self):
        scorer = FocusScorer()
        scorer.update({"SIT": 3})
        for _ in range(30):
            scorer.update({"DOWN": 3})
        self.assertAlmostEqual(scorer.peak, 100.0)
        self.assertLess(scorer.valley, 20.0)

    def test_grade(self):
        scorer = FocusScorer()
        scorer.value = 90
        self.assertEqual(scorer.grade(), "good")
        scorer.value = 70
        self.assertEqual(scorer.grade(), "fair")
        scorer.value = 30
        self.assertEqual(scorer.grade(), "poor")

    def test_grade_boundaries(self):
        scorer = FocusScorer()
        scorer.value = config.FOCUS_GOOD
        self.assertEqual(scorer.grade(), "good")
        scorer.value = config.FOCUS_GOOD - 1
        self.assertEqual(scorer.grade(), "fair")


class TestLessonSummary(unittest.TestCase):

    def test_empty(self):
        result = evaluate_lesson([])
        self.assertEqual(result["samples"], 0)
        self.assertEqual(result["mean"], 0.0)

    def test_summary(self):
        series = [90, 85, 40, 88, 92]
        result = evaluate_lesson(series)
        self.assertEqual(result["samples"], 5)
        self.assertAlmostEqual(result["mean"], 79.0)
        self.assertEqual(result["min"], 40)
        self.assertEqual(result["max"], 92)
        self.assertAlmostEqual(result["good_ratio"], 80.0)


if __name__ == "__main__":
    unittest.main()
