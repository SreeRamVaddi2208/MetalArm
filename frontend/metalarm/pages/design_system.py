"""/design-system: every token and every primitive, in every state. Not in
any navigation - it is the reference the screens are built from, and the
first page the screenshot sweep (scripts/e2e/screens.mjs) captures. Static:
nothing here talks to the API."""

import reflex as rx

from metalarm import theme as t
from metalarm.ui.body_map import body_map
from metalarm.ui.calendar import month_calendar, week_strip
from metalarm.ui.chart import line_chart
from metalarm.ui.chrome import avatar, top_bar
from metalarm.ui.primitives import (
    button,
    card,
    chip,
    chips,
    empty_state,
    error_state,
    field,
    icon_button,
    list_row,
    number,
    pill,
    progress_bar,
    rows,
    section,
    segmented,
    skeleton,
    skeleton_rows,
    stat_group,
    stat_tile,
    stepper,
    text,
)
from metalarm.ui.rank_badge import rank_badge
from metalarm.ui.set_row import done_row, entry_panel

WEEK = [{"letter": letter, "number": str(n), "today": "1" if n == 7 else "", "trained": "1" if n in (5, 6) else "",
         "iso": f"2026-10-{n:02d}"} for letter, n in zip("MTWTFSS", range(5, 12))]
# Two weeks of October 2026 (it starts on a Thursday), the last of September before it.
_DAYS = [(d, False) for d in (28, 29, 30)] + [(d, True) for d in range(1, 12)]
MONTH = [[{"number": str(d), "trained": "1" if inside and d in (1, 2, 5, 6) else "",
           "today": "1" if inside and d == 7 else "", "in_month": "1" if inside else ""}
          for d, inside in _DAYS[w * 7:w * 7 + 7]] for w in range(2)]
SERIES = [{"label": f"{d} Sep", "value": v, "mark": None} for d, v in ((1, 80), (8, 82.5), (15, 82.5), (22, 85))] + [
    {"label": "29 Sep", "value": 87.5, "mark": 87.5}]
COLORS = [("bg", t.BG), ("surface", t.SURFACE), ("surface-2", t.SURFACE_2), ("border", t.BORDER),
          ("text", t.TEXT), ("text-2", t.TEXT_2), ("text-3", t.TEXT_3), ("accent", t.ACCENT),
          ("accent-soft", t.ACCENT_SOFT), ("on-accent", t.ON_ACCENT), ("danger", t.DANGER)]
TYPE = [("display 48/52", t.DISPLAY), ("title-lg 28/34", t.TITLE_LG), ("title 20/26", t.TITLE),
        ("body 16/24", t.BODY), ("label 14/20", t.LABEL), ("caption 12/16", t.CAPTION)]


def _swatch(name: str, value: str) -> rx.Component:
    return rx.vstack(rx.box(height="48px", width="100%", background=value, border_radius=t.RADIUS,
                            border=t.HAIRLINE),
                     text(name, t.CAPTION), text(value, t.CAPTION, t.TEXT_2, word_break="break-all"),
                     spacing="1", min_width="0")


def _state(label: str, *children: rx.Component) -> rx.Component:
    return rx.vstack(text(label, t.CAPTION, t.TEXT_3), *children, spacing="2", width="100%", align="start")


def design_system_page() -> rx.Component:
    noop = rx.noop()
    return rx.box(
        rx.vstack(
            top_bar("Design system", large=True),
            text("One accent, near-black neutrals, three type sizes a screen, one primary a screen.", t.BODY,
                 t.TEXT_2),
            section("Colour", rx.grid(*[_swatch(n, v) for n, v in COLORS], columns="3", gap=t.space(12),
                                      width="100%")),
            section("Type", *[rx.vstack(text(label, t.CAPTION, t.TEXT_3), text("Bench 87.5 kg", style),
                                        spacing="0", align="start") for label, style in TYPE]),
            section("Space", rx.vstack(*[rx.hstack(text(f"{s}", t.CAPTION, t.TEXT_2, width="32px"),
                                                   rx.box(width=f"{s}px", height="8px", background=t.ACCENT_SOFT))
                                         for s in t.SPACE[1:]], spacing="1", width="100%")),
            section("Buttons",
                    _state("primary", button("Start workout", noop, icon="play", full=True)),
                    _state("primary · disabled", button("Start workout", noop, disabled=True, full=True)),
                    _state("secondary · ghost · danger",
                           rx.hstack(button("Save", noop, variant="secondary"), button("Skip", noop, variant="ghost"),
                                     button("Delete", noop, variant="danger"), spacing="2", flex_wrap="wrap")),
                    _state("icon buttons", rx.hstack(icon_button("bell", "Notifications", badge=1),
                                                     icon_button("ellipsis", "Options"), icon_button("x", "Close")))),
            section("Rows and cards",
                    rows(list_row("Push day", "6 exercises · 2 days ago", chevron=True, on_click=noop),
                         list_row("Body weight", "5 Oct", trailing="81.4 kg"),
                         list_row("Sign out", title_color=t.DANGER, on_click=noop)),
                    card(text("Up next", t.CAPTION, t.TEXT_2), text("Pull day", t.TITLE),
                         text("5 exercises · Yesterday", t.CAPTION, t.TEXT_2))),
            section("Numbers",
                    number("87.5", "kg"),
                    stat_group(stat_tile("4", "Week streak"), stat_tile("3", "Workouts"), stat_tile("1,240", "Points")),
                    progress_bar(0.62, label="1,240 / 2,000 XP to Hunter")),
            section("Controls",
                    _state("chips", chips(chip("Chest", selected=True), chip("Back"), chip("Legs"), chip("Arms"))),
                    _state("segmented", segmented(["3M", "6M", "1Y", "All"], "3M")),
                    _state("field", field("", noop, "Search exercises")),
                    _state("stepper", stepper("87.5", noop, noop, noop, unit="kg", label="Weight")),
                    _state("pill", rx.hstack(pill("PR"), pill("Warm-up", accent=False), spacing="2"))),
            section("Sets",
                    _state("logged", rows(done_row("1", "normal", "80 kg × 8"),
                                          done_row("2", "normal", "85 kg × 6", pr=True))),
                    _state("entry", entry_panel("3", "normal", weight="85", reps="6", unit="kg", ghost_weight="85",
                                                ghost_reps="6", on_weight=noop, on_reps=noop, on_weight_minus=noop,
                                                on_weight_plus=noop, on_reps_minus=noop, on_reps_plus=noop,
                                                on_log=noop, on_type=noop))),
            section("Rank and people",
                    rx.hstack(*[rank_badge(r, 48) for r in ("E", "D", "C", "B", "A", "S")], spacing="2",
                              flex_wrap="wrap"),
                    rx.hstack(avatar("SR", size=40), rank_badge("C", 24), rank_badge("C", 96), spacing="3",
                              align="center")),
            section("Charts and maps", line_chart(SERIES), week_strip(WEEK, "2026-10-07"),
                    month_calendar("October 2026", MONTH),
                    rx.center(body_map({}, size="160px"), width="100%")),
            section("States",
                    _state("skeleton", skeleton("64px"), skeleton_rows(2)),
                    _state("empty", empty_state("list", "Save a workout as a routine, or build one.",
                                                button("Build a routine", noop, variant="secondary"))),
                    _state("error", error_state("We couldn't reach the server.", noop))),
            spacing="7", width="100%", max_width=t.MAX_WIDTH, margin="0 auto",
            padding=f"0 {t.GUTTER} {t.space(48)}",
        ),
        background=t.BG, min_height="100vh", width="100%",
    )
