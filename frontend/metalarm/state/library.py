"""The Library tab: the caller's programs, routines and logged exercises in
one list, their favourites, a program's routines, and starting a workout
from any routine.

Everything listed comes from GET /library, cursor-paged; this state only
holds what is on screen.
"""

from __future__ import annotations

import reflex as rx

from metalarm import theme as t
from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.state.auth import AuthState
from metalarm.state.workout import WorkoutState


def _item(data: dict) -> dict[str, str]:
    title = data.get("title") or ""
    return {
        "type": data.get("type") or "",
        "id": str(data.get("id") or ""),
        "title": title,
        "subtitle": data.get("subtitle") or "",
        "image": data.get("image") or "",
        "color": data.get("color") or t.tile_color(title),
        "favorite": "1" if data.get("favorite") else "",
        "initials": "".join(w[0] for w in title.split()[:2]).upper() or "?",
    }


class LibraryState(rx.State):
    # programs | routines | exercises; "favorites" when the Favorites row is open.
    filter: str = "routines"
    sort: str = "recents"
    grid: bool = True
    items: list[dict[str, str]] = []
    next_cursor: str = ""
    favorite_count: int = 0
    loading: bool = False
    error: str = ""

    # "Create new program"
    creating_program: bool = False
    program_name: str = ""

    # Program detail
    program_id: str = ""
    program_name_view: str = ""
    program_description: str = ""
    program_routines: list[dict[str, str]] = []

    @rx.var
    def sort_label(self) -> str:
        return {"recents": "Recents", "name": "Name", "most_used": "Most used"}[self.sort]

    @rx.var
    def has_items(self) -> bool:
        return len(self.items) > 0

    async def _token(self) -> str:
        return (await self.get_state(AuthState)).token

    async def _fetch(self, cursor: str = "") -> None:
        token = await self._token()
        if not token:
            return
        self.loading = True
        self.error = ""
        try:
            page = await wapi.library(token, filter=self.filter, sort=self.sort, cursor=cursor)
        except ApiError as exc:
            self.error = exc.detail
            self.loading = False
            return
        got = [_item(i) for i in page.get("items") or []]
        self.items = (self.items + got) if cursor else got
        self.next_cursor = page.get("next_cursor") or ""
        self.favorite_count = page.get("favorite_count") or 0
        self.loading = False

    async def load(self):
        self.program_id = ""
        self.creating_program = False
        await self._fetch()

    async def refresh(self):
        await self._fetch()
        if self.program_id:
            await self._load_program(self.program_id)

    async def set_filter(self, value: str):
        self.filter = value
        self.program_id = ""
        await self._fetch()

    async def set_sort(self, value: str):
        self.sort = value
        await self._fetch()

    async def cycle_sort(self):
        order = ["recents", "name", "most_used"]
        self.sort = order[(order.index(self.sort) + 1) % len(order)]
        await self._fetch()

    def toggle_grid(self) -> None:
        self.grid = not self.grid

    async def load_more(self):
        if self.next_cursor:
            await self._fetch(self.next_cursor)

    async def toggle_favorite(self, kind: str, target_id: str, on: bool):
        token = await self._token()
        try:
            await wapi.favorite(token, kind, target_id, on)
        except ApiError as exc:
            self.error = exc.detail
            return
        await self._fetch()

    # --- programs -----------------------------------------------------------

    def start_program(self) -> None:
        self.creating_program = True
        self.program_name = ""

    def cancel_program(self) -> None:
        self.creating_program = False

    def set_program_name(self, value: str) -> None:
        self.program_name = value

    async def create_program(self):
        name = self.program_name.strip()
        if not name:
            self.error = "Give the program a name."
            return
        token = await self._token()
        try:
            program = await wapi.create_program(token, {"name": name})
        except ApiError as exc:
            self.error = exc.detail
            return
        self.creating_program = False
        self.filter = "programs"
        await self._fetch()
        await self._load_program(str(program["id"]))

    async def _load_program(self, program_id: str) -> None:
        token = await self._token()
        try:
            program = await wapi.get_program(token, program_id)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.program_id = program_id
        self.program_name_view = program.get("name") or ""
        self.program_description = program.get("description") or ""
        self.program_routines = [
            {"id": str(r["id"]), "title": r["name"],
             "subtitle": f"{r['exercise_count']} exercise{'s' if r['exercise_count'] != 1 else ''}",
             "color": t.tile_color(r["name"]),
             "initials": "".join(w[0] for w in r["name"].split()[:2]).upper() or "?"}
            for r in program.get("routines") or []
        ]

    async def open_program(self, program_id: str):
        await self._load_program(program_id)

    def close_program(self) -> None:
        self.program_id = ""

    async def delete_program(self):
        token = await self._token()
        try:
            await wapi.delete_program(token, self.program_id)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.program_id = ""
        await self._fetch()

    # --- routines -----------------------------------------------------------

    def start_routine(self, routine_id: str):
        return WorkoutState.start_session(routine_id)
