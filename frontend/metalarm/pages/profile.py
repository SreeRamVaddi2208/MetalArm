"""Profile - the Stat Panel as a character sheet, with badges."""

import reflex as rx

from metalarm import theme
from metalarm.components.layout import error_banner, section_heading, shell
from metalarm.components.scroll_reveal import pinned, reveal, reveal_assets
from metalarm.components.stat_panel import stat_panel
from metalarm.models import Badge
from metalarm.state.profile import ProfileState


def badge_tile(badge: Badge) -> rx.Component:
    earned = badge.earned
    return rx.box(
        rx.vstack(
            rx.text(
                badge.icon,
                font_size="1.6rem",
                line_height="1",
                # Unearned badges are desaturated rather than hidden, so the
                # panel shows what there is to aim at.
                filter=rx.cond(earned, "none", "grayscale(1)"),
                opacity=rx.cond(earned, "1", "0.45"),
            ),
            rx.text(
                badge.name,
                color=rx.cond(earned, theme.TEXT, theme.FAINT),
                font_weight="700",
                font_size="0.8rem",
                text_align="center",
            ),
            rx.text(
                badge.description,
                color=theme.FAINT,
                font_size="0.68rem",
                text_align="center",
                line_height="1.4",
            ),
            rx.cond(
                earned,
                rx.text(
                    "EARNED",
                    color=theme.SUCCESS,
                    font_size="0.6rem",
                    letter_spacing="0.14em",
                    font_weight="800",
                ),
                rx.vstack(
                    rx.box(
                        rx.box(
                            width="100%",
                            height="100%",
                            # scaleX, not width - a compositor property, same
                            # rule as the XP bar.
                            transform=f"scaleX({badge.scale})",
                            transform_origin="left center",
                            background=theme.BORDER_HI,
                            border_radius="999px",
                        ),
                        width="100%",
                        height="4px",
                        background=theme.FIELD,
                        border_radius="999px",
                        overflow="hidden",
                    ),
                    rx.text(
                        badge.progress_label,
                        color=theme.FAINT,
                        font_size="0.62rem",
                    ),
                    spacing="1",
                    width="100%",
                    align="center",
                ),
            ),
            spacing="2",
            align="center",
            width="100%",
        ),
        padding="1rem 0.75rem",
        background=theme.PANEL,
        border=f"1px solid {rx.cond(earned, theme.BORDER_HI, theme.BORDER)}",
        border_radius="12px",
        box_shadow=rx.cond(earned, theme.glow(theme.ACCENT, "34px"), "none"),
        height="100%",
    )


def stat_line(label: str, value: rx.Var | str) -> rx.Component:
    return rx.hstack(
        rx.text(label, **theme.LABEL_STYLE),
        rx.spacer(),
        rx.text(value, color=theme.TEXT, font_weight="700", font_size="0.9rem"),
        width="100%",
    )


def lifetime_panel() -> rx.Component:
    s = ProfileState.stats
    return rx.vstack(
        rx.text("LIFETIME", **theme.LABEL_STYLE),
        rx.divider(border_color=theme.BORDER),
        stat_line("QUESTS COMPLETED", s.quests_completed.to_string()),
        stat_line("PARTY QUESTS", s.party_quests_completed.to_string()),
        stat_line("POINTS EARNED", s.points_earned.to_string()),
        stat_line("POINTS SPENT", s.points_spent.to_string()),
        stat_line("REWARDS REDEEMED", s.rewards_redeemed.to_string()),
        stat_line("PARTIES", s.parties_joined.to_string()),
        stat_line("PARTY XP", s.party_xp_contributed.to_string()),
        rx.divider(border_color=theme.BORDER),
        rx.text("TRAINING", **{**theme.LABEL_STYLE, "color": theme.ACCENT}),
        stat_line("WORKOUTS", s.workouts_completed.to_string()),
        stat_line("PR SETS", s.workout_prs.to_string()),
        stat_line("VOLUME LIFTED", s.volume_label),
        stat_line("BEST WEEK STREAK", s.streak_label),
        rx.divider(border_color=theme.BORDER),
        rx.text(
            f"Hunter since {s.member_since}",
            color=theme.FAINT,
            font_size="0.72rem",
        ),
        spacing="3",
        **theme.panel(),
    )


def profile_page() -> rx.Component:
    return shell(
        reveal_assets(),
        error_banner(ProfileState.error),
        rx.flex(
            rx.box(
                pinned(stat_panel()),
                width=rx.breakpoints(initial="100%", lg="340px"),
                flex_shrink="0",
            ),
            rx.vstack(
                reveal(lifetime_panel()),
                rx.vstack(
                    section_heading(
                        "BADGES",
                        rx.text(
                            ProfileState.badge_summary,
                            color=theme.FAINT,
                            font_size="0.72rem",
                        ),
                    ),
                    rx.grid(
                        rx.foreach(ProfileState.badges, badge_tile),
                        columns=rx.breakpoints(initial="2", md="3"),
                        gap="0.75rem",
                        width="100%",
                    ),
                    spacing="3",
                    width="100%",
                ),
                spacing="5",
                width="100%",
                flex="1",
                min_width="0",
            ),
            direction=rx.breakpoints(initial="column", lg="row"),
            gap="1.25rem",
            width="100%",
            align="start",
        ),
    )
