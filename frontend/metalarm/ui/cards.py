"""Cards and tiles: the Monthly Summary hero, muscle and equipment tiles,
routine tiles, the feed card, the game strip and the ring metric."""

from __future__ import annotations

from typing import Any

import reflex as rx

from metalarm import theme as t
from metalarm.ui.assets import EQUIPMENT_ICONS, equipment_icon
from metalarm.ui.chrome import avatar
from metalarm.ui.primitives import number, text, thumb, when


def hero_card(title: Any, subtitle: Any, on_play: Any = None) -> rx.Component:
    """The story-style recap card: gradient, title, a big white play button."""
    return rx.hstack(
        rx.vstack(text(title, t.TITLE_1), text(subtitle, t.SUBHEAD, t.TEXT_SECONDARY),
                  spacing="1", align="start", flex="1", min_width="0"),
        rx.center(rx.icon("play", size=26, fill=t.ON_LIGHT, color=t.ON_LIGHT),
                  width="64px", height="64px", border_radius=t.RADIUS_PILL,
                  background=t.TEXT_PRIMARY, cursor="pointer", on_click=on_play,
                  flex_shrink="0", custom_attrs={"role": "button", "aria-label": "Play"}),
        background=t.SUMMARY_GRADIENT,
        border_radius=t.RADIUS_CARD,
        padding=t.space(5),
        width="100%",
        align="center",
        spacing="3",
    )


def muscle_tile(label: Any, body_map_view: rx.Component, on_click: Any = None) -> rx.Component:
    """A muscle group with its region lit on a small body map."""
    return rx.vstack(
        rx.center(body_map_view, width="100%", aspect_ratio="1", background=t.SURFACE_1,
                  border_radius=t.RADIUS_TILE, padding=t.space(2)),
        text(label, t.SUBHEAD, text_align="center"),
        spacing="2",
        align="center",
        width="100%",
        cursor="pointer",
        on_click=on_click,
    )


def _equipment_glyph(code: Any) -> rx.Component:
    """Icons are named at compile time, so a Var code picks among them with a
    match rather than a lookup."""
    style = {"size": 30, "color": t.TEXT_PRIMARY, "stroke_width": 1.6}
    if isinstance(code, str):
        return rx.icon(equipment_icon(code), **style)
    return rx.match(code, *[(c, rx.icon(name, **style)) for c, name in EQUIPMENT_ICONS.items()],
                    rx.icon("shapes", **style))


def equipment_circle(code: Any, label: Any, on_click: Any = None) -> rx.Component:
    return rx.vstack(
        rx.center(_equipment_glyph(code),
                  width="76px", height="76px", border_radius=t.RADIUS_PILL, background=t.SURFACE_1),
        text(label, t.FOOTNOTE, text_align="center"),
        spacing="2",
        align="center",
        cursor="pointer",
        on_click=on_click,
    )


def routine_tile(name: Any, abbreviation: Any, color: Any, last_done: Any,
                 on_click: Any = None) -> rx.Component:
    """A coloured square with a two-letter mark, the name under it, and when
    it was last done."""
    return rx.vstack(
        rx.center(text(abbreviation, t.TITLE_1), width="132px", height="132px",
                  background=color, border_radius=t.RADIUS_TILE),
        text(name, t.HEADLINE, overflow="hidden", text_overflow="ellipsis",
             white_space="nowrap", max_width="132px"),
        rx.hstack(rx.icon("clock", size=13, color=t.TEXT_SECONDARY),
                  text(last_done, t.FOOTNOTE, t.TEXT_SECONDARY), spacing="1", align="center"),
        spacing="1",
        align="start",
        cursor="pointer",
        on_click=on_click,
        flex_shrink="0",
    )


def ring_metric(percent: Any, label: Any, *, color: str = t.RECOVERY_GREEN,
                size: int = 96) -> rx.Component:
    """A circular progress ring with the number in the middle."""
    radius = 42
    circumference = 2 * 3.14159 * radius
    offset = (circumference * (1 - percent / 100)) if isinstance(percent, (int, float)) else (
        circumference - percent * circumference / 100)
    return rx.vstack(
        rx.box(
            rx.el.svg(
                rx.el.circle(cx="50", cy="50", r=str(radius), fill="none",
                             stroke=t.SURFACE_2, stroke_width="9"),
                rx.el.circle(cx="50", cy="50", r=str(radius), fill="none", stroke=color,
                             stroke_width="9", stroke_linecap="round",
                             stroke_dasharray=str(circumference), stroke_dashoffset=offset,
                             transform="rotate(-90 50 50)"),
                view_box="0 0 100 100", width=f"{size}px", height=f"{size}px",
            ),
            rx.center(number(percent, "%", style=t.HEADLINE), position="absolute", inset="0"),
            position="relative",
            width=f"{size}px",
            height=f"{size}px",
        ),
        text(label, t.FOOTNOTE, t.TEXT_SECONDARY),
        spacing="1",
        align="center",
    )


def game_strip(rank: Any, rank_title: Any, xp_now: Any, xp_next: Any, next_tier: Any,
               points_week: Any, quests_label: Any, xp_scale: Any = 0.5,
               on_click: Any = None) -> rx.Component:
    """One row of game: rank badge, XP to the next tier, points this week,
    quests. Never more than this on Home."""
    return rx.hstack(
        avatar(rank, rank, size=40),
        rx.vstack(
            rx.hstack(text(rank_title, t.HEADLINE, overflow="hidden", text_overflow="ellipsis",
                           white_space="nowrap", min_width="0"),
                      rx.spacer(), text(quests_label, t.FOOTNOTE, t.TEXT_SECONDARY, white_space="nowrap"),
                      width="100%", align="baseline"),
            rx.box(rx.box(height="100%", width="100%", background=t.ACCENT_BLUE,
                          border_radius=t.RADIUS_PILL, transform=f"scaleX({xp_scale})",
                          transform_origin="left center",
                          transition=f"transform {t.DURATION} {t.EASE}"),
                   height="6px", width="100%", background=t.SURFACE_2,
                   border_radius=t.RADIUS_PILL, overflow="hidden"),
            rx.hstack(text(points_week, t.FOOTNOTE, t.TEXT_SECONDARY, white_space="nowrap",
                           **t.NUMERAL_GAME),
                      rx.spacer(),
                      text(f"{xp_now} / {xp_next} XP to {next_tier}", t.FOOTNOTE, t.TEXT_SECONDARY,
                           white_space="nowrap", overflow="hidden", text_overflow="ellipsis",
                           min_width="0", **t.TABULAR),
                      width="100%"),
            spacing="1",
            flex="1",
            min_width="0",
        ),
        background=t.SURFACE_1,
        border_radius=t.RADIUS_CARD,
        padding=t.space(3),
        spacing="3",
        width="100%",
        align="center",
        cursor="pointer",
        on_click=on_click,
    )


def _feed_stat(label: Any, value: Any, unit: Any = "") -> rx.Component:
    return rx.vstack(text(label, t.FOOTNOTE, t.TEXT_SECONDARY),
                     number(value, unit, style=t.HEADLINE), spacing="0", align="start",
                     min_width="0")


def feed_card(name: Any, initials: Any, rank: Any, when_label: Any, workout: Any,
              duration: Any, volume: Any, records: Any, points: Any,
              exercises: list[tuple[str, str]] | Any = (), more: Any = 0,
              spotted: Any = 0, on_spot: Any = None) -> rx.Component:
    """A finished workout in the feed: who, when, what, the four numbers, and
    a grid of what they did."""
    def tile(item: tuple[str, str]) -> rx.Component:
        caption, image = item
        return rx.vstack(thumb(image, size="100%", icon="dumbbell"),
                         text(caption, t.FOOTNOTE, t.TEXT_SECONDARY, overflow="hidden",
                              text_overflow="ellipsis", white_space="nowrap", max_width="100%"),
                         spacing="1", width="100%", min_width="0")
    return rx.vstack(
        rx.hstack(avatar(initials, rank, size=40),
                  rx.vstack(text(name, t.HEADLINE),
                            text(when_label, t.FOOTNOTE, t.TEXT_SECONDARY),
                            spacing="0", align="start", flex="1", min_width="0"),
                  rx.icon("ellipsis", size=20, color=t.TEXT_SECONDARY),
                  spacing="3", width="100%", align="center"),
        text(workout, t.TITLE_2),
        rx.hstack(_feed_stat("Duration", duration), _feed_stat("Volume", volume, "kg"),
                  rx.vstack(text("Records", t.FOOTNOTE, t.TEXT_SECONDARY),
                            rx.hstack(rx.icon("medal", size=16, color=t.PR_GOLD),
                                      number(records, style=t.HEADLINE), spacing="1"),
                            spacing="0", align="start"),
                  _feed_stat("Points", points),
                  spacing="5", width="100%"),
        rx.grid(*[tile(e) for e in exercises], columns="3", gap=t.space(2), width="100%")
        if isinstance(exercises, (list, tuple)) else rx.grid(rx.foreach(exercises, tile),
                                                              columns="3", gap=t.space(2), width="100%"),
        rx.hstack(
            rx.cond(more > 0, text(f"+{more} more", t.FOOTNOTE, t.TEXT_SECONDARY)) if not isinstance(more, int)
            else (text(f"+{more} more", t.FOOTNOTE, t.TEXT_SECONDARY) if more else rx.fragment()),
            rx.spacer(),
            rx.hstack(rx.icon("hand-metal", size=18), text(spotted, t.FOOTNOTE, **t.TABULAR),
                      spacing="1", align="center", cursor="pointer", on_click=on_spot,
                      custom_attrs={"role": "button", "aria-label": "Spot"}),
            width="100%",
            align="center",
        ),
        spacing="3",
        width="100%",
        padding_y=t.space(4),
        border_bottom=t.HAIRLINE,
    )
