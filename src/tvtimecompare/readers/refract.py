"""Reader for watched episodes in Refract export archives."""

from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pandas as pd

from tvtimecompare.models import Episode, Show
from tvtimecompare.readers.diagnostics import (
    CsvParseError,
    ExportReadResult,
    SkipReason,
    _DiagnosticsCollector,
    new_diagnostics_collector,
    read_csv_with_diagnostics,
)
from tvtimecompare.utils import normalize_title

_EPISODES_FILENAME = "episodes.csv"
_REQUIRED_COLUMNS = {"ShowTitle", "ShowOriginalTitle", "Season", "Episode"}


class RefractExportError(ValueError):
    """Raised when a ZIP archive cannot be read as a Refract export."""


def read_refract_export(export_path: Path) -> ExportReadResult:
    """Read watched episodes from a Refract export ZIP archive.

    The Refract sample has no stable show ID. Shows are therefore keyed by the
    normalized ``ShowTitle`` when available, falling back to
    ``ShowOriginalTitle``.
    """
    return RefractReader(export_path).read()


class RefractReader:
    """Read watched television episodes from one Refract export ZIP archive."""

    def __init__(self, export_path: Path) -> None:
        self.export_path = export_path

    def read(self) -> ExportReadResult:
        """Return parsed shows and diagnostics for ``episodes.csv``."""
        collector = new_diagnostics_collector(_EPISODES_FILENAME)
        try:
            with ZipFile(self.export_path) as archive:
                if _EPISODES_FILENAME not in archive.namelist():
                    raise RefractExportError(
                        f"Refract export does not contain {_EPISODES_FILENAME}."
                    )
                records = read_csv_with_diagnostics(
                    archive, _EPISODES_FILENAME, collector
                )
        except FileNotFoundError as error:
            message = f"Refract export was not found: {self.export_path}"
            raise RefractExportError(message) from error
        except BadZipFile as error:
            message = f"Refract export is not a valid ZIP file: {self.export_path}"
            raise RefractExportError(message) from error
        except CsvParseError as error:
            raise RefractExportError(str(error)) from error

        missing_columns = _REQUIRED_COLUMNS.difference(records.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise RefractExportError(
                f"{_EPISODES_FILENAME} is missing required columns: {missing}."
            )
        return _build_shows(records, collector)


def _build_shows(
    records: pd.DataFrame, collector: _DiagnosticsCollector
) -> ExportReadResult:
    shows: dict[str, Show] = {}
    for row in records.itertuples(index=False):
        title = _title(row.ShowTitle, row.ShowOriginalTitle)
        season = _to_episode_number(row.Season)
        episode = _to_episode_number(row.Episode)
        if title is None:
            collector.record_skip(SkipReason.MISSING_REQUIRED_VALUE)
            continue
        if season is None:
            collector.record_skip(SkipReason.INVALID_SEASON_NUMBER)
            continue
        if episode is None:
            collector.record_skip(SkipReason.INVALID_EPISODE_NUMBER)
            continue
        normalized_title = normalize_title(title)
        if not normalized_title:
            collector.record_skip(SkipReason.EMPTY_NORMALIZED_TITLE)
            continue
        show = shows.setdefault(
            normalized_title,
            Show(
                display_title=title,
                normalized_title=normalized_title,
                source="refract",
            ),
        )
        if show.add_episode(Episode(season, episode)):
            collector.record_import()
        else:
            collector.record_skip(SkipReason.DUPLICATE_EPISODE)
    return ExportReadResult(shows=shows, diagnostics=collector.build())


def _title(display_title: object, original_title: object) -> str | None:
    for value in (display_title, original_title):
        if not pd.isna(value) and str(value).strip():
            return str(value).strip()
    return None


def _to_episode_number(value: object) -> int | None:
    if pd.isna(value):
        return None
    try:
        number = int(str(value))
    except ValueError:
        return None
    return number if number >= 0 else None
