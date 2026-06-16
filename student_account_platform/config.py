"""Student account system configuration."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Shared across the account system (writer) and the student answering
# system (reader). Both services read/write through this directory.
STUDENTS_DIR = PROJECT_ROOT / "students"

# Session cookie name shared with the student answering system (8001).
SESSION_COOKIE = "student_session"

# Session time-to-live in seconds (default: 7 days).
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60

# Student answering system entry point (for profile navigation).
STUDENT_SYSTEM_URL = "http://127.0.0.1:8001/"
