/* Service worker generado por generar_app.py — no editar a mano. */
const CACHE = "repaso-clf-c02-202609090348";
const ARCHIVOS = ["./", "./index.html", "./manifest.json", "./icono-192.png", "./icono-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ARCHIVOS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((claves) => Promise.all(claves.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;

  // El HTML se pide siempre a la red: así una versión nueva llega enseguida.
  // La caché queda como respaldo para cuando no hay conexión.
  if (e.request.mode === "navigate") {
    e.respondWith(
      fetch(e.request)
        .then((r) => {
          const copia = r.clone();
          caches.open(CACHE).then((c) => c.put("./index.html", copia));
          return r;
        })
        .catch(() => caches.match("./index.html"))
    );
    return;
  }

  // Iconos y manifiesto: caché primero, que no cambian casi nunca.
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
});
