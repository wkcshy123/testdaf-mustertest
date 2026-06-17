"""Unified Qwen text generation client."""

import time

import dashscope
import dashscope.common.constants as _ds_const
import requests
from dashscope import Generation, MultiModalConversation

from testdaf_platform.config import DASHSCOPE_BASE_URL, QWEN_TEXT_MODEL
from shared.api_stats import get_api_stats

dashscope.base_http_api_url = DASHSCOPE_BASE_URL

_ds_const.DEFAULT_REQUEST_TIMEOUT_SECONDS = 600

import dashscope.client.base_api as _ba
_ba.DEFAULT_REQUEST_TIMEOUT_SECONDS = 600


MULTIMODAL_TEXT_MODEL_PREFIXES = ("qwen3.7", "qwen3.6", "qwen3.5")
TEXT_GENERATION_REQUEST_RETRIES = 3
DEFAULT_FALLBACK_TEXT_MODELS = ("qwen3.6-flash",)


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
        if fallback_models is None:
            self.fallback_models = tuple(
                fallback for fallback in DEFAULT_FALLBACK_TEXT_MODELS if fallback != model
            )
        else:
            self.fallback_models = tuple(fallback_models)

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
        stats = get_api_stats()

        for model in (self.model, *self.fallback_models):
            try:
                t0 = time.time()
                response, text = self._generate_with_retries(
                    model=model,
                    api_key=api_key,
                    messages=messages,
                    max_tokens=max_tokens,
                )
                stats.record_text(model=model, status="ok", elapsed_seconds=time.time() - t0)
                break
            except RuntimeError as exc:
                stats.record_text(model=model, status="error", error_message=str(exc))
                model_errors.append(f"{model}: {exc}")
                if model == self.model and not self.fallback_models:
                    raise
        else:
            raise RuntimeError("文本模型请求失败：" + "；".join(model_errors))

        if response is None:
            raise RuntimeError("文本模型请求失败：未获得响应")
        if response.status_code != 200:
            error_msg = f"API 错误 {response.status_code}: {response.message or response.code}"
            raise RuntimeError(error_msg)
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
