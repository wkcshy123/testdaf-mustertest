import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scoring_platform.services import report_builder
from shared.file_io.atomic_json import write_json_atomic


class ScoringReportBuilderTest(unittest.TestCase):
    def test_list_attempts_when_grading_results_dir_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            attempts_dir = root / "student_attempts"
            grading_dir = root / "grading_results"
            attempt_dir = attempts_dir / "attempt_20260618_014254_8b210559"
            attempt_dir.mkdir(parents=True)
            write_json_atomic(
                attempt_dir / "meta.json",
                {
                    "attempt_id": attempt_dir.name,
                    "question_id": "q_test",
                    "section": "reading",
                    "task_type": "aufgabe_3",
                    "answer_mode": "ja_nein_not_given",
                    "title": "Test Reading",
                    "submitted_at": "2026-06-18T01:42:54",
                    "student_id": "stu_test",
                    "student_name": "测试学生",
                },
            )
            write_json_atomic(attempt_dir / "answers.json", {"21": "Nein"})

            self.assertFalse(grading_dir.exists())
            with patch("scoring_platform.config.STUDENT_ATTEMPTS_DIR", attempts_dir):
                with patch.object(report_builder, "GRADING_RESULTS_DIR", grading_dir):
                    results = report_builder.list_graded_attempts("stu_test")

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["attempt_id"], attempt_dir.name)
            self.assertEqual(results[0]["student_id"], "stu_test")
            self.assertEqual(results[0]["title"], "Test Reading")


if __name__ == "__main__":
    unittest.main()
