"""Persist and look up student accounts.

Mirrors the file-based, atomic-write style of ``AttemptStore`` /
``ExamStore`` in the student answering system. Accounts live in a single
JSON map keyed by ``student_id`` so lookups are cheap and writes are
atomic.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path

from shared.file_io.atomic_json import read_json, write_json_atomic

from student_account_platform.auth import hash_password, verify_password


class AccountStore:
    """Manage ``students/accounts.json`` with atomic writes."""

    def __init__(self, students_dir: Path):
        self.dir = students_dir
        self.path = students_dir / "accounts.json"

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        data = read_json(self.path)
        return data if isinstance(data, dict) else {}

    def _save(self, accounts: dict) -> None:
        write_json_atomic(self.path, accounts)

    @staticmethod
    def _new_student_id() -> str:
        return f"stu_{secrets.token_hex(4)}"

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def register(self, *, username: str, password: str, name: str) -> str:
        """Create a new account and return its ``student_id``.

        Raises ``ValueError`` on a duplicate username or empty fields.
        """
        username = username.strip()
        name = name.strip()
        if not username or not password or not name:
            raise ValueError("用户名、姓名和密码都不能为空。")
        if len(password) < 6:
            raise ValueError("密码至少需要 6 个字符。")

        accounts = self._load()
        # usernames are case-insensitive unique
        for record in accounts.values():
            if record.get("username", "").lower() == username.lower():
                raise ValueError("该用户名已被注册。")

        student_id = self._new_student_id()
        accounts[student_id] = {
            "student_id": student_id,
            "name": name,
            "username": username,
            "password_hash": hash_password(password),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._save(accounts)
        return student_id

    def find_by_username(self, username: str) -> dict | None:
        """Return the account record matching ``username`` (case-insensitive)."""
        if not username:
            return None
        accounts = self._load()
        target = username.strip().lower()
        for record in accounts.values():
            if record.get("username", "").lower() == target:
                return record
        return None

    def find_by_id(self, student_id: str) -> dict | None:
        """Return the account record matching ``student_id``."""
        if not student_id:
            return None
        return self._load().get(student_id)

    def verify(self, username: str, password: str) -> dict | None:
        """Return the account if the username exists and password matches."""
        record = self.find_by_username(username)
        if not record:
            return None
        if not verify_password(password, record.get("password_hash", "")):
            return None
        return record

    def list_accounts(self) -> list[dict]:
        """Return all account records (without password hashes), newest first."""
        records = []
        for record in self._load().values():
            public = {k: v for k, v in record.items() if k != "password_hash"}
            records.append(public)
        records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return records
