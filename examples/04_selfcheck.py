"""示例 4：上电自检。

依次检查模型、摄像头、SD 卡、LED，打印结果后退出。现场部署或换卡后
先跑一遍，可以把"看起来在跑、实际没输出"这类沉默失败提前暴露出来。

退出码语义靠打印结果判断：critical_ok 为 False 时不进入主循环。
"""

import machine

import csi
import ml

from lxt.selfcheck import SelfCheck
from lxt.hal import Storage


def main():
    storage = Storage()
    check = SelfCheck(ml_module=ml, csi_module=csi,
                      machine_module=machine, storage=storage)
    results = check.run(verbose=True)

    if check.critical_ok:
        print("[ok] 关键项通过，可以进入主循环")
    else:
        print("[halt] 模型或摄像头不可用，请检查 SD 卡与排线")

    for item in results:
        if item.status == "FAIL":
            print("[todo] 需要处理的故障项: %s (%s)"
                  % (item.name, item.detail))


if __name__ == "__main__":
    main()
