/* ══════════════════════════════════════════════════════════════════════════
   آزمون ایمنی پیش‌نمایش محلی «حساب من»
   اجرا: node account.test.mjs
   هدف: هیچ پرداخت، احراز هویت سروری، صدور، پیام بیرونی یا مقصد عمومی فعال نباشد؛
   درخواست‌ها و داده‌های نمونه فقط در مرورگر بمانند و brSave تأیید مالک بخواهد.
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
const sessionProbeOnly=p=>p.network.length===1&&p.network[0].path==='/api/account/me'&&p.network[0].method==='GET';
const reply=(status,payload={})=>({ok:status>=200&&status<300,status,json:async()=>payload});
const MEMBER={name:'سارا محمدی',mobile:'09121234567',joined:'نمونهٔ محلی',wallet:1250000,certs:2,msgs:1};
const makeStore=(init={})=>{
  const m=new Map(Object.entries(init));
  return {getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k),
    clear:()=>m.clear(),key:i=>[...m.keys()][i],get length(){return m.size},_m:m};
};
const memberStore=(extra={})=>makeStore(Object.assign({'nora-home-user':JSON.stringify(MEMBER)},extra));
async function load(store,hash='',server=null,hosted=false,fixtureMode=true){
  const errs=[], network=[], hostOrigin='http://nora.test';
  const dom=await JSDOM.fromFile(OPEN,{runScripts:'dangerously',
    resources:{interceptors:[jsdom.requestInterceptor(request=>{
      const requestUrl=new URL(request.url);
      if(hosted&&requestUrl.origin===hostOrigin){
        const localPath=path.join(DIR,decodeURIComponent(requestUrl.pathname.slice(1)));
        if(fs.existsSync(localPath)&&fs.statSync(localPath).isFile()){
          const type=({'.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8',
            '.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg'})[path.extname(localPath)]||'application/octet-stream';
          return new Response(fs.readFileSync(localPath),{status:200,headers:{'content-type':type}});
        }
        return new Response('',{status:404,headers:{'content-type':'text/plain'}});
      }
      return /^https?:/i.test(request.url)?new Response('',{status:200,headers:{'content-type':'text/html;charset=utf-8'}}):undefined;
    })]},
    pretendToBeVisual:true,url:(hosted?hostOrigin+'/account.html':URLF)+hash,
    beforeParse(w){
      w.__NORA_TEST_FIXTURE_MODE__=fixtureMode===true;
      w.scrollTo=()=>{}; if(w.Element&&!w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView=()=>{};
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      if(store) Object.defineProperty(w,'localStorage',{configurable:true,value:store});
      Object.defineProperty(w.document,'cookie',{configurable:true,get:()=> 'nora_account_csrf=account-csrf'});
      w.fetch=(url,options={})=>{
        const path=String(url), method=String(options.method||'GET').toUpperCase();
        network.push({path,method,options});
        if(!server) return Promise.reject(new Error('network disabled in test'));
        if(path==='/api/account/me') return Promise.resolve(server.account?reply(200,server.account):reply(401,{detail:'account_authentication_required'}));
        const registrationsPage=path.match(/^\/api\/account\/registrations\?limit=(\d+)&offset=(\d+)$/);
        if(registrationsPage){
          const all=server.registrations||[],offset=Number(registrationsPage[2]),limit=Number(registrationsPage[1]);
          return Promise.resolve(reply(200,{items:all.slice(offset,offset+limit),total:all.length,has_more:offset+limit<all.length}));
        }
        if(path==='/api/account/notifications?limit=50&offset=0') return Promise.resolve(reply(200,{items:server.notifications||[],has_more:false}));
        if(path==='/api/account/files?limit=50&offset=0') return Promise.resolve(reply(200,{items:server.files||[],has_more:false}));
        const noticeRead=path.match(/^\/api\/account\/notifications\/([0-9a-f-]{36})\/read$/);
        if(noticeRead&&method==='POST') return Promise.resolve(reply(200,{read:true}));
        if(path==='/api/auth/account/logout'&&method==='POST') return Promise.resolve(reply(200,{authenticated:false}));
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
  await wait(40);
  const doc=window.document;
  return {dom,window,doc,errs,network,
    click:sel=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel);
      el.dispatchEvent(new window.MouseEvent('click',{bubbles:true,cancelable:true}))},
    set:(sel,v)=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel); el.value=v;
      el.dispatchEvent(new window.Event('change',{bubbles:true}))},
    txt:sel=>{const el=doc.querySelector(sel); return el?el.textContent.replace(/\s+/g,' ').trim():''},
    all:sel=>[...doc.querySelectorAll(sel)],
    open:()=>[...doc.querySelectorAll('.sheet.on')].map(e=>e.id),
    view:()=>doc.querySelector('#viewBox').textContent.replace(/\s+/g,' ').trim(),
    inView:()=>!doc.querySelector('#viewBox').hidden,
    nav:async k=>{window.location.hash=k?'#'+k:''; await wait(100)}};
}

/* ── ۱) نشان محلی در نمایهٔ چسبان، metadata و مهمان ── */
{
  console.log('\n── نشان محلی و ورود ──');
  const p=await load(memberStore());
  ok(p.errs.length===0,'حساب بی‌خطا بار می‌شود'+(p.errs.length?': '+p.errs[0]:''));
  ok(p.doc.title==='نورا · حساب من','عنوان صفحهٔ حساب');
  ok(p.txt('.hfoot').includes('موسسه فرهنگی، اجتماعی و آموزشی خط‌زندگی'),'نام مؤسسه در مقصد حساب پس از ورود دیده می‌شود');
  ok(p.doc.querySelector('meta[name="robots"]')?.content==='noindex,nofollow,noarchive','صفحه از نمایه‌سازی عمومی کنار گذاشته شده');
  ok(!p.doc.querySelector('.account-preview-banner')&&!p.doc.body.textContent.includes('اتصال حساب بررسی نشد'),
    'نوار اتصال حساب و هشدار تکراری از صفحه برداشته شده‌اند');
  ok(p.doc.querySelector('.tabbar [data-account-nav]')?.getAttribute('href')==='account.html',
    'حسابِ واردشده از ناوبری به صفحهٔ حساب خودش می‌رود');
  ok(p.doc.querySelector('#profBox')&&!p.doc.querySelector('#profBox').hidden,'نمای حساب نمونه پیش چشم است');
  ok(p.txt('#profBox').includes('سارا محمدی'),'نام فقط از نشست نمونهٔ مرورگر نمایش داده می‌شود');
  ok(sessionProbeOnly(p),'بارشدن صفحه نشست حساب را با GET امن بررسی می‌کند');

  const guest=await load(makeStore(),'',{account:null});
  ok(!!guest.doc.querySelector('.guestcard'),'مهمان، کارت ورود آزمایشی می‌بیند');
  ok(guest.doc.querySelector('.tabbar [data-account-nav]')?.getAttribute('href')==='account.html',
    'دکمهٔ ورود/ثبت‌نام مهمان ابتدا نمای امن حساب را باز می‌کند؛ ورود واقعی داخل همان مسیر در دسترس است');
  ok(!guest.doc.body.textContent.includes('اتصال حساب بررسی نشد'),'وضعیت حساب مهمان با هشدار اتصال تکراری نمایش داده نمی‌شود');
  ok(guest.txt('.guestcard').includes('پیامکی فرستاده نمی‌شود')&&guest.txt('.guestcard').includes('احراز هویت سروری نداریم'),
    'متن ورود می‌گوید پیامک یا احراز هویت واقعی وصل نیست');
  ok(!!guest.doc.querySelector('[data-login]'),'کنش ورود از صفحهٔ حساب می‌ماند');
  ok(!!guest.doc.querySelector('a[href="login.html?mode=server&next=account.html%23notifications"]'),
    'برای اعلان‌ها و فایل‌های سروری، روش‌های ورود امن پیوند روشن دارند');
  const accountJs=fs.readFileSync(DIR+'account.js','utf8'), loginJs=fs.readFileSync(DIR+'login.js','utf8');
  ok(accountJs.includes("login.html?mode=server&next=")&&accountJs.includes("'account.html'+(after?'#'+after:'')"),
    'حساب مسیر بازگشت را به login.js می‌دهد');
  ok(/function safeAccountNext\(\)[\s\S]*?URLSearchParams\(location\.search\)[\s\S]*?test\(requested\)[\s\S]*?\?\s*requested\s*:\s*''/.test(loginJs),
    'login.js مقصد بازگشت حساب را به صفحهٔ محلی محدود می‌کند');
  ok(guest.all('a[href^="http:"] ,a[href^="https:"]').length===0,'صفحهٔ مهمان پیوند مقصد بیرونی ندارد');
  ok(sessionProbeOnly(guest),'نمای مهمان فقط وضعیت ورود را می‌سنجد؛ هیچ داده یا تغییری نمی‌فرستد');
}

/* ── نمای تولیدی: بدون نمونه و فقط با دادهٔ API ── */
{
  console.log('\n── جلوگیری از دادهٔ نمونه در حساب تولیدی ──');
  const production=await load(memberStore(),'',{account:null},false,false);
  const visible=production.doc.querySelector('#profBox').textContent+' '+production.doc.body.textContent;
  ok(production.errs.length===0&&!production.doc.querySelector('.guestcard')
    &&!production.doc.querySelector('[data-demo]')&&!visible.includes('سارا محمدی')
    &&!visible.includes('۵۴۳۲۱')&&!visible.includes('پیش‌نمایش محلی'),
    'حساب تولیدی ورود و دادهٔ نمونهٔ محلی را نشان نمی‌دهد');
  ok(production.doc.querySelector('a[href="login.html?mode=server&next=account.html"]')
    &&production.doc.querySelector('.tabbar [data-account-nav]')?.getAttribute('href')==='account.html'
    &&production.doc.querySelector('.help-btn')?.getAttribute('href')==='support.html'
    &&production.txt('#profBox').includes('رویدادهای من')
    &&production.txt('#profBox').includes('ثبت‌نام‌هایت')
    &&production.txt('#profBox').includes('اعلان‌های حساب')
    &&production.txt('#profBox').includes('فایل‌های شخصی')
    &&!production.txt('#profBox').includes('در دسترس نیست'),
    'صفحهٔ معرفی حساب مهمان امکانات واقعی را نشان می‌دهد و ورود امن و پشتیبانی باز است');
  ok(!!production.doc.querySelector('.account-promo-hero')
    &&production.all('.account-promo-feature').length===3
    &&production.all('.account-promo a[href="login.html?mode=server&next=account.html"]').length===2
    &&production.doc.querySelector('.account-promo a[href="events.html"]')
    &&!production.txt('#profBox').includes('نیاز به ورود')
    &&!production.doc.querySelector('.server-account-head'),
    'مهمان به‌جای کارت محدودیت، معرفی امکانات، دعوت به ساخت حساب و مسیر رویدادهای عمومی می‌بیند');
  ok(!production.doc.querySelector('.account-promo-preview a, .account-promo-preview button')
    &&!production.doc.querySelector('.account-promo [data-login], .account-promo [data-demo]')
    &&!production.txt('#profBox').includes('۵۴۳۲۱')
    &&sessionProbeOnly(production),
    'نمای کوچک فقط نام بخش‌هاست؛ معرفی حساب دادهٔ خصوصی نمی‌خواند و OTP یا حساب محلی نمی‌سازد');
  ok(production.all('.account-promo-feature h4').length===3
    &&production.doc.querySelector('.account-promo-preview-brand img')?.getAttribute('alt')===''
    &&production.doc.querySelector('.account-promo-preview-brand img')?.getAttribute('width')==='24'
    &&production.doc.querySelector('.account-promo-preview-brand img')?.getAttribute('height')==='24',
    'کارت‌های امکانات تیتر معنایی دارند و نشان تزئینی نورا بدون جابه‌جایی چیدمان نمایش داده می‌شود');
  ok(!production.doc.body.textContent.includes('نشست'),
    'واژهٔ نشست در متن قابل‌مشاهدهٔ حساب تولیدی وجود ندارد');
  await production.nav('events');
  ok(production.view().includes('نیاز به ورود')&&production.view().includes('برای دیدن ثبت‌نام‌ها وارد حساب شو')
    &&production.view().includes('ورود/ثبت‌نام')
    &&!production.view().includes('کارگاه')&&!production.view().includes('سارا محمدی'),
    'فهرست ثبت‌نام مهمان فقط پس از ورود امن نمایش داده می‌شود و دادهٔ نمونه ندارد');
  await production.nav('pay');
  ok(production.view().includes('پرداخت')&&production.view().includes('API حساب وب')
    &&!production.view().includes('۱۲۵۰۰۰۰'),'پرداخت بدون endpoint هیچ مانده یا فاکتور نمونه‌ای نشان نمی‌دهد');
  await production.nav('book');
  ok(production.view().includes('API حساب وب')&&!production.view().includes('باشگاه نمونه'),
    'باشگاه بدون endpoint در وضعیت روشن و خالی می‌ماند');
  production.dom.window.close();

  const live=await load(memberStore(),'',{
    account:{authenticated:true,account_id:'live-account-1',provider:'phone',role:null,permissions:[],delivery_bot_url:''},
    notifications:[],files:[]
  },false,false);
  ok(!!live.doc.querySelector('.server-account-head')&&live.txt('#profBox').includes('رویدادهای من')
    &&!live.txt('#profBox').includes('در دسترس نیست')
    &&live.doc.querySelector('.tabbar [data-account-nav]')?.getAttribute('href')==='account.html'
    &&!live.doc.body.textContent.includes('سارا محمدی')&&!live.doc.body.textContent.includes('نشست')
    &&!live.doc.querySelector('.account-promo'),
    'حساب واردشده در مسیر خود می‌ماند و فقط دادهٔ سروری، نه پروفایل نمونه یا تبلیغ ورود، می‌بیند');
  live.click('[data-server-account-logout]'); await wait(80);
  ok(!!live.doc.querySelector('.account-promo')&&!live.doc.querySelector('.server-account-head')
    &&live.network.some(call=>call.path==='/api/auth/account/logout'&&call.method==='POST'),
    'خروج حساب، معرفی امکانات مهمان را برمی‌گرداند و دادهٔ خصوصی از صفحه پاک می‌شود');
  live.dom.window.close();

  const offline=await load(makeStore(),'',null,false,false);
  ok(!!offline.doc.querySelector('.account-promo')
    &&offline.doc.querySelector('.account-promo [data-server-account-retry]')
    &&!offline.txt('#profBox').includes('در دسترس نیست')&&sessionProbeOnly(offline),
    'قطع API معرفی امکانات و ورود را پنهان نمی‌کند و دادهٔ نمونه هم نمایش داده نمی‌شود');
  offline.click('.account-promo [data-server-account-retry]'); await wait(50);
  ok(!!offline.doc.querySelector('.account-promo')&&offline.network.length===2
    &&offline.network.every(call=>call.path==='/api/account/me'&&call.method==='GET'),
    'تلاش دوباره از معرفی حساب فقط وضعیت ورود را می‌سنجد و پیام یا درخواست احراز نمی‌فرستد');
  offline.dom.window.close();
}

/* ── فهرست ثبت‌نام‌ها از API حساب وب، نه از دادهٔ محلی ── */
{
  console.log('\n── ثبت‌نام‌های حساب وب ──');
  const registration={id:'00000000-0000-4000-8000-000000000401',form_name:'ثبت‌نام کارگاه',
    event_title:'کارگاه بهار',event_date:'۱۴۰۵/۰۲/۱۱',event_time:'۱۶:۰۰',status:'accepted',
    payment_status:'receipt_submitted',receipt_uploaded:true,ticket_checked_in:false,
    ticket_type:{id:'standard',name:'ورودی عادی'},created_at:'2026-04-30T10:00:00+00:00'};
  const p=await load(memberStore(),'',{
    account:{authenticated:true,account_id:'registration-account-1',provider:'phone',role:null,permissions:[],delivery_bot_url:''},
    registrations:[registration],notifications:[],files:[]
  },false,false);
  await p.nav('events');
  ok(p.network.some(call=>call.path==='/api/account/registrations?limit=50&offset=0')
    &&p.view().includes('کارگاه بهار')&&p.view().includes('رسید ثبت شد')
    &&p.view().includes('ورودی عادی'),
    'فهرست رویداد، وضعیت رسید و نوع بلیت از API حساب وب خوانده می‌شود');
  ok(!p.view().includes('جواب خصوصی')&&!p.view().includes('شمارهٔ همراه'),
    'فهرست حساب پاسخ فرم یا شمارهٔ همراه را افشا نمی‌کند');
  p.click('[data-account-registrations-refresh]'); await wait(20);
  ok(p.network.filter(call=>call.path==='/api/account/registrations?limit=50&offset=0').length===2,
    'بازخوانی فهرست دوباره API حساب را صدا می‌زند');
  p.dom.window.close();
}

/* ── ورود نمایشی قدیمی با شماره و کد ثابت، فقط محلی می‌ماند ── */
{
  console.log('\n── بازگشت ورود آزمایشی حساب ──');
  const store=makeStore(), p=await load(store,'',{account:null});
  p.click('[data-login]'); await wait(20);
  ok(p.open().includes('shAuth')&&!!p.doc.querySelector('#uimob'),
    'دکمهٔ ورود آزمایشی همان ورقهٔ محلی شماره را باز می‌کند');
  ok(!!p.doc.querySelector('#shAuth a[href="login.html?mode=server"]'),
    'ورود امن سروری جدا از مسیر نمایشی و از داخل ورقه در دسترس است');
  p.set('#uimob','09123456789'); p.click('[data-uiphone]'); await wait(20);
  ok(!!p.doc.querySelector('#uicode')&&p.txt('#shAuth').includes('۵۴۳۲۱'),
    'پس از شماره، ورقهٔ قدیمی کد نمایشی ۵۴۳۲۱ را نشان می‌دهد');
  p.set('#uicode','54321'); p.click('[data-uicode]'); await wait(90);
  const localUser=JSON.parse(store.getItem('nora-home-user')||'null');
  ok(localUser&&localUser.name==='سارا محمدی'&&localUser.mobile==='09123456789',
    'تأیید کد نمونه فقط نشست محلی قبلی را برمی‌گرداند');
  ok(!!p.doc.querySelector('.phead')&&!p.doc.querySelector('.guestcard'),
    'پس از ورود آزمایشی، همان نمای عضو پیش‌نمایش دوباره نمایش داده می‌شود');
  ok(p.network.every(call=>call.path==='/api/account/me'),
    'ورود آزمایشی endpoint ورود، OTP یا نقش سروری را صدا نمی‌زند');
  p.dom.window.close();
}

/* ── provider تلفنی و Bale هر دو به همان نشست حساب وصل‌اند ── */
{
  console.log('\n── نشست حساب تلفنی ──');
  const p=await load(memberStore(),'',{
    account:{authenticated:true,account_id:'server-phone-account-1',provider:'phone',role:null,permissions:[],delivery_bot_url:'https://ble.ir/nora_test_bot'},
  });
  ok(!!p.doc.querySelector('.server-account-head'),'نشست حساب OTP به نشست سروری عمومی وصل می‌شود');
  ok(p.txt('.server-account-head').includes('ورود با شمارهٔ موبایل وصل است')
    &&!p.doc.querySelector('.account-preview-banner'),
    'حساب تلفنی در کارت حساب معرفی می‌شود؛ نوار اتصال تکراری وجود ندارد');
  ok(p.network.some(call=>call.path==='/api/account/me'&&call.method==='GET'),
    'حساب تلفنی نیز فقط پس از بررسی نشست سرور نمایش داده می‌شود');
  p.dom.window.close();
}

/* ── نشست سروریِ ورود مدیر با گذرواژه ── */
{
  console.log('\n── نشست حساب مدیر با نام کاربری ──');
  const p=await load(memberStore(),'',{
    account:{authenticated:true,account_id:'server-manager-account-1',provider:'manager-password',
      role:'manager',permissions:['fm_create'],delivery_bot_url:'https://ble.ir/nora_test_bot'},
  });
  ok(!!p.doc.querySelector('.server-account-head')&&p.window.NORA_ACCOUNT_SOURCE==='server',
    'نشست نام‌کاربری مدیر به حساب سروری وصل می‌شود');
  ok(p.txt('.server-account-head').includes('ورود مدیر با نام کاربری وصل است')
    &&!p.doc.querySelector('.account-preview-banner'),
    'provider نام‌کاربری در کارت حساب درست معرفی می‌شود؛ نوار اتصال تکراری وجود ندارد');
  ok(p.network.some(call=>call.path==='/api/account/me'&&call.method==='GET'),
    'حساب مدیر فقط پس از بررسی نشست امن از backend نمایش داده می‌شود');
  p.dom.window.close();
}

/* ── اعلان‌ها و فایل‌های همان حساب از API ── */
{
  console.log('\n── حساب بله، اعلان‌ها و فایل‌های خصوصی ──');
  const noticeId='00000000-0000-4000-8000-000000000201';
  const fileId='00000000-0000-4000-8000-000000000202';
  const p=await load(memberStore(),'',{
    account:{authenticated:true,account_id:'server-account-1',provider:'bale',role:null,permissions:[],delivery_bot_url:'https://ble.ir/nora_test_bot'},
    notifications:[{id:noticeId,bale_user_id:'73424',kind:'receipt_rejected',title:'فیش نیاز به اصلاح دارد',
      body:'تصویر رسید خوانا نیست.',file_refs:[fileId],delivery_status:'delivered',created_at:'2026-09-30T10:00:00+00:00',read:false}],
    files:[{id:fileId,task_id:'00000000-0000-4000-8000-000000000301',file_name:'receipt.pdf',
      content_type:'application/pdf',content_size:12345,created_at:'2026-09-30T10:00:00+00:00'}],
  });
  ok(!!p.doc.querySelector('.server-account-head'),'نشست سروری در صفحهٔ حساب شناسایی می‌شود');
  ok(p.window.NORA_ACCOUNT_SOURCE==='server','فعال‌بودن مقصدهای بیرونی حساب فقط پس از هویت تأییدشدهٔ API است');
  ok(p.network.some(call=>call.path==='/api/account/notifications?limit=50&offset=0')
    &&p.network.some(call=>call.path==='/api/account/files?limit=50&offset=0'),
    'اعلان‌ها و فهرست فایل‌ها از API حساب خوانده می‌شوند');
  ok(p.doc.querySelector('.server-account-head [data-server-data-open="notifications"]')
    &&p.doc.querySelector('.server-account-head [data-server-data-open="files"]'),
    'راه ورود به اعلان‌ها و فایل‌های حساب در صفحه روشن است');
  p.click('[data-server-data-open="notifications"]');
  await wait(20);
  ok(p.inView()&&p.view().includes('فیش نیاز به اصلاح دارد')&&p.view().includes('تصویر رسید خوانا نیست.'),
    'اعلان و متن پیگیری در حساب نشان داده می‌شود');
  const noticeBotLink=p.doc.querySelector('#viewBox .server-notice-files a.local-disabled-link');
  ok(noticeBotLink&&!noticeBotLink.hasAttribute('href')
    &&p.window.NORA_UI.baleStartHref('private_'+fileId)==='https://ble.ir/nora_test_bot?start=private_'+fileId
    &&!p.doc.querySelector('#viewBox a[href^="/api/account/files/"]'),
    'شناسهٔ پیوست به بات ساخته می‌شود؛ پیش‌نمایش file:// مقصد را غیرفعال و وب فایل را پنهان می‌کند');
  p.click('[data-account-notice-read="'+noticeId+'"]');
  await wait(20);
  const mark=p.network.find(call=>call.path==='/api/account/notifications/'+noticeId+'/read');
  ok(mark&&mark.method==='POST'&&mark.options.headers['X-CSRF-Token']==='account-csrf',
    'علامت‌گذاری اعلان با POST و CSRF حساب انجام می‌شود');
  ok(!p.doc.querySelector('[data-account-notice-read]'),'پس از ثبت، اعلان خوانده‌شده نمایش داده می‌شود');
  p.click('[data-serverdata="files"]'); await wait(20);
  ok(p.view().includes('receipt.pdf')&&p.view().includes('دریافت در بات بله'),'فهرست فایل خصوصی با نام و پیوند بات نشان داده می‌شود');
  const accountBotLink=p.doc.querySelector('#viewBox .server-account-file a.local-disabled-link');
  ok(accountBotLink&&!accountBotLink.hasAttribute('href')
    &&p.window.NORA_UI.baleStartHref('private_'+fileId)==='https://ble.ir/nora_test_bot?start=private_'+fileId
    &&!p.doc.querySelector('#viewBox a[download],#viewBox img[src^="/api/account/files/"]'),
    'دریافت فایل حساب به بات ساخته می‌شود؛ file:// آن را نمی‌دهد و مقصد فعال نمی‌کند');
  p.dom.window.close();
}

/* ── ۲) برنامهٔ پرداخت: دو نیمه، بدون کیف پول یا تراکنش ── */
{
  console.log('\n── برنامهٔ پرداخت دونیمه‌ای ──');
  const finance={gates:[{k:'card',on:1},{k:'bale',on:1},{k:'wallet',on:1}],rot:'time',rotHours:24,
    cards:[{id:'sample-card',bank:'بانک نمونه',no:'4111111111111111',name:'دارندهٔ نمونه',cap:5,dailyMax:500000,used:0,usedAmount:0}]};
  const store=memberStore({'nora-finance':JSON.stringify(finance)}), p=await load(store,'#pay');
  ok(p.errs.length===0,'صفحهٔ پرداخت بی‌خطا بالا آمد');
  ok(p.view().includes('نصف الان، نصف تا پنجم ماه بعد')&&p.all('#viewBox .installment-step').length===2,
    'برنامهٔ دو مرحله‌ای و هر دو قسط روشن نمایش داده می‌شوند');
  ok(p.all('#viewBox .installment-card').length===1&&p.txt('#viewBox').includes('کارگاه امداد و نجات')
      &&p.txt('#viewBox').includes('پرداخت‌نشده'),
    'قسط‌های نمونه برای رویداد کاربر نمایش داده می‌شوند');
  ok(p.all('#viewBox .paym').length===6&&p.all('#viewBox .paym[disabled]').length===6
      &&!p.doc.querySelector('#viewBox [data-paym="wallet"]')
      &&p.all('#viewBox [data-paynow],#viewBox [data-method],#viewBox [data-topup]').length===0
      &&p.doc.querySelector('#viewBox .installment-card button[disabled]')?.textContent.includes('پرداخت واقعی'),
    'جزئیات روش‌های غیروالی نمایش دارد، اما کیف پول، شارژ، انتخاب و پرداخت واقعی غیرفعال‌اند');
  ok(p.txt('#viewBox').includes('روش‌های پرداخت')&&p.txt('#viewBox').includes('درگاه بله')
      &&p.txt('#viewBox').includes('کارت‌به‌کارت')&&p.all('#viewBox .ivrow').length===4
      &&p.all('#viewBox .txrow').length===2&&p.txt('#viewBox').includes('سررسید نمونه'),
    'روش‌ها، صورت‌حساب‌ها، سررسید و تراکنش‌های نمونهٔ غیرکیف‌پولی در حساب برگشته‌اند');
  ok(!p.txt('#viewBox').includes('4111 1111 1111 1111')
      &&!p.txt('#viewBox').includes('شارژ کیف پول')
      &&p.txt('#viewBox').includes('شمارهٔ کارت مقصد در این نمونه ارائه نمی‌شود'),
    'صفحه شماره یا شارژ ساختگی نشان نمی‌دهد و نبود کارت مقصد را شفاف می‌گوید');

  const beforePay=store.getItem('nora-home-pay'),beforeReceipts=store.getItem('nora-receipts'),beforeFinance=store.getItem('nora-finance');
  ok(p.window.NORA_UI.finBump('sample-card',100)===null,'API مالی حتی با کارت و gate نمونه، تراکنش نمی‌سازد');
  ok(p.window.NORA_UI.finAddReceipt({id:'fake-receipt'})===false,'API رسید، رسید ثبت نمی‌کند');
  ok(sessionProbeOnly(p)&&p.all('a[href^="http:"] ,a[href^="https:"]').length===0,
    'نمای مالی هیچ درخواست یا پیوند بیرونی ندارد');
  ok(store.getItem('nora-home-pay')===beforePay&&store.getItem('nora-receipts')===beforeReceipts
      &&store.getItem('nora-finance')===beforeFinance,
    'موجودی، تراکنش، تنظیم مالی و رسید دست‌نخورده می‌مانند');
}

/* ── ۳) رویدادهای من: بدون بلیت/QR و بدون درخواست گواهی ── */
{
  console.log('\n── رویدادهای من، رسانه و گواهینامه ──');
  const store=memberStore({'nora-evpack':JSON.stringify({h9:{files:[{kind:'image',title:'تصویر رویداد برای آزمون storage',
    src:'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lfsAAAAASUVORK5CYII='}]}})}), p=await load(store);
  await p.nav('events');
  p.click('[data-vtab="past"]');
  p.click('[data-myev="h1"]');
  ok(p.open().includes('shMyEvent'),'جزئیات رویداد برگزارشده باز می‌شود');
  ok(!p.doc.querySelector('#shMyEvent [data-my-ticket],#shMyEvent [data-ticket],#shMyEvent .tk-qr'),
    'در جزئیات رویداد کارت ورود، QR یا کنترل بلیت وجود ندارد');
  ok(!p.doc.querySelector('#shMyEvent [data-certreq],#shMyEvent [data-cert-askid],#shMyEvent [data-cert-yes]')
    &&!p.txt('#shMyEvent').includes('درخواست گواهینامه'),
    'هیچ دکمه یا مسیر درخواست گواهینامه‌ای در جزئیات نمانده است');
  ok(p.txt('#shMyEvent').includes('هنوز صادر نشده')&&p.txt('#shMyEvent').includes('بعد از صدور'),
    'وضعیت گواهیِ صادرنشده و محل نمایش بعدی روشن است');
  ok(p.txt('#shMyEvent').includes('محتوای آزمایشی')&&!!p.doc.querySelector('#shMyEvent [data-my-media-event="h1"]'),
    'فهرست رسانهٔ رویداد پیوند پخش آزمایشیِ مشخص دارد');
  ok(!!p.doc.querySelector('#shMyEvent [data-event-media-search]')&&!!p.doc.querySelector('#shMyEvent [data-media-filter="video"]'),
    'جست‌وجو و صافی نوع رسانه در جزئیات در دسترس است');
  const mediaSearch=p.doc.querySelector('#shMyEvent [data-event-media-search]');
  mediaSearch.value='پیش‌نمایش'; mediaSearch.dispatchEvent(new p.window.Event('input',{bubbles:true}));
  const demoRow=p.doc.querySelector('#shMyEvent [data-media-title*="پیش‌نمایش"]');
  ok(demoRow&&!demoRow.hidden,'جست‌وجوی فایل، ردیف مطابق را نگه می‌دارد');
  p.click('#shMyEvent [data-media-filter="video"]');
  ok(p.doc.querySelector('#shMyEvent [data-media-kind="audio"]')?.hidden===true,
    'صافی ویدیو، ردیف صوتی را پنهان می‌کند');
  mediaSearch.value=''; mediaSearch.dispatchEvent(new p.window.Event('input',{bubbles:true}));
  p.click('#shMyEvent [data-my-media-event="h1"]');
  ok(p.open().includes('shPlay')&&!!p.doc.querySelector('#shPlay video[controls]'),
    'رسانه با پلیر داخل همان جزئیات باز می‌شود');
  ok(p.doc.querySelector('#shPlay video')?.getAttribute('controlsList')==='nodownload'
    &&!p.doc.querySelector('#shPlay a[download],#shPlay [data-uidl]'),
    'پلیر رسانهٔ رویداد فاقد کنش دانلود است');
  ok(!!p.doc.querySelector('#shPlay [data-uibookmark]')&&!!p.doc.querySelector('#shPlay [data-uichapter]')
    &&!!p.doc.querySelector('#shPlay [data-uirate]')&&!!p.doc.querySelector('#shPlay [data-uiplayerback="shMyEvent"]'),
    'کنترل سرعت، بخش، نشان‌گذاری و بازگشت به جزئیات فراهم است');
  p.click('#shPlay [data-uiplayerback="shMyEvent"]');
  ok(p.open().includes('shMyEvent')&&!p.open().includes('shPlay'),'بازگشت از پلیر همان جزئیات رویداد را برمی‌گرداند');
  ok(!store.getItem('nora-issued-certificates')&&!store.getItem('nora-broadcasts'),
    'بازکردن رسانه یا دیدن وضعیت گواهی چیزی صادر یا ارسال نمی‌کند');

  p.click('#shMyEvent [data-close]');
  p.click('[data-myev="h9"]');
  ok(p.txt('#shMyEvent').includes('هنوز صادر نشده')&&!p.doc.querySelector('#shMyEvent [data-cert-bot]'),
    'پیش از صدور، وضعیت همان رویداد روشن و پیوند گواهی غایب است');
  ok(p.txt('#shMyEvent').includes('دریافت از بات منتشر نشده')
    &&!p.doc.querySelector('#shMyEvent [data-my-media-event="h9"]'),
    'پیوست تصویر در وب نمایش یا دانلود نمی‌شود و تا انتشار بات فقط وضعیت دارد');
  p.click('#shMyEvent [data-close]');
  p.click('[data-myev="h1"]');
  p.click('#shMyEvent [data-my-media-event="h1"]');
  ok(p.open().includes('shPlay')&&!!p.doc.querySelector('#shPlay video[controls]'),
    'آزمون تازه‌سازی با ضبط ویدیوییِ قابل‌پخش رویداد h1 انجام می‌شود');
  const U=p.window.NORA_UI, approval=U.ownerApprovalAdd({type:'cert-batch',status:'pending',eventId:'h1',eventTitle:'کارگاه عکاسی مقدماتی',
    recipients:[{name:'سارا محمدی',mobile:'09121234567',eventId:'h1',eventTitle:'کارگاه عکاسی مقدماتی'}]});
  U.ownerApprovalPatch(approval.id,{status:'approved',approvedBy:'مالک نمونه',approvedById:'owner-test',approvedAt:Date.now()});
  const issued=U.addIssuedCertificate({serial:'OFF-2026-09',eventId:'h1',eventTitle:'کارگاه عکاسی مقدماتی',
    name:'سارا محمدی',mobile:'09121234567',source:'offline-purchase',state:'issued'},approval.id);
  ok(!!issued,'گواهیِ خرید آفلاین پس از تأیید مالک در رجیستری محلی پذیرفته می‌شود');
  let storageSeen=false;
  p.window.addEventListener('storage',e=>{if(e.key===U.ISSUED_CERTS_KEY)storageSeen=true},{once:true});
  p.window.dispatchEvent(new p.window.StorageEvent('storage',{key:U.ISSUED_CERTS_KEY,
    newValue:store.getItem(U.ISSUED_CERTS_KEY)}));
  ok(storageSeen,'StorageEvent هم‌مبدأِ تست به صفحه می‌رسد');
  ok(p.open().includes('shPlay')&&!p.doc.querySelector('#shMyEvent [data-cert-bot]'),
    'تازه‌سازی storage هنگام بازبودن پلیر به‌تعویق می‌افتد');
  let returnEventSeen=false;
  p.window.addEventListener('nora:player-return',e=>{if(e.detail&&e.detail.id==='shMyEvent'&&e.detail.eventId==='h1')returnEventSeen=true},{once:true});
  p.click('#shPlay [data-uiplayerback="shMyEvent"]');
  await wait(20);
  ok(returnEventSeen,'پلیر هنگام بازگشت رویداد اختصاصی را می‌فرستد');
  ok(p.open().includes('shMyEvent')&&!!p.doc.querySelector('#shMyEvent [data-cert-bot]'),
    'با بازگشت از پلیر، گواهی تازه‌شده همان‌جا بی‌درنگ ظاهر می‌شود');
  const botLink=p.doc.querySelector('#shMyEvent [data-cert-bot]');
  ok(p.window.NORA_UI.baleStartHref('mycerts')==='https://ble.ir/lifeline_bot?start=mycerts'
    &&botLink?.classList.contains('local-disabled-link')
    &&p.txt('#shMyEvent').includes('خرید آفلاین')&&p.txt('#shMyEvent').includes('گواهینامه‌های من')
    &&!p.doc.querySelector('#shMyEvent [data-debtpay]'),
    'گواهی آفلاین به شناسهٔ دریافت از بات می‌رسد؛ مقصد بیرونی فقط در پیش‌نمایش محلی بسته است');
  ok(!p.doc.querySelector('#shMyEvent [data-my-cert],#shMyEvent a[download]'),
    'گواهی از داخل ربات دریافت می‌شود، نه با دانلود مستقیم صفحه');
  ok(sessionProbeOnly(p),'پلیر و گواهی هیچ درخواست تازه‌ای جز بررسی نشست نفرستادند');
}

/* ── ۳ب) لینک ورود امن رویداد آنلاین و iframe محدود به سرویس‌های شناخته‌شده ── */
{
  console.log('\n── لینک ورود آنلاین و allowlist ویدیو ──');
  const pack={e1:{files:[
    {kind:'link',title:'پیوند ورود آنلاین',url:'https://meet.google.com/abc-defg-hij'},
    {kind:'video',title:'سرویس ویدیویی ناشناس',url:'https://video.unknown.example/watch/abc'},
    {kind:'video',title:'نمونهٔ YouTube',url:'https://www.youtube.com/watch?v=abcdefghijk'}
  ]}};
  const store=memberStore({'nora-evpack':JSON.stringify(pack)}), p=await load(store,'#events');
  p.click('[data-myev="e1"]');
  await wait(20);
  const join=p.doc.querySelector('#shMyEvent .event-join a');
  ok(!!join&&join.classList.contains('local-disabled-link')&&!join.hasAttribute('href')
    &&join.textContent.includes('ورود به جلسه'),'پیوند ورود آنلاین در پیش‌نمایش file:// ساخته می‌شود، اما فعال نمی‌شود');
  ok(!p.doc.querySelector('#shMyEvent [data-media-title="پیوند ورود آنلاین"]'),
    'پیوند ورود از فهرست رسانه جدا و در بخش مخصوص خودش نمایش داده می‌شود');
  p.click('#shMyEvent [data-my-media-event="e1"]');
  await wait(20);
  const unknownVideo=p.doc.querySelector('#shPlay a.local-disabled-link');
  ok(p.open().includes('shPlay')&&!p.doc.querySelector('#shPlay iframe')
    &&unknownVideo&&!unknownVideo.hasAttribute('href'),
    'نشانی ناشناس embed نمی‌شود و پیش‌نمایش file:// آن را هم غیرفعال می‌کند');
  p.click('#shPlay [data-uiplayerback="shMyEvent"]');
  p.click('#shMyEvent [data-my-media-id="event-e1-1"]');
  ok(!!p.doc.querySelector('#shPlay iframe[src^="https://www.youtube-nocookie.com/embed/abcdefghijk"]'),
    'پیوند YouTube فقط در دامنهٔ embed امن و محدودشده باز می‌شود');
  const U=p.window.NORA_UI;
  ok(!!U.videoEmbedInfo('https://www.youtube.com/watch?v=abcdefghijk')
    &&!!U.videoEmbedInfo('https://www.aparat.com/v/abc123')
    &&!U.videoEmbedInfo('https://video.unknown.example/embed/abc'),
    'YouTube و Aparat شناخته می‌شوند، ولی دامنهٔ ناشناس embed نمی‌شود');
  ok(U.safeHttpsMediaUrl('http://example.com/video.mp4')===''&&U.safeHttpsMediaUrl('https://127.0.0.1/private')===''
    &&U.safeHttpsMediaUrl('https://[fc00::1]/private')===''&&!!U.safeHttpsMediaUrl('https://[2001:4860:4860::8888]/'),
    'پیوند HTTP، IPهای خصوصی/loopback رد و IP عمومی HTTPS پذیرفته می‌شود');
  ok(sessionProbeOnly(p),'پیوند آنلاین و پلیر هیچ درخواست تازه‌ای جز بررسی نشست نفرستادند');
  p.dom.window.close();

  const hosted=await load(memberStore({'nora-evpack':JSON.stringify(pack)}),'#events',{
    account:{authenticated:true,account_id:'server-account-hosted',provider:'bale',role:null,permissions:[],delivery_bot_url:'https://ble.ir/nora_test_bot'},
    notifications:[],files:[]
  },true);
  hosted.click('[data-myev="e1"]'); await wait(20);
  const hostedJoin=hosted.doc.querySelector('#shMyEvent .event-join a');
  ok(hosted.window.location.protocol==='http:'&&hosted.window.NORA_ACCOUNT_SOURCE==='server'
    &&hostedJoin?.getAttribute('href')==='https://meet.google.com/abc-defg-hij'
    &&!hostedJoin.classList.contains('local-disabled-link'),
    'روی میزبانی HTTP، ورود آنلاینِ حساب سروری پیوند فعال دارد');
  hosted.dom.window.close();
}

/* ── ۴) شرط صریح مالک برای ساخت brSave و ساعت محلی ── */
{
  console.log('\n── پخش و زمان ──');
  const store=makeStore(), p=await load(store);
  const U=p.window.NORA_UI, rec={id:'sample-broadcast',ev:'sample',title:'اعلان نمونه'};
  const q=U.ownerApprovalAdd({type:'notification',status:'pending',brRecord:rec});
  ok(U.brSave(rec,q.id)===null&&!store.getItem(U.BR_KEY),'brSave پیش از تأیید صریح مالک چیزی نمی‌سازد');
  U.ownerApprovalPatch(q.id,{status:'approved',notificationStatus:'approved',approvedBy:'مالک نمونه',
    approvedById:'p1',approvedAt:Date.now(),brRecord:rec});
  const saved=U.brSave(rec,q.id);
  ok(!!saved&&saved.ownerApprovalId===q.id&&saved.sent===false,
    'پس از تأیید مالک فقط رکورد محلی با sent=false ساخته می‌شود');
  ok(p.window.NORA_UI.clockState()==='local','وضعیت ساعت صریحاً محلی است');
  ok(sessionProbeOnly(p),'بارگذاری صفحه یا ساعت هیچ سرویس زمانی بیرونی را صدا نمی‌زند');
  const ui=fs.readFileSync(DIR+'ui.js','utf8');
  ok(/no external time service|هیچ سرویس زمانی/i.test(ui),
    'توضیح موتور زمان هم نبود همگام‌سازی بیرونی را ثبت می‌کند');
}

console.log(`\naccount: ${pass} موفق، ${fail} خطا`);
process.exit(fail?1:0);
