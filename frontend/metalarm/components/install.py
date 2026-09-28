"""Registering the service worker, and the install prompt.

Registration is a script rather than anything Reflex knows about: a service
worker has to be served from the origin root and registered by the page, and
Reflex has no opinion about either.

The rules this follows:

- **The app must work with no worker at all.** Registration failing, being
  blocked, or the browser not supporting it changes nothing about the page -
  the worker adds offline, it does not enable the app.
- **The install prompt is offered, never forced.** Chrome fires
  `beforeinstallprompt`; the button appears only if it does, and disappears
  once installed. A browser that never fires it shows nothing, rather than a
  button that does nothing.
- **A queued set is reported honestly.** The worker answers 202 for a set it
  has kept rather than sent, and the page says so - the same promise the iOS
  app makes with its own pending store.
- **Notifications are asked for on a TAP, never on load.** A permission prompt
  that appears unprompted is the fastest way to be denied permanently, and
  Chrome now blocks some of them outright. The button also only appears where
  the server actually has a VAPID key, so it is never offered by a deployment
  that cannot send.
"""

import reflex as rx

from metalarm import theme

_SCRIPT = """
(function () {
  if (window.maInstall) return;
  window.maInstall = { prompt: null };

  function register() {
    if (!('serviceWorker' in navigator)) return;
    navigator.serviceWorker.register('/service-worker.js').then(function (reg) {
      // A set logged offline is flushed the moment we are back.
      window.addEventListener('online', function () {
        if (reg.active) reg.active.postMessage('flush');
      });
    }).catch(function () { /* no worker: the app is unchanged */ });
  }

  // This script is injected by the app AFTER the page has loaded, so waiting
  // for the load event means waiting for one that has already fired and never
  // registering at all. Check first, then listen only if it is still coming.
  if (document.readyState === 'complete') register();
  else window.addEventListener('load', register);

  // Chrome offers the install; we only surface it.
  window.addEventListener('beforeinstallprompt', function (event) {
    event.preventDefault();
    window.maInstall.prompt = event;
    var button = document.getElementById('ma-install');
    if (button) button.removeAttribute('hidden');
  });

  window.addEventListener('appinstalled', function () {
    window.maInstall.prompt = null;
    var button = document.getElementById('ma-install');
    if (button) button.setAttribute('hidden', '');
  });

  // --- Notifications -----------------------------------------------------
  // Base64url from the server to the Uint8Array subscribe() wants.
  function keyBytes(base64) {
    var padded = (base64 + '='.repeat((4 - base64.length % 4) % 4))
      .replace(/-/g, '+').replace(/_/g, '/');
    var raw = atob(padded);
    var bytes = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    return bytes;
  }

  // Returns the subscription as a string for the state to POST, or "" if the
  // browser cannot or the person said no. Deliberately does NOT call the API
  // itself: Reflex state runs on the server, where the token already is, so
  // routing it through there avoids putting credentials in the page and CORS
  // in the way.
  window.maSubscribe = async function (publicKey) {
    try {
      if (!publicKey || !('serviceWorker' in navigator) || !('PushManager' in window)) return '';
      if ((await Notification.requestPermission()) !== 'granted') return '';
      var registration = await navigator.serviceWorker.ready;
      var subscription = await registration.pushManager.getSubscription()
        || await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: keyBytes(publicKey),
        });
      return JSON.stringify(subscription);
    } catch (e) {
      return '';
    }
  };

  window.maInstallApp = function () {
    var deferred = window.maInstall.prompt;
    if (!deferred) return;
    deferred.prompt();
    window.maInstall.prompt = null;
    var button = document.getElementById('ma-install');
    if (button) button.setAttribute('hidden', '');
  };
})();
"""


def install_assets() -> rx.Component:
    """Injected once per page that can offer the install."""
    return rx.script(_SCRIPT)


def install_button() -> rx.Component:
    """Hidden until the browser says the app CAN be installed, so it is never
    a button that does nothing."""
    return rx.el.button(
        "INSTALL THE APP",
        id="ma-install",
        hidden=True,
        on_click=rx.call_script("window.maInstallApp && window.maInstallApp()"),
        style={
            "background": "transparent",
            "border": f"1px solid {theme.BORDER}",
            "border_radius": "9px",
            "color": theme.MUTED,
            "font_size": "0.68rem",
            "font_weight": "700",
            "letter_spacing": "0.12em",
            "padding": "0.4rem 0.7rem",
            "cursor": "pointer",
        },
    )
