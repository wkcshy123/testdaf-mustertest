# 德语转语音 · Deutsch TTS

基于阿里云 Qwen-TTS 的德语文字转语音桌面工具。

## 功能特性

- 🎙 支持输入任意长度德语文字，生成高质量 WAV 音频
- 🎭 提供 10 种音色（Cherry、Serena、Ethan、Maia、Moon 等）
- 💾 可自定义保存路径，默认保存到桌面
- 🔑 API Key 在本地使用，不会上传第三方服务器
- 🖥 支持 macOS 和 Windows 双平台

## 快速开始

### 方式一：直接运行（需要 Python 环境）

```bash
# 安装依赖
uv sync

# 运行
uv run python app.py
```

### 方式二：使用打包好的应用

- **macOS**：打开 `dist/德语转语音.app`（若提示安全警告，在系统偏好设置→安全性中允许）
- **Windows**：运行 `dist/德语转语音/德语转语音.exe`

## 使用步骤

1. 填写阿里云百炼 API Key（[获取地址](https://bailian.console.aliyun.com/)）
2. 选择音色（默认 Cherry，推荐用于德语）
3. 在文本框粘贴或输入德语文字
4. 设置保存路径（默认桌面）
5. 点击「开始转录语音」按钮

## 重新打包

```bash
# macOS（生成 .app）
uv run pyinstaller app.py --name="德语转语音" --onedir --windowed --clean --noconfirm

# Windows（生成 .exe，在 Windows 环境下运行）
uv run pyinstaller app.py --name="德语转语音" --onedir --windowed --clean --noconfirm
```

## 音色列表（均支持德语）

| voice 参数 | 音色名 | 性别 | 特点 |
|-----------|--------|------|------|
| Cherry | 芊悦 | 女 | 阳光积极、亲切自然 |
| Serena | 苏瑶 | 女 | 温柔温和 |
| Ethan | 晨煦 | 男 | 阳光、温暖、活力 |
| Maia | 四月 | 女 | 知性与温柔 |
| Moon | 月白 | 男 | 率性帅气 |
| Kai | 凯 | 男 | 治愈系 |
| Neil | 阿闻 | 男 | 新闻主播风格 |
| Mochi | 沙小弥 | 男 | 聪慧少年 |
| Mia | 乖小妹 | 女 | 温顺如水 |
| Elias | 墨讲师 | 女 | 知识分享者 |

## 技术栈

- **TTS API**: 阿里云百炼 Qwen-TTS (`qwen3-tts-flash`)
- **GUI**: Python tkinter
- **打包**: PyInstaller
- **包管理**: uv
