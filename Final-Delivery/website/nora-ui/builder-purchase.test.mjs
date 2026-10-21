/* ══════════════════════════════════════════════════════════════════════════
   آزمون فرم‌ساز در حالت «فرم خرید محتوای ضبط‌شده» (فاز ۹.۱)
   اجرا: node --max-old-space-size=3072 --test builder-purchase.test.mjs
   معیارها: ورود با ?purpose=recording_access&recording=&ev= از پنل REC؛ مدل فقط ثبت‌نام؛ همراه و بلیت بسته؛
   محصول از API مدیریتی خوانده می‌شود (نه عدد ساختگی)؛ payload ذخیره purpose/recording_id سطح‌بالا دارد و
   ticketing ندارد؛ خطاهای سروری خرید با متن روشن نمایش داده می‌شوند.
   ══════════════════════════════════════════════════════════════════════════ */
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
const REC='rec-1ce219fb32',EV='ev-1ce219fb32';
function api({productStatus=200,product=null,createStatus=201,createDetail=null}={}){
  const calls=[];let record=null;
  const response=(status,payload)=>({ok:status>=200&&status<300,status,json:async()=>payload});
  const fetch=async(path,init={})=>{
    const method=String(init.method||'GET').toUpperCase();let body=null;
    if(typeof init.body==='string'){try{body=JSON.parse(init.body)}catch(_){body=init.body}}
    calls.push({path,method,body,headers:init.headers||{}});
    if(path==='/api/health')return response(200,{ok:true,formsEnabled:true,responsesEnabled:true,deliveryEnabled:false,formBalePaymentsReady:false});
    if(path==='/api/public/forms/capabilities')return response(200,{version:1,source:'same_application_fastapi',api_configured:true,
      models:['registration','questionnaire','survey','contest','exam','attendance','datacollect','order','election'].map(id=>({id,status:id==='registration'?'server':'limited',publishable:true,reason:''})),
      field_types:{text:{status:'server',reason:''},fullname:{status:'server',reason:''}},settings:{response_list:{status:'server',page_size_max:100}}});
    if(path==='/api/auth/me')return response(200,{authenticated:true,owner_id:'owner-qa',role:'owner'});
    if(path==='/api/account/me')return response(200,{authenticated:true,account_id:'owner-qa',role:'owner',permissions:['fm_create']});
    if(path==='/api/admin/events/'+EV+'/recording')return productStatus===200
      ?response(200,{recording:product||{id:REC,title:'ضبط کارگاه نجوم',status:'ready',commerce:{source:'product',form_id:null}},event_held:true,limits:{streaming:'none'}})
      :response(productStatus,{detail:productStatus===403?'permission_denied':'not_found'});
    if(path==='/api/forms'&&method==='POST'){
      if(createStatus!==201)return response(createStatus,{detail:createDetail||{code:'error'}});
      record={id:'form-purchase-1',name:body.name,model:body.model,need:body.need,slug:body.slug,ev:EV,purpose:body.purpose||'registration',recording_id:body.recording_id||null,
        fields:body.fields,settings:body.settings,status:'draft',version:1,response_count:0,created_at:'2026-10-22T00:00:00+00:00',updated_at:'2026-10-22T00:00:00+00:00'};
      return response(201,record);
    }
    if(record&&path==='/api/forms/'+record.id+'/readiness')return response(200,{source:'same_server_database',form_id:record.id,version:1,status:'draft',publishable:true,issues:[]});
    if(record&&path==='/api/forms/'+record.id&&method==='GET')return response(200,record);
    return response(404,{detail:'not_found'});
  };
  return {fetch,calls,get record(){return record}};
}
async function load(query,fetchImpl){
  const errors=[],url=pathToFileURL(DIR+'create.html').href+query;
  const dom=await JSDOM.fromFile(DIR+'create.html',{url,runScripts:'dangerously',resources:offlineResources,pretendToBeVisual:true,beforeParse(w){
    w.scrollTo=()=>{};if(w.Element&&!w.Element.prototype.scrollIntoView)w.Element.prototype.scrollIntoView=()=>{};
    if(!w.matchMedia)w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
    Object.defineProperty(w,'localStorage',{configurable:true,value:makeStore()});
    w.__NORA_TEST_FIXTURE_MODE__=false;
    Object.defineProperty(w.document,'cookie',{configurable:true,get:()=>'nora_csrf=owner-csrf'});
    w.fetch=(...args)=>Promise.resolve(fetchImpl(...args));
    w.open=()=>null;
    w.addEventListener('error',e=>errors.push('error: '+(e.message||'')));
    w.console.error=(...args)=>errors.push('console.error: '+args.join(' '));
  }});
  const {window}=dom;
  if(window.document.readyState!=='complete')await new Promise(resolve=>{const t=setTimeout(resolve,5000);window.addEventListener('load',()=>{clearTimeout(t);resolve()},{once:true})});
  await wait(150);
  const doc=window.document;
  return {dom,window,doc,errors,
    click:s=>{const el=doc.querySelector(s);if(!el)throw new Error('نیست: '+s);el.dispatchEvent(new window.MouseEvent('click',{bubbles:true,cancelable:true}))},
    txt:s=>{const el=doc.querySelector(s);return el?el.textContent.replace(/\s+/g,' ').trim():''}};
}
const PURCHASE_QS='?purpose=recording_access&recording='+REC+'&ev='+EV+'&back='+encodeURIComponent('admin.html#newev');
test('فرم‌ساز: حالت فرم خرید محتوای ضبط‌شده',async()=>{
  console.log('\n— ورود از پنل REC: قفل مدل/همراه/بلیت و خواندن محصول از سرور —');
  {
    const a=api();const b=await load(PURCHASE_QS,a.fetch);
    ok(b.errors.length===0,'بدون خطای JavaScript'+(b.errors.length?': '+b.errors[0]:''));
    const box=b.doc.querySelector('#purchaseFormBox');
    ok(box&&!box.hidden&&b.txt('#purchaseFormBox').includes('ضبط کارگاه نجوم')&&b.txt('#purchaseFormBox').includes('آمادهٔ انتشار'),'جعبهٔ فرم خرید: عنوان و وضعیت واقعی محصول از API مدیریتی');
    ok(a.calls.some(c=>c.path==='/api/admin/events/'+EV+'/recording'),'محصول از مسیر مدیریتیِ همان رویداد خوانده می‌شود');
    ok(b.txt('#purchaseFormBox').includes('خرید ثبت‌نام یا حضور به شمار نمی‌آید'),'توضیح صریح: خرید ≠ ثبت‌نام ≠ حضور');
    const tiles=[...b.doc.querySelectorAll('#tiles [data-model]')];
    ok(tiles.length>1&&tiles.every(t=>t.dataset.model==='registration'?!t.disabled&&t.classList.contains('on'):t.disabled),'فقط کاشی «ثبت‌نام» فعال است؛ سایر مدل‌ها قفل‌اند');
    ok(b.window.eval("S.model==='registration'&&S.purpose==='recording_access'&&S.recordingId==='"+REC+"'&&S.guestsOn===false&&S.ticketingEnabled===false"),'وضعیت داخلی: مدل ثبت‌نام، بدون همراه، بدون بلیت');
    b.click('#guestsOn');await wait(20);
    ok(b.window.eval('S.guestsOn===false')&&b.doc.querySelector('#guestsOn').getAttribute('aria-checked')==='false','کلید همراه‌آوردن در فرم خرید روشن نمی‌شود');
    b.click('#ticketingEnabled');await wait(20);
    ok(b.window.eval('S.ticketingEnabled===false')&&b.doc.querySelector('#ticketingEnabled').getAttribute('aria-checked')==='false','کلید مدل بلیت در فرم خرید روشن نمی‌شود');
    const survey=b.doc.querySelector('#tiles [data-model="survey"]');
    survey.removeAttribute('disabled');survey.dispatchEvent(new b.window.MouseEvent('click',{bubbles:true,cancelable:true}));await wait(20);
    ok(b.window.eval("S.model==='registration'"),'حتی با دور زدن قفل DOM، مدل عوض نمی‌شود');
    /* ذخیره: payload با purpose/recording_id سطح‌بالا و بدون ticketing */
    b.window.eval("S.title='خرید ضبط کارگاه نجوم'");
    b.click('#publish');await wait(400);
    const post=a.calls.find(c=>c.method==='POST'&&c.path==='/api/forms');
    ok(!!post&&post.body.purpose==='recording_access'&&post.body.recording_id===REC&&post.body.model==='registration'&&post.body.need==='reg'&&post.body.ev===EV,'ذخیره: purpose و recording_id در سطح بالا، مدل ثبت‌نام، رویداد همان پنل');
    ok(!!post&&!('ticketing' in post.body.settings)&&post.body.settings.guestsOn===false&&post.body.settings.ticketingEnabled===false&&!('purpose' in post.body.settings)&&!('recording_id' in post.body.settings),'تنظیمات: بدون بلیت و همراه؛ هدف/محصول در settings تکرار نمی‌شود');
    ok(post&&post.headers['Idempotency-Key']&&post.headers['X-CSRF-Token']==='owner-csrf','ذخیره با کلید یکتا و CSRF');
    ok(b.doc.querySelector('#doneCard').style.display==='block'&&b.doc.querySelector('#donePreview').getAttribute('href')&&b.doc.querySelector('#donePreview').getAttribute('href').startsWith('form.html?fid=form-purchase-1'),'پس از ذخیره، پیش‌نمایش همان form.html است (ورودی استاندارد خرید)');
    b.dom.window.close();
  }
  console.log('\n— بدون دسترسی/بدون محصول: پیام صادقانه، بدون عدد ساختگی —');
  {
    const a=api({productStatus:403});const b=await load(PURCHASE_QS,a.fetch);
    ok(b.txt('#purchaseFormBox').includes('دسترسی مدیریتی لازم است')&&!b.txt('#purchaseFormBox').includes('ریال'),'۴۰۳: توضیح دسترسی؛ بدون قیمت یا وضعیت ساختگی');
    b.dom.window.close();
    const m=api({productStatus:404});const bm=await load(PURCHASE_QS,m.fetch);
    ok(bm.txt('#purchaseFormBox').includes('محصول ضبط‌شده‌ای برای این رویداد در سرور نیست'),'۴۰۴: راهنمایی ساخت محصول در پنل رویداد');
    bm.dom.window.close();
    const mm=api({product:{id:'rec-other',title:'محصول دیگر',status:'draft',commerce:{source:'product',form_id:null}}});const bmm=await load(PURCHASE_QS,mm.fetch);
    ok(bmm.txt('#purchaseFormBox').includes('یکی نیست'),'ناهم‌خوانی شناسهٔ محصول با رویداد اعلام می‌شود');
    bmm.dom.window.close();
  }
  console.log('\n— خطای سروری هنگام ذخیره: کدهای خرید با متن روشن —');
  {
    const a=api({createStatus:422,createDetail:{code:'purchase_form_event_mismatch',message:'x'}});const b=await load(PURCHASE_QS,a.fetch);
    b.window.eval("S.title='خرید ضبط کارگاه نجوم'");b.click('#publish');await wait(400);
    ok(b.txt('#ownerApiMessage').includes('رویداد فرم با رویداد محصول یکی نیست'),'۴۲۲ purchase_form_event_mismatch → پیام فارسی روشن');
    b.dom.window.close();
    const d=api({createStatus:409,createDetail:{code:'purchase_form_already_published'}});const bd=await load(PURCHASE_QS,d.fetch);
    bd.window.eval("S.title='خرید ضبط کارگاه نجوم'");bd.click('#publish');await wait(400);
    ok(bd.txt('#ownerApiMessage').includes('فرم خرید منتشرشده دارد'),'۴۰۹ purchase_form_already_published → پیام روشن');
    bd.dom.window.close();
  }
  console.log('\n— فرم عادی: بدون پارامتر خرید هیچ‌چیز تغییر نمی‌کند —');
  {
    const a=api();const b=await load('?ev='+EV+'&need=reg',a.fetch);
    ok(b.doc.querySelector('#purchaseFormBox').hidden&&!a.calls.some(c=>c.path.includes('/recording'))&&b.window.eval("S.purpose==='registration'"),'فرم ثبت‌نام: جعبهٔ خرید پنهان و بدون فراخوانی محصول');
    ok([...b.doc.querySelectorAll('#tiles [data-model]')].filter(t=>!t.disabled).length>1,'کاشی‌های مدل در فرم عادی قفل نیستند');
    b.window.eval("S.title='ثبت‌نام کارگاه'");b.click('#publish');await wait(400);
    const post=a.calls.find(c=>c.method==='POST'&&c.path==='/api/forms');
    ok(!!post&&post.body.purpose===undefined&&post.body.recording_id===undefined&&post.body.settings.purpose===undefined,'payload فرم عادی بدون purpose/recording_id (سرور پیش‌فرض ثبت‌نام را می‌گذارد)');
    b.dom.window.close();
  }
  console.log(`\nفرم‌ساز خرید: ${checks-fails}/${checks} معیار`);
  assert.equal(fails,0,`${fails} معیار شکست خورد`);
});
