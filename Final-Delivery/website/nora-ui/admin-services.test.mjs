/* ══════════════════════════════════════════════════════════════════════════
   نورا · آزمون «اتصال سرویس‌ها» و «داده‌ها و مهاجرت» در پنل مدیران
   ──────────────────────────────────────────────────────────────────────────
   اجرا:  node admin-services.test.mjs   (بخشی از tools/run-unit-tests.cjs)

   این آزمون پنل را در حالت زنده (نه نمونهٔ محلی) با یک fetch جعلی بالا
   می‌آورد و قراردادهای امنیتی رابط را می‌سنجد: مقدار محرمانه در DOM نیست،
   فرم خالی چیزی نمی‌فرستد، تعویض توکن بدون تأیید انجام نمی‌شود، حذف فقط با
   تأیید صریح است، و نتیجهٔ آزمایش اتصال صادقانه نمایش داده می‌شود.
   ══════════════════════════════════════════════════════════════════════════ */
import {fileURLToPath} from 'node:url';
import jsdom from 'jsdom';
import fs from 'fs';

const {JSDOM}=jsdom;
const DIR=fileURLToPath(new URL('./',import.meta.url));
let fails=0, checks=0;
const ok=(c,m)=>{checks++; if(!c){fails++; console.log('   ✗ '+m);} else console.log('   ✓ '+m);};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function waitFor(fn,ms=4000){
  const end=Date.now()+ms;
  while(Date.now()<end){ try{ if(fn()) return true }catch(e){} await wait(25); }
  return false;
}

const SOURCE=fs.readFileSync(DIR+'admin.js','utf8');
const CALLS=[];
let PAYLOAD=null;
function statusPayload(){
  const field=(key,attribute,extra)=>Object.assign({
    key, service:'', label:'برچسب '+key, help:'راهنما', env_name:attribute,
    editable:true, acknowledge_restart:false, probe:false, configured:false,
    source:'none', hint:'', updated_at:null, encryption_ready:true, blocked_by:[],
    check:{checked:false,ok:null,code:'',checked_at:null}
  }, extra||{});
  return {
    encryption_ready:true,
    public_base_url:'https://nora.example',
    services:[
      {key:'bale',title:'بله و مینی‌اپ',icon:'i-send',summary:'توکن ربات و امضای مینی‌اپ',state:'configured',
       runtime:{ready:true,missing:[],scope:'web'},
       fields:[field('bale_bot','NORA_BALE_BOT_TOKEN',{service:'bale',label:'توکن ربات اصلی',
         acknowledge_restart:true,probe:true,configured:true,source:'database',hint:'…abcd',
         consumers:['web','bot'],bot_env_name:'BOT_TOKEN'})],
       readonly:[{env_name:'NORA_PUBLIC_BASE_URL',label:'نشانی عمومی سامانه',note:'دامنه',value:'https://nora.example',configured:true}]},
      {key:'sms',title:'پیامک و رمز یک‌بارمصرف',icon:'i-send',summary:'کلید سفیر',state:'unconfigured',
       fields:[field('safir_api_key','SAFIR_API_KEY',{service:'sms',label:'کلید سرویس سفیر'})],readonly:[]},
      {key:'payment',title:'پرداخت و کیف پول',icon:'i-wallet',summary:'توکن ربات پرداخت و Provider Token',state:'configured',
       runtime:{ready:false,missing:['NORA_FORM_PAYMENT_PROVIDER_TOKEN','NORA_FORM_PAYMENT_WEBHOOK_SECRET'],scope:'web'},
       fields:[field('bale_wallet','NORA_FORM_PAYMENT_BOT_TOKEN',{service:'payment',label:'توکن ربات پرداخت',
         probe:true,configured:true,source:'database',hint:'…wxyz',consumers:['web']}),
         field('payment_provider','NORA_FORM_PAYMENT_PROVIDER_TOKEN',{service:'payment',label:'توکن پرداخت کیف پول بله / Provider Token',consumers:['web']})],readonly:[]}
    ]
  };
}
function json(data,status=200){
  return new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
}
function findField(body){
  for(const service of PAYLOAD.services){
    const field=(service.fields||[]).find(item=>item.key===body.id);
    if(field) return field;
  }
  return null;
}
async function fakeFetch(url,init){
  const method=String(init&&init.method||'GET').toUpperCase();
  const path=String(url).split('?')[0];
  const body=init&&init.body?JSON.parse(init.body):null;
  CALLS.push({path,method,body});
  if(path==='/api/auth/me') return json({authenticated:true,owner_id:'owner-01',role:'owner',
    permissions:['sys_settings','sys_backup','sys_fields','rp_view','us_view','fm_create','fm_responses']});
  if(path==='/api/account/me') return json({detail:'authentication_required'},401);
  if(path==='/api/owner/service-settings'&&method==='GET') return json(PAYLOAD);
  if(path.startsWith('/api/owner/service-settings/')&&method==='PUT'){
    const field=findField({id:path.split('/').pop()});
    field.configured=true; field.source='database'; field.hint='…'+String(body.value).slice(-4);
    field.check={checked:false,ok:null,code:'',checked_at:null};
    return json(PAYLOAD);
  }
  if(path.endsWith('/test')&&method==='POST'){
    return json({ok:false,code:'bot_token_rejected',
      check:{checked:true,ok:false,code:'bot_token_rejected',checked_at:new Date().toISOString()}});
  }
  if(path.startsWith('/api/owner/service-settings/')&&method==='DELETE'){
    const field=findField({id:path.split('/').pop()});
    field.configured=false; field.source='none'; field.hint='';
    return json(PAYLOAD);
  }
  if(path==='/api/owner/data/status') return json({database:{engine:'postgresql',schema_version:'0025_service_checks'},
    staging:{retention_hours:72,max_bytes:268435456,used_bytes:0,outside_webroot:true},
    audit_tool_available:true,operational_writes:0});
  if(path==='/api/owner/data/uploads'&&method==='GET') return json({uploads:[],limits:{max_bytes:268435456,retention_hours:72},audit_tool_available:true});
  return json({detail:'not_found'},404);
}

async function boot(){
  PAYLOAD=statusPayload();
  const errors=[];
  const dom=await JSDOM.fromFile(DIR+'admin.html',{
    runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,
    beforeParse(w){
      w.fetch=(url,init)=>fakeFetch(url,init);
      w.scrollTo=()=>{};
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      w.addEventListener('error',e=>errors.push('error: '+e.message));
      w.console.error=(...a)=>errors.push('console.error: '+a.join(' '));
    }});
  const {window}=dom;
  await new Promise(resolve=>{
    if(window.document.readyState==='complete') return resolve();
    const timer=setTimeout(resolve,10000);
    window.addEventListener('load',()=>{clearTimeout(timer);resolve()},{once:true});
  });
  const doc=window.document;
  const click=sel=>{const el=typeof sel==='string'?doc.querySelector(sel):sel;
    if(!el) throw new Error('نیست: '+sel);
    el.dispatchEvent(new window.MouseEvent('click',{bubbles:true})); return el};
  return {window,doc,click,errors};
}

const {doc,click,errors}=await boot();
ok(await waitFor(()=>doc.querySelector('[data-sec="settings"]')),
  'پنل با نشست مالک بالا آمد');

console.log('\n── اتصال سرویس‌ها ──');
click('[data-sec="settings"]');
ok(await waitFor(()=>doc.querySelector('[data-sset-tiles]')&&doc.querySelector('[data-setg="texts"]')),'تنظیمات با کاشی‌های حوزه و گروه‌های طرح نورا باز شد');
click('[data-setg="data"]');
click('[data-setg="services"]');
ok(await waitFor(()=>doc.querySelector('#svcInput_bale_bot')),'ماژول اتصال سرویس‌ها با دادهٔ سرور رندر شد');
ok(doc.body.textContent.includes('بله و مینی‌اپ')&&doc.body.textContent.includes('پیامک و رمز یک‌بارمصرف')
  &&doc.body.textContent.includes('پرداخت و کیف پول'),'سه سرویس در تب‌ها دیده می‌شود');
const fieldInput=()=>doc.querySelector('#svcInput_bale_bot');
ok(fieldInput()&&fieldInput().getAttribute('type')==='password','ورودی توکن از نوع password است');
ok(!doc.body.innerHTML.includes('AAFakeTokenForPanelTest'),'مقدار کامل توکن در DOM نیست');
ok(doc.body.innerHTML.includes('…abcd'),'فقط سایهٔ مقدار ذخیره‌شده نمایش داده می‌شود');

let puts=CALLS.filter(call=>call.method==='PUT'&&call.path==='/api/owner/service-settings/bale_bot');
ok(puts.length===0,'تا این لحظه درخواست ذخیره‌ای ارسال نشده');
click('[data-svc-save="bale_bot"]');
await wait(60);
ok(puts.length===0,'ذخیرهٔ خالی هیچ درخواستی نمی‌فرستد');
ok(doc.body.textContent.includes('مقدار خالی ذخیره نمی‌شود'),'پیام «مقدار خالی» نمایش داده شد');

fieldInput().value='123456789:AAFakeTokenForPanelTest_0123456789';
click('[data-svc-save="bale_bot"]');
await wait(80);
ok(puts.length===0,'تعویض توکن بدون علامت‌زدن تأیید راه‌اندازی انجام نمی‌شود');
ok(doc.body.textContent.includes('راه‌اندازی دوبارهٔ ربات'),'پیام تأیید راه‌اندازی دیده می‌شود');

ok(doc.querySelector('#svcInput_bale_bot').value==='123456789:AAFakeTokenForPanelTest_0123456789',
  'مقدار تایپ‌شده پس از خطای اعتبارسنجی از دست نمی‌رود');
doc.querySelector('#svcAck_bale_bot').checked=true;
click('[data-svc-save="bale_bot"]');
ok(await waitFor(()=>CALLS.filter(call=>call.method==='PUT').length===1),'ذخیرهٔ توکن با تأیید ارسال شد');
const put=CALLS.filter(call=>call.method==='PUT')[0];
ok(put.path==='/api/owner/service-settings/bale_bot','مسیر ذخیره همان API یکپارچه است');
ok(put.body&&put.body.acknowledge_restart===true,'پرچم تأیید راه‌اندازی همراه درخواست است');
ok(String(put.body.value||'').startsWith('123456789:'),'مقدار فقط در بدنهٔ همان درخواست است');
ok(await waitFor(()=>doc.body.textContent.includes('مقدار ذخیره شد')),'پیام موفقیت ذخیره نمایش داده شد');
ok(doc.body.textContent.includes('…6789'),'فقط بخش پایانی مقدار نمایش داده می‌شود');

click('[data-svc-test="bale_bot"]');
ok(await waitFor(()=>CALLS.some(call=>call.path.endsWith('/test')&&call.method==='POST')),'آزمایش اتصال فراخوانی شد');
ok(await waitFor(()=>doc.body.textContent.includes('آزمایش اتصال ناموفق')),'نتیجهٔ ناموفق صادقانه گزارش شد');
ok(!doc.body.textContent.includes('آزمایش اتصال موفق'),'نتیجهٔ ناموفق به‌عنوان موفق نمایش داده نمی‌شود');

const deletes=()=>CALLS.filter(call=>call.method==='DELETE'&&call.path==='/api/owner/service-settings/bale_bot');
click('[data-svc-clear="bale_bot"]');
await wait(40);
ok(deletes().length===0,'کلیک حذف به‌تنهایی چیزی حذف نمی‌کند');
ok(doc.body.textContent.includes('بازگشت‌پذیر نیست'),'هشدار حذف نمایش داده شد');
click('[data-svc-clear-yes="bale_bot"]');
ok(await waitFor(()=>deletes().length===1),'حذف فقط پس از تأیید صریح انجام شد');

console.log('\n── وضعیت عملیاتی و دامنهٔ اثر ──');
ok(doc.querySelector('[data-svc-runtime="bale"][data-ready="1"]')!==null,'وضعیت عملیاتی وب برای بله از سرور نمایش داده شد');
ok(doc.body.textContent.includes('به معنی آزمایش موفق با سرویس بیرونی نیست'),'«فعال در وب» با «آزمایش‌شده» یکی گرفته نمی‌شود');
ok(doc.querySelector('[data-svc-scope="web+bot"]')!==null&&doc.body.textContent.includes('BOT_TOKEN')
  &&doc.body.textContent.includes('ربات باید جداگانه به‌روز و راه‌اندازی شود'),'دامنهٔ اثر توکن ربات (وب + ربات legacy) و نام متغیر ربات نمایش داده شد');
click('[data-svc-tab="payment"]');
ok(await waitFor(()=>doc.querySelector('[data-svc-runtime="payment"][data-ready="0"]')),'پرداخت با تنظیمات ناقص «غیرفعال در وب» گزارش شد');
ok(doc.body.textContent.includes('NORA_FORM_PAYMENT_PROVIDER_TOKEN')&&doc.body.textContent.includes('غیرفعال در وب'),'مقادیر ناقص پرداخت از سرور فهرست شدند');
ok(doc.body.textContent.includes('توکن ربات پرداخت')&&doc.body.textContent.includes('Provider Token'),'دو توکن پرداخت با نام‌های جدا نمایش داده می‌شوند');
ok(doc.querySelector('[data-svc-scope="web"]')!==null&&doc.body.textContent.includes('ربات legacy این مقدار را مصرف نمی‌کند'),'دامنهٔ اثر فقط-وب برای توکن پرداخت روشن است');
ok(!doc.body.textContent.includes('کلید کیف پول'),'برچسب قدیمی و مبهم «کلید کیف پول» دیگر نمایش داده نمی‌شود');
click('[data-svc-tab="bale"]');
ok(await waitFor(()=>doc.querySelector('#svcInput_bale_bot')),'بازگشت به تب بله');

console.log('\n── دامنه، امنیت و داده‌ها ──');
click('[data-sset-go="deploy"]');
ok(await waitFor(()=>doc.body.textContent.includes('دامنه و راه‌اندازی')),'ماژول دامنه رندر شد');
ok(doc.body.textContent.includes('NORA_PUBLIC_BASE_URL')&&doc.body.textContent.includes('https://nora.example'),
  'نشانی عمومی نمایش داده می‌شود');
ok(doc.body.textContent.includes('از پنل تغییر نمی‌کنند'),'ماهیت فقط‌خواندنی توضیح داده شده است');

click('[data-setg="security"]');
ok(await waitFor(()=>doc.body.textContent.includes('امنیت و دسترسی‌ها')),'ماژول امنیت رندر شد');
ok(doc.body.textContent.includes('sys_settings')&&doc.body.textContent.includes('sys_backup'),
  'مجوزهای مؤثر از سرور نمایش داده می‌شوند');

click('[data-setg="data"]');
ok(await waitFor(()=>doc.querySelector('[data-data-panel]')),'ماژول داده و مهاجرت زیر گروه «داده و پشتیبان» رندر شد');
ok(doc.querySelectorAll('[data-sset-row]').length>=4&&!doc.querySelector('[data-sset-row] [data-tog]'),'گزینه‌های بی‌endpoint فقط با وضعیت و دلیل می‌آیند، نه کلید نمایشی');
ok(await waitFor(()=>doc.body.textContent.includes('سقف هر فایل')),'سقف حجم از سرور نمایش داده شد');
ok(await waitFor(()=>doc.body.textContent.includes('بیرون ریشهٔ وب')),'محل staging توضیح داده شد');
ok(!CALLS.some(call=>call.method==='POST'&&call.path==='/api/owner/data/uploads'),'بدون انتخاب فایل درخواستی ارسال نشد');
click('[data-data-upload]');
await wait(60);
ok(!CALLS.some(call=>call.method==='POST'&&call.path==='/api/owner/data/uploads'),'بارگذاری بدون فایل انجام نمی‌شود');
ok(doc.body.textContent.includes('فایل SQLite انتخاب کنید'),'پیام انتخاب فایل نمایش داده شد');

click('[data-data-tab="database"]');
ok(await waitFor(()=>doc.body.textContent.includes('نسخهٔ شِمای فعلی')),'تب پایگاه‌های داده رندر شد');
ok(doc.body.textContent.includes('0025_service_checks'),'نسخهٔ شِما از سرور نمایش داده شد');
ok(doc.body.textContent.includes('صفر'),'نوشتن روی پایگاه عملیاتی صفر گزارش می‌شود');
click('[data-data-tab="reports"]');
ok(await waitFor(()=>doc.body.textContent.includes('گزارش‌های ممیزی')||doc.body.textContent.includes('هنوز گزارشی ثبت نشده')),
  'تب گزارش‌های ممیزی رندر شد');

console.log('\n── پاکی و یکتایی ──');
ok(!SOURCE.includes('WALLET_KEY_API')&&!SOURCE.includes('payment-settings'),
  'کلید کیف پول فقط از API یکپارچه می‌آید و مسیر قدیمی حذف شده است');
ok(!SOURCE.includes('api_key:value'),'فرم قدیمی کیف پول در admin.js نمانده است');
ok(errors.length===0,'هیچ خطای اجرایی در کنسول ثبت نشد'+(errors.length?': '+errors.join(' | '):''));

console.log(`\nadmin-services-test: ${checks} بررسی، ${fails} خطا`);
process.exitCode=fails?1:0;
