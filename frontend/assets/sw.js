// MetalArm's service worker: install, and keep working on a bad gym signal.
//
// - The build's hashed files (/assets/*), exercise images and icons are
//   cache-first: a hashed name never changes content.
// - Pages are network-first, falling back to the last copy seen, then to
//   /offline.html.
// - The API and Reflex's event socket are never cached: sets logged without a
//   connection are queued by the page itself (metalarm/components/offline.py)
//   and sent when it returns.
const VERSION = 'metalarm-v1';
const SHELL = ['/offline.html', '/manifest.json', '/icon-192.png', '/icon-512.png', '/favicon.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

const cacheFirst = (path) =>
  path.startsWith('/assets/') || path.startsWith('/exercises/') || /^\/(icon-|favicon|apple-touch)/.test(path);

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith('/_event')) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(VERSION).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(async () => (await caches.match(request)) || caches.match('/offline.html')),
    );
    return;
  }

  if (cacheFirst(url.pathname)) {
    event.respondWith(
      caches.match(request).then((hit) => hit || fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(VERSION).then((cache) => cache.put(request, copy));
        }
        return response;
      })),
    );
  }
});
