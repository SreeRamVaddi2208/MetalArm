"""Rank letters, as lifting tiers.

The server stores and returns the ladder as letters (E-D-C-B-A-S), and
`trials_passed` records them the same way, so nothing here changes the data:
this is only what the UI says. The tiers match how the rank trials are already
framed - a bench at 1x bodyweight, a squat at 1.5x, a deadlift at 2x.

Keep in step with ios/MetalARM/API/Rank.swift.
"""

import reflex as rx

from metalarm import theme

# Ascending.
RANK_TITLES = {
    "E": "Untrained",
    "D": "Novice",
    "C": "Intermediate",
    "B": "Advanced",
    "A": "Elite",
    "S": "World Class",
}


def rank_title(rank: str) -> str:
    """For a plain Python string. An unknown letter is returned as it came, so a
    rank added server-side is never rendered blank."""
    return RANK_TITLES.get(rank, rank)


def rank_title_var(rank: rx.Var) -> rx.Var:
    """For a Var, resolved with rx.match - a dict indexed by a Var is not
    available in the compiled component, the same reason theme colours use it."""
    return rx.match(
        rank,
        *[(letter, title) for letter, title in RANK_TITLES.items()],
        rank,
    )


def rank_color_var(rank: rx.Var) -> rx.Var:
    """The per-rank colour, still keyed by the letter."""
    return rx.match(
        rank,
        *[(letter, color) for letter, color in theme.RANK_COLORS.items()],
        theme.MUTED,
    )


def titles(letters: list[str]) -> str:
    """"Advanced, Elite and World Class" - the rank trials sentence."""
    names = [rank_title(letter) for letter in letters]
    if len(names) < 2:
        return names[0] if names else ""
    return ", ".join(names[:-1]) + " and " + names[-1]


def promotion(before: str, after: str) -> str:
    """"Intermediate → Advanced", for the rank-up celebration. Empty when the
    two are the same or either is unknown, so the line is simply left out."""
    if not before or not after or before == after:
        return ""
    return f"{rank_title(before)} \u2192 {rank_title(after)}"
