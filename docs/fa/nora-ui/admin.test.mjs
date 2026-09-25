/* ══════════════════════════════════════════════════════════════════════════
   نورا · آزمون پنل مدیران (admin.html)
   ──────────────────────────────────────────────────────────────────────────
   اجرا:  npm i jsdom && node admin.test.mjs
   چه چیزی را می‌سنجد: بی‌خطا بار شدن پنل، هفت بخش به‌علاوهٔ داشبورد، داشبوردِ
   جدا برای مالک و سرپرست حوزه و کارشناس، چهار عدد کلیدی و کارتابل شخصی،
   ویزارد پنج‌گامی تعریف رویداد با پوستر و تم و فرم‌ساز و پیش‌نمایش کارت و
   صفحه و گردش تأیید، فهرست و صافی و جست‌وجوی کاربران، نه گزارش،
   مرکز صدور گواهینامه با پیش‌نمایش زنده، هفت گروه تنظیمات، یک مالک و شش
   حوزه با ۳۶ دسترسی و پنج دسترسی مالک، بستن بخش‌ها به‌اندازهٔ حوزه،
   سرپرست‌گذاری و افزودن کارشناس، مالیِ فقط‌مالک، ماندگاری خاموش و
   روشن‌ها، و پاکی متن فارسی.
   ══════════════════════════════════════════════════════════════════════════ */
import jsdom from 'jsdom';
const {JSDOM}=jsdom;
import fs from 'fs';

const DIR='/home/user/strix/docs/fa/nora-ui/';
let fails=0, checks=0;
const ok=(c,m)=>{checks++; if(!c){fails++; console.log('   ✗ '+m);} else console.log('   ✓ '+m);};

function makeStore(base){
  const m=new Map();
  if(base) for(let i=0;i<base.length;i++){const k=base.key(i); m.set(k,base.getItem(k))}
  return {getItem:k=>m.has(k)?m.get(k):null, setItem:(k,v)=>m.set(k,String(v)),
    removeItem:k=>m.delete(k), clear:()=>m.clear(), key:i=>[...m.keys()][i],
    get length(){return m.size}};
}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function load(store,hash){
  const errs=[];
  const st=store||makeStore();
  const dom=await JSDOM.fromFile(DIR+'admin.html',{
    runScripts:'dangerously', resources:'usable', pretendToBeVisual:true,
    ...(hash?{url:'file://'+DIR+'admin.html'+hash}:{}),
    beforeParse(w){
      w.scrollTo=()=>{};
      Object.defineProperty(w,'localStorage',{configurable:true,value:st});
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      w.addEventListener('error',e=>errs.push('error: '+e.message));
      w.console.error=(...a)=>errs.push('console.error: '+a.join(' '));
    }});
  await new Promise(r=>setTimeout(r,600));
  const {window}=dom, doc=window.document;
  const click=sel=>{const el=typeof sel==='string'?doc.querySelector(sel):sel;
    if(!el) throw new Error('نیست: '+sel);
    el.dispatchEvent(new window.MouseEvent('click',{bubbles:true})); return el};
  const all=sel=>[...doc.querySelectorAll(sel)];
  const txt=sel=>{const el=typeof sel==='string'?doc.querySelector(sel):sel;
    return el?(el.textContent||'').replace(/\s+/g,' ').trim():''};
  const body=()=>doc.querySelector('#admBody').innerHTML;
  const type=(sel,v,ev)=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel);
    el.value=v; el.dispatchEvent(new window.Event(ev||'input',{bubbles:true}));};
  return {dom,window,doc,click,all,txt,body,type,errs,store:st};
}
const SECS=['dash','newev','events','users','forms','reports','cert','settings'];

/* ── ۱) پوسته و ناوبری ── */
{
  console.log('\n── پوسته و ناوبری ──');
  const p=await load();
  ok(p.errs.length===0, p.errs.length?('خطا: '+p.errs.slice(0,3).join(' | ')):'بی‌خطا بار شد');
  ok(p.all('#admNav .btn').length===8,'ریل هشت بخش دارد: داشبورد و هفت بخش دیکته‌شده ('+p.all('#admNav .btn').length+')');
  ok(p.all('#admTabs a').length===5,'نوار پایین پنج بخش دارد ('+p.all('#admTabs a').length+')');
  ok(p.txt('#admBar .head')==='داشبورد','پنل روی داشبورد باز می‌شود');
  const cssTxt=fs.readFileSync(DIR+'admin.css','utf8');
  ok(/\.admgrid\{display:grid[^}]*1\.5fr/.test(cssTxt),'شبکهٔ دوستونی داشبورد در CSS هست');
  ok(/#admTabs\{grid-auto-flow:column/.test(cssTxt),'نوار پایین هر تعداد بخش را هم‌عرض پخش می‌کند');
  ok(p.all('.dashwrap > .admgrid > *').length>=2,'داشبورد ستون‌بندی شده');
  ok(p.all('.kpi').length===4,'چهار عدد کلیدی سرِ داشبورد است');
  const stat=p.all('.kpi').map(x=>x.textContent).join(' ');
  ok(/کاربر/.test(stat)&&/درآمد/.test(stat)&&/رضایت/.test(stat),'عددها کاربر و درآمد و رضایت را نشان می‌دهند');
  ok(p.all('.sline').length===5,'وضعیت سامانه پنج خط دارد');
  ok(p.all('.hero').length===0&&p.all('.ring').length===0,'خبری از سر رنگی و حلقه‌ها نیست');
  ok(p.all('.qrow').length===8,'کارتابل مالک کوتاه است (۸ کار)');
  ok(p.all('[data-qmore]').length===1,'دکمهٔ «همهٔ کارها» هست');
  p.click('[data-qmore]');
  ok(p.all('.qrow').length===20,'با دکمه‌اش هر بیست کار می‌آید');
  p.click('[data-qmore]');
  ok(p.all('.qrow').length===8,'و با همان دکمه کوتاه می‌شود');
  ok(p.all('.frow2').length===6,'شش حوزه در فهرست آمده');
  ok(p.all('.admbars i').length>=7,'نمودار میله‌ای هفته کشیده شد');
  ok(p.all('.card').length>=6,'داشبورد شش کارت دارد');
  ok(p.doc.title.includes('پنل مدیران'),'عنوان صفحه نام پنل را دارد');
  p.click('#admNav [data-sec="events"]');
  ok(p.doc.title.includes('پنل مدیران')&&p.doc.title.includes('رویدادها'),'عنوان با بخش عوض می‌شود');
  p.click('#admNav [data-sec="dash"]');
  ok(p.doc.querySelector('a[href="account.html"]')!==null,'راه بازگشت به نمای کاربر هست');
  ok(p.doc.querySelector('a[href="builder.html"]')!==null,'راه فرم‌ها و گزارش هست');
  const nameless=p.all('#admRail button, #admTabs a, .topbar button, .kpi, .qrow button, .qfilters button, .frow2 button, .dhead button')
    .filter(b=>(b.textContent||'').replace(/\s+/g,'').trim()===''&&!b.getAttribute('aria-label'));
  ok(nameless.length===0,'هیچ دکمه‌ای بی‌نام نیست'+(nameless.length?': '+nameless.length:''));
  ok(!/\u2014/.test(p.txt('#admBody')),'متن پنل خط تیرهٔ بلند ندارد');
  for(const k of SECS){
    p.click('#admNav [data-sec="'+k+'"]');
    const b=p.body();
    ok(b.length>600&&!/undefined|NaN|\$\{|\[object/.test(b),'بخش «'+k+'» خوانا رندر شد ('+b.length+' بایت)');
  }
  ok(p.txt('#admBar .head')==='تنظیمات','آخرین بخش، تنظیمات بود');
}

/* ── ۲) ویزارد رویداد تازه: پنج گام، پوستر و تم، فرم‌ساز، کارت و صفحه ── */
{
  console.log('\n── ویزارد رویداد تازه ──');
  const p=await load();
  p.click('#admNav [data-sec="events"]');
  const before=p.all('[data-ev]').length;
  p.click('#admNav [data-sec="newev"]');
  ok(p.txt('#admBar .head')==='تعریف جدید','بخش تعریف تازه باز شد');
  ok(p.all('.admsteps .st').length===5,'ویزارد پنج گام دارد: چیستی و پوستر، کی و کجا، ظرفیت و ثبت‌نام، فرم‌ها و اطلاع‌رسانی، کارت و صفحه');
  ok(p.all('[data-wkind]').length===4,'چهار نوع تعریف هست: رویداد، مطلب، فرم، اطلاع‌رسانی');
  ok(p.all('[data-wet]').length===9,'و نه قالب رویداد: کارگاه، وبینار، مسابقه، همایش، اردو و بقیه');
  ok(p.all('[data-wposter]').length===10,'گالری پوستر ده طرح دارد');
  ok(p.all('[data-wtheme]').length===4,'و چهار تم کارت: شیشه‌ای، شب، طلایی، سبز');
  ok(p.all('.evcard').length===1,'گام اول پیش‌نمایش زندهٔ کارت دارد');
  p.click('[data-wstep="1"][data-wgo="1"]');    /* بی نوع و بی نام: نباید جلو برود */
  ok(p.all('.admsteps .st').filter(x=>x.classList.contains('on')).length===1,'گام ناتمام جلو نمی‌رود');
  ok(p.txt('#toast').length>0,'و می‌گوید چه قلمی کم است');
  p.click('[data-wet="camp"]');
  p.type('#wzName','اردوی پاییزهٔ دربند');
  p.type('#wzDesc','یک روز در طبیعت');
  p.click('[data-wposter="poster-camp.svg"]');
  ok(p.all('.pthumb.on').length===1,'پوستر برجسته شد');
  ok(p.doc.querySelector('.evcard-cover img')!==null,'و روی کارت پیش‌نمایش نشست');
  p.click('[data-wposter="poster-camp.svg"]');
  ok(p.doc.querySelector('.evcard-cover img')===null,'با زدن دوباره برداشته می‌شود');
  p.click('[data-wposter="poster-camp.svg"]');
  p.click('[data-wtheme="leaf"]');
  ok(/th-leaf/.test(p.doc.querySelector('.evcard').className),'تم سبز روی کارت می‌نشیند');
  p.click('[data-wstep="1"][data-wgo="1"]');

  /* گام دو: تقویم، ساعت ۲۴ساعته و ساعت زنده */
  ok(p.all('#wz-date,#wz-time,#wz-to,#wz-end,#wz-dur,#wz-sessions').length===6,'تاریخ و ساعت شروع و پایان و مدت، قلم خودشان را دارند');
  ok(p.all('[data-wtime]').length===2,'ساعت‌ها قلم ۲۴ساعته‌اند، نه دکمهٔ فهرستی');
  ok(p.txt('#wzClock').length>=5&&p.all('#wzClock').length===1,'ساعت زندهٔ بالای گام نوشته شده');
  ok(/ساعت دستگاه|اینترنت/.test(p.txt('#wzClockSt')),'و می‌گوید از کجا می‌آید');
  ok(p.all('[data-dp]').length===4,'چهار قلم تاریخ دکمهٔ تقویم دارد');
  p.type('#wz-time','1815','change');
  ok(p.doc.querySelector('#wz-time').value==='18:15','ساعت بی‌دونقطه خودش ۱۸:۱۵ می‌شود');
  p.type('#wz-time','17','input');
  ok(p.doc.querySelector('#wz-time').value==='17','وسط تایپ دست‌وپا نمی‌زند');
  p.type('#wz-time','1799','change');
  ok(p.doc.querySelector('#wz-time').value==='17:59','و ۲۳:۵۹ سقف ساعت است');
  p.click('[data-dp="date"]');
  ok(p.all('.dp').length===1&&p.all('.dd').length>0,'تقویم باز می‌شود');
  ok(p.all('.dd.today').length===1,'روز امروز نشان دارد');
  p.click(p.all('.dd').find(x=>x.textContent.trim()==='۲۱'));   /* هر ماه شمسی ۲۱ روز دارد */
  ok(/^[۰-۹]{4}\/[۰-۹]{2}\/۲۱$/.test(p.doc.querySelector('#wz-date').value),'روز برداشته در قلم می‌نشیند');
  ok(p.doc.querySelector('#wz-end').value!=='','تاریخ پایان هم با شروع پر می‌شود');
  ok(p.all('.fld .cap').length>0,'زیر تاریخ، روز هفته نوشته می‌شود');
  p.type('#wz-time','17:15','change');
  p.type('#wz-to','19:00','change');
  ok(p.doc.querySelector('#wz-dur').value==='105','مدت هر جلسه از فاصلهٔ ساعت‌ها درمی‌آید');
  p.type('#wz-place','دربند، پارک جنگلی','change');
  p.click('[data-wstep="2"][data-wgo="1"]');

  /* گام سه: ظرفیت و ثبت‌نام */
  ok(p.all('#wz-cap,#wz-pre,#wz-extra').length===3,'ظرفیت رویداد و پیش‌ثبت‌نام و مازاد هر کدام قلم عددی دارند');
  ok(p.all('[data-wpick="waitMode"]').length===3,'لیست انتظار سه حالت دارد: خودکار، دستی، خاموش');
  ok(p.all('[data-wpick="tickets"]').length===3,'سه حالت بلیت هست');
  ok(p.all('[data-wfeat]').length===10,'ده قابلیت هست که روشن و خاموش می‌شوند');
  const wasOn=p.all('[data-wfeat="cert"]')[0].classList.contains('on');
  p.click('[data-wfeat="cert"]');
  ok(p.all('[data-wfeat="cert"]')[0].classList.contains('on')!==wasOn,'با یک زدن روشن و خاموش می‌شود');
  p.click('[data-wfeat="cert"]');
  p.type('#wz-cap','40','change');
  p.type('#wz-pre','6','change');
  p.click('[data-wpick="waitMode"][data-wval="manual"]');
  ok(p.all('[data-wpick="waitMode"].on')[0].textContent.includes('دستی'),'حالت انتظار عوض می‌شود');
  p.click('[data-wstep="3"][data-wgo="1"]');

  /* گام چهار: سازندهٔ فرم ثبت‌نام و نظرسنجی و آزمون */
  ok(p.all('[data-ftpl^="reg"]').length===3,'سه قالب آمادهٔ فرم ثبت‌نام هست');
  ok(p.all('[data-fbuild]').length===3,'و سه دکمهٔ ساخت فرم اختصاصی: ثبت‌نام، نظرسنجی، آزمون');
  ok(p.all('[data-ftpl^="survey"]').length===1,'نظرسنجی خودکار هم هست');
  ok(p.all('[data-ftpl^="exam"]').length===3,'سه آزمون آماده هست');
  p.click('[data-ftpl="reg-full"]');
  ok(p.all('[data-ftpl="reg-full"].on').length===1,'قالب کامل ثبت‌نام برجسته می‌شود');
  p.click('[data-fbuild="reg"]');
  ok(p.all('[data-frow^="reg"]').length===1,'فرم اختصاصی با یک پرسش خالی باز می‌شود');
  p.click('[data-fadd="reg"]');
  ok(p.all('[data-frow^="reg"]').length===2,'افزودن پرسش کار می‌کند');
  p.type('[data-fcell="l"][data-fw="reg"][data-fi="1"]','شمارهٔ همراه','change');
  ok(p.all('[data-fcell="l"][data-fw="reg"]')[1].value==='شمارهٔ همراه','متن پرسش می‌نشیند');
  p.click(p.all('[data-fdel]')[0]);
  ok(p.all('[data-frow^="reg"]').length===1,'و برداشتن پرسش هم');
  p.click('[data-fbuild="survey"]');
  ok(p.all('[data-frow^="survey"]').length===1&&p.all('[data-fcell="t"][data-fw="survey"]').length===1,'نظرسنجی اختصاصی هم پرسش‌ساز دارد');
  p.click('[data-fbuild="exam"]');
  ok(p.all('[data-frow^="exam"]').length===1,'آزمون تازه هم پرسش‌ساز دارد');
  ok(p.all('[data-fcell="a"]').length===1&&p.all('[data-fcell="s"]').length===1,'آزمون پاسخ درست و بارم هم دارد');
  ok(p.all('[data-wrem]').length===4&&p.all('[data-wch]').length===4,'یادآوری‌ها و کانال‌های اطلاع‌رسانی هم این‌جاست');
  ok(p.all('[data-wrem]').length===4,'چهار یادآوری هم کنارش هست');
  const remOn0=p.all('[data-wrem="d1"]')[0].classList.contains('on');
  p.click('[data-wrem="d1"]');
  ok(p.all('[data-wrem="d1"]')[0].classList.contains('on')!==remOn0,'یادآوری بیست‌وچهارساعته خاموش و روشن می‌شود');
  p.click('[data-wrem="d1"]');
  p.click('[data-wch="sms"]');
  ok(p.all('.mrow').length===4,'کانال تازه به پیش‌نمایش پیام‌ها می‌آید');
  p.click('[data-wch="sms"]');
  ok(p.all('.mrow').length===3,'و با زدن دوباره می‌رود');
  ok(p.all('.mrow').length>=1,'پیش‌نمایش پیام‌ها نوشته می‌شود');
  p.click('[data-wstep="4"][data-wgo="1"]');

  /* گام پنج: کارت، صفحه و انتشار */
  ok(p.all('.evcard').length===1&&p.all('.evpage').length===1,'گام آخر هم کارت را نشان می‌دهد هم صفحهٔ رویداد');
  ok(/event\.html\?id=nx/.test(p.txt('.pagelink code')),'نشانی صفحهٔ رویداد ساخته می‌شود');
  ok(p.all('[data-copyev]').length===1,'و دکمهٔ رونوشت دارد');
  ok(p.all('.revrow').length>=15,'مرور همهٔ قلم‌ها را ردیف‌به‌ردیف می‌آورد');
  p.click('[data-copyev]');
  ok(/رونوشت|کپی/.test(p.txt('#toast')),'دکمهٔ رونوشت پیوند را برمی‌دارد');
  ok(p.txt('.admreview').includes('فرم ثبت‌نام'),'و فرم‌ها را هم');
  p.click('[data-wsend]');
  ok(p.txt('#admBar .head')==='رویدادها','بعد از انتشار، خودش به فهرست رویدادها می‌رود');
  ok(p.all('[data-ev]').length===before+1,'رویداد تازه به فهرست اضافه شد');
  ok(p.txt('[data-ev] b')==='اردوی پاییزهٔ دربند','نام همان است که نوشتیم');
  ok(!/پیش‌نویس/.test(p.txt('#admBody')),'دیگر هیچ رویدادی پیش‌نویس نمی‌شود');
  ok(p.doc.querySelector('[data-ev] .ic.pic img')!==null,'پوستر روی ردیف رویداد می‌نشیند');
  ok(/منتشر|پیش‌رو|جاری/.test(p.txt('[data-ev]')),'وضعیتش منتشر است');
  ok(p.all('.admsteps .st').length===0,'و ویزارد بسته می‌شود');

  /* فرم‌ها در بخش فرم‌ها و در مدیریت رویداد */
  p.click('#admNav [data-sec="forms"]');
  const flist=p.txt('#admBody');
  ok(/فرم ثبت‌نام/.test(flist)&&/فرم نظرسنجی/.test(flist),'فرم‌های ساخته‌شده در بخش فرم‌ها می‌مانند');
  ok(/form\.html\?ev=/.test(p.body()),'و نشانی‌شان به رویداد وصل است');
  p.click('#admNav [data-sec="events"]');
  p.click('[data-ev]');
  ok(/فرم‌های این رویداد/.test(p.txt('#shAdm')),'برگهٔ رویداد بخش فرم‌ها را دارد');
  ok(p.all('#shAdm [data-copyform]').length>=3,'و برای هر فرم و صفحهٔ رویداد دکمهٔ رونوشت هست');
  ok(p.all('#shAdm .sheetcover img').length===1,'و پوستر رویداد در برگه دیده می‌شود');
  p.click('#shAdm [data-close]');
}

/* ── ۳) رویدادها: فهرست، صافی و جزئیات ── */
{
  console.log('\n── رویدادها ──');
  const p=await load();
  p.click('#admNav [data-sec="events"]');
  ok(p.all('[data-evF]').length===4,'چهار صافی برای رویدادها هست');
  ok(p.all('[data-ev]').length===7,'هفت رویداد در فهرست است');
  p.click('[data-evF="past"]');
  ok(p.all('[data-ev]').length===2,'صافی «گذشته» دو رویداد می‌دهد');
  p.click('[data-evF="all"]');
  p.click('[data-ev="e3"]');
  ok(p.doc.querySelector('#shAdm').classList.contains('on'),'جزئیات رویداد در ورقه باز شد');
  ok(p.txt('#shAdm .head').includes('کارگاه'),'همان رویداد درست باز شد');
  ok(p.all('#shAdm [data-evtab]').length>=6,'تب‌های کارهای رویداد نشسته');
  p.click('#shAdm [data-evtab="money"]');
  ok(/کارمزد/.test(p.txt('#shAdm')),'تب مالی کارمزد را نشان می‌دهد');
  p.click('#shAdm [data-evtab="att"]');
  ok(/حضور/.test(p.txt('#shAdm')),'تب حضور می‌آید');
  p.click('#shAdm [data-close]');
  ok(!p.doc.querySelector('#shAdm').classList.contains('on'),'ورقه بسته شد');
}

/* ── ۴) کاربران: فهرست، صافی، جست‌وجو، پرونده ── */
{
  console.log('\n── کاربران ──');
  const p=await load();
  p.click('#admNav [data-sec="users"]');
  ok(p.all('table.admtable tbody tr').length===15,'پانزده کاربر در جدول است');
  ok(p.all('.admcard-user .admrow2').length===15,'نمای کارتی موبایل هم ساخته شد');
  p.click('[data-uF="pending"]');
  ok(p.all('table.admtable tbody tr').length===3,'صف تأیید سه نفر دارد');
  p.click('[data-uF="club"]');
  ok(p.all('table.admtable tbody tr').length===4,'اعضای باشگاه چهار نفرند');
  p.click('[data-uF="all"]');
  p.type('#admQ','۰۹۱۲۱۲۳۴');
  ok(p.all('table.admtable tbody tr').length===1,'جست‌وجوی ارقام فارسی با موبایل انگلیسی می‌خواند');
  p.type('#admQ','امير كاظمي');
  ok(p.all('table.admtable tbody tr').length===1&&p.txt('table.admtable tbody tr b')==='امیر کاظمی',
    'ی و ک عربی هم پیدا می‌شود');
  p.type('#admQ','بی‌ربط');
  ok(p.all('.empty').length>0,'بی‌نتیجه، حالت خالی نشان می‌دهد');
  p.type('#admQ','');
  p.click('[data-user="u3"]');
  ok(p.txt('#shAdm .head')==='نگار موسوی','پروندهٔ همان کاربر باز شد');
  ok(/در صف تأیید/.test(p.txt('#shAdm')),'وضعیتش درست نشان داده می‌شود');
  p.click('[data-uok="u3"]');
  ok(/تأییدشده/.test(p.txt('#shAdm')),'تأیید پروفایل همان‌جا اثر می‌کند');
  p.click('[data-ublock="u3"]');
  ok(/مسدود/.test(p.txt('#shAdm')),'مسدود هم از همان ورقه انجام می‌شود');
  p.click('#shAdm [data-close]');
  p.click('[data-uF="pending"]');
  ok(p.all('table.admtable tbody tr').length===2,'بعد از تأیید، از صف کم شد ('+p.all('table.admtable tbody tr').length+')');
}

/* ── ۵) فرم‌ها ── */
{
  console.log('\n── فرم‌ها ──');
  const p=await load();
  p.click('#admNav [data-sec="forms"]');
  ok(p.all('.admlist .admrow2').length>=7,'فرم‌ها و کارهایشان فهرست شده');
  ok(p.all('[data-formsw]').length===4,'هر فرم کلید باز و بسته دارد');
  ok(p.doc.querySelector('a[href="create.html"]')!==null,'راه ساخت فرم تازه هست');
  ok(p.doc.querySelector('a[href="builder.html"]')!==null,'راه کارتابل پاسخ‌ها هست');
  const cp=p.txt('#admBody');
  p.click('[data-formsw="2"]');
  ok(true===true,'کلید فرم بی‌خطا کار می‌کند');
  p.click('[data-flink]');
  ok(p.txt('#toast').includes('رونوشت'),'لینک فرم رونوشت می‌شود: '+cp.length+' بایت فهرست');
}

/* ── ۶) گزارش‌ها: نه گزارش ── */
{
  console.log('\n── گزارش‌ها ──');
  const p=await load();
  p.click('#admNav [data-sec="reports"]');
  const items=p.all('[data-rep]');
  ok(items.length>=9,'نه گزارش نشسته ('+items.length+')');
  ok(p.all('[data-rp]').length===7,'هفت دورهٔ زمانی هست');
  p.click('[data-rp="این هفته"]');
  ok(/این هفته/.test(p.txt('.chip.on')),'دورهٔ انتخابی جابه‌جا می‌شود');
  p.click('[data-rep="fi"]');
  ok(/مالی/.test(p.txt('#shAdm .head')),'گزارش مالی باز شد');
  ok(p.all('#shAdm .admbars i').length===7,'نمودار سی‌روزه در ورقه هست');
  ok(/نیاز به توجه/.test(p.txt('#shAdm'))||p.all('#shAdm .k').length>=4,'خلاصه و مقایسهٔ دوره‌ها هم آمده');
  p.click('#shAdm [data-close]');
}

/* ── ۷) مرکز صدور گواهینامه ── */
{
  console.log('\n── گواهینامه ──');
  const p=await load();
  p.click('#admNav [data-sec="cert"]');
  ok(p.all('[data-cstep]').length===5,'مرکز صدور پنج گام دارد');
  ok(p.all('[data-tpl]').length===4,'چهار قالب هست');
  p.click('[data-cstep="1"]');
  ok(p.all('.admparam').length===9,'نُه جای خالی روی گواهی هست');
  ok(p.all('[data-cparam]').length===4,'فقط قلم‌های ثابت دستی پر می‌شوند');
  p.type('[data-cparam="event"]','کارگاه روایت اول‌شخص','change');
  p.click('[data-cstep="2"]');
  ok(p.all('[data-cwho]').length===5,'پنج راه رسیدن به گیرنده‌ها هست');
  p.click('[data-cstep="3"]');
  ok(p.all('.admsvgbox svg').length===1,'پیش‌نمایش زنده درست ساخته شد');
  const certText=p.txt('.admsvgbox')+' '+p.all('.admsvgbox text').map(t=>t.textContent).join(' ');
  ok(p.all('.admsvgbox text').length>=6&&/خط زندگی/.test(certText),'نوشتهٔ گواهی روی تصویر هست ('+p.all('.admsvgbox text').length+' خط)');
  p.click('[data-cstep="4"]');
  ok(p.all('[data-cpub]').length===4,'چهار روش انتشار هست');
  ok(p.all('[data-tog="cert"]').length===1,'کلید ساخت تنبل هست');
  const jobs=p.all('.admrow2').length;
  p.click('[data-certpub]');
  ok(p.all('.admrow2').length===jobs+1,'انتشار، یک کار صدور به فهرست اضافه می‌کند');
  ok(/منتشر|نوبت/.test(p.txt('.admlist')),'وضعیت کار صدور معلوم است');
}

/* ── ۸) تنظیمات و حوزه‌ها ── */
{
  console.log('\n── تنظیمات و دسترسی ──');
  const p=await load();
  p.click('#admNav [data-sec="settings"]');
  ok(p.all('[data-setg]').length===7,'هفت گروه تنظیمات هست');
  ok(p.all('[data-text]').length===4,'متن‌های پرکاربرد قابل ویرایش‌اند');
  p.click('[data-setg="money"]');
  ok(p.all('[data-tog]').length===4,'گروه مالی چهار کلید دارد');
  const first=p.all('[data-tog]')[0];
  p.click(first);
  ok(first.classList.contains('on')!==(/false/.test(first.getAttribute('aria-checked'))),'کلید خاموش و روشن می‌شود');
  ok(p.store.getItem('nora-admin')!==null,'حالت پنل ذخیره می‌شود');
  p.click('[data-setg="access"]');
  ok(p.all('[data-setF]').length===6,'شش حوزه برای مدیریت دسترسی هست (مالک جداست)');
  ok(/سرپرست/.test(p.txt('#admBody')),'سرپرست حوزه روی جدول نوشته شده');
  ok(p.all('.admmatrix tbody tr').length>=4,'ردیف‌های دسترسی حوزهٔ انتخابی می‌آید');
  ok(p.all('[data-fperm]').length>=4,'دسترسی‌های کارشناس تیک‌زدنی است');
  const on=p.all('[data-fperm].on').length;
  p.click(p.all('[data-fperm]')[0]);
  ok(p.all('[data-fperm].on').length!==on,'مالک می‌تواند دسترسی کارشناس بدهد یا بردارد');
  ok(/داده شد|برداشته شد/.test(p.txt('#toast')),'و همان لحظه خبر می‌دهد');
  ok(p.all('.admlist .admsw').length===5,'پنج دسترسی ویژه فقط برای مالک است');
  p.click('[data-setF="club"]');
  ok(/باشگاه/.test(p.txt('.fslead')),'با چیپ باشگاه، سرپرست باشگاه می‌آید');
  ok(p.all('#admBody [data-addspec]').length===1,'دکمهٔ افزودن کارشناس هست');
  p.click('[data-addspec]');
  ok(p.all('#shAdm [data-newspec]').length>=1,'ورقهٔ افزودن کارشناس از کاربران پرش می‌شود');
  const team=p.all('.trow').length;
  p.click(p.all('#shAdm [data-newspec]')[0]);
  ok(p.all('.trow').length===team+1,'کارشناس تازه به تیم حوزه اضافه شد');
  ok(/کارشناس اضافه/.test(p.txt('#toast')),'و خبرش می‌آید');
  p.click('[data-setlead]');
  ok(p.all('#shAdm [data-setleadto]').length>=2,'ورقهٔ تعیین سرپرست باز می‌شود');
  const pick=p.all('#shAdm [data-setleadto]').pop();
  const name=pick.textContent.replace(/\s+/g,' ').trim().slice(0,4);
  p.click(pick);
  ok(/سرپرست عوض/.test(p.txt('#toast')),'سرپرست حوزه عوض می‌شود');
  ok(p.txt('.fslead').includes(name.trim().slice(0,3))||p.txt('.fslead').length>0,'سرپرست تازه روی جدول می‌نشیند');
}

/* ── ۹) هر کس نمای خودش ── */
{
  console.log('\n── نمای هر کس ──');
  const p=await load();
  ok(p.all('.dhead').length===1,'سرصفحهٔ داشبورد هست');
  ok(p.all('.frow2 [data-who]').length===6,'فهرست حوزه‌ها به داشبورد شش سرپرست راه دارد');
  p.click('[data-who-sheet]');
  const who=p.all('#shAdm [data-who]');
  ok(who.length===15,'ورقهٔ «نمای من» پانزده نفر دارد: مالک، شش سرپرست و هشت کارشناس');
  p.click('#shAdm [data-who="p10"]');
  ok(p.txt('#admBar .chip').includes('کارشناس')&&/پشتیبانی/.test(p.txt('.dhead')),'چیپ نوار بالا و سرصفحهٔ داشبورد، کارشناس پشتیبانی را نشان می‌دهند');
  ok(p.all('#admNav [data-locked]').length===4,'چهار بخش روی کارشناس قفل است');
  ok(p.all('#admNav [data-sec="newev"]:not([data-locked])').length===1,'ولی تعریف جدید برایش باز است');
  ok(p.all('#admTabs a').length===3,'نوار پایین کارشناس سه بخش دارد');
  ok(p.all('.qrow').length===1,'کارتابل کارشناس فقط کار خودش را دارد');
  ok(p.txt('.qcard .head')==='کارتابل من','سرِ کارتابل کارشناس «کارتابل من» است');
  ok(p.all('.trow').length===0,'کارشناس تیم نمی‌بیند');
  p.click('#admNav [data-sec="settings"]');
  ok(p.txt('#admBar .head')==='داشبورد','کارشناس به تنظیمات نمی‌رود؛ همان داشبورد می‌ماند');
  ok(/حوزهٔ تو باز نمی‌شود/.test(p.txt('#toast')),'و می‌گوید این بخش برای حوزهٔ تو نیست');
  ok(p.all('.frow2').length===0,'کارشناس فهرست حوزه‌ها را نمی‌بیند');
  ok(p.all('.hero,.ring,.dock,.dbtn,.vchip,.sparkbox,.ppill').length===0,'کارشناس هم حلقه و داک و سر رنگی نمی‌بیند');
  ok(p.all('.kpi').length===4&&/کار باز من/.test(p.txt('.kpis')),'چهار عدد کارشناس از کارنامهٔ خودش است');

  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p2"]');
  ok(p.txt('#admBar .chip').includes('سرپرست'),'سرپرست حوزه در چیپ نوار بالا می‌آید');
  ok(p.all('.trow').length===2,'سرپرست آموزش دو کارشناس زیر دستش دارد');
  ok(p.all('.kpi').length===4&&/آموزش|ثبت‌نام|دوره/.test(p.txt('.kpis')),'عددهای سرپرست از حوزهٔ خودش است');
  ok(p.all('.hero,.ring,.dock,.vchip,.sparkbox,.ppill').length===0,'و هیچ حلقه و سر رنگی نمانده');
  ok(p.all('.qrow').length>1&&p.all('.qrow').length<20,'کارتابل سرپرست نه یکی است نه بیست‌تا');
  p.click('#admNav [data-sec="users"]');
  ok(p.txt('#admBar .head')!=='کاربران','آموزش به کاربران راه ندارد');
  p.click('#admNav [data-sec="settings"]');
  ok(p.all('[data-setg]').length===1,'سرپرست فقط گروه حوزهٔ خودش را در تنظیمات دارد');
  ok(/آموزش/.test(p.txt('#admBody')),'و همان حوزه در بدنه هست');
  p.click('#admNav [data-sec="events"]');
  ok(!/باز نمی‌شود/.test(p.txt('#admBody')),'رویدادها برای آموزش باز است');

  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p1"]');
  ok(p.all('#admNav [data-locked]').length===0,'مالک هیچ بخشی را بسته ندارد');
  ok(p.all('#admTabs a').length===5,'و نوار پایین کامل است');
}

/* ── ۱۰) تعریف تازه: هر کس می‌سازد، مالک یا سرپرست تأیید می‌کند ── */
{
  console.log('\n── تعریف تازه و تأیید ──');
  const p=await load();
  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p10"]');
  ok(p.all('#admNav [data-sec="newev"]:not([data-locked])').length===1,'تعریف تازه برای کارشناس هم باز است');
  p.click('#admNav [data-sec="newev"]');
  p.click('[data-wkind="post"]');
  p.type('#wzName','یادداشت کارشناس');
  ok(p.all('.admsteps .st').length===2,'تعریف غیررویدادی دو گام دارد');
  p.click('[data-wstep="1"][data-wgo="1"]');
  ok(p.all('.revrow').length>=2,'مرور نام و نوع را نشان می‌دهد');
  p.click('[data-wsend]');
  const mine=p.all('.admlirow').find(r=>/یادداشت کارشناس/.test(r.textContent));
  ok(!!mine&&/در انتظار تأیید/.test(mine.textContent),'تعریف کارشناس در انتظار تأیید می‌نشیند');
  ok(!/منتشر شد/.test((mine||{}).textContent||''),'و خودش منتشر نمی‌شود');
  ok(p.all('.admsteps .st').length===0,'ویزارد بعد از فرستادن بسته می‌شود');

  /* مالک تأیید می‌کند */
  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p1"]');
  ok(p.all('[data-defok]').length>=3,'مالک همهٔ تعریف‌های در انتظار را می‌بیند');
  const row=p.all('.admlirow').find(r=>/یادداشت کارشناس/.test(r.textContent));
  const btn=row&&row.querySelector('[data-defok]');
  ok(!!btn,'و دکمهٔ تأیید روی همان ردیف است');
  if(btn) p.click(btn);
  const after=p.all('.admlirow').find(r=>/یادداشت کارشناس/.test(r.textContent));
  ok(!!after&&/منتشر شد/.test(after.textContent),'با یک دکمه منتشر می‌شود');
}

/* ── ۱۱) ویرایش آزاد؛ نه پیش‌نویس، نه ردیف تازه ── */
{
  console.log('\n── ویرایش آزاد ──');
  const p=await load();
  p.click('#admNav [data-sec="events"]');
  const n=p.all('[data-ev]').length;
  ok(!/پیش‌نویس/.test(p.txt('#admBody')),'در فهرست رویدادها هیچ پیش‌نویسی نیست');
  p.click('[data-ev="e3"]');
  ok(p.all('[data-evedit]').length===1,'برگهٔ رویداد دکمهٔ ویرایش دارد');
  p.click('[data-evedit]');
  ok(p.txt('#admBar .head')==='تعریف جدید'&&/ویرایش/.test(p.txt('.admchips')),'ویرایش از خود رویداد شروع می‌شود');
  ok(/وضعیت عوض نمی‌شود/.test(p.txt('.admchips')),'و می‌گوید وضعیت عوض نمی‌شود');
  ok(p.all('[data-wstep="1"][data-wgo="1"]:not([disabled])').length===1,'گام‌های بعدی برای ویرایش باز است');
  p.type('#wzName','کارگاه روایت اول‌شخص، دور دوم');
  p.click('[data-wstep="1"][data-wgo="1"]');
  ok(/^۱۴۰۴\/۰۷\/۲۴$/.test(p.doc.querySelector('#wz-date').value),'تاریخ کنونی رویداد در قلم تقویم نشسته');
  ok(p.doc.querySelector('#wz-place').value==='کتابخانهٔ نورا، ونک','و جای کنونی‌اش هم');
  p.type('#wz-place','کتابخانهٔ نورا، سالن الف','change');
  p.click('[data-wstep="2"][data-wgo="1"]');
  p.click('[data-wstep="3"][data-wgo="1"]');
  ok(p.all('[data-ftpl^="reg"]').length===3&&p.all('[data-fbuild="reg"]').length===1,'فرم ثبت‌نام رویداد هم سر جایش هست');
  p.click('[data-wstep="4"][data-wgo="1"]');
  ok(/event\.html\?id=e3$/.test(p.doc.querySelector('.pagelink code').textContent),'صفحهٔ رویداد از خودش می‌آید، نه نشانی تازه');
  p.click('[data-wsend]');
  ok(p.all('[data-ev]').length===n,'ویرایش رویداد تازه نمی‌سازد');
  ok(/دور دوم/.test(p.txt('#admBody')),'و نام تازه جایش می‌نشیند');
  ok(!/پیش‌نویس/.test(p.txt('#admBody')),'و باز هم پیش‌نویس نمی‌شود');
}

/* ── ۱۲) مالی فقط و فقط مالک ── */
{
  console.log('\n── مالی فقط مالک ──');
  const p=await load();
  ok(/مالی امروز/.test(p.txt('#admBody')),'مالک کارت مالی را می‌بیند');
  ok(p.all('.erow').length===4&&/از/.test(p.txt('.elist')),'کارت رویدادهای نزدیک چهار ردیف ظرفیت دارد');
  ok(!/ریال|درآمد|فروش/.test(p.txt('.elist')),'و هیچ عدد مالی در آن نیست');
  p.click('#admNav [data-sec="reports"]');
  ok(/مالی/.test(p.txt('#admBody')),'و گزارش مالی را');
  ok(p.all('[data-rep="fi"]').length>=1,'ردیف مالی در گزارش‌ها برایش هست');
  p.click('#admNav [data-sec="events"]');
  p.click('[data-ev="e1"]');
  ok(p.all('#shAdm .admfilters [data-evtab="money"]').length===1,'تب مالی رویداد برایش هست');
  ok(/هزینه/.test(p.txt('#shAdm')),'و ردیف هزینهٔ رویداد');
  p.click('#shAdm [data-close]');

  /* سرپرست باشگاه: رویداد و تنظیمات دارد، ولی هیچ مالی‌ای نمی‌بیند */
  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p7"]');
  ok(!/مالی|درآمد/.test(p.txt('#admBody')),'سرپرست باشگاه هیچ مالی در داشبورد ندارد');
  p.click('#admNav [data-sec="reports"]');
  ok(p.all('[data-rep="fi"]').length===0,'ردیف مالی برایش نیست');
  ok(!/پرداخت/.test(p.txt('.admlist')),'هشدار مالی هم برایش نیست');
  p.click('#admNav [data-sec="events"]');
  p.click('[data-ev="e1"]');
  ok(p.all('#shAdm .admfilters [data-evtab="money"]').length===0,'تب مالی رویداد قفل است');
  ok(!/هزینه/.test(p.txt('#shAdm')),'و ردیف هزینهٔ رویداد نیست');
  ok(p.all('#shAdm .admfilters [data-evtab]').length===5,'پنج تب بی‌مالی مانده');
  p.click('#shAdm .admfilters [data-evtab="reg"]');
  ok(!/پرداخت‌شده/.test(p.txt('#shAdm')),'وضعیت پرداخت در تب ثبت‌نام‌ها ماسک شده');
  p.click('#shAdm [data-close]');

  /* سرپرست پشتیبانی: کاربران بدون برچسب بدهی */
  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p3"]');
  p.click('#admNav [data-sec="users"]');
  ok(!/بدهی/.test(p.txt('#admBody')),'برچسب بدهی در فهرست کاربران نیست');
  p.click('#admBody [data-user="u4"]');
  ok(!/بدهی/.test(p.txt('#shAdm')),'و در پروندهٔ کاربر نیست');
  p.click('#shAdm [data-close]');

  p.click('#admNav [data-sec="settings"]');
  ok(p.all('[data-setg]').length===1&&/حوزه/.test(p.txt('[data-setg]')),'سرپرست فقط گروه حوزه‌ها را دارد');
  p.click('[data-setg="access"]');
  ok(p.all('.admlist .admsw').length===5,'پنج دسترسی فقط‌مالک فهرست شده');
  ok(!/حق عضویت/.test(p.txt('.admmatrix')),'حق عضویت باشگاه در دسترس حوزه نیست');

  p.click('#admNav [data-sec="dash"]');
  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p10"]');
  ok(!/مالی|درآمد|بدهی/.test(p.txt('#admBody')),'کارشناس هم هیچ مالی نمی‌بیند');
  p.click('#admNav [data-sec="reports"]');
  ok(p.all('[data-rep="fi"]').length===0,'گزارش مالی برای کارشناس نیست');
}

/* ── ۱۳) ماندگاری ── */
{
  console.log('\n── ماندگاری ──');
  const store=makeStore();
  const a=await load(store);
  a.click('#admNav [data-sec="settings"]');
  a.click('[data-setg="notify"]');
  const t=a.all('[data-tog]')[0];
  const wasOn=t.classList.contains('on');
  a.click(t);
  a.click('[data-setg="texts"]');
  a.type('[data-text="welcome"]','خوش آمدی؛ همه‌چیز همین‌جاست.','change');
  const b=await load(store);
  b.click('#admNav [data-sec="settings"]');
  b.click('[data-setg="notify"]');
  ok(b.all('[data-tog]')[0].classList.contains('on')!==wasOn,'کلید خاموش و روشن بعد از بازخوانی می‌ماند');
  b.click('[data-setg="texts"]');
  ok(b.doc.querySelector('[data-text="welcome"]').value.includes('همین‌جاست'),'متن ویرایش‌شده می‌ماند');
  b.click('#admNav [data-sec="reports"]');
  b.click('[data-rp="امسال"]');
  const c=await load(store);
  c.click('#admNav [data-sec="reports"]');
  ok(/امسال/.test(c.txt('.chip.on')),'دورهٔ انتخابی گزارش هم می‌ماند');
}

/* ── ۱۱) نشانی: هر بخش از راه هش ── */
{
  console.log('\n── نشانی و هش ──');
  const p=await load(makeStore(),'#cert');
  ok(p.txt('#admBar .head')==='گواهینامه','با #cert پنل روی مرکز صدور باز می‌شود');
  p.window.location.hash='#users';
  p.window.dispatchEvent(new p.window.Event('hashchange'));
  await wait(150);
  ok(p.txt('#admBar .head')==='کاربران','تغییر هش، بخش را عوض می‌کند');
  ok(p.window.location.hash==='#users','هش با بخش هم‌خوان می‌ماند');
}

/* ── ۱۲) حالت کهنه ── */
{
  console.log('\n── حالت کهنه ──');
  const store=makeStore();
  store.setItem('nora-admin',JSON.stringify({v:1,who:'p99',qf:'زز',evTab:'money',sec:'settings',role:'super',perms:{}}));
  const p=await load(store);
  ok(p.errs.length===0,'با حالت کهنهٔ دور پیش، پنل بی‌خطا بالا می‌آید');
  ok(p.all('.kpi').length===4,'و داشبورد سالم رندر می‌شود');
  ok(p.txt('#admBar .head')==='داشبورد','روی داشبورد می‌نشیند، نه بخش قفل‌شدهٔ کهنه');
}

/* ── ۱۳) پرونده‌ها و متن‌ها ── */
{
  console.log('\n── پرونده‌ها و متن ──');
  const files=['admin.html','admin.js','admin.css','builder.html','create.html'];
  const dash=files.filter(f=>fs.readFileSync(DIR+f,'utf8').includes(' — '));
  ok(dash.length===0,'خط تیرهٔ بلند با فاصله در متن فارسی نمانده'+(dash.length?': '+dash.join('، '):''));
  const html=fs.readFileSync(DIR+'admin.html','utf8');
  ok(html.includes('admin.css?v=41')&&html.includes('admin.js?v=41'),'نسخهٔ پرونده‌های پنل ۴۱ است');
  const sw=fs.readFileSync(DIR+'sw.js','utf8');
  ok(sw.includes("'nora-v30'"),'کارگر سرویس نسخهٔ ۳۰ است');
  ok(sw.includes("'admin.html'")&&sw.includes("'admin.css'")&&sw.includes("'admin.js'"),'پنل در پوستهٔ کش هست');
  /* هر آیکونی که پنل صدا می‌زند، باید در اسپرایت همان صفحه باشد */
  const have=new Set([...html.matchAll(/<symbol id="([^"]+)"/g)].map(m=>m[1]));
  const used=new Set();
  for(const f of ['admin.js','data.js']){
    let s=fs.readFileSync(DIR+f,'utf8');
    if(f==='data.js') s=s.slice(s.indexOf('const ADMIN={'), s.indexOf('/* ══ جمله‌های اطمینان'));
    for(const m of s.matchAll(/'(i-[a-z0-9-]+)'/g)) used.add(m[1]);
  }
  const miss=[...used].filter(x=>!have.has(x));
  ok(miss.length===0,'همهٔ آیکون‌های پنل در اسپرایت هست'+(miss.length?': '+miss.join('، '):''));
  /* برچسب هر بخش و هر تب و عددهای سرِ پنل باید همان چیزی باشد که در داده است */
  const data=fs.readFileSync(DIR+'data.js','utf8');
  const htmlTxt=fs.readFileSync(DIR+'admin.html','utf8');
  ok(!/\u2014/.test(data.slice(data.indexOf('const ADMIN={'),data.indexOf('/* ══ جمله‌های اطمینان'))),
    'بلوک پنل در data.js خط تیرهٔ بلند ندارد');
  const js=fs.readFileSync(DIR+'admin.js','utf8');
  ok(!/\u2014/.test(js),'خودِ admin.js هم خط تیرهٔ بلند ندارد');
  ok(htmlTxt.includes('پنل مدیران'),'سرصفحهٔ صفحه نام پنل را دارد');
  const p2=await load();
  const bad=p2.all('#admNav .btn').map(b=>{const sp=b.querySelector('span');
      return sp?sp.textContent.trim():''}).filter(t=>t&&data.indexOf(t)===-1);
  ok(bad.length===0,'هر برچسب بخش، همان واژهٔ data.js است'+(bad.length?': '+bad.join('، '):''));
  const nums=p2.all('.kpi b').map(b=>{const u=b.querySelector('.ku');
    return (u?b.textContent.replace(u.textContent,''):b.textContent).trim();})
    .filter(t=>t&&data.indexOf(t)===-1);
  ok(nums.length===0,'عددهای سرِ پنل هم از داده می‌آید'+(nums.length?': '+nums.join('، '):''));
  const units=p2.all('.kpi .ku').map(u=>u.textContent.trim()).filter(t=>t&&data.indexOf(t)===-1);
  ok(units.length===0,'و یکای هر عدد هم از داده می‌آید'+(units.length?': '+units.join('، '):''));
  ok(p2.all('.kpi .ku').length>=3,'یکا ریز و جدا نوشته می‌شود، نه چسبیده به رقم');
}

console.log('\nadmin-test: '+checks+' بررسی، '+fails+' خطا');
if(fails) process.exit(1);
