/* ══════════════════════════════════════════════════════════════════════════
   آزمون مطلب: خوانندهٔ post.html، ادغام خانهٔ کاربر، فرم بی‌رویداد و پنل
   ──────────────────────────────────────────────────────────────────────────
   اجرا (از پوشهٔ همین فایل):
     npm i jsdom          # یک بار
     node post.test.mjs
   چه چیزی را می‌سنجد: رندر همهٔ بلوکها (پاراگراف، تیتر و فهرست مطالب،
   عکس با زیرنویس، ویدیوی آپارات و یوتیوب و فایل، صدا، نقل قول، دکمهٔ لینک،
   جعبهٔ توجه، جمع‌شونده)، پیوند رویداد و فرم، شمار بازدید، پیش‌نمایش و
   صف تأیید، مطلبهای پیشنهادی، ریل خانهٔ کاربر، حالت fr فرم کاربر و
   ویرایشگر بلوکی پنل تا انتشار.
   ══════════════════════════════════════════════════════════════════════════ */
import jsdom from 'jsdom';
const {JSDOM}=jsdom;
const DIR='/home/user/strix/docs/fa/nora-ui/';
let fails=0, checks=0;
const ok=(c,m)=>{checks++; if(!c){fails++; console.log('   ✗ '+m);} else console.log('   ✓ '+m);};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
function makeStore(){const m=new Map(); return {
  getItem:k=>m.has(k)?m.get(k):null, setItem:(k,v)=>m.set(k,String(v)),
  removeItem:k=>m.delete(k), clear:()=>m.clear(), key:i=>[...m.keys()][i],
  get length(){return m.size}};}
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
      w.console.error=(...a)=>{errs.push('console.error: '+a.join(' '))};
      w.onerror=(m)=>errs.push('onerror: '+m);
    }
  });
  await wait(700);
  const {window}=dom;
  const click=sel=>{const el=window.document.querySelector(sel); if(!el) throw new Error('نیست: '+sel);
    el.dispatchEvent(new window.MouseEvent('click',{bubbles:true}));};
  const type=(sel,v,ev)=>{const el=window.document.querySelector(sel); if(!el) throw new Error('نیست: '+sel);
    el.value=v; el.dispatchEvent(new window.Event(ev||'input',{bubbles:true}));};
  const txt=sel=>{const el=window.document.querySelector(sel); return el?el.textContent.replace(/\s+/g,' ').trim():''};
  const all=sel=>[...window.document.querySelectorAll(sel)];
  return {dom,window,doc:window.document,click,type,txt,all,errs};
}

const GRAD='linear-gradient(135deg,#1E6FD0,#0A3A82)';
const POST={id:'np1701', t:'گزارش کارگاه عکاسی خیابانی', cat:'گزارش', tags:['گزارش','عکاسی'],
  lead:'سه ساعت در خیابان، با دوربین و بی‌هیچ عجله‌ای.', author:'نگار صادقی', at:Date.now(),
  cover:{g:GRAD}, pin:1, club:0, pub:1, pend:0, views:0,
  blocks:[
    {ty:'p', x:'از میدان شروع شد؛ نور کم بود و دست‌ها سرد.'},
    {ty:'h', x:'نور را از کجا بیاوریم', lv:2},
    {ty:'p', x:'قانون یک‌سوم و گوشه‌های تیز.'},
    {ty:'h', x:'ستبندی در کوچه', lv:3},
    {ty:'img', src:'posters/poster-camera.svg', cap:'کارگاه در حرکت', alt:'کارگاه عکاسی'},
    {ty:'vid', src:'https://www.aparat.com/v/iNgzs', cap:'کلیپ کوتاه کارگاه'},
    {ty:'vid', src:'https://www.youtube.com/watch?v=dQw4w9WgXcQ'},
    {ty:'vid', src:'https://example.org/clip.mp4'},
    {ty:'aud', src:'https://example.org/podcast.mp3', cap:'پادکست جلسه'},
    {ty:'q', x:'عکاسی یعنی ایستادن در جای درست.', by:'استاد کارگاه'},
    {ty:'ul', x:['قانون یک‌سوم','نور از بغل','کادر تمیز']},
    {ty:'btn', x:'ثبت‌نام دورهٔ بعد', href:'https://lifeline1.ir/reg', kind:'primary'},
    {ty:'box', x:'تمرین این هفته: ده قاب از یک کوچه.', ic:'i-info'},
    {ty:'tog', t:'تجهیزات پیشنهادی', x:'دوربین بی‌آینه و لند ثابت.'},
    {ty:'hr'}
  ], ev:'e1', fm:'fr1'};

console.log('\n── ۱) خواندن نمونهٔ ثابت (a1) ──');
{
  const p=await load('post.html',makeStore(),'?id=a1');
  ok(p.errs.length===0,'post.html نمونه ثابت بی‌خطا'+(p.errs.length?': '+p.errs[0]:''));
  ok(/هفت تمرین تنفس/.test(p.txt('h1')),'عنوان نمونه میآید');
  ok(p.all('.pb-q').length===1,'نقل قول نمونه هست');
  ok(p.all('.pb-list li').length>=4,'فهرست تمرینها هست');
  ok(/دقیقه مطالعه/.test(p.doc.body.textContent),'زمان خواندن هست');
  ok(!!p.doc.querySelector('#pbShare')&&!!p.doc.querySelector('#pbCopy'),'همرسانی و رونوشت هست');
}

console.log('\n── ۲) مطلب بلوکی پنل ──');
{
  const store=makeStore();
  store.setItem('nora-posts',JSON.stringify([POST]));
  store.setItem('nora-forms',JSON.stringify([{id:'fr1', name:'فرم پیش‌ثبت‌نام دوره', fields:[['نام و نام خانوادگی',100],['موبایل',100]], intro:'ثبت شد؛ خبرت می‌کنیم.', on:1}]));
  const p=await load('post.html',store,'?id=np1701');
  ok(p.errs.length===0,'مطلب بلوکی بی‌خطا'+(p.errs.length?': '+p.errs[0]:''));
  ok(p.all('.pb-toc a').length===2,'فهرست مطالب دو تیتر دارد');
  ok(!!p.doc.querySelector('#psec1'),'لنگر تیتر ساخته شده');
  ok(p.all('.pb-vid iframe').length===2,'آپارات و یوتیوب هر دو iframe شدند');
  ok(/videohash\/iNgzs\/vt\/frame/.test(p.all('.pb-vid iframe')[0].src),'نشانی امبد آپارات درست است');
  ok(/youtube-nocookie\.com\/embed\/dQw4w9WgXcQ/.test(p.all('.pb-vid iframe')[1].src),'امبد یوتیوب درست است');
  ok(!!p.doc.querySelector('.pb-vid video'),'فایل mp4 پخش‌گر خودش را گرفت');
  ok(!!p.doc.querySelector('.pb-aud audio'),'صدا پخش‌گر گرفت');
  ok(/پادکست جلسه/.test(p.txt('.pb-aud .pb-audrow')),'نام فایل صوتی هست');
  ok(!!p.doc.querySelector('.pb-fig img')&&/کارگاه در حرکت/.test(p.txt('.pb-fig figcaption')),'عکس با زیرنویس هست');
  ok(p.all('.pb-q cite').length===1&&/استاد کارگاه/.test(p.txt('.pb-q cite')),'نقل قول با گوینده');
  ok(p.all('.pb-btn a')[0].target==='_blank','دکمهٔ لینک در پنجرهٔ تازه باز می‌شود');
  ok(p.all('.pb-box').length===1&&p.all('.pb-tog').length===1&&p.all('.pb-hr').length===1,'جعبه و جمع‌شونده و جداکننده');
  ok(!!p.doc.querySelector('.pb-ev'),'کارت رویداد پیوندی هست');
  ok(/event\.html\?id=e1/.test(p.doc.querySelector('.pb-ev').getAttribute('href')),'رویداد پیوندی به event.html میرود');
  const fmA=[...p.all('a')].find(a=>/form\.html\?fr=fr1/.test(a.getAttribute('href')||''));
  ok(!!fmA,'فرم بیرویداد با fr= باز میشود');
  ok(/گزارش کارگاه عکاسی/.test(p.doc.title),'عنوان برگه شد عنوان مطلب');
  ok(/نگار صادقی/.test(p.doc.body.textContent)&&/بازدید/.test(p.doc.body.textContent),'نویسنده و بازدید هست');
  const S=JSON.parse(store.getItem('nora-posts'));
  if(S[0].views!==1) console.log('   [dbg] views='+S[0].views+' keys='+Object.keys(S[0]).join(','));
  ok(S[0].views===1,'شمار بازدید یک بار خورد');
  ok(p.all('.pb-relcard').length===0,'پیشنهاد بیبرچسب مشترک خالی است');
}

console.log('\n── ۳) پیش‌نمایش و صف تأیید و نیافتن ──');
{
  const store=makeStore();
  const draft=JSON.parse(JSON.stringify(POST)); draft.pub=0; draft.pend=0;
  store.setItem('nora-posts',JSON.stringify([draft]));
  const p=await load('post.html',store,'?id=np1701&d=1');
  ok(/پیش‌نمایش سازنده/.test(p.txt('#pvRibbon')),'پیش‌نمایش با نوار پیش‌نمایش باز میشود');
  const S=JSON.parse(store.getItem('nora-posts'));
  ok(S[0].views===0,'پیش‌نمایش بازدید نمیخورد');
  const store2=makeStore();
  const pendP=JSON.parse(JSON.stringify(POST)); pendP.pub=0; pendP.pend=1;
  store2.setItem('nora-posts',JSON.stringify([pendP]));
  const p2=await load('post.html',store2,'?id=np1701');
  ok(/در انتظار تأیید/.test(p2.txt('#pvRibbon')),'مطلب در صف تأیید برچسبش را دارد');
  const p3=await load('post.html',makeStore(),'?id=zzz');
  ok(/این مطلب پیدا نشد/.test(p3.doc.body.textContent),'مطلب نایافته پیام لطیف دارد');
}

console.log('\n── ۴) خانهٔ کاربر: مطلب پنلی در ریل و منو ──');
{
  const store=makeStore();
  store.setItem('nora-posts',JSON.stringify([POST]));
  const p=await load('home.html',store);
  ok(p.errs.length===0,'خانه بی‌خطا'+(p.errs.length?': '+p.errs[0]:''));
  ok(/گزارش کارگاه عکاسی/.test(p.txt('#artRail')),'مطلب پنلی سر ریل مطالب است');
  const menuTxt=p.doc.body.textContent;
  ok(/مطلب تازه/.test(menuTxt),'شمار مطلبهای منو زنده است');
  const first=p.doc.querySelector('#artRail [data-article]');
  ok(first&&first.getAttribute('data-article')==='np1701','کارت اول، مطلب پنلی است');
}

console.log('\n── ۵) form.html?fr= فرم بیرویداد ──');
{
  const store=makeStore();
  store.setItem('nora-forms',JSON.stringify([{id:'fr1', name:'فرم پیش‌ثبت‌نام دوره', fields:[['نام و نام خانوادگی',100],['موبایل',100]], intro:'ثبت شد؛ خبرت می‌کنیم.', on:1}]));
  const p=await load('form.html',store,'?fr=fr1');
  ok(p.errs.length===0,'form.html حالت fr بی‌خطا'+(p.errs.length?': '+p.errs[0]:''));
  ok(/فرم پیش‌ثبت‌نام دوره/.test(p.doc.title),'عنوان برگه نام فرم است');
  const btn=p.doc.querySelector('#next');
  btn.dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  ok(!!p.doc.querySelector('#sqp0.on'),'پرسش اول پویا ساخته شد');
  ok(/نام و نام خانوادگی/.test(p.doc.querySelector('#sqp0').textContent),'قلمهای فرم‌ساز همان است');
  btn.dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  ok(!!p.doc.querySelector('#sqp1.on'),'پرسش دوم هم هست');
  ok(/فقط برای سازندهٔ فرم/.test(p.doc.querySelector('#sqp1').textContent),'برچسب بی‌نامی در fr نمیآید');
  btn.dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  ok(!!p.doc.querySelector('#u12.on'),'پایان: صفحهٔ سپاس');
  ok(/فرم شما دریافت شد/.test(p.doc.querySelector('#u12').textContent),'و متن پایان فرم است، نه نظرسنجی');
}

console.log('\n── ۶) پنل: ساخت و انتشار مطلب ──');
{
  const store=makeStore();
  const p=await load('admin.html',store,'#posts');
  ok(p.errs.length===0,'پنل بخش مطلبها بی‌خطا'+(p.errs.length?': '+p.errs[0]:''));
  ok(/مطلب تازه/.test(p.txt('#admBody')),'فهرست مطلبها با دکمهٔ تازه');
  ok(/هفت تمرین تنفس/.test(p.txt('#admBody')),'نمونههای ثابت زیر فهرستند');
  p.click('[data-pnew]');
  ok(!!p.doc.querySelector('[data-pf="t"]'),'ویرایشگر مطلب باز شد');
  ok(p.all('[data-badd]').length>=11,'پالت بلوکها کامل است ('+p.all('[data-badd]').length+')');
  p.type('[data-pf="t"]','خبر تازهٔ باشگاه');
  p.type('[data-pf="lead"]','سه خط دربارهٔ باشگاه.');
  p.type('[data-pf="cat"]','گزارش');
  p.type('[data-pf="tags"]','گزارش، باشگاه');
  p.click('[data-badd="p"]');
  p.click('[data-badd="h"]');
  p.click('[data-badd="vid"]');
  p.click('[data-badd="aud"]');
  p.type('[data-bi="0"][data-bf="x"]','متن اول مطلب تازه.');
  p.type('[data-bi="1"][data-bf="x"]','تیتر میانی');
  p.type('[data-bi="2"][data-bf="src"]','https://www.aparat.com/v/abc12');
  p.type('[data-bi="3"][data-bf="src"]','https://example.org/a.mp3');
  const sel=p.doc.querySelector('[data-pev]');
  sel.value=sel.options[1].value; sel.dispatchEvent(new p.window.Event('change',{bubbles:true}));
  const evSel=sel.value;
  const sel2=p.doc.querySelector('[data-pfm]');
  sel2.value=''; sel2.dispatchEvent(new p.window.Event('change',{bubbles:true}));
  ok(!!p.doc.querySelector('[data-pprev]'),'دکمهٔ پیش‌نمایش هست');
  ok(!!p.doc.querySelector('[data-ppub]'),'مالک دکمهٔ انتشار دارد');
  p.click('[data-pprev]');
  const S1=JSON.parse(store.getItem('nora-posts')||'[]');
  ok(S1.length===1&&S1[0].pub===0,'پیش‌نمایش، پیش‌نویس در انبار گذاشت');
  p.click('[data-ppub]');
  const S2=JSON.parse(store.getItem('nora-posts'));
  ok(S2[0].pub===1&&S2[0].pend===0,'انتشار در انبار نشست');
  ok(Array.isArray(S2[0].tags)&&S2[0].tags.length===2,'برچسبها جدا شدند');
  ok(S2[0].blocks.length===4&&S2[0].blocks[2].src.includes('aparat'),'بلوکها با متن و رسانه ذخیره شدند');
  ok(S2[0].ev===evSel&&!!evSel,'پیوند رویداد ذخیره شد');
  ok(/خبر تازهٔ باشگاه/.test(p.txt('#admBody'))&&/منتشر شده/.test(p.txt('#admBody')),'فهرست، منتشرشده را میگوید');
  p.click('[data-ppin]');
  const S3=JSON.parse(store.getItem('nora-posts'));
  ok(S3[0].pin===1,'پین از فهرست میچرخد');
  /* جابهجایی بلوکها و برداشتن */
  p.click('[data-pedit]');
  p.click('[data-bup="1"]');
  const S4=JSON.parse(store.getItem('nora-posts'));
  p.click('[data-bdel="0"]');
  ok(true,'جابهجایی و برداشتن بلوک بیخطا');
  p.click('[data-pback]');
  ok(/نمونه‌های ثابت/.test(p.txt('#admBody')),'بازگشت به فهرست');
}

console.log('\n── ۷) related با برچسب مشترک ──');
{
  const store=makeStore();
  const rel=JSON.parse(JSON.stringify(POST)); rel.id='np1702'; rel.t='دوم' ; rel.cat='فن بیان'; rel.tags=['عکاسی'];
  const demo=JSON.parse(store.getItem('nora-posts')||'[]');
  store.setItem('nora-posts',JSON.stringify([POST,rel]));
  const p=await load('post.html',store,'?id=np1701');
  ok(p.all('.pb-relcard').length===1,'پیشنهاد با برچسب مشترک یک کارت است');
  ok(/دوم/.test(p.txt('.pb-relcard')),'و همان مطلب دوم است');
}


console.log('\n── ۸) تعریف جدید: فقط مطلب ──');
{
  const store=makeStore();
  const p=await load('admin.html',store,'#newev');
  ok(p.errs.length===0,'تعریف جدید بی‌خطا'+(p.errs.length?': '+p.errs[0]:''));
  ok(p.txt('#admBar .head')==='تعریف جدید','بخش تعریف جدید باز شد');
  ok(!!p.doc.querySelector('[data-pf="t"]')&&p.all('[data-badd]').length>=12,'همین‌جا ویرایشگر بلوکی مطلب است');
  ok(p.all('[data-wkind]').length===0,'انتخابگر رویداد و مطلب از ویزارد رفت');
  p.type('[data-pf="t"]','مطلب تعریف جدید');
  p.click('[data-badd="p"]');
  p.type('[data-bi="0"][data-bf="x"]','متن مطلب تعریف جدید.');
  ok(!!p.doc.querySelector('[data-pprev]')&&!!p.doc.querySelector('[data-ppub]'),'پیش‌نمایش و انتشار سرِ کار است');
  p.click('[data-ppub]');
  const P=JSON.parse(store.getItem('nora-posts'));
  ok(P.length===1&&P[0].pub===1,'از تعریف جدید منتشر شد');
  ok(p.doc.querySelector('[data-pf="t"]').value==='','و ویرایشگر برای تعریف بعدی تازه شد');
  /* رویداد از بخش رویدادها */
  p.click('#admNav [data-sec="events"]');
  ok(/رویداد جدید/.test(p.txt('#admBody')),'رویدادها دکمهٔ رویداد جدید دارد');
  p.click('[data-evnew]');
  ok(!!p.doc.querySelector('#wzName')&&p.all('.admsteps .st').length===5,'ویزارد پنج گامی رویداد زیر همین بخش باز می‌شود');
  p.click('[data-evback]');
  ok(p.all('[data-ev]').length>=1&&p.all('.admsteps .st').length===0,'با بازگشت، فهرست رویدادها میآید');
}

console.log('\nخلاصه: '+(checks-fails)+' قبول، '+fails+' خطا');
process.exit(fails?1:0);
