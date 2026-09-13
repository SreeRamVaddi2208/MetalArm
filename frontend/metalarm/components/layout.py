"""Page shell: brand, navigation, and the signed-in identity."""

import reflex as rx

from metalarm import theme
from metalarm.state.auth import AuthState


def nav_link(label: str, href: str) -> rx.Component:
    return rx.link(
        label,
        href=href,
        color=theme.MUTED,
        font_size="0.78rem",
        letter_spacing="0.16em",
        font_weight="700",
        text_decoration="none",
        _hover={"color": theme.ACCENT},
    )


def brand() -> rx.Component:
    return rx.hstack(
        rx.box(
            width="10px",
            height="10px",
            background=theme.ACCENT,
            border_radius="2px",
            box_shadow=theme.glow(theme.ACCENT, "18px"),
        ),
        rx.text(
            "METALARM",
            color=theme.TEXT,
            font_weight="800",
            letter_spacing="0.22em",
            font_size="0.9rem",
        ),
        spacing="3",
        align="center",
    )


def navbar() -> rx.Component:
    return rx.hstack(
        rx.link(brand(), href="/dashboard", text_decoration="none"),
        rx.spacer(),
        rx.hstack(
            nav_link("QUESTS", "/dashboard"),
            nav_link("WORKOUT", "/workout"),
            nav_link("PROGRESS", "/progress"),
            nav_link("PARTIES", "/parties"),
            nav_link("REWARDS", "/rewards"),
            nav_link("PROFILE", "/profile"),
            spacing="5",
            display=["none", "none", "flex", "flex"],
        ),
        rx.spacer(),
        rx.hstack(
            rx.text(
                AuthState.display_name,
                color=theme.MUTED,
                font_size="0.8rem",
                display=["none", "flex", "flex", "flex"],
            ),
            rx.button(
                "SIGN OUT",
                on_click=AuthState.do_logout,
                background="transparent",
                color=theme.FAINT,
                border=f"1px solid {theme.BORDER}",
                border_radius="8px",
                font_size="0.7rem",
                letter_spacing="0.12em",
                padding="0.4rem 0.7rem",
                cursor="pointer",
                _hover={"color": theme.DANGER, "border_color": theme.DANGER},
            ),
            spacing="3",
            align="center",
        ),
        width="100%",
        padding="1rem 1.25rem",
        border_bottom=f"1px solid {theme.BORDER}",
        background=theme.BG,
        position="sticky",
        top="0",
        z_index="50",
        align="center",
    )


def mobile_nav() -> rx.Component:
    """Shown only where the top-bar links are hidden, so navigation never
    disappears on a narrow screen."""
    # Six links on one line that scrolls sideways at phone width, rather than
    # wrapping into two ragged rows. The right edge fades out so the row reads
    # as scrollable - otherwise the links past the edge look like they do not
    # exist. The end padding lets the last link scroll clear of the fade.
    return rx.hstack(
        nav_link("QUESTS", "/dashboard"),
        nav_link("WORKOUT", "/workout"),
        nav_link("PROGRESS", "/progress"),
        nav_link("PARTIES", "/parties"),
        nav_link("REWARDS", "/rewards"),
        nav_link("PROFILE", "/profile"),
        spacing="5",
        flex_wrap="nowrap",
        overflow_x="auto",
        white_space="nowrap",
        justify="start",
        padding_left="1.25rem",
        padding_right="3.5rem",
        style={
            "scrollbar_width": "none",
            "mask_image": "linear-gradient(to right, #000 80%, transparent)",
        },
        width="100%",
        padding="0.75rem",
        border_bottom=f"1px solid {theme.BORDER}",
        display=["flex", "flex", "none", "none"],
    )


def session_keeper() -> rx.Component:
    """Invisible 5-minute tick that renews the access token while a page stays
    open (a workout can outlast a 60-minute token). Rendered only when signed
    in; the seconds in the format make every tick a change, so on_change fires."""
    return rx.cond(
        AuthState.is_authenticated,
        rx.moment(
            interval=5 * 60 * 1000,
            format="HH:mm:ss",
            on_change=AuthState.keep_fresh,
            display="none",
        ),
    )


def shell(*children: rx.Component) -> rx.Component:
    """Standard signed-in page frame."""
    return rx.box(
        session_keeper(),
        navbar(),
        mobile_nav(),
        rx.box(
            rx.vstack(*children, spacing="5", width="100%"),
            width="100%",
            max_width="1100px",
            margin="0 auto",
            padding_left="1rem",
            padding_right="1rem",
            padding_block="1.75rem",
        ),
        min_height="100vh",
        background=theme.BG,
        color=theme.TEXT,
        width="100%",
    )


def error_banner(message: rx.Var) -> rx.Component:
    """Inline message area. Also carries expected 409s such as 'already
    completed for this period', which are normal states rather than faults."""
    return rx.cond(
        message != "",
        rx.box(
            rx.text(message, color=theme.DANGER, font_size="0.85rem"),
            width="100%",
            padding="0.75rem 1rem",
            background="#2a121a",
            border=f"1px solid {theme.DANGER}55",
            border_radius="10px",
        ),
    )


def notice_banner(message: rx.Var) -> rx.Component:
    return rx.cond(
        message != "",
        rx.box(
            rx.text(message, color=theme.SUCCESS, font_size="0.85rem"),
            width="100%",
            padding="0.75rem 1rem",
            background="#0f2620",
            border=f"1px solid {theme.SUCCESS}55",
            border_radius="10px",
        ),
    )


def section_heading(label: str, *trailing: rx.Component) -> rx.Component:
    return rx.hstack(
        rx.text(label, **theme.LABEL_STYLE),
        rx.spacer(),
        *trailing,
        width="100%",
        align="center",
    )
