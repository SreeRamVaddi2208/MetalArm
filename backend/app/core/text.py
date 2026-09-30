"""What counts as a name a person can read.

The single place that decides, in the same spirit as `security.normalize_email`
and `exercise_names.clean_name`: every path that accepts text a STRANGER will
see - a display name on the league table, a party name, a quest title - runs
through here, or they drift apart and one of them lets something through.

Cleaning and rejecting are deliberately different jobs:

- Whitespace is CLEANED. "Sree  Ram" and " Sree Ram " are the same name typed
  slightly differently, and nobody wants to be told off for a stray space.
- Control and direction characters are REJECTED, not stripped. Somebody who
  pasted a newline into their name has made a mistake worth hearing about, and
  quietly deleting characters from a person's name is its own unpleasant
  surprise. U+202E in particular reverses everything after it - on a
  leaderboard that is a spoofing tool, not a typo.
"""

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")

# C0 and C1 controls. Tab, newline and carriage return are whitespace and are
# collapsed before this ever sees them; what is left is genuinely unprintable.
_CONTROL = {chr(code) for code in [*range(0x00, 0x20), 0x7F, *range(0x80, 0xA0)]}

# Bidirectional overrides and isolates. Legitimate right-to-left text does NOT
# need these - Arabic and Hebrew render correctly from their own characters -
# so their presence in a name is either confusion or intent.
_BIDI = {"‪", "‫", "‬", "‭", "‮",
         "⁦", "⁧", "⁨", "⁩"}


def clean_text(value: str) -> str:
    """Trimmed, inner whitespace collapsed, case untouched."""
    return _WHITESPACE.sub(" ", value).strip()


def human_name(value: str) -> str:
    """A name somebody else will read, or a ValueError saying why not.

    Used as a Pydantic AfterValidator, so the message reaches the client as a
    422 naming the field.
    """
    cleaned = clean_text(value)
    if not cleaned:
        # min_length=1 passes "   ", which then stores blank and shows as a
        # nameless row on every leaderboard.
        raise ValueError("cannot be blank")

    bad = {character for character in cleaned if character in _CONTROL or character in _BIDI}
    if bad:
        names = ", ".join(
            unicodedata.name(character, f"U+{ord(character):04X}") for character in sorted(bad)
        )
        raise ValueError(f"cannot contain {names}")
    return cleaned


# A Pydantic annotation, so a schema says `HumanName` rather than repeating the
# validator six times. Imported by app/schemas/*.
try:  # pragma: no cover - the import is trivial; the behaviour is tested above
    from typing import Annotated

    from pydantic import AfterValidator

    HumanName = Annotated[str, AfterValidator(human_name)]
except ImportError:  # pragma: no cover - core stays importable without pydantic
    HumanName = str  # type: ignore[misc, assignment]
