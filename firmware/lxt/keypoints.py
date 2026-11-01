"""COCO 17 关键点定义、骨架连接与行为配色。

顺序与模型导出时保持一致，改动会导致骨架连线错乱。
"""

# ---- 关键点索引 ----
NOSE, L_EYE, R_EYE, L_EAR, R_EAR = 0, 1, 2, 3, 4
L_SHO, R_SHO, L_ELB, R_ELB, L_WRI, R_WRI = 5, 6, 7, 8, 9, 10
L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANK, R_ANK = 11, 12, 13, 14, 15, 16

NAMES = (
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
)

# ---- 骨架连线（索引对） ----
SKELETON = (
    (0, 1), (0, 2), (1, 3), (2, 4),        # 头部
    (5, 6),                                 # 肩线
    (5, 7), (7, 9),                         # 左臂
    (6, 8), (8, 10),                        # 右臂
    (5, 11), (6, 12), (11, 12),             # 躯干
    (11, 13), (13, 15),                     # 左腿
    (12, 14), (14, 16),                     # 右腿
)

# ---- 行为配色 (R, G, B) ----
COLOR_RAISE = (255, 255, 0)     # 举手    黄
COLOR_DOWN = (255, 0, 0)        # 趴桌    红
COLOR_STAND = (0, 255, 255)     # 站立    青
COLOR_SIT = (0, 255, 0)         # 坐姿    绿
COLOR_UNKNOWN = (160, 160, 160)  # 未知    灰

BEHAVIOR_COLOR = {
    "RAISE": COLOR_RAISE,
    "DOWN": COLOR_DOWN,
    "STAND": COLOR_STAND,
    "SIT": COLOR_SIT,
    "UNKNOWN": COLOR_UNKNOWN,
}

BEHAVIOR_LABEL_CN = {
    "RAISE": "举手发言",
    "DOWN": "趴桌/低头",
    "STAND": "站立",
    "SIT": "坐姿端正",
    "UNKNOWN": "未确定",
}

# ---- 行为类别（顺序即统计输出顺序） ----
BEHAVIORS = ("RAISE", "DOWN", "STAND", "SIT")

# ---- 渲染配色 ----
COLOR_BONE = (0, 255, 255)
COLOR_JOINT = (255, 255, 0)
COLOR_OSD_BG = (0, 0, 0)
COLOR_OSD_TEXT = (255, 255, 255)
COLOR_OSD_DIM = (200, 200, 200)


def visible(point, threshold):
    """判断关键点是否可见（置信度达到门限）。"""
    return point[2] >= threshold
