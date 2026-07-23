"""Tests for platform-neutral desktop packaging helpers."""

import importlib.util
from pathlib import Path


def _load_build_module() -> object:
    script = Path(__file__).parent.parent / "scripts" / "build_desktop.py"
    specification = importlib.util.spec_from_file_location("build_desktop", script)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_bundle_paths_match_pyinstaller_platform_conventions(tmp_path: Path) -> None:
    """macOS uses an app bundle while Windows uses a directory bundle."""
    build_desktop = _load_build_module()

    assert build_desktop._bundle_path(tmp_path, "Darwin") == (
        tmp_path / "TVTimeCompare.app"
    )
    assert build_desktop._bundle_path(tmp_path, "Windows") == tmp_path / "TVTimeCompare"
