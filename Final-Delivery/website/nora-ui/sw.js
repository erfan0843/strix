/* نورا — کش عمومی، بدون پاسخ حساب یا API.
   فقط پوستهٔ عمومیِ بی‌اتصال از پیش ذخیره می‌شود. پاسخ‌های شخصی، ناموفق،
   no-store و وابسته به Cookie وارد کش نمی‌شوند. robots/noindex مجوز نیستند. */
const V='nora-v96';
// offline.html is an explicitly provisioned, static, cookie-free fallback.
// Do not prefetch protected pages, ID-dependent detail routes, or unused JS bundles.
const SHELL=['offline.html','glass.css','nora.css','nora-mark-mini.svg','icons.svg','manifest.webmanifest'];
const MEDIA=/\/(people|posters|fonts)\//;
const PRIVATE_PAGE=/\/(?:account|login|admin|builder|create|form)\.html$/;

function decodedPath(url){
  const pathname=new URL(url,location.origin).pathname;
  try{return decodeURIComponent(pathname)}catch(_){return pathname}
}
function isApi(path){return path==='/api'||path.startsWith('/api/')}
function cacheable(response){
  if(!response||!response.ok)return false;
  if(/(?:^|,)\s*no-store\b/i.test(response.headers.get('Cache-Control')||''))return false;
  if(/(?:^|,)\s*(?:cookie|\*)\s*(?:,|$)/i.test(response.headers.get('Vary')||''))return false;
  if(response.url){
    const path=decodedPath(response.url);
    if(isApi(path)||PRIVATE_PAGE.test(path))return false;
  }
  return true;
}
function networkFirst(event,mayCache){
  let storing=Promise.resolve();
  const network=fetch(event.request).then(response=>{
    if(mayCache&&cacheable(response)){
      const copy=response.clone();
      storing=caches.open(V).then(cache=>cache.put(event.request,copy)).catch(()=>{});
    }
    return response;
  });
  event.waitUntil(network.then(()=>storing).catch(()=>{}));
  return network;
}
self.addEventListener('install',event=>{
  event.waitUntil(caches.open(V).then(cache=>cache.addAll(
    SHELL.map(url=>new Request(url,{cache:'reload'}))
  )).then(()=>self.skipWaiting()));
});
self.addEventListener('message',event=>{
  if(event.data&&event.data.k==='skip'&&self.skipWaiting)self.skipWaiting();
});
self.addEventListener('activate',event=>{
  // Never delete another application's caches on a shared origin.
  event.waitUntil(caches.keys().then(keys=>Promise.all(
    keys.filter(key=>key.startsWith('nora-')&&key!==V).map(key=>caches.delete(key))
  )).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',event=>{
  const request=event.request,url=new URL(request.url),path=decodedPath(request.url);
  if(request.method!=='GET'||url.origin!==location.origin||isApi(path))return;
  if(request.mode==='navigate'){
    const privatePage=PRIVATE_PAGE.test(path);
    event.respondWith(networkFirst(event,!privatePage).catch(async()=>{
      const cached=!privatePage?await caches.open(V).then(cache=>cache.match(request)):null;
      return cached||caches.open(V).then(cache=>cache.match('offline.html'));
    }));
    return;
  }
  if(PRIVATE_PAGE.test(path))return;
  if(MEDIA.test(path)||/\.(woff2|svg|png|jpg|jpeg|webp)$/.test(path)){
    const media=caches.open(V).then(cache=>cache.match(request)).then(
      cached=>cached||networkFirst(event,true)
    );
    event.respondWith(media);
    // Establish a lifetime promise synchronously before an async cache lookup.
    event.waitUntil(media.then(()=>{}).catch(()=>{}));
  }
});
