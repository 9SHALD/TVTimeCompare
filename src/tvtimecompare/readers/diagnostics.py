"""Shared parsing diagnostics for export readers."""

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping
from zipfile import ZipFile

import pandas as pd
from pandas.errors import EmptyDataError, ParserError

from tvtimecompare.models import Show


class SkipReason(StrEnum):
    """Reasons an export row can be excluded from watched-episode data."""

    MALFORMED_CSV_ROW = "malformed CSV row"
    MISSING_REQUIRED_VALUE = "missing required value"
    INVALID_SEASON_NUMBER = "invalid season number"
    INVALID_EPISODE_NUMBER = "invalid episode number"
    EMPTY_NORMALIZED_TITLE = "empty normalized title"
    DUPLICATE_EPISODE = "duplicate episode"


class CsvParseError(ValueError):
    """Raised when a watched-episode CSV cannot be decoded or parsed."""


@dataclass(frozen=True, slots=True)
class ParseDiagnostics:
    """Immutable summary of one watched-episode CSV parsing operation."""

    source_file: str
    rows_read: int
    rows_imported: int
    skipped_by_reason: Mapping[SkipReason, int]

    def __post_init__(self) -> None:
        """Defensively copy skip counts so the diagnostics snapshot is immutable."""
        object.__setattr__(
            self,
            "skipped_by_reason",
            MappingProxyType(dict(self.skipped_by_reason)),
        )

    @property
    def rows_skipped(self) -> int:
        """Return the total number of rows skipped for all recorded reasons."""
        return sum(self.skipped_by_reason.values())

    def reason_summary(self) -> str:
        """Return a concise human-readable breakdown of skipped rows."""
        if not self.skipped_by_reason:
            return "none"
        return ", ".join(
            f"{reason.value}: {count}"
            for reason, count in sorted(self.skipped_by_reason.items())
        )


@dataclass(frozen=True, slots=True)
class ExportReadResult:
    """Shows and parsing diagnostics returned by a single export reader."""

    shows: dict[str, Show]
    diagnostics: ParseDiagnostics


class _DiagnosticsCollector:
    """Mutable accumulator used only while one source file is parsed."""

    def __init__(self, source_file: str) -> None:
        self.source_file = source_file
        self.rows_read = 0
        self.rows_imported = 0
        self._skipped_by_reason: Counter[SkipReason] = Counter()

    def record_read_rows(self, count: int) -> None:
        """Record rows yielded by the CSV parser."""
        self.rows_read += count

    def record_skip(self, reason: SkipReason) -> None:
        """Record why a row already read by pandas was skipped."""
        self._skipped_by_reason[reason] += 1

    def record_malformed_row(self) -> None:
        """Record one malformed row omitted by the CSV parser."""
        self.rows_read += 1
        self._skipped_by_reason[SkipReason.MALFORMED_CSV_ROW] += 1

    def record_import(self) -> None:
        """Record one imported watched episode."""
        self.rows_imported += 1

    def build(self) -> ParseDiagnostics:
        """Create an immutable diagnostics snapshot."""
        return ParseDiagnostics(
            source_file=self.source_file,
            rows_read=self.rows_read,
            rows_imported=self.rows_imported,
            skipped_by_reason=self._skipped_by_reason,
        )


def read_csv_with_diagnostics(
    archive: ZipFile,
    filename: str,
    collector: _DiagnosticsCollector,
) -> pd.DataFrame:
    """Read one UTF-8 CSV while counting structurally malformed rows."""

    def skip_malformed_row(_: list[str]) -> list[str] | None:
        collector.record_malformed_row()
        return None

    try:
        with archive.open(filename) as csv_file:
            records = pd.read_csv(
                csv_file,
                dtype="string",
                encoding="utf-8-sig",
                engine="python",
                on_bad_lines=skip_malformed_row,
            )
    except (EmptyDataError, ParserError, UnicodeDecodeError) as error:
        message = f"{filename} could not be parsed as UTF-8 CSV."
        raise CsvParseError(message) from error
    collector.record_read_rows(len(records))
    return records


def new_diagnostics_collector(source_file: str) -> _DiagnosticsCollector:
    """Create a collector for one source CSV file."""
    return _DiagnosticsCollector(source_file)
