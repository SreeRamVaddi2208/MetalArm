"""Authentication state: tokens, identity, and progression.

The tokens live in browser LocalStorage so a refresh does not log the user out.
Note the API calls themselves run server-side in the Reflex process; only the
tokens are client-persisted.

Access tokens are short-lived. The refresh token keeps the session going: it is
swapped for a new pair on page load when the access token is about to expire,
and by a timer in the page shell (components/layout.py) while a page stays open,
so a long workout never hits an expired token mid-set.
"""

from __future__ import annotations

import base64
import json
import time

import reflex as rx

from metalarm import api
from metalarm.models import Progress

# Refresh when the access token has less than this left. The shell's timer
# fires every 5 minutes, so this keeps a margin of at least one tick.
REFRESH_MARGIN_SECONDS = 10 * 60


def seconds_until_expiry(token: str) -> float:
    """Seconds until the access token's `exp`, read from its payload.

    Not verified here - the server verifies every request; this only decides
    when to refresh. An unreadable token reads as already expiring.
    """
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload))["exp"]) - time.time()
    except (IndexError, ValueError, KeyError, TypeError):
        return 0.0


class AuthState(rx.State):
    # Persisted per browser. Survives reload; never leaves this origin.
    token: str = rx.LocalStorage("", name="lf_token")
    refresh_token: str = rx.LocalStorage("", name="lf_refresh")

    display_name: str = ""
    email: str = ""
    timezone: str = "UTC"
    # Workout display unit, stored on the account so it follows the user
    # across devices. Weights are always stored in kg server-side.
    weight_unit: str = "kg"
    progress: Progress = Progress()

    # Form fields
    form_email: str = ""
    form_password: str = ""
    form_display_name: str = ""
    form_timezone: str = "UTC"

    error: str = ""
    loading: bool = False
    # Distinguishes "not loaded yet" from "loaded and empty", so the dashboard
    # does not flash an empty Stat Panel before the first fetch resolves.
    loaded: bool = False

    RANK_ORDER = ["E", "D", "C", "B", "A", "S"]

    @rx.var
    def is_authenticated(self) -> bool:
        return bool(self.token)

    @rx.var
    def xp_percent(self) -> int:
        """XP bar fill, 0-100.

        Computed here rather than on the model because Reflex evaluates
        rx.var server-side; a Python property on an rx.Base is invisible to
        the compiled component. Guards the MAX_LEVEL case, where the API
        reports 0/0 - that reads as a full bar, not a division by zero.
        """
        if not self.loaded:
            # Pre-load defaults are all zero, and 0/0 would otherwise render a
            # FULL bar on a brand-new session.
            return 0
        if self.progress.xp_for_next_level <= 0:
            return 100
        return min(
            100,
            int(self.progress.xp_into_level * 100 / self.progress.xp_for_next_level),
        )

    @rx.var
    def xp_scale(self) -> float:
        """XP bar fill as a 0..1 scale factor for `transform: scaleX()`.

        Computed here rather than dividing a Var in the template, so the value
        the component receives is a plain float and does not depend on how
        Reflex compiles arithmetic on a state var.
        """
        return round(self.xp_percent / 100, 4)

    @rx.var
    def rank_is_gated(self) -> bool:
        """True when the level has earned a higher rank than the streak allows.

        The UI must say "reach a 14-day streak to claim A" rather than silently
        showing the lower badge.
        """
        order = self.RANK_ORDER
        if self.progress.rank not in order or self.progress.rank_by_level not in order:
            return False
        return order.index(self.progress.rank_by_level) > order.index(self.progress.rank)

    @rx.var
    def at_max_rank(self) -> bool:
        """True only once progression has actually loaded.

        `next_rank` is "" both at the top of the ladder AND in the unloaded
        default, so without the `loaded` guard a new user was told they had
        reached the maximum rank.
        """
        return self.loaded and not self.progress.next_rank

    @rx.var
    def streak_label(self) -> str:
        """'BROKEN' is only truthful for someone who once had a streak."""
        if not self.loaded:
            return "--"
        if self.progress.streak_is_active:
            return f"{self.progress.current_streak} DAYS"
        if self.progress.longest_streak == 0:
            return "NONE YET"
        return "BROKEN"

    @rx.var
    def rank_gate_message(self) -> str:
        if not self.rank_is_gated:
            return ""
        return (
            f"Level {self.progress.current_level} has earned rank "
            f"{self.progress.rank_by_level} - hold a "
            f"{self.progress.next_rank_streak}-day streak to claim it."
        )

    def set_error(self, message: str) -> None:
        self.error = message

    # --- Form binding -----------------------------------------------------

    def set_form_email(self, value: str) -> None:
        self.form_email = value
        self.error = ""

    def set_form_password(self, value: str) -> None:
        self.form_password = value
        self.error = ""

    def set_form_display_name(self, value: str) -> None:
        self.form_display_name = value
        self.error = ""

    def set_form_timezone(self, value: str) -> None:
        self.form_timezone = value

    # --- Tokens -----------------------------------------------------------

    def _store_tokens(self, data: dict) -> None:
        self.token = data["access_token"]
        # Older backends did not return one; the session then simply ends when
        # the access token does, as before.
        self.refresh_token = data.get("refresh_token") or ""

    async def _refresh_tokens(self) -> bool:
        """Swap the refresh token for a new pair. False if there is none or
        the server rejected it (which ends the session). A network failure
        keeps the current tokens: a blip must not sign the user out."""
        if not self.refresh_token:
            return False
        try:
            self._store_tokens(await api.refresh(self.refresh_token))
            return True
        except api.ApiError as exc:
            if exc.status == 401:
                self.token = ""
                self.refresh_token = ""
            return False

    async def keep_fresh(self, _tick: str = ""):
        """Called by the page shell's timer while a signed-in page is open."""
        if not self.token or seconds_until_expiry(self.token) > REFRESH_MARGIN_SECONDS:
            return
        await self._refresh_tokens()
        if not self.token:
            return AuthState.do_logout

    # --- Actions ----------------------------------------------------------

    async def do_login(self):
        # NOTE: this handler yields (to flash the loading state before the
        # request), which makes it an async GENERATOR - so navigation must be
        # `yield rx.redirect(...)`. `return rx.redirect(...)` is a SyntaxError
        # in a generator, not a runtime failure, so it breaks the build.
        if not self.form_email or not self.form_password:
            self.error = "Email and password are required."
            return
        self.loading = True
        self.error = ""
        yield

        ok = False
        try:
            self._store_tokens(await api.login(self.form_email, self.form_password))
            self.form_password = ""
            await self._load_me()
            ok = True
        except api.ApiError as exc:
            self.error = exc.detail
        finally:
            self.loading = False

        if ok:
            yield rx.redirect("/dashboard")

    async def do_signup(self):
        # Async generator - see the note in do_login about yield vs return.
        if not (self.form_email and self.form_password and self.form_display_name):
            self.error = "Email, password and display name are required."
            return
        self.loading = True
        self.error = ""
        yield

        ok = False
        try:
            await api.signup(
                self.form_email,
                self.form_password,
                self.form_display_name,
                self.form_timezone or "UTC",
            )
            # Sign straight in, so a new account never lands on a login form.
            self._store_tokens(await api.login(self.form_email, self.form_password))
            self.form_password = ""
            await self._load_me()
            ok = True
        except api.ApiError as exc:
            self.error = exc.detail
        finally:
            self.loading = False

        if ok:
            yield rx.redirect("/dashboard")

    async def do_logout(self):
        # End this browser's session on the server too, with the refresh token
        # (still valid when the access token has expired). If that fails -
        # offline, or the session already ended - signing out here still happens.
        if self.refresh_token or self.token:
            try:
                await api.logout(refresh_token=self.refresh_token, token=self.token)
            except api.ApiError:
                pass
        self.token = ""
        self.refresh_token = ""
        self.display_name = ""
        self.email = ""
        self.weight_unit = "kg"
        self.progress = Progress()
        self.loaded = False
        return rx.redirect("/login")

    async def _load_me(self) -> None:
        data = await api.me(self.token)
        self.display_name = data.get("display_name") or ""
        self.email = data.get("email") or ""
        self.timezone = data.get("timezone") or "UTC"
        self.weight_unit = data.get("weight_unit") or "kg"
        self.progress = Progress.from_api(data.get("progress") or {})
        self.loaded = True

    async def refresh_me(self):
        """Re-fetch identity and progression. Safe to call on every page load.

        Runs first on every signed-in page, so it also renews an access token
        that is about to expire before the page's own requests use it.
        """
        if not self.token:
            return
        if seconds_until_expiry(self.token) <= REFRESH_MARGIN_SECONDS:
            await self._refresh_tokens()
            if not self.token:
                return AuthState.do_logout
        try:
            await self._load_me()
        except api.ApiError as exc:
            # An expired or revoked token must not leave a stale session
            # rendering as if it were live - but try the refresh token once
            # before giving up on it.
            if exc.status != 401:
                self.error = exc.detail
                return
            if await self._refresh_tokens():
                try:
                    await self._load_me()
                    return
                except api.ApiError:
                    pass
            return AuthState.do_logout

    async def require_auth(self):
        """Page guard. Redirects out when there is no usable session."""
        if not self.token:
            return rx.redirect("/login")
        return AuthState.refresh_me
