"""The credits page: who made each piece of library artwork and whose words
the how-to steps are. A condition of using licensed material, not a courtesy."""

from __future__ import annotations

import reflex as rx

from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.state.auth import AuthState


class CreditsState(rx.State):
    rows: list[dict] = []
    text_rows: list[dict] = []
    error: str = ""

    diagrams: int = 0

    async def load(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        rows, text_rows, diagrams, cursor = [], [], 0, ""
        try:
            while True:
                page = await wapi.browse(auth.token, cursor=cursor, limit=100)
                for e in page.get("items") or []:
                    if e.get("is_custom"):
                        continue
                    if e.get("text_source_url"):
                        text_rows.append({"name": e["name"], "license": e.get("text_license") or "",
                                          "source": e["text_source_url"]})
                    if not e.get("media_license"):
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
        self.rows, self.text_rows, self.diagrams = rows, text_rows, diagrams
