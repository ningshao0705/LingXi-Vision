"""示例 2：行为判定离线验证。

不接摄像头，直接用合成关键点喂给规则引擎，验证阈值是否符合预期。
lxt.rules 与 lxt.geometry 均为纯 Python，因此在 PC 上也能直接运行，
便于在没有硬件在场时调整阈值——这也是把判定逻辑与驱动解耦的收益。

板端运行：把 skeleton() 的返回值换成 model.predict() 的输出即可。
"""

from lxt.keypoints import BEHAVIOR_LABEL_CN, NOSE, L_EYE, R_EYE, \
    L_SHO, R_SHO, L_ELB, R_ELB, L_WRI, R_WRI, \
    L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANK, R_ANK
from lxt.rules import classify, classify_all, count_people

FRAME_H = 240
VISIBLE = 0.95
HIDDEN = 0.0


def skeleton(behavior):
    """按目标行为构造一组合成关键点（坐标按 320x240 画面量级）。"""
    pts = [(0, 0, HIDDEN) for _ in range(17)]
    if behavior == "UNKNOWN":
        return pts, (120, 40, 80, 100)

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
        return pts, (120, 20, 80, 204)

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
        pts[NOSE] = (160, 55, VISIBLE)
        pts[L_EYE] = (155, 52, VISIBLE)
        pts[R_EYE] = (165, 52, VISIBLE)
        pts[L_WRI] = (130, 130, VISIBLE)
        pts[R_WRI] = (190, 60, VISIBLE)          # 手腕高于肩线
    elif behavior == "DOWN":
        pts[NOSE] = (160, 145, VISIBLE)          # 头部塌到肩线以下
        pts[L_EYE] = (155, 142, VISIBLE)
        pts[R_EYE] = (165, 142, VISIBLE)
        pts[L_WRI] = (130, 150, VISIBLE)
        pts[R_WRI] = (190, 150, VISIBLE)
    else:
        pts[NOSE] = (160, 55, VISIBLE)
        pts[L_EYE] = (155, 52, VISIBLE)
        pts[R_EYE] = (165, 52, VISIBLE)
        pts[L_WRI] = (130, 130, VISIBLE)
        pts[R_WRI] = (190, 130, VISIBLE)
    return pts, (120, 40, 80, 100)


def main():
    print("单人判定：")
    for behavior in ("SIT", "RAISE", "DOWN", "STAND", "UNKNOWN"):
        pts, rect = skeleton(behavior)
        label, _color = classify(pts, rect, FRAME_H)
        flag = "OK" if label == behavior else "MISMATCH"
        print("  %-8s -> %-8s %-9s %s"
              % (behavior, label, flag, BEHAVIOR_LABEL_CN.get(label, "")))

    print("多人统计：")
    people = []
    for behavior in ("SIT", "RAISE", "DOWN", "SIT"):
        pts, rect = skeleton(behavior)
        people.append((rect, 0.90, pts))

    counter, details = classify_all(people, FRAME_H)
    for label, _color, rect, score, _pts in details:
        print("  %-8s score=%.2f rect=%s" % (label, score, rect))
    print("  汇总: %s  有效人数=%d" % (counter, count_people(counter)))


if __name__ == "__main__":
    main()
