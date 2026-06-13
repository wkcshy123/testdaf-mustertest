@echo off
setlocal

cd /d "%~dp0"

echo TestDaF 模拟考试系统
echo 项目目录: %cd%
echo.

where uv >nul 2>nul
if errorlevel 1 (
  echo 未检测到 uv。请先安装 uv 后再双击启动。
  echo 安装说明: https://docs.astral.sh/uv/getting-started/installation/
  echo.
  pause
  exit /b 1
)

echo 正在同步依赖...
uv sync
if errorlevel 1 (
  echo.
  echo 依赖同步失败，请检查上方错误信息。
  pause
  exit /b 1
)

echo.
echo 正在启动服务...
echo 访问地址: http://127.0.0.1:8000/
echo 如需停止服务，请在此窗口按 Ctrl+C。
echo.

uv run python main.py

echo.
echo 服务已停止。
pause
