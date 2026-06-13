#!/bin/bash

set -e

cd "$(dirname "$0")"

echo "TestDaF 模拟考试系统"
echo "项目目录: $(pwd)"
echo

if ! command -v uv >/dev/null 2>&1; then
  echo "未检测到 uv。请先安装 uv 后再双击启动。"
  echo "安装说明: https://docs.astral.sh/uv/getting-started/installation/"
  echo
  read -n 1 -s -r -p "按任意键退出..."
  echo
  exit 1
fi

echo "正在同步依赖..."
uv sync

echo
echo "正在启动服务..."
echo "访问地址: http://127.0.0.1:8000/"
echo "如需停止服务，请在此窗口按 Control+C。"
echo

uv run python main.py

echo
read -n 1 -s -r -p "服务已停止，按任意键关闭窗口..."
echo
