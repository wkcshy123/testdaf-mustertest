import json
import tempfile
import unittest
from pathlib import Path

from testdaf_platform.storage.question_bank import QuestionBank


def _write_manifest(question_dir: Path, *, title: str = "Original") -> None:
    question_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": question_dir.name,
        "section": "reading",
        "task_type": "aufgabe_1",
        "title": title,
        "topic": "Topic",
        "reference_material": "",
        "parameters": {},
        "assets": {},
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
        "version": 1,
    }
    (question_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class QuestionBankFileSafetyTest(unittest.TestCase):
    def test_restore_does_not_overwrite_existing_question(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bank = QuestionBank(root=Path(temp_dir))
            relative_path = "reading/aufgabe_1/q_restore"
            question_dir = Path(temp_dir) / relative_path
            _write_manifest(question_dir)

            bank.move_to_trash(relative_path)
            _write_manifest(question_dir, title="Replacement")

            with self.assertRaisesRegex(RuntimeError, "原始位置已有题目"):
                bank.restore_from_trash(relative_path)

            manifest = json.loads((question_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["title"], "Replacement")

    def test_rename_uses_atomic_json_without_temp_leftovers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bank = QuestionBank(root=Path(temp_dir))
            relative_path = "reading/aufgabe_1/q_rename"
            question_dir = Path(temp_dir) / relative_path
            _write_manifest(question_dir)

            bank.rename_question(relative_path, "New Title")

            manifest = json.loads((question_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["title"], "New Title")
            self.assertFalse(list(question_dir.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
