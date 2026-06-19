const CACHE_NAME = "process-offline-shell-v12";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL_URLS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) {
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(networkFirstNavigation(request, routeCacheKey(url.pathname)));
    return;
  }

  if (url.pathname === "/api/bootstrap") {
    event.respondWith(networkFirst(request, "/api/bootstrap"));
    return;
  }

  if (
    url.pathname.startsWith("/static/")
    || url.pathname === "/manifest.webmanifest"
    || url.pathname === "/service-worker.js"
  ) {
    event.respondWith(cacheFirst(request));
  }
});

function routeCacheKey(pathname) {
  return APP_ROUTE_URLS.includes(pathname) ? pathname : "/";
}

async function networkFirstNavigation(request, cacheKey) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request);
    if (response.ok && !response.redirected) {
      await cache.put(cacheKey, response.clone());
    }
    return response;
  } catch (_error) {
    const cached = await cache.match(cacheKey) || await cache.match("/");
    if (cached) {
      return cached;
    }
    throw _error;
  }
}

async function networkFirst(request, cacheKey) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request);
    if (response.ok) {
      await cache.put(cacheKey, response.clone());
    }
    return response;
  } catch (_error) {
    const cached = await cache.match(cacheKey);
    if (cached) {
      return cached;
    }
    throw _error;
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  if (cached) {
    return cached;
  }
  const response = await fetch(request);
  if (response.ok) {
    await cache.put(request, response.clone());
  }
  return response;
}
