import json
import tempfile
import unittest
from pathlib import Path

from testdaf_platform.services.reference_materials import ReferenceMaterialBundle
from testdaf_platform.storage.question_bank import QuestionBank
from testdaf_platform.usecases.create_reading_aufgabe_2 import (
    CreateReadingAufgabe2Request,
    CreateReadingAufgabe2UseCase,
)


class FakeReferenceMaterialService:
    def build(self, text_material: str, url_material: str) -> ReferenceMaterialBundle:
        return ReferenceMaterialBundle(
            combined_text=f"素材: {text_material.strip()}",
            sources={"text_material_chars": len(text_material.strip()), "urls": []},
        )


class FakeReadingAufgabe2Generator:
    def generate(self, api_key: str, data) -> dict:
        return {
            "title": "Fahrradsharing in der Stadt",
            "topic": data.topic,
            "reading_text": "Fahrradsharing ist beliebt. " * 80,
            "paragraphs": [
                {"index": 1, "heading": "Einleitung", "text": "Erste Absatz " * 20},
                {"index": 2, "heading": "Probleme", "text": "Zweite Absatz " * 20},
            ],
            "questions": [
                {
                    "number": 1,
                    "prompt": "Was ist ein Vorteil?",
                    "options": {"A": "Kosten", "B": "Flexibilität", "C": "Lärm"},
                    "answer": "B",
                    "tested_skill": "detail",
                    "evidence": "Flexibilität wird im Text erwähnt.",
                    "distractor_explanation": "A und C sind nicht im Text.",
                },
                {
                    "number": 2,
                    "prompt": "Was ist ein Problem?",
                    "options": {"A": "Preise", "B": "Farben", "C": "wildes Parken"},
                    "answer": "C",
                    "tested_skill": "detail",
                    "evidence": "Falschparken wird kritisiert.",
                    "distractor_explanation": "A und B sind irrelevant.",
                },
            ],
            "length_metadata": {"current_bytes": 4150, "target_bytes": 4100, "status": "ok"},
        }


class CreateReadingAufgabe2UseCaseTest(unittest.TestCase):
    def test_execute_creates_question_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bank = QuestionBank(root=Path(temp_dir))
            usecase = CreateReadingAufgabe2UseCase(
                reference_material_service=FakeReferenceMaterialService(),
                generator=FakeReadingAufgabe2Generator(),
                question_bank=bank,
            )

            manifest = usecase.execute(
                api_key="fake-key",
                request=CreateReadingAufgabe2Request(
                    topic="Stadtfahrräder",
                    reference_material="Sharing-Wirtschaft",
                    reference_urls="",
                    difficulty="standard",
                    text_length="standard",
                    skill_focus="balanced",
                ),
            )

            question_dir = Path(temp_dir) / "reading" / "aufgabe_2" / manifest.id
            saved_manifest = json.loads((question_dir / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(saved_manifest["title"], "Fahrradsharing in der Stadt")
            self.assertEqual(saved_manifest["parameters"]["text_length"], "standard")
            self.assertEqual(saved_manifest["parameters"]["skill_focus"], "balanced")
            self.assertEqual(saved_manifest["reference_material"], "素材: Sharing-Wirtschaft")
            self.assertTrue((question_dir / "reading_text.txt").exists())
            self.assertTrue((question_dir / "paragraphs.json").exists())
            self.assertTrue((question_dir / "questions.json").exists())


if __name__ == "__main__":
    unittest.main()
