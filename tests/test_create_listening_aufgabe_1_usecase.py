import json
import tempfile
import unittest
from pathlib import Path

from testdaf_platform.services.multi_speaker_tts import DialogueAudioResult
from testdaf_platform.services.reference_materials import ReferenceMaterialBundle
from testdaf_platform.storage.question_bank import QuestionBank
from testdaf_platform.usecases.create_listening_aufgabe_1 import (
    CreateListeningAufgabe1Request,
    CreateListeningAufgabe1UseCase,
)


class FakeReferenceMaterialService:
    def build(self, text_material: str, url_material: str) -> ReferenceMaterialBundle:
        return ReferenceMaterialBundle(
            combined_text=f"素材: {text_material.strip()}",
            sources={"text_material_chars": len(text_material.strip()), "urls": []},
        )


class FakeListeningGenerator:
    def generate(self, api_key: str, data) -> dict:
        return {
            "title": "Bibliothek und Gruppenraum",
            "topic": "Lernen auf dem Campus",
            "relationship": "Zwei Studierende",
            "speaker_roles": {"A": "Studentin", "B": "Student"},
            "transcript": "A: Hallo. B: Hallo. " * 20,
            "segments": [
                {
                    "index": 1,
                    "speaker_id": "A",
                    "text": "Hallo, hast du kurz Zeit?",
                    "pause_after_ms": 300,
                    "pause_reason": "kurze Reaktion",
                },
                {
                    "index": 2,
                    "speaker_id": "B",
                    "text": "Ja, worum geht es?",
                    "pause_after_ms": 300,
                    "pause_reason": "Themenwechsel",
                },
            ],
            "questions": [
                {
                    "number": 1,
                    "prompt": "Worum geht es?",
                    "answer": ["um einen Gruppenraum"],
                    "acceptable_variants": ["Gruppenraum"],
                    "evidence": "Die Studierenden sprechen über einen Gruppenraum.",
                },
            ],
        }


class FakeInstructionGenerator:
    def generate(self, *, api_key, title, scenario, speaker_roles, relationship, segments, speech_speed="normal"):
        return [f"指令 {s.get('speaker_id')}" for s in segments]


class FakeMultiSpeakerTTSService:
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
        audio_path = output_dir / "audio.wav"
        audio_path.write_bytes(b"fake wav")
        return DialogueAudioResult(
            path=audio_path,
            size_kb=audio_path.stat().st_size / 1024,
            segment_files=["audio_segments/segment_001_A.wav"],
            speaker_voice_map=speaker_voice_map,
            instructions=instructions or [],
            used_instruct_model=bool(instructions),
        )


class CreateListeningAufgabe1UseCaseTest(unittest.TestCase):
    def test_execute_creates_question_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bank = QuestionBank(root=Path(temp_dir))
            usecase = CreateListeningAufgabe1UseCase(
                reference_material_service=FakeReferenceMaterialService(),
                generator=FakeListeningGenerator(),
                multi_speaker_tts_service=FakeMultiSpeakerTTSService(),
                instruction_generator=FakeInstructionGenerator(),
                question_bank=bank,
            )

            manifest = usecase.execute(
                api_key="fake-key",
                request=CreateListeningAufgabe1Request(
                    scenario="Zwei Studierende planen eine Lerngruppe",
                    reference_material="Campusbibliothek, Gruppenräume, Prüfungsphase",
                    reference_urls="",
                    difficulty="standard",
                    information_flow="sequential",
                    speech_speed="normal",
                    speaker_a_voice="Cherry",
                    speaker_b_voice="Cherry",
                ),
            )

            question_dir = Path(temp_dir) / "listening" / "aufgabe_1" / manifest.id
            saved_manifest = json.loads((question_dir / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(saved_manifest["title"], "Bibliothek und Gruppenraum")
            self.assertEqual(saved_manifest["parameters"]["speaker_voice_map"], {"A": "Cherry", "B": "Ethan"})
            self.assertTrue((question_dir / "audio.wav").exists())
            self.assertTrue((question_dir / "segments.json").exists())
            self.assertTrue((question_dir / "questions.json").exists())

            # Instructions are persisted onto each segment.
            saved_segments = json.loads((question_dir / "segments.json").read_text(encoding="utf-8"))
            self.assertTrue(all("tts_instruction" in s for s in saved_segments))


if __name__ == "__main__":
    unittest.main()
