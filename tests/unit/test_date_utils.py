import unittest

from src.utils.date_utils import normalize_date_format, normalize_datetime_format


class DateUtilsTest(unittest.TestCase):
    def test_normalize_chinese_date(self):
        self.assertEqual(normalize_date_format("2013年2月4日"), "2013-02-04")

    def test_normalize_fullwidth_date(self):
        self.assertEqual(normalize_date_format("２０２５－０５－２９"), "2025-05-29")

    def test_normalize_datetime_keeps_seconds(self):
        self.assertEqual(
            normalize_datetime_format("2025-06-23T16:25:10.215903"),
            "2025-06-23 16:25:10",
        )

    def test_unknown_date_is_preserved(self):
        self.assertEqual(normalize_date_format("自发布之日起施行"), "自发布之日起施行")


if __name__ == "__main__":
    unittest.main()
