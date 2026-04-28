import os
import tempfile
import textwrap
import unittest
import importlib.util

try:
    from src.crawler.known_urls import known_urls_as_mapping, load_known_law_urls
except ImportError as error:
    load_known_law_urls = None
    known_urls_as_mapping = None
    IMPORT_ERROR = error
else:
    IMPORT_ERROR = None

try:
    from src.service.catalog_service import CatalogService
except ImportError as error:
    CatalogService = None
    SERVICE_IMPORT_ERROR = error
else:
    SERVICE_IMPORT_ERROR = None


@unittest.skipIf(load_known_law_urls is None, f"known URL dependencies are unavailable: {IMPORT_ERROR}")
class KnownUrlsTest(unittest.TestCase):
    @unittest.skipIf(
        importlib.util.find_spec("tomllib") is None and importlib.util.find_spec("toml") is None,
        "TOML parser is unavailable",
    )
    def test_load_known_law_urls(self):
        content = textwrap.dedent(
            """
            [[laws]]
            name = "示例法规"
            url = "https://www.gov.cn/example.htm"
            source = "中国政府网"
            aliases = ["示例别名"]
            """
        )

        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as file:
            file.write(content)
            path = file.name

        try:
            records = load_known_law_urls(path)
            mapping = known_urls_as_mapping(path)
        finally:
            os.unlink(path)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].name, "示例法规")
        self.assertEqual(records[0].aliases, ("示例别名",))
        self.assertEqual(mapping["示例法规"], "https://www.gov.cn/example.htm")
        self.assertEqual(mapping["示例别名"], "https://www.gov.cn/example.htm")


@unittest.skipIf(CatalogService is None, f"catalog service dependencies are unavailable: {SERVICE_IMPORT_ERROR}")
class CatalogServiceTest(unittest.TestCase):
    @unittest.skipIf(
        importlib.util.find_spec("tomllib") is None and importlib.util.find_spec("toml") is None,
        "TOML parser is unavailable",
    )
    def test_validate_known_urls_reports_duplicate_alias(self):
        content = textwrap.dedent(
            """
            [[laws]]
            name = "示例法规"
            url = "https://www.gov.cn/example.htm"
            source = "中国政府网"
            aliases = ["示例法规"]
            """
        )

        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as file:
            file.write(content)
            path = file.name

        try:
            result = CatalogService(path).validate_known_urls()
        finally:
            os.unlink(path)

        self.assertFalse(result.ok)
        self.assertEqual(result.issues[0].issue, "alias duplicates canonical name")


if __name__ == "__main__":
    unittest.main()
