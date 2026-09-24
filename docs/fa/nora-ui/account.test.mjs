/* ══════════════════════════════════════════════════════════════════════════
   نورا — آزمون صفحهٔ «حساب من» (account.html)
   ──────────────────────────────────────────────────────────────────────────
   چه چیزی می‌سنجد:
   • مهمان: کارت ورود، بخش‌های شخصی پنهان، میان‌برها و «در راه»
   • عضو: سرِ حساب از خود داده، نوار تکمیل، سه پلهٔ تأیید، نردبان سطح
   • ویرایش: قفل شمارهٔ تماس، اعتبارسنجی کد ملی (چک‌سام) و تاریخ شمسی،
     ذخیرهٔ پیش‌نویس و ارسال برای تأیید، سابقهٔ پله‌ها
   • پاک‌سازی: نام تزریقی، دادهٔ خراب، نشانی شکسته
   اجرا:  node account.test.mjs      (با سیم‌لینک node_modules همین پوشه)
   ══════════════════════════════════════════════════════════════════════════ */
import jsdom from 'jsdom';
import fs from 'fs';
const {JSDOM}=jsdom;
const DIR=new URL('./',import.meta.url).pathname;
const OPEN=DIR+'account.html';
const URLF='file://'+OPEN;

let pass=0, fail=0;
const ok=(c,m)=>{ if(c){pass++; console.log('   ✓ '+m)} else {fail++; console.log('   ✗ '+m)} };

/* حافظهٔ مرورگر ساختگی، تا هر بار از صفر شروع شود */
function makeStore(init){
  const m=new Map(Object.entries(init||{}));
  return {getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k),
    clear:()=>m.clear(),key:i=>[...m.keys()][i],get length(){return m.size},_m:m};
}

async function load(store){
  const errs=[];
  const dom=await JSDOM.fromFile(OPEN,{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,url:URLF,
    beforeParse(w){
      w.scrollTo=()=>{}; if(w.Element&&!w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView=()=>{};
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      if(store) Object.defineProperty(w,'localStorage',{configurable:true,value:store});
      w.addEventListener('error',e=>errs.push('error: '+(e.message||''))); w.onerror=m=>errs.push('onerror: '+m);
      const ce=w.console.error; w.console.error=(...a)=>errs.push('console.error: '+a.join(' '));
    }});
  await new Promise(r=>setTimeout(r,700));
  const {window}=dom, doc=window.document;
  return {dom,window,doc,errs,
    click:sel=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel);
      el.dispatchEvent(new window.MouseEvent('click',{bubbles:true}))},
    set:(sel,v)=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel); el.value=v},
    txt:sel=>{const el=doc.querySelector(sel); return el?el.textContent.replace(/\s+/g,' ').trim():''},
    all:sel=>[...doc.querySelectorAll(sel)],
    open:()=>[...doc.querySelectorAll('.sheet.on')].map(e=>e.id)};
}
const MEMBER={name:'سارا محمدی',mobile:'09121234567',joined:'شهریور ۱۴۰۴',wallet:2340000};
const session=()=>({'nora-home-user':JSON.stringify(MEMBER)});

/* ── ۱) مهمان ── */
{
  console.log('\n── مهمان ──');
  const p=await load(makeStore());
  ok(p.errs.length===0,'بی‌خطا بار می‌شود'+(p.errs.length?': '+p.errs.slice(0,2).join(' | '):''));
  ok(p.txt('#headBox').includes('وارد نشده‌ای'),'کارت ورود به‌جای سرِ حساب');
  ok(p.doc.querySelector('#secInfo').hidden && p.doc.querySelector('#secFlow').hidden &&
     p.doc.querySelector('#secLevel').hidden && p.doc.querySelector('#secPrivacy').hidden,'بخش‌های شخصی پنهان‌اند');
  ok(!p.doc.querySelector('#secRoad').hidden && p.all('#roadBox .rchip').length===6,'«در راه» با شش بخش فاز بعد');
  ok(p.all('.tabbar a').length===3 && p.doc.querySelector('.tabbar a[href="account.html"]').getAttribute('aria-current')==='page',
     'تب‌بار سه‌تایی و «حساب من» تب جاری');
  ok(p.doc.querySelector('.brand .mark')!==null && p.doc.querySelector('.topbar .mark')!==null,'نشان نورا در نوار بالا');
  p.click('[data-login]'); await new Promise(r=>setTimeout(r,120));
  ok(p.open().includes('shAuth'),'دکمهٔ ورود، ورقهٔ ورود مشترک را باز می‌کند');
}

/* ── ۲) عضو ── */
const st=makeStore(session());
{
  console.log('\n── عضو ──');
  const p=await load(st);
  ok(p.errs.length===0,'بی‌خطا بار می‌شود'+(p.errs.length?': '+p.errs.slice(0,2).join(' | '):''));
  const h=p.txt('#headBox');
  ok(h.includes('سارا محمدی') && h.includes('تأیید شده'),'سرِ حساب: نام و نشان وضعیت');
  ok(h.includes('شهریور ۱۴۰۴'),'تاریخ عضویت از نشست خوانده می‌شود');
  ok(h.includes('نقره‌ای') && h.includes('۲٬۴۵۰'),'سطح و امتیاز از دادهٔ نورا می‌آید');
  ok(h.includes('مانده'),'فاصله تا سطح بعدی شمرده می‌شود');
  ok(p.txt('#infoBody').includes('کد ملی') && p.txt('#infoBody').includes('ثبت نشده'),'فیلد خالی «ثبت نشده» می‌شود');
  ok(p.txt('#infoBody').includes('تأییدشده'),'شمارهٔ تماس نشان تأیید دارد');
  ok(p.txt('#infoBody').includes('۰۹۱۲۱۲۳۴۵۶۷'),'شمارهٔ تماس در نما با رقم فارسی');
  ok(p.doc.querySelector('.meter i').style.width==='78%','نوار تکمیل ۷۸٪ برای نمونهٔ داده');
  ok(h.includes('کد ملی') && h.includes('نشانی'),'موردهای مانده روی سرِ حساب نوشته می‌شود');
  ok(p.all('#quickBox .srow').length===6,'شش میان‌بر در «کارهای من»');
  ok(p.all('#flowSteps .step').length===3,'سه پلهٔ تأیید پروفایل');
  ok(p.all('#ladder .lvrow').length===4 && p.all('#ladder .lvrow.on').length===1,'نردبان چهار سطح با یک سطح جاری');
  ok(p.txt('#ladder').includes('نقره‌ای') && p.txt('#ladder').includes('امتیاز'),'نام سطح و حد امتیاز در نردبان');
  ok(p.all('#quickBox [data-goto]').every(b=>/\.html/.test(b.dataset.goto)),'میان‌برها به صفحه‌های واقعی می‌روند');
  ok(!p.doc.querySelector('#delBtn').disabled,'دکمهٔ حذف حساب روشن است');
}

/* ── ۳) ویرایش، اعتبارسنجی و ارسال ── */
{
  console.log('\n── ویرایش و تأیید ──');
  const p=await load(st);
  p.click('#editBtn'); await new Promise(r=>setTimeout(r,60));
  ok(p.doc.querySelector('#f_fullName').value==='سارا محمدی','مقدار فعلی در فرم می‌آید');
  ok(p.doc.querySelector('#f_phone').hasAttribute('readonly'),'شمارهٔ تماس قفل است');
  ok(p.all('#infoCard input').length===9,'هر ۹ فیلد حساب در فرم است');
  /* اعتبارسنجی: نام خالی، کد ملی کوتاه و تاریخ بی‌قالب */
  p.set('#f_fullName',''); p.set('#f_nationalId','123'); p.set('#f_birthDate','۱۳۷۰');
  p.click('#sendBtn'); await new Promise(r=>setTimeout(r,90));
  ok(p.all('#infoCard .fld.bad').length>=3,'سه فیلد نادرست هم‌زمان علامت می‌خورد');
  ok(p.doc.querySelector('#f_nationalId').getAttribute('aria-invalid')==='true','فیلد نادرست aria-invalid دارد');
  ok(p.window.localStorage.getItem('nora-home-profile')===null,'با خطا چیزی ذخیره نمی‌شود');
  ok(p.txt('#toast').includes('ببین'),'پیام خطا کاربر را راهنمایی می‌کند');
  /* کد ملی با ۱۰ رقم ولی چک‌سام غلط */
  p.set('#f_fullName','سارا محمدی'); p.set('#f_birthDate','1378/05/12'); p.set('#f_nationalId','1111111111');
  p.click('#sendBtn'); await new Promise(r=>setTimeout(r,70));
  ok(p.txt('#infoCard').includes('درست نیست'),'کد ملی بی‌چک‌سام رد می‌شود');
  /* مقدار درست */
  p.set('#f_nationalId','۰۰۷۹۵۴۳۹۴۴'); p.set('#f_address','خیابان ولی‌عصر، پلاک ۱۲');
  p.click('#sendBtn'); await new Promise(r=>setTimeout(r,160));
  const saved=JSON.parse(p.window.localStorage.getItem('nora-home-profile')||'{}');
  ok(saved.status==='pending','بعد از ارسال، وضعیت «در صف تأیید» می‌شود');
  ok(saved.nationalId==='0079543944','رقم فارسی ورودی، لاتین ذخیره می‌شود');
  ok(saved.birthDate==='1378/05/12','تاریخ تولد با قالب ثابت ذخیره می‌شود');
  ok(saved.phone==='09121234567','شمارهٔ تماس از حساب می‌آید، نه از فرم');
  ok(saved.history.some(x=>x.k==='pending'),'سابقهٔ پلهٔ تأیید ثبت می‌شود');
  ok(p.doc.querySelector('#f_fullName')===null,'بعد از ذخیره، فرم بسته می‌شود');
  ok(p.txt('#headBox').includes('در صف تأیید'),'سرِ حساب وضعیت تازه را نشان می‌دهد');
  ok(p.txt('#flowSteps').includes('در صف تأیید') && p.all('#flowSteps .step.done').length>=1,'پله‌های تأیید تازه می‌شوند');
  ok(p.txt('#toast').includes('تأیید'),'پیام ارسال برای تأیید');
  ok(p.txt('#infoBody').includes('۱۳۷۸/۰۵/۱۲'),'تاریخ در نما با رقم فارسی');
  ok(p.txt('#infoBody').includes('۰۰۷۹۵۴۳۹۴۴'),'کد ملی در نما با رقم فارسی');
  /* پیش‌نویس */
  p.click('#editBtn'); await new Promise(r=>setTimeout(r,50));
  p.set('#f_email','sara@nora.ir');
  p.click('#draftBtn'); await new Promise(r=>setTimeout(r,140));
  const d2=JSON.parse(p.window.localStorage.getItem('nora-home-profile')||'{}');
  ok(d2.email==='sara@nora.ir' && d2.status==='pending','«فقط ذخیره» وضعیت را خراب نمی‌کند');
  /* دانلود اطلاعات من */
  ok(p.doc.querySelector('#secPrivacy .srow')!==null && p.all('#secPrivacy .srow').length===2,'حریم خصوصی: دانلود و حذف');
  p.window.URL.createObjectURL=()=>'blob:nora'; p.window.URL.revokeObjectURL=()=>{};
  p.click('#dlBtn'); await new Promise(r=>setTimeout(r,80));
  ok(p.txt('#toast').includes('آماده'),'دانلود اطلاعات من فایل می‌سازد');
  /* حذف حساب: سه پلهٔ سند — تأیید، تایپ «حذف»، کد پیامکی */
  const asked=()=>!!JSON.parse(p.window.localStorage.getItem('nora-home-profile')||'{}').askedDelete;
  p.click('#delBtn'); await new Promise(r=>setTimeout(r,90));
  ok(p.open().includes('shConfirm'),'ورقهٔ تأیید حذف باز می‌شود');
  ok(p.doc.querySelector('#delWord')!==null && p.doc.querySelector('#delCode')!==null,'کلمهٔ تأیید و کد پیامکی خواسته می‌شود');
  p.click('[data-close]'); await new Promise(r=>setTimeout(r,70));
  ok(p.open().length===0 && !asked(),'«هنوز نه» ورقه را می‌بندد و چیزی ثبت نمی‌شود');
  p.click('#delBtn'); await new Promise(r=>setTimeout(r,70));
  p.click('#delYes'); await new Promise(r=>setTimeout(r,80));
  ok(!asked() && p.txt('#toast').includes('تأیید'),'بی کلمهٔ تأیید، ثبت نمی‌شود');
  p.set('#delWord','حذف'); p.click('#delYes'); await new Promise(r=>setTimeout(r,80));
  ok(!asked() && p.txt('#toast').includes('۵۴۳۲۱'),'بی کد پیامکی درست، رد می‌شود');
  p.set('#delCode','۵۴۳۲۱'); p.click('#delYes'); await new Promise(r=>setTimeout(r,130));
  const d3=JSON.parse(p.window.localStorage.getItem('nora-home-profile')||'{}');
  ok(d3.askedDelete===true,'با هر سه تأیید، درخواست حذف ثبت می‌شود');
  ok(d3.history.some(x=>x.k==='delete'),'سابقهٔ درخواست حذف ثبت می‌شود');
  ok(p.open().length===0,'ورقه بسته می‌شود');
  ok(p.doc.querySelector('#delBtn').disabled,'دکمهٔ حذف بعد از ثبت خاموش می‌شود');
  ok(p.txt('#delNote').includes('ثبت شده'),'روی کارت نوشته می‌شود که درخواست ثبت شده');
}

/* ── ۴) دادهٔ خراب و امنیت ── */
{
  console.log('\n── دادهٔ خراب ──');
  const p=await load(makeStore(Object.assign(session(),{
    'nora-home-profile':JSON.stringify({fullName:'<img src=x onerror=alert(1)>',status:'عجیب',
      reason:'<b>خطر</b>',history:[{k:'hack',at:'x'},{k:'approved',at:'۸ شهریور'}],extra:'x'})})));
  ok(p.errs.length===0,'دادهٔ آلوده صفحه را نمی‌شکند');
  ok(p.doc.querySelectorAll('img[src="x"]').length===0,'نام تزریقی پاک‌سازی می‌شود');
  ok(p.txt('#headBox').includes('تکمیل نشده'),'وضعیت ناشناس به «تکمیل نشده» برمی‌گردد');
  const links=[...new Set(p.all('[href]').map(a=>a.getAttribute('href')))].filter(h=>h&&!h.startsWith('#')&&!h.startsWith('mailto:')&&!h.startsWith('http'));
  const bad=links.filter(h=>{const f=h.split('?')[0].split('#')[0]; return f && !fs.existsSync(DIR+f)});
  ok(bad.length===0,'نشانی شکسته‌ای در صفحه نیست'+(bad.length?': '+bad.join(', '):''));
  ok(p.doc.querySelector('h1')!==null && /حساب من/.test(p.doc.title),'تیتر صفحه و عنوان سند');
  ok(p.all('meta[property^="og:"]').length>=4 && p.doc.querySelector('link[rel=manifest]')!==null,'متاها و مانیفست سرجایشان‌اند');
}

console.log('\naccount-test: '+pass+' بررسی، '+fail+' خطا');
process.exit(fail?1:0);
