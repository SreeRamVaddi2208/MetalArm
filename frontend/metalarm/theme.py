"""MetalArm's design tokens - the ONLY place a colour, type size, radius,
spacing step or duration is written down. (The redesign spec calls this module
`tokens.py`; it keeps the name every screen already imports.)

The system (docs/DESIGN_SYSTEM.md): dark-first, seven neutrals, ONE accent
(Forge orange) and one danger colour - nothing else in the everyday UI.
Tokens are named by role, never by colour, so a light theme is a token swap.
Rank tier colours exist only for RankBadge and the rank-up overlay.

Components read tokens only - frontend/tests/test_tokens.py fails on a hex
colour, a raw size or radius anywhere else, and on tier colours outside their
two homes. frontend/tests/test_contrast.py checks every text/background pair
against WCAG AA.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Colour - 7 neutrals, 1 accent, 1 danger
# ---------------------------------------------------------------------------
BG = "#0E0E10"            # app background
SURFACE = "#17171A"       # cards, sheets, tab bar
SURFACE_2 = "#202024"     # inputs, pressed states, nested rows
BORDER = "#2A2A2F"        # 1px hairlines and input outlines only
TEXT = "#F4F4F2"          # primary text and hero numbers
TEXT_2 = "#A1A1A8"        # labels, secondary info
TEXT_3 = "#6E6E76"        # placeholders, ghost "last time" values, disabled - never needed to act  (spec #66666E: 2.85:1 on surface-2; see FLAGS.md)

ACCENT = "#FF6B2C"        # Forge: primary button, active tab, progress fills, PR highlight
ON_ACCENT = "#0E0E10"     # text and icons sitting on the accent
DANGER = "#E5484D"        # destructive actions only


def alpha(color: str, opacity: float) -> str:
    """`color` (#RRGGBB) at `opacity`."""
    value = color.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{opacity})"


ACCENT_SOFT = alpha(ACCENT, 0.14)   # selected chip/card background, PR row tint
SCRIM = "rgba(0,0,0,0.6)"           # behind sheets and dialogs
HAIRLINE = f"1px solid {BORDER}"

# Rank tiers (E..S). ONLY ui/rank_badge.py and the rank-up overlay
# (components/level_up.py) may read these - the lint enforces it.
TIER_COLORS: dict[str, str] = {
    "E": "#8A6B4E",   # bronze
    "D": "#9AA4AE",   # silver
    "C": "#D4A93C",   # gold
    "B": "#3FB6B0",   # platinum
    "A": "#5BA8FF",   # diamond
    "S": "#C77DFF",   # royal
}


def tier_color(rank: str) -> str:
    """For RankBadge and the rank-up overlay only."""
    return TIER_COLORS.get(rank, TEXT_2)


# ---------------------------------------------------------------------------
# Type - Space Grotesk for numbers and headings, Manrope for everything else.
# Three sizes per screen at most: a display number, a title, body/caption.
# ---------------------------------------------------------------------------
FONT_HEAD = "'Space Grotesk', Manrope, system-ui, sans-serif"
FONT_BODY = "Manrope, -apple-system, system-ui, 'Helvetica Neue', Arial, sans-serif"
FONT_STYLESHEET = (
    "https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700"
    "&family=Space+Grotesk:wght@500;600&display=swap"
)
TABULAR = {"font_variant_numeric": "tabular-nums"}


def _type(font: str, size: int, line: int, weight: int) -> dict:
    return {"font_family": font, "font_size": f"{size}px", "line_height": f"{line}px",
            "font_weight": str(weight), **TABULAR}


DISPLAY = _type(FONT_HEAD, 48, 52, 600)      # the hero number: timer, set weight, rank
TITLE_LG = _type(FONT_HEAD, 28, 34, 600)     # screen title
TITLE = _type(FONT_HEAD, 20, 26, 600)        # section and card titles
BODY = _type(FONT_BODY, 16, 24, 500)         # default text
LABEL = _type(FONT_BODY, 14, 20, 600)        # buttons, row labels
CAPTION = _type(FONT_BODY, 12, 16, 500)      # meta, units, timestamps

# ---------------------------------------------------------------------------
# Space, shape, motion
# ---------------------------------------------------------------------------
SPACE = (0, 4, 8, 12, 16, 24, 32, 48)


def space(px: int) -> str:
    """One of the allowed steps, as CSS: space(16) == "16px"."""
    if px not in SPACE:
        raise ValueError(f"{px}px is not on the spacing scale {SPACE}")
    return f"{px}px"


GUTTER = "20px"           # screen side padding
SECTION_GAP = space(32)
CARD_PADDING = space(16)
TOUCH = "48px"            # minimum tap target
ICON_HIT = "44px"         # IconButton hit area
ROW_MIN = "56px"          # ListRow minimum height
BUTTON_HEIGHT = "52px"
MAX_WIDTH = "430px"       # the app column; centred on wide screens
TAB_BAR_HEIGHT = "64px"
# Content keeps clear of the tab bar and anything pinned above it.
BOTTOM_CLEARANCE = "160px"
# Where a toast or banner floats: above the tab bar AND the pinned button.
FLOAT_BOTTOM = f"calc({TAB_BAR_HEIGHT} + 12px + {BUTTON_HEIGHT} + 16px + env(safe-area-inset-bottom))"
# A toast stacks one slot above that, so it never covers the PR banner.
TOAST_BOTTOM = f"calc({TAB_BAR_HEIGHT} + 12px + {BUTTON_HEIGHT} + 16px + 56px + env(safe-area-inset-bottom))"

RADIUS = "12px"           # cards and inputs
RADIUS_SHEET = "16px"     # sheets (top corners)
RADIUS_PILL = "999px"     # buttons and chips

FAST = "150ms"            # taps and toggles
BASE = "250ms"            # sheets and screen transitions
EASE = "cubic-bezier(0.22, 1, 0.36, 1)"   # ease-out

# Phone widths the design-system page and the screenshot sweep render at.
PHONE_WIDTHS = (360, 390, 430)


def css_variables() -> str:
    """Every token as a CSS custom property on :root."""
    pairs = {
        "bg": BG, "surface": SURFACE, "surface-2": SURFACE_2, "border": BORDER,
        "text": TEXT, "text-2": TEXT_2, "text-3": TEXT_3, "accent": ACCENT,
        "accent-soft": ACCENT_SOFT, "on-accent": ON_ACCENT, "danger": DANGER, "scrim": SCRIM,
        "radius": RADIUS, "radius-sheet": RADIUS_SHEET, "fast": FAST, "base": BASE, "ease": EASE,
        "font-head": FONT_HEAD, "font-body": FONT_BODY,
    }
    return ":root { " + "; ".join(f"--ma-{k}: {v}" for k, v in pairs.items()) + "; }"
