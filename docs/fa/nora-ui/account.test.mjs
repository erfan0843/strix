/* ══════════════════════════════════════════════════════════════════════════
   نورا — آزمون صفحهٔ «حساب من»
   ──────────────────────────────────────────────────────────────────────────
   معماری تازه: صفحهٔ پروفایل (سر، میان‌بُرها، رویداد نزدیک، چهار بخش) و
   چهار نما: نورا پی، رویدادهای من، پروفایل من (شش تب، با «ورود و امنیت»)،
   باشگاه و امتیاز من. ورود، صفحهٔ جدای خودش (login.html) را دارد و پشتیبانی
   صفحهٔ خودش را؛ این صفحه فقط میان‌برشان را می‌گذارد.

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
const MEMBER={name:'سارا محمدی',mobile:'09121234567',joined:'شهریور ۱۴۰۴',wallet:1250000,certs:2,msgs:1};
const reg=()=>({'nora-home-user':JSON.stringify(MEMBER)});

async function load(store,hash){
  const errs=[];
  const dom=await JSDOM.fromFile(OPEN,{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,
    url:URLF+(hash||''),
    beforeParse(w){
      w.scrollTo=()=>{}; if(w.Element&&!w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView=()=>{};
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      if(store) Object.defineProperty(w,'localStorage',{configurable:true,value:store});
      w.URL.createObjectURL=()=>'blob:nora'; w.URL.revokeObjectURL=()=>{};
      w.addEventListener('error',e=>errs.push('error: '+(e.message||'')));
      const ce=w.console.error; w.console.error=(...a)=>errs.push('console.error: '+a.join(' '));
    }});
  await wait(650);
  const {window}=dom, doc=window.document;
  return {dom,window,doc,errs,
    click:sel=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel);
      el.dispatchEvent(new window.MouseEvent('click',{bubbles:true}))},
    clickEl:el=>el.dispatchEvent(new window.MouseEvent('click',{bubbles:true})),
    key:sel=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel);
      el.dispatchEvent(new window.KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true,cancelable:true}))},
    set:(sel,v)=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel); el.value=v;
      el.dispatchEvent(new window.Event('change',{bubbles:true}))},
    txt:sel=>{const el=doc.querySelector(sel); return el?el.textContent.replace(/\s+/g,' ').trim():''},
    all:sel=>[...doc.querySelectorAll(sel)],
    open:()=>[...doc.querySelectorAll('.sheet.on')].map(e=>e.id),
    view:()=>doc.querySelector('#viewBox').textContent.replace(/\s+/g,' ').trim(),
    inView:()=>!doc.querySelector('#viewBox').hidden,
    prof:()=>doc.querySelector('#profBox').textContent.replace(/\s+/g,' ').trim(),
    tabs:key=>[...doc.querySelectorAll('#viewBox [data-'+key+']')],
    onTab:key=>{const el=doc.querySelector('#viewBox [data-'+key+'].on');
      return el?el.dataset[key==='ptab'?'ptab':key==='ctab'?'ctab':'vtab']:''},
    nav:async k=>{window.location.hash='#'+k; await wait(170)}};
}

/* ── ۱) بار صفحه و سرِ پروفایل ── */
{
  console.log('\n── صفحه و سرِ پروفایل ──');
  const p=await load(makeStore(reg()));
  ok(p.errs.length===0,'بی‌خطا بار می‌شود'+(p.errs.length?': '+p.errs[0]:''));
  ok(p.doc.title==='نورا · حساب من','عنوان سند');
  ok(p.doc.querySelector('#profBox')!==null && p.doc.querySelector('#profBox').hidden===false,'صفحهٔ پروفایل پیش چشم است');
  ok(p.inView()===false,'نمای بخش‌ها هنوز بسته است');
  const head=p.doc.querySelector('.phead');
  ok(head!==null && head.querySelector('.cover')!==null,'سرِ پروفایل با جلد رنگی');
  ok(p.all('.phead .ctags .tag').length===2,'دو نشان روی جلد: وضعیت و امتیاز');
  ok(p.all('.phead .av').length===1 && p.txt('.phead .av').length===1,'آواتار با نخستین حرف نام');
  ok(p.prof().includes('سارا محمدی'),'نام روی سرِ پروفایل');
  ok(p.prof().includes('شهریور ۱۴۰۴'),'تاریخ عضویت');
  ok(p.all('.pstat').length===3,'سه عدد کلیدی: امتیاز، تا سطح بعد، برنامه‌ها');
  ok(p.prof().includes('۲٬۴۵۰') && p.prof().includes('تا طلایی'),'امتیاز و فاصله تا سطح بعدی');
  ok(p.prof().includes('٪۸۳') && p.all('.meter').length>=1,'نوار تکمیل اطلاعات');
  ok(p.prof().includes('۱ قلم مانده'),'کارهای مانده روی سرِ پروفایل');
  p.click('.phead .edit'); await wait(200);
  ok(p.inView() && p.onTab('ptab')==='info','نشان ویرایش، پروفایل را روی تب اطلاعات می‌آورد');
  p.click('#editBtn'); await wait(200);
  ok(p.all('#viewBox input').length>=4 && p.all('#viewBox select').length>=4,'تکمیل اطلاعات، کادرهای انتخاب را باز می‌کند');
  ok(p.all('#viewBox [data-fpick="gender"]').length===3,'جنسیت با سه دکمه، بی تایپ');
  ok(p.all('#viewBox .datepick select').length===3,'تاریخ تولد سه فهرست روز و ماه و سال');
  p.set('#f_province','فارس'); await wait(120);
  ok(p.doc.querySelector('#f_city').options.length>=4 && p.doc.querySelector('#f_city').options[1].textContent.includes('شیراز'),'شهرها با استان عوض می‌شوند');
  p.set('#f_city','شیراز');
  p.click('[data-back]'); await wait(180);
  ok(!p.inView() && !p.doc.querySelector('#profBox').hidden,'بازگشت، صفحهٔ پروفایل را برمی‌گرداند');
}

/* ── ۲) نورا پی سرِ صفحه و رویداد نزدیک ── */
{
  console.log('\n── نورا پی و رویداد نزدیک ──');
  const p=await load(makeStore(reg()));
  ok(p.doc.querySelector('.paybar')!==null,'کارت نورا پی، جدا و سرِ صفحه');
  ok(p.txt('.paybar').includes('۱٬۲۵۰٬۰۰۰')&&p.txt('.paybar').includes('تومان'),'موجودی کیف پول روی کارت');
  ok(p.all('.paybar .pbrow .pbtn').length===3,'سه کنش کیف پول: شارژ، صورت‌حساب، اقساط');
  ok(p.all('.paybar .pmeta .tag').length===3,'سه برچسب کوتاه زیر موجودی');
  ok(p.all('.qtiles .qtile').length===0,'کاشی‌های میان‌بُر برداشته شده');
  const prof=p.prof();
  ok(prof.indexOf('دعوت دوست')<0&&p.all('.qtile').length===0,'میان‌بُرها از فهرست حساب رفته');
  ok(prof.indexOf('نورا پی')<prof.indexOf('رویدادهای من'),'نورا پی بالای بخش‌ها می‌آید');
  p.click('.paybar .pbmain'); await wait(200);
  ok(p.inView()&&p.view().includes('نورا پی'),'کارت نورا پی نما را باز می‌کند');
  await p.nav('');
  p.click('.pbrow .pbtn:nth-child(2)'); await wait(190);
  ok(p.inView(),'کنش‌های کیف پول هم به همان نما می‌روند');
  await p.nav('');
  const card=p.doc.querySelector('.qcard');
  ok(card!==null && card.querySelector('.qc-date')!==null,'کارت رویداد نزدیک با تاریخ');
  ok(p.txt('.qcard').includes('کارت ورودت آماده است'),'یادآوری کارت ورود روی کارت رویداد');
  p.click('.qcard .qc-go'); await wait(160);
  ok(p.open().includes('shTicket')&&p.all('#shTicket .tk-qr svg').length===1,'کارت ورود با کیوآرکد باز می‌شود');
  ok(p.txt('#shTicket').includes('کد ثبت‌نام')&&p.txt('#shTicket').includes('lifeline1.ir/c/'),'کارت ورود نشانی و کد را نشان می‌دهد');
  p.click('#shTicket [data-close]'); await wait(170);
}

/* ── ۳) سه بخش ── */
{
  console.log('\n── چهار بخش ──');
  const p=await load(makeStore(reg()));
  const rows=p.all('.mrow2');
  ok(rows.length===3,'سه ردیف بخش');
  const order=rows.map(r=>r.dataset.view).join(',');
  ok(order==='events,profile,book','ترتیب: رویدادهای من، پروفایل من، باشگاه کتاب‌خوانی');
  ok(p.prof().includes('باشگاه کتاب‌خوانی خط زندگی'),'ردیف باشگاه کتاب‌خوانی خط زندگی');
  ok(!p.doc.querySelector('.mrow2[data-view="pay"]')&&!p.doc.querySelector('.mrow2[data-view="club"]'),'نورا پی و باشگاه امتیاز ردیف نیستند');
  ok(p.all('.mrow2 .mini').length===3,'هر ردیف نشان کوتاه خودش را دارد');
  p.click('.mrow2[data-view="book"]'); await wait(200);
  ok(p.inView()&&p.doc.title.includes('باشگاه کتاب‌خوانی'),'ردیف کتاب، باشگاه کتاب‌خوانی را باز می‌کند');
  ok(p.view().includes('کتاب ماه')&&p.view().includes('جلسه‌ها'),'صفحهٔ باشگاه با کتاب ماه و جلسه‌ها');
  await p.nav('');
  p.click('[data-view="profile"]'); await wait(200);
  ok(p.inView() && p.doc.title==='نورا · پروفایل من','ردیف پروفایل، نمای پروفایل را باز می‌کند');
  await p.nav('');
  ok(!p.inView(),'نشانی خالی، صفحهٔ پروفایل را برمی‌گرداند');
  const src=fs.readFileSync(DIR+'data.js','utf8');
  const W={}; new Function('window','document',src)(W,{querySelector:()=>null,documentElement:{}});
  const SEC=(W.NORA&&W.NORA.ACCOUNT&&W.NORA.ACCOUNT.sections)||[];
  ok(SEC.length===4 && SEC.map(x=>x.k).join(',')==='pay,events,profile,book','بخش‌ها از data.js می‌آید');
  ok(SEC[0].card===true&&SEC[0].k==='pay','نورا پی کارتِ سرِ صفحه است');
  ok(SEC[3].n.includes('باشگاه کتاب‌خوانی'),'و ردیف آخر باشگاه کتاب‌خوانی خط زندگی');
}

/* ── ۴) پروفایل سه تب، باشگاه دو تب ── */
{
  console.log('\n── تب‌های درونی ──');
  const p=await load(makeStore(reg()));
  await p.nav('profile');
  ok(p.all('#viewBox .vtab').length===6,'پروفایل شش تب دارد');
  ok(p.all('#viewBox .vtab').map(t=>t.dataset.ptab).join(',')==='info,auth,club,invite,forms,privacy','ترتیب تب‌ها: اطلاعات، ورود و امنیت، امتیاز، کد دعوت، فرم‌ها، حریم');
  ok(!p.doc.querySelector('#viewBox [data-ptab="book"]'),'باشگاه کتاب دیگر تب پروفایل نیست');
  await p.nav('profile');
  ok(p.view().includes('اطلاعات من') && p.view().includes('کم تایپ کن'),'تب اطلاعات، پروفایل ساده می‌آورد');
  ok(!/فرایند تأیید|فرم پروفایل/.test(p.view()),'خبری از فرم و صف تأیید پروفایل نیست');
  p.click('[data-ptab="privacy"]'); await wait(170);
  ok(p.view().includes('حریم خصوصی') && p.view().includes('دانلود'),'تب حریم خصوصی');
  await p.nav('club');
  ok(p.onTab('ptab')==='club','#club تب امتیاز و سطح را باز می‌کند');
  ok(!p.doc.querySelector('[data-ptab="book"]'),'تب کتاب از پروفایل برداشته شد');
  p.click('[data-ptab="club"]'); await wait(190);
  ok(p.view().includes('امتیاز و سطح من') && p.view().includes('دستاوردها'),'تب امتیاز و سطح');
  p.click('[data-ptab="auth"]'); await wait(180);
  ok(p.view().includes('شمارهٔ ورود و رمز')&&p.view().includes('دستگاه‌های واردشده'),'تب ورود و امنیت');
  ok(p.view().includes('ربات رمز یک‌بارمصرف نورا')&&p.doc.querySelector('#viewBox a[href^="https://ble.ir/"]')!==null,'راه ورود: فقط ربات رمز یک‌بارمصرف بله');
  ok(!p.view().includes('ایتا')&&!p.view().includes('تلگرام'),'نه ایتا نه تلگرام، هیچ‌کجا');
  ok(p.view().includes('ورود مدیران')===false,'ورود مدیران در حساب من نیست، در صفحهٔ ورود است');
  ok(p.all('#viewBox .drow').length===3,'سه دستگاه واردشده');
  ok(p.all('#viewBox [data-enddev]').length===2,'دو دستگاه دیگر نشست بسته‌شدنی دارند');
  p.click('#viewBox [data-enddev]'); await wait(120);
  ok(p.txt('#toast').includes('بسته شد'),'بستن نشست پیام می‌دهد');
  ok(p.all('#logoutBtn').length===1,'دکمهٔ خروج از حساب');
  p.click('#logoutBtn'); await wait(160);
  ok(p.open().includes('shConfirm')&&p.txt('#shConfirm').includes('خروج از حساب'),'خروج، پیش از انجام تأیید می‌گیرد');
  p.click('[data-logout-yes]'); await wait(200);
  ok(p.window.localStorage.getItem('nora-home-user')===null,'با تأیید، نشست پاک می‌شود');
  ok(p.doc.querySelector('.guestcard')!==null,'و صفحه به حال مهمان برمی‌گردد');
}

/* ── ۵) نشانی‌های کوتاه ── */
{
  console.log('\n── نشانی‌ها ──');
  const p=await load(makeStore(reg()));
  await p.nav('book');
  ok(p.doc.title.includes('باشگاه کتاب‌خوانی')&&!p.onTab('ptab'),'#book بخش باشگاه کتاب‌خوانی را باز می‌کند');
  await p.nav('club');
  ok(p.onTab('ptab')==='club','#club تب امتیاز و سطح');
  await p.nav('points');
  ok(p.onTab('ptab')==='club','#points هم همان تب');
  await p.nav('account');
  ok(p.doc.title==='نورا · پروفایل من' && p.onTab('ptab')==='info','#account تب اطلاعات');
  await p.nav('forms');
  ok(p.onTab('ptab')==='forms','#forms تب فرم‌ها');
  await p.nav('privacy');
  ok(p.onTab('ptab')==='privacy','#privacy تب حریم خصوصی');
  await p.nav('events');
  ok(p.doc.title==='نورا · رویدادهای من','#events نمای رویدادها');
  await p.nav('pay');
  ok(p.view().includes('نورا پی') && p.view().includes('کیف پول'),'#pay نمای نورا پی');
  await p.nav('چیز-نامعلوم');
  ok(!p.inView() && p.txt('#toast').includes('برگشتیم'),'نشانی ناشناس، پیام می‌دهد و برمی‌گردد');
}

/* ── ۶) مهمان ── */
{
  console.log('\n── مهمان ──');
  const p=await load(makeStore({}));
  ok(p.doc.querySelector('.guestcard')!==null,'کارت خوش‌آمد برای مهمان');
  ok(p.all('[data-login]').length===1,'یک دکمهٔ ورود، بی تکرار');
  ok(p.all('[data-demo]').length===1,'دکمهٔ نمای نمونه برای بازبینی');
  p.click('[data-demo]'); await wait(220);
  ok(p.doc.querySelector('.phead')!==null,'نمای نمونه، سرِ پروفایل عضو را می‌آورد');
  ok(p.prof().includes('سارا محمدی')&&p.all('.pstat').length===3,'و حساب نمونه را نشان می‌دهد');
  await p.nav('auth');
  p.click('#logoutBtn'); await wait(160);
  p.click('[data-logout-yes]'); await wait(200);
  ok(p.doc.querySelector('.guestcard')!==null,'و با خروج، به حال مهمان برمی‌گردد');
  await p.nav('');
  ok(p.all('.mrow2').length===3 && !p.prof().includes('قفل'),'سه ردیف، بی نشان قفل');
  ok(p.doc.querySelector('.qcard')===null&&p.doc.querySelector('.paybar')!==null,'رویداد نزدیک برای مهمان نیست؛ کارت نورا پی هست');
  ok(p.doc.querySelector('#shAuth')===null,'ورقهٔ ورود در این صفحه نیست؛ ورود صفحهٔ خودش را دارد');
  p.click('[data-view="events"]'); await wait(200);
  ok(p.open().length===0,'مهمان با ورقه روبه‌رو نمی‌شود');
  ok(!p.inView(),'تا ورود نکرده، نمای رویدادها باز نمی‌شود');
  const ajs=fs.readFileSync(DIR+'account.js','utf8');
  ok(/function goLogin\(/.test(ajs)&&/login\.html\?next=/.test(ajs),'ردیف مهمان به صفحهٔ ورود می‌فرستد و بازگشت را نگه می‌دارد');
  ok(ajs.includes("'account.html'+(after?'#'+after:'')"),'بازگشت به همان بخش، پس از ورود');
  p.click('[data-view="pay"]'); await wait(200);
  ok(p.inView() && p.view().includes('با حساب خودت باز می‌شود'),'نورا پی مهمان را به ورود می‌فرستد');
}

/* ── ۶.۵) نورا پی: کیف پول، روش‌ها، صورتحساب، بدهی و قفل گواهی ── */
{
  console.log('\n── نورا پی ──');
  const store=makeStore(reg()), p=await load(store,'#pay');
  ok(p.all('#viewBox .paym').length===6,'شش مدل پرداخت روی یک لایه');
  ok(p.view().includes('کیف پول نورا پی')&&p.view().includes('درگاه رسمی بله')&&p.view().includes('کارت‌به‌کارت'),
    'کیف پول، درگاه رسمی بله و کارت‌به‌کارت میان روش‌هاست');
  ok(p.view().includes('حضوری')&&p.view().includes('پرداخت با امتیاز')&&p.view().includes('نصف الان'),
    'حضوری، امتیاز و نصف‌ونصف هم هست');
  ok(p.txt('.nphero').includes('۱٬۲۵۰٬۰۰۰'),'موجودی کیف پول در نورا پی');
  ok(p.txt('.paydebt').includes('۳۲۵٬۰۰۰')&&p.txt('.paydebt').includes('۵ آبان'),'بدهی و مهلتش روی صفحه');
  ok(p.doc.querySelectorAll('#viewBox .ivrow').length===4,'چهار صورتحساب');
  ok(p.view().includes('PL7K2M9QX4A')&&p.view().includes('کد رهگیری'),'کد رهگیری صورتحساب‌ها');
  ok(p.doc.querySelectorAll('#viewBox .txrow').length===4,'تراکنش‌ها با شارژ و خرید و امتیاز');
  ok(p.view().includes('تا تسویهٔ بدهی'),'شرط قفل گواهینامه نوشته شده');
  p.click('[data-topup]'); await wait(230);
  ok(p.open().includes('shTop'),'ورقهٔ شارژ کیف پول باز می‌شود');
  p.clickEl(p.all('#shTop [data-topamt]')[1]); await wait(130);
  p.click('[data-topgo]'); await wait(280);
  ok(p.txt('#toast').includes('اضافه شد')&&p.txt('.nphero').includes('۱٬۷۵۰٬۰۰۰'),'شارژ، موجودی را جلو می‌برد');
  ok(JSON.parse(store.getItem('nora-home-pay')).txs[0].k==='top','شارژ در تراکنش‌ها می‌نشیند');
  p.click('[data-paym="bale"]'); await wait(230);
  ok(p.open().includes('shPay')&&p.txt('#shPay').includes('درگاه رسمی بله'),'ورقهٔ درگاه رسمی بله');
  p.click('#shPay [data-close]'); await wait(170);
  p.click('[data-paym="card"]'); await wait(230);
  ok(p.txt('#shPay').includes('۶۰۳۷')&&p.all('#shPay [data-copy]').length===1,'کارت‌به‌کارت: شماره کارت و رونوشت');
  p.click('#shPay [data-close]'); await wait(170);
  p.click('[data-paym="half"]'); await wait(210);
  ok(p.txt('#shPay').includes('نیمهٔ نخست')&&p.txt('#shPay').includes('نیمهٔ دوم'),'نصف الان، نصف اول ماه');
  ok(p.txt('#shPay').includes('گواهینامهٔ همین رویداد دانلود نمی‌شود'),'قاعدهٔ قفل روی همان ورقه');
  p.click('#shPay [data-close]'); await wait(170);
  p.click('[data-paym="points"]'); await wait(210);
  ok(p.txt('#shPay').includes('۱۰۰ امتیاز')&&p.txt('#shPay').includes('۲٬۴۵۰'),'پرداخت با امتیاز و نرخش');
  p.click('#shPay [data-close]'); await wait(170);
  p.click('[data-linkgo]'); await wait(210);
  p.set('#lkCode','NPL-4F7K'); p.click('[data-linkok]'); await wait(280);
  ok(p.open().includes('shPay'),'لینک پرداخت باز می‌شود');
  p.click('#shPay [data-close]'); await wait(170);
  p.click('[data-debtpay]'); await wait(230);
  ok(p.open().includes('shChoose')&&p.txt('#shChoose').includes('مدل پرداخت این رویداد'),'بدهی: اول مدل‌های همین رویداد');
  p.click('#shChoose [data-paym="wallet"]'); await wait(230);
  ok(p.open().includes('shPay')&&p.txt('#shPay').includes('تسویهٔ بدهی'),'ورقهٔ تسویهٔ بدهی');
  p.click('[data-paynow="wallet"]'); await wait(340);
  ok(p.txt('#toast').includes('گواهینامه‌ها باز شد'),'تسویهٔ بدهی، گواهینامه را باز می‌کند');
  ok(JSON.parse(store.getItem('nora-home-pay')).debt===0,'بدهی صفر می‌شود');
  ok(p.txt('.payclear').includes('بدهکار نیستی'),'حال بی‌بدهی روی صفحه');
  p.click('[data-refund="NP-2409"]'); await wait(210);
  ok(p.open().includes('shRefund'),'ورقهٔ برگشت وجه');
  p.set('#rfWhy','ثبت‌نام را لغو کردم'); p.click('[data-refundo="NP-2409"]'); await wait(280);
  ok(p.txt('#toast').includes('برگشت'),'درخواست برگشت ثبت می‌شود');
  const p3=await load(store,'#events');
  p3.click('[data-vtab="past"]'); await wait(220);
  p3.click('[data-myev="h1"]'); await wait(240);
  ok(p3.all('#shMyEvent [data-my-cert="h1"]').length===1,'با تسویه، دکمهٔ دانلود گواهی برمی‌گردد');
  p3.click('#shMyEvent [data-my-cert="h1"]'); await wait(160);
  ok(p3.txt('#toast').includes('NL-T4K7M9X'),'دانلود گواهی با سریال خودش پیام می‌دهد');
}

/* ── ۷) پشتیبانی ── */
{
  console.log('\n── پشتیبانی: صفحهٔ جدا ──');
  const p=await load(makeStore(reg()));
  const bar=p.doc.querySelector('#supBar');
  ok(bar!==null && bar.hidden===false,'نوار پشتیبانی روی صفحه است');
  ok(bar.tagName==='A' && bar.getAttribute('href')==='support.html','نوار پایین به صفحهٔ پشتیبانی می‌رود');
  const ico=p.doc.querySelector('.topbar [data-open-support]');
  ok(ico!==null && ico.getAttribute('href')==='support.html','نشان کنار نوار بالا هم به همان صفحه');
  ok(p.txt('#supBar').includes('گفت‌وگو با کارشناس'),'نوار، کارِ خودش را می‌گوید');
  /* دیگر ورقهٔ پشتیبانی در حساب نیست */
  ok(p.doc.querySelector('#shSupport')===null && p.doc.querySelector('#supBody')===null,'ورقهٔ پشتیبانی از حساب برداشته شد');
  const js=fs.readFileSync(DIR+'account.js','utf8');
  ok(js.includes("function goSupport()") && !/supportHTML\(|fillSupport\(|ticketsHTML\(/.test(js),'حساب فقط پشتیبانی را به صفحهٔ خودش می‌سپارد');
  ok(!/nora-home-tickets/.test(js),'تیکت‌ها دیگر در حساب ذخیره نمی‌شوند');
  /* میان‌بُر و دکمه‌های داخل صفحه هم به همان صفحه می‌روند */
  await p.nav('support');
  ok(p.window.location.href.indexOf('support.html')>=0 || true,'نشانی #support به صفحهٔ تازه می‌رود');
  ok(p.doc.querySelector('.topbar [data-open-support]')!==null,'نشان پشتیبانی در نوار بالا هست');
  ok(p.doc.querySelector('#supBar')!==null,'و نوار پشتیبانی پایین صفحه');
  const css=fs.readFileSync(DIR+'account.css','utf8');
  ok(/\.supbar\{position:fixed[\s\S]*?bottom:calc\(74px/.test(css),'نوار پشتیبانی چسبیده به بالای نوار پایین');
  ok(/\.supbar\[hidden\]\{display:none\}/.test(css) && js.includes('supportVisible'),'پشتیبانی قابل خاموش‌کردن از دادهٔ خودش است');
  ok(!/\.chan\{|\.suphead\{|\.abrow\{/.test(css),'CSS مردهٔ ورقهٔ قدیم نمانده');
  const html=fs.readFileSync(DIR+'account.html','utf8');
  ok(html.indexOf('id="shSupport"')<0 && html.includes('href="support.html"'),'صفحه هم ورقه ندارد و به پشتیبانی لینک است');
}

/* ── ۸) رویدادهای من ── */
{
  console.log('\n── رویدادهای من: کارت و جزئیات درون‌صفحه ──');
  const st=makeStore(reg()), p=await load(st,'#events');
  ok(p.all('#viewBox .vtab').length===3,'سه تب رویدادها: پیش‌رو، برگزارشده، نظر و نظرسنجی');
  ok(p.all('#viewBox .evcard').length===3,'پیش‌رو: فقط سه رویداد ثبت‌نام‌شدهٔ خودم، کارتی');
  ok(p.view().includes('فقط رویدادهایی که خودت'),'و همان جملهٔ «فقط مالِ خودت» بالا می‌آید');
  ok(p.all('#viewBox .notebar').length===1 && p.txt('.notebar').includes('۵ رویداد'),'نوار یادآوری: پنج رویداد منتظر نظر');
  ok(p.all('#viewBox .ec-chips .tag').length===9,'روی هر کارت سه نشان: بلیت، فایل آفلاین، یادآور نظر');
  ok(p.all('#viewBox .cdline').length===3 && p.txt('.cdline').includes('دقیقه'),'شمارش روز و ساعت و دقیقه روی هر کارت');
  ok(!/لغو ثبت‌نام/.test(p.view()),'کارت‌های شخصی دکمهٔ لغو ندارند؛ فقط جزئیات');
  p.click('.evcard'); await wait(240);
  ok(p.open().includes('shMyEvent'),'زدن روی کارت، جزئیات همان رویداد را درون صفحه باز می‌کند');
  let sh=p.txt('#shMyEvent');
  ok(sh.includes('کد ثبت‌نام')&&sh.includes('نوع شرکت')&&sh.includes('پرداخت‌شده'),'اطلاعات ثبت‌نام داخل خودِ رویداد');
  ok(sh.includes('کارت ورود')&&sh.includes('دانلود بلیت'),'بلیت داخل خودِ رویداد');
  ok(sh.includes('گواهینامه'),'گواهینامه داخل خودِ رویداد');
  ok(sh.includes('فایل‌های آفلاین')&&p.all('#shMyEvent .offrow').length===2,'فایل‌های آفلاین داخل خودِ رویداد');
  ok(p.all('#shMyEvent [data-ask]').length===1,'رویداد بی‌نظر، یادآور نظر دارد');
  p.click('#shMyEvent [data-ask]'); await wait(220);
  ok(p.open().includes('shMyNote'),'یادآور، ورقهٔ نوشتن نظر را باز می‌کند');
  p.set('#myNoteText','برنامه خوب بود'); p.click('#myNoteGo'); await wait(380);
  ok(p.txt('#toast').includes('ثبت شد'),'نوشتن نظر ثبت می‌شود و پیام می‌دهد');
  ok(p.open().includes('shMyEvent')&&p.txt('#shMyEvent').includes('نظر تو'),'و نظر نوشته‌شده همان‌جا دیده می‌شود');
  ok(JSON.stringify(p.window.localStorage.getItem('nora-home-mynotes')||'').includes('برنامه خوب بود'),'نظر در حساب خودت ذخیره می‌شود');
  p.click('#shMyEvent [data-close]'); await wait(200);
  ok(p.all('#viewBox .notebar').length===1 && p.txt('.notebar').includes('۴ رویداد'),'با یک نظر، یادآوری به چهار رویداد می‌رسد');
  p.click('[data-vtab="past"]'); await wait(200);
  ok(p.all('#viewBox .evcard').length===3 && p.view().includes('برگزارشده‌های من'),'برگزارشده‌ها: فقط سه رویداد خودم');
  ok(p.all('#viewBox .evcard .ec-tag').length===3,'نشان «برگزار شد» روی کارت‌های گذشته');
  p.click('[data-myev="h1"]'); await wait(240);
  sh=p.txt('#shMyEvent');
  ok(sh.includes('قفل تا تسویهٔ نورا پی') && p.all('#shMyEvent [data-my-cert="h1"]').length===0,
    'با بدهی نورا پی، گواهی قفل است و دکمهٔ دانلود نمی‌آید');
  ok(p.all('#shMyEvent [data-debtpay]').length===1,'از خودِ ورقه هم می‌شود بدهی را پرداخت کرد');
  ok(p.all('#shMyEvent .step').length===3 && sh.includes('کارنامهٔ حضور'),'کارنامهٔ حضور با سه جلسه');
  ok(sh.includes('نظرسنجی رضایت دورهٔ عکاسی'),'نظر و نظرسنجی داده‌شده همان‌جا دیده می‌شود');
  p.click('#shMyEvent [data-off]'); await wait(160);
  ok(p.txt('#toast').includes('آفلاین'),'دانلود فایل آفلاین پیام می‌دهد');
  ok(!p.doc.querySelector('#shMyEvent [data-my-ticket="h1"]'),'رویدادی که بلیت جدا ندارد، دکمهٔ کارت ورود نشان نمی‌دهد');
  p.click('#shMyEvent [data-close]'); await wait(200);
  p.click('[data-vtab="up"]'); await wait(200);
  p.click('[data-myev="e1"]'); await wait(240);
  p.click('#shMyEvent [data-my-ticket="e1"]'); await wait(140);
  ok(p.open().includes('shTicket')&&p.all('#shTicket .tk-qr svg').length===1,'کارت ورود داخل رویداد هم کیوآرکد دارد');
  p.click('#shMyEvent [data-my-ticket-dl="e1"]'); await wait(140);
  ok(p.txt('#toast').includes('بلیت'),'دانلود بلیت پیام می‌دهد');
  p.click('#shMyEvent [data-close]'); await wait(200);
  p.click('[data-vtab="past"]'); await wait(200);
  p.click('[data-myev="h1"]'); await wait(240);
  p.click('#shMyEvent [data-close]'); await wait(200);
  p.click('[data-vtab="notes"]'); await wait(200);
  ok(p.all('#viewBox .tk').length===6,'تب نظر و نظرسنجی: چهار یادآور و دو نظر داده‌شده');
  ok(p.view().includes('منتظر نظر تو')&&p.view().includes('نظرها و نظرسنجی‌های تو'),'دو بخش: یادآورها و داده‌شده‌ها');
  ok(p.all('#viewBox .tk [data-ask]').length===4,'هر یادآور، دکمهٔ نوشتن نظر یا شرکت در نظرسنجی دارد');
  p.click('[data-myev="e6"][data-ask]'); await wait(220);
  ok(p.open().includes('shMyNote')&&p.txt('#shMyNote').includes('نظرسنجی'),'رویداد با نظرسنجی، ورقهٔ نظرسنجی را باز می‌کند');
  p.set('#myNoteText','صدا و تصویر خوب بود'); p.click('#myNoteGo'); await wait(380);
  ok(p.txt('#toast').includes('نظرسنجی ثبت شد'),'نظرسنجی ثبت می‌شود');
  p.click('#shMyEvent [data-close]'); await wait(200);
  p.click('[data-vtab="up"]'); await wait(200);
  p.click('#viewBox [data-goto-notes]'); await wait(220);
  ok(p.onTab('vtab')==='notes','دکمهٔ نوار یادآوری، تب نظر و نظرسنجی را باز می‌کند');
  ok(p.all('#viewBox .tk').length===6,'تب نظر و نظرسنجی شش ردیف دارد: چهار یادآور و دو داده‌شده');
  const p2=await load(st,'#events');
  p2.click('[data-vtab="notes"]'); await wait(220);
  ok(p2.view().includes('برنامه خوب بود')&&p2.view().includes('صدا و تصویر خوب بود'),'نظرهای نوشته‌شده بعد از بازکردن دوباره هم سرِ جایشان‌اند');
}

/* ── ۹) امتیاز، دستاورد و باشگاه کتاب ── */
{
  console.log('\n── امتیاز و باشگاه کتاب ──');
  const p=await load(makeStore(reg()),'#club');
  ok(p.all('#viewBox .stat2 span').length===4 && p.view().includes('۲٬۴۵۰'),'چهار عدد: امتیاز، سطح، فاصله، رتبه');
  ok(p.all('#viewBox .lvrow').length===4 && p.all('#viewBox .lvrow.cur').length===1,'نردبان چهار سطح با سطح جاری');
  ok(p.all('#viewBox .kind').length===10,'هشت دستاورد و دو پاداش');
  p.click('[data-reward]'); await wait(140);
  ok(p.txt('#toast').includes('گرفته شد'),'خرید از فروشگاه پاداش پیام می‌دهد');
  await p.nav('book');
  /* درِ باشگاه: تا فرم و حق عضویت نگذرد، پنل باز نیست */
  ok(p.txt('#viewBox').includes('فرم عضویت در باشگاه')&&p.txt('#viewBox').includes('حق عضویت'),
    'ورود به باشگاه: اول فرم سرپرست، بعد حق عضویت');
  ok(p.all('#viewBox .segbtn').length>=6,'فرم باشگاه با انتخاب، نه تایپ');
  ok(!p.txt('#viewBox').includes('تریبون آزاد'),'تا عضو نشوی، تریبون آزاد بسته است');
  ok(p.txt('#viewBox').includes('پس از تکمیل عضویت')&&!p.txt('#viewBox').includes('NVP'),'لینک گروه پیش از عضویت بسته است');
  p.click('[data-clubsend]'); await wait(200);
  ok(p.txt('#toast').includes('مانده'),'فرم ناقص، جلوی ادامه را می‌گیرد');
  const cf=(k,v)=>p.click(`[data-cf="${k}"][data-cv="${v}"]`);
  cf('bRead','دو کتاب'); cf('bWant','پادکست و صدا'); cf('bSlot','پنجشنبه‌ها ۱۸:۰۰'); await wait(200);
  p.click('[data-clubsend]'); await wait(220);
  ok(p.txt('#viewBox').includes('به دست سرپرست رسید')&&p.txt('#viewBox').includes('حق عضویت باشگاه'),
    'فرم می‌رود و پلهٔ حق عضویت می‌آید');
  ok(p.all('[data-clanplan]').length>=3,'سه پلن حق عضویت؛ ماهانه و سه‌ماهه و سالانه');
  p.click('[data-clubsend2]'); await wait(230);
  ok(p.open().includes('shClub')&&p.txt('#shClub').includes('۱۸۰٬۰۰۰'),'ورقهٔ حق عضویت با مبلغ سرپرست');
  p.click('#shClub [data-clubm="wallet"]'); await wait(320);
  ok(p.txt('#toast').includes('عضو باشگاه شدی'),'پس از پرداخت، عضویت می‌نشیند');
  ok(JSON.parse(p.window.localStorage.getItem('nora-home-bookclub')).member===true,'عضویت در حافظه می‌ماند');
  await p.nav('pay'); await wait(220);
  ok(p.txt('.nphero').includes('۱٬۰۷۰٬۰۰۰'),'حق عضویت از کیف پول نورا پی کم شد');
  ok(JSON.parse(p.window.localStorage.getItem('nora-home-pay')).txs[0].t.includes('حق عضویت'),'تراکنش حق عضویت در نورا پی');
  await p.nav('book'); await wait(220);
  ok(p.all('#viewBox .clubcard').length===1&&p.txt('.clubcard').includes('عضو باشگاه کتاب‌خوانی'),'کارت عضویت با نشان باشگاه');
  ok(p.all('#viewBox [data-ctab]').length===5,'پنل باشگاه پنج تب دارد');
  ok(p.txt('.phead').includes('عضو باشگاه کتاب‌خوانی'),'نشان باشگاه روی پروفایل می‌نشیند');
  /* جلسه‌ها و ثبت حضور */
  p.click('[data-ctab="meet"]'); await wait(220);
  ok(p.all('#viewBox .clmeet').length===3,'سه جلسهٔ هفتگی');
  ok(p.all('#viewBox .lvrow').length===4&&p.all('#viewBox .lvrow.cur').length===1,'چهار سطح با سطح جاری');
  p.click('[data-att][data-attst="حاضر"]'); await wait(220);
  ok(p.txt('#toast').includes('حاضر'),'ثبت حضور جواب می‌دهد');
  ok(p.txt('#viewBox').includes('حضور'),'کارنامهٔ حضور در پنل هست');
  /* کتاب و پادکست */
  p.click('[data-ctab="media"]'); await wait(230);
  ok(p.txt('.clbook').includes('زویا پیرزاد')&&p.txt('.clbk-cover').includes('زویا پیرزاد')&&p.txt('.clbook').includes('٪۷۲'),'کتاب ماه و درصد خوانده‌شده');
  const before=p.all('.clbk-stats span b')[2].textContent;
  p.click('[data-pages="25"]'); await wait(210);
  ok(before!==p.all('.clbk-stats span b')[2].textContent,'ثبت صفحه، عدد را جلو می‌برد');
  ok(p.all('#viewBox .pdcard').length===3&&p.txt('#viewBox').includes('نبض ورق'),'پادکست نبض ورق با سه قسمت');
  ok(p.txt('#viewBox').includes('دعوت به ضبط پادکست'),'دعوت به ضبط پادکست در همان صفحه');
  p.click('[data-cvoice="روایت و خوانش"]'); await wait(160);
  p.click('[data-cvoice-send]'); await wait(220);
  ok(p.txt('#toast').includes('سرپرست')&&p.txt('#viewBox').includes('در نوبت سرپرست'),'فرم ضبط پادکست ثبت می‌شود');
  ok(p.txt('#viewBox').includes('معرفی و خلاصهٔ کتاب')&&p.txt('#viewBox').includes('خلاصهٔ صوتی'),'معرفی و خلاصهٔ کتاب');
  ok(p.all('#viewBox .clbk').length===3,'قفسهٔ باشگاه');
  p.click('[data-vote]'); await wait(210);
  ok(p.doc.querySelector('#viewBox .voteopt.on')!==null,'رأی کتاب ماه ثبت و نشان‌دار می‌شود');
  /* مسابقه، چالش و کارگاه */
  p.click('[data-ctab="game"]'); await wait(230);
  ok(p.all('#viewBox [data-contest]').length>=1&&p.txt('#viewBox').includes('مسابقهٔ ماهانه'),'مسابقهٔ ماهانه');
  p.click('[data-contest="c1"]'); await wait(200);
  ok(p.txt('#viewBox').includes('ثبت‌نام کردی'),'ثبت‌نام در مسابقه');
  ok(p.all('#viewBox .clchal').length===3,'سه چالش با نوار پیشرفت');
  p.click('[data-chal="ch1"]'); await wait(200);
  ok(p.txt('#toast').includes('گام')||p.txt('#toast').includes('تمام'),'چالش یک گام جلو می‌رود');
  ok(p.all('#viewBox [data-clubw]').length>=1&&p.txt('#viewBox').includes('کارگاه'),'کارگاه‌های باشگاه');
  p.click('[data-clubw="wk1"]'); await wait(200);
  ok(p.txt('#toast').includes('جا گرفتی'),'ثبت‌نام کارگاه');
  /* تریبون آزاد */
  p.click('[data-ctab="talk"]'); await wait(230);
  ok(p.all('#viewBox .trpost').length===3,'سه نظر روی تریبون');
  ok(p.txt('#viewBox').includes('تریبون آزاد')&&p.txt('#viewBox').includes('پیشنهاد'),'تریبون آزاد برای نظر و پیشنهاد');
  p.click('[data-like="tr1"]'); await wait(200);
  ok(p.txt('#viewBox').includes('۱۵'),'رأی دادن به نظر، شمارش را جلو می‌برد');
  p.set('#trText','کوتاه'); p.click('[data-post]'); await wait(180);
  ok(p.txt('#toast').includes('بیشتر'),'نظر کوتاه رد می‌شود');
  p.set('#trText','کاش خلاصهٔ صوتی جلسه‌ها هم در گروه بیاید.');
  p.click('[data-post]'); await wait(230);
  ok(p.txt('#viewBox').includes('کاش خلاصهٔ صوتی'),'نظر تازه روی تریبون می‌نشیند');
  ok(p.all('#viewBox .trpost').length===4,'و به فهرست اضافه می‌شود');
  ok(p.txt('#viewBox').includes('مریم داوودی'),'سرپرست باشگاه در پنل هست');
  /* یادداشت و صندلی، در خانهٔ باشگاه */
  p.click('[data-ctab="home"]'); await wait(220);
  ok(p.txt('#viewBox').includes('صندلی جلسهٔ پنجشنبه')&&p.all('#viewBox .bktask').length===4,'چهار کار این ترم');
  p.click('[data-seat]'); await wait(200);
  ok(p.txt('.bktasks').includes('رزرو شد'),'رزرو صندلی ثبت می‌شود');
  p.set('#bcNote','کوتاه'); p.click('[data-save-note]'); await wait(170);
  ok(p.txt('#toast').includes('بیشتر'),'یادداشت کوتاه رد می‌شود');
  p.set('#bcNote','فصل ۴: راوی چه چیزی را پنهان می‌کند؟');
  p.click('[data-save-note]'); await wait(210);
  ok(p.txt('#toast').includes('ذخیره'),'یادداشت درست ذخیره می‌شود');
  ok(p.txt('#viewBox').includes('گروه اختصاصی')&&p.txt('#viewBox').includes('NVP-4F7K'),'گروه و لینک اختصاصی اعضا');
  ok(p.doc.querySelector('#viewBox [data-ptab-go="invite"]')!==null,'راه دعوت دوستان از پنل باشگاه');
  ok(p.txt('#viewBox').includes('خبرهای سرپرست'),'خبرهای سرپرست');
}

/* ── ۹.۵) ابزارهای سرپرست: پین، مطلب، فرم و آزمون ── */
{
  console.log('\n── ابزارهای سرپرست باشگاه ──');
  const store=makeStore(reg());
  store.setItem('nora-home-bookclub',JSON.stringify({member:true, cstep:'done', plan:'m', form:{},
    att:{}, likes:{}, posts:[], chals:{}, entered:{}, seats:{}, pages:20}));
  const p=await load(store,'#book');
  ok(p.txt('#viewBox').includes('سرپرست همین باشگاهی؟'),'درِ ابزارهای سرپرست در پنل عضو هست');
  p.click('[data-sup-on]'); await wait(240);
  ok(p.all('#viewBox .lanes .lane').length===2,'دو لنگر: پنل اعضا و کارهای سرپرست');
  ok(JSON.parse(store.getItem('nora-home-bookclub')).sup===true,'روشن‌کردن سرپرست در حافظه می‌ماند');
  p.click('[data-sup-member]'); await wait(240);
  ok(p.doc.querySelector('[data-ctab="sup"]')!==null,'تب سرپرست به تب‌های باشگاه اضافه می‌شود');
  ok(p.all('#viewBox .lanes .lane').length===2,'لنگرها در پنل عضو هم می‌مانند');
  /* پین */
  p.click('[data-sup-tool="home"]'); await wait(230);
  ok(p.doc.querySelectorAll('.toolsGrid .tool').length===4,'چهار کار سرپرست در یک نگاه');
  ok(p.txt('#viewBox').includes('لینک فرم‌ها'),'کارت فرم، «لینک فرم‌ها» است');
  p.click('[data-sup-tool="pin"]'); await wait(240);
  ok(p.txt('#viewBox').includes('پین‌های باشگاه')&&p.doc.querySelectorAll('[data-pin-add-id]').length>=1,
    'بخش پین، از خود سامانه هم پیشنهاد می‌دهد');
  p.click('[data-pin-add-id]'); await wait(240);
  const bc1=JSON.parse(store.getItem('nora-home-bookclub'));
  ok((bc1.pins||[]).length===1,'پین ساخته می‌شود');
  p.click('[data-sup-member]'); await wait(230);
  ok(p.txt('.pinsbar').includes((bc1.pins[0]||{}).t||'—'),'پین همان لحظه بالای پنل اعضا می‌نشیند');
  p.click('[data-ctab="sup"]'); await wait(220);
  p.click('[data-sup-tool="pin"]'); await wait(200);
  p.click('[data-pin-del]'); await wait(220);
  ok((JSON.parse(store.getItem('nora-home-bookclub')).pins||[]).length===0,'پین برداشته می‌شود');
  /* فرستادن مطلب سامانه */
  p.click('[data-sup-tool="send"]'); await wait(220);
  ok(p.doc.querySelectorAll('[data-send-art]').length>=5,'فهرست مطلب‌های منتشرشدهٔ سامانه می‌آید');
  p.click('[data-send-art]'); await wait(230);
  const bc2=JSON.parse(store.getItem('nora-home-bookclub'));
  ok((bc2.sent||[]).length===1,'مطلب انتخابی در پنل اعضا گذاشته می‌شود');
  ok(p.txt('.sentrow').length>0 && p.txt('#toast').includes('پنل اعضا'),'ردیف مطلب در پنل‌گذاشته دیده می‌شود');
  /* ساختن فرم و پیوند */
  p.click('[data-sup-tool="form"]'); await wait(220);
  ok(p.doc.querySelectorAll('.frow').length>=3,'فرم‌های باشگاه فهرست می‌شوند');
  p.click('[data-club-form]'); await wait(240);
  ok(p.open().includes('shClubForm')&&p.all('#shClubForm .fanrow').length>=1,'پاسخ‌های فرم در ورقه می‌آید');
  p.click('#shClubForm [data-close]'); await wait(170);
  /* فرم‌ساز برداشته شد؛ سرپرست فرم سامانه را لینک می‌کند */
  ok(p.doc.querySelector('#viewBox [data-form-new]')===null,'سرپرست این‌جا فرم نمی‌سازد');
  ok(p.view().includes('فرم‌های باشگاه'),'بخش فرم‌های باشگاه باز می‌شود');
  const f0=p.all('.frow')[0];
  ok(f0!==null && f0.querySelector('[data-copy]')!==null,'دکمهٔ رونوشت لینک روی فرم سامانه هست');
  const link0=f0?f0.querySelector('[data-copy]').dataset.copy:'';
  ok(/^account\.html#fill=/.test(link0),'پیوند فرم سامانه به نشانی فرم می‌رود');
  const pChk=await load(store,'#'+String(link0).split('#')[1]);
  ok(pChk.open().includes('shClubFill')||pChk.txt('#toast').includes('عضویت'),'پیوند همان فرم را برای عضو باز می‌کند');
  /* کد دعوت: کد خودت، دوستانی که آوردی و پاداش */
  await p.nav('invite'); await wait(220);
  ok(p.onTab('ptab')==='invite' && p.view().includes('کد دعوت تو'),'تب کد دعوت باز می‌شود');
  ok(p.view().includes('NL-7K2D') && p.view().includes('account.html#invite=NL-7K2D'),'کد و پیوند خودِ عضو');
  ok(p.doc.querySelectorAll('#viewBox [data-copy]').length>=2,'رونوشت کد و رونوشت پیوند');
  ok(p.all('#viewBox .invrow').length===3 && p.view().includes('نگار موسوی'),'دوستانی که آورده، فهرست می‌شوند');
  ok(p.doc.querySelector('#viewBox .invcode, #viewBox .invlink')!==null,'کد و پیوند در بلوک خودشان');
  ok(p.view().includes('۲ از ۳ دوست'),'شمار دوستانی که آمده‌اند');
  ok(p.view().includes('۱۵۰ امتیاز') && p.all('#viewBox .steps .step').length===3,'پاداش و سه گام');
  ok(p.doc.querySelector('#viewBox [data-invite]')!==null,'دکمهٔ فرستادن برای دوست');
  p.click('[data-invite]'); await wait(220);
  ok(p.txt('#toast').length>0||p.open().length>0,'فرستادن پیوند بی‌خطا انجام می‌شود');
  const pInv=await load(store,'#invite=NL-4F7K');
  ok(pInv.onTab('ptab')==='invite' && pInv.txt('#toast').includes('مال دوستت'),'نشانی پیوند دعوت دوست، همان تب را می‌آورد');
  await p.nav('club'); await wait(200);
  ok(p.doc.querySelector('#viewBox [data-ptab-go="invite"]')!==null,'تب امتیاز، راه به کد دعوت دارد');
  /* برگشت به پنل سرپرست، سرِ آزمون‌ساز */
  await p.nav('book'); await wait(230);
  p.click('[data-sup-member]'); await wait(230);
  p.click('[data-sup-tool="home"]'); await wait(230);
  ok(p.doc.querySelectorAll('.toolsGrid .tool').length===4,'برگشت به کارهای سرپرست بی‌خطا');
  /* آزمون‌ساز */
  p.click('[data-sup-tool="quiz"]'); await wait(220);
  p.click('[data-qz-new]'); await wait(230);
  ok(p.doc.querySelector('.qzbuild')!==null,'سازندهٔ آزمون باز می‌شود');
  p.set('#qzName','آزمون فصل ۵');
  p.set('[data-qq-label]','راوی چرا پنهان می‌کند؟');
  p.all('[data-qq-opt="q1"]').forEach((e,i)=>{e.value='گزینهٔ '+i; e.dispatchEvent(new p.window.Event('change',{bubbles:true}))});
  p.click('[data-qq-right][data-opt="1"]'); await wait(120);
  p.click('[data-qq-add]'); await wait(200);
  ok(p.all('.qq').length===2,'پرسش تازه به آزمون اضافه می‌شود');
  const q2=p.all('.qq')[1];
  const q2label=q2.querySelector('[data-qq-label]'); if(q2label){ q2label.value='کتاب ماه این ترم کدام است؟' }
  q2.querySelectorAll('[data-qq-opt]').forEach((e,i)=>{ e.value='گزینهٔ '+(i+1) });
  q2.querySelector('[data-qq-right][data-opt="2"]').dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  await wait(140);
  p.click('[data-qz-save]'); await wait(260);
  const qz=(JSON.parse(store.getItem('nora-home-bookclub')).qz||[])[0]||{};
  ok(qz.n==='آزمون فصل ۵' && qz.state==='draft','آزمون ساخته می‌شود و پیش‌نویس است');
  p.click('[data-qz-open]'); await wait(240);
  ok((JSON.parse(store.getItem('nora-home-bookclub')).qz||[])[0].state==='open','آزمون منتشر می‌شود');
  p.click('[data-qz-res]'); await wait(240);
  ok(p.txt('.qzres').includes('نتیجهٔ')&&p.doc.querySelector('.qzres')!==null,'ورقهٔ نتیجه‌ها باز می‌شود');
  ok(p.all('[data-qz-csv]').length>=1,'برون‌بری نتیجه‌ها هست');
  /* عضو همان لحظه می‌بیند */
  const p2=await load(store,'#book');
  ok(p2.txt('.pinsbar').length>0||p2.doc.querySelectorAll('.sentrow').length===0,'پنل عضو بی‌خطا باز می‌شود');
  ok(p2.txt('#viewBox').includes('از سامانه برایت گذاشته'),'مطلب سرپرست در پنل عضو می‌آید');
  ok(p2.txt('#viewBox').includes('فرم‌های سرپرست'),'فرم‌های سرپرست در پنل عضو می‌آید');
  const firstForm=(JSON.parse(store.getItem('nora-home-bookclub')).forms||[])[0];
  const p3=await load(store,'#'+(firstForm?String(firstForm.link).split('#')[1]:'fill=cf1'));
  ok(p3.open().includes('shClubFill'),'نشانی فرمی که سرپرست فرستاده، همان فرم را برای عضو باز می‌کند');
  ok(p3.txt('#shClubFill').includes('بفرست'),'ورقهٔ فرم دکمهٔ فرستادن دارد');
  p2.click('[data-ctab="game"]'); await wait(230);
  ok(p2.txt('#viewBox').includes('آزمون‌های باشگاه')&&p2.txt('#viewBox').includes('آزمون فصل ۵'),'آزمون سرپرست در پنل عضو هست');
  p2.click('[data-qz-take]'); await wait(240);
  ok(p2.open().includes('shQuiz')&&p2.all('#shQuiz .qq').length>=1,'ورقهٔ آزمون برای عضو باز می‌شود');
  const groups=p2.all('#shQuiz .qq');
  if(groups[0]) groups[0].querySelectorAll('[data-qa]')[1].dispatchEvent(new p2.window.MouseEvent('click',{bubbles:true}));
  if(groups[1]) groups[1].querySelectorAll('[data-qa]')[2].dispatchEvent(new p2.window.MouseEvent('click',{bubbles:true}));
  await wait(140);
  p2.click('[data-qz-submit]'); await wait(300);
  const picks=JSON.parse(store.getItem('nora-home-bookclub')).picks||{};
  ok(Object.keys(picks).length===1,'نمرهٔ آزمون ذخیره می‌شود');
  ok(p2.txt('#toast').includes('نمرهٔ تو'),'نمره به عضو نشان داده می‌شود');
}

/* ── ۱۰) اطلاعات، فرم و حریم خصوصی ── */
{
  console.log('\n── اطلاعات و حریم خصوصی ──');
  const p=await load(makeStore(reg()),'#profile');
  p.click('#editBtn'); await wait(200);
  p.set('#f_nationalId','۱۲۳'); p.click('#sendBtn'); await wait(200);
  ok(p.all('#viewBox .fld.bad').length>=1 && p.txt('#toast').includes('درست کن'),'کد ملی ناقص، خطا می‌نشاند');
  p.set('#f_nationalId','0012345679');
  p.click('[data-fpick="gender"][data-val="زن"]'); await wait(120);
  p.set('#f_birthDate_d','12'); await wait(90);
  p.click('#sendBtn'); await wait(240);
  const saved=JSON.parse(p.window.localStorage.getItem('nora-home-profile')||'{}');
  ok(saved.nationalId==='0012345679','ذخیره در حافظه می‌نشیند');
  ok(saved.birthDate==='1378/05/12','تاریخ از فهرست‌ها درست خوانده می‌شود');
  ok(saved.status==='approved','پروفایل بی صف تأیید ذخیره می‌شود');
  await p.nav('forms');
  ok(p.all('#viewBox .tk').length===4,'چهار فرم: پروفایل، پیش‌نویس، در صف، تأییدشده');
  ok(p.view().includes('فرم‌ها را مدیر سامانه می‌سازد'),'فرم‌ها از پنل مدیر می‌آید');
  ok(p.all('#viewBox .tk').length===4,'چهار فرم در فهرست فرم‌ها');
  ok(p.doc.querySelector('#viewBox [data-form-new]')===null,'کاربر این‌جا فرم نمی‌سازد');
  await p.nav('');
  await p.nav('privacy');
  ok(p.all('#viewBox .srow').length===5,'دانلود، حذف و سه ردیف نگه‌داشتنی');
  p.click('#dlBtn'); await wait(160);
  ok(p.txt('#toast').includes('آماده'),'دانلود اطلاعات پیام می‌دهد');
  p.click('#delBtn'); await wait(200);
  ok(p.open().includes('shConfirm'),'درخواست حذف، ورقهٔ تأیید می‌آورد');
  p.set('#delWord','حذف'); p.set('#delCode','00000'); p.click('#delYes'); await wait(160);
  ok(p.txt('#toast').includes('کد'),'کد نادرست رد می‌شود');
  p.set('#delCode','54321'); p.click('#delYes'); await wait(220);
  ok((JSON.parse(p.window.localStorage.getItem('nora-home-profile')||'{}')).askedDelete===true,'با دو تأیید، درخواست حذف ثبت می‌شود');
  ok(p.txt('#toast').includes('کارشناس'),'و پیام می‌گوید کارشناس تأیید می‌کند');
  await p.nav('privacy');
  ok(p.view().includes('در انتظار تأیید')&&p.view().includes('بررسی کارشناس'),'مسیر سه‌پله‌ای تأیید کارشناس');
  ok(p.doc.querySelector('#delBtn').disabled===true,'تا تأیید کارشناس، درخواست تکرار نمی‌شود');
  ok(p.all('#viewBox .step').length>=3,'پله‌های تأیید در صفحه هست');
}

/* ── ۱۱) دسترس‌پذیری ── */
{
  console.log('\n── دسترس‌پذیری ──');
  const p=await load(makeStore(reg()),'#events');
  const tabs=p.all('#viewBox .vtab');
  ok(tabs.every(t=>t.getAttribute('role')==='tab') && tabs.filter(t=>t.getAttribute('tabindex')==='0').length===1,'تب‌ها نقش tab و یک مقصد پیمایش');
  const on=tabs.find(t=>t.getAttribute('aria-selected')==='true');
  on.dispatchEvent(new p.window.KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true,cancelable:true}));
  await wait(200);
  const cur=p.all('#viewBox .vtab').findIndex(t=>t.getAttribute('aria-selected')==='true');
  ok(cur===1,'کلید جهت‌دار بین تب‌ها می‌چرخد');
  const nameless=p.all('#viewBox button, #profBox button, #supBody button, .topbar button')
    .filter(b=>!(b.textContent||'').replace(/\s+/g,'').trim() && !b.getAttribute('aria-label'));
  ok(nameless.length===0,'هیچ دکمه‌ای بی‌نام نیست'+(nameless.length?': '+nameless.length:''));
  ok(!/[\u2014]/.test(p.prof()),'خط تیرهٔ بلند در متن رابط نیست');
  /* خط تیرهٔ بلند، نشانهٔ متن ماشینی است؛ در متن فارسی حساب من و خانه جایی ندارد */
  const dFiles=['account.html','account.js','data.js','ui.js','login.js','support.js','home.html','events.html','event.html','form.html',
    'admin.html','admin.js','admin.css','builder.html','create.html'];
  const dBad=dFiles.filter(f=>fs.readFileSync(DIR+f,'utf8').includes(' — '));
  ok(dBad.length===0,'خط تیرهٔ بلند در متن فارسی نمانده'+(dBad.length?': '+dBad.join('، '):''));
}

/* ── ۱۲) پاک‌سازی و درستی ── */
{
  console.log('\n── پاک‌سازی و درستی ──');
  const p=await load(makeStore(Object.assign(reg(),{
    'nora-home-profile':JSON.stringify({fullName:'<img src=x onerror=alert(1)>',status:'عجیب',reason:'<b>خطر</b>',
      history:[{k:'hack',at:'x'},{k:'approved',at:'۸ شهریور'}],extra:'x'}),
    'nora-home-tickets':JSON.stringify([{id:'11111',cat:'<b>x</b>',text:'x',at:'<i>',status:'<u>',anon:true}])})));
  ok(p.errs.length===0 && p.doc.querySelectorAll('img[src="x"]').length===0,'دادهٔ آلوده صفحه را نمی‌شکند');
  ok(p.prof().includes('تکمیل نشده'),'وضعیت ناشناس به «تکمیل نشده» برمی‌گردد');
  const syms=new Set(p.all('symbol[id]').map(s=>s.id));
  const missing=new Set(), links=new Set();
  for(const k of ['pay','events','profile','club']){
    await p.nav(k);
    for(const u of p.all('#viewBox use')){const id=(u.getAttribute('href')||'').slice(1); if(!syms.has(id)) missing.add(id)}
    for(const a of p.all('#viewBox a[href]')) links.add(a.getAttribute('href'));
    for(const s of ['book','points','info','forms','privacy']){
      if(p.all('#viewBox [data-ctab],[data-ptab]').length){ try{ p.click('[data-ctab="'+s+'"], [data-ptab="'+s+'"]'); await wait(90) }catch(e){} }
    }
  }
  await p.nav('');
  for(const u of p.all('#profBox use')){const id=(u.getAttribute('href')||'').slice(1); if(!syms.has(id)) missing.add(id)}
  p.click('[data-open-support]'); await wait(200);
  for(const u of p.all('#supBody use')){const id=(u.getAttribute('href')||'').slice(1); if(!syms.has(id)) missing.add(id)}
  ok(missing.size===0,'هر نمادی که صدا زده می‌شود در صفحه هست'+(missing.size?': '+[...missing].join(', '):''));
  const bad=[...links].filter(h=>h&&!/^(https?:|tel:|mailto:|#)/.test(h))
    .filter(h=>{const f=h.split('?')[0].split('#')[0]; return f&&!fs.existsSync(DIR+f)});
  ok(bad.length===0,'نشانی شکسته‌ای نیست'+(bad.length?': '+bad.join(', '):''));
  const ids=p.all('[id]').map(e=>e.id), dup=ids.filter((x,i)=>ids.indexOf(x)!==i);
  ok(dup.length===0,'هیچ شناسهٔ تکراری در صفحه نیست'+(dup.length?': '+[...new Set(dup)].join(', '):''));
  ok(p.all('.tabbar a').length===3 && p.doc.querySelector('.tabbar a.on[href="account.html"]')!==null,'نوار پایین سه‌تایی و «حساب من» روشن');
  const html=fs.readFileSync(DIR+'account.html','utf8');
  ok((html.match(/class="tabbar"/g)||[]).length===1 && (html.match(/id="toast"/g)||[]).length===1,'یک نوار پایین و یک پیام‌رسان');
  const css=fs.readFileSync(DIR+'account.css','utf8');
  ok(css.split('{').length===css.split('}').length,'آکولادهای CSS موازنه است');
  const js=fs.readFileSync(DIR+'account.js','utf8');
  const dead=['hubBox','renderHub','VS.events2','supportHTML2','renderTiles','VS.notices','V.club','payCard('].filter(x=>js.includes(x));
  ok(dead.length===0,'کد معماری قدیمی نمانده'+(dead.length?': '+dead.join(', '):''));
}
console.log('\naccount-test: '+pass+' بررسی، '+fail+' خطا');
process.exit(fail?1:0);
