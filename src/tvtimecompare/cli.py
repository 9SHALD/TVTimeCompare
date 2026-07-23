"""Command-line interface for TVTimeCompare."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table

from tvtimecompare.compare import ComparisonStatistics
from tvtimecompare.readers import (
    ParseDiagnostics,
    RefractExportError,
    TVTimeExportError,
)
from tvtimecompare.services import run_comparison

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
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            help="Directory in which to create CSV and HTML reports.",
        ),
    ] = Path("reports"),
) -> None:
    """Compare TV Time and Refract exports and generate migration reports."""
    _validate_export(tvtime_export, "TV Time")
    _validate_export(refract_export, "Refract")
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task("Reading TV Time export", total=4)
            comparison_run = run_comparison(
                tvtime_export,
                refract_export,
                output_dir,
                on_progress=lambda completed, description: _update_progress(
                    progress, task_id, completed, description
                ),
            )
    except (RefractExportError, TVTimeExportError) as error:
        console.print(f"[red]Export error:[/red] {error}")
        raise typer.Exit(code=1) from error

    _print_statistics(comparison_run.result.statistics)
    _print_diagnostics(comparison_run.diagnostics)
    console.print(
        f"Reports written to [cyan]{comparison_run.report_paths.report_html.parent}[/cyan]"
    )


def _update_progress(
    progress: Progress, task_id: int, completed: int, description: str
) -> None:
    """Synchronize a Rich task with the shared comparison workflow stages."""
    progress.update(task_id, completed=completed, description=description)


@app.command()
def gui() -> None:
    """Open the PySide6 desktop interface."""
    try:
        from tvtimecompare.gui import run_gui
    except ImportError as error:
        message = "GUI support is not installed. Install it with: pip install -e '.[gui]'"
        console.print(f"[red]{message}[/red]")
        raise typer.Exit(code=1) from error
    raise typer.Exit(run_gui())


def _print_statistics(statistics: ComparisonStatistics) -> None:
    """Print the comparison statistics as a Rich table."""
    table = Table(title="Comparison complete")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    for label, value in (
        ("TV Time shows", statistics.tvtime_show_count),
        ("Refract shows", statistics.refract_show_count),
        ("Matched shows", statistics.matched_show_count),
        ("Missing shows", statistics.missing_show_count),
        ("Ambiguous shows", statistics.ambiguous_show_count),
        ("TV Time episodes", statistics.tvtime_episode_count),
        ("Refract episodes", statistics.refract_episode_count),
        ("Missing episodes", statistics.missing_episode_count),
    ):
        table.add_row(label, str(value))
    console.print(table)


def _print_diagnostics(diagnostics: tuple[ParseDiagnostics, ...]) -> None:
    """Print source parsing diagnostics as a Rich table."""
    table = Table(title="Import diagnostics")
    table.add_column("Source file", style="bold")
    table.add_column("Read", justify="right")
    table.add_column("Imported", justify="right")
    table.add_column("Skipped", justify="right")
    table.add_column("Reasons")
    for item in diagnostics:
        table.add_row(
            item.source_file,
            str(item.rows_read),
            str(item.rows_imported),
            str(item.rows_skipped),
            item.reason_summary(),
        )
    console.print(table)
