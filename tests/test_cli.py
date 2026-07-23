"""Tests for the command-line interface."""

from pathlib import Path

from typer.testing import CliRunner

from tvtimecompare.cli import app

runner = CliRunner()


def test_compare_accepts_zip_exports(tmp_path: Path) -> None:
    """The placeholder command accepts two ZIP-named export files."""
    tvtime_export = tmp_path / "tvtime.zip"
    refract_export = tmp_path / "refract.zip"
    tvtime_export.touch()
    refract_export.touch()

    result = runner.invoke(app, ["compare", str(tvtime_export), str(refract_export)])

    assert result.exit_code == 0
    assert "Comparison is not implemented yet." in result.output


def test_compare_rejects_non_zip_export(tmp_path: Path) -> None:
    """The command explains when an export does not have a ZIP extension."""
    tvtime_export = tmp_path / "tvtime.csv"
    refract_export = tmp_path / "refract.zip"
    tvtime_export.touch()
    refract_export.touch()

    result = runner.invoke(app, ["compare", str(tvtime_export), str(refract_export)])

    assert result.exit_code != 0
    assert "must be a .zip file" in result.output
