/* ══════════════════════════════════════════════════════════════════════════
   نورا، کارگر سرویس
   ──────────────────────────────────────────────────────────────────────────
   سیاست روشن، بی‌غافلگیری:
   • صفحه‌ها (ناوبری): شبکه اول؛ اگر اتصال نبود، نسخهٔ کش‌شده و در نهایت
     صفحهٔ «بی‌اتصال». پس کاربر با نسخهٔ کهنه گیر نمی‌کند.
   • تصویر، فونت و پوستر: کش اول (این‌ها کم عوض می‌شوند) با به‌روزرسانی پس‌زمینه.
   • بقیهٔ درخواست‌ها: مستقیم از شبکه.
   ══════════════════════════════════════════════════════════════════════════ */
const V='nora-v30';
const SHELL=['home.html','account.html','login.html','events.html','event.html','support.html','offline.html',
  'admin.html','builder.html',
  'glass.css','nora.css','events.css','account.css','login.css','support.css','admin.css',
  'ui.js','data.js','login.js','support.js','admin.js','manifest.webmanifest'];
const MEDIA=/\/(people|posters|fonts)\//;

self.addEventListener('install',e=>{
  e.waitUntil(caches.open(V).then(c=>c.addAll(SHELL.map(u=>new Request(u,{cache:'reload'})))).then(()=>self.skipWaiting()));
});
/* کارگر نو زودتر بنشیند و کهنه کنار برود */
self.addEventListener('message',e=>{
  if(e.data&&e.data.k==='skip'&&self.skipWaiting) self.skipWaiting();
});
self.addEventListener('activate',e=>{
  e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==V).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',e=>{
  const r=e.request;
  if(r.method!=='GET'||new URL(r.url).origin!==location.origin) return;
  if(r.mode==='navigate'){
    e.respondWith(fetch(r).then(res=>{
      const cp=res.clone(); caches.open(V).then(c=>c.put(r,cp)); return res;
    }).catch(()=>caches.match(r,{ignoreSearch:true}).then(hit=>hit||caches.match('offline.html'))));
    return;
  }
  if(MEDIA.test(new URL(r.url).pathname)||/\.(woff2|svg|png|jpg|jpeg|webp)$/.test(new URL(r.url).pathname)){
    e.respondWith(caches.match(r).then(hit=>hit||fetch(r).then(res=>{
      const cp=res.clone(); caches.open(V).then(c=>c.put(r,cp)); return res;
    })));
  }
});
