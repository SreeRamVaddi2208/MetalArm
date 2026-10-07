"""The Train tab when no workout is live: what to do next, your routines,
programs (yours and the curated plans), and the way into the exercise
library. Plus one program's detail. Every list is the server's."""

from __future__ import annotations

import uuid

import reflex as rx

from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.state.auth import AuthState
from metalarm.state.workout_home import last_done_label
from metalarm.workout_models import ago, plural

CATEGORY = {"powerlifter": "Powerlifter", "bodybuilder": "Bodybuilder", "athlete": "Athlete"}


class TrainState(rx.State):
    up_next: dict[str, str] = {}
    routines: list[dict[str, str]] = []
    programs: list[dict[str, str]] = []
    curated: list[dict[str, str]] = []
    loaded: bool = False
    error: str = ""

    async def load(self):
        token = (await self.get_state(AuthState)).token
        if not token:
            return
        self.error = ""
        try:
            suggested = await wapi.suggested(token)
            routines = (await wapi.library(token, filter="routines", sort="recents", limit=50)).get("items") or []
            programs = (await wapi.library(token, filter="programs", sort="recents", limit=50)).get("items") or []
            curated = await wapi.curated_programs(token)
        except ApiError as exc:
            self.error = exc.detail
            return
        top = suggested[0] if suggested else None
        self.up_next = ({"id": str(top["routine_id"]), "name": top["name"],
                         "sub": f"{plural(top['exercise_count'], 'exercise')} · {last_done_label(top.get('days_since'))}"}
                        if top else {})
        self.routines = [{"id": str(r["id"]), "name": r["title"],
                          "sub": r["subtitle"] + (f" · {ago(r['last_used_at'])}" if r.get("last_used_at") else "")}
                         for r in routines]
        self.programs = [{"id": str(p["id"]), "name": p["title"], "sub": p["subtitle"]} for p in programs]
        self.curated = [{"slug": p["slug"], "name": p["name"],
                         "sub": f"{CATEGORY.get(p['category'], p['category'])} · {p['level'].capitalize()} · "
                                f"{p['sessions_per_week']}× a week"}
                        for p in curated if not p.get("saved_program_id")]
        self.loaded = True


class ProgramState(rx.State):
    """/train/program/<id or curated slug>."""

    key: str = ""
    curated: bool = False
    name: str = ""
    meta: str = ""
    description: str = ""
    # Your program: its routines. A curated one: each routine and what it holds.
    routines: list[dict[str, str]] = []
    saved_id: str = ""
    loaded: bool = False
    error: str = ""

    async def load(self):
        token = (await self.get_state(AuthState)).token
        if not token:
            return
        parts = [p for p in str(self.router.url.path).split("/") if p]
        self.key = parts[-1] if len(parts) >= 3 else ""
        self.loaded, self.error = False, ""
        try:
            uuid.UUID(self.key)
            mine = True
        except ValueError:
            mine = False
        try:
            if mine:
                p = await wapi.get_program(token, self.key)
                self.curated = False
                self.name, self.description = p["name"], p.get("description") or ""
                bits = [b for b in (p.get("level") or "", f"{p['weeks']} weeks" if p.get("weeks") else "",
                                    f"{p['sessions_per_week']}× a week" if p.get("sessions_per_week") else "") if b]
                self.meta = " · ".join(b.capitalize() if i == 0 else b for i, b in enumerate(bits))
                self.routines = [{"id": str(r["id"]), "name": r["name"],
                                  "sub": plural(r['exercise_count'], "exercise")
                                         + (f" · {ago(r['last_performed_at'])}" if r.get("last_performed_at") else "")}
                                 for r in p.get("routines") or []]
            else:
                p = next((x for x in await wapi.curated_programs(token) if x["slug"] == self.key), None)
                if p is None:
                    self.error = "That program isn't available."
                    return
                self.curated = True
                self.name, self.description = p["name"], p["description"]
                self.meta = (f"{CATEGORY.get(p['category'], p['category'])} · {p['level'].capitalize()} · "
                             f"{p['weeks']} weeks · {p['sessions_per_week']}× a week")
                self.saved_id = str(p.get("saved_program_id") or "")
                self.routines = [{"id": "", "name": r["name"],
                                  "sub": " · ".join(e["name"] for e in r["exercises"])} for r in p["routines"]]
        except ApiError as exc:
            self.error = exc.detail
            return
        self.loaded = True

    async def save(self):
        token = (await self.get_state(AuthState)).token
        try:
            program = await wapi.save_curated(token, self.key)
        except ApiError as exc:
            self.error = exc.detail
            return
        return rx.redirect(f"/train/program/{program['id']}")

    async def delete(self):
        token = (await self.get_state(AuthState)).token
        try:
            await wapi.delete_program(token, self.key)
        except ApiError as exc:
            self.error = exc.detail
            return
        return rx.redirect("/train")
