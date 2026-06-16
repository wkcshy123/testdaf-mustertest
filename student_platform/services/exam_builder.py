"""Assemble a full TestDaF exam by picking one question per task type."""

from __future__ import annotations

import random
from dataclasses import dataclass

from shared.question_bank import QuestionBankReader


# Each module maps to the task types it needs (one question per type).
EXAM_STRUCTURE = {
    "reading": ["aufgabe_1", "aufgabe_2", "aufgabe_3"],
    "listening": ["aufgabe_1", "aufgabe_2", "aufgabe_3"],
    "writing": ["aufgabe_1"],
    "speaking": [f"aufgabe_{n}" for n in range(1, 8)],
}

MODULE_ORDER = ["reading", "listening", "writing", "speaking"]


@dataclass(frozen=True)
class ExamBuildResult:
    """Outcome of building an exam: either questions or a list of gaps."""

    questions: dict[str, list[dict]] | None
    gaps: list[str]  # human-readable missing descriptions


class ExamBuilder:
    """Pick one random question per task type from the question bank.

    Strict mode: if any task type has zero questions, the build fails and
    returns the list of missing task types.
    """

    def __init__(self, reader: QuestionBankReader):
        self.reader = reader

    def build(self) -> ExamBuildResult:
        questions: dict[str, list[dict]] = {}
        gaps: list[str] = []

        for section in MODULE_ORDER:
            task_types = EXAM_STRUCTURE[section]
            section_questions = self.reader.list_questions(section=section)
            questions[section] = []

            for task_type in task_types:
                pool = [q for q in section_questions if q.get("task_type") == task_type]
                if not pool:
                    gaps.append(f"{section}/{task_type}")
                    continue
                picked = random.choice(pool)
                questions[section].append(picked)

        if gaps:
            return ExamBuildResult(questions=None, gaps=gaps)

        return ExamBuildResult(questions=questions, gaps=[])
