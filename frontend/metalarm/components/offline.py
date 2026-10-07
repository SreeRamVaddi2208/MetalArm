"""Offline set logging (overhaul phase 5) - for a bad signal in the gym.

The app's state lives on the server, over a websocket, so with no connection
a tap on "Log set" would go nowhere. This script catches that tap first (a
capture-phase listener, before React), reads the entry row's values - the
weight and reps the row is showing, pre-filled from the routine or last
time - and keeps the set in localStorage with its own client_set_id. When
the connection is back it posts each queued set straight to the API, oldest
first; the id makes a retry log nothing twice. Then it asks the page to
reload the workout, and the sets appear as if logged live.

Like the rest timer, it never writes React-owned text: only attributes
(data-ma-*) that CSS renders.
"""

import os

import reflex as rx

from metalarm import theme as t
from metalarm.state.workout import WorkoutState

# The API as the BROWSER reaches it (the frontend server uses an internal
# address). Baked in when the frontend is compiled.
PUBLIC_API = os.getenv("METALARM_PUBLIC_API_URL", "http://localhost:8000").rstrip("/")

_CSS = f"""
.ma-offline {{ display: none; }}
.ma-offline[data-ma-online="0"], .ma-offline[data-ma-count]:not([data-ma-count=""]) {{
  display: block; position: sticky; top: 0; z-index: 25;
  background: {t.SURFACE_2}; color: {t.TEXT}; border-radius: {t.RADIUS};
  padding: {t.space(8)} {t.space(12)}; font-size: {t.LABEL["font_size"]}; line-height: {t.LABEL["line_height"]};
  font-weight: {t.LABEL["font_weight"]};
}}
.ma-offline[data-ma-online="0"]::after {{ content: "Offline - sets you log are kept and sent when you reconnect"; }}
.ma-offline[data-ma-count]:not([data-ma-count=""])::after {{ content: attr(data-ma-count); }}
.ma-card[data-ma-queued]::after {{
  content: attr(data-ma-queued); color: {t.TEXT_2}; font-size: {t.CAPTION["font_size"]};
  line-height: {t.CAPTION["line_height"]};
}}
"""

_SCRIPT = """
(function () {
  if (window.__maOffline) return;
  window.__maOffline = true;
  var KEY = 'ma_offline_sets';

  function api() {
    var meta = document.querySelector('meta[name="ma-api"]');
    return (meta && meta.content) || '';
  }
  function token() {
    var raw = localStorage.getItem('lf_token') || '';
    try { if (raw.charAt(0) === '"') raw = JSON.parse(raw); } catch (e) {}
    return raw;
  }
  function read() {
    try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch (e) { return []; }
  }
  function save(queue) { localStorage.setItem(KEY, JSON.stringify(queue)); render(); }
  function set(node, name, value) {
    if (value === null) node.removeAttribute(name);
    else if (node.getAttribute(name) !== value) node.setAttribute(name, value);
  }

  function render() {
    var queue = read();
    var bar = document.getElementById('ma-offline');
    if (bar) {
      set(bar, 'data-ma-online', navigator.onLine ? '1' : '0');
      set(bar, 'data-ma-count', queue.length === 0 ? '' :
        queue.length + (queue.length === 1 ? ' set' : ' sets') +
        (navigator.onLine ? ' sending...' : ' waiting for a connection'));
    }
    document.querySelectorAll('.ma-card').forEach(function (card) {
      var entry = card.querySelector('.ma-entry');
      var id = entry ? entry.getAttribute('data-ma-card') : null;
      var n = queue.filter(function (q) { return q.card === id; }).length;
      set(card, 'data-ma-queued', n ? n + ' queued - sent when you reconnect' : null);
    });
  }

  document.addEventListener('click', function (event) {
    if (navigator.onLine) return;
    var button = event.target.closest && event.target.closest('[aria-label="Log set"]');
    var row = button && button.closest('.ma-entry');
    if (!row) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    var values = Array.prototype.map.call(row.querySelectorAll('input'), function (i) { return i.value.trim(); });
    var reps = parseInt(values[1], 10);
    if (!(reps >= 1)) return;
    var rpe = parseFloat(values[2]);
    var queue = read();
    queue.push({
      session: row.getAttribute('data-ma-session'),
      card: row.getAttribute('data-ma-card'),
      at: new Date().toISOString(),
      body: {
        exercise_id: row.getAttribute('data-ma-exercise'),
        session_exercise_id: row.getAttribute('data-ma-card') || null,
        weight: parseFloat(values[0]) || 0,
        unit: row.getAttribute('data-ma-unit') || 'kg',
        reps: reps,
        rpe: isNaN(rpe) ? null : rpe,
        set_type: row.getAttribute('data-ma-type') || 'normal',
        client_set_id: (crypto.randomUUID ? crypto.randomUUID() :
          'xxxxxxxx-xxxx-4xxx-8xxx-xxxxxxxxxxxx'.replace(/x/g, function () { return (Math.random() * 16 | 0).toString(16); }))
      }
    });
    save(queue);
  }, true);

  var flushing = false;
  async function flush() {
    if (flushing || !navigator.onLine) return;
    var queue = read();
    if (!queue.length) return;
    flushing = true;
    var sent = 0;
    while (queue.length) {
      var item = queue[0];
      var response;
      try {
        response = await fetch(api() + '/api/v1/workouts/sessions/' + item.session + '/sets', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token() },
          body: JSON.stringify(item.body)
        });
      } catch (e) { break; }                    // still no way through: keep it
      if (response.status === 401 || response.status >= 500) break;   // try again later
      // Sent - or refused for good (the workout was finished or discarded
      // meanwhile): either way it leaves the queue.
      if (!response.ok) console.warn('MetalArm: a queued set was refused', response.status, item);
      else sent++;
      queue.shift();
      save(queue);
    }
    flushing = false;
    if (sent) {
      var sync = document.getElementById('ma-sync');
      if (sync) sync.click();
    }
  }

  window.addEventListener('online', function () { render(); setTimeout(flush, 800); });
  window.addEventListener('offline', render);
  setInterval(function () { render(); flush(); }, 4000);
  render();
  flush();
})();
"""


def offline_assets() -> rx.Component:
    """The script, its styles, the banner, and the hidden button the script
    presses to reload the workout once queued sets are in."""
    return rx.fragment(
        rx.el.style(_CSS),
        rx.script(_SCRIPT),
        rx.el.div(id="ma-offline", class_name="ma-offline", custom_attrs={"role": "status", "aria-live": "polite"}),
        rx.el.button(id="ma-sync", on_click=WorkoutState.load, display="none", tab_index=-1,
                     custom_attrs={"aria-hidden": "true"}),
    )
