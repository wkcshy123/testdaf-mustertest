import json
import tempfile
import unittest
from pathlib import Path

from testdaf_platform.services.reference_materials import ReferenceMaterialBundle
from testdaf_platform.storage.question_bank import QuestionBank
from testdaf_platform.usecases.create_reading_aufgabe_3 import (
    CreateReadingAufgabe3Request,
    CreateReadingAufgabe3UseCase,
)


class FakeReferenceMaterialService:
    def build(self, text_material: str, url_material: str) -> ReferenceMaterialBundle:
        return ReferenceMaterialBundle(
            combined_text=f"素材: {text_material.strip()}",
            sources={"text_material_chars": len(text_material.strip()), "urls": []},
        )


class FakeReadingAufgabe3Generator:
    def generate(self, api_key: str, data) -> dict:
        return {
            "title": "Fernarbeit und Teams",
            "topic": data.topic,
            "reading_text": "Fernarbeit verändert die Zusammenarbeit. " * 80,
            "paragraphs": [
                {"index": 1, "heading": "Vorteile", "text": "Erste Absatz " * 20},
                {"index": 2, "heading": "Nachteile", "text": "Zweite Absatz " * 20},
            ],
            "statements": [
                {
                    "number": 1,
                    "statement": "Fernarbeit erhöht die Konzentration.",
                    "answer": "Ja",
                    "judgement_type": "ja",
                    "tested_information": "Konzentration bei Fernarbeit",
                    "evidence": "Der Text nennt höhere Konzentration.",
                    "explanation": "Studien bestätigen dies.",
                },
                {
                    "number": 2,
                    "statement": "Fernarbeit stärkt den informellen Austausch.",
                    "answer": "Nein",
                    "judgement_type": "nein",
                    "tested_information": "informeller Austausch",
                    "evidence": "Der Text sagt, dieser nehme ab.",
                    "explanation": "Weniger spontane Gespräche.",
                },
                {
                    "number": 3,
                    "statement": "Alle Teams profitieren gleichermaßen.",
                    "answer": "Text sagt dazu nichts",
                    "judgement_type": "not_given",
                    "tested_information": "gleichmäßiger Nutzen",
                    "evidence": "Dazu äußert sich der Text nicht.",
                    "explanation": "Keine Aussage vorhanden.",
                },
            ],
            "length_metadata": {"target_bytes": 4950, "actual_bytes": 5000},
        }


class CreateReadingAufgabe3UseCaseTest(unittest.TestCase):
    def test_execute_creates_question_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bank = QuestionBank(root=Path(temp_dir))
            usecase = CreateReadingAufgabe3UseCase(
                reference_material_service=FakeReferenceMaterialService(),
                generator=FakeReadingAufgabe3Generator(),
                question_bank=bank,
            )

            manifest = usecase.execute(
                api_key="fake-key",
                request=CreateReadingAufgabe3Request(
                    topic="Fernarbeit",
                    reference_material="Organisationspsychologie",
                    reference_urls="",
                    difficulty="standard",
                    judgement_balance="balanced",
                    unsupported_items="standard",
                ),
            )

            question_dir = Path(temp_dir) / "reading" / "aufgabe_3" / manifest.id
            saved_manifest = json.loads((question_dir / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(saved_manifest["title"], "Fernarbeit und Teams")
            self.assertEqual(saved_manifest["parameters"]["judgement_balance"], "balanced")
            self.assertEqual(saved_manifest["parameters"]["unsupported_items"], "standard")
            self.assertEqual(saved_manifest["reference_material"], "素材: Organisationspsychologie")
            self.assertTrue((question_dir / "reading_text.txt").exists())
            self.assertTrue((question_dir / "statements.json").exists())
            self.assertTrue((question_dir / "questions.json").exists())


if __name__ == "__main__":
    unittest.main()
