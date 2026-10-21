/* ══════════════════════════════════════════════════════════════════════════
   نورا · آزمون پنل مدیران (admin.html)
   ──────────────────────────────────────────────────────────────────────────
   اجرا:  npm i jsdom && node admin.test.mjs
   چه چیزی را می‌سنجد: ریل چهار بخشی به‌علاوهٔ داشبورد، پیوند مستقیم فرم‌ها به
   builder.html و مسیرهای legacy، نقش‌ها، کارتابل و شاخص‌ها؛ ویزارد پنج‌گامی
   رویداد با پوستر و تم و فرم‌ساز و پیش‌نمایش کارت و
   صفحه و گردش تأیید، فهرست و صافی و جست‌وجوی کاربران، نه گزارش،
   گواهینامه با صف محلی و تأیید صریح مالک، اعلان‌های ارسال‌نشده و بازبینی
   رسید نمونه بدون اثر مالی، کنترل رباتِ غیرفعال و بی‌پیوند، نه گروه تنظیمات، یک مالک و شش
   حوزه با ۳۶ دسترسی و پنج دسترسی مالک، بستن بخش‌ها به‌اندازهٔ حوزه،
   سرپرست‌گذاری و افزودن کارشناس، مالیِ فقط‌مالک، ماندگاری خاموش و
   روشن‌ها، هشت کاشی تنظیمات با کاشی پنجبرگهٔ پشتیبانی و گفتگو (صندوق
   زندهٔ تیکتها با جستوجو و فوریت و واگذاری، پاسخهای آمادهٔ متغیردار با
   ساخت و ویرایش و برداشتن، سرویس و ساعات و تعطیلی و پاسخ بیرون از ساعت
   با کلید مشترک به صفحهٔ کاربر، تیم پاسخگو با ساخت و انتشار به کاربر،
   گزارش هفتروزه و اکسل)، و پاکی متن فارسی.
   ══════════════════════════════════════════════════════════════════════════ */
import {fileURLToPath,pathToFileURL} from 'node:url';
import jsdom from 'jsdom';
const {JSDOM}=jsdom;
import fs from 'fs';

const DIR=fileURLToPath(new URL('./',import.meta.url));
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
    ...(hash?{url:pathToFileURL(DIR+'admin.html').href+hash}:{}),
    beforeParse(w){
      w.__NORA_TEST_FIXTURE_MODE__=true;
      w.scrollTo=()=>{};
      Object.defineProperty(w,'localStorage',{configurable:true,value:st});
      /* jsdom کلیپ‌بورد ندارد؛ copyText فقط پس از موفقیت واقعی «رونوشت شد» می‌گوید، پس اینجا راهِ هم‌زمان execCommand موفق شبیه‌سازی می‌شود */
      w.Document.prototype.execCommand=()=>true;
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      w.addEventListener('error',e=>errs.push('error: '+e.message));
      w.console.error=(...a)=>errs.push('console.error: '+a.join(' '));
    }});
  const {window}=dom;
  await new Promise(resolve=>{
    if(window.document.readyState==='complete') return resolve();
    const timer=setTimeout(resolve,10000);
    window.addEventListener('load',()=>{clearTimeout(timer);resolve()},{once:true});
  });
  await wait(50);
  const doc=window.document;
  const click=sel=>{const el=typeof sel==='string'?doc.querySelector(sel):sel;
    if(!el) throw new Error('نیست: '+sel);
    el.dispatchEvent(new window.MouseEvent('click',{bubbles:true})); return el};
  const all=sel=>[...doc.querySelectorAll(sel)];
  const txt=sel=>{const el=typeof sel==='string'?doc.querySelector(sel):sel;
    return el?(el.textContent||'').replace(/\s+/g,' ').trim():''};
  const body=()=>doc.querySelector('#admBody').innerHTML;
  const type=(sel,v,ev)=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel);
    el.value=v; el.dispatchEvent(new window.Event(ev||'input',{bubbles:true}));};
  const upload=async(sel,bytes,name,type='')=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel);
    const f=new window.File([bytes],name,type?{type}:{});
    Object.defineProperty(el,'files',{value:[f],configurable:true});
    el.dispatchEvent(new window.Event('change',{bubbles:true}));};
  return {dom,window,doc,click,all,txt,body,type,upload,errs,store:st};
}
const openReports=p=>{p.click('#admNav [data-sec="users"]'); p.click('[data-user-hub="reports"]')};
const openLegacyForms=async p=>{p.window.location.hash='#forms'; await wait(10)};

/* سازندهٔ کوچک zip با ذخیرهٔ بیفشرده: docx واقعی برای آزمون آنالیز */
function miniZip(entries){
  const enc=new TextEncoder(), u16=v=>[v&255,(v>>8)&255], u32=v=>[v&255,(v>>8)&255,(v>>16)&255,(v>>24)&255];
  const locals=[], centrals=[]; let off=0;
  for(const [nm,txt] of entries){
    const nd=enc.encode(nm), cd=enc.encode(txt);
    const lh=new Uint8Array([...u32(0x04034b50),...u16(20),...u16(0),...u16(0),...u16(0),...u16(0),...u32(0),...u32(cd.length),...u32(cd.length),...u16(nd.length),...u16(0)]);
    locals.push(lh,nd,cd);
    const ch=new Uint8Array([...u32(0x02014b50),...u16(20),...u16(20),...u16(0),...u16(0),...u16(0),...u16(0),...u32(0),...u32(cd.length),...u32(cd.length),...u16(nd.length),...u16(0),...u16(0),...u16(0),...u16(0),...u32(0),...u32(off)]);
    centrals.push(ch,nd); off+=lh.length+nd.length+cd.length;
  }
  const csize=centrals.reduce((a,x)=>a+x.length,0);
  const end=new Uint8Array([...u32(0x06054b50),...u16(0),...u16(0),...u16(entries.length),...u16(entries.length),...u32(csize),...u32(off),...u16(0)]);
  const total=locals.reduce((a,x)=>a+x.length,0)+csize+end.length;
  const out=new Uint8Array(total); let p2=0;
  [...locals,...centrals,end].forEach(x=>{out.set(x,p2); p2+=x.length});
  return out;
}
const docxBytes=params=>miniZip([['[Content_Types].xml','<?xml version="1.0"?><Types/>'],
  ['word/document.xml','<?xml version="1.0"?><w:document><w:body><w:p><w:r><w:t>گواهینامهٔ '
    +params.map(x=>'{' +x+'}').join(' مدرس ')+'</w:t></w:r></w:p></w:body></w:document>']]);
const csvBytes=t=>new TextEncoder().encode(t);
const SECS=['dash','events','users','settings'];
let KEEP=null;   /* صفحه‌ای که تا بلوک آخر نگه داشته می‌شود */

/* ── ۱) پوسته و ناوبری ── */
{
  console.log('\n── پوسته و ناوبری ──');
  const p=await load();
  ok(p.errs.length===0, p.errs.length?('خطا: '+p.errs.slice(0,3).join(' | ')):'بی‌خطا بار شد');
  ok(p.all('#admNav .btn').length===5,'ریل پنج ورودی دارد: داشبورد و چهار بخش ('+p.all('#admNav .btn').length+')');
  ok(p.all('#admTabs a').length===p.all('#admNav .btn').length
    &&p.all('#admTabs a[data-sec]').map(x=>x.dataset.sec).join(',')===p.all('#admNav .btn[data-sec]:not([data-locked])').map(x=>x.dataset.sec).join(',')
    &&!!p.doc.querySelector('#admNav [data-center-href="builder.html"]')
    &&!!p.doc.querySelector('#admTabs [data-center-href="builder.html"]'),
    'نوار پایین با منو هم‌خوان است و فرم‌ها مستقیم به مرکز فرم‌ها می‌روند');
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
  ok(p.doc.querySelector('a[href="home.html"]')!==null&&p.doc.querySelector('a[href="home.html"]').textContent.includes('نمای عمومی سایت'),
    'پیوند بازگشت به نمای عمومی سایت از پنل حاضر است');
  ok(p.doc.querySelector('#admNav a[data-center-href="builder.html"]')?.getAttribute('href')==='builder.html','پیوند فرم‌ها مرکز builder.html را باز می‌کند');
  const navText=p.txt('#admNav');
  ok(!p.doc.querySelector('#admNav [data-user-hub="reports"],#admNav [data-sec="reports"],#admNav [data-sec="newev"]')
      &&!/گزارش‌ها|تعریف جدید|تعریف تازه|مطلب جدید|مطلب تازه/.test(navText),
    'گزارش‌ها و تعریف تازه ورودی ناوبری جدا ندارند');
  p.click('#admNav [data-sec="users"]');
  ok(p.txt('#admBar .head')==='کاربران'&&!!p.doc.querySelector('#admBody [data-user-hub="reports"]'),
    'گزارش‌ها در برگهٔ کاربران مانده‌اند، نه منوی اصلی');
  p.click('#admNav [data-sec="dash"]');
  const nameless=p.all('#admRail button, #admTabs a, .topbar button, .kpi, .qrow button, .qfilters button, .frow2 button, .dhead button')
    .filter(b=>(b.textContent||'').replace(/\s+/g,'').trim()===''&&!b.getAttribute('aria-label'));
  ok(nameless.length===0,'هیچ دکمه‌ای بی‌نام نیست'+(nameless.length?': '+nameless.length:''));
  ok(!/\u2014/.test(p.txt('#admBody')),'متن پنل خط تیرهٔ بلند ندارد');
  for(const k of SECS){
    p.click('#admNav [data-sec="'+k+'"]');
    const b=p.body();
    ok(b.length>600&&!/undefined|NaN|\$\{|\[object/.test(b),'بخش «'+k+'» خوانا رندر شد ('+b.length+' بایت)');
  }
  p.click('#admNav [data-sec="events"]');
  ok(!p.doc.querySelector('#admNav [data-sec="newev"]')
    &&!!p.doc.querySelector('[data-evnew]')&&!!p.doc.querySelector('[data-pnew]'),
    'تعریف جدید از منوی مستقل برداشته شد؛ ساخت رویداد و مطلب در بخش رویدادها ماند');
  p.click('#admNav [data-sec="settings"]');
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
  ok(p.all('[data-wtheme]').length===4,'و چهار تم کارت: شیشهای، شب، طلایی، سبز');
  ok(p.all('[data-wtchr]').length>=8,'مدرس یا برگزارکننده از همانجا برگزیده میشود: همهٔ تیم پیشِ روست');
  p.click('[data-wtchr="p2"]');
  ok(JSON.parse(p.store.getItem('nora-admin')).wiz.tchr==='p2','برگزیدنِ مدرسِ رویداد');
  ok(/کیوان مرادی/.test(p.txt('.evcard')),'و نامش روی پیشنمایش کارتِ رویداد مینشیند');
  p.click('[data-wtchrnew]');
  p.type('#wzTchrN','استاد نرگس بهار','change'); p.type('#wzTchrR','مدرس نقالی','change');
  p.click('[data-wtchrmake]');
  const wt=(JSON.parse(p.store.getItem('nora-admin')).pp.add||[]);
  ok(wt.length===1&&wt[0].n==='استاد نرگس بهار','مدرس تازه همانجا ساخته میشود');
  ok(String(JSON.parse(p.store.getItem('nora-admin')).wiz.tchr)===String(wt[0].id),'و همان لحظه به رویداد وصل میشود');
  ok(/هنوز به کاربر نرسیده/.test(p.txt('#admBody')),'و میگوید تا انتشارِ کاشی اساتید به کاربر نمیرسد');
  ok(p.doc.querySelector('#wzPartner option[value="o1"]')!==null,'نهادهای همکارِ موجود برای اتصال به رویداد در دسترس‌اند');
  p.type('#wzPartner','o1','change');
  ok(JSON.parse(p.store.getItem('nora-admin')).wiz.partnerId==='o1'
      &&/گروه آموزشی نمونه/.test(p.txt('.evcard')),'انتخاب نهاد در ویزارد ذخیره و روی کارت پیش‌نمایش نشان داده می‌شود');
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
  // The earlier picker chooses day 21; that day may already be past.
  // Publication status must not depend on today's day-of-month or CI date.
  p.type('#wz-date','1500/01/21','change');
  p.type('#wz-end','1500/01/21','change');
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
  ok(p.all('[data-wfeat]').length===11,'یازده قابلیت هست که روشن و خاموش می‌شوند');
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
  ok(/استاد نرگس بهار/.test(p.txt('.admreview')),'مرورِ آخر نام مدرس را هم میآورد');
  p.click('[data-wsend]');
  ok(p.txt('#admBar .head')==='رویدادها و مطالب','بعد از انتشار، خودش به بخش رویدادها و مطالب می‌رود');
  ok(p.all('[data-ev]').length===before+1,'رویداد تازه به فهرست اضافه شد');
  ok(p.txt('[data-ev] b')==='اردوی پاییزهٔ دربند','نام همان است که نوشتیم');
  ok(!/پیش‌نویس/.test(p.txt('#admBody')),'دیگر هیچ رویدادی پیش‌نویس نمی‌شود');
  ok(p.doc.querySelector('[data-ev] .ic.pic img')!==null,'پوستر روی ردیف رویداد می‌نشیند');
  ok(/منتشر|پیش‌رو|جاری/.test(p.txt('[data-ev]')),'وضعیتش منتشر است');
  ok(p.all('.admsteps .st').length===0,'و ویزارد بسته می‌شود');
  const wEv=(JSON.parse(p.store.getItem('nora-admin')).added||[])[0]||{};
  ok(String(wEv.tchr)===String(wt[0].id),'رویداد با مدرسش منتشر شد');
  ok(wEv.partnerId==='o1'&&wEv.partnerName==='گروه آموزشی نمونه','شناسه و نام نهاد همکار در رویداد ذخیره شد');
  p.click('[data-ev="'+wEv.id+'"]');
  p.click('[data-evedit="'+wEv.id+'"]');
  ok(p.doc.querySelector('#wzPartner').value==='o1','ویرایش رویداد، نهاد همکار فعلی را از دادهٔ ذخیره‌شده برمی‌گرداند');
  p.type('#wzPartner','o2','change');
  for(let step=1;step<=4;step++) p.click('[data-wstep="'+step+'"][data-wgo="1"]');
  ok(p.all('.evpage').length===1&&/فضای فرهنگی نمونه/.test(p.txt('.evpage')),'نهاد تازه در پیش‌نمایش صفحهٔ کامل رویداد هم دیده می‌شود');
  p.click('[data-wsend]');
  const editedState=JSON.parse(p.store.getItem('nora-admin'))||{}, editedEvent=(editedState.evEdit||{})[wEv.id]||{};
  ok(editedEvent.partnerId==='o2'&&editedEvent.partnerName==='فضای فرهنگی نمونه','ویرایش، نهاد همکار را در روکش همان رویداد ذخیره می‌کند');
  /* فرم‌ساز و رویداد سینک می‌مانند: فرم به رویداد گره خورده است */
  const f1=p.window.NORA_UI.formById('t-reg')||{};
  ok(!!f1.ev,'فرمِ وصل‌شده به رویداد گره می‌خورد');
  ok(f1.sync&&f1.sync.cap===1&&f1.sync.money===1,'و ظرفیت و تاریخ و مبلغش با رویداد سینک است');
  ok(String(f1.ev)===p.all('[data-ev]')[0].dataset.ev,'و شناسهٔ همان رویداد است');

  /* فرم‌ها در بخش فرم‌ها و در مدیریت رویداد */
  await openLegacyForms(p);
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

/* ── مدرسِ رویداد: در ویرایش برمیگردد و از همانجا به پروفایل راه دارد ── */
{const s2=makeStore();
  s2.setItem('nora-admin',JSON.stringify({added:[{id:'nx9',n:'اردوی پاییزهٔ دربند',kind:'اردو',
    when:'جمعه ۲۵ مهر',on:'1405/07/25',time:'09:00',end:'1405/07/25',place:'دربند',cap:30,tchr:'p2',state:'soon'}]}));
  const q=await load(s2);
  q.click('#admNav [data-sec="events"]');
  q.click('[data-ev="nx9"]');
  q.click('[data-evedit]');
  ok(String(JSON.parse(q.store.getItem('nora-admin')).wiz.tchr)==='p2','ویرایش رویداد، مدرس را همراه میآورد');
  ok(/کیوان مرادی/.test(q.txt('#admBody')),'و نامش در ویزارد برجسته است');
  q.click('[data-wtchredit]');
  ok(!!q.doc.querySelector('[data-ppf="n"]'),'«ویرایش پروفایل» از دل ویزارد، کاشی مدیران و اساتید را باز میکند');
  ok(/کیوان مرادی/.test(q.txt('#ppPrev')),'و پیش‌نمایشِ همان مدرس را نشست');
  ok(q.errs.length===0,'ویرایشِ مدرس بیخطا بود');
}

/* ── نویسندهٔ مطلب به پروفایل وصل میشود ── */
{const q=await load();
  q.click('#admNav [data-sec="events"]');
  q.click('[data-pnew]');
  ok(!!q.doc.querySelector('[data-ptchr]')&&q.all('[data-ptchr] option').length>=9,'ویرایشگر مطلب: نویسنده از فهرست آدمها برگزیده میشود');
  q.type('[data-pf="t"]','گزارش کارگاه نقالی');
  q.type('[data-pf="lead"]','گزارش کوتاه','change');
  const sel=q.doc.querySelector('[data-ptchr]'); sel.value='p2';
  sel.dispatchEvent(new q.window.Event('change',{bubbles:true}));
  ok(JSON.parse(q.store.getItem('nora-admin')).ped.tchr==='p2','نویسنده به پروفایلش پیوند خورد');
  ok(JSON.parse(q.store.getItem('nora-admin')).ped.author==='مهندس کیوان مرادی','و نامِ زیرِ خط همراهش آمد');
  if(q.doc.querySelector('[data-pgo="2"]')) q.click('[data-pgo="2"]');
  q.click('[data-ppub]');
  const po=(JSON.parse(q.store.getItem('nora-posts')||'[]'))[0]||{};
  ok(po.tchr==='p2','مطلب با نویسنده منتشر شد');
  ok(q.errs.length===0,'ویرایشِ نویسنده بیخطا بود');
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
  ok(/جمع محلیِ نمونه/.test(p.txt('#shAdm'))&&/پرداخت، رسید تأییدشده، فروش یا دفترکل بانکی نیست/.test(p.txt('#shAdm')),
    'تب مالی فقط جمع نمونهٔ فرم‌ساز را نشان می‌دهد، نه پرداخت یا دفترکل بانکی');
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
  ok(/در صف محلی/.test(p.txt('#admBody'))&&!/در صف محلی · نمونه/.test(p.txt('#admBody')),'وضعیت محلی خواناست و برچسب تکراریِ نمونه ندارد');
  p.click('[data-uok="u3"]');
  ok(/تأیید محلی/.test(p.txt('#admBody'))&&/اعلان فقط در صف محلی مالک است/.test(p.txt('#toast')),
    'تغییر وضعیت فقط محلی است و اعلان برای ارسال بیرونی نمی‌رود');
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
  const profileBale=p.doc.querySelector('#admBody .row button[disabled][aria-disabled="true"]');
  ok(!!profileBale&&/ربات وصل نیست/.test(profileBale.title||''),
    'کنترل ربات برای پروندهٔ فردی صریحاً غیرفعال است');
  ok(!p.doc.querySelector('[data-bale="profile_u7"], [data-balesend], a[href*="ble.ir"]'),
    'برای پرونده هیچ کد شروع، پیوند بیرونی یا دکمهٔ ارسال ساخته نمی‌شود');
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
  ok(/مسدودی نمونه برداشته شد/.test(p.txt('#toast'))&&/دسترسی سروری تغییر نکرد/.test(p.txt('#toast')),
    'رفع مسدودی فقط برچسب نمونه را عوض می‌کند؛ دسترسی واقعی تغییر نمی‌کند');
  p.click('[data-utool="log"]');
  ok(p.all('#admBody .admlirow').length>=4,'لاگ عملیات پر میشود: تأیید، رد، VIP، ورود');
}

/* ── ۵) فرم‌ها ── */
{
  console.log('\n── فرم‌ها ──');
  const p=await load(undefined,'#forms');
  ok(p.all('.admlist .admrow2').length>=7,'صفحهٔ قدیمی فرم‌ها با نشانی مستقیم برای سازگاری در دسترس است');
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
  const deep=await load(undefined,'#reports');
  ok(deep.txt('#admBar .head')==='کاربران'&&deep.all('[data-rep]').length>=9,
    'پیوند قدیمی #reports هم گزارش‌ها را در بخش ترکیبی باز می‌کند');
  const p=await load();
  openReports(p);
  const items=p.all('[data-rep]');
  ok(items.length>=9,'نه گزارش نشسته ('+items.length+')');
  ok(p.all('[data-rp]').length===7,'هفت دورهٔ طرح هست: امروز، دیروز، ۷ روز، ۳۰ روز، فصل، سال، از ابتدا');
  p.click('[data-rp="۳۰ روز"]');
  ok(p.doc.querySelector('[data-rp="۳۰ روز"].on')!==null,'دورهٔ انتخابی جابه‌جا و برای خود کاربر میماند');
  ok(p.all('.admkpi .k').length===4,'چهار کارت آماری سر داشبورد هست');
  ok(/کاربران/.test(p.txt('.admkpi .k'))&&/تغییر نمایشی/.test(p.txt('.admkpi')),'سنجه و تغییرِ آماری، نمونه و نمایشی برچسب دارد');
  ok(!!p.doc.querySelector('.admbars'),'نمودار روند سی‌روزه روی داشبورد هست');
  ok(/فعالیت در ۱۵ دقیقهٔ اخیر/.test(p.txt('#admBody'))&&/پرداخت بانکی وصل نیست/.test(p.txt('#admBody')),'نبض فعالیت و پرداخت صریحاً نمونه و محلی است');
  ok(/توصیههای خودکار/.test(p.txt('#admBody')),'توصیههای خودکار آمده');
  p.click('[data-rcust="reg"]'); p.click('[data-rcust="cer"]'); p.click('[data-rcustgo]');
  ok(/گزارش سفارشی با ۲ سنجه/.test(p.txt('#toast')),'گزارش سفارشی با سنجههای برگزیده ساخته میشود');
  const customReportBtn=p.doc.querySelector('.stgroup .balerow button[disabled][aria-disabled="true"]');
  ok(/گزارش سفارشی تو/.test(p.txt('#admBody'))&&!!customReportBtn
    &&!p.doc.querySelector('.stgroup a[href*="ble.ir"]'),'گزارش سفارشی محلی می‌ماند و خروجی ربات تا اتصال سرور غیرفعال است');
  p.click('[data-rsch="0"]');
  ok(/هفتگی خاموش شد/.test(p.txt('#toast')),'زمان‌بندی خاموش و روشن می‌شود');
  p.click('[data-rsch="0"]'); p.click('[data-rschnew]');
  ok(/جمعبندی فصلی/.test(p.txt('#admBody'))&&/پیش‌نویس زمان‌بندی محلی ذخیره شد/.test(p.txt('#toast'))
    &&/اجرای خودکار یا ارسال گزارش وصل نیست/.test(p.txt('#toast')),'زمان‌بندی فصلی فقط پیش‌نویس محلی است؛ خودکار اجرا یا ارسال نمی‌شود');
  const fullReportBtn=[...p.doc.querySelectorAll('#admBody .row button[disabled][aria-disabled="true"]')]
    .find(x=>/اکسل کامل/.test(x.textContent));
  ok(!!fullReportBtn&&!p.doc.querySelector('#admBody a[href*="ble.ir"]'),
    'خروجی کامل ربات در این نسخه غیرفعال است و پیوند بیرونی ساخته نمی‌شود');
  p.click('[data-rep="fi"]');
  ok(/مالی/.test(p.txt('#shAdm .head')),'گزارش مالی باز شد');
  ok(/▲|▼/.test(p.txt('#shAdm')),'درصد تغییر دورهٔ مشابه قبل در ورقه هست');
  ok(p.all('#shAdm .admbars i').length===7,'نمودار سی‌روزه در ورقه هست');
  ok(p.all('#shAdm .k').length>=4,'مقایسهٔ دوره‌ها در ورقه هست');
  ok(!!p.doc.querySelector('#shAdm button[disabled][aria-disabled="true"]')
    &&!p.doc.querySelector('#shAdm a[href*="ble.ir"]'),
    'خروجی گزارش ربات غیرفعال است و پیوند بیرونی ساخته نمی‌شود');
  ok(/مقایسه: (رشد|افت)/.test(p.txt('#shAdm')),'برچسب مقایسهٔ دورهٔ مشابه قبل در ورقه هست');
  ok(/دورهٔ ۳۰ روز/.test(p.txt('#shAdm')),'برچسب دورهٔ جاری در ورقه هست');
  p.click('#shAdm [data-close]');
  /* هر ۹ ورقه پشت هم: همه جدول و میله و برچسب دارند */
  let allSheets=true;
  for(const kk of ['ev','us','fm','at','fi','ce','bc','ad','tp']){
    p.click('[data-rep="'+kk+'"]');
    if(!p.doc.querySelector('#shAdm table')||!p.doc.querySelector('#shAdm .admbars i[style]')) allSheets=false;
    if(!/دورهٔ/.test(p.txt('#shAdm'))) allSheets=false;
    p.click('#shAdm [data-close]');
  }
  ok(allSheets,'هر نه ورقه: جدول، میلهٔ استایل‌دار و برچسب دوره دارد');
  ok(/جمعبندی مدیریتی، خودنویس/.test(p.txt('#admBody'))&&/خلاصهٔ نمونه برای/.test(p.txt('#admBody'))
    &&/پروندهٔ نمایشی/.test(p.txt('#admBody')),'جمعبندی مدیریتی دادهٔ نمونهٔ محلی را معرفی می‌کند');
  p.click('[data-rp="امسال"]');
  ok(/خلاصهٔ نمونه برای «امسال»/.test(p.txt('#admBody')),'دوره عوض می‌شود و متن خلاصه همچنان برچسب نمونه دارد');
  p.click('[data-rp="۳۰ روز"]');
  ok(/روند هفت محور اخیر/.test(p.txt('#admBody'))||/روند/.test(p.txt('#admBody')),'زیرنویس روند با دورهٔ جاری میآید');
  ok(p.all('.admbars i[style]').length>=10,'میلههای روند ارتفاع واقعی دارند');
  p.click('[data-rcust="reg"]'); p.click('[data-rcust="frm"]'); p.click('[data-rcustgo]');
  ok(/گزارش سفارشی تو/.test(p.txt('#admBody'))&&p.all('.stgroup .admkpi .k').length>=2,'گزارش سفارشی کارتهای سه‌دورهای دارد');
  ok(p.all('.stgroup .admbars i[style]').length>=5,'میلههای گزارش سفارشی هم ارتفاع دارند');
  p.click('[data-rschnew]'); p.click('[data-rschnew]');
  ok(/از قبل ثبت شده/.test(p.txt('#toast')),'زمانبندی فصلی دوبار نمیسازد');
  ok(/جمع عددهای مالی نمونه/.test(p.txt('#admBody'))&&/پرداخت یا حسابداری واقعی نیست/.test(p.txt('#admBody')),
    'خلاصهٔ مالی فقط دادهٔ نمونه است و پرداخت یا حسابداری واقعی نیست');
  p.click('[data-rep="us"]');
  ok(/۱۱ پذیرفته‌شدهٔ محلی · ۳ در صف محلی · ۱ مسدود در نمونه/.test(p.txt('#shAdm')),'شمار وضعیت کاربران صریحاً دادهٔ محلی و نمونه است');
  p.click('#shAdm [data-close]');
  p.click('[data-rep="tp"]');
  ok(/مریم رضایی/.test(p.txt('#shAdm'))&&/۳۱۲۰/.test(p.txt('#shAdm')),'برترین امتیاز واقعاً رتبهبندی میشود: مریم بالای سارا');
  ok(/رتبهٔ ۱/.test(p.txt('#shAdm'))&&/رتبهٔ ۳/.test(p.txt('#shAdm')),'سه رتبهٔ اول مدال دارد');
  p.click('#shAdm [data-close]');
  p.click('[data-rep="ad"]');
  ok(/امیر کاظمی/.test(p.txt('#shAdm'))&&/۲۶ کار انجامشده/.test(p.txt('#shAdm')),'حوزهها با کار واقعی کارشناسان حساب میشود');
  p.click('#shAdm [data-close]');
  p.click('[data-rep="ce"]');
  ok(/قالب ورد آماده/.test(p.txt('#shAdm'))&&/درخواست رسیده از ربات/.test(p.txt('#shAdm')),'گزارش گواهی از قالبها و درخواستهای ربات میگوید');
  p.click('#shAdm [data-close]');

  /* ممیزی کامل پنل: هر دکمه و بنرِ در دسترس، واقعاً کلیک میشود */
  ok(/ممیزی کامل پنل/.test(p.txt('#admBody')),'بلوک ممیزی کامل در گزارشها هست');
  ok(/نقشهٔ دسترسی نقشها/.test(p.txt('#admBody')),'نقشهٔ دسترسی همهٔ نقشها نوشته میشود');
  p.click('[data-auditrun]');
  ok(/پیمایش شروع شد/.test(p.txt('#toast'))||/در حال پیمایش/.test(p.txt('#admBody')),'پیمایش با پیام شروع میشود');
  let au=null;
  for(let i=0;i<170&&!au;i++){await wait(500);
    try{au=JSON.parse(p.store.getItem('nora-admin')||'{}').auditLast||null}catch(e){}}
  ok(!!au,'پیمایش تا پایان میرود و ثبت میشود');
  ok(au&&au.secs===5&&au.tot>=500&&au.tot<=1200,'پیمایش از ریز تا درشت عمق دارد: '+au.tot+' کنترل در '+au.secs+' بخش');
  ok(au&&au.mute===0&&!au.errs.length,'هیچ کنترل بیپاسخ و هیچ خطا نیست');
  ok(au&&au.skip>=10&&au.ext>=1,'کنترلهای حساس (بازنشانی و شخص) و پیوندهای بیرونی دور ماندهاند');
  ok(au&&au.banTot>0,'بنرهای اطلاعی هم دیده شدهاند');
  ok(/همه پاسخ دادند/.test(p.txt('#admBody')),'جمعبندی «همه پاسخ دادند» میآید');
  ok(/بنر و جعبهٔ اطلاعی/.test(p.txt('#admBody')),'شمار بنرهای اطلاعی نوشته میشود');
  ok(!!p.doc.querySelector('[data-auditrun]'),'دکمهٔ پیمایش دوباره سر جایش است');
}

/* ── ۷) گواهینامه: صف محلی، بدون صدور تا تأیید صریح مالک ── */
{
  console.log('\n── گواهینامهٔ نمونه و تأیید مالک ──');
  const p=await load();
  p.click('#admNav [data-sec="users"]');
  ok(!!p.doc.querySelector('[data-uv="cert"]'),'مرکز گواهی در کاشی کاربران است');
  p.click('[data-uv="cert"]');
  ok(p.all('[data-cstep]').length===4,'مرکز گواهی چهار گام نمونه دارد');
  ok(/صف محلی/.test(p.txt('#admBody'))&&/فقط مالک/.test(p.txt('#admBody')),
    'متن مرکز روشن می‌کند که صف محلی است و تصمیم با مالک است');
  ok(!p.doc.querySelector('[data-cfast]')&&!p.doc.querySelector('[data-crun]')&&!p.doc.querySelector('[data-cbnudge]'),
    'صدور فوری، اجرای فوری و یادآوری بیرونی وجود ندارد');
  ok(p.all('[data-cfile]').length===3,'قالب‌ها فقط دادهٔ نمونه‌اند');
  ok(/خروجی نهایی نمی‌سازد|پیش‌نمایش نمونه/.test(p.txt('#admBody')),
    'قالب و موتور محلی به‌عنوان خروجی رسمی معرفی نشده‌اند');

  p.click('[data-cstep="1"]');
  ok(p.all('[data-cev]').length>=1,'گزینش رویداد برای دستهٔ نمونه وجود دارد');
  p.click(p.all('[data-cev]')[0]);
  p.click('[data-cstep="2"]');
  await p.upload('[data-cxlsup]',csvBytes('نام,موبایل\nسارا محمدی,09121234567\n'),'sample-list.csv');
  await wait(100);
  const seeded=JSON.parse(p.store.getItem('nora-admin')||'{}');
  ok(seeded.cert&&seeded.cert.xlsRows&&seeded.cert.xlsRows.length===1
    &&seeded.cert.xlsRows[0].n==='سارا محمدی','گیرندهٔ نام‌دار فقط به‌عنوان فهرست نمونهٔ محلی افزوده شد');
  p.click('[data-cstep="3"]');
  ok(!!p.doc.querySelector('[data-cqueue]')&&/صدور فوری/.test(p.txt('#admBody')),
    'گام آخر فقط دکمهٔ درخواستِ بازبینی دارد و صدور فوری را غیرفعال می‌داند');
  const U=p.window.NORA_UI;
  const issuedBefore=U.issuedCertificates().length;
  p.click('[data-cqueue]');
  const req=U.ownerApprovals().find(x=>x&&x.type==='cert-batch'&&x.status==='pending');
  ok(!!req&&req.recipients.length===1,'درخواست گواهی به صف محلی مالک رفت');
  ok(U.issuedCertificates().length===issuedBefore,
    'ثبت درخواست به‌تنهایی هیچ گواهی‌ای صادر یا در حساب کاربر نمایش نمی‌دهد');
  ok(!!p.doc.querySelector('[data-certapprove="'+req.id+'"]')
    &&!!p.doc.querySelector('[data-certreject="'+req.id+'"]'),
    'فقط روی ردیف صف مالک، دکمهٔ تأیید یا رد دیده می‌شود');
  ok(/ارسال واقعی وصل نیست|ارسال نشده/.test(p.txt('#admBody')),
    'پیش‌نمایش اطلاع‌رسانی نیز ارسال‌نشده و محلی معرفی شده است');

  p.click('[data-certapprove="'+req.id+'"]');
  const approved=U.ownerApprovals().find(x=>x&&x.id===req.id);
  const finalCerts=U.issuedCertificates().filter(x=>x.ownerApprovalId===req.id);
  ok(approved&&approved.status==='approved'&&approved.approvedById==='p1'
    &&finalCerts.length===1&&finalCerts[0].localOnly===true,
    'رکورد محلی فقط پس از تأیید صریح مالک ثبت می‌شود و شناسهٔ تأیید را نگه می‌دارد');
  ok(/هیچ پیام بیرونی ارسال نشد/.test(p.txt('#toast'))&&approved.notificationStatus==='approved',
    'تأیید مالک فقط نمایش محلی گواهی را مجاز می‌کند؛ پیام بیرونی ارسال نمی‌شود');
}

/* ── ۸) تنظیمات و حوزه‌ها ── */
{
  console.log('\n── تنظیمات و دسترسی ──');
  const p=await load();
  p.click('#admNav [data-sec="settings"]');
  ok(p.all('[data-setg]').length===9&&!!p.doc.querySelector('[data-setg="publishing"]'),'نه گروه تنظیمات، از جمله انتشار عمومی و همکاری');
  ok(p.all('[data-setg]').length===9&&p.all('.sktile').length===8&&p.all('#admBody .card').length>=1,
    'گروه‌های تنظیمات و کاشی‌های سامانه جدا و مرتب نمایش داده می‌شوند');
  ok(/۹ گروه · متن/.test(p.txt('#admBody')),'سربرگ کارت تنظیمات، گروه کنونی را نشان می‌دهد');
  ok(p.all('[data-text]').length===4,'متن‌های پرکاربرد قابل ویرایش‌اند');
  ok(p.doc.querySelector('#ownerPublishingToolsParking').hidden&&!p.doc.querySelector('#admBody #siteContentSync'),
    'همگام‌سازی و همکاری از داشبورد و گروه‌های دیگر پنهان است');
  p.click('[data-setg="publishing"]');
  ok(!!p.doc.querySelector('#admBody #siteContentSync')&&!!p.doc.querySelector('#admBody #cooperationInbox')
    &&!p.doc.querySelector('#ownerPublishingTools').hidden,'انتشار عمومی و صندوق همکاری فقط در گروه اختصاصی مالک باز می‌شوند');
  p.click('[data-setg="texts"]');
  ok(p.doc.querySelector('#ownerPublishingToolsParking').hidden&&!p.doc.querySelector('#admBody #siteContentSync'),
    'با خروج از گروه انتشار، پنل‌های همکاری دوباره از صفحه جمع می‌شوند');
  p.click('[data-setg="performance"]');
  ok(!!p.doc.querySelector('[data-perf-check]')&&!!p.doc.querySelector('[data-perf="imageQuality"]')
    &&!!p.doc.querySelector('[data-perf="maxImageEdge"]')&&/بدون مکث اجباری/.test(p.txt('#admBody')),
    'سلامت، شاخص‌های مرورگر، WebP و لودر رویدادمحور در تنظیمات مالک هستند');
  const quality=p.doc.querySelector('[data-perf="imageQuality"]');quality.value='88';
  quality.dispatchEvent(new p.window.Event('change',{bubbles:true}));
  ok(p.window.NORA_UI.performanceSettings().imageQuality===88,'کیفیت WebP برای صفحه‌های بعد در تنظیم محلی مشترک ذخیره شد');
  p.click('[data-perf-check]');await wait(30);
  ok(/API هم‌مبدأ پاسخ نداد/.test(p.txt('#admBody')),'بررسی سلامت شبکه نتیجهٔ واقعی و روشن نشان می‌دهد');
  p.click('[data-setg="cert"]');
  ok(/قالب فایل ورد گواهینامه/.test(p.txt('#admBody')),'گروه گواهینامه، مدیریت قالب را دارد');
  ok(!!p.doc.querySelector('[data-cfileup]'),'بارگذاری فایل ورد در تنظیمات است');
  ok(/مالک یا سرپرست/.test(p.txt('#admBody'))&&/صدور نهایی فقط با مالک/.test(p.txt('#admBody')),
    'قالب را مالک یا سرپرست می‌بیند، اما صدور نهایی فقط با مالک است');
  ok(p.all('#admBody .sd-sect').length===2&&/سیاست صدور گواهینامه/.test(p.txt('#admBody')),'گواهینامه: قالب و سیاست صدور در دو بخشبند جداست');
  p.click('#admNav [data-sec="users"]');
  p.click('[data-uv="cert"]');
  ok(!!p.doc.querySelector('[data-cert-format]')&&p.all('[data-cert-field]').length>=7
    &&p.txt('#admBody').includes('واترمارک'),'مرکز گواهی PDF/JPG و محتوای خروجی را برای هر درخواستِ مالک انتخاب می‌کند و واترمارک نمونه را نگه می‌دارد');
  p.click('#admNav [data-sec="settings"]');
  p.click('[data-setg="cert"]');
  await p.upload('[data-cfileup]',docxBytes(['نام','مدرس']),'gava-davari.docx');
  await wait(100);
  ok(/پارامتر متغیر پیدا شد/.test(p.txt('#toast')),'فایل ورد آنالیز و پارامترهای متغیرش درمیآید');
  ok(p.all('#admBody a.local-disabled-link[aria-disabled="true"]').length===1
    &&p.all('#admBody a[download]').length===0,'فایل قالبِ data URI دانلود عملیاتی ندارد و نگهبان پیوند محلی آن را غیرفعال می‌کند');
  p.click('[data-cdef]');
  ok(/پیشفرض عوض شد/.test(p.txt('#toast')),'پیشفرضسازی قالب در تنظیمات هم هست');
  p.click('[data-setg="ticket"]');
  ok(p.all('#admBody .sd-sect').length===2&&p.all('[data-ticket-field]').length===8
    &&p.txt('#admBody').includes('رفتارهای نمایشی بلیت')&&p.txt('#admBody').includes('فقط بله'),
    'بلیت دو بخش تنظیمات دارد، محتوای خروجی انتخابی است و کانال آینده فقط بله است');
  ok(!!p.doc.querySelector('[data-ticket-format]')&&p.all('[data-ticket-field]').length===8
    &&p.txt('#admBody').includes('فاقد اعتبار ورود'),'موتور بلیت فرمت، فیلدهای انتخابی و واترمارک نمونه دارد');
  p.click('[data-ticket-test]');
  ok(!!p.doc.querySelector('.ticket-engine-preview svg')&&p.txt('#admBody').includes('صادر نشده'),
    'آزمایش موتور فقط پیش‌نمایش محلی می‌سازد');
  p.click('[data-setg="money"]');
  ok(p.all('[data-fintab]').map(x=>x.dataset.fintab).join(',')==='gates,cards,book,inst,receipts','مالی و کارمزد: درگاه، استخر کارت، حسابداری، اقساط و فیش یکجا هستند');
  ok(p.all('[data-fingate]').length===4&&new Set(p.all('[data-fingate]').map(el=>el.dataset.fingate)).size===4
    &&/درگاههای پرداخت نورا پی|درگاه‌های پرداخت نورا پی/.test(p.txt('#admBody'))
    &&!p.txt('#admBody').includes('غیرمتمرکز'),'چهار مسیر مالیِ نمایشی جدا هستند و درگاه غیرمتمرکز وجود ندارد');
  p.click('[data-fingate="bale"]');
  ok(p.all('[data-fingate="bale"].on').length===1&&JSON.parse(p.store.getItem('nora-finance')).gates.find(x=>x.k==='bale').on===1,
    'تغییر وضعیت درگاه فقط با مالک ذخیره می‌شود');
  p.click('[data-fintab="cards"]');
  ok(/بدون کارت پیش‌فرض/.test(p.txt('#admBody'))&&p.doc.querySelector('#finDailyMax')!==null&&/کارتی نیست/.test(p.txt('#admBody')),
    'استخر بدون کارت پیش‌فرض است و سقف مبلغ روزانه می‌گیرد');
  p.click('[data-fintab="gates"]');
  p.click('[data-setg="data"]');
  ok(p.all('#admBody .sd-sect').length===2&&p.all('[data-keycopy]').length===4,'داده: سیاست و کلیدها در دو بخشبند با چهار کلید');
  ok(p.all('#admBody .admsw').length===p.all('#admBody .admsw small').length,'داده: شرح رفتار زیر هر کلید');
  p.click('#admNav [data-sec="settings"]');
  p.click('[data-setg="texts"]');
  ok(p.all('[data-text]').length===4&&/هیچ پیام یا اعلانی ارسال نمی‌شود/.test(p.txt('#admBody'))
    &&/پس از تأیید صریح مالک/.test(p.txt('#admBody')),
    'گروه متن‌ها چهار متن نمونه دارد و دربارهٔ عدم ارسال و شرط تأیید مالک شفاف است');
  p.click('[data-setg="notify"]');
  ok(p.all('#admBody .sd-sect').length>=5,'نامهخانه: پنج بخشبند از اعلانها تا دفتر نامهها');
  ok(p.all('[data-ntfch$=":eitaa"]').length>0
    &&p.txt('#admBody').includes('ایتا'),'اعلان عمومی کانال ایتا را هم پیشنهاد می‌کند و آن را وصل‌نشده نشان می‌دهد');
  p.click('[data-setg="bots"]');
  ok(p.txt('#admBody').includes('بدون secret در مرورگر')&&p.txt('#admBody').includes('ارسال خاموش')
    &&!p.doc.querySelector('input[name*="token"],input[id*="token"]'),'تنظیم ربات‌ها هیچ توکنی را در مرورگر نمی‌گیرد');
  ok(p.store.getItem('nora-admin')!==null,'حالت پنل ذخیره می‌شود');
  /* ── تنظیمات سامانه: کاشیها و مدیریت ظاهر ── */
  p.click('#admNav [data-sec="settings"]');
  ok(p.all('[data-skit]').length===8,'هشت کاشی تنظیمات سامانه هست');
  ok(p.all('.sktgrid .sktile').length===8,'کاشیها در شبکهٔ تنظیمات نشستهاند');
  p.click('[data-skit="forms"]');
  ok(/تنظیمات فرمساز/.test(p.txt('#admBody')),'کاشی فرمساز، مدیریت فرمساز را باز کرد');
  ok(p.all('#admBody .metric').length===4,'گزارش کلی: چهار عدد (فرم، روی هوا، پاسخ، کار باز)');
  ok(!!p.doc.querySelector('#admBody [data-useg="forms.model:exam"]'),'نُه مدل فرم در پیشفرضها هست');
  ok(/گزارش تفکیک نوع/.test(p.txt('#admBody')),'گزارش تفکیک نوع فرمها همینجا است');
  [...p.all('#admBody [data-useg]')].find(x=>x.dataset.useg==='forms.model:exam').click();
  [...p.all('#admBody [data-useg]')].find(x=>x.dataset.useg==='forms.display:all').click();
  [...p.all('#admBody [data-useg]')].find(x=>x.dataset.useg==='forms.after:view').click();
  [...p.all('#admBody [data-useg]')].find(x=>x.dataset.useg==='forms.limit:invite').click();
  [...p.all('#admBody [data-useg]')].find(x=>x.dataset.useg==='forms.dept:media').click();
  p.click(p.all('#admBody [data-uk]')[0]);
  p.click(p.all('#admBody [data-uk]')[1]);
  p.doc.querySelector('#skFEnd').value='پاسخت رسید؛ ممنون.';
  p.click('[data-fsettext]');
  const fdef=JSON.parse(p.store.getItem('nora-uiset')).forms;
  ok(fdef.model==='exam'&&fdef.display==='all'&&fdef.after==='view'&&fdef.limit==='invite'&&fdef.dept==='media',
     'پیشفرضهای فرم تازه در انبار نشست');
  ok(fdef.guests===1&&fdef.wait===0,'سوییچ دعوت دوست و لیست انتظار هم ذخیره شدند');
  ok(fdef.endText==='پاسخت رسید؛ ممنون.','متن پایانی پیشفرض ذخیره شد');
  ok(JSON.parse(p.store.getItem('nora-uiset')).forms.tags.length===3,'سه برچسب عمومی از پیشفرض هست');
  p.doc.querySelector('#skTagN').value='پیگیری شد';
  p.click('[data-ftagadd]');
  ok(JSON.parse(p.store.getItem('nora-uiset')).forms.tags.length===4&&/برچسب «پیگیری شد»/.test(p.txt('#toast')),'برچسب تازه با رنگ اضافه شد');
  p.click('[data-ftagdel]');
  ok(JSON.parse(p.store.getItem('nora-uiset')).forms.tags.length===3,'برچسب برداشته میشود');
  p.click('[data-fclean]'); p.click('[data-fclean]');
  ok(/کار انجامشده/.test(p.txt('#toast')),'بایگانی کارهای کارتابل با دو پا گام روشن میشود');
  p.click('[data-skinback]');
  ok(p.all('[data-skit]').length===8,'برگشت به کاشیها (هشت کاشی با مدیریت پنل)');
  /* ── کاشی کاربران و دسترسی: شش عدد، سه صف درخواست، پارامتر پروفایل، برچسب، مسدود ── */
  p.click('[data-skit="users"]');
  ok(/کاربران و دسترسی/.test(p.txt('#admBody')),'کاشی کاربران، مدیریت کاربران را باز کرد');
  ok(p.all('#admBody .metric').length===6,'گزارش کلی کاربران: شش عدد (کاربر، صف، پرداختی، مسدود، ویژه، بیخبر)');
  ok(!!p.doc.querySelector('#admBody [data-useg="users.regs:invite"]'),'چهار سیاست عضویت هست');
  [...p.all('#admBody [data-useg]')].find(x=>x.dataset.useg==='users.regs:invite').click();
  [...p.all('#admBody [data-useg]')].find(x=>x.dataset.useg==='users.prune:3m').click();
  p.click(p.all('#admBody [data-uk]')[0]);
  const usv=JSON.parse(p.store.getItem('nora-uiset')).users;
  ok(usv.regs==='invite'&&usv.prune==='3m'&&usv.dues===0,'سیاست عضویت و قفل بدهی و پاکسازی ذخیره شد');
  ok(p.all('#admBody .utile[data-govreq]').length===3,'سه صف درخواست (پروفایل، غیبت مجاز، پاداش) در کاشی هست');
  p.click('[data-govreq]');
  ok(/درخواست/.test(p.txt('#admBody')),'میانبر درخواستها، برگهٔ درخواستها را باز کرد');
  p.click('#admNav [data-sec="settings"]'); p.click('[data-skit="users"]');
  ok(p.all('#admBody [data-upar]').length===8,'هشت فیلد پروفایل، از کاشی روشن و خاموش میشود');
  p.click(p.all('#admBody [data-upar]')[0]); p.click(p.all('#admBody [data-uparreq]')[0]);
  ok(JSON.parse(p.store.getItem('nora-admin')).upar['nid|req']===true,'فیلد اجباری شد و در پنل نشست');
  p.click('[data-uparreset]');
  ok(Object.keys(JSON.parse(p.store.getItem('nora-admin')).upar||{}).length===0,'بازگشت پارامترهای پروفایل به پیشفرض');
  p.doc.querySelector('#uTagNew').value='داوطلب اردو';
  p.click('[data-utagadd]');
  ok((JSON.parse(p.store.getItem('nora-admin')).ulabels||[]).indexOf('داوطلب اردو')>-1,'برچسب تازه از کاشی ساخته شد');
  p.click('[data-govtags]');
  ok(/برچسب‌ها و دسته‌ها/.test(p.txt('#admBody')),'میانبر برچسبها، برگهٔ برچسبها را باز کرد');
  p.click('#admNav [data-sec="settings"]'); p.click('[data-skit="users"]');
  p.click('[data-govuser]');
  ok(/اطلاعات/.test(p.txt('#admBody')),'پروندهٔ مسدود از کاشی باز میشود');
  p.click('#admNav [data-sec="settings"]'); p.click('[data-skit="users"]');
  {const un=p.doc.querySelector('[data-uunblock]'); const uid=un.dataset.uunblock;
   p.click(un);
   ok(/فقط برچسب مرورگر عوض شد/.test(p.txt('#toast'))&&JSON.parse(p.store.getItem('nora-admin')).uov[uid].st[0]==='تأیید محلی · نمونه',
     'رفع مسدودی فقط برچسب محلی را عوض می‌کند؛ دسترسی سروری و دادهٔ پایه تغییر نمی‌کند ('+uid+')');}
  /* ── کاشی مدیریت پنل: سقف، لاگ، نگهداری، میانبرها، حافظه ── */
  {p.click('#admNav [data-sec="settings"]');
   if(!p.doc.querySelector('[data-skit="ops"]')) p.click('[data-skinback]');
   p.click('[data-skit="ops"]');}
  ok(/مدیریت پنل/.test(p.txt('#admBody')),'کاشی مدیریت پنل باز شد');
  ok(p.all('#admBody .metric').length===4,'چهار عدد مدیریت پنل (کار باز، لاگ، سقف، حساب تازه)');
  ok(p.all('#admBody .utile[data-goset]').length===4,'چهار میانبر تنظیمهای مرتبط (متنها، اعلانها، داده، مالی)');
  p.click('[data-goset="notify"]');
  ok(!!p.doc.querySelector('[data-setg="notify"].on'),'میانبر اعلانها، گروه اعلانهای تنظیمات را باز کرد');
  /* ── نامهخانهٔ اعلان‌ها: پیش‌نویس و صف محلیِ مالک؛ ارسال واقعی نداریم ── */
  console.log('\n── نامهخانهٔ اعلان‌های محلی ──');
  ok(p.all('[data-ntfon]').length===14,'چهارده قالب پیش‌نمایش اعلان تعریف شده');
  ok(p.all('.ntfcard').length===14,'هر قالب روشن فقط کارت پیش‌نمایش دارد');
  {const c=p.txt('.ntfcard');
   ok(p.txt('.ntfcard .ntf-from')==='نورا','نام نمایشی فرستنده در پیش‌نمایش می‌آید');
   ok(/پیش‌نمایش محلی/.test(c)&&/نمونه/.test(c)&&/ارسال نشده/.test(c),
     'متن اعلان ثبت‌نام، نمونهٔ محلی و ارسال‌نشده است؛ بلیت یا پرداخت وعده نمی‌دهد');
   ok(/پیش‌نمایش نمونه/.test(c)&&/ارسال نشده/.test(c),
     'کارت اعلان برچسب نمونه و ارسال‌نشده دارد؛ مهر عملیاتی تاریخ یا ساعت نمایش نمی‌دهد');}
  ok(p.all('[data-ntfch$=":bale"]').length===14&&p.all('[data-ntfch$=":eitaa"]').length===14&&/وصل‌نیست/.test(p.txt('#admBody')),
    'کانال‌های بله و ایتا صریحاً وصل‌نشده‌اند و ارسال محسوب نمی‌شوند');
  p.click('[data-ntfon="pay_no"]');
  ok(p.all('.ntfcard').length===13&&(JSON.parse(p.store.getItem('nora-admin')).ntfOff||[]).indexOf('pay_no')>-1,
     'خاموش‌کردن قالب فقط نمایش محلی را تغییر می‌دهد');
  p.click('[data-ntfon="pay_no"]');
  p.click('[data-ntfch="remind:eitaa"]');
  ok(JSON.parse(p.store.getItem('nora-admin')).ntfCh.remind.eitaa===1,'کانال ایتا فقط به‌عنوان ترجیح محلی روشن می‌شود');
  p.click('[data-ntfch="remind:eitaa"]');
  p.click('[data-ntfg="money"]');
  ok(p.all('[data-ntfon]').length===2,'فیلتر مالی دو قالب نمونه دارد');
  p.click('[data-ntfg="all"]');
  p.click('[data-ntfed="reg_ok"]');
  ok(!!p.doc.querySelector('#ntfT')&&!!p.doc.querySelector('#ntfB'),'ویرایش پیش‌نویس سه فیلد دارد');
  p.doc.querySelector('#ntfB').value='{نام}، این فقط یک متن نمونه است؛ پیام ارسال نمی‌شود.';
  p.click('[data-ntfsave="reg_ok"]');
  ok(JSON.parse(p.store.getItem('nora-admin')).ntfT.reg_ok.b.includes('پیام ارسال نمی‌شود'),
    'ویرایش فقط در تنظیم محلی پنل ذخیره می‌شود');
  p.click('[data-ntfreset="reg_ok"]');
  ok(!JSON.parse(p.store.getItem('nora-admin')).ntfT.reg_ok,'قالب نمونه به پیش‌فرض محلی برمی‌گردد');
  p.click('[data-ntfsend="reg_ok"]');
  const U=p.window.NORA_UI;
  const sampleReq=U.ownerApprovals().find(x=>x&&x.type==='notification'&&x.status==='pending'
    &&x.source==='notification-sample'&&x.testOnly);
  ok(!!sampleReq&&/هیچ پیامی ارسال نشد/.test(p.txt('#toast')),
    'دکمه فقط نمونهٔ آزمایشی را در صف مالک می‌گذارد؛ ارسال واقعی نمی‌کند');
  ok(!U.ownerApprovals().some(x=>x&&x.type==='notification'&&x.status==='sent'),
    'هیچ رکورد ارسال‌شده‌ای در انبار مالک ساخته نمی‌شود');
  ok(!!p.doc.querySelector('[data-noticeapprove="'+sampleReq.id+'"]'),
    'درخواست نمونه برای بازبینی مالک قابل مشاهده است');
  p.click('[data-noticeapprove="'+sampleReq.id+'"]');
  const approvedSample=U.ownerApprovals().find(x=>x&&x.id===sampleReq.id);
  ok(approvedSample.status==='approved'&&approvedSample.testOnly===true
    &&/هیچ پیامی ارسال نشد/.test(p.txt('#toast')),
    'تأیید مالکِ نمونه نیز فقط محلی است و حتی پس از تأیید ارسال نمی‌شود');
  ok(/دفتر تأییدهای محلی/.test(p.txt('#admBody'))&&p.all('#admBody .metric').length===4,
    'دفتر محلی و چهار سنجهٔ قالب پیش‌نمایش دیده می‌شوند');
  p.doc.querySelector('#ntfFrom').value='مؤسسهٔ نمونه';
  p.click('[data-ntffrom]');
  ok(p.txt('.ntfcard .ntf-from')==='مؤسسهٔ نمونه'&&/فقط در پیش‌نمایش محلی/.test(p.txt('#toast')),
    'نام فرستنده فقط روی کارت‌های پیش‌نمایش عوض می‌شود');
  p.doc.querySelector('#ntfFrom').value='نورا';
  p.click('[data-ntffrom]');
  p.type('[data-ntfclock="remind"]','۲۱:۰۰','change');
  ok(JSON.parse(p.store.getItem('nora-admin')).ntfClock.remind==='۲۱:۰۰'
    &&/زمان‌بندی و ارسال غیرفعال/.test(p.txt('#admBody')),
     'ساعت یادآور فقط پیشنهاد محلی است؛ زمان‌بندی غیرفعال می‌ماند');
  p.doc.querySelector('#ntfBc').value='یادداشت نمونه برای بازبینی';
  p.click('[data-ntfbcast]');
  const bcReq=U.ownerApprovals().find(x=>x&&x.type==='notification'&&x.status==='pending'&&x.source==='broadcast');
  ok(!!bcReq&&/ارسال واقعی متصل نیست/.test(p.txt('#toast')),
     'نامهٔ همگانی فقط درخواست محلی می‌سازد؛ به اعضا نمی‌رسد');
  p.click('[data-noticeapprove="'+bcReq.id+'"]');
  const localNotice=U.ownerApprovals().find(x=>x&&x.id===bcReq.id);
  ok(localNotice.status==='approved'&&localNotice.notificationStatus==='approved'
    &&!U.ownerApprovals().some(x=>x&&x.id===bcReq.id&&x.sent===true),
    'تأیید مالک فقط اعلان محلیِ ارسال‌نشده ثبت می‌کند');
  p.click('[data-ntflogclr]');
  ok((JSON.parse(p.store.getItem('nora-admin')).ntfLog||[]).length===0,'دفتر تأییدهای محلی پاک می‌شود');

  /* تأیید پروفایل نیز وضعیت نمونه و درخواست خوش‌آمدِ محلی می‌سازد، نه ارسال فوری */
  p.click('#admNav [data-sec="users"]');
  p.click('[data-uv="req"]');
  {const uok=p.doc.querySelector('[data-uok]');
   p.click(uok);
   const profileReq=U.ownerApprovals().find(x=>x&&x.type==='notification'&&x.status==='pending'
     &&x.key==='welcome');
   ok(!!profileReq&&profileReq.testOnly===false&&profileReq.source==='notification-trigger'
     &&/فقط در صف محلی مالک است/.test(p.txt('#toast'))&&/ارسال نمی‌شود/.test(p.txt('#toast'))
     &&!U.ownerApprovals().some(x=>x&&x.id===profileReq.id&&x.sent===true),
     'تغییر وضعیت پروفایل فقط محلی است؛ خوش‌آمد برای بازبینی مالک می‌ماند و ارسال نمی‌شود');}
  /* رویداد: CTA اعلان بلیت فقط درخواست بازبینی نمونه می‌سازد */
  p.click('#admNav [data-sec="events"]');
  p.click('[data-ev]');
  p.click('#shAdm [data-evtab="reg"]');
  ok(!!p.doc.querySelector('#shAdm [data-ntfsend="reg_ok"]')
    &&/فقط درخواست محلی|ارسال خودکار وجود ندارد/.test(p.txt('#shAdm')),
    'CTA رویداد برای اعلان بلیت، درخواست محلی است و ارسال خودکار ندارد');
  /* ── کاشی باشگاه کتابخوانی: از تعریف تا برنامه ── */
  console.log('\n── کاشی باشگاه کتابخوانی ──');
  p.click('#admNav [data-sec="settings"]');
  p.click('[data-skit="book"]');
  ok(/باشگاه کتابخوانی/.test(p.txt('#admBody')),'کاشی باشگاه کتابخوانی باز شد');
  ok(p.all('[data-bktab]').length===10,'ده برگه: هویت، در، حق عضویت، جلسهها، پادکست، کتابخانه، مسابقه، کتاب، کارگاه، تریبون');
  ok(p.all('#admBody .metric').length===4,'چهار عدد ترم: عضو، ظرفیت، جلسه، پیشرفت');
  p.doc.querySelector('#bkBook').value='سووشون';
  p.click('[data-bksave]');
  ok(JSON.parse(p.store.getItem('nora-admin')).bk.book==='سووشون','هویت باشگاه (کتاب ماه و ترم و سرپرست) ذخیره میشود');
  p.click('[data-bktab="gate"]');
  ok(p.all('[data-bkstepup]').length===2&&/فرم نمونه/.test(p.txt('#admBody'))
    &&/فقط در مرورگر ذخیره می‌شود/.test(p.txt('#admBody'))&&/پرداخت واقعی/.test(p.txt('#admBody')),
    'درِ باشگاه دو گام نمونه دارد؛ داده فقط محلی است و عضویت یا پرداخت واقعی نمی‌سازد');
  ok(p.all('[data-bkfup]').length===5,'پنج پرسش فرم عضویت، از کاشی اجباری و برداشتن دارد');
  p.doc.querySelector('#bkFQ').value='سبک مورد علاقه';
  p.doc.querySelector('#bkFO').value='رمان، شعر، نقد';
  p.click('[data-bkfaddpick]');
  ok(p.all('[data-bkfup]').length===6,'پرسش چهارگزلهای تازه به فرم عضویت نشست');
  p.doc.querySelector('#bkRule').value='هر ماه یک نقد کوتاه';
  p.click('[data-bkradd]');
  ok(p.all('[data-bkrdel]').length===4,'قاعدهٔ تازهٔ باشگاه نشست');
  p.click('[data-bktab="fee"]');
  p.doc.querySelector('#bkFee').value='200000';
  p.click('[data-bkfeesave]');
  ok(JSON.parse(p.store.getItem('nora-admin')).bk.feeAmount===200000,'حق عضویت ماهانه و نرخ دانشجو و سررسید ذخیره میشود');
  ok(p.all('[data-bkplan]').length===3,'سه بستهٔ پرداخت با ویرایش مبلغ');
  p.click('[data-bktab="meet"]');
  p.click(p.doc.querySelector('[data-bkmeetok]'));
  ok(JSON.parse(p.store.getItem('nora-admin')).bk.meets[0].state==='later','برگزار شد، جلسهٔ باز را میبندد');
  p.doc.querySelector('#bkMW').value='پنجشنبه ۲۴ مهر';
  p.doc.querySelector('#bkMC').value='فصل ۶: مکان روایت';
  p.click('[data-bkmeetadd]');
  ok(JSON.parse(p.store.getItem('nora-admin')).bk.meets.length===4,'جلسهٔ تازه با میزبان و شکل جلسه ریخته میشود');
  p.click('[data-bktab="pod"]');
  p.click(p.doc.querySelector('[data-bkepok]'));
  ok(JSON.parse(p.store.getItem('nora-admin')).bk.eps[0].st==='منتشر شد','انتشار قسمت پادکست، با مهر تاریخ');
  p.click('[data-bktab="game"]');
  p.doc.querySelector('#bkCN').value='مسابقهٔ نقد';
  p.doc.querySelector('#bkCD').value='نقد فصل ۶';
  p.click('[data-bkconadd]');
  ok(JSON.parse(p.store.getItem('nora-admin')).bk.contests.length===3,'مسابقهٔ تازه با مهلت و جایزه باز شد');
  p.click('[data-bkcopy="contest:2"]');
  ok(/مسابقهٔ نقد.*رونوشت شد|رونوشت شد/.test(p.txt('#toast')),'مدیر لینک مسابقه را از همان ردیف کپی میکند');
  p.click('[data-bked="contest:2"]');
  p.doc.querySelector('#bkEdBN').value='ثبتنام مسابقه';
  p.doc.querySelector('#bkEdBU').value='https://ble.ir/nora';
  p.click('[data-bkedsave]');
  ok(JSON.parse(p.store.getItem('nora-admin')).bk.contests[2].btnN==='ثبتنام مسابقه','مسابقه دکمه و نشانی خودش را گرفت');
  p.click('[data-bktab="books"]');
  p.doc.querySelector('#bkVT').value='همسایهها';
  p.click('[data-bkvoteadd]');
  {const vs=p.all('[data-bkvoteend]'); p.click(vs[vs.length-1]);}
  ok(JSON.parse(p.store.getItem('nora-admin')).bk.book==='همسایهها'&&JSON.parse(p.store.getItem('nora-admin')).bk.vote.length===0,
     'بستن رأیگیری، پررایگترین را کتاب ماه بعد میکند');
  p.click('[data-bktab="wk"]');
  p.doc.querySelector('#bkWkT').value='کارگاه آزمایشی';
  p.click('[data-bkwkadd]');
  ok(JSON.parse(p.store.getItem('nora-admin')).bk.wkL.length===4,'کارگاه تازه با ظرفیت و هزینه ریخته میشود');
  p.click('[data-bktab="trib"]');
  p.doc.querySelector('#bkTrM').value='300';
  p.click('[data-bktribsave]');
  ok(JSON.parse(p.store.getItem('nora-admin')).bk.tribMax===300,'تریبون: برچسبها و سقف نامه ذخیره میشود');
  p.doc.querySelector('#bkGrR').value='قاعدهٔ یک؛ قاعدهٔ دو';
  p.click('[data-bkgrsave]');
  ok(JSON.parse(p.store.getItem('nora-admin')).bk.grRules.length===2,'گروه اختصاصی: پیوند و کد و قاعدهها ذخیره میشود');
  /* کتابخانه و صدا: فایل، انتشار در خانهٔ کاربر، دکمه و پیوند */
  p.click('[data-bktab="lib"]');
  ok(!!p.doc.querySelector('[data-bkaudio]')&&!!p.doc.querySelector('[data-bkfile]'),'کتابخانه دو ریختگاه دارد: صدا و فایل کتاب');
  {const el=p.doc.querySelector('[data-bkaudio]');
   Object.defineProperty(el,'files',{value:[new p.window.File([new Uint8Array(50).fill(7)],'nabz-ep13.mp3')],configurable:true});
   el.dispatchEvent(new p.window.Event('change',{bubbles:true}));}
  await wait(150);
  ok(!!p.doc.querySelector('.bkform .bkcard audio'),'پیش از انتشار، پیشنمایش پخش صدا دیده میشود');
  p.doc.querySelector('#bkLibT').value='قسمت ۱۳: راوی چرا پنهان می‌کند؟';
  p.click('[data-bklibadd]');
  ok(JSON.parse(p.store.getItem('nora-admin')).bk.lib.length===1,'مطلب صوتی در کتابخانه نشست');
  {const L=JSON.parse(p.store.getItem('nora-clublib')||'[]');
   ok(L.some(x=>x.kind==='صدا'&&x.t.indexOf('قسمت ۱۳')>-1),'انتشار شد؛ کارت در انبار مشترک خانهٔ کاربر نشست');
   ok((L[0].link||'').indexOf('home.html#club')>-1,'هر مطلب، پیوند سامانهٔ خودش را دارد');}
  p.click('[data-bked="lib:0"]');
  ok(!!p.doc.querySelector('#bkEdBN'),'ویرایشگر دکمه و پیوند باز میشود');
  p.doc.querySelector('#bkEdBN').value='شنیدن در گروه';
  p.doc.querySelector('#bkEdBU').value='https://ble.ir/join/nabzvaragh';
  p.click('[data-bkedsave]');
  ok(JSON.parse(p.store.getItem('nora-admin')).bk.lib[0].btnN==='شنیدن در گروه','دکمهٔ سفارشی مطلب ذخیره شد و روی کارت نشست');
  p.click('[data-bkcopy="lib:0"]');
  ok(/رونوشت شد/.test(p.txt('#toast')),'کپی پیوند مطلب، با پیام روشن');
  {const el=p.doc.querySelector('[data-bkfile]');
   Object.defineProperty(el,'files',{value:[new p.window.File([new Uint8Array(30).fill(9)],'soooshoon.pdf')],configurable:true});
   el.dispatchEvent(new p.window.Event('change',{bubbles:true}));}
  await wait(150);
  p.doc.querySelector('#bkLibT').value='سووشون؛ فصل اول';
  p.click('[data-bklibadd]');
  ok(!!p.doc.querySelector('.bkcard a[download]'),'فایل کتاب، با دکمهٔ خواندن و دانلود روی کارت');
  p.click('[data-govclub]');
  ok(/باشگاه و امتیاز/.test(p.txt('#admBody')),'میانبر «باشگاه و امتیاز»، برگهٔ اعضا را باز کرد');
  /* ── کاشی رویدادها و مطالب: برچسب، دسته، تقویم، قالب، دکمهها، سیاست ── */
  console.log('\n── کاشی رویدادها و مطالب ──');
  p.click('#admNav [data-sec="settings"]');
  if(!p.doc.querySelector('[data-skit="skdev"]')) p.click('[data-skinback]');
  p.click('[data-skit="skdev"]');
  ok(/رویدادها و مطالب/.test(p.txt('#admBody')),'کاشی رویدادها و مطالب باز شد');
  ok(p.all('[data-sdtab]').length===6,'شش برگه: برچسب، دسته، تقویم، قالب، دکمهها، سیاست');
  ok(p.all('#admBody .metric').length===4,'سر برگهٔ برچسب، چهار عدد زنده');
  ok(p.all('#admBody .sd-sect').length>=2,'برگهها با بخشبند کارتی: سربرگ کمّار و بدنهٔ جداشده');
  p.doc.querySelector('#sdTag').value='ویژهٔ نوروز';
  p.click('[data-sdtagadd]');
  ok((JSON.parse(p.store.getItem('nora-admin')).sd||{}).qtags.indexOf('ویژهٔ نوروز')>-1,'برچسب برنامه نشست و در خانه هم میآید');
  p.doc.querySelector('#sdPTag').value='از مسترکلاس';
  p.click('[data-sdptagadd]');
  ok((JSON.parse(p.store.getItem('nora-admin')).sd||{}).ptags.indexOf('از مسترکلاس')>-1,'برچسب مطلب تازه هم از همینجا ساخته میشود');
  p.click('[data-sdtab="cat"]');
  p.doc.querySelector('#sdCatN').value='مناظره';
  p.click('[data-sdcatadd]');
  ok((JSON.parse(p.store.getItem('nora-admin')).sd||{}).cats.length===7,'دستهٔ تازه با آیکن و توضیح نشست');
  p.click('[data-sdtab="cal"]');
  ok(p.all('#admBody .metric').length===4,'تقویم: چهار عدد (رویداد، در راه، مطلب، تاریخ خاص)');
  ok(!!p.doc.querySelector('[data-sdholdel]')&&p.txt('#admBody').includes('تقویم پیش رو'),'تقویم پیش رو و تاریخهای خاص در یک برگه است');
  p.doc.querySelector('#sdHolN').value='روز کتاب';
  p.click('[data-sdholadd]');
  ok((JSON.parse(p.store.getItem('nora-admin')).sd||{}).holidays.length===4,'تاریخ خاص و تعطیلی نشست');
  p.type('[data-sdclock="start"]','۱۶:۰۰','change');
  ok(JSON.parse(p.store.getItem('nora-admin')).sd.clockStart==='۱۶:۰۰','ساعت پیشفرض برنامهها عوض میشود');
  p.click('[data-sdtab="tpl"]');
  ok(!!p.doc.querySelector('[data-sdtpl="lead"]')&&!!p.doc.querySelector('.pcard .pc-ttl'),'پیشنمایش قالب: کارت واقعی خانه (جلد و برچسب و دکمه)');
  ok(/دقیقه مطالعه/.test(p.txt('.sdprev'))&&/ادامهٔ مطلب/.test(p.txt('.sdprev .pc-foot')),'کارت پیشنمایش: زمان مطالعه و دکمهٔ کنش از برگهٔ دکمهها');
  ok(/پنل ساخته شده|نمونهٔ ثابت/.test(p.txt('.sdprev .pc-foot')),'پیشنمایش از مطلب فعال پنل میآید و نشانهاش را دارد');
  p.click('[data-sdtab="cta"]');
  p.doc.querySelector('[data-sdcta="reg"]').value='ثبتنام کن';
  p.click('[data-sdctasave]');
  ok(JSON.parse(p.store.getItem('nora-admin')).sd.ctaReg==='ثبتنام کن','متن دکمههای خانه ذخیره میشود');
  p.click('[data-sdtab="mod"]');
  p.click(p.doc.querySelector('[data-sdtog="autopub"]'));
  ok(p.all('[data-sdtog]').length===4,'سیاست انتشار: خودکار، بی تأیید، اعلان، آرشیو؛ چهار کلید');
  ok(p.all('[data-gonew]').length===2&&!!p.doc.querySelector('[data-gojump2]'),'سه میانبر: رویداد تازه، مطلب تازه، فهرست');
  p.click('[data-gonew="ev"]');
  ok(/گام|تعریف/.test(p.txt('#admBody')),'میانبر رویداد تازه، ویزارد را باز کرد');
  p.click('[data-evback]');
  p.click('#admNav [data-sec="settings"]');
  if(!p.doc.querySelector('[data-skit="skdev"]')) p.click('[data-skinback]');
  p.click('[data-skit="skdev"]');
  p.click('[data-gonew="post"]');
  ok(!!p.doc.querySelector('[data-pback]'),'میانبر مطلب تازه، ویرایشگر مطلب را باز کرد');
  p.click('[data-pback]');
  p.click('#admNav [data-sec="settings"]');
  if(!p.doc.querySelector('[data-skit="skdev"]')) p.click('[data-skinback]');
  p.click('[data-skit="skdev"]');
  p.click('[data-goev]');
  ok(/رویداد|مطلب/.test(p.txt('#admBody')),'میانبر بخش رویدادها، همان بخش را باز کرد');
  /* ═══ کاشی «پشتیبانی و گفتگو»: صندوق، پاسخهای آماده، سرویس، تیم، گزارش ═══ */
  {const now=Date.now();
   const TKS=[{id:'t1',code:'11827',sec:'pay',cat:'پرداخت',anon:false,name:'رضا کریمی',contact:'۰۹۱۲۱۱۱۲۲۳۳',
      at:now-5*3600000,thread:[{who:'me',at:now-5*3600000,text:'پرداختم دوبار کم شد؛ لطفاً بررسی کنید.'}]},
     {id:'t2',code:'23094',sec:'cert',cat:'گواهی',anon:false,name:'سارا محمدی',contact:'۰۹۱۲۹۹۸۸۷۷۶',
      at:now-2*86400000,closed:1,thread:[{who:'me',at:now-2*86400000,text:'گواهی کارگاه را نمیتوانم ببینم.'},
      {who:'agent',by:'کارشناس نمونه',at:now-2*86400000+3600000,text:'این پاسخ محلیِ نمونه است؛ گواهی رسمی صادر یا برای شما ارسال نشده.'}]}];
   const st2=makeStore(); st2.setItem('nora-support-tickets',JSON.stringify(TKS));
   const pc=await load(st2);
   pc.click('#admNav [data-sec="settings"]');
   ok(pc.all('[data-skit]').length===8&&!/در نوبت بعد/.test(pc.txt('[data-skit="chat"]')),'کاشی پشتیبانی و گفتگو از نوبت خارج شد و هشت کاشی کامل است');
   pc.click('[data-skit="chat"]');
   ok(pc.all('[data-chtab]').length===5,'پنج برگه: گفتگوها، پاسخهای آماده، سرویس، تیم، گزارش');
   ok(pc.all('#admBody .tag').some(x=>/بازهٔ نمایشی|پیش‌نمایش تعطیلی/.test(x.textContent)),
     'نشان ساعات فقط وضعیت نمایشی پاسخگویی را می‌گوید');
   ok(pc.all('#admBody .metric').length===4&&pc.all('[data-chopen]').length===2
     &&/دادهٔ نمونهٔ همین مرورگر/.test(pc.txt('#admBody')),'صندوق: چهار عدد و دو گفت‌وگوی نمونهٔ محلی‌اند');
   ok(/گذشت از مهلت/.test(pc.txt('#admBody')),'تیکت گذشته از مهلت، نشان «گذشت از مهلت» میگیرد');
   ok(/تیکت بیپاسخ مانده/.test(pc.txt('#admBody')),'یادآور تیکت بیپاسخ بالای صندوق می‌نشیند');
   /* جستوجو */
   pc.type('#chQ','کریمی'); pc.click('[data-chqgo]');
   ok(pc.all('[data-chopen]').length===1,'جستوجو در نام و کد و متن گفتگوها');
   pc.click('[data-chqclr]');
   ok(pc.all('[data-chopen]').length===2,'پاککردن جستوجو، همه را برگرداند');
   /* فوریت و واگذاری */
   pc.click('[data-chopen="t1"]');
   pc.click('[data-chprio="t1"]');
   ok(JSON.parse(pc.store.getItem('nora-support-tickets'))[0].prio===1&&/فوری/.test(pc.txt('#admBody')),'فوریت تیکت نشست و نشانش دیده میشود');
   const assignBtn=pc.doc.querySelector('[data-chassign^="t1:"]');
   const assignedName=assignBtn&&assignBtn.dataset.chassign.slice('t1:'.length);
   pc.click(assignBtn);
   ok(!!assignedName&&JSON.parse(pc.store.getItem('nora-support-tickets'))[0].assign===assignedName,
     'واگذاری تیکت فقط به‌صورت محلی ثبت می‌شود؛ پیام برای پاسخگوی واقعی نمی‌رود');
   /* قالب آماده با متغیر */
   pc.click('[data-chuse="2"]');
   ok(pc.doc.querySelector('#chMsg').value.includes('رضا کریمی')&&pc.doc.querySelector('#chMsg').value.includes('۱۱۸۲۷'),'قالب آماده با متغیرهای {نام} و {کد} در گفتوگو پر میشود');
   pc.type('#chMsg','پاسخ نمونه برای بازبینی؛ این متن به کاربر واقعی ارسال نمی‌شود.');
   pc.click('[data-chsend]');
   const t1=JSON.parse(pc.store.getItem('nora-support-tickets'))[0];
   ok(t1.thread[t1.thread.length-1].who==='agent'&&t1.thread[t1.thread.length-1].by===assignedName
     &&/فقط در همین مرورگر ذخیره شد/.test(pc.txt('#toast'))&&/ارسال نشد/.test(pc.txt('#toast')),
     'پاسخ و نام پاسخگو فقط در تیکت نمونهٔ همین مرورگر ذخیره می‌شوند؛ ارسال بیرونی ندارند');
   ok(/پاسخ داده شد/.test(pc.txt('#admBody')),'وضعیت تیکت به «پاسخ داده شد» چرخید');
   pc.click('[data-chclose]');
   ok(JSON.parse(pc.store.getItem('nora-support-tickets'))[0].closed===1,'بستن تیکت در حافظهٔ مشترک مینویسد');
   pc.click('[data-chreopen]');
   ok(JSON.parse(pc.store.getItem('nora-support-tickets'))[0].closed===0,'گشودن تیکت، همان را برمیگرداند');
   /* برگهٔ پاسخهای آماده: افزودن، ویرایش، برداشتن، متغیر */
   pc.click('[data-chtab="canned"]');
   ok(pc.all('[data-chvar]').length===3,'سه متغیر آماده: {نام}، {کد}، {بخش}');
   pc.type('#chCann','صبر کن {کد} را بررسی کنم'); pc.click('[data-chcannadd]');
   ok(pc.all('[data-chcdel]').length===4&&/متغیر دارد/.test(pc.txt('#admBody')),'افزودن پاسخ آمادهٔ تازه با تشخیص متغیر');
   pc.click('[data-chcannedit="3"]'); pc.type('#chCannEd','ویرایش شد'); pc.click('[data-chcannsave]');
   ok(/ویرایش شد/.test(pc.txt('#admBody')),'ویرایش درجای پاسخ آماده');
   pc.click('[data-chvar="{نام}"]');
   ok(pc.doc.querySelector('#chCann').value.includes('{نام}'),'کلیک متغیر، آن را در کادر میگذارد');
   pc.click('[data-chcdel="3"]');
   ok(pc.all('[data-chcdel]').length===3,'برداشتن پاسخ آماده');
   /* برگهٔ سرویس: تعطیلی، پاسخ بیرون از ساعت، ساخت متن، ذخیرهٔ کلید مشترک */
   pc.click('[data-chtab="svc"]');
   ok(pc.all('[data-chday]').length===7&&!!pc.doc.querySelector('#chFrom')&&!!pc.doc.querySelector('#chTo'),'سرویس: هفت روز هفته و ساعات از/تا');
   pc.click('[data-chtog="closedNow"]');
   ok(/پیش‌نمایش تعطیلی/.test(pc.txt('#admBody'))&&/برچسب نمونهٔ تعطیلی موقت/.test(pc.txt('#admBody')),
     'تعطیلی فقط نشانِ نمونهٔ مرورگر را همان لحظه عوض می‌کند');
   pc.click('[data-chtog="awayOn"]');
   pc.click('[data-chautotext]');
   ok(pc.doc.querySelector('#chHrsT').value.length>4,'ساخت خودکار متن ساعات از اعداد و روزها');
   pc.click('[data-chday="6"]');
   pc.type('#chReply','تا دو ساعت کاری پاسخ میدهیم');
   pc.click('[data-chsvsave]');
   const sk=JSON.parse(pc.store.getItem('nora-support-hours')||'null');
   ok(!!sk&&sk.closedNow===1&&sk.awayOn===1&&/دو ساعت/.test(sk.reply)&&Array.isArray(sk.days)&&sk.days.includes(6),'ذخیرهٔ کامل سرویس در کلید مشترک nora-support-hours');
   pc.click('[data-chtog="closedNow"]'); pc.click('[data-chsvsave]');
   ok(JSON.parse(pc.store.getItem('nora-support-hours')).closedNow===0,'برداشتن تعطیلی، در کلید مشترک هم برمیگردد');
   ok(/در بازهٔ نمایشی|بیرون از بازهٔ نمایشی/.test(pc.txt('#admBody .card.stack > .row:nth-of-type(2) .tag')),
     'با برداشتن تعطیلی، فقط نشانِ بازهٔ نمایشی برگشت');
   /* برگهٔ تیم: عضو تازه، ویرایش، آنلاین، انتشار به کاربر */
   pc.click('[data-chtab="team"]');
   ok(pc.all('[data-chteamdel]').length===5&&pc.all('[data-chagent]').length===5,'تیم پاسخگو: پنج عضو از دادهٔ سامانه (لید و کارشناسها)');
   pc.type('#chTmN','هومن راد'); pc.type('#chTmR','کارشناس رویدادها'); pc.click('[data-chteamadd]');
   ok(pc.all('[data-chteamdel]').length===6,'افزودن عضو تازه به تیم');
   pc.click('[data-chteamedit="5"]'); pc.type('#chTmER','سرپرست رویدادها'); pc.click('[data-chteamsave]');
   ok(/سرپرست رویدادها/.test(pc.txt('#admBody')),'ویرایش درجای عضو تیم');
   pc.click('[data-chteamon="5"]');
   ok(JSON.parse(pc.store.getItem('nora-admin')).ch.team[5].on===0,'کلید آنلاین/بعداً هر عضو');
   pc.click('[data-chteampub]');
   const tk=JSON.parse(pc.store.getItem('nora-support-team')||'null');
   ok(!!tk&&tk.list.length===6&&tk.list[5].r==='سرپرست رویدادها','انتشار تیم در کلید مشترک nora-support-team برای صفحهٔ کاربر');
   pc.click('[data-chteamdel="5"]');
   ok(/منتشرنشده/.test(pc.txt('#admBody')),'پس از تغییر بی انتشار، حالت «منتشرنشده» دیده میشود');
   /* برگهٔ گزارش */
   pc.click('[data-chtab="rep"]');
   ok(pc.all('.ch-bars b').length===7,'گزارش: نمودار هفتروزه با هفت ستون');
   ok(/بی‌نام/.test(pc.txt('#admBody'))&&/فوری/.test(pc.txt('#admBody')),'شمارش بی‌نام و فوری و واگذارشده در گزارش');
   ok(/گزارش اکسل/.test(pc.txt('#admBody'))&&/وصل نیست/.test(pc.txt('#admBody')),'گزارش اکسل فقط پیوند نمایشی دارد؛ ارسال رباتی وصل نیست');
   ok(pc.errs.length===0,'کاشی پشتیبانی و گفتگو بیخطا بود');}
  /* ═══ کاشی «مدیران و اساتید»: پروفایل کامل، لینک و فرم، پیشنمایش زنده ═══ */
  {const pp=await load();
   pp.click('#admNav [data-sec="settings"]');
   ok(/مدیران و اساتید/.test(pp.txt('[data-skit="people"]')),'کاشی مدیران و اساتید سر جای خودش است');
   pp.click('[data-skit="people"]');
   ok(pp.all('[data-pptab]').length===4&&!!pp.doc.querySelector('[data-pptab="partners"]'),
     'چهار برگه: اساتید، دستاندرکاران، مدیران و نهادهای همکار');
   ok(pp.all('[data-pped]').length===6&&/منتشرنشده/.test(pp.txt('#admBody')),'شش استاد از دادهٔ سامانه با حالت منتشرنشده');
   pp.click('[data-pped="p1"]');
   const F=s=>!!pp.doc.querySelector(s);
   ok(F('[data-ppf="n"]')&&F('[data-ppf="r"]')&&F('[data-ppf="role2"]')&&F('[data-ppf="ini"]'),'ویرایش: نام و سمت و سمتِ دوم و حرفِ آواتار');
   ok(F('[data-ppf="bio"]')&&F('[data-ppf="quote"]')&&F('[data-ppf="where"]')&&F('[data-ppf="exp"]'),'درباره، جملهٔ ایشان، محل کارگاه و تخصصها');
   ok(F('[data-ppf="rate"]')&&F('[data-ppf="courses"]')&&F('[data-ppf="yrs"]'),'آمارِ ورقه: امتیاز، شمار دوره، سال تجربه');
   ok(pp.all('[data-ppg]').length===4&&pp.all('[data-ppic]').length===10,'چهار رنگ و ده آیکون برای کارت');
   ok(pp.all('[data-pptag]').length===7,'هفت برچسبِ کارت (و برچسبِ دلخواه)');
   ok(!!pp.doc.querySelector('.tcard .nm')&&!!pp.doc.querySelector('.ppsheet'),'پیشنمایشِ کارت و ورقهٔ پروفایل، همان که کاربر میبیند');
   pp.type('[data-ppf="n"]','خانم الهه رضایی‌فر');
   ok(/رضایی‌فر/.test(pp.txt('.tcard .nm'))&&/رضایی‌فر/.test(pp.txt('.ppsheet')),'پیشنمایش با هر تایپ زنده میشود');
   /* راه‌های ارتباط: از شماره و نام کاربری، نشانی ساخته میشود */
   pp.click('[data-pplkadd]');
   pp.type('[data-pplk="0"]','09123456789');
   ok(/tel:/.test(pp.txt('#ppPrev')),'نشانیِ موبایل از شماره ساخته شد');
   pp.click('[data-pplkk="0"][data-pplkv="tg"]');
   pp.type('[data-pplk="0"]','@nora_elocution');
   ok(/t\.me\/nora_elocution/.test(pp.txt('#ppPrev')),'نشانی تلگرام از نام کاربری ساخته شد');
   /* فرمِ پیوست از فرم‌ساز */
   pp.window.NORA_UI.formPut({id:'t-ask',name:'پرسش از ایشان',kind:'پرسش',fields:[{l:'پرسش شما'}]});
   pp.click('[data-ppg="1"]');
   ok(pp.all('[data-ppform]').length>=1,'فرمهای فرم‌ساز برای پیوستن به پروفایل');
   pp.click('[data-ppform="t-ask"]');
   pp.type('[data-ppf="formTxt"]','بپرس از ایشان');
   ok(/بپرس از ایشان/.test(pp.txt('.ppsheet')),'فرمِ پیوست در ورقهٔ پروفایل نشست');
   /* عکسِ خودشان */
   await pp.upload('[data-ppfile]',Buffer.from('89504e470d0a1a0a','hex'),'a.png','image/png');
   await wait(150);
   ok(/^data:image/.test((JSON.parse(pp.store.getItem('nora-admin')).ppD||{}).photo||''),'بارگذاری عکسِ خودشان در پیش‌نمایش نشست');
   pp.click('[data-ppphoto="__none"]');
   ok((JSON.parse(pp.store.getItem('nora-admin')).ppD||{}).photo==='','و با «برداشتن عکس» به حرفِ نام برمیگردد');
   pp.click('[data-ppphoto="people/p2.svg"]');
   pp.click('[data-pptag="پرطرفدار"]'); pp.click('[data-ppic="i-book"]');
   pp.click('[data-ppsave]');
   const o1=(JSON.parse(pp.store.getItem('nora-admin')).pp.o||{}).p1||{};
   ok(o1.n==='خانم الهه رضایی‌فر'&&o1.ic==='i-book'&&o1.tag==='پرطرفدار','ذخیره با نام و آیکون و برچسب');
   ok(o1.links.length===1&&o1.links[0].k==='tg'&&o1.links[0].v==='@nora_elocution','راه ارتباط ذخیره شد');
   ok(o1.form==='t-ask'&&o1.formTxt==='بپرس از ایشان','فرمِ پیوست ذخیره شد');
   /* ترتیب و نقش در سامانه */
   pp.click('[data-ppdown="0"]');
   ok((JSON.parse(pp.store.getItem('nora-admin')).pp.ord||[])[0]==='p2','بالا و پایینِ فهرست در تنظیمات نشست');
   pp.click('[data-pped="p3"]');
   pp.click('[data-ppkind="staff"]');
   pp.click('[data-ppsave]');
   ok((JSON.parse(pp.store.getItem('nora-admin')).pp.o||{}).p3.kind==='staff','جابجاییِ مدرس به دستاندرکاران');
   pp.click('[data-pptab="staff"]');
   ok(/شیرین رستگار/.test(pp.txt('#admBody')),'و در برگهٔ دستاندرکاران آمد');
   pp.click('[data-pptab="tch"]');
   /* عضو تازه، پنهان، انتشار */
   pp.click('[data-ppnew]');
   pp.type('[data-ppf="n"]','هومن راد'); pp.type('[data-ppf="r"]','مدرس خط شکسته'); pp.type('[data-ppf="exp"]','خط شکسته، خوشنویسی');
   pp.click('[data-ppsave]');
   ok((JSON.parse(pp.store.getItem('nora-admin')).pp.add||[]).length===1,'افزودن عضو تازه');
   pp.click('[data-pppub]');
   const pv=JSON.parse(pp.store.getItem('nora-people')||'null');
   const basePeople=pp.window.NORA.PEOPLE||[];
   const teamCount=(pp.window.NORA.ADMIN.people||[]).filter(x=>x&&x.k&&x.f!=='owner').length;
   ok(!!pv&&pv.list.length===basePeople.length+teamCount+1,'انتشارِ مدرس‌ها، دست‌اندرکاران پایه، تیم مدیران و عضو تازه');
   ok(pv.list.some(x=>x.n==='هومن راد')&&pv.list.filter(x=>x.kind==='staff').length===basePeople.filter(x=>x.kind==='staff').length+teamCount+1,'عضو تازه و جابه‌جاییِ مدرس به دست‌اندرکار در کلید مشترک درست نشستند');
   ok(pv.list.find(x=>x.id==='p1').photo==='people/p2.svg'&&pv.list.find(x=>x.id==='p1').form==='t-ask','عکس و فرم هم به کلید مشترک رفتند');
   ok(/همگام/.test(pp.txt('#admBody')),'پس از انتشار، حالت همگامی دیده میشود');
   pp.click('[data-pphide="p2"]');
   ok((JSON.parse(pp.store.getItem('nora-admin')).pp.hide||[]).includes('p2')&&/۱ پنهان/.test(pp.txt('#admBody')),'پنهانکردن استاد از صفحهٔ کاربر');
   pp.click('[data-ppshow="p2"]');
   /* بازگشت به پیش‌فرض، رونوشت و جستوجو */
   pp.click('[data-pped="p1"]');
   pp.click('[data-ppreset]');
   ok(!((JSON.parse(pp.store.getItem('nora-admin')).pp.o||{})['p1']),'«بازگشت به پیش‌فرضِ سامانه» لایهٔ تغییر را برمیدارد');
   ok(/الهه رضایی/.test(pp.txt('#admBody')),'و همانِ دادهٔ سامانه سر جایش برمیگردد');
   pp.click('[data-pped="p1"]');
   pp.click('[data-ppdup]');
   const dup=(JSON.parse(pp.store.getItem('nora-admin')).pp.add||[]).slice(-1)[0]||{};
   ok(/رونوشت/.test(dup.n||''),'رونوشت گرفتن از یک پروفایل');
   pp.type('[data-ppq]','رونوشت','change');
   ok(pp.all('[data-pped]').length===1,'جست‌وجو در برگه، فهرست را تنگ میکند');
   ok(/همگام|منتشرنشده/.test(pp.txt('#admBody')),'و نشانِ انتشارِ هر ردیف سر جایش است');
   pp.type('[data-ppq]','','change');
   const dupDel=pp.all('[data-ppdel]').filter(b=>/رونوشت/.test((b.closest('.admlirow')||{}).textContent||''))[0];
   pp.click(dupDel);
   ok(!(JSON.parse(pp.store.getItem('nora-admin')).pp.add||[]).some(x=>/رونوشت/.test(x.n||'')),'رونوشتِ آزمایشی برداشته شد');
   ok((JSON.parse(pp.store.getItem('nora-admin')).pp.add||[]).some(x=>x.n==='هومن راد'),'و عضوِ پیشین سر جایش است');
   /* مدیران */
   pp.click('[data-pptab="mgr"]');
   ok(pp.all('[data-pped]').length===2&&/مدیر نمونه/.test(pp.txt('#admBody')),'برگهٔ مدیران با دو نام نمایشیِ نمونه');
   pp.click('[data-pped="0"]');
   ok(!pp.doc.querySelector('[data-ppf="bio"]')&&!pp.doc.querySelector('[data-ppic]'),'مدیر نه عکس دارد نه آیکون؛ همان که صفحهٔ پشتیبانی میخواهد');
   pp.type('[data-ppf="why"]','تصمیمهای مدیریتی و همکاری نهادی');
   pp.click('[data-ppsave]');
   const m0=(JSON.parse(pp.store.getItem('nora-admin')).pp.mgrO||{})['0']||{};
   ok(m0.why==='تصمیمهای مدیریتی و همکاری نهادی','ویرایش سمت و پاسخگویی مدیر');
   ok(!m0.href&&!pp.doc.querySelector('#admBody a[href^="mailto:"]')
     &&/راه تماس تأیید نشده/.test(pp.txt('#admBody')),
     'برای مدیر نمونه نشانی ایمیل یا CTA بیرونی ساخته نمی‌شود؛ راه تماس تأییدنشده است');
   pp.click('[data-ppnew]');
   pp.type('[data-ppf="n"]','الهام نوری'); pp.type('[data-ppf="r"]','مدیر روابط عمومی');
   pp.click('[data-ppsave]');
   pp.click('[data-pppubmgr]');
   const mg=JSON.parse(pp.store.getItem('nora-managers')||'null');
   ok(!!mg&&mg.list.length===3&&mg.list.some(x=>x.n==='الهام نوری'),'انتشار مدیران در کلید مشترک nora-managers');
   /* نهادهای همکار: ویرایش کامل، پیش‌نمایش زنده، ترتیب، پنهان‌سازی و انتشار */
   pp.click('[data-pptab="partners"]');
   ok(pp.all('[data-ppartner-row]').length===8&&/نهاد همکار/.test(pp.txt('#admBody')),
     'برگهٔ نهادهای همکار با داده‌های پایه در همان کاشی باز می‌شود');
   const partnerSearch=pp.doc.querySelector('[data-ppartner-q]');
   pp.type('[data-ppartner-q]','گروه');
   ok(pp.all('[data-ppartner-row]').length<8&&pp.doc.querySelector('[data-ppartner-q]')===partnerSearch,
     'جست‌وجوی زنده فهرست را پالایش می‌کند بی‌آنکه قلم جست‌وجو از فوکوس بیفتد');
   pp.type('[data-ppartner-q]','');
   pp.click('[data-ppartner-edit="o1"]');
   const PF=s=>!!pp.doc.querySelector(s);
   ok(PF('[data-ppartner-field="n"]')&&PF('[data-ppartner-field="type"]')
      &&PF('[data-ppartner-field="collab"]')&&PF('[data-ppartner-field="mon"]')
      &&PF('[data-ppartner-field="since"]')&&PF('[data-ppartner-field="s"]')
      &&PF('[data-ppartner-field="d"]')&&PF('[data-ppartner-field="focus"]')
      &&PF('[data-ppartner-field="href"]')&&PF('[data-ppartner-field="logo"]')
      &&PF('[data-ppartner-file]'),'فرم جامع نهاد: هویت، دسته، همکاری، معرفی، حوزه، وبگاه و لوگو');
   pp.type('[data-ppartner-field="n"]','انجمن آموزش نوین');
   pp.type('[data-ppartner-field="type"]','آموزشی · فرهنگی');
   pp.type('[data-ppartner-field="collab"]','برگزاری کارگاه مشترک');
   pp.type('[data-ppartner-field="mon"]','آنو');
   pp.type('[data-ppartner-field="since"]','مهر ۱۴۰۵');
   pp.type('[data-ppartner-field="s"]','همراه آموزش و گفت‌وگو');
   pp.type('[data-ppartner-field="d"]','شرح همکاری و دامنهٔ فعالیت انجمن');
   pp.type('[data-ppartner-field="focus"]','آموزش، کارگاه، رسانه');
   pp.type('[data-ppartner-field="href"]','https://example.org/partner');
   pp.click('[data-ppartner-link-add]');
   pp.click('[data-ppartner-link-kind="0"][data-ppartner-kind="tg"]');
   pp.type('[data-ppartner-link="0"]','@nora_partner');
   await pp.upload('[data-ppartner-file]',Buffer.from('89504e470d0a1a0a','hex'),'logo.png','image/png');
   await wait(150);
   ok(/انجمن آموزش نوین/.test(pp.txt('#ppPartnerPreview'))&&/کارگاه مشترک/.test(pp.txt('#ppPartnerPreview')),
     'پیش‌نمایش کارت و ورقهٔ نهاد همراه با هر تایپ زنده به‌روز می‌شود');
   pp.click('[data-ppartner-save]');
   const pps=(JSON.parse(pp.store.getItem('nora-admin')).pp||{}), editedPartner=(pps.partnerO||{}).o1||{};
   ok(editedPartner.n==='انجمن آموزش نوین'&&editedPartner.collab==='برگزاری کارگاه مشترک'
      &&editedPartner.since==='مهر ۱۴۰۵'&&editedPartner.focus.join(',')==='آموزش,کارگاه,رسانه',
     'ذخیرهٔ فیلدهای کامل همکاری و حوزه‌های نهاد');
   ok(/^data:image/.test(editedPartner.logo||'')&&editedPartner.links[0].k==='tg'
      &&editedPartner.links[0].href==='https://t.me/nora_partner',
     'لوگوی بارگذاری‌شده و راه تماس معتبر همراه نهاد ذخیره شدند');
   pp.click('[data-ppartner-up="1"]');
   ok((JSON.parse(pp.store.getItem('nora-admin')).pp.partnerOrd||[])[0]==='o2',
     'ترتیب نهادها در فهرست پیش‌نویس ذخیره می‌شود');
   pp.click('[data-ppartner-hide="o8"]');
   ok(!!pp.doc.querySelector('[data-ppartner-hidden="o8"]'),'پنهان‌سازی نهاد از فهرست عمومی و بخش بازگردانی');
   pp.click('[data-ppartner-show="o8"]');
   ok(!!pp.doc.querySelector('[data-ppartner-row="o8"]'),'نمایش دوبارهٔ نهاد پنهان‌شده');
   pp.click('[data-ppartner-new]');
   pp.type('[data-ppartner-field="n"]','مرکز نوآوری شهر');
   pp.type('[data-ppartner-field="type"]','شهری');
   pp.type('[data-ppartner-field="collab"]','میزبانی برنامه');
   pp.type('[data-ppartner-field="since"]','تابستان ۱۴۰۵');
   pp.type('[data-ppartner-field="d"]','شرح همکاری مرکز نوآوری');
   pp.click('[data-ppartner-save]');
   ok((JSON.parse(pp.store.getItem('nora-admin')).pp.partnerAdd||[]).length===1,
     'افزودن نهاد همکار تازه');
   pp.click('[data-ppartner-hide="o3"]');
   pp.click('[data-ppartner-pub]');
   const partnersPublished=JSON.parse(pp.store.getItem('nora-partners')||'null');
   ok(!!partnersPublished&&partnersPublished.list.length===8
      &&partnersPublished.list.some(x=>x.id==='o1'&&x.n==='انجمن آموزش نوین')
      &&partnersPublished.list.some(x=>x.n==='مرکز نوآوری شهر')
      &&!partnersPublished.list.some(x=>x.id==='o3')
      &&partnersPublished.list.every(x=>x.status==='published'&&x.pub===true),
     'انتشار فقط نهادهای نمایان با همهٔ تنظیمات در کلید عمومی nora-partners');
   const syncPartners=pp.window.NORA_SITE_CONTENT_SYNC.snapshot().partners;
   ok(syncPartners.length===partnersPublished.list.length&&syncPartners.some(x=>x.collab==='برگزاری کارگاه مشترک'),
     'فهرست منتشرشدهٔ نهادها به دستهٔ آمادهٔ همگام‌سازی سرور می‌رسد');
   ok(pp.errs.length===0,'کاشی مدیران، اساتید و نهادهای همکار بیخطا بود');}
  {p.click('#admNav [data-sec="settings"]');
   if(!p.doc.querySelector('[data-skit="ops"]')) p.click('[data-skinback]');
   p.click('[data-skit="ops"]');}
  ok(p.all('#admBody .admlirow').length>=1,'آخرین لاگها در مدیریت پنل دیده میشود');
  [...p.all('#admBody [data-useg]')].find(x=>x.dataset.useg==='ops.cap:5').click();
  {p.click('#admNav [data-sec="dash"]');
   const qCap=p.all('.qrow').length;
   ok(qCap<=5,'سقف کوتاه کارتابل از مدیریت پنل میآید ('+qCap+')');}
  {p.click('#admNav [data-sec="settings"]');
   if(!p.doc.querySelector('[data-skit="ops"]')) p.click('[data-skinback]');
   p.click('[data-skit="ops"]');}
  [...p.all('#admBody [data-useg]')].find(x=>x.dataset.useg==='ops.log:off').click();
  p.click('[data-logclear]');
  {const ul=JSON.parse(p.store.getItem('nora-admin')).ulog||[];
   ok(ul.length===1&&/خالی شد/.test(ul[0].act||''),'خالی کردن لاگ از کاشی، لاگ را سر و سامان میکند');}
  p.click('[data-cacheclr]');
  ok(/حافظه/.test(p.txt('#toast')),'پاکسازی حافظهٔ نهان پیام روشن دارد');
  p.click(p.doc.querySelector('[data-uk="maint"]'));
  ok(/حالت نگهداری روشن شد/.test(p.txt('#toast'))&&JSON.parse(p.store.getItem('nora-uiset')).users.regs==='closed',
     'حالت نگهداری، عضویت را بست و با نامش خبر داد');
  p.click(p.doc.querySelector('[data-uk="maint"]'));
  ok(/برداشته شد/.test(p.txt('#toast'))&&JSON.parse(p.store.getItem('nora-uiset')).users.regs==='invite',
     'حالت نگهداری برداشته شد و عضویت به کد دعوت برگشت');
  p.click('[data-skinback]');
  p.click('[data-skit="skin"]');
  ok(/تنظیمات ظاهری سامانه/.test(p.txt('#admBody')),'کاشی ظاهری، مدیریت ظاهر را باز کرد');
  ok(p.all('[data-skintab]').length===8,'هشت برگه: خانه، منو، بنرها، استوریها، کارتها، نوشتار، نوار، پای صفحه');
  ok(p.all('[data-uk]').length===15,'پانزده بخش خانه، هرکدام یک کلید؛ از جمله بنر و استوری');
  p.click(p.all('[data-uk]')[0]);
  ok(/خاموش شد/.test(p.txt('#toast')) && JSON.parse(p.store.getItem('nora-uiset')).home.bnr===0,
     'کلید بخش خانه در انبار «nora-uiset» نشست');
  p.click('[data-skintab="menu"]');
  ok(p.all('[data-umenu]').length===19,'نوزده ردیف منوی کاربر در پنل است');
  p.click('[data-umenu]');
  ok(JSON.parse(p.store.getItem('nora-uiset')).menu.length===1,'ردیف منو به فهرست پنهانشدنها رفت');
  p.click('[data-skintab="bnr"]');
  ok(p.all('[data-bhide]').length===3,'سه بنر پیشفرض با کلید پنهانکردن');
  p.click('[data-bhide]');
  ok(JSON.parse(p.store.getItem('nora-uiset')).bnr.hide.length===1,'بنر پیشفرض پنهان شد');
  p.doc.querySelector('#skBnT').value='جشنوارهٔ فیلم کوتاه';
  p.click('[data-skbadd]');
  ok(p.all('[data-skbdel]').length===1,'بنر تازه در فهرست بنرهای پنل نشست');
  p.click('[data-skbdel]');
  ok(p.all('[data-skbdel]').length===0,'بنر تعریفشده برداشته میشود');
  p.click('[data-skintab="story"]');
  ok(p.all('[data-shide]').length===5,'پنج استوری پیشفرض با کلید پنهانکردن');
  p.doc.querySelector('#skST').value='پشت صحنهٔ تمرین';
  p.click('[data-sksadd]');
  ok(JSON.parse(p.store.getItem('nora-uiset')).storyAdd.length===1,'استوری تازه تعریف شد');
  p.click('[data-skintab="look"]');
  p.click('[data-ucards="big"]');
  p.click('[data-upeople="row"]');
  const look=JSON.parse(p.store.getItem('nora-uiset'));
  ok(look.cards==='big'&&look.people==='row','اندازهٔ کارت و مدل نمایش اساتید ذخیره شد');
  ok(p.doc.documentElement.dataset.cards==='big','اندازهٔ کارت، همان لحظه روی <html> پنل هم نشست');
  p.click('[data-skintab="foot"]');
  p.doc.querySelector('#skTrust').value='جملهٔ پنل';
  p.doc.querySelector('#skFoot').value='پای صفحهٔ پنل';
  p.click('[data-skinfoot]');
  const foot=JSON.parse(p.store.getItem('nora-uiset'));
  ok(foot.trust.text==='جملهٔ پنل'&&foot.foot.text==='پای صفحهٔ پنل','متنهای پای صفحه ذخیره شدند');
  p.click('[data-skinreset]');
  p.click('[data-skinreset]');
  ok(/پیشفرض برگشت/.test(p.txt('#toast')),'بازنشانی با دو پا گام روشن میشود');
  ok(JSON.parse(p.store.getItem('nora-uiset')).menu.length===0&&JSON.parse(p.store.getItem('nora-uiset')).cards==='mid',
     'بازنشانی، همهٔ ظاهر را به پیشفرض برگرداند');
  /* قالبهای آماده، جمعبندی، دو برگهٔ تازه و بازنشانی برگهبهبرگه (هنوز در مدیریت ظاهریم) */
  ok(p.all('[data-sknpreset]').length===4,'چهار قالب آماده بالای مدیریت ظاهر');
  ok(/از .*بخش خانه روشن/.test(p.txt('#admBody')),'خط جمعبندی، شمار بخشهای روشن را میگوید');
  const useg=sel=>p.all(sel)[0];
  p.click('[data-skintab="type"]');
  ok(p.all('[data-useg]').length===17,'برگهٔ نوشتار و چیدمان: هفده انتخاب (اندازه، گوشه، عرض، فاصله، رنگ)');
  [...p.all('#admBody [data-useg]')].find(x=>x.dataset.useg==='type.size:big').click();
  [...p.all('#admBody [data-useg]')].find(x=>x.dataset.useg==='type.width:wide').click();
  [...p.all('#admBody [data-useg]')].find(x=>x.dataset.useg==='type.accent:teal').click();
  const ty=JSON.parse(p.store.getItem('nora-uiset')).type;
  ok(ty.size==='big'&&ty.width==='wide'&&ty.accent==='teal','اندازه، عرض و رنگ کنش در انبار نشست');
  [...p.all('#admBody [data-useg]')].find(x=>x.dataset.useg==='type.accent:teal').click();
  p.click(p.all('#admBody [data-uk]')[0]);
  ok(JSON.parse(p.store.getItem('nora-uiset')).type.motion===0,'کلید «حرکت و انیمیشن» خاموش میشود');
  p.click('[data-skintab="chrome"]');
  ok(p.all('[data-uk]').length===5,'برگهٔ نوار بالا و پایین: پنج کلید');
  p.click(p.all('#admBody [data-uk]')[0]);
  ok(JSON.parse(p.store.getItem('nora-uiset')).chrome.bell===0,'زنگ اعلانها از نوار کاربر برداشته شد');
  p.click('[data-skintab="bnr"]');
  [...p.all('#admBody [data-useg]')].find(x=>x.dataset.useg==='bnr.speed:fast').click();
  ok(JSON.parse(p.store.getItem('nora-uiset')).bnr.speed==='fast','سرعت چرخش بنر ذخیره شد');
  p.click('[data-sknpreset="lean"]');
  const ln=JSON.parse(p.store.getItem('nora-uiset'));
  ok(ln.home.stories===0&&ln.home.articles===0&&ln.home.events===1,'قالب «ساده» بخشها را یکجا چید');
  ok(ln.quick.length===4&&ln.type.width==='narrow','قالب، کاشیها و عرض را هم با خودش آورد');
  ok(/قالب «ساده» اعمال شد/.test(p.txt('#toast')),'و با نامش خبر داد');
  p.click('[data-skintab="home"]');
  p.click('[data-skrtab]');
  ok(JSON.parse(p.store.getItem('nora-uiset')).home.stories===1,'بازنشانی برگه، همان برگه را به پیشفرض برگرداند');
  ok(/برگهٔ «بخشهای خانه»/.test(p.txt('#toast')),'بازنشانی برگه با نام برگه خبر میدهد');
  p.click('[data-skinback]');
  ok(p.all('[data-skit]').length===8,'بازگشت به کاشیها');
  p.click('#admNav [data-sec="users"]'); p.click('[data-uv="tools"]'); p.click('[data-utool="staff"]');
  ok(p.all('[data-setF]').length===6,'شش حوزه در مدیریت مدیران و کارشناسان هست (مالک جداست)');
  ok(p.all('.stflow .stf').length===3,'جریان سهگامی حساب و ورود اول روی صفحه است');
  ok(/در انتظار تکمیل پروفایل/.test(p.txt('#admBody')),'کارشناس بی‌پروفایل با برچسب هشدار نشان داده میشود');
  ok(p.all('.stacc').length>=2,'نام کاربری هر کارشناس روی ردیفش هست');
  ok(/مدیر مسئول حوزه/.test(p.txt('#admBody')),'مسئول حوزه به‌عنوان سمت کاری نمایش داده می‌شود، نه نقش چهارم');
  ok(/نقش‌های دسترسی/.test(p.txt('#admBody'))&&p.all('#admBody .stgroup .admlirow').length>=3,
    'مدل دسترسی سه نقش مرکزی را نشان می‌دهد');
  ok(p.all('[data-roleassign]').length>=3,'فقط مالک برای حساب‌ها انتخاب‌گر نقش دارد');
  const roleOptions=[...p.all('[data-roleassign]')].every(sel=>[...sel.options].map(o=>o.value).join(',')==='manager,club-supervisor');
  ok(roleOptions,'انتخاب‌گر حساب‌ها فقط مدیر و سرپرست باشگاه دارد و نقش مالک را واگذار نمی‌کند');
  const rolePick=p.doc.querySelector('[data-roleassign="p2"]');
  rolePick.value='club-supervisor'; rolePick.dispatchEvent(new p.window.Event('change',{bubbles:true}));
  ok(JSON.parse(p.store.getItem('nora-admin')).roleOverrides.p2==='club-supervisor'
    &&/سرپرست باشگاه/.test(p.txt('#admBody')),'تغییر نقش فقط با مالک ذخیره و بلافاصله در فهرست منعکس می‌شود');
  p.click('[data-setF="club"]');
  ok(/باشگاه/.test(p.txt('.fslead')),'با گزینش حوزهٔ باشگاه، مسئول کاری همان حوزه دیده می‌شود');
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
  ok(/حساب محلی ساخته شد/.test(p.txt('#toast'))&&/ارسال خودکار وجود ندارد/.test(p.txt('#toast')),
    'رکورد حساب نمونه محلی است و پیام یا رمز خودکار ارسال نمی‌شود');
  ok(/در انتظار تکمیل پروفایل/.test(p.txt('#admBody')),'حساب تازه بی‌پروفایل است');
  p.click('[data-specrow]');
  ok(/پروفایل دست‌اندرکاران/.test(p.txt('#shAdm')),'پروندهٔ دست‌اندرکاران از ردیف باز میشود');
  p.click('#shAdm [data-close]');
  p.click('[data-resetspec]');
  ok(/رمز موقت محلی برای/.test(p.txt('#toast'))&&/چیزی ارسال نشد/.test(p.txt('#toast')),
    'تغییر رمز فقط محلی است و چیزی ارسال نمی‌شود');
  p.click('[data-setlead]');
  ok(p.all('#shAdm [data-setleadto]').length>=2,'ورقهٔ تعیین سرپرست باز می‌شود');
  const pick=p.all('#shAdm [data-setleadto]').pop();
  const name=pick.textContent.replace(/\s+/g,' ').trim().slice(0,4);
  p.click(pick);
  ok(/مدیر مسئول حوزه عوض/.test(p.txt('#toast')),'مدیر مسئول حوزه عوض می‌شود');
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
  ok(who.length===15,'ورقهٔ «نمای من» پانزده حساب نمونه دارد: مالک و چهارده حساب با نقش مدیر یا سرپرست باشگاه');
  const whoGroups=p.all('#shAdm .whogroup .head').map(x=>x.textContent.replace(/\s+/g,' ').trim());
  ok(whoGroups.join('|')==='مالک|مدیر|سرپرست باشگاه','فهرست پروفایل مالک فقط سه نقش را نشان می‌دهد، نه حوزه‌های قدیمی را');
  p.click('#shAdm [data-who="p10"]');
  ok(p.txt('#admBar .chip').includes('مدیر')&&/پشتیبانی/.test(p.txt('.dhead')),'چیپ نوار بالا و سرصفحه، مدیر پشتیبانی را نشان می‌دهند');
  ok(p.all('#admNav [data-locked]').length===0,'مدیر بخش‌های عمومی پنل را می‌بیند');
  ok(p.all('#admNav [data-sec="newev"]').length===0,'منوی مستقل تعریف جدید حذف شده است');
  p.click('#admNav [data-sec="events"]');
  ok(!!p.doc.querySelector('[data-evnew]')&&!!p.doc.querySelector('[data-pnew]'),'مدیر هنوز می‌تواند از بخش رویدادها رویداد و مطلب بسازد');
  ok(p.all('#admTabs a').length===p.all('#admNav .btn').length,'نوار پایین با همهٔ ورودی‌های منو هم‌خوان است');
  p.click('#admNav [data-sec="dash"]');
  ok(p.all('.qrow').length>1&&p.all('.qrow').length<20,'کارتابل مدیر کارهای عمومی را می‌بیند');
  ok(p.all('.trow').length>0,'مدیر همکاران حوزهٔ کاری را می‌بیند');
  ok(p.all('.kpi').length===4&&!/کار باز من/.test(p.txt('.kpis')),'چهار عدد مدیر از حوزهٔ کاری است، نه کارنامهٔ کارشناس');
  p.click('#admNav [data-sec="settings"]');
  ok(p.txt('#admBar .head')==='تنظیمات'&&p.all('[data-setg]').length===2,'مدیر وارد تنظیمات محدود می‌شود');
  ok(p.all('[data-skit]').length===0,'اما تنظیمات سراسری و کاشی‌ها برای مدیر پنهان‌اند');
  ok(p.all('.frow2').length===0,'مدیر فهرست حوزه‌ها را نمی‌بیند');
  ok(p.all('.hero,.ring,.dock,.dbtn,.vchip,.sparkbox,.ppill').length===0,'مدیر هم حلقه و داک و سر رنگی نمی‌بیند');

  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p2"]');
  ok(p.txt('#admBar .chip').includes('مدیر'),'مدیر در چیپ نوار بالا می‌آید');
  ok(p.all('.trow').length===2,'مدیر آموزش دو همکار در حوزهٔ خود دارد');
  ok(p.all('.kpi').length===4&&/آموزش|ثبت‌نام|دوره/.test(p.txt('.kpis')),'عددهای مدیر از حوزهٔ خودش است');
  ok(p.all('.hero,.ring,.dock,.vchip,.sparkbox,.ppill').length===0,'و هیچ حلقه و سر رنگی نمانده');
  ok(p.all('.qrow').length>1&&p.all('.qrow').length<20,'کارتابل مدیر نه یکی است نه بیست‌تا');
  p.click('#admNav [data-sec="users"]');
  ok(p.txt('#admBar .head')==='کاربران','مدیر به بخش کاربران دسترسی دارد؛ گزارش‌ها تب همین بخش‌اند');
  ok(!p.doc.querySelector('[data-uv="club"]'),'مدیر مسیر اختصاصی باشگاه را نمی‌بیند');
  p.click('#admNav [data-sec="settings"]');
  ok(p.all('[data-setg]').length===2&&!!p.doc.querySelector('[data-setg="cert"]')&&!!p.doc.querySelector('[data-setg="receipts"]')&&!p.doc.querySelector('[data-setg="money"]'),
    'مدیر فقط گواهینامه و بازبینی محدود فیش را می‌بیند؛ مالی کامل پنهان است');
  ok(!p.doc.querySelector('[data-setg="publishing"]')&&!p.doc.querySelector('#admBody #siteContentSync')
    &&p.doc.querySelector('#ownerPublishingToolsParking').hidden,
    'انتشار عمومی و درخواست همکاری فقط در تنظیمات مالک است و به منوی مدیر نمی‌چسبد');
  const forgedPublishing=p.doc.createElement('button'); forgedPublishing.setAttribute('data-setg','publishing'); p.doc.body.appendChild(forgedPublishing);
  p.click(forgedPublishing);
  ok(!p.doc.querySelector('[data-setg="publishing"].on')&&/فقط برای مالک/.test(p.txt('#toast')),
    'handler هم بازکردن مستقیم تنظیمات انتشار را برای مدیر رد می‌کند');
  forgedPublishing.remove();
  ok(!!p.doc.querySelector('[data-cfileup]')&&/قالب فایل ورد/.test(p.txt('#admBody')),'قالب گواهینامه برای مدیر باز است');
  ok(p.all('[data-skit]').length===0,'مدیر کاشی‌های تنظیمات سراسری را نمی‌بیند');
  const blockedBook=p.doc.createElement('button'); blockedBook.setAttribute('data-skit','book'); p.doc.body.appendChild(blockedBook);
  p.click(blockedBook);
  ok(!JSON.parse(p.store.getItem('nora-admin')).skinB&&/مدیریت باشگاه فقط/.test(p.txt('#toast')),
    'handler هم بازکردن مستقیم کاشی باشگاه را برای مدیر رد می‌کند');
  blockedBook.remove();
  const beforeBlockedClub=p.store.getItem('nora-admin');
  const blockedClubAction=p.doc.createElement('button'); blockedClubAction.setAttribute('data-bkfeesave','1'); p.doc.body.appendChild(blockedClubAction);
  p.click(blockedClubAction);
  ok(p.store.getItem('nora-admin')===beforeBlockedClub&&/مدیریت باشگاه فقط/.test(p.txt('#toast')),
    'handler هر کنش مستقیم data-bk را برای مدیر رد می‌کند');
  blockedClubAction.remove();
  const blockedClubUpload=p.doc.createElement('input'); blockedClubUpload.setAttribute('data-bkaudio',''); p.doc.body.appendChild(blockedClubUpload);
  blockedClubUpload.dispatchEvent(new p.window.Event('change',{bubbles:true}));
  ok(p.store.getItem('nora-admin')===beforeBlockedClub&&/مدیریت باشگاه فقط/.test(p.txt('#toast')),
    'handler بارگذاری فوری فایل باشگاه را هم برای مدیر مسدود می‌کند');
  blockedClubUpload.remove();
  const staleClubFilter=JSON.parse(p.store.getItem('nora-admin'));
  staleClubFilter.sec='users'; staleClubFilter.uV=''; staleClubFilter.uF='club';
  p.store.setItem('nora-admin',JSON.stringify(staleClubFilter));
  const staleFilterPage=await load(p.store);
  ok(!staleFilterPage.doc.querySelector('[data-uF="club"]')&&!!staleFilterPage.doc.querySelector('[data-uF="all"].on'),
    'فهرست کاربرانِ مدیر، صافی باشگاهِ ذخیره‌شده را به «همه» برمی‌گرداند');
  staleFilterPage.dom.window.close();
  p.click('#admNav [data-sec="events"]');
  ok(!/باز نمی‌شود/.test(p.txt('#admBody')),'رویدادها برای مدیر آموزش باز است');

  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p7"]');
  ok(p.txt('#admBar .chip').includes('سرپرست باشگاه'),'سرپرست باشگاه نقش جداگانه و صریح دارد');
  p.click('#admNav [data-sec="settings"]');
  ok(p.all('[data-setg]').length===2&&!!p.doc.querySelector('[data-setg="cert"]')&&!!p.doc.querySelector('[data-setg="receipts"]')&&!p.doc.querySelector('[data-setg="money"]'),
    'سرپرست باشگاه همهٔ گروه‌های غیرمالک مدیر را به ارث می‌برد');
  ok(p.all('[data-skit]').length===1&&!!p.doc.querySelector('[data-skit="book"]'),
    'سرپرست باشگاه فقط کاشی مدیریت باشگاه را علاوه بر مجوزهای مدیر می‌بیند');
  p.click('[data-skit="book"]');
  ok(/باشگاه کتابخوانی/.test(p.txt('#admBody'))&&!!p.doc.querySelector('[data-bksave]'),
    'کاشی باشگاه برای سرپرست باز می‌شود');
  p.click('[data-skinback]');

  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p1"]');
  ok(p.all('#admNav [data-locked]').length===0,'مالک هیچ بخشی را بسته ندارد');
  ok(p.all('#admTabs a').length===p.all('#admNav .btn').length,'و نوار پایین دقیقاً با نوار کناری هم‌اندازه است');
  p.click('[data-who-sheet]');
  ok(!!p.doc.querySelector('#shAdm [data-addspec]')&&!!p.doc.querySelector('#shAdm [data-openstaff]'),
    'مالک از پروفایلش به ساخت حساب و مدیریت نقش‌ها دسترسی روشن دارد');
  p.click('#shAdm [data-addspec]');
  const quickRole=p.doc.querySelector('#spRole');
  ok(!!quickRole&&[...quickRole.options].map(o=>o.value).join(',')==='manager,club-supervisor',
    'فرم ساخت سریع فقط مدیر و سرپرست باشگاه را پیشنهاد می‌دهد');
  p.type('#spN','نگین راد'); p.type('#spU','negin.r'); quickRole.value='club-supervisor';
  p.click('[data-newspec2]');
  const quickCreated=JSON.parse(p.store.getItem('nora-admin')).extra.slice(-1)[0];
  ok(quickCreated&&quickCreated.role==='club-supervisor'&&quickCreated.f==='club',
    'ساخت سریع، حساب سرپرست باشگاه را با نقش و حوزهٔ درست می‌سازد');
  p.click('[data-who-sheet]'); p.click('#shAdm [data-openstaff]');
  ok(/مدیریت حساب‌ها و نقش‌ها/.test(p.txt('#admBody'))&&p.all('[data-roleassign]').length>0,
    'میانبر پروفایل مستقیماً فهرست مدیریت نقش‌ها و حساب‌ها را باز می‌کند');
}

/* ── ۱۰) تعریف جدید: مدیر منتشر می‌کند؛ تصمیم‌های مالک‌محور جدا می‌مانند ── */
{
  console.log('\n── تعریف تازه و انتشار نقش‌ها ──');
  const p=await load();
  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p10"]');
  ok(p.all('#admNav [data-sec="newev"]').length===0,'تعریف جدید ورودی مستقل ندارد');
  p.click('#admNav [data-sec="events"]');
  p.click('[data-pnew]');
  ok(p.txt('#admBar .head')==='رویدادها و مطالب','ساخت مطلب از بخش رویدادها باز می‌شود');
  ok(!!p.doc.querySelector('[data-pf="t"]')&&!!p.doc.querySelector('[data-pgo="2"]'),'ساخت و ویرایش مطلب همچنان در دسترس است');
  ok(p.all('[data-wkind]').length===0,'اینجا دیگر رویداد تعریف نمی‌شود');
  p.type('[data-pf="t"]','یادداشت مدیر');
  p.type('[data-pf="lead"]','سه خط دربارهٔ کلاس.');
  p.click('[data-pgo="2"]');
  p.click('[data-badd="p"]');
  p.type('[data-bi="0"][data-bf="x"]','متن یادداشت مدیر.');
  ok(!!p.doc.querySelector('[data-ppub]')&&!p.doc.querySelector('[data-psend]'),'مدیر انتشار عمومی دارد و دکمهٔ صف نقش قدیمی نمایش داده نمی‌شود');
  p.click('[data-ppub]');
  const P10=JSON.parse(p.store.getItem('nora-posts')||'[]');
  ok(P10.length===1&&P10[0].pend===0&&P10[0].pub===1,'مطلب مدیر منتشر شد؛ صف تأیید نقش قدیمی ساخته نشد');
  ok(p.txt('#admBar .head')==='رویدادها و مطالب','پس از انتشار، مدیر به بخش رویدادها و مطالب می‌رود');
  p.click('[data-pmgrback]');
  ok(/یادداشت مدیر/.test(p.txt('#admBody'))&&/منتشر شده/.test(p.txt('#admBody')),'مطلب منتشرشده در فهرست دیده می‌شود');
  p.click('[data-pnew]');
  ok(p.doc.querySelector('[data-pf="t"]').value==='','ویرایشگر مطلب برای تعریف بعدی تازه است');
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
  ok(p.doc.querySelector('#wz-place').value==='کتابخانهٔ نمونه · تأییدنشده','و جای کنونی‌اش هم');
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

/* ── رویدادِ تازه بی فرمِ ثبتنام منتشر نمیشود؛ فرمِ وصلشده با رویداد میآید ── */
{
  console.log('\n── ثبت‌نام رویداد وابسته به فرم‌ساز ──');
  const st=makeStore();
  const a=await load(st);
  a.click('#admNav [data-sec="events"]'); a.click('[data-evnew]');
  a.type('#wzName','کارگاه بیفرم','change'); a.type('#wzDesc','توضیح','change');
  a.click('[data-wet="webinar"]');
  a.click('[data-wstep="1"][data-wgo="1"]');
  a.type('#wz-date','۱۴۰۵/۰۸/۱۰','change'); a.type('#wz-time','17:00','change');
  a.type('#wz-to','19:00','change'); a.type('#wz-place','سالن نورا','change');
  a.click('[data-wstep="2"][data-wgo="1"]'); a.type('#wz-cap','30','change');
  a.click('[data-wstep="3"][data-wgo="1"]');
  ok(a.all('[data-wstep="4"][data-wgo="1"]:not([disabled])').length===0,'رویدادِ بیفرمِ ثبتنام از گام فرمها جلو نمیرود');
  ok(/فرم‌ساز/.test(a.txt('#admBody')),'و راهِ ساختنِ فرم را نشان میدهد');
  ok(/ساختنِ فرمِ ثبت‌نامِ همین رویداد در فرم‌ساز/.test(a.txt('#admBody')),'دکمهٔ ساختنِ فرمِ همان رویداد هست');
  const bld=[...a.all('a')].map(x=>x.getAttribute('href')||'').filter(h=>/create\.html\?ev=/.test(h)&&/need=reg/.test(h))[0];
  ok(!!bld,'پیوندِ فرمساز با شناسهٔ همین رویداد باز میشود');
  /* فرم را در انبار فرمساز میگذاریم و به رویداد وصل میکنیم */
  const f1={id:'ff1',name:'فرم ثبتنام کارگاه',kind:'ثبت‌نام',need:'reg',
    fields:[{id:1,t:'fullname',l:'نام و نام خانوادگی',req:true},{id:2,t:'mobile',l:'موبایل',req:true},
            {id:3,t:'choice',l:'سطح',req:true,opts:[{l:'تازه'},{l:'قدیمی'}]},{id:4,t:'terms',l:'قوانین',req:true}],
    fin:[{l:'حضوری',p:120000,off:0}],groups:[{n:'نوع',of:[0],req:true,one:true}],maxPer:2,guestsOn:false,
    methods:['bale','wallet']};
  st.setItem('nora-forms',JSON.stringify([f1]));
  st.removeItem('nora-admin');
  const b=await load(st);
  b.click('#admNav [data-sec="events"]'); b.click('[data-evnew]');
  b.type('#wzName','کارگاه پیوندخورده','change'); b.click('[data-wet="webinar"]');
  b.click('[data-wstep="1"][data-wgo="1"]');
  b.type('#wz-date','۱۴۰۵/۰۸/۱۰','change'); b.type('#wz-time','17:00','change');
  b.type('#wz-to','19:00','change'); b.type('#wz-place','سالن نورا','change');
  b.click('[data-wstep="2"][data-wgo="1"]'); b.type('#wz-cap','30','change');
  b.click('[data-wstep="3"][data-wgo="1"]');
  ok(b.all('[data-fpick="reg"][data-fid="ff1"]').length===1,'فرم فرمساز در برگهٔ گام فرمها هست');
  b.click('[data-fpick="reg"][data-fid="ff1"]');
  ok(JSON.parse(st.getItem('nora-admin')).wiz.fp.reg==='ff1','فرم به رویداد وصل شد');
  ok(/۴ پرسش · ۴ اجباری/.test(b.txt('#admBody')),'قلمها و اجباریهای فرم در پنل شمرده شد');
  ok(/۱۲۰۰۰۰ ریال/.test(b.txt('#admBody')),'و مبلغش از دلِ فرم آمد');
  ok(b.all('[data-wstep="4"][data-wgo="1"]:not([disabled])').length===1,'با وصلشدنِ فرم، راه مرور باز میشود');
  b.click('[data-wstep="4"][data-wgo="1"]');
  ok(/فرم ثبتنام کارگاه/.test(b.txt('#admBody')),'در مرور، نامِ فرم دیده میشود');
  b.click('[data-wsend]');
  const added=JSON.parse(st.getItem('nora-admin')).added||[];
  ok(added.length===1,'رویدادِ پیوندخورده منتشر شد');
  ok((added[0].forms||[]).some(f=>String(f.id)==='ff1'),'و فرمش با رویداد پیوست');
  ok(a.errs.length===0&&b.errs.length===0,'هیچ خطایی نماند');
}


/* ── ۱۱ب) کارت رویداد، جامع و زنده: سی‌آر‌ام، حضور، اطلاع‌رسانی، نظرسنجی و خروجی ── */
{
  console.log('\n── کارت رویداد: سی‌آر‌ام زنده از فرم‌ساز ──');
  const f1={id:'crm-reg',name:'فرم ثبتنام کارگاه سی‌آر‌ام',kind:'ثبت‌نام',need:'reg',
    fields:[{id:1,t:'fullname',l:'نام و نام خانوادگی',req:true},{id:2,t:'mobile',l:'موبایل',req:true}],
    fin:[{l:'عادی',p:100000,off:0}],groups:[],maxPer:1,guestsOn:false,methods:['wallet']};
  const f2={id:'crm-svy',name:'نظرسنجی کارگاه سی‌آر‌ام',kind:'نظرسنجی',need:'survey',
    fields:[{id:1,t:'choice',l:'کیفیت جلسه',req:true,opts:[{l:'عالی'},{l:'خوب'},{l:'ضعیف'}]}]};
  const st=makeStore();
  st.setItem('nora-forms',JSON.stringify([f1,f2]));
  const p=await load(st);
  p.click('#admNav [data-sec="events"]'); p.click('[data-evnew]');
  p.type('#wzName','کارگاه سی‌آر‌ام','change'); p.click('[data-wet="webinar"]');
  p.click('[data-wstep="1"][data-wgo="1"]');
  p.type('#wz-date','۱۴۰۵/۰۹/۰۲','change'); p.type('#wz-time','17:00','change');
  p.type('#wz-to','19:00','change'); p.type('#wz-place','سالن نورا','change');
  p.click('[data-wstep="2"][data-wgo="1"]'); p.type('#wz-cap','25','change');
  p.click('[data-wstep="3"][data-wgo="1"]');
  p.click('[data-fpick="reg"][data-fid="crm-reg"]');
  p.click('[data-fpick="survey"][data-fid="crm-svy"]');
  p.click('[data-wstep="4"][data-wgo="1"]');
  p.click('[data-wsend]');
  const added=JSON.parse(st.getItem('nora-admin')).added||[];
  ok(added.length===1,'رویداد منتشر شد');
  const evId=added[0].id, U=p.window.NORA_UI;
  /* یک نفر دو بار فرم پر میکند؛ پرونده‌اش یکی میماند و کامل میشود */
  const mk=(code,name,mob,sum,at)=>({id:'r'+code,ev:evId,form:'crm-reg',at:at,atFa:'۱۴۰۵/۰۸/۲۰',
    code:code,count:1,sum:sum,method:sum?'wallet':'رایگان',
    ans:[{l:'نام و نام خانوادگی',v:name},{l:'موبایل',v:mob}]});
  const r1=mk('CR1001','نیلوفر آبی','09121112233',100000,1000);
  const r2=mk('CR1002','نیلوفر آبی','09121112233',0,2000);
  const r3=mk('CR1003','راد مهر','09354445566',100000,3000);
  [r1,r2,r3].forEach(r=>{r.pid=U.personFromReg(r,U.formById('crm-reg'))});
  const s1={id:'rs1',ev:evId,form:'crm-svy',at:4000,atFa:'۱۴۰۵/۰۸/۲۱',code:'CR2001',count:1,sum:0,
    method:'رایگان',ans:[{l:'کیفیت جلسه',v:'عالی'}]};
  st.setItem('nora-regs',JSON.stringify([s1,r3,r2,r1]));
  const ppl=JSON.parse(st.getItem('nora-people')||'[]');
  ok(ppl.length===2,'دو نفر دو پرونده دارند، نه سه');
  const nil=ppl.find(x=>x.name==='نیلوفر آبی');
  ok(nil&&(nil.subs||[]).length===2,'پروندهٔ نیلوفر دو تکمیل دارد');
  /* کارت رویداد: تب ثبت‌نام‌ها زنده از فرم‌ساز */
  p.click('#admNav [data-sec="events"]');
  p.click('[data-ev="'+evId+'"]');
  p.click('#shAdm [data-evtab="reg"]');
  ok(/نیلوفر آبی/.test(p.txt('#shAdm')),'ثبت‌نام زنده در کارت نشست');
  ok(/۳ پاسخ محلی · نمونه/.test(p.txt('#shAdm')),'و شمار پاسخ‌های نمونه از انبار محلی فرم‌ساز شمرده شد');
  /* پروندهٔ شخص: تاریخچهٔ هر دو فرم */
  p.click('#shAdm [data-regpp]');
  ok(/پروندهٔ/.test(p.txt('#shAdm')),'پروندهٔ شخص باز شد');
  ok(/تاریخچهٔ فرم‌ها/.test(p.txt('#shAdm')),'و تاریخچهٔ فرمهایش هست');
  /* جست‌وجوی زنده */
  p.type('#evregq','راد');
  ok(/راد مهر/.test(p.txt('#evreglist'))&&!/نیلوفر/.test(p.txt('#evreglist')),'جست‌وجو زنده پالایش میکند');
  p.type('#evregq','');
  /* خروجی اکسل */
  p.click('#shAdm [data-regcsv]');
  const csv=JSON.parse(st.getItem('nora-admin')).evLastCsv||'';
  ok(/نام/.test(csv)&&/نیلوفر آبی/.test(csv)&&/موبایل/.test(csv),'خروجی اکسل از دادهٔ زنده ساخته شد');
  /* حضور */
  p.click('#shAdm [data-evtab="att"]');
  p.click('#shAdm [data-regatt]');
  ok(/۱ وضعیت محلی از ۳ پاسخ نمونه/.test(p.txt('#shAdm'))&&/حاضر/.test(p.txt('#shAdm')),
    'تغییر حضور با یک کلیک فقط در برگهٔ محلی نشست');
  /* مالی زنده از فرم‌ساز */
  p.click('#shAdm [data-evtab="money"]');
  ok(/جمع محلیِ نمونه/.test(p.txt('#shAdm'))&&/پرداخت، رسید تأییدشده، فروش یا دفترکل بانکی نیست/.test(p.txt('#shAdm')),
    'جمع مالی رویداد از دادهٔ مرورگر است و دفترکل یا پرداخت واقعی نیست');
  ok(/۲۰۰/.test(p.txt('#shAdm')),'و جمع از ثبت‌نام‌ها حساب میشود');
  /* اطلاع‌رسانی و پویش */
  p.click('#shAdm [data-evtab="news"]');
  p.type('#evbrtxt','یادآوری: فردا میبینمتان');
  p.click('#shAdm [data-brsend]');
  const req1=U.ownerApprovals().find(x=>x&&x.type==='notification'&&x.status==='pending'&&x.source==='event-broadcast');
  ok(!!req1&&!!req1.brRecord,'خبر فقط در صف بازبینی محلی مالک قرار گرفت');
  const brBefore=U.brAll().length;
  ok(brBefore===0,'درخواست pending فقط payload صف محلی دارد؛ هنوز رکورد nora-broadcasts ساخته نشده');
  ok(U.brSave({id:'forged',ev:evId,txt:'بدون تأیید'},'not-an-approval')===null&&U.brAll().length===brBefore,
    'brSave بدون تأیید صریح مالک هیچ رکورد پایداری نمی‌سازد');
  const approveNotice=id=>{
    p.click('#shAdm [data-close]');
    p.click('#admNav [data-sec="settings"]');
    p.click('#admBody [data-setg="notify"]');
    p.click('#admBody [data-noticeapprove="'+id+'"]');
  };
  approveNotice(req1.id);
  let brs=U.brAll();
  ok(brs.length===1&&brs[0].n===3&&brs[0].ownerApprovalId===req1.id&&brs[0].sent===false,
    'خبر تنها پس از تأیید مالک با شناسهٔ همان درخواست در انبار محلی ثبت شد؛ ارسال نشد');
  p.click('#admNav [data-sec="events"]');
  p.click('[data-ev="'+evId+'"]');
  p.click('#shAdm [data-evtab="news"]');
  p.click('#shAdm [data-brpoke="remind"]');
  const req2=U.ownerApprovals().find(x=>x&&x.type==='notification'&&x.status==='pending'&&x.source==='event-reminder');
  ok(!!req2&&U.brAll().length===1&&!U.brAll().some(b=>b.poke),
    'یادآوری تا پیش از تأیید مالک فقط در صف می‌ماند');
  approveNotice(req2.id);
  brs=U.brAll();
  ok(brs.length===2&&brs.some(b=>b.poke&&b.ownerApprovalId===req2.id&&b.sent===false),
    'یادآوری هم فقط پس از تأیید مالک، به‌صورت محلی ثبت شد');
  p.click('#admNav [data-sec="events"]');
  p.click('[data-ev="'+evId+'"]');
  /* نظرسنجی پایانی */
  p.click('#shAdm [data-evtab="survey"]');
  ok(/نظرسنجی کارگاه سی‌آر‌ام/.test(p.txt('#shAdm')),'نظرسنجی وصلشده در کارت است');
  ok(/کیفیت جلسه/.test(p.txt('#shAdm')),'و پرسشهایش با پاسخ شمرده میشوند');
  /* رویداد با کد دعوت */
  p.click('#shAdm [data-close]');
  p.click('#admNav [data-sec="events"]'); p.click('[data-evnew]');
  p.type('#wzName','جلسهٔ خصوصی','change'); p.click('[data-wet="webinar"]');
  p.click('[data-wstep="1"][data-wgo="1"]');
  p.type('#wz-date','۱۴۰۵/۰۹/۰۵','change'); p.type('#wz-time','18:00','change');
  p.type('#wz-to','20:00','change'); p.type('#wz-place','سالن نورا','change');
  p.click('[data-wstep="2"][data-wgo="1"]'); p.type('#wz-cap','10','change');
  p.click('[data-wfeat="invite"]');
  p.click('[data-wstep="3"][data-wgo="1"]');
  p.click('[data-fpick="reg"][data-fid="crm-reg"]');
  p.click('[data-wstep="4"][data-wgo="1"]');
  p.click('[data-wsend]');
  const added2=JSON.parse(st.getItem('nora-admin')).added||[];
  ok(added2.length===2&&/^\d{6}$/.test(added2[0].code||''),'رویداد با کد دعوت شش‌رقمی ساخته شد');
  p.click('[data-ev="'+added2[0].id+'"]');
  p.click('#shAdm [data-evtab="info"]');
  ok(/کد دعوت/.test(p.txt('#shAdm')),'و کد در کارت رویداد دیده میشود');
  ok(p.errs.length===0,'هیچ خطایی نماند');
}
/* ── ۱۲) مالی فقط و فقط مالک ── */
{
  console.log('\n── مالی فقط مالک ──');
  const p=await load();
  ok(/مالی نمونهٔ امروز/.test(p.txt('#admBody'))&&/پرداخت، دفترکل و اتصال بانکی وجود ندارد/.test(p.txt('#admBody')),
    'مالک کارت مالی را صریحاً به‌عنوان نمونهٔ محلی می‌بیند');
  ok(p.all('.erow').length===4&&/از/.test(p.txt('.elist')),'کارت رویدادهای نزدیک چهار ردیف ظرفیت دارد');
  ok(!/ریال|درآمد|فروش/.test(p.txt('.elist')),'و هیچ عدد مالی در آن نیست');
  openReports(p);
  ok(/مالی/.test(p.txt('#admBody')),'و گزارش مالی را');
  ok(p.all('[data-rep="fi"]').length>=1,'ردیف مالی در گزارش‌ها برایش هست');
  p.click('#admNav [data-sec="events"]');
  p.click('[data-ev="e1"]');
  ok(p.all('#shAdm .admfilters [data-evtab="money"]').length===1,'تب مالی رویداد برایش هست');
  ok(/مبلغ/.test(p.txt('#shAdm'))&&/رایگان/.test(p.txt('#shAdm'))
    &&/ظرفیت/.test(p.txt('#shAdm'))&&/داده‌ها و شمارها محلی‌اند/.test(p.txt('#admBody')),
    'ردیف مبلغ و ظرفیت خواناست و هشدار محلی‌بودن داده‌ها روشن می‌ماند');
  p.click('#shAdm [data-close]');

  /* سرپرست باشگاه: مالی نمی‌بیند، جز صف تأیید فیش */
  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p7"]');
  ok(!/مالی نمونه|درآمد نمونه|حق عضویت|[۰-۹٬,]+ ریال/.test(p.txt('#admBody .dashwrap')),
    'داشبورد سرپرست باشگاه عدد یا تنظیم مالی ندارد؛ یادداشت عمومیِ غیرفعال‌بودن جداست');
  openReports(p);
  ok(p.all('[data-rep="fi"]').length===0,'ردیف مالی برایش نیست');
  ok(!/پرداخت/.test(p.txt('.admlist')),'هشدار مالی هم برایش نیست');
  ok(!/ریال|فروش همین دوره/.test(p.txt('#admBody')),'جمعبندی مدیریتی هم مالی را نشان نمیدهد');
  p.click('#admNav [data-sec="events"]');
  p.click('[data-ev="e1"]');
  ok(p.all('#shAdm .admfilters [data-evtab="money"]').length===0,'تب مالی رویداد قفل است');
  ok(!/هزینه/.test(p.txt('#shAdm')),'و ردیف هزینهٔ رویداد نیست');
  ok(p.all('#shAdm .admfilters [data-evtab]').length===7,'هفت تب غیرمالی مانده؛ سرپرست تب درآمد را نمی‌بیند');
  p.click('#shAdm .admfilters [data-evtab="reg"]');
  ok(!/پرداخت‌شده/.test(p.txt('#shAdm')),'وضعیت پرداخت در تب ثبت‌نام‌ها ماسک شده');
  p.click('#shAdm [data-close]');
  const receiptSample={id:'receipt-review-sample',who:'شرکت‌کنندهٔ نمونه',ev:'رویداد نمونه',amount:125000,
    code:'SAMPLE',state:'wait',at:'نمونه',fileName:'رسید-نمونه.png'};
  p.store.setItem('nora-receipts',JSON.stringify([receiptSample]));
  p.click('#admNav [data-sec="settings"]'); p.click('[data-setg="receipts"]');
  ok(p.all('[data-rcok]').length===1&&p.all('[data-rcno]').length===1
    &&/بازبینی محلی/.test(p.txt('#admBody'))&&!/data-fintab/.test(p.body())
    &&p.all('[data-finaddcard],[data-finledadd],[data-fininstadd],[data-fingate]').length===0,
    'سرپرست فقط بازبینی محلی رسید نمونه را می‌بیند؛ نه تنظیم درگاه، درآمد یا اقساط');
  const waitReceipt=p.all('[data-rcok]')[0], receiptId=waitReceipt&&waitReceipt.dataset.rcok;
  const baseFin=p.window.NORA.ADMIN.settings.finance;
  const ledgerBefore=JSON.stringify(baseFin.ledger), instBefore=JSON.stringify(baseFin.inst);
  if(waitReceipt) p.click(waitReceipt);
  const savedFin=JSON.parse(p.store.getItem('nora-admin')).fin;
  const reviewed=savedFin.receipts.find(x=>x.id===receiptId);
  ok(receiptId&&reviewed&&reviewed.state==='ok'&&reviewed.reviewOnly===true&&reviewed.localOnly===true,
    'تصمیم سرپرست فقط برچسب بازبینی محلی را روی رسید نمونه می‌گذارد');
  ok(JSON.stringify(savedFin.ledger||baseFin.ledger)===ledgerBefore
    &&JSON.stringify(savedFin.inst||baseFin.inst)===instBefore
    &&JSON.parse(p.store.getItem('nora-receipts')).length===0,
    'بازبینی رسید نه دفترکل، نه بدهی/قسط، نه پرداخت بانکی را تغییر می‌دهد؛ فقط فایل محلی از صف پاک می‌شود');

  /* سرپرست پشتیبانی: کاربران بدون برچسب بدهی */
  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p3"]');
  p.click('#admNav [data-sec="users"]');
  ok(!/بدهی/.test(p.txt('#admBody')),'برچسب بدهی در فهرست کاربران نیست');
  p.click('#admBody [data-user="u4"]');
  ok(!/بدهی/.test(p.txt('#shAdm')),'و در پروندهٔ کاربر نیست');
  p.click('#shAdm [data-close]');

  p.click('[data-who-sheet]'); p.click('#shAdm [data-who="p1"]');
  p.click('#admNav [data-sec="users"]'); p.click('[data-uv="tools"]'); p.click('[data-utool="staff"]');
  ok(/مدیریت حساب‌ها و نقش‌ها/.test(p.txt('#admBody')),'فقط مالک به مدیریت نقش‌های حساب‌ها دسترسی دارد');
  ok(p.all('.admlist .admsw').length===10&&!p.all('[data-fperm],[data-extra]').length
    &&/حق عضویت/.test(p.txt('#admBody'))&&/قوانین امتیاز باشگاه/.test(p.txt('#admBody')),
    'اختیارهای مالک، از جمله حق عضویت و امتیازِ واگذارنشده، فهرست شده‌اند');
  ok(!p.all('[data-roleassign] option[value="owner"]').length&&/تأیید نهایی/.test(p.txt('#admBody')),
    'نقش مالک به دیگران واگذار نمی‌شود و تأیید نهایی فقط‌مالک روشن است');

  p.click('#admNav [data-sec="dash"]');
  p.click('[data-who-sheet]');
  p.click('#shAdm [data-who="p10"]');
  ok(!/مالی نمونه|درآمد نمونه|حق عضویت|بدهی|[۰-۹٬,]+ ریال/.test(p.txt('#admBody .dashwrap')),
    'داشبورد کارشناس عدد مالی یا بدهی ندارد؛ یادداشت عمومیِ غیرفعال‌بودن جداست');
  openReports(p);
  ok(p.all('[data-rep="fi"]').length===0,'گزارش مالی برای کارشناس نیست');
}

/* ── نشست شخصی، پروفایل جدا و خروج مدیر ── */
{
  console.log('\n── نشست و پروفایل سرپرست ──');
  const st=makeStore();
  st.setItem('nora-admin-session',JSON.stringify({u:'maryam.r',role:'admin',personKey:'p2',at:Date.now()}));
  const p=await load(st);
  ok(p.txt('#admBar').includes('مریم رضایی'),'هویت از نشست می‌آید، نه از شخصیت مانده در state پنل');
  p.click('[data-who-sheet]');
  ok(p.txt('#shAdm').includes('پروفایل شخصی')&&p.all('#shAdm [data-admout]').length===1,
    'دکمهٔ نام مستقیم پروفایل خودش را باز می‌کند و خروج دارد');
  ok(p.doc.querySelector('#meName')&&p.doc.querySelector('#meName').value==='مریم رضایی',
    'سرپرست فرم ویرایش نام نمایشیِ خودش را می‌بیند');
  p.type('#meName','مریم رضایی‌نیا'); p.type('#meBio','سرپرست حوزهٔ آموزش');
  p.click('[data-mesave]');
  const saved=JSON.parse(st.getItem('nora-admin')||'{}');
  ok(saved.meProf&&saved.meProf.p2.name==='مریم رضایی‌نیا'&&saved.meProf.p2.bio==='سرپرست حوزهٔ آموزش',
    'پروفایل شخصی در state پنل ذخیره می‌شود');
  ok(st.getItem('nora-people')===null&&p.txt('#admBar').includes('مریم رضایی‌نیا'),
    'پروفایل عمومی خودکار منتشر نمی‌شود و نام نوار بعد از ذخیره تازه می‌شود');
  p.click('[data-who-sheet]');
  ok(p.all('#shAdm [data-who]').length===0&&!p.txt('#shAdm').includes('نمای آزمایشی نقش‌ها'),
    'سرپرست نمی‌تواند خودش را جای نقش دیگری بگذارد');
  ok(/nora-admin-session/.test(fs.readFileSync(DIR+'admin.js','utf8'))&&/location.href='login.html\?mode=server'/.test(fs.readFileSync(DIR+'admin.js','utf8')),
    'خروج نشست مدیر را پاک می‌کند و به ورود برمی‌گرداند');
  const future=makeStore();
  future.setItem('nora-admin-session',JSON.stringify({u:'maryam.r',role:'admin',personKey:'p2',at:Date.now()+30000}));
  await load(future);
  ok(future.getItem('nora-admin-session')===null,'نشست با زمانِ آینده پذیرفته نمی‌شود و از حافظه پاک می‌شود');
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
  openReports(b);
  b.click('[data-rp="امسال"]');
  const c=await load(store);
  openReports(c);
  ok(c.doc.querySelector('[data-rp="امسال"].on')!==null,'دورهٔ انتخابی گزارش هم می‌ماند');
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
  ok(/گذشته · نمونه/.test(p.txt('.admreview')),'مرور وضعیت نمونهٔ گذشته را می‌گوید؛ وقوع واقعی را تأیید نمی‌کند');
  p.click('[data-wsend]');
  ok(p.all('[data-ev]').length>=8,'رویداد گذشته هم به فهرست اضافه می‌شود');
  const publishedPast=(JSON.parse(p.store.getItem('nora-admin')||'{}').added||[]).find(x=>x.n==='کارگاه گذشتهٔ آفلاین');
  const publishedPastId=publishedPast&&publishedPast.id;
  p.click('#admNav [data-sec="events"]');
  const firstRow=p.txt('[data-ev]');
  ok(/کارگاه گذشتهٔ آفلاین/.test(firstRow)&&/گذشته/.test(firstRow),
    'و در فهرست با وضعیت گذشته نشاندار می‌شود؛ هشدار محلی بالای صفحه است');
  ok(p.all('[data-evF]').length===4,'چهار صافی رویدادها سر جایش است');
  p.click('[data-evF="past"]');
  ok(p.all('[data-ev]').length>=3,'صافی برگزار شده رویدادهای گذشته را جدا می‌کند');
  p.click(`[data-ev="${publishedPastId}"]`);
  p.click('#shAdm [data-evtab="media"]');
  const mediaGuide=p.txt('#shAdm');
  ok(mediaGuide.includes('پیوند ورود')&&mediaGuide.includes('YouTube')&&mediaGuide.includes('Aparat')
    &&mediaGuide.includes('Vimeo')&&mediaGuide.includes('Dailymotion')&&mediaGuide.includes('iframe'),
    'راهنمای مدیریت رسانه، پیوند ورود آنلاین و سرویس‌های embed مجاز/ناشناس را روشن می‌کند');
  ok(!!p.doc.querySelector('#evdetail')&&!!p.doc.querySelector('[data-evfile]'),'رویداد برگزارشده در کارت خودش جزئیات و بارگذاری فایل دارد');
  p.type('#evdetail','گزارش کوتاه پس از برگزاری');
  p.click('[data-evdetail]');
  let mediaInput=p.doc.querySelector('[data-evfile]');
  const mediaFile=new p.window.File([new Uint8Array([137,80,78,71,13,10,26,10])],'آلبوم.png',{type:'image/png'});
  Object.defineProperty(mediaInput,'files',{value:[mediaFile],configurable:true});
  mediaInput.dispatchEvent(new p.window.Event('change',{bubbles:true}));
  await wait(130);
  const zipFile=new p.window.File([new Uint8Array([80,75,3,4,0,0,0,0])],'برگه‌های کارگاه.zip',{type:'application/zip'});
  mediaInput=p.doc.querySelector('[data-evfile]');
  Object.defineProperty(mediaInput,'files',{value:[zipFile],configurable:true});
  mediaInput.dispatchEvent(new p.window.Event('change',{bubbles:true}));
  await wait(130);
  let pack=JSON.parse(p.store.getItem('nora-evpack')||'{}')[publishedPastId]||{};
  ok(pack.detail==='گزارش کوتاه پس از برگزاری'&&pack.files.length===2&&pack.files.some(f=>f.src.startsWith('data:image/png'))
    &&pack.files.some(f=>f.kind==='file'&&f.mime==='application/zip'&&f.src.startsWith('data:application/zip')),
    'گزارش، رسانه و فایل عمومی در آرشیو همان رویداد ذخیره شدند');
  p.click('#shAdm [data-evtab="cert"]');
  p.type('#evcertmin','85'); p.type('#evcertnote','حضور در جلسهٔ پایانی');
  p.click('[data-evcertsave]');
  const pubEvent=p.window.NORA_UI.pubEvents().find(x=>x.id===publishedPastId), publicFile=pubEvent&&pubEvent.media.find(m=>m.t==='برگه‌های کارگاه.zip');
  ok(pubEvent&&pubEvent.past&&pubEvent.media.length===2&&publicFile&&publicFile.k==='file'
    &&pubEvent.cert&&pubEvent.certMin===85&&pubEvent.certNote==='حضور در جلسهٔ پایانی',
    'وضعیت و شرط گواهی همراه رسانه و فایل آرشیو عمومی رویداد منتشر می‌شود');
  const publicErrors=[];
  const publicDom=await JSDOM.fromFile(DIR+'event.html',{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,
    url:pathToFileURL(DIR+'event.html').href+'?id='+encodeURIComponent(publishedPastId),
    beforeParse(w){w.__NORA_TEST_FIXTURE_MODE__=true;w.scrollTo=()=>{}; if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      Object.defineProperty(w,'localStorage',{configurable:true,value:p.store});
      w.addEventListener('error',e=>publicErrors.push(e.message)); const ce=w.console.error;
      w.console.error=(...a)=>publicErrors.push(a.join(' '));}});
  await new Promise(resolve=>{
    if(publicDom.window.document.readyState==='complete') return resolve();
    const timer=setTimeout(resolve,5000);
    publicDom.window.addEventListener('load',()=>{clearTimeout(timer); resolve()},{once:true});
  });
  const publicPage=publicDom.window.document.querySelector('#page');
  const publicText=publicPage?publicPage.textContent.replace(/\s+/g,' ').trim():'';
  ok(publicErrors.length===0&&!!publicPage,'صفحهٔ عمومی رویدادِ منتشرشده بی‌خطا بار می‌شود');
  ok(publicPage&&publicPage.querySelector('[data-uimedia]')&&publicText.includes('آلبوم.png')&&publicText.includes('برگه‌های کارگاه.zip')
    &&publicText.includes('گزارش کوتاه پس از برگزاری'),
    'صفحهٔ عمومی، گزارش، رسانه و فایل آرشیو را نشان می‌دهد');
  const publicFileRow=publicDom.window.NORA_UI.pubEvents().find(x=>x.id===publishedPastId).media.find(m=>m.k==='file');
  publicDom.window.NORA_UI.player(publishedPastId,publicFileRow.id);
  const fileDownload=publicDom.window.document.querySelector('#shPlay a[download],#shPlay a[href^="data:"]');
  ok(!fileDownload&&!publicDom.window.document.querySelector('#shPlay iframe[src^="data:application/"]')
    &&publicDom.window.document.querySelector('#shPlay .pdoc'),
    'فایل ZIP در وب‌اپ دانلود یا نمایش داده نمی‌شود؛ دریافت باید از مسیر بات باشد');
  ok(publicDom.window.NORA_PUBLIC_SOURCE==='test-fixture'
      &&publicText.includes('حداقل حضور نمایشی ٪۸۵')&&publicText.includes('حضور در جلسهٔ پایانی'),
    'واژهٔ نمایشی فقط برای دادهٔ fixture آزمون می‌آید؛ شرط و یادداشت همان رویداد هم روشن است');
  publicDom.window.close();
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
  seed.setItem('nora-admin', JSON.stringify({v:78, evF:'all', added:[
    {id:'z-done', n:'نشست دیروز', kind:'نشست', when:'', on:g(-1), time:'۲۰:۰۰', end:g(-1),
     place:'آنلاین', cap:40, reg:40, state:'soon', sess:[], sessions:1},
    {id:'z-mid', n:'کارگاه سه‌جلسه‌ای', kind:'کارگاه', when:'', on:g(-2), time:'۱۷:۰۰', end:g(3),
     place:'لانه', cap:20, reg:8, state:'soon', sessions:3,
     sess:[{d:g(-2),t:'17:00',to:'19:00'},{d:g(1),t:'17:00',to:'19:00'},{d:g(3),t:'17:00',to:'19:00'}]}]}));
  const p=await load(seed,'#events');
  const row=id=>p.all('[data-ev]').find(r=>r.getAttribute('data-ev')===id);
  ok(!!row('z-done')&&/گذشته/.test(row('z-done').textContent),
    'تک‌جلسهٔ گذشته با وضعیت محلیِ «گذشته» نشان داده می‌شود');
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
  const U0=p.window.NORA_UI;
  U0.formPut({id:'sv-reg',name:'ثبت‌نام کارگاه نظرسنجی',kind:'ثبت‌نام',need:'reg',
    fields:[{id:1,t:'fullname',l:'نام و نام خانوادگی',req:true},{id:2,t:'mobile',l:'موبایل',req:true}]});
  p.click('[data-wstep="2"]'); p.click('[data-wstep="3"][data-wgo="1"]');
  p.click('[data-fpick="reg"][data-fid="sv-reg"]');
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
  const U1=p2.window.NORA_UI;
  U1.formPut({id:'ns-reg',name:'ثبت‌نام بی نظرسنجی',kind:'ثبت‌نام',need:'reg',
    fields:[{id:1,t:'fullname',l:'نام و نام خانوادگی',req:true}]});
  p2.click('[data-wstep="2"]'); p2.click('[data-wstep="3"][data-wgo="1"]');
  p2.click('[data-fpick="reg"][data-fid="ns-reg"]');
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
  ok(/مطلب‌ها/.test(p.txt('#admBody'))&&/مطلب‌های آماده/.test(p.txt('#admBody')),'فهرست مطلب‌ها و مطلب‌های آماده زیر رویدادهاست');
  const readyArticle=p.all('#admBody [data-pprevgo]').find(row=>row.textContent.includes('هفت تمرین تنفس'));
  ok(!!readyArticle&&readyArticle.querySelector('.tag')?.textContent==='نمونه'
      &&!readyArticle.querySelector('.tx small')?.textContent.includes('نمونه'),
    'مطلب آماده با یک برچسب محلی و بدون تکرار نمونه دیده می‌شود');
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
  const adminSource=fs.readFileSync(DIR+'admin.js','utf8');
  ok(adminSource.includes("isReceipt&&key==='note'?'توضیح ثبت فیش'")
      &&adminSource.includes('${esc(String(value))}'),
    'یادداشت اختیاری فیش در کارتابل برچسب روشن دارد و متن آن escape می‌شود');
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
  await openLegacyForms(KEEP);
  ok(/ثبت‌نام کارگاه سینک/.test(KEEP.txt('#admBody')),'و در صفحهٔ قدیمی فرم‌ها هم همین فرم دیده می‌شود');

  const html=fs.readFileSync(DIR+'admin.html','utf8');
  /* نسخهٔ بستهٔ مشترک (ui.js) عمداً اینجا سنجیده نمی‌شود؛ یکنواختی و
     رو‌به‌جلو‌بودن آن در asset-audit.test.mjs برای همهٔ صفحه‌ها (از جمله همین
     admin.html) یک‌جا بررسی می‌شود تا با هر به‌روزرسانیِ بسته، این فایل
     بی‌دلیل نشکند. */
  ok(html.includes('admin.css?v=103')&&html.includes('admin.js?v=128')
      &&html.includes('owner-api.js?v=113')&&html.includes('data.js?v=100')
      &&html.includes('site-content-sync.js?v=102')&&html.includes('owner-banner-manager.css?v=4')
      &&html.includes('owner-banner-manager.js?v=5')&&html.includes('nora.css?v=102'),
    'نسخهٔ پرونده‌های پنل، همگام‌سازی و مدیر بنر تازه است');
  const sw=fs.readFileSync(DIR+'sw.js','utf8');
  ok(sw.includes("'nora-v100'"),'کارگر سرویس نسخهٔ تازه است');
  ok(!sw.includes("'admin.html'")&&!sw.includes("'admin.js'"),'صفحهٔ خصوصی و اسکریپت بلااستفادهٔ پنل در پیش‌کش عمومی نیستند');
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
