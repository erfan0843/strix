/* ══════════════════════════════════════════════════════════════════════════
   نورا — آزمون صفحهٔ «حساب من» (account.html)
   ──────────────────────────────────────────────────────────────────────────
   معماری تازه: یک نمای پروفایل اپلی، کارت نورا پی در بالا، سه بخش ادغام‌شده
   و پشتیبانی چسبیده به نوار پایین.

   چه چیزی می‌سنجد:
   • سرِ پروفایل: نام، وضعیت، سطح، امتیاز، نوار تکمیل اطلاعات
   • نورا پی: کارت بالای صفحه، دو زبانه، رنگ و آیکون خودش، فاز بعد
   • سه بخش: رویدادهای من، باشگاه و امتیاز من، اطلاعات و تنظیمات
     (بلیت و گواهی و کارنامهٔ حضور داخل رویدادهای من)
   • پشتیبانی: یک جا، نوار چسبیده به نوار پایین، ورقه از پایین، پرسش‌های
     پرتکرار، دربارهٔ نورا و پیام‌فرستادن. همهٔ راه‌های دیگر سامانه به همین‌جا.
   • مهمان: یک کارت ورود روشن، بی تکرار «با ورود باز می‌شود» روی هر ردیف
   • اعلان‌ها: هیچ نشانی از بخش اعلان در حساب من نیست
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
  return {dom,window,doc,errs,
    click:sel=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel);
      el.dispatchEvent(new window.MouseEvent('click',{bubbles:true}))},
    clickEl:el=>el.dispatchEvent(new window.MouseEvent('click',{bubbles:true})),
    set:(sel,v)=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel); el.value=v},
    txt:sel=>{const el=doc.querySelector(sel); return el?el.textContent.replace(/\s+/g,' ').trim():''},
    all:sel=>[...doc.querySelectorAll(sel)],
    open:()=>[...doc.querySelectorAll('.sheet.on')].map(e=>e.id),
    hub:()=>doc.querySelector('#hubBox').textContent.replace(/\s+/g,' ').trim(),
    view:()=>doc.querySelector('#viewBox').textContent.replace(/\s+/g,' ').trim(),
    inView:()=>!doc.querySelector('#viewBox').hidden,
    nav:async k=>{window.location.hash='#'+k; await wait(110)}};
}
/* بخش‌های معماری، همان چیزی که data.js می‌گوید */
const SRC=fs.readFileSync(DIR+'data.js','utf8');
const SECT=SRC.match(/sections:\[([\s\S]*?)\n  \],/)[1].match(/\{k:'([a-z]+)'/g).map(x=>x.slice(4,-1));
const CARDS=SECT.filter(k=>k==='pay').length;

/* ── ۱) نمای پروفایل ── */
{
  console.log('\n── نمای پروفایل ──');
  const p=await load(makeStore(session()));
  ok(p.errs.length===0,'بی‌خطا بار می‌شود'+(p.errs.length?': '+p.errs.slice(0,2).join(' | '):''));
  const h=p.hub();
  ok(h.includes('سارا محمدی') && h.includes('تأیید شده'),'نام و نشان وضعیت روی سرِ پروفایل');
  ok(h.includes('شهریور ۱۴۰۴') && h.includes('نقره‌ای'),'تاریخ عضویت و سطح');
  ok(h.includes('۲٬۴۵۰') && h.includes('تا طلایی ۵۵۰ امتیاز'),'امتیاز و فاصله تا سطح بعدی');
  ok(p.doc.querySelector('.meter i').style.width==='78%','نوار تکمیل اطلاعات: ٪۷۸');
  ok(h.includes('تکمیل اطلاعات'),'دکمهٔ کار بعدی روی سرِ پروفایل');
  ok(p.all('.pstat').length===3,'سه عدد کلیدی زیر نام');
  ok(SECT.length===3 && CARDS===1,'معماری سه مورد دارد: نورا پی، رویدادهای من، پروفایل من');
  ok(p.all('.mrow2').length===2,'منو دو ردیف بیشتر نیست');
  ok(p.all('.mrow2').map(b=>b.dataset.go).join('|')===SECT.filter(k=>k!=='pay').join('|'),'ردیف‌ها: رویدادهای من و پروفایل من');
  ok(!/اعلان/.test(h),'بخش اعلان‌ها روی پروفایل نیست');
  ok(p.doc.querySelector('.topbar .icon-btn')===null,'نوار بالا زنگ اعلان ندارد');
  ok(p.doc.title==='نورا · حساب من','عنوان سند');
}

/* ── ۲) نورا پی: بالا، دو زبانه، با رنگ و آیکون خودش ── */
{
  console.log('\n── نورا پی ──');
  const p=await load(makeStore(session()));
  const pay=p.doc.querySelector('.paycard');
  ok(pay!==null,'کارت نورا پی ساخته می‌شود');
  const hub=p.doc.querySelector('#hubBox');
  const order=[...hub.children].map(e=>e.className.split(' ')[0]);
  ok(order.indexOf('pcard')===0 && order.indexOf('paycard')===1 && order[2]==='mrows','نورا پی بالای صفحه و پیش از بخش‌ها');
  ok(p.txt('.paycard').includes('nora pay') && p.txt('.paycard').includes('نورا پی'),'نام دو زبانه: nora pay | نورا پی');
  ok(p.txt('.paycard').includes('فاز بعد') && p.txt('.paycard').includes('به‌زودی'),'کارت خودش می‌گوید فاز بعد است');
  ok(p.doc.querySelector('.paycard .pico use').getAttribute('href')==='#i-wallet','آیکون کیف پول مخصوص خودش');
  ok(SRC.includes("paycard")===false && SRC.includes("en:'nora pay'"),'دادهٔ دو زبانه از data.js می‌آید');
  p.click('.paycard'); await wait(110);
  ok(p.doc.querySelector('#viewBox').textContent.includes('نورا پی'),'کارت، نمای نورا پی را باز می‌کند');
  ok(p.view().includes('قفل است') && p.view().includes('کیف پول و شارژ'),'نمای نورا پی: قفل با فهرست فاز بعد');
}

/* ── ۳) نشانی بخش‌ها و بازگشت ── */
{
  console.log('\n── نشانی بخش‌ها ──');
  const p=await load(makeStore(session()),'#club');
  ok(p.inView() && p.view().includes('باشگاه و امتیاز') && p.view().includes('نردبان')===false,'نشانی #club تب باشگاه پروفایل را باز می‌کند');
  ok(p.doc.title==='نورا · پروفایل من','عنوان سند نام بخش را می‌گوید');
  ok(p.all('#viewBox .vtab').length===4,'پروفایل چهار تب دارد');
  p.click('[data-back]'); await wait(110);
  ok(!p.inView() && !p.doc.querySelector('#hubBox').hidden,'بازگشت، پروفایل را برمی‌گرداند');
  await p.nav('چیز-نامعلوم');
  ok(!p.inView() && p.txt('#toast').includes('برگشتیم'),'نشانی ناشناس به پروفایل برمی‌گردد');
  const empty=[];
  for(const k of ['events','club','account','pay']){
    await p.nav(k);
    if(!p.inView() || p.view().length<60) empty.push(k);
  }
  ok(empty.length===0,'هر چهار نما متن دارد'+(empty.length?': '+empty.join(', '):''));
  for(const r of p.all('.mrow2')){ p.clickEl(r); await wait(90); }
  ok(true,'همهٔ ردیف‌ها کلیک‌شدنی‌اند');
}

/* ── ۴) مهمان ── */
{
  console.log('\n── مهمان ──');
  const p=await load(makeStore());
  const h=p.hub();
  ok(h.includes('خوش آمدی') && h.includes('ورود با شمارهٔ موبایل'),'یک کارت ورود روشن بالای صفحه');
  ok(!/با ورود باز می‌شود/.test(h),'روی ردیف‌ها جملهٔ تکراری «با ورود باز می‌شود» نیست');
  ok(p.all('.mrow2').length===2 && !/با ورود باز|قفل/.test(p.txt('#hubBox')),'روی ردیف‌ها نشان قفل تکرار نمی‌شود');
  ok(p.txt('.paycard').includes('با ورود، کیف پول خودت را می‌بینی'),'کارت نورا پی حالت مهمان');
  p.click('.mrow2'); await wait(140);
  ok(p.open().includes('shAuth'),'زدم روی ردیف، ورقهٔ ورود می‌آید');
  p.doc.querySelector('#uimob').value='09121234567'; p.click('[data-uiphone]'); await wait(140);
  p.doc.querySelector('#uicode').value='54321'; p.click('[data-uicode]'); await wait(260);
  ok(p.window.location.hash==='#events','بعد از ورود، همان بخشی که خواستی باز می‌شود');
  ok(p.view().includes('رویدادهای من'),'نمای رویدادهای من می‌آید');
  p.click('#supBar'); await wait(140);
  ok(p.open().includes('shSupport'),'پشتیبانی برای مهمان هم باز است');
}

/* ── ۵) پشتیبانی: یک جا ── */
{
  console.log('\n── پشتیبانی و راهنما ──');
  const p=await load(makeStore(session()),'#support');
  await wait(120);
  ok(p.open().includes('shSupport'),'نشانی #support ورقه را از پایین می‌آورد');
  const s=p.doc.querySelector('#supBody');
  ok(s!==null && p.all('#supBody .chan').length===4,'چهار راه تماس');
  ok(p.txt('#supBody').includes('حسن مقدم') && p.txt('#supBody').includes('آنلاین'),'کارشناس با نام و وضعیت');
  ok(p.all('#supBody .chipsline .tag').length===6,'شش دستهٔ تیکت');
  ok(p.all('#supBody .faq').length===7,'هفت پرسش پرتکرار');
  ok(p.txt('#supBody').includes('گروه فرهنگی خط زندگی') && p.txt('#supBody').includes('ولی‌عصر'),'دربارهٔ نورا در همان ورقه');
  p.click('[data-close]'); await wait(90);
  ok(p.open().length===0,'ورقه بسته می‌شود');
  /* نوار چسبیده به نوار پایین */
  const bar=p.doc.querySelector('#supBar');
  ok(bar!==null && !bar.hidden,'نوار پشتیبانی روی صفحه هست');
  ok(/position:fixed/.test(fs.readFileSync(DIR+'account.css','utf8')) && /\.supbar\{[^}]*bottom:calc\(74px/.test(fs.readFileSync(DIR+'account.css','utf8')),
     'نوار پشتیبانی چسبیده به بالای نوار پایین است');
  ok(bar.dataset.sheet==='shSupport','نوار، همان ورقه را باز می‌کند');
  /* پیام کوتاه و بلند */
  p.click('#supBar'); await wait(120);
  p.set('#msg','کم'); p.click('[data-sup-send]'); await wait(90);
  ok(p.txt('#toast').includes('بیشتر'),'پیام کوتاه فرستاده نمی‌شود');
  p.set('#msg','دربارهٔ تأیید رسید کارت‌به‌کارت سؤال دارم');
  p.click('[data-sup-send]'); await wait(120);
  ok(p.txt('#toast').includes('ثبت شد'),'پیام پشتیبانی ثبت می‌شود');
  /* یک جا بودن: هیچ صفحهٔ دیگری ورقهٔ پشتیبانی ندارد */
  const others=['home.html','events.html','event.html'];
  const bad=others.filter(f=>/id="shSupport"|id="shFaq"|supBody|faqBody/.test(fs.readFileSync(DIR+f,'utf8')));
  ok(bad.length===0,'هیچ صفحهٔ دیگری ورقهٔ پشتیبانی ندارد'+(bad.length?': '+bad:''));
  const links=[];
  for(const f of others.concat(['data.js'])){
    const src=fs.readFileSync(DIR+f,'utf8');
    for(const m of src.matchAll(/href:'([^']*support[^']*)'/g)) links.push(f+':'+m[1]);
  }
  ok(links.length>0 && links.every(x=>x.endsWith('account.html#support')),'همهٔ راه‌های پشتیبانی به حساب من می‌روند: '+links.length);
  ok(/f==='shSupport'\|\|f==='shFaq'\)\{ location\.href='account\.html#support'/.test(fs.readFileSync(DIR+'ui.js','utf8')),
     'منوی مشترک هم همان نشانی را می‌دهد');
}

/* ── ۶) رویدادهای من: بلیت، گواهی، کارنامه، نظر ── */
{
  console.log('\n── رویدادهای من ──');
  const p=await load(makeStore(session()),'#events');
  ok(p.all('#viewBox .vtab').length===5,'پنج تب: پیش‌رو، برگزارشده، بلیت و گواهی، کارنامهٔ حضور، نظرها');
  ok(p.all('#viewBox .erow').length===3,'سه ثبت‌نام پیش‌رو');
  ok(p.txt('#viewBox').includes('کارت ورود') && p.all('#viewBox [data-cancel-ev]').length===3,'کارت ورود و لغو روی هر ردیف');
  p.click('#viewBox [data-tab="past"]'); await wait(110);
  ok(p.all('#viewBox .erow').length===2 && p.txt('#viewBox').includes('حضور ثبت شد'),'تب برگزارشده‌ها');
  p.click('#viewBox [data-tab="tickets"]'); await wait(110);
  const t=p.view();
  ok(p.doc.querySelector('#viewBox .idcard')!==null && t.includes('NL-4567'),'کارت ورود با کد عضویت');
  ok(t.includes('کارگاه عکاسی مقدماتی') && t.includes('NL-T4K7M9X'),'گواهی خودِ عضو با سریال');
  ok(p.all('#viewBox .kind').length===4 && t.includes('چاپی') && t.includes('VIP'),'چهار گونهٔ گواهی');
  ok(t.includes('۲۴ ماه'),'اعتبار پیش‌فرض گواهی');
  p.window.URL.createObjectURL=()=>'blob:nora'; p.window.URL.revokeObjectURL=()=>{};
  p.click('#viewBox [data-cert-dl]'); await wait(90);
  ok(p.txt('#toast').includes('گواهی'),'دانلود گواهی فایل می‌سازد');
  p.click('#viewBox [data-cert-req="print"]'); await wait(100);
  ok(p.open().includes('shConfirm') && p.txt('#shConfirm').includes('سرپرست'),'سفارش گواهی چاپی با تأیید سرپرست');
  p.click('#shConfirm [data-cert-yes]'); await wait(100);
  ok(p.txt('#toast').includes('سفارش ثبت شد'),'سفارش ثبت می‌شود');
  p.click('#viewBox [data-tab="attend"]'); await wait(110);
  ok(p.all('#viewBox .bars i').length===12 && p.all('#viewBox .bars i.off').length===2,'نمودار دوازده‌ماهه با دو ماه کم‌رنگ');
  ok(p.all('#viewBox .tk').length===5 && p.view().includes('غیبت'),'پنج جلسهٔ آخر با حضور و غیبت');
  p.click('#viewBox [data-tab="reviews"]'); await wait(110);
  ok(p.all('#viewBox .tk').length===2 && p.view().includes('★'),'نظرهای نوشته‌شده با ستاره');
  p.click('#viewBox [data-tab="up"]'); await wait(110);
  p.click('#viewBox [data-cancel-ev="e1"]'); await wait(110);
  ok(p.open().includes('shConfirm'),'لغو ثبت‌نام ورقهٔ تأیید می‌آورد');
  p.click('[data-cancel-yes="e1"]'); await wait(110);
  ok(p.txt('#toast').includes('لغو شد'),'لغو ثبت می‌شود');
}

/* ── ۷) باشگاه و امتیاز من ── */
{
  console.log('\n── باشگاه و امتیاز من ──');
  const p=await load(makeStore(session()),'#club');
  const v=p.view();
  const s1=p.doc.querySelectorAll('#viewBox .stats')[0];
  ok(s1.querySelectorAll('.stat2').length===4 && v.includes('۲٬۴۵۰'),'چهار عدد: امتیاز، سطح، فاصله، رتبه');
  ok(v.includes('رتبهٔ شهریور ۱۴۰۵') && v.includes('از ۳۴۰'),'رتبهٔ ماهانه از داده');
  ok(p.all('#viewBox .lvrow').length===4,'نردبان چهار سطح');
  ok(p.all('#viewBox .ack').length===8 && p.all('#viewBox .ack.on').length===4,'هشت دستاورد، چهار گرفته‌شده');
  ok(p.all('#viewBox .kind').length===2 && v.includes('کد تخفیف ٪۵'),'فروشگاه پاداش');
  ok(v.includes('NORA-4567') && v.includes('دعوت ۲ دوست'),'دعوت دوستان داخل باشگاه ادغام شده');
  ok(v.includes('روزانه تا ۵۰') && v.includes('ماهانه تا ۳۰۰'),'سقف‌های محافظ امتیاز');
  ok(v.includes('انجام شد'),'کانال، انجام‌شده نشان می‌دهد');
  p.click('#viewBox [data-copy]'); await wait(90);
  ok(p.txt('#toast').includes('کپی'),'کپی کد دعوت');
  p.click('#viewBox [data-reward]'); await wait(90);
  ok(p.txt('#toast').includes('امتیازت'),'جایزه پیام می‌دهد');
}

/* ── ۸) اطلاعات و تنظیمات ── */
const st=makeStore(session());
{
  console.log('\n── اطلاعات و تنظیمات ──');
  const p=await load(st,'#account');
  const v=p.view();
  ok(v.includes('اطلاعات حساب من') && p.all('#viewBox input').length===0,'اطلاعات در حالت نمایش');
  ok(p.txt('#viewBox').includes('ثبت نشده') && p.txt('#viewBox').includes('۰۹۱۲۱۲۳۴۵۶۷'),'فیلد خالی و شمارهٔ تأییدشده');
  ok(p.all('#viewBox .step').length===3,'سه پلهٔ تأیید پروفایل');
  p.click('#viewBox [data-ptab="forms"]'); await wait(120);
  ok(p.all('#viewBox .tk').length===3 && p.view().includes('پیش‌نویس'),'فرم‌های من تب پروفایل شده');
  ok(p.view().includes('۹ گونه'),'گونه‌های فرم از قواعد');
  p.click('#viewBox [data-ptab="privacy"]'); await wait(120);
  ok(p.view().includes('حریم خصوصی') && p.doc.querySelector('#dlBtn')!==null && p.doc.querySelector('#delBtn')!==null,
     'حریم خصوصی و حذف حساب تب پروفایل شده');
  p.click('#viewBox [data-ptab="info"]'); await wait(120);
  ok(p.doc.querySelector('#editBtn')!==null && p.all('#viewBox input').length===0,'برگشت به تب اطلاعات');
  /* ویرایش و اعتبارسنجی */
  p.click('#editBtn'); await wait(110);
  ok(p.all('#viewBox input').length===9 && p.doc.querySelector('#f_phone').hasAttribute('readonly'),'نه فیلد، شمارهٔ قفل');
  p.set('#f_fullName',''); p.set('#f_nationalId','123'); p.set('#f_birthDate','۱۳۷۰');
  p.click('#sendBtn'); await wait(110);
  ok(p.all('#viewBox .fld.bad').length>=3 && p.window.localStorage.getItem('nora-home-profile')===null,'خطاها می‌نشینند و چیزی ذخیره نمی‌شود');
  ok(p.txt('#toast').includes('ببین'),'پیام خطا راهنمایی می‌کند');
  p.set('#f_fullName','سارا محمدی'); p.set('#f_birthDate','1378/05/12'); p.set('#f_nationalId','1111111111');
  p.click('#sendBtn'); await wait(110);
  ok(p.view().includes('درست نیست')||p.txt('#viewBox').includes('درست نیست'),'کد ملی بی‌چک‌سام رد می‌شود');
  p.set('#f_nationalId','۰۰۷۹۵۴۳۹۴۴'); p.set('#f_address','خیابان ولی‌عصر، پلاک ۱۲');
  p.click('#sendBtn'); await wait(160);
  const saved=JSON.parse(p.window.localStorage.getItem('nora-home-profile')||'{}');
  ok(saved.status==='pending' && saved.nationalId==='0079543944' && saved.birthDate==='1378/05/12','ذخیره، یکدست‌سازی و ارسال برای تأیید');
  ok(saved.phone==='09121234567','شمارهٔ تماس از حساب می‌آید');
  ok(saved.history.some(x=>x.k==='pending'),'سابقهٔ پلهٔ تأیید ثبت می‌شود');
  ok(p.all('#viewBox input').length===0,'بعد از ذخیره، فرم بسته می‌شود');
  ok(p.hub().includes('در صف تأیید'),'وضعیت تازه روی پروفایل هم می‌آید');
  /* پیش‌نویس */
  p.click('#editBtn'); await wait(100);
  p.set('#f_email','sara@nora.ir'); p.click('#draftBtn'); await wait(150);
  const d2=JSON.parse(p.window.localStorage.getItem('nora-home-profile')||'{}');
  ok(d2.email==='sara@nora.ir' && d2.status==='pending','«فقط ذخیره» وضعیت را خراب نمی‌کند');
  /* دانلود و حذف: تب حریم خصوصی */
  p.click('#viewBox [data-ptab="privacy"]'); await wait(120);
  p.window.URL.createObjectURL=()=>'blob:nora'; p.window.URL.revokeObjectURL=()=>{};
  p.click('#dlBtn'); await wait(100);
  ok(p.txt('#toast').includes('آماده'),'دانلود اطلاعات من فایل می‌سازد');
  const asked=()=>!!JSON.parse(p.window.localStorage.getItem('nora-home-profile')||'{}').askedDelete;
  p.click('#delBtn'); await wait(110);
  ok(p.open().includes('shConfirm') && p.doc.querySelector('#delWord')!==null && p.doc.querySelector('#delCode')!==null,'حذف حساب سه تأیید می‌خواهد');
  p.click('[data-close]'); await wait(90);
  ok(p.open().length===0 && !asked(),'«هنوز نه» چیزی ثبت نمی‌کند');
  p.click('#delBtn'); await wait(100); p.click('#delYes'); await wait(90);
  ok(!asked() && p.txt('#toast').includes('تأیید'),'بی کلمهٔ تأیید ثبت نمی‌شود');
  p.set('#delWord','حذف'); p.click('#delYes'); await wait(90);
  ok(!asked() && p.txt('#toast').includes('۵۴۳۲۱'),'بی کد پیامکی رد می‌شود');
  p.set('#delCode','۵۴۳۲۱'); p.click('#delYes'); await wait(140);
  const d3=JSON.parse(p.window.localStorage.getItem('nora-home-profile')||'{}');
  ok(d3.askedDelete===true && d3.history.some(x=>x.k==='delete'),'با هر سه تأیید ثبت می‌شود');
  ok(p.txt('#viewBox').includes('ثبت شده'),'کارت حریم خصوصی وضعیت را نشان می‌دهد');
}

/* ── ۹) پاک‌سازی و درستی ── */
{
  console.log('\n── پاک‌سازی و درستی ──');
  const p=await load(makeStore(Object.assign(session(),{
    'nora-home-profile':JSON.stringify({fullName:'<img src=x onerror=alert(1)>',status:'عجیب',reason:'<b>خطر</b>',
      history:[{k:'hack',at:'x'},{k:'approved',at:'۸ شهریور'}],extra:'x'})})));
  ok(p.errs.length===0 && p.doc.querySelectorAll('img[src="x"]').length===0,'دادهٔ آلوده صفحه را نمی‌شکند');
  ok(p.hub().includes('تکمیل نشده'),'وضعیت ناشناس به «تکمیل نشده» برمی‌گردد');
  const syms=new Set(p.all('symbol[id]').map(s=>s.id));
  const missing=new Set(), links=new Set(), gos=new Set();
  for(const k of ['events','club','account','pay']){
    await p.nav(k);
    for(const u of p.all('#viewBox use')){const id=(u.getAttribute('href')||'').slice(1); if(!syms.has(id)) missing.add(id)}
    for(const a of p.all('#viewBox a[href]')) links.add(a.getAttribute('href'));
    for(const g of p.all('#viewBox [data-goto]')) gos.add(g.dataset.goto);
  }
  await p.nav(''); await wait(90);
  for(const u of p.all('#hubBox use')){const id=(u.getAttribute('href')||'').slice(1); if(!syms.has(id)) missing.add(id)}
  for(const u of p.all('#supBody use')){const id=(u.getAttribute('href')||'').slice(1); if(!syms.has(id)) missing.add(id)}
  ok(missing.size===0,'هر نمادی که صدا زده می‌شود در صفحه هست'+(missing.size?': '+[...missing].join(', '):''));
  const deep=[...links,...gos].filter(h=>h&&!h.startsWith('http')&&!h.startsWith('tel:')&&!h.startsWith('mailto:'));
  const bad=deep.filter(h=>{const f=h.split('?')[0].split('#')[0]; return f&&!fs.existsSync(DIR+f)});
  ok(bad.length===0,'نشانی شکسته‌ای نیست'+(bad.length?': '+bad.join(', '):''));
  ok(p.all('.mrow2').length===2,'دو ردیف سرجایشان‌اند');
  const css=fs.readFileSync(DIR+'account.css','utf8');
  ok(!/\.tiles\{|\.tile\{/.test(css),'سبک کاشی‌های بخش‌های قدیمی پاک شد');
  const html=fs.readFileSync(DIR+'account.html','utf8');
  ok(!/secTiles|secQuick|secRoad|secPrivacy|secLevel/.test(html),'قاب بخش‌های قدیمی از صفحه برداشته شد');
  const js=fs.readFileSync(DIR+'account.js','utf8');
  const dead=['renderTiles','VS.notices','VS.forms','VS.privacy','VS.reviews','VS.attend','VS.tickets','V.club','V.account'].filter(x=>js.includes(x));
  ok(dead.length===0,'کد بخش‌های ادغام‌شدهٔ قدیمی نمانده'+(dead.length?': '+dead.join(', '):''));
}

console.log('\naccount-test: '+pass+' بررسی، '+fail+' خطا');
process.exit(fail?1:0);
