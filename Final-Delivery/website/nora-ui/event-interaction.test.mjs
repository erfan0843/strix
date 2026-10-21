/* فاز ۸ — بخش‌های تعاملی صفحهٔ رویداد (منابع، پرسش‌وپاسخ، دیدگاه) در jsdom.
   اجرا: node event-interaction.test.mjs
   فقط نمایش حالت‌های سرور سنجیده می‌شود؛ تصمیم دسترسی در سرور است و این‌جا فقط باید صادقانه بازتاب یابد. */
import {fileURLToPath,pathToFileURL} from 'node:url';
import jsdom from 'jsdom';
import fs from 'node:fs';
const {JSDOM}=jsdom;
const DIR=fileURLToPath(new URL('./',import.meta.url));
let checks=0,fails=0;
const ok=(condition,message)=>{checks++;if(!condition){fails++;console.log('   ✗ '+message)}else console.log('   ✓ '+message)};
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const EVENT_ID='ev-qa-phase8';
const content={events:[{id:EVENT_ID,t:'کارگاه آزمایشی فاز ۸',kind:'کارگاه',privacy:'public',when:'۱۲ آبان',time:'۱۰ تا ۱۳',place:'سالن اصلی',
  d:'شرح رویداد آزمایشی.',parts:[{title:'جلسهٔ اول',date:'۱۲ آبان'}],forms:[{id:'form-qa-1',need:'reg',n:'فرم'}],
  registration:{state:'open',reason:'',lifecycle:'scheduled',opensAt:'',closesAt:'',startsAt:'',endsAt:'',countdownTo:'',startsIn:''},
  lifecycle:'scheduled',regMode:'auto',qaClosed:false}],people:[],partners:[],posts:[],banners:[],library:[],cooperation:[],banner_settings:{}};
const baseInteraction=()=>({source:'shared_server_database',server_time:new Date().toISOString(),
  event:{id:EVENT_ID,title:'کارگاه آزمایشی فاز ۸',published:true,lifecycle:'scheduled',qa_open:true,qa_closed_reason:''},
  viewer:{signed_in:false,staff:false,participation:{registered:false,attended:false,pending:false}},
  resources:[
    {id:'11111111-1111-4111-8111-111111111111',kind:'file',title:'جزوهٔ جلسه',description:'اسلایدها',access:'registered',status:'published',publish_at:'2026-10-20T06:30:00Z',published:true,publisher:'تیم آموزش',file_name:'jozve.pdf',content_type:'application/pdf',size:204800,allowed:false,reason:'login_required',updated_at:''},
    {id:'22222222-2222-4222-8222-222222222222',kind:'link',title:'پیوند جلسهٔ برخط',description:'',access:'public',status:'published',publish_at:'',published:true,publisher:'',file_name:'',content_type:'',size:0,allowed:true,reason:'public',link_url:'https://example.org/live',updated_at:''}
  ],
  questions:{items:[
    {id:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',event_id:EVENT_ID,author:'مینا ر.',mine:false,body:'ساعت شروع دقیقاً چند است؟',status:'published',answered:true,answer:'ساعت ده صبح.',answer_official:true,answer_label:'برگزارکننده',answered_at:'2026-10-20T07:00:00Z',created_at:'2026-10-19T07:00:00Z',reported:false}
  ],total:1,mine_pending:0},
  reviews:{eligible:false,items:[
    {id:'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',event_id:EVENT_ID,author:'امید ن.',mine:false,verified_attendee:true,body:'کارگاه بسیار مفیدی بود.',status:'published',edited:false,created_at:'2026-10-18T07:00:00Z',updated_at:'',reported:false}
  ],total:1,mine:null}});

async function load(interaction,{cookie='',onFetch=null}={}){
  const errors=[],calls=[];
  const dom=await JSDOM.fromFile(DIR+'event.html',{url:pathToFileURL(DIR+'event.html').href+'?id='+EVENT_ID,runScripts:'dangerously',pretendToBeVisual:true,
    resources:{interceptors:[jsdom.requestInterceptor(async request=>new URL(request.url).protocol==='https:'?new Response('',{status:403}):undefined)]},
    beforeParse(w){
      w.scrollTo=()=>{};if(w.Element&&!w.Element.prototype.scrollIntoView)w.Element.prototype.scrollIntoView=()=>{};
      if(!w.matchMedia)w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      w.__NORA_TEST_FIXTURE_MODE__=false;
      w.confirm=()=>true;w.prompt=()=>'تبلیغاتی';
      if(cookie)Object.defineProperty(w.document,'cookie',{configurable:true,get:()=>cookie,set(){}});
      w.fetch=async(path,init={})=>{
        const url=String(path||'');calls.push({url,init});
        if(onFetch){const custom=await onFetch(url,init);if(custom)return custom;}
        if(url==='/api/public/site-content')return{ok:true,status:200,json:async()=>({content,server_time:new Date().toISOString()})};
        if(url==='/api/public/events/'+EVENT_ID+'/interaction'){
          if(interaction==='fail')return{ok:false,status:500,json:async()=>({detail:'boom'})};
          if(interaction==='missing')return{ok:false,status:404,json:async()=>({detail:'event_not_found'})};
          return{ok:true,status:200,json:async()=>JSON.parse(JSON.stringify(interaction))};
        }
        return{ok:false,status:404,json:async()=>({})};
      };
      w.addEventListener('error',e=>errors.push('error: '+(e.message||'')));
      w.console.error=(...args)=>errors.push('console.error: '+args.join(' '));
      w.onerror=message=>errors.push('onerror: '+message);
    }});
  const {window}=dom;
  if(window.document.readyState!=='complete')await new Promise(resolve=>{const t=setTimeout(resolve,5000);window.addEventListener('load',()=>{clearTimeout(t);resolve()},{once:true})});
  await wait(120);
  const doc=window.document;
  return{dom,window,doc,errors,calls,txt:s=>{const el=doc.querySelector(s);return el?el.textContent.replace(/\s+/g,' ').trim():''}};
}

console.log('\n— مهمان: ترتیب بخش‌ها، وضعیت منابع و نبود فرم —');
{
  const p=await load(baseInteraction());
  ok(p.errors.length===0,'صفحه بدون خطای JavaScript بار شد'+(p.errors.length?': '+p.errors[0]:''));
  const sections=[...p.doc.querySelectorAll('.event-detail > section, .event-detail > div[data-event-interaction] > section')].map(s=>s.id||s.getAttribute('aria-labelledby'));
  const idx=name=>sections.findIndex(s=>String(s).includes(name));
  ok(idx('event-info')<idx('event-schedule')&&idx('event-schedule')<idx('resources')&&idx('resources')<idx('qa')&&idx('qa')<idx('reviews'),
    'ترتیب: اطلاعات → زمان‌بندی → منابع → پرسش‌وپاسخ → دیدگاه‌ها ('+sections.join(' , ')+')');
  const file=p.doc.querySelector('[data-resource="11111111-1111-4111-8111-111111111111"]');
  ok(file&&!file.querySelector('a[download]')&&file.textContent.includes('برای دریافت وارد حساب شوید')
      &&file.querySelector('a.btn')?.getAttribute('href')==='login.html?mode=server&next='+encodeURIComponent('event.html?id='+EVENT_ID+'#resources'),
    'منبع ویژهٔ ثبت‌نام‌شدگان برای مهمان: بدون پیوند دانلود، با دعوت به ورود و بازگشت به همین بخش');
  ok(file.textContent.includes('PDF')&&file.textContent.includes('کیلوبایت')&&file.textContent.includes('ویژهٔ ثبت‌نام‌شدگان')&&file.textContent.includes('ناشر: تیم آموزش'),
    'نوع، اندازه، سطح دسترسی و ناشر منبع نمایش داده می‌شود');
  const link=p.doc.querySelector('[data-resource="22222222-2222-4222-8222-222222222222"] a.btn');
  /* در پیش‌نمایش file: نگهبان پیوند بیرونیِ ui.js (رفتار موجود) پیوند را بی‌عمل می‌کند؛ روی سرور HTTPS همین پیوند با rel امن زنده می‌ماند. */
  ok(link&&link.textContent.includes('بازکردن پیوند')&&link.getAttribute('rel')==='noopener noreferrer'&&link.classList.contains('local-disabled-link'),
    'پیوند عمومی با rel امن ساخته می‌شود و نگهبان پیوند بیرونی موجود روی آن اعمال می‌شود');
  ok(!p.doc.querySelector('form[data-ei-form="question"]')&&p.doc.querySelector('#qa .ei-login a')?.getAttribute('href')==='login.html?mode=server&next='+encodeURIComponent('event.html?id='+EVENT_ID+'#qa'),
    'مهمان فرم پرسش نمی‌بیند؛ فقط دعوت به ورود با بازگشت به #qa');
  ok(p.txt('#qa').includes('ساعت ده صبح.')&&p.txt('#qa').includes('پاسخ رسمی')&&!p.doc.querySelector('[data-ei-report]'),
    'پرسش منتشرشده با پاسخ رسمی دیده می‌شود و مهمان دکمهٔ گزارش ندارد');
  ok(p.txt('#reviews').includes('شرکت‌کنندهٔ تأییدشده')&&p.txt('#reviews').includes('کارگاه بسیار مفیدی بود.')&&!p.doc.querySelector('form[data-ei-form="review"]')
      &&!/★|امتیاز/.test(p.txt('#reviews')),
    'دیدگاه منتشرشده با نشان سروری دیده می‌شود؛ بدون فرم برای مهمان و بدون امتیاز ستاره‌ای');
  ok(p.doc.querySelector('.event-register')&&p.doc.querySelector('#reg'),'ستون ثبت‌نام و دکمهٔ فرم دست‌نخورده‌اند');
  p.dom.window.close();
}

console.log('\n— کاربر واردشده: پرسش، خطاهای سرور، گزارش —');
{
  const data=baseInteraction();
  data.viewer={signed_in:true,staff:false,participation:{registered:true,attended:false,pending:false}};
  data.resources[0].allowed=true;data.resources[0].reason='registered';
  data.questions.items.unshift({id:'cccccccc-cccc-4ccc-8ccc-cccccccccccc',event_id:EVENT_ID,author:'شما',mine:true,body:'پارکینگ هست؟',status:'pending',answered:false,answer:'',answer_official:false,answer_label:'',answered_at:'',created_at:'2026-10-20T08:00:00Z',reported:false});
  const posted=[];
  const p=await load(data,{cookie:'nora_account_csrf=csrf-token-123',onFetch:async(url,init)=>{
    if(url==='/api/account/events/'+EVENT_ID+'/questions'&&init.method==='POST'){
      posted.push(init);
      const body=JSON.parse(init.body||'{}');
      if(body.body==='ساعت شروع دقیقاً چند است؟')return{ok:false,status:409,json:async()=>({detail:{code:'duplicate_question'}})};
      return{ok:true,status:201,json:async()=>({id:'new',status:'pending'})};
    }
    if(url.endsWith('/report')&&init.method==='POST')return{ok:true,status:201,json:async()=>({reported:true})};
    return null;
  }});
  ok(p.errors.length===0,'بدون خطای JavaScript');
  const download=p.doc.querySelector('[data-resource="11111111-1111-4111-8111-111111111111"] a[download]');
  ok(download&&download.getAttribute('href')==='/api/public/events/'+EVENT_ID+'/resources/11111111-1111-4111-8111-111111111111/download',
    'کاربر مجاز پیوند دانلود را فقط به نقطهٔ مجوزدار سرور می‌گیرد');
  const mine=p.doc.querySelector('[data-question="cccccccc-cccc-4ccc-8ccc-cccccccccccc"]');
  ok(mine&&mine.textContent.includes('در انتظار بررسی')&&mine.textContent.includes('هنوز پاسخ داده نشده')&&!mine.querySelector('[data-ei-report]'),
    'پرسش خود کاربر با وضعیت «در انتظار بررسی» و بدون دکمهٔ گزارش');
  const form=p.doc.querySelector('form[data-ei-form="question"]');
  ok(!!form,'کاربر واردشده فرم پرسش دارد');
  p.doc.querySelector('#eiQuestionBody').value='ساعت شروع دقیقاً چند است؟';
  form.dispatchEvent(new p.window.Event('submit',{bubbles:true,cancelable:true}));
  await wait(80);
  ok(posted.length===1&&posted[0].headers['X-CSRF-Token']==='csrf-token-123'&&posted[0].credentials==='same-origin'
      &&JSON.parse(posted[0].body).body==='ساعت شروع دقیقاً چند است؟'&&Object.keys(JSON.parse(posted[0].body)).join()==='body',
    'ارسال پرسش: فقط متن، با CSRF نشست و بدون هیچ شناسهٔ کاربر از سمت مرورگر');
  ok(p.txt('#qa').includes('همین پرسش را پیش‌تر ثبت کرده‌اید'),'خطای ۴۰۹ تکراری با پیام انسانی نمایش داده می‌شود');
  const form2=p.doc.querySelector('form[data-ei-form="question"]');
  p.doc.querySelector('#eiQuestionBody').value='آیا پذیرایی دارد؟';
  form2.dispatchEvent(new p.window.Event('submit',{bubbles:true,cancelable:true}));
  await wait(120);
  ok(posted.length===2&&p.txt('#qa').includes('پرسش شما ثبت شد'),'ارسال موفق پیام تأیید می‌دهد و فهرست را دوباره از سرور می‌خواند');
  const report=p.doc.querySelector('[data-ei-report="question"][data-id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"]');
  ok(!!report,'پرسش دیگران دکمهٔ گزارش دارد');
  report.dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  await wait(80);
  ok(p.calls.some(c=>c.url==='/api/account/events/'+EVENT_ID+'/questions/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/report'&&c.init.method==='POST'&&JSON.parse(c.init.body).reason==='تبلیغاتی'),
    'گزارش به نقطهٔ همان رویداد و همان پرسش ارسال می‌شود');
  ok(p.txt('#reviews').includes('پس از تأیید حضور در رویداد می‌توانید دیدگاه بنویسید')&&!p.doc.querySelector('form[data-ei-form="review"]'),
    'ثبت‌نام‌شدهٔ بدون حضور: فرم دیدگاه ندارد و دلیل صادقانه می‌بیند');
  p.dom.window.close();
}

console.log('\n— شرکت‌کنندهٔ تأییدشده: دیدگاه، ویرایش، پس‌گرفتن؛ Q&A بسته —');
{
  const data=baseInteraction();
  data.viewer={signed_in:true,staff:false,participation:{registered:true,attended:true,pending:false}};
  data.reviews.eligible=true;
  data.event.qa_open=false;data.event.qa_closed_reason='closed';
  const sent=[];
  let mine=null;
  const p=await load(data,{cookie:'nora_account_csrf=t',onFetch:async(url,init)=>{
    if(url==='/api/account/events/'+EVENT_ID+'/reviews'&&init.method==='POST'){sent.push(init);mine={id:'dddddddd-dddd-4ddd-8ddd-dddddddddddd',author:'شما',mine:true,verified_attendee:true,body:JSON.parse(init.body).body,status:'pending',edited:false,created_at:'',updated_at:'',reported:false};return{ok:true,status:201,json:async()=>mine}}
    if(url==='/api/account/events/'+EVENT_ID+'/reviews/dddddddd-dddd-4ddd-8ddd-dddddddddddd'&&init.method==='PUT'){sent.push(init);mine={...mine,body:JSON.parse(init.body).body,edited:true,status:'pending'};return{ok:true,status:200,json:async()=>mine}}
    if(url.endsWith('/withdraw')){sent.push(init);mine={...mine,status:'withdrawn'};return{ok:true,status:200,json:async()=>mine}}
    if(url==='/api/public/events/'+EVENT_ID+'/interaction'&&mine){const next=JSON.parse(JSON.stringify(data));next.reviews.mine=mine;next.reviews.items=[mine,...data.reviews.items];return{ok:true,status:200,json:async()=>next}}
    return null;
  }});
  ok(p.errors.length===0,'بدون خطای JavaScript');
  ok(p.txt('#qa').includes('بسته')&&p.txt('#qa').includes('پرسش‌وپاسخ این رویداد بسته شده است')&&!p.doc.querySelector('form[data-ei-form="question"]')&&p.txt('#qa').includes('ساعت ده صبح.'),
    'Q&A بسته: بدون فرم، با توضیح، پرسش‌های پاسخ‌داده‌شده همچنان دیده می‌شوند');
  const form=p.doc.querySelector('form[data-ei-form="review"]');
  ok(!!form&&!form.querySelector('input[type="number"],input[type="range"],[data-star]'),'شرکت‌کنندهٔ تأییدشده فرم دیدگاه متنی دارد، بدون امتیاز');
  p.doc.querySelector('#eiReviewBody').value='کوتاه';
  form.dispatchEvent(new p.window.Event('submit',{bubbles:true,cancelable:true}));
  await wait(40);
  ok(sent.length===0&&p.txt('#reviews').includes('دست‌کم ۱۰ نویسه'),'اعتبارسنجی اولیهٔ طول در مرورگر، بدون درخواست به سرور');
  p.doc.querySelector('#eiReviewBody').value='کارگاه بسیار مفیدی بود و خوب برگزار شد.';
  p.doc.querySelector('form[data-ei-form="review"]').dispatchEvent(new p.window.Event('submit',{bubbles:true,cancelable:true}));
  await wait(120);
  ok(sent.length===1&&Object.keys(JSON.parse(sent[0].body)).join()==='body'&&p.txt('#reviews').includes('دیدگاه شما')&&p.txt('#reviews').includes('در انتظار تأیید برگزارکننده'),
    'ثبت دیدگاه فقط متن می‌فرستد و وضعیت «در انتظار تأیید» (ثبت ≠ انتشار) نمایش داده می‌شود');
  p.doc.querySelector('[data-ei-edit-review]').dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  await wait(30);
  const edit=p.doc.querySelector('form[data-ei-form="review"]');
  ok(edit&&p.doc.querySelector('#eiReviewBody').value==='کارگاه بسیار مفیدی بود و خوب برگزار شد.','ویرایش با متن قبلی پر می‌شود');
  p.doc.querySelector('#eiReviewBody').value='کارگاه بسیار مفیدی بود؛ فقط زمان استراحت کم بود.';
  edit.dispatchEvent(new p.window.Event('submit',{bubbles:true,cancelable:true}));
  await wait(120);
  ok(sent.length===2&&sent[1].method==='PUT'&&p.txt('#reviews').includes('زمان استراحت کم بود'),'ویرایش با PUT روی همان دیدگاه انجام می‌شود');
  p.doc.querySelector('[data-ei-withdraw-review]').dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  await wait(120);
  ok(sent.length===3&&p.txt('#reviews').includes('پس‌گرفته‌شده')&&!p.doc.querySelector('[data-ei-edit-review]'),'پس‌گرفتن، وضعیت را عوض می‌کند و دکمه‌های ویرایش برداشته می‌شوند');
  p.dom.window.close();
}

console.log('\n— خطای سرور و نبود سرور —');
{
  const p=await load('fail');
  ok(p.errors.length===0&&p.doc.querySelectorAll('.ei-error').length===3&&p.doc.querySelectorAll('[data-ei-retry]').length===3,
    'خطای ۵۰۰: هر سه بخش پیام خطا و دکمهٔ تلاش دوباره دارند، بدون خطای JavaScript');
  p.dom.window.close();
  const m=await load('missing');
  ok(m.errors.length===0&&m.txt('#resources').includes('در دسترس نیست'),'۴۰۴: پیام صادقانه، بدون داده‌ی ساختگی');
  m.dom.window.close();
  const html=fs.readFileSync(DIR+'event.html','utf8');
  ok(html.indexOf('event-interaction.js?v=2')<html.indexOf('event-page.js?v=105'),'ماژول تعامل پیش از اسکریپت صفحه بار می‌شود');
  const src=fs.readFileSync(DIR+'event-interaction.js','utf8');
  ok(!/rating|stars|★/.test(src),'در کد صفحه هیچ امتیاز ستاره‌ای/عددی وجود ندارد');
  ok(/credentials: 'same-origin'/.test(src)&&/X-CSRF-Token/.test(src),'درخواست‌ها با کوکی نشست و CSRF ارسال می‌شوند');
}

console.log(`\n${checks-fails}/${checks} بررسی موفق`);
if(fails)process.exitCode=1;
