"""The Library tab: ready-made programs and workouts for each training path.

What is recommended, and in what order, is the server's (`recommended` and
`sort` on every item, app/api/routes/library_catalog.py); this state renders
it as given. Starting a workout asks the API for a pre-loaded session and
goes to Train, where WorkoutState.load picks it up like any live workout.
"""

from __future__ import annotations

import reflex as rx

from metalarm import library_api as lapi
from metalarm.api import ApiError
from metalarm.state.auth import AuthState

PATHS = {"athlete": "Athletic", "bodybuilder": "Bodybuilder", "powerlifter": "Powerlifter"}
DAY_OPTIONS = ["2", "3", "4", "5", "6"]
DIFFICULTIES = ["beginner", "intermediate", "advanced"]
EQUIPMENT = ["bodyweight", "dumbbell", "kettlebell", "barbell", "cable", "machine", "band"]
DURATIONS = ["30", "45", "60"]


LABELS = {"ez_bar": "EZ bar", "trap_bar": "Trap bar", "cardio_machine": "Cardio machine"}


def label(code: str) -> str:
    return LABELS.get(code, code.replace("_", " ").capitalize())


def program_row(p: dict) -> dict[str, str]:
    return {
        "slug": p["slug"], "name": p["name"], "description": p.get("description") or "",
        "category": p["category"], "path": p["category_label"],
        "meta": f"{p['weeks']} weeks · {p['days_per_week']} days a week · {label(p['difficulty'])}",
        "recommended": "1" if p["recommended"] else "", "following": "1" if p.get("following") else "",
    }


def workout_row(w: dict) -> dict[str, str]:
    gear = ", ".join(label(e) for e in w["equipment"][:3]) + (" +" if len(w["equipment"]) > 3 else "")
    return {
        "slug": w["slug"], "name": w["name"], "description": w.get("description") or "",
        "category": w["category"], "path": w["category_label"],
        "meta": f"{w['duration_minutes']} min · {w['exercise_count']} exercises",
        "gear": gear, "recommended": "1" if w["recommended"] else "",
    }


def _started_message(exc: ApiError) -> str:
    return "Finish or discard the workout you have going first." if exc.status == 409 else exc.detail


class LibraryState(rx.State):
    """/library and /library/path/<category>."""

    path: str = ""
    needs_path: bool = False
    # The program the user follows: name, where they are, what is next.
    your_program: dict[str, str] = {}
    programs: list[dict[str, str]] = []
    workouts: list[dict[str, str]] = []
    others: list[dict[str, str]] = []
    loaded: bool = False
    error: str = ""

    # The path view and its filters.
    category: str = ""
    show_filters: bool = False
    f_days: str = ""
    f_difficulty: str = ""
    f_equipment: list[str] = []
    f_minutes: str = ""

    @rx.var
    def category_label(self) -> str:
        return PATHS.get(self.category, "")

    @rx.var
    def filtering(self) -> bool:
        return bool(self.f_days or self.f_difficulty or self.f_equipment or self.f_minutes)

    @rx.var
    def filter_count(self) -> int:
        return sum(1 for f in (self.f_days, self.f_difficulty, self.f_minutes) if f) + len(self.f_equipment)

    async def _token(self) -> str:
        return (await self.get_state(AuthState)).token

    async def load(self):
        """The Library home, as the server builds it."""
        token = await self._token()
        if not token:
            return
        self.loaded, self.error = False, ""
        try:
            home = await lapi.home(token)
        except ApiError as exc:
            self.error = exc.detail
            self.loaded = True
            return
        self.path, self.needs_path = home["path"], home["needs_path"]
        mine = home.get("your_program")
        if mine:
            e, nxt = mine["enrollment"], mine["enrollment"].get("next_workout")
            self.your_program = {
                "slug": mine["program"]["slug"], "name": mine["program"]["name"],
                "where": f"Week {e['current_week']} · Day {e['current_day']}",
                "next_slug": nxt["slug"] if nxt else "", "next_name": nxt["name"] if nxt else "",
                "next_meta": f"{nxt['duration_minutes']} min · {nxt['exercise_count']} exercises" if nxt else "",
            }
        else:
            self.your_program = {}
        self.programs = [program_row(p) for p in home["recommended_programs"]]
        self.workouts = [workout_row(w) for w in home["recommended_workouts"]]
        self.others = [
            {"category": o["category"], "label": o["label"],
             "meta": f"{o['programs']} programs · {o['workouts']} workouts"}
            for o in home["other_paths"]
        ]
        self.loaded = True

    async def load_path(self):
        """/library/path/<category>: every program and workout of one path,
        filtered."""
        parts = [p for p in str(self.router.url.path).split("/") if p]
        self.category = parts[-1] if len(parts) >= 3 and parts[-1] in PATHS else "athlete"
        # The Library's search icon lands here with the filters open.
        self.show_filters = str(self.router.url.query_parameters.get("filters", "")) == "1"
        await self._load_lists()

    async def _load_lists(self) -> None:
        token = await self._token()
        if not token:
            return
        self.loaded, self.error = False, ""
        try:
            programs = await lapi.programs(
                token, category=self.category, difficulty=self.f_difficulty,
                days_per_week=int(self.f_days) if self.f_days else None, equipment=self.f_equipment)
            workouts = await lapi.workouts(
                token, category=self.category, difficulty=self.f_difficulty, equipment=self.f_equipment,
                max_minutes=int(self.f_minutes) if self.f_minutes else None)
        except ApiError as exc:
            self.error = exc.detail
            self.loaded = True
            return
        self.programs = [program_row(p) for p in programs]
        self.workouts = [workout_row(w) for w in workouts]
        self.loaded = True

    def open_filters(self) -> None:
        self.show_filters = True

    def close_filters(self) -> None:
        self.show_filters = False

    def pick_days(self, value: str) -> None:
        self.f_days = "" if self.f_days == value else value

    def pick_difficulty(self, value: str) -> None:
        self.f_difficulty = "" if self.f_difficulty == value else value

    def toggle_equipment(self, value: str) -> None:
        self.f_equipment = ([e for e in self.f_equipment if e != value] if value in self.f_equipment
                            else [*self.f_equipment, value])

    def pick_minutes(self, value: str) -> None:
        self.f_minutes = "" if self.f_minutes == value else value

    async def apply_filters(self):
        self.show_filters = False
        await self._load_lists()

    async def clear_filters(self):
        self.f_days = self.f_difficulty = self.f_minutes = ""
        self.f_equipment = []
        self.show_filters = False
        await self._load_lists()

    async def start(self, slug: str):
        """Start a workout from a card (the 'Your program' Start)."""
        token = await self._token()
        try:
            await lapi.start(token, slug)
        except ApiError as exc:
            self.error = _started_message(exc)
            return
        return rx.redirect("/train")


class LibraryWorkoutState(rx.State):
    """/library/workout/<slug>."""

    slug: str = ""
    name: str = ""
    description: str = ""
    path: str = ""
    duration: str = ""
    count: str = ""
    gear: str = ""
    rows: list[dict[str, str]] = []
    saved: bool = False
    loaded: bool = False
    busy: bool = False
    error: str = ""
    notice: str = ""

    async def load(self):
        token = (await self.get_state(AuthState)).token
        if not token:
            return
        parts = [p for p in str(self.router.url.path).split("/") if p]
        self.slug = parts[-1] if len(parts) >= 3 else ""
        self.loaded, self.error, self.notice = False, "", ""
        try:
            w = await lapi.workout(token, self.slug)
        except ApiError as exc:
            self.error = exc.detail
            self.loaded = True
            return
        self.name, self.description, self.path = w["name"], w.get("description") or "", w["category_label"]
        self.duration, self.count = str(w["duration_minutes"]), str(w["exercise_count"])
        self.gear = ", ".join(label(e) for e in w["equipment"])
        self.rows = [
            {
                "name": e["exercise"]["name"],
                "muscle": label((e["exercise"].get("primary_muscle_groups") or [""])[0]),
                "target": (f"{e['target_sets']} × "
                           + (f"{e['rep_low']}" if e["rep_low"] == e["rep_high"] else f"{e['rep_low']}–{e['rep_high']}")
                           + f" · {e['rest_seconds']}s rest"),
                "note": e.get("note") or "",
                "superset": f"Superset {e['superset_group']}" if e["superset_group"] else "",
                "exercise_id": e["exercise"]["id"],
            }
            for e in w["exercises"]
        ]
        self.saved = bool(w.get("routine_id"))
        self.loaded = True

    async def start(self):
        token = (await self.get_state(AuthState)).token
        self.busy, self.error = True, ""
        yield
        try:
            await lapi.start(token, self.slug)
        except ApiError as exc:
            self.error = _started_message(exc)
            self.busy = False
            return
        self.busy = False
        yield rx.redirect("/train")

    async def save(self):
        token = (await self.get_state(AuthState)).token
        try:
            await lapi.save_to_routines(token, self.slug)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.saved, self.notice = True, f"{self.name} is in your routines on Train."


class LibraryProgramState(rx.State):
    """/library/program/<slug>."""

    slug: str = ""
    name: str = ""
    description: str = ""
    path: str = ""
    weeks: str = ""
    days: str = ""
    difficulty: str = ""
    # Weeks as rows, days 1-7 as cells: {label, slug, rest}.
    schedule: list[list[dict[str, str]]] = []
    workouts: list[dict[str, str]] = []
    status: str = ""            # "", active, paused, completed
    where: str = ""
    next_slug: str = ""
    next_name: str = ""
    loaded: bool = False
    busy: bool = False
    error: str = ""

    async def load(self):
        token = (await self.get_state(AuthState)).token
        if not token:
            return
        parts = [p for p in str(self.router.url.path).split("/") if p]
        self.slug = parts[-1] if len(parts) >= 3 else ""
        self.loaded, self.error = False, ""
        await self._fetch(token)

    async def _fetch(self, token: str) -> None:
        try:
            p = await lapi.program(token, self.slug)
        except ApiError as exc:
            self.error = exc.detail
            self.loaded = True
            return
        self.name, self.description, self.path = p["name"], p.get("description") or "", p["category_label"]
        self.weeks, self.days, self.difficulty = str(p["weeks"]), str(p["days_per_week"]), label(p["difficulty"])
        short = {w["slug"]: w["name"] for w in p["workouts"]}
        self.schedule = [
            [{"label": short.get(d["workout_slug"], "") if d["workout_slug"] else "Rest",
              "slug": d["workout_slug"] or "", "day": str(d["day"])} for d in week["days"]]
            for week in p["schedule"]
        ]
        self.workouts = [workout_row(w) for w in p["workouts"]]
        e = p.get("enrollment")
        self.status = e["status"] if e else ""
        nxt = (e or {}).get("next_workout")
        self.where = f"Week {e['current_week']} · Day {e['current_day']}" if e else ""
        self.next_slug, self.next_name = (nxt["slug"], nxt["name"]) if nxt else ("", "")
        self.loaded = True

    async def follow(self):
        token = (await self.get_state(AuthState)).token
        try:
            await lapi.follow(token, self.slug)
        except ApiError as exc:
            self.error = exc.detail
            return
        await self._fetch(token)

    async def unfollow(self):
        token = (await self.get_state(AuthState)).token
        try:
            await lapi.unfollow(token, self.slug)
        except ApiError as exc:
            self.error = exc.detail
            return
        await self._fetch(token)

    async def start_next(self):
        token = (await self.get_state(AuthState)).token
        if not self.next_slug:
            return
        self.busy, self.error = True, ""
        yield
        try:
            await lapi.start(token, self.next_slug)
        except ApiError as exc:
            self.error = _started_message(exc)
            self.busy = False
            return
        self.busy = False
        yield rx.redirect("/train")
