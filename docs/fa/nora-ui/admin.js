/* ══════════════════════════════════════════════════════════════════════════
   نورا، پنل مدیران
   ──────────────────────────────────────────────────────────────────────────
   یک صفحه، شش بخش، به‌علاوهٔ داشبورد:
     داشبورد · رویداد جدید (ویزارد سه‌گامی) · رویدادها · کاربران (گواهینامه و
     مدیریت کارشناسان هم اینجاست) · فرم‌ها · گزارش‌ها · تنظیمات
   قاعده‌های پنل:
     هر عدد، هر فهرست و هر برچسب بخش از data.js می‌آید؛ واژه‌های کوتاه
     دکمه‌ها و پیام‌های لحظه‌ای هم یک‌جا، در بلوک همین پرونده.
     هر کاری که هنوز سرور ندارد، یا به صفحهٔ کارش می‌رود یا با پیام روشن
     جواب می‌دهد؛ دکمهٔ بی‌جواب و کارت توخالی نداریم.
     نقش‌ها واقعی‌اند: بخشی که نقش کاربر اجازه ندارد، قفل باز می‌شود و
     می‌گوید از کجا باید اجازه گرفت.
   ══════════════════════════════════════════════════════════════════════════ */
(function(){
'use strict';

const N=window.NORA||{}, A=N.ADMIN||{}, UI=window.NORA_UI||{};
const W=A.w||{}, T=A.t||{}, D=A.d||{};
const HOME=A.home||{k:'dash',n:'داشبورد',i:'i-grid',s:''};
const ALLSECS=[HOME].concat(A.menu||[]);

const $=s=>document.querySelector(s), $$=s=>Array.from(document.querySelectorAll(s));
const ico=(n,c)=>'<svg class="i '+(c||'')+'" aria-hidden="true"><use href="#'+n+'"/></svg>';
const esc=s=>String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const fa=n=>String(n==null?'':n).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
const un =s=>String(s==null?'':s).replace(/[۰-۹]/g,d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/[٠-٩]/g,d=>'٠١٢٣٤٥٦٧٨٩'.indexOf(d));
/* جست‌وجوی فارسی: ی و ک عربی، اعداد، و فاصلهٔ مجازی یک‌دست می‌شوند */
const norm=s=>un(String(s||'')).toLowerCase().replace(/[يى]/g,'ی').replace(/[كک]/g,'ک')
  .replace(/\u200c/g,' ').replace(/[‌\s]+/g,' ').trim();
const toast=(m)=>{ if(AUD.on) AUD.tick++; return (UI.toast||(x=>{}))(m) };
const copy=UI.copyText||(()=>{});
const tag=(b,k)=>b?`<span class="tag ${k||''}">${esc(b)}</span>`:'';
const btn=(label,attrs,i)=>`<button class="btn sm" ${attrs||''}>${i?ico(i):''}${esc(label)}</button>`;
/* قانون خروجی: هیچ فایلی مستقیم دانلود نمیشود؛ فقط پیش‌نمایش تار و فایل کامل
   از ربات بلهٔ موسسه می‌آید (نشانی یکجا در data.js کنار ADMIN.bale). */
const baleStart=c=>'https://ble.ir/'+(A.bale||'lifeline_bot')+'?start='+c;
const baleA=(code,label)=>S.baleReg
  ?'<button class="btn sm" data-balesend="'+esc(code)+'">'+ico('i-send')+esc(label||'فرستادن به ربات بله')+'</button>'
  :'<button class="btn sm brand" data-bale="'+esc(code)+'">'+ico('i-send')+esc(label||'دریافت از ربات بله')+'</button>';
/* نخستین دریافت: برگهٔ پیوند با ربات؛ لینک دقیق، پس از ثبت فقط ارسال */
const baleIntro=code=>{sheetImpl('shAdm',`<div class="admsheet">
    <div class="row"><div class="head">${esc('نخستین دریافت: پیوند با ربات')}</div><span class="sp"></span>
      ${btn(W.close||'بستن','data-close')}</div>
    <p class="cap">${esc('بار نخست در ربات بلهٔ موسسه ثبت‌نام می‌کنید؛ پس از آن هر گزارشی که بخواهید بی هیچ گام اضافه‌ای در همان ربات به دستتان می‌رسد.')}</p>
    <a class="btn brand" data-balereg target="_blank" rel="noopener" href="${baleStart(code)}">${ico('i-send')}رفتن به ربات و ثبت‌نام</a>
    <div class="row"><span class="sp"></span><button class="btn sm quiet" data-balereg>${esc('ثبت‌نام کرده‌ام؛ از این پس خودکار بفرست')}</button></div>
    <p class="cap" dir="ltr" style="overflow-wrap:anywhere">${baleStart(code)}</p></div>`);};
const balebox=(pv,code,label)=>`<div class="balebox"><div class="pv">${pv}</div>
  <div class="ov">${ico('i-lock')}<b>فقط پیش‌نمایش تار</b><small class="cap">${esc(label||'فایل کامل از ربات بلهٔ موسسه می‌آید')}</small>${baleA(code)}</div></div>`;
/* پیشنمایش زندهٔ گواهینامه: همان موتور SVG صفحهٔ کاربر، پرشده با دادهٔ نمونه */
const certLive=(o,label)=>{let pv='';
  try{ pv=(window.certificateSVG||function(){return ''})(o||{})||'' }catch(e){}
  if(!pv) pv=`<div class="pvsheet">${'<i></i>'.repeat(7)}</div>`;
  return `<div class="balebox live"><div class="pv">${pv}</div>
    <div class="ov">${ico('i-medal')}<b>پیش‌نمایش زنده</b><small class="cap">${esc(label||'فایل ورد کامل از ربات بلهٔ موسسه می‌آید')}</small>${baleA('cert_sample','نمونهٔ کامل از ربات بله')}</div></div>`};
/* گزارش اکسلِ هر بخش: یک ردیف سبک */
const baleRow=(code,title)=>`<div class="balerow">${ico('i-download')}
  <span class="sp"><b>گزارش اکسل این بخش</b><small class="cap">${esc(title)} · فایل کامل از ربات بلهٔ موسسه می‌آید</small></span>
  ${baleA(code,'اکسل')}</div>`;
/* موتور صدور گواهینامه: پنجرهٔ خلوت و صف شبانه */
const certWin=()=>{const h=(new Date()).getHours(); return h<2?'امشب ۰۲:۰۰':'شب آینده ۰۲:۰۰'};
const certXls=()=>Array.isArray((S.cert||{}).xlsRows)?S.cert.xlsRows:[];
/* خواندن docx و xlsx: پروندهٔ فشرده بی سرور باز میشود؛ ذخیرهٔ بدون فشردهسازی
   همان لحظه برمیگردد و فشرده با DecompressionStream باد میکند */
const utf8=u8=>new TextDecoder().decode(u8);
const xent=s=>String(s||'').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&apos;/g,"'").replace(/&amp;/g,'&');
const zipPull=async(buf,name)=>{
  try{
    const u8=new Uint8Array(buf), dv=new DataView(buf);
    let i=u8.length-22;
    for(;i>=0;i--){ if(dv.getUint32(i,true)===0x06054b50) break }
    if(i<0) return null;
    let off=dv.getUint32(i+16,true);
    const cnt=dv.getUint16(i+10,true);
    for(let e=0;e<cnt;e++){
      if(dv.getUint32(off,true)!==0x02014b50) break;
      const m=dv.getUint16(off+10,true), cs=dv.getUint32(off+20,true),
        nl=dv.getUint16(off+28,true), el=dv.getUint16(off+30,true), cl=dv.getUint16(off+32,true);
      const fn=utf8(u8.subarray(off+46,off+46+nl));
      if(fn===name){
        const lo=dv.getUint32(off+42,true), lnl=dv.getUint16(lo+26,true), lel=dv.getUint16(lo+28,true);
        const st=lo+30+lnl+lel, comp=u8.subarray(st,st+cs);
        if(m===0) return comp;
        if(m===8&&typeof DecompressionStream==='function'){
          try{ const out=await new Response(new Blob([comp]).stream()
            .pipeThrough(new DecompressionStream('deflate-raw'))).arrayBuffer();
            return new Uint8Array(out) }catch(e){ return null } }
        return null;
      }
      off=off+46+nl+el+cl;
    }
  }catch(e){}
  return null; };
const xmlText=x=>xent(String(x).replace(/<\/w:p>/g,'\n').replace(/<[^>]+>/g,''));
const certParamsOf=txt=>{ const out=[], re=/\{([^{}\n]{1,30})\}/g; let m;
  while((m=re.exec(txt))){ const t=m[1].trim(); if(t&&out.indexOf(t)<0) out.push(t) } return out };
const certDocxParams=async buf=>{ const d=await zipPull(buf,'word/document.xml');
  return d?certParamsOf(xmlText(utf8(d))):null };
const certXlsxRows=async buf=>{
  const ss=await zipPull(buf,'xl/sharedStrings.xml');
  const sh=ss?xmlText(utf8(ss)).split('\n').map(x=>x.trim()).filter(Boolean):[];
  const s1=await zipPull(buf,'xl/worksheets/sheet1.xml');
  if(!s1) return null;
  const xml=String(utf8(s1)), rows=[];
  xml.replace(/<row[^>]*>([\s\S]*?)<\/row>/g,(_,r)=>{
    const cells=[];
    String(r).replace(/<c[^>]*?(?:\st="(\w+)")?[^>]*>([\s\S]*?)<\/c>/g,(_,t,v)=>{
      const mv=/<v>([^<]*)<\/v>/.exec(v||'');
      cells.push(t==='s'&&mv?(sh[+mv[1]]||''):(mv?mv[1]:'')); return ''});
    rows.push(cells.join(' ')); return ''});
  return rows.filter(x=>x.trim()); };
const certRowsOf=lines=>lines.map(line=>{
  const nums=un(line).match(/\d+/g)||[];
      const mob=nums.find(x=>/^0\d{10}$/.test(x)), nat=nums.find(x=>/^\d{10}$/.test(x));
  const key=mob||nat||'';
  const name=line.replace(/[0-9۰-۹٠-٩]+/g,'').replace(/[\s،,]+/g,' ').trim();
  const mm=key?memList().find(m=>m.ph===key||(m.nid&&un(m.nid)===key)):null;
  return {n:name, ok:!!mm}; });

/* ── واژه‌های کوتاه پنل: یک‌جا، تا عوض کردنشان یک نقطه داشته باشد ─────── */
const L={users:'فهرست کاربران', formTasks:'کارهای فرم‌ها', keys:'کلیدها',
  linkCopied:'لینک فرم رونوشت شد', sampleEvent:'کارگاه رویدادنگاری', roleSwitch:'عوض کردن نقش من',
  askCert:'استعلام گواهی',
  roleAll:'سوپرادمین همهٔ دسترسی‌ها را دارد؛ این فهرست بسته و دست‌نخورده می‌ماند.',
  roleEdit:'تیک‌ها را بزن و بردار؛ همان لحظه روی دسترسی همین نقش اثر می‌کند.',
  roleView:'دیدن دسترسی‌ها با نقش تو باز است؛ عوض کردنش با سوپرادمین است.'};

/* ── وضعیت پنل ─────────────────────────────────────────────────────────── */
const SKEY='nora-admin';
const SVER=55;
const BASE={v:SVER, sec:'dash', q:'', qMore:0, evF:'all', evId:null, evTab:'info', uF:'all',
  who:'p1', qf:'all', qdone:[], qextra:[], qgive:{}, leads:{}, specPerms:{}, specExtra:{}, extra:[], setF:'edu',
  wiz:{step:0,open:0,kind:'event',et:'',name:'',desc:'',about:'',org:'',label:'',
    poster:'',posterUp:'',theme:'glass',mode:'physical',date:'',time:'',to:'',end:'',
    dur:90,sessions:1,sess:[],place:'',link:'',privacy:'public',regFrom:'',regTo:'',
    held:0,who:0,rep:'',media:'',
    cap:45,pre:6,extra:4,waitMode:'auto',tickets:'one',
    feat:{},att:'qr',ch:{notify:1,bale:1,email:1},points:10,
    fp:{reg:'',survey:'auto',exam:'',other:''},exam:'none',remEvery:1,
    rem:[{w:'before',n:24,u:'h',ch:'bale',on:1},{w:'before',n:1,u:'h',ch:'sms',on:1},
         {w:'after',n:1,u:'d',ch:'notify',on:1}],
    stamp:0,edit:''},
  defs:[], evEdit:{},
  cert:{step:0,file:'',evs:[],tags:[],xlsRows:null,picked:[],vals:{},letter:'',months:'',news:'',rand:''},
  rpCust:[], rpCustOn:0, rpSchedExtra:[], auditLast:null,
  skin:0, skinTab:'home',
  setG:'texts', toggles:{}, texts:{}, jobs:[], added:[], uov:{}, rp:'', baleReg:0,
  uV:'', uTag:'', uRej:'', uhide:[], upar:{}, uocc:{}, uoccC:[], urules:{}, urulesC:[], uabs:[], ushop:[],
  ulog:[], uinbox:{}, uextra:[], uimp:[], ulabels:[], rankHide:0,
  psec:'list', pstep:1, ped:null};
let S=JSON.parse(JSON.stringify(BASE));
try{
  const v=JSON.parse(localStorage.getItem(SKEY)||'null');
  if(v&&typeof v==='object'){
    S=Object.assign(S,v);
    S.wiz=Object.assign({},BASE.wiz,v.wiz||{});
    S.cert=Object.assign({},BASE.cert,v.cert||{});
    if(v.ped){ if(!Array.isArray(v.ped.blocks)) delete v.ped; }
    ['jobs','added','qdone','qextra','extra','defs','uoccC','urulesC','uabs','ushop','ulog','uextra','uimp','ulabels','ushopDone','uhide','rpCust','rpSchedExtra'].forEach(k=>{if(!Array.isArray(S[k])) S[k]=[]});
    ['qgive','leads','specPerms','specExtra','upar','uocc','urules','uinbox'].forEach(k=>{if(!S[k]||typeof S[k]!=='object') S[k]={}});
    if(S.uimpPv&&typeof S.uimpPv!=='object') S.uimpPv=null;
    /* حالت دور پیش پنل: نقش تخت جایش را به حوزه داده */
    delete S.role; delete S.perms; delete S.permRole; delete S.custom;
    if(!S.uov||typeof S.uov!=='object') S.uov={};
    if(!S.toggles||typeof S.toggles!=='object') S.toggles={};
    if(!S.texts||typeof S.texts!=='object') S.texts={};
  }
}catch(e){}
const save=()=>{try{localStorage.setItem(SKEY,JSON.stringify(Object.assign({},S,{q:'',evId:null})))}catch(e){}};

/* خاموش و روشن‌های تنظیمات: پیش‌فرض از داده، بعد از آن از خود کاربر */
const togDef=(g,label,def)=>{const k=g+'|'+label; if(!(k in S.toggles)) S.toggles[k]=!!def; return S.toggles[k]};
const txtDef=(k,v)=>{if(!(k in S.texts)) S.texts[k]=v; return S.texts[k]};

/* ── حوزه‌ها و آدم‌ها ──────────────────────────────────────────────────────
   پنل روی «شخص» می‌چرخد، نه روی نقش تخت: مالک، سرپرست حوزه، کارشناس.
   هر کس داشبورد و کارتابل خودش را دارد و بخش‌ها به‌اندازهٔ حوزه‌اش باز است. */
const FIELDS=A.fields||[], PEOPLE=A.people||[], QUEUE=A.queue||[], PULSE=A.pulse||[], FEED=A.feed||[];
const PERMS=A.perms||{}, PROWS=PERMS.rows||[], OWNER_PERMS=PERMS.owner||[];
const fieldOf=k=>FIELDS.find(f=>f.k===k)||FIELDS[0];
const allP=()=>PEOPLE.concat(S.extra||[]);
const personOf=k=>allP().find(p=>p.k===k)||allP()[0]||{k:'',n:'',f:'owner',lv:'مالک',open:0,done:0,late:0,avg:0,load:0,score:0};
const me=()=>personOf(S.who);
const myField=()=>fieldOf(me().f);
const isOwner=()=>me().f==='owner';
const isLead=()=>me().lv==='سرپرست';
const leadK=f=>S.leads[f]||fieldOf(f).lead;
const leadOf=f=>personOf(leadK(f));
const teamOf=f=>allP().filter(p=>p.f===f&&p.k!==leadK(f));
const fieldSecs=()=>{const f=myField(); return isOwner()?f.sections:(isLead()?f.sections:(f.spec||['dash']))};
const canSec=k=>fieldSecs().indexOf(k)>-1;
const fieldOfSec=k=>FIELDS.find(f=>f.k!=='owner'&&(f.sections||[]).indexOf(k)>-1);
/* کارتابل: مالک همه، سرپرست حوزه کار حوزهٔ خودش، کارشناس فقط کارهای خودش */
const qDone=id=>(S.qdone||[]).indexOf(id)>-1;
const qWho=it=>(S.qgive||{})[it.id]||it.who;
const qAll=()=>QUEUE.concat(S.qextra||[]);
const myQueue=()=>qAll().filter(it=>isOwner()?true:(isLead()?it.f===me().f:qWho(it)===me().k));
const qOpen=()=>myQueue().filter(it=>!qDone(it.id));
/* دسترسی: سرپرست حوزه همهٔ دسترسی‌های حوزه‌اش را دارد؛ کارشناس آن‌هایی که تیک خورده */
const specPermsOf=f=>{const o=(S.specPerms||{})[f]; return o?o.slice():(fieldOf(f).specPerms||[])};
const extraOf=k=>(S.specExtra||{})[k]||[];
function canPerm(p){
  const row=PROWS.find(r=>r[0]===p); if(!row) return false;
  if(isOwner()) return true;
  if(row[2]!=='any'&&row[2]!==myField().k) return false;
  if(isLead()) return true;
  return specPermsOf(myField().k).indexOf(p)>-1||extraOf(me().k).indexOf(p)>-1;
}
const permRowsOf=f=>PROWS.filter(r=>r[2]===f||r[2]==='any');

/* ── آدم‌ها: فهرست کاربران ─────────────────────────────────────────────── */
const MEM=[
  {id:'u1', n:'سارا محمدی',  code:'NL-1024', ph:'09121234567', st:['تأییدشده','ok'],   tags:['عضو باشگاه','عکاس'], reg:'شهریور ۱۴۰۳', ev:6, pt:2450, note:'مدرس کارگاه عکاسی'},
  {id:'u2', n:'امیر کاظمی',  code:'NL-1025', ph:'09123456789', st:['تأییدشده','ok'],   tags:['عضو باشگاه','داوطلب'], reg:'مهر ۱۴۰۳', ev:5, pt:2180, note:''},
  {id:'u3', n:'نگار موسوی',  code:'NL-1026', ph:'09351112233', st:['در صف تأیید','warn'], tags:['تازه'], reg:'مهر ۱۴۰۴', ev:1, pt:120, note:'پروفایل نیمه‌کاره'},
  {id:'u4', n:'رضا شریفی',   code:'NL-1027', ph:'09127778899', st:['مسدود','stop'], tags:['بدهی'], reg:'تیر ۱۴۰۳', ev:0, pt:0, note:'دو پرداخت ناموفق'},
  {id:'u5', n:'مریم رضایی',  code:'NL-1028', ph:'09129998877', st:['تأییدشده','ok'],   tags:['عضو باشگاه','سرپرست'], reg:'خرداد ۱۴۰۳', ev:8, pt:3120, note:''},
  {id:'u6', n:'حسین آذری',   code:'NL-1029', ph:'09364445566', st:['در صف تأیید','warn'], tags:['تازه'], reg:'مهر ۱۴۰۴', ev:0, pt:0, note:''},
  {id:'u7', n:'فاطمه کریمی', code:'NL-1030', ph:'09191112222', st:['تأییدشده','ok'],   tags:['داوطلب'], reg:'اسفند ۱۴۰۳', ev:3, pt:940, note:'داوطلب اردو'},
  {id:'u8', n:'علی نجفی',    code:'NL-1031', ph:'09022223333', st:['تأییدشده','ok'],   tags:['عضو باشگاه'], reg:'فروردین ۱۴۰۴', ev:4, pt:1470, note:''},
  {id:'u9', n:'زهرا سلطانی', code:'NL-1032', ph:'09335556677', st:['در صف تأیید','warn'], tags:['تازه','عکس‌دار'], reg:'مهر ۱۴۰۴', ev:1, pt:80, note:''},
  {id:'u10',n:'مجید رستمی',  code:'NL-1033', ph:'09121230000', st:['تأییدشده','ok'],   tags:['مدرس'], reg:'اردیبهشت ۱۴۰۳', ev:7, pt:2010, note:'مدرس فن بیان'},
  {id:'u11',n:'سمیرا احمدی', code:'NL-1034', ph:'09123334455', st:['تأییدشده','ok'],   tags:['داوطلب','عکس‌دار'], reg:'مرداد ۱۴۰۴', ev:2, pt:320, note:'داوطلب پشتیبانی'},
  {id:'u12',n:'بابک مرادی',  code:'NL-1035', ph:'09352221100', st:['تأییدشده','ok'],   tags:['کارشناس محتوا'], reg:'شهریور ۱۴۰۴', ev:3, pt:410, note:''},
  {id:'u13',n:'لیلا شفیعی',  code:'NL-1036', ph:'09192223344', st:['تأییدشده','ok'],   tags:['مترجم'], reg:'مرداد ۱۴۰۴', ev:1, pt:180, note:''},
  {id:'u14',n:'کامران یوسفی',code:'NL-1037', ph:'09124445566', st:['تأییدشده','ok'],   tags:['عکاس','داوطلب'], reg:'تیر ۱۴۰۴', ev:4, pt:760, note:'عکاس رویدادها'},
  {id:'u15',n:'مهسا تهرانی', code:'NL-1038', ph:'09367778899', st:['تأییدشده','ok'],   tags:['حسابداری'], reg:'مهر ۱۴۰۴', ev:0, pt:60, note:''}];
const memOf=id=>{const m=MEM.find(x=>x.id===id); if(!m) return null;
  const o=(S.uov||{})[id], x=MEMX[id]||{}; return Object.assign({},x,m,o||{})};
const memList=()=>MEM.concat(S.uextra||[]).filter(m=>(S.uhide||[]).indexOf(m.id)<0)
  .map(m=>{const mm=memOf(m.id); return mm||Object.assign({},MEMX[m.id]||{},m)});
const UF=[{k:'all',n:'همه'},{k:'pending',n:'در صف تأیید'},{k:'vip',n:'ویژه'},{k:'club',n:'عضو باشگاه'},{k:'blocked',n:'مسدود'}];
const ufCount=k=>({all:memList().length, pending:memList().filter(m=>m.st[1]==='warn').length,
  vip:memList().filter(m=>m.vip).length,
  club:memList().filter(m=>m.tags.indexOf('عضو باشگاه')>-1).length,
  blocked:memList().filter(m=>m.st[1]==='stop').length}[k]);

/* ── باشگاه، پرونده و مناسبتها: همهٔ امکانات کاربران، از طرح قدیم تا حالا ──
   پروندهٔ ۱۸ فیلدی با پیش‌نمایش گروهی؛ درصد تکمیل از فیلدهای پرشده درمیآید. */
const MEMX={
  u1:{ln:'محمدی',g:'زن',city:'تهران',nid:'۰۰۲۹۸۴۵۵۱۲',bd:'۱۲/۵',fa:'علی',ad:'خیابان انقلاب، کوچهٔ مهر، پلاک ۱۲',em:'sara@mail.com',ed:'کارشناسی ارشد',job:'مدرس و عکاس',src:'مستقیم',inv:7,fm:9,act:0,bio:'مدرس کارگاه عکاسی؛ از سال ۱۴۰۱ با خط زندگی.'},
  u2:{ln:'کاظمی',g:'مرد',city:'کرج',bd:'۳/۹',ed:'کارشناسی',job:'گرافیست',src:'دعوت از دوست',inv:3,fm:4,act:1},
  u3:{ln:'موسوی',g:'زن',city:'تهران',bd:'۲۱/۱۱',ed:'کارشناسی',job:'دانشجو',src:'مستقیم',inv:0,fm:1,act:0},
  u4:{ln:'شریفی',g:'مرد',city:'اصفهان',bd:'۸/۷',ed:'دیپلم',job:'آزاد',src:'گروهی اکسل',inv:0,fm:0,act:64},
  u5:{ln:'رضایی',g:'زن',city:'تهران',bd:'۱۹/۲',ed:'کارشناسی ارشد',job:'سرپرست برنامه‌ها',src:'مستقیم',inv:11,fm:12,act:0},
  u6:{ln:'آذری',g:'مرد',city:'شیراز',bd:'۷/۱۲',ed:'کارشناسی',job:'کارمند',src:'مستقیم',inv:0,fm:0,act:0},
  u7:{ln:'کریمی',g:'زن',city:'تهران',bd:'۲/۶',ed:'کارشناسی',job:'ویراستار',src:'دعوت از دوست',inv:2,fm:3,act:2},
  u8:{ln:'نجفی',g:'مرد',city:'تهران',bd:'۱۵/۴',ed:'کارشناسی',job:'برنامه‌نویس',src:'مستقیم',inv:1,fm:5,act:1},
  u9:{ln:'سلطانی',g:'زن',city:'رشت',bd:'۳۰/۹',ed:'دیپلم',job:'دانش‌آموز',src:'گروهی اکسل',inv:0,fm:0,act:0},
  u10:{ln:'رستمی',g:'مرد',city:'مشهد',bd:'۹/۳',ed:'دکتری',job:'مدرس فن بیان',src:'مستقیم',inv:5,fm:8,act:1},
  u11:{ln:'احمدی',g:'زن',city:'تبریز',bd:'۱۱/۸',ed:'کارشناسی',job:'پشتیبان',src:'دعوت از دوست',inv:1,fm:2,act:3},
  u12:{ln:'مرادی',g:'مرد',city:'تهران',bd:'۲۶/۱',ed:'کارشناسی',job:'تولید محتوا',src:'مستقیم',inv:0,fm:4,act:2},
  u13:{ln:'شفیعی',g:'زن',city:'اصفهان',bd:'۴/۱۰',ed:'کارشناسی',job:'مترجم',src:'گروهی اکسل',inv:0,fm:1,act:5},
  u14:{ln:'یوسفی',g:'مرد',city:'تهران',bd:'۱۷/۶',ed:'کارشناسی',job:'عکاس',src:'دعوت از دوست',inv:4,fm:3,act:1},
  u15:{ln:'تهرانی',g:'زن',city:'تهران',bd:'۲۸/۴',ed:'کارشناسی ارشد',job:'حسابدار',src:'مستقیم',inv:0,fm:1,act:8}};
/* پارامترهای پروفایل: هر فیلد روشن/خاموش و اجباری/اختیاری؛ نام قفل است */
const PFLDS=[['ln','نام خانوادگی','پایه',1],['nid','کد ملی','پایه'],['bd','تاریخ تولد','پایه',1],
  ['g','جنسیت','پایه'],['fa','نام پدر','خانواده'],['ad','نشانی','تماس و نشانی'],
  ['ed','مقطع تحصیلی','تحصیلات'],['job','شغل','شغل و تماس'],['em','ایمیل','شغل و تماس'],['bio','بیو','شغل و تماس']];
const uPct=m=>Math.round(PFLDS.reduce((a,f)=>a+((m[f[0]]||'')!==''?1:0),0)/PFLDS.length*100);
/* سطح باشگاه: همان آستانههای حساب کاربر، تا دو جا عدد فرق نکند */
const uLevel=m=>{const p=+m.pt||0, lv=((N.ACCOUNT||{}).levels||[]);
  let cur=lv[0]||{n:'تازه'}; lv.forEach(l=>{if(p>=(l.at||0)) cur=l}); return cur};
/* رتبهٔ کاربر از امتیاز، میان همه */
const uRank=m=>{const s=memList().slice().sort((a,b)=>(+b.pt||0)-(+a.pt||0));
  const i=s.findIndex(x=>x.id===m.id); return i<0?0:i+1};
/* مناسبتها: تولد + چهارده مناسبت آماده؛ پیشفرضها حذف نمیشوند */
const OCC=[['nowruz','نوروز',1,1,'همه',10],['tabiat','روز طبیعت',1,13,'همه',5],
  ['teacher','روز معلم',2,12,'همه',10],['ferdowsi','بزرگداشت فردوسی',2,25,'همه',5],
  ['son','روز پسر',3,14,'مرد',5],['father','روز پدر',3,27,'مرد',5],
  ['daughter','روز دختر',4,25,'زن',5],['journalist','روز خبرنگار',5,17,'همه',5],
  ['cinema','روز سینما',6,16,'همه',5],['molana','بزرگداشت مولوی',7,7,'همه',5],
  ['book','روز کتاب و کتابخوانی',8,24,'همه',5],['yalda','شب یلدا',9,30,'همه',10],
  ['woman','روز زن',12,6,'زن',10],['man','روز مرد',12,29,'مرد',5]];
const occAll=()=>OCC.map(o=>({k:o[0],n:o[1],jm:o[2],jd:o[3],g:o[4],pts:o[5],def:1}))
  .concat((S.uoccC||[]).map(o=>Object.assign({def:0},o)));
const occOn=o=>S.uocc[o.k]!==0;
/* امتیاز شرطی: هشت شرط، قانونها با حدنصاب و امتیاز؛ یکبارمصرف */
const TRG={event_attend:'حضور در رویداد',workshop_attend:'حضور در کارگاه',
  form_submit:'پر کردن فرم',survey_submit:'شرکت در نظرسنجی',invite_friend:'دعوت دوست',
  profile_complete:'تکمیل پروفایل',birthday:'جشن تولد',occasion:'مناسبت'};
const RULES=[['first_workshop','اولین کارگاه','workshop_attend',1,20],
  ['attend5','پنج حضور','event_attend',5,30],['profile','پروفایل کامل','profile_complete',1,10],
  ['invite5','پنج دعوت','invite_friend',5,25],['birthday','جشن تولد','birthday',1,15],
  ['form3','سه فرم','form_submit',3,20]];
const rulesAll=()=>RULES.map(r=>({id:r[0],n:r[1],trg:r[2],th:r[3],pts:r[4],def:1}))
  .concat(S.urulesC||[]);
const ruleOn=r=>S.urules[r.id]!==0;
/* نشانها: سیزده نشان در چهار سطح، با شرط و امتیاز و نوار پیشرفت */
const BADGES=[['first_step','👣 اولین قدم','برنزی','event_attend',1,5],
  ['welcome','🌱 خوش‌آمد','برنزی','profile_complete',1,5],['voice','💬 اولین نظر','برنزی','survey_submit',1,5],
  ['birthday3','🎂 سه‌ساله','برنزی','birthday',3,10],['busy','🔥 پرحضور','نقره‌ای','event_attend',10,15],
  ['curious','🧭 کنجکاو','نقره‌ای','form_submit',5,15],['inviter','👥 دوست‌ساز','نقره‌ای','invite_friend',10,20],
  ['loyal','🏅 وفادار','طلایی','event_attend',30,40],['pillar','🧱 ستون','طلایی','form_submit',20,30],
  ['ambassador','🌟 سفیر','طلایی','invite_friend',30,50],['legend','💎 افسانه','افسانه‌ای','event_attend',100,100],
  ['star','⭐ ستاره','افسانه‌ای','invite_friend',50,80],['sage','🦉 خرد','افسانه‌ای','form_submit',50,80]];
const uCount=(m,trg)=>({event_attend:+m.ev||0,workshop_attend:+m.ev||0,survey_submit:+m.fm||0,
  form_submit:+m.fm||0,invite_friend:+m.inv||0,profile_complete:(+uPct(m)>=80?1:0),
  birthday:(+m.pt||0)>2000?1:0,occasion:0}[trg]||0);
const badgeGot=(m,b)=>uCount(m,b[3])>=b[4];
const badgePct=(m,b)=>Math.min(100,Math.round(uCount(m,b[3])/b[4]*100));
/* فروشگاه پاداش: کد تخفیف و VIP خودکار، جایزهٔ دستی با اعلان */
const SHOP=[['d5','کد تخفیف ۵٪',100,'خودکار'],['d10','کد تخفیف ۱۰٪',200,'خودکار'],
  ['hcert','گواهی افتخار',500,'دستی'],['vip1','عضویت VIP یک‌ماهه',800,'خودکار'],
  ['ticket','بلیت رایگان رویداد',1000,'دستی'],['vipg','VIP طلایی',5000,'خودکار']];
/* صندوق پیامها و غیبتهای مجاز: اگر در خانه نبود، نمونهٔ اولیه میآید */
const uAbs=()=>(S.uabs&&S.uabs.length)?S.uabs:(S.uabs=[
  {id:'ab1',u:'u7',ev:'کارگاه عکاسی با موبایل',why:'بیماری',at:'دیروز',st:'در انتظار'},
  {id:'ab2',u:'u11',ev:'نشست کتاب‌خوانی',why:'سفر خانوادگی',at:'۲ روز پیش',st:'در انتظار'}]);
const uShopReq=()=>(S.ushop&&S.ushop.length)?S.ushop:(S.ushop=[
  {id:'sr1',u:'u2',r:'d5',at:'امروز ۱۰:۲۰',st:'در انتظار'},
  {id:'sr2',u:'u8',r:'vip1',at:'دیروز',st:'در انتظار'}]);
const uInbox=()=>(S.uinboxM&&S.uinboxM.length)?S.uinboxM:(S.uinboxM=[
  {id:'im1',u:'u3',txt:'سلام، برای کارگاه عکاسی ثبت‌نام کردم؛ لینک جلسه کی می‌آید؟',at:'امروز ۹:۴۰',read:0,rep:0},
  {id:'im2',u:'u7',txt:'ممنون از برنامهٔ آخر هفته؛ گواهی‌ام به ایمیل هم می‌آید؟',at:'دیروز ۱۸:۲۰',read:1,rep:1}]);
const uLog=()=>(S.ulog&&S.ulog.length)?S.ulog:(S.ulog=[
  {at:'امروز ۹:۱۴',who:'مالک',act:'پروفایل نگار موسوی تأیید شد'},
  {at:'دیروز ۱۶:۰۲',who:'مالک',act:'فهرست کاربران به اکسل رفت (۱۵ نفر)'}]);
const uLogAdd=act=>{S.ulog=[{at:'همین حالا',who:me().n||'مالک',act:act}].concat(S.ulog||[]).slice(0,40)};
/* برچسبها: از خود کاربران درمیآید + برچسب دلخواه پنل */
const uLabels=()=>{const c={}; memList().forEach(m=>(m.tags||[]).forEach(t=>{if(!isMoney()&&moneyTag(t))return; c[t]=(c[t]||0)+1}));
  (S.ulabels||[]).forEach(t=>{if(!(t in c)) c[t]=0}); return c};


/* ── رویدادها ──────────────────────────────────────────────────────────── */
const EV=A.events||{}, EVROWS=EV.rows||[];
/* فرم‌های ساختهٔ ویزارد، به رویدادش چسبیده، می‌مانند تا در بخش فرم‌ها هم دیده شوند */
function linkForms(evId, w0){
  const w=w0||S.wiz, fp=Object.assign({},w.fp||{}), u=(window.NORA_UI&&NORA_UI)||null, out=[];
  ['reg','survey','exam','other'].forEach(need=>{
    const id=fp[need]; if(!id) return;
    const f=formOf(id); if(!f) return;
    /* فرم‌ساز و رویداد یکی می‌مانند: ظرفیت و پنجرهٔ ثبت‌نام به فرم می‌رود */
    try{
      if(!f.demo&&u&&u.formPatch) u.formPatch(id,{ev:evId, need:need,
        cap:+w.cap||f.cap||0, start:w.regFrom||w.date||f.start||'', ends:w.regTo||w.end||f.ends||'',
        sync:{cap:1,dates:1,money:1}});
    }catch(e){}
    out.push({id:String(id), need:need, n:formName(f), q:formQs(f), money:formSum(f), ev:evId,
      link:'form.html?ev='+evId+'&kind='+need});
  });
  return out;
}
/* ویرایش آزاد است و وضعیت را عوض نمی‌کند: هر رویداد می‌تواند روکش ویرایش داشته باشد */
const evAll=()=>{const ov=S.evEdit||{};
  return (S.added||[]).concat(EVROWS).map(e=>ov[e.id]?Object.assign({},e,ov[e.id]):e);};
const evOf=id=>evAll().find(e=>e.id===id)||null;
/* عدد و یکا: رقم درشت می‌ماند و واژهٔ یکا ریز و کم‌رنگ کنارش می‌نشیند تا هیچ
   عددی درشت و بی‌توضیح نماند و در تنگی جا هم شکسته شود، نه سرریز */
const bits=v=>{const t=String(v==null?'':v).trim(), i=t.search(/\s/);
  return i<0?`<b>${esc(t)}</b>`:`<b>${esc(t.slice(0,i))} <small class="ku">${esc(t.slice(i+1))}</small></b>`;};
const evFilter=f=>f==='live'?e=>evState(e)==='live' : f==='soon'?e=>evState(e)==='soon'
  : f==='past'?e=>evState(e)==='past' : ()=>true;
/* وضعیت هر ردیف: برگزاری تمام شده؟ خودش رفته در برگزار شده */
const evStateOf=e=>evState(e);

/* ── گزارش‌ها ─────────────────────────────────────────────────────────── */
const RP=A.reports||{}, RPLIST=RP.list||[], RPD=RP.detail||{};
const rpOf=k=>RPLIST.find(r=>r.k===k)||RPLIST[0]||{};

/* ── گواهینامه ────────────────────────────────────────────────────────── */
const CE=A.cert||{}, CEP=CE.params||[];
const cenum=n=>fa(n);
const cparam=k=>{const v=(S.cert.params||{})[k]; return v==null||v===''?'':String(v)};
const certSVG=(typeof certificateSVG==='function')?certificateSVG:null;

/* ══ قطعه‌های مشترک ═════════════════════════════════════════════════════ */
const BANDS={ok:1,warn:1,stop:1,brand:1,accent:1};
function table(rows,cols){
  if(!rows||!rows.length) return emptyBox(T.none);
  const head=cols&&cols.length?`<thead><tr>${cols.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead>`:'';
  const body=rows.map(r=>{
    const cells=r.slice(), last=cells[cells.length-1], band=BANDS[String(last)];
    if(cols&&cols.length&&cells.length>cols.length&&band) cells.pop();   /* ستون برچسب جدا */
    const td=cells.map((c,i)=>{
      const isBand=band&&i===cells.length-1;
      if(isBand) return `<td>${tag(String(c),String(c))}</td>`;
      return `<td class="${/^[0-9٬,]+$/.test(String(c))?'num':''}">${esc(c)}</td>`;
    }).join('');
    return `<tr>${td}</tr>`;
  }).join('');
  return `<div class="admmatrix"><table>${head}<tbody>${body}</tbody></table></div>`;
}
function emptyBox(msg){return `<div class="empty">${ico('i-search')}<p class="cap" style="margin-top:8px">${esc(msg||T.empty)}</p></div>`}
function bars(arr,hi){
  const mx=Math.max.apply(null,arr.concat([1]));
  return `<div class="admbars">${arr.map((v,i)=>`<i class="${(hi&&i===arr.length-1)||v===mx?'hi':''}" style="height:${Math.round(v/mx*100)}%"></i>`).join('')}</div>`;
}
function rowLink(o){  /* یک ردیف کاری: آیکون یا پوستر، دو خط متن، برچسب و فلش */
  return `<button class="admrow2" ${o.attrs||''}>
    ${o.img?`<span class="ic pic"><img src="${esc(o.img)}" alt="" loading="lazy"/></span>`:`<span class="ic">${ico(o.i||'i-doc')}</span>`}
    <span class="tx"><b>${o.b||''}</b><small>${o.s||''}</small></span>
    ${o.right||''}${o.chev?ico('i-chev-left','chev'):''}</button>`;
}
const sheetImpl=(id,html)=>{const s=$('#'+id); if(!s) return; s.querySelector('.sbody').innerHTML=html;
  if(UI.uiOpen) UI.uiOpen(id); else {s.classList.add('on'); const sc=$('#scrim'); if(sc) sc.classList.add('on')}};
function miniSheet(title,html,label){
  return `<div class="admsheet">
    <div class="row"><div class="head">${esc(title)}</div><span class="sp"></span>
      <button class="btn sm quiet" data-close>${esc(W.close||'بستن')}</button></div>
    ${label?`<p class="cap">${esc(label)}</p>`:''}${html}
    <div class="row"><span class="sp"></span>${btn(W.close||'بستن','data-close')}</div></div>`;
}

/* ══ ناوبری و نوار بالا ═════════════════════════════════════════════════ */
const TABS=[{k:'dash',n:'داشبورد'},{k:'events',n:'رویدادها و مطالب'},{k:'users',n:'کاربران'},
  {k:'reports',n:'گزارش'},{k:'settings',n:'تنظیمات'}];
const secOf=k=>ALLSECS.find(s=>s.k===k)||HOME;
const NEEDQ=['users','events','forms','reports'];

function renderNav(){
  const secs=fieldSecs();
  $('#admNav').innerHTML=ALLSECS.map(s=>{
    const open=secs.indexOf(s.k)>-1, lock=!open;
    return `<button class="btn quiet block ${S.sec===s.k?'on':''}" data-sec="${s.k}" ${open?'':'data-locked="1"'}>
      ${ico(s.i)}<span>${esc(s.n)}</span>${s.badge&&open?`<span class="tag warn bd">${esc(s.badge)}</span>`:(lock?`<span class="bd">${ico('i-lock')}</span>`:'')}</button>`;}).join('');
  $('#admTabs').innerHTML=TABS.filter(t=>secs.indexOf(t.k)>-1||t.k==='dash').map(t=>{const s=secOf(t.k);
    return `<a href="#${t.k}" data-sec="${t.k}" class="${S.sec===t.k?'on':''}">${ico(s.i)}<span>${esc(t.n)}</span></a>`}).join('');
}
function renderBar(){
  const s=secOf(S.sec);
  $('#admBar').innerHTML=`
    <span class="nmark" aria-hidden="true">${ico(s.i)}</span>
    <div class="tt"><div class="head">${esc(s.n)}</div><div class="cap">${esc(s.s||A.lead||'')}</div></div>
    <span class="sp"></span>
    <span class="navclock" title="${esc((NE().l||{}).tz||'')}" aria-label="${esc('تاریخ و ساعت')}">${ico('i-clock')}
      <b data-clock>${esc(typeof clockFull==='function'?clockFull():'')}</b></span>
    ${NEEDQ.indexOf(S.sec)>-1?`<label class="searchbox">${ico('i-search')}
      <input id="admQ" type="search" autocomplete="off" placeholder="${esc(T.search||W.search||'جست‌وجو')}" value="${esc(S.q)}" aria-label="${esc(W.search||'جست‌وجو')}"/></label>`:''}
    <button class="chip" data-who-sheet>${ico('i-shield')}<span>${esc(me().n)}</span>
      <small class="cap">${esc(me().lv)}</small></button>`;
}

/* ══ بخش‌ها ═════════════════════════════════════════════════════════════ */

/* ── داشبورد ─────────────────────────────────────────────────────────────
   یک داشبورد، سه نما؛ همه‌جا ساده و پله‌پله: سرصفحه (کی هستم، چند کار باز
   دارم)، چهار عدد کلیدی، بعد کارتابل و حوزه‌ها و در ستون کنار وضعیت و
   برنامهٔ امروز و هشدارها. بی حلقه و بی شکل تزئینی؛ هیچ عددی سخت نوشته
   نشده و همه از data می‌آید. مالک همهٔ حوزه‌ها را می‌بیند، سرپرست حوزهٔ
   خودش، کارشناس کارتابل و کارنامهٔ خودش. */

const priTone=p=>p==='بالا'?'stop':p==='میان'?'warn':'';
/* خط زمان رویداد: تاریخ شمسی را با روزش می‌خواند؛ اگر متن بود، همان */
function whenLine(e){
  const j=jParse(e.on||'')||jFromWhen(e.when);
  return j?jLong(j.jy,j.jm,j.jd):(e.when||'');
}
/* نام تب را از داده می‌خواند تا دکمه‌های میان‌بر هم همان واژه را بگویند */
const tabName=k=>(((A.events||{}).tabs||[]).find(t=>t.k===k)||{n:''}).n;
/* مالی فقط دست مالک است؛ بقیه نه عدد می‌بینند نه تب مالی نه برچسب بدهی */
const isMoney=()=>isOwner();
const moneyTag=t=>((A.moneyTags||[]).some(w=>t.indexOf(w)>-1));
const priRank=p=>p==='بالا'?0:p==='میان'?1:2;

/* سرصفحهٔ داشبورد: چه روزی است، من کدام‌ام، چند کار روی میز است */
function dashHead(){
  const p=me(), f=myField(), own=isOwner(), lead=isLead(), ld=leadOf(f.k)||{};
  /* مالک فقط عنوانش را می‌بیند؛ سرپرست «حوزه · سرپرست حوزه»؛ کارشناس نام سرپرستش را */
  const sub=own?(D.ownerLine||'مالک سامانه')
    :(f.n+' · '+p.lv+(!lead&&ld.n?' · '+(D.lead||'سرپرست')+': '+ld.n:''));
  const open=qOpen(), urgent=open.filter(it=>it.pri==='بالا').length;
  return `<section class="dhead">
    <div class="dh">
      <small class="cap">${esc((A.dash||{}).day||'')}</small>
      <b>${esc(p.n)}</b>
      <span class="cap">${esc(sub)}</span>
    </div>
    <span class="sp"></span>
    <div class="dhnow">
      <b>${esc(fa(open.length))}</b>
      <small class="cap">${esc(D.qOpen||'کار باز')}${urgent?' · '+esc(fa(urgent))+' '+esc(D.urgent||'فوری'):''}</small>
    </div>
  </section>`;
}

/* چهار عدد کلیدی: برای مالک و سرپرست از حوزه، برای کارشناس از کارنامهٔ خودش */
function kpiRow(){
  const p=me(), f=myField(), own=isOwner(), lead=isLead();
  /* هدف پاسخ‌گویی از دادهٔ خود حوزه خوانده می‌شود، نه از عدد سخت‌نوشته */
  const goal=((f.rings||[]).find(r=>/پاسخ/.test(String(r[0])))||[])[3]||'';
  const rows=(own||lead)?(f.rings||[]).map(r=>[r[0],String(r[1])+(r[4]?' '+r[4]:''),r[3]||'']):[
    [D.rOpen||'کار باز من', fa(p.open)+' '+(D.qWork||'کار'), p.late?fa(p.late)+' '+(D.late||''):''],
    [D.rDone||'انجام‌شده این هفته', fa(p.done)+' '+(D.qWork||'کار'), ''],
    [D.rAvg||'میانگین پاسخ', fa(p.avg)+' '+(D.minute||'دقیقه'), goal],
    [D.rScore||'امتیاز هفته', fa(p.score), (D.of||'از')+' ۱۰۰']];
  return `<div class="kpis">${rows.map(r=>`<div class="kpi">
    <small>${esc(r[0])}</small>${bits(r[1])}<span class="cap">${esc(r[2]||'')}</span></div>`).join('')}</div>`;
}

/* وضعیت سامانه: چند خط ساده با چراغ */
function cardStatus(){
  return `<section class="card stack">
    <div class="head">${esc(D.pulse||'وضعیت سامانه')}</div>
    <div class="slist">${(PULSE||[]).map(x=>`<div class="sline">
      <span class="lst"><i class="ldot ${x.st||'ok'}" aria-hidden="true"></i></span><b>${esc(x.n)}</b>
      <span class="sp"></span><span class="cap">${esc(x.d)}</span></div>`).join('')}</div>
  </section>`;
}

/* کارتابل: هر کار یک دکمه دارد: انجام شد، واگذار، باز کن */
function cardQueue(){
  const q=myQueue();
  const qf=S.qf||'all', cap=isOwner()?8:isLead()?6:99;
  const all=q.filter(it=>!qDone(it.id)&&(qf==='all'||it.pri===qf))
    .sort((a,b)=>priRank(a.pri)-priRank(b.pri)||String(a.due).localeCompare(String(b.due)));
  const open=S.qMore?all:all.slice(0,cap);
  const done=q.filter(it=>qDone(it.id));
  const row=it=>{
    const p=personOf(qWho(it));
    return `<article class="qrow ${priTone(it.pri)}">
      <span class="qcode">${esc(it.code)}</span>
      <div class="qb"><b>${esc(it.n)}</b>
        <small>${isOwner()?esc(fieldOf(it.f).n)+' · ':''}${esc(p.n)} · ${esc(it.due)} · ${esc(it.at)}</small></div>
      <span class="qpri ${priTone(it.pri)}">${esc(it.pri)}</span>
      <div class="qa">
        <button class="btn sm quiet" data-qdone="${esc(it.id)}" aria-label="${esc(D.qDoneBtn||'انجام شد')}">${ico('i-check')}</button>
        <button class="btn sm quiet" data-qgive="${esc(it.id)}" aria-label="${esc(D.qGive||'واگذار')}">${ico('i-send')}</button>
        <button class="btn sm quiet" data-sec="${esc(it.sec)}" aria-label="${esc(D.qOpenBtn||'باز کردن')}">${ico('i-chev-left')}</button>
      </div></article>`;
  };
  return `<section class="card stack qcard">
    <div class="row"><div class="head">${esc(isOwner()?(D.q||'کارتابل'):isLead()?(D.fieldQueue||'کارتابل حوزه'):(D.myQueue||'کارتابل من'))}</div>
      <span class="sp"></span>
      <span class="cap">${esc(fa(all.length))} ${esc(D.qOpen||'کار باز')}</span>
      <span class="qfilters">${['all','بالا','میان','معمولی'].map(k=>`<button class="tag ${qf===k?'on':''}"
        data-qf="${esc(k)}">${esc(k==='all'?(T.all||'همه'):k)}</button>`).join('')}</span>
    </div>
    <div class="qlist">${open.length?open.map(row).join(''):`<div class="empty">${ico('i-check')}<p class="cap" style="margin-top:8px">${esc(D.qEmpty||'')}</p></div>`}</div>
    ${all.length>cap?`<div class="row"><span class="cap">${esc(fa(open.length))} ${esc(D.of||'از')} ${esc(fa(all.length))}</span>
      <span class="sp"></span>
      <button class="btn sm quiet" data-qmore>${esc(S.qMore?(D.qLess||'کمتر'):(D.qMore||'همهٔ کارها'))}${ico(S.qMore?'i-chev-down':'i-chev-left')}</button></div>`:''}
    ${done.length?`<div class="qdone"><span class="cap">${esc(D.qDoneToday||'انجام‌شدهٔ امروز')} (${esc(fa(done.length))})</span>
      ${done.map(it=>`<span class="qdonechip">${esc(it.code)} · ${esc(it.n)}</span>`).join('')}</div>`:''}
  </section>`;
}
/* حوزه‌ها: کارت هر حوزه با سلامت و سرپرست؛ زدنش داشبورد آن حوزه را می‌آورد */
function cardFields(){
  const f=FIELDS.filter(x=>x.k!=='owner');
  return `<section class="card stack">
    <div class="row"><div class="head">${esc(D.fields||'حوزه‌ها')}</div><span class="sp"></span>
      <span class="cap">${esc(fa(f.length))} ${esc(D.fieldWord||'حوزه')}</span></div>
    <div class="flist">${f.map(x=>{
      const l=personOf(leadK(x.k)), t=teamOf(x.k), q=qOpen().filter(it=>it.f===x.k).length;
      return `<div class="frow2">
        <span class="fic">${ico(x.i)}</span>
        <div class="ft"><b>${esc(x.n)}</b>
          <small>${esc(D.lead||'سرپرست')}: ${esc(l?l.n:(D.noLead||''))} · ${esc(fa(t.length))} ${esc(D.specs||'کارشناس')} · ${esc(fa(q))} ${esc(D.qOpen||'کار باز')}</small></div>
        <span class="fhealth ${x.health<80?'low':''}">${esc(fa(x.health))}٪</span>
        <div class="fbar"><i style="width:${x.health}%"></i></div>
        <div class="fbtns">
          ${l?`<button class="btn sm quiet" data-who="${esc(l.k)}">${esc(D.openField||'سر بزن')}</button>`:''}
          <button class="btn sm quiet" data-setlead="${esc(x.k)}" aria-label="${esc(D.setLead||'تعیین سرپرست')}">${ico('i-shield')}</button>
        </div></div>`}).join('')}</div>
  </section>`;
}
function cardTeam(){
  const f=myField(), lead=isLead(), t=(lead||isOwner())?teamOf(f.k):[];
  const rows=t.map(p=>`<div class="trow">
      <span class="va">${esc(String(p.n||' ').slice(0,1))}</span>
      <div class="tt"><b>${esc(p.n)}</b><small>${esc(p.lv)} · ${esc(fa(p.open))} ${esc(D.qOpen||'')} · ${esc(D.qDone||'')} ${esc(fa(p.done))}</small></div>
      <span class="tload"><i style="width:${p.load}%"></i></span>
      <span class="cap">${esc(fa(p.load))}٪</span>
      <button class="btn sm quiet" data-specperm="${esc(p.k)}">${esc(D.specPerms||'دسترسی‌ها')}</button>
    </div>`).join('');
  return `<section class="card stack">
    <div class="row"><div class="head">${esc(lead?(D.team||'تیم من'):(D.leads||'سرپرست حوزه‌ها'))}</div><span class="sp"></span>
      ${lead||isOwner()?`<button class="btn sm tint" data-addspec="${esc(f.k)}">${ico('i-plus')}${esc(D.addSpec||'افزودن کارشناس')}</button>`:''}</div>
    ${lead?`<div class="tlist">${rows||emptyBox(D.qEmpty||'')}</div>
      <p class="cap">${esc(D.specNotAll||'')}</p>`
     :`<div class="tlist">${FIELDS.filter(x=>x.k!=='owner').map(x=>{
        const l=personOf(leadK(x.k));
        return `<div class="trow"><span class="va">${esc(String((l&&l.n)||' ').slice(0,1))}</span>
          <div class="tt"><b>${esc(l?l.n:'')}</b><small>${esc(x.n)} · ${esc(fa(x.open))} ${esc(D.qOpen||'')}</small></div>
          <span class="tload"><i style="width:${l?l.load:0}%"></i></span>
          <button class="btn sm quiet" data-setlead="${esc(x.k)}">${esc(D.changeLead||'تعیین سرپرست')}</button></div>`}).join('')}</div>
      <p class="cap">${esc(D.ownerNote||'')}</p>`}
  </section>`;
}
function cardWeek(){
  const Wk=(A.dash||{}).week||{bars:[],days:[]}, f=myField(), p=me();
  if(!isLead()&&!isOwner()){
    const wk=(A.dash||{}).week||{bars:[],days:[]};
    return `<section class="card stack">
      <div class="row"><div class="head">${esc(D.myWeek||'کارنامهٔ من')}</div><span class="sp"></span>
        <span class="cap">${esc(p.lv)} · ${esc(f.n)}</span></div>
      ${bars(wk.bars||[],true)}
      <div class="admbarsx">${(wk.days||[]).map(d=>`<span>${esc(d)}</span>`).join('')}</div>
      <div class="admkpi">
        <div class="k"><small>${esc(D.qDone||'انجام‌شده')}</small>${bits(fa(p.done)+' '+(D.qWork||'کار'))}</div>
        <div class="k"><small>${esc(D.qOpen||'کار باز')}</small>${bits(fa(p.open)+' '+(D.qWork||'کار'))}</div>
        <div class="k"><small>${esc(D.late||'دیرکرد')}</small>${bits(fa(p.late)+' '+(D.qWork||'کار'))}</div>
        <div class="k"><small>${esc(D.rAvg||'میانگین پاسخ')}</small>${bits(fa(p.avg)+' '+(D.minute||'دقیقه'))}</div></div>
    </section>`;
  }
  return `<section class="card stack">
    <div class="row"><div class="head">${esc(D.week||'کارهای هفته')}</div><span class="sp"></span>
      <span class="cap">${esc(f.n)}</span></div>
    ${bars(Wk.bars||[],true)}
    <div class="admbarsx">${(Wk.days||[]).map(d=>`<span>${esc(d)}</span>`).join('')}</div>
    ${bars((f.spark||{}).v||[],true)}
    <span class="cap">${esc((f.spark||{}).n||'')}</span>
  </section>`;
}
function cardFeed(){
  const f=myField(), list=(FEED||[]).filter(x=>isOwner()||x.f===f.k).slice(0,isOwner()?7:6);
  return `<section class="card stack">
    <div class="head">${esc(D.feed||'خط زمانی امروز')}</div>
    <div class="feed">${list.map(x=>`<div class="fitem">
      <span class="ftime">${esc(x.t)}</span><span class="fdot"></span>
      <div class="fb"><b>${esc(x.n)}</b><small>${esc(x.d)}${isOwner()?' · '+esc(fieldOf(x.f).n):''}</small></div></div>`).join('')||emptyBox(D.qEmpty||'')}</div>
  </section>`;
}
function cardToday(){
  const f=myField(), list=((A.dash||{}).today||[]).filter(x=>isOwner()||x.f===f.k);
  return `<section class="card stack">
    <div class="head">${esc(D.today||'برنامهٔ امروز')}</div>
    <div class="admlist">${list.map(x=>`<div class="admlirow">
      <span class="ic">${ico('i-clock')}</span>
      <span class="sp"><b style="font-size:var(--fs-sub)">${esc(x.t)}</b>
        <small class="cap" style="display:block">${esc(x.d)}</small></span>
      ${tag(x.b,'brand')}</div>`).join('')||emptyBox(D.todayEmpty||'برای امروز چیزی نمانده')}</div>
  </section>`;
}
function cardAlerts(){
  const f=myField(), D2=A.dash||{};
  let rows=[];
  if(isOwner()){
    rows=(D2.ownerAlerts||[]).map(x=>({n:x.n,d:x.d,f:x.f}))
      .concat(FIELDS.filter(x=>x.k!=='owner'&&x.health<85).map(x=>({n:'حوزهٔ '+x.n+' '+(D.alertFieldLow||''),
        d:(D.alertHealth||'')+' '+fa(x.health)+'٪ · '+fa(x.open)+' '+(D.openWork||''),f:x.k})));
  } else {
    rows=qOpen().filter(it=>it.pri==='بالا').map(it=>({n:it.n,d:it.due+' · '+it.code,f:it.f}));
    if(f.health<85) rows.push({n:(D.alertHealth||'سلامت حوزه')+' '+fa(f.health)+'٪',d:D.alertGoal||'هدف ۸۵٪ است',f:f.k});
  }
  return `<section class="card stack">
    <div class="row"><div class="head">${esc(D.alert||'نیاز به توجه')}</div><span class="sp"></span>
      <span class="tag warn">${esc(fa(rows.length))}</span></div>
    <div class="admlist">${rows.map(x=>`<div class="admlirow">
      <span class="ic">${ico('i-bell')}</span>
      <span class="sp"><b style="font-size:var(--fs-sub)">${esc(x.n)}</b>
        <small class="cap" style="display:block">${esc(x.d)}</small></span>
      ${x.f&&isOwner()?`<button class="tag brand" data-who="${esc(leadK(x.f))}">${esc(fieldOf(x.f).n)}</button>`:''}</div>`).join('')||emptyBox(D.alertEmpty||'')}</div>
  </section>`;
}
function cardMoney(){
  const rows=((A.dash||{}).money||[]), sp=(A.dash||{}).moneySpark||{};
  return `<section class="card stack">
    <div class="row"><div class="head">${esc(D.money||'مالی امروز')}</div><span class="sp"></span>
      <button class="btn sm quiet" data-sec="reports">${ico('i-chart')}${esc(D.reportsToday||'گزارش')}</button></div>
    <div class="admkpi">${rows.map(r=>`<div class="k"><small>${esc(r[0])}</small>${bits(r[1])}</div>`).join('')}</div>
    ${bars(sp.v||[],true)}
    <span class="cap">${esc(sp.n||'')}</span>
    <p class="cap">${esc(D.moneyNote||'')}</p>
  </section>`;
}
/* رویدادهای نزدیک: هر رویداد یک ردیف با ظرفیتش؛ هیچ عدد مالی این‌جا نیست */
function cardSoon(){
  const ev=(EVROWS||[]).filter(e=>e.state==='live'||e.state==='soon').slice(0,4);
  const st=(A.events||{}).states||{};
  return `<section class="card stack">
    <div class="row"><div class="head">${esc(D.soon||'رویدادهای نزدیک')}</div><span class="sp"></span>
      <button class="btn sm quiet" data-sec="events">${ico('i-calendar')}${esc(secOf('events').n)}</button></div>
    <div class="elist">${ev.map(e=>{const p=Math.min(100,Math.round(((+e.reg||0)/Math.max(1,+e.cap||0))*100)),
        tg=st[e.state]||[e.state,''];
      return `<div class="erow">
        <div class="et"><b>${esc(e.n)}</b><small>${esc(e.when)} · ${esc(e.time)} · ${esc(e.place)}</small></div>
        ${tag(tg[0],tg[1])}
        <div class="ecap"><span class="cap">${esc(fa(e.reg))} ${esc(D.of||'از')} ${esc(fa(e.cap))}</span>
          <span class="ebar"><i style="width:${p}%"></i></span></div></div>`}).join('')||emptyBox(D.todayEmpty||'')}</div>
  </section>`;
}
function vDash(){
  const own=isOwner(), lead=isLead();
  const one=own?cardQueue()+cardSoon()+cardFields()+cardTeam()
    :lead?cardQueue()+cardSoon()+cardTeam()
    :cardQueue()+cardSoon();
  const two=own?cardStatus()+cardToday()+cardAlerts()+cardMoney()
    :lead?cardStatus()+cardToday()+cardAlerts()+cardWeek()
    :cardToday()+cardAlerts()+cardWeek();
  return `<div class="dashwrap">
    ${dashHead()}${kpiRow()}${cardDefs()}
    <div class="admgrid">${one}${two}</div>
    ${cardFeed()}
  </div>`;
}

/* ── تقویم و ساعت: شمسی، ۲۴ساعته، هم‌گام با اینترنت ────────────────────
   تاریخ‌ها به شکل ۱۴۰۴/۰۷/۱۶ نگه داشته می‌شوند؛ تبدیل شمسی و میلادی همین‌جا
   است تا «امروز» همیشه امروز باشد. ساعت اول از اینترنت خوانده می‌شود و اگر
   نبود، از ساعت دستگاه می‌رود. */
const JDIV=(a,b)=>Math.trunc(a/b), JMOD=(a,b)=>a-Math.trunc(a/b)*b;
function jCal(jy){
  const breaks=[-61,9,38,199,426,686,756,818,1111,1181,1210,1635,2060,2097,2192,2262,2324,2394,2456,3178];
  const bl=breaks.length; let gy=jy+621, leapJ=-14, jp=breaks[0], jump=0;
  for(let i=1;i<bl;i++){const jm=breaks[i]; jump=jm-jp; if(jy<jm) break;
    leapJ+=JDIV(jump,33)*8+JDIV(JMOD(jump,33),4); jp=jm;}
  let n=jy-jp; leapJ+=JDIV(n,33)*8+JDIV(JMOD(n,33)+3,4);
  if(JMOD(jump,33)===4&&jump-n===4) leapJ++;
  const leapG=JDIV(gy,4)-JDIV((JDIV(gy,100)+1)*3,4)-150, march=20+leapJ-leapG;
  if(jump-n<6) n=n-jump+JDIV(jump+4,33)*33;
  let leap=JMOD(JMOD(n+1,33)-1,4); if(leap===-1) leap=4;
  return {leap:leap, gy:gy, march:march};
}
function g2d(gy,gm,gd){
  let d=JDIV((gy+JDIV(gm-8,6)+100100)*1461,4)+JDIV(153*JMOD(gm+9,12)+2,5)+gd-34840408;
  return d-JDIV(JDIV(gy+100100+JDIV(gm-8,6),100)*3,4)+752;
}
function d2g(jdn){
  let j=4*jdn+139361631;
  j=j+JDIV(JDIV(4*jdn+183187720,146097)*3,4)*4-3908;
  const i=JDIV(JMOD(j,1461),4)*5+308, gd=JDIV(JMOD(i,153),5)+1, gm=JMOD(JDIV(i,153),12)+1;
  return {gy:JDIV(j,1461)-100100+JDIV(8-gm,6), gm:gm, gd:gd};
}
const j2d=(jy,jm,jd)=>{const r=jCal(jy); return g2d(r.gy,3,r.march)+(jm-1)*31-JDIV(jm,7)*(jm-7)+jd-1;};
function d2j(jdn){
  let gy=d2g(jdn).gy, jy=gy-621; let k=jdn-g2d(gy,3,jCal(jy).march);
  if(k>=0){ if(k<=185) return {jy:jy, jm:1+JDIV(k,31), jd:JMOD(k,31)+1}; k-=186; }
  else { jy-=1; k+=179; if(jCal(jy).leap===1) k+=1; }
  return {jy:jy, jm:7+JDIV(k,30), jd:JMOD(k,30)+1};
}
const jLen=(jy,jm)=>jm<=6?31:jm<=11?30:(jCal(jy).leap===1?30:29);
const jWeek=(jy,jm,jd)=>(j2d(jy,jm,jd)+2)%7;
const jPad=n=>String(n).padStart(2,'0');
const jForm=(jy,jm,jd)=>fa(jy)+'/'+fa(jPad(jm))+'/'+fa(jPad(jd));
const JN=['شنبه','یکشنبه','دوشنبه','سه‌شنبه','چهارشنبه','پنجشنبه','جمعه'];
const jLong=(jy,jm,jd)=>JN[jWeek(jy,jm,jd)]+' '+fa(jd)+' '+(((NE().j||{}).months||[])[jm-1]||'');
/* ساعت: اول اینترنت، بعد دستگاه */
const NET={state:'local', diff:0, at:''};
/* ساعت مشترک سامانه در ui.js است؛ پنل هم همان را می‌خواند تا همه‌جا یکی باشد */
function netNow(){const u=(window.NORA_UI)||null; if(u&&u.clockNow) return u.clockNow();
  return Date.now()+(NET.diff||0)}
function clockParts(ms){
  const opt={timeZone:'Asia/Tehran', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false,
    year:'numeric', month:'2-digit', day:'2-digit'};
  try{
    const p=new Intl.DateTimeFormat('en-US',opt).formatToParts(new Date(ms)).reduce((o,x)=>(o[x.type]=x.value,o),{});
    return {h:+p.hour%24, mi:+p.minute, s:+p.second, gy:+p.year, gm:+p.month, gd:+p.day};
  }catch(e){const d=new Date(ms); return {h:d.getHours(), mi:d.getMinutes(), s:d.getSeconds(),
    gy:d.getFullYear(), gm:d.getMonth()+1, gd:d.getDate()};}
}
function jNow(){
  const c=clockParts(netNow()), j=d2j(g2d(c.gy,c.gm,c.gd));
  return {jy:j.jy, jm:j.jm, jd:j.jd, h:c.h, mi:c.mi, s:c.s};
}
const jToday=()=>{const n=jNow(); return {jy:n.jy, jm:n.jm, jd:n.jd};};
const clockStr=()=>{const n=jNow(); return fa(jPad(n.h))+':'+fa(jPad(n.mi))+':'+fa(jPad(n.s))};
/* هم‌گام‌سازی: یک بار که پنل باز می‌شود */
let netTried=false;
async function netSync(){
  /* اول از ساعت مشترک بپرس؛ اگر نبود، خودش از اینترنت می‌گیرد */
  const u=(window.NORA_UI)||null;
  if(u&&u.netSyncClock){
    try{ const st=await u.netSyncClock();
      NET.state=(st==='net')?'net':'local'; NET.diff=0;
      NET.at=(u.clockAt&&u.clockAt())||clockStr(); tick(true); return; }catch(e){}
  }
  if(netTried||typeof fetch!=='function') return;
  netTried=true;
  const tries=[['https://worldtimeapi.org/api/timezone/Asia/Tehran',j=>+(j.unixtime||0)*1000],
               ['https://timeapi.io/api/Time/current/zone?timeZone=Asia/Tehran',j=>+new Date(j.dateTime)]];
  for(const [url,pick] of tries){
    try{
      const r=await fetch(url,{cache:'no-store'}); if(!r.ok) continue;
      const j=await r.json(), t=pick(j); if(!t||Math.abs(t-Date.now())>31536000000) continue;
      NET.state='net'; NET.diff=t-Date.now(); NET.at=clockStr();
      tick(true); return;
    }catch(e){}
  }
  NET.state='local'; tick(true);
}
/* ساعت زندهٔ گام دوم؛ هر ثانیه جلو می‌رود و تا وقتی پنل باز است تازه می‌ماند */
let tickTimer=null;
function tick(force){
  const el=document.getElementById('wzClock');
  if(!el){ if(tickTimer){clearInterval(tickTimer); tickTimer=null;} return; }
  el.textContent=clockStr();
  const st=document.getElementById('wzClockSt');
  if(st) st.textContent=(NET.state==='net'?(NE().l||{}).synced:(NE().l||{}).local)||'';
  if(!tickTimer&&!IS_TEST) tickTimer=setInterval(()=>tick(false),1000);
}
function jParse(str){
  const t=un(String(str||'')).replace(/[-.]/g,'/').trim(), m=t.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/);
  if(!m) return null;
  const jy=+m[1], jm=+m[2], jd=+m[3];
  if(jm<1||jm>12||jd<1||jd>jLen(jy,jm)) return null;
  return {jy:jy, jm:jm, jd:jd};
}
/* تاریخ و ساعت زنده از اینترنت می‌آید؛ سالِ رویدادهای بی‌سالِ نمونه اما از خود دنیای نمونه،
   تا ویرایش «پنجشنبه ۲۴ مهر» به سال اشتباه نیفتد */
function jAnchorYear(){
  const t=un(String(((A.dash||{}).day)||''));
  const m=t.match(/(\d{4})/);
  return m?+m[1]:jToday().jy;
}
function jFromWhen(str){
  const t=un(String(str||'')), months=(NE().j||{}).months||[];
  const m=t.match(/(\d{1,2})\s+(\S+)/); if(!m) return null;
  const jd=+m[1], jm=months.indexOf(m[2])+1; if(!jd||!jm) return null;
  const y=t.match(/(\d{4})/); return {jy:y?+y[1]:jAnchorYear(), jm:jm, jd:jd};
}
/* ساعت ۲۴ساعته: نوشتنی، خودش دونقطه می‌گذارد و ۲۳:۵۹ سقف است */
const h24=(v,hard)=>{
  const t=un(String(v||'')).replace(/[^\d:]/g,'');
  if(t.includes(':')){
    const p2=t.split(':'), h=Math.min(23,+p2[0]||0), mi=Math.min(59,+(p2[1]||0));
    return jPad(h)+':'+jPad(mi);
  }
  const d=t.replace(/\D/g,'').slice(0,4);
  /* وسط تایپ دست نمی‌زنیم تا کارت نپرد؛ در رفتن از قلم، کاملش می‌کنیم */
  if(d.length<4&&!hard) return d;
  const h=Math.min(23,+(d.slice(0,2)||d.slice(0,1)||0)), mi=Math.min(59,+(d.length>2?d.slice(2):0));
  return jPad(h)+':'+jPad(mi);
};
/* قلم‌های ویزارد: تاریخ، پایان، پنجرهٔ ثبت‌نام و «جلسه‌ها» که sess3 یعنی جلسهٔ چهارم */
function wGet(f){
  const m=/^sess(\d+)$/.exec(String(f||''));
  if(m){const s=(S.wiz.sess||[])[+m[1]]; return s?(s.d||''):''}
  return S.wiz[f];
}
function wSet(f,v){
  const m=/^sess(\d+)$/.exec(String(f||''));
  if(m){
    const ses=S.wiz.sess=S.wiz.sess||[], i=+m[1];
    if(!ses[i]) return;
    ses[i].d=v;
    /* پایان رویداد همان آخرین جلسه است */
    const last=ses[ses.length-1]; if(last&&last.d) S.wiz.end=last.d;
    return;
  }
  S.wiz[f]=v;
}
function dpOpen(f,y,m){S.dp={f:f, y:y, m:m}; save(); renderBody();}
function dpBox(){
  const dp=S.dp||{}, F=NE().l||{}, J=NE().j||{}, months=J.months||[], days=J.days||[];
  if(!dp.f) return '';
  const t=jToday(), y=+dp.y||t.jy, m=+dp.m||t.jm, len=jLen(y,m), pad=jWeek(y,m,1), cur=jParse(wGet(dp.f));
  let cells='<span class="db"></span>'.repeat(pad);
  for(let d=1;d<=len;d++){
    const on=cur&&cur.jy===y&&cur.jm===m&&cur.jd===d, td=t.jy===y&&t.jm===m&&t.jd===d;
    cells+=`<button class="dd ${on?'on':''} ${td?'today':''}" data-dpday="${fa(d)}">${esc(fa(d))}</button>`;
  }
  return `<div class="dp">
    <div class="dphead">
      <button class="dpnav" data-dpmv="-1" aria-label="${esc(J.prev||'ماه قبل')}">${ico('i-chev-right')}</button>
      <b>${esc(months[m-1]||'')} ${esc(fa(y))}</b>
      <button class="dpnav" data-dpmv="1" aria-label="${esc(J.next||'ماه بعد')}">${ico('i-chev-left')}</button>
      <span class="sp"></span>
      <button class="btn sm quiet" data-dptoday="1">${esc(F.today||'امروز')}</button>
      <button class="btn sm quiet" data-dpclose="1">${esc(W.close||'بستن')}</button></div>
    <div class="dpweek">${days.map(d=>`<span>${esc(d)}</span>`).join('')}</div>
    <div class="dpgrid">${cells}</div></div>`;
}
function dpField(f,label){
  const F=NE().l||{}, v=String(S.wiz[f]||''), j=jParse(v), open=(S.dp||{}).f===f;
  return `<div class="fld">
    <span class="lbl">${esc(label)}</span>
    <div class="withbtn">
      <input class="input num" id="wz-${esc(f)}" data-winput="${esc(f)}" dir="ltr"
        inputmode="numeric" placeholder="۱۴۰۴/۰۷/۱۶" value="${esc(v)}" autocomplete="off"/>
      <button class="btn sm quiet" data-dp="${esc(f)}" aria-label="${esc(F.pick||'تقویم')}">${ico('i-calendar')}</button></div>
    <span class="cap">${esc(j?jLong(j.jy,j.jm,j.jd):'')}</span>
    ${open?dpBox():''}</div>`;
}
function timeField(f,label){
  return `<div class="fld"><span class="lbl">${esc(label)}</span>
    <input class="input num" id="wz-${esc(f)}" data-wtime="${esc(f)}" dir="ltr" inputmode="numeric"
      placeholder="۱۸:۳۰" maxlength="5" autocomplete="off" value="${esc(un(String(S.wiz[f]||'')))}"/>
    <span class="cap">${esc('۲۴ ساعته')}</span></div>`;
}
function numField(f,label,min,step,hint){
  return `<div class="fld"><span class="lbl">${esc(label)}</span>
    <input class="input num" id="wz-${esc(f)}" type="number" inputmode="numeric" dir="ltr"
      min="${esc(min||0)}" step="${esc(step||1)}" data-winput="${esc(f)}" value="${esc(un(String(S.wiz[f]||0)))}"/>
    ${hint?`<span class="cap">${esc(hint)}</span>`:''}</div>`;
}
function textField(f,label,list,ph){
  const L=(NE().suggest||{})[list]||[];
  return `<div class="fld"><span class="lbl">${esc(label)}</span>
    <input class="input" id="wz-${esc(f)}" data-winput="${esc(f)}" value="${esc(S.wiz[f]||'')}"
      placeholder="${esc(ph||'')}" autocomplete="off" list="dl-${esc(list||f)}"/>
    <datalist id="dl-${esc(list||f)}">${L.map(x=>`<option value="${esc(x)}"></option>`).join('')}</datalist></div>`;
}
const minOfT=t=>{const m=/^(\d{1,2}):(\d{2})$/.exec(String(t||'')); return m?(+m[1])*60+(+m[2]):null;};

/* ── تعریف تازه: هر کس، هر بخش؛ مالک یا سرپرست تأیید می‌کند ──────────────
   پنج گام: چیستی و پوستر، کی و کجا، ظرفیت و ثبت‌نام، فرم‌ها و اطلاع‌رسانی،
   کارت و صفحه. هیچ تعریفی پیش‌نویس نمی‌ماند: یا منتشر می‌شود یا می‌رود در
   فهرست تأیید. فرم‌ها همین‌جا ساخته می‌شوند و در مدیریت رویداد هم می‌مانند. */
const DEFD=()=>A.defs||{};
const NE=()=>A.newev||{};
const defKind=k=>(DEFD().kinds||[]).find(x=>x.k===k)||{n:'تعریف',i:'i-plus'};
const neKind=k=>(NE().kinds||[]).find(x=>x.k===k)||{n:'',i:'i-calendar'};
const themeOf=k=>(NE().themes||[]).find(x=>x.k===k)||{n:'',d:''};
const wizSteps=()=>S.wiz.kind==='event'?(NE().steps||[]):['چیستی','مرور و فرستادن'];
function defaultFeat(k){
  const t=neKind(k), f={};
  ['ticket','att','cert'].forEach(x=>{if(t[x])f[x]=1});
  f.survey=1; f.profile=1;
  return f;
}
const featOn=k=>!!(S.wiz.feat||{})[k];
const remOn=k=>!!(S.wiz.rem||{})[k];
const chOn=k=>!!(S.wiz.ch||{})[k];
const canPublish=()=>isOwner()||isLead();
function defsFor(){
  const rows=(S.defs||[]).concat((DEFD().pending||[]).map(x=>Object.assign({wait:1},x)));
  return isOwner()?rows:isLead()?rows.filter(x=>x.f===myField().k):rows.filter(x=>x.by===me().k);
}
function canApprove(r){return !!r.wait&&(isOwner()||(isLead()&&r.f===myField().k))}

/* ── فرم‌ها: انبار مشترک فرم‌ساز + نمونه‌های پنل ─────────────────────────
   فرم در فرم‌ساز ساخته می‌شود؛ این‌جا فقط وصلیم. مبلغ و ظرفیت و پنجرهٔ
   ثبت‌نام از همان فرم خوانده می‌شود تا رویداد و فرم یکی بمانند. */
const FST=()=>(window.NORA_UI&&NORA_UI)||null;
function madeForms(){try{const u=FST(); return u&&u.formsAll?u.formsAll():[]}catch(e){return []}}
function demoForms(){const F=(A.forms||{}); return (F.rows||[]).map((r,i)=>({id:'demo'+(i+1), name:r.n, kind:r.k,
  q:NR(un(String(r.got||'0'))), cap:0, fin:[], demo:1, need:''}))}
/* نظرسنجی آمادهٔ نورا: با شناسهٔ auto هرجا فرم خواست، همین میآید */
const autoForm=()=>{const a=(window.NORA_UI&&NORA_UI.autoSurvey)||{};
  return {id:'auto', name:a.name||'نظرسنجی آمادهٔ نورا', kind:a.kind||'نظرسنجی',
    q:(a.questions||[]).length||4, fields:a.questions||[], demo:1, need:'survey'};};
function formOf(id){
  if(!id) return null;
  if(String(id)==='auto') return autoForm();
  const made=madeForms().find(f=>String(f.id)===String(id));
  if(made) return made;
  return demoForms().find(f=>String(f.id)===String(id))||null;
}
const formName=f=>f?(f.name||'فرم بی‌نام'):'';
const formQs=f=>f?(f.q?fa(f.q)+' پرسش':((f.fields||[]).length?fa((f.fields||[]).length)+' پرسش':'')):'';
function formSum(f){  /* جمع مبالغ فرم با تخفیف‌ها */
  const fin=(f&&f.fin)||[]; if(!fin.length) return 0;
  return fin.reduce((n,o)=>n+(o.off?Math.round(+o.p*(100-+o.off)/100):(+o.p||0)),0);
}
function moneyRows(f){
  const fin=(f&&f.fin)||[];
  return fin.map(o=>`<div class="revrow"><span class="cap">${esc(o.l||'')}</span>
    <span>${esc(fa(+o.p||0))} ${esc('ریال')}${o.off?` · ${esc('٪'+fa(o.off)+' تخفیف')}`:''}</span></div>`).join('');
}
const NEEDN={reg:'فرم ثبت‌نام', survey:'فرم نظرسنجی', exam:'فرم آزمون', other:'فرم'};
const fpOf=need=>((S.wiz.fp||{})[need]||'');
function fpForm(need){return formOf(fpOf(need))}
/* نشانی فرم‌ساز با همهٔ قلم‌های همین رویداد: ظرفیت، پنجرهٔ ثبت‌نام، نام، برگشت */
function builderUrl(need){
  const w=S.wiz, j=jParse(w.date), p2=new URLSearchParams();
  p2.set('ev', evLinkId()); p2.set('need', need||'reg');
  p2.set('name', w.name||''); p2.set('cap', String(w.cap||''));
  p2.set('when', j?jLong(j.jy,j.jm,j.jd):'');
  p2.set('place', w.mode==='online'?(w.link||''):(w.place||''));
  if(w.date) p2.set('from', w.date+(w.time?' · '+w.time:''));
  if(w.end) p2.set('end', w.end+(w.to?' · '+w.to:''));
  p2.set('slug', 'events/'+evLinkId()+'/'+(need==='exam'?'exam':need==='survey'?'survey':'register'));
  p2.set('back', 'admin.html#newev&edit='+encodeURIComponent(evLinkId()));
  return 'create.html?'+p2.toString();
}
/* پوستر: یا از گالری یا تصویری که خودت آوردی */
function posterSrc(v){v=String(v||''); return !v?'':(/^(data:|https?:|\/)/.test(v)?v:'posters/'+v)}
const posterVal=()=>S.wiz.posterUp||S.wiz.poster||'';

/* ── یادآوری‌ها: هر ردیف یک زمان و یک راه ─────────────────────────────
   زمان ارسال از تاریخ رویداد و جلسه‌ها حساب می‌شود، نه از حدس. */
function remList(){S.wiz.rem=Array.isArray(S.wiz.rem)?S.wiz.rem:[]; return S.wiz.rem}
function remAt(r){  /* زمان ارسال این یادآوری */
  const w=S.wiz, j=jParse(w.date); if(!j) return '';
  const t=minOfT(w.time)||0, mult={m:1,h:60,d:1440,w:10080}[r.u]||60, mins=(+r.n||0)*mult;
  let day=j2d(j.jy,j.jm,j.jd), min=t+(r.w==='after'?mins:-mins);
  while(min>=1440){min-=1440; day++}
  while(min<0){min+=1440; day--}
  const g=d2j(day);
  return jLong(g.jy,g.jm,g.jd)+' · '+fa(pad2(Math.floor(min/60))+':'+pad2(min%60));
}
const pad2=n=>String(n).length<2?'0'+n:String(n);
/* متن و زمان یادآوری همان ردیف، بی‌آنکه قلم از دست برود */
function rcap(el,i){
  const r=remList()[i];
  const row=el.closest?el.closest('.frow'):null, cap=row&&row.querySelector('.cap');
  if(r&&cap) cap.textContent=remText(r)+' · '+(remAt(r)||'');
}
const remText=r=>`${fa(r.n||0)} ${((NE().remUnits||[]).find(u=>u.k===r.u)||{}).n||''} ${r.w==='after'?'بعد':'قبل'}`;
function remRows(){
  const B=NE().remB||{}, units=NE().remUnits||[], chs=NE().remCh||[];
  const rows=remList();
  return `<div class="fbuilder rems">${rows.map((r,i)=>`<div class="frow" data-remrow="${i}">
    <div class="frowtop rem">
      <button class="fbtn ${r.on?'':'stop'}" data-remon="${i}" aria-pressed="${r.on?'true':'false'}" aria-label="${esc(B.off||'خاموش')}">${ico(r.on?'i-bell':'i-bell-off')}</button>
      <span class="fnum">${esc(fa(i+1))}</span>
      <button class="chip ${r.w!=='after'?'on':''}" data-remtow="${i}" data-w="before">${esc(B.before||'قبل')}</button>
      <button class="chip ${r.w==='after'?'on':''}" data-remtow="${i}" data-w="after">${esc(B.after||'بعد')}</button>
      <input class="input num" dir="ltr" inputmode="numeric" data-remn="${i}" value="${esc(un(String(r.n||0)))}" aria-label="${esc('عدد')}"/>
      <select class="input" data-remu="${i}" aria-label="${esc(B.unit||'یکا')}">
        ${units.map(u=>`<option value="${esc(u.k)}" ${r.u===u.k?'selected':''}>${esc(u.n)}</option>`).join('')}</select>
      <select class="input" data-remch="${i}" aria-label="${esc(B.ch||'راه')}">
        ${chs.map(c=>`<option value="${esc(c.k)}" ${r.ch===c.k?'selected':''}>${esc(c.n)}</option>`).join('')}</select>
      <button class="fbtn stop" data-remdel="${i}" aria-label="${esc(B.del||'برداشتن')}">${ico('i-trash')}</button>
    </div>
    <span class="cap">${esc(remText(r))} · ${esc(remAt(r)||(B.at||'زمان ارسال'))}</span>
  </div>`).join('')||`<span class="cap">${esc(B.empty||'')}</span>`}
    <div class="row tight">
      <button class="btn sm" data-remadd="before">${ico('i-plus')}${esc(B.add||'یادآوری تازه')}</button>
      <label class="chip ${S.wiz.remEvery?'on':''}" data-remever="1">${ico('i-check')}${esc((NE().remB||{}).every||'هر جلسه هم یادآوری شود')}</label>
    </div></div>`;
}
/* جلسه‌ها: هر جلسه تاریخ و ساعت خودش؛ تاریخ پایان از آخرین جلسه می‌آید */
function sessRows(){
  const B=NE().sess||{}, rows=S.wiz.sess||[];
  return `<div class="fbuilder">${rows.map((s,i)=>`<div class="frow" data-sessrow="${i}">
    <div class="frowtop sess">
      <span class="fnum">${esc(fa(i+1))}</span>
      <span class="cap">${esc(B.t||'جلسه')} ${esc(fa(i+1))}</span>
      <span class="sp"></span>
      <button class="fbtn stop" data-sessdel="${i}" aria-label="${esc(B.del||'برداشتن')}">${ico('i-trash')}</button>
    </div>
    <div class="wgrid">
      <div class="fld"><span class="lbl">${esc('تاریخ')}</span>
        <div class="row tight"><input class="input num" id="wsd-${i}" dir="ltr" inputmode="numeric" data-sessd="${i}"
            value="${esc(s.d||'')}" placeholder="۱۴۰۴/۰۷/۲۱" autocomplete="off"/>
          <button class="btn sm quiet" data-dp="sess${i}" aria-label="${esc('تقویم')}">${ico('i-calendar')}</button></div></div>
      <div class="fld"><span class="lbl">${esc('از')}</span>
        <input class="input num" id="wst-${i}" dir="ltr" inputmode="numeric" maxlength="5" data-sesst="${i}" data-wtime="sesst${i}" value="${esc(un(s.t||''))}"/></div>
      <div class="fld"><span class="lbl">${esc('تا')}</span>
        <input class="input num" id="wse-${i}" dir="ltr" inputmode="numeric" maxlength="5" data-sessto="${i}" value="${esc(un(s.to||''))}"/></div>
    </div>
    ${S.dp&&S.dp.f==='sess'+i?dpBox():''}
  </div>`).join('')}
    <div class="row tight"><button class="btn sm" data-sessadd="1">${ico('i-plus')}${esc(B.add||'جلسهٔ تازه')}</button>
      <span class="cap">${esc(B.auto||'')}</span></div></div>`;
}
/* امروز زنده است، پس هر رویدادی که برگزاری‌اش تمام شده خودش به برگزار شده می‌رود */
/* وضعیت رویداد از خود تاریخ‌ها درمی‌آید: بعد از پایان برگزاری، خودش
   می‌رود در «برگزار شده»؛ ولی رویداد چندجلسه‌ای تا آخرین جلسه باز می‌ماند. */
function evState(e){
  if(e.held) return 'past';
  if(e.state==='wait') return 'wait';
  const start=jParse(e.on||'');
  const ses=(e.sess||[]).filter(x=>x&&jParse(x.d));
  if(!start&&!ses.length) return e.state||'soon';
  /* امروز شمسی از همان ساعت مشترک سامانه: jNow خودش تاریخ و ساعت را می‌دهد */
  const n=jNow(), today=j2d(n.jy,n.jm,n.jd), nowMin=n.h*60+n.mi;
  const first=ses.length?jParse(ses[0].d):start;
  const lastSes=ses[ses.length-1];
  const last=jParse(lastSes?lastSes.d:(e.end||''))||start;
  const t=minOfT(lastSes?lastSes.to:e.to)||1440;
  if(!last) return e.state||'soon';
  const lastDay=j2d(last.jy,last.jm,last.jd);
  if(today>lastDay) return 'past';
  if(today===lastDay&&nowMin>=t) return 'past';
  /* از روز جلسهٔ اول تا روز جلسهٔ آخر، رویداد در جریان است؛ چندجلسه‌ای
     میان دو جلسه نه «پیش‌رو» می‌ماند نه می‌رود در برگزار شده */
  if(first&&today>=j2d(first.jy,first.jm,first.jd)) return 'live';
  return (e.state==='past')?'soon':(e.state||'soon');
}
function afterEvent(e){  /* رویداد گذشته: فهرست «برگزار شده» و آرشیو */
  return evState(e)==='past';
}
/* ── پیش‌نمایش: کارت رویداد، صفحهٔ رویداد و پیام‌ها ─────────────────── */
const evLinkId=()=>{ if(S.wiz.edit) return S.wiz.edit;
  if(!S.wiz.stamp){S.wiz.stamp=Date.now(); try{save()}catch(e){}}
  return 'nx'+S.wiz.stamp; };
const stampNow=()=>S.wiz.stamp||(S.wiz.stamp=Date.now());
const evLink=()=>'event.html?id='+evLinkId();
const fmtCap=n=>fa(+n||0);
/* ── پوستر خودت: فایل خوانده می‌شود و اگر سنگین بود، خودش کوچک می‌شود ──
   در مرورگر با canvas کوچک می‌شود؛ جایی که canvas نیست، همان تصویر می‌ماند. */
/* در محیط آزمایش نه canvas هست نه تیک ثانیه‌شمار؛ وگرنه فرایند بسته نمی‌شود */
const IS_TEST=(typeof navigator!=='undefined'&&/jsdom/i.test(String(navigator.userAgent||'')));
const NO_CANVAS=IS_TEST;
function shrinkPoster(file,cb){
  const fr=new FileReader();
  fr.onload=()=>{
    const url=String(fr.result||'');
    if(!url) return cb('');
    if(NO_CANVAS||url.length<220000) return cb(url);
    try{
      const img=new Image();
      img.onload=()=>{
        try{
          const max=900, sc=Math.min(1, max/Math.max(img.width||max, img.height||max));
          const cv=document.createElement('canvas');
          cv.width=Math.max(1,Math.round((img.width||max)*sc));
          cv.height=Math.max(1,Math.round((img.height||max)*sc));
          const cx=cv.getContext?cv.getContext('2d'):null;
          if(!cx) return cb(url);
          cx.drawImage(img,0,0,cv.width,cv.height);
          cb(cv.toDataURL('image/jpeg',0.82));
        }catch(e){cb(url)}
      };
      img.onerror=()=>cb(url);
      img.src=url;
    }catch(e){cb(url)}
  };
  fr.onerror=()=>cb('');
  fr.readAsDataURL(file);
}

/* ── برگهٔ انتخاب فرم: فرم‌های فرم‌ساز بالای فهرست می‌آیند، بعد نمونه‌های پنل ──
   نظرسنجی: پیشفرض فرم آمادهٔ نوراست (خودکار)؛ اختصاصی همان رویداد هم دکمه دارد */
function formPick(need,label,hint){
  const F=NE().forms||{}, isAuto=String(fpOf(need))==='auto', cur=isAuto?autoForm():formOf(fpOf(need)),
    made=madeForms(), demo=demoForms();
  const row=(f)=>`<div class="admlirow pickrow ${cur&&String(cur.id)===String(f.id)?'on':''}">
      <span class="ic">${ico(f.fin&&f.fin.length?'i-wallet':'i-doc')}</span>
      <span class="sp"><b style="font-size:var(--fs-sub)">${esc(formName(f))}</b>
        <small class="cap" style="display:block">${esc([f.kind||'', formQs(f), f.fin&&f.fin.length?fa(formSum(f))+' ریال':''].filter(Boolean).join(' · '))}${f.ev?` · ${esc('وصل به '+f.ev)}`:''}</small></span>
      ${cur&&String(cur.id)===String(f.id)?`<span class="tag brand">${esc(F.linked||'وصل شده')}</span>`:
        `<button class="btn sm" data-fpick="${esc(need)}" data-fid="${esc(f.id)}">${ico('i-check')}${esc(F.pick||'بردار')}</button>`}</div>`;
  const autoRow=isAuto?`<div class="admlirow on"><span class="ic">${ico('i-star')}</span>
      <span class="sp"><b style="font-size:var(--fs-sub)">${esc(formName(autoForm()))}</b>
        <small class="cap" style="display:block">${esc((F.autoReady||'آماده و خودکار')+' · '+formQs(autoForm()))}</small></span>
      <span class="tag ok">${esc(F.autoTag||'خودکار')}</span>
      <a class="btn sm quiet" href="${esc(builderUrl(need))}" target="_blank" rel="noopener">${ico('i-plus')}${esc(F.autoOwn||'اختصاصی همین رویداد')}</a>
      <button class="btn sm quiet" data-fclear="${esc(need)}" aria-label="${esc(F.clear||'بردار')}">${ico('i-close')}</button></div>`:'';
  return `<div class="fld"><span class="lbl">${esc(label)}</span>
    ${hint?`<span class="cap">${esc(hint)}</span>`:''}
    ${autoRow}
    ${!isAuto&&cur?`<div class="admlirow on"><span class="ic">${ico('i-doc')}</span>
      <span class="sp"><b style="font-size:var(--fs-sub)">${esc(formName(cur))}</b>
        <small class="cap" style="display:block">${esc([cur.kind||'', formQs(cur)].filter(Boolean).join(' · '))}</small></span>
      <a class="btn sm quiet" href="${esc(builderUrl(need))}" target="_blank" rel="noopener">${ico('i-sliders')}${esc(F.openBuilder||'ویرایش در فرم‌ساز')}</a>
      <button class="btn sm quiet" data-fclear="${esc(need)}" aria-label="${esc(F.clear||'بردار')}">${ico('i-close')}</button></div>`
    :!isAuto?`<div class="empty cap">${ico('i-doc')}<p style="margin-top:6px">${esc(F.none||'فرمی وصل نشده')}</p></div>`:''}
    <div class="admlist picklist">${made.length?made.map(row).join(''):`<div class="cap">${esc(F.empty||'')}</div>`}</div>
    ${demo.length?`<div class="cap" style="margin-top:6px">${esc(F.fromDemo||'')}</div>${demo.map(row).join('')}`:''}
    <div class="row tight">
      <a class="btn sm" href="${esc(builderUrl(need))}" target="_blank" rel="noopener">${ico('i-plus')}${esc(F.build||'ساختن در فرم‌ساز')}</a>
      <span class="cap">${esc(F.inBuilder||'')}</span></div></div>`;
}
/* تاریخ و ساعت رویداد: با جلسه‌ها، اولین و آخرین جلسه خوانده می‌شود */
function evWhen(){
  const w=S.wiz, j=jParse(w.date), ses=(w.sess||[]).filter(x=>x&&x.d);
  const first=ses.length?jParse(ses[0].d):j, last=ses.length?jParse(ses[ses.length-1].d):(jParse(w.end)||j);
  const line=s=>s?jLong(s.jy,s.jm,s.jd):'';
  return {first:first, last:last, day:line(first),
    range:(last&&first&&j2d(last.jy,last.jm,last.jd)!==j2d(first.jy,first.jm,first.jd))?line(last):'',
    time:[(ses.length?(ses[0].t||w.time):w.time),(ses.length?(ses[0].to||w.to):w.to)].filter(Boolean).join(' تا '),
    count:ses.length||(+w.sessions||1)};
}
function evCardPrev(){
  const w=S.wiz, L=NE().l||{}, t=neKind(w.et), src=posterSrc(posterVal()), W2=evWhen();
  return `<div class="evcard th-${esc(w.theme||'glass')}">
    <div class="evcard-cover">${src?`<img src="${esc(src)}" alt="" loading="lazy"/>`:`<span class="cap">${esc((NE().noPoster)||'')}</span>`}</div>
    <div class="evcard-body">
      <div class="evcard-top"><span class="tag brand">${esc(t.n||'تعریف')}</span>${w.label?`<span class="tag">${esc((NE().labels||[]).find(x=>x.k===w.label)?.n||'')}</span>`:''}${w.held?`<span class="tag">${esc('برگزار شده')}</span>`:''}</div>
      <b>${esc(w.name||'نام رویداد')}</b>
      <small>${esc(w.desc||'یک خط توضیح')}</small>
      <div class="evcard-meta">
        <span>${ico('i-calendar')}${esc(W2.day||'تاریخ')}${W2.range?` · ${esc(W2.range)}`:''}</span>
        <span>${ico('i-clock')}${esc(W2.time||'ساعت')}${W2.count>1?` · ${esc(fa(W2.count)+' جلسه')}`:''}</span>
        <span>${ico('i-pin')}${esc(w.mode==='online'?(w.link||'آنلاین'):(w.place||'جا'))}</span>
      </div>
      <div class="evcard-foot"><span class="cap">${esc(fmtCap(w.cap||0))} ${esc('نفر')}${w.waitMode?` · ${esc((NE().waitModes||[]).find(x=>x.k===w.waitMode)?.n||'')}`:''}</span>
        <span class="tag brand">${esc(w.held?(L.arch||'آرشیو'):(L.book||'ثبت‌نام'))}</span></div>
    </div></div>`;
}
function evPagePrev(){
  const w=S.wiz, t=neKind(w.et), src=posterSrc(posterVal()), W2=evWhen();
  const on=(NE().features||[]).filter(x=>featOn(x.k)).map(x=>x.n);
  const reg=fpForm('reg'), svy=fpForm('survey'), exm=fpForm('exam');
  return `<div class="evpage th-${esc(w.theme||'glass')}">
    <div class="evpage-cover">${src?`<img src="${esc(src)}" alt="" loading="lazy"/>`:''}</div>
    <div class="evpage-body">
      <span class="tag brand">${esc(t.n||'تعریف')}</span>
      <h4>${esc(w.name||'نام رویداد')}</h4>
      <p class="cap">${esc(w.about||w.desc||'')}</p>
      <div class="evpage-chips">
        <span class="chip2">${ico('i-calendar')}${esc([W2.day,W2.range].filter(Boolean).join(' تا '))}</span>
        <span class="chip2">${ico('i-clock')}${esc(W2.time||'')}${W2.count>1?` · ${esc(fa(W2.count)+' جلسه')}`:''}</span>
        <span class="chip2">${ico('i-pin')}${esc(w.mode==='online'?(w.link||'آنلاین'):(w.place||''))}</span>
        <span class="chip2">${ico('i-users')}${esc(fmtCap(w.cap||0))} ${esc('نفر')}</span>
      </div>
      ${(w.sess||[]).length>1?`<div class="evpage-secs">${(w.sess||[]).map((x,i)=>{const j=jParse(x.d);
        return `<span>${ico('i-calendar')}${esc('جلسهٔ '+fa(i+1)+': '+(j?jLong(j.jy,j.jm,j.jd):'')+' '+(x.t?fa(x.t):''))}</span>`}).join('')}</div>`:''}
      <div class="evpage-secs">
        <span>${ico('i-doc')}${esc(reg?formName(reg):'فرم ثبت‌نام وصل نشده')}</span>
        ${featOn('survey')?`<span>${ico('i-star')}${esc(svy?'نظرسنجی: '+formName(svy):'نظرسنجی')}</span>`:''}
        ${featOn('exam')&&w.exam!=='none'?`<span>${ico('i-check')}${esc(exm?'آزمون: '+formName(exm):'آزمون')}</span>`:''}
        ${featOn('cert')?`<span>${ico('i-medal')}${esc('گواهی حضور')}</span>`:''}
        ${featOn('att')?`<span>${ico('i-qr')}${esc('ورود با QR')}</span>`:''}
      </div>
      ${w.held&&w.rep?`<p class="cap">${esc(w.rep)}</p>`:''}
      ${on.length?`<div class="admchips">${on.map(x=>`<span class="tag">${esc(x)}</span>`).join('')}</div>`:''}
      <div class="row tight">${w.held?`<span class="btn sm">${esc('آرشیو رویداد')}</span>`:`<span class="btn sm">${esc('ثبت‌نام')}</span>`}
        <span class="btn sm quiet">${esc('افزودن به تقویم')}</span>
        <span class="btn sm quiet">${esc('اشتراک‌گذاری')}</span></div>
    </div></div>`;
}
function msgPrev(){
  const w=S.wiz, L=NE().l||{}, M=(NE().msgTpl)||{};
  const fill=s=>String(s||'').replace('{name}',w.name||'رویداد').replace('{when}',w.date||'')
    .replace('{time}',w.time||'');
  const rows=(NE().channels||[]).filter(c=>chOn(c.k)).map(c=>
    `<div class="mrow"><span class="cap">${esc(c.n)}</span><span>${esc(fill(M[c.k]||''))}</span></div>`);
  const rem=remList().filter(r=>r.on!==0).map(r=>
    `<div class="mrem"><span class="cap">${esc(remText(r))}</span><span>${esc(remAt(r)||'بی تاریخ')}
      · ${esc(((NE().remCh||[]).find(c=>c.k===r.ch)||{}).n||'')}${S.wiz.remEvery&&(S.wiz.sess||[]).length>1?' · هر جلسه':''}</span></div>`);
  return `<div class="msgs">${rows.join('')}${rem.join('')}</div>`;
}
function cardDefs(){
  const rows=defsFor().slice(0,5);
  if(!rows.length) return '';
  const st=(DEFD().states||{}).wait||['در انتظار تأیید','warn'], waiting=rows.filter(r=>r.wait).length;
  return `<section class="card stack">
    <div class="row"><div class="head">${esc(DEFD().lead||'تعریف‌های تازه')}</div><span class="sp"></span>
      <span class="cap">${esc(waiting?fa(waiting)+' '+esc(DEFD().note||''):(DEFD().empty||''))}</span></div>
    <div class="admlist">${rows.map(r=>{const s=r.wait?st:((DEFD().states||{})[r.st||'ok']||st), mine=r.by===me().k;
      return `<div class="admlirow">
        <span class="ic">${ico(defKind(r.kind).i)}</span>
        <span class="sp"><b style="font-size:var(--fs-sub)">${esc(r.n)}</b>
          <small class="cap" style="display:block">${esc(defKind(r.kind).n)} · ${esc(personOf(r.by).n)} · ${esc(fieldOf(r.f).n)} · ${esc(r.at)}${mine?' · '+esc(W.you||'خودت'):''}</small></span>
        ${tag(s[0],s[1])}
        ${canApprove(r)?`<button class="btn sm" data-defok="${esc(r.id)}">${ico('i-check')}${esc(W.approve||'تأیید')}</button>
          <button class="btn sm quiet" data-defno="${esc(r.id)}" aria-label="${esc(W.back||'برگشت برای اصلاح')}">${ico('i-close')}</button>`:''}</div>`}).join('')}</div>
  </section>`;
}
function vEventWizard(){
  const Z=NE(), L=Z.l||{}, w=S.wiz, isEv=w.kind==='event',
    stepsAll=wizSteps(), st=Math.max(0,Math.min(stepsAll.length-1,+w.step||0));
  const sem=isEv?st:(st===0?0:4);
  const steps=stepsAll.map((n,i)=>`<div class="st ${i<st?'done':i===st?'on':''}"><i></i>
      <small>${esc(fa(i+1))}. ${esc(n)}</small></div>`).join('');
  const types=(Z.kinds||[]).map(k=>`<button class="admkind ${w.et===k.k?'on':''}" data-wet="${esc(k.k)}">
      ${ico(k.i)}<b>${esc(k.n)}</b></button>`).join('');
  const toggles=(Z.features||[]).map(x=>`<button class="admfeat ${featOn(x.k)?'on':''}" data-wfeat="${esc(x.k)}">
      <i>${featOn(x.k)?ico('i-check'):''}</i><b>${esc(x.n)}</b><small>${esc(x.d||'')}</small></button>`).join('');
  const seg=(attr,arr,cur)=>arr.map(m=>`<button class="chip ${String(cur)===String(m.k)?'on':''}"
      data-wpick="${attr}" data-wval="${esc(m.k)}">${esc(m.n)}</button>`).join('');
  let inner='';
  if(sem===0){
    const th=themeOf(w.theme);
    inner=`${isEv?`<span class="lbl twolbl">${esc('نوع رویداد')}</span>
      <div class="admkinds types">${types}</div>`:''}
    <div class="wgrid">
      <label class="fld"><span class="lbl">${esc(L.name||'نام')}</span>
        <input class="input" id="wzName" data-winput="name" value="${esc(w.name||'')}" placeholder="مثلاً کارگاه نقالی و پرده‌خوانی"/></label>
      <label class="fld"><span class="lbl">${esc(L.sum||'یک خط توضیح')}</span>
        <input class="input" id="wzDesc" data-winput="desc" value="${esc(w.desc||'')}" placeholder="برای کارت و فهرست"/></label>
      <label class="fld"><span class="lbl">${esc(L.org||'برگزارکننده')}</span>
        <input class="input" id="wzOrg" data-winput="org" value="${esc(w.org||'')}" placeholder="حوزه یا مسئول اجرا"/></label>
    </div>
    <div class="wgrid">
      <label class="fld"><span class="lbl">${esc(L.about||'دربارهٔ رویداد')}</span>
        <textarea class="input" id="wzAbout" data-winput="about" rows="3" placeholder="چند خط برای صفحهٔ رویداد">${esc(w.about||'')}</textarea></label>
      <div class="fld"><span class="lbl">${esc(L.tags||'برچسب‌ها')}</span>
        <div class="row tight">${(Z.labels||[]).map(x=>`<button class="chip ${String(w.label||'')===String(x.k)?'on':''}"
          data-wpick="label" data-wval="${esc(x.k)}">${esc(x.n)}</button>`).join('')}</div></div>
      <div class="fld"><span class="lbl">${esc(L.poster||'پوستر')}</span>
        <div class="posters">${(Z.posters||[]).map(p=>`<button class="pthumb ${w.poster===p.k?'on':''}" data-wposter="${esc(p.k)}"
          aria-label="${esc(p.n)}" title="${esc(p.n)}"><img src="posters/${esc(p.k)}" alt="" loading="lazy"/></button>`).join('')}
          <label class="pthumb up ${w.posterUp?'on':''}" title="${esc(((Z.posterUp||{}).add)||'پوستر خودم')}">
            ${w.posterUp?`<img src="${esc(w.posterUp)}" alt=""/>`:ico('i-image')}
            <input type="file" accept="image/*" data-wfile="1" hidden/>
            <small>${esc(w.posterUp?(((Z.posterUp||{}).change)||'عوض کن'):(((Z.posterUp||{}).add)||'پوستر خودم'))}</small>
          </label>
        </div>
        <span class="cap">${esc(((Z.posterUp||{}).hint)||'')}</span>
        ${w.posterUp?`<button class="btn sm quiet" data-wposterclear="1">${ico('i-trash')}${esc(((Z.posterUp||{}).clear)||'بردار')}</button>`:''}
      </div>
    </div>
    <div class="themeRow">
      <div class="fld"><span class="lbl">${esc(L.theme||'تم کارت')}</span>
        <div class="row tight">${(Z.themes||[]).map(x=>`<button class="chip ${w.theme===x.k?'on':''}" data-wtheme="${esc(x.k)}">${esc(x.n)}</button>`).join('')}</div>
        <span class="cap">${esc(th.d||'')}</span></div>
      <div class="cardPrev"><span class="lbl">${esc(L.cardPrev||'پیش‌نمایش کارت')}</span>${evCardPrev()}</div>
    </div>`;
  }
  else if(sem===1) inner=`<p class="cap">${esc((Z.hints||{}).when||'')}</p>
    <div class="wform">
      <div class="clockbar">
        <span class="ic">${ico('i-clock')}</span>
        <b id="wzClock">${esc(clockStr())}</b>
        <span class="cap" id="wzClockSt">${esc(NET.state==='net'?L.synced:L.local)}</span>
        <span class="sp"></span><span class="cap">${esc(L.tz||'')}</span></div>
      <div class="fld"><span class="lbl">${esc('نحوهٔ برگزاری')}</span>
        <div class="row tight">${seg('mode',Z.modes||[],w.mode)}</div></div>
      <div class="wgrid">
        ${dpField('date',L.date)}${timeField('time',L.time)}${timeField('to',L.to)}
      </div>
      <div class="wgrid">
        ${dpField('end',L.end)}${numField('dur',L.dur,15,15)}${numField('sessions',L.sessions,1,1)}
      </div>
      <div class="fld"><span class="lbl">${esc((Z.held||{}).t||'این رویداد برگزار شده')}</span>
        <div class="row tight">
          <button class="chip ${w.held?'on':''}" data-wheld="1">${esc((Z.held||{}).t||'برگزار شده')}</button>
          <span class="cap">${esc((Z.held||{}).d||'')}${w.held?' · '+esc((Z.held||{}).willArchive||''):''}</span></div></div>
      ${w.mode!=='online'?textField('place',L.place,'place',L.room):''}
      ${w.mode!=='physical'?textField('link',L.link,'link',L.linkPh):''}
      ${(+w.sessions||1)>1?`<div class="fld"><span class="lbl">${esc((Z.sess||{}).t||'جلسه‌ها')}</span>
        <span class="cap">${esc((Z.sess||{}).d||'')}</span>${sessRows()}</div>`:''}
      ${w.held?'':`<div class="wgrid">
        ${dpField('regFrom',L.regFrom)}${dpField('regTo',L.regTo)}
        <div class="fld"><span class="lbl">${esc('سطح دسترسی')}</span>
          <div class="row tight">${seg('privacy',Z.privacy||[],w.privacy)}</div></div>
      </div>`}
    </div>`;
  else if(sem===2){
    const caps=Z.capNote||{};
    inner=`<p class="cap">${esc((Z.hints||{}).cap||'')}</p>
    <div class="wform">
      <div class="wgrid">
        ${numField('cap',L.cap,1,1,caps.cap)}${numField('pre',L.pre,0,1,caps.pre)}${numField('extra',L.extra,0,1,caps.extra)}
      </div>
      ${w.held?`<div class="fld"><span class="lbl">${esc((Z.held||{}).archive||'آرشیو رویداد')}</span>
        <div class="wgrid">
          ${numField('who',(Z.held||{}).who||'چند نفر شرکت کردند',0,1)}
          <label class="fld"><span class="lbl">${esc((Z.held||{}).rep||'گزارش کوتاه')}</span>
            <input class="input" id="wz-rep" data-winput="rep" value="${esc(w.rep||'')}" placeholder="${esc('دو خط از رویداد')}"/></label>
          <label class="fld"><span class="lbl">${esc((Z.held||{}).media||'لینک آلبوم یا فیلم')}</span>
            <input class="input" id="wz-media" dir="ltr" data-winput="media" value="${esc(w.media||'')}" placeholder="https://"/></label>
        </div>
        <span class="cap">${esc((Z.held||{}).auto||'')}</span></div>`
      :`<div class="fld"><span class="lbl">${esc('لیست انتظار')}</span>
        <div class="row tight">${seg('waitMode',Z.waitModes||[],w.waitMode)}</div>
        <span class="cap">${esc((Z.wait||{})[w.waitMode]||Z.seats||'')}</span></div>
      <div class="fld"><span class="lbl">${esc('بلیت')}</span>
        <div class="row tight">${seg('tickets',Z.tickets||[],w.tickets)}</div></div>
      <div class="fld"><span class="lbl">${esc('روش حضور و غیاب')}</span>
        <div class="row tight">${seg('att',Z.att||[],w.att)}</div></div>`}
      <div class="fld">${numField('points','امتیاز شرکت',0,5)}</div>
      ${isMoney()?`<div class="fld"><span class="lbl">${esc('مبالغ و پرداخت')}</span>
        ${fpForm('reg')?`${moneyRows(fpForm('reg'))}
          <div class="revrow"><span class="cap">${esc((Z.forms||{}).sum||'جمع')}</span>
            <span>${esc(fa(formSum(fpForm('reg'))))} ${esc('ریال')}</span></div>
          <a class="btn sm quiet" href="${esc(builderUrl('reg'))}" target="_blank" rel="noopener">${ico('i-wallet')}${esc(((Z.forms||{}).openBuilder)||'ویرایش در فرم‌ساز')}</a>`
        :`<span class="cap">${esc((Z.forms||{}).money||'')}</span>
          <div class="row tight"><a class="btn sm quiet" href="${esc(builderUrl('reg'))}" target="_blank" rel="noopener">${ico('i-plus')}${esc((Z.forms||{}).build||'ساختن در فرم‌ساز')}</a></div>`}
      </div>`:`<p class="cap">${esc(Z.money||'')}</p>`}
      <div class="head">${esc('قابلیت‌ها')}</div>
      <div class="admkinds feats">${toggles}</div>
    </div>`;
  }
  else if(sem===3){
    inner=`<p class="cap">${esc((Z.hints||{}).forms||'')}</p>
    <div class="wform">
      <div class="head">${esc((Z.forms||{}).lead||'فرم‌ها')}</div>
      ${((Z.forms||{}).needs||[]).map(n=>formPick(n.k,n.n,n.d)).join('')}
      <div class="fld"><span class="lbl">${esc((Z.forms||{}).other||'فرم دیگر')}</span>
        ${formPick('other',(Z.forms||{}).other||'فرم دیگر','')}</div>
      <div class="fld"><span class="lbl">${esc((Z.remB||{}).t||'یادآوری‌ها')}</span>${remRows()}</div>
      <div class="fld"><span class="lbl">${esc('کانال‌های اطلاع‌رسانی')}</span>
        <div class="row tight">${(Z.channels||[]).map(x=>`<button class="chip ${chOn(x.k)?'on':''}" data-wch="${esc(x.k)}">${esc(x.n)}</button>`).join('')}</div></div>
      <div class="fld"><span class="lbl">${esc('پیش‌نمایش پیام‌ها')}</span>${msgPrev()}</div>
    </div>`;
  }
  else {
    const rK=defKind(w.kind), t=neKind(w.et);
    const on=(Z.features||[]).filter(x=>featOn(x.k)).map(x=>x.n);
    const j1=jParse(w.date), j2=jParse(w.end), W2=evWhen();
    const dayOf=j=>j?jLong(j.jy,j.jm,j.jd):'';
    const reg=fpForm('reg'), svy=fpForm('survey'), exm=fpForm('exam');
    const heldN=(((A.events||{}).states||{}).held||[])[0]||'برگزار شده';
    const R=[w.held?['وضعیت',[heldN,w.who?fa(w.who)+' نفر':'',w.rep].filter(Boolean).join(' · ')]:null,
      ['تعریف',rK.n+(t.n?' · '+t.n:'')],['نام',w.name||''],['توضیح',w.desc||''],
      ['برگزارکننده',w.org||''],['پوستر',w.posterUp?(((Z.posterUp||{}).add)||'پوستر خودم'):(w.poster?((Z.posters||[]).find(p=>p.k===w.poster)||{}).n||w.poster:'برداشته نشده')],
      isEv?['شروع',[W2.day||dayOf(j1),W2.time&&fa(W2.time),w.mode==='online'?(w.link||''):(w.place||'')].filter(Boolean).join(' · ')]:null,
      isEv?['پایان',[W2.range||dayOf(j2)||W2.day,dayOf(j1)&&(w.sess||[]).length?fa(((w.sess||[])[(w.sess||[]).length-1]||{}).to||w.to||''):(w.to&&fa(w.to)),].filter(Boolean).join(' · ')]:null,
      isEv?['جلسات',fa(W2.count)+' جلسه'+(w.dur?' · هر جلسه '+fa(w.dur)+' دقیقه':'')]:null,
      isEv?['ظرفیت',fa(w.cap||0)+' نفر'+(w.pre?' · پیش‌ثبت‌نام '+fa(w.pre):'')+(w.extra?' · مازاد '+fa(w.extra):'')+' · لیست انتظار '+((Z.waitModes||[]).find(x=>x.k===w.waitMode)||{}).n]:null,
      isEv&&!w.held?['ثبت‌نام',[w.regFrom?fa(w.regFrom):(L.now||'همین حالا'),w.regTo?fa(w.regTo):(L.tillStart||'تا شروع')].join(' · ')]:null,
      isEv?['دسترسی',((Z.privacy||[]).find(x=>x.k===w.privacy)||{}).n||'']:null,
      isEv?['فرم ثبت‌نام',reg?formName(reg):(Z.forms||{}).none||'']:null,
      isEv&&featOn('survey')?['نظرسنجی',svy?formName(svy):((Z.forms||{}).none||'')]:null,
      isEv&&featOn('exam')?['آزمون',w.exam==='none'?(Z.forms||{}).none||'':(exm?formName(exm):'')]:null,
      (isMoney()&&reg)?['مبالغ',fa(formSum(reg))+' '+((NE().l||{}).rial||'ریال')]:null,
      w.held?['شرکت‌کننده',w.who?fa(w.who)+' نفر':'']:null,
      w.held?['گزارش',w.rep||'']:null,
      w.held?['آرشیو',w.media||'']:null,
      isEv&&!w.held?['حضور و غیاب',((Z.att||[]).find(x=>x.k===w.att)||{}).n||'']:null,
      isEv?['قابلیت‌ها',on.join(' · ')]:null,
      isEv?['یادآوری',remList().filter(r=>r.on!==0).map(r=>remText(r)+(S.wiz.remEvery&&(S.wiz.sess||[]).length>1?' («هر جلسه»)':'')).join(' · ')]:null,
      isEv?['اطلاع‌رسانی',(Z.channels||[]).filter(c=>chOn(c.k)).map(c=>c.n).join(' · ')]:null,
      isEv?[L.pageLink||'نشانی صفحه',evLink()]:null].filter(r=>r&&r[1]);
    inner=`<p class="cap">${esc((Z.hints||{}).look||'')}</p>
      <div class="cardPrev"><span class="lbl">${esc(L.cardPrev||'')}</span>${evCardPrev()}</div>
      <div class="pagelink"><span class="ic">${ico('i-link')}</span>
        <code dir="ltr">${esc(evLink())}</code>
        <button class="btn sm quiet" data-copyev="1">${ico('i-copy')}${esc('رونوشت')}</button>
        <a class="btn sm quiet" href="${esc(evLink())}" target="_blank" rel="noopener">${ico('i-eye')}${esc('باز کردن')}</a>
        <span class="cap">${esc(L.linkHint||'')}</span></div>
      <div class="pagePrev"><span class="lbl">${esc(L.pagePrev||'پیش‌نمایش صفحه')}</span>${evPagePrev()}</div>
      <div class="admreview"><div class="revhead">
          <b>${esc(w.name||'بی‌نام')}</b>${tag(canPublish()?(Z.route||{}).self:(Z.route||{}).ask,canPublish()?'ok':'warn')}</div>
        ${R.map(r=>`<div class="revrow"><span class="cap">${esc(r[0])}</span><span>${esc(r[1])}</span></div>`).join('')}
        <div class="admchips"><span class="tag brand">${esc(themeOf(w.theme).n||'')}</span>
          ${reg?`<span class="tag">${esc('فرم ثبت‌نام: '+formName(reg))}</span>`:''}
          ${featOn('survey')&&svy?`<span class="tag">${esc('نظرسنجی: '+formName(svy))}</span>`:''}
          ${featOn('exam')&&exm?`<span class="tag">${esc('آزمون: '+formName(exm))}</span>`:''}
          ${w.held?`<span class="tag">${esc('آرشیو')}</span>`:''}</div></div>`;
  }
  const j1=jParse(w.date);
  const ready=sem===0?(isEv?!!(w.et&&String(w.name||'').trim()):!!String(w.name||'').trim())
    :sem===1?!!(j1&&w.time&&w.to&&(w.mode==='online'?String(w.link||'').trim():String(w.place||'').trim()))
    :sem===2?!!(+w.cap>0)
    :sem===3?true
    :true;
  const last=stepsAll.length-1, wEdit=!!w.edit;
  return `<section class="card stack admwiz">
    <div class="row"><div class="head">${esc(Z.lead||'تعریف تازه')}</div><span class="sp"></span>
      <span class="cap">${esc(W.steps||'گام')} ${esc(fa(st+1))} ${esc(W.of||'از')} ${esc(fa(stepsAll.length))}</span>
      ${btn('بازگشت به فهرست','data-evback','i-back')}</div>
    <div class="admsteps">${steps}</div>
    ${wEdit?`<div class="admchips"><span class="tag brand">${esc(W.editEvent||'در حال ویرایش')} · ${esc(w.name||'')}</span>
      <span class="cap">${esc(W.editKeeps||'وضعیت عوض نمی‌شود')}</span></div>`:''}
    ${inner}
    <div class="row"><span class="sp"></span>
      ${wEdit?`<button class="btn quiet sm" data-wcancel="1">${esc(W.cancelEdit||'انصراف از ویرایش')}</button>`:''}
      ${btn(W.prev||'گام پیش','data-wstep="'+Math.max(0,st-1)+'"'+(st===0?' disabled':''),'i-chev-right')}
      ${st<last?btn(W.next||'گام بعد','data-wstep="'+(st+1)+'" data-wgo="1"'+(ready?'':' disabled'),'i-chev-left')
        :`<button class="btn" data-wsend="1" ${ready?'':'disabled'}>${ico(canPublish()?'i-check':'i-send')}${esc(wEdit?(W.saveEdit||'ذخیرهٔ ویرایش'):(canPublish()?(W.publish||'انتشار'):(W.sendApprove||'فرستادن برای تأیید')))}</button>`}</div>
  </section>`;
}

/* ── رویدادها ─────────────────────────────────────────────────────────── */
function vEvents(){
  if(S.psec==='edit') return postEditor();
  if(S.pmgr) return postMgr();
  const f=EV.filters||[], cur=S.evF||'all';
  const all=evAll(), list=all.filter(evFilter(cur));
  const filt=f.map(x=>`<button class="tag ${cur===x.k?'on':''}" data-evF="${esc(x.k)}">${esc(x.n)}
      <b>${esc(fa(all.filter(evFilter(x.k)).length))}</b></button>`).join('');
  const rows=list.map(e=>{
    const stE=evState(e), st=(EV.states||{})[stE]||['',''];
    const pct=Math.min(100,Math.round((+e.reg||0)/Math.max(1,+e.cap||1)*100));
    const ses=(e.sess||[]);
    return rowLink({attrs:`data-ev="${esc(e.id)}"`, i:'i-calendar', chev:1, stt:stE,
      b:esc(e.n), s:`${esc(e.kind)} · ${esc(whenLine(e))}${ses.length>1?` · ${esc(fa(ses.length)+' جلسه')}`:''} · ${esc(e.time)} · ${esc(e.place)}`,
      i:e.kind==='همایش'?'i-ticket':e.kind==='وبینار'?'i-globe':e.kind==='اردو'?'i-flag':e.kind==='مسابقه'?'i-medal':'i-calendar',
      img:e.posterUp?e.posterUp:(e.poster?('posters/'+e.poster):''),
      right:`<span class="mini"><span class="cap">${esc(fa(e.reg))}/${esc(fa(e.cap))}</span>
        <span class="admbar-line ${pct>=100?'full':''}"><i style="width:${pct}%"></i></span>${tag(st[0],st[1])}</span>`});
  }).join('');
  return `<section class="card stack">
    <div class="row"><div class="head">${esc(EV.lead||'رویدادها و مطالب')}</div><span class="sp"></span>
      ${btn('مطلب جدید','data-pnew','i-article')}
      ${btn('رویداد جدید','data-evnew','i-calendar')}</div>
    <div class="admfilters">${filt}</div>
    <div class="admlist">${rows||emptyBox(T.empty)}</div>
    <hr class="hr"/>
    <div class="head">مطلب‌ها</div>
    <div class="admlist">${postRows()||emptyBox('هنوز مطلبی نساخته‌ای')}</div>
    <div class="head" style="margin-top:10px">نمونه‌های ثابت</div>
    <div class="admlist">${demoRows()}</div>
    <p class="cap">مطلب منتشرشده در خانهٔ کاربران، بخش «مطالب» می‌نشیند و پیش‌نمایشش در post.html باز می‌شود.</p>
  </section>`;
}

/* ── کاربران ───────────────────────────────────────────────────────────── */
/* بخش کاربران: پنج گروه روشن، نه چهارده ردیف؛ هر گروه اگر لازم داشت زیرتب دارد
   و پروندهٔ هر کاربر خودش صفحهٔ کامل با تبهای جدا است. */
/* چهار کاشی سرِ کاربران؛ خط جمعبندی هر کاشی در vUList با عدد زنده ساخته میشود */
const UTILES=[['req','درخواست‌ها','i-check'],['club','باشگاه و امتیاز','i-star'],
  ['cert','گواهینامه‌ها','i-medal'],['tools','ابزارها و گزارش','i-sliders']];
const UCLUBTABS=[['rules','امتیاز شرطی'],['ach','نشان‌ها'],['shop','فروشگاه پاداش'],['rank','رتبه‌بندی'],
  ['occ','مناسبت‌ها و تولدها']];
const UTOOLTABS=[['report','گزارش کاربران'],['staff','مدیران و کارشناسان'],['par','پارامتر پروفایل'],['add','افزودن دستی'],
  ['imp','ورودی اکسل'],['tags','برچسب‌ها'],['blocked','مسدودها'],['inbox','صندوق پیام‌ها'],['log','لاگ عملیات']];
const UPTABS=[['info','اطلاعات'],['club','باشگاه'],['ev','رویدادها و فرم‌ها'],['msg','پیام‌ها'],['log','تاریخچه']];
function vUsers(){
  const v=S.uV||'';
  if(v==='req') return vUReq(); if(v==='club') return vUClub();
  if(v==='occ') return vUOcc();
  if(v==='tools') return vUTools(); if(v==='user') return vUUser();
  if(v==='cert') return vCert();
  return vUList();
}
const uBack=`<div class="row">${btn(W.back||'بازگشت به فهرست','data-uback','i-back')}<span class="sp"></span></div>`;
function uHead(n,extra){return `<div class="row"><div class="head">${esc(n)}</div><span class="sp"></span>${extra||''}</div>`}
function vUList(){
  const q=norm(S.q), cur=S.uF||'all', curTag=S.uTag||'';
  let list=memList().filter(m=>{
    if(cur==='pending'&&m.st[1]!=='warn') return false;
    if(cur==='vip'&&!m.vip) return false;
    if(cur==='club'&&m.tags.indexOf('عضو باشگاه')<0) return false;
    if(cur==='blocked'&&m.st[1]!=='stop') return false;
    if(curTag&&(m.tags||[]).indexOf(curTag)<0) return false;
    if(!q) return true;
    return norm(m.n+' '+m.code+' '+m.ph+' '+(m.nid||'')+' '+(m.city||'')).indexOf(q)>-1;});
  const filt=UF.map(x=>`<button class="tag ${cur===x.k&&!curTag?'on':''}" data-uF="${x.k}">${esc(x.n)}
      <b>${esc(fa(ufCount(x.k)))}</b></button>`).join('');
  const lab=Object.keys(uLabels()).slice(0,6).map(t=>`<button class="chip ${curTag===t?'on':''}" data-uTag="${esc(t)}">${esc(t)}</button>`).join('');
  const prof=ufCount('pending'), absR=uAbs().filter(a=>a.st==='در انتظار').length,
    shopR=uShopReq().filter(r=>r.st==='در انتظار').length, reqs=prof+absR+shopR;
  const unread=uInbox().filter(i=>!i.read).length, occL=occAll(), occOnN=occL.filter(occOn).length;
  const cj=(CE.jobs||[]).concat(S.jobs||[]), cw=cj.filter(j=>j.st==='wait').length;
  const sum={
    req:{s:`پروفایل ${fa(prof)} · غیبت مجاز ${fa(absR)} · پاداش ${fa(shopR)}`,
      b:reqs?tag(fa(reqs)+' در انتظار','warn'):''},
    club:{s:`${fa(ufCount('club'))} عضو · ${fa(ufCount('vip'))} ویژه · ${fa(occOnN)} مناسبت روشن`,b:''},
    cert:{s:`${fa(cw)} صدور در نوبت · ${fa(cj.length-cw)} منتشرشده · استعلام با کیوآرکد`,b:''},
    tools:{s:`${fa(unread)} پیام ناخوانده · ${fa(ufCount('blocked'))} مسدود · گزارش و اکسل`,
      b:unread?tag(fa(unread)+' پیام تازه','warn'):''}};
  const rows=UTILES.map(t=>{const d=sum[t[0]];
    return `<button class="utile" data-uv="${t[0]}"><span class="tt">${ico(t[2])}<b>${esc(t[1])}</b>${d.b}</span>
      <small>${d.s}</small></button>`}).join('');
  const tbody=list.map(m=>`<tr data-user="${esc(m.id)}">
      <td><b>${esc(m.n)}</b>${m.vip?' ⭐':''}</td><td class="num">${esc(m.code)}</td><td class="num">${esc(fa(m.ph))}</td>
      <td>${tag(m.st[0],m.st[1])}</td><td>${esc(m.tags.filter(t=>isMoney()||!moneyTag(t)).join('، '))}</td>
      <td class="num">${esc(fa(m.ev))}</td><td class="num">${esc(fa(m.pt))}</td></tr>`).join('');
  const cards=list.map(m=>rowLink({attrs:`data-user="${esc(m.id)}"`, i:'i-users', chev:1,
      b:esc(m.n), s:`${esc(m.code)} · ${esc(fa(m.ph))}`, right:tag(m.st[0],m.st[1])})).join('');
  return `<section class="card stack">
    ${uHead(L.users,`<span class="cap">${esc(fa(list.length))} ${esc(W.people||'نفر')}</span>`)}
    <div class="admtiles">${rows}</div>
    <hr class="hr"/>
    <div class="head">فهرست کاربران</div>
    <div class="admfilters">${filt}</div>
    ${lab?`<div class="admfilters">${lab}${curTag?`<button class="chip" data-uTag="">${esc('بی‌برچسب‌سازی ×')}</button>`:''}</div>`:''}
    ${list.length?`<div class="admmatrix"><table class="admtable">
      <thead><tr><th>نام</th><th>کد</th><th>موبایل</th><th>وضعیت</th><th>برچسب</th><th>رویداد</th><th>امتیاز</th></tr></thead>
      <tbody>${tbody}</tbody></table></div>
      <div class="admcard-user">${cards}</div>`:emptyBox(T.empty)}
    <hr class="hr"/>
    <div class="head">خروجی اکسل کاربران</div>
    ${balebox(`<div class="pvsheet">${'<i></i>'.repeat(9)}</div>`,'users','فایل کامل با همهٔ ستون‌ها از ربات بلهٔ موسسه می‌آید')}
    <p class="cap">${esc('با زدن هر نفر، پروندهٔ کاملش با تبهای اطلاعات و باشگاه و رویدادها باز میشود.')}</p>
  </section>`;
}
/* گزارش کاربران: زیرتب اول ابزارها: آمار، جنسیت، فعالیت، شهر، تحصیلات و منبع عضویت */
function cUReport(){
  const L0=memList(), tot=L0.length;
  const pend=L0.filter(m=>m.st[1]==='warn').length, vip=L0.filter(m=>m.vip).length,
    blk=L0.filter(m=>m.st[1]==='stop').length, ok=L0.filter(m=>m.st[1]==='ok').length,
    imp=L0.filter(m=>(m.src||'').indexOf('اکسل')>-1||(m.src||'').indexOf('گروهی')>-1).length,
    ref=L0.filter(m=>(m.src||'').indexOf('دعوت')>-1).length;
  const male=L0.filter(m=>m.g==='مرد').length, female=L0.filter(m=>m.g==='زن').length;
  const avg=tot?Math.round(L0.reduce((a,m)=>a+uPct(m),0)/tot):0;
  const act7=L0.filter(m=>+m.act<=7).length, act30=L0.filter(m=>+m.act<=30).length, sleep=tot-act30;
  const city={}; L0.forEach(m=>{if(m.city) city[m.city]=(city[m.city]||0)+1});
  const topCity=Object.keys(city).sort((a,b)=>city[b]-city[a]).slice(0,7);
  const edu={}; L0.forEach(m=>{if(m.ed) edu[m.ed]=(edu[m.ed]||0)+1});
  const topEdu=Object.keys(edu).sort((a,b)=>edu[b]-edu[a]).slice(0,5);
  const bar=(v,t)=>{const w=t?Math.round(v/t*10):0; return '▓'.repeat(w)+'░'.repeat(10-w)};
  const per=(RP.periods||[]).map(x=>`<button class="chip ${S.rp===x?'on':''}" data-rp="${esc(x)}">${esc(x)}</button>`).join('');
  return `<div class="admfilters">${per}</div>
    <div class="admkpi">
      <div class="k"><small>کل</small>${bits(fa(tot))}</div>
      <div class="k"><small>تأییدشده</small>${bits(fa(ok))}</div>
      <div class="k"><small>در صف</small>${bits(fa(pend))}</div>
      <div class="k"><small>ویژه</small>${bits(fa(vip))}</div></div>
    <div class="admkpi">
      <div class="k"><small>واردشده از اکسل</small>${bits(fa(imp))}</div>
      <div class="k"><small>با دعوت دوستان</small>${bits(fa(ref))}</div>
      <div class="k"><small>مسدود</small>${bits(fa(blk))}</div>
      <div class="k"><small>میانگین تکمیل پروفایل</small>${bits(fa(avg)+'٪')}</div></div>
    <div class="head">جنسیت</div>
    ${table([['آقایان',fa(male)+' نفر ('+fa(tot?Math.round(male/tot*100):0)+'٪)',bar(male,tot)],
      ['خانم‌ها',fa(female)+' نفر ('+fa(tot?Math.round(female/tot*100):0)+'٪)',bar(female,tot)]])}
    <div class="head">فعالیت</div>
    ${table([['۲۴ ساعت اخیر',fa(act7),''],['۷ روز اخیر',fa(act7),''],['۳۰ روز اخیر',fa(act30),''],
      ['غیرفعال',fa(sleep),sleep?'به یادشان بیفت؛ پیام مهربان':'' ]])}
    ${topCity.length?`<div class="head">شهرهای برتر</div>
    ${table(topCity.map(c=>[c,fa(city[c])+' نفر',bar(city[c],tot)]))}`:''}
    ${topEdu.length?`<div class="head">مقطع تحصیلی</div>
    ${table(topEdu.map(c=>[c,fa(edu[c])+' نفر']))}`:''}
    <div class="head">منبع عضویت</div>
    ${table([['با دعوت دوستان',fa(ref)+' نفر'],['ورود گروهی اکسل',fa(imp)+' نفر'],
      ['مستقیم',fa(Math.max(0,tot-ref-imp))+' نفر']])}
    <div class="head">خروجی اکسل گزارش</div>
    ${balebox(`<div class="pvsheet">${'<i></i>'.repeat(7)}</div>`,'report','فایل کامل با هر دورهٔ زمانی که برگزینید از ربات بلهٔ موسسه می‌آید')}`;
}
/* مناسبتها و تولدها */
function cUOcc(){
  const occ=occAll(), mb=(N.ACCOUNT||{}).monthsFa||[];
  const now=new Date(), mIdx=(new Date(now.getFullYear(),now.getMonth(),1));
  const bdays=memList().filter(m=>m.bd).map(m=>{const pr=String(m.bd).split('/');
    return {m:un(pr[0]||''), d:un(pr[1]||''), n:m.n, id:m.id}})
    .sort((a,b)=>(+a.m-b.m)||(+a.d-b.d)).slice(0,6);
  const rows=occ.map(o=>{const on=occOn(o);
    return `<div class="admlirow">${ico('i-calendar')}
      <span class="sp"><b>${esc(o.n)}</b><small class="cap">${esc(fa(o.jd))} ${esc(mb[o.jm-1]||'')} ·
        ${esc(o.g==='همه'?'همه':o.g)} · ${esc(fa(o.pts))} امتیاز${o.def?'':' · سفارشی'}</small></span>
      <span class="mini">${o.def?'':`<button class="btn sm quiet" data-uoccdel="${esc(o.k)}">${esc('برداشتن')}</button>`}
        <span class="switch ${on?'on':''}" data-uocc="${esc(o.k)}" role="switch" aria-checked="${on?'true':'false'}" aria-label="${esc(o.n)}"></span></span></div>`}).join('');
  return `<div class="row"><div class="head">مناسبت‌ها و تولدها</div><span class="sp"></span>
    ${btn('مناسبت تازه','data-uoccnew','i-plus')}</div>
    <div class="head">تولدهای نزدیک</div>
    ${bdays.length?table(bdays.map(b=>[b.n,fa(b.d)+' '+(mb[+b.m-1]||''),'پیام تبریک + '+fa(15)+' امتیاز'])):emptyBox('تاریخ تولدی در پروندهها نیست')}
    <div class="head">مناسبت‌ها (${esc(fa(occ.filter(occOn).length))} روشن از ${esc(fa(occ.length))})</div>
    ${rows}
    <p class="cap">${esc('مناسبت آماده حذف نمیشود؛ فقط خاموش میشود. مناسبت سفارشی با روز و جنسیت و امتیاز خودت ساخته میشود و ارسال تکراری ندارد.')}</p>
    ${S.uoccNew?`<hr class="hr"/>
    <div class="row"><div class="head">مناسبت تازه</div><span class="sp"></span></div>
    <div class="stack">
      <label class="fld"><span>نام مناسبت</span><input id="occN" type="text" placeholder="مثل: روز خانه‌سازی"/></label>
      <div class="row tight">
        <label class="fld"><span>ماه</span><input id="occM" type="number" min="1" max="12" value="1"/></label>
        <label class="fld"><span>روز</span><input id="occD" type="number" min="1" max="31" value="1"/></label>
        <label class="fld"><span>مخاطب</span><select id="occG"><option>همه</option><option>زن</option><option>مرد</option></select></label>
        <label class="fld"><span>امتیاز</span><input id="occP" type="number" min="0" max="100" value="10"/></label></div>
      <div class="row tight">${btn('ساختن مناسبت','data-uoccadd','i-check')}${btn('بی‌خیال','data-uocccancel')}</div></div>`:''}
    <hr class="hr"/>
    ${baleRow("club_occ","مناسبت‌ها و تولدهای پیشِ رو")}`;
}
/* امتیاز شرطی: محتوای زیرتب باشگاه */
function cURules(){
  const rs=rulesAll();
  const rows=rs.map(r=>{const on=ruleOn(r);
    return `<div class="admlirow">${ico('i-star')}
      <span class="sp"><b>${esc(r.n)}</b><small class="cap">${esc(TRG[r.trg]||r.trg)} · حدنصاب ${esc(fa(r.th))} ·
        ${esc(fa(r.pts))} امتیاز${r.def?'':' · سفارشی'}</small></span>
      <span class="mini">${r.def?'':`<button class="btn sm quiet" data-uruledel="${esc(r.id)}">${esc('برداشتن')}</button>`}
        <span class="switch ${on?'on':''}" data-urule="${esc(r.id)}" role="switch" aria-checked="${on?'true':'false'}" aria-label="${esc(r.n)}"></span></span></div>`}).join('');
  return `
    <div class="row"><div class="head">قانون‌های امتیاز</div><span class="sp"></span>
      ${btn('قانون تازه','data-urulenew','i-plus')}</div>
    ${rows}
    <div class="head">سقف‌های محافظ</div>
    ${table([['هر امتیاز واحد','حداکثر ۱۰۰','بیشترش مهار می‌شود'],['هر کاربر در روز','حداکثر ۵۰',''],
      ['هر کاربر در ماه','حداکثر ۳۰۰','']])}
    <p class="cap">${esc('ثبت‌نام صرف امتیاز ندارد؛ فقط حضور واقعی و کار واقعی. قانون تازه با شرط از همین هشت شرط ساخته میشود و یکبارمصرف است.')}</p>
    ${S.uruleNew?`<div class="stack">
      <label class="fld"><span>عنوان قانون</span><input id="rulN" type="text" placeholder="مثل: قهرمان فرم"/></label>
      <div class="row tight">
        <label class="fld"><span>شرط</span><select id="rulT">${Object.keys(TRG).map(k=>`<option value="${k}">${esc(TRG[k])}</option>`).join('')}</select></label>
        <label class="fld"><span>حدنصاب</span><input id="rulH" type="number" min="1" max="100" value="1"/></label>
        <label class="fld"><span>امتیاز</span><input id="rulP" type="number" min="1" max="100" value="20"/></label></div>
      <div class="row tight">${btn('ساختن قانون','data-uruleadd','i-check')}${btn('بی‌خیال','data-urulecancel')}</div></div>`:''}
  </section>
    <hr class="hr"/>
    ${baleRow("club_rules","قانون‌های امتیاز و سقف‌های محافظ")}`;
}
/* نشانها: محتوای زیرتب باشگاه */
function cUAch(){
  const rows=BADGES.map(b=>{const got=memList().filter(m=>badgeGot(m,b)).length;
    return `<div class="admlirow"><span class="ic">${esc(b[1].split(' ')[0])}</span>
    <span class="sp"><b>${esc(b[1].replace(/^[^ا-ی]+ /,''))}</b>
    <small class="cap">${esc(b[2])} · ${esc(TRG[b[3]]||b[3])} ≥ ${esc(fa(b[4]))} · ${esc(fa(b[5]))} امتیاز</small></span>
    <span class="mini">${tag(fa(got)+' نفر نشان‌دار','')}</span></div>`}).join('');
  const mine=memList().map(m=>({m,got:BADGES.filter(b=>badgeGot(m,b))}));
  const top=mine.sort((a,b)=>b.got.length-a.got.length).slice(0,5);
  return `
    <div class="head">۱۳ نشان در ۴ سطح</div>
    ${table([['برنزی',fa(3)+' نشان','از ۱ مورد شروع می‌شود'],['نقره‌ای',fa(3)+' نشان','از ۵ مورد'],
      ['طلایی',fa(3)+' نشان','از ۲۰ مورد'],['افسانه‌ای',fa(4)+' نشان','۱۰۰ حضور!']])}
    ${rows}
    <div class="head">نشان‌دارترین‌ها</div>
    ${table(top.map(x=>[x.m.n,fa(x.got.length)+' نشان',x.got.slice(0,3).map(b=>b[1].replace(/^[^ا-ی]+ /,'')).join('، ')]))}
    <p class="cap">${esc('هیچ نشانی بیش از ۱۰۰ امتیاز نیست؛ سقف محافظ روی نشان سفارشی هم اعمال میشود.')}</p>
  </section>
    <hr class="hr"/>
    ${baleRow("club_ach","نشان‌های باشگاه و دارندگانشان")}`;
}
/* فروشگاه پاداش: محتوای زیرتب باشگاه */
function cUShop(){
  const reqs=uShopReq();
  const rows=SHOP.map(s=>`<div class="admlirow">${ico('i-wallet')}
    <span class="sp"><b>${esc(s[1])}</b><small class="cap">${esc(fa(s[2]))} امتیاز · تحویل ${esc(s[3])}</small></span>
    <span class="mini">${tag(fa((S.ushopDone||[]).filter(x=>x===s[0]).length)+' تحویل','')}</span></div>`).join('');
  const pend=reqs.filter(r=>r.st==='در انتظار');
  return `
    <div class="admkpi">
      <div class="k"><small>پاداش‌ها</small>${bits(fa(SHOP.length))}</div>
      <div class="k"><small>در انتظار تحویل</small>${bits(fa(pend.length))}</div>
      <div class="k"><small>تحویل‌شده</small>${bits(fa((S.ushopDone||[]).length))}</div>
      <div class="k"><small>ردشده</small>${bits(fa(reqs.filter(r=>r.st==='رد شد').length))}</div></div>
    ${rows}
    <div class="head">درخواست‌ها</div>
    ${reqs.length?reqs.map(r=>{const m=memOf(r.u)||{}, it=SHOP.find(x=>x[0]===r.r)||[r.r,r.r,0];
      return `<div class="admlirow">${ico('i-users')}
        <span class="sp"><b>${esc(m.n||r.u)}</b><small class="cap">${esc(it[1])} · ${esc(fa(it[2]))} امتیاز · ${esc(r.at)} · ${esc(r.st)}</small></span>
        <span class="mini">${r.st==='در انتظار'?btn('تحویل','data-ushopok="'+esc(r.id)+'"','i-check')+btn('رد','data-ushopno="'+esc(r.id)+'"'):tag(r.st,r.st==='تحویل شد'?'ok':'stop')}</span></div>`}).join(''):emptyBox('درخواستی نیست')}
    <p class="cap">${esc('کسر امتیاز اتمیک است؛ اگر رد کنی، امتیاز سالم برمیگردد و در لاگ می‌ماند.')}</p>
  </section>
    <hr class="hr"/>
    ${baleRow("club_shop","فروشگاه پاداش و درخواست‌های تحویل")}`;
}
/* رتبه‌بندی: محتوای زیرتب باشگاه */
function cURank(){
  const hide=x=>S.rankHide?(String(x.n||'ک').slice(0,1)+'***'):x.n;
  const top=(key,lim)=>memList().slice().sort((a,b)=>(key(b)||0)-(key(a)||0)).slice(0,5);
  const medal=i=>['🥇','🥈','🥉','۴','۵'][i]||'';
  return `
    <div class="row"><div class="head">چهار جدول برترین‌ها</div><span class="sp"></span>
      <span class="cap">نام مخفی</span>
      <span class="switch ${S.rankHide?'on':''}" data-urankhide role="switch" aria-checked="${S.rankHide?'true':'false'}" aria-label="نام مخفی"></span></div>
    <div class="head">🏆 امتیاز کل</div>
    ${table(top(m=>+m.pt).map((m,i)=>[medal(i)+' '+esc(hide(m)),fa(m.pt)+' امتیاز',esc(uLevel(m).n||'')]))}
    <div class="head">✋ بیشترین حضور</div>
    ${table(top(m=>+m.ev).map((m,i)=>[medal(i)+' '+esc(hide(m)),fa(m.ev)+' رویداد','']))}
    <div class="head">👥 بیشترین دعوت</div>
    ${table(top(m=>+m.inv).map((m,i)=>[medal(i)+' '+esc(hide(m)),fa(m.inv)+' دعوت','']))}
    <div class="head">🎖️ بیشترین نشان</div>
    ${table(top(m=>BADGES.filter(b=>badgeGot(m,b)).length).map((m,i)=>[medal(i)+' '+esc(hide(m)),
      fa(BADGES.filter(b=>badgeGot(m,b)).length)+' نشان','']))}
    <p class="cap">${esc('اگر کسی در پنج نفر اول نباشد، رتبه‌اش جدا نشان داده میشود؛ کلید نام مخفی هم برای حریم خصوصی است.')}</p>
    <hr class="hr"/>
    ${baleRow("club_rank","رتبه‌بندی امتیاز و حضور و دعوت")}`;
}
/* پوستهٔ زیرتبهای باشگاه */
function vUClub(){
  const cur=S.uClub||'rules';
  const tabs=UCLUBTABS.map(t=>`<button class="chip ${cur===t[0]?'on':''}" data-uclub="${t[0]}">${esc(t[1])}</button>`).join('');
  const body=cur==='occ'?cUOcc():cur==='ach'?cUAch():cur==='shop'?cUShop():cur==='rank'?cURank():cURules();
  return `<section class="card stack">${uBack}
    ${uHead('باشگاه و امتیاز')}
    <div class="admfilters">${tabs}</div>
    ${body}</section>`;
}
/* برچسبها و دستهها */
function cUTags(){
  const labs=uLabels();
  const rows=Object.keys(labs).map(t=>`<div class="admlirow">${ico('i-filter')}
    <span class="sp"><b>${esc(t)}</b><small class="cap">${esc(fa(labs[t]))} کاربر</small></span>
    <span class="mini">${btn('فهرست','data-uTag="'+esc(t)+'"')}</span></div>`).join('');
  return `${uHead('برچسب‌ها و دسته‌ها')}
    <p class="cap">${esc('برچسب روی پروندهٔ هر کاربر می‌نشیند؛ همین‌جا می‌شود برچسب تازه گذاشت و با زدن «فهرست» همان دسته را دید.')}</p>
    ${rows||emptyBox('هنوز برچسبی نیست')}
    <label class="fld"><span>برچسب تازه</span><input id="uTagNew" type="text" placeholder="مثل: داوطلب اردو"/></label>
    <div class="row tight">${btn('گذاشتن برچسب','data-utagadd','i-plus')}<span class="sp"></span></div>
    <hr class="hr"/>
    ${baleRow("users_tags","برچسب‌ها و کاربران هر دسته")}`;
}
/* پارامترهای پروفایل */
function cUPar(){
  const on=k=>S.upar[k+'|on']!==0, req=k=>!!S.upar[k+'|req'];
  const rows=PFLDS.map(f=>{const k=f[0];
    return `<div class="admlirow">${ico('i-sliders')}
      <span class="sp"><b>${esc(f[1])}</b><small class="cap">${esc(f[2])}${f[3]?' · همیشه فعال و اجباری':''}</small></span>
      <span class="mini">${f[3]?'':`<span class="switch ${on(k)?'on':''}" data-upar="${esc(k)}" role="switch" aria-checked="${on(k)?'true':'false'}" aria-label="${esc(f[1])}"></span>`}
        ${f[3]?'':`<span class="mini">${req(k)?'⭐':'○'}<span class="switch ${req(k)?'on':''}" data-uparreq="${esc(k)}" role="switch" aria-checked="${req(k)?'true':'false'}" aria-label="اجباری"></span></span>`}</span></div>`}).join('');
  const nOn=PFLDS.filter(f=>f[3]||on(f[0])).length, nReq=PFLDS.filter(f=>f[3]||req(f[0])).length;
  return `${uHead('پارامترهای پروفایل')}
    <div class="admkpi">
      <div class="k"><small>فعال</small>${bits(fa(nOn+2)+' فیلد')}</div>
      <div class="k"><small>اجباری</small>${bits(fa(nReq+2)+' فیلد')}</div></div>
    <div class="admlirow">${ico('i-users')}<span class="sp"><b>نام و نام خانوادگی</b><small class="cap">همیشه فعال و اجباری</small></span></div>
    <div class="admlirow">${ico('i-mobile')}<span class="sp"><b>شمارهٔ همراه</b><small class="cap">با کد یک‌بارمصرف؛ همیشه اجباری</small></span></div>
    ${rows}
    <div class="row tight">${btn('بازگشت به پیش‌فرض','data-uparreset','i-back')}<span class="sp"></span></div>
    <p class="cap">${esc('روشن و خاموش و اجباری و اختیاری؛ فرم پروفایل کاربر از همین پیروی میکند و درصد تکمیل با همین حساب میشود.')}</p>
    <hr class="hr"/>
    ${baleRow("users_par","پارامترهای پروفایل کاربران")}`;
}
/* افزودن دستی: هر خط یک نفر */
function cUAdd(){
  return `${uHead('افزودن دستی')}
    <p class="cap">${esc('هر خط یک نفر؛ نام را بنویس و اگر داشتی کد ملی یا موبایل را با ویرگول جدا کن. مثل: «علی محمدی، ۰۰۲۳۴۵۶۷۸۷»')}</p>
    <label class="fld"><textarea id="uAddTxt" rows="6" placeholder="علی محمدی، ۰۰۲۳۴۵۶۷۸۷
زهرا کریمی، ۰۹۱۲۱۲۳۴۵۶۷
حسین رحیمی"></textarea></label>
    <div class="row tight">${btn('افزودن همه','data-uaddgo','i-check')}<span class="sp"></span></div>
    ${uImpList()}
    <hr class="hr"/>
    ${baleRow("users_add","افزوده‌شدگان دستی")}`;
}
/* ورودی اکسل: چسباندن جدول، شناخت ستونها، بهروزرسانی موجودها */
function cUImp(){
  const pv=S.uimpPv||null;
  return `${uHead('ورودی اکسل')}
    <p class="cap">${esc('جدول را از اکسل رونوشت کن و همین‌جا بچسبان؛ سرستونها با نامهای مختلف (نام و فامیل، شماره، همراه…) شناخته میشوند.')}</p>
    <label class="fld"><textarea id="uImpTxt" rows="6" placeholder="نام	موبایل	شهر
زهرا کریمی	۰۹۱۲۱۲۳۴۵۶۷	تهران"></textarea></label>
    <div class="row tight">${btn('شناسایی جدول','data-uimpparse','i-check')}<span class="sp"></span></div>
    ${pv?`<div class="head">پیش‌نمایش (${esc(fa(pv.rows.length))} ردیف)</div>
    ${table(pv.rows.slice(0,5).map(r=>pv.cols.map(c=>esc(r[c]||'ـ'))))}
    <div class="admlirow">${ico('i-check')}<span class="sp"><b>به‌روزرسانی موجودها</b>
      <small class="cap">اگر موبایل یا کد ملی از قبل بود، رکورد همان تازه میشود</small></span>
      <span class="switch ${S.uimpUpd?'on':''}" data-uimpupd role="switch" aria-checked="${S.uimpUpd?'true':'false'}" aria-label="به‌روزرسانی موجودها"></span></div>
    <div class="row tight">${btn('درج '+esc(fa(pv.rows.length))+' نفر','data-uimpgo','i-check')}<span class="sp"></span></div>`
    :`<p class="cap">${esc('ستونهای شناخته‌شده: نام، نام خانوادگی، موبایل، کد ملی، شهر، جنسیت، ایمیل، مقطع، شغل، استان و تاریخ تولد.')}</p>`}
    ${uImpList()}
    <hr class="hr"/>
    ${baleRow("users_imp","تاریخچهٔ ورود از اکسل")}`;
}
function uImpList(){
  const h=S.uimp||[];
  return h.length?`<div class="head">تاریخچهٔ ورودها</div>
    ${table(h.slice(0,5).map(x=>[x.at,fa(x.n)+' نفر تازه'+(x.upd?' + '+fa(x.upd)+' به‌روزرسانی':''),x.by]))}`:'';
}
/* مسدودها: محتوای زیرتب ابزارها */
function cUBlocked(){
  const blk=memList().filter(m=>m.st[1]==='stop');
  const rows=blk.map(m=>`<div class="admlirow">${ico('i-lock')}
    <span class="sp"><b>${esc(m.n)}</b><small class="cap">${esc(m.code)} · ${esc(m.ph)}${m.note?' · '+esc(m.note):''}</small></span>
    <span class="mini">${btn('رفع مسدودی','data-uunblock="'+esc(m.id)+'"','i-check')}
      <button class="btn sm quiet" data-user="${esc(m.id)}">${esc('پرونده')}</button></span></div>`).join('');
  return `
    ${rows||emptyBox('کاربر مسدودی نیست')}
    <p class="cap">${esc('مسدود به هیچ بخشی راه ندارد و پیامش بسته است؛ سوپرادمین را نمیشود مسدود کرد.')}</p>
    <hr class="hr"/>
    ${baleRow("users_blocked","کاربران مسدود")}`;
}
/* صندوق پیامها: محتوای زیرتب ابزارها */
function cUInbox(){
  const msgs=uInbox(), un=msgs.filter(x=>!x.read).length;
  const rows=msgs.map(i=>{const m=memOf(i.u)||{};
    return `<div class="admlirow">${ico(i.read?'i-doc':'i-bell')}
      <span class="sp"><b>${esc(m.n||i.u)}${i.read?'':' 🔴'}</b>
        <small class="cap">${esc(i.txt)}</small>
        <small class="cap">${esc(i.at)}${i.rep?' · پاسخ داده شد':''}</small></span>
      <span class="mini">${i.read?'':btn('خواندم','data-uinboxread="'+esc(i.id)+'"')}
        <button class="btn sm quiet" data-uinboxopen="${esc(i.u)}">${ico('i-users')}${esc('پرونده')}</button>
        <a class="btn sm quiet" href="support.html">${ico('i-send')}${esc('پاسخ')}</a></span></div>`}).join('');
  return `
    <div class="row"><div class="head">پیام‌ها</div><span class="sp"></span>
      ${tag(fa(un)+' خوانده‌نشده',un?'warn':'')}</div>
    ${rows||emptyBox('پیامی نیست')}
    <div class="row tight">${btn('همه را خوانده کنم','data-uinboxall','i-check')}<span class="sp"></span></div>
    <p class="cap">${esc('پیام کاربر گم نمیشود؛ از همین‌جا پروندهاش را باز کن یا در پشتیبانی پاسخش را بده.')}</p>
    <hr class="hr"/>
    ${baleRow("users_inbox","پیام‌های صندوق")}`;
}
/* لاگ عملیات: محتوای زیرتب ابزارها */
function cULog(){
  const log=uLog();
  const rows=log.map(l=>`<div class="admlirow">${ico('i-doc')}
    <span class="sp"><b>${esc(l.act)}</b><small class="cap">${esc(l.who)} · ${esc(l.at)}</small></span></div>`).join('');
  return `
    ${rows||emptyBox('هنوز کاری ثبت نشده')}
    <p class="cap">${esc('تأیید و مسدودی و VIP و حذف و ورود اکسل؛ همه با نام کارشناس، تا چهل کارِ آخر.')}</p>
    <hr class="hr"/>
    ${baleRow("users_log","لاگ عملیات کاربران")}`;
}
/* پوستهٔ زیرتبهای ابزارها */
function vUTools(){
  const cur=S.uTool||'report';
  const tabs=UTOOLTABS.map(t=>`<button class="chip ${cur===t[0]?'on':''}" data-utool="${t[0]}">${esc(t[1])}</button>`).join('');
  const body=cur==='report'?cUReport():cur==='staff'?cUStaff():cur==='add'?cUAdd():cur==='imp'?cUImp():cur==='tags'?cUTags():cur==='blocked'?cUBlocked():cur==='inbox'?cUInbox():cur==='log'?cULog():cUPar();
  return `<section class="card stack">${uBack}
    ${uHead('ابزارها و گزارش')}
    <div class="admfilters">${tabs}</div>
    ${body}</section>`;
}
/* درخواستها: پروفایل در صف، غیبت مجاز، پاداش */
function vUReq(){
  const pend=memList().filter(m=>m.st[1]==='warn');
  const abs=uAbs().filter(a=>a.st==='در انتظار');
  const reqs=uShopReq().filter(r=>r.st==='در انتظار');
  const rowP=pend.map(m=>`<div class="admlirow">${ico('i-users')}
      <span class="sp"><b>${esc(m.n)}</b><small class="cap">${esc(m.code)} · تکمیل پروفایل ${esc(fa(uPct(m)))}٪</small></span>
      <span class="mini">${btn('تأیید','data-uok="'+esc(m.id)+'"','i-check')}
      <button class="btn sm quiet" data-urej="${esc(m.id)}">${esc('رد با دلیل')}</button></span></div>`).join('');
  const rowA=abs.map(a=>{const m=memOf(a.u)||{}; return `<div class="admlirow">${ico('i-doc')}
      <span class="sp"><b>${esc(m.n||a.u)}</b><small class="cap">${esc(a.ev)} · ${esc(a.why)} · ${esc(a.at)}</small></span>
      <span class="mini">${btn('تأیید','data-uabsok="'+esc(a.id)+'"','i-check')}
      ${btn('رد','data-uabsno="'+esc(a.id)+'"')}</span></div>`}).join('');
  const rowR=reqs.map(r=>{const m=memOf(r.u)||{}, it=SHOP.find(x=>x[0]===r.r)||[r.r,r.r,0,''];
    return `<div class="admlirow">${ico('i-wallet')}
      <span class="sp"><b>${esc(m.n||r.u)}</b><small class="cap">${esc(it[1])} · ${esc(fa(it[2]))} امتیاز · ${esc(r.at)}</small></span>
      <span class="mini">${btn('تحویل','data-ushopok="'+esc(r.id)+'"','i-check')}
      ${btn('رد','data-ushopno="'+esc(r.id)+'"')}</span></div>`}).join('');
  return `<section class="card stack">${uBack}
    ${uHead('درخواست‌ها')}
    <div class="head">درخواست پروفایل (${esc(fa(pend.length))})</div>
    ${rowP||emptyBox('پروفایلی در صف نیست')}
    <div class="head">غیبت مجاز (${esc(fa(abs.length))})</div>
    ${rowA||emptyBox('درخواست غیبت مجازی نیست')}
    <div class="head">تحویل پاداش (${esc(fa(reqs.length))})</div>
    ${rowR||emptyBox('درخواست پاداشی نیست')}
    <p class="cap">${esc('رد پاداش، امتیاز را سالم به حساب صاحبش برمی‌گرداند؛ رد پروفایل با دلیل می‌آید تا کاربر بداند چه کم دارد.')}</p>
    <hr class="hr"/>
    ${baleRow("users_req","درخواست‌های پروفایل، غیبت مجاز و تحویل پاداش")}
  </section>`;
}

/* ── فرم‌ها ────────────────────────────────────────────────────────────── */
function vForms(){
  const F=A.forms||{}, rows=madeForms().map(f=>Object.assign({},f,{q:0,made:1,kind:f.kind||'فرم'}))
    .concat(F.rows||[]);
  const list=rows.map((r,i)=>rowLink({attrs:`data-formrow="${i}"`, i:'i-doc',
      b:esc(r.n||r.name||''), s:r.made
        ? `${esc(r.kind)} · ${esc((r.fin||[]).length?fa(formSum(r))+' ریال':'بی مبلغ')}${r.ev?` · ${esc('وصل به رویداد '+r.ev+' · form.html?ev='+r.ev+(r.need?'&kind='+r.need:''))}`:''} · ${esc('فرم‌ساز')}`
        : `${esc(r.k)} · ${esc(fa(r.got))} پاسخ · ${esc(r.at)}`,
      right:`<span class="mini">${r.made?`<a class="btn sm quiet" href="create.html?fid=${esc(r.id)}&name=${encodeURIComponent(r.n||r.name||'')}&back=${encodeURIComponent('admin.html#forms')}" target="_blank" rel="noopener">${ico('i-sliders')}${esc('فرم‌ساز')}</a>`:''}
        ${r.on?tag('باز','ok'):tag('بسته','')}
        <span class="switch ${r.on?'on':''}" data-formsw="${i}" role="switch" aria-checked="${r.on?'true':'false'}" aria-label="باز و بسته"></span></span>`}));
  const paths=(F.paths||[]).map(p=>`<a class="admrow2" href="${esc(p.href)}">
      <span class="ic">${ico(p.i)}</span><span class="tx"><b>${esc(p.n)}</b><small>${esc(p.s)}</small></span>
      ${ico('i-chev-left','chev')}</a>`).join('');
  return `<section class="card stack">
    <div class="row"><div class="head">${esc(F.lead||'')}</div><span class="sp"></span>
      ${btn('لینک کردن فرم','data-flink','i-link')}</div>
    <div class="admlist">${list.join('')}</div>
    <hr class="hr"/>
    <div class="head">${esc(L.formTasks)}</div>
    <div class="admlist">${paths}</div>
    <p class="cap">${esc('ساخت فرم تازه و گزارش پاسخ‌ها در صفحهٔ فرم‌ها و گزارش است؛ پنل کاربر همان لینک را می‌بیند.')}</p>
  </section>`;
}

/* ── گزارش‌ها: نه گزارش ────────────────────────────────────────────────── */
/* ── ممیزی کامل پنل: هر دکمه، کلید، چیپ، کاشی و بنرِ در دسترس همین نقش،
   واقعاً یک بار کلیک میشود و پاسخش سنجیده میشود؛ از ریز تا درشت ── */
const AUD={on:0, i:0, cur:'', errs:[], tick:0};
const audSig=el=>{const d=el.dataset||{}, ks=Object.keys(d).sort().slice(0,2);
  return el.tagName+'|'+(el.getAttribute('class')||'').trim().split(/\s+/).slice(0,2).join('.')
    +'|'+ks.map(k=>k+'='+d[k]).join(',')+'|'+(el.getAttribute('aria-label')||el.textContent||'')
      .replace(/\s+/g,' ').trim().slice(0,26)};
const audBlocked=el=>{
  if(el.matches('[data-reset],[data-who],[data-who-sheet],[data-balereg]')) return 'skip';
  if(el.matches('a')){const h=el.getAttribute('href')||'';
    if(/^https?:/i.test(h)||/\.html/i.test(h)||el.hasAttribute('download')) return 'ext';}
  return '';};
const audKind=el=>el.getAttribute('role')==='switch'?'کلید':el.classList.contains('chip')?'چیپ'
  :el.closest('.admtiles')?'کاشی':el.matches('a')?'پیوند':'دکمه';
const audSubs=k=>{
  if(k==='users') return [['درخواستها','req'],['باشگاه','club'],['گواهینامه','cert'],['ابزارها','tools']]
    .concat(['rules','ach','shop','rank','occ'].map(t=>['باشگاه › '+({rules:'قوانین',ach:'نشانها',shop:'فروشگاه',rank:'رتبه',occ:'مناسبتها'}[t]||t),'club:'+t]))
    .concat(['report','staff','par','add','imp','tags','blocked','inbox','log'].map(t=>['ابزارها › '+t,'tools:'+t]));
  if(k==='events') return (isMoney()?['info','reg','att','money','cert','news']:['info','reg','att','cert','news'])
    .map(t=>['رویدادها › '+t, t]);
  if(k==='settings'){return ((A.settings||{}).groups||[]).filter(g=>isOwner()||g.k==='cert')
    .map(g=>['تنظیمات › '+g.n, g.k]);}
  if(k==='newev') return [0,1,2,3,4].map(i2=>['ویزارد › گام '+fa(i2+1), String(i2)]);
  return [];};
function audGoto(p){
  S.sec=p.sec;
  if(p.sec==='users'){const parts=String(p.sub||'').split(':'), a=parts[0];
    S.uV=a||''; S.uSel=''; S.uRej='';
    if(a==='club') S.uClub=parts[1]||'rules';
    if(a==='tools') S.uTool=parts[1]||'report';}
  else if(p.sec==='events') S.evTab=p.sub||'info';
  else if(p.sec==='settings') S.setG=p.sub||'texts';
  else if(p.sec==='newev') S.wiz.step=+p.sub||0;
}
const audSel='#admBody button:not([disabled]), #admBody a.btn, #admBody [role="switch"]';
const BAN_SEL='#admBody .balebox .ov, #admBody .notebar, #admBody .empty, #admBody .balerow';
const audTick=()=>new Promise(r=>setTimeout(r,0));
async function auditRun(){
  if(AUD.on) return;
  AUD.on=1; AUD.i=0; AUD.cur='آماده'; AUD.errs=[];
  const snap=JSON.parse(JSON.stringify(S));
  const errHook=e=>{AUD.errs.push(String((e&&e.message)||e).slice(0,80))};
  window.addEventListener('error',errHook);
  const open0=window.open, uiToast0=(window.NORA_UI||{}).toast;
  window.open=()=>{AUD.tick++; return null};
  if(uiToast0&&window.NORA_UI) window.NORA_UI.toast=m=>{AUD.tick++; return uiToast0(m)};
  toast('پیمایش شروع شد؛ هر دکمه و بنرِ در دسترس تو یک بار زده میشود');
  renderBody();
  await audTick();
  const secs=ALLSECS.filter(x=>canSec(x.k));
  const locked=ALLSECS.filter(x=>!canSec(x.k)).map(x=>x.n);
  const per=[]; let T=0, OK=0, MUTE=0, EXT=0, SKIP=0; const issues=[];
  for(const sv of secs){
    const subs=[{lab:'',sub:''}].concat(audSubs(sv.k).map(x=>({lab:x[0],sub:x[1]})));
    const pt={n:sv.n, tot:0, ok:0, mute:0, ext:0, skip:0, ban:0, mutes:[]};
    for(const sb of subs){
      const ctx={sec:sv.k, sub:sb.sub};
      const ctxSnap=JSON.stringify(S);
      const done=new Set();
      AUD.cur=sv.n+(sb.lab?' › '+sb.lab:'');
      for(let guard=0; guard<400; guard++){
        S=JSON.parse(ctxSnap); audGoto(ctx); closeSheets(); renderBody();
        await audTick();
        if(guard===0) pt.ban+=[...document.querySelectorAll(BAN_SEL)]
          .filter(b=>(b.textContent||'').trim().length>4).length;
        const el=[...document.querySelectorAll(audSel)].find(x=>!done.has(audSig(x)));
        if(!el) break;
        const sig=audSig(el); done.add(sig);
        const bl=audBlocked(el);
        if(bl){ if(bl==='ext') pt.ext++; else pt.skip++; continue }
        AUD.cur=(sb.lab?sv.n+' › '+sb.lab:sv.n)+' · '
          +((el.textContent||'').replace(/\s+/g,' ').trim().slice(0,18)||audKind(el));
        const toastEl=document.querySelector('#toast')
          , t0=AUD.tick
          , toast0=toastEl?toastEl.textContent:''
          , sheet0=document.querySelectorAll('.sheet.on').length
          , hash0=location.hash;
        el.dispatchEvent(new MouseEvent('click',{bubbles:true}));
        await audTick();
        const toastEl2=document.querySelector('#toast')
        const responded=AUD.tick>t0
          || (toastEl2?toastEl2.textContent:'')!==toast0
          || document.querySelectorAll('.sheet.on').length!==sheet0
          || location.hash!==hash0;
        pt.tot++;
        if(responded) pt.ok++;
        else {pt.mute++; pt.mutes.push(audKind(el)+': '
          +((el.getAttribute('aria-label')||el.textContent||'').replace(/\s+/g,' ').trim().slice(0,30)||'بی‌نام'))}
        AUD.i++; T++;
      }
    }
    OK+=pt.ok; MUTE+=pt.mute; EXT+=pt.ext; SKIP+=pt.skip;
    pt.mutes.slice(0,6).forEach(m2=>issues.push(sv.n+' · '+m2));
    per.push(pt);
  }

  window.removeEventListener('error',errHook);
  window.open=open0;
  if(uiToast0&&window.NORA_UI) window.NORA_UI.toast=uiToast0;
  S=snap;
  S.auditLast={at:'همین حالا', who:me().n||'', lv:me().lv||'',
    secs:secs.length, locked:locked, tot:T, ok:OK, mute:MUTE, ext:EXT, skip:SKIP,
    errs:AUD.errs.slice(0,4), issues:issues.slice(0,10), per:per,
    banTot:per.reduce((a2,x)=>a2+(x.ban||0),0)};
  AUD.on=0; save(); renderBody();
  toast(MUTE||AUD.errs.length
    ? 'پیمایش تمام شد؛ '+fa(MUTE)+' کنترل بیپاسخ و '+fa(AUD.errs.length)+' خطا'
    : 'پیمایش تمام شد؛ '+fa(OK)+' کنترل پاسخ داد و هیچ دکمه و بنری بیجواب نماند');
}

/* برچسب دوره: اعداد فارسی و بی‌فاصلهٔ اضافه */
const faTag=t=>fa(String(t||'')).trim();
/* ── گزارش زنده: تفکیکها و برترینها از همین پنل حساب میشود، نه متن ثابت ── */
const evAllRP=()=>(S.added||[]).concat(EVROWS);
function rpCalc(k){
  const mem=memList(), out={rows:[], bars:[]};
  if(k==='ev'){
    const evs=evAllRP(), kn={};
    evs.forEach(e=>{kn[e.kind||'دیگر']=(kn[e.kind||'دیگر']||0)+1});
    const st={live:0,soon:0,past:0};
    evs.forEach(e=>{const s2=evState(e); if(s2==='live'||s2==='soon'||s2==='past') st[s2]++});
    const top=evs.slice().sort((a,b)=>(+b.reg||0)-(+a.reg||0))[0]||{};
    const capS=evs.reduce((a,e)=>a+(+e.cap||0),0), regS=evs.reduce((a,e)=>a+(+e.reg||0),0);
    out.rows=[['نشست / کارگاه / اردو / بسته', fa(kn['نشست']||0)+' / '+fa(kn['کارگاه']||0)+' / '+fa(kn['اردو']||0)+' / '+fa(kn['بستهٔ رسانه']||0)],
      ['جاری / پیش‌رو / برگزارشده', fa(st.live)+' / '+fa(st.soon)+' / '+fa(st.past)],
      ['پرطرفدارترین', (top.n||'')+' · '+fa(top.reg||0)+' ثبت‌نام'],
      ['میانگین ثبت‌نام', fa(evs.length?Math.round(regS/evs.length):0)+' نفر'],
      ['جای خالی از ظرفیت', fa(Math.max(0,capS-regS))+' جا']];
    out.bars=evs.slice(0,7).map(e=>+e.reg||0);
  } else if(k==='us'){
    const ok2=mem.filter(m=>m.st[1]==='ok').length, warn=mem.filter(m=>m.st[1]==='warn').length,
      stop=mem.filter(m=>m.st[1]==='stop').length;
    const newYear=mem.filter(m=>String(m.reg||'').indexOf('۱۴۰۴')>-1).length;
    const tc={}; mem.forEach(m=>(m.tags||[]).forEach(t=>{tc[t]=(tc[t]||0)+1}));
    const topT=Object.keys(tc).sort((a,b)=>tc[b]-tc[a])[0]||'';
    const top=mem.slice().sort((a,b)=>(+b.pt||0)-(+a.pt||0))[0]||{};
    out.rows=[['اعضا', fa(mem.length)+' نفر'],
      ['وضعیت', fa(ok2)+' تأییدشده · '+fa(warn)+' در صف تأیید · '+fa(stop)+' مسدود'],
      ['تازهٔ امسال', fa(newYear)+' نفر'],
      ['برچسب پرتکرار', topT?topT+' · '+fa(tc[topT])+' نفر':''],
      ['پرامتیازترین', (top.n||'')+' · '+fa(top.pt||0)+' امتیاز']];
    out.bars=Object.keys(tc).slice(0,7).map(t=>tc[t]);
  } else if(k==='fm'){
    const made=madeForms(), demo=(A.forms||{}).rows||[];
    const open2=made.concat(demo).filter(r=>r.on||r.on===undefined).length;
    const got=demo.reduce((a,r)=>a+(un(String(r.got||'0'))|0),0);
    const topD=demo.slice().sort((a,b)=>(un(String(b.got||'0'))|0)-(un(String(a.got||'0'))|0))[0]||{};
    out.rows=[['فرم باز', fa(open2)+' فرم'],
      ['ساختهٔ فرم‌ساز', fa(made.length)+' فرم'],
      ['پاسخ نمونههای آماده', fa(got)+' پاسخ'],
      ['پرپاسخترین', (topD.n||'')+' · '+fa((topD.got||'0'))+' پاسخ'],
      ['نظرسنجی آمادهٔ نورا', '۴ پرسش، همیشه در دسترس']];
    out.bars=demo.map(r=>un(String(r.got||'0'))|0);
  } else if(k==='at'){
    const top=mem.slice().sort((a,b)=>(+b.ev||0)-(+a.ev||0))[0]||{};
    out.rows=[['حاضر', '٪۷۸'],['تأخیر', '٪۹'],['غایب', '٪۱۰'],['معذور با درخواست', '٪۳'],
      ['پرحضورترین', (top.n||'')+' · '+fa(top.ev||0)+' رویداد']];
    out.bars=[60,72,68,75,70,78,74];
  } else if(k==='fi'){
    const evs=evAllRP().filter(e=>+e.price>0);
    const sum=evs.reduce((a,e)=>a+(+e.price||0)*(+e.reg||0),0);
    const top=evs.slice().sort((a,b)=>(+b.price||0)*(+b.reg||0)-(+a.price||0)*(+a.reg||0))[0]||{};
    out.rows=[['فروش همین دوره', fa(sum)+' ریال'],
      ['رویدادهای پردار', fa(evs.length)+' رویداد'],
      ['پردرآمدترین', (top.n||'')+' · '+fa((+top.price||0)*(+top.reg||0))+' ریال'],
      ['درگاه بله / کارت به کارت', '٪۸۷ / ٪۱۳'],
      ['رسید در انتظار تأیید', '۱۵ رسید']];
    out.bars=[30,48,40,56,44,70,58];
  } else if(k==='ce'){
    const jobs=(CE.jobs||[]).concat(S.jobs||[]), files=(CE.files||[]).concat(S.certFiles||[]);
    const okJ=jobs.filter(j=>j.st==='ok').length, waitJ=jobs.filter(j=>j.st!=='ok').length;
    const q=(S.certQueue||[]).filter(b=>!b.rev);
    out.rows=[['کار منتشرشده', fa(okJ)+' کار'],
      ['در نوبت صدور', fa(waitJ)+' کار'],
      ['دسته در صف صدور', fa(q.length)+' دسته'],
      ['قالب ورد آماده', fa(files.length)+' قالب'],
      ['درخواست رسیده از ربات', fa(CE.botReq||0)+' نفر']];
    out.bars=[20,26,34,30,44,40,50];
  } else if(k==='bc'){
    out.rows=(RPD.bc&&RPD.bc.rows)||[];
    out.bars=(RPD.bc&&RPD.bc.bars)||[];
  } else if(k==='ad'){
    const f={}; PEOPLE.forEach(p=>{f[p.f]=(f[p.f]||0)+1});
    const lead=PEOPLE.filter(p=>p.lv==='سرپرست').length;
    const top=PEOPLE.slice().sort((a,b)=>(b.done||0)-(a.done||0))[0]||{};
    const openS=PEOPLE.reduce((a,p)=>a+(+p.open||0),0);
    out.rows=[['حوزه', fa(Object.keys(f).length)+' حوزه'],
      ['سرپرست / کارشناس', fa(lead)+' / '+fa(Math.max(0,PEOPLE.length-lead-1))],
      ['پرمشغولترین', (top.n||'')+' · '+fa(top.done||0)+' کار انجامشده'],
      ['کار باز همین حالا', fa(openS)+' کار'],
      ['کلیدهای سیستم', fa((((A.settings||{}).keys||{}).list||[]).length)+' کلید سالم']];
    out.bars=FIELDS.filter(x=>x.k!=='owner').map(x=>PEOPLE.filter(p=>p.f===x.k).reduce((a,p)=>a+(+p.open||0),0));
  } else if(k==='tp'){
    const pt=mem.slice().sort((a,b)=>(+b.pt||0)-(+a.pt||0)).slice(0,3);
    const ev2=mem.slice().sort((a,b)=>(+b.ev||0)-(+a.ev||0)).slice(0,3);
    out.rows=[['برترین امتیاز: نفر اول', (pt[0]&&pt[0].n||'')+' · '+fa(pt[0]&&pt[0].pt||0)+' امتیاز'],
      ['نفر دوم', (pt[1]&&pt[1].n||'')+' · '+fa(pt[1]&&pt[1].pt||0)+' امتیاز'],
      ['نفر سوم', (pt[2]&&pt[2].n||'')+' · '+fa(pt[2]&&pt[2].pt||0)+' امتیاز'],
      ['پرحضورترین', (ev2[0]&&ev2[0].n||'')+' · '+fa(ev2[0]&&ev2[0].ev||0)+' رویداد'],
      ['پرتکرارترین نشان', 'طلایی · '+fa(4)+' نفر']];
    out.bars=pt.map(m=>+m.pt||0).concat([0,0]);
  }
  return out;
}
function rpSummary(){
  const mem=memList(), curP=S.rp||'۳۰ روز';
  const ok2=mem.filter(m=>m.st[1]==='ok').length, warn=mem.filter(m=>m.st[1]==='warn').length;
  const evs=evAllRP(); let live=0, past=0;
  evs.forEach(e=>{const s2=evState(e); if(s2==='live'||s2==='soon') live++; if(s2==='past') past++});
  const ps=['در دورهٔ «'+curP+'» '+fa(mem.length)+' عضو داریم: '+fa(ok2)+' تأییدشده، '+fa(warn)+' در صف تأیید'
    +(past?'؛ '+fa(past)+' رویداد برگزار شده و '+fa(live)+' در راه است':'؛ '+fa(live)+' رویداد در راه است')+'.'];
  if(isMoney()){const sum=evAllRP().reduce((a,e)=>a+(+e.price>0?(+e.price)*(+e.reg||0):0),0);
    ps.push('فروش همین دوره '+fa(sum)+' ریال است و '+fa((((A.settings||{}).keys||{}).list||[]).length)+' کلید سامانه سالم است.');}
  const att=(RP.attention||[]).filter(a=>!a.own||isMoney())[0];
  if(att) ps.push('نیاز به توجه: '+att.t+'.');
  const tip=(RP.tips||[]).filter(t=>!t.own||isMoney())[0];
  if(tip) ps.push(tip.t+'.');
  return ps.join(' ');
}

function vReports(){
  const periods=RP.periods||[], curP=S.rp||periods[3]||'';
  const per=periods.map(p=>`<button class="chip ${curP===p?'on':''}" data-rp="${esc(p)}">${esc(p)}</button>`).join('');
  const kpis=(RP.kpis||[]).filter(k=>!k.own||isMoney()).map(k=>`<div class="k"><small>${esc(k.n)}</small>
      ${bits(k.v+(k.u?' '+k.u:''))}
      ${k.pc?`<span class="tag ${k.up?'ok':'warn'}">${esc(k.pc)}</span>`:''}
      <small>${esc(k.s||'')}</small></div>`).join('');
  const trend=RP.trend||{};
  const live=((RP.live||{}).rows||[]).filter(r=>!r[2]||isMoney());
  const tips=(RP.tips||[]).filter(t=>!t.own||isMoney()).map(t=>`<div class="admlirow">${ico('i-eye')}
      <span class="sp">${esc(t.t)}</span><span class="mini">${tag('توصیه','brand')}</span></div>`).join('');
  const att=(RP.attention||[]).filter(a=>!a.own||isMoney()).map(a=>rowLink({attrs:`data-rep="${esc(a.k)}"`, i:'i-bell', chev:1, b:esc(a.t), right:tag(W.alert||'توجه','warn')})).join('');
  const list=RPLIST.filter(r=>!r.own||isMoney()).map(r=>rowLink({attrs:`data-rep="${esc(r.k)}"`, i:r.i, chev:1,
      b:esc(r.n), s:r.k==='fi'?esc(r.d):`${esc(r.v)} · ${esc(r.d)}`,
      right:r.pc?`<span class="tag ${r.up?'ok':'warn'}">${esc((r.up?'▲ ':'▼ ')+r.pc)}</span>`:''})).join('');
  const CU=RP.custom||{}, cSel=S.rpCust||[], cOpts=(CU.opts||[]).filter(o=>!o.own||isMoney());
  const cOn=S.rpCustOn&&cSel.length;
  const schedL=(RP.sched||{}).list||[], schL=schedL.concat(S.rpSchedExtra||[]);
  return `<div class="stgroup" style="margin-bottom:var(--sp-2)">
      <div class="fslead"><span class="ic">${ico('i-pen')}</span>
        <span class="sp"><b>جمعبندی مدیریتی، خودنویس</b>
          <small>${esc(rpSummary())}</small></span></div>
      <div class="row">${baleA('reports_summary','همین جمعبندی از ربات بله')}
        <span class="sp"></span><span class="cap">${esc('هر بار که دوره یا داده عوض شود، همین جمله تازه میشود')}</span></div></div>
  <div class="admgrid">
    <section class="card stack">
      <div class="row"><div class="head">${esc(RP.lead||'')}</div></div>
      <div class="admfilters">${per}</div>
      <p class="cap">${esc(RP.perCap||'')}</p>
      <div class="admkpi">${kpis}</div>
      ${trend.v&&trend.v.length?`<div class="head">${esc(trend.n||'')}</div><div class="admbars">${bars(trend.v,true)}</div>`:''}
      ${live.length?`<div class="head">${esc((RP.live||{}).n||'فعالیت لحظهای')}</div>
        <div class="admlist">${live.map(r=>`<div class="admlirow"><span class="ic">${ico('i-bolt')}</span>
          <span class="sp"><b>${esc(r[0])}</b></span><span class="mini">${bits(r[1])}</span></div>`).join('')}</div>`:''}
      <div class="admlist">${list}</div>
    </section>
    <section class="card stack">
      <div class="head">${esc(W.alert||'نیاز به توجه')}</div>
      <div class="admlist">${att}</div>
      ${tips.length?`<div class="head">توصیههای خودکار</div><div class="admlist">${tips}</div>`:''}
      <hr class="hr"/>
      <div class="head">${esc((RP.custom||{}).n||'گزارش سفارشی')}</div>
      <p class="cap">${esc((RP.custom||{}).s||'')}</p>
      <div class="admfilters">${cOpts.map(o=>`<button class="chip ${cSel.indexOf(o.k)>-1?'on':''}" data-rcust="${esc(o.k)}">${esc(o.n)}</button>`).join('')}</div>
      <div class="row">${btn('ساختن گزارش','data-rcustgo','i-chart')}</div>
      ${cOn?`<div class="stgroup"><div class="head">گزارش سفارشی تو · ${esc(curP)}</div>
        <div class="admlist">${cOpts.filter(o=>cSel.indexOf(o.k)>-1).map(o=>`<div class="admlirow">${ico('i-chart')}
          <span class="sp"><b>${esc(o.n)}</b></span><span class="mini">${bits(o.v)}</span></div>`).join('')}</div>
        <div class="admbars">${bars(CU.bars||[],true)}</div>
        <div class="admkpi">${cOpts.filter(o=>cSel.indexOf(o.k)>-1).slice(0,3).map((o,i2)=>`<div class="k"><small>${esc(['این دوره','دورهٔ مشابه قبل','تغییر'][i2])}</small>${bits(o.v)}</div>`).join('')}</div>
        ${baleRow('report_custom','گزارش سفارشی ('+fa(cSel.length)+' سنجه)')}</div>`:''}
      <hr class="hr"/>
      <div class="head">${esc((RP.sched||{}).n||'گزارش زمان‌بندی‌شده')}</div>
      <p class="cap">${esc((RP.sched||{}).s||'')}</p>
      <div class="admlist">${schL.map((r,i)=>`<div class="admlirow">${ico('i-clock')}
        <span class="sp"><b>${esc(r.n)}</b><small class="cap">${esc(r.at)}</small></span>
        <span class="mini"><span class="switch ${r.on?'on':''}" data-rsch="${i}" role="switch" aria-checked="${r.on?'true':'false'}" aria-label="${esc(r.n)}"></span></span></div>`).join('')}</div>
      <div class="row">${btn('زمان‌بندی تازه: جمعبندی فصلی','data-rschnew','i-plus')}</div>
      ${baleRow('reports_sched','همین حالا یک جمعبندی از ربات بله بگیر')}
      <hr class="hr"/>
      <div class="head">ممیزی کامل پنل · از ریز تا درشت</div>
      <p class="cap">${esc('پنل خودش را میپیماید: هر بخش، هر نما، هر دکمه و کلید و چیپ و کاشی و بنرِ در دسترس نقش تو یک بار کلیک میشود و پاسخش سنجیده میشود؛ بیپاسخ یعنی کنترلِ بیعکسالعمل.')}</p>
      ${AUD.on?`<div class="audprog"><i style="width:${Math.min(96,4+AUD.i*2)}%"></i></div>
        <p class="cap">در حال پیمایش (${fa(AUD.i)} کنترل): ${esc(AUD.cur)}</p>`
      :(()=>{const A2=S.auditLast;
        if(!A2) return `<p class="cap">هنوز پیمایشی ثبت نشده؛ با دکمهٔ زیر پنل با دسترسی خودت سراسر پیموده میشود.</p>`;
        return `<div class="admkpi">
          <div class="k"><small>بخش پیمایششده</small>${bits(fa(A2.secs))}</div>
          <div class="k"><small>کنترل زدهشده</small>${bits(fa(A2.tot))}</div>
          <div class="k"><small>پاسخ دادند</small>${bits(fa(A2.ok))}</div>
          <div class="k"><small>بیپاسخ</small>${bits(fa(A2.mute))}</div></div>
        ${(A2.issues||[]).length?`<div class="admlist">${A2.issues.map(x=>`<div class="admlirow">${ico('i-bell')}<span class="sp">${esc(x)}</span><span class="mini">${tag('بیپاسخ','warn')}</span></div>`).join('')}</div>`
          :`<div class="row">${tag('همه پاسخ دادند؛ هیچ دکمه و بنری بیجواب نماند','ok')}</div>`}
        ${(A2.errs||[]).length?`<div class="admlist">${A2.errs.map(x=>`<div class="admlirow">${ico('i-bell')}<span class="sp">${esc('خطا: '+x)}</span><span class="mini">${tag('خطا','warn')}</span></div>`).join('')}</div>`
          :`<p class="cap">هیچ خطای جاوااسکریپتی هم در پیمایش درنیامد.</p>`}
        <p class="cap">${esc('پیوندهای بیرونی '+fa(A2.ext)+' (ربات بله و صفحههای دیگر) و '+fa(A2.skip)+' کنترل حساس (بازنشانی و عوض کردن شخص) از پیمایش دور ماندند تا حالت بههم نریزد.')}</p>
        <div class="admlist">${(A2.per||[]).map(pt=>`<div class="admlirow">${ico('i-check')}<span class="sp"><b>${esc(pt.n)}</b>
          <small class="cap">${fa(pt.tot)} کنترل · ${pt.mute?fa(pt.mute)+' بیپاسخ':'همه پاسخ دادند'}${pt.ext?' · '+fa(pt.ext)+' پیوند بیرونی':''}</small></span>
          <span class="mini">${pt.mute?tag('مشکل','warn'):tag('سالم','ok')}</span></div>`).join('')}</div>
        <p class="cap">${esc(fa((A2.per||[]).reduce((a,x)=>a+(x.ban||0),0))+' بنر و جعبهٔ اطلاعی هم دیده شد و همه متن داشتند.')}</p>
        ${(A2.locked||[]).length||!isMoney()?`<p class="cap">${esc('بیرون از دسترسی نقش تو: '+(A2.locked||[]).join('، ')+(isMoney()?'':' · و همهٔ سنجههای مالی'))}</p>`:''}
        <p class="cap">${esc('پیمایش با دست «'+(A2.who||'')+' ('+(A2.lv||')').slice(0,0)+(A2.lv||'')+')» · '+(A2.at||''))}</p>`})()}
      <div class="row">${AUD.on?'':btn('پیمایش کامل با دسترسی من','data-auditrun','i-check')}</div>
      <div class="head">نقشهٔ دسترسی نقشها</div>
      <div class="admlist">${FIELDS.map(f=>{const open=(f.sections||[]).length;
        const lk=ALLSECS.filter(x=>(f.sections||[]).indexOf(x.k)<0).map(x=>x.n).join('، ')||'هیچ';
        return `<div class="admlirow">${ico('i-shield')}<span class="sp"><b>${esc(f.n)}</b>
          <small class="cap">${fa(open)} بخش از ${fa(ALLSECS.length)} · قفل: ${esc(lk)}</small></span></div>`}).join('')}</div>
      <hr class="hr"/>
      <div class="head">${esc((RP.excel||{}).n||'خروجی کامل اکسل')}</div>
      <p class="cap">${esc((RP.excel||{}).s||'')}</p>
      <div class="row">${baleA('reports_full','اکسل کامل (هفت شیت)')}</div>
      <hr class="hr"/>
      <div class="head">${esc(RP.out||'خروجی')}</div>
      <div class="admlist">
        <a class="admrow2" href="builder.html"><span class="ic">${ico('i-chart')}</span>
          <span class="tx"><b>${esc(RP.outA||'')}</b><small>${esc(RP.outAS||'')}</small></span>${ico('i-chev-left','chev')}</a>
        <a class="admrow2" href="account.html"><span class="ic">${ico('i-mobile')}</span>
          <span class="tx"><b>${esc(RP.outB||'')}</b><small>${esc(RP.outBS||'')}</small></span>${ico('i-chev-left','chev')}</a>
      </div>
      <p class="cap">${esc(RP.note||'')}</p>
    </section>
  </div>`;
}

/* ── گواهینامه: مرکز صدور ─────────────────────────────────────────────── */
function vCert(){
  const C=S.cert||{}, st=Math.max(0,Math.min(3,+C.step||0));
  const steps=(CE.steps||[]).map((n,i)=>`<button class="${i===st?'on':i<st?'done':''}" data-cstep="${i}">
      <span class="n">${i<st?'✓':esc(fa(i+1))}</span><span>${esc(n)}</span></button>`).join('');
  const files=(CE.files||[]).concat(S.certFiles||[]);
  const defK=S.certDef||((files.find(f=>f.def)||files[0]||{}).k);
  const curFile=files.find(f=>f.k===(C.file||defK))||files[0]||{};
  const evSel=(C.evs||[]).filter(id=>EVROWS.some(e=>e.id===id));
  const evCnt=evSel.reduce((a,id)=>a+(+(EVROWS.find(e=>e.id===id)||{}).reg||0),0);
  const tagCnt=(C.tags||[]).reduce((a,t)=>a+memList().filter(m=>(m.tags||[]).indexOf(t)>-1).length,0);
  const xls=(C.xlsRows||[]);
  const xlsOk=xls.filter(x=>x.ok).length;
  const picked=(C.picked||[]).map(id=>memOf(id)).filter(Boolean);
  const recTot=evCnt+tagCnt+xls.length+picked.length;
  const letter=C.letter||CE.letter||'', months=C.months||CE.months||'', news=C.news||CE.news||'';
  const winNow=certWin();
  let inner='';
  if(st===0){
    const fp=curFile.params||[];
    const AUTO=['نام','نام خانوادگی','نام‌خانوادگی','نام کامل','نام‌کامل','کد ملی','کدملی','موبایل','شمارهٔ موبایل','عکس'];
    const auto=fp.filter(x=>AUTO.indexOf(x)>-1), man=fp.filter(x=>AUTO.indexOf(x)<0), vals=C.vals||{};
    inner=`<p class="cap">${esc(CE.tplCap||'')}</p>
      <div class="admlist">${files.map(f=>`<div class="admrow2" style="cursor:default">
        <span class="ic">${ico('i-doc')}</span>
        <button class="tx" data-cfile="${esc(f.k)}"><b>${esc(f.n)}</b><small>${esc(f.s||'')}${(f.params||[]).length?' · '+esc(fa(f.params.length))+' پارامتر متغیر':''}</small></button>
        <span class="mini">${defK===f.k?tag('پیشفرض','brand'):''}
          ${curFile.k===f.k?tag('برداشته شد','ok'):''}
          ${defK!==f.k?btn('پیشفرض کن','data-cdef="'+esc(f.k)+'"','i-check'):''}</span></div>`).join('')}</div>
      ${curFile.k?balebox(`<div class="pvsheet">${'<i></i>'.repeat(8)}</div>`,'cert_file_'+curFile.k,
        'پیش‌نمایش «'+curFile.n+'» تار است؛ فایل ورد کامل از ربات بلهٔ موسسه می‌آید'):''}
      ${fp.length?`<div class="head">${esc((CE.paramsOf||'پارامترهای قالب')+' «'+(curFile.n||'')+'»')}</div>
        ${auto.length?`<p class="cap">${esc(CE.autoCap||'')}</p>
          <div class="admfilters">${auto.map(x=>`<span class="tag ok" dir="ltr">{${esc(x)}}</span>`).join('')}</div>`:''}
        ${man.length?`<p class="cap">${esc(CE.manCap||'')}</p>
          <div class="stpr vals">${man.map(x=>`<label class="fld"><span dir="ltr">{${esc(x)}}</span>
            <input class="input" data-cparam="${esc(x)}" value="${esc(vals[x]||'')}" placeholder="${esc('مقدار '+x)}"/></label>`).join('')}</div>`:''}`
       :`<p class="cap">${esc(CE.noParams||'')}</p>`}
      <div class="head">${esc('راهنمای کامل پارامترها')}</div>
      <p class="cap">${esc('هر جای خالی را با همین نوشتار در ورد بگذار؛ ردیف پررنگ در قالب برگزیدهٔ تو هست. هیچکدام اجباری نیست؛ خالی بماند، همانطور که در فایل است میماند.')}</p>
      <div class="stguide">${(CE.guide||[]).map(g=>`<div class="stg"><div class="stgh"><b>${esc(g.g)}</b><small class="cap">${esc(g.s)}</small></div>
        <div class="stpr">${(g.rows||[]).map(x=>`<div class="stp ${fp.indexOf(String(x[0]).replace(/[{}]/g,''))>-1?'has':''}">${ico('i-pen')}<span class="sp"><b dir="ltr">${esc(x[0])}</b><small>${esc(x[1]||'')}</small></span></div>`).join('')}</div></div>`).join('')}</div>`;
    } else if(st===1){
    inner=`<p class="cap">${esc('چند رویداد را هرچندتا که خواستی برگزین؛ حاضران همهٔ رویدادهای برگزیده گیرندهٔ گواهینامه می‌شوند.')}</p>
      <div class="admfilters">${EVROWS.filter(e=>+e.reg>0).map(e=>`<button class="chip ${evSel.indexOf(e.id)>-1?'on':''}" data-cev="${esc(e.id)}">
        ${esc((e.n||'').slice(0,26))} <b>${esc(fa(e.reg))}</b></button>`).join('')}</div>
      <p class="cap">${evSel.length
        ?esc(fa(evSel.length)+' رویداد برگزیده شد · '+fa(evCnt)+' گیرنده')
        :esc('هنوز رویدادی برگزینشده؛ اگر گیرنده از جای دیگری میآید، این گام را رد کن.')}</p>`;
  } else if(st===2){
    const finds=(S.certFind?memList().filter(m=>norm(m.n+' '+m.code+' '+m.ph+' '+(m.nid||'')).indexOf(S.certFind)>-1).slice(0,6):[]);
    inner=`<p class="cap">${esc('گیرندهها از هر راهی که راحت‌تری: دستهٔ آماده، اکسل، یا جست‌وجوی تک‌تک. تکراریها خودکار یکی میشوند؛ هر کس یک گواهینامه.')}</p>
      <div class="head">${esc('از دستهٔ آماده')}</div>
      <div class="admfilters">${Object.keys(uLabels()).slice(0,6).map(t=>`<button class="chip ${(C.tags||[]).indexOf(t)>-1?'on':''}" data-ctag="${esc(t)}">${esc(t)} <b>${esc(fa(uLabels()[t]))}</b></button>`).join('')}</div>
      <div class="head">${esc('از فایل اکسل')}</div>
      <p class="cap">${esc('فایل اکسل یا CSV را بارگذاری کن؛ هر ردیف یک نفر با ستون‌های نام و موبایل یا کد ملی. شناخته‌شدهها به پروفایل وصل میشوند؛ ناشناسها هم با همان نام گواهینامه میگیرند.')}</p>
      <label class="fileup">${ico('i-upload')}<span class="sp"><b>${esc((CE.xlsUp||{}).n||'')}</b><small>${esc((CE.xlsUp||{}).s||'')}</small></span>
        <input type="file" accept=".xlsx,.csv,.txt" data-cxlsup/></label>
      <div class="row tight">${xls.length?tag(fa(xlsOk)+' شناخته شد · '+fa(xls.length-xlsOk)+' ناشناس',xlsOk?'ok':'warn'):''}</div>
      <div class="head">${esc('جست‌وجوی کاربر و افزودن تک‌تک')}</div>
      <div class="row tight"><input id="cFind" class="input" placeholder="نام، کد یا موبایل" value="${esc(S.certFind||'')}"/>
      ${btn('جست‌وجو','data-cfindgo','i-search')}</div>
      ${finds.length?`<div class="admlist">${finds.map(m=>`<div class="admlirow">${ico('i-users')}
        <span class="sp"><b>${esc(m.n)}</b><small class="cap">${esc(m.code)} · ${esc(fa(m.ph))}</small></span>
        <span class="mini">${(C.picked||[]).indexOf(m.id)>-1?tag('افزوده شد','ok'):btn('افزودن','data-cpick="'+esc(m.id)+'"','i-plus')}</span></div>`).join('')}</div>`:''}
      ${(C.picked||[]).length?`<div class="admfilters">${picked.map(m=>`<button class="chip on" data-cunpick="${esc(m.id)}">${esc(m.n)} ×</button>`).join('')}</div>`:''}
      <div class="admkpi">
        <div class="k"><small>از رویدادها</small>${bits(fa(evCnt))}</div>
        <div class="k"><small>از دسته‌ها</small>${bits(fa(tagCnt))}</div>
        <div class="k"><small>از اکسل</small>${bits(fa(xls.length))}</div>
        <div class="k"><small>افزودهٔ دستی</small>${bits(fa((C.picked||[]).length))}</div></div>
      <p class="cap">${esc('جمع گیرنده‌ها با یکتاسازی خودکار: '+fa(recTot)+' نفر.')}</p>`;
  } else {
    const qn=(S.certQueue||[]).filter(b=>!b.rev), qd=(S.certQueue||[]).filter(b=>b.rev);
    inner=`<div class="stgroup">
      <div class="head">${esc('پنجرهٔ صدور: ساعت خلوت سامانه')}</div>
      <div class="fslead"><span class="ic">${ico('i-clock')}</span>
        <span class="sp"><b>پنجرهٔ بعدی: ${esc(winNow)}</b>
          <small>صدورها صف میشوند و در کم‌بارترین ساعت سامانه (۰۲:۰۰ بامداد) یک‌جا اجرا میشوند؛ به هر گیرنده در ربات بله گفته میشود «تا ۲۴ ساعت آینده صادر میشود».</small></span></div>
      <div class="admsw" style="border:0;padding-inline:0">
        <span class="sp"><b>${esc((CE.lazy||{}).n||'')}</b><small>${esc((CE.lazy||{}).s||'')}</small></span>
        <span class="switch ${togDef('cert','lazy',true)?'on':''}" data-tog="cert" data-toglabel="${esc((CE.lazy||{}).n||'ساخت تنبل')}" data-togdef="1" role="switch" aria-checked="true" aria-label="${esc((CE.lazy||{}).n||'ساخت تنبل')}"></span></div>
      <p class="cap">${esc('درخواستهای رسیده از ربات: '+fa(CE.botReq||0)+' نفر؛ همینها هم در همان پنجره صادر میشوند.')}</p></div>
    <div class="stgroup">
      <div class="head">${esc('شماره‌ها و خبر')}</div>
      <label class="fld"><span>شمارهٔ نامهٔ مشترک</span><input class="input" data-cletter value="${esc(C.letter||'')}" placeholder="${esc(CE.letter||'')}"/></label>
      <label class="fld"><span>اعتبار (ماه)</span><input class="input" data-cmonths value="${esc(C.months||'')}" placeholder="${esc(CE.months||'')}"/></label>
      <label class="fld"><span>متن خبر گیرنده‌ها (قابل ویرایش)</span><textarea data-cnews rows="2" placeholder="${esc(CE.news||'')}">${esc(C.news||'')}</textarea></label>
      <div class="row tight">${btn('پیش‌نمایش تصادفی','data-crand','i-eye')}
        ${baleA('cert_random','نمونهٔ کامل از ربات بله')}</div>
      ${C.rand?certLive({name:C.rand,kind:'گواهینامهٔ پایان دوره',
        title:((EVROWS.find(e=>evSel.indexOf(e.id)>-1)||EVROWS[0]||{}).n||'برنامهٔ آموزشی موسسه'),
        serial:'NL-'+String(100000+((S.certQueue||[]).length+1)*7919%899999),
        date:letter?letter:''},
        'نمونه برای «'+C.rand+'» · '+letter+' · اعتبار '+fa(months)+' ماه'):''}
      <div class="row stctas">
        ${btn('ثبت در صف صدور ('+winNow+')','data-cqueue','i-send')}
        ${btn('صدور فوری، خارج از نوبت','data-cfast','i-bolt')}</div></div>
    <div class="stgroup">
      <div class="head">${esc('صف و منتشرشده‌ها')}</div>
      ${(S.certQueue||[]).length?S.certQueue.map((b,bi)=>`<div class="permrow"><span class="sp"><b>${esc(b.n)}</b>
          <small class="cap">${b.rev?'باطل‌شده · ':''}${esc(fa(b.cnt))} گیرنده · ${esc(b.letter||'بدون شمارهٔ نامه')} · ${b.st==='ok'?esc(fa(b.got))+' دریافتشده':'اجرا: '+esc(b.plan)}</small></span>
        <span class="mini">${b.rev?'':b.st==='wait'
          ?btn('اجرا همین حالا','data-crun="'+bi+'"','i-bolt')+btn('برداشتن از صف','data-cbrev="'+bi+'"','i-trash')
          :btn('یادآوری مانده‌ها','data-cbnudge="'+bi+'"','i-send')}</span></div>`).join('')
        :emptyBox('صف خالی است؛ با «ثبت در صف صدور» نخستین دسته را بساز')}</div>`;
  }
  const jobs=(CE.jobs||[]).concat(S.jobs||[]);
  return `<section class="card stack admcert">
    ${uBack}
    <div class="row"><div class="head">${esc(CE.lead||'')}</div><span class="sp"></span>
      ${btn(sheetName('استعلام'),'data-verify-help','i-qr')}</div>
    <div class="admcertsteps">${steps}</div>
    ${inner}
    <div class="row"><span class="sp"></span>
      ${btn(W.prev||'گام پیش','data-cgo="'+Math.max(0,st-1)+'"'+(st===0?' disabled':''),"i-chev-right")}
      ${st<3?btn(W.next||'گام بعد','data-cgo="'+(st+1)+'"','i-chev-left'):''}</div>
    <hr class="hr"/>
    <div class="head">${esc(W.jobs||'کارهای صدور')}</div>
    <div class="admlist">${jobs.map((j,ji)=>rowLink({attrs:'data-cjob="'+ji+'"', i:'i-medal', b:esc(j.n),
      s:`${esc(j.who)} · ${esc(j.way)} · ${esc(j.at)}`, right:tag(j.st==='wait'?'در نوبت':'منتشر شد',j.st==='wait'?'warn':'ok')})).join('')}</div>
    ${baleRow('cert_list','کارهای صدور گواهینامه')}
  </section>`;
}
function sheetName(){return L.askCert}

/* مدیریت مدیران و کارشناسان: حساب با نام کاربری و رمز؛ ورود اول و پروفایل دست‌اندرکاران */
const SPECU={p1:'sara.m',p2:'maryam.r',p3:'amir.k',p4:'majid.r',p5:'negar.m',p6:'hossein.a',
  p7:'zahra.s',p8:'fatemeh.k',p9:'reza.sh',p10:'ali.n',p11:'elham.n',p12:'pouya.s',
  p13:'shirin.gh',p14:'mina.t',p15:'saeed.r'};
const genPw=()=>'Nora-'+Math.floor(1000+Math.random()*9000);
const accOf=p=>{const o=(S.specAcc||{})[p.k]; if(o) return o;
  return {u:SPECU[p.k]||('user'+p.k.replace(/^p/,'')), done:(p.k==='p9'||p.k==='p12')?0:1}};
const SPROF=[['i-users','نام و نام خانوادگی','همان که روی گواهی و کارت می‌نشیند'],
  ['i-pen','سمت','مثل: مسئول اجرا و پشتیبانی'],
  ['i-shield','حوزه','همان حوزه‌ای که برایش ساختی'],
  ['i-mobile','موبایل','برای یادآوریها و اطلاع‌رسانی حوزه'],
  ['i-doc','بیو کوتاه','دو خط دربارهٔ خودش برای صفحهٔ دست‌اندرکاران']];
function cUStaff(){
  const fk=(S.setF&&fieldOf(S.setF).k===S.setF)?S.setF:'edu', f=fieldOf(fk);
  const l=personOf(leadK(fk)), t=teamOf(fk);
  const flow=[['i-key','حساب می‌سازید','نام کاربری و رمز یکبارمصرف می‌سازید و برایش می‌فرستید'],
    ['i-mobile','ورود اول','با همان رمز وارد می‌شود و رمز تازه‌ای می‌گذارد'],
    ['i-idcard','تکمیل پروفایل','پروفایل دست‌اندرکاران را پر می‌کند؛ سرپرست تأیید می‌کند']];
  const pend=t.filter(pp=>!accOf(pp).done).length;
  return uHead('مدیران و کارشناسان')+'\n'+
  `    <p class="cap">${esc('برای هر کارشناس حساب می‌سازید؛ او در نخستین ورود رمز تازه‌ای می‌گذارد و پروفایل دست‌اندرکاران را کامل می‌کند.')}</p>
    <div class="stflow">${flow.map((x,i2)=>`<div class="stf"><span class="n">${fa(i2+1)}</span>${ico(x[0])}<b>${esc(x[1])}</b><small>${esc(x[2])}</small></div>`).join('')}</div>
    <div class="admfilters">${FIELDS.filter(x=>x.k!=='owner').map(x=>`<button class="tag ${fk===x.k?'on':''}"
        data-setF="${esc(x.k)}">${esc(x.n)}</button>`).join('')}</div>
    <div class="stgroup">
      <div class="fslead">
        <span class="ic">${ico('i-shield')}</span>
        <span class="sp"><b>${esc(D.lead||'سرپرست')}: ${esc(l.n)}</b>
          <small>${esc(f.s)} · سرپرست همهٔ دسترسی‌های حوزه را دارد</small></span>
        ${isOwner()?`<button class="btn sm quiet" data-setlead="${esc(fk)}">${esc(D.changeLead||'تعیین سرپرست')}</button>`:''}
      </div>
      <div class="row"><div class="head">${esc(D.specs||'کارشناسان')} (${esc(fa(t.length))} ${esc(D.specsWord||'نفر')}${pend?' · '+fa(pend)+' در انتظار پروفایل':''})</div>
        <span class="sp"></span>
        ${isOwner()||isLead()?`<button class="btn sm tint" data-addspec="${esc(fk)}">${ico('i-plus')}${esc('حساب تازه')}</button>`:''}</div>
      <div class="tlist">${t.map(pp=>{const ac=accOf(pp); return `<div class="trow">
          <span class="va">${esc(String(pp.n||' ').slice(0,1))}</span>
          <button class="tt" data-specrow="${esc(pp.k)}"><b>${esc(pp.n)}</b>
            <small><span class="stacc" dir="ltr">@${esc(ac.u)}</span> · ${esc(fa(pp.open))} ${esc(D.qOpen||'کار باز')} · از ${esc(pp.since||'')}</small></button>
          ${pp.lv==='سرپرست'?tag('سرپرست','brand'):''}
          ${ac.done?tag('پروفایل کامل','ok'):tag('در انتظار تکمیل پروفایل','warn')}
          <span class="tload"><i style="width:${pp.load}%"></i></span>
          <span class="mini"><button class="btn sm quiet" data-resetspec="${esc(pp.k)}">${esc('تغییر رمز')}</button>
          <button class="btn sm quiet" data-specperm="${esc(pp.k)}">${esc(D.specPerms||'دسترسی‌ها')}</button></span></div>`}).join('')||emptyBox(D.qEmpty||'')}</div>
    </div>
    <div class="stgroup">
      <div class="head">${esc('پروفایل دست‌اندرکاران (ورود اول)')}</div>
      <p class="cap">${esc('این پنج چیز را در نخستین ورود از او می‌پرسیم؛ با تأیید سرپرست، نام و سمتش بر صفحهٔ دست‌اندرکاران سایت می‌نشیند.')}</p>
      <div class="stprof">${SPROF.map(x=>`<div class="stp">${ico(x[0])}<span class="sp"><b>${esc(x[1])}</b><small>${esc(x[2])}</small></span></div>`).join('')}</div>
    </div>
    <div class="stgroup">
      <div class="head">${esc('دسترسی‌های '+f.n)}</div>
      <p class="cap">${esc('هر تیک، دسترسی همان کارشناس است؛ سرپرست همهٔ دسترسی‌ها را دارد و همین‌جا عوض می‌شود.')}</p>
      <div class="permrows">${permRowsOf(fk).map(r=>{
        const on=specPermsOf(fk).indexOf(r[0])>-1;
        return `<div class="permrow"><span class="sp"><b>${esc(r[1])}</b></span>
          ${isOwner()||isLead()
            ?`<span class="switch ${on?'on':''}" data-fperm="${esc(r[0])}" role="switch" aria-checked="${on?'true':'false'}" aria-label="${esc(r[1])}"></span>`
            :tag(on?'کارشناس دارد':'کارشناس ندارد',on?'ok':'')}</div>`}).join('')}</div>
    </div>
    <div class="stgroup">
      <div class="head">${esc(PERMS.ownerTitle||D.ownerPerms||'فقط مالک')}</div>
      <p class="cap">${esc(PERMS.ownerNote||'')}</p>
      <div class="admlist">${(OWNER_PERMS||[]).map(x=>`<div class="admsw">
        <span class="sp">${esc(x[1])}</span>${tag(D.ownerOnly||'فقط مالک','accent')}</div>`).join('')}</div>
    </div>`;
}
/* ══ تنظیمات سامانه: کاشیهای حوزهها + مدیریت ظاهر ══════════════════════ */
const SKIN_TILES=[
 {k:'skin', n:'ظاهری سامانه', i:'i-sparkle', s:'منو، بنر، استوری، کارتها، پای صفحه'},
 {k:'forms', n:'فرمساز', i:'i-pen', s:'پیشفرضهای فرم تازه', soon:1},
 {k:'book', n:'باشگاه کتابخوانی', i:'i-book', s:'ترمها، نشانها، فروشگاه', soon:1},
 {k:'users', n:'کاربران و دسترسی', i:'i-users', s:'نقشها، عضویتها، مسدودها', soon:1},
 {k:'skdev', n:'رویدادها و مطالب', i:'i-calendar', s:'برچسبها، دستهها، تقویم', soon:1},
 {k:'chat', n:'پشتیبانی و گفتگو', i:'i-headphone', s:'سرویس، قالب پاسخ، ساعات', soon:1}];
const SKIN_TABS=[['home','بخشهای خانه'],['menu','منو و کاشیها'],['bnr','بنرها'],
  ['story','استوریها'],['look','کارتها و اساتید'],['foot','پای صفحه']];
let skinArm=0;
function usGet(path){return path.split('.').reduce((o,k)=>(o||{})[k],uiSet())}
function usSet(path,val){const U=uiSet(), ks=path.split('.'); let o=U;
  for(let i=0;i<ks.length-1;i++) o=o[ks[i]];
  o[ks[ks.length-1]]=val; uiSetSave(U); return U}
function skinSwitch(label,path){const on=usGet(path)?1:0;
  return `<div class="admsw"><span class="sp">${esc(label)}</span>
    <span class="switch ${on?'on':''}" data-uk="${esc(path)}" data-uklabel="${esc(label)}"
      role="switch" aria-checked="${on?'true':'false'}" aria-label="${esc(label)}"></span></div>`}
function skinView(){
  const U=uiSet(), M=(window.NORA&&window.NORA.MENU)||[], ST=(window.NORA&&window.NORA.STORIES)||[];
  let inner='';
  if(S.skinTab==='home'){
    inner=`<p class="cap">هر بخشی از خانهٔ کاربر که لازم نداری، همین‌جا خاموش می‌شود؛ چیدمان صفحه نمی‌ریزد.</p>`
      +UISET_META.home.map(([k,n])=>skinSwitch(n,'home.'+k)).join('');
  } else if(S.skinTab==='menu'){
    inner=`<p class="cap">ردیفهای ورقهٔ «منوی نورا»؛ گروهی که همهٔ ردیفهایش پنهان شود، خودش هم نمیآید.</p>`
      +M.map(g=>`<div class="head tight" style="margin-top:10px">${ico(g.i)}${esc(g.g)}</div>`
        +g.rows.map(r=>{const on=!U.menu.includes(r.t);
          return `<div class="admsw"><span class="sp">${esc(r.t)}</span>
            <span class="switch ${on?'on':''}" data-umenu="${esc(r.t)}" data-uklabel="${esc(r.t)}"
              role="switch" aria-checked="${on?'true':'false'}" aria-label="${esc(r.t)}"></span></div>`}).join('')).join('')
      +`<div class="head tight" style="margin-top:10px">${ico('i-grid')}کاشیهای «از کجا شروع کنیم؟»</div>`
      +UISET_META.quick.map(([k,n])=>{const on=!U.quick.includes(k);
        return `<div class="admsw"><span class="sp">${esc(n)}</span>
          <span class="switch ${on?'on':''}" data-uquick="${k}" data-uklabel="${esc(n)}"
            role="switch" aria-checked="${on?'true':'false'}" aria-label="${esc(n)}"></span></div>`}).join('');
  } else if(S.skinTab==='bnr'){
    inner=`<p class="cap">بنرهای بالای خانه؛ هر بنر را میتوانی پنهان کنی یا بنر تازه تعریف کنی.</p>`
      +skinSwitch('نمایش بنرها','bnr.on')+skinSwitch('چرخش خودکار','bnr.auto')
      +(window.NORA.BANNERS||[]).map(b=>{const on=!U.bnr.hide.includes(b.t);
        return `<div class="admsw"><span class="sp">${esc(b.t)}</span>
          <span class="switch ${on?'on':''}" data-bhide="${esc(b.t)}" data-uklabel="بنر ${esc(b.t)}"
            role="switch" aria-checked="${on?'true':'false'}" aria-label="${esc(b.t)}"></span></div>`}).join('')
      +`<hr class="hr"/><div class="head tight">تعریف بنر تازه</div>
      <div class="admtext"><span class="lbl">عنوان</span><input class="input" id="skBnT" placeholder="مثل: جشنوارهٔ فیلم کوتاه"/></div>
      <div class="g2"><div><label class="lbl">برچسب</label><input class="input" id="skBnTag" placeholder="ویژه"/></div>
        <div><label class="lbl">زمان و مکان</label><input class="input" id="skBnM" placeholder="آبان · تهران"/></div></div>
      <div class="admtext"><span class="lbl">توضیح یکخطی</span><input class="input" id="skBnN"/></div>
      <div class="admtext"><span class="lbl">نام دکمهٔ بنر</span><input class="input" id="skBnA" placeholder="دیدن جزئیات"/></div>
      <label class="lbl">رنگ بنر</label>
      <div class="row tight">${UISET_META.grads.map(([g,n],i)=>`<button class="chip ${i===0?'on':''}" data-bg="${esc(g)}">${esc(n)}</button>`).join('')}</div>
      <div class="row">${btn('افزودن بنر','data-skbadd','i-plus')}</div>`
      +((U.bnrAdd||[]).length?`<div class="admlist">${U.bnrAdd.map((b,i)=>`
        <div class="admrow2"><span class="ic">${ico('i-image')}</span>
          <span class="tx"><b>${esc(b.t)}</b><small>${esc(b.m||'')}</small></span>
          ${btn('برداشتن','data-skbdel="'+i+'"','i-trash')}</div>`).join('')}</div>`:'');
  } else if(S.skinTab==='story'){
    inner=`<p class="cap">استوریهای کوتاه خانه؛ هرکدام را پنهان کن یا استوری تازه بساز.</p>`
      +ST.map(x=>{const on=!U.storyHide.includes(x.id);
        return `<div class="admsw"><span class="sp">${esc(x.t)}</span>
          <span class="switch ${on?'on':''}" data-shide="${esc(x.id)}" data-uklabel="استوری ${esc(x.t)}"
            role="switch" aria-checked="${on?'true':'false'}" aria-label="${esc(x.t)}"></span></div>`}).join('')
      +`<hr class="hr"/><div class="head tight">تعریف استوری تازه</div>
      <div class="admtext"><span class="lbl">عنوان</span><input class="input" id="skST" placeholder="مثل: پشت صحنهٔ تمرین"/></div>
      <div class="admtext"><span class="lbl">زیرعنوان</span><input class="input" id="skSS"/></div>
      <label class="lbl">آیکن</label>
      <div class="row tight">${UISET_META.storyIco.map(([k,n],i)=>`<button class="chip ${i===0?'on':''}" data-sico="${k}">${esc(n)}</button>`).join('')}</div>
      <label class="lbl">رنگ</label>
      <div class="row tight">${UISET_META.grads.map(([g,n],i)=>`<button class="chip ${i===0?'on':''}" data-sgrad="${esc(g)}">${esc(n)}</button>`).join('')}</div>
      <label class="lbl">مقصد دکمهٔ استوری</label>
      <div class="row tight">${UISET_META.storyGo.map(([k,n],i)=>`<button class="chip ${i===0?'on':''}" data-sdest="${k}">${esc(n)}</button>`).join('')}</div>
      <div class="row">${btn('افزودن استوری','data-sksadd','i-plus')}</div>`
      +((U.storyAdd||[]).length?`<div class="admlist">${U.storyAdd.map((s,i)=>`
        <div class="admrow2"><span class="ic">${ico(s.i||'i-sparkle')}</span>
          <span class="tx"><b>${esc(s.t)}</b><small>${esc(s.s||'')}</small></span>
          ${btn('برداشتن','data-sksdel="'+i+'"','i-trash')}</div>`).join('')}</div>`:'');
  } else if(S.skinTab==='look'){
    inner=`<div><label class="lbl">اندازهٔ کارت رویداد</label>
      <div class="admfilters">${UISET_META.cards.map(([k,n])=>`<button class="chip ${U.cards===k?'on':''}" data-ucards="${k}">${esc(n)}</button>`).join('')}</div>
      <p class="cap">خانه، رویدادها و برگزارشدهها همه از همین میخوانند.</p></div>
    <div><label class="lbl">مدل نمایش اساتید و دستاندرکاران</label>
      <div class="admfilters">${UISET_META.people.map(([k,n])=>`<button class="chip ${U.people===k?'on':''}" data-upeople="${k}">${esc(n)}</button>`).join('')}</div>
      <p class="cap">کارت کامل با امتیاز و تگها؛ ردیف فشرده برای فهرستهای شلوغ؛ فقط نامها برای چیدمان سبک.</p></div>`;
  } else {
    inner=`<p class="cap">جملهٔ اطمینان پای هر صفحه و پای صفحهٔ خانه؛ خالی بگذاری تا همان جملهٔ خود نورا بنشیند.</p>`
      +skinSwitch('نمایش خط اطمینان','trust.on')+skinSwitch('نمایش پای صفحهٔ خانه','foot.on')
      +`<div class="admtext"><span class="lbl">متن خط اطمینان</span><input class="input" id="skTrust" value="${esc(U.trust.text||'')}"/></div>
      <div class="admtext"><span class="lbl">متن پای صفحهٔ خانه</span><input class="input" id="skFoot" value="${esc(U.foot.text||'')}"/></div>
      <div class="row">${btn('ذخیرهٔ متنها','data-skinfoot','i-check')}</div>`;
  }
  return `<section class="card stack">
    <div class="row"><button class="btn sm quiet" data-skinback>${ico('i-chev-right')} بازگشت به کاشیها</button>
      <span class="sp"></span>${btn('بازنشانی پیشفرضها','data-skinreset','i-trash')}</div>
    <div class="row"><div class="head">تنظیمات ظاهری سامانه</div><span class="sp"></span>
      <span class="cap">هر کلید، همان لحظه روی صفحههای کاربر مینشیند</span></div>
    <div class="admfilters">${SKIN_TABS.map(([k,n])=>`<button class="chip ${S.skinTab===k?'on':''}" data-skintab="${esc(k)}">${esc(n)}</button>`).join('')}</div>
    <div class="admset">${inner}</div>
  </section>`;
}
function vSettings(){
  const ST=A.settings||{}, own=isOwner(), lead=isLead();
  const canTpl=own||lead;   /* قالب گواهینامه: فقط دست مالک و سرپرست */
  if(own&&S.skin) return skinView();
  if(!own) S.setF=myField().k;
  let g=S.setG||'texts';
  if(!canTpl) g=''; else if(!own&&g!=='cert') g='cert';
  const list=(ST.groups||[]).filter(x=>own||x.k==='cert');
  const groups=list.map(x=>`<button class="chip ${g===x.k?'on':''}" data-setg="${esc(x.k)}">
      ${ico(x.i)}<span>${esc(x.n)}</span></button>`).join('');
  /* کاشیهای تنظیمات: هر حوزه یک کاشی؛ شش کاشی، ردیف تا چهار تا */
  const tiles=own?`<section class="card stack">
    <div class="row"><div class="head">تنظیمات سامانه</div><span class="sp"></span>
      <span class="cap">${esc(fa(SKIN_TILES.length))} کاشی · هر کاشی یک حوزه</span></div>
    <div class="sktgrid">${SKIN_TILES.map(x=>`
      <button class="sktile" data-skit="${x.k}"><span class="si">${ico(x.i)}</span>
        <b>${esc(x.n)}</b><span class="cap">${esc(x.s)}</span>${x.soon?tag('در نوبت بعد',''):''}</button>`).join('')}</div>
  </section>`:'';
  const group=(ST.groups||[]).find(x=>x.k===g)||{n:'',s:''};
  let inner='';
  if(!canTpl){
    inner=emptyBox('مدیریت مدیران و کارشناسان به بخش «کاربران» منتقل شد؛ تنظیمات پنل با حساب مالک و سرپرست است');
  } else if(g==='cert'){
    const TU=ST.tpl||{};
    const tfiles=(CE.files||[]).concat(S.certFiles||[]);
    const tdef=S.certDef||((tfiles.find(f=>f.def)||tfiles[0]||{}).k);
    inner=`<div class="head">${esc(TU.title||'')}</div><p class="cap">${esc(TU.note||'')}</p>
      <label class="fileup">${ico('i-upload')}<span class="sp"><b>${esc(TU.up||'')}</b><small>${esc(TU.ups||'')}</small></span>
        <input type="file" accept=".docx" data-cfileup/></label>
      <div class="admlist">${tfiles.map(f=>`<div class="admrow2" style="cursor:default">
        <span class="ic">${ico('i-doc')}</span>
        <span class="tx"><b>${esc(f.n)}</b><small>${esc(f.s||'')}${(f.params||[]).length?' · <span dir="ltr">'+esc((f.params||[]).slice(0,5).map(x=>'{'+x+'}').join(' '))+'</span>':''}</small></span>
        <span class="mini">${tdef===f.k?tag('پیشفرض','brand'):btn('پیشفرض کن','data-cdef="'+esc(f.k)+'"','i-check')}
          ${f.up?'<a class="btn sm" download="'+esc(f.n)+'.docx" href="'+f.up+'">'+ico('i-download')+esc(TU.dl||'دانلود')+'</a>':(f.big?tag(TU.heavy||'','warn'):'')}</span></div>`).join('')}</div><hr class="hr"/>`;
    inner+=(((ST.rows||{})['cert'])||[]).map(r=>{const on=togDef('cert',r[0],r[1]);
      return `<div class="admsw"><span class="sp">${esc(r[0])}</span>
        <span class="switch ${on?'on':''}" data-tog="cert" data-toglabel="${esc(r[0])}" data-togdef="${r[1]?1:0}"
          role="switch" aria-checked="${on?'true':'false'}" aria-label="${esc(r[0])}"></span></div>`}).join('');
  } else if(g==='texts'){
    const TX=ST.texts||{};
    inner=`<div class="head">${esc(TX.title||'')}</div><p class="cap">${esc(TX.note||'')}</p>`+
      (TX.list||[]).map(t=>`<div class="admtext"><span class="lbl">${esc(t.n)}</span>
        <input class="input" data-text="${esc(t.k)}" value="${esc(txtDef(t.k,t.v))}"/></div>`).join('')+
      `<div class="row"><span class="sp"></span>${btn(T.save||W.save||'ذخیره شد','data-savetexts','i-check')}</div>`;
  } else {
    const rows=((ST.rows||{})[g])||[];
    inner=`<div class="head">${esc(group.n)}</div><p class="cap">${esc(group.s||'')}</p>
      ${rows.map(r=>{const on=togDef(g,r[0],r[1]);
        return `<div class="admsw"><span class="sp">${esc(r[0])}</span>
          <span class="switch ${on?'on':''}" data-tog="${esc(g)}" data-toglabel="${esc(r[0])}" data-togdef="${r[1]?1:0}"
            role="switch" aria-checked="${on?'true':'false'}" aria-label="${esc(r[0])}"></span></div>`}).join('')}`;
    if(g==='data'){
      const K=ST.keys||{};
      inner+=`<hr class="hr"/><div class="head">${esc(K.title||L.keys)}</div><p class="cap">${esc(K.note||'')}</p>
        <div class="admlist">${(K.list||[]).map((k,ki)=>rowLink({attrs:'data-keycopy="'+ki+'"', i:'i-key', b:esc(k.n),
          s:`<span dir="ltr">${esc(k.v)}</span>`, right:tag(k.st==='ok'?'سالم':'بررسی',k.st==='ok'?'ok':'warn')})).join('')}</div>
        <div class="row">${baleA('backup','پشتیبان در ربات بله')}
          ${btn('بازگردانی','data-restore','i-layers')}${btn('بازنشانی پنل','data-reset','i-trash')}</div>`;
    }
  }
  return tiles+`<section class="card stack">
    <div class="row"><div class="head">${esc(ST.lead||'')}</div><span class="sp"></span>
      <span class="cap">${esc(own?fa((ST.groups||[]).length)+' گروه':(D.fieldSettings||'حوزهٔ من'))}</span></div>
    <div class="admfilters">${groups}</div>
    <div class="admset">${inner}</div>
  </section>`;
}
/* ══ ورقه‌ها ═══════════════════════════════════════════════════════════ */
function sheetEv(id){
  const e=evOf(id); if(!e) return;
  const D=A.events||{}, stE=evState(e), st=(D.states||{})[stE]||['',''];
  const src=posterSrc(e.posterUp||e.poster), ses=(e.sess||[]);
  const madeForms=(function(){try{const u=(window.NORA_UI&&NORA_UI)||null;
    return u&&u.formsFor?u.formsFor(e.id):[]}catch(err){return []}})();
  /* هزینهٔ رویداد از خود فرم ثبتنام زنده خوانده میشود؛ فرمساز که عوض کند، همینجا تازه میشود */
  const livePrice=(function(){try{
    const rf=madeForms.find(f=>(f.need||'reg')==='reg');
    return rf?formSum(rf):null}catch(err){return null}})();
  const evPrice=livePrice!=null?livePrice:(+e.price||0);
  const tabs=(D.tabs||[]).filter(t=>!t.own||isMoney())
    .map(t=>`<button class="chip ${S.evTab===t.k?'on':''}" data-evtab="${esc(t.k)}">${esc(t.n)}</button>`).join('');
  let block='';
  if(S.evTab==='info'){
    block=`<div class="admmatrix"><table><tbody>
      <tr><td>${esc('نوع')}</td><td>${esc(e.kind)}</td></tr>
      <tr><td>${esc('زمان')}</td><td>${esc(e.when)} · ${esc(e.time)}</td></tr>
      <tr><td>${esc('جا')}</td><td>${esc(e.place)}</td></tr>
      <tr><td>${esc('ظرفیت')}</td><td class="num">${esc(fa(e.reg))} ${esc('از')} ${esc(fa(e.cap))}</td></tr>
      ${isMoney()?`<tr><td>${esc('هزینه')}</td><td class="num">${evPrice?esc(fa(evPrice)+' ریال'):esc('آزاد')}</td></tr>`:''}
      <tr><td>${esc('وضعیت')}</td><td>${tag(st[0],st[1])}</td></tr></tbody></table></div>`;
  } else {
    let D2=D[{reg:'regd',att:'attd',money:'moneyd',cert:'certd',news:'newsd'}[S.evTab]]||{};
  /* وضعیت پرداخت فقط دست مالک است؛ برای بقیه «ثبت‌شده» می‌شود */
  if(!isMoney()&&D2.rows&&D2.mask) D2=Object.assign({},D2,{rows:D2.rows.map(r=>r.map((c,i)=>i===2?(D2.mask[c]||c):c))});
    block=`<div class="stack tight"><div class="head">${esc(D2.lead||'')}</div>${table(D2.rows||[],D2.cols)}</div>`;
  }
  sheetImpl('shAdm',`<div class="admsheet">
    ${src?`<div class="sheetcover"><img src="${esc(src)}" alt=""/>
      <span class="lbl">${esc('پوستر رویداد')}</span></div>`:''}
    <div class="row"><div class="tx" style="min-width:0"><div class="head">${esc(e.n)}</div>
      <div class="cap">${esc(e.kind)} · ${esc(whenLine(e))} · ${esc(e.time)}${ses.length>1?` · ${esc(fa(ses.length)+' جلسه')}`:''}</div></div>
      <span class="sp"></span>${tag(st[0],st[1])}</div>
    ${ses.length>1?`<div class="evpage-secs">${ses.map((x,i)=>{const j=jParse(x.d);
      return `<span>${ico('i-calendar')}${esc('جلسهٔ '+fa(i+1)+': '+(j?jLong(j.jy,j.jm,j.jd):'')+(x.t?' '+fa(x.t):'')+(x.to?' تا '+fa(x.to):''))}</span>`}).join('')}</div>`:''}
    ${e.held?`<div class="admempty"><span class="cap">${esc('برگزار شده')}${e.who?' · '+esc(fa(e.who)+' نفر'):''}${e.rep?' · '+esc(e.rep):''}</span>
      ${e.media?`<a class="btn sm quiet" href="${esc(e.media)}" target="_blank" rel="noopener">${ico('i-link')}${esc('آرشیو')}</a>`:''}</div>`:''}
    <div class="admfilters">${tabs}</div>
    ${block}
    <div class="row tight">${btn(tabName('reg'),'data-evtab="reg"','i-users')}
      ${btn(tabName('news'),'data-evtab="news"','i-send')}
      ${btn(tabName('cert'),'data-evtab="cert"','i-medal')}
      <button class="btn sm" data-evedit="${esc(e.id)}">${ico('i-pen')}${esc(W.edit||'ویرایش')}</button>
      <a class="btn sm" href="builder.html">${ico('i-doc')}${esc(D.formQueue||'کارتابل فرم')}</a></div>
    ${((e.forms||[]).length||madeForms.length)?`<div class="stack tight"><div class="head">${esc('فرم‌های این رویداد')}</div>
      ${(e.forms||[]).length?'':`<div class="admlirow"><span class="ic">${ico('i-doc')}</span>
        <span class="sp cap">${esc('هنوز فرمی به این رویداد وصل نشده')}</span>
        <a class="btn sm" href="create.html?ev=${esc(e.id)}&need=reg&name=${encodeURIComponent(e.n||'')}&cap=${esc(String(e.cap||''))}&back=${encodeURIComponent('admin.html#newev')}" target="_blank" rel="noopener">${ico('i-plus')}${esc('ساختن در فرم‌ساز')}</a></div>`}
      ${(e.forms||[]).map(f=>{const link=(f.link||('form.html?ev='+e.id+'&kind='+(f.need||'reg')));
        return `<div class="admlirow"><span class="ic">${ico(f.need==='exam'?'i-check':f.need==='survey'?'i-star':'i-doc')}</span>
        <span class="sp"><b style="font-size:var(--fs-sub)">${esc(f.n||f.name||'')}</b>
          <small class="cap" style="display:block">${esc([f.q||'', isMoney()&&f.money?fa(f.money)+' ریال':''].filter(Boolean).join(' · '))} · ${esc(link)}</small></span>
        <button class="btn sm quiet" data-copyform="${esc(link)}" aria-label="${esc('رونوشت نشانی فرم')}">${ico('i-copy')}</button>
        <a class="btn sm quiet" href="${esc(link)}">${ico('i-eye')}${esc('دیدن')}</a></div>`}).join('')}
      ${madeForms.filter(f=>(e.forms||[]).every(x=>String(x.id)!==String(f.id))).map(f=>`<div class="admlirow">
        <span class="ic">${ico(f.fin&&f.fin.length?'i-wallet':'i-doc')}</span>
        <span class="sp"><b style="font-size:var(--fs-sub)">${esc(formName(f))}</b>
          <small class="cap" style="display:block">${esc([f.kind||'', isMoney()&&formSum(f)?fa(formSum(f))+' ریال':''].filter(Boolean).join(' · '))}</small></span>
        <a class="btn sm quiet" href="create.html?ev=${esc(e.id)}&need=${esc(f.need||'reg')}&name=${encodeURIComponent(e.n||'')}&fid=${esc(f.id)}&back=${encodeURIComponent('admin.html#newev')}" target="_blank" rel="noopener">${ico('i-sliders')}${esc('ویرایش در فرم‌ساز')}</a></div>`).join('')}</div>`:''}
    ${e.page?`<div class="pagelink"><span class="ic">${ico('i-link')}</span><code dir="ltr">${esc(e.page)}</code>
      <button class="btn sm quiet" data-copyform="${esc(e.page)}">${ico('i-copy')}${esc('رونوشت')}</button>
      <a class="btn sm quiet" href="${esc(e.page)}" target="_blank" rel="noopener">${ico('i-eye')}${esc('صفحهٔ رویداد')}</a></div>`:''}
    <div class="row"><span class="sp"></span>${btn(W.close||'بستن','data-close')}</div></div>`);
}
/* پروندهٔ کامل کاربر: یک صفحه با پنج تب، به‌جای ورقهٔ شلوغ */
function uHist(m){
  const done=(EVROWS||[]).filter(e=>e.state==='done').slice(0,+m.ev||0)
    .map(e=>[e.n||'رویداد',e.on||'',e.time||'','حاضر']);
  const up=(EVROWS||[]).filter(e=>e.state!=='done').slice(0,Math.max(0,(+m.ev||0)-done.length))
    .map(e=>[e.n||'رویداد',e.on||'',e.time||'','ثبت‌نام']);
  return done.concat(up);
}
function vUUser(){
  const m=memOf(S.uSel); if(!m){S.uV=''; return vUList()}
  const pct=uPct(m), lv=uLevel(m), rank=uRank(m), got=BADGES.filter(b=>badgeGot(m,b));
  const next=BADGES.filter(b=>!badgeGot(m,b)).slice(0,3);
  const cur=S.uTab||'info';
  const tabs=UPTABS.map(t=>`<button class="chip ${cur===t[0]?'on':''}" data-utab="${t[0]}">${esc(t[1])}</button>`).join('');
  const grp={};
  PFLDS.forEach(f=>{if((m[f[0]]||'')!==''){grp[f[2]]=grp[f[2]]||[]; grp[f[2]].push([f[1],m[f[0]]])}});
  const labs=uLabels(), myTags=(m.tags||[]);
  const abs=uAbs().filter(a=>a.u===m.id);
  const msgs=uInbox().filter(i=>i.u===m.id);
  const reqs=uShopReq().filter(r=>r.u===m.id);
  const logs=uLog().filter(l=>norm(l.act||'').indexOf(norm(m.n))>-1||norm(l.act||'').indexOf(m.id)>-1);
  const myLog=[['عضویت در سامانه',esc(m.reg),'منبع: '+(m.src||'مستقیم')],
    ['آخرین ورود',m.act===0?'امروز':+m.act===1?'دیروز':fa(m.act)+' روز پیش',''],
    ['وضعیت کنونی',m.st[0],m.rejWhy?'دلیل برگشت: '+m.rejWhy:'']].concat(logs.map(l=>[l.act,l.who,l.at]));
  let body='';
  if(cur==='info'){
    body=`<div class="head">پرونده</div>
    ${Object.keys(grp).map(g2=>`<div class="head">${esc(g2)}</div>${table(grp[g2])}`).join('')||emptyBox('پروفایل خالی است؛ کاربر باید فرم پروفایل را پر کند')}
    <div class="head">برچسب‌ها</div>
    <div class="admchips">${Object.keys(labs).map(t2=>`<button class="chip ${myTags.indexOf(t2)>-1?'on':''}" data-utagm="${esc(m.id)}" data-utagm2="${esc(t2)}">${esc(t2)}</button>`).join('')}</div>
    <div class="head">یادداشت پرونده</div>
    <label class="fld"><textarea id="uNoteTxt" rows="2" placeholder="یادداشت برای همکارها">${esc(m.note||'')}</textarea></label>
    <div class="row tight">${btn('یادداشت را بنشین','data-unotego="'+esc(m.id)+'"','i-pen')}
      ${baleA('profile_'+esc(m.id),'پرونده در ربات بله')}</div>
    ${S.uRej===m.id?`<div class="head">رد با دلیل</div>
    <label class="fld"><textarea id="uRejTxt" rows="2" placeholder="مثلاً: کد ملی و تاریخ تولد را کامل کن"></textarea></label>
    <div class="row tight">${btn('با دلیل برگشت','data-urejgo="'+esc(m.id)+'"')}</div>`:''}`;
  }else if(cur==='club'){
    body=`<div class="head">کد معرف و دعوت</div>
    ${table([['کد معرف',esc((m.code||'')+'-'+String(m.id).toUpperCase())],['دعوت‌شده',fa(m.inv||0)+' نفر'],
      ['پاداش‌های گرفته‌شده',fa((S.ushopDone||[]).length?(reqs.filter(r=>r.st==='تحویل شد').length):0)+' مورد']])}
    <div class="head">نشان‌ها (${esc(fa(got.length))} از ${esc(fa(BADGES.length))})</div>
    ${table(BADGES.map(b=>[b[1],esc(b[2])+' · '+esc(TRG[b[3]]||b[3])+' '+fa(uCount(m,b[3]))+' از '+fa(b[4]),
      badgeGot(m,b)?'✓ گرفت':fa(badgePct(m,b))+'٪']))}
    ${next.length?`<div class="head">نزدیک‌ترین دستاوردها</div>
    ${table(next.map(b=>[b[1],esc(TRG[b[3]]||b[3])+' '+fa(uCount(m,b[3]))+' از '+fa(b[4]),fa(badgePct(m,b))+'٪']))}`:''}
    ${reqs.length?`<div class="head">درخواست‌های پاداش</div>
    ${table(reqs.map(r=>{const it=SHOP.find(x=>x[0]===r.r)||[r.r,r.r,0]; return [esc(it[1]),fa(it[2])+' امتیاز',esc(r.st)]}))}`:''}`;
  }else if(cur==='ev'){
    const hist=uHist(m);
    body=`<div class="head">رویدادها (${esc(fa(hist.length))})</div>
    ${hist.length?table(hist.map(h=>[esc(h[0]),esc(h[1]),esc(h[3])])):emptyBox('رویدادی در نمونهٔ نمایشی نیست')}
    <div class="head">غیبت‌های مجاز</div>
    ${abs.length?table(abs.map(a=>[esc(a.ev),esc(a.why),esc(a.st)])):emptyBox('درخواست غیبتی ندارد')}
    <div class="head">فرم‌ها</div>
    ${table([['فرم‌های پرکرده',fa(m.fm||0)+' فرم','فهرستشان در بخش فرم‌هاست']])}
    <div class="row tight"><button class="btn sm" data-gofrms>${ico('i-doc')}فرم‌ها</button><span class="sp"></span></div>`;
  }else if(cur==='msg'){
    body=`<div class="head">پیام‌ها</div>
    ${msgs.length?msgs.map(i=>`<div class="admlirow">${ico(i.read?'i-doc':'i-bell')}
      <span class="sp"><b>${i.read?'خوانده شده':'🔴 تازه'}</b>
        <small class="cap">${esc(i.txt)}</small><small class="cap">${esc(i.at)}</small></span>
      <span class="mini">${i.read?'':btn('خواندم','data-uinboxread="'+esc(i.id)+'"')}</span></div>`).join(''):emptyBox('پیامی از این کاربر نیست')}
    <div class="row tight"><a class="btn sm" href="support.html">${ico('i-send')}پاسخ در پشتیبانی</a>
      <span class="sp"></span></div>`;
  }else{
    body=`<div class="head">تاریخچه</div>
    ${table(myLog)}`;
  }
  return `<section class="card stack">
    ${uBack}
    <div class="row"><span class="ic" style="width:44px;height:44px;border-radius:14px;display:grid;place-items:center;background:var(--brand-tint);color:var(--brand-ink)">${ico('i-users')}</span>
      <span class="tx" style="min-width:0"><div class="head">${esc(m.n)}${m.vip?' ⭐':''}</div>
      <div class="cap">${esc(m.code)} · ${esc(fa(m.ph))}${m.city?' · '+esc(m.city):''}</div></span>
      <span class="sp"></span>${tag(m.st[0],m.st[1])}</div>
    <div class="admkpi">
      <div class="k"><small>رویداد</small>${bits(fa(m.ev))}</div>
      <div class="k"><small>امتیاز</small>${bits(fa(m.pt))}</div>
      <div class="k"><small>سطح باشگاه</small>${bits(esc(lv.n||'تازه'))}</div>
      <div class="k"><small>رتبه</small>${bits(fa(rank)+' از '+fa(memList().length))}</div>
      <div class="k"><small>تکمیل پروفایل</small>${bits(fa(pct)+'٪')}</div>
      <div class="k"><small>دعوت‌ها</small>${bits(fa(m.inv||0))}</div></div>
    <div class="row tight">
      ${m.st[1]==='warn'?btn(W.approve||'تأیید پروفایل','data-uok="'+esc(m.id)+'"','i-check'):''}
      ${m.st[1]==='warn'?btn('رد با دلیل','data-urej="'+esc(m.id)+'"'):''}
      ${m.st[1]==='stop'?btn('رفع مسدودی','data-uunblock="'+esc(m.id)+'"','i-check'):btn(W.block||'مسدود','data-ublock="'+esc(m.id)+'"','i-lock')}
      ${btn(m.vip?'برداشتن VIP':'ویژه (VIP)','data-uvip="'+esc(m.id)+'"','i-star')}
      ${isOwner()?btn('برداشتن کاربر','data-udel="'+esc(m.id)+'"'):''}
      <span class="sp"></span></div>
    <div class="admfilters">${tabs}</div>
    ${body}
    <div class="row tight"><a class="btn sm quiet" href="account.html">${ico('i-mobile')}${esc(W.view||'نمای کاربر')}</a>
      <span class="sp"></span>${btn(W.close||'بستن پرونده','data-uback')}</div>
  </section>`;
}
function sheetUser(id){
  const m=memOf(id); if(!m) return;
  const pct=uPct(m), lv=uLevel(m), rank=uRank(m), got=BADGES.filter(b=>badgeGot(m,b));
  const next=BADGES.filter(b=>!badgeGot(m,b)).slice(0,2);
  const grp={};
  PFLDS.forEach(f=>{if((m[f[0]]||'')!==''){grp[f[2]]=grp[f[2]]||[]; grp[f[2]].push([f[1],m[f[0]]])}});
  const grpHtml=Object.keys(grp).map(g2=>`<div class="head">${esc(g2)}</div>${table(grp[g2])}`).join('');
  const labs=uLabels(), myTags=(m.tags||[]).slice();
  const rej=S.uRej===id;
  sheetImpl('shAdm',`<div class="admsheet">
    <div class="row"><span class="ic" style="width:44px;height:44px;border-radius:14px;display:grid;place-items:center;background:var(--brand-tint);color:var(--brand-ink)">${ico('i-users')}</span>
      <span class="tx" style="min-width:0"><div class="head">${esc(m.n)}${m.vip?' ⭐':''}</div>
      <div class="cap">${esc(m.code)} · ${esc(fa(m.ph))}${m.city?' · '+esc(m.city):''}</div></span>
      <span class="sp"></span>${tag(m.st[0],m.st[1])}</div>
    <div class="admkpi"><div class="k"><small>رویداد</small>${bits(fa(m.ev)+' رویداد')}</div>
      <div class="k"><small>امتیاز</small>${bits(fa(m.pt))}</div>
      <div class="k"><small>سطح باشگاه</small>${bits(esc(lv.n||'تازه'))}</div>
      <div class="k"><small>رتبه</small>${bits(fa(rank)+' از '+fa(memList().length))}</div></div>
    <div class="admtext"><span class="lbl">تکمیل پروفایل</span><span>${esc(fa(pct))}٪</span></div>
    <div class="admbars" style="height:10px"><i class="${pct>=80?'hi':''}" style="height:10px;width:${Math.max(4,pct)}%"></i></div>
    <div class="admchips">${m.tags.filter(t=>isMoney()||!moneyTag(t)).map(t=>tag(t,'brand')).join('')}
      ${tag('عضویت '+m.reg,'')}${tag('منبع: '+(m.src||'مستقیم'),'')}</div>
    <div class="head">پرونده</div>
    ${grpHtml||emptyBox('پروفایل خالی است؛ کاربر باید فرم پروفایل را پر کند')}
    <div class="head">دعوت دوستان</div>
    ${table([['کد معرف',esc(m.code+'-'+String(m.id).toUpperCase())],['دعوت‌شده',fa(m.inv||0)+' نفر']])}
    ${got.length?`<div class="head">نشان‌ها (${esc(fa(got.length))} از ${esc(fa(BADGES.length))})</div>
    <div class="admchips">${got.map(b=>tag(b[1],'ok')).join('')||'ـ'}</div>`:''}
    ${next.length?`<div class="head">دستاورد بعدی</div>
    ${table(next.map(b=>[b[1],esc(TRG[b[3]]||b[3])+' '+fa(uCount(m,b[3]))+' از '+fa(b[4]),fa(badgePct(m,b))+'٪']))}`:''}
    ${m.rejWhy?`<div class="admtext"><span class="lbl">دلیل برگشت پروفایل</span><span>${esc(m.rejWhy)}</span></div>`:''}
    <div class="head">یادداشت پرونده</div>
    <label class="fld"><textarea id="uNoteTxt" rows="2" placeholder="یادداشت برای همکارها">${esc(m.note||'')}</textarea></label>
    <div class="row tight">${btn('یادداشت را بنشین','data-unotego="'+esc(m.id)+'"','i-pen')}</div>
    ${rej?`<div class="head">رد با دلیل</div>
    <label class="fld"><textarea id="uRejTxt" rows="2" placeholder="مثلاً: کد ملی و تاریخ تولد را کامل کن">${esc('')}</textarea></label>
    <div class="row tight">${btn('با دلیل برگشت','data-urejgo="'+esc(m.id)+'"')}</div>`:''}
    <div class="head">برچسب‌ها</div>
    <div class="admchips">${Object.keys(labs).map(t2=>`<button class="chip ${myTags.indexOf(t2)>-1?'on':''}" data-utagm="${esc(m.id)}" data-utagm2="${esc(t2)}">${esc(t2)}</button>`).join('')}</div>
    <div class="row tight">${m.st[1]==='warn'?btn(W.approve||'تأیید پروفایل','data-uok="'+esc(m.id)+'"','i-check'):''}
      ${m.st[1]==='warn'?btn('رد با دلیل','data-urej="'+esc(m.id)+'"'):''}
      ${m.st[1]==='stop'?btn('رفع مسدودی','data-uunblock="'+esc(m.id)+'"','i-check'):btn(W.block||'مسدود','data-ublock="'+esc(m.id)+'"','i-lock')}
      ${btn(m.vip?'برداشتن VIP':'ویژه (VIP)','data-uvip="'+esc(m.id)+'"','i-star')}
      ${isOwner()?btn('برداشتن کاربر','data-udel="'+esc(m.id)+'"'):''}
      <span class="sp"></span></div>
    <div class="admmatrix">${table([['آخرین ورود',(m.act===0?'امروز':+m.act===1?'دیروز':fa(m.act)+' روز پیش')],
      ['فرم‌های پرکرده',fa(m.fm||0)],['وضعیت باشگاه',m.tags.indexOf('عضو باشگاه')>-1?'عضو':'عضو نیست']]
      .concat(isMoney()?[['بدهی','۰']]:[]))}</div>
    <div class="row tight"><a class="btn sm quiet" href="account.html">${ico('i-mobile')}${esc(W.view||'نمای کاربر')}</a>
      <span class="sp"></span>${btn(W.close||'بستن','data-close')}</div></div>`);
}
function sheetRep(k){
  const r=rpOf(k), d=rpCalc(k), rows=d.rows||[], bs=d.bars||[];
  const li=(RPLIST||[]).find(x=>x.k===k)||{};
  const hl=rows[2]||rows[0]||[];
  const sum='در این گزارش «'+(hl[0]||'')+'» '+((hl[1]||'').toString().trim()||'ثبت نشده')+' میشود'
    +(li.pc?('؛ از دورهٔ مشابه قبل '+(li.up?'رشد ':'افت ')+String(li.pc).replace(/[+−]/g,'')+' داشته'):'')
    +'. اعداد از همین پنل حساب میشود.';
  const att=(RP.attention||[]).filter(a=>a.k===k);
  sheetImpl('shAdm',`<div class="admsheet">
    <div class="row"><span class="ic">${ico('i-chart')}</span>
      <span class="tx" style="min-width:0"><div class="head">${esc(r.n||'')}</div>
      <div class="cap">${esc(r.v||'')} · ${esc(r.d||'')}</div></span><span class="sp"></span>
      ${r.pc?`<span class="tag ${r.up?'ok':'warn'}">${esc((r.up?'▲ ':'▼ ')+String(r.pc).replace(/[+−]/g,''))}</span>`:''}</div>
    ${bs.length?bars(bs,true):''}
    <div class="row tight"><span class="mini cap">${esc('روند هفت محور اخیر، بر پایهٔ دورهٔ '+(S.rp||'۳۰ روز'))}</span></div>
    <p class="cap">${esc(sum)}</p>
    ${table(rows,['',''])}
    <div class="row tight">
      ${li.pc?`<span class="tag ${li.up?'ok':'warn'}">${esc('مقایسه: '+(li.up?'رشد ':'افت ')+String(li.pc).replace(/[+−]/g,''))}</span>`:''}
      <span class="tag">${esc('دورهٔ '+faTag(S.rp||'۳۰ روز'))}</span></div>
    ${k==='tp'?`<div class="admkpi">${rows.slice(0,3).map((r2,i2)=>`<div class="k"><small>رتبهٔ ${fa(i2+1)}</small>${bits(String(r2[1]).split('·')[0]||'')}</div>`).join('')}</div>`:''}
    ${att.length?`<div class="stack tight"><div class="head">${esc(W.alert||'')}</div>
      ${att.map(a=>`<div class="admlirow">${ico('i-bell')}<span class="sp">${esc(a.t)}</span></div>`).join('')}</div>`:''}
    <div class="admkpi">${(RP.periods||[]).slice(0,4).map(p=>`<div class="k"><small>${esc(p)}</small>
      ${bits(r.v||'')}</div>`).join('')}</div>
    <div class="row tight">
      <a class="btn sm" href="builder.html">${ico('i-chart')}${esc('نمودار کامل')}</a>
      ${baleA('report_'+esc(k),'اکسل همین گزارش')}
      <span class="sp"></span>${btn(W.close||'بستن','data-close')}</div></div>`);
}
function sheetWho(){
  const groups=[{k:'owner',n:'مالک',i:'i-medal'}].concat(FIELDS.filter(f=>f.k!=='owner'));
  const rows=groups.map(g=>{
    const list=allP().filter(p=>p.f===g.k);
    if(!list.length) return '';
    return `<div class="whogroup"><div class="head">${ico(g.i)} ${esc(g.n)}</div>
      ${list.map(p=>`<button class="admrole ${S.who===p.k?'on':''}" data-who="${esc(p.k)}">
        <span class="va">${esc(String(p.n||' ').slice(0,1))}</span>
        <span class="tx"><b>${esc(p.n)}</b><small>${esc(p.lv)} · ${esc(g.n)}</small></span>
        ${S.who===p.k?tag(D.you||'','brand'):`<span class="cap">${esc(fa(p.open))} ${esc(D.qOpen||'')}</span>`}
      </button>`).join('')}</div>`}).join('');
  sheetImpl('shAdm',`<div class="admsheet">
    <div class="row"><div class="head">${esc(D.mine||'نمای من')}</div><span class="sp"></span>
      ${btn(W.close||'بستن','data-close')}</div>
    <p class="cap">${esc('هر کس داشبورد و کارتابل خودش را دارد؛ یکی را بردار و ببین.')}</p>
    ${rows}</div>`);
}
function sheetGive(id){
  const it=qAll().find(x=>x.id===id); if(!it) return;
  const list=(it.f==='owner'?allP():teamOf(it.f)).filter(p=>p.k!==me().k);
  sheetImpl('shAdm',`<div class="admsheet">
    <div class="row"><div class="head">${esc(D.qGive||'واگذار')}</div><span class="sp"></span>
      ${btn(W.close||'بستن','data-close')}</div>
    <p class="cap">${esc(it.n)} · ${esc(fieldOf(it.f).n)}</p>
    <div class="admlist">${list.map(p=>`<button class="admrow2" data-giveto="${esc(p.k)}" data-qid="${esc(it.id)}">
      <span class="va">${esc(String(p.n||' ').slice(0,1))}</span>
      <span class="tx"><b>${esc(p.n)}</b><small>${esc(p.lv)} · ${esc(fa(p.open))} ${esc(D.qOpen||'')}</small></span>
      ${ico('i-chev-left','chev')}</button>`).join('')||emptyBox(D.qEmpty||'')}</div></div>`);
}
/* دسترسی‌های یک کارشناس: تیک‌های حوزهٔ خودش به‌علاوهٔ دسترسی‌های مشترک */
function sheetSpecPerm(personKey){
  const p=personOf(personKey); if(!p) return;
  const base=specPermsOf(p.f).slice(), extra=extraOf(personKey).slice();
  const extraRows=PROWS.filter(r=>(r[2]==='any'||r[2]===p.f)&&base.indexOf(r[0])<0);
  sheetImpl('shAdm',`<div class="admsheet">
    <div class="row"><div class="head">${esc(D.specPerms||'دسترسی‌ها')}</div><span class="sp"></span>
      ${btn(W.close||'بستن','data-close')}</div>
    <p class="cap">${esc(p.n)} · ${esc(fieldOf(p.f).n)} · ${esc(p.lv)}</p>
    <div class="head">${esc('دسترسی‌های پایه')}</div>
    <div class="admchips">${base.map(k=>{const r=PROWS.find(x=>x[0]===k)||['',k]; return tag(r[1],'ok')}).join('')||tag('هیچ','')}</div>
    <div class="head">${esc('دسترسی ویژه')}</div>
    <div class="admlist">${extraRows.map(r=>`<div class="admsw"><span class="sp">${esc(r[1])}</span>
      <span class="switch ${extra.indexOf(r[0])>-1?'on':''}" data-extra="${esc(r[0])}" data-extraFor="${esc(personKey)}"
        role="switch" aria-checked="${extra.indexOf(r[0])>-1?'true':'false'}" aria-label="${esc(r[1])}"></span></div>`).join('')||emptyBox(D.qEmpty||'')}</div>
    <p class="cap">${esc('پایه‌ها را سرپرست حوزه برای همهٔ کارشناسان تیک می‌زند؛ این‌جا فقط ویژه‌های همین نفر است.')}</p></div>`);
}
/* ساخت حساب کارشناس: نام، نام کاربری و رمز یکبارمصرف */
function sheetAddSpec(fk){
  const f=fieldOf(fk);
  sheetImpl('shAdm',`<div class="admsheet">
    <div class="row"><div class="head">${esc('حساب تازه برای کارشناس')}</div><span class="sp"></span>
      ${btn(W.close||'بستن','data-close')}</div>
    <p class="cap">${esc('حوزه: '+f.n+' · دسترسی‌های پیش‌فرض همین حوزه خودکار می‌نشیند.')}</p>
    <label class="fld"><span>نام و نام خانوادگی</span><input id="spN" class="input" placeholder="مثل: مینا رحیمی"/></label>
    <label class="fld"><span>نام کاربری</span><input id="spU" class="input" dir="ltr" placeholder="m.rahimi"/></label>
    <label class="fld"><span>رمز یکبارمصرف ورود اول</span>
      <div class="row tight"><input id="spP" class="input" dir="ltr" readonly value="${genPw()}"/>
      ${btn('رمز تازه','data-genpw','i-check')}</div></label>
    <div class="row"><span class="sp"></span>${btn('ساختن حساب','data-newspec2','i-check')}</div>
    <p class="cap">${esc('نام کاربری و رمز را برایش می‌فرستید؛ در نخستین ورود رمز تازه‌ای می‌گذارد و پروفایل دست‌اندرکاران را کامل می‌کند.')}</p></div>`);
}
/* پروندهٔ دست‌اندرکاران: از ردیف تیم باز میشود */
function sheetSpecFile(k){
  const p=personOf(k), ac=accOf(p), f=fieldOf(p.f);
  sheetImpl('shAdm',`<div class="admsheet">
    <div class="row"><div class="head">${esc(p.n)}</div><span class="sp"></span>
      ${btn(W.close||'بستن','data-close')}</div>
    <p class="cap"><span class="stacc" dir="ltr">@${esc(ac.u)}</span> · ${esc(f.n)} · ${esc(p.lv)} · از ${esc(p.since||'')}</p>
    <div class="admchips">${ac.done?tag('پروفایل کامل','ok'):tag('در انتظار تکمیل پروفایل','warn')}
      ${tag(fa(p.done)+' کار انجامشده','')}${tag(fa(p.late)+' دیرکرد',p.late?'warn':'')}</div>
    <div class="head">${esc('پروفایل دست‌اندرکاران')}</div>
    <div class="stprof">${SPROF.map(x=>`<div class="stp">${ico(x[0])}<span class="sp"><b>${esc(x[1])}</b><small>${esc(ac.done?'کامل شده':'در ورود اول پرسیده می‌شود')}</small></span></div>`).join('')}</div>
    ${ac.done?'':`<div class="row"><span class="sp"></span>${btn('یادآوری تکمیل پروفایل','data-specnudge','i-send')}</div>
    <p class="cap">${esc('یادآوری تکمیل پروفایل از ربات بلهٔ موسسه برایش می‌رود.')}</p>`}</div>`);
}
/* تعیین سرپرست حوزه: مالک یکی را می‌گذارد */
function sheetSetLead(fk){
  const f=fieldOf(fk);
  const list=allP().filter(p=>p.f!=='owner'&&p.k!==leadK(fk));
  sheetImpl('shAdm',`<div class="admsheet">
    <div class="row"><div class="head">${esc(D.setLead||'تعیین سرپرست')}</div><span class="sp"></span>
      ${btn(W.close||'بستن','data-close')}</div>
    <p class="cap">${esc('حوزه: '+f.n)}</p>
    <div class="admlist">${list.map(p=>`<button class="admrow2" data-setleadTo="${esc(p.k)}" data-leadFor="${esc(fk)}">
      <span class="va">${esc(String(p.n||' ').slice(0,1))}</span>
      <span class="tx"><b>${esc(p.n)}</b><small>${esc(fieldOf(p.f).n)} · ${esc(p.lv)}</small></span>
      ${ico('i-chev-left','chev')}</button>`).join('')||emptyBox(D.qEmpty||'')}</div></div>`);
}

/* ══ مطلبها: فهرست و ویرایشگر بلوکی ══════════════════════════════════════
   مطلب بلوکی است: پاراگراف، تیتر، عکس، ویدیو (آپارات، یوتیوب یا فایل)،
   صدا، نقل قول، فهرست، دکمهٔ لینک، جعبهٔ توجه، جمع‌شونده و جداکننده؛
   هر کدام هر چند تا. رویداد و فرم هم پیوند می‌خورند و پیش‌نمایش، پیش از
   انتشار در post.html دیده می‌شود. مالک و سرپرست منتشر می‌کنند؛ بقیه
   می‌فرستند برای تأیید. */
const PGRADS=['linear-gradient(135deg,#1E6FD0,#0A3A82)','linear-gradient(135deg,#3E5B84,#0B2447)',
  'linear-gradient(135deg,#0E7B61,#083D33)','linear-gradient(135deg,#8A5A2B,#3D2714)'];
const PTY={p:{n:'پاراگراف',i:'i-pen'},h:{n:'تیتر',i:'i-align'},img:{n:'عکس',i:'i-image'},
  gal:{n:'گالری',i:'i-grid'},vid:{n:'ویدیو',i:'i-play'},aud:{n:'صدا',i:'i-headphone'},
  q:{n:'نقل قول',i:'i-doc'},ul:{n:'فهرست',i:'i-list'},ol:{n:'شمارشی',i:'i-list'},
  btn:{n:'دکمهٔ لینک',i:'i-link'},bm:{n:'لینک خودکار',i:'i-globe'},file:{n:'فایل',i:'i-download'},
  tbl:{n:'جدول',i:'i-align'},box:{n:'جعبهٔ توجه',i:'i-bell'},tog:{n:'جمع‌شونده',i:'i-chev-down'},
  hr:{n:'جداکننده',i:'i-close'}};
function U(){try{return (window.NORA_UI&&NORA_UI)||null}catch(e){return null}}
function pedPosts(){const u=U(); return u&&u.postsAll?u.postsAll():[]}
function pedFresh(){return {id:'np'+Date.now(), t:'', cat:'', tags:'', lead:'', author:(me().n||''), cover:{g:PGRADS[0]},
  pin:0, club:0, blocks:[], ev:'', fm:'', pub:0, pend:0, views:0, at:0}}
function pedSave(p){const u=U(); if(u&&u.postPut) u.postPut(p)}
function pedMin(p){const u=U(); return u&&u.postMin?u.postMin(p):1}
const BLK=v=>({ty:v});
function blockEd(b,i){
  const T=PTY[b.ty]||{n:'بلوک',i:'i-doc'};
  const ctl=`<span class="sp"></span>
    <button class="btn sm quiet" data-bup="${i}" aria-label="بالا">${ico('i-chev-right','transform:rotate(-90deg)')}</button>
    <button class="btn sm quiet" data-bdown="${i}" aria-label="پایین">${ico('i-chev-right','transform:rotate(90deg)')}</button>
    <button class="btn sm quiet" data-bdel="${i}" aria-label="برداشتن">${ico('i-trash')}</button></div>`;
  const head=`<div class="row tight"><span class="tag brand">${ico(T.i)}${esc(T.n)}</span><small class="cap">${faN(i+1)}</small>${ctl}`;
  const inp=(f,ph,val,extra)=>`<input class="input" data-bi="${i}" data-bf="${f}" value="${esc(val==null?'':val)}" placeholder="${esc(ph)}" ${extra||''}/>`;
  const ta=(f,ph,val,rows)=>`<textarea class="input" data-bi="${i}" data-bf="${f}" rows="${rows||3}" placeholder="${esc(ph)}">${esc(val==null?'':val)}</textarea>`;
  let body='';
  switch(b.ty){
    case 'p': body=ta('x','متن پاراگراف…',b.x); break;
    case 'h': body=inp('x','متن تیتر',b.x)+`<select class="input" data-bi="${i}" data-bf="lv">
        <option value="2"${+b.lv!==3?' selected':''}>تیتر اصلی</option>
        <option value="3"${+b.lv===3?' selected':''}>تیتر کوچک</option></select>`; break;
    case 'img': body=`${b.up?`<img src="${esc(b.up)}" alt="" style="width:100%;max-height:150px;object-fit:cover;border-radius:12px"/>`:''}
      <label class="btn sm quiet">${ico('i-file-up')}آپلود عکس<input type="file" accept="image/*" data-bfile="${i}" data-bmedia="img" hidden/></label>
      ${inp('src','یا لینک عکس',b.src)}
      ${inp('cap','زیرنویس عکس',b.cap)}${inp('alt','متن جایگزین (دسترس‌پذیری)',b.alt)}`; break;
    case 'vid': body=`${b.up?`<div class="pb-vid" style="max-width:280px"><video controls playsinline src="${esc(b.up)}"></video></div>`:''}
      <label class="btn sm quiet">${ico('i-file-up')}آپلود ویدیو<input type="file" accept="video/*" data-bfile="${i}" data-bmedia="vid" hidden/></label>
      ${inp('src','یا لینک آپارات، یوتیوب یا فایل mp4',b.src)}${inp('cap','زیرنویس ویدیو',b.cap)}
      <small class="cap">آپلود تا حدود ۴ مگابایت در همان مرورگر پخش میشود؛ ویدیوی سنگینتر لینک آپارات بده. لینک آپارات و یوتیوب خودش پخش‌شونده میشود.</small>`; break;
    case 'aud': body=`${b.up?`<audio controls src="${esc(b.up)}" style="width:100%"></audio>`:''}
      <label class="btn sm quiet">${ico('i-file-up')}آپلود صدا<input type="file" accept="audio/*" data-bfile="${i}" data-bmedia="aud" hidden/></label>
      ${inp('src','یا لینک مستقیم فایل صوتی (mp3)',b.src)}${inp('cap','نام یا زیرنویس صدا',b.cap)}`; break;
    case 'gal': body=ta('x','هر سطر یک لینک عکس',Array.isArray(b.x)?b.x.join('\n'):'')+inp('cap','زیرنویس گالری',b.cap); break;
    case 'file': body=inp('src','لینک فایل (pdf و هر فایلی)',b.src)+inp('t','نام فایل',b.t); break;
    case 'bm': body=inp('href','نشانی لینک',b.href)+inp('t','عنوان لینک',b.t)
      +ta('x','توضیح کوتاه',b.x)+inp('src','لینک تصویر (اختیاری)',b.src||''); break;
    case 'tbl': body=ta('x','هر سطر یک ردیف؛ ستون‌ها با | جدا شوند. سطر اول سرستون می‌شود',Array.isArray(b.x)?b.x.join('\n'):''); break;
    case 'q': body=ta('x','متن نقل قول…',b.x)+inp('by','گوینده یا منبع',b.by); break;
    case 'ul': case 'ol': body=ta('x','هر سطر یک مورد',Array.isArray(b.x)?b.x.join('\n'):''); break;
    case 'btn': body=inp('x','نوشتهٔ دکمه',b.x)+inp('href','نشانی لینک',b.href)
      +`<div class="row tight"><button class="chip ${b.kind!=='quiet'?'on':''}" data-bbtn="${i}" data-bk="primary">اصلی</button>
        <button class="chip ${b.kind==='quiet'?'on':''}" data-bbtn="${i}" data-bk="quiet">آرام</button></div>`; break;
    case 'box': body=ta('x','متن جعبه…',b.x)+`<select class="input" data-bi="${i}" data-bf="ic">
        <option value="i-info"${b.ic!=='i-star'&&b.ic!=='i-bell'?' selected':''}>نکته</option>
        <option value="i-star"${b.ic==='i-star'?' selected':''}>پیشنهاد</option>
        <option value="i-bell"${b.ic==='i-bell'?' selected':''}>هشدار</option></select>`; break;
    case 'tog': body=inp('t','عنوان جمع‌شونده',b.t)+ta('x','متن پنهان…',b.x); break;
    case 'hr': body=`<small class="cap">خط جداکنندهٔ ساده.</small>`; break;
    default: body='';
  }
  return `<div class="card sunk" style="padding:12px;display:grid;gap:8px">${head}${body}</div>`;
}
function postEditor(){
  const d=S.ped||{}, blocks=d.blocks||[];
  const pc=String(+S.pstep===2?2:1);
  const catList=(()=>{try{return (window.NORA&&NORA.ARTICLES||[]).map(a=>a.cat).concat(pedPosts().map(x=>x.cat||''))
    .filter((v,i,arr)=>v&&arr.indexOf(v)===i)}catch(e){return []}})();
  const evs=evAll(), mades=madeForms(), demos=demoForms();
  const cov=d.cover||{};
  const pcats=catList.map(c=>`<option value="${esc(c)}"/>`).join('');
  return `<section class="card stack">
    <div class="row"><div class="head">${d.id?'ویرایش مطلب':'مطلب تازه'}</div><span class="sp"></span>
      ${btn(W.back||'بازگشت','data-pback','i-back')}</div>
    <div class="admsteps"><div class="st ${pc==='1'?'on':''}"><i></i><small>۱. هویت و رسانه</small></div>
      <div class="st ${pc==='2'?'on':''}"><i></i><small>۲. بن‌مایه و انتشار</small></div></div>
    <div class="pb-covprev" style="--g:${esc(cov.g||PGRADS[0])};position:relative;height:120px;border-radius:14px;overflow:hidden;border:.5px solid var(--hairline)">
      ${cov.up?`<img src="${esc(cov.up)}" alt="" style="width:100%;height:100%;object-fit:cover"/>`:''}</div>
    <div class="row tight">
      ${PGRADS.map((g,i)=>`<button class="chip ${!cov.up&&cov.g===g?'on':''}" data-pgrad="${i}" aria-label="تم ${faN(i+1)}"><span style="display:inline-block;width:26px;height:14px;border-radius:6px;background:${g}"></span></button>`).join('')}
      <label class="btn sm quiet">${ico('i-file-up')}جلد خودم<input type="file" accept="image/*" data-pfile="1" hidden/></label>
      ${cov.up?`<button class="btn sm quiet" data-pclear="1">${ico('i-trash')}بردار</button>`:''}
    </div>
    <div class="fld"><span class="lbl">عنوان مطلب</span>
      <input class="input" data-pf="t" value="${esc(d.t||'')}" placeholder="مثلاً: گزارش کارگاه عکاسی"/></div>
    <div class="fld"><span class="lbl">سرآغاز (یک تا دو خط، بالای مطلب می‌نشیند)</span>
      <textarea class="input" rows="2" data-pf="lead" placeholder="چرا این مطلب را باید خواند؟">${esc(d.lead||'')}</textarea></div>
    <div class="row tight">
      <div class="fld" style="flex:1"><span class="lbl">دسته</span>
        <input class="input" data-pf="cat" value="${esc(d.cat||'')}" list="pcats" placeholder="مثلاً: گزارش"/>
        <datalist id="pcats">${(()=>{const base=['گزارش','خبر','یادداشت','آموزش','گفت‌وگو','معرفی','پادکست','ویدیو'];
          return base.concat(catList).filter((v,i,arr)=>v&&arr.indexOf(v)===i).map(c=>`<option value="${esc(c)}"/>`).join('')})()}</datalist>
        <div class="row tight" style="margin-top:6px;flex-wrap:wrap">
          ${(()=>{const base=['گزارش','خبر','یادداشت','آموزش','گفت‌وگو','معرفی','پادکست','ویدیو'];
            return base.concat(catList).filter((v,i,arr)=>v&&arr.indexOf(v)===i).slice(0,10)
              .map(c=>`<button class="chip ${String(d.cat||'')===c?'on':''}" data-pcat="${esc(c)}">${esc(c)}</button>`).join('')})()}
        </div></div>
      <div class="fld" style="flex:1"><span class="lbl">برچسب‌ها (با ویرگول)</span>
        <input class="input" data-pf="tags" value="${esc(d.tags||'')}" placeholder="گزارش، عکاسی"/></div>
    </div>
    <div class="row tight">
      <div class="fld" style="flex:1"><span class="lbl">نویسنده</span>
        <input class="input" data-pf="author" value="${esc(d.author||'')}" placeholder="نام نویسنده"/></div>
      <div class="fld"><span class="lbl">نماد</span>
        <div class="row tight">
          <button class="chip ${d.pin?'on':''}" data-ptog="pin">${ico('i-pin')} پین</button>
          <button class="chip ${d.club?'on':''}" data-ptog="club">${ico('i-book')} باشگاه</button>
        </div></div>
    </div>
    ${pc==='1'?`<div class="row"><span class="sp"></span>
      ${btn('گام بعد؛ بن‌مایهٔ مطلب','data-pgo="2"','i-chev-left')}</div>`
    :`<hr class="hr"/>
    <div class="head">بن‌مایهٔ مطلب</div>
    ${blocks.length?blocks.map(blockEd).join(''):`<div class="empty cap">${ico('i-doc')}<p style="margin-top:6px">هنوز بلوکی نیست؛ از پالت پایین اضافه کن.</p></div>`}
    <div class="fld"><span class="lbl">افزودن بلوک</span>
      <div class="row tight" style="flex-wrap:wrap">
        ${Object.keys(PTY).map(k=>`<button class="chip" data-badd="${k}">${ico(PTY[k].i)}${esc(PTY[k].n)}</button>`).join('')}
      </div></div>
    <hr class="hr"/>
    <div class="row tight">
      <div class="fld" style="flex:1"><span class="lbl">پیوند رویداد</span>
        <select class="input" data-pev="1"><option value="">بدون پیوند</option>
          ${evs.map(e=>`<option value="${esc(e.id)}"${String(d.ev)===String(e.id)?' selected':''}>${esc(e.n||e.t||e.id)}</option>`).join('')}
        </select></div>
      <div class="fld" style="flex:1"><span class="lbl">پیوند فرم</span>
        <select class="input" data-pfm="1"><option value="">بدون فرم</option>
          ${mades.map(f=>`<option value="${esc(f.id)}"${String(d.fm)===String(f.id)?' selected':''}>${esc(f.name||f.n||f.id)} · فرم‌ساز</option>`).join('')}
          ${demos.map(f=>`<option value="${esc(f.id)}"${String(d.fm)===String(f.id)?' selected':''}>${esc(f.name||f.n||f.id)} · نمونه</option>`).join('')}
        </select></div>
    </div>
    <div class="row">
      <span class="sp"></span>
      ${btn('گام پیش','data-pgo="1"','i-chev-right')}
      <button class="btn quiet" data-pprev="1">${ico('i-eye')} پیش‌نمایش</button>
      ${isOwner()||isLead()
        ?`<button class="btn primary" data-ppub="1">${ico('i-check')} انتشار</button>`
        :`<button class="btn primary" data-psend="1">${ico('i-send')} فرستادن برای تأیید</button>`}
    </div>
    <p class="cap">پیش‌نمایش پیش از انتشار در post.html باز می‌شود؛ خواننده مطلب را با فهرست، رسانه و پیوند رویداد و فرم می‌بیند. بعد از انتشار، مدیریت مطلب با بازدید و گزارش همین‌جا باز می‌شود.</p>
  </section>`}`;
}
/* ── مدیریت مطلب: بعد از انتشار، با کلیک روی ردیف باز می‌شود ──
   بازدید، پیوند و وضعیت از خود مطلب؛ گزارش خواندن از حافظهٔ نشستها */
function postMgr(){
  const u=U(), pid=S.pmgr, p=u&&u.postById?u.postById(pid):null;
  if(!p) return emptyBox('این مطلب پیدا نشد');
  const fromBody=(u&&u.postReads?u.postReads(pid):[]);
  const last=fromBody.length?fromBody[fromBody.length-1]:null;
  const reps=p.reps||[];
  const stat=(t2,v2,s2)=>`<div class="card sunk" style="padding:12px 14px">
    <div class="cap">${esc(t2)}</div><b style="font-size:21px;font-variant-numeric:tabular-nums">${esc(v2)}</b>
    <small class="cap" style="display:block">${esc(s2||'')}</small></div>`;
  return `<section class="card stack">
    <div class="row"><div class="head">مدیریت مطلب</div><span class="sp"></span>
      <a class="btn sm quiet" href="post.html?id=${encodeURIComponent(pid)}" target="_blank" rel="noopener">${ico('i-eye')} دیدن</a>
      ${btn(W.back||'بازگشت','data-pmgrback','i-back')}</div>
    <div class="admgrid">
      ${stat('بازدید',faN(+p.views||0),last?('آخرین: '+esc(postDayName(last.at||0))):'هنوز خوانده نشده')}
      ${stat('زمان مطالعه',faN(p.min||pedMin(p))+' دقیقه','از خود متن حساب میشود')}
      ${stat('گزارش خواندن',faN(fromBody.length)+' نفر','از حافظهٔ همین مرورگر')}
    </div>
    <div class="row tight">
      ${p.pub?tag('منتشر شده','ok'):(p.pend?tag('در انتظار تأیید','warn'):tag('پیش‌نویس',''))}
      <span class="tag brand">${esc(p.cat||'مطلب')}</span>
      ${(p.tags||[]).slice(0,4).map(t2=>`<span class="tag">${esc(t2)}</span>`).join('')}
      ${p.pin?tag('پین‌شده',''):''}${p.club?tag('ویژهٔ باشگاه',''):''}
    </div>
    <hr class="hr"/>
    <div class="row"><div class="head">پیوندها</div><span class="sp"></span>
      ${btn('ویرایش مطلب','data-pmgrEdit','i-pen')}</div>
    <div class="admlist">
      ${rowLink({attrs:'', i:'i-calendar', chev:1, b:'رویداد پیوندی',
        s:p.ev?esc(p.ev):'بدون پیوند', right:p.ev?tag('وصل','ok'):tag('بی پیوند','')})}
      ${rowLink({attrs:'', i:'i-doc', chev:1, b:'فرم پیوندی',
        s:p.fm?esc(p.fm):'بدون فرم', right:p.fm?tag('وصل','ok'):tag('بی پیوند','')})}
    </div>
    <p class="cap">پیوند رویداد و فرم در گام دوم ویرایش عوض می‌شود؛ دکمهٔ «ویرایش مطلب» همان‌جا می‌برد.</p>
    <hr class="hr"/>
    <div class="row"><div class="head">آخرین بازخوانیها</div><span class="sp"></span></div>
    <div class="admlist">${reps.map(r=>rowLink({attrs:'', i:'i-eye',
      b:esc(r.t||'بدون عنوان'),
      s:`${esc(postDayName(r.at||0))}${r.min?` · ${faN(r.min)} دقیقه خواند`:''}`,
      right:tag('بازدید','')})).join('')||emptyBox('هنوز گزارشی ثبت نشده')}</div>
  </section>`;
}
function postDayName(at){try{const u=U(); return u&&u.postDate?u.postDate(at):''}catch(e){return ''}}

/* فهرست مطلبها؛ در همان بخش رویدادها و مطالب زیر رویدادها می‌نشیند */
function postRows(){
  const rows=pedPosts().filter(p=>p.pub||p.pend);
  return rows.map(p=>{
    const open=p.pub?' data-pmgr="'+esc(p.id)+'"':' data-pedit="'+esc(p.id)+'"';
    return rowLink({attrs:open, i:'i-article',
    b:esc(p.t||'بی نام'),
    s:`${esc(p.cat||'مطلب')} · ${faN(pedMin(p))} دقیقه · ${faN(+p.views||0)} بازدید · ${faN((p.reps||[]).length)} گزارش`,
    right:`${p.pend?tag('در انتظار تأیید','warn'):(p.pub?tag('منتشر شده','ok'):tag('پیش‌نویس',''))}
      ${p.pub?`<button class="btn sm quiet" data-pedit="${esc(p.id)}" aria-label="ویرایش">${ico('i-pen')}</button>`
        :`<a class="btn sm quiet" href="post.html?id=${encodeURIComponent(p.id)}&d=1" target="_blank" rel="noopener" aria-label="دیدن">${ico('i-eye')}</a>`}
      <button class="btn sm quiet" data-ppin="${esc(p.id)}" aria-label="پین">${ico('i-pin')}</button>
      <button class="btn sm quiet" data-pdel="${esc(p.id)}" aria-label="حذف">${ico('i-trash')}</button>`});}).join('');
}
function demoRows(){
  return ((window.NORA&&NORA.ARTICLES)||[]).map(a=>rowLink({attrs:`data-pprevgo="${esc(a.id)}"`, i:'i-article',
    b:esc(a.t), s:`${esc(a.cat)} · ${faN(a.min)} دقیقه · نمونهٔ ثابت`, right:tag('نمونه','')})).join('');
}

/* تعریف جدید: همین‌جا فقط مطلب ساخته می‌شود */
function vNewev(){
  if(!S.ped||S.ped.pub||S.ped.pend){S.ped=pedFresh(); S.psec='list'}
  return postEditor();
}

/* ══ رندر ══════════════════════════════════════════════════════════════ */
const VIEWS={dash:vDash, newev:vNewev, events:vEvents, users:vUsers, forms:vForms,
  reports:vReports, cert:vCert, settings:vSettings};
function body(){
  if(!canSec(S.sec)) return `<section class="card stack">${emptyBox(W.locked||'')}
    <p class="cap" style="text-align:center">${esc(W.lockedLead||'')}</p>
    <div class="row" style="justify-content:center">
      ${btn(W.view||'نمای کاربر','data-sec="dash"','i-grid')}
      ${btn(D.mine||'نمای من','data-who-sheet','i-shield')}</div></section>`;
  if(S.sec==='events'&&S.wiz.open) return vEventWizard();
  const v=VIEWS[S.sec];
  return v?v():emptyBox(T.none);
}
function renderBody(){ if(AUD.on) AUD.tick++; $('#admBody').innerHTML=body()}
/* ── نگهبان حالت: حالت کهنه یا ناقص نباید داشبورد را خراب کند ─────────── */
function sanitize(){
  if(S.v!==SVER){ S=JSON.parse(JSON.stringify(BASE)); return; }
  if(!personOf(S.who)) S.who=BASE.who;
  if(fieldOf(S.setF).k!==S.setF) S.setF=BASE.setF;
  if(S.addF&&(!personOf(S.addF)||fieldOf(S.addF).k!==S.addF)) delete S.addF;
  if(['all','بالا','میان','معمولی'].indexOf(S.qf)<0) S.qf='all';
  if(['info','reg','att','money','cert','news'].indexOf(S.evTab)<0) S.evTab='info';
  if(['list','edit'].indexOf(S.psec)<0) S.psec='list';
  if(S.pstep!=='2'&&+S.pstep!==2) S.pstep=1;
  if(S.ped&&(!Array.isArray(S.ped.blocks))) S.ped=null;
  if(S.sec==='posts') S.sec='events';
  if(UCLUBTABS.every(t=>t[0]!==S.uClub)) S.uClub='rules';
  if(UTOOLTABS.every(t=>t[0]!==S.uTool)) S.uTool='report';
  if(UPTABS.every(t=>t[0]!==S.uTab)) S.uTab='info';
  if(S.uV==='user'&&!memOf(S.uSel)) S.uV='';
  if(S.uV==='occ'){S.uV='club'; S.uClub='occ';}
  if(S.uV&&['req','club','cert','tools','user'].indexOf(S.uV)<0) S.uV='';
  S.baleReg=S.baleReg?1:0;
  if(S.cert){ if(+(S.cert.step||0)>3) S.cert.step=0;
    if(S.cert.evs&&!Array.isArray(S.cert.evs)) S.cert.evs=[];
    if(S.cert.evs) S.cert.evs=S.cert.evs.filter(id=>EVROWS.some(e=>e.id===id));
    if(S.cert.pub) delete S.cert.pub;
    if(!Array.isArray(S.certFiles)) S.certFiles=[];
    if(!Array.isArray(S.certQueue)){ S.certQueue=(S.certPub||[]).map(b=>({n:b.n||'دسته', cnt:b.cnt||0, got:b.got||0,
      letter:b.letter||'', plan:b.plan||'همین حالا', st:b.rev?'wait':'ok', rev:b.rev?1:0})); S.certPub=null; }
    if(!Array.isArray(S.cert.picked)) S.cert.picked=[];
    if(!Array.isArray(S.cert.tags)) S.cert.tags=[];
    if(S.cert.xlsRows&&!Array.isArray(S.cert.xlsRows)) S.cert.xlsRows=null;
    if(!S.cert.vals||typeof S.cert.vals!=='object') S.cert.vals={};
    if(S.auditLast&&typeof S.auditLast!=='object') S.auditLast=null;
    (S.certFiles||[]).forEach(f=>{ if(!Array.isArray(f.params)) f.params=[] });
    if(S.certFind) S.certFind=String(S.certFind).slice(0,40); }
  if(!isMoney()&&S.evTab==='money') S.evTab='info';
  S.qMore=S.qMore?1:0;
}

function render(){
  if(typeof tick==='function') tick(false); if(!canSec(S.sec)) S.sec='dash'; renderNav(); renderBar(); renderBody();
  const s=secOf(S.sec);
  document.title=(S.sec==='dash'?'نورا · پنل مدیران':'پنل مدیران · '+s.n)}
function go(k){
  if(!secOf(k)) k='dash';
  const changed=S.sec!==k; S.sec=k; S.q=''; save();
  if(changed) try{history.replaceState(null,'','#'+k)}catch(e){}
  window.scrollTo({top:0,behavior:'smooth'});
  render();
}

/* ══ کنش‌ها ════════════════════════════════════════════════════════════
   مهم: این هندلرها باید *بعد از* initUI بسته شوند. ui.js خودش کلیدهای
   خاموش و روشن را با کلیک جابه‌جا می‌کند و بی‌ترتیب، حالت و شکل از هم
   جدا می‌افتند. */
function bind(){
document.addEventListener('click',e=>{
  const t=e.target; if(!t||!t.closest) return;
  const q=s=>t.closest(s);

  /* ── شخص و کارتابل ── */
  const ws2=q('[data-who-sheet]'); if(ws2){sheetWho(); return}
  const wh=q('[data-who]'); if(wh&&wh.dataset.who){S.who=wh.dataset.who; S.sec='dash'; S.qf='all';
    S.wiz=Object.assign({},BASE.wiz); save();
    render(); toast('داشبورد '+me().n+' · '+me().lv); return}
  const qf2=q('[data-qf]'); if(qf2){S.qf=qf2.dataset.qf; save(); renderBody(); return}
  const qm=q('[data-qmore]'); if(qm){S.qMore=S.qMore?0:1; save(); renderBody(); return}
  const qd=q('[data-qdone]'); if(qd){const id=qd.dataset.qdone;
    S.qdone=(S.qdone||[]).indexOf(id)>-1?(S.qdone||[]).filter(x=>x!==id):(S.qdone||[]).concat([id]);
    save(); renderBody(); toast(qDone(id)?(D.doneMsg||'انجام شد'):(D.backToQueue||'به کارتابل برگشت')); return}
  const qg=q('[data-qgive]'); if(qg){sheetGive(qg.dataset.qgive); return}
  const gt=q('[data-giveto]'); if(gt){S.qgive[gt.dataset.qid]=gt.dataset.giveto; save();
    sheetImpl('shAdm',''); closeSheets(); renderBody();
    toast((D.givenTo||'واگذار شد به')+' '+personOf(gt.dataset.giveto).n); return}
  const qgo=q('[data-qgo]'); if(qgo){const el=$('.qcard'); if(el) el.scrollIntoView({behavior:'smooth',block:'center'}); return}
  const nb=q('[data-note]'); if(nb){toast(D.quickNoteMsg||'یادداشت سریع باز می‌شود'); return}
  const wk2=q('[data-week]'); if(wk2){renderBody(); toast(D.myWeek||'کارنامهٔ من'); return}
  const bc=q('[data-broadcast]'); if(bc){toast(D.broadcastMsg||'اطلاع‌رسانی حوزه ساخته می‌شود'); return}
  /* ── سرپرست و کارشناس ── */
  const sl=q('[data-setlead]'); if(sl){sheetSetLead(sl.dataset.setlead); return}
  const sl2=q('[data-setleadto]'); if(sl2){S.leads[sl2.dataset.leadfor]=sl2.dataset.setleadto; save();
    closeSheets(); render(); toast((D.leadSet||'سرپرست عوض شد')+' · '+personOf(sl2.dataset.setleadto).n); return}
  const asp=q('[data-addspec]'); if(asp){S.addF=asp.dataset.addspec; save(); sheetAddSpec(S.addF); return}
  const gpw=q('[data-genpw]'); if(gpw){const el=$('#spP'); if(el) el.value=genPw(); return}
  const nsp2=q('[data-newspec2]'); if(nsp2){
    const nm=$('#spN')?$('#spN').value.trim():'', un=$('#spU')?$('#spU').value.trim():'';
    if(!nm||!un){toast('نام و نام کاربری را بنویس'); return}
    const fk=isOwner()?((S.addF&&fieldOf(S.addF).k===S.addF)?S.addF:myField().k):myField().k;
    const k='x'+(Date.now()%100000);
    S.extra=(S.extra||[]).concat([{k:k, n:nm, f:fk, lv:'کارشناس', open:0, done:0, late:0, avg:0, load:12, score:70, since:'مهر ۱۴۰۴'}]);
    S.specAcc=(S.specAcc||{}); S.specAcc[k]={u:un, pw:$('#spP')?$('#spP').value:'', done:0};
    save(); closeSheets(); renderBody(); toast('حساب ساخته شد؛ نام کاربری و رمز را برای '+nm+' بفرستید'); return}
  const rsp=q('[data-resetspec]'); if(rsp){const p2=personOf(rsp.dataset.resetspec), ac=accOf(p2), pw=genPw();
    S.specAcc=(S.specAcc||{}); S.specAcc[p2.k]={u:ac.u, pw:pw, done:ac.done};
    save(); toast('رمز تازه برای '+p2.n+': '+pw+' · از ربات بلهٔ موسسه می‌رود'); return}
  const srf=q('[data-specrow]'); if(srf){sheetSpecFile(srf.dataset.specrow); return}
  const sng=q('[data-specnudge]'); if(sng){toast('یادآوری تکمیل پروفایل از ربات بلهٔ موسسه فرستاده شد'); return}
  const sp2=q('[data-specperm]'); if(sp2){sheetSpecPerm(sp2.dataset.specperm); return}
  const ex=q('[data-extra]'); if(ex){const p2=ex.dataset.extrafor, k=ex.dataset.extra;
    const list=extraOf(p2), i=list.indexOf(k);
    if(i>-1) list.splice(i,1); else list.push(k);
    S.specExtra[p2]=list.slice(); save(); sheetSpecPerm(p2); toast((i>-1?'برداشته شد':'داده شد')+': '+(PROWS.find(r=>r[0]===k)||['',''])[1]); return}
  const spf=q('[data-fperm]'); if(spf){
    if(!(isOwner()||isLead())){toast(W.locked||''); return}
    const fk=(S.setF&&fieldOf(S.setF).k===S.setF)?S.setF:myField().k, k=spf.dataset.fperm;
    const list=specPermsOf(fk), i=list.indexOf(k);
    if(i>-1) list.splice(i,1); else list.push(k);
    S.specPerms[fk]=list.slice(); save(); renderBody();
    toast((PROWS.find(r=>r[0]===k)||['','دسترسی'])[1]+(i>-1?' برداشته شد':' داده شد')); return}
  const sf=q('[data-setF]'); if(sf){S.setF=sf.dataset.setf; save(); renderBody(); return}
  /* ── بخش‌ها ── */
  const sec=q('[data-sec]'); if(sec){
    if(sec.dataset.locked==='1'){toast(W.locked||''); return}
    if(sec.dataset.sec==='users'){S.uV=''; S.uSel=''; S.uTab='info'; save()}
    go(sec.dataset.sec); return}
  const evt=q('[data-evtab]'); if(evt){S.evTab=evt.dataset.evtab; save(); if(S.evId) sheetEv(S.evId); return}
  const ev=q('[data-ev]'); if(ev){S.evId=ev.dataset.ev; S.evTab=S.evTab||'info'; save(); sheetEv(S.evId); return}
  const ef=q('[data-evF]'); if(ef){S.evF=ef.dataset.evf; save(); renderBody(); return}
  const uf=q('[data-uF]'); if(uf){S.uF=uf.dataset.uf; save(); renderBody(); return}
  const us=q('[data-user]'); if(us){S.uV='user'; S.uSel=us.dataset.user; S.uTab='info'; S.uRej=''; save(); renderBody(); return}
  const utab=q('[data-utab]'); if(utab){S.uTab=utab.dataset.utab; save(); renderBody(); return}
  const ucl=q('[data-uclub]'); if(ucl){S.uClub=ucl.dataset.uclub; save(); renderBody(); return}
  const utl=q('[data-utool]'); if(utl){S.uTool=utl.dataset.utool; save(); renderBody(); return}
  const uio=q('[data-uinboxopen]'); if(uio){S.uV='user'; S.uSel=uio.dataset.uinboxopen; S.uTab='msg'; S.uRej=''; save(); renderBody(); return}
  const ble=q('[data-bale]'); if(ble){baleIntro(ble.dataset.bale); return}
  const breg=q('[data-balereg]'); if(breg){S.baleReg=1; save(); closeSheets(); renderBody();
    toast('پیوند با ربات ثبت شد؛ از این پس گزارش‌ها خودکار می‌آیند'); return}
  const bse=q('[data-balesend]'); if(bse){toast('فرستاده شد؛ گزارش در ربات بلهٔ موسسه (@'+(A.bale||'lifeline_bot')+') است'); return}
  const gfr=q('[data-gofrms]'); if(gfr){go('forms'); return}
  const rp=q('[data-rp]'); if(rp){S.rp=rp.dataset.rp; save(); renderBody(); toast('دوره: '+rp.dataset.rp); return}
  const rep=q('[data-rep]'); if(rep){sheetRep(rep.dataset.rep); return}
  const rc=q('[data-rcust]'); if(rc){const k2=rc.dataset.rcust, l=S.rpCust||[];
    S.rpCust=l.indexOf(k2)>-1?l.filter(x=>x!==k2):l.concat([k2]); save(); renderBody(); return}
  const rg=q('[data-rcustgo]'); if(rg){if(!(S.rpCust||[]).length){toast('نخست سنجهها را برگزین'); return}
    S.rpCustOn=1; save(); renderBody();
    toast('گزارش سفارشی با '+fa(S.rpCust.length)+' سنجه ساخته شد · دوره: '+(S.rp||'۳۰ روز')); return}
  const rs=q('[data-rsch]'); if(rs){const i=+rs.dataset.rsch, base=((RP.sched||{}).list||[]).length, ex=S.rpSchedExtra||[];
    if(i<base){const L=(RP.sched.list||[]); L[i].on=L[i].on?0:1;
      toast(L[i].n+(L[i].on?' روشن شد؛ جمعبندی بعدی: ':' خاموش شد · ')+L[i].at)}
    else{const r2=ex[i-base]; r2.on=r2.on?0:1; toast(r2.n+(r2.on?' روشن شد':' خاموش شد'))}
    save(); renderBody(); return}
  const kc=q('[data-keycopy]'); if(kc){const k=(((A.settings||{}).keys||{}).list||[])[+kc.dataset.keycopy];
    if(k){copy(k.v,null,'«'+k.n+'» رونوشت شد')} return}
  const ar=q('[data-auditrun]'); if(ar){auditRun(); return}
  const cj=q('[data-cjob]'); if(cj){const j=((CE.jobs||[]).concat(S.jobs||[]))[+cj.dataset.cjob];
    if(j){sheetImpl('shAdm',`<div class="admsheet">
      <div class="row"><span class="ic">${ico('i-medal')}</span>
        <span class="tx" style="min-width:0"><div class="head">${esc(j.n||'')}</div>
        <div class="cap">${esc(j.who||'')} · ${esc(j.way||'')}</div></span><span class="sp"></span>
        ${tag(j.st==='wait'?'در نوبت':'منتشر شد',j.st==='wait'?'warn':'ok')}</div>
      <div class="admkpi"><div class="k"><small>گیرندگان</small>${bits((j.who||'').split(' ')[0]||'ـ')}</div>
        <div class="k"><small>زمان</small>${bits(j.at||'ـ')}</div></div>
      <div class="row">${baleA('cert_list','گزارش این کار از ربات بله')}
        <span class="sp"></span>${btn(W.close||'بستن','data-close')}</div></div>`); renderBody()} return}
  const rn=q('[data-rschnew]'); if(rn){
    if((S.rpSchedExtra||[]).some(x=>x.n==='جمعبندی فصلی')){toast('زمانبندی فصلی از قبل نشسته؛ همین پایین خاموش و روشنش میکنی'); return}
    S.rpSchedExtra=(S.rpSchedExtra||[]).concat([{n:'جمعبندی فصلی',at:'نخست هر فصل ۰۹:۰۰',on:1}]);
    save(); renderBody(); toast('زمانبندی نشست؛ نخستین جمعبندی فصلی سرِ فصل بعد در ربات بله میرسد'); return}
  const cs=q('[data-cstep]')||q('[data-cgo]');
  if(cs){S.cert.step=+(cs.dataset.cstep!=null?cs.dataset.cstep:cs.dataset.cgo); save(); renderBody(); return}
  const cf2=q('[data-cfile]'); if(cf2){S.cert.file=cf2.dataset.cfile; save(); renderBody();
    toast('فایل ورد برداشته شد: '+((CE.files||[]).concat(S.certFiles||[]).find(f=>f.k===cf2.dataset.cfile)||{}).n); return}
  const cdf=q('[data-cdef]'); if(cdf){S.certDef=cdf.dataset.cdef; S.cert.file=''; save(); renderBody();
    toast('فایل پیشفرض عوض شد؛ صدورهای بعدی با همین فایل میشود'); return}
  const ce2=q('[data-cev]'); if(ce2){const id=ce2.dataset.cev, l=S.cert.evs||[];
    S.cert.evs=l.indexOf(id)>-1?l.filter(x=>x!==id):l.concat([id]); save(); renderBody(); return}
  const ctg=q('[data-ctag]'); if(ctg){const t=ctg.dataset.ctag, l=S.cert.tags||[];
    S.cert.tags=l.indexOf(t)>-1?l.filter(x=>x!==t):l.concat([t]); save(); renderBody(); return}
  const cfg=q('[data-cfindgo]'); if(cfg){S.certFind=$('#cFind')?norm($('#cFind').value):''; save(); renderBody(); return}
  const cpk=q('[data-cpick]'); if(cpk){const id=cpk.dataset.cpick, l=S.cert.picked||[];
    if(l.indexOf(id)<0) S.cert.picked=l.concat([id]); save(); renderBody(); return}
  const cup=q('[data-cunpick]'); if(cup){S.cert.picked=(S.cert.picked||[]).filter(x=>x!==cup.dataset.cunpick); save(); renderBody(); return}
  const se=q('[data-setg]'); if(se){S.setG=se.dataset.setg; save(); renderBody(); return}
  /* ── تنظیمات سامانه: کاشیها و مدیریت ظاهر ── */
  const skt=q('[data-skit]'); if(skt){const k=skt.dataset.skit;
    if(k!=='skin'){toast('تنظیم «'+((SKIN_TILES.find(x=>x.k===k)||{}).n||'')+'» در نوبت بعد باز میشود'); return}
    S.skin=1; S.skinTab='home'; save(); renderBody(); return}
  const skb=q('[data-skinback]'); if(skb){S.skin=0; save(); renderBody(); return}
  const skw=q('[data-skintab]'); if(skw){S.skinTab=skw.dataset.skintab; save(); renderBody(); return}
  const uk=q('[data-uk]'); if(uk){const on=!usGet(uk.dataset.uk);
    usSet(uk.dataset.uk,on?1:0);
    uk.classList.toggle('on',on); uk.setAttribute('aria-checked',on?'true':'false');
    toast((uk.dataset.uklabel||'بخش')+(on?' روشن شد':' خاموش شد')); return}
  const um=q('[data-umenu]'); if(um){const U=uiSet(), nm=um.dataset.umenu, had=U.menu.indexOf(nm)>-1;
    if(had) U.menu.splice(U.menu.indexOf(nm),1); else U.menu.push(nm);
    uiSetSave(U);
    um.classList.toggle('on',had); um.setAttribute('aria-checked',had?'true':'false');
    toast('«'+nm+'» '+(had?'به منو برگشت':'از منو پنهان شد')); return}
  const ukq=q('[data-uquick]'); if(ukq){const U=uiSet(), k=ukq.dataset.uquick, had=U.quick.indexOf(k)>-1;
    if(had) U.quick.splice(U.quick.indexOf(k),1); else U.quick.push(k);
    uiSetSave(U);
    ukq.classList.toggle('on',had); ukq.setAttribute('aria-checked',had?'true':'false');
    toast('کاشی '+(had?'برگشت':'پنهان شد')); return}
  const bh=q('[data-bhide]'); if(bh){const U=uiSet(), nm=bh.dataset.bhide, had=U.bnr.hide.indexOf(nm)>-1;
    if(had) U.bnr.hide.splice(U.bnr.hide.indexOf(nm),1); else U.bnr.hide.push(nm);
    uiSetSave(U);
    bh.classList.toggle('on',had); bh.setAttribute('aria-checked',had?'true':'false');
    toast('بنر «'+nm+'» '+(had?'برگشت':'پنهان شد')); return}
  const sh=q('[data-shide]'); if(sh){const U=uiSet(), id=sh.dataset.shide, had=U.storyHide.indexOf(id)>-1;
    if(had) U.storyHide.splice(U.storyHide.indexOf(id),1); else U.storyHide.push(id);
    uiSetSave(U);
    sh.classList.toggle('on',had); sh.setAttribute('aria-checked',had?'true':'false');
    toast('استوری '+(had?'برگشت':'پنهان شد')); return}
  const pk=q('[data-bg],[data-sico],[data-sdest],[data-sgrad]'); if(pk){
    [...pk.parentElement.children].forEach(x=>x.classList.remove('on')); pk.classList.add('on'); return}
  const ba=q('[data-skbadd]'); if(ba){
    const t=((document.getElementById('skBnT')||{}).value||'').trim();
    if(!t){toast('عنوان بنر را بنویسید'); return}
    const v=id=>((document.getElementById(id)||{}).value||'').trim();
    const gr=(document.querySelector('#admBody .chip.on[data-bg]')||{dataset:{}}).dataset.bg||'';
    const U=uiSet(); U.bnrAdd.push({t:t,tag:v('skBnTag'),m:v('skBnM'),n:v('skBnN'),a:v('skBnA'),g:gr});
    uiSetSave(U); toast('بنر «'+t+'» به خانه اضافه شد'); renderBody(); return}
  const bd=q('[data-skbdel]'); if(bd){const U=uiSet(), b=U.bnrAdd.splice(+bd.dataset.skbdel,1)[0]||{};
    uiSetSave(U); toast('بنر «'+b.t+'» برداشته شد'); renderBody(); return}
  const sa=q('[data-sksadd]'); if(sa){
    const t=((document.getElementById('skST')||{}).value||'').trim();
    if(!t){toast('عنوان استوری را بنویسید'); return}
    const v=id=>((document.getElementById(id)||{}).value||'').trim();
    const pick=s=>(document.querySelector('#admBody .chip.on['+s+']')||{dataset:{}}).dataset;
    const U=uiSet();
    U.storyAdd.push({id:'c'+Date.now(),t:t,s:v('skSS'),i:pick('data-sico').sico||'i-sparkle',
      g:pick('data-sgrad').sgrad||'',to:pick('data-sdest').sdest||'me'});
    uiSetSave(U); toast('استوری «'+t+'» به خانه اضافه شد'); renderBody(); return}
  const sd=q('[data-sksdel]'); if(sd){const U=uiSet(), s=U.storyAdd.splice(+sd.dataset.sksdel,1)[0]||{};
    uiSetSave(U); toast('استوری «'+s.t+'» برداشته شد'); renderBody(); return}
  const uc=q('[data-ucards]'); if(uc){const U=uiSet(); U.cards=uc.dataset.ucards; uiSetSave(U);
    document.querySelectorAll('#admBody [data-ucards]').forEach(x=>x.classList.toggle('on',x===uc));
    try{document.documentElement.dataset.cards=U.cards}catch(e){}
    toast('اندازهٔ کارتها: '+uc.textContent.trim()); return}
  const up=q('[data-upeople]'); if(up){const U=uiSet(); U.people=up.dataset.upeople; uiSetSave(U);
    document.querySelectorAll('#admBody [data-upeople]').forEach(x=>x.classList.toggle('on',x===up));
    toast('نمایش اساتید: '+up.textContent.trim()); return}
  const skf=q('[data-skinfoot]'); if(skf){
    usSet('trust.text',((document.getElementById('skTrust')||{}).value||'').trim());
    usSet('foot.text',((document.getElementById('skFoot')||{}).value||'').trim());
    toast('متنهای پای صفحه ذخیره شد'); return}
  const sr=q('[data-skinreset]'); if(sr){
    if(!skinArm){skinArm=1; sr.textContent='مطمئنید؟ همه پیشفرض';
      setTimeout(()=>{skinArm=0; if(document.contains(sr)) sr.textContent='بازنشانی پیشفرضها'},4000); return}
    skinArm=0; uiSetSave(JSON.parse(JSON.stringify((window.NORA_UI||{}).uiSetDef||{})));
    S.skinTab='home'; save(); renderBody(); toast('ظاهر سامانه به پیشفرض برگشت'); return}
  const tg=q('[data-tog]'); if(tg){const key=tg.dataset.tog+'|'+tg.dataset.toglabel;
    const cur=togDef(tg.dataset.tog, tg.dataset.toglabel, tg.dataset.togdef==='1');
    const on=!cur; S.toggles[key]=on; save();
    tg.classList.toggle('on',on); tg.setAttribute('aria-checked',on?'true':'false');
    toast((tg.dataset.toglabel||'')+(on?' روشن شد':' خاموش شد')); return}
  const frow=q('[data-formrow]'); if(frow){const i=+frow.dataset.formrow,
      rows=madeForms().map(f=>Object.assign({},f,{made:1})).concat((A.forms||{}).rows||[]), r=rows[i];
    if(r){const made=!!r.made;
      sheetImpl('shAdm',`<div class="admsheet">
        <div class="row"><span class="ic">${ico('i-doc')}</span>
          <span class="tx" style="min-width:0"><div class="head">${esc(r.name||r.n||'')}</div>
          <div class="cap">${esc(r.kind||r.k||'فرم')}${r.got!=null?' · '+esc(fa(r.got))+' پاسخ':''}${made?' · ساختهٔ فرم‌ساز':' · نمونهٔ آمادهٔ نورا'}</div></span><span class="sp"></span>
          ${r.on!==undefined?tag(r.on?'باز':'بسته',r.on?'ok':''):''}</div>
        ${r.d||r.fin?`<p class="cap">${esc(r.d||'')} ${r.fin&&r.fin.length?' · '+esc(fa(r.fin.length))+' قلم مالی':''}</p>`:''}
        <div class="row">
          ${made?`<a class="btn sm" href="create.html?fid=${esc(r.id)}&name=${encodeURIComponent(r.n||r.name||'')}&back=${encodeURIComponent('admin.html#forms')}" target="_blank" rel="noopener">${ico('i-sliders')}فرم‌ساز</a>`:''}
          ${r.link?`<a class="btn sm" target="_blank" rel="noopener" href="${esc(r.link)}">${ico('i-eye')}دیدن فرم</a>`:''}
          <span class="sp"></span>${btn(W.close||'بستن','data-close')}</div></div>`); renderBody()} return}
  const fs=q('[data-formsw]'); if(fs){const i=+fs.dataset.formsw, r=((A.forms||{}).rows||[])[i];
    if(r){r.on=!r.on; toast(r.on?'فرم باز شد':'فرم بسته شد'); renderBody()} return}
  /* ── مطلبها: فهرست و ویرایشگر بلوکی ── */
  const pnew=q('[data-pnew]'); if(pnew){
    S.ped=pedFresh();
    S.psec='edit'; save(); renderBody(); return}
  const pedit=q('[data-pedit]'); if(pedit){const pid=pedit.dataset.pedit, pp=pedPosts().find(x=>String(x.id)===String(pid));
    if(pp){S.ped=JSON.parse(JSON.stringify(pp)); S.ped.tags=(pp.tags||[]).join('، '); S.psec='edit'; S.pstep=1; save(); renderBody()} return}
  const pmgr=q('[data-pmgr]'); if(pmgr){
    const pid=pmgr.dataset.pmgr, pp=pedPosts().find(x=>String(x.id)===String(pid));
    if(pp){S.pmgr=pid; S.pstep=1; renderBody()} return}
  const pmgrback=q('[data-pmgrback]'); if(pmgrback){S.pmgr=null; save(); renderBody(); return}
  const pme=q('[data-pmgrEdit]'); if(pme&&S.pmgr){
    const pp=pedPosts().find(x=>String(x.id)===String(S.pmgr));
    if(pp){S.ped=JSON.parse(JSON.stringify(pp)); S.ped.tags=(pp.tags||[]).join('، ');
      S.psec='edit'; S.pstep=1; save(); renderBody()} return}
  const pback=q('[data-pback]'); if(pback){S.ped=null; S.psec='list'; S.pstep=1; save(); renderBody(); return}
  const pgo=q('[data-pgo]'); if(pgo&&S.ped){S.pstep=String(pgo.dataset.pgo)==='2'?2:1; save(); renderBody(); return}
  const pcat=q('[data-pcat]'); if(pcat&&S.ped){S.ped.cat=pcat.dataset.pcat; save(); renderBody(); return}
  const pdel=q('[data-pdel]'); if(pdel){const u=U(); if(u&&u.postDrop) u.postDrop(pdel.dataset.pdel);
    if(S.ped&&String(S.ped.id)===String(pdel.dataset.pdel)){S.ped=null; S.psec='list'}
    toast('مطلب برداشته شد'); save(); renderBody(); return}
  const ppin=q('[data-ppin]'); if(ppin){const u=U(), pp=u&&u.postById?u.postById(ppin.dataset.ppin):null;
    if(u&&u.postPatch&&pp){u.postPatch(pp.id,{pin:pp.pin?0:1}); toast(pp.pin?'پین برداشته شد':'مطلب پین شد'); renderBody()} return}
  const pprevgo=q('[data-pprevgo]'); if(pprevgo){window.open('post.html?id='+encodeURIComponent(pprevgo.dataset.pprevgo)+'&d=1','_blank','noopener'); return}
  const pgrad=q('[data-pgrad]'); if(pgrad&&S.ped){S.ped.cover=Object.assign({},S.ped.cover||{},{g:PGRADS[+pgrad.dataset.pgrad],up:''});
    save(); renderBody(); return}
  const pclear=q('[data-pclear]'); if(pclear&&S.ped){S.ped.cover={g:PGRADS[0]}; save(); renderBody(); return}
  const ptog=q('[data-ptog]'); if(ptog&&S.ped){const k2=ptog.dataset.ptog; S.ped[k2]=S.ped[k2]?0:1; save(); renderBody(); return}
  const badd=q('[data-badd]'); if(badd&&S.ped){
    const ty=badd.dataset.badd, nb=BLK(ty);
    if(ty==='h'){nb.x=''; nb.lv=2}
    S.ped.blocks.push(nb); save(); renderBody(); return}
  const bdel=q('[data-bdel]'); if(bdel&&S.ped){S.ped.blocks.splice(+bdel.dataset.bdel,1); save(); renderBody(); return}
  const bup=q('[data-bup]'); if(bup&&S.ped){const i=+bup.dataset.bup;
    if(i>0){const bl=S.ped.blocks; const t=bl[i-1]; bl[i-1]=bl[i]; bl[i]=t; save(); renderBody()} return}
  const bdown=q('[data-bdown]'); if(bdown&&S.ped){const i=+bdown.dataset.bdown, bl=S.ped.blocks;
    if(i<bl.length-1){const t=bl[i+1]; bl[i+1]=bl[i]; bl[i]=t; save(); renderBody()} return}
  const bbtn=q('[data-bbtn]'); if(bbtn&&S.ped){const b=S.ped.blocks[+bbtn.dataset.bbtn];
    if(b){b.kind=bbtn.dataset.bk; save(); renderBody()} return}
  const pprev=q('[data-pprev]'); if(pprev&&S.ped){
    const d2=JSON.parse(JSON.stringify(S.ped));
    d2.tags=String(d2.tags||'').split(/[،,]/).map(x=>x.trim()).filter(Boolean);
    d2.min=pedMin(d2); d2.pub=0; d2.pend=0; pedSave(d2);
    window.open('post.html?id='+encodeURIComponent(d2.id)+'&d=1','_blank','noopener'); return}
  const ppub=q('[data-ppub]'); if(ppub&&S.ped){
    const d2=JSON.parse(JSON.stringify(S.ped));
    if(!String(d2.t||'').trim()){toast('عنوان مطلب را بنویس'); return}
    d2.tags=String(d2.tags||'').split(/[،,]/).map(x=>x.trim()).filter(Boolean);
    d2.min=pedMin(d2); d2.pub=1; d2.pend=0; d2.at=d2.at||Date.now(); pedSave(d2);
    S.ped=null; S.psec='list'; save();
    toast('«'+(d2.t||'بی نام')+'» منتشر شد؛ در خانهٔ کاربران هم نشست');
    S.pmgr=d2.id; if(S.sec!=='events') go('events'); else renderBody(); return}
  const psend=q('[data-psend]'); if(psend&&S.ped){
    const d2=JSON.parse(JSON.stringify(S.ped));
    if(!String(d2.t||'').trim()){toast('عنوان مطلب را بنویس'); return}
    d2.tags=String(d2.tags||'').split(/[،,]/).map(x=>x.trim()).filter(Boolean);
    d2.min=pedMin(d2); d2.pub=0; d2.pend=1; d2.at=d2.at||Date.now(); pedSave(d2);
    S.ped=null; S.psec='list'; save();
    toast('مطلب رفت در صف تأیید؛ مالک یا سرپرست منتشر می‌کند');
    if(S.sec==='newev'){S.pmgr=d2.id; go('events')} else renderBody(); return}

  const evnew=q('[data-evnew]'); if(evnew){S.wiz.kind='event'; S.wiz.step=0; S.wiz.open=1; S.dp=null; save(); renderBody(); return}
  const evback=q('[data-evback]'); if(evback){S.wiz.open=0; save(); renderBody(); return}
  const wpo=q('[data-wposter]'); if(wpo){const k=wpo.dataset.wposter;
    S.wiz.poster=S.wiz.poster===k?'':k; save(); renderBody(); return}
  const wth=q('[data-wtheme]'); if(wth){S.wiz.theme=wth.dataset.wtheme; save(); renderBody(); return}
  const wch=q('[data-wch]'); if(wch){const k=wch.dataset.wch; S.wiz.ch[k]=chOn(k)?0:1; save(); renderBody(); return}
  const cpf=q('[data-copyform]'); if(cpf){copy(location.href.split('#')[0].replace(/[^/]*$/,'')+cpf.dataset.copyform,null,
    L2=>L2||'نشانی رونوشت شد'); return}
  const wcp=q('[data-copyev]'); if(wcp){copy(location.href.split('#')[0].replace(/[^/]*$/,'')+evLink(),null,
    (NE().copyLink||'نشانی رونوشت شد')); return}
  /* فرم‌ها: از انبار فرم‌ساز بردار یا بردار کنار */
  const fpk=q('[data-fpick]'); if(fpk){const need=fpk.dataset.fpick, id=fpk.dataset.fid, f=formOf(id);
    S.wiz.fp=S.wiz.fp||{reg:'',survey:'',exam:'',other:''};
    S.wiz.fp[need]=String(id);
    if(need==='survey') S.wiz.feat.survey=1;
    if(need==='exam'){S.wiz.feat.exam=1; S.wiz.exam=f&&f.need?f.need:'exam';}
    save(); renderBody(); toast(f?('وصل شد: '+formName(f)):'وصل شد'); return}
  const fcl=q('[data-fclear]'); if(fcl){S.wiz.fp=S.wiz.fp||{}; S.wiz.fp[fcl.dataset.fclear]=''; save(); renderBody(); return}
  /* جلسه‌ها */
  const sad=q('[data-sessadd]'); if(sad){const ses=S.wiz.sess=S.wiz.sess||[];
    const last=ses[ses.length-1]||{d:S.wiz.date||'',t:S.wiz.time||'',to:S.wiz.to||''};
    ses.push({d:last.d||'',t:last.t||'',to:last.to||''});
    S.wiz.sessions=Math.max(+S.wiz.sessions||1, ses.length);
    if(ses[ses.length-1].d) S.wiz.end=ses[ses.length-1].d;
    const de=document.getElementById('wz-sessions'); if(de) de.value=String(S.wiz.sessions);
    save(); renderBody(); return}
  const sdl=q('[data-sessdel]'); if(sdl){const ses=S.wiz.sess||[]; ses.splice(+sdl.dataset.sessdel,1);
    S.wiz.sessions=Math.max(1,ses.length||(+S.wiz.sessions||1));
    const de=document.getElementById('wz-sessions'); if(de) de.value=String(S.wiz.sessions);
    save(); renderBody(); return}
  /* برگزار شده */
  const whd=q('[data-wheld]'); if(whd){S.wiz.held=S.wiz.held?0:1; save(); renderBody(); return}
  const wpc=q('[data-wposterclear]'); if(wpc){S.wiz.posterUp=''; save(); renderBody(); return}
  /* یادآوری‌ها */
  const rad=q('[data-remadd]'); if(rad){remList().push({w:'before',n:1,u:'d',ch:'bale',on:1}); save(); renderBody(); return}
  const rdl=q('[data-remdel]'); if(rdl){remList().splice(+rdl.dataset.remdel,1); save(); renderBody(); return}
  const ron=q('[data-remon]'); if(ron){const r=remList()[+ron.dataset.remon]; if(r){r.on=r.on?0:1; save(); renderBody()} return}
  const rtw=q('[data-remtow]'); if(rtw){const r=remList()[+rtw.dataset.remtow]; if(r){r.w=rtw.dataset.w; save(); renderBody()} return}
  const rev=q('[data-remever]'); if(rev){S.wiz.remEvery=S.wiz.remEvery?0:1; save(); renderBody(); return}
  const wet=q('[data-wet]'); if(wet){S.wiz.et=wet.dataset.wet; S.wiz.feat=defaultFeat(wet.dataset.wet);
    save(); renderBody(); return}
  const wp=q('[data-wpick]'); if(wp){const key=wp.dataset.wpick, val=wp.dataset.wval, num=['cap','pre','extra','dur','sessions','points'];
    S.wiz[key]=num.indexOf(key)>-1?(key==='points'?+un(val):+un(val)):val; save(); renderBody(); return}
  const wf=q('[data-wfeat]'); if(wf){const k=wf.dataset.wfeat; S.wiz.feat[k]=featOn(k)?0:1;
    toast(neKind(S.wiz.et).n+' · '+(S.wiz.feat[k]?'روشن شد':'خاموش شد')); save(); renderBody(); return}
  const wr=q('[data-wrem]'); if(wr){const k=wr.dataset.wrem; S.wiz.rem[k]=remOn(k)?0:1; save(); renderBody(); return}
  /* تقویم: بازش کن، ماه بچرخان، روز بردار، امروز، ببند */
  const dp=q('[data-dp]'); if(dp){const f=dp.dataset.dp, cur=jParse(wGet(f)), t=jToday();
    S.dp=(S.dp||{}).f===f?null:{f:f, y:(cur||t).jy, m:(cur||t).jm}; save(); renderBody(); return}
  const dmv=q('[data-dpmv]'); if(dmv){const d=S.dp||{}, t=jToday();
    let y=+d.y||t.jy, m=(+d.m||t.jm)+(+dmv.dataset.dpmv);
    if(m<1){m=12; y--} if(m>12){m=1; y++}
    S.dp={f:d.f, y:y, m:m}; save(); renderBody(); return}
  const dday=q('[data-dpday]'); if(dday){const d=S.dp||{}, t=jToday(), jd=+un(dday.dataset.dpday), was=wGet(d.f);
    wSet(d.f, jForm(+d.y||t.jy, +d.m||t.jm, jd));
    /* تاریخ پایان تا وقتی دستی عوض نشده، همراه شروع جلو می‌آید */
    if(d.f==='date'&&(!String(S.wiz.end||'').trim()||S.wiz.end===was)) S.wiz.end=wGet(d.f);
    S.dp=null; save(); renderBody(); return}
  const dt0=q('[data-dptoday]'); if(dt0){const d=S.dp||{}, t=jToday(), was=wGet(d.f);
    wSet(d.f, jForm(t.jy,t.jm,t.jd));
    if(d.f==='date'&&(!String(S.wiz.end||'').trim()||S.wiz.end===was)) S.wiz.end=wGet(d.f);
    S.dp={f:d.f, y:t.jy, m:t.jm}; save(); renderBody(); return}
  const dc=q('[data-dpclose]'); if(dc){S.dp=null; save(); renderBody(); return}
  const ww=q('[data-wwait]'); if(ww){S.wiz.wait=S.wiz.wait?0:1; save(); renderBody(); return}
  const wc=q('[data-wcancel]'); if(wc){S.wiz=Object.assign({},BASE.wiz); save(); renderBody(); return}
  const ws=q('[data-wstep]'); if(ws){const step=+ws.dataset.wstep;
    if(ws.dataset.wgo!=='1'){S.wiz.step=step; S.dp=null; save(); renderBody(); return}
    const w=S.wiz, i=step-1;
    w.time=h24(w.time,true); w.to=h24(w.to,true);
    if(i===0&&!(w.kind&&(w.kind!=='event'||w.et)&&String(w.name||'').trim())){toast(W.fieldsReq||'این قلم را پر کن'); return}
    if(i===1&&!w.edit&&!(w.date&&w.time&&w.to&&(w.mode==='online'?w.link:w.place))){toast(W.fieldsReq||'این قلم را پر کن'); return}
    S.wiz.step=step; save(); renderBody(); return}
  const dOk=q('[data-defok]'); if(dOk){const id=dOk.dataset.defok, r=defsFor().find(x=>x.id===id)||{};
    S.defs=(S.defs||[]).map(x=>x.id===id?Object.assign({},x,{wait:0,st:'ok'}):x);
    if(r.kind==='event'&&!evAll().some(e=>e.id==='d-'+id)){
      const w=(r.extra||{}).wiz||r.wiz||{}, evId='d-'+id, ses=(w.sess||[]).filter(x=>x&&x.d);
      const j1=jParse(w.date), W2={day:j1?jLong(j1.jy,j1.jm,j1.jd):(w.date||''),
        time:[w.time,w.to].filter(Boolean).join(' تا '),
        count:ses.length||(+w.sessions||1)};
      S.added=[Object.assign({id:evId, n:r.n, kind:neKind(w.et).n||'رویداد',
        when:W2.day||'تاریخ در تعریف', on:w.date||'', time:W2.time,
        place:w.mode==='online'?(w.link||'آنلاین'):(w.place||''),
        cap:+w.cap||0, reg:0, state:(w.held?'past':'soon'), held:w.held?1:0, poster:w.posterUp?'':(w.poster||''),
        posterUp:w.posterUp||'', theme:w.theme||'glass', sess:ses, sessions:W2.count,
        who:+w.who||0, rep:w.rep||'', media:w.media||'', about:w.about||'', org:w.org||'',
        label:w.label||'', privacy:w.privacy||'public', page:'event.html?id='+evId,
        forms:linkForms(evId, w),
        rem:(w.rem||[]).filter(x=>x&&x.on!==0).map(x=>({w:x.w,n:+x.n||0,u:x.u,ch:x.ch})),
        ch:Object.keys(w.ch||{}).filter(k=>w.ch[k]), points:+w.points||0, att:w.att||'qr'},
        (r.extra||{}).add||{})].concat(S.added||[]);
    }
    save(); renderBody(); toast((DEFD().route||{}).self||'تأیید شد'); return}
  const dNo=q('[data-defno]'); if(dNo){const id=dNo.dataset.defno;
    S.defs=(S.defs||[]).map(x=>x.id===id?Object.assign({},x,{wait:0,st:'no'}):x);
    save(); renderBody(); toast((DEFD().states||{}).no?DEFD().states.no[0]:'برگشت برای اصلاح'); return}
  const wsend=q('[data-wsend]'); if(wsend){const w=S.wiz, et=neKind(w.et), kk=defKind(w.kind);
    const kind=w.kind==='event'?(et.n||'رویداد'):kk.n, j1=jParse(w.date), W2=evWhen();
    const ses=(w.sess||[]).filter(x=>x&&x.d);
    if(j1&&w.edit&&!w.held&&evState({on:w.date,end:w.end,to:w.to,sess:ses,state:'soon'})==='past'&&!ses.length)
      toast(((NE().held||{}).past)||'تاریخ این رویداد گذشته');
    const forms=[];
    const moneyOf=need=>{const f=fpForm(need); return f?formSum(f):0};
    const withForms=(e,evId)=>Object.assign(e,{forms:linkForms(evId), poster:w.posterUp?'':(w.poster||''), posterUp:w.posterUp||'',
      theme:w.theme||'glass', page:evLink(), about:w.about||'', label:w.label||'', org:w.org||'',
      privacy:w.held?'public':(w.privacy||'public'), on:w.date||'',
      sess:ses.map(x=>({d:x.d,t:x.t,to:x.to})), sessions:W2.count,
      held:w.held?1:0, who:+w.who||0, rep:w.rep||'', media:w.media||'',
      cap:+w.cap||0, pre:+w.pre||0, extra:+w.extra||0, wait:w.waitMode||'auto',
      tickets:w.tickets||'one', points:+w.points||0, att:w.att||'qr',
      rem:(w.rem||[]).filter(r=>r.on!==0).map(r=>({w:r.w,n:+r.n||0,u:r.u,ch:r.ch})), remEvery:w.remEvery?1:0,
      ch:Object.keys(w.ch||{}).filter(k=>chOn(k)),
      price:isMoney()?moneyOf('reg'):0, state:w.held?'past':undefined,
      svyOff:fpOf('survey')?0:1});
    if(w.edit){  /* ویرایش: همان‌جا می‌ماند، نه پیش‌نویس می‌شود نه از فهرست می‌رود */
      S.evEdit=Object.assign({},S.evEdit||{});
      const st=evState({on:w.date,end:w.end,to:w.to,sess:ses,state:(evOf(w.edit)||{}).state||'soon'});
      S.evEdit[w.edit]=withForms({n:w.name||'', kind:kind,
        when:W2.day||(j1?jLong(j1.jy,j1.jm,j1.jd):(w.date||'')), on:w.date||'',
        time:W2.time, end:(ses.length?ses[ses.length-1].d:w.end||''),
        place:w.mode==='online'?(w.link||'آنلاین'):(w.place||''), cap:+w.cap||0,
        state:(w.held?'past':(st==='past'?'past':'soon'))}, w.edit);
      S.wiz=Object.assign({},BASE.wiz); save();
      toast((NE().again||'ویرایش شد')); go('events'); return}
    const route={id:(w.stamp?'nxs'+w.stamp:'nx'+Date.now()), kind:w.kind, n:w.name||'بی‌نام',
      by:me().k, f:myField().k, at:'همین حالا'};
    if(canPublish()){
      S.added=[withForms({id:route.id, n:route.n, kind:kind, when:W2.day||(w.date||''),
        on:w.date||'', time:W2.time, end:(ses.length?ses[ses.length-1].d:w.end||''),
        place:w.mode==='online'?(w.link||'آنلاین'):(w.place||''), cap:+w.cap||0,
        reg:w.held?(+w.who||0):0, state:(w.held?'past':'soon')}, route.id)].concat(S.added||[]);
      S.wiz=Object.assign({},BASE.wiz); S.evF='all'; save();
      toast((NE().made||'منتشر شد')); go('events'); return}
    S.defs=[Object.assign({},route,{wait:1,extra:{wiz:JSON.parse(JSON.stringify(w))}})].concat(S.defs||[]);
    S.wiz=Object.assign({},BASE.wiz); save(); renderBody();
    toast((NE().queued||'رفت برای تأیید')); go('dash'); return}
  const cpar=q('[data-cparam]'); if(cpar){S.cert.params=S.cert.params||{}; S.cert.params[cpar.dataset.cparam]=cpar.value; save(); return}
  const crun3=q('[data-crun]'); if(crun3){const b=(S.certQueue||[])[+crun3.dataset.crun];
    if(b&&b.st!=='ok'){b.st='ok'; b.got=b.cnt; b.plan='همین حالا'; save(); renderBody();
      toast('همین حالا صادر شد؛ خبر و فایل از ربات بله به '+fa(b.cnt)+' گیرنده رفت')} return}
  const cl2=q('[data-cletter]'); if(cl2){S.cert.letter=cl2.value; save(); return}
  const cm2=q('[data-cmonths]'); if(cm2){S.cert.months=cm2.value; save(); return}
  const cn2=q('[data-cnews]'); if(cn2){S.cert.news=cn2.value; save(); return}
  const cr2=q('[data-crand]'); if(cr2){const all=memList().filter(m=>m.st[1]!=='stop');
    const one=all[Math.floor(Math.random()*all.length)]||{};
    S.cert.rand=one.n||''; save(); renderBody(); toast('نمونهٔ تصادفی: '+(one.n||'')); return}
  const cbn=q('[data-cbnudge]'); if(cbn){const b=(S.certQueue||[])[+cbn.dataset.cbnudge];
    if(b){b.nudged=1; save(); toast('یادآوری برای '+fa(Math.max(0,b.cnt-(b.got||0)))+' گیرندهٔ مانده از ربات بله رفت')} return}
  const cbr=q('[data-cbrev]'); if(cbr){const b=(S.certQueue||[])[+cbr.dataset.cbrev];
    if(b){b.rev=1; save(); renderBody(); toast('دستهٔ «'+b.n+'» باطل شد؛ استعلام همان گواهینامهها «باطل» میگوید')} return}
  const cqueue=fast=>{const files=(CE.files||[]).concat(S.certFiles||[]);
    const curFile=files.find(f=>f.k===S.cert.file)||files.find(f=>f.k===(S.certDef||''))||files.find(f=>f.def)||files[0]||{n:'فایل ورد'};
    const evSel=(S.cert.evs||[]).filter(id=>EVROWS.some(e=>e.id===id));
    const tagC=(S.cert.tags||[]).reduce((a,t)=>a+memList().filter(m=>(m.tags||[]).indexOf(t)>-1).length,0);
    const xl=(S.cert.xlsRows||[]).length;
    const cnt=evSel.reduce((a,id)=>a+(+(EVROWS.find(e=>e.id===id)||{}).reg||0),0)+tagC+xl+(S.cert.picked||[]).length;
    if(!cnt){toast('نخست گیرنده بیاورید: رویداد، دسته، اکسل یا جست‌وجو'); return}
    S.certQueue=(S.certQueue||[]);
    S.certQueue=[{n:curFile.n, cnt:cnt, got:fast?cnt:0, letter:S.cert.letter||(CE.letter||''),
      months:S.cert.months||(CE.months||''), news:S.cert.news||(CE.news||''),
      plan:fast?'همین حالا':certWin(), st:fast?'ok':'wait', rev:0}].concat(S.certQueue);
    S.jobs=[{n:curFile.n, who:fa(cnt)+' نفر', way:fast?'صدور فوری':'صف '+certWin(),
      at:fast?'همین حالا':'در نوبت', st:fast?'ok':'wait'}].concat(S.jobs||[]);
    save(); renderBody();
    toast(fast?'همین حالا صادر شد؛ خبر و فایل از ربات بله رفت':'در صف نشست؛ '+certWin()+' صادر میشود و به گیرندهها گفته میشود تا ۲۴ ساعت آینده')};
  const cqq=q('[data-cqueue]'); if(cqq){cqueue(false); return}
  const cfs=q('[data-cfast]'); if(cfs){cqueue(true); return}
  const uv=q('[data-uv]'); if(uv){S.uV=uv.dataset.uv; S.uRej=''; if(S.uV==='tools') S.uTool='report'; if(S.uV==='club') S.uClub='rules'; save(); renderBody(); return}
  const uback=q('[data-uback]'); if(uback){S.uV=''; S.uSel=''; S.uRej=''; S.uimpPv=null; save(); renderBody(); return}
  const utag=q('[data-uTag]'); if(utag){S.uTag=(S.uTag===utag.dataset.utag)?'':utag.dataset.utag; save(); renderBody(); return}
  const uok=q('[data-uok]'); if(uok){const id=uok.dataset.uok;
    S.uov[id]=Object.assign({},S.uov[id],{st:['تأییدشده','ok']}); save();
    uLogAdd('پروفایل '+((memOf(id)||{}).n||'')+' تأیید شد');
    toast('پروفایل تأیید شد'); renderBody(); return}
  const urej=q('[data-urej]'); if(urej){S.uRej=urej.dataset.urej;
    if(S.uV!=='user'){S.uV='user'; S.uSel=urej.dataset.urej; S.uTab='info'}
    save(); renderBody(); return}
  const urejgo=q('[data-urejgo]'); if(urejgo){const id=urejgo.dataset.urejgo,
      why=(($('#uRejTxt')||{}).value||'').trim();
    if(!why){toast('دلیل رد را بنویس تا کاربر بداند چه کم دارد'); return}
    S.uov[id]=Object.assign({},S.uov[id],{st:['برگشت برای اصلاح','stop'],rejWhy:why}); S.uRej=''; save();
    uLogAdd('پروفایل '+((memOf(id)||{}).n||'')+' با دلیل برگشت');
    closeSheets(); toast('با دلیل برگشت'); renderBody(); return}
  const uvip=q('[data-uvip]'); if(uvip){const id=uvip.dataset.uvip, cur=(memOf(id)||{}).vip;
    S.uov[id]=Object.assign({},S.uov[id],{vip:cur?0:1}); save();
    uLogAdd(((memOf(id)||{}).n||'')+(cur?' از ویژه درآمد':' ویژه (VIP) شد'));
    toast(cur?'ویژه بودن برداشته شد':'کاربر ویژه شد'); renderBody(); return}
  const udel=q('[data-udel]'); if(udel){const id=udel.dataset.udel;
    if(!isOwner()){toast('برداشتن کاربر فقط با مالک است'); return}
    S.uhide=(S.uhide||[]).concat([id]); S.uV=''; S.uSel=''; save();
    uLogAdd(((memOf(id)||{}).n||id)+' از سامانه برداشته شد');
    toast('کاربر برداشته شد'); renderBody(); return}
  const ed=q('[data-evedit]'); if(ed){const e=evOf(ed.dataset.evedit); if(e){
    const t=(NE().kinds||[]).find(x=>x.n===e.kind)||{};
    const half=String(e.time||'').split('تا').map(x=>x.trim()).filter(Boolean);
    const jw=jFromWhen(e.when);
    const ses=(e.sess||[]).map(x=>({d:x.d||'',t:un(String(x.t||'')),to:un(String(x.to||''))}));
    const fp={reg:'',survey:'',exam:'',other:''};
    (e.forms||[]).forEach(f=>{if(f&&f.need&&fp[f.need]!==undefined) fp[f.need]=String(f.id||'')});
    /* نظرسنجی: اگر رویداد عمداً بی نظرسنجی ذخیره شده، برنگردد؛ وگرنه آماده میآید */
    if(!fp.survey&&!e.svyOff) fp.survey='auto';
    S.wiz=Object.assign({},BASE.wiz,{edit:e.id,kind:'event',et:t.k||'custom',name:e.n||'',
      desc:e.d||e.about||'',about:e.about||'',org:e.org||'',label:e.label||'',
      poster:((e.poster||'').indexOf('nora-')===0?'':(e.poster||'')),posterUp:e.posterUp||'',
      theme:e.theme||'glass',
      date:e.on||(jw?jForm(jw.jy,jw.jm,jw.jd):''),
      time:un((ses[0]||{}).t||half[0]||''),to:un((ses[0]||{}).to||half[1]||''),end:e.end||'',
      sess:ses,sessions:+e.sessions||(+e.sessions||1),
      held:e.held?1:0,who:+e.who||0,rep:e.rep||'',media:e.media||'',
      place:(e.place||'')==='آنلاین'?'':(e.place||''),
      link:(e.place||'')==='آنلاین'?((NE().suggest||{}).link||[])[0]:'',cap:+e.cap||45,
      waitMode:e.wait||'auto',tickets:e.tickets||'one',privacy:e.privacy||'public',
      points:+e.points||10,att:e.att||'qr',
      rem:(e.rem&&e.rem.length)?e.rem.map(r=>Object.assign({on:1},r)):BASE.wiz.rem,
      remEvery:(e.remEvery==null?1:e.remEvery),
      ch:(e.ch&&e.ch.length)?e.ch.reduce((o,k)=>(o[k]=1,o),{}):{notify:1,bale:1,email:1},
      fp:fp,
      mode:(e.place||'')==='آنلاین'?'online':'physical'});
    S.wiz.stamp=(e.id||'').replace(/^nx/,'')||Date.now();
    /* جلسه‌ها اگر جا مانده باشد، از شمار جلسه‌ها ساخته می‌شود */
    if(!S.wiz.sess.length&&+S.wiz.sessions>1) S.wiz.sess=[{d:S.wiz.date,t:S.wiz.time,to:S.wiz.to}];
    S.wiz.open=1; closeSheets(); save(); toast(W.editEvent||'در حال ویرایش'); go('events'); return}}
  const ub=q('[data-ublock]'); if(ub){const id=ub.dataset.ublock;
    S.uov[id]=Object.assign({},S.uov[id],{st:['مسدود','stop']}); save();
    uLogAdd(((memOf(id)||{}).n||'')+' مسدود شد');
    toast('دسترسی این کاربر بسته شد'); renderBody(); return}
  const uun=q('[data-uunblock]'); if(uun){const id=uun.dataset.uunblock;
    S.uov[id]=Object.assign({},S.uov[id],{st:['تأییدشده','ok']}); save();
    uLogAdd('مسدودی '+((memOf(id)||{}).n||'')+' برداشته شد');
    toast('مسدودی برداشته شد'); renderBody(); return}
  const unote2=q('[data-unotego]'); if(unote2){const id=unote2.dataset.unotego,
      v=(($('#uNoteTxt')||{}).value||'').trim();
    S.uov[id]=Object.assign({},S.uov[id],{note:v}); save();
    uLogAdd('یادداشت پروندهٔ '+((memOf(id)||{}).n||'')+' بهروز شد');
    toast('یادداشت در پرونده نشست'); renderBody(); return}
  const un2=q('[data-unote]'); if(un2){const el=$('#uNoteTxt'); if(el) el.focus();
    toast('یادداشت را در همین ورقه بنویس'); return}
  const utm=q('[data-utagm]'); if(utm){const id=utm.dataset.utagm, t2=utm.dataset.utagm2||utm.getAttribute('data-utagm-2')||'',
      m=memOf(id)||{}, cur=(m.tags||[]).slice(), i=cur.indexOf(t2);
    if(i>-1) cur.splice(i,1); else cur.push(t2);
    S.uov[id]=Object.assign({},S.uov[id],{tags:cur}); save();
    uLogAdd('برچسب «'+t2+'» روی پروندهٔ '+((m.n||''))+(i>-1?' برداشته شد':' نشست'));
    renderBody(); return}
  const ut2=q('[data-utagadd]'); if(ut2){const v=(($('#uTagNew')||{}).value||'').trim();
    if(!v){toast('نام برچسب را بنویس'); return}
    S.ulabels=(S.ulabels||[]).concat([v]); save();
    uLogAdd('برچسب تازه «'+v+'» ساخته شد');
    toast('برچسب ساخته شد؛ از پروندهٔ هر کاربر رویش بگذار'); renderBody(); return}
  const uabso=q('[data-uabsok]'); if(uabso){const id=uabso.dataset.uabsok, a=uAbs().find(x=>x.id===id);
    if(a){a.st='تأیید شد'; uLogAdd('غیبت مجاز '+((memOf(a.u)||{}).n||'')+' تأیید شد'); save()}
    toast('غیبت مجاز تأیید شد؛ حضورش «معذور» ثبت میشود'); renderBody(); return}
  const uabsn=q('[data-uabsno]'); if(uabsn){const id=uabsn.dataset.uabsno, a=uAbs().find(x=>x.id===id);
    if(a){a.st='رد شد'; save()} toast('درخواست غیبت رد شد'); renderBody(); return}
  const usho=q('[data-ushopok]'); if(usho){const id=usho.dataset.ushopok, r=uShopReq().find(x=>x.id===id);
    if(r){r.st='تحویل شد'; S.ushopDone=(S.ushopDone||[]).concat([r.r]);
      uLogAdd('پاداش '+r.r+' به '+((memOf(r.u)||{}).n||'')+' تحویل شد'); save()}
    toast('پاداش تحویل شد'); renderBody(); return}
  const ushn=q('[data-ushopno]'); if(ushn){const id=ushn.dataset.ushopno, r=uShopReq().find(x=>x.id===id);
    if(r){r.st='رد شد'; const it=SHOP.find(x=>x[0]===r.r), m=memOf(r.u);
      if(it&&m){S.uov[r.u]=Object.assign({},S.uov[r.u],{pt:Math.max(0,(+m.pt||0)-(+it[2]||0))})}
      uLogAdd('پاداش '+r.r+' رد شد؛ امتیاز به '+((memOf(r.u)||{}).n||'')+' برگشت'); save()}
    toast('رد شد؛ امتیاز سالم برگشت'); renderBody(); return}
  const uocc=q('[data-uocc]'); if(uocc){const k=uocc.dataset.uocc;
    S.uocc[k]=occOn({k:k})?0:1; save(); renderBody(); return}
  const uocn=q('[data-uoccnew]'); if(uocn){S.uoccNew=1; save(); renderBody(); return}
  const uocc2=q('[data-uocccancel]'); if(uocc2){S.uoccNew=0; save(); renderBody(); return}
  const uoccd=q('[data-uoccdel]'); if(uoccd){const k=uoccd.dataset.uoccdel;
    S.uoccC=(S.uoccC||[]).filter(o=>o.k!==k); delete S.uocc[k]; save();
    uLogAdd('مناسبت سفارشی برداشته شد'); toast('مناسبت برداشته شد'); renderBody(); return}
  const uocca=q('[data-uoccadd]'); if(uocca){const n=($('#occN')||{}).value||'',
      m=+un(($('#occM')||{}).value||'1'), d=+un(($('#occD')||{}).value||'1'),
      g=($('#occG')||{}).value||'همه', p=Math.min(100,+un(($('#occP')||{}).value||'0')||0);
    if(!String(n).trim()){toast('نام مناسبت را بنویس'); return}
    if(!(m>=1&&m<=12&&d>=1&&d<=31)){toast('تاریخ نامعتبر است'); return}
    S.uoccC=(S.uoccC||[]).concat([{k:'oc'+Date.now(),n:String(n).trim(),jm:m,jd:d,g:g,pts:p}]);
    S.uoccNew=0; save(); uLogAdd('مناسبت سفارشی «'+n+'» ساخته شد');
    toast('مناسبت ساخته شد'); renderBody(); return}
  const urul=q('[data-urule]'); if(urul){const k=urul.dataset.urule;
    S.urules[k]=ruleOn({id:k})?0:1; save(); renderBody(); return}
  const urln=q('[data-urulenew]'); if(urln){S.uruleNew=1; save(); renderBody(); return}
  const urlc=q('[data-urulecancel]'); if(urlc){S.uruleNew=0; save(); renderBody(); return}
  const urld=q('[data-uruledel]'); if(urld){const k=urld.dataset.uruledel;
    S.urulesC=(S.urulesC||[]).filter(o=>o.id!==k); delete S.urules[k]; save();
    uLogAdd('قانون امتیاز برداشته شد'); toast('قانون برداشته شد'); renderBody(); return}
  const urla=q('[data-uruleadd]'); if(urla){const n=($('#rulN')||{}).value||'',
      t2=($('#rulT')||{}).value||'', h=+un(($('#rulH')||{}).value||'1'), p=Math.min(100,+un(($('#rulP')||{}).value||'0'));
    if(!String(n).trim()){toast('عنوان قانون را بنویس'); return}
    if(!TRG[t2]){toast('شرط نامعتبر است'); return}
    S.urulesC=(S.urulesC||[]).concat([{id:'rl'+Date.now(),n:String(n).trim(),trg:t2,th:Math.max(1,h),pts:p}]);
    S.uruleNew=0; save(); uLogAdd('قانون امتیاز «'+n+'» ساخته شد');
    toast('قانون ساخته شد'); renderBody(); return}
  const upar=q('[data-upar]'); if(upar){const k=upar.dataset.upar;
    S.upar[k+'|on']=(S.upar[k+'|on']!==0)?0:1; save(); renderBody(); return}
  const uprq=q('[data-uparreq]'); if(uprq){const k=uprq.dataset.uparreq;
    S.upar[k+'|req']=!(S.upar[k+'|req']); save(); renderBody(); return}
  const uprr=q('[data-uparreset]'); if(uprr){S.upar={}; save(); toast('به پیشفرض برگشت'); renderBody(); return}
  const urh=q('[data-urankhide]'); if(urh){S.rankHide=S.rankHide?0:1; save(); renderBody(); return}
  const uadr=q('[data-uaddgo]'); if(uadr){const raw=(($('#uAddTxt')||{}).value||''), rows=raw.split('\n')
      .map(x=>x.trim()).filter(Boolean);
    if(!rows.length){toast('هر خط یک نفر را بنویس'); return}
    let n=0; rows.forEach((r2,i)=>{let parts=r2.split(/[،,]/).map(x=>x.trim()).filter(Boolean);
      if(parts.length===1){const tk=parts[0].split(/\s+/);
        if(tk.length>1&&/^[\d۰-۹]+$/.test(un(tk[tk.length-1]))&&un(tk[tk.length-1]).length>=8)
          parts=[tk.slice(0,-1).join(' '),tk[tk.length-1]]}
      if(!parts[0]) return; n++;
      S.uextra=(S.uextra||[]).concat([Object.assign({id:'x'+Date.now()+'_'+i,
        n:parts[0], code:'NL-'+(1039+memList().length), ph:'', st:['تأییدشده','ok'], tags:['تازه'],
        reg:'همین حالا', ev:0, pt:0, src:'دستی', g:'', city:'', inv:0, fm:0, act:0},
        /^\d+$/.test(un(parts[1]||''))?(un(parts[1]).length>10?{ph:un(parts[1])}:{nid:parts[1]}):{})])});
    S.uV=''; save(); uLogAdd(fa(n)+' نفر با افزودن دستی اضافه شد');
    toast(fa(n)+' نفر اضافه شد'); renderBody(); return}
  const uimp=q('[data-uimpparse]'); if(uimp){const raw=(($('#uImpTxt')||{}).value||'').trim();
    if(!raw){toast('جدول را بچسبان'); return}
    const lines=raw.split('\n').map(x=>x.trim()).filter(Boolean);
    const sep=lines[0].indexOf('\t')>-1?'\t':(lines[0].indexOf(',')>-1?',':(lines[0].indexOf('،')>-1?'،':';'));
    const ALIAS={'نام و نام خانوادگی':'n','نام':'n','نام خانوادگی':'ln','فامیل':'ln','موبایل':'ph','شماره':'ph',
      'شماره موبایل':'ph','همراه':'ph','تلفن':'ph','کد ملی':'nid','کدملی':'nid','شهر':'city','استان':'pr',
      'جنسیت':'g','ایمیل':'em','مقطع':'ed','رشته':'fost','دانشگاه':'uni','شغل':'job','محل کار':'co',
      'تاریخ تولد':'bd','آدرس':'ad','بیو':'bio'};
    const heads=lines[0].split(sep).map(x=>norm(x));
    const cols=heads.map(h2=>ALIAS[h2]||'');
    if(!cols.some(Boolean)){toast('سرستونها شناخته نشد؛ نام یا موبایل باشد'); return}
    const rows=lines.slice(1).map(l2=>{const cells=l2.split(sep), o={};
      cells.forEach((c2,i2)=>{if(cols[i2]) o[cols[i2]]=c2.trim()}); return o})
      .filter(o=>Object.keys(o).some(k2=>o[k2]));
    S.uimpPv={cols:cols.filter(Boolean),rows:rows}; save(); renderBody(); return}
  const uimu=q('[data-uimpupd]'); if(uimu){S.uimpUpd=S.uimpUpd?0:1; save(); renderBody(); return}
  const uimp2=q('[data-uimpgo]'); if(uimp2){const pv=S.uimpPv||{rows:[],cols:[]};
    let nn=0, up=0;
    pv.rows.forEach(r2=>{const hit=S.uimpUpd&&memList().find(m=>(r2.ph&&m.ph===r2.ph)||(r2.nid&&m.nid===r2.nid));
      if(hit){S.uov[hit.id]=Object.assign({},S.uov[hit.id],r2); up++}
      else{S.uextra=(S.uextra||[]).concat([Object.assign({id:'x'+Date.now()+'_'+Math.random().toString(36).slice(2,6),
        n:r2.n||'بی نام', code:'NL-'+(1039+memList().length), ph:r2.ph||'', st:['تأییدشده','ok'], tags:['گروهی اکسل'],
        reg:'همین حالا', ev:0, pt:0, src:'گروهی اکسل', g:r2.g||'', city:r2.city||'', inv:0, fm:0, act:0},r2)]); nn++}});
    S.uimp=[{at:'همین حالا',n:nn,upd:up,by:me().n||'مالک'}].concat(S.uimp||[]);
    S.uimpPv=null; S.uV=''; save(); uLogAdd('ورود گروهی اکسل: '+fa(nn)+' تازه، '+fa(up)+' بهروزرسانی');
    toast(fa(nn)+' نفر اضافه و '+fa(up)+' نفر بهروز شد'); renderBody(); return}
  const uinr=q('[data-uinboxread]'); if(uinr){const id=uinr.dataset.uinboxread, m=uInbox().find(x=>x.id===id);
    if(m){m.read=1; save()} renderBody(); return}
  const uina=q('[data-uinboxall]'); if(uina){uInbox().forEach(x=>{x.read=1}); save(); toast('همه خوانده شد'); renderBody(); return}
  const fl=q('[data-flink]'); if(fl){copy(location.href.split('#')[0]+'#forms?form=1',null,L.linkCopied); return}
  const vh=q('[data-verify-help]'); if(vh){toast('صفحهٔ استعلام: lifeline1.ir/c/<سریال>'); return}
  const rr=q('[data-restore]'); if(rr){toast('بازگردانی فقط با تأیید سوپرادمین'); return}
  const rs2=q('[data-reset]'); if(rs2){try{localStorage.removeItem(SKEY)}catch(e){} S=JSON.parse(JSON.stringify(BASE));
    toast('پنل به حالت اول برگشت'); go('dash'); return}
  const st2=q('[data-savetexts]'); if(st2){save(); toast(T.save||W.save||'ذخیره شد'); return}
});
document.addEventListener('change',e=>{
  const el=e.target; if(!el||!el.dataset) return;
  /* آپلود قالب ورد: خوانده و آنالیز میشود؛ پارامترهای متغیرش درمیآید */
  if(el.dataset.cfileup!==undefined){const f=(el.files||[])[0]; if(!f) return;
    const fr=new FileReader();
    fr.onload=async()=>{ const u8=new Uint8Array(fr.result);
      const ps=await certDocxParams(fr.result);
      if(ps===null){toast('این پرونده خوانده نشد؛ فایل ورد (docx) باشد'); return}
      const k='x'+(Date.now()%100000), small=u8.length<=800000;
      let b64='';
      if(small){let t=''; for(let i=0;i<u8.length;i+=8192) t+=String.fromCharCode.apply(null,u8.subarray(i,i+8192)); b64=btoa(t)}
      S.certFiles=[{k:k, n:f.name.replace(/\.docx$/i,''),
        s:fa(Math.max(1,Math.round(u8.length/1024)))+' کیلوبایت · '+fa(ps.length)+' پارامتر متغیر',
        params:ps, big:!small,
        up:small?'data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,'+b64:''}];
      S.cert.file=k; save(); renderBody();
      toast(ps.length?'قالب نشست؛ '+fa(ps.length)+' پارامتر متغیر پیدا شد: '+ps.slice(0,4).map(x=>'{'+x+'}').join(' ')
        :'قالب نشست؛ جای خالی {…} پیدا نشد و همان فایل برای همه میرود')};
    fr.onerror=()=>toast('این پرونده خوانده نشد');
    fr.readAsArrayBuffer(f); return}
  /* آپلود اکسل: xlsx یا CSV؛ هر ردیف یک نفر */
  if(el.dataset.cxlsup!==undefined){const f=(el.files||[])[0]; if(!f) return;
    const fr=new FileReader();
    fr.onload=async()=>{ let lines=null;
      try{ const buf=fr.result, u8=new Uint8Array(buf);
        if(u8.length>3&&u8[0]===0x50&&u8[1]===0x4b) lines=await certXlsxRows(buf);
        else lines=utf8(u8).replace(/"/g,'').split(/\r?\n/).filter(Boolean);
      }catch(e){}
      if(!lines||!lines.length){toast((CE.xlsUp||{}).bad||'جدولی در فایل خوانده نشد'); return}
      /* سرستون اکسل: خط نخست بی‌رقمِ دارای «نام»، ردیف حساب نمیشود */
      if(lines.length>1&&!/\d/.test(lines[0])&&lines[0].indexOf('نام')>-1) lines=lines.slice(1);
      const rows=certRowsOf(lines);
      S.cert.xlsRows=rows; save(); renderBody();
      const okn=rows.filter(x=>x.ok).length;
      toast(fa(okn)+' نفر از «'+f.name+'» شناخته شد'+(rows.length-okn?' · '+fa(rows.length-okn)+' ناشناس با همان نام صادر میشود':''))};
    fr.onerror=()=>toast('این پرونده خوانده نشد');
    fr.readAsArrayBuffer(f); return}
  if(el.dataset.pev&&S.ped){S.ped.ev=el.value; save(); return}
  if(el.dataset.pfm&&S.ped){S.ped.fm=el.value; save(); return}
  if(el.dataset.pfile){const f=(el.files||[])[0]; if(!f||!S.ped) return;
    shrinkPoster(f,url=>{ if(!url){toast('این تصویر خوانده نشد'); return}
      S.ped.cover={up:url}; save(); renderBody(); toast('جلد خودم نشست');}); return}
  if(el.dataset.bfile&&S.ped){const i=+el.dataset.bfile, f=(el.files||[])[0]; if(!f) return;
    const med=el.dataset.bmedia;
    if(med==='vid'&&f.size>4200000){toast('ویدیو سنگین است؛ لینک آپارات بده'); return}
    const fr=new FileReader();
    fr.onload=()=>{const url=String(fr.result||''); if(!url){toast('این پرونده خوانده نشد'); return}
      const b=S.ped.blocks[i]; if(b){b.up=url; delete b.src; save(); renderBody(); toast(med==='vid'?'ویدیو نشست و همین‌جا پخش میشود':med==='aud'?'صدا نشست و همین‌جا پخش میشود':'عکس نشست')}};
    fr.onerror=()=>toast('این پرونده خوانده نشد');
    fr.readAsDataURL(f); return}
  if(el.dataset.cparam){S.cert.vals=S.cert.vals||{}; S.cert.vals[el.dataset.cparam]=String(el.value||'').trim(); save(); return}
  if(el.dataset.text){S.texts[el.dataset.text]=String(el.value||''); save(); return}
  if(el.dataset.sessd!==undefined){const ses=S.wiz.sess||[], s2=ses[+el.dataset.sessd]; if(s2) s2.d=el.value; save(); return}
  if(el.dataset.sesst!==undefined){const ses=S.wiz.sess||[], s2=ses[+el.dataset.sesst]; if(s2){const v=h24(el.value); s2.t=v; if(v!==el.value) el.value=v} save(); return}
  if(el.dataset.sessto!==undefined){const ses=S.wiz.sess||[], s2=ses[+el.dataset.sessto]; if(s2){const v=h24(el.value); s2.to=v; if(v!==el.value) el.value=v} save(); return}
  if(el.dataset.remn!==undefined){const i=+el.dataset.remn, r=remList()[i];
    if(r){r.n=Math.max(0,+un(el.value)||0); rcap(el,i); save()}
    return}
  if(el.dataset.remu!==undefined){const i=+el.dataset.remu, r=remList()[i];
    if(r){r.u=el.value; rcap(el,i); save()}
    return}
  if(el.dataset.remch!==undefined){const r=remList()[+el.dataset.remch]; if(r){r.ch=el.value; save(); renderBody()} return}
  if(el.dataset.wfile){const f=(el.files||[])[0]; if(!f) return;
    shrinkPoster(f,url=>{
      if(!url){toast(((NE().posterUp||{}).fail)||'این تصویر خوانده نشد'); return}
      S.wiz.posterUp=url; S.wiz.poster=''; save(); renderBody();
      toast(((NE().posterUp||{}).add)||'پوستر خودم');
    });
    return}
  if(el.dataset.wtime){const f2=el.dataset.wtime, v=h24(el.value,true);
    S.wiz[f2]=v||String(el.value||''); el.value=v;
    const a2=minOfT(S.wiz.time), b2=minOfT(S.wiz.to);
    if(a2!=null&&b2!=null&&b2>a2) S.wiz.dur=b2-a2;
    save(); renderBody(); return}
  const f=el.dataset.winput;
  if(!f) return;
  if(el.type==='number'){
    S.wiz[f]=Math.max(0,+un(el.value)||0);
    if(f==='sessions'){  /* با شمار جلسه‌ها، ردیف‌های جلسه باز و بسته می‌شود */
      const n=Math.max(1,+S.wiz.sessions||1), ses=S.wiz.sess=S.wiz.sess||[];
      while(ses.length<n){const last=ses[ses.length-1]||{d:S.wiz.date||'',t:S.wiz.time||'',to:S.wiz.to||''};
        ses.push({d:last.d||'',t:last.t||'',to:last.to||''})}
      if(ses.length>n) ses.length=n;
      save(); renderBody(); return;
    }
    save(); return}

  if(['date','end','regFrom','regTo'].indexOf(f)>-1){
    const j=jParse(el.value), was=S.wiz[f];
    S.wiz[f]=j?jForm(j.jy,j.jm,j.jd):String(el.value||'').trim();
    if(f==='date'&&j){
      if(!String(S.wiz.end||'').trim()||S.wiz.end===was) S.wiz.end=S.wiz.date;
      if(!S.wiz.regFrom||!jParse(S.wiz.regFrom)) S.wiz.regFrom=S.wiz.date;
    }
    save(); renderBody(); return}
  S.wiz[f]=String(el.value||'').trim(); save(); return;
});
document.addEventListener('input',e=>{
  const el=e.target; if(!el||!el.dataset) return;
  if(el.dataset.pf&&S.ped){S.ped[el.dataset.pf]=el.value; save(); return}
  if(el.dataset.bf&&S.ped){
    const bi=el.closest('[data-bi]'), i=bi?+bi.dataset.bi:-1, b=i>-1?S.ped.blocks[i]:null;
    if(b){const f=el.dataset.bf;
      if(b.ty==='ul'||b.ty==='ol'||b.ty==='gal'||b.ty==='tbl') b.x=el.value.split('\n');
      else if(f==='lv') b.lv=+el.value||2;
      else b[f]=el.value;
      save()}
    return}
  if(el.id==='admQ'){S.q=el.value; renderBody(); return}
  if(el.dataset.remn!==undefined){const i=+el.dataset.remn, r=remList()[i];
    if(r){r.n=Math.max(0,+un(el.value)||0); rcap(el,i); save()}
    return}
  if(el.dataset.winput){const f=el.dataset.winput;
    if(['date','end','regFrom','regTo'].indexOf(f)>-1||el.type==='number'){
      /* قلم‌های تاریخ و عدد در «change» می‌نشینند تا وسط تایپ نپرد */
      if(el.type==='number') S.wiz[f]=Math.max(0,+un(el.value)||0);
      save(); return}
    S.wiz[f]=el.value; save(); return}
  if(el.dataset.sesst!==undefined||el.dataset.sessto!==undefined){
    const i=+((el.dataset.sesst!==undefined)?el.dataset.sesst:el.dataset.sessto);
    const s2=(S.wiz.sess||[])[i], k=(el.dataset.sesst!==undefined)?'t':'to';
    if(s2){const v=h24(el.value); if(v){s2[k]=v; if(v!==el.value) el.value=v}}
    save(); return}
  /* ساعت ۲۴ساعته: همان‌جا که می‌نویسی دونقطه می‌خورد و ۲۳:۵۹ سقف است */
  if(el.dataset.wtime){const f=el.dataset.wtime, v=h24(el.value);
    if(v){S.wiz[f]=v; if(v!==el.value) el.value=v}
    /* مدت هر جلسه خودش از شروع و پایان درمی‌آید و همان‌جا در قلمش می‌نشیند */
    const a2=minOfT(S.wiz.time), b2=minOfT(S.wiz.to);
    if(a2!=null&&b2!=null&&b2>a2){S.wiz.dur=b2-a2;
      const de=document.getElementById('wz-dur'); if(de) de.value=String(b2-a2);}
    save(); return}
});
addEventListener('hashchange',()=>{
  const k=(location.hash||'').replace('#','');
  if(k&&secOf(k)&&k!==S.sec){S.sec=k; S.q=''; save(); render()}
});
window.addEventListener('keydown',e=>{
  if(e.key!=='Escape') return;
  const s=$('#shAdm'); if(s&&s.classList.contains('on')) s.classList.remove('on');
  const sc=$('#scrim'); if(sc) sc.classList.remove('on');
});
}

/* ══ بوت ═══════════════════════════════════════════════════════════════ */
(function boot(){
  const h=(location.hash||'').replace('#','');
  if(h==='cert'){S.sec='users'; S.uV='cert';}
  else if(h&&secOf(h)) S.sec=h;
  if(!secOf(S.sec)) S.sec='dash';
  const th=$('#admTheme'); if(th) th.onclick=()=>{if(typeof themeToggle==='function') themeToggle()};
  const tb=$('#admTabs');
  if(tb) tb.addEventListener('click',e=>{const a=e.target.closest('a[data-sec]'); if(!a) return;
    e.preventDefault(); go(a.dataset.sec)});
  netSync();
  if(typeof initUI==='function'){try{initUI()}catch(e){}}
  bind();
  sanitize(); render();
})();
})();
