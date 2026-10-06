"""Session Detail (overhaul 7.10): one finished workout, every exercise and
set, as the server recorded it."""

from __future__ import annotations

import reflex as rx

from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.state.auth import AuthState
from metalarm.state.workout_home import duration_label
from metalarm.workout_models import fmt, local_dt, session_title, thousands, to_unit

TYPE_BADGE = {"warmup": "W", "drop": "D", "failure": "F"}


class SessionDetailState(rx.State):
    title: str = ""
    when: str = ""
    stats: list[dict[str, str]] = []
    rows: list[dict[str, str]] = []
    loaded: bool = False
    error: str = ""

    async def load(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        parts = [p for p in str(self.router.url.path).split("/") if p]
        unit, tz = auth.weight_unit or "kg", auth.timezone or "UTC"
        self.loaded = False
        try:
            s = await wapi.get_session(auth.token, parts[-1])
        except ApiError as exc:
            self.error = exc.detail
            return
        moment = local_dt(s.get("started_at"), tz)
        self.title = session_title(s.get("name"), s.get("started_at"), tz)
        self.when = moment.strftime("%A %d %B %Y, %H:%M") if moment else ""
        records = sum(1 for e in s.get("exercises") or [] for x in e.get("sets") or [] if x.get("is_pr"))
        self.stats = [
            {"label": "Duration", "value": duration_label(s.get("duration_seconds"))},
            {"label": "Volume", "value": f"{thousands(to_unit(s.get('total_volume_kg'), unit))} {unit}"},
            {"label": "Sets", "value": str(s.get("working_sets") or 0)},
            {"label": "Records", "value": str(records)},
            {"label": "Points", "value": f"+{s.get('points_credited') or s.get('points_total') or 0}"},
        ]
        rows = []
        for e in s.get("exercises") or []:
            ex = e.get("exercise") or {}
            rows.append({"kind": "head", "title": ex.get("name") or "", "id": str(ex.get("id") or ""),
                         "image": ex.get("thumbnail_url") or "", "badge": "", "pr": "",
                         "sub": e.get("notes") or ""})
            for x in e.get("sets") or []:
                weight = f"{fmt(to_unit(x['weight_kg'], unit))} {unit}" if x.get("weight_kg") else "Bodyweight"
                body = f"{weight} × {x['reps']}" if x.get("reps") else (
                    duration_label(x.get("duration_seconds")) if x.get("duration_seconds") else weight)
                rows.append({"kind": "set", "title": body, "id": "", "image": "", "sub": "",
                             "badge": TYPE_BADGE.get(x.get("set_type") or "", str(x.get("set_number") or "")),
                             "pr": "1" if x.get("is_pr") else ""})
        self.rows = rows
        self.loaded = True
