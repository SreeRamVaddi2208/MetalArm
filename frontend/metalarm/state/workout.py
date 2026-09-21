"""Live workout state: the in-progress session, the start screen, the PR
moment, set editing, and the finish summary.

Kept apart from reference data - the library lives in PickerState, routines in
RoutineState - per the brief. The session itself lives on the SERVER: `load`
rehydrates it from GET /workouts/sessions/active, so a refresh mid-workout
loses nothing and there is no client-side copy to go stale. Two small things
are client-persisted: nothing else would survive a refresh -
  - exercises added from the picker but not logged yet (they have no sets, so
    the server does not know about them), keyed to the session;
  - nothing else. The weight unit lives on the account (AuthState).

No number here is computed. Points, PR flags, streaks and level movement all
come from API responses - the brief's hard rule against client-side scoring.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from typing import Any

import reflex as rx

from metalarm import api as core_api
from metalarm import ranks
from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.share_card import share_card_script
from metalarm.state.auth import AuthState
from metalarm.state.quests import QuestState
from metalarm.workout_models import (
    ExerciseCard,
    FinishSummary,
    HistoryRow,
    PrView,
    RoutineItem,
    SetRow,
    StreakView,
    fmt,
    muscles_label,
    session_title,
    thousands,
    to_unit,
    weight_label,
)

DEFAULT_REST_SECONDS = 90
WEIGHT_STEP = {"kg": 2.5, "lb": 5.0}

_STOP_REST = "window.maRest && window.maRest.stop()"


def _num(value: str) -> float:
    try:
        return float(str(value).strip() or 0)
    except ValueError:
        return -1.0


def build_card(
    exercise: dict[str, Any],
    sets: list[dict[str, Any]],
    previous: list[dict[str, Any]],
    target: dict[str, Any] | None,
    unit: str,
    keep: ExerciseCard | None,
    hint: dict[str, Any] | None = None,
) -> ExerciseCard:
    """An exercise card from API data.

    `keep` is the card as it was before this refresh: its half-typed entry
    fields, warm-up toggle and idempotency key survive, so a server round trip
    never wipes what the user is typing. A NEW card is pre-filled from the last
    set logged this session, else last time's first set, else the routine's
    target - one tap then repeats it, which is the whole logging loop.
    """
    rows = [SetRow.from_api(s, unit) for s in sets]
    prev = [SetRow.from_api(s, unit) for s in previous]
    t = target or {}

    bits = []
    if t.get("target_sets"):
        bits.append(f"{t['target_sets']} sets")
    if t.get("target_reps"):
        bits.append(f"× {t['target_reps']}")
    if t.get("target_weight_kg"):
        bits.append(f"@ {weight_label(t['target_weight_kg'], unit)}")

    card = ExerciseCard(
        exercise_id=exercise.get("id") or "",
        name=exercise.get("name") or "",
        muscles_label=muscles_label(exercise.get("primary_muscle_groups")),
        is_cardio=exercise.get("category") == "cardio",
        target_label=" ".join(bits),
        rest_seconds=int(t.get("rest_seconds") or DEFAULT_REST_SECONDS),
        sets=rows,
        previous=prev,
        # Only worth saying before anything is logged: once sets exist in
        # this workout, "first time" is noise.
        previous_label=(
            "Last time: " + ", ".join(r.summary for r in prev[:5])
            if prev
            else ("" if rows else "First time - this sets your baseline")
        ),
        hint_label=(hint or {}).get("text") or "",
        hint_kind=(hint or {}).get("kind") or "",
    )

    if keep is not None:
        card = dataclasses.replace(
            card,
            weight_input=keep.weight_input,
            reps_input=keep.reps_input,
            rpe_input=keep.rpe_input,
            duration_input=keep.duration_input,
            distance_input=keep.distance_input,
            warmup=keep.warmup,
            client_set_id=keep.client_set_id,
            flash_kind=keep.flash_kind,
            flash_label=keep.flash_label,
            rest_seconds=card.rest_seconds if t else keep.rest_seconds,
        )
    else:
        seed = rows[-1] if rows else (prev[0] if prev else None)
        if seed is not None:
            card = dataclasses.replace(
                card,
                weight_input=seed.weight,
                reps_input=seed.reps,
                duration_input=seed.duration_min,
                distance_input=seed.distance_km,
            )
        elif t:
            card = dataclasses.replace(
                card,
                weight_input=fmt(to_unit(t.get("target_weight_kg"), unit))
                if t.get("target_weight_kg")
                else "",
                reps_input=str(t.get("target_reps") or ""),
            )
        card = dataclasses.replace(card, client_set_id=str(uuid.uuid4()))

    ghost_index = len(rows)
    ghost = prev[ghost_index] if ghost_index < len(prev) else None
    return dataclasses.replace(
        card,
        ghost_label=f"Last time, set {ghost_index + 1}: {ghost.summary}" if ghost else "",
    )


def set_payload(card: ExerciseCard, unit: str) -> tuple[dict[str, Any] | None, str]:
    """The request body for logging a card's entry, or a message saying what
    is missing. Raw workout data only - never a point value."""
    payload: dict[str, Any] = {
        "exercise_id": card.exercise_id,
        "unit": unit,
        "is_warmup": card.warmup,
        "client_set_id": card.client_set_id,
    }
    if card.is_cardio:
        minutes, km = _num(card.duration_input), _num(card.distance_input)
        if minutes < 0 or km < 0:
            return None, "Duration and distance must be numbers."
        if not minutes and not km:
            return None, "Enter a duration or a distance."
        if minutes:
            payload["duration_seconds"] = max(1, int(round(minutes * 60)))
        if km:
            payload["distance_m"] = round(km * 1000, 2)
        payload["weight"] = 0
    else:
        reps = _num(card.reps_input)
        weight = _num(card.weight_input)
        if reps < 1 or reps != int(reps):
            return None, "Enter the reps for this set (a whole number)."
        if weight < 0:
            return None, "Weight must be a number (0 for bodyweight)."
        payload["reps"] = int(reps)
        payload["weight"] = weight

    if card.rpe_input.strip():
        rpe = _num(card.rpe_input)
        if not 1 <= rpe <= 10:
            return None, "RPE is 1 to 10."
        payload["rpe"] = rpe
    return payload, ""


def level_beat(progression: dict[str, Any]) -> tuple[str, str, str]:
    """('rank'|'level'|'', badge, ladder) from the API's explicit flags.
    `ranked_up` is true only on promotion, so a demotion never fires a
    celebration. A rank-up's badge is the tier, not the letter."""
    if progression.get("ranked_up"):
        after = str(progression.get("rank_after") or "")
        return (
            "rank",
            ranks.rank_title(after).upper(),
            ranks.promotion(str(progression.get("rank_before") or ""), after),
        )
    if progression.get("leveled_up"):
        return "level", str(progression.get("level_after") or ""), ""
    return "", "", ""


class WorkoutState(rx.State):
    # Display unit, copied from the account (AuthState.weight_unit) on load.
    unit: str = "kg"
    # Exercises added but not yet logged: {"session": id, "ids": [...]}.
    pending: str = rx.LocalStorage("", name="ma_pending")

    loaded: bool = False
    busy: bool = False
    error: str = ""

    session_id: str = ""
    session_name: str = ""
    started_at: str = ""
    session_points: int = 0
    working_sets: int = 0
    volume_label: str = ""
    cards: list[ExerciseCard] = []

    routines: list[RoutineItem] = []
    recent: list[HistoryRow] = []
    streak: StreakView = StreakView()

    # The PR moment.
    show_pr: bool = False
    pr: PrView = PrView()
    pr_others: list[PrView] = []
    pr_points: int = 0
    # A level-up earned by the same set waits until the PR moment is
    # dismissed, so the two celebrations never stack on top of each other.
    _pending_kind: str = ""
    _pending_badge: str = ""
    _pending_ladder: str = ""
    _tz: str = "UTC"

    # Editing a logged set.
    editing_set_id: str = ""
    edit_is_cardio: bool = False
    edit_weight: str = ""
    edit_reps: str = ""
    edit_rpe: str = ""
    edit_duration: str = ""
    edit_distance: str = ""
    edit_warmup: bool = False

    show_summary: bool = False
    summary: FinishSummary = FinishSummary()
    confirm_abandon: bool = False

    @rx.var
    def has_session(self) -> bool:
        return self.session_id != ""

    @rx.var
    def has_cards(self) -> bool:
        return len(self.cards) > 0

    @rx.var
    def has_routines(self) -> bool:
        return len(self.routines) > 0

    @rx.var
    def has_recent(self) -> bool:
        return len(self.recent) > 0

    @rx.var
    def has_pr_others(self) -> bool:
        return len(self.pr_others) > 0

    # --- helpers ----------------------------------------------------------

    async def _auth(self) -> AuthState:
        return await self.get_state(AuthState)

    def _clear_session(self) -> None:
        self.session_id = ""
        self.session_name = ""
        self.started_at = ""
        self.session_points = 0
        self.working_sets = 0
        self.volume_label = ""
        self.cards = []
        self.confirm_abandon = False
        self.editing_set_id = ""
        self.pending = ""

    def _pending_for(self, session_id: str) -> list[str]:
        try:
            data = json.loads(self.pending or "{}")
        except ValueError:
            return []
        if not isinstance(data, dict) or data.get("session") != session_id:
            return []
        return [i for i in data.get("ids") or [] if isinstance(i, str)]

    def _save_pending(self) -> None:
        ids = [c.exercise_id for c in self.cards if not c.sets]
        self.pending = (
            json.dumps({"session": self.session_id, "ids": ids})
            if self.session_id and ids
            else ""
        )

    def _apply_session(self, data: dict[str, Any]) -> None:
        """Render the server's copy of the session, keeping per-card entry
        fields and any exercise added from the picker but not yet logged."""
        same = data.get("id") == self.session_id
        existing = {c.exercise_id: c for c in self.cards} if same else {}
        unit = self.unit

        self.session_id = data.get("id") or ""
        self.session_name = session_title(data.get("name"), data.get("started_at"), self._tz)
        self.started_at = data.get("started_at") or ""
        self.session_points = data.get("points_total") or 0
        self.working_sets = data.get("working_sets") or 0
        self.volume_label = f"{thousands(to_unit(data.get('total_volume_kg'), unit))} {unit}"

        cards: list[ExerciseCard] = []
        seen: set[str] = set()
        for item in data.get("exercises") or []:
            exercise = item.get("exercise") or {}
            seen.add(exercise.get("id") or "")
            cards.append(
                build_card(
                    exercise,
                    item.get("sets") or [],
                    item.get("previous_sets") or [],
                    item.get("target"),
                    unit,
                    existing.get(exercise.get("id") or ""),
                    hint=item.get("hint"),
                )
            )
        if same:
            cards += [c for c in self.cards if c.exercise_id not in seen and not c.sets]
        self.cards = cards
        self._save_pending()

    async def _restore_pending(self, token: str, ids: list[str]) -> None:
        """Re-add exercises picked before a refresh but never logged."""
        present = {c.exercise_id for c in self.cards}
        cards = list(self.cards)
        for exercise_id in ids:
            if exercise_id in present:
                continue
            try:
                exercise = await wapi.get_exercise(token, exercise_id)
                last = await wapi.last_performance(token, exercise_id)
            except ApiError:
                # Deleted or no longer visible: drop it quietly.
                continue
            cards.append(
                build_card(exercise, [], last.get("sets") or [], None, self.unit, None, hint=last.get("hint"))
            )
            present.add(exercise_id)
        self.cards = cards
        self._save_pending()

    def _update(self, index: int, **changes: Any) -> None:
        # Reassign the list: Reflex marks a var dirty on assignment, and a
        # nested in-place write can render stale (see the progress log).
        cards = list(self.cards)
        if 0 <= index < len(cards):
            cards[index] = dataclasses.replace(cards[index], **changes)
            self.cards = cards

    def _index_of(self, exercise_id: str) -> int:
        return next((i for i, c in enumerate(self.cards) if c.exercise_id == exercise_id), -1)

    async def _raise_level_up(self, kind: str, badge: str, ladder: str = "") -> None:
        """Reuse the app's one level-up overlay rather than a second copy, so
        the workout feeds the same game moment quests do."""
        quests = await self.get_state(QuestState)
        quests.level_up_is_rank = kind == "rank"
        quests.level_up_badge = badge
        quests.level_up_ladder = ladder
        quests.level_up_message = "RANK UP" if kind == "rank" else "LEVEL UP"
        quests.show_level_up = True

    # --- loading ----------------------------------------------------------

    async def load(self):
        auth = await self._auth()
        if not auth.token:
            return
        self.unit = auth.weight_unit or "kg"
        self._tz = auth.timezone or "UTC"
        self.error = ""
        try:
            active = (await wapi.active_session(auth.token)).get("session")
            self.streak = StreakView.from_api((await wapi.points(auth.token)).get("streak") or {})
            if active:
                restore = self._pending_for(active.get("id") or "")
                self._apply_session(active)
                if restore:
                    await self._restore_pending(auth.token, restore)
            else:
                self._clear_session()
                self.routines = [
                    RoutineItem.from_api(r, self.unit)
                    for r in await wapi.list_routines(auth.token)
                ]
                self.recent = [
                    HistoryRow.from_api(h, self.unit, auth.timezone)
                    for h in await wapi.list_sessions(auth.token, limit=5)
                ]
        except ApiError as exc:
            self.error = exc.detail
        finally:
            self.loaded = True

    async def set_unit(self, unit: str):
        """Save the display unit on the ACCOUNT, then re-render in it."""
        if unit not in WEIGHT_STEP or unit == self.unit:
            return
        auth = await self._auth()
        try:
            data = await wapi.update_account(auth.token, {"weight_unit": unit})
        except ApiError as exc:
            self.error = exc.detail
            return
        auth.weight_unit = data.get("weight_unit") or unit
        self.unit = auth.weight_unit
        return WorkoutState.load

    # --- starting ---------------------------------------------------------

    async def start_session(self, routine_id: str = ""):
        auth = await self._auth()
        self._tz = auth.timezone or "UTC"
        self.error = ""
        self.show_summary = False
        try:
            data = await wapi.start_session(auth.token, routine_id or None)
        except ApiError as exc:
            self.error = exc.detail
            # 409: a workout is already live. Show it rather than a dead end.
            return WorkoutState.load if exc.status == 409 else None
        self.cards = []
        self._apply_session(data)
        return rx.redirect("/workout")

    async def add_exercise(self, exercise_id: str):
        if self._index_of(exercise_id) >= 0:
            return
        auth = await self._auth()
        try:
            exercise = await wapi.get_exercise(auth.token, exercise_id)
            last = await wapi.last_performance(auth.token, exercise_id)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.cards = [
            *self.cards,
            build_card(exercise, [], last.get("sets") or [], None, self.unit, None, hint=last.get("hint")),
        ]
        self._save_pending()

    def remove_card(self, index: int) -> None:
        """Only an exercise with nothing logged can be removed - a logged set
        is removed by deleting the set."""
        if 0 <= index < len(self.cards) and not self.cards[index].sets:
            self.cards = [c for i, c in enumerate(self.cards) if i != index]
            self._save_pending()

    # --- entry fields -----------------------------------------------------

    def set_weight(self, index: int, value: str) -> None:
        self._update(index, weight_input=value)

    def set_reps(self, index: int, value: str) -> None:
        self._update(index, reps_input=value)

    def set_rpe(self, index: int, value: str) -> None:
        self._update(index, rpe_input=value)

    def set_duration(self, index: int, value: str) -> None:
        self._update(index, duration_input=value)

    def set_distance(self, index: int, value: str) -> None:
        self._update(index, distance_input=value)

    def toggle_warmup(self, index: int) -> None:
        if 0 <= index < len(self.cards):
            self._update(index, warmup=not self.cards[index].warmup)

    def bump_weight(self, index: int, direction: int) -> None:
        if not 0 <= index < len(self.cards):
            return
        current = max(0.0, _num(self.cards[index].weight_input))
        step = WEIGHT_STEP.get(self.unit, 2.5)
        self._update(index, weight_input=fmt(max(0.0, current + direction * step)))

    def bump_reps(self, index: int, direction: int) -> None:
        if not 0 <= index < len(self.cards):
            return
        current = max(0.0, _num(self.cards[index].reps_input))
        self._update(index, reps_input=str(int(max(1, current + direction))))

    # --- logging ----------------------------------------------------------

    async def log_set(self, index: int):
        if self.busy or not 0 <= index < len(self.cards):
            return
        card = self.cards[index]
        payload, problem = set_payload(card, self.unit)
        if payload is None:
            self.error = problem
            return

        auth = await self._auth()
        self.busy = True
        self.error = ""
        yield

        try:
            result = await wapi.log_set(auth.token, self.session_id, payload)
            session = await wapi.get_session(auth.token, self.session_id)
        except ApiError as exc:
            self.busy = False
            self.error = exc.detail
            if exc.status in (404, 409):
                # Finished or abandoned elsewhere (another tab): re-sync.
                yield WorkoutState.load
            return
        self.busy = False

        # Rotate the idempotency key only now, after a confirmed log.
        self._update(index, client_set_id=str(uuid.uuid4()))
        self._apply_session(session)
        if not result.get("is_duplicate"):
            await self._show_outcome(card.exercise_id, result)
            if not card.warmup:
                yield rx.call_script(
                    f"window.maRest && window.maRest.start({int(card.rest_seconds)})"
                )
        yield AuthState.refresh_me

    async def _show_outcome(self, exercise_id: str, result: dict[str, Any]) -> None:
        """Turn the API's verdict on a set into the right-sized moment.

        A paid PR gets the full-screen moment; a record that earned no bonus
        gets a pill on the card; a first-ever log gets a quiet note. The
        classification is the API's (bonus_awarded / is_baseline), not ours.
        """
        unit = self.unit
        events = result.get("pr_events") or []
        paid = next((e for e in events if e.get("bonus_awarded")), None)
        real = [e for e in events if not e.get("is_baseline")]

        kind, label = "", ""
        if paid is not None:
            self.pr = PrView.from_api(paid, unit)
            self.pr_others = [PrView.from_api(e, unit) for e in real if e is not paid]
            self.pr_points = sum(
                a.get("points") or 0
                for a in result.get("awards") or []
                if a.get("source_type") == "pr_achieved"
            )
            self.show_pr = True
            kind, label = "pr", f"PR · {self.pr.headline}"
        elif real:
            kind, label = "record", f"NEW RECORD · {PrView.from_api(real[0], unit).headline}"
        elif events:
            kind, label = "first", "BASELINE SET"

        index = self._index_of(exercise_id)
        if index >= 0:
            self._update(index, flash_kind=kind, flash_label=label)

        beat, badge, ladder = level_beat(result.get("progression") or {})
        if beat:
            if self.show_pr:
                self._pending_kind, self._pending_badge = beat, badge
                self._pending_ladder = ladder
            else:
                await self._raise_level_up(beat, badge, ladder)

    async def dismiss_pr(self):
        self.show_pr = False
        if self._pending_kind:
            kind, badge, ladder = self._pending_kind, self._pending_badge, self._pending_ladder
            self._pending_kind = self._pending_badge = self._pending_ladder = ""
            await self._raise_level_up(kind, badge, ladder)

    async def delete_set(self, set_id: str):
        auth = await self._auth()
        self.error = ""
        try:
            await wapi.delete_set(auth.token, self.session_id, set_id)
            session = await wapi.get_session(auth.token, self.session_id)
        except ApiError as exc:
            self.error = exc.detail
            return
        if self.editing_set_id == set_id:
            self.editing_set_id = ""
        self._apply_session(session)
        return AuthState.refresh_me

    # --- editing a logged set ---------------------------------------------

    def start_edit(self, set_id: str) -> None:
        for card in self.cards:
            for row in card.sets:
                if row.id != set_id:
                    continue
                self.editing_set_id = set_id
                self.edit_is_cardio = card.is_cardio
                self.edit_weight = row.weight or ("" if card.is_cardio else "0")
                self.edit_reps = row.reps
                self.edit_rpe = row.rpe
                self.edit_duration = row.duration_min
                self.edit_distance = row.distance_km
                self.edit_warmup = row.is_warmup
                self.error = ""
                return

    def cancel_edit(self) -> None:
        self.editing_set_id = ""

    def set_edit_weight(self, value: str) -> None:
        self.edit_weight = value

    def set_edit_reps(self, value: str) -> None:
        self.edit_reps = value

    def set_edit_rpe(self, value: str) -> None:
        self.edit_rpe = value

    def set_edit_duration(self, value: str) -> None:
        self.edit_duration = value

    def set_edit_distance(self, value: str) -> None:
        self.edit_distance = value

    def toggle_edit_warmup(self) -> None:
        self.edit_warmup = not self.edit_warmup

    async def save_edit(self):
        """PATCH the set. The API reverses its old awards and judges the
        edited set afresh, so an edit can earn (or lose) a PR - which is then
        shown exactly like a newly logged one."""
        set_id = self.editing_set_id
        exercise_id = next(
            (c.exercise_id for c in self.cards if any(r.id == set_id for r in c.sets)), ""
        )
        if not set_id or not exercise_id:
            self.editing_set_id = ""
            return

        draft = ExerciseCard(
            exercise_id=exercise_id,
            is_cardio=self.edit_is_cardio,
            weight_input=self.edit_weight,
            reps_input=self.edit_reps,
            rpe_input=self.edit_rpe,
            duration_input=self.edit_duration,
            distance_input=self.edit_distance,
            warmup=self.edit_warmup,
        )
        payload, problem = set_payload(draft, self.unit)
        if payload is None:
            self.error = problem
            return
        payload.pop("exercise_id", None)
        payload.pop("client_set_id", None)
        # A cleared field must be sent as null to actually clear it.
        payload.setdefault("rpe", None)
        if self.edit_is_cardio:
            payload.setdefault("duration_seconds", None)
            payload.setdefault("distance_m", None)

        auth = await self._auth()
        self.busy = True
        self.error = ""
        yield
        try:
            result = await wapi.update_set(auth.token, self.session_id, set_id, payload)
            session = await wapi.get_session(auth.token, self.session_id)
        except ApiError as exc:
            self.busy = False
            self.error = exc.detail
            return
        self.busy = False
        self.editing_set_id = ""
        self._apply_session(session)
        await self._show_outcome(exercise_id, result)
        yield AuthState.refresh_me

    # --- sharing ----------------------------------------------------------

    async def share_card(self):
        """Draw this workout's story card in the browser and share or download it.
        The footer invites friends into the user's first active party."""
        summary = self.summary
        auth = await self._auth()
        invite = ""
        try:
            parties = await core_api.list_parties(auth.token)
            active = [p for p in parties if p.get("is_active", True)]
            if active:
                invite = active[0].get("invite_code") or ""
        except ApiError:
            pass  # the card still works without an invite
        card = {
            "kind": summary.share_kind or "workout",
            "eyebrow": summary.share_eyebrow,
            "headline": summary.share_headline,
            "caption": summary.share_caption,
            "stats": [
                {"value": summary.duration_label, "label": "Duration"},
                {"value": summary.volume_label, "label": "Volume"},
                {"value": summary.sets_label, "label": "Sets"},
            ],
            "footer": f"Join my party: {invite}" if invite else "Level up every workout",
        }
        return rx.call_script(share_card_script(card))

    # --- finishing --------------------------------------------------------

    async def finish(self):
        if self.busy or not self.session_id:
            return
        auth = await self._auth()
        self.busy = True
        self.error = ""
        yield
        try:
            result = await wapi.finish_session(auth.token, self.session_id)
        except ApiError as exc:
            self.busy = False
            self.error = exc.detail
            return
        self.busy = False
        self.summary = FinishSummary.from_api(result, self.session_name, self.unit)
        self.show_summary = True
        self._clear_session()
        yield rx.call_script(_STOP_REST)

        beat, badge, ladder = level_beat(result.get("progression") or {})
        if beat:
            await self._raise_level_up(beat, badge, ladder)
        yield AuthState.refresh_me

    def ask_abandon(self) -> None:
        self.confirm_abandon = True

    def cancel_abandon(self) -> None:
        self.confirm_abandon = False

    async def abandon(self):
        auth = await self._auth()
        self.error = ""
        try:
            await wapi.abandon_session(auth.token, self.session_id)
        except ApiError as exc:
            self.error = exc.detail
            return
        self._clear_session()
        yield rx.call_script(_STOP_REST)
        yield WorkoutState.load
        yield AuthState.refresh_me

    def close_summary(self):
        self.show_summary = False
        return WorkoutState.load
