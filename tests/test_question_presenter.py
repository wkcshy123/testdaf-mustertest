import unittest
from pathlib import Path

from student_platform.services.question_presenter import QuestionPresenter


class FakeReader:
    """Returns canned bundles so tests don't touch the real question bank."""

    def __init__(self, bundle: dict):
        self._bundle = bundle

    def load_question_bundle(self, relative_path: str) -> dict:
        return self._bundle


class QuestionPresenterTest(unittest.TestCase):
    def _meta(self, **overrides) -> dict:
        meta = {
            "id": "q_test",
            "title": "Test",
            "topic": "Topic",
            "section": "listening",
            "task_type": "aufgabe_1",
            "_path": "listening/aufgabe_1/q_test",
            "assets": {"audio": "audio.wav"},
            "parameters": {"answer_mode": "short_text"},
        }
        meta.update(overrides)
        return meta

    # ---- short_text strips answer/evidence/acceptable_variants ----

    def test_short_text_strips_grading_fields(self) -> None:
        bundle = {
            "questions": [
                {
                    "number": 1,
                    "prompt": "Was?",
                    "required_points": 1,
                    "answer": ["Geheim"],
                    "acceptable_variants": ["secret"],
                    "evidence": "should not leak",
                }
            ]
        }
        view = QuestionPresenter(FakeReader(bundle)).present(self._meta())
        item = view["items"][0]
        self.assertEqual(item["number"], 1)
        self.assertEqual(item["prompt"], "Was?")
        self.assertNotIn("answer", item)
        self.assertNotIn("acceptable_variants", item)
        self.assertNotIn("evidence", item)

    # ---- richtig_falsch strips answer/evidence ----

    def test_richtig_falsch_strips_grading_fields(self) -> None:
        bundle = {
            "statements": [
                {
                    "number": 9,
                    "statement": "Eine Aussage.",
                    "answer": "Richtig",
                    "evidence": "leak",
                    "tested_information": "leak",
                    "distractor_type": "none",
                }
            ]
        }
        meta = self._meta(
            section="listening", task_type="aufgabe_2",
            parameters={"answer_mode": "richtig_falsch"},
        )
        view = QuestionPresenter(FakeReader(bundle)).present(meta)
        item = view["items"][0]
        self.assertEqual(item["statement"], "Eine Aussage.")
        self.assertNotIn("answer", item)
        self.assertNotIn("evidence", item)

    # ---- matching strips answer/matching_reason, exposes labels ----

    def test_matching_provides_option_labels(self) -> None:
        bundle = {
            "profiles": [{"number": 1, "need": "Person A braucht X."}],
            "texts": [
                {"label": "A", "heading": "Angebot A", "text": "Text A " * 20},
                {"label": "B", "heading": "Angebot B", "text": "Text B " * 20},
            ],
            "questions": [{"number": 1, "answer": "A", "evidence": "leak", "matching_reason": "leak"}],
        }
        meta = self._meta(
            section="reading", task_type="aufgabe_1",
            parameters={"answer_mode": "matching"},
        )
        view = QuestionPresenter(FakeReader(bundle)).present(meta)
        self.assertEqual(view["option_labels"], ["A", "B", "I"])
        self.assertEqual(view["items"][0]["need"], "Person A braucht X.")

    # ---- single_choice strips answer/evidence, keeps options ----

    def test_single_choice_keeps_options_strips_answer(self) -> None:
        bundle = {
            "questions": [
                {
                    "number": 11,
                    "prompt": "Was?",
                    "options": {"A": "Eins", "B": "Zwei", "C": "Drei"},
                    "answer": "B",
                    "evidence": "leak",
                }
            ]
        }
        meta = self._meta(
            section="reading", task_type="aufgabe_2",
            parameters={"answer_mode": "single_choice_abc"},
        )
        view = QuestionPresenter(FakeReader(bundle)).present(meta)
        item = view["items"][0]
        self.assertEqual(item["options"]["A"], "Eins")
        self.assertNotIn("answer", item)
        self.assertNotIn("evidence", item)

    # ---- ja_nein strips answer/evidence ----

    def test_ja_nein_strips_grading_fields(self) -> None:
        bundle = {
            "statements": [
                {
                    "number": 21,
                    "statement": "Aussage.",
                    "answer": "Ja",
                    "evidence": "leak",
                    "judgement_type": "supported",
                    "explanation": "leak",
                }
            ]
        }
        meta = self._meta(
            section="reading", task_type="aufgabe_3",
            parameters={"answer_mode": "ja_nein_not_given"},
        )
        view = QuestionPresenter(FakeReader(bundle)).present(meta)
        item = view["items"][0]
        self.assertNotIn("answer", item)
        self.assertNotIn("evidence", item)
        self.assertNotIn("judgement_type", item)

    # ---- play_count defaults to 1, reads from params when present ----

    def test_play_count_defaults_to_one(self) -> None:
        view = QuestionPresenter(FakeReader({"questions": []})).present(self._meta())
        self.assertEqual(view["play_count"], 1)

    def test_play_count_reads_from_params(self) -> None:
        meta = self._meta(parameters={"answer_mode": "short_text", "play_count": 2})
        view = QuestionPresenter(FakeReader({"questions": []})).present(meta)
        self.assertEqual(view["play_count"], 2)

    # ---- essay returns prompt data, no grading fields ----

    def test_essay_returns_prompt_and_strips_grading_fields(self) -> None:
        bundle = {
            "prompt": {
                "title": "Nebenjobs",
                "topic": "Thema",
                "background": "Hintergrundtext.",
                "task_prompt": "Schreiben Sie …",
                "writing_instructions": ["Punkt 1", "Punkt 2"],
                "length_metadata": {"status": "ok"},
            }
        }
        meta = self._meta(
            section="writing", task_type="aufgabe_1",
            assets={"chart_images": ["chart_1.svg", "chart_2.svg"]},
            parameters={"answer_mode": "essay"},
        )
        view = QuestionPresenter(FakeReader(bundle)).present(meta)
        self.assertIsNotNone(view)
        self.assertEqual(view["essay_background"], "Hintergrundtext.")
        self.assertEqual(view["essay_task_prompt"], "Schreiben Sie …")
        self.assertEqual(view["essay_instructions"], ["Punkt 1", "Punkt 2"])
        self.assertEqual(view["chart_images"], ["chart_1.svg", "chart_2.svg"])

    # ---- unsupported mode returns None ----

    def test_speaking_returns_none(self) -> None:
        meta = self._meta(
            section="speaking", task_type="aufgabe_1",
            assets={"audio": "intro.wav"},
            parameters={"answer_mode": "spoken_response"},
        )
        self.assertIsNone(QuestionPresenter(FakeReader({})).present(meta))


if __name__ == "__main__":
    unittest.main()
