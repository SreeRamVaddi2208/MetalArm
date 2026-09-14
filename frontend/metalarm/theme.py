"""Visual language for MetalArm.

Original work: a grey, machined-steel identity - a near-black field, graphite
panels, wide-tracked uppercase labels, and white/silver as the only accent.
Red is reserved for errors and destructive actions. The values match the iOS
app's ios/MetalARM/Theme/Theme.swift.

Single source of truth for colour and spacing so pages stay consistent and a
retheme touches one file.
"""

# --- Core palette ----------------------------------------------------------
BG = "#0b0b0c"          # page field
PANEL = "#1a1a1d"       # raised surface
PANEL_HI = "#2a2a2e00"  # transparent hover wash, layered over PANEL
FIELD = "#121214"       # inputs and inset wells
BORDER = "#2a2a2e"
BORDER_HI = "#3a3a40"

ACCENT = "#ffffff"      # white: primary actions and highlights
ACCENT_DIM = "#9a9aa2"  # silver
ON_ACCENT = "#0b0b0c"   # text on a white or silver fill
SUCCESS = "#b8b8bf"
WARNING = "#d4d4da"
DANGER = "#e5484d"      # the one colour left: errors and destructive actions
SUCCESS_BG = "#1c1c1f"
WARNING_BG = "#1e1e21"
DANGER_BG = "#2a1416"
VEIL = "rgba(8, 8, 9, 0.84)"  # behind overlays

TEXT = "#f2f2f4"
MUTED = "#a8a8b0"
FAINT = "#7c7c84"

# --- Rank identity ---------------------------------------------------------
# Each rank gets its own shade so the badge reads at a glance: brighter metal
# the higher the rank, from dark grey at E to white at S.
RANK_COLORS: dict[str, str] = {
    "E": "#5a5a62",
    "D": "#7a7a82",
    "C": "#9a9aa2",
    "B": "#c0c0c8",
    "A": "#e0e0e6",
    "S": "#ffffff",
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
