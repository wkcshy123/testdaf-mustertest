"""Use case for creating Listening Aufgabe 1 question packages."""

from dataclasses import dataclass

from testdaf_platform.services.listening_aufgabe_1 import (
    ListeningAufgabe1Generator,
    ListeningAufgabe1Input,
)
from testdaf_platform.services.multi_speaker_tts import MultiSpeakerTTSService
from testdaf_platform.services.reference_materials import ReferenceMaterialService
from testdaf_platform.storage.question_bank import QuestionBank, QuestionManifest


@dataclass(frozen=True)
class CreateListeningAufgabe1Request:
    scenario: str
    reference_material: str
    reference_urls: str
    difficulty: str
    information_flow: str
    speech_speed: str
    speaker_a_voice: str
    speaker_b_voice: str


class CreateListeningAufgabe1UseCase:
    """Coordinate generation, TTS, and storage for Listening Aufgabe 1."""

    def __init__(
        self,
        *,
        reference_material_service: ReferenceMaterialService,
        generator: ListeningAufgabe1Generator,
        multi_speaker_tts_service: MultiSpeakerTTSService,
        question_bank: QuestionBank,
    ) -> None:
        self.reference_material_service = reference_material_service
        self.generator = generator
        self.multi_speaker_tts_service = multi_speaker_tts_service
        self.question_bank = question_bank

    def execute(self, *, api_key: str, request: CreateListeningAufgabe1Request) -> QuestionManifest:
        scenario = request.scenario.strip()
        reference_bundle = self.reference_material_service.build(
            request.reference_material,
            request.reference_urls,
        )
        generation = self.generator.generate(
            api_key,
            ListeningAufgabe1Input(
                scenario=scenario,
                reference_material=reference_bundle.combined_text,
                difficulty=request.difficulty,
                information_flow=request.information_flow,
            ),
        )

        question_id = self.question_bank.new_question_id()
        question_dir = self.question_bank.get_question_dir("listening", "aufgabe_1", question_id)
        speaker_voice_map = _build_voice_map(request.speaker_a_voice, request.speaker_b_voice)
        audio_result = self.multi_speaker_tts_service.synthesize_dialogue(
            api_key=api_key,
            segments=generation["segments"],
            speaker_voice_map=speaker_voice_map,
            output_dir=question_dir,
        )

        return self.question_bank.save_listening_aufgabe_1(
            question_id=question_id,
            scenario=scenario,
            reference_material=reference_bundle.combined_text,
            difficulty=request.difficulty,
            information_flow=request.information_flow,
            speech_speed=request.speech_speed,
            speaker_voice_map=speaker_voice_map,
            generation=generation,
            audio_filename=audio_result.path.name,
            audio_size_kb=audio_result.size_kb,
            segment_files=audio_result.segment_files,
            reference_sources=reference_bundle.sources,
        )


def _build_voice_map(speaker_a_voice: str, speaker_b_voice: str) -> dict[str, str]:
    if speaker_a_voice != speaker_b_voice:
        return {"A": speaker_a_voice, "B": speaker_b_voice}

    fallback = "Ethan" if speaker_a_voice != "Ethan" else "Cherry"
    return {"A": speaker_a_voice, "B": fallback}
