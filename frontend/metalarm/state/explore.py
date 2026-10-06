"""Explore (overhaul phase 0 cut): the muscle and equipment grids, from the
taxonomy endpoint. Filtered exercise lists, search and programs land in
phase 3."""

from __future__ import annotations

import reflex as rx

from metalarm import api
from metalarm.state.auth import AuthState
from metalarm.ui.body_map import paths_for


class ExploreState(rx.State):
    muscles: list[dict] = []
    equipment: list[dict] = []
    tab: str = "Exercises"
    loaded: bool = False
    error: str = ""

    def set_tab(self, tab: str) -> None:
        self.tab = tab

    async def load(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        try:
            data = await api.taxonomy(auth.token)
        except api.ApiError as exc:
            self.error = exc.detail
            return
        svg = {m["code"]: m["svg_path_ids"] for m in data.get("muscle_groups", [])}
        # Each tile lights its own muscle, full strength.
        self.muscles = [
            {"code": m["code"], "label": m["display_name"],
             "paths": paths_for({m["code"]: 1.0}, svg), "side": m["body_side"]}
            for m in data.get("muscle_groups", []) if m["browsable"]
        ]
        self.equipment = [
            {"code": e["code"], "label": e["display_name"]}
            for e in data.get("equipment", []) if e["browsable"]
        ]
        self.loaded = True
