"""灵犀智眸 LingXi Vision —— 端侧课堂行为感知运行时

包结构按职责分层，其中标注 [纯 Python] 的模块不依赖任何 MicroPython
专有模块，可直接在 CPython 下导入并执行单元测试（见 tests/）。

    config      全局常量与可调参数          [纯 Python]
    compat      跨平台时间/数学兼容层       [纯 Python]
    keypoints   COCO 关键点定义与配色       [纯 Python]
    geometry    关键点几何量计算            [纯 Python]
    rules       行为判定规则引擎            [纯 Python]
    events      行为事件引擎（防抖/边沿）   [纯 Python]
    score       课堂专注度评分              [纯 Python]
    proto       串口数据协议编解码          [纯 Python]
    pose        姿态模型加载与解码         依赖 ml
    hal         板载外设硬件抽象           依赖 csi / machine
    render      OSD 叠加渲染               依赖 image
    logger      CSV 教学日志落盘           依赖 uos / builtins
    selfcheck   开机自检                   依赖 hal
    app         应用主循环                  聚合以上模块
"""

__version__ = "2.1.0"
__codename__ = "LingXi"

# 模块导入失败不应让整包不可用：PC 端跑测试时只依赖纯 Python 子集
_PURE_MODULES = ("config", "compat", "keypoints", "geometry",
                 "rules", "events", "score", "proto")

__all__ = list(_PURE_MODULES)
