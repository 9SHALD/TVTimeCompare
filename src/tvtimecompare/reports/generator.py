"""CSV and HTML report generation for comparison results."""

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from tvtimecompare.compare import AmbiguousMatch, ComparisonResult, MissingEpisode
from tvtimecompare.readers import ParseDiagnostics


@dataclass(frozen=True, slots=True)
class ReportPaths:
    """Paths to the files generated for a comparison result."""

    summary_csv: Path
    missing_shows_csv: Path
    ambiguous_matches_csv: Path
    missing_episodes_csv: Path
    report_html: Path


def generate_reports(
    result: ComparisonResult,
    output_dir: Path,
    diagnostics: tuple[ParseDiagnostics, ...] = (),
) -> ReportPaths:
    """Generate CSV and HTML reports for a comparison result.

    Args:
        result: Completed TV Time-to-Refract comparison.
        output_dir: Directory where report files will be created.
        diagnostics: Optional reader diagnostics to include in summary outputs.

    Returns:
        Paths to the four generated report files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = ReportPaths(
        summary_csv=output_dir / "summary.csv",
        missing_shows_csv=output_dir / "missing_shows.csv",
        ambiguous_matches_csv=output_dir / "ambiguous_matches.csv",
        missing_episodes_csv=output_dir / "missing_episodes.csv",
        report_html=output_dir / "report.html",
    )
    _write_summary_csv(result, paths.summary_csv, diagnostics)
    _write_missing_shows_csv(result, paths.missing_shows_csv)
    _write_ambiguous_matches_csv(result, paths.ambiguous_matches_csv)
    _write_missing_episodes_csv(result, paths.missing_episodes_csv)
    _write_html_report(result, paths.report_html, diagnostics)
    return paths


def _write_summary_csv(
    result: ComparisonResult,
    path: Path,
    diagnostics: tuple[ParseDiagnostics, ...],
) -> None:
    statistics = result.statistics
    rows: list[tuple[str, int]] = [
        ("TV Time shows", statistics.tvtime_show_count),
        ("Refract shows", statistics.refract_show_count),
        ("Matched shows", statistics.matched_show_count),
        ("Missing shows", statistics.missing_show_count),
        ("Ambiguous shows", statistics.ambiguous_show_count),
        ("TV Time episodes", statistics.tvtime_episode_count),
        ("Refract episodes", statistics.refract_episode_count),
        ("Missing episodes", statistics.missing_episode_count),
    ]
    for item in diagnostics:
        rows.extend(
            (
                (f"{item.source_file}: rows read", item.rows_read),
                (f"{item.source_file}: rows imported", item.rows_imported),
                (f"{item.source_file}: rows skipped", item.rows_skipped),
            )
        )
        rows.extend(
            (f"{item.source_file}: {reason.value}", count)
            for reason, count in sorted(item.skipped_by_reason.items())
        )
    with path.open("w", encoding="utf-8", newline="") as report_file:
        writer = csv.writer(report_file)
        writer.writerow(("Metric", "Value"))
        writer.writerows(rows)


def _write_missing_shows_csv(result: ComparisonResult, path: Path) -> None:
    fieldnames = (
        "Display Title",
        "Normalized Title",
        "Source",
        "Source Show ID",
        "TMDB ID",
        "TVDB ID",
        "IMDb ID",
        "Watched Episode Count",
    )
    with path.open("w", encoding="utf-8", newline="") as report_file:
        writer = csv.DictWriter(report_file, fieldnames=fieldnames)
        writer.writeheader()
        for show in sorted(
            result.missing_shows, key=lambda item: item.display_title.casefold()
        ):
            writer.writerow(
                {
                    "Display Title": show.display_title,
                    "Normalized Title": show.normalized_title,
                    "Source": show.source,
                    "Source Show ID": show.source_show_id or "",
                    "TMDB ID": show.tmdb_id or "",
                    "TVDB ID": show.tvdb_id or "",
                    "IMDb ID": show.imdb_id or "",
                    "Watched Episode Count": len(show.episodes),
                }
            )


def _write_ambiguous_matches_csv(result: ComparisonResult, path: Path) -> None:
    fieldnames = ("TV Time Title", "Candidate Refract Title", "Confidence")
    with path.open("w", encoding="utf-8", newline="") as report_file:
        writer = csv.DictWriter(report_file, fieldnames=fieldnames)
        writer.writeheader()
        for ambiguous_match in result.ambiguous_matches:
            for candidate in ambiguous_match.candidates:
                writer.writerow(
                    {
                        "TV Time Title": ambiguous_match.tvtime_show.display_title,
                        "Candidate Refract Title": candidate.refract_show.display_title,
                        "Confidence": f"{candidate.confidence:.1f}",
                    }
                )


def _write_missing_episodes_csv(result: ComparisonResult, path: Path) -> None:
    fieldnames = (
        "TV Time Title",
        "Refract Title",
        "Match Method",
        "Season",
        "Episode",
    )
    with path.open("w", encoding="utf-8", newline="") as report_file:
        writer = csv.DictWriter(report_file, fieldnames=fieldnames)
        writer.writeheader()
        for missing_episode in result.missing_episodes:
            writer.writerow(_missing_episode_row(missing_episode))


def _missing_episode_row(missing_episode: MissingEpisode) -> dict[str, str | int]:
    show_match = missing_episode.show_match
    return {
        "TV Time Title": show_match.tvtime_show.display_title,
        "Refract Title": show_match.refract_show.display_title,
        "Match Method": show_match.method,
        "Season": missing_episode.episode_key.season_number,
        "Episode": missing_episode.episode_key.episode_number,
    }


def _write_html_report(
    result: ComparisonResult,
    path: Path,
    diagnostics: tuple[ParseDiagnostics, ...],
) -> None:
    environment = Environment(
        loader=PackageLoader("tvtimecompare.reports", "templates"),
        autoescape=select_autoescape(("html", "xml")),
    )
    template = environment.get_template("report.html.j2")
    path.write_text(
        template.render(
            statistics=result.statistics,
            missing_shows=sorted(
                result.missing_shows, key=lambda item: item.display_title.casefold()
            ),
            ambiguous_matches=result.ambiguous_matches,
            missing_episode_sections=_missing_episode_sections(result.missing_episodes),
            diagnostics=diagnostics,
        ),
        encoding="utf-8",
    )


def _missing_episode_sections(
    missing_episodes: tuple[MissingEpisode, ...],
) -> list[dict[str, object]]:
    grouped: defaultdict[tuple[str, str, str], list[MissingEpisode]] = defaultdict(list)
    for missing_episode in missing_episodes:
        show_match = missing_episode.show_match
        grouped[
            (
                show_match.tvtime_show.display_title,
                show_match.refract_show.display_title,
                show_match.method,
            )
        ].append(missing_episode)

    return [
        {
            "tvtime_title": key[0],
            "refract_title": key[1],
            "method": key[2],
            "episodes": sorted(
                items,
                key=lambda item: (
                    item.episode_key.season_number,
                    item.episode_key.episode_number,
                ),
            ),
        }
        for key, items in sorted(
            grouped.items(), key=lambda item: item[0][0].casefold()
        )
    ]
