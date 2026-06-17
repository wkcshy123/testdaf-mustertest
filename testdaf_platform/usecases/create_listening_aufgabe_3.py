"""Use case for creating Listening Aufgabe 3 question packages."""

from dataclasses import dataclass
from typing import NamedTuple

from testdaf_platform.config import VOICE_GENDER
from testdaf_platform.services.listening_aufgabe_3 import (
    ListeningAufgabe3Generator,
    ListeningAufgabe3Input,
)
from testdaf_platform.services.multi_speaker_tts import MultiSpeakerTTSService
from testdaf_platform.services.reference_materials import ReferenceMaterialService
from testdaf_platform.services.tts_instructions import InstructionGenerator
from testdaf_platform.services.generation_utils import build_two_voice_map
from testdaf_platform.storage.question_bank import QuestionBank, QuestionManifest
from testdaf_platform.usecases._instruction_support import attach_instructions_to_segments


class ListeningAufgabe3Result(NamedTuple):
    manifest: QuestionManifest
    generation: dict

    @property
    def id(self) -> str:
        return self.manifest.id


@dataclass(frozen=True)
class CreateListeningAufgabe3Request:
    topic: str
    expert_domain: str
    reference_material: str
    reference_urls: str
    difficulty: str
    question_focus_mix: str
    multi_point_questions: int
    speech_speed: str
    host_voice: str
    expert_voice: str


class CreateListeningAufgabe3UseCase:
    """Coordinate generation, TTS, and storage for Listening Aufgabe 3."""

    def __init__(
        self,
        *,
        reference_material_service: ReferenceMaterialService,
        generator: ListeningAufgabe3Generator,
        multi_speaker_tts_service: MultiSpeakerTTSService,
        question_bank: QuestionBank,
        instruction_generator: InstructionGenerator | None = None,
    ) -> None:
        self.reference_material_service = reference_material_service
        self.generator = generator
        self.multi_speaker_tts_service = multi_speaker_tts_service
        self.question_bank = question_bank
        self.instruction_generator = instruction_generator or InstructionGenerator()

    def execute(self, *, api_key: str, request: CreateListeningAufgabe3Request, progress_callback=None) -> ListeningAufgabe3Result:
        topic = request.topic.strip()
        expert_domain = request.expert_domain.strip()
        normalized_multi_point = max(0, min(int(request.multi_point_questions), 3))
        speaker_voice_map = build_two_voice_map(request.host_voice, request.expert_voice)
        speaker_genders = {sid: VOICE_GENDER[v] for sid, v in speaker_voice_map.items()}
        reference_bundle = self.reference_material_service.build(
            request.reference_material,
            request.reference_urls,
        )
        generator_input = ListeningAufgabe3Input(
            topic=topic,
            expert_domain=expert_domain,
            reference_material=reference_bundle.combined_text,
            difficulty=request.difficulty,
            question_focus_mix=request.question_focus_mix,
            multi_point_questions=normalized_multi_point,
            speaker_genders=speaker_genders,
        )
        if progress_callback is None:
            generation = self.generator.generate(api_key, generator_input)
        else:
            generation = self.generator.generate(
                api_key,
                generator_input,
                progress_callback=progress_callback,
            )

        instructions = self.instruction_generator.generate(
            api_key=api_key,
            title=generation.get("title", topic),
            scenario=f"{topic}（专家领域：{expert_domain}）" if expert_domain else topic,
            speaker_roles=generation.get("speaker_roles", {}),
            relationship=generation.get("relationship", ""),
            segments=generation["segments"],
            speech_speed=request.speech_speed,
        )
        generation["tts_instructions"] = instructions
        attach_instructions_to_segments(generation["segments"], instructions)

        question_id = self.question_bank.new_question_id()
        question_dir = self.question_bank.get_question_dir("listening", "aufgabe_3", question_id)
        audio_result = self.multi_speaker_tts_service.synthesize_dialogue(
            api_key=api_key,
            segments=generation["segments"],
            speaker_voice_map=speaker_voice_map,
            output_dir=question_dir,
            instructions=instructions,
        )

        return ListeningAufgabe3Result(
            manifest=self.question_bank.save_listening_aufgabe_3(
                question_id=question_id,
                topic_input=topic,
                expert_domain_input=expert_domain,
                reference_material=reference_bundle.combined_text,
                difficulty=request.difficulty,
                question_focus_mix=request.question_focus_mix,
                multi_point_questions=normalized_multi_point,
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
