import os
import tempfile
import textwrap
import unittest

try:
    from config.settings import Settings
except ImportError as error:
    Settings = None
    IMPORT_ERROR = error
else:
    IMPORT_ERROR = None


@unittest.skipIf(Settings is None, f"settings dependencies are unavailable: {IMPORT_ERROR}")
class SettingsTest(unittest.TestCase):
    def test_load_from_toml_applies_nested_sections(self):
        content = textwrap.dedent(
            """
            project_name = "测试项目"
            debug = true

            [crawler]
            max_concurrent = 7
            enable_selenium_search = false
            enable_optimized_selenium = false

            [database]
            url = "sqlite:///tmp/test.db"

            [data_sources.national]
            name = "测试国家库"
            base_url = "https://example.test"
            enabled = false
            """
        )

        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as file:
            file.write(content)
            path = file.name

        try:
            settings = Settings.load_from_toml(path)
        finally:
            os.unlink(path)

        self.assertEqual(settings.project_name, "测试项目")
        self.assertTrue(settings.debug)
        self.assertEqual(settings.crawler.max_concurrent, 7)
        self.assertFalse(settings.crawler.enable_selenium_search)
        self.assertFalse(settings.crawler.enable_optimized_selenium)
        self.assertEqual(settings.database.url, "sqlite:///tmp/test.db")
        self.assertEqual(settings.data_sources.national_name, "测试国家库")
        self.assertEqual(settings.data_sources.national_base_url, "https://example.test")
        self.assertFalse(settings.data_sources.national_enabled)


if __name__ == "__main__":
    unittest.main()

