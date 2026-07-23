"""Tests for watch-history comparison."""

from typing import Literal

from tvtimecompare.compare import compare_watched_episodes
from tvtimecompare.models import Episode, EpisodeKey, Show


def _show(
    title: str,
    source: Literal["tvtime", "refract"],
    episodes: tuple[tuple[int, int], ...] = (),
    **identifiers: str,
) -> Show:
    show = Show(
        display_title=title,
        normalized_title=title.casefold(),
        source=source,
        **identifiers,
    )
    for season, episode in episodes:
        show.add_episode(Episode(season, episode))
    return show


def test_comparison_matches_in_identifier_priority_order() -> None:
    """TMDB takes precedence over TVDB, IMDb, and title when all are available."""
    tvtime_show = _show(
        "TV Time Title",
        "tvtime",
        tmdb_id="tmdb-1",
        tvdb_id="tvdb-1",
        imdb_id="tt1",
    )
    tmdb_match = _show("Different Title", "refract", tmdb_id="TMDB-1")
    tvdb_match = _show("TV Time Title", "refract", tvdb_id="tvdb-1")

    result = compare_watched_episodes(
        {"tvtime": tvtime_show}, {"tmdb": tmdb_match, "tvdb": tvdb_match}
    )

    assert result.matches[0].refract_show is tmdb_match
    assert result.matches[0].method == "tmdb"


def test_comparison_uses_tvdb_imdb_then_normalized_title() -> None:
    """Each lower-priority matcher is used when earlier identifiers are absent."""
    tvdb_tvtime = _show("TVDB", "tvtime", tvdb_id="tvdb-1")
    imdb_tvtime = _show("IMDb", "tvtime", imdb_id="tt2")
    title_tvtime = _show("Shared Title", "tvtime")
    tvdb_refract = _show("Different", "refract", tvdb_id="tvdb-1")
    imdb_refract = _show("Different Again", "refract", imdb_id="TT2")
    title_refract = _show("Shared Title", "refract")

    result = compare_watched_episodes(
        {"tvdb": tvdb_tvtime, "imdb": imdb_tvtime, "title": title_tvtime},
        {"tvdb": tvdb_refract, "imdb": imdb_refract, "title": title_refract},
    )

    assert [match.method for match in result.matches] == ["tvdb", "imdb", "title"]


def test_comparison_reports_missing_shows_episodes_and_statistics() -> None:
    """The result includes unmatched shows and missing episode coordinates."""
    matched_tvtime = _show("Matched", "tvtime", ((1, 1), (1, 2)))
    missing_tvtime = _show("Missing", "tvtime", ((1, 1),))
    refract = _show("Matched", "refract", ((1, 1), (2, 1)))

    result = compare_watched_episodes(
        {"matched": matched_tvtime, "missing": missing_tvtime},
        {"matched": refract},
    )

    assert result.missing_shows == (missing_tvtime,)
    missing_episode_details = [
        (item.show_match.method, item.episode_key) for item in result.missing_episodes
    ]
    assert missing_episode_details == [("title", EpisodeKey(1, 2))]
    assert result.statistics.tvtime_show_count == 2
    assert result.statistics.refract_show_count == 1
    assert result.statistics.matched_show_count == 1
    assert result.statistics.missing_show_count == 1
    assert result.statistics.tvtime_episode_count == 3
    assert result.statistics.refract_episode_count == 2
    assert result.statistics.missing_episode_count == 1


def test_comparison_does_not_match_ambiguous_or_reused_candidates() -> None:
    """Ambiguous titles and already used Refract shows remain unmatched."""
    ambiguous = _show("Shared", "tvtime")
    first_same_id = _show("First", "tvtime", tmdb_id="id-1")
    second_same_id = _show("Second", "tvtime", tmdb_id="id-1")
    refract_one = _show("Shared", "refract")
    refract_two = _show("Shared", "refract")
    id_match = _show("Other", "refract", tmdb_id="id-1")

    result = compare_watched_episodes(
        {"ambiguous": ambiguous, "first": first_same_id, "second": second_same_id},
        {"one": refract_one, "two": refract_two, "id": id_match},
    )

    assert [match.tvtime_show for match in result.matches] == [first_same_id]
    assert result.missing_shows == (ambiguous, second_same_id)
