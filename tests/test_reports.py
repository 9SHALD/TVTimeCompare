"""Tests for comparison report generation."""

import csv
from pathlib import Path
from typing import Literal

from tvtimecompare.compare import compare_watched_episodes
from tvtimecompare.models import Episode, Show
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

    paths = generate_reports(result, tmp_path / "reports")

    assert paths.summary_csv.name == "summary.csv"
    assert all(
        path.is_file()
        for path in (
            paths.summary_csv,
            paths.missing_shows_csv,
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
