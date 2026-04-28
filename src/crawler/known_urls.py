"""Load curated direct-crawl law URLs from configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union


DEFAULT_KNOWN_URLS_PATH = Path("config/known_urls.toml")


@dataclass(frozen=True)
class KnownLawUrl:
    """A public URL seed for a known law or regulation."""

    name: str
    url: str
    source: str = "未知来源"
    aliases: tuple[str, ...] = ()

    @property
    def match_names(self) -> tuple[str, ...]:
        """Names that can be used for exact or fuzzy matching."""
        return (self.name, *self.aliases)


def load_known_law_urls(path: Union[str, Path] = DEFAULT_KNOWN_URLS_PATH) -> list[KnownLawUrl]:
    """Load known law URLs from a TOML file."""
    config_path = Path(path)
    if not config_path.exists():
        return []

    data = _load_toml(config_path)
    records = []
    for item in data.get("laws", []):
        record = _build_record(item)
        if record:
            records.append(record)
    return records


def known_urls_as_mapping(path: Union[str, Path] = DEFAULT_KNOWN_URLS_PATH) -> dict[str, str]:
    """Return a name-to-URL mapping for display and compatibility."""
    mapping = {}
    for record in load_known_law_urls(path):
        mapping[record.name] = record.url
        for alias in record.aliases:
            mapping[alias] = record.url
    return mapping


def _build_record(item: dict[str, Any]) -> Optional[KnownLawUrl]:
    name = str(item.get("name", "")).strip()
    url = str(item.get("url", "")).strip()
    if not name or not url:
        return None

    aliases = item.get("aliases", [])
    if isinstance(aliases, str):
        aliases = [aliases]

    return KnownLawUrl(
        name=name,
        url=url,
        source=str(item.get("source", "未知来源")).strip() or "未知来源",
        aliases=tuple(str(alias).strip() for alias in aliases if str(alias).strip()),
    )


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib

        with path.open("rb") as file:
            return tomllib.load(file)
    except ModuleNotFoundError:
        import toml

        return toml.load(path)
