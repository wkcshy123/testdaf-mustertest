"""Use case for creating Writing Aufgabe 1 question packages."""

from dataclasses import dataclass
from pathlib import Path

from testdaf_platform.services.reference_materials import ReferenceMaterialService
from testdaf_platform.services.writing import (
    ChartRenderer,
    WritingAufgabe1Generator,
    WritingAufgabe1Input,
)
from testdaf_platform.storage.question_bank import QuestionBank, QuestionManifest


@dataclass(frozen=True)
class CreateWritingAufgabe1Request:
    topic: str
    reference_material: str
    reference_urls: str
    image_notes: str
    difficulty: str
    chart_count: int
    chart_type_preference: str
    argument_focus: str
    country_comparison: str
    # question_id is allocated up-front by the caller so that reference images
    # (saved by the HTTP layer into the final question dir) stay bound to the
    # question even when generation later fails.
    question_id: str
    reference_image_files: list[str]
    reference_image_paths: list[Path]


class CreateWritingAufgabe1UseCase:
    """Coordinate generation, chart rendering, and storage for Writing Aufgabe 1."""

    def __init__(
        self,
        *,
        reference_material_service: ReferenceMaterialService,
        generator: WritingAufgabe1Generator,
        chart_renderer: ChartRenderer,
        question_bank: QuestionBank,
    ) -> None:
        self.reference_material_service = reference_material_service
        self.generator = generator
        self.chart_renderer = chart_renderer
        self.question_bank = question_bank

    def execute(self, *, api_key: str, request: CreateWritingAufgabe1Request) -> QuestionManifest:
        topic = request.topic.strip()
        normalized_chart_count = max(1, min(int(request.chart_count), 2))
        reference_bundle = self.reference_material_service.build(
            request.reference_material,
            request.reference_urls,
        )
        question_dir = self.question_bank.get_question_dir(
            "writing", "aufgabe_1", request.question_id
        )
        generation = self.generator.generate(
            api_key,
            WritingAufgabe1Input(
                topic=topic,
                reference_material=reference_bundle.combined_text,
                image_notes=request.image_notes.strip(),
                difficulty=request.difficulty,
                chart_count=normalized_chart_count,
                chart_type_preference=request.chart_type_preference,
                argument_focus=request.argument_focus,
                country_comparison=request.country_comparison,
                reference_image_paths=request.reference_image_paths,
            ),
        )
        chart_files = self.chart_renderer.render_charts(generation["chart_specs"], question_dir)

        return self.question_bank.save_writing_aufgabe_1(
            question_id=request.question_id,
            topic_input=topic,
            reference_material=reference_bundle.combined_text,
            difficulty=request.difficulty,
            chart_count=normalized_chart_count,
            chart_type_preference=request.chart_type_preference,
            argument_focus=request.argument_focus,
            country_comparison=request.country_comparison,
            generation=generation,
            chart_files=chart_files,
            reference_image_files=request.reference_image_files,
            reference_sources=reference_bundle.sources,
        )
