"""Sign in / create account."""

import reflex as rx

from metalarm import theme
from metalarm.components.layout import brand, error_banner
from metalarm.state.auth import AuthState


def field(
    label: str, placeholder: str, on_change, input_type: str = "text", value=None
) -> rx.Component:
    return rx.vstack(
        rx.text(label, **theme.LABEL_STYLE),
        rx.input(
            placeholder=placeholder,
            on_change=on_change,
            type=input_type,
            value=value,
            width="100%",
            background="#0b1220",
            border=f"1px solid {theme.BORDER}",
            border_radius="9px",
            color=theme.TEXT,
            padding="0.7rem 0.85rem",
            font_size="0.9rem",
            _focus={"border_color": theme.ACCENT, "outline": "none"},
        ),
        spacing="1",
        width="100%",
        align="start",
    )


def primary_button(label: str, on_click) -> rx.Component:
    return rx.button(
        rx.cond(AuthState.loading, "WORKING...", label),
        on_click=on_click,
        disabled=AuthState.loading,
        background=theme.ACCENT,
        color="#04121c",
        border="none",
        border_radius="10px",
        font_weight="800",
        letter_spacing="0.14em",
        font_size="0.78rem",
        padding="0.75rem 1rem",
        width="100%",
        cursor="pointer",
    )


def auth_shell(*children: rx.Component) -> rx.Component:
    return rx.center(
        rx.vstack(
            brand(),
            rx.text(
                "Level up your life.",
                color=theme.MUTED,
                font_size="0.85rem",
                letter_spacing="0.04em",
            ),
            rx.vstack(
                *children,
                spacing="4",
                **theme.panel(box_shadow=theme.glow(theme.ACCENT, "70px")),
            ),
            spacing="5",
            align="center",
            width="100%",
            max_width="400px",
        ),
        min_height="100vh",
        width="100%",
        background=theme.BG,
        padding="1.5rem",
    )


def login_page() -> rx.Component:
    return auth_shell(
        rx.text("SIGN IN", **theme.LABEL_STYLE),
        error_banner(AuthState.error),
        field("EMAIL", "hunter@example.com", AuthState.set_form_email),
        field("PASSWORD", "••••••••", AuthState.set_form_password, "password"),
        primary_button("ENTER", AuthState.do_login),
        rx.hstack(
            rx.text("No account?", color=theme.FAINT, font_size="0.8rem"),
            rx.link(
                "Create one",
                href="/signup",
                color=theme.ACCENT,
                font_size="0.8rem",
                text_decoration="none",
            ),
            spacing="2",
            justify="center",
            width="100%",
        ),
    )


def signup_page() -> rx.Component:
    return auth_shell(
        rx.text("CREATE ACCOUNT", **theme.LABEL_STYLE),
        error_banner(AuthState.error),
        field("DISPLAY NAME", "Your hunter name", AuthState.set_form_display_name),
        field("EMAIL", "hunter@example.com", AuthState.set_form_email),
        field("PASSWORD", "At least 8 characters", AuthState.set_form_password, "password"),
        field(
            "TIMEZONE",
            "e.g. America/New_York",
            AuthState.set_form_timezone,
            value=AuthState.form_timezone,
        ),
        rx.text(
            "Your timezone decides when daily quests reset and when a streak "
            "counts as broken.",
            color=theme.FAINT,
            font_size="0.72rem",
            line_height="1.5",
        ),
        primary_button("BEGIN", AuthState.do_signup),
        rx.hstack(
            rx.text("Already registered?", color=theme.FAINT, font_size="0.8rem"),
            rx.link(
                "Sign in",
                href="/login",
                color=theme.ACCENT,
                font_size="0.8rem",
                text_decoration="none",
            ),
            spacing="2",
            justify="center",
            width="100%",
        ),
    )
