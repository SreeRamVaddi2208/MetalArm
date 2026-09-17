"""Profile - the Stat Panel as a character sheet, with badges."""

import reflex as rx

from metalarm import theme
from metalarm.components.layout import error_banner, section_heading, shell
from metalarm.components.scroll_reveal import pinned, reveal, reveal_assets
from metalarm.components.stat_panel import stat_panel
from metalarm.models import Badge, StatRow, TrialRow
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


def stat_bar(stat: StatRow) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(
                stat.label,
                color=rx.cond(stat.highlighted, theme.ACCENT, theme.TEXT),
                font_weight="700",
                font_size="0.85rem",
            ),
            rx.spacer(),
            rx.text(stat.value.to_string(), color=theme.TEXT, font_weight="800", font_size="0.85rem"),
            width="100%",
        ),
        rx.box(
            rx.box(
                width=f"{stat.value}%",
                height="100%",
                background=rx.cond(stat.highlighted, theme.ACCENT, theme.ACCENT_DIM),
                border_radius="999px",
            ),
            width="100%",
            height="6px",
            background=theme.FIELD,
            border_radius="999px",
            overflow="hidden",
        ),
        rx.text(stat.detail, color=theme.FAINT, font_size="0.72rem"),
        spacing="2",
        width="100%",
    )


def class_button(value: str, label: str) -> rx.Component:
    chosen = ProfileState.character_class == value
    return rx.button(
        label,
        on_click=ProfileState.choose_class(value),
        background=rx.cond(chosen, theme.ACCENT, "transparent"),
        color=rx.cond(chosen, theme.ON_ACCENT, theme.TEXT),
        border=f"1px solid {theme.BORDER}",
        border_radius="10px",
        font_size="0.72rem",
        font_weight="700",
        letter_spacing="0.06em",
        padding="0.45rem 0.7rem",
        cursor="pointer",
    )


def character_panel() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text("CHARACTER", **theme.LABEL_STYLE),
            rx.spacer(),
            rx.cond(
                ProfileState.class_label != "",
                rx.text(ProfileState.class_label, color=theme.ACCENT, font_size="0.75rem", font_weight="700"),
            ),
            width="100%",
            align="center",
        ),
        rx.divider(border_color=theme.BORDER),
        rx.foreach(ProfileState.stats_sheet, stat_bar),
        rx.text(
            "A class highlights the stats you care about. It never changes a score.",
            color=theme.MUTED,
            font_size="0.72rem",
        ),
        rx.hstack(
            class_button("powerlifter", "POWERLIFTER"),
            class_button("bodybuilder", "BODYBUILDER"),
            class_button("athlete", "ATHLETE"),
            spacing="2",
            wrap="wrap",
        ),
        spacing="3",
        **theme.panel(),
    )


def trial_row(trial: TrialRow) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.center(
                rx.text(trial.rank, font_weight="800", font_size="0.85rem"),
                width="1.75rem",
                height="1.75rem",
                border_radius="8px",
                border=f"1px solid {theme.BORDER}",
                background=rx.cond(trial.passed, theme.ACCENT, theme.FIELD),
                color=rx.cond(trial.passed, theme.ON_ACCENT, theme.TEXT),
                flex_shrink="0",
            ),
            rx.text(trial.description, color=theme.TEXT, font_weight="600", font_size="0.85rem"),
            rx.spacer(),
            rx.cond(trial.passed, rx.icon("badge-check", size=18, color=theme.SUCCESS)),
            width="100%",
            align="center",
        ),
        rx.box(
            rx.box(
                width=f"{trial.pct}%",
                height="100%",
                background=theme.ACCENT,
                border_radius="999px",
            ),
            width="100%",
            height="6px",
            background=theme.FIELD,
            border_radius="999px",
            overflow="hidden",
        ),
        rx.text(trial.progress_label, color=theme.FAINT, font_size="0.72rem"),
        spacing="2",
        width="100%",
    )


def trials_panel() -> rx.Component:
    return rx.vstack(
        rx.text("RANK TRIALS", **theme.LABEL_STYLE),
        rx.text(
            "Ranks B, A and S also need a lift at a multiple of your bodyweight.",
            color=theme.MUTED,
            font_size="0.78rem",
        ),
        rx.divider(border_color=theme.BORDER),
        rx.foreach(ProfileState.trials, trial_row),
        spacing="3",
        **theme.panel(),
    )


def import_panel() -> rx.Component:
    return rx.vstack(
        rx.text("IMPORT HISTORY", **theme.LABEL_STYLE),
        rx.text(
            "Bring your history from Strong or Hevy: export a CSV in the app and drop it here. "
            "Records and rank trials count it; points and streaks don't.",
            color=theme.MUTED,
            font_size="0.78rem",
        ),
        rx.upload(
            rx.vstack(
                rx.icon("upload", size=20, color=theme.MUTED),
                rx.text(
                    rx.cond(ProfileState.importing, "IMPORTING...", "CHOOSE OR DROP A CSV"),
                    color=theme.TEXT,
                    font_weight="700",
                    font_size="0.78rem",
                    letter_spacing="0.08em",
                ),
                align="center",
                spacing="2",
            ),
            id="history_csv",
            accept={"text/csv": [".csv"], "text/plain": [".txt"]},
            max_files=1,
            multiple=False,
            on_drop=ProfileState.import_history(rx.upload_files(upload_id="history_csv")),
            border=f"1px dashed {theme.BORDER}",
            border_radius="12px",
            padding="1.25rem",
            width="100%",
            cursor="pointer",
            background=theme.FIELD,
        ),
        rx.cond(
            ProfileState.import_message != "",
            rx.text(ProfileState.import_message, color=theme.TEXT, font_size="0.8rem"),
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
                rx.cond(ProfileState.stats_sheet.length() > 0, reveal(character_panel())),
                rx.cond(ProfileState.trials.length() > 0, reveal(trials_panel())),
                reveal(import_panel()),
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
