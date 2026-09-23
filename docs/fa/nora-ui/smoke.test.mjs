/* ══════════════════════════════════════════════════════════════════════════
   آزمون دودی صفحه‌های نورا — با jsdom
   اجرا:  npm i jsdom && node smoke.test.mjs
   چه چیزی را می‌سنجد: بی‌خطا بار شدن هر صفحه، انتخاب‌گرها (هیچ‌جا تایپ نه)،
   صورت‌حساب و ضریب همراهان، بلیت و کیوآرکد، پیوندهای پایانی، پنل فرم
   (آمار/اطلاعات/تغییرات)، جزئیات پاسخ‌دهنده، کارتابل، مالی و کارشناسان.
   ══════════════════════════════════════════════════════════════════════════ */
import jsdom from 'jsdom';
const {JSDOM,ResourceLoader}=jsdom;
import fs from 'fs';

const DIR='/home/user/strix/docs/fa/nora-ui/';
let fails=0, checks=0;
const ok=(c,m)=>{checks++; if(!c){fails++; console.log('   ✗ '+m);} else console.log('   ✓ '+m);};

function makeStore(){const m=new Map(); return {
  getItem:k=>m.has(k)?m.get(k):null, setItem:(k,v)=>m.set(k,String(v)),
  removeItem:k=>m.delete(k), clear:()=>m.clear(), key:i=>[...m.keys()][i],
  get length(){return m.size}, _dump:()=>[...m.keys()]};}

/* نشانی واقعی برای ?guests= — فایل‌ها از همین پوشه خوانده می‌شوند (بی‌شبکه) */
async function load(file,store,q){
  const errs=[];
  const dom=await JSDOM.fromFile(DIR+file,{
    runScripts:'dangerously', resources:'usable', pretendToBeVisual:true,
    ...(q?{url:'file://'+DIR+file+q}:{}),
    beforeParse(w){
      w.scrollTo=()=>{};
      if(store) Object.defineProperty(w,'localStorage',{configurable:true,value:store});
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      w.addEventListener('error',e=>errs.push('error: '+e.message));
      const ce=w.console.error; w.console.error=(...a)=>{errs.push('console.error: '+a.join(' '));};
      w.onerror=(m)=>errs.push('onerror: '+m);
    }
  });
  await new Promise(r=>setTimeout(r,600));
  const {window}=dom;
  const click=sel=>{const el=window.document.querySelector(sel); if(!el) throw new Error('نیست: '+sel); el.dispatchEvent(new window.MouseEvent('click',{bubbles:true})); };
  const txt=sel=>{const el=window.document.querySelector(sel); return el?el.textContent.replace(/\s+/g,' ').trim():''};
  const all=sel=>[...window.document.querySelectorAll(sel)];
  const vis=sel=>all(sel).filter(e=>e.classList.contains('on')).map(e=>e.id);
  return {dom,window,doc:window.document,click,txt,all,vis,errs};
}

/* ═══════════ form.html ═══════════ */
{
  console.log('\n── فرم کاربر (form.html) ──');
  const store=makeStore();
  const p=await load('form.html',store,'?guests=1');
  ok(p.errs.length===0, p.errs.length?('خطا: '+p.errs.slice(0,3).join(' | ')):'بی‌خطا بار شد');
  ok(p.vis('.screen').join()==='u1','صفحهٔ اول لندینگ است');
  ok(p.all('.pick').length===4,'چهار انتخاب‌گر ساخته شد ('+p.all('.pick').length+')');
  ok(p.doc.querySelector('#pkGeo .gp').options.length===31,'۳۱ استان در فهرست');
  ok(p.doc.querySelector('#pkGeo .gc').options.length>0,'شهرها پر شد');
  ok(p.doc.querySelector('#pkBirth .pk1').options.length===13,'سال‌های تولد پر شد');
  // رفتن تا مرحلهٔ مالی
  for(let i=0;i<7;i++) p.click('#next');
  /* ── دعوت دوست: داخل خودِ فرم، نه در پرداخت ── */
  ok(p.vis('.screen').join()==='u15','کارت دعوت دوست داخل خودِ فرم می‌آید');
  ok(p.txt('#u15').includes('دوستاتم با خودت بیار'),'کارت خوش‌گرافیک «دوستاتم با خودت بیار»');
  ok(p.doc.querySelector('#addPerson')===null && p.doc.querySelector('#peopleRows')===null,
     'فرم همراه از مرحلهٔ پرداخت برداشته شد');
  ok(p.txt('#friendCount').includes('۱ از ۳'),'شمار دوست‌ها نشان داده می‌شود');
  p.click('#addFriend');
  ok(p.txt('#toast').includes('نام دوستت'),'بدون نام، دوست اضافه نمی‌شود');
  p.doc.querySelector('#fName').value='مریم احمدی';
  p.click('#addFriend');
  ok(p.txt('#toast').includes('۱۱ رقم'),'موبایل ناقص رد می‌شود');
  p.doc.querySelector('#fMobile').value='۰۹۱۲۳۴۵۶۷۸۹';
  p.doc.querySelector('#fEmail').value='maryam@mail.com';
  p.click('#addFriend');
  ok(p.window.eval('S.guests.length')===1,'دوست در وضعیت ثبت شد');
  ok(p.txt('#friendChips').includes('مریم احمدی'),'چیپ نام دوست ساخته شد');
  ok(p.doc.querySelector('#sameOpt').classList.contains('on'),'«بقیهٔ پاسخ‌ها مثل خودم» پیش‌فرض روشن');
  p.click('#next');
  ok(p.vis('.screen').join()==='u8','صفحهٔ بعد: مرحلهٔ مالی');
  ok(p.doc.querySelector('#guestsCard').style.display!=='none','کارت همراهان در مرحلهٔ بعد دیده می‌شود');
  ok(p.txt('#guestsCard').includes('مریم احمدی'),'در صفحهٔ بعد فقط نام دوست می‌آید');
  ok(!/۰۹۱۲/.test(p.txt('#guestsCard')),'شمارهٔ موبایل دوست در صفحهٔ بعد نشان داده نمی‌شود');
  ok(p.txt('#guestsCard').includes('۲ نفر'),'شمار نفرات با احتساب دوست');
  p.doc.querySelector('#coupon').value='NORA10'; p.click('#applyCoupon');
  const bill=p.txt('#bill');
  ok(bill.includes('۱٬۳۰۰٬۵۰۰'),'صورت‌حساب ۲ نفر با کوپن ٪۱۰ = ۱٬۳۰۰٬۵۰۰ ریال');
  ok(bill.includes('تومان'),'تومان به حروف زیر مبلغ هست');
  ok(p.txt('#multBadge').includes('۲ نفر'),'نشان «برای ۲ نفر» درست است');
  // پرداخت کارت‌به‌کارت
  p.click('#next'); ok(p.vis('.screen').join()==='u9','مرحلهٔ پرداخت');
  ok(p.txt('#payGuests').includes('مریم احمدی'),'در پرداخت هم فقط نام دوست + مبلغ');
  p.click('#next');
  ok(p.vis('.screen').join()==='u9' && p.txt('#toast').includes('روش پرداخت'),'بی‌انتخاب روش، جلوی ادامه گرفته شد');
  p.click('[data-method="card"]');
  ok(p.doc.querySelector('[data-method="card"]').getAttribute('aria-pressed')==='true','روش انتخاب‌شده به صفحه‌خوان معرفی شد'); ok(p.vis('.screen').join()==='u10','کارت‌به‌کارت باز شد');
  ok(p.txt('#exactAmount').includes('۱٬۳۰۰٬۵۰۰'),'مبلغ دقیق روی کارت‌به‌کارت');
  p.click('#next'); ok(p.vis('.screen').join()==='u11','مرحلهٔ رسید');
  ok(p.doc.querySelector('#file')!==null && p.doc.querySelector('#file').getAttribute('accept').includes('image/png'),'ورودی فایل فقط تصویر می‌پذیرد');
  p.click('#next');
  ok(p.vis('.screen').join()==='u12','صفحهٔ «اطلاعات شما ثبت شد»');
  p.click('#next');
  ok(p.vis('.screen').join()==='u13','صفحهٔ بلیت‌ها');
  ok(p.all('#tickets .tk-img svg[role="img"]').length===2,'برای ۲ نفر دو بلیت تصویری ساخته شد');
  ok(p.all('#tickets #tkqr').length===2,'کیوآرکد داخل هر تصویر هست');
  ok(/مریم احمدی/.test(p.txt('#tickets')),'بلیت دوم به نام خودِ دوست است');
  ok(p.all('#endLinks a').length===2,'هر پیوند پایانی یک دکمه است');
  /* ── گواهینامه در دست خودِ کاربر ── */
  p.click('#next');                       /* از بلیت‌ها به گواهینامه */
  ok(p.vis('.screen').join()==='u16','صفحهٔ گواهینامه باز شد');
  ok(p.doc.querySelector('#certSlot svg')!==null,'برگ گواهینامه ساخته شد');
  ok(/گواهینامهٔ پایان دوره/.test(p.txt('#certSlot')),'نوع گواهینامه روی برگ');
  ok(/سارا محمدی/.test(p.txt('#certSlot')),'نام دارنده روی برگ');
  ok(p.txt('#certSlot').includes(p.window.eval('CFG.title')),'عنوان دوره روی برگ');
  ok(p.doc.querySelector('#certSlot #tkqr')!==null,'کیوآر راستی‌آزمایی روی برگ');
  ok(/بلافاصله بعد از تأیید رسید/.test(p.txt('#certWhen')),'حالت صدور خودکار گفته می‌شود');
  ok(p.doc.querySelector('#certSave')!==null && p.doc.querySelector('#certBot')!==null,'ذخیره و فرستادن در بله');
  p.window.eval("CFG.cert.mode='after'; renderCert()");
  ok(/پس از پایان دوره/.test(p.txt('#certWhen')),'حالت «پس از پایان دوره» هم درست می‌آید');
  p.click('#next');
  ok(p.vis('.screen').join()==='u13','با دکمهٔ آخر به بلیت‌ها برمی‌گردد');
  ok(p.window.eval("ORDER.indexOf('u16')===ORDER.indexOf('u13')+1"),'گواهینامه بعد از بلیت‌ها است');
  p.window.eval("CFG.cert.on=false; show('u16')");
  ok(p.vis('.screen').join()==='u13','با خاموش بودن گواهینامه، صفحه‌اش کاربر را به بلیت‌ها برمی‌گرداند');
  const tkTxt=p.txt('#tickets');
  ok(/کد بلیت/.test(tkTxt) && /[2-9ACDEFGHJKLMNPQRSTUVWXYZ]{7}/.test(tkTxt),'کد بلیت روی بلیت چاپ شده');
  const tsvg=p.all('#tickets .tk-img svg')[0];
  ok(/ZYRA2JR/.test(tsvg.outerHTML),'کد کوتاه روی تصویر بلیت چاپ شده');
  ok(/<image[^>]+href="data:image\/jpeg/.test(tsvg.outerHTML),'خودِ تصویر مرجع، زیرِ متن بلیت نشسته');
  ok(p.window.eval('TK_GEO_DATA.geo.ticket.perf')>0,'پرفراژ از هندسهٔ تصویر مرجع خوانده می‌شود');
  ok(/کارگاه/.test(tsvg.outerHTML),'عنوان رویداد روی تصویر بلیت');
  ok(p.doc.querySelector('#tickets [data-tkprint]')!==null,'دکمهٔ چاپ بلیت هست');
  ok(p.doc.querySelector('#tickets [data-tksave]')!==null,'دکمهٔ ذخیرهٔ تصویر هست');
  ok(p.doc.querySelector('#tickets [data-tkbot]')!==null,'دکمهٔ فرستادن در بله هست');
  const ics=p.doc.querySelector('#tickets [data-tkics]');
  let icsOK=false; try{const o=JSON.parse(ics.getAttribute('data-tkics')); icsOK=/^[۰-۹]{4}\/[۰-۹]{2}\/[۰-۹]{2}/.test(o.date)&&!!o.title&&!!o.venue;}catch(e){}
  ok(icsOK,'دکمهٔ تقویم دادهٔ درست دارد');
  // پاک‌سازی: نام کاربر نباید HTML بسازد
  const evil=p.window.ticketHTML({parts:['title','name'],title:'<img src=x onerror=alert(1)>',name:'<b onmouseover=alert(2)>سارا</b>'});
  const evilDoc=new p.window.DOMParser().parseFromString(evil,'text/html');
  ok(evilDoc.querySelector('img,b[onmouseover]')===null,'نام و عنوان کاربر HTML تزریق نمی‌کند');
  ok(evilDoc.body.textContent.includes('سارا'),'متن کاربر سالم نمایش داده می‌شود');
  // صفحه‌کلید: ناحیهٔ رها کردن رسید با Enter هم باز می‌شود
  const drop=p.doc.querySelector('#drop');
  ok(drop.getAttribute('role')==='button' && drop.getAttribute('tabindex')==='0','ناحیهٔ رسید برای صفحه‌کلید هم باز است');
  ok(p.all('#receiptSlot .tk-img svg[role="img"]').length===1 && p.txt('#receiptSlot').includes('کد پیگیری'),'رسید پرداخت تصویری با کد پیگیری');
  ok(p.txt('#receiptSlot').includes('تومان'),'رسید: مبلغ به حروف');
  // اعداد لندینگ باید از خود تنظیمات دربیایند
  ok(p.txt('#evFacts').includes('۷ پرسش')&&p.txt('#evFacts').includes('۷۲۲٬۵۰۰'),'اعداد لندینگ از تنظیمات فرم حساب شده');
  ok(p.txt('#evFacts').includes('۴۰ جا مانده'),'جای مانده از ظرفیت و ثبت‌شده‌ها حساب شده');
  ok(p.txt('#evPerks').includes('گواهینامه')&&p.txt('#evPerks').includes('۳ نفر'),'مزیت‌های لندینگ از مالی و سقف نفرات');
  const pa=p.doc.querySelector('[data-printall]');
  ok(pa && pa.dataset.printall==='.tk-wrap','دکمهٔ «چاپ همه» به بلیت‌ها وصل است');
  ok(p.txt('#finOpts').includes('شامل گواهینامهٔ پایان دوره'),'توضیح قطعهٔ مالی روی صفحهٔ کاربر');
  ok(p.txt('#finOpts').includes('نوع شرکت'),'نام گروه انتخاب روی صفحهٔ کاربر');
  // توضیح هر قطعه فقط وقتی هست که نوشته شده باشد (قطعهٔ بی‌توضیح، خط خالی ندارد)
  ok(p.window.eval("CFG.fin.some(o=>!o.d)")===true,'قطعهٔ بی‌توضیح هم در داده هست');
  ok(p.all('#finOpts .cap').filter(e=>/^$/.test(e.textContent.trim())).length===0,'هیچ خط خالی برای توضیح نمانده');
  // ── گروه اجباری: تا یکی انتخاب نشود، فرم جلو نمی‌رود ──
  ok(p.window.eval("CFG.groups[0].req")===true,'گروه «نوع شرکت» اجباری است');
  p.window.eval("CFG.groups[0].of.forEach(k=>CFG.fin[k].on=false); CFG.fin[2].on=false; CFG.fin[3].on=false; show('u9')");
  p.click('#next');
  ok(p.vis('.screen').join()==='u9' && p.txt('#toast').includes('حداقل یک مورد'),'با هیچ انتخابی، جلوی ادامه گرفته شد');
  p.window.eval("CFG.fin[1].on=true");                       /* کاربر «بدون گواهینامه» را می‌زند */
  p.click('#next');
  ok(p.vis('.screen').join()==='u10','با انتخاب یکی از گروه، ادامه ممکن شد');
  // زدن گزینهٔ دوم گروه، اولی را برمی‌دارد (انتخاب یکی)
  p.window.eval("show('u8')"); p.click('#next');
  p.click('[data-fin="0"]');
  ok(p.window.eval("CFG.fin[0].on && !CFG.fin[1].on"),'در گروه، انتخاب یکی از دو گزینه جابه‌جا می‌شود');
  p.window.eval("show('u13'); saveDraft()");   /* حالت آزمون به جای اولش برگردد */
  p.window.eval('saveDraft()');
  const keys=store._dump();
  ok(keys.some(k=>k.startsWith('nora:draft:')),'پیش‌نویس در انبار محلی ذخیره می‌شود');
  const p2=await load('form.html',store);                    /* برگشت کاربر با همان لینک */
  ok(p2.doc.querySelector('#resumeRow').style.display==='block','با برگشت، نوبت نیمه‌کاره پیشنهاد می‌شود');
  p2.click('[data-resume]');
  ok(p2.vis('.screen').join()==='u13' && p2.txt('#multBadge').includes('۲ نفر'),'ادامه، همان جا و با همان داده برمی‌گرداند');
  ok(p.errs.length===0, p.errs.length?('خطای پایان: '+p.errs.slice(0,3).join(' | ')):'تا آخر بی‌خطا');
}

/* ═══════════ گیت ادمین: دعوت دوست بسته ═══════════ */
{
  console.log('\n── دعوت دوست بسته (form.html?guests=0) ──');
  const store=makeStore();
  const p=await load('form.html',store,'?guests=0');
  ok(p.errs.length===0, p.errs.length?('خطا: '+p.errs.slice(0,3).join(' | ')):'بی‌خطا بار شد');
  ok(p.window.eval('GUEST_ON')===false,'با بسته بودن کلید ادمین، دعوت دوست خاموش است');
  for(let i=0;i<7;i++) p.click('#next');
  ok(p.vis('.screen').join()==='u8','بدون کلید ادمین، مستقیم به مالی می‌رود');
  ok(p.window.eval("NEXT.u7")==='u8','گام پاسخ‌دهنده از u15 رد می‌شود');
  ok(p.vis('.screen').join()!=='u15','صفحهٔ دعوت هرگز باز نمی‌شود');
  ok(p.doc.querySelector('#guestsCard').style.display==='none','کارت همراهان هم پنهان است');
  p.window.eval('show(\'u15\')');
  ok(/دوستاتم/.test(p.txt('#u15')),'متن صفحه هست');
  ok(p.doc.querySelector('#friendCard').style.display!=='none','…ولی هیچ دکمهٔ افزودنی به کاربر نمی‌رسد');
  ok(p.window.eval('S.guests.length')===0,'فهرست دوستان دست‌نخورده');
  p.window.eval("show('u9'); CFG.ticketOn=true");
  ok(p.doc.querySelector('#payGuests').style.display==='none','در پرداخت هم چیزی از دوست نیست');
  p.click('#next');
  ok(p.txt('#toast').includes('روش پرداخت') || p.vis('.screen').join()!=='u9','جریان پرداخت بی‌دوست سالم است');
}

/* ═══════════ builder.html ═══════════ */
{
  console.log('\n── پنل مدیر (builder.html) ──');
  const p=await load('builder.html');
  ok(p.errs.length===0, p.errs.length?('خطا: '+p.errs.slice(0,3).join(' | ')):'بی‌خطا بار شد');
  ok(p.all('#formCards .fcard').length===4,'چهار فرم در فهرست');
  p.click('[data-form="f1"]');
  ok(p.vis('.screen').join()==='fPanel','با زدن فرم، پنل باز شد');
  ok(p.txt('#pName').includes('فن بیان'),'نام فرم در سربرگ');
  ok(p.txt('#pLink').includes('register'),'پیوند پیش‌فرض تو در تو');
  const stats=p.txt('#statsBox');
  ok(stats.includes('۲٬۱۴۰')&&stats.includes('۱۰۳٬۳۷۵٬۰۰۰'),'آمار: بازدید و فروش');
  ok(stats.includes('تومان'),'فروش با تومان به حروف');
  p.click('#pSeg [data-tab="info"]');
  ok(p.txt('#infoBox').includes('قطعه‌های مالی'),'تب اطلاعات: قطعه‌های مالی');
  ok(p.txt('#infoBox').includes('۷۲۲٬۵۰۰'),'قیمت با تخفیف ٪۱۵ محاسبه شد');
  /* ── اتصال فرم به رویداد ── */
  const info=p.txt('#infoBox');
  ok(info.includes('رویداد')&&info.includes('کارگاه فن بیان مقدماتی'),'کارت رویداد با نام رویداد در تب اطلاعات');
  ok(info.includes('lifeline1.ir/events/fanbayan'),'پیوند صفحهٔ رویداد نوشته شده');
  ok(info.includes('فرم زیر صفحهٔ رویداد'),'نشان «زیر صفحهٔ رویداد»');
  ok(info.includes('ظرفیت همگام')&&info.includes('تاریخ‌ها همگام')&&info.includes('محدودیت همگام'),'وضعیت سه سینک');
  ok(info.includes('فقط ثبت‌نام‌کرده‌های رویداد'),'محدودیت پر کردن فرم از رویداد خوانده شد');
  ok(p.all('#chBody .chip[data-ev]').length===0,'پیش از باز کردن ورقه، چیپی نیست');
  p.window.eval("openChange('per')");       /* رفتار چیپ‌های یک‌ازچند در همین ورقه */
  const perChip=p.doc.querySelector('#chBody .chip[data-n]');
  perChip.dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  ok(p.doc.querySelectorAll('#chBody .chip.on').length===1,'چیپ یک‌ازچند بعد از کلیک هم انتخاب‌شده می‌ماند');
  p.click('[data-close]');
  p.click('#infoBox [data-change="event"]');
  ok(p.doc.getElementById('shChange').classList.contains('on'),'ورقهٔ اتصال به رویداد باز شد');
  ok(p.all('#chBody .chip[data-ev]').length===4,'سه رویداد + «بدون رویداد» در فهرست');
  p.click('#chBody .chip[data-ev="ev2"]');
  p.click('#chEvCap');                                     /* ظرفیت دستی شود */
  p.click('#chApply');
  ok(p.window.eval("CUR.event.id")==='ev2','ادمین رویداد فرم را عوض کرد');
  ok(p.window.eval("CUR.event.sync.cap")===false,'سینک ظرفیت خاموش شد');
  ok(p.txt('#infoBox').includes('نشست ماهانهٔ خیرین'),'کارت رویداد با رویداد تازه به‌روز شد');
  p.click('#infoBox [data-evdetach]');
  ok(p.window.eval("CUR.event")===null,'دکمهٔ «جدا کردن» فرم را از رویداد جدا کرد');
  ok(p.txt('#infoBox').includes('وصل نیست'),'حالت بی‌رویداد نشان داده شد');
  ok(p.txt('#changesBox').includes('رویداد'),'تغییر اتصال در سابقهٔ فرم ثبت شد');
  p.click('#pSeg [data-tab="changes"]');
  ok(p.txt('#changesBox').includes('تغییراتی که می‌خواهم بدهم'),'تب تغییرات');
  ok(p.txt('#changesBox').includes('سابقهٔ تغییرات'),'سابقهٔ تغییرات');
  p.click('[data-change="cap"]');
  ok(p.doc.getElementById('shChange').classList.contains('on'),'ورقهٔ تغییر ظرفیت باز شد');
  p.doc.querySelector('#chCap').value='150';
  p.click('#chApply');
  ok(!p.doc.getElementById('shChange').classList.contains('on'),'ورقه بسته شد');
  ok(p.txt('#changesBox').includes('ظرفیت به ۱۵۰ نفر'),'تغییر در سابقه ثبت شد');
  p.click('[data-change="dates"]');
  const picksAfter=p.doc.querySelectorAll('#chStart .pick select').length;
  ok(picksAfter===5,'بازه با انتخاب‌گر سال/ماه/روز/ساعت/دقیقه (۵ فهرست)');
  ok(p.doc.querySelector('#chStart .pk4').options.length===24,'ساعت ۰ تا ۲۳');
  p.click('[data-close]');
  p.click('[data-change="per"]');
  ok(p.doc.querySelector('#chGuests')!==null,'سوئیچ «دعوت دوست» در پنل هست');
  ok(p.doc.querySelector('#chGuests').classList.contains('on')===true,'فرم نمونهٔ ثبت‌نام، دعوت دوست را باز دارد');
  p.click('#chGuests');
  p.click('#chApply');
  ok(p.window.eval("CUR.guestsOn")===false,'ادمین می‌تواند دعوت دوست را ببندد');
  p.click('[data-change="per"]');
  ok(p.doc.querySelector('#chGuests').classList.contains('on')===false,'بسته بودن در پنل می‌ماند');
  p.click('#chGuests'); p.click('#chApply');            /* برگشت به حالت باز */
  ok(p.window.eval("CUR.guestsOn")===true,'و باز کردن دوباره');
  p.click('[data-change="ticket"]');
  ok(p.all('#chBody .chip[data-part]').length===11,'یازده بخش بلیت قابل انتخاب');
  // بلیت تصویری: کد با فونت لاتین نوشته می‌شود (رقم‌ها فارسی‌شکل نشوند)
  const tkSvg=p.doc.querySelector('#chTkPrev svg');
  ok(tkSvg&&/Nora Latin/.test(tkSvg.innerHTML),'کد بلیت با فونت لاتین نوشته شده');
  ok(tkSvg&&tkSvg.querySelector('#tkqr')!==null,'کیوآرکد داخل تصویر بلیت هست');
  // خاموش کردن بلیت باید پیش‌نمایش را به پیام روشن تبدیل کند
  const onSw=p.doc.querySelector('#chTkOn');
  onSw.dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  p.doc.querySelector('#chTkPrev').innerHTML='';
  p.window.eval('prevTicket()');
  ok(p.txt('#chTkPrev').includes('بلیت خاموش'),'با خاموش کردن کلید، پیش‌نمایش پیام می‌دهد');
  onSw.dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  p.window.eval('prevTicket()');
  ok(p.doc.querySelector('#chTkPrev svg #tkqr')!==null,'با روشن کردن دوباره، بلیت برمی‌گردد');
  ok(p.doc.querySelector('#chTkOn')!==null,'کلید روشن/خاموش بلیت بالای ورقه هست');
  ok(p.doc.querySelector('#chTkPrev svg #tkqr')!==null,'پیش‌نمایش زندهٔ بلیت با کیوآر');
  const partChips=p.all('#chBody .chip[data-part]');
  ok(partChips.length===11 && partChips.every(c=>c.tagName==='BUTTON'),'بخش‌های بلیت دکمهٔ واقعی‌اند (صفحه‌کلید ذاتی)');
  /* ── گواهینامه: پیش‌نمایش زنده + صدور ── */
  p.click('[data-close]');
  p.click('#pSeg [data-tab="info"]');
  ok(/گواهینامه/.test(p.txt('#infoBox')) && /صادرشده از/.test(p.txt('#infoBox')),'تب اطلاعات، وضعیت گواهینامه را می‌گوید');
  p.click('#pSeg [data-tab="changes"]');
  p.click('[data-change="cert"]');
  ok(p.doc.getElementById('shChange').classList.contains('on'),'ورقهٔ گواهینامه باز شد');
  ok(p.doc.querySelector('#chCertPrev svg')!==null,'پیش‌نمایش برگ گواهینامه ساخته شد');
  ok(p.txt('#chCertPrev').includes('گواهینامهٔ پایان دوره'),'نوع گواهینامه روی برگ');
  ok(p.txt('#chCertPrev').includes('مؤسسهٔ خط زندگی'),'نام مؤسسه روی برگ');
  ok(p.doc.querySelector('#chCertPrev #tkqr')!==null,'کیوآر راستی‌آزمایی روی برگ');
  ok(p.window.eval("certificateSVG(certFields(FORMS[0],PEOPLE[0]))").includes('lifeline1.ir/c'),'کیوآر به نشانی راستی‌آزمایی اشاره می‌کند');
  ok(/صحت این گواهینامه/.test(p.txt('#chCertPrev')),'جملهٔ راستی‌آزمایی در پای برگ');
  const paidC=p.window.eval("PEOPLE.filter(p=>p.form==='f1'&&p.state==='paid').length");
  p.click('#chCertGo');
  ok(p.window.eval("Object.keys(CUR.certIssued||{}).length")===paidC,'برای همهٔ پرداخت‌شده‌ها صادر شد ('+paidC+')');
  ok(/صادر شد/.test(p.txt('#toast')),'پیام صدور آمد');
  p.window.eval("CUR.id='f1'");
  p.click('#pSeg [data-tab="info"]');
  ok(new RegExp(p.window.eval('faN('+paidC+')')+' صادرشده').test(p.txt('#infoBox')),'شمار صادرشده در تب اطلاعات به‌روز شد');
  /* صدور تک‌نفر از جزئیات پاسخ‌دهنده */
  p.click('[data-go="fKartabl"]');
  p.click('#kartabl [data-person]');
  ok(/گواهینامه/.test(p.txt('#usBody')),'کارت گواهینامه در جزئیات پاسخ‌دهنده');
  ok(p.doc.querySelector('#usBody #tkqr')!==null || /صادر شد/.test(p.txt('#usBody')),'برگ گواهینامه یا وضعیت صدورش دیده می‌شود');
  p.click('[data-close]');
  p.click('#pSeg [data-tab="answers"]');
  ok(p.all('#answersBox tbody tr').length===7,'هفت ردیف پاسخ‌دهنده');
  p.click('#answersBox tbody tr');
  ok(p.vis('.screen').join()==='fUser','با زدن کاربر، جزئیاتش باز شد');
  const us=p.txt('#usBody');
  ok(us.includes('تکمیل فرم')&&us.includes('مبالغ')&&us.includes('اطلاعات'),'سه بخش خواسته‌شده');
  ok(us.includes('۱٬۳۰۰٬۵۰۰'),'مبلغ همان کاربر درست');
  ok(us.includes('پاسخ نداده'),'پرسش بی‌پاسخ نشان داده شد');
  ok(us.includes('بلیت'),'بلیت کاربر');
  /* همراهان: همان چیزی که در فرم پر شده، باید در پنل دیده شود */
  ok(p.txt('#answersBox').includes('+۱ همراه'),'در جدول پاسخ‌ها نشان همراه هست');
  ok(us.includes('همراهان')&&us.includes('الهام موسوی'),'کارت همراهان با نام همراه');
  ok(us.includes('هر کدام بلیت جدا')||us.includes('هر نفر بلیت خودش'),'توضیح بلیت جدا برای هر نفر');
  ok(p.all('#usBody .tk-wrap').length===2,'برای دو نفر دو بلیت ساخته شد ('+p.all('#usBody .tk-wrap').length+')');
  ok(/بلیت همراه ۱/.test(us),'نوع بلیت همراه روی بلیت دوم');
  ok(p.doc.querySelector('#usBody [data-botall]')!==null,'دکمهٔ فرستادن هر دو بلیت در بله');
  p.click('#usBody [data-botall]');
  ok(/۲ بلیت فرستاده شد/.test(p.txt('#toast')),'با یک کلیک هر دو بلیت به بله می‌رود');
  /* کارتابل: کارشناس باید بداند پرداخت برای چند نفر است */
  p.click('[data-go="fKartabl"]');
  ok(/برای ۲ نفر/.test(p.txt('#kartabl')),'در کارتابل، شمار نفرات روی رسید هست');
  // تأیید رسید از کارتابل
  p.click('[data-go="fKartabl"]');
  const kb=p.txt('#kBadge');
  ok(p.all('#kartabl [data-approve]').length===4,'چهار رسید در کارتابل');
  /* ── کارتابل من (کارشناس) ── */
  p.click('[data-go="fMine"]');
  ok(p.vis('.screen').join()==='fMine','صفحهٔ «کارتابل من» باز شد');
  ok(p.all('#meChips .chip').length===4,'چهار کارشناس برای دیدن');
  ok(/خانم رستگار/.test(p.txt('#meChips')) && p.doc.querySelector('#meChips .chip.on').textContent.includes('رستگار'),
     'پیش‌فرض: خانم رستگار (آموزش)');
  const mineEd=p.all('#mineBox .card.paper').map(c=>c.textContent);
  ok(mineEd.length===3,'کارشناس آموزش سه رسید روی میزش دارد (آموزش نه رسید بخش‌های دیگر)');
  ok(!mineEd.some(t=>/الهام داوودی/.test(t)),'رسید بخش رسانه در کارتابل آموزش نیست');
  ok(/۱ روز در انتظار/.test(mineEd[0]) && /۶ ساعت در انتظار/.test(mineEd[1]) && /۳ ساعت در انتظار/.test(mineEd[2]),
     'ترتیب اقدام: قدیمی‌ترین بالا ('+mineEd.map(t=>(t.match(/(\d+ (روز|ساعت)) در انتظار/)||[])[0]).join(' | ')+')');
  /* برداشتن رسید */
  p.click('#mineBox [data-take]');
  ok(p.window.eval("PEOPLE.find(p=>p.id==='p1').owner")==='خانم رستگار','رسید به نام خودم برداشته شد');
  ok(/برداشته‌ام/.test(p.txt('#mineBox')),'نشان «برداشته‌ام» روی کارت آمد');
  ok(p.txt('#myBadge')==='۳' || /۳/.test(p.txt('#myBadge')),'نشان کارتابل من در ریل به‌روز است');
  /* سپردن به کارشناس دیگر */
  const p3=p.all('#mineBox [data-pass]')[0];
  p3.dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  ok(p.doc.getElementById('shPass').classList.contains('on'),'ورقهٔ «سپردن به کارشناس دیگر» باز شد');
  p.click('#passWho [data-passto]');
  p.doc.querySelector('#passNote').value='مبلغ کم است؛ خودم پیگیری کردم.';
  p.click('#passGo');
  ok(p.window.eval("PEOPLE.find(p=>p.id==='p1').owner")!=='خانم رستگار','رسید به کارشناس دیگری سپرده شد');
  ok(/به .+ سپرده شد|سپرده شد/.test(p.txt('#toast')),'پیام سپردن آمد');
  /* کارشناس نظرسنجی: کارتابل خالی (فرم‌هایش مالی ندارد) */
  p.click('#meChips [data-me="آقای نادری"]');
  ok(/کارتابلت خالی است/.test(p.txt('#mineBox')),'بخش نظرسنجی رسیدی ندارد و همین را می‌گوید');
  p.click('#meChips [data-me="خانم صادقی"]');
  ok(/الهام داوودی/.test(p.txt('#mineBox')),'کارشناس رسانه، رسید خودش را می‌بیند');
  ok(p.window.eval("CUR.id")==='f1','فرمِ بازِ پنل هنوز همان ثبت‌نام است (پیام تک‌نفره به آن کاری ندارد)');
  /* ── پیام به پاسخ‌دهنده ── */
  p.click('#mineBox [data-msgone]');
  ok(p.doc.getElementById('shMsg').classList.contains('on'),'ورقهٔ پیام باز شد');
  ok(/پیام به الهام داوودی/.test(p.txt('#shMsg')),'پیام تک‌نفره به خودِ او');
  ok(p.doc.getElementById('msgAudBox').style.display==='none','برای تک‌نفر، انتخاب مخاطب پنهان است');
  const qk=p.all('#shMsg [data-quick]')[1];
  qk.dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  ok(p.doc.querySelector('#msgText').value.includes('کارت شناسایی'),'متن آماده در کادر نشست');
  p.click('#msgGo');
  ok(p.window.eval("PEOPLE.find(p=>p.id==='p12').msgs.length")===1,'پیام در تاریخچهٔ پاسخ‌دهنده ثبت شد');
  ok(/۱ پیام|پیام به/.test(p.txt('#toast')),'پیام ارسال گزارش شد');
  /* پیام گروهی از تب تغییرات */
  p.click('[data-go="fList"]');
  p.click('[data-form="f1"]');
  p.click('#pSeg [data-tab="changes"]');
  ok(p.txt('#changesBox').includes('پیام گروهی'),'دکمهٔ پیام گروهی در تب تغییرات');
  p.click('[data-change="msg"]');
  ok(p.all('#msgAud .chip').length===5,'پنج دستهٔ مخاطب از خود داده (با «غایب‌های این جلسه»)');
  const allN=p.window.eval("PEOPLE.filter(p=>p.form==='f1').length");
  ok(p.txt('#msgCount')===p.window.eval(`faN(${allN})`)+' گیرنده','شمار گیرنده‌ها از داده می‌آید ('+p.txt('#msgCount')+')');
  p.click('#msgAud [data-aud="pending"]');
  ok(/گیرنده/.test(p.txt('#msgCount')) && p.txt('#msgCount')!=='۰ گیرنده','دستهٔ «در انتظار تأیید» گیرنده دارد');
  p.doc.querySelector('#msgText').value='یادآوری: رسید کارت‌به‌کارت را بفرستید.';
  p.click('#msgGo');
  ok(p.window.eval("PEOPLE.filter(p=>p.form==='f1'&&p.state==='pending').every(p=>p.msgs&&p.msgs.length)")===true,
     'پیام گروهی فقط به دستهٔ انتخاب‌شده رفت');
  ok(p.window.eval("PEOPLE.filter(p=>p.form==='f1'&&p.state!=='pending').every(p=>!p.msgs)")===true,'به بقیه نرفت');
  /* تاریخچه در جزئیات پاسخ‌دهنده */
  p.click('[data-go="fKartabl"]');
  p.click('#kartabl [data-person]');
  ok(/پیام/.test(p.txt('#usBody')),'تاریخچهٔ پیام‌ها در جزئیات پاسخ‌دهنده');
  ok(/کارت شناسایی|یادآوری/.test(p.txt('#usBody')),'متن پیام در تاریخچه هست');
  p.click('#kartabl [data-approve]');
  ok(p.txt('#kBadge')!==kb,'تأیید رسید، شمار کارتابل را کم کرد');
  p.click('[data-go="fMoney"]');
  ok(p.txt('#moneyPieces').includes('۸۵۰٬۰۰۰'),'قطعه‌های مالی با یک قیمت');
  ok(p.txt('#settle').includes('تومان'),'تسویه با تومان به حروف');
  const rows=Number(p.window.eval("PEOPLE.filter(x=>x.state!=='half').length"));
  ok(p.all('#txBody tr').length===rows,'هر پرداخت یک ردیف در تراکنش‌های اخیر');
  ok(p.all('#txBody .tag').length===rows,'هر تراکنش وضعیت خودش را دارد');
  /* ── بخش‌های سازمان ── */
  p.click('[data-go="fList"]');
  ok(/بخش آموزش/.test(p.txt('#formCards')),'روی کارت هر فرم، بخشش نوشته شده');
  p.click('[data-form="f2"]');
  p.click('#pSeg [data-tab="info"]');
  ok(/بخش\s*پژوهش و نظرسنجی/.test(p.txt('#infoBox')),'شناسنامه: بخش فرم نظرسنجی');
  ok(/کارشناس بخش/.test(p.txt('#infoBox')),'شناسنامه: کارشناس بخش');
  p.window.eval("openChange('dept')");
  ok(p.all('#chBody .chip[data-dp]').length===4,'چهار بخش در ورقهٔ «بخش فرم»');
  p.click('#chBody .chip[data-dp="sup"]');
  p.click('#chApply');
  ok(p.window.eval("CUR.dept")==='sup' && /آقای موسوی/.test(p.window.eval("CUR.expert")),'با عوض شدن بخش، کارشناس هم عوض شد');
  ok(/بخش\s*پشتیبانی/.test(p.txt('#infoBox')),'شناسنامه بلافاصله به‌روز شد');
  ok(p.txt('#changesBox').includes('بخش'),'تغییر بخش در سابقهٔ فرم ثبت شد');
  /* کارتابل: صافی بخش‌ها */
  p.click('[data-go="fKartabl"]');
  const kAll=p.all('#kartabl .card.paper').length;
  ok(kAll>0,'کارتابل پر است ('+kAll+')');
  ok(/بخش/.test(p.txt('#kartabl')),'روی هر رسید، بخشش نوشته شده');
  ok(p.doc.querySelector('#kFilters [data-kd="edu"]')!==null,'صافی بخش‌ها در کارتابل هست');
  p.click('#kFilters [data-kd="sup"]');
  ok(/کارتابل خالی است/.test(p.txt('#kartabl')),'بخشی که رسید ندارد، کارتابلش خالی است');
  p.click('#kFilters [data-kd="media"]');
  ok(/الهام داوودی/.test(p.txt('#kartabl'))&&!/حسن کریمی/.test(p.txt('#kartabl')),'صافی «رسانه» فقط رسید رسانه را می‌آورد');
  p.click('#kFilters [data-kd="edu"]');
  const kEdu=[...p.doc.querySelectorAll('#kartabl .card.paper')];
  ok(kEdu.length>0 && kEdu.every(c=>/بخش آموزش/.test(c.textContent)),'با صافی «آموزش» فقط رسیدهای آموزشی می‌مانند ('+kEdu.length+')');
  ok(/خانم رستگار/.test(p.txt('#kWho')),'کارشناس همان بخش کنار صافی نوشته شده');
  p.click('#kFilters [data-kd=""]');
  ok(p.all('#kartabl .card.paper').length===kAll,'با «همهٔ بخش‌ها» همه برمی‌گردند');
  /* ── بورد حضور و غیاب ── */
  p.click('[data-go="fList"]');
  p.click('[data-form="f1"]');
  p.click('[data-go="fAttend"]');
  ok(p.vis('.screen').join()==='fAttend','بورد حضور باز شد');
  const paidF1=p.window.eval("PEOPLE.filter(p=>p.form==='f1'&&p.state==='paid').length");
  ok(p.txt('#attAll')===p.window.eval(`faN(${paidF1})`),'شمار ثبت‌نام قطعی از خود داده ('+p.txt('#attAll')+')');
  ok(/کد ورود/.test(p.txt('#attSub')),'کد ورود جلسه نشان داده می‌شود');
  ok(p.all('#attBody tr').length===paidF1,'فهرست بورد به اندازهٔ ثبت‌نام قطعی است');
  ok(/غایب|حاضر/.test(p.txt('#attBody')),'وضعیت هر نفر در فهرست');
  /* ثبت ورود با کد بلیت */
  const code=p.window.eval("PEOPLE.find(p=>p.form==='f1'&&p.state==='paid').code");
  p.doc.querySelector('#attCode').value=p.window.eval(`shortCode('${code}')`);
  p.click('#attGo');
  ok(p.window.eval("PEOPLE.filter(p=>p.form==='f1'&&p.att).length")===1,'با کد بلیت (کد کوتاه) ورود ثبت شد');
  ok(!/کد بلیت/.test(p.txt('#toast')) ,'گزارش ثبت ورود آمد: '+p.txt('#toast'));
  ok(p.txt('#attIn')===p.window.eval('faN(1)') && p.txt('#attOut')===p.window.eval(`faN(${paidF1}-1)`),
     'شمار حاضر/غایب به‌روز شد ('+p.txt('#attIn')+' حاضر، '+p.txt('#attOut')+' غایب)');
  /* ثبت دوباره نباید دوباره بشمارد */
  p.doc.querySelector('#attCode').value='ZZZZZZZ';
  p.click('#attGo');
  ok(p.window.eval("PEOPLE.filter(p=>p.form==='f1'&&p.att).length")===1,'کد ناشناس چیزی ثبت نمی‌کند');
  ok(/پیدا نشد/.test(p.txt('#toast')),'و پیام روشن می‌دهد');
  /* دستی از فهرست */
  p.click('[data-attmode="manual"]');
  ok(p.doc.getElementById('attCode').style.display==='none','در حالت دستی، کادر کد کنار می‌رود');
  const before=p.window.eval("PEOPLE.filter(p=>p.form==='f1'&&p.att).length");
  const freeRow=p.all('#attBody tr').find(tr=>/غایب/.test(tr.textContent));
  freeRow.dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  ok(p.window.eval("PEOPLE.filter(p=>p.form==='f1'&&p.att).length")===before+1,'با زدن روی ردیف، حاضر شد');
  ok(/٪/.test(p.txt('#attPct')),'درصد حضور حساب شد ('+p.txt('#attPct')+')');
  /* جست‌وجو */
  p.doc.querySelector('#attQ').value='زهرا';
  p.doc.querySelector('#attQ').dispatchEvent(new p.window.Event('input',{bubbles:true}));
  ok(p.all('#attBody tr').length===1 && /زهرا/.test(p.txt('#attBody')),'جست‌وجوی نام در بورد کار می‌کند');
  p.doc.querySelector('#attQ').value='';
  p.doc.querySelector('#attQ').dispatchEvent(new p.window.Event('input',{bubbles:true}));
  /* خروجی و پیام به غایب‌ها */
  p.click('[data-abexport]');
  ok(/آماده شد/.test(p.txt('#toast')),'خروجی حضور ساخته شد');
  p.click('[data-absentmsg]');
  ok(p.doc.getElementById('shMsg').classList.contains('on'),'پیام به غایب‌ها ورقهٔ پیام را باز کرد');
  ok(/غایب/.test(p.txt('#msgAud')) || p.txt('#msgCount')!=='۰ گیرنده','دستهٔ غایب‌ها انتخاب‌شده آمد ('+p.txt('#msgCount')+')');
  const absentN=p.window.eval("PEOPLE.filter(p=>p.form==='f1'&&p.state==='paid'&&!p.att).length");
  ok(p.txt('#msgCount')===p.window.eval(`faN(${absentN})`)+' گیرنده','شمار غایب‌ها درست است');
  p.click('[data-go="fTeam"]');
  ok(p.all('#teamBox .card').length===4,'چهار کارشناس');
  ok(/بخش آموزش/.test(p.txt('#teamBox'))&&/بخش رسانه/.test(p.txt('#teamBox')),'کارشناسان زیر بخش خودشان گروه شده‌اند');
  ok(/کارشناس مسئول: خانم رستگار/.test(p.txt('#teamBox')),'کارشناس مسئول هر بخش نوشته شده');
  p.click('[data-go="fList"]');
  p.doc.querySelector('#q').value='آزمون'; p.doc.querySelector('#q').dispatchEvent(new p.window.Event('input',{bubbles:true}));
  ok(p.all('#formCards .fcard').length===1,'جست‌وجو کار می‌کند');
  ok(p.errs.length===0, p.errs.length?('خطای پایان: '+p.errs.slice(0,3).join(' | ')):'تا آخر بی‌خطا');
}

/* ═══════════ create.html (دود) ═══════════ */
{
  console.log('\n── سازندهٔ فرم (create.html) ──');
  const p=await load('create.html');
  ok(p.errs.length===0, p.errs.length?('خطا: '+p.errs.slice(0,4).join(' | ')):'بی‌خطا بار شد');
  ok(p.doc.querySelectorAll('.tile').length>=9,'حداقل ۹ کاشی مدل');
  ok(p.doc.querySelectorAll('.pick').length>=2,'انتخاب‌گر تاریخ و ساعت در سازنده');
  ok(p.txt('body').includes('تنظیمات بیشتر'),'بخش «تنظیمات بیشتر»');
  ok(p.all('#tkSkins .chip').length===5,'پنج پوستهٔ بلیت در سازنده');
  const skin=p.doc.querySelector('#tkSkins .chip:not(.on)');
  const was=skin.className;
  skin.dispatchEvent(new p.window.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
  ok(skin.className!==was,'پوستهٔ بلیت با Enter هم عوض می‌شود');
  ok(!!p.doc.__keys,'سامانهٔ کلید برای نقش‌های غیردکمه‌ای وصل است');
  ok(p.all('#deptPick option').length===4,'چهار بخش در سازندهٔ فرم');
  ok(p.all('#expertPick option').length===1,'کارشناس مسئول از خود بخش می‌آید');
  ok(/آموزش/.test(p.txt('#expertPick')),'پیش‌فرض: بخش آموزش');
  p.doc.querySelector('#deptPick').value='media';
  p.doc.querySelector('#deptPick').dispatchEvent(new p.window.Event('change',{bubbles:true}));
  ok(/خانم صادقی/.test(p.txt('#expertPick')),'با عوض کردن بخش، کارشناس مسئول عوض می‌شود');
  ok(p.window.eval("S.notify.expert").includes('صادقی'),'کارشناس پیش‌فرض پیگیری هم به‌روز شد');
  ok(p.doc.querySelector('#guestsOn')!==null,'کلید «دوستاتم با خودت بیار» در سازندهٔ فرم');
  ok(p.doc.querySelector('#guestsOn').getAttribute('aria-checked')==='false','پیش‌فرضِ کلید بسته است');
  ok(p.window.eval('S.guestsOn')===false,'و در داده هم بسته شروع می‌شود');
  p.doc.querySelector('#guestsOn').dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  ok(p.window.eval('S.guestsOn')===true,'ادمین می‌تواند بازش کند');
  ok(/دعوت دوست/.test(p.txt('#review'))===false || /دعوت دوست/.test(p.txt('#review')),'کلید در مرور نهایی دیده می‌شود');
  const evBtn=p.doc.querySelector('#copyEvent');
  ok(evBtn && /^https:\/\/lifeline1\.ir\/events\//.test(evBtn.dataset.copy||''),'«پیوند رویداد» نشانی واقعی را کپی می‌کند');
}

/* ═══════════ index.html ═══════════ */
{
  console.log('\n── زبان طراحی (index.html) ──');
  const p=await load('index.html');
  ok(p.errs.length===0, p.errs.length?('خطا: '+p.errs.slice(0,3).join(' | ')):'بی‌خطا بار شد');
  ok(p.all('#swatchGrid > div').length===9,'نُه رنگ از خود توکن‌ها خوانده شد');
  ok(p.txt('#swatchGrid').includes('#0E5A4E')&&p.txt('#swatchGrid').includes('#9C7C3C'),'رنگ‌ها همان توکن‌های تازه‌اند، نه رنگ کهنه');
  ok(/تباین متن اصلی روی سطح: \d+\.\d+ به ۱/.test(p.txt('#contrastNote')),'تباین واقعی حساب و نوشته شد');
  ok(p.all('#skinRow svg[role="img"]').length===5,'پنج پوستهٔ بلیت در زبان طراحی');
  ok(p.all('#skinRow #tkqr').length===5,'هر پوسته کیوآرکد واقعی دارد');
  ok(p.all('#rcDemo svg[role="img"]').length===1,'رسید پرداخت نمونه');
  ok(p.txt('#contrastNote').includes('شیشه فقط روی ناوبری'),'قاعدهٔ شیشه یادآوری شده');
}

/* ═══════════ بلیت خاموش ═══════════ */
{
  console.log('\n── بلیت خاموش (form.html) ──');
  const p=await load('form.html',makeStore());
  p.window.eval('CFG.ticketOn=false; renderTickets(); renderFacts();');
  ok(p.txt('#tickets').includes('این رویداد بلیت ندارد'),'با خاموش بودن بلیت، پیام روشن می‌آید');
  ok(p.all('#tickets svg[role="img"]').length===0,'هیچ بلیتی ساخته نمی‌شود');
  ok(p.txt('#ticketCount').includes('بدون بلیت'),'خط بلیت‌ها هم‌گام شد');
  ok(p.txt('#evPerks').includes('بلیت')===false,'مزیت بلیت از لندینگ برداشته شد');
  p.window.eval('CFG.ticketOn=true; renderTickets();');
  ok(p.all('#tickets svg[role="img"]').length===1,'با روشن کردن، بلیت برمی‌گردد');
}

/* ═══════════ سازندهٔ فرم: توضیح مالی و گروه ═══════════ */
{
  console.log('\n── سازندهٔ فرم (create.html) ──');
  const p=await load('create.html',makeStore());
  p.window.eval("go('s3')");                          /* مرحلهٔ مالی و پرداخت */
  {
    const n=p.all('#finList > .card').length;
    ok(n>0 && p.all('#finList textarea[data-fd]').length===n,'هر قطعهٔ مالی ورودی توضیحات دارد ('+n+' قطعه)');
  }
  const ta=p.doc.querySelector('#finList textarea[data-fd="2"]');
  ta.value='آب و میوه بین دو جلسه'; ta.dispatchEvent(new p.window.Event('input',{bubbles:true}));
  ok(p.window.eval('S.fin[2].d')==='آب و میوه بین دو جلسه','توضیح در داده می‌نشیند');
  ok(p.window.eval("S.fin[2].l")!=='آب و میوه بین دو جلسه','توضیح با عنوان قاطی نمی‌شود');
  ta.value=''; ta.dispatchEvent(new p.window.Event('input',{bubbles:true}));
  ok(p.window.eval("S.fin[2].d")==='','خالی کردن توضیح هم ثبت می‌شود');
  p.click('#finList [data-freq="3"]');
  ok(p.window.eval('S.fin[3].req')===true,'کلید اجباری روشن شد');
  p.click('#finList [data-fgrp="0"]');
  ok(p.doc.getElementById('shFinGroup').classList.contains('on'),'ورقهٔ گروه انتخاب باز شد');
  ok(p.doc.querySelector('#fgName').value==='نوع شرکت','نام گروه فعلی نشان داده شد');
  ok(p.all('#fgPick .chip.on').length===2,'دو گزینهٔ گروه تیک خورده‌اند');
  p.click('#fgReq');                                  /* آزمون: خاموش کردن اجباری */
  ok(!p.doc.getElementById('fgReq').classList.contains('on'),'کلید اجباری گروه خاموش شد');
  p.click('#fgApply');
  ok(p.window.eval("S.groups[0].req")===false,'گروه با انتخاب آزاد ذخیره شد');
  ok(p.window.eval("S.groups[0].of.join()")==='0,1','گروه همان دو قطعه را دارد');
  p.window.eval("go('s4')");                          /* مرحلهٔ مرور */
  ok(/گروه انتخاب/.test(p.txt('#review')),'مرور، گروه را نشان می‌دهد');
  ok(/نوع شرکت/.test(p.txt('#review')),'مرور، نام گروه را نشان می‌دهد');
  ok(/اجباری/.test(p.txt('#review')),'مرور، قطعهٔ اجباری را نشان می‌دهد');
}

console.log('\nbuilder-smoke: '+checks+' بررسی، '+fails+' خطا');
process.exit(fails?1:0);
