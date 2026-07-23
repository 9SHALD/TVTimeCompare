"""Comparison and title-matching logic."""

from tvtimecompare.compare.engine import (
    AmbiguousMatch,
    ComparisonResult,
    ComparisonStatistics,
    FuzzyCandidate,
    MatchingConfig,
    MissingEpisode,
    ShowMatch,
    compare_watched_episodes,
)

__all__ = [
    "ComparisonResult",
    "ComparisonStatistics",
    "AmbiguousMatch",
    "FuzzyCandidate",
    "MatchingConfig",
    "MissingEpisode",
    "ShowMatch",
    "compare_watched_episodes",
]
