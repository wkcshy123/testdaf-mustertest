import json
import tempfile
import unittest
from pathlib import Path

from testdaf_platform.services.reference_materials import ReferenceMaterialBundle
from testdaf_platform.storage.question_bank import QuestionBank
from testdaf_platform.usecases.create_reading_aufgabe_1 import (
    CreateReadingAufgabe1Request,
    CreateReadingAufgabe1UseCase,
)


class FakeReferenceMaterialService:
    def build(self, text_material: str, url_material: str) -> ReferenceMaterialBundle:
        return ReferenceMaterialBundle(
            combined_text=f"素材: {text_material.strip()}",
            sources={"text_material_chars": len(text_material.strip()), "urls": []},
        )


class FakeReadingAufgabe1Generator:
    def generate(self, api_key: str, data) -> dict:
        return {
            "title": "Praktika für Studierende",
            "topic": data.topic,
            "scenario": "Ordnen Sie jeder Person das passende Angebot zu.",
            "offers": [
                {"label": "A", "heading": "Angebot A", "text": "Beschreibung A " * 30},
                {"label": "B", "heading": "Angebot B", "text": "Beschreibung B " * 30},
            ],
            "profiles": [
                {"number": 1, "need": "Anna sucht ein Praktikum im Marketing."},
                {"number": 2, "need": "Ben möchte remote arbeiten."},
            ],
            "answers": [
                {"number": 1, "answer": "A", "evidence": "Angebot A passt zu Marketing.", "matching_reason": "Anna und Angebot A"},
                {"number": 2, "answer": "B", "evidence": "Angebot B ist remote.", "matching_reason": "Ben und Angebot B"},
            ],
            "length_metadata": {
                "target_per_offer_bytes": 500,
                "status": "ok",
                "offers": {"A": {"bytes": 510, "status": "ok"}, "B": {"bytes": 505, "status": "ok"}},
            },
            "example_offer_label": "A",
        }


class CreateReadingAufgabe1UseCaseTest(unittest.TestCase):
    def test_execute_creates_question_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bank = QuestionBank(root=Path(temp_dir))
            usecase = CreateReadingAufgabe1UseCase(
                reference_material_service=FakeReferenceMaterialService(),
                generator=FakeReadingAufgabe1Generator(),
                question_bank=bank,
            )

            manifest = usecase.execute(
                api_key="fake-key",
                request=CreateReadingAufgabe1Request(
                    topic="Sommerpraktika",
                    reference_material="Verschiedene Praktikumsangebote",
                    reference_urls="",
                    difficulty="standard",
                    offer_count=8,
                    no_match_count=3,
                ),
            )

            question_dir = Path(temp_dir) / "reading" / "aufgabe_1" / manifest.id
            saved_manifest = json.loads((question_dir / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(saved_manifest["title"], "Praktika für Studierende")
            self.assertEqual(saved_manifest["parameters"]["offer_count"], 8)
            self.assertEqual(saved_manifest["parameters"]["no_match_count"], 3)
            # reference material is processed through the fake service
            self.assertEqual(saved_manifest["reference_material"], "素材: Verschiedene Praktikumsangebote")
            self.assertTrue((question_dir / "texts.json").exists())
            self.assertTrue((question_dir / "profiles.json").exists())
            self.assertTrue((question_dir / "questions.json").exists())
            self.assertTrue((question_dir / "preview.md").exists())


if __name__ == "__main__":
    unittest.main()
