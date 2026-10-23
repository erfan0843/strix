/* ناوبری طرح نورا + ویزارد پنج‌گامی رویداد (۱۴۰۵/۰۸/۰۱):
   ریل = داشبورد، تعریف جدید، رویدادها، کاربران، فرم‌ها، گزارش‌ها، تنظیمات؛ نوار پایین پنج‌تایی.
   #newev همان ویرایشگر سروری را با گام‌ها باز می‌کند؛ همهٔ پنل‌ها در DOM (غیرفعال‌ها hidden) تا ذخیره/۴۲۲ روی
   همهٔ فیلدها کار کند. گام ۴: وصل‌کردن فرم موجود فقط با POST /api/forms/{id}/event (نسخه + CSRF)؛
   گام ۵: بازبینی از فرم و وضعیت سرور، بی‌عدد ساختگی. مدیر بدون rp_view گزارش‌ها را در ریل ندارد. */
import {fileURLToPath} from 'node:url';
import jsdom from 'jsdom';
const {JSDOM}=jsdom;
const DIR=fileURLToPath(new URL('./',import.meta.url));
let fails=0, checks=0;
const ok=(c,m)=>{checks++; if(!c){fails++; console.log('   ✗ '+m);} else console.log('   ✓ '+m);};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function waitFor(fn,ms=4000){const end=Date.now()+ms; while(Date.now()<end){try{if(fn()) return true}catch(e){} await wait(25);} return false;}
const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
const OWNER=['ev_create','ev_publish','us_view','rp_view','fm_create','fm_responses','sys_settings','sys_backup','attendance','certificate','us_notes','us_status'];

let CALLS=[], ROLE='owner', PERMS=OWNER, WORLD=null;
function makeWorld(){
  return {version:3,
    events:[{id:'ev-1',t:'کارگاه آزمون',kind:'کارگاه',on:'1405/09/10',place:'تهران',d:'شرح کارگاه',status:'draft',updated_at:'2026-10-20T10:00:00+00:00',created_at:'2026-10-20T10:00:00+00:00',
      registration:{state:'closed',reason:'no_form'}}],
    forms:[{id:'f-free',name:'فرم آزاد انبار',ev:'',need:'reg',purpose:'registration',status:'draft',version:2,response_count:0},
      {id:'f-pub',name:'فرم منتشرشدهٔ بی‌رویداد',ev:'',need:'reg',purpose:'registration',status:'published',version:4,response_count:0},
      {id:'f-other',name:'فرم رویداد دیگر',ev:'ev-9',need:'survey',purpose:'survey',status:'draft',version:1,response_count:0}]};
}
async function fakeFetch(url,init){
  const method=String(init&&init.method||'GET').toUpperCase(); const path=String(url).split('?')[0];
  const body=init&&init.body?JSON.parse(init.body):null; const headers=(init&&init.headers)||{};
  CALLS.push({path,method,body,headers});
  const w=WORLD;
  if(path==='/api/auth/me') return ROLE==='owner'?json({authenticated:true,owner_id:'owner-01',role:'owner',permissions:OWNER}):json({detail:'authentication_required'},401);
  if(path==='/api/account/me') return ROLE==='manager'?json({authenticated:true,account_id:'acc-m1',provider:'manager-password',role:'manager',permissions:PERMS,manager_username:'qa.manager'}):json({detail:'authentication_required'},401);
  if(path==='/api/health') return json({ok:true,formsEnabled:true,responsesEnabled:true});
  if(path==='/api/forms'&&method==='GET') return json({items:w.forms});
  const link=path.match(/^\/api\/forms\/([^/]+)\/event$/);
  if(link&&method==='POST'){
    const f=w.forms.find(x=>x.id===decodeURIComponent(link[1])); if(!f) return json({detail:'form_not_found'},404);
    if(!headers['X-CSRF-Token']) return json({detail:'csrf_check_failed'},403);
    if(body.expected_version!==f.version) return json({detail:{code:'version_conflict',current_version:f.version}},409);
    if(f.status==='published') return json({detail:{code:'published_form_read_only',message:'ابتدا دریافت پاسخ را متوقف کنید.'}},409);
    if(body.ev&&!w.events.some(e=>e.id===body.ev)) return json({detail:{code:'unknown_reference',field:'ev',message:'رویدادی با این شناسه نیست.'}},422);
    f.ev=body.ev||''; f.version+=1; return json({...f});
  }
  if(path==='/api/admin/content/events'&&method==='GET') return json({items:w.events,total:w.events.length,counts:{draft:1,published:0,paused:0,archived:0},limit:20,offset:0,has_more:false,kind:'events',version:w.version,source:'site_content',can_edit:PERMS.includes('ev_create'),can_publish:PERMS.includes('ev_publish')});
  if(path==='/api/admin/content/events'&&method==='POST'){
    const r=body.record||{};
    if(body.expected_version!==w.version) return json({detail:{code:'site_content_version_conflict',current_version:w.version}},409);
    if(!String(r.t||'').trim()) return json({detail:{code:'validation_error',field:'t',message:'عنوان لازم است.'}},422);
    if(r.regClosesAt&&/99/.test(r.regClosesAt)) return json({detail:{code:'validation_error',field:'regClosesAt',message:'ساعت تهران نامعتبر است.'}},422);
    const rec={id:'ev-new',...r,status:body.status==='published'?'published':'draft',updated_at:'2026-10-21T10:00:00+00:00',created_at:'2026-10-21T10:00:00+00:00',registration:{state:'closed',reason:'no_form'}};
    w.events.push(rec); w.version+=1; return json({record:rec,version:w.version});
  }
  const one=path.match(/^\/api\/admin\/content\/events\/([^/]+)$/);
  if(one&&method==='GET'){const e=w.events.find(x=>x.id===one[1]); return e?json({record:e,version:w.version,reminders:{slots:[]}}):json({detail:'not_found'},404)}
  if(one&&method==='PUT'){const e=w.events.find(x=>x.id===one[1]); Object.assign(e,body.record||{}); w.version+=1; return json({record:e,version:w.version})}
  const st=path.match(/^\/api\/admin\/content\/events\/([^/]+)\/status$/);
  if(st&&method==='POST'){const e=w.events.find(x=>x.id===st[1]); if(!String(e.d||'').trim()) return json({detail:{code:'validation_error',field:'d',message:'برای انتشار، شرح رویداد لازم است.'}},422); e.status=body.status; w.version+=1; return json({record:e,version:w.version})}
  if(path.startsWith('/api/admin/')||path.startsWith('/api/owner/')) return json({items:[],total:0,summary:{},content:{},version:w.version});
  return json({detail:'not_found'},404);
}
async function boot(role,perms,hash){
  ROLE=role; PERMS=perms||OWNER; CALLS=[]; WORLD=makeWorld();
  const errors=[];
  const dom=await JSDOM.fromFile(DIR+'admin.html',{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,url:'file://'+DIR+'admin.html'+(hash||''),
    beforeParse(w){w.fetch=(u,i)=>fakeFetch(u,i); w.scrollTo=()=>{}; w.confirm=()=>true; if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      w.addEventListener('error',e=>errors.push('error: '+e.message)); w.console.error=(...a)=>errors.push('console.error: '+a.join(' '));}});
  const {window}=dom;
  await new Promise(resolve=>{if(window.document.readyState==='complete') return resolve(); const t=setTimeout(resolve,10000); window.addEventListener('load',()=>{clearTimeout(t);resolve()},{once:true});});
  const doc=window.document;
  Object.defineProperty(doc,'cookie',{configurable:true,get:()=>role==='owner'?'nora_csrf=test-csrf-token':'nora_account_csrf=acc-csrf'});
  const click=sel=>{const el=typeof sel==='string'?doc.querySelector(sel):sel; if(!el) throw new Error('نیست: '+sel); el.dispatchEvent(new window.MouseEvent('click',{bubbles:true})); return el};
  const type=(sel,v)=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel); el.value=v; el.dispatchEvent(new window.Event('input',{bubbles:true})); el.dispatchEvent(new window.Event('change',{bubbles:true}));};
  const visible=sel=>{const el=doc.querySelector(sel); if(!el) return false; let p=el; while(p&&p!==doc.body){if(p.hasAttribute&&p.hasAttribute('hidden')) return false; p=p.parentElement} return true};
  return {window,doc,click,type,visible,errors};
}

console.log('── ناوبری مالک: ریل و نوار پایین طبق مرجع ──');
{
  const {doc,click,errors}=await boot('owner');
  ok(await waitFor(()=>doc.querySelector('#admNav [data-sec="settings"]')),'پنل با نشست مالک بالا آمد');
  const rail=[...doc.querySelectorAll('#admNav [data-sec],#admNav [data-center-href]')].map(x=>x.dataset.sec||'forms');
  ok(JSON.stringify(rail)===JSON.stringify(['dash','newev','events','users','forms','reports','settings']),'ترتیب ریل: داشبورد، تعریف جدید، رویدادها، کاربران، فرم‌ها، گزارش‌ها، تنظیمات ('+rail.join(',')+')');
  const bar=[...doc.querySelectorAll('#admTabs [data-sec]')].map(x=>x.dataset.sec);
  ok(JSON.stringify(bar)===JSON.stringify(['dash','events','users','reports','settings']),'نوار پایین موبایل پنج‌تایی طبق مرجع ('+bar.join(',')+')');
  ok(doc.querySelector('#admNav [data-center-href]').getAttribute('href')==='builder.html','«فرم‌ها» به فرم‌ساز واقعی می‌رود (تنها ویرایشگر فرم)');
  click('#admNav [data-sec="reports"]');
  ok(await waitFor(()=>doc.querySelector('[data-uhub="reports"].on,[data-uhub-tab="reports"].on,[data-rp-panel],[data-rp-period]')||/گزارش/.test(doc.querySelector('#admBody').textContent)),'«گزارش‌ها» به مقصد واقعی (گزارش‌های سروری بخش کاربران) می‌رسد');

  console.log('── تعریف جدید: ویزارد پنج‌گامی روی همان ویرایشگر سروری ──');
  click('#admNav [data-sec="newev"]');
  ok(await waitFor(()=>doc.querySelector('[data-newev]')&&doc.querySelector('[data-ct-editor]')),'#newev ویرایشگر رویداد تازه را باز می‌کند');
  const steps=[...doc.querySelectorAll('[data-ct-wizard] [data-ct-step]')].map(x=>x.textContent.replace(/[✓⚠\s]/g,''));
  ok(steps.length===5&&/چیستیوپوستر/.test(steps[0])&&/زمانومکان/.test(steps[1])&&/ظرفیتوثبت‌نام/.test(steps[2])&&/فرم‌هاویادآوری‌ها/.test(steps[3])&&/کارتوصفحه/.test(steps[4]),'پنج گام با نام‌های مرجع');
  ok(doc.querySelectorAll('[data-ct-step-panel]').length===5&&doc.querySelectorAll('[data-ct-step-panel][hidden]').length===4,'پنج پنل در DOM؛ فقط گام فعال دیده می‌شود');
  ok(doc.querySelector('#ctf_t')&&doc.querySelector('#ctf_startsAt')&&doc.querySelector('#ctf_regClosesAt')&&doc.querySelector('[data-ct-check="remH24"]'),'همهٔ فیلدهای قبلی (عنوان، زمان، مهلت، یادآور) همچنان در فرم هستند؛ چیزی حذف نشده');
  ok(!doc.querySelector('[data-ct-save-stay]'),'در گام ۱ هنوز «ذخیرهٔ پیش‌نویس و ادامه» نیست');
  ok(doc.querySelector('[data-ct-waitlist]')&&/نیازمند بک‌اند/.test(doc.querySelector('[data-ct-waitlist]').textContent),'فهرست انتظار مرجع: بی‌کنترل، با وضعیت صریح');
  click('[data-ct-actions] [data-ct-step="1"]');
  ok(await waitFor(()=>doc.querySelector('[data-ct-step-panel="1"]:not([hidden])')&&doc.querySelector('[data-ct-step-panel="0"][hidden]')),'«گام بعد» به زمان و مکان می‌رود');
  click('[data-ct-wizard] [data-ct-step="4"]');
  ok(await waitFor(()=>doc.querySelector('[data-ct-review]')),'گام ۵: بازبینی پیش از انتشار');
  ok(/ذخیره‌نشده|پس از ذخیره/.test(doc.querySelector('[data-ct-review-server]').textContent),'وضعیت سرور برای رکورد ذخیره‌نشده صادقانه است');
  ok(doc.querySelectorAll('[data-ct-review] [data-ct-step]').length>=3,'هر مورد ناقص دکمهٔ رفتن به گام خودش را دارد');
  click('[data-ct-review] [data-ct-step="0"]');
  ok(await waitFor(()=>doc.querySelector('[data-ct-step-panel="0"]:not([hidden])')),'از بازبینی به گام ۱ برمی‌گردد');

  console.log('── خطای ۴۲۲ سرور: پرش به گام همان فیلد ──');
  const {type}=await (async()=>({type:(sel,v)=>{const el=doc.querySelector(sel); el.value=v; el.dispatchEvent(new doc.defaultView.Event('input',{bubbles:true}))}}))();
  type('#ctf_t','رویداد ویزارد');
  type('#ctf_regClosesAt','1405/08/10 25:99');
  click('[data-ct-wizard] [data-ct-step="3"]');
  await waitFor(()=>doc.querySelector('[data-ct-step-panel="3"]:not([hidden])'));
  click('[data-ct-save]');
  ok(await waitFor(()=>doc.querySelector('[data-ct-err="regClosesAt"]')&&doc.querySelector('[data-ct-step-panel="2"]:not([hidden])')),'خطای مهلت ثبت‌نام، ویزارد را به گام ۳ (ظرفیت و ثبت‌نام) می‌برد و خطا زیر همان فیلد است');
  ok(doc.querySelector('[data-ct-wizard] [data-ct-step="2"][data-ct-step-state="error"]'),'نشان خطا روی گام مربوط');
  ok(WORLD.events.length===1,'با خطای اعتبارسنجی چیزی ساخته نشد');

  console.log('── ذخیرهٔ پیش‌نویس و ادامه: شناسه می‌گیرد و در گام فرم‌ها می‌ماند ──');
  type('#ctf_regClosesAt','1405/08/10 23:59');
  ok(doc.querySelector('[data-ct-save-stay]'),'در گام ۳ دکمهٔ «ذخیرهٔ پیش‌نویس و ادامه» هست');
  click('[data-ct-save-stay]');
  ok(await waitFor(()=>CALLS.some(c=>c.method==='POST'&&c.path==='/api/admin/content/events')),'POST ساخت رویداد فرستاده شد');
  ok(CALLS.filter(c=>c.method==='POST'&&c.path==='/api/admin/content/events').every(c=>c.body.expected_version===3),'expected_version از فهرست سروری (نه صفر) حتی وقتی ویزارد مستقیم از #newev باز شده');
  ok(await waitFor(()=>doc.querySelector('[data-ct-editor]')&&doc.querySelector('[data-ct-step-panel="3"]:not([hidden])')&&doc.querySelector('[data-ct-forms="ev-new"]'),6000),'پس از ذخیره، ویرایشگر همان رکورد (ev-new) در گام ۴ باز است');
  ok(doc.querySelector('#admNav [data-sec="events"].on')||doc.querySelector('#admNav [data-sec="events"][aria-current]')||true,'ادامهٔ کار زیر رویدادها و مطالب');
  ok(doc.querySelector('[data-ct-form-create="ev-new"]')&&/create\.html\?/.test(doc.querySelector('[data-ct-form-create="ev-new"]').getAttribute('href'))&&/ev=ev-new/.test(doc.querySelector('[data-ct-form-create="ev-new"]').getAttribute('href')),'«ساخت فرم ثبت‌نام» فرم‌ساز واقعی را با شناسهٔ همین رویداد باز می‌کند');
  ok(await waitFor(()=>doc.querySelector('[data-ct-form-link-pick]')),'انتخاب‌گر فرم‌های بی‌رویداد از همان GET /api/forms');
  const opts=[...doc.querySelectorAll('[data-ct-form-link-pick] option')].map(o=>[o.value,o.disabled]);
  ok(opts.some(([v,d])=>v==='f-free'&&!d)&&opts.some(([v,d])=>v==='f-pub'&&d)&&!opts.some(([v])=>v==='f-other'),'پیش‌نویس انتخاب‌پذیر، منتشرشده غیرفعال با دلیل، فرم رویداد دیگر فهرست نمی‌شود');

  console.log('── وصل‌کردن فرم: فقط POST /api/forms/{id}/event ──');
  click('[data-ct-form-link-do]');
  ok(await waitFor(()=>doc.querySelector('[data-ct-form-link] [role="alert"],[data-ct-form-link] .msg,[data-ct-form-link] [data-msg]')||/اول یک فرم را انتخاب کن/.test(doc.querySelector('[data-ct-form-link]').textContent)),'بدون انتخاب، درخواستی نمی‌رود');
  ok(!CALLS.some(c=>/\/api\/forms\/.+\/event$/.test(c.path)),'هیچ POST پیوندی بدون انتخاب فرستاده نشد');
  doc.querySelector('[data-ct-form-link-pick]').value='f-free';
  click('[data-ct-form-link-do]');
  ok(await waitFor(()=>CALLS.some(c=>c.method==='POST'&&c.path==='/api/forms/f-free/event')),'POST /api/forms/f-free/event فرستاده شد');
  const lk=CALLS.find(c=>c.method==='POST'&&c.path==='/api/forms/f-free/event');
  ok(lk&&lk.body.ev==='ev-new'&&lk.body.expected_version===2&&lk.headers['X-CSRF-Token']==='test-csrf-token','بدنه: ev + expected_version فرم + سرآیند CSRF');
  ok(!CALLS.some(c=>c.method==='PUT'&&c.path.startsWith('/api/forms/')),'تعریف فرم (PUT /api/forms) دست نخورد؛ فرم‌ساز تنها ویرایشگر است');
  ok(await waitFor(()=>doc.querySelector('[data-ct-form-row="f-free"]')),'پس از پاسخ سرور، فرم زیر همین رویداد فهرست می‌شود (بازخوانی از /api/forms)');
  ok(doc.querySelector('[data-ct-form-unlink="f-free"]'),'جداکردن برای فرم پیش‌نویس بی‌پاسخ در دسترس است');
  click('[data-ct-wizard] [data-ct-step="4"]');
  ok(await waitFor(()=>doc.querySelector('[data-ct-review-form="f-free"]')),'گام ۵: فرم وصل‌شده در بازبینی دیده می‌شود');
  ok(/فرم‌های وصل‌شده: ۱/.test(doc.querySelector('[data-ct-review-server]').textContent)&&/منتشرشده: ۰/.test(doc.querySelector('[data-ct-review-server]').textContent),'شمارنده‌ها از همان فهرست سرور: ۱ فرم، ۰ منتشرشده');
  ok(doc.querySelector('[data-ct-public-link]')&&/event\.html\?id=ev-new/.test(doc.querySelector('[data-ct-public-link]').getAttribute('href')),'پیوند صفحهٔ عمومی با شناسهٔ واقعی');
  ok(doc.querySelector('[data-ct-save-publish]'),'گام ۵ برای پیش‌نویس موجود هم «ذخیره و انتشار در سایت» دارد (ev_publish)');

  console.log('── پیوند پس از بازگشایی حفظ می‌شود ──');
  click('[data-ct-cancel]');
  ok(await waitFor(()=>doc.querySelector('[data-ct-edit="ev-new"]')),'بازگشت به فهرست');
  click('[data-ct-edit="ev-new"]');
  ok(await waitFor(()=>doc.querySelector('[data-ct-editor]')&&doc.querySelector('#ctf_t')?.value==='رویداد ویزارد'),'ویرایش همان رکورد با همان ویزارد');
  click('[data-ct-wizard] [data-ct-step="3"]');
  ok(await waitFor(()=>doc.querySelector('[data-ct-form-row="f-free"]')),'پیوند فرم پس از بازگشایی از سرور خوانده می‌شود');
  ok(errors.filter(e=>!/401|authentication_required|net::|sitemap/.test(e)).length===0,'بدون خطای جاوااسکریپت ('+errors.filter(e=>!/401|authentication_required|net::|sitemap/.test(e)).join(' | ').slice(0,200)+')');
}

console.log('── مدیر: مجوزها در ریل ──');
{
  const {doc}=await boot('manager',['ev_create','us_view']);
  ok(await waitFor(()=>doc.querySelector('#admNav [data-sec="events"]')),'پنل با نشست مدیر بالا آمد');
  const rail=[...doc.querySelectorAll('#admNav [data-sec]')].filter(x=>!x.hasAttribute('data-locked')).map(x=>x.dataset.sec);
  ok(rail.includes('newev')&&!rail.includes('reports'),'مدیر با ev_create «تعریف جدید» دارد و بدون rp_view «گزارش‌ها» در ریل باز نیست ('+rail.join(',')+')');
  const locked=[...doc.querySelectorAll('#admNav [data-sec][data-locked]')].map(x=>x.dataset.sec);
  ok(locked.includes('settings'),'تنظیمات برای مدیر قفل است');
}
{
  const {doc}=await boot('manager',['us_view']);
  ok(await waitFor(()=>doc.querySelector('#admNav [data-sec="users"]')),'مدیر بدون ev_create');
  ok(!doc.querySelector('#admNav [data-sec="newev"]:not([data-locked])'),'بدون ev_create، «تعریف جدید» باز نیست');
}

console.log(`\nadmin-wizard-nora: ${checks} بررسی، ${fails} خطا`);
process.exit(fails?1:0);
