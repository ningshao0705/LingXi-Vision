#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布构建脚本。

用途：把 firmware/ 组装成一张可直接拷贝进 SD 卡的发布目录，并做发布前
的一致性校验。

做三件事：
    1. 语法校验：逐个编译 lxt/*.py，避免把语法错误带到板端才发现；
    2. 一致性校验：单文件版 main.py 与模块化版 lxt/config.py 的关键阈值
       必须一致。两者算法同源，若有人只改了一处，这里会立刻报错；
    3. 可选预编译：若本机有 mpy-cross，把 lxt/ 编译为 .mpy 放进发布目录，
       显著降低板端导入期的堆占用与启动耗时。

用法：
    python tools/build_release.py
    python tools/build_release.py --mpy-cross /path/to/mpy-cross
    python tools/build_release.py --out dist/sdcard
"""

from __future__ import print_function

import argparse
import hashlib
import os
import py_compile
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIRMWARE = os.path.join(ROOT, "firmware")
PKG = os.path.join(FIRMWARE, "lxt")

# 必须在两个版本中保持一致的阈值常量
SHARED_CONSTANTS = (
    "PERSON_THRESHOLD", "KEYPOINT_THRESHOLD", "NMS_THRESHOLD",
    "RAISE_WRIST_ABOVE", "DOWN_HEAD_BELOW", "STAND_BOX_RATIO",
    "STAND_LEG_RATIO", "MIN_TORSO", "RAISE_CONFIRM_MS",
    "RAISE_RELEASE_MS", "DOWN_ALERT_MS", "DOWN_RELEASE_MS",
    "MAX_PEOPLE", "MODEL_INPUT_SIZE",
)


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def list_modules():
    names = []
    for name in sorted(os.listdir(PKG)):
        if name.endswith(".py"):
            names.append(name)
    # __init__ 必须排在首位，其余按依赖顺序粗排
    order = ["__init__.py", "compat.py", "config.py", "keypoints.py",
             "geometry.py", "rules.py", "events.py", "score.py",
             "proto.py", "pose.py", "hal.py", "render.py",
             "logger.py", "selfcheck.py", "app.py"]
    ordered = [n for n in order if n in names]
    ordered += [n for n in names if n not in ordered]
    return ordered


def syntax_check():
    """逐个模块做语法编译检查。"""
    ok = True
    for name in list_modules():
        path = os.path.join(PKG, name)
        try:
            py_compile.compile(path, cfile=path + "c", doraise=True)
        except py_compile.PyCompileError as exc:
            print("  [FAIL] %s: %s" % (name, exc))
            ok = False
        finally:
            if os.path.exists(path + "c"):
                os.remove(path + "c")
    return ok


def scan_source(name, text):
    """从源码文本中提取常量赋值（只处理字面量）。"""
    found = {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        left, right = stripped.split("=", 1)
        key = left.strip()
        if key in SHARED_CONSTANTS:
            found[key] = right.split("#")[0].strip()
    return found


def consistency_check():
    """比对单文件版与模块化版的共享常量。"""
    single = read(os.path.join(FIRMWARE, "main.py"))
    config_src = read(os.path.join(PKG, "config.py"))
    a = scan_source("main.py", single)
    b = scan_source("config.py", config_src)

    problems = []
    for key in SHARED_CONSTANTS:
        va, vb = a.get(key), b.get(key)
        if va is None or vb is None:
            problems.append("%s 在其中一侧缺失 (main=%r, config=%r)"
                            % (key, va, vb))
        elif va != vb:
            problems.append("%s 不一致: main.py=%s  config.py=%s"
                            % (key, va, vb))
    return problems


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(out_dir, mpy_cross=None, entry="main_modular.py"):
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    pkg_out = os.path.join(out_dir, "lxt")
    os.makedirs(pkg_out)

    total_lines = 0
    for name in list_modules():
        src = os.path.join(PKG, name)
        if mpy_cross and name != "__init__.py":
            dest = os.path.join(pkg_out, name[:-3] + ".mpy")
            subprocess.check_call([mpy_cross, "-O2", src, "-o", dest])
        else:
            dest = os.path.join(pkg_out, name)
            shutil.copy2(src, dest)
        total_lines += len(read(src).splitlines())

    entry_src = os.path.join(FIRMWARE, entry)
    shutil.copy2(entry_src, os.path.join(out_dir, "main.py"))
    total_lines += len(read(entry_src).splitlines())

    manifest = os.path.join(out_dir, "MANIFEST.txt")
    with open(manifest, "w", encoding="utf-8") as handle:
        handle.write("# LingXi Vision firmware release\n")
        handle.write("entry=main.py\n")
        handle.write("total_lines=%d\n" % total_lines)
        for name in sorted(os.listdir(pkg_out)):
            path = os.path.join(pkg_out, name)
            handle.write("%-18s %s\n" % (name, sha256(path)))
    return total_lines


def main():
    parser = argparse.ArgumentParser(description="构建板端发布目录")
    parser.add_argument("--out", default=os.path.join(ROOT, "dist", "sdcard"))
    parser.add_argument("--mpy-cross", default=None,
                        help="mpy-cross 可执行文件路径（可选）")
    parser.add_argument("--entry", default="main_modular.py",
                        choices=["main_modular.py", "main.py"])
    args = parser.parse_args()

    print("[1/3] 语法校验 ...")
    if not syntax_check():
        print("  语法校验未通过，终止")
        return 1
    print("  %d 个模块通过" % len(list_modules()))

    print("[2/3] 常量一致性校验 ...")
    problems = consistency_check()
    if problems:
        for item in problems:
            print("  [FAIL] " + item)
        return 1
    print("  %d 项共享常量一致" % len(SHARED_CONSTANTS))

    print("[3/3] 组装发布目录 ...")
    lines = build(args.out, args.mpy_cross, args.entry)
    print("  输出: %s" % args.out)
    print("  代码行数: %d" % lines)
    print("完成。把该目录内容整体复制到 SD 卡根目录即可。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
