"""LevelForge frontend entrypoint.

SPRINT 1 SCOPE ONLY. This is a scaffold whose sole job is to prove the
Python -> React/Next.js pipeline compiles and serves, locally and in Docker.
It is intentionally wired to no data.

Frontend Agent (Sonnet) owns everything past this point: the real Stat Panel,
quest board, party views, theme, and the Section 7 animation components. Build
those in levelforge/pages/ and levelforge/components/ - keep animation code out
of state/data modules, per Section 7.
"""

import reflex as rx

# Placeholder palette. Frontend Agent should replace this with a proper theme
# module - original work only, inspired by the hunter-rank aesthetic, never
# copying Solo Leveling assets, logos, or text.
ACCENT = "#38bdf8"
BG = "#0a0e17"
PANEL = "#121826"
BORDER = "#1f2937"
MUTED = "#94a3b8"


def stat_row(label: str, value: str) -> rx.Component:
    return rx.hstack(
        rx.text(label, color=MUTED, font_size="0.8rem", letter_spacing="0.08em"),
        rx.spacer(),
        rx.text(value, color="white", font_weight="600", font_size="0.95rem"),
        width="100%",
    )


def stat_panel_placeholder() -> rx.Component:
    """Structural placeholder for the Stat Panel. No live data behind it."""
    return rx.vstack(
        rx.text(
            "STATUS",
            color=ACCENT,
            font_size="0.75rem",
            letter_spacing="0.3em",
            font_weight="700",
        ),
        rx.heading("HUNTER", size="7", color="white"),
        rx.divider(border_color=BORDER),
        stat_row("LEVEL", "--"),
        stat_row("RANK", "--"),
        stat_row("XP", "-- / --"),
        stat_row("STREAK", "--"),
        rx.divider(border_color=BORDER),
        rx.text(
            "Scaffold only - not connected to the API. "
            "Sprint 1 verifies the build pipeline, nothing more.",
            color=MUTED,
            font_size="0.75rem",
            font_style="italic",
        ),
        spacing="3",
        padding="2rem",
        width="100%",
        max_width="420px",
        background=PANEL,
        border=f"1px solid {BORDER}",
        border_radius="14px",
        box_shadow=f"0 0 40px -12px {ACCENT}55",
    )


def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("LevelForge", size="9", color="white"),
            rx.text("Level up your life.", color=MUTED),
            stat_panel_placeholder(),
            spacing="5",
            align="center",
        ),
        min_height="100vh",
        width="100%",
        background=BG,
        padding="2rem",
    )


# Theme is configured via RadixThemesPlugin in rxconfig.py - passing
# theme= to rx.App() is deprecated in Reflex 0.9 and removed in 1.0.
app = rx.App()
app.add_page(index, route="/", title="LevelForge")
