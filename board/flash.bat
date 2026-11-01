@echo off
rem 灵犀智眸 —— 固件烧录脚本（DAP-Link / CMSIS-DAP）
rem
rem 用法：
rem   flash.bat                       使用同目录下的 rtthread.hex
rem   flash.bat D:\path\to\rtthread.hex
rem
rem 前置：PyOCD 已在 PATH 中（RT-Thread Studio 自带，通常位于
rem   <Studio>\repo\Extract\Debugger_Support_Packages\RealThread\PyOCD\<ver>）

setlocal

set HEX=%~1
if "%HEX%"=="" set HEX=%~dp0rtthread.hex

if not exist "%HEX%" (
    echo [error] 找不到固件文件: %HEX%
    echo 请把 rtthread.hex 放到本目录，或作为第一个参数传入路径。
    exit /b 1
)

echo [1/3] 检查调试器 ...
pyocd list
if errorlevel 1 (
    echo [error] 未检测到 CMSIS-DAP 调试器。
    echo 请确认板子 USB-Debug 口已接电脑，且驱动正常。
    exit /b 1
)

echo [2/3] 目标型号检查 ...
pyocd list --targets | findstr /i "R7KA8P1" >nul
if errorlevel 1 (
    echo [warn] 当前 PyOCD 未列出 R7KA8P1 目标，请确认已加载瑞萨 RA_DFP pack。
)

echo [3/3] 烧录 %HEX% ...
pyocd flash --target=R7KA8P1KF --erase=auto --frequency=1000000 "%HEX%"
if errorlevel 1 (
    echo [error] 烧录失败。
    exit /b 1
)

echo.
echo 烧录完成。请按板子上的 RST 复位。
endlocal
