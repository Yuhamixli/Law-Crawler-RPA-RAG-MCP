"""Export crawler results to JSON and Excel ledgers."""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.utils.date_utils import normalize_date_format, normalize_datetime_format


@dataclass(frozen=True)
class CrawlExportSummary:
    """Paths and basic statistics produced by a crawl export."""

    json_file: str
    detailed_json_file: str
    excel_file: str
    source_stats: dict[str, int]


def build_result_tables(
    results: list[dict[str, Any]],
    target_laws: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build simplified ledger rows and detailed rows from crawler results."""
    results_map = _build_results_map(results, target_laws)
    excel_results = []
    detailed_results = []

    for index, target_law in enumerate(target_laws):
        if target_law in results_map:
            law_data = results_map[target_law]
            source_channel = get_source_channel(law_data)

            excel_data = {
                "序号": index + 1,
                "目标法规": target_law,
                "搜索关键词": law_data.get("search_keyword", target_law),
                "法规名称": law_data.get("name", ""),
                "文号": law_data.get("number", "") or law_data.get("document_number", ""),
                "发布日期": normalize_date_format(law_data.get("publish_date", "")),
                "实施日期": normalize_date_format(law_data.get("valid_from", "")),
                "失效日期": normalize_date_format(law_data.get("valid_to", "")),
                "发布机关": law_data.get("office", "") or law_data.get("issuing_authority", ""),
                "法规级别": law_data.get("level", "") or law_data.get("law_level", ""),
                "状态": law_data.get("status", ""),
                "来源渠道": source_channel,
                "来源链接": law_data.get("source_url", ""),
                "采集时间": normalize_datetime_format(
                    law_data.get("crawl_time", datetime.now().isoformat())
                ),
                "采集状态": "成功",
            }

            detailed_data = {
                "序号": index + 1,
                "采集状态": "成功",
                "来源渠道": source_channel,
                **law_data,
            }
        else:
            excel_data = build_missing_row(index, target_law)
            detailed_data = {
                "序号": index + 1,
                "target_name": target_law,
                "采集状态": "未找到",
                "来源渠道": "",
                "采集时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        excel_results.append(excel_data)
        detailed_results.append(detailed_data)

    return excel_results, detailed_results


def save_crawl_results(
    results: list[dict[str, Any]],
    target_laws: list[str],
    output_dir: str = "data",
) -> CrawlExportSummary:
    """Save crawl results to simplified JSON, detailed JSON, and Excel."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    os.makedirs(f"{output_dir}/raw/json", exist_ok=True)
    os.makedirs(f"{output_dir}/raw/detailed", exist_ok=True)
    os.makedirs(f"{output_dir}/ledgers", exist_ok=True)

    excel_results, detailed_results = build_result_tables(results, target_laws)

    json_file = f"{output_dir}/raw/json/search_crawl_{timestamp}.json"
    with open(json_file, "w", encoding="utf-8") as file:
        json.dump(excel_results, file, ensure_ascii=False, indent=2)

    detailed_json_file = f"{output_dir}/raw/detailed/search_crawl_detailed_{timestamp}.json"
    with open(detailed_json_file, "w", encoding="utf-8") as file:
        json.dump(detailed_results, file, ensure_ascii=False, indent=2)

    excel_file = f"{output_dir}/ledgers/search_crawl_{timestamp}.xlsx"
    write_excel_ledger(excel_results, excel_file)

    return CrawlExportSummary(
        json_file=json_file,
        detailed_json_file=detailed_json_file,
        excel_file=excel_file,
        source_stats=calculate_source_stats(excel_results),
    )


def write_excel_ledger(excel_results: list[dict[str, Any]], excel_file: str) -> None:
    """Write ledger rows to Excel and convert source URLs to hyperlinks."""
    import pandas as pd

    dataframe = pd.DataFrame(excel_results)

    with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
        dataframe.to_excel(writer, sheet_name="法规采集结果", index=False)
        worksheet = writer.sheets["法规采集结果"]

        for row_index, row in enumerate(dataframe.iterrows(), start=2):
            url = row[1]["来源链接"]
            if url and row[1]["采集状态"] == "成功":
                worksheet.cell(row=row_index, column=13).hyperlink = url
                worksheet.cell(row=row_index, column=13).value = "点击查看"


def calculate_source_stats(excel_results: list[dict[str, Any]]) -> dict[str, int]:
    """Count successful records by source channel."""
    source_stats: dict[str, int] = {}
    for result in excel_results:
        if result.get("采集状态") != "成功":
            continue
        channel = result.get("来源渠道", "未知")
        source_stats[channel] = source_stats.get(channel, 0) + 1
    return source_stats


def get_source_channel(law_data: dict[str, Any]) -> str:
    """Infer a human-readable source channel from result metadata."""
    source = law_data.get("source", "unknown")
    source_url = law_data.get("source_url", "")

    if source == "search_api":
        return "国家法律法规数据库"
    if source == "selenium_gov_web":
        return "中国政府网(www.gov.cn)"
    if source == "gov_web":
        return "中国政府网"
    if source in ["中国政府网-直接访问", "直接URL访问"]:
        return "中国政府网-直接访问"
    if source in ["搜索引擎(政府网)", "DuckDuckGo", "Bing"]:
        return "搜索引擎(政府网)"

    if "flk.npc.gov.cn" in source_url:
        return "国家法律法规数据库"
    if "gov.cn" in source_url:
        return "搜索引擎(政府网)"
    if source_url:
        return "其他政府网站"
    return "未知来源"


def build_missing_row(index: int, target_law: str) -> dict[str, Any]:
    """Build a placeholder row for an unfound law."""
    return {
        "序号": index + 1,
        "目标法规": target_law,
        "搜索关键词": "",
        "法规名称": "",
        "文号": "",
        "发布日期": "",
        "实施日期": "",
        "失效日期": "",
        "发布机关": "",
        "法规级别": "",
        "状态": "",
        "来源渠道": "",
        "来源链接": "",
        "采集时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "采集状态": "未找到",
    }


def _build_results_map(
    results: list[dict[str, Any]],
    target_laws: list[str],
) -> dict[str, dict[str, Any]]:
    """Map target and actual law names to result records."""
    results_map = {}

    for result in results:
        if result.get("success") is False:
            continue

        target_name = result.get("target_name")
        actual_name = result.get("name")

        if target_name:
            results_map[target_name] = result

        if actual_name:
            results_map[actual_name] = result

            for target_law in target_laws:
                is_revision_target = (
                    "修订" in target_law or "修正" in target_law or "（" in target_law
                )
                if actual_name in target_law and is_revision_target:
                    results_map[target_law] = result
                    break

    return results_map
