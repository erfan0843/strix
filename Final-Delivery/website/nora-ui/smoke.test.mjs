/* ══════════════════════════════════════════════════════════════════════════
   آزمون دودی ایمنی پیش‌نمایش نورا
   اجرا: node smoke.test.mjs
   معیارها: نشان محلی، ساعت محلی، QR بدون مقصد عمومی، پیوند و embed بیرونی غیرفعال،
   رسانهٔ مستقیم فقط با HTTPS عمومیِ پذیرفته‌شده؛ پرداخت محلی غیرفعال، بارگذاری فیش فقط در فرم سروری، ذخیرهٔ پاسخ محلی و شرط تأیید مالک برای brSave.
   ══════════════════════════════════════════════════════════════════════════ */
import {fileURLToPath,pathToFileURL} from 'node:url';
import jsdom from 'jsdom';
import fs from 'node:fs';
const {JSDOM}=jsdom;
const DIR=fileURLToPath(new URL('./',import.meta.url));
/* The legacy smoke scenarios use local fixtures only through this explicit test flag. */
const TEST_FIXTURE_MODE=true;
const offlineResources = {
  interceptors: [jsdom.requestInterceptor(async (request) => {
    if (request.url === 'https://tapi.bale.ai/miniapp.js') {
      return new Response('window.Bale = { WebApp: { initData: "" } };', {
        headers: { 'Content-Type': 'application/javascript' },
      });
    }
    if (new URL(request.url).protocol === 'https:') return new Response('', { status: 403 });
    return undefined;
  })],
};
let checks=0, fails=0;
const ok=(condition,message)=>{checks++; if(!condition){fails++; console.log('   ✗ '+message)}else console.log('   ✓ '+message)};
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function makeStore(init={}){
  const m=new Map(Object.entries(init));
  return {getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k),
    clear:()=>m.clear(),key:i=>[...m.keys()][i],get length(){return m.size},_dump:()=>[...m.keys()]};
}
async function loadHtml(file,html=null,store=makeStore(),query='',fetchImpl=null,sessionStore=null,fixtureMode=TEST_FIXTURE_MODE){
  const errors=[], network=[], healthChecks=[], capabilityChecks=[], opened=[], url=pathToFileURL(DIR+file).href+query,options={
    ...(query?{url}:{}),runScripts:'dangerously',resources:offlineResources,pretendToBeVisual:true,
    beforeParse(w){
      w.scrollTo=()=>{}; if(w.Element&&!w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView=()=>{};
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      Object.defineProperty(w,'localStorage',{configurable:true,value:store});
      w.__NORA_TEST_FIXTURE_MODE__=fixtureMode===true;
      if(sessionStore)Object.defineProperty(w,'sessionStorage',{configurable:true,value:sessionStore});
      w.fetch=(...args)=>{
        const path=String(args[0]||'');
        if(path==='/api/health'||path.startsWith('/api/health?'))healthChecks.push(path);
        else if(path==='/api/public/forms/capabilities')capabilityChecks.push(path);
        else network.push(args[0]);
        return fetchImpl?Promise.resolve(fetchImpl(...args)):Promise.reject(new Error('network disabled in smoke test'));
      };
      w.open=(...args)=>{opened.push(args);return null};
      w.addEventListener('error',e=>errors.push('error: '+(e.message||'')));
      w.console.error=(...args)=>errors.push('console.error: '+args.join(' '));
      w.onerror=message=>errors.push('onerror: '+message);
    }};
  const dom=html===null?await JSDOM.fromFile(DIR+file,options):new JSDOM(html,{...options,url});
  const {window}=dom;
  if(window.document.readyState!=='complete') await new Promise(resolve=>{
    const timer=setTimeout(resolve,5000);
    window.addEventListener('load',()=>{clearTimeout(timer);resolve()},{once:true});
  });
  await wait(60);
  const doc=window.document;
  return {dom,window,doc,store,errors,network,healthChecks,capabilityChecks,opened,
    click:selector=>{const el=doc.querySelector(selector); if(!el) throw new Error('نیست: '+selector);
      el.dispatchEvent(new window.MouseEvent('click',{bubbles:true,cancelable:true}))},
    set:(selector,value)=>{const el=doc.querySelector(selector); if(!el) throw new Error('نیست: '+selector); el.value=value;
      el.dispatchEvent(new window.Event('change',{bubbles:true}))},
    input:(selector,value)=>{const el=doc.querySelector(selector);if(!el)throw new Error('نیست: '+selector);el.value=value;
      el.dispatchEvent(new window.Event('input',{bubbles:true}));el.dispatchEvent(new window.Event('change',{bubbles:true}))},
    txt:selector=>{const el=doc.querySelector(selector);return el?el.textContent.replace(/\s+/g,' ').trim():''},
    all:selector=>[...doc.querySelectorAll(selector)],
    visible:selector=>[...doc.querySelectorAll(selector)].filter(el=>el.classList.contains('on')).map(el=>el.id)};
}
async function load(file,store=makeStore(),query='',fetchImpl=null,{fixtureMode=TEST_FIXTURE_MODE}={}){
  return loadHtml(file,null,store,query,fetchImpl,null,fixtureMode);
}
function safeScriptJSON(value){return JSON.stringify(value).replace(/</g,'\\u003c').replace(/>/g,'\\u003e').replace(/&/g,'\\u0026');}
async function loadPublicForm(form,fetchImpl,draft=null){
  const html=fs.readFileSync(DIR+'form.html','utf8')
    .replace('<!--nora-public-form-->',safeScriptJSON(form))
    .replace('<!--nora-public-draft-->',safeScriptJSON(draft));
  return loadHtml('form.html',html,makeStore(),'?fid='+encodeURIComponent(String(form.id||'')),fetchImpl);
}
function makePublicFormData(id='server-public-smoke',receiptUploadRequired=false,enabledPaymentMethods=receiptUploadRequired?['card_transfer']:[]){
  const paymentCard=receiptUploadRequired?{number:'4111111111111111',bank:'بانک نمونه',holder:'حساب سازمان'}:undefined;
  const paymentInstructions=receiptUploadRequired?'واریز فقط به کارت مقصد.\nرسید را همین‌جا ثبت کن.':undefined;
  return {id,name:'فرم سروری آزمایشی',model:'registration',need:'reg',slug:'public-smoke',status:'published',version:2,
    display:'one',dir:'rtl',after:'view',profilePrefill:false,onePerPerson:false,limit:'none',cap:0,wait:0,taken:0,
    receiptUploadRequired,enabledPaymentMethods:[...enabledPaymentMethods],...(paymentCard?{paymentCard}:{}),...(paymentInstructions?{paymentInstructions}:{}),
    fields:[{id:'full-name',t:'text',l:'نام کامل',required:true,prof:true,placeholder:'نام'}],
    ...(receiptUploadRequired?{fin:[{l:'ورودی نمونه',p:650000,off:0,req:true,d:''}]}:{}),
    settings:{display:'one',dir:'rtl',after:'view',profilePrefill:false,notify:{on:false},
      enabledPaymentMethods:[...enabledPaymentMethods],...(paymentCard?{paymentCard}:{}),...(paymentInstructions?{paymentInstructions}:{})}};
}
function makePublicApiMock({id='server-public-smoke',draft={answers:{},companions:[],submitted:false,status:'draft',form_version:2},submitStatus='accepted',receiptUploadRequired=false,ticketType=null}={}){
  const calls=[];let payment=null,paymentCounter=0;
  const ticketUrl='https://ble.ir/nora_test_bot?start=ft_'+'A'.repeat(48);
  const response=(status,payload)=>({ok:status>=200&&status<300,status,json:async()=>payload});
  const paymentPayload=(overrides={})=>payment?{payment_id:payment.payment_id,method:payment.method,status:payment.status,
    amount:payment.amount,currency:payment.currency,invoice_url:payment.invoice_url,expires_at:payment.expires_at,
    selection:payment.selection,response_status:draft.submitted?draft.status:'',receipt_uploaded:draft.receipt_uploaded===true,
    tracking_code:draft.tracking_code||'',ticket_type:draft.ticket_type||null,...overrides}:null;
  const fetch=async(path,init={})=>{
    const method=String(init.method||'GET').toUpperCase();
    let body=null;
    if(typeof init.body==='string'){try{body=JSON.parse(init.body)}catch(_){body=init.body}}
    else if(init.body)body=init.body;
    calls.push({path,method,body,headers:init.headers||{},credentials:init.credentials});
    if(path==='/api/public/forms/'+id+'/draft'&&method==='GET')return response(200,{...draft,payment_intent:paymentPayload()});
    if(path==='/api/public/forms/'+id+'/draft'&&method==='PATCH'){
      draft={...draft,answers:body.answers||{},companions:Array.isArray(body.companions)?body.companions:[],hasUnsavedChanges:true};return response(200,{saved:true});
    }
    if(path==='/api/public/forms/'+id+'/payment-intents'&&method==='POST'){
      paymentCounter++;
      const selected=body&&body.selection&&Array.isArray(body.selection.items)?body.selection.items:[];
      const items=selected.map(index=>({index,name:'ورودی نمونه',amount:650000}));
      payment={payment_id:'payment-'+paymentCounter,method:'bale_wallet',status:'pending',amount:650000,currency:'IRR',
        invoice_url:'https://ble.ir/payment-invoice-smoke',expires_at:'2026-10-31T10:00:00+00:00',
        selection:{items,party_count:1,coupon_code:body&&body.selection&&body.selection.coupon_code||'',coupon_applied:false}};
      draft={...draft,payment_intent:payment};return response(201,paymentPayload());
    }
    const paymentMatch=path.match(new RegExp('^/api/public/forms/'+id+'/payment-intents/([^/]+)$'));
    if(paymentMatch&&payment&&decodeURIComponent(paymentMatch[1])===payment.payment_id&&method==='GET')return response(200,paymentPayload());
    if(paymentMatch&&payment&&decodeURIComponent(paymentMatch[1])===payment.payment_id&&method==='DELETE'){
      payment={...payment,status:'cancelled',invoice_url:''};draft={...draft,payment_intent:payment};return response(200,{payment_id:payment.payment_id,status:'cancelled'});
    }
    if(path==='/api/public/forms/'+id+'/responses'&&method==='POST'){
      const assignedType=submitStatus==='accepted'?ticketType:null;
      const cardPayment=body.payment&&body.payment.method==='card_transfer';
      if(cardPayment){
        paymentCounter++;payment={payment_id:'payment-card-'+paymentCounter,method:'card_transfer',status:'awaiting_receipt',amount:650000,currency:'IRR',
          invoice_url:'',expires_at:'',selection:{items:(body.payment.selection&&body.payment.selection.items||[]).map(index=>({index,name:'ورودی نمونه',amount:650000})),
            party_count:1,coupon_code:'',coupon_applied:false}};
      }
      draft={answers:body.answers||{},companions:Array.isArray(body.companions)?body.companions:[],submitted:true,status:submitStatus,form_version:2,
        receipt_uploaded:false,ticket_type:assignedType,tracking_code:'F1234567890',payment_intent:payment};
      return response(200,{accepted:true,status:submitStatus,receipt_uploaded:false,ticket_type:assignedType,
        payment_id:payment&&payment.payment_id||'',payment_method:payment&&payment.method||'',payment_status:payment&&payment.status||'',message:submitStatus==='waitlisted'
        ?'پاسخ در فهرست انتظار ثبت شد.'
        :'پاسخ در پایگاه‌دادهٔ همین سامانه ثبت شد.'});
    }
    if(path==='/api/public/forms/'+id+'/receipt'&&method==='POST'){
      if(!draft.submitted)return response(409,{detail:'ticket_response_not_submitted'});
      if(payment&&payment.method==='card_transfer')payment={...payment,status:'receipt_submitted'};
      draft={...draft,receipt_uploaded:true,payment_intent:payment};return response(200,{uploaded:true,created:true});
    }
    if(path==='/api/public/forms/'+id+'/ticket-link'&&method==='POST'){
      if(receiptUploadRequired&&!draft.receipt_uploaded)return response(409,{detail:{code:'ticket_receipt_required'}});
      if(payment&&payment.method==='card_transfer'&&payment.status!=='paid_manual'&&!draft.receipt_uploaded)
        return response(409,{detail:{code:'ticket_payment_not_confirmed'}});
      return response(200,{delivery_url:ticketUrl,tracking_code:'F1234567890',expires_at:'2026-10-31T10:00:00+00:00'});
    }
    if(path==='/api/public/forms/'+id+'/draft'&&method==='DELETE'){
      draft={answers:{},companions:[],submitted:false,status:'draft',form_version:2};payment=null;return response(200,{deleted:true,responseDeleted:false});
    }
    return response(404,{detail:'not_found'});
  };
  return {fetch,calls,get draft(){return draft},get payment(){return payment},setPaymentStatus(status){
    if(!payment)return false;payment={...payment,status,invoice_url:status==='pending'?payment.invoice_url:''};draft={...draft,payment_intent:payment};return true;
  }};
}
function makeFormsApiMock({authenticated=true,id='server-form-1',initialRecord=null,responses=[],readinessIssues=[]}={}){
  const calls=[]; let loggedIn=authenticated, record=initialRecord;
  const response=(status,payload)=>({ok:status>=200&&status<300,status,json:async()=>payload});
  const fetch=async(path,init={})=>{
    const method=String(init.method||'GET').toUpperCase();
    calls.push({path,method,headers:init.headers||{},credentials:init.credentials,body:init.body||''});
    if(path==='/api/health') return response(200,{ok:true,formsEnabled:true,responsesEnabled:true,deliveryEnabled:false,formBalePaymentsReady:false});
    if(path==='/api/public/forms/capabilities'&&method==='GET')return response(200,{
      version:1,source:'same_application_fastapi',api_configured:true,
      models:['registration','questionnaire','survey','contest','exam','attendance','datacollect','election'].map(id=>({id,status:id==='registration'?'server':'limited',publishable:true,reason:'پاسخ سروری آزمایشی'}))
        .concat([{id:'order',status:'unavailable',publishable:false,reason:'سفارش آماده نیست'}]),
      field_types:{text:{status:'server',reason:''},fullname:{status:'server',reason:''},mobile:{status:'limited',reason:'بدون احراز شماره'},uni:{status:'limited',reason:'فهرست محلی'},image:{status:'unavailable',reason:'بارگذاری وصل نیست'},file:{status:'unavailable',reason:'بارگذاری وصل نیست'}},
      settings:{response_list:{status:'server',page_size_max:100},schedule:{status:'unavailable'},one_response_per_person:{status:'unavailable'}}
    });
    if(path==='/api/auth/me') return loggedIn
      ?response(200,{authenticated:true,owner_id:'owner-smoke',role:'owner'})
      :response(401,{detail:'authentication_required'});
    if(path==='/api/account/me') return loggedIn
      ?response(200,{authenticated:true,account_id:'owner-smoke',role:'owner',permissions:['fm_create']})
      :response(401,{detail:'authentication_required'});
    if(path==='/api/auth/login'){
      const body=JSON.parse(init.body||'{}');
      if(body.username!=='owner-smoke'||body.password!=='owner-password-111') return response(401,{detail:'invalid_credentials'});
      loggedIn=true;return response(200,{authenticated:true,owner_id:'owner-smoke',role:'owner'});
    }
    if(path==='/api/forms'&&method==='POST'){
      const body=JSON.parse(init.body||'{}');
      record={id, name:body.name, model:body.model, need:body.need, slug:body.slug, ev:body.ev,
        fields:body.fields, settings:body.settings, status:'draft',version:1,response_count:responses.length,
        created_at:'2026-01-01T00:00:00+00:00',updated_at:'2026-01-01T00:00:00+00:00'};
      return response(201,record);
    }
    if(path==='/api/forms/'+id&&method==='PUT'){
      const body=JSON.parse(init.body||'{}');
      record={...record,name:body.name,model:body.model,need:body.need,slug:body.slug,ev:body.ev,
        fields:body.fields,settings:body.settings,status:'draft',version:(record.version||1)+1};
      return response(200,record);
    }
    if(path==='/api/forms/'+id+'/readiness'&&method==='GET'){
      if(!record)return response(404,{detail:'form_not_found'});
      return response(200,{source:'same_server_database',form_id:id,version:record.version||1,status:record.status||'draft',
        publishable:readinessIssues.length===0,issues:readinessIssues});
    }
    if(path==='/api/forms/'+id+'/publish'&&method==='POST'){
      record={...record,status:'published',version:(record.version||1)+1};return response(200,record);
    }
    if(path==='/api/forms/'+id+'/pause'&&method==='POST'){
      record={...record,status:'paused',version:(record.version||1)+1};return response(200,record);
    }
    if(path==='/api/forms'&&method==='GET'){
      const item=record?{...record,response_count:Number(record.response_count??responses.length)}:null;
      return response(200,{items:item?[item]:[],total:item?1:0,limit:100,has_more:false});
    }
    if(path.startsWith('/api/forms/'+id+'/responses?')&&method==='GET'){
      const url=new URL(path,'http://nora.test'),limit=Math.max(1,Number(url.searchParams.get('limit'))||50),offset=Math.max(0,Number(url.searchParams.get('offset'))||0);
      return response(200,{items:responses.slice(offset,offset+limit),total:responses.length,limit,offset});
    }
    if(path==='/api/forms/'+id+'/responses'&&method==='GET')return response(200,{items:responses,total:responses.length,limit:50,offset:0});
    if(path==='/api/forms/'+id&&method==='GET') return record?response(200,record):response(404,{detail:'form_not_found'});
    if(path==='/api/auth/logout'&&method==='POST'){loggedIn=false;return response(200,{authenticated:false})}
    return response(404,{detail:'not_found'});
  };
  return {fetch,calls,get record(){return record},get loggedIn(){return loggedIn}};
}
const externalAnchors=p=>p.all('a[href]').filter(a=>/^(?:https?:|mailto:|tel:|sms:|tg:|whatsapp:|ftp:)/i.test(a.getAttribute('href')||''));

/* ── ۱) خانه: فقط محتوای منتشرشده، مسیر رویداد/فرم و ساعت محلی ── */
{
  console.log('\n── خانه و مسیرهای محتوای منتشرشده ──');
  const store=makeStore();
  store.setItem('nora-admin',JSON.stringify({added:[{
    id:'event-live-1',n:'نشست فرهنگی منتشرشده',kind:'نشست آموزشی',privacy:'public',
    on:'1406/01/15',end:'1406/01/15',time:'16:00',place:'پاریس',sessions:1,cap:24,price:0,
    about:'شرح واقعی برنامهٔ منتشرشده.',tchr:'person-live-1',partnerId:'partner-live-1',partnerName:'نهاد همکار منتشرشده',tags:['گفت‌وگو'],
    sess:[{d:'1406/01/15',t:'16:00',to:'17:00'}]
  },
    {id:'event-draft',n:'پیش‌نویس نباید عمومی شود',status:'draft',privacy:'public'},
    {id:'event-hidden',n:'رویداد پنهان',hidden:true,privacy:'public'},
    {id:'event-private',n:'رویداد خصوصی',privacy:'private'},
    {id:'event-unpublished',n:'رویداد منتشرنشده',pub:false,privacy:'public'}
  ]}));
  store.setItem('nora-forms',JSON.stringify([{
    id:'form-live-1',name:'فرم ثبت‌نام نشست',model:'registration',need:'reg',ev:'event-live-1',
    status:'published',eventVisible:true,fields:[{id:'name',t:'text',l:'نام'}],fin:[]
  }]));
  store.setItem('nora-people',JSON.stringify({list:[
    {id:'person-live-1',n:'مدرس منتشرشده',kind:'teacher',r:'مدرس',bio:'زندگی‌نامهٔ منتشرشده',
      exp:['گفت‌وگو'],where:'پاریس',yrs:'۸ سال'},
    {id:'staff-live-1',n:'دست‌اندرکار منتشرشده',kind:'staff',r:'هماهنگ‌کننده',bio:'شرح نقش دست‌اندرکار',exp:['هماهنگی']}
  ]}));
  store.setItem('nora-partners',JSON.stringify({list:[{
    id:'partner-live-1',n:'نهاد همکار منتشرشده',type:'نهاد فرهنگی',s:'همراه برنامه‌های آموزشی',
    collab:'برگزاری کارگاه',since:'مهر ۱۴۰۵',focus:['آموزش','کارگاه'],d:'شرح همکاری',
    href:'https://partner.example.org',links:[
      {k:'mail',v:'hello@partner.example.org'},
      {k:'other',v:'javascript:alert(1)'}
    ],status:'published'
  }]}));
  const serverContent={events:[
    {id:'event-live-1',t:'نشست فرهنگی منتشرشده',kind:'نشست آموزشی',privacy:'public',past:false,
      when:'۱۵ فروردین ۱۴۰۶',time:'16:00',place:'پاریس',price:0,cap:24,d:'شرح واقعی برنامهٔ منتشرشده.',
      tchr:'person-live-1',partnerId:'partner-live-1',partnerName:'نهاد همکار منتشرشده',tags:['گفت‌وگو'],
      parts:[{title:'گفت‌وگو',date:'۱۴۰۶/۰۱/۱۵',time:'16:00',to:'17:00'}],
      forms:[{id:'form-live-1',need:'reg',n:'فرم ثبت‌نام نشست'}]},
    {id:'event-draft',t:'پیش‌نویس نباید عمومی شود',status:'draft',privacy:'public'},
    {id:'event-hidden',t:'رویداد پنهان',hidden:true,privacy:'public'},
    {id:'event-private',t:'رویداد خصوصی',privacy:'private'},
    {id:'event-unpublished',t:'رویداد منتشرنشده',pub:false,privacy:'public'}
  ],people:[
    {id:'person-live-1',n:'مدرس منتشرشده',kind:'teacher',r:'مدرس',bio:'زندگی‌نامهٔ منتشرشده',exp:['گفت‌وگو'],where:'پاریس',yrs:'۸ سال'},
    {id:'staff-live-1',n:'دست‌اندرکار منتشرشده',kind:'staff',r:'هماهنگ‌کننده',bio:'شرح نقش دست‌اندرکار',exp:['هماهنگی']}
  ],partners:[{
    id:'partner-live-1',n:'نهاد همکار منتشرشده',type:'نهاد فرهنگی',s:'همراه برنامه‌های آموزشی',
    collab:'برگزاری کارگاه',since:'مهر ۱۴۰۵',focus:['آموزش','کارگاه'],d:'شرح همکاری',
    href:'https://partner.example.org',links:[{k:'mail',v:'hello@partner.example.org'},{k:'other',v:'javascript:alert(1)'}]
  }],articles:[],banners:[
    {id:'banner-live-1',status:'published',active:true,order:1,t:'برنامهٔ <b>این هفته</b>',tag:'رویداد',
      subtitle:'ثبت‌نام برنامه',s:'جزئیات زمان و مکان را بخوانید.',
      img:'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p7sAAAAASUVORK5CYII=',
      imgAlt:'تصویر برنامه',href:'events.html?status=upcoming',primaryLabel:'برنامه‌های پیش‌رو',
      secondaryHref:'javascript:alert(1)',secondaryLabel:'پیوند ناامن',theme:'teal',layout:'split',align:'center',
      overlay:68,focusX:28,focusY:74,startsAt:'2026-01-01T00:00:00Z',endsAt:'2027-01-01T00:00:00Z'},
    {id:'banner-draft',status:'draft',t:'پیش‌نویس خصوصی'},
    {id:'banner-inactive',status:'published',active:false,t:'بنر خاموش'},
    {id:'banner-future',status:'published',active:true,startsAt:new Date(Date.now()+60_000).toISOString(),t:'بنر زمان‌بندی‌شده'}
  ],banner_settings:{enabled:true,auto_rotate:false,interval_seconds:7,show_controls:true},library:[],cooperation:[]};
  const serverFetch=async path=>path==='/api/public/site-content'
    ?{ok:true,json:async()=>({content:serverContent})}:{ok:false,status:404,json:async()=>({})};
  const p=await load('home.html',store,'',serverFetch);
  ok(p.errors.length===0,'خانه بی‌خطا بار شد'+(p.errors.length?': '+p.errors[0]:''));
  const liveBanner=p.doc.querySelector('#bsdeck .bs');
  ok(p.window.NORA_PUBLIC.banners.length===1&&liveBanner&&!p.doc.querySelector('#bsdeck').textContent.includes('پیش‌نویس خصوصی')
      &&!p.doc.querySelector('#bsdeck').textContent.includes('بنر خاموش')&&!p.doc.querySelector('#bsdeck').textContent.includes('بنر زمان‌بندی‌شده'),
    'خانه فقط بنر منتشرشده، فعال و زمان‌بندی‌شدهٔ سرور را می‌سازد');
  ok(liveBanner.classList.contains('layout-split')&&liveBanner.classList.contains('align-center')
      &&liveBanner.querySelector('.bs-media img')?.getAttribute('alt')==='تصویر برنامه'
      &&liveBanner.querySelector('h2').textContent==='برنامهٔ <b>این هفته</b>',
    'چیدمان، متن امن و تصویر بنر سروری در خانه نمایش داده می‌شوند');
  ok(liveBanner.querySelector('.bacts a[href="events.html?status=upcoming"]')?.textContent==='برنامه‌های پیش‌رو'
      &&!liveBanner.textContent.includes('پیوند ناامن')
      &&liveBanner.style.getPropertyValue('--bnr-overlay')==='0.68',
    'CTA امن، حذف پیوند ناامن و شدت لایهٔ بنر درست اعمال می‌شود');
  ok(p.doc.querySelector('#bnr').hidden===false&&p.doc.querySelector('#bdots').hidden,
    'بنر سروری دیده می‌شود و کنترل‌های چرخش تک‌بنری پنهان‌اند');
  ok(p.doc.querySelector('#evTop').textContent.includes('نشست فرهنگی منتشرشده')
      && !p.doc.querySelector('#evTop').textContent.includes('نمونه'),'خانهٔ قابل‌مشاهده فقط محتوای رویداد منتشرشده را نشان می‌دهد');
  ok(p.all('#evTop .evcard').length===1&&p.window.NORA_PUBLIC.events.length===1,
    'فقط رویداد منتشرشده نمایش داده شد؛ پیش‌نویس و مورد پنهان/خصوصی کنار گذاشته شدند');
  ok(p.doc.querySelector('#evTop .evc-cta[href="event.html?id=event-live-1"]')?.textContent.includes('جزئیات')
      &&!p.doc.querySelector('#evTop .evc-cta[href*="form.html"]'),
    'CTA خانه ابتدا جزئیات رویداد را باز می‌کند و از کارت مستقیم وارد ثبت‌نام نمی‌شود');
  ok(p.doc.querySelector('#evTop .evc-cov[data-ev="event-live-1"]')!==null,
    'کارت جزئیات رویداد به شناسهٔ همان رویداد وصل است');
  ok(p.doc.querySelector('#evTop .mi-partner[data-partner="partner-live-1"]')?.textContent.includes('نهاد همکار منتشرشده'),
    'کارت عمومی رویداد، نهاد همکارِ متصل به همان شناسه را نمایش می‌دهد');
  ok(p.window.NORA_UI.clockState()==='local','ساعت محلی بدون نیاز به سرویس بیرونی کار می‌کند');
  ok(p.network.length===1&&p.network[0]==='/api/public/site-content','خانه فقط snapshot عمومیِ هم‌مبدأ را درخواست کرد');
  const external=p.window.document.createElement('a'); external.href='https://example.org/cta'; external.textContent='دکمهٔ بیرونی';
  p.doc.body.appendChild(external); await wait(40);
  ok(!external.hasAttribute('href')&&external.getAttribute('aria-disabled')==='true'&&external.classList.contains('local-disabled-link'),
    'نگهبان مشترک، پیوند بیرونیِ ساخته‌شدهٔ پویا را هم بی‌عمل می‌کند');
  const otpLoginStep=p.doc.createElement('div'); otpLoginStep.className='loginpage';
  otpLoginStep.innerHTML='<div id="lgPhoneCodeMethod"><a class="bale-otp-link" href="https://ble.ir/verification_code_bot?start=login" target="_blank" rel="noopener noreferrer">ورود به ربات بله</a></div>';
  p.doc.body.appendChild(otpLoginStep); await wait(40);
  const baleOtpLink=otpLoginStep.querySelector('.bale-otp-link');
  ok(!baleOtpLink?.hasAttribute('href')&&baleOtpLink?.getAttribute('aria-disabled')==='true'
      &&baleOtpLink.classList.contains('local-disabled-link'),
    'نگهبان پیش‌نمایش، پیوند ورود به ربات بله را در تجربهٔ وبِ پیامکی غیرفعال می‌کند');
  ok(p.window.NORA_UI.copyText('https://example.org/cta')===false,'رونوشت URL بیرونی هم مسدود است');
  ok(await p.window.NORA_UI.shareItem({url:'https://example.org'})===false,'اشتراک بیرونی بی‌اثر است');
  ok(!p.doc.querySelector('#about,#cooperationForm,#cooperation-form'),'بخش درباره و همکاری از خانه حذف شده است');
  ok(p.doc.querySelector('#peopleRail a[href="person.html?id=person-live-1"]')!==null,
    'کارت مدرس منتشرشده به پروفایل اختصاصی او می‌رود');
  ok(p.doc.querySelector('#staffList a[href="person.html?id=staff-live-1"]')!==null,
    'کارت دست‌اندرکار منتشرشده به پروفایل اختصاصی او می‌رود');
  ok(!p.doc.querySelector('#partners').hidden&&p.doc.querySelector('#logoWall [data-partner="partner-live-1"]'),
    'نهاد همکار منتشرشده از snapshot عمومی در خانه نمایش داده شد');
  p.click('[data-menu]');
  const fullMenuRows=p.window.NORA.MENU.reduce((count,group)=>count+(group.rows||[]).length,0);
  ok(p.window.NORA.MENU.length===5&&fullMenuRows===19&&p.all('#shMenu .mgroup').length===5
      &&p.all('#shMenu .mrow').length===19,'منوی کامل پنج‌گروهی، بدون ردیف‌های اتصالِ حذف‌شده، حفظ شده است');
  ok(p.all('#shMenu .mrow').every(row=>!row.textContent.includes('نشست')),
    'برچسب‌های ناوبری عمومی برای برنامه‌های منتشرشده از اصطلاح مبهم «نشست» استفاده نمی‌کنند');
  ok(p.all('#quick .tile').length===5&&!p.all('#quick a[href*="cooperation"]').length
      &&p.all('#quick a[href="support.html"]').length===1,
    'پنج میان‌بر جامع‌اند و پیوند همکاری فقط در بخش پشتیبانی است، نه خانه');
  const partialQuick=await load('home.html',makeStore({'nora-uiset':JSON.stringify({v:1,quick:['events']})}));
  ok(partialQuick.all('#quick .tile').some(tile=>tile.textContent.includes('رویدادها و آرشیو')),
    'دستهٔ میان‌بر ترکیبی با پنهان‌کردن فقط یکی از دو کلیدش همچنان می‌ماند');
  const hiddenQuick=await load('home.html',makeStore({'nora-uiset':JSON.stringify({v:1,quick:['events','past']})}));
  ok(!hiddenQuick.all('#quick .tile').some(tile=>tile.textContent.includes('رویدادها و آرشیو'))
      &&hiddenQuick.all('#quick .tile').length===4,
    'دستهٔ میان‌بر ترکیبی فقط وقتی هر دو کلید پنهان‌اند برداشته می‌شود');
  const homeNav=p.all('#tabs a').map(link=>link.getAttribute('href'));
  ok(homeNav.length===3&&homeNav[0]==='home.html'&&homeNav[1]==='events.html#list'
      &&homeNav[2]==='account.html'
      &&p.doc.querySelector('#tabs [data-account-nav-label]')?.textContent==='ورود/ثبت‌نام'
      &&p.all('#shMenu .mrow').some(row=>row.dataset.uihref==='account.html#profile'
        &&row.textContent.includes('ورود/ثبت‌نام')),
    'دکمهٔ حساب در تب و منوی مهمان ابتدا نمای حساب را باز می‌کند و ورود سروری در آن باقی است');
  const signed=await load('home.html',makeStore({'nora-home-user':JSON.stringify({name:'سارا محمدی'})}));
  ok(signed.doc.querySelector('#tabs [data-account-nav-label]')?.textContent==='سارا',
    'پس از ورود، برچسب حساب در تب‌بار با نام کوچک جایگزین می‌شود');
  signed.click('[data-menu]');
  ok(signed.all('#shMenu .mrow').some(row=>row.dataset.uihref==='account.html'
      &&row.textContent.includes('سارا'))
      &&signed.all('#shMenu .mrow').some(row=>row.dataset.uihref==='account.html#profile'
        &&row.textContent.includes('سارا')),
    'پس از ورود، برچسب ردیف‌های حساب و پروفایل در منوی کامل نام کوچک کاربر است');
  const homeSectionSettings=p.window.NORA_UI.UISET_META.home.map(([key])=>key);
  ok(homeSectionSettings.includes('bnr')&&homeSectionSettings.includes('stories')
      &&homeSectionSettings.includes('quick')&&homeSectionSettings.includes('events'),
    'تنظیمات نمایش بنر، استوری و بخش‌های خانه در پنل باقی مانده‌اند');
  ok(p.all('#shMenu .mrow').every(row=>!row.textContent.includes('نمونه')&&!row.textContent.includes('پیش‌نمایش')),
    'عنوان‌ها و توضیح‌های منوی کامل محتوای ساختگی را نشان نمی‌دهند');
  ok(p.all('#shMenu .mrow').some(row=>row.dataset.uijump==='partners')
      &&p.all('#shMenu .mrow').some(row=>row.dataset.uihref==='account.html')
      &&p.all('#shMenu .mrow').every(row=>!/#about|cooperation-form/.test(row.dataset.uihref||'')),
    'منوی مهمان بخش‌های عمومی را نگه می‌دارد و ورود/ثبت‌نام را به نمای حساب مهمان می‌برد');
  ok(p.all('#shMenu .mrow[data-uijump]').every(row=>{
    const section=p.doc.getElementById(row.dataset.uijump); return !!section&&!section.hidden;
  }), 'هیچ ردیف منو به بخش پنهان یا خالی هدایت نمی‌شود');
  ok(p.doc.querySelector('#logoWall a.logo[href="partner.html?id=partner-live-1"]')!==null
      &&p.doc.querySelector('#footLogos a[href="partner.html?id=partner-live-1"]')!==null
      &&p.doc.querySelector('#evTop a.mi-partner[href="partner.html?id=partner-live-1"]')!==null
      &&!p.doc.querySelector('#shPartner')&&!p.doc.querySelector('#logoWall button'),
    'کارت نهاد در خانه، نشان پایین صفحه و برچسب نهاد روی کارت رویداد همگی پیوند واقعی به صفحهٔ اختصاصی همان نهادند؛ ورقهٔ قدیمی حذف شده');
  const partnerPage=await load('partner.html',store,'?id=partner-live-1',serverFetch,{fixtureMode:false});
  ok(partnerPage.errors.length===0&&partnerPage.window.NORA_PUBLIC_SOURCE==='server'
      &&partnerPage.doc.querySelector('.partner-profile h1')?.textContent==='نهاد همکار منتشرشده'
      &&partnerPage.all('h1').length===1&&partnerPage.window.document.title.includes('نهاد همکار منتشرشده'),
    'صفحهٔ اختصاصی نهاد از snapshot عمومی سرور همان شناسه را می‌خواند و یک h1 معنادار دارد');
  ok(/نهاد فرهنگی/.test(partnerPage.txt('.partner-heading'))&&/همراه برنامه‌های آموزشی/.test(partnerPage.txt('.partner-lead'))
      &&/برگزاری کارگاه/.test(partnerPage.txt('.partner-facts'))&&/مهر ۱۴۰۵/.test(partnerPage.txt('.partner-facts'))
      &&partnerPage.all('.partner-tags .tag').map(tag=>tag.textContent).join()==='آموزش,کارگاه'
      &&/شرح همکاری/.test(partnerPage.txt('.partner-desc')),
    'نوع، معرفی کوتاه، نوع و زمان همکاری، حوزه‌ها و شرح کامل نهاد نمایش داده می‌شوند');
  const siteLink=partnerPage.doc.querySelector('[data-partner-site]'), mailLink=partnerPage.doc.querySelector('[data-partner-contact="mail"]');
  ok(siteLink&&mailLink&&(siteLink.getAttribute('aria-disabled')==='true'||(siteLink.getAttribute('href')==='https://partner.example.org/'
      &&siteLink.getAttribute('rel')==='noopener noreferrer'&&siteLink.getAttribute('target')==='_blank')),
    'وبگاه رسمی و رایانامهٔ نهاد ساخته می‌شوند و پیوند بیرونی یا با noopener است یا زیر نگهبان پیوند بیرونی پیش‌نمایش محلی');
  ok(!partnerPage.doc.querySelector('a[href^="javascript:"]')&&!partnerPage.doc.querySelector('[data-partner-contact="other"]'),
    'نشانی ناامن راه تماس در صفحهٔ نهاد به پیوند اجرایی تبدیل نمی‌شود');
  ok(partnerPage.doc.querySelector('a.partner-event[href="event.html?id=event-live-1"]')!==null
      &&partnerPage.all('a.partner-event').length===1,
    'فقط رویدادی که در داده صریحاً partnerId همین نهاد را دارد به‌عنوان رویداد مرتبط فهرست می‌شود');
  ok(partnerPage.doc.querySelector('.partner-breadcrumb a[href="home.html#partners"]')!==null
      &&partnerPage.doc.querySelector('.partner-footer-nav a[href="home.html#partners"]')!==null
      &&partnerPage.doc.querySelector('.topbar a[href="home.html#partners"]')!==null,
    'مسیر بازگشت به خانه و بخش نهادهای همکار در بالای صفحه، مسیر صفحه و پایین مقاله وجود دارد');
  const xssPartnerContent={...serverContent,partners:[{id:'partner-xss',n:'<img src=x onerror=alert(1)>',type:'<b>نوع</b>',
    d:'<script>alert(1)</script>',logo:'javascript:alert(1)',href:'javascript:alert(1)',g:'url(javascript:alert(1))',
    links:[{k:'web',v:'javascript:alert(1)'},{k:'mail',v:'<svg onload=alert(1)>@x.y'}]}]};
  const xssPage=await load('partner.html',makeStore({}),'?id=partner-xss',async path=>path==='/api/public/site-content'
    ?{ok:true,json:async()=>({content:xssPartnerContent})}:{ok:false,status:404,json:async()=>({})},{fixtureMode:false});
  ok(xssPage.errors.length===0&&xssPage.doc.querySelector('.partner-profile h1')?.textContent==='<img src=x onerror=alert(1)>'
      &&!xssPage.doc.querySelector('.partner-profile img')&&!xssPage.doc.querySelector('.partner-profile script')
      &&!xssPage.doc.querySelector('[data-partner-site]')&&xssPage.all('.partner-contact').length===0
      &&xssPage.doc.querySelector('.partner-logo').getAttribute('style')==='--g:linear-gradient(135deg,#2E6B7A,#0B2447)'
      &&xssPage.txt('.partner-logo')==='<i',
    'نام/شرح/لوگو/پیوند مخرب نهاد فقط به‌صورت متن امن نمایش داده می‌شود؛ هیچ تصویر، اسکریپت یا پیوند اجرایی ساخته نمی‌شود');
  const missingPartner=await load('partner.html',store,'?id=partner-does-not-exist',serverFetch,{fixtureMode:false});
  ok(missingPartner.errors.length===0&&missingPartner.doc.querySelector('.partner-not-found[role="status"] h1')?.textContent==='این نهاد همکار در دسترس نیست'
      &&missingPartner.doc.querySelector('.partner-not-found a[href="home.html#partners"]')!==null,
    'شناسهٔ ناموجود در صفحهٔ نهاد، وضعیت «در دسترس نیست» با مسیر بازگشت نشان می‌دهد');
  const offlinePartner=await load('partner.html',makeStore({}),'?id=partner-live-1','',{fixtureMode:false});
  ok(offlinePartner.errors.length===0&&offlinePartner.window.NORA_PUBLIC_SOURCE==='unavailable'
      &&offlinePartner.doc.querySelector('.partner-not-found h1')?.textContent==='محتوای زنده در دسترس نیست',
    'خطای API در صفحهٔ نهاد پیام انسانی متفاوت از «پیدا نشد» می‌دهد و خطای JavaScript ندارد');
  const eventDetail=await load('event.html',store,'?id=event-live-1',serverFetch,{fixtureMode:false});
  ok(eventDetail.errors.length===0&&eventDetail.doc.querySelector('.event-detail'),'صفحهٔ اختصاصی رویداد منتشرشده سالم رندر شد');
  const eventLayout=eventDetail.doc.querySelector('.event-layout'),eventChildren=[...eventLayout.children],
    eventStyles=[...eventDetail.doc.querySelectorAll('style')].map(style=>style.textContent).join('\n');
  ok(eventDetail.txt('#page').includes('شرح واقعی برنامهٔ منتشرشده.')
      && eventDetail.doc.querySelector('#reg')?.getAttribute('href')==='form.html?fid=form-live-1&kind=reg'
      &&eventChildren.findIndex(node=>node.classList.contains('event-detail'))<eventChildren.findIndex(node=>node.classList.contains('event-register'))
      &&!/\.event-register\{[^}]*order\s*:\s*-1/i.test(eventStyles)
      &&eventStyles.includes('#ctabar{display:none!important}'),
    'جزئیات کامل پیش از پنل ثبت‌نام دیده می‌شوند و ثبت‌نام همان رویداد پس از آن در دسترس است');
  ok(eventDetail.doc.querySelector('a.event-partner-link[href="partner.html?id=partner-live-1"]')?.textContent.includes('نهاد همکار منتشرشده'),
    'صفحهٔ عمومی رویداد، پیوند نهاد همکار را به صفحهٔ اختصاصی همان نهاد می‌رساند');
  const certContent={...serverContent,events:[{id:'event-cert-live',t:'رویداد آرشیوی دارای گواهی',
    kind:'کارگاه',privacy:'public',past:true,cert:true,certMin:85,certNote:'حضور در جلسهٔ پایانی',media:[]}]};
  const certFetch=async path=>path==='/api/public/site-content'
    ?{ok:true,json:async()=>({content:certContent})}:{ok:false,status:404,json:async()=>({})};
  const certEvent=await load('event.html',store,'?id=event-cert-live',certFetch,{fixtureMode:false});
  const certCopy=certEvent.doc.querySelector('[data-cert-requirement]')?.textContent||'';
  ok(certCopy.includes('حداقل حضور برای درخواست گواهی ٪۸۵')
      &&certCopy.includes('از اطلاعات منتشرشدهٔ سرور')
      &&!certCopy.includes('نمایشی'),
    'شرط گواهی در رویداد واقعی با منبع سروری توصیف می‌شود، نه دادهٔ نمایشی');
  const editedPublicStore=makeStore({
    'nora-admin':JSON.stringify({added:[{id:'event-edit-public',n:'رویداد ویرایش‌شده',kind:'نشست',privacy:'public',
      on:'1406/01/15',end:'1406/01/15',time:'16:00',place:'پاریس',sessions:1,cap:20,partnerId:'',partnerName:''}],
      evEdit:{'event-edit-public':{partnerId:'partner-live-1',partnerName:'نهاد همکار منتشرشده'}}}),
    'nora-partners':store.getItem('nora-partners')
  });
  const localOnly=await load('event.html',editedPublicStore,'?id=event-edit-public',null,{fixtureMode:false});
  ok(!localOnly.doc.querySelector('.event-detail')&&/در دسترس نیست/.test(localOnly.doc.body.textContent),
    'رویداد صرفاً محلی در مسیر تولیدی جزئیات عمومی نمی‌سازد');
  const updatedContent={...serverContent,events:[...serverContent.events,{
    id:'event-edit-public',t:'رویداد ویرایش‌شده',kind:'نشست',privacy:'public',when:'۱۵ فروردین ۱۴۰۶',
    time:'16:00',place:'پاریس',d:'شرح سروری رویداد ویرایش‌شده.',partnerId:'partner-live-1',
    partnerName:'نهاد همکار منتشرشده',parts:[],forms:[]
  }]};
  const updatedFetch=async path=>path==='/api/public/site-content'
    ?{ok:true,json:async()=>({content:updatedContent})}:{ok:false,status:404,json:async()=>({})};
  const editedPublic=await load('event.html',editedPublicStore,'?id=event-edit-public',updatedFetch,{fixtureMode:false});
  ok(editedPublic.doc.querySelector('a.event-partner-link[href="partner.html?id=partner-live-1"]')!==null,
    'صفحهٔ عمومی تغییر نهاد را از snapshot سروریِ منتشرشده می‌خواند');
  const teacherProfile=await load('person.html',store,'?id=person-live-1',serverFetch,{fixtureMode:false});
  ok(teacherProfile.errors.length===0&&teacherProfile.doc.querySelector('.person-profile')
      &&teacherProfile.txt('.person-profile').includes('زندگی‌نامهٔ منتشرشده'),
    'پروفایل مدرس جزئیات منتشرشده را منظم نمایش می‌دهد');
  ok(teacherProfile.doc.querySelector('.person-event[href="event.html?id=event-live-1"]')!==null
      &&!teacherProfile.doc.querySelector('.person-actions a[href*="cooperation"]'),
    'پروفایل مدرس رویداد مرتبط دارد و به بخش حذف‌شده پیوند نمی‌دهد');
  const staffProfile=await load('person.html',store,'?id=staff-live-1',serverFetch,{fixtureMode:false});
  ok(staffProfile.errors.length===0&&staffProfile.doc.querySelector('.person-profile')
      &&staffProfile.txt('.person-profile').includes('دست‌اندرکار')
      &&staffProfile.txt('.person-profile').includes('شرح نقش دست‌اندرکار'),
    'پروفایل دست‌اندرکار با نقش و شرح منتشرشده نمایش داده می‌شود');
  const emptyHome=await load('home.html',makeStore({
    'nora-uiset':JSON.stringify({v:1,home:{bnr:1},bnr:{on:1},bnrAdd:[{t:'بنر محلی ساختگی',m:'نباید نمایش داده شود'}]}),
    'nora-public-banners':JSON.stringify([{id:'stale-local-banner',status:'published',t:'بنر محلی قدیمی'}])
  }),'','',{fixtureMode:false});
  emptyHome.click('[data-menu]');
  ok(emptyHome.doc.querySelector('#bnr').hidden&&!emptyHome.doc.querySelector('#bsdeck').textContent.includes('بنر محلی')
      &&emptyHome.window.NORA_PUBLIC.banners.length===0,
    'در نبود API سرور، بنرهای محلی و قدیمی در تجربهٔ تولیدی نمایش داده نمی‌شوند');
  ok(emptyHome.all('#shMenu .mrow').every(row=>{
    const target=row.dataset.uijump&&emptyHome.doc.getElementById(row.dataset.uijump);
    return !row.dataset.uijump||(!!target&&!target.hidden);
  }), 'در نبود محتوای منتشرشده، منو پیوندی به بخش پنهان نمی‌سازد');
  ok(!emptyHome.txt('#shMenu').includes('· نمونه')&&!emptyHome.txt('#shMenu').includes('پیش‌نمایش'),
    'منوی عمومی عنوان یا دادهٔ نمونه نشان نمی‌دهد');
  const noBannerContent={...serverContent,banners:[]};
  const introHome=await load('home.html',makeStore({
    'nora-uiset':JSON.stringify({v:1,home:{bnr:0},bnr:{on:0},bnrAdd:[{t:'بنر محلی ساختگی'}]})
  }),'',async path=>path==='/api/public/site-content'
    ?{ok:true,json:async()=>({content:noBannerContent})}:{ok:false,status:404,json:async()=>({})},{fixtureMode:false});
  const introSlide=introHome.doc.querySelector('#bsdeck .bs');
  ok(introHome.errors.length===0&&introHome.window.NORA_PUBLIC_SOURCE==='server'&&introHome.doc.querySelector('#bnr').hidden===false
      &&introHome.doc.querySelector('#bnr').classList.contains('is-intro')&&introSlide?.classList.contains('bs-intro')
      &&introHome.all('#bsdeck .bs').length===1&&introHome.doc.querySelector('#bdots').hidden&&introHome.doc.querySelector('#bnr .bnav').hidden,
    'وقتی سرور بنر منتشرشده ندارد، بنر معرفی نورا (تک‌اسلاید، بدون کنترل چرخش) دیده می‌شود');
  ok(!introHome.txt('#bsdeck').includes('بنر محلی')&&!/\d/.test(introHome.txt('#bsdeck').replace(/[۰-۹]/g,'0').replace(/0/g,''))
      &&JSON.stringify(introHome.all('#bsdeck .bacts a').map(a=>a.getAttribute('href')))===JSON.stringify(['events.html','home.html#articles'])
      &&introSlide.querySelector('.bs-media img')?.getAttribute('src')==='home-banner.webp',
    'بنر معرفی فقط به مسیرهای واقعی نورا پیوند می‌دهد و از تنظیم محلی مرورگر یا دادهٔ ساختگی تأثیر نمی‌گیرد');
  const disabledContent={...noBannerContent,banner_settings:{...serverContent.banner_settings,enabled:false}};
  const disabledHome=await load('home.html',makeStore({}),'',async path=>path==='/api/public/site-content'
    ?{ok:true,json:async()=>({content:disabledContent})}:{ok:false,status:404,json:async()=>({})},{fixtureMode:false});
  ok(disabledHome.errors.length===0&&disabledHome.doc.querySelector('#bnr').hidden&&disabledHome.all('#bsdeck .bs').length===0,
    'خاموش‌کردن بنر از تنظیمات مالک، بنر معرفی را هم پنهان می‌کند');
  const kindContent={...serverContent,banners:[
    {id:'banner-ad',status:'published',active:true,order:0,t:'بنر حامی‌شده',kind:'sponsored',theme:'amber'},
    {id:'banner-partner',status:'published',active:true,order:1,t:'بنر نهاد همکار',kind:'partner'},
    {id:'banner-plain',status:'published',active:true,order:2,t:'اطلاعیهٔ ساده',kind:'javascript:x'}]};
  const kindHome=await load('home.html',makeStore({}),'',async path=>path==='/api/public/site-content'
    ?{ok:true,json:async()=>({content:kindContent})}:{ok:false,status:404,json:async()=>({})},{fixtureMode:false});
  ok(kindHome.errors.length===0&&!kindHome.doc.querySelector('#bnr').classList.contains('is-intro')
      &&JSON.stringify(kindHome.all('#bsdeck .bs').map(slide=>[slide.classList.contains('bs-sponsored')||slide.classList.contains('bs-partner'),
        slide.querySelector('.btag-kind')?.textContent||'']))===JSON.stringify([[true,'تبلیغ'],[true,'حامی'],[false,'']])
      &&!kindHome.doc.querySelector('#bdots').hidden,
    'نوع بنر (تبلیغ/حامی) با برچسب شفاف نمایش داده می‌شود و نوع نامعتبر برچسبی نمی‌سازد');
  const unpublishedHome=await load('home.html',makeStore({}),'',async()=>({ok:false,status:404,json:async()=>({detail:'site_content_not_published'})}),{fixtureMode:false});
  ok(unpublishedHome.errors.length===0&&unpublishedHome.window.NORA_PUBLIC_SOURCE==='empty'
      &&unpublishedHome.doc.querySelector('#bnr').hidden===false&&unpublishedHome.doc.querySelector('#bnr').classList.contains('is-intro')
      &&unpublishedHome.doc.querySelector('#publicContentStatus').hidden===false
      &&unpublishedHome.txt('#publicContentStatus').includes('هنوز محتوای عمومی منتشر نشده'),
    'سرور سالم ولی بدون محتوای منتشرشده: وضعیت «خالی» با بنر معرفی و کارت توضیح نمایش داده می‌شود');
  const preserved=await load('home.html',makeStore({'nora-uiset':JSON.stringify({v:1,home:{about:0,events:0}})}));
  ok(preserved.window.NORA_UI.uiSet().home.about===0&&preserved.window.NORA_UI.uiSet().home.events===0
      &&!preserved.doc.getElementById('about')&&preserved.doc.querySelector('#evSec').hidden,
    'تنظیم‌های ذخیره‌شده حفظ می‌شوند و بخش حذف‌شده در خانه ساخته نمی‌شود');

  /* ── فاز ۷: خانه با وضعیت ثبت‌نام سرور، گروه‌بندی، شمارشگر مشترک و بنر وصل به رویداد ── */
  {
    const serverNow=new Date('2026-11-01T10:00:00Z');
    const iso=h=>new Date(serverNow.getTime()+h*3600_000).toISOString();
    const content={events:[
      {id:'p7-open',t:'کارگاه با ثبت‌نام باز',kind:'کارگاه',privacy:'public',when:'۱۲ آبان',on:'۱۴۰۵/۰۸/۱۲',d:'شرح',price:0,forms:[{id:'f-open',need:'reg',n:'ثبت‌نام'}],
        startsAt:iso(48),regClosesAt:iso(26.5),registration:{state:'open',reason:'',lifecycle:'scheduled',closesAt:iso(26.5),countdownTo:iso(26.5),startsAt:iso(48),startsIn:iso(48)}},
      {id:'p7-wait',t:'نشست با ثبت‌نام آینده',kind:'نشست',privacy:'public',when:'۲۰ آبان',on:'۱۴۰۵/۰۸/۲۰',d:'شرح',price:0,forms:[{id:'f-wait',need:'reg',n:'ثبت‌نام'}],
        startsAt:iso(240),regOpensAt:iso(72),registration:{state:'not_started',reason:'time',lifecycle:'scheduled',opensAt:iso(72),countdownTo:iso(72),startsAt:iso(240),startsIn:iso(240)}},
      {id:'p7-full',t:'اردوی پر',kind:'اردو',privacy:'public',when:'۲۵ آبان',on:'۱۴۰۵/۰۸/۲۵',d:'شرح',price:0,forms:[{id:'f-full',need:'reg',n:'ثبت‌نام'}],
        startsAt:iso(400),registration:{state:'full',reason:'capacity',lifecycle:'scheduled',countdownTo:'',startsAt:iso(400),startsIn:iso(400)}},
      {id:'p7-cancel',t:'جلسهٔ لغوشده',kind:'نشست',privacy:'public',when:'۲۸ آبان',on:'۱۴۰۵/۰۸/۲۸',d:'شرح',price:0,lifecycle:'cancelled',
        startsAt:iso(500),registration:{state:'cancelled',reason:'cancelled',lifecycle:'cancelled',countdownTo:''}},
      {id:'p7-ended',t:'کارگاه تمام‌شده',kind:'کارگاه',privacy:'public',when:'۱ مهر',on:'۱۴۰۵/۰۷/۰۱',d:'شرح',price:0,
        registration:{state:'ended',reason:'time',lifecycle:'scheduled',countdownTo:''}}
    ],people:[],partners:[],articles:[],library:[],cooperation:[],banners:[
      {id:'p7-banner-event',status:'published',active:true,order:1,t:'بنر رویداد',eventId:'p7-open',countdown:'reg_close',countdownTo:iso(26.5),countdownEnded:false,
        afterEnd:'details',href:'event.html?id=p7-open',primaryLabel:'جزئیات',event:{id:'p7-open',t:'کارگاه با ثبت‌نام باز',when:'۱۲ آبان',startsAt:iso(48),regClosesAt:iso(26.5),state:'open',lifecycle:'scheduled'}},
      {id:'p7-banner-ended',status:'published',active:true,order:2,t:'بنر تمام‌شده',eventId:'p7-full',countdown:'reg_close',countdownTo:'',countdownEnded:true,
        afterEnd:'message',afterEndText:'ظرفیت این دوره تکمیل شد',href:'event.html?id=p7-full',primaryLabel:'جزئیات',event:{id:'p7-full',t:'اردوی پر',when:'۲۵ آبان',state:'full',lifecycle:'scheduled'}},
      {id:'p7-banner-hidden',status:'published',active:true,order:3,t:'بنر پایان‌یافتهٔ پنهان',eventId:'p7-full',countdown:'reg_close',countdownTo:'',countdownEnded:true,afterEnd:'hide'}
    ],banner_settings:{enabled:true,auto_rotate:false,interval_seconds:7,show_controls:true}};
    const fetch7=async path=>path==='/api/public/site-content'
      ?{ok:true,json:async()=>({content,server_time:serverNow.toISOString()})}:{ok:false,status:404,json:async()=>({})};
    const p=await load('home.html',makeStore(),'',fetch7);
    ok(p.errors.length===0,'خانهٔ فاز ۷ بی‌خطا بار شد'+(p.errors.length?': '+p.errors[0]:''));
    ok(p.window.NORA_SERVER_CLOCK&&Math.abs(p.window.NORA_COUNTDOWN.serverNow()-serverNow.getTime())<5000,
      'ساعت مرجع خانه از server_time پاسخ گرفته می‌شود، نه از ساعت مرورگر');
    const card=id=>p.doc.querySelector(`#evSec .evc-cov[data-ev="${id}"]`)?.closest('.evcard');
    const openCard=card('p7-open');
    ok(openCard&&openCard.querySelector('.reg-state.live')?.textContent==='ثبت‌نام باز است'
        &&/تا پایان ثبت‌نام/.test(openCard.querySelector('[data-countdown]')?.textContent||'')
        &&/۱ روز و ۲ ساعت/.test(openCard.querySelector('.nora-countdown-value')?.textContent||''),
      'کارت ثبت‌نام باز: نشان وضعیت و شمارشگر تا مهلت، محاسبه‌شده با ساعت سرور');
    ok(openCard.querySelector('.evc-cta')?.getAttribute('href')==='event.html?id=p7-open'&&/ثبت‌نام و جزئیات/.test(openCard.querySelector('.evc-cta').textContent),
      'دکمهٔ کارت باز به صفحهٔ جزئیات می‌رود، نه مستقیم به فرم');
    ok(card('p7-wait')?.querySelector('.reg-state.wait')&&/تا آغاز ثبت‌نام/.test(card('p7-wait').textContent),
      'کارت ثبت‌نام آغازنشده: نشان انتظار و شمارش تا آغاز ثبت‌نام');
    ok(card('p7-full')?.querySelector('.reg-state.stop')?.textContent==='ظرفیت تکمیل شد'&&/تا شروع رویداد/.test(card('p7-full').textContent)
        &&!/ثبت‌نام و جزئیات/.test(card('p7-full').querySelector('.evc-cta').textContent),
      'کارت ظرفیت تکمیل: نشان توقف، فقط شمارش تا شروع، بدون دعوت به ثبت‌نام');
    ok(card('p7-cancel')?.querySelector('.reg-state.stop')?.textContent==='لغو شد'&&!card('p7-cancel').querySelector('[data-countdown]'),
      'رویداد لغوشده: نشان لغو و هیچ شمارشگری');
    ok(!card('p7-ended')&&p.doc.querySelector('#pastList .evc-cov[data-ev="p7-ended"]'),
      'پایان‌یافته طبق سرور از ویترین خارج و در برگزارشده‌ها است');
    ok(p.all('#evTop .evcard').length===3&&p.all('#evTop .evc-cov')[0].dataset.ev==='p7-open',
      'ویترین: اول ثبت‌نام باز، سپس بقیه؛ حداکثر سه کارت');
    ok(p.doc.querySelector('#evSoonGroup').hidden===false&&p.all('#evSoon .evc-cov').map(e=>e.dataset.ev).join(',')==='p7-cancel'
        &&p.doc.querySelector('#evOpenGroup').hidden===true,
      'گروه «پیش رو» فقط کارت‌های باقی‌مانده به ترتیب تاریخ؛ گروه خالی «ثبت‌نام باز» پنهان است');
    const banners=p.all('#bsdeck .bs');
    ok(banners.length===2&&!p.doc.querySelector('#bsdeck').textContent.includes('بنر پایان‌یافتهٔ پنهان'),
      'بنر پایان‌یافته با رفتار «پنهان» ساخته نمی‌شود');
    ok(/تا پایان ثبت‌نام/.test(banners[0].querySelector('.btimer [data-countdown]')?.textContent||'')&&banners[0].querySelector('.bmeta')?.textContent==='۱۲ آبان',
      'بنر وصل به رویداد: شمارشگر از مهلت خود رویداد و زمان رویداد از رکورد رویداد');
    ok(banners[1].querySelector('.bnote')?.textContent==='ظرفیت این دوره تکمیل شد'&&banners[1].querySelector('.nora-countdown.is-ended')
        &&banners[1].querySelector('.bacts a')?.getAttribute('href')==='event.html?id=p7-full'&&!banners[1].querySelector('a[href*="form.html"]'),
      'بنر پایان‌یافته با رفتار «متن»: متن پایان، نشان پایان‌یافته و دکمه فقط به جزئیات');
    const shares=[]; p.window.shareItem=async item=>{shares.push(item); return true};
    const shareBtn=p.doc.createElement('button'); shareBtn.dataset.share='p7-open'; p.doc.body.appendChild(shareBtn); shareBtn.click(); await wait(20);
    ok(shares.length===1&&shares[0].title==='کارگاه با ثبت‌نام باز'&&!/نمونه/.test(shares[0].title+shares[0].text)&&/event\.html\?id=p7-open$/.test(shares[0].url),
      'اشتراک رویداد از خانه با عنوان و نشانی واقعی، بدون واژهٔ «نمونه»');
    p.window.close();
  }
}

/* ── ۲) فرم: پاسخ محلی، بدون روش پرداخت/رسید/بلیت ── */
{
  console.log('\n── فرم عمومی: ثبت محلی، بدون پرداخت ──');
  const finance={gates:[{k:'card',on:1},{k:'bale',on:1}],rot:'time',rotHours:24,
    cards:[{id:'smoke-card',bank:'بانک نمونه',no:'4111111111111111',name:'دارندهٔ نمونه',cap:5,dailyMax:500000,used:0,usedAmount:0}]};
  const store=makeStore({'nora-finance':JSON.stringify(finance)}), p=await load('form.html',store,'?guests=0');
  ok(p.errors.length===0,'فرم بی‌خطا بار شد');
  {
    const t=p.doc.getElementById('toast'), icon=t&&t.querySelector('svg.i');
    p.window.toast('ذخیره انجام نشد؛ دوباره تلاش کن.','error');
    const errorHidesCheck=!!icon&&icon.style.display==='none'&&t.classList.contains('is-error')&&t.textContent.includes('ذخیره انجام نشد');
    p.window.toast('پاسخت بازیابی شد');
    const successRestoresCheck=icon.style.display===''&&!t.classList.contains('is-error');
    ok(errorHidesCheck&&successRestoresCheck,'توست خطا نشانهٔ ✓ موفقیت را نشان نمی‌دهد و توست بعدی آن را برمی‌گرداند');
  }
  const visibleLandingText=[p.txt('#topTitle'),p.txt('#evTitle'),p.txt('#next'),
    ...['formLead','evMeta','landingCount','footerLocalNotice','formMeta'].map(id=>{const el=p.doc.getElementById(id);return el&&(el.hidden||el.style.display==='none')?'':el?.textContent||''})].join(' ');
  ok(p.doc.querySelector('#prev').hidden&&p.doc.querySelector('#botbar').classList.contains('start-mode')
      &&p.doc.querySelector('#next').textContent.includes('شروع')&&p.doc.querySelector('#landingCount').hidden
      &&p.doc.body.classList.contains('standalone-form-preview')
      &&!p.doc.querySelector('#evTitle').hidden&&p.txt('#evTitle')==='کارگاه فن بیان مقدماتی'
      &&p.doc.querySelector('#localPreviewNotice').style.display!=='none'
      &&p.txt('#localPreviewNotice').includes('پیش‌نمایش محلی')
      &&!/(SAMPLE-|DEMO-|پیش‌نویس|ثبت‌نام در رویداد)/.test(visibleLandingText),
    'صفحهٔ آغاز نام برنامه و برچسب روشنِ پیش‌نمایش را نشان می‌دهد؛ شمارنده و دادهٔ ثبت‌نام ساختگی ندارد');
  const programName='نشست تابستانی محله';
  const namedFormStore=makeStore({
    'nora-admin':JSON.stringify({added:[{id:'event-start-title',n:programName,kind:'کارگاه',privacy:'public',
      on:'1410/07/08',end:'1410/07/08',time:'16:00',place:'آنلاین',sessions:1,cap:25,reg:0}]}),
    'nora-forms':JSON.stringify([{id:'form-start-title',name:'فرم تکمیل مشخصات',need:'reg',ev:'event-start-title',
      status:'published',eventVisible:true,fields:[{id:'q-title',t:'text',l:'نام',req:true}],fin:[]}])
  });
  const namedForm=await load('form.html',namedFormStore,'?ev=event-start-title&kind=reg');
  ok(namedForm.errors.length===0&&!namedForm.doc.querySelector('#evTitle').hidden
      &&namedForm.txt('#evTitle')===programName&&!namedForm.txt('#evTitle').includes('ثبت‌نام'),
    'در فرم متصل به رویداد، فقط نام خود برنامه در عنوان آغاز دیده می‌شود');
  p.click('#next');
  ok(p.visible('.screen').join()==='u2'&&p.doc.querySelector('#prev').hidden
      &&p.doc.querySelector('#botbar').classList.contains('first-step-mode')
      &&p.txt('#stepCap')==='۱ از ۷'&&!p.doc.querySelector('#pos')
      &&p.doc.querySelector('#draftStatus').classList.contains('sr'),
    'سؤال اول قبلی ندارد، فقط یک شمارهٔ مرحله دارد و وضعیت ذخیره از چیدمان دیداری کنار رفته است');
  p.click('#next');
  ok(p.visible('.screen').join()==='u3'&&!p.doc.querySelector('#prev').hidden,
    'از سؤال دوم به بعد، قبلی برای بازگشت به مرحلهٔ پیشین ظاهر می‌شود');
  p.click('#prev');
  ok(p.visible('.screen').join()==='u2'&&p.doc.querySelector('#prev').hidden,
    'بازگشت به سؤال اول، قبلی را دوباره پنهان می‌کند');
  ok(p.doc.querySelector('meta[name="robots"]')?.content.includes('noindex'),'فرم عمومی noindex است');
  ok(p.all('#u8 [data-method]:not([hidden])').length===0
      &&p.window.eval("selectedPaymentMethod==='' ")
      &&p.doc.querySelector('#paymentMethodRequired').hidden===false
      &&p.doc.querySelector('#gatewayPaymentInfo').hidden
      &&p.doc.querySelector('#paymentTransferTotal').hidden
      &&p.doc.querySelector('#serverReceiptUpload').hidden,
    'بدون انتخاب صریح سازنده هیچ روش پرداختی نمایش داده نمی‌شود و روش/مبلغ از پیش انتخاب نمی‌شوند');
  p.window.eval("show('u10')");p.click('[data-fin="0"]');
  ok(p.visible('.screen').join()==='u8'&&p.window.eval("selectedPaymentMethod==='' ")
      &&p.all('#u8 [data-method]:not([hidden])').length===0,
    'مرحلهٔ مقصد بانکیِ غیرفعال به انتخاب فعال برمی‌گردد، بدون ساخت روش پیش‌فرض');
  p.click('#next');
  ok(p.visible('.screen').join()==='u8'&&p.doc.querySelector('#paymentMethodList').getAttribute('aria-invalid')==='true'
      &&p.doc.querySelector('#paymentMethodRequired').hidden===false,
    'فرم هزینه‌دار بدون روش منتخب اجازهٔ ادامه نمی‌دهد');
  p.window.eval("CFG.enabledPaymentMethods=['card_transfer','bale_wallet'];updatePaymentFlow();renderPaymentMethods()");
  ok(p.all('#u8 [data-method]:not([hidden])').length===2
      &&p.doc.querySelector('[data-method="bale_wallet"]').getAttribute('aria-checked')==='false'
      &&p.doc.querySelector('[data-method="card_transfer"]').getAttribute('aria-checked')==='false',
    'پس از فعال‌سازی صریح فقط کارت‌به‌کارت و کیف پول بله دیده می‌شوند و هیچ‌کدام خودکار انتخاب نمی‌شود');
  p.click('[data-method="bale_wallet"]');
  ok(p.window.eval("selectedPaymentMethod==='bale_wallet'")
      &&!p.doc.querySelector('#balePaymentCheckout').hidden
      &&p.txt('#balePaymentMessage').includes('پیش‌نمایش محلی')
      &&p.doc.querySelector('#balePaymentInvoiceLink').hidden
      &&p.network.length===0,
    'کیف پول بله در پیش‌نمایش فقط توضیح می‌دهد و صورتحساب یا پرداخت واقعی نمی‌سازد');
  p.click('#next');
  ok(p.visible('.screen').join()==='u9'&&p.txt('#paymentTitle')==='کیف پول بله'
      &&p.doc.querySelector('#balePaymentInvoiceLink').hidden&&p.network.length===0
      &&p.txt('#next').includes('پیش‌نمایش'),
    'گام بله در همان صفحهٔ پرداخت می‌ماند، اما پیش‌نمایش لینک صورتحساب ندارد');
  p.window.eval("show('u8')");p.click('[data-method="card_transfer"]');
  ok(p.txt('#next').includes('کارت مقصد'),'انتخاب هزینه و کارت‌به‌کارت، مسیر پیش‌نمایش را روشن می‌کند');
  p.click('#next');
  ok(p.visible('.screen').join()==='u9'&&p.txt('#paymentTitle')==='کارت‌به‌کارت'
      &&p.txt('#payAmount').includes('۷۲۲٬۵۰۰')&&p.txt('#payAmount').includes('ریال')
      &&!p.doc.querySelector('#paymentTransferTotal').hidden
      &&p.doc.querySelector('#paymentBankCardWrap').hidden===false
      &&p.txt('#paymentBankCardNumber').includes('••••')
      &&p.doc.querySelector('#paymentBankCardQuickCopy').hidden
      &&p.txt('#next').includes('فیش نمونه'),
    'کارت‌به‌کارت مبلغ کامل را نشان می‌دهد، اما شمارهٔ مقصد و انتقال واقعی در پیش‌نمایش بسته‌اند');
  let copiedAmount='';p.window.NORA_UI.copyText=value=>{copiedAmount=String(value);return true};
  p.click('#paymentAmountCopy');
  ok(copiedAmount==='722500','مبلغ کامل دقیق در پیش‌نمایش قابل کپی است، بدون انتقال وجه');
  p.click('#next');
  ok(p.visible('.screen').join()==='u11'&&!p.doc.querySelector('#serverReceiptUpload').hidden
      &&!p.doc.querySelector('#receiptPreviewStatus').hidden,
    'کارت‌به‌کارت محلی فقط به مرحلهٔ رسید نمونه می‌رود و روشن می‌گوید فایل ارسال نمی‌شود');
  const localReceiptFile=new p.window.File(['sample image'], 'receipt.png', {type:'image/png'});
  const localReceiptInput=p.doc.querySelector('#serverReceiptFile');
  Object.defineProperty(localReceiptInput,'files',{configurable:true,value:[localReceiptFile]});
  p.input('#receiptNote','یادداشت فقط برای پیش‌نمایش');
  localReceiptInput.dispatchEvent(new p.window.Event('change',{bubbles:true}));
  p.click('#next');
  ok(p.visible('.screen').join()==='u12'&&p.txt('#endStatusTitle')==='پیش‌نمایش تموم شد'
      &&p.txt('#endLocalNotice').includes('پیش‌نمایش محلی')&&p.network.length===0
      &&!p.store.getItem('nora-regs')&&!p.store.getItem('nora-receipts')
      &&p.txt('#receiptPreviewStatus').includes('فقط پیش‌نمایش')
      &&!p.store._dump().some(key=>{try{return JSON.stringify(JSON.parse(p.store.getItem(key))).includes('یادداشت فقط برای پیش‌نمایش')}catch(_){return false}}),
    'پیش‌نمایش فیش و یادداشت در پایانِ برچسب‌خورده می‌ماند و نه ثبت، پرداخت یا رسید محلیِ واقعی می‌سازد');
  ok(p.doc.querySelector('#serverTicketPreview').hidden
      &&p.doc.querySelector('#serverTicketLink').hidden
      &&!p.doc.querySelector('#serverTicketImage').getAttribute('src'),
    'تا ثبت سروری، در پیش‌نمایش تصویر، پیوند یا بلیت جعلی نمایش داده نمی‌شود');
  ok(p.window.NORA_UI.finBump('smoke-card',100)===null&&p.window.NORA_UI.finAddReceipt({id:'x'})===false,
    'APIهای مالی حتی با کارت نمونه هیچ تراکنش یا رسیدی نمی‌سازند');
  ok(JSON.parse(store.getItem('nora-finance')).cards[0].used===0&&JSON.parse(store.getItem('nora-receipts')||'[]').length===0,
    'مصرف کارت و انبار رسید بدون تغییر ماند');
  ok(p.network.length===0&&externalAnchors(p).length===0,'فرم درخواست شبکه یا لینک بیرونی ندارد');

}

/* ── ۲ب) فرم منتشرشده: پیش‌نویس و پاسخ فقط از API سروری ── */
{
  console.log('\n── پاسخ‌گیری عمومی سروری ──');
  const id='server-public-smoke',form=makePublicFormData(id),api=makePublicApiMock({id});
  const page=await loadPublicForm(form,api.fetch);
  ok(page.errors.length===0,'فرم منتشرشده با bootstrap سرور بی‌خطا بار شد'+(page.errors.length?': '+page.errors[0]:''));
  ok(page.window.eval('FORM_ROUTE.serverBacked')===true&&page.window.eval('REG.profilePrefill')===false,
    'فرم از مسیر پاسخ سروری رندر شد و پیش‌پرکردن نمایه برای پاسخ عمومی خاموش است');
  ok(api.calls.some(call=>call.path==='/api/public/forms/'+id+'/draft'&&call.method==='GET')
      &&page.doc.querySelector('#next').disabled===false,
    'نشست ناشناس از API بازیابی شد و فرم پس از تکمیل بازیابی قابل‌ادامه شد');
  ok(page.network.every(path=>String(path).startsWith('/api/public/forms/'))
      &&page.store.getItem('nora-regs')===null&&!page.store._dump().some(key=>key.startsWith('nora:draft:')),
    'فرم سروری هیچ پاسخ یا پیش‌نویسی را در انبار محلی نمی‌نویسد');
  page.click('#next');await wait(20);
  ok(page.visible('.screen').join()==='qp0'&&page.txt('#stepCap')==='۱ از ۱'&&!page.doc.querySelector('#qall,#pos'),
    'فرم ثبت‌نام پرسش‌ها را یکی‌یکی و با یک شمارنده در سرصفحه نشان می‌دهد');
  page.input('#qa0','لیلا رضایی');await wait(720);
  const autosave=api.calls.find(call=>call.method==='PATCH');
  ok(autosave?.body?.answers?.['full-name']==='لیلا رضایی','تغییر پاسخ به‌صورت debounceشده به API پیش‌نویس فرستاده شد');
  page.click('#next');await wait(80);
  const submitted=api.calls.find(call=>call.method==='POST'&&call.path.endsWith('/responses'));
  ok(submitted?.body?.answers?.['full-name']==='لیلا رضایی'&&api.draft.submitted===true,
    'ثبت نهایی پاسخ با شناسهٔ فیلد به API سروری رسید و وضعیت سمت سرور تأیید شد');
  ok(page.visible('.screen').join()==='u12'&&page.txt('#endStatusTitle')==='تکمیل شد!'
      &&page.txt('#endStatusCaption').includes('بله')
      &&page.txt('#endText')===''&&page.doc.querySelector('#serverTicketTypeRow').hidden
      &&!page.store.getItem('nora-regs')&&api.calls.some(call=>call.method==='POST'&&call.path.endsWith('/ticket-link')),
    'پایان سروری عنوان «تکمیل شد!» و لینک تحویل سرور را دارد، بدون رکورد محلی');
  const ticketLink=page.doc.querySelector('#serverTicketLink');
  const validTicketUrl='https://ble.ir/nora_test_bot?start=ft_'+'A'.repeat(48);
  const rejectsUnsafeTicketUrls=page.window.eval('publicTicketDeliveryURL('+JSON.stringify('https://evil.example/nora?start=ft_'+'A'.repeat(48))+')')===''
    &&page.window.eval('publicTicketDeliveryURL('+JSON.stringify('https://ble.ir/nora_test_bot?start=ft_short')+')')==='';
  ok(ticketLink&&!ticketLink.hidden&&ticketLink.getAttribute('href')===validTicketUrl
      &&ticketLink.textContent.includes('دانلود بلیت')
      &&!page.doc.querySelector('#serverTicketDownload')
      &&page.doc.querySelector('#serverTicketImage').getAttribute('src')==='/api/public/forms/'+id+'/ticket-image'
      &&page.txt('#serverTicketImageStatus').includes('تصویر بلیتت رو آماده می‌کنیم')
      &&rejectsUnsafeTicketUrls,
    'پایان فقط یک CTA دانلود بلیت در بله دارد و تصویر را از endpoint واقعی می‌گیرد');
  ok(!page.doc.querySelector('#localTicketSummary')&&page.doc.querySelector('#endLocalNotice').hidden
      &&page.doc.querySelector('#endSampleMessageCard').hidden
      &&page.doc.querySelector('#endLinksCard').hidden
      &&page.doc.querySelector('#endLocalFooterCard').hidden
      &&page.all('#u12 [data-after-mode]:not([hidden])').length===0
      &&!page.doc.querySelector('#endLinksCard').contains(page.doc.querySelector('#endText')),
    'پایان سروری فقط محتوای لازم را دارد و کارت محلی/پیوند برگشت یا ویرایش ندارد');

  const typedId='server-ticket-type-smoke',assignedType={id:'priority',name:'ورودی ویژه'};
  const unsafeTypeName='ویژه <img src=x onerror=alert(1)>',typedType={id:'priority-html',name:unsafeTypeName};
  const typedApi=makePublicApiMock({id:typedId,ticketType:typedType});
  const typedPage=await loadPublicForm(makePublicFormData(typedId),typedApi.fetch);
  typedPage.click('#next');await wait(20);typedPage.input('#qa0','نیلوفر نوع بلیت');await wait(720);typedPage.click('#next');await wait(80);
  const assignedTypeRow=typedPage.doc.querySelector('#serverTicketTypeRow');
  ok(!assignedTypeRow.hidden&&typedPage.doc.querySelector('#serverTicketTypeName').textContent===unsafeTypeName
      &&assignedTypeRow.querySelector('#serverTicketTypeName').childElementCount===0
      &&!assignedTypeRow.querySelector('img')
      &&typedPage.doc.querySelector('#serverTicketImage').getAttribute('src')==='/api/public/forms/'+typedId+'/ticket-image'
      &&typedPage.doc.querySelector('#serverTicketLink').textContent.includes('دانلود بلیت')
      &&!typedPage.doc.querySelector('#serverTicketDownload')
      &&typedApi.draft.ticket_type.id==='priority-html',
    'مدل تخصیص‌یافتهٔ سرور از HTML ایمن می‌ماند؛ CTA تصویرِ renderer فقط یک لینک بله است');

  const recoveredType={id:'vip',name:'ورودی ویژه'};
  const recoveredApi=makePublicApiMock({id,draft:{answers:{'full-name':'آرمان بازیابی‌شده'},submitted:true,status:'accepted',form_version:2,ticket_type:recoveredType}});
  const recovered=await loadPublicForm(form,recoveredApi.fetch);
  ok(recovered.doc.querySelector('#qa0')?.value==='آرمان بازیابی‌شده'
      &&recovered.visible('.screen').join()==='u12'
      &&!recovered.doc.querySelector('#serverTicketTypeRow').hidden
      &&recovered.txt('#serverTicketTypeName')==='ورودی ویژه'
      &&recovered.txt('#draftStatus').includes('پاسخ قبلی از سرور بازیابی شد'),
    'پاسخ ثبت‌شده، مدل تخصیص‌یافته و مقدار فیلد از کوکی نشست سروری پس از بارگذاری دوباره بازیابی شدند');

  const waitApi=makePublicApiMock({id:'server-waitlist-smoke',submitStatus:'waitlisted',ticketType:assignedType});
  const waitPage=await loadPublicForm(makePublicFormData('server-waitlist-smoke'),waitApi.fetch);
  waitPage.click('#next');waitPage.input('#qa0','سارا انتظار');await wait(720);waitPage.click('#next');await wait(100);
  ok(waitPage.visible('.screen').join()==='u12'&&waitPage.txt('#endText')===''
      &&!/(صف|انتظار|ظرفیت|بلیتی صادر نشده)/.test(waitPage.txt('#endText'))
      &&waitPage.doc.querySelector('#serverTicketPreview').hidden&&waitPage.doc.querySelector('#serverTicketTypeRow').hidden
      &&!waitApi.calls.some(call=>call.method==='POST'&&call.path.endsWith('/ticket-link')),
    'پاسخ فهرست انتظار بدون ذکر صف/ظرفیت در پایان ماند و هیچ پیوند یا بلیتی نگرفت');

  const receiptId='server-receipt-smoke',receiptApi=makePublicApiMock({id:receiptId,receiptUploadRequired:true,ticketType:assignedType});
  const receiptForm=makePublicFormData(receiptId,true);
  const receiptPage=await loadPublicForm(receiptForm,receiptApi.fetch);
  receiptPage.window.eval("show('u9')");
  ok(receiptPage.visible('.screen').join()==='u8'
      &&receiptPage.window.eval("selectedPaymentMethod==='' ")
      &&receiptPage.all('#u8 [data-method]:not([hidden])').length===1
      &&receiptPage.doc.querySelector('[data-method="card_transfer"]').disabled===false
      &&receiptPage.doc.querySelector('[data-method="card_transfer"]').getAttribute('aria-checked')==='false'
      &&receiptPage.doc.querySelector('[data-method="bale_wallet"]').hidden
      &&receiptPage.doc.querySelector('#paymentBankCardWrap').hidden
      &&!receiptPage.doc.querySelector('#paymentMethodRequired').hidden,
    'فرم فقط روش کارت‌به‌کارتِ انتخاب‌شدهٔ سازنده را نشان می‌دهد؛ کیف پول بله و انتخاب پیش‌فرض پنهان‌اند');
  receiptPage.window.eval("show('u1')");
  receiptPage.click('#next');await wait(20);receiptPage.input('#qa0','مریم کارت‌به‌کارت');await wait(720);
  receiptPage.click('#next');
  ok(receiptPage.visible('.screen').join()==='u8'&&receiptPage.doc.querySelector('#paymentSelectionCard').hidden===false
      &&receiptPage.window.eval("selectedPaymentMethod==='' "),
    'تنظیم سروری دریافت فیش، روش پرداخت را بدون انتخاب پیش‌فرض نشان می‌دهد');
  receiptPage.click('[data-fin="0"]');
  ok(receiptPage.window.eval('calc().sum===650000')&&receiptPage.txt('#bill').includes('۶۵۰٬۰۰۰ ریال'),
    'پس از انتخاب گزینهٔ مالی، مبلغ کل فرم درست در جمع‌بندی دیده می‌شود');
  receiptPage.click('#next');
  ok(receiptPage.visible('.screen').join()==='u8'
      &&receiptPage.doc.querySelector('#paymentMethodList').getAttribute('aria-invalid')==='true',
    'فرم سروری نیز بدون انتخاب طرح پرداخت اجازهٔ ادامه نمی‌دهد');
  receiptPage.click('[data-method="card_transfer"]');
  ok(receiptPage.txt('#next')==='ادامه به کارت مقصد','صفحهٔ انتخاب، گام کارت‌به‌کارت را پس از انتخاب طرح روشن می‌کند');
  receiptPage.click('#next');
  ok(receiptPage.visible('.screen').join()==='u9'
      &&receiptPage.txt('#next')==='ثبت پاسخ و ادامه'
      &&receiptPage.doc.querySelector('[data-method="card_transfer"]').getAttribute('aria-checked')==='true'
      &&!receiptPage.doc.querySelector('#paymentBankCardWrap').hidden
      &&receiptPage.txt('#paymentBankName')==='بانک نمونه'
      &&receiptPage.txt('#paymentBankCardNumber')==='4111 1111 1111 1111'
      &&receiptPage.txt('#paymentBankCardHolder')==='به نام حساب سازمان'
      &&!receiptPage.doc.querySelector('#paymentBankCardQuickCopy').hidden
      &&receiptPage.doc.querySelector('#paymentBankCardQuickCopy').textContent.trim()===''
      &&!receiptPage.doc.querySelector('#paymentInstructionsBox').hidden
      &&receiptPage.txt('#paymentInstructionsBox').includes('واریز فقط به کارت مقصد')
      &&!receiptPage.doc.querySelector('#paymentTransferTotal').hidden
      &&receiptPage.txt('#paymentTransferLabel')==='مبلغ کامل واریز'
      &&receiptPage.txt('#payAmount').includes('۶۵۰٬۰۰۰'),
    'کارت مقصدِ سروری تمام مبلغ را یک‌جا نشان می‌دهد و فیش برای بازبینی دستی می‌ماند');
  let quickCopiedPaymentCard='';
  receiptPage.window.NORA_UI.copyText=value=>{quickCopiedPaymentCard=String(value);return true};
  receiptPage.click('#paymentBankCardQuickCopy');
  ok(quickCopiedPaymentCard==='4111111111111111','شماره کارت از روی کارت گرافیکیِ مقصد کپی می‌شود');
  receiptPage.click('#paymentAmountCopy');
  ok(quickCopiedPaymentCard==='650000','کل مبلغ دقیق ریالی از آیکون کپی می‌شود');
  receiptPage.click('#next');await wait(120);
  const responseCall=receiptApi.calls.find(call=>call.method==='POST'&&call.path.endsWith('/responses'));
  ok(receiptPage.visible('.screen').join()==='u11'
      &&responseCall&&receiptPage.doc.querySelector('#serverReceiptUpload')&&!receiptPage.doc.querySelector('#serverReceiptUpload').hidden
      &&receiptPage.doc.querySelector('#serverTicketPreview').hidden
      &&receiptPage.doc.querySelector('#serverTicketTypeRow').hidden
      &&receiptPage.txt('#endText')===''
      &&!receiptApi.calls.some(call=>call.method==='POST'&&call.path.endsWith('/ticket-link')),
    'پاسخ ثبت شد و فرم به بارگذاری رسید رفت؛ تصویر و لینک بلیت هنوز ساخته نشده‌اند');
  const receiptInput=receiptPage.doc.querySelector('#serverReceiptFile');
  const receiptFile=new receiptPage.window.File(['%PDF-1.4\n'], 'receipt.pdf', {type:'application/pdf'});
  Object.defineProperty(receiptInput,'files',{configurable:true,value:[receiptFile]});
  receiptInput.dispatchEvent(new receiptPage.window.Event('change',{bubbles:true}));
  const participantNote='واریز بابت ثبت‌نام مریم';
  receiptPage.input('#receiptNote',participantNote);
  receiptPage.click('#next');await wait(150);
  const uploadCall=receiptApi.calls.find(call=>call.method==='POST'&&call.path.endsWith('/receipt'));
  const reviewLinkCall=receiptApi.calls.find(call=>call.method==='POST'&&call.path.endsWith('/ticket-link'));
  ok(uploadCall?.body?.type==='application/pdf'&&uploadCall.body.size===receiptFile.size
      &&uploadCall.headers['X-Receipt-Note']===encodeURIComponent(participantNote)
      &&receiptApi.calls.indexOf(responseCall)<receiptApi.calls.indexOf(uploadCall)
      &&reviewLinkCall&&receiptApi.draft.receipt_uploaded===true&&receiptApi.payment.status==='receipt_submitted'
      &&receiptPage.visible('.screen').join()==='u11'
      &&receiptPage.doc.querySelector('#serverReceiptUpload').hidden
      &&!receiptPage.doc.querySelector('#receiptReviewBaleLink').hidden
      &&receiptPage.doc.querySelector('#receiptReviewBaleLink').getAttribute('href')===validTicketUrl
      &&receiptPage.txt('#receiptReviewMessage').includes('همین پیوند'),
    'پس از آپلود، همان لینک بله فقط بازبینی رسید را آغاز می‌کند و می‌گوید پس از تأیید دوباره بازش کن');
  ok(receiptPage.doc.querySelector('#serverTicketPreview').hidden
      &&receiptPage.doc.querySelector('#serverTicketTypeRow').hidden
      &&receiptPage.doc.querySelector('#serverTicketLink').hidden
      &&!receiptPage.doc.querySelector('#serverTicketImage').getAttribute('src')
      &&!receiptPage.store.getItem('nora-receipts'),
    'رسیدِ در انتظار تأیید هیچ تصویر، داده یا CTA بلیت نمی‌دهد و به انبار محلی نمی‌رود');

  receiptApi.setPaymentStatus('paid_manual');receiptPage.click('#receiptReviewStatusCheck');await wait(150);
  ok(receiptPage.visible('.screen').join()==='u12'
      &&receiptPage.txt('#endStatusTitle')==='تکمیل شد!'
      &&receiptPage.doc.querySelector('#serverTicketPreview').hidden===false
      &&receiptPage.doc.querySelector('#serverTicketLink').hidden===false
      &&receiptPage.doc.querySelector('#serverTicketLink').getAttribute('href')===validTicketUrl
      &&receiptPage.doc.querySelector('#serverTicketImage').getAttribute('src')==='/api/public/forms/'+receiptId+'/ticket-image'
      &&receiptPage.doc.querySelector('#serverReceiptReview').hidden
      &&!receiptPage.doc.querySelector('#serverTicketDownload')
      &&receiptPage.txt('#endText')==='',
    'پس از paid_manual، تصویر سروری و تنها لینک «دانلود بلیت» به بله فعال می‌شوند؛ رسید/مالی وارد صفحهٔ پایان نمی‌شود');
  ok(receiptApi.calls.filter(call=>call.method==='POST'&&call.path.endsWith('/ticket-link')).length>=2
      &&!receiptPage.store.getItem('nora-regs')&&!receiptPage.store.getItem('nora-receipts'),
    'لینک claim/review و لینک تحویل امنِ پس از تأیید جدا هستند و هیچ پاسخ سروری در ذخیرهٔ محلی کپی نشده');

}

/* ── ۲پ) همراهانِ پاسخ مستقل، ذخیرهٔ سروری و بازیابی ── */
{
  console.log('\n── پاسخ جداگانهٔ همراهان در فرم سروری ──');
  const id='server-companions-smoke',form=makePublicFormData(id);
  form.name='فرم همراهان';form.guestsOn=true;form.maxPer=3;form.compFields='name-mobile-answers';
  form.settings={...form.settings,guestsOn:true,maxPer:3,compFields:'name-mobile-answers'};
  form.fields=[
    {id:'full-name',t:'fullname',l:'نام و نام خانوادگی',required:true},
    {id:'mobile',t:'mobile',l:'شمارهٔ همراه',required:true},
    {id:'city',t:'select',l:'شهر',opts:['تهران','اصفهان'],required:true},
  ];
  const api=makePublicApiMock({id}),page=await loadPublicForm(form,api.fetch);
  ok(page.errors.length===0&&page.window.eval("GUEST_ON&&GUEST_MAX===3&&companionAnswersOn()&&REG.display==='one'")
      &&page.doc.querySelectorAll('[data-companion-toggle]').length===3&&!page.doc.querySelector('#qall'),
    'فرم ثبت‌نام دانه‌دانه است و کنترل + کنار هر پرسش را از تنظیمات سرور می‌خواند');
  page.click('#next');
  ok(page.visible('.screen').includes('qp0')&&page.txt('#stepCap')==='۱ از ۳',
    'فرم در هر مرحله فقط یک پرسش را نشان می‌دهد');
  page.input('#qa0','لیلا پاسخ‌دهنده');
  page.click('[data-companion-toggle="0"]');
  ok(page.doc.querySelector('[data-companion-fields="0"]').hidden===false
      &&page.doc.querySelector('#shBuddy').classList.contains('on')===false
      &&page.doc.querySelector('[data-companion-answer-card][data-guest-index="0"][data-question-index="0"] [data-companion-input]')
      &&!page.doc.querySelector('[data-companion-identity]')
      &&page.doc.querySelector('[data-companion-toggle="0"]').textContent.includes('جای دوستات خالیه :)'),
    'دکمهٔ + همان پرسش را برای همراه باز می‌کند و نام جدا از پرسش فرم نمی‌گیرد');
  page.input('[data-companion-answer-card][data-guest-index="0"][data-question-index="0"] [data-companion-input]','مریم همراه');
  ok(page.window.eval("S.guests.length===1&&S.companionFields.has(0)&&S.guests[0].name==='مریم همراه'&&S.guests[0].answers['full-name']==='مریم همراه'"),
    'نام همراه از پاسخ همان پرسش گرفته و جداگانه در پاسخ‌های او ذخیره شد');
  page.click('#next');
  ok(page.visible('.screen').includes('qp1'),'پس از تکمیل پرسش نام برای هر دو نفر، فرم به سؤال بعدی می‌رود');
  page.input('#qa1','09121112222');
  page.click('[data-companion-toggle="1"]');
  page.input('[data-companion-answer-card][data-guest-index="0"][data-question-index="1"] [data-companion-input]','09121234567');
  page.click('#next');
  ok(page.visible('.screen').includes('qp2'),'شمارهٔ همراه هم از پرسش فرم گرفته و مسیر به پرسش بعدی رفت');
  page.set('#qa2','تهران');
  page.click('[data-companion-toggle="2"]');
  page.click('#next');
  ok(page.visible('.screen').includes('qp2')
      &&page.doc.querySelector('[data-companion-answer-card][data-guest-index="0"][data-question-index="2"] [data-companion-error]')?.textContent.includes('اجباری'),
    'پرسش اجباری بعدی برای همراه هم اعتبارسنجی می‌شود');
  page.set('[data-companion-answer-card][data-guest-index="0"][data-question-index="2"] select','اصفهان');
  page.click('[data-companion-add="2"]');
  page.set('[data-companion-answer-card][data-guest-index="1"][data-question-index="2"] select','تهران');
  page.click('#prev');
  page.input('[data-companion-answer-card][data-guest-index="1"][data-question-index="1"] [data-companion-input]','09121234568');
  page.click('#prev');
  page.input('[data-companion-answer-card][data-guest-index="1"][data-question-index="0"] [data-companion-input]','رضا همراه');
  page.click('#next');page.click('#next');
  await wait(720);
  const autosave=api.calls.filter(call=>call.method==='PATCH').at(-1);
  ok(autosave?.body?.companions?.length===2
      &&autosave.body.companions[0].answers['full-name']==='مریم همراه'
      &&autosave.body.companions[0].answers.mobile==='09121234567'
      &&autosave.body.companions[0].answers.city==='اصفهان'
      &&autosave.body.companions[1].answers['full-name']==='رضا همراه'
      &&autosave.body.companions[1].answers.mobile==='09121234568'
      &&autosave.body.companions[1].answers.city==='تهران',
    'پیش‌نویس سرور پاسخ‌های مستقل دوست‌ها را با شناسهٔ درست پارامتر نگه می‌دارد');
  page.click('#next');await wait(120);
  ok(page.visible('.screen').includes('u12'),'پاسخ اصلی و پاسخ‌های جداگانهٔ دو همراه در هر دو پرسش اجباری ثبت شد؛ فرمِ بی‌هزینه مرحلهٔ همراه جدا ندارد');
  const submitted=api.calls.find(call=>call.method==='POST'&&call.path.endsWith('/responses'));
  ok(submitted?.body?.companions?.length===2&&api.draft.companions.length===2
      &&api.draft.companions[0].answers.mobile==='09121234567'
      &&api.draft.companions[0].answers.city==='اصفهان'
      &&api.draft.companions[1].answers.mobile==='09121234568'
      &&api.draft.companions[1].answers.city==='تهران'
      &&page.visible('.screen').includes('u12'),
    'ثبت نهایی، هویت و پاسخ‌های جداگانهٔ دو دوست را برای ساخت ردیف‌های مستقل به سرور می‌فرستد');
  ok(!page.store.getItem('nora-regs')&&!page.store._dump().some(key=>key.startsWith('nora:draft:')),
    'فرم سروری، پاسخ یا پیش‌نویس را در انبار محلی نمی‌نویسد');

  const recoveredApi=makePublicApiMock({id,draft:{answers:{'full-name':'لیلا بازیابی',mobile:'09121112222'},companions:[
    {name:'مریم همراه',mobile:'09121234567',answers:{'full-name':'پاسخ بازیابی مریم',mobile:'09121234567',city:'اصفهان'}},
    {name:'رضا همراه',mobile:'09121234568',answers:{'full-name':'پاسخ بازیابی رضا',mobile:'09121234568',city:'تهران'}},
  ],submitted:false,status:'draft',form_version:2}});
  const recovered=await loadPublicForm(form,recoveredApi.fetch);
  ok(recovered.errors.length===0&&recovered.window.eval("S.guests.length===2")
      &&recovered.doc.querySelector('#qa0').value==='لیلا بازیابی'
      &&recovered.doc.querySelector('[data-companion-answer-card][data-guest-index="0"][data-question-index="0"] [data-companion-input]').value==='پاسخ بازیابی مریم'
      &&recovered.doc.querySelector('[data-companion-answer-card][data-guest-index="1"][data-question-index="0"] [data-companion-input]').value==='پاسخ بازیابی رضا'
      &&recovered.doc.querySelector('[data-companion-answer-card][data-guest-index="0"][data-question-index="1"] [data-companion-input]').value==='09121234567'
      &&recovered.doc.querySelector('[data-companion-answer-card][data-guest-index="0"][data-question-index="2"] select').value==='اصفهان',
    'پیش‌نویس سروری، پاسخ اصلی و جواب جداگانهٔ هر همراه را پس از بارگذاری دوباره بازیابی می‌کند');
}

/* ── ۲پ) پنل فرم‌ساز در تولید از نمونه‌ها و حافظهٔ محلی خالی می‌ماند ── */
{
  console.log('\n── فرم‌ساز تولیدی: بدون دادهٔ نمونه ──');
  const store=makeStore({
    'nora-forms':JSON.stringify([{id:'fake-local-form',name:'فرم محلی نباید بیاید',status:'published',fields:[]}]),
    'nora-regs':JSON.stringify([{form:'fake-local-form',code:'FAKE-1',demo:true,ans:[{l:'نام',v:'کاربر ساختگی'}]}])
  });
  const page=await load('builder.html',store,'',null,{fixtureMode:false});
  await wait(60);
  /* در تولید، فهرست خودکار از سرور خواسته می‌شود؛ وقتی شبکه در دسترس نیست حالت خطا با «تلاش دوباره» می‌آید، نه فهرست محلی */
  ok(page.errors.length===0&&!page.doc.querySelector('#formCards [data-form]')
    &&!page.txt('#formCards').includes('فرم محلی نباید بیاید')
    &&page.doc.querySelector('#serverFormsMessage').dataset.state==='error'
    &&page.doc.querySelector('#serverFormsRetry').hidden===false
    &&page.txt('#formCards').includes('تلاش دوباره'),
    'فهرست پیش‌فرض خالی است، فرم ذخیره‌شدهٔ محلی به‌جای سرور نشان داده نمی‌شود و بدون شبکه حالت خطا با تلاش دوباره دیده می‌شود');
  page.click('[data-go="fReports"]');
  ok(page.txt('#formReportCount').includes('۰ سرور')&&!page.txt('#formReportList').includes('نمونهٔ مرورگر')
    &&!page.txt('#formReportList').includes('فرم محلی نباید بیاید'),
    'گزارش بدون پاسخ API خالی است و فرم محلی را وارد آمار نمی‌کند');
  page.click('[data-go="fSettings"]');
  ok(page.txt('#formSettingsCount').includes('۰ فرم')&&page.txt('#formSettingsList').includes('هنوز فرمی نیست'),
    'تنظیمات فرم بدون فرم سروری در وضعیت خالی می‌ماند');
  page.click('[data-go="fTeam"]');
  ok(page.txt('#teamBox').includes('از API این صفحه پشتیبانی نمی‌شود')
    &&!page.txt('#teamBox').includes('خانم رستگار'),'فهرست کارشناسان ساختگی در تجربهٔ تولیدی نمایش داده نمی‌شود');
  page.click('[data-go="fKartabl"]');
  ok(page.txt('#kartabl').includes('کارتابل مشترک پنل مدیران')&&!!page.doc.querySelector('#kartabl a[href="admin.html#inbox"]')
    &&!page.txt('#kartabl').includes('سارا محمدی'),
    'کارتابل فاقد API به کارتابل مشترک پنل پیوند می‌دهد و رسید نمونه نشان نمی‌دهد');
  page.click('[data-go="fAttend"]');
  ok(page.txt('#attBody').includes('هیچ داده یا صندلی نمونه‌ای نمایش داده نمی‌شود')
    &&page.txt('#attBody').includes('تا اتصال API حضور'),'حضور و غیاب بدون API به‌جای صندلی و حضور نمونه توضیح می‌دهد');
  page.dom.window.close();
}

/* ── ۲ت) پاسخ‌های سروری و جواب‌های همراه در گزارش مدیر ── */
{
  console.log('\n── گزارش مدیر برای پاسخ‌های سروری و همراهان ──');
  const id='server-manager-companions',record={
    id,name:'فرم ثبت‌نام سروری',model:'registration',need:'reg',slug:'manager-companions',ev:'',
    fields:[
      {id:'full-name',t:'fullname',l:'نام کامل',req:true},
      {id:'city',t:'select',l:'شهر',req:true,opts:['تهران','اصفهان']},
    ],settings:{display:'all',guestsOn:true,maxPer:3,compFields:'name-mobile-answers'},
    status:'published',version:2,created_at:'2026-10-03T08:00:00+00:00',updated_at:'2026-10-03T08:00:00+00:00',
  };
  const responses=[{
    id:'response-primary-001',status:'accepted',form_version:2,
    answers:{'full-name':'لیلا پاسخ‌دهنده',city:'تهران'},companions:[],
    created_at:'2026-10-03T08:15:00+00:00',updated_at:'2026-10-03T08:15:00+00:00',
  },{
    id:'response-companion-001',status:'accepted',form_version:2,
    answers:{'full-name':'مریم همراه',city:'اصفهان'},companions:[],
    registrant_name:'مریم همراه',registrant_mobile:'09121234567',
    added_by_response_id:'response-primary-001',added_by_name:'لیلا پاسخ‌دهنده',companion_index:0,
    created_at:'2026-10-03T08:15:00+00:00',updated_at:'2026-10-03T08:15:00+00:00',
  }];
  const api=makeFormsApiMock({id,initialRecord:record,responses}),store=makeStore();
  const page=await load('builder.html',store,'',api.fetch);
  page.click('#syncServerForms');await wait(120);
  ok(page.errors.length===0&&page.doc.querySelector('#formCards [data-form="'+id+'"]'),
    'مدیر فرم منتشرشده را از API سرور خواند'+(page.errors.length?': '+page.errors[0]:''));
  page.click('#formCards [data-form="'+id+'"]');await wait(100);
  ok(api.calls.some(call=>call.path.startsWith('/api/forms/'+id+'/responses')&&call.method==='GET')
      &&page.doc.querySelectorAll('#answersBox tbody tr[data-person]').length===2
      &&page.txt('#answersBox').includes('لیلا پاسخ‌دهنده')
      &&page.txt('#answersBox').includes('مریم همراه')
      &&page.txt('#answersBox').includes('افزوده‌شده توسط لیلا پاسخ‌دهنده')
      &&page.txt('#answersBox').includes('ثبت‌شده در سرور')
      &&page.txt('#formCards').includes('پاسخ سروری'),
    'گزارش پاسخ‌ها از endpoint مجاز سروری پر شد؛ همراه ردیف مستقل و یادداشت «افزوده‌شده توسط» دارد');
  page.click('#answersBox tr[data-person="server:response-companion-001"]');
  ok(page.txt('#usSub').includes('شناسهٔ پاسخ سروری')
      &&page.txt('#usName')==='مریم همراه'
      &&page.txt('#usBody').includes('اصفهان')
      &&page.txt('#usBody').includes('افزوده‌شده توسط لیلا پاسخ‌دهنده')
      &&page.txt('#usBody').includes('این پاسخ از سرور خوانده شده')
      &&!page.txt('#usBody').includes('فقط در همین مرورگر ذخیره شد'),
    'جزئیات مدیر همراه را به‌عنوان پاسخ مستقل با پاسخ‌های خودش و نام ثبت‌کننده نشان می‌دهد');
  page.click('[data-refresh-server-responses="'+id+'"]');await wait(80);
  ok(api.calls.filter(call=>call.path.startsWith('/api/forms/'+id+'/responses')&&call.method==='GET').length>=2,
    'مدیر می‌تواند پاسخ‌های سروری را دوباره از API بخواند');
  ok(page.network.every(path=>String(path).startsWith('/api/')),
    'نمایش پاسخ‌های همراه هیچ درخواست بیرونی نمی‌سازد');
}

/* ── ۳) فرم‌ساز مرکزی → پروندهٔ محلی شخص؛ پاسخ مبلغ‌دار هم پرداخت نمی‌شود ── */
{
  console.log('\n── فرم‌ساز و پروندهٔ شخص ──');
  const store=makeStore();
  store.setItem('nora-forms',JSON.stringify([
    {id:'f1',name:'فرم کارگاه نمونه',kind:'ثبت‌نام',need:'reg',ev:'ev1',
      fields:[{id:1,t:'fullname',l:'نام و نام خانوادگی',req:true},
              {id:2,t:'mobile',l:'شماره موبایل',req:true},
              {id:3,t:'choice',l:'سطح',req:true,opts:[{l:'آغازگر'},{l:'میانی'}]}],
      fin:[],groups:[],methods:[],on:1}]));
  const p=await load('form.html',store,'?kind=reg&fid=f1');
  p.click('#next');
  ok(p.visible('.screen').join()==='qp0'&&p.doc.querySelector('#prev').hidden
      &&p.txt('#stepCap')==='۱ از ۳'&&!p.doc.querySelector('#pos'),
    'اولین سؤال فرم‌ساز قبلی ندارد و شمارنده فقط در سرصفحه نمایش داده می‌شود');
  p.set('#qa0','مریم احمدی'); p.click('#next');
  p.set('#qa1','09121234567'); p.click('#next');
  p.click('#qp2 .opt:nth-child(2)'); p.click('#next');
  ok(p.visible('#u12').length===1,'فرم‌ساز با پاسخ‌های لازم به پایان محلی رسید ('+p.visible('.screen').join(',')+')');
  const regs=JSON.parse(store.getItem('nora-regs')||'[]'), people=JSON.parse(store.getItem('nora-people')||'[]');
  ok(regs.length===1&&regs[0].form==='f1'&&regs[0].ev==='ev1','پاسخ با شناسهٔ فرم و رویداد فقط در انبار محلی ثبت شد');
  ok((regs[0].ans||[]).length>=3,'پاسخ‌ها به ثبت محلی پیوستند');
  ok(people.length===1&&people[0].name==='مریم احمدی'&&people[0].mobile==='09121234567',
    'همان پاسخ پروندهٔ شخص را کامل کرد');
  ok(regs[0].pid===people[0].id,'ثبت به پروندهٔ محلی شخص وصل است');
  p.window.eval('renderPaymentMethods()');
  ok(!store.getItem('nora-receipts')&&!store.getItem('nora-home-pay')
      &&p.window.eval('paymentStepEnabled===false')&&p.doc.querySelector('#paymentSelectionCard').hidden,
    'فرم بدون تنظیم پرداخت، روش پرداخت را پنهان می‌کند و هیچ تراکنش یا رسیدی نمی‌سازد');
  ok(p.network.length===0,'ثبت پاسخ هیچ پیام یا درخواست شبکه‌ای نفرستاد');
  const retry=await load('form.html',store,'?kind=reg&fid=f1');
  retry.click('#next');retry.set('#qa0','مریم دوباره');retry.click('#next');retry.set('#qa1','09121234567');retry.click('#next');
  retry.click('#qp2 .opt:first-child');retry.click('#next');
  ok(retry.visible('.screen').join()==='qp2'&&JSON.parse(store.getItem('nora-regs')||'[]').length===1,
    'تنظیم یک‌پاسخی تکرار محلی را فقط با شناسهٔ پاسخ همین مرورگر می‌بندد');
}

/* ── ۳الف) ویرایش همان پاسخ محلی، بدون رکورد یا پروندهٔ تکراری ── */
{
  console.log('\n── ویرایش پاسخ محلی ──');
  const form={id:'f-answer-edit',name:'فرم ویرایش پاسخ',need:'reg',display:'one',after:'edit',onePerPerson:true,
    fields:[{id:'name',t:'fullname',l:'نام و نام خانوادگی',req:true},{id:'mobile',t:'mobile',l:'شمارهٔ همراه',req:true}],fin:[]},
    store=makeStore({'nora-forms':JSON.stringify([form])}),p=await load('form.html',store,'?fid=f-answer-edit');
  p.click('#next');p.set('#qa0','مریم پاسخ‌دهنده');p.click('#next');
  p.set('#qa1','09121234567');p.click('#next');
  const firstRegs=JSON.parse(store.getItem('nora-regs')||'[]'),firstPeople=JSON.parse(store.getItem('nora-people')||'[]');
  ok(firstRegs.length===1&&firstPeople.length===1&&firstRegs[0].pid===firstPeople[0].id,
    'ثبت نخست یک پاسخ محلی و یک پروندهٔ شخصِ مرتبط می‌سازد');
  const code=firstRegs[0].code,personId=firstPeople[0].id;
  p.click('#u12 [data-after-mode="edit"]');
  if(p.window.eval("cur==='qp1'"))p.click('#prev');
  p.set('#qa0','مریم ویرایش‌شده');p.click('#next');p.click('#next');
  const updatedRegs=JSON.parse(store.getItem('nora-regs')||'[]'),updatedPeople=JSON.parse(store.getItem('nora-people')||'[]');
  ok(updatedRegs.length===1&&updatedRegs[0].code===code
      &&updatedRegs[0].ans.some(a=>a.l==='نام و نام خانوادگی'&&a.v==='مریم ویرایش‌شده')
      &&updatedPeople.length===1&&updatedPeople[0].id===personId&&updatedPeople[0].name==='مریم ویرایش‌شده',
    'ویرایش، همان پاسخ در nora-regs و همان پرونده در nora-people را به‌روز می‌کند؛ رکورد تازه نمی‌سازد');
}

/* ── ۳ب) مسیر خطای فرم و پاک‌کردن فقط پیش‌نویس ── */
{
  console.log('\n── مسیر فرم و پاک‌کردن پیش‌نویس ──');
  const missing=await load('form.html',makeStore(),'?fid=missing-form');
  ok(missing.errors.length===0&&missing.visible('.screen').join()==='uUnavailable'
      &&missing.txt('#unavailableTitle')==='فرم پیدا نشد'&&missing.txt('#unavailableText').includes('پیوند فرم')
      &&missing.doc.querySelector('#botbar').style.display==='none',
    'خطای پیوند ناموجود درون صفحه، روشن و بدون دکمهٔ ادامه نمایش داده می‌شود');
  const draftForm={id:'f-route-draft',name:'پیش‌نویس نمونه',status:'draft',fields:[{id:'q',t:'text',l:'پرسش'}],fin:[]},
    draftStore=makeStore({'nora-forms':JSON.stringify([draftForm])});
  const draft=await load('form.html',draftStore,'?fid=f-route-draft');
  ok(draft.visible('.screen').join()==='uUnavailable'&&draft.txt('#unavailableTitle')==='فرم هنوز منتشر نشده',
    'فرم پیش‌نویس به‌جای نمایش فرم قابل‌ارسال، پیام وضعیت می‌دهد');
  /* فاز ۷: سرور فرم منتشرشده را به‌خاطر بستهٔ بودن پنجرهٔ ثبت‌نام رویداد با registration-closed:<event> برمی‌گرداند */
  const gatedHtml=fs.readFileSync(DIR+'form.html','utf8')
    .replace('<!--nora-public-form-->','null').replace('<!--nora-public-draft-->','null')
    .replace('<!--nora-public-error-->',safeScriptJSON('registration-closed:ev-gated-1'));
  const gated=await loadHtml('form.html',gatedHtml,makeStore(),'?fid=f-gated');
  ok(gated.errors.length===0&&gated.visible('.screen').join()==='uUnavailable'
      &&gated.txt('#unavailableTitle')==='ثبت‌نام این رویداد باز نیست'&&gated.txt('#unavailableText').includes('ساعت و وضعیت سرور')
      &&gated.doc.querySelector('#unavailableBack')?.getAttribute('href')==='event.html?id=ev-gated-1'
      &&gated.doc.querySelector('#botbar').style.display==='none',
    'بستهٔ بودن ثبت‌نام رویداد (دروازهٔ سرور) با پیام مشخص و بازگشت به صفحهٔ همان رویداد نمایش داده می‌شود؛ فرم باز نمی‌شود');
  const injected=fs.readFileSync(DIR+'form.html','utf8')
    .replace('<!--nora-public-form-->','null').replace('<!--nora-public-draft-->','null')
    .replace('<!--nora-public-error-->',safeScriptJSON('registration-closed:javascript:alert(1)'));
  const injectedPage=await loadHtml('form.html',injected,makeStore(),'?fid=f-gated');
  ok(injectedPage.doc.querySelector('#unavailableBack')?.getAttribute('href')==='home.html','شناسهٔ رویداد نامعتبر در خطای مسیر، پیوند بازگشت را تغییر نمی‌دهد');
  const preview=await load('form.html',draftStore,'?fid=f-route-draft&preview=1');
  ok(!!preview.window.__NORA_FORM_PREVIEW&&preview.visible('.screen').join()==='u1',
    'پیش‌نمایش صریح سازنده می‌تواند پیش‌نویس را بدون انتشار باز کند');

  const completionForm={id:'local-fill-completion-test',name:'فرم آزمایشی تکمیل',model:'registration',need:'reg',
    status:'draft',slug:'local-fill-completion-test',display:'one',after:'view',profilePrefill:false,onePerPerson:false,
    enabledPaymentMethods:[],receiptReviewRequired:false,fin:[],links:[],fields:[
      {id:'preview-name',t:'fullname',l:'نام نمایشی برای آزمون',req:true},
      {id:'preview-step',t:'choice',l:'کدام بخش را بررسی می‌کنی؟',req:true,opts:[{l:'پرسش‌ها'},{l:'مرحلهٔ بعد'},{l:'پایان فرم'}]},
      {id:'preview-note',t:'area',l:'یادداشت آزمایشی',req:true}
    ]};
  const completionStore=makeStore({'nora-forms':JSON.stringify([completionForm]),
    'nora:draft:local-fill-completion-test':JSON.stringify({inputs:{qa0:'پاسخ قبلی نباید بازیابی شود'}})});
  const completion=await load('form.html',completionStore,
    '?fid=local-fill-completion-test&kind=reg&preview=1');
  ok(completion.visible('.screen').join()==='u1'&&completion.doc.querySelector('#qa0')?.value===''
      &&completionStore.getItem('nora:draft:local-fill-completion-test')===null,
    'فرم محلیِ پیش‌نمایش خالی باز می‌شود و پاسخ قبلی را خودکار بازیابی نمی‌کند');
  completion.click('#next');completion.input('#qa0','نام آزمایشی');completion.click('#next');
  completion.click('#qp1 .opt:last-child');completion.click('#next');
  completion.input('#qa2','یادداشت فقط برای آزمون');completion.click('#next');
  ok(completion.visible('.screen').join()==='u12'
      &&completion.txt('#endStatusTitle').includes('پیش‌نمایش')
      &&completion.txt('#endText').includes('به سرور ارسال نشد')
      &&!completionStore.getItem('nora-regs')&&!completionStore.getItem('nora-people')
      &&!completionStore.getItem('nora:draft:local-fill-completion-test')
      &&completion.network.length===0,
    'تکمیل فرم آزمایشی فقط صفحهٔ پیش‌نمایش را نشان می‌دهد؛ پاسخ، ثبت‌نام یا پرداخت محلی/سروری نمی‌سازد');

  const response={id:'r-existing',code:'DEMO-NOT-A-TICKET-existing',form:'f-draft-delete'},
    person={id:'p-existing',name:'پاسخ‌دهندهٔ نمونه'},form={id:'f-draft-delete',name:'فرم پیش‌نویس',slug:'draft-delete',
      fields:[{id:'q',t:'text',l:'پرسش'}],fin:[]},
    clearStore=makeStore({'nora-forms':JSON.stringify([form]),'nora:draft:draft-delete':JSON.stringify({cur:'qp0',
      at:'۱۴۰۵/۰۷/۰۹ · ۱۰:۰۰',savedAt:Date.now(),inputs:{qa0:'نیمه‌کاره'},guests:[],fin:[],picked:[]}),
      'nora-regs':JSON.stringify([response]),'nora-people':JSON.stringify([person])});
  const clear=await load('form.html',clearStore,'?fid=f-draft-delete');
  ok(clear.doc.querySelector('#resumeRow').style.display!=='none'&&clear.txt('#resumeRow').includes('نیمه‌کاره'),
    'پیش‌نویس نیمه‌کاره با زمان محلی و گزینهٔ ادامه نشان داده می‌شود');
  clear.click('[data-restart]');
  ok(clear.doc.querySelector('#shDraftDelete').classList.contains('on'),
    'پاک‌کردن پیش‌نویس قبل از اقدام، تأیید می‌خواهد');
  clear.click('[data-clear-draft]');
  ok(!clearStore.getItem('nora:draft:draft-delete')&&clear.doc.querySelector('#resumeRow').style.display==='none'
      &&JSON.stringify(JSON.parse(clearStore.getItem('nora-regs')))==JSON.stringify([response])
      &&JSON.stringify(JSON.parse(clearStore.getItem('nora-people')))==JSON.stringify([person])
      &&clear.txt('#draftStatus').includes('پاسخ‌های ثبت‌شده جداگانه می‌مانند'),
    'تأیید فقط پیش‌نویس را پاک می‌کند؛ پاسخ‌های nora-regs و پرونده‌های nora-people دست‌نخورده می‌مانند');
}

/* ── ۴) تنظیمات ذخیره‌شدهٔ فرم‌ساز → نمایش، شرط‌ها، دعوت، گزارش محلی ── */
{
  console.log('\n── تنظیمات فرم‌ساز، شرط‌ها و گزارش محلی ──');
  const store=makeStore();
  const form={id:'f-config',name:'فرم پیکربندی نمونه',kind:'ثبت‌نام',need:'reg',ev:'ev-config',slug:'local-config',
    display:'one',dir:'ltr',after:'view',eventVisible:true,start:'1405/07/01 08:00',ends:'1405/07/30 23:45',
    cap:8,wait:2,limit:'invite',inviteCodes:'DEMO-7',onePerPerson:true,sync:{cap:false,dates:true,limit:false,once:true},
    notify:{on:true,to:'ایتا'},introMedia:'image',introMediaNote:'پوستر آزمایشی',guestsOn:false,maxPer:2,fin:[],groups:[],
    fields:[
      {id:'q-name',t:'fullname',l:'نام و نام خانوادگی',req:true,prof:true},
      {id:'q-kind',t:'choice',l:'دسته',req:true,opts:[{l:'دیگر'},{l:'معمول'}]},
      {id:'q-details',t:'text',l:'توضیح شرطی',req:true,col:false,condField:'q-kind',condOp:'eq',condVal:'دیگر'},
      {id:'q-country',t:'dropdown',l:'گزینهٔ کشویی',req:true,opts:[{l:'ایران'},{l:'دیگر کشور'}]},
      {id:'q-private',t:'area',l:'یادداشت خارج از خروجی',req:false,col:false},
      {id:'q-file',t:'file',l:'پیوست نمونه',req:false,count:2,maxSize:1,media:'image',mediaNote:'فقط راهنمای محلی'}]};
  store.setItem('nora-forms',JSON.stringify([form]));
  const p=await load('form.html',store,'?fid=f-config&kind=reg');
  ok(p.errors.length===0,'فرم پیکربندی‌شده بی‌خطا بار شد'+(p.errors.length?': '+p.errors[0]:''));
  ok(p.window.__NORA_FORM_PREVIEW?.display==='one'&&p.doc.querySelector('#qp0')?.getAttribute('dir')==='ltr'
      &&!p.doc.querySelector('#qall'),
    'فرم ثبت‌نام با وجود تنظیم قدیمیِ یک‌صفحه‌ای، پرسش‌ها را یکی‌یکی نمایش می‌دهد');
  ok(p.txt('#formMeta').includes('ظرفیت')&&p.txt('#formMeta').includes('کد دعوت محلی')===false&&p.txt('#formMeta').includes('این پیش‌نمایش پیامی ارسال نمی‌کند'),
    'ظرفیت نمایشی و خاموش‌بودن اعلان در پیش‌نمایش روشن است');
  ok(p.doc.querySelector('#qp2').style.display==='none','پرسش شرطی تا انتخاب مقدار وابسته پنهان می‌ماند');
  p.click('#next');
  ok(p.visible('.screen').join()==='u1','کد دعوت نادرست فرم را از مرحلهٔ آغاز جلو نمی‌برد');
  p.set('#entryCode','DEMO-7');p.click('#next');
  ok(p.visible('.screen').join()==='qp0','کد دعوت نمونهٔ درست فقط در پیش‌نمایش محلی پذیرفته شد');
  p.click('#next');
  const nameError=p.doc.querySelector('#qerr-0'),nameControl=p.doc.querySelector('#qa0');
  ok(p.visible('.screen').join()==='qp0'&&nameError&&!nameError.hidden&&nameError.textContent.includes('اجباری')
      &&nameControl.getAttribute('aria-invalid')==='true'&&nameControl.getAttribute('aria-describedby').includes('qerr-0')
      &&p.doc.activeElement===nameControl,
    'اعتبارسنجیِ پرسش اجباری در همان مرحله پیام درون‌صفحه‌ای، پیوند دسترس‌پذیر و تمرکز می‌دهد');
  p.set('#qa0','مریم پیکربندی');
  ok(nameError.hidden&&nameControl.getAttribute('aria-invalid')===null,
    'پس از اصلاح پاسخ، پیام خطا و وضعیت نامعتبر خودکار پاک می‌شوند');
  p.click('#next');
  p.click('#qp1 [data-qsel="1"] .opt:first-child');
  ok(p.doc.querySelector('#qp2').style.display!=='none','شرط فیلد با پاسخ همان فرم باز و دوباره محاسبه شد');
  p.click('#next');p.set('#qa2','توضیح محلی');p.click('#next');
  p.set('#qa3','ایران');p.click('#next');
  p.set('#qa4','پاسخ خصوصی');p.click('#next');
  p.click('#next');
  ok(p.visible('.screen').join()==='u12','فرم شرطی پس از تکمیل پرسش‌های قابل‌مشاهده به پایان محلی رسید');
  ok(p.doc.querySelector('[data-after-mode="edit"]').style.display==='none'&&p.doc.querySelector('#afterViewNote').style.display!=='none',
    'رفتار پس از ثبت روی «فقط مشاهده» اعمال شد');
  const regs=JSON.parse(store.getItem('nora-regs')||'[]'),row=regs[0];
  ok(row&&row.form==='f-config'&&row.settings.display==='one'&&row.settings.dir==='ltr'&&row.settings.after==='view',
    'شناسه و تنظیمات فرم در رکورد پاسخ محلی حفظ شدند');
  ok(row&&row.ans.some(a=>a.l==='یادداشت خارج از خروجی'&&a.v==='پاسخ خصوصی'&&a.col===false),
    'پاسخ خصوصی در پروندهٔ محلی می‌ماند و پرچم خروجی آن حفظ می‌شود');
  const csv=p.window.NORA_UI.regsCsv(regs,{money:false});
  ok(!csv.includes('یادداشت خارج از خروجی')&&!csv.includes('پاسخ خصوصی'),'فیلد خارج از خروجی از CSV محلی حذف شد');
  ok(row&&row.notificationStatus==='not-sent'&&row.paymentStatus==='not-connected',
    'رکورد گزارش، اعلان و پرداخت را صریحاً ارسال‌نشده/وصل‌نشده نشان می‌دهد');

  const b=await load('builder.html',store);
  ok(b.errors.length===0,'گزارش فرم‌ساز بی‌خطا بار شد'+(b.errors.length?': '+b.errors[0]:''));
  ok(b.txt('#infoBox').includes('یک پرسش در هر مرحله')&&b.txt('#infoBox').includes('کد دعوت')&&b.txt('#infoBox').includes('خارج از خروجی اکسل'),
    'گزارش چیدمان یک‌پرسشی، محدودیت و فیلدهای مخفی را از انبار مرکزی نشان می‌دهد');
  ok(b.txt('#answersBox').includes('نمونهٔ محلی · نه پاسخ سرور')
      &&b.txt('#answersBox').includes('پاسخ‌های محلی در این تب و گزارش‌ها نمایش داده نمی‌شوند')
      &&!b.txt('#answersBox').includes('مریم پیکربندی')&&!b.doc.querySelector('#answersBox [data-person]'),
    'پاسخ‌های محلی در جدول پاسخ سروری نمایش داده نمی‌شوند و با دادهٔ واقعی مخلوط نمی‌شوند');
  b.click('[data-go="fReports"]');
  ok(b.txt('#formReportList').includes('نمونهٔ مرورگر · در آمار واقعی محاسبه نمی‌شود')
      &&!b.txt('#formReportSummary').includes('پاسخ محلی')&&b.txt('#formReportSummary').includes('۰'),
    'گزارش آماری فقط endpoint واقعی را می‌شمارد و نمونهٔ محلی را با برچسب جدا نگه می‌دارد');
  const forms=JSON.parse(store.getItem('nora-forms')||'[]');
  forms.push({id:'f-cancel',name:'فرم پایان نمونه',need:'reg',after:'cancel',fields:[{id:'only',t:'text',l:'پاسخ',req:true}],fin:[]});
  store.setItem('nora-forms',JSON.stringify(forms));
  const cancel=await load('form.html',store,'?fid=f-cancel');
  cancel.click('#next');cancel.set('#qa0','پاسخ نمونه');cancel.click('#next');
  ok(cancel.visible('.screen').join()==='u14'&&JSON.parse(store.getItem('nora-regs')||'[]').some(r=>r.form==='f-cancel'),
    'رفتار «پایان پیش‌نمایش» پاسخ محلی را ذخیره می‌کند و سپس به صفحهٔ پایان می‌رود');
}

/* ── ۴الف) همهٔ عملگرهای شرط نمایش و ارجاع پنهان ── */
{
  console.log('\n── همهٔ عملگرهای شرط نمایش ──');
  const operators=['eq','ne','contains','ncontains','starts','nstarts','ends','nends','gt','gte','lt','lte','empty','nempty'];
  const conditionValues={eq:'Alpha',ne:'beta',contains:'LP',ncontains:'GAMMA',starts:'Al',nstarts:'Al',ends:'HA',nends:'HA',
    gt:0,gte:8,lt:'10',lte:8,empty:'',nempty:''};
  const fields=[{id:'source',t:'text',l:'پاسخ مرجع',req:false},{id:'source-number',t:'number',l:'عدد مرجع',req:false},
    ...operators.map(op=>({id:'condition-'+op,t:'text',l:'شرط '+op,req:false,condField:['gt','gte','lt','lte'].includes(op)?'source-number':'source',condOp:op,condVal:conditionValues[op]})),
    {id:'condition-ncontains-match',t:'text',l:'عدم شامل مورد هم‌حروف',req:false,condField:'source',condOp:'ncontains',condVal:'LP'},
    {id:'condition-case-eq',t:'text',l:'برابری حساس به بزرگی حروف',req:false,condField:'source',condOp:'eq',condVal:'alpha'},
    {id:'condition-case-ne',t:'text',l:'نابرابری حساس به بزرگی حروف',req:false,condField:'source',condOp:'ne',condVal:'alpha'},
    {id:'condition-decimal',t:'text',l:'آستانهٔ اعشاری',req:false,condField:'source-number',condOp:'gt',condVal:'١٫٥'},
    {id:'numeric-empty',t:'text',l:'عدد خالی',req:false,condField:'source-number',condOp:'empty',condVal:''},
    {id:'numeric-nempty',t:'text',l:'عدد غیرخالی',req:false,condField:'source-number',condOp:'nempty',condVal:''},
    {id:'invalid-legacy-op',t:'text',l:'عملگر legacy نامعتبر',req:false,condField:'source',condOp:'future-op',condVal:'Alpha'},
    {id:'invalid-group-logic',t:'text',l:'منطق گروه نامعتبر',req:false,conditionLogic:'xor',conditions:[
      {field:'source',op:'eq',value:'Alpha'},{field:'source',op:'eq',value:'Alpha'}]},
    {id:'too-many-rules',t:'text',l:'گروه بیش از حد',req:false,conditions:Array.from({length:11},()=>({field:'source',op:'eq',value:'Alpha'}))},
    {id:'hidden-root',t:'text',l:'مرجع پنهان',req:false,condField:'source',condOp:'eq',condVal:'open'},
    {id:'hidden-child',t:'text',l:'وابسته به مرجع پنهان',req:false,condField:'hidden-root',condOp:'empty',condVal:''}];
  const store=makeStore({'nora-forms':JSON.stringify([{id:'f-condition-ops',name:'آزمون شرط‌ها',model:'questionnaire',need:'other',
    display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-condition-ops&kind=other');
  ok(p.errors.length===0,'فرم آزمون عملگرها بی‌خطا بار شد'+(p.errors.length?': '+p.errors[0]:''));
  const visible=id=>p.window.__NORA_FORM_PREVIEW.visibleFields.find(field=>field.id===id)?.visible===true;
  const matches=expected=>operators.every(op=>visible('condition-'+op)===expected[op]);
  const expectedWhenEmpty={eq:false,ne:false,contains:false,ncontains:false,starts:false,nstarts:false,ends:false,nends:false,
    gt:false,gte:false,lt:false,lte:false,empty:true,nempty:false};
  ok(matches(expectedWhenEmpty)&&visible('numeric-empty')&&!visible('numeric-nempty')
      &&!visible('condition-case-eq')&&!visible('condition-case-ne'),
    'پاسخ خالی فقط empty را برآورده می‌کند و برابری/نابرابری مقداردار را نه');
  p.set('#qa0','Alpha');
  ok(matches({eq:true,ne:true,contains:true,ncontains:true,starts:true,nstarts:false,ends:true,nends:false,
    gt:false,gte:false,lt:false,lte:false,empty:false,nempty:true})&&!visible('condition-ncontains-match')
      &&!visible('condition-case-eq')&&visible('condition-case-ne'),
    'برابری/نابرابری متنی دقیق و عملگرهای شامل/شروع/پایانِ بی‌حساسیت به بزرگی حروف ارزیابی شدند');
  ok(!visible('condition-decimal')&&!visible('invalid-legacy-op')&&!visible('invalid-group-logic')&&!visible('too-many-rules'),
    'عملگر legacy ناشناخته، منطق گروه نامعتبر و بیش از ۱۰ قاعده در پیش‌نمایش fail-closed می‌شوند');
  p.set('#qa1','0');
  ok(!visible('numeric-empty')&&visible('numeric-nempty')&&!visible('condition-decimal'),
    'عدد صفر غیرخالی است و در empty با پاسخ عددیِ خالی اشتباه نمی‌شود');
  p.set('#qa1','8');
  ok(matches({eq:true,ne:true,contains:true,ncontains:true,starts:true,nstarts:false,ends:true,nends:false,
    gt:true,gte:true,lt:true,lte:true,empty:false,nempty:true})&&!visible('condition-ncontains-match')&&visible('condition-decimal')
      &&!visible('numeric-empty')&&visible('numeric-nempty'),
    'مقایسهٔ عددی، آستانهٔ صفر و رقم/ممیز عربی‌هندی و عملگرهای دوطرف ncontains ارزیابی شدند');
  p.set('#qa0','beta');
  ok(matches({eq:false,ne:false,contains:false,ncontains:true,starts:false,nstarts:true,ends:false,nends:true,
    gt:true,gte:true,lt:true,lte:true,empty:false,nempty:true})&&visible('condition-ncontains-match')
      &&!visible('condition-case-eq')&&visible('condition-case-ne'),
    'شرط ne فقط وقتی پاسخ با مقدار مرجع برابر نیست برقرار می‌شود');
  p.set('#qa0','   ');
  ok(matches({eq:false,ne:false,contains:false,ncontains:false,starts:false,nstarts:false,ends:false,nends:false,
    gt:true,gte:true,lt:true,lte:true,empty:true,nempty:false})&&!visible('condition-ncontains-match')
      &&!visible('condition-case-eq')&&!visible('condition-case-ne'),
    'empty و nempty پاسخ فاصله‌ای را trim می‌کنند و هیچ عملگر مقداردار پاسخ خالی را نمی‌پذیرد');
  ok(!visible('hidden-root')&&!visible('hidden-child'),
    'فیلد وابسته به مرجع پنهان، صرفاً به‌خاطر empty نمایش داده نمی‌شود');
  p.set('#qa0','open');
  ok(visible('hidden-root')&&visible('hidden-child'),
    'empty پس از نمایان‌شدن مرجع، پاسخ خالی همان مرجع را درست ارزیابی می‌کند');
  ok(operators.every(op=>p.window.__REG.q.find(field=>field.id==='condition-'+op)?.condOp===op),
    'نرمال‌سازی فرم هر چهارده عملگر را بدون جایگزینی به eq نگه می‌دارد');
}

/* ── ۴ب) مقایسهٔ تاریخ و زمان در پیش‌نمایش ── */
{
  console.log('\n── شرط‌های تاریخ و زمان ──');
  const fields=[
    {id:'date-source',t:'date',l:'تاریخ مرجع',req:false},
    {id:'time-source',t:'time',l:'زمان مرجع',req:false},
    {id:'datetime-source',t:'datetime',l:'تاریخ و زمان مرجع',req:false},
    {id:'date-later',t:'text',l:'تاریخ بعدی',req:false,conditions:[{field:'date-source',op:'gt',value:'۱۴۰۵/۰۶/۳۱'}]},
    {id:'time-earlier',t:'text',l:'زمان پیش از حد',req:false,conditions:[{field:'time-source',op:'lt',value:'۱۸:۴۵'}]},
    {id:'datetime-equal',t:'text',l:'برابری تاریخ و زمان',req:false,conditions:[{field:'datetime-source',op:'eq',value:'۱۴۰۵/۰۷/۰۱ ۱۸:۳۰'}]},
    {id:'datetime-after',t:'text',l:'پس از تاریخ و زمان',req:false,conditions:[{field:'datetime-source',op:'gt',value:'۱۴۰۵/۰۷/۰۱ ۱۸:۳۰'}]},
    {id:'invalid-leap-rule',t:'text',l:'قاعدهٔ تاریخ نامعتبر قدیمی',req:false,conditions:[{field:'date-source',op:'eq',value:'۱۴۰۵/۱۲/۳۰'}]},
    {id:'invalid-time-rule',t:'text',l:'قاعدهٔ ساعت نامعتبر قدیمی',req:false,conditions:[{field:'datetime-source',op:'eq',value:'۱۴۰۵/۰۷/۰۱ ۱۸:۶۰'}]},
  ];
  const store=makeStore({'nora-forms':JSON.stringify([{id:'f-condition-temporal',name:'آزمون تاریخ و زمان',model:'questionnaire',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-condition-temporal&kind=other');
  const visible=id=>p.window.__NORA_FORM_PREVIEW.visibleFields.find(field=>field.id===id)?.visible===true;
  const setPicker=(index,values)=>{
    const box=p.doc.querySelector('[data-qpick][data-i="'+index+'"]');
    for(const selector of ['.pk1','.pk2','.pk3','.pk4','.pk5'])if(Object.hasOwn(values,selector)){
      const control=box.querySelector(selector);control.value=values[selector];
      control.dispatchEvent(new p.window.Event('change',{bubbles:true}));
    }
  };
  ok(p.errors.length===0&&!visible('date-later')&&!visible('time-earlier')&&!visible('datetime-equal')&&!visible('datetime-after')
      &&!visible('invalid-leap-rule')&&!visible('invalid-time-rule'),
    'قاعدهٔ تاریخ/زمان تا ثبت پاسخ همان مرجع برقرار نمی‌شود');
  setPicker(0,{'.pk1':'1405','.pk2':'7','.pk3':'1'});
  setPicker(1,{'.pk4':'18','.pk5':'30'});
  setPicker(2,{'.pk1':'1405','.pk2':'7','.pk3':'1','.pk4':'18','.pk5':'30'});
  ok(visible('date-later')&&visible('time-earlier')&&visible('datetime-equal')&&!visible('datetime-after')
      &&!visible('invalid-leap-rule')&&!visible('invalid-time-rule'),
    'تاریخ، ساعت و تاریخ‌وساعت با مقایسهٔ ترتیبی و برابرشدنِ مقدار دقیق سنجیده شدند');
}

/* ── ۴ب۰) انتخاب تاریخ و ساعت شمسی، بدون پیش‌فرض گمراه‌کننده ── */
{
  console.log('\n── انتخاب تاریخ و ساعت شمسی ──');
  const fields=[{id:'date-required',t:'date',l:'تاریخ موردنظر',req:true},{id:'time-optional',t:'time',l:'ساعت',req:false},
      {id:'datetime-optional',t:'datetime',l:'تاریخ و ساعت',req:false}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-jalali-picker',name:'آزمون تاریخ شمسی',model:'questionnaire',need:'other',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-jalali-picker&kind=other'),dateBox=p.doc.querySelector('[data-qpick][data-i="0"]'),
    timeBox=p.doc.querySelector('[data-qpick][data-i="1"]'),datetimeBox=p.doc.querySelector('[data-qpick][data-i="2"]');
  const change=(box,selector,value)=>{const control=box.querySelector(selector);control.value=String(value);control.dispatchEvent(new p.window.Event('change',{bubbles:true}));};
  ok(p.errors.length===0&&dateBox.querySelector('.pk1').value===''&&dateBox.querySelector('.pk1').options[0].value===''&&
      dateBox.querySelector('.pk2').disabled&&dateBox.querySelector('.pk3').disabled&&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'تاریخ اجباری بدون انتخاب کاربر خالی می‌ماند؛ ماه و روز تا انتخاب گام قبلی قفل‌اند');
  const currentYear=Number(p.window.eval('CURRENT_JY')),
    dateYears=[...dateBox.querySelector('.pk1').options].slice(1).map(option=>Number(option.value)),
    datetimeYears=[...datetimeBox.querySelector('.pk1').options].slice(1).map(option=>Number(option.value)),
    datePast=dateYears.slice(0,126),dateFuture=dateYears.slice(126),datetimeFuture=datetimeYears.slice(0,96),datetimePast=datetimeYears.slice(96);
  ok(dateYears.length===221&&datePast[0]===currentYear&&datePast.at(-1)===currentYear-125
      &&datePast.every((year,i)=>i===0||datePast[i-1]===year+1)
      &&dateFuture[0]===currentYear+1&&dateFuture.at(-1)===currentYear+95
      &&dateFuture.every((year,i)=>i===0||dateFuture[i-1]+1===year)
      &&datetimeFuture[0]===currentYear&&datetimeFuture.at(-1)===currentYear+95
      &&datetimeFuture.every((year,i)=>i===0||datetimeFuture[i-1]+1===year)
      &&datetimePast[0]===currentYear-1&&datetimePast.at(-1)===currentYear-125
      &&datetimePast.every((year,i)=>i===0||datetimePast[i-1]===year+1),
    'سال‌های تاریخ تولد پیوسته از جدید به قدیم‌اند؛ تاریخ‌وساعت هم سال جاری و آینده را پیوسته نشان می‌دهد');
  change(dateBox,'.pk1','1403');
  ok(!dateBox.querySelector('.pk2').disabled&&dateBox.querySelector('.pk3').disabled
      &&p.window.__NORA_FORM_PREVIEW.validate().includes('تاریخ شمسی کامل'),
    'انتخاب سال، فهرست ماه را باز می‌کند؛ تاریخ ناقص تا انتخاب روز معتبر نمی‌شود');
  change(dateBox,'.pk2','12');
  ok([...dateBox.querySelector('.pk3').options].some(option=>option.value==='30'),
    'اسفندِ سال کبیسه ۱۴۰۳ روز سی‌ام دارد');
  change(dateBox,'.pk3','30');
  ok(p.doc.querySelector('#qa0').value==='۱۴۰۳/۱۲/۳۰'&&p.window.__NORA_FORM_PREVIEW.validate()===null,
    'تاریخ کامل به رقم فارسی در پیش‌نویس محلی ثبت و معتبر شناخته می‌شود');
  change(dateBox,'.pk1','1404');
  ok(dateBox.querySelector('.pk3').value===''&&![...dateBox.querySelector('.pk3').options].some(option=>option.value==='30'),
    'با تغییر به سال غیرکبیسه روز سی‌ام بی‌صدا به تاریخ دیگری تبدیل نمی‌شود');
  change(dateBox,'.pk3','29');
  ok(p.doc.querySelector('#qa0').value==='۱۴۰۴/۱۲/۲۹'&&p.window.__NORA_FORM_PREVIEW.validate()===null,
    'تاریخ غیرکبیسه تا آخرین روز معتبر پذیرفته می‌شود');
  ok(p.doc.querySelector('#pkBirth .pk1').value==='1370'&&p.doc.querySelector('#pkBirth .pk3').value==='12'
      &&p.window.NORA_UI.jalaliDaysInMonth(1399,12)===30&&p.window.NORA_UI.jalaliDaysInMonth(1408,12)===30
      &&p.window.NORA_UI.jalaliDaysInMonth(1404,12)===29,
    'تاریخ تولد پیش‌فرض ۱۳۷۰ حفظ می‌شود و محاسبهٔ اسفند برای سال‌های کبیسه و عادی دقیق است');
  const hour=timeBox.querySelector('.pk4'),minute=timeBox.querySelector('.pk5');
  ok(hour.value===''&&minute.value===''&&minute.disabled&&minute.options.length===61,
    'ساعت پیش‌فرض ندارد و فهرست دقیقه‌ها همهٔ ۶۰ دقیقه را پوشش می‌دهد');
  change(timeBox,'.pk4','0');change(timeBox,'.pk5','37');
  ok(p.doc.querySelector('#qa1').value==='۰۰:۳۷'&&p.window.__NORA_FORM_PREVIEW.validate()===null,
    'نیمه‌شب و دقیقهٔ دلخواه بدون تایپ ثبت می‌شوند');
  ok(datetimeBox.querySelector('.pk1').value===''&&datetimeBox.querySelector('.pk4').value===''&&datetimeBox.querySelector('.pk5').disabled,
    'تاریخ‌وساعت هم هیچ پیش‌فرضی ندارد و دقیقه پیش از انتخاب ساعت قفل است');
  for(const [selector,value] of [['.pk1','1403'],['.pk2','12'],['.pk3','30'],['.pk4','18'],['.pk5','47']])change(datetimeBox,selector,value);
  ok(p.doc.querySelector('#qa2').value==='۱۴۰۳/۱۲/۳۰ ساعت ۱۸:۴۷'&&p.window.__NORA_FORM_PREVIEW.validate()===null,
    'تاریخ‌وساعت شمسی با دقیقهٔ دقیق و رقم فارسی ثبت می‌شود');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'۱۴۰۳/۱۲/۳۰',qa1:'۰۰:۳۷',qa2:'۱۴۰۳/۱۲/۳۰ ساعت ۱۸:۴۷'},picks:{},guests:[],fin:[],picked:[]});
  ok(dateBox.querySelector('.pk1').value==='1403'&&dateBox.querySelector('.pk2').value==='12'
      &&dateBox.querySelector('.pk3').value==='30'&&hour.value==='0'&&minute.value==='37'
      &&datetimeBox.querySelector('.pk4').value==='18'&&datetimeBox.querySelector('.pk5').value==='47',
    'پیش‌نویس تاریخ، ساعت و تاریخ‌وساعت را پس از بازگشت دقیق بازیابی می‌کند');
  p.window.restoreDraft({cur:'qall',inputs:{qa2:'۱۴۰۳/۱۲/۳۰ ۱۸:۴۷'},picks:{},guests:[],fin:[],picked:[]});
  ok(datetimeBox.querySelector('.pk1').value==='1403'&&datetimeBox.querySelector('.pk3').value==='30'
      &&datetimeBox.querySelector('.pk4').value==='18'&&datetimeBox.querySelector('.pk5').value==='47',
    'پیش‌نویس قدیمی با فاصلهٔ ساده میان تاریخ و ساعت هم بازیابی می‌شود');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'۱۴۰۴/۱۲/۳۰',qa1:'۱۸:۶۰',qa2:'۱۴۰۴/۱۲/۳۰ ساعت ۱۸:۶۰'},picks:{},guests:[],fin:[],picked:[]});
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('تاریخ شمسی کامل')&&dateBox.querySelector('.pk3').value==='',
    'تاریخ نامعتبر و روزی که در فهرست وجود ندارد هنگام بازیابی قابل تأیید نیست');
  ok(p.network.length===0,'انتخاب تاریخ و ساعت فقط در پیش‌نویس محلی می‌ماند');
}

/* ── کیفیت‌سنجی محلی و آفلاین پاسخ‌ها ── */
{
  console.log('\n── کیفیت‌سنجی آفلاین پاسخ‌ها ──');
  const fields=[
    {id:'full-name',t:'text',l:'نام کامل',req:true},
    {id:'birth-date',t:'date',l:'تاریخ تولد',req:true},
    {id:'event-date',t:'date',l:'تاریخ رویداد',req:false},
    {id:'university',t:'uni',l:'نام دانشگاه',req:false},
    {id:'comment',t:'text',l:'توضیح آزاد',req:false},
  ],store=makeStore({'nora-forms':JSON.stringify([{id:'f-quality-local',name:'کیفیت‌سنجی محلی',model:'questionnaire',need:'other',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-quality-local&kind=other'),quality=p.window.NORA_FORM_QUALITY;
  ok(p.errors.length===0&&quality?.version==='nora-quality-2',
    'موتور قواعد کیفیت به‌صورت فایل محلی بارگیری می‌شود و نسخهٔ آن مشخص است');
  const repeated=quality.analyze(fields[0],'رررر');
  ok(repeated.some(issue=>issue.code==='suspicious_repeated_name'&&issue.severity==='error'),
    'نام متشکل از تکرار یک حرف به‌عنوان خطای قابل‌اقدام شناسایی می‌شود');
  ok(quality.analyze(fields[0],'لیلا رررر').some(issue=>issue.code==='suspicious_repeated_name'),
    'واژهٔ متشکل از تکرار یک حرف در کنار نام واقعی هم شناسایی می‌شود');
  ok(quality.analyze(fields[0],'Test').some(issue=>issue.code==='placeholder_name'),
    'نام نمونهٔ آشکار مانند Test پیش از ثبت نهایی شناسایی می‌شود');
  const keyboardAnswer=quality.analyze(fields[4],'poiuytrewq');
  ok(keyboardAnswer.some(issue=>issue.code==='keyboard_mash'&&issue.severity==='warning'),
    'الگوی صفحه‌کلید در فیلد متنی عمومی هم به‌عنوان هشدار شناسایی می‌شود');
  const repeatedNumber=quality.analyze({id:'national-id',t:'nid',l:'کد ملی'},'۱۱۱۱۱۱۱۱۱۱');
  ok(repeatedNumber.some(issue=>issue.code==='repetitive_input_pattern'&&issue.severity==='warning')
      &&!repeatedNumber.some(issue=>issue.severity==='error'),
    'الگوی عددی تکراری در ورودی ساختاریافته هشدار می‌دهد اما به‌تنهایی آن را رد نمی‌کند');
  ok(quality.analyze({id:'choice-q',t:'choice',l:'گزینه'},'Test').length===0
      &&quality.analyze(fields[3],'تهران · دانشگاه خارج از فهرست').length===0,
    'گزینهٔ فرم و نام دستی دانشگاه بی‌دلیل با قواعد متن عمومی رد نمی‌شوند');
  p.input('#qa0','رررر');
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('تکرار یک حرف'),
    'اعتبارسنجی فرم پیش از ادامه، نام تکراری را با راه اصلاح روشن متوقف می‌کند');
  p.input('#qa0','لیلا');
  const today=quality.currentJalaliDate(),tomorrowYear=today[0]+1;
  const chooseDate=(index,date)=>{
    const prefix='[data-qpick][data-i="'+index+'"]';
    p.set(prefix+' .pk1',String(date[0]));p.set(prefix+' .pk2',String(date[1]));p.set(prefix+' .pk3',String(date[2]));
  };
  chooseDate(1,today);
  ok(quality.analyze(fields[1],p.doc.querySelector('#qa1').value).some(issue=>issue.code==='birth_date_is_today'
      &&issue.severity==='warning'&&issue.requiresConfirmation===true)
      &&p.doc.querySelector('#qquality-1 button[data-quality-confirm]')!==null,
    'تولدِ برابر امروز هشدار می‌دهد و برای نوزاد واقعی، تأیید صریح و قابل دسترس دارد');
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('دکمهٔ زیر تأیید'),
    'ثبت یا ادامه بدون تأیید دوبارهٔ تاریخ تولد امروز مسدود می‌شود');
  p.click('#qquality-1 [data-quality-confirm]');
  ok(p.window.__NORA_FORM_PREVIEW.validate()===null&&p.txt('#qquality-1').includes('تأیید شد'),
    'با تأیید پاسخ‌دهنده، تاریخ تولد امروز پذیرفته می‌شود و وضعیت تأیید دیده می‌شود');
  chooseDate(1,[tomorrowYear,1,1]);
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('نمی‌تواند در آینده'),
    'تاریخ تولد آینده با همان منطق محلی رد می‌شود');
  chooseDate(1,[today[0]-1,1,1]);chooseDate(2,[tomorrowYear,1,1]);
  ok(p.window.__NORA_FORM_PREVIEW.validate()===null,
    'تاریخ آیندهٔ عمومی/رویداد محدود نمی‌شود؛ قاعده فقط به فیلد تولد اعمال می‌شود');
  const unknownUniversity=quality.analyze(fields[3],'تهران · دانشگاه خارج از فهرست');
  ok(unknownUniversity.length===0,
    'نام دانشگاه خارج از snapshot محلی به‌اشتباه نامعتبر نمی‌شود و ورود دستی حفظ می‌شود');
  p.input('#qa4','poiuytrewq');
  ok(p.txt('#qquality-4').includes('صفحه‌کلید')&&p.window.__NORA_FORM_PREVIEW.validate()===null,
    'هشدار عمومی در خود فیلد نمایش داده می‌شود و پاسخ مشکوکِ غیرقطعی را بی‌اجازه مسدود نمی‌کند');
  ok(p.network.length===0,
    'تحلیل نام، تاریخ و دانشگاه هیچ درخواست بیرونی یا سرویس هوش مصنوعی ایجاد نمی‌کند');
}

/* ── ۴ب۰۱) امتیاز ستاره‌ای، دسترس‌پذیر و بدون مقدار پیش‌فرض ── */
{
  console.log('\n── امتیاز ستاره‌ای ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.model='survey';S.need='survey';S.fields=[];addField('rating');editField(S.fields[0].id)");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='rating'&&S.fields[0].scoreOn===true")
      &&builder.doc.querySelector('#fdScoreBox').style.display==='block'
      &&builder.doc.querySelector('#fdScoreOn').classList.contains('on')
      &&builder.doc.querySelector('#fdScoreHint').textContent.includes('ستاره‌ها از ۱ تا ۵'),
    'سازنده فیلد ستاره‌ای آماده می‌سازد و امتیازدهیِ پرسشنامه را روشن و توضیح‌داده‌شده نشان می‌دهد');
  const fields=[{id:'rating-source',t:'rating',l:'ارزیابی',req:true},
      {id:'rating-followup',t:'text',l:'توضیح تکمیلی',req:false,conditions:[{field:'rating-source',op:'gte',value:'4'}],conditionLogic:'all'}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-rating',name:'فرم امتیاز ستاره‌ای',model:'survey',need:'survey',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-rating&kind=survey'),group=p.doc.querySelector('[data-qrate="0"]'),stars=[...group.querySelectorAll('[role="radio"]')],clear=group.querySelector('[data-qrate-clear]');
  const visible=id=>p.window.__NORA_FORM_PREVIEW.visibleFields.find(field=>field.id===id)?.visible===true;
  ok(p.errors.length===0&&group.getAttribute('role')==='radiogroup'&&stars.length===5
      &&stars.every(star=>star.getAttribute('aria-checked')==='false')&&stars[0].tabIndex===0&&stars.slice(1).every(star=>star.tabIndex===-1)
      &&clear.hidden&&group.dataset.val===''&&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'امتیاز پیش‌فرضی ثبت نمی‌شود؛ پنج ستاره نقش رادیویی، وضعیت دسترس‌پذیر و توقف روی پرسش اجباری دارد');
  p.click('[data-qrate="0"] [data-qv="4"]');
  ok(group.dataset.val==='4'&&p.doc.querySelector('#qa0').value==='۴'&&stars[3].getAttribute('aria-checked')==='true'
      &&stars.filter(star=>star.classList.contains('on')).length===4&&!clear.hidden&&visible('rating-followup'),
    'انتخاب چهار ستاره فقط یک پاسخ عددیِ روشن ثبت می‌کند و شرط عددیِ امتیاز را فعال می‌کند');
  stars[3].dispatchEvent(new p.window.KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true,cancelable:true}));
  ok(group.dataset.val==='3'&&stars[2].getAttribute('aria-checked')==='true'&&!visible('rating-followup'),
    'کلیدهای جهت‌دار امتیاز را عوض می‌کنند و شرط وابسته هم‌زمان دوباره سنجیده می‌شود');
  stars[2].dispatchEvent(new p.window.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true,cancelable:true}));
  stars[3].dispatchEvent(new p.window.KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));
  ok(group.dataset.val==='4'&&stars[3].getAttribute('aria-checked')==='true',
    'فلش و Enter انتخاب ستاره را برای صفحه‌کلید هم کامل می‌کنند');
  p.click('[data-qrate-clear="0"]');
  ok(group.dataset.val===''&&clear.hidden&&stars.every(star=>star.getAttribute('aria-checked')==='false')
      &&p.doc.querySelector('#qa0').value===''&&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'دکمهٔ روشنِ پاک‌کردن، پاسخ را واقعاً خالی می‌کند و اجباری‌بودن را دور نمی‌زند');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'۵'},picks:{},guests:[],fin:[],picked:[]});
  ok(group.dataset.val==='5'&&stars[4].getAttribute('aria-checked')==='true'&&!clear.hidden
      &&p.window.__NORA_FORM_PREVIEW.validate()===null,
    'پیش‌نویس امتیاز و وضعیت رادیویی را درست بازیابی می‌کند');
  ok(p.window.__NORA_FORM_PREVIEW.finish()===true&&p.txt('#regSum').includes('۵ ستاره')
      &&p.doc.querySelector('#regSum img')===null,
    'خلاصه پاسخ را به‌شکل «۵ ستاره» و به‌صورت متن امن نشان می‌دهد');
  ok(p.network.length===0,'امتیاز ستاره‌ای هیچ پیام یا داده‌ای بیرون نمی‌فرستد');
}

/* ── ۴ب۰۲) بازهٔ لغزندهٔ ۰ تا ۱۰ بدون ثبت پیش‌فرض ── */
{
  console.log('\n── بازهٔ لغزندهٔ ۰ تا ۱۰ ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.model='survey';S.need='survey';S.fields=[];addField('scale');editField(S.fields[0].id)");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='scale'&&S.fields[0].scoreOn===true")
      &&builder.doc.querySelector('#fdScoreBox').style.display==='block'
      &&builder.doc.querySelector('#fdScoreOn').classList.contains('on')
      &&builder.doc.querySelector('#fdScoreHint').textContent.includes('بازهٔ ۰ تا ۱۰'),
    'سازنده بازهٔ صفر تا ده را آماده می‌کند و امتیاز کلی پرسشنامه را روشن نشان می‌دهد');
  const fields=[{id:'scale-source',t:'scale',l:'ارزیابی از صفر تا ده',req:true,min:0,max:10},
      {id:'scale-followup',t:'text',l:'توضیح امتیاز بالا',req:false,conditions:[{field:'scale-source',op:'gte',value:'8'}],conditionLogic:'all'}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-scale',name:'فرم بازهٔ لغزنده',model:'survey',need:'survey',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-scale&kind=survey'),range=p.doc.querySelector('#qa0'),valueLabel=p.doc.querySelector('#qa0v'),clear=p.doc.querySelector('[data-qrange-clear="0"]');
  const visible=id=>p.window.__NORA_FORM_PREVIEW.visibleFields.find(field=>field.id===id)?.visible===true;
  ok(p.errors.length===0&&range.type==='range'&&range.min==='0'&&range.max==='10'&&range.step==='1'
      &&range.value==='0'&&range.dataset.touched!=='1'&&valueLabel.textContent==='پاسخی ثبت نشده'
      &&range.getAttribute('aria-valuetext').includes('پاسخی ثبت نشده')&&clear.hidden
      &&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'نوار از صفر شروع می‌کند اما مقدار صفر را پیشاپیش پاسخ حساب نمی‌کند؛ دامنه و راهنمای دسترس‌پذیر روشن است');
  range.dispatchEvent(new p.window.Event('pointerdown',{bubbles:true}));
  ok(range.dataset.touched==='1'&&p.doc.querySelector('#qa0').value==='0'&&valueLabel.textContent==='۰ از ۱۰'
      &&!clear.hidden&&p.window.__NORA_FORM_PREVIEW.validate()===null,
    'با لمس همان نقطهٔ صفر هم پاسخ عمدی ثبت می‌شود؛ مقدار صفر با پاسخ خالی اشتباه نمی‌شود');
  p.input('#qa0','7');
  ok(p.doc.querySelector('#qa0').value==='7'&&valueLabel.textContent==='۷ از ۱۰'
      &&range.getAttribute('aria-valuetext')==='۷ از ۱۰'&&!visible('scale-followup'),
    'تغییر نوار، عدد فارسی و توضیح دسترس‌پذیر را به‌روز می‌کند و شرط ۸ را زودتر فعال نمی‌کند');
  p.input('#qa0','8');
  ok(visible('scale-followup')&&p.window.__NORA_FORM_PREVIEW.validate()===null,
    'مقایسهٔ عددیِ شرط در مرز ۸ به‌درستی برقرار می‌شود');
  p.click('[data-qrange-clear="0"]');
  ok(range.value==='0'&&range.dataset.touched!=='1'&&valueLabel.textContent==='پاسخی ثبت نشده'
      &&clear.hidden&&!visible('scale-followup')&&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'پاک‌کردن نوار پاسخ را خالی می‌کند، شرط را می‌بندد و اجباری‌بودن را حفظ می‌کند');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'۸',qa1:''},picks:{},guests:[],fin:[],picked:[]});
  ok(range.value==='8'&&range.dataset.touched==='1'&&valueLabel.textContent==='۸ از ۱۰'
      &&visible('scale-followup')&&p.window.__NORA_FORM_PREVIEW.validate()===null,
    'پیش‌نویس مقدار بازه، متن فارسی و شرط وابسته را درست بازیابی می‌کند');
  ok(p.window.__NORA_FORM_PREVIEW.finish()===true&&p.txt('#regSum').includes('۸')
      &&p.network.length===0,'مقدار انتخاب‌شده در خلاصهٔ محلی می‌ماند و هیچ درخواست بیرونی نمی‌فرستد');
}

/* ── ۴ب۰۳) نوار لغزندهٔ نمایشی به‌جای نمودار ساختگی ── */
{
  console.log('\n── نوار لغزندهٔ جایگزین نمودار ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.model='survey';S.need='survey';S.fields=[];addField('bars');editField(S.fields[0].id)");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='bars'&&S.fields[0].scoreOn===true")
      &&builder.doc.querySelector('#fdStruct').textContent.includes('نمودار وصل نیست')
      &&builder.doc.querySelector('#fdHelp').value.includes('نمودار یا تحلیل تصویری وصل نیست')
      &&builder.doc.querySelector('#fdScoreBox').style.display==='block',
    'سازنده صریح می‌گوید این نوع فعلاً نوار لغزنده است، نمودار نیست، و امتیازدهی اختیاری دارد');
  const fields=[{id:'bar-scale',t:'bars',l:'میزان رضایت',req:false,min:0,max:10}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-bars',name:'فرم نوار لغزنده',model:'survey',need:'survey',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-bars&kind=survey'),range=p.doc.querySelector('#qa0'),label=p.doc.querySelector('#qa0v'),clear=p.doc.querySelector('[data-qrange-clear="0"]');
  ok(p.errors.length===0&&range.type==='range'&&range.min==='0'&&range.max==='10'
      &&range.dataset.touched!=='1'&&label.textContent==='پاسخی ثبت نشده'&&clear.hidden
      &&p.window.__NORA_FORM_PREVIEW.validate()===null&&!p.doc.querySelector('canvas'),
    'پاسخ‌دهنده نوار واقعیِ قابل‌استفاده می‌بیند؛ فیلد اختیاری با مقدار ساختگی یا نمودار جعلی شروع نمی‌شود');
  p.input('#qa0','10');
  ok(range.value==='10'&&label.textContent==='۱۰ از ۱۰'&&p.doc.querySelector('#qa0').value==='10'
      &&p.window.__NORA_FORM_PREVIEW.validate()===null,
    'لبهٔ بالای بازهٔ نوار درست و بدون تایپ ثبت می‌شود');
  p.click('[data-qrange-clear="0"]');
  ok(range.dataset.touched!=='1'&&label.textContent==='پاسخی ثبت نشده'&&clear.hidden
      &&p.window.__NORA_FORM_PREVIEW.validate()===null,
    'پاسخ اختیاریِ نوار را می‌شود پاک کرد و فرم بدون آن هم معتبر می‌ماند');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'۱۰'},picks:{},guests:[],fin:[],picked:[]});
  ok(range.value==='10'&&range.dataset.touched==='1'&&label.textContent==='۱۰ از ۱۰'
      &&!clear.hidden,'پیش‌نویس مقدار نوار را دوباره بازیابی می‌کند');
  ok(p.network.length===0,'نوار لغزنده داده‌ای به شبکه نمی‌فرستد');
}

/* ── ۴ب۰۴) پذیرش قوانین با کنترل صفحه‌کلید و ثبت محلی ── */
{
  console.log('\n── پذیرش قوانین در پیش‌نمایش ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('terms');editField(S.fields[0].id)");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='terms'&&S.fields[0].req===false")
      &&builder.doc.querySelector('#fdStruct').textContent.includes('پاسخ فقط محلی')
      &&builder.doc.querySelector('#fdHelp').value.includes('پذیرش این پیش‌نمایش فقط محلی است'),
    'سازنده پذیرش را اختیاری می‌سازد و صریح می‌گوید پاسخ محلی است؛ متن قوانین را مالک فرم می‌نویسد');
  const fields=[{id:'terms-required',t:'terms',l:'شرایط شرکت',req:true,help:'متن نمونهٔ شرایط'},
      {id:'terms-optional',t:'terms',l:'دریافت خبرنامه',req:false,help:'عضویت اختیاری است.'}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-terms',name:'فرم پذیرش',model:'datacollect',need:'other',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-terms&kind=other'),required=p.doc.querySelector('[data-qterm="0"]'),optional=p.doc.querySelector('[data-qterm="1"]');
  ok(p.errors.length===0&&required.getAttribute('role')==='checkbox'&&required.getAttribute('aria-checked')==='false'
      &&required.tabIndex===0&&optional.getAttribute('aria-checked')==='false'
      &&p.txt('#qall').includes('رضایت رسمی ثبت نمی‌شود')
      &&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'پاسخ‌دهنده تیک صفحه‌کلیدی و قابل‌دسترسی می‌بیند؛ پذیرش اجباری تا رضایت خالی می‌ماند');
  required.dispatchEvent(new p.window.KeyboardEvent('keydown',{key:' ',bubbles:true,cancelable:true}));
  ok(required.getAttribute('aria-checked')==='true'&&p.doc.querySelector('#qa0').value==='پذیرفتم'
      &&p.window.__NORA_FORM_PREVIEW.validate()===null,
    'Space پذیرش اجباری را روشن می‌کند و وضعیت ARIA و پاسخ همگام می‌شوند');
  required.dispatchEvent(new p.window.KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));
  ok(required.getAttribute('aria-checked')==='false'&&p.doc.querySelector('#qa0').value===''
      &&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'Enter می‌تواند پذیرش را پس بگیرد؛ فیلد اجباری دوباره جلوی ادامه را می‌گیرد');
  p.click('[data-qterm="0"]');p.click('[data-qterm="1"]');
  ok(p.doc.querySelector('#qa0').value==='پذیرفتم'&&p.doc.querySelector('#qa1').value==='پذیرفتم'
      &&required.getAttribute('aria-checked')==='true'&&optional.getAttribute('aria-checked')==='true',
    'پذیرش اجباری و اختیاری هرکدام جداگانه در پاسخ همان فیلد ذخیره می‌شوند');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'',qa1:''},picks:{},guests:[],fin:[],picked:[]});
  ok(required.getAttribute('aria-checked')==='false'&&optional.getAttribute('aria-checked')==='false'
      &&p.doc.querySelector('#qa0').value===''&&p.doc.querySelector('#qa1').value==='',
    'بازیابی پیش‌نویس، نپذیرفتن را هم دقیق نگه می‌دارد و چیزی را از طرف کاربر تیک نمی‌زند');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'پذیرفتم',qa1:'پذیرفتم'},picks:{},guests:[],fin:[],picked:[]});
  ok(required.getAttribute('aria-checked')==='true'&&optional.getAttribute('aria-checked')==='true'
      &&p.window.__NORA_FORM_PREVIEW.finish()===true&&p.txt('#regSum').includes('پذیرفتم')
      &&p.network.length===0,'خلاصه و پاسخ‌های پذیرش فقط در مرورگر می‌مانند؛ رضایت رسمی یا ارسال بیرونی ادعا نمی‌شود');
}

/* ── ۴ب۰۵) نشانی چندخطی، با پیش‌پرکردن صریح از پروفایل ── */
{
  console.log('\n── نشانی چندخطی ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('address')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='address'&&S.fields[0].help.includes('پیش‌پرکردن از پروفایل')")
      &&builder.doc.querySelector('#fdStruct').textContent.includes('نشانی چندخطی'),
    'سازنده توضیح می‌دهد نشانی چندخطی است و پیش‌پرکردن فقط با انتخاب مالک فرم انجام می‌شود');
  const profileAddress='تهران، خیابان انقلاب، کوچهٔ نمونه، پلاک ۱۲',fields=[
      {id:'address-profile',t:'address',l:'نشانی',req:true,prof:true},
      {id:'address-manual',t:'address',l:'نشانی دیگر',req:false,prof:false}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-address',name:'فرم نشانی',model:'datacollect',need:'other',display:'all',fields,fin:[]}]),
      'nora-home-user':JSON.stringify({name:'کاربر نمونه'}),'nora-home-profile':JSON.stringify({address:profileAddress})}),
    p=await load('form.html',store,'?fid=f-address&kind=other'),prefilled=p.doc.querySelector('#qa0'),manual=p.doc.querySelector('#qa1');
  ok(p.errors.length===0&&prefilled.tagName==='TEXTAREA'&&prefilled.rows===3&&prefilled.maxLength===1000
      &&prefilled.value===''&&p.doc.querySelector('#profileAssist').style.display!=='none'
      &&manual.tagName==='TEXTAREA'&&manual.value==='',
    'فیلد نشانی مستقل و خالی می‌ماند تا پاسخ‌دهنده خودش پیشنهاد اختیاری پروفایل را بخواهد');
  p.click('#profilePrefill');
  ok(prefilled.value===profileAddress&&manual.value==='',
    'کلیک صریح فقط فیلد نشانیِ علامت‌خورده را پر می‌کند و فیلد دستی را دست‌نخورده می‌گذارد');
  const unsafe='تهران، خیابان نمونه\nپلاک ۷ <img src=x onerror=alert(1)>';
  p.input('#qa0',unsafe);
  ok(p.doc.querySelector('#qa0').value===unsafe&&p.doc.querySelector('#qa0').maxLength===1000,
    'نشانی چندخطی و طولانی به‌صورت متن ثبت می‌شود؛ محدودیت طول جلوی ورودی بی‌انتها را می‌گیرد');
  p.window.__NORA_FORM_PREVIEW.finish();
  ok(p.txt('#regSum').includes('<img src=x onerror=alert(1)>')&&p.doc.querySelector('#regSum img')===null
      &&p.network.length===0,'متن نشانی در خلاصه escape می‌شود و موقعیت‌یابی یا ارسال بیرونی انجام نمی‌شود');
}

/* ── ۴ب۰۶) موقعیت متنی، نه دسترسی GPS یا نقشه ── */
{
  console.log('\n── موقعیت متنی ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('location')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='location'&&S.fields[0].help.includes('موقعیت‌یابی خودکار وصل نیست')")
      &&builder.doc.querySelector('#fdStruct').textContent.includes('موقعیت‌یابی ندارد'),
    'سازنده روشن می‌گوید این فیلد فقط متنی است و GPS یا نقشه نمی‌خواند');
  const fields=[{id:'place',t:'location',l:'موقعیت',req:true}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-location-text',name:'فرم موقعیت',model:'datacollect',need:'other',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-location-text&kind=other'),input=p.doc.querySelector('#qa0');
  ok(p.errors.length===0&&input.type==='text'&&input.placeholder==='مثلاً تهران، میدان آزادی'
      &&!p.doc.querySelector('iframe, [data-map], [data-geolocation]')
      &&p.txt('#qall').includes('موقعیت‌یابی وصل نیست')
      &&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'فرم ورودی متنِ خالی نشان می‌دهد، درخواست مجوز مکان یا نقشهٔ ساختگی ندارد و پاسخ اجباری را حدس نمی‌زند');
  const value='تهران، میدان آزادی <img src=x onerror=alert(1)>';
  p.input('#qa0',value);
  ok(p.doc.querySelector('#qa0').value===value&&p.window.__NORA_FORM_PREVIEW.validate()===null,
    'نشانیِ متنیِ دلخواه ثبت می‌شود و تگ HTML به اجرا تبدیل نمی‌شود');
  p.window.__NORA_FORM_PREVIEW.finish();
  ok(p.txt('#regSum').includes(value)&&p.doc.querySelector('#regSum img')===null&&p.network.length===0,
    'موقعیت در خلاصه به‌صورت متن امن و فقط در مرورگر می‌ماند');
}

/* ── ۴ب۰۷) فایل تصویر، محلی و با سقف روشن ── */
{
  console.log('\n── فایل تصویر ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('image');editField(S.fields[0].id)");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='image'&&S.fields[0].count===1")
      &&builder.doc.querySelector('#fdCountBox').style.display==='block'
      &&builder.doc.querySelector('#fdAccept').value==='image/*',
    'سازنده برای تصویر، انتخاب فایل را با محدودیت نوع و سقف قابل‌ویرایش آماده می‌کند');
  const fields=[{id:'image-file',t:'image',l:'تصویر نمونه',req:true,count:1,maxSize:1,accept:'image/*'}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-image-file',name:'فرم تصویر',model:'datacollect',need:'other',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-image-file&kind=other'),input=p.doc.querySelector('#qa0');
  const putFiles=files=>{Object.defineProperty(input,'files',{configurable:true,value:files});input.dispatchEvent(new p.window.Event('change',{bubbles:true}))};
  ok(p.errors.length===0&&input.type==='file'&&input.accept==='image/*'&&!input.multiple
      &&input.getAttribute('aria-label')==='تصویر نمونه'&&input.getAttribute('aria-describedby')==='qa0fileNote'
      &&p.txt('#qa0fileNote').includes('تصویر ارسال نمی‌شود')
      &&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'ورودی تصویر نام دسترس‌پذیر دارد، پاسخ خالی اجباری است و پیش‌نمایش وعدهٔ بارگذاری یا بررسی محتوا نمی‌دهد');
  const maliciousName='<img src=x onerror=alert(1)>.png';
  putFiles([{name:maliciousName,size:512,type:'image/png'}]);
  ok(p.window.__NORA_FORM_PREVIEW.validate()===null&&input.files.length===1,
    'فایل تصویرِ زیر سقف و با نوع سازگار در پاسخ محلی پذیرفته می‌شود');
  putFiles([{name:'not-an-image.txt',size:512,type:'text/plain'}]);
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('قالب‌های مجاز'),
    'انتخابی که نوع اعلام‌شده‌اش با تصویر سازگار نیست در پیش‌نمایش رد می‌شود');
  putFiles([{name:'large.png',size:1024*1024+1,type:'image/png'}]);
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('حجم هر فایل'),
    'فایل بزرگ‌تر از سقف یک مگابایت پذیرفته نمی‌شود');
  putFiles([{name:'one.png',size:10,type:'image/png'},{name:'two.png',size:10,type:'image/png'}]);
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('حداکثر ۱ فایل'),
    'تزریق بیش از یک فایل هم با وجود محدودیت مرورگر در منطق فرم رد می‌شود');
  putFiles([{name:maliciousName,size:512,type:'image/png'}]);
  p.window.__NORA_FORM_PREVIEW.finish();
  ok(p.txt('#regSum').includes(maliciousName)&&p.doc.querySelector('#regSum img')===null,
    'نام فایل ناامن هنگام نمایش escape می‌شود و فقط نام فایل وارد خلاصه می‌شود');
  putFiles([]);p.window.restoreDraft({cur:'qall',inputs:{qa0:maliciousName},picks:{},guests:[],fin:[],picked:[]});
  ok(input.files.length===0&&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'بازیابی پیش‌نویس فایل را دوباره بارگذاری یا جعل نمی‌کند؛ کاربر باید آن را دوباره انتخاب کند');
  ok(p.network.length===0,'فایل تصویر از مرورگر بارگذاری یا ارسال نمی‌شود');
}

/* ── ۴ب۰۸) فایل PDF یا JPG با تعداد، حجم و نوع قابل‌تنظیم ── */
{
  console.log('\n── فایل PDF یا JPG ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('file');editField(S.fields[0].id);window.fileAcceptDefault=$('#fdAccept').value;$('#fdAccept').value='application/pdf,image/jpeg';$('#fdCount').value='2';$('#fdMaxSize').value='2';saveField()");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='file'&&S.fields[0].accept==='application/pdf,image/jpeg'&&S.fields[0].count===2&&S.fields[0].maxSize===2")
      &&builder.window.fileAcceptDefault==='.pdf,.jpg,.jpeg,.png,.doc,.docx',
    'سازنده نوع، تعداد و حجم مجاز فایل را می‌پذیرد؛ پیش‌فرض عمومی سند هم روشن است');
  const fields=[{id:'certificate-copy',t:'file',l:'مدرک نمونه',req:true,count:2,maxSize:2,accept:'application/pdf,image/jpeg'}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-doc-file',name:'فرم مدرک نمونه',model:'datacollect',need:'other',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-doc-file&kind=other'),input=p.doc.querySelector('#qa0');
  const putFiles=files=>{Object.defineProperty(input,'files',{configurable:true,value:files});input.dispatchEvent(new p.window.Event('change',{bubbles:true}))};
  ok(p.errors.length===0&&input.accept==='application/pdf,image/jpeg'&&input.multiple
      &&input.getAttribute('aria-label')==='مدرک نمونه'
      &&p.txt('#qa0fileNote').includes('هرکدام ۲ مگابایت')
      &&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'ورودی چندفایلی نام دسترس‌پذیر، سقف دو فایل و محدودیت اندازه را اعلام می‌کند');
  const pdf={name:'گواهی.pdf',size:1024,type:'application/pdf'},jpg={name:'تصویر.jpg',size:2048,type:'image/jpeg'};
  putFiles([pdf,jpg]);
  ok(p.window.__NORA_FORM_PREVIEW.validate()===null,
    'PDF و JPG زیر سقف با قالب‌های مجاز تطبیق دارند');
  putFiles([{name:'scan.png',size:1024,type:'image/png'}]);
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('قالب‌های مجاز'),
    'PNG با وجود تصویری‌بودن، وقتی مالک فقط PDF و JPG خواسته رد می‌شود');
  putFiles([{name:'گواهی.pdf',size:1024,type:'text/plain'}]);
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('قالب‌های مجاز'),
    'پسوند و نوع اعلام‌شدهٔ ناسازگار پیش از پذیرش رد می‌شود');
  putFiles([{name:'big.pdf',size:2*1024*1024+1,type:'application/pdf'}]);
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('حجم هر فایل'),
    'حجم بیش از دو مگابایت رد می‌شود');
  putFiles([pdf,jpg,{name:'extra.pdf',size:512,type:'application/pdf'}]);
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('حداکثر ۲ فایل'),
    'فرم فایل بیش از سقف دو مورد را حتی با تزریق برنامه‌ای نمی‌پذیرد');
  putFiles([pdf,jpg]);p.window.__NORA_FORM_PREVIEW.finish();
  ok(p.txt('#regSum').includes('گواهی.pdf')&&p.txt('#regSum').includes('تصویر.jpg')
      &&p.network.length===0,'خلاصه فقط نام فایل‌ها را محلی نگه می‌دارد؛ محتوای مدرک بارگذاری یا ارسال نمی‌شود');
}

/* ── ۴ب۰۹) فایل صدا بدون دسترسی میکروفون یا ضبط ── */
{
  console.log('\n── فایل صدا ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('voice');editField(S.fields[0].id)");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='voice'&&S.fields[0].accept==='audio/*'&&S.fields[0].count===1")
      &&builder.doc.querySelector('#fdStruct').textContent.includes('ضبط/ارسال ندارد')
      &&builder.doc.querySelector('#fdHelp').value.includes('میکروفون، ضبط و ارسال وصل نیست'),
    'سازنده صریح می‌گوید صدا فقط فایلِ انتخابی است؛ ضبط و دسترسی میکروفون وجود ندارد');
  const fields=[{id:'voice-file',t:'voice',l:'فایل صدا',req:true,count:1,maxSize:2,accept:'audio/*',
      help:'فایل صوتی را انتخاب کنید؛ ضبط، میکروفون و ارسال وصل نیست.'}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-voice-file',name:'فرم صدا',model:'datacollect',need:'other',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-voice-file&kind=other'),input=p.doc.querySelector('#qa0');
  const putFiles=files=>{Object.defineProperty(input,'files',{configurable:true,value:files});input.dispatchEvent(new p.window.Event('change',{bubbles:true}))};
  ok(p.errors.length===0&&input.type==='file'&&input.accept==='audio/*'&&!input.multiple
      &&p.txt('#qa0fileNote').includes('ضبط یا ارسال صدا فعال نیست')
      &&!p.doc.querySelector('audio,video,[data-record],button[aria-label*="ضبط"]')
      &&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'پاسخ‌دهنده فقط انتخاب فایل می‌بیند؛ ضبط‌کننده، پخش‌کننده یا درخواست دسترسی جعلی وجود ندارد');
  putFiles([{name:'voice.mp3',size:1024,type:'audio/mpeg'}]);
  ok(p.window.__NORA_FORM_PREVIEW.validate()===null,
    'فایل صوتیِ سازگار زیر سقف برای پیش‌نمایش محلی پذیرفته می‌شود');
  putFiles([{name:'photo.png',size:1024,type:'image/png'}]);
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('قالب‌های مجاز'),
    'فایل تصویری به‌جای صدا پذیرفته نمی‌شود');
  putFiles([{name:'long.mp3',size:2*1024*1024+1,type:'audio/mpeg'}]);
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('حجم هر فایل'),
    'سقف حجم فایل صوتی هم پیش از ادامه بررسی می‌شود');
  putFiles([{name:'voice.mp3',size:1024,type:'audio/mpeg'}]);p.window.__NORA_FORM_PREVIEW.finish();
  ok(p.txt('#regSum').includes('voice.mp3')&&p.network.length===0,
    'در خلاصه فقط نام صدا می‌ماند؛ فایل یا صدایی ضبط و ارسال نمی‌شود');
}

/* ── ۴ب۱۰) امضا فقط تصویر محلی است، نه ابزار رسم یا تأیید ── */
{
  console.log('\n── تصویر امضا ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('sign');editField(S.fields[0].id)");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='sign'&&S.fields[0].accept==='image/*'")
      &&builder.doc.querySelector('#fdStruct').textContent.includes('ابزار رسم/ارسال ندارد')
      &&builder.doc.querySelector('#fdHelp').value.includes('رسم، تأیید یا ارسال واقعی وصل نیست'),
    'سازنده شفاف می‌گوید «امضا» فقط انتخاب تصویر است و ابزار رسم یا تأیید ندارد');
  const fields=[{id:'signature-image',t:'sign',l:'تصویر امضا',req:true,count:1,maxSize:2,accept:'image/*'}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-signature-image',name:'فرم تصویر امضا',model:'datacollect',need:'other',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-signature-image&kind=other'),input=p.doc.querySelector('#qa0');
  const putFiles=files=>{Object.defineProperty(input,'files',{configurable:true,value:files});input.dispatchEvent(new p.window.Event('change',{bubbles:true}))};
  ok(p.errors.length===0&&input.type==='file'&&input.accept==='image/*'
      &&p.txt('#qa0fileNote').includes('این تصویر امضای دیجیتال نیست')
      &&!p.doc.querySelector('canvas,[data-signature-pad],button[aria-label*="رسم امضا"]')
      &&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'فرم فقط انتخاب فایل تصویر دارد؛ نه بوم رسم، امضای دیجیتال یا ادعای احراز هویت');
  putFiles([{name:'signature.jpg',size:1024,type:'image/jpeg'}]);
  ok(p.window.__NORA_FORM_PREVIEW.validate()===null,
    'تصویر امضا با نوع سازگار و اندازهٔ مجاز برای نمایش محلی پذیرفته می‌شود');
  putFiles([{name:'signature.pdf',size:1024,type:'application/pdf'}]);
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('قالب‌های مجاز'),
    'سند PDF به‌جای تصویر امضا پذیرفته نمی‌شود');
  putFiles([{name:'signature.jpg',size:2*1024*1024+1,type:'image/jpeg'}]);
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('حجم هر فایل'),
    'تصویر امضا هم از سقف حجم عبور نمی‌کند');
  putFiles([{name:'signature.jpg',size:1024,type:'image/jpeg'}]);p.window.__NORA_FORM_PREVIEW.finish();
  ok(p.txt('#regSum').includes('signature.jpg')&&p.network.length===0,
    'خلاصه فقط نام تصویر را محلی نگه می‌دارد؛ امضا بارگذاری، تأیید یا برای مالک ارسال نمی‌شود');
}

/* ── ۴ب۱۱) نام و نام خانوادگی با پیش‌پرکردن اختیاری و سقف روشن ── */
{
  console.log('\n── نام و نام خانوادگی ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('fullname')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='fullname'&&S.fields[0].prof===true")
      &&builder.doc.querySelector('#fdHelp').value.includes('پیش‌پرکردن از پروفایل فقط در صورت فعال‌بودن'),
    'سازنده نام را آماده می‌کند و امکان کم‌کردن تایپ را از پروفایل محلی می‌دهد');
  const fields=[{id:'name-profile',t:'fullname',l:'نام و نام خانوادگی',req:true,prof:true},
      {id:'name-manual',t:'fullname',l:'نام همراه',req:false,prof:false}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-fullname',name:'فرم نام',model:'datacollect',need:'other',display:'all',fields,fin:[]}]),
      'nora-home-user':JSON.stringify({name:'کاربر نمونه'}),'nora-home-profile':JSON.stringify({fullName:'سارا محمدی'})}),
    p=await load('form.html',store,'?fid=f-fullname&kind=other'),name=p.doc.querySelector('#qa0'),manual=p.doc.querySelector('#qa1');
  ok(p.errors.length===0&&name.value===''&&name.maxLength===120&&name.autocomplete==='name'
      &&p.doc.querySelector('#profileAssist').style.display!=='none'&&manual.value==='',
    'نام مستقل و خالی است؛ پاسخ‌دهنده می‌تواند دستی بنویسد یا پیشنهاد پروفایل را خودش بخواهد');
  p.click('#profilePrefill');
  ok(name.value==='سارا محمدی'&&manual.value==='',
    'پیشنهاد نام فقط پس از کلیک و فقط برای فیلد انتخاب‌شده اعمال می‌شود');
  p.input('#qa0','  مریم احمدی  ');
  ok(p.window.__NORA_FORM_PREVIEW.validate()===null&&p.doc.querySelector('#qa0').value==='  مریم احمدی  ',
    'نام پس از ویرایش معتبر می‌ماند و متن ورودی بی‌اجازه دست‌کاری نمی‌شود');
  p.input('#qa0','ن'.repeat(121));
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('۱۲۰ نویسه'),
    'نام بیش از سقف ۱۲۰ نویسه از برنامهٔ ثبت رد می‌شود');
  p.input('#qa0','<img src=x onerror=alert(1)>');
  p.window.__NORA_FORM_PREVIEW.finish();
  ok(p.txt('#regSum').includes('<img src=x onerror=alert(1)>')&&p.doc.querySelector('#regSum img')===null
      &&p.network.length===0,'نام دلخواه هنگام خلاصه escape می‌شود و فقط پاسخ محلی می‌ماند');
}

/* ── ۴ب۱۲) موبایل ایرانی، رقم فارسی و پیش‌شمارهٔ بین‌المللی ── */
{
  console.log('\n── موبایل ایرانی ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('mobile');editField(S.fields[0].id)");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='mobile'&&S.fields[0].prof===true")
      &&builder.doc.querySelector('#fdStruct').textContent.includes('بدون ماسک، پیامک یا احراز مالکیت')
      &&builder.doc.querySelector('#fdHelp').value.includes('۰۹، +۹۸')&&builder.doc.querySelector('#fdHelp').value.includes('۰۰۹۸'),
    'سازنده قالب شمارهٔ ایرانی و نبود پیامک/احراز را صریح می‌گوید؛ فیلد می‌تواند از پروفایل محلی پر شود');
  const fields=[{id:'mobile',t:'mobile',l:'شمارهٔ همراه',req:true,prof:true}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-mobile',name:'فرم موبایل',model:'datacollect',need:'other',display:'all',fields,fin:[]}]),
      'nora-home-user':JSON.stringify({name:'کاربر نمونه',mobile:'+989121234567'})}),
    p=await load('form.html',store,'?fid=f-mobile&kind=other'),input=p.doc.querySelector('#qa0');
  ok(p.errors.length===0&&input.value===''&&input.maxLength===20&&input.inputMode==='tel'
      &&p.txt('#qall').includes('تأیید پیامکی یا هویتی فعال نیست')
      &&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'شمارهٔ همراه دستی و خالی می‌ماند، صفحه‌کلید تلفن باز می‌شود و احراز هویت فرض نمی‌شود');
  p.click('#profilePrefill');
  ok(input.value==='+989121234567'&&p.window.__NORA_FORM_PREVIEW.validate()===null,
    'شمارهٔ پروفایل فقط پس از درخواست صریح پیشنهاد می‌شود');
  p.input('#qa0','۰۹۱۲۱۲۳۴۵۶۷');
  ok(p.window.__NORA_FORM_PREVIEW.validate()===null,'۱۱ رقم فارسی با ۰۹ پذیرفته می‌شود');
  p.input('#qa0','+۹۸ ۹۱۲ ۱۲۳ ۴۵۶۷');
  ok(p.window.__NORA_FORM_PREVIEW.validate()===null,'شمارهٔ +۹۸ با فاصله هم بدون تایپ دوبارهٔ صفر پذیرفته می‌شود');
  p.input('#qa0','+98912-123-4567');
  ok(p.window.__NORA_FORM_PREVIEW.validate()===null,'فاصله و خط تیرهٔ رایج در شماره حذف می‌شوند، نه نویسه‌های نامعتبر');
  p.input('#qa0','۰۰۹۸ ۹۱۲ ۱۲۳ ۴۵۶۷');
  ok(p.window.__NORA_FORM_PREVIEW.validate()===null,'پیش‌شمارهٔ ۰۰۹۸ با فاصله هم به شمارهٔ همراه ایران تبدیل و بررسی می‌شود');
  p.input('#qa0','۱۲۳۴۵۶۷۸۹۰۱');
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('۰۰۹۸'),'شمارهٔ ناقص یا نامعتبر با راهنمای قابل‌فهم رد می‌شود');
  p.input('#qa0','۰۹۱۲۱۲۳۴۵۶x');
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('۰۰۹۸'),'حرف چسبیده به شماره با حذف نویسهٔ نامعتبر، به شمارهٔ معتبر تبدیل نمی‌شود');
  p.input('#qa0','09121234567');p.window.__NORA_FORM_PREVIEW.finish();
  ok(p.txt('#regSum').includes('09121234567')&&p.network.length===0,
    'شمارهٔ واردشده فقط در خلاصهٔ محلی می‌ماند؛ پیامک یا بررسی مالکیت انجام نمی‌شود');
}

/* ── ۴ب۱۳) کد ملی با اعتبارسنجی قالب، نه احراز هویت ── */
{
  console.log('\n── کد ملی ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('nid');editField(S.fields[0].id)");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='nid'&&S.fields[0].prof===true")
      &&builder.doc.querySelector('#fdStruct').textContent.includes('بدون بررسی رقم کنترل یا هویت')
      &&builder.doc.querySelector('#fdHelp').value.includes('رقم کنترل و هویت بررسی نمی‌شود'),
    'سازنده تنها قالب ده‌رقمی را وعده می‌دهد و کد ملی را مدرک احراز هویت معرفی نمی‌کند');
  const fields=[{id:'nid',t:'nid',l:'کد ملی',req:true}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-nid',name:'فرم کد ملی',model:'datacollect',need:'other',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-nid&kind=other'),input=p.doc.querySelector('#qa0');
  ok(p.errors.length===0&&input.type==='text'&&input.maxLength===10&&input.inputMode==='numeric'
      &&p.txt('#qall').includes('هویت تأیید نمی‌شود')
      &&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'کد خالی اجباری می‌ماند و ورودی ده‌رقمی، صفحه‌کلید عددی و یادآوریِ نبود احراز را دارد');
  p.input('#qa0','۰۰۱۲۳۴۵۶۷۸');
  ok(p.window.__NORA_FORM_PREVIEW.validate()===null,
    'ده رقم فارسی با صفرهای آغازین پذیرفته می‌شوند');
  p.input('#qa0','001234567x');
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('دقیقاً ده رقم'),
    'حرفی که با جداکنندهٔ غیرمجاز جای رقم آمده از قالب‌سنجی عبور نمی‌کند');
  p.input('#qa0','12345678901');
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('دقیقاً ده رقم'),
    'کدِ یازده‌رقمی هم پذیرفته نمی‌شود');
  p.input('#qa0','0012345678');p.window.__NORA_FORM_PREVIEW.finish();
  ok(p.txt('#regSum').includes('0012345678')&&p.network.length===0,
    'کد واردشده فقط در مرورگر می‌ماند؛ رقم کنترل، هویت یا مالکیت بررسی نمی‌شود');
}

/* ── ۴ب۱۴) ایمیل با قالب‌سنجی پایه، بدون تأیید مالکیت ── */
{
  console.log('\n── ایمیل ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('email');editField(S.fields[0].id)");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='email'")
      &&builder.doc.querySelector('#fdStruct').textContent.includes('بدون تأیید مالکیت')
      &&builder.doc.querySelector('#fdHelp').value.includes('ارسال یا مالکیت آن بررسی نمی‌شود'),
    'سازنده فقط بررسی قالب پایه را وعده می‌دهد؛ ایمیل یا مالکیت نشانی تأیید نمی‌شود');
  const fields=[{id:'email',t:'email',l:'ایمیل',req:true}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-email',name:'فرم ایمیل',model:'datacollect',need:'other',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-email&kind=other'),input=p.doc.querySelector('#qa0');
  ok(p.errors.length===0&&input.type==='email'&&input.maxLength===254&&input.autocomplete==='email'
      &&input.getAttribute('autocapitalize')==='none'&&input.getAttribute('spellcheck')==='false'
      &&p.txt('#qall').includes('مالکیت ایمیل تأیید نمی‌شود')
      &&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'ورودی ایمیل صفحه‌کلید و autocomplete درست دارد؛ خالی‌بودنش در پرسش اجباری پذیرفته نمی‌شود');
  p.input('#qa0','  Sara.Example@Mail.com  ');
  ok(p.window.__NORA_FORM_PREVIEW.validate()===null,
    'ایمیل معتبر پس از برداشتن فاصلهٔ ابتدا و انتها پذیرفته می‌شود');
  p.input('#qa0','sara@@example.com');
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('قالب ایمیل کامل نیست'),
    'نشانی با دو علامت @ پیش از ثبت رد می‌شود');
  p.input('#qa0','sara@example');
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('قالب ایمیل کامل نیست'),
    'نشانی بدون بخش دامنهٔ کامل پذیرفته نمی‌شود');
  p.input('#qa0','a'.repeat(255)+'@x.com');
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('۲۵۴ نویسه'),
    'ایمیل طولانی‌تر از سقف استاندارد ۲۵۴ نویسه در منطق فرم رد می‌شود');
  p.input('#qa0','sara@example.com');p.window.__NORA_FORM_PREVIEW.finish();
  ok(p.txt('#regSum').includes('sara@example.com')&&p.network.length===0,
    'نشانی فقط در خلاصهٔ محلی می‌ماند؛ ایمیل یا کد تأییدی ارسال نمی‌شود');
}

/* ── ۴ب۱۵) عددِ موسوم به قیمت، فقط پاسخ است و پرداخت نمی‌سازد ── */
{
  console.log('\n── فیلد قیمتِ نمایشی ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('price');editField(S.fields[0].id);$('#fdMin').value='1000';$('#fdMax').value='2000';saveField()");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='price'&&S.fields[0].min===1000&&S.fields[0].max===2000")
      &&builder.doc.querySelector('#fdBoundsBox').style.display==='block'
      &&builder.doc.querySelector('#fdStruct').textContent.includes('قیمت‌گذاری مالی نیست')
      &&builder.doc.querySelector('#fdHelp').value.includes('تخفیف واقعی محاسبه نمی‌شود'),
    'سازنده برای پاسخِ عددیِ قیمت حد می‌گذارد اما آن را قیمت‌گذاری یا تخفیف واقعی معرفی نمی‌کند');
  const fields=[{id:'price-answer',t:'price',l:'مبلغ نمونه',req:true,min:1000,max:2000}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-price-answer',name:'فرم قیمت نمایشی',model:'datacollect',need:'other',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-price-answer&kind=other'),input=p.doc.querySelector('#qa0');
  ok(p.errors.length===0&&input.inputMode==='decimal'&&p.txt('#qall').includes('پرداختی انجام نمی‌شود')
      &&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'پاسخ‌دهنده عدد خالی و اجباری می‌بیند؛ متن صفحه آن را از مبلغ پرداختی جدا می‌کند');
  p.input('#qa0','۱٬۲۵۰');
  ok(p.window.__NORA_FORM_PREVIEW.validate()===null&&p.doc.querySelector('#qa0').value==='۱٬۲۵۰',
    'رقم فارسی و جداکنندهٔ هزارگان در پاسخ قیمت‌مانند پذیرفته می‌شوند');
  p.input('#qa0','۹۹۹');
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('حداقل مقدار'),
    'حد پایینِ فیلد عددی پیش از ادامه کنترل می‌شود');
  p.input('#qa0','1,5');
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('باید عدد باشد'),
    'جداکنندهٔ هزارگان نامعتبر به عدد ۱۵ تبدیل نمی‌شود');
  p.input('#qa0','۲۰۰۱');
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('حداکثر مقدار'),
    'حد بالای پاسخ هم اعمال می‌شود');
  p.input('#qa0','۱۲۵۰');p.window.__NORA_FORM_PREVIEW.finish();
  ok(p.txt('#regSum').includes('۱۲۵۰')&&!p.store.getItem('nora-receipts')&&p.network.length===0,
    'عدد فقط پاسخ محلی است؛ رسید، پرداخت یا درخواست شبکه‌ای ساخته نمی‌شود');
}

/* ── ۴ب۱۶) کد تخفیف، فقط ورودی متنی و بدون اعتبارسنجی یا اعمال تخفیف ── */
{
  console.log('\n── کد تخفیفِ متنی ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('coupon');editField(S.fields[0].id)");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='coupon'&&S.fields[0].help.includes('اعتبارسنجی یا تخفیف واقعی ندارد')")
      &&builder.doc.querySelector('#fdStruct').textContent.includes('اعتبارسنجی تخفیف ندارد'),
    'سازنده هشدار می‌دهد کد فقط ورودی متنی است و تخفیف واقعی اعمال نمی‌شود');
  const fields=[{id:'coupon',t:'coupon',l:'کد نمونه',req:false}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-coupon',name:'فرم کد نمونه',model:'datacollect',need:'other',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-coupon&kind=other'),input=p.doc.querySelector('#qa0');
  ok(p.errors.length===0&&input.type==='text'&&input.maxLength===64&&input.placeholder==='مثلاً NORA-10'
      &&p.txt('#qall').includes('تخفیف واقعی اعمال نمی‌شود')
      &&p.window.__NORA_FORM_PREVIEW.validate()===null,
    'کد اختیاری، با سقف طول مشخص و بدون بررسی یا تغییر مبلغ، خالی می‌ماند');
  p.input('#qa0','SUMMER-10');
  ok(p.window.__NORA_FORM_PREVIEW.validate()===null&&p.doc.querySelector('#qa0').value==='SUMMER-10',
    'هر رشتهٔ کد فقط همان متنِ واردشده را ثبت می‌کند و وعدهٔ اعتبار نمی‌دهد');
  p.input('#qa0','<img src=x onerror=alert(1)>');p.window.__NORA_FORM_PREVIEW.finish();
  ok(p.txt('#regSum').includes('<img src=x onerror=alert(1)>')&&p.doc.querySelector('#regSum img')===null
      &&!p.store.getItem('nora-receipts')&&p.network.length===0,
    'کد متنی در خلاصه escape می‌شود و به تخفیف، رسید یا شبکه وصل نیست');
}

/* ── ۴ب۱۷) متن کوتاه و بلند با سقف اندازه و حفظ سطرها ── */
{
  console.log('\n── متن کوتاه و بلند ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('text');addField('area')");
  ok(builder.window.eval("S.fields.length===2&&S.fields[0].t==='text'&&S.fields[1].t==='area'")
      &&builder.window.eval("S.fields[0].help.length>0&&S.fields[1].help.length>0"),
    'سازنده میان پاسخ تک‌خطی و توضیح چندخطی فرق می‌گذارد و برای هرکدام راهنمای جدا دارد');
  const fields=[{id:'short-text',t:'text',l:'پاسخ کوتاه',req:true},{id:'long-text',t:'area',l:'توضیح کامل',req:false}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-text-area',name:'فرم نوشتاری',model:'questionnaire',need:'other',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-text-area&kind=other'),short=p.doc.querySelector('#qa0'),long=p.doc.querySelector('#qa1');
  ok(p.errors.length===0&&short.tagName==='INPUT'&&short.maxLength===1000
      &&long.tagName==='TEXTAREA'&&long.rows===4&&long.maxLength===3000
      &&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'پاسخ کوتاه یک‌خطی و متن بلند چندخطی‌اند؛ سقف طول در خود رابط هم مشخص است');
  p.input('#qa0','خلاصهٔ پاسخ');p.input('#qa1','خط نخست\nخط دوم با جزئیات');
  ok(p.window.__NORA_FORM_PREVIEW.validate()===null&&p.doc.querySelector('#qa1').value.includes('\n'),
    'متن چندخطی بدون حذف سطرها ثبت می‌شود و فیلد اختیاری هم اجباری نمی‌شود');
  p.input('#qa0','x'.repeat(1001));
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('حداکثر ۱۰۰۰ نویسه'),
    'ورودی کوتاهِ دست‌کاری‌شده هم از سقف ۱۰۰۰ نویسه عبور نمی‌کند');
  p.input('#qa0','پاسخ نهایی');p.input('#qa1','خط یک\nخط دو <img src=x onerror=alert(1)>');
  p.window.__NORA_FORM_PREVIEW.finish();
  ok(p.txt('#regSum').includes('خط یک خط دو <img src=x onerror=alert(1)>')
      &&p.doc.querySelector('#regSum img')===null&&p.network.length===0,
    'خلاصه سطرهای متن را نگه می‌دارد، HTML را اجرا نمی‌کند و پاسخ را بیرون نمی‌فرستد');
}

/* ── ۴ب۱۸) ساعت پیشنهادی، بدون رزرو یا ظرفیت قطعی ── */
{
  console.log('\n── ساعت پیشنهادی ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('slot');editField(S.fields[0].id)");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='slot'")
      &&builder.doc.querySelector('#fdStruct').textContent.includes('فهرست بازه ندارد')
      &&builder.doc.querySelector('#fdHelp').value.includes('رزرو یا تأیید ظرفیت نیست'),
    'سازنده می‌گوید این فیلد فقط ساعت می‌گیرد و بازه یا رزرو خودکار نمی‌سازد');
  const fields=[{id:'suggested-time',t:'slot',l:'ساعت پیشنهادی',req:true}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-slot-time',name:'فرم ساعت پیشنهادی',model:'datacollect',need:'other',display:'all',fields,fin:[]}])}),
    p=await load('form.html',store,'?fid=f-slot-time&kind=other'),box=p.doc.querySelector('[data-qpick][data-i="0"]');
  ok(p.errors.length===0&&box.dataset.qpick==='time'&&box.querySelector('.pk1').style.display==='none'
      &&box.querySelector('.pk4').value===''&&box.querySelector('.pk5').disabled
      &&p.txt('#qall').includes('رزرو قطعی نیست')
      &&p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'پاسخ‌دهنده ساعت خالی و دقیقهٔ کامل دارد؛ انتخاب ساعت به رزرو یا تأیید تبدیل نمی‌شود');
  const set=(selector,value)=>{const input=box.querySelector(selector);input.value=String(value);input.dispatchEvent(new p.window.Event('change',{bubbles:true}))};
  set('.pk4','9');
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('کامل و درست'),
    'انتخاب ساعت بدون دقیقه به اشتباه به :۰۰ تبدیل نمی‌شود');
  set('.pk5','17');
  ok(p.doc.querySelector('#qa0').value==='۰۹:۱۷'&&p.window.__NORA_FORM_PREVIEW.validate()===null,
    'ساعت و دقیقهٔ دلخواه در پاسخ محلی ثبت می‌شوند');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'۲۳:۵۹'},picks:{},guests:[],fin:[],picked:[]});
  ok(box.querySelector('.pk4').value==='23'&&box.querySelector('.pk5').value==='59'
      &&p.doc.querySelector('#qa0').value==='۲۳:۵۹','پیش‌نویس ساعت پیشنهادی را هم دقیق بازیابی می‌کند');
  ok(p.network.length===0,'ساعت پیشنهادی درخواست شبکه یا رزرو واقعی نمی‌سازد');
}

/* ── ۴ب۱۹) انتخاب استان و شهر، بدون انتخاب اشتباه و با راهِ شهر دیگر ── */
{
  console.log('\n── انتخاب استان و شهر ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('province')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='province'&&S.fields[0].l==='استان و شهر'&&S.fields[0].opts.length===0")
      &&builder.doc.querySelector('#fdHelp').value.includes('اگر شهرتان را پیدا نکردید'),
    'سازنده با یک انتخاب، فیلد آمادهٔ استان و شهر می‌سازد؛ لازم نیست فهرست شهرها را خودش وارد کند');
  const fields=[{id:'region',t:'province',l:'استان و شهر',req:true,help:'اول استان را انتخاب کنید، بعد شهر را.'}];
  const store=makeStore({'nora-forms':JSON.stringify([{id:'f-geo-picker',name:'فرم مکان',model:'datacollect',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-geo-picker&kind=other'),box=p.doc.querySelector('[data-qgeo][data-i="0"]');
  const province=box.querySelector('.gp'),city=box.querySelector('.gc'),other=box.querySelector('.geo-other');
  ok(p.errors.length===0&&province.value===''&&city.disabled&&city.value===''&&city.options[0].textContent.includes('اول استان'),
    'فرم با استان و شهر خالی شروع می‌شود؛ شهر تا انتخاب استان غیرفعال است');
  p.click('#next');p.set('[data-qgeo] .gp','البرز');
  ok(city.value===''&&city.options[0].textContent==='شهر را انتخاب کنید'&&p.doc.querySelector('#qa0').value==='',
    'انتخاب استان، شهر اول فهرست را بی‌اجازه انتخاب نمی‌کند');
  p.click('#next');
  ok(p.window.eval("cur==='qall'")&&p.txt('#toast').includes('اجباری'),
    'انتخاب استان به‌تنهایی برای فیلد اجباری پاسخ کامل حساب نمی‌شود');
  p.set('[data-qgeo] .gc','کرج');
  ok(p.doc.querySelector('#qa0').value==='البرز · کرج',
    'با انتخاب شهر از فهرست، پاسخ استان و شهر درست کنار هم ذخیره می‌شود');
  p.set('[data-qgeo] .gc','__other__');
  ok(other.style.display!=='none'&&p.doc.querySelector('#qa0').value==='',
    'برای شهرِ پیدا نشده، ورودی جدا باز می‌شود و تا نوشتن نام شهر پاسخ ناقص می‌ماند');
  p.input('[data-qgeo] .geo-other','هشتگردک');
  ok(p.doc.querySelector('#qa0').value==='البرز · هشتگردک',
    'نام شهر دیگر بی‌درنگ در پاسخ همان فیلد ثبت می‌شود');
  p.input('[data-qgeo] .geo-other','شهر <img src=x onerror=alert(1)>');
  ok(p.doc.querySelector('#qa0').value==='البرز · شهر <img src=x onerror=alert(1)>'&&p.errors.length===0,
    'نام شهر در پاسخ، به‌صورت متن و بدون تغییر می‌ماند');
  p.click('#next');
  ok(p.window.eval("cur==='u12'")&&p.doc.querySelector('#regSum img')===null
      &&p.doc.querySelector('#regSum').textContent.includes('<img src=x'),
    'نام شهر هنگام نمایش پاسخ escape می‌شود و HTML قابل اجرا نمی‌سازد');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'البرز · شهر تازه'},picks:{},guests:[],fin:[],picked:[]});
  ok(province.value==='البرز'&&city.value==='__other__'&&other.value==='شهر تازه'&&p.doc.querySelector('#qa0').value==='البرز · شهر تازه',
    'پیش‌نویس شهرِ خارج از فهرست هم پس از بازگشت دقیقاً بازیابی می‌شود');
}

/* ── ۴ب۲۰) جست‌وجوی دانشگاه و ورود نامِ خارج از فهرست ── */
{
  const production=await load('form.html',makeStore(),'',null,{fixtureMode:false});
  ok(production.doc.querySelector('#pkBirth [data-val]').dataset.val===''&&production.doc.querySelector('#pkGeo .gp').value==='' 
      &&production.doc.querySelector('#pkUni .uni-other').value===''&&production.doc.querySelector('#pkJob .lp').value==='',
    'پروفایل واقعی با تاریخ، شهر، دانشگاه یا شغل نمونه از پیش پر نمی‌شود');
  ok(!production.window.NORA_UNIVERSITIES_BY_PROVINCE&&!production.doc.querySelector('script[data-nora-universities]'),
    'صفحهٔ عادی نه فهرست دانشگاه و نه دادهٔ نمونهٔ آن را بارگیری می‌کند');
  production.dom.window.close();
}
{

  console.log('\n── دانشگاه، بدون تایپ اجباری ──');
  const fields=[{id:'university',t:'uni',l:'دانشگاه',req:true},{id:'university-2',t:'uni',l:'دانشگاه دوم',req:false}];
  const store=makeStore({'nora-forms':JSON.stringify([{id:'f-uni-picker',name:'فرم دانشگاه',model:'datacollect',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-uni-picker&kind=other'),input=p.doc.querySelector('[data-qlist][data-i="0"] .lp'),
    otherInput=p.doc.querySelector('[data-qlist][data-i="0"] .uni-other'),secondInput=p.doc.querySelector('[data-qlist][data-i="1"] .lp'),
    profileUni=p.doc.querySelector('#pkUni .lp'),province=p.doc.querySelector('[data-qlist][data-i="0"] .up');
  ok(p.errors.length===0&&input.tagName==='SELECT'&&input.disabled&&province.tagName==='SELECT'
      &&province.getAttribute('aria-label')==='استان محل تحصیل'&&province.options.length===32
      &&input.getAttribute('aria-label')==='دانشگاه محل تحصیل'&&input.options.length===1&&otherInput.disabled,
    'استان و دانشگاه دو منوی کشویی‌اند؛ منوی دانشگاه تا انتخاب استان بسته می‌ماند');
  ok(!p.doc.querySelector('script[data-nora-universities]')&&!p.window.NORA_UNIVERSITIES_BY_PROVINCE,
    'فهرست پرحجم دانشگاه پیش از نیاز در صفحه بارگیری نمی‌شود');
  p.set('[data-qlist][data-i="0"] .up','تهران');
  await p.window.NORA_UI.loadUniversities();
  ok(!!p.doc.querySelector('script[data-nora-universities]')&&Object.keys(p.window.NORA_UNIVERSITIES_BY_PROVINCE||{}).length===31,
    'با انتخاب استان، دادهٔ دانشگاه به‌صورت تنبل و از همان مبدأ بارگیری می‌شود');
  ok(!input.disabled&&input.options.length>100&&[...input.options].some(option=>option.value==='دانشگاه تهران')
      &&[...input.options].some(option=>option.value==='__other__'&&option.textContent==='سایر'),
    'پس از انتخاب استان، منوی دانشگاه فقط فهرست همان استان و گزینهٔ «سایر» را دارد');
  p.set('[data-qlist][data-i="0"] .lp','__other__');
  ok(input.value==='__other__'&&otherInput.style.display!=='none'&&!otherInput.disabled,
    'انتخاب «سایر» ورودی کوتاه نام دانشگاه را باز می‌کند');
  p.set('[data-qlist][data-i="0"] .lp','دانشگاه تهران');
  ok(otherInput.style.display==='none'&&otherInput.value==='',
    'انتخاب نام موجود ورودی «سایر» را می‌بندد');
  ok(secondInput?.disabled&&secondInput.options.length===1,
    'هر پرسش دانشگاه منوی مستقل دارد و تا انتخاب استان، گزینه‌ای نشان نمی‌دهد');
  ok(profileUni?.tagName==='SELECT'
      &&p.txt('#u6').includes('جامعه‌ساخته')&&p.txt('#u6').includes('کامل یا به‌روز بودنش تضمین نمی‌شود')
      &&p.txt('#u6').includes('«سایر» را انتخاب کنید'),
    'محدودیت پوشش فهرست در فرم روشن است و راه انتخاب «سایر» باقی می‌ماند');
  ok(![...input.options].some(option=>option.value==='دانشگاه گیلان'),
    'دانشگاهِ استان دیگر در منوی استان انتخاب‌شده ظاهر نمی‌شود');
  p.set('[data-qlist][data-i="0"] .lp','');
  p.click('#next');p.click('#next');
  ok(p.window.eval("cur==='qall'")&&p.txt('#toast').includes('اجباری'),
    'دانشگاهِ اجباری بدون انتخاب یا نام «سایر» تکمیل نمی‌شود');
  p.set('[data-qlist][data-i="0"] .lp','دانشگاه تهران');
  ok(p.doc.querySelector('#qa0').value==='تهران · دانشگاه تهران',
    'انتخاب دانشگاه آماده، استان و نام را باهم در پاسخ ثبت می‌کند');
  p.set('[data-qlist][data-i="0"] .lp','__other__');
  p.input('[data-qlist][data-i="0"] .uni-other','دانشگاه تازه');
  ok(input.value==='__other__'&&otherInput.value==='دانشگاه تازه'
      &&p.doc.querySelector('#qa0').value==='تهران · دانشگاه تازه',
    'نام غایب از مسیر کشویی «سایر» همراه استان در پاسخ ذخیره می‌شود');
  const unsafe='<img src=x onerror=alert(1)>';
  p.input('[data-qlist][data-i="0"] .uni-other',unsafe);p.click('#next');
  ok(p.doc.querySelector('#regSum img')===null&&p.txt('#regSum').includes(unsafe),
    'نام دانشگاه در خلاصه به‌صورت متن escape می‌شود و HTML اجرایی نمی‌سازد');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'تهران · دانشگاه جدید'},picks:{},guests:[],fin:[],picked:[]});
  ok(input.value==='__other__'&&otherInput.value==='دانشگاه جدید'&&province.value==='تهران'
      &&p.doc.querySelector('#qa0').value==='تهران · دانشگاه جدید',
    'نام خارج از فهرست پس از بازگشت از پیش‌نویس در گزینهٔ «سایر» بازیابی می‌شود');
  ok(p.network.length===0,'انتخاب دانشگاه فقط از دادهٔ محلی است و به سرویس بیرونی وصل نیست');
}

/* ── ۴ب۲۱) پیش‌پرکردن فیلد دانشگاه از نمایهٔ محلی ── */
{
  console.log('\n── پیش‌پرکردن دانشگاه از نمایهٔ محلی ──');
  const fields=[{id:'uni-prefill',t:'uni',l:'دانشگاه',req:true,prof:true}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-uni-prefill',name:'فرم دانشگاه',model:'datacollect',need:'other',display:'all',fields,fin:[]}]),
      'nora-home-user':JSON.stringify({name:'کاربر نمونه',uni:'دانشگاه تهران'})});
  const p=await load('form.html',store,'?fid=f-uni-prefill&kind=other'),input=p.doc.querySelector('[data-qlist][data-i="0"] .lp');
  ok(p.errors.length===0&&input.value===''&&p.doc.querySelector('#qa0').value==='',
    'دانشگاه بدون انتخاب پاسخ‌دهنده خودکار از نمایه خوانده نمی‌شود');
  p.click('#profilePrefill');
  await p.window.NORA_UI.loadUniversities();
  ok(input.value==='دانشگاه تهران'&&p.doc.querySelector('[data-qlist][data-i="0"] .up').value==='تهران'
      &&p.doc.querySelector('#qa0').value==='تهران · دانشگاه تهران'&&p.network.length===0,
    'نمایهٔ دانشگاه پس از رضایت، استان و دانشگاه را کنار هم پر می‌کند و درخواست بیرونی ندارد');
  const customStore=makeStore({'nora-forms':JSON.stringify([{id:'f-uni-prefill-custom',name:'فرم دانشگاه',model:'datacollect',need:'other',display:'all',fields,fin:[]}]),
    'nora-home-user':JSON.stringify({name:'کاربر نمونه',uni:'دانشگاه جاافتاده'})});
  const custom=await load('form.html',customStore,'?fid=f-uni-prefill-custom&kind=other'),customInput=custom.doc.querySelector('[data-qlist][data-i="0"] .lp'),
    customOther=custom.doc.querySelector('[data-qlist][data-i="0"] .uni-other'),customProvince=custom.doc.querySelector('[data-qlist][data-i="0"] .up');
  custom.click('#profilePrefill');
  await custom.window.NORA_UI.loadUniversities();
  ok(customInput.disabled&&customOther.value==='دانشگاه جاافتاده'&&customOther.disabled
      &&customProvince.value===''&&custom.doc.querySelector('#qa0').value==='',
    'نام قدیمیِ بدون استان گم نمی‌شود و تا تعیین استان پاسخ ناقص می‌ماند');
  custom.set('[data-qlist][data-i="0"] .up','گیلان');
  ok(customInput.value==='__other__'&&customOther.value==='دانشگاه جاافتاده'&&!customOther.disabled
      &&custom.doc.querySelector('#qa0').value==='گیلان · دانشگاه جاافتاده',
    'با تعیین استان، نام خارج از فهرست حفظ و به گزینهٔ «سایر» متصل می‌شود');
}

/* ── ۴ب۲۲) شغل: فهرست محلی و ورود نام دلخواه ── */
{
  console.log('\n── فهرست شغل و گزینهٔ «سایر» ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('job')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='job'&&S.fields[0].opts.length===0")
      &&builder.doc.querySelector('#fdHelp').value.includes('اسمش را بنویسید'),
    'فیلد شغل بدون ساختن گزینه‌های تکراری، راهنمای روشن برای «سایر» دارد');
  const fields=[{id:'job',t:'job',l:'شغل',req:true}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-job-picker',name:'فرم شغل',model:'datacollect',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-job-picker&kind=other'),select=p.doc.querySelector('[data-qlist][data-i="0"] .lp');
  ok(p.errors.length===0&&select.tagName==='SELECT'&&select.getAttribute('aria-label')==='شغل'
      &&select.options.length>=20&&[...select.options].some(option=>option.value==='دانشجو'),
    'شغل‌های پرکاربرد از فهرست انتخاب می‌شوند و کنترل ورودی نام قابل‌فهمی دارد');
  p.click('#next');p.click('#next');
  ok(p.txt('#toast').includes('اجباری')&&p.window.eval("cur==='qall'"),
    'فیلد اجباری تا انتخاب شغل یا نوشتن مقدار در «سایر» خالی می‌ماند');
  p.set('[data-qlist][data-i="0"] .lp','برنامه‌نویس و فناوری اطلاعات');
  ok(p.doc.querySelector('#qa0').value==='برنامه‌نویس و فناوری اطلاعات',
    'انتخاب شغل آماده، پاسخ فرم را به‌روز می‌کند');
  p.set('[data-qlist][data-i="0"] .lp','سایر');
  const other=p.doc.querySelector('[data-qlist][data-i="0"] .other');
  ok(other.style.display!=='none'&&other.getAttribute('aria-label')==='شغل دلخواه'
      &&other.getAttribute('placeholder').includes('شغل')&&p.doc.activeElement===other,
    'با انتخاب «سایر»، ورودی با راهنمای مخصوص شغل باز و آمادهٔ تایپ می‌شود');
  p.input('[data-qlist][data-i="0"] .other','مشاور مستقل');
  ok(p.doc.querySelector('#qa0').value==='مشاور مستقل',
    'نام شغل خارج از فهرست در پاسخ فرم و پیش‌نویس محلی ذخیره می‌شود');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'مشاور مستقل'},picks:{},guests:[],fin:[],picked:[]});
  ok(select.value==='سایر'&&other.value==='مشاور مستقل'&&other.style.display!=='none'
      &&p.doc.querySelector('#qa0').value==='مشاور مستقل',
    'نام شغل دلخواه پس از بازگشت از پیش‌نویس دقیقاً بازیابی می‌شود');
  const unsafe='<img src=x onerror=alert(1)>';
  p.input('[data-qlist][data-i="0"] .other',unsafe);p.click('#next');
  ok(p.doc.querySelector('#regSum img')===null&&p.txt('#regSum').includes(unsafe),
    'نام دلخواه در خلاصه به شکل متن امن دیده می‌شود و HTML اجرایی نمی‌سازد');
  ok(p.network.length===0,'فهرست شغل و نام دلخواه هیچ درخواست بیرونی نمی‌فرستند');
}

/* ── ۴ب۲۳) مقطع تحصیلی: انتخاب محلی یا نوشتن مورد دیگر ── */
{
  console.log('── مقطع تحصیلی و گزینهٔ «سایر» ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('edu')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='edu'&&S.fields[0].opts.length===0")
      &&builder.doc.querySelector('#fdHelp').value.includes('گزینهٔ مدنظرتان نبود'),
    'فیلد مقطع تحصیلی راهنمای روشن دارد و سازنده لازم نیست گزینه‌های پایه را دوباره بسازد');
  const fields=[{id:'education',t:'edu',l:'مقطع تحصیلی',req:true}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-edu-picker',name:'فرم تحصیلی',model:'datacollect',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-edu-picker&kind=other'),select=p.doc.querySelector('[data-qlist][data-i="0"] .lp');
  ok(p.errors.length===0&&select.tagName==='SELECT'&&select.getAttribute('aria-label')==='مقطع تحصیلی'
      &&select.options.length>=9&&[...select.options].some(option=>option.value==='کارشناسی')
      &&[...select.options].some(option=>option.value==='سایر'),
    'مقطع‌های پرکاربرد در فهرست آماده‌اند و راه ورود مورد دلخواه هم مشخص است');
  p.click('#next');p.click('#next');
  ok(p.txt('#toast').includes('اجباری')&&p.window.eval("cur==='qall'"),
    'فیلد اجباری تا انتخاب مقطع یا نوشتن مورد دیگر خالی می‌ماند');
  p.set('[data-qlist][data-i="0"] .lp','کارشناسی');
  ok(p.doc.querySelector('#qa0').value==='کارشناسی','انتخاب مقطع آماده، پاسخ فرم را به‌روز می‌کند');
  p.set('[data-qlist][data-i="0"] .lp','سایر');
  const other=p.doc.querySelector('[data-qlist][data-i="0"] .other');
  ok(other.style.display!=='none'&&other.getAttribute('aria-label')==='مقطع تحصیلی دلخواه'
      &&other.getAttribute('placeholder').includes('مقطع تحصیلی')&&p.doc.activeElement===other,
    'با انتخاب «سایر»، ورودی مخصوص مقطع باز و آمادهٔ نوشتن می‌شود');
  p.input('[data-qlist][data-i="0"] .other','دانشجوی دکتری حرفه‌ای');
  ok(p.doc.querySelector('#qa0').value==='دانشجوی دکتری حرفه‌ای',
    'مقطع خارج از گزینه‌های آماده در پاسخ و پیش‌نویس محلی می‌ماند');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'دانشجوی دکتری حرفه‌ای'},picks:{},guests:[],fin:[],picked:[]});
  ok(select.value==='سایر'&&other.value==='دانشجوی دکتری حرفه‌ای'&&other.style.display!=='none'
      &&p.doc.querySelector('#qa0').value==='دانشجوی دکتری حرفه‌ای',
    'مقطع دلخواه پس از بازگشت از پیش‌نویس دقیقاً بازیابی می‌شود');
  const unsafe='<img src=x onerror=alert(1)>';
  p.input('[data-qlist][data-i="0"] .other',unsafe);p.click('#next');
  ok(p.doc.querySelector('#regSum img')===null&&p.txt('#regSum').includes(unsafe),
    'متن دلخواه مقطع در خلاصه امن است و HTML اجرایی نمی‌سازد');
  ok(p.network.length===0,'فهرست مقطع تحصیلی و ورود آزاد آفلاین می‌مانند');
}

/* ── ۴ب۲۴) متن کوتاه: راهنمای سازنده، نام دسترس‌پذیر و پاسخ امن ── */
{
  console.log('── متن کوتاه و پاسخ آزاد ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('text')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='text'&&S.fields[0].help==='کوتاه بنویسید.'")
      &&builder.doc.querySelector('#fdPlaceholderBox').style.display!=='none',
    'فیلد متن کوتاه با راهنمای طبیعی و تنظیم متن راهنما/جای‌نگهدار آماده می‌شود');
  builder.set('#fdPlaceholder','مثلاً ونک');builder.window.eval('saveField()');
  ok(builder.window.eval("S.fields[0].placeholder==='مثلاً ونک'"),'جای‌نگهدار دلخواه در تنظیم فیلد ذخیره می‌شود');
  const fields=[{id:'short-answer',t:'text',l:'نام محله',req:true,help:'اسم محله‌تان را بنویسید.',placeholder:'مثلاً ونک'}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-short-text',name:'فرم متن کوتاه',model:'datacollect',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-short-text&kind=other'),input=p.doc.querySelector('#qa0');
  ok(p.errors.length===0&&input.type==='text'&&input.getAttribute('aria-label')==='نام محله'
      &&input.getAttribute('placeholder')==='مثلاً ونک'&&p.txt('#qall').includes('اسم محله‌تان را بنویسید.'),
    'عنوان پرسش، جای‌نگهدار و راهنما کنار ورودی با نام دسترس‌پذیر درست نمایش داده می‌شوند');
  p.click('#next');p.click('#next');
  ok(p.txt('#toast').includes('اجباری')&&p.window.eval("cur==='qall'"),
    'پاسخ فقط از فاصله خالی تشکیل شده باشد، فیلد اجباری پذیرفته نمی‌شود');
  p.input('#qa0','  ونک  ');
  ok(input.value==='  ونک  ','فاصله‌های متن هنگام تایپ از ورودی کاربر حذف نمی‌شوند');
  p.click('#next');
  ok(p.txt('#regSum').includes('ونک')&&!p.txt('#regSum').includes('  ونک  '),
    'فاصلهٔ ابتدا و انتها از پاسخ نهایی پاک می‌شود، بدون تغییر زودهنگام ورودی');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'شهرک غرب'},picks:{},guests:[],fin:[],picked:[]});
  ok(input.value==='شهرک غرب','پاسخ متن کوتاه پس از برگشت از پیش‌نویس بازیابی می‌شود');
  const unsafe='<img src=x onerror=alert(1)>';
  p.input('#qa0',unsafe);p.click('#next');
  ok(p.doc.querySelector('#regSum img')===null&&p.txt('#regSum').includes(unsafe),
    'متن کوتاه در خلاصه امن می‌ماند و HTML اجرایی نمی‌سازد');
  ok(p.network.length===0,'نوشتن و بازیابی پاسخ متنی هیچ سرویس بیرونی را صدا نمی‌زند');
}

/* ── ۴ب۲۵) متن بلند: چندخطی، پیش‌نویس و خروجی امن ── */
{
  console.log('── متن بلند و کادر چندخطی ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('area')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='area'&&S.fields[0].help==='توضیح کامل بدهید.'")
      &&builder.doc.querySelector('#fdPlaceholderBox').style.display!=='none',
    'فیلد متن بلند با راهنمای خودش و تنظیم جای‌نگهدار آماده می‌شود');
  const fields=[{id:'long-answer',t:'area',l:'توضیحات بیشتر',req:true,help:'هر نکته‌ای لازم است اضافه کنید.',placeholder:'شرح را این‌جا بنویسید'}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-long-text',name:'فرم متن بلند',model:'datacollect',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-long-text&kind=other'),area=p.doc.querySelector('#qa0');
  ok(p.errors.length===0&&area.tagName==='TEXTAREA'&&area.rows===4
      &&area.getAttribute('aria-label')==='توضیحات بیشتر'&&area.placeholder==='شرح را این‌جا بنویسید'
      &&p.txt('#qall').includes('هر نکته‌ای لازم است اضافه کنید.'),
    'کادر چندخطی، عنوان دسترس‌پذیر، جای‌نگهدار و راهنمای فرم را درست نشان می‌دهد');
  p.click('#next');p.click('#next');
  ok(p.txt('#toast').includes('اجباری')&&p.window.eval("cur==='qall'"),
    'کادر اجباری با فاصله یا خط خالی پذیرفته نمی‌شود');
  const answer='  خط اول\nخط دوم  ';
  p.input('#qa0',answer);
  ok(area.value===answer,'فاصله و شکست‌خط هنگام نوشتن از متن کاربر حذف نمی‌شود');
  p.click('#next');
  const summary=p.doc.querySelector('#regSum .ticketline span:last-child')?.textContent||'';
  ok(summary==='خط اول\nخط دوم','پاسخ نهایی فاصلهٔ دور متن را می‌زداید و خط‌های داخلی را نگه می‌دارد');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:answer},picks:{},guests:[],fin:[],picked:[]});
  ok(area.value===answer,'متن چندخطی در پیش‌نویس با ترتیب خط‌ها بازیابی می‌شود');
  const unsafe='<img src=x onerror=alert(1)>';
  p.input('#qa0',unsafe);p.click('#next');
  ok(p.doc.querySelector('#regSum img')===null&&p.txt('#regSum').includes(unsafe),
    'متن بلند در خلاصه امن می‌ماند و HTML اجرایی نمی‌سازد');
  ok(p.network.length===0,'نوشتن و بازیابی متن بلند آفلاین می‌ماند');
}

/* ── ۴ب۲۶) عدد: رقم‌های فارسی/عربی، ممیز، جداکننده و حدها ── */
{
  console.log('── عدد محلی و محدودهٔ قابل‌اعتماد ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('number')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='number'&&S.fields[0].help.includes('رقم فارسی')")
      &&builder.doc.querySelector('#fdBoundsBox').style.display!=='none'
      &&builder.doc.querySelector('#fdMin').getAttribute('inputmode')==='decimal',
    'فیلد عددی راهنمای رقم محلی و تنظیم بازهٔ اعشاری دارد');
  builder.set('#fdMin','۱۰٫۵');builder.set('#fdMax','۲۰');
  ok(builder.window.eval('saveField()')===true
      &&builder.window.eval('S.fields[0].min===10.5&&S.fields[0].max===20'),
    'حداقل و حداکثر با رقم فارسی و ممیز فارسی به عدد درست تبدیل و ذخیره می‌شوند');
  builder.set('#fdMin','۲۵');builder.set('#fdMax','۲۰');builder.click('#btnNext');
  ok(builder.window.eval("S.step==='s1'&&S.fields[0].min===10.5&&S.fields[0].max===20")
      &&builder.doc.querySelector('#shField').classList.contains('on')&&builder.txt('#toast').includes('حداقل نمی‌تواند'),
    'حداقلِ بزرگ‌تر از حداکثر رد می‌شود؛ مقدار قبلی حفظ می‌ماند و سازنده جلو نمی‌رود');
  ok(builder.window.NORA_UI.parseLocalizedNumber('۱۲٫۵')===12.5
      &&builder.window.NORA_UI.parseLocalizedNumber('١٢٫٥')===12.5
      &&builder.window.NORA_UI.parseLocalizedNumber('۱٬۵۰۰')===1500
      &&builder.window.NORA_UI.parseLocalizedNumber('1,500')===1500
      &&builder.window.NORA_UI.parseLocalizedNumber('1,5')===null
      &&builder.window.NORA_UI.parseLocalizedNumber('۱۲,۳۴')===null
      &&builder.window.NORA_UI.parseLocalizedNumber('۱۲x')===null,
    'تبدیل عدد فارسی، عربی، ممیز و جداکنندهٔ هزارگان دقیق است و متن نامعتبر عدد جا زده نمی‌شود');
  const fields=[{id:'numeric-answer',t:'number',l:'تعداد',req:true,min:10.5,max:20,help:'یک عدد بنویسید.'}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-number-local',name:'فرم عددی',model:'datacollect',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-number-local&kind=other'),input=p.doc.querySelector('#qa0');
  ok(p.errors.length===0&&input.type==='text'&&input.inputMode==='decimal'
      &&input.getAttribute('aria-label')==='تعداد'&&input.getAttribute('data-min')==='10.5'
      &&input.getAttribute('data-max')==='20'&&input.placeholder==='مثلاً ۱۲٫۵',
    'پاسخ عددی با صفحه‌کلید اعشاری و پشتیبانی از رقم فارسی/عربی نمایش داده می‌شود');
  p.click('#next');p.click('#next');
  ok(p.txt('#toast').includes('اجباری')&&p.window.eval("cur==='qall'"),
    'پاسخ خالی برای فیلد عددی اجباری پذیرفته نمی‌شود');
  p.input('#qa0','۲۱');p.click('#next');
  ok(p.window.eval("cur==='qall'")&&p.txt('#toast').includes('حداکثر مقدار'),
    'عدد بالاتر از حداکثر، با پیام روشن متوقف می‌شود');
  p.input('#qa0','۱۰');p.click('#next');
  ok(p.window.eval("cur==='qall'")&&p.txt('#toast').includes('حداقل مقدار'),
    'عدد پایین‌تر از حداقل، با پیام روشن متوقف می‌شود');
  p.input('#qa0','۱۲x');p.click('#next');
  ok(p.window.eval("cur==='qall'")&&p.txt('#toast').includes('باید عدد باشد'),
    'ورودیِ ترکیب‌شده با متن به‌عنوان عدد معتبر پذیرفته نمی‌شود');
  p.input('#qa0','۱۲٫۵');p.click('#next');
  ok(p.window.eval("cur==='u12'")&&p.txt('#regSum').includes('۱۲٫۵'),
    'عدد فارسی با ممیز فارسی از محدوده عبور می‌کند و همان‌طور که نوشته شده نمایش داده می‌شود');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'١٢٫٥'},picks:{},guests:[],fin:[],picked:[]});
  ok(input.value==='١٢٫٥','پیش‌نویس عدد عربی دقیقاً بازیابی می‌شود');
  p.click('#next');
  ok(p.window.eval("cur==='u12'")&&p.txt('#regSum').includes('١٢٫٥'),
    'عدد عربی در پاسخ نهایی هم با همان مقدار محلی حفظ می‌شود');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'۱٬۵۰۰'},picks:{},guests:[],fin:[],picked:[]});
  p.click('#next');
  ok(p.window.eval("cur==='qall'")&&p.txt('#toast').includes('حداکثر مقدار'),
    'جداکنندهٔ هزارگان شناخته می‌شود؛ مقدار واقعی سنجیده می‌شود، نه متنِ خام');
  ok(p.network.length===0,'ورود، اعتبارسنجی و بازیابی عدد به سرویس بیرونی وصل نیست');
}

/* ── ۴ب۲۷) مبلغ: پاسخ عددی، نه مسیر پرداخت ── */
{
  console.log('── مبلغِ فرم و جدایی از پرداخت ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('amount')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='amount'&&S.fields[0].help.includes('پرداختی انجام نمی‌دهد')")
      &&builder.doc.querySelector('#fdBoundsBox').style.display!=='none',
    'فیلد مبلغ برای ورود داده است و راهنمای سازنده با پرداخت اشتباه گرفته نمی‌شود');
  const fields=[{id:'amount-answer',t:'amount',l:'مبلغ نمونه',req:true,min:1000,max:2000,
      help:'مبلغ را با رقم فارسی یا لاتین وارد کنید؛ این فیلد پرداختی انجام نمی‌دهد.'}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-amount-answer',name:'فرم مبلغ',model:'datacollect',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-amount-answer&kind=other'),input=p.doc.querySelector('#qa0');
  ok(p.errors.length===0&&input.type==='text'&&input.inputMode==='decimal'
      &&input.placeholder==='مثلاً ۲۵۰٬۰۰۰'&&p.txt('#qall').includes('پرداختی انجام نمی‌دهد')
      &&p.window.eval('paymentStepEnabled===false'),
    'پاسخ مبلغ با رقم فارسی می‌آید؛ ورودی توضیح می‌دهد که به پرداخت یا درگاه وصل نیست');
  ok(p.network.length===0&&!store.getItem('nora-receipts'),'پیش از ثبت، درخواست بیرونی یا رکورد رسید ساخته نمی‌شود');
  p.click('#next');p.set('#qa0','۱٬۲۵۰');p.click('#next');
  const regs=JSON.parse(store.getItem('nora-regs')||'[]'),row=regs.find(item=>item.form==='f-amount-answer');
  ok(p.window.eval("cur==='u12'")&&row?.ans?.[0]?.v==='۱٬۲۵۰'
      &&row.paymentStatus==='not-connected'&&row.notificationStatus==='not-sent'
      &&!store.getItem('nora-receipts')&&p.window.eval('paymentStepEnabled===false'),
    'مبلغ فقط در پاسخ محلی ثبت می‌شود؛ وضعیت پرداخت/اعلان وصل‌نشده است و رسید ساخته نمی‌شود');
  ok(p.network.length===0,'ثبت مقدار مبلغ هیچ پرداخت یا درخواست شبکه‌ای انجام نمی‌دهد');
}

/* ── ۴ب۲۸) تک‌انتخاب: دسترس‌پذیری صفحه‌کلید و انتخاب امن ── */
{
  console.log('── تک‌انتخاب و پیمایش با صفحه‌کلید ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('choice')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='choice'&&S.fields[0].opts.length===2")
      &&builder.doc.querySelector('#fdOptionsBox').style.display!=='none',
    'فیلد تک‌انتخاب با گزینه‌های پایهٔ قابل‌ویرایش ساخته می‌شود');
  const malicious='<img src=x onerror=alert(1)>',fields=[{id:'color-choice',t:'choice',l:'رنگ دلخواه',req:true,
      opts:['قرمز','آبی','سبز',malicious]}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-choice-accessible',name:'فرم تک‌انتخاب',model:'datacollect',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-choice-accessible&kind=other'),group=p.doc.querySelector('[data-qsel="0"]'),options=[...group.querySelectorAll('[role="radio"]')];
  ok(p.errors.length===0&&group.getAttribute('role')==='radiogroup'
      &&group.getAttribute('aria-label')==='رنگ دلخواه'&&options.length===4
      &&options.every(option=>option.getAttribute('aria-checked')==='false')
      &&options[0].tabIndex===0&&options.slice(1).every(option=>option.tabIndex===-1)
      &&group.querySelector('img')===null&&group.textContent.includes(malicious),
    'گزینه‌ها نام گروه، وضعیت انتخاب و متن امن دارند؛ یک گزینه با Tab در دسترس است');
  p.click('#next');p.click('#next');
  ok(p.txt('#toast').includes('اجباری')&&p.window.eval("cur==='qall'"),
    'تک‌انتخاب اجباری بدون انتخاب، جلو نمی‌رود');
  p.click('[data-qsel="0"] [role="radio"]');
  ok(options[0].getAttribute('aria-checked')==='true'&&options[0].tabIndex===0
      &&p.doc.querySelector('#qa0').value==='قرمز'&&p.doc.activeElement===options[0],
    'با انتخاب گزینه، پاسخ محلی و وضعیت دسترس‌پذیر هم‌زمان به‌روز می‌شوند');
  options[0].dispatchEvent(new p.window.KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true}));
  ok(options[1].getAttribute('aria-checked')==='true'&&options[1].tabIndex===0
      &&options[0].tabIndex===-1&&p.doc.querySelector('#qa0').value==='آبی'&&p.doc.activeElement===options[1],
    'کلید جهت‌دار گزینهٔ بعدی را انتخاب و کانون صفحه‌کلید را همراه آن جابه‌جا می‌کند');
  options[1].dispatchEvent(new p.window.KeyboardEvent('keydown',{key:' ',bubbles:true,cancelable:true}));
  ok(options[1].getAttribute('aria-checked')==='true','کلید فاصله پاسخ تک‌انتخابی را فعال می‌کند');
  p.click('#next');
  ok(p.txt('#regSum').includes('آبی'),'همان گزینه‌ای که با صفحه‌کلید انتخاب شد در خلاصه می‌آید');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'سبز'},picks:{},guests:[],fin:[],picked:[]});
  ok(options[2].getAttribute('aria-checked')==='true'&&options[2].tabIndex===0
      &&p.doc.querySelector('#qa0').value==='سبز','بازیابی پیش‌نویس، گزینه و وضعیت صفحه‌کلید را هماهنگ نگه می‌دارد');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:malicious},picks:{},guests:[],fin:[],picked:[]});p.click('#next');
  ok(p.doc.querySelector('#regSum img')===null&&p.txt('#regSum').includes(malicious),
    'متن گزینهٔ دلخواه در خلاصه هم HTML اجرایی نمی‌سازد');
  ok(p.network.length===0,'انتخاب تک‌گزینه‌ای و پیمایش صفحه‌کلید بدون سرویس بیرونی کار می‌کند');
}

/* ── ۴ب۲۹) کشویی: مقدار خالی روشن، انتخاب و پیش‌نویس امن ── */
{
  console.log('── فهرست کشویی و انتخاب روشن ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('dropdown')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='dropdown'&&S.fields[0].opts.length===2")
      &&builder.doc.querySelector('#fdOptionsBox').style.display!=='none',
    'فیلد کشویی با دو گزینهٔ پایه و ویرایش ساده ساخته می‌شود');
  const unsafe='<img src=x onerror=alert(1)>',fields=[{id:'region-choice',t:'dropdown',l:'منطقه',req:true,
      opts:['شمال','مرکز',unsafe]}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-dropdown',name:'فرم کشویی',model:'datacollect',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-dropdown&kind=other'),select=p.doc.querySelector('#qa0');
  ok(p.errors.length===0&&select.tagName==='SELECT'&&select.getAttribute('aria-label')==='منطقه'
      &&select.value===''&&select.options[0].textContent==='یک مورد را انتخاب کنید'
      &&select.options.length===4&&p.doc.querySelector('#qall img')===null,
    'کشویی بدون پیش‌انتخاب، با نام قابل‌فهم و گزینه‌های متنیِ امن باز می‌شود');
  p.click('#next');p.click('#next');
  ok(p.txt('#toast').includes('اجباری')&&p.window.eval("cur==='qall'"),
    'کشویی اجباری تا انتخاب کاربر خالی می‌ماند');
  p.set('#qa0','مرکز');
  ok(select.value==='مرکز'&&p.doc.querySelector('#qa0').value==='مرکز',
    'انتخاب کشویی پاسخ فرم را همان لحظه به‌روز می‌کند');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'شمال'},picks:{},guests:[],fin:[],picked:[]});
  ok(select.value==='شمال','گزینهٔ انتخاب‌شده از پیش‌نویس دقیق بازیابی می‌شود');
  p.click('#next');
  ok(p.txt('#regSum').includes('شمال'),'خلاصه همان مقدار بازیابی‌شده را نشان می‌دهد');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:unsafe},picks:{},guests:[],fin:[],picked:[]});p.click('#next');
  ok(p.doc.querySelector('#regSum img')===null&&p.txt('#regSum').includes(unsafe),
    'برچسب گزینه در صفحه و خلاصه متن امن است و HTML اجرا نمی‌شود');
  ok(p.network.length===0,'کشویی و بازیابی آن کاملاً محلی می‌مانند');
}

/* ── ۴ب۳۰) چندانتخاب: صفحه‌کلید، شمارنده و سقف انتخاب ── */
{
  console.log('── چندانتخاب و حد انتخاب ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('multi')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='multi'&&S.fields[0].opts.length===2")
      &&builder.doc.querySelector('#fdMultiLimitsBox').style.display!=='none',
    'فیلد چندانتخاب گزینه‌های آماده و تنظیم حداقل/حداکثر دارد');
  const fields=[{id:'multi-answer',t:'multi',l:'موضوع‌ها',req:false,minSelect:2,maxSelect:2,opts:['الف','ب','ج']}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-multi-accessible',name:'فرم چندانتخاب',model:'datacollect',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-multi-accessible&kind=other'),group=p.doc.querySelector('[data-qmul="0"]'),options=[...group.querySelectorAll('[role="checkbox"]')];
  ok(p.errors.length===0&&group.getAttribute('role')==='group'&&group.getAttribute('aria-label')==='موضوع‌ها'
      &&options.length===3&&options.every(o=>o.getAttribute('aria-checked')==='false'&&o.tabIndex===0)
      &&p.txt('#qall').includes('حداقل ۲ · حداکثر ۲ انتخاب'),
    'هر گزینه مثل checkbox قابل‌دسترسی است و حد انتخاب کنار شمارنده دیده می‌شود');
  p.click('#next');p.click('#next');
  ok(p.txt('#toast').includes('دست‌کم')&&p.window.eval("cur==='qall'"),
    'حداقل انتخاب حتی برای فیلدی که کلید اجباری‌اش خاموش است رعایت می‌شود');
  options[0].dispatchEvent(new p.window.KeyboardEvent('keydown',{key:' ',bubbles:true,cancelable:true}));
  ok(options[0].getAttribute('aria-checked')==='true'&&p.doc.querySelector('#qa0').value==='الف'
      &&p.txt('[data-qmul-count="0"]').includes('۱ انتخاب'),
    'کلید فاصله گزینه را برمی‌گزیند، شمارنده را به‌روز می‌کند و پاسخ را ذخیره می‌کند');
  p.click('#next');
  ok(p.txt('#toast').includes('دست‌کم')&&p.window.eval("cur==='qall'"),
    'ادامه با کمتر از حداقل انتخاب متوقف می‌شود');
  options[1].dispatchEvent(new p.window.KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));
  ok(options[1].getAttribute('aria-checked')==='true'&&p.doc.querySelector('#qa0').value==='الف، ب'
      &&p.txt('[data-qmul-count="0"]').includes('۲ انتخاب'),
    'Enter انتخاب دوم را ثبت می‌کند و پاسخ چندگزینه‌ای را به‌روزرسانی می‌کند');
  options[2].dispatchEvent(new p.window.KeyboardEvent('keydown',{key:' ',bubbles:true,cancelable:true}));
  ok(options[2].getAttribute('aria-checked')==='false'&&p.doc.querySelector('#qa0').value==='الف، ب'
      &&p.txt('#toast').includes('حداکثر'),
    'رسیدن به حداکثر، انتخاب اضافه را با پیام روشن رد می‌کند');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'الف، ج'},picks:{},guests:[],fin:[],picked:[]});
  ok(options[0].getAttribute('aria-checked')==='true'&&options[2].getAttribute('aria-checked')==='true'
      &&p.doc.querySelector('#qa0').value==='الف، ج'&&p.txt('[data-qmul-count="0"]').includes('۲ انتخاب'),
    'پیش‌نویس وضعیت هر checkbox، پاسخ و شمارنده را با هم بازیابی می‌کند');
  p.click('#next');
  ok(p.window.eval("cur==='u12'")&&p.txt('#regSum').includes('الف، ج'),
    'پاسخ چندانتخابیِ بازیابی‌شده با حدهای معتبر نهایی می‌شود');
  ok(p.network.length===0,'چندانتخاب و شمارش گزینه‌ها به سرویس بیرونی وصل نیستند');
}

/* ── ۴ب۳۱) بله/خیر: دو پاسخ روشن و بدون پیش‌فرض ── */
{
  console.log('── پاسخ بله یا خیر ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('yesno')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='yesno'&&JSON.stringify(S.fields[0].opts.map(o=>o.l))===JSON.stringify(['بله','خیر'])")
      &&builder.doc.querySelector('#fdOptionsBox').style.display==='none',
    'نوع بله/خیر گزینه‌های ثابت دارد و سازنده مجبور به ساخت فهرست نیست');
  const fields=[{id:'consent-answer',t:'yesno',l:'مایل هستید؟',req:true}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-yes-no',name:'فرم بله یا خیر',model:'datacollect',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-yes-no&kind=other'),group=p.doc.querySelector('[data-qsel="0"]'),options=[...group.querySelectorAll('[role="radio"]')];
  ok(p.errors.length===0&&group.getAttribute('role')==='radiogroup'&&group.getAttribute('aria-label')==='مایل هستید؟'
      &&options.map(o=>o.textContent.trim()).join('،')==='بله،خیر'
      &&options.every(o=>o.getAttribute('aria-checked')==='false'),
    'دو پاسخ «بله» و «خیر» بی‌طرفانه و با نام دسترس‌پذیر نمایش داده می‌شوند');
  p.click('#next');p.click('#next');
  ok(p.txt('#toast').includes('اجباری')&&p.window.eval("cur==='qall'"),
    'فیلد بله/خیر اجباری تا انتخاب خود کاربر خالی می‌ماند');
  p.click('[data-qsel="0"] [role="radio"]:last-child');
  ok(p.doc.querySelector('#qa0').value==='خیر'&&options[1].getAttribute('aria-checked')==='true',
    'انتخاب «خیر» هم مثل «بله» پاسخ معتبر است و گم نمی‌شود');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'بله'},picks:{},guests:[],fin:[],picked:[]});
  ok(p.doc.querySelector('#qa0').value==='بله'&&options[0].getAttribute('aria-checked')==='true'
      &&options[1].getAttribute('aria-checked')==='false','بازیابی پیش‌نویس، پاسخ بله/خیر را درست انتخاب می‌کند');
  p.click('#next');
  ok(p.txt('#regSum').includes('بله')&&p.window.eval("cur==='u12'"),'پاسخ بازیابی‌شده در خلاصه و پایان محلی ثبت می‌شود');
  ok(p.network.length===0,'فیلد بله/خیر برای پاسخ‌گویی به سرویس بیرونی نیاز ندارد');
}

/* ── ۴ب۳۲) جنسیت: پاسخ اختیاری و حفظ حریم شخصی ── */
{
  console.log('── فیلد جنسیت و حق ندادن پاسخ ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('gender')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='gender'&&S.fields[0].req===false&&JSON.stringify(S.fields[0].opts.map(o=>o.l))===JSON.stringify(['زن','مرد','ترجیح می‌دهم نگویم'])")
      &&builder.doc.querySelector('#fdOptionsBox').style.display!=='none'
      &&builder.doc.querySelector('#fdHelp').value.includes('ترجیح می‌دهم نگویم'),
    'سازنده گزینه‌های روشن و قابل‌ویرایش می‌دهد و پاسخ را به‌طور پیش‌فرض اجباری نمی‌کند');
  const fields=[{id:'gender-answer',t:'gender',l:'جنسیت',req:false,opts:[]}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-gender',name:'فرم جنسیت',model:'datacollect',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-gender&kind=other'),group=p.doc.querySelector('[data-qsel="0"]'),options=[...group.querySelectorAll('[role="radio"]')];
  ok(p.errors.length===0&&options.map(o=>o.textContent.trim()).join('، ')==='زن، مرد، ترجیح می‌دهم نگویم'
      &&options.every(o=>o.getAttribute('aria-checked')==='false'),
    'فهرست پیش‌فرض شامل گزینهٔ ندادن پاسخ است و هیچ موردی خودکار انتخاب نمی‌شود');
  p.click('#next');p.click('#next');
  ok(p.window.eval("cur==='u12'")&&p.doc.querySelector('#qa0').value==='',
    'وقتی فیلد اختیاری است، پاسخ‌دهنده می‌تواند بدون انتخاب ادامه دهد');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'ترجیح می‌دهم نگویم'},picks:{},guests:[],fin:[],picked:[]});
  ok(p.doc.querySelector('#qa0').value==='ترجیح می‌دهم نگویم'
      &&options[2].getAttribute('aria-checked')==='true','پاسخ «ترجیح می‌دهم نگویم» در فرم و پیش‌نویس درست نگه داشته می‌شود');
  p.click('#next');
  ok(p.txt('#regSum').includes('ترجیح می‌دهم نگویم'),'خلاصه فقط همان پاسخی را نشان می‌دهد که خود کاربر انتخاب کرده است');
  ok(p.network.length===0,'پاسخ جنسیت هیچ درخواست بیرونی ارسال نمی‌کند');
}

/* ── ۴ب۳۳) وضعیت تأهل: فهرست قابل‌ویرایش و پاسخ اختیاری ── */
{
  console.log('── وضعیت تأهل و انتخاب نکردن ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('marital')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='marital'&&S.fields[0].req===false&&JSON.stringify(S.fields[0].opts.map(o=>o.l))===JSON.stringify(['مجرد','متأهل','ترجیح می‌دهم نگویم'])")
      &&builder.doc.querySelector('#fdOptionsBox').style.display!=='none'
      &&builder.doc.querySelector('#fdHelp').value.includes('پاسخ لازم نیست'),
    'فهرست وضعیت تأهل قابل‌ویرایش است، پاسخ‌ندادن را پوشش می‌دهد و اجباری نیست');
  const fields=[{id:'marital-answer',t:'marital',l:'وضعیت تأهل',req:false,opts:[]}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-marital',name:'فرم تأهل',model:'datacollect',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-marital&kind=other'),group=p.doc.querySelector('[data-qsel="0"]'),options=[...group.querySelectorAll('[role="radio"]')];
  ok(p.errors.length===0&&options.map(o=>o.textContent.trim()).join('، ')==='مجرد، متأهل، ترجیح می‌دهم نگویم'
      &&options.every(o=>o.getAttribute('aria-checked')==='false'),
    'هیچ وضعیت تأهلی پیش‌فرض انتخاب نمی‌شود و گزینهٔ ندادن پاسخ در فهرست هست');
  p.click('#next');p.click('#next');
  ok(p.window.eval("cur==='u12'")&&p.doc.querySelector('#qa0').value==='',
    'پرسش اختیاری اجازه می‌دهد بدون اعلام وضعیت تأهل ادامه بدهید');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'متأهل'},picks:{},guests:[],fin:[],picked:[]});
  ok(p.doc.querySelector('#qa0').value==='متأهل'&&options[1].getAttribute('aria-checked')==='true',
    'پاسخ انتخاب‌شده از پیش‌نویس بازیابی می‌شود');
  p.click('#next');
  ok(p.txt('#regSum').includes('متأهل'),'خلاصه فقط انتخاب خود پاسخ‌دهنده را نگه می‌دارد');
  ok(p.network.length===0,'وضعیت تأهل در پیش‌نمایش محلی می‌ماند و جایی فرستاده نمی‌شود');
}

/* ── ۴ب۳۴) گزینهٔ تصویری: متن امن تا اتصال رسانهٔ واقعی ── */
{
  console.log('── گزینهٔ تصویریِ نمایشی ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('imgchoice')");
  ok(builder.window.eval("S.fields.length===1&&S.fields[0].t==='imgchoice'&&S.fields[0].opts.length===2")
      &&builder.doc.querySelector('#fdStruct').textContent.includes('گزینه‌های متنی')
      &&builder.doc.querySelector('#fdHelp').value.includes('تصویر واقعی'),
    'سازنده می‌گوید گزینهٔ تصویری فعلاً برچسب متنی است و رسانهٔ واقعی وصل نیست');
  const unsafe='<img src=x onerror=alert(1)>',fields=[{id:'image-choice',t:'imgchoice',l:'انتخاب تصویر',req:true,
      opts:['گزینهٔ یک','گزینهٔ دو',unsafe]}],
    store=makeStore({'nora-forms':JSON.stringify([{id:'f-imgchoice',name:'فرم گزینهٔ تصویری',model:'datacollect',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-imgchoice&kind=other'),group=p.doc.querySelector('[data-qsel="0"]'),options=[...group.querySelectorAll('[role="radio"]')];
  ok(p.errors.length===0&&group.getAttribute('role')==='radiogroup'&&options.length===3
      &&group.querySelector('img')===null&&p.txt('#qall').includes('گزینه‌ها متنی‌اند')
      &&p.txt('#qall').includes('تصویر پیوست نشده است'),
    'پاسخ‌دهنده هم می‌بیند که گزینه‌ها متنی‌اند؛ رسانهٔ ساختگی یا بارگذاری جعلی وجود ندارد');
  p.click('#next');p.click('#next');
  ok(p.txt('#toast').includes('اجباری')&&p.window.eval("cur==='qall'"),
    'گزینهٔ تصویری اجباری تا انتخاب پاسخ‌دهنده خالی می‌ماند');
  p.click('[data-qsel="0"] [role="radio"]:nth-child(2)');
  ok(p.doc.querySelector('#qa0').value==='گزینهٔ دو','گزینهٔ تصویریِ نمایشی مثل تک‌انتخاب ثبت محلی می‌شود');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:'گزینهٔ یک'},picks:{},guests:[],fin:[],picked:[]});
  ok(p.doc.querySelector('#qa0').value==='گزینهٔ یک','انتخاب متنی پس از بازگشت از پیش‌نویس بازیابی می‌شود');
  p.click('#next');
  ok(p.txt('#regSum').includes('گزینهٔ یک')&&p.doc.querySelector('#regSum img')===null,
    'خلاصه متن انتخاب‌شده را امن می‌سازد و عکس واقعی ادعا نمی‌کند');
  p.window.restoreDraft({cur:'qall',inputs:{qa0:unsafe},picks:{},guests:[],fin:[],picked:[]});p.click('#next');
  ok(p.doc.querySelector('#regSum img')===null&&p.txt('#regSum').includes(unsafe),
    'برچسب دلخواه تصویری هم به‌صورت متن escape می‌شود');
  ok(p.network.length===0,'گزینهٔ تصویری هیچ تصویر یا داده‌ای از شبکه بارگیری نمی‌کند');
}

/* ── ۴ب۳۵) متن پایانی و پیوندهای امن، بدون خروج به وب ── */
{
  console.log('\n── متن پایانی و پیوندها ──');
  const attack='<img src=x onerror=alert(1)>',form={id:'f-end-links',name:'فرم پیوند نمونه',model:'questionnaire',need:'other',
    display:'all',after:'view',endText:'متن پایانی '+attack,fields:[{id:'q',t:'text',l:'پاسخ',req:false}],
    links:[{t:'صفحهٔ رویداد نمونه',u:'event.html?id=e5'},{t:'پیوند بیرونی '+attack,u:'https://attacker.example/collect'},
      {t:'جاوااسکریپت',u:'javascript:alert(1)'},{t:'مسیر ممنوع',u:'../admin.html'}]};
  const store=makeStore({'nora-forms':JSON.stringify([form])}),p=await load('form.html',store,'?fid=f-end-links&kind=other');
  p.window.__NORA_FORM_PREVIEW.finish();
  const links=p.doc.querySelectorAll('#endLinks .linkbtn'),anchor=p.doc.querySelector('#endLinks a[href]');
  ok(p.errors.length===0&&links.length===4&&anchor?.getAttribute('href')==='event.html?id=e5'
      &&p.doc.querySelectorAll('#endLinks a').length===1,
    'از میان پیوندهای پایانی فقط صفحهٔ داخلیِ مجاز لینک واقعی می‌شود');
  ok(p.doc.querySelectorAll('#endLinks [aria-disabled="true"]').length===3
      &&p.doc.querySelector('#endLinks img')===null&&p.txt('#endLinks').includes(attack),
    'پیوند بیرونی، javascript و مسیر ممنوع غیرفعال و عنوانهای HTML به‌صورت متن امن نشان داده می‌شوند');
  ok(p.doc.querySelector('#endText').textContent.includes(attack)&&p.doc.querySelector('#endText img')===null,
    'متن پایانی هم به‌صورت متن نشان داده می‌شود و HTML ارسالی اجرا نمی‌شود');
  ok(p.network.length===0&&p.opened.length===0&&externalAnchors(p).length===0,
    'پایان فرم هیچ درخواست، پنجره یا پیوند بیرونی باز نمی‌کند');
}

/* ── ۴ج) سازگاری نوع انتخابی legacy ── */
{
  console.log('\n── سازگاری select قدیمی با شرط گزینه‌ای ──');
  const fields=[
    {id:'legacy-select',t:'select',l:'گزینهٔ قدیمی',options:['الف','ب'],req:false},
    {id:'legacy-dependent',t:'text',l:'وابسته',req:false,conditions:[{field:'legacy-select',op:'eq',value:'الف'}]},
  ];
  const store=makeStore({'nora-forms':JSON.stringify([{id:'f-condition-select-legacy',name:'آزمون select قدیمی',model:'questionnaire',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-condition-select-legacy&kind=other');
  const visible=p.window.__NORA_FORM_PREVIEW.visibleFields.find(field=>field.id==='legacy-dependent')?.visible===true;
  ok(p.errors.length===0&&p.window.__REG.q[0].t==='dropdown'&&p.doc.querySelector('#qa0').tagName==='SELECT'&&!visible,
    'نوع select قدیمی در پیش‌نمایش به پرسش گزینه‌ای تبدیل و مقدار خالی بسته نگه داشته شد');
  p.set('#qa0','الف');
  ok(p.window.__NORA_FORM_PREVIEW.visibleFields.find(field=>field.id==='legacy-dependent')?.visible===true,
    'قاعدهٔ legacy گزینهٔ انتخاب‌شده را با تطبیق دقیق تشخیص می‌دهد');
}

/* ── ۴د) شرط‌های ترکیبی، AND/OR و عملگرهای وابسته به نوع پاسخ ── */
{
  console.log('\n── شرط‌های چندگانه و نوع‌محور ──');
  const fields=[
    {id:'source-text',t:'text',l:'متن مرجع',req:false},
    {id:'source-number',t:'number',l:'عدد مرجع',req:false},
    {id:'source-choice',t:'choice',l:'گزینهٔ مرجع',req:false,opts:['A','B']},
    {id:'source-multi',t:'multi',l:'چندانتخابی مرجع',req:false,opts:['Red','Redwood','Blue']},
    {id:'all-rules',t:'text',l:'همهٔ قواعد',req:false,conditionLogic:'all',conditions:[
      {field:'source-text',op:'starts',value:'Al'},
      {field:'source-number',op:'gte',value:'5'},
      {field:'source-choice',op:'eq',value:'B'}]},
    {id:'any-rules',t:'text',l:'هرکدام از قواعد',req:false,conditionLogic:'any',conditions:[
      {field:'source-choice',op:'eq',value:'A'},
      {field:'source-number',op:'gt',value:'9'}]},
    {id:'multi-contains',t:'text',l:'گزینهٔ چندانتخابی حاضر',req:false,conditions:[{field:'source-multi',op:'contains',value:'Red'}]},
    {id:'multi-not-contains',t:'text',l:'گزینهٔ چندانتخابی غایب',req:false,conditions:[{field:'source-multi',op:'ncontains',value:'Red'}]}];
  const store=makeStore({'nora-forms':JSON.stringify([{id:'f-condition-groups',name:'آزمون قواعد ترکیبی',model:'questionnaire',need:'other',display:'all',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-condition-groups&kind=other');
  const visible=id=>p.window.__NORA_FORM_PREVIEW.visibleFields.find(field=>field.id===id)?.visible===true;
  ok(p.errors.length===0&&!visible('all-rules')&&!visible('any-rules')&&!visible('multi-contains')&&!visible('multi-not-contains'),
    'قواعد گروهی بدون پاسخ، و ncontains روی چندانتخابی خالی، پیش‌فرض بسته دارند');
  p.set('#qa0','Alpha');p.set('#qa1','8');p.click('#qall [data-qsel="2"] .opt:last-child');p.click('#qall [data-qmul="3"] .opt:nth-child(3)');
  ok(visible('all-rules')&&!visible('any-rules')&&!visible('multi-contains')&&visible('multi-not-contains'),
    'AND به همهٔ قواعد نیاز دارد؛ OR فقط قواعد درست را می‌سنجد و گزینهٔ multi را دقیق تطبیق می‌دهد');
  p.click('#qall [data-qsel="2"] .opt:first-child');
  ok(!visible('all-rules')&&visible('any-rules'),
    'OR با یک قاعدهٔ درست باز می‌شود، ولی AND با شکست یک قاعده بسته می‌ماند');
  p.set('#qa1','10');p.click('#qall [data-qsel="2"] .opt:last-child');
  ok(visible('all-rules')&&visible('any-rules'),'gte روی عدد و ترکیب هم‌زمان قواعد دوباره ارزیابی شدند');
  p.click('#qall [data-qmul="3"] .opt:first-child');
  ok(visible('multi-contains')&&!visible('multi-not-contains'),
    'contains و ncontains برای چندانتخابی عضویت دقیق گزینه را می‌سنجند، نه تطبیق زیررشته‌ای');
}

/* ── ۴هـ) جریان یک‌پرسشی با شرط‌های پویا ── */
{
  console.log('\n── جریان تک‌پرسشی و پرش از فیلد پنهان ──');
  const fields=[
    {id:'source-choice',t:'choice',l:'گزینهٔ مرجع',opts:['A','B'],req:false},
    {id:'source-text',t:'text',l:'متن مرجع',req:false},
    {id:'any-rule',t:'text',l:'فیلد OR',req:false,conditionLogic:'any',conditions:[
      {field:'source-choice',op:'eq',value:'A'},{field:'source-text',op:'eq',value:'باز'}]},
    {id:'all-rule',t:'text',l:'فیلد AND',req:false,conditionLogic:'all',conditions:[
      {field:'source-choice',op:'eq',value:'A'},{field:'source-text',op:'eq',value:'باز'}]},
  ];
  const store=makeStore({'nora-forms':JSON.stringify([{id:'f-condition-flow',name:'آزمون جریان شرطی',model:'questionnaire',need:'other',display:'one',fields,fin:[]}])});
  const p=await load('form.html',store,'?fid=f-condition-flow&kind=other');
  const visible=id=>p.window.__NORA_FORM_PREVIEW.visibleFields.find(field=>field.id===id)?.visible===true;
  ok(p.errors.length===0&&!visible('any-rule')&&!visible('all-rule'),'در حالت تک‌پرسشی هر دو گروه پیش از پاسخ مرجع پنهان‌اند');
  p.click('#next');p.click('[data-qsel="0"] .opt:first-child');
  ok(p.window.eval('cur')==='qp0'&&visible('any-rule')&&!visible('all-rule'),
    'OR پس از پاسخ درست نمایان می‌شود و AND تا تحقق همهٔ قواعد پنهان می‌ماند');
  p.click('#next');p.set('#qa1','باز');
  ok(visible('all-rule')&&p.window.eval("ORDER.includes('qp3')"),'تغییر پاسخ در مرحلهٔ قبل، فهرست صفحات وابسته را دوباره می‌سازد');
  p.click('#next');p.set('#qa1','');
  ok(p.window.eval('cur')==='qp2'&&visible('any-rule')&&!visible('all-rule')&&!p.window.eval("ORDER.includes('qp3')"),
    'با پس‌گرفتن پاسخ، صفحهٔ AND از مسیر تک‌پرسشی حذف می‌شود بدون پرش از صفحهٔ جاری');
  p.click('#next');
  ok(p.window.eval("cur==='u12'"),'مسیر تک‌پرسشی از روی صفحهٔ شرطیِ پنهان عبور می‌کند و به پایان محلی می‌رسد');
}

/* ── ۴و) حداقل/حداکثر انتخاب چندگانه ── */
{
  console.log('\n── حداقل و حداکثر انتخاب چندگانه ──');
  const fields=[{id:'bounded-multi',t:'multi',l:'انتخاب‌های محدود',opts:['قرمز','آبی','سبز'],req:false,minSelect:2,maxSelect:2}];
  const store=makeStore({'nora-forms':JSON.stringify([{id:'f-multi-bounds',name:'آزمون حدود چندانتخابی',model:'questionnaire',need:'other',display:'all',fields,fin:[] }])});
  const p=await load('form.html',store,'?fid=f-multi-bounds&kind=other');
  p.click('#next');p.click('#next');
  ok(p.window.eval("cur==='qall'")&&p.txt('#toast').includes('دست‌کم'),
    'حداقل انتخاب مستقل از اجباری‌بودن فیلد بررسی می‌شود');
  p.click('[data-qmul="0"] .opt:first-child');
  ok(p.doc.querySelector('[data-qmul-count="0"]').textContent.includes('۱'),
    'شمار انتخاب‌شده پس از هر تغییر به‌روز می‌شود');
  p.click('#next');
  ok(p.window.eval("cur==='qall'")&&p.txt('#toast').includes('دست‌کم'),
    'پاسخ کمتر از حداقل اجازهٔ ثبت نمی‌گیرد');
  p.click('[data-qmul="0"] .opt:nth-child(2)');
  p.click('[data-qmul="0"] .opt:nth-child(3)');
  ok(p.doc.querySelectorAll('[data-qmul="0"] .opt.on').length===2&&p.txt('#toast').includes('حداکثر'),
    'پس از رسیدن به حداکثر، گزینهٔ تازه انتخاب نمی‌شود و انتخاب‌های قبلی می‌مانند');
  p.click('#next');
  ok(p.window.eval("cur==='u12'"),'تعداد انتخاب در بازهٔ مجاز اجازهٔ پایان پاسخ محلی می‌دهد');

  const requiredStore=makeStore({'nora-forms':JSON.stringify([{id:'f-required-multi',name:'چندانتخابی اجباری',model:'questionnaire',need:'other',display:'all',fields:[
    {id:'required-multi',t:'multi',l:'گزینه‌های اجباری',req:true,opts:['الف','ب']}
  ],fin:[]}])});
  const requiredPage=await load('form.html',requiredStore,'?fid=f-required-multi&kind=other');
  requiredPage.click('#next');requiredPage.set('#qa0','گزینهٔ ناشناخته');requiredPage.click('#next');
  ok(requiredPage.window.eval("cur==='qall'")&&requiredPage.txt('#toast').includes('اجباری'),
    'مقدار پنهان یا ناسازگار بدون انتخاب واقعی، چندانتخابی اجباری را دور نمی‌زند');
}

/* ── ۵) خاموش‌کردن نمایش فرم از کارت رویداد ── */
{
  console.log('\n── نمایش فرم در کارت رویداد ──');
  const store=makeStore();
  store.setItem('nora-admin',JSON.stringify({added:[{id:'ev-hidden',n:'رویداد محلی',on:'1410/07/08',end:'1410/07/08',time:'16:00',place:'آنلاین',cap:25,reg:0,sessions:1}]}));
  store.setItem('nora-forms',JSON.stringify([{id:'f-hidden',name:'فرم پنهان',need:'reg',ev:'ev-hidden',eventVisible:false,fields:[{id:'x',t:'text',l:'پرسش'}],fin:[]} ]));
  const p=await load('event.html',store,'?id=ev-hidden');
  ok(p.errors.length===0,'کارت رویداد سفارشی بی‌خطا بار شد'+(p.errors.length?': '+p.errors[0]:''));
  ok(!p.doc.querySelector('#reg')&&!p.doc.querySelector('[data-copy-reg]')&&!!p.doc.querySelector('.registration-notice'),
    'فرم پنهان هیچ دکمه یا پیوند ثبت‌نامی نمی‌سازد و وضعیت را روشن می‌گوید');
  const draftStore=makeStore();
  draftStore.setItem('nora-admin',JSON.stringify({added:[{id:'ev-draft',n:'رویداد پیش‌نویس',on:'1405/07/08',end:'1405/07/08',time:'16:00',place:'آنلاین',cap:25,reg:0,sessions:1}]}));
  draftStore.setItem('nora-forms',JSON.stringify([{id:'f-draft',name:'فرم پیش‌نویس',need:'reg',ev:'ev-draft',status:'draft',serverDraft:true,on:1,eventVisible:true,fields:[{id:'x',t:'text',l:'پرسش'}]}]));
  const draftPage=await load('event.html',draftStore,'?id=ev-draft');
  ok(!draftPage.doc.querySelector('#reg')&&!draftPage.doc.querySelector('[data-copy-reg]'),
    'پیش‌نویس سروری حتی با eventVisible روشن، به کارت عمومی رویداد وصل نمی‌شود');
}

/* ── ۶) فرم‌ساز: QR فرم فقط دادهٔ متنی نمونه، کارت و درگاه همیشه خاموش ── */
{
  console.log('\n── فرم‌ساز و QR ──');
  const apiMock=makeFormsApiMock(),store=makeStore({
    'nora-admin-session':JSON.stringify({u:'owner',role:'admin',personKey:'p1',at:Date.now()}),
    'nora-finance':JSON.stringify({gates:[{k:'card',on:1}],rot:'cap',cards:[
      {id:'receipt-card',bank:'بانک نمونه',no:'4111 1111 1111 1111',name:'حساب سازمان',cap:5,dailyMax:500000,used:0,usedAmount:0}
    ]})}),p=await load('create.html',store,'',apiMock.fetch);
  ok(p.errors.length===0,'فرم‌ساز بی‌خطا بار شد'+(p.errors.length?': '+p.errors[0]:''));
  p.window.eval(`S.fields=[{id:'base',t:'text',l:'پایه'},
    {id:'choice-base',t:'choice',l:'گزینهٔ مرجع',opts:[{l:'A'},{l:'B'}]},
    {id:'legacy-select-base',t:'select',l:'گزینهٔ legacy',options:['Old A','Old B']},
    {id:'number-base',t:'number',l:'عدد مرجع'},
    {id:'dependent',t:'text',l:'وابسته',condField:'base',condOp:'eq',condVal:'sample'},
    {id:'decimal-dependent',t:'text',l:'قاعدهٔ اعشاری',condField:'number-base',condOp:'gt',condVal:''}];
    renderCanvas();editField('dependent')`);
  const editorOps=p.all('#fdCondOp option').map(option=>option.value);
  ok(JSON.stringify(editorOps)===JSON.stringify(['eq','ne','contains','ncontains','starts','nstarts','ends','nends','empty','nempty']),
    'ویرایشگر متن عملگرهای سازگار با نوع مرجع را نشان می‌دهد');
  const operatorMatrix=JSON.parse(p.window.eval(`JSON.stringify({
    number:conditionOperatorsFor('number'),date:conditionOperatorsFor('date'),
    choice:conditionOperatorsFor('choice'),legacySelect:conditionOperatorsFor('select'),
    multi:conditionOperatorsFor('multi'),file:conditionOperatorsFor('file'),terms:conditionOperatorsFor('terms')})`));
  ok(JSON.stringify(operatorMatrix)===JSON.stringify({
    number:['eq','ne','gt','gte','lt','lte','empty','nempty'],date:['eq','ne','gt','gte','lt','lte','empty','nempty'],
    choice:['eq','ne','empty','nempty'],legacySelect:['eq','ne','empty','nempty'],
    multi:['contains','ncontains','empty','nempty'],file:['empty','nempty'],terms:['empty','nempty']}),
    'ماتریس عملگرهای عدد، تاریخ، گزینه، چندانتخاب، فایل و تأیید با نوع مرجع سازگار است');
  p.set('#fdCondOp','empty');
  ok(p.doc.querySelector('#fdCondVal').disabled&&p.doc.querySelector('#fdCondVal').style.display==='none'
      &&p.doc.querySelector('#fdCondVal').value==='',
    'انتخاب «خالی است» ورودی مقدار را پنهان، غیرفعال و پاک می‌کند');
  p.window.eval('saveField()');
  ok(p.window.eval("S.fields.find(f=>f.id==='dependent').condOp==='empty'&&S.fields.find(f=>f.id==='dependent').condVal===''"),
    'عملگر خالی بدون مقدار اضافی در تنظیم فیلد ذخیره می‌شود');
  p.window.eval("editField('dependent')"); p.set('#fdCondOp','nempty');
  ok(p.doc.querySelector('#fdCondVal').disabled&&p.doc.querySelector('#fdCondVal').style.display==='none'
      &&p.doc.querySelector('#fdCondVal').value==='',
    'انتخاب «خالی نیست» نیز ورودی مقدار را پنهان و پاک می‌کند');
  p.window.eval('saveField()');
  ok(p.window.eval("S.fields.find(f=>f.id==='dependent').condOp==='nempty'&&S.fields.find(f=>f.id==='dependent').condVal===''"),
    'عملگر nempty نیز بدون مقدار اضافی ذخیره می‌شود');
  p.window.eval("editField('dependent')"); p.set('#fdCondOp','ncontains');
  p.set('#fdCondVal','needle'); p.window.eval('saveField()');
  ok(!p.doc.querySelector('#fdCondVal').disabled&&p.doc.querySelector('#fdCondVal').style.display!=='none'
      &&p.window.eval("S.fields.find(f=>f.id==='dependent').condOp==='ncontains'&&S.fields.find(f=>f.id==='dependent').condVal==='needle'"),
    'عملگر «شامل نیست» مقدار را می‌گیرد و پس از ذخیره حفظ می‌شود');
  p.click('#fdAddCondition');
  p.set('#fdCondLogic','any');
  p.set('#fdCondRules [data-condition-row="1"] [data-cond-field]','base');
  p.set('#fdCondRules [data-condition-row="1"] [data-cond-op]','starts');
  p.set('#fdCondRules [data-condition-row="1"] [data-cond-value]','Alpha');
  p.window.eval('saveField()');
  ok(p.window.eval("S.fields.find(f=>f.id==='dependent').conditionLogic==='any'&&S.fields.find(f=>f.id==='dependent').conditions.length===2&&S.fields.find(f=>f.id==='dependent').condField===''"),
    'چندقاعده‌ای بودن و منطق OR به‌صورت گروهی ذخیره می‌شود، بدون تکیه به alias تک‌قاعده‌ای');
  p.window.eval("editField('dependent')"); p.set('#fdCondField','choice-base');
  ok(JSON.stringify(p.all('#fdCondOp option').map(option=>option.value))===JSON.stringify(['eq','ne','empty','nempty'])
      &&p.doc.querySelector('#fdCondVal').tagName==='SELECT'
      &&p.all('#fdCondVal option').some(option=>option.value==='A')&&p.all('#fdCondVal option').some(option=>option.value==='B'),
    'نوع گزینه‌ای فقط عملگر سازگار و انتخاب مقدار از گزینه‌های مرجع را نشان می‌دهد');
  p.set('#fdCondField','legacy-select-base');
  ok(p.doc.querySelector('#fdCondVal').tagName==='SELECT'
      &&p.all('#fdCondVal option').some(option=>option.value==='Old A')
      &&p.all('#fdCondVal option').some(option=>option.value==='Old B'),
    'ویرایشگر هم گزینه‌های type=select و کلید legacy options را در شرط می‌شناسد');
  p.window.eval("editField('decimal-dependent')");
  const decimalInput=p.doc.querySelector('#fdCondVal');
  p.set('#fdCondVal','١٫٥');p.window.eval('saveField()');
  ok(decimalInput.type==='text'&&decimalInput.getAttribute('inputmode')==='decimal'
      &&p.window.eval("S.fields.find(f=>f.id==='decimal-dependent').conditions[0].value==='١٫٥'&&validConditionValue(conditionRulesForField(S.fields.find(f=>f.id==='decimal-dependent'))[0],S.fields.find(f=>f.id==='number-base'))"),
    'ورودی عددی، ارقام و ممیز فارسی/عربی را بدون coercion مرورگر حفظ و اعتبارسنجی می‌کند');
  ok(p.window.eval('cardPaymentReady()')===false&&JSON.stringify(p.window.eval('centralFormMethods()'))==='[]'
      &&p.window.eval('receiptCardReady()')===true,
    'خرید مبلغ‌دار همچنان به پرداخت سرور وصل نیست، اما مقصد فیش از استخر کارت موجود خوانده می‌شود');
  const paymentInstructions='ابتدا مبلغ را به کارت مقصد واریز کنید.';
  p.click('[data-go="s3"]');p.click('#receiptReviewRequired');
  p.input('#receiptInstructions',paymentInstructions);
  ok(p.doc.querySelector('#receiptReviewRequired').getAttribute('aria-checked')==='true'
      &&!p.doc.querySelector('#receiptInstructionsWrap').hidden
      &&p.window.eval('S.paymentInstructions')===paymentInstructions,
    'روشن‌کردن دریافت فیش، تنظیم اختیاری نکات واریز را برای مدیر باز می‌کند');
  p.click('#receiptReviewRequired');
  ok(p.doc.querySelector('#receiptInstructionsWrap').hidden&&p.window.eval('S.paymentInstructions')===paymentInstructions,
    'خاموش‌کردن دریافت فیش نکات مدیر را پنهان می‌کند، بدون پاک‌کردن پیش‌نویس آن');
  p.click('#receiptReviewRequired');
  ok(!p.doc.querySelector('#receiptInstructionsWrap').hidden
      &&p.doc.querySelector('#receiptInstructions').value===paymentInstructions,
    'با روشن‌کردن دوباره، نکات واریز قبلی بازیابی می‌شوند');
  p.window.eval('renderReview()');
  const qr=p.doc.querySelector('#revQR svg');
  ok(!!qr,'QR متنیِ نمونه روی مرور فرم ساخته می‌شود');
  ok(p.txt('#revQRNote').includes('نشانی وب')&&p.txt('#revQRNote').includes('ندارد'),'متن کنار QR می‌گوید مقصد عمومی ندارد');
  ok(qr&&!qr.querySelector('a')&&!p.all('#revQR a[href^="http"]').length,'QR به URL یا فرم عمومی پیوند نشده است');
  ok(fs.readFileSync(DIR+'create.html','utf8').includes("qrSVG('SAMPLE-FORM:'")&&p.window.eval("!!qrMatrix('SAMPLE-FORM:LOCAL')"),
    'محتوای تولید QR نشان متنی نمونه دارد، نه نشانی مقصد');
  ok(p.network.length===0&&externalAnchors(p).length===0,'فرم‌ساز شبکه را تا اقدام صریح برای ذخیره صدا نمی‌زند');
  ok(fs.readFileSync(DIR+'create.html','utf8').includes('id="i-check"'),'آیکن i-check در sprite صفحهٔ فرم‌ساز تعریف شده است');
  p.window.eval(`S.title='فرم ذخیره‌سازی تنظیمات';S.model='registration';S.need='reg';S.evId='ev-save';
    S.display='all';S.dir='ltr';S.after='view';S.eventVisible=false;S.limit='invite';S.inviteCodes='SAVE-7';
    S.onePerPerson=true;S.wait=4;S.cap=12;S.sync={cap:false,dates:true,limit:false,money:false};
    S.enabledPaymentMethods=['card_transfer'];S.receiptReviewRequired=true;S.notify.on=true;S.notify.to='ایتا';S.introMedia='image';S.introMediaNote='یادداشت پوستر';
    S.fields=[Object.assign(freshField('text','q-save'),{l:'پرسش ذخیره',req:true,col:false,condField:'',condOp:'eq',condVal:''})];
    renderReview()`);
  ok(p.txt('#review').includes('کارت‌به‌کارت با رسید و بازبینی دستی')
      &&p.txt('#review').includes('مقصد کارتِ فیش')&&p.txt('#review').includes('بانک نمونه')
      &&!p.txt('#review').includes('پرداخت لازم نیست'),
    'خلاصهٔ فرم رسید، مقصد کارت را نشان می‌دهد و کارت‌به‌کارت را با فرم رایگان اشتباه نمی‌گیرد');
  p.doc.cookie='nora_csrf=csrf-smoke; path=/';
  p.click('#publish'); await wait(80);
  const saved=JSON.parse(store.getItem('nora-forms')||'[]').find(x=>x.name==='فرم ذخیره‌سازی تنظیمات');
  ok(saved&&saved.display==='all'&&saved.dir==='ltr'&&saved.after==='view'&&saved.eventVisible===false&&saved.serverDraft===true,
    'پیش‌نویس در پاسخ API و نسخهٔ محلیِ سازگار ثبت شد');
  ok(saved&&saved.limit==='invite'&&saved.inviteCodes==='SAVE-7'&&saved.wait===4&&saved.sync.cap===false&&saved.sync.dates===true
      &&saved.receiptReviewRequired===true&&saved.paymentInstructions===paymentInstructions
      &&saved.paymentCard?.number==='4111111111111111'
      &&saved.paymentCard?.bank==='بانک نمونه'&&saved.paymentCard?.holder==='حساب سازمان',
    'تنظیمات شرطی، ظرفیت/صف، همگام‌سازی، دریافت فیش و کارت انتخاب‌شده به payload سرور رسیدند');
  ok(saved&&saved.fields[0].col===false&&saved.fields[0].req===true&&saved.introMediaNote==='یادداشت پوستر'&&saved.notify.on===false,
    'ویژگی‌های فیلد و رسانه حفظ شدند و اعلان بیرونی همچنان خاموش ماند');
  const builderText=fs.readFileSync(DIR+'create.html','utf8');
  ok(builderText.includes('رسید را در همین فرم بارگذاری می‌کند')&&builderText.includes('بلیت فقط پس از تأیید دستی از backend آماده می‌شود')
      &&!builderText.includes('فیش در ربات بله به کارتابل مدیر می‌رود'),
    'متن واقعی فرم‌ساز می‌گوید فیش داخل فرم است و بلیت پیش از بررسی مدیر به Bale می‌آید');
  const createCall=apiMock.calls.find(call=>call.path==='/api/forms'&&call.method==='POST');
  const createBody=createCall&&JSON.parse(createCall.body);
  ok(createCall&&createCall.credentials==='same-origin'&&createCall.headers['Idempotency-Key']&&createBody?.fields?.[0]?.id==='q-save'
      &&createBody?.settings?.receiptReviewRequired===true
      &&createBody?.settings?.paymentInstructions===paymentInstructions
      &&createBody?.settings?.paymentCard?.number==='4111111111111111',
    'ذخیرهٔ فرم از همان مبدأ، با کلید تکرارنشدن و مقصد کارت واقعی به API رفت');
  ok(saved&&saved.status==='draft'&&saved.on===0&&p.doc.querySelector('#doneCard').style.display==='block',
    'پس از پاسخ موفق سرور فقط پیش‌نویس ساخته شد، نه فرم منتشرشده');
  p.click('#donePublish');await wait(80);
  ok(apiMock.record?.status==='published'&&apiMock.record.version===2
      &&apiMock.calls.some(call=>call.path==='/api/forms/server-form-1/publish'&&call.method==='POST'),
    'انتشار فقط با اقدام صریح مالک و نسخهٔ مورد انتظار به API سرور می‌رود');
  ok(p.doc.querySelector('#publicLinkPanel').style.display!=='none'
      &&p.doc.querySelector('#publicFormUrl').value.includes('form.html?fid=server-form-1')
      &&p.doc.querySelector('#donePreview').textContent==='بازکردن فرم عمومی',
    'پس از انتشار، پیوند عمومی واقعی و دکمهٔ بازکردن فرم نمایش داده می‌شوند');
  p.click('#copyPublicLink');await wait(30);
  ok(p.doc.querySelector('#publicFormUrl').value.includes('server-form-1'),'پیوند عمومی برای کپی/انتخاب آماده است');
  p.click('#donePause');await wait(80);
  ok(apiMock.record?.status==='paused'&&apiMock.record.version===3
      &&apiMock.calls.some(call=>call.path==='/api/forms/server-form-1/pause'&&call.method==='POST'),
    'توقف پاسخ‌گیری با درخواست مالک و نسخهٔ مورد انتظار به API سرور می‌رود');
  ok(p.doc.querySelector('#publicLinkPanel').style.display==='none'
      &&p.doc.querySelector('#donePublish').style.display!=='none'
      &&p.txt('#doneNote').includes('پاسخ‌گیری عمومی متوقف شد'),
    'پس از توقف، پیوند عمومی پنهان و امکان انتشار مجدد آشکار است');

  const readinessApi=makeFormsApiMock({id:'server-not-ready',readinessIssues:[
    {code:'schedule_not_connected',message:'بازهٔ زمانی هنوز در سرور اجرا نمی‌شود؛ تاریخ شروع و پایان را پاک کنید.'}
  ]}),readinessPage=await load('create.html',makeStore(),'',readinessApi.fetch);
  readinessPage.window.eval("S.title='فرم با مانع انتشار';S.fields=[Object.assign(freshField('text','q-ready'),{l:'پرسش'})]");
  readinessPage.click('#publish');await wait(80);readinessPage.click('#donePublish');await wait(80);
  ok(readinessApi.record?.status==='draft'
      &&readinessApi.calls.some(call=>call.path==='/api/forms/server-not-ready/readiness'&&call.method==='GET')
      &&!readinessApi.calls.some(call=>call.path==='/api/forms/server-not-ready/publish')
      &&readinessPage.txt('#ownerApiMessage').includes('بازهٔ زمانی هنوز در سرور اجرا نمی‌شود'),
    'مانع readiness پیش از POST انتشار نمایش داده می‌شود و وضعیت پیش‌نویس تغییر نمی‌کند');

  const reloadId='server-published-reload',publishedRecord={id:reloadId,name:'فرم منتشرشدهٔ بازشده',model:'registration',need:'reg',
    slug:'reload',ev:'',fields:[{id:'reload-name',t:'text',l:'نام',req:true}],settings:{display:'all'},status:'published',version:4,
    created_at:'2026-01-01T00:00:00+00:00',updated_at:'2026-01-01T00:00:00+00:00'};
  const reloadStore=makeStore({'nora-forms':JSON.stringify([{...publishedRecord,serverManaged:true,serverDraft:false,on:1}])});
  const reloadApi=makeFormsApiMock({id:reloadId,initialRecord:publishedRecord});
  const reloaded=await load('create.html',reloadStore,'?fid='+reloadId,reloadApi.fetch);
  ok(reloaded.doc.querySelector('#doneCard').style.display==='block'
      &&reloaded.doc.querySelector('#publicLinkPanel').style.display!=='none'
      &&reloaded.doc.querySelector('#donePause').style.display!=='none',
    'فرم منتشرشده از انبار سازگار پس از بارگذاری دوباره، پیوند و کنترل توقف خود را بازیابی کرد');
  ok(reloadApi.calls.some(call=>call.path==='/api/auth/me'&&call.method==='GET'),
    'نمایش کنترل توقف پس از بازخوانی، با نقش دریافتی از API سرور ممکن شد');
  const viewerApi=makeFormsApiMock({authenticated:false,id:reloadId,initialRecord:publishedRecord});
  const viewer=await load('create.html',makeStore({'nora-forms':JSON.stringify([{...publishedRecord,serverManaged:true,serverDraft:false,on:1}])}),
    '?fid='+reloadId,viewerApi.fetch);
  ok(viewer.doc.querySelector('#doneCard').style.display==='block'
      &&viewer.doc.querySelector('#donePause').style.display==='none'
      &&viewer.doc.querySelector('#donePublish').style.display==='none'
      &&viewerApi.calls.some(call=>call.path==='/api/account/me'),
    'فرم منتشرشده برای بازدیدکنندهٔ بی‌نشست می‌ماند، اما کنترل مالک نمایش داده نمی‌شود');
  reloaded.click('#donePause');await wait(70);
  ok(reloadApi.record.status==='paused'&&reloadApi.record.version===5,
    'فرم بازشده پس از تازه‌خوانی نسخهٔ سرور با موفقیت متوقف شد');
  reloaded.click('#donePublish');await wait(70);
  ok(reloadApi.record.status==='published'&&reloadApi.record.version===6,
    'فرم متوقف‌شده پس از بازبارگذاری قابل انتشار مجدد باقی ماند');

  const blockedStore=makeStore(), originalSet=blockedStore.setItem, blockedApi=makeFormsApiMock();
  blockedStore.setItem=(key,value)=>{if(key==='nora-forms')throw new Error('quota');originalSet(key,value)};
  const blocked=await load('create.html',blockedStore,'',blockedApi.fetch);
  blocked.window.eval("S.title='فرم با فضای مرورگر پر';S.fields=[Object.assign(freshField('text','q-storage'),{l:'پرسش نمونه'})]");
  blocked.doc.cookie='nora_csrf=csrf-smoke; path=/';
  blocked.click('#publish'); await wait(80);
  ok(!blockedStore.getItem('nora-forms')&&blocked.doc.querySelector('#doneCard').style.display==='block',
    'اگر نسخهٔ محلی به‌دلیل سهمیه ذخیره نشود، نتیجهٔ موفق فقط برای پاسخ تأییدشدهٔ سرور نشان داده می‌شود');
  ok(blocked.doc.querySelector('#doneNote').textContent.includes('پیش‌نمایش محلی در دسترس نیست')
      &&blocked.doc.querySelector('#donePreview').getAttribute('aria-disabled')==='true',
    'شکست همگام‌سازی محلی شفاف است و پیوند پیش‌نمایش خراب ساخته نمی‌شود');

  const offline=await load('create.html',makeStore());
  offline.window.eval("S.title='ذخیرهٔ بدون API';S.fields=[Object.assign(freshField('text','q-offline'),{l:'پرسش نمونه'})]");
  offline.click('#publish'); await wait(30);
  ok(!offline.store.getItem('nora-forms')&&offline.doc.querySelector('#doneCard').style.display==='none',
    'بدون API فرم‌ساز به ذخیرهٔ محلی برنمی‌گردد و موفقیت جعلی نمی‌سازد');
  ok(offline.txt('#ownerApiMessage').includes('سرور همین سامانه')&&offline.healthChecks.includes('/api/health'),
    'نبود سرویس سروری با پیام روشن اعلام می‌شود');

  const loginStore=makeStore(),loginApi=makeFormsApiMock({authenticated:false,id:'server-auth-1'});
  const loginPage=await load('create.html',loginStore,'',loginApi.fetch);
  loginPage.window.eval("S.title='فرم نیازمند مالک';S.fields=[Object.assign(freshField('text','q-owner'),{l:'پرسش مالک'})]");
  loginPage.click('#publish');await wait(50);
  ok(!loginApi.calls.some(call=>call.path==='/api/forms'&&call.method==='POST')
      &&loginPage.doc.querySelector('#ownerLoginForm').style.display==='block'
      &&loginPage.doc.querySelector('#doneCard').style.display==='none',
    'بدون نشست مالک، پیش‌نویس متوقف می‌شود و ورود امن درخواست می‌شود');
  loginPage.doc.querySelector('#ownerUsername').value='owner-smoke';
  loginPage.doc.querySelector('#ownerPassword').value='owner-password-111';
  loginPage.doc.querySelector('#ownerLoginForm').dispatchEvent(new loginPage.window.Event('submit',{bubbles:true,cancelable:true}));
  await wait(100);
  ok(loginApi.loggedIn&&loginApi.calls.some(call=>call.path==='/api/forms'&&call.method==='POST')
      &&loginPage.doc.querySelector('#doneCard').style.display==='block',
    'پس از احراز سروری مالک، همان پیش‌نویس در ادامهٔ همان جریان ذخیره شد');
  ok(loginPage.doc.querySelector('#ownerPassword').value===''&&!JSON.stringify(loginStore._dump()).includes('owner-password-111')
      &&!JSON.stringify(loginStore._dump()).includes('csrf-smoke'),
    'گذرواژه و توکن CSRF در localStorage یا انبار نمونه نگه‌داری نشدند');
}

/* ── ۶الف) عنوان و نشانی خودکار/دستی فقط برای پیش‌نمایش محلی ── */
{
  console.log('\n── عنوان و نشانی فرم ──');
  const p=await load('create.html',makeStore()),title=p.doc.querySelector('#fTitle'),slug=p.doc.querySelector('#fSlug');
  ok(title.maxLength===120&&slug.maxLength===120&&p.window.eval('S.slugAuto===true'),
    'عنوان و نشانی سقف مشخص دارند و فرم تازه از نشانی خودکار شروع می‌شود');
  p.input('#fTitle','کارگاه نمونهٔ پاییزی');
  ok(p.window.eval("S.slugAuto===true&&S.slug.endsWith('/'+faSlug(S.title))&&!!safeSamplePath(S.slug)")
      &&p.txt('#slugAutoLabel')==='خودکار',
    'ویرایش عنوان، بخش پایانی نشانی امن را خودکار و فقط برای پیش‌نمایش به‌روز می‌کند');
  p.input('#fSlug','events/my-workshop');
  ok(p.window.eval("S.slug==='events/my-workshop'&&S.slugAuto===false&&safeSamplePath(S.slug)==='/events/my-workshop'")
      &&p.txt('#slugAutoLabel')==='دستی'&&p.txt('#slugView').includes('پیش‌نمایش محلی'),
    'با ویرایش دستی، ساخت خودکار خاموش می‌شود و نشانی همچنان فقط محلی نمایش داده می‌شود');
  p.input('#fSlug','https://attacker.example/collect');
  ok(p.window.eval("S.slugAuto===false&&safeSamplePath(S.slug)===''&&slugView()===undefined")
      &&p.txt('#slugView').includes('نشانی عمومی غیرفعال')&&!p.txt('#slugView').includes('attacker'),
    'نشانی بیرونی یا مقصددار به لینک تبدیل نمی‌شود و رابط مقصد عمومی را غیرفعال نشان می‌دهد');
  p.click('#slugAuto');
  ok(p.window.eval("S.slugAuto===true&&!!safeSamplePath(S.slug)&&!S.slug.includes('attacker')&&S.slug===faSlug(S.title)")
      &&p.doc.querySelector('#slugAuto').classList.contains('on')&&p.txt('#slugAutoLabel')==='خودکار',
    'روشن‌کردن خودکار پس از ورودی نامعتبر مسیر امن تازه می‌سازد و بخش نامطمئن را نگه نمی‌دارد');
  p.input('#fTitle','x'.repeat(121));
  ok(p.window.eval('validateBeforeSave()===false')&&p.txt('#toast').includes('۱۲۰ نویسه')
      &&p.window.eval('S.title.length===121'),
    'عنوان بیش از ۱۲۰ نویسه در ذخیره رد می‌شود و بی‌صدا بریده نمی‌شود');
  p.input('#fTitle','عنوان معتبر');
  p.input('#fSlug','x'.repeat(121));
  ok(p.window.eval('validateBeforeSave()===false')&&p.txt('#toast').includes('نشانی دستی')
      &&p.window.eval('S.slug.length===121'),
    'نشانی دستیِ بیش‌ازحد هم پیش از ذخیره رد می‌شود، نه اینکه خاموش کوتاه شود');
  ok(p.network.length===0&&externalAnchors(p).length===0,'ویرایش نشانی هیچ درخواست یا پیوند بیرونی نمی‌سازد');
}

/* ── ۶الف) قرارداد قابلیت‌ها، مدل چهارقدمی و مرتب‌سازی دسترس‌پذیر ── */
{
  console.log('\n── قابلیت‌های واقعی و ترتیب پرسش‌ها ──');
  const api=makeFormsApiMock({id:'capability-smoke'}),p=await load('create.html',makeStore(),'',api.fetch);
  ok(p.errors.length===0&&p.capabilityChecks.includes('/api/public/forms/capabilities')
      &&p.window.eval("FORM_CAPABILITY_STATE==='ready'&&modelCapability('order').publishable===false")
      &&p.doc.querySelector('#modelCapabilitySummary')?.textContent.includes('از API همین میزبان'),
    'وضعیت مدل‌ها از قرارداد عمومی همان سرور خوانده می‌شود و سفارش قابل‌انتشار نیست');
  ok(p.doc.querySelectorAll('#stepper button').length===4
      &&p.doc.querySelector('#tiles [data-model="order"]')?.disabled
      &&p.doc.querySelector('#catList [data-add="image"]')?.disabled,
    'جریان ساخت همان چهار قدم را دارد و نوع پرسشِ بارگذاریِ پشتیبانی‌نشده غیرفعال است');
  p.window.eval(`S.fields=[freshField('text','reorder-a'),freshField('text','reorder-b'),freshField('text','reorder-c')];
    S.fields.forEach((field,index)=>field.l='پرسش '+(index+1));renderCanvas()`);
  p.window.eval("go('s2')");
  const firstHandle=p.doc.querySelector('[data-drag-handle="reorder-a"]'),firstBlock=p.doc.querySelector('[data-block="reorder-a"]');
  ok(p.doc.querySelector('#fieldList').getAttribute('role')==='list'
      &&p.doc.querySelector('#fieldList').getAttribute('aria-label')==='پرسش‌های فرم'
      &&firstHandle.getAttribute('aria-label').includes('پرسش «پرسش 1»')
      &&firstHandle.getAttribute('aria-describedby')==='fieldReorderHelp'
      &&firstHandle.getAttribute('aria-keyshortcuts')==='ArrowUp ArrowDown'
      &&[...firstBlock.querySelectorAll('button')].every(button=>button.textContent.trim()||button.getAttribute('aria-label'))
      &&p.doc.querySelector('[data-up="reorder-a"]').disabled
      &&p.doc.querySelector('[data-down="reorder-c"]').disabled,
    'فهرست پرسش، دستهٔ جابه‌جایی، دکمه‌های بی‌آیکن‌متن و مرزهای بالا/پایین نام دسترس‌پذیر دارند');
  firstHandle.dispatchEvent(new p.window.KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true}));
  ok(p.window.eval("S.fields.map(field=>field.id).join(',')==='reorder-b,reorder-a,reorder-c'")
      &&p.txt('#fieldReorderStatus').includes('جایگاه ۲')
      &&p.doc.querySelector('#fieldList [role="listitem"][aria-posinset="2"][aria-setsize="3"]')
      &&p.doc.activeElement?.getAttribute('data-drag-handle')==='reorder-a',
    'جابجایی صفحه‌کلیدی ترتیب، جایگاه/تعداد دسترس‌پذیر، فوکوس و پیام زنده را به‌روز می‌کند');
  const dragHandle=p.doc.querySelector('[data-drag-handle="reorder-c"]'),startEvent=new p.window.Event('dragstart',{bubbles:true,cancelable:true});
  Object.defineProperty(startEvent,'dataTransfer',{value:{effectAllowed:'',setData(){}}});dragHandle.dispatchEvent(startEvent);
  const dropTarget=p.doc.querySelector('[data-block="reorder-b"]'),dropEvent=new p.window.Event('drop',{bubbles:true,cancelable:true});
  Object.defineProperty(dropEvent,'clientY',{value:-1});dropTarget.dispatchEvent(dropEvent);
  ok(p.window.eval("S.fields.map(field=>field.id).join(',')==='reorder-c,reorder-b,reorder-a'")
      &&p.doc.activeElement?.getAttribute('data-drag-handle')==='reorder-c'
      &&p.doc.querySelector('#fieldList [data-block="reorder-c"][aria-posinset="1"][aria-setsize="3"]')
      &&!p.doc.querySelector('.block.dragging'),
    'کشیدن و رهاکردن ترتیب دسترس‌پذیر، جایگاه و فوکوس را حفظ و نشانگر را پاک می‌کند');
}

/* ── ۶ب) تنظیم‌های چیدمان، نمایش و رفتار پس از ثبت ── */
{
  console.log('\n── چیدمان و دسترسی فرم ──');
  const p=await load('create.html',makeStore());
  p.click('#segDisplay [data-display="all"]');
  ok(p.window.eval("S.display==='all'")&&p.doc.querySelector('#segDisplay [data-display="all"]').classList.contains('on'),
    'چیدمان «همه در یک صفحه» با انتخاب کاربر فعال می‌شود');
  p.click('[data-dir="ltr"]');
  ok(p.window.eval("S.dir==='ltr'")&&p.doc.querySelector('[data-dir="ltr"]').classList.contains('on'),
    'جهت چپ‌به‌راست مستقل از چیدمان قابل انتخاب است');
  p.click('#segAfter [data-after="view"]');
  ok(p.window.eval("S.after==='view'")&&p.doc.querySelector('#segAfter [data-after="view"]').classList.contains('on'),
    'رفتار پس از ثبت روی مشاهدهٔ پاسخ تنظیم می‌شود، نه ویرایش');
  p.click('#showOnEvent');
  ok(p.window.eval('S.eventVisible===false')&&p.doc.querySelector('#showOnEvent').getAttribute('aria-checked')==='false'
      &&!p.doc.querySelector('#showOnEvent').classList.contains('on'),
    'نمایش در کارت رویداد با کلید مستقل خاموش می‌شود');
  ok(!p.doc.querySelector('#syncCapDates')&&!p.doc.querySelector('#syncLimitTop')
      &&!p.doc.querySelector('#syncLimitLive')&&!p.doc.querySelector('#onePerPerson')
      &&p.txt('#s2').includes('همگام‌سازی ظرفیت و تاریخ‌ها با رویداد')
      &&p.txt('#s2').includes('غیرفعال · ظرفیت را اینجا تنظیم کنید')
      &&p.txt('#s2').includes('هویت پاسخ‌دهنده ناشناس است'),
    'همگام‌سازی رویداد و تضمین یک پاسخ حذف شده‌اند و دلیل نبود احراز هویت کنارشان مانده است');
  ok(p.txt('#review').includes('همه در یک صفحه')&&p.txt('#review').includes('چپ‌به‌راست')
      &&p.txt('#review').includes('فقط مشاهده')&&p.txt('#review').includes('غیرفعال')
      &&p.network.length===0,
    'مرور فرم، انتخاب‌های نمایشی را نشان می‌دهد؛ هیچ‌کدام اعلان یا درخواست شبکه‌ای نمی‌فرستد');
}

/* ── ۶ج) ظرفیت، صف و تعداد افراد فقط عدد صحیحِ محلی ── */
{
  console.log('\n── ظرفیت و تعداد افراد ──');
  const p=await load('create.html',makeStore()),cap=p.doc.querySelector('#cap'),waitInput=p.doc.querySelector('#wcount'),max=p.doc.querySelector('#maxPer');
  ok(cap.inputMode==='numeric'&&waitInput.inputMode==='numeric'&&max.inputMode==='numeric'
      &&cap.maxLength===16&&waitInput.maxLength===16&&max.maxLength===2,
    'ظرفیت، صف و تعداد نفر صفحه‌کلید عددی و طول ورودی متناسب دارند');
  p.input('#cap','۱٬۰۰۰');p.input('#wcount','۲۰');
  ok(p.window.eval('S.cap===1000&&S.wait===20')&&cap.value==='۱۰۰۰'&&waitInput.value==='۲۰',
    'رقم فارسی با جداکنندهٔ هزارگان پذیرفته می‌شود و مقدار نمایشی محلی می‌ماند');
  p.input('#cap','۱٫۵');
  ok(p.window.eval('S.cap===1000&&document.querySelector("#cap").getAttribute("aria-invalid")==="true"')
      &&p.window.eval('validateBeforeSave()===false')&&p.txt('#toast').includes('عدد صحیح'),
    'ظرفیت اعشاری بی‌صدا به عدد صحیح گرد نمی‌شود و ذخیره را متوقف می‌کند');
  p.input('#cap','۰');p.input('#wcount','-۱');
  ok(p.window.eval('S.cap===0&&S.wait===20&&document.querySelector("#wcount").getAttribute("aria-invalid")==="true"')
      &&p.window.eval('validateBeforeSave()===false')&&p.txt('#toast').includes('صف نمونه'),
    'ظرفیت صفر معتبر است، اما صف منفی پذیرفته نمی‌شود');
  p.input('#wcount','۱۰');
  ok(p.window.eval('S.cap===0&&S.wait===10&&firstInvalidCountSetting()===null'),
    'ظرفیت صفر به‌معنای مقدار خالی نیست و صف صحیح ذخیره می‌شود');
  p.input('#maxPer','۱');
  ok(p.window.eval('S.maxPer===1&&firstInvalidCountSetting()===null'),'بدون همراه، حداقل یک نفر برای هر پاسخ کافی است');
  p.click('#guestsOn');
  ok(p.window.eval('S.guestsOn&&S.maxPer===2')&&max.value==='۲'&&max.getAttribute('aria-invalid')===null
      &&p.doc.querySelector('#guestsOn').getAttribute('aria-checked')==='true'
      &&p.doc.querySelector('#guestsOn').classList.contains('on'),
    'بازکردن همراه، حداقل دو نفر را اعمال و ورودی تعداد را هم‌زمان به‌روز می‌کند');
  p.input('#maxPer','۲٫۵');
  ok(p.window.eval('S.maxPer===2&&firstInvalidCountSetting()?.id==="maxPer"')
      &&max.getAttribute('aria-invalid')==='true'&&p.window.eval('validateBeforeSave()===false'),
    'تعداد نفر اعشاری به ظرفیت همراه تبدیل نمی‌شود و ذخیره را متوقف می‌کند');
  p.input('#maxPer','۱۰');
  ok(p.window.eval('S.maxPer===2&&firstInvalidCountSetting()?.id==="maxPer"'),
    'حداکثر ۹ نفر بی‌صدا بریده نمی‌شود؛ مقدار ۱۰ برای اصلاح می‌ماند');
  p.input('#maxPer','۹');
  ok(p.window.eval('S.maxPer===9&&firstInvalidCountSetting()===null')&&max.value==='۹',
    'مرز بالای ۹ نفر پذیرفته می‌شود');
  p.input('#maxPer','۱');
  ok(p.window.eval('firstInvalidCountSetting()?.id==="maxPer"'),
    'با بازبودن همراه، یک نفر کمتر از حداقل دو نفر رد می‌شود');
  p.click('#guestsOn');
  ok(p.window.eval('!S.guestsOn&&S.maxPer===9&&firstInvalidCountSetting()===null')&&max.value==='۹'
      &&p.doc.querySelector('#guestsOn').getAttribute('aria-checked')==='false'
      &&!p.doc.querySelector('#guestsOn').classList.contains('on'),
    'بستن همراه ورودی نامعتبر را با آخرین تعداد صحیح جایگزین می‌کند');
}

/* ── ۶د) محدودیت‌های هویتی هنوز پشتیبانی نمی‌شوند ── */
{
  console.log('\n── محدودیت افراد و وضعیت سروری ──');
  const p=await load('create.html',makeStore());
  ok(p.window.eval("S.limit==='none'")
      &&['event','attended','invite'].every(value=>p.doc.querySelector('#limitMode option[value="'+value+'"]')?.disabled)
      &&p.txt('#limitModeHelp').includes('در سرور احراز نمی‌شوند'),
    'ثبت‌نام رویداد، حضور و کد دعوت از کاتالوگ انتخاب قابل‌انتشار نیستند و دلیل به‌روشنی نوشته شده');
  ok(!p.doc.querySelector('#syncLimitLive')&&!p.doc.querySelector('#onePerPerson')
      &&p.txt('#s2').includes('یک پاسخ برای هر شخص')&&p.txt('#s2').includes('هویت پاسخ‌دهنده ناشناس است'),
    'تضمین یک پاسخ و همگام‌سازی محدودیت به‌جای کلید ظاهری، غیرفعال با علت نشان داده می‌شوند');
  p.window.eval("S.limit='invite';S.inviteCodes=['SAMPLE-1','SAMPLE-2'].join(String.fromCharCode(10));renderReview()");
  ok(p.txt('#review').includes('محدودیت رویداد/دعوت در سرور احراز نمی‌شود')
      &&p.network.length===0,
    'تنظیم legacy نامعتبر در خلاصهٔ انتشار به‌عنوان مانع سروری دیده می‌شود و درخواست شبکه‌ای نمی‌سازد');
}

/* ── ۶هـ) تاریخ شروع و پایان شمسی، ترتیب و ساعت محلی ── */
{
  console.log('\n── بازهٔ ثبت‌نام در فرم‌ساز ──');
  const p=await load('create.html',makeStore()),start=p.doc.querySelector('#pkStart'),end=p.doc.querySelector('#pkEnd');
  const change=(box,selector,value)=>{const input=box.querySelector(selector);input.value=String(value);input.dispatchEvent(new p.window.Event('change',{bubbles:true}))};
  const setDateTime=(box,year,month,day,hour,minute)=>{
    for(const [selector,value] of [['.pk1',year],['.pk2',month],['.pk3',day],['.pk4',hour],['.pk5',minute]])change(box,selector,value);
  };
  ok(p.window.eval('firstInvalidFormDateRange()===null')
      &&p.window.eval("S.start===''&&S.end==='' ")
      &&start.querySelector('.pk1').value===''&&end.querySelector('.pk5').value==='',
    'بازهٔ زمان‌بندیِ غیرپشتیبانی‌شده پیش‌فرض خالی است و فرم را مسدود نمی‌کند');
  setDateTime(start,1403,12,30,9,0);setDateTime(end,1403,12,30,8,59);
  ok(p.window.eval("S.start==='1403/12/30 09:00'&&S.end==='1403/12/30 08:59'")
      &&p.window.eval("firstInvalidFormDateRange()?.target==='#pkEnd'")
      &&p.window.eval('validateBeforeSave()===false')&&p.txt('#toast').includes('بعد از زمان شروع')
      &&end.closest('details').open,
    'اسفندِ کبیسه انتخاب می‌شود، اما زمان پایانِ زودتر در تنظیمات رد و پنل درست باز می‌شود');
  setDateTime(end,1403,12,30,9,0);
  ok(p.window.eval('firstInvalidFormDateRange()?.target==="#pkEnd"'),
    'پایانِ هم‌زمان با شروع هم بازهٔ صفرمدت می‌سازد و پذیرفته نمی‌شود');
  setDateTime(end,1403,12,30,9,1);
  ok(p.window.eval("firstInvalidFormDateRange()===null&&S.end==='1403/12/30 09:01'")
      &&p.window.eval('validateBeforeSave()===true'),
    'پایانِ یک دقیقه بعد از شروع معتبر است و تنظیمات دیگر فرم هم اجازهٔ ذخیره می‌دهند');
  change(end,'.pk1',1404);change(end,'.pk2',12);
  ok(![...end.querySelector('.pk3').options].some(option=>option.value==='30'),
    'روز سی‌ام اسفند در سال غیرکبیسه اصلاً در فهرست پایان نمایش داده نمی‌شود');
  change(end,'.pk3',30);
  ok(p.window.eval('firstInvalidFormDateRange()?.target==="#pkEnd"')
      &&p.window.eval('validateBeforeSave()===false')&&p.txt('#toast').includes('پایان را کامل'),
    'تاریخ غیرممکنِ سال غیرکبیسه با دست‌کاری گزینه هم به ذخیره راه پیدا نمی‌کند');
  ok(p.txt('#s2').includes('محلی و غیرقابل‌انتشار')&&p.txt('#s2').includes('همگام‌سازی خودکار رویداد هنوز فعال نیست')&&p.network.length===0,
    'تاریخ فقط محلی است، ظرفیت/صف سروری‌اند و همگام‌سازی رویداد ادعای اجرا ندارد');
  p.click('#clearSchedule');
  ok(p.window.eval("S.start===''&&S.end===''&&firstInvalidFormDateRange()===null")
      &&p.doc.querySelector('#pkStart .pk1').value===''&&p.doc.querySelector('#pkEnd .pk1').value==='',
    'دکمهٔ پاک‌کردن هر دو تاریخ محلی را خالی می‌کند تا مانع انتشار باقی نماند');
}

/* ── ۶و) سقف نوشته‌های تنظیمات و پیوندهای پایانی ── */
{
  console.log('\n── متن‌ها و پیوندهای فرم‌ساز ──');
  const p=await load('create.html',makeStore()),intro=p.doc.querySelector('#introText'),introNote=p.doc.querySelector('#introMediaNote'),
    end=p.doc.querySelector('#endText'),invite=p.doc.querySelector('#inviteCodes');
  ok(intro.maxLength===3000&&introNote.maxLength===160&&end.maxLength===1000&&invite.maxLength===5000,
    'توضیحات ابتدا، یادداشت رسانه، متن پایان و فهرست دعوت سقف طول مشخص دارند');
  for(let i=0;i<10;i++)p.click('#addLink');
  ok(p.window.eval('S.links.length===10')&&p.all('#linkList [data-lt]').length===10
      &&p.doc.querySelector('#linkList [data-lt="0"]').maxLength===120
      &&p.doc.querySelector('#linkList [data-lu="0"]').maxLength===2048,
    'تا ۱۰ پیوند پایانی با سقف جداگانه برای عنوان و نشانی قابل‌ویرایش‌اند');
  p.click('#addLink');
  ok(p.window.eval('S.links.length===10')&&p.txt('#toast').includes('۱۰ پیوند'),
    'پیوند یازدهم بی‌صدا حذف نمی‌شود؛ سازنده پیام روشن می‌دهد و سقف را حفظ می‌کند');
  p.input('#linkList [data-lt="0"]','x'.repeat(121));
  ok(p.window.eval('validateBeforeSave()===false')&&p.txt('#toast').includes('عنوان هر پیوند')
      &&p.window.eval('S.links[0].t.length===121'),
    'عنوان طولانیِ دست‌کاری‌شده پیش از ذخیره رد می‌شود و بریده نمی‌شود');
  p.input('#linkList [data-lt="0"]','راهنمای محلی');
  p.input('#linkList [data-lu="0"]','x'.repeat(2049));
  ok(p.window.eval('validateBeforeSave()===false')&&p.txt('#toast').includes('نشانی هر پیوند')
      &&p.window.eval('S.links[0].u.length===2049'),
    'نشانی بیش‌ازحد هم پیش از ذخیره رد می‌شود و برای اصلاح باقی می‌ماند');
  p.input('#introText','x'.repeat(3001));
  ok(p.window.eval('validateBeforeSave()===false')&&p.txt('#toast').includes('توضیحات ابتدا')
      &&p.window.eval('S.intro.length===3001'),
    'توضیحات طولانی در اعتبارسنجی ذخیره متوقف می‌شود، نه اینکه بی‌صدا کوتاه شود');
  ok(p.network.length===0,'ویرایش متن و پیوند فقط در سازندهٔ محلی انجام می‌شود');
}

/* ── ۶ز) مسیر بازبینی و رسانه فقط برچسب نمونه‌اند ── */
{
  console.log('\n── مسیر محلی و رسانهٔ آغاز فرم ──');
  const p=await load('create.html',makeStore());
  p.set('#notifyTo','کارتابل + بله');
  ok(p.window.eval("S.notify.to==='کارتابل + بله'&&S.notify.on===false")
      &&p.txt('#review').includes('کارتابل + بله')&&p.txt('#review').includes('ارسال بیرونی خاموش'),
    'انتخاب مسیر بله فقط یادداشت محلی را عوض می‌کند؛ ارسال بیرونی خاموش می‌ماند');
  p.set('#notifyTo','کارتابل + ایمیل');
  ok(p.window.eval("S.notify.to==='کارتابل + ایمیل'&&S.notify.on===false")&&p.network.length===0,
    'انتخاب مسیر ایمیل هم ارسال، ایمیل تأییدی یا درخواست شبکه نمی‌سازد');
  p.set('#deptPick','data');
  ok(p.window.eval("S.dept==='data'&&S.notify.expert.includes('نادری')")
      &&p.txt('#deptHint').includes('پیش‌فرض پیگیری'),
    'تغییر بخش، کارشناس همان بخش را برای پیگیری نمونه انتخاب می‌کند');
  p.click('#introMedia');
  ok(p.window.eval("S.introMedia==='image'")&&p.txt('#introMediaLbl')==='تصویر'
      &&p.txt('#review').includes('نشان نمونه'),
    'رسانهٔ آغاز با یک کلیک فقط به برچسب تصویر نمونه تغییر می‌کند');
  p.click('#introMedia');p.click('#introMedia');
  ok(p.window.eval("S.introMedia==='video'")&&p.txt('#introMediaLbl')==='ویدیو',
    'چرخهٔ نوع رسانه فایل واقعی را پیوست یا منتشر نمی‌کند');
  p.input('#introMediaNote','توضیح پوستر نمونه');
  ok(p.window.eval("S.introMediaNote==='توضیح پوستر نمونه'")
      &&p.doc.querySelector('#introMediaNote').maxLength===160&&p.network.length===0,
    'توضیح رسانه سقف دارد و فقط در دادهٔ محلی سازنده می‌ماند');
}

/* ── ۶ح) اجباری، پیش‌پرکردن و خروجی هر فیلد با سوییچ واقعی ── */
{
  console.log('\n── تنظیم سوییچ‌های فیلد ──');
  const builder=await load('create.html',makeStore());
  builder.window.eval("S.fields=[];addField('fullname');editField(S.fields[0].id)");
  ok(builder.doc.querySelector('#fdProf').classList.contains('on')
      &&builder.doc.querySelector('#fdProf').getAttribute('aria-checked')==='true',
    'فیلد نام به‌صورت پیش‌فرض پیشنهاد پرشدن از نمایهٔ محلی دارد');
  builder.click('#fdProf');builder.click('#fdReq');builder.click('#fdCol');
  ok(!builder.doc.querySelector('#fdProf').classList.contains('on')
      &&builder.doc.querySelector('#fdProf').getAttribute('aria-checked')==='false'
      &&builder.doc.querySelector('#fdReq').classList.contains('on')
      &&builder.doc.querySelector('#fdReq').getAttribute('aria-checked')==='true'
      &&!builder.doc.querySelector('#fdCol').classList.contains('on')
      &&builder.doc.querySelector('#fdCol').getAttribute('aria-checked')==='false',
    'کلیدهای اجباری، پیش‌پرکردن و ورود به خروجی با ظاهر و وضعیت دسترس‌پذیر هماهنگ می‌شوند');
  builder.window.eval('saveField()');
  builder.window.eval("addField('mobile');editField(S.fields[1].id)");
  ok(builder.doc.querySelector('#fdVerifyBox').style.display==='block'
      &&builder.txt('#fdVerifyStatus').includes('غیرفعال')&&!builder.doc.querySelector('#fdVerify')
      &&builder.doc.querySelector('#fdVerifyClear').style.display==='none',
    'تأیید شماره قابلیت زنده جلوه داده نمی‌شود و برای فیلد تازه هیچ درخواست تأییدی ساخته نمی‌شود');
  builder.window.eval("S.fields[1].verify=true;editField(S.fields[1].id)");
  ok(builder.txt('#fdVerifyStatus').includes('قدیمی')
      &&builder.doc.querySelector('#fdVerifyClear').style.display!=='none',
    'پرچم تأیید قدیمی جداگانه شناسایی و برای پاک‌سازی در دسترس قرار می‌گیرد');
  builder.click('#fdVerifyClear');
  const fields=JSON.parse(builder.window.eval('JSON.stringify(S.fields)'));
  ok(fields[0].req===true&&fields[0].prof===false&&fields[0].col===false
      &&fields[1].prof===true&&fields[1].verify===false
      &&builder.doc.querySelector('#fdVerifyClear').style.display==='none',
    'تنظیم‌های پشتیبانی‌شده ذخیره و پرچم قدیمیِ احرازِ پشتیبانی‌نشده پاک می‌شود');
  const store=makeStore({'nora-forms':JSON.stringify([{id:'f-field-switches',name:'فرم کلید فیلد',model:'datacollect',need:'other',display:'all',fields,fin:[]}]),
    'nora-home-user':JSON.stringify({name:'پروفایل نمونه',mobile:'+989121234567'})}),
    p=await load('form.html',store,'?fid=f-field-switches&kind=other');
  ok(p.errors.length===0&&p.doc.querySelector('#qa0').value===''&&p.doc.querySelector('#qa1').value===''
      &&p.doc.querySelector('#profileAssist').style.display!=='none'
      &&p.txt('#qall').includes('تأیید پیامکی یا هویتی فعال نیست'),
    'نام و موبایل تا درخواست صریح مستقل و خالی می‌مانند؛ احراز مالکیت شماره‌ای در کار نیست');
  p.click('#profilePrefill');
  ok(p.doc.querySelector('#qa0').value===''&&p.doc.querySelector('#qa1').value==='+989121234567',
    'پس از کلیک فقط موبایلِ علامت‌خورده پیشنهاد می‌شود و نامِ غیرفعال دست‌نخورده می‌ماند');
  ok(p.window.__NORA_FORM_PREVIEW.validate().includes('اجباری'),
    'کلید اجباری روی پاسخ‌دهنده هم اعمال می‌شود');
  p.input('#qa0','مریم نمونه');p.window.__NORA_FORM_PREVIEW.finish();
  const reg=JSON.parse(store.getItem('nora-regs')||'[]')[0];
  ok(reg&&reg.ans.some(a=>a.l==='نام و نام خانوادگی'&&a.col===false)
      &&reg.ans.some(a=>a.l==='موبایل'&&!Object.hasOwn(a,'verifyRequested')&&!Object.hasOwn(a,'verified'))
      &&p.network.length===0,
    'پیش‌نمایش خصوصی هیچ درخواست/نتیجهٔ ساختگیِ احراز ذخیره نمی‌کند و شبکه‌ای هم صدا نمی‌زند');
}

/* ── ۶ط) سقف عنوان، راهنما و متن جای‌نگهدار فیلد ── */
{
  console.log('\n── طول نوشته‌های فیلد ──');
  const p=await load('create.html',makeStore());
  p.window.eval("S.fields=[];addField('text');S.fields[0].media='image';editField(S.fields[0].id)");
  ok(p.doc.querySelector('#fdTitle').maxLength===160&&p.doc.querySelector('#fdHelp').maxLength===300
      &&p.doc.querySelector('#fdPlaceholder').maxLength===120&&p.doc.querySelector('#fdMediaNote').maxLength===160,
    'عنوان، راهنما، جای‌نگهدار و یادداشت رسانه سقف‌های جداگانه دارند');
  p.input('#fdTitle','x'.repeat(161));
  ok(p.window.eval('saveField()')===false&&p.txt('#toast').includes('عنوان فیلد')
      &&p.window.eval('S.fields[0].l.length<161'),
    'عنوان بیش‌ازحد بدون کوتاه‌سازی ذخیره متوقف می‌شود');
  p.input('#fdTitle','پرسش نمونه');p.input('#fdHelp','h'.repeat(301));
  ok(p.window.eval('saveField()')===false&&p.txt('#toast').includes('راهنمای پرسش'),
    'راهنمای بیش‌ازحد هم پیش از ذخیره رد می‌شود');
  p.input('#fdHelp','راهنمای کوتاه');p.input('#fdPlaceholder','p'.repeat(121));
  ok(p.window.eval('saveField()')===false&&p.txt('#toast').includes('متن راهنمای داخل کادر'),
    'جای‌نگهدار بلند به‌جای بریده‌شدن برای اصلاح می‌ماند');
  p.input('#fdPlaceholder','بنویسید');p.input('#fdMediaNote','m'.repeat(161));
  ok(p.window.eval('saveField()')===false&&p.txt('#toast').includes('توضیح رسانه'),
    'یادداشت رسانه هم از سقف مجاز عبور نمی‌کند');
  p.input('#fdMediaNote','تصویر نمونه');
  ok(p.window.eval('saveField()')===true&&p.window.eval("S.fields[0].l==='پرسش نمونه'&&S.fields[0].help==='راهنمای کوتاه'&&S.fields[0].placeholder==='بنویسید'&&S.fields[0].mediaNote==='تصویر نمونه'"),
    'پس از اصلاح، مقادیر کامل و بدون بریدن در همان فیلد ذخیره می‌شوند');
}

/* ── ۶ی) نوشته‌های بلندِ بستهٔ محلی هم بی‌صدا ذخیره نمی‌شوند ── */
{
  console.log('\n── اعتبارسنجی فیلدهای بسته‌شده ──');
  const p=await load('create.html',makeStore());
  p.window.eval("S.fields=[Object.assign(freshField('text','packed-text'),{l:'L'.repeat(161),help:'help',placeholder:'hint',mediaNote:'note'})];renderCanvas()");
  ok(p.window.eval('validateBeforeSave()===false')&&p.txt('#toast').includes('عنوان فیلد')
      &&p.doc.querySelector('#fdTitle').value.length===161,
    'عنوان بلندِ فرم legacy/بسته‌شده هنگام ذخیره رد می‌شود و مقدار برای اصلاح می‌ماند');
  p.window.eval("S.fields[0].l='عنوان کوتاه';S.fields[0].help='h'.repeat(301);renderCanvas()");
  ok(p.window.eval('validateBeforeSave()===false')&&p.txt('#toast').includes('راهنمای پرسش'),
    'راهنمای بیش‌ازحدِ فیلدی که ویرایشگرش باز نبود هم اعتبارسنجی می‌شود');
  p.window.eval("S.fields[0].help='راهنمای کوتاه';S.fields[0].placeholder='p'.repeat(121);renderCanvas()");
  ok(p.window.eval('validateBeforeSave()===false')&&p.txt('#toast').includes('متن راهنمای داخل کادر'),
    'جای‌نگهدار بسته‌شده هم پیش از ذخیره از نظر طول بررسی می‌شود');
  p.window.eval("S.fields[0].placeholder='کوتاه';S.fields[0].mediaNote='m'.repeat(161);renderCanvas()");
  ok(p.window.eval('validateBeforeSave()===false')&&p.txt('#toast').includes('توضیح رسانه'),
    'یادداشت رسانهٔ بسته‌شده هم از سقف خودش عبور نمی‌کند');
  p.window.eval("S.fields[0].mediaNote='یادداشت درست';renderCanvas()");
  ok(p.window.eval('validateBeforeSave()===true'),'با اصلاح متن‌ها، همان فیلد legacy دوباره آمادهٔ ذخیره می‌شود');
}

/* ── ۶ک) ذخیره و بازیابی بستهٔ محلی بدون پاسخ شخصی ── */
{
  console.log('\n── بسته‌های محلی فیلدها ──');
  const store=makeStore(),p=await load('create.html',store);
  p.window.eval(`S.fields=[
    {id:'pack-source',t:'choice',l:'حوزه',req:true,opts:[{l:'آموزش'},{l:'پژوهش'}],conditions:[],conditionLogic:'all'},
    {id:'pack-dependent',t:'area',l:'توضیح',req:false,opts:[],conditions:[{field:'pack-source',op:'eq',value:'پژوهش'}],conditionLogic:'all'}];renderCanvas()`);
  p.click('[data-quick="save"]');
  ok(p.doc.querySelector('#shPackSave').classList.contains('on')
      &&p.txt('#shPackSave').includes('پاسخ‌های فرم در بسته قرار نمی‌گیرند'),
    'ذخیرهٔ بسته روشن می‌کند که فقط تعریف فیلدها می‌ماند، نه پاسخ‌های اشخاص');
  p.set('#packName','بستهٔ نمونهٔ شرطی');p.click('#packSave');
  let packs=JSON.parse(store.getItem('nora-form-packs')||'[]'),pack=packs[0];
  ok(pack&&pack.name==='بستهٔ نمونهٔ شرطی'&&pack.fields.length===2
      &&pack.fields[1].conditions[0].field==='pack-source'&&!store.getItem('nora-regs'),
    'بستهٔ نام‌دار با گزینه‌ها و شرط وابسته فقط در localStorage ذخیره شد');
  p.window.eval("S.fields[0].l='موقت';renderCanvas()");
  p.click('[data-quick="saved:'+pack.id+'"]');
  const fields=JSON.parse(p.window.eval('JSON.stringify(S.fields)'));
  packs=JSON.parse(store.getItem('nora-form-packs')||'[]');pack=packs[0];
  ok(fields.length===2&&fields[0].l==='حوزه'&&String(fields[0].id)!=='pack-source'
      &&String(fields[1].conditions[0].field)===String(fields[0].id)&&fields[1].conditions[0].value==='پژوهش',
    'بازیابی بسته شناسه‌ها را تازه و ارجاع شرط را درست بازسازی می‌کند');
  ok(pack.fields[0].id==='pack-source'&&pack.fields[0].l==='حوزه'
      &&!store.getItem('nora-regs')&&p.network.length===0,
    'اعمال بسته، نسخهٔ ذخیره‌شده را دست‌کاری نمی‌کند و پاسخ شخصی یا درخواست شبکه نمی‌سازد');
}

/* ── ۶ل) مدل‌های فرم و نگاشت هدف، بدون وعدهٔ خدمت واقعی ── */
{
  console.log('\n── مدل‌های فرم‌ساز ──');
  const p=await load('create.html',makeStore());
  const modelRows=JSON.parse(p.window.eval('JSON.stringify(MODELS.map(m=>({id:m.k,label:m.tn,need:needForModel(m.k)})))'));
  ok(modelRows.length===9&&modelRows.map(x=>x.id).join(',')==='registration,questionnaire,survey,contest,exam,attendance,datacollect,order,election',
    'هر ۹ مدل فرم در انتخاب‌گر فرم‌ساز حضور دارند');
  const expected={registration:'reg',questionnaire:'other',survey:'survey',contest:'exam',exam:'exam',attendance:'other',datacollect:'other',order:'reg',election:'other'};
  let allSelected=true;
  for(const model of modelRows){
    p.click('[data-model="'+model.id+'"]');
    if(p.window.eval('S.model')!==model.id||p.window.eval('S.need')!==expected[model.id]
        ||p.doc.querySelectorAll('[data-model].tile.on').length!==1
        ||p.doc.querySelector('[data-model="'+model.id+'"]').classList.contains('on')===false)allSelected=false;
  }
  ok(allSelected&&p.window.eval('cardPaymentReady()===false&&centralFormMethods().length===0'),
    'انتخاب هر مدل نیاز فرم و کاشی فعال را هماهنگ می‌کند؛ هیچ‌کدام درگاه یا کارت فعال نمی‌کند');
  ok(p.doc.querySelector('[data-model="survey"]').textContent.includes('ناشناس‌بودن یا آمار کامل تضمین نیست')
      &&p.doc.querySelector('[data-model="contest"]').textContent.includes('رتبه‌بندی/قرعه‌کشی فعال نیست')
      &&p.doc.querySelector('[data-model="exam"]').textContent.includes('زمان‌سنجی و نمره‌دهی فعال نیست')
      &&p.doc.querySelector('[data-model="attendance"]').textContent.includes('حضور واقعی تأیید نمی‌شود')
      &&p.doc.querySelector('[data-model="election"]').textContent.includes('رأی یکتا/محرمانه تضمین نمی‌شود'),
    'مدل‌های حساس، نبود تضمین ناشناس‌بودن، رتبه‌بندی، زمان‌سنجی، حضور و رأی یکتا را پنهان نمی‌کنند');
  ok(p.network.length===0,'جابه‌جایی مدل‌ها فقط در مرورگر انجام می‌شود');
}

/* ── ۶م) گزینه‌ها: ویرایش، یکتایی و مرز تعداد ── */
{
  console.log('\n── فهرست گزینه‌ها و محدودیت چندانتخابی در ویرایشگر ──');
  const page=await load('create.html',makeStore());
  page.window.eval(`S.title='فرم گزینه‌ها';S.fields=[freshField('choice','choice-list'),
    Object.assign(freshField('multi','multi-list'),{l:'چندانتخابی',opts:[{l:'قرمز'},{l:'آبی'},{l:'سبز'}],minSelect:null,maxSelect:null})];renderCanvas();editField('choice-list')`);
  ok(page.doc.querySelector('#fdOptionsBox').style.display==='block'&&page.all('#fdOptions [data-optl]').length===2,
    'گزینه‌های ویرایش‌پذیر و شمارنده برای پرسش انتخابی نمایش داده می‌شوند');
  page.click('#fdOptions [data-optdel="0"]');page.click('#fdOptions [data-optdel="0"]');
  ok(page.doc.querySelector('#fdOptionsBox').style.display==='block'&&!page.doc.querySelector('#fdAddOption').disabled
      &&page.doc.querySelector('#fdOptionCount').textContent.includes('۰'),
    'حذف آخرین گزینه ویرایشگر را پنهان نمی‌کند و امکان افزودن دوباره می‌ماند');
  ok(page.window.eval('validateBeforeSave()')===false&&page.txt('#toast').includes('دست‌کم')
      &&page.doc.querySelector('#fdOptionsBox').style.display==='block',
    'فیلد انتخابیِ بدون گزینه ذخیره نمی‌شود و پنل افزودن گزینه در دسترس می‌ماند');
  page.click('#fdAddOption');
  ok(page.all('#fdOptions [data-optl]').length===1&&page.doc.querySelector('#fdOptionCount').textContent.includes('۱'),
    'افزودن گزینه از فهرست خالی همان فیلد را دوباره قابل‌استفاده می‌کند');
  page.input('#fdOptions [data-optl="0"]','');page.window.eval('saveField()');
  ok(page.window.eval('validateBeforeSave()')===false&&page.txt('#toast').includes('عنوان')
      &&page.window.eval("S.fields.find(f=>f.id==='choice-list').opts.length===1&&S.fields.find(f=>f.id==='choice-list').opts[0].l===''"),
    'عنوان خالی بی‌صدا حذف نمی‌شود و برای اصلاح در فهرست می‌ماند');
  page.input('#fdOptions [data-optl="0"]','گزینه');page.click('#fdAddOption');
  page.input('#fdOptions [data-optl="1"]',' گزینه ');
  ok(page.window.eval('validateBeforeSave()')===false&&page.txt('#toast').includes('یکتا')
      &&page.all('#fdOptions [data-optl]').length===2,
    'گزینه‌های تکراری پس از trim و بدون حذف خاموش رد می‌شوند تا کاربر اصلاح کند');
  page.input('#fdOptions [data-optl="0"]','Straße');page.input('#fdOptions [data-optl="1"]','STRASSE');
  ok(page.window.eval('firstInvalidOptionSettings()?.message.includes("یکتا")'),
    'casefold کامل، از جمله ß و SS، در ویرایشگر با API هم‌معناست');
  page.input('#fdOptions [data-optl="0"]',String.fromCharCode(0xFEFF)+'Ａ'+String.fromCharCode(0xFEFF));
  page.input('#fdOptions [data-optl="1"]','a');
  ok(page.window.eval('firstInvalidOptionSettings()?.message.includes("یکتا")'),
    'NFKC و trim یکسان، شکل تمام‌عرض و BOM پیرامونی را با حرف لاتین برابر می‌گیرد');
  page.input('#fdOptions [data-optl="0"]','Σ');page.input('#fdOptions [data-optl="1"]','ς');
  ok(page.window.eval('firstInvalidOptionSettings()?.message.includes("یکتا")'),
    'حروف سیگمای یونانی با حالت پایانی متفاوت، تکراری شناخته می‌شوند');
  page.input('#fdOptions [data-optl="0"]','🙂'.repeat(120));
  ok(page.window.eval('firstInvalidOptionSettings()===null'),
    'سقف ۱۲۰ نویسه برای ۱۲۰ code point ایموجی با API هم‌خوان است');
  page.input('#fdOptions [data-optl="0"]','🙂'.repeat(121));
  ok(page.window.eval('firstInvalidOptionSettings()?.optionIndex===0'),
    'نویسهٔ ۱۲۱ام حتی اگر surrogate pair باشد رد می‌شود');
  page.input('#fdOptions [data-optl="0"]',String.fromCharCode(0x85)+'گزینه');
  ok(page.window.eval('firstInvalidOptionSettings()?.optionIndex===0'),
    'کنترل‌های C1 نیز مانند C0 در ویرایشگر و API پذیرفته نمی‌شوند');
  page.input('#fdOptions [data-optl="0"]',String.fromCharCode(0xD800)+'گزینه');
  ok(page.window.eval('firstInvalidOptionSettings()?.optionIndex===0'),
    'surrogate منفرد در عنوان گزینه رد می‌شود تا در JSON یا پاسخ API خطا نسازد');

  page.window.eval("S.fields.find(f=>f.id==='choice-list').opts=Array.from({length:100},(_,i)=>({l:'item-'+i}));editField('choice-list')");
  ok(page.all('#fdOptions [data-optl]').length===100&&page.doc.querySelector('#fdAddOption').disabled
      &&page.window.eval('firstInvalidOptionSettings()===null'),
    '۱۰۰ گزینه مرز مجاز است و دکمهٔ افزودن در همان سقف غیرفعال می‌شود');
  page.window.eval("S.fields.find(f=>f.id==='choice-list').opts.push({l:'item-100'});editField('choice-list')");
  ok(page.all('#fdOptions [data-optl]').length===101&&page.window.eval('validateBeforeSave()===false')
      &&page.doc.querySelector('#fdOptionCount').textContent.includes('۱۰۱'),
    'گزینهٔ ۱۰۱ بی‌صدا بریده نمی‌شود و ذخیره تا حذف آگاهانه متوقف می‌ماند');
  page.click('#fdOptions [data-optdel="100"]');page.window.eval('saveField()');
  ok(page.window.eval("S.fields.find(f=>f.id==='choice-list').opts.length===100&&firstInvalidOptionSettings()===null"),
    'حذف صریح گزینهٔ اضافی، دقیقاً فهرست را به سقف معتبر بازمی‌گرداند');

  page.window.eval("editField('multi-list')");
  ok(page.doc.querySelector('#fdMultiLimitsBox').style.display!=='none',
    'حداقل و حداکثر انتخاب فقط برای نوع چندانتخابی نمایش داده می‌شوند');
  page.set('#fdMinSelect','۲');page.set('#fdMaxSelect','۳');page.window.eval('saveField()');
  ok(page.window.eval("S.fields.find(f=>f.id==='multi-list').minSelect===2&&S.fields.find(f=>f.id==='multi-list').maxSelect===3&&firstInvalidOptionSettings()===null"),
    'محدودیت انتخاب، رقم فارسی را به عدد صحیح تبدیل و سازگاری آن با تعداد گزینه‌ها را تأیید می‌کند');
  page.set('#fdMinSelect','۰');page.window.eval('saveField()');
  ok(page.window.eval("firstInvalidOptionSettings()?.target==='#fdMinSelect'"),
    'حداقل صفر به‌عنوان عدد صحیح مثبت نامعتبر شناخته می‌شود');
  page.set('#fdMinSelect','۴');page.set('#fdMaxSelect','۳');page.window.eval('saveField()');
  ok(page.window.eval("firstInvalidOptionSettings()?.target==='#fdMinSelect'"),
    'حداقل بزرگ‌تر از تعداد گزینه‌های موجود رد می‌شود');
  page.set('#fdMinSelect','۳');page.set('#fdMaxSelect','۲');page.window.eval('saveField()');
  ok(page.window.eval("firstInvalidOptionSettings()?.target==='#fdMinSelect'"),
    'حداقل بیشتر از حداکثر رد می‌شود');
  page.set('#fdMinSelect','۱٫۵');page.set('#fdMaxSelect','۳');page.window.eval('saveField()');
  ok(page.window.eval("firstInvalidOptionSettings()?.target==='#fdMinSelect'"),
    'مقدار اعشاری حد انتخاب پذیرفته نمی‌شود');
  page.set('#fdMinSelect','');page.set('#fdMaxSelect','۴');page.window.eval('saveField()');
  ok(page.window.eval("firstInvalidOptionSettings()?.target==='#fdMaxSelect'"),
    'حداکثر بیشتر از تعداد گزینه‌ها رد می‌شود');
  page.set('#fdMinSelect','');page.set('#fdMaxSelect','۳');page.window.eval('saveField()');
  ok(page.window.eval("S.fields.find(f=>f.id==='multi-list').minSelect===null&&S.fields.find(f=>f.id==='multi-list').maxSelect===3&&firstInvalidOptionSettings()===null"),
    'خالی‌گذاشتن حداقل مجاز است و حداکثر مستقل به‌درستی ذخیره می‌شود');
}

/* ── ۶ت) مرکز فرم‌ها در تولید: دریافت خودکار فهرست با نشست معتبر؛ مهمان بدون درخواست محافظت‌شده ── */
{
  console.log('\n── مرکز فرم‌ها: بارگیری خودکار ──');
  const formsCalls=api=>api.calls.filter(call=>call.path==='/api/forms'&&call.method==='GET').length;
  /* الف) نشست معتبر مالک: دقیقاً یک بار health → auth/me → /api/forms؛ کارت‌ها بدون کلیک دیده می‌شوند */
  const record={id:'auto-form-1',name:'فرم خودکار',model:'registration',need:'reg',slug:'auto/one',ev:'',fields:[{id:'q1',t:'text',l:'پرسش'}],
    settings:{display:'one'},status:'published',version:2,response_count:3,created_at:'2026-01-01T00:00:00+00:00',updated_at:'2026-10-01T00:00:00+00:00'};
  const api=makeFormsApiMock({id:'auto-form-1',initialRecord:record});
  const page=await load('builder.html',makeStore(),'',api.fetch,{fixtureMode:false});
  await wait(80);
  ok(page.errors.length===0&&page.doc.querySelector('#formCards [data-form="auto-form-1"]')
      &&page.doc.querySelector('#serverFormsMessage').dataset.state==='loaded'
      &&page.txt('#serverFormsMessageText').includes('۱ فرم از API دریافت شد')
      &&formsCalls(api)===1&&api.calls.filter(call=>call.path==='/api/auth/me').length===1
      &&page.doc.querySelector('#serverFormsRetry').hidden===true&&page.doc.querySelector('#syncServerForms').disabled===false,
    'با نشست معتبر، فهرست بدون کلیک و فقط با یک درخواست /api/forms از سرور آمد');
  const requestsBefore=page.network.length;
  page.window.dispatchEvent(new page.window.Event('pageshow'));await wait(40);
  ok(page.network.length===requestsBefore&&formsCalls(api)===1,'رندر دوباره یا بازگشت به صفحه درخواست تکراری نمی‌فرستد');
  /* ب) تازه‌سازی دستی: همان دکمه دوباره می‌گیرد؛ دو کلیک پشت‌سرهم فقط یک درخواست */
  page.click('#syncServerForms');page.click('#syncServerForms');await wait(80);
  ok(formsCalls(api)===2&&page.doc.querySelector('#serverFormsMessage').dataset.state==='loaded',
    'تازه‌سازی دستی یک درخواست تازه می‌فرستد و کلیک تکراری در حین دریافت، درخواست دوم نمی‌سازد');
  /* پ) بدون نشست: مهمان فقط بررسی نشست می‌بیند؛ /api/forms هرگز صدا زده نمی‌شود؛ پیوند ورود دیده می‌شود */
  const guestApi=makeFormsApiMock({authenticated:false,id:'auto-form-1',initialRecord:record});
  const guest=await load('builder.html',makeStore(),'',guestApi.fetch,{fixtureMode:false});
  await wait(80);
  ok(guest.errors.length===0&&formsCalls(guestApi)===0&&guest.doc.querySelector('#serverFormsMessage').dataset.state==='unauthenticated'
      &&guest.doc.querySelector('#serverFormsLogin').style.display!=='none'&&!guest.doc.querySelector('#formCards [data-form]')
      &&guest.txt('#formCards').includes('وارد شوید'),
    'مهمان درخواست محافظت‌شدهٔ فهرست نمی‌گیرد و پیوند ورود می‌بیند');
  /* ت) فهرست واقعاً خالی: حالت خالی فقط پس از پاسخ موفق */
  const emptyApi=makeFormsApiMock({id:'none'});
  const empty=await load('builder.html',makeStore(),'',emptyApi.fetch,{fixtureMode:false});
  await wait(80);
  ok(formsCalls(emptyApi)===1&&empty.doc.querySelector('#serverFormsMessage').dataset.state==='loaded'
      &&empty.txt('#formCards').includes('هنوز فرمی در فهرست سرور نیست')&&!empty.doc.querySelector('[data-forms-loading]'),
    'فهرست خالی سرور پس از پاسخ موفق، حالت خالی درست را نشان می‌دهد');
  /* ث) شکست API و تلاش دوباره: اولین /api/forms خطای ۵۰۰ می‌دهد؛ «تلاش دوباره» فهرست را می‌آورد */
  let failOnce=true;
  const flakyApi=makeFormsApiMock({id:'auto-form-1',initialRecord:record});
  const flakyFetch=async(path,init={})=>{
    if(path==='/api/forms'&&String(init.method||'GET').toUpperCase()==='GET'&&failOnce){failOnce=false;flakyApi.calls.push({path,method:'GET'});
      return {ok:false,status:500,json:async()=>({detail:'server_error'})}}
    return flakyApi.fetch(path,init);
  };
  const flaky=await load('builder.html',makeStore(),'',flakyFetch,{fixtureMode:false});
  await wait(80);
  ok(flaky.doc.querySelector('#serverFormsMessage').dataset.state==='error'&&flaky.doc.querySelector('#serverFormsRetry').hidden===false
      &&!flaky.doc.querySelector('#formCards [data-form]')&&flaky.txt('#formCards').includes('تلاش دوباره'),
    'شکست API پیام روشن و دکمهٔ تلاش دوباره می‌دهد و حالت خالی را جعل نمی‌کند');
  flaky.click('#serverFormsRetry');await wait(80);
  ok(flaky.doc.querySelector('#serverFormsMessage').dataset.state==='loaded'&&flaky.doc.querySelector('#formCards [data-form="auto-form-1"]')
      &&flaky.doc.querySelector('#serverFormsRetry').hidden===true&&formsCalls(flakyApi)===2,
    'تلاش دوباره فهرست را از سرور می‌گیرد و دکمهٔ تلاش پنهان می‌شود');
}

/* ── ۷) پیش‌نویس‌های سرور در فهرست مرکزی فرم‌ها ── */
{
  console.log('\n── همگام‌سازی پیش‌نویس‌های سروری ──');
  const api=makeFormsApiMock({id:'server-builder-1'});
  await api.fetch('/api/forms',{method:'POST',body:JSON.stringify({name:'فرم سروری آزمایشی',model:'registration',need:'reg',slug:'test/form',ev:'ev-server',fields:[{id:'q1',t:'text',l:'پرسش'}],settings:{kind:'ثبت‌نام',eventVisible:true}})});
  const store=makeStore(),page=await load('builder.html',store,'',api.fetch);
  ok(page.errors.length===0,'فهرست فرم‌ها بی‌خطا بار شد');
  ok(page.network.length===0,'در حالت fixture آزمون، فهرست تا اقدام مالک هیچ API سروری را صدا نزد (در تولید خودکار است؛ بخش ۶ت)');
  page.click('#syncServerForms');await wait(100);
  const cached=JSON.parse(store.getItem('nora-forms')||'[]').find(row=>row.id==='server-builder-1');
  ok(cached&&cached.serverDraft===true&&cached.status==='draft'&&cached.on===0,
    'همگام‌سازی، تعریف سرور را به‌عنوان پیش‌نویس محلیِ سازگار ثبت کرد');
  ok(page.doc.querySelector('[data-form="server-builder-1"]')?.textContent.includes('پیش‌نویس سرور')
      &&page.txt('#serverFormsMessageText').includes('از API دریافت شد'),
    'پیش‌نویس در فهرست با وضعیت منتشرنشده و تعداد دریافت‌شده دیده می‌شود');
  page.click('[data-form="server-builder-1"]');
  const panelText=page.txt('#infoBox');
  ok(page.txt('#pLink').includes('منتشر نشده')&&!page.doc.querySelector('#pLink').textContent.includes('test/form')
      &&page.all('[data-copy="#pLink"][disabled]').length===2,
    'پیش‌نویس پیوند عمومی نشان نمی‌دهد و کنترل‌های کپی پیوند غیرفعال‌اند');
  ok(panelText.includes('پیش‌نویس سرور')&&!panelText.includes('منتشرشده')
      &&panelText.includes('اعتبارسنجی نهایی با backend')
      &&panelText.includes('شمارش endpoint'),
    'پنل وضعیت واقعی پیش‌نویس و شمار API را نشان می‌دهد و قابلیت تخصصیِ اجرا‌نشده را ادعا نمی‌کند');
  ok(page.doc.querySelector('#editFormLink')?.getAttribute('href')==='create.html?fid=server-builder-1'
      &&page.doc.querySelector('#previewFormLink')?.getAttribute('href')==='form.html?fid=server-builder-1&kind=reg&preview=1'
      &&page.txt('#openSettings').includes('ویرایش و ذخیرهٔ پیش‌نویس'),
    'ویرایش پیش‌نویس به فرم‌ساز برمی‌گردد و پیش‌نمایش به همان فرم محلی وصل است');
  const legacy=await load('builder.html',makeStore({'nora-forms':JSON.stringify([
    {id:'legacy-draft',name:'پیش‌نویس قدیمی',status:'draft',slug:'/old/public/path',fields:[{id:'q',t:'text',l:'پرسش'}]}
  ])}));
  ok(legacy.errors.length===0&&legacy.txt('#pStatus').includes('پیش‌نویس محلی')
      &&legacy.txt('#pLink').includes('پیوند عمومی ندارد')
      &&legacy.all('[data-copy="#pLink"][disabled]').length===2
      &&!legacy.txt('#infoBox').includes('منتشر شد'),
    'پیش‌نویس legacy محلی هم پیوند عمومی یا وضعیت انتشار جعلی نشان نمی‌دهد');
}

/* ── ۷الف) پاسخ‌های سروری صفحه‌بندی‌شده و گزارش جدا از نمونه ── */
{
  console.log('\n── پاسخ‌های واقعی و صفحه‌بندی ──');
  const id='server-paged-form',responses=Array.from({length:125},(_,index)=>({
    id:'response-'+String(index+1).padStart(3,'0'),status:'accepted',form_version:3,
    answers:{question:'پاسخ '+String(index+1)},companions:[],registrant_name:'پاسخ‌دهنده '+String(index+1),
    registrant_mobile:'09120000000',created_at:'2026-10-01T12:00:00+00:00',updated_at:'2026-10-01T12:00:00+00:00'
  }));
  const record={id,name:'پرسشنامهٔ سروری',model:'questionnaire',need:'survey',slug:'server-paged',ev:'',
    fields:[{id:'question',t:'text',l:'پاسخ'}],settings:{display:'all'},status:'published',version:3,
    created_at:'2026-01-01T00:00:00+00:00',updated_at:'2026-10-01T00:00:00+00:00'};
  const api=makeFormsApiMock({id,initialRecord:record,responses}),p=await load('builder.html',makeStore(),'',api.fetch);
  p.click('#syncServerForms');await wait(80);
  p.click('[data-form="'+id+'"]');await wait(100);
  ok(p.errors.length===0&&p.doc.querySelectorAll('#answersBox tbody tr[data-person]').length===50
      &&p.txt('#answersBox').includes('۱۲۵ پاسخ')
      &&p.doc.querySelector('#answersBox [aria-label="صفحهٔ پاسخ‌های بعدی"]')?.disabled===false,
    'فهرست پاسخ API در صفحه‌های ۵۰تایی نشان داده می‌شود و شمار کل از همان endpoint است');
  p.click('#answersBox [aria-label="صفحهٔ پاسخ‌های بعدی"]');await wait(80);
  ok(p.doc.querySelectorAll('#answersBox tbody tr[data-person]').length===50
      &&p.txt('#answersBox').includes('صفحهٔ ۲ از ۳')
      &&api.calls.some(call=>call.path==='/api/forms/'+id+'/responses?limit=50&offset=50'),
    'دکمهٔ صفحهٔ بعد offset واقعی را به API می‌فرستد و صفحهٔ دوم را جایگزین می‌کند');
  p.click('#answersBox tbody tr[data-person]');
  ok(p.doc.querySelector('#fUser').classList.contains('on')
      &&p.txt('#usName')==='پاسخ‌دهنده 51'
      &&p.txt('#usBody').includes('پاسخ 51')
      &&p.txt('#usBody').includes('این پاسخ از سرور خوانده شده'),
    'جزئیات یک پاسخ از رکورد سروری باز می‌شود و منبع آن آشکار است');
  p.click('#usBody [data-go="fPanel"]');
  p.click('[data-go="fReports"]');
  const reportNumbers=p.all('#formReportSummary .metric .n').map(node=>node.textContent.trim());
  ok(reportNumbers.includes('۱۲۵')&&reportNumbers.includes('۱')
      &&p.txt('#formReportList').includes('نمونهٔ مرورگر · در آمار واقعی محاسبه نمی‌شود')
      &&!p.txt('#formReportSummary').includes('پاسخ محلی'),
    'گزارش کل فقط شمار API را جمع می‌زند و نمونه‌های مرورگر را کنار آن با برچسب جدا نشان می‌دهد');
}

/* ── ۷ب) مرکز فرم‌ها، گزارش پاسخ‌ها، تنظیمات پایه و قفل مالی مالک ── */
{
  console.log('\n── مرکز فرم‌ها و دسترسی به تنظیمات ──');
  const managerStore=makeStore({'nora-admin-session':JSON.stringify({u:'maryam.r',role:'admin',personKey:'p2',at:Date.now()})});
  const manager=await load('builder.html',managerStore);
  ok(manager.errors.length===0&&manager.doc.querySelector('#fList').classList.contains('on'),
    'مرکز فرم‌ها بی‌خطا و روی فهرست فرم‌ها باز می‌شود');
  manager.click('[data-go="fReports"]');
  ok(manager.doc.querySelector('#fReports').classList.contains('on')
      &&manager.all('#formReportList [data-form]').length===4
      &&manager.txt('#fReports').includes('نمونه‌های محلی جدا هستند')
      &&manager.txt('#formReportSummary').includes('۰'),
    'گزارش پاسخ‌ها نمونه‌های مرورگر را از آمار API جدا می‌کند و بدون API عدد واقعی جعل نمی‌شود');
  manager.click('[data-go="fSettings"]');
  ok(manager.doc.querySelector('#fSettings').classList.contains('on')
      &&manager.all('#formSettingsList [data-form-settings]').length===4
      &&manager.doc.querySelector('#coreFinanceLink').hidden,
    'تنظیمات پایه برای مدیر در دسترس است؛ پیوند مالی برای او پنهان می‌ماند');
  manager.click('#formSettingsList [data-form-settings]');
  ok(manager.doc.querySelector('#shSettings').classList.contains('on')
      &&manager.doc.querySelector('#fPanel').classList.contains('on')
      &&manager.txt('#setForm').includes('ثبت‌نام کارگاه فن بیان')
      &&manager.doc.querySelector('#setCap').value==='۱۵۰',
    'مرکز تنظیمات همان برگهٔ تنظیمات فرم را با وضعیت و ظرفیت موجود باز می‌کند');
  const ownerStore=makeStore({'nora-admin-session':JSON.stringify({u:'owner',role:'admin',personKey:'p1',at:Date.now()})});
  const owner=await load('builder.html',ownerStore);
  ok(!owner.doc.querySelector('#financeNav').hidden&&!owner.doc.querySelector('#coreFinanceLink').hidden
      &&!owner.doc.querySelector('#moneyFilter').hidden,
    'پیوند و فیلتر مالی فقط برای مالک نمایش داده می‌شوند');
}

/* ── ۸) مدل فرم، ویرایش، اعتبارسنجی و حفظ تنظیمات مالی ── */
{
  console.log('\n── مدل فرم‌ساز، ویرایش و سازگاری پیش‌نمایش ──');
  const store=makeStore(), apiMock=makeFormsApiMock({id:'server-survey-1'}), p=await load('create.html',store,'',apiMock.fetch);
  p.click('[data-model="survey"]');
  ok(p.window.eval('S.model')==='survey'&&p.window.eval('S.need')==='survey'&&p.all('.tile.on')[0]?.dataset.model==='survey'
      &&p.doc.querySelector('#ticketingPanel').hidden,
    'انتخاب مدل نظرسنجی، نوع فرم و کاشی را هماهنگ می‌کند و تنظیم بلیت را پنهان می‌سازد');
  ok(p.doc.querySelector('[data-model="survey"]').textContent.includes('ناشناس‌بودن یا آمار کامل تضمین نیست')&&
     p.doc.querySelector('[data-model="registration"]').textContent.includes('پرداخت فقط با مسیر امن backend'),
    'توضیح مدل‌ها ناشناس‌بودن را تضمین نمی‌کند و پرداخت را به مسیر امن backend مشروط می‌کند');
  p.click('#publish'); await wait(80);
  let rows=JSON.parse(store.getItem('nora-forms')||'[]'), survey=rows.find(x=>x.model==='survey');
  ok(survey&&survey.need==='survey'&&survey.scoring.enabled===true&&!apiMock.record.settings.ticketing,
    'مدل نظرسنجی با need درست ذخیره شد و تنظیم بلیتِ مختص ثبت‌نام به آن نشت نکرد');
  const previewHref=p.doc.querySelector('#donePreview')?.getAttribute('href')||'';
  ok(previewHref.includes('kind=survey'),'پیوند پیش‌نمایش با نوع نظرسنجی ساخته شد');
  const preview=await load('form.html',store,'?fid='+encodeURIComponent(survey.id)+'&kind=survey&preview=1');
  ok(preview.window.__REG?.need==='survey','فرم پاسخ از پیوند ذخیره‌شده در حالت نظرسنجی رندر شد');
  ok(preview.errors.length===0,'پیش‌نمایش فرم نظرسنجی بی‌خطا بار شد');
  const scoreForm={id:'f-score',name:'نظرسنجی امتیازی نمونه',model:'survey',need:'survey',fin:[],
    fields:[{id:'score-q',t:'choice',l:'سنجش',req:true,scoreOn:true,weight:2,opts:[{l:'کم',score:0},{l:'زیاد',score:5}]}]};
  const scoreStore=makeStore({'nora-forms':JSON.stringify([scoreForm])}), scored=await load('form.html',scoreStore,'?fid=f-score&kind=survey');
  scored.click('#next'); scored.click('#qp0 [data-qsel="0"] .opt:last-child'); scored.click('#next');
  const scoreRow=JSON.parse(scoreStore.getItem('nora-regs')||'[]').find(x=>x.form==='f-score');
  ok(scoreRow&&scoreRow.score?.earned===10&&scoreRow.score.max===10&&scoreRow.score.percent===100,
    'پاسخ گزینه‌ای در پیش‌نمایش نظرسنجی امتیاز و وزن ذخیره‌شده را واقعاً محاسبه کرد');

  const prior={id:'f-edit',name:'فرم نظرسنجی قدیمی',model:'survey',need:'reg',eventVisible:false,ev:'ev-old',
    fields:[{id:'q-edit',t:'choice',l:'گزینهٔ امتیازی',req:true,opts:[{l:'الف',score:1},{l:'ب',score:5}]}],
    fin:[{l:'مبلغ نمونه',p:250000,off:10,req:true}],groups:[{n:'گروه نمونه',of:[0],req:true}],
    methods:{card:'legacy-card',bale:false},coupon:{code:'OLD-7',off:7,all:false},sync:{money:1,cap:false,dates:true}};
  const editStore=makeStore({'nora-forms':JSON.stringify([prior])}), editApi=makeFormsApiMock({id:'server-edit-1'});
  const edit=await load('create.html',editStore,'?fid=f-edit',editApi.fetch);
  ok(edit.all('.tile.on')[0]?.dataset.model==='survey'&&edit.window.eval('S.need')==='survey',
    'ویرایش فرم قدیمی، کاشی و need را از مدل ذخیره‌شده بازیابی و ناسازگاری legacy را اصلاح می‌کند');
  const needOnly={id:'f-need-only',name:'نظرسنجی legacy',need:'survey',fields:[{id:'q-old',t:'text',l:'پرسش'}]};
  const needStore=makeStore({'nora-forms':JSON.stringify([needOnly])}), needEdit=await load('create.html',needStore,'?fid=f-need-only');
  ok(needEdit.all('.tile.on')[0]?.dataset.model==='survey'&&needEdit.window.eval('S.need')==='survey',
    'فرم legacy بدون فیلد model از need ذخیره‌شده مدل مناسب را بازیابی می‌کند');
  edit.click('[data-edit="q-edit"]');
  ok(edit.doc.querySelector('#shField').classList.contains('on')&&edit.doc.querySelector('#fdTitle').value==='گزینهٔ امتیازی',
    'بازکردن تنظیم فیلد با شناسهٔ متنیِ قدیمی کار می‌کند');
  edit.click('#shField [data-close]'); edit.click('[data-copy="q-edit"]');
  ok(edit.window.eval('S.fields.length')===2,'کپی فیلد با شناسهٔ متنی نیز به انبار سازنده اضافه شد');
  edit.click('#publish'); await wait(80);
  rows=JSON.parse(editStore.getItem('nora-forms')||'[]');
  const updated=rows.find(x=>x.id==='server-edit-1');
  ok(updated&&updated.model==='survey'&&updated.need==='survey'&&updated.eventVisible===false&&updated.serverDraft===true,
    'فرم قدیمی به‌صورت پیش‌نویس سروری بازذخیره شد و بی‌اجازه منتشر نشد');
  ok(updated&&JSON.stringify(updated.fin)===JSON.stringify(prior.fin)&&JSON.stringify(updated.groups)===JSON.stringify(prior.groups)&&
     JSON.stringify(updated.methods)===JSON.stringify(prior.methods)&&JSON.stringify(updated.coupon)===JSON.stringify(prior.coupon),
    'ذخیرهٔ غیرمالک، مبلغ/گروه/روش/تخفیف مالی قبلی را دست‌نخورده نگه داشت');
  ok(updated&&updated.sync.money===1&&edit.doc.querySelector('#donePreview')?.getAttribute('href').includes('kind=survey'),
    'پرچم مالی قبلی و نوع پیش‌نمایش هم هنگام ویرایش حفظ شدند');

  const invalidStore=makeStore(), invalid=await load('create.html',invalidStore);
  invalid.window.eval('S.fields=[]'); invalid.click('#publish');
  ok(!invalidStore.getItem('nora-forms')&&invalid.window.eval('S.step')==='s2',
    'ذخیرهٔ فرم بی‌فیلد متوقف می‌شود و سازنده را به افزودن فیلد برمی‌گرداند');
  const tooManyStore=makeStore(), tooMany=await load('create.html',tooManyStore);
  tooMany.window.eval("S.fields=Array.from({length:31},(_,i)=>Object.assign(freshField('text',i+1),{l:'فیلد '+(i+1)}));renderCanvas()");
  tooMany.click('#publish');
  ok(!tooManyStore.getItem('nora-forms')&&tooMany.window.eval('S.step')==='s2',
    'فرم بیش از سقف ۳۰ فیلد در سازنده ذخیره نمی‌شود');
  const badConditionApi=makeFormsApiMock(),badCondition=await load('create.html',makeStore(),'',badConditionApi.fetch);
  badCondition.window.eval(`S.title='فرم با قاعدهٔ ناقص';S.fields=[
    Object.assign(freshField('text','condition-source'),{l:'مرجع'}),
    Object.assign(freshField('text','condition-dependent'),{l:'وابسته',conditions:[{field:'condition-source',op:'eq',value:''}],conditionLogic:'all'})];renderCanvas()`);
  badCondition.click('#publish');
  ok(!badConditionApi.calls.some(call=>call.path==='/api/forms'&&call.method==='POST')
      &&badCondition.doc.querySelector('#shField').classList.contains('on')&&badCondition.txt('#toast').includes('مقدار شرط'),
    'شرط بدون مقدار لازم پیش از ذخیره در UI متوقف و همان قاعده برای اصلاح باز می‌شود');
  const dateRuleBuilder=await load('create.html',makeStore());
  ok(dateRuleBuilder.window.eval("validConditionValue({op:'eq',value:'۱۴۰۳/۱۲/۳۰'},{t:'date'})===true")
      &&dateRuleBuilder.window.eval("validConditionValue({op:'eq',value:'۱۴۰۴/۱۲/۳۰'},{t:'date'})===false"),
    'اعتبارسنجی شرط تاریخ در سازنده هم اسفندِ سال کبیسه را می‌پذیرد و روزِ نامعتبر را رد می‌کند');
  const badDateApi=makeFormsApiMock(),badDate=await load('create.html',makeStore(),'',badDateApi.fetch);
  badDate.window.eval(`S.title='فرم با تاریخ نامعتبر';S.fields=[Object.assign(freshField('date','date-source'),{l:'تاریخ'}),
    Object.assign(freshField('text','date-dependent'),{l:'وابسته',conditions:[{field:'date-source',op:'eq',value:'۱۴۰۵/۱۲/۳۰'}],conditionLogic:'all'})];renderCanvas()`);
  badDate.click('#publish');
  ok(!badDateApi.calls.some(call=>call.path==='/api/forms'&&call.method==='POST')
      &&badDate.doc.querySelector('#fdCondVal').value==='۱۴۰۵/۱۲/۳۰'&&badDate.txt('#toast').includes('مقدار شرط'),
    'تاریخ نامعتبرِ سال غیرکبیسه در UI پیش از ارسال به API رد می‌شود و مقدار دقیق برای اصلاح می‌ماند');
  const overLimitStore=makeStore(),overLimit=await load('create.html',overLimitStore);
  overLimit.window.eval(`S.title='فرم با قواعد زیاد';S.fields=[freshField('text','rule-source'),
    Object.assign(freshField('text','rule-dependent'),{conditions:Array.from({length:11},(_,i)=>({field:'rule-source',op:'eq',value:'قاعده '+i})),conditionLogic:'any'})];renderCanvas()`);
  const rejectedOverLimit=overLimit.window.eval('validateBeforeSave()');
  const beforeRules=overLimit.window.eval("conditionRulesForField(S.fields.find(f=>f.id==='rule-dependent'))");
  const overLimitRows=overLimit.all('#fdCondRules [data-condition-row]').length;
  const addDisabled=overLimit.doc.querySelector('#fdAddCondition').disabled;
  const overLimitCount=overLimit.doc.querySelector('#fdCondCount').textContent;
  overLimit.click('#fdCondRules [data-cond-remove="10"]');overLimit.window.eval('saveField()');
  const afterRules=overLimit.window.eval("conditionRulesForField(S.fields.find(f=>f.id==='rule-dependent'))");
  ok(rejectedOverLimit===false&&overLimitRows===11&&beforeRules.length===11&&addDisabled
      &&overLimitCount.includes('۱۱')
      &&afterRules.length===10&&afterRules[9].value==='قاعده 9'&&afterRules[0].value==='قاعده 0'
      &&overLimit.window.eval("S.fields.find(f=>f.id==='rule-dependent').conditionLogic==='any'")
      &&!overLimitStore.getItem('nora-forms'),
    '۱۱ قاعده بدون برش در ویرایشگر باقی می‌مانند، ذخیره متوقف می‌شود و کاربر می‌تواند یکی را آگاهانه حذف کند');
}

/* ── ۸الف) مدل ثابت یا تصادفی بلیت، ذخیرهٔ پیش‌نویس و بازیابی ── */
{
  console.log('\n── مدل بلیت در فرم‌ساز و ذخیرهٔ امنِ پیش‌نویس ──');
  const store=makeStore(),api=makeFormsApiMock({id:'server-ticket-config'}),page=await load('create.html',store,'',api.fetch);
  page.click('[data-go="s2"]');page.click('#ticketingEnabled');
  page.input('#ticketTypeName0','بلیت ثابت');page.click('[data-go="s4"]');page.click('#publish');await wait(80);
  const single=api.record?.settings?.ticketing;
  ok(single?.mode==='single'&&single.types.length===1&&single.types[0].name==='بلیت ثابت',
    'حالت تک‌مدل با یک نام، در تنظیمات پیش‌نویس API ذخیره شد');

  page.click('[data-go="s2"]');page.click('[data-ticket-mode="random"]');
  page.input('[data-ticket-name="0"]','عادی');page.input('[data-ticket-name="1"]','ویژه');
  page.click('#addTicketType');page.input('[data-ticket-name="2"]','مهمان');
  page.click('[data-go="s4"]');page.click('#publish');await wait(80);
  const random=api.record?.settings?.ticketing;
  const mirrored=JSON.parse(store.getItem('nora-forms')||'[]').find(form=>form.id==='server-ticket-config');
  ok(random?.mode==='random'&&random.types.length===3&&random.types.map(type=>type.name).join('|')==='عادی|ویژه|مهمان'
      &&JSON.stringify(mirrored?.ticketing)===JSON.stringify(random),
    'حالت تصادفی سه مدلِ یکتا را به تنظیمات سرور و نسخهٔ همگام‌شدهٔ فرم رساند');
  const reloaded=await load('create.html',store,'?fid=server-ticket-config',api.fetch);
  ok(reloaded.window.eval('S.ticketingEnabled&&S.ticketing.mode===\'random\'&&S.ticketing.types.length===3')
      &&reloaded.doc.querySelector('#ticketingPanel').hidden===false
      &&reloaded.doc.querySelector('[data-ticket-mode="random"]').getAttribute('aria-pressed')==='true'
      &&reloaded.doc.querySelector('[data-ticket-name="2"]').value==='مهمان',
    'ویرایش پیش‌نویس، حالت و هر سه مدل بلیت را پس از بارگذاری دوباره بازیابی کرد');

  const invalidApi=makeFormsApiMock({id:'server-ticket-invalid'}),invalid=await load('create.html',makeStore(),'',invalidApi.fetch);
  invalid.click('[data-go="s2"]');invalid.click('#ticketingEnabled');invalid.click('[data-ticket-mode="random"]');
  invalid.input('[data-ticket-name="1"]','ورودی عمومی');invalid.click('[data-go="s4"]');invalid.click('#publish');
  ok(!invalidApi.calls.some(call=>call.path==='/api/forms'&&call.method==='POST')
      &&invalid.txt('#toast').includes('نام مدل‌های بلیت باید یکتا باشد'),
    'مدل‌های هم‌نام پیش از ارسال به API رد می‌شوند و پیام اصلاحی می‌آید');
}

/* ── ۸) تنظیمات مالی، کوپن نمایشی و سقف کل افراد ── */
{
  console.log('\n── تنظیم مالی و ظرفیت همراهان ──');
  const form={id:'f-money-settings',name:'فرم مالی نمونه',model:'registration',need:'reg',slug:'money-settings',
    guestsOn:true,maxPer:3,compFields:'name-mobile',enabledPaymentMethods:['card_transfer'],fin:[
      {l:'حضوری · نمونه',p:850000,off:15,req:false,d:'رزرو واقعی نیست'},
      {l:'آنلاین · نمونه',p:600000,off:0,req:false}],
    groups:[{n:'شیوهٔ حضور',of:[0,1],req:true,one:true}],coupon:{code:'SAVE10',off:10,all:false},
    fields:[{id:'note',t:'text',l:'توضیح',req:false}]};
  const store=makeStore({'nora-forms':JSON.stringify([form])}),p=await load('form.html',store,'?fid=f-money-settings');
  ok(p.errors.length===0&&p.window.eval('GUEST_ON&&GUEST_MAX===3')&&p.doc.querySelector('#couponRow').style.display!=='none',
    'ظرفیت کل، گروه مالی و کد تخفیف از تنظیمات خود فرم خوانده می‌شوند');
  p.click('#next');p.click('#next');
  ok(p.window.eval("cur==='u8'"),'فرمِ دارای گروه مالی به جمع‌بندی نمونه می‌رسد');
  const first=p.doc.querySelector('[data-fin="0"]');first.focus();
  first.dispatchEvent(new p.window.KeyboardEvent('keydown',{key:' ',bubbles:true,cancelable:true}));
  ok(p.doc.querySelector('[data-fin="0"]').getAttribute('aria-checked')==='true'
      &&p.doc.querySelector('[data-fin="1"]').getAttribute('aria-checked')==='false'
      &&p.doc.activeElement===p.doc.querySelector('[data-fin="0"]'),
    'گزینهٔ مالی با Space انتخاب می‌شود، گروه تک‌گزینه‌ای را رعایت می‌کند و تمرکز برمی‌گردد');
  p.click('#next');
  ok(p.window.eval("cur==='u8'&&selectedPaymentMethod==='' ")
      &&p.doc.querySelector('#paymentMethodList').getAttribute('aria-invalid')==='true',
    'پس از انتخاب مدل مالی هم روش پرداخت جداگانه و اجباری است');
  p.click('[data-method="card_transfer"]');p.click('#next');
  ok(p.window.eval("cur==='u9'&&selectedPaymentMethod==='card_transfer'")
      &&p.txt('#payAmount').includes('۷۲۲٬۵۰۰'),'کارت‌به‌کارت پس از انتخاب مدل، تمام مبلغ را یک‌جا نشان می‌دهد');
  p.click('#next');
  ok(p.window.eval("cur==='u11'")&&!p.doc.querySelector('#receiptPreviewStatus').hidden,
    'جزئیات کارت به پیش‌نمایش رسید می‌رسد؛ هنوز فایل یا پرداختی ارسال نمی‌شود');
  p.click('#next');
  ok(p.window.eval("cur==='u12'"),'ثبت پاسخ محلی پس از مرحلهٔ رسید انجام می‌شود؛ بقیهٔ گزینه‌های گروه اجباری نیستند');
  p.window.eval("show('u8')");p.set('#coupon','save10');p.click('#applyCoupon');
  ok(p.window.eval('calc().per===722500&&calc().dis===72250&&calc().sum===650250')
      &&p.txt('#couponNote').includes('کد تخفیف اعمال شد'),
    'کد تخفیف روی مبلغ انتخابی اعمال می‌شود');
  p.click('#editGuests');p.set('#fName','مهمان نمونهٔ یک');p.set('#fMobile','09121234567');p.click('#addFriend');
  ok(p.window.eval('S.guests.length===1&&calc().count===2&&calc().dis===72250'),
    'در حالت پیش‌فرض کوپن فقط روی مبلغ نفر اصلی حساب می‌شود، نه همراه');
  p.set('#fName','مهمان نمونهٔ دو');p.set('#fMobile','09121234568');p.click('#addFriend');
  ok(p.window.eval('S.guests.length===2&&calc().count===3&&GUEST_MAX===3')
      &&p.doc.querySelector('#editGuests').style.display==='none',
    'سقف سه نفر شامل خود پاسخ‌دهنده است و افزودن همراه سوم بسته می‌شود');
  p.window.eval('CFG.coupon.all=true;renderBill()');
  ok(p.window.eval('calc().dis===216750&&calc().count===3'),
    'تنظیم all تخفیف نمونه را برای هر سه نفر حساب می‌کند');
  p.click('#next');
  ok(p.window.eval("cur==='u9'&&document.getElementById('payAmount').textContent===rialTxt(calc().sum)"
      +"&&document.getElementById('paymentTransferLabel').textContent==='مبلغ کامل واریز'"
      +"&&document.getElementById('paymentTransferTotal').hidden===false")
      &&p.txt('#payCount').includes('۳ نفر'),'مبلغ کامل کارت‌به‌کارت پس از تخفیف و همراهان درست است و قسطی نشان داده نمی‌شود');
  p.click('#next');
  ok(p.window.eval("cur==='u11'")&&!p.doc.querySelector('#receiptPreviewStatus').hidden,
    'پس از تغییر همراهان، مسیر پرداخت همچنان پیش از رسید محلی می‌ماند');
  p.click('#next');
  const row=JSON.parse(store.getItem('nora-regs')||'[]').find(r=>r.form==='f-money-settings');
  ok(row&&row.count===3&&row.guests.length===2&&row.sampleAmount===p.window.eval('calc().sum')
      &&row.paymentStatus==='not-connected'&&!store.getItem('nora-receipts'),
    'جمع‌بندی فقط به‌عنوان مبلغ نمونه در پاسخ محلی می‌ماند و پرداخت یا رسیدی نمی‌سازد');
}

/* ── ۸الف) مقادیر ناسازگار تنظیمات با مرز امن نرمال می‌شوند ── */
{
  console.log('\n── مرزهای امن تنظیمات فرم ──');
  const form={id:'f-setting-bounds',name:'فرم مرز تنظیمات',need:'reg',slug:'setting-bounds',
    guestsOn:true,maxPer:'۲٫۵',cap:200001,wait:-3,fin:[
      {l:'',p:999,off:0},{l:'گزینهٔ بزرگ',p:'9999999999999999',off:150},
      {l:'گزینهٔ منفی',p:-50,off:-4}],
    groups:[{n:'گروه پاک‌سازی‌شده',of:[0,1,2],req:true,one:false}],coupon:{code:'CLAMP',off:170,all:false},
    fields:[{id:'q',t:'text',l:'پرسش',req:false}]};
  const p=await load('form.html',makeStore({'nora-forms':JSON.stringify([form])}),'?fid=f-setting-bounds');
  ok(p.errors.length===0&&p.window.eval('CFG.maxPer===1&&GUEST_ON===false&&CFG.cap===100000&&CFG.wait===0'),
    'تعداد اعشاری، ظرفیت بیش‌ازحد و صف منفی به مقدار صحیح و سقف امن تبدیل می‌شوند');
  ok(p.window.eval("CFG.fin.length===2&&CFG.fin[0].p===1000000000000&&CFG.fin[0].off===100&&CFG.fin[1].p===0&&CFG.fin[1].off===0")
      &&p.window.eval("CFG.groups[0].of.join(',')==='0,1'&&CFG.groups[0].req&&CFG.groups[0].one===false&&CFG.coupon.off===100"),
    'گزینه‌های مالی، گروه‌های ارجاع‌داده‌شده و درصد تخفیف با ترتیب درست و کران معتبر بازیابی می‌شوند');
}

/* ── ۸ب) اطلاعات همراهان از تنظیم سازنده تا پاسخ محلی ── */
{
  console.log('\n── تنظیمات همراهان در پیش‌نمایش پاسخ ──');
  const form={id:'f-buddy',name:'فرم همراه نمونه',model:'registration',need:'reg',guestsOn:true,maxPer:3,
    compFields:'name-mobile-nid',fin:[],fields:[{id:'buddy-answer',t:'text',l:'یادداشت',req:false}]};
  const store=makeStore({'nora-forms':JSON.stringify([form])}), p=await load('form.html',store,'?fid=f-buddy');
  p.click('#next'); p.set('#qa0','پاسخ محلی'); p.click('#next');
  ok(p.visible('.screen').join()==='u8'&&p.doc.querySelector('#feeOptionsCard').style.display==='none',
    'فرم رایگانِ دارای همراه به صفحهٔ همراهان می‌رود، بدون نمایش کارت مالی خالی');
  p.click('#editGuests');
  ok(p.doc.querySelector('#fNid').style.display!=='none'&&p.txt('#compFieldsNote').includes('هویت تأیید نمی‌شود')
      &&p.doc.querySelector('#fMobile').maxLength===20&&p.doc.querySelector('#fMobile').inputMode==='tel'
      &&p.doc.querySelector('#fName').maxLength===120,
    'ورودی همراه قالب شمارهٔ ایران، سقف طول نام و توضیح صریح دربارهٔ کد ملی را دارد');
  p.set('#fName','poiuytrewq');
  ok(p.txt('#friendNameQuality').includes('صفحه‌کلید'),
    'هشدار کیفیت برای نام همراه در پنل افزودن دوست هم کنار خود فیلد دیده می‌شود');
  p.set('#fName','مریم همراه');p.set('#fMobile','abc09123456789');p.click('#addFriend');
  ok(p.window.eval('S.guests.length===0'),'حروفِ چسبیده به شمارهٔ همراه با حذف ساده نادیده گرفته نمی‌شوند');
  p.set('#fMobile','+۹۸ ۹۱۲ ۳۴۵ ۶۷۸۹');p.set('#fNid','۰۰۱۲۳۴۵۶۷x');p.click('#addFriend');
  ok(p.window.eval('S.guests.length===0'),'کد ملی همراه هم باید دقیقاً ده رقم باشد و حروف از آن حذف نمی‌شوند');
  p.set('#fName','x'.repeat(121));p.set('#fNid','۰۰۱۲۳۴۵۶۷۸');p.click('#addFriend');
  ok(p.window.eval('S.guests.length===0'),'نام همراهِ بیش از ۱۲۰ نویسه در اعتبارسنجی رد می‌شود');
  const unsafeName='<img src=x onerror=alert(1)>';
  p.set('#fName',unsafeName);p.set('#fMobile','+۹۸ ۹۱۲ ۳۴۵ ۶۷۸۹');p.click('#addFriend');
  ok(p.window.eval("S.guests.length===1&&S.guests[0].mobile==='09123456789'&&S.guests[0].nid==='0012345678'")
      &&p.txt('#friendChips').includes(unsafeName)&&p.doc.querySelector('#friendChips img')===null,
    'شمارهٔ +۹۸ به قالب محلی تبدیل، کد ملی فارسی حفظ و نام همراه در چیپ امن escape می‌شود');
  p.click('#next');
  let regs=JSON.parse(store.getItem('nora-regs')||'[]'), reg=regs.find(x=>x.form==='f-buddy');
  ok(reg&&reg.guests?.[0]?.name===unsafeName&&reg.guests[0].mobile==='09123456789'&&reg.guests[0].nid==='0012345678',
    'اطلاعات همراهِ انتخاب‌شده در پاسخ محلی می‌ماند و نام/موبایل/کد ملی حذف نمی‌شوند');
  ok(reg&&reg.notificationStatus==='not-sent'&&reg.paymentStatus==='not-connected',
    'ذخیرهٔ اطلاعات همراه پیام یا پرداخت واقعی ایجاد نمی‌کند');
  const cap=await load('create.html',makeStore());
  cap.window.eval("S.guestsOn=false;S.maxPer=1;document.getElementById('maxPer').value='1';setSwitch('guestsOn',false)");
  cap.click('#guestsOn');
  ok(cap.window.eval('S.guestsOn&&S.maxPer===2')&&cap.doc.querySelector('#maxPer').value==='۲'
      &&cap.doc.querySelector('#guestsOn').getAttribute('aria-checked')==='true'
      &&cap.doc.querySelector('#guestsOn').classList.contains('on'),
    'بازکردن همراه، سقف کل افراد را به حداقل دو نفر می‌رساند');

  const noIdentityForm={id:'f-buddy-no-identity',name:'فرم بدون پرسش هویت همراه',model:'registration',need:'reg',guestsOn:true,maxPer:2,
    compFields:'name-mobile-answers',fin:[],fields:[{id:'note',t:'text',l:'یادداشت',req:false}]};
  const noIdentity=await load('form.html',makeStore({'nora-forms':JSON.stringify([noIdentityForm])}),'?fid=f-buddy-no-identity');
  noIdentity.click('#next');noIdentity.click('[data-companion-toggle="0"]');
  ok(noIdentity.window.eval('S.guests.length===0')&&!noIdentity.doc.querySelector('[data-companion-identity]')
      &&noIdentity.txt('#toast').includes('سؤال نام و شمارهٔ همراه'),
    'اگر سؤال نام یا شماره در فرم نیست، همراه با فیلد تکراری ساخته نمی‌شود');

  const feeForm={id:'f-buddy-fee',name:'فرم همراه با مبلغ نمونه',model:'registration',need:'reg',guestsOn:true,maxPer:3,
    compFields:'name-mobile-answers',fin:[{l:'کارگاه نمونه',p:250000,off:0,req:false}],
    fields:[
      {id:'name',t:'fullname',l:'نام و نام خانوادگی',req:false},
      {id:'mobile',t:'mobile',l:'شمارهٔ همراه',req:false},
      {id:'required-answer',t:'text',l:'پاسخ نمونه',req:false},
    ]};
  const feeStore=makeStore({'nora-forms':JSON.stringify([feeForm])}),feePage=await load('form.html',feeStore,'?fid=f-buddy-fee');
  feePage.click('#next');feePage.set('#qa0','لیلا');feePage.click('[data-companion-toggle="0"]');
  feePage.set('[data-companion-answer-card][data-guest-index="0"][data-question-index="0"] [data-companion-input]','مینا همراه');
  feePage.click('#next');feePage.set('#qa1','09121112222');feePage.click('[data-companion-toggle="1"]');
  feePage.set('[data-companion-answer-card][data-guest-index="0"][data-question-index="1"] [data-companion-input]','09121112223');
  feePage.click('#next');feePage.set('#qa2','پاسخ اصلی');feePage.click('[data-companion-toggle="2"]');
  feePage.set('[data-companion-answer-card][data-guest-index="0"][data-question-index="2"] [data-companion-input]','پاسخ مینا');
  feePage.click('#next');feePage.click('[data-fin="0"]');
  ok(feePage.window.eval("cur==='u8'&&calc().count===2&&calc().sum===500000")
      &&feePage.txt('#guestChips').includes('مینا همراه')&&!feePage.txt('#guestChips').includes('09121112222')
      &&feePage.txt('#guestCardTitle')==='همراهان'&&feePage.doc.querySelector('#countTxt').style.display==='none'
      &&feePage.doc.querySelector('#editGuests').style.display==='none',
    'در بخش هزینه فقط نام همراه دیده می‌شود و مبلغ نمونه با تعداد افراد محاسبه می‌شود');

  const sameForm={id:'f-buddy-same',name:'فرم همراه با پاسخ مشترک',model:'registration',need:'reg',guestsOn:true,maxPer:2,
    compFields:'same-as-primary',fin:[],fields:[{id:'same-answer',t:'text',l:'پاسخ اصلی',req:false}]};
  const sameStore=makeStore({'nora-forms':JSON.stringify([sameForm])}), same=await load('form.html',sameStore,'?fid=f-buddy-same');
  same.click('#next'); same.set('#qa0','پاسخ مشترک محلی'); same.click('#next'); same.click('#editGuests');
  ok(same.doc.querySelector('#sameOpt').style.display!=='none','گزینهٔ «همان فیلدهای نفر اصلی» در همراه‌ساز نمایش داده شد');
  same.set('#fName','علی همراه'); same.set('#fMobile','09112223344'); same.click('#addFriend'); same.click('#next');
  regs=JSON.parse(sameStore.getItem('nora-regs')||'[]'); reg=regs.find(x=>x.form==='f-buddy-same');
  ok(reg&&reg.guests?.[0]?.sameAsPrimary===true&&reg.guests[0].answers?.some(a=>a.l==='پاسخ اصلی'&&a.v==='پاسخ مشترک محلی'),
    'پاسخ اصلی فقط در حالت انتخاب‌شده به دادهٔ محلی همراه کپی شد');
}

/* ── ۹) مطلب: رسانهٔ پذیرفته‌شده، embed و CTA بیرونی ── */
{
  console.log('\n── مطلب و CTA بیرونی ──');
  const post={id:'smoke-post',t:'مطلب نمونه',cat:'گزارش',tags:['نمونه'],lead:'مطلب محلی',author:'تحریریه',at:Date.now(),
    cover:{g:'linear-gradient(135deg,#0A56B8,#0B2447)'},pub:1,pend:0,views:0,
    blocks:[
      {ty:'p',x:'محتوای محلی'}, {ty:'h',x:'بخش'},
      {ty:'vid',src:'https://www.youtube.com/watch?v=dQw4w9WgXcQ'},
      {ty:'vid',src:'https://example.org/movie.mp4'},
      {ty:'vid',src:'https://127.0.0.1/private.mp4'},
      {ty:'aud',src:'https://example.org/audio.mp3'},
      {ty:'img',src:'https://example.org/image.jpg'},
      {ty:'img',src:'https://127.0.0.1/private.jpg'},
      {ty:'file',src:'https://example.org/guide.pdf',t:'فایل بیرونی'},
      {ty:'bm',href:'https://example.org/learn',t:'پیوند بیرونی'},
      {ty:'btn',href:'https://example.org/register',x:'ثبت‌نام بیرونی'},
      {ty:'btn',href:'event.html?id=ev1',x:'رویداد محلی'}]};
  const store=makeStore({'nora-posts':JSON.stringify([post])}), p=await load('post.html',store,'?id=smoke-post');
  ok(p.errors.length===0,'خوانندهٔ مطلب بی‌خطا بار شد');
  ok(p.txt('body').includes('پیش‌نمایش محلی'),'نشان محلی روی مطلب دیده می‌شود');
  ok(p.all('.pb-vid iframe').length===0
      &&p.doc.querySelector('.pb-vid video[src="https://example.org/movie.mp4"]')!==null
      &&p.doc.querySelector('.pb-aud audio[src="https://example.org/audio.mp3"]')!==null,
    'YouTube/آپارات embed نمی‌شود؛ رسانهٔ HTTPS پذیرفته‌شده با پخش‌گر داخلی می‌ماند');
  ok(p.all('.pb-disabled').length>=5,'embed و رسانهٔ نشانی خصوصی، فایل و کارت پیوند بیرونی غیرفعال شدند');
  ok(p.doc.querySelector('.pb-btn button[disabled]')!==null,'CTA بیرونی به دکمهٔ غیرفعال تبدیل شد');
  ok(p.doc.querySelector('.pb-btn a[href="event.html?id=ev1"]')!==null,'پیوند داخلی به صفحهٔ رویداد محلی می‌ماند');
  ok(/غیرفعال/.test(p.txt('#pbShare'))&&p.doc.querySelector('#pbCopy')?.disabled,'همرسانی و کپی پیوند عمومی غیرفعال‌اند');
  ok(externalAnchors(p).length===0,'خوانندهٔ مطلب هیچ پیوند http(s) عملیاتی ندارد');
  const remoteMedia=p.all('img[src],video[src],audio[src],iframe[src]').filter(node=>{
    const src=node.getAttribute('src')||''; return /^https?:/i.test(src)||src.startsWith('//');
  });
  ok(remoteMedia.every(node=>p.window.NORA_UI.safeHttpsMediaUrl(node.getAttribute('src'))===node.getAttribute('src'))
      &&p.all('.pb-vid iframe').length===0,
    'رسانهٔ HTTPS فقط با اعتبارسنجی نشانی عمومی رندر می‌شود و embed سرویس خارجی ساخته نمی‌شود');
  ok(p.network.length===1&&p.network[0]==='/api/public/site-content'
      &&p.network.every(path=>String(path).startsWith('/api/')),
    'مطلب فقط snapshot عمومی هم‌مبدأ را می‌گیرد و درخواست دامنهٔ بیرونی ندارد');
}

/* ── ۱۰) صفحه‌های عمومی و مدیریتی: نمایه‌پذیری و فقط API هم‌مبدأ ── */
{
  console.log('\n── metadata، پنل و انتشار عمومی ──');
  const files=['account.html','events.html','event.html','person.html','partner.html','form.html','login.html','support.html','post.html','admin.html'];
  const publicFiles=new Set(['events.html']);
  const serverSeoFiles=new Set(['event.html','person.html','partner.html']);
  let checked=0;
  for(const file of files){
    const p=await load(file,makeStore(),file==='event.html'?'?id=e1':file==='person.html'?'?id=p1':file==='partner.html'?'?id=o1':'');
    const robots=p.doc.querySelector('meta[name="robots"]')?.content||'';
    const publicPage=publicFiles.has(file),serverSeoPage=serverSeoFiles.has(file);
    const correctRobots=publicPage?/index/.test(robots)&&!/noindex/.test(robots):/noindex/.test(robots);
    if(p.errors.length===0&&correctRobots) checked++;
    ok(p.errors.length===0,file+' بی‌خطا بار شد');
    ok(correctRobots,publicPage?file+' برای محتوای منتشرشده قابل نمایه‌سازی است'
      :serverSeoPage?file+' در پوستهٔ ثابت noindex می‌ماند تا backend فقط محتوای منتشرشده را نمایه‌پذیر کند'
        :file+' از نمایه‌سازی عمومی کنار گذاشته شده');
    ok(externalAnchors(p).length===0,file+' در حالت بدون محتوای منتشرشده پیوند بیرونی ندارد');
    ok(p.network.every(path=>String(path).startsWith('/api/')),file+' فقط API هم‌مبدأ صدا می‌زند');
  }
  ok(checked===files.length,'پوسته‌های ثابت و صفحه‌های خصوصی noindex می‌مانند؛ backend محتوای منتشرشده را index می‌کند و همه بی‌خطا بار می‌شوند');
  const bareForm=await load('form.html',makeStore(),'','',{fixtureMode:false});
  ok(bareForm.visible('.screen').join()==='uUnavailable'&&bareForm.txt('#unavailableTitle')==='فرم پیدا نشد'
      &&bareForm.doc.querySelector('#localPreviewNotice').style.display==='none'
      &&!bareForm.doc.querySelector('#u1').classList.contains('on')
      &&!bareForm.doc.body.classList.contains('form-booting'),
    'فرم بی‌پیوند در تجربهٔ تولیدی، به‌جای داده و محتوای نمونه، وضعیت خالی نشان می‌دهد');
  bareForm.dom.window.close();
  const formMarkup=fs.readFileSync(DIR+'form.html','utf8'),staticForm=new JSDOM(formMarkup,{url:'https://nora.test/form.html'});
  ok(staticForm.window.document.body.classList.contains('form-booting')
      &&staticForm.window.getComputedStyle(staticForm.window.document.querySelector('.wrap')).visibility==='hidden'
      &&!!staticForm.window.document.querySelector('noscript [role="alert"]'),
    'پیش از راه‌اندازی JavaScript، رابط و fixtureهای فرم پنهان‌اند و پیام امنِ بی‌JavaScript دیده می‌شود');
  staticForm.window.close();
  const adminJs=fs.readFileSync(DIR+'admin.js','utf8');
  ok(!/https?:\/\/ble\.ir\//i.test(adminJs)&&!adminJs.includes('baleStart'),
    'کد شروع یا URL واقعی بله در admin.js وجود ندارد');
  ok(adminJs.includes('ربات پیام‌رسان · وصل‌نیست')&&adminJs.includes('ارتباط بیرونی غیرفعال است'),
    'راهنمای بله در پنل فقط وضعیت وصل‌نبودن را نشان می‌دهد');
}

/* ── ۱۱) brSave فقط پس از تأیید صریح مالک و آن هم محلی/ارسال‌نشده ── */
{
  console.log('\n── شرط تأیید مالک برای brSave ──');
  const store=makeStore(), p=await load('home.html',store), U=p.window.NORA_UI;
  const rec={id:'smoke-broadcast',ev:'sample',title:'اعلان نمونه'};
  const pending=U.ownerApprovalAdd({type:'notification',status:'pending',brRecord:rec});
  ok(U.brSave(rec,pending.id)===null&&!store.getItem(U.BR_KEY),'brSave پیش از تأیید مالک رکورد نمی‌سازد');
  U.ownerApprovalPatch(pending.id,{status:'approved',notificationStatus:'approved',approvedBy:'مالک نمونه',
    approvedById:'p1',approvedAt:Date.now(),brRecord:rec});
  const saved=U.brSave(rec,pending.id);
  ok(!!saved&&saved.ownerApprovalId===pending.id&&saved.sent===false,'پس از تأیید مالک فقط رکورد محلیِ ارسال‌نشده ساخته می‌شود');
  ok(p.network.every(path=>String(path).startsWith('/api/')),'ساخت رکورد محلی فقط درخواست API هم‌مبدأ صفحه را دارد و پیام بیرونی نمی‌فرستد');
}

/* ── ۱۲) روش‌های per-form، صورتحساب server-side و صفحهٔ پایان ── */
{
  console.log('\n── پرداخت سروریِ per-form و صفحهٔ پایان ──');
  const baleId='server-bale-wallet-preview-smoke',baleForm=makePublicFormData(baleId,false,['bale_wallet']);
  baleForm.fin=[{l:'ورودی نمونه',p:650000,off:0,req:true,d:''}];
  baleForm.settings.fin=baleForm.fin;
  const baleApi=makePublicApiMock({id:baleId}),balePage=await loadPublicForm(baleForm,baleApi.fetch);
  balePage.click('#next');await wait(20);balePage.input('#qa0','نام آزمون پرداخت');await wait(720);balePage.click('#next');await wait(80);
  ok(balePage.errors.length===0&&balePage.all('#u8 [data-method]:not([hidden])').length===1
      &&balePage.doc.querySelector('[data-method="bale_wallet"]').hidden===false
      &&balePage.doc.querySelector('[data-method="card_transfer"]').hidden
      &&balePage.window.eval("CFG.enabledPaymentMethods.length===1&&CFG.enabledPaymentMethods[0]==='bale_wallet'"),
    'فرم عمومی فقط کیف پول بله را وقتی سازنده همان روش را فعال کرده نمایش می‌دهد');
  balePage.click('[data-fin="0"]');balePage.click('[data-method="bale_wallet"]');balePage.click('#next');
  ok(balePage.visible('.screen').join()==='u9'&&balePage.txt('#paymentTitle')==='کیف پول بله',
    'انتخاب کیف پول بله به گام اختصاصی همان روش می‌رود');
  balePage.click('#next');await wait(100);
  const baleIntentCall=baleApi.calls.find(call=>call.method==='POST'&&call.path.endsWith('/payment-intents'));
  ok(baleIntentCall?.body?.method==='bale_wallet'&&baleIntentCall.body.selection.items[0]===0
      &&balePage.doc.querySelector('#balePaymentInvoiceLink').hidden===false
      &&balePage.doc.querySelector('#balePaymentInvoiceLink').getAttribute('href')==='https://ble.ir/payment-invoice-smoke'
      &&balePage.window.eval("S.paymentIntent.status==='pending'&&!S.submitted")
      &&!baleApi.calls.some(call=>call.method==='POST'&&call.path.endsWith('/responses'))
      &&!balePage.store.getItem('nora-regs')&&balePage.doc.querySelector('#serverTicketPreview').hidden,
    'backend فقط صورتحساب pending می‌سازد؛ پاسخ ثبت یا پرداخت موفق در مرورگر شبیه‌سازی نمی‌شود');

  const apiMock=makeFormsApiMock({id:'server-form-method-builder'});
  const builderStore=makeStore({
    'nora-admin-session':JSON.stringify({u:'owner',role:'admin',personKey:'p1',at:Date.now()}),
    'nora-finance':JSON.stringify({gates:[{k:'card',n:'کارت‌به‌کارت',on:1},{k:'bale',n:'کیف پول بله',on:1}],
      cards:[{id:'builder-card',bank:'بانک نمونه',no:'4111111111111111',name:'حساب سازنده',on:true,cap:50,dailyMax:10000000,used:0,usedAmount:0}]})
  });
  const builder=await load('create.html',builderStore,'',apiMock.fetch);
  builder.click('[data-go="s3"]');await wait(80);
  ok(builder.doc.querySelector('#formPaymentMethodsCard').hidden===false
      &&builder.doc.querySelector('#enableBaleWallet').getAttribute('aria-disabled')==='true'
      &&builder.txt('#createPaymentStatus').includes('backend امن آماده نیست'),
    'سازنده پیش از پیکربندی امن backend، کیف پول بله را غیرفعال نگه می‌دارد');
  builder.click('#enableBaleWallet');builder.click('#receiptReviewRequired');
  ok(builder.window.eval("S.enabledPaymentMethods.length===1&&S.enabledPaymentMethods[0]==='card_transfer'&&S.receiptReviewRequired===true")
      &&builder.doc.querySelector('#enableBaleWallet').getAttribute('aria-checked')==='false'
      &&builder.doc.querySelector('#receiptReviewRequired').getAttribute('aria-checked')==='true',
    'سازنده فقط کارت‌به‌کارتِ دارای کارت مقصد معتبر را برای این فرم انتخاب می‌کند؛ کیف پول غیرفعال می‌ماند');
  builder.window.eval("S.name='فرم پرداخت سروری';S.slug='form-payment-server';S.fin=[{l:'ورودی نمونه',p:650000,off:0,req:true,d:'',g:null}];S.fields=[freshField('fullname',1)];S.fields[0].l='نام و نام خانوادگی';S.uid=2;renderCanvas();renderReview()");
  builder.click('[data-go="s4"]');builder.click('#publish');await wait(120);
  const createCall=apiMock.calls.find(call=>call.path==='/api/forms'&&call.method==='POST');
  const createPayload=createCall&&JSON.parse(createCall.body||'{}');
  ok(builder.errors.length===0&&createPayload&&createPayload.settings
      &&JSON.stringify(createPayload.settings.enabledPaymentMethods)==='["card_transfer"]'
      &&createPayload.settings.receiptReviewRequired===true
      &&createPayload.settings.paymentCard?.number==='4111111111111111'
      &&createPayload.settings.fin?.[0]?.p===650000
      &&!createPayload.settings.noraPayEnabled
      &&!apiMock.calls.some(call=>call.path.includes('/payment-intents')),
    'سازنده فقط روش‌های منتخب و کارت/قیمت لازم را به API می‌فرستد؛ secret یا تراکنش مرورگری ساخته نمی‌شود');

  const finalId='standalone-final-review-smoke',validDelivery='https://ble.ir/nora_test_bot?start=ft_'+'A'.repeat(48);
  const handoff={formId:finalId,createdAt:Date.now(),form:{id:finalId,name:'فرم رویداد نمونه',model:'registration',need:'reg',
      receiptReviewRequired:true,endText:'از همراهی شما سپاسگزاریم.',links:[
        {t:'صفحهٔ سازنده',u:'home.html'},{t:'شبکهٔ اجتماعی',u:'https://instagram.com/nora.example',social:'instagram'},
        {t:'پیوند ناامن',u:'javascript:alert(1)'}]},
    response:{status:'accepted',paymentMethod:'card_transfer',paymentStatus:'paid_manual',receiptUploaded:true,
      trackingCode:'F1234567890',ticketType:{id:'general',name:'عمومی'},ticketDeliveryUrl:validDelivery}};
  const sessionStore=makeStore({['nora-final-page-handoff:'+finalId]:JSON.stringify(handoff)});
  const finalPage=await loadHtml('final-page-review.html',fs.readFileSync(DIR+'final-page-review.html','utf8'),makeStore(),
    '?fid='+finalId,null,sessionStore);
  ok(finalPage.errors.length===0&&finalPage.txt('#endTitle')==='تکمیل شد!'
      &&finalPage.doc.querySelector('#ticketImageFrame').hidden===false
      &&finalPage.doc.querySelector('#ticketImageFrame img').getAttribute('src')==='/api/public/forms/'+finalId+'/ticket-image'
      &&finalPage.doc.querySelector('#ticketDelivery').hidden===false
      &&finalPage.doc.querySelector('#ticketDelivery').getAttribute('href')===validDelivery
      &&finalPage.doc.querySelectorAll('#ticketDelivery').length===1,
    'صفحهٔ پایان مستقل عنوان درست، تصویر endpoint سرور و فقط یک CTA دانلود بلیت در بله دارد');
  ok(finalPage.doc.querySelectorAll('#endLinksList a.final-link').length===2
      &&finalPage.txt('#endLinks').includes('صفحهٔ سازنده')
      &&finalPage.doc.querySelector('#endLinksList a[href*='+'\"home.html\"'+']')
      &&finalPage.txt('#endText')==='از همراهی شما سپاسگزاریم.'
      &&!/(رسید|مبلغ|پرداخت|صف انتظار|ظرفیت|تأیید دستی)/.test(finalPage.txt('main'))
      &&!finalPage.doc.querySelector('#ticketImageFrame img').getAttribute('src').includes('ticket-fars-design.png'),
    'پیوندهای سازنده دکمه‌اند؛ رسید، مالی، صف و بلیت تصویری ثابت در پایان نمی‌آیند');

  const pendingId='standalone-pending-review-smoke',pendingHandoff={...handoff,formId:pendingId,
    form:{...handoff.form,id:pendingId},response:{...handoff.response,paymentStatus:'receipt_submitted',ticketDeliveryUrl:''}};
  const pendingSession=makeStore({['nora-final-page-handoff:'+pendingId]:JSON.stringify(pendingHandoff)});
  const pendingPage=await loadHtml('final-page-review.html',fs.readFileSync(DIR+'final-page-review.html','utf8'),makeStore(),
    '?fid='+pendingId,null,pendingSession);
  ok(pendingPage.txt('#endTitle')==='تکمیل شد!'
      &&pendingPage.doc.querySelector('#ticketImageFrame').hidden
      &&pendingPage.doc.querySelector('#ticketDelivery').hidden
      &&pendingPage.txt('#statusMessage').includes('هنوز امکان نمایش بلیت وجود ندارد'),
    'حتی دسترسی مستقیم به صفحهٔ پایان پیش از paid_manual تصویر یا لینک بلیت نشان نمی‌دهد');
}
console.log(`\nsmoke: ${checks-fails} قبول، ${fails} خطا`);
process.exit(fails?1:0);
