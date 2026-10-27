/* ناوبری طرح نورا + فرم فشردهٔ رویداد (مرحلهٔ نهایی ۱۴۰۵/۰۸/۰۱):
   ریل = داشبورد، تعریف جدید، رویدادها، کاربران، فرم‌ها، گزارش‌ها، تنظیمات؛ نوار پایین پنج‌تایی.
   #newev همان ویرایشگر سروری را با سه بخش روی یک صفحه باز می‌کند (اطلاعات اصلی / ثبت‌نام و امکانات / مرور و ذخیره)
   و جزئیات زیر <details> با عنوان صریح؛ همهٔ فیلدها در DOM تا ذخیره/۴۲۲/پیش‌نویس روی همه کار کند.
   تاریخ/ساعت: ورودی ناقص بازنویسی نمی‌شود، پایانِ خالی خالی می‌ماند، ارقام فارسی و لاتین. نوع برگزاری فیلدها را عوض می‌کند.
   وصل‌کردن فرم موجود فقط با POST /api/forms/{id}/event (نسخه + CSRF)؛ مرور از فرم و وضعیت سرور، بی‌عدد ساختگی. */
import {fileURLToPath} from 'node:url';
import jsdom from 'jsdom';
const {JSDOM}=jsdom;
const DIR=fileURLToPath(new URL('./',import.meta.url));
let fails=0, checks=0;
const ok=(c,m)=>{checks++; if(!c){fails++; console.log('   ✗ '+m);} else console.log('   ✓ '+m);};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function waitFor(fn,ms=4000){const end=Date.now()+ms; while(Date.now()<end){try{if(fn()) return true}catch(e){} await wait(25);} return false;}
const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
const OWNER=['ev_create','ev_publish','us_view','rp_view','fm_create','fm_responses','sys_settings','sys_backup','attendance','certificate','us_notes','us_status','finance','receipt_approve'];

let CALLS=[], ROLE='owner', PERMS=OWNER, WORLD=null;
function makeWorld(){
  return {version:3,
    events:[{id:'ev-1',t:'کارگاه آزمون',kind:'کارگاه',on:'1405/09/10',place:'تهران',mode:'حضوری',when_bucket:'upcoming',d:'شرح کارگاه',status:'draft',updated_at:'2026-10-20T10:00:00+00:00',created_at:'2026-10-20T10:00:00+00:00',
      registration:{state:'closed',reason:'no_form'}},
      {id:'ev-old',t:'نشست برگزارشده',kind:'نشست',on:'1405/06/10',place:'',mode:'آنلاین',joinUrl:'https://meet.example.org/old',past:true,when_bucket:'past',d:'شرح',status:'published',updated_at:'2026-09-01T10:00:00+00:00',created_at:'2026-09-01T10:00:00+00:00',
      registration:{state:'ended',reason:'past'}}],
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
  if(path==='/api/admin/content/events'&&method==='GET'){const qs=new URLSearchParams(String(url).split('?')[1]||''); const mode=qs.get('mode')||'', when=qs.get('when')||'', status=qs.get('status')||'';
    const items=w.events.filter(e=>(!mode||e.mode===mode)&&(!status||e.status===status)&&(!when||e.when_bucket===when)); const mc={}; w.events.forEach(e=>{if(e.mode) mc[e.mode]=(mc[e.mode]||0)+1});
    return json({items,total:items.length,counts:{draft:w.events.filter(e=>e.status==='draft').length,published:w.events.filter(e=>e.status==='published').length,paused:0,archived:0},when_counts:{today:0,upcoming:w.events.filter(e=>e.when_bucket==='upcoming').length,past:w.events.filter(e=>e.when_bucket==='past').length,undated:0},mode:mode,mode_counts:mc,today:'1405/08/01',limit:20,offset:0,has_more:false,kind:'events',version:w.version,source:'site_content',can_edit:PERMS.includes('ev_create'),can_publish:PERMS.includes('ev_publish')})}
  if(path==='/api/admin/content/events'&&method==='POST'){
    const r=body.record||{};
    if(body.expected_version!==w.version) return json({detail:{code:'site_content_version_conflict',current_version:w.version}},409);
    if(!String(r.t||'').trim()) return json({detail:{code:'validation_error',field:'t',message:'عنوان لازم است.'}},422);
    if(r.regClosesAt&&/99/.test(r.regClosesAt)) return json({detail:{code:'validation_error',field:'regClosesAt',message:'ساعت تهران نامعتبر است.'}},422);
    const rec={id:'ev-new',...r,when_bucket:'upcoming',status:body.status==='published'?'published':'draft',updated_at:'2026-10-21T10:00:00+00:00',created_at:'2026-10-21T10:00:00+00:00',registration:{state:'closed',reason:'no_form'}};
    w.events.push(rec); w.version+=1; return json({record:rec,version:w.version});
  }
  const one=path.match(/^\/api\/admin\/content\/events\/([^/]+)$/);
  if(one&&method==='GET'){const e=w.events.find(x=>x.id===one[1]); return e?json({record:e,version:w.version,reminders:{slots:[]}}):json({detail:'not_found'},404)}
  if(one&&method==='PUT'){const e=w.events.find(x=>x.id===one[1]); if(body.record&&body.record.joinUrl&&!/^https:\/\//.test(body.record.joinUrl)) return json({detail:{code:'invalid_link',field:'joinUrl'}},422); Object.assign(e,body.record||{}); w.version+=1; return json({record:e,version:w.version})}
  const st=path.match(/^\/api\/admin\/content\/events\/([^/]+)\/status$/);
  if(st&&method==='POST'){const e=w.events.find(x=>x.id===st[1]); if(!String(e.d||'').trim()) return json({detail:{code:'validation_error',field:'d',message:'برای انتشار، شرح رویداد لازم است.'}},422); e.status=body.status; w.version+=1; return json({record:e,version:w.version})}
  /* پروندهٔ رویداد: نماهای سروریِ یک رویداد (فرم‌ها از همان w.forms با ev برابر) */
  const ef=path.match(/^\/api\/admin\/events\/([^/]+)\/(overview|registrations|payments)$/);
  if(ef&&method==='GET'){const e=w.events.find(x=>x.id===ef[1]); if(!e) return json({detail:'event_not_found'},404);
    const forms=w.forms.filter(f=>String(f.ev||'')===e.id).map(f=>({id:f.id,name:f.name,model:'registration',need:f.need,type:f.need==='reg'?'registration':f.need,purpose:f.purpose,status:f.status,version:f.version,response_count:f.response_count||0,updated_at:'2026-10-20T10:00:00+00:00',uses_payment:false}));
    const counts={total:0,accepted:0,waitlisted:0,paid:0,pending_payment:0,failed_payment:0,free:0,checked_in:0,companions:0,cap:0,wait:0,remaining:null,full:false,bale_holds:0,source:'form_responses'};
    const can={edit_event:PERMS.includes('ev_create'),publish_event:PERMS.includes('ev_publish'),forms:PERMS.includes('fm_create'),responses:PERMS.includes('fm_responses'),attendance:PERMS.includes('attendance'),finance:ROLE==='owner',receipts:ROLE==='owner',certificates:PERMS.includes('certificate'),export:ROLE==='owner'};
    if(ef[2]==='overview') return json({source:'shared_server_database',event:{...e,public_path:e.status==='published'?'event.html?id='+e.id:''},forms,registration_settings:null,declared:{cap:e.cap||0,price:e.price||0},counts,can});
    if(ef[2]==='registrations') return json({source:'shared_server_database',event_id:e.id,forms:forms.filter(f=>f.type==='registration').map(f=>({id:f.id,name:f.name,status:f.status})),summary:counts,items:[],total:0,limit:50,offset:0,has_more:false,finance_visible:ROLE==='owner',filters:{}});
    return json({source:'form_payments',event_id:e.id,forms:[],totals:{paid_amount:0,paid:0,pending:0,failed:0},items:[],total:0,limit:50,offset:0,has_more:false,filters:{}});
  }
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
  const {doc,click,errors,window}=await boot('owner');
  ok(await waitFor(()=>doc.querySelector('#admNav [data-sec="settings"]')),'پنل با نشست مالک بالا آمد');
  const rail=[...doc.querySelectorAll('#admNav [data-sec],#admNav [data-center-href]')].map(x=>x.dataset.sec||'forms');
  /* بازآرایی منو ۱۴۰۵/۰۸/۰۵ (درخواست کاربر): «کاربران» و «گزارش‌ها» زیر والد «کاربران و گزارش‌ها»؛ «فرم‌ساز» در ریل و نوار پایین */
  ok(JSON.stringify(rail)===JSON.stringify(['dash','newev','events','users','reports','forms','settings']),'ترتیب ریل: داشبورد، تعریف جدید، رویدادها، [کاربران، گزارش‌ها]، فرم‌ساز، تنظیمات ('+rail.join(',')+')');
  const grp=doc.querySelector('#admNav [data-nav-group="people"]');
  ok(grp&&/کاربران و گزارش‌ها/.test(grp.querySelector('.nav-group-head').textContent),'والد «کاربران و گزارش‌ها» در ریل');
  ok(grp&&[...grp.querySelectorAll('[data-sec]')].map(x=>x.dataset.sec).join(',')==='users,reports','هر دو زیرمقصد مستقل زیر همان والد (#users و #reports)');
  const bar=[...doc.querySelectorAll('#admTabs a')].map(x=>x.dataset.sec||'forms');
  ok(JSON.stringify(bar)===JSON.stringify(['dash','events','users','forms','settings']),'نوار پایین موبایل پنج‌تایی: داشبورد، رویدادها، کاربران و گزارش‌ها، فرم‌ساز، تنظیمات ('+bar.join(',')+')');
  ok(doc.querySelector('#admTabs [data-sec="users"]').getAttribute('aria-label')==='کاربران و گزارش‌ها','زبانهٔ موبایل گروه، نام کامل را در aria-label دارد');
  ok(/فرم‌ساز/.test(doc.querySelector('#admNav [data-center-href]').textContent)&&/فرم‌ساز/.test(doc.querySelector('#admTabs [data-center-href]').textContent),'«فرم‌ساز» هم در ریل هم در نوار پایین موبایل دیده می‌شود');
  ok(doc.querySelector('#admNav [data-center-href]').getAttribute('href')==='builder.html','«فرم‌ساز» به مرکز فرم‌های واقعی می‌رود (تنها ویرایشگر فرم)');
  click('#admNav [data-sec="reports"]');
  ok(await waitFor(()=>doc.querySelector('#admNav [data-sec="reports"].on')&&!doc.querySelector('#admNav [data-sec="users"].on')),'زیرمقصد «گزارش‌ها» مستقل باز می‌شود و فعال است');
  ok(doc.querySelector('#admNav [data-nav-group="people"].on')&&doc.querySelector('#admTabs [data-sec="users"].on'),'والد و زبانهٔ موبایل گروه، فعال‌بودن زیرمقصد را نشان می‌دهند');
  click('#admNav [data-sec="users"]');
  ok(await waitFor(()=>doc.querySelector('#admNav [data-sec="users"].on')&&!doc.querySelector('#admNav [data-sec="reports"].on')),'زیرمقصد «کاربران» مستقل باز می‌شود');

  console.log('── تعریف جدید: فرم فشردهٔ سه‌بخشی روی همان ویرایشگر سروری ──');
  click('#admNav [data-sec="newev"]');
  ok(await waitFor(()=>doc.querySelector('[data-newev]')&&doc.querySelector('[data-ct-editor]')),'#newev ویرایشگر رویداد تازه را باز می‌کند');
  const secs=[...doc.querySelectorAll('[data-ct-sec]')].map(x=>x.dataset.ctSec);
  ok(JSON.stringify(secs)===JSON.stringify(['main','reg','review']),'سه بخش روی یک صفحه: اطلاعات اصلی، ثبت‌نام و امکانات، مرور و ذخیره ('+secs.join(',')+')');
  ok(!doc.querySelector('[data-ct-wizard],[data-ct-step-panel]'),'ویزارد اجباری چندصفحه‌ای دیگر نیست');
  const mains=[...doc.querySelectorAll('[data-ct-sec="main"] [data-ct-field]')].map(x=>x.dataset.ctField);
  ok(['t','mode','on','time','endTime','poster'].every(k=>mains.includes(k)),'اطلاعات اصلی: عنوان، نوع برگزاری، تاریخ، ساعت شروع/پایان، پوستر ('+mains.slice(0,8).join(',')+')');
  const more=[...doc.querySelectorAll('details[data-ct-more]')].map(x=>x.dataset.ctMore+':'+(x.open?'باز':'بسته'));
  ok(JSON.stringify(more)===JSON.stringify(['desc:بسته','sched:بسته','extra:بسته']),'سه بلوک «تنظیمات بیشتر» با عنوان صریح و پیش‌فرض بسته ('+more.join(',')+')');
  ok(doc.querySelector('#ctf_d')&&doc.querySelector('#ctf_startsAt')&&doc.querySelector('#ctf_regClosesAt')&&doc.querySelector('[data-ct-check="remH24"]')&&doc.querySelector('[data-ct-parts]')&&doc.querySelector('#ctf_certMin')===null&&doc.querySelector('[data-ct-check="cert"]'),'همهٔ قابلیت‌های قبلی (شرح، زمان دقیق، مهلت، یادآور، جلسه‌ها، گواهی) در DOM هستند؛ چیزی حذف نشده');
  ok(doc.querySelector('[data-ct-waitlist]')&&/نیازمند بک‌اند/.test(doc.querySelector('[data-ct-waitlist]').textContent),'فهرست انتظار مرجع: بی‌کنترل، با وضعیت صریح');
  const foot=[...doc.querySelectorAll('[data-ct-actions] .btn')].map(x=>x.textContent.trim());
  ok(foot.length===4&&/انصراف/.test(foot[0])&&/ذخیرهٔ پیش‌نویس/.test(foot[1])&&/پیش‌نمایش/.test(foot[2])&&/انتشار/.test(foot[3]),'دکمه‌های پایین محدود: انصراف، ذخیرهٔ پیش‌نویس، پیش‌نمایش، انتشار ('+foot.join(' | ')+')');
  ok(doc.querySelector('[data-ct-review-row="t"][data-ct-review-ok="0"]')&&doc.querySelector('[data-ct-review-row="on"][data-ct-review-ok="0"]'),'مرور: عنوان و تاریخ به‌عنوان ناقص علامت خورده‌اند');
  ok(/ذخیره‌نشده|پس از ذخیره/.test(doc.querySelector('[data-ct-review-server]').textContent),'وضعیت سرور برای رکورد ذخیره‌نشده صادقانه است');

  console.log('── نوع برگزاری: فیلدها با حالت عوض می‌شوند ──');
  const type=(sel,v)=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel); el.value=v; el.dispatchEvent(new window.Event('input',{bubbles:true}))};
  const blur=sel=>doc.querySelector(sel).dispatchEvent(new window.Event('focusout',{bubbles:true}));
  ok(doc.querySelector('#ctf_mode')&&doc.querySelector('#ctf_place')&&!doc.querySelector('#ctf_joinUrl'),'بدون انتخاب نوع: فقط مکان؛ پیوند با انتخاب آنلاین/ترکیبی می‌آید');
  type('#ctf_mode','آنلاین');
  ok(await waitFor(()=>doc.querySelector('[data-ct-where="online"]')),'آنلاین انتخاب شد');
  ok(!doc.querySelector('#ctf_place')&&doc.querySelector('#ctf_joinUrl'),'آنلاین: فقط پیوند ورود');
  type('#ctf_joinUrl','https://meet.example.org/room');
  type('#ctf_mode','حضوری');
  ok(await waitFor(()=>doc.querySelector('[data-ct-where="onsite"]'))&&doc.querySelector('#ctf_place')&&!doc.querySelector('#ctf_joinUrl'),'حضوری: فقط مکان');
  type('#ctf_place','سالن اصلی');
  type('#ctf_mode','ترکیبی');
  ok(await waitFor(()=>doc.querySelector('[data-ct-where="hybrid"]'))&&doc.querySelector('#ctf_place')?.value==='سالن اصلی'&&doc.querySelector('#ctf_joinUrl')?.value==='https://meet.example.org/room','ترکیبی: مکان و پیوند هر دو؛ متن تایپ‌شده با جابه‌جایی حالت گم نشده');

  console.log('── تاریخ و ساعت: ورودی ناقص دست نمی‌خورد، پایانِ خالی خالی می‌ماند ──');
  type('#ctf_on','1405/0');
  ok(doc.querySelector('#ctf_on').value==='1405/0','تاریخ ناقص وسط تایپ بازنویسی نمی‌شود');
  blur('#ctf_on');
  ok(doc.querySelector('#ctf_on').value==='1405/0','تاریخ ناقص با ترک قلم هم قفل/بازنویسی نمی‌شود');
  type('#ctf_on','۱۴۰۵۰۸۲۰');
  ok(doc.querySelector('#ctf_on').value==='1405/08/20','هشت رقم فارسی کامل → ۱۴۰۵/۰۸/۲۰ (جداکننده خودکار برای صفحه‌کلید عددی)');
  ok(/۱۴۰۵\/۰۸\/۲۰/.test(doc.querySelector('[data-ct-weekday="on"]').textContent)&&/آبان/.test(doc.querySelector('[data-ct-weekday="on"]').textContent),'راهنمای روز هفته با قالب فارسی ۱۴۰۵/۰۸/۲۰');
  type('#ctf_on','1405/8/5'); blur('#ctf_on');
  ok(doc.querySelector('#ctf_on').value==='1405/08/05','تاریخ کامل بدون صفر با ترک قلم صفرپُر می‌شود');
  type('#ctf_time','9');
  ok(doc.querySelector('#ctf_time').value==='9','یک رقم ساعت دست‌نخورده');
  blur('#ctf_time');
  ok(doc.querySelector('#ctf_time').value==='9','یک رقم ساعت حتی با ترک قلم بازنویسی نمی‌شود (ابهام)');
  type('#ctf_time','۱۸۰۰');
  ok(doc.querySelector('#ctf_time').value==='18:00','چهار رقم فارسی کامل → ۱۸:۰۰');
  ok(doc.querySelector('#ctf_startsAt').value==='1405/08/05 18:00','شروع دقیق از تاریخ + ساعت شروع پر شد');
  ok(doc.querySelector('#ctf_endsAt').value===''&&doc.querySelector('#ctf_endTime').value==='','پایانِ خالی هرگز خودکار پر نمی‌شود');
  type('#ctf_endTime','1');
  ok(doc.querySelector('#ctf_endTime').value==='1'&&doc.querySelector('#ctf_endsAt').value==='','ساعت پایان ناقص: نه بازنویسی، نه همگام‌سازی');
  type('#ctf_endTime','2030');
  ok(doc.querySelector('#ctf_endTime').value==='20:30'&&doc.querySelector('#ctf_endsAt').value==='1405/08/05 20:30','ساعت پایان کامل → پایان دقیق همان روز');
  type('#ctf_on','1405/08/12');
  ok(doc.querySelector('#ctf_startsAt').value==='1405/08/12 18:00'&&doc.querySelector('#ctf_endsAt').value==='1405/08/12 20:30'&&doc.querySelector('#ctf_endTime').value==='20:30','تغییر تاریخ، شروع و پایانِ هم‌روز را با حفظ ساعت جابه‌جا می‌کند');
  type('#ctf_endTime','');
  ok(doc.querySelector('#ctf_endsAt').value===''&&doc.querySelector('#ctf_endTime').value==='','پاک‌کردن ساعت پایان، پایان دقیق را خالی می‌کند');
  type('#ctf_endTime','1700');
  ok(await waitFor(()=>doc.querySelector('[data-ct-review-warns]')&&/پایان پیش از شروع/.test(doc.querySelector('[data-ct-review-warns]').textContent)),'مرور: هشدار «پایان پیش از شروع» از همین فرم');
  type('#ctf_endTime','');
  ok(await waitFor(()=>!doc.querySelector('[data-ct-review-warns]')||!/پایان پیش از شروع/.test(doc.querySelector('[data-ct-review-warns]').textContent)),'با خالی‌شدن پایان، خطای ترتیب نمی‌ماند');

  console.log('── تقویم: ماه/سال، امروز، پاک‌کردن، Escape ──');
  click('[data-ctdp="on"]');
  ok(await waitFor(()=>doc.querySelector('[data-ctdp-box="on"]')),'تقویم زیر فیلد تاریخ باز شد');
  ok(doc.querySelector('[data-ctdp-set="m"]')&&doc.querySelector('[data-ctdp-set="y"]')&&doc.querySelector('[data-ctdp-today]')&&doc.querySelector('[data-ctdp-clear]')&&doc.querySelector('[data-ctdp-mv="-1"]'),'انتخاب ماه و سال، ماه قبل/بعد، امروز، پاک‌کردن');
  ok(/آبان ۱۴۰۵/.test(doc.querySelector('[data-ctdp-box="on"] .dphead b').textContent),'ماه فعلیِ تقویم از مقدار فیلد');
  const mSel=doc.querySelector('[data-ctdp-set="m"]'); mSel.value='10'; mSel.dispatchEvent(new window.Event('change',{bubbles:true}));
  ok(await waitFor(()=>/دی ۱۴۰۵/.test(doc.querySelector('[data-ctdp-box="on"] .dphead b').textContent)),'انتخاب ماه از فهرست');
  click('[data-ctdp-box="on"] [data-ctdp-day="3"]');
  ok(await waitFor(()=>doc.querySelector('#ctf_on').value==='1405/10/03'),'انتخاب روز از تقویم: ۱۴۰۵/۱۰/۰۳');
  ok(doc.querySelector('#ctf_startsAt').value==='1405/10/03 18:00','شروع دقیق همراه آمد');
  click('[data-ctdp="on"]'); await waitFor(()=>doc.querySelector('[data-ctdp-box="on"]'));
  doc.querySelector('#ctf_on').dispatchEvent(new window.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  ok(await waitFor(()=>!doc.querySelector('[data-ctdp-box="on"]')),'Escape تقویم را می‌بندد');
  click('[data-ctdp="on"]'); await waitFor(()=>doc.querySelector('[data-ctdp-box="on"]'));
  type('#ctf_endTime','20:00');
  ok(doc.querySelector('#ctf_endsAt').value==='1405/10/03 20:00','ساعت پایان پیش از پاک‌کردن تاریخ: پایان دقیق همان روز');
  click('[data-ctdp-clear]');
  ok(await waitFor(()=>doc.querySelector('#ctf_on').value===''),'پاک‌کردن تاریخ از تقویم');
  ok(doc.querySelector('#ctf_startsAt').value===''&&doc.querySelector('#ctf_endsAt').value===''&&doc.querySelector('#ctf_endTime').value==='20:00'&&doc.querySelector('#ctf_time').value==='18:00','پاک‌کردن تاریخ، شروع/پایانِ هم‌روز را پاک می‌کند ولی ساعت‌های تایپ‌شده می‌مانند');
  type('#ctf_on','1405/08/12');
  ok(doc.querySelector('#ctf_startsAt').value==='1405/08/12 18:00'&&doc.querySelector('#ctf_endsAt').value==='1405/08/12 20:00','تاریخ تازه: شروع و پایان از ساعت‌های نگه‌داشته‌شده ساخته می‌شوند');
  type('#ctf_endTime','');
  ok(doc.querySelector('#ctf_endsAt').value==='','پایان دوباره خالی');
  type('#ctf_on','۱۴۰۵/۰۸/۱۲');
  ok(doc.querySelector('#ctf_on').value==='۱۴۰۵/۰۸/۱۲','ارقام فارسی هنگام تایپ بازنویسی نمی‌شوند');
  doc.querySelector('#ctf_on').dispatchEvent(new window.FocusEvent('focusout',{bubbles:true}));
  ok(doc.querySelector('#ctf_on').value==='1405/08/12','پس از ترک فیلد به لاتین نرمال می‌شود');

  console.log('── خطای ۴۲۲ سرور: بلوک همان فیلد باز می‌شود ──');
  type('#ctf_t','رویداد فشرده');
  type('#ctf_regClosesAt','1405/08/10 25:99');
  click('[data-ct-save]');
  ok(await waitFor(()=>CALLS.some(c=>c.method==='POST'&&c.path==='/api/admin/content/events')&&doc.querySelector('[data-ct-sec="reg"] [data-ct-err="regClosesAt"][style]')&&/پذیرفته نشد|نامعتبر/.test(doc.querySelector('[data-ct-err="regClosesAt"]').textContent)),'خطای ۴۲۲ مهلت ثبت‌نام زیر همان فیلد در بخش ثبت‌نام');
  ok(!doc.querySelector('[data-ct-save-stay][disabled]'),'پس از پاسخ سرور دکمه‌ها دوباره فعال‌اند');
  ok(doc.querySelector('#ctf_t').value==='رویداد فشرده'&&doc.querySelector('#ctf_joinUrl').value==='https://meet.example.org/room','متن تایپ‌شده پس از خطا می‌ماند');
  ok(WORLD.events.length===2,'با خطای اعتبارسنجی چیزی ساخته نشد');

  console.log('── ذخیرهٔ پیش‌نویس و اتصال فرم: شناسه می‌گیرد و در بخش ثبت‌نام می‌ماند ──');
  type('#ctf_regClosesAt','1405/08/10 23:59');
  ok(doc.querySelector('[data-ct-forms="unsaved"]')&&doc.querySelector('[data-ct-save-stay]'),'رویداد ذخیره‌نشده: راهنمای «پس از ذخیره» + دکمهٔ ذخیرهٔ پیش‌نویس و اتصال فرم');
  click('[data-ct-save-stay]');
  ok(await waitFor(()=>CALLS.filter(c=>c.method==='POST'&&c.path==='/api/admin/content/events').length===2),'POST ساخت رویداد فرستاده شد');
  const created=CALLS.filter(c=>c.method==='POST'&&c.path==='/api/admin/content/events')[1];
  ok(created.body.expected_version===3,'expected_version از فهرست سروری (نه صفر) حتی وقتی فرم مستقیم از #newev باز شده');
  ok(created.body.record.mode==='ترکیبی'&&created.body.record.joinUrl==='https://meet.example.org/room'&&created.body.record.place==='سالن اصلی'&&created.body.record.startsAt==='1405/08/12 18:00'&&created.body.record.endsAt===''&&!('endTime' in created.body.record),'بدنه: نوع، پیوند، مکان، شروع دقیق؛ پایان خالی؛ فیلد مجازی ساعت پایان فرستاده نمی‌شود');
  ok(await waitFor(()=>doc.querySelector('[data-ct-editor]')&&doc.querySelector('[data-ct-forms="ev-new"]'),6000),'پس از ذخیره، ویرایشگر همان رکورد (ev-new) باز است و کارت فرم فعال شد');
  ok(doc.querySelector('[data-ct-form-create="ev-new"]')&&/create\.html\?/.test(doc.querySelector('[data-ct-form-create="ev-new"]').getAttribute('href'))&&/ev=ev-new/.test(doc.querySelector('[data-ct-form-create="ev-new"]').getAttribute('href')),'«ساخت فرم ثبت‌نام» فرم‌ساز واقعی را با شناسهٔ همین رویداد باز می‌کند');
  ok(await waitFor(()=>doc.querySelector('[data-ct-form-link-pick]')),'انتخاب‌گر فرم‌های بی‌رویداد از همان GET /api/forms');
  const opts=[...doc.querySelectorAll('[data-ct-form-link-pick] option')].map(o=>[o.value,o.disabled]);
  ok(opts.some(([v,d])=>v==='f-free'&&!d)&&opts.some(([v,d])=>v==='f-pub'&&d)&&!opts.some(([v])=>v==='f-other'),'پیش‌نویس انتخاب‌پذیر، منتشرشده غیرفعال با دلیل، فرم رویداد دیگر فهرست نمی‌شود');
  ok(doc.querySelector('[data-ct-file="ev-new"]')&&doc.querySelector('[data-ct-interaction="ev-new"]'),'رکورد ذخیره‌شده: دکمهٔ پروندهٔ رویداد و «فایل‌ها و رسانه‌ها»');

  console.log('── وصل‌کردن فرم: فقط POST /api/forms/{id}/event ──');
  click('[data-ct-form-link-do]');
  ok(!CALLS.some(c=>/\/api\/forms\/.+\/event$/.test(c.path)),'هیچ POST پیوندی بدون انتخاب فرستاده نشد');
  doc.querySelector('[data-ct-form-link-pick]').value='f-free';
  click('[data-ct-form-link-do]');
  ok(await waitFor(()=>CALLS.some(c=>c.method==='POST'&&c.path==='/api/forms/f-free/event')),'POST /api/forms/f-free/event فرستاده شد');
  const lk=CALLS.find(c=>c.method==='POST'&&c.path==='/api/forms/f-free/event');
  ok(lk&&lk.body.ev==='ev-new'&&lk.body.expected_version===2&&lk.headers['X-CSRF-Token']==='test-csrf-token','بدنه: ev + expected_version فرم + سرآیند CSRF');
  ok(!CALLS.some(c=>c.method==='PUT'&&c.path.startsWith('/api/forms/')),'تعریف فرم (PUT /api/forms) دست نخورد؛ فرم‌ساز تنها ویرایشگر است');
  ok(await waitFor(()=>doc.querySelector('[data-ct-form-row="f-free"]')),'پس از پاسخ سرور، فرم زیر همین رویداد فهرست می‌شود (بازخوانی از /api/forms)');
  ok(doc.querySelector('[data-ct-form-unlink="f-free"]'),'جداکردن برای فرم پیش‌نویس بی‌پاسخ در دسترس است');
  ok(await waitFor(()=>doc.querySelector('[data-ct-review-form="f-free"]')),'مرور: فرم وصل‌شده دیده می‌شود');
  ok(/فرم‌های وصل‌شده: ۱/.test(doc.querySelector('[data-ct-review-server]').textContent)&&/منتشرشده: ۰/.test(doc.querySelector('[data-ct-review-server]').textContent),'شمارنده‌ها از همان فهرست سرور: ۱ فرم، ۰ منتشرشده');
  ok(doc.querySelector('[data-ct-public-link]')&&/event\.html\?id=ev-new/.test(doc.querySelector('[data-ct-public-link]').getAttribute('href')),'پیوند صفحهٔ عمومی با شناسهٔ واقعی');
  ok(doc.querySelector('[data-ct-save-publish]'),'پیش‌نویس موجود «ذخیره و انتشار در سایت» دارد (ev_publish)');

  console.log('── پیش‌نمایش و بازشوندگی بدون گم‌شدن متن ──');
  ok(doc.querySelector('[data-ct-review-card][hidden]'),'کارت پیش‌نمایش تا درخواست پنهان است');
  click('[data-ct-preview-toggle]');
  ok(await waitFor(()=>doc.querySelector('[data-ct-review-card]:not([hidden]) #ctPreview')),'«پیش‌نمایش» کارت را در بخش مرور باز می‌کند');
  ok(doc.querySelector('[data-ct-review-row="d"][data-ct-review-ok="0"] [data-ct-jump="desc"]'),'شرح خالی در مرور با دکمهٔ پرش به بلوک خودش');
  click('[data-ct-jump="desc"]');
  ok(await waitFor(()=>doc.querySelector('details[data-ct-more="desc"]').open),'پرش از مرور، بلوک «شرح…» را باز می‌کند');
  type('#ctf_d','شرح تازه');
  ok(await waitFor(()=>doc.querySelector('[data-ct-review-row="d"][data-ct-review-ok="1"]')),'مرور بی‌درنگ از همین فرم به‌روز می‌شود');
  const sched=doc.querySelector('details[data-ct-more="sched"]'); sched.open=true; sched.dispatchEvent(new window.Event('toggle')); sched.open=false; sched.dispatchEvent(new window.Event('toggle'));
  type('#ctf_sess','3');
  ok(doc.querySelector('#ctf_d').value==='شرح تازه'&&doc.querySelector('#ctf_joinUrl').value==='https://meet.example.org/room'&&doc.querySelector('#ctf_sess').value==='3'&&doc.querySelector('details[data-ct-more="desc"]').open,'باز و بسته‌شدن بلوک‌ها متن تایپ‌شده را گم نمی‌کند و حالت بازِ بلوک می‌ماند');

  console.log('── پیوند نامعتبر: ۴۲۲ سرور روی همان فیلد ──');
  type('#ctf_joinUrl','http://insecure.example.org');
  click('[data-ct-save]');
  ok(await waitFor(()=>doc.querySelector('[data-ct-err="joinUrl"]')&&doc.querySelector('[data-ct-err="joinUrl"]').textContent.trim().length>0),'خطای joinUrl زیر فیلد پیوند ورود');
  type('#ctf_joinUrl','https://meet.example.org/room');

  console.log('── پیوند پس از بازگشایی حفظ می‌شود ──');
  click('[data-ct-cancel]');
  ok(await waitFor(()=>doc.querySelector('[data-ct-edit="ev-new"]')),'بازگشت به فهرست');
  click('[data-ct-edit="ev-new"]');
  ok(await waitFor(()=>doc.querySelector('[data-ct-editor]')&&doc.querySelector('#ctf_t')?.value==='رویداد فشرده'),'ویرایش همان رکورد با همان فرم فشرده');
  ok(doc.querySelector('[data-ct-where="hybrid"]')&&doc.querySelector('#ctf_joinUrl').value==='https://meet.example.org/room','نوع ترکیبی و پیوند ورود پس از بازگشایی از سرور');
  ok(await waitFor(()=>doc.querySelector('[data-ct-form-row="f-free"]')),'پیوند فرم پس از بازگشایی از سرور خوانده می‌شود');
  click('[data-ct-cancel]'); await waitFor(()=>doc.querySelector('[data-ct-quick]'));

  console.log('── فهرست: صافی ساده + شیوهٔ برگزاری ──');
  const quick=[...doc.querySelectorAll('[data-ct-quick]')].map(x=>x.dataset.ctQuick);
  ok(JSON.stringify(quick)===JSON.stringify(['all','upcoming','past','draft','archived']),'صافی‌های همه/پیش‌رو/برگزارشده/پیش‌نویس/بایگانی');
  ok(doc.querySelector('details[data-ct-more-filters]')&&doc.querySelector('[data-ct-status="published"]')&&doc.querySelector('[data-ct-when="today"]'),'صافی‌های ریزتر زیر «صافی‌های بیشتر» مانده‌اند');
  click('[data-ct-quick="past"]');
  ok(await waitFor(()=>CALLS.some(c=>c.method==='GET'&&/\/api\/admin\/content\/events\?.*when=past/.test(c.path+'?'+(c.query||''))||CALLS.some(c=>c.method==='GET'&&c.path==='/api/admin/content/events'))&&doc.querySelector('[data-ct-row="ev-old"]')&&!doc.querySelector('[data-ct-row="ev-1"]')),'«برگزارشده» فقط رویداد گذشته را (از سرور، when=past) نشان می‌دهد');
  ok(/آنلاین/.test(doc.querySelector('[data-ct-row="ev-old"]').textContent)&&/برگزارشده/.test(doc.querySelector('[data-ct-row="ev-old"]').textContent),'ردیف: شیوهٔ برگزاری و برگزارشده قابل تشخیص');
  click('[data-ct-quick="all"]'); await waitFor(()=>doc.querySelector('[data-ct-row="ev-1"]'));
  const modeSel=doc.querySelector('[data-ct-mode]'); ok(modeSel&&[...modeSel.options].some(o=>o.value==='حضوری')&&[...modeSel.options].some(o=>o.value==='آنلاین'),'انتخاب شیوهٔ برگزاری از mode_counts سرور');
  modeSel.value='آنلاین'; modeSel.dispatchEvent(new window.Event('change',{bubbles:true}));
  ok(await waitFor(()=>doc.querySelector('[data-ct-row="ev-old"]')&&!doc.querySelector('[data-ct-row="ev-1"]')),'صافی شیوهٔ برگزاری با پارامتر mode سرور');
  modeSel.value=''; doc.querySelector('[data-ct-mode]').dispatchEvent(new window.Event('change',{bubbles:true})); await waitFor(()=>doc.querySelector('[data-ct-row="ev-1"]'));

  console.log('── ثبت رویداد برگزارشده ──');
  click('#admNav [data-sec="newev"]');
  ok(await waitFor(()=>doc.querySelector('[data-newev-past]')),'چیپ «رویداد برگزارشده» در تعریف جدید');
  click('[data-newev-past]');
  ok(await waitFor(()=>doc.querySelector('[data-ct-past-hint]')&&doc.querySelector('[data-ct-check="past"]')?.checked),'فرم برگزارشده: راهنمای صریح + علامت past (همان پرچم سرور)');
  ok(doc.querySelector('[data-ct-past-reg]')&&!doc.querySelector('[data-ct-reminders]')&&!doc.querySelector('#ctf_regClosesAt')&&!doc.querySelector('[data-ct-save-stay]'),'بدون اجبار ثبت‌نام، مهلت و یادآور (بسته در بدنه می‌رود)');
  ok(!doc.querySelector('[data-ct-review-row="form"]')&&!doc.querySelector('[data-ct-review-row="rem"]'),'مرور رویداد برگزارشده، فرم و یادآور را طلب نمی‌کند');
  type('#ctf_t','نشست گذشته'); type('#ctf_on','1405/06/01'); type('#ctf_mode','حضوری'); await waitFor(()=>doc.querySelector('[data-ct-where="onsite"]')); type('#ctf_place','کتابخانه');
  click('[data-ct-save]');
  ok(await waitFor(()=>CALLS.filter(c=>c.method==='POST'&&c.path==='/api/admin/content/events').length===3),'ذخیرهٔ رویداد برگزارشده');
  ok(await waitFor(()=>!doc.querySelector('[data-ct-editor]')&&doc.querySelector('[data-ct-row]')),'پس از ذخیره از «تعریف جدید»، فهرست رویدادها با رکورد تازه دیده می‌شود (نه فرم خالی)');
  const pastBody=CALLS.filter(c=>c.method==='POST'&&c.path==='/api/admin/content/events').pop().body.record;
  ok(pastBody.past===true&&pastBody.regMode==='closed'&&pastBody.reminders.h24===false&&pastBody.reminders.h1===false&&pastBody.on==='1405/06/01','بدنه: past=true، ثبت‌نام بسته، یادآور خاموش، تاریخ گذشته');
  ok(errors.filter(e=>!/401|authentication_required|net::|sitemap/.test(e)).length===0,'بدون خطای جاوااسکریپت ('+errors.filter(e=>!/401|authentication_required|net::|sitemap/.test(e)).join(' | ').slice(0,200)+')');
}

console.log('── پروندهٔ رویداد: نمای کلی، فرم‌ها و فعالیت‌ها، ثبت‌نام‌کنندگان، نظرسنجی، اطلاع‌رسانی؛ هر زبانه با منبع سروری همین رویداد ──');
{
  const {doc,click,type}=await boot('owner');
  ok(await waitFor(()=>doc.querySelector('#admNav [data-sec="events"]')),'پنل بالا آمد');
  click('#admNav [data-sec="events"]');
  ok(await waitFor(()=>doc.querySelector('[data-ct-file="ev-1"]')),'کارت رویداد دکمهٔ «مدیریت رویداد» دارد');
  ok(/مدیریت رویداد/.test(doc.querySelector('[data-ct-file="ev-1"]').textContent),'برچسب دکمه: مدیریت رویداد');
  ok(doc.querySelector('[data-ct-interaction="ev-1"]'),'دکمهٔ «فایل‌ها و پرسش‌ها» حذف نشده');
  click('[data-ct-file="ev-1"]');
  ok(await waitFor(()=>doc.querySelector('[data-ei-panel] [data-ef-overview="ev-1"]')),'پرونده روی «نمای کلی» باز می‌شود');
  ok(CALLS.some(c=>c.method==='GET'&&c.path==='/api/admin/events/ev-1/overview'),'نمای کلی از GET /api/admin/events/ev-1/overview خوانده شد');
  /* msg 97: شش کاشی به‌جای ردیف بلند زبانه‌ها؛ هر زیرزبانهٔ قبلی زیر بخش خودش می‌ماند (حذف نشده) */
  const tiles=[...doc.querySelectorAll('[data-ei-panel] [data-ef-tile]')].map(x=>x.dataset.efTile);
  ok(JSON.stringify(tiles)===JSON.stringify(['overview','forms','regs','pay','comms','reports']),'شش کاشی پرونده: نمای کلی، فرم‌ها و ثبت‌نام، ثبت‌نام‌کنندگان، پرداخت و حضور، محتوا و ارتباطات، گزارش و گواهی');
  const tabs=[...doc.querySelectorAll('[data-ei-panel] [data-ei-tab]')].map(x=>x.dataset.eiTab);
  ok(['info','forms','survey','regs','payments','tickets','resources','notify','recording','questions','reviews','certs','reports'].every(k=>tabs.includes(k)),'همهٔ زیربخش‌های قبلی از روی کاشی‌ها در دسترس‌اند (هیچ قابلیتی حذف نشده)');
  ok(!/[۰-۹]/.test(doc.querySelector('[data-ef-tile="regs"] .eftile-num')?.textContent||'')&&!doc.querySelector('[data-ef-kpis]')&&/بدون فرم ثبت‌نام/.test(doc.querySelector('[data-ef-head]').textContent),'جمع ثبت‌نام از counts سرور فقط در سربرگ پرونده است؛ ردیف تفکیک با همه‌صفر رندر نمی‌شود (بازطراحی مرحلهٔ B)');
  const head=doc.querySelector('[data-ef-head]').textContent;
  ok(/کارگاه آزمون/.test(head)&&/پیش‌نویس/.test(head)&&/بدون فرم ثبت‌نام/.test(head),'سربرگ: عنوان، وضعیت مشتق‌شده و وضعیت فرم ثبت‌نام (بدون فرم)');
  ok(doc.querySelector('[data-ef-head] [data-ei-edit="ev-1"]')&&!doc.querySelector('[data-ef-head] [data-ef-reg-settings]'),'دکمهٔ «ویرایش رویداد» هست؛ «ویرایش تنظیمات ثبت‌نام» بدون فرم نیست');
  click('[data-ef-tile="overview"] [data-ei-tab="info"]');
  ok(await waitFor(()=>doc.querySelector('[data-ef-info="ev-1"]')),'کاشی «نمای کلی» زیرصفحهٔ مشخصات را باز می‌کند');
  const info=doc.querySelector('[data-ef-info="ev-1"]').textContent;
  ok(/تهران/.test(info)&&/ثبت‌نام بسته/.test(info)&&/هنوز فرمی به این رویداد وصل نیست/.test(info),'نمای کلی: مکان، وضعیت ثبت‌نام سرور، نبود فرم');
  ok(doc.querySelector('[data-ef-group="overview"] [data-ef-hub-back]')&&/نمای کلی/.test(doc.querySelector('[data-ef-group="overview"]').textContent),'زیرصفحه: عنوان بخش + دکمهٔ بازگشت به پرونده');
  ok(!doc.querySelector('[data-ei-panel] .hub-tabs [data-ei-tab="recording"]'),'در زیرصفحه ردیف بلند زبانه‌های بخش‌های دیگر نیست (فقط منوی جمع‌شده)');

  console.log('── فرم‌ها و فعالیت‌ها: فقط فرم‌های همین رویداد؛ اتصال/قطع اتصال با POST /api/forms/{id}/event ──');
  click('[data-ei-tab="forms"]');
  ok(await waitFor(()=>doc.querySelector('[data-ef-forms]')&&doc.querySelector('[data-ef-forms-empty]')),'زبانهٔ فرم‌ها: حالت خالی صریح');
  const mk=doc.querySelector('[data-ef-create="reg"]').getAttribute('href');
  ok(/^create\.html\?ev=ev-1&need=reg/.test(mk)&&/back=admin\.html%23event%3Dev-1%26tab%3Dforms/.test(mk),'ساخت فرم ثبت‌نام در فرم‌ساز با شناسهٔ رویداد و بازگشت به همین پرونده و زبانه ('+mk+')');
  ok(doc.querySelector('[data-ef-create="survey"]')&&doc.querySelector('[data-ef-create="exam"]'),'ساخت نظرسنجی و آزمون هم از همین‌جا');
  ok(await waitFor(()=>doc.querySelector('[data-ef-link-pick]')),'انتخاب‌گر «اتصال فرم موجود» از همان GET /api/forms');
  const opts=[...doc.querySelectorAll('[data-ef-link-pick] option')].map(o=>o.value+(o.disabled?'!':''));
  ok(opts.includes('f-free')&&opts.includes('f-pub!')&&!opts.includes('f-other'),'نامزدها: فرم بی‌رویداد پیش‌نویس فعال، منتشرشده قفل، فرم رویداد دیگر نیست ('+opts.join(',')+')');
  ok(!doc.querySelector('[data-ef-form="f-other"]'),'فرم رویداد دیگر در فهرست این رویداد نیست');
  type('[data-ef-link-pick]','f-free');
  ok(await waitFor(()=>doc.querySelector('[data-ef-link-do]')&&!doc.querySelector('[data-ef-link-do]').disabled),'دکمهٔ «اتصال فرم» پس از انتخاب فعال می‌شود');
  click('[data-ef-link-do]');
  ok(await waitFor(()=>CALLS.some(c=>c.method==='POST'&&c.path==='/api/forms/f-free/event'&&c.body.ev==='ev-1'&&c.body.expected_version===2&&c.headers['X-CSRF-Token'])),'POST /api/forms/f-free/event با ev=ev-1، نسخه و CSRF');
  ok(await waitFor(()=>doc.querySelector('[data-ef-form="f-free"]')),'پس از پاسخ سرور، فرم زیر همین رویداد فهرست می‌شود (بازخوانی overview)');
  ok(/فرم ثبت‌نام/.test(doc.querySelector('[data-ef-form="f-free"]').textContent)&&/۰ پاسخ/.test(doc.querySelector('[data-ef-form="f-free"]').textContent),'کارت فرم: نوع، شمار پاسخ از سرور');
  ok(!CALLS.some(c=>c.method==='PUT'&&c.path.startsWith('/api/forms/')),'تعریف فرم (PUT /api/forms) دست نخورد؛ فرم‌ساز تنها ویرایشگر است');
  const edit=doc.querySelector('[data-ef-form="f-free"] a[href^="create.html?fid=f-free"]');
  ok(edit&&/back=admin\.html%23event%3Dev-1%26tab%3Dforms/.test(edit.getAttribute('href')),'«ویرایش فرم» به فرم‌ساز با بازگشت به همین رویداد و زبانه');
  ok(doc.querySelector('[data-ef-unlink="f-free"]'),'«قطع اتصال» برای فرم پیش‌نویس بدون پاسخ');
  click('[data-ef-unlink="f-free"]');
  ok(await waitFor(()=>CALLS.filter(c=>c.method==='POST'&&c.path==='/api/forms/f-free/event').length===2&&CALLS.filter(c=>c.method==='POST'&&c.path==='/api/forms/f-free/event').pop().body.ev===''),'قطع اتصال: همان نقطهٔ پایانی با ev خالی (فرم حذف نمی‌شود)');
  ok(await waitFor(()=>!doc.querySelector('[data-ef-form="f-free"]')&&doc.querySelector('[data-ef-forms-empty]')),'پس از قطع اتصال، فرم از پروندهٔ رویداد می‌رود');
  ok(!CALLS.some(c=>c.method==='DELETE'),'هیچ حذفی فرستاده نشد');

  console.log('── ثبت‌نام‌کنندگان و نظرسنجی: فقط از نماهای همین رویداد ──');
  click('[data-ei-tab="regs"]');
  ok(await waitFor(()=>doc.querySelector('[data-ef-regs]')),'زبانهٔ ثبت‌نام‌کنندگان');
  ok(CALLS.some(c=>c.method==='GET'&&c.path==='/api/admin/events/ev-1/registrations'),'فهرست از GET /api/admin/events/ev-1/registrations');
  ok(doc.querySelector('[data-ef-summary]')&&/بدون سقف ظرفیت/.test(doc.querySelector('[data-ef-summary]').textContent),'خلاصهٔ سروری (ظرفیت) بالای فهرست');
  ok(doc.querySelector('[data-ef-regs-empty]')&&/فرم ثبت‌نامی به این رویداد وصل نیست/.test(doc.querySelector('[data-ef-regs-empty]').textContent)&&doc.querySelector('[data-ef-regs-empty] [data-ef-tab="forms"]'),'بدون فرم: حالت خالی با اقدام (رفتن به فرم‌ها)');
  click('[data-ei-tab="survey"]');
  ok(await waitFor(()=>doc.querySelector('[data-ef-survey]')),'زبانهٔ نظرسنجی و آزمون');
  ok(doc.querySelector('[data-ef-survey-empty]')&&/create\.html\?ev=ev-1&need=survey/.test(doc.querySelector('[data-ef-survey] [data-ef-create="survey"]').getAttribute('href')),'نظرسنجی جدا از ثبت‌نام؛ ساخت فقط در فرم‌ساز با شناسهٔ رویداد');
  click('[data-ei-tab="notify"]');
  ok(await waitFor(()=>doc.querySelector('[data-ei-notify]')),'زبانهٔ اطلاع‌رسانی و تاریخچه');
  ok(/۲۴ ساعت قبل: خاموش/.test(doc.querySelector('[data-ei-notify]').textContent)&&doc.querySelector('[data-ch-pane="hist"][data-ch-id="ev-1"]'),'وضعیت یادآورها از رکورد سرور + تاریخچهٔ مالک (B18)');
  ok(!doc.querySelector('[data-ntfbcast],[data-ei-send]'),'هیچ دکمهٔ ارسال دستی/همگانی وجود ندارد');
  click('[data-ch-pane="hist"][data-ch-id="ev-1"]');
  ok(await waitFor(()=>CALLS.some(c=>c.path.startsWith('/api/owner/audit'))&&doc.querySelector('[data-ch-panel="content.events"]')),'تاریخچه از /api/owner/audit داخل همان زبانه');
  click('[data-ef-hub-back]');
  ok(await waitFor(()=>doc.querySelector('[data-ef-hub]')&&doc.querySelector('[data-ef-head] [data-ei-edit="ev-1"]')),'بازگشت به پرونده: کاشی‌ها و سربرگ با «ویرایش رویداد»');
  click('[data-ef-head] [data-ei-edit="ev-1"]');
  ok(await waitFor(()=>doc.querySelector('[data-ct-editor]')&&doc.querySelector('[data-ct-sec="reg"]')&&doc.querySelector('[data-ct-forms="ev-1"]')),'«ویرایش رویداد» همان فرم فشرده را باز می‌کند');
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
