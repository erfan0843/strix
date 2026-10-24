/* ══════════════════════════════════════════════════════════════════════════
   آزمون فرم خرید محتوای ضبط‌شده (فاز ۹.۱) — form.html با purpose=recording_access
   اجرا: node --max-old-space-size=3072 --test form-purchase.test.mjs
   معیارها: خرید ≠ ثبت‌نام (بدون بلیت/پیوند بله)، مهمان فقط «ورود برای خرید»، مبلغ و روش
   پرداخت از bootstrap سرور، رسید به‌تنهایی دسترسی نمی‌دهد، وضعیت «در فروش نیست» صادقانه.
   ══════════════════════════════════════════════════════════════════════════ */
import {fileURLToPath,pathToFileURL} from 'node:url';
import test from 'node:test';
import assert from 'node:assert/strict';
import jsdom from 'jsdom';
import fs from 'node:fs';
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
const safe=value=>JSON.stringify(value).replace(/</g,'\\u003c').replace(/>/g,'\\u003e').replace(/&/g,'\\u0026');
const REC='rec-1ce219fb32',EV='ev-1ce219fb32',FID='purchase-form-smoke';
function purchaseForm({signedIn=true,accessState='none',price=1500000,methods=['card_transfer']}={}){
  const card=methods.includes('card_transfer')?{number:'6037997599999993',bank:'بانک نمونه',holder:'انجمن نجوم'}:undefined;
  return {id:FID,name:'خرید ضبط کارگاه نجوم',model:'registration',need:'reg',slug:'buy-astro',status:'published',version:1,
    purpose:'recording_access',recording_id:REC,
    purchase:{recording_id:REC,event_id:EV,title:'ضبط کارگاه نجوم',access_state:accessState,signed_in:signedIn,price,currency:'IRR',selection:{items:[0],party_count:1}},
    display:'one',dir:'rtl',after:'view',profilePrefill:false,onePerPerson:true,limit:'none',cap:0,wait:0,taken:0,
    receiptUploadRequired:methods.includes('card_transfer'),enabledPaymentMethods:[...methods],...(card?{paymentCard:card}:{}),
    fields:[{id:'full-name',t:'text',l:'نام کامل',required:true,prof:true,placeholder:'نام'}],
    fin:[{l:'دسترسی به ضبط',p:price,off:0,req:true,d:''}],
    settings:{display:'one',dir:'rtl',after:'view',profilePrefill:false,notify:{on:false},enabledPaymentMethods:[...methods],...(card?{paymentCard:card}:{})}};
}
function api({accessState='none',submitStatus=200,submitPayload=null}={}){
  const calls=[];let draft={answers:{},companions:[],submitted:false,status:'draft',form_version:1},payment=null,receipt=false;
  const response=(status,payload)=>({ok:status>=200&&status<300,status,json:async()=>payload});
  const intent=()=>payment?{...payment,response_status:draft.submitted?draft.status:'',receipt_uploaded:receipt,tracking_code:draft.tracking_code||'',ticket_type:null}:null;
  const fetch=async(path,init={})=>{
    const method=String(init.method||'GET').toUpperCase();let body=null;
    if(typeof init.body==='string'){try{body=JSON.parse(init.body)}catch(_){body=init.body}}else if(init.body)body=init.body;
    calls.push({path,method,body});
    if(path==='/api/public/forms/'+FID+'/draft'&&method==='GET')return response(200,{...draft,payment_intent:intent()});
    if(path==='/api/public/forms/'+FID+'/draft'&&method==='PATCH'){draft={...draft,answers:body.answers||{}};return response(200,{saved:true})}
    if(path==='/api/public/forms/'+FID+'/responses'&&method==='POST'){
      if(submitStatus!==200)return response(submitStatus,submitPayload||{detail:'error'});
      payment={payment_id:'pay-1',method:'card_transfer',status:'awaiting_receipt',amount:1500000,currency:'IRR',invoice_url:'',expires_at:'',selection:{items:[{index:0,name:'دسترسی به ضبط',amount:1500000}],party_count:1,coupon_code:'',coupon_applied:false}};
      draft={answers:body.answers||{},companions:[],submitted:true,status:'accepted',form_version:1,tracking_code:'F000000001',receipt_uploaded:false,payment_intent:payment};
      return response(200,{accepted:true,status:'accepted',receipt_uploaded:false,ticket_type:null,payment_id:'pay-1',payment_method:'card_transfer',payment_status:'awaiting_receipt',
        purpose:'recording_access',purchase:{recording_id:REC,access_state:accessState,order_status:'awaiting_receipt'},message:'درخواست خرید ثبت شد.'});
    }
    if(path==='/api/public/forms/'+FID+'/receipt'&&method==='POST'){receipt=true;payment={...payment,status:'receipt_submitted'};draft={...draft,receipt_uploaded:true,payment_intent:payment};return response(200,{uploaded:true,created:true,review_task_id:'task-1'})}
    if(path==='/api/public/forms/'+FID+'/ticket-link')return response(409,{detail:{code:'ticket_not_available_for_purchase'}});
    return response(404,{detail:'not_found'});
  };
  return {fetch,calls};
}
async function load(form,fetchImpl,routeError='',draftBootstrap=null){
  const html=fs.readFileSync(DIR+'form.html','utf8').replace('<!--nora-public-form-->',safe(form)).replace('<!--nora-public-draft-->',safe(draftBootstrap))
    .replace('<!--nora-public-route-error-->',routeError?safe(routeError):'');
  const errors=[],url=pathToFileURL(DIR+'form.html').href+'?fid='+FID+'&kind=reg';
  const dom=new JSDOM(html,{url,runScripts:'dangerously',resources:offlineResources,pretendToBeVisual:true,beforeParse(w){
    w.scrollTo=()=>{};if(w.Element&&!w.Element.prototype.scrollIntoView)w.Element.prototype.scrollIntoView=()=>{};
    if(!w.matchMedia)w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
    Object.defineProperty(w,'localStorage',{configurable:true,value:makeStore()});
    w.__NORA_TEST_FIXTURE_MODE__=true;
    w.fetch=(...args)=>fetchImpl?Promise.resolve(fetchImpl(...args)):Promise.reject(new Error('network disabled'));
    w.open=()=>null;
    w.addEventListener('error',e=>errors.push('error: '+(e.message||'')));
    w.console.error=(...args)=>errors.push('console.error: '+args.join(' '));
  }});
  const {window}=dom;
  if(window.document.readyState!=='complete')await new Promise(resolve=>{const t=setTimeout(resolve,5000);window.addEventListener('load',()=>{clearTimeout(t);resolve()},{once:true})});
  await wait(80);
  const doc=window.document;
  return {dom,window,doc,errors,
    click:s=>{const el=doc.querySelector(s);if(!el)throw new Error('نیست: '+s);el.dispatchEvent(new window.MouseEvent('click',{bubbles:true,cancelable:true}))},
    input:(s,v)=>{const el=doc.querySelector(s);if(!el)throw new Error('نیست: '+s);el.value=v;el.dispatchEvent(new window.Event('input',{bubbles:true}));el.dispatchEvent(new window.Event('change',{bubbles:true}))},
    txt:s=>{const el=doc.querySelector(s);return el?el.textContent.replace(/\s+/g,' ').trim():''},
    visible:()=>[...doc.querySelectorAll('.screen')].filter(el=>el.classList.contains('on')).map(el=>el.id)};
}
test('فرم خرید محتوای ضبط‌شده در form.html',async()=>{
  const hasRouteErrorSlot=fs.readFileSync(DIR+'form.html','utf8').includes('<!--nora-public-route-error-->');
  console.log('\n— مهمان: فقط «ورود برای خرید»، بدون شروع فرم —');
  {
    const guestApi=api();const p=await load(purchaseForm({signedIn:false}),guestApi.fetch);
    ok(p.errors.length===0,'بدون خطای JavaScript'+(p.errors.length?': '+p.errors[0]:''));
    const header=p.doc.querySelector('#purchaseHeader');
    ok(header&&!header.hidden&&p.txt('#purchaseHeader').includes('ضبط کارگاه نجوم')&&p.txt('[data-purchase-price]').includes('۱٬۵۰۰٬۰۰۰'),'سربرگ خرید: عنوان محصول و مبلغ از bootstrap سرور');
    ok(p.txt('#purchaseHeader').includes('ثبت‌نام یا حضور در رویداد به شمار نمی‌آید'),'به‌روشنی می‌گوید خرید ≠ ثبت‌نام/حضور و بلیت ندارد');
    const login=p.doc.querySelector('[data-purchase-login]');
    ok(login&&/^login\.html\?next=/.test(login.getAttribute('href'))&&decodeURIComponent(login.getAttribute('href')).includes('fid='+FID),'دکمهٔ ورود با بازگشت به همین فرم');
    ok(p.doc.querySelector('[data-purchase-event]').getAttribute('href')==='event.html?id='+EV+'#recording','پیوند صفحهٔ رویداد با شناسهٔ سروری');
    p.click('#next');await wait(30);
    ok(p.visible().join()==='u1'&&!guestApi.calls.some(c=>c.method==='POST'),'مهمان با «شروع» جلو نمی‌رود و هیچ POSTی نمی‌فرستد');
    p.dom.window.close();
  }
  console.log('\n— خریدار واردشده: مبلغ/روش از سرور → ثبت پاسخ → رسید فقط «در انتظار بررسی» —');
  {
    const buyerApi=api();const p=await load(purchaseForm({signedIn:true}),buyerApi.fetch);
    ok(p.errors.length===0,'بدون خطای JavaScript'+(p.errors.length?': '+p.errors[0]:''));
    ok(!p.doc.querySelector('[data-purchase-login]')&&!p.doc.querySelector('[data-purchase-login-note]'),'برای کاربر واردشده دکمهٔ ورود نمایش داده نمی‌شود');
    p.click('#next');await wait(30);p.input('#qa0','خریدار آزمایشی');await wait(760);p.click('#next');await wait(30);
    ok(p.visible().join()==='u8'&&p.doc.querySelectorAll('#u8 [data-method]:not([hidden])').length===1&&!p.doc.querySelector('[data-method="card_transfer"]').hidden,'فقط روش پرداختی که سرور/فرم‌ساز تعیین کرده نمایان است');
    p.click('[data-fin="0"]');p.click('[data-method="card_transfer"]');p.click('#next');await wait(30);
    ok(p.visible().join()==='u9'&&p.txt('#paymentBankCardNumber')==='6037 9975 9999 9993'&&p.txt('#payAmount').includes('۱٬۵۰۰٬۰۰۰'),'کارت مقصد و مبلغ از دادهٔ سروری فرم، نه ورودی کاربر');
    p.click('#next');await wait(150);
    const submit=buyerApi.calls.find(c=>c.method==='POST'&&c.path.endsWith('/responses'));
    ok(!!submit&&submit.body&&submit.body.payment&&submit.body.payment.method==='card_transfer'&&!('amount' in submit.body.payment),'پاسخ با روش پرداخت ثبت شد؛ مبلغ در بدنهٔ درخواست فرستاده نمی‌شود');
    ok(p.visible().join()==='u11'&&p.doc.querySelector('#serverTicketPreview').hidden&&!buyerApi.calls.some(c=>c.path.endsWith('/ticket-link')),'گام رسید باز شد؛ هیچ بلیت یا پیوند بله ساخته نشد');
    const result=p.doc.querySelector('#purchaseResult');
    ok(!result||result.hidden||result.dataset.purchaseState!=='active','پیش از تأیید، هیچ نشان «دسترسی فعال» وجود ندارد');
    const input=p.doc.querySelector('#serverReceiptFile');
    Object.defineProperty(input,'files',{configurable:true,value:[new p.window.File(['%PDF-1.4\n'],'receipt.pdf',{type:'application/pdf'})]});
    input.dispatchEvent(new p.window.Event('change',{bubbles:true}));
    p.click('#next');await wait(250);
    const uploaded=buyerApi.calls.some(c=>c.method==='POST'&&c.path.endsWith('/receipt'));
    ok(uploaded&&!buyerApi.calls.some(c=>/\/orders|\/recordings\//.test(c.path)),'رسید به مسیر رسمی فرم فرستاده شد (نه مسیر موازی سفارش)');
    ok(p.doc.querySelector('#receiptReviewBaleLink')?.hidden!==false&&!p.txt('#receiptReviewMessage').includes('بلیت'),'پس از رسیدِ خرید، پیوند بلیت بله ساخته نمی‌شود');
    const after=p.doc.querySelector('#purchaseResult');
    ok(after&&!after.hidden&&after.dataset.purchaseState==='review'&&p.txt('#purchaseResult').includes('فقط پس از تأیید بازبین'),'پس از رسید: «در انتظار بررسی» و تصریح این‌که رسید به‌تنهایی دسترسی نمی‌دهد');
    ok(!p.doc.querySelector('[data-purchase-view]')&&p.doc.querySelector('[data-purchase-orders]').getAttribute('href')==='account.html#payments','بدون دکمهٔ «مشاهدهٔ محتوا»؛ پیگیری از «سفارش‌ها و پرداخت‌ها»');
    p.dom.window.close();
  }
  console.log('\n— بازگشت/reload با همان کوکی در awaiting_receipt: کارت بارگذاری رسید باید نمایان باشد (9.7-پ) —');
  for(const bootstrap of [true,false]){
    const reloadApi=api();
    /* همان وضعیت سرور پس از ثبت پاسخ با کارت‌به‌کارت و پیش از بارگذاری رسید */
    const pending={payment_id:'pay-1',method:'card_transfer',status:'awaiting_receipt',amount:1500000,currency:'IRR',invoice_url:'',expires_at:'',
      selection:{items:[{index:0,name:'دسترسی به ضبط',amount:1500000}],party_count:1,coupon_code:'',coupon_percent:0}};
    const savedDraft={answers:{'full-name':'خریدار آزمایشی'},companions:[],submitted:true,status:'accepted',form_version:1,tracking_code:'F000000001',receipt_uploaded:false,payment_intent:pending};
    const baseFetch=reloadApi.fetch;
    const fetchWithDraft=async(path,init={})=>{
      const method=String(init.method||'GET').toUpperCase();
      if(path==='/api/public/forms/'+FID+'/draft'&&method==='GET'){reloadApi.calls.push({path,method,body:null});return {ok:true,status:200,json:async()=>savedDraft}}
      if(path==='/api/public/forms/'+FID+'/payment-intents/pay-1'){reloadApi.calls.push({path,method,body:null});return {ok:true,status:200,json:async()=>({...pending,response_status:'accepted',receipt_uploaded:false,tracking_code:'F000000001',ticket_type:null})}}
      return baseFetch(path,init);
    };
    const p=await load(purchaseForm({signedIn:true}),fetchWithDraft,'',bootstrap?savedDraft:null);
    await wait(400);
    const label=bootstrap?'bootstrap سروری':'بازیابی با GET /draft';
    ok(p.errors.length===0,'بدون خطای JavaScript ('+label+')'+(p.errors.length?': '+p.errors[0]:''));
    ok(p.visible().join()==='u11','پس از reload گام رسید (u11) باز می‌شود ('+label+')');
    const box=p.doc.querySelector('#serverReceiptUpload');
    ok(box&&box.hidden===false,'کارت بارگذاری رسید نمایان است، نه فقط دکمهٔ «ثبت فیش» ('+label+')');
    ok(p.doc.querySelector('#serverReceiptReview').hidden===true&&p.doc.querySelector('#serverTicketPreview').hidden===true,'بدون پیام «در صف بررسی» و بدون پیش‌نمایش بلیت پیش از بارگذاری رسید ('+label+')');
    ok(!reloadApi.calls.some(c=>c.method==='POST'&&c.path.endsWith('/responses')),'reload پاسخ/سفارش دوباره نمی‌سازد ('+label+')');
    p.dom.window.close();
  }
  console.log('\n— دسترسی فعال: فرم دوباره خرید نمی‌گیرد —');
  {
    const activeApi=api({accessState:'active'});const p=await load(purchaseForm({signedIn:true,accessState:'active'}),activeApi.fetch);
    ok(p.doc.querySelector('[data-purchase-state="active"]')&&p.doc.querySelector('[data-purchase-view]').getAttribute('href')==='event.html?id='+EV+'#recording','وضعیت فعال از سرور + دکمهٔ مشاهده');
    p.click('#next');await wait(30);
    ok(p.visible().join()==='u1'&&!activeApi.calls.some(c=>c.method==='POST'),'با دسترسی فعال، فرم شروع نمی‌شود و درخواستی نمی‌رود');
    p.dom.window.close();
  }
  console.log('\n— خطای سروری هنگام ثبت: account_required / recording_not_on_sale —');
  {
    const closedApi=api({submitStatus:409,submitPayload:{detail:{code:'recording_not_on_sale'}}});
    const p=await load(purchaseForm({signedIn:true}),closedApi.fetch);
    p.click('#next');await wait(30);p.input('#qa0','خریدار آزمایشی');await wait(760);p.click('#next');await wait(30);
    p.click('[data-fin="0"]');p.click('[data-method="card_transfer"]');p.click('#next');await wait(30);p.click('#next');await wait(150);
    ok(p.visible().join()!=='u11'&&p.visible().join()!=='u12'&&p.doc.body.textContent.includes('در فروش نیست'),'توقف فروش از سرور: پیام صادقانه، بدون گام رسید');
    p.dom.window.close();
  }
  if(hasRouteErrorSlot){
    console.log('\n— مسیر HTML: recording-not-on-sale —');
    const p=await load(purchaseForm({signedIn:true}),api().fetch,'recording-not-on-sale:'+REC);
    ok(p.doc.body.textContent.includes('این محتوا الان در فروش نیست'),'خطای مسیر «در فروش نیست» با متن صادقانه نشان داده می‌شود');
    p.dom.window.close();
  }else console.log('   · (جای‌نگهدار خطای مسیر در form.html نیست؛ این سناریو با آزمون API پوشش داده می‌شود)');
  console.log(`\nفرم خرید: ${checks-fails}/${checks} معیار`);
  assert.equal(fails,0,`${fails} معیار شکست خورد`);
});
