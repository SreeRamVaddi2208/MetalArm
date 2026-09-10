"""The level-up / rank-up reveal.

Section 7 in one component, deliberately isolated from state so motion can be
iterated on without touching data flow. The trigger is the backend's explicit
`leveled_up` / `ranked_up` flags, so the moment is never inferred by diffing.

Principles applied here:
  - Animates ONLY transform and opacity, so the compositor handles it and no
    frame forces a reflow.
  - Pinned to the viewport for the reveal, rather than hijacking the scroll.
  - `prefers-reduced-motion` collapses everything to a plain fade - mandatory,
    not optional.
  - This is one of the two signature beats, so it is the one place that earns
    a heavier effect; a quest checkbox gets none.
"""

import reflex as rx

from metalarm import theme
from metalarm.state.quests import QuestState

_KEYFRAMES = f"""
@keyframes lf-burst {{
  0%   {{ opacity: 0; transform: scale(0.82); }}
  55%  {{ opacity: 1; transform: scale(1.04); }}
  100% {{ opacity: 1; transform: scale(1); }}
}}
@keyframes lf-rise {{
  0%   {{ opacity: 0; transform: translateY(14px); }}
  100% {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes lf-ring {{
  0%   {{ opacity: 0.85; transform: scale(0.6); }}
  100% {{ opacity: 0;    transform: scale(2.4); }}
}}
@keyframes lf-veil {{
  0%   {{ opacity: 0; }}
  100% {{ opacity: 1; }}
}}

.lf-veil  {{ animation: lf-veil 220ms ease-out both; }}
.lf-card  {{ animation: lf-burst 520ms cubic-bezier(0.22, 1, 0.36, 1) both; }}
.lf-line  {{ animation: lf-rise 460ms cubic-bezier(0.22, 1, 0.36, 1) 120ms both; }}
.lf-ring  {{
  /* The one looping effect in the app, and only while the overlay is open -
     Section 7: save the expensive motion for the moment that matters. */
  animation: lf-ring 1100ms ease-out 80ms infinite;
  border: 2px solid {theme.ACCENT};
}}

/* Motion sensitivity: no scaling, no travel, no looping pulse - just a fade. */
@media (prefers-reduced-motion: reduce) {{
  .lf-veil, .lf-card, .lf-line {{
    animation: lf-veil 160ms ease-out both;
  }}
  .lf-ring {{ display: none; }}
}}
"""


def _beat_color():
    """Rank-up is the rarer, larger beat, so it reads gold rather than accent
    blue - the same colour the S-rank badge uses."""
    return rx.cond(QuestState.level_up_is_rank, theme.RANK_COLORS["S"], theme.ACCENT)


def keyframes() -> rx.Component:
    """Injected once per page that can raise the overlay."""
    return rx.el.style(_KEYFRAMES)


def level_up_overlay() -> rx.Component:
    return rx.cond(
        QuestState.show_level_up,
        rx.box(
            rx.center(
                rx.vstack(
                    rx.box(
                        rx.box(
                            class_name="lf-ring",
                            position="absolute",
                            width="128px",
                            height="128px",
                            border_radius="50%",
                            pointer_events="none",
                        ),
                        # The new level number, or the new rank letter. Showing
                        # the value reached is the payoff; "you levelled up"
                        # without saying to what is a weaker beat.
                        rx.heading(
                            QuestState.level_up_badge,
                            size="9",
                            color=_beat_color(),
                            font_weight="900",
                            line_height="1",
                        ),
                        position="relative",
                        display="flex",
                        align_items="center",
                        justify_content="center",
                        width="128px",
                        height="128px",
                    ),
                    rx.heading(
                        QuestState.level_up_message,
                        size="7",
                        color=_beat_color(),
                        letter_spacing="0.2em",
                        text_align="center",
                        class_name="lf-line",
                    ),
                    rx.text(
                        rx.cond(
                            QuestState.level_up_is_rank,
                            "A new rank. Keep the streak alive to hold it.",
                            "Keep going.",
                        ),
                        color=theme.MUTED,
                        font_size="0.85rem",
                        text_align="center",
                        class_name="lf-line",
                    ),
                    rx.button(
                        "CONTINUE",
                        on_click=QuestState.dismiss_level_up,
                        background=theme.ACCENT,
                        color="#04121c",
                        border="none",
                        border_radius="10px",
                        font_weight="800",
                        letter_spacing="0.14em",
                        font_size="0.75rem",
                        padding="0.65rem 1.4rem",
                        cursor="pointer",
                        class_name="lf-line",
                    ),
                    spacing="4",
                    align="center",
                    class_name="lf-card",
                    padding="2.5rem 2rem",
                    background=theme.PANEL,
                    border=f"1px solid {_beat_color()}55",
                    border_radius="18px",
                    box_shadow=theme.glow(theme.ACCENT, "90px"),
                    max_width="90vw",
                ),
                width="100%",
                height="100%",
            ),
            class_name="lf-veil",
            position="fixed",
            top="0",
            left="0",
            width="100vw",
            height="100vh",
            background="rgba(4, 7, 12, 0.82)",
            backdrop_filter="blur(3px)",
            z_index="100",
            # Dismissible by clicking the veil, so the overlay can never trap
            # the user if the button is off-screen.
            on_click=QuestState.dismiss_level_up,
        ),
    )
