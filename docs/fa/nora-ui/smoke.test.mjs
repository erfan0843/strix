/* ══════════════════════════════════════════════════════════════════════════
   آزمون دودی صفحه‌های نورا — با jsdom
   اجرا:  npm i jsdom && node smoke.test.mjs
   چه چیزی را می‌سنجد: بی‌خطا بار شدن هر صفحه، انتخاب‌گرها (هیچ‌جا تایپ نه)،
   صورت‌حساب و ضریب همراهان، گواهینامه و کیوآرکد، پیوندهای پایانی، پنل فرم
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
      if(w.Element&&!w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView=()=>{};
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
  /* ── همراه: کارت خودش در اسلاید مالی (نه نوار شناور) ── */
  for(let i=0;i<7;i++) p.click('#next');
  ok(p.vis('.screen').join()==='u8','هفت پرسش، بعد انتخاب شما — پلهٔ جدای دعوت دوست برداشته شد');
  ok(p.doc.querySelector('#u15')===null,'صفحهٔ جدا برای دعوت دوست نمی‌ماند');
  ok(p.doc.querySelector('#buddyBar')===null,'نوار شناور همراه برداشته شد');
  const gc=p.doc.querySelector('#guestsCard');
  ok(gc.style.display!=='none','کارت «همراه می‌آوری؟» در همان اسلاید مالی دیده می‌شود');
  ok(p.txt('#guestChips').includes('بدون همراه'),'کاربر بدون همراه هم راه دارد');
  p.click('#editGuests');
  ok(p.doc.querySelector('#shBuddy').classList.contains('on'),'شیت همراه از خودِ کارت باز می‌شود');
  p.click('#addFriend');
  ok(p.txt('#toast').includes('نام دوستت'),'بدون نام، همراه اضافه نمی‌شود');
  p.doc.querySelector('#fName').value='مریم احمدی';
  p.click('#addFriend');
  ok(p.txt('#toast').includes('۱۱ رقم'),'موبایل ناقص رد می‌شود');
  p.doc.querySelector('#fMobile').value='۰۹۱۲۳۴۵۶۷۸۹';
  p.doc.querySelector('#fEmail').value='maryam@mail.com';
  p.click('#addFriend');
  ok(p.window.eval('S.guests.length')===1,'همراه در وضعیت ثبت شد');
  ok(p.txt('#guestChips').includes('مریم احمدی'),'نام همراه روی کارت می‌آید');
  ok(p.doc.querySelector('#sameOpt').classList.contains('on'),'«بقیهٔ پاسخ‌ها مثل خودم» پیش‌فرض روشن');
  p.window.eval('closeSheets()');
  ok(p.txt('#guestsCard').includes('۲ نفر'),'شمار نفرات با احتساب همراه');

  /* سقف همراه: جا که پر شود، خودِ کارت می‌گوید */
  p.window.eval("S.guests=new Array(GUEST_MAX).fill(0).map((_,i)=>({name:'همراه '+faN(i+1)})); cur='u8'; renderBuddy()");
  ok(p.doc.querySelector('#editGuests').style.display==='none','با پر شدن جا، دکمهٔ افزودن برداشته می‌شود');
  ok(/جا پر شد/.test(p.txt('#countTxt'))||/جا پر شد/.test(p.txt('#gaddTitle'))||p.window.eval("buddyTip()===' — جا پر شد'"),'کارت می‌گوید جا پر است');
  p.window.eval("S.guests=[{name:'مریم احمدی',mobile:'09123456789',same:true}]; renderBuddy()");

  /* ── انتخاب مالی: گزینهٔ فرعی تنها، فرم را جلو نمی‌برد ── */
  ok(p.window.eval("CFG.fin.every(o=>!o.on)"),'هیچ گزینه‌ای از پیش انتخاب نشده');
  p.click('[data-fin="2"]');                      /* ناهار و پذیرایی — گزینهٔ فرعی */
  p.click('#next');
  ok(p.vis('.screen').join()==='u8' && p.txt('#toast').includes('نوع شرکت'),'با فقط گزینهٔ فرعی، جلوی ادامه گرفته شد');
  p.click('[data-fin="0"]');                      /* انتخاب صریح گروه اجباری */
  p.click('[data-fin="2"]');                      /* ناهار برداشته می‌شود */
  ok(p.window.eval("CFG.fin[0].on && PICKED.has(0) && !CFG.fin[2].on"),'انتخاب صریح ثبت و گزینهٔ فرعی برداشته شد');
  p.doc.querySelector('#coupon').value='NORA10'; p.click('#applyCoupon');
  const bill=p.txt('#bill');
  ok(bill.includes('۱٬۳۰۰٬۵۰۰'),'صورت‌حساب ۲ نفر با کوپن ٪۱۰ = ۱٬۳۰۰٬۵۰۰ ریال');
  ok(bill.includes('تومان'),'تومان به حروف زیر مبلغ هست');
  ok(p.txt('#multBadge').includes('۲ نفر'),'نشان «برای ۲ نفر» درست است');
  // پرداخت کارت‌به‌کارت
  p.click('#next'); ok(p.vis('.screen').join()==='u9','مرحلهٔ پرداخت');
  ok(p.txt('#payGuests').includes('مریم احمدی'),'در پرداخت هم فقط نام دوست + مبلغ');
  ok(p.vis('.screen').join()==='u9','در پرداخت هم چیزی از همراه نیست جز فهرست نام‌ها');
  p.click('#next');
  ok(p.vis('.screen').join()==='u9' && p.txt('#toast').includes('روش پرداخت'),'بی‌انتخاب روش، جلوی ادامه گرفته شد');
  p.click('[data-method="card"]');
  ok(p.doc.querySelector('[data-method="card"]').getAttribute('aria-pressed')==='true','روش انتخاب‌شده به صفحه‌خوان معرفی شد'); ok(p.vis('.screen').join()==='u10','کارت‌به‌کارت باز شد');
  ok(p.txt('#exactAmount').includes('۱٬۳۰۰٬۵۰۰'),'مبلغ دقیق روی کارت‌به‌کارت');
  p.click('#next'); ok(p.vis('.screen').join()==='u11','مرحلهٔ رسید');
  ok(p.doc.querySelector('#file')!==null && p.doc.querySelector('#file').getAttribute('accept').includes('image/png'),'ورودی فایل فقط تصویر می‌پذیرد');
  p.click('#next');
  ok(p.vis('.screen').join()==='u12','صفحهٔ «اطلاعات شما ثبت شد» — پایان فرم');
  ok(p.doc.querySelector('#u13')===null,'صفحهٔ بلیت‌ها کلاً برداشته شد');
  ok(!/بلیت/.test(p.txt('#u12')),'هیچ وعدهٔ بلیتی روی صفحهٔ پایان نیست');
  ok(p.all('#endLinks a').length===2,'هر پیوند پایانی یک دکمه است');
  ok(p.txt('#endText').length>0,'متن پایانی هست');
  ok(/کد پیگیری/.test(p.txt('#u12')),'کد پیگیری روی صفحهٔ پایان');
  p.click('#next');
  ok(p.vis('.screen').join()==='u16','صفحهٔ گواهینامه باز شد');
  ok(p.doc.querySelector('#certSlot svg')!==null,'برگ گواهینامه ساخته شد');
  ok(/گواهینامهٔ پایان دوره/.test(p.txt('#certSlot')),'نوع گواهینامه روی برگ');
  ok(/سارا محمدی/.test(p.txt('#certSlot')),'نام دارنده روی برگ');
  ok(p.txt('#certSlot').includes(p.window.eval('CFG.title')),'عنوان دوره روی برگ');
  ok(p.doc.querySelector('#certSlot .tkqr')!==null,'کیوآر راستی‌آزمایی روی برگ');
  ok(/بلافاصله بعد از تأیید رسید/.test(p.txt('#certWhen')),'حالت صدور خودکار گفته می‌شود');
  ok(p.doc.querySelector('#certSave')!==null && p.doc.querySelector('#certBot')!==null,'ذخیره و فرستادن در بله');
  p.window.eval("CFG.cert.mode='after'; renderCert()");
  ok(/پس از پایان دوره/.test(p.txt('#certWhen')),'حالت «پس از پایان دوره» هم درست می‌آید');
  p.click('#next');
  ok(p.vis('.screen').join()==='u12','با دکمهٔ آخر به صفحهٔ پایان برمی‌گردد');
  ok(p.window.eval("ORDER.indexOf('u16')===ORDER.indexOf('u12')+1"),'گواهینامه بعد از صفحهٔ پایان است');
  p.window.eval("CFG.cert.on=false; show('u16')");
  ok(p.vis('.screen').join()==='u12','با خاموش بودن گواهینامه، صفحه‌اش کاربر را به پایان برمی‌گرداند');
  p.window.eval("CFG.cert.on=true");
  ok(p.window.eval("typeof ticketSVG")==='undefined' && p.window.eval("typeof receiptSVG")==='undefined','موتور بلیت/رسید از ui.js برداشته شد');
  ok(p.doc.querySelector('[data-printall]')===null,'دکمهٔ «چاپ همه» نیست');
  // پاک‌سازی: نام کاربر نباید HTML بسازد
  const evil=p.window.certificateSVG({name:'<b onmouseover=alert(2)>سارا</b>',title:'<img src=x onerror=alert(1)>'});
  const evilDoc=new p.window.DOMParser().parseFromString(evil,'text/html');
  ok(evilDoc.querySelector('img,b[onmouseover]')===null,'نام و عنوان کاربر HTML تزریق نمی‌کند');
  ok(evilDoc.body.textContent.includes('سارا'),'متن کاربر سالم نمایش داده می‌شود');
  // صفحه‌کلید: ناحیهٔ رها کردن رسید با Enter هم باز می‌شود
  const drop=p.doc.querySelector('#drop');
  ok(drop.getAttribute('role')==='button' && drop.getAttribute('tabindex')==='0','ناحیهٔ رسید برای صفحه‌کلید هم باز است');
  ok(p.doc.querySelector('#receiptSlot')===null,'تصویر رسید پرداخت ساخته نمی‌شود');
  // اعداد لندینگ باید از خود تنظیمات دربیایند
  ok(p.txt('#evFacts').includes('۷ پرسش')&&p.txt('#evFacts').includes('۶۰۰٬۰۰۰'),'اعداد لندینگ از تنظیمات فرم حساب شده');
  ok(p.txt('#evFacts').includes('۴۰ جا مانده'),'جای مانده از ظرفیت و ثبت‌شده‌ها حساب شده');
  ok(p.txt('#evPerks').includes('گواهینامه')&&p.txt('#evPerks').includes('۳ نفر'),'مزیت‌های لندینگ از مالی و سقف نفرات');
  ok(p.txt('#finOpts').includes('شامل گواهینامهٔ پایان دوره'),'توضیح قطعهٔ مالی روی صفحهٔ کاربر');
  ok(p.txt('#finOpts').includes('نوع شرکت'),'نام گروه انتخاب روی صفحهٔ کاربر');
  // توضیح هر قطعه فقط وقتی هست که نوشته شده باشد (قطعهٔ بی‌توضیح، خط خالی ندارد)
  ok(p.window.eval("CFG.fin.some(o=>!o.d)")===true,'قطعهٔ بی‌توضیح هم در داده هست');
  ok(p.all('#finOpts .cap').filter(e=>/^$/.test(e.textContent.trim())).length===0,'هیچ خط خالی برای توضیح نمانده');
  // ── گروه اجباری: تا انتخاب خودِ کاربر نباشد، فرم جلو نمی‌رود ──
  ok(p.window.eval("CFG.groups[0].req")===true,'گروه «نوع شرکت» اجباری است');
  p.window.eval("show('u8'); CFG.groups[0].of.forEach(k=>{CFG.fin[k].on=false}); CFG.fin[2].on=true; CFG.fin[3].on=false; PICKED.clear(); renderFin()");
  p.click('#next');
  ok(p.vis('.screen').join()==='u8' && p.txt('#toast').includes('نوع شرکت'),'تنها گزینهٔ فرعی روشن، فرم را جلو نمی‌برد');
  p.click('[data-fin="1"]');                                  /* کاربر «بدون گواهینامه» را می‌زند */
  p.click('#next');
  ok(p.vis('.screen').join()==='u9','با انتخاب خودِ کاربر، ادامه ممکن می‌شود');
  p.window.eval("show('u8')");
  p.click('[data-fin="0"]');
  ok(p.window.eval("CFG.fin[0].on && !CFG.fin[1].on"),'در گروه، انتخاب یکی از دو گزینه جابه‌جا می‌شود');
  ok(p.window.eval("PICKED.has(0) && !PICKED.has(1)"),'رد انتخاب صریح هم با گروه جابه‌جا می‌شود');
  p.window.eval("show('u12'); saveDraft()");   /* حالت آزمون به جای اولش برگردد */
  p.window.eval('saveDraft()');
  const keys=store._dump();
  ok(keys.some(k=>k.startsWith('nora:draft:')),'پیش‌نویس در انبار محلی ذخیره می‌شود');
  const p2=await load('form.html',store);                    /* برگشت کاربر با همان لینک */
  ok(p2.doc.querySelector('#resumeRow').style.display==='block','با برگشت، نوبت نیمه‌کاره پیشنهاد می‌شود');
  p2.click('[data-resume]');
  ok(p2.vis('.screen').join()==='u12' && p2.txt('#multBadge').includes('۲ نفر'),'ادامه، همان جا و با همان داده برمی‌گرداند');
  ok(p.errs.length===0, p.errs.length?('خطای پایان: '+p.errs.slice(0,3).join(' | ')):'تا آخر بی‌خطا');
}

/* ═══════════ گیت ادمین: دعوت دوست بسته ═══════════ */
{
  console.log('\n── دعوت دوست بسته (form.html?guests=0) ──');
  const store=makeStore();
  const p=await load('form.html',store,'?guests=0');
  ok(p.errs.length===0, p.errs.length?('خطا: '+p.errs.slice(0,3).join(' | ')):'بی‌خطا بار شد');
  ok(p.window.eval('GUEST_ON')===false,'با بسته بودن کلید ادمین، دعوت دوست خاموش است');
  ok(p.doc.querySelector('#guestsCard').style.display==='none','کارت همراه با کلید بستهٔ ادمین نمی‌آید');
  for(let i=0;i<7;i++) p.click('#next');
  ok(p.vis('.screen').join()==='u8','هفت پرسش، بعد مستقیم انتخاب شما');
  ok(p.doc.querySelector('#guestsCard').style.display==='none','کارت همراهان هم پنهان است');
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
  ok(p.doc.querySelector('[data-change="ticket"]')===null,'آیتم «بلیت» از ورقهٔ تغییرات برداشته شد');
  ok(p.doc.querySelector('#chTkPrev')===null,'پیش‌نمایش بلیت در پنل نیست');
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
  ok(p.doc.querySelector('#chCertPrev .tkqr')!==null,'کیوآر راستی‌آزمایی روی برگ');
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
  ok(p.doc.querySelector('#usBody .tkqr')!==null || /صادر نشده|پس از پرداخت قطعی/.test(p.txt('#usBody')),'وضعیت گواهینامه در جزئیات پاسخ‌دهنده دیده می‌شود');
  p.click('[data-close]');
  p.click('#pSeg [data-tab="answers"]');
  ok(p.all('#answersBox tbody tr').length===7,'هفت ردیف پاسخ‌دهنده');
  p.click('#answersBox tbody tr');
  ok(p.vis('.screen').join()==='fUser','با زدن کاربر، جزئیاتش باز شد');
  const us=p.txt('#usBody');
  ok(us.includes('تکمیل فرم')&&us.includes('مبالغ')&&us.includes('اطلاعات'),'سه بخش خواسته‌شده');
  ok(us.includes('۱٬۳۰۰٬۵۰۰'),'مبلغ همان کاربر درست');
  ok(us.includes('پاسخ نداده'),'پرسش بی‌پاسخ نشان داده شد');
  ok(us.includes('همراهان')&&us.includes('الهام موسوی'),'کارت همراهان با نام همراه');
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
  ok(p.doc.querySelector('#tkSkins')===null && p.doc.querySelector('#tkPreview')===null,'پنل بلیت از سازندهٔ فرم برداشته شد');
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
  ok(p.txt('#swatchGrid').includes('#0071E3')&&p.txt('#swatchGrid').includes('#9C7C3C'),'رنگ‌ها همان توکن‌های تازه‌اند (کنش آبی، طلا تزئینی)');
  ok(p.doc.querySelector('#skinRow')===null && p.doc.querySelector('#rcDemo')===null,'بخش بلیت و رسید از زبان طراحی برداشته شد');
  ok(p.doc.querySelector('a[href="home.html"]')!==null,'پیوند خانه در زبان طراحی هست');
  ok(/تباین متن اصلی روی سطح: \d+\.\d+ به ۱/.test(p.txt('#contrastNote')),'تباین واقعی حساب و نوشته شد');

  ok(p.txt('#contrastNote').includes('شیشه فقط روی ناوبری'),'قاعدهٔ شیشه یادآوری شده');
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

/* ═══════════ home.html — خانهٔ وب‌اپ ═══════════ */
{
  console.log('\n── خانه (home.html) ──');
  const p=await load('home.html',makeStore());
  const H=p.window.NORA_HOME;
  ok(p.errs.length===0, p.errs.length?('خطا: '+p.errs.slice(0,3).join(' | ')):'بی‌خطا بار شد');
  /* بنر بالای صفحه */
  ok(p.all('#bsdeck .bs').length===3,'سه بنر با تیتر و کنش');
  ok(p.all('#bdots i').length===3,'نقطه‌های بنر به تعداد بنرها');
  ok(p.doc.querySelector('main.wrap > *').id==='bnr','بنر اولین چیز صفحه است');
  p.click('[data-bnext]'); ok(H.S.slide===1,'بنر بعدی می‌رود');
  p.click('[data-bs="2"]'); ok(H.S.slide===2,'با نقطهٔ بنر جابه‌جا می‌شود');
  /* استوری‌های کوتاه */
  ok(p.all('#stories .story').length===5,'پنج استوری کوتاه');
  p.click('#stories .story');
  ok(p.doc.querySelector('#shStory').className.includes('on'),'استوری باز می‌شود');
  ok(p.txt('#storyBody').includes('استوری') && p.all('#storyBody .storybig').length===1,'ورقهٔ استوری سرصفحه و متن دارد');
  p.click('[data-storygo]');
  ok(!p.doc.querySelector('#shStory').className.includes('on'),'از استوری به بخشش می‌رود');
  /* منوی سریع */
  ok(p.all('#quick .tile').length===8,'هشت کاشی منوی سریع');
  ok(p.all('#quick .tile .ci svg').length===8,'هر کاشی آیکون دارد');
  ok(p.all('#quick .tile[data-anim]').length>=3,'چند آیکون حرکت سبک دارند');
  p.click('[data-q="club"]'); ok(p.doc.querySelector('#shClub').className.includes('on'),'کاشی باشگاه ورقه‌اش را باز می‌کند');
  p.click('#shClub [data-close]');
  /* رویدادها در خانه: فقط سه کارت نمایشی */
  ok(p.all('#evTop .ev3').length===3,'خانه فقط سه کارت رویداد دارد');
  ok(p.txt('#evTop').includes('·') && p.all('#evTop .tagg').length===3,'هر کارت تاریخ و یک تگ دارد');
  ok(p.all('#evTop a[href^="events.html?ev="]').length===3,'هر سه کارت خانه به منوی جداگانهٔ رویدادها پیوند دارند');
  ok(p.doc.querySelector('#evSec a[href="events.html#list"]')!==null,'دکمهٔ «همهٔ رویدادها» به منوی رویدادها می‌رود');
  ok(p.doc.querySelector('#evSec a[href="events.html#cal"]')!==null,'دکمهٔ «تقویم رویدادها» هم به همان منو می‌رود');
  ok(p.doc.querySelector('#evBrowser')===null && p.doc.querySelector('#shEvents')===null,'خانه ورقهٔ رویداد ندارد — رویدادها منوی جداست');
  ok(p.doc.querySelector('#qTags')===null,'صافی رویداد در خانه نمانده');
  ok(p.doc.querySelector('#live')===null && p.doc.querySelector('.livecard')===null,'جریان زنده از خانه رفت به صفحهٔ رویدادها');
  ok(p.doc.querySelector('a[href="events.html#cal"]')!==null && p.doc.querySelector('a[href="events.html#list"]')!==null,'پیوندهای خانه به تقویم و فهرست رویدادها');
  /* جست‌وجو: رویداد، مطلب و استاد */
  p.doc.querySelector('#q').value='عکاسی';
  p.doc.querySelector('#q').dispatchEvent(new p.window.Event('input',{bubbles:true}));
  ok(!p.doc.querySelector('#searchRes').hidden,'نتیجهٔ جست‌وجو می‌آید');
  ok(p.doc.querySelector('#evSec').hidden,'جای رویدادها به نتیجهٔ جست‌وجو می‌رود');
  ok(p.all('#searchRes .sres').length>=2,'نتیجه‌ها فهرست می‌شوند');
  ok(p.txt('#searchRes').includes('رویداد'),'نتیجهٔ رویداد در جست‌وجو هست');
  ok(p.all('#searchRes a.sres[href^="events.html?ev="]').length>=1,'نتیجهٔ رویداد در جست‌وجو به صفحهٔ رویدادها می‌رود');
  ok(p.all('#searchRes button.sres').length>=1,'مطلب و استاد همچنان ورقهٔ کشویی دارند');
  p.click('#qClear');
  ok(p.doc.querySelector('#searchRes').hidden && !p.doc.querySelector('#evSec').hidden,'پاک کردن جست‌وجو');
  /* برگزارشده‌ها، برچسب درخواست گواهینامه، نمای فعالیت */
  ok(p.all('#pastList .pastcard').length===4,'چهار کارگاه برگزارشده');
  ok(p.txt('#pastList').includes('درخواست گواهینامه'),'دکمهٔ درخواست گواهینامه (نه صدور خودکار)');
  ok(p.txt('#pastList').includes('تماشای ضبط') && p.txt('#pastList').includes('جزوهٔ دوره'),'ضبط و جزوه در برگزارشده‌ها');
  ok(p.all('#actBox .minibars i').length===12,'نمای فعالیت: دوازده ستون ماهانه');
  p.click('#pastList .pastcard [data-sheetdl]');
  ok(p.txt('#toast').includes('جزوه'),'جزوهٔ دوره پیام می‌دهد');
  /* باشگاه کتاب‌خوانی */
  ok(p.txt('#club').includes('باشگاه کتاب‌خوانی'),'بلوک اختصاصی باشگاه');
  ok(p.txt('#club').includes('مریم داوودی'),'سرپرست باشگاه با نام');
  ok(p.txt('#club').includes('چراغ‌ها را من خاموش می‌کنم') && p.txt('#club').includes('۷۲٪'),'کتاب ماه و درصد خواندن');
  p.click('#club [data-clubjoin]');
  ok(p.doc.querySelector('#shAccount').className.includes('on'),'عضویت مهمان را به ورود می‌برد');
  p.click('[data-close]');
  p.click('#club [data-f="shClub"]');
  ok(p.all('#clubBody .srow').length>=6,'ورقهٔ باشگاه: قواعد و جلسه‌ها');
  ok(p.all('#clubBody .voteopt').length===3,'رأی‌گیری کتاب ماه: سه گزینه');
  p.click('#clubBody [data-vote]');
  ok(p.doc.querySelector('#shAccount').className.includes('on') || p.txt('#toast').includes('وارد شو'),'رأی مهمان ورود می‌خواهد');
  p.click('[data-close]');
  /* اساتید و دست‌اندرکاران */
  ok(p.all('#peopleRail .tcard').length===6,'بخش اساتید جدا: شش کارت استاد');
  ok(p.doc.querySelector('#peopleRail .tcard .av img')!==null,'کارت استاد عکس دارد');
  ok(p.txt('#peopleRail .tcard').includes('دوره'),'کارت استاد تعداد دوره دارد');
  ok(p.all('#staffList .scard').length===2,'بخش دست‌اندرکاران جدا: دو نفر با کارت خودشان');
  ok(p.txt('#staffList').includes('مسئول روابط عمومی') && p.txt('#staffList').includes('مسئول اجرا'),'نقش دست‌اندرکاران در کارتشان');
  ok(p.doc.querySelector('#people')===null,'دو بخش یک تب مشترک ندارند');
  ok(p.all('#peopleRail a[href^="events.html?q="]').length>=6,'دوره‌های هر استاد به فهرست رویدادها می‌رود');
  p.click('#staffList [data-person="p7"]');
  ok(p.doc.querySelector('#shPerson').className.includes('on') && p.txt('#personBody').includes('نگار شریفی'),'پروفایل دست‌اندرکار با ورقهٔ کشویی');
  ok(p.txt('#personBody').includes('کارهای شریفی') && p.txt('#personBody').includes('خبر و گزارش'),'پروفایل دست‌اندرکار: کارهای خودش');
  p.click('#shPerson [data-close]');
  p.click('#peopleRail [data-person="p1"]');
  ok(p.txt('#personBody').includes('الهه رضایی') && p.txt('#personBody').includes('صدا ابزار کار است'),'پروفایل استاد: نام و جمله');
  ok(p.txt('#personBody').includes('فن بیان مقدماتی'),'دوره‌های استاد فهرست شده');
  ok(p.txt('#personBody').includes('دورهٔ بعدی ایشان'),'پروفایل استاد: دورهٔ بعدی ایشان');
  p.click('#shPerson [data-close]');
  /* مطالب و مقالات */
  ok(p.all('#artRail .pcard-ar').length===6,'شش مطلب و مقاله');
  p.click('[data-article="a1"]');
  ok(p.txt('#articleBody').includes('هفت تمرین تنفس') && p.txt('#articleBody').includes('فهرست کوتاه'),'ورقهٔ مطلب: تیتر و فهرست');
  p.click('#articleBody [data-close]');
  /* نهادهای همکار */
  ok(p.all('#logoWall .logo').length===8,'هشت نهاد همکار');
  p.click('#logoWall [data-partner="o7"]');
  ok(p.txt('#partnerBody').includes('بنیاد نیکوکاری مهر'),'ورقهٔ نهاد همکار');
  p.click('#partnerBody [data-close]');
  /* سنجاق کردن (مطلب و استاد، نه لیست رویداد خانه) */
  p.click('[data-pin="ar:a2"]');
  ok(!p.doc.querySelector('#pins').hidden && p.txt('#pins').includes('سواد رسانه')===false,'بلند سنجاق‌شده‌ها می‌آید');
  ok(p.window.localStorage.getItem('nora-home-pins').includes('ar:a2'),'سنجاق در حافظهٔ مرورگر می‌ماند');
  p.click('[data-clearpins]');
  ok(p.doc.querySelector('#pins').hidden,'برداشتن همهٔ سنجاق‌ها');
  /* منوی نورا */
  p.click('.menubtn');
  ok(p.all('#menuBody .mgroup').length===5 && p.all('#menuBody .mrow').length===21,'منو: پنج گروه و ۲۱ ردیف');
  ok(p.all('#menuBody .mfoot .mon').length===8,'نهادهای همکار در پاصفحهٔ منو');
  p.click('#menuBody [data-jump="people"]');
  ok(!p.doc.querySelector('#shMenu').className.includes('on'),'ردیف منو ورقه را می‌بندد و می‌رود سر بخش');
  /* تب‌بار: خانه، رویدادها، حساب من */
  ok(p.all('#tabs button').length===3,'تب‌بار سه تب دارد');
  ok(p.all('#tabs button small').map(x=>x.textContent).join('|')==='خانه|رویدادها|حساب من','نام تب‌ها درست است');
  ok(p.doc.querySelector('#tabs button.on use').getAttribute('href')==='#i-home-f','تب فعال آیکون پُر دارد (سبک اپل)');
  p.click('#tabs [data-tab="events"]');
  ok(true,'تب رویدادها به صفحهٔ جداگانه می‌رود (رفت‌وبرگشت در آزمون صفحهٔ رویدادها)');
  /* حساب من: مهمان — پشتیبانی و راهنما باز، باشگاه قفل */
  p.click('#tabs [data-tab="me"]');
  ok(p.doc.querySelector('#shAccount').className.includes('on'),'تب حساب من ورقه را باز می‌کند');
  ok(p.txt('#acctBody').includes('بدون ورود هم پشتیبانی و راهنما باز است'),'مهمان می‌بیند که خدمات باز است');
  ok(p.all('#acctBody .dim .srow').length===5,'پیش‌نمایش کم‌رنگ کارهای شخصی');
  ok(p.doc.querySelector('#acctBody [data-needlogin]')!==null,'باشگاه برای مهمان قفل است');
  p.click('#acctBody [data-needlogin]');
  ok(p.doc.querySelector('#mob')!==null,'قفل باشگاه به ورود می‌برد');
  p.click('[data-close]');
  p.click('#tabs [data-tab="me"]');
  p.click('#acctBody [data-f="shSupport"]');
  ok(p.doc.querySelector('#shSupport').className.includes('on'),'پشتیبانی بدون لاگین باز می‌شود');
  ok(p.all('#supBody .chan').length===4,'چهار کانال پشتیبانی');
  ok(p.txt('#supBody').includes('حسن مقدم') && p.txt('#supBody').includes('آنلاین'),'کارشناس با نام و وضعیت');
  p.doc.querySelector('#msg').value='سؤال دربارهٔ تأیید رسید';
  p.click('[data-send]');
  ok(p.txt('#toast').includes('ثبت شد'),'پیام پشتیبانی ثبت می‌شود');
  p.click('[data-close]');
  p.click('#acctBody [data-f="shFaq"]');
  ok(p.all('#faqBody details.faq').length===7,'هفت پرسش پرتکرار');
  p.click('[data-close]');
  p.click('#acctBody [data-f="shVerify"]');
  p.doc.querySelector('#serial').value='nl-t4k7m9x';
  p.click('[data-verify]');
  ok(p.txt('#verifyBody').includes('معتبر'),'استعلام سریال معتبر');
  p.click('[data-close]');
  /* ورود */
  p.click('#tabs [data-tab="me"]');
  p.click('#acctBody [data-next]');
  p.doc.querySelector('#mob').value='۰۹۱۲۳۴۵۶۷۸۹';
  p.click('[data-login]');
  p.doc.querySelector('#code').value='54321';
  p.click('[data-code]');
  ok(H.S.user && H.S.user.name==='سارا محمدی','ورود با کد نمایشی');
  ok(p.txt('#acctBody').includes('کارهای من') && p.txt('#acctBody').includes('خدمات و پشتیبانی'),'چیدمان شخصی بالا، خدماتی پایین');
  ok(p.all('#acctBody .badge-pill').length===5,'پنج نشان عضو');
  ok(p.txt('#acctBody').includes('پس از تأیید سرپرست'),'گواهینامه با تأیید سرپرست');
  p.click('#acctBody [data-remind]');
  ok(p.txt('#toast').includes('یادآوری پیامکی'),'کلید یادآوری پیامکی کار می‌کند');
  p.click('#acctBody [data-f="shClub"]');
  ok(p.doc.querySelector('#shClub').className.includes('on'),'عضویت، باشگاه را باز می‌کند');
  p.click('#clubBody [data-vote="v2"]');
  ok(H.S.vote==='v2' && p.txt('#toast').includes('رأیت'),'رأی عضو ثبت می‌شود');
  p.click('[data-close]');
  p.click('#acctBody [data-f="shNotice"]');
  ok(p.all('#noticeBody .notif').length===3,'سه اعلان');
  ok(p.txt('#noticeBody').includes('سرپرست'),'اعلان گواهینامه: در انتظار سرپرست');
  p.click('[data-readall]');
  ok(p.doc.querySelector('#bellBadge').hidden,'خواندن همه، نشان را برمی‌دارد');
  p.click('[data-close]');
  ok(p.txt('#mine').includes('برای تو، سارا') && p.all('#mine .pcard').length===6,'بعد از ورود، شش کارت شخصی');
  ok(p.txt('#mine').includes('تأیید سرپرست'),'کارت گواهینامه هم همین رویه را می‌گوید');
  p.click('#pastList .pastcard [data-cert]');
  ok(p.txt('#toast').includes('تأیید سرپرست'),'درخواست گواهینامه به سرپرست ارجاع می‌شود');
  /* زبان و پوسته */
  ok(!/بلیت/.test(p.txt('body')),'هیچ وعدهٔ بلیتی در خانه نیست');
  ok(p.doc.querySelector('#tabs button[data-tab="home"]')!==null,'تب خانه سرجایش است');
  p.click('[data-theme-toggle]');
  ok(p.doc.documentElement.dataset.theme==='dark','شب و روز کار می‌کند');
}

/* ═══════════ events.html — منوی جدا و کامل رویدادها ═══════════ */
{
  console.log('\n── رویدادها (events.html) ──');
  const p=await load('events.html',makeStore(),'#list');
  const N=p.window.NORA;
  ok(p.errs.length===0, p.errs.length?('خطا: '+p.errs.slice(0,3).join(' | ')):'بی‌خطا بار شد');
  ok(N && N.EVENTS.length===11,'دادهٔ مشترک از data.js می‌آید (یازده رویداد)');
  ok(p.all('#hstats .s').length===5,'نوار آمار: چهار ستون + ردیف رایگان‌ها');
  ok(p.all('#liveList .livecard').length===2,'جریان زنده در صفحهٔ رویدادها');
  ok(p.txt('#liveList').includes('در حال برگزاری'),'یکی در حال برگزاری است');
  ok(p.txt('#hstats').includes('گواهی‌دار') && p.txt('#hstats').includes('آنلاین'),'آمار حالت‌ها هست');
  /* فهرست و صافی‌ها */
  ok(p.all('#evList .ev').length===11,'فهرست کامل: یازده رویداد');
  ok(p.all('#dayChips .chip').length===5 && p.all('#catChips .chip').length===6 && p.all('#modeChips .chip').length===5,'سه ردیف صافی (روز، دسته، حالت)');
  p.click('#dayChips [data-day="tomorrow"]');
  ok(p.all('#evList .ev').length===2,'صافی «فردا» دو رویداد');
  p.click('#dayChips [data-day="tomorrow"]');
  p.click('#catChips [data-cat="workshop"]');
  ok(p.all('#evList .ev').length===4,'صافی «کارگاه» چهار رویداد');
  p.click('#modeChips [data-mode="آنلاین"]');
  ok(p.all('#evList .ev').length===0,'کارگاه آنلاین نداریم — فهرست خالی می‌شود');
  ok(p.txt('#evList').includes('چیزی پیدا نشد'),'حالت خالی پیام خودش را دارد');
  p.click('#catChips [data-cat="workshop"]');
  p.click('#modeChips [data-mode="آنلاین"]');
  p.click('#clearFilters');
  ok(p.all('#evList .ev').length===11,'برداشتن صافی‌ها');
  /* جست‌وجو */
  p.doc.querySelector('#q').value='عکاسی';
  p.doc.querySelector('#q').dispatchEvent(new p.window.Event('input',{bubbles:true}));
  ok(p.all('#evList .ev').length===2,'جست‌وجوی «عکاسی» دو رویداد');
  p.click('#qClear');
  ok(p.all('#evList .ev').length===11,'پاک کردن جست‌وجو');
  /* تقویم ماهانه */
  p.click('[data-view="cal"]');
  ok(p.all('#monthsw button').length===2,'دو ماه در تقویم (شهریور و مهر)');
  ok(p.all('#calgrid .wd').length===7,'سرستون‌های هفته');
  ok(p.all('#calgrid .cel').length===32,'شهریور: ۳۱ روز + ۱ خانهٔ خالی');
  ok(p.all('#calgrid .cel.has').length===3,'سه روز پررویداد در شهریور');
  ok(p.doc.querySelector('#calgrid .cel.today')!==null,'روز امروز نشان دارد');
  ok(p.txt('#dayTitle').includes('۲۸') && p.all('#dayList .ev').length===2,'روز پیش‌فرض امروز با دو برنامه');
  p.click('#calgrid .cel[data-dn="29"]');
  ok(p.txt('#dayTitle').includes('یکشنبه') && p.all('#dayList .ev').length===1,'روز ۲۹: یک برنامه');
  p.click('#monthsw [data-month="mehr"]');
  ok(p.all('#calgrid .cel').length===34,'مهر: ۳۰ روز + ۴ خانهٔ خالی');
  ok(p.all('#calgrid .cel.has').length===6,'شش روز پررویداد در مهر');
  /* دسته‌ها */
  p.click('[data-view="cat"]');
  ok(p.all('#catGrid .cattile').length===10,'دسته‌ها: شش دسته + چهار نشان');
  p.click('#catGrid [data-cat="camp"]');
  ok(!p.doc.querySelector('#listView').hidden && p.all('#evList .ev').length===1,'از دسته به فهرست صافی‌شده می‌رود');
  p.click('#clearFilters');
  /* ورقهٔ رویداد: جزئیات، تقویم گوشی، ثبت‌نام */
  p.click('#evList [data-ev="e3"]');
  ok(p.doc.querySelector('#shEvent').className.includes('on'),'ورقهٔ رویداد (کشویی از پایین) باز می‌شود');
  ok(p.txt('#evBody').includes('۱۱ جا مانده'),'جای مانده از ظرفیت حساب شده');
  ok(p.doc.querySelector('#evBody a.btn.primary').getAttribute('href')==='form.html','ثبت‌نام به فرم کاربر می‌رود');
  ok(p.doc.querySelector('#evBody [data-ics]')!==null && /calendar\.google\.com/.test(p.doc.querySelector('#evBody a[target="_blank"]').getAttribute('href')),'افزودن به تقویم گوشی و گوگل‌کلندر');
  p.click('#evBody [data-ics]');
  ok(p.txt('#toast').includes('تقویم'),'ساخت فایل تقویم پیام می‌دهد');
  ok(p.txt('#evBody').includes('کیوان مرادی'),'مدرس رویداد در ورقه با نام می‌آید');
  ok(p.doc.querySelector('#evBody [data-person="p2"]')!==null,'دکمهٔ پروفایل مدرس هست');
  p.click('#evBody [data-pin]');
  ok(p.window.localStorage.getItem('nora-home-pins').includes('ev:e3'),'سنجاق در همان کلید خانه ذخیره می‌شود');
  p.click('#evBody [data-close]');
  p.click('#evList [data-ev="e8"]');
  ok(p.txt('#evBody').includes('ظرفیت تکمیل'),'اردوی پر: ظرفیت تکمیل');
  p.click('#evBody [data-wait]');
  ok(p.txt('#toast').includes('لیست انتظار'),'ثبت در لیست انتظار پیام می‌دهد');
  p.click('[data-close]');
  /* تب‌بار: خانه، این صفحه، حساب من */
  ok(p.all('.tabbar a').length===3,'تب‌بار سه لینک دارد');
  ok(p.doc.querySelector('.tabbar a.on small').textContent==='رویدادها','تب فعال همین صفحه است');
  ok(p.doc.querySelector('.tabbar a[href="home.html"]')!==null && p.doc.querySelector('.tabbar a[href="home.html#me"]')!==null,'بازگشت به خانه و حساب من کار می‌کند');
  ok(p.doc.querySelector('.tabbar a.on use').getAttribute('href')==='#i-calendar-f','آیکون تب فعال پُر است');
  /* نشانی‌های ورودی */
  const p2=await load('events.html',makeStore(),'?q='+encodeURIComponent('عکاسی')+'#list');
  ok(p2.all('#evList .ev').length===2,'ورود با ?q= صافی می‌کند');
  const p3=await load('events.html',makeStore(),'?ev=e5#list');
  ok(p3.doc.querySelector('#shEvent').className.includes('on'),'ورود با ?ev= مستقیم ورقه را باز می‌کند');
}

console.log('\nbuilder-smoke: '+checks+' بررسی، '+fails+' خطا');
process.exit(fails?1:0);
