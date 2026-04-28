"""Date and datetime normalization helpers."""

import re
from datetime import datetime


FULLWIDTH_TO_HALFWIDTH = str.maketrans(
    {
        "０": "0",
        "１": "1",
        "２": "2",
        "３": "3",
        "４": "4",
        "５": "5",
        "６": "6",
        "７": "7",
        "８": "8",
        "９": "9",
        "－": "-",
        "—": "-",
        "–": "-",
    }
)


def normalize_date_format(date_str: str) -> str:
    """
    Normalize common Chinese and numeric date formats to ``YYYY-MM-DD``.

    Unknown formats are returned unchanged so crawled source data is not lost.
    """
    if not date_str or str(date_str).strip() == "":
        return ""

    date_str = str(date_str).strip().translate(FULLWIDTH_TO_HALFWIDTH)

    patterns = [
        r"^(\d{4})年(\d{1,2})月(\d{1,2})日",
        r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})",
    ]
    for pattern in patterns:
        match = re.match(pattern, date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    timestamp_match = re.match(r"^(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}", date_str)
    if timestamp_match:
        return timestamp_match.group(1)

    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str

    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"]:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return date_str


def normalize_datetime_format(datetime_str: str) -> str:
    """Normalize datetime strings to ``YYYY-MM-DD HH:MM:SS``."""
    if not datetime_str or str(datetime_str).strip() == "":
        return ""

    datetime_str = str(datetime_str).strip()

    if "T" in datetime_str:
        try:
            parsed = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", datetime_str):
        return datetime_str

    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"]:
        try:
            parsed = datetime.strptime(datetime_str, fmt)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

