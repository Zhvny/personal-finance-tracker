// KILL SWITCH - SERVICE WORKER UNINSTALLER
// This version is designed to clean up any stuck service workers causing fetch errors.

self.addEventListener("install", (e) => {
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  // Unregister self
  self.registration.unregister()
    .then(() => self.clients.matchAll())
    .then((clients) => {
      clients.forEach(client => client.navigate(client.url));
    });

  // Clear all caches
  caches.keys().then((names) => {
    for (let name of names) caches.delete(name);
  });
});

// Do not intercept any fetch requests
self.addEventListener("fetch", (event) => {
  return; 
});
