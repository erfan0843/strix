/* ══════════════════════════════════════════════════════════════════════════
   نورا — آزمون صفحهٔ «پشتیبانی و راهنما»
   ──────────────────────────────────────────────────────────────────────────
   کاشی هر بخش ربات، پاپ‌آپ پرسش‌ها و راهنمای مدیر و راهنمای تصویری و صوتی،
   تیکت با پیوست (صدا، تصویر، ویدیو، فایل، پیوند)، پاسخ کارشناس، ارتباط
   مستقیم با مدیریت، پیام‌رسان‌ها، صندوق بی‌نام و جست‌وجو.

   اجرا:  node support.test.mjs
   ══════════════════════════════════════════════════════════════════════════ */
import jsdom from 'jsdom';
import fs from 'fs';
const {JSDOM}=jsdom;
const DIR=new URL('./',import.meta.url).pathname;
const OPEN=DIR+'support.html', URLF='file://'+OPEN;

let pass=0, fail=0;
const ok=(c,m)=>{ if(c){pass++; console.log('   ✓ '+m)} else {fail++; console.log('   ✗ '+m)} };
const wait=(t=90)=>new Promise(r=>setTimeout(r,t));

function makeStore(init){
  const m=new Map(Object.entries(init||{}));
  return {getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k),
    clear:()=>m.clear(),key:i=>[...m.keys()][i],get length(){return m.size},_m:m};
}

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
      w.console.error=(...a)=>errs.push('console.error: '+a.join(' '));
    }});
  await wait(650);
  const {window}=dom, doc=window.document;
  const fire=(el,type)=>{ el.dispatchEvent(new window.MouseEvent(type,{bubbles:true,cancelable:true})) };
  return {dom,window,doc,errs,
    click:sel=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel); fire(el,'click')},
    clickEl:el=>fire(el,'click'),
    set:(sel,v)=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel); el.value=v;
      el.dispatchEvent(new window.Event('input',{bubbles:true}));
      el.dispatchEvent(new window.Event('change',{bubbles:true}))},
    key:(sel,k)=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel);
      el.dispatchEvent(new window.KeyboardEvent('keydown',{key:k,bubbles:true}))},
    txt:sel=>{const el=doc.querySelector(sel); return el?el.textContent.replace(/\s+/g,' ').trim():''},
    all:sel=>[...doc.querySelectorAll(sel)],
    shown:sel=>{const el=doc.querySelector(sel); return !!el&&el.hidden!==true},
    openSheets:()=>[...doc.querySelectorAll('.sheet.on')].map(e=>e.id),
    tickets:()=>{ try{ return JSON.parse(window.localStorage.getItem('nora-support-tickets')||'[]') }catch(e){ return [] } },
    file:(sel,name,type)=>{
      const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel);
      const f=new window.File(['nora'],name,{type:type||'image/png'});
      Object.defineProperty(el,'files',{value:[f],configurable:true});
      el.dispatchEvent(new window.Event('change',{bubbles:true}));
    }};
}

/* ── ۱) صفحه و نوار بالا ── */
{
  console.log('\n── صفحهٔ پشتیبانی ──');
  const p=await load(makeStore());
  ok(p.errs.length===0,'بی‌خطا بار می‌شود'+(p.errs.length?': '+p.errs[0]:''));
  ok(p.doc.title==='نورا · پشتیبانی و راهنما','عنوان سند');
  ok(p.doc.documentElement.getAttribute('dir')==='rtl'&&p.doc.documentElement.getAttribute('lang')==='fa','راست‌به‌چپ و فارسی');
  const hb=p.doc.querySelector('.topbar .help-btn');
  ok(hb!==null&&hb.getAttribute('href')==='support.html'&&hb.classList.contains('on'),'نشان پشتیبانی در نوار بالا، کنار اعلان‌ها');
  ok(p.doc.querySelector('.topbar [href="home.html#notice"]')!==null,'نشان اعلان‌ها هم سرِ جایش');
  ok(p.all('.tabbar a').length===3,'نوار پایین سه‌تایی');
  ok(p.all('#modal').length===1&&p.all('#toast').length===1&&p.all('#scrim').length===1,'یک پاپ‌آپ، یک پیام‌رسان، یک پرده');
  const head=p.txt('.shead');
  ok(head.includes('پشتیبانی و راهنما')&&head.includes('هر بخش ربات یک کاشی'),'سرِ صفحه: نام و معنی کاشی‌ها');
  ok(p.all('#stiles .stile').length===16,'شانزده کاشی، همهٔ بخش‌های ربات');
  ok(p.txt('#tilesCount').includes('۱۶'),'شمارندهٔ کاشی‌ها');
  ok(p.all('#exList .ecard').length===5,'کارشناس‌ها در نوار کنار هم (لید + چهار کارشناس)');
  ok(p.all('#slaRows .adrow').length===3,'جدول پاسخ‌گویی');
  ok(p.txt('#neverText').includes('رمز'),'هشدار رمز کارت در کارت تماس');
  ok(p.all('#faqAll .qrow').length===32,'همهٔ پرسش‌های پرتکرار بخش‌ها');
  ok(p.doc.querySelector('h1.sr')!==null,'سرِ پنهان برای صفحه‌خوان');
  ok(p.doc.querySelector('#bellBadge')!==null,'نشان اعلان‌ها هم سرِ جایش هست');
  const th0=p.doc.documentElement.dataset.theme;
  p.click('[data-theme-toggle]');
  ok(p.doc.documentElement.dataset.theme!==th0,'کلید شب و روز کار می‌کند');
  p.click('[data-theme-toggle]');
  ok(p.doc.documentElement.dataset.theme===th0,'و به همان حال برمی‌گردد');
}

/* ── ۲) کاشی‌ها از داده می‌آیند؛ صافی و جست‌وجو ── */
{
  console.log('\n── کاشی‌ها، صافی و جست‌وجو ──');
  const p=await load(makeStore());
  const keys=p.all('#stiles .stile').map(b=>b.dataset.sec);
  ok(new Set(keys).size===16&&keys.includes('login')&&keys.includes('anon')&&keys.includes('complain'),'هر کاشی یک شناسهٔ بخش دارد');
  ok(p.all('#stiles .iw.brand').length>=3&&p.all('#stiles .iw.rose').length===3,'رنگ خانه‌ها از گروه بخش می‌آید');
  ok(p.all('#grpChips .fchip').length===6&&p.txt('#grpChips .fchip').includes('همه'),'صافی گروه‌ها شش‌تایی');
  p.click('#grpChips [data-grp="money"]');
  ok(p.all('#stiles .stile').length===2,'صافی «پرداخت» دو کاشی می‌گذارد');
  ok(p.txt('#tilesTitle')==='پرداخت','عنوان فهرست با صافی عوض می‌شود');
  p.click('#grpChips [data-grp="all"]');
  ok(p.all('#stiles .stile').length===16,'برگشتن به «همه»');
  p.set('#supQ','گواهی');
  await wait(260);
  ok(p.all('#stiles .stile').length<16,'جست‌وجو کاشی‌ها را صاف می‌کند');
  ok(p.shown('#qres')&&p.all('#qlist .qrow').length>=1,'نتیجهٔ جست‌وجو در کادر خودش');
  ok(p.all('#qlist .hitmark').length>=1,'واژهٔ جست‌وجو نشانه می‌خورد');
  p.click('#supQClear');
  await wait(260);
  ok(!p.shown('#qres')&&p.all('#stiles .stile').length===16,'پاک‌کردن جست‌وجو همه‌چیز را برمی‌گرداند');
  p.set('#supQ','زِرِشت');
  await wait(260);
  ok(p.txt('#qlist').includes('پیدا نشد')&&p.all('#qlist [data-ticket]').length>=1,'واژهٔ بی‌نتیجه راه تیکت را نشان می‌دهد');
}

/* ── ۳) پاپ‌آپ هر کاشی ── */
{
  console.log('\n── پاپ‌آپ بخش ──');
  const p=await load(makeStore());
  p.click('#stiles [data-sec="cert"]');
  await wait(120);
  ok(p.shown('#modal'),'پاپ‌آپ باز می‌شود');
  ok(p.txt('#mTitle')==='گواهی و بلیت'||p.txt('#mTitle').includes('گواهی'),'عنوان پاپ‌آپ نام همان بخش است');
  ok(p.all('#mBody .qrow').length===2,'پرسش‌های پرتکرار همان بخش');
  ok(p.all('#mBody .qrow.open').length===1,'پرسش نخست باز است');
  ok(p.txt('#mBody').includes('راهنمای مدیر سامانه'),'راهنمای مدیر سامانه در پاپ‌آپ');
  ok(p.all('#mBody .mcard').length>=1,'راهنمای تصویری یا صوتی همان بخش');
  ok(p.all('#mBody a[href^="form.html"]').length===1,'فرم لینک‌شدهٔ مدیر');
  ok(p.all('#mFoot [data-ticket="cert"]').length===1,'دکمهٔ ثبت تیکت از همان بخش، ته پاپ‌آپ');
  const faq=p.doc.querySelector('#mBody .qrow .qbtn');
  p.clickEl(faq);
  ok(p.doc.querySelector('#mBody .qrow').classList.contains('open')===false,'پرسش با کلیک بسته می‌شود');
  p.clickEl(faq);
  ok(p.doc.querySelector('#mBody .qrow').classList.contains('open')===true,'و باز هم می‌شود');
  p.key('body','Escape');
  ok(!p.shown('#modal'),'Escape پاپ‌آپ را می‌بندد');
  p.click('#stiles [data-sec="login"]');
  await wait(80);
  p.click('#modal');
  ok(!p.shown('#modal'),'کلیک روی پشت پاپ‌آپ هم می‌بندد');
}

/* ── ۴) تیکت با پیوست، پاسخ کارشناس ── */
{
  console.log('\n── تیکت و پاسخ ──');
  const p=await load(makeStore());
  p.click('#stiles [data-sec="pay"]');
  await wait(80);
  p.click('#mFoot [data-ticket="pay"]');
  await wait(80);
  ok(p.txt('#mTitle').includes('تیکت تازه'),'از پاپ‌آپ به فرم تیکت می‌رسیم');
  ok(p.all('#mBody [data-att="image"]').length===1&&p.all('#mBody [data-att="video"]').length===1&&
     p.all('#mBody [data-att="voice"]').length===1&&p.all('#mBody [data-att="link"]').length===1,
     'پنج راه پیوست: تصویر، ویدیو، ویس، پیوند، فایل');
  ok(p.all('#mBody #fCat option').length>=6&&p.doc.querySelector('#fCat').value==='پرداخت','دسته از خودِ بخش پیش‌انتخاب می‌شود');
  p.set('#fBody','کوتاه');
  p.click('#mFoot [data-sendticket]');
  await wait(60);
  ok(p.tickets().length===1&&p.txt('#toast').includes('روشن‌تر'),'متن کوتاه فرستاده نمی‌شود');
  p.set('#fBody','رسید کارگاه عکاسی را فرستادم؛ مبلغ کم شده و ثبت‌نام نشده است.');
  p.set('#fName','سارا محمدی');
  p.set('#fContact','۰۹۱۲۳۴۵۶۷۸۹');
  p.click('#mBody [data-att="link"]');
  p.set('#mBody [data-lurl]','https://lifeline1.ir/pay');
  p.click('#mBody [data-ladd]');
  ok(p.all('#mBody [data-pins] .pin').length===1,'پیوند به پیوست‌ها می‌چسبد');
  p.click('#mBody [data-att="voice"]');
  await wait(1200);
  p.click('#mBody [data-att="voice"]');
  ok(p.all('#mBody [data-pins] .pin').length===2,'ویس هم پیوست می‌شود');
  p.file('#mBody [data-finput]','اسکرین‌شات.png','image/png');
  await wait(60);
  ok(p.all('#mBody [data-pins] .pin').length===3,'تصویر پیوست می‌شود');
  p.click('#mFoot [data-sendticket]');
  await wait(120);
  const T=p.tickets();
  ok(T.length===2&&T[1].sec==='pay','تیکت ثبت شد');
  ok(/^[0-9]{5}$/.test(T[1].code),'کد پیگیری پنج‌رقمی');
  ok(T[1].thread[0].atts.length===3,'پیوست‌ها همراه تیکت رفتند');
  ok(p.txt('#mTitle').includes('گفت‌وگو')||p.all('#modal .frow.me').length===1,'بی‌درنگ وارد گفت‌وگوی تیکت می‌شویم');
  ok(p.all('#supReply').length===1,'کادر پاسخ در گفت‌وگو');
  await wait(1700);
  ok(p.all('#modal .frow').length===2&&p.txt('#modal').includes('بررسی می‌کنم'),'پاسخ کارشناس در همان گفت‌وگو می‌آید');
  ok(p.all('#modal .fx').length>=1,'پاسخ کارشناس هم پیوست دارد');
  p.click('#mBody .abtn[data-catt]');
  ok(p.all('#mBody [data-ctray] [data-att]').length===5,'سینی پیوست برای پاسخ هم هست');
  p.set('#supReply','پیگیری کردم، ممنون.');
  p.click('.cinput [data-csend]');
  await wait(1700);
  ok(p.tickets()[1].thread.length===4,'پاسخ من هم به همان تیکت می‌چسبد');
  p.click('#mFoot [data-closetk]');
  await wait(80);
  ok(p.tickets()[1].closed===true&&p.txt('#modal').includes('بسته شده'),'تیکت با پایان کار بسته می‌شود');
  p.key('body','Escape');
}

/* ── ۵) صندوق بی‌نام و پیشروی تیکت‌ها ── */
{
  console.log('\n── بی‌نام و سقف تیکت باز ──');
  const p=await load(makeStore());
  p.window.location.hash='#anon';
  p.click('#stiles [data-sec="anon"]');
  await wait(80);
  p.click('#mFoot [data-ticket="anon"]');
  await wait(80);
  ok(p.txt('#mTitle').includes('بی‌نام')&&p.all('#fName').length===0,'صندوق بی‌نام نام و شماره نمی‌خواهد');
  p.set('#fBody','پیشنهاد: جلسه‌های کتاب‌خوانی شهرهای دیگر هم باشد.');
  p.click('#mFoot [data-sendticket]');
  await wait(300);
  const T=p.tickets();
  ok(T.length===2&&T[1].anon===true&&T[1].name==='','پیام بی‌نام ثبت شد، بی نام و نشان');
  ok(p.txt('#modal').includes('پاسخ')&&p.txt('#modal').includes('کد پیگیری'),'به بی‌نام پاسخ نمی‌دهیم، توضیح می‌دهیم');
  p.key('body','Escape');
  ok(p.all('#tkList .tkrow').length===2,'تیکت‌های من دو ردیف شد');
  const openNow=p.tickets().filter(t=>!t.closed).length;
  ok(openNow===2,'دو تیکت باز داریم (نمونه + بی‌نام)');
  p.click('#tkList .tkrow');
  await wait(80);
  ok(p.txt('#mTitle').includes('گفت‌وگو'),'ردیف تیکت‌های من گفت‌وگو را باز می‌کند');
  ok(p.all('#modal .frow').length>=1,'متن پیام بی‌نام خودم پیداست');
  p.key('body','Escape');
  ok(p.shown('#latest'),'بالاچهٔ تازه‌ترین پاسخ هست');
}

/* ── ۶) ورقه‌های مدیریت و راهنمای رسانه ── */
{
  console.log('\n── ورقه‌ها ──');
  const p=await load(makeStore());
  p.click('#more [data-sheet="shContacts"]');
  await wait(120);
  ok(p.openSheets().includes('shContacts')&&p.doc.querySelector('#scrim').classList.contains('on'),'ورقهٔ مدیریت باز می‌شود');
  ok(p.all('#ctBody .mlink').length>=5,'مدیران و فرم‌های لینک‌شده در ورقه');
  ok(p.txt('#ctBody').includes('پیام‌رسان'),'پیام‌رسان‌ها هم آمده‌اند');
  ok(p.all('#ctBody .mchip').length>=4,'بله، تلگرام، سروش و گپ');
  ok(p.all('#ctBody [data-ticket="join"]').length===1&&p.all('#ctBody [data-ticket="complain"]').length===1,'ردیف همکاری و ردیف انتقاد');
  p.click('#ctBody [data-ticket="join"]');
  await wait(150);
  ok(p.openSheets().length===0&&p.shown('#modal'),'از ورقه به فرم تیکت همان کار می‌رسد');
  p.key('body','Escape');
  p.click('#stiles [data-sec="login"]');
  await wait(80);
  const md=p.doc.querySelector('#mBody [data-media]');
  ok(md!==null,'دکمهٔ راهنمای رسانه در پاپ‌آپ');
  p.clickEl(md);
  await wait(120);
  ok(p.openSheets().includes('shMedia'),'راهنمای تصویری در ورقهٔ خودش باز می‌شود');
  ok(p.txt('#mdBody').includes('گام‌به‌گام')&&p.all('#mdBody .tipit').length>=2,'گام‌های راهنما از دادهٔ همان بخش');
  p.click('#mdBody [data-ticket]');
  await wait(150);
  ok(p.shown('#modal')&&p.openSheets().length===0,'از راهنما هم می‌شود تیکت زد');
}

/* ── ۷) داده، سند و پیوند‌ها ── */
{
  console.log('\n── داده و سند ──');
  const p=await load(makeStore());
  const raw=fs.readFileSync(DIR+'data.js','utf8');
  ok(/grps:\[/.test(raw)&&/tones:\{/.test(raw)&&/lead:\{/.test(raw)&&/sla:\[/.test(raw)&&/howto:\[/.test(raw),
     'گروه‌ها، رنگ‌ها، کارشناس لید و جدول‌ها همه در data.js');
  ok((raw.match(/grp:'/g)||[]).length>=16,'هر کاشی گروه خودش را دارد');
  const html=fs.readFileSync(OPEN,'utf8');
  const ids=[...html.matchAll(/id="([^"]+)"/g)].map(m=>m[1]);
  ok(new Set(ids).size===ids.length,'شناسه‌های یکتا در صفحه');
  ok(!/class="(search|sup-hero|mcard mcard)"/.test(html),'کلاس به‌جاماندهٔ طرح پیشین نیست');
  const css=fs.readFileSync(DIR+'support.css','utf8');
  ok((css.match(/\{/g)||[]).length===(css.match(/\}/g)||[]).length,'آکولادهای CSS جفت‌اند');
  ok(!/\.mpart \.bd\{/.test(css),'بدنهٔ قطعه‌های پاپ‌آپ کلاس جدا دارد');
  const pages=['home.html','events.html','account.html','event.html','form.html','builder.html','create.html','support.html','index.html','offline.html'];
  ok(pages.every(f=>fs.readFileSync(DIR+f,'utf8').includes('?v=18')),'همهٔ صفحه‌ها یک نسخهٔ دارایی (v=18)');
  const sw=fs.readFileSync(DIR+'sw.js','utf8');
  ok(sw.includes("'support.html'")&&sw.includes("'support.css'")&&sw.includes("'support.js'"),'سرویس‌ورکر صفحهٔ پشتیبانی را پیش‌بار می‌کند');
  const man=fs.readFileSync(DIR+'manifest.webmanifest','utf8');
  ok(man.includes('support.html'),'میان‌بر پشتیبانی در manifest');
  const doc=fs.readFileSync(DIR+'support-arch.md','utf8');
  ok(doc.includes('کاشی')&&doc.includes('تیکت'),'سند معماری پشتیبانی به‌روز است');
  ok(p.all('a[href^="http"]').every(a=>a.rel.includes('noopener')),'پیوندهای بیرونی rel دارند');
  ok(p.all('.i use').every(u=>p.doc.querySelector(u.getAttribute('href'))!==null),'همهٔ نمادها در اسپرایت هستند');
}

console.log('\n'+(fail?'✗ '+fail+' رد، '+pass+' قبول':'✓ همه سبز: '+pass+' قبول'));
process.exit(fail?1:0);
