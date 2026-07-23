"""Utilities for producing stable, comparable television-show titles."""

import re
import unicodedata

_NON_ALPHANUMERIC = re.compile(r"[^\w]+", flags=re.UNICODE)
_UNDERSCORES = re.compile(r"_+")


def normalize_title(title: str) -> str:
    """Return a case-insensitive, accent- and punctuation-insensitive title.

    The result is suitable as a stable key and is intentionally shared by all
    readers so titles from different sources are compared consistently.
    """
    decomposed = unicodedata.normalize("NFKD", title)
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    normalized = _NON_ALPHANUMERIC.sub(" ", without_accents.casefold())
    return _UNDERSCORES.sub(" ", normalized).strip()
