/* موتور انتخاب و سفارشی‌سازی فیلدهای فرم‌ساز (create.html)
   اجرا: node builder-fields.test.mjs
   پوشش: منبع واحد نوع/الگو و تطبیق آن با قرارداد سرور، دروازهٔ قابلیت در همهٔ مسیرهای افزودن، وضعیت‌های قابلیت،
   جست‌وجوی فارسی، ویرایشگرِ ذخیره/انصراف، جابه‌جایی گزینه‌ها، تغییر نوع امن، ماتریس مدل×تنظیم، وضعیت ذخیره، نگاشت خطای سرور. */
import {JSDOM} from 'jsdom';
import {readFileSync} from 'node:fs';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {dirname} from 'node:path';

const DIR=dirname(fileURLToPath(import.meta.url))+'/';
let checks=0, fails=0;
const ok=(condition,message)=>{checks++; if(!condition){fails++; console.log('   ✗ '+message)}else console.log('   ✓ '+message)};
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function makeStore(init={}){
  const m=new Map(Object.entries(init));
  return {getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k),
    clear:()=>m.clear(),key:i=>[...m.keys()][i],get length(){return m.size}};
}
/* قرارداد قابلیت‌ها مستقیماً از کد سرور خوانده می‌شود تا آزمون با backend هم‌خوان بماند (نه یک فهرست دستی دوم) */
const PY_RESPONSES=readFileSync(DIR+'backend/responses.py','utf8'), PY_CAPS=readFileSync(DIR+'backend/form_capabilities.py','utf8');
function pyStrings(block){return [...block.matchAll(/"([a-z_]+)"/g)].map(m=>m[1])}
function pyAssign(source,name){
  const match=source.match(new RegExp('^'+name+'\\s*=\\s*([^\\n]*\\{[\\s\\S]*?\\})','m'));
  if(!match)throw new Error('پیدا نشد: '+name);
  return match[1];
}
function pyDictKeys(source,name){
  const match=source.match(new RegExp('^'+name+'\\s*=\\s*\\{([\\s\\S]*?)\\n\\}','m'));
  if(!match)throw new Error('پیدا نشد: '+name);
  return [...match[1].matchAll(/^\s*"([a-z_]+)":/gm)].map(m=>m[1]);
}
const UPLOAD_TYPES=pyStrings(pyAssign(PY_RESPONSES,'UPLOAD_FIELD_TYPES'));
const unsupportedExpr=pyAssign(PY_RESPONSES,'UNSUPPORTED_FIELD_TYPES');
const SERVER_UNSUPPORTED=[...new Set([...(unsupportedExpr.includes('UPLOAD_FIELD_TYPES')?UPLOAD_TYPES:[]),...pyStrings(unsupportedExpr)])];
const SERVER_SUPPORTED=pyStrings(pyAssign(PY_RESPONSES,'SUPPORTED_PUBLIC_FIELD_TYPES'));
const SERVER_LIMITED=pyDictKeys(PY_CAPS,'FIELD_LIMITATIONS');
function serverContract(){
  const field_types={};
  SERVER_SUPPORTED.forEach(t=>{field_types[t]={status:SERVER_LIMITED.includes(t)?'limited':'server',reason:SERVER_LIMITED.includes(t)?'محدودیت سروری':''}});
  SERVER_UNSUPPORTED.forEach(t=>{field_types[t]={status:'unavailable',reason:'در فرم عمومی سرور وصل نیست'}});
  return {version:1,source:'same_application_fastapi',api_configured:true,
    models:['registration','questionnaire','survey','contest','exam','attendance','datacollect','election'].map(id=>({id,status:id==='registration'?'server':'limited',publishable:true,reason:''}))
      .concat([{id:'order',status:'unavailable',publishable:false,reason:'سفارش آماده نیست'}]),
    field_types,
    field_settings:{length:{status:'server',types:['address','area','fullname','location','text'],keys:['minLen','maxLen'],max_by_type:{address:1000,area:3000,fullname:120,location:180,text:1000}},
      integer:{status:'server',types:['amount','number'],keys:['integer'],reason:'با روشن‌بودن، عدد اعشاری در فرم عمومی و سرور رد می‌شود؛ گام تغییر یا تعداد رقم اعشار تنظیم‌پذیر نیست.'},
      placeholder:{status:'client_display',keys:['placeholder'],max_length:120},temporal_bounds:{status:'unavailable',types:['date','time','datetime','slot'],keys:[]}},
    settings:{response_list:{status:'server',page_size_max:100},schedule:{status:'unavailable'},one_response_per_person:{status:'unavailable'},
      companions:{status:'conditional',models:['registration'],reason:'فقط ثبت‌نام'},
      survey_scoring:{status:'unavailable',models:['survey'],reason:'امتیاز فقط در پیش‌نمایش محلی فرم‌ساز است.'}}};
}
function makeApi({id='server-form-1',capabilities='ready',initialRecord=null,readinessIssues=[],saveStatus=null}={}){
  const calls=[]; let record=initialRecord;
  const response=(status,payload)=>({ok:status>=200&&status<300,status,json:async()=>payload});
  const fetch=async(path,init={})=>{
    const method=String(init.method||'GET').toUpperCase();
    calls.push({path,method,body:init.body||''});
    if(path==='/api/health')return response(200,{ok:true,formsEnabled:true,responsesEnabled:true,deliveryEnabled:false,formBalePaymentsReady:false});
    if(path==='/api/public/forms/capabilities'){
      if(capabilities==='pending')return new Promise(()=>{});
      if(capabilities==='reject')return response(503,{detail:'unavailable'});
      return response(200,serverContract());
    }
    if(path==='/api/auth/me')return response(200,{authenticated:true,owner_id:'owner-smoke',role:'owner'});
    if(path==='/api/account/me')return response(200,{authenticated:true,account_id:'owner-smoke',role:'owner',permissions:['fm_create','finance']});
    if(path==='/api/forms'&&method==='POST'){
      if(saveStatus)return response(saveStatus,{detail:saveStatus===409?'version_conflict':'server_error'});
      const body=JSON.parse(init.body||'{}');
      record={id,name:body.name,model:body.model,need:body.need,slug:body.slug,ev:body.ev,fields:body.fields,settings:body.settings,status:'draft',version:1,response_count:0,
        created_at:'2026-01-01T00:00:00+00:00',updated_at:'2026-01-01T00:00:00+00:00'};
      return response(201,record);
    }
    if(path==='/api/forms/'+id&&method==='PUT'){
      if(saveStatus)return response(saveStatus,{detail:saveStatus===409?'version_conflict':'server_error'});
      const body=JSON.parse(init.body||'{}');
      record={...record,name:body.name,model:body.model,need:body.need,slug:body.slug,ev:body.ev,fields:body.fields,settings:body.settings,status:'draft',version:(record.version||1)+1};
      return response(200,record);
    }
    if(path==='/api/forms/'+id+'/readiness'&&method==='GET')return record?response(200,{source:'same_server_database',form_id:id,version:record.version||1,status:record.status||'draft',publishable:!readinessIssues.length,issues:readinessIssues}):response(404,{detail:'form_not_found'});
    if(path==='/api/forms'&&method==='GET')return response(200,{items:record?[record]:[],total:record?1:0,limit:100,has_more:false});
    if(path==='/api/forms/'+id&&method==='GET')return record?response(200,record):response(404,{detail:'form_not_found'});
    return response(404,{detail:'not_found'});
  };
  return {fetch,calls,get record(){return record},set record(v){record=v}};
}
async function load({store=makeStore(),query='',api=null,fixtureMode=true}={}){
  const errors=[], url=pathToFileURL(DIR+'create.html').href+query;
  const dom=await JSDOM.fromFile(DIR+'create.html',{...(query?{url}:{}),runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,
    beforeParse(w){
      w.scrollTo=()=>{}; if(w.Element&&!w.Element.prototype.scrollIntoView)w.Element.prototype.scrollIntoView=()=>{};
      if(!w.matchMedia)w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      Object.defineProperty(w,'localStorage',{configurable:true,value:store});
      w.__NORA_TEST_FIXTURE_MODE__=fixtureMode===true;
      w.fetch=(...args)=>api?Promise.resolve(api.fetch(...args)):Promise.reject(new Error('network disabled'));
      w.addEventListener('error',e=>errors.push('error: '+(e.message||'')));
      w.console.error=(...args)=>errors.push('console.error: '+args.join(' '));
    }});
  const {window}=dom;
  if(window.document.readyState!=='complete')await new Promise(resolve=>{const t=setTimeout(resolve,5000);window.addEventListener('load',()=>{clearTimeout(t);resolve()},{once:true})});
  await wait(80);
  const doc=window.document;
  return {window,doc,store,errors,
    click:selector=>{const el=doc.querySelector(selector);if(!el)throw new Error('نیست: '+selector);el.dispatchEvent(new window.MouseEvent('click',{bubbles:true,cancelable:true}))},
    key:(selector,key)=>{const el=selector?doc.querySelector(selector):doc.activeElement;el.dispatchEvent(new window.KeyboardEvent('keydown',{key,bubbles:true,cancelable:true}))},
    input:(selector,value)=>{const el=doc.querySelector(selector);if(!el)throw new Error('نیست: '+selector);el.value=value;el.dispatchEvent(new window.Event('input',{bubbles:true}));el.dispatchEvent(new window.Event('change',{bubbles:true}))},
    set:(selector,value)=>{const el=doc.querySelector(selector);if(!el)throw new Error('نیست: '+selector);el.value=value;el.dispatchEvent(new window.Event('change',{bubbles:true}))},
    txt:selector=>{const el=doc.querySelector(selector);return el?el.textContent.replace(/\s+/g,' ').trim():''},
    all:selector=>[...doc.querySelectorAll(selector)],
    ev:code=>window.eval(code)};
}
const html=readFileSync(DIR+'create.html','utf8');

/* ── ۱) منبع واحد نوع/الگو و تطبیق با سرور ── */
{
  console.log('\n── منبع واحد نوع/الگو ──');
  const p=await load({api:makeApi()});
  const types=p.ev('Object.keys(FIELD_TYPES)'), serverAll=[...new Set([...SERVER_SUPPORTED,...SERVER_UNSUPPORTED])].sort();
  ok(JSON.stringify([...types].sort())===JSON.stringify(serverAll),'کلیدهای FIELD_TYPES دقیقاً همان نوع‌های قرارداد سرور (SUPPORTED ∪ UNSUPPORTED) هستند');
  ok(JSON.stringify(p.ev('[...LOCAL_ONLY_TYPES].sort()'))===JSON.stringify([...SERVER_UNSUPPORTED].sort()),'فهرست نوع‌های فقط‌محلیِ فرم‌ساز با UNSUPPORTED_FIELD_TYPES سرور یکی است');
  const ks=p.ev('CATALOG.map(c=>c.k)');
  ok(new Set(ks).size===ks.length&&ks.includes('birth-date')&&ks.includes('jalali-date'),'شناسهٔ الگوها یکتاست و دو الگوی هم‌نوع تاریخ شناسهٔ جدا دارند');
  ok(p.ev("CATALOG.filter(c=>c.t==='date').length===2&&freshField('birth-date',1).l==='تاریخ تولد'&&freshField('jalali-date',2).l==='تاریخ شمسی'&&freshField('birth-date',1).preset==='birth-date'&&freshField('jalali-date',2).t==='date'"),
    'دو الگوی تاریخ برچسب و شناسهٔ خودشان را می‌گیرند (نه برچسب اولین مورد هم‌نوع)');
  ok(p.ev("typeOf('date').n==='تاریخ'&&byT('date').n==='تاریخ'&&presetOf('date').k==='date'&&presetOf('date').n==='تاریخ'&&freshField('date',5).l==='تاریخ'&&freshField('date',5).preset==='date'"),'الگوی عمومی یک نوع خود نوع است؛ هیچ الگوی هم‌نوعی (تاریخ تولد) بی‌صدا تحمیل نمی‌شود');
  ok(p.ev("presetsOfType('date').map(c=>c.k).join(',')==='birth-date,jalali-date'&&presetsOfType('text').length===1"),'الگوهای هم‌نوع یک نوع فنی قابل‌شمارش‌اند (تاریخ: تولد و شمسی)');
  ok(p.ev("CATALOG.every(c=>c.n&&c.ans&&c.g&&FIELD_CATEGORIES.some(g=>g.id===c.g)&&Array.isArray(typeOf(c.t).ctl))"),'هر ردیف کاتالوگ نام، نوع پاسخ، دستهٔ معتبر و فهرست تنظیم‌های نوع دارد');
  ok(p.ev("FIELD_TYPES.time.n!==FIELD_TYPES.slot.n&&FIELD_TYPES.slot.n.includes('بدون رزرو')&&FIELD_TYPES.imgchoice.n.includes('بدون تصویر')"),'ساعت و بازهٔ ساعت و انتخاب کارتی نام‌های صادقانه و متمایز دارند');
  ok(p.ev("PACKS.find(x=>x.id==='max').f.every(k=>!LOCAL_ONLY_TYPES.has(presetOf(k).t))&&PACKS.find(x=>x.id==='max').f.includes('birth-date')"),'بستهٔ «کامل‌تر» دیگر نوع بارگذاری ندارد و الگوی تاریخ تولد را با شناسهٔ پایدار می‌آورد');
  ok(p.ev("S.fields.length===7&&S.fields.find(f=>f.t==='date').preset==='birth-date'&&S.fields.find(f=>f.t==='date').l==='تاریخ تولد'"),'بستهٔ پیش‌فرض فرم تازه پس از دریافت قرارداد چیده می‌شود و الگوی تاریخ تولد را درست می‌سازد');
  const legacy=p.ev("JSON.stringify(restoreField({id:'x',t:'date',l:'تاریخ عقد',preset:'nonexistent'},9))");
  ok(JSON.parse(legacy).l==='تاریخ عقد'&&JSON.parse(legacy).preset==='date'&&JSON.parse(legacy).id==='x','بازیابی فیلد قدیمی برچسب را نگه می‌دارد و شناسهٔ الگوی نامعتبر را به الگوی عمومی نوع (نه تاریخ تولد) برمی‌گرداند');
  ok(p.ev("restoreField({id:'j',t:'date',l:'تاریخ شمسی',preset:'jalali-date'},8).preset==='jalali-date'&&restoreField({id:'b',t:'date',l:'تاریخ تولد',preset:'birth-date'},9).preset==='birth-date'"),'بازیابی، شناسهٔ الگوی معتبرِ هر دو الگوی تاریخ را دست‌نخورده نگه می‌دارد');
  ok(p.ev("restoreField({id:'y',t:'image',l:'عکس'},2).t==='image'&&typeOf('mystery').legacy===1&&restoreField({id:'z',t:'mystery',l:'ناشناخته'},3).t==='mystery'"),'نوع پشتیبانی‌نشده یا ناشناخته در بازیابی حذف یا تبدیل خاموش نمی‌شود');
  ok(!/find\(c=>c\.t===t\)|find\(x=>x\.t===f\.t\)|find\(x=>x\.t===t\)/.test(html),'هیچ جست‌وجوی «اولین مورد با همین نوع» برای برچسب/پیش‌فرض در کد نمانده است');
  ok(p.errors.length===0,'بارگذاری بدون خطای کنسول');
}

/* ── ۲) کاتالوگ: وضعیت‌ها، جست‌وجو، دسته‌ها، سقف، دوبار کلیک ── */
{
  console.log('\n── کاتالوگ و جست‌وجو ──');
  const p=await load({api:makeApi()});
  p.ev("S.fields=[];renderCanvas()");p.click('#addTop');
  ok(p.doc.querySelector('#shAdd').classList.contains('on')&&p.all('#catChips button[data-cat][aria-pressed]').length>=8
      &&p.doc.querySelector('#catChips [data-cat="all"]').getAttribute('aria-pressed')==='true','دسته‌ها دکمهٔ واقعی با aria-pressed هستند و «همه» پیش‌فرض است');
  ok(p.txt('#catCount').includes('نوع فیلد')&&!p.all('#catList [data-add]').some(b=>b.dataset.type==='select'),'شمار نتیجه‌ها نمایش داده می‌شود و نوع قدیمی select در کاتالوگ نیست');
  ok(p.doc.querySelector('#catList [data-add="image"]').disabled&&p.doc.querySelector('#catList [data-add="image"]').textContent.includes('غیرفعال')
      &&p.doc.querySelector('#catList [data-add="image"]').textContent.includes('وصل نیست'),'ردیف بارگذاری با وضعیت واقعی سرور غیرفعال است و دلیل را کنار خودش می‌گوید');
  ok(!p.doc.querySelector('#catList [data-add="birth-date"]').disabled&&p.doc.querySelector('#catList [data-add="birth-date"]').textContent.includes('پاسخ:')
      &&p.doc.querySelector('#catList [data-add="mobile"] .cap-tag.limited'),'ردیف فعال نوع پاسخ و برچسب قابلیت (سروری با محدودیت) را نشان می‌دهد');
  p.click('#catChips [data-cat="time"]');
  const timeRows=p.all('#catList [data-add]').map(b=>b.dataset.add);
  ok(timeRows.includes('jalali-date')&&timeRows.includes('slot')&&!timeRows.includes('birth-date')&&p.doc.querySelector('#catChips [data-cat="time"]').getAttribute('aria-pressed')==='true'
      &&p.doc.activeElement===p.doc.querySelector('#catChips [data-cat="time"]'),'فیلتر دسته فقط الگوهای همان دسته را می‌آورد و تمرکز روی دکمهٔ دسته می‌ماند');
  p.click('#catChips [data-cat="all"]');
  const first=q=>{p.input('#catSearch',q);return p.all('#catList [data-add]').map(b=>b.dataset.add)};
  ok(first('شماره همراه')[0]==='mobile'&&first('کد ملی')[0]==='nid'&&first('پذیرش قوانین')[0]==='terms','عبارت‌های طبیعی (شماره همراه، کد ملی، پذیرش قوانین) اول نتیجه می‌آیند');
  ok(first('كد ملي')[0]==='nid'&&first('ايميل')[0]==='email'&&first('۰۹')[0]==='mobile'&&first('شماره‌همراه')[0]==='mobile','ی/ي، ک/ك، رقم فارسی و نیم‌فاصله در جست‌وجو یکسان‌سازی می‌شوند');
  ok(first('تاریخ').includes('birth-date')&&first('تاریخ').includes('jalali-date')&&p.txt('#catCount').includes('نتیجه'),'جست‌وجوی «تاریخ» هر دو الگوی هم‌نوع را با شمار نتیجه می‌آورد');
  p.input('#catSearch','xyzناموجود');
  ok(!p.all('#catList [data-add]').length&&p.txt('#catList').includes('پیدا نشد')&&p.doc.querySelector('#catList [data-cat-reset]'),'نتیجهٔ خالی راه‌حل (نمایش همه) دارد');
  p.click('#catList [data-cat-reset]');
  ok(p.doc.querySelector('#catSearch').value===''&&p.all('#catList [data-add]').length>20,'بازنشانی جست‌وجو همهٔ انواع را برمی‌گرداند');
  const before=p.ev('S.fields.length');
  p.click('#catList [data-add="nid"]');p.click('#catList [data-add="nid"]');
  ok(p.ev('S.fields.length')===before+1&&p.ev("S.fields[S.fields.length-1].t==='nid'")&&p.doc.querySelector('#shField').classList.contains('on'),'دوبار کلیک پیاپی روی یک ردیف فقط یک فیلد می‌سازد و ویرایشگر آن باز می‌شود');
  p.ev("S.fields=Array.from({length:30},(_,i)=>freshField('text',i+1));renderCanvas()");p.click('#addTop');
  ok(p.all('#catList [data-add]').every(b=>b.disabled)&&p.txt('#catList').includes('سقف')&&p.ev("addField('text')===null"),'در سقف ۳۰ فیلد همهٔ ردیف‌ها با دلیل غیرفعال‌اند و افزودن برنامه‌ای هم رد می‌شود');
  ok(p.errors.length===0,'کاتالوگ بدون خطای کنسول');
}

/* ── ۳) وضعیت‌های قابلیت: در انتظار، خطا، مسیرهای غیرمستقیم ── */
{
  console.log('\n── وضعیت‌های قابلیت و مسیرهای غیرمستقیم ──');
  const pending=await load({api:makeApi({capabilities:'pending'})});
  pending.click('#addTop');
  ok(pending.ev("FORM_CAPABILITY_STATE==='checking'&&fieldSupport('text').status==='pending'")&&pending.all('#catList [data-add]').every(b=>b.disabled)
      &&pending.txt('#catList').includes('در انتظار تأیید سرور')&&pending.ev("S.fields.length===0&&addField('text')===null"),'تا رسیدن قرارداد، هیچ نوعی قابل‌افزودن نیست و وضعیت «در انتظار تأیید سرور» است (نامشخص ≠ قابل‌استفاده)');
  const broken=await load({api:makeApi({capabilities:'reject'})});
  broken.click('#addTop');
  ok(broken.ev("FORM_CAPABILITY_STATE==='unavailable'&&fieldSupport('text').status==='error'&&fieldSupport('image').addable===false")
      &&broken.txt('#catList').includes('وضعیت سرور نامشخص')&&broken.doc.querySelector('#catList [data-add="image"]').disabled&&!broken.doc.querySelector('#catList [data-add="text"]').disabled,
    'خطای دریافت قرارداد وضعیت جداگانه دارد: نوع‌های سروری با برچسب صریح قابل‌ساخت‌اند، بارگذاری هرگز');
  const p=await load({api:makeApi()});
  p.ev("S.fields=[];renderCanvas()");
  p.ev("SAVED_PACKS=[{id:'old',name:'بستهٔ قدیمی',fields:[{id:1,t:'fullname',l:'نام'},{id:2,t:'image',l:'عکس'},{id:3,t:'sign',l:'امضا'}]}];applyPack('saved:old','replace')");
  ok(p.ev("S.fields.length===1&&S.fields[0].t==='fullname'")&&p.txt('#toast').includes('۲ فیلد')&&p.txt('#toast').includes('بارگذاری تصویر'),'بستهٔ ذخیره‌شدهٔ مرورگر با نوع پشتیبانی‌نشده از همان دروازه می‌گذرد: کنار گذاشته و گزارش می‌شود');
  p.ev("applyPack('max','replace')");
  ok(p.ev("S.fields.length===12&&S.fields.every(f=>fieldSupport(f.t).addable)&&S.fields.some(f=>f.preset==='birth-date')"),'بستهٔ کامل‌تر ۱۲ فیلد قابل‌انتشار می‌سازد');
  p.ev("S.fields=[restoreField({id:'legacy-img',t:'image',l:'عکس پرسنلی'},1),freshField('text','t2')];renderCanvas()");
  const block=p.doc.querySelector('[data-block="legacy-img"]');
  ok(block&&block.textContent.includes('نیاز به اصلاح')&&block.querySelector('.cap-tag.unavailable')&&p.doc.querySelector('[data-edit="legacy-img"]'),'فیلد قدیمی بارگذاری ناپدید نمی‌شود: در بوم با نشان «نیاز به اصلاح» و دکمهٔ ویرایش می‌ماند');
  p.click('[data-copy="legacy-img"]');
  ok(p.ev('S.fields.length')===2&&p.txt('#toast').includes('قابل‌افزودن نیست'),'کپی فیلد پشتیبانی‌نشده از دروازهٔ قابلیت رد می‌شود');
  p.click('[data-edit="legacy-img"]');
  const targets=p.all('#fdTypeChange option').map(o=>o.value).filter(Boolean);
  ok(p.doc.querySelector('#shField').classList.contains('on')&&targets.includes('text')&&targets.includes('area')&&!targets.includes('file')
      &&p.txt('#fdTypeNote').includes('اجرا نمی‌شود')&&p.doc.querySelector('#fdCountBox').style.display==='block','ویرایشگر فیلد قدیمی راه اصلاح می‌دهد: تغییر نوع به متن/متن بلند یا حذف؛ تنظیم‌های قدیمی برای مرور می‌مانند');
  p.set('#fdTypeChange','area');p.click('#fdTypeApply');
  ok(!p.doc.querySelector('#fdTypeConfirm').hidden&&p.txt('#fdTypeConsequences').includes('فایل'),'پیش از تغییر نوع، پیامدها (حذف تنظیم‌های فایل) نشان داده می‌شود');
  p.click('#fdTypeConfirmGo');
  ok(p.ev("S.fields[0].t==='area'&&S.fields[0].l==='عکس پرسنلی'&&fieldSupport(S.fields[0].t).addable")&&p.ev("fieldEditorDirty()")===true,'تغییر نوع عنوان را نگه می‌دارد و تا «ذخیره» به‌عنوان تغییر ذخیره‌نشده شمرده می‌شود');
  p.click('#fdSave');
  ok(!p.doc.querySelector('#shField').classList.contains('on')&&p.ev("S.fields[0].t==='area'&&S.fields[0].count===5&&S.fields[0].accept===''")&&!p.doc.querySelector('[data-block="legacy-img"]').textContent.includes('نیاز به اصلاح'),'پس از ذخیره، فیلد اصلاح‌شده بدون نشان خطا و بدون تنظیم‌های فایل می‌ماند');
  ok(p.errors.length===0,'مسیرهای غیرمستقیم بدون خطای کنسول');
}

/* ── ۴) ویرایشگر: ذخیره/انصراف، گزینه‌ها، اعتبارسنجی، تغییر نوع با شرط ── */
{
  console.log('\n── ویرایشگر فیلد ──');
  const p=await load({api:makeApi()});
  p.ev(`S.fields=[Object.assign(freshField('choice','q1'),{l:'رنگ',opts:[{l:'قرمز',score:1},{l:'آبی',score:2},{l:'سبز',score:3}]}),
    Object.assign(freshField('text','q2'),{l:'چرا؟',conditions:[{field:'q1',op:'eq',value:'آبی'}],conditionLogic:'all'})];renderCanvas();go('s2')`);
  p.click('[data-edit="q1"]');
  ok(p.doc.querySelector('[data-optup="0"]').disabled&&!p.doc.querySelector('[data-optdown="0"]').disabled&&p.doc.querySelector('[data-optdown="2"]').disabled&&!p.doc.querySelector('[data-optup="2"]').disabled,
    'دکمه‌های بالا/پایین در ابتدا و انتهای فهرست غیرفعال‌اند');
  p.click('[data-optdown="0"]');
  ok(p.ev("JSON.stringify(S.fields[0].opts.map(o=>o.l+':'+o.score))")==='["آبی:2","قرمز:1","سبز:3"]'&&p.doc.activeElement===p.doc.querySelector('[data-optdown="1"]')&&p.txt('#fdOptionCount').includes('جایگاه ۲'),
    'جابه‌جایی واقعی است (امتیاز همراه گزینه می‌رود)، تمرکز روی همان دکمه در جای تازه می‌ماند و اعلام می‌شود');
  p.click('[data-optdown="1"]');
  ok(p.ev("S.fields[0].opts.map(o=>o.l).join()")==='آبی,سبز,قرمز'&&p.doc.activeElement===p.doc.querySelector('[data-optup="2"]'),'در انتهای فهرست، تمرکز به دکمهٔ «بالا» همان ردیف می‌رود (دکمهٔ غیرفعال تمرکز نمی‌گیرد)');
  p.click('#shField [data-close]');
  ok(p.doc.querySelector('#shField').classList.contains('on')&&!p.doc.querySelector('#fdDiscardBar').hidden&&p.doc.activeElement===p.doc.querySelector('#fdDiscardYes'),'بستن با تغییر ذخیره‌نشده بی‌صدا دور نمی‌ریزد؛ نوار تأیید باز می‌شود');
  p.click('#fdDiscardNo');
  ok(p.doc.querySelector('#fdDiscardBar').hidden&&p.doc.querySelector('#shField').classList.contains('on'),'«ادامهٔ ویرایش» نوار را می‌بندد و ویرایشگر می‌ماند');
  p.key('#fdTitle','Escape');
  ok(!p.doc.querySelector('#fdDiscardBar').hidden,'Escape هم همان مسیر تأیید را می‌رود');
  p.click('#fdDiscardYes');
  ok(!p.doc.querySelector('#shField').classList.contains('on')&&p.ev("S.fields[0].opts.map(o=>o.l).join()")==='قرمز,آبی,سبز'&&p.doc.activeElement===p.doc.querySelector('[data-edit="q1"]'),
    '«بستن بدون ذخیره» ترتیب اولیهٔ گزینه‌ها را برمی‌گرداند و تمرکز به دکمهٔ ویرایش همان پرسش بازمی‌گردد');
  p.click('[data-edit="q1"]');p.click('[data-optdown="0"]');p.click('#fdSave');
  ok(!p.doc.querySelector('#shField').classList.contains('on')&&p.ev("S.fields[0].opts.map(o=>o.l).join()")==='آبی,قرمز,سبز'&&p.ev("buildDraftRow().fields[0].opts.map(o=>o.l).join()")==='آبی,قرمز,سبز',
    '«ذخیره» ترتیب تازه را در فیلد و در payload سرور ثبت می‌کند');
  p.click('[data-edit="q1"]');p.input('#fdTitle','رنگ دلخواه');p.click('#scrim');
  ok(p.doc.querySelector('#shField').classList.contains('on')&&!p.doc.querySelector('#fdDiscardBar').hidden,'کلیک بیرون ورقه با عنوان تغییرکرده هم بی‌صدا نمی‌بندد');
  p.click('#fdDiscardYes');
  ok(p.ev("S.fields[0].l==='رنگ'"),'انصراف عنوان تایپ‌شده را اعمال نمی‌کند');
  p.click('[data-edit="q1"]');p.click('#shField [data-close]');
  ok(!p.doc.querySelector('#shField').classList.contains('on'),'بستن بدون تغییر بی‌پرسش می‌بندد');
  p.ev("S.fields.push(Object.assign(freshField('scale','q3'),{l:'میزان'}));renderCanvas();editField('q3')");
  ok(p.doc.querySelector('#fdBoundsBox').style.display==='block'&&p.txt('#fdBoundsLabel').includes('۰')&&p.txt('#fdBoundsLabel').includes('۱۰'),'بازهٔ عددی برای طیف ۰ تا ۱۰ هم تنظیم‌پذیر است (هم‌خوان با بررسی سرور)');
  p.set('#fdMin','۲');p.set('#fdMax','۱۲');p.click('#fdSave');
  ok(p.doc.querySelector('#shField').classList.contains('on')&&!p.doc.querySelector('#fdIssues').hidden&&p.txt('#fdIssues').includes('۱۰')&&p.ev("S.fields[2].max===''||S.fields[2].max==null"),'ذخیرهٔ نامعتبر پنجره را نمی‌بندد، خطا داخل ویرایشگر نشان داده می‌شود و مقدار قبلی می‌ماند');
  p.set('#fdMax','۸');p.click('#fdSave');
  ok(!p.doc.querySelector('#shField').classList.contains('on')&&p.ev("S.fields[2].min===2&&S.fields[2].max===8"),'بازهٔ معتبر ذخیره می‌شود');
  p.ev("editField('q3')");
  ok(p.doc.querySelector('#fdMin').value==='2'&&p.doc.querySelector('#fdMax').value==='8'&&p.doc.querySelector('#fdScoreBox').style.display==='none','بازکردن دوباره مقدارها را برمی‌گرداند؛ امتیازدهی خارج از نظرسنجی دیده نمی‌شود');
  p.click('#fdCancel');
  p.ev("S.model='survey';S.need='survey';editField('q3')");
  ok(p.doc.querySelector('#fdScoreBox').style.display==='block'&&p.txt('#fdSecScore').includes('فقط پیش‌نمایش محلی')&&p.txt('#fdScoreServerNote').includes('پیش‌نمایش محلی'),'امتیازدهی نظرسنجی صریحاً «فقط پیش‌نمایش محلی» است و متن وضعیت از قرارداد سرور می‌آید');
  ok(p.all('#shField [data-media]').filter(c=>c.dataset.media!=='none').every(c=>c.disabled)&&p.txt('#shField').includes('در دست ساخت'),'رسانهٔ همراه پرسش غیرفعال با دلیل است، نه تنظیمِ فعال‌نما');
  p.click('#fdCancel');
  p.ev("S.model='registration';S.need='reg';editField('q1')");
  p.set('#fdTypeChange','multi');p.click('#fdTypeApply');
  ok(p.txt('#fdTypeConsequences').includes('قاعدهٔ شرطی')&&p.txt('#fdTypeConsequences').includes('حذف'),'تغییر تک‌انتخاب به چندانتخاب هشدار می‌دهد که شرطِ «برابر» پرسش بعدی سازگار نیست');
  p.click('#fdTypeCancel');
  ok(p.doc.querySelector('#fdTypeConfirm').hidden&&p.ev("S.fields[0].t==='choice'"),'انصراف از تغییر نوع چیزی را عوض نمی‌کند');
  p.set('#fdTypeChange','dropdown');p.click('#fdTypeApply');p.click('#fdTypeConfirmGo');p.click('#fdSave');
  ok(p.ev("S.fields[0].t==='dropdown'&&S.fields[0].opts.length===3&&S.fields[1].conditions.length===1&&firstInvalidCondition()===null"),'تک‌انتخاب → کشویی گزینه‌ها و شرط وابسته (عملگر سازگار) را نگه می‌دارد');
  p.ev("editField('q1')");p.set('#fdTypeChange','multi');p.click('#fdTypeApply');p.click('#fdTypeConfirmGo');p.click('#fdSave');
  ok(p.ev("S.fields[0].t==='multi'&&S.fields[1].conditions.length===0&&firstInvalidCondition()===null"),'پس از تغییر به چندانتخاب، شرط ناسازگار حذف می‌شود (نه این‌که خاموش بماند و انتشار را بشکند)');
  ok(p.ev("typeChangeTargets('rating').sort().join()==='bars,scale'&&typeChangeTargets('date').includes('datetime')&&!typeChangeTargets('text').includes('choice')"),'مقصدهای تغییر نوع فقط هم‌خانواده‌اند');
  ok(p.errors.length===0,'ویرایشگر بدون خطای کنسول');
}

/* ── ۵) ماتریس مدل × تنظیم ── */
{
  console.log('\n── ماتریس مدل ──');
  const p=await load({api:makeApi()});
  p.click('#tiles [data-model="survey"]');
  ok(p.doc.querySelector('#companionBody').hidden&&!p.doc.querySelector('#companionModelNote').hidden&&p.doc.querySelector('#ticketingPanel').hidden,'در نظرسنجی، همراهان و بلیت تنظیمِ فعال‌نما نیستند');
  p.ev("S.guestsOn=true");
  ok(p.ev("buildDraftRow().guestsOn===false&&buildDraftRow().ticketingEnabled===false"),'payload سرور برای مدل غیرثبت‌نام همراهان و بلیت را روشن نمی‌فرستد');
  p.click('#tiles [data-model="registration"]');
  ok(!p.doc.querySelector('#companionBody').hidden&&p.doc.querySelector('#companionModelNote').hidden&&!p.doc.querySelector('#ticketingPanel').hidden,'در ثبت‌نام همان گردش سروری (همراهان، بلیت) در دسترس است');
  ok(p.ev("['questionnaire','survey','exam','contest','attendance','election','datacollect'].every(m=>modelCapability(m).status==='limited')&&modelCapability('order').publishable===false"),'هفت مدل عمومی «محدود» و سفارش غیرقابل‌انتشار از قرارداد سرور خوانده می‌شوند');
  ok(p.errors.length===0,'ماتریس مدل بدون خطای کنسول');
}

/* ── ۶) وضعیت ذخیره: یک مسیر واحد ── */
{
  console.log('\n── وضعیت ذخیره ──');
  const api=makeApi({id:'save-state-1'}), store=makeStore(), p=await load({api,store});
  const state=()=>p.doc.querySelector('#saveState').dataset.state;
  ok(state()==='idle','فرم تازه: «ذخیره‌نشده در سرور»');
  p.input('#fTitle','فرم وضعیت');p.ev("S.fields=[freshField('text','a')];renderCanvas()");
  p.click('#publish');await wait(120);
  ok(state()==='saved'&&p.txt('#saveState').includes('نسخهٔ ۱')&&api.calls.some(c=>c.method==='POST'&&c.path==='/api/forms'),'پس از تأیید سرور، وضعیت «ذخیره شد · نسخهٔ ۱» است');
  p.click('[data-edit="a"]');p.input('#fdTitle','عنوان تازه');p.click('#fdSave');await wait(10);
  ok(state()==='dirty','تغییر عنوان پرسش از داخل ورقه (خارج از main) وضعیت را «تغییرات ذخیره‌نشده» می‌کند');
  p.click('[data-edit="a"]');p.input('#fdTitle','متن کوتاه');p.click('#fdSave');await wait(10);
  ok(state()==='saved','برگرداندن همان مقدار، وضعیت را دوباره «ذخیره شد» می‌کند (مقایسه با نسخهٔ تأییدشده، نه شمارش لمس‌ها)');
  p.ev("addField('nid')");p.click('#fdCancel');await wait(10);
  ok(state()==='dirty','افزودن فیلد وضعیت را تغییر می‌دهد');
  p.click('#publish');await wait(120);
  ok(state()==='saved'&&p.txt('#saveState').includes('نسخهٔ ۲'),'ذخیرهٔ دوباره نسخهٔ ۲ را تأیید می‌کند');
  p.click('[data-edit="a"]');p.click('#fdDelete');await wait(10);
  ok(state()==='dirty'&&p.ev('S.fields.length')===1,'حذف فیلد از ویرایشگر هم ردیابی می‌شود');
  p.click('#tiles [data-model="survey"]');await wait(10);
  ok(state()==='dirty','تغییر مدل ردیابی می‌شود');
  p.click('#tiles [data-model="registration"]');p.ev("S.fields.unshift(freshField('text','a'));S.fields[0].l='متن کوتاه';renderCanvas();commitChange()");await wait(10);
  ok(state()==='saved','بازگشت دقیق به نسخهٔ ذخیره‌شده دوباره «ذخیره شد» می‌شود');
  const failApi=makeApi({id:'save-fail-1',saveStatus:500}), f=await load({api:failApi});
  f.input('#fTitle','فرم خطا');f.ev("S.fields=[freshField('text','a')];renderCanvas()");f.click('#publish');await wait(120);
  ok(f.doc.querySelector('#saveState').dataset.state==='error','شکست ذخیره «ذخیره نشد» می‌ماند، نه «ذخیره شد»');
  f.click('#btnNext');await wait(10);
  ok(f.doc.querySelector('#saveState').dataset.state==='error','کلیک بی‌تغییر بعد از خطا وضعیت خطا را پاک نمی‌کند');
  f.input('#fTitle','فرم خطا ۲');await wait(10);
  ok(f.doc.querySelector('#saveState').dataset.state==='idle','تغییر پس از خطا (فرم هنوز بی‌شناسهٔ سروری) به وضعیت ذخیره‌نشده برمی‌گردد');
  const conflictApi=makeApi({id:'save-conflict-1',saveStatus:409}), c=await load({api:conflictApi});
  c.input('#fTitle','فرم تعارض');c.ev("S.fields=[freshField('text','a')];renderCanvas()");c.click('#publish');await wait(120);
  c.input('#fTitle','فرم تعارض ۲');await wait(10);
  ok(c.doc.querySelector('#saveState').dataset.state==='conflict','تعارض نسخه تا بازخوانی با ویرایش بعدی پنهان نمی‌شود');
  ok(p.errors.length===0&&f.errors.length===0&&c.errors.length===0,'وضعیت ذخیره بدون خطای کنسول');
}

/* ── ۷) بازگشایی فرم سروری: مبنا = نسخهٔ سرور؛ نگاشت خطای آمادگی به پرسش ── */
{
  console.log('\n── فرم سروری و خطای آمادگی ──');
  const record={id:'srv-7',name:'فرم سروری',model:'registration',need:'reg',slug:'',ev:'',status:'draft',version:4,response_count:0,
    fields:[{id:'n1',t:'number',l:'سن',min:'50',max:'10'},{id:'m1',t:'mobile',l:'موبایل',verify:true}],settings:{display:'one',dir:'rtl',after:'edit'}};
  const issues=[{code:'invalid_numeric_range',field_id:'n1',message:'بازهٔ عددی پرسش «سن» معتبر نیست.'},{code:'verification_not_connected',field_id:'m1',message:'تأیید مالکیت وصل نیست.'},{code:'schedule_not_connected',message:'بازهٔ زمانی را پاک کنید.'}];
  const api=makeApi({id:'srv-7',initialRecord:record,readinessIssues:issues});
  const store=makeStore({'nora-forms':JSON.stringify([{...record,...record.settings,serverManaged:true}])});
  const p=await load({api,store,query:'?fid=srv-7',fixtureMode:false});
  ok(p.doc.querySelector('#saveState').dataset.state==='saved'&&p.txt('#saveState').includes('نسخهٔ ۴'),'فرم سروری با مبنای «ذخیره شد · نسخهٔ سرور» باز می‌شود، نه «ذخیره‌نشده»');
  ok(p.doc.querySelector('[data-block="m1"]').textContent.includes('نیاز به اصلاح')&&p.ev("S.fields.length===2"),'فیلد قدیمی با درخواست تأیید حذف نمی‌شود و نشان‌دار می‌ماند');
  p.ev("go('s4')");await wait(150);
  const openButtons=p.all('[data-ready-field]');
  ok(openButtons.length===2&&openButtons[0].dataset.readyField==='n1'&&p.all('[data-ready-go]').length===1,'خطاهای سروریِ پرسش‌دار دکمهٔ «بازکردن پرسش» دارند و خطای تنظیمی به تنظیم خودش می‌رود');
  openButtons[0].dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));await wait(10);
  ok(p.doc.querySelector('#shField').classList.contains('on')&&p.doc.querySelector('#fdTitle').value==='سن'&&p.doc.activeElement===p.doc.querySelector('#fdMin'),'خطای بازهٔ عددی همان پرسش را باز و حداقل را فوکوس می‌کند');
  p.set('#fdMin','۵');p.set('#fdMax','۱۰');p.click('#fdSave');await wait(10);
  ok(p.ev("S.fields[0].min===5&&S.fields[0].max===10")&&p.doc.querySelector('#saveState').dataset.state==='dirty','اصلاح از همان کنترل انجام و به‌عنوان تغییر ذخیره‌نشده ثبت می‌شود');
  ok(p.errors.length===0,'فرم سروری بدون خطای کنسول');
  /* رونوشت محلی کهنه (نسخهٔ ۳) در برابر سرور (نسخهٔ ۴): مبنا سرور است؛ رونوشت تازه می‌شود و صفحه بازخوانی می‌شود */
  const staleStore=makeStore({'nora-forms':JSON.stringify([{...record,...record.settings,version:3,fields:[record.fields[0]],serverManaged:true}])});
  const staleApi=makeApi({id:'srv-7',initialRecord:record});
  const stale=await load({api:staleApi,store:staleStore,query:'?fid=srv-7',fixtureMode:false});await wait(150);
  const mirrored=JSON.parse(staleStore.getItem('nora-forms')||'[]').find(f=>f.id==='srv-7');
  ok(stale.ev("S.fields.length")===1&&mirrored&&Number(mirrored.version)===4&&mirrored.fields.length===2&&staleApi.calls.some(c=>c.method==='GET'&&c.path==='/api/forms/srv-7'),
    'با رونوشت محلی کهنه، نسخهٔ سرور خوانده و جایگزین رونوشت می‌شود (بازخوانی صفحه با hydrated=1)؛ رونوشت محلی بی‌صدا جای سرور را نمی‌گیرد');
  const freshStore=makeStore({'nora-forms':JSON.stringify([{...record,...record.settings,serverManaged:true}])});
  const freshApi=makeApi({id:'srv-7',initialRecord:record});
  await load({api:freshApi,store:freshStore,query:'?fid=srv-7',fixtureMode:false});await wait(150);
  ok(JSON.parse(freshStore.getItem('nora-forms')).find(f=>f.id==='srv-7').version===4&&freshApi.calls.filter(c=>c.method==='GET'&&c.path==='/api/forms/srv-7').length===1,'با رونوشت هم‌نسخه، فقط یک بررسی نسخه انجام می‌شود و بازخوانی رخ نمی‌دهد');
}

/* ── ۸) تنظیمات نوع‌محور: الگو ≠ نوع در تغییر نوع، کنترل‌های بی‌اثر، ثبت کنترل‌ها، خلاصهٔ بوم، انتخاب‌گر ── */
{
  console.log('\n── تنظیمات نوع‌محور و الگوهای هم‌نوع ──');
  const p=await load({api:makeApi()});
  p.ev("S.fields=[];applyPack('empty','replace')");
  p.ev("addField('time');editField(S.fields[0].id)");
  const choices=p.all('#fdTypeChange option').map(o=>o.value);
  ok(choices.includes('birth-date')&&choices.includes('jalali-date')&&!choices.includes('date')&&choices.includes('datetime'),'تغییر نوع، برای نوعی که چند الگو دارد هر دو الگو (تاریخ تولد / تاریخ شمسی) را صریح فهرست می‌کند، نه یک «date» مبهم');
  p.set('#fdTypeChange','birth-date');p.click('#fdTypeApply');
  ok(p.txt('#fdTypeConsequences').includes('عنوان پیش‌فرض به «تاریخ تولد» تغییر می‌کند')&&p.txt('#fdTypeConsequences').includes('الگوی «تاریخ تولد»'),'پیامدها اعلام می‌کنند عنوان پیش‌فرض عوض می‌شود و کدام الگو ثبت می‌شود');
  p.click('#fdTypeConfirmGo');p.click('#fdSave');
  ok(p.ev("S.fields[0].t==='date'&&S.fields[0].preset==='birth-date'&&S.fields[0].l==='تاریخ تولد'"),'اعمال: نوع date، الگوی birth-date و عنوان پیش‌فرض الگو');
  p.ev("addField('time');editField(S.fields[1].id)");p.input('#fdTitle','زمان جلسهٔ معارفه');p.click('#fdSave');
  p.ev("editField(S.fields[1].id)");p.set('#fdTypeChange','jalali-date');p.click('#fdTypeApply');
  ok(p.txt('#fdTypeConsequences').includes('عنوان «زمان جلسهٔ معارفه» حفظ می‌شود'),'با عنوان سفارشی، پیامد «حفظ عنوان» اعلام می‌شود');
  p.click('#fdTypeConfirmGo');p.click('#fdSave');
  ok(p.ev("S.fields[1].t==='date'&&S.fields[1].preset==='jalali-date'&&S.fields[1].l==='زمان جلسهٔ معارفه'"),'عنوان سفارشی کاربر در تغییر نوع حفظ و الگوی انتخابی (تاریخ شمسی) ثبت می‌شود، نه تاریخ تولد');
  p.ev("editField(S.fields[1].id)");
  ok(!p.all('#fdTypeChange option').map(o=>o.value).includes('jalali-date')&&p.all('#fdTypeChange option').map(o=>o.value).includes('birth-date'),'الگوی فعلی از فهرست مقصد حذف می‌شود ولی الگوی هم‌نوع دیگر قابل انتخاب می‌ماند');
  p.click('#fdCancel');
  /* کپی پرسش شناسهٔ الگو را نگه می‌دارد */
  p.click('[data-copy="'+p.ev('S.fields[1].id')+'"]');
  ok(p.ev("S.fields.length===3&&S.fields[2].preset==='jalali-date'&&S.fields[2].l==='زمان جلسهٔ معارفه'&&S.fields[0].preset==='birth-date'"),'کپی پرسش، الگوی تاریخ شمسی را به تاریخ تولد تبدیل نمی‌کند');
  /* پیشنهاد از پروفایل: فقط نوع‌های دارای مسیر؛ در پیش‌نمایش محلی فعال */
  p.ev("addField('choice');editField(S.fields[3].id)");
  ok(p.doc.querySelector('#fdProfBox').style.display==='none','برای تک‌انتخاب، سوییچ «پیشنهاد از پروفایل» اصلاً نمایش داده نمی‌شود (فرم عمومی مقداری برایش ندارد)');
  p.click('#fdCancel');p.ev("addField('fullname');editField(S.fields[4].id)");
  ok(p.doc.querySelector('#fdProfBox').style.display!=='none'&&p.doc.querySelector('#fdProf').getAttribute('aria-disabled')==='false','برای نام، در پیش‌نمایش محلی سوییچ فعال است');
  p.click('#fdCancel');
  /* ثبت واحد کنترل‌ها: هر جعبهٔ کنترل دقیقاً وقتی دیده می‌شود که تعریف می‌گوید */
  const typesToCheck=p.ev("Object.keys(FIELD_TYPES).filter(t=>!FIELD_TYPES[t].hidden&&fieldSupport(t).addable)");
  let mismatch=[];
  for(const t of typesToCheck){
    p.ev("S.fields=[];addField('"+t+"');editField(S.fields[0].id)");
    const bad=p.ev("FIELD_SETTINGS.filter(def=>def.box).filter(def=>{const el=document.querySelector(def.box);if(!el)return true;const shown=el.style.display!=='none';return shown!==settingVisible(def,'"+t+"',FIELD_DRAFT)}).map(def=>def.id)");
    if(bad.length)mismatch.push(t+':'+bad.join('/'));
    p.click('#fdCancel');
  }
  ok(mismatch.length===0,'برای همهٔ نوع‌های قابل‌افزودن، نمایش هر جعبهٔ تنظیم با ثبت FIELD_SETTINGS یکی است'+(mismatch.length?' — ناهم‌خوان: '+mismatch.join(' ، '):''));
  ok(p.ev("visibleSettings('text',null).includes('placeholder')&&!visibleSettings('choice',null).includes('placeholder')&&visibleSettings('multi',null).includes('multiLimits')&&!visibleSettings('choice',null).includes('multiLimits')&&visibleSettings('rating',null).includes('bounds')&&!visibleSettings('date',null).includes('bounds')"),
    'متن داخل کادر فقط برای ورودی متنی، حداقل/حداکثر انتخاب فقط برای چندانتخاب، بازه برای ستاره/عدد و نه تاریخ');
  /* ستاره: بازهٔ واقعی ۱ تا ۵ با اعتبارسنجی */
  p.ev("S.fields=[];addField('rating');editField(S.fields[0].id)");
  ok(p.doc.querySelector('#fdBoundsBox').style.display!=='none'&&p.txt('#fdBoundsLabel').includes('ستاره'),'ستاره جعبهٔ بازه (۱ تا ۵) دارد');
  p.set('#fdMin','۰');p.set('#fdMax','۵');
  ok(p.ev('saveField()')===false&&p.doc.querySelector('#shField').classList.contains('on')&&p.txt('#fdIssues').includes('۱ تا ۵'),'بازهٔ خارج از ۱ تا ۵ برای ستاره رد می‌شود و پنجره باز می‌ماند');
  p.set('#fdMin','۲');p.set('#fdMax','۴');
  ok(p.ev('saveField()')===true&&p.ev("S.fields[0].min===2&&S.fields[0].max===4"),'بازهٔ معتبر ستاره ذخیره می‌شود');
  ok(p.doc.querySelector('[data-block="'+p.ev('S.fields[0].id')+'"]').textContent.includes('بازه از ۲ تا ۴'),'بوم خلاصهٔ بازهٔ ذخیره‌شده را نشان می‌دهد');
  p.ev("addField('choice')");p.click('#fdSave');
  ok(p.doc.querySelector('[data-block="'+p.ev('S.fields[1].id')+'"]').textContent.includes('۲ گزینه'),'بوم شمار گزینه‌های پرسش انتخابی را نشان می‌دهد');
  /* ستون CSV: توضیح مطابق رفتار واقعی سرور */
  p.ev("editField(S.fields[1].id)");
  ok(p.txt('#fdColNote').includes('CSV')&&!p.txt('#fdColNote').includes('فقط روی خروجی محلی'),'توضیح «ستون در خروجی CSV سرور» با رفتار واقعی endpoint خروجی هم‌خوان است');
  p.click('#fdCancel');
  /* انتخاب‌گر: شمار هر دسته، پاک‌کردن جست‌وجو */
  p.ev("openSheet('shAdd');renderCatalog()");
  const allCount=Number(p.ev("digits=s=>String(s).replace(/[۰-۹]/g,d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d));Number(digits(document.querySelector('[data-cat-count=\"all\"]').textContent))"));
  ok(allCount===p.ev("CATALOG.filter(c=>!c.hidden).length")&&p.all('[data-cat-count]').length===p.all('#catChips [data-cat]').length,'هر دستهٔ انتخاب‌گر شمار نوع‌هایش را نشان می‌دهد');
  ok(p.doc.querySelector('#catClear').hidden===true,'بدون جست‌وجو دکمهٔ پاک‌کردن پنهان است');
  p.input('#catSearch','شماره همراه');await wait(20);
  ok(p.doc.querySelector('#catClear').hidden===false&&p.all('#catList [data-add]').length>=1&&p.all('#catList [data-add]')[0].dataset.add==='mobile','با جست‌وجو دکمهٔ پاک‌کردن ظاهر می‌شود و «شماره همراه» موبایل را اول می‌آورد');
  p.click('#catClear');await wait(20);
  ok(p.doc.querySelector('#catSearch').value===''&&p.doc.querySelector('#catClear').hidden===true&&p.doc.activeElement===p.doc.querySelector('#catSearch'),'پاک‌کردن، فهرست کامل را برمی‌گرداند و تمرکز روی کادر جست‌وجو می‌ماند');
  ok(p.errors.length===0,'بدون خطای کنسول');
}

/* ── ۹) فرم سروری: پیشنهاد از پروفایل غیرفعال با دلیل سرور و حفظ مقدار ذخیره‌شده ── */
{
  console.log('\n── پیشنهاد از پروفایل در فرم سروری ──');
  const record={id:'srv-9',name:'فرم سروری',model:'registration',need:'reg',slug:'',ev:'',status:'draft',version:1,response_count:0,
    fields:[{id:'f1',t:'fullname',l:'نام',prof:true},{id:'f2',t:'choice',l:'انتخاب',prof:true,opts:[{l:'الف'},{l:'ب'}]}],settings:{display:'one',dir:'rtl',after:'edit'}};
  const api=makeApi({id:'srv-9',initialRecord:record});
  const store=makeStore({'nora-forms':JSON.stringify([{...record,...record.settings,serverManaged:true}])});
  const p=await load({api,store,query:'?fid=srv-9',fixtureMode:false});
  p.ev("go('s2');editField('f1')");
  ok(p.doc.querySelector('#fdProfBox').style.display!=='none'&&p.doc.querySelector('#fdProf').getAttribute('aria-disabled')==='true'&&p.doc.querySelector('#fdProf').classList.contains('on'),'در فرم سروری سوییچ پروفایل غیرفعال است ولی مقدار ذخیره‌شده (روشن) نشان داده می‌شود');
  ok(p.txt('#fdProfNote').includes('ناشناس')||p.txt('#fdProfNote').includes('پشتیبانی نمی‌کند'),'دلیل غیرفعال‌بودن از قرارداد سرور (profile_prefill) می‌آید');
  p.click('#fdProf');
  ok(p.doc.querySelector('#fdProf').classList.contains('on')&&p.doc.querySelector('#saveState').dataset.state==='saved','کلیک روی سوییچ غیرفعال چیزی را تغییر نمی‌دهد و فرم ذخیره‌نشده نمی‌شود');
  p.click('#fdSave');
  ok(p.ev("S.fields[0].prof===true")&&p.doc.querySelector('#saveState').dataset.state==='saved','ذخیرهٔ فیلد، تنظیم قدیمی prof را حذف نمی‌کند و تغییری ثبت نمی‌شود');
  p.ev("editField('f2')");
  ok(p.doc.querySelector('#fdProfBox').style.display!=='none'&&p.txt('#fdProfNote').includes('اثری ندارد'),'برای نوع بدون مسیر پروفایل که مقدار قدیمی دارد، وضعیت «ذخیره‌شده ولی بی‌اثر» نشان داده می‌شود');
  p.click('#fdCancel');
  ok(p.errors.length===0,'بدون خطای کنسول');
}

/* ── ۱۰) ویرایشگر: گزینهٔ تکراری/خالی و حداقل>حداکثر انتخاب همان‌جا رد می‌شوند (نه فقط هنگام ذخیرهٔ کل فرم) ── */
{
  console.log('\n── اعتبارسنجی گزینه‌ها در خود ویرایشگر ──');
  const p=await load();
  p.ev("go('s2');S.fields=[];addField('choice');editField(S.fields[0].id)");
  const n=p.all('#fdOptions [data-optl]').length;
  p.input('[data-optl="1"]',p.doc.querySelector('[data-optl="0"]').value);
  ok(p.ev('saveField()')===false&&p.doc.querySelector('#shField').classList.contains('on')&&p.txt('#fdIssues').includes('یکتا')&&p.doc.activeElement===p.doc.querySelector('[data-optl="1"]'),'گزینهٔ تکراری: ذخیره رد می‌شود، پیام کنار کنترل و فوکوس روی همان گزینه');
  p.input('[data-optl="1"]','');
  ok(p.ev('saveField()')===false&&p.txt('#fdIssues').includes('نویسه'),'گزینهٔ خالی رد می‌شود');
  p.input('[data-optl="1"]','گزینهٔ دوم');
  ok(p.ev('saveField()')===true&&p.ev("S.fields[0].opts.length")===n,'گزینه‌های معتبر ذخیره می‌شوند');
  p.ev("S.fields=[];addField('multi');editField(S.fields[0].id)");
  p.set('#fdMinSelect','۳');p.set('#fdMaxSelect','۲');
  ok(p.ev('saveField()')===false&&p.txt('#fdIssues').includes('حداقل انتخاب')&&p.doc.activeElement===p.doc.querySelector('#fdMinSelect'),'حداقل انتخاب بزرگ‌تر از حداکثر در ویرایشگر رد می‌شود و فوکوس روی حداقل است');
  p.set('#fdMinSelect','۱');p.set('#fdMaxSelect','۲');
  ok(p.ev('saveField()')===true&&p.ev("S.fields[0].minSelect===1&&S.fields[0].maxSelect===2"),'محدودیت معتبر ذخیره می‌شود');
  ok(p.errors.length===0,'بدون خطای کنسول');
}

/* ── ۱۱) جست‌وجوی انتخاب‌گر: عبارت‌های نیازمحور، نام بر توضیح مقدم، بدون تطبیق زیررشته‌ای تصادفی؛ چیدمان دسکتاپ/موبایل ── */
{
  console.log('\n── عبارت‌های جست‌وجوی انتخاب‌گر ──');
  const p=await load();
  const first=q=>p.ev("catalogSearch("+JSON.stringify(q)+",'all').map(c=>c.k)");
  const cases=[['شماره همراه','mobile'],['کد ملی','nid'],['توضیح طولانی','area'],['تاریخ تولد','birth-date'],['زمان جلسه','time'],['انتخاب چند مورد','multi'],['پذیرش قوانین','terms'],['ايميل','email'],['كد ملي','nid']];
  const bad=cases.filter(([q,k])=>first(q)[0]!==k).map(([q,k])=>q+'→'+(first(q)[0]||'∅')+'≠'+k);
  ok(bad.length===0,'هر عبارت نیازمحور، الگوی درست را اول می‌آورد (ی/ي و ک/ك هم)'+(bad.length?' — '+bad.join(' ، '):''));
  ok(!first('تاریخ تولد').includes('yesno')&&first('تاریخ تولد').length===1,'مترادفِ کوتاه («آری») دیگر به‌صورت زیررشته در «تاریخ» تطبیق نمی‌خورد؛ نتیجهٔ «تاریخ تولد» فقط الگوی تاریخ تولد است');
  ok(p.doc.querySelector('#shAdd').classList.contains('picker')&&p.doc.querySelector('#shAdd .picker-body #catChips')&&p.doc.querySelector('#shAdd .picker-body #catList'),'انتخاب‌گر ساختار دوبخشی (دسته‌ها + فهرست) دارد که روی دسکتاپ نوار کناری می‌شود');
  const css=readFileSync(new URL('./glass.css',import.meta.url),'utf8');
  ok(/@media \(min-width:900px\)[\s\S]*\.sheet\.picker\{width:min\(760px,64vw\)\}[\s\S]*\.sheet\.picker \.picker-body\{display:grid/.test(css)&&!/\.sheet\.picker\{[^}]*\}[\s\S]*?@media \(min-width:900px\)/.test(css.split('.sheet.picker')[0]),'پهنای بیشتر و چیدمان شبکه‌ای فقط در رسانهٔ دسکتاپ تعریف شده و فهرست موبایل تک‌ستونه می‌ماند');
  ok(p.errors.length===0,'بدون خطای کنسول');
}

/* ── ۱۲) ستاره: راهنمای پیش‌فرض از بازهٔ واقعی ساخته می‌شود؛ راهنمای سفارشی دست نمی‌خورد؛ متن‌های نوع «فقط محلی» نمی‌گویند ── */
{
  console.log('\n── ستاره و پذیرش قوانین: متن‌های راست‌گو ──');
  const p=await load();
  p.ev("go('s2');S.fields=[];addField('rating');editField(S.fields[0].id)");
  ok(p.doc.querySelector('#fdHelp').value==='۱ کم، ۵ زیاد.','راهنمای پیش‌فرض ستاره برای بازهٔ ۱ تا ۵');
  p.set('#fdMin','۲');p.set('#fdMax','۴');
  ok(p.ev('saveField()')===true&&p.ev('S.fields[0].help')==='۲ کم، ۴ زیاد.','با بازهٔ ۲ تا ۴ راهنمای پیش‌فرض هم ۲ تا ۴ می‌شود (نه «۱ کم، ۵ زیاد»)');
  p.ev("editField(S.fields[0].id)");p.set('#fdMin','۳');p.set('#fdMax','۳');
  ok(p.ev('saveField()')===true&&p.ev('S.fields[0].help')==='یک ستاره؛ زدن آن یعنی انتخاب.','بازهٔ تک‌مقداری راهنمای خودش را دارد');
  p.ev("editField(S.fields[0].id)");p.set('#fdHelp','چقدر راضی بودی؟');p.set('#fdMin','');p.set('#fdMax','');
  ok(p.ev('saveField()')===true&&p.ev('S.fields[0].help')==='چقدر راضی بودی؟','راهنمای سفارشی مالک با تغییر بازه بازنویسی نمی‌شود');
  ok(!/فقط محلی/.test(p.ev("STRUCT.terms+' '+HELP.terms+' '+STRUCT.rating"))&&/در سرور ذخیره/.test(p.ev('STRUCT.terms'))&&/امضا/.test(p.ev('STRUCT.terms')),'متن نوع پذیرش قوانین و ستاره رفتار واقعی سرور را می‌گوید');
  ok(p.errors.length===0,'بدون خطای کنسول');
}
/* ── ۱۳) منبع واحد تنظیمات: هر ظرف DOM ویرایشگر به یک تنظیم ثبت‌شده تعلق دارد؛ نمایش ظرف‌ها فقط از ثبت می‌آید؛
       کلیدهای ذخیره‌شده ⊆ کلیدهای ثبت ∪ پایه؛ شناسهٔ قرارداد هر تنظیم در form_capabilities.py وجود دارد ── */
{
  console.log('\n── منبع واحد تنظیمات فیلد ──');
  const p=await load();
  const registry=p.ev("FIELD_SETTINGS.map(d=>({id:d.id,keys:d.keys,box:d.box||null,cap:d.cap||null,hasRender:!!d.render,hasApply:!!d.apply,hasValidate:!!d.validate,hasDirty:!!d.dirty}))");
  const ids=registry.map(d=>d.id), keys=registry.flatMap(d=>d.keys);
  ok(new Set(ids).size===ids.length&&new Set(keys).size===keys.length,'شناسه‌ها و کلیدهای داده در ثبت یکتا هستند');
  const domBoxes=[...p.doc.querySelectorAll('#shField [id$="Box"]')].map(el=>'#'+el.id).filter(id=>!['#fdValidationBox','#fdMediaNoteBox','#fdCondLogicBox'].includes(id));
  const registryBoxes=registry.map(d=>d.box).filter(Boolean);
  const orphan=domBoxes.filter(id=>!registryBoxes.includes(id)), missing=registryBoxes.filter(id=>!p.doc.querySelector(id));
  ok(orphan.length===0&&missing.length===0,'هر ظرف تنظیم در DOM ↔ یک تنظیم ثبت‌شده'+(orphan.length?' — بی‌صاحب: '+orphan.join(','):'')+(missing.length?' — گم‌شده: '+missing.join(','):''));
  const pySource=readFileSync(new URL('./backend/form_capabilities.py',import.meta.url),'utf8');
  const capMissing=registry.filter(d=>d.cap&&!pySource.includes('"'+d.cap+'": {')).map(d=>d.cap);
  ok(capMissing.length===0,'شناسهٔ قرارداد هر تنظیم (cap) در field_settings سرور تعریف شده'+(capMissing.length?' — '+capMissing.join(','):''));
  const mismatches=[];
  for(const t of p.ev("Object.keys(FIELD_TYPES).filter(t=>fieldSupport(t).addable)")){
    p.ev("S.fields=[];addField("+JSON.stringify(t)+");editField(S.fields[0].id)");
    const expected=p.ev("FIELD_SETTINGS.filter(d=>d.box&&settingVisible(d,FIELD_DRAFT.t,FIELD_DRAFT)).map(d=>d.box)");
    const shown=registryBoxes.filter(id=>{const el=p.doc.querySelector(id);return el&&el.style.display!=='none'});
    if(JSON.stringify([...expected].sort())!==JSON.stringify([...shown].sort()))mismatches.push(t);
    const base=new Set(['id','k','t','l','preset','opts','options','help','req','col','media','mediaNote','verify','count','accept','maxSize','min','max','weight','scoreOn','prof','placeholder']);
    const saved=p.ev("(saveField(),Object.keys(S.fields[0]))").filter(key=>!base.has(key)&&!keys.includes(key));
    if(saved.length)mismatches.push(t+':'+saved.join('/'));
  }
  ok(mismatches.length===0,'برای همهٔ نوع‌های قابل‌افزودن، ظرف‌های نمایان = ثبت، و کلیدهای ذخیره‌شده ⊆ ثبت'+(mismatches.length?' — '+mismatches.join(' ، '):''));
  ok(registry.filter(d=>d.hasApply||d.hasRender).length===registry.length,'هر تنظیم دست‌کم render یا apply دارد (هیچ ثبتِ صرفاً تزئینی)');
  ok(p.errors.length===0,'بدون خطای کنسول');
}

/* ── ۱۴) طول متن و فقط‌صحیح: کنترل واقعی → ذخیره → بازگشایی → تغییر نوع → خطا کنار کنترل ── */
{
  console.log('\n── طول پاسخ و فقط عدد صحیح ──');
  const p=await load();
  p.ev("go('s2');S.fields=[];addField('text');editField(S.fields[0].id)");
  ok(p.doc.querySelector('#fdLengthBox').style.display==='block'&&p.doc.querySelector('#fdIntegerBox').style.display==='none','متن: جعبهٔ طول دیده می‌شود و «فقط عدد صحیح» نه');
  ok(/۱٬?۰۰۰/.test(p.txt('#fdLengthNote').replace(/\u066c/g,'٬'))||p.txt('#fdLengthNote').includes('۱۰۰۰'),'یادداشت طول سقف نوع (۱۰۰۰) را می‌گوید');
  p.set('#fdMinLen','۱۰');p.set('#fdMaxLen','۵');
  ok(p.ev('saveField()')===false&&p.txt('#fdIssues').includes('حداقل نویسه')&&p.doc.activeElement===p.doc.querySelector('#fdMinLen'),'حداقل > حداکثر رد می‌شود و تمرکز روی کنترل');
  p.set('#fdMinLen','');p.set('#fdMaxLen','۲۰۰۰');
  ok(p.ev('saveField()')===false&&p.txt('#fdIssues').includes('۱۰۰۰')&&p.doc.activeElement===p.doc.querySelector('#fdMaxLen'),'حداکثر بیش از سقف نوع رد می‌شود');
  p.set('#fdMinLen','۳');p.set('#fdMaxLen','۸');
  ok(p.ev('saveField()')===true&&p.ev('S.fields[0].minLen===3&&S.fields[0].maxLen===8'),'طول معتبر با رقم فارسی به عدد ذخیره می‌شود');
  ok(p.ev('editorControlsChanged()')===false,'پس از ذخیره، کنترل‌ها «تغییر ذخیره‌نشده» ندارند');
  p.ev("closeSheets();editField(S.fields[0].id)");
  ok(p.doc.querySelector('#fdMinLen').value==='3'&&p.doc.querySelector('#fdMaxLen').value==='8','بازگشایی: مقدارها برمی‌گردند');
  p.set('#fdMaxLen','9');ok(p.ev('editorControlsChanged()')===true,'تغییر حداکثر نویسه «تغییر ذخیره‌نشده» است');
  ok(p.txt('#fieldList').includes('طول دست‌کم ۳ حداکثر ۸ نویسه'),'خلاصهٔ فیلد روی بوم طول را نشان می‌دهد');
  ok(p.ev("typeChangeConsequences(FIELD_DRAFT,'fullname').join(' ')").includes('محدودیت طول')===false&&p.ev("typeChangeConsequences(FIELD_DRAFT,'email').join(' ')").includes('محدودیت طول پاسخ برداشته'),'پیامد تغییر نوع: به ایمیل → محدودیت طول برداشته می‌شود؛ به نام → می‌ماند');
  p.ev("applyTypeChange('email');saveField()");
  ok(p.ev("!('minLen' in S.fields[0])&&!('maxLen' in S.fields[0])&&S.fields[0].t==='email'"),'پس از تغییر به ایمیل کلیدهای طول پاک می‌شوند');
  p.ev("S.fields=[];addField('number');editField(S.fields[0].id)");
  ok(p.doc.querySelector('#fdIntegerBox').style.display!=='none'&&p.doc.querySelector('#fdLengthBox').style.display==='none','عدد: «فقط عدد صحیح» دیده می‌شود و جعبهٔ طول نه');
  ok(p.doc.querySelector('#fdInteger').getAttribute('aria-checked')==='false'&&p.ev("saveField();S.fields[0].integer")===undefined,'پیش‌فرض خاموش و کلید ذخیره نمی‌شود');
  p.ev("editField(S.fields[0].id)");p.click('#fdInteger');
  ok(p.ev('editorControlsChanged()')===true&&p.ev('saveField()')===true&&p.ev('S.fields[0].integer===true'),'روشن‌کردن → ذخیره → integer:true');
  ok(p.ev('S.fields[0].help')===p.ev('HELP_NUMBER_INTEGER')&&!/ممیز و/.test(p.ev('S.fields[0].help')),'راهنمای پیش‌فرض عدد با فقط‌صحیح دیگر «ممیز پذیرفته می‌شود» نمی‌گوید');
  p.ev("closeSheets();editField(S.fields[0].id)");
  ok(p.doc.querySelector('#fdInteger').getAttribute('aria-checked')==='true'&&p.txt('#fieldList').includes('فقط عدد صحیح'),'بازگشایی: سوییچ روشن و خلاصه روی بوم');
  ok(p.ev("typeChangeConsequences(FIELD_DRAFT,'amount').join(' ')").includes('فقط عدد صحیح')===false,'عدد → مبلغ: «فقط عدد صحیح» حفظ می‌شود');
  p.ev("applyTypeChange('amount');saveField()");ok(p.ev('S.fields[0].integer===true&&S.fields[0].t==="amount"'),'پس از تغییر به مبلغ، تنظیم می‌ماند');
  const html=readFileSync(new URL('./create.html',import.meta.url),'utf8');
  ok(html.includes("invalid_length_range:'#fdMinLen'")&&p.doc.querySelector('#fdMinLen'),'خطای انتشار invalid_length_range به کنترل حداقل نویسه می‌رسد');
  ok(p.errors.length===0,'بدون خطای کنسول');
}
/* ── ۱۵) ماتریس مدل × تنظیم: همراهان/بلیت/پرداخت فقط ثبت‌نام؛ امتیاز فقط نظرسنجی؛ سفارش قابل انتشار نیست؛
       تغییر مدل دادهٔ معتبر قبلی را بی‌صدا دور نمی‌ریزد (در حالت می‌ماند و فقط از payload مدل نامربوط حذف می‌شود) ── */
{
  console.log('\n── ماتریس مدل × تنظیم ──');
  const p=await load({api:makeApi()});await new Promise(r=>setTimeout(r,50));p.ev('renderTiles()');
  const MODEL_IDS=['registration','questionnaire','survey','contest','exam','attendance','datacollect','order','election'];
  ok(p.ev('MODELS.map(m=>m.k).join()')===MODEL_IDS.join(),'۹ مدل در فرم‌ساز همان ۹ مدل سرور');
  p.ev("go('s1');S.guestsOn=true;S.model='registration';S.need='reg';renderTiles();syncTicketingUI()");
  const rows=[];
  for(const m of MODEL_IDS){
    if(m==='order'){ok(p.doc.querySelector('[data-model="order"]').disabled===true,'سفارش: کاشی غیرفعال (قرارداد سرور: قابل انتشار نیست)');continue}
    p.click('[data-model="'+m+'"]');
    const companions=!p.doc.querySelector('#companionBody').hidden, ticketing=!p.doc.querySelector('#ticketingPanel').hidden;
    p.ev("go('s2');S.fields=[];addField('choice');editField(S.fields[0].id)");
    const score=p.doc.querySelector('#fdScoreBox').style.display==='block';
    p.ev("closeSheets();go('s1')");
    const payload=p.ev("JSON.stringify(buildDraftRow())"), row=JSON.parse(payload);
    rows.push({m,companions,ticketing,score,guests:row.guestsOn,scoring:row.scoring&&row.scoring.enabled,need:row.need});
  }
  const reg=rows.find(r=>r.m==='registration'), others=rows.filter(r=>r.m!=='registration');
  ok(reg.companions&&reg.ticketing&&!reg.score&&reg.guests===true&&reg.scoring===false&&reg.need==='reg','ثبت‌نام: همراهان و بلیت فعال، امتیاز نه، guestsOn در payload');
  ok(others.every(r=>!r.companions&&!r.ticketing&&r.guests===false),'بقیهٔ مدل‌ها: همراهان/بلیت پنهان و guestsOn در payload false (سرور همین را می‌خواهد)');
  ok(rows.filter(r=>r.score).map(r=>r.m).join()==='survey'&&rows.filter(r=>r.scoring).map(r=>r.m).join()==='survey','جعبهٔ امتیاز و scoring.enabled فقط برای نظرسنجی (فقط پیش‌نمایش محلی)');
  ok(rows.find(r=>r.m==='exam').scoring===false&&rows.find(r=>r.m==='contest').scoring===false,'آزمون و مسابقه نمره‌دهی ندارند (پیاده‌سازی‌نشده، نه تقلبی)');
  p.click('[data-model="registration"]');
  ok(p.ev('S.guestsOn===true')&&p.ev('buildDraftRow().guestsOn===true'),'بازگشت به ثبت‌نام: تنظیم همراهان بی‌صدا دور ریخته نشده بود');
  const descs=p.ev("MODELS.map(m=>m.k+':'+m.d).join('\\n')");
  ok(/exam:.*نمره‌دهی خودکار هنوز ساخته نشده/.test(descs)&&/attendance:.*حضور واقعی را تأیید نمی‌کند/.test(descs)&&/election:.*تضمین نمی‌شود/.test(descs)&&/contest:.*رتبه‌بندی و قرعه‌کشی هنوز ساخته نشده/.test(descs),'توضیح کاشی مدل‌ها قابلیت‌های ثابت‌نشده را صادقانه می‌گوید');
  ok(p.errors.length===0,'بدون خطای کنسول');
}
/* ── ۱۶) جایگاه افزودن: «+» بالا = ابتدا، «+» پایین = انتها، منوی پرسش = پس از همان پرسش؛ شرط‌های وابسته سالم می‌مانند ── */
{
  console.log('\n── جایگاه افزودن پرسش ──');
  const p=await load();
  p.ev("go('s2');S.fields=[freshField('text',1),freshField('choice',2),freshField('text',3)];S.fields[2].conditions=[{field:'2',op:'eq',value:'گزینهٔ یک'}];normalizeFieldConditions();renderCanvas()");
  const ids=()=>p.ev('S.fields.map(f=>String(f.id)).join()');
  p.click('#addTop');
  ok(p.doc.querySelector('#shAdd').classList.contains('on')&&!p.doc.querySelector('#catPositionNote').hidden&&p.txt('#catPositionNote').includes('ابتدای فهرست'),'«+» بالا: انتخاب‌گر با یادداشت «ابتدای فهرست» باز می‌شود');
  p.click('#catList [data-add="nid"]');
  ok(p.ev("S.fields[0].t==='nid'")&&ids().endsWith('1,2,3')&&p.doc.querySelector('#shField').classList.contains('on'),'پرسش تازه در ابتدا قرار گرفت و ویرایشگرش باز شد');
  ok(p.txt('#fieldReorderStatus').includes('جایگاه ۱ از ۴'),'وضعیت زنده جایگاه را اعلام می‌کند');
  ok(p.ev("conditionRulesForField(S.fields[3]).length===1&&String(conditionRulesForField(S.fields[3])[0].field)==='2'"),'شرط وابستهٔ پرسش سوم به پرسش دوم دست‌نخورده ماند');
  p.ev('closeSheets()');p.click('[data-add-after="1"]');
  ok(p.doc.querySelector('#shAdd').classList.contains('on')&&p.txt('#catPositionNote').includes('پس از پرسش ۲'),'منوی پرسش: «افزودن پرسش پس از این» با جایگاه درست');
  p.click('#catList [data-add="email"]');
  ok(p.ev("S.fields[2].t==='email'")&&p.ev("S.fields.length===5"),'پرسش تازه دقیقاً پس از آن پرسش نشست');
  p.ev('closeSheets()');p.click('#addBottom');
  ok(p.doc.querySelector('#catPositionNote').hidden,'«+» پایین: بدون یادداشت جایگاه (انتها)');
  p.click('#catList [data-add="area"]');
  ok(p.ev("S.fields[S.fields.length-1].t==='area'"),'پرسش تازه در انتها');
  p.ev('closeSheets()');p.click('#addTop');p.ev('closeSheets()');
  ok(p.ev("addField('text');S.fields[S.fields.length-1].t==='text'"),'بستن انتخاب‌گر بدون افزودن، جایگاه را برای افزودن بعدی نگه نمی‌دارد');
  ok(p.errors.length===0,'بدون خطای کنسول');
}
/* ── ۱۷) ارتقای UX ۱۴۰۵/۰۸/۰۵: کارت کاتالوگ آرام‌تر، راهنمای «تنظیم ≠ نوع» در جست‌وجو، اثر مدل، رسانهٔ بی‌کنترل، خطای کنار کنترل ── */
{
  console.log('\n── ارتقای UX انتخاب‌گر و ویرایشگر ──');
  const p=await load({api:makeApi()}); await new Promise(r=>setTimeout(r,60)); p.ev('renderTiles()');
  /* اثر مدل: پیش از ساخت فرم، فعال/غیرفعال هر مدل دیده می‌شود و با انتخاب مدل عوض می‌شود */
  ok(!p.doc.querySelector('#modelEffects').hidden&&p.txt('#modelEffects').includes('با انتخاب «ثبت‌نام»')&&p.txt('#modelEffects').includes('همراهان'),'جعبهٔ اثر مدل برای ثبت‌نام: همراهان/بلیت/پرداخت فعال');
  p.click('[data-model="survey"]');
  ok(p.txt('#modelEffects').includes('با انتخاب «نظرسنجی»')&&p.txt('#modelEffects').includes('فقط در پیش‌نمایش محلی')&&p.doc.querySelectorAll('#modelEffects li.off').length>=2,'نظرسنجی: امتیاز فقط محلی و نبود همراهان/بلیت، پیش از انتخاب روشن است');
  ok(p.ev("Object.keys(MODEL_EFFECTS).sort().join()===MODELS.map(m=>m.k).sort().join()"),'هر مدل یک رکورد اثر دارد (بدون مدل بی‌توضیح)');
  ok(p.txt('#modelEffects').includes('فیلدهای قابل‌افزودن در همهٔ مدل‌ها یکسان'),'یکسان‌بودن فیلدها بین مدل‌ها صریح گفته می‌شود');
  p.click('[data-model="registration"]');
  /* کاتالوگ: برچسب وضعیت فقط برای غیر «پشتیبانی سروری»؛ راهنما و نوع پاسخ در دو خط جدا؛ دلیل محدودیت کنار همان کارت */
  p.ev("go('s2');openSheet('shAdd');renderCatalog()");
  ok(!p.doc.querySelector('#catList [data-add="text"] .cap-tag')&&p.doc.querySelector('#catList [data-add="mobile"] .cap-tag.limited'),'برچسب وضعیت فقط روی نوع‌های محدود/غیرفعال است (کارت سروری بی‌برچسب)');
  ok(p.doc.querySelector('#catList [data-add="birth-date"] .hint').textContent.includes('تاریخ تولد را به شمسی')&&p.doc.querySelector('#catList [data-add="birth-date"] .hint.meta').textContent.includes('پاسخ: تاریخ شمسی'),'کارت الگو: راهنمای خودِ الگو، سپس نوع پاسخ و مثال');
  ok(p.doc.querySelector('#catList [data-add="image"].is-blocked .hint.warn').textContent.includes('وصل نیست'),'دلیل غیرفعال‌بودن انسانی و کنار همان کارت است');
  ok(p.all('#catList .cat-group').length>=8&&p.all('#catList .cat-list-grid').length===p.all('#catList .cat-group').length,'هر دسته عنوان و فهرست خودش را دارد');
  /* جست‌وجوی «تنظیم» به‌جای نوع: راهنما + نوع‌های میزبان */
  p.input('#catSearch','عدد صحیح');
  ok(p.doc.querySelector('#catSettingHint')&&p.txt('#catSettingHint').includes('یک تنظیم است، نه نوع فیلد')&&p.all('#catList [data-add]').map(b=>b.dataset.add).includes('number'),'«عدد صحیح»: راهنمای تنظیم‌بودن + نوع «عدد» پیشنهاد می‌شود');
  p.input('#catSearch','اجباری');
  ok(p.doc.querySelector('#catSettingHint')&&p.txt('#catSettingHint').includes('اجباری'),'«اجباری»: به‌جای نتیجهٔ خالی، مسیر تنظیم گفته می‌شود');
  p.input('#catSearch','گزینه پیش‌فرض');
  ok(p.doc.querySelector('#catSettingHint')&&p.txt('#catSettingHint').includes('پیاده‌سازی نشده'),'«پیش‌فرض»: صادقانه «پیاده‌سازی نشده» (نه کنترل تزئینی)');
  p.input('#catSearch','تأیید قوانین');
  ok(!p.doc.querySelector('#catSettingHint')&&p.all('#catList [data-add]')[0].dataset.add==='terms','«تأیید قوانین» → پذیرش قوانین (بدون راهنمای اضافی)');
  p.input('#catSearch','');
  /* رسانهٔ همراه: بدون مقدار قدیمی هیچ چیپی نیست؛ با مقدار قدیمی چیپ‌ها برای پاک‌کردن دیده می‌شوند */
  p.click('#catList [data-add="text"]');
  ok(p.doc.querySelector('#shField').classList.contains('editor')&&p.doc.querySelector('#fdMediaChips').hidden&&p.txt('#fdMediaNote0').includes('کنترلی برای آن نشان داده نمی‌شود'),'ویرایشگر: رسانهٔ در دست ساخت بدون چیپ‌های بی‌اثر');
  p.ev("FIELD_DRAFT.media='image';FIELD_DRAFT.mediaNote='x';renderFieldEditor()");
  ok(!p.doc.querySelector('#fdMediaChips').hidden&&p.txt('#fdMediaNote0').includes('نسخهٔ قدیمی')&&p.doc.querySelector('#shField [data-media="none"]'),'مقدار قدیمی رسانه: چیپ‌ها و دکمهٔ «بدون» (مقصد پرش readiness) ظاهر می‌شوند');
  p.ev("FIELD_DRAFT.media='none';FIELD_DRAFT.mediaNote='';renderFieldEditor()");
  /* خطای ذخیره کنار همان کنترل: گزینهٔ تکراری */
  p.ev("cancelFieldEdit()");
  p.ev("openSheet('shAdd')"); p.click('#catList [data-add="choice"]');
  p.ev("FIELD_DRAFT.opts=[{l:'الف'},{l:'الف'}];renderFieldOptions()");
  ok(p.ev('saveField()')===false&&p.doc.querySelector('#fdInlineError')&&p.doc.querySelector('#fdOptions [data-optl="1"][aria-invalid="true"]')&&p.doc.querySelector('#fdOptions [data-opt-row="1"]+#fdInlineError'),'گزینهٔ تکراری: ذخیره نمی‌شود و خطا زیر همان گزینه با aria-invalid می‌نشیند');
  p.input('#fdOptions [data-optl="1"]','ب');
  ok(!p.doc.querySelector('#fdInlineError')&&!p.doc.querySelector('#shField [aria-invalid="true"]'),'با اصلاح همان کنترل، خطای کنار کنترل پاک می‌شود');
  ok(p.ev('saveField()')===true&&!p.doc.querySelector('#fdInlineError'),'پس از اصلاح، ذخیره می‌شود');
  ok(p.errors.length===0,'بدون خطای کنسول');
}
console.log(`\nbuilder-fields: ${checks} بررسی، ${fails} خطا`);
process.exit(fails?1:0);
