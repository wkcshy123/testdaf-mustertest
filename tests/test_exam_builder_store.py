import json
import tempfile
import unittest
from pathlib import Path

from student_platform.services.attempt_store import AttemptStore
from student_platform.services.exam_builder import (
    EXAM_STRUCTURE,
    MODULE_ORDER,
    ExamBuildResult,
    ExamBuilder,
)
from student_platform.services.exam_store import ExamStore


class FakeReader:
    """QuestionBankReader stub with configurable question pools."""

    def __init__(self, pools: dict[str, list[dict]]):
        # pools: {"section": [{"id":..., "task_type":..., "title":...}, ...]}
        self._pools = pools

    def list_questions(self, section: str | None = None) -> list[dict]:
        if section is None:
            result = []
            for qs in self._pools.values():
                result.extend(qs)
            return result
        return list(self._pools.get(section, []))


def _full_pools() -> dict[str, list[dict]]:
    """Return pools with at least one question for every task type."""
    pools: dict[str, list[dict]] = {}
    for section, task_types in EXAM_STRUCTURE.items():
        pools[section] = [
            {"id": f"q_{section}_{tt}", "task_type": tt, "title": f"{section} {tt}"}
            for tt in task_types
        ]
    return pools


class ExamBuilderTest(unittest.TestCase):
    def test_build_success_picks_one_per_task_type(self) -> None:
        builder = ExamBuilder(FakeReader(_full_pools()))
        result = builder.build()
        self.assertEqual(result.gaps, [])
        self.assertIsNotNone(result.questions)
        for section in MODULE_ORDER:
            expected = len(EXAM_STRUCTURE[section])
            self.assertEqual(len(result.questions[section]), expected)

    def test_build_returns_gaps_when_missing(self) -> None:
        pools = _full_pools()
        # Remove all speaking aufgabe_3
        pools["speaking"] = [
            q for q in pools["speaking"] if q["task_type"] != "aufgabe_3"
        ]
        builder = ExamBuilder(FakeReader(pools))
        result = builder.build()
        self.assertIsNone(result.questions)
        self.assertIn("speaking/aufgabe_3", result.gaps)

    def test_build_picks_randomly(self) -> None:
        """With multiple questions per type, should pick one (not all)."""
        pools = _full_pools()
        pools["reading"].append(
            {"id": "q_reading_extra", "task_type": "aufgabe_1", "title": "extra"}
        )
        builder = ExamBuilder(FakeReader(pools))
        result = builder.build()
        reading_ids = [q["id"] for q in result.questions["reading"] if q.get("task_type") == "aufgabe_1"]
        self.assertEqual(len(reading_ids), 1)


class ExamStoreTest(unittest.TestCase):
    def test_create_and_load_exam(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ExamStore(Path(temp_dir))
            pools = _full_pools()
            exam_id = store.create_exam(pools)
            self.assertTrue(exam_id.startswith("exam_"))

            exam = store.load_exam(exam_id)
            self.assertIsNotNone(exam)
            self.assertEqual(exam["status"], "in_progress")
            self.assertEqual(exam["current_module"], "reading")
            self.assertIn("reading", exam["question_ids"])
            self.assertEqual(len(exam["question_ids"]["speaking"]), 7)

    def test_update_exam(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ExamStore(Path(temp_dir))
            exam_id = store.create_exam(_full_pools())
            store.update_exam(exam_id, current_module="listening", status="completed")

            exam = store.load_exam(exam_id)
            self.assertEqual(exam["current_module"], "listening")
            self.assertEqual(exam["status"], "completed")

    def test_list_exams(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ExamStore(Path(temp_dir))
            id1 = store.create_exam(_full_pools())
            import time; time.sleep(1.1)  # ensure distinct timestamp
            id2 = store.create_exam(_full_pools())
            exams = store.list_exams()
            self.assertEqual(len(exams), 2)
            # newest first
            self.assertEqual(exams[0]["exam_id"], id2)

    def test_load_nonexistent_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ExamStore(Path(temp_dir))
            self.assertIsNone(store.load_exam("exam_nonexistent"))


class AttemptStoreExamIdTest(unittest.TestCase):
    def test_save_with_exam_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = AttemptStore(Path(temp_dir))
            attempt_id = store.save(
                question_id="q_test1234",
                section="reading",
                task_type="aufgabe_1",
                answer_mode="matching",
                title="Test",
                answers={"1": "B"},
                time_limit_seconds=3600,
                elapsed_seconds=100,
                timed_out=False,
                exam_id="exam_20260617_test",
            )
            data = store.load_attempt(attempt_id)
            self.assertEqual(data["meta"]["exam_id"], "exam_20260617_test")

    def test_save_without_exam_id_has_no_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = AttemptStore(Path(temp_dir))
            attempt_id = store.save(
                question_id="q_test1234",
                section="reading",
                task_type="aufgabe_1",
                answer_mode="matching",
                title="Test",
                answers={"1": "B"},
                time_limit_seconds=600,
                elapsed_seconds=50,
                timed_out=False,
            )
            data = store.load_attempt(attempt_id)
            self.assertNotIn("exam_id", data["meta"])


if __name__ == "__main__":
    unittest.main()
