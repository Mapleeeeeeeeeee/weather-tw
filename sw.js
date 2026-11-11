// The offline cache was removed: it served the previous page first, so new versions only showed after a full restart.
// This worker only cleans up what older versions left on a device (every cache, then the worker itself) and reloads open pages.
// The page no longer registers any worker. Delete this file once every device you use has opened the app since this change.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) await caches.delete(k);
    await self.registration.unregister();
    for (const c of await self.clients.matchAll({ type: "window" })) c.navigate(c.url);
  })());
});
