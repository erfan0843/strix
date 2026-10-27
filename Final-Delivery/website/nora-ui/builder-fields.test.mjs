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

console.log(`\nbuilder-fields: ${checks} بررسی، ${fails} خطا`);
process.exit(fails?1:0);
