from __future__ import annotations

from datetime import datetime
from pathlib import Path

from scoring_platform.config import (
    GRADING_RESULTS_DIR, SECTION_LABELS, TASK_LABELS,
    DIMENSION_LABELS, DIMENSION_DESCRIPTIONS,
)
from scoring_platform.services.objective_scorer import score_objective
from scoring_platform.services.writing_scorer import score_writing, _extract_student_text
from scoring_platform.services.speaking_store import get_speaking
from shared.file_io.atomic_json import read_json, write_json_atomic


def _find_attempt_dir(attempt_id: str) -> Path | None:
    from scoring_platform.config import STUDENT_ATTEMPTS_DIR
    attempt_dir = STUDENT_ATTEMPTS_DIR / attempt_id
    if attempt_dir.exists():
        return attempt_dir
    return None


def _result_path(attempt_id: str) -> Path:
    result_dir = GRADING_RESULTS_DIR / attempt_id
    result_dir.mkdir(parents=True, exist_ok=True)
    return result_dir / "result.json"


def score_attempt(attempt_id: str) -> dict | None:
    result_file = _result_path(attempt_id)
    if result_file.exists():
        return read_json(result_file)

    attempt_dir = _find_attempt_dir(attempt_id)
    if not attempt_dir:
        return None

    meta = read_json(attempt_dir / "meta.json")
    answers = read_json(attempt_dir / "answers.json")

    section = meta.get("section", "")
    answer_mode = meta.get("answer_mode", "")

    result_base = {
        "attempt_id": attempt_id,
        "scored_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "question_id": meta.get("question_id", ""),
        "section": section,
        "task_type": meta.get("task_type", ""),
        "answer_mode": answer_mode,
        "title": meta.get("title", ""),
        "exam_id": meta.get("exam_id", ""),
        "student_id": meta.get("student_id", ""),
        "student_name": meta.get("student_name", ""),
        "objective": None,
        "writing": None,
    }

    if section in ("reading", "listening"):
        objective = score_objective(meta, answers)
        if objective:
            result_base["objective"] = objective
        else:
            result_base["objective"] = {
                "total_correct": 0, "total_questions": 0,
                "tdn": 0, "tdn_label": "—",
                "tasks": [],
            }
    elif section == "writing":
        writing = score_writing(meta, answers)
        student_text = _extract_student_text(meta, answers)
        if writing:
            writing["student_text"] = student_text
            result_base["writing"] = writing
        else:
            result_base["writing"] = {
                "tdn": 0, "tdn_label": "—",
                "dimensionen": {}, "kommentar": "",
                "student_text": student_text,
            }

    write_json_atomic(result_file, result_base)
    return result_base


def list_graded_attempts(student_id: str | None = None) -> list[dict]:
    results = []

    from scoring_platform.config import STUDENT_ATTEMPTS_DIR

    for attempt_dir in sorted(STUDENT_ATTEMPTS_DIR.glob("attempt_*"), reverse=True):
        aid = attempt_dir.name
        meta_file = attempt_dir / "meta.json"
        if not meta_file.exists():
            continue
        try:
            meta = read_json(meta_file)
        except Exception:
            continue

        sid = meta.get("student_id", "")
        if student_id and sid != student_id:
            continue

        result_file = GRADING_RESULTS_DIR / aid / "result.json"
        result = {}
        if result_file.exists():
            try:
                result = read_json(result_file)
            except Exception:
                pass

        section = meta.get("section", "")
        obj = result.get("objective") or {}
        wri = result.get("writing") or {}

        summary = {
            "attempt_id": aid,
            "section": section,
            "task_type": meta.get("task_type", ""),
            "title": meta.get("title", ""),
            "student_id": sid,
            "student_name": meta.get("student_name", ""),
            "exam_id": meta.get("exam_id", ""),
            "submitted_at": meta.get("submitted_at", ""),
            "tdn": obj.get("tdn") or wri.get("tdn") or 0,
            "tdn_label": obj.get("tdn_label") or wri.get("tdn_label") or "—",
            "correct": obj.get("total_correct"),
            "total": obj.get("total_questions"),
            "dimensionen": wri.get("dimensionen"),
            "kommentar": wri.get("kommentar"),
        }
        results.append(summary)

    # 注入口语评分
    if student_id:
        spk = get_speaking(student_id)
        if spk.get("overall_label"):
            results.append({
                "attempt_id": "",
                "section": "speaking",
                "task_type": "",
                "title": "Sprechen (口语)",
                "student_id": spk.get("student_id", student_id),
                "student_name": spk.get("student_name", ""),
                "exam_id": "",
                "submitted_at": spk.get("updated_at", ""),
                "tdn": spk.get("overall_tdn", 0),
                "tdn_label": spk.get("overall_label", "—"),
                "correct": None,
                "total": None,
                "dimensionen": spk.get("tasks"),
                "kommentar": None,
            })
    else:
        from scoring_platform.services.speaking_store import list_all_speaking
        all_speaking = list_all_speaking()
        for sid, spk in all_speaking.items():
            if spk.get("overall_label"):
                results.append({
                    "attempt_id": "",
                    "section": "speaking",
                    "task_type": "",
                    "title": "Sprechen (口语)",
                    "student_id": sid,
                    "student_name": spk.get("student_name", ""),
                    "exam_id": "",
                    "submitted_at": spk.get("updated_at", ""),
                    "tdn": spk.get("overall_tdn", 0),
                    "tdn_label": spk.get("overall_label", "—"),
                    "correct": None,
                    "total": None,
                    "dimensionen": spk.get("tasks"),
                    "kommentar": None,
                })

    return results


def build_exam_summary(exam_id: str) -> dict | None:
    from scoring_platform.config import STUDENT_ATTEMPTS_DIR

    exam_dir = STUDENT_ATTEMPTS_DIR / exam_id
    if not exam_dir.exists():
        return None

    meta_file = exam_dir / "exam_meta.json"
    if not meta_file.exists():
        return None

    exam_meta = read_json(meta_file)
    question_ids = exam_meta.get("question_ids", {})
    titles = exam_meta.get("question_titles", {})

    module_results = {}
    for section in ("reading", "listening", "writing"):
        if section not in question_ids:
            continue
        for qid in question_ids.get(section, []):
            for attempt_dir in STUDENT_ATTEMPTS_DIR.glob("attempt_*"):
                try:
                    meta = read_json(attempt_dir / "meta.json")
                except Exception:
                    continue
                if meta.get("exam_id") == exam_id and meta.get("question_id") == qid:
                    result_file = GRADING_RESULTS_DIR / attempt_dir.name / "result.json"
                    if not result_file.exists():
                        score_attempt(attempt_dir.name)
                    if result_file.exists():
                        result = read_json(result_file)
                        obj = result.get("objective") or {}
                        wri = result.get("writing") or {}
                        module_results[section] = {
                            "attempt_id": attempt_dir.name,
                            "tdn": obj.get("tdn") or wri.get("tdn") or 0,
                            "tdn_label": obj.get("tdn_label") or wri.get("tdn_label") or "—",
                            "total_correct": obj.get("total_correct"),
                            "total_questions": obj.get("total_questions"),
                            "dimensionen": wri.get("dimensionen"),
                        }
                    break

    student_id = ""
    student_name = ""
    submitted_at = ""
    for adir in STUDENT_ATTEMPTS_DIR.glob("attempt_*"):
        try:
            m = read_json(adir / "meta.json")
        except Exception:
            continue
        if m.get("exam_id") == exam_id:
            student_id = m.get("student_id", "")
            student_name = m.get("student_name", "")
            submitted_at = m.get("submitted_at", "")
            break

    return {
        "exam_id": exam_id,
        "created_at": exam_meta.get("created_at", ""),
        "student_id": student_id,
        "student_name": student_name,
        "submitted_at": submitted_at,
        "module_order": exam_meta.get("module_order", ["reading", "listening", "writing", "speaking"]),
        "modules": module_results,
        "titles": titles,
    }
