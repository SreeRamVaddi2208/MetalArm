"""/gallery - every component in the design system, in every state, at two
phone widths side by side. Hidden (not in any navigation): for reviewing the
system, and for the screenshot sweep (scripts/e2e/screens.mjs)."""

import reflex as rx

from metalarm import theme as t
from metalarm.ui.body_map import body_map
from metalarm.ui.calendar import month_calendar, week_strip
from metalarm.ui.cards import (
    equipment_circle,
    feed_card,
    game_strip,
    hero_card,
    muscle_tile,
    ring_metric,
    routine_tile,
)
from metalarm.ui.chart import area_chart
from metalarm.ui.chrome import avatar, icon_button, start_pill, top_bar
from metalarm.ui.primitives import (
    card,
    delta_pill,
    empty_state,
    filter_chip,
    list_row,
    metric_chips,
    number,
    primary_button,
    section_header,
    segmented_control,
    skeleton,
    stat_tile,
    sub_tabs,
    text,
)
from metalarm.ui.set_row import set_header, set_row

WEEK = [{"letter": l, "number": n, "today": n == 6, "trained": n in (1, 3, 4), "iso": f"2026-10-0{n}"}
        for l, n in zip("MTWTFSS", range(5, 12))]
MONTH = [[{"number": d if 1 <= d <= 31 else "", "trained": d in (1, 3, 6, 7, 8, 13, 15),
           "today": d == 6, "in_month": 1 <= d <= 31} for d in range(w * 7 - 2, w * 7 + 5)]
         for w in range(5)]
SERIES = [{"label": l, "value": v} for l, v in
          zip(["Aug 3", "Aug 10", "Aug 17", "Aug 24", "Aug 31", "Sep 7", "Sep 14", "Sep 21", "Sep 28", "Oct 5"],
              [140, 210, 180, 260, 0, 230, 300, 280, 339, 95])]
WORKED = {"front-chest-l": 1, "front-chest-r": 1, "front-delt-l": 0.6, "front-delt-r": 0.6,
          "back-triceps-l": 0.8, "back-triceps-r": 0.8, "front-abs": 0.3}


def section(title: str, *items: rx.Component) -> rx.Component:
    return rx.vstack(text(title, t.CAPTION, t.TEXT_SECONDARY), *items, spacing="3", width="100%",
                     padding_top=t.space(6))


def catalogue() -> rx.Component:
    """Everything, once - rendered at each phone width below."""
    return rx.vstack(
        section("TopBar",
                top_bar("You", icon_button("share", "Share"), icon_button("calendar", "Calendar"),
                        icon_button("settings", "Settings"), leading=avatar("MA", "C")),
                top_bar("Home ▾", icon_button("flame", "Streak", color=t.STREAK_ORANGE),
                        icon_button("bell", "Notifications", badge=1), leading=avatar("MA", "A"))),
        section("Avatar frames by tier", rx.hstack(*[avatar(r, r, size=44) for r in "EDCBAS"], spacing="2")),
        section("SubTabs", sub_tabs([("Overview", ""), ("Exercises", ""), ("Measurements", ""), ("History", "")],
                                    "Overview")),
        section("FilterChip", rx.hstack(filter_chip("Programs", selected=True), filter_chip("Routines"),
                                        filter_chip("Exercises"), filter_chip("Disabled", disabled=True),
                                        spacing="2", flex_wrap="wrap")),
        section("SegmentedControl", segmented_control(["3M", "6M", "Year", "All"], "6M")),
        section("Numbers and units", rx.hstack(number("93", "%"), number("1h 35m"), number("14,715", "kg"),
                                               spacing="5", flex_wrap="wrap")),
        section("StatTile + DeltaPill",
                rx.hstack(stat_tile("Workouts", "3", delta="2", direction="down"),
                          stat_tile("Duration", "4h 10m", delta="3h 32m"),
                          stat_tile("Volume", "18,240", "kg", delta="1,532 kg", direction="up"),
                          width="100%")),
        section("SectionHeader", section_header("Your weekly snapshot", action="See more"),
                section_header("This week", "See which muscles you worked.")),
        section("HeroCard", hero_card("Monthly Summary", "September 2026")),
        section("GameStrip", game_strip("C", "Intermediate", 340, 500, "Advanced", "+212 pts this week",
                                        "2 of 5 quests", xp_scale=0.68)),
        section("RoutineTile", rx.hstack(routine_tile("Lower A", "Lo", t.tile_color("Lower A"), "Oct 2"),
                                         routine_tile("Arms", "Ar", t.tile_color("Arms"), "Sep 30"),
                                         routine_tile("Back + biceps", "Ba", t.tile_color("Back"), "Sep 27"),
                                         spacing="3", overflow_x="auto", width="100%")),
        section("MuscleTile + EquipmentCircle",
                rx.grid(muscle_tile("Chest", body_map({"front-chest-l": 1, "front-chest-r": 1},
                                                      views=("front",), size="96px")),
                        muscle_tile("Glutes", body_map({"back-glute-l": 1, "back-glute-r": 1},
                                                       views=("back",), size="96px")),
                        muscle_tile("Calves", body_map({"back-calf-l": 1, "back-calf-r": 1},
                                                       views=("back",), size="96px")),
                        columns="3", gap=t.space(3), width="100%"),
                rx.hstack(equipment_circle("barbell", "Barbell"), equipment_circle("bodyweight", "Body weight"),
                          equipment_circle("cable", "Cable"), spacing="4")),
        section("ListRow", list_row("Create new program", "Plan weeks of routines", icon="plus"),
                list_row("Favorites", "0 routines", icon="heart"),
                list_row("Upper / Lower - 4 days", "4 routines", icon="layers")),
        section("WeekStrip", week_strip(WEEK)),
        section("MonthCalendar", month_calendar("October 2026", MONTH)),
        section("RingMetric", rx.hstack(ring_metric(93, "Recovered"),
                                        ring_metric(40, "Quests", color=t.ACCENT_BLUE), spacing="6")),
        section("AreaChart + MetricChips", area_chart(SERIES),
                metric_chips(["Duration", "Volume", "Workouts", "Points"], "Duration")),
        section("BodyMap", body_map(WORKED)),
        section("SetRow", set_header(rpe=True),
                set_row(1, set_type="warmup", previous="40 kg × 10", weight="40", reps="10", rpe="", done=True),
                set_row(2, previous="80 kg × 8", weight="82.5", reps="8", rpe="8", done=True, pr=True,
                        points="+52"),
                set_row(3, set_type="drop", previous="80 kg × 8", weight="60", reps="12", rpe=""),
                set_row(4, set_type="failure", previous="-", weight="", reps="", rpe="")),
        section("FeedCard", feed_card("Maya", "MY", "A", "Yesterday at 08:19 PM", "Upper A", "1h 35m",
                                      "14,715", 3, 186,
                                      [("3 × Bench press", ""), ("4 × Barbell row", ""),
                                       ("3 × Overhead press", "")], more=2, spotted=4)),
        section("EmptyState", empty_state("No workouts today", "Start one and it shows up here.",
                                          primary_button("Start New Workout", icon="play"))),
        section("Skeleton", skeleton(), skeleton("120px")),
        section("Card", card(text("Card title", t.HEADLINE), text("A line of body copy.", t.BODY, t.TEXT_SECONDARY))),
        section("Buttons", primary_button("Finish", icon="check"), primary_button("Disabled", disabled=True)),
        section("StartWorkoutPill", start_pill(floating=False),
                start_pill(active_since="2026-10-06T08:00:00Z", floating=False)),
        spacing="0",
        width="100%",
        padding_bottom=t.space(12),
    )


def phone(width: int) -> rx.Component:
    return rx.vstack(
        text(f"{width} px", t.CAPTION, t.TEXT_SECONDARY),
        rx.box(catalogue(), width=f"{width}px", padding_left=t.GUTTER, padding_right=t.GUTTER,
               background=t.COLOR_BG, border=t.HAIRLINE, border_radius=t.RADIUS_CARD,
               overflow_x="hidden", font_family=t.FONT_UI),
        spacing="2",
        align="start",
        flex_shrink="0",
    )


def gallery_page() -> rx.Component:
    return rx.box(
        rx.hstack(*[phone(w) for w in t.PHONE_WIDTHS], spacing="8", align="start",
                  padding=t.space(6), overflow_x="auto"),
        background=t.COLOR_BG, min_height="100vh", color=t.TEXT_PRIMARY,
    )
