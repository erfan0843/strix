/* ══════════════════════════════════════════════════════════════════════════
   نورا — آزمون صفحهٔ «حساب من» (account.html)
   ──────────────────────────────────────────────────────────────────────────
   چه چیزی می‌سنجد:
   • سرِ حساب و کاشی‌های دوازده‌گانهٔ بخش‌ها
   • رفت‌وبرگشت نشانی‌ها: هر بخش یک نشانی، بازگشت همیشه به سرِ حساب
   • مهمان: دروازهٔ ورود روی بخش‌های عضو، پشتیبانی و درباره باز
   • اطلاعات حساب من: ویرایش، اعتبارسنجی (چک‌سام کد ملی، تاریخ شمسی)، تأیید
   • نمای هر بخش: بلیت و گواهی، باشگاه، کارنامهٔ حضور، دعوت، اعلان‌ها،
     فرم‌ها، نظرها، پشتیبانی، درباره، حریم خصوصی و نورا پی
   • پاک‌سازی: نام تزریقی، دادهٔ خراب، نشانی شکسته، نماد ناموجود
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
const wait=(t=70)=>new Promise(r=>setTimeout(r,t));

function makeStore(init){
  const m=new Map(Object.entries(init||{}));
  return {getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k),
    clear:()=>m.clear(),key:i=>[...m.keys()][i],get length(){return m.size},_m:m};
}
const MEMBER={name:'سارا محمدی',mobile:'09121234567',joined:'شهریور ۱۴۰۴',wallet:2340000};
const session=()=>({'nora-home-user':JSON.stringify(MEMBER)});

async function load(store,hash){
  const errs=[];
  const dom=await JSDOM.fromFile(OPEN,{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,
    url:URLF+(hash||''),
    beforeParse(w){
      w.scrollTo=()=>{}; if(w.Element&&!w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView=()=>{};
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      if(store) Object.defineProperty(w,'localStorage',{configurable:true,value:store});
      w.addEventListener('error',e=>errs.push('error: '+(e.message||''))); w.onerror=m=>errs.push('onerror: '+m);
      const ce=w.console.error; w.console.error=(...a)=>errs.push('console.error: '+a.join(' '));
    }});
  await wait(650);
  const {window}=dom, doc=window.document;
  const p={dom,window,doc,errs,
    click:sel=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel);
      el.dispatchEvent(new window.MouseEvent('click',{bubbles:true}))},
    set:(sel,v)=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel); el.value=v},
    txt:sel=>{const el=doc.querySelector(sel); return el?el.textContent.replace(/\s+/g,' ').trim():''},
    all:sel=>[...doc.querySelectorAll(sel)],
    open:()=>[...doc.querySelectorAll('.sheet.on')].map(e=>e.id),
    nav:async k=>{window.location.hash='#'+k; await wait(90)},
    view:()=>doc.querySelector('#viewBox').textContent.replace(/\s+/g,' ').trim(),
    hub:()=>doc.querySelector('#hubBox').textContent.replace(/\s+/g,' ').trim(),
    inView:!!doc.querySelector('#viewBox')&&!doc.querySelector('#viewBox').hidden};
  return p;
}
/* بخش‌های معماری، همان چیزی که data.js می‌گوید */
const SEC=(await import('fs')).readFileSync(DIR+'data.js','utf8')
  .match(/sections:\[([\s\S]*?)\n  \],/)[1].match(/\{k:'([a-z]+)'/g).map(x=>x.slice(4,-1));

/* ── ۱) سرِ حساب و کاشی‌ها ── */
{
  console.log('\n── سرِ حساب و بخش‌ها ──');
  const p=await load(makeStore(session()));
  ok(p.errs.length===0,'بی‌خطا بار می‌شود'+(p.errs.length?': '+p.errs.slice(0,2).join(' | '):''));
  const h=p.hub();
  ok(h.includes('سارا محمدی') && h.includes('تأیید شده') && h.includes('نقره‌ای'),'سرِ حساب: نام، وضعیت و سطح');
  ok(h.includes('۲٬۴۵۰') && h.includes('تا سطح طلایی'),'امتیاز و فاصله تا سطح بعدی');
  ok(p.doc.querySelector('.meter i').style.width==='78%','نوار تکمیل اطلاعات: ٪۷۸');
  ok(SEC.length===12,'معماری دوازده بخش دارد: '+SEC.length);
  ok(p.all('#tilesBox .tile').length===SEC.length,'هر بخش یک کاشی روی سرِ حساب');
  ok(p.all('#tilesBox .tile[data-view]').map(b=>b.dataset.view).join('|')===SEC.join('|'),'ترتیب و نشانی کاشی‌ها درست است');
  ok(p.all('#tilesBox .tile.next').length===1 && p.txt('#tilesBox .tile.next').includes('نورا پی'),'نورا پی کاشی «فاز بعد» است');
  ok(p.hub().includes('اطلاعات حساب من') && p.all('#ladder .lvrow').length===4,'اطلاعات حساب و نردبان سطح سرجایشان');
  ok(p.doc.querySelector('#viewBox').hidden,'نما پنهان است تا بخشی باز شود');
  ok(p.doc.title==='نورا · حساب من','عنوان سند روی سرِ حساب');
}

/* ── ۲) نشانی‌ها و بازگشت ── */
{
  console.log('\n── نشانی بخش‌ها ──');
  const p=await load(makeStore(session()),'#club');
  ok(!p.doc.querySelector('#hubBox').hidden===false || !p.inView,'با نشانی #club نما باز می‌شود');
  ok(p.inView && p.txt('#viewBox').includes('باشگاه من'),'نمای باشگاه از نشانی خوانده می‌شود');
  ok(p.doc.title==='نورا · باشگاه من','عنوان سند با بخش عوض می‌شود');
  p.click('[data-back]'); await wait(90);
  ok(!p.doc.querySelector('#viewBox').hidden===false,'بازگشت، نما را می‌بندد');
  ok(!p.doc.querySelector('#hubBox').hidden,'سرِ حساب برمی‌گردد');
  await p.nav('چیز-نامعلوم'); await wait(60);
  ok(p.doc.querySelector('#viewBox').hidden && p.txt('#toast').includes('برگشتیم'),'نشانی ناشناس به سرِ حساب برمی‌گردد');
  /* همهٔ بخش‌ها یک به یک */
  const empty=[];
  for(const k of SEC){
    await p.nav(k); await wait(80);
    if(!p.inView || p.view().length<30) empty.push(k);
  }
  ok(empty.length===0,'هر دوازده بخش نما و متن دارد'+(empty.length?': '+empty.join(', '):''));
}

/* ── ۳) مهمان: دروازه‌ها ── */
{
  console.log('\n── مهمان ──');
  const p=await load(makeStore());
  ok(p.hub().includes('وارد نشده‌ای'),'کارت ورود روی سرِ حساب');
  const locked=p.all('#tilesBox .tile').filter(b=>/با ورود باز می‌شود/.test(b.textContent)).length;
  ok(locked===SEC.length-2,'بخش‌های عضو برای مهمان قفل‌اند: '+locked+' از '+SEC.length);
  await p.nav('tickets'); await wait(80);
  ok(p.view().includes('با حساب خودت باز می‌شود'),'نمای عضو برای مهمان دروازه می‌دهد');
  p.click('#viewBox [data-login]'); await wait(120);
  ok(p.open().includes('shAuth'),'دکمهٔ دروازه، ورقهٔ ورود می‌آورد');
  p.click('#scrim'); await wait(60);
  await p.nav('support'); await wait(80);
  ok(p.view().includes('راه‌های تماس') && p.all('#viewBox .srow a.btn').length===4,'پشتیبانی برای مهمان باز است');
  await p.nav('about'); await wait(80);
  ok(p.view().includes('گروه فرهنگی خط زندگی') && p.view().includes('ولی‌عصر'),'دربارهٔ نورا برای مهمان باز است');
}

/* ── ۴) اطلاعات حساب من ── */
const st=makeStore(session());
{
  console.log('\n── اطلاعات حساب من ──');
  const p=await load(st);
  ok(p.txt('#infoBody').includes('ثبت نشده') && p.txt('#infoBody').includes('تأییدشده'),'فیلد خالی و شمارهٔ تأییدشده');
  ok(p.txt('#infoBody').includes('۰۹۱۲۱۲۳۴۵۶۷'),'شمارهٔ تماس در نما با رقم فارسی');
  ok(p.all('#flowSteps .step').length===3,'سه پلهٔ تأیید پروفایل');
  p.click('#editBtn'); await wait(60);
  ok(p.all('#infoCard input').length===9 && p.doc.querySelector('#f_phone').hasAttribute('readonly'),'نه فیلد، شمارهٔ قفل');
  p.set('#f_fullName',''); p.set('#f_nationalId','123'); p.set('#f_birthDate','۱۳۷۰');
  p.click('#sendBtn'); await wait(90);
  ok(p.all('#infoCard .fld.bad').length>=3 && p.window.localStorage.getItem('nora-home-profile')===null,'خطاها می‌نشینند و چیزی ذخیره نمی‌شود');
  p.set('#f_fullName','سارا محمدی'); p.set('#f_birthDate','1378/05/12'); p.set('#f_nationalId','1111111111');
  p.click('#sendBtn'); await wait(80);
  ok(p.txt('#infoCard').includes('درست نیست'),'کد ملی بی‌چک‌سام رد می‌شود');
  p.set('#f_nationalId','۰۰۷۹۵۴۳۹۴۴'); p.click('#sendBtn'); await wait(150);
  const saved=JSON.parse(p.window.localStorage.getItem('nora-home-profile')||'{}');
  ok(saved.status==='pending' && saved.nationalId==='0079543944' && saved.birthDate==='1378/05/12','ذخیره، یکدست‌سازی و ارسال برای تأیید');
  ok(saved.phone==='09121234567','شمارهٔ تماس از حساب می‌آید');
  ok(p.txt('#headBox').includes('در صف تأیید') && p.txt('#flowSteps').includes('در صف تأیید'),'وضعیت تازه در سرِ حساب');
}

/* ── ۵) رویدادهای من ── */
{
  console.log('\n── رویدادهای من ──');
  const p=await load(makeStore(session()),'#events');
  ok(p.all('#viewBox .vtab').length===3,'سه تب: پیشرو، برگزارشده، لغوشده');
  ok(p.all('#viewBox .erow').length===3,'سه ثبت‌نام پیش‌رو');
  ok(p.txt('#viewBox').includes('کارت ورود') && p.all('#viewBox [data-cancel-ev]').length===3,'کارت ورود و لغو روی هر ردیف');
  p.click('#viewBox [data-vtab="past"]'); await wait(90);
  ok(p.all('#viewBox .erow').length===2 && p.txt('#viewBox').includes('حضور ثبت شد'),'تب برگزارشده‌ها');
  p.click('#viewBox [data-vtab="cancel"]'); await wait(90);
  ok(p.view().includes('لغوشده‌ای نداری'),'تب لغوشده‌ها حالت خالی دارد');
  p.click('#viewBox [data-vtab="up"]'); await wait(90);
  p.click('#viewBox [data-cancel-ev="e1"]'); await wait(80);
  ok(p.open().includes('shConfirm'),'لغو ثبت‌نام ورقهٔ تأیید می‌آورد');
  p.click('[data-cancel-yes="e1"]'); await wait(90);
  ok(p.txt('#toast').includes('لغو شد'),'لغو ثبت‌نام ثبت می‌شود');
  p.click('#viewBox [data-view="tickets"]'); await wait(100);
  ok(p.inView && p.view().includes('بلیت و گواهی'),'از رویدادها به بلیت و گواهی می‌رود');
}

/* ── ۶) بلیت و گواهی ── */
{
  console.log('\n── بلیت و گواهی ──');
  const p=await load(makeStore(session()),'#tickets');
  const v=p.view();
  ok(p.doc.querySelector('#viewBox .idcard')!==null,'کارت ورود ساخته می‌شود');
  ok(v.includes('NL-4567') && v.includes('۰۹۱۲۱۲۳۴۵۶۷'),'کد عضویت و شمارهٔ تماس روی کارت');
  ok(p.all('#viewBox .tk').length===1 && v.includes('کارگاه عکاسی مقدماتی'),'گواهی خودِ عضو پیدا می‌شود');
  ok(p.all('#viewBox .kind').length===4 && v.includes('چاپی') && v.includes('VIP'),'چهار گونهٔ گواهی');
  ok(v.includes('۲۴ ماه'),'اعتبار پیش‌فرض گواهی');
  p.window.URL.createObjectURL=()=>'blob:nora'; p.window.URL.revokeObjectURL=()=>{};
  p.click('#viewBox [data-cert-dl]'); await wait(80);
  ok(p.txt('#toast').includes('گواهی'),'دانلود گواهی فایل می‌سازد');
  p.click('#viewBox [data-cert-req="print"]'); await wait(80);
  ok(p.open().includes('shConfirm') && p.txt('#shConfirm').includes('سرپرست'),'سفارش گواهی چاپی با تأیید سرپرست');
  p.click('#shConfirm [data-cert-yes]'); await wait(80);
  ok(p.txt('#toast').includes('سفارش ثبت شد'),'سفارش گواهی ثبت می‌شود');
  p.click('#viewBox [data-cert-req="free"]'); await wait(70);
  ok(!p.open().includes('shConfirm'),'گواهی رایگان ورقه باز نمی‌کند');
}

/* ── ۷) باشگاه من ── */
{
  console.log('\n── باشگاه من ──');
  const p=await load(makeStore(session()),'#club');
  const v=p.view();
  ok(p.all('#viewBox .stat2').length===4 && v.includes('۲٬۴۵۰'),'چهار عدد: امتیاز، سطح، فاصله، رتبه');
  ok(v.includes('رتبهٔ شهریور ۱۴۰۵') && v.includes('از ۳۴۰'),'رتبهٔ ماهانه از داده');
  ok(p.all('#viewBox .lvrow').length===4,'نردبان چهار سطح');
  ok(p.all('#viewBox .ack').length===8 && p.all('#viewBox .ack.on').length===4,'هشت دستاورد، چهار گرفته‌شده');
  ok(p.all('#viewBox .kind').length===2 && v.includes('کد تخفیف ٪۵') && v.includes('۸۰۰'),'فروشگاه پاداش با قیمت امتیازی');
  ok(p.all('#viewBox [data-reward]').filter(b=>!b.hasAttribute('disabled')).length===2,'با ۲٬۴۵۰ امتیاز، هر دو جایزه باز است');
  ok(v.includes('روزانه تا ۵۰') && v.includes('ماهانه تا ۳۰۰'),'سقف‌های محافظ امتیاز');
  p.click('#viewBox [data-reward]'); await wait(70);
  ok(p.txt('#toast').includes('امتیازت'),'جایزه پیام می‌دهد');
}

/* ── ۸) کارنامهٔ حضور ── */
{
  console.log('\n── کارنامهٔ حضور ──');
  const p=await load(makeStore(session()),'#attend');
  ok(p.all('#viewBox .bars i').length===12,'دوازده ستون ماهانه');
  ok(p.all('#viewBox .bars i.off').length===2,'دو ماه زیر ٪۶۰ کم‌رنگ می‌شوند');
  ok(p.view().includes('درصد حضور') && p.view().includes('۲۲'),'عددهای کارنامه');
  ok(p.all('#viewBox .tk').length===5 && p.txt('#viewBox').includes('غیبت'),'پنج جلسهٔ آخر با وضعیت');
}

/* ── ۹) دعوت دوستان ── */
{
  console.log('\n── دعوت دوستان ──');
  const p=await load(makeStore(session()),'#invite');
  const v=p.view();
  ok(v.includes('NORA-4567'),'کد دعوت از شمارهٔ حساب ساخته می‌شود');
  ok(v.includes('دعوت ۲ دوست') && v.includes('۱ از ۲'),'قفل عضویت با نیاز دو دعوت');
  ok(v.includes('عضویت در کانال نورا') && v.includes('انجام شد'),'کانال، انجام‌شده نشان می‌دهد');
  p.click('#viewBox [data-copy]'); await wait(80);
  ok(p.txt('#toast').includes('کپی'),'کپی کد دعوت پیام می‌دهد');
}

/* ── ۱۰) اعلان‌ها ── */
{
  console.log('\n── اعلان‌ها ──');
  const p=await load(makeStore(session()),'#notices');
  ok(p.all('#viewBox .vtab').length===6,'یک تب «همه» و پنج دستهٔ اعلان');
  ok(p.all('#viewBox .tk').length===3,'اعلان‌ها فهرست می‌شوند');
  ok(p.view().includes('خوانده‌نشده'),'وضعیت خوانده‌نشده نشان می‌شود');
  ok(p.all('#viewBox [data-chan]').length===4,'چهار کانال اعلان');
  p.click('#viewBox [data-chan="بله"]'); await wait(80);
  const ch=JSON.parse(p.window.localStorage.getItem('nora-account-notify')||'[]');
  ok(!ch.includes('بله') && p.txt('#toast').includes('خاموش'),'خاموش‌کردن کانال در حافظه می‌ماند');
  p.click('#viewBox [data-ncat="گواهی"]'); await wait(80);
  ok(p.all('#viewBox .tk').length===1,'دستهٔ گواهی فیلتر می‌کند');
  p.click('#viewBox [data-ncat="پشتیبانی"]'); await wait(80);
  ok(p.all('#viewBox .tk').length===0 && p.view().includes('در این دسته چیزی نیست'),'دستهٔ بی‌اعلان، حالت خالی دارد');
  p.click('#viewBox [data-ncat="همه"]'); await wait(80);
  p.click('#viewBox [data-vread]'); await wait(90);
  ok(!p.doc.querySelector('#bellBadge') || p.doc.querySelector('#bellBadge').hidden,'خواندن همه، نشان زنگ را برمی‌دارد');
}

/* ── ۱۱) فرم‌ها، نظرها، پشتیبانی، درباره، نورا پی ── */
{
  console.log('\n── فرم، نظر، پشتیبانی، درباره، نورا پی ──');
  const p=await load(makeStore(session()),'#forms');
  ok(p.all('#viewBox .tk').length===3 && p.txt('#viewBox').includes('پیش‌نویس'),'سه فرم با وضعیت');
  ok(p.view().includes('۹ گونه'),'انواع فرم از قواعد خوانده می‌شود');
  p.click('#viewBox [data-form-new]'); await wait(70);
  ok(p.txt('#toast').includes('کارشناس فرم'),'فرم تازه پیام می‌دهد');
  await p.nav('reviews'); await wait(80);
  ok(p.all('#viewBox .tk').length===2 && p.view().includes('★'),'دو نظر با ستاره');
  await p.nav('support'); await wait(80);
  ok(p.all('#viewBox .srow a.btn').length===4,'چهار راه تماس');
  ok(p.view().includes('حسن مقدم') && p.view().includes('۱ از ۳'),'تیکت باز با پاسخ‌دهنده');
  ok(p.all('#viewBox .chipsline .tag').length===6,'شش دستهٔ تیکت');
  p.click('#viewBox [data-ticket-new]'); await wait(70);
  ok(p.txt('#toast').includes('تیکت'),'تیکت تازه پیام می‌دهد');
  await p.nav('about'); await wait(80);
  ok(p.all('#viewBox .abrow').length===5 && p.view().includes('info@lifeline1.ir'),'پنج ردیف دربارهٔ ما');
  await p.nav('pay'); await wait(80);
  ok(p.view().includes('فعلاً قفل است') && p.view().includes('کیف پول و شارژ'),'نورا پی، نمای قفل با فهرست فاز بعد');
  await p.nav('privacy'); await wait(80);
  ok(p.doc.querySelector('#dlBtn')!==null && p.doc.querySelector('#delBtn')!==null,'حریم خصوصی: دانلود و حذف');
  p.window.URL.createObjectURL=()=>'blob:nora'; p.window.URL.revokeObjectURL=()=>{};
  p.click('#dlBtn'); await wait(80);
  ok(p.txt('#toast').includes('آماده'),'دانلود اطلاعات فایل می‌سازد');
  p.click('#delBtn'); await wait(80);
  ok(p.doc.querySelector('#delWord')!==null && p.doc.querySelector('#delCode')!==null,'حذف حساب سه تأیید می‌خواهد');
  p.click('#delYes'); await wait(70);
  p.set('#delWord','حذف'); p.click('#delYes'); await wait(70);
  ok(p.txt('#toast').includes('۵۴۳۲۱'),'بی کد پیامکی رد می‌شود');
  p.set('#delCode','۵۴۳۲۱'); p.click('#delYes'); await wait(120);
  const d=JSON.parse(p.window.localStorage.getItem('nora-home-profile')||'{}');
  ok(d.askedDelete===true && d.history.some(x=>x.k==='delete'),'درخواست حذف با هر سه تأیید ثبت می‌شود');
  ok(p.txt('#viewBox').includes('ثبت شده'),'کارت حریم خصوصی وضعیت تازه را نشان می‌دهد');
}

/* ── ۱۲) پاک‌سازی و درستی ── */
{
  console.log('\n── پاک‌سازی و درستی ──');
  const p=await load(makeStore(Object.assign(session(),{
    'nora-home-profile':JSON.stringify({fullName:'<img src=x onerror=alert(1)>',status:'عجیب',reason:'<b>خطر</b>',
      history:[{k:'hack',at:'x'},{k:'approved',at:'۸ شهریور'}],extra:'x'})})));
  ok(p.errs.length===0 && p.doc.querySelectorAll('img[src="x"]').length===0,'دادهٔ آلوده صفحه را نمی‌شکند');
  ok(p.txt('#headBox').includes('تکمیل نشده'),'وضعیت ناشناس به «تکمیل نشده» برمی‌گردد');
  /* هر نمادی که صفحه صدا می‌زند، باید در صفحه باشد */
  const syms=new Set(p.all('symbol[id]').map(s=>s.id));
  const used=new Set(), missing=new Set(), links=new Set(), gos=new Set();
  for(const k of SEC){
    await p.nav(k); await wait(70);
    for(const u of p.all('#viewBox use')){ const id=(u.getAttribute('href')||'').slice(1); used.add(id); if(!syms.has(id)) missing.add(id) }
    for(const a of p.all('#viewBox a[href]')) links.add(a.getAttribute('href'));
    for(const g of p.all('#viewBox [data-goto]')) gos.add(g.dataset.goto);
  }
  await p.nav(''); await wait(80);
  for(const u of p.all('#hubBox use,#tilesBox use')){ const id=(u.getAttribute('href')||'').slice(1); used.add(id); if(!syms.has(id)) missing.add(id) }
  ok(missing.size===0,'هر نمادی که صدا زده می‌شود، در صفحه هست'+(missing.size?': '+[...missing].join(', '):''));
  const deep=[...links,...gos].filter(h=>h&&!h.startsWith('http')&&!h.startsWith('tel:')&&!h.startsWith('mailto:'));
  const bad=deep.filter(h=>{const f=h.split('?')[0].split('#')[0]; return f&&!fs.existsSync(DIR+f)});
  ok(bad.length===0,'نشانی شکسته‌ای در بخش‌ها نیست'+(bad.length?': '+bad.join(', '):''));
  ok(p.all('#hubBox [data-view]').length===SEC.length && p.doc.querySelector('#viewBox').hidden,'بازگشت به سرِ حساب سالم است');
  ok(p.txt('body').includes('با همیاری')===false,'متن‌های بیرون‌از‌جا در صفحه نیست');
}

console.log('\naccount-test: '+pass+' بررسی، '+fail+' خطا');
process.exit(fail?1:0);
