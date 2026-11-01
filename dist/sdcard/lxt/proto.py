"""串口数据协议。

板端向 PC / 网关输出两类文本行，均以换行结尾，便于任何串口工具肉眼
观察，也便于前端按行切分：

    CBJSON:{...}    状态流，周期性（默认 500ms）输出整机状态
    CBEVENT:...     事件流，边沿触发时输出一条语义事件

之所以不直接只发 JSON：JSON 行在串口里被 IDE 终端、日志混排时难以
快速定位，加一个 ASCII 前缀后可以用 grep / 文本过滤直接分流，
排障成本明显下降。前缀本身不参与 JSON 解析。

本模块 [纯 Python]，可在 PC 端直接测试。
"""

PREFIX_JSON = "CBJSON:"
PREFIX_EVENT = "CBEVENT:"

SCHEMA_VERSION = "1.2"
DEVICE_MODEL = "TitanBoardMini-RA8P1"


def build_status(now, count, fps, counter, focus, engine, peak,
                 infer_ms=None, npu_load=None):
    """构造状态流负载（dict）。

    字段命名与 Web 控制台的 data-kpi 绑定一一对应，前端无需再做映射。
    """
    payload = {
        "v": SCHEMA_VERSION,
        "dev": DEVICE_MODEL,
        "t": int(now),
        "count": int(count),
        "fps": round(float(fps), 1),
        "raise": counter.get("RAISE", 0),
        "down": counter.get("DOWN", 0),
        "stand": counter.get("STAND", 0),
        "sit": counter.get("SIT", 0),
        "focus": int(focus),
        "total_raise": engine.events_raise,
        "total_down": engine.events_down,
        "peak": int(peak),
        "alert": 1 if engine.alert else 0,
    }
    if infer_ms is not None:
        payload["infer_ms"] = round(float(infer_ms), 1)
    if npu_load is not None:
        payload["npu"] = int(npu_load)
    return payload


def build_event(now, name, people, count, focus):
    """构造事件流负载（dict）。"""
    return {
        "v": SCHEMA_VERSION,
        "t": int(now),
        "event": name,
        "people": int(people),
        "count": int(count),
        "focus": int(focus),
    }


def _escape(text):
    return str(text).replace('"', "'")


def dumps(payload):
    """手写 JSON 序列化。

    MicroPython 的 ujson 在部分构建下不可用，且我们自己拼装字符串可以
    完全控制字段顺序与小数位——字段顺序固定对前端 diff 与日志比对很
    有用，小数位固定则避免 21.600000000000001 这类噪声。
    """
    parts = []
    for key, value in payload.items():
        if isinstance(value, bool):
            parts.append('"%s":%s' % (key, "1" if value else "0"))
        elif isinstance(value, (int, float)):
            parts.append('"%s":%s' % (key, value))
        else:
            parts.append('"%s":"%s"' % (key, _escape(value)))
    return "{%s}" % ",".join(parts)


def encode_status(payload):
    return PREFIX_JSON + dumps(payload)


def encode_event(payload):
    """事件流刻意不用 JSON，而用 key=value 形式。

    事件需要被 shell / Excel / 串口助手直接阅读，k=v 形式在 CSV 转换
    和人工排障时更省事。
    """
    return PREFIX_EVENT + " ".join(
        "%s=%s" % (k, v) for k, v in payload.items())


def loads(text):
    """极简 JSON 解析（仅支持本协议的扁平结构）。

    仅用于 PC 端工具的反向解析，板端不调用——板端只出不进，避免
    在固件里引入解析开销与攻击面。
    """
    text = text.strip()
    if not text.startswith("{"):
        raise ValueError("not a json object: %r" % text[:32])
    body = text[1:-1]
    result = {}
    depth = 0
    token = ""
    in_string = False
    pairs = []
    for ch in body:
        if ch == '"':
            in_string = not in_string
            token += ch
        elif ch == "{" and not in_string:
            depth += 1
            token += ch
        elif ch == "}" and not in_string:
            depth -= 1
            token += ch
        elif ch == "," and not in_string and depth == 0:
            pairs.append(token)
            token = ""
        else:
            token += ch
    if token.strip():
        pairs.append(token)
    for pair in pairs:
        if ":" not in pair:
            continue
        key, value = pair.split(":", 1)
        key = key.strip().strip('"')
        value = value.strip()
        if value.startswith('"'):
            result[key] = value.strip('"')
        else:
            try:
                result[key] = float(value) if "." in value else int(value)
            except ValueError:
                result[key] = value
    return result


def decode_line(line):
    """从一行串口文本中提取结构化数据，非协议行返回 None。"""
    line = line.strip()
    if line.startswith(PREFIX_JSON):
        return loads(line[len(PREFIX_JSON):])
    if line.startswith(PREFIX_EVENT):
        item = {}
        for token in line[len(PREFIX_EVENT):].split():
            if "=" in token:
                k, v = token.split("=", 1)
                try:
                    item[k] = float(v) if "." in v else int(v)
                except ValueError:
                    item[k] = v
        return item
    return None
