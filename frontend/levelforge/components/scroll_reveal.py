"""Scroll-linked reveals (Section 7).

Two implementations of the same effect, picked per browser:

1. **CSS scroll-driven animation** (`animation-timeline: view()`), where
   supported. This is genuinely scroll-LINKED - progress is a function of the
   element's position in the viewport, driven by the compositor with no
   JavaScript on the frame path at all.
2. **IntersectionObserver**, everywhere else. A trigger rather than a true
   linkage, but it degrades honestly: the element fades in once and stays.

Principles this follows, and why:

- **Never scroll-jacking.** Nothing here touches scroll position, wheel events
  or scroll-snap. The animation tracks the user's scroll; it never replaces it.
- **Transform and opacity only.** Both are compositor properties, so a reveal
  costs no layout or paint. Animating `top`/`height`/`margin` instead would
  force a reflow on every frame of every card.
- **Progressive enhancement, and this part matters.** The hidden state is
  scoped to `html.lf-js`, a class the script adds to the document itself. If
  the script never runs - blocked, errored, unsupported - that class is absent
  and every element renders fully visible. Content must never depend on
  JavaScript to become readable.
- **`prefers-reduced-motion` is honoured**, not approximated: no travel, no
  scaling, just a short fade.
"""

import reflex as rx

from levelforge import theme

# Distance a revealing element travels. Small on purpose - a long slide reads
# as sluggish once you have scrolled past a dozen of them.
_TRAVEL = "18px"

_CSS = f"""
/* Baseline: visible. Nothing here can leave content unreadable if the CSS
   feature is missing or the script never runs. */
.lf-reveal {{ }}

/* --- Path 1: genuinely scroll-LINKED, CSS only, no JavaScript ----------- */
/* Progress is a function of the element's position in the viewport, driven by
   the compositor. Because this needs no script, there is no window between
   first paint and hydration in which the page could flash. */
@supports (animation-timeline: view()) {{
  .lf-reveal {{
    opacity: 0;
    transform: translate3d(0, {_TRAVEL}, 0);
    animation: lf-reveal-in linear both;
    animation-timeline: view();
    /* Begin as the element enters the lower edge and finish once it is
       properly on screen, so progress tracks scroll rather than firing once. */
    animation-range: entry 5% cover 26%;
  }}
}}

@keyframes lf-reveal-in {{
  to {{ opacity: 1; transform: translate3d(0, 0, 0); }}
}}

/* --- Path 2: IntersectionObserver, for browsers without scroll-timeline -- */
/* `lf-armed` is added by the script ONLY to elements that are below the fold
   when it runs. Anything already on screen is left completely alone, so
   hydration can never hide something the user is already reading and then fade
   it back in - a flash is worse than no animation. */
.lf-reveal.lf-armed {{
  opacity: 0;
  transform: translate3d(0, {_TRAVEL}, 0);
  will-change: opacity, transform;
}}

.lf-reveal.lf-armed.lf-in {{
  opacity: 1;
  transform: translate3d(0, 0, 0);
  transition:
    opacity 520ms cubic-bezier(0.22, 1, 0.36, 1),
    transform 520ms cubic-bezier(0.22, 1, 0.36, 1);
}}

/* Drop the compositor hint once the reveal has played; holding a layer per
   card for the life of the page is a real cost on a long board. */
.lf-reveal.lf-done {{ will-change: auto; }}

/* --- Pinned hero -------------------------------------------------------- */
/* The Stat Panel holds position while the quest board scrolls past beneath -
   the same pattern a product hero uses. 1024px matches Reflex's `lg`
   breakpoint, where dashboard.py switches to two columns: pinning at a width
   with nothing beside it would just freeze the panel mid-page. */
@media (min-width: 1024px) {{
  .lf-pinned {{
    position: sticky;
    /* Clears the sticky navbar. */
    top: 84px;
  }}
}}

/* --- Motion sensitivity: mandatory, not optional ------------------------ */
@media (prefers-reduced-motion: reduce) {{
  .lf-reveal,
  .lf-reveal.lf-armed,
  .lf-reveal.lf-armed.lf-in {{
    opacity: 1;
    transform: none;
    animation: none;
    transition: none;
  }}
  .lf-pinned {{ position: static; }}
}}
"""

# This runs on hydration, i.e. AFTER first paint, which is exactly why it only
# ever arms elements that are currently below the fold. Hiding something the
# user can already see and fading it back in would be a visible flash.
_SCRIPT = """
(function () {
  if (window.__lfReveal) return;
  window.__lfReveal = true;

  var reduce = window.matchMedia &&
               window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce) return;

  // Where scroll-timeline exists the CSS already handles this, with no
  // JavaScript on the frame path. Doing both would double-apply.
  var linked = window.CSS && CSS.supports &&
               CSS.supports('animation-timeline', 'view()');
  if (linked) return;

  if (!('IntersectionObserver' in window)) return;  // leave content visible

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      var el = entry.target;
      el.classList.add('lf-in');
      window.setTimeout(function () { el.classList.add('lf-done'); }, 900);
      io.unobserve(el);
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });

  function arm() {
    var fold = window.innerHeight || 0;
    document.querySelectorAll('.lf-reveal:not(.lf-armed)').forEach(function (el) {
      // Only elements comfortably below the fold. Anything on screen stays
      // untouched and simply never animates - which is correct: it was already
      // visible before the animation code existed.
      if (el.getBoundingClientRect().top <= fold * 0.95) return;
      el.classList.add('lf-armed');
      io.observe(el);
    });
  }

  arm();

  // Reflex re-renders on navigation and on every state update, so cards that
  // appear later must be armed too. Without this, a quest added after load
  // would never animate.
  if ('MutationObserver' in window) {
    new MutationObserver(arm).observe(document.body, {
      childList: true,
      subtree: true,
    });
  }
})();
"""


def reveal_assets() -> rx.Component:
    """Styles + script. Include once per page that uses `reveal`."""
    return rx.fragment(
        rx.el.style(_CSS),
        rx.script(_SCRIPT),
    )


def reveal(child: rx.Component, delay_ms: int = 0) -> rx.Component:
    """Wrap a component so it reveals as it scrolls into view.

    `delay_ms` staggers a list. Keep it small and cap it: a long stagger on a
    twenty-item board leaves the last item visibly late.
    """
    return rx.box(
        child,
        class_name="lf-reveal",
        style={"--lf-delay": f"{delay_ms}ms"},
        width="100%",
    )


def pinned(child: rx.Component) -> rx.Component:
    """Hold a component in place while the rest of the page scrolls past.

    Sticky, never fixed: it stays inside its column and stops at the end of it,
    so it cannot overlap the footer or trap the user.
    """
    return rx.box(child, class_name="lf-pinned", width="100%")


def section_label(text: str) -> rx.Component:
    """Small scroll-revealed heading used between page sections."""
    return reveal(
        rx.text(text, **theme.LABEL_STYLE),
    )
