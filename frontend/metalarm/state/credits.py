"""The credits page: who made each piece of library artwork, under which
licence. A condition of using CC-BY-SA material, not a courtesy."""

from __future__ import annotations

import reflex as rx

from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.state.auth import AuthState


class CreditsState(rx.State):
    rows: list[dict] = []
    error: str = ""

    async def load(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        try:
            exercises = await wapi.search_exercises(auth.token, limit=500)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.rows = [
            {"name": e["name"], "author": e.get("media_author") or "",
             "license": e.get("media_license") or "", "source": e.get("media_source_url") or "",
             "image": e.get("thumbnail_url") or ""}
            for e in exercises if e.get("media_license")
        ]
