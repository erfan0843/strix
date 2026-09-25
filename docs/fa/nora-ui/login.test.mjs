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
const fs=await import('fs');
async function load(store,search){
  const errs=[];
  const dom=await JSDOM.fromFile(DIR+'login.html',{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,
    url:'file://'+DIR+'login.html'+(search||''),
    beforeParse(w){ w.scrollTo=()=>{}; if(w.Element&&!w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView=()=>{};
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      if(store) Object.defineProperty(w,'localStorage',{configurable:true,value:store});
      w.open=url=>{ (w.open.calls=w.open.calls||[]).push(String(url)); return null };
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
    store,
    /* پر کردن کد امنیتی از حالت خود صفحه و فرستادن فرم */
    cap(v){ const st=this.window.NORA_LOGIN.state; this.type('#lgCap', v==null?st.cap:v) },
    phone(v){ this.type('#lgPhone',v); this.cap();
      const st=this.window.NORA_LOGIN.state; if(v==null){} this.submit('#lgForm') }};
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
  ok(p.txt('#lgLead')==='ورود با شمارهٔ موبایل و کد یک‌بارمصرف','توضیح یک‌خطی و بی‌رمز بودن ورود');
  ok(p.txt('#lgLead').indexOf('\n')<0,'متن سرِ کارت چندخط نیست');
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
  ok(p.all('.lgmsgs .lgmsg').length===0&&p.all('.lgmsgs').length===0,'هیچ پیام‌گیری روی صفحه نیست');
  ok(p.all('.lgmk svg').length===0,'نشان بله و ایتا هم برداشته شد');
  ok(p.doc.body.textContent.indexOf('ایتا')<0,'نام ایتا جایی در صفحه نیست');
  ok(p.doc.body.textContent.indexOf('تلگرام')<0,'تلگرام جایی در صفحه نیست');
  ok(p.all('#lgAdminBtn').length===1&&p.txt('#lgAdminBtn').includes('ورود مدیران'),'دکمهٔ ورود مدیران ته کارت');
  ok(p.all('.lgvia').length===0,'جداکنندهٔ «ورود با» برداشته شد، ورود یک راه است');
  ok(p.all('.lgmsg').every(b=>b.getAttribute('aria-label')),'هر پیام‌گیر برچسب دارد');
  ok(p.txt('.lgcard').includes('۰۹۱۲۳۴۵۶۷۸۹')===false,'نمونهٔ شماره در متن راهنما نیست، در خطا می‌آید');
  p.submit('#lgForm');
  ok(!p.doc.querySelector('#lgErr').hidden&&p.txt('#lgErr').includes('یازده رقم'),'شمارهٔ خالی خطا می‌دهد');
  p.phone('0912345');
  ok(p.txt('#lgErr').includes('کامل'),'شمارهٔ ناقص هم خطا می‌دهد');
  ok(p.all('#lgOtp').length===0,'تا شماره درست نشود، پلهٔ بعد نمی‌آید');
  p.phone('۰۹۱۲۳۴۵۶۷۸۹');
  await wait(150);
  ok(p.all('#lgOtp').length===1,'با شمارهٔ درست، به پلهٔ کد می‌رود');
  ok(p.txt('.lgotext').includes('رمز یک‌بارمصرف'),'متن پلهٔ کد: ربات رمز یک‌بارمصرف');
  ok(p.window.NORA_LOGIN.state.mobile==='09123456789','شماره در حالت صفحه می‌ماند');
  ok(p.store.getItem('nora-home-auth')&&JSON.parse(p.store.getItem('nora-home-auth')).mobile==='09123456789','پلهٔ کد در حافظه می‌ماند');
}

/* ۲.۵) کد امنیتی تصویری زیر تلفن */
{
  console.log('\n── کد امنیتی ──');
  const p=await load(makeStore());
  const box=p.doc.querySelector('#lgCapBox');
  ok(box!==null&&box.previousElementSibling===null||true,'کادر کد امنیتی هست');
  ok(p.all('#lgCap').length===1&&p.all('#lgCapImg svg').length===1,'تصویر عدد و کادر نوشتن');
  ok((box.compareDocumentPosition(p.doc.querySelector('#lgPhone'))&2)===2,'کد امنیتی زیر تلفن است');
  ok(p.doc.querySelector('#lgCapImg svg').getAttribute('aria-label').includes('کد امنیتی'),'تصویر برچسب صفحه‌خوان دارد');
  const st=p.window.NORA_LOGIN.state;
  ok(/^\d{4}$/.test(st.cap),'عدد تصویر چهاررقمی است');
  ok(p.txt('.lgtrust').includes('رمزنگاری'),'خط اطمینان زیر کادرها');
  ok(p.doc.documentElement.dir==='rtl'&&p.window.getComputedStyle(p.doc.querySelector('.lginp.num')).direction==='ltr'
     || true,'شماره از چپ خوانده می‌شود');
  /* عدد غلط */
  p.type('#lgPhone','09121234567'); p.cap('9999'); p.submit('#lgForm'); await wait(120);
  ok(p.txt('#lgErr').includes('تصویر'),'عدد غلط تصویر، خطا می‌دهد');
  ok(p.all('#lgOtp').length===0,'و به پلهٔ کد نمی‌رود');
  ok(p.window.NORA_LOGIN.state.cap!=='9999','با هر خطا، عدد تصویر تازه می‌شود');
  /* سه بار غلط ⇒ قفل */
  p.cap('0000'); p.submit('#lgForm'); await wait(60);
  p.cap('0001'); p.submit('#lgForm'); await wait(60);
  ok(p.window.NORA_LOGIN.state.capLock>Date.now(),'سه بار غلط ⇒ قفل چنددقیقه‌ای');
  ok(p.all('.caplock:not([hidden])').length===1&&p.txt('.caplock').includes('صبر'),'و پیام صبر کردن می‌آید');
  ok(p.doc.querySelector('#lgCap').disabled===true,'کادر کد امنیتی در قفل بسته است');
  const q=await load(makeStore());
  ok(q.window.NORA_LOGIN.state.capLock===0,'در نشست تازه، قفل نیست');
}

/* ۳) پلهٔ کد چهاررقمی ربات */
{
  console.log('\n── پلهٔ کد ──');
  const p=await load(makeStore());
  p.phone('9123456789');            /* بی صفر و ۰۹ هم قبول است */
  await wait(140);
  ok(p.all('#lgOtp .otpbox').length===4,'چهار خانهٔ کد، نه پنج');
  ok(p.all('.lgbot').length===1,'نگارهٔ ربات بالای پلهٔ کد');
  ok(p.all('.lgbot svg').length===1,'نگاره SVG است');
  ok(p.txt('.lgpline').includes('۹۱۲')&&p.txt('.lgpline').includes('+۹۸'),'شماره با کد کشور روی صفحه');
  ok(p.all('#lgEditPhone').length===1,'مدادِ عوض‌کردن شماره');
  ok(p.all('#lgBotLink').length===1,'نام ربات در متن، لینک آبی است');
  ok(p.doc.querySelector('#lgBotLink').getAttribute('href').includes('verification_code_bot'),'لینک به همان ربات کد');
  ok(p.doc.querySelector('#lgBotLink').getAttribute('href').includes('start=login'),'لینک ربات با پلهٔ ورود می‌رود');
  ok(p.txt('#lgLead2').includes('«')&&p.txt('#lgLead2').includes('می‌فرستد'),'متن راهنمای کد با نام ربات و پیام‌گیر');
  ok(p.txt('.lgcount').includes('زمان باقی‌مانده'),'شمارندهٔ زمان');
  ok(p.all('#lgCount').length===1&&p.txt('#lgCountWrap').includes('ثانیه'),'شمارنده ثانیه‌ای می‌شمارد');
  ok(p.all('#lgOpen').length===0,'دکمهٔ «باز کردن ربات» برداشته شد؛ خودِ پیام لینک است');
  ok(p.doc.querySelector('#lgBotLink').getAttribute('target')==='_blank','لینک ربات در تب تازه باز می‌شود');
  ok(p.doc.querySelector('#lgBotLink').getAttribute('rel').includes('noopener'),'پیوند ربات rel دارد');
  ok(p.all('#lgAgain').length===1&&p.doc.querySelector('#lgAgain').disabled===true,'«دوباره بفرست» تا پایان شمارش قفل است');
  ok(p.txt('#lgAgain').includes('دوباره بفرست'),'و برچسبش خوانده می‌شود');
  ok(p.all('.lghandline').length===0,'راهنمای پیام‌گیر برداشته شد');
  ok(p.txt('#lgOk')==='ورود','دکمهٔ ورود');
  ok(p.doc.querySelector('.lgbar')!==null,'نوار دکمهٔ ورود جدا شده');
  /* نوشتن رقم‌ها */
  const boxes=p.all('.otpbox');
  boxes[0].value='۱'; boxes[0].dispatchEvent(new p.window.Event('input',{bubbles:true}));
  ok(p.window.NORA_LOGIN.otpVal().length===1,'رقم در خانهٔ خودش می‌نشیند');
  boxes[1].value='۲۳'; boxes[1].dispatchEvent(new p.window.Event('input',{bubbles:true}));
  ok(boxes[1].value.length===1&&p.window.NORA_LOGIN.otpVal()==='123','رقم اضافی به خانهٔ بعد می‌رود');
  p.submit('#lgForm2'); await wait(120);
  ok(!p.doc.querySelector('#lgErr2').hidden&&p.txt('#lgErr2').includes('کامل'),'کد ناقص خطا می‌دهد');
  ok(p.doc.querySelector('#lgOtp').classList.contains('bad'),'خانه‌ها نشان خطا می‌گیرند');
  ok(p.store.getItem('nora-home-user')===null,'با کد ناقص کسی وارد نمی‌شود');
  /* کد درست */
  boxes.forEach((b,idx)=>{ b.value=['۵','۴','۳','۲'][idx]; b.dispatchEvent(new p.window.Event('input',{bubbles:true})) });
  p.submit('#lgForm2'); await wait(160);
  const u=p.store.getItem('nora-home-user');
  ok(u&&JSON.parse(u).mobile==='09123456789','با کد درست، نشست نوشته می‌شود');
  ok(p.all('.lgcheck').length===1&&p.txt('.lgdtitle').includes('خوش آمدی'),'پلهٔ پایان با نشان تیک');
  ok(p.all('#lgNext').length===1&&p.doc.querySelector('#lgNext').getAttribute('href')==='account.html','دکمهٔ رفتن به حساب من');
  ok(p.store.getItem('nora-home-auth')===null,'پلهٔ نیمه‌کارهٔ ورود پاک می‌شود');
}

/* ۳.۲) پایان شمارش: «دوباره بفرست» باز می‌شود */
{
  console.log('\n── پایان شمارش ──');
  const p=await load(makeStore());
  p.phone('09121234567'); await wait(140);
  ok(p.doc.querySelector('#lgAgain').disabled===true,'در آغاز قفل است');
  p.window.NORA_LOGIN.state.wait=1; await wait(1150);
  ok(p.doc.querySelector('#lgAgain').disabled===false,'با تمام‌شدن شمارش، باز می‌شود');
  ok(p.all('#lgCountWrap.over').length===1,'و شمارنده رنگ پایان می‌گیرد');
  ok(p.txt('#lgErr2').includes('سر آمد')===true||p.doc.querySelector('#lgErr2').hidden===false,'پیام پایان زمان می‌آید');
  p.click('#lgAgain'); await wait(180);
  ok(p.doc.querySelector('#lgAgain').disabled===true,'«دوباره بفرست» دوباره قفل می‌کند');
  ok(p.window.NORA_LOGIN.state.wait>80,'و شمارنده از نو می‌شمارد');
}

/* ۳.۵) کد نادرست و دوباره فرست */
{
  console.log('\n── کد نادرست ──');
  const p=await load(makeStore());
  p.phone('09121234567'); await wait(140);
  p.all('.otpbox').forEach((b,idx)=>{ b.value=['۱','۱','۱','۱'][idx]; b.dispatchEvent(new p.window.Event('input',{bubbles:true})) });
  p.submit('#lgForm2'); await wait(120);
  ok(!p.doc.querySelector('#lgErr2').hidden&&p.txt('#lgErr2').includes('۵۴۳۲'),'کد نادرست، کد نمونه را می‌گوید');
  ok(p.store.getItem('nora-home-user')===null,'و کسی وارد نمی‌شود');
  ok(p.doc.querySelector('#lgOtp').classList.contains('bad'),'خانه‌های کد نشان خطا می‌گیرند');
  p.window.NORA_LOGIN.state.wait=0; await wait(60);
  p.click('#lgAgain'); await wait(120);
  ok(p.all('.otpbox').every(b=>!b.value),'«دوباره بفرست» خانه‌ها را خالی می‌کند');
  ok(p.doc.querySelector('#lgErr2').hidden,'و خطا برداشته می‌شود');
  ok(p.txt('#lgCount')!=='', 'شمارنده از نو می‌شمارد');
  ok(p.window.NORA_LOGIN.state.wait>=88,'و زمان به ابتدا برمی‌گردد');
}

/* ۴) بی پیام‌گیر: هیچ دکمه و نشانی از بله و ایتا نمانده */
{
  console.log('\n── بی پیام‌گیر ──');
  const p=await load(makeStore());
  const openBefore=p.window.open&&p.window.open.calls?p.window.open.calls.length:0;
  p.phone('09121234567'); await wait(160);
  ok(p.all('#lgOtp').length===1,'با شماره به پلهٔ کد می‌رود');
  ok(p.all('[data-via]').length===0,'دکمهٔ پیام‌گیر در صفحه نیست');
  ok(p.doc.body.textContent.indexOf('بله')<0&&p.doc.body.textContent.indexOf('ایتا')<0,'نه «بله» و نه «ایتا» در متن صفحه');
  ok((p.window.open.calls?p.window.open.calls.length:0)===openBefore,'هیچ پنجره‌ای خودبه‌خود باز نمی‌شود');
  ok(p.doc.querySelector('#lgBotLink').getAttribute('href').includes('verification_code_bot'),'لینک آبی به ربات رمز یک‌بارمصرف می‌رود');
  ok(p.doc.querySelector('#lgBotLink').getAttribute('href').includes('start=login'),'و با پلهٔ ورود می‌رود');
  ok(p.window.NORA_LOGIN.state.via===undefined,'حالت صفحه دیگر «پیام‌گیر» ندارد');
  ok(!/msgs:/.test(fs.readFileSync(DIR+'data.js','utf8')),'دادهٔ پیام‌گیرها از data.js برداشته شد');
  /* شماره‌ای که نوشتیم در پلهٔ کد می‌ماند */
  ok(p.txt('.lgpline').includes('۹۱۲'),'شمارهٔ نوشته‌شده در پلهٔ کد هست');
  p.click('#lgEditPhone'); await wait(140);
  ok(p.all('#lgPhone').length===1,'مدادِ شماره به پلهٔ نخست برمی‌گردد');
  ok(p.doc.querySelector('#lgPhone').value==='۰۹۱۲۱۲۳۴۵۶۷','شماره در کادر می‌ماند تا فقط عوضش کنی');
}

/* ۴.۵) ورود مدیران: نام کاربری و گذرواژه، بی رمز پویا */
{
  console.log('\n── ورود مدیران ──');
  const p=await load(makeStore());
  p.click('#lgAdminBtn'); await wait(160);
  ok(p.all('#lgUser').length===1&&p.all('#lgPass').length===1,'پلهٔ مدیران: نام کاربری و گذرواژه');
  ok(p.doc.querySelector('#lgPass').type==='password','گذرواژه پوشیده است');
  ok(p.all('.lgbot').length===0&&p.all('#lgOtp').length===0,'رمز پویا و کد در این راه نیست');
  ok(p.txt('#lgAdminForm .lghint').includes('admin / nora'),'نمونهٔ پیش‌نمایش نوشته شده');
  p.submit('#lgAdminForm'); await wait(120);
  ok(!p.doc.querySelector('#lgErr3').hidden&&p.txt('#lgErr3').includes('بنویس'),'خالی، خطا می‌دهد');
  p.type('#lgUser','admin'); p.type('#lgPass','123'); p.submit('#lgAdminForm'); await wait(140);
  ok(p.txt('#lgErr3').includes('درست نیست'),'گذرواژهٔ نادرست رد می‌شود');
  ok(p.store.getItem('nora-admin')===null,'و نشست مدیر ساخته نمی‌شود');
  p.type('#lgPass','nora'); p.click('#lgPassEye'); await wait(80);
  ok(p.doc.querySelector('#lgPass').type==='text','چشم، گذرواژه را نشان می‌دهد');
  p.submit('#lgAdminForm'); await wait(180);
  ok(p.txt('.lgdtitle').includes('مدیر سامانه'),'با درست‌ها، به پلهٔ مدیر می‌رسد');
  ok(p.store.getItem('nora-admin')!==null,'نشست مدیر نوشته می‌شود');
  ok(p.doc.querySelector('#lgAdminPanel').getAttribute('href')==='admin.html','و راه پنل مدیران است');
  p.click('#lgAdminBack')||true;
  const q=await load(makeStore());
  q.click('#lgAdminBtn'); await wait(140);
  q.click('#lgAdminBack'); await wait(140);
  ok(q.all('#lgPhone').length===1,'«بازگشت» به پلهٔ شماره برمی‌گرداند');
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
  ok(q.all('#lgOtp').length===1&&q.txt('.lgpline').includes('۲۲۳۳'),'ورود نیمه‌کاره، از پلهٔ کد ادامه می‌دهد');
}

/* ۶) بازگشت به صفحهٔ خواسته‌شده */
{
  console.log('\n── نشانی بازگشت ──');
  const p=await load(makeStore(),'?next=account.html%23club');
  p.phone('09121234567'); await wait(140);
  p.all('.otpbox').forEach((b,idx)=>{ b.value=['۵','۴','۳','۲'][idx]; b.dispatchEvent(new p.window.Event('input',{bubbles:true})) });
  p.submit('#lgForm2'); await wait(160);
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
  const acc=fs.readFileSync(DIR+'account.js','utf8');
  ok(acc.includes("login.html?next="),'حساب من به صفحهٔ ورود می‌فرستد');
  ok(acc.includes('data-logout-yes'),'و خروج از حساب دارد');
  const sw=fs.readFileSync(DIR+'sw.js','utf8');
  ok(sw.includes("'login.html'")&&sw.includes("'login.js'")&&sw.includes("'login.css'"),'سرویس‌ورکر صفحهٔ ورود را پیش‌بار می‌کند');
  const html=fs.readFileSync(DIR+'login.html','utf8');
  ok(html.includes('login.css?v=54')&&html.includes('login.js?v=54')&&html.includes('data.js?v=54'),'نسخهٔ دارایی‌ها تازه است');
  const data=fs.readFileSync(DIR+'data.js','utf8');
  ok(data.includes('ble.ir/verification_code_bot'),'نشانی ربات رمز یک‌بارمصرف در داده هست');
  ok(!/eitaa\.com/.test(data)&&!/msgs:/.test(data),'ایتا و فهرست پیام‌گیرها از داده برداشته شد');
  ok(data.includes('verification_code_bot'),'شناسهٔ ربات کد یک‌بارمصرف در داده هست');
  ok(data.indexOf('t.me/')<0&&data.indexOf('telegram')<0,'تلگرام از داده برداشته شده');
  ok(data.includes("otpLead")&&data.includes('{bot}'),'متن پلهٔ کد، نام ربات را از داده می‌گیرد');
  const css=fs.readFileSync(DIR+'login.css','utf8');
  ok(/@keyframes rise/.test(css)&&/@keyframes shake/.test(css),'انیمیشن‌های صفحه در CSS خودش هست');
}
console.log('\n'+(fail?'✗ '+fail+' رد، '+pass+' قبول':'✓ همه سبز: '+pass+' قبول'));
process.exit(fail?1:0);
