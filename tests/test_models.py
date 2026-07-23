"""Tests for the internal comparison data model."""

from dataclasses import FrozenInstanceError

import pytest

from tvtimecompare.models import Episode, EpisodeKey, Show


def test_episode_and_key_are_immutable() -> None:
    """Episode comparison values cannot be changed after construction."""
    episode = Episode(2, 4, "episode-42")
    key = EpisodeKey(2, 4)

    with pytest.raises(FrozenInstanceError):
        episode.season_number = 3  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        key.episode_number = 5  # type: ignore[misc]


def test_episode_exposes_its_coordinate_key() -> None:
    """An episode derives the key used by a show's episode dictionary."""
    assert Episode(2, 4, "episode-42").key == EpisodeKey(2, 4)


def test_show_stores_episodes_by_key_without_overwriting_first_watch() -> None:
    """A show keeps the first source record for a repeated logical episode."""
    show = Show(
        display_title="Example Show",
        normalized_title="example show",
        source="tvtime",
        source_show_id="show-1",
    )
    first_watch = Episode(1, 2, "episode-1")

    assert show.add_episode(first_watch) is True
    assert show.add_episode(Episode(1, 2, "episode-1-rewatch")) is False

    assert show.episodes == {EpisodeKey(1, 2): first_watch}
    assert show.original_title == "Example Show"
    assert show.watched_episodes == {first_watch}
