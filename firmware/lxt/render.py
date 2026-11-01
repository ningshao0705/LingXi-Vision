"""OSD 叠加渲染。

板端直接在图像缓冲上绘制检测框、骨架、行为标签与状态栏，这样输出的
每一帧都自带完整语义，任何能显示画面的客户端都能直接看到结果，
不必依赖外部再做一次渲染。

依赖 image 对象的方法（draw_rectangle / draw_line / draw_circle /
draw_string），由 csi.snapshot() 返回的帧提供。
"""

from . import config
from . import keypoints


def draw_skeleton(img, points,
                  bone_color=None, joint_color=None, threshold=None):
    """绘制骨架连线与关键点。

    仅当两端点都可见时才连线，避免出现跨越画面的错误飞线。
    """
    bone = bone_color or keypoints.COLOR_BONE
    joint = joint_color or keypoints.COLOR_JOINT
    limit = config.KEYPOINT_THRESHOLD if threshold is None else threshold

    for a, b in keypoints.SKELETON:
        if points[a][2] >= limit and points[b][2] >= limit:
            img.draw_line((points[a][0], points[a][1],
                           points[b][0], points[b][1]),
                          color=bone, thickness=2)
    for x, y, confidence in points:
        if confidence >= limit:
            img.draw_circle((x, y, 2), color=joint, fill=True)


def draw_person(img, rect, label, score, color):
    """绘制人体框与行为标签。

    标签放在框上方；当框贴近画面顶部时下移到框内，避免文字被裁掉。
    """
    img.draw_rectangle(rect, color=color, thickness=2)
    x, y = rect[0], rect[1]
    if y < 18:
        y = rect[1] + rect[3]
    else:
        y = max(18, y - 2)
    img.draw_string((x, y), "%s %.2f" % (label, score), color=color)


def _bar(img, top, height):
    """画一条通栏黑色底，用于承载文字。"""
    img.draw_rectangle((0, top, img.width(), height),
                       color=keypoints.COLOR_OSD_BG, fill=True)


def draw_top_bar(img, counter, count, focus):
    """顶部状态栏：人数 + 四类行为计数 + 专注度。"""
    _bar(img, 0, 16)
    img.draw_string(
        (2, 2),
        "P:%d R:%d D:%d S:%d T:%d" % (count,
                                      counter.get("RAISE", 0),
                                      counter.get("DOWN", 0),
                                      counter.get("STAND", 0),
                                      counter.get("SIT", 0)),
        color=keypoints.COLOR_OSD_TEXT)
    if focus >= config.FOCUS_GOOD:
        color = keypoints.COLOR_SIT
    elif focus >= config.FOCUS_FAIR:
        color = keypoints.COLOR_RAISE
    else:
        color = keypoints.COLOR_DOWN
    img.draw_string((img.width() - 88, 2),
                    "F:%d%%" % int(focus), color=color)


def draw_bottom_bar(img, fps, engine):
    """底部信息栏：帧率 + 事件累计。"""
    height = img.height()
    _bar(img, height - 14, 14)
    img.draw_string(
        (2, height - 12),
        "FPS:%.1f Events R:%d D:%d" % (fps, engine.events_raise,
                                       engine.events_down),
        color=keypoints.COLOR_OSD_DIM)


def draw_alert_banner(img, text="DOWN ALERT"):
    """趴桌告警时在画面中部弹出提示条。"""
    width = img.width()
    top = img.height() // 2 - 10
    img.draw_rectangle((0, top, width, 20),
                       color=keypoints.COLOR_DOWN, fill=True)
    img.draw_string((width // 2 - 40, top + 4), text,
                    color=keypoints.COLOR_OSD_BG)


def render_frame(img, people_details, counter, count, focus, fps, engine):
    """一帧的完整渲染流程。

    先画个体（框/骨架/标签），再画状态栏——顺序不能反，否则状态栏
    会被后续的人体框覆盖。
    """
    for label, color, rect, score, points in people_details:
        draw_person(img, rect, label, score, color)
        draw_skeleton(img, points)
    draw_top_bar(img, counter, count, focus)
    draw_bottom_bar(img, fps, engine)
    if engine.alert:
        draw_alert_banner(img)
