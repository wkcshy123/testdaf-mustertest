"""Unified Qwen text generation client."""

import time

import dashscope
import dashscope.common.constants as _ds_const
from dashscope import Generation, MultiModalConversation

from testdaf_platform.config import DASHSCOPE_BASE_URL, QWEN_TEXT_MODEL

dashscope.base_http_api_url = DASHSCOPE_BASE_URL

_ds_const.DEFAULT_REQUEST_TIMEOUT_SECONDS = 600

import dashscope.client.base_api as _ba
_ba.DEFAULT_REQUEST_TIMEOUT_SECONDS = 600


MULTIMODAL_TEXT_MODEL_PREFIXES = ("qwen3.7", "qwen3.6", "qwen3.5")
TEXT_GENERATION_REQUEST_RETRIES = 1


class TextGenerationClient:
    """Route text generation requests to the correct DashScope API."""

    def __init__(
        self,
        model: str = QWEN_TEXT_MODEL,
        base_url: str = DASHSCOPE_BASE_URL,
        fallback_models: tuple[str, ...] | None = None,
    ):
        self.model = model
        self.base_url = base_url
        self.fallback_models = tuple(fallback_models or ())

    def generate_text(
        self,
        *,
        api_key: str,
        messages: list[dict],
        max_tokens: int | None = None,
    ) -> str:
        model_errors: list[str] = []
        response: object | None = None
        text = ""
        for model in (self.model, *self.fallback_models):
            try:
                response, text = self._generate_with_retries(
                    model=model,
                    api_key=api_key,
                    messages=messages,
                    max_tokens=max_tokens,
                )
                break
            except RuntimeError as exc:
                model_errors.append(f"{model}: {exc}")
                if model == self.model and not self.fallback_models:
                    raise
        else:
            raise RuntimeError("文本模型请求失败：" + "；".join(model_errors))

        if response is None:
            raise RuntimeError("文本模型请求失败：未获得响应")
        if response.status_code != 200:
            raise RuntimeError(f"API 错误 {response.status_code}: {response.message or response.code}")
        if not text:
            raise RuntimeError("API 未返回文本")
        return text.strip()

    def _generate_with_retries(
        self,
        *,
        model: str,
        api_key: str,
        messages: list[dict],
        max_tokens: int | None,
    ) -> tuple[object, str]:
        last_error: requests.RequestException | None = None
        for attempt in range(1, TEXT_GENERATION_REQUEST_RETRIES + 1):
            try:
                return self._call_generation_once(
                    model=model,
                    api_key=api_key,
                    messages=messages,
                    max_tokens=max_tokens,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt == TEXT_GENERATION_REQUEST_RETRIES:
                    raise RuntimeError(
                        f"已重试 {TEXT_GENERATION_REQUEST_RETRIES} 次：{exc}"
                    ) from exc
                time.sleep(min(attempt * 2, 5))
        raise RuntimeError(f"文本模型请求失败：{last_error}")

    def _call_generation_once(
        self,
        *,
        model: str,
        api_key: str,
        messages: list[dict],
        max_tokens: int | None,
    ) -> tuple[object, str]:
        dashscope.base_http_api_url = self.base_url
        if self.uses_multimodal_api(model):
            response = MultiModalConversation.call(
                model=model,
                api_key=api_key,
                messages=self._to_multimodal_messages(messages),
                max_tokens=max_tokens,
            )
            return response, self._extract_multimodal_text(response)

        response = Generation.call(
            model=model,
            api_key=api_key,
            messages=messages,
            max_tokens=max_tokens,
        )
        return response, getattr(getattr(response, "output", None), "text", "") or ""

    @staticmethod
    def uses_multimodal_api(model: str) -> bool:
        normalized = model.lower()
        return normalized.startswith(MULTIMODAL_TEXT_MODEL_PREFIXES)

    def _to_multimodal_messages(self, messages: list[dict]) -> list[dict]:
        converted = []
        for message in messages:
            content = message.get("content", "")
            if isinstance(content, str):
                content = [{"text": content}]
            converted.append({**message, "content": content})
        return converted

    def _extract_multimodal_text(self, response: object) -> str:
        message = response.output.choices[0].message
        content = message.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
            return "\n".join(parts).strip()
        return str(content).strip()


class TextGenerationService:
    """封装故事概要到德语短文的生成能力。"""

    def __init__(self, model: str = QWEN_TEXT_MODEL):
        self.model = model
        self.client = TextGenerationClient(model=model)

    def generate_german_story(self, api_key: str, summary: str) -> str:
        return self.client.generate_text(
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
