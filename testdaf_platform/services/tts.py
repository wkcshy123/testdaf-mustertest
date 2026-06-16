"""Qwen-TTS 语音生成服务。"""

from dataclasses import dataclass
from pathlib import Path

import dashscope
import requests

from testdaf_platform.config import (
    DASHSCOPE_BASE_URL,
    QWEN_TTS_INSTRUCT_MODEL,
    QWEN_TTS_MODEL,
)

dashscope.base_http_api_url = DASHSCOPE_BASE_URL

AUDIO_DOWNLOAD_TIMEOUT_SECONDS = 180
AUDIO_DOWNLOAD_RETRIES = 3


@dataclass(frozen=True)
class TTSResult:
    path: Path
    size_kb: float
    audio_url: str
    instruction: str = ""
    used_instruct_model: bool = False


class TTSService:
    """封装德语文本转 WAV 音频的能力。

    当提供 ``instruction`` 时，自动切换到支持指令控制的
    ``qwen3-tts-instruct-flash`` 模型，并用自然语言控制语速、语气、
    情绪等表现力，使对话更自然。
    """

    def __init__(
        self,
        model: str = QWEN_TTS_MODEL,
        instruct_model: str = QWEN_TTS_INSTRUCT_MODEL,
    ):
        self.model = model
        self.instruct_model = instruct_model

    def synthesize_german(
        self,
        *,
        api_key: str,
        text: str,
        voice: str,
        save_path: Path,
        instruction: str = "",
        optimize_instructions: bool = True,
    ) -> TTSResult:
        instruction = (instruction or "").strip()
        call_kwargs: dict = {
            "api_key": api_key,
            "text": text,
            "voice": voice,
            "language_type": "German",
            "stream": False,
        }
        used_instruct_model = False
        if instruction:
            # 指令控制需要使用 instruct 模型；普通 flash 模型不响应 instructions。
            call_kwargs["model"] = self.instruct_model
            call_kwargs["instructions"] = instruction
            call_kwargs["optimize_instructions"] = optimize_instructions
            used_instruct_model = True
        else:
            call_kwargs["model"] = self.model

        resp = dashscope.MultiModalConversation.call(**call_kwargs)

        if resp.status_code != 200:
            raise RuntimeError(f"API 错误 {resp.status_code}: {resp.message or resp.code}")

        audio_url = resp.output.audio.url
        if not audio_url:
            raise RuntimeError("API 未返回音频 URL")

        download = self._download_audio(audio_url)

        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(download.content)

        return TTSResult(
            path=save_path,
            size_kb=len(download.content) / 1024,
            audio_url=audio_url,
            instruction=instruction,
            used_instruct_model=used_instruct_model,
        )

    def _download_audio(self, audio_url: str) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(1, AUDIO_DOWNLOAD_RETRIES + 1):
            try:
                response = requests.get(audio_url, timeout=AUDIO_DOWNLOAD_TIMEOUT_SECONDS)
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
                if attempt == AUDIO_DOWNLOAD_RETRIES:
                    break
        raise RuntimeError(f"下载 TTS 音频失败，已重试 {AUDIO_DOWNLOAD_RETRIES} 次：{last_error}") from last_error
