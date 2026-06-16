"""Persist and validate login sessions.

Each session is a small JSON file under ``students/sessions/<token>.json``.
The answering system (8001) reads the same files to resolve the cookie
back to a ``student_id``, so writing logic stays centralized here.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from shared.file_io.atomic_json import read_json, write_json_atomic


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SessionStore:
    """Manage ``students/sessions/*.json`` session files."""

    def __init__(self, students_dir: Path, ttl_seconds: int):
        self.dir = students_dir / "sessions"
        self.ttl_seconds = ttl_seconds

    # ------------------------------------------------------------------
    def create(self, student_id: str) -> str:
        """Create a session for ``student_id`` and return its token."""
        self.dir.mkdir(parents=True, exist_ok=True)
        token = secrets.token_urlsafe(32)
        created = _now()
        expires = created + timedelta(seconds=self.ttl_seconds)
        payload = {
            "token": token,
            "student_id": student_id,
            "created_at": created.isoformat(timespec="seconds"),
            "expires_at": expires.isoformat(timespec="seconds"),
        }
        write_json_atomic(self.dir / f"{token}.json", payload)
        return token

    def resolve(self, token: str | None) -> str | None:
        """Return the ``student_id`` for a valid, non-expired ``token``."""
        if not token:
            return None
        path = self.dir / f"{token}.json"
        if not path.exists():
            return None
        payload = read_json(path)
        if not isinstance(payload, dict):
            return None
        expires_at = payload.get("expires_at")
        if not expires_at:
            return None
        try:
            expires_dt = datetime.fromisoformat(expires_at)
        except ValueError:
            return None
        # datetime.fromisoformat may drop tz info on older Pythons; normalize.
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=timezone.utc)
        if _now() > expires_dt:
            # expired: clean up the stale file
            try:
                path.unlink()
            except OSError:
                pass
            return None
        return payload.get("student_id")

    def destroy(self, token: str | None) -> None:
        """Delete the session file for ``token`` if it exists."""
        if not token:
            return
        path = self.dir / f"{token}.json"
        try:
            path.unlink()
        except FileNotFoundError:
            pass
