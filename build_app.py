# -*- coding: utf-8 -*-
"""
PyInstaller 打包配置文件
"""
import PyInstaller.__main__
import os
import sys

# 项目根目录
ROOT = os.path.dirname(os.path.abspath(__file__))

PyInstaller.__main__.run([
    os.path.join(ROOT, "app.py"),
    "--name=德语转语音",
    "--onefile",
    "--windowed",              # 无控制台窗口（macOS/Windows GUI模式）
    "--clean",
    "--noconfirm",
    f"--distpath={os.path.join(ROOT, 'dist')}",
    f"--workpath={os.path.join(ROOT, 'build')}",
    f"--specpath={ROOT}",
])
