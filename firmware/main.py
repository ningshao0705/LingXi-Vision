import csi
import math
import ml
import time
from machine import LED

MODEL_PATH = "/rom/yolov8n_pose_192_u55_256.tflite"
MODEL_INPUT_SIZE = 192
PERSON_THRESHOLD = 0.40
KEYPOINT_THRESHOLD = 0.50
NMS_THRESHOLD = 0.45
MAX_PEOPLE = 10
LOG_PATH = "/classroom_log.csv"

# 行为判定阈值，以躯干长归一化，与 lxt/config.py 保持同源
RAISE_WRIST_ABOVE = 0.15
DOWN_HEAD_BELOW = 0.45
STAND_BOX_RATIO = 0.55
STAND_LEG_RATIO = 0.18
MIN_TORSO = 8.0

# COCO 17 关键点顺序
NOSE, L_EYE, R_EYE, L_EAR, R_EAR = 0, 1, 2, 3, 4
L_SHO, R_SHO, L_ELB, R_ELB, L_WRI, R_WRI = 5, 6, 7, 8, 9, 10
L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANK, R_ANK = 11, 12, 13, 14, 15, 16

SKELETON = ((0, 1), (0, 2), (1, 3), (2, 4), (5, 6),
            (5, 7), (7, 9), (6, 8), (8, 10), (5, 11),
            (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16))

# 行为配色 (R, G, B)
COLOR_RAISE = (255, 255, 0)     # 举手 - 黄
COLOR_DOWN = (255, 0, 0)        # 低头/趴桌 - 红
COLOR_STAND = (0, 255, 255)     # 站立 - 青
COLOR_SIT = (0, 255, 0)         # 坐姿端正 - 绿

# 专注度权重：坐姿/举手计为专注，站立略降，趴桌归零
FOCUS_WEIGHT = {"RAISE": 1.0, "SIT": 1.0, "STAND": 0.85, "DOWN": 0.0, "UNKNOWN": 0.5}

# 事件引擎时间参数（毫秒）
RAISE_CONFIRM_MS = 400      # 举手持续 0.4s 确认一次发言事件
RAISE_RELEASE_MS = 1000     # 放下 1s 后才允许下一次计数
DOWN_ALERT_MS = 2000        # 趴桌持续 2s 触发告警
DOWN_RELEASE_MS = 1500      # 恢复正常 1.5s 解除告警


class YoloV8Pose:
    """姿态解码器：DFL 框回归 + 关键点头解码。
    常量与模型导出配置严格对应，改动会导致坐标错乱，请勿随意调整。"""

    SHAPES = ((1, 144, 64), (1, 576, 64), (1, 36, 1), (1, 756, 51),
              (1, 576, 1), (1, 36, 64), (1, 144, 1))
    SCALES = (0.0743677095, 0.0850540623, 0.1490852833, 0.0513033383,
              0.0935444459, 0.0694025531, 0.1864520013)
    ZEROS = (-72, -64, 107, 5, 110, -64, 116)
    HEADS = ((8, 24, 1, 4, 0), (16, 12, 0, 6, 576), (32, 6, 5, 2, 720))

    def __init__(self, threshold=0.4, nms_threshold=0.45,
                 max_candidates=60, max_people=MAX_PEOPLE):
        self.threshold = threshold
        self.nms_threshold = nms_threshold
        self.max_candidates = max_candidates
        self.max_people = max_people

    def validate(self, model):
        if (len(model.input_shape) != 1
                or tuple(model.input_shape[0]) != (1, 192, 192, 3)
                or model.input_dtype[0] != "b"
                or abs(model.input_scale[0] - 1.0 / 255.0) > 1e-8
                or model.input_zero_point[0] != -128):
            raise ValueError("请使用配套的 LingXi-Pose-Tiny 192×192 INT8 模型文件")

    @staticmethod
    def sigmoid(value):
        if value >= 0:
            return 1.0 / (1.0 + math.exp(-value))
        value = math.exp(value)
        return value / (1.0 + value)

    @staticmethod
    def dfl(tensor, row, offset, scale):
        peak = max(int(tensor[0, row, offset + k]) for k in range(16))
        total = 0.0
        weighted = 0.0
        for k in range(16):
            value = math.exp((int(tensor[0, row, offset + k]) - peak) * scale)
            total += value
            weighted += k * value
        return weighted / total

    @staticmethod
    def iou(a, b):
        intersection = (max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
                        * max(0.0, min(a[3], b[3]) - max(a[1], b[1])))
        union = ((a[2] - a[0]) * (a[3] - a[1])
                 + (b[2] - b[0]) * (b[3] - b[1]) - intersection)
        return intersection / union if union > 0 else 0.0

    def __call__(self, model, inputs, outputs):
        candidates = []
        logit_threshold = math.log(self.threshold / (1.0 - self.threshold))
        for stride, grid, box_output, score_output, base in self.HEADS:
            scale = model.output_scale[score_output]
            zero = model.output_zero_point[score_output]
            for row in range(grid * grid):
                logit = (int(outputs[score_output][0, row, 0]) - zero) * scale
                if logit >= logit_threshold:
                    candidate = (self.sigmoid(logit), row, stride, grid,
                                 box_output, base + row)
                    if len(candidates) < self.max_candidates:
                        candidates.append(candidate)
                    elif candidate > candidates[-1]:
                        candidates[-1] = candidate
                    else:
                        continue
                    candidates.sort(reverse=True)

        kept = []
        for score, row, stride, grid, box_output, anchor in candidates:
            x = row % grid + 0.5
            y = row // grid + 0.5
            distances = [self.dfl(outputs[box_output], row, k * 16,
                                  model.output_scale[box_output]) for k in range(4)]
            box = ((x - distances[0]) * stride, (y - distances[1]) * stride,
                   (x + distances[2]) * stride, (y + distances[3]) * stride)
            if any(self.iou(box, item[0]) > self.nms_threshold for item in kept):
                continue
            kept.append((box, score, anchor, x, y, stride))
            if len(kept) >= self.max_people:
                break

        rx, ry, rw, rh = inputs[0].roi
        sx, sy = rw / 192.0, rh / 192.0
        scale = model.output_scale[3]
        zero = model.output_zero_point[3]
        results = []
        for box, score, anchor, ax, ay, stride in kept:
            x1, y1 = max(0.0, box[0]), max(0.0, box[1])
            x2, y2 = min(192.0, box[2]), min(192.0, box[3])
            if x2 <= x1 or y2 <= y1:
                continue
            left, top = rx + int(x1 * sx), ry + int(y1 * sy)
            right, bottom = rx + int(x2 * sx), ry + int(y2 * sy)
            if right <= left or bottom <= top:
                continue
            points = []
            for k in range(17):
                px = (int(outputs[3][0, anchor, k * 3]) - zero) * scale
                py = (int(outputs[3][0, anchor, k * 3 + 1]) - zero) * scale
                confidence = self.sigmoid(
                    (int(outputs[3][0, anchor, k * 3 + 2]) - zero) * scale)
                px = (px * 2.0 + ax - 0.5) * stride
                py = (py * 2.0 + ay - 0.5) * stride
                if not (0.0 <= px < 192.0 and 0.0 <= py < 192.0):
                    confidence = 0.0
                points.append((rx + int(px * sx), ry + int(py * sy), confidence))
            results.append(((left, top, right - left, bottom - top), score, points))
        return results


def good(point):
    return point[2] >= KEYPOINT_THRESHOLD


def classify(points, rect, frame_h):
    """课堂行为规则引擎：用关键点几何关系判定，无需训练。"""
    if not (good(points[L_SHO]) and good(points[R_SHO])):
        return "UNKNOWN", COLOR_SIT

    shoulder_y = (points[L_SHO][1] + points[R_SHO][1]) / 2.0
    torso = 1.0
    if good(points[L_HIP]) and good(points[R_HIP]):
        hip_y = (points[L_HIP][1] + points[R_HIP][1]) / 2.0
        torso = max(MIN_TORSO, hip_y - shoulder_y)
    else:
        hip_y = shoulder_y + torso

    # 1) 举手发言：手腕明显高于肩部
    for wrist in (L_WRI, R_WRI):
        if good(points[wrist]) and \
           points[wrist][1] < shoulder_y - RAISE_WRIST_ABOVE * torso:
            return "RAISE", COLOR_RAISE

    # 2) 低头 / 趴桌：头部明显低于肩线
    head_y = None
    if good(points[NOSE]):
        head_y = points[NOSE][1]
    elif good(points[L_EYE]) and good(points[R_EYE]):
        head_y = (points[L_EYE][1] + points[R_EYE][1]) / 2.0
    if head_y is not None and head_y > shoulder_y + DOWN_HEAD_BELOW * torso:
        return "DOWN", COLOR_DOWN

    # 3) 站立：人体框占画面高度比例大，且髋-踝展开
    box_h = rect[3]
    leg_span = 0
    if (good(points[L_HIP]) or good(points[R_HIP])) and \
       (good(points[L_ANK]) or good(points[R_ANK])):
        leg_span = max(points[L_ANK][1] if good(points[L_ANK]) else 0,
                       points[R_ANK][1] if good(points[R_ANK]) else 0) - hip_y
    if box_h > STAND_BOX_RATIO * frame_h and leg_span > STAND_LEG_RATIO * frame_h:
        return "STAND", COLOR_STAND

    # 4) 默认：坐姿端正 / 认真听讲
    return "SIT", COLOR_SIT


class EventEngine:
    """行为事件引擎：时间防抖 + 边沿触发，输出结构化事件。"""

    def __init__(self):
        self.raise_since = None      # 举手开始的时刻
        self.raise_active = False    # 一次发言事件进行中
        self.raise_release = None    # 举手消失时刻（冷却用）
        self.down_since = None       # 趴桌开始时刻
        self.down_active = False     # 告警进行中
        self.down_release = None
        self.events_raise = 0        # 发言事件累计
        self.events_down = 0         # 趴桌告警累计

    def update(self, now, raise_cnt, down_cnt):
        fired = []

        # ---- 举手事件：持续 RAISE_CONFIRM_MS 确认；放下 RAISE_RELEASE_MS 后复位
        if raise_cnt > 0:
            self.raise_release = None
            if self.raise_since is None:
                self.raise_since = now
            elif (not self.raise_active
                  and time.ticks_diff(now, self.raise_since) >= RAISE_CONFIRM_MS):
                self.raise_active = True
                self.events_raise += 1
                fired.append(("RAISE", raise_cnt))
        else:
            self.raise_since = None
            if self.raise_active:
                if self.raise_release is None:
                    self.raise_release = now
                elif time.ticks_diff(now, self.raise_release) >= RAISE_RELEASE_MS:
                    self.raise_active = False
                    self.raise_release = None

        # ---- 趴桌告警：持续 DOWN_ALERT_MS 触发；恢复 DOWN_RELEASE_MS 解除
        if down_cnt > 0:
            self.down_release = None
            if self.down_since is None:
                self.down_since = now
            elif (not self.down_active
                  and time.ticks_diff(now, self.down_since) >= DOWN_ALERT_MS):
                self.down_active = True
                self.events_down += 1
                fired.append(("DOWN_ALERT", down_cnt))
        else:
            self.down_since = None
            if self.down_active:
                if self.down_release is None:
                    self.down_release = now
                elif time.ticks_diff(now, self.down_release) >= DOWN_RELEASE_MS:
                    self.down_active = False
                    self.down_release = None

        return fired


class CsvLogger:
    """教学数据沉淀：课堂行为事件写入 SD 卡 CSV，供课后统计分析。"""

    def __init__(self, path):
        self.ok = False
        self.file = None
        try:
            self.file = open(path, "a")
            self.file.write("# classroom_behavior_log,version=2\n")
            self.file.write("uptime_ms,event,people,count,focus\n")
            self.file.flush()
            self.ok = True
        except Exception as e:
            print("CSV log disabled:", e)

    def log(self, now, event, people, count, focus):
        if not self.ok:
            return
        try:
            self.file.write("%d,%s,%d,%d,%d\n" % (now, event, people, count, focus))
            self.file.flush()
        except Exception:
            self.ok = False

    def close(self):
        try:
            if self.file:
                self.file.close()
        except Exception:
            pass


def main():
    decoder = YoloV8Pose(PERSON_THRESHOLD, NMS_THRESHOLD)
    model = ml.Model(MODEL_PATH, postprocess=decoder)
    decoder.validate(model)
    print(model)

    camera = csi.CSI()
    camera.reset()
    camera.pixformat(csi.RGB565)
    camera.framesize(csi.QVGA)
    camera.snapshot(time=2000)

    # 三色 LED 课堂状态灯：LED1 心跳 / LED2 趴桌告警 / LED3 举手提示
    led_heart = LED(1)
    led_alert = LED(2)
    led_raise = LED(3)
    led_alert.off()
    led_raise.off()

    engine = EventEngine()
    logger = CsvLogger(LOG_PATH)

    clock = time.clock()
    last_print = time.ticks_ms()
    last_report = time.ticks_ms()
    last_blink = time.ticks_ms()
    focus = 100.0            # 专注度 EMA
    peak = 0
    frame_h = 240
    blink_on = False

    print("=== Classroom Behavior Monitor v2 Started ===")

    while True:
        clock.tick()
        img = camera.snapshot()
        frame_h = img.height()
        people = model.predict([img])
        now = time.ticks_ms()

        counter = {"RAISE": 0, "DOWN": 0, "STAND": 0, "SIT": 0}
        focus_sum = 0.0

        for rect, score, points in people:
            behavior, color = classify(points, rect, frame_h)
            if behavior in counter:
                counter[behavior] += 1
            focus_sum += FOCUS_WEIGHT.get(behavior, 0.5)

            # 画人体框与行为标签
            img.draw_rectangle(rect, color=color, thickness=2)
            img.draw_string((rect[0], max(18, rect[1] - 2)),
                            "%s %.2f" % (behavior, score), color=color)

            # 画骨架与关键点
            for a, b in SKELETON:
                if good(points[a]) and good(points[b]):
                    img.draw_line((points[a][0], points[a][1],
                                   points[b][0], points[b][1]),
                                  color=(0, 255, 255), thickness=2)
            for x, y, confidence in points:
                if confidence >= KEYPOINT_THRESHOLD:
                    img.draw_circle((x, y, 2), color=(255, 255, 0), fill=True)

        count = len(people)
        if count > peak:
            peak = count

        # ---- 专注度评分：即时值 -> EMA 平滑
        instant = 100.0 * focus_sum / count if count else 100.0
        focus += 0.15 * (instant - focus)

        # ---- 事件引擎
        fired = engine.update(now, counter["RAISE"], counter["DOWN"])
        for name, n in fired:
            logger.log(now, name, n, count, int(focus))
            print("CBEVENT:%s people=%d count=%d focus=%d" % (name, n, count, focus))

        # ---- LED 状态灯
        if time.ticks_diff(now, last_blink) >= 500:     # 心跳
            blink_on = not blink_on
            last_blink = now
            if blink_on:
                led_heart.on()
            else:
                led_heart.off()
        if engine.down_active:
            led_alert.on()                              # 红色告警
        else:
            led_alert.off()
        if counter["RAISE"] > 0:
            led_raise.on()                              # 举手提示
        else:
            led_raise.off()

        # ---- 顶部状态栏 + 专注度
        img.draw_rectangle((0, 0, img.width(), 16), color=(0, 0, 0), fill=True)
        img.draw_string((2, 2),
                        "P:%d R:%d D:%d S:%d T:%d" % (
                            count, counter["RAISE"], counter["DOWN"],
                            counter["STAND"], counter["SIT"]),
                        color=(255, 255, 255))
        focus_color = COLOR_SIT if focus >= 80 else (COLOR_RAISE if focus >= 60 else COLOR_DOWN)
        img.draw_string((img.width() - 88, 2), "F:%d%%" % focus, color=focus_color)

        # ---- 底部信息栏
        img.draw_rectangle((0, img.height() - 14, img.width(), img.height()),
                           color=(0, 0, 0), fill=True)
        img.draw_string((2, img.height() - 12),
                        "FPS:%.1f Events R:%d D:%d" % (
                            clock.fps(), engine.events_raise, engine.events_down),
                        color=(200, 200, 200))

        # ---- 每 500ms 输出 JSON 数据流（Web Serial 大屏消费）
        if time.ticks_diff(now, last_report) >= 500:
            print("CBJSON:{\"t\":%d,\"count\":%d,\"fps\":%.1f,"
                  "\"raise\":%d,\"down\":%d,\"stand\":%d,\"sit\":%d,"
                  "\"focus\":%d,\"total_raise\":%d,\"total_down\":%d,"
                  "\"peak\":%d,\"alert\":%d}" % (
                      now, count, clock.fps(),
                      counter["RAISE"], counter["DOWN"],
                      counter["STAND"], counter["SIT"],
                      int(focus), engine.events_raise, engine.events_down,
                      peak, 1 if engine.down_active else 0))
            last_report = now

        if time.ticks_diff(now, last_print) >= 1000:
            print("People:%d Raise:%d Down:%d Stand:%d Sit:%d Focus:%d FPS:%.1f" % (
                count, counter["RAISE"], counter["DOWN"],
                counter["STAND"], counter["SIT"], focus, clock.fps()))
            last_print = now


if __name__ == "__main__":
    main()
