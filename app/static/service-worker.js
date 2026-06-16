const CACHE_NAME = "process-offline-shell-v9";
const APP_SHELL_URLS = [
  "/manifest.webmanifest",
  "/static/css/app.css?v=20260615-css",
  "/static/css/base.css?v=20260615-css",
  "/static/css/components/buttons.css?v=20260615-css",
  "/static/css/components/forms.css?v=20260615-css",
  "/static/css/components/lists.css?v=20260615-css",
  "/static/css/components/nav.css?v=20260615-css",
  "/static/css/components/status.css?v=20260615-css",
  "/static/css/components/tables.css?v=20260615-css",
  "/static/css/layout.css?v=20260615-css",
  "/static/css/pages/login.css?v=20260615-css",
  "/static/css/pages/planning.css?v=20260615-css",
  "/static/css/print.css?v=20260615-css",
  "/static/css/responsive.css?v=20260615-css",
  "/static/css/tokens.css?v=20260615-css",
  "/static/js/api.js?v=20260612-refactor",
  "/static/js/app.js?v=20260615-shop-orders",
  "/static/js/modules/dates.js?v=20260612-refactor",
  "/static/js/modules/field-definitions.js?v=20260615-fields",
  "/static/js/modules/lists.js?v=20260612-refactor",
  "/static/js/modules/login.js?v=20260612-refactor",
  "/static/js/modules/bootstrap.js?v=20260612-refactor",
  "/static/js/modules/offline/constants.js?v=20260616-offline-split",
  "/static/js/modules/offline/outbox-db.js?v=20260616-offline-split",
  "/static/js/modules/offline/outbox-export.js?v=20260616-offline-split",
  "/static/js/modules/offline/outbox-records.js?v=20260616-offline-split",
  "/static/js/modules/offline/outbox-results.js?v=20260616-offline-split",
  "/static/js/modules/offline/outbox-sync.js?v=20260616-offline-split",
  "/static/js/modules/offline/outbox-upload.js?v=20260616-offline-split",
  "/static/js/modules/offline/server-excel-retry.js?v=20260616-offline-split",
  "/static/js/modules/offline/service-worker-registration.js?v=20260616-offline-split",
  "/static/js/modules/offline/status.js?v=20260616-offline-split",
  "/static/js/modules/pages/operator-entry.js?v=20260616-operator-forms",
  "/static/js/modules/pages/operator.js?v=20260615-shop-orders",
  "/static/js/modules/pages/operator-tour-context.js?v=20260616-operator-forms",
  "/static/js/modules/pages/phone-sync-controls.js?v=20260616-page-controls",
  "/static/js/modules/pages/planning-cycle-report.js?v=20260616-planning-cycle",
  "/static/js/modules/pages/planning-ifs-return.js?v=20260616-planning-ifs",
  "/static/js/modules/pages/planning.js?v=20260615-pages",
  "/static/js/modules/pages/supervisor.js?v=20260615-pages",
  "/static/js/modules/pages/supervisor-sync-controls.js?v=20260616-supervisor-sync",
  "/static/js/modules/pages/utility-auxiliary.js?v=20260616-utility-forms",
  "/static/js/modules/pages/utility.js?v=20260615-pages",
  "/static/js/modules/payloads.js?v=20260612-refactor",
  "/static/js/modules/render/auxiliary-submissions.js?v=20260615-render",
  "/static/js/modules/render/ifs-return.js?v=20260615-render",
  "/static/js/modules/render/process-entries.js?v=20260615-render",
  "/static/js/modules/render/shared.js?v=20260615-render",
  "/static/js/modules/render/status.js?v=20260615-render",
  "/static/js/modules/shop-orders/dropdowns.js?v=20260615-shop-orders",
  "/static/js/modules/shop-orders/machine-section.js?v=20260615-shop-orders",
  "/static/js/modules/shop-orders/materials.js?v=20260615-shop-orders",
  "/static/js/modules/shop-orders/normalization.js?v=20260615-shop-orders",
  "/static/js/modules/shop-orders/state.js?v=20260615-shop-orders",
  "/static/js/modules/shop-orders/status.js?v=20260615-shop-orders",
  "/static/js/modules/temperature.js?v=20260612-refactor",
  "/static/js/modules/tour-context.js?v=20260612-refactor",
  "/static/js/modules/utils.js?v=20260612-refactor",
];

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
    event.respondWith(networkFirst(request, "/"));
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
