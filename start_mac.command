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
echo "出题系统（老师）: http://127.0.0.1:8000/"
echo "答题系统（学生）: http://127.0.0.1:8001/"
echo "账号系统（注册/登录）: http://127.0.0.1:8002/"
echo "如需停止服务，请在此窗口按 Control+C。"
echo

# 学生答题系统（后台）
uv run python student_main.py >/tmp/testdaf_student.log 2>&1 &
# 学生账号系统（后台）
uv run python student_account_platform/account_main.py >/tmp/testdaf_account.log 2>&1 &

# 出题系统（前台）
uv run python main.py

# 前台退出后，回收后台进程
kill %+ 2>/dev/null || true
kill %- 2>/dev/null || true

echo
read -n 1 -s -r -p "服务已停止，按任意键关闭窗口..."
echo
