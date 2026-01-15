const CACHE_NAME = 'music-player-v2';
const CACHE_URLS = [
    '/',
    '/static/css/main.css',
    '/static/css/dark-theme.css',
    '/static/js/player.js',
    '/static/js/visualizer.js',
    '/static/js/lyrics.js',
    '/static/assets/default-album.jpg',
    '/manifest.json'
];

// Install event
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(CACHE_URLS))
            .then(() => self.skipWaiting())
    );
});

// Activate event
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch event
self.addEventListener('fetch', event => {
    // Skip non-GET requests
    if (event.request.method !== 'GET') return;
    
    // Skip API requests
    if (event.request.url.includes('/api/')) return;
    
    // Skip audio streaming requests
    if (event.request.url.includes('/stream/')) return;
    
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                // Return cached response if found
                if (response) {
                    return response;
                }
                
                // Clone the request
                const fetchRequest = event.request.clone();
                
                return fetch(fetchRequest).then(response => {
                    // Check if valid response
                    if (!response || response.status !== 200 || response.type !== 'basic') {
                        return response;
                    }
                    
                    // Clone the response
                    const responseToCache = response.clone();
                    
                    // Cache the response
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, responseToCache);
                    });
                    
                    return response;
                });
            })
    );
});

// Background sync for downloads
self.addEventListener('sync', event => {
    if (event.tag === 'download-songs') {
        event.waitUntil(syncDownloads());
    }
});

async function syncDownloads() {
    // Get pending downloads from IndexedDB
    const pendingDownloads = await getPendingDownloads();
    
    for (const download of pendingDownloads) {
        try {
            // Try to download
            await processDownload(download);
            // Remove from pending
            await removePendingDownload(download.id);
        } catch (error) {
            console.error('Background sync download failed:', error);
        }
    }
}

// Message handling
self.addEventListener('message', event => {
    if (event.data.type === 'CACHE_API') {
        cacheAPIResponse(event.data.url, event.data.data);
    } else if (event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

// Cache API responses
async function cacheAPIResponse(url, data) {
    const cache = await caches.open(CACHE_NAME);
    const response = new Response(JSON.stringify(data), {
        headers: { 'Content-Type': 'application/json' }
    });
    await cache.put(url, response);
}

// IndexedDB for pending downloads
function getPendingDownloads() {
    return new Promise((resolve) => {
        const request = indexedDB.open('music-player-db', 1);
        
        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains('downloads')) {
                db.createObjectStore('downloads', { keyPath: 'id' });
            }
        };
        
        request.onsuccess = (event) => {
            const db = event.target.result;
            const transaction = db.transaction(['downloads'], 'readonly');
            const store = transaction.objectStore('downloads');
            const getAllRequest = store.getAll();
            
            getAllRequest.onsuccess = () => {
                resolve(getAllRequest.result || []);
            };
            
            getAllRequest.onerror = () => resolve([]);
        };
        
        request.onerror = () => resolve([]);
    });
}

function removePendingDownload(id) {
    return new Promise((resolve) => {
        const request = indexedDB.open('music-player-db', 1);
        
        request.onsuccess = (event) => {
            const db = event.target.result;
            const transaction = db.transaction(['downloads'], 'readwrite');
            const store = transaction.objectStore('downloads');
            const deleteRequest = store.delete(id);
            
            deleteRequest.onsuccess = () => resolve(true);
            deleteRequest.onerror = () => resolve(false);
        };
        
        request.onerror = () => resolve(false);
    });
}

// Process download in background
async function processDownload(download) {
    // Implementation would depend on your download API
    console.log('Processing background download:', download);
}