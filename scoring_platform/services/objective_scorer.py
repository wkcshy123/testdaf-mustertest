from __future__ import annotations

from pathlib import Path
from scoring_platform.config import (
    QUESTION_BANK_DIR, READING_TDN, LISTENING_TDN, TASK_LABELS,
)
from shared.file_io.atomic_json import read_json


GRADING_FIELDS = {
    "short_text": ["answer", "acceptable_variants"],
    "richtig_falsch": ["answer"],
    "matching": ["answer"],
    "single_choice_abc": ["answer"],
    "ja_nein_not_given": ["answer"],
    "essay": [],
    "spoken_response": [],
}

ANSWER_BUNDLE_KEY = {
    "short_text": "questions",
    "richtig_falsch": "statements",
    "matching": "questions",
    "single_choice_abc": "questions",
    "ja_nein_not_given": "statements",
}


def _find_question_dir(question_id: str) -> Path | None:
    for path in QUESTION_BANK_DIR.rglob(question_id):
        if path.is_dir() and ".trash" not in path.parts and (path / "manifest.json").exists():
            return path
    return None


def _load_answer_items(question_id: str, answer_mode: str) -> list[dict] | None:
    if answer_mode not in GRADING_FIELDS or not GRADING_FIELDS[answer_mode]:
        return None
    qdir = _find_question_dir(question_id)
    if not qdir:
        return None
    manifest = read_json(qdir / "manifest.json")
    bundle_key = ANSWER_BUNDLE_KEY.get(answer_mode)
    if not bundle_key:
        return None
    asset_name = manifest.get("assets", {}).get(bundle_key)
    if not asset_name:
        return None
    answer_file = qdir / asset_name
    if not answer_file.exists():
        return None
    return read_json(answer_file)


def _check_short_text(student_answer: str, correct: dict) -> bool:
    answer = correct.get("answer", "")
    if isinstance(answer, list):
        acceptable = [str(item).strip().lower() for item in answer]
    else:
        acceptable = [str(answer).strip().lower()]
    variants = correct.get("acceptable_variants", [])
    if isinstance(variants, list):
        acceptable.extend(v.strip().lower() for v in variants if isinstance(v, str))
    student = (student_answer or "").strip().lower()
    return student in acceptable


def _check_choice(student_answer: str, correct: dict) -> bool:
    return (student_answer or "").strip().upper() == str(correct.get("answer", "")).strip().upper()


def _check_matching(student_answer: str | dict, correct: dict) -> bool:
    correct_answer = correct.get("answer", "")
    if isinstance(correct_answer, dict):
        if not isinstance(student_answer, dict):
            return False
        return all(correct_answer.get(k) == student_answer.get(k) for k in correct_answer)
    return str(student_answer or "").strip().upper() == str(correct_answer).strip().upper()


CHECK_FUNCTIONS = {
    "short_text": _check_short_text,
    "richtig_falsch": _check_choice,
    "single_choice_abc": _check_choice,
    "ja_nein_not_given": _check_choice,
    "matching": _check_matching,
}


def _tdn_for_section(section: str, correct: int, total: int) -> tuple[int, str]:
    table = READING_TDN if section == "reading" else LISTENING_TDN
    for (lo, hi), (tdn, label) in table.items():
        if lo <= correct <= hi:
            return tdn, label
    return 0, "U3"


def score_objective(attempt_meta: dict, student_answers: dict | list) -> dict | None:
    question_id = attempt_meta.get("question_id", "")
    section = attempt_meta.get("section", "")
    answer_mode = attempt_meta.get("answer_mode", "")

    answer_items = _load_answer_items(question_id, answer_mode)
    if not answer_items:
        return None

    checker = CHECK_FUNCTIONS.get(answer_mode, _check_choice)

    task_ranges: dict[str, tuple[int, int]]
    if section == "reading":
        task_ranges = {"aufgabe_1": (1, 10), "aufgabe_2": (11, 20), "aufgabe_3": (21, 30)}
    else:
        task_ranges = {"aufgabe_1": (1, 8), "aufgabe_2": (9, 18), "aufgabe_3": (19, 25)}

    if isinstance(student_answers, dict):
        answers_dict = student_answers
    elif isinstance(student_answers, list):
        answers_dict = {str(i + 1): v for i, v in enumerate(student_answers)}
    else:
        answers_dict = {}

    tasks_result = []
    total_correct = 0
    total_questions = len(answer_items)

    for task_name, (lo, hi) in task_ranges.items():
        task_items = [it for it in answer_items if lo <= it.get("number", 0) <= hi]
        if not task_items:
            continue
        correct_count = 0
        errors = []
        for item in task_items:
            num = item.get("number", 0)
            student_val = answers_dict.get(str(num), answers_dict.get(f"q_{num}", ""))
            is_correct = checker(student_val, item)
            if is_correct:
                correct_count += 1
            else:
                correct_val = item.get("answer", "")
                errors.append({
                    "number": num,
                    "student": str(student_val) if student_val else "未作答",
                    "correct": str(correct_val) if correct_val else "—",
                })
        total_correct += correct_count
        tasks_result.append({
            "task": task_name,
            "label": TASK_LABELS.get(task_name, task_name),
            "total": len(task_items),
            "correct": correct_count,
            "errors": errors,
        })

    tdn, tdn_label = _tdn_for_section(section, total_correct, total_questions)

    return {
        "total_correct": total_correct,
        "total_questions": total_questions,
        "tdn": tdn,
        "tdn_label": tdn_label,
        "tasks": tasks_result,
    }
