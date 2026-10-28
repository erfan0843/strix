/* تنظیمات پنل به ساختار طرح نورا (۱۴۰۵/۰۸/۰۱): کاشی‌های حوزه + شش گروه با بخش‌بند،
   هر گزینه با وضعیت صریح؛ فقط گزینه‌های «متصل» کنترل زنده دارند و از /api/owner/settings
   خوانده/ذخیره می‌شوند. هیچ کلیدی در localStorage ذخیره نمی‌شود؛ مدیر بی‌مجوز فقط
   گروه‌های عمومی را می‌بیند و پیام انتقال مدیران/کارشناسان به «کاربران» می‌گیرد. */
import {fileURLToPath} from 'node:url';
import jsdom from 'jsdom';
const {JSDOM}=jsdom;
const DIR=fileURLToPath(new URL('./',import.meta.url));
let fails=0, checks=0;
const ok=(c,m)=>{checks++; if(!c){fails++; console.log('   ✗ '+m);} else console.log('   ✓ '+m);};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function waitFor(fn,ms=4000){const end=Date.now()+ms; while(Date.now()<end){try{if(fn()) return true}catch(e){} await wait(25);} return false;}
const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});

const STORE={items:[
  {key:'texts.reminder_head',value:'',default:'',custom:false,consumer:'سطر نخست پیام یادآور رویداد',updated_at:null,updated_by:''},
  {key:'events.reminders_default',value:{h24:false,h1:false},default:{h24:false,h1:false},custom:false,consumer:'پیش‌فرض کلیدهای یادآور رویداد تازه',updated_at:null,updated_by:''}]};
let CALLS=[], ROLE='owner', REJECT_NEXT_PUT='';
const SERVICES={encryption_ready:true,public_base_url:'https://nora.example',services:[
  {key:'bale',title:'بله و مینی‌اپ',icon:'i-send',summary:'',state:'configured',runtime:{ready:true,missing:[],scope:'web'},fields:[],readonly:[]},
  {key:'sms',title:'پیامک',icon:'i-send',summary:'',state:'unconfigured',fields:[],readonly:[]},
  {key:'payment',title:'پرداخت و کیف پول',icon:'i-wallet',summary:'توکن ربات پرداخت',state:'unconfigured',runtime:{ready:false,missing:['NORA_FORM_PAYMENT_PROVIDER_TOKEN'],scope:'web'},
   fields:[{key:'bale_wallet',service:'payment',label:'توکن ربات پرداخت',help:'',env_name:'NORA_FORM_PAYMENT_BOT_TOKEN',editable:true,acknowledge_restart:false,probe:true,configured:false,source:'none',hint:'',updated_at:null,encryption_ready:true,blocked_by:[],check:{checked:false,ok:null,code:'',checked_at:null},consumers:['web']}],readonly:[]}]};
async function fakeFetch(url,init){
  const method=String(init&&init.method||'GET').toUpperCase(); const path=String(url).split('?')[0];
  const body=init&&init.body?JSON.parse(init.body):null; const headers=(init&&init.headers)||{};
  CALLS.push({path,method,body,headers});
  if(path==='/api/auth/me'){
    if(ROLE==='owner') return json({authenticated:true,owner_id:'owner-01',role:'owner',permissions:['sys_settings','sys_backup','sys_fields','rp_view','us_view','fm_create','fm_responses','certificate','attendance']});
    return json({detail:'authentication_required'},401);
  }
  if(path==='/api/account/me'){
    if(ROLE==='manager') return json({authenticated:true,account_id:'acc-m1',provider:'manager-password',role:'manager',permissions:['ev_create','us_view','rp_view','certificate'],manager_username:'qa.manager'});
    return json({detail:'authentication_required'},401);
  }
  if(path==='/api/owner/settings'&&method==='GET') return ROLE==='owner'?json(STORE):json({detail:'permission_denied'},403);
  if(path==='/api/owner/settings'&&method==='PUT'){
    if(ROLE!=='owner') return json({detail:'permission_denied'},403);
    if(!headers['X-CSRF-Token']) return json({detail:'csrf_check_failed'},400);
    if(REJECT_NEXT_PUT){const code=REJECT_NEXT_PUT; REJECT_NEXT_PUT=''; return json({detail:{code,message:'متن خیلی بلند است.'}},422);}
    Object.entries(body.changes).forEach(([k,v])=>{const it=STORE.items.find(x=>x.key===k); it.value=v; it.custom=JSON.stringify(v)!==JSON.stringify(it.default); it.updated_by='owner-01'; it.updated_at='2026-10-23T10:00:00+00:00';});
    return json(STORE);
  }
  if(path==='/api/owner/service-settings'&&method==='GET') return json(SERVICES);
  if(path==='/api/owner/data/status') return json({database:{engine:'sqlite',schema_version:'0038_system_settings'},staging:{retention_hours:72,max_bytes:1,used_bytes:0,outside_webroot:true},audit_tool_available:true,operational_writes:0});
  if(path==='/api/owner/data/uploads') return json({uploads:[],limits:{max_bytes:1,retention_hours:72},audit_tool_available:true});
  if(path.startsWith('/api/owner/audit')) return json({items:[],total:0});
  if(path.startsWith('/api/admin/')||path.startsWith('/api/forms')) return json({items:[],total:0,summary:{}});
  return json({detail:'not_found'},404);
}
async function boot(role){
  ROLE=role; CALLS=[];
  const errors=[];
  const dom=await JSDOM.fromFile(DIR+'admin.html',{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,
    beforeParse(w){w.fetch=(u,i)=>fakeFetch(u,i); w.scrollTo=()=>{}; if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      w.addEventListener('error',e=>errors.push('error: '+e.message)); w.console.error=(...a)=>errors.push('console.error: '+a.join(' '));}});
  const {window}=dom;
  await new Promise(resolve=>{if(window.document.readyState==='complete') return resolve(); const t=setTimeout(resolve,10000); window.addEventListener('load',()=>{clearTimeout(t);resolve()},{once:true});});
  const doc=window.document; if(role==='owner') Object.defineProperty(doc,'cookie',{configurable:true,get:()=>'nora_csrf=test-csrf-token'});
  const click=sel=>{const el=typeof sel==='string'?doc.querySelector(sel):sel; if(!el) throw new Error('نیست: '+sel); el.dispatchEvent(new window.MouseEvent('click',{bubbles:true})); return el};
  const type=(sel,v)=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel); el.value=v; el.dispatchEvent(new window.Event('input',{bubbles:true}));};
  return {window,doc,click,type,errors};
}

console.log('── مالک: ساختار طرح نورا ──');
{
  const {window,doc,click,type,errors}=await boot('owner');
  ok(await waitFor(()=>doc.querySelector('#admNav [data-sec="settings"]')),'پنل با نشست مالک بالا آمد');
  click('#admNav [data-sec="settings"]');
  ok(await waitFor(()=>doc.querySelector('[data-sset-tiles]')),'کاشی‌های حوزه بالای صفحه رندر شد');
  const tiles=[...doc.querySelectorAll('[data-sset-tile]')].map(x=>x.querySelector('b').textContent.trim()).sort();
  ok(JSON.stringify(tiles)===JSON.stringify(['ظاهری سامانه','فرمساز','کاربران و دسترسی','مدیریت پنل','باشگاه کتابخوانی','رویدادها و مطالب','مدیران و اساتید','پشتیبانی و گفتگو'].sort()),'هر هشت حوزه در دسترس‌اند: چهار حوزهٔ درون‌صفحه چیپِ همان ردیف گروه‌ها، چهار حوزهٔ بخش‌های دیگر میان‌بر (بازطراحی مرحلهٔ E): '+tiles.join('، '));
  ok(['skin','ops','people','chat'].every(k=>doc.querySelector('[data-sset-groups] [role="tablist"] [data-sset-tile="'+k+'"]'))&&['forms','users','book','skdev'].every(k=>doc.querySelector('[data-sset-tiles] [data-sset-tile="'+k+'"]')),'یک مدل ناوبری: حوزه‌های درون‌صفحه در همان ردیف انتخاب؛ مقصدهای بیرونی جدا و کوتاه');
  ok(doc.querySelector('[data-sset-tile="forms"]').getAttribute('href')==='builder.html','کاشی فرم‌ساز به فرم‌ساز واقعی می‌رود');
  const groups=[...doc.querySelectorAll('[data-sset-groups] .admfilters[aria-label="گروه‌های تنظیمات"] [data-setg]')].map(x=>x.textContent.trim());
  ok(JSON.stringify(groups)===JSON.stringify(['متن‌ها','مالی و کارمزد','گواهینامه','بلیت','اعلان‌ها','داده و پشتیبان']),'شش گروه با نام و ترتیب data.js مرجع: '+groups.join('، '));
  ok(doc.querySelector('[data-sset-legend]'),'راهنمای وضعیت‌ها دیده می‌شود');
  ok(!doc.querySelector('[data-tog]')&&!doc.querySelector('[data-savetexts]'),'هیچ کلید یا دکمهٔ نمایشی طرح (data-tog/data-savetexts) در پنل سروری نیست');

  console.log('── متن‌ها: انبار سروری ──');
  ok(await waitFor(()=>CALLS.some(c=>c.path==='/api/owner/settings'&&c.method==='GET')),'تنظیمات از /api/owner/settings خوانده شد');
  ok(await waitFor(()=>doc.querySelector('[data-sys-text="texts.reminder_head"]')),'قلم «متن یادآور رویداد» با مقدار سرور رندر شد');
  ok(doc.querySelector('[data-sys-save]').hasAttribute('disabled'),'بی‌تغییر، دکمهٔ ذخیره غیرفعال است');
  ok(doc.querySelectorAll('[data-sset-row="backend"],[data-sset-row="scope"]').length===3,'سه نوشتهٔ بی‌مصرف‌کننده فقط با وضعیت می‌آیند');
  type('[data-sys-text="texts.reminder_head"]','دوست عزیز، «{رویداد}» {زمان} برگزار می‌شود');
  ok(!doc.querySelector('[data-sys-save]').hasAttribute('disabled'),'با تایپ، ذخیره فعال می‌شود (حالت dirty)');
  click('[data-sys-save]');
  ok(await waitFor(()=>CALLS.some(c=>c.path==='/api/owner/settings'&&c.method==='PUT')),'PUT /api/owner/settings فرستاده شد');
  const put=CALLS.find(c=>c.path==='/api/owner/settings'&&c.method==='PUT');
  ok(put&&put.headers['X-CSRF-Token']==='test-csrf-token','سرآیند CSRF از کوکی مالک همراه ذخیره است');
  ok(put&&Object.keys(put.body.changes).join()==='texts.reminder_head','فقط کلید تغییرکرده فرستاده می‌شود');
  ok(await waitFor(()=>doc.querySelector('[data-sys-msg="ok"]')),'پیام موفقیت پس از پاسخ سرور (نه پیش از آن)');
  ok(doc.querySelector('[data-sys-text="texts.reminder_head"]').value==='دوست عزیز، «{رویداد}» {زمان} برگزار می‌شود','مقدار از پاسخ سرور بازخوانی شد');
  ok(doc.body.textContent.includes('سفارشی‌شده'),'نشان «سفارشی‌شده» از فیلد custom سرور');
  ok(!JSON.stringify(window.NORA_ADMIN_STATE||window.S||{}).includes('{رویداد}')&&!doc.documentElement.outerHTML.includes('nora-forms'),'متن فقط در پیش‌نویس حافظهٔ صفحه و پاسخ سرور است؛ در حالت ذخیره‌شدهٔ پنل نیست');

  console.log('── خطای سرور: چیزی عوض نمی‌شود ──');
  REJECT_NEXT_PUT='text_too_long';
  type('[data-sys-text="texts.reminder_head"]','x');
  click('[data-sys-save]');
  ok(await waitFor(()=>doc.querySelector('[data-sys-msg="stop"]')),'خطای ۴۲۲ کنار نوار ذخیره نمایش داده شد');
  ok(doc.body.textContent.includes('متن خیلی بلند است'),'پیام خطای سرور عیناً می‌آید');
  ok(!doc.querySelector('[data-sys-save]').hasAttribute('disabled'),'تغییر ذخیره‌نشده می‌ماند تا کاربر تصمیم بگیرد');
  click('[data-sys-cancel]');
  ok(await waitFor(()=>doc.querySelector('[data-sys-text="texts.reminder_head"]').value==='دوست عزیز، «{رویداد}» {زمان} برگزار می‌شود'),'انصراف مقدار سرور را برمی‌گرداند');

  console.log('── اعلان‌ها: پیش‌فرض یادآورها ──');
  click('[data-setg="notify"]');
  ok(await waitFor(()=>doc.querySelector('[data-sys-switch="events.reminders_default"][data-sys-slot="h24"]')),'کلیدهای پیش‌فرض یادآور از سرور رندر شدند');
  ok(doc.querySelectorAll('[data-sset-kind]').length>=5&&doc.body.textContent.includes('event_reminder'),'انواع اعلان واقعی سرور فهرست شده‌اند');
  ok(!doc.querySelector('[data-ntfbcast]')&&doc.body.textContent.includes('عمداً دکمه ندارد'),'نامهٔ فوری همگانی دکمه ندارد و دلیلش نوشته شده');
  click('[data-sys-switch="events.reminders_default"][data-sys-slot="h24"]');
  ok(doc.querySelector('[data-sys-switch="events.reminders_default"][data-sys-slot="h24"]').getAttribute('aria-checked')==='true','کلید ۲۴ ساعت روشن شد (پیش‌نویس)');
  click('[data-sys-save]');
  ok(await waitFor(()=>CALLS.filter(c=>c.path==='/api/owner/settings'&&c.method==='PUT').length===3),'ذخیرهٔ پیش‌فرض یادآور فرستاده شد');
  const last=CALLS.filter(c=>c.path==='/api/owner/settings'&&c.method==='PUT').pop();
  ok(JSON.stringify(last.body.changes)==='{"events.reminders_default":{"h24":true,"h1":false}}','بدنهٔ ذخیره دقیقاً {h24:true,h1:false}');

  console.log('── مالی، گواهینامه، بلیت، داده ──');
  click('[data-setg="money"]');
  ok(await waitFor(()=>doc.querySelector('[data-sset-pay]')),'درگاه بله با دکمهٔ پیکربندی واقعی');
  click('[data-sset-pay]');
  ok(await waitFor(()=>doc.querySelector('[data-sset-embed="payment"] [data-service-settings]')),'پیکربندی درگاه همان ماژول اتصال سرویس‌ها را زیر گروه مالی باز می‌کند');
  ok(doc.querySelectorAll('[data-sset-row="decision"]').length===2,'اقساط و کارمزد: «نیازمند تصمیم مالک»');
  click('[data-setg="cert"]');
  ok(await waitFor(()=>doc.body.textContent.includes('قالب فایل ورد گواهینامه')),'گروه گواهینامه با دو بخش‌بند');
  ok(!doc.querySelector('[data-cfileup]'),'بارگذاری قالب نمایشی وجود ندارد');
  click('[data-setg="ticket"]');
  ok(await waitFor(()=>doc.body.textContent.includes('ورود و مهمان')),'گروه بلیت با بخش‌بند ورود و مهمان');
  click('[data-setg="data"]');
  ok(await waitFor(()=>doc.querySelector('[data-data-panel]')),'داده و پشتیبان › سیاست‌ها: ماژول داده‌ها و مهاجرت');
  click('[data-setg="services"]');
  ok(await waitFor(()=>doc.querySelector('[data-service-settings]')),'داده و پشتیبان › اتصال‌ها و کلیدها: ماژول اتصال سرویس‌ها');

  console.log('── کاشی‌ها ──');
  click('[data-sset-tile="ops"]');
  ok(await waitFor(()=>doc.querySelector('[data-setg="performance"]')&&doc.querySelector('[data-sset-tile="ops"].on')),'کاشی مدیریت پنل: دامنه/امنیت/سلامت و کاشی روشن');
  click('[data-sset-tile="people"]');
  ok(await waitFor(()=>doc.querySelector('[data-pe-list],[data-pe-edit],[data-pe-new]')||doc.body.textContent.includes('استادان و افراد')),'کاشی مدیران و اساتید همان ویرایشگر افراد را باز می‌کند');
  click('[data-sset-tile="chat"]');
  ok(await waitFor(()=>doc.querySelector('[data-sset-chat]')),'کاشی پشتیبانی: وضعیت صریح، بی‌عدد نمونه');
  click('[data-sset-tile="users"]');
  ok(await waitFor(()=>doc.querySelector('[data-server-tools]')&&doc.body.textContent.includes('ابزارها و گزارش')),'کاشی کاربران و دسترسی به «کاربران › ابزارها» می‌رود (مدیریت مدیران و کارشناسان)');
  ok(errors.filter(e=>!/401|favicon|preload/.test(e)).length===0,'بدون خطای اجرایی: '+errors.slice(0,2).join(' | '));
}

console.log('── مدیر: تنظیمات سامانه فقط با مالک (مدیران و کارشناسان در «کاربران») ──');
{
  const {window,doc,errors}=await boot('manager');
  ok(await waitFor(()=>doc.querySelector('#admNav [data-sec="events"]')),'پنل با نشست مدیر بالا آمد');
  const navSet=doc.querySelector('#admNav [data-sec="settings"]');
  ok(navSet&&navSet.hasAttribute('data-locked'),'بخش تنظیمات در ریل مدیر قفل است (sys_settings فقط مالک؛ همان قاعدهٔ roles.py)');
  window.location.hash='#settings'; window.dispatchEvent(new window.HashChangeEvent('hashchange'));
  await wait(150);
  ok(!doc.querySelector('[data-sset]')&&!doc.querySelector('[data-sys-switch]'),'نشانی مستقیم #settings هم تنظیمات را برای مدیر باز نمی‌کند');
  ok(!CALLS.some(c=>c.path==='/api/owner/settings'),'بدون مجوز، /api/owner/settings اصلاً صدا زده نمی‌شود');
  ok(errors.filter(e=>!/401|403|favicon|preload/.test(e)).length===0,'بدون خطای اجرایی');
}
console.log(`\nadmin-settings-nora: ${checks} بررسی، ${fails} خطا`);
process.exit(fails?1:0);
