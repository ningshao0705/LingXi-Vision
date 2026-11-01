"""全局配置。

所有可调参数集中在此，便于按教室场景（小学/中学/阶梯教室）做整包替换。
板端 MicroPython 内存紧张，这里刻意不使用类封装，全部为模块级常量，
导入后即为只读引用，无额外堆开销。
"""

# ---------------- 模型 ----------------
# 注意：此处为 SD 卡上的真实文件名，与模型导出配置绑定，不可重命名
MODEL_PATH = "/rom/yolov8n_pose_192_u55_256.tflite"
MODEL_INPUT_SIZE = 192
PERSON_THRESHOLD = 0.40        # 人体框置信度门限
KEYPOINT_THRESHOLD = 0.50      # 关键点可见性门限
NMS_THRESHOLD = 0.45           # 非极大值抑制 IoU 门限
MAX_PEOPLE = 10                # 单帧最多处理人数（超出按得分截断）

# ---------------- 摄像头 ----------------
CAM_PIXFORMAT = "RGB565"
CAM_FRAMESIZE = "QVGA"         # 320 x 240
CAM_WARMUP_MS = 2000           # 自动曝光/白平衡收敛等待

# ---------------- 存储 ----------------
LOG_PATH = "/classroom_log.csv"
LOG_FLUSH_EVERY = 1            # 每条事件即落盘，掉电不丢

# ---------------- 行为判定阈值 ----------------
# 全部以躯干长（肩线到髋线）为单位归一化，从而对远近尺度不敏感
RAISE_WRIST_ABOVE = 0.15       # 手腕高于肩线 0.15 倍躯干长 -> 举手
DOWN_HEAD_BELOW = 0.45         # 头部低于肩线 0.45 倍躯干长 -> 趴桌
STAND_BOX_RATIO = 0.55         # 人体框高 / 画面高 超过此值
STAND_LEG_RATIO = 0.18         # 髋踝展开 / 画面高 超过此值
MIN_TORSO = 8.0                # 躯干长下限，防止除零与误判

# ---------------- 事件引擎（毫秒） ----------------
RAISE_CONFIRM_MS = 400         # 举手持续 0.4s 才计一次发言
RAISE_RELEASE_MS = 1000        # 放下 1s 后才允许下一次计数
DOWN_ALERT_MS = 2000           # 趴桌持续 2s 触发告警
DOWN_RELEASE_MS = 1500         # 恢复正常 1.5s 解除告警（滞回）

# ---------------- 专注度评分 ----------------
FOCUS_WEIGHT = {
    "RAISE": 1.0,              # 举手发言
    "SIT": 1.0,                # 坐姿端正
    "STAND": 0.85,             # 站立（可能是走动/回答问题）
    "DOWN": 0.0,               # 趴桌
    "UNKNOWN": 0.5,            # 关键点不全，中性处理
}
FOCUS_EMA_ALPHA = 0.15
FOCUS_GOOD = 80                # 绿色档
FOCUS_FAIR = 60                # 黄色档

# ---------------- 输出节奏（毫秒） ----------------
REPORT_JSON_MS = 500           # CBJSON 状态流周期
REPORT_TEXT_MS = 1000          # 人类可读摘要周期
HEARTBEAT_MS = 500             # LED1 心跳翻转周期

# ---------------- 串口 ----------------
UART_BAUDRATE = 115200

# ---------------- 板载 LED 编号 ----------------
LED_HEARTBEAT = 1              # 系统运行指示
LED_ALERT = 2                  # 趴桌告警
LED_RAISE = 3                  # 举手提示
