import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.responses import FileResponse, RedirectResponse

from scoring_platform import web
from shared.file_io.atomic_json import write_json_atomic


class SpeakingAudioRouteTest(unittest.TestCase):
    def test_teacher_can_access_speaking_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            attempts_dir = Path(temp_dir)
            attempt_dir = attempts_dir / "attempt_test"
            attempt_dir.mkdir()
            (attempt_dir / "response.webm").write_bytes(b"audio")
            write_json_atomic(
                attempt_dir / "meta.json",
                {
                    "section": "speaking",
                    "student_id": "stu_1",
                    "audio_file": "response.webm",
                },
            )
            with patch.object(web, "STUDENT_ATTEMPTS_DIR", attempts_dir):
                with patch.object(web, "get_user", return_value={"student_id": "_teacher", "role": "teacher"}):
                    response = web.speaking_audio(SimpleNamespace(), "attempt_test")

            self.assertIsInstance(response, FileResponse)
            self.assertEqual(response.media_type, "audio/webm")

    def test_other_student_cannot_access_speaking_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            attempts_dir = Path(temp_dir)
            attempt_dir = attempts_dir / "attempt_test"
            attempt_dir.mkdir()
            (attempt_dir / "response.webm").write_bytes(b"audio")
            write_json_atomic(
                attempt_dir / "meta.json",
                {
                    "section": "speaking",
                    "student_id": "stu_owner",
                    "audio_file": "response.webm",
                },
            )
            with patch.object(web, "STUDENT_ATTEMPTS_DIR", attempts_dir):
                with patch.object(web, "get_user", return_value={"student_id": "stu_other", "role": "student"}):
                    response = web.speaking_audio(SimpleNamespace(), "attempt_test")

            self.assertIsInstance(response, RedirectResponse)
            self.assertEqual(response.status_code, 303)


if __name__ == "__main__":
    unittest.main()
