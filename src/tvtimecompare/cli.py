"""Command-line interface for TVTimeCompare."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(
    name="tvtimecompare",
    help="Compare TV Time GDPR exports with Refract exports.",
    no_args_is_help=True,
)
console = Console()


def _validate_export(path: Path, export_name: str) -> None:
    """Ensure an input path is a readable ZIP archive."""
    if not path.is_file():
        raise typer.BadParameter(
            f"{export_name} export was not found or is not a file: {path}",
            param_hint=export_name.lower().replace(" ", "_"),
        )
    if path.suffix.lower() != ".zip":
        raise typer.BadParameter(
            f"{export_name} export must be a .zip file: {path}",
            param_hint=export_name.lower().replace(" ", "_"),
        )


@app.command()
def compare(
    tvtime_export: Annotated[
        Path,
        typer.Argument(
            help="Path to the TV Time GDPR ZIP export.",
            exists=True,
            readable=True,
            resolve_path=True,
        ),
    ],
    refract_export: Annotated[
        Path,
        typer.Argument(
            help="Path to the Refract ZIP export.",
            exists=True,
            readable=True,
            resolve_path=True,
        ),
    ],
) -> None:
    """Compare TV Time and Refract exports (implementation pending)."""
    _validate_export(tvtime_export, "TV Time")
    _validate_export(refract_export, "Refract")

    console.print("[yellow]Comparison is not implemented yet.[/yellow]")
    console.print(f"TV Time export: [cyan]{tvtime_export}[/cyan]")
    console.print(f"Refract export: [cyan]{refract_export}[/cyan]")
