/* فاز ۹ — حساب کاربر: «محتوای من» (دسترسی‌های واقعی با وضعیت و مهلت) و «سفارش‌ها و پرداخت‌ها»
   (سفارش‌های محتوای ضبط‌شده کنار پرداخت ثبت‌نام‌ها، جدا از هم). jsdom با fetch شبیه‌سازی‌شده؛ سروری اجرا نمی‌شود.
   هیچ دسترسی/پیشرفتی در مرورگر ساخته نمی‌شود؛ ارسال رسید فقط وضعیت سفارش را به «در انتظار بررسی» می‌برد. */
import {fileURLToPath,pathToFileURL} from 'node:url';
import jsdom from 'jsdom';
const {JSDOM}=jsdom;
const DIR=fileURLToPath(new URL('./',import.meta.url));
const OPEN=DIR+'account.html', URLF=pathToFileURL(OPEN).href;
let pass=0, fail=0;
const ok=(c,m)=>{ if(c){pass++; console.log('   ✓ '+m)} else {fail++; console.log('   ✗ '+m)} };
const wait=(t=120)=>new Promise(r=>setTimeout(r,t));
const reply=(status,payload={})=>({ok:status>=200&&status<300,status,json:async()=>payload});
const store=()=>{const m=new Map(); return {getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k),clear:()=>m.clear(),key:i=>[...m.keys()][i],get length(){return m.size}}};
const ACCOUNT={authenticated:true,account_id:'acc-qa-9',provider:'phone',role:null,permissions:[],delivery_bot_url:'https://ble.ir/nora_test_bot'};
const REC='99999999-9999-4999-8999-999999999999', EV='ev-qa-phase9', ORDER='77777777-7777-4777-8777-777777777771', FORM='88888888-8888-4888-8888-888888888881';
const FORM_HREF='form.html?fid='+FORM+'&kind=reg';
const openOrder={id:ORDER,recording_id:REC,method:'card_transfer',status:'awaiting_receipt',open:true,paid:false,amount:1500000,currency:'IRR',expires_at:'2026-10-24T06:00:00Z',
  receipt_submitted:false,receipt_submitted_at:'',receipt_file_name:'',paid_at:'',decided_at:'',decision_reason:'',refunded_at:'',created_at:'2026-10-21T06:00:00Z',updated_at:'',event_id:EV,
  title:'ضبط کارگاه نجوم',event_title:'کارگاه نجوم',card:{number:'6037997599999993',bank:'ملی',holder:'انجمن نجوم'},form_response_id:null,form_payment_id:null,purchase_form_id:FORM};
/* فاز ۹.۱: سفارش فرم‌دار (پاسخ/پرداخت فرم خرید) — رسید و پیگیری فقط در همان فرم */
const formOrder={...openOrder,id:'77777777-7777-4777-8777-777777777774',status:'receipt_submitted',receipt_submitted:true,receipt_submitted_at:'2026-10-21T07:00:00Z',receipt_file_name:'receipt.webp',card:undefined,
  form_response_id:'99999999-9999-4999-8999-999999999991',form_payment_id:'99999999-9999-4999-8999-999999999992',title:'ضبط کارگاه فرم‌دار',event_title:'کارگاه فرم‌دار',recording_id:'rec-7',event_id:'ev-7'};
const paidOrder={...openOrder,id:'77777777-7777-4777-8777-777777777772',status:'paid_manual',open:false,paid:true,paid_at:'2026-10-20T06:00:00Z',decided_at:'2026-10-20T06:00:00Z',card:undefined,title:'ضبط نشست ادبی',event_title:'نشست ادبی',recording_id:'rec-2',event_id:'ev-2'};
const rejectedOrder={...openOrder,id:'77777777-7777-4777-8777-777777777773',status:'rejected',open:false,paid:false,decided_at:'2026-10-19T06:00:00Z',decision_reason:'مبلغ واریزی با سفارش نمی‌خواند',card:undefined,title:'ضبط دورهٔ عکاسی',event_title:'دورهٔ عکاسی',recording_id:'rec-3',event_id:'ev-3'};
const library=[
  {recording_id:'rec-2',event_id:'ev-2',title:'ضبط نشست ادبی',event_title:'نشست ادبی',cover_url:'',status:'published',session_count:3,total_minutes:140,access:{state:'active',source:'purchase',expires_at:'2027-01-18T06:00:00Z',granted_at:'2026-10-20T06:00:00Z',revoked_at:''},progress:null,certificate:{kind:'recording_completion',policy:'manual',automatic:false,manual_issue_only:true,counts_as_attendance:false}},
  {recording_id:'rec-4',event_id:'ev-4',title:'ضبط کارگاه رایگان',event_title:'کارگاه رایگان',cover_url:'',status:'published',session_count:0,total_minutes:0,access:{state:'active',source:'free',expires_at:'',granted_at:'2026-10-18T06:00:00Z',revoked_at:''},progress:null,certificate:{kind:'recording_completion',policy:'none',automatic:false,manual_issue_only:false,counts_as_attendance:false}},
  {recording_id:'rec-5',event_id:'ev-5',title:'ضبط دورهٔ قدیمی',event_title:'دورهٔ قدیمی',cover_url:'',status:'published',session_count:2,total_minutes:60,access:{state:'expired',source:'purchase',expires_at:'2026-09-01T06:00:00Z',granted_at:'2026-06-01T06:00:00Z',revoked_at:''},progress:null},
  {recording_id:'rec-6',event_id:'ev-6',title:'ضبط لغوشده',event_title:'رویداد شش',cover_url:'',status:'published',session_count:1,total_minutes:30,access:{state:'revoked',source:'granted',expires_at:'',granted_at:'2026-07-01T06:00:00Z',revoked_at:'2026-08-01T06:00:00Z'},progress:null}];
const registrations=[{id:'reg-1',form_name:'ثبت‌نام کارگاه',event_title:'کارگاه نجوم',status:'accepted',created_at:'2026-09-01T06:00:00Z',payment_status:'receipt_submitted'}];

async function load(hash,server){
  const errs=[], network=[]; let orders=server.orders||[];
  const dom=await JSDOM.fromFile(OPEN,{runScripts:'dangerously',pretendToBeVisual:true,url:URLF+hash,
    resources:{interceptors:[jsdom.requestInterceptor(request=>/^https?:/i.test(request.url)?new Response('',{status:200,headers:{'content-type':'text/html;charset=utf-8'}}):undefined)]},
    beforeParse(w){
      w.__NORA_TEST_FIXTURE_MODE__=false; w.scrollTo=()=>{}; w.confirm=()=>true;
      if(w.Element&&!w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView=()=>{};
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      Object.defineProperty(w,'localStorage',{configurable:true,value:store()});
      Object.defineProperty(w.document,'cookie',{configurable:true,get:()=>'nora_account_csrf=account-csrf'});
      w.fetch=(url,options={})=>{
        const path=String(url), method=String(options.method||'GET').toUpperCase(); network.push({path,method,options});
        if(path==='/api/account/me') return Promise.resolve(server.account?reply(200,server.account):reply(401,{detail:'account_authentication_required'}));
        if(/^\/api\/account\/registrations\?/.test(path)) return Promise.resolve(reply(200,{items:registrations,total:registrations.length,has_more:false}));
        if(/^\/api\/account\/notifications\?/.test(path)) return Promise.resolve(reply(200,{items:[],has_more:false}));
        if(/^\/api\/account\/files\?/.test(path)) return Promise.resolve(reply(200,{items:[],has_more:false}));
        if(path==='/api/account/identities') return Promise.resolve(reply(200,{identities:[{provider:'phone',linked_at:'2026-01-01T00:00:00Z'}],available_providers:['bale'],bale_link_available:false}));
        if(path==='/api/account/recordings') return Promise.resolve(server.libraryStatus?reply(server.libraryStatus,{detail:'boom'}):reply(200,{items:server.library||[],total:(server.library||[]).length}));
        if(path==='/api/account/certificates'){ const items=server.certificates||[]; const counts={issued:0,revoked:0,expired:0}; items.forEach(c=>{counts[c.effective_status]=(counts[c.effective_status]||0)+1});
          return Promise.resolve(server.certsStatus?reply(server.certsStatus,{detail:'boom'}):reply(200,{items,total:items.length,counts,delivery:'bale_bot',source:'shared_server_database'})); }
        if(/^\/api\/account\/recording-orders\?limit=50&offset=0$/.test(path)) return Promise.resolve(server.ordersStatus?reply(server.ordersStatus,{detail:'boom'}):reply(200,{items:orders,total:orders.length,limit:50,offset:0}));
        const receipt=path.match(/^\/api\/account\/recording-orders\/([0-9a-f-]{36})\/receipt$/);
        if(receipt&&method==='PUT'){ const o=orders.find(x=>x.id===receipt[1]); const next={...o,status:'receipt_submitted',receipt_submitted:true,receipt_submitted_at:'2026-10-21T07:00:00Z',receipt_file_name:String(options.headers['X-File-Name'])}; orders=orders.map(x=>x.id===o.id?next:x); return Promise.resolve(reply(200,next)); }
        const cancel=path.match(/^\/api\/account\/recording-orders\/([0-9a-f-]{36})\/cancel$/);
        if(cancel&&method==='POST'){ const o=orders.find(x=>x.id===cancel[1]); const next={...o,status:'cancelled',open:false}; orders=orders.map(x=>x.id===o.id?next:x); return Promise.resolve(reply(200,next)); }
        return Promise.resolve(reply(404,{detail:'not_found'}));
      };
      w.addEventListener('error',e=>errs.push('error: '+(e.message||'')));
      w.console.error=(...a)=>errs.push('console.error: '+a.join(' '));
    }});
  const {window}=dom;
  if(window.document.readyState!=='complete') await new Promise(resolve=>{const t=setTimeout(resolve,4000); window.addEventListener('load',()=>{clearTimeout(t);resolve()},{once:true})});
  await wait(200);
  const doc=window.document;
  return {dom,window,doc,errs,network,view:()=>doc.querySelector('#viewBox').textContent.replace(/\s+/g,' ').trim(),inView:()=>!doc.querySelector('#viewBox').hidden,
    click:sel=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel); el.dispatchEvent(new window.MouseEvent('click',{bubbles:true,cancelable:true})); return el}};
}

console.log('\n── محتوای من: دسترسی‌های واقعی با وضعیت، مهلت و بدون «ادامهٔ مشاهده» ساختگی ──');
{
  const p=await load('#library',{account:ACCOUNT,library});
  ok(p.errs.length===0,'نمای #library بی‌خطا باز می‌شود'+(p.errs.length?': '+p.errs[0]:''));
  ok(p.inView()&&p.network.some(c=>c.path==='/api/account/recordings')&&p.doc.title==='نورا · محتوای من','#library از API کتابخانهٔ حساب می‌خواند و عنوان خودش را دارد');
  const cards=[...p.doc.querySelectorAll('[data-account-rec-library]')];
  ok(cards.length===4&&p.view().includes('۲ دسترسی فعال از ۴'),'همهٔ دسترسی‌ها با شمارندهٔ واقعی فعال/کل نمایش داده می‌شوند');
  const active=p.doc.querySelector('[data-account-rec-library="rec-2"]');
  ok(active.dataset.recAccessState==='active'&&active.textContent.includes('دسترسی فعال')&&active.textContent.includes('خریداری‌شده')&&active.textContent.includes('دسترسی تا')&&active.textContent.includes('۳ جلسه')&&active.textContent.includes('۲ ساعت و ۲۰ دقیقه')
    &&active.querySelector('a[data-account-rec-view]').getAttribute('href')==='event.html?id=ev-2#recording-sessions','دسترسی فعال: منبع، مهلت واقعی، شمار/مدت جلسات و پیوند «مشاهدهٔ جلسات» به همان صفحهٔ رویداد');
  const free=p.doc.querySelector('[data-account-rec-library="rec-4"]');
  ok(free.textContent.includes('دسترسی رایگان')&&free.textContent.includes('دسترسی دائمی')&&!free.textContent.includes('جلسه')&&!free.textContent.includes('دقیقه'),'دسترسی رایگان دائمی؛ شمار جلسه/مدت فقط وقتی واقعی باشد');
  const expired=p.doc.querySelector('[data-account-rec-library="rec-5"]');
  ok(expired.textContent.includes('منقضی‌شده')&&expired.textContent.includes('پایان‌یافته در')&&!expired.querySelector('[data-account-rec-view]')&&expired.querySelector('a[href="event.html?id=ev-5#recording"]'),'دسترسی منقضی: بدون دکمهٔ مشاهده، فقط پیوند به صفحهٔ محصول');
  const revoked=p.doc.querySelector('[data-account-rec-library="rec-6"]');
  ok(revoked.textContent.includes('لغوشده')&&revoked.textContent.includes('اعطاشده')&&!revoked.querySelector('[data-account-rec-view]'),'دسترسی لغوشده: وضعیت صادقانه و بدون دکمهٔ مشاهده');
  /* ۹.۱ §۲: گواهی پایان محتوا فقط به‌صورت سیاست سرور بیان می‌شود؛ دکمهٔ «دریافت گواهی» وجود ندارد */
  ok(active.querySelector('[data-account-rec-certificate="manual"]')&&active.textContent.includes('فقط با صدور دستی برگزارکننده')&&active.textContent.includes('خرید یا تماشا به‌تنهایی گواهی نمی‌سازد'),'سیاست «صدور دستی» صادقانه و بدون وعدهٔ خودکار');
  ok(free.querySelector('[data-account-rec-certificate="none"]')&&free.textContent.includes('برای این محتوا صادر نمی‌شود'),'سیاست «بدون گواهی» نمایش داده می‌شود');
  ok(!p.doc.querySelector('[data-account-rec-library] button[data-cert], [data-account-rec-library] [data-rec-cert-issue]')&&!/دریافت گواهی|صدور گواهی/.test(p.view()),'هیچ دکمهٔ دریافت/صدور گواهی در کتابخانه نیست');
  ok(!p.view().includes('ادامهٔ مشاهده')&&!/٪|درصد/.test(p.view())&&p.view().includes('پیشرفت تماشا هنوز در سرور ثبت نمی‌شود'),'بدون دادهٔ پیشرفت واقعی، «ادامهٔ مشاهده» یا درصد ساختگی نیست');
  p.dom.window.close();

  const empty=await load('#library',{account:ACCOUNT,library:[]});
  ok(empty.view().includes('هنوز به محتوای ضبط‌شده‌ای دسترسی نداری')&&empty.view().includes('۰ دسترسی فعال از ۰'),'حالت خالی صادقانه');
  empty.dom.window.close();
  const failed=await load('#library',{account:ACCOUNT,libraryStatus:500});
  ok(failed.view().includes('محتوای تو خوانده نشد')&&!!failed.doc.querySelector('[data-account-library-refresh]')&&!failed.doc.querySelector('[data-account-rec-library]'),'خطای سرور: پیام و تلاش دوباره، بدون کارت ساختگی');
  failed.dom.window.close();
  const guest=await load('#library',{account:null});
  ok(guest.inView()&&!guest.network.some(c=>c.path==='/api/account/recordings')&&guest.view().includes('ورود')
    &&!!guest.doc.querySelector('#viewBox a[href="login.html?mode=server&next='+encodeURIComponent('account.html#library')+'"]'),'مهمان در #library فقط دعوت به ورود با بازگشت به همین بخش می‌بیند؛ API صدا زده نمی‌شود');
  guest.dom.window.close();
}

console.log('\n── گواهینامه‌های من (۹.۲): فقط آینهٔ صدور واقعی ربات؛ پایان محتوای ضبط‌شده جدا از گواهی حضور ──');
{
  const certificates=[
    {id:'c1',kind:'recording',status:'issued',effective_status:'issued',serial:'1421/R22',full_code:'1421/R22',doc_no:'1421',person_code:'R22',event_ref:'',event_title:'',title:'پایان دورهٔ ضبط‌شدهٔ نجوم مقدماتی',issued_on:'1405/07/30',expires_on:'',issued_at:'2026-10-22T06:00:00Z',revoked_at:null,has_file:true,has_preview:false},
    {id:'c2',kind:'event',status:'issued',effective_status:'issued',serial:'NC-0023',full_code:'1421/A23',doc_no:'1421',person_code:'A23',event_ref:'17',event_title:'کارگاه نجوم',title:'گواهی حضور',issued_on:'1405/01/12',expires_on:'',issued_at:'2026-04-01T10:00:00Z',revoked_at:null,has_file:false,has_preview:false},
    {id:'c3',kind:'recording',status:'revoked',effective_status:'revoked',serial:'1421/R24',full_code:'1421/R24',doc_no:'1421',person_code:'R24',event_ref:'',event_title:'',title:'پایان محتوای تلسکوپ',issued_on:'1405/07/01',expires_on:'',issued_at:'2026-09-23T06:00:00Z',revoked_at:'2026-10-01T06:00:00Z',has_file:false,has_preview:false}];
  const p=await load('#library',{account:ACCOUNT,library,certificates});
  ok(p.errs.length===0,'نمای #library با بخش گواهینامه‌ها بی‌خطا است'+(p.errs.length?': '+p.errs[0]:''));
  ok(p.network.some(c=>c.path==='/api/account/certificates')&&p.network.filter(c=>c.method!=='GET'&&/certificat/.test(c.path)).length===0,'گواهینامه‌ها فقط با GET از سرور خوانده می‌شوند؛ هیچ درخواست ساخت/صدور از مرورگر نمی‌رود');
  const cards=[...p.doc.querySelectorAll('[data-account-certificate]')];
  ok(cards.length===3&&p.view().includes('گواهینامه‌های من')&&p.view().includes('۲ معتبر')&&p.view().includes('۱ باطل‌شده'),'هر سه رکورد با شمارندهٔ واقعی معتبر/باطل‌شده نمایش داده می‌شوند');
  const rec=p.doc.querySelector('[data-account-certificate="c1"]'), att=p.doc.querySelector('[data-account-certificate="c2"]'), rev=p.doc.querySelector('[data-account-certificate="c3"]');
  ok(rec.dataset.certKind==='recording'&&rec.textContent.includes('پایان محتوای آموزشی ضبط‌شده')&&rec.textContent.includes('پایان دورهٔ ضبط‌شدهٔ نجوم مقدماتی')&&rec.textContent.includes('1421/R22')&&rec.textContent.includes('گواهی حضور در رویداد نیست'),'گواهی پایان محتوای ضبط‌شده: نوع، عنوان صریح، شمارهٔ یکتا و تذکر «حضور نیست»');
  ok(att.dataset.certKind==='event'&&att.textContent.includes('گواهی رویداد / حضور')&&att.textContent.includes('کارگاه نجوم')&&!att.textContent.includes('حضور در رویداد نیست'),'گواهی حضور رویداد با برچسب جدا و بدون تذکر محتوای ضبط‌شده');
  const botLink=rec.querySelector('a[data-account-cert-bot]');
  /* زیر file:// پیوند بیرونی توسط ui.js غیرفعال می‌شود (aria-disabled)؛ در سرور واقعی همان پیوند ble.ir می‌ماند. */
  ok(!!botLink&&(String(botLink.getAttribute('href')||'').startsWith('https://ble.ir/nora_test_bot')||botLink.getAttribute('aria-disabled')==='true')&&!rec.querySelector('a[href*="/api/account/"]'),'دریافت فایل فقط از طریق ربات بله؛ هیچ پیوند دانلود مستقیم در حساب نیست');
  ok(rev.dataset.certStatus==='revoked'&&rev.textContent.includes('باطل‌شده')&&!rev.querySelector('a[data-account-cert-bot]')&&rev.textContent.includes('در استعلام تأیید نمی‌شود'),'گواهی باطل‌شده با وضعیت واقعی و بدون دکمهٔ دریافت');
  ok(!/درخواست گواهی|ساخت گواهی|صدور گواهی/.test(p.view()),'هیچ دکمهٔ «درخواست/ساخت گواهی» در حساب نیست (صدور فقط دستی در ربات)');
  p.dom.window.close();

  const empty=await load('#library',{account:ACCOUNT,library,certificates:[]});
  ok(empty.doc.querySelectorAll('[data-account-certificate]').length===0&&empty.view().includes('هنوز گواهینامه‌ای در حساب ثبت نشده')&&empty.view().includes('خرید یا تماشای محتوا به‌تنهایی گواهی نمی‌سازد'),'حالت خالی صادقانه: بدون گواهی ساختگی؛ خرید/تماشا گواهی نمی‌سازد');
  empty.dom.window.close();

  const broken=await load('#library',{account:ACCOUNT,library,certsStatus:503});
  ok(broken.view().includes('گواهینامه‌ها خوانده نشدند')&&!!broken.doc.querySelector('[data-account-certs-refresh]')&&broken.doc.querySelectorAll('[data-account-rec-library]').length===4,'خطای سرور گواهینامه‌ها: پیام خطا و «تلاش دوباره»؛ کتابخانه همچنان نمایش داده می‌شود');
  broken.dom.window.close();
}

console.log('\n── سفارش‌ها و پرداخت‌ها (۹.۱): سفارش فرم‌دار، سفارش قدیمی، پرداخت‌شده، ردشده؛ خرید فقط از فرم خرید ──');
{
  const p=await load('#payments',{account:ACCOUNT,orders:[openOrder,paidOrder,rejectedOrder,formOrder]});
  ok(p.errs.length===0,'نمای #payments بی‌خطا باز می‌شود'+(p.errs.length?': '+p.errs[0]:''));
  ok(p.doc.title==='نورا · سفارش‌ها و پرداخت‌ها'&&p.network.some(c=>c.path==='/api/account/recording-orders?limit=50&offset=0')&&p.network.some(c=>/^\/api\/account\/registrations\?/.test(c.path)),'سفارش‌های محتوا و پرداخت ثبت‌نام‌ها هر دو از سرور خوانده می‌شوند');
  ok(p.view().includes('سفارش‌های محتوای ضبط‌شده')&&p.view().includes('پرداخت ثبت‌نام‌ها')&&p.view().includes('۴ سفارش محتوای ضبط‌شده')&&p.view().includes('۱ ثبت‌نام دارای وضعیت پرداخت'),'دو فهرست جدا با شمارنده‌های واقعی: خرید محتوا ≠ ثبت‌نام');
  const open=p.doc.querySelector('[data-account-rec-order="'+ORDER+'"]');
  ok(open.dataset.recOrderStatus==='awaiting_receipt'&&open.textContent.includes('در انتظار رسید')&&open.textContent.includes('6037-9975-9999-9993')&&open.textContent.includes('۱,۵۰۰,۰۰۰ ریال')&&open.textContent.includes('مهلت:'),'سفارش باز: وضعیت، کارت مقصد، مبلغ و مهلت از سرور');
  ok(!open.querySelector('form')&&!open.querySelector('input[type=file]')&&!!open.querySelector('[data-account-rec-legacy]')&&!!open.querySelector('[data-account-rec-cancel]')&&open.querySelector('a[data-account-rec-form]').getAttribute('href')===FORM_HREF,'سفارش قدیمی بدون فرم: بدون بارگذاری رسید در حساب؛ انصراف + پیوند فرم خرید');
  const viaForm=p.doc.querySelector('[data-account-rec-order="'+formOrder.id+'"]');
  ok(viaForm.dataset.recOrderStatus==='receipt_submitted'&&!!viaForm.querySelector('[data-account-rec-via-form]')&&viaForm.textContent.includes('در صف بررسی مدیران')&&!viaForm.querySelector('form')&&!viaForm.querySelector('[data-account-rec-cancel]')&&!viaForm.querySelector('[data-account-rec-view]')&&viaForm.querySelector('a[data-account-rec-form]').getAttribute('href')===FORM_HREF,'سفارش فرم‌دار: وضعیت واقعی، بدون انصراف/رسید/مشاهده؛ پیگیری در فرم خرید');
  ok(!p.network.some(c=>c.method==='PUT'||(c.method==='POST'&&/\/orders$/.test(c.path))),'هیچ PUT رسید یا POST سفارش از صفحهٔ حساب فرستاده نمی‌شود');
  const paid=p.doc.querySelector('[data-account-rec-order="'+paidOrder.id+'"]');
  ok(paid.textContent.includes('پرداخت تأیید شد')&&paid.querySelector('a[data-account-rec-view]').getAttribute('href')==='event.html?id=ev-2#recording-sessions'&&!paid.querySelector('form'),'سفارش پرداخت‌شده: فقط «مشاهدهٔ جلسات»');
  const rejected=p.doc.querySelector('[data-account-rec-order="'+rejectedOrder.id+'"]');
  ok(rejected.textContent.includes('رد شد')&&rejected.textContent.includes('مبلغ واریزی با سفارش نمی‌خواند')&&rejected.querySelector('a[data-account-rec-retry]').getAttribute('href')===FORM_HREF&&!rejected.querySelector('form'),'سفارش ردشده: دلیل سرور و خرید دوباره از فرم خرید');
  const noForm=await load('#payments',{account:ACCOUNT,orders:[{...rejectedOrder,purchase_form_id:null}]});
  ok(noForm.doc.querySelector('a[data-account-rec-retry]').getAttribute('href')==='event.html?id=ev-3#recording','بدون فرم منتشرشده: فقط پیوند صفحهٔ محصول، بدون مسیر ساختگی');
  noForm.dom.window.close();
  p.dom.window.close();

  /* انصراف */
  const c=await load('#payments',{account:ACCOUNT,orders:[openOrder]});
  c.click('[data-account-rec-cancel="'+ORDER+'"]'); await wait(200);
  const post=c.network.find(x=>x.method==='POST'&&x.path==='/api/account/recording-orders/'+ORDER+'/cancel');
  ok(!!post&&post.options.headers['X-CSRF-Token']==='account-csrf'&&c.doc.querySelector('[data-account-rec-order="'+ORDER+'"]').dataset.recOrderStatus==='cancelled'&&!!c.doc.querySelector('[data-account-rec-retry]'),'انصراف با CSRF؛ کارت به «لغو شد» و مسیر سفارش دوباره تغییر می‌کند');
  c.dom.window.close();

  const none=await load('#payments',{account:ACCOUNT,orders:[]});
  ok(none.view().includes('سفارشی برای محتوای ضبط‌شده نداری')&&none.view().includes('۱ ثبت‌نام دارای وضعیت پرداخت')&&!none.view().includes('کیف پول'),'بدون سفارش: حالت خالی صادقانه؛ پرداخت ثبت‌نام‌ها سر جایش می‌ماند');
  none.dom.window.close();
  const failed=await load('#payments',{account:ACCOUNT,ordersStatus:500});
  ok(failed.view().includes('سفارش‌های محتوای ضبط‌شده خوانده نشدند')&&!!failed.doc.querySelector('[data-account-rec-orders-refresh]')&&failed.view().includes('ثبت‌نام کارگاه'),'خطای سرویس سفارش‌ها فهرست پرداخت ثبت‌نام‌ها را از کار نمی‌اندازد');
  failed.dom.window.close();
  const guest=await load('#payments',{account:null});
  ok(guest.view().includes('ورود')&&!guest.network.some(x=>/recording-orders/.test(x.path)),'مهمان: دعوت به ورود، بدون فراخوانی سفارش‌ها');
  guest.dom.window.close();
}

console.log('\n── خانهٔ حساب: ردیف‌های «محتوای من» و «سفارش‌ها و پرداخت‌ها» با شمارندهٔ سروری ──');
{
  const p=await load('',{account:ACCOUNT,library,orders:[openOrder]});
  await p.window.NORA_UI?.syncServerProfile?.(); await wait(150);
  const rows=p.doc.querySelector('.server-rows');
  ok(!!rows&&!!rows.querySelector('a[href="account.html#library"]')&&!rows.querySelector('a[href="account.html#payments"]')&&rows.textContent.includes('۵ بخش')&&p.doc.querySelector('.server-paybar').textContent.includes('سفارش‌ها و پرداخت‌ها')&&!!p.doc.querySelector('.server-paybar a[href="account.html#payments"]'),'بخش‌های من شامل «محتوای من» است و نورا پی تنها ورودی «سفارش‌ها و پرداخت‌ها» می‌ماند');
  ok(!rows.textContent.includes('دسترسی فعال'),'شمارندهٔ کتابخانه پیش از خواندن از سرور نمایش داده نمی‌شود (بدون عدد حدسی)');
  p.dom.window.close();
}

console.log(`\naccount-recordings: ${pass} قبول، ${fail} خطا`);
if(fail) process.exit(1);
