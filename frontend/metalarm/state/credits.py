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

    diagrams: int = 0

    async def load(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        rows, diagrams, cursor = [], 0, ""
        try:
            while True:
                page = await wapi.browse(auth.token, cursor=cursor, limit=100)
                for e in page.get("items") or []:
                    if e.get("is_custom") or not e.get("media_license"):
                        continue
                    if e.get("media_author") == "MetalArm":
                        diagrams += 1
                        continue
                    rows.append({"name": e["name"], "author": e.get("media_author") or "",
                                 "license": e.get("media_license") or "",
                                 "source": e.get("media_source_url") or "",
                                 "image": e.get("thumbnail_url") or ""})
                cursor = page.get("next_cursor") or ""
                if not cursor:
                    break
        except ApiError as exc:
            self.error = exc.detail
            return
        self.rows, self.diagrams = rows, diagrams
