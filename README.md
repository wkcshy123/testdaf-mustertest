# TestDaF 模拟考试系统

本项目是本地优先的 TestDaF 模拟考试 Web 系统，当前重点是老师端出题系统。系统已经覆盖听力、阅读、写作、口语四大模块，并把生成结果保存到本地 `question_bank/`。

如果需要让人或 LLM 快速理解代码结构，请先阅读：[架构概览](docs/architecture-overview.md)。

## 一键启动

项目根目录提供了双击启动脚本：

| 系统 | 双击文件 | 说明 |
| --- | --- | --- |
| macOS | `start_mac.command` | 双击后会同步依赖并启动服务 |
| Windows | `start_windows.bat` | 双击后会同步依赖并启动服务 |

启动后访问：

```text
http://127.0.0.1:8000/
```

如需停止服务，在启动窗口中按 `Control+C` 或 `Ctrl+C`。

macOS 如果首次双击提示没有执行权限，请在项目目录执行一次：

```bash
chmod +x start_mac.command
```

两个脚本都依赖本机已安装 `uv`。如果提示未检测到 `uv`，请先参考 uv 官方文档安装。

## 命令行启动

```bash
uv sync
uv run python main.py
```

然后访问：

```text
http://127.0.0.1:8000/
```

## API Key

可以在页面表单中填写阿里云百炼 API Key，也可以设置环境变量：

```bash
export DASHSCOPE_API_KEY=YOUR_API_KEY
```

非 TTS 生成模型配置在 `testdaf_platform/config.py`：

```python
QWEN_TEXT_MODEL = "qwen3.7-plus"
QWEN_TTS_MODEL = "qwen3-tts-flash"
```

## 页面路径

| 页面 | 路径 |
| --- | --- |
| 系统总览 | `/` |
| 老师出题索引 | `/teacher` |
| 学生入口 | `/student` |
| 健康检查 | `/health` |

## 听力出题路径

| 题型 | 路径 | 主要产物 |
| --- | --- | --- |
| Hörverstehen Aufgabe 1 | `/teacher/listening/aufgabe-1` | 双人校园对话、8 道短答题、分段 TTS、完整音频 |
| Hörverstehen Aufgabe 2 | `/teacher/listening/aufgabe-2` | 主持人与两位嘉宾访谈、10 道 Richtig/Falsch、完整音频 |
| Hörverstehen Aufgabe 3 | `/teacher/listening/aufgabe-3` | 专家访谈、7 道短答题、完整音频 |

听力题会保存 `transcript.txt`、`segments.json`、`questions.json` 或 `statements.json`、`audio.wav`、`audio_segments/`、`preview.md`。

## 阅读出题路径

| 题型 | 路径 | 主要产物 |
| --- | --- | --- |
| Leseverstehen Aufgabe 1 | `/teacher/reading/aufgabe-1` | A-H 短文本、10 个人物需求、匹配答案 |
| Leseverstehen Aufgabe 2 | `/teacher/reading/aufgabe-2` | 中长阅读文本、10 道 A/B/C 单选题 |
| Leseverstehen Aufgabe 3 | `/teacher/reading/aufgabe-3` | 长阅读文本、10 道 Ja/Nein/Text sagt dazu nichts |

阅读题支持 UTF-8 长度控制，失败后会调用 LLM 对文本进行扩写或压缩修复。

## 写作出题路径

| 题型 | 路径 | 主要产物 |
| --- | --- | --- |
| Schriftlicher Ausdruck | `/teacher/writing/aufgabe-1` | 写作题干、核心讨论问题、任务要求、1-2 张 SVG 图表 |

写作题支持文字参考素材、网页参考链接和多张本地参考图片。上传图片用于多模态生成和追溯，预览中只展示生成图表。

## 口语出题路径

| 题型 | 路径 | 是否图表题 | 主要产物 |
| --- | --- | --- | --- |
| Mündlicher Ausdruck Aufgabe 1 | `/teacher/speaking/aufgabe-1` | 否 | 电话咨询/信息询问、引子语音 |
| Mündlicher Ausdruck Aufgabe 2 | `/teacher/speaking/aufgabe-2` | 否 | 本国情况说明、引子语音 |
| Mündlicher Ausdruck Aufgabe 3 | `/teacher/speaking/aufgabe-3` | 是 | 图表描述、SVG 图表、引子语音 |
| Mündlicher Ausdruck Aufgabe 4 | `/teacher/speaking/aufgabe-4` | 否 | 议题立场表达、引子语音 |
| Mündlicher Ausdruck Aufgabe 5 | `/teacher/speaking/aufgabe-5` | 否 | 学习/人生决策建议、引子语音 |
| Mündlicher Ausdruck Aufgabe 6 | `/teacher/speaking/aufgabe-6` | 是 | 图表 + 原因/影响分析、SVG 图表、引子语音 |
| Mündlicher Ausdruck Aufgabe 7 | `/teacher/speaking/aufgabe-7` | 否 | 复杂生活化选择建议、引子语音 |

口语单题使用后台任务生成，页面会轮询 `/jobs/{job_id}` 展示当前进度。`Aufgabe 3` 和 `Aufgabe 6` 支持本地图片参考素材。

## 参考素材

- 所有题型支持文字参考素材。
- 所有题型支持多个 HTML 网页链接。
- 网页素材会提取标题和正文摘要，并保存到 `reference_sources.json`。
- 写作和口语图表题支持本地图片上传，图片会保存到题目包的 `reference_images/`。

## 本地题库

生成题目会保存在：

```text
question_bank/
  listening/
  reading/
  writing/
  speaking/
```

每个题目包至少包含：

```text
manifest.json
preview.md
reference_sources.json  # 如果使用网页参考素材
```

不同模块会额外保存文本、答案、音频、图表或上传图片等资源。

## 修改系统提示词

如果需要调整某题的生成逻辑、题型要求、长度要求或输出 JSON schema，优先修改对应服务文件。

| 模块 | 题型 | 提示词所在文件 |
| --- | --- | --- |
| 听力 | Aufgabe 1 | `testdaf_platform/services/listening_aufgabe_1.py` |
| 听力 | Aufgabe 2 | `testdaf_platform/services/listening_aufgabe_2.py` |
| 听力 | Aufgabe 3 | `testdaf_platform/services/listening_aufgabe_3.py` |
| 阅读 | Aufgabe 1/2/3 | `testdaf_platform/services/reading.py` |
| 写作 | Aufgabe 1 | `testdaf_platform/services/writing.py` |
| 口语 | Aufgabe 1-7 | `testdaf_platform/services/speaking.py` |

常见修改点：

- 系统角色和 TestDaF 背景说明：查找 `_system_prompt()` 或 `_prompt()`。
- 用户输入拼接和题型参数：查找 `_user_prompt()` 或 `_prompt()`。
- 输出字段校验：查找 `_validate()`。
- 长度控制或失败修复：阅读在 `reading.py`，听力在对应 `listening_aufgabe_*.py`。
- 图表生成规格：写作在 `writing.py`，口语在 `speaking.py`，SVG 渲染在 `ChartRenderer`。
- 题库保存和预览结构：`testdaf_platform/storage/question_bank.py`。
- 页面表单和字段：`testdaf_platform/templates/teacher_*.html`。
- 路由和表单处理：`testdaf_platform/web.py`。

## 项目结构

```text
testdaf_platform/
  config.py        # 模型、路径和全局配置
  web.py           # FastAPI 路由和页面入口
  services/        # LLM、TTS、多说话人音频、参考素材、后台任务
  storage/         # 本地题库读写
  templates/       # 服务端模板
  static/          # 页面样式
docs/              # 路线图与题型分析
question_bank/     # 本地生成题库，默认不纳入版本控制
```

## 技术栈

- FastAPI
- Jinja2
- DashScope / Qwen
- Qwen-TTS
- uv
