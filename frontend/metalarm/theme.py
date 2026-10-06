"""MetalArm's design tokens - the ONLY place a colour, type size, radius,
spacing step or blur is written down.

The direction (overhaul, Section 5): pure black, dark grey surfaces, white
bold titles, grey secondary text, ONE accent - blue - for interaction, and
colour otherwise only where it means something (orange streak, green
recovery, red-orange worked muscle, gold record, tier colours for rank).
Inter and the system stack for everything; Space Grotesk survives only as the
game's numerals (rank, points), MetalArm's signature.

Components in metalarm/ui/ read tokens only - frontend/tests/test_tokens.py
fails on a hex colour or a raw size anywhere else. The screens built before
the overhaul read the LEGACY names at the bottom, re-pointed at the new
palette, until each is rebuilt.

Values were estimated from reference screenshots by eye; confirm against a
device capture before treating them as final.
"""

# ---------------------------------------------------------------------------
# Colour
# ---------------------------------------------------------------------------
COLOR_BG = "#000000"
SURFACE_1 = "#1C1C1E"         # cards, list rows, inputs
SURFACE_2 = "#2C2C2E"         # chips, segmented track, delta pills
SURFACE_3 = "#3A3A3C"         # pressed, selected segment
SEPARATOR = "rgba(255,255,255,0.08)"
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#8E8E93"
TEXT_TERTIARY = "#636366"

ACCENT_BLUE = "#0A84FF"       # interaction only: links, selection, play, focus
CHART_LINE = "#3B9EFF"
MUSCLE_ACTIVE = "#E5533D"
STREAK_ORANGE = "#FF9F0A"
RECOVERY_GREEN = "#30D158"
PR_GOLD = "#FFD60A"
DANGER_RED = "#FF453A"

SUMMARY_GRADIENT = "linear-gradient(135deg, #0B1E3F 0%, #1E4E8C 100%)"
TILE_PALETTE = ("#4E4459", "#E57F84", "#3E5C76", "#5B7553",
                "#8C6A4F", "#6B5B95", "#2F6F73", "#A0616A")
TRANSLUCENT_BAR = "rgba(28,28,30,0.72)"   # SURFACE_1 under a blur
SCRIM = "rgba(0,0,0,0.72)"
ON_LIGHT = "#000000"                      # text on the white Start pill

# Rank tiers (E..S): the avatar frame, the rank badge, the rank-up takeover.
TIER_COLORS: dict[str, str] = {
    "E": "#8A6B4E",   # bronze
    "D": "#9AA4AE",   # silver
    "C": "#D4A93C",   # gold
    "B": "#3FB6B0",   # platinum
    "A": "#5BA8FF",   # diamond
    "S": "#C77DFF",   # world class
}


def tier_color(rank: str) -> str:
    return TIER_COLORS.get(rank, TEXT_SECONDARY)


def tile_color(name: str) -> str:
    """A stable colour per routine name, from the tile palette."""
    total = sum(ord(c) for c in name or "?")
    return TILE_PALETTE[total % len(TILE_PALETTE)]


def alpha(color: str, opacity: float) -> str:
    """`color` (#RRGGBB) at `opacity` - for tints without new hex values."""
    value = color.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{opacity})"


# ---------------------------------------------------------------------------
# Type
# ---------------------------------------------------------------------------
FONT_UI = ("Inter, -apple-system, 'SF Pro Display', 'SF Pro Text', system-ui, "
           "'Helvetica Neue', Arial, sans-serif")
FONT_GAME = "'Space Grotesk', Inter, system-ui, sans-serif"
FONT_STYLESHEET = (
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800"
    "&family=Space+Grotesk:wght@500;700&display=swap"
)
TABULAR = {"font_variant_numeric": "tabular-nums"}


def _type(size: int, line: int, weight: int, **extra) -> dict:
    return {"font_size": f"{size}px", "line_height": f"{line}px",
            "font_weight": str(weight), **extra}


LARGE_TITLE = _type(34, 41, 700, letter_spacing="-0.01em")
DISPLAY_NUMBER = _type(40, 44, 700, **TABULAR)
TITLE_1 = _type(28, 34, 700)
TITLE_2 = _type(22, 28, 700)
HEADLINE = _type(17, 22, 600)
BODY = _type(17, 22, 400)
SUBHEAD = _type(15, 20, 400)
FOOTNOTE = _type(13, 18, 400)
CAPTION = _type(11, 13, 500, letter_spacing="0.5px", text_transform="uppercase")
# The game's numerals: rank letters, points, XP.
NUMERAL_GAME = {"font_family": FONT_GAME, **TABULAR}
# Units next to a number: about half its size, same weight, on the baseline.
UNIT_SCALE = 0.52


# ---------------------------------------------------------------------------
# Space, shape, depth
# ---------------------------------------------------------------------------
def space(steps: int) -> str:
    """The 4-point grid: space(4) == "16px"."""
    return f"{steps * 4}px"


GUTTER = space(4)             # screen side padding
GUTTER_WIDE = space(5)
SECTION_GAP = space(8)
CARD_PADDING = space(4)
TOUCH_MIN = "44px"
TAB_BAR_HEIGHT = "64px"
# Content keeps clear of the floating tab bar and Start pill.
TAB_BAR_CLEARANCE = "148px"

RADIUS_CARD = "20px"
RADIUS_THUMB = "12px"
RADIUS_TILE = "16px"
RADIUS_PILL = "999px"
RADIUS_BAR = "32px"
BLUR = "blur(20px)"
HAIRLINE = f"1px solid {SEPARATOR}"
EASE = "cubic-bezier(0.22, 1, 0.36, 1)"
DURATION_FAST = "160ms"
DURATION = "260ms"

# Phone frames the gallery and the screenshot sweep render at.
PHONE_WIDTHS = (375, 430)


# ---------------------------------------------------------------------------
# Legacy names - the pre-overhaul screens read these until each is rebuilt.
# Re-pointed at the new palette, so those screens already sit on black and
# grey; new code must use the tokens above.
# ---------------------------------------------------------------------------
BG = COLOR_BG
PANEL = SURFACE_1
PANEL_HI = "rgba(255,255,255,0)"
FIELD = SURFACE_2
BORDER = SURFACE_2
BORDER_HI = SURFACE_3
ACCENT = TEXT_PRIMARY        # the old primary action fill was white
ACCENT_DIM = TEXT_SECONDARY
ON_ACCENT = ON_LIGHT
SUCCESS = RECOVERY_GREEN
WARNING = STREAK_ORANGE
DANGER = DANGER_RED
SUCCESS_BG = alpha(RECOVERY_GREEN, 0.12)
WARNING_BG = alpha(STREAK_ORANGE, 0.12)
DANGER_BG = alpha(DANGER_RED, 0.14)
VEIL = SCRIM
TEXT = TEXT_PRIMARY
MUTED = TEXT_SECONDARY
FAINT = TEXT_TERTIARY
RANK_COLORS = TIER_COLORS


def rank_color(rank: str) -> str:
    return tier_color(rank)


PANEL_STYLE = {
    "background": PANEL,
    "border": "none",
    "border_radius": RADIUS_CARD,
    "padding": CARD_PADDING,
    "width": "100%",
}

LABEL_STYLE = {
    "color": MUTED,
    "font_size": "0.7rem",
    "letter_spacing": "0.08em",
    "font_weight": "600",
}


def panel(**overrides: object) -> dict:
    """PANEL_STYLE merged with per-call overrides (see the legacy screens)."""
    return {**PANEL_STYLE, **overrides}


def glow(color: str = ACCENT, strength: str = "40px") -> str:
    """Kept for the legacy screens; the new system has no glows."""
    return "none"
