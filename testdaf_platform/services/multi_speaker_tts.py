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


class MultiSpeakerTTSService:
    """按说话人分段生成音频，并插入语境停顿拼接为最终 WAV。"""

    def __init__(self, tts_service: TTSService | None = None):
        self.tts_service = tts_service or TTSService()

    def synthesize_dialogue(
        self,
        *,
        api_key: str,
        segments: list[dict],
        speaker_voice_map: dict[str, str],
        output_dir: Path,
    ) -> DialogueAudioResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        segments_dir = output_dir / "audio_segments"
        segments_dir.mkdir(parents=True, exist_ok=True)

        segment_files: list[Path] = []
        for segment in segments:
            speaker_id = segment["speaker_id"]
            voice = speaker_voice_map.get(speaker_id)
            if not voice:
                raise RuntimeError(f"说话人 {speaker_id} 未配置音色")

            segment_path = segments_dir / f"segment_{int(segment['index']):03d}_{speaker_id}.wav"
            self.tts_service.synthesize_german(
                api_key=api_key,
                text=segment["text"],
                voice=voice,
                save_path=segment_path,
            )
            segment_files.append(segment_path)

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

        with wave.open(str(segment_paths[0]), "rb") as first:
            params = first.getparams()

        with wave.open(str(output_path), "wb") as output:
            output.setparams(params)
            for index, segment_path in enumerate(segment_paths):
                with wave.open(str(segment_path), "rb") as segment_file:
                    if segment_file.getparams() != params:
                        raise RuntimeError("音频片段 WAV 参数不一致，暂无法直接拼接")
                    output.writeframes(segment_file.readframes(segment_file.getnframes()))

                if index < len(segment_paths) - 1:
                    silence = self._silence_frames(params, pauses_ms[index])
                    output.writeframes(silence)

    def _silence_frames(self, params, pause_ms: int) -> bytes:
        frame_count = int(params.framerate * pause_ms / 1000)
        frame_width = params.nchannels * params.sampwidth
        return b"\x00" * frame_count * frame_width
