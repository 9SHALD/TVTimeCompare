"""Shared orchestration for a complete export comparison."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tvtimecompare.compare import (
    ComparisonResult,
    MatchingConfig,
    compare_watched_episodes,
)
from tvtimecompare.readers import (
    ParseDiagnostics,
    read_refract_export,
    read_tvtime_export,
)
from tvtimecompare.reports import ReportPaths, generate_reports

ProgressCallback = Callable[[int, str], None]


@dataclass(frozen=True, slots=True)
class ComparisonRun:
    """Artifacts produced by parsing, comparing, and reporting one migration."""

    result: ComparisonResult
    diagnostics: tuple[ParseDiagnostics, ParseDiagnostics]
    report_paths: ReportPaths


def run_comparison(
    tvtime_export: Path,
    refract_export: Path,
    output_dir: Path,
    *,
    matching_config: MatchingConfig | None = None,
    on_progress: ProgressCallback | None = None,
) -> ComparisonRun:
    """Run the complete comparison workflow and write its reports.

    Args:
        tvtime_export: Path to a TV Time GDPR ZIP export.
        refract_export: Path to a Refract ZIP export.
        output_dir: Directory where reports will be written.
        matching_config: Optional matching configuration.
        on_progress: Receives the completed-stage count and current stage label.

    Returns:
        The comparison result, parser diagnostics, and generated report paths.

    Raises:
        TVTimeExportError: If the TV Time export cannot be read.
        RefractExportError: If the Refract export cannot be read.
    """
    _notify_progress(on_progress, 0, "Reading TV Time export")
    tvtime_result = read_tvtime_export(tvtime_export)
    _notify_progress(on_progress, 1, "Reading Refract export")
    refract_result = read_refract_export(refract_export)
    _notify_progress(on_progress, 2, "Comparing watched episodes")
    result = compare_watched_episodes(
        tvtime_result.shows,
        refract_result.shows,
        matching_config=matching_config,
    )
    _notify_progress(on_progress, 3, "Generating reports")
    report_paths = generate_reports(
        result,
        output_dir,
        diagnostics=(tvtime_result.diagnostics, refract_result.diagnostics),
    )
    _notify_progress(on_progress, 4, "Comparison complete")
    return ComparisonRun(
        result=result,
        diagnostics=(tvtime_result.diagnostics, refract_result.diagnostics),
        report_paths=report_paths,
    )


def _notify_progress(
    callback: ProgressCallback | None, completed: int, description: str
) -> None:
    if callback is not None:
        callback(completed, description)
