/* ══════════════════════════════════════════════════════════════════════════
   نورا — آزمون صفحهٔ «پشتیبانی و راهنما»
   ──────────────────────────────────────────────────────────────────────────
   ساختار تازه: سرِ صفحه و جست‌وجو، راهنمای بخش به بخش (۲۱ فصل جمع‌شده در ۵
   گروه؛ هر فصل با مهلت، چیزهای لازم، سه گام تصویری، پنج یا شش پرسش و پاسخ،
   نکتهٔ مدیر و بخش‌های وابسته)، تیکت با پیوست صدا و تصویر و ویدیو و فایل و
   پیوند، گفت‌وگوی کارشناس، صندوق بی‌نام، سقف تیکت باز، و کارشناس‌ها و
   مدیریت در ته صفحه.

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
  await wait(700);
  const {window}=dom, doc=window.document;
  const fire=(el,type)=>{ el.dispatchEvent(new window.MouseEvent(type,{bubbles:true,cancelable:true})) };
  return {dom,window,doc,errs,
    click:sel=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel); fire(el,'click')},
    clickEl:el=>fire(el,'click'),
    set:(sel,v)=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel); el.value=v;
      el.dispatchEvent(new window.Event('input',{bubbles:true}));
      el.dispatchEvent(new window.Event('change',{bubbles:true}))},
    key:(sel,k)=>{const el=sel==='body'?doc.body:doc.querySelector(sel);
      if(!el) throw new Error('نیست: '+sel);
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

/* ── ۱) صفحه، نوار بالا و سرِ صفحه ── */
{
  console.log('\n── صفحه و سرِ صفحه ──');
  const p=await load(makeStore());
  ok(p.errs.length===0,'بی‌خطا بار می‌شود'+(p.errs.length?': '+p.errs[0]:''));
  ok(p.doc.title==='نورا · پشتیبانی و راهنما','عنوان سند');
  ok(p.doc.documentElement.getAttribute('dir')==='rtl'&&p.doc.documentElement.getAttribute('lang')==='fa','راست‌به‌چپ و فارسی');
  const hb=p.doc.querySelector('.topbar .help-btn');
  ok(hb!==null&&hb.getAttribute('href')==='support.html'&&hb.classList.contains('on'),'نشان پشتیبانی در نوار بالا، کنار اعلان‌ها');
  ok(p.doc.querySelector('.topbar [href="home.html#notice"]')!==null,'نشان اعلان‌ها هم سرِ جایش');
  ok(p.all('.tabbar a').length===3,'نوار پایین سه‌تایی');
  ok(p.all('#modal').length===1&&p.all('#toast').length===1&&p.all('#scrim').length===1,'یک پاپ‌آپ، یک پیام‌رسان، یک پرده');
  ok(p.doc.querySelector('h1.sr')!==null,'سرِ پنهان برای صفحه‌خوان');
  ok(p.doc.querySelector('#bellBadge')!==null,'نشان اعلان‌ها هم سرِ جای خودش');
  ok(p.txt('.shtx').includes('پشتیبانی و راهنما')&&p.txt('.shtx').includes('گام‌به‌گام'),'سرِ صفحه: نام و معنی راهنما');
  ok(p.all('#supQ').length===1&&p.all('#supQClear').length===1,'کادر جست‌وجو و دکمهٔ پاک‌کردن');
  ok(p.txt('#supHours').includes('۹ تا ۱۸')&&p.txt('#supLive').includes('آنلاین'),'ساعت پاسخ‌گویی و نشان آنلاین');
  ok(p.all('.hacts [data-ticket]').length===2&&p.all('.hacts [data-jump]').length===1,'سه کنش زودِ سرِ صفحه');
  const th0=p.doc.documentElement.dataset.theme;
  p.click('[data-theme-toggle]');
  ok(p.doc.documentElement.dataset.theme!==th0,'کلید شب و روز کار می‌کند');
  p.click('[data-theme-toggle]');
  ok(p.doc.documentElement.dataset.theme===th0,'و به همان حال برمی‌گردد');
  ok(p.all('a[href^="http"]').every(a=>a.rel.includes('noopener')),'پیوندهای بیرونی rel دارند');
  ok(p.all('.i use').every(u=>p.doc.querySelector(u.getAttribute('href'))!==null),'همهٔ نمادها در اسپرایت هستند');
  const sprite=new Set(p.all('symbol[id]').map(s=>'#'+s.id));
  const secIcons=[...new Set([...p.all('#chapters .chhead .iw use')].map(u=>u.getAttribute('href')))];
  ok(secIcons.length>=18&&secIcons.every(h=>sprite.has(h)),'نماد هر بخش در اسپرایت هست ('+secIcons.length+' نماد)');
}

/* ── ۲) راهنمای بخش به بخش ── */
{
  console.log('\n── راهنمای بخش به بخش ──');
  const p=await load(makeStore());
  ok(p.all('#chapters .chapter').length===21,'بیست‌ویک فصل برای بیست‌ویک بخش ربات');
  ok(p.all('#chapters .gsec').length===5,'پنج گروه روایی');
  ok(p.all('#chapters .gband').length===5,'هر گروه هنرِ سرصفحه دارد');
  ok(p.all('#chapters .chapter .chhead').length===21,'هر فصل سرِ دکمه‌ای خودش را دارد');
  ok(p.all('#chapters .chbody[hidden]').length===21,'همهٔ فصل‌ها جمع‌شده می‌آیند');
  ok(p.all('#chapters .chapter.open').length===0,'هیچ فصلی در آغاز باز نیست');
  ok(p.all('#chapters .stp').length===63,'هر فصل سه گام: شصت‌وسه گام');
  ok(p.all('#chapters .stp .mk').length===63,'هر گام صفحهٔ کوچک تصویری خودش را دارد');
  ok(p.all('#chapters .qrow').length===126,'پرسش‌های هر بخش: صد و بیست‌وشش پرسش');
  ok(p.all('#chapters .tipit').length===42,'دو نکتهٔ مدیر برای هر بخش');
  ok(p.all('#chapters .needlist li').length===38,'چیزهایی که باید همراه داشته باشی: '+p.all('#chapters .needlist li').length);
  ok(p.all('#chapters .ptime').length===21,'مهلت و زمان هر بخش');
  ok(p.all('#chapters .relrow [data-goto]').length>=42,'بخش‌های وابسته، میان‌بر هر بخش');
  ok(p.all('#chapters [data-media]').length===25,'راهنمای رسانه‌ای هر بخش');
  ok(new Set(p.all('#chapters a[href^="form.html"]').map(a=>a.getAttribute('href'))).size===3,'سه فرم لینک‌شدهٔ مدیران');
  ok(p.all('#chapters .chcover img').every(i=>/^posters\/.+\.svg$/.test(i.getAttribute('src'))),'هنر هر فصل پوستر SVG است');
  ok(p.all('#toc .fchip').length===6&&p.txt('#toc .fchip').includes('همه'),'فهرست گروه‌ها شش چسب دارد');
  ok(p.txt('#readerCount').includes('۲۱ بخش')&&p.txt('#readerCount').includes('۵ گروه'),'شمارندهٔ راهنما');
  ok(p.doc.querySelector('#ch-login')!==null&&p.doc.querySelector('#ch-complain')!==null,'شناسهٔ فصل‌ها از کلید بخش می‌آید');
  ok(p.doc.querySelector('#g-money .chapter').id==='ch-pay','هر گروه فصل‌های خودش را دارد');
  ok(p.all('#chapters .qrow.open').length===0,'پرسش‌ها بسته می‌آیند تا شلوغ نشود');
  ok(p.all('#chapters .chcover .catg').length===21&&p.txt('#ch-cert .chmeta').includes('گواهی'),'نشان دسته و مهلت روی هر فصل');
  ok(p.all('#chapters .ecard').length===0&&p.all('#chapters .mchip').length===0,'کارشناس‌ها میان فصل‌ها نیستند');
  ok(p.all('#openAll').length===1&&p.txt('#openAll').includes('همه را باز کن'),'دکمهٔ باز کردن همهٔ فصل‌ها');

  /* باز و بسته کردن */
  const ch=p.doc.querySelector('#ch-login');
  ok(ch.querySelector('.chbody').hidden&&ch.querySelector('.chhead').getAttribute('aria-expanded')==='false','فصل ورود بسته است');
  p.clickEl(ch.querySelector('.chhead'));
  ok(!ch.querySelector('.chbody').hidden&&ch.getAttribute('aria-expanded')===undefined===false||!ch.querySelector('.chbody').hidden,'با یک زدن باز می‌شود');
  ok(ch.querySelector('.chhead').getAttribute('aria-expanded')==='true','و aria هم عوض می‌شود');
  ok(ch.querySelector('.chbody').textContent.includes('پیش از شروع'),'بلوک «پیش از شروع» در تنِ فصل');
  const qb=ch.querySelector('.qbtn');
  p.clickEl(qb);
  ok(ch.querySelector('.qrow').classList.contains('open'),'پرسش درون فصل باز باز می‌شود');
  p.clickEl(qb);
  ok(!ch.querySelector('.qrow').classList.contains('open'),'و بسته');
  p.clickEl(ch.querySelector('.chhead'));
  ok(ch.querySelector('.chbody').hidden,'و فصل دوباره جمع می‌شود');

  /* همه را باز کن */
  p.click('#openAll');
  await wait(60);
  ok(p.all('#chapters .chapter.open').length===21,'«همه را باز کن» همه را می‌گشاید');
  ok(p.txt('#openAll').includes('همه را ببند'),'برچسب دکمه می‌گردد');
  p.click('#openAll');
  await wait(60);
  ok(p.all('#chapters .chapter.open').length===0&&p.txt('#openAll').includes('همه را باز کن'),'و دوباره همه را می‌بندد');

  /* وابسته‌ها: از یک بخش به بخش دیگر */
  p.clickEl(p.doc.querySelector('#ch-pay [data-goto]'));
  await wait(120);
  ok(p.doc.querySelector('#ch-installment').classList.contains('open'),'چسب وابسته، بخش مربوط را باز می‌کند');
}

/* ── ۳) جست‌وجو ── */
{
  console.log('\n── جست‌وجو ──');
  const p=await load(makeStore());
  ok(!p.shown('#results'),'نتیجهٔ جست‌وجو در آغاز پنهان است');
  p.set('#supQ','اقساط');
  await wait(300);
  ok(p.shown('#results'),'با واژه، کادر نتیجه باز می‌شود');
  ok(p.all('#resList .qrow').length>=1&&p.all('#resList .qrow').length<=10,'پاسخ‌های پیداشده، سقف ده تا');
  ok(p.all('#resList .hitmark').length>=1,'واژهٔ جست‌وجو نشانه می‌خورد');
  ok(p.txt('#resCount').includes('پاسخ'),'شمارندهٔ پاسخ‌ها');
  ok(p.all('#resList [data-goto]').length>=1,'هر پاسخ میان‌بر «راهنمای همین بخش» دارد');
  p.clickEl(p.doc.querySelector('#resList [data-goto]'));
  await wait(140);
  ok(p.all('#chapters .chapter.open').length>=1,'از نتیجهٔ جست‌وجو، فصل همان بخش باز می‌شود');
  ok(p.all('#chapters .chapter').filter(c=>!c.hidden).length>0,'فصل‌های مربوط هم می‌مانند');
  ok(p.all('#chapters .chapter').filter(c=>c.hidden).length>0,'و فصل‌های بی‌ربط می‌روند');
  ok(p.all('#chapters .gsec').filter(g=>g.hidden).length>0,'گروه‌های بی‌فصل هم پنهان می‌شوند');
  ok(p.txt('#readerCount').includes('بخش با این واژه'),'شمارندهٔ راهنما با صافی عوض می‌شود');
  p.click('#supQClear');
  await wait(300);
  ok(!p.shown('#results')&&p.all('#chapters .chapter').filter(c=>c.hidden).length===0,'پاک‌کردن جست‌وجو همه را برمی‌گرداند');
  ok(p.txt('#readerCount').includes('۲۱ بخش'),'شمارنده هم به حال نخست برمی‌گردد');
  p.set('#supQ','زِرِشت');
  await wait(300);
  ok(p.shown('#resMiss')&&p.all('#resMiss [data-ticket]').length===1,'واژهٔ بی‌نتیجه راه تیکت را نشان می‌دهد');
  ok(p.txt('#resCount')==='۰ پاسخ','شمارنده صفر می‌شود');
  p.key('#supQ','Escape');
  await wait(300);
  ok(p.doc.querySelector('#supQ').value===''&&!p.shown('#results'),'Escape واژه را پاک می‌کند');
  p.key('body','/');
  ok(p.doc.activeElement&&p.doc.activeElement.id==='supQ','کلید / جست‌وجو را نشان می‌کند');
}

/* ── ۴) تیکت با پیوست و گفت‌وگوی کارشناس ── */
{
  console.log('\n── تیکت و پاسخ ──');
  const p=await load(makeStore());
  p.click('#ch-pay .cha [data-ticket="pay"]');
  await wait(120);
  ok(p.shown('#modal'),'پاپ‌آپ تیکت باز می‌شود');
  ok(p.txt('#mTitle').includes('تیکت تازه')&&p.txt('#mSub').includes('پیوست'),'عنوان و زیرعنوان فرم تیکت');
  ok(p.all('[data-tray] [data-att="image"]').length===1&&p.all('[data-tray] [data-att="video"]').length===1&&
     p.all('[data-tray] [data-att="voice"]').length===1&&p.all('[data-tray] [data-att="link"]').length===1&&
     p.all('[data-tray] [data-att="file"]').length===1,'پنج راه پیوست: تصویر، ویدیو، ویس، فایل، پیوند');
  ok(p.all('#fCat option').length>=6&&p.doc.querySelector('#fCat').value==='پرداخت','دسته از خودِ بخش پیش‌انتخاب می‌شود');
  p.set('#fBody','کوتاه');
  p.click('[data-sendticket]');
  await wait(80);
  ok(p.tickets().length===1&&p.txt('#toast').includes('روشن‌تر'),'متن کوتاه فرستاده نمی‌شود');
  p.set('#fBody','رسید کارگاه عکاسی را فرستادم؛ مبلغ کم شده و ثبت‌نام نشده است.');
  p.click('[data-sendticket]');
  await wait(80);
  ok(p.tickets().length===1&&p.txt('#toast').includes('نامت را بنویس'),'بی نام، تیکت حساب‌دار ثبت نمی‌شود');
  p.set('#fName','سارا محمدی');
  p.set('#fContact','۰۹۱۲۳۴۵۶۷۸۹');
  p.click('[data-tray] [data-att="link"]');
  ok(!p.doc.querySelector('[data-lbox]').hidden,'کادر پیوند باز می‌شود');
  p.set('[data-lurl]','بدون‌پیشوند');
  p.click('[data-ladd]');
  ok(p.all('[data-pins] .pin').length===0&&p.txt('#toast').includes('http'),'پیوند بی‌پیشوند پذیرفته نمی‌شود');
  p.set('[data-lurl]','https://lifeline1.ir/pay');
  p.click('[data-ladd]');
  ok(p.all('[data-pins] .pin').length===1,'پیوند به پیوست‌ها می‌چسبد');
  p.click('[data-tray] [data-att="voice"]');
  await wait(1150);
  ok(p.doc.querySelector('[data-att="voice"]').classList.contains('on'),'ویس در حال ضبط است');
  p.click('[data-tray] [data-att="voice"]');
  ok(p.all('[data-pins] .pin').length===2,'ویس پیوست شد');
  p.file('[data-finput]','اسکرین‌شات.png','image/png');
  await wait(60);
  ok(p.all('[data-pins] .pin').length===3,'تصویر پیوست شد');
  p.click('[data-pins] [data-unpin]');
  ok(p.all('[data-pins] .pin').length===2,'پیوست با ضربدر برداشته می‌شود');
  p.file('[data-finput]','اسکرین‌شات.png','image/png');
  await wait(60);
  p.click('[data-sendticket]');
  await wait(150);
  const T=p.tickets();
  ok(T.length===2&&T[1].sec==='pay'&&T[1].cat==='پرداخت','تیکت ثبت شد، با بخش و دستهٔ خودش');
  ok(/^[0-9]{5}$/.test(T[1].code),'کد پیگیری پنج‌رقمی');
  ok(T[1].thread[0].atts.length===3,'سه پیوست همراه تیکت رفتند');
  ok(p.txt('#mTitle').includes('گفت‌وگو')||p.all('#modal .frow.me').length===1,'بی‌درنگ وارد گفت‌وگوی تیکت می‌شویم');
  ok(p.all('#supReply').length===1&&p.all('.cinput [data-csend]').length===1,'کادر پاسخ در گفت‌وگو');
  await wait(1700);
  ok(p.all('#modal .frow').length===2&&p.txt('#modal').includes('بررسی می‌کنم'),'پاسخ کارشناس در همان گفت‌وگو می‌آید');
  ok(p.all('#modal .fx').length>=2,'پاسخ کارشناس هم پیوست دارد');
  ok(p.all('#modal .pbsim i').length>0,'نوار ویس در حباب کشیده می‌شود');
  p.click('#mBody [data-catt]');
  ok(p.all('#mBody [data-ctray] [data-att]').length===5,'سینی پیوست برای پاسخ هم هست');
  p.set('#supReply','پیگیری کردم، ممنون.');
  p.click('.cinput [data-csend]');
  await wait(150);
  ok(p.tickets()[1].thread.length===3,'پاسخ من هم به همان تیکت می‌چسبد');
  ok(p.doc.querySelector('#supReply')&&p.doc.querySelector('#supReply').value==='','کادر پاسخ خالی می‌شود');
  p.click('#mFoot [data-closetk]');
  await wait(150);
  ok(p.tickets()[1].closed===true&&p.txt('#modal').includes('بسته'),'تیکت با پایان کار بسته می‌شود');
  ok(p.all('#mFoot [data-closetk]').length===0,'تیکت بسته دکمهٔ پایان ندارد');
  ok(p.all('#modal .tkt-acc.on').length===1,'نوار پیشرفت تیکت پر می‌شود');
  p.key('body','Escape');
  ok(p.all('#tkList .tkrow').length===2,'تیکت‌های من دو ردیف شد');
  ok(p.all('#tkList .tkrow .tag').length===2,'حال هر تیکت روی ردیف پیداست');
  p.click('#tkList .tkrow');
  await wait(120);
  ok(p.txt('#mTitle').includes('گفت‌وگو'),'ردیف تیکت‌های من گفت‌وگو را باز می‌کند');
  p.key('body','Escape');
  ok(p.shown('#latest')&&p.all('#latest .bubble').length===1,'بالاچهٔ تازه‌ترین پاسخ هست');
  p.click('#latest [data-thread]');
  ok(p.shown('#modal'),'از تازه‌ترین پاسخ هم گفت‌وگو باز می‌شود');
  p.key('body','Escape');
}

/* ── ۵) صندوق بی‌نام و سقف تیکت باز ── */
{
  console.log('\n── بی‌نام و سقف تیکت باز ──');
  const p=await load(makeStore());
  ok(p.all('#tkList .tkrow').length===1,'تیکت نمونهٔ نخستین در حافظه است');
  p.click('.hacts [data-ticket="anon"]');
  await wait(100);
  ok(p.txt('#mTitle').includes('بی‌نام')&&p.all('#fName').length===0&&p.all('#fContact').length===0,'صندوق بی‌نام نام و شماره نمی‌خواهد');
  p.set('#fBody','پیشنهاد: جلسه‌های کتاب‌خوانی شهرهای دیگر هم باشد.');
  p.click('[data-sendticket]');
  await wait(300);
  const T=p.tickets();
  ok(T.length===2&&T[1].anon===true&&T[1].name===''&&T[1].contact==='','پیام بی‌نام ثبت شد، بی نام و نشان');
  ok(p.txt('#modal').includes('کد پیگیری')&&p.txt('#modal').includes('پاسخ'),'به بی‌نام پاسخ نمی‌دهیم، توضیح می‌دهیم');
  ok(p.all('#modal [data-ticket="complain"]').length===1,'و راه تیکت حساب‌دار را نشان می‌دهیم');
  p.key('body','Escape');
  ok(p.all('#tkList .tkrow').length===2,'تیکت‌های من دو ردیف شد');
  p.click('#tkList .tkrow');
  await wait(120);
  ok(p.all('#modal .frow').length>=1&&p.txt('#modal').includes('بی‌نام'),'متن پیام بی‌نام خودم پیداست');
  ok(p.all('#modal .fmeta').length>=1,'زمان روی حباب هست');
  p.key('body','Escape');
  ok(p.txt('#tkOpenCap').includes('۲ تیکت باز'),'شمارندهٔ سقف تیکت باز: '+p.txt('#tkOpenCap'));
  /* دو تیکت باز می‌زنیم تا سقف سه‌تایی پر شود، بعد تیکت چهارم را می‌سنجیم */
  const q=await load(makeStore({}));
  ok(q.tickets().filter(t=>!t.closed).length===1,'نمونه یک تیکت باز دارد');
  for(let i=0;i<2;i++){
    q.click('.hacts [data-ticket="general"]');
    await wait(90);
    q.set('#fBody','تیکت آزمایشی شمارهٔ '+i+' برای پر کردن سقف تیکت‌های باز');
    q.set('#fName','سارا محمدی');
    q.click('[data-sendticket]');
    await wait(180);
    q.key('body','Escape');
  }
  ok(q.tickets().filter(t=>!t.closed).length===3,'سقف تیکت باز پر شد: سه تیکت');
  ok(q.txt('#tkOpenCap').includes('۳ تیکت باز از ۳'),'شمارنده سقف را نشان می‌دهد');
  q.click('.hacts [data-ticket="general"]');
  await wait(140);
  ok(q.txt('#mTitle').includes('زیاد است')&&q.all('[data-sendticket]').length===0,'تیکت چهارم ثبت نمی‌شود و راه بستن را می‌گوید');
  ok(q.tickets().length===3,'حافظه دست‌نخورده ماند');
  q.click('[data-mclose]');
  await wait(80);
  ok(q.tickets().filter(t=>!t.closed).length===3,'پس از بستن پاپ‌آپ هم همان سه تیکت');
  ok(q.errs.length===0,'بی‌خطا'+(q.errs.length?': '+q.errs[0]:''));
}

/* ── ۶) کارشناس‌ها، مدیریت و تماس (ته صفحه) ── */
{
  console.log('\n── کارشناس‌ها و مدیریت ──');
  const p=await load(makeStore());
  ok(p.all('#exList .ecard').length===5,'کارشناس لید و چهار کارشناس');
  ok(p.all('#exList .ecard .eav').length===5,'هر کارشناس نشان خودش را دارد');
  ok(p.txt('#exCount').includes('آنلاین'),'شمارندهٔ آنلاین‌ها');
  ok(p.all('#exList .mchip').length>=4,'راه‌های پیام‌رسان کارشناس‌ها');
  ok(p.all('#mgList .drow').length===2&&p.all('#mgList .drow[href^="mailto"]').length===2,'دو مدیر با رایانامهٔ مستقیم');
  ok(p.all('#fmList .drow[href^="form.html"]').length===3,'سه فرم لینک‌شدهٔ مدیران');
  ok(p.all('#slaRows .adrow').length===3,'جدول پاسخ‌گویی سه ردیف');
  ok(p.all('#howto .adrow').length===3,'چه بنویسی که سریع حل شود، سه ردیف');
  ok(p.txt('#neverText').includes('رمز'),'هشدار رمز کارت در کارت تماس');
  ok(p.doc.querySelector('.adrow[href^="tel:"]')!==null&&p.doc.querySelector('.adrow[href^="mailto:"]')!==null,'شماره و رایانامهٔ تماس');
  const team=p.doc.querySelector('#team');
  const main=p.doc.querySelector('main');
  const order=[...main.querySelectorAll('section.sec')].map(s=>s.id||'');
  ok(order[order.length-1]==='team','کارشناس‌ها و مدیریت ته صفحه است: '+order.slice(-2).join(' ‹ '));
  ok(team.compareDocumentPosition(p.doc.querySelector('#chapters'))&p.window.Node.DOCUMENT_POSITION_PRECEDING,
    'و پس از راهنمای بخش‌ها می‌آید');
  ok(order.includes('mine')&&order.indexOf('mine')<order.indexOf('team'),'تیکت‌های من پیش از کارشناس‌ها');
  ok(p.doc.querySelector('#topics')===null&&p.doc.querySelector('#stiles')===null&&p.doc.querySelector('#grpChips')===null,
    'ردیف کاشی‌های موضوعی و صافی گروه برداشته شده');
  ok(p.doc.querySelector('#shead')===null&&p.doc.querySelector('#qres')===null&&p.doc.querySelector('#shContacts')===null,
    'باقی‌ماندهٔ طرح پیشین نمانده');
}

/* ── ۷) ورقهٔ راهنمای رسانه‌ای ── */
{
  console.log('\n── راهنمای تصویری و صوتی ──');
  const p=await load(makeStore());
  ok(p.all('#chapters [data-media]').length>=16,'از هر فصل یک ورقه باز می‌شود');
  p.clickEl(p.doc.querySelector('#ch-login .chhead'));
  await wait(40);
  p.click('#ch-login [data-media]');
  await wait(120);
  ok(p.openSheets().includes('shMedia')&&p.doc.querySelector('#scrim').classList.contains('on'),'راهنما در ورقهٔ خودش باز می‌شود');
  ok(p.txt('#mdBody').includes('گام‌به‌گام')&&p.all('#mdBody .tipit').length===3,'گام‌های همان بخش');
  ok(p.all('#mdBody .gcard .gthumb img').length===1,'هنر بخش در ورقه');
  const pl=p.doc.querySelector('#mdBody [data-playmock]');
  ok(pl!==null,'دکمهٔ پخش نمونه');
  p.clickEl(pl);
  ok(p.doc.querySelector('#mdBody .gthumb').dataset.play==='1','پخش روشن می‌شود');
  p.clickEl(pl);
  ok(p.doc.querySelector('#mdBody .gthumb').dataset.play==='0','و خاموش');
  const t0=p.txt('#mdBody .shtx b');
  p.click('#mdBody [data-gstep="1"]');
  await wait(60);
  ok(p.txt('#mdBody .shtx b')!==t0,'بخش پس می‌رود');
  p.click('#mdBody [data-gstep="-1"]');
  await wait(60);
  ok(p.txt('#mdBody .shtx b')===t0,'و بخش پیش برمی‌گردد');
  p.click('#mdBody [data-ticket]');
  await wait(150);
  ok(p.shown('#modal')&&p.openSheets().length===0,'از راهنما هم می‌شود تیکت زد');
  p.key('body','Escape');
  p.click('#ch-complain [data-media]');
  await wait(100);
  p.click('#scrim');
  ok(p.openSheets().length===0&&!p.shown('#modal'),'پرده همه را می‌بندد');
}

/* ── ۸) داده، سند و پیوند‌ها ── */
{
  console.log('\n── داده و سند ──');
  const p=await load(makeStore());
  const raw=fs.readFileSync(DIR+'data.js','utf8');
  const W={}; new Function('window','document',raw)(W,{});
  const S=W.NORA.SUPPORT;
  ok(S.sections.length===21&&S.grps.length===6,'بیست‌ویک بخش در شش گروه (همه + پنج)');
  ok(S.sections.every(s=>s.grp&&s.cover&&s.steps.length===3&&s.faq.length===6),'هر بخش: گروه، هنر، سه گام، شش پرسش');
  ok(S.sections.every(s=>s.time&&s.need.length>=1&&s.rel.length>=2),'هر بخش: مهلت، چیزهای لازم و بخش‌های وابسته');
  const keys=new Set(S.sections.map(x=>x.k));
  ok(S.sections.every(s=>s.rel.every(r=>keys.has(r))),'هر وابسته به بخشی هست که وجود دارد');
  ok(S.sections.every(s=>!s.faq.some(f=>f.length!==2)),'هر پرسش یک پاسخ دارد');
  ok(S.sections.every(s=>(s.media||[]).length>=1),'هر بخش راهنمای رسانه‌ای دارد');
  ok(S.sections.filter(s=>s.form).length===3,'سه فرم لینک‌شده');
  ok(S.sections.some(s=>s.k==='library')&&S.sections.some(s=>s.k==='exam')&&S.sections.some(s=>s.k==='live'),'بخش‌های تازه: کتابخانه، آزمون، پخش زنده');
  ok(S.sections.every(s=>!/—/.test(JSON.stringify(s))),'دش میان متن فارسی نیست');
  ok(/grps:\[/.test(raw)&&/tones:\{/.test(raw)&&/lead:\{/.test(raw)&&/sla:\[/.test(raw)&&/howto:\[/.test(raw),
    'گروه‌ها، رنگ‌ها، کارشناس لید و جدول‌ها همه در data.js');
  const posters=fs.readdirSync(DIR+'posters').filter(f=>f.endsWith('.svg'));
  ok(posters.length>=10,'پوسترها در پوشهٔ خودشان: '+posters.length);
  ok(S.sections.every(s=>posters.includes(s.cover)),'هر هنرِ فصل، پروندهٔ خودش را دارد');

  const html=fs.readFileSync(OPEN,'utf8');
  const ids=[...html.matchAll(/id="([^"]+)"/g)].map(m=>m[1]);
  ok(new Set(ids).size===ids.length,'شناسه‌های یکتا در صفحه');
  ok(!/[a-z-]+:[ ]*[^;{}]+;\s*}/.test('')&&!/class="(search|sup-hero)"/.test(html),'کلاس به‌جاماندهٔ طرح پیشین نیست');
  ok(html.includes('support.css?v=20')&&html.includes('support.js?v=20')&&html.includes('data.js?v=20'),'نسخهٔ دارایی‌ها تازه شده (v=20)');
  ok(html.includes('rel="canonical"')&&html.includes('og:title')&&html.includes('theme-color'),'سند و سرصفحهٔ اشتراک‌گذاری');
  ok(html.includes('rel="preload" as="image" href="posters/'),'پوستر نخستین پیش‌بار می‌شود');
  const css=fs.readFileSync(DIR+'support.css','utf8');
  ok((css.match(/\{/g)||[]).length===(css.match(/\}/g)||[]).length,'آکولادهای CSS جفت‌اند');
  ok(/\.mk\{/.test(css)&&/\.stp\{/.test(css)&&/\.gband\{/.test(css)&&/\.miss\{/.test(css),'طرح گام‌ها و نوار گروه و کارت تهی در CSS هست');
  ok(!/\.mpart \.bd\{/.test(css),'بدنهٔ قطعه‌های پاپ‌آپ کلاس جدا دارد');
  const js=fs.readFileSync(DIR+'support.js','utf8');
  ok(!/#stiles|#grpChips|#topics/.test(js),'کد به کاشی‌های موضوعی برنمی‌گردد');
  ok(/nora-support-tickets/.test(js)&&/nora-support-seeded/.test(js),'کلیدهای حافظه همان‌ها هستند');
  const sw=fs.readFileSync(DIR+'sw.js','utf8');
  ok(sw.includes("'support.html'")&&sw.includes("'support.css'")&&sw.includes("'support.js'"),'سرویس‌ورکر صفحهٔ پشتیبانی را پیش‌بار می‌کند');
  const man=fs.readFileSync(DIR+'manifest.webmanifest','utf8');
  ok(man.includes('support.html'),'میان‌بر پشتیبانی در manifest');
  const doc=fs.readFileSync(DIR+'support-arch.md','utf8');
  ok(doc.includes('گام')&&doc.includes('تیکت')&&doc.includes('کارشناس'),'سند معماری پشتیبانی به‌روز است');
}

console.log('\n'+(fail?'✗ '+fail+' رد، '+pass+' قبول':'✓ همه سبز: '+pass+' قبول'));
process.exit(fail?1:0);
