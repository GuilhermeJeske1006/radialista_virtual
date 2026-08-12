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
  // So intercepta same-origin (assets/paginas). Requests cross-origin (ex.: API
  // backend em outra porta) ficam pro browser lidar direto -- refazer o fetch aqui
  // dentro do SW quebra CORS em POST/PUT cross-origin.
  if (new URL(event.request.url).origin !== self.location.origin) {
    return;
  }
  event.respondWith(fetch(event.request));
});
