"""多人对话 TTS 与 WAV 拼接服务。"""

import wave
from dataclasses import dataclass
from pathlib import Path

from testdaf_platform.services.tts import TTSService


@dataclass(frozen=True)
class DialogueAudioResult:
    path: Path
    size_kb: float
    segment_files: list[str]
    speaker_voice_map: dict[str, str]
    instructions: list[str] = None
    used_instruct_model: bool = False


class MultiSpeakerTTSService:
    """按说话人分段生成音频，并插入语境停顿拼接为最终 WAV。

    当提供 ``instructions``（与 segments 等长、一一对应的 Qwen-TTS
    表现力指令）时，逐段切换到 instruct 模型，用自然语言控制语速、
    语气、情绪，使对话更自然。
    """

    def __init__(self, tts_service: TTSService | None = None):
        self.tts_service = tts_service or TTSService()

    def synthesize_dialogue(
        self,
        *,
        api_key: str,
        segments: list[dict],
        speaker_voice_map: dict[str, str],
        output_dir: Path,
        instructions: list[str] | None = None,
    ) -> DialogueAudioResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        segments_dir = output_dir / "audio_segments"
        segments_dir.mkdir(parents=True, exist_ok=True)

        if instructions is not None and len(instructions) != len(segments):
            raise RuntimeError(
                f"instructions 数量({len(instructions)})与 segments 数量"
                f"({len(segments)})不一致"
            )

        segment_files: list[Path] = []
        used_instruct_model = False
        recorded_instructions: list[str] = []
        for index, segment in enumerate(segments):
            speaker_id = segment["speaker_id"]
            voice = speaker_voice_map.get(speaker_id)
            if not voice:
                raise RuntimeError(f"说话人 {speaker_id} 未配置音色")

            instruction = instructions[index].strip() if instructions else ""
            segment_path = segments_dir / f"segment_{int(segment['index']):03d}_{speaker_id}.wav"
            result = self.tts_service.synthesize_german(
                api_key=api_key,
                text=segment["text"],
                voice=voice,
                save_path=segment_path,
                instruction=instruction,
            )
            segment_files.append(segment_path)
            recorded_instructions.append(result.instruction)
            if result.used_instruct_model:
                used_instruct_model = True

        final_path = output_dir / "audio.wav"
        self._concatenate_wavs(
            segment_paths=segment_files,
            pauses_ms=[int(segment["pause_after_ms"]) for segment in segments],
            output_path=final_path,
        )

        return DialogueAudioResult(
            path=final_path,
            size_kb=final_path.stat().st_size / 1024,
            segment_files=[str(path.relative_to(output_dir)) for path in segment_files],
            speaker_voice_map=speaker_voice_map,
            instructions=recorded_instructions,
            used_instruct_model=used_instruct_model,
        )

    def _concatenate_wavs(
        self,
        *,
        segment_paths: list[Path],
        pauses_ms: list[int],
        output_path: Path,
    ) -> None:
        if not segment_paths:
            raise RuntimeError("没有可拼接的音频片段")

        # Compare the audio FORMAT only (channels, sample width, framerate),
        # not the full params tuple — that also includes nframes, which
        # legitimately differs per segment and would block concatenation
        # whenever individual clips have different durations.
        with wave.open(str(segment_paths[0]), "rb") as first:
            base_params = first.getparams()
        base_format = (base_params.nchannels, base_params.sampwidth, base_params.framerate)

        with wave.open(str(output_path), "wb") as output:
            output.setnchannels(base_params.nchannels)
            output.setsampwidth(base_params.sampwidth)
            output.setframerate(base_params.framerate)
            for index, segment_path in enumerate(segment_paths):
                with wave.open(str(segment_path), "rb") as segment_file:
                    seg_format = (
                        segment_file.getnchannels(),
                        segment_file.getsampwidth(),
                        segment_file.getframerate(),
                    )
                    if seg_format != base_format:
                        raise RuntimeError("音频片段 WAV 格式（声道/位深/采样率）不一致，暂无法直接拼接")
                    output.writeframes(segment_file.readframes(segment_file.getnframes()))

                if index < len(segment_paths) - 1:
                    silence = self._silence_frames(base_params, pauses_ms[index])
                    output.writeframes(silence)

    def _silence_frames(self, params, pause_ms: int) -> bytes:
        frame_count = int(params.framerate * pause_ms / 1000)
        frame_width = params.nchannels * params.sampwidth
        return b"\x00" * frame_count * frame_width
