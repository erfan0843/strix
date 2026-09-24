/* ══════════════════════════════════════════════════════════════════════════
   نورا — آزمون صفحهٔ «حساب من»
   ──────────────────────────────────────────────────────────────────────────
   معماری تازه: یک نمای پروفایل اپلی، کارت نورا پی در بالا، دو بخش
   (رویدادهای من و پروفایل من) و پشتیبانی که به نوار پایین چسبیده است.

   چه چیزی می‌سنجد:
   • سرِ پروفایل: نام، نشان وضعیت، سطح، امتیاز، نوار تکمیل اطلاعات
   • نورا پی: کارت بالای صفحه، دو زبانه، رنگ و نشان خودش
   • رویدادهای من: پنج تب (پیش‌رو، برگزارشده، بلیت و گواهی، کارنامهٔ حضور، نظرها)
   • پروفایل من: پنج تب (اطلاعات، امتیاز و سطح، باشگاه کتاب‌خوانی، فرم‌ها، حریم خصوصی)
   • پشتیبانی: یک جا، نواری چسبیده به پایین، ورقه از پایین، پرسش‌های پرتکرار
   • مهمان: یک کارت ورود روشن، بی تکرار «با ورود باز می‌شود» روی هر ردیف
   • پاک‌سازی: نام تزریقی، دادهٔ خراب، نشانی شکسته، نماد ناموجود، شناسهٔ تکراری
   اجرا:  node account.test.mjs
   ══════════════════════════════════════════════════════════════════════════ */
import jsdom from 'jsdom';
import fs from 'fs';
const {JSDOM}=jsdom;
const DIR=new URL('./',import.meta.url).pathname;
const OPEN=DIR+'account.html', URLF='file://'+OPEN;

let pass=0, fail=0;
const ok=(c,m)=>{ if(c){pass++; console.log('   ✓ '+m)} else {fail++; console.log('   ✗ '+m)} };
const wait=(t=80)=>new Promise(r=>setTimeout(r,t));

function makeStore(init){
  const m=new Map(Object.entries(init||{}));
  return {getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k),
    clear:()=>m.clear(),key:i=>[...m.keys()][i],get length(){return m.size},_m:m};
}
const MEMBER={name:'سارا محمدی',mobile:'09121234567',joined:'شهریور ۱۴۰۴'};
const reg=()=>({'nora-home-user':JSON.stringify(MEMBER)});

async function load(store,hash){
  const errs=[];
  const dom=await JSDOM.fromFile(OPEN,{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,
    url:URLF+(hash||''),
    beforeParse(w){
      w.scrollTo=()=>{}; if(w.Element&&!w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView=()=>{};
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      if(store) Object.defineProperty(w,'localStorage',{configurable:true,value:store});
      w.addEventListener('error',e=>errs.push('error: '+(e.message||'')));
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
    view:()=>doc.querySelector('#viewBox').textContent.replace(/\s+/g,' ').trim(),
    inView:()=>!doc.querySelector('#viewBox').hidden,
    hub:()=>doc.querySelector('#hubBox').textContent.replace(/\s+/g,' ').trim(),
    nav:async k=>{window.location.hash='#'+k; await wait(140)}};
}
const SRC=fs.readFileSync(DIR+'data.js','utf8');
const SECT=SRC.match(/sections:\[([\s\S]*?)\n  \],/)[1].match(/\{k:'([a-z]+)'/g).map(x=>x.slice(4,-1));
const PTABS=SRC.match(/profileTabs:\[([\s\S]*?)\n  \],/)[1].match(/\{k:'([a-z]+)'/g).map(x=>x.slice(4,-1));

/* ── ۱) نمای پروفایل ── */
{
  console.log('\n── نمای پروفایل ──');
  const p=await load(makeStore(reg()));
  ok(p.errs.length===0,'بی‌خطا بار می‌شود'+(p.errs.length?': '+p.errs.slice(0,2).join(' | '):''));
  const h=p.hub();
  ok(h.includes('سارا محمدی') && h.includes('تأیید شده'),'نام و نشان وضعیت روی سرِ پروفایل');
  ok(h.includes('شهریور ۱۴۰۴') && h.includes('نقره‌ای'),'تاریخ عضویت و سطح');
  ok(h.includes('۲٬۴۵۰') && h.includes('تا طلایی ۵۵۰'),'امتیاز و فاصله تا سطح بعدی');
  ok(p.doc.querySelector('.meter i').style.width==='78%','نوار تکمیل اطلاعات: ٪۷۸');
  ok(h.includes('۲ مورد مانده: کد ملی، نشانی'),'کارهای مانده روی سرِ پروفایل');
  ok(p.all('.pstat').length===3,'سه عدد کلیدی زیر نام');
  ok(SECT.length===3,'معماری: نورا پی و دو بخش');
  ok(p.all('.mrow2').length===2,'منو دو ردیف بیشتر نیست');
  ok(p.all('.mrow2').map(b=>b.dataset.go).join('|')===SECT.filter(k=>k!=='pay').join('|'),'ردیف‌ها: رویدادهای من و پروفایل من');
  ok(!/اعلان/.test(h),'بخش اعلان‌ها روی پروفایل نیست');
  ok(p.doc.querySelector('.topbar .icon-btn')===null,'نوار بالا زنگ اعلان ندارد');
  ok(p.doc.title==='نورا · حساب من','عنوان سند');
}

/* ── ۲) نورا پی: بالا، دو زبانه، با رنگ و نشان خودش ── */
{
  console.log('\n── نورا پی ──');
  const p=await load(makeStore(reg()));
  const pay=p.doc.querySelector('.paycard');
  ok(pay!==null,'کارت نورا پی ساخته می‌شود');
  const order=[...p.doc.querySelector('#hubBox').children].map(e=>e.className.split(' ')[0]);
  ok(order.indexOf('phead')===0 && order.indexOf('paycard')===1 && order[2]==='mrows','نورا پی بالای صفحه و پیش از بخش‌ها');
  const t=p.txt('.paycard');
  ok(t.includes('nora pay') && t.includes('نورا پی'),'نام دو زبانه: nora pay | نورا پی');
  ok(t.includes('فاز بعد') && t.includes('به‌زودی'),'کارت خودش می‌گوید فاز بعد است');
  ok(p.doc.querySelector('.paycard .pico use').getAttribute('href')==='#i-wallet','نشان کیف پول مخصوص خودش');
  ok(p.all('.paycard .pbits span').length===4,'چهار قلم فاز بعد');
  const css=fs.readFileSync(DIR+'account.css','utf8');
  ok(/\.paycard\{[\s\S]*?C9A96A/.test(css),'رنگ طلایی مخصوص نورا پی در CSS');
  p.click('.paycard'); await wait(140);
  ok(p.view().includes('نورا پی') && p.view().includes('قفل است'),'کارت، نمای نورا پی را باز می‌کند');
}

/* ── ۳) نشانی‌ها و بازگشت ── */
{
  console.log('\n── نشانی بخش‌ها ──');
  const p=await load(makeStore(reg()),'#club');
  ok(p.inView() && p.view().includes('امتیاز و سطح من'),'#club تب امتیاز پروفایل را باز می‌کند');
  ok(p.doc.title==='نورا · پروفایل من','عنوان سند نام بخش را می‌گوید');
  ok(p.all('#viewBox .vtab').length===PTABS.length && PTABS.length===5,'پروفایل پنج تب دارد');
  p.click('[data-back]'); await wait(140);
  ok(!p.inView() && !p.doc.querySelector('#hubBox').hidden,'بازگشت، پروفایل را برمی‌گرداند');
  await p.nav('چیز-نامعلوم');
  ok(!p.inView() && p.txt('#toast').includes('برگشتیم'),'نشانی ناشناس به پروفایل برمی‌گردد');
  const empty=[];
  for(const k of ['events','profile','pay']){
    await p.nav(k);
    if(!p.inView() || p.view().length<80) empty.push(k);
  }
  ok(empty.length===0,'هر سه نما متن دارد'+(empty.length?': '+empty.join(', '):''));
  for(const h of ['account','forms','info','book']) await p.nav(h);
  await p.nav('privacy');
  ok(p.doc.querySelector('[data-ptab="privacy"]').classList.contains('on'),'نشانی #privacy تب حریم خصوصی را باز می‌کند');
  await p.nav('book');
  ok(p.doc.querySelector('[data-ptab="book"]').classList.contains('on') && p.view().includes('کتاب ماه'),
     'نشانی #book تب باشگاه کتاب‌خوانی را باز می‌کند');
}

/* ── ۴) مهمان ── */
{
  console.log('\n── مهمان ──');
  const p=await load(makeStore());
  const h=p.hub();
  ok(h.includes('خوش آمدی') && h.includes('ورود با شمارهٔ موبایل'),'یک کارت ورود روشن بالای صفحه');
  ok(!/با ورود باز می‌شود/.test(h),'روی ردیف‌ها جملهٔ تکراری «با ورود باز می‌شود» نیست');
  ok(p.all('.mrow2').length===2 && p.all('.mrow2 b').every(b=>!/قفل/.test(b.textContent)),'ردیف‌های مهمان بی نشان قفل');
  ok(p.txt('.paycard').includes('با ورود، کیف پول خودت را می‌بینی'),'کارت نورا پی حالت مهمان');
  p.click('.mrow2'); await wait(160);
  ok(p.open().includes('shAuth'),'زدم روی ردیف، ورقهٔ ورود می‌آید');
  p.doc.querySelector('#uimob').value='09121234567'; p.click('[data-uiphone]'); await wait(160);
  p.doc.querySelector('#uicode').value='54321'; p.click('[data-uicode]'); await wait(300);
  ok(p.window.location.hash==='#events','بعد از ورود، همان بخشی که خواستی باز می‌شود');
  ok(p.view().includes('رویدادهای من'),'نمای رویدادهای من می‌آید');
  p.click('#supBar'); await wait(160);
  ok(p.open().includes('shSupport'),'پشتیبانی برای مهمان هم باز است');
}

/* ── ۵) پشتیبانی: یک جا ── */
{
  console.log('\n── پشتیبانی و راهنما ──');
  const p=await load(makeStore(reg()),'#support');
  await wait(160);
  ok(p.open().includes('shSupport'),'نشانی #support ورقه را از پایین می‌آورد');
  ok(p.all('#supBody .chan').length===4,'چهار راه تماس');
  ok(p.txt('#supBody').includes('حسن مقدم') && p.txt('#supBody').includes('آنلاین'),'کارشناس با نام و وضعیت');
  ok(p.all('#supBody .chipsline .tag').length===6,'شش دستهٔ تیکت');
  ok(p.all('#supBody .faq').length===7,'هفت پرسش پرتکرار');
  ok(p.txt('#supBody').includes('گروه فرهنگی خط زندگی') && p.txt('#supBody').includes('ولی‌عصر'),'دربارهٔ نورا در همان ورقه');
  p.click('#supBody [data-cat]:nth-child(2)'); await wait(120);
  ok(p.all('#supBody .pickc.on').length===1,'دستهٔ تیکت انتخاب می‌شود');
  p.set('#msg','کم'); p.click('[data-sup-send]'); await wait(120);
  ok(p.txt('#toast').includes('بیشتر'),'پیام کوتاه فرستاده نمی‌شود');
  p.set('#msg','دربارهٔ تأیید رسید کارت‌به‌کارت سؤال دارم'); p.click('[data-sup-send]'); await wait(160);
  ok(p.txt('#toast').includes('ثبت شد'),'پیام پشتیبانی ثبت می‌شود');
  ok(p.open().length===0,'ورقه بعد از فرستادن بسته می‌شود');
  const bar=p.doc.querySelector('#supBar');
  const css=fs.readFileSync(DIR+'account.css','utf8');
  ok(bar!==null && bar.dataset.sheet==='shSupport','نوار پشتیبانی روی صفحه هست و همان ورقه را باز می‌کند');
  ok(/\.supbar\{[\s\S]*?position:fixed[\s\S]*?bottom:calc\(74px/.test(css),'نوار چسبیده به بالای نوار پایین');
  /* یک‌جایی: هیچ صفحهٔ دیگری ورقهٔ پشتیبانی ندارد */
  const others=['home.html','events.html','event.html'];
  const bad=others.filter(f=>/id="shSupport"|id="shFaq"|supBody|faqBody/.test(fs.readFileSync(DIR+f,'utf8')));
  ok(bad.length===0,'هیچ صفحهٔ دیگری ورقهٔ پشتیبانی ندارد'+(bad.length?': '+bad:''));
  const links=[];
  for(const f of others.concat(['data.js','ui.js'])){
    const src=fs.readFileSync(DIR+f,'utf8');
    for(const m of src.matchAll(/['"]([^'"]*account\.html#support)['"]/g)) links.push(f+':'+m[1]);
  }
  ok(links.length>=4,'راه‌های پشتیبانی در همهٔ صفحه‌ها به حساب من می‌روند: '+links.length);
  ok(/f==='shSupport'\|\|f==='shFaq'\)\{ location\.href='account\.html#support'/.test(fs.readFileSync(DIR+'ui.js','utf8')),
     'منوی مشترک هم همان نشانی را می‌دهد');
}

/* ── ۶) رویدادهای من ── */
{
  console.log('\n── رویدادهای من ──');
  const p=await load(makeStore(reg()),'#events');
  ok(p.all('#viewBox .vtab').length===5,'پنج تب: پیش‌رو، برگزارشده، بلیت و گواهی، کارنامهٔ حضور، نظرها');
  ok(p.all('#viewBox .erow').length===11,'یازده ثبت‌نام پیش‌رو با کارت ورود و لغو');
  ok(p.view().includes('کارت ورود') && p.all('#viewBox [data-cancel]').length===11,'کارت ورود و لغو روی هر ردیف');
  p.click('#viewBox [data-vtab="past"]'); await wait(130);
  ok(p.view().includes('برگزارشده‌ها') && p.all('#viewBox .erow').length===12,'تب برگزارشده‌ها: دوازده رویداد گذشته');
  p.click('#viewBox [data-vtab="tickets"]'); await wait(130);
  const t=p.view();
  ok(p.doc.querySelector('#viewBox .idcard')!==null && t.includes('NL-4567'),'کارت ورود با کد عضویت');
  ok(t.includes('کارگاه عکاسی مقدماتی') && t.includes('NL-T4K7M9X'),'گواهی خودِ عضو با سریال');
  ok(p.all('#viewBox .kind').length===4 && t.includes('چاپی') && t.includes('VIP'),'چهار گونهٔ گواهی');
  ok(t.includes('۲۴ ماه'),'اعتبار پیش‌فرض گواهی');
  p.window.URL.createObjectURL=()=>'blob:nora'; p.window.URL.revokeObjectURL=()=>{};
  p.click('#viewBox [data-dl-cert]'); await wait(120);
  ok(p.txt('#toast').includes('گواهی'),'دانلود گواهی فایل می‌سازد');
  p.click('#viewBox [data-certreq="print"]'); await wait(140);
  ok(p.open().includes('shConfirm') && p.txt('#shConfirm').includes('سرپرست'),'سفارش گواهی چاپی با تأیید سرپرست');
  p.click('#shConfirm [data-cert-yes]'); await wait(140);
  ok(p.txt('#toast').includes('سفارش ثبت شد'),'سفارش ثبت می‌شود');
  p.click('#viewBox [data-vtab="attend"]'); await wait(130);
  ok(p.all('#viewBox .bars i').length===12 && p.all('#viewBox .bars i.off').length===2,'نمودار دوازده‌ماهه با دو ماه کم‌رنگ');
  ok(p.all('#viewBox .tk').length===5 && p.view().includes('غایب'),'پنج جلسهٔ آخر با حضور و غیاب');
  p.click('#viewBox [data-vtab="reviews"]'); await wait(130);
  ok(p.all('#viewBox .tk').length===3 && p.view().includes('★'),'نظرهای نوشته‌شده با ستاره');
  p.click('#viewBox [data-vtab="up"]'); await wait(130);
  p.click('#viewBox [data-cancel]'); await wait(140);
  ok(p.open().includes('shConfirm'),'لغو ثبت‌نام ورقهٔ تأیید می‌آورد');
  p.click('[data-cancel-yes]'); await wait(140);
  ok(p.txt('#toast').includes('لغو شد'),'لغو ثبت می‌شود');
}

/* ── ۷) پروفایل: امتیاز و سطح ── */
{
  console.log('\n── امتیاز و سطح من ──');
  const p=await load(makeStore(reg()),'#club');
  const v=p.view();
  ok(p.all('#viewBox .stat2').length===4 && v.includes('۲٬۴۵۰'),'چهار عدد: امتیاز، سطح، فاصله، رتبه');
  ok(v.includes('رتبهٔ شهریور ۱۴۰۵')===false && v.includes('۱۲ از ۳۴۰'),'رتبهٔ ماهانه از داده');
  ok(p.all('#viewBox .lvrow').length===4,'نردبان چهار سطح');
  ok(p.all('#viewBox .ack').length===8 && p.all('#viewBox .ack.on').length===4,'هشت دستاورد، چهار گرفته‌شده');
  ok(p.all('#viewBox .kind').length===2 && v.includes('کد تخفیف ٪۵'),'فروشگاه پاداش');
  ok(v.includes('NORA-4567') && v.includes('دعوت دوستان'),'دعوت دوستان داخل باشگاه');
  ok(v.includes('روزانه تا ۵۰') && v.includes('ماهانه تا ۳۰۰'),'سقف‌های محافظ امتیاز');
  p.click('#viewBox [data-copy]'); await wait(120);
  ok(p.txt('#toast').includes('کپی'),'کپی کد دعوت');
  p.click('#viewBox [data-reward]'); await wait(120);
  ok(p.txt('#toast').includes('امتیازت'),'جایزه پیام می‌دهد');
}

/* ── ۸) پروفایل: باشگاه کتاب‌خوانی خط زندگی ── */
{
  console.log('\n── باشگاه کتاب‌خوانی ──');
  const st=makeStore(reg());
  const p=await load(st,'#book');
  const v=p.view();
  ok(v.includes('چراغ‌ها را من خاموش می‌کنم') && v.includes('زویا پیرزاد'),'کتاب ماه و نویسنده');
  ok(v.includes('ترم مهر ۱۴۰۵') && v.includes('پنجشنبه‌ها ۱۸:۰۰'),'ترم و روز جلسه');
  ok(v.includes('۷۲') && p.doc.querySelector('.bchero .bar i').style.width==='72%','پیشرفت کتاب ماه ٪۷۲');
  ok(p.all('#viewBox .stat2').length===4,'چهار عدد: اعضا، جلسه‌ها، صفحهٔ من، قفسه');
  ok(v.includes('خانم مریم داوودی'),'سرپرست باشگاه');
  ok(p.all('#viewBox .tk').length===6 && p.all('#viewBox .srow').length>=5,'جلسه‌های پیش‌رو و گذشته، به‌علاوهٔ رزرو و یادداشت');
  ok(v.includes('فصل ۴') && v.includes('فصل ۵'),'برنامهٔ جلسه‌ها');
  ok(v.includes('سووشون') && v.includes('سیمین دانشور'),'قفسهٔ کتاب‌ها');
  ok(v.includes('مدیر مدرسه') && v.includes('خانهٔ ادریسی‌ها'),'سه کتاب ماه گذشته');
  ok(p.all('#viewBox .voteopt').length===3,'رأی کتاب ماه بعد: سه گزینه');
  /* رزرو صندلی */
  p.click('#viewBox [data-seat]'); await wait(140);
  ok(JSON.parse(st.getItem('nora-home-bookclub')).seat===true && p.view().includes('رزرو شد'),'رزرو صندلی ثبت می‌شود');
  /* پیشرفت مطالعه */
  p.click('#viewBox [data-pages="10"]'); await wait(140);
  p.click('#viewBox [data-pages="25"]'); await wait(140);
  ok(JSON.parse(st.getItem('nora-home-bookclub')).pages===35,'صفحه‌ها ثبت می‌شوند: ۳۵');
  /* یادداشت */
  p.set('#bcNote','کوته'); p.click('[data-save-note]'); await wait(140);
  ok(p.txt('#toast').includes('بیشتر'),'یادداشت کوتاه رد می‌شود');
  p.set('#bcNote','فصل ۴: راوی چیزی را پنهان می‌کند که خودش هم نمی‌داند.'); p.click('[data-save-note]'); await wait(140);
  ok(JSON.parse(st.getItem('nora-home-bookclub')).note.length>20,'یادداشت ذخیره می‌شود');
  /* رأی */
  p.click('#viewBox [data-vote="v2"]'); await wait(140);
  const bc=JSON.parse(st.getItem('nora-home-bookclub'));
  ok(bc.vote==='v2' && p.view().includes('رأیت ثبت شد'),'رأی ثبت می‌شود و پیام می‌دهد');
  /* تماشا */
  p.click('#viewBox [data-watch]'); await wait(120);
  ok(p.txt('#toast').includes('ضبط'),'تماشای جلسهٔ گذشته پیام می‌دهد');
  /* پرسش از سرپرست */
  p.click('#viewBox [data-go="support"]'); await wait(160);
  ok(p.open().includes('shSupport'),'پرسش از سرپرست ورقهٔ پشتیبانی را می‌آورد');
  p.click('[data-close]'); await wait(120);
  /* بخشی از پروفایل است، نه بخش جدا */
  ok(SECT.indexOf('book')<0 && PTABS.indexOf('book')>=0,'باشگاه کتاب زیر پروفایل من است، نه ردیف جدا');
  ok(fs.readFileSync(DIR+'home.html','utf8').indexOf('account.html#book')>0,'خانه هم به همین تب می‌فرستد');
  ok(/f==='shClub'\)\{ location\.href='account\.html#book'/.test(fs.readFileSync(DIR+'ui.js','utf8')),'منوی مشترک هم همین تب را باز می‌کند');
}

/* ── ۹) پروفایل: اطلاعات، فرم‌ها، حریم خصوصی ── */
const st=makeStore(reg());
{
  console.log('\n── اطلاعات و تنظیمات ──');
  const p=await load(st,'#account');
  const v=p.view();
  ok(v.includes('اطلاعات حساب من') && p.all('#viewBox input').length===0,'اطلاعات در حالت نمایش');
  ok(p.txt('#viewBox').includes('ثبت نشده') && p.txt('#viewBox').includes('۰۹۱۲۱۲۳۴۵۶۷'),'فیلد خالی و شمارهٔ تأییدشده');
  ok(p.all('#viewBox .step').length===3,'سه پلهٔ تأیید پروفایل');
  p.click('#viewBox [data-ptab="forms"]'); await wait(130);
  ok(p.all('#viewBox .tk').length===3 && p.view().includes('پیش‌نویس'),'فرم‌های من تب پروفایل شده');
  ok(p.view().includes('۹ گونه'),'گونه‌های فرم از قواعد');
  p.click('#viewBox [data-ptab="privacy"]'); await wait(130);
  ok(p.view().includes('حریم خصوصی') && p.doc.querySelector('#dlBtn')!==null && p.doc.querySelector('#delBtn')!==null,
     'حریم خصوصی و حذف حساب تب پروفایل شده');
  p.click('#viewBox [data-ptab="info"]'); await wait(130);
  ok(p.doc.querySelector('#editBtn')!==null && p.all('#viewBox input').length===0,'برگشت به تب اطلاعات');
  /* ویرایش و اعتبارسنجی */
  p.click('#editBtn'); await wait(130);
  ok(p.all('#viewBox input').length===9 && p.doc.querySelector('#f_phone').hasAttribute('readonly'),'نه فیلد، شمارهٔ قفل');
  p.set('#f_fullName',''); p.set('#f_nationalId','123'); p.set('#f_birthDate','۱۳۷۰');
  p.click('#sendBtn'); await wait(130);
  ok(p.all('#viewBox .fld.bad').length>=3 && p.window.localStorage.getItem('nora-home-profile')===null,'خطاها می‌نشینند و چیزی ذخیره نمی‌شود');
  ok(p.txt('#toast').includes('ببین'),'پیام خطا راهنمایی می‌کند');
  p.set('#f_fullName','سارا محمدی'); p.set('#f_birthDate','1378/05/12'); p.set('#f_nationalId','1111111111');
  p.click('#sendBtn'); await wait(130);
  ok(p.view().includes('درست نیست'),'کد ملی بی‌چک‌سام رد می‌شود');
  p.set('#f_nationalId','۰۰۷۹۵۴۳۹۴۴'); p.set('#f_address','خیابان ولی‌عصر، پلاک ۱۲');
  p.click('#sendBtn'); await wait(180);
  const saved=JSON.parse(p.window.localStorage.getItem('nora-home-profile')||'{}');
  ok(saved.status==='pending' && saved.nationalId==='0079543944' && saved.birthDate==='1378/05/12','ذخیره، یکدست‌سازی و ارسال برای تأیید');
  ok(saved.phone==='09121234567','شمارهٔ تماس از حساب می‌آید');
  ok(saved.history.some(x=>x.k==='pending'),'سابقهٔ پلهٔ تأیید ثبت می‌شود');
  ok(p.all('#viewBox input').length===0,'بعد از ذخیره، فرم بسته می‌شود');
  ok(p.hub().includes('در صف تأیید'),'وضعیت تازه روی پروفایل هم می‌آید');
  /* پیش‌نویس */
  p.click('#editBtn'); await wait(120);
  p.set('#f_email','sara@nora.ir'); p.click('#draftBtn'); await wait(160);
  const d2=JSON.parse(p.window.localStorage.getItem('nora-home-profile')||'{}');
  ok(d2.email==='sara@nora.ir' && d2.status==='pending','«فقط ذخیره» وضعیت را خراب نمی‌کند');
  /* دانلود و حذف */
  p.click('#viewBox [data-ptab="privacy"]'); await wait(130);
  p.window.URL.createObjectURL=()=>'blob:nora'; p.window.URL.revokeObjectURL=()=>{};
  p.click('#dlBtn'); await wait(130);
  ok(p.txt('#toast').includes('آماده'),'دانلود اطلاعات من فایل می‌سازد');
  const asked=()=>!!JSON.parse(p.window.localStorage.getItem('nora-home-profile')||'{}').askedDelete;
  p.click('#delBtn'); await wait(140);
  ok(p.open().includes('shConfirm') && p.doc.querySelector('#delWord')!==null && p.doc.querySelector('#delCode')!==null,'حذف حساب دو تأیید می‌خواهد');
  p.click('[data-close]'); await wait(120);
  ok(p.open().length===0 && !asked(),'«هنوز نه» چیزی ثبت نمی‌کند');
  p.click('#delBtn'); await wait(130); p.click('#delYes'); await wait(120);
  ok(!asked() && p.txt('#toast').includes('تأیید'),'بی کلمهٔ تأیید ثبت نمی‌شود');
  p.set('#delWord','حذف'); p.click('#delYes'); await wait(120);
  ok(!asked() && p.txt('#toast').includes('۵۴۳۲۱'),'بی کد پیامکی رد می‌شود');
  p.set('#delCode','۵۴۳۲۱'); p.click('#delYes'); await wait(170);
  const d3=JSON.parse(p.window.localStorage.getItem('nora-home-profile')||'{}');
  ok(d3.askedDelete===true && d3.history.some(x=>x.k==='delete'),'با هر دو تأیید ثبت می‌شود');
  ok(p.txt('#viewBox').includes('ثبت شده'),'کارت حریم خصوصی وضعیت را نشان می‌دهد');
}

/* ── ۱۰) پاک‌سازی و درستی ── */
{
  console.log('\n── پاک‌سازی و درستی ──');
  const p=await load(makeStore(Object.assign(reg(),{
    'nora-home-profile':JSON.stringify({fullName:'<img src=x onerror=alert(1)>',status:'عجیب',reason:'<b>خطر</b>',
      history:[{k:'hack',at:'x'},{k:'approved',at:'۸ شهریور'}],extra:'x'})})));
  ok(p.errs.length===0 && p.doc.querySelectorAll('img[src="x"]').length===0,'دادهٔ آلوده صفحه را نمی‌شکند');
  ok(p.hub().includes('تکمیل نشده'),'وضعیت ناشناس به «تکمیل نشده» برمی‌گردد');
  const syms=new Set(p.all('symbol[id]').map(s=>s.id));
  const missing=new Set(), links=new Set();
  for(const k of ['events','profile','pay']){
    await p.nav(k);
    for(const u of p.all('#viewBox use')){const id=(u.getAttribute('href')||'').slice(1); if(!syms.has(id)) missing.add(id)}
    for(const a of p.all('#viewBox a[href]')) links.add(a.getAttribute('href'));
  }
  await p.nav(''); await wait(120);
  for(const u of p.all('#hubBox use')){const id=(u.getAttribute('href')||'').slice(1); if(!syms.has(id)) missing.add(id)}
  for(const u of p.all('#supBody use')){const id=(u.getAttribute('href')||'').slice(1); if(!syms.has(id)) missing.add(id)}
  ok(missing.size===0,'هر نمادی که صدا زده می‌شود در صفحه هست'+(missing.size?': '+[...missing].join(', '):''));
  const bad=[...links].filter(h=>h&&!/^(https?:|tel:|mailto:|#)/.test(h))
    .filter(h=>{const f=h.split('?')[0].split('#')[0]; return f&&!fs.existsSync(DIR+f)});
  ok(bad.length===0,'نشانی شکسته‌ای نیست'+(bad.length?': '+bad.join(', '):''));
  ok(p.all('.mrow2').length===2,'دو ردیف سرجایشان‌اند');
  /* شناسهٔ تکراری و ساختار تکراری */
  const ids=p.all('[id]').map(e=>e.id), dup=ids.filter((x,i)=>ids.indexOf(x)!==i);
  ok(dup.length===0,'هیچ شناسهٔ تکراری در صفحه نیست'+(dup.length?': '+[...new Set(dup)].join(', '):''));
  const html=fs.readFileSync(DIR+'account.html','utf8');
  ok((html.match(/class="tabbar"/g)||[]).length===1 && (html.match(/id="toast"/g)||[]).length===1,'یک نوار پایین و یک پیام‌رسان');
  const css=fs.readFileSync(DIR+'account.css','utf8');
  ok(css.split('{').length===css.split('}').length,'آکولادهای CSS موازنه است');
  const js=fs.readFileSync(DIR+'account.js','utf8');
  const dead=['renderTiles','VS.notices','VS.forms','VS.privacy','VS.reviews','VS.attend','VS.tickets','V.club','V.account','pcard','supportHTML2'].filter(x=>js.includes(x));
  ok(dead.length===0,'کد بخش‌های ادغام‌شدهٔ قدیمی نمانده'+(dead.length?': '+dead.join(', '):''));
  ok(!/[\u2014]/.test(p.txt('#hubBox')),'خط تیرهٔ بلند در متن رابط نیست');
}

/* ── ۱۱. دسترس‌پذیری و جزئیات پایانی ── */
{
  console.log('\n── دسترس‌پذیری ──');
  const p=await load(makeStore(reg()));
  await part11(p);
}
async function part11(p){
  await p.nav('events'); await wait(150);
  const tabs=p.all('#viewBox .vtab');
  ok(tabs.length===5 && tabs.every(t=>t.getAttribute('role')==='tab'),'تب‌های رویدادها نقش تب دارند');
  ok(tabs.filter(t=>t.getAttribute('tabindex')==='0').length===1,'فقط تب روشن در ترتیب پیمایش است');
  const on=tabs.find(t=>t.getAttribute('aria-selected')==='true');
  ok(!!on && on.getAttribute('tabindex')==='0','تب روشن نشان‌دار و در ترتیب پیمایش است');
  ok(!!p.doc.querySelector('[role="tablist"][aria-label]'),'فهرست تب‌ها برچسب دارد');
  /* کلید جهت‌دار: راست در RTL به تب پیشین می‌رود */
  on.dispatchEvent(new p.window.KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true,cancelable:true}));
  await wait(180);
  const cur=p.all('#viewBox .vtab').findIndex(t=>t.getAttribute('aria-selected')==='true');
  ok(cur===1,'کلید چپ تب را یکی جلو می‌برد');
  const cur2=p.all('#viewBox .vtab').find(t=>t.getAttribute('aria-selected')==='true');
  cur2.dispatchEvent(new p.window.KeyboardEvent('keydown',{key:'End',bubbles:true,cancelable:true}));
  await wait(180);
  const last=p.all('#viewBox .vtab'); ok(last[last.length-1].getAttribute('aria-selected')==='true','کلید End به آخرین تب می‌رود');
  /* پشتیبانی از پایین همین صفحه */
  p.click('#supBar'); await wait(180);
  ok(p.doc.querySelector('#shSupport').className.includes('on'),'نوار پشتیبانی ورقهٔ راهنما را باز می‌کند');
  p.click('#shSupport [data-close]'); await wait(120);
  /* تصاویر و متن جانشین */
  const imgs=p.all('#viewBox img, #hubBox img, #supBody img');
  ok(imgs.every(i=>i.hasAttribute('alt')),'هر تصویر متن جانشین دارد');
  /* هیچ دکمه‌ای بی‌نام نیست */
  const nameless=p.all('#viewBox button, #hubBox button, #supBody button').filter(b=>{
    const t=(b.textContent||'').replace(/\s+/g,'').trim();
    return !t && !b.getAttribute('aria-label') && !b.querySelector('svg + small');
  });
  ok(nameless.length===0,'هیچ دکمه‌ای بی‌نام نیست'+(nameless.length?': '+nameless.length+' مورد':''));
}
console.log('\naccount-test: '+pass+' بررسی، '+fail+' خطا');
process.exit(fail?1:0);
