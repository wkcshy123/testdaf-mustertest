"""Qwen 文本生成服务。"""

import dashscope
from dashscope import Generation

from testdaf_platform.config import DASHSCOPE_BASE_URL, QWEN_TEXT_MODEL

dashscope.base_http_api_url = DASHSCOPE_BASE_URL


class TextGenerationService:
    """封装故事概要到德语短文的生成能力。"""

    def __init__(self, model: str = QWEN_TEXT_MODEL):
        self.model = model

    def generate_german_story(self, api_key: str, summary: str) -> str:
        resp = Generation.call(
            model=self.model,
            api_key=api_key,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个德语写作助手。用户会提供一个故事概要，"
                        "请将其扩展成一篇流畅自然的德语短文（约150-300词）。"
                        "只输出德语文本，不要添加任何解释、翻译或标记。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"请根据以下概要，写一篇德语短文：\n\n{summary}",
                },
            ],
            max_tokens=800,
        )

        if resp.status_code != 200:
            raise RuntimeError(f"API 错误 {resp.status_code}: {resp.message or resp.code}")

        text = resp.output.text
        if not text:
            raise RuntimeError("API 未返回文本")
        return text.strip()

