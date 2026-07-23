"""Tests for the command-line interface."""

from pathlib import Path
from zipfile import ZipFile

from typer.testing import CliRunner

from tvtimecompare.cli import app

runner = CliRunner()
_FIXTURES = Path(__file__).parent / "fixtures"


def _archive_with(path: Path, name: str, fixture_name: str) -> Path:
    with ZipFile(path, "w") as archive:
        archive.write(_FIXTURES / fixture_name, arcname=name)
    return path


def test_compare_reads_exports_and_generates_reports(tmp_path: Path) -> None:
    """The command completes the full import, comparison, and report workflow."""
    tvtime_export = _archive_with(
        tmp_path / "tvtime.zip",
        "tracking-prod-records-v2.csv",
        "tvtime_tracking-prod-records-v2.csv",
    )
    refract_export = _archive_with(
        tmp_path / "refract.zip", "episodes.csv", "refract_episodes.csv"
    )
    output_dir = tmp_path / "reports"

    result = runner.invoke(
        app,
        [
            "compare",
            str(tvtime_export),
            str(refract_export),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert "Comparison complete" in result.output
    assert "Import diagnostics" in result.output
    assert "Reports written to" in result.output
    assert (output_dir / "summary.csv").is_file()
    assert (output_dir / "missing_shows.csv").is_file()
    assert (output_dir / "ambiguous_matches.csv").is_file()
    assert (output_dir / "missing_episodes.csv").is_file()
    assert (output_dir / "report.html").is_file()


def test_compare_rejects_non_zip_export(tmp_path: Path) -> None:
    """The command explains when an export does not have a ZIP extension."""
    tvtime_export = tmp_path / "tvtime.csv"
    refract_export = tmp_path / "refract.zip"
    tvtime_export.touch()
    refract_export.touch()

    result = runner.invoke(app, ["compare", str(tvtime_export), str(refract_export)])

    assert result.exit_code != 0
    assert "must be a .zip file" in result.output
