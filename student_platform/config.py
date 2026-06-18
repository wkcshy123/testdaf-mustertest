"""Student system configuration."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUESTION_BANK_DIR = PROJECT_ROOT / "question_bank"
STUDENT_ATTEMPTS_DIR = PROJECT_ROOT / "student_attempts"

# Shared with the account system (8002). The answering system only reads
# session files written there to resolve the cookie back to a student id.
STUDENTS_DIR = PROJECT_ROOT / "students"
SESSION_COOKIE = "student_session"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60

# Account system entry point (for login/register navigation).
ACCOUNT_SYSTEM_URL = "http://127.0.0.1:8002/"

# Scoring system entry point (for score detail navigation).
SCORING_SYSTEM_URL = "http://127.0.0.1:8003/"
