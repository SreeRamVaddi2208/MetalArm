"""Authentication state: token, identity, and progression.

The token lives in browser LocalStorage so a refresh does not log the user out.
Note the API calls themselves run server-side in the Reflex process; only the
token is client-persisted.
"""

from __future__ import annotations

import reflex as rx

from levelforge import api
from levelforge.models import Progress


class AuthState(rx.State):
    # Persisted per browser. Survives reload; never leaves this origin.
    token: str = rx.LocalStorage("", name="lf_token")

    display_name: str = ""
    email: str = ""
    timezone: str = "UTC"
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
            data = await api.login(self.form_email, self.form_password)
            self.token = data["access_token"]
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
            data = await api.login(self.form_email, self.form_password)
            self.token = data["access_token"]
            self.form_password = ""
            await self._load_me()
            ok = True
        except api.ApiError as exc:
            self.error = exc.detail
        finally:
            self.loading = False

        if ok:
            yield rx.redirect("/dashboard")

    def do_logout(self):
        self.token = ""
        self.display_name = ""
        self.email = ""
        self.progress = Progress()
        self.loaded = False
        return rx.redirect("/login")

    async def _load_me(self) -> None:
        data = await api.me(self.token)
        self.display_name = data.get("display_name") or ""
        self.email = data.get("email") or ""
        self.timezone = data.get("timezone") or "UTC"
        self.progress = Progress.from_api(data.get("progress") or {})
        self.loaded = True

    async def refresh_me(self):
        """Re-fetch identity and progression. Safe to call on every page load."""
        if not self.token:
            return
        try:
            await self._load_me()
        except api.ApiError as exc:
            # An expired or revoked token must not leave a stale session
            # rendering as if it were live.
            if exc.status == 401:
                return AuthState.do_logout
            self.error = exc.detail

    async def require_auth(self):
        """Page guard. Redirects out when there is no usable session."""
        if not self.token:
            return rx.redirect("/login")
        return AuthState.refresh_me
