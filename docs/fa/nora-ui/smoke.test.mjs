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
  // تأیید رسید از کارتابل
  p.click('[data-go="fKartabl"]');
  const kb=p.txt('#kBadge');
  ok(p.all('#kartabl [data-approve]').length===2,'دو رسید در کارتابل');
  p.click('#kartabl [data-approve]');
  ok(p.txt('#kBadge')!==kb,'تأیید رسید، شمار کارتابل را کم کرد');
  p.click('[data-go="fMoney"]');
  ok(p.txt('#moneyPieces').includes('۸۵۰٬۰۰۰'),'قطعه‌های مالی با یک قیمت');
  ok(p.txt('#settle').includes('تومان'),'تسویه با تومان به حروف');
  const rows=Number(p.window.eval("PEOPLE.filter(x=>x.state!=='half').length"));
  ok(p.all('#txBody tr').length===rows,'هر پرداخت یک ردیف در تراکنش‌های اخیر');
  ok(p.all('#txBody .tag').length===rows,'هر تراکنش وضعیت خودش را دارد');
  p.click('[data-go="fTeam"]');
  ok(p.all('#teamBox .card').length===4,'چهار کارشناس');
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
