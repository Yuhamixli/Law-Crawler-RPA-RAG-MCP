"""Catalog services for curated law URL seeds."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.crawler.known_urls import KnownLawUrl, load_known_law_urls


@dataclass(frozen=True)
class CatalogValidationIssue:
    """A validation issue found in the known URL catalog."""

    name: str
    issue: str


@dataclass(frozen=True)
class CatalogValidationResult:
    """Validation result for the known URL catalog."""

    total: int
    issues: tuple[CatalogValidationIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


class CatalogService:
    """Read and validate curated law URL seeds."""

    def __init__(self, known_urls_path: Optional[str | Path] = None):
        self.known_urls_path = known_urls_path

    def list_known_urls(self) -> list[KnownLawUrl]:
        """Return configured known law URLs."""
        if self.known_urls_path:
            return load_known_law_urls(self.known_urls_path)
        return load_known_law_urls()

    def validate_known_urls(self) -> CatalogValidationResult:
        """Validate known URL seed metadata without making network requests."""
        records = self.list_known_urls()
        issues = []
        seen_names = set()
        seen_urls = set()

        for record in records:
            if record.name in seen_names:
                issues.append(CatalogValidationIssue(record.name, "duplicate law name"))
            seen_names.add(record.name)

            if record.url in seen_urls:
                issues.append(CatalogValidationIssue(record.name, "duplicate URL"))
            seen_urls.add(record.url)

            if not record.url.startswith(("https://", "http://")):
                issues.append(CatalogValidationIssue(record.name, "URL must start with http:// or https://"))

            for alias in record.aliases:
                if alias == record.name:
                    issues.append(CatalogValidationIssue(record.name, "alias duplicates canonical name"))

        return CatalogValidationResult(total=len(records), issues=tuple(issues))

