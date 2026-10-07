"""Settings: the account's training defaults (PATCH /auth/me) and the app's
own comforts - sound, haptics, reduced motion - which are per device, so they
live in the browser like the celebration sound always has."""

from __future__ import annotations

import reflex as rx

from metalarm import api
from metalarm import social_api as sapi
from metalarm import workout_api as wapi
from metalarm.api import ApiError
from metalarm.models import TrainingPathRow
from metalarm.state.auth import AuthState

VISIBILITY = {"Public": "public", "Followers": "followers", "Only me": "private"}
REST_STEP = 15

# Mirrors the setting onto <html data-ma-reduce>, which GLOBAL_CSS reads.
_REDUCE_JS = ("(function(on){var d=document.documentElement;"
              "if(on){d.setAttribute('data-ma-reduce','1')}else{d.removeAttribute('data-ma-reduce')}})")


class SettingsState(rx.State):
    haptics_pref: str = rx.LocalStorage("", name="ma_haptics")       # "off" or ""
    reduce_pref: str = rx.LocalStorage("", name="ma_reduce_motion")  # "1" or ""
    rest_seconds: int = 90
    visibility: str = "followers"
    paths: list[TrainingPathRow] = []
    show_paths: bool = False
    followers: int = 0
    following: int = 0
    error: str = ""

    @rx.var
    def haptics_on(self) -> bool:
        return self.haptics_pref != "off"

    @rx.var
    def reduce_on(self) -> bool:
        return self.reduce_pref == "1"

    @rx.var
    def rest_label(self) -> str:
        m, s = divmod(self.rest_seconds, 60)
        return f"{m}:{s:02d}"

    @rx.var
    def visibility_label(self) -> str:
        return next((k for k, v in VISIBILITY.items() if v == self.visibility), "Followers")

    async def load(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return
        try:
            me = await api.me(auth.token)
            self.rest_seconds = int(me.get("default_rest_seconds") or 90)
            self.visibility = me.get("default_visibility") or "followers"
            if not self.paths:
                self.paths = [TrainingPathRow.from_api(r) for r in await api.training_categories(auth.token)]
            social = await sapi.profile(auth.token, auth.user_id)
            self.followers, self.following = social["followers"], social["following"]
        except ApiError as exc:
            self.error = exc.detail

    async def _patch(self, payload: dict) -> bool:
        auth = await self.get_state(AuthState)
        try:
            await wapi.update_account(auth.token, payload)
        except ApiError as exc:
            self.error = exc.detail
            return False
        self.error = ""
        return True

    async def set_unit(self, label: str):
        if await self._patch({"weight_unit": label}):
            (await self.get_state(AuthState)).weight_unit = label

    async def bump_rest(self, delta: int):
        value = max(0, min(900, self.rest_seconds + delta))
        if await self._patch({"default_rest_seconds": value}):
            self.rest_seconds = value

    async def set_visibility(self, label: str):
        value = VISIBILITY.get(label, "followers")
        if await self._patch({"default_visibility": value}):
            self.visibility = value

    def open_paths(self) -> None:
        self.show_paths = True

    def close_paths(self) -> None:
        self.show_paths = False

    async def choose_path(self, category: str):
        auth = await self.get_state(AuthState)
        value = "" if category == auth.character_class else category
        if await self._patch({"character_class": value}):
            auth.character_class = value
            self.show_paths = False
            from metalarm.state.profile import ProfileState

            return ProfileState.load

    def toggle_haptics(self) -> None:
        self.haptics_pref = "" if self.haptics_pref == "off" else "off"

    def toggle_reduce(self):
        self.reduce_pref = "" if self.reduce_pref == "1" else "1"
        return rx.call_script(f"{_REDUCE_JS}({'true' if self.reduce_pref == '1' else 'false'})")


class WelcomeState(rx.State):
    """/welcome, after signup: one question a step - your name and units, then
    the training path. Saved together at the end."""

    step: int = 0
    name: str = ""
    unit: str = "kg"
    path: str = ""
    paths: list[TrainingPathRow] = []
    busy: bool = False
    error: str = ""

    async def load(self):
        auth = await self.get_state(AuthState)
        if not auth.token:
            return rx.redirect("/login")
        self.step, self.error = 0, ""
        self.name = auth.display_name
        self.unit = auth.weight_unit or "kg"
        self.path = auth.character_class
        try:
            self.paths = [TrainingPathRow.from_api(r) for r in await api.training_categories(auth.token)]
        except ApiError as exc:
            self.error = exc.detail

    def set_name(self, value: str) -> None:
        self.name = value

    def set_unit(self, label: str) -> None:
        self.unit = label

    def pick(self, category: str) -> None:
        self.path = category

    def back(self) -> None:
        self.step = 0

    async def next(self):
        if self.step == 0:
            if not self.name.strip():
                self.error = "Tell us what to call you."
                return
            self.error, self.step = "", 1
            return
        auth = await self.get_state(AuthState)
        self.busy = True
        yield
        try:
            await wapi.update_account(auth.token, {"display_name": self.name.strip(), "weight_unit": self.unit,
                                                   "character_class": self.path})
        except ApiError as exc:
            self.error = exc.detail
            self.busy = False
            return
        self.busy = False
        yield AuthState.refresh_me
        yield rx.redirect("/home")
