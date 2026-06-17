"""Use case for creating Reading Aufgabe 2 question packages."""

from dataclasses import dataclass
from typing import NamedTuple

from testdaf_platform.services.reading import ReadingAufgabe2Generator, ReadingAufgabe2Input
from testdaf_platform.services.reference_materials import ReferenceMaterialService
from testdaf_platform.storage.question_bank import QuestionBank, QuestionManifest


class ReadingAufgabe2Result(NamedTuple):
    manifest: QuestionManifest
    generation: dict


@dataclass(frozen=True)
class CreateReadingAufgabe2Request:
    topic: str
    reference_material: str
    reference_urls: str
    difficulty: str
    text_length: str
    skill_focus: str


class CreateReadingAufgabe2UseCase:
    """Coordinate generation and storage for Reading Aufgabe 2."""

    def __init__(
        self,
        *,
        reference_material_service: ReferenceMaterialService,
        generator: ReadingAufgabe2Generator,
        question_bank: QuestionBank,
    ) -> None:
        self.reference_material_service = reference_material_service
        self.generator = generator
        self.question_bank = question_bank

    def execute(self, *, api_key: str, request: CreateReadingAufgabe2Request) -> ReadingAufgabe2Result:
        topic = request.topic.strip()
        reference_bundle = self.reference_material_service.build(
            request.reference_material,
            request.reference_urls,
        )
        generation = self.generator.generate(
            api_key,
            ReadingAufgabe2Input(
                topic=topic,
                reference_material=reference_bundle.combined_text,
                difficulty=request.difficulty,
                text_length=request.text_length,
                skill_focus=request.skill_focus,
            ),
        )

        return ReadingAufgabe2Result(
            manifest=self.question_bank.save_reading_aufgabe_2(
                question_id=self.question_bank.new_question_id(),
                topic_input=topic,
                reference_material=reference_bundle.combined_text,
                difficulty=request.difficulty,
                text_length=request.text_length,
                skill_focus=request.skill_focus,
                generation=generation,
                reference_sources=reference_bundle.sources,
            ),
            generation=generation,
        )
