"""Domain models for television shows and watched episodes."""

from dataclasses import dataclass, field
from typing import Literal

SourceName = Literal["tvtime", "refract"]


@dataclass(frozen=True, order=True, slots=True)
class EpisodeKey:
    """The season and episode coordinates that identify a logical episode."""

    season_number: int
    episode_number: int


@dataclass(frozen=True, order=True, slots=True)
class Episode:
    """An immutable watched episode, optionally retaining its source record ID."""

    season_number: int
    episode_number: int
    source_episode_id: str | None = field(default=None, compare=False)

    @property
    def key(self) -> EpisodeKey:
        """Return the comparison key for this episode."""
        return EpisodeKey(self.season_number, self.episode_number)


@dataclass(slots=True)
class Show:
    """A source show with watched episodes keyed by their logical coordinates."""

    display_title: str
    normalized_title: str
    source: SourceName
    source_show_id: str | None = None
    episodes: dict[EpisodeKey, Episode] = field(default_factory=dict)

    def add_episode(self, episode: Episode) -> bool:
        """Add an episode unless its logical key is already present.

        Returns:
            ``True`` when the episode was added, otherwise ``False``.
        """
        if episode.key in self.episodes:
            return False
        self.episodes[episode.key] = episode
        return True

    @property
    def original_title(self) -> str:
        """Return the display title using the previous public attribute name."""
        return self.display_title

    @property
    def watched_episodes(self) -> set[Episode]:
        """Return watched episodes as a set for backwards-compatible reads."""
        return set(self.episodes.values())
