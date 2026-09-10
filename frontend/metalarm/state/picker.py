"""Exercise picker: search the library, filter by muscle group, or create a
custom exercise - then hand the choice to whoever opened the picker.

One picker serves both the live workout and the routine editor (`mode`), so
the library UI exists exactly once.
"""

from __future__ import annotations

import reflex as rx

from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.state.auth import AuthState
from metalarm.state.routines import RoutineState
from metalarm.state.workout import WorkoutState
from metalarm.workout_models import Chip, ExercisePick


class PickerState(rx.State):
    is_open: bool = False
    mode: str = "session"
    query: str = ""
    muscle: str = ""
    muscles: list[Chip] = []
    # Raw values too: rx.select takes a list of plain strings.
    muscle_values: list[str] = []
    categories: list[str] = []
    equipment: list[str] = []
    results: list[ExercisePick] = []
    loading: bool = False
    error: str = ""

    show_create: bool = False
    new_category: str = "strength"
    new_equipment: str = "barbell"
    new_muscle: str = "chest"

    @rx.var
    def has_results(self) -> bool:
        return len(self.results) > 0

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
        self.error = ""
        token = await self._token()
        if not self.muscles:
            try:
                meta = await wapi.exercise_meta(token)
            except ApiError as exc:
                self.error = exc.detail
                return
            self.muscle_values = list(meta.get("muscle_groups") or [])
            self.muscles = [Chip.of(m) for m in self.muscle_values]
            self.categories = list(meta.get("categories") or [])
            self.equipment = list(meta.get("equipment") or [])
        await self._search(token)

    def set_open(self, value: bool) -> None:
        self.is_open = value

    async def set_query(self, value: str):
        self.query = value
        await self._search(await self._token())

    async def pick_muscle(self, value: str):
        self.muscle = "" if self.muscle == value else value
        await self._search(await self._token())

    async def _search(self, token: str) -> None:
        self.loading = True
        try:
            rows = await wapi.search_exercises(token, q=self.query, muscle=self.muscle)
            self.results = [ExercisePick.from_api(r) for r in rows]
            self.error = ""
        except ApiError as exc:
            self.error = exc.detail
        finally:
            self.loading = False

    def _hand_off(self, exercise_id: str):
        self.is_open = False
        if self.mode == "routine":
            return RoutineState.add_slot(exercise_id)
        return WorkoutState.add_exercise(exercise_id)

    def pick(self, exercise_id: str):
        return self._hand_off(exercise_id)

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
                {
                    "name": name,
                    "category": self.new_category,
                    "primary_muscle_groups": [self.new_muscle],
                    "equipment": self.new_equipment,
                },
            )
        except ApiError as exc:
            self.error = exc.detail
            return
        self.show_create = False
        return self._hand_off(created["id"])
