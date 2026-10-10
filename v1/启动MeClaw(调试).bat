@echo off
chcp 65001 >nul
cd /d "%~dp0"
set MECLAW_DEBUG=1
echo MeClaw 调试模式：F12 或 右键 -^> 检查，可使用「选择元素」定位 UI
echo.
python main.py --debug
pause
