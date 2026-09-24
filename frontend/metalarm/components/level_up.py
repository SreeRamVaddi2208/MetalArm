"""The level-up / rank-up reveal.

Section 7 in one component, deliberately isolated from state so motion can be
iterated on without touching data flow. The trigger is the backend's explicit
`leveled_up` / `ranked_up` flags, so the moment is never inferred by diffing.

ONE sequence, six intensities: flash -> shockwave -> camera shake -> zoom ->
badge (with its ornament) -> level counter -> settle. Everything that differs
between a Novice promotion and a World Class one arrives from
`rank_tiers.TIERS` as custom properties and a particle list, so a sixth tier is
a row in that table rather than a second animation. QuestState resolves the
tier; nothing here knows what a rank is worth.

Principles applied here:
  - The motion is transform and opacity, so the compositor handles it. The one
    exception is the shine sweep across the heading, which is paint-only on a
    single line of text.
  - No JavaScript animation library. The frontend has no package.json by
    design (see frontend/requirements.txt), and CSS keyframes driven by custom
    properties give the same escalation without one. The ornaments are plain
    boxes behind `_ornament()`, which is the seam where illustrated art would
    go if it is ever drawn.
  - Pinned to the viewport for the reveal, rather than hijacking the scroll.
  - `prefers-reduced-motion` collapses everything to a plain fade - mandatory,
    not optional.
  - This is one of the two signature beats, so it is the one place that earns
    a heavier effect: rings, metal sparks, a shine. A quest checkbox gets none.

The script only ever writes attributes React does not manage (`data-ma-count`,
`data-ma-ready`), for the reason spelled out in rest_timer.py: writing into
React-owned nodes breaks hydration.
"""

import reflex as rx

from metalarm import theme
from metalarm.state.quests import QuestState

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
/* A rank-up throws plates, not shards: they travel further and spin. */
@keyframes lf-plate {{
  0%   {{ opacity: 1; transform: rotate(var(--a)) translateY(0) rotate(0deg); }}
  100% {{ opacity: 0; transform: rotate(var(--a)) translateY(calc(-1.35 * var(--d))) rotate(220deg); }}
}}
/* The white-out that opens the sequence. */
@keyframes lf-flash {{
  0%   {{ opacity: 0; }}
  18%  {{ opacity: 0.9; }}
  100% {{ opacity: 0; }}
}}
/* The camera, not the card: the whole stage jolts and settles. Travel is
   --lf-shake, which is 0 on the quiet tiers, so the same rule plays a no-op
   there instead of needing a second code path. */
@keyframes lf-shake {{
  0%, 100% {{ transform: translate3d(0, 0, 0); }}
  15%  {{ transform: translate3d(calc(var(--lf-shake, 0px) * -1), var(--lf-shake, 0px), 0); }}
  30%  {{ transform: translate3d(var(--lf-shake, 0px), calc(var(--lf-shake, 0px) * -0.6), 0); }}
  45%  {{ transform: translate3d(calc(var(--lf-shake, 0px) * -0.7), calc(var(--lf-shake, 0px) * 0.4), 0); }}
  60%  {{ transform: translate3d(calc(var(--lf-shake, 0px) * 0.5), var(--lf-shake, 0px), 0); }}
  80%  {{ transform: translate3d(calc(var(--lf-shake, 0px) * -0.25), 0, 0); }}
}}
@keyframes lf-zoom {{
  0%   {{ transform: scale(var(--lf-zoom, 1)); }}
  100% {{ transform: scale(1); }}
}}
/* The shockwave: one wide ring that outruns the others. Top two tiers only. */
@keyframes lf-shock {{
  0%   {{ opacity: 0.8; transform: scale(0.25); }}
  100% {{ opacity: 0;   transform: scale(2.6); }}
}}
/* Layer two: a soft trail behind each spark, slower and shrinking. */
@keyframes lf-glow-out {{
  0%   {{ opacity: 0.85; transform: rotate(var(--a)) translateY(0) scale(1); }}
  100% {{ opacity: 0;    transform: rotate(var(--a)) translateY(calc(-1 * var(--d))) scale(0.35); }}
}}
/* Layer three: embers drift further and outlast the burst. */
@keyframes lf-ember-out {{
  0%   {{ opacity: 0;   transform: rotate(var(--a)) translateY(0); }}
  20%  {{ opacity: 0.8; }}
  100% {{ opacity: 0;   transform: rotate(var(--a)) translateY(calc(-1.9 * var(--d))); }}
}}
/* Layer four, World Class only: dust still drifting after everything else has
   settled, which is what makes the top tier feel like it lingers. */
@keyframes lf-ambient-out {{
  0%   {{ opacity: 0;    transform: translateY(0) scale(0.8); }}
  30%  {{ opacity: 0.55; }}
  100% {{ opacity: 0;    transform: translateY(-150px) scale(1); }}
}}
/* The crown drops in over the badge and settles. */
@keyframes lf-crown {{
  0%   {{ opacity: 0; transform: translateY(-40px) scale(0.55); }}
  70%  {{ opacity: 1; transform: translateY(3px) scale(1.07); }}
  100% {{ opacity: 1; transform: translateY(0) scale(1); }}
}}
/* The counter's landing: harder on the tiers that earned it (--lf-pop). */
@keyframes lf-count {{
  0%   {{ opacity: 0; transform: scale(0.85); }}
  55%  {{ opacity: 1; transform: scale(var(--lf-pop, 1)); }}
  100% {{ opacity: 1; transform: scale(1); }}
}}
/* The shine is a narrow soft-edged window sliding right over a white copy of
   the text, while the copy slides left by the same distance so its letters stay
   exactly over the originals. Both are transforms: animating the gradient's
   background-position instead repainted the text on every frame (Section 7).
   Window = 40% of the text, copy = 250% of the window - which makes the copy
   exactly as wide as the text, so a percentage means the same distance on
   both: -100%/250% against 40%/-100%, and the two always cancel. Measured in
   the browser: window -64.05px, copy +64.04px. */
@keyframes lf-shine-window {{
  0%   {{ transform: translateX(-100%); }}
  100% {{ transform: translateX(250%); }}
}}
@keyframes lf-shine-copy {{
  0%   {{ transform: translateX(40%); }}
  100% {{ transform: translateX(-100%); }}
}}

/* --- The sequence, timed as fractions of the tier's duration -------------
   --lf-dur is the only clock. A tier is louder by lasting longer, shaking
   further and throwing more, never by running a different timeline. */
.lf-veil  {{ animation: lf-veil 220ms ease-out both; }}
.lf-card  {{ animation: lf-rise 420ms cubic-bezier(0.22, 1, 0.36, 1) both; }}
/* Shake, zoom and rise each get their own element: two animations on one
   element that both drive `transform` do not compose - the later one simply
   wins. The PR overlay reuses .lf-veil and .lf-card, so everything the
   celebration adds is scoped to .lf-celebrate and its own stage. */
.lf-stage {{ animation: lf-shake calc(var(--lf-dur, 1800ms) * 0.26) cubic-bezier(0.36, 0.07, 0.19, 0.97) 60ms both; }}
.lf-zoom-wrap {{ animation: lf-zoom calc(var(--lf-dur, 1800ms) * 0.45) cubic-bezier(0.16, 1, 0.3, 1) both; }}
.lf-flash {{
  position: fixed;
  inset: 0;
  background: {theme.TEXT};
  pointer-events: none;
  animation: lf-flash calc(var(--lf-dur, 1800ms) * 0.3) ease-out both;
}}
.lf-badge {{ animation: lf-burst 620ms cubic-bezier(0.22, 1, 0.36, 1) 80ms both; }}
/* A rank is a word, not a digit: it starts wide and slightly large and settles
   as the rings go out - a heavier landing than the level number's pop. */
@keyframes lf-land {{
  0%   {{ opacity: 0; transform: scale(1.22); }}
  60%  {{ opacity: 1; transform: scale(0.99); }}
  100% {{ opacity: 1; transform: scale(1); }}
}}
.lf-badge.lf-rank {{
  animation: lf-land 820ms cubic-bezier(0.16, 1, 0.3, 1) 80ms both;
  /* "INTERMEDIATE" is the longest tier and has to fit a 320px phone's card
     (90vw less 2rem of padding either side) without touching the edges. */
  font-size: 1.4rem;
  letter-spacing: 0.12em;
  line-height: 1.1;
  text-align: center;
  padding: 0 0.4rem;
}}
/* The promotion, read at a glance: the tier left behind, then the new one. */
.lf-ladder {{
  animation: lf-rise 520ms cubic-bezier(0.22, 1, 0.36, 1) 380ms both;
  letter-spacing: 0.12em;
}}
.lf-line  {{ animation: lf-rise 460ms cubic-bezier(0.22, 1, 0.36, 1) 220ms both; }}
.lf-ring  {{
  /* A few beats around the badge, then still - bounded and clipped by the
     card, so it frames the number instead of crossing the text. */
  animation: lf-ring 1100ms ease-out 120ms 3 both;
  border: 2px solid var(--lf-glow, #9a9aa2);
}}
.lf-ring.lf-shock {{
  animation: lf-shock calc(var(--lf-dur, 1800ms) * 0.4) cubic-bezier(0.1, 0.8, 0.2, 1) 40ms both;
  border-width: 3px;
  border-color: var(--lf-base, #9a9aa2);
}}

/* --- Particles: one rule per layer, count and spread from the tier -------- */
.lf-p {{
  position: absolute;
  top: 50%;
  left: 50%;
  pointer-events: none;
  animation-delay: var(--lf-delay, 0ms);
  animation-fill-mode: both;
}}
.lf-p.lf-spark {{
  width: 3px;
  height: 14px;
  margin: -7px 0 0 -1.5px;
  border-radius: 2px;
  background: linear-gradient(var(--lf-base, #9a9aa2), var(--lf-glow, #9a9aa2));
  animation-name: lf-spark;
  animation-duration: calc(var(--lf-dur, 1800ms) * 0.5);
  animation-timing-function: cubic-bezier(0.2, 0.8, 0.2, 1);
}}
/* A rank-up throws plates: wider, further, spinning. */
.lf-rank-up .lf-p.lf-spark {{
  width: 9px;
  height: 4px;
  margin: -2px 0 0 -4.5px;
  animation-name: lf-plate;
  animation-duration: calc(var(--lf-dur, 1800ms) * 0.62);
}}
.lf-p.lf-glow {{
  width: 16px;
  height: 16px;
  margin: -8px 0 0 -8px;
  border-radius: 50%;
  background: var(--lf-glow, #9a9aa2);
  filter: blur(5px);
  animation-name: lf-glow-out;
  animation-duration: calc(var(--lf-dur, 1800ms) * 0.66);
  animation-timing-function: ease-out;
}}
.lf-p.lf-ember {{
  width: 4px;
  height: 4px;
  margin: -2px 0 0 -2px;
  border-radius: 50%;
  background: var(--lf-jewel, #9a9aa2);
  animation-name: lf-ember-out;
  animation-duration: calc(var(--lf-dur, 1800ms) * 0.9);
  animation-timing-function: cubic-bezier(0.25, 0.6, 0.3, 1);
}}
.lf-p.lf-ambient {{
  top: auto;
  bottom: -10px;
  left: var(--x);
  width: 3px;
  height: 3px;
  margin: 0;
  border-radius: 50%;
  background: var(--lf-jewel, #9a9aa2);
  animation-name: lf-ambient-out;
  animation-duration: calc(var(--lf-dur, 1800ms) * 0.75);
  animation-timing-function: linear;
  animation-iteration-count: 2;
}}

/* --- Ornaments -----------------------------------------------------------
   Placeholder geometry, drawn with borders and one clip-path. Swapping in
   illustrated art means replacing `_ornament()`; nothing above depends on how
   these are drawn. */
.lf-laurel {{
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 2px solid transparent;
  border-left-color: var(--lf-glow, #9a9aa2);
  border-right-color: var(--lf-glow, #9a9aa2);
  opacity: 0.85;
  animation: lf-burst calc(var(--lf-dur, 1800ms) * 0.4) cubic-bezier(0.22, 1, 0.36, 1) 120ms both;
}}
.lf-gem {{
  position: absolute;
  top: 50%;
  left: 50%;
  width: 9px;
  height: 9px;
  margin: -4.5px 0 0 -4.5px;
  background: var(--lf-jewel, #9a9aa2);
  transform: rotate(var(--a)) translateY(-68px) rotate(45deg);
  animation: lf-burst calc(var(--lf-dur, 1800ms) * 0.45) cubic-bezier(0.22, 1, 0.36, 1) 200ms both;
}}
.lf-crown {{
  position: absolute;
  top: -26px;
  left: 50%;
  margin-left: -26px;
  width: 52px;
  height: 30px;
  background: linear-gradient(var(--lf-base, #9a9aa2), var(--lf-glow, #9a9aa2));
  clip-path: polygon(0% 100%, 12% 34%, 30% 62%, 50% 8%, 70% 62%, 88% 34%, 100% 100%);
  animation: lf-crown calc(var(--lf-dur, 1800ms) * 0.36) cubic-bezier(0.16, 1, 0.3, 1) calc(var(--lf-dur, 1800ms) * 0.22) both;
}}
.lf-filigree {{
  position: absolute;
  inset: -18px;
  border-radius: 50%;
  border: 1px dashed var(--lf-jewel, #9a9aa2);
  opacity: 0.5;
  animation: lf-burst calc(var(--lf-dur, 1800ms) * 0.5) ease-out 260ms both;
}}

/* --- The counter ---------------------------------------------------------
   The number is written by the script into an attribute React never sets, and
   painted with content: attr(). Writing textContent into a React-owned node
   is what caused hydration error #418 in rest_timer.py. With no script at all
   the line simply reads LEVEL with nothing after it. */
/* The label and the number arrive together: animating only the number left
   "LEVEL" sitting there alone for two seconds. */
.lf-count-line {{
  animation: lf-count calc(var(--lf-dur, 1800ms) * 0.3) cubic-bezier(0.16, 1, 0.3, 1) calc(var(--lf-dur, 1800ms) * 0.45) both;
}}
.lf-count {{ font-variant-numeric: tabular-nums; }}
.lf-count::after {{ content: attr(data-ma-count); }}

/* --- Dismissal -----------------------------------------------------------
   The reward is not swipeable away mid-sequence: the veil ignores pointer
   events until the script marks it ready, which it does after the tier's
   duration and, as a backstop, after 5s whatever happens. */
.lf-celebrate {{ pointer-events: none; }}
.lf-celebrate[data-ma-ready] {{ pointer-events: auto; }}
.lf-continue {{ opacity: 0; transition: opacity 220ms ease; }}
.lf-celebrate[data-ma-ready] .lf-continue {{ opacity: 1; }}

/* Brushed-metal numbers and a light sweep across the heading. */
.lf-metal {{
  background: linear-gradient(180deg, var(--lf-base, #9a9aa2) 0%, var(--lf-glow, #9a9aa2) 45%, {theme.MUTED} 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}}
.lf-shine {{ position: relative; display: inline-block; }}
.lf-shine-window {{
  position: absolute;
  inset: 0;
  overflow: hidden;
  width: 40%;
  animation: lf-shine-window 1500ms ease-out 380ms 2 both;
  pointer-events: none;
}}
.lf-shine-copy {{
  position: absolute;
  top: 0;
  left: 0;
  width: 250%;
  color: {theme.TEXT};
  animation: lf-shine-copy 1500ms ease-out 380ms 2 both;
}}

/* Motion sensitivity: no scaling, no travel, no sparks or shine - just a fade.
   The badge, the promotion line and the counter still say what happened. */
@media (prefers-reduced-motion: reduce) {{
  .lf-veil, .lf-card, .lf-badge, .lf-line, .lf-stage, .lf-zoom-wrap {{
    animation: lf-veil 160ms ease-out both;
  }}
  .lf-ring, .lf-p, .lf-flash, .lf-crown, .lf-gem, .lf-laurel, .lf-filigree {{ display: none; }}
  .lf-badge.lf-rank {{ animation: lf-veil 160ms ease-out both; }}
  .lf-ladder, .lf-count-line {{ animation: lf-veil 160ms ease-out both; }}
  .lf-shine-window {{ display: none; }}
}}
"""

_SCRIPT = """
(function () {
  if (window.maCelebrate) return;
  // Anything longer than this and a reward starts feeling like a lock screen.
  var CAP = 5000;

  function ctx() {
    try {
      var C = window.AudioContext || window.webkitAudioContext;
      if (!C) return null;
      if (!window.__maAudio) window.__maAudio = new C();
      if (window.__maAudio.state === 'suspended') window.__maAudio.resume();
      return window.__maAudio;
    } catch (e) { return null; }
  }

  // Tones, not files: a sample pack would be a download and an asset pipeline
  // for four sounds. Each layer is a short envelope so nothing clips or rings.
  function tone(ac, type, from, to, at, len, gain) {
    var osc = ac.createOscillator(), amp = ac.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(from, ac.currentTime + at);
    if (to !== from) osc.frequency.exponentialRampToValueAtTime(to, ac.currentTime + at + len);
    amp.gain.setValueAtTime(0.0001, ac.currentTime + at);
    amp.gain.exponentialRampToValueAtTime(gain, ac.currentTime + at + 0.02);
    amp.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime + at + len);
    osc.connect(amp); amp.connect(ac.destination);
    osc.start(ac.currentTime + at); osc.stop(ac.currentTime + at + len + 0.05);
  }

  function play(layers) {
    var ac = ctx();
    if (!ac) return;
    layers.forEach(function (layer) {
      if (layer === 'chime')   { tone(ac, 'sine', 880, 1320, 0, 0.5, 0.16); }
      if (layer === 'shimmer') { [1760, 2340, 2640].forEach(function (f, i) { tone(ac, 'triangle', f, f, 0.06 + i * 0.07, 0.6, 0.05); }); }
      if (layer === 'bass')    { tone(ac, 'sine', 90, 55, 0, 0.7, 0.28); }
      if (layer === 'fanfare') { [523, 659, 784, 1046].forEach(function (f, i) { tone(ac, 'sawtooth', f, f, i * 0.11, 0.55, 0.07); }); }
    });
  }

  function buzz(pattern) {
    try { if (navigator.vibrate && pattern.length) navigator.vibrate(pattern); } catch (e) {}
  }

  function numbers(value) {
    return String(value || '').split(',').map(Number).filter(function (n) { return !isNaN(n); });
  }

  window.maCelebrate = function () {
    var root = document.getElementById('ma-celebrate');
    if (!root || root.__maRan) return;
    root.__maRan = true;

    var calm = false;
    try { calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}
    var dur = Math.min(parseInt(root.getAttribute('data-ma-duration') || '1800', 10), CAP);

    if (root.getAttribute('data-ma-muted') !== '1') {
      var layers = (root.getAttribute('data-ma-sound') || '').split(',').filter(Boolean);
      if (layers.length) play(layers);
      buzz(numbers(root.getAttribute('data-ma-haptic')));
    }

    // The level counter ticks up into an attribute React never sets - see the
    // hydration note in rest_timer.py. Reduced motion jumps to the answer.
    var counter = root.querySelector('.lf-count');
    if (counter) {
      var from = parseInt(counter.getAttribute('data-ma-from') || '0', 10);
      var to = parseInt(counter.getAttribute('data-ma-to') || '0', 10);
      if (calm || to <= from) {
        counter.setAttribute('data-ma-count', String(to));
      } else {
        var started = 0, span = dur * 0.3;
        var step = function (now) {
          if (!started) started = now;
          var k = Math.min(1, (now - started) / span);
          counter.setAttribute('data-ma-count', String(Math.round(from + (to - from) * k)));
          if (k < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
      }
    }

    // Not dismissible until the sequence has played - but always dismissible
    // in the end, even if a backgrounded tab throttles the first timer.
    var ready = function () { root.setAttribute('data-ma-ready', '1'); };
    if (calm) ready(); else setTimeout(ready, dur);
    setTimeout(ready, CAP);
  };
})();
"""


def keyframes() -> rx.Component:
    """Injected once per page that can raise the overlay."""
    return rx.fragment(rx.el.style(_KEYFRAMES), rx.script(_SCRIPT))


def _ring(extra_class: str = "", delay: str = "120ms") -> rx.Component:
    return rx.box(
        class_name=f"lf-ring {extra_class}".strip(),
        position="absolute",
        width="128px",
        height="128px",
        border_radius="50%",
        pointer_events="none",
        style={"animation-delay": delay},
    )


def _particles() -> rx.Component:
    """One element per particle, angle and travel from the tier's config."""
    return rx.foreach(
        QuestState.level_up_particles,
        lambda p: rx.box(
            class_name=p["cls"],
            style={
                "--a": p["a"],
                "--d": p["d"],
                "--x": p["x"],
                "--lf-delay": p["delay"],
            },
        ),
    )


def _gems() -> rx.Component:
    return rx.fragment(
        *[
            rx.box(class_name="lf-gem", style={"--a": f"{angle}deg"})
            for angle in (0, 72, 144, 216, 288)
        ]
    )


def _ornament() -> rx.Component:
    """Plain -> laurel -> laurel and gems -> crown -> full regalia.

    Placeholder geometry (see the CSS): this function is the seam. Illustrated
    or Lottie art would replace what each branch returns, and the sequencing
    above would not change.
    """
    return rx.match(
        QuestState.level_up_ornament,
        ("laurel", rx.box(class_name="lf-laurel")),
        ("gems", rx.fragment(rx.box(class_name="lf-laurel"), _gems())),
        ("crown", rx.fragment(rx.box(class_name="lf-laurel"), _gems(), rx.box(class_name="lf-crown"))),
        (
            "regalia",
            rx.fragment(
                rx.box(class_name="lf-filigree"),
                rx.box(class_name="lf-laurel"),
                _gems(),
                rx.box(class_name="lf-crown"),
            ),
        ),
        rx.fragment(),
    )


def _sound_toggle() -> rx.Component:
    """A rank-up is the only thing in MetalArm that makes a noise, and there is
    no global sound preference to hook into, so it carries its own - remembered
    in the browser, off for nobody by default but one tap from silent."""
    return rx.button(
        rx.cond(QuestState.sound_muted, "SOUND OFF", "SOUND ON"),
        on_click=QuestState.toggle_sound,
        background="transparent",
        border=f"1px solid {theme.BORDER}",
        color=theme.MUTED,
        border_radius="8px",
        font_size="0.6rem",
        font_weight="700",
        letter_spacing="0.12em",
        padding="0.25rem 0.5rem",
        cursor="pointer",
        position="absolute",
        top="0.7rem",
        right="0.7rem",
        aria_label=rx.cond(QuestState.sound_muted, "Turn celebration sound on", "Turn celebration sound off"),
    )


def level_up_overlay() -> rx.Component:
    return rx.cond(
        QuestState.show_level_up,
        rx.box(
            rx.box(class_name="lf-flash"),
            rx.center(
                rx.box(
                rx.vstack(
                    _sound_toggle(),
                    rx.box(
                        _ring(delay="120ms"),
                        # Rank-up is the rarer, larger beat: more rings, later.
                        rx.cond(QuestState.level_up_rings > 1, _ring("lf-late", "420ms")),
                        rx.cond(QuestState.level_up_rings > 2, _ring("lf-latest", "700ms")),
                        rx.cond(QuestState.level_up_shock, _ring("lf-shock", "40ms")),
                        _particles(),
                        _ornament(),
                        # The new level number, or the new rank title. Showing
                        # the value reached is the payoff; "you levelled up"
                        # without saying to what is a weaker beat.
                        rx.heading(
                            QuestState.level_up_badge,
                            size="9",
                            font_weight="900",
                            line_height="1",
                            class_name=rx.cond(
                                QuestState.level_up_is_rank,
                                "lf-metal lf-badge lf-rank",
                                "lf-metal lf-badge",
                            ),
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
                    rx.cond(
                        QuestState.level_up_ladder != "",
                        rx.text(
                            QuestState.level_up_ladder,
                            color=theme.MUTED,
                            font_size="0.8rem",
                            font_weight="700",
                            text_align="center",
                            class_name="lf-ladder",
                        ),
                    ),
                    # The level counter, ticking up to where the session left
                    # it. The number is painted from a data attribute the
                    # script owns; React only supplies the two ends.
                    rx.text(
                        "LEVEL ",
                        rx.el.span(
                            class_name="lf-count",
                            custom_attrs={
                                "data-ma-from": QuestState.level_up_level_from.to_string(),
                                "data-ma-to": QuestState.level_up_level_to.to_string(),
                            },
                        ),
                        color=theme.TEXT,
                        font_size="0.95rem",
                        font_weight="800",
                        letter_spacing="0.16em",
                        text_align="center",
                        class_name="lf-count-line",
                    ),
                    rx.text(
                        QuestState.level_up_line,
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
                        class_name="lf-line lf-continue",
                    ),
                    spacing="4",
                    align="center",
                    class_name="lf-card",
                    position="relative",
                    padding="2.5rem 2rem",
                    background=theme.PANEL,
                    border="1px solid var(--lf-glow, #9a9aa2)",
                    border_radius="18px",
                    box_shadow=theme.glow("var(--lf-glow, #9a9aa2)", "150px"),
                    max_width="90vw",
                    overflow="hidden",
                ),
                    class_name="lf-zoom-wrap",
                ),
                width="100%",
                height="100%",
                class_name="lf-stage",
            ),
            id="ma-celebrate",
            # lf-celebrate is what the dismissal and stage rules hang off:
            # the PR overlay shares .lf-veil and must stay clickable.
            class_name=rx.cond(
                QuestState.level_up_is_rank,
                "lf-veil lf-celebrate lf-rank-up",
                "lf-veil lf-celebrate",
            ),
            # Read by the script on mount: what to play, how long to hold the
            # reward open, and whether the browser has been told to be quiet.
            custom_attrs={
                "data-ma-duration": QuestState.level_up_duration.to_string(),
                "data-ma-sound": QuestState.level_up_sound,
                "data-ma-haptic": QuestState.level_up_haptic,
                "data-ma-muted": rx.cond(QuestState.sound_muted, "1", "0"),
            },
            style={
                "--lf-dur": QuestState.level_up_duration_css,
                "--lf-base": QuestState.level_up_base,
                "--lf-glow": QuestState.level_up_glow,
                "--lf-jewel": QuestState.level_up_jewel,
                "--lf-shake": QuestState.level_up_shake,
                "--lf-zoom": QuestState.level_up_zoom,
                "--lf-pop": QuestState.level_up_pop,
            },
            position="fixed",
            top="0",
            left="0",
            width="100vw",
            height="100vh",
            background=theme.VEIL,
            backdrop_filter="blur(3px)",
            z_index="100",
            # Dismissible by clicking the veil once the sequence has played, so
            # the overlay can never trap the user if the button is off-screen.
            on_click=QuestState.dismiss_level_up,
            on_mount=rx.call_script("window.maCelebrate && window.maCelebrate()"),
        ),
    )
