"""Tests using small CSV fixtures extracted from the supplied exports."""

from pathlib import Path
from zipfile import ZipFile

from tvtimecompare.models import Episode
from tvtimecompare.readers import read_refract_export, read_tvtime_export

_FIXTURES = Path(__file__).parent / "fixtures"


def _archive_with(path: Path, name: str, fixture_name: str) -> Path:
    with ZipFile(path, "w") as archive:
        archive.write(_FIXTURES / fixture_name, arcname=name)
    return path


def test_tvtime_primary_reader_uses_show_id_and_ignores_rewatches(
    tmp_path: Path,
) -> None:
    export = _archive_with(
        tmp_path / "tvtime.zip",
        "tracking-prod-records-v2.csv",
        "tvtime_tracking-prod-records-v2.csv",
    )

    shows = read_tvtime_export(export)

    assert set(shows) == {"80348"}
    chuck = shows["80348"]
    assert chuck.original_title == "Chuck"
    assert chuck.normalized_title == "chuck"
    assert chuck.source_id == "80348"
    assert chuck.watched_episodes == {Episode(1, 13), Episode(4, 22)}
    assert chuck.tmdb_id is chuck.tvdb_id is chuck.imdb_id is None


def test_tvtime_reader_uses_seen_episode_when_primary_is_absent(tmp_path: Path) -> None:
    export = _archive_with(
        tmp_path / "tvtime.zip",
        "seen_episode.csv",
        "tvtime_seen_episode.csv",
    )

    shows = read_tvtime_export(export)

    show = shows["tsukimichi moonlit fantasy"]
    assert show.original_title == "Tsukimichi -Moonlit Fantasy-"
    assert show.watched_episodes == {Episode(2, 1)}


def test_refract_reader_uses_original_title_when_display_title_is_empty(
    tmp_path: Path,
) -> None:
    export = _archive_with(
        tmp_path / "refract.zip", "episodes.csv", "refract_episodes.csv"
    )

    shows = read_refract_export(export)

    assert shows["trigun"].original_title == "TRIGUN"
    assert shows["trigun"].watched_episodes == {Episode(1, 1)}
    assert shows["the new gate"].original_title == "THE NEW GATE"
    assert shows["the new gate"].watched_episodes == {Episode(1, 2)}
