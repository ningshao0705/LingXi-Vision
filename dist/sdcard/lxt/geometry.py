"""关键点几何量计算。

行为判定不使用分类器，而依赖一组几何量。这样做的前提是：课堂场景的
四类行为在骨架几何上区分度足够，且几何量天然具备尺度不变性——把长度
用躯干长归一化后，前排与后排学生可以共用同一套阈值。

所有函数均 [纯 Python]，可在 PC 端直接测试。
"""

from . import config
from .keypoints import (NOSE, L_EYE, R_EYE, L_SHO, R_SHO,
                        L_HIP, R_HIP, L_WRI, R_WRI, L_ANK, R_ANK)


def _ok(point):
    return point[2] >= config.KEYPOINT_THRESHOLD


def midpoint_y(a, b):
    """两点纵坐标中点。"""
    return (a[1] + b[1]) / 2.0


def shoulder_line(points):
    """肩线纵坐标。

    返回 (y, valid)。双肩都可见才算有效，否则整条判定链失去基准，
    上层会直接判为 UNKNOWN——宁可不判，也不要用单点噪声硬猜。
    """
    if _ok(points[L_SHO]) and _ok(points[R_SHO]):
        return midpoint_y(points[L_SHO], points[R_SHO]), True
    return 0.0, False


def torso_length(points, shoulder_y):
    """躯干长（肩线到髋线的垂直距离）。

    这是全部归一化阈值的基准量。取 max(...) 下限是为了避免学生侧身
    或严重遮挡时髋部关键点塌缩到肩线附近，导致分母趋零后阈值被放大。
    """
    if _ok(points[L_HIP]) and _ok(points[R_HIP]):
        hip_y = midpoint_y(points[L_HIP], points[R_HIP])
        return max(float(config.MIN_TORSO), hip_y - shoulder_y), hip_y
    return float(config.MIN_TORSO), shoulder_y + config.MIN_TORSO


def head_y(points):
    """头部纵坐标。

    优先用鼻子；鼻子被遮挡时退化为双眼中点；都不可见返回 None，
    交由上层跳过趴桌判定（缺少头部信息不能推定趴桌）。
    """
    if _ok(points[NOSE]):
        return points[NOSE][1]
    if _ok(points[L_EYE]) and _ok(points[R_EYE]):
        return midpoint_y(points[L_EYE], points[R_EYE])
    return None


def wrist_height(points):
    """两手中较高的手腕纵坐标（屏幕坐标 y 越小越高）。

    返回 None 表示双手均不可见。
    """
    candidates = [points[L_WRI][1] if _ok(points[L_WRI]) else None,
                  points[R_WRI][1] if _ok(points[R_WRI]) else None]
    visible = [y for y in candidates if y is not None]
    if not visible:
        return None
    return min(visible)


def leg_span(points, hip_y, frame_h):
    """髋-踝展开量，用于区分站立与坐姿。

    坐姿下踝部通常被课桌遮挡或髋踝几乎同高，展开量小；站立时双腿
    伸展，展开量显著。除以画面高归一化，消除分辨率差异。
    """
    ankles = [points[L_ANK][1] if _ok(points[L_ANK]) else None,
              points[R_ANK][1] if _ok(points[R_ANK]) else None]
    visible = [y for y in ankles if y is not None]
    if not visible:
        return 0.0
    return (max(visible) - hip_y) / float(frame_h)


def box_height_ratio(rect, frame_h):
    """人体框高占画面高度的比例。"""
    if not frame_h:
        return 0.0
    return rect[3] / float(frame_h)


def summarize(points, rect, frame_h):
    """一次性算出判定所需的全部几何量。

    合并计算的目的是避免各判定分支重复取点——在 MicroPython 上，
    每次列表索引与函数调用都有实打实的开销，21 FPS 的余量不多。
    """
    shoulder_y, valid = shoulder_line(points)
    return {
        "valid": valid,
        "shoulder_y": shoulder_y,
        "torso": torso_length(points, shoulder_y)[0] if valid else config.MIN_TORSO,
        "hip_y": torso_length(points, shoulder_y)[1] if valid else shoulder_y,
        "head_y": head_y(points),
        "wrist_y": wrist_height(points),
        "leg_span": leg_span(points, torso_length(points, shoulder_y)[1]
                             if valid else shoulder_y, frame_h),
        "box_ratio": box_height_ratio(rect, frame_h),
    }
