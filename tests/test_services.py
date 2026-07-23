"""Tests for the shared application comparison workflow."""

from pathlib import Path
from zipfile import ZipFile

from tvtimecompare.services import run_comparison

_FIXTURES = Path(__file__).parent / "fixtures"


def _archive_with(path: Path, name: str, fixture_name: str) -> Path:
    with ZipFile(path, "w") as archive:
        archive.write(_FIXTURES / fixture_name, arcname=name)
    return path


def test_run_comparison_orchestrates_every_backend_stage(tmp_path: Path) -> None:
    """The reusable workflow produces results, diagnostics, reports, and stages."""
    tvtime_export = _archive_with(
        tmp_path / "tvtime.zip",
        "tracking-prod-records-v2.csv",
        "tvtime_tracking-prod-records-v2.csv",
    )
    refract_export = _archive_with(
        tmp_path / "refract.zip", "episodes.csv", "refract_episodes.csv"
    )
    progress: list[tuple[int, str]] = []

    comparison_run = run_comparison(
        tvtime_export,
        refract_export,
        tmp_path / "reports",
        on_progress=lambda stage, label: progress.append((stage, label)),
    )

    assert [stage for stage, _ in progress] == [0, 1, 2, 3, 4]
    assert comparison_run.result.statistics.tvtime_show_count == 1
    assert len(comparison_run.diagnostics) == 2
    assert comparison_run.report_paths.report_html.is_file()
