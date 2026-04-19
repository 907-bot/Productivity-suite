const CACHE_NAME = 'prod-os-v2';
const assets = [
  './index.html',
  './manifest.json',
  './icon.png',
  './config.js'
];

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('Caching assets');
      return cache.addAll(assets);
    })
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
      );
    })
  );
});

self.addEventListener('fetch', (e) => {
  e.respondWith(
    caches.match(e.request).then((res) => res || fetch(e.request))
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow('/')
  );
});

self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : { title: 'Productivity OS', body: 'New Alert!' };
  const opts = {
    body: data.body,
    icon: 'icon.png',
    badge: 'icon.png',
    vibrate: [100, 50, 100]
  };
  event.waitUntil(self.registration.showNotification(data.title, opts));
});
