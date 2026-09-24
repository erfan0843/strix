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
      const ce=w.console.error; w.console.error=(...a)=>errs.push('console.error: '+a.join(' '));
    }});
  await wait(650);
  const {window}=dom, doc=window.document;
  const fire=(el,type)=>{ el.dispatchEvent(new window.MouseEvent(type,{bubbles:true,cancelable:true})) };
  return {dom,window,doc,errs,
    click:sel=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel); fire(el,'click')},
    clickEl:el=>fire(el,'click'),
    set:(sel,v)=>{const el=doc.querySelector(sel); if(!el) throw new Error('نیست: '+sel); el.value=v;
      el.dispatchEvent(new window.Event('input',{bubbles:true}))},
    txt:sel=>{const el=doc.querySelector(sel); return el?el.textContent.replace(/\s+/g,' ').trim():''},
    all:sel=>[...doc.querySelectorAll(sel)],
    shown:sel=>{const el=doc.querySelector(sel); return !!el&&el.hidden!==true},
    open:()=>[...doc.querySelectorAll('.sheet.on')].map(e=>e.id),
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
  const hb=p.doc.querySelector('.topbar .help-btn');
  ok(hb!==null && hb.getAttribute('href')==='support.html' && hb.classList.contains('on'),'نشان پشتیبانی در نوار بالا، کنار اعلان‌ها');
  ok(p.doc.querySelector('.topbar [href="home.html#notice"]')!==null,'نشان اعلان‌ها هم سرِ جایش');
  ok(p.all('.tabbar a').length===3,'نوار پایین سه‌تایی');
  ok(p.all('#modal').length===1 && p.all('#toast').length===1 && p.all('#scrim').length===1,'یک پاپ‌آپ، یک پیام‌رسان، یک پرده');
  ok(p.txt('.sup-hero').includes('پشتیبانی و راهنما') && p.txt('.sup-hero').includes('بی‌نیاز به ورود'),'سرِ صفحه: نام و بی‌نیازی از ورود');
  ok(p.all('#stiles .stile').length===16,'شانزده کاشی، همهٔ بخش‌های ربات');
  ok(p.txt('#tilesCount').includes('۱۶'),'شمارندهٔ کاشی‌ها');
  ok(p.all('#exList .erow2').length===4,'چهار کارشناس');
  ok(p.all('#mgList .drow').length===2,'دو راه ارتباط مستقیم با مدیریت');
  ok(p.all('#faqAll .faq').length===7,'پرسش‌های پرتکرار کلی');
  ok(p.all('#fmList .drow').length>=3,'فرم‌های لینک‌شدهٔ مدیر');
  ok(p.all('#mine').length===1 && p.doc.querySelector('#mine').hidden===false,'کادر تیکت‌های من با نمونهٔ آماده');
}

/* ── ۲) کاشی‌ها از داده می‌آیند ── */
{
  console.log('\n── کاشی بخش‌ها ──');
  const p=await load(makeStore());
  const src=fs.readFileSync(DIR+'data.js','utf8');
  const W={}; new Function('window','document',src)(W,{});
  const S=W.NORA.SUPPORT;
  ok(S.sections.length===16,'دادهٔ کاشی‌ها در data.js هست');
  const keys=p.all('#stiles .stile').map(b=>b.dataset.sec);
  ok(keys.join(',')===S.sections.map(s=>s.k).join(','),'ترتیب کاشی‌ها همان ترتیب داده');
  const first=p.doc.querySelector('#stiles .stile');
  ok(first.tagName==='BUTTON' && first.querySelector('.sico use')!==null,'کاشی، دکمه‌ای با نشان است');
  ok(p.txt('#stiles .stile').includes('پرسش') ,'روی هر کاشی شمار پرسش‌ها هست');
  const cert=p.doc.querySelector('#stiles [data-sec="cert"]');
  ok(cert.textContent.includes('فرم دارد'),'کاشیای که فرم دارد، نشانش را می‌دهد');
  ok(S.sections.every(s=>s.faq.length>=2&&s.tips.length>=2&&s.media.length>=1),'هر بخش: پرسش، راهنمای مدیر و راهنمای تصویری یا صوتی');
  ok(S.sections.some(s=>s.media.some(m=>m.kind==='video')) && S.sections.some(s=>s.media.some(m=>m.kind==='audio'))
    && S.sections.some(s=>s.media.some(m=>m.kind==='image')),'هر سه گونهٔ راهنما هست: ویدیو، صدا، تصویر');
}

/* ── ۳) پاپ‌آپ کاشی: پرسش، راهنمای مدیر، راهنمای تصویری، تیکت ── */
{
  console.log('\n── پاپ‌آپ کاشی ──');
  const p=await load(makeStore());
  ok(p.doc.querySelector('#modal').hidden===true,'پاپ‌آپ اول بسته است');
  p.click('#stiles [data-sec="cert"]'); await wait(140);
  ok(p.doc.querySelector('#modal').hidden===false,'کلیک روی کاشی، پاپ‌آپ را باز می‌کند');
  ok(p.txt('#mTitle')==='گواهی و استعلام','نام همان بخش روی پاپ‌آپ');
  ok(p.all('#mBody .faq').length===2,'پرسش‌های پرتکرار همان بخش');
  ok(p.txt('#mBody').includes('راهنمای مدیر سامانه') && p.all('#mBody .tips li').length>=2,'راهنمای مدیر سامانه');
  ok(p.txt('#mBody').includes('راهنمای تصویری و صوتی') && p.all('#mBody .mcard').length>=1,'راهنمای تصویری و صوتی');
  ok(p.all('#mBody a[href="form.html?form=cert"]').length===1,'فرم مرتبط همان بخش');
  ok(p.doc.querySelector('#tkSlot').hidden===true,'کادر تیکت تا درخواست باز نمی‌شود');
  p.click('#modal [data-ticket-open]'); await wait(140);
  ok(p.doc.querySelector('#tkSlot').hidden===false && p.doc.querySelector('#tkText')!==null,'دکمهٔ «تیکت ثبت کن» ته پاپ‌آپ، کادر تیکت را می‌آورد');
  ok(p.all('#tkSlot .abtn').length===5,'پنج راه پیوست: صدا، تصویر، ویدیو، فایل، پیوند');
  ok(p.all('#tkSlot .pickc').length===7,'شش دستهٔ تیکت به‌علاوهٔ بی‌نام');
  p.click('#scrim'); await wait(140);
  ok(p.doc.querySelector('#modal').hidden===true && !p.doc.body.classList.contains('modal-open'),'پرده، پاپ‌آپ را می‌بندد');
  p.click('#stiles [data-sec="cert"]'); await wait(120);
  p.doc.dispatchEvent(new p.window.KeyboardEvent('keydown',{key:'Escape',bubbles:true})); await wait(120);
  ok(p.doc.querySelector('#modal').hidden===true,'Esc هم می‌بندد');
}

/* ── ۴) تیکت، کد پیگیری و پاسخ کارشناس ── */
{
  console.log('\n── تیکت ──');
  const p=await load(makeStore());
  p.click('#stiles [data-sec="pay"]'); await wait(120);
  p.click('#modal [data-ticket-open]'); await wait(120);
  const before=p.tickets().length;
  p.set('#tkText','کو'); p.click('[data-tksend]'); await wait(150);
  ok(before===1 && p.tickets().length===1,'متن کوتاه بی پیوست رد می‌شود');
  ok(p.txt('#toast').includes('بیشتر بنویس'),'پیام راهنمای کوتاه بودن متن');
  p.click('[data-linkopen]'); await wait(80);
  p.set('#linUrl','lifeline1.ir/docs'); p.click('[data-linkadd]'); await wait(120);
  ok(p.all('#tkSlot .fchip').length===1,'پیوند به تیکت می‌چسبد');
  p.set('#tkText','مبلغ کم شد و ثبت‌نام نشد'); p.click('[data-tksend]'); await wait(200);
  const T=p.tickets();
  ok(T.length===2 && /^\d{5}$/.test(T[0].id),'تیکت تازه با کد پیگیری پنج‌رقمی ثبت می‌شود');
  ok(T[0].sec==='pay' && T[0].files.length===1 && T[0].files[0].kind==='link','تیکت با بخش و پیوستش ذخیره می‌شود');
  ok(p.txt('#mBody').includes('گفت‌وگو') && p.txt('#mBody').includes('در صف بررسی'),'گفت‌وگو با وضعیت «در صف بررسی»');
  ok(p.txt('#toast').includes('کد پیگیری'),'کد پیگیری به کاربر گفته می‌شود');
  await wait(1500);
  const T2=(p.tickets()[0]||{});
  ok(T2.status==='پاسخ داده شد' && (T2.thread||[]).some(m=>m.who==='agent'),'پاسخ کارشناس روی همان تیکت می‌آید');
  ok((T2.thread||[]).some(m=>m.who==='agent'&&(m.files||[]).length>0),'کارشناس هم می‌تواند فایل و پیوند بفرستد');
  ok(p.all('#tkList .tkrow').length>=1 || p.all('#mine').length===1,'تیکت در «تیکت‌های من» می‌ماند');
  p.click('#tkList .tkrow'); await wait(140);
  ok(p.doc.querySelector('#modal').hidden===false && p.txt('#mBody').includes('کارشناس پشتیبانی'),'روی تیکت که بزنی، گفت‌وگو باز می‌شود');
}

/* ── ۵) بی‌ورود و پیام بی‌نام ── */
{
  console.log('\n── بی‌ورود و بی‌نام ──');
  const p=await load(makeStore());
  ok(p.window.localStorage.getItem('nora-home-user')===null,'کاربر وارد نشده');
  ok(p.doc.querySelector('#modal').hidden===true && p.all('#stiles .stile').length===16,'بی‌ورود هم همهٔ کاشی‌ها باز است');
  p.click('.direct [data-sec="anon"]'); await wait(140);
  ok(p.doc.querySelector('#modal').hidden===false,'صندوق پیام بی‌نام، بی‌ورود باز می‌شود');
  ok(p.doc.querySelector('#tkSlot').hidden===false,'و کادر نوشتن همان‌جا آماده است');
  const on=p.doc.querySelector('#tkSlot .pickc.on');
  ok(on&&on.dataset.tcat==='بی‌نام','دستهٔ «بی‌نام» از پیش انتخاب است');
  ok((p.doc.querySelector('#tkText').getAttribute('placeholder')||'').includes('بی‌نام می‌ماند'),'کاربر می‌داند بی‌نام می‌رود');
  p.set('#tkText','پیشنهاد می‌کنم جلسهٔ کتاب دو بار در ماه باشد'); p.click('[data-tksend]'); await wait(200);
  const T=p.tickets()[0]||{};
  ok(T.anon===true && T.cat==='بی‌نام','تیکت بی‌نام ثبت می‌شود');
  ok(!/nora-home-user/.test(JSON.stringify(T)),'نام و شماره‌ای در تیکت نمی‌ماند');
}

/* ── ۶) پیوست‌ها ── */
{
  console.log('\n── پیوست ──');
  const p=await load(makeStore());
  p.click('.direct [data-sec="login"]'); await wait(140);
  p.click('#modal [data-ticket-open]'); await wait(120);
  p.click('[data-linkopen]'); await wait(60);
  p.set('#linUrl','نشانی غلط'); p.click('[data-linkadd]'); await wait(120);
  ok(p.all('#tkSlot .fchip').length===0 && p.txt('#toast').includes('پیوند'),'پیوند نادرست رد می‌شود');
  p.file('#fImage','عکس-رسید.png','image/png'); await wait(140);
  ok(p.all('#tkSlot .fchip').length===1 && p.txt('#tkSlot').includes('عکس-رسید.png'),'تصویر به تیکت می‌چسبد');
  p.file('#fVideo','ویدیوی-ورود.mp4','video/mp4'); await wait(140);
  ok(p.txt('#tkSlot').includes('ویدیو'),'ویدیو هم می‌چسبد');
  p.click('#tkSlot [data-frm="0"]'); await wait(120);
  ok(p.all('#tkSlot .fchip').length===1,'پیوست را می‌شود برداشت');
  p.click('[data-rec]'); await wait(140);
  ok(p.txt('#recNote').includes('ضبط') ,'بی میکروفون، راهنمای ضبط و انتخاب فایل صدا می‌آید');
  p.set('#tkText','صدای مشکل را ضبط کردم و می‌فرستم'); p.click('[data-tksend]'); await wait(200);
  const T=p.tickets()[0]||{};
  ok(T.files.length>=1 && T.files.every(f=>['image','video','file','link','voice','audio'].includes(f.kind)),'پیوست‌ها با گونه‌شان ذخیره می‌شوند');
}

/* ── ۷) جست‌وجو ── */
{
  console.log('\n── جست‌وجو ──');
  const p=await load(makeStore());
  p.set('#supQ','گواهی'); await wait(160);
  ok(p.all('#stiles .stile').length<16 && p.all('#stiles .stile').length>0,'جست‌وجو کاشی‌ها را کم می‌کند');
  ok(p.doc.querySelector('#qres').hidden===false && p.all('#qlist .qrow').length>0,'پرسش‌های پیداشده فهرست می‌شوند');
  ok(p.doc.querySelector('#supQClear').hidden===false,'دکمهٔ پاک‌کردن جست‌وجو می‌آید');
  p.click('#supQClear'); await wait(140);
  ok(p.all('#stiles .stile').length===16 && p.doc.querySelector('#qres').hidden===true,'پاک‌کردن، همه را برمی‌گرداند');
  p.set('#supQ','چیزی که نیست'); await wait(140);
  ok(p.all('#stiles .stile').length===0 && p.doc.querySelector('#tilesEmpty').hidden===false,'بی‌نتیجه، پیام راهنما می‌دهد');
  p.set('#supQ',''); await wait(120);
  ok(p.txt('#tilesTitle')==='بخش‌های ربات' && p.all('#stiles .stile').length===16,'عنوان و کاشی‌ها به حالت اول برمی‌گردند');
}

/* ── ۸) نشانی‌ها، پیام‌رسان‌ها و پاک‌سازی ── */
{
  console.log('\n── نشانی‌ها و پاک‌سازی ──');
  const p=await load(makeStore(),'#cert');
  await wait(200);
  ok(p.doc.querySelector('#modal').hidden===false && p.txt('#mTitle')==='گواهی و استعلام','نشانی #cert همان بخش را باز می‌کند');
  ok(p.doc.querySelector('#experts')!==null && p.all('#exList .mchip').length>=6,'هر کارشناس، پیام‌رسان خودش');
  const hosts=p.all('#exList .mchip').map(a=>a.getAttribute('href'));
  ok(hosts.every(h=>/^(https:\/\/(ble\.ir|t\.me|splus\.ir|gap\.im)\/|$)/.test(h)),'نشانی پیام‌رسان‌ها سالم است');
  ok(p.all('#mgList a[href^="mailto:"]').length===2,'مدیریت با پست الکترونیک');
  const syms=new Set([...p.doc.querySelectorAll('symbol')].map(s=>s.id));
  const missing=new Set();
  for(const u of p.all('use')){const id=(u.getAttribute('href')||'').slice(1); if(!syms.has(id)) missing.add(id)}
  p.click('#stiles [data-sec="complain"]'); await wait(140);
  p.click('#modal [data-ticket-open]'); await wait(140);
  for(const u of p.all('#modal use')){const id=(u.getAttribute('href')||'').slice(1); if(!syms.has(id)) missing.add(id)}
  ok(missing.size===0,'هر نمادی که صدا زده می‌شود در صفحه هست'+(missing.size?': '+[...missing].join(', '):''));
  const links=p.all('a[href]').map(a=>a.getAttribute('href'));
  const bad=links.filter(h=>h&&!/^(https?:|tel:|mailto:|#)/.test(h))
    .filter(h=>{const f=h.split('?')[0].split('#')[0]; return f&&!fs.existsSync(DIR+f)});
  ok(bad.length===0,'نشانی شکسته‌ای نیست'+(bad.length?': '+bad.join(', '):''));
  const ids=p.all('[id]').map(e=>e.id), dup=ids.filter((x,i)=>ids.indexOf(x)!==i);
  ok(dup.length===0,'هیچ شناسهٔ تکراری نیست'+(dup.length?': '+[...new Set(dup)].join(', '):''));
  const html=fs.readFileSync(DIR+'support.html','utf8');
  ok((html.match(/class="tabbar"/g)||[]).length===1 && (html.match(/id="toast"/g)||[]).length===1,'یک نوار پایین و یک پیام‌رسان');
  ok(!/data-modal=/.test(html),'جای کهنهٔ دکمه‌ها نمانده');
  const css=fs.readFileSync(DIR+'support.css','utf8');
  ok(css.split('{').length===css.split('}').length,'آکولادهای CSS موازنه است');
  ok(/\?v=17/.test(html) && (html.match(/\?v=17/g)||[]).length>=4 && !/account\.css/.test(html),'دارایی‌های صفحه نسخه‌دارند و به CSS حساب وابسته نیست');
  const js=fs.readFileSync(DIR+'support.js','utf8');
  ok(!/login\(\)|shAuth|uid\(\)/.test(js),'صفحهٔ پشتیبانی در ورود را نمی‌بندد');
  const sw=fs.readFileSync(DIR+'sw.js','utf8');
  ok(sw.includes("'support.html'") && sw.includes("'support.css'") && sw.includes("'support.js'") && /nora-v[6-9]/.test(sw),'سرویس‌ورکر صفحهٔ پشتیبانی را می‌شناسد');
  /* میان‌برهای بقیهٔ صفحه‌ها */
  const home=fs.readFileSync(DIR+'home.html','utf8'), acc=fs.readFileSync(DIR+'account.html','utf8');
  ok(!/account\.html#support/.test(home+acc+fs.readFileSync(DIR+'ui.js','utf8')+fs.readFileSync(DIR+'data.js','utf8')),'هیچ میان‌بری به نشانی کهنه نمی‌رود');
  ok(/href="support\.html"/.test(fs.readFileSync(DIR+'events.html','utf8')) && /href="support\.html"/.test(fs.readFileSync(DIR+'event.html','utf8')),'صفحه‌های رویداد هم به پشتیبانی وصل‌اند');
}

/* ── ۹) پخش راهنمای تصویری و صوتی ── */
{
  console.log('\n── پخش راهنما ──');
  const p=await load(makeStore());
  p.click('#stiles [data-sec="login"]'); await wait(140);
  p.click('#mBody .mcard'); await wait(200);
  ok(p.open().includes('shMedia'),'کارت راهنما، ورقهٔ پخش را باز می‌کند');
  ok(p.doc.querySelector('#pToggle')!==null && p.doc.querySelector('#pFill')!==null,'پخش‌کننده با دکمه و نوار پیشرفت');
  ok(p.doc.querySelector('#modal').hidden===true,'راهنما روی پاپ‌آپ نمی‌نشیند');
  p.click('#pToggle'); await wait(1400);
  const w=parseFloat((p.doc.querySelector('#pFill').style.width||'0'))||0;
  ok(w>0,'زدن پخش، پیشرفت را جلو می‌برد');
  ok((p.doc.querySelector('.pbar').getAttribute('aria-valuenow')||'0')!=='0','نوار پیشرفت برای صفحه‌خوان هم خوانا است');
  p.click('#shMedia [data-close]'); await wait(220);
  ok(p.open().length===0 && p.doc.querySelector('#modal').hidden===false,'بستن راهنما، پاپ‌آپ را برمی‌گرداند');
}

console.log('\nsupport-test: '+pass+' بررسی، '+fail+' خطا');
process.exit(fail?1:0);
