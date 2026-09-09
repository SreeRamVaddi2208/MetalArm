"""Visual language for LevelForge.

Original work. Inspired by the hunter-rank RPG aesthetic - a dark field, a
single cold glowing accent, wide-tracked uppercase labels - but no Solo Leveling
asset, logo, colour value, or line of copy is reproduced anywhere.

Single source of truth for colour and spacing so pages stay consistent and a
retheme touches one file.
"""

# --- Core palette ----------------------------------------------------------
BG = "#080b12"          # page field
PANEL = "#111726"       # raised surface
PANEL_HI = "#18203100"  # transparent hover wash, layered over PANEL
BORDER = "#1f2a3d"
BORDER_HI = "#2b3a54"

ACCENT = "#38bdf8"      # the one glowing accent
ACCENT_DIM = "#0ea5e9"
SUCCESS = "#34d399"
WARNING = "#fbbf24"
DANGER = "#f87171"

TEXT = "#e8eef8"
MUTED = "#8b9bb4"
FAINT = "#5a6b85"

# --- Rank identity ---------------------------------------------------------
# Each rank gets its own colour so the badge reads at a glance. Ascending
# warmth: cold greys at the bottom, gold at the top.
RANK_COLORS: dict[str, str] = {
    "E": "#8b9bb4",
    "D": "#34d399",
    "C": "#38bdf8",
    "B": "#a78bfa",
    "A": "#fb923c",
    "S": "#fbbf24",
}


def rank_color(rank: str) -> str:
    return RANK_COLORS.get(rank, MUTED)


# --- Reusable style fragments ---------------------------------------------
PANEL_STYLE = {
    "background": PANEL,
    "border": f"1px solid {BORDER}",
    "border_radius": "14px",
    "padding": "1.5rem",
    "width": "100%",
}

LABEL_STYLE = {
    "color": MUTED,
    "font_size": "0.7rem",
    "letter_spacing": "0.18em",
    "font_weight": "700",
}


def panel(**overrides: object) -> dict:
    """PANEL_STYLE merged with per-call overrides.

    Use this rather than spreading `**PANEL_STYLE` beside other props: passing
    `width=` next to it duplicates the key PANEL_STYLE already sets, which
    Reflex reports as `create() got multiple values for keyword argument
    'width'` at COMPILE time. Merging first makes that impossible.
    """
    return {**PANEL_STYLE, **overrides}


def glow(color: str = ACCENT, strength: str = "40px") -> str:
    """Outer glow used sparingly - panels and the rank badge, not every element."""
    return f"0 0 {strength} -14px {color}"
