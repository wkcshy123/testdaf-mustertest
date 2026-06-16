"""Persist and retrieve student attempt records."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from shared.file_io.atomic_json import read_json, write_json_atomic


class AttemptStore:
    """Manage student_attempts/ directories with atomic JSON writes."""

    def __init__(self, root: Path):
        self.root = root

    def save(
        self,
        *,
        question_id: str,
        section: str,
        task_type: str,
        answer_mode: str,
        title: str,
        answers: dict,
        time_limit_seconds: int,
        elapsed_seconds: int,
        timed_out: bool,
    ) -> str:
        """Write an attempt directory and return its id."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_qid = question_id[-8:] if len(question_id) > 8 else question_id
        attempt_id = f"attempt_{timestamp}_{short_qid}"
        attempt_dir = self.root / attempt_id
        attempt_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "attempt_id": attempt_id,
            "question_id": question_id,
            "section": section,
            "task_type": task_type,
            "answer_mode": answer_mode,
            "title": title,
            "submitted_at": datetime.now().isoformat(timespec="seconds"),
            "time_limit_seconds": time_limit_seconds,
            "elapsed_seconds": elapsed_seconds,
            "timed_out": timed_out,
        }
        write_json_atomic(attempt_dir / "meta.json", meta)
        write_json_atomic(attempt_dir / "answers.json", answers)
        return attempt_id

    def list_attempts(self) -> list[dict]:
        """Return all attempt metas, newest first."""
        if not self.root.exists():
            return []
        metas = []
        for attempt_dir in sorted(self.root.glob("attempt_*"), reverse=True):
            meta_path = attempt_dir / "meta.json"
            if not meta_path.exists():
                continue
            meta = read_json(meta_path)
            if isinstance(meta, dict):
                meta["attempt_id"] = attempt_dir.name
                metas.append(meta)
        return metas

    def load_attempt(self, attempt_id: str) -> dict | None:
        """Load a single attempt's meta and answers."""
        attempt_dir = self.root / attempt_id
        meta_path = attempt_dir / "meta.json"
        if not meta_path.exists():
            return None
        meta = read_json(meta_path)
        answers_path = attempt_dir / "answers.json"
        answers = read_json(answers_path) if answers_path.exists() else {}
        return {"meta": meta, "answers": answers}
