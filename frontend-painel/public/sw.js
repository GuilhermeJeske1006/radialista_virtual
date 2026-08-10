// Minimal service worker: exists only to satisfy PWA installability
// (Chrome/Edge require a controlling SW with a fetch handler). No caching —
// the panel always needs live data, so everything just passes through.
self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  event.respondWith(fetch(event.request));
});
