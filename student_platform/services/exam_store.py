"""Persist and retrieve full exam sessions."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from shared.file_io.atomic_json import read_json, write_json_atomic


# Module time limits in seconds (configurable via env vars).
MODULE_TIME_LIMITS = {
    "reading": 3600,      # 60 min
    "listening": 2400,    # 40 min
    "writing": 3600,      # 60 min
    "speaking": 0,        # unlimited
}

MODULE_LABELS = {
    "reading": "阅读 Leseverstehen",
    "listening": "听力 Hörverstehen",
    "writing": "写作 Schriftlicher Ausdruck",
    "speaking": "口语 Mündlicher Ausdruck",
}


class ExamStore:
    """Manage exam session state under student_attempts/exam_*/.

    Each exam is a directory containing:
      - exam_meta.json: session state (questions, current module, etc.)
      - Per-question attempts are saved as separate attempt_* dirs by
        AttemptStore, linked via the exam_id field in their meta.
    """

    def __init__(self, root: Path):
        self.root = root

    def create_exam(self, questions: dict[str, list[dict]]) -> str:
        """Create an exam session directory and return the exam_id."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        exam_id = f"exam_{timestamp}"
        exam_dir = self.root / exam_id
        exam_dir.mkdir(parents=True, exist_ok=True)

        # Flatten questions into a simple id list per module.
        question_ids: dict[str, list[str]] = {}
        question_titles: dict[str, list[str]] = {}
        for section, qs in questions.items():
            question_ids[section] = [q["id"] for q in qs]
            question_titles[section] = [q.get("title", "") for q in qs]

        meta = {
            "exam_id": exam_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "question_ids": question_ids,
            "question_titles": question_titles,
            "module_order": ["reading", "listening", "writing", "speaking"],
            "current_module": "reading",
            "status": "in_progress",
        }
        write_json_atomic(exam_dir / "exam_meta.json", meta)
        return exam_id

    def load_exam(self, exam_id: str) -> dict | None:
        """Load exam session state."""
        meta_path = self.root / exam_id / "exam_meta.json"
        if not meta_path.exists():
            return None
        return read_json(meta_path)

    def update_exam(self, exam_id: str, **fields) -> None:
        """Update one or more fields in the exam meta."""
        meta_path = self.root / exam_id / "exam_meta.json"
        meta = read_json(meta_path)
        meta.update(fields)
        write_json_atomic(meta_path, meta)

    def list_exams(self) -> list[dict]:
        """Return all exam metas, newest first."""
        if not self.root.exists():
            return []
        metas = []
        for exam_dir in sorted(self.root.glob("exam_*"), reverse=True):
            meta_path = exam_dir / "exam_meta.json"
            if not meta_path.exists():
                continue
            meta = read_json(meta_path)
            if isinstance(meta, dict):
                metas.append(meta)
        return metas
