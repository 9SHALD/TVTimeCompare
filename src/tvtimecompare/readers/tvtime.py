"""Reader for watched episodes in TV Time GDPR export archives."""

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

_PRIMARY_FILENAME = "tracking-prod-records-v2.csv"
_FALLBACK_FILENAME = "seen_episode.csv"
_PRIMARY_REQUIRED_COLUMNS = {
    "series_name",
    "s_id",
    "episode_id",
    "season_number",
    "episode_number",
}
_FALLBACK_REQUIRED_COLUMNS = {
    "tv_show_name",
    "episode_id",
    "episode_season_number",
    "episode_number",
}


class TVTimeExportError(ValueError):
    """Raised when a ZIP archive cannot be read as a TV Time GDPR export."""


def read_tvtime_export(export_path: Path) -> ExportReadResult:
    """Read watched episodes from a TV Time GDPR ZIP export.

    ``tracking-prod-records-v2.csv`` is preferred. The legacy
    ``seen_episode.csv`` is used only when the primary file is absent. Shows
    are keyed by TV Time's ``s_id`` when available; this avoids conflating
    distinct shows that share a title.
    """
    return TVTimeReader(export_path).read()


class TVTimeReader:
    """Read watched television episodes from one TV Time GDPR ZIP export."""

    def __init__(self, export_path: Path) -> None:
        self.export_path = export_path

    def read(self) -> ExportReadResult:
        """Return parsed shows and diagnostics for the selected TV Time CSV."""
        try:
            with ZipFile(self.export_path) as archive:
                names = set(archive.namelist())
                if _PRIMARY_FILENAME in names:
                    return _read_primary(archive)
                if _FALLBACK_FILENAME in names:
                    return _read_fallback(archive)
        except FileNotFoundError as error:
            message = f"TV Time export was not found: {self.export_path}"
            raise TVTimeExportError(message) from error
        except BadZipFile as error:
            message = f"TV Time export is not a valid ZIP file: {self.export_path}"
            raise TVTimeExportError(message) from error

        expected = f"{_PRIMARY_FILENAME} or {_FALLBACK_FILENAME}"
        raise TVTimeExportError(f"TV Time export does not contain {expected}.")


def _read_primary(archive: ZipFile) -> ExportReadResult:
    collector = new_diagnostics_collector(_PRIMARY_FILENAME)
    records = _read_csv(archive, _PRIMARY_FILENAME, collector)
    _require_columns(records, _PRIMARY_REQUIRED_COLUMNS, _PRIMARY_FILENAME)

    shows: dict[str, Show] = {}
    seen_episode_ids: dict[str, set[str]] = {}
    for row in records.itertuples(index=False):
        title = row.series_name
        show_id = row.s_id
        episode_id = row.episode_id
        season = _to_episode_number(row.season_number)
        episode = _to_episode_number(row.episode_number)
        if pd.isna(title) or pd.isna(show_id) or pd.isna(episode_id):
            collector.record_skip(SkipReason.MISSING_REQUIRED_VALUE)
            continue
        if season is None:
            collector.record_skip(SkipReason.INVALID_SEASON_NUMBER)
            continue
        if episode is None:
            collector.record_skip(SkipReason.INVALID_EPISODE_NUMBER)
            continue
        title_text = str(title).strip()
        show_id_text = str(show_id).strip()
        episode_id_text = str(episode_id).strip()
        normalized_title = normalize_title(title_text)
        if not title_text or not show_id_text or not episode_id_text:
            collector.record_skip(SkipReason.MISSING_REQUIRED_VALUE)
            continue
        if not normalized_title:
            collector.record_skip(SkipReason.EMPTY_NORMALIZED_TITLE)
            continue
        if episode_id_text in seen_episode_ids.setdefault(show_id_text, set()):
            collector.record_skip(SkipReason.DUPLICATE_EPISODE)
            continue
        seen_episode_ids[show_id_text].add(episode_id_text)
        show = shows.setdefault(
            show_id_text,
            Show(
                display_title=title_text,
                normalized_title=normalized_title,
                source="tvtime",
                source_show_id=show_id_text,
            ),
        )
        if show.add_episode(Episode(season, episode, episode_id_text)):
            collector.record_import()
        else:
            collector.record_skip(SkipReason.DUPLICATE_EPISODE)
    return ExportReadResult(shows=shows, diagnostics=collector.build())


def _read_fallback(archive: ZipFile) -> ExportReadResult:
    collector = new_diagnostics_collector(_FALLBACK_FILENAME)
    records = _read_csv(archive, _FALLBACK_FILENAME, collector)
    _require_columns(records, _FALLBACK_REQUIRED_COLUMNS, _FALLBACK_FILENAME)

    shows: dict[str, Show] = {}
    seen_episode_ids: dict[str, set[str]] = {}
    for row in records.itertuples(index=False):
        title = row.tv_show_name
        episode_id = row.episode_id
        season = _to_episode_number(row.episode_season_number)
        episode = _to_episode_number(row.episode_number)
        if pd.isna(title) or pd.isna(episode_id):
            collector.record_skip(SkipReason.MISSING_REQUIRED_VALUE)
            continue
        if season is None:
            collector.record_skip(SkipReason.INVALID_SEASON_NUMBER)
            continue
        if episode is None:
            collector.record_skip(SkipReason.INVALID_EPISODE_NUMBER)
            continue
        title_text = str(title).strip()
        episode_id_text = str(episode_id).strip()
        normalized_title = normalize_title(title_text)
        if not title_text or not episode_id_text:
            collector.record_skip(SkipReason.MISSING_REQUIRED_VALUE)
            continue
        if not normalized_title:
            collector.record_skip(SkipReason.EMPTY_NORMALIZED_TITLE)
            continue
        if episode_id_text in seen_episode_ids.setdefault(normalized_title, set()):
            collector.record_skip(SkipReason.DUPLICATE_EPISODE)
            continue
        seen_episode_ids[normalized_title].add(episode_id_text)
        show = shows.setdefault(
            normalized_title,
            Show(
                display_title=title_text,
                normalized_title=normalized_title,
                source="tvtime",
            ),
        )
        if show.add_episode(Episode(season, episode, episode_id_text)):
            collector.record_import()
        else:
            collector.record_skip(SkipReason.DUPLICATE_EPISODE)
    return ExportReadResult(shows=shows, diagnostics=collector.build())


def _read_csv(
    archive: ZipFile,
    filename: str,
    collector: _DiagnosticsCollector,
) -> pd.DataFrame:
    try:
        return read_csv_with_diagnostics(archive, filename, collector)
    except CsvParseError as error:
        raise TVTimeExportError(str(error)) from error


def _require_columns(
    records: pd.DataFrame, required_columns: set[str], filename: str
) -> None:
    missing_columns = required_columns.difference(records.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise TVTimeExportError(f"{filename} is missing required columns: {missing}.")


def _to_episode_number(value: object) -> int | None:
    if pd.isna(value):
        return None
    try:
        number = int(str(value))
    except ValueError:
        return None
    return number if number >= 0 else None
