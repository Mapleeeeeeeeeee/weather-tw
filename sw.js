// Service Worker: precache the app shell, then stale-while-revalidate.
// Bump VERSION when the shell file list changes.
const VERSION = "v1";
const CACHE = `weather-tw-${VERSION}`;
const SHELL = [
  "./", "index.html", "manifest.webmanifest",
  "favicon.svg", "favicon-16.png", "favicon-32.png", "apple-touch-icon.png",
  "icon-192.png", "icon-512.png", "icon-maskable-512.png",
  "fonts/genyomin-r.woff2", "fonts/genyomin-sb.woff2",
];
const CACHEABLE_HOSTS = ["fonts.googleapis.com", "fonts.gstatic.com"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin && !CACHEABLE_HOSTS.includes(url.hostname)) return;

  e.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const cached = await cache.match(req, { ignoreSearch: req.mode === "navigate" });
      const network = fetch(req)
        .then((res) => {
          if (res && (res.ok || res.type === "opaque")) cache.put(req, res.clone());
          return res;
        })
        .catch(() => null);
      if (cached) { e.waitUntil(network); return cached; }
      const res = await network;
      return res || (req.mode === "navigate" ? cache.match("index.html") : Response.error());
    })
  );
});
