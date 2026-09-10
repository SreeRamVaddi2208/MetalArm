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


class RoutineState(rx.State):
    routines: list[RoutineItem] = []
    loading: bool = False
    error: str = ""
    notice: str = ""

    editing: bool = False
    edit_id: str = ""
    form_name: str = ""
    form_notes: str = ""
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
        workout = await self.get_state(WorkoutState)
        return auth.token, workout.unit

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

    def new_routine(self) -> None:
        self.editing = True
        self.edit_id = ""
        self.form_name = ""
        self.form_notes = ""
        self.slots = []
        self.error = ""
        self.notice = ""

    def edit(self, routine_id: str) -> None:
        routine = next((r for r in self.routines if r.id == routine_id), None)
        if routine is None:
            return
        self.editing = True
        self.edit_id = routine.id
        self.form_name = routine.name
        self.form_notes = routine.notes
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
                        "target_reps": _int_or_none(slot.target_reps),
                        "target_weight_kg": round(kg, 2) if kg is not None else None,
                        "rest_seconds": _int_or_none(slot.rest_seconds),
                    }
                )
        except ValueError:
            self.error = "Targets must be numbers."
            return

        payload = {
            "name": self.form_name.strip(),
            "notes": self.form_notes.strip() or None,
            "exercises": exercises,
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
        return RoutineState.load

    async def delete(self, routine_id: str):
        token, _ = await self._ctx()
        try:
            await wapi.delete_routine(token, routine_id)
        except ApiError as exc:
            self.error = exc.detail
            return
        if self.edit_id == routine_id:
            self.editing = False
        return RoutineState.load

    def start(self, routine_id: str):
        return WorkoutState.start_session(routine_id)
