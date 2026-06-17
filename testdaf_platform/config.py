"""项目级配置。"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = Path.home() / ".german_tts_config.json"
QUESTION_BANK_DIR = PROJECT_ROOT / "question_bank"

QWEN_TTS_MODEL = "qwen3-tts-flash"
# 支持 instructions 表现力控制的模型；仅在提供 instructions 时切换使用。
QWEN_TTS_INSTRUCT_MODEL = "qwen3-tts-instruct-flash"
QWEN_TEXT_MODEL = "qwen3.6-flash"

# 复杂结构题（多人访谈、匹配题、精确长度长文本）flash 偶发无法遵循
# JSON schema 或长度约束，改用更强模型保证稳定。
COMPLEX_STRUCTURE_MODEL = "qwen3.7-plus"
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"

VOICES = [
    ("Cherry", "芊悦 · 女声 · 阳光亲切"),
    ("Serena", "苏瑶 · 女声 · 温柔如水"),
    ("Ethan", "晨煦 · 男声 · 阳光温暖"),
    ("Maia", "四月 · 女声 · 知性温柔"),
    ("Moon", "月白 · 男声 · 率性帅气"),
    ("Kai", "凯 · 男声 · 治愈低音"),
    ("Neil", "阿闻 · 男声 · 新闻主播"),
    ("Mochi", "沙小弥 · 男声 · 聪慧少年"),
    ("Mia", "乖小妹 · 女声 · 温顺恬静"),
    ("Elias", "墨讲师 · 女声 · 娓娓道来"),
]

VOICE_GENDER: dict[str, str] = {
    "Cherry": "female",
    "Serena": "female",
    "Ethan": "male",
    "Maia": "female",
    "Moon": "male",
    "Kai": "male",
    "Neil": "male",
    "Mochi": "male",
    "Mia": "female",
    "Elias": "female",
}
