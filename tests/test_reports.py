"""Tests for comparison report generation."""

import csv
from pathlib import Path
from typing import Literal

from tvtimecompare.compare import MatchingConfig, compare_watched_episodes
from tvtimecompare.models import Episode, Show
from tvtimecompare.readers import ParseDiagnostics, SkipReason
from tvtimecompare.reports import generate_reports


def _show(
    title: str,
    source: Literal["tvtime", "refract"],
    episodes: tuple[tuple[int, int], ...],
) -> Show:
    show = Show(
        display_title=title,
        normalized_title=title.casefold(),
        source=source,
    )
    for season, episode in episodes:
        show.add_episode(Episode(season, episode))
    return show


def test_generate_reports_writes_csv_and_searchable_html(tmp_path: Path) -> None:
    """All report files contain the comparison data in their expected format."""
    tvtime_matched = _show("Matched Show", "tvtime", ((1, 1), (1, 2)))
    tvtime_missing = _show("Missing Show", "tvtime", ((1, 1),))
    refract_matched = _show("Matched Show", "refract", ((1, 1),))
    result = compare_watched_episodes(
        {"matched": tvtime_matched, "missing": tvtime_missing},
        {"matched": refract_matched},
    )

    diagnostics = ParseDiagnostics(
        source_file="episodes.csv",
        rows_read=3,
        rows_imported=2,
        skipped_by_reason={SkipReason.DUPLICATE_EPISODE: 1},
    )
    paths = generate_reports(result, tmp_path / "reports", diagnostics=(diagnostics,))

    assert paths.summary_csv.name == "summary.csv"
    assert all(
        path.is_file()
        for path in (
            paths.summary_csv,
            paths.missing_shows_csv,
            paths.ambiguous_matches_csv,
            paths.missing_episodes_csv,
            paths.report_html,
        )
    )
    with paths.summary_csv.open(newline="", encoding="utf-8") as report_file:
        summary_rows = list(csv.DictReader(report_file))
    with paths.missing_shows_csv.open(newline="", encoding="utf-8") as report_file:
        missing_show_rows = list(csv.DictReader(report_file))
    with paths.missing_episodes_csv.open(newline="", encoding="utf-8") as report_file:
        missing_episode_rows = list(csv.DictReader(report_file))

    summary = {row["Metric"]: row["Value"] for row in summary_rows}
    assert summary["Missing episodes"] == "1"
    assert summary["episodes.csv: rows skipped"] == "1"
    assert summary["episodes.csv: duplicate episode"] == "1"
    assert missing_show_rows == [
        {
            "Display Title": "Missing Show",
            "Normalized Title": "missing show",
            "Source": "tvtime",
            "Source Show ID": "",
            "TMDB ID": "",
            "TVDB ID": "",
            "IMDb ID": "",
            "Watched Episode Count": "1",
        }
    ]
    assert missing_episode_rows == [
        {
            "TV Time Title": "Matched Show",
            "Refract Title": "Matched Show",
            "Match Method": "title",
            "Season": "1",
            "Episode": "2",
        }
    ]
    html = paths.report_html.read_text(encoding="utf-8")
    assert "Comparison statistics" in html
    assert "table-search" in html
    assert "<details open>" in html
    assert "Matched Show" in html
    assert "Import diagnostics" in html
    assert "episodes.csv" in html


def test_reports_include_ambiguous_fuzzy_candidates(tmp_path: Path) -> None:
    """Ambiguous candidates are written for review rather than hidden as gaps."""
    tvtime = _show("The Great Adventure", "tvtime", ())
    first_candidate = _show("Great Adventure", "refract", ())
    second_candidate = _show("Great Adventures", "refract", ())
    result = compare_watched_episodes(
        {"tvtime": tvtime},
        {"first": first_candidate, "second": second_candidate},
        MatchingConfig(fuzzy_confidence_threshold=50, fuzzy_ambiguity_threshold=100),
    )

    paths = generate_reports(result, tmp_path / "reports")

    with paths.ambiguous_matches_csv.open(newline="", encoding="utf-8") as report_file:
        rows = list(csv.DictReader(report_file))
    assert len(rows) == 2
    assert {row["Candidate Refract Title"] for row in rows} == {
        "Great Adventure",
        "Great Adventures",
    }
    assert "Ambiguous title matches" in paths.report_html.read_text(encoding="utf-8")
