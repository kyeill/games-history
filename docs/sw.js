
const CACHE="games-history-20260911-161024";
// Only the shell is pre-cached. The data files carry ?v=<build> and are cached
// at runtime, so a rebuild always misses and refetches -- pre-caching them by
// bare name is what served a stale games.json after a rebuild.
const ASSETS=["./","./index.html","./manifest.webmanifest"];
self.addEventListener("install",e=>{
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(
    ASSETS.map(u=>new Request(u,{cache:"reload"})))).catch(()=>{}));
});
self.addEventListener("activate",e=>{
  e.waitUntil(caches.keys().then(ks=>Promise.all(
    ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>
      self.clients.claim()));
});
self.addEventListener("fetch",e=>{
  const u=new URL(e.request.url);
  // tags.json is shared state and ESPN is live: never serve either from cache
  if(u.pathname.endsWith("tags.json")||u.host!==location.host) return;
  if(e.request.mode==="navigate"){
    e.respondWith(fetch(e.request,{cache:"no-store"})
      .catch(()=>caches.match("./index.html")));
    return;
  }
  e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));
});
