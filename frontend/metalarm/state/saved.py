"""The Library tab: what the user has kept - their routines, their programs,
and what they have bookmarked (GET /library)."""

from __future__ import annotations

import reflex as rx

from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.state.auth import AuthState

SAVED_TABS = ["Routines", "Programs", "Saved"]
_FILTERS = {"Routines": "routines", "Programs": "programs", "Saved": "favorites"}
_EMPTY = {"Routines": "Save a workout as a routine, or build one in Workout.",
          "Programs": "Follow or save a program in Explore and it appears here.",
          "Saved": "Bookmark an exercise in Explore and it appears here."}
_HREFS = {"routine": "/train/routine/{}", "program": "/train/program/{}", "exercise": "/exercise/{}"}


class SavedState(rx.State):
    tab: str = "Routines"
    items: list[dict[str, str]] = []
    loaded: bool = False
    error: str = ""

    @rx.var
    def empty_note(self) -> str:
        return _EMPTY.get(self.tab, "")

    async def load(self):
        token = (await self.get_state(AuthState)).token
        if not token:
            return
        self.loaded, self.error = False, ""
        try:
            page = await wapi.library(token, filter=_FILTERS[self.tab], limit=100)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.items = [{"title": i["title"], "sub": i.get("subtitle") or "", "image": i.get("image") or "",
                       "href": _HREFS[i["type"]].format(i["id"])} for i in page.get("items") or []]
        self.loaded = True

    async def set_tab(self, tab: str):
        self.tab = tab
        await self.load()
