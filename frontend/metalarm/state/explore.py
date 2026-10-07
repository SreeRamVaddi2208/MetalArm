"""Explore (overhaul 7.2): search, the muscle and equipment grids, filtered
exercise lists, curated programs. People arrive with following (phase 4).

The server filters and pages (GET /exercises/browse); this state holds the
current query, filters and page.
"""

from __future__ import annotations

import json

import reflex as rx

from metalarm import api
from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.state.auth import AuthState
from metalarm.ui.body_map import paths_for
from metalarm.workout_models import plural

CATEGORY_LABELS = {"powerlifter": "Powerlifter", "bodybuilder": "Bodybuilder", "athlete": "Athlete"}
RECENT_MAX = 6


def _card(e: dict) -> dict[str, str]:
    return {"id": str(e["id"]), "name": e["name"], "image": e.get("thumbnail_url") or "",
            "sub": " · ".join([m.replace("_", " ").capitalize() for m in e.get("primary_muscle_groups") or []][:2]
                              + [e["equipment"].replace("_", " ").capitalize().replace("Ez bar", "EZ bar")])}


def _rows(program: dict) -> list[dict[str, str]]:
    """A curated program's routines and their exercises, flat, for the sheet."""
    rows = []
    for r in program["routines"]:
        rows.append({"kind": "head", "title": r["name"], "sub": plural(len(r['exercises']), "exercise"),
                     "image": "", "id": ""})
        for e in r["exercises"]:
            reps = str(e["target_reps_low"]) + (
                f"-{e['target_reps_high']}" if e["target_reps_high"] != e["target_reps_low"] else "")
            rows.append({"kind": "ex", "title": e["name"], "image": e.get("thumbnail_url") or "",
                         "id": str(e["exercise_id"]),
                         "sub": f"{e['target_sets']} × {reps}"
                                + (f" · superset {e['superset_group']}" if e.get("superset_group") else "")})
    return rows


class ExploreState(rx.State):
    muscles: list[dict] = []
    equipment: list[dict] = []
    tab: str = "Exercises"
    loaded: bool = False
    error: str = ""

    # Search and filters
    query: str = ""
    searching: bool = False
    recents_json: str = rx.LocalStorage("[]", name="ma_recent_searches")
    muscle: str = ""
    muscle_label: str = ""
    gear: str = ""
    gear_label: str = ""
    results: list[dict[str, str]] = []
    total: int = 0
    cursor: str = ""
    busy: bool = False

    # Programs
    programs: list[dict[str, str]] = []
    program_slug: str = ""
    program_rows: list[dict[str, str]] = []
    saved_note: str = ""

    @rx.var
    def listing(self) -> bool:
        return bool(self.query.strip() or self.muscle or self.gear)

    @rx.var
    def recents(self) -> list[str]:
        try:
            return [str(x) for x in json.loads(self.recents_json or "[]")][:RECENT_MAX]
        except (ValueError, TypeError):
            return []

    @rx.var
    def total_label(self) -> str:
        return f"{self.total} exercise{'s' if self.total != 1 else ''}"

    @rx.var
    def visible_programs(self) -> list[dict[str, str]]:
        needle = self.query.strip().casefold()
        return [p for p in self.programs if not needle or needle in p["name"].casefold()]

    @rx.var
    def program(self) -> dict[str, str]:
        return next((p for p in self.programs if p["slug"] == self.program_slug), {})

    async def _token(self) -> str:
        return (await self.get_state(AuthState)).token

    async def load(self):
        token = await self._token()
        if not token:
            return
        # A program sheet left open on the last visit must not cover this one.
        self.program_slug = ""
        wanted = str(self.router.url.query_parameters.get("tab", "")).capitalize()
        if wanted in ("Programs", "Exercises", "People"):
            self.tab = wanted
        try:
            data = await api.taxonomy(token)
            curated = await wapi.curated_programs(token)
        except ApiError as exc:
            self.error = exc.detail
            return
        svg = {m["code"]: m["svg_path_ids"] for m in data.get("muscle_groups", [])}
        # Each tile lights its own muscle, full strength.
        self.muscles = [
            {"code": m["code"], "label": m["display_name"],
             "paths": paths_for({m["code"]: 1.0}, svg), "side": m["body_side"]}
            for m in data.get("muscle_groups", []) if m["browsable"]
        ]
        self.equipment = [
            {"code": e["code"], "label": e["display_name"]}
            for e in data.get("equipment", []) if e["browsable"]
        ]
        self._set_programs(curated)
        self.loaded = True
        # /train/exercises lists the whole library until something narrows it.
        self.tab = "Exercises"
        await self._search()

    def _set_programs(self, curated: list[dict]) -> None:
        self.programs = [
            {"slug": p["slug"], "name": p["name"], "category": CATEGORY_LABELS.get(p["category"], p["category"]),
             "meta": f"{p['level'].capitalize()} · {p['weeks']} weeks · {p['sessions_per_week']}× a week",
             "description": p["description"], "routines": str(len(p["routines"])),
             "saved": str(p.get("saved_program_id") or ""),
             "rows": json.dumps(_rows(p)),
             }
            for p in curated
        ]

    def set_tab(self, tab: str) -> None:
        self.tab = tab

    # --- search and filters ---------------------------------------------

    async def _search(self, more: bool = False) -> None:
        token = await self._token()
        self.busy = True
        try:
            page = await wapi.browse(token, q=self.query.strip(), muscle=self.muscle, equipment=self.gear,
                                     cursor=self.cursor if more else "")
        except ApiError as exc:
            self.error = exc.detail
            self.busy = False
            return
        cards = [_card(e) for e in page.get("items") or []]
        self.results = (self.results + cards) if more else cards
        self.total = page.get("total") or 0
        self.cursor = page.get("next_cursor") or ""
        self.busy = False

    async def set_query(self, value: str):
        self.query = value
        if self.tab == "Exercises":
            await self._search()

    def focus_search(self) -> None:
        self.searching = True

    def blur_search(self) -> None:
        self.searching = False
        term = self.query.strip()
        if len(term) >= 2:
            recents = [term] + [r for r in self.recents if r.casefold() != term.casefold()]
            self.recents_json = json.dumps(recents[:RECENT_MAX])

    async def use_recent(self, term: str):
        self.searching = False
        await self.set_query(term)

    async def clear_query(self):
        await self.set_query("")

    async def pick_muscle(self, code: str, label: str):
        self.muscle, self.muscle_label = ("", "") if self.muscle == code else (code, label)
        self.tab = "Exercises"
        await self._search()

    async def pick_gear(self, code: str, label: str):
        self.gear, self.gear_label = ("", "") if self.gear == code else (code, label)
        self.tab = "Exercises"
        await self._search()

    async def clear_filters(self):
        self.muscle = self.muscle_label = self.gear = self.gear_label = ""
        self.query = ""
        await self._search()

    async def more(self):
        if self.cursor:
            await self._search(more=True)

    # --- programs -------------------------------------------------------

    def open_program(self, slug: str) -> None:
        self.program_slug = slug
        self.saved_note = ""
        chosen = next((p for p in self.programs if p["slug"] == slug), None)
        self.program_rows = json.loads(chosen["rows"]) if chosen else []

    def close_program(self) -> None:
        self.program_slug = ""

    async def save_program(self):
        token = await self._token()
        try:
            await wapi.save_curated(token, self.program_slug)
            curated = await wapi.curated_programs(token)
        except ApiError as exc:
            self.error = exc.detail
            return
        self._set_programs(curated)
        self.saved_note = "Saved to your Library"
