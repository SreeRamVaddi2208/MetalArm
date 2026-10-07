"""Signed out: sign in, create an account, then /welcome - one question a
step (your name and units, then your training path)."""

import reflex as rx

from metalarm import theme as t
from metalarm.components.layout import brand, error_banner
from metalarm.state.auth import AuthState
from metalarm.state.settings import WelcomeState
from metalarm.ui.path_card import path_card
from metalarm.ui.primitives import button, field, segmented, text


def _page(*children: rx.Component, action: rx.Component) -> rx.Component:
    """A signed-out screen: the column, and the one action pinned under it."""
    return rx.box(
        rx.vstack(*children, spacing="5", width="100%", max_width=t.MAX_WIDTH, margin="0 auto",
                  padding=f"{t.space(48)} {t.GUTTER} {t.BOTTOM_CLEARANCE}"),
        rx.box(rx.box(action, max_width=t.MAX_WIDTH, margin="0 auto", width="100%"),
               position="fixed", left="0", right="0", bottom="0", background=t.BG,
               padding=f"{t.space(12)} {t.GUTTER} calc({t.space(24)} + env(safe-area-inset-bottom))"),
        min_height="100vh", width="100%", background=t.BG,
    )


def _labelled(label: str, control: rx.Component) -> rx.Component:
    return rx.vstack(text(label, t.LABEL, t.TEXT_2), control, spacing="2", width="100%")


def _switch(prompt: str, link: str, href: str) -> rx.Component:
    return rx.hstack(text(prompt, t.BODY, t.TEXT_2),
                     rx.link(text(link, t.BODY, t.TEXT, font_weight="600"), href=href, underline="always"),
                     spacing="2", justify="center", width="100%")


def login_page() -> rx.Component:
    return _page(
        brand(),
        text("Sign in", t.TITLE_LG),
        error_banner(AuthState.error),
        _labelled("Email", field(AuthState.form_email, AuthState.set_form_email, "you@example.com", type_="email",
                                 autocomplete="email")),
        _labelled("Password", field(AuthState.form_password, AuthState.set_form_password, "Your password",
                                    type_="password", autocomplete="current-password")),
        _switch("No account?", "Create one", "/signup"),
        action=button(rx.cond(AuthState.loading, "Signing in…", "Sign in"), AuthState.do_login,
                      disabled=AuthState.loading, full=True),
    )


def signup_page() -> rx.Component:
    return _page(
        brand(),
        text("Create account", t.TITLE_LG),
        error_banner(AuthState.error),
        _labelled("Name", field(AuthState.form_display_name, AuthState.set_form_display_name, "What friends call you",
                                autocomplete="name")),
        _labelled("Email", field(AuthState.form_email, AuthState.set_form_email, "you@example.com", type_="email",
                                 autocomplete="email")),
        _labelled("Password", field(AuthState.form_password, AuthState.set_form_password, "At least 8 characters",
                                    type_="password", autocomplete="new-password")),
        _labelled("Timezone", field(AuthState.form_timezone, AuthState.set_form_timezone, "e.g. Europe/London")),
        text("Your timezone decides when daily quests reset and when a week counts toward your streak.",
             t.CAPTION, t.TEXT_2),
        _switch("Already have an account?", "Sign in", "/login"),
        action=button(rx.cond(AuthState.loading, "Creating…", "Create account"), AuthState.do_signup,
                      disabled=AuthState.loading, full=True),
    )


def _dots() -> rx.Component:
    def dot(i: int) -> rx.Component:
        return rx.box(width=rx.cond(WelcomeState.step == i, "24px", "8px"), height="8px",
                      border_radius=t.RADIUS_PILL,
                      background=rx.cond(WelcomeState.step == i, t.ACCENT, t.BORDER),
                      transition=f"width {t.FAST} {t.EASE}")
    return rx.hstack(dot(0), dot(1), spacing="2", aria_label="Step", class_name="ma-steps")


def welcome_page() -> rx.Component:
    w = WelcomeState
    about_you = rx.vstack(
        text("About you", t.TITLE_LG),
        _labelled("Name", field(w.name, w.set_name, "What friends call you")),
        _labelled("Units", segmented(["kg", "lb"], w.unit, w.set_unit)),
        spacing="5", width="100%",
    )
    your_path = rx.vstack(
        text("How do you train?", t.TITLE_LG),
        text("It shapes what MetalArm suggests - never your score. Change it any time.", t.BODY, t.TEXT_2),
        rx.vstack(rx.foreach(w.paths, lambda p: path_card(p, selected=w.path == p.category,
                                                          on_click=w.pick(p.category))),
                  spacing="3", width="100%", custom_attrs={"role": "radiogroup"}),
        spacing="4", width="100%",
    )
    return _page(
        rx.hstack(_dots(), rx.spacer(),
                  rx.cond(w.step == 1, button("Back", w.back, variant="ghost")), width="100%", align="center"),
        error_banner(w.error),
        rx.cond(w.step == 0, about_you, your_path),
        action=button(rx.cond(w.step == 0, "Continue", rx.cond(w.path == "", "Skip for now", "Confirm")), w.next,
                      disabled=w.busy, full=True),
    )
