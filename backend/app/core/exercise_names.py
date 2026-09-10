"""Exercise name normalisation - the single place it happens.

exercises.name_key carries the uniqueness rules ("Bench Press" and
"bench  press" are the same exercise), so the importer and the custom-exercise
endpoint must derive it identically. Same pattern as security.normalize_email.
"""

import re

_WHITESPACE = re.compile(r"\s+")
_NON_SLUG = re.compile(r"[^a-z0-9]+")


def clean_name(name: str) -> str:
    """The display name: trimmed, inner whitespace collapsed, case kept."""
    return _WHITESPACE.sub(" ", name).strip()


def name_key(name: str) -> str:
    return clean_name(name).casefold()


def slugify(name: str) -> str:
    return _NON_SLUG.sub("-", name_key(name)).strip("-")
