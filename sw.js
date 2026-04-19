const CACHE_NAME = 'prod-os-v1';
const assets = ['./index.html', './manifest.json'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(assets)));
});

self.addEventListener('fetch', (e) => {
  e.respondWith(caches.match(e.request).then((res) => res || fetch(e.request)));
});

// Notification Logic
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow('https://907-bot.github.io/Productivity-suite/')
  );
});

self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : { title: 'Productivity OS', body: 'New Alert!' };
  const opts = {
    body: data.body,
    icon: 'productivity_suite_hero_1776616434984.png',
    badge: 'productivity_suite_hero_1776616434984.png',
    vibrate: [100, 50, 100]
  };
  event.waitUntil(self.registration.showNotification(data.title, opts));
});
