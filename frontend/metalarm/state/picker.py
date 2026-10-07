"""Exercise picker: search the library, filter by muscle and equipment, pick
several, or create a custom exercise - then hand the picks, in the order
chosen, to whoever opened it (the live workout or the routine editor).

The same browse endpoint as Explore (GET /exercises/browse), so the library
reads the same everywhere.
"""

from __future__ import annotations

import reflex as rx

from metalarm import api
from metalarm import analytics_api as wapi_analytics
from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.state.auth import AuthState
from metalarm.state.routines import RoutineState
from metalarm.state.workout import WorkoutState


class PickerState(rx.State):
    is_open: bool = False
    mode: str = "session"
    query: str = ""
    muscle: str = ""
    gear: str = ""
    muscles: list[dict[str, str]] = []
    gears: list[dict[str, str]] = []
    categories: list[str] = ["strength", "bodyweight", "cardio", "mobility"]
    results: list[dict[str, str]] = []
    # Shown first when nothing is searched or filtered: what the user did lately.
    recent: list[dict[str, str]] = []
    cursor: str = ""
    # Ids in the order they were picked.
    selected: list[str] = []
    loading: bool = False
    error: str = ""

    show_create: bool = False
    new_category: str = "strength"
    new_equipment: str = "barbell"
    new_muscle: str = "chest"

    @rx.var
    def add_label(self) -> str:
        n = len(self.selected)
        return f"Add {n} exercise{'s' if n != 1 else ''}" if n else "Add"

    @rx.var
    def muscle_codes(self) -> list[str]:
        return [m["code"] for m in self.muscles]

    @rx.var
    def gear_codes(self) -> list[str]:
        return [g["code"] for g in self.gears]

    @rx.var
    def create_label(self) -> str:
        name = self.query.strip()
        return f'Create "{name}"' if name else "Type a name above first"

    async def _token(self) -> str:
        return (await self.get_state(AuthState)).token

    async def open_for(self, mode: str):
        self.mode = mode
        self.is_open = True
        self.show_create = False
        self.selected = []
        self.error = ""
        token = await self._token()
        if not self.muscles:
            try:
                data = await api.taxonomy(token)
            except ApiError as exc:
                self.error = exc.detail
                return
            self.muscles = [{"code": m["code"], "label": m["display_name"]}
                            for m in data.get("muscle_groups", []) if m["browsable"]]
            self.gears = [{"code": e["code"], "label": e["display_name"]}
                          for e in data.get("equipment", []) if e["browsable"]]
        try:
            mine = await wapi_analytics.my_exercises(token, limit=6)
            self.recent = [{"id": str(e["exercise_id"]), "name": e["name"], "image": e.get("thumbnail_url") or "",
                            "sub": " · ".join(m.replace("_", " ").capitalize() for m in e["primary_muscle_groups"][:2])}
                           for e in mine.get("items") or []]
        except ApiError:
            self.recent = []
        await self._search()

    @rx.var
    def browsing(self) -> bool:
        """Nothing searched or filtered - show what was used lately first."""
        return not (self.query.strip() or self.muscle or self.gear)

    def close(self) -> None:
        self.is_open = False
        self.selected = []

    def set_open(self, value: bool) -> None:
        self.is_open = value

    async def set_query(self, value: str):
        self.query = value
        await self._search()

    async def pick_muscle(self, code: str):
        self.muscle = "" if self.muscle == code else code
        await self._search()

    async def pick_gear(self, code: str):
        self.gear = "" if self.gear == code else code
        await self._search()

    async def _search(self, more: bool = False) -> None:
        self.loading = True
        try:
            page = await wapi.browse(await self._token(), q=self.query.strip(), muscle=self.muscle,
                                     equipment=self.gear, cursor=self.cursor if more else "", limit=40)
        except ApiError as exc:
            self.error = exc.detail
            self.loading = False
            return
        rows = [{"id": str(e["id"]), "name": e["name"], "image": e.get("thumbnail_url") or "",
                 "sub": " · ".join([m.replace("_", " ").capitalize() for m in e["primary_muscle_groups"]][:2]
                                   + [e["equipment"].replace("_", " ").capitalize().replace("Ez bar", "EZ bar")])}
                for e in page.get("items") or []]
        self.results = (self.results + rows) if more else rows
        self.cursor = page.get("next_cursor") or ""
        self.error = ""
        self.loading = False

    async def more(self):
        if self.cursor:
            await self._search(more=True)

    def toggle(self, exercise_id: str) -> None:
        self.selected = ([i for i in self.selected if i != exercise_id] if exercise_id in self.selected
                         else [*self.selected, exercise_id])

    def _hand_off(self, ids: list[str]):
        self.is_open = False
        self.selected = []
        target = RoutineState.add_slot if self.mode == "routine" else WorkoutState.add_exercise
        return [target(i) for i in ids]

    def add_selected(self):
        if self.selected:
            return self._hand_off(list(self.selected))

    # --- custom exercise --------------------------------------------------

    def toggle_create(self) -> None:
        self.show_create = not self.show_create
        self.error = ""

    def set_new_category(self, value: str) -> None:
        self.new_category = value

    def set_new_equipment(self, value: str) -> None:
        self.new_equipment = value

    def set_new_muscle(self, value: str) -> None:
        self.new_muscle = value

    async def create_custom(self):
        name = self.query.strip()
        if not name:
            self.error = "Type the exercise name in the search box first."
            return
        try:
            created = await wapi.create_exercise(
                await self._token(),
                {"name": name, "category": self.new_category,
                 "primary_muscle_groups": [self.new_muscle], "equipment": self.new_equipment},
            )
        except ApiError as exc:
            self.error = exc.detail
            return
        self.show_create = False
        return self._hand_off([*self.selected, created["id"]])
