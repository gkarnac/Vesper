// Vesper — service worker : permet d'ouvrir l'appli sans réseau (sentier de la WCT).
// L'appli et les histoires : réseau d'abord, copie gardée pour le hors-ligne.
// Images et narrations : copie locale d'abord (mises en cache par « Préparer pour le sentier »).
const CACHE = 'vesper-offline-v1';
const COQUILLE = ['./', './index.html', './manifest.json', './icons/icon-192.png?v=2', './icons/icon-512.png?v=2',
  './story/chapitre0.js', './story/chapitre1.js', './story/chapitre2.js', './story/chapitre3.js',
  './story/chapitre4.js', './story/chapitre5.js', './story/chapitre6.js'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => Promise.all(COQUILLE.map(u => c.add(new Request(u, { cache: 'reload' })).catch(() => {})))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => { e.waitUntil(self.clients.claim()); });

async function reseauDabord(req, cle) {
  const c = await caches.open(CACHE);
  try {
    const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), 5000);
    const r = await fetch(req, { signal: ctl.signal }); clearTimeout(t);
    if (r.ok) c.put(cle || req, r.clone());
    return r;
  } catch (err) {
    const m = await c.match(cle || req, { ignoreSearch: true });
    if (m) return m;
    throw err;
  }
}

// Réponse partielle (206) pour l'audio, à partir de la copie complète en cache.
async function partiel(req, rep) {
  const plage = req.headers.get('range');
  if (!plage) return rep;
  const buf = await rep.arrayBuffer();
  const m = /bytes=(\d*)-(\d*)/.exec(plage) || [];
  const debut = m[1] ? parseInt(m[1], 10) : 0;
  const fin = m[2] ? Math.min(parseInt(m[2], 10), buf.byteLength - 1) : buf.byteLength - 1;
  return new Response(buf.slice(debut, fin + 1), { status: 206, headers: {
    'Content-Type': rep.headers.get('Content-Type') || 'audio/mpeg',
    'Content-Range': 'bytes ' + debut + '-' + fin + '/' + buf.byteLength,
    'Content-Length': String(fin - debut + 1), 'Accept-Ranges': 'bytes' } });
}

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  // Polices Google : copie locale si disponible.
  if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') {
    e.respondWith(caches.open(CACHE).then(async c => (await c.match(req)) || fetch(req).then(r => { c.put(req, r.clone()); return r; })));
    return;
  }
  if (url.origin !== self.location.origin) return;   // API Google Sheet, Ma Vie : jamais interceptés
  if (req.mode === 'navigate') { e.respondWith(reseauDabord(req, './index.html')); return; }
  if (/\/story\/|manifest\.json|\/icons\//.test(url.pathname)) { e.respondWith(reseauDabord(req)); return; }
  if (/\/(images|audio)\//.test(url.pathname)) {
    e.respondWith(caches.open(CACHE).then(async c => {
      const m = await c.match(req.url);
      return m ? partiel(req, m) : fetch(req);
    }));
  }
});
