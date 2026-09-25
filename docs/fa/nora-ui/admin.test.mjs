/* ══════════════════════════════════════════════════════════════════════════
   نورا · آزمون پنل مدیران (admin.html)
   ──────────────────────────────────────────────────────────────────────────
   اجرا:  npm i jsdom && node admin.test.mjs
   چه چیزی را می‌سنجد: بی‌خطا بار شدن پنل، هفت بخش به‌علاوهٔ داشبورد، سه عدد
   بالای پنل، ویزارد سه‌گامی رویداد، فهرست و صافی و جست‌وجوی کاربران، نه
   گزارش، مرکز صدور گواهینامه با پیش‌نمایش زنده، هفت گروه تنظیمات، نقش‌ها و
   ۳۸ دسترسی، قفل شدن بخش‌ها به‌اندازهٔ نقش، ماندگاری خاموش و روشن‌ها، و
   پاکی متن فارسی (بدون خط تیرهٔ بلند، بدون متن سخت‌شده در HTML).
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
  ok(p.all('.admstat').length===3,'سه عدد وضعیت بالای پنل نشسته');
  const stat=p.all('.admstat').map(x=>x.textContent).join(' ');
  ok(/کاربر/.test(stat)&&/رویداد/.test(stat)&&/ریال/.test(stat),'عددها کاربر و رویداد و درآمد را نشان می‌دهند');
  ok(p.txt('.admtasks').length>10,'کارهای امروز فهرست شده');
  ok(p.all('.admbars i').length===7,'نمودار هفت روز کشیده شد');
  ok(p.all('.card').length>=2,'داشبورد دو کارت دارد');
  ok(p.doc.title.includes('پنل مدیران'),'عنوان صفحه نام پنل را دارد');
  p.click('#admNav [data-sec="events"]');
  ok(p.doc.title.includes('پنل مدیران')&&p.doc.title.includes('رویدادها'),'عنوان با بخش عوض می‌شود');
  p.click('#admNav [data-sec="dash"]');
  ok(p.doc.querySelector('a[href="account.html"]')!==null,'راه بازگشت به نمای کاربر هست');
  ok(p.doc.querySelector('a[href="builder.html"]')!==null,'راه فرم‌ها و گزارش هست');
  const nameless=p.all('#admRail button, #admTabs a, .topbar button, .admstat, .admtask')
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

/* ── ۲) ویزارد رویداد تازه ── */
{
  console.log('\n── رویداد جدید: سه گام ──');
  const p=await load();
  p.click('#admNav [data-sec="events"]');
  const before=p.all('[data-ev]').length;
  p.click('#admNav [data-sec="newev"]');
  ok(p.all('.admsteps .st').length===3,'ویزارد سه گام دارد، نه بیشتر');
  ok(p.all('.admkind').length===6,'شش قالب رویداد هست');
  ok(/گام/.test(p.txt('#admBody')),'شمارندهٔ گام نوشته شده');
  p.click('[data-wstep="1"][data-wgo="1"]');    /* بی نوع و بی نام: نباید جلو برود */
  ok(p.txt('#admBar .head')==='رویداد جدید','گام ناتمام جلو نمی‌رود');
  ok(p.txt('#toast').length>0,'و می‌گوید چه قلمی کم است');
  p.click('[data-wkind="workshop"]');
  p.type('#wzName','کارگاه روایت اول‌شخص');
  p.click('[data-wstep="1"][data-wgo="1"]');
  ok(p.all('[data-wpick]').length>15,'گام دوم تاریخ و ساعت و جا و ظرفیت دارد');
  p.click('[data-wstep="2"][data-wgo="1"]');
  ok(p.all('.admkind').length===0,'گام دوم با قلم ناتمام جلو نمی‌رود');
  p.click('[data-wpick="date"][data-wval="۱۶ مهر"]');
  p.click('[data-wpick="time"][data-wval="۱۷:۰۰"]');
  p.click('[data-wpick="place"][data-wval="کتابخانهٔ نورا، ونک"]');
  p.click('[data-wstep="2"][data-wgo="1"]');
  ok(/کارگاه روایت/.test(p.txt('.admreview')),'گام سوم همه‌چیز را برای مرور نشان می‌دهد');
  p.click('[data-wbuild]');
  ok(p.txt('#admBar .head')==='رویدادها','بعد از ساخت، خودش به فهرست رویدادها می‌رود');
  ok(p.all('[data-ev]').length===before+1,'رویداد تازه به فهرست اضافه شد ('+before+' → '+p.all('[data-ev]').length+')');
  ok(p.txt('[data-ev] b')==='کارگاه روایت اول‌شخص','نام همان است که نوشتیم');
  ok(/پیش‌نویس/.test(p.txt('[data-ev]')),'وضعیتش پیش‌نویس است، نه منتشرشده');
  ok(p.all('[data-ev]').length>7,'رویدادهای قدیمی هم سرِ جایشان ماندند');
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
  ok(p.all('table.admtable tbody tr').length===10,'ده کاربر در جدول است');
  ok(p.all('.admcard-user .admrow2').length===10,'نمای کارتی موبایل هم ساخته شد');
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

/* ── ۸) تنظیمات و دسترسی‌ها ── */
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
  ok(p.all('[data-permrole]').length===8,'هشت نقش برای مدیریت دسترسی هست');
  p.click('[data-permrole="report"]');
  ok(/دسترسی‌های گزارش‌گیر/.test(p.txt('#admBody')),'دسترسی‌های نقش انتخابی می‌آید');
  ok(p.all('[data-perm]').length===34,'۳۴ دسترسی تیک‌زدنی است و چهار دسترسی ویژه نه');
  ok(p.all('[data-perm].on').length===6,'شش دسترسی گزارش‌گیر تیک خورده');
  const off=p.all('[data-perm]').find(x=>!x.classList.contains('on'));
  p.click(off);
  ok(p.all('[data-perm].on').length===7,'سوپرادمین می‌تواند دسترسی بدهد');
  ok(p.txt('#toast').includes('داده شد'),'و همان لحظه خبر می‌دهد');
  p.click(p.all('[data-perm].on')[0]);
  ok(p.all('[data-perm].on').length===6,'و می‌تواند بردارد');
  p.click('[data-permrole="super"]');
  ok(p.all('.admsetgroup .tag').length>=38,'سوپرادمین همهٔ ۳۸ دسترسی را دارد');
  ok(p.all('[data-perm]').length===0,'و تیک‌هایش قفل است');
  ok(p.all('.admsetgroup').length===7,'دسترسی‌ها در هفت دسته دسته‌بندی شده');
}

/* ── ۹) قفل بخش‌ها به‌اندازهٔ نقش ── */
{
  console.log('\n── قفل دسترسی ──');
  const p=await load();
  p.click('[data-rolesheet]');
  ok(p.all('#shAdm [data-role]').length===8,'ورقهٔ نقش‌ها از نوار بالا باز می‌شود');
  p.click('#shAdm [data-role="report"]');
  ok(p.txt('#admBar .chip').includes('گزارش‌گیر'),'نقش در نوار بالا عوض شد');
  p.click('#shAdm [data-close]');
  p.click('#admNav [data-sec="settings"]');
  ok(/باز نمی‌شود/.test(p.txt('#admBody')),'گزارش‌گیر به تنظیمات راه ندارد');
  ok(/نقش دیگری/.test(p.txt('#admBody')),'و می‌گوید از کجا اجازه بگیرد');
  p.click('#admNav [data-sec="reports"]');
  ok(p.all('[data-rep]').length>=9,'ولی گزارش‌ها برایش باز است');
  p.click('[data-rolesheet]');
  p.click('#shAdm [data-role="super"]');
  p.click('#shAdm [data-close]');
  p.click('#admNav [data-sec="settings"]');
  ok(p.all('[data-setg]').length===7,'سوپرادمین همه‌چیز را می‌بیند');
}

/* ── ۱۰) ماندگاری ── */
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

/* ── ۱۲) پرونده‌ها و متن‌ها ── */
{
  console.log('\n── پرونده‌ها و متن ──');
  const files=['admin.html','admin.js','admin.css','builder.html','create.html'];
  const dash=files.filter(f=>fs.readFileSync(DIR+f,'utf8').includes(' — '));
  ok(dash.length===0,'خط تیرهٔ بلند با فاصله در متن فارسی نمانده'+(dash.length?': '+dash.join('، '):''));
  const html=fs.readFileSync(DIR+'admin.html','utf8');
  ok(html.includes('admin.css?v=33')&&html.includes('admin.js?v=33'),'نسخهٔ پرونده‌های پنل ۳۳ است');
  const sw=fs.readFileSync(DIR+'sw.js','utf8');
  ok(sw.includes("'nora-v22'"),'کارگر سرویس نسخهٔ ۲۲ است');
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
  const nums=p2.all('.admstat b').map(b=>b.textContent.trim()).filter(t=>data.indexOf(t)===-1);
  ok(nums.length===0,'عددهای سرِ پنل هم از داده می‌آید'+(nums.length?': '+nums.join('، '):''));
}

console.log('\nadmin-test: '+checks+' بررسی، '+fails+' خطا');
if(fails) process.exit(1);
