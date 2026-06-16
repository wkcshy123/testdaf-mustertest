import json
import tempfile
import unittest
from pathlib import Path

from testdaf_platform.services.reference_materials import ReferenceMaterialBundle
from testdaf_platform.services.writing import ChartRenderer
from testdaf_platform.storage.question_bank import QuestionBank
from testdaf_platform.usecases.create_writing_aufgabe_1 import (
    CreateWritingAufgabe1Request,
    CreateWritingAufgabe1UseCase,
)


class FakeReferenceMaterialService:
    def build(self, text_material: str, url_material: str) -> ReferenceMaterialBundle:
        return ReferenceMaterialBundle(
            combined_text=f"素材: {text_material.strip()}",
            sources={"text_material_chars": len(text_material.strip()), "urls": []},
        )


class FakeWritingGenerator:
    def generate(self, api_key: str, data) -> dict:
        return {
            "title": "Studium im Ausland",
            "topic": data.topic,
            "background": "Immer mehr Studierende verbringen einen Teil des Studiums im Ausland.",
            "task_prompt": "Beschreiben Sie die Entwicklung des Auslandsstudiums.",
            "writing_instructions": [
                "Beschreiben Sie die Grafik.",
                "Vergleichen Sie zwei Länder.",
                "Begründen Sie Ihre eigene Meinung.",
            ],
            "image_usage_note": "",
            "length_metadata": {"status": "ok"},
            "chart_specs": [
                {
                    "type": "bar",
                    "title": "Auslandsstudierende",
                    "data": [{"label": "2018", "value": 120}, {"label": "2022", "value": 180}],
                }
            ],
        }


class CreateWritingAufgabe1UseCaseTest(unittest.TestCase):
    def test_execute_creates_question_package_with_charts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bank = QuestionBank(root=Path(temp_dir))
            usecase = CreateWritingAufgabe1UseCase(
                reference_material_service=FakeReferenceMaterialService(),
                generator=FakeWritingGenerator(),
                chart_renderer=ChartRenderer(),
                question_bank=bank,
            )
            question_id = bank.new_question_id()

            manifest = usecase.execute(
                api_key="fake-key",
                request=CreateWritingAufgabe1Request(
                    topic="Auslandsstudium",
                    reference_material="Mobilitätsprogramme",
                    reference_urls="",
                    image_notes="",
                    difficulty="standard",
                    chart_count=2,
                    chart_type_preference="mixed",
                    argument_focus="balanced",
                    country_comparison="required",
                    question_id=question_id,
                    reference_image_files=[],
                    reference_image_paths=[],
                ),
            )

            self.assertEqual(manifest.id, question_id)
            question_dir = Path(temp_dir) / "writing" / "aufgabe_1" / manifest.id
            saved_manifest = json.loads((question_dir / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(saved_manifest["title"], "Studium im Ausland")
            self.assertEqual(saved_manifest["parameters"]["chart_count"], 2)
            self.assertEqual(saved_manifest["reference_material"], "素材: Mobilitätsprogramme")
            self.assertTrue((question_dir / "prompt.json").exists())
            self.assertTrue((question_dir / "charts.json").exists())
            # real ChartRenderer must produce an SVG file
            self.assertTrue((question_dir / "chart_1.svg").exists())
            self.assertTrue((question_dir / "preview.md").exists())


if __name__ == "__main__":
    unittest.main()
