// MetalArm's service worker: an offline shell and a queue for sets logged
// without a signal.
//
// What it deliberately does NOT do is cache API responses. Points, ranks and
// duel scores are derived server-side on every read (see app/core/duels.py and
// app/core/leagues.py) precisely so they cannot drift; serving a stale copy of
// them from here would reintroduce exactly the drift that design avoids. The
// shell is cached so the app OPENS offline; what it shows then is what the
// page itself remembers.
//
// Bump CACHE when the shell changes: an old worker keeps serving an old shell
// until its cache name stops matching.
const CACHE = 'metalarm-shell-v2';
// WITH the trailing slash: Reflex answers /dashboard with a 307 to /dashboard/,
// and `cache.add` refuses a redirect, so the bare paths cached nothing at all
// and the app opened to a browser error page offline.
const SHELL = ['/dashboard/', '/workout/', '/duels/', '/manifest.webmanifest',
               '/icon-192.png', '/icon-512.png'];
// Where a navigation lands when nothing better is cached.
const FALLBACK = '/dashboard/';
// Sets logged while offline wait here, in the worker's own store, so closing
// the tab does not lose them.
const QUEUE_DB = 'metalarm-queue';
const QUEUE_STORE = 'sets';

self.addEventListener('install', (event) => {
  // addAll fails the whole install if ANY entry 404s, which would leave the
  // app with no worker at all; each is fetched on its own instead.
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => Promise.all(SHELL.map((url) => cache.add(url).catch(() => null))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(names.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

function openQueue() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(QUEUE_DB, 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(QUEUE_STORE, { keyPath: 'clientSetId' });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function queueRequest(request) {
  const body = await request.clone().json().catch(() => null);
  if (!body) return;
  const db = await openQueue();
  await new Promise((resolve, reject) => {
    const tx = db.transaction(QUEUE_STORE, 'readwrite');
    // Keyed by the client's own id, which is what makes a replay idempotent
    // server-side (POST /workouts/sessions/{id}/sets carries client_set_id).
    tx.objectStore(QUEUE_STORE).put({
      clientSetId: body.client_set_id || crypto.randomUUID(),
      url: request.url,
      body,
      queuedAt: Date.now(),
    });
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
}

async function flushQueue() {
  const db = await openQueue();
  const entries = await new Promise((resolve, reject) => {
    const tx = db.transaction(QUEUE_STORE, 'readonly');
    const all = tx.objectStore(QUEUE_STORE).getAll();
    all.onsuccess = () => resolve(all.result || []);
    all.onerror = () => reject(all.error);
  });
  for (const entry of entries) {
    try {
      const response = await fetch(entry.url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entry.body),
        credentials: 'include',
      });
      // 4xx means the server refused it on its merits - replaying forever
      // would keep a bad set in the queue for good.
      if (response.ok || (response.status >= 400 && response.status < 500)) {
        const tx = db.transaction(QUEUE_STORE, 'readwrite');
        tx.objectStore(QUEUE_STORE).delete(entry.clientSetId);
      }
    } catch {
      return;  // still offline; the rest keep their turn
    }
  }
}

self.addEventListener('sync', (event) => {
  if (event.tag === 'metalarm-sets') event.waitUntil(flushQueue());
});

self.addEventListener('message', (event) => {
  if (event.data === 'flush') event.waitUntil(flushQueue());
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // A set logged without a signal is kept rather than lost.
  if (request.method === 'POST' && /\/workouts\/sessions\/[^/]+\/sets$/.test(url.pathname)) {
    event.respondWith(
      fetch(request.clone()).catch(async () => {
        await queueRequest(request);
        try { await self.registration.sync.register('metalarm-sets'); } catch { /* no Background Sync */ }
        return new Response(JSON.stringify({ queued: true }), {
          status: 202, headers: { 'Content-Type': 'application/json' },
        });
      }),
    );
    return;
  }

  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  // The shell: network first so a deploy is picked up, cache as the fallback.
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok && request.mode === 'navigate') {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(async () => {
        // Try what was asked for, then the same path with the slash Reflex
        // actually serves, then the shell. A navigation must never fall
        // through to the browser's error page.
        const slashed = url.pathname.endsWith('/') ? url.pathname : `${url.pathname}/`;
        return (await caches.match(request))
          || (await caches.match(slashed))
          || (await caches.match(FALLBACK))
          || Response.error();
      }),
  );
});
