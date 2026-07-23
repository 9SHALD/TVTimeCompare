"""Smoke tests for the optional desktop interface."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from tvtimecompare.gui.app import MainWindow


def test_gui_validates_the_selected_export_paths(tmp_path: Path) -> None:
    """The UI rejects a missing archive before starting a worker thread."""
    missing = tmp_path / "missing.zip"

    assert MainWindow._validate_inputs(missing, missing) == (
        f"TV Time export was not found: {missing}"
    )
