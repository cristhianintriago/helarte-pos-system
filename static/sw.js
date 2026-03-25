const CACHE_NAME = 'helarte-pos-v2';
const ASSETS_TO_CACHE = [
    '/pedidos',
    '/static/css/theme.css',
    '/static/css/estilos.css',
    '/static/js/app.js',
    '/static/js/pedidos.js',
    '/static/js/index.js',
    '/static/img/logo.png',
    '/static/manifest.json',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
        .then(cache => cache.addAll(ASSETS_TO_CACHE))
        .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.filter(key => key !== CACHE_NAME)
                .map(key => caches.delete(key))
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', event => {
    if (event.request.method !== 'GET') return;

    // Network-first for HTML pages and APIs to always get the freshest catalog if online
    if (event.request.headers.get('accept').includes('text/html') || event.request.url.includes('/api')) {
        event.respondWith(
            fetch(event.request)
            .then(response => {
                const resClone = response.clone();
                caches.open(CACHE_NAME).then(cache => cache.put(event.request, resClone));
                return response;
            })
            .catch(() => caches.match(event.request))
        );
    } else {
        // Cache-first for static CSS, JS, Images for speed
        event.respondWith(
            caches.match(event.request)
            .then(cachedRes => {
                const fetchPromise = fetch(event.request).then(networkRes => {
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, networkRes.clone()));
                    return networkRes;
                }).catch(() => {});
                return cachedRes || fetchPromise;
            })
        );
    }
});
