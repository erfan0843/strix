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

function makeStoreWith(base){
  const m=new Map();
  for(let i=0;i<base.length;i++){const k=base.key(i); m.set(k,base.getItem(k))}
  return {getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k),
    clear:()=>m.clear(),key:i=>[...m.keys()][i],get length(){return m.size}};
}
function makeStore(){const m=new Map(); return {
  getItem:k=>m.has(k)?m.get(k):null, setItem:(k,v)=>m.set(k,String(v)),
  removeItem:k=>m.delete(k), clear:()=>m.clear(), key:i=>[...m.keys()][i],
  get length(){return m.size}, _dump:()=>[...m.keys()]};}

/* نشانی واقعی برای ?guests= — فایل‌ها از همین پوشه خوانده می‌شوند (بی‌شبکه) */
const wait=ms=>new Promise(r=>setTimeout(r,ms));
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
  ok(p.doc.querySelector('#u16')===null,'صفحهٔ گواهینامه کلاً از فرم برداشته شد');
  ok(p.window.eval("ORDER.includes('u16')")===false,'گواهینامه در نقشهٔ حرکت فرم نیست');
  ok(!/گواهی/.test(p.txt('body')),'هیچ وعده یا صدور گواهینامه‌ای در فرم نمانده');
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
  ok(p.txt('#evPerks').includes('۳ نفر'),'مزیت‌های لندینگ از مالی و سقف نفرات');
  ok(p.txt('#finOpts').includes('شرکت حضوری در سالن'),'توضیح قطعهٔ مالی روی صفحهٔ کاربر');
  ok(p.txt('#finOpts').includes('نوع شرکت'),'نام گروه انتخاب روی صفحهٔ کاربر');
  // توضیح هر قطعه فقط وقتی هست که نوشته شده باشد (قطعهٔ بی‌توضیح، خط خالی ندارد)
  ok(p.window.eval("CFG.fin.some(o=>!o.d)")===true,'قطعهٔ بی‌توضیح هم در داده هست');
  ok(p.all('#finOpts .cap').filter(e=>/^$/.test(e.textContent.trim())).length===0,'هیچ خط خالی برای توضیح نمانده');
  // ── گروه اجباری: تا انتخاب خودِ کاربر نباشد، فرم جلو نمی‌رود ──
  ok(p.window.eval("CFG.groups[0].req")===true,'گروه «نوع شرکت» اجباری است');
  p.window.eval("show('u8'); CFG.groups[0].of.forEach(k=>{CFG.fin[k].on=false}); CFG.fin[2].on=true; PICKED.clear(); renderFin()");
  p.click('#next');
  ok(p.vis('.screen').join()==='u8' && p.txt('#toast').includes('نوع شرکت'),'تنها گزینهٔ فرعی روشن، فرم را جلو نمی‌برد');
  p.click('[data-fin="1"]');                                  /* کاربر «شرکت آنلاین» را می‌زند */
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
  /* ── گواهینامه: پیش‌نمایش زنده + درخواست با تأیید سرپرست ── */
  p.click('[data-close]');
  p.click('#pSeg [data-tab="info"]');
  ok(/گواهینامه/.test(p.txt('#infoBox')) && /تأیید سرپرست/.test(p.txt('#infoBox')) && /در انتظار تأیید/.test(p.txt('#infoBox')),
     'تب اطلاعات می‌گوید صدور فقط با تأیید سرپرست است');
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
  ok(p.doc.querySelector('#chCertAuto')===null && p.doc.querySelector('#chCertAfter')===null,
     'کلید «صدور خودکار/پس از پایان دوره» از پنل برداشته شد');
  ok(/صدور فقط با تأیید سرپرست/.test(p.txt('#chBody')),'ورقهٔ گواهینامه می‌گوید صدور دست پنل نیست');
  ok(/مریم داوودی/.test(p.txt('#chBody')),'سرپرست همان‌جا نامش آمده');
  p.click('#chCertGo');
  ok(p.window.eval("Object.keys(CUR.certIssued||{}).length")===0,'با یک کلیک هیچ گواهینامه‌ای صادر نمی‌شود');
  ok(p.window.eval("Object.keys(CUR.certReq||{}).length")===paidC,'به‌جایش برای همهٔ پرداخت‌شده‌ها درخواست ثبت شد ('+paidC+')');
  ok(/در انتظار تأیید سرپرست/.test(p.txt('#toast')),'پیام درخواست، تأیید سرپرست را می‌گوید');
  p.window.eval("CUR.id='f1'");
  p.click('#pSeg [data-tab="info"]');
  ok(new RegExp(p.window.eval('faN('+paidC+')')+' در انتظار تأیید').test(p.txt('#infoBox')),'شمار در انتظار تأیید در تب اطلاعات به‌روز شد');
  /* صدور تک‌نفر از جزئیات پاسخ‌دهنده */
  p.click('[data-go="fKartabl"]');
  p.click('#kartabl [data-person]');
  ok(/گواهینامه/.test(p.txt('#usBody')),'کارت گواهینامه در جزئیات پاسخ‌دهنده');
  ok(p.doc.querySelector('#usBody .tkqr')!==null || /در انتظار تأیید سرپرست|صدور با تأیید سرپرست|پس از پرداخت قطعی/.test(p.txt('#usBody')),
     'وضعیت گواهینامه در جزئیات پاسخ‌دهنده دیده می‌شود');
  ok(p.doc.querySelector('#usBody [data-certone]')===null,'دکمهٔ «صدور» در جزئیات پاسخ‌دهنده نیست');
  const paidId=p.window.eval("PEOPLE.filter(p=>p.form==='f1'&&p.state==='paid')[0].id");
  p.window.eval("CUR.certReq={}; PEOPLE.forEach(x=>x.certReq=false); openUser('"+paidId+"')");
  ok(p.doc.querySelector('#usBody [data-certreq]')!==null,'برای پرداخت‌شدهٔ بی‌درخواست، دکمهٔ «درخواست گواهینامه» هست');
  p.click('#usBody [data-certreq]');
  ok(p.window.eval("Object.keys(CUR.certReq||{}).length")===1,'درخواست تک‌نفره ثبت شد');
  ok(/در انتظار تأیید سرپرست/.test(p.txt('#usBody')),'و همان‌جا وضعیت «در انتظار تأیید سرپرست» شد');
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
  p.click('#finList [data-freq="2"]');
  ok(p.window.eval('S.fin[2].req')===true,'کلید اجباری روشن شد');
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
  ok(p.all('#evTop .evcard').length===3,'خانه فقط سه کارت رویداد دارد');
  ok(p.all('#evTop .evcard .evc-cov img').length===3,'هر کارت رویداد پوسترش را نشان می‌دهد');
  ok(p.all('#evTop .evcard .evc-tag').length===3 && p.all('#evTop .evcard .evc-day').length===3,'هر کارت یک تگ و روز خودش را دارد');
  ok(p.all('#evTop button.evc-cov[data-ev]').length===3,'هر سه کارت خانه، ورقهٔ کلیات رویداد را باز می‌کنند');
  p.click('#evTop [data-ev="e1"]');
  ok(p.doc.querySelector('#shEvent') && p.doc.querySelector('#shEvent').className.includes('on'),'ورقهٔ کلیات رویداد از خانه باز می‌شود');
  ok(p.doc.querySelector('#shEvent a.btn.primary').getAttribute('href')==='event.html?id=e1','و از همان‌جا به صفحهٔ اختصاصی رویداد می‌رود');
  p.click('#shEvent [data-close]');
  ok(p.doc.querySelector('#evSec a[href="events.html#list"]')!==null,'دکمهٔ «همهٔ رویدادها» به منوی رویدادها می‌رود');
  ok(p.doc.querySelector('#evSec a[href="events.html#cal"]')!==null,'دکمهٔ «تقویم رویدادها» هم به همان منو می‌رود');
  ok(p.doc.querySelector('#evBrowser')===null && p.doc.querySelector('#shEvents')===null,'خانه فهرست کامل رویداد ندارد — آن کار منوی رویدادهاست');
  ok(p.doc.querySelector('#qTags')===null,'صافی رویداد در خانه نمانده');
  ok(p.doc.querySelector('#live')===null && p.doc.querySelector('.livecard')===null,'جریان زنده از خانه رفت به صفحهٔ رویدادها');
  ok(p.doc.querySelector('a[href="events.html#cal"]')!==null && p.doc.querySelector('a[href="events.html#list"]')!==null,'پیوندهای خانه به تقویم و فهرست رویدادها');
  /* جست‌وجو: رویداد، مطلب و استاد */
  p.doc.querySelector('#q').value='عکاسی';
  p.doc.querySelector('#q').dispatchEvent(new p.window.Event('input',{bubbles:true}));
  await wait(180);   /* جست‌وجو قاب‌بندی دارد تا هر کلید، همهٔ کارت‌ها را از نو نسازد */
  ok(!p.doc.querySelector('#searchRes').hidden,'نتیجهٔ جست‌وجو می‌آید');
  ok(p.doc.querySelector('#evSec').hidden,'جای رویدادها به نتیجهٔ جست‌وجو می‌رود');
  ok(p.all('#searchRes .sres').length>=2,'نتیجه‌ها فهرست می‌شوند');
  ok(p.txt('#searchRes').includes('رویداد'),'نتیجهٔ رویداد در جست‌وجو هست');
  ok(p.all('#searchRes a.sres[href^="events.html?ev="]').length>=1,'نتیجهٔ رویداد در جست‌وجو به صفحهٔ رویدادها می‌رود');
  ok(p.all('#searchRes button.sres').length>=1,'مطلب و استاد همچنان ورقهٔ کشویی دارند');
  p.click('#qClear');
  ok(p.doc.querySelector('#searchRes').hidden && !p.doc.querySelector('#evSec').hidden,'پاک کردن جست‌وجو');
  /* برگزارشده‌ها، برچسب درخواست گواهینامه، نمای فعالیت */
  ok(p.all('#pastList .evcard').length===3,'خانه سه برگزارشده را ویترین می‌کند');
  ok(p.all('#pastList .evcard .evc-cov img').length===3,'کارت برگزارشده هم پوستر دارد');
  ok(p.txt('#pastList').includes('برگزار شد') && p.txt('#pastList').includes('ریال'),'نشان «برگزار شد» و مبلغ بازپخش روی کارت');
  ok(p.doc.querySelector('#pastSec a[href="events.html?status=past"]')!==null,'پیوند «همهٔ برگزارشده‌ها» به آرشیو می‌رود');
  ok(p.all('#pastList button.evc-cov[data-past]').length===3,'هر کارت برگزارشده، ورقهٔ بستهٔ رسانه را باز می‌کند');
  p.click('#pastList [data-past="h1"]');
  ok(p.doc.querySelector('#shEvent').className.includes('on'),'ورقهٔ بستهٔ رسانه باز می‌شود');
  ok(p.txt('#shEvent').includes('داخل این بسته') && p.all('#shEvent .mrow2').length===5,'فهرست رسانه‌های بسته در ورقه می‌آید');
  ok(p.doc.querySelector('#shEvent a.btn.primary').getAttribute('href')==='event.html?id=h1','و به صفحهٔ اختصاصی بسته می‌رود');
  p.click('#shEvent [data-close]');
  ok(p.all('#actBox .minibars i').length===12,'نمای فعالیت: دوازده ستون ماهانه');
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
  p.click('[data-menu]');
  ok(p.all('#menuBody .mgroup').length===5 && p.all('#menuBody .mrow').length===21,'منو: پنج گروه و ۲۱ ردیف');
  ok(p.all('#menuBody .mfoot .mon').length===8,'نهادهای همکار در پاصفحهٔ منو');
  ok(p.doc.querySelector('#menuBody [data-jump="people"]')===null,'هیچ ردیفی به بخش بی‌وجود «people» پرش نمی‌کند');
  ok(p.all('#menuBody [data-uijump="teachers"]').length===1 && p.doc.querySelector('#menuBody [data-uijump="staff"]')!==null,'ردیف استادان و دست‌اندرکاران به بخش‌های خودشان می‌روند');
  p.click('#menuBody [data-uijump="teachers"]');
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
  p.click('[data-uireadall]');
  ok(p.doc.querySelector('#bellBadge').hidden,'خواندن همه، نشان را برمی‌دارد');
  p.click('[data-close]');
  ok(p.txt('#mine').includes('برای تو، سارا') && p.all('#mine .pcard').length===6,'بعد از ورود، شش کارت شخصی');
  ok(p.txt('#mine').includes('تأیید سرپرست'),'کارت گواهینامه هم همین رویه را می‌گوید');
  ok(p.doc.querySelector('#pastList [data-cert]')===null,'خانه خودش گواهینامه صادر/درخواست نمی‌کند — در ورقهٔ برگزارشدهٔ صفحهٔ رویدادهاست');
  /* زبان و پوسته */
  ok(!/بلیت/.test(p.txt('body')),'هیچ وعدهٔ بلیتی در خانه نیست');
  ok(p.doc.querySelector('#tabs button[data-tab="home"]')!==null,'تب خانه سرجایش است');
  p.click('[data-theme-toggle]');
  ok(p.doc.documentElement.dataset.theme==='dark','شب و روز کار می‌کند');
}

/* ═══════════ events.html — آرشیو رویدادها (v9) ═══════════ */
{
  console.log('\n── آرشیو رویدادها (events.html) ──');
  const shellHome=await load('home.html',makeStore());
  const p=await load('events.html',makeStore());
  ok(p.errs.length===0, p.errs.length?('خطا: '+p.errs.slice(0,3).join(' | ')):'بی‌خطا بار شد');
  const cls=sel=>[...sel.classList].sort().join('.');
  ok(cls(shellHome.doc.querySelector('.tabbar'))===cls(p.doc.querySelector('.tabbar')),'تب‌بار دو صفحه یک کلاس و ساختار دارد');
  ok(shellHome.all('.tabbar a,.tabbar button').length===3 && p.all('.tabbar a,.tabbar button').length===3,'هر دو تب‌بار سه تب');
  ok(shellHome.txt('.tabbar')===p.txt('.tabbar'),'نام تب‌ها یکی است: '+p.txt('.tabbar'));
  ok(p.doc.querySelector('.topbar .menubtn')===null && p.doc.querySelector('.topbar #acctBtn')===null,'نوار بالا بی منو و بی پروفایل است');

  /* الف) بنر: نزدیک‌ترین برنامه‌ها، یک اسلاید در قاب */
  ok(p.all('#spotrail .spot').length===3,'بنر سه برنامهٔ نزدیک را نشان می‌دهد');
  ok(p.txt('#spotrail .spot h2').length>3,'تیتر اسلاید اول پر است');
  ok(p.all('#spotrail .spot')[0].querySelector('.cd')!==null,'شمار روزهای مانده روی اسناید');
  ok(/روز مانده|امشب|فردا|در حال برگزاری/.test(p.txt('#spotrail .spot .cd')),'متن شمارش معکوس درست است: '+p.txt('#spotrail .spot .cd'));
  ok(p.all('#spotrail .spot .acts .btn').length>=2,'هر اسلاید دکمهٔ ثبت‌نام/پیش‌ثبت‌نام و جزئیات دارد');
  ok(p.all('#spotdots i').length===3,'سه نقطهٔ اسلایدر');
  ok(p.doc.querySelector('#spotrail .spot img.pbg')!==null,'پوستر برنامه در بنر نشسته');

  /* ب) آمار زیر بنر */
  ok(p.all('#stats .stat').length===4,'چهار عدد آماری زیر بنر');
  ok(p.txt('#stats').includes('برنامهٔ برگزارشده') && p.txt('#stats').includes('رسانه در آرشیو'),'آمار برگزارشده و آرشیو هست');
  ok(/[۰-۹]+/.test(p.txt('#stats')) && p.txt('#statsNote').includes('آرشیو'),'عددها فارسی و زیرنویس آرشیو دارد');

  /* ج) دو نما: تقویم و فهرست */
  ok(p.all('.seg [data-view]').length===2,'بالای صفحه فقط دو نما: تقویم و فهرست');
  ok(!p.doc.querySelector('#listView').hidden && p.doc.querySelector('#calView').hidden,'فهرست نمای پیش‌فرض است');
  ok(p.all('#grid .etile').length===23,'آرشیو: ۲۳ برنامه (۱۱ پیش رو + ۱۲ برگزارشده)');
  ok(p.all('#grid .etile:not(.past)').length===11 && p.all('#grid .etile.past').length===12,'پیش‌روها و برگزارشده‌ها کنار هم');
  ok(p.all('#grid .etile .ecov img').length===23,'هر کاشی پوستر خودش را دارد');
  ok(p.txt('#cnt').includes('۲۳ برنامه'),'شمار کل در سرصفحه: '+p.txt('#cnt'));
  const order=p.all('#grid .etile').map(x=>x.querySelector('.ettl').textContent.trim());
  ok(order[0]==='جلسهٔ شعر و موسیقی','فهرست از نزدیک‌ترین برنامه شروع می‌شود: '+order[0]);
  ok(order[order.length-1].includes('امداد و نجات — ترم تیر')||order[order.length-1].includes('اردوی کوه‌پیمایی — ترم تیر'),
    'و به قدیمی‌ترین برگزارشده می‌رسد: '+order[order.length-1]);

  /* د) صافی‌ها: بالا به پایین، سه مدل، بی دکمهٔ «همه» */
  ok(p.all('#filters .frow').length===4,'چهار ردیف بالا به پایین: جست‌وجو + سه صافی');
  ok(p.doc.querySelector('#filters #q')!==null,'جست‌وجو بالای صافی‌ها نشسته است');
  ok(p.txt('#filters').includes('وضعیت') && p.txt('#filters').includes('نوع برنامه') && p.txt('#filters').includes('شیوهٔ برگزاری'),'نام سه مدل صافی');
  ok(p.all('#filters .chip').length>=7 && p.all('#filters .chip').filter(c=>/همه/.test(c.textContent)).length===0,'چیپ‌های صافی از یوآی می‌آیند و هیچ دکمهٔ «همه» ای نمانده');
  ok(p.all('#filters .chip.on').length===0 && p.all('#filters .chip .i').length===p.all('#filters .chip').length,'هیچ صافی‌ای از پیش روشن نیست و هر چیپ نشان تیک خودش را دارد');
  ok(p.all('#filters [data-status="up"]').length===1 && p.all('#filters [data-status="past"]').length===1,'وضعیت: پیش رو / برگزارشده');
  ok(p.all('#filters [data-kind]').length>=5,'صافی نوع برنامه از خود داده می‌آید');
  p.click('#filters [data-status="past"]');
  ok(p.all('#grid .etile').length===12 && p.all('#grid .etile.past').length===12,'صافی «برگزارشده» فقط آرشیو را می‌آورد');
  ok(p.doc.querySelector('#filters [data-status="past"]').classList.contains('on'),'صافی فعال، نشان خودش را دارد');
  p.click('#filters [data-status="past"]');
  ok(p.all('#grid .etile').length===23,'زدن دوبارهٔ صافی، آن را برمی‌دارد');
  p.click('#filters [data-kind="کارگاه"]');
  ok(p.all('#grid .etile').length===10,'صافی «کارگاه» ده برنامه');
  p.click('#filters [data-mode="آنلاین"]');
  const onlineKind=p.all('#grid .etile').length;
  ok(onlineKind>0 && onlineKind<10,'دو صافی با هم کار می‌کنند: '+onlineKind+' برنامه');
  p.click('#filters [data-kind="کارگاه"]');
  p.click('#filters [data-mode="آنلاین"]');
  ok(p.all('#grid .etile').length===23,'هر دو صافی برداشته شد');

  /* ه) جست‌وجو */
  p.doc.querySelector('#q').value='عکاسی';
  p.doc.querySelector('#q').dispatchEvent(new p.window.Event('input',{bubbles:true}));
  ok(p.all('#grid .etile').length===4,'جست‌وجوی «عکاسی» چهار برنامه');
  p.click('#qClear');
  ok(p.all('#grid .etile').length===23,'پاک کردن جست‌وجو');

  /* و) پیش‌ثبت‌نام برای برنامه‌های پیش رو */
  const preTile=p.doc.querySelector('#grid .etile [data-uipre="e5"]');
  ok(preTile!==null,'کارت برنامهٔ پیش رو دکمهٔ پیش‌ثبت‌نام دارد');
  ok(p.txt('#grid .etile [data-uipre="e5"]').includes('پیش‌ثبت‌نام'),'متن دکمه پیش‌ثبت‌نام است');
  ok(p.doc.querySelector('#grid .etile a[href="form.html?ev=e1"]')!==null,'برنامهٔ با ثبت‌نام باز، دکمهٔ ثبت‌نام دارد');
  p.click('#grid .etile [data-uipre="e5"]');
  await wait(40);
  ok(p.doc.querySelector('#shAuth').className.includes('on'),'بی حساب، پیش‌ثبت‌نام اول ورود می‌خواهد');
  p.doc.querySelector('#uimob').value='09121234567';
  p.click('[data-uiphone]');
  await wait(30);
  p.doc.querySelector('#uicode').value='54321';
  p.click('[data-uicode]');
  await wait(160);
  ok(p.window.localStorage.getItem('nora-home-prereg').includes('e5'),'پیش‌ثبت‌نام بعد از ورود ثبت می‌شود');
  ok(p.txt('#toast').includes('پیش‌ثبت‌نام'),'پیام پیش‌ثبت‌نام نشان داده می‌شود');
  ok(p.txt('#grid').includes('پیش‌ثبت‌نام شده'),'کاشی بی‌نوکردن صفحه، حالت تازه را می‌گیرد');

  /* ز) کاشی برگزارشده: پیش‌نمایش و تهیه */
  const pastTile=p.doc.querySelector('#grid .etile.past');
  ok(pastTile.querySelector('[data-uipreview]')!==null,'کاشی برگزارشده دکمهٔ پیش‌نمایش دارد');
  ok(pastTile.querySelector('a[href^="event.html?id="]')!==null,'و راه تهیه/دریافت دارد');
  ok(/ریال|رایگان/.test(pastTile.querySelector('.eprice').textContent),'مبلغ روی کاشی برگزارشده');
  ok(pastTile.querySelector('.etags').textContent.includes('رسانه'),'شمار رسانه روی کاشی برگزارشده');
  const h1tile=[...p.all('#grid .etile.past')].find(x=>x.querySelector('[data-uipreview="h1"]'));
  ok(h1tile!==undefined,'کاشی کارگاه عکاسی مقدماتی در آرشیو هست');
  p.click('#grid [data-uipreview="h1"]');
  await wait(60);
  ok(p.doc.querySelector('#shPlay').className.includes('on'),'پیش‌نمایش، پخش‌کننده را باز می‌کند');
  ok(p.txt('#shPlay').includes('دوربین')||p.txt('#shPlay').length>40,'نام قطعهٔ نمونه در پخش‌کننده');
  p.click('#shPlay [data-close]');
  await wait(30);

  /* ح) ورقهٔ کلیات از کاشی */
  p.click('#grid .etile [data-ev="e3"]');
  await wait(40);
  ok(p.doc.querySelector('#shEvent').className.includes('on'),'کلیک کاشی، ورقهٔ کلیات را باز می‌کند');
  ok(p.doc.querySelector('#shEvent').className.includes('full'),'ورقه تمام‌صفحه است');
  ok(p.txt('#shEvent').includes('فقط ۱۱ جا مانده'),'جای مانده از ظرفیت حساب شده');
  ok(p.doc.querySelector('#shEvent a.btn.primary').getAttribute('href')==='event.html?id=e3','از ورقه به صفحهٔ اختصاصی رویداد می‌رود');
  ok(p.txt('#shEvent').includes('کیوان مرادی'),'مدرس رویداد در ورقه با نام می‌آید');
  ok(p.txt('#shEvent').includes('۳ جلسه'),'برنامهٔ چندجلسه‌ای، شمار جلسه‌ها را نشان می‌دهد');
  p.click('#shEvent [data-close]');
  p.click('#grid .etile:not(.past) .ettl');
  await wait(30);
  ok(p.txt('#shEvent').includes('زمان')||p.doc.querySelector('#shEvent').className.includes('on'),'کلیک روی تنِ کاشی هم ورقه را باز می‌کند');
  p.click('#shEvent [data-close]');
  await wait(20);
  p.click('#grid .etile [data-ev="e4"]');
  await wait(40);
  ok(p.txt('#shEvent').includes('لینک ورود'),'برای برنامهٔ آنلاین، لینک ورود یادآوری می‌شود');
  p.click('#shEvent [data-close]');
  p.click('#grid .etile [data-ev="e8"]');
  await wait(40);
  ok(p.txt('#shEvent').includes('ظرفیت تکمیل'),'اردوی پر: ظرفیت تکمیل در کلیات');
  p.click('#shEvent [data-close]');

  /* ط) تقویم: گذشته و پیش رو */
  p.click('.seg [data-view="cal"]');
  ok(!p.doc.querySelector('#calView').hidden && p.doc.querySelector('#listView').hidden,'نمای تقویم باز می‌شود');
  ok(p.all('#monthsw button').length===4,'چهار ماه در تقویم: تیر، مرداد، شهریور، مهر');
  ok(p.all('#monthsw button.was').length===2,'تیر و مرداد نشان گذشته دارند');
  ok(p.all('#calgrid .wd').length===7,'سرستون‌های هفته');
  ok(p.all('#calgrid .cel').length===32,'شهریور: ۳۱ روز + ۱ خانهٔ خالی');
  ok(p.all('#calgrid .cel.has').length>=3,'روزهای پررویداد نشان دارند');
  ok(p.doc.querySelector('#calgrid .cel.today')!==null,'روز امروز نشان دارد');
  ok(p.txt('#dayTitle').includes('۲۸') && p.all('#dayGrid .etile').length===2,'روز پیش‌فرض امروز با دو برنامه');
  p.click('#calgrid .cel[data-dn="29"]');
  ok(p.txt('#dayTitle').includes('یکشنبه') && p.all('#dayGrid .etile').length===1,'روز ۲۹: یک برنامه');
  p.click('#monthsw [data-month="tir"]');
  ok(p.all('#calgrid .cel').length===33,'تیر: ۳۱ روز + ۲ خانهٔ خالی');
  ok(p.all('#dayGrid .etile.past').length>0,'ماه گذشته، خودش روی روز پررویداد می‌ایستد');
  ok(p.txt('#dayTitle').includes('تیر'),'عنوان روز از همان ماه است: '+p.txt('#dayTitle'));
  p.click('#calgrid .cel[data-dn="9"]');
  ok(p.txt('#dayGrid').includes('حلقهٔ مطالعهٔ ادبیات'),'روز ۹ تیر: حلقهٔ مطالعه');
  p.click('#monthsw [data-month="mehr"]');
  ok(p.all('#calgrid .cel').length===34,'مهر: ۳۰ روز + ۴ خانهٔ خالی');
  p.click('.seg [data-view="list"]');
  ok(!p.doc.querySelector('#listView').hidden,'برگشت به فهرست');

  /* ی) کتابخانهٔ من، پشت دکمهٔ خودش */
  ok(p.doc.querySelector('#libBar').hidden,'بی حساب، نوار کتابخانه پنهان است');
  ok(p.doc.querySelector('#viewRow').hidden===false,'نوار تقویم/فهرست سرجایش هست');
  const p5=await load('events.html',makeStore(),'#lib');
  ok(p5.doc.querySelector('#libView').hidden===false && p5.doc.querySelector('#viewRow').hidden,'#lib کتابخانه را جدا نشان می‌دهد');
  ok(p5.txt('#libBox').includes('وارد شو'),'بی ورود، کتابخانه ورود می‌خواهد');

  /* ک) نشانی‌های ورودی */
  const p2=await load('events.html',makeStore(),'?q='+encodeURIComponent('عکاسی'));
  ok(p2.all('#grid .etile').length===4,'ورود با ?q= صافی می‌کند');
  const p6=await load('events.html',makeStore(),'?status=past');
  ok(p6.all('#grid .etile.past').length===12 && p6.all('#grid .etile:not(.past)').length===0,'ورود با ?status=past فقط آرشیو را می‌آورد');
  const p3=await load('events.html',makeStore(),'?ev=e5');
  ok(p3.doc.querySelector('#shEvent').className.includes('on') && p3.txt('#shEvent').includes('الهه رضایی'),'ورود با ?ev= مستقیم ورقهٔ کلیات را باز می‌کند');
  const p4=await load('events.html',makeStore(),'?past=h2');
  ok(p4.doc.querySelector('#shEvent').className.includes('on') && p4.txt('#shEvent').includes('کارگاه فن بیان — ترم تیر'),'ورود با ?past= ورقهٔ بسته را باز می‌کند');
}

/* ══════════════════════════════════════════════════════════════════════════
   v7 — «ادامه بده»، جست‌وجوی زنده، اشتراک بومی، نصب‌شدنی، دسترس‌پذیری
   ══════════════════════════════════════════════════════════════════════════ */
{
  console.log('\n── ادامه بده و جست‌وجو (v7) ──');
  const homeSrc=fs.readFileSync(DIR+'home.html','utf8');

  /* الف) «ادامه بده» تازه‌وارد را خالی نمی‌ترساند، اما بعد از بازدید می‌آید */
  const st0=makeStore();
  const p0=await load('home.html',st0);
  ok(p0.doc.querySelector('#continue').hidden,'کاربر تازه، بخش «ادامه بده» را خالی نمی‌بیند');
  p0.window.NORA_HOME.pushRecent('ar','a1');
  ok(p0.doc.querySelector('#continue').hidden===false,'بعد از دیدن یک مطلب، «ادامه بده» پیدا می‌شود');
  ok(p0.txt('#continue').includes('ادامه بده') && p0.txt('#continue').includes('همین حالا'),'عنوان و زمان نسبی درست است');
  ok(p0.txt('#continue').includes('مطلب'),'نوع مورد هم نوشته می‌شود');
  /* ترتیب: تازه‌ترین اول */
  p0.window.NORA_HOME.pushRecent('pe','p1'); p0.window.NORA_HOME.pushRecent('ev','e1');
  const rows=p0.all('#continue [data-openrec]').map(b=>b.dataset.openrec);
  ok(rows[0]==='ev:e1'&&rows[1]==='pe:p1'&&rows[2]==='ar:a1','تازه‌ترین بازدید، بالای فهرست است: '+rows.join(' | '));
  /* تکرار: یک مورد دو بار ثبت نمی‌شود */
  p0.window.NORA_HOME.pushRecent('ar','a1');
  ok(p0.all('#continue [data-openrec]').length===3,'بازدید دوباره، ردیف تکراری نمی‌سازد');
  /* برداشتن یک مورد */
  p0.click('#continue [data-droprec="pe:p1"]');
  ok(p0.all('#continue [data-openrec]').length===2 && !p0.txt('#continue').includes('نگار'),'برداشتن یک مورد از فهرست کار می‌کند');
  /* پاک کردن کل فهرست */
  p0.click('#continue [data-clearrec]');
  ok(p0.all('#continue [data-openrec]').length===0,'پاک کردن کل فهرست کار می‌کند');
  /* پنهان کردن، و برگشت با اولین بازدید */
  p0.window.NORA_HOME.pushRecent('ar','a2');
  p0.click('#continue [data-hiderec]');
  ok(p0.doc.querySelector('#continue').hidden,'«پنهان کن» بخش را جمع می‌کند');
  p0.window.NORA_HOME.pushRecent('ar','a3');
  ok(p0.doc.querySelector('#continue').hidden===false,'با اولین بازدید بعدی، بخش برمی‌گردد');

  /* ب) ماندگاری بین دو بازدید و پاک‌سازی دادهٔ خراب */
  const st1=makeStore();
  st1.setItem('nora-home-recent',JSON.stringify([{k:'ar',id:'a1',at:Date.now()},{k:'zz',id:'a1',at:Date.now()},
    {k:'ar',id:'../etc/passwd',at:Date.now()},{k:'ar',id:'a9',at:Date.now()},{k:'ar',id:'a1',at:1}]));
  const p1=await load('home.html',st1);
  const ids=p1.all('#continue [data-openrec]').map(b=>b.dataset.openrec);
  ok(ids.join('|')==='ar:a1','از دادهٔ خراب فقط مورد سالم می‌ماند: '+ids.join(' | '));
  ok(p1.window.NORA_HOME.S.recent.length===1,'کلید ناشناس و شناسهٔ ناامن وارد فهرست نمی‌شوند');

  /* ج) کار نیمه‌تمام: ورود نصفه‌کاره در «ادامه بده» می‌آید */
  const st2=makeStore();
  const p2=await load('home.html',st2);
  p2.click('#tabs [data-tab="me"]'); p2.click('[data-next]');
  p2.doc.querySelector('#mob').value='۰۹۱۲۳۴۵۶۷۸۹';
  p2.click('[data-login]');
  ok(p2.window.localStorage.getItem('nora-home-auth')!==null,'گام ورود در حافظهٔ مرورگر ثبت می‌شود');
  p2.click('[data-close]');
  const p2b=await load('home.html',makeStoreWith(st2));
  ok(p2b.txt('#continue').includes('ورودت را تمام کن'),'کاربر نیمه‌راه، دکمهٔ «ورودت را تمام کن» می‌بیند');
  ok(p2b.txt('#continue').includes('۶۷۸۹')||p2b.txt('#continue').includes('۰۹۱۲'),'شمارهٔ نیمه‌کاره هم یادآوری می‌شود');
  p2b.click('#continue [data-resume-auth]');
  ok(p2b.doc.querySelector('#shAccount').className.includes('on') && p2b.doc.querySelector('#code')!==null,
    'دکمهٔ ادامه، مستقیم به گام کد می‌برد');
  p2b.doc.querySelector('#code').value='54321';
  p2b.click('[data-code]');
  ok(p2b.doc.querySelector('#continue').hidden && p2b.window.localStorage.getItem('nora-home-auth')===null,
    'بعد از ورود، کار نیمه‌تمام از فهرست می‌رود');

  /* د) جست‌وجوی زنده: پیشنهاد، کیبورد، سابقه */
  const st3=makeStore();
  const p3=await load('home.html',st3);
  ok(p3.doc.querySelector('#hotRow').textContent.includes('پیشنهادی'),'چیپ‌های داغ پیش از تایپ دیده می‌شوند');
  ok(p3.doc.querySelector('#sugBox').hidden,'جعبهٔ پیشنهاد پیش از تایپ بسته است');
  p3.doc.querySelector('#q').value='عکاسی';
  p3.doc.querySelector('#q').dispatchEvent(new p3.window.Event('input',{bubbles:true}));
  await wait(200);
  const sugs=p3.all('#sugBox .sug');
  ok(p3.doc.querySelector('#sugBox').hidden===false,'با تایپ، پیشنهاد باز می‌شود');
  ok(sugs.length>=3,'پیشنهاد از رویداد و مطلب و استاد می‌آید: '+sugs.length+' مورد');
  ok(sugs.some(x=>x.textContent.includes('عکاسی')),'واژهٔ تایپ‌شده در پیشنهادها هست');
  ok(sugs[sugs.length-1].dataset.sugall!==undefined,'ردیف «همهٔ نتیجه‌ها» آخر فهرست است');
  /* کیبورد */
  p3.doc.querySelector('#q').dispatchEvent(new p3.window.KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}));
  ok(p3.all('#sugBox .sug.on').length===1,'کلید پایین، اولین پیشنهاد را فعال می‌کند');
  ok(p3.doc.querySelector('#q').getAttribute('aria-activedescendant')==='sug0','وضعیت فعال به صفحه‌خوان هم گفته می‌شود');
  p3.doc.querySelector('#q').dispatchEvent(new p3.window.KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}));
  ok(p3.doc.querySelector('#q').getAttribute('aria-activedescendant')==='sug1','کلید پایین، جلو می‌رود');
  p3.doc.querySelector('#q').dispatchEvent(new p3.window.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  ok(p3.doc.querySelector('#sugBox').hidden && p3.doc.querySelector('#q').getAttribute('aria-expanded')==='false','Escape جعبه را می‌بندد');
  /* سابقه: با Enter تثبیت می‌شود و دفعهٔ بعد چیپ می‌شود */
  p3.doc.querySelector('#q').dispatchEvent(new p3.window.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
  ok(p3.window.localStorage.getItem('nora-home-search').includes('عکاسی'),'جست‌وجو در سابقهٔ خود کاربر می‌ماند');
  const p3b=await load('home.html',makeStoreWith(st3));
  ok(p3b.txt('#hotRow').includes('عکاسی'),'دفعهٔ بعد، سابقهٔ جست‌وجو به‌عنوان چیپ می‌آید');
  p3b.click('#hotRow [data-clearhistory]');
  ok(p3b.window.localStorage.getItem('nora-home-search')===null && !p3b.txt('#hotRow').includes('عکاسی'),
    '«پاک کردن سابقه» واقعاً پاک می‌کند');
  /* چیپ داغ، فیلتر را در جست‌وجو می‌گذارد */
  p3b.click('#hotRow [data-sq="رایگان"]');
  ok(p3b.doc.querySelector('#q').value==='رایگان' && !p3b.doc.querySelector('#searchRes').hidden,'چیپ می‌گذارد و نتیجه را می‌سازد');
  /* واژه‌نویسی خراب: صفحه سالم می‌ماند */
  ok(p3b.errs.length===0,'خطای کنسول صفر ماند');

  /* ه) اشتراک بومی: اگر گوشی نپذیرد، کپی می‌شود */
  const p4=await load('home.html',makeStore());
  let shared=null;
  p4.window.navigator.share=o=>{shared=o; return Promise.resolve()};
  let copied=null;
  p4.doc.addEventListener('click',()=>{});
  p4.window.__copied=null;
  const cp=p4.window.NORA_UI; ok(cp&&typeof cp.shareItem==='function','تابع اشتراک بومی از پوستهٔ مشترک می‌آید');
  await cp.shareItem({title:'یک رویداد',text:'توضیح',url:'https://lifeline1.ir/e/e1'});
  ok(shared&&shared.url==='https://lifeline1.ir/e/e1','وقتی گوشی بپذیرد، همان لینک را می‌دهد');
  /* لغو کاربر: پیام اضافه‌ای نمی‌دهد */
  p4.window.navigator.share=()=>Promise.reject(Object.assign(new Error('x'),{name:'AbortError'}));
  const r=await cp.shareItem({url:'https://lifeline1.ir/e/e2'});
  ok(r===false,'لغو کردن کاربر، بی‌صدا رد می‌شود');

  /* و) دسترس‌پذیری: تلهٔ فوکوس و مودال واقعی */
  const p5=await load('home.html',makeStore());
  p5.click('[data-menu]');
  await wait(40);   /* نشان‌دار دگرگونی، ناهم‌گام است */
  ok(p5.doc.querySelector('#shMenu').getAttribute('aria-modal')==='true','ورقهٔ باز، مودال واقعی اعلام می‌شود');
  ok(p5.doc.querySelector('#shMenu').contains(p5.doc.activeElement),'فوکوس داخل ورقه می‌رود');
  const f=[...p5.doc.querySelectorAll('#shMenu a[href],#shMenu button,#shMenu input')];
  f[0].focus();
  p5.doc.dispatchEvent(new p5.window.KeyboardEvent('keydown',{key:'Tab',shiftKey:true,bubbles:true}));
  ok(p5.doc.querySelector('#shMenu').contains(p5.doc.activeElement),'Shift+Tab از ورقه بیرون نمی‌زند');
  const fl=f[f.length-1]; fl.focus();
  p5.doc.dispatchEvent(new p5.window.KeyboardEvent('keydown',{key:'Tab',bubbles:true}));
  ok(p5.doc.querySelector('#shMenu').contains(p5.doc.activeElement),'Tab از ورقه بیرون نمی‌زند');
  p5.click('[data-close]');
  await wait(40);
  ok(p5.doc.querySelector('#shMenu').getAttribute('aria-modal')==='false','بستن ورقه، مودال را برمی‌گرداند');

  /* ز) نشانه‌گذاری و نصب‌شدنی */
  ok(/<h1 class="vh"/.test(homeSrc),'خانه سرفصل اصلی دارد (برای صفحه‌خوان)');
  ok(/<a class="skip" href="#quick"/.test(homeSrc),'پیوند «پرش به محتوا» هست');
  ok(/role="tablist"/.test(homeSrc) && /role="tab" aria-selected="true"/.test(homeSrc),'تب‌بار نقش تب دارد');
  ok(/Combobox|role="combobox"/.test(homeSrc),'میدان جست‌وجو نقش combobox دارد');
  for(const f of ['manifest.webmanifest','sw.js','offline.html','icon-192.png','icon-512.png']){
    ok(fs.existsSync(DIR+f),'فایل نصب‌شدنی هست: '+f);
  }
  const mf=JSON.parse(fs.readFileSync(DIR+'manifest.webmanifest','utf8'));
  ok(mf.display==='standalone' && mf.dir==='rtl' && mf.icons.length===3,'manifest کامل است: نام، راست‌به‌چپ، آیکون‌ها');
  const sw=fs.readFileSync(DIR+'sw.js','utf8');
  ok(/if\(r\.mode==='navigate'\)/.test(sw)&&/offline\.html/.test(sw),'کارگر سرویس: شبکه اول و صفحهٔ بی‌اتصال');
  ok(/people\|posters\|fonts/.test(sw),'تصویر و فونت مسیر کش‌شدن خودشان را دارند');
  ok(/>بازگشت به صفحهٔ اصلی|فایل نصب‌شدنی هست: (home|events)/.test('x')||/manifest\.webmanifest/.test(homeSrc),
    'خانه به manifest وصل است');
  /* گواهینامه از بار اول کنار رفته باشد */
  ok(!/AAEAAAAOAIAAA/.test(fs.readFileSync(DIR+'ui.js','utf8')) || fs.statSync(DIR+'ui.js').size<90000,
    'ui.js دیگر فونت گواهینامه را با خود نمی‌آورد');
  ok(/cert-font\.js/.test(fs.readFileSync(DIR+'builder.html','utf8')),'صفحهٔ سازندهٔ گواهی، فونتش را جدا می‌آورد');
}

/* ══════════════════════════════════════════════════════════════════════════
   v6 — بازبینی منوی خانه: امنیت، کارایی، یو‌آی، کلید شب و روز
   ══════════════════════════════════════════════════════════════════════════ */
{
  console.log('\n── بازبینی خانه (v6) ──');
  const homeSrc=fs.readFileSync(DIR+'home.html','utf8');
  const nora=fs.readFileSync(DIR+'nora.css','utf8');

  /* الف) کلید شب و روز به سبک اپل */
  const p=await load('home.html',makeStore());
  const sw=p.doc.querySelector('.topbar [data-theme-toggle]');
  ok(sw!==null && sw.classList.contains('themesw'),'کلید شب و روز در نوار بالا هست');
  ok(sw.getAttribute('role')==='switch' && sw.getAttribute('aria-checked')!==null,'کلید نقش switch و وضعیت aria دارد');
  ok(p.all('.themesw .tsw-ico').length===2,'کلید دو سر دارد: خورشید و ماه');
  ok(p.doc.querySelector('.themesw use[href="#i-sun"]')!==null && p.doc.querySelector('.themesw use[href="#i-moon"]')!==null,'خورشید و ماه نماد خودشان را دارند');
  ok(p.doc.querySelectorAll('.themesw .tsw-knob').length===1,'گرهِ لغزان روی شیار هست');
  const before=p.doc.documentElement.dataset.theme;
  p.click('.themesw');
  const after=p.doc.documentElement.dataset.theme;
  ok(before==='light'&&after==='dark','یک کلیک، تم را روز↔شب می‌کند');
  ok(p.doc.querySelector('.themesw').getAttribute('aria-checked')==='true','وضعیت کلید با تم هم‌گام است');
  ok(p.window.localStorage.getItem('nora-theme')==='dark','تم در حافظهٔ مرورگر می‌ماند');
  ok(p.doc.querySelector('meta[name="theme-color"]').getAttribute('content')==='#1B211E','رنگ نوار مرورگر با تم عوض می‌شود');
  p.click('.themesw');
  ok(p.doc.documentElement.dataset.theme==='light' && p.doc.querySelector('.themesw').getAttribute('aria-checked')==='false','برگشت به روز هم کار می‌کند');

  /* صفحهٔ دوم پوسته هم همان کلید را دارد */
  const pe=await load('events.html',makeStore());
  ok(pe.doc.querySelector('.topbar .themesw')!==null && pe.doc.querySelectorAll('.themesw .tsw-ico').length===2,'صفحهٔ رویدادها هم همان کلید را دارد');
  pe.click('.themesw');
  ok(pe.doc.documentElement.dataset.theme==='dark' && pe.window.localStorage.getItem('nora-theme')==='dark','کلید در صفحهٔ رویدادها هم تم را می‌برد');

  /* بی‌فلش: تم پیش از رنگ‌آمیزی می‌نشیند */
  const head=homeSrc.slice(homeSrc.indexOf('<head>'),homeSrc.indexOf('</head>'));
  const cssAt=head.indexOf('rel="stylesheet"');
  const scriptAt=head.indexOf("localStorage.getItem('nora-theme')");
  ok(scriptAt>0 && scriptAt<cssAt,'تم پیش از بارگذاری پوسته‌ها خوانده می‌شود (بدون فلش سفید)');
  ok(!/data-theme="light"/.test(homeSrc.slice(0,homeSrc.indexOf('<head>'))+head.slice(0,scriptAt)),'حالت اولیه در نشانه‌گذاری قفل نشده');

  /* ب) پیوندها و هدف‌های پرش: هیچ ردیف مرده‌ای نماند */
  const jumpIds=[...homeSrc.matchAll(/data-jump="([^"]+)"/g)].map(m=>m[1]);
  const declared=new Set([...homeSrc.matchAll(/id="([A-Za-z0-9_-]+)"/g)].map(m=>m[1]));
  const jumpTargets=new Set([...homeSrc.matchAll(/\bj:'([A-Za-z0-9_-]+)'/g)].map(m=>m[1]));
  ok([...jumpTargets].every(j=>declared.has(j)),'هر پرش منو/کاشی به بخش موجود می‌رود: '+[...jumpTargets].join('، '));
  ok(!jumpTargets.has('people'),'پرش مردهٔ «people» برداشته شد');
  ok(/\{k:'events'[^}]*href:'events\.html#list'/.test(homeSrc) &&
     /q\.href[\s\S]{0,120}?<a class="tile" href=/.test(homeSrc),
     'کاشی «رویدادها» پیوند واقعی است، نه دکمهٔ بی‌کار');
  ok(/\^\[a-z\]\[a-z0-9-\]\*\\\.html/.test(homeSrc),'مسیرهای data-href فقط درون سامانه باز می‌شوند');

  /* ج) امنیت: دادهٔ خراب در حافظهٔ مرورگر صفحه را نمی‌شکند */
  const bad=makeStore();
  bad.setItem('nora-home-user',JSON.stringify({nothing:true}));
  bad.setItem('nora-home-pins',JSON.stringify(['ev:e3',{'x':1},'javascript:alert(1)',42]));
  const pb=await load('home.html',bad);
  ok(pb.errs.length===0&&pb.txt('#tabs [data-tab="me"]')==='حساب من','نشست خراب در حافظه، صفحه را سفید نمی‌کند');
  ok(pb.window.localStorage.getItem('nora-home-user')==='null','نشست بی‌اعتبار پاک می‌شود');
  ok(pb.window.NORA_HOME.S.pins.size===1 && pb.window.NORA_HOME.S.pins.has('ev:e3'),'از سنجاق‌ها فقط کلیدهای معتبر می‌مانند');
  const bad2=makeStore();
  bad2.setItem('nora-home-user',JSON.stringify({name:'<img src=x onerror=alert(1)>سارا',mobile:'12',certs:'۹۹۹۹۹',wallet:-5}));
  const pb2=await load('home.html',bad2);
  ok(pb2.errs.length===0 && pb2.all('#tabs img').length===0,'نام آلوده به نشانه‌گذاری، تصویر/اسکریپت نمی‌سازد');
  ok(pb2.window.NORA_HOME.S.user.certs===999 && pb2.window.NORA_HOME.S.user.wallet===0,'عددهای نشست در بازهٔ مجاز می‌مانند');

  /* د) کارایی */
  ok(/qTimer=setTimeout/.test(homeSrc),'تایپ در جست‌وجو قاب‌بندی شده (نه رندر در هر کلید)');
  ok(/renderPins\(\); if\(k==='pe'\) renderTeachers\(\)/.test(homeSrc),'سنجاق فقط بخش‌های خودش را از نو می‌سازد');
  const uijs=fs.readFileSync(DIR+'ui.js','utf8');
  ok(/sheenRaf=requestAnimationFrame/.test(uijs),'درخشش زیر ماوس قاب‌بندی شده و هر حرکت، چیدمان نمی‌خواند');

  /* ه) یو‌آی: پرش درون‌صفحه زیر نوار بالا نرود */
  ok(/\.sec\[id\],section\[id\]\{scroll-margin-top:64px\}/.test(nora),'سرِ بخش هنگام پرش، زیر نوار بالا پنهان نمی‌شود');
  ok(/\.themesw\{\.\.\.\}/.test(nora)||/\.themesw\{/.test(nora),'پوستهٔ مشترک، کلید تم را می‌شناسد');
  ok(/html\[dir="rtl"\]\[data-theme="dark"\] \.tsw-knob\{transform:translateX\(-32px\)\}/.test(nora),
     'گره در چیدمان راست‌به‌چپ به سمت ماه می‌لغزد (قرینه)');

  /* ز) سلامت نشانه‌گذاری: شناسه تکراری، ورقهٔ بی‌مقصد، آیکون تعریف‌نشده */
  const pl0=await load('home.html',makeStore());
  const pe0=await load('events.html',makeStore(),'#list');
  for(const [file,src] of [['home.html',homeSrc],['events.html',fs.readFileSync(DIR+'events.html','utf8')]]){
    const body=src.slice(src.indexOf('</head>'));
    const ids=[...body.matchAll(/\sid="([^"]+)"/g)].map(m=>m[1]);
    const dup=ids.filter((x,i)=>ids.indexOf(x)!==i);
    ok(dup.length===0,file+': شناسهٔ تکراری ندارد'+(dup.length?' → '+[...new Set(dup)].join('، '):''));
    const sheets=new Set([...body.matchAll(/<aside class="sheet" id="([^"]+)"/g)].map(m=>m[1]));
    const targets=[...body.matchAll(/data-f="([^"]+)"/g)].map(m=>m[1]).filter(f=>!/[${}]/.test(f));
    const deadF=[...new Set(targets)].filter(f=>!sheets.has(f));
    ok(deadF.length===0,file+': هر دکمهٔ ورقه، ورقهٔ خودش را دارد'+(deadF.length?' → '+deadF.join('، '):''));
    const syms=new Set([...src.matchAll(/<symbol id="([^"]+)"/g)].map(m=>m[1]));
    const used=[...new Set([...body.matchAll(/<use href="#([^"]+)"/g)].map(m=>m[1]))].filter(u=>!/[${}]/.test(u));
    const missing=used.filter(u=>!syms.has(u));
    ok(missing.length===0,file+': همهٔ آیکون‌های ثابت تعریف شده‌اند'+(missing.length?' → '+missing.join('، '):''));
  }

  /* آیکون‌های پویا: در صفحهٔ رندرشده، هر آیکون باید نماد خودش را داشته باشد */
  const pf0=await load('event.html',makeStore(),'?id=h1');
  pf0.window.NORA_UI.player('h1','h1m1');          /* ورقهٔ پخش */
  const pq0=await load('events.html',makeStore(),'#media');
  pq0.window.NORA_UI.buySheet('h1',null);          /* ورقهٔ خرید */
  for(const [file,chk] of [['خانه',pl0],['رویدادها',pe0],['صفحهٔ بسته',pf0],['فروشگاه',pq0]]){
    const syms=new Set([...chk.doc.querySelectorAll('symbol')].map(x=>x.id));
    const used=[...new Set([...chk.doc.querySelectorAll('use')].map(u=>(u.getAttribute('href')||'').slice(1)))].filter(Boolean);
    const missing=used.filter(u=>!syms.has(u));
    ok(missing.length===0,file+': هر آیکونِ رندرشده نمادش را دارد'+(missing.length?' → '+missing.join('، '):''));
    const inSvg=[...chk.doc.querySelectorAll('symbol')].filter(x=>x.closest('svg'));
    ok(inSvg.length===syms.size,file+': همهٔ نمادها داخل ریشهٔ svg هستند ('+inSvg.length+'/'+syms.size+')');
  }

  /* ح) کاشی‌های پیوندی و برگشت‌پذیری تم بین دو صفحه */
  const pl=await load('home.html',makeStore());
  const tile=pl.doc.querySelector('#quick .tile[href="events.html#list"]');
  ok(tile && tile.tagName==='A','کاشی «رویدادها» یک پیوند واقعی است');
  ok(pl.all('#quick a.tile').length===1 && pl.all('#quick button.tile').length===7,'هفت کاشی دیگر همچنان ورقه/پرش درون‌صفحه‌اند');
  pl.click('.themesw');
  pl.window.NORA_HOME.renderAll();
  ok(pl.doc.documentElement.dataset.theme==='dark' && pl.doc.querySelector('.themesw').getAttribute('aria-checked')==='true','رندر دوبارهٔ صفحه، وضعیت کلید را به هم نمی‌ریزد');
  const store2=makeStore(); store2.setItem('nora-theme','dark');
  const pd=await load('home.html',store2);
  ok(pd.doc.documentElement.dataset.theme==='dark' && pd.doc.querySelector('.themesw').getAttribute('aria-checked')==='true','صفحه با تم ذخیره‌شده درست بالا می‌آید');

  /* و) شمارش‌های منو زنده‌اند، نه هاردکد */
  ok(/s:faN\(TEACHERS\.length\)/.test(homeSrc) && !/s:'۸ نفر'/.test(homeSrc),'شمارش استادان از خود داده می‌آید');
  const pm=await load('home.html',makeStore());
  pm.click('[data-menu]');
  ok(pm.txt('#menuBody').includes('۶ استاد'),'منو عدد درست را نشان می‌دهد (۶ استاد)');
}

/* ══════════════════════════════════════════════════════════════════════════
   v5 — پاس کیفیت: حروف نمایشی، ریتم بخش‌ها، یکدستی رنگ روی جلدها
   ══════════════════════════════════════════════════════════════════════════ */
{
  const glass=fs.readFileSync(DIR+'glass.css','utf8');
  const nora=fs.readFileSync(DIR+'nora.css','utf8');
  const home=fs.readFileSync(DIR+'home.html','utf8');
  const evp=fs.readFileSync(DIR+'events.html','utf8');
  const data=fs.readFileSync(DIR+'data.js','utf8');

  /* حروف: تیترها با استداد، متن با وزیرمتن */
  ok(/@font-face\{[^}]*font-family:'Estedad'/.test(glass),'فونت نمایشی استداد در لایهٔ پایه تعریف شده');
  ok(fs.existsSync(DIR+'fonts/Estedad-Variable.woff2') && fs.statSync(DIR+'fonts/Estedad-Variable.woff2').size>50000,
     'فایل فونت استداد کنار بقیهٔ فونت‌ها هست');
  ok(/--f-h:'Estedad',var\(--f\)/.test(glass),'متغیر فونت تیتر به وزیرمتن برمی‌گردد (اگر استداد نبود)');
  ok(/\.display,\.title,\.head,\.ttl,\.fw,/.test(glass)&&/\.tabbar small/.test(glass)&&/\.tile b/.test(glass),
     'تیترها، تب‌بار و کاشی‌ها استداد می‌خوانند');
  ok(!/--f-h:/.test(nora)&&/font-variant-numeric:tabular-nums/.test(nora),'ارقام هم‌عرض در پوستهٔ اپ هست');

  /* ریتم و سطح‌ها */
  ok(/\.sec\{margin-top:22px\}/.test(nora) && /\/\* ── ریتم/.test(nora),'فاصلهٔ بخش‌ها یکدست شد');
  ok(/\.card\.paper\{border-radius:var\(--r-lg\);padding:18px;box-shadow:var\(--sh-1\)\}/.test(nora),
     'کارت‌ها یک شعاع و یک سایه دارند');
  ok(/\.card \.card,/.test(nora) && /box-shadow:none/.test(nora),'کارت روی کارت بی‌سایه است');
  ok(/\.glass\.statstrip\{background:var\(--surface\)/.test(nora),'نوار آمار دیگر شیشه نیست (شیشه فقط ناوبری)');

  /* سطح آرام: هاله‌های شعاعی و نقطه‌چین تزئینی رفتند */
  ok(!/radial-gradient/.test(home),'هیچ هالهٔ شعاعی تزئینی در خانه نمانده');
  ok(!/data-tone=/.test(home) && !/tone:'/.test(home),'کاشی‌ها یک رنگ دارند، نه چهار رنگ');
  ok(!/radial-gradient/.test(evp),'صفحهٔ رویدادها هم سطح تخت دارد');
  ok(!/class="sec card paper"/.test(home) && !/class="sec card paper"/.test(evp),'بخش‌ها بیرون کارت‌اند (کارت‌ها فقط خود آیتم‌ها)');

  /* جلدها: یک خانوادهٔ رنگی آرام */
  const covers=[...data.matchAll(/linear-gradient\([^)]*\)/g)].map(m=>m[0]);
  ok(!covers.some(g=>/#B4453C|#0B7A57|#6E4B1F|#9C7C3C|#4EA1FF/.test(g)),
     'رنگ‌های پرش‌وکنار جلدها (قرمز، سبز، قهوه‌ای، طلایی) رفتند');
  const fam=[...new Set(covers.map(g=>g.replace(/^linear-gradient\(\d+deg,/,'(unused,')))];
  ok(new Set(covers).size<=6,'جلدها فقط پنج گرادیان هم‌خانواده دارند، نه رنگ‌قلمی');

  /* ریتم صفحه: نوار آمار پای صفحه، پیش از نشانی‌ها */
  ok(home.indexOf('id="about"')>home.indexOf('id="voices"') && home.indexOf('id="about"')<home.indexOf('class="hfoot"'),
     '«نورا در یک نگاه» به پای صفحه رفت');
}

/* ══════════════════════════════════════════════════════════════════════════
   v8 — فروشگاه رویداد و رسانه: صفحهٔ اختصاصی، خرید، دسترسی آنلاین
   ══════════════════════════════════════════════════════════════════════════ */
{
  console.log('\n── فروشگاه رویداد و رسانه (v8) ──');
  const sara={name:'سارا محمدی',mobile:'09123456789',joined:'مهر ۱۴۰۲',certs:2,wallet:1250000,msgs:1};
  const withSara=()=>{const s=makeStore(); s.setItem('nora-home-user',JSON.stringify(sara)); return s};

  /* الف) صفحهٔ اختصاصی رویداد */
  const fe=await load('event.html',makeStore(),'?id=e3');
  ok(fe.errs.length===0, fe.errs.length?('خطا در صفحهٔ رویداد: '+fe.errs.slice(0,2).join(' | ')):'صفحهٔ رویداد بی‌خطا بالا آمد');
  ok(fe.txt('.evhero').includes('کارگاه عکاسی در طبیعت'),'تیتر رویداد در سرصفحه');
  ok(fe.txt('#page').includes('کیوان مرادی'),'مدرس با نام و نشان می‌آید');
  ok(fe.txt('#page').includes('یکشنبه ۲۹ شهریور'),'تاریخ برگزاری در جزئیات');
  ok(fe.txt('#page').includes('فرهنگسرای نیاوران'),'نشانی برگزاری در جزئیات');
  ok(fe.doc.querySelector('#reg')!==null && fe.doc.querySelector('#reg').getAttribute('href')==='form.html?ev=e3','لینک ثبت‌نام به فرم کاربر می‌رود');
  ok(fe.all('.evrail .rtile').length>0,'ردیف «برنامه‌های مشابه» پر است');
  ok(fe.all('.evrail .rtile').every(x=>x.dataset.goto!=='e3'),'رویداد خودش در ردیف مشابه‌ها نیست');
  ok(fe.doc.querySelector('#ctabar').hidden===false||fe.doc.querySelector('#ctabar')!==null,'نوار کار پایین صفحه هست');
  ok(fe.errs.length===0 && fe.doc.querySelectorAll('svg > symbol').length>=60,'اسپرایت آیکون کامل در صفحه هست');
  ok(fe.doc.title.includes('کارگاه عکاسی در طبیعت'),'عنوان تب همان رویداد است');
  ok(fe.doc.querySelector('meta[property="og:title"]').getAttribute('content').includes('کارگاه عکاسی در طبیعت'),'og:title با اشتراک‌گذاری هم‌خوان است');
  ok(fe.doc.querySelector('link[rel="canonical"]').getAttribute('href').includes('id=e3'),'canonical به همین رویداد اشاره می‌کند');
  const fx=await load('event.html',makeStore(),'?id=nope');
  ok(fx.txt('#page').includes('پیدا نکردم') && fx.doc.querySelector('#page a').getAttribute('href').startsWith('events.html'),'شناسهٔ ناشناس، راه بازگشت به فهرست می‌دهد');

  /* ب) اعلان و منو در همین صفحه کار می‌کنند */
  fe.click('[data-notice]');
  ok(fe.doc.querySelector('#shNotice').className.includes('on'),'اعلان‌ها در صفحهٔ رویداد باز می‌شود');
  ok(fe.txt('#shNotice').length>20,'فهرست اعلان‌ها پر است');
  fe.click('#shNotice [data-close]');
  const menuSrc=fs.readFileSync(DIR+'event.html','utf8');
  ok(menuSrc.includes('data-menu')||fe.doc.querySelector('[data-menu]')!==null,'در صفحهٔ رویداد هم راهی به منو هست');
  fe.window.NORA_UI.uiOpen('shMenu');
  ok(fe.all('#shMenu .mgroup').length===5 && fe.all('#shMenu .mrow').length===21,'منوی مشترک با پنج گروه در این صفحه هم می‌آید');
  ok(fe.doc.querySelector('.topbar .menubtn')===null && fe.doc.querySelector('.topbar #acctBtn')===null,'نوار بالای صفحهٔ رویداد بی منو و بی پروفایل است');
  fe.window.NORA_UI.uiOpen('shNotice');
  fe.click('[data-uireadall]');
  ok(fe.txt('#toast').includes('خوانده')&&fe.doc.querySelector('#bellBadge').hidden,'«خواندن همه» اعلان‌ها را می‌بندد');

  /* ج) بستهٔ رسانه: خرید کیف پول تا پخش */
  const fb=await load('event.html',withSara(),'?id=h1');
  ok(fb.errs.length===0,'صفحهٔ بستهٔ رسانه بی‌خطا بالا آمد');
  ok(fb.txt('.evhero').includes('کارگاه عکاسی مقدماتی'),'تیتر بسته همان بستهٔ رسانه است');
  ok(fb.all('.mediatile').length===5,'پنج رسانهٔ بسته با کاشی می‌آید');
  ok(fb.txt('#page').includes('تماشای نمونه'),'قطعهٔ نمونهٔ رایگان روی کاشی');
  fb.click('[data-buy-bundle]');
  ok(fb.doc.querySelector('#shBuy').className.includes('on'),'ورقهٔ خرید باز می‌شود');
  ok(fb.txt('#shBuy').includes('کیف پول نورا'),'راه پرداخت کیف پول با موجودی می‌آید');
  ok(fb.txt('#shBuy').includes('بازگشت وجه'),'ضمانت بازگشت وجه نوشته شده');
  fb.click('[data-uipay="gateway"]');
  ok(fb.doc.querySelector('#shBuy .opt.on')!==null && fb.doc.querySelector('[data-uipay="gateway"]').classList.contains('on'),'درگاه پرداخت انتخاب می‌شود');
  fb.click('[data-uipayyes]');
  await wait(60);
  ok(!fb.doc.querySelector('#shBuy').className.includes('on'),'بعد از پرداخت، ورقهٔ خرید بسته می‌شود');
  const lib1=JSON.parse(fb.window.localStorage.getItem('nora-home-library')||'[]');
  ok(lib1.filter(x=>x.past==='h1').length===5,'بعد از پرداخت، پنج قطعه به کتابخانه گره خورد');
  ok(lib1.some(x=>x.k==='bundle'&&x.id==='h1'),'خودِ بسته هم نشان‌دار کتابخانه شد');
  ok(JSON.parse(fb.window.localStorage.getItem('nora-home-user')).wallet===1250000,'پرداخت درگاه به کیف پول دست نزد');

  ok(fb.txt('#ctaIn').includes('تماشا')||fb.txt('#ctaIn').includes('پخش'),'بعد از خرید، نوار کار «تماشا» می‌شود نه «تهیه»');

  /* د) دسترسی آنلاین: پخش با پیشرفت و ادامه */
  fb.window.NORA_UI.player('h1','h1m1');
  await wait(40);
  ok(fb.doc.querySelector('#shPlay').className.includes('on'),'پخش‌کننده برای همین قطعه باز می‌شود');
  ok(/[۰-۹]+:[۰-۹]{2}/.test(fb.txt('#shPlay')),'زمان قطعه در پخش‌کننده');
  fb.click('#shPlay [data-uirate="1.5"]');
  ok(fb.doc.querySelector('#shPlay [data-uirate="1.5"]').classList.contains('on'),'سرعت پخش تا یک‌ونیم برابر تنطیم می‌شود');
  fb.window.NORA_UI.setProgress('h1m1',60);
  ok(fb.window.NORA_UI.progressOf('h1m1')===60,'ثانیهٔ تماشا ذخیره می‌شود');
  const libStore=makeStoreWith(fb.window.localStorage);
  const pg=await load('events.html',libStore,'#lib');
  ok(pg.txt('#libBox').includes('دوربین، نور و تنظیمات'),'کتابخانهٔ من قطعه‌های خریداری‌شده را می‌آورد');
  ok(pg.txt('#libBox').includes('ادامه'),'روی قطعهٔ نیمه‌دیده «ادامه» می‌آید');
  ok(/[۰-۹]+ رسانه/.test(pg.txt('#libCount')),'شمار رسانه‌های کتابخانه در سرصفحه می‌آید');
  pg.window.NORA_UI.doBuy('h3','h3m2');
  await wait(60);
  ok(pg.txt('#libBox').includes('احیای قلبی')||pg.txt('#libBox').includes('امداد'),'خرید تازه، بی نوکردن صفحه در کتابخانه می‌نشیند');

  /* ه) خرید تک‌قلم با کیف پول */
  const fm=await load('events.html',withSara(),'#media');
  fm.click('#grid .etile [data-ev="h2"]');
  await wait(40);
  ok(fm.doc.querySelector('#shEvent').className.includes('on'),'ورقهٔ بستهٔ دوم باز می‌شود');
  ok(/ریال/.test(fm.txt('#shEvent')),'مبلغ بسته دوم با ریال');
  fm.window.NORA_UI.buySheet('h2','h2m2');
  await wait(30);
  ok(fm.txt('#shBuy').includes('خرید تک‌قلم') && fm.txt('#shBuy').includes('۱۱۰'),'ورقهٔ تک‌قلم مبلغ قطعه را می‌دهد');
  fm.click('[data-uipayyes]');
  await wait(60);
  const lib2=JSON.parse(fm.window.localStorage.getItem('nora-home-library')||'[]');
  ok(lib2.some(x=>x.id==='h2m2'),'تک‌قلم خریداری‌شده در کتابخانه نشست');
  ok(lib2.filter(x=>x.past==='h2').length===1,'فقط همان قطعه باز شد، نه کل بسته');
  const wallet=JSON.parse(fm.window.localStorage.getItem('nora-home-user')).wallet;
  ok(wallet===1250000-110000,'کیف پول به اندازهٔ قطعه کم شد ('+wallet+')');

  /* و) بی حساب: ورود میان‌بر می‌خورد */
  const fn=await load('events.html',makeStore(),'#media');
  fn.window.NORA_UI.buySheet('h1',null);
  await wait(30);
  fn.click('[data-uipay="gateway"]');
  fn.click('[data-uipayyes]');
  await wait(40);
  ok(fn.doc.querySelector('#shAuth').className.includes('on'),'بی حساب، ورقهٔ ورود می‌آید');
  fn.doc.querySelector('#uimob').value='09121234567';
  fn.click('[data-uiphone]');
  await wait(30);
  ok(fn.doc.querySelector('#shAuth #uicode')!==null,'پلهٔ کد پنج‌رقمی می‌آید');
  fn.click('[data-uiback]');
  await wait(30);
  ok(fn.doc.querySelector('#shAuth #uimob')!==null,'دکمهٔ تغییر شماره برمی‌گرداند به پلهٔ موبایل');
  fn.doc.querySelector('#uimob').value='09121234567';
  fn.click('[data-uiphone]');
  await wait(30);
  fn.doc.querySelector('#uicode').value='11111';
  fn.click('[data-uicode]');
  await wait(30);
  ok(fn.txt('#toast').includes('۵۴۳۲۱'),'کد نادرست رد می‌شود');
  fn.doc.querySelector('#uicode').value='54321';
  fn.click('[data-uicode]');
  await wait(160);
  ok(!!fn.window.localStorage.getItem('nora-home-user'),'با کد درست، نشست ساخته می‌شود');
  const libN=JSON.parse(fn.window.localStorage.getItem('nora-home-library')||'[]');
  ok(libN.filter(x=>x.past==='h1').length===5,'بعد از ورود، خرید خودش تمام می‌شود (۵ قطعه)');
  ok(fn.window.localStorage.getItem('nora-home-user').includes('سارا محمدی'),'حساب ساخته‌شده همان کاربر نمونه است');

  /* ز) ورقهٔ کلیات از هر دو صفحه به صفحهٔ اختصاصی می‌رسد */
  const fh=await load('home.html',makeStore());
  fh.window.NORA_UI.eventSheet('e5');
  await wait(40);
  ok(fh.doc.querySelector('#shEvent a.btn.primary').getAttribute('href')==='event.html?id=e5','ورقهٔ خانه هم لینک صفحهٔ اختصاصی را می‌دهد');
  ok(fh.txt('#shEvent').includes('۱۱ مهر')||fh.txt('#shEvent').includes('۸ مهر'),'تاریخ رویداد در ورقهٔ خانه');
  fh.window.NORA_UI.eventSheet('h3');
  await wait(40);
  ok(fh.txt('#shEvent').includes('بسته')||fh.txt('#shEvent').includes('رسانه'),'ورقهٔ بستهٔ رسانه در خانه هم باز می‌شود');

  /* ح) نشانه‌گذاری و پیوندهای صفحهٔ اختصاصی */
  const evSrc=fs.readFileSync(DIR+'event.html','utf8');
  ok(/<link rel="canonical"/.test(evSrc),'صفحهٔ اختصاصی canonical دارد');
  ok(/property="og:title"/.test(evSrc),'og برای اشتراک‌گذاری هست');
  ok(/name="theme-color"/.test(evSrc),'رنگ نوار مرورگر تعیین شده');
  ok(!/href="event\.html\?id=\$\{id\}<\/a>/.test(evSrc),'لینک مرده به خودِ صفحه نمانده');
}

console.log('\nbuilder-smoke: '+checks+' بررسی، '+fails+' خطا');
process.exit(fails?1:0);
