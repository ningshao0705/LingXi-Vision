"""CSV 教学日志。

课堂行为事件按时间戳追加写入 SD 卡，供课后统计分析使用。这是系统
区别于"纯实时 demo"的地方：数据沉淀下来才谈得上教学改进。

可靠性设计：
    - 每条事件立即 flush，掉电最多丢一条，不会丢一批；
    - 写入异常后自动置为不可用并打印一次提示，之后静默跳过，
      避免因 SD 卡问题反复抛异常拖慢推理流水线；
    - 文件头写入版本号，便于解析端兼容演进。
"""

from . import config

HEADER_VERSION = "2"
HEADER_LINES = (
    "# classroom_behavior_log,version=%s" % HEADER_VERSION,
    "uptime_ms,event,people,count,focus",
)


class CsvLogger(object):
    """追加式 CSV 事件日志。"""

    def __init__(self, path=None, open_fn=open):
        self.path = path or config.LOG_PATH
        self.ok = False
        self.file = None
        self.dropped = 0
        try:
            self.file = open_fn(self.path, "a")
            for line in HEADER_LINES:
                self.file.write(line + "\n")
            self.file.flush()
            self.ok = True
        except Exception as exc:
            print("[logger] disabled:", exc)

    def log(self, now, event, people, count, focus):
        """写入一条事件。失败时累计 dropped 计数，便于事后排查。"""
        if not self.ok:
            self.dropped += 1
            return False
        try:
            self.file.write("%d,%s,%d,%d,%d\n"
                            % (now, event, people, count, int(focus)))
            self.file.flush()
            return True
        except Exception as exc:
            self.ok = False
            self.dropped += 1
            print("[logger] write failed, disabled:", exc)
            return False

    def close(self):
        try:
            if self.file:
                self.file.close()
        except Exception:
            pass
        self.ok = False

    def stats(self):
        return {"enabled": self.ok, "dropped": self.dropped, "path": self.path}


class NullLogger(object):
    """空实现，SD 卡不可用时使用，保证调用方无需判空。"""

    def __init__(self, *args, **kwargs):
        self.ok = False
        self.dropped = 0

    def log(self, *args, **kwargs):
        self.dropped += 1
        return False

    def close(self):
        pass

    def stats(self):
        return {"enabled": False, "dropped": self.dropped, "path": None}


def create(sd_available, open_fn=open):
    """按 SD 卡可用性选择实现——这是降级策略的落地点。"""
    if not sd_available:
        print("[logger] fallback to NullLogger")
        return NullLogger()
    return CsvLogger(open_fn=open_fn)
