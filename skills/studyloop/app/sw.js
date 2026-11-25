/* Studyloop service worker. The page and its data always come from the local server; this only keeps
   the shell (fonts, icons, last page) so that, when the server isn't running, the app window shows how
   to start it instead of the browser's error page. */
const CACHE = "studyloop-v3";
const SHELL = ["/fonts/instrument-sans-latin.woff2", "/fonts/instrument-serif-latin.woff2",
  "/fonts/jetbrains-mono-latin.woff2", "/icons/icon-192.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

const OFFLINE = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Studyloop</title><style>
@font-face { font-family: "Instrument Serif"; src: url(/fonts/instrument-serif-latin.woff2) format("woff2"); }
@font-face { font-family: "Instrument Sans"; src: url(/fonts/instrument-sans-latin.woff2) format("woff2"); font-weight: 400 700; }
:root { color-scheme: light dark; --bg: #E9E9E8; --ink: #111111; --ink-2: #474747; --line: rgba(17,17,17,.12); }
@media (prefers-color-scheme: dark) { :root { --bg: #131313; --ink: #E4E4E3; --ink-2: #9B9B9A; --line: rgba(228,228,227,.1); } }
body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: var(--bg); color: var(--ink); font: 16px/1.5 "Instrument Sans", system-ui, sans-serif; }
main { max-width: 30rem; padding: 32px; }
h1 { font: 400 2.5rem/1.1 "Instrument Serif", Georgia, serif; margin: 0 0 12px; }
p { color: var(--ink-2); margin: 0 0 12px; }
code { font: 14px ui-monospace, Menlo, monospace; padding: 2px 6px; border: 1px solid var(--line); border-radius: 6px; color: var(--ink); }
button { margin-top: 12px; font: inherit; font-weight: 500; padding: 8px 16px; border-radius: 10px; border: 1px solid var(--line); background: transparent; color: var(--ink); cursor: pointer; }
</style></head><body><main><h1>Studyloop isn't running</h1>
<p>The app window is there, but the local server behind it isn't. Start it from a terminal with <code>studyloop</code>,
or turn on autostart once with <code>studyloop --autostart on</code>.</p>
<button onclick="location.reload()">Try again</button></main></body></html>`;

self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/fonts/") || url.pathname.startsWith("/icons/")) {
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
      const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); return res;
    })));
    return;
  }
  if (req.mode === "navigate") {
    e.respondWith(fetch(req).catch(() => new Response(OFFLINE, { headers: { "Content-Type": "text/html; charset=utf-8" } })));
  }
});
