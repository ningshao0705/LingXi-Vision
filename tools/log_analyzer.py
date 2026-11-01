#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教学日志分析。

读取板端写入 SD 卡的 classroom_log.csv（或 tools/serial_monitor.py 采集的
status_*.csv），产出一份课堂行为报告：事件统计、专注度曲线、异常时段。

    python tools/log_analyzer.py classroom_log.csv
    python tools/log_analyzer.py classroom_log.csv --report out/report.txt

CSV 格式（板端 logger.py 写出）：
    # classroom_behavior_log,version=2
    uptime_ms,event,people,count,focus
"""

from __future__ import print_function

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "firmware"))

from lxt import config                    # noqa: E402
from lxt.score import evaluate_lesson     # noqa: E402

EVENT_CN = {
    "RAISE": "举手发言",
    "DOWN_ALERT": "趴桌告警",
}


def load(path):
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            if len(parts) < 5:
                continue
            if parts[0] == "uptime_ms":       # 表头
                continue
            try:
                rows.append({
                    "t": int(parts[0]),
                    "event": parts[1],
                    "people": int(parts[2]),
                    "count": int(parts[3]),
                    "focus": int(parts[4]),
                })
            except ValueError:
                continue
    return rows


def analyze(rows):
    if not rows:
        return {"empty": True}

    events = {}
    for row in rows:
        events[row["event"]] = events.get(row["event"], 0) + 1

    focus_series = [row["focus"] for row in rows]
    counts = [row["count"] for row in rows]
    duration_ms = rows[-1]["t"] - rows[0]["t"]

    return {
        "empty": False,
        "samples": len(rows),
        "duration_min": round(duration_ms / 60000.0, 2),
        "events": events,
        "avg_count": round(sum(counts) / float(len(counts)), 2),
        "peak_count": max(counts),
        "lesson": evaluate_lesson(focus_series),
        "focus_series": focus_series,
        "first_ms": rows[0]["t"],
        "last_ms": rows[-1]["t"],
    }


def render_text(result, path=None):
    lines = []
    if result.get("empty"):
        lines.append("日志为空或格式不匹配")
    else:
        lesson = result["lesson"]
        lines.append("=" * 46)
        lines.append("灵犀智眸 · 课堂行为分析报告")
        lines.append("=" * 46)
        lines.append("样本点数    : %d" % result["samples"])
        lines.append("覆盖时长    : %.2f 分钟" % result["duration_min"])
        lines.append("平均在座    : %.2f 人" % result["avg_count"])
        lines.append("峰值人数    : %d 人" % result["peak_count"])
        lines.append("")
        lines.append("-- 事件统计 --")
        for name, num in sorted(result["events"].items()):
            lines.append("  %-14s %d 次" % (EVENT_CN.get(name, name), num))
        if not result["events"]:
            lines.append("  （本次记录无行为事件）")
        lines.append("")
        lines.append("-- 专注度 --")
        lines.append("  平均      : %.1f" % lesson["mean"])
        lines.append("  最低      : %.1f" % lesson["min"])
        lines.append("  最高      : %.1f" % lesson["max"])
        lines.append("  优良占比  : %.1f%%" % lesson["good_ratio"])
        lines.append("")
        if lesson["mean"] >= config.FOCUS_GOOD:
            verdict = "整体专注度良好"
        elif lesson["mean"] >= config.FOCUS_FAIR:
            verdict = "整体专注度一般，建议增加互动环节"
        else:
            verdict = "整体专注度偏低，建议排查教学内容与作息安排"
        lines.append("评价        : %s" % verdict)
        lines.append("=" * 46)

    text = "\n".join(lines)
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print("报告已写入 %s" % path)
    return text


def sparkline(series, width=40):
    """用 Unicode 块字符画一条迷你趋势线。"""
    if not series:
        return ""
    blocks = "▁▂▃▄▅▆▇█"
    step = max(1, len(series) // width)
    sampled = series[::step][:width]
    low, high = min(sampled), max(sampled)
    span = max(1.0, high - low)
    return "".join(blocks[min(7, int((v - low) / span * 7))] for v in sampled)


def main():
    parser = argparse.ArgumentParser(description="课堂行为日志分析")
    parser.add_argument("csv", help="classroom_log.csv 路径")
    parser.add_argument("--report", default=None, help="报告输出路径")
    parser.add_argument("--spark", action="store_true", help="打印专注度迷你趋势")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        parser.error("文件不存在: %s" % args.csv)

    result = analyze(load(args.csv))
    print(render_text(result, args.report))
    if args.spark and not result.get("empty"):
        print("专注度趋势: " + sparkline(result["focus_series"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
