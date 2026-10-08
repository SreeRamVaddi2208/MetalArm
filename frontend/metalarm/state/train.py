"""The Train tab when no workout is live: what to do next, your routines and
your own programs, and the way into the Library. Plus one program of your own.
Every list is the server's. Ready-made programs and workouts are the Library's
(state/library.py)."""

from __future__ import annotations

import uuid

import reflex as rx

from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.state.auth import AuthState
from metalarm.state.workout_home import last_done_label
from metalarm.workout_models import ago, plural



class TrainState(rx.State):
    up_next: dict[str, str] = {}
    routines: list[dict[str, str]] = []
    programs: list[dict[str, str]] = []
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
        self.loaded = True


class ProgramState(rx.State):
    """/train/program/<id>: a program of your own."""

    key: str = ""
    name: str = ""
    meta: str = ""
    description: str = ""
    routines: list[dict[str, str]] = []
    loaded: bool = False
    error: str = ""

    async def load(self):
        token = (await self.get_state(AuthState)).token
        if not token:
            return
        parts = [p for p in str(self.router.url.path).split("/") if p]
        self.key = parts[-1] if len(parts) >= 3 else ""
        try:
            uuid.UUID(self.key)
        except ValueError:
            # A curated plan's old address: those live in the Library now.
            return rx.redirect("/library")
        self.loaded, self.error = False, ""
        try:
            p = await wapi.get_program(token, self.key)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.name, self.description = p["name"], p.get("description") or ""
        bits = [b for b in (p.get("level") or "", f"{p['weeks']} weeks" if p.get("weeks") else "",
                            f"{p['sessions_per_week']}× a week" if p.get("sessions_per_week") else "") if b]
        self.meta = " · ".join(b.capitalize() if i == 0 else b for i, b in enumerate(bits))
        self.routines = [{"id": str(r["id"]), "name": r["name"],
                          "sub": plural(r["exercise_count"], "exercise")
                                 + (f" · {ago(r['last_performed_at'])}" if r.get("last_performed_at") else "")}
                         for r in p.get("routines") or []]
        self.loaded = True

    async def delete(self):
        token = (await self.get_state(AuthState)).token
        try:
            await wapi.delete_program(token, self.key)
        except ApiError as exc:
            self.error = exc.detail
            return
        return rx.redirect("/train")
