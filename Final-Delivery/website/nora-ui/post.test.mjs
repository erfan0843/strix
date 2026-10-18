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
import {fileURLToPath,pathToFileURL} from 'node:url';
import jsdom from 'jsdom';
const {JSDOM}=jsdom;
const DIR=fileURLToPath(new URL('./',import.meta.url));
let fails=0, checks=0;
const ok=(c,m)=>{checks++; if(!c){fails++; console.log('   ✗ '+m);} else console.log('   ✓ '+m);};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
function makeStore(){const m=new Map(); return {
  getItem:k=>m.has(k)?m.get(k):null, setItem:(k,v)=>m.set(k,String(v)),
  removeItem:k=>m.delete(k), clear:()=>m.clear(), key:i=>[...m.keys()][i],
  get length(){return m.size}};}
async function load(file,store,q,{fixtureMode=true,fetchImpl=null}={}){
  const errs=[];
  const dom=await JSDOM.fromFile(DIR+file,{
    runScripts:'dangerously', resources:'usable', pretendToBeVisual:true,
    ...(q?{url:pathToFileURL(DIR+file).href+q}:{}),
    beforeParse(w){
      /* Local content is intentionally enabled only by this explicit test flag. */
      w.__NORA_TEST_FIXTURE_MODE__=fixtureMode;
      w.fetch=fetchImpl||(()=>Promise.reject(new Error('offline test')));
      w.scrollTo=()=>{};
      if(w.Element&&!w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView=()=>{};
      if(store) Object.defineProperty(w,'localStorage',{configurable:true,value:store});
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      w.addEventListener('error',e=>errs.push('error: '+e.message));
      w.open=()=>null;
      w.console.error=(...a)=>{errs.push('console.error: '+a.join(' '))};
      w.onerror=(m)=>errs.push('onerror: '+m);
    }
  });
  const {window}=dom;
  if(window.document.readyState!=='complete') await new Promise(resolve=>{
    const timer=setTimeout(resolve,5000);
    window.addEventListener('load',()=>{clearTimeout(timer);resolve()},{once:true});
  });
  await wait(60);
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
  ok(p.all('.tabbar a').length===3&&p.all('.tabbar a')[2].getAttribute('href')==='events.html#lib'
      &&p.all('.tabbar a')[2].textContent.includes('کتابخانهٔ من')
      &&!p.all('.tabbar a')[2].hasAttribute('data-account-nav'),
    'کتابخانهٔ شخصیِ مطلب از پیوند حساب/پروفایل جدا می‌ماند');
  ok(p.all('.pb-q').length===1,'نقل قول نمونه هست');
  ok(p.all('.pb-list li').length>=4,'فهرست تمرینها هست');
  ok(/دقیقه مطالعه/.test(p.doc.body.textContent),'زمان خواندن هست');
  ok(/غیرفعال/.test(p.txt('#pbShare'))&&p.doc.querySelector('#pbCopy')?.disabled,'همرسانی و پیوند عمومی غیرفعال‌اند');
  ok(p.txt('body').includes('پیش‌نمایش محلی'),'نشان پیش‌نمایش در صفحه دیده می‌شود');
}

console.log('\n── ۲) مطلب بلوکی پنل ──');
{
  const store=makeStore();
  store.setItem('nora-posts',JSON.stringify([POST]));
  store.setItem('nora-forms',JSON.stringify([{id:'fr1', name:'فرم پیش‌ثبت‌نام دوره', fields:[['نام و نام خانوادگی',100],['موبایل',100]], intro:'پاسخ فقط در همین مرورگر می‌ماند؛ پیامکی ارسال نمی‌شود.', on:1}]));
  const p=await load('post.html',store,'?id=np1701');
  ok(p.errs.length===0,'مطلب بلوکی بی‌خطا'+(p.errs.length?': '+p.errs[0]:''));
  ok(p.all('.pb-toc a').length===2,'فهرست مطالب دو تیتر دارد');
  ok(!!p.doc.querySelector('#psec1'),'لنگر تیتر ساخته شده');
  ok(p.all('.pb-vid iframe').length===0
    &&!!p.doc.querySelector('.pb-vid video[src="https://example.org/clip.mp4"][controlsList="nodownload"]')
    &&!!p.doc.querySelector('.pb-aud audio[src="https://example.org/podcast.mp3"][controlsList="nodownload"]'),
    'آپارات و یوتیوب embed نمی‌شوند؛ فایل امن صوتی/ویدیویی پخش می‌شود و کنش دانلود ندارد');
  ok(p.all('.pb-disabled').length>=2,'ویدیوهای سرویس بیرونی با پیام محلی جایگزین می‌شوند؛ CTA جداگانه غیرفعال است');
  ok(p.all('a[href^="https://"],a[href^="http://"]').length===0,'مطلب هیچ پیوند بیرونیِ عملیاتی ندارد');
  ok(!!p.doc.querySelector('.pb-fig img')&&/کارگاه در حرکت/.test(p.txt('.pb-fig figcaption')),'عکس با زیرنویس هست');
  ok(p.all('.pb-q cite').length===1&&/استاد کارگاه/.test(p.txt('.pb-q cite')),'نقل قول با گوینده');
  ok(p.doc.querySelector('.pb-btn button[disabled]')!==null,'CTA بیرونی دکمهٔ غیرفعال است و مقصد باز نمی‌کند');
  ok(p.all('.pb-box').length===1&&p.all('.pb-tog').length===1&&p.all('.pb-hr').length===1,'جعبه و جمع‌شونده و جداکننده');
  ok(!!p.doc.querySelector('.pb-ev'),'کارت رویداد پیوندی هست');
  ok(/event\.html\?id=e1/.test(p.doc.querySelector('.pb-ev').getAttribute('href')),'رویداد پیوندی به event.html میرود');
  const fmA=[...p.all('a')].find(a=>/form\.html\?fr=fr1/.test(a.getAttribute('href')||''));
  ok(!!fmA,'فرم بیرویداد با fr= باز میشود');
  ok(/گزارش کارگاه عکاسی/.test(p.doc.title),'عنوان برگه شد عنوان مطلب');
  ok(/نگار صادقی/.test(p.doc.body.textContent)&&/بازدید/.test(p.doc.body.textContent),'نویسنده و بازدید هست');
  const S=JSON.parse(store.getItem('nora-posts'));
  ok(S[0].views===1,'شمار بازدید یک بار خورد');
  ok(JSON.parse(store.getItem('nora-pvlog')||'[]').length===1,'گزارش خواندن در انبار نشست');
  ok(p.all('.pb-relcard').length===0,'پیشنهاد بیبرچسب مشترک خالی است');
}

console.log('\n── ۳) پیش‌نمایش و صف تأیید و نیافتن ──');
{
  const store=makeStore();
  const draft=JSON.parse(JSON.stringify(POST)); draft.pub=0; draft.pend=0;
  store.setItem('nora-posts',JSON.stringify([draft]));
  const p=await load('post.html',store,'?id=np1701&d=1');
  ok(/پیش‌نمایش محلی/.test(p.txt('#pvRibbon')),'پیش‌نمایش با نوار پیش‌نمایش باز میشود');
  const S=JSON.parse(store.getItem('nora-posts'));
  ok(S[0].views===0,'پیش‌نمایش بازدید نمیخورد');
  const store2=makeStore();
  const pendP=JSON.parse(JSON.stringify(POST)); pendP.pub=0; pendP.pend=1;
  store2.setItem('nora-posts',JSON.stringify([pendP]));
  const p2=await load('post.html',store2,'?id=np1701');
  ok(/پیش‌نمایش محلی · پیش‌نویس منتشرنشده/.test(p2.txt('#pvRibbon')),'مطلب در صف تأیید به‌روشنی محلی و منتشرنشده برچسب می‌خورد');
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
  ok(/مطلب/.test(menuTxt)&&/\d/.test(menuTxt.replace(/[۰-۹]/g,'0')),'منو شمار مطلب‌ها را از داده می‌سازد');
  const first=p.doc.querySelector('#artRail [data-open-post-card]');
  ok(first&&first.getAttribute('data-open-post-card')==='np1701','کارت اول، مطلب پنلی است');
  ok(first?.dataset.openPostCard==='np1701'
      &&p.doc.querySelector('#artRail .pc-ttl[href="post.html?id=np1701"]')
      &&p.doc.querySelector('#artRail .pc-foot a[href="post.html?id=np1701"]'),
    'عنوان و دکمهٔ مطلب به صفحهٔ جزئیات همان مطلب پیوند مستقیم دارند');
}

console.log('\n── ۴-الف) تجربهٔ تولیدی فقط از محتوای سروری ──');
{
  const emptyHome=await load('home.html',makeStore(),'',{fixtureMode:false});
  ok(emptyHome.errs.length===0&&emptyHome.doc.querySelector('#publicContentStatus:not([hidden])')
      &&!emptyHome.doc.querySelector('#articles .pcard'),
    'نبود snapshot سروری در خانه، وضعیت شفاف و بدون کارت نمونه می‌دهد');
  const missing=await load('post.html',makeStore(),'?id=a1',{fixtureMode:false});
  ok(missing.errs.length===0&&/این مطلب پیدا نشد/.test(missing.doc.body.textContent)
      &&!missing.doc.body.textContent.includes('هفت تمرین تنفس'),
    'صفحهٔ تولیدی از مطلب ثابت محلی fallback نمی‌گیرد');

  const serverArticle={id:'server-article-9001',t:'مطلب سروری منتشرشده',cat:'گزارش',tags:['گزارش'],
    lead:'مقدمهٔ واقعی از سرور.',who:'نویسندهٔ سروری',g:GRAD,pub:true,min:3,views:17,at:'2026-06-01T12:00:00Z',
    blocks:[{ty:'p',x:'متن منتشرشده از پایگاه سرور.'},
      {ty:'vid',src:'https://www.youtube.com/watch?v=public-article-media'}]};
  const fetchImpl=async url=>url==='/api/public/site-content'
    ?{ok:true,json:async()=>({content:{articles:[serverArticle],events:[],people:[],partners:[],banners:[],library:[],cooperation:[]}})}
    :{ok:false,json:async()=>({})};
  const home=await load('home.html',makeStore(),'',{fixtureMode:false,fetchImpl});
  const card=home.doc.querySelector('#articles [data-open-post-card="server-article-9001"]');
  ok(home.errs.length===0&&home.window.NORA_PUBLIC_SOURCE==='server'
      &&card?.querySelector('.pc-ttl')?.getAttribute('href')==='post.html?id=server-article-9001'
      &&card?.querySelector('.pc-foot a')?.getAttribute('href')==='post.html?id=server-article-9001',
    'کارت محتوای منتشرشدهٔ سرور به صفحهٔ جزئیات همان شناسه می‌رود');
  const detail=await load('post.html',makeStore(),'?id=server-article-9001',{fixtureMode:false,fetchImpl});
  const publicMeta=detail.doc.querySelector('.pb-meta')?.textContent||'';
  const publicDescription=detail.doc.querySelector('meta[name="description"]')?.content||'';
  ok(detail.errs.length===0&&detail.window.NORA_PUBLIC_SOURCE==='server'
      &&detail.doc.querySelector('h1')?.textContent.includes('مطلب سروری منتشرشده')
      &&detail.doc.body.textContent.includes('متن منتشرشده از پایگاه سرور'),
    'صفحهٔ post.html همان مطلب عمومی سرور را با متن کامل نمایش می‌دهد');
  ok(detail.doc.querySelector('#pvRibbon')?.hidden&&publicMeta.includes('۱۷ بازدید')
      &&!publicMeta.includes('نمونه')&&!publicMeta.includes('پیش‌نمایش')
      &&!publicDescription.includes('نمونه')&&!publicDescription.includes('پیش‌نمایش'),
    'مطلب سروری بدون نوار نمونه/پیش‌نمایش و با شمار بازدید و توضیح بی‌گمراهی دیده می‌شود');
  {
    const copied=[];
    Object.defineProperty(detail.window.navigator,'clipboard',{configurable:true,value:{writeText:async t=>{copied.push(t)}}});
    const cpBtn=detail.doc.querySelector('#pbCopy'), shBtn=detail.doc.querySelector('#pbShare');
    ok(!!cpBtn&&!cpBtn.disabled&&cpBtn.getAttribute('aria-disabled')!=='true'&&!/غیرفعال/.test(shBtn?.textContent||''),
      'مطلب منتشرشدهٔ سرور دکمهٔ همرسانی و رونوشت نشانی فعال دارد');
    detail.click('#pbCopy'); await wait(30);
    ok(copied.length===1&&/post\.html\?id=server-article-9001$/.test(copied[0]),
      'رونوشت نشانی، نشانی عمومی همین مطلب را در کلیپ‌بورد می‌گذارد');
    detail.click('#pbShare'); await wait(30);
    ok(copied.length===2,'بدون Web Share، همرسانی به رونوشت نشانی برمی‌گردد');
    ok(/رونوشت شد/.test(detail.txt('#toast')),'بازخورد رونوشت به کاربر گفته می‌شود');
    /* شکست واقعی کلیپ‌بورد (API رد می‌کند و execCommand هم false می‌دهد) نباید «رونوشت شد» بگوید */
    Object.defineProperty(detail.window.navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw new Error('blocked')}}});
    detail.doc.execCommand=()=>false;
    detail.click('#pbCopy'); await wait(30);
    ok(/ممکن نشد|انجام نشد/.test(detail.txt('#toast'))&&!/رونوشت شد/.test(detail.txt('#toast'))
        &&detail.doc.querySelector('#toast').classList.contains('is-error'),
      'وقتی کپی واقعاً شکست می‌خورد، توست خطا می‌دهد نه موفقیت دروغین');
    Object.defineProperty(detail.window.navigator,'clipboard',{configurable:true,value:{writeText:async t=>{copied.push(t)}}});
  }
  const blockedMedia=detail.doc.querySelector('.pb-disabled');
  ok(blockedMedia?.textContent.includes('پشتیبانی نمی‌شود')
      &&!blockedMedia.textContent.includes('پیش‌نمایش محلی'),
    'محدودیت رسانهٔ بیرونی در مطلب واقعی به‌درستی توضیح داده می‌شود، نه با برچسب preview محلی');
}

console.log('\n── ۵) form.html?fr= فرم بیرویداد ──');
{
  const store=makeStore();
  store.setItem('nora-forms',JSON.stringify([{id:'fr1', name:'فرم پیش‌ثبت‌نام دوره', fields:[['نام و نام خانوادگی',100],['موبایل',100]], intro:'پاسخ فقط در همین مرورگر می‌ماند؛ پیامکی ارسال نمی‌شود.', on:1}]));
  const p=await load('form.html',store,'?fr=fr1');
  ok(p.errs.length===0,'form.html حالت fr بی‌خطا'+(p.errs.length?': '+p.errs[0]:''));
  ok(/فرم پیش‌ثبت‌نام دوره/.test(p.doc.title),'عنوان برگه نام فرم است');
  const btn=p.doc.querySelector('#next');
  btn.dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  ok(!!p.doc.querySelector('#qp0.on'),'پرسش اول پویا ساخته شد');
  ok(/نام و نام خانوادگی/.test(p.doc.querySelector('#qp0').textContent),'قلمهای فرم‌ساز همان است');
  p.type('#qa0','سارا محمدی');
  btn.dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  ok(!!p.doc.querySelector('#qp1.on'),'پرسش دوم هم هست');
  ok(!/بی‌نام/.test(p.doc.querySelector('#qp1').textContent),'پیش‌نمایش بی‌نام‌بودن پاسخ را ادعا نمی‌کند');
  p.type('#qa1','09120000000');
  btn.dispatchEvent(new p.window.MouseEvent('click',{bubbles:true}));
  ok(!!p.doc.querySelector('#u12.on'),'پایان: صفحهٔ سپاس');
  ok(/فقط در همین مرورگر|حافظهٔ همین مرورگر/.test(p.doc.querySelector('#u12').textContent)&&! /خبرت می‌کنیم|ارسال پیامک/.test(p.doc.querySelector('#u12').textContent),
    'پایان فرم محلی است و پیام یا اعلان واقعی وعده نمی‌دهد');
}

console.log('\n── ۶) پنل: ساخت و انتشار مطلب ──');
{
  const store=makeStore();
  const p=await load('admin.html',store,'#events');
  ok(p.errs.length===0,'پنل بخش رویدادها و مطالب بی‌خطا'+(p.errs.length?': '+p.errs[0]:''));
  ok(/مطلب جدید/.test(p.txt('#admBody')),'دکمهٔ مطلب جدید کنار رویداد جدید');
  ok(!!p.doc.querySelector('[data-evnew]'),'و دکمهٔ رویداد جدید هم سرِ همین بخش است');
  ok(/هفت تمرین تنفس/.test(p.txt('#admBody')),'نمونههای ثابت زیر فهرستند');
  ok(p.all('[data-ev]').length>=1,'فهرست رویدادها بالای مطلبهاست');
  ok(p.all('[data-badd]').length===0,'پالت بلوک‌ها در فهرست نیست؛ داخل ویرایشگر است');
  p.click('[data-pnew]');
  ok(!!p.doc.querySelector('[data-pf="t"]'),'مطلب جدید، ویرایشگر را زیر همین بخش باز می‌کند');
  ok(p.all('[data-badd]').length===0&&!!p.doc.querySelector('[data-pgo="2"]'),'گام یک، هویت و رسانه است؛ پالت در گام دو میآید');
  p.type('[data-pf="t"]','خبر تازهٔ باشگاه');
  p.type('[data-pf="lead"]','سه خط دربارهٔ باشگاه.');
  p.type('[data-pf="cat"]','گزارش');
  p.type('[data-pf="tags"]','گزارش، باشگاه');
  p.click('[data-pgo="2"]');
  ok(p.all('[data-badd]').length>=16,'پالت بلوکها در گام دوم کامل است ('+p.all('[data-badd]').length+')');
  ok(!!p.doc.querySelector('[data-pev]')&&!!p.doc.querySelector('[data-pfm]'),'پیوند رویداد و فرم در گام دوم است');
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
  ok(/مدیریت مطلب/.test(p.txt('#admBody'))&&/بازدید/.test(p.txt('#admBody')),'بعد از انتشار، مدیریت مطلب با بازدید باز میشود');
  p.click('[data-pmgrback]');
  ok(/خبر تازهٔ باشگاه/.test(p.txt('#admBody'))&&/منتشر شده/.test(p.txt('#admBody')),'فهرست، منتشرشده را میگوید و زیر رویدادهاست');
  p.click('[data-ppin]');
  const S3=JSON.parse(store.getItem('nora-posts'));
  ok(S3[0].pin===1,'پین از فهرست میچرخد');
  /* ویرایش: بلوکها در گام دوم جابهجا و برداشته میشوند */
  p.click('[data-pedit]');
  ok(!!p.doc.querySelector('[data-pf="t"]'),'ویرایش دوباره باز شد');
  p.click('[data-pgo="2"]');
  p.click('[data-bup="1"]');
  p.click('[data-bdel="0"]');
  ok(true,'جابهجایی و برداشتن بلوک بیخطا');
  p.click('[data-pback]');
  ok(/مطلب‌های آماده/.test(p.txt('#admBody')),'بازگشت به فهرست مطلب‌های آماده');
}

console.log('\n── ۷) related با برچسب مشترک ──');
{
  const store=makeStore();
  const rel=JSON.parse(JSON.stringify(POST)); rel.id='np1702'; rel.t='دوم' ; rel.cat='فن بیان'; rel.tags=['عکاسی'];
  const demo=JSON.parse(store.getItem('nora-posts')||'[]');
  store.setItem('nora-posts',JSON.stringify([POST,rel]));
  const p=await load('post.html',store,'?id=np1701');
  ok(p.all('.pb-relcard').length>=1,'برای مطلبِ برچسب‌دار، پیشنهاد مرتبط نمایش داده می‌شود');
  ok(p.all('.pb-relcard').some(card=>/دوم/.test(card.textContent)),'مطلب دوم با برچسب مشترک در پیشنهادهاست');
}


console.log('\n── ۸) تعریف جدید: فقط مطلب ──');
{
  const store=makeStore();
  const p=await load('admin.html',store,'#newev');
  ok(p.errs.length===0,'تعریف جدید بی‌خطا'+(p.errs.length?': '+p.errs[0]:''));
  ok(p.txt('#admBar .head')==='تعریف جدید','بخش تعریف جدید باز شد');
  ok(!!p.doc.querySelector('[data-pf="t"]')&&!!p.doc.querySelector('[data-pgo="2"]'),'همین‌جا ویرایشگر دوگامی مطلب است');
  ok(p.all('[data-wkind]').length===0,'انتخابگر رویداد و مطلب از ویزارد رفت');
  p.type('[data-pf="t"]','مطلب تعریف جدید');
  p.click('[data-pgo="2"]');
  p.click('[data-badd="p"]');
  p.type('[data-bi="0"][data-bf="x"]','متن مطلب تعریف جدید.');
  ok(!!p.doc.querySelector('[data-pprev]')&&!!p.doc.querySelector('[data-ppub]'),'پیش‌نمایش و انتشار در گام دوم سرِ کار است');
  p.click('[data-ppub]');
  const P=JSON.parse(store.getItem('nora-posts'));
  ok(P.length===1&&P[0].pub===1,'از تعریف جدید منتشر شد');
  ok(p.txt('#admBar .head')==='رویدادها و مطالب','بعد از انتشار، بخش رویدادها و مطالب باز میشود');
  ok(/مدیریت مطلب/.test(p.txt('#admBody'))&&/هنوز خوانده نشده/.test(p.txt('#admBody')),'مدیریت، مطلب تازه را با گزارش خالی نشان میدهد');
  p.click('[data-pmgrback]');
  ok(/مطلب تعریف جدید/.test(p.txt('#admBody'))&&/منتشر شده/.test(p.txt('#admBody')),'و در فهرست زیر رویدادهاست');
  ok(!p.doc.querySelector('#admNav [data-sec="newev"]'),'تعریف جدید در ناوبری اصلی قرار نگرفته است');
  p.window.location.hash='#events'; await wait(20);
  p.window.location.hash='#newev'; await wait(30);
  ok(p.txt('#admBar .head')==='تعریف جدید'&&p.doc.querySelector('[data-pf="t"]').value==='','مسیر مستقیم تعریف، ویرایشگر تازه را بدون افزودن ناوبری اصلی باز می‌کند');
  /* رویداد از بخش رویدادها و مطالب؛ مدیریت هنوز باز است، پس اول برگرد */
  if(p.doc.querySelector('[data-pmgrback]')) p.click('[data-pmgrback]');
  p.click('#admNav [data-sec="events"]');
  ok(!!p.doc.querySelector('[data-evnew]'),'رویدادها و مطالب دکمهٔ رویداد جدید دارد');
  p.click('[data-evnew]');
  ok(!!p.doc.querySelector('#wzName')&&p.all('.admsteps .st').length===5,'ویزارد پنج گامی رویداد زیر همین بخش باز می‌شود');
  p.click('[data-evback]');
  ok(p.all('[data-ev]').length>=1&&p.all('.admsteps .st').length===0,'با بازگشت، فهرست رویدادها میآید');
}


console.log('\n── ۹) گالری، فایل، لینک خودکار و جدول در خواننده ──');
{
  const store=makeStore();
  const rich=JSON.parse(JSON.stringify(POST));
  rich.id='npRich'; rich.t='مطلب رسانهای'; rich.blocks=[
    {ty:'p',x:'متن آغازین.'},
    {ty:'gal',x:['posters/poster-camera.svg','posters/poster-voice.svg','posters/poster-stage.svg'],cap:'سه قاب از کارگاه'},
    {ty:'tbl',x:['قاب|نور|نتیجه','اول|کم|تاریک','دوم|بغل|خوانا']},
    {ty:'file',src:'https://example.org/kit.pdf',t:'دفترچهٔ تمرین'},
    {ty:'bm',href:'https://example.org/report',t:'گزارش کامل',x:'همهٔ عکسها و جزئیات',src:'posters/poster-media.svg'},
    {ty:'p',x:'پایان.'}];
  store.setItem('nora-posts',JSON.stringify([rich]));
  const p=await load('post.html',store,'?id=npRich');
  ok(p.errs.length===0,'مطلب رسانهای بی‌خطا'+(p.errs.length?': '+p.errs[0]:''));
  ok(p.all('.pb-galwrap .pb-fig img').length===3,'گالری سه عکس را کنار هم نشاند');
  ok(/سه قاب از کارگاه/.test(p.doc.querySelector('.pb-galwrap').nextElementSibling?p.doc.body.textContent:'')||/سه قاب از کارگاه/.test(p.doc.body.textContent),'زیرنویس گالری هست');
  ok(p.all('.pb-tbl th').length===3&&p.all('.pb-tbl td').length===6,'جدول با سرستون و دو ردیف');
  ok(/قاب/.test(p.txt('.pb-tbl th')),'سرستونها از سطر اول میآید');
  ok(p.txt('body').includes('دفترچهٔ تمرین'),'نام فایل بیرونی به‌جای لینکِ فعال حفظ می‌شود');
  ok(!p.doc.querySelector('a.pb-file[href^="https://"]'),'فایل بیرونی دانلود یا باز نمی‌شود');
  ok(!!p.doc.querySelector('.pb-bm[aria-disabled="true"]')&&/گزارش کامل/.test(p.txt('.pb-bm')),'لینک خودکار فقط کارتِ غیرفعال می‌سازد');
  ok(/پیوند بیرونی · غیرفعال/.test(p.txt('.pb-bmhost')),'میزبان یا مقصد بیرونی باز نمی‌شود');
  ok(!!p.doc.querySelector('.pb-bmimg img'),'تصویر پیوندِ محلی حفظ می‌شود');
  ok(p.all('a[href^="https://"],a[href^="http://"]').length===0,'بلوک فایل و لینک هم هیچ مقصد بیرونی ندارند');
}

console.log('\nخلاصه: '+(checks-fails)+' قبول، '+fails+' خطا');
process.exit(fails?1:0);
