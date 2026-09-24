/* ══════════════════════════════════════════════════════════════════════════
   نورا — آزمون صفحهٔ «ورود» (login.html)
   ──────────────────────────────────────────────────────────────────────────
   یک کارت، سه پله: شماره → تحویل شماره به پیام‌گیر (بله، ایتا، تلگرام) →
   کد پنج‌رقمی → حساب باز می‌شود. پیوندهای راهنما و پشتیبانی و قوانین،
   بازگشت به بخش خواسته‌شده، حال کسی که همین حالا وارد شده، و پیمان با
   account.js و sw.js هم این‌جا بررسی می‌شود.

   اجرا:  node login.test.mjs
   ══════════════════════════════════════════════════════════════════════════ */
import jsdom from 'jsdom';
const {JSDOM}=jsdom;
const DIR=new URL('./',import.meta.url).pathname;
const wait=(t=120)=>new Promise(r=>setTimeout(r,t));
function makeStore(init){ const m=new Map(Object.entries(init||{}));
  return {getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k),clear:()=>m.clear(),key:i=>[...m.keys()][i],get length(){return m.size},_m:m} }
async function load(store,search){
  const errs=[];
  const dom=await JSDOM.fromFile(DIR+'login.html',{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,
    url:'file://'+DIR+'login.html'+(search||''),
    beforeParse(w){ w.scrollTo=()=>{}; if(w.Element&&!w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView=()=>{};
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      if(store) Object.defineProperty(w,'localStorage',{configurable:true,value:store});
      w.addEventListener('error',e=>errs.push('error: '+(e.message||'')));
      const ce=w.console.error; w.console.error=(...a)=>errs.push('console.error: '+a.join(' '));
    }});
  await wait(700);
  const doc=dom.window.document;
  return {window:dom.window,doc,errs,
    all:s=>[...doc.querySelectorAll(s)], txt:s=>{const e=doc.querySelector(s);return e?e.textContent.trim():''},
    click(s){const e=typeof s==='string'?doc.querySelector(s):s; if(e) e.dispatchEvent(new dom.window.MouseEvent('click',{bubbles:true}))},
    type(s,v){const e=doc.querySelector(s); if(!e) return; e.value=v; e.dispatchEvent(new dom.window.Event('input',{bubbles:true}))},
    submit(s){const e=doc.querySelector(s); if(e) e.dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}))},
    store};
}
let pass=0,fail=0;
const ok=(c,m)=>{ if(c){pass++;console.log('   ✓ '+m)} else {fail++;console.log('   ✗ '+m)} };

/* ۱) شکل صفحه */
{
  console.log('\n── شکل صفحهٔ ورود ──');
  const p=await load(makeStore());
  ok(p.errs.length===0,'بی‌خطا بار می‌شود'+(p.errs.length?': '+p.errs[0]:''));
  ok(p.doc.title==='نورا · ورود','عنوان سند');
  ok(p.doc.documentElement.dir==='rtl'&&/fa/.test(p.doc.documentElement.lang),'راست‌به‌چپ و فارسی');
  ok(p.txt('#lgTitle')==='ورود به نورا','نام صفحه: ورود به نورا');
  ok(p.txt('#lgEye').includes('خط زندگی'),'نام گروه زیر نشان');
  ok(p.doc.querySelector('.lgmark img')!==null,'نشان نورا بالای کارت');
  ok(p.txt('.lgcard').includes('رمز و گذرواژه‌ای در کار نیست'),'توضیح بی‌رمز بودن ورود');
  ok(p.all('#lgStatus').length===1,'کادر وضعیت برای صفحه‌خوان');
  ok(p.all('.tabbar a').length===3,'نوار پایین سه‌تایی');
  ok(p.doc.querySelector('.help-btn')!==null,'نشان پشتیبانی در نوار بالا');
  ok(p.doc.querySelector('[data-theme-toggle]')!==null,'کلید شب و روز');
  ok(p.all('.lglinks a').length===2&&p.all('#rulesBtn').length===1,'سه پیوند ته کارت: راهنما، پشتیبانی، قوانین');
  ok(p.all('.lglinks a')[0].getAttribute('href')==='support.html#reader','راهنما به فصل‌های راهنما می‌رود');
  ok(p.all('.lglinks a')[1].getAttribute('href')==='support.html','پشتیبانی به صفحهٔ پشتیبانی');
}

/* ۲) پلهٔ شماره */
{
  console.log('\n── پلهٔ شماره ──');
  const p=await load(makeStore());
  ok(p.all('#lgPhone').length===1,'کادر شماره');
  ok(p.all('.lgtel .pref').length===1&&p.txt('.lgtel .pref')==='۰۹','پیش‌شمارهٔ ۰۹ در کادر');
  ok(p.all('#lgForm .lgbtn').length===1&&p.txt('#lgGo')==='ورود','یک دکمهٔ ورود');
  ok(p.all('.lgmsgs .lgmsg').length===3,'سه پیام‌گیر');
  ok(p.all('.lgmsgs .lgmsg').map(b=>b.textContent.trim()).join(',')==='بله,ایتا,تلگرام','نام پیام‌گیرها: بله، ایتا، تلگرام');
  ok(p.all('.lgmsgs .lgmsg svg').length===3,'نشان هر پیام‌گیر');
  ok(p.txt('.lgvia').includes('ورود با'),'جداکنندهٔ «ورود با»');
  ok(p.txt('.lgcard').includes('۰۹۱۲۳۴۵۶۷۸۹')===false,'نمونهٔ شماره در متن راهنما نیست، در خطا می‌آید');
  p.submit('#lgForm');
  ok(!p.doc.querySelector('#lgErr').hidden&&p.txt('#lgErr').includes('یازده رقم'),'شمارهٔ خالی خطا می‌دهد');
  p.type('#lgPhone','0912345');
  p.submit('#lgForm');
  ok(p.txt('#lgErr').includes('کامل'),'شمارهٔ ناقص هم خطا می‌دهد');
  ok(p.all('.lghand').length===0,'تا شماره درست نشود، پلهٔ بعد نمی‌آید');
  p.type('#lgPhone','۰۹۱۲۳۴۵۶۷۸۹');
  p.submit('#lgForm');
  await wait(150);
  ok(p.all('.lghand').length===1,'با شمارهٔ درست، به پلهٔ تحویل می‌رود');
  ok(p.txt('.lghand').includes('بله'),'پیش‌فرض: تحویل به بله');
  ok(p.txt('.lghand').includes('۰۹۱۲۳…۶۷۸۹')||p.txt('.lghand').includes('…'),'شمارهٔ پوشیده روی کارت تحویل');
  ok(p.store.getItem('nora-home-auth')&&JSON.parse(p.store.getItem('nora-home-auth')).mobile==='09123456789','پلهٔ کد در حافظه می‌ماند');
}

/* ۳) پلهٔ کد و ورود */
{
  console.log('\n── پلهٔ کد ──');
  const p=await load(makeStore());
  p.type('#lgPhone','9123456789');            /* بی صفر و ۰۹ هم قبول است */
  p.submit('#lgForm'); await wait(140);
  ok(p.all('#lgCode').length===1,'کادر کد پنج‌رقمی');
  ok(p.txt('#lgCodeHint').includes('۵۴۳۲۱'),'کد نمونه روی صفحه هست');
  ok(p.all('#lgTtl').length===1,'شمارندهٔ اعتبار کد');
  p.type('#lgCode','12345'); p.submit('#lgForm2'); await wait(120);
  ok(!p.doc.querySelector('#lgErr2').hidden,'کد نادرست خطا می‌دهد');
  ok(p.store.getItem('nora-home-user')===null,'با کد نادرست کسی وارد نمی‌شود');
  p.type('#lgCode','۵۴۳۲۱'); p.submit('#lgForm2'); await wait(160);
  const u=p.store.getItem('nora-home-user');
  ok(u&&JSON.parse(u).mobile==='09123456789','با کد درست، نشست نوشته می‌شود');
  ok(p.all('.lgcheck').length===1&&p.txt('.lgdtitle').includes('خوش آمدی'),'پلهٔ پایان با نشان تیک');
  ok(p.all('#lgNext').length===1&&p.doc.querySelector('#lgNext').getAttribute('href')==='account.html','دکمهٔ رفتن به حساب من');
  ok(p.store.getItem('nora-home-auth')===null,'پلهٔ نیمه‌کارهٔ ورود پاک می‌شود');
}

/* ۴) پیام‌گیرهای دیگر و بازگشت */
{
  console.log('\n── ایتا و برگشت ──');
  const p=await load(makeStore());
  p.type('#lgPhone','09121234567');
  p.click('[data-via="eitaa"]'); await wait(150);
  ok(p.txt('.lghand').includes('ایتا'),'تحویل به ایتا');
  ok(p.doc.querySelector('#lgOpen').getAttribute('href').includes('eitaa.com'),'پیوند باز کردن ایتا');
  ok(p.doc.querySelector('#lgOpen').getAttribute('rel').includes('noopener'),'پیوند بیرونی rel دارد');
  ok(p.doc.querySelector('#lgOpen').getAttribute('target')==='_blank','پیوند در تب تازه باز می‌شود');
  p.click('#lgBack'); await wait(150);
  ok(p.all('#lgPhone').length===1,'«تغییر شماره» به پلهٔ نخست برمی‌گردد');
  p.type('#lgPhone','09121234567'); p.click('[data-via="telegram"]'); await wait(150);
  ok(p.txt('.lghand').includes('تلگرام'),'تحویل به تلگرام');
  p.click('#lgAgain'); await wait(60);
  ok(p.doc.querySelector('#lgCode').value==='','«دوباره بفرست» کادر کد را خالی می‌کند');
  ok(p.txt('#lgCodeHint').includes('کد تازه'),'و پیام تازه می‌دهد');
  ok(p.all('#lgTtl').length===1,'شمارنده از نو می‌شمارد');
}

/* ۵) کسی که وارد شده و کسی که نیمه‌کاره مانده */
{
  console.log('\n── حال‌های آغازین ──');
  const p=await load(makeStore({'nora-home-user':JSON.stringify({name:'سارا محمدی',mobile:'09121234567'})}));
  ok(p.txt('.lgdtitle').includes('همین حالا وارد شده‌ای'),'کاربر واردشده کارت تازه می‌بیند');
  ok(p.all('#lgOutMost').length===1,'و می‌تواند بیرون بیاید');
  p.click('#lgOutMost'); await wait(120);
  ok(p.store.getItem('nora-home-user')===null,'خروج، نشست را پاک می‌کند');
  ok(p.all('#lgPhone').length===1,'و به پلهٔ شماره برمی‌گردد');
  const q=await load(makeStore({'nora-home-auth':JSON.stringify({step:'code',mobile:'09121112233'})}));
  ok(q.all('.lghand').length===1&&q.txt('.lghand').includes('۲۲۳۳')||q.txt('.lghand').includes('…'),'ورود نیمه‌کاره، از پلهٔ کد ادامه می‌دهد');
}

/* ۶) بازگشت به صفحهٔ خواسته‌شده */
{
  console.log('\n── نشانی بازگشت ──');
  const p=await load(makeStore(),'?next=account.html%23club');
  p.type('#lgPhone','09121234567'); p.submit('#lgForm'); await wait(140);
  p.type('#lgCode','54321'); p.submit('#lgForm2'); await wait(140);
  ok(p.doc.querySelector('#lgNext').getAttribute('href')==='account.html#club','پس از ورود به نشانی خواسته‌شده برمی‌گردد');
  const bad=await load(makeStore(),'?next=https%3A%2F%2Fbad.example');
  ok(bad.window.NORA_LOGIN.nextUrl()==='account.html','نشانی بیرونی پذیرفته نمی‌شود');
}

/* ۷) ورقهٔ قوانین */
{
  console.log('\n── قوانین ──');
  const p=await load(makeStore());
  ok(p.doc.querySelector('#shRules')!==null,'ورقهٔ قوانین در صفحه هست');
  p.click('#rulesBtn'); await wait(140);
  ok(p.doc.querySelector('#shRules').classList.contains('on'),'با زدن «قوانین» باز می‌شود');
  ok(p.all('#shRules .rrow').length===5,'پنج بند کوتاه');
  ok(p.txt('#shRules').includes('بلیت و کارت ورود'),'بند بلیت');
  ok(p.txt('#shRules').includes('حریم'),'بند حساب و حریم خصوصی');
  p.click('#shRules [data-close]'); await wait(120);
  ok(!p.doc.querySelector('#shRules').classList.contains('on'),'و بسته می‌شود');
}

/* ۸) پیمان با بقیهٔ صفحه‌ها */
{
  console.log('\n── پیوند با بقیهٔ صفحه‌ها ──');
  const fs=await import('fs');
  const acc=fs.readFileSync(DIR+'account.js','utf8');
  ok(acc.includes("login.html?next="),'حساب من به صفحهٔ ورود می‌فرستد');
  ok(acc.includes('data-logout-yes'),'و خروج از حساب دارد');
  const sw=fs.readFileSync(DIR+'sw.js','utf8');
  ok(sw.includes("'login.html'")&&sw.includes("'login.js'")&&sw.includes("'login.css'"),'سرویس‌ورکر صفحهٔ ورود را پیش‌بار می‌کند');
  const html=fs.readFileSync(DIR+'login.html','utf8');
  ok(html.includes('login.css?v=22')&&html.includes('login.js?v=22')&&html.includes('data.js?v=22'),'نسخهٔ دارایی‌ها تازه است');
  const data=fs.readFileSync(DIR+'data.js','utf8');
  ok(data.includes("ble.ir")&&data.includes("eitaa.com"),'نشانی بله و ایتا در داده هست');
  const css=fs.readFileSync(DIR+'login.css','utf8');
  ok(/@keyframes rise/.test(css)&&/@keyframes shake/.test(css),'انیمیشن‌های صفحه در CSS خودش هست');
}
console.log('\n'+(fail?'✗ '+fail+' رد، '+pass+' قبول':'✓ همه سبز: '+pass+' قبول'));
process.exit(fail?1:0);
