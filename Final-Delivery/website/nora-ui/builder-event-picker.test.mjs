/* ════════════════════════════════════════════════════════════════════════════
   آزمون فرم‌ساز: انتخاب رویداد از سرور (ممیزی پنل ۱۴۰۵/۰۸/۰۱ — ردیف D6) و خطای unknown_reference (D3)
   اجرا: node --max-old-space-size=3072 --test builder-event-picker.test.mjs
   معیارها: فهرست فقط از /api/admin/content/events (و در نبود مجوز، /api/public/site-content) — هرگز data.js؛
   جست‌وجوی فارسی + Enter؛ انتخاب → S.evId و payload ذخیره؛ قطع اتصال؛ خطا/تلاش دوباره؛ پنهان در فرم خرید؛
   پاسخ ۴۲۲ unknown_reference(ev) با پیام روشن و بدون کارت «ذخیره شد».
   ════════════════════════════════════════════════════════════════════════════ */
import {fileURLToPath,pathToFileURL} from 'node:url';
import test from 'node:test';
import assert from 'node:assert/strict';
import jsdom from 'jsdom';
const {JSDOM}=jsdom;
const DIR=fileURLToPath(new URL('./',import.meta.url));
const offlineResources={interceptors:[jsdom.requestInterceptor(async request=>{
  if(request.url==='https://tapi.bale.ai/miniapp.js')return new Response('window.Bale = { WebApp: { initData: "" } };',{headers:{'Content-Type':'application/javascript'}});
  if(new URL(request.url).protocol==='https:')return new Response('',{status:403});
  return undefined;
})]};
let checks=0,fails=0;
const ok=(condition,message)=>{checks++;if(!condition){fails++;console.log('   ✗ '+message)}else console.log('   ✓ '+message)};
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function makeStore(){const m=new Map();return{getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k),clear:()=>m.clear(),key:i=>[...m.keys()][i],get length(){return m.size}}}
const EVENTS=[
  {id:'ev-aaa111',t:'کارگاه نجوم شبانه',on:'1405/08/10',status:'published'},
  {id:'ev-bbb222',t:'نشست فلسفهٔ ذهن',on:'1405/08/12',status:'draft'},
  {id:'ev-ccc333',t:'دورهٔ عکاسی',on:'1405/08/20',status:'published'}];
function api({adminStatus=200,adminFailFirst=false,createStatus=201,createDetail=null,role='owner'}={}){
  const calls=[];let record=null,adminHits=0;
  const response=(status,payload)=>({ok:status>=200&&status<300,status,json:async()=>payload});
  const fetch=async(path,init={})=>{
    const method=String(init.method||'GET').toUpperCase();let body=null;
    if(typeof init.body==='string'){try{body=JSON.parse(init.body)}catch(_){body=init.body}}
    calls.push({path,method,body,headers:init.headers||{}});
    if(path==='/api/health')return response(200,{ok:true,formsEnabled:true,responsesEnabled:true,deliveryEnabled:false,formBalePaymentsReady:false});
    if(path==='/api/public/forms/capabilities')return response(200,{version:1,source:'same_application_fastapi',api_configured:true,
      models:['registration','questionnaire','survey','contest','exam','attendance','datacollect','order','election'].map(id=>({id,status:'server',publishable:true,reason:''})),
      field_types:{text:{status:'server',reason:''},fullname:{status:'server',reason:''}},settings:{response_list:{status:'server',page_size_max:100}}});
    if(path==='/api/auth/me')return response(200,{authenticated:true,owner_id:'owner-qa',role});
    if(path==='/api/account/me')return response(200,{authenticated:true,account_id:'acct-qa',role,permissions:role==='owner'?['fm_create']:['fm_create']});
    if(path.startsWith('/api/admin/content/events')){
      adminHits++;
      if(adminFailFirst&&adminHits===1)throw new TypeError('network down');
      if(adminStatus!==200)return response(adminStatus,{detail:adminStatus===403?'permission_denied':'not_authenticated'});
      return response(200,{items:EVENTS.map(x=>({id:x.id,t:x.t,on:x.on,status:x.status})),total:EVENTS.length,version:7});
    }
    if(path==='/api/public/site-content')return response(200,{version:7,content:{events:EVENTS.filter(x=>x.status==='published').map(({id,t,on})=>({id,t,on})),articles:[],people:[]}});
    if(path==='/api/forms'&&method==='POST'){
      if(createStatus!==201)return response(createStatus,{detail:createDetail||{code:'error'}});
      record={id:'form-ev-1',name:body.name,model:body.model,need:body.need,slug:body.slug,ev:body.ev||'',purpose:'registration',recording_id:null,
        fields:body.fields,settings:body.settings,status:'draft',version:1,response_count:0,created_at:'2026-10-23T00:00:00+00:00',updated_at:'2026-10-23T00:00:00+00:00'};
      return response(201,record);
    }
    if(record&&path==='/api/forms/'+record.id+'/readiness')return response(200,{source:'same_server_database',form_id:record.id,version:1,status:'draft',publishable:true,issues:[]});
    if(record&&path==='/api/forms/'+record.id&&method==='GET')return response(200,record);
    return response(404,{detail:'not_found'});
  };
  return {fetch,calls,get record(){return record},get adminHits(){return adminHits}};
}
async function load(query,fetchImpl){
  const errors=[],url=pathToFileURL(DIR+'create.html').href+query;
  const dom=await JSDOM.fromFile(DIR+'create.html',{url,runScripts:'dangerously',resources:offlineResources,pretendToBeVisual:true,beforeParse(w){
    w.scrollTo=()=>{};if(w.Element&&!w.Element.prototype.scrollIntoView)w.Element.prototype.scrollIntoView=()=>{};
    if(!w.matchMedia)w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
    Object.defineProperty(w,'localStorage',{configurable:true,value:makeStore()});
    w.__NORA_TEST_FIXTURE_MODE__=false;
    Object.defineProperty(w.document,'cookie',{configurable:true,get:()=>'nora_csrf=owner-csrf'});
    w.fetch=(...args)=>Promise.resolve().then(()=>fetchImpl(...args));
    w.open=()=>null;
    w.addEventListener('error',e=>errors.push('error: '+(e.message||'')));
    w.console.error=(...args)=>errors.push('console.error: '+args.join(' '));
  }});
  const {window}=dom;
  if(window.document.readyState!=='complete')await new Promise(resolve=>{const t=setTimeout(resolve,5000);window.addEventListener('load',()=>{clearTimeout(t);resolve()},{once:true})});
  await wait(150);
  const doc=window.document;
  return {dom,window,doc,errors,
    q:s=>doc.querySelector(s),
    click:s=>{const el=doc.querySelector(s);if(!el)throw new Error('نیست: '+s);el.dispatchEvent(new window.MouseEvent('click',{bubbles:true,cancelable:true}))},
    type:(s,v)=>{const el=doc.querySelector(s);if(!el)throw new Error('نیست: '+s);el.value=v;el.dispatchEvent(new window.Event('input',{bubbles:true}))},
    key:(s,k)=>{const el=doc.querySelector(s);if(!el)throw new Error('نیست: '+s);el.dispatchEvent(new window.KeyboardEvent('keydown',{key:k,bubbles:true,cancelable:true}))},
    txt:s=>{const el=doc.querySelector(s);return el?el.textContent.replace(/\s+/g,' ').trim():''}};
}
const BACK='&back='+encodeURIComponent('admin.html#forms');
test('فرم‌ساز: انتخاب رویداد از سرور (D6) و خطای unknown_reference (D3)',async()=>{
  console.log('\n— ورود بدون ?ev: فهرست فقط پس از بازکردن و فقط از API مدیریتی —');
  {
    const a=api();const b=await load('?'+BACK.slice(1),a.fetch);
    ok(b.errors.length===0,'بدون خطای JavaScript'+(b.errors.length?': '+b.errors[0]:''));
    const box=b.q('#evPickBox');
    ok(box&&!box.hidden&&b.txt('#evPickBox').includes('هنوز رویدادی وصل نیست')&&!!b.q('[data-ev-pick-toggle]'),'جعبهٔ «رویداد متصل به این فرم» با وضعیت خالی و دکمهٔ انتخاب');
    ok(!a.calls.some(c=>c.path.startsWith('/api/admin/content/events')||c.path==='/api/public/site-content'),'پیش از بازکردن فهرست هیچ درخواستی برای رویدادها نمی‌رود');
    b.click('[data-ev-pick-toggle]');await wait(60);
    ok(a.adminHits===1&&!a.calls.some(c=>c.path==='/api/public/site-content'),'بازکردن فهرست = یک درخواست به /api/admin/content/events (نه site-content عمومی)');
    const options=[...b.doc.querySelectorAll('[data-ev-pick]')];
    ok(options.length===3&&options.map(x=>x.dataset.evPick).join(',')==='ev-aaa111,ev-bbb222,ev-ccc333','سه رویداد سرور (شامل پیش‌نویس) فهرست شدند');
    ok(b.txt('#evPickBox').includes('پیش‌نویس')&&!b.txt('#evPickBox').includes('فقط رویدادهای منتشرشده'),'وضعیت پیش‌نویس کنار رویداد دیده می‌شود؛ یادداشت «فقط منتشرشده» در حالت مدیریتی نیست');
    ok(b.q('#evPickQ')&&b.doc.activeElement===b.q('#evPickQ'),'قلم جست‌وجو پس از بازکردن فوکوس دارد');
    b.type('#evPickQ','فلسفه');await wait(30);
    const filtered=[...b.doc.querySelectorAll('[data-ev-pick]')].map(x=>x.dataset.evPick);
    ok(filtered.join(',')==='ev-bbb222'&&b.doc.activeElement===b.q('#evPickQ'),'جست‌وجوی فارسی فهرست را فیلتر می‌کند و فوکوس در قلم می‌ماند');
    b.type('#evPickQ','كارگاه');await wait(30);
    ok([...b.doc.querySelectorAll('[data-ev-pick]')].map(x=>x.dataset.evPick).join(',')==='ev-aaa111','یکسان‌سازی ك/ک در جست‌وجو');
    b.key('#evPickQ','Enter');await wait(30);
    ok(b.window.eval("S.evId==='ev-aaa111'")&&b.q('[data-ev-pick-current="ev-aaa111"]')&&b.txt('[data-ev-pick-current]').includes('کارگاه نجوم'),'Enter = انتخاب نخستین نتیجه؛ S.evId و نام رویداد نمایش داده شد');
    ok(!b.q('#evPickQ')&&!!b.q('[data-ev-unlink]')&&b.txt('[data-ev-pick-toggle]').includes('تغییر رویداد'),'پس از انتخاب فهرست بسته می‌شود؛ «قطع اتصال» و «تغییر رویداد» در دسترس‌اند');
    /* ذخیره: ev در payload */
    b.window.eval("S.title='فرم ثبت‌نام کارگاه نجوم'");
    b.click('#publish');await wait(400);
    const post=a.calls.find(c=>c.method==='POST'&&c.path==='/api/forms');
    ok(!!post&&post.body.ev==='ev-aaa111'&&post.headers['Idempotency-Key']&&post.headers['X-CSRF-Token']==='owner-csrf','ذخیره: همان شناسهٔ انتخاب‌شده در payload (ev) با کلید یکتا و CSRF');
    ok(b.q('#doneCard').style.display==='block','کارت «ذخیره شد» نمایش داده شد');
    /* قطع اتصال (فرم پیش‌نویس است، قفل نیست) */
    b.click('[data-ev-unlink]');await wait(30);
    ok(b.window.eval("S.evId===''")&&b.txt('#evPickBox').includes('هنوز رویدادی وصل نیست'),'قطع اتصال: S.evId خالی و وضعیت خالی برگشت');
    ok(a.adminHits===1,'فهرست در حافظه می‌ماند؛ درخواست تکراری نمی‌رود');
    b.dom.window.close();
  }
  console.log('\n— بدون مجوز محتوا: بازگشت به رویدادهای منتشرشدهٔ عمومی با یادداشت روشن —');
  {
    const a=api({adminStatus:403,role:'manager'});const b=await load('?'+BACK.slice(1),a.fetch);
    b.click('[data-ev-pick-toggle]');await wait(60);
    ok(a.adminHits===1&&a.calls.some(c=>c.path==='/api/public/site-content'),'۴۰۳ از API مدیریتی → یک درخواست به /api/public/site-content');
    ok([...b.doc.querySelectorAll('[data-ev-pick]')].map(x=>x.dataset.evPick).join(',')==='ev-aaa111,ev-ccc333','فقط رویدادهای منتشرشده فهرست شدند (پیش‌نویس نیست)');
    ok(b.txt('#evPickBox').includes('فقط رویدادهای منتشرشده دیده می‌شوند'),'یادداشت صادقانه دربارهٔ محدودیت مجوز');
    b.dom.window.close();
  }
  console.log('\n— قطع سرور: پیام خطا و تلاش دوباره —');
  {
    const a=api({adminFailFirst:true});const b=await load('?'+BACK.slice(1),a.fetch);
    b.click('[data-ev-pick-toggle]');await wait(60);
    ok(b.txt('#evPickBox').includes('فهرست رویدادها از سرور خوانده نشد')&&!!b.q('[data-ev-pick-retry]')&&!b.q('[data-ev-pick]'),'خطای شبکه: پیام فارسی + دکمهٔ تلاش دوباره، بدون فهرست ساختگی');
    ok(b.errors.length===0,'خطای شبکه به خطای JavaScript تبدیل نشد');
    b.click('[data-ev-pick-retry]');await wait(60);
    ok(a.adminHits===2&&b.doc.querySelectorAll('[data-ev-pick]').length===3&&!b.q('[data-ev-pick-retry]'),'تلاش دوباره: درخواست دوم و فهرست واقعی');
    b.dom.window.close();
  }
  console.log('\n— ورود با ?ev از پروندهٔ رویداد: رویداد از پیش وصل است —');
  {
    const a=api();const b=await load('?ev=ev-ccc333'+BACK,a.fetch);
    ok(b.window.eval("S.evId==='ev-ccc333'")&&!!b.q('[data-ev-pick-current="ev-ccc333"]'),'شناسهٔ رویداد از نشانی خوانده شد و در جعبه دیده می‌شود');
    ok(!a.calls.some(c=>c.path.startsWith('/api/admin/content/events')),'بدون بازکردن فهرست، درخواستی برای فهرست نمی‌رود');
    b.dom.window.close();
  }
  console.log('\n— فرم خرید محتوای ضبط‌شده: انتخاب‌گر رویداد پنهان است —');
  {
    const a=api();const b=await load('?purpose=recording_access&recording=rec-1ce219fb32&ev=ev-1ce219fb32'+BACK,a.fetch);
    const box=b.q('#evPickBox');
    ok(!!box&&box.hidden&&!b.q('[data-ev-pick-toggle]'),'در فرم خرید، جعبهٔ انتخاب رویداد پنهان و بدون دکمه است');
    b.dom.window.close();
  }
  console.log('\n— سرور شناسهٔ ناشناخته را رد می‌کند (۴۲۲ unknown_reference / ev) —');
  {
    const a=api({createStatus:422,createDetail:{code:'unknown_reference',field:'ev',message:'رویدادی با این شناسه در محتوای سایت نیست'}});
    const b=await load('?ev=ev-missing9'+BACK,a.fetch);
    b.window.eval("S.title='فرم با رویداد ناموجود'");
    b.click('#publish');await wait(400);
    const post=a.calls.find(c=>c.method==='POST'&&c.path==='/api/forms');
    ok(!!post&&post.body.ev==='ev-missing9','درخواست ذخیره با همان شناسه رفت (اعتبارسنجی سمت سرور است)');
    ok(b.txt('#ownerApiMessage').includes('رویداد متصل به این فرم روی سرور پیدا نشد')&&b.txt('#ownerApiMessage').includes('ev-missing9'),'پیام فارسی روشن با شناسهٔ ردشده');
    ok(b.q('#doneCard').style.display!=='block','کارت «ذخیره شد» نمایش داده نشد');
    ok(b.window.eval("S.evId==='ev-missing9'&&S.title==='فرم با رویداد ناموجود'"),'ویرایش کاربر پس از خطا حفظ شد');
    b.dom.window.close();
  }
  console.log(`\nجمع: ${checks} بررسی، ${fails} ناموفق`);
  assert.equal(fails,0,'همهٔ بررسی‌های انتخاب‌گر رویداد باید قبول شوند');
});
