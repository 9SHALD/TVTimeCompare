"""Episode comparison between TV Time and Refract show collections."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from tvtimecompare.models import EpisodeKey, Show

MatchMethod = Literal["tmdb", "tvdb", "imdb", "title"]


@dataclass(frozen=True, slots=True)
class ShowMatch:
    """A TV Time show paired with its matched Refract show."""

    tvtime_show: Show
    refract_show: Show
    method: MatchMethod


@dataclass(frozen=True, slots=True)
class MissingEpisode:
    """A TV Time episode absent from a matched Refract show."""

    show_match: ShowMatch
    episode_key: EpisodeKey


@dataclass(frozen=True, slots=True)
class ComparisonStatistics:
    """Counts that summarize one TV Time-to-Refract comparison."""

    tvtime_show_count: int
    refract_show_count: int
    matched_show_count: int
    missing_show_count: int
    tvtime_episode_count: int
    refract_episode_count: int
    missing_episode_count: int


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """The matches, gaps, and statistics from comparing two watch histories."""

    matches: tuple[ShowMatch, ...]
    missing_shows: tuple[Show, ...]
    missing_episodes: tuple[MissingEpisode, ...]
    statistics: ComparisonStatistics


def compare_watched_episodes(
    tvtime_shows: Mapping[str, Show], refract_shows: Mapping[str, Show]
) -> ComparisonResult:
    """Compare TV Time watched episodes with Refract watched episodes.

    Matching tries TMDB, TVDB, IMDb, then normalized title. A candidate must be
    unique within the relevant index and cannot be matched to more than one TV
    Time show.
    """
    refract_indexes = _build_indexes(refract_shows.values())
    used_refract_shows: set[int] = set()
    matches: list[ShowMatch] = []
    missing_shows: list[Show] = []
    missing_episodes: list[MissingEpisode] = []

    for tvtime_show in tvtime_shows.values():
        show_match = _find_match(tvtime_show, refract_indexes, used_refract_shows)
        if show_match is None:
            missing_shows.append(tvtime_show)
            continue
        matches.append(show_match)
        used_refract_shows.add(id(show_match.refract_show))
        for episode_key in sorted(
            tvtime_show.episodes.keys() - show_match.refract_show.episodes.keys()
        ):
            missing_episodes.append(MissingEpisode(show_match, episode_key))

    statistics = ComparisonStatistics(
        tvtime_show_count=len(tvtime_shows),
        refract_show_count=len(refract_shows),
        matched_show_count=len(matches),
        missing_show_count=len(missing_shows),
        tvtime_episode_count=sum(len(show.episodes) for show in tvtime_shows.values()),
        refract_episode_count=sum(
            len(show.episodes) for show in refract_shows.values()
        ),
        missing_episode_count=len(missing_episodes),
    )
    return ComparisonResult(
        matches=tuple(matches),
        missing_shows=tuple(missing_shows),
        missing_episodes=tuple(missing_episodes),
        statistics=statistics,
    )


def _build_indexes(
    shows: Iterable[Show],
) -> dict[MatchMethod, dict[str, tuple[Show, ...]]]:
    indexes: dict[MatchMethod, dict[str, list[Show]]] = {
        "tmdb": defaultdict(list),
        "tvdb": defaultdict(list),
        "imdb": defaultdict(list),
        "title": defaultdict(list),
    }
    for show in shows:
        for method, value in _match_values(show).items():
            if value:
                indexes[method][value].append(show)
    return {
        method: {value: tuple(candidates) for value, candidates in values.items()}
        for method, values in indexes.items()
    }


def _find_match(
    tvtime_show: Show,
    indexes: Mapping[MatchMethod, Mapping[str, tuple[Show, ...]]],
    used_refract_shows: set[int],
) -> ShowMatch | None:
    for method, value in _match_values(tvtime_show).items():
        if value is None:
            continue
        candidates = indexes[method].get(value, ())
        if len(candidates) != 1:
            continue
        candidate = candidates[0]
        if id(candidate) not in used_refract_shows:
            return ShowMatch(tvtime_show, candidate, method)
    return None


def _match_values(show: Show) -> dict[MatchMethod, str | None]:
    return {
        "tmdb": _normalize_id(show.tmdb_id),
        "tvdb": _normalize_id(show.tvdb_id),
        "imdb": _normalize_id(show.imdb_id),
        "title": show.normalized_title or None,
    }


def _normalize_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold()
    return normalized or None
