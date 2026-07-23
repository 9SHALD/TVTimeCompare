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

from tvtimecompare.compare import ComparisonStatistics, compare_watched_episodes
from tvtimecompare.readers import (
    RefractExportError,
    TVTimeExportError,
    read_refract_export,
    read_tvtime_export,
)
from tvtimecompare.reports import generate_reports

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
            tvtime_shows = read_tvtime_export(tvtime_export)
            progress.advance(task_id)
            progress.update(task_id, description="Reading Refract export")
            refract_shows = read_refract_export(refract_export)
            progress.advance(task_id)
            progress.update(task_id, description="Comparing watched episodes")
            result = compare_watched_episodes(tvtime_shows, refract_shows)
            progress.advance(task_id)
            progress.update(task_id, description="Generating reports")
            report_paths = generate_reports(result, output_dir)
            progress.advance(task_id)
    except (RefractExportError, TVTimeExportError) as error:
        console.print(f"[red]Export error:[/red] {error}")
        raise typer.Exit(code=1) from error

    _print_statistics(result.statistics)
    console.print(f"Reports written to [cyan]{report_paths.report_html.parent}[/cyan]")


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
        ("TV Time episodes", statistics.tvtime_episode_count),
        ("Refract episodes", statistics.refract_episode_count),
        ("Missing episodes", statistics.missing_episode_count),
    ):
        table.add_row(label, str(value))
    console.print(table)
