"""Use case for creating Reading Aufgabe 1 question packages."""

from dataclasses import dataclass
from typing import NamedTuple

from testdaf_platform.services.reading import ReadingAufgabe1Generator, ReadingAufgabe1Input
from testdaf_platform.services.reference_materials import ReferenceMaterialService
from testdaf_platform.storage.question_bank import QuestionBank, QuestionManifest


class ReadingAufgabe1Result(NamedTuple):
    manifest: QuestionManifest
    generation: dict


@dataclass(frozen=True)
class CreateReadingAufgabe1Request:
    topic: str
    reference_material: str
    reference_urls: str
    difficulty: str
    offer_count: int
    no_match_count: int


class CreateReadingAufgabe1UseCase:
    """Coordinate generation and storage for Reading Aufgabe 1."""

    def __init__(
        self,
        *,
        reference_material_service: ReferenceMaterialService,
        generator: ReadingAufgabe1Generator,
        question_bank: QuestionBank,
    ) -> None:
        self.reference_material_service = reference_material_service
        self.generator = generator
        self.question_bank = question_bank

    def execute(self, *, api_key: str, request: CreateReadingAufgabe1Request) -> ReadingAufgabe1Result:
        topic = request.topic.strip()
        offer_count = int(request.offer_count)
        no_match_count = int(request.no_match_count)
        reference_bundle = self.reference_material_service.build(
            request.reference_material,
            request.reference_urls,
        )
        generation = self.generator.generate(
            api_key,
            ReadingAufgabe1Input(
                topic=topic,
                reference_material=reference_bundle.combined_text,
                difficulty=request.difficulty,
                offer_count=offer_count,
                no_match_count=no_match_count,
            ),
        )

        return ReadingAufgabe1Result(
            manifest=self.question_bank.save_reading_aufgabe_1(
            question_id=self.question_bank.new_question_id(),
            topic_input=topic,
            reference_material=reference_bundle.combined_text,
            difficulty=request.difficulty,
            offer_count=offer_count,
            no_match_count=no_match_count,
            generation=generation,
            reference_sources=reference_bundle.sources,
        ),
        generation=generation,
    )
