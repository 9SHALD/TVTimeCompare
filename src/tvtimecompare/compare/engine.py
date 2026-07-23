"""Episode comparison between TV Time and Refract show collections."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from rapidfuzz import fuzz, process

from tvtimecompare.models import EpisodeKey, Show

ExactMatchMethod = Literal["tmdb", "tvdb", "imdb", "title"]
MatchMethod = ExactMatchMethod | Literal["fuzzy"]


@dataclass(frozen=True, slots=True)
class MatchingConfig:
    """Configuration for conservative fuzzy title matching."""

    fuzzy_confidence_threshold: float = 90.0
    fuzzy_ambiguity_threshold: float = 3.0

    def __post_init__(self) -> None:
        """Validate score thresholds expressed on RapidFuzz's 0–100 scale."""
        if not 0 <= self.fuzzy_confidence_threshold <= 100:
            raise ValueError("fuzzy_confidence_threshold must be between 0 and 100.")
        if self.fuzzy_ambiguity_threshold < 0:
            raise ValueError("fuzzy_ambiguity_threshold must be non-negative.")


@dataclass(frozen=True, slots=True)
class ShowMatch:
    """A TV Time show paired with its matched Refract show."""

    tvtime_show: Show
    refract_show: Show
    method: MatchMethod
    confidence: float


@dataclass(frozen=True, slots=True)
class FuzzyCandidate:
    """A scored Refract title candidate for an unresolved TV Time show."""

    refract_show: Show
    confidence: float


@dataclass(frozen=True, slots=True)
class AmbiguousMatch:
    """A TV Time show with multiple fuzzy candidates too close to choose safely."""

    tvtime_show: Show
    candidates: tuple[FuzzyCandidate, ...]


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
    ambiguous_show_count: int
    tvtime_episode_count: int
    refract_episode_count: int
    missing_episode_count: int


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """The matches, gaps, and statistics from comparing two watch histories."""

    matches: tuple[ShowMatch, ...]
    missing_shows: tuple[Show, ...]
    ambiguous_matches: tuple[AmbiguousMatch, ...]
    missing_episodes: tuple[MissingEpisode, ...]
    statistics: ComparisonStatistics


def compare_watched_episodes(
    tvtime_shows: Mapping[str, Show],
    refract_shows: Mapping[str, Show],
    matching_config: MatchingConfig | None = None,
) -> ComparisonResult:
    """Compare TV Time watched episodes with Refract watched episodes.

    Exact matching tries TMDB, TVDB, IMDb, then normalized title. Fuzzy matching
    runs only after all exact matches are complete. A candidate must be unique
    and cannot be matched to more than one TV Time show.
    """
    config = matching_config or MatchingConfig()
    refract_indexes = _build_indexes(refract_shows.values())
    used_refract_shows: set[int] = set()
    matches: list[ShowMatch] = []
    missing_shows: list[Show] = []
    ambiguous_matches: list[AmbiguousMatch] = []
    missing_episodes: list[MissingEpisode] = []
    unmatched_tvtime_shows: list[Show] = []

    for tvtime_show in tvtime_shows.values():
        show_match = _find_exact_match(
            tvtime_show, refract_indexes, used_refract_shows
        )
        if show_match is None:
            unmatched_tvtime_shows.append(tvtime_show)
            continue
        _record_match(show_match, matches, missing_episodes)
        used_refract_shows.add(id(show_match.refract_show))

    for tvtime_show in unmatched_tvtime_shows:
        fuzzy_result = _find_fuzzy_match(
            tvtime_show,
            refract_shows.values(),
            used_refract_shows,
            config,
        )
        if isinstance(fuzzy_result, ShowMatch):
            _record_match(fuzzy_result, matches, missing_episodes)
            used_refract_shows.add(id(fuzzy_result.refract_show))
        elif isinstance(fuzzy_result, AmbiguousMatch):
            ambiguous_matches.append(fuzzy_result)
        else:
            missing_shows.append(tvtime_show)

    statistics = ComparisonStatistics(
        tvtime_show_count=len(tvtime_shows),
        refract_show_count=len(refract_shows),
        matched_show_count=len(matches),
        missing_show_count=len(missing_shows),
        ambiguous_show_count=len(ambiguous_matches),
        tvtime_episode_count=sum(len(show.episodes) for show in tvtime_shows.values()),
        refract_episode_count=sum(
            len(show.episodes) for show in refract_shows.values()
        ),
        missing_episode_count=len(missing_episodes),
    )
    return ComparisonResult(
        matches=tuple(matches),
        missing_shows=tuple(missing_shows),
        ambiguous_matches=tuple(ambiguous_matches),
        missing_episodes=tuple(missing_episodes),
        statistics=statistics,
    )


def _build_indexes(
    shows: Iterable[Show],
) -> dict[ExactMatchMethod, dict[str, tuple[Show, ...]]]:
    indexes: dict[ExactMatchMethod, dict[str, list[Show]]] = {
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


def _find_exact_match(
    tvtime_show: Show,
    indexes: Mapping[ExactMatchMethod, Mapping[str, tuple[Show, ...]]],
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
            return ShowMatch(tvtime_show, candidate, method, confidence=100.0)
    return None


def _find_fuzzy_match(
    tvtime_show: Show,
    refract_shows: Iterable[Show],
    used_refract_shows: set[int],
    config: MatchingConfig,
) -> ShowMatch | AmbiguousMatch | None:
    candidates = [
        show
        for show in refract_shows
        if id(show) not in used_refract_shows and show.normalized_title
    ]
    if not candidates or not tvtime_show.normalized_title:
        return None
    scored = process.extract(
        tvtime_show.normalized_title,
        [show.normalized_title for show in candidates],
        scorer=fuzz.ratio,
        limit=2,
    )
    if not scored:
        return None

    fuzzy_candidates = tuple(
        FuzzyCandidate(candidates[index], float(score))
        for _, score, index in scored
    )
    best_candidate = fuzzy_candidates[0]
    if best_candidate.confidence < config.fuzzy_confidence_threshold:
        return None
    if len(fuzzy_candidates) > 1:
        runner_up = fuzzy_candidates[1]
        confidence_gap = best_candidate.confidence - runner_up.confidence
        if confidence_gap <= config.fuzzy_ambiguity_threshold:
            return AmbiguousMatch(tvtime_show, fuzzy_candidates)
    return ShowMatch(
        tvtime_show,
        best_candidate.refract_show,
        method="fuzzy",
        confidence=best_candidate.confidence,
    )


def _record_match(
    show_match: ShowMatch,
    matches: list[ShowMatch],
    missing_episodes: list[MissingEpisode],
) -> None:
    """Store a show match and its episode-level gaps."""
    matches.append(show_match)
    for episode_key in sorted(
        show_match.tvtime_show.episodes.keys()
        - show_match.refract_show.episodes.keys()
    ):
        missing_episodes.append(MissingEpisode(show_match, episode_key))


def _match_values(show: Show) -> dict[ExactMatchMethod, str | None]:
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
