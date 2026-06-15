import unittest

from testdaf_platform.services.export_service import _export_filename
from testdaf_platform.web import app


class RoutesAndExportsTest(unittest.TestCase):
    def test_management_routes_are_registered_after_split(self) -> None:
        paths = [getattr(route, "path", "") for route in app.routes]

        self.assertIn("/teacher/manage/trash", paths)
        self.assertIn("/teacher/manage/{section}", paths)
        self.assertIn("/teacher/manage/download/{fmt}", paths)
        self.assertNotIn("/downloads", paths)
        self.assertLess(paths.index("/teacher/manage/trash"), paths.index("/teacher/manage/{section}"))

    def test_export_filename_is_unique_and_keeps_question_id(self) -> None:
        first = _export_filename("Same Title", "docx", "q_20260101_abcdef")
        second = _export_filename("Same Title", "docx", "q_20260101_abcdef")

        self.assertNotEqual(first, second)
        self.assertTrue(first.endswith(".docx"))
        self.assertIn("q_20260101_abcdef", first)


if __name__ == "__main__":
    unittest.main()
