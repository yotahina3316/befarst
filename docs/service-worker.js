const CACHE_NAME = "befirst-app-v4";
const CORE_ASSETS = ["./", "./css/style.css", "./js/app.js", "./manifest.json", "./images/hero.webp"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // ニュース/スケジュールのデータは常に最新を優先(オフライン時のみキャッシュにフォールバック)
  if (url.pathname.includes("/data/")) {
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
    return;
  }

  // 静的アセットはキャッシュ優先
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});

self.addEventListener("push", (event) => {
  let payload = { title: "BE:FIRST", body: "新着情報があります", url: "./" };
  try {
    payload = event.data.json();
  } catch (e) {
    // データなし/JSON以外の場合はデフォルト値を使う
  }

  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: "./icons/icon-192.png",
      data: { url: payload.url },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || "./";
  event.waitUntil(clients.openWindow(targetUrl));
});
