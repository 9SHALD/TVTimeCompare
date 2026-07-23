"""Reader for watched episodes in Refract export archives."""

from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pandas as pd
from pandas.errors import EmptyDataError, ParserError

from tvtimecompare.models import Episode, Show
from tvtimecompare.utils import normalize_title

_EPISODES_FILENAME = "episodes.csv"
_REQUIRED_COLUMNS = {"ShowTitle", "ShowOriginalTitle", "Season", "Episode"}


class RefractExportError(ValueError):
    """Raised when a ZIP archive cannot be read as a Refract export."""


def read_refract_export(export_path: Path) -> dict[str, Show]:
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

    def read(self) -> dict[str, Show]:
        """Return shows keyed by normalized display title."""
        try:
            with ZipFile(self.export_path) as archive:
                if _EPISODES_FILENAME not in archive.namelist():
                    raise RefractExportError(
                        f"Refract export does not contain {_EPISODES_FILENAME}."
                    )
                with archive.open(_EPISODES_FILENAME) as csv_file:
                    records = pd.read_csv(
                        csv_file,
                        dtype="string",
                        encoding="utf-8-sig",
                        on_bad_lines="skip",
                    )
        except FileNotFoundError as error:
            message = f"Refract export was not found: {self.export_path}"
            raise RefractExportError(message) from error
        except BadZipFile as error:
            message = f"Refract export is not a valid ZIP file: {self.export_path}"
            raise RefractExportError(message) from error
        except (EmptyDataError, ParserError, UnicodeDecodeError) as error:
            message = f"{_EPISODES_FILENAME} could not be parsed as UTF-8 CSV."
            raise RefractExportError(message) from error

        missing_columns = _REQUIRED_COLUMNS.difference(records.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise RefractExportError(
                f"{_EPISODES_FILENAME} is missing required columns: {missing}."
            )
        return _build_shows(records)


def _build_shows(records: pd.DataFrame) -> dict[str, Show]:
    shows: dict[str, Show] = {}
    for row in records.itertuples(index=False):
        title = _title(row.ShowTitle, row.ShowOriginalTitle)
        season = _to_episode_number(row.Season)
        episode = _to_episode_number(row.Episode)
        if title is None or season is None or episode is None:
            continue
        normalized_title = normalize_title(title)
        if not normalized_title:
            continue
        show = shows.setdefault(
            normalized_title,
            Show(
                display_title=title,
                normalized_title=normalized_title,
                source="refract",
            ),
        )
        show.add_episode(Episode(season, episode))
    return shows


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
