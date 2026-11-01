#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PC 端串口监听与数据采集。

用途：连上板子的数据口（Windows 下形如 COM7，VID:PID = 37C5:16E3），
实时解析 CBJSON 状态流与 CBEVENT 事件流，同时落盘为 CSV / JSONL，
供前端联调、演示录制与课后分析使用。

    python tools/serial_monitor.py --port COM7
    python tools/serial_monitor.py --port COM7 --save out/
    python tools/serial_monitor.py --list

依赖：pyserial（pip install pyserial）
"""

from __future__ import print_function

import argparse
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "firmware"))

from lxt import proto            # noqa: E402


def list_ports():
    try:
        import serial.tools.list_ports as lp
    except ImportError:
        print("未安装 pyserial，无法枚举串口")
        return
    for port in lp.comports():
        print("%-8s %s  %s" % (port.device, port.description or "",
                               port.hwid or ""))


class Collector(object):
    """把串口数据流分流成状态序列与事件序列。"""

    def __init__(self, save_dir=None):
        self.save_dir = save_dir
        self.status_rows = []
        self.event_rows = []
        self.raw = []
        self.csv_writer = None
        self.csv_handle = None
        self.json_handle = None
        self._setup_files()

    def _setup_files(self):
        if not self.save_dir:
            return
        if not os.path.isdir(self.save_dir):
            os.makedirs(self.save_dir)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.csv_handle = open(os.path.join(self.save_dir,
                                            "status_%s.csv" % stamp),
                               "w", newline="", encoding="utf-8")
        self.csv_writer = csv.writer(self.csv_handle)
        self.csv_writer.writerow(["wall_time", "t", "count", "fps", "raise",
                                  "down", "stand", "sit", "focus",
                                  "total_raise", "total_down", "peak",
                                  "alert"])
        self.json_handle = open(os.path.join(self.save_dir,
                                             "events_%s.jsonl" % stamp),
                                "w", encoding="utf-8")

    def feed(self, line):
        self.raw.append(line)
        item = proto.decode_line(line)
        if item is None:
            return None
        wall = time.strftime("%H:%M:%S")
        if "event" in item:
            self.event_rows.append(item)
            print("[EVENT] %s %s" % (wall, item))
            if self.json_handle:
                self.json_handle.write(json.dumps(item, ensure_ascii=False)
                                       + "\n")
                self.json_handle.flush()
        else:
            self.status_rows.append(item)
            print("[STATUS] %s count=%s fps=%s focus=%s R=%s D=%s"
                  % (wall, item.get("count"), item.get("fps"),
                     item.get("focus"), item.get("raise"),
                     item.get("down")))
            if self.csv_writer:
                self.csv_writer.writerow([wall, item.get("t"),
                                          item.get("count"), item.get("fps"),
                                          item.get("raise"), item.get("down"),
                                          item.get("stand"), item.get("sit"),
                                          item.get("focus"),
                                          item.get("total_raise"),
                                          item.get("total_down"),
                                          item.get("peak"),
                                          item.get("alert")])
                self.csv_handle.flush()
        return item

    def close(self):
        for handle in (self.csv_handle, self.json_handle):
            if handle:
                handle.close()

    def summary(self):
        if not self.status_rows:
            return "未采集到状态数据"
        frames = len(self.status_rows)
        fps = [r.get("fps", 0) for r in self.status_rows]
        focus = [r.get("focus", 0) for r in self.status_rows]
        peak = max(r.get("peak", 0) for r in self.status_rows)
        return ("帧数=%d  平均帧率=%.1f  平均专注度=%.1f  "
                "峰值人数=%d  事件=%d"
                % (frames, sum(fps) / frames, sum(focus) / frames,
                   peak, len(self.event_rows)))


def monitor(port, baud=115200, save_dir=None, duration=None):
    try:
        import serial
    except ImportError:
        print("请先安装 pyserial: pip install pyserial")
        return 1

    collector = Collector(save_dir)
    try:
        handle = serial.Serial(port, baud, timeout=1)
    except Exception as exc:
        print("打开 %s 失败: %s" % (port, exc))
        return 1

    print("已连接 %s @ %d，按 Ctrl+C 结束" % (port, baud))
    started = time.time()
    try:
        while True:
            if duration and time.time() - started > duration:
                break
            try:
                raw = handle.readline()
            except Exception:
                break
            if not raw:
                continue
            line = raw.decode("utf-8", "replace").strip()
            if line:
                collector.feed(line)
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        handle.close()
        print(collector.summary())
        collector.close()
    return 0


def main():
    parser = argparse.ArgumentParser(description="灵犀智眸串口监听")
    parser.add_argument("--port", help="串口号，如 COM7 或 /dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--save", default=None, help="落盘目录")
    parser.add_argument("--duration", type=float, default=None,
                        help="采集时长（秒），不填则持续采集")
    parser.add_argument("--list", action="store_true", help="列出可用串口")
    args = parser.parse_args()

    if args.list:
        list_ports()
        return 0
    if not args.port:
        parser.error("需要 --port，或用 --list 查看可用串口")
    return monitor(args.port, args.baud, args.save, args.duration)


if __name__ == "__main__":
    sys.exit(main())
