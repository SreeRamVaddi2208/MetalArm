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
import uuid
from typing import Any

import reflex as rx

from metalarm import api as core_api
from metalarm import ranks
from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.share_card import share_card_script
from metalarm.ui.body_map import paths_for
from metalarm.ui.toast import ToastState
from metalarm.state.auth import AuthState
from metalarm.state.quests import QuestState
from metalarm.workout_models import (
    Beat,
    ExerciseCard,
    FinishSummary,
    HistoryRow,
    PresetSlot,
    PrView,
    QuestLine,
    VoiceProposal,
    RoutineItem,
    WorkoutPreset,
    SetRow,
    StreakView,
    fmt,
    muscles_label,
    plural,
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
    meta: dict[str, Any] | None = None,
) -> ExerciseCard:
    """An exercise card from API data.

    `keep` is the card as it was before this refresh: its half-typed entry
    fields, warm-up toggle and idempotency key survive, so a server round trip
    never wipes what the user is typing. A NEW card is pre-filled from the last
    set logged this session, else last time's first set, else the routine's
    target - one tap then repeats it, which is the whole logging loop.
    """
    prev = [SetRow.from_api(s, unit) for s in previous]
    # Each logged set shows last session's set at the same position.
    rows = [
        dataclasses.replace(SetRow.from_api(s, unit), previous=prev[i].summary if i < len(prev) else "-")
        for i, s in enumerate(sets)
    ]
    t = target or {}
    m = meta or {}

    bits = []
    if t.get("target_sets"):
        bits.append(plural(t['target_sets'], "set"))
    if t.get("target_reps"):
        bits.append(f"× {t['target_reps']}")
    if t.get("target_weight_kg"):
        bits.append(f"@ {weight_label(t['target_weight_kg'], unit)}")

    card = ExerciseCard(
        exercise_id=exercise.get("id") or "",
        session_exercise_id=str(m.get("session_exercise_id") or ""),
        superset_group=int(m.get("superset_group") or 0),
        notes=m.get("notes") or "",
        entry_previous=prev[len(rows)].summary if len(rows) < len(prev) else "-",
        ghost_weight=prev[len(rows)].weight if len(rows) < len(prev) else "",
        ghost_reps=prev[len(rows)].reps if len(rows) < len(prev) else "",
        name=exercise.get("name") or "",
        muscles_label=muscles_label(exercise.get("primary_muscle_groups")),
        media_url=exercise.get("media_url") or "",
        thumbnail_url=exercise.get("thumbnail_url") or "",
        is_cardio=exercise.get("category") == "cardio",
        target_label=" ".join(bits),
        target_count=int(t.get("target_sets") or 0),
        rest_seconds=int(m.get("rest_seconds") or t.get("rest_seconds") or DEFAULT_REST_SECONDS),
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
            entry_type=keep.entry_type,
            menu_open=keep.menu_open,
            last_points=keep.last_points,
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
        "set_type": card.entry_type,
        "client_set_id": card.client_set_id,
    }
    if card.session_exercise_id:
        payload["session_exercise_id"] = card.session_exercise_id
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


def level_beat(progression: dict[str, Any]) -> Beat:
    """What to celebrate, from the API's explicit flags.

    `ranked_up` is true only on promotion, so a demotion never fires a
    celebration. A rank-up's badge is the tier, not the letter - and it carries
    the letter too, because that is what the overlay dresses itself from."""
    levels = (
        int(progression.get("level_before") or 0),
        int(progression.get("level_after") or 0),
    )
    if progression.get("ranked_up"):
        after = str(progression.get("rank_after") or "")
        return Beat(
            kind="rank",
            badge=ranks.rank_title(after).upper(),
            ladder=ranks.promotion(str(progression.get("rank_before") or ""), after),
            rank=after,
            level_from=levels[0],
            level_to=levels[1],
        )
    if progression.get("leveled_up"):
        return Beat(
            kind="level",
            badge=str(progression.get("level_after") or ""),
            level_from=levels[0],
            level_to=levels[1],
        )
    return Beat()


class WorkoutState(rx.State):
    # Display unit, copied from the account (AuthState.weight_unit) on load.
    unit: str = "kg"
    # Exercises added but not yet logged: {"session": id, "ids": [...]}.

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
    # Ready-made workouts, one per training style, with a demo per movement.
    presets: list[WorkoutPreset] = []
    # The one whose plan is open, and the movement its demo is showing.
    open_preset: str = ""
    demo_slot: str = ""
    recent: list[HistoryRow] = []
    streak: StreakView = StreakView()

    # The PR moment.
    show_pr: bool = False
    # Bumped per record so the in-workout banner replays for each one.
    pr_serial: int = 0
    # The open sheets: an exercise's options (its index, -1 for none) and
    # the Finish confirmation.
    options_index: int = -1
    # The options card's id and its notes as the server has them, so a typed
    # note is saved before anything that re-reads the session can drop it.
    options_card_id: str = ""
    options_notes_saved: str = ""
    confirm_finish: bool = False
    # The card being worked on: the only one showing the steppers and the
    # accent Log set (one accent action per screen).
    focus_index: int = 0
    pr: PrView = PrView()
    pr_others: list[PrView] = []
    pr_points: int = 0
    # The in-session quest chip: the quest the last set moved, as the API
    # reported it. Read-only - it adds nothing to the logging loop.
    quest_chip: QuestLine = QuestLine()
    # A quest the last set completed: a small inline moment in the HUD,
    # deliberately below the PR overlay and the level-up in size.
    quest_done: QuestLine = QuestLine()
    # Voice / typed logging. The proposal is the API's (POST /log/parse);
    # nothing in it is logged until the user taps "Log it".
    voice_text: str = ""
    show_typed: bool = False
    voice_busy: bool = False
    voice_error: str = ""
    proposal: VoiceProposal = VoiceProposal()
    # Sets the last confirmed proposal logged, for Undo.
    undo_set_ids: list[str] = []
    # A level-up earned by the same set waits until the PR moment is
    # dismissed, so the two celebrations never stack on top of each other.
    _pending_beat: Beat = Beat()
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
    # The finished workout, for "Save as routine"; and its muscles: path id ->
    # intensity for the body map, plus the names, most worked first.
    summary_session_id: str = ""
    summary_muscles: dict[str, float] = {}
    summary_muscle_names: list[str] = []
    summary_saved: str = ""
    summary_visibility: str = "followers"
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

    @rx.var
    def has_proposal(self) -> bool:
        return self.proposal.parse_id != ""

    @rx.var
    def can_undo_voice(self) -> bool:
        return len(self.undo_set_ids) > 0

    @rx.var
    def has_quest_chip(self) -> bool:
        return self.quest_chip.id != ""

    @rx.var
    def has_quest_done(self) -> bool:
        return self.quest_done.id != ""

    # --- helpers ----------------------------------------------------------

    async def _auth(self) -> AuthState:
        return await self.get_state(AuthState)

    def _clear_session(self) -> None:
        self.quest_chip = QuestLine()
        self.quest_done = QuestLine()
        self.proposal = VoiceProposal()
        self.undo_set_ids = []
        self.voice_error = ""
        self.session_id = ""
        self.session_name = ""
        self.started_at = ""
        self.session_points = 0
        self.working_sets = 0
        self.volume_label = ""
        self.cards = []
        self.confirm_abandon = False
        self.editing_set_id = ""

    def _apply_session(self, data: dict[str, Any]) -> None:
        """Render the server's copy of the session, keeping per-card entry
        fields and any exercise added from the picker but not yet logged."""
        same = data.get("id") == self.session_id
        existing = {c.session_exercise_id: c for c in self.cards} if same else {}
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
                    existing.get(str(item.get("session_exercise_id") or "")),
                    hint=item.get("hint"),
                    meta=item,
                )
            )
        # The server holds every card now, logged or not: no client-side copy.
        self.cards = cards

    def _update(self, index: int, **changes: Any) -> None:
        # Reassign the list: Reflex marks a var dirty on assignment, and a
        # nested in-place write can render stale (see the progress log).
        cards = list(self.cards)
        if 0 <= index < len(cards):
            cards[index] = dataclasses.replace(cards[index], **changes)
            self.cards = cards

    def _index_of(self, exercise_id: str) -> int:
        return next((i for i, c in enumerate(self.cards) if c.exercise_id == exercise_id), -1)

    async def _raise_level_up(self, beat: Beat) -> None:
        """Reuse the app's one level-up overlay rather than a second copy, so
        the workout feeds the same game moment quests do - including the tier
        dressing, which QuestState.celebrate resolves."""
        quests = await self.get_state(QuestState)
        quests.celebrate(
            beat.kind,
            beat.badge,
            beat.ladder,
            rank=beat.rank,
            level_from=beat.level_from,
            level_to=beat.level_to,
        )

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
                self._apply_session(active)
                self._refocus()
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
                # A failure here must not block starting a workout, so the
                # cards simply do not appear.
                try:
                    self.presets = [
                        WorkoutPreset.from_api(p) for p in await wapi.presets(auth.token)
                    ]
                except ApiError:
                    self.presets = []
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
        from metalarm.state.train import TrainState

        return [WorkoutState.load, TrainState.load]

    # --- starting ---------------------------------------------------------

    def choose_preset(self, slug: str) -> None:
        """Open a ready-made workout's plan, its demo on the first movement."""
        self.open_preset = slug
        chosen = next((p for p in self.presets if p.slug == slug), None)
        self.demo_slot = chosen.exercises[0].exercise_id if chosen and chosen.exercises else ""

    def close_preset(self) -> None:
        self.open_preset = ""
        self.demo_slot = ""

    def show_demo(self, exercise_id: str) -> None:
        self.demo_slot = exercise_id

    @rx.var
    def chosen_preset(self) -> WorkoutPreset:
        return next(
            (p for p in self.presets if p.slug == self.open_preset), WorkoutPreset()
        )

    @rx.var
    def demo_exercise(self) -> PresetSlot:
        """The movement the demo is showing: the tapped one, else the first."""
        chosen = self.chosen_preset
        if not chosen.exercises:
            return PresetSlot()
        return next(
            (slot for slot in chosen.exercises if slot.exercise_id == self.demo_slot),
            chosen.exercises[0],
        )

    @rx.var
    def has_presets(self) -> bool:
        return len(self.presets) > 0

    async def start_preset(self, slug: str):
        """Start a ready-made workout. A separate handler from start_session
        because an event handler's extra argument is where Reflex puts the
        click event itself - one handler cannot take both."""
        self.close_preset()
        return await self._start(preset_slug=slug)

    async def start_session(self, routine_id: str = ""):
        return await self._start(routine_id=routine_id)

    async def _start(self, routine_id: str = "", preset_slug: str = ""):
        auth = await self._auth()
        self._tz = auth.timezone or "UTC"
        self.error = ""
        self.show_summary = False
        try:
            data = await wapi.start_session(
                auth.token, routine_id or None, preset_slug or None
            )
        except ApiError as exc:
            self.error = exc.detail
            # 409: a workout is already live. Show it rather than a dead end.
            return WorkoutState.load if exc.status == 409 else None
        self.cards = []
        self.focus_index = 0
        self._apply_session(data)
        return rx.redirect("/train")

    async def add_exercise(self, exercise_id: str):
        """A new card at the end of the workout - on the server, so it is there
        after a refresh before a single set is logged."""
        auth = await self._auth()
        try:
            session = await wapi.add_session_exercise(auth.token, self.session_id, exercise_id)
        except ApiError as exc:
            self.error = exc.detail
            return
        self._apply_session(session)
        self.focus_index = len(self.cards) - 1

    async def remove_card(self, index: int):
        """Take a card out. With sets on it, those sets go too and their
        awards are reversed - the menu asks first."""
        if not 0 <= index < len(self.cards):
            return
        card = self.cards[index]
        auth = await self._auth()
        try:
            session = await wapi.remove_session_exercise(
                auth.token, self.session_id, card.session_exercise_id, force=bool(card.sets))
        except ApiError as exc:
            self.error = exc.detail
            return
        self._apply_session(session)
        yield AuthState.refresh_me

    # --- the card menu ----------------------------------------------------

    def toggle_menu(self, index: int) -> None:
        if 0 <= index < len(self.cards):
            self._update(index, menu_open=not self.cards[index].menu_open)

    async def _patch_card(self, index: int, payload: dict[str, Any]) -> None:
        auth = await self._auth()
        try:
            session = await wapi.update_session_exercise(
                auth.token, self.session_id, self.cards[index].session_exercise_id, payload)
        except ApiError as exc:
            self.error = exc.detail
            return
        self._apply_session(session)

    async def move_card(self, index: int, direction: int):
        target = index + direction
        if not (0 <= index < len(self.cards) and 0 <= target < len(self.cards)):
            return
        order = [c.session_exercise_id for c in self.cards]
        order[index], order[target] = order[target], order[index]
        auth = await self._auth()
        try:
            session = await wapi.reorder_session_exercises(auth.token, self.session_id, order)
        except ApiError as exc:
            self.error = exc.detail
            return
        self._apply_session(session)
        self.cards = [dataclasses.replace(c, menu_open=False) for c in self.cards]

    async def superset_with_next(self, index: int):
        """This card and the next become one superset (or leave it)."""
        if not 0 <= index < len(self.cards) - 1:
            return
        this, nxt = self.cards[index], self.cards[index + 1]
        if this.superset_group and this.superset_group == nxt.superset_group:
            await self._patch_card(index, {"superset_group": None})
            await self._patch_card(index + 1, {"superset_group": None})
            return
        group = this.superset_group or nxt.superset_group or (
            max([c.superset_group for c in self.cards] + [0]) + 1)
        await self._patch_card(index, {"superset_group": group})
        await self._patch_card(index + 1, {"superset_group": group})

    def set_notes(self, index: int, value: str) -> None:
        self._update(index, notes=value)

    async def save_notes(self, card_id: str, value: str):
        """On blur, keyed by card id: a reorder can land first and move the
        card to another index."""
        index = next((i for i, c in enumerate(self.cards) if c.session_exercise_id == card_id), -1)
        if index >= 0:
            await self._patch_card(index, {"notes": (value or "").strip() or None})

    async def bump_rest(self, index: int, seconds: int):
        if 0 <= index < len(self.cards):
            rest = max(0, min(600, self.cards[index].rest_seconds + seconds))
            await self._patch_card(index, {"rest_seconds": rest})

    # --- the set row --------------------------------------------------------

    def cycle_type(self, index: int) -> None:
        """Tap the SET cell: normal -> warm-up -> drop -> failure -> normal."""
        order = ["normal", "warmup", "drop", "failure"]
        if 0 <= index < len(self.cards):
            current = self.cards[index].entry_type
            nxt = order[(order.index(current) + 1) % len(order)] if current in order else "normal"
            self._update(index, entry_type=nxt, warmup=nxt == "warmup")

    def copy_previous(self, index: int) -> None:
        """Tap PREVIOUS: last session's set at this position into the fields."""
        if not 0 <= index < len(self.cards):
            return
        card = self.cards[index]
        position = len(card.sets)
        if position < len(card.previous):
            last = card.previous[position]
            self._update(index, weight_input=last.weight, reps_input=last.reps)

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
        points = int(result.get("points_awarded") or 0)
        # A set type is for one set: the next entry is a normal set again.
        self._update(index, client_set_id=str(uuid.uuid4()), entry_type="normal", warmup=False,
                     last_points=f"+{points}" if points > 0 else "")
        self._apply_session(session)
        self.undo_set_ids = []
        if not result.get("is_duplicate"):
            self._advance(index)
            self._show_quests(result)
            await self._show_outcome(card.exercise_id, result)
            if not card.warmup:
                yield rx.call_script(
                    f"window.maRest && window.maRest.start({int(card.rest_seconds)})"
                )
            if self.show_pr:
                # A light tap for a record, where the device and the setting allow.
                yield rx.call_script("localStorage.getItem('ma_haptics') !== 'off' && navigator.vibrate"
                                     " && navigator.vibrate(30)")
            if self.quest_done.id:
                yield ToastState.show(f"Quest complete · {self.quest_done.title}", "scroll-text")
        yield AuthState.refresh_me

    def focus(self, index: int) -> None:
        self.focus_index = index

    @staticmethod
    def _working(card: ExerciseCard) -> int:
        return sum(1 for r in card.sets if r.set_type != "warmup")

    def _short(self, card: ExerciseCard) -> bool:
        """Still owes sets: under its plan, or untouched when it has none."""
        return self._working(card) < card.target_count if card.target_count else not card.sets

    def _refocus(self) -> None:
        """After a reload: stay on the card in focus if it still owes sets,
        otherwise the first that does."""
        if 0 <= self.focus_index < len(self.cards) and self._short(self.cards[self.focus_index]):
            return
        nxt = next((i for i, c in enumerate(self.cards) if self._short(c)), None)
        if nxt is not None:
            self.focus_index = nxt
        elif not 0 <= self.focus_index < len(self.cards):
            self.focus_index = max(0, len(self.cards) - 1)

    def _advance(self, index: int) -> None:
        """Move the entry panel on once this card has done its part, so the
        next set is one tap away: within a superset to the partner that is
        behind, otherwise to the next exercise still short of its plan."""
        working, short = self._working, self._short
        card = self.cards[index]
        if card.superset_group:
            group = [i for i, c in enumerate(self.cards) if c.superset_group == card.superset_group]
            partners = group[group.index(index) + 1:] + group[:group.index(index) + 1]
            nxt = next((i for i in partners if short(self.cards[i]) and working(self.cards[i]) <= working(card)),
                       None)
            if nxt is not None:
                self.focus_index = nxt
                return
        if card.target_count and working(card) < card.target_count:
            return
        nxt = next((i for i in range(index + 1, len(self.cards)) if short(self.cards[i])), None)
        if nxt is not None:
            self.focus_index = nxt

    def set_entry_type(self, index: int, kind: str) -> None:
        if 0 <= index < len(self.cards) and kind in ("normal", "warmup", "drop", "failure"):
            self._update(index, entry_type=kind, warmup=kind == "warmup")

    def open_options(self, index: int) -> None:
        self.options_index = index
        if 0 <= index < len(self.cards):
            self.options_card_id = self.cards[index].session_exercise_id
            self.options_notes_saved = self.cards[index].notes

    async def flush_notes(self):
        """Save the options card's note if it was edited and not yet saved."""
        card = next((c for c in self.cards if c.session_exercise_id == self.options_card_id), None)
        if card is not None and card.notes != self.options_notes_saved:
            self.options_notes_saved = card.notes
            await self.save_notes(card.session_exercise_id, card.notes)

    async def close_options(self):
        await self.flush_notes()
        self.options_index = -1
        self.options_card_id = ""

    def ask_finish(self) -> None:
        self.confirm_finish = True

    def cancel_finish(self) -> None:
        self.confirm_finish = False

    @rx.var
    def options_card(self) -> ExerciseCard:
        return self.cards[self.options_index] if 0 <= self.options_index < len(self.cards) else ExerciseCard()

    def _show_quests(self, result: dict[str, Any]) -> None:
        """The chip follows whichever quest this set moved; a quest it
        completed gets the small moment. Both straight from the response."""
        done = result.get("quests_completed") or []
        moved = [q for q in result.get("quest_progress") or [] if q.get("advanced")]
        self.quest_done = QuestLine.from_api(done[0]) if done else QuestLine()
        if moved:
            # An unfinished quest is the more useful thing to keep in view.
            moved.sort(key=lambda q: bool(q.get("completed")))
            self.quest_chip = QuestLine.from_api(moved[0])

    # --- voice / typed logging ------------------------------------------------

    def set_voice_text(self, value: str) -> None:
        self.voice_text = value

    def toggle_typed(self) -> None:
        self.show_typed = not self.show_typed

    def _current_card_id(self) -> str:
        """The exercise a bare "80 for 8" means: a card added but not logged
        yet. Otherwise the server uses the session's last set."""
        fresh = [c for c in self.cards if not c.sets]
        return fresh[-1].exercise_id if fresh else ""

    async def voice_done(self, outcome: dict):
        """The mic was released: `outcome` is what the speech script heard,
        {text} or {error}. Errors fall back to the typed box."""
        outcome = outcome or {}
        error = outcome.get("error") or ""
        text = (outcome.get("text") or "").strip()
        if error or not text:
            self.voice_error = {
                "denied": "Microphone access is off - type it instead.",
                "unsupported": "Voice isn't available in this browser - type it instead.",
            }.get(error, "Didn't catch anything - try again or type it.")
            self.show_typed = True
            return
        self.voice_text = text
        async for update in self._parse(text):
            yield update

    async def submit_typed(self):
        text = self.voice_text.strip()
        if not text:
            return
        async for update in self._parse(text):
            yield update

    async def _parse(self, text: str):
        auth = await self._auth()
        self.voice_busy = True
        self.voice_error = ""
        yield
        try:
            data = await wapi.parse_set(
                auth.token, text, self.session_id, self._current_card_id()
            )
        except ApiError as exc:
            self.voice_busy = False
            self.voice_error = exc.detail
            return
        self.voice_busy = False
        if not data.get("proposed_sets"):
            self.proposal = VoiceProposal()
            self.voice_error = data.get("problem") or "Couldn't understand that."
            self.show_typed = True
            return
        self.proposal = VoiceProposal.from_api(data)
        self.voice_text = ""

    def _edit(self, **changes: Any) -> None:
        self.proposal = dataclasses.replace(self.proposal, **changes)

    def set_proposal_weight(self, value: str) -> None:
        self._edit(weight=value)

    def set_proposal_reps(self, value: str) -> None:
        self._edit(reps=value)

    def set_proposal_rpe(self, value: str) -> None:
        self._edit(rpe=value)

    def toggle_proposal_warmup(self) -> None:
        self._edit(warmup=not self.proposal.warmup)

    def bump_proposal_sets(self, direction: int) -> None:
        self._edit(set_count=max(1, min(20, self.proposal.set_count + direction)))

    def pick_alternative(self, exercise_id: str, name: str) -> None:
        self._edit(exercise_id=exercise_id, exercise_name=name, unsure=False)

    async def discard_proposal(self):
        """Thrown away: recorded as not accepted, so the parser learns what
        it got wrong."""
        auth = await self._auth()
        parse_id, self.proposal = self.proposal.parse_id, VoiceProposal()
        try:
            await wapi.parse_feedback(auth.token, parse_id, {"accepted": False})
        except ApiError:
            pass

    async def confirm_proposal(self):
        """One tap: each proposed set goes through the ordinary log-set
        endpoint, so PRs, points and quests fire exactly as for a tapped set."""
        p = self.proposal
        if self.busy or not p.parse_id or not self.session_id:
            return
        reps, weight = _num(p.reps), _num(p.weight)
        if reps < 1 or reps != int(reps) or weight < 0:
            self.voice_error = "Check the weight and reps."
            return
        payload: dict[str, Any] = {
            "exercise_id": p.exercise_id,
            "weight": weight,
            "unit": p.unit,
            "reps": int(reps),
            "is_warmup": p.warmup,
        }
        if p.rpe.strip():
            rpe = _num(p.rpe)
            if not 1 <= rpe <= 10:
                self.voice_error = "RPE is 1 to 10."
                return
            payload["rpe"] = rpe

        auth = await self._auth()
        self.busy = True
        self.voice_error = ""
        yield
        logged: list[str] = []
        result: dict[str, Any] = {}
        try:
            for _ in range(p.set_count):
                result = await wapi.log_set(
                    auth.token, self.session_id, {**payload, "client_set_id": str(uuid.uuid4())}
                )
                logged.append((result.get("set") or {}).get("id") or "")
            session = await wapi.get_session(auth.token, self.session_id)
        except ApiError as exc:
            self.busy = False
            self.voice_error = exc.detail
            if logged:
                yield WorkoutState.load
            return
        self.busy = False

        edited = p.signature() != p.original
        feedback: dict[str, Any] = {"accepted": not edited}
        if edited:
            feedback["corrected_result"] = {
                **{k: v for k, v in payload.items() if k != "is_warmup"},
                "is_warmup": p.warmup,
                "set_count": p.set_count,
            }
        try:
            await wapi.parse_feedback(auth.token, p.parse_id, feedback)
        except ApiError:
            pass  # feedback is for learning; the sets are already logged

        self.proposal = VoiceProposal()
        self.undo_set_ids = [i for i in logged if i]
        self._apply_session(session)
        self._show_quests(result)
        await self._show_outcome(p.exercise_id, result)
        yield AuthState.refresh_me

    async def undo_voice(self):
        auth = await self._auth()
        ids, self.undo_set_ids = self.undo_set_ids, []
        try:
            for set_id in ids:
                await wapi.delete_set(auth.token, self.session_id, set_id)
            session = await wapi.get_session(auth.token, self.session_id)
        except ApiError as exc:
            self.voice_error = exc.detail
            return
        self._apply_session(session)
        yield AuthState.refresh_me

    def _refresh_chip(self, result: dict[str, Any]) -> None:
        """After a delete nothing ADVANCES, but the chip's quest may have
        gone back (and a completed one reopened): show where it stands now."""
        for q in (result or {}).get("quest_progress") or []:
            if str(q.get("assignment_id") or "") == self.quest_chip.id:
                self.quest_chip = QuestLine.from_api(q)
        if self.quest_done.id and not any(
            str(q.get("assignment_id") or "") == self.quest_done.id and q.get("completed")
            for q in (result or {}).get("quest_progress") or []
        ):
            self.quest_done = QuestLine()

    def dismiss_quest_done(self) -> None:
        self.quest_done = QuestLine()

    async def _show_outcome(self, exercise_id: str, result: dict[str, Any]) -> None:
        """Turn the API's verdict on a set into the right-sized moment.

        A paid PR gets the full-screen moment; a record that earned no bonus
        gets a pill on the card; a first-ever log gets a quiet note. The
        classification is the API's (bonus_awarded / is_baseline), not ours.
        """
        unit = self.unit
        self.show_pr = False
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
            self.pr_serial += 1
            kind, label = "pr", f"PR · {self.pr.headline}"
        elif real:
            kind, label = "record", f"NEW RECORD · {PrView.from_api(real[0], unit).headline}"
        elif events:
            kind, label = "first", "Baseline set"

        index = self._index_of(exercise_id)
        if index >= 0:
            self._update(index, flash_kind=kind, flash_label=label)

        # The PR is a banner now - it never blocks - so a level-up plays at once.
        beat = level_beat(result.get("progression") or {})
        if beat.kind:
            await self._raise_level_up(beat)

    async def dismiss_pr(self):
        self.show_pr = False
        if self._pending_beat.kind:
            beat, self._pending_beat = self._pending_beat, Beat()
            await self._raise_level_up(beat)

    async def delete_set(self, set_id: str):
        auth = await self._auth()
        self.error = ""
        try:
            result = await wapi.delete_set(auth.token, self.session_id, set_id)
            session = await wapi.get_session(auth.token, self.session_id)
        except ApiError as exc:
            self.error = exc.detail
            return
        if self.editing_set_id == set_id:
            self.editing_set_id = ""
        self._apply_session(session)
        self._refresh_chip(result)
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
        self.confirm_finish = False
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
        self.summary_session_id = self.session_id
        self.summary_saved = ""
        self.summary_visibility = (result.get("session") or {}).get("visibility") or "followers"
        await self._summary_muscles(auth.token, result.get("muscles_worked") or {})
        self.show_summary = True
        self._clear_session()
        yield rx.call_script(_STOP_REST)

        beat = level_beat(result.get("progression") or {})
        if beat.kind:
            await self._raise_level_up(beat)
        yield AuthState.refresh_me

    async def _summary_muscles(self, token: str, worked: dict[str, float]) -> None:
        """The body map's input. Intensities come from the server; only the
        taxonomy's path ids and names are looked up here."""
        self.summary_muscles, self.summary_muscle_names = {}, []
        if not worked:
            return
        try:
            taxonomy = await core_api.taxonomy(token)
        except ApiError:
            return
        groups = {m["code"]: m for m in taxonomy.get("muscle_groups", [])}
        self.summary_muscles = paths_for(worked, {c: m["svg_path_ids"] for c, m in groups.items()})
        self.summary_muscle_names = [
            groups[c]["display_name"] for c, _ in sorted(worked.items(), key=lambda kv: -kv[1])
            if c in groups
        ][:6]

    async def set_summary_visibility(self, label: str):
        """Who sees the workout just finished - in friends' feeds or not."""
        from metalarm import social_api

        value = {"Public": "public", "Followers": "followers", "Only me": "private"}[label]
        auth = await self._auth()
        try:
            await social_api.set_visibility(auth.token, self.summary_session_id, value)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.summary_visibility = value

    async def save_as_routine(self):
        if not self.summary_session_id or self.summary_saved:
            return
        auth = await self._auth()
        try:
            routine = await wapi.routine_from_session(auth.token, self.summary_session_id)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.summary_saved = routine.get("name") or "Saved"

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
        from metalarm.state.train import TrainState

        yield TrainState.load
        yield AuthState.refresh_me

    def close_summary(self):
        self.show_summary = False
        from metalarm.state.train import TrainState

        return [WorkoutState.load, TrainState.load]
