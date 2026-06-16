"""Read-only student identity resolution for the answering system.

The answering system (8001) never creates accounts or sessions; it only
reads the session files written by the account system (8002) under the
shared ``students/sessions/`` directory. This keeps the account as the
single writer, consistent with the project's file-boundary architecture.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from shared.file_io.atomic_json import read_json


class StudentIdentityService:
    """Resolve a session cookie token back to a student record."""

    def __init__(self, students_dir: Path):
        self.accounts_path = students_dir / "accounts.json"
        self.sessions_dir = students_dir / "sessions"

    def resolve(self, token: str | None) -> dict | None:
        """Return ``{student_id, name}`` for a valid token, else ``None``.

        Returns only the minimal fields the answering system needs; it
        must not see password hashes.
        """
        if not token:
            return None
        session_path = self.sessions_dir / f"{token}.json"
        if not session_path.exists():
            return None
        session = read_json(session_path)
        if not isinstance(session, dict):
            return None

        expires_at = session.get("expires_at")
        if expires_at and self._is_expired(expires_at):
            return None

        student_id = session.get("student_id")
        if not student_id or not self.accounts_path.exists():
            return None

        accounts = read_json(self.accounts_path)
        if not isinstance(accounts, dict):
            return None
        record = accounts.get(student_id)
        if not isinstance(record, dict):
            return None
        return {"student_id": student_id, "name": record.get("name", "")}

    @staticmethod
    def _is_expired(expires_at: str) -> bool:
        try:
            expires_dt = datetime.fromisoformat(expires_at)
        except ValueError:
            return True
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > expires_dt
