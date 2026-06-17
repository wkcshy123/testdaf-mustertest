"""Use case for creating Listening Aufgabe 2 question packages."""

from dataclasses import dataclass
from typing import NamedTuple

from testdaf_platform.config import VOICE_GENDER
from testdaf_platform.services.listening_aufgabe_2 import (
    ListeningAufgabe2Generator,
    ListeningAufgabe2Input,
)
from testdaf_platform.services.multi_speaker_tts import MultiSpeakerTTSService
from testdaf_platform.services.reference_materials import ReferenceMaterialService
from testdaf_platform.services.tts_instructions import InstructionGenerator
from testdaf_platform.storage.question_bank import QuestionBank, QuestionManifest
from testdaf_platform.usecases._instruction_support import attach_instructions_to_segments


class ListeningAufgabe2Result(NamedTuple):
    manifest: QuestionManifest
    generation: dict


@dataclass(frozen=True)
class CreateListeningAufgabe2Request:
    topic: str
    reference_material: str
    reference_urls: str
    difficulty: str
    information_flow: str
    statement_balance: str
    speech_speed: str
    host_voice: str
    guest_b_voice: str
    guest_c_voice: str
    guest_d_voice: str = ""


class CreateListeningAufgabe2UseCase:
    """Coordinate generation, TTS, and storage for Listening Aufgabe 2."""

    def __init__(
        self,
        *,
        reference_material_service: ReferenceMaterialService,
        generator: ListeningAufgabe2Generator,
        multi_speaker_tts_service: MultiSpeakerTTSService,
        question_bank: QuestionBank,
        instruction_generator: InstructionGenerator | None = None,
    ) -> None:
        self.reference_material_service = reference_material_service
        self.generator = generator
        self.multi_speaker_tts_service = multi_speaker_tts_service
        self.question_bank = question_bank
        self.instruction_generator = instruction_generator or InstructionGenerator()

    def execute(self, *, api_key: str, request: CreateListeningAufgabe2Request, progress_callback=None) -> ListeningAufgabe2Result:
        topic = request.topic.strip()
        speaker_voice_map = _build_multi_voice_map(
            request.host_voice, request.guest_b_voice, request.guest_c_voice, request.guest_d_voice
        )
        speaker_genders = {sid: VOICE_GENDER[v] for sid, v in speaker_voice_map.items()}
        reference_bundle = self.reference_material_service.build(
            request.reference_material,
            request.reference_urls,
        )
        generation = self.generator.generate(
            api_key,
            ListeningAufgabe2Input(
                topic=topic,
                reference_material=reference_bundle.combined_text,
                difficulty=request.difficulty,
                information_flow=request.information_flow,
                statement_balance=request.statement_balance,
                speaker_genders=speaker_genders,
            ),
            progress_callback=progress_callback,
        )

        instructions = self.instruction_generator.generate(
            api_key=api_key,
            title=generation.get("title", topic),
            scenario=topic,
            speaker_roles=generation.get("speaker_roles", {}),
            relationship=generation.get("relationship", ""),
            segments=generation["segments"],
            speech_speed=request.speech_speed,
        )
        generation["tts_instructions"] = instructions
        attach_instructions_to_segments(generation["segments"], instructions)

        question_id = self.question_bank.new_question_id()
        question_dir = self.question_bank.get_question_dir("listening", "aufgabe_2", question_id)
        audio_result = self.multi_speaker_tts_service.synthesize_dialogue(
            api_key=api_key,
            segments=generation["segments"],
            speaker_voice_map=speaker_voice_map,
            output_dir=question_dir,
            instructions=instructions,
        )

        return ListeningAufgabe2Result(
            manifest=self.question_bank.save_listening_aufgabe_2(
                question_id=question_id,
                topic_input=topic,
                reference_material=reference_bundle.combined_text,
                difficulty=request.difficulty,
                information_flow=request.information_flow,
                statement_balance=request.statement_balance,
                speech_speed=request.speech_speed,
                speaker_voice_map=speaker_voice_map,
                generation=generation,
                audio_filename=audio_result.path.name,
                audio_size_kb=audio_result.size_kb,
                segment_files=audio_result.segment_files,
                reference_sources=reference_bundle.sources,
            ),
            generation=generation,
        )


def _build_multi_voice_map(
    host_voice: str, guest_b_voice: str, guest_c_voice: str, guest_d_voice: str = ""
) -> dict[str, str]:
    selected = [host_voice, guest_b_voice, guest_c_voice]
    keys = ["A", "B", "C"]
    if guest_d_voice.strip():
        selected.append(guest_d_voice.strip())
        keys.append("D")
    fallbacks = ["Neil", "Maia", "Ethan", "Cherry", "Kai", "Serena"]
    resolved: list[str] = []
    for voice in selected:
        if voice not in resolved:
            resolved.append(voice)
        else:
            replacement = next(item for item in fallbacks if item not in resolved)
            resolved.append(replacement)
    return {keys[i]: resolved[i] for i in range(len(resolved))}
