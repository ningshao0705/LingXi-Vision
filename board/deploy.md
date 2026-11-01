# 部署指南

从空 SD 卡到系统跑起来，共五步。全流程约 10 分钟。

## 0. 准备

- Titan Board Mini 开发板 + MIPI CSI 摄像头（OV5640）
- microSD 卡（FAT32 格式化，建议 ≤32 GB）
- 板载 DAP-Link 调试口（USB-Debug）接 PC
- PyOCD（RT-Thread Studio 自带 0.36.0，含瑞萨 RA CMSIS Pack）

## 1. 烧录固件

固件与视觉资源必须同包、同一次构建：

```bat
pyocd flash --target=R7KA8P1KF --erase=auto --frequency=1000000 rtthread.hex
```

确认调试器在线：

```bat
pyocd list
```

## 2. 准备 SD 卡

SD 卡根目录应包含：

```
openmv-vision.bin                 视觉运行时（来自固件包，必选）
main.py                           应用入口
lxt/                              模块化包（若使用 main_modular.py）
yolov8n_pose_192_u55_256.tflite   模型
yolov8n_pose_192_u55_256.txt      模型说明
```

用发布脚本一键组装：

```bash
python tools/build_release.py --out dist/sdcard
```

然后把 `dist/sdcard/` 内全部内容复制到 SD 卡根目录。

## 3. 上电

- 复制完成后**安全弹出** SD 卡，断电状态下插入板子
- 按 RST 复位

## 4. 验证

按优先级依次确认：

1. **LED1 每秒闪烁** —— 主循环在跑
2. **画面出现骨架与行为标签** —— 模型与判定正常（OpenMV IDE 帧缓冲区）
3. **串口出现 `CBJSON:{...}`** —— 数据流正常
4. **举手 1 秒** —— LED3 亮，串口出现 `CBEVENT:event=RAISE`
5. **趴桌 2 秒** —— LED2 亮，画面中部弹出告警条

若第 2 步正常但第 3 步无输出，属于固件行为：上电自启时 USB CDC 不吐
数据，需在 OpenMV IDE 中打开 `main.py` 点运行，或用串口工具接管 REPL。

## 5. 采集与分析

```bash
python tools/serial_monitor.py --port COM7 --save capture/
python tools/log_analyzer.py classroom_log.csv --spark
```

## 常见问题

| 现象 | 排查 |
| --- | --- |
| 烧录器识别不到 | 换 USB 口；确认接的是 USB-Debug 而非 USB 数据口 |
| `pyocd` 报 unknown target | 确认已加载瑞萨 RA_DFP pack，目标名 `R7KA8P1KF` |
| 画面黑屏 | 摄像头排线未插紧；`openmv-vision.bin` 未放根目录 |
| 报 `csi`/`ml` 不存在 | 视觉资源与固件版本不匹配，重新拷贝同包文件 |
| 检测不到人 | 镜头对人不对着桌面；检查自动曝光是否已收敛（等 2 秒） |
| CSV 未生成 | SD 卡未识别或写保护；系统会自动降级为不落盘，不影响检测 |
