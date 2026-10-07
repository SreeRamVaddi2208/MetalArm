"""WCAG 2.1 contrast for every text-on-background pair the screens use.

Body text needs 4.5:1. Large numbers (24 px and up) and UI parts - icons,
the accent line, borders of controls - need 3:1. text-3 is for placeholders
and disabled labels only, which WCAG exempts; it is still held to 3:1 on the
backgrounds it sits on so a placeholder stays findable.
"""

import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("theme", Path(__file__).resolve().parents[1] / "metalarm" / "theme.py")
t = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(t)


def _luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _blend(fg_hex: str, opacity: float, bg_hex: str) -> str:
    """accent-soft is the accent at 14% over whatever is under it."""
    f, b = (int(fg_hex[i:i + 2], 16) for i in (1, 3, 5)), (int(bg_hex[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(x * opacity + y * (1 - opacity)):02x}" for x, y in zip(f, b))


def ratio(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


SOFT_ON_BG = _blend(t.ACCENT, 0.14, t.BG)
SOFT_ON_SURFACE = _blend(t.ACCENT, 0.14, t.SURFACE)

BODY = [  # (text, background) - 4.5:1
    (t.TEXT, t.BG), (t.TEXT, t.SURFACE), (t.TEXT, t.SURFACE_2),
    (t.TEXT_2, t.BG), (t.TEXT_2, t.SURFACE), (t.TEXT_2, t.SURFACE_2),
    (t.ON_ACCENT, t.ACCENT),                       # primary button label
    (t.ACCENT, t.BG), (t.ACCENT, t.SURFACE),       # active tab, selected chip text, "PR" pill
    (t.ACCENT, SOFT_ON_BG), (t.ACCENT, SOFT_ON_SURFACE),
    (t.TEXT, SOFT_ON_BG), (t.TEXT, SOFT_ON_SURFACE),   # your leaderboard row, PR rows
    (t.DANGER, t.BG), (t.DANGER, t.SURFACE),       # Delete, Sign out
]
LARGE_OR_UI = [  # 3:1
    (t.TEXT_3, t.BG), (t.TEXT_3, t.SURFACE), (t.TEXT_3, t.SURFACE_2),
    (t.ACCENT, t.SURFACE_2),
]


@pytest.mark.parametrize("fg,bg", BODY)
def test_body_pairs(fg: str, bg: str) -> None:
    assert ratio(fg, bg) >= 4.5, f"{fg} on {bg}: {ratio(fg, bg):.2f}"


@pytest.mark.parametrize("fg,bg", LARGE_OR_UI)
def test_large_and_ui_pairs(fg: str, bg: str) -> None:
    assert ratio(fg, bg) >= 3.0, f"{fg} on {bg}: {ratio(fg, bg):.2f}"
