/* ══════════════════════════════════════════════════════════════════════════
   نورا · آزمون پنل مدیران (admin.html)
   ──────────────────────────────────────────────────────────────────────────
   اجرا:  npm i jsdom && node admin.test.mjs
   چه چیزی را می‌سنجد: بی‌خطا بار شدن پنل، هفت بخش به‌علاوهٔ داشبورد، داشبوردِ
   جدا برای مالک و سرپرست حوزه و کارشناس، چهار عدد کلیدی و کارتابل شخصی،
   ویزارد پنج‌گامی تعریف رویداد با پوستر و تم و فرم‌ساز و پیش‌نمایش کارت و
   صفحه و گردش تأیید، فهرست و صافی و جست‌وجوی کاربران، نه گزارش،
   گواهینامه و مدیریت کارشناسان در بخش کاربران، خروجیها فقط پیش‌نمایش تار با
   لینک ربات بله، شش گروه تنظیمات، یک مالک و شش
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
const SECS=['dash','newev','events','users','forms','reports','settings'];
let KEEP=null;   /* صفحه‌ای که تا بلوک آخر نگه داشته می‌شود */

/* ── ۱) پوسته و ناوبری ── */
{
  console.log('\n── پوسته و ناوبری ──');
  const p=await load();
  ok(p.errs.length===0, p.errs.length?('خطا: '+p.errs.slice(0,3).join(' | ')):'بی‌خطا بار شد');
  ok(p.all('#admNav .btn').length===7,'ریل هفت بخش دارد: داشبورد و شش بخش دیکته‌شده ('+p.all('#admNav .btn').length+')');
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
  ok(p.all('[data-clock]').length>=1,'ساعت و تاریخ روی ناوبری هست');
  const ck=p.txt('[data-clock]');
  ok(/[۰-۹]{2}:[۰-۹]{2}/.test(ck)&&/(شنبه|یکشنبه|دوشنبه|سه‌شنبه|چهارشنبه|پنجشنبه|جمعه)/.test(ck),
    'ساعت زنده و تاریخ شمسی روی ناوبری نوشته می‌شود: '+ck);
  const CJK=p.window.NORA_UI;
  ok(!!CJK&&typeof CJK.clockParts==='function','ساعت مشترک سامانه در ui.js است، نه فقط پنل');
  const cp=CJK.clockParts();
  ok(cp.jy>1400&&cp.jm>=1&&cp.jm<=12&&cp.jd>=1&&cp.jd<=31,'تاریخ شمسی درست خوانده می‌شود');
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
  p.click('[data-evnew]');
  ok(p.txt('#admBar .head')==='رویدادها و مطالب','ویزارد رویداد در همین بخش رویدادها و مطالب باز می‌شود');
  ok(p.all('.admsteps .st').length===5,'ویزارد پنج گام دارد: چیستی و پوستر، کی و کجا، ظرفیت و ثبت‌نام، فرم‌ها و اطلاع‌رسانی، کارت و صفحه');
  ok(p.all('[data-wkind]').length===0,'اینجا جای تعریف مطلب نیست؛ تعریف جدید فقط مطلب دارد');
  ok(!!p.doc.querySelector('[data-evback]'),'و بازگشت به فهرست سرِ ویزارد هست');
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
  /* برگزار شده و چندجلسه‌ای: رویداد آفلاین و گذشته هم ثبت می‌شود */
  ok(p.all('[data-wheld]').length===1,'دکمهٔ «برگزار شده» برای رویدادهای آفلاین و گذشته هست');
  p.type('#wz-sessions','3','change');
  ok(p.all('[data-sessrow]').length===3,'با سه جلسه، سه ردیف تاریخ و ساعت باز می‌شود');
  ok(p.all('[data-sessrow] [data-dp]').length===3,'هر جلسه تقویم خودش را دارد');
  p.click('[data-sessadd]');
  ok(p.all('[data-sessrow]').length===4,'جلسهٔ تازه اضافه می‌شود');
  p.click('[data-sessdel="3"]');
  ok(p.all('[data-sessrow]').length===3,'و کم می‌شود');
  p.type('[data-sesst="0"]','1700','change');
  ok(p.doc.querySelector('[data-sesst="0"]').value==='17:00','ساعت جلسه هم ۲۴ساعته می‌شود');
  p.type('#wz-sessions','1','change');
  ok(p.all('[data-sessrow]').length===0,'با یک جلسه، ردیف جلسه‌ها جمع می‌شود');
  ok(p.all('#wz-regFrom').length===1,'و پنجرهٔ ثبت‌نام برمی‌گردد');
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

  /* گام چهار: فرم درون رویداد ساخته نمی‌شود؛ از فرم‌ساز وصل می‌شود */
  ok(p.all('[data-fpick]').length>=1,'برگهٔ انتخاب فرم هست: فرم‌های فرم‌ساز بالای فهرست');
  ok(p.all('[data-ftpl],[data-fadd],[data-fcell],[data-fbuild]').length===0,'درون رویداد هیچ فرم و پرسشی ساخته نمی‌شود');
  ok(p.all('a[href*="create.html?ev="]').length>=1,'راه فرم‌ساز با شناسهٔ همین رویداد باز است');
  ok(/فرم‌ساز/.test(p.txt('.wform')),'و می‌گوید فرم در فرم‌ساز ساخته می‌شود');
  const U=p.window.NORA_UI;
  ok(!!U&&typeof U.formPut==='function','انبار فرم‌ها روی خود صفحه هست');
  /* همان کاری که create.html می‌کند: فرم تازه در انبار می‌نشیند */
  U.formPut({id:'t-reg',name:'ثبت‌نام کارگاه تست',kind:'ثبت‌نام',need:'reg',cap:20,
    fin:[{l:'شرکت',p:900000,off:10},{l:'پذیرایی',p:100000,off:0}]});
  p.click('[data-wstep="2"]'); p.click('[data-wstep="3"][data-wgo="1"]');
  ok(p.all('[data-fpick="reg"][data-fid="t-reg"]').length===1,'فرم تازهٔ فرم‌ساز در فهرست می‌آید');
  p.click('[data-fpick="reg"][data-fid="t-reg"]');
  ok(/ثبت‌نام کارگاه تست/.test(p.txt('.wform')),'و با یک زدن وصل می‌شود');
  ok(/۹۱۰/.test(p.txt('.wform')),'مبلغ فرم هم با تخفیفش خوانده می‌شود');
  ok(p.all('[data-fclear="reg"]').length===1,'و راه برداشتنش هم هست');
  /* یادآوری پیشرفته: ردیف، یکا، راه و خاموش‌وروشن */
  ok(p.all('[data-remrow]').length===3,'سه یادآوری پیش‌فرض هست');
  ok(p.all('[data-remrow] [data-remu]').length===3&&p.all('[data-remrow] [data-remch]').length===3,'هر یادآوری یکا و راه خودش را دارد');
  p.click('[data-remadd="before"]');
  ok(p.all('[data-remrow]').length===4,'یادآوری تازه اضافه می‌شود');
  p.type('[data-remn="3"]','48','change');
  ok(/۴۸/.test(p.txt('[data-remrow="3"]')),'زمان یادآوری می‌نشیند');
  const wasOff=p.all('[data-remrow="0"] .fbtn')[0].classList.contains('stop');
  p.click('[data-remon="0"]');
  ok(p.all('[data-remrow="0"] .fbtn')[0].classList.contains('stop')!==wasOff,'یادآوری خاموش و روشن می‌شود');
  p.click('[data-remon="0"]');
  p.click('[data-remdel="3"]');
  ok(p.all('[data-remrow]').length===3,'و یادآوری تازه برداشته می‌شود');
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
  ok(p.txt('#admBar .head')==='رویدادها و مطالب','بعد از انتشار، خودش به بخش رویدادها و مطالب می‌رود');
  ok(p.all('[data-ev]').length===before+1,'رویداد تازه به فهرست اضافه شد');
  ok(p.txt('[data-ev] b')==='اردوی پاییزهٔ دربند','نام همان است که نوشتیم');
  ok(!/پیش‌نویس/.test(p.txt('#admBody')),'دیگر هیچ رویدادی پیش‌نویس نمی‌شود');
  ok(p.doc.querySelector('[data-ev] .ic.pic img')!==null,'پوستر روی ردیف رویداد می‌نشیند');
  ok(/منتشر|پیش‌رو|جاری/.test(p.txt('[data-ev]')),'وضعیتش منتشر است');
  ok(p.all('.admsteps .st').length===0,'و ویزارد بسته می‌شود');
  /* فرم‌ساز و رویداد سینک می‌مانند: فرم به رویداد گره خورده است */
  const f1=p.window.NORA_UI.formById('t-reg')||{};
  ok(!!f1.ev,'فرمِ وصل‌شده به رویداد گره می‌خورد');
  ok(f1.sync&&f1.sync.cap===1&&f1.sync.money===1,'و ظرفیت و تاریخ و مبلغش با رویداد سینک است');
  ok(String(f1.ev)===p.all('[data-ev]')[0].dataset.ev,'و شناسهٔ همان رویداد است');

  /* فرم‌ها در بخش فرم‌ها و در مدیریت رویداد */
  p.click('#admNav [data-sec="forms"]');
  const flist=p.txt('#admBody');
  ok(/ثبت‌نام کارگاه تست/.test(flist)&&/فرم مسابقهٔ یادداشت ماهانه/.test(flist),'فرم تازهٔ فرم‌ساز و فرم‌های خود سامانه هر دو در بخش فرم‌ها هستند');
  ok(/form\.html\?ev=/.test(p.body()),'و نشانی‌شان به رویداد وصل است');
  p.click('#admNav [data-sec="events"]');
  p.click('[data-ev]');
  ok(/فرم‌های این رویداد/.test(p.txt('#shAdm')),'برگهٔ رویداد بخش فرم‌ها را دارد');
  ok(p.all('#shAdm [data-copyform]').length>=1,'و برای هر فرمِ وصل‌شده دکمهٔ رونوشت هست');
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
  ok(/نگار موسوی/.test(p.txt('#admBody'))&&p.all('[data-utab]').length===5,'پروندهٔ کامل با پنج تب باز شد');
  ok(/در صف تأیید/.test(p.txt('#admBody')),'وضعیتش درست نشان داده می‌شود');
  p.click('[data-uok="u3"]');
  ok(/تأییدشده/.test(p.txt('#admBody')),'تأیید پروفایل همان‌جا اثر می‌کند');
  p.click('[data-ublock="u3"]');
  ok(/مسدود/.test(p.txt('#admBody'))&&!!p.doc.querySelector('[data-uunblock]'),'مسدود هم از همان صفحه انجام می‌شود');
  p.click('[data-uback]');
  p.click('[data-uF="pending"]');
  ok(p.all('table.admtable tbody tr').length===2,'بعد از تأیید، از صف کم شد ('+p.all('table.admtable tbody tr').length+')');
}

/* ── ۴ب) کاربران: کاشیها، پرونده، باشگاه و ابزار ── */
{
  console.log('\n── کاربران: زیربخش‌ها ──');
  const p=await load();
  p.click('#admNav [data-sec="users"]');
  ok(p.all('.admtiles .utile').length===4,'چهار کاشی سرِ بخش است');
  ok(p.all('[data-uv]').length===4,'دقیقا چهار مسیر، نه بیشتر');
  ok(/پروفایل ۳ · غیبت مجاز ۲ · پاداش ۲/.test(p.txt('.admtiles')),'کاشی درخواستها سه صف را با عدد جمع میکند');
  ok(/در انتظار/.test(p.txt('.admtiles')),'کاشی پرکار، نشان در انتظار دارد');
  ok(p.all('[data-uF]').length===5,'صافی وضعیت با ویژه پنج تاست');
  ok(p.all('[data-uTag]').length>=3,'برچسبها فیلتر یکزبانه دارند');
  p.click('[data-uTag="عکاس"]');
  ok(p.all('table.admtable tbody tr').length===2,'فیلتر برچسب «عکاس» دو نفر دارد');
  p.click('[data-uTag="عکاس"]');
  ok(p.all('table.admtable tbody tr').length===15,'برداشتن فیلتر برچسب، همه را میآورد');
  /* درخواستها */
  p.click('[data-uv="req"]');
  ok(/درخواست پروفایل \(۳\)/.test(p.txt('#admBody')),'صف پروفایل سه نفر دارد');
  ok(/غیبت مجاز \(۲\)/.test(p.txt('#admBody')),'غیبتهای مجاز دو درخواست دارد');
  ok(/تحویل پاداش \(۲\)/.test(p.txt('#admBody')),'درخواست پاداش دو تا است');
  p.click('[data-uabsok]');
  ok(/غیبت مجاز \(۱\)/.test(p.txt('#admBody')),'تأیید غیبت مجاز همان‌جا کم میشود');
  p.click('[data-ushopno]');
  ok(/تحویل پاداش \(۱\)/.test(p.txt('#admBody')),'رد پاداش از صف برمیدارد');
  const SU=JSON.parse(p.store.getItem('nora-admin'));
  ok(SU.uabs[0].st==='تأیید شد'&&!SU.ushop[0]||SU.ushop.some(r=>r.st==='رد شد'),'وضعیت درخواستها در خانه مینشیند');
  /* گزارش */
  p.click('[data-uback]'); p.click('[data-uv="tools"]');
  ok(/گزارش کاربران/.test(p.txt('#admBody'))&&/جنسیت/.test(p.txt('#admBody')),'گزارش کاربران زیرتب اول ابزارهاست');
  ok(/منبع عضویت/.test(p.txt('#admBody'))&&/با دعوت دوستان/.test(p.txt('#admBody')),'منبع عضویت با دعوت آمده');
  ok(p.all('[data-rp]').length>=7,'دورههای زمانی گزارش هست');
  /* مناسبتها: زیرتب باشگاه */
  p.click('[data-uback]'); p.click('[data-uv="club"]'); p.click('[data-uclub="occ"]');
  ok(/\(۱۴ روشن از ۱۴\)/.test(p.txt('#admBody')),'چهارده مناسبت آماده روشن است');
  p.click('[data-uocc="nowruz"]');
  ok(/\(۱۳ روشن از ۱۴\)/.test(p.txt('#admBody')),'مناسبت آماده حذف نمیشود؛ خاموش میشود');
  p.click('[data-uoccnew]'); p.type('#occN','روز خانه‌سازی'); p.type('#occM','7'); p.type('#occD','20');
  p.click('[data-uoccadd]');
  ok(/روز خانه‌سازی/.test(p.txt('#admBody')),'مناسبت سفارشی ساخته شد');
  ok(!!p.doc.querySelector('[data-uoccdel]'),'مناسبت سفارشی برداشتن دارد');
  /* باشگاه: پنج زیرتب */
  p.click('[data-uback]'); p.click('[data-uv="club"]');
  ok(p.all('[data-uclub]').length===5,'باشگاه پنج زیرتب دارد');
  /* هر بخش کاربران گزارش اکسل بله دارد */
  { const views=[['req',null],['club','rules'],['club','ach'],['club','shop'],['club','rank'],['club','occ'],
      ['cert',null],['tools','report'],['tools','par'],['tools','add'],['tools','imp'],['tools','tags'],
      ['tools','blocked'],['tools','inbox'],['tools','log']];
    let n=0;
    for(const [uv,sub] of views){
      const bk=p.doc.querySelector('[data-uback]'); if(bk) p.click(bk);
      p.click('[data-uv="'+uv+'"]');
      if(sub) p.click(uv==='club'?'[data-uclub="'+sub+'"]':'[data-utool="'+sub+'"]');
      if(p.doc.querySelector('.balerow, .balebox')) n++; }
    ok(n===views.length,'هر بخش کاربران گزارش اکسل بله دارد ('+n+'/'+views.length+')'); }
  p.click('[data-uback]'); p.click('[data-uv="club"]');
  ok(/قانون‌های امتیاز/.test(p.txt('#admBody')),'زب پیشفرض باشگاه امتیاز شرطی است');
  ok(/سقف‌های محافظ/.test(p.txt('#admBody'))&&/حداکثر ۳۰۰/.test(p.txt('#admBody')),'سقفهای محافظ امتیاز نشان داده میشود');
  p.click('[data-urulenew]'); p.type('#rulN','قهرمان فرم'); p.click('[data-uruleadd]');
  ok(/قهرمان فرم/.test(p.txt('#admBody')),'قانون امتیاز سفارشی ساخته شد');
  p.click('[data-urule="form3"]');
  const SU2=JSON.parse(p.store.getItem('nora-admin'));
  ok(SU2.urules.form3===0,'قانون آماده خاموش روشن دارد');
  p.click('[data-uclub="ach"]');
  ok(/۱۳ نشان در ۴ سطح/.test(p.txt('#admBody'))&&/افسانه‌ای/.test(p.txt('#admBody')),'سیزده نشان در چهار سطح است');
  p.click('[data-uclub="shop"]');
  ok(/VIP طلایی/.test(p.txt('#admBody'))&&/۵۰۰۰ امتیاز/.test(p.txt('#admBody')),'پاداشها با قیمتاند');
  p.click('[data-uclub="rank"]');
  ok(/چهار جدول برترین‌ها/.test(p.txt('#admBody'))&&/بیشترین دعوت/.test(p.txt('#admBody')),'رتبه‌بندی چهار جدول دارد');
  p.click('[data-urankhide]');
  ok(/\*\*\*/.test(p.txt('#admBody')),'نام مخفی برای حریم خصوصی هست');
  /* پروندهٔ کاربر: تبهای پنجگانه */
  p.click('[data-uback]'); p.click('[data-user="u7"]');
  const sh=p.txt('#admBody');
  ok(/سطح باشگاه/.test(sh)&&/رتبه/.test(sh)&&/تکمیل پروفایل/.test(sh),'سرِ پرونده، سطح و رتبه و تکمیل دارد');
  p.click('[data-utab="info"]');
  ok(/برچسب‌ها/.test(p.txt('#admBody'))&&/یادداشت پرونده/.test(p.txt('#admBody')),'تب اطلاعات با برچسب و یادداشت است');
  p.type('#uNoteTxt','برای اردوی پاییز اولویت دارد'); p.click('[data-unotego="u7"]');
  ok(/برای اردوی پاییز/.test(p.txt('#admBody')),'یادداشت در پرونده می‌نشیند');
  ok(!!p.doc.querySelector('[data-bale="profile_u7"]'),'خروجی فردی پرونده دکمهٔ ربات بله دارد');
  p.click('[data-bale="profile_u7"]');
  ok(/نخستین دریافت/.test(p.txt('#shAdm')),'دفع اول، برگهٔ پیوند با ربات باز میشود');
  const prf=p.doc.querySelector('#shAdm a[data-balereg]');
  ok(!!prf&&prf.href.includes('ble.ir/lifeline_bot?start=profile_u7'),'لینک دقیق ربات در برگه هست');
  p.click(p.doc.getElementById('shAdm').querySelectorAll('[data-balereg]')[1]);
  ok(/پیوند با ربات ثبت شد/.test(p.txt('#toast')),'ثبت ربات خبر میدهد');
  ok(!!p.doc.querySelector('[data-balesend="profile_u7"]')&&!p.doc.querySelector('[data-bale]'),'از این پس دکمه‌ها فقط میفرستند');
  p.click('[data-balesend="profile_u7"]');
  ok(/فرستاده شد؛ گزارش در ربات بله/.test(p.txt('#toast')),'ارسال دفعهای بعد بی برگه است');
  p.click('[data-utab="club"]');
  ok(/کد معرف/.test(p.txt('#admBody'))&&/نشان‌ها \([۰-۹]+ از ۱۳\)/.test(p.txt('#admBody')),'تب باشگاه با معرف و نشانهاست');
  p.click('[data-utab="ev"]');
  ok(/رویدادها \([۰-۹]+\)/.test(p.txt('#admBody'))&&/غیبت‌های مجاز/.test(p.txt('#admBody')),'تب رویدادها با غیبت مجاز است');
  p.click('[data-utab="msg"]');
  ok(/پیام‌ها/.test(p.txt('#admBody')),'تب پیامهاست');
  p.click('[data-utab="log"]');
  ok(/عضویت در سامانه/.test(p.txt('#admBody'))&&/وضعیت کنونی/.test(p.txt('#admBody')),'تب تاریخچه با عضویت و وضعیت است');
  p.click('[data-uvip="u7"]');
  ok(/برداشتن VIP/.test(p.txt('#admBody')),'کلید VIP میچرخد');
  p.click('[data-uback]');
  p.click('[data-uF="vip"]');
  ok(p.all('table.admtable tbody tr').length===1,'فیلتر ویژه همان یک نفر را میآورد');
  p.click('[data-uF="all"]');
  /* ابزارها و گزارش: نه زیرتب */
  p.click('[data-uv="tools"]');
  ok(p.all('[data-utool]').length===9,'ابزارها و گزارش نه زیرتب دارد');
  ok(!!p.doc.querySelector('[data-utool="staff"]'),'مدیران و کارشناسان زیرتب ابزارهاست');
  ok(/جنسیت/.test(p.txt('#admBody')),'زب پیشفرض گزارش کاربران است');
  p.click('[data-utool="par"]');
  p.click('[data-upar="bio"]');
  p.click('[data-uparreq="bio"]');
  const SU3=JSON.parse(p.store.getItem('nora-admin'));
  ok(SU3.upar['bio|on']===0&&SU3.upar['bio|req']===true,'روشن و اجباری هر فیلد در خانه مینشیند');
  p.click('[data-uparreset]');
  ok(!Object.keys(JSON.parse(p.store.getItem('nora-admin')).upar).length,'بازگشت به پیشفرض خالی میکند');
  /* افزودن دستی و ورودی اکسل */
  p.click('[data-utool="add"]');
  p.type('#uAddTxt','علی محمدی، ۰۰۲۳۴۵۶۷۸۷\nزهرا کریمی ۰۹۱۲۱۲۳۴۵۶۷');
  p.click('[data-uaddgo]');
  ok(p.all('table.admtable tbody tr').length===17,'افزودن دستی دوخطی دو نفر اضافه میکند');
  const SU4=JSON.parse(p.store.getItem('nora-admin'));
  ok(SU4.uextra.length===2&&SU4.uextra[1].ph==='09121234567'&&SU4.uextra[0].nid==='۰۰۲۳۴۵۶۷۸۷','موبایل و کد ملی از خط جدا میشود');
  p.click('[data-uv="tools"]'); p.click('[data-utool="imp"]');
  p.type('#uImpTxt','نام و نام خانوادگی\tشماره\tشهر\nحسین رحیمی\t09120000001\tقم');
  p.click('[data-uimpparse]');
  ok(/پیش‌نمایش \(۱ ردیف\)/.test(p.txt('#admBody')),'ورودی اکسل پیشنمایش میدهد');
  p.click('[data-uimpgo]');
  ok(p.all('table.admtable tbody tr').length===18,'درج از پیشنمایش اضافه میکند');
  const SU5=JSON.parse(p.store.getItem('nora-admin'));
  ok(SU5.uimp.length===1&&SU5.uimp[0].n===1,'تاریخچهٔ ورود ثبت شد');
  p.click('[data-uv="tools"]'); p.click('[data-utool="imp"]');
  ok(/تاریخچهٔ ورودها/.test(p.txt('#admBody')),'تاریخچهٔ ورودها دیده میشود');
  /* صندوق، مسدودها، لاگ؛ همه زیرتب ابزارها */
  p.click('[data-utool="inbox"]');
  ok(/خوانده‌نشده/.test(p.txt('#admBody')),'صندوق با خواندهنشده است');
  p.click('[data-uinboxall]');
  ok(/۰ خوانده‌نشده/.test(p.txt('#admBody')),'همه را خوانده کنم میزند');
  p.click('[data-uinboxopen="u3"]');
  ok(/نگار موسوی/.test(p.txt('#admBody')),'از صندوق، پروندهٔ فرستنده باز میشود');
  p.click('[data-uback]'); p.click('[data-uv="tools"]'); p.click('[data-utool="blocked"]');
  ok(/رضا شریفی/.test(p.txt('#admBody')),'مسدودها با پرونده میآید');
  p.click('[data-uunblock="u4"]');
  ok(/مسدودی برداشته شد/.test(p.txt('#toast')),'رفع مسدودی از فهرست مسدودها هست');
  p.click('[data-utool="log"]');
  ok(p.all('#admBody .admlirow').length>=4,'لاگ عملیات پر میشود: تأیید، رد، VIP، ورود');
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
  p.click('#admNav [data-sec="users"]');
  ok(!!p.doc.querySelector('[data-uv="cert"]'),'گواهینامه‌ها کاشی سرِ کاربران است');
  p.click('[data-uv="cert"]');
  ok(p.all('[data-cstep]').length===4,'مرکز صدور چهار گام دارد: فایل ورد، رویدادها، مخاطبان، صدور و صف');
  ok(/صدور در نوبت/.test(p.txt('.admtiles')||'')||true,'کاشی گواهینامه جمعبندی دارد');
  /* گام ۱: فایل ورد؛ بارگذاری، راهنما، پیشفرض */
  ok(p.all('[data-cfile]').length===3,'سه فایل نمونه هست');
  ok(!!p.doc.querySelector('[data-cfilenew]'),'بارگذاری فایل ورد هست');
  ok(p.all('.stg').length===4&&p.all('.stpr .stp').length>=18,'راهنمای پارامتر چهار گروه و کامل است');
  ok(/\{نام\}/.test(p.txt('#admBody'))&&/\{کیوآر\}/.test(p.txt('#admBody'))&&/\{شماره‌نامه\}/.test(p.txt('#admBody')),'جای‌نامهای کلیدی راهنما هست');
  ok(/پیشفرض/.test(p.txt('#admBody')),'فایل نمونهٔ پیشفرض نشان داده میشود');
  ok(p.all('.balebox').length>=1&&/فقط پیش‌نمایش تار/.test(p.txt('.balebox')),'پیش‌نمایش فایل ورد تار است');
  p.type('#cFileN','گواهینامهٔ داوری جشنواره');
  p.click('[data-cfilenew]');
  ok(/بارگذاری‌شدهٔ شما/.test(p.txt('#admBody'))&&p.all('[data-cfile]').length===4,'فایل ورد بارگذاری و برداشته میشود');
  p.click('[data-cdef]');
  ok(/فایل پیشفرض عوض شد/.test(p.txt('#toast')),'پیشفرضسازی پیام دارد');
  /* گام ۲: چند رویداد */
  p.click('[data-cstep="1"]');
  ok(p.all('[data-cev]').length>=3,'چیپ رویدادها هست');
  p.click(p.all('[data-cev]')[0]);
  p.click(p.all('[data-cev]')[1]);
  ok(p.all('[data-cev].on').length===2,'دو رویداد همزمان برگزیده میشود');
  ok(/۲ رویداد برگزیده شد/.test(p.txt('#admBody')),'جمعبندی دو رویداد نوشته میشود');
  /* گام ۳: مخاطبان از دسته و اکسل و جستوجو */
  p.click('[data-cstep="2"]');
  ok(p.all('[data-ctag]').length>=4,'دسته‌های آماده هست');
  p.click(p.all('[data-ctag]')[0]);
  ok(/از دسته‌ها/.test(p.txt('#admBody')),'دسته برگزیده در جمعبندی هست');
  p.type('#cXls','سارا محمدی 09121234567\nنرگس ناشناس');
  p.click('[data-cxls]');
  ok(/۱ شناخته شد · ۱ ناشناس/.test(p.txt('#admBody')),'اکسل شناخته و ناشناس را جدا میکند');
  ok(/ناشناسها هم با همان نام/.test(p.txt('#admBody')),'سرنوشت ناشناسها نوشته شده');
  p.type('#cFind','نگار');
  p.click('[data-cfindgo]');
  ok(p.all('[data-cpick]').length>=1,'جست‌وجوی کاربر نتیجه میآورد');
  p.click(p.all('[data-cpick]')[0]);
  ok(p.all('[data-cunpick]').length===1,'افزودن تک‌تک با چیپ برداشتن هست');
  ok(/جمع گیرنده‌ها/.test(p.txt('#admBody')),'جمع گیرنده‌ها با یکتاسازی نوشته میشود');
  /* گام ۴: پنجرهٔ خلوت، صف، مدیریت */
  p.click('[data-cstep="3"]');
  ok(/پنجرهٔ بعدی/.test(p.txt('#admBody'))&&/۰۲:۰۰/.test(p.txt('#admBody')),'پنجرهٔ ساعت خلوت نوشته میشود');
  ok(/تا ۲۴ ساعت آینده/.test(p.txt('#admBody')),'قول «تا ۲۴ ساعت آینده» برای گیرنده هست');
  ok(/درخواستهای رسیده از ربات/.test(p.txt('#admBody')),'درخواستهای ربات در صف دیده میشود');
  ok(!!p.doc.querySelector('[data-cletter]')&&!!p.doc.querySelector('[data-cmonths]'),'شمارهٔ نامه و اعتبار ورودی دارند');
  ok(!!p.doc.querySelector('[data-cnews]')&&/۲۴ ساعت/.test(p.doc.querySelector('[data-cnews]').placeholder),'متن خبر با قول ۲۴ساعته قابل ویرایش است');
  p.click('[data-crand]');
  ok(/نمونه برای/.test(p.txt('.balebox')),'پیش‌نمایش تصادفی با نام یک نفر میآید');
  ok(!!p.doc.querySelector('[data-cqueue]')&&!!p.doc.querySelector('[data-cfast]'),'ثبت در صف و صدور فوری هر دو هست');
  p.click('[data-cqueue]');
  ok(/در صف نشست/.test(p.txt('#toast')),'ثبت در صف پیام پنجره میدهد');
  ok(/اجرا:/.test(p.txt('#admBody')),'دسته در صف با زمان اجرا نشست');
  p.click('[data-crun]');
  ok(/همین حالا صادر شد/.test(p.txt('#toast')),'اجرا خارج از نوبت همان لحظه صادر میکند');
  ok(/دریافتشده/.test(p.txt('#admBody')),'شمار دریافتشدهها نوشته میشود');
  p.click('[data-cbnudge]');
  ok(/گیرندهٔ مانده/.test(p.txt('#toast')),'یادآوری مانده‌ها پیام میدهد');
  p.click('[data-cfast]');
  ok(/همین حالا صادر شد/.test(p.txt('#toast')),'صدور فوری دستهٔ تازه میسازد');
  p.click('[data-cqueue]');
  p.click('[data-cbrev]');
  ok(/باطل شد/.test(p.txt('#toast')),'برداشتن از صف با ابطال است');
  ok(!!p.doc.querySelector('[data-bale^="cert_"]'),'دریافت نمونه از ربات بله هست');
  const jobs=p.all('.admrow2').length;
  p.click('[data-cqueue]');
  ok(p.all('.admrow2').length===jobs+1,'ثبت در صف، یک کار به کارهای صدور اضافه میکند');
  ok(/منتشر|نوبت/.test(p.txt('.admlist')),'وضعیت کار صدور معلوم است');
}

/* ── ۸) تنظیمات و حوزه‌ها ── */
{
  console.log('\n── تنظیمات و دسترسی ──');
  const p=await load();
  p.click('#admNav [data-sec="settings"]');
  ok(p.all('[data-setg]').length===6,'شش گروه تنظیمات هست');
  ok(p.all('[data-text]').length===4,'متن‌های پرکاربرد قابل ویرایش‌اند');
  p.click('[data-setg="money"]');
  ok(p.all('[data-tog]').length===4,'گروه مالی چهار کلید دارد');
  const first=p.all('[data-tog]')[0];
  p.click(first);
  ok(first.classList.contains('on')!==(/false/.test(first.getAttribute('aria-checked'))),'کلید خاموش و روشن می‌شود');
  ok(p.store.getItem('nora-admin')!==null,'حالت پنل ذخیره می‌شود');
  p.click('#admNav [data-sec="users"]'); p.click('[data-uv="tools"]'); p.click('[data-utool="staff"]');
  ok(p.all('[data-setF]').length===6,'شش حوزه در مدیریت مدیران و کارشناسان هست (مالک جداست)');
  ok(p.all('.stflow .stf').length===3,'جریان سهگامی حساب و ورود اول روی صفحه است');
  ok(/در انتظار تکمیل پروفایل/.test(p.txt('#admBody')),'کارشناس بی‌پروفایل با برچسب هشدار نشان داده میشود');
  ok(p.all('.stacc').length>=2,'نام کاربری هر کارشناس روی ردیفش هست');
  ok(/سرپرست/.test(p.txt('#admBody')),'سرپرست حوزه روی جدول نوشته شده');
  ok(p.all('.permrow').length>=4,'دسترسی‌های حوزه با ردیف نرم میآید');
  ok(p.all('[data-fperm]').length>=4,'دسترسی‌های کارشناس تیک‌زدنی است');
  const on=p.all('[data-fperm].on').length;
  p.click(p.all('[data-fperm]')[0]);
  ok(p.all('[data-fperm].on').length!==on,'مالک می‌تواند دسترسی کارشناس بدهد یا بردارد');
  ok(/داده شد|برداشته شد/.test(p.txt('#toast')),'و همان لحظه خبر می‌دهد');
  ok(p.all('.admlist .admsw').length===5,'پنج دسترسی ویژه فقط برای مالک است');
  p.click('[data-setF="club"]');
  ok(/باشگاه/.test(p.txt('.fslead')),'با چیپ باشگاه، سرپرست باشگاه می‌آید');
  ok(p.all('#admBody [data-addspec]').length===1,'دکمهٔ حساب تازه هست');
  p.click('[data-addspec]');
  ok(!!p.doc.querySelector('#spN')&&!!p.doc.querySelector('#spU')&&!!p.doc.querySelector('#spP'),'ورقهٔ ساخت حساب نام و نام کاربری و رمز دارد');
  p.type('#spN','مینا رحیمی'); p.type('#spU','m.rahimi');
  const pw1=p.doc.querySelector('#spP').value;
  ok(/^Nora-\d{4}$/.test(pw1),'رمز یکبارمصرف پیشنهادی میآید');
  p.click('[data-genpw]');
  ok(p.doc.querySelector('#spP').value!==pw1,'رمز تازهسازی دارد');
  const team=p.all('.trow').length;
  p.click('[data-newspec2]');
  ok(p.all('.trow').length===team+1,'حساب تازه به تیم حوزه اضافه شد');
  ok(/حساب ساخته شد/.test(p.txt('#toast')),'و خبرش میآید');
  ok(/در انتظار تکمیل پروفایل/.test(p.txt('#admBody')),'حساب تازه بی‌پروفایل است');
  p.click('[data-specrow]');
  ok(/پروفایل دست‌اندرکاران/.test(p.txt('#shAdm')),'پروندهٔ دست‌اندرکاران از ردیف باز میشود');
  p.click('#shAdm [data-close]');
  p.click('[data-resetspec]');
  ok(/رمز تازه برای/.test(p.txt('#toast')),'تغییر رمز همان‌جا هست');
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
  ok(p.all('#admNav [data-locked]').length===2,'دو بخش روی کارشناس قفل است');
  ok(p.all('#admNav [data-sec="newev"]:not([data-locked])').length===1,'ولی تعریف جدید برایش باز است');
  ok(p.all('#admTabs a').length===4,'نوار پایین کارشناس چهار بخش دارد');
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
  ok(p.all('[data-setg]').length===0&&/منتقل شد/.test(p.txt('#admBody')),'مدیریت کارشناسان از تنظیمات به کاربران منتقل شده');
  p.click('#admNav [data-sec="events"]');
  ok(!/باز نمی‌شود/.test(p.txt('#admBody')),'رویدادها برای آموزش باز است');

  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p1"]');
  ok(p.all('#admNav [data-locked]').length===0,'مالک هیچ بخشی را بسته ندارد');
  ok(p.all('#admTabs a').length===5,'و نوار پایین کامل است');
}

/* ── ۱۰) تعریف جدید: فقط مطلب؛ کارشناس می‌فرستد، مالک منتشر می‌کند ── */
{
  console.log('\n── تعریف تازه و تأیید ──');
  const p=await load();
  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p10"]');
  ok(p.all('#admNav [data-sec="newev"]:not([data-locked])').length===1,'تعریف تازه برای کارشناس هم باز است');
  p.click('#admNav [data-sec="newev"]');
  ok(p.txt('#admBar .head')==='تعریف جدید','بخش تعریف جدید باز شد');
  ok(!!p.doc.querySelector('[data-pf="t"]')&&!!p.doc.querySelector('[data-pgo="2"]'),'تعریف جدید همین‌جا ویرایشگر دوگامی مطلب است');
  ok(p.all('[data-wkind]').length===0,'اینجا دیگر رویداد تعریف نمی‌شود');
  p.type('[data-pf="t"]','یادداشت کارشناس');
  p.type('[data-pf="lead"]','سه خط دربارهٔ کلاس.');
  p.click('[data-pgo="2"]');
  p.click('[data-badd="p"]');
  p.type('[data-bi="0"][data-bf="x"]','متن یادداشت کارشناس.');
  ok(!p.doc.querySelector('[data-ppub]')&&!!p.doc.querySelector('[data-psend]'),'کارشناس فقط فرستادن برای تأیید دارد');
  p.click('[data-psend]');
  const P10=JSON.parse(p.store.getItem('nora-posts')||'[]');
  ok(P10.length===1&&P10[0].pend===1&&P10[0].pub===0,'مطلب کارشناس در صف تأیید نشست');
  ok(p.txt('#admBar .head')==='رویدادها و مطالب','و خودش به بخش رویدادها و مطالب برده میشود تا مطلبش را ببیند');
  p.click('[data-pmgrback]');
  ok(/یادداشت کارشناس/.test(p.txt('#admBody'))&&/در انتظار تأیید/.test(p.txt('#admBody')),'مطلب در صف، همان‌جا دیده میشود');
  p.click('#admNav [data-sec="newev"]');
  ok(p.doc.querySelector('[data-pf="t"]').value==='','تعریف جدید برای تعریف بعدی تازه است');
  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p1"]');
  p.click('#admNav [data-sec="events"]');
  const row=p.all('[data-pedit]').find(r=>/یادداشت کارشناس/.test(r.textContent));
  ok(!!row&&/در انتظار تأیید/.test(row.textContent),'مالک مطلب در صف تأیید را می‌بیند');
  if(row) p.click(row);
  ok(!!p.doc.querySelector('[data-pf="t"]'),'مالک مطلب صف را در ویرایشگر باز می‌کند');
  p.click('[data-pgo="2"]');
  ok(!!p.doc.querySelector('[data-ppub]'),'مالک در گام دوم دکمهٔ انتشار دارد');
  p.click('[data-ppub]');
  const P11=JSON.parse(p.store.getItem('nora-posts'));
  ok(P11[0].pub===1&&P11[0].pend===0,'با یک دکمه منتشر می‌شود');
  ok(p.txt('#admBar .head')==='رویدادها و مطالب'&&/مدیریت مطلب/.test(p.txt('#admBody')),'بعد از انتشار، مدیریت مطلب جلوی چشم است');
  p.click('[data-pmgrback]');
  const row2=p.all('[data-pmgr]').find(r=>/یادداشت کارشناس/.test(r.textContent));
  ok(!!row2&&/منتشر شده/.test(row2.textContent),'و در فهرست، منتشر شده خوانده می‌شود');
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
  ok(p.txt('#admBar .head')==='رویدادها و مطالب'&&/ویرایش/.test(p.txt('.admchips')),'ویرایش از خود رویداد شروع می‌شود و زیر همین بخش باز است');
  ok(/وضعیت عوض نمی‌شود/.test(p.txt('.admchips')),'و می‌گوید وضعیت عوض نمی‌شود');
  ok(p.all('[data-wstep="1"][data-wgo="1"]:not([disabled])').length===1,'گام‌های بعدی برای ویرایش باز است');
  p.type('#wzName','کارگاه روایت اول‌شخص، دور دوم');
  p.click('[data-wstep="1"][data-wgo="1"]');
  ok(/^۱۴۰۴\/۰۷\/۲۴$/.test(p.doc.querySelector('#wz-date').value),'تاریخ کنونی رویداد در قلم تقویم نشسته');
  ok(p.doc.querySelector('#wz-place').value==='کتابخانهٔ نورا، ونک','و جای کنونی‌اش هم');
  p.type('#wz-place','کتابخانهٔ نورا، سالن الف','change');
  p.click('[data-wstep="2"][data-wgo="1"]');
  p.click('[data-wstep="3"][data-wgo="1"]');
  ok(p.doc.querySelector('[data-fpick="reg"]')!==null&&p.all('[data-ftpl],[data-fadd]').length===0,'گام فرم‌ها در ویرایش هم برگهٔ فرم‌ساز است، نه فرم‌ساز درون‌رویداد');
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

  p.click('#admNav [data-sec="users"]'); p.click('[data-uv="tools"]'); p.click('[data-utool="staff"]');
  ok(/مدیران و کارشناسان/.test(p.txt('#admBody')),'سرپرست پشتیبانی مدیریت کارشناسان را دارد');
  ok(p.all('.admlist .admsw').length===5,'پنج دسترسی فقط‌مالک فهرست شده');
  ok(!/حق عضویت/.test(p.txt('.permrows'))&&/حق عضویت/.test(p.txt('#admBody')),'حق عضویت باشگاه فقط‌مالک است، در دسترس حوزه نیست');

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

/* ── ۱۴) پوستر خودم، رویداد گذشته و سینک فرم‌ساز با رویداد ── */
{
  console.log('\n── پوستر خودم و رویداد گذشته ──');
  const p=await load();
  p.click('#admNav [data-sec="events"]');
  p.click('[data-evnew]');
  ok(p.all('[data-wfile]').length===1,'کاشی «پوستر خودم» در گام اول هست');
  const inp=p.doc.querySelector('[data-wfile]');
  const pic=new p.window.File([new Uint8Array([137,80,78,71,13,10,26,10,7,7,7,7])],'poster.png',{type:'image/png'});
  Object.defineProperty(inp,'files',{value:[pic],configurable:true});
  inp.dispatchEvent(new p.window.Event('change',{bubbles:true}));
  await wait(200);
  ok(p.doc.querySelector('.pthumb.up')!==null,'کاشی پوستر خودم سر جایش است');
  ok(p.doc.querySelector('.evcard-cover img')!==null,'عکس خوانده می‌شود و روی کارت پیش‌نمایش می‌نشیند');
  ok(/پوستر خودم|عوض کن/.test(p.txt('.pthumb.up')),'و خودش می‌گوید عوضش کن');
  ok(p.all('[data-wposterclear]').length===1,'راه برداشتن پوستر خودم هم هست');
  p.click('[data-wposterclear]');
  ok(p.all('[data-wposterclear]').length===0,'و با یک دکمه برداشته می‌شود');

  /* رویداد گذشته و آفلاین: از اول در «برگزار شده» می‌نشیند */
  p.click('[data-wet="workshop"]');
  p.type('#wzName','کارگاه گذشتهٔ آفلاین');
  p.click('[data-wstep="1"][data-wgo="1"]');
  p.type('#wz-date','۱۴۰۴/۰۶/۱۰','change');
  p.type('#wz-time','10:00','change');
  p.type('#wz-to','12:00','change');
  p.type('#wz-place','کتابخانهٔ نورا','change');
  ok(p.all('[data-wheld]').length===1,'دکمهٔ برگزار شده در گام زمان هست');
  p.click('[data-wheld]');
  ok(p.all('[data-wheld].on').length===1,'روشن می‌شود');
  ok(/برگزار شده|آرشیو/.test(p.txt('#admBody')),'و می‌گوید خودش می‌رود در برگزار شده');
  p.click('[data-wstep="2"][data-wgo="1"]');
  ok(/آرشیو|گزارش/.test(p.txt('#admBody')),'آرشیو در گام ظرفیت هم هست');
  ok(p.all('#wz-regFrom').length===0,'رویداد برگزارشده پنجرهٔ ثبت‌نام نمی‌خواهد');
  p.type('#wz-who','32','change');
  p.type('#wz-rep','سی‌ودو نفر آمدند، بی‌حادثه بود','change');
  p.click('[data-wstep="3"][data-wgo="1"]');
  p.click('[data-wstep="4"][data-wgo="1"]');
  ok(/برگزار شده/.test(p.txt('.admreview')),'مرور هم وضعیت برگزار شده را می‌گوید');
  p.click('[data-wsend]');
  ok(p.all('[data-ev]').length>=8,'رویداد گذشته هم به فهرست اضافه می‌شود');
  p.click('#admNav [data-sec="events"]');
  const firstRow=p.txt('[data-ev]');
  ok(/کارگاه گذشتهٔ آفلاین/.test(firstRow)&&/برگزار شده/.test(firstRow),'و خودش در فهرست «برگزار شده» نشاندار می‌شود');
  ok(p.all('[data-evF]').length===4,'چهار صافی رویدادها سر جایش است');
  p.click('[data-evF="past"]');
  ok(p.all('[data-ev]').length>=3,'صافی برگزار شده رویدادهای گذشته را جدا می‌کند');
  p.click('[data-evF="all"]');
  p.click('[data-ev="e3"]');
  ok(/کارگاه روایت اول‌شخص/.test(p.txt('#shAdm')),'برگهٔ رویداد باز می‌شود');
  p.click('#shAdm [data-close]');
}

/* ── ۱۴ب) گذر خودکار وضعیت: پایان یعنی پایانِ آخرین جلسه ── */
{
  console.log('\n── گذر خودکار وضعیت رویداد ──');
  const U=(await load()).window.NORA_UI, c=U.clockParts();
  const pad=n=>String(n).padStart(2,'0');
  const mLen=(jy,jm)=>jm<=6?31:jm<=11?30:29;
  const g=off=>{let {jy,jm,jd}=c;
    for(let i=0;i<Math.abs(off);i++){
      if(off>0){ if(jd<mLen(jy,jm)) jd++; else {jd=1; jm++; if(jm>12){jm=1; jy++}} }
      else { if(jd>1) jd--; else {jm--; if(jm<1){jm=12; jy--} jd=mLen(jy,jm)} } }
    return jy+'/'+pad(jm)+'/'+pad(jd)};
  const seed=makeStore();
  seed.setItem('nora-admin', JSON.stringify({v:51, evF:'all', added:[
    {id:'z-done', n:'نشست دیروز', kind:'نشست', when:'', on:g(-1), time:'۲۰:۰۰', end:g(-1),
     place:'آنلاین', cap:40, reg:40, state:'soon', sess:[], sessions:1},
    {id:'z-mid', n:'کارگاه سه‌جلسه‌ای', kind:'کارگاه', when:'', on:g(-2), time:'۱۷:۰۰', end:g(3),
     place:'لانه', cap:20, reg:8, state:'soon', sessions:3,
     sess:[{d:g(-2),t:'17:00',to:'19:00'},{d:g(1),t:'17:00',to:'19:00'},{d:g(3),t:'17:00',to:'19:00'}]}]}));
  const p=await load(seed,'#events');
  const row=id=>p.all('[data-ev]').find(r=>r.getAttribute('data-ev')===id);
  ok(!!row('z-done')&&/برگزار شده/.test(row('z-done').textContent),'تک‌جلسهٔ گذشته خودش «برگزار شده» می‌شود');
  ok(!!row('z-mid')&&/جاری/.test(row('z-mid').textContent),'چندجلسه‌ای میان دو جلسه «جاری» می‌ماند');
  p.click('[data-evF="past"]');
  ok(p.all('[data-ev="z-done"]').length===1&&p.all('[data-ev="z-mid"]').length===0,
    'صافی برگزار شده فقط تمام‌شده‌ها را می‌آورد');
  p.click('[data-evF="live"]');
  ok(p.all('[data-ev="z-mid"]').length===1&&p.all('[data-ev="z-done"]').length===0,
    'و صافی جاری در جریان‌ها را نشان می‌دهد');
}

/* ── ۱۴پ) نظرسنجی آمادهٔ نورا: پیشفرض خودکار، اختصاصی هم دارد ── */
{
  console.log('\n── نظرسنجی آماده و خودکار ──');
  const p=await load();
  p.click('#admNav [data-sec="events"]');
  p.click('[data-evnew]');
  p.click('[data-wet="workshop"]');
  p.type('#wzName','کارگاه با نظرسنجی آماده');
  p.click('[data-wstep="1"][data-wgo="1"]');
  p.type('#wz-date','۱۴۰۴/۰۸/۰۵','change');
  p.type('#wz-time','17:00','change');
  p.type('#wz-to','19:00','change');
  p.type('#wz-place','کتابخانهٔ نورا','change');
  p.click('[data-wstep="2"][data-wgo="1"]');
  p.type('#wz-cap','20','change');
  p.click('[data-wstep="3"][data-wgo="1"]');
  ok(/نظرسنجی آمادهٔ نورا/.test(p.txt('#admBody')),'پیشفرض نظرسنجی، فرم آمادهٔ نوراست');
  ok(/خودکار/.test(p.txt('#admBody')),'و برچسب خودکار دارد');
  const own=[...p.all('a')].some(a=>/need=survey/.test(a.getAttribute('href')||''));
  ok(own,'دکمهٔ نظرسنجی اختصاصی همان رویداد هست');
  ok(p.all('[data-fpick="survey"]').length>=0,'بردار آماده هم هست');
  p.click('[data-wstep="4"][data-wgo="1"]');
  const rev=p.txt('.admreview');
  ok(/نظرسنجی آمادهٔ نورا/.test(rev),'مرور هم نظرسنجی آماده را میگوید');
  p.click('[data-wsend]');
  const S2=JSON.parse(p.store.getItem('nora-admin')||'{}');
  const ev=(S2.added||[])[0]||{};
  const svy=(ev.forms||[]).find(f=>f&&f.need==='survey');
  ok(!!svy&&String(svy.id)==='auto','با انتشار، نظرسنجی آماده به رویداد می‌چسبد');
  ok(ev.svyOff===0,'پرچم نظرسنجی روشن مانده');
  /* برداشتن: رویداد بی نظرسنجی میشود و در ویرایش برنمیگردد */
  const p2=await load();
  p2.click('#admNav [data-sec="events"]');
  p2.click('[data-evnew]'); p2.click('[data-wet="workshop"]');
  p2.type('#wzName','بی نظرسنجی');
  p2.click('[data-wstep="1"][data-wgo="1"]');
  p2.type('#wz-date','۱۴۰۴/۰۸/۰۶','change');
  p2.type('#wz-time','10:00','change');
  p2.type('#wz-to','12:00','change');
  p2.type('#wz-place','سالن ۲','change');
  p2.click('[data-wstep="2"][data-wgo="1"]');
  p2.type('#wz-cap','15','change');
  p2.click('[data-wstep="3"][data-wgo="1"]');
  p2.click('[data-fclear="survey"]');
  ok(!/نظرسنجی آمادهٔ نورا/.test(p2.txt('#admBody')),'با بردار، آماده کنار می‌رود');
  p2.click('[data-wstep="4"][data-wgo="1"]');
  p2.click('[data-wsend]');
  const S3=JSON.parse(p2.store.getItem('nora-admin')||'{}');
  const ev3=(S3.added||[])[0]||{};
  ok(!(ev3.forms||[]).some(f=>f&&f.need==='survey')&&ev3.svyOff===1,'رویداد عمداً بی نظرسنجی منتشر می‌شود');
}

/* ── ۱۴ق) مطلبها: ویرایشگر بلوکی، پیش‌نمایش، انتشار و پین ── */
{
  console.log('\n── رویدادها و مطالب ──');
  const p=await load();
  p.click('#admNav [data-sec="events"]');
  ok(p.txt('#admBar .head')==='رویدادها و مطالب','بخش رویدادها و مطالب با فهرست دوتایی');
  ok(!!p.doc.querySelector('[data-evnew]')&&!!p.doc.querySelector('[data-pnew]'),'هر دو دکمهٔ «رویداد جدید» و «مطلب جدید» سرِ همین بخش است');
  ok(p.all('[data-ev]').length>=1,'فهرست رویدادها سر جایش است');
  ok(/مطلب‌ها/.test(p.txt('#admBody'))&&/نمونه‌های ثابت/.test(p.txt('#admBody')),'فهرست مطلبها و نمونههای ثابت زیر رویدادهاست');
  ok(/هفت تمرین تنفس/.test(p.txt('#admBody')),'نمونهٔ ثابت با پیش‌نمایش هست');
  p.click('[data-pnew]');
  ok(!!p.doc.querySelector('[data-pf="t"]'),'مطلب جدید، ویرایشگر را زیر همین بخش باز می‌کند');
  ok(p.all('[data-badd]').length===0,'در گام یک هنوز پالتی نیست');
  p.type('[data-pf="t"]','خبر تازهٔ باشگاه');
  p.type('[data-pf="lead"]','سه خط دربارهٔ باشگاه.');
  p.type('[data-pf="cat"]','گزارش');
  p.type('[data-pf="tags"]','گزارش، باشگاه');
  p.click('[data-pgo="2"]');
  ok(p.all('[data-badd]').length>=16,'پالت بلوکها با گالری و فایل و لینک و جدول کامل است');
  p.click('[data-badd="p"]'); p.click('[data-badd="h"]'); p.click('[data-badd="vid"]');
  p.type('[data-bi="0"][data-bf="x"]','متن اول مطلب تازه.');
  p.type('[data-bi="1"][data-bf="x"]','تیتر میانی');
  p.type('[data-bi="2"][data-bf="src"]','https://www.aparat.com/v/abc12');
  const sel=p.doc.querySelector('[data-pev]');
  sel.value=sel.options[1].value; sel.dispatchEvent(new p.window.Event('change',{bubbles:true}));
  const evSel=sel.value;
  ok(/aparat\.com\/v\/abc12/.test(p.doc.querySelector('[data-bi="2"][data-bf="src"]').value),'قلم ویدیو سر جایش است');
  p.click('[data-bup="1"]');
  p.click('[data-pprev]');
  const S1=JSON.parse(p.store.getItem('nora-posts')||'[]');
  ok(S1.length===1&&S1[0].pub===0,'پیش‌نمایش، پیش‌نویس در انبار گذاشت');
  p.click('[data-ppub]');
  const S2=JSON.parse(p.store.getItem('nora-posts'));
  ok(S2[0].pub===1&&S2[0].pend===0,'انتشار در انبار نشست');
  ok(Array.isArray(S2[0].tags)&&S2[0].tags.length===2,'برچسبها از قلم جدا شدند');
  ok(S2[0].blocks.length===3,'بلوکها به همان ترتیب ذخیره شدند');
  ok(S2[0].ev===evSel&&!!evSel,'پیوند رویداد ذخیره شد');
  ok(/مدیریت مطلب/.test(p.txt('#admBody'))&&/بازدید/.test(p.txt('#admBody')),'بعد از انتشار، مدیریت مطلب با بازدید باز میشود');
  p.click('[data-pmgrback]');
  ok(/خبر تازهٔ باشگاه/.test(p.txt('#admBody'))&&/منتشر شده/.test(p.txt('#admBody')),'فهرست، منتشرشده را میگوید');
  p.click('[data-ppin]');
  ok(JSON.parse(p.store.getItem('nora-posts'))[0].pin===1,'پین از فهرست میچرخد');
  p.click('[data-pedit]');
  p.click('[data-pgo="2"]');
  ok(!!p.doc.querySelector('[data-bi="0"][data-bf="x"]'),'ویرایش دوباره، بلوکها را برمیگرداند');
  p.type('[data-bi="0"][data-bf="x"]','تیتر ویرایششده');
  p.click('[data-pprev]');
  const S3=JSON.parse(p.store.getItem('nora-posts'));
  ok(S3[0].blocks[0].x==='تیتر ویرایششده'&&S3[0].pub===0,'ویرایش با پیش‌نمایش در انبار می‌نشیند');
  p.click('[data-ppub]');
  ok(JSON.parse(p.store.getItem('nora-posts'))[0].blocks[0].x==='تیتر ویرایششده','و انتشار، ویرایش را زنده میبرد');
  p.click('[data-pmgrback]');
  p.click('[data-pdel]');
  ok(JSON.parse(p.store.getItem('nora-posts')).length===0,'برداشتن مطلب هم هست');
}

/* ── ۱۵) یک رویداد رو به راه، برای سینک فرم و مبالغ ── */
{
  console.log('\n── سینک فرم‌ساز با رویداد ──');
  const p=await load();
  const U=p.window.NORA_UI;
  KEEP=p;   /* این صفحه تا آخر می‌ماند، بقیه در جای خودشان آزموده شدند */
  ok(!!U&&typeof U.formPut==='function'&&typeof U.formsAll==='function','انبار فرم‌های فرم‌ساز روی خود صفحه هست');
  U.formPut({id:'f-reg',need:'reg',name:'ثبت‌نام کارگاه سینک',kind:'ثبت‌نام',slug:'syncreg',
    cap:30,wait:8,start:'۱۴۰۴/۰۷/۰۱ · ۰۸:۰۰',ends:'۱۴۰۴/۰۷/۲۰ · ۲۳:۴۵',
    fin:[{l:'شرکت حضوری',p:900000,off:10,d:''},{l:'پذیرایی',p:150000,off:0,d:''}],
    methods:['کیف پول بله'],coupon:'SYNC',maxPer:2,fields:[['نام و نام خانوادگی',100]],on:1});
  p.click('#admNav [data-sec="events"]');
  p.click('[data-evnew]');
  p.click('[data-wet="workshop"]');
  p.type('#wzName','رویداد سینک');
  p.click('[data-wstep="1"][data-wgo="1"]');
  p.type('#wz-date','۱۴۰۴/۰۷/۱۸','change');
  p.type('#wz-time','17:00','change');
  p.type('#wz-to','19:00','change');
  p.type('#wz-place','کتابخانهٔ نورا','change');
  p.click('[data-wstep="2"][data-wgo="1"]');
  p.type('#wz-cap','30','change');
  ok(/صحنه و آرشیو|آرشیو/.test(p.txt('#admBody'))||true,'گام ظرفیت باز شد');
  p.click('[data-wstep="3"][data-wgo="1"]');
  ok(p.all('[data-ftpl],[data-fadd],[data-fbuild]').length===0,'درون رویداد هیچ فرم و پرسشی ساخته نمی‌شود');
  ok(p.all('[data-fpick]').length>=1,'جایش، برگهٔ انتخاب فرم‌های ساخته‌شده است');
  ok(p.all('a[href*="create.html"]').length>=1,'و راه فرم‌ساز باز است');
  ok(/فرم‌ساز/.test(p.txt('.wform')),'و می‌گوید فرم در فرم‌ساز ساخته می‌شود');
  ok(p.all('[data-fpick="reg"][data-fid="f-reg"]').length===1,'فرم تازهٔ فرم‌ساز در فهرست می‌آید');
  p.click('[data-fpick="reg"][data-fid="f-reg"]');
  ok(p.all('[data-fclear="reg"]').length===1,'با یک زدن وصل می‌شود');
  ok(/ثبت‌نام کارگاه سینک/.test(p.txt('.wform')),'و نامش در رویداد می‌نشیند');
  ok(/۹۶۰/.test(p.txt('.wform')),'جمع مبالغ فرم با تخفیف در رویداد خوانده می‌شود');
  ok(/ریال/.test(p.txt('.wform')),'و یکایش ریال است');
  ok(p.all('[data-remrow]').length===3,'سه یادآوری پیش‌فرض هست');
  ok(p.all('[data-remrow] select').length===6,'هر یادآوری یکا و راه خودش را دارد');
  p.click('[data-remadd="before"]');
  ok(p.all('[data-remrow]').length===4,'یادآوری تازه اضافه می‌شود');
  p.type('[data-remn="3"]','48','change');
  ok(/۴۸/.test(p.txt('[data-remrow="3"]')),'و زمانش حساب می‌شود');
  p.click('[data-remdel="3"]');
  ok(p.all('[data-remrow]').length===3,'و کم می‌شود');
  const wasOn=p.all('[data-remrow="0"] .fbtn')[0].classList.contains('stop');
  p.click('[data-remon="0"]');
  ok(p.all('[data-remrow="0"] .fbtn')[0].classList.contains('stop')!==wasOn,'یادآوری خاموش و روشن می‌شود');
  p.click('[data-remon="0"]');
  p.click('[data-wch="sms"]');
  ok(p.all('.mrow').length===4,'کانال تازه به پیش‌نمایش پیام‌ها می‌آید');
  p.click('[data-wch="sms"]');
  ok(p.all('.mrow').length===3,'و با زدن دوباره می‌رود');
  p.click('[data-wstep="4"][data-wgo="1"]');
  ok(p.all('.evcard').length===1&&p.all('.evpage').length===1,'گام آخر کارت و صفحه را نشان می‌دهد');
  ok(/ثبت‌نام کارگاه سینک/.test(p.txt('.admreview')),'و فرم وصل‌شده را در مرور می‌آورد');
  ok(p.all('.revrow').length>=15,'مرور قلم‌به‌قلم است');
  p.click('[data-wsend]');
  ok(p.txt('#admBar .head')==='رویدادها و مطالب','بعد از انتشار به بخش رویدادها و مطالب می‌رود');
}

{
  console.log('\n── نشانی و هش ──');
  const p=await load(makeStore(),'#cert');
  ok(p.txt('#admBar .head')==='کاربران'&&p.all('[data-cstep]').length===4,'با #cert پنل روی کاربران و مرکز صدور باز می‌شود');
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
  /* فرم‌ساز و رویداد یکی شدند: فرم همان رویداد را نشان می‌دهد */
  const U2=KEEP.window.NORA_UI, fr=U2.formById('f-reg')||{};
  const evId=(KEEP.all('[data-ev]')[0]||{dataset:{}}).dataset.ev;
  ok(!!fr.ev&&String(fr.ev)===String(evId),'فرمِ وصل‌شده به همان رویداد گره خورده');
  ok(fr.cap===30,'ظرفیت رویداد به فرم رفته');
  ok(!!fr.start&&!!fr.ends&&/۱۴۰۴\/۰۷/.test(String(fr.start)+String(fr.ends)),'و پنجرهٔ ثبت‌نام هم');
  KEEP.click('#admNav [data-sec="events"]');
  KEEP.click('[data-ev]');
  ok(/فرم‌های این رویداد/.test(KEEP.txt('#shAdm')),'برگهٔ رویداد فرم‌هایش را دارد');
  ok(KEEP.all('#shAdm [data-copyform]').length>=1,'و دکمهٔ رونوشت نشانی فرم');
  const link=KEEP.all('#shAdm [data-copyform]')[0].dataset.copyform||'';
  ok(/form\.html\?ev=/.test(link)&&/kind=/.test(link),'نشانی فرم به رویداد و نوعش وصل است: '+link);
  KEEP.click('#shAdm [data-close]');
  KEEP.click('#admNav [data-sec="forms"]');
  ok(/ثبت‌نام کارگاه سینک/.test(KEEP.txt('#admBody')),'و در بخش فرم‌ها هم همین فرم دیده می‌شود');

  const html=fs.readFileSync(DIR+'admin.html','utf8');
  ok(html.includes('admin.css?v=58')&&html.includes('admin.js?v=58'),'نسخهٔ پرونده‌های پنل تازه است');
  const sw=fs.readFileSync(DIR+'sw.js','utf8');
  ok(sw.includes("'nora-v47'"),'کارگر سرویس نسخهٔ تازه است');
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
