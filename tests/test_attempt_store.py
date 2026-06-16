import json
import tempfile
import unittest
from pathlib import Path

from student_platform.services.attempt_store import AttemptStore


class AttemptStoreTest(unittest.TestCase):
    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = AttemptStore(Path(temp_dir))
            attempt_id = store.save(
                question_id="q_test1234",
                section="listening",
                task_type="aufgabe_1",
                answer_mode="short_text",
                title="Test Question",
                answers={"1": "online", "2": "Bibliothek"},
                time_limit_seconds=300,
                elapsed_seconds=120,
                timed_out=False,
            )
            self.assertTrue(attempt_id.startswith("attempt_"))

            data = store.load_attempt(attempt_id)
            self.assertIsNotNone(data)
            self.assertEqual(data["meta"]["question_id"], "q_test1234")
            self.assertEqual(data["meta"]["answer_mode"], "short_text")
            self.assertEqual(data["answers"]["1"], "online")

    def test_list_attempts_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = AttemptStore(Path(temp_dir))
            id1 = store.save(
                question_id="q_aaaaaaaa", section="reading", task_type="aufgabe_1",
                answer_mode="matching", title="A", answers={"1": "B"},
                time_limit_seconds=600, elapsed_seconds=10, timed_out=False,
            )
            id2 = store.save(
                question_id="q_bbbbbbbb", section="reading", task_type="aufgabe_2",
                answer_mode="single_choice_abc", title="B", answers={"11": "C"},
                time_limit_seconds=600, elapsed_seconds=20, timed_out=True,
            )
            attempts = store.list_attempts()
            self.assertEqual(len(attempts), 2)
            # newest first
            self.assertEqual(attempts[0]["attempt_id"], id2)
            self.assertEqual(attempts[1]["attempt_id"], id1)
            self.assertTrue(attempts[0]["timed_out"])

    def test_load_nonexistent_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = AttemptStore(Path(temp_dir))
            self.assertIsNone(store.load_attempt("attempt_does_not_exist"))


if __name__ == "__main__":
    unittest.main()
