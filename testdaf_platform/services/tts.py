"""Qwen-TTS 语音生成服务。"""

from dataclasses import dataclass
from pathlib import Path

import dashscope
import requests

from testdaf_platform.config import DASHSCOPE_BASE_URL, QWEN_TTS_MODEL

dashscope.base_http_api_url = DASHSCOPE_BASE_URL


@dataclass(frozen=True)
class TTSResult:
    path: Path
    size_kb: float
    audio_url: str


class TTSService:
    """封装德语文本转 WAV 音频的能力。"""

    def __init__(self, model: str = QWEN_TTS_MODEL):
        self.model = model

    def synthesize_german(
        self,
        *,
        api_key: str,
        text: str,
        voice: str,
        save_path: Path,
    ) -> TTSResult:
        resp = dashscope.MultiModalConversation.call(
            model=self.model,
            api_key=api_key,
            text=text,
            voice=voice,
            language_type="German",
            stream=False,
        )

        if resp.status_code != 200:
            raise RuntimeError(f"API 错误 {resp.status_code}: {resp.message or resp.code}")

        audio_url = resp.output.audio.url
        if not audio_url:
            raise RuntimeError("API 未返回音频 URL")

        download = requests.get(audio_url, timeout=60)
        download.raise_for_status()

        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(download.content)

        return TTSResult(
            path=save_path,
            size_kb=len(download.content) / 1024,
            audio_url=audio_url,
        )

