#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线数据回放。

把采集到的历史数据按原始时间节奏重新吐出 CBJSON / CBEVENT 文本行，
用于在脱离硬件的情况下联调前端、录制演示视频或做回归对比。

三种输出目标：
    --stdout          打印到终端（默认）
    --port COMx       写入指定串口，让前端或第三方软件以为是板端在发
    --file out.txt    写入文件

    python tools/data_replay.py status_20261101.csv --speed 2
    python tools/data_replay.py status_20261101.csv --port COM9
"""

from __future__ import print_function

import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "firmware"))

from lxt import proto            # noqa: E402


class FakeEngine(object):
    """回放用的事件累计器，接口与 EventEngine 的快照一致。"""

    def __init__(self):
        self.events_raise = 0
        self.events_down = 0
        self.down_active = False

    @property
    def alert(self):
        return self.down_active


def load_status(path):
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                rows.append({
                    "t": int(float(row.get("t") or 0)),
                    "count": int(float(row.get("count") or 0)),
                    "fps": float(row.get("fps") or 0),
                    "raise": int(float(row.get("raise") or 0)),
                    "down": int(float(row.get("down") or 0)),
                    "stand": int(float(row.get("stand") or 0)),
                    "sit": int(float(row.get("sit") or 0)),
                    "focus": int(float(row.get("focus") or 0)),
                    "total_raise": int(float(row.get("total_raise") or 0)),
                    "total_down": int(float(row.get("total_down") or 0)),
                    "peak": int(float(row.get("peak") or 0)),
                    "alert": int(float(row.get("alert") or 0)),
                })
            except (TypeError, ValueError):
                continue
    return rows


def replay(rows, sink, speed=1.0, loop=False, max_seconds=None):
    """按数据中的时间间隔回放。

    speed > 1 表示加速（2 即两倍速）。间隔被裁剪到 [0, 2] 秒，避免数据
    里存在长时间空档时回放卡住。
    """
    engine = FakeEngine()
    started = time.time()
    round_index = 0

    while True:
        previous_t = None
        for row in rows:
            if max_seconds and time.time() - started > max_seconds:
                return
            if previous_t is not None:
                delta = max(0.0, min(2.0, (row["t"] - previous_t) / 1000.0))
                time.sleep(delta / speed)
            previous_t = row["t"]

            engine.events_raise = row["total_raise"]
            engine.events_down = row["total_down"]
            engine.down_active = bool(row["alert"])

            counter = {"RAISE": row["raise"], "DOWN": row["down"],
                       "STAND": row["stand"], "SIT": row["sit"]}
            payload = proto.build_status(row["t"], row["count"], row["fps"],
                                         counter, row["focus"], engine,
                                         row["peak"])
            sink(proto.encode_status(payload))

        round_index += 1
        if not loop:
            return
        print("[replay] 第 %d 轮结束，重新开始" % round_index)


def main():
    parser = argparse.ArgumentParser(description="历史数据回放")
    parser.add_argument("csv", help="status_*.csv 路径")
    parser.add_argument("--port", default=None, help="写入串口，如 COM9")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--file", default=None, help="写入文件")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--seconds", type=float, default=None)
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        parser.error("文件不存在: %s" % args.csv)

    sinks = []

    if args.port:
        import serial
        handle = serial.Serial(args.port, args.baud, timeout=1)

        def _to_serial(text, _h=handle):
            _h.write((text + "\r\n").encode("utf-8"))
        sinks.append(_to_serial)

    out_handle = None
    if args.file:
        out_handle = open(args.file, "w", encoding="utf-8")

        def _to_file(text, _f=out_handle):
            _f.write(text + "\n")
            _f.flush()
        sinks.append(_to_file)

    if not sinks:
        sinks.append(lambda text: print(text))

    def sink(text):
        for fn in sinks:
            fn(text)

    rows = load_status(args.csv)
    print("加载 %d 条状态记录，speed=%.1f" % (len(rows), args.speed))
    try:
        replay(rows, sink, args.speed, args.loop, args.seconds)
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        if out_handle:
            out_handle.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
