"""Voice and typed set logging on the live workout screen.

Hold the mic, say "bench 80 for 8", let go: the words go to POST /log/parse,
which PROPOSES sets. A card shows the proposal, editable in place, and one
"Log it" tap sends each set through the ordinary log-set endpoint - so PRs,
points and quests fire exactly as they do for a tapped-in set. Nothing is ever
logged without that tap.

Speech-to-text is the browser's Web Speech API, so audio never leaves the
device for MetalArm's servers. Where it is missing (Firefox, some in-app
browsers), the mic is hidden and the typed box is shown instead - same parser.

How the script and Reflex share the mic, under the same rule as rest_timer.py
(the script never writes text or classes into React-owned nodes):

- Press-and-hold has to be pointer events, which Reflex does not expose. The
  script listens for pointerdown / pointerup on `[data-ma-mic]` by delegation
  on the document, starting and stopping recognition.
- Releasing a press also fires `click`, which IS a Reflex event: its handler
  asks `window.maVoice.result()` for a promise of what was heard, and
  rx.call_script awaits it into WorkoutState.voice_done.
- The live transcript is an attribute (`data-ma-heard`) on an element React
  rendered empty, shown with CSS `content: attr(...)`.
- Support is flagged on <html> (`data-ma-voice="yes|no"`), which CSS reads to
  hide the mic or force the typed box open.
"""

import reflex as rx

from metalarm import theme
from metalarm.state.workout import WorkoutState
from metalarm.workout_models import Alternative

_CSS = f"""
.ma-mic {{
  -webkit-user-select: none; user-select: none; -webkit-touch-callout: none;
  touch-action: none;
}}
.ma-mic[data-ma-listening] {{ background: {theme.ACCENT} !important; color: {theme.ON_ACCENT} !important; }}
html[data-ma-voice="no"] .ma-mic {{ display: none !important; }}
.ma-voice-text {{ display: none; }}
.ma-voice-text.ma-open, html[data-ma-voice="no"] .ma-voice-text {{ display: flex; }}
.ma-heard::after {{ content: attr(data-ma-heard); }}
.ma-heard:not([data-ma-heard]) {{ display: none; }}
@media (prefers-reduced-motion: no-preference) {{
  .ma-mic[data-ma-listening] {{ animation: ma-mic-pulse 1.4s ease-in-out infinite; }}
}}
@keyframes ma-mic-pulse {{
  0%, 100% {{ box-shadow: 0 0 0 0 {theme.ACCENT}55; }}
  50% {{ box-shadow: 0 0 0 10px {theme.ACCENT}00; }}
}}
"""

_SCRIPT = """
(function () {
  if (window.maVoice) return;
  var Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  document.documentElement.setAttribute('data-ma-voice', Rec ? 'yes' : 'no');

  var rec = null, heard = '', error = '', done = null, finish = null;

  function attr(node, name, value) {
    if (!node) return;
    if (value === null) node.removeAttribute(name); else node.setAttribute(name, value);
  }
  function live(text) { attr(document.querySelector('[data-ma-heard-slot]'), 'data-ma-heard', text || null); }

  function start(button) {
    if (!Rec || rec) return;
    heard = ''; error = '';
    done = new Promise(function (resolve) { finish = resolve; });
    rec = new Rec();
    rec.lang = navigator.language || 'en-US';
    rec.interimResults = true;
    rec.continuous = true;
    rec.onresult = function (event) {
      var text = '';
      for (var i = 0; i < event.results.length; i++) text += event.results[i][0].transcript;
      heard = text.trim();
      live(heard);
    };
    rec.onerror = function (event) {
      error = (event.error === 'not-allowed' || event.error === 'service-not-allowed') ? 'denied'
            : (event.error === 'no-speech' ? 'no-speech' : event.error || 'failed');
    };
    rec.onend = function () {
      attr(button, 'data-ma-listening', null);
      live(null);
      rec = null;
      if (finish) finish(error ? { error: error } : { text: heard });
      finish = null;
    };
    attr(button, 'data-ma-listening', '');
    live('Listening...');
    try { rec.start(); } catch (e) { error = 'failed'; rec.onend(); }
  }
  function stop() { if (rec) { try { rec.stop(); } catch (e) {} } }

  document.addEventListener('pointerdown', function (e) {
    var mic = e.target.closest && e.target.closest('[data-ma-mic]');
    if (mic) { e.preventDefault(); start(mic); }
  });
  ['pointerup', 'pointercancel'].forEach(function (type) {
    document.addEventListener(type, function () { stop(); });
  });
  document.addEventListener('contextmenu', function (e) {
    if (e.target.closest && e.target.closest('[data-ma-mic]')) e.preventDefault();
  });

  window.maVoice = {
    // What the last press heard. Resolves once recognition has ended.
    result: function () {
      if (!Rec) return Promise.resolve({ error: 'unsupported' });
      // Handed over once: a click with no press before it (keyboard
      // activation) must not replay the previous transcript.
      var pending = done;
      done = null;
      return pending || Promise.resolve({ error: 'no-speech' });
    }
  };
})();
"""


def voice_assets() -> rx.Component:
    return rx.fragment(rx.el.style(_CSS), rx.script(_SCRIPT))


def _field(value, on_change, width: str, **kwargs) -> rx.Component:
    return rx.input(
        value=value,
        on_change=on_change,
        width=width,
        height="40px",
        background=theme.FIELD,
        border=f"1px solid {theme.BORDER}",
        border_radius="8px",
        color=theme.TEXT,
        text_align="center",
        font_weight="800",
        **{"input_mode": "decimal", **kwargs},
    )


def _alternative(alt: Alternative) -> rx.Component:
    return rx.button(
        alt.name,
        on_click=WorkoutState.pick_alternative(alt.exercise_id, alt.name),
        background="transparent",
        color=theme.MUTED,
        border=f"1px solid {theme.BORDER_HI}",
        border_radius="999px",
        font_size="0.72rem",
        padding="0.3rem 0.7rem",
        cursor="pointer",
    )


def proposal_card() -> rx.Component:
    p = WorkoutState.proposal
    return rx.cond(
        WorkoutState.has_proposal,
        rx.vstack(
            rx.hstack(
                rx.text("HEARD", **theme.LABEL_STYLE),
                rx.cond(p.by_llm, rx.text("· via AI", color=theme.FAINT, font_size="0.66rem")),
                rx.spacer(),
                rx.button(
                    rx.icon("x", size=14),
                    on_click=WorkoutState.discard_proposal,
                    background="transparent",
                    color=theme.FAINT,
                    border="none",
                    cursor="pointer",
                    aria_label="Discard",
                ),
                width="100%",
                align="center",
            ),
            rx.text(p.exercise_name, color=theme.TEXT, font_weight="800", font_size="1rem"),
            rx.cond(
                p.alternatives.length() > 0,
                rx.vstack(
                    rx.text(
                        rx.cond(p.unsure, "Not sure - did you mean:", "Or:"),
                        color=theme.FAINT,
                        font_size="0.72rem",
                    ),
                    rx.hstack(rx.foreach(p.alternatives, _alternative), spacing="2", flex_wrap="wrap"),
                    spacing="1",
                    align="start",
                ),
            ),
            rx.hstack(
                rx.vstack(rx.text(p.unit.upper(), **theme.LABEL_STYLE),
                          _field(p.weight, WorkoutState.set_proposal_weight, "84px"), spacing="1"),
                rx.vstack(rx.text("REPS", **theme.LABEL_STYLE),
                          _field(p.reps, WorkoutState.set_proposal_reps, "64px", input_mode="numeric"),
                          spacing="1"),
                rx.vstack(rx.text("RPE", **theme.LABEL_STYLE),
                          _field(p.rpe, WorkoutState.set_proposal_rpe, "56px", placeholder="-"), spacing="1"),
                rx.vstack(
                    rx.text("SETS", **theme.LABEL_STYLE),
                    rx.hstack(
                        rx.button("-", on_click=WorkoutState.bump_proposal_sets(-1), size="1",
                                  variant="soft", color_scheme="gray"),
                        rx.text(p.set_count, color=theme.TEXT, font_weight="800", min_width="1.2rem",
                                text_align="center"),
                        rx.button("+", on_click=WorkoutState.bump_proposal_sets(1), size="1",
                                  variant="soft", color_scheme="gray"),
                        align="center",
                        spacing="1",
                        height="40px",
                    ),
                    spacing="1",
                ),
                spacing="3",
                flex_wrap="wrap",
                align="end",
            ),
            rx.hstack(
                rx.checkbox("Warm-up", checked=p.warmup, on_change=lambda _: WorkoutState.toggle_proposal_warmup(),
                            color_scheme="gray", size="1"),
                rx.spacer(),
                rx.cond(p.unparsed_label != "",
                        rx.text(p.unparsed_label, color=theme.FAINT, font_size="0.7rem")),
                width="100%",
                align="center",
            ),
            rx.button(
                rx.cond(p.set_count > 1, f"LOG {p.set_count} SETS", "LOG IT"),
                on_click=WorkoutState.confirm_proposal,
                loading=WorkoutState.busy,
                width="100%",
                height="52px",
                background=theme.ACCENT,
                color=theme.ON_ACCENT,
                border="none",
                border_radius="10px",
                font_weight="900",
                letter_spacing="0.14em",
                cursor="pointer",
            ),
            spacing="3",
            **theme.panel(padding="1rem 1.1rem", border=f"1px solid {theme.BORDER_HI}"),
        ),
    )


def voice_bar() -> rx.Component:
    """The mic in the thumb zone, the typed fallback, the live transcript,
    and Undo after a voice-logged set."""
    return rx.vstack(
        voice_assets(),
        proposal_card(),
        rx.cond(
            WorkoutState.voice_error != "",
            rx.text(WorkoutState.voice_error, color=theme.WARNING, font_size="0.8rem"),
        ),
        rx.text(class_name="ma-heard", custom_attrs={"data-ma-heard-slot": ""},
                color=theme.MUTED, font_size="0.85rem", font_style="italic"),
        rx.hstack(
            rx.input(
                placeholder='Type a set - "bench 80 for 8"',
                value=WorkoutState.voice_text,
                on_change=WorkoutState.set_voice_text,
                on_key_down=lambda key: rx.cond(key == "Enter", WorkoutState.submit_typed, rx.noop()),
                flex="1",
                height="44px",
                background=theme.FIELD,
                border=f"1px solid {theme.BORDER}",
                border_radius="10px",
                color=theme.TEXT,
            ),
            rx.button(
                "PARSE",
                on_click=WorkoutState.submit_typed,
                loading=WorkoutState.voice_busy,
                height="44px",
                background="transparent",
                color=theme.ACCENT,
                border=f"1px solid {theme.ACCENT}66",
                border_radius="10px",
                font_weight="800",
                font_size="0.72rem",
                letter_spacing="0.12em",
                cursor="pointer",
            ),
            width="100%",
            spacing="2",
            class_name=rx.cond(WorkoutState.show_typed, "ma-voice-text ma-open", "ma-voice-text"),
        ),
        rx.hstack(
            rx.cond(
                WorkoutState.can_undo_voice,
                rx.button(
                    rx.icon("undo-2", size=14),
                    "Undo",
                    on_click=WorkoutState.undo_voice,
                    background="transparent",
                    color=theme.MUTED,
                    border=f"1px solid {theme.BORDER}",
                    border_radius="10px",
                    height="56px",
                    padding="0 1rem",
                    cursor="pointer",
                ),
            ),
            rx.button(
                rx.icon("mic", size=20),
                rx.cond(WorkoutState.voice_busy, "Working...", "Hold to talk"),
                on_click=rx.call_script("window.maVoice.result()", callback=WorkoutState.voice_done),
                class_name="ma-mic",
                custom_attrs={"data-ma-mic": ""},
                flex="1",
                height="56px",
                background="transparent",
                color=theme.ACCENT,
                border=f"1px solid {theme.ACCENT}88",
                border_radius="12px",
                font_weight="800",
                letter_spacing="0.12em",
                font_size="0.8rem",
                cursor="pointer",
            ),
            rx.button(
                rx.icon("keyboard", size=18),
                on_click=WorkoutState.toggle_typed,
                class_name="ma-mic",
                background="transparent",
                color=theme.MUTED,
                border=f"1px solid {theme.BORDER}",
                border_radius="12px",
                height="56px",
                width="56px",
                cursor="pointer",
                aria_label="Type a set instead",
            ),
            width="100%",
            spacing="2",
        ),
        spacing="2",
        width="100%",
    )
