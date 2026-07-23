"""Domain models for television shows and watched episodes."""

from dataclasses import dataclass, field


@dataclass(frozen=True, order=True, slots=True)
class Episode:
    """A uniquely identified episode within a television show."""

    season_number: int
    episode_number: int


@dataclass(slots=True)
class Show:
    """A television show and its unique watched episodes.

    The normalized title is used as the stable dictionary key when comparing
    exports. External IDs are optional because they are not available in every
    TV Time export row.
    """

    original_title: str
    normalized_title: str
    watched_episodes: set[Episode] = field(default_factory=set)
    tmdb_id: str | None = None
    tvdb_id: str | None = None
    imdb_id: str | None = None
    source_id: str | None = None
