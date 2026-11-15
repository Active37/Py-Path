const CACHE_NAME = "pypath-shell-v9";
const APP_SHELL = [
  "/static/app.css?v=9",
  "/static/app.js?v=9",
  "/static/manifest.webmanifest?v=9",
  "/static/pwa/icon.svg?v=9",
  "/static/pwa/icon-192.png?v=9",
  "/static/pwa/icon-512.png?v=9",
  "/static/pwa/apple-touch-icon.png?v=9",
  "/static/offline.html?v=9"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names.filter((name) => name.startsWith("pypath-shell-") && name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("/static/offline.html", { ignoreSearch: true }))
    );
    return;
  }

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request, { ignoreSearch: true }).then((cached) => cached || fetch(request))
    );
  }
});
