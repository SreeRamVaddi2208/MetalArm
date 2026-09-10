"""The Stat Panel - an RPG character sheet over real progression data."""

import reflex as rx

from levelforge import theme
from levelforge.state.auth import AuthState


def rank_badge() -> rx.Component:
    """The rank letter, coloured per rank.

    rx.match rather than a dict lookup: the colour has to be resolved in the
    compiled component, where a Python dict indexed by a Var is not available.
    """
    color = rx.match(
        AuthState.progress.rank,
        ("E", theme.RANK_COLORS["E"]),
        ("D", theme.RANK_COLORS["D"]),
        ("C", theme.RANK_COLORS["C"]),
        ("B", theme.RANK_COLORS["B"]),
        ("A", theme.RANK_COLORS["A"]),
        ("S", theme.RANK_COLORS["S"]),
        theme.MUTED,
    )
    return rx.vstack(
        rx.text("RANK", **theme.LABEL_STYLE),
        rx.center(
            rx.heading(
                AuthState.progress.rank,
                size="8",
                color=color,
                font_weight="900",
            ),
            width="76px",
            height="76px",
            border=f"2px solid {color}",
            border_radius="16px",
            box_shadow=f"0 0 30px -8px {color}",
        ),
        spacing="2",
        align="center",
    )


def stat_row(label: str, value: rx.Var | str, accent: str = theme.TEXT) -> rx.Component:
    return rx.hstack(
        rx.text(label, **theme.LABEL_STYLE),
        rx.spacer(),
        rx.text(value, color=accent, font_weight="700", font_size="0.95rem"),
        width="100%",
    )


def xp_bar() -> rx.Component:
    """XP bar fill.

    Driven by `transform: scaleX()`, not `width`. Section 7 is explicit about
    this: width is a layout property, so animating it forces the browser to
    reflow on every frame, whereas a transform is handled by the compositor.
    `transform-origin: left` makes the bar grow from its start rather than
    from the centre.
    """
    return rx.vstack(
        rx.hstack(
            rx.text("XP", **theme.LABEL_STYLE),
            rx.spacer(),
            rx.text(
                f"{AuthState.progress.xp_into_level} / {AuthState.progress.xp_for_next_level}",
                color=theme.MUTED,
                font_size="0.8rem",
            ),
            width="100%",
        ),
        rx.box(
            rx.box(
                width="100%",
                height="100%",
                # scaleX from 0..1 rather than a width percentage.
                transform=f"scaleX({AuthState.xp_scale})",
                transform_origin="left center",
                background=f"linear-gradient(90deg, {theme.ACCENT_DIM}, {theme.ACCENT})",
                border_radius="999px",
                transition="transform 620ms cubic-bezier(0.22, 1, 0.36, 1)",
                box_shadow=theme.glow(theme.ACCENT, "22px"),
            ),
            width="100%",
            height="10px",
            background="#0b1220",
            border=f"1px solid {theme.BORDER}",
            border_radius="999px",
            overflow="hidden",
        ),
        spacing="2",
        width="100%",
    )


def gate_notice() -> rx.Component:
    """Shown when the level has earned a rank the streak does not yet allow.

    Without this the user would see the lower badge with no explanation of the
    rank they have actually qualified for.
    """
    return rx.cond(
        AuthState.rank_is_gated,
        rx.box(
            rx.text(
                AuthState.rank_gate_message,
                color=theme.WARNING,
                font_size="0.78rem",
                line_height="1.5",
            ),
            width="100%",
            padding="0.7rem 0.9rem",
            background="#241d0c",
            border=f"1px solid {theme.WARNING}44",
            border_radius="10px",
        ),
    )


def stat_panel() -> rx.Component:
    streak_color = rx.cond(
        AuthState.progress.streak_is_active, theme.SUCCESS, theme.FAINT
    )
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                rx.text("STATUS", **{**theme.LABEL_STYLE, "color": theme.ACCENT}),
                rx.heading(AuthState.display_name, size="6", color=theme.TEXT),
                rx.text(
                    f"LEVEL {AuthState.progress.current_level}",
                    color=theme.MUTED,
                    font_size="0.85rem",
                    letter_spacing="0.12em",
                ),
                spacing="1",
                align="start",
            ),
            rx.spacer(),
            rank_badge(),
            width="100%",
            align="center",
        ),
        rx.divider(border_color=theme.BORDER),
        xp_bar(),
        stat_row("TOTAL XP", AuthState.progress.total_xp.to_string()),
        stat_row("STREAK", AuthState.streak_label, streak_color),
        stat_row("LONGEST", f"{AuthState.progress.longest_streak} DAYS"),
        stat_row("POINTS", AuthState.progress.points_balance.to_string(), theme.WARNING),
        gate_notice(),
        rx.cond(
            AuthState.progress.next_rank != "",
            rx.text(
                f"Next rank {AuthState.progress.next_rank} at level "
                f"{AuthState.progress.next_rank_level}",
                color=theme.FAINT,
                font_size="0.75rem",
            ),
            # Only claim the top of the ladder once data has actually loaded.
            rx.cond(
                AuthState.at_max_rank,
                rx.text(
                    "Maximum rank reached",
                    color=theme.RANK_COLORS["S"],
                    font_size="0.75rem",
                ),
            ),
        ),
        spacing="3",
        **theme.panel(box_shadow=theme.glow(theme.ACCENT, "60px")),
    )
