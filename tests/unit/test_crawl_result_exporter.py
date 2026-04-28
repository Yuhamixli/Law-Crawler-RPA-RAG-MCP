import unittest

from src.report.crawl_result_exporter import build_result_tables, calculate_source_stats


class CrawlResultExporterTest(unittest.TestCase):
    def test_build_result_tables_normalizes_successful_row(self):
        results = [
            {
                "target_name": "中华人民共和国民法典",
                "name": "中华人民共和国民法典",
                "number": "中华人民共和国主席令第四十五号",
                "publish_date": "2020年5月28日",
                "valid_from": "2021-01-01 00:00:00",
                "office": "全国人民代表大会",
                "level": "法律",
                "status": "现行有效",
                "source": "search_api",
                "source_url": "https://flk.npc.gov.cn/detail.html",
                "crawl_time": "2025-06-23T16:25:10.215903",
            }
        ]

        excel_rows, detailed_rows = build_result_tables(results, ["中华人民共和国民法典"])

        self.assertEqual(excel_rows[0]["发布日期"], "2020-05-28")
        self.assertEqual(excel_rows[0]["实施日期"], "2021-01-01")
        self.assertEqual(excel_rows[0]["来源渠道"], "国家法律法规数据库")
        self.assertEqual(excel_rows[0]["采集时间"], "2025-06-23 16:25:10")
        self.assertEqual(detailed_rows[0]["采集状态"], "成功")

    def test_build_result_tables_keeps_missing_targets(self):
        excel_rows, detailed_rows = build_result_tables([], ["不存在的法规"])

        self.assertEqual(excel_rows[0]["目标法规"], "不存在的法规")
        self.assertEqual(excel_rows[0]["采集状态"], "未找到")
        self.assertEqual(detailed_rows[0]["采集状态"], "未找到")

    def test_calculate_source_stats_counts_success_only(self):
        source_stats = calculate_source_stats(
            [
                {"采集状态": "成功", "来源渠道": "国家法律法规数据库"},
                {"采集状态": "成功", "来源渠道": "国家法律法规数据库"},
                {"采集状态": "未找到", "来源渠道": "未知"},
            ]
        )

        self.assertEqual(source_stats, {"国家法律法规数据库": 2})


if __name__ == "__main__":
    unittest.main()

