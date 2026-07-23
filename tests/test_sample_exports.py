"""Regression tests against the supplied, anonymized development exports."""

import csv
from pathlib import Path

import pytest

from tvtimecompare.compare import compare_watched_episodes
from tvtimecompare.readers import (
    ExportReadResult,
    SkipReason,
    read_refract_export,
    read_tvtime_export,
)
from tvtimecompare.reports import generate_reports

_SAMPLE_DATA = Path(__file__).parent.parent / "sample_data"
_TVTIME_EXPORT = _SAMPLE_DATA / "tvtime" / "gdpr-data.zip"
_REFRACT_EXPORT = _SAMPLE_DATA / "refract" / "refract-export.zip"


@pytest.fixture(scope="module")
def parsed_sample_exports() -> tuple[ExportReadResult, ExportReadResult]:
    """Parse each supplied archive once for the sample-export regression suite."""
    if not _TVTIME_EXPORT.is_file() or not _REFRACT_EXPORT.is_file():
        pytest.skip("Supplied development exports are not available in this checkout.")
    return read_tvtime_export(_TVTIME_EXPORT), read_refract_export(_REFRACT_EXPORT)


def test_tvtime_sample_export_regression(
    parsed_sample_exports: tuple[ExportReadResult, ExportReadResult],
) -> None:
    """TV Time's real schema keeps its watched rows and duplicate semantics."""
    tvtime_result, _ = parsed_sample_exports

    assert tvtime_result.diagnostics.source_file == "tracking-prod-records-v2.csv"
    assert tvtime_result.diagnostics.rows_read == 21_911
    assert tvtime_result.diagnostics.rows_imported == 21_029
    assert tvtime_result.diagnostics.skipped_by_reason == {
        SkipReason.MISSING_REQUIRED_VALUE: 725,
        SkipReason.DUPLICATE_EPISODE: 157,
    }
    assert len(tvtime_result.shows) == 587
    assert sum(len(show.episodes) for show in tvtime_result.shows.values()) == 21_029


def test_refract_sample_export_regression(
    parsed_sample_exports: tuple[ExportReadResult, ExportReadResult],
) -> None:
    """Refract's BOM-prefixed episode export retains all source rows."""
    _, refract_result = parsed_sample_exports

    assert refract_result.diagnostics.source_file == "episodes.csv"
    assert refract_result.diagnostics.rows_read == 16_067
    assert refract_result.diagnostics.rows_imported == 16_067
    assert refract_result.diagnostics.rows_skipped == 0
    assert len(refract_result.shows) == 551
    assert sum(len(show.episodes) for show in refract_result.shows.values()) == 16_067


def test_sample_exports_complete_pipeline(
    parsed_sample_exports: tuple[ExportReadResult, ExportReadResult],
    tmp_path: Path,
) -> None:
    """Real exports flow from parsing through comparison and report generation."""
    tvtime_result, refract_result = parsed_sample_exports
    result = compare_watched_episodes(tvtime_result.shows, refract_result.shows)

    statistics = result.statistics
    assert statistics.tvtime_show_count == len(tvtime_result.shows)
    assert statistics.refract_show_count == len(refract_result.shows)
    assert statistics.tvtime_episode_count == tvtime_result.diagnostics.rows_imported
    assert statistics.refract_episode_count == refract_result.diagnostics.rows_imported
    assert (
        statistics.matched_show_count
        + statistics.missing_show_count
        + statistics.ambiguous_show_count
        == statistics.tvtime_show_count
    )
    assert len({id(match.refract_show) for match in result.matches}) == len(
        result.matches
    )

    paths = generate_reports(
        result,
        tmp_path / "reports",
        diagnostics=(tvtime_result.diagnostics, refract_result.diagnostics),
    )

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
        summary = {row["Metric"]: row["Value"] for row in csv.DictReader(report_file)}
    assert summary["TV Time shows"] == str(statistics.tvtime_show_count)
    assert summary["Refract shows"] == str(statistics.refract_show_count)
    assert summary["tracking-prod-records-v2.csv: rows read"] == "21911"
    assert summary["episodes.csv: rows imported"] == "16067"
