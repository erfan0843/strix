/* ══════════════════════════════════════════════════════════════════════════
   آزمون پیوند حساب بله در صفحهٔ «حساب من»
   اجرا: node account-linking.test.mjs

   هدف: جریان پیوند از دید کاربر واقعاً کامل باشد و هیچ موفقیت کاذبی نشان
   داده نشود. هر آزمون رفتار واقعی صفحهٔ تولیدی (بدون دادهٔ نمونه) را با یک
   سرور ساختگی می‌سنجد؛ مدرک اثبات مالکیت همان امضای یک‌بارمصرفِ بله است.
   ══════════════════════════════════════════════════════════════════════════ */
import {fileURLToPath,pathToFileURL} from 'node:url';
import jsdom from 'jsdom';
import fs from 'node:fs';
import path from 'node:path';
const {JSDOM}=jsdom;
const DIR=fileURLToPath(new URL('./',import.meta.url));
const OPEN=DIR+'account.html', URLF=pathToFileURL(OPEN).href;

let pass=0, fail=0;
const ok=(c,m)=>{ if(c){pass++; console.log('   ✓ '+m)} else {fail++; console.log('   ✗ '+m)} };
const wait=(t=70)=>new Promise(r=>setTimeout(r,t));
const reply=(status,payload={})=>({ok:status>=200&&status<300,status,json:async()=>payload});
const dialog=(code)=>({detail:{code}});
const makeStore=(init={})=>{
  const m=new Map(Object.entries(init));
  return {getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k),
    clear:()=>m.clear(),key:i=>[...m.keys()][i],get length(){return m.size},_m:m};
};

const SIGNED_IN={authenticated:true,account_id:'link-account-1',provider:'phone',role:null,permissions:[],delivery_bot_url:''};
const INIT_DATA='auth_date=1700000000&user=%7B%22id%22%3A73421%7D&hash='+'a'.repeat(64);
const LIST_PHONE={identities:[{provider:'phone',linked_at:'2026-04-01T10:00:00+00:00'}],
  available_providers:['phone','bale'],bale_link_available:true};
const LIST_LINKED={identities:[
    {provider:'phone',linked_at:'2026-04-01T10:00:00+00:00'},
    {provider:'bale',linked_at:'2026-04-02T11:30:00+00:00'}],
  available_providers:['phone','bale'],bale_link_available:true};

/**
 * صفحه را در حالت تولیدی با یک سرور ساختگی باز می‌کند.
 *  initData    : امضای بله؛ خالی یعنی صفحه بیرون بله است.
 *  identities  : پاسخ GET /api/account/identities (یا آرایه‌ای برای پاسخ‌های پشت‌سرهم).
 *  linkResult  : {status, body} پاسخ POST پیوند.
 *  unlinkResult: {status, body} پاسخ DELETE.
 */
async function openPage({initData=INIT_DATA, identities=LIST_PHONE, linkResult={status:200,body:{linked:true,provider:'bale',already_linked:false}}, unlinkResult={status:200,body:{linked:false,provider:'bale'}} , extra={}}={}){
  const errs=[], network=[];
  let listCalls=0;
  const listQueue=Array.isArray(identities)?identities.slice():null;
  const dom=await JSDOM.fromFile(OPEN,{runScripts:'dangerously',
    resources:{interceptors:[jsdom.requestInterceptor(request=>{
      const u=new URL(request.url);
      if(u.origin==='http://nora.test'){
        const localPath=path.join(DIR,decodeURIComponent(u.pathname.slice(1)));
        if(fs.existsSync(localPath)&&fs.statSync(localPath).isFile()){
          const type=({'.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8',
            '.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon'})[path.extname(localPath)]||'application/octet-stream';
          return new Response(fs.readFileSync(localPath),{status:200,headers:{'content-type':type}});
        }
        return new Response('',{status:404,headers:{'content-type':'text/plain'}});
      }
      return /^https?:/i.test(request.url)?new Response('',{status:200,headers:{'content-type':'text/html;charset=utf-8'}}):undefined;
    })]},
    pretendToBeVisual:true,url:'http://nora.test/account.html',
    beforeParse(w){
      w.__NORA_TEST_FIXTURE_MODE__=false;
      w.scrollTo=()=>{}; if(w.Element&&!w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView=()=>{};
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      Object.defineProperty(w,'localStorage',{configurable:true,value:makeStore()});
      Object.defineProperty(w.document,'cookie',{configurable:true,get:()=> 'nora_account_csrf=account-csrf'});
      w.Bale={WebApp:{initData}};
      w.fetch=(url,options={})=>{
        const p=String(url), method=String(options.method||'GET').toUpperCase();
        network.push({path:p,method,options});
        if(extra.fetch) { const custom=extra.fetch(p,method,options); if(custom) return custom; }
        if(p==='/api/auth/me') return Promise.resolve(reply(401,{detail:'authentication_required'}));
        if(p==='/api/account/me') return Promise.resolve(reply(200,SIGNED_IN));
        if(p==='/api/account/identities'){
          listCalls++;
          if(extra.identitiesThrows) return Promise.reject(new Error('network down'));
          if(listQueue) return Promise.resolve(reply(200,listQueue.shift()||LIST_PHONE));
          return Promise.resolve(reply(200,identities));
        }
        if(p==='/api/account/identities/bale'&&method==='POST') return Promise.resolve(reply(linkResult.status,linkResult.body));
        if(p==='/api/account/identities/bale'&&method==='DELETE') return Promise.resolve(reply(unlinkResult.status,unlinkResult.body));
        if(p==='/api/account/notifications?limit=50&offset=0') return Promise.resolve(reply(200,{items:[],has_more:false}));
        if(p==='/api/account/files?limit=50&offset=0') return Promise.resolve(reply(200,{items:[],has_more:false}));
        if(p==='/api/auth/account/logout'&&method==='POST') return Promise.resolve(reply(200,{authenticated:false}));
        return Promise.resolve(reply(404,{detail:'not_found'}));
      };
      w.addEventListener('error',e=>errs.push('error: '+(e.message||'')));
      w.console.error=(...a)=>errs.push('console.error: '+a.join(' '));
    }});
  const {window}=dom;
  if(window.document.readyState!=='complete') await new Promise(resolve=>{
    const timer=setTimeout(resolve,4000);
    window.addEventListener('load',()=>{clearTimeout(timer);resolve()},{once:true});
  });
  /* ورود خودکار مینی‌اپ و بارگذاری دادهٔ حساب کمی异步 است */
  await wait(160);
  const doc=window.document;
  const callsTo=(p,m)=>network.filter(n=>n.path===p&&(!m||n.method===m));
  return {dom,window,doc,errs,network,callsTo,listCalls:()=>listCalls,
    click:sel=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel);
      el.dispatchEvent(new window.MouseEvent('click',{bubbles:true,cancelable:true}))},
    has:sel=>!!doc.querySelector(sel),
    txt:sel=>{const el=doc.querySelector(sel); return el?el.textContent.replace(/\s+/g,' ').trim():''},
    prof:()=>doc.querySelector('#profBox').textContent.replace(/\s+/g,' ').trim(),
    toasts:()=>[...doc.querySelectorAll('#toast,.toast,[role=status]')].map(e=>e.textContent.replace(/\s+/g,' ').trim())};
}

/* ── ۱) وضعیت فعلی پیوند از سرور خوانده می‌شود ─────────────────────────── */
{
  console.log('\n── وضعیت پیوند از سرور ──');
  const unlinked=await openPage({initData:'',identities:LIST_PHONE});
  ok(unlinked.callsTo('/api/account/identities','GET').length===1,
    'وضعیت پیوند یک‌بار از سرور خوانده می‌شود، نه حدس‌زده می‌شود');
  ok(unlinked.prof().includes('شمارهٔ موبایل')&&unlinked.prof().includes('وصل است')
    &&unlinked.prof().includes('حساب بله')&&unlinked.prof().includes('وصل نیست'),
    'سطر شماره «وصل است» و سطر بله «وصل نیست» نشان می‌دهد');
  ok(!unlinked.has('[data-identity-link]'),
    'بیرون بله دکمهٔ پیوند نشان داده نمی‌شود؛ چون امضای اثبات مالکیت در دسترس نیست');
  ok(unlinked.prof().includes('از داخل خودِ بله باز شود'),
    'به‌جای دکمهٔ بی‌اثر، راه درست پیوند گفته می‌شود');
  ok(unlinked.errs.length===0,'بیرون بله صفحه بی‌خطا بالا می‌آید');
  unlinked.dom.window.close();

  const linked=await openPage({identities:LIST_LINKED});
  ok(linked.prof().includes('بله وصل است')&&!linked.has('[data-identity-link]'),
    'حساب وصل‌شده نشان «بله وصل است» می‌گیرد و پیوند دوباره پیشنهاد نمی‌شود');
  ok(linked.has('[data-identity-unlink]'),'برای حساب وصل‌شده امکان برداشتن پیوند وجود دارد');
  linked.dom.window.close();
}

/* ── ۲) پیوند موفق داخل بله ─────────────────────────────────────────────── */
{
  console.log('\n── پیوند موفق ──');
  const page=await openPage({identities:[LIST_PHONE,LIST_LINKED]});
  ok(page.has('[data-identity-link]'),'داخل بله با سرور پیکربندی‌شده، دکمهٔ پیوند فعال است');
  page.click('[data-identity-link]'); await wait(120);
  const posts=page.callsTo('/api/account/identities/bale','POST');
  ok(posts.length===1,'پیوند دقیقاً یک درخواست می‌فرستد');
  const body=JSON.parse(posts[0].options.body||'{}');
  ok(body.init_data===INIT_DATA,'مدرک اثبات مالکیت همان امضای یک‌بارمصرفِ بله است');
  ok(posts[0].options.headers['X-CSRF-Token']==='account-csrf',
    'درخواست پیوند توکن CSRF نشست را همراه دارد');
  ok(!('user_id' in body)&&!('account_id' in body)&&Object.keys(body).length===1,
    'هیچ شناسه‌ای از سمت مرورگر فرستاده نمی‌شود؛ فقط امضای بله');
  ok(page.callsTo('/api/account/identities','GET').length===2,
    'پس از پیوند، وضعیت از سرور بازخوانی می‌شود');
  ok(page.prof().includes('حساب بله به حسابت وصل شد')&&page.prof().includes('بله وصل است'),
    'موفقیت تأییدشدهٔ سرور به کاربر نشان داده می‌شود');
  ok(page.has('[data-identity-unlink]')&&!page.has('[data-identity-link]'),
    'پس از پیوند، دکمهٔ پیوند می‌رود و امکان برداشتن پیوند می‌آید');
  ok(page.errs.length===0,'پیوند موفق خطایی در صفحه نمی‌گذارد');
  page.dom.window.close();
}

/* ── ۳) تعارض: حساب بله از قبل به حساب دیگری وصل است ──────────────────── */
{
  console.log('\n── تعارض حساب ──');
  const page=await openPage({identities:LIST_PHONE,
    linkResult:{status:409,body:dialog('bale_identity_already_linked')}});
  page.click('[data-identity-link]'); await wait(120);
  ok(page.callsTo('/api/account/identities/bale','POST').length===1,
    'تلاش پیوند انجام شد');
  ok(page.prof().includes('از قبل به حساب دیگری وصل است'),
    'پیام تعارض به زبان کاربر و با راهنمای اقدام نشان داده می‌شود');
  ok(page.prof().includes('حساب بله')&&page.prof().includes('وصل نیست')
    &&!page.prof().includes('به حسابت وصل شد'),
    'هیچ موفقیت کاذبی نشان داده نمی‌شود؛ وضعیت همچنان «وصل نیست» است');
  ok(page.has('[data-identity-link]'),
    'دکمهٔ پیوند برمی‌گردد تا کاربر بعد از رفع تعارض دوباره تلاش کند');
  page.dom.window.close();
}

/* ── ۴) امضای نامعتبر و درخواست تکراری ────────────────────────────────── */
{
  console.log('\n── امضای نامعتبر و تکرار ──');
  const invalid=await openPage({identities:LIST_PHONE,
    linkResult:{status:401,body:{detail:'invalid_bale_init_data'}}});
  invalid.click('[data-identity-link]'); await wait(120);
  ok(invalid.prof().includes('امضای بله معتبر یا تازه نیست'),
    'امضای نامعتبر پیام روشن می‌گیرد، نه خطای مبهم');
  ok(!invalid.prof().includes('به حسابت وصل شد'),'امضای نامعتبر هرگز «وصل شد» نشان نمی‌دهد');
  invalid.dom.window.close();

  const replay=await openPage({identities:LIST_PHONE,
    linkResult:{status:409,body:dialog('bale_init_data_replayed')}});
  replay.click('[data-identity-link]'); await wait(120);
  ok(replay.prof().includes('قبلاً استفاده شده'),
    'درخواست تکراری پیام «قبلاً استفاده شده» می‌گیرد');
  replay.dom.window.close();

  /* دو کلیک پشت‌سرهم نباید دو بار امضای یک‌بارمصرف را بفرستد */
  const double=await openPage({identities:[LIST_PHONE,LIST_LINKED]});
  double.click('[data-identity-link]');
  double.click('[data-identity-link]');
  await wait(140);
  ok(double.callsTo('/api/account/identities/bale','POST').length===1,
    'کلیک دوباره امضا را دو بار نمی‌فرستد؛ امضای یک‌بارمصرف هدر نمی‌رود');
  double.dom.window.close();
}

/* ── ۵) سرور پیکربندی‌نشده و نشست منقضی ────────────────────────────────── */
{
  console.log('\n── پیکربندی سرور و انقضای نشست ──');
  const off=await openPage({identities:{identities:[{provider:'phone',linked_at:null}],
    available_providers:['phone','bale'],bale_link_available:false}});
  ok(!off.has('[data-identity-link]')&&off.prof().includes('روی این سرور پیکربندی نشده است'),
    'وقتی سرور پیوند بله را غیرفعال کرده، دکمه نشان داده نمی‌شود و دلیلش گفته می‌شود');
  off.dom.window.close();

  /* نشستی که وسط کار منقضی می‌شود: صفحه باید به حالت مهمان برگردد، نه اینکه
     پیام موفقیت نشان دهد یا کاربر پشت خطا بماند. */
  const expired=await openPage({identities:LIST_PHONE,
    linkResult:{status:401,body:{detail:'authentication_required'}}});
  expired.click('[data-identity-link]'); await wait(140);
  ok(expired.callsTo('/api/account/identities/bale','POST').length===1,
    'درخواست پیوند با نشست منقضی فرستاده شد');
  ok(!expired.prof().includes('به حسابت وصل شد'),'نشست منقضی هرگز «وصل شد» نشان نمی‌دهد');
  ok(!expired.has('[data-identity-link]')&&!expired.has('[data-identity-unlink]'),
    'پس از انقضای نشست، کنترل پیوند از صفحه برداشته می‌شود');
  expired.dom.window.close();
}

/* ── ۶) برداشتن پیوند: تأیید لازم، و محافظت از تنها راه ورود ───────────── */
{
  console.log('\n── برداشتن پیوند ──');
  const page=await openPage({identities:[LIST_LINKED,LIST_PHONE]});
  page.click('[data-identity-unlink]'); await wait(60);
  ok(page.callsTo('/api/account/identities/bale','DELETE').length===0
    &&page.has('[data-identity-unlink-confirm]'),
    'برداشتن پیوند بی‌درنگ انجام نمی‌شود؛ اول تأیید می‌خواهد');
  page.click('[data-identity-unlink-cancel]'); await wait(40);
  ok(page.callsTo('/api/account/identities/bale','DELETE').length===0
    &&page.has('[data-identity-unlink]'),
    'انصراف هیچ درخواستی نمی‌فرستد');
  page.click('[data-identity-unlink]'); await wait(40);
  page.click('[data-identity-unlink-confirm]'); await wait(140);
  const deletes=page.callsTo('/api/account/identities/bale','DELETE');
  ok(deletes.length===1&&deletes[0].options.headers['X-CSRF-Token']==='account-csrf',
    'تأیید، برداشتن پیوند را با توکن CSRF می‌فرستد');
  ok(page.prof().includes('پیوند بله برداشته شد')&&page.prof().includes('وصل نیست'),
    'نتیجهٔ برداشتن پیوند نشان داده می‌شود');
  page.dom.window.close();

  /* حساب بی‌شماره: بله تنها راه ورود است */
  const onlyBale=await openPage({identities:{identities:[{provider:'bale',linked_at:null}],
    available_providers:['phone','bale'],bale_link_available:true}});
  ok(!onlyBale.has('[data-identity-unlink]')&&!onlyBale.has('[data-identity-unlink-confirm]')
    &&onlyBale.prof().includes('تنها راه ورود حساب است'),
    'برای حسابی که تنها با بله وارد می‌شود، کنترل برداشتن پیوند نمایش داده نمی‌شود');
  ok(onlyBale.prof().includes('این حساب با شماره ساخته نشده است'),
    'نبود هویت شماره هم صادقانه گفته می‌شود');
  onlyBale.dom.window.close();

  /* سرور در لحظهٔ برداشتن، محافظت آخرین هویت را اعمال می‌کند */
  const refused=await openPage({identities:LIST_LINKED,
    unlinkResult:{status:409,body:dialog('last_identity_cannot_be_removed')}});
  refused.click('[data-identity-unlink]'); await wait(40);
  refused.click('[data-identity-unlink-confirm]'); await wait(140);
  ok(refused.prof().includes('تنها راه ورود حساب است'),
    'رد سرور برای آخرین هویت، با پیام روشن به کاربر گفته می‌شود');
  refused.dom.window.close();
}

/* ── ۷) مهمان و خطای خواندن: هیچ درخواست بی‌جایی نمی‌رود ───────────────── */
{
  console.log('\n── مهمان و خطای خواندن ──');
  const guest=await openPage({extra:{fetch:(p,m)=>p==='/api/account/me'?Promise.resolve(reply(401,{detail:'authentication_required'})):null}});
  ok(guest.callsTo('/api/account/identities','GET').length===0,
    'کاربر مهمان هیچ درخواست پیوندی نمی‌فرستد');
  ok(!guest.has('[data-identity-link]')&&!guest.has('[data-identity-unlink]'),
    'مهمان کنترل پیوند نمی‌بیند');
  guest.dom.window.close();

  /* سرور در دسترس نیست: وضعیت پیوند نامعلوم است. در این حالت نه «وصل نیست» ادعا
     می‌کنیم و نه دکمهٔ پیوند می‌گذاریم؛ فقط خطای روشن و راه تلاش دوباره. */
  const broken=await openPage({extra:{identitiesThrows:true}});
  ok(broken.prof().includes('سرور در دسترس نیست')&&broken.has('[data-identity-retry]'),
    'خطای خواندن وضعیت پیوند، پیام روشن و راه تلاش دوباره می‌گیرد');
  ok(!broken.has('[data-identity-link]'),
    'با نامعلوم‌بودن وضعیت، دکمهٔ پیوند نمایش داده نمی‌شود');
  const before=broken.callsTo('/api/account/identities','GET').length;
  broken.click('[data-identity-retry]'); await wait(120);
  ok(broken.callsTo('/api/account/identities','GET').length===before+1,
    'دکمهٔ تلاش دوباره واقعاً وضعیت را از سرور دوباره می‌خواند');
  broken.dom.window.close();
}

console.log(`\naccount-linking: ${pass} موفق، ${fail} خطا`);
process.exitCode=fail?1:0;
