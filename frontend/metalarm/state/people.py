"""People (overhaul 7.2.6, 7.10): find and follow people, a person's
profile, and notifications. Who may see what is the server's rule."""

from __future__ import annotations

import dataclasses

import reflex as rx

from metalarm import social_api as sapi
from metalarm.api import ApiError
from metalarm.ranks import rank_title
from metalarm.state.auth import AuthState
from metalarm.workout_models import FeedCard, ago, initials_of


def person(u: dict) -> dict[str, str]:
    return {"id": str(u["id"]), "name": u["display_name"], "initials": initials_of(u["display_name"]),
            "rank": u["rank"], "sub": u.get("reason") or f"{rank_title(u['rank'])} · Level {u['level']}",
            "following": "1" if u["you_follow"] else "", "follows_you": "1" if u["follows_you"] else ""}


class PeopleState(rx.State):
    query: str = ""
    results: list[dict[str, str]] = []
    suggested: list[dict[str, str]] = []
    error: str = ""

    async def _token(self) -> str:
        return (await self.get_state(AuthState)).token

    async def load(self):
        token = await self._token()
        if not token:
            return
        try:
            self.suggested = [person(u) for u in (await sapi.suggested_users(token)).get("items") or []]
        except ApiError as exc:
            self.error = exc.detail

    async def set_query(self, value: str):
        self.query = value
        if not value.strip():
            self.results = []
            return
        try:
            page = await sapi.search_users(await self._token(), value.strip())
        except ApiError as exc:
            self.error = exc.detail
            return
        self.results = [person(u) for u in page.get("items") or []]

    async def toggle_follow(self, user_id: str, following: str):
        try:
            await sapi.follow(await self._token(), user_id, on=not following)
        except ApiError as exc:
            self.error = exc.detail
            return
        flip = lambda rows: [{**r, "following": "" if following else "1"} if r["id"] == user_id else r  # noqa: E731
                             for r in rows]
        self.results, self.suggested = flip(self.results), flip(self.suggested)


class ProfileViewState(rx.State):
    """/u/<id>: someone's profile and the workouts they let you see."""

    user_id: str = ""
    name: str = ""
    initials: str = ""
    rank: str = "E"
    rank_line: str = ""
    category: str = ""
    bio: str = ""
    followers: int = 0
    following: int = 0
    workouts: int = 0
    you_follow: bool = False
    follows_you: bool = False
    is_friend: bool = False
    is_me: bool = False
    sessions: list[FeedCard] = []
    cursor: str = ""
    loaded: bool = False
    error: str = ""

    async def _ctx(self) -> tuple[str, str]:
        auth = await self.get_state(AuthState)
        return auth.token, auth.weight_unit or "kg"

    async def load(self):
        token, unit = await self._ctx()
        if not token:
            return
        parts = [p for p in str(self.router.url.path).split("/") if p]
        self.user_id = parts[-1] if len(parts) >= 2 else ""
        self.loaded = False
        try:
            p = await sapi.profile(token, self.user_id)
            page = await sapi.user_sessions(token, self.user_id)
        except ApiError as exc:
            self.error = exc.detail
            return
        u = p["user"]
        self.name, self.initials, self.rank = u["display_name"], initials_of(u["display_name"]), u["rank"]
        self.rank_line = f"{rank_title(u['rank'])} · Level {u['level']}"
        self.category = (u.get("training_category") or "").capitalize()
        self.bio = p.get("bio") or ""
        self.followers, self.following, self.workouts = p["followers"], p["following"], p["workouts"]
        self.you_follow, self.follows_you = u["you_follow"], u["follows_you"]
        self.is_friend, self.is_me = p["is_friend"], p["is_me"]
        self.sessions = [FeedCard.from_api(i, unit) for i in page.get("items") or []]
        self.cursor = page.get("next_cursor") or ""
        self.loaded = True

    async def more(self):
        token, unit = await self._ctx()
        page = await sapi.user_sessions(token, self.user_id, self.cursor)
        self.sessions = self.sessions + [FeedCard.from_api(i, unit) for i in page.get("items") or []]
        self.cursor = page.get("next_cursor") or ""

    async def toggle_follow(self):
        token, _ = await self._ctx()
        try:
            await sapi.follow(token, self.user_id, on=not self.you_follow)
        except ApiError as exc:
            self.error = exc.detail
            return
        return ProfileViewState.load

    async def toggle_spot(self, session_id: str):
        token, _ = await self._ctx()
        card = next((c for c in self.sessions if c.session_id == session_id), None)
        if card is None:
            return
        try:
            r = await sapi.spot(token, session_id, not card.spotted_by_me)
        except ApiError as exc:
            self.error = exc.detail
            return
        self.sessions = [dataclasses.replace(c, spotted=r["spotted"], spotted_by_me=r["spotted_by_me"])
                         if c.session_id == session_id else c for c in self.sessions]


ICONS = {"follow": "user-plus", "reaction": "hand-metal", "duel_challenge": "swords",
         "friend_pr": "medal", "quest_complete": "scroll-text"}


def _line(n: dict) -> tuple[str, str]:
    """(sentence, link) for one notification."""
    who = (n.get("actor") or {}).get("display_name") or "Someone"
    detail = n.get("detail") or ""
    kind, target = n["type"], str(n.get("target_id") or "")
    actor = str((n.get("actor") or {}).get("id") or "")
    if kind == "follow":
        return f"{who} followed you", f"/u/{actor}"
    if kind == "reaction":
        return f"{who} spotted your workout{f' {detail}' if detail else ''}", f"/session/{target}"
    if kind == "duel_challenge":
        return f"{who} challenged you to a duel{f': {detail}' if detail else ''}", "/duels"
    if kind == "friend_pr":
        return f"{who} set a record - {detail}", f"/session/{target}"
    return f"Quest complete: {detail}", "/quests"


class NotificationsState(rx.State):
    items: list[dict[str, str]] = []
    cursor: str = ""
    error: str = ""

    async def _token(self) -> str:
        return (await self.get_state(AuthState)).token

    def _rows(self, page: dict) -> list[dict[str, str]]:
        out = []
        for n in page.get("items") or []:
            line, href = _line(n)
            actor = n.get("actor") or {}
            out.append({"id": str(n["id"]), "line": line, "href": href, "icon": ICONS.get(n["type"], "bell"),
                        "when": ago(n.get("created_at")), "unread": "" if n["read"] else "1",
                        "initials": initials_of(actor.get("display_name") or ""), "rank": actor.get("rank") or "",
                        "has_actor": "1" if actor else ""})
        return out

    async def load(self):
        token = await self._token()
        if not token:
            return
        try:
            page = await sapi.notifications(token)
            self.items = self._rows(page)
            self.cursor = page.get("next_cursor") or ""
            # Seen now: the dots stay for this visit, the bell clears.
            if page.get("unread"):
                await sapi.mark_read(token)
        except ApiError as exc:
            self.error = exc.detail

    async def more(self):
        page = await sapi.notifications(await self._token(), self.cursor)
        self.items = self.items + self._rows(page)
        self.cursor = page.get("next_cursor") or ""
