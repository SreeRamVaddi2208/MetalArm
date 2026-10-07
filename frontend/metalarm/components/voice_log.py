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
from metalarm import theme as t
from metalarm.ui.primitives import button, chip, chips, field, icon_button, text
from metalarm.state.workout import WorkoutState
from metalarm.workout_models import Alternative

_CSS = f"""
.ma-mic {{
  -webkit-user-select: none; user-select: none; -webkit-touch-callout: none;
  touch-action: none;
}}
.ma-mic[data-ma-listening] {{ background: {theme.ACCENT_SOFT} !important; color: {theme.ACCENT} !important; }}
html[data-ma-voice="no"] .ma-mic {{ display: none !important; }}
.ma-voice-text {{ display: none; }}
.ma-voice-text.ma-open, html[data-ma-voice="no"] .ma-voice-text {{ display: flex; }}
.ma-heard::after {{ content: attr(data-ma-heard); }}
.ma-heard:not([data-ma-heard]) {{ display: none; }}
@media (prefers-reduced-motion: no-preference) {{
  .ma-mic[data-ma-listening] {{ animation: ma-mic-pulse 1.4s ease-in-out infinite; }}
}}
@keyframes ma-mic-pulse {{
  0%, 100% {{ opacity: 1; }}
  50% {{ opacity: 0.6; }}
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


def _alternative(alt: Alternative) -> rx.Component:
    return chip(alt.name, on_click=WorkoutState.pick_alternative(alt.exercise_id, alt.name))


def proposal_card() -> rx.Component:
    """What was heard, editable, and one tap to log it."""
    p = WorkoutState.proposal
    return rx.cond(
        WorkoutState.has_proposal,
        rx.vstack(
            rx.hstack(text(rx.cond(p.by_llm, "Heard · via AI", "Heard"), t.CAPTION, t.TEXT_2), rx.spacer(),
                      icon_button("x", "Discard", on_click=WorkoutState.discard_proposal), width="100%",
                      align="center"),
            text(p.exercise_name, t.TITLE),
            rx.cond(p.alternatives.length() > 0,
                    rx.vstack(text(rx.cond(p.unsure, "Not sure - did you mean:", "Or:"), t.CAPTION, t.TEXT_2),
                              chips(rx.foreach(p.alternatives, _alternative)), spacing="1", width="100%")),
            rx.hstack(
                field(p.weight, WorkoutState.set_proposal_weight, p.unit, mode="decimal"),
                field(p.reps, WorkoutState.set_proposal_reps, "reps", mode="numeric"),
                field(p.rpe, WorkoutState.set_proposal_rpe, "RPE", mode="decimal"),
                spacing="2", width="100%",
            ),
            rx.hstack(
                text("Sets", t.LABEL, t.TEXT_2), rx.spacer(),
                icon_button("minus", "Fewer sets", on_click=WorkoutState.bump_proposal_sets(-1)),
                text(p.set_count, t.TITLE, min_width="24px", text_align="center"),
                icon_button("plus", "More sets", on_click=WorkoutState.bump_proposal_sets(1)),
                width="100%", align="center",
            ),
            chips(chip("Warm-up", selected=p.warmup, on_click=WorkoutState.toggle_proposal_warmup)),
            rx.cond(p.unparsed_label != "", text(p.unparsed_label, t.CAPTION, t.TEXT_2)),
            button(rx.cond(p.set_count > 1, f"Log {p.set_count} sets", "Log it"), WorkoutState.confirm_proposal,
                   variant="secondary", full=True, disabled=WorkoutState.busy),
            spacing="3", width="100%", background=t.SURFACE, border_radius=t.RADIUS, padding=t.CARD_PADDING,
        ),
    )


def voice_bar() -> rx.Component:
    """Hold the mic and say a set, or type it; Undo after a voice-logged set."""
    return rx.vstack(
        voice_assets(),
        proposal_card(),
        rx.cond(WorkoutState.voice_error != "", text(WorkoutState.voice_error, t.BODY, t.TEXT_2)),
        rx.text(class_name="ma-heard", custom_attrs={"data-ma-heard-slot": ""}, color=t.TEXT_2, margin="0",
                **t.BODY),
        rx.hstack(
            field(WorkoutState.voice_text, WorkoutState.set_voice_text, 'Type a set - "bench 80 for 8"',
                  on_key_down=lambda key: rx.cond(key == "Enter", WorkoutState.submit_typed, rx.noop()), flex="1"),
            button("Parse", WorkoutState.submit_typed, variant="secondary", disabled=WorkoutState.voice_busy),
            width="100%", spacing="2",
            class_name=rx.cond(WorkoutState.show_typed, "ma-voice-text ma-open", "ma-voice-text"),
        ),
        rx.hstack(
            rx.cond(WorkoutState.can_undo_voice, button("Undo", WorkoutState.undo_voice, variant="ghost",
                                                        icon="undo-2")),
            button(rx.cond(WorkoutState.voice_busy, "Working…", "Hold to talk"),
                   rx.call_script("window.maVoice.result()", callback=WorkoutState.voice_done),
                   variant="secondary", icon="mic", flex="1", class_name="ma-mic",
                   custom_attrs={"data-ma-mic": ""}),
            icon_button("keyboard", "Type a set instead", on_click=WorkoutState.toggle_typed),
            width="100%", spacing="2", align="center",
        ),
        spacing="3",
        width="100%",
    )
