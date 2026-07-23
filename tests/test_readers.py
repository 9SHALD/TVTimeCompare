"""Tests using small CSV fixtures extracted from the supplied exports."""

from pathlib import Path
from zipfile import ZipFile

from tvtimecompare.models import Episode, EpisodeKey
from tvtimecompare.readers import SkipReason, read_refract_export, read_tvtime_export

_FIXTURES = Path(__file__).parent / "fixtures"


def _archive_with(path: Path, name: str, fixture_name: str) -> Path:
    with ZipFile(path, "w") as archive:
        archive.write(_FIXTURES / fixture_name, arcname=name)
    return path


def _archive_with_text(path: Path, name: str, contents: str) -> Path:
    with ZipFile(path, "w") as archive:
        archive.writestr(name, contents)
    return path


def test_tvtime_primary_reader_uses_show_id_and_ignores_rewatches(
    tmp_path: Path,
) -> None:
    export = _archive_with(
        tmp_path / "tvtime.zip",
        "tracking-prod-records-v2.csv",
        "tvtime_tracking-prod-records-v2.csv",
    )

    read_result = read_tvtime_export(export)
    shows = read_result.shows

    assert set(shows) == {"100"}
    show = shows["100"]
    assert show.display_title == "Example Show"
    assert show.normalized_title == "example show"
    assert show.source == "tvtime"
    assert show.source_show_id == "100"
    assert show.episodes == {
        EpisodeKey(1, 13): Episode(1, 13, "1001"),
        EpisodeKey(4, 22): Episode(4, 22, "1002"),
    }
    assert show.episodes[EpisodeKey(1, 13)].source_episode_id == "1001"
    assert show.watched_episodes == {Episode(1, 13), Episode(4, 22)}
    assert read_result.diagnostics.source_file == "tracking-prod-records-v2.csv"
    assert read_result.diagnostics.rows_read == 3
    assert read_result.diagnostics.rows_imported == 2
    assert read_result.diagnostics.skipped_by_reason == {
        SkipReason.DUPLICATE_EPISODE: 1
    }


def test_tvtime_reader_uses_seen_episode_when_primary_is_absent(tmp_path: Path) -> None:
    export = _archive_with(
        tmp_path / "tvtime.zip",
        "seen_episode.csv",
        "tvtime_seen_episode.csv",
    )

    read_result = read_tvtime_export(export)
    shows = read_result.shows

    show = shows["example legacy show"]
    assert show.display_title == "Example Legacy Show"
    assert show.watched_episodes == {Episode(2, 1)}
    assert read_result.diagnostics.source_file == "seen_episode.csv"
    assert read_result.diagnostics.rows_read == 1
    assert read_result.diagnostics.rows_imported == 1
    assert read_result.diagnostics.rows_skipped == 0


def test_refract_reader_prefers_display_title_and_falls_back_to_original_title(
    tmp_path: Path,
) -> None:
    export = _archive_with(
        tmp_path / "refract.zip", "episodes.csv", "refract_episodes.csv"
    )

    read_result = read_refract_export(export)
    shows = read_result.shows

    assert shows["example anime"].display_title == "Example Anime"
    assert shows["example anime"].watched_episodes == {Episode(1, 1)}
    assert shows["example show"].display_title == "Example Show"
    assert shows["example show"].watched_episodes == {Episode(1, 2)}
    assert shows["example show"].source == "refract"
    assert shows["example show"].source_show_id is None
    assert read_result.diagnostics.rows_read == 3
    assert read_result.diagnostics.rows_imported == 2
    assert read_result.diagnostics.skipped_by_reason == {
        SkipReason.DUPLICATE_EPISODE: 1
    }


def test_readers_accept_bom_and_skip_malformed_rows(tmp_path: Path) -> None:
    tvtime_contents = (_FIXTURES / "tvtime_tracking-prod-records-v2.csv").read_text()
    tvtime_export = _archive_with_text(
        tmp_path / "tvtime.zip",
        "tracking-prod-records-v2.csv",
        "\ufeff" + tvtime_contents + "too,many,columns," * 10 + "\n",
    )
    refract_contents = (_FIXTURES / "refract_episodes.csv").read_text()
    refract_export = _archive_with_text(
        tmp_path / "refract.zip",
        "episodes.csv",
        "\ufeff" + refract_contents + "broken,row\n",
    )

    tvtime_result = read_tvtime_export(tvtime_export)
    refract_result = read_refract_export(refract_export)

    assert tvtime_result.shows["100"].watched_episodes == {
        Episode(1, 13),
        Episode(4, 22),
    }
    assert refract_result.shows["example show"].watched_episodes == {Episode(1, 2)}
    assert tvtime_result.diagnostics.rows_read == 4
    assert tvtime_result.diagnostics.skipped_by_reason == {
        SkipReason.MALFORMED_CSV_ROW: 1,
        SkipReason.DUPLICATE_EPISODE: 1,
    }
    assert refract_result.diagnostics.rows_read == 4
    assert refract_result.diagnostics.skipped_by_reason == {
        SkipReason.DUPLICATE_EPISODE: 1,
        SkipReason.INVALID_SEASON_NUMBER: 1,
    }


def test_refract_reader_records_semantic_skip_reasons(tmp_path: Path) -> None:
    """Missing, invalid, empty, and duplicate records are diagnosed separately."""
    header = (_FIXTURES / "refract_episodes.csv").read_text().splitlines()[0]
    export = _archive_with_text(
        tmp_path / "refract.zip",
        "episodes.csv",
        "\n".join(
            (
                header,
                ",,Anime,ZZ,1,1,2024-01-01,,",
                "???,,Anime,ZZ,1,2,2024-01-01,,",
                "Example,Anime,Anime,ZZ,x,3,2024-01-01,,",
                "Example,Anime,Anime,ZZ,1,x,2024-01-01,,",
                "Example,Anime,Anime,ZZ,1,4,2024-01-01,,",
                "Example,Anime,Anime,ZZ,1,4,2024-01-01,,",
            )
        ),
    )

    read_result = read_refract_export(export)

    assert read_result.diagnostics.rows_read == 6
    assert read_result.diagnostics.rows_imported == 1
    assert read_result.diagnostics.skipped_by_reason == {
        SkipReason.MISSING_REQUIRED_VALUE: 1,
        SkipReason.EMPTY_NORMALIZED_TITLE: 1,
        SkipReason.INVALID_SEASON_NUMBER: 1,
        SkipReason.INVALID_EPISODE_NUMBER: 1,
        SkipReason.DUPLICATE_EPISODE: 1,
    }
