"""RankBadge - the ONE component allowed to use rank tier colours (with the
rank-up overlay, components/level_up.py). A hexagon in the tier's colour with
the rank letter; 24, 48 or 96 px."""

from __future__ import annotations

from typing import Any

import reflex as rx

from metalarm import theme as t

HEXAGON = "polygon(25% 3%, 75% 3%, 100% 50%, 75% 97%, 25% 97%, 0% 50%)"
_LETTER = {24: t.CAPTION, 48: t.TITLE, 96: t.DISPLAY}


def rank_badge(rank: Any, size: int = 48) -> rx.Component:
    color = t.tier_color(rank) if isinstance(rank, str) else rx.match(
        rank, *[(r, c) for r, c in t.TIER_COLORS.items()], t.TEXT_2)
    ring = max(2, size // 16)
    return rx.center(
        rx.center(rx.text(rank, color=color, margin="0", **_LETTER.get(size, t.TITLE)),
                  width=f"{size - 2 * ring}px", height=f"{size - 2 * ring}px", background=t.SURFACE,
                  clip_path=HEXAGON),
        width=f"{size}px", height=f"{size}px", background=color, clip_path=HEXAGON, flex_shrink="0",
        custom_attrs={"role": "img", "aria-label": f"Rank {rank}" if isinstance(rank, str) else "Rank"},
        class_name="ma-rank-badge",
    )
