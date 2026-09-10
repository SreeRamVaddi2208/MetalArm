"""Rest timer and live workout clock - entirely client-side.

The brief is explicit that the rest timer needs no backend involvement, and a
ticking clock is the worst possible thing to route through the Reflex
websocket (a state update per second, per user, for nothing). So both are a
small script:

- `#ma-rest`: a bottom bar shown while resting. Started by the workout state
  via rx.call_script after a working set is logged. The end time is kept in
  localStorage, so a refresh mid-rest resumes the countdown instead of losing
  it. Vibrates when rest is over, where the device supports it.
- any `[data-ma-start]` element: shows elapsed time since that ISO instant.

The one rule that matters: the script NEVER writes text or classes into
React-owned nodes. It only sets attributes React does not manage
(`data-ma-state`, `data-ma-time`, `data-ma-clock`), and CSS renders them with
`content: attr(...)`. Writing textContent instead broke hydration: with a rest
still running at page load, the script updated the server-rendered timer text
before React hydrated it, and React 19 threw mismatch error #418. Attributes
React never set are neither compared during hydration nor touched on
re-render, so the script and React cannot fight.

Transform/opacity only for the bar's entrance; reduced motion gets no travel.
"""

import reflex as rx

from metalarm import theme

_CSS = f"""
.ma-rest {{
  position: fixed;
  left: 50%;
  bottom: 16px;
  transform: translate(-50%, 160%);
  opacity: 0;
  pointer-events: none;
  transition: transform 260ms cubic-bezier(0.22, 1, 0.36, 1), opacity 200ms ease;
  z-index: 60;
}}
.ma-rest[data-ma-state] {{ transform: translate(-50%, 0); opacity: 1; pointer-events: auto; }}
.ma-rest-time::after {{ content: attr(data-ma-time); color: {theme.ACCENT}; }}
.ma-rest[data-ma-state="done"] .ma-rest-time::after {{ color: {theme.SUCCESS}; }}
[data-ma-start]::after {{ content: attr(data-ma-clock); }}
@media (prefers-reduced-motion: reduce) {{
  .ma-rest, .ma-rest[data-ma-state] {{ transform: translate(-50%, 0); transition: opacity 120ms ease; }}
}}
"""

_SCRIPT = """
(function () {
  if (window.maRest) return;
  var KEY = 'ma_rest_end';

  function read() { try { return Number(localStorage.getItem(KEY) || 0); } catch (e) { return 0; } }
  function write(v) { try { v ? localStorage.setItem(KEY, String(v)) : localStorage.removeItem(KEY); } catch (e) {} }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function set(node, name, value) {
    if (value === null) { if (node.hasAttribute(name)) node.removeAttribute(name); }
    else if (node.getAttribute(name) !== value) node.setAttribute(name, value);
  }

  function renderRest() {
    var bar = document.getElementById('ma-rest');
    var time = document.getElementById('ma-rest-time');
    if (!bar || !time) return;
    var end = read();
    if (!end) { set(bar, 'data-ma-state', null); return; }
    var left = Math.round((end - Date.now()) / 1000);
    if (left <= 0) {
      if (bar.getAttribute('data-ma-state') !== 'done' && navigator.vibrate) navigator.vibrate([180, 80, 180]);
      set(bar, 'data-ma-state', 'done');
      set(time, 'data-ma-time', 'GO');
      if (left < -10) { write(0); set(bar, 'data-ma-state', null); }
      return;
    }
    set(bar, 'data-ma-state', 'on');
    set(time, 'data-ma-time', Math.floor(left / 60) + ':' + pad(left % 60));
  }

  function renderClocks() {
    document.querySelectorAll('[data-ma-start]').forEach(function (node) {
      var start = Date.parse(node.getAttribute('data-ma-start') || '');
      if (!start) { set(node, 'data-ma-clock', null); return; }
      var s = Math.max(0, Math.floor((Date.now() - start) / 1000));
      var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
      set(node, 'data-ma-clock', (h ? h + ':' + pad(m) : m) + ':' + pad(s % 60));
    });
  }

  window.maRest = {
    start: function (seconds) { write(Date.now() + seconds * 1000); renderRest(); },
    add: function (seconds) { write(Math.max(read(), Date.now()) + seconds * 1000); renderRest(); },
    stop: function () { write(0); renderRest(); }
  };

  setInterval(function () { renderRest(); renderClocks(); }, 250);
  renderRest();
  renderClocks();
})();
"""


def timer_assets() -> rx.Component:
    return rx.fragment(rx.el.style(_CSS), rx.script(_SCRIPT))


def _bar_button(label: str, script: str) -> rx.Component:
    return rx.button(
        label,
        on_click=rx.call_script(script),
        background="transparent",
        color=theme.MUTED,
        border=f"1px solid {theme.BORDER_HI}",
        border_radius="9px",
        font_size="0.72rem",
        font_weight="800",
        letter_spacing="0.1em",
        padding="0.55rem 0.8rem",
        cursor="pointer",
        height="40px",
    )


def rest_bar() -> rx.Component:
    return rx.hstack(
        rx.text("REST", **theme.LABEL_STYLE),
        rx.text(
            id="ma-rest-time",
            class_name="ma-rest-time",
            font_size="1.6rem",
            font_weight="900",
            min_width="4.2ch",
            text_align="center",
            font_variant_numeric="tabular-nums",
        ),
        _bar_button("+30s", "window.maRest && window.maRest.add(30)"),
        _bar_button("SKIP", "window.maRest && window.maRest.stop()"),
        id="ma-rest",
        class_name="ma-rest",
        align="center",
        spacing="3",
        padding="0.6rem 0.9rem",
        background=theme.PANEL,
        border=f"1px solid {theme.BORDER_HI}",
        border_radius="14px",
        box_shadow=f"0 12px 40px -12px #000, {theme.glow(theme.ACCENT, '50px')}",
    )


def elapsed_clock(started_at: rx.Var, **props) -> rx.Component:
    """Elapsed time since `started_at`, ticked by the script above."""
    return rx.el.span(custom_attrs={"data-ma-start": started_at}, **props)
