# Titan Board Mini 引脚与外设映射

本文件记录灵犀智眸实际占用的板载资源，供接线与迁移参考。信息来自
SDK BSP 文档与工程示例，若与所用硬件版本不符以官方手册为准。

## 主控

| 项目 | 规格 |
| --- | --- |
| 型号 | Renesas RA8P1（R7KA8P1KFLCAC） |
| 内核 | Cortex-M85 @1GHz（含 Helium 矢量扩展）+ Cortex-M33 @250MHz |
| NPU | Arm Ethos-U55 @500MHz，INT8 定点加速 |
| 片上存储 | 2 MB SRAM + 1 MB MRAM |
| 板载存储 | 32 MB SDRAM + 8 MB QSPI Flash + microSD 卡槽 |

## 本系统占用的外设

| 外设 | 用途 | 软件入口 |
| --- | --- | --- |
| MIPI CSI | OV5640 摄像头，QVGA(320x240) RGB565 | `csi.CSI()`，`lxt/hal.py` |
| RGB LCD | 本地画面与 OSD 渲染 | GLCDC + D/AVE 2D |
| LED1 / P109 | 系统心跳 | `lxt/hal.py StatusLED("heartbeat")` |
| LED2 / P108 | 趴桌告警（红） | `StatusLED("alert")` |
| LED3 / P110 | 举手提示 | `StatusLED("raise")` |
| SDIO | microSD，CSV 教学日志 | `lxt/logger.py` |
| USB CDC | 数据流输出 + OpenMV IDE 连接 | `print` / REPL |
| USB MSC | SD 卡在 PC 上暴露为可移动磁盘 | 固件自带 |

## 板上未使用但可用的资源

| 外设 | 备注 |
| --- | --- |
| LSM6DS3 六轴 IMU | I2C1，地址 0x6A。可用于设备防拆/姿态校正，本期未启用 |
| PWM（GPT6/7/8/12） | 可外接无源蜂鸣器做声音告警，需额外硬件 |
| 以太网 | 当前固件未编译 LwIP，启用需重新配置并编译 |
| UART1 | 被 RT-Thread 控制台占用，MicroPython 层不可再打开 |
| UART2 | 排针可能未焊接；如需使用需确认硬件并准备 USB-TTL |

## 音频相关说明

Titan Board Mini 板载**无音频编解码器与扬声器**，因此告警采用三色 LED
视觉指示而非声音播报。若需要声音，外接无源蜂鸣器到任一 GPT PWM 通道
即可，软件侧增加 3 行 PWM 驱动代码。

## 关键约束

1. **模型文件名不可改**：`/rom/yolov8n_pose_192_u55_256.tflite` 与导出
   配置绑定，重命名会导致加载失败。
2. **USB CDC 单客户端**：同一时刻只能被 OpenMV IDE 或一个串口工具占用。
3. **固件与视觉资源配对**：`rtthread.hex` 与 `openmv-vision.bin` 必须来自
   同一次构建，二者有 SHA256 绑定校验。
