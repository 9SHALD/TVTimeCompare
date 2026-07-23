"""Build a native TVTimeCompare desktop bundle on the current platform."""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_ROOT = _PROJECT_ROOT / "src"
_ENTRY_POINT = _SOURCE_ROOT / "tvtimecompare" / "gui" / "__main__.py"
_APPLICATION_NAME = "TVTimeCompare"


def build_desktop_bundle(output_dir: Path) -> Path:
    """Build and archive a GUI bundle for the current supported platform.

    The build must run on the target operating system because PyInstaller does
    not cross-compile macOS applications or Windows executables.
    """
    platform_name = platform.system()
    if platform_name not in {"Darwin", "Windows"}:
        message = "Desktop bundles can only be built on macOS or Windows."
        raise RuntimeError(message)

    output_dir = output_dir.resolve()
    build_dir = output_dir / "build"
    dist_dir = output_dir / "dist"
    output_dir.mkdir(parents=True, exist_ok=True)
    command = (
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        _APPLICATION_NAME,
        "--paths",
        str(_SOURCE_ROOT),
        "--collect-data",
        "tvtimecompare.reports",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(build_dir),
        "--specpath",
        str(build_dir),
        str(_ENTRY_POINT),
    )
    subprocess.run(command, check=True, cwd=_PROJECT_ROOT)

    bundle = _bundle_path(dist_dir, platform_name)
    if not bundle.exists():
        raise RuntimeError(f"PyInstaller did not create the expected bundle: {bundle}")
    return _archive_bundle(bundle, output_dir, platform_name)


def _bundle_path(dist_dir: Path, platform_name: str) -> Path:
    if platform_name == "Darwin":
        return dist_dir / f"{_APPLICATION_NAME}.app"
    return dist_dir / _APPLICATION_NAME


def _archive_bundle(bundle: Path, output_dir: Path, platform_name: str) -> Path:
    archive_dir = output_dir / "archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    platform_label = "macos" if platform_name == "Darwin" else "windows"
    architecture = platform.machine().casefold().replace("_", "-")
    archive_base = archive_dir / f"{_APPLICATION_NAME}-{platform_label}-{architecture}"
    archive_path = shutil.make_archive(
        str(archive_base),
        "zip",
        root_dir=bundle.parent,
        base_dir=bundle.name,
    )
    return Path(archive_path)


def main() -> int:
    """Parse command-line options and create a distributable desktop ZIP."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_PROJECT_ROOT / "package-dist",
        help="Directory for PyInstaller output and the distributable ZIP.",
    )
    arguments = parser.parse_args()
    try:
        archive = build_desktop_bundle(arguments.output_dir)
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Desktop build failed: {error}", file=sys.stderr)
        return 1
    print(f"Desktop bundle created: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
