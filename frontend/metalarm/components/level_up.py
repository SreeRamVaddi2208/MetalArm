"""The level-up / rank-up reveal.

Section 7 in one component, deliberately isolated from state so motion can be
iterated on without touching data flow. The trigger is the backend's explicit
`leveled_up` / `ranked_up` flags, so the moment is never inferred by diffing.

Principles applied here:
  - The motion is transform and opacity, so the compositor handles it. The one
    exception is the shine sweep across the heading, which is paint-only on a
    single line of text.
  - Pinned to the viewport for the reveal, rather than hijacking the scroll.
  - `prefers-reduced-motion` collapses everything to a plain fade - mandatory,
    not optional.
  - This is one of the two signature beats, so it is the one place that earns
    a heavier effect: silver rings, metal sparks, a shine. A quest checkbox
    gets none.
"""

import reflex as rx

from metalarm import theme
from metalarm.state.quests import QuestState

# Angle and travel of each metal spark, spread around the badge.
_SPARKS = [(i * 15 + (7 if i % 2 else -5), 96 + (i * 37) % 48) for i in range(24)]

_KEYFRAMES = f"""
@keyframes lf-burst {{
  0%   {{ opacity: 0; transform: scale(0.4); }}
  55%  {{ opacity: 1; transform: scale(1.12); }}
  100% {{ opacity: 1; transform: scale(1); }}
}}
@keyframes lf-rise {{
  0%   {{ opacity: 0; transform: translateY(14px); }}
  100% {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes lf-ring {{
  0%   {{ opacity: 0.9; transform: scale(0.6); }}
  100% {{ opacity: 0;   transform: scale(1.6); }}
}}
@keyframes lf-veil {{
  0%   {{ opacity: 0; }}
  100% {{ opacity: 1; }}
}}
@keyframes lf-spark {{
  0%   {{ opacity: 1; transform: rotate(var(--a)) translateY(0); }}
  100% {{ opacity: 0; transform: rotate(var(--a)) translateY(calc(-1 * var(--d))); }}
}}
/* The shine is a narrow soft-edged window sliding right over a white copy of
   the text, while the copy slides left by the same distance so its letters stay
   exactly over the originals. Both are transforms: animating the gradient's
   background-position instead repainted the text on every frame (Section 7).
   Window = 40% of the text, copy = 250% of the window, hence -100%/250% and
   40%/-100%: the two always cancel. */
@keyframes lf-shine-window {{
  0%   {{ transform: translateX(-100%); }}
  100% {{ transform: translateX(250%); }}
}}
@keyframes lf-shine-copy {{
  0%   {{ transform: translateX(40%); }}
  100% {{ transform: translateX(-100%); }}
}}

.lf-veil  {{ animation: lf-veil 220ms ease-out both; }}
.lf-card  {{ animation: lf-rise 420ms cubic-bezier(0.22, 1, 0.36, 1) both; }}
.lf-badge {{ animation: lf-burst 620ms cubic-bezier(0.22, 1, 0.36, 1) 80ms both; }}
.lf-line  {{ animation: lf-rise 460ms cubic-bezier(0.22, 1, 0.36, 1) 220ms both; }}
.lf-ring  {{
  /* A few beats around the badge, then still - bounded and clipped by the
     card, so it frames the number instead of crossing the text. */
  animation: lf-ring 1100ms ease-out 120ms 3 both;
  border: 2px solid {theme.ACCENT};
}}
.lf-ring.lf-late {{ animation-delay: 420ms; border-color: {theme.ACCENT_DIM}; }}
.lf-spark {{
  position: absolute;
  top: 50%;
  left: 50%;
  width: 3px;
  height: 14px;
  margin: -7px 0 0 -1.5px;
  border-radius: 2px;
  background: linear-gradient({theme.ACCENT}, {theme.ACCENT_DIM});
  animation: lf-spark 900ms cubic-bezier(0.2, 0.8, 0.2, 1) 140ms both;
  pointer-events: none;
}}
/* Brushed-metal numbers and a light sweep across the heading. */
.lf-metal {{
  background: linear-gradient(180deg, #ffffff 0%, #c0c0c8 55%, #6a6a72 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent !important;
}}
.lf-shine {{
  position: relative;
  display: inline-block;
  white-space: nowrap;
  color: {theme.ACCENT_DIM};
}}
.lf-shine-window {{
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 40%;
  overflow: hidden;
  pointer-events: none;
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 50%, transparent);
  mask-image: linear-gradient(90deg, transparent, #000 50%, transparent);
  animation: lf-shine-window 1500ms ease-out 380ms 2 both;
}}
.lf-shine-copy {{
  display: block;
  width: 250%;
  white-space: nowrap;
  color: #ffffff;
  animation: lf-shine-copy 1500ms ease-out 380ms 2 both;
}}

/* Motion sensitivity: no scaling, no travel, no sparks or shine - just a fade. */
@media (prefers-reduced-motion: reduce) {{
  .lf-veil, .lf-card, .lf-badge, .lf-line {{
    animation: lf-veil 160ms ease-out both;
  }}
  .lf-ring, .lf-spark {{ display: none; }}
  .lf-shine-window {{ display: none; }}
}}
"""


def keyframes() -> rx.Component:
    """Injected once per page that can raise the overlay."""
    return rx.el.style(_KEYFRAMES)


def _sparks() -> list[rx.Component]:
    return [
        rx.box(class_name="lf-spark", style={"--a": f"{angle}deg", "--d": f"{distance}px"})
        for angle, distance in _SPARKS
    ]


def _ring(extra_class: str = "") -> rx.Component:
    return rx.box(
        class_name=f"lf-ring {extra_class}".strip(),
        position="absolute",
        width="128px",
        height="128px",
        border_radius="50%",
        pointer_events="none",
    )


def level_up_overlay() -> rx.Component:
    return rx.cond(
        QuestState.show_level_up,
        rx.box(
            rx.center(
                rx.vstack(
                    rx.box(
                        _ring(),
                        # Rank-up is the rarer, larger beat: a second, later ring.
                        rx.cond(QuestState.level_up_is_rank, _ring("lf-late")),
                        *_sparks(),
                        # The new level number, or the new rank letter. Showing
                        # the value reached is the payoff; "you levelled up"
                        # without saying to what is a weaker beat.
                        rx.heading(
                            QuestState.level_up_badge,
                            size="9",
                            font_weight="900",
                            line_height="1",
                            class_name="lf-metal lf-badge",
                        ),
                        position="relative",
                        display="flex",
                        align_items="center",
                        justify_content="center",
                        width="128px",
                        height="128px",
                    ),
                    rx.heading(
                        rx.el.span(
                            QuestState.level_up_message,
                            # The highlight: a white copy, seen through a sliding window.
                            rx.el.span(
                                rx.el.span(QuestState.level_up_message, class_name="lf-shine-copy"),
                                class_name="lf-shine-window",
                                aria_hidden="true",
                            ),
                            class_name="lf-shine",
                        ),
                        size="7",
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
                        color=theme.ON_ACCENT,
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
                    border=f"1px solid {theme.ACCENT}40",
                    border_radius="18px",
                    box_shadow=rx.cond(
                        QuestState.level_up_is_rank,
                        theme.glow(theme.ACCENT, "150px"),
                        theme.glow(theme.ACCENT, "90px"),
                    ),
                    max_width="90vw",
                    overflow="hidden",
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
            background=theme.VEIL,
            backdrop_filter="blur(3px)",
            z_index="100",
            # Dismissible by clicking the veil, so the overlay can never trap
            # the user if the button is off-screen.
            on_click=QuestState.dismiss_level_up,
        ),
    )
