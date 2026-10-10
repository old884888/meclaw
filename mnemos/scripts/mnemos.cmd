@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem MNEMOS local server helper — start / stop / restart / status / first-run setup
rem Run from repo root (this folder); scripts/mnemos.cmd

set "PORT=8766"
set "HOST=127.0.0.1"
set "URL=http://127.0.0.1:%PORT%"

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "MNEMOS=%%~fI"
set "REPO_ROOT=%MNEMOS%"

rem Keep embedding model cache inside this project folder (migrates with it)
set "FASTEMBED_CACHE_DIR=%MNEMOS%\.fastembed_cache"
set "FASTEMBED_CACHE_PATH=%MNEMOS%\.fastembed_cache"

rem Force UTF-8 for every Python child. Without this, Python 3.12 on a CP936
rem console can fault while printing the Chinese status lines (0xC0000005).
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

call :find_python
if errorlevel 1 goto python_missing

if "%~1"=="" goto menu
if /i "%~1"=="menu" goto menu
if /i "%~1"=="start" goto do_start
if /i "%~1"=="stop" goto do_stop_quiet
if /i "%~1"=="restart" goto do_restart
if /i "%~1"=="status" goto do_status
if /i "%~1"=="open" goto do_open
if /i "%~1"=="setup" goto do_setup
echo 未知命令: %~1
exit /b 1

:find_python
set "PY="
for %%V in (313 312 311 310) do (
  if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
    set "PY=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
  )
)
if not defined PY (
  where py >nul 2>&1 && (
    for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%P"
  )
)
if not defined PY (
  for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | findstr /i "WindowsApps" >nul && (
      rem skip Microsoft Store stub
    ) || (
      if not defined PY set "PY=%%P"
    )
  )
)
if not defined PY exit /b 1
exit /b 0

:python_missing
chcp 65001 >nul 2>&1
cls
echo.
echo ========================================
echo   未检测到可用的 Python
echo ========================================
echo.
echo   MNEMOS 需要 Python 3.10 或更高版本。
echo.
echo   请按以下步骤操作:
echo     1. 打开 https://www.python.org/downloads/
echo     2. 下载并安装 Python 3.12 (推荐)
echo     3. 安装时勾选 「Add python.exe to PATH」
echo     4. 安装完成后重新双击 启动MNEMOS.bat
echo.
echo   若已安装但仍提示此错误, 可在 CMD 中运行:
echo     py -3 --version
echo.
pause
exit /b 1

:menu
chcp 65001 >nul 2>&1
:menu_loop
cls
echo ========================================
echo   MNEMOS 本地服务  %URL%
echo ========================================
echo   说明: 选 [1] 后服务在本窗口运行
echo         关闭本窗口或 Ctrl+C 会停止服务
echo         若关窗后仍能访问, 请先选 [2] 停止
echo         第一次使用请先选 [6] 安装依赖
echo ----------------------------------------
call :do_status_inline
echo ----------------------------------------
call :print_env_status
echo ----------------------------------------
echo   [1] 启动服务
echo   [2] 停止服务
echo   [3] 重启服务
echo   [4] 查看状态
echo   [5] 打开浏览器
echo   [6] 首次安装 / 环境检测
echo   [0] 退出
echo ========================================
set "CHOICE="
set /p "CHOICE=请选择: "
if "%CHOICE%"=="1" goto menu_start
if "%CHOICE%"=="2" goto menu_stop
if "%CHOICE%"=="3" goto menu_restart
if "%CHOICE%"=="4" goto menu_status
if "%CHOICE%"=="5" goto menu_open
if "%CHOICE%"=="6" goto menu_setup
if "%CHOICE%"=="0" exit /b 0
goto menu_loop

:print_env_status
if not defined PY (
  echo   环境: 未找到 Python — 请先安装 Python 3.12
  exit /b 0
)
for /f "delims=" %%L in ('"%PY%" "%MNEMOS%\scripts\setup_check.py" --brief 2^>nul') do echo %%L
exit /b 0

:menu_setup
call :do_setup
pause
goto menu_loop

:do_setup
echo.
"%PY%" "%MNEMOS%\scripts\setup_check.py" --wizard
exit /b !ERRORLEVEL!

:menu_start
call :ensure_core_or_offer_setup
if errorlevel 1 goto menu_loop
call :maybe_warn_embedding
call :ensure_port_free
if errorlevel 1 goto menu_loop
goto run_server

:ensure_core_or_offer_setup
"%PY%" "%MNEMOS%\scripts\setup_check.py" --check-core >nul 2>&1
if not errorlevel 2 exit /b 0
echo.
echo   检测到尚未安装运行依赖 (fastapi / uvicorn 等)。
set "SETUP_ANS="
set /p "SETUP_ANS=是否现在运行首次安装向导? [Y/n]: "
if /i "!SETUP_ANS!"=="n" (
  echo   已取消启动。请选 [6] 完成安装后再启动。
  pause
  exit /b 1
)
call :do_setup
echo.
set "GO_ANS="
set /p "GO_ANS=安装完成。是否立即启动服务? [Y/n]: "
if /i "!GO_ANS!"=="n" exit /b 1
exit /b 0

:maybe_warn_embedding
"%PY%" "%MNEMOS%\scripts\setup_check.py" --needs-embedding-setup >nul 2>&1
if not errorlevel 2 exit /b 0
echo.
echo   提示: 本地语义模型尚未就绪, 记忆检索会暂时降级。
echo         可在菜单选 [6] 下载约 470MB 的语义模型 (需联网)。
echo.
exit /b 0

:menu_stop
call :kill_port
echo.
echo 已尝试停止 %URL% 上的服务。
pause
goto menu_loop

:menu_restart
call :ensure_core_or_offer_setup
if errorlevel 1 goto menu_loop
call :maybe_warn_embedding
call :kill_port
echo.
echo 正在重启...
timeout /t 1 /nobreak >nul
goto run_server

:menu_status
echo.
call :do_status
echo.
"%PY%" "%MNEMOS%\scripts\setup_check.py" --status
pause
goto menu_loop

:menu_open
call :do_open
pause
goto menu_loop

:do_stop_quiet
call :kill_port
if "%KILLED%"=="1" (
  echo MNEMOS 已停止 — 端口 %PORT% 已释放。
) else (
  echo MNEMOS 未在运行 — 端口 %PORT% 空闲。
)
exit /b 0

:do_restart
call :ensure_core_or_offer_setup
if errorlevel 1 exit /b 1
call :maybe_warn_embedding
call :kill_port
timeout /t 1 /nobreak >nul
goto run_server

:do_start
call :ensure_core_or_offer_setup
if errorlevel 1 exit /b 1
call :maybe_warn_embedding
call :ensure_port_free
if errorlevel 1 exit /b 1
goto run_server

:run_server
cd /d "%REPO_ROOT%"
if not exist "%REPO_ROOT%\backend\main.py" (
  echo 错误: 找不到 backend\main.py
  echo 当前目录: %REPO_ROOT%
  pause
  exit /b 1
)
echo.
echo 正在启动 MNEMOS ...
echo 地址: %URL%
echo 数据: %MNEMOS%\data
echo 语义模型缓存: %MNEMOS%\.fastembed_cache
echo 提示: 保持本窗口打开; 关闭窗口即停止服务
echo.
echo 首次使用? 浏览器打开后: 设置 -^> 供应商 -^> 填 API Key -^> 绑定 Bot
echo.
start "" "%URL%"
"%PY%" -m uvicorn backend.main:app --host %HOST% --port %PORT%
set "EXIT_CODE=!ERRORLEVEL!"
echo.
if not "!EXIT_CODE!"=="0" (
  echo 服务异常退出, 代码: !EXIT_CODE!
  echo.
  echo 常见原因:
  echo   - 未安装依赖: 菜单选 [6] 首次安装向导
  echo   - 端口被占用: 请先选 [2] 停止服务
  echo   - Python 模块找不到: 确认从仓库根目录启动
) else (
  echo 服务已正常退出。
)
pause
exit /b %EXIT_CODE%

:do_status
call :do_status_inline
if "%RUNNING%"=="1" exit /b 0
exit /b 1

:do_status_inline
set "RUNNING=0"
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr /C:":%PORT% " ^| findstr LISTENING') do (
  echo 状态: 运行中 — %URL%  PID=%%p
  set "RUNNING=1"
  goto :status_done
)
echo 状态: 未运行 — 端口 %PORT% 空闲
:status_done
exit /b 0

:do_open
start "" "%URL%"
echo 已在浏览器打开 %URL%
exit /b 0

:ensure_port_free
set "RUNNING=0"
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr /C:":%PORT% " ^| findstr LISTENING') do set "RUNNING=1"
if not "%RUNNING%"=="1" exit /b 0
echo.
echo 检测到端口 %PORT% 已被占用 (可能仍有旧 MNEMOS 在跑)。
set "ANS="
set /p "ANS=是否先停止旧进程再启动? [Y/n]: "
if /i "%ANS%"=="n" (
  echo 已取消启动。请先选 [2] 停止服务, 或关闭占用端口的进程。
  pause
  exit /b 1
)
call :kill_port
timeout /t 1 /nobreak >nul
exit /b 0

:kill_port
set "KILLED=0"
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr /C:":%PORT% " ^| findstr LISTENING') do (
  echo 正在结束进程树 PID %%p ...
  taskkill /PID %%p /T /F >nul 2>&1
  set "KILLED=1"
)
exit /b 0
