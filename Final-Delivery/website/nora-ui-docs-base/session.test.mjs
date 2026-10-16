/* آزمون نشست سرور در حساب من: نشست نامعتبر پاک می‌شود، پیام‌های نخوانده از سرور شمرده می‌شوند.
   اجرا: node session.test.mjs (نیاز به jsdom در node_modules) */
import {JSDOM} from 'jsdom';
const DIR=new URL('.',import.meta.url).pathname;
const wait=t=>new Promise(r=>setTimeout(r,t));
let fail=0; const ok=(c,m)=>{ console.log((c?'   ✓ ':'   ✗ ')+m); if(!c) fail++ };
function mk(seed,respond){
  const store=new Map(); const ls={getItem:k=>store.has(k)?store.get(k):null,setItem:(k,v)=>store.set(k,String(v)),removeItem:k=>store.delete(k)};
  if(seed) store.set('nora-home-user',JSON.stringify(seed));
  return JSDOM.fromFile(DIR+'account.html',{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,url:'file://'+DIR+'account.html',
    beforeParse(w){ w.scrollTo=()=>{}; if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      Object.defineProperty(w,'localStorage',{configurable:true,value:ls});
      w.fetch=async(u)=>{ const s=String(u); if(s.startsWith('/api/')) return respond(s); return {ok:true,status:200,json:async()=>({})}; }}}).then(d=>({dom:d,store}));
}
console.log('── نشست سرور در حساب من ──');
{ const {dom,store}=await mk({name:'x',mobile:'09121234567',server:true,msgs:0},()=>({ok:false,status:401,json:async()=>({})}));
  await wait(800); ok(store.get('nora-home-user')===undefined||store.get('nora-home-user')===null,'۴۰۱ از سرور، نشست مرورگر پاک می‌شود'); dom.window.close(); }
{ const {dom,store}=await mk({name:'x',mobile:'09121234567',server:true,msgs:0},s=>s.includes('notifications')
    ?{ok:true,status:200,json:async()=>({items:[{id:1,read:false},{id:2,read:true},{id:3,read:false}],has_more:false})}
    :{ok:true,status:200,json:async()=>({authenticated:true})});
  await wait(800); ok(JSON.parse(store.get('nora-home-user')).msgs===2,'پیام نخوانده از سرور شمرده می‌شود (۲)'); dom.window.close(); }
{ const {dom,store}=await mk({name:'ساختگی',mobile:'09121234567',wallet:1250000},()=>({ok:false,status:401,json:async()=>({})}));
  await wait(800); ok(store.get('nora-home-user')==null,'نشست ساختگی بدون علامت سرور پاک می‌شود'); dom.window.close(); }
console.log('── نام کاربر پس از ورود و تکمیل پروفایل ──');
{ const {dom,store}=await mk({name:'۰۹۱۲۱۲۳۴۵۶۷',mobile:'09121234567',provider:'phone',server:true,msgs:0},()=>({ok:true,status:200,json:async()=>({authenticated:true})}));
  await wait(800); const txt=dom.window.document.body.textContent;
  ok(!txt.includes('سارا محمدی'),'کاربر واقعی بدون پروفایل، نام نمونه (سارا محمدی) را نمی‌بیند'); dom.window.close(); }
{ const {dom,store}=await mk({name:'۰۹۱۲۱۲۳۴۵۶۷',mobile:'09121234567',provider:'phone',server:true,msgs:0},()=>({ok:true,status:200,json:async()=>({authenticated:true})}));
  store.set('nora-home-profile',JSON.stringify({fullName:'علی رضایی'}));
  await wait(200); dom.window.location.hash=''; await wait(400);
  const txt=dom.window.document.body.textContent;
  ok(txt.includes('علی رضایی'),'نام تکمیل‌شده در پروفایل نمایش داده می‌شود'); dom.window.close(); }
if(fail) { console.log(`session-test: ${fail} خطا`); process.exit(1) }
console.log('session-test: همه قبول');
