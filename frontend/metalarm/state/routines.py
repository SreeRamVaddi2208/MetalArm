"""Routines: reusable workout templates - list, create, edit, delete, start."""

from __future__ import annotations

import dataclasses

import reflex as rx

from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.state.auth import AuthState
from metalarm.state.workout import WorkoutState
from metalarm.workout_models import (
    LB_PER_KG,
    RoutineItem,
    RoutineSlot,
    muscles_label,
)


def _int_or_none(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    return int(float(value))


def _reps(value: str) -> dict:
    """"8" or "8-12" (any dash) -> the routine slot's rep fields."""
    value = (value or "").strip().replace("–", "-").replace("—", "-")
    if "-" in value:
        low, high = (_int_or_none(v) for v in value.split("-", 1))
        if low and high:
            low, high = min(low, high), max(low, high)
            return {"target_reps_low": low, "target_reps_high": high}
    return {"target_reps": _int_or_none(value)}


class RoutineState(rx.State):
    routines: list[RoutineItem] = []
    loading: bool = False
    error: str = ""
    notice: str = ""

    editing: bool = False
    edit_id: str = ""
    form_name: str = ""
    form_notes: str = ""
    # The program a new routine is filed under, if any.
    form_program_id: str = ""
    slots: list[RoutineSlot] = []

    @rx.var
    def has_routines(self) -> bool:
        return len(self.routines) > 0

    @rx.var
    def has_slots(self) -> bool:
        return len(self.slots) > 0

    @rx.var
    def form_title(self) -> str:
        return "EDIT ROUTINE" if self.edit_id else "NEW ROUTINE"

    async def _ctx(self) -> tuple[str, str]:
        auth = await self.get_state(AuthState)
        return auth.token, auth.weight_unit or "kg"

    async def load(self):
        token, unit = await self._ctx()
        if not token:
            return
        self.loading = True
        self.error = ""
        yield
        try:
            self.routines = [RoutineItem.from_api(r, unit) for r in await wapi.list_routines(token)]
        except ApiError as exc:
            self.error = exc.detail
        finally:
            self.loading = False

    # --- editor -------------------------------------------------------------

    def new_routine(self, program_id: str = "") -> None:
        self.editing = True
        self.edit_id = ""
        self.form_name = ""
        self.form_notes = ""
        self.form_program_id = program_id
        self.slots = []
        self.error = ""
        self.notice = ""

    async def open_routine(self, routine_id: str):
        """Edit a routine fetched by id - the Library lists summaries only."""
        token, unit = await self._ctx()
        try:
            routine = RoutineItem.from_api(await wapi.get_routine(token, routine_id), unit)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.routines = [r for r in self.routines if r.id != routine.id] + [routine]
        self.edit(routine.id)

    def edit(self, routine_id: str) -> None:
        routine = next((r for r in self.routines if r.id == routine_id), None)
        if routine is None:
            return
        self.editing = True
        self.edit_id = routine.id
        self.form_name = routine.name
        self.form_notes = routine.notes
        self.form_program_id = routine.program_id
        self.slots = [dataclasses.replace(s) for s in routine.slots]
        self.error = ""
        self.notice = ""

    def cancel(self) -> None:
        self.editing = False
        self.error = ""

    def set_form_name(self, value: str) -> None:
        self.form_name = value

    def set_form_notes(self, value: str) -> None:
        self.form_notes = value

    def _update(self, index: int, **changes) -> None:
        slots = list(self.slots)
        if 0 <= index < len(slots):
            slots[index] = dataclasses.replace(slots[index], **changes)
            self.slots = slots

    def set_slot_sets(self, index: int, value: str) -> None:
        self._update(index, target_sets=value)

    def set_slot_reps(self, index: int, value: str) -> None:
        self._update(index, target_reps=value)

    def set_slot_weight(self, index: int, value: str) -> None:
        self._update(index, target_weight=value)

    def set_slot_rest(self, index: int, value: str) -> None:
        self._update(index, rest_seconds=value)

    def set_slot_notes(self, index: int, value: str) -> None:
        self._update(index, notes=value)

    def superset_with_next(self, index: int) -> None:
        """Link this slot and the next into one superset, or unlink them."""
        if not (0 <= index < len(self.slots) - 1):
            return
        here, after = self.slots[index], self.slots[index + 1]
        if here.superset_group and here.superset_group == after.superset_group:
            self._update(index + 1, superset_group=0)
            if not any(s.superset_group == here.superset_group
                       for i, s in enumerate(self.slots) if i != index):
                self._update(index, superset_group=0)
            return
        group = here.superset_group or after.superset_group or (
            max((s.superset_group for s in self.slots), default=0) + 1)
        self._update(index, superset_group=group)
        self._update(index + 1, superset_group=group)

    def move_slot(self, index: int, direction: int) -> None:
        other = index + direction
        if 0 <= index < len(self.slots) and 0 <= other < len(self.slots):
            slots = list(self.slots)
            slots[index], slots[other] = slots[other], slots[index]
            self.slots = slots

    def remove_slot(self, index: int) -> None:
        self.slots = [s for i, s in enumerate(self.slots) if i != index]

    async def add_slot(self, exercise_id: str):
        token, _ = await self._ctx()
        try:
            exercise = await wapi.get_exercise(token, exercise_id)
        except ApiError as exc:
            self.error = exc.detail
            return
        cardio = exercise.get("category") == "cardio"
        self.slots = [
            *self.slots,
            RoutineSlot(
                exercise_id=exercise["id"],
                name=exercise.get("name") or "",
                muscles_label=muscles_label(exercise.get("primary_muscle_groups")),
                target_sets="" if cardio else "3",
                target_reps="" if cardio else "8",
                rest_seconds="90",
                image=exercise.get("thumbnail_url") or "",
            ),
        ]

    async def save(self):
        token, unit = await self._ctx()
        if not self.form_name.strip():
            self.error = "Give the routine a name."
            return
        try:
            exercises = []
            for slot in self.slots:
                weight = (slot.target_weight or "").strip()
                kg = float(weight) / LB_PER_KG if weight and unit == "lb" else (
                    float(weight) if weight else None
                )
                exercises.append(
                    {
                        "exercise_id": slot.exercise_id,
                        "target_sets": _int_or_none(slot.target_sets),
                        **_reps(slot.target_reps),
                        "target_weight_kg": round(kg, 2) if kg is not None else None,
                        "rest_seconds": _int_or_none(slot.rest_seconds),
                        "superset_group": slot.superset_group or None,
                        "notes": slot.notes.strip() or None,
                    }
                )
        except ValueError:
            self.error = "Targets must be numbers."
            return

        payload = {
            "name": self.form_name.strip(),
            "notes": self.form_notes.strip() or None,
            "exercises": exercises,
            "program_id": self.form_program_id or None,
        }
        try:
            if self.edit_id:
                await wapi.replace_routine(token, self.edit_id, payload)
            else:
                await wapi.create_routine(token, payload)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.editing = False
        self.notice = f"Saved {payload['name']}."
        from metalarm.state.library import LibraryState

        return [RoutineState.load, LibraryState.refresh]

    async def delete(self, routine_id: str):
        token, _ = await self._ctx()
        try:
            await wapi.delete_routine(token, routine_id)
        except ApiError as exc:
            self.error = exc.detail
            return
        if self.edit_id == routine_id:
            self.editing = False
        from metalarm.state.library import LibraryState

        return [RoutineState.load, LibraryState.refresh]

    def start(self, routine_id: str):
        self.editing = False
        return WorkoutState.start_session(routine_id)
