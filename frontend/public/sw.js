// Service worker mínimo para que la aplicación se pueda instalar.
// No guarda respuestas de la API ni documentos: los cupos y accesos siempre van a la red.
// Solo atiende la navegación: si no hay conexión, muestra un aviso en vez del error del navegador.

const AVISO_SIN_CONEXION = `<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Sin conexión</title>
  </head>
  <body style="margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#f9fafb;font-family:system-ui,sans-serif;color:#111827">
    <div style="text-align:center;padding:16px">
      <h1 style="font-size:20px">Sin conexión</h1>
      <p style="color:#6b7280">El parqueadero necesita internet para mostrar los cupos. Revisa la conexión y vuelve a intentarlo.</p>
      <button onclick="location.reload()" style="padding:8px 16px;border:0;border-radius:6px;background:#b91c1c;color:#fff">Reintentar</button>
    </div>
  </body>
</html>`;

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (evento) => evento.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (evento) => {
  if (evento.request.mode !== "navigate") return;
  evento.respondWith(
    fetch(evento.request).catch(
      () =>
        new Response(AVISO_SIN_CONEXION, {
          headers: { "Content-Type": "text/html; charset=utf-8" },
        }),
    ),
  );
});
