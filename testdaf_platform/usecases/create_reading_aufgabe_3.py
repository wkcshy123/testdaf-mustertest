"""Use case for creating Reading Aufgabe 3 question packages."""

from dataclasses import dataclass
from typing import NamedTuple

from testdaf_platform.services.reading import ReadingAufgabe3Generator, ReadingAufgabe3Input
from testdaf_platform.services.reference_materials import ReferenceMaterialService
from testdaf_platform.storage.question_bank import QuestionBank, QuestionManifest


class ReadingAufgabe3Result(NamedTuple):
    manifest: QuestionManifest
    generation: dict


@dataclass(frozen=True)
class CreateReadingAufgabe3Request:
    topic: str
    reference_material: str
    reference_urls: str
    difficulty: str
    judgement_balance: str
    unsupported_items: str


class CreateReadingAufgabe3UseCase:
    """Coordinate generation and storage for Reading Aufgabe 3."""

    def __init__(
        self,
        *,
        reference_material_service: ReferenceMaterialService,
        generator: ReadingAufgabe3Generator,
        question_bank: QuestionBank,
    ) -> None:
        self.reference_material_service = reference_material_service
        self.generator = generator
        self.question_bank = question_bank

    def execute(self, *, api_key: str, request: CreateReadingAufgabe3Request) -> ReadingAufgabe3Result:
        topic = request.topic.strip()
        reference_bundle = self.reference_material_service.build(
            request.reference_material,
            request.reference_urls,
        )
        generation = self.generator.generate(
            api_key,
            ReadingAufgabe3Input(
                topic=topic,
                reference_material=reference_bundle.combined_text,
                difficulty=request.difficulty,
                judgement_balance=request.judgement_balance,
                unsupported_items=request.unsupported_items,
            ),
        )

        return ReadingAufgabe3Result(
            manifest=self.question_bank.save_reading_aufgabe_3(
                question_id=self.question_bank.new_question_id(),
                topic_input=topic,
                reference_material=reference_bundle.combined_text,
                difficulty=request.difficulty,
                judgement_balance=request.judgement_balance,
                unsupported_items=request.unsupported_items,
                generation=generation,
                reference_sources=reference_bundle.sources,
            ),
            generation=generation,
        )
