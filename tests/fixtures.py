# -*- coding: utf-8 -*-
"""测试用骨架数据构造。

关键点格式为 (x, y, confidence)，屏幕坐标系，y 向下增大。
为便于阅读，坐标按 320x240 画面量级给出。
"""

from lxt.keypoints import (NOSE, L_EYE, R_EYE, L_SHO, R_SHO,
                           L_ELB, R_ELB, L_WRI, R_WRI,
                           L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANK, R_ANK)

INVISIBLE = 0.0
VISIBLE = 0.95


def blank():
    """17 个不可见关键点。"""
    return [(0, 0, INVISIBLE) for _ in range(17)]


def person(behavior="SIT"):
    """按目标行为构造一组合成关键点。"""
    pts = list(blank())

    if behavior == "UNKNOWN":
        # 双肩不可见，判定链缺少基准
        return pts

    if behavior == "STAND":
        shoulder, hip = 60, 130
        pts[NOSE] = (160, 30, VISIBLE)
        pts[L_EYE] = (155, 28, VISIBLE)
        pts[R_EYE] = (165, 28, VISIBLE)
        pts[L_SHO] = (140, shoulder, VISIBLE)
        pts[R_SHO] = (180, shoulder, VISIBLE)
        pts[L_ELB] = (135, 95, VISIBLE)
        pts[R_ELB] = (185, 95, VISIBLE)
        pts[L_WRI] = (130, 110, VISIBLE)
        pts[R_WRI] = (190, 110, VISIBLE)
        pts[L_HIP] = (145, hip, VISIBLE)
        pts[R_HIP] = (175, hip, VISIBLE)
        pts[L_KNEE] = (145, 180, VISIBLE)
        pts[R_KNEE] = (175, 180, VISIBLE)
        pts[L_ANK] = (145, 230, VISIBLE)
        pts[R_ANK] = (175, 230, VISIBLE)
        return pts

    # SIT / RAISE / DOWN 共用同一副躯干
    shoulder, hip = 80, 140
    pts[L_SHO] = (140, shoulder, VISIBLE)
    pts[R_SHO] = (180, shoulder, VISIBLE)
    pts[L_ELB] = (135, 110, VISIBLE)
    pts[R_ELB] = (185, 110, VISIBLE)
    pts[L_HIP] = (145, hip, VISIBLE)
    pts[R_HIP] = (175, hip, VISIBLE)
    pts[L_KNEE] = (145, 175, VISIBLE)
    pts[R_KNEE] = (175, 175, VISIBLE)

    if behavior == "RAISE":
        # 右手举起：手腕明显高于肩线
        pts[NOSE] = (160, 55, VISIBLE)
        pts[L_EYE] = (155, 52, VISIBLE)
        pts[R_EYE] = (165, 52, VISIBLE)
        pts[L_WRI] = (130, 130, VISIBLE)
        pts[R_WRI] = (190, 60, VISIBLE)      # 高于肩线
        return pts

    if behavior == "DOWN":
        # 头部塌到肩线以下
        pts[NOSE] = (160, 145, VISIBLE)
        pts[L_EYE] = (155, 142, VISIBLE)
        pts[R_EYE] = (165, 142, VISIBLE)
        pts[L_WRI] = (130, 150, VISIBLE)
        pts[R_WRI] = (190, 150, VISIBLE)
        return pts

    # SIT
    pts[NOSE] = (160, 55, VISIBLE)
    pts[L_EYE] = (155, 52, VISIBLE)
    pts[R_EYE] = (165, 52, VISIBLE)
    pts[L_WRI] = (130, 130, VISIBLE)
    pts[R_WRI] = (190, 130, VISIBLE)
    return pts


def rect_for(behavior, frame_h=240):
    """配套的人体框 (x, y, w, h)。"""
    if behavior == "STAND":
        return (120, 20, 80, int(frame_h * 0.85))
    return (120, 40, 80, 100)


def frame(behaviors, frame_h=240):
    """构造一帧多人的模型输出 [(rect, score, points)]。"""
    out = []
    for index, behavior in enumerate(behaviors):
        out.append((rect_for(behavior, frame_h), 0.9, person(behavior)))
    return out
