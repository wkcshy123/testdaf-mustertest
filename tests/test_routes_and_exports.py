import unittest

from testdaf_platform.services.export_service import safe_filename
from testdaf_platform.web import app


class RoutesAndExportsTest(unittest.TestCase):
    def test_management_routes_are_registered_after_split(self) -> None:
        paths = [getattr(route, "path", "") for route in app.routes]
        self.assertIn("/teacher/manage/trash", paths)
        self.assertIn("/teacher/manage/{section}", paths)
        self.assertIn("/teacher/manage/download/{fmt}", paths)
        self.assertLess(paths.index("/teacher/manage/trash"), paths.index("/teacher/manage/{section}"))

    def test_safe_filename_strips_invalid_chars(self) -> None:
        result = safe_filename('Test: "reading" <Aufgabe>?')
        for ch in (':', '"', '<', '>', '?'):
            self.assertNotIn(ch, result)

    def test_safe_filename_fits_max_len(self) -> None:
        long_title = "A" * 100 + "B" * 100
        result = safe_filename(long_title, max_len=50)
        self.assertLessEqual(len(result), 50)


if __name__ == "__main__":
    unittest.main()
