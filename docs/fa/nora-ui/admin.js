/* ══════════════════════════════════════════════════════════════════════════
   نورا، پنل مدیران
   ──────────────────────────────────────────────────────────────────────────
   یک صفحه، هفت بخش، به‌علاوهٔ داشبورد:
     داشبورد · رویداد جدید (ویزارد سه‌گامی) · رویدادها · کاربران · فرم‌ها ·
     گزارش‌ها (نه گزارش) · گواهینامه (مرکز صدور) · تنظیمات
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
const toast=UI.toast||(m=>{});
const copy=UI.copyText||(()=>{});
const tag=(b,k)=>b?`<span class="tag ${k||''}">${esc(b)}</span>`:'';
const btn=(label,attrs,i)=>`<button class="btn sm" ${attrs||''}>${i?ico(i):''}${esc(label)}</button>`;

/* ── واژه‌های کوتاه پنل: یک‌جا، تا عوض کردنشان یک نقطه داشته باشد ─────── */
const L={users:'فهرست کاربران', formTasks:'کارهای فرم‌ها', keys:'کلیدها',
  linkCopied:'لینک فرم رونوشت شد', sampleEvent:'کارگاه رویدادنگاری', roleSwitch:'عوض کردن نقش من',
  askCert:'استعلام گواهی',
  roleAll:'سوپرادمین همهٔ دسترسی‌ها را دارد؛ این فهرست بسته و دست‌نخورده می‌ماند.',
  roleEdit:'تیک‌ها را بزن و بردار؛ همان لحظه روی دسترسی همین نقش اثر می‌کند.',
  roleView:'دیدن دسترسی‌ها با نقش تو باز است؛ عوض کردنش با سوپرادمین است.'};

/* ── وضعیت پنل ─────────────────────────────────────────────────────────── */
const SKEY='nora-admin';
const SVER=48;
const BASE={v:SVER, sec:'dash', q:'', qMore:0, evF:'all', evId:null, evTab:'info', uF:'all',
  who:'p1', qf:'all', qdone:[], qextra:[], qgive:{}, leads:{}, specPerms:{}, specExtra:{}, extra:[], setF:'edu',
  wiz:{step:0,kind:'event',et:'',name:'',desc:'',org:'',mode:'physical',date:'',time:'',to:'',
    dur:90,sessions:1,place:'',link:'',privacy:'public',regFrom:'',regTo:'',cap:45,pre:6,extra:4,
    wait:1,feat:{},form:'light',exam:'none',att:'qr',rem:{d1:1,h1:1,after:1},points:10,edit:''},
  defs:[], evEdit:{},
  cert:{step:0,tpl:'t1',kind:'per',params:{},who:'ev',whoVal:'',pub:'notify'},
  setG:'texts', toggles:{}, texts:{}, jobs:[], added:[], uov:{}, rp:''};
let S=JSON.parse(JSON.stringify(BASE));
try{
  const v=JSON.parse(localStorage.getItem(SKEY)||'null');
  if(v&&typeof v==='object'){
    S=Object.assign(S,v);
    S.wiz=Object.assign({},BASE.wiz,v.wiz||{});
    S.cert=Object.assign({},BASE.cert,v.cert||{});
    ['jobs','added','qdone','qextra','extra','defs'].forEach(k=>{if(!Array.isArray(S[k])) S[k]=[]});
    ['qgive','leads','specPerms','specExtra'].forEach(k=>{if(!S[k]||typeof S[k]!=='object') S[k]={}});
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
  const o=(S.uov||{})[id]; return o?Object.assign({},m,o):m};
const memList=()=>MEM.map(m=>memOf(m.id));
const UF=[{k:'all',n:'همه'},{k:'pending',n:'در صف تأیید'},{k:'club',n:'عضو باشگاه'},{k:'blocked',n:'مسدود'}];
const ufCount=k=>({all:MEM.length, pending:memList().filter(m=>m.st[1]==='warn').length,
  club:memList().filter(m=>m.tags.indexOf('عضو باشگاه')>-1).length,
  blocked:memList().filter(m=>m.st[1]==='stop').length}[k]);

/* ── رویدادها ──────────────────────────────────────────────────────────── */
const EV=A.events||{}, EVROWS=EV.rows||[];
/* ویرایش آزاد است و وضعیت را عوض نمی‌کند: هر رویداد می‌تواند روکش ویرایش داشته باشد */
const evAll=()=>{const ov=S.evEdit||{};
  return (S.added||[]).concat(EVROWS).map(e=>ov[e.id]?Object.assign({},e,ov[e.id]):e);};
const evOf=id=>evAll().find(e=>e.id===id)||null;
const fN=n=>fa(Number(n).toLocaleString?Number(n).toLocaleString('en-US'):n);
/* عدد و یکا: رقم درشت می‌ماند و واژهٔ یکا ریز و کم‌رنگ کنارش می‌نشیند تا هیچ
   عددی درشت و بی‌توضیح نماند و در تنگی جا هم شکسته شود، نه سرریز */
const bits=v=>{const t=String(v==null?'':v).trim(), i=t.search(/\s/);
  return i<0?`<b>${esc(t)}</b>`:`<b>${esc(t.slice(0,i))} <small class="ku">${esc(t.slice(i+1))}</small></b>`;};
const evFilter=f=>f==='live'?e=>e.state==='live' : f==='soon'?e=>e.state==='soon'
  : f==='past'?e=>e.state==='past' : ()=>true;

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
function rowLink(o){  /* یک ردیف کاری: آیکون، دو خط متن، برچسب و فلش */
  return `<button class="admrow2" ${o.attrs||''}>
    <span class="ic">${ico(o.i||'i-doc')}</span>
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
const TABS=[{k:'dash',n:'داشبورد'},{k:'events',n:'رویدادها'},{k:'users',n:'کاربران'},
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

/* ── تعریف تازه: هر کس، هر بخش؛ مالک یا سرپرست تأیید می‌کند ──────────────
   رویداد چهار گام دارد و بعدش یا منتشر می‌شود یا می‌رود در فهرست تأیید.
   هیچ تعریفی پیش‌نویس نمی‌ماند و ویرایش هم چیزی را از فهرست برنمی‌دارد. */
const DEFD=()=>A.defs||{};
const NE=()=>A.newev||{};
const defKind=k=>(DEFD().kinds||[]).find(x=>x.k===k)||{n:'تعریف',i:'i-plus'};
const neKind=k=>(NE().kinds||[]).find(x=>x.k===k)||{n:'',i:'i-calendar'};
const wizSteps=()=>S.wiz.kind==='event'?(NE().steps||[]):['چیستی','مرور و فرستادن'];
/* هر قالب رویداد قابلیت‌هایش را با خودش می‌آورد و بقیه قلم‌ها آزاد می‌ماند */
function defaultFeat(k){
  const t=neKind(k), f={};
  ['ticket','att','cert'].forEach(x=>{if(t[x])f[x]=1});
  f.profile=1;
  return f;
}
const featOn=k=>!!(S.wiz.feat||{})[k];
const remOn=k=>!!(S.wiz.rem||{})[k];
/* چه کسی خودش منتشر می‌کند: مالک همه‌چیز، سرپرست حوزهٔ خودش */
const canPublish=()=>isOwner()||isLead();
function defsFor(){
  const rows=(S.defs||[]).concat((DEFD().pending||[]).map(x=>Object.assign({wait:1},x)));
  return isOwner()?rows:isLead()?rows.filter(x=>x.f===myField().k):rows.filter(x=>x.by===me().k);
}
function canApprove(r){return !!r.wait&&(isOwner()||(isLead()&&r.f===myField().k))}

/* فهرست تعریف‌ها: تازه‌ها و آن‌چه منتظر تأیید است */
function cardDefs(){
  const rows=defsFor().slice(0,5);
  if(!rows.length) return '';
  const st=(DEFD().states||{}).wait||['در انتظار تأیید','warn'];
  const waiting=rows.filter(r=>r.wait).length;
  return `<section class="card stack">
    <div class="row"><div class="head">${esc(DEFD().lead||'تعریف‌های تازه')}</div><span class="sp"></span>
      <span class="cap">${esc(waiting?fa(waiting)+' '+esc(DEFD().note||''):(DEFD().empty||''))}</span></div>
    <div class="admlist">${rows.map(r=>{const s=r.wait?st:((DEFD().states||{})[r.st||'ok']||st),
        mine=r.by===me().k;
      return `<div class="admlirow">
        <span class="ic">${ico(defKind(r.kind).i)}</span>
        <span class="sp"><b style="font-size:var(--fs-sub)">${esc(r.n)}</b>
          <small class="cap" style="display:block">${esc(defKind(r.kind).n)} · ${esc(personOf(r.by).n)} · ${esc(fieldOf(r.f).n)} · ${esc(r.at)}${mine?' · '+esc(W.you||'خودت'):''}</small></span>
        ${tag(s[0],s[1])}
        ${canApprove(r)?`<button class="btn sm" data-defok="${esc(r.id)}">${ico('i-check')}${esc(W.approve||'تأیید')}</button>
          <button class="btn sm quiet" data-defno="${esc(r.id)}" aria-label="${esc(W.back||'برگشت برای اصلاح')}">${ico('i-close')}</button>`:''}</div>`}).join('')}</div>
  </section>`;
}
function vNewev(){
  const Z=NE(), w=S.wiz, isEv=w.kind==='event', stepsAll=wizSteps(),
    st=Math.max(0,Math.min(stepsAll.length-1,+w.step||0));
  /* گام معنایی: تعریف غیررویدادی دو گام دارد و گام دومش همان مرور است */
  const sem=isEv?st:(st===0?0:3);
  const steps=stepsAll.map((n,i)=>`<div class="st ${i<st?'done':i===st?'on':''}"><i></i>
      <small>${esc(fa(i+1))}. ${esc(n)}</small></div>`).join('');
  const chips=(arr,attr,cur)=> (arr||[]).map(v=>`<button class="chip ${String(cur)===String(v)?'on':''}"
      data-wpick="${attr}" data-wval="${esc(String(v))}">${esc(String(v))}</button>`).join('');
  const kinds=(DEFD().kinds||[]).map(k=>`<button class="admkind ${w.kind===k.k?'on':''}" data-wkind="${esc(k.k)}">
      ${ico(k.i)}<b>${esc(k.n)}</b><small>${esc(k.s||'')}</small></button>`).join('');
  const types=(Z.kinds||[]).map(k=>`<button class="admkind ${w.et===k.k?'on':''}" data-wet="${esc(k.k)}">
      ${ico(k.i)}<b>${esc(k.n)}</b></button>`).join('');
  const toggles=(Z.features||[]).map(x=>`<button class="admfeat ${featOn(x.k)?'on':''}" data-wfeat="${esc(x.k)}">
      <i>${featOn(x.k)?ico('i-check'):''}</i><b>${esc(x.n)}</b><small>${esc(x.d||'')}</small></button>`).join('');
  let inner='';
  if(sem===0) inner=`<p class="cap">${esc((Z.hints||{}).kind||'')}</p>
    <div class="admkinds">${kinds}</div>
    ${w.kind==='event'?`<span class="lbl" style="margin-top:var(--sp-3)">${esc('نوع رویداد')}</span>
      <div class="admkinds types">${types}</div>`:''}
    <div class="wgrid">
      <label class="stack tight"><span class="lbl">${esc('نام')}</span>
        <input class="input" id="wzName" data-winput="name" value="${esc(w.name||'')}" placeholder="مثلاً کارگاه نقالی و پرده‌خوانی"/></label>
      <label class="stack tight"><span class="lbl">${esc('یک خط توضیح')}</span>
        <input class="input" id="wzDesc" data-winput="desc" value="${esc(w.desc||'')}" placeholder="برای کارت و فهرست"/></label>
      <label class="stack tight"><span class="lbl">${esc('برگزارکننده')}</span>
        <input class="input" id="wzOrg" data-winput="org" value="${esc(w.org||'')}" placeholder="حوزه یا مسئول اجرا"/></label>
    </div>`;
  else if(sem===1) inner=`<p class="cap">${esc((Z.hints||{}).when||'')}</p>
    <div class="stack">
      <div><span class="lbl">${esc('نحوهٔ برگزاری')}</span><div class="row tight">
        ${(Z.modes||[]).map(m=>`<button class="chip ${w.mode===m.k?'on':''}" data-wpick="mode" data-wval="${esc(m.k)}">${esc(m.n)}</button>`).join('')}</div></div>
      <div class="wgrid">
        <div><span class="lbl">${esc('تاریخ')}</span><div class="row tight">${chips(Z.whens,'date',w.date)}</div></div>
        <div><span class="lbl">${esc('ساعت شروع')}</span><div class="row tight">${chips(Z.times,'time',w.time)}</div></div>
        <div><span class="lbl">${esc('ساعت پایان')}</span><div class="row tight">${chips(Z.ends,'to',w.to)}</div></div>
      </div>
      <div class="wgrid">
        <div><span class="lbl">${esc('مدت هر جلسه')}</span><div class="row tight">${chips((Z.durs||[]).map(x=>fa(x)+' دقیقه'),'dur',w.dur?fa(w.dur)+' دقیقه':'')}</div></div>
        <div><span class="lbl">${esc('تعداد جلسه')}</span><div class="row tight">${chips((Z.sessions||[]).map(fa),'sessions',w.sessions?fa(w.sessions):'')}</div></div>
      </div>
      ${w.mode!=='online'?`<div><span class="lbl">${esc('جا')}</span><div class="row tight">${chips(Z.places,'place',w.place)}</div></div>`:''}
      ${w.mode!=='physical'?`<div><span class="lbl">${esc('سامانه یا لینک ورود')}</span><div class="row tight">${chips(Z.links,'link',w.link)}</div></div>`:''}
      <div class="wgrid">
        <div><span class="lbl">${esc('ثبت‌نام از')}</span><div class="row tight">${chips(Z.regFrom,'regFrom',w.regFrom)}</div></div>
        <div><span class="lbl">${esc('تا')}</span><div class="row tight">${chips(Z.regTo,'regTo',w.regTo)}</div></div>
      </div>
      <div><span class="lbl">${esc('سطح دسترسی')}</span><div class="row tight">
        ${(Z.privacy||[]).map(x=>`<button class="chip ${w.privacy===x.k?'on':''}" data-wpick="privacy" data-wval="${esc(x.k)}">${esc(x.n)}</button>`).join('')}</div></div>
    </div>`;
  else if(sem===2){
    const F=Z.forms||{}, caps=Z.capNote||{};
    inner=`<p class="cap">${esc((Z.hints||{}).cap||'')}</p>
    <div class="stack">
      <div class="wgrid">
        <div><span class="lbl">${esc('ظرفیت رویداد')}</span><div class="row tight">${chips(Z.caps,'cap',w.cap)}</div>
          <span class="cap">${esc(caps.cap||'')}</span></div>
        <div><span class="lbl">${esc('ظرفیت پیش‌ثبت‌نام')}</span><div class="row tight">${chips(Z.preCaps,'pre',w.pre)}</div>
          <span class="cap">${esc(caps.pre||'')}</span></div>
        <div><span class="lbl">${esc('ظرفیت مازاد')}</span><div class="row tight">${chips(Z.extras,'extra',w.extra)}</div>
          <span class="cap">${esc(caps.extra||'')}</span></div>
      </div>
      <button class="admfeat wide ${w.wait?'on':''}" data-wwait="1"><i>${w.wait?ico('i-check'):''}</i>
        <b>${esc('لیست انتظار')}</b><small>${esc((Z.wait||{})[w.wait?'on':'off']||'')}</small></button>
      <div class="head">${esc(F.lead||'فرم‌ها')}</div>
      <div><span class="lbl">${esc('فرم ثبت‌نام')}</span><div class="row tight">
        ${(F.reg||[]).map(x=>`<button class="chip ${w.form===x.k?'on':''}" data-wpick="form" data-wval="${esc(x.k)}">${esc(x.n)}</button>`).join('')}</div>
        <span class="cap">${esc(((F.reg||[]).find(x=>x.k===w.form)||{}).d||'')}${w.form?esc(' · لینک مستقیم فرم ساخته می‌شود'):''}</span></div>
      ${featOn('survey')?`<p class="cap">${esc(F.survey||'')}</p>`:''}
      <div><span class="lbl">${esc('آزمون رویداد')}</span><div class="row tight">
        ${(F.exam||[]).map(x=>`<button class="chip ${w.exam===x.k?'on':''}" data-wpick="exam" data-wval="${esc(x.k)}">${esc(x.n)}</button>`).join('')}</div></div>
      <div><span class="lbl">${esc('روش حضور و غیاب')}</span><div class="row tight">
        ${(Z.att||[]).map(x=>`<button class="chip ${w.att===x.k?'on':''}" data-wpick="att" data-wval="${esc(x.k)}">${esc(x.n)}</button>`).join('')}</div></div>
      <div><span class="lbl">${esc('یادآوری به شرکت‌کنندگان')}</span><div class="row tight">
        ${(Z.reminders||[]).map(x=>`<button class="chip ${remOn(x.k)?'on':''}" data-wrem="${esc(x.k)}">${esc(x.n)}</button>`).join('')}</div></div>
      <div class="head">${esc('قابلیت‌ها')}</div>
      <div class="admkinds feats">${toggles}</div>
      ${isMoney()?`<div class="wgrid">
        <div><span class="lbl">${esc('پرداخت')}</span><div class="row tight">
          ${Object.keys(Z.pay||{}).map(k=>`<button class="chip ${w.paid===k?'on':''}" data-wpick="paid" data-wval="${esc(k)}">${esc((Z.pay||{})[k])}</button>`).join('')}</div></div>
        <div><span class="lbl">${esc('امتیاز شرکت')}</span><div class="row tight">${chips([0,5,10,20].map(fa),'points',w.points?fa(w.points):'')}</div></div>
      </div>`:`<p class="cap">${esc(Z.money||'')}</p>`}
    </div>`;
  } else {
    const rK=defKind(w.kind), t=neKind(w.et), F=Z.forms||{};
    const on=(Z.features||[]).filter(x=>featOn(x.k)).map(x=>x.n);
    const regName=((F.reg||[]).find(x=>x.k===w.form)||{}).n||'';
    const examName=((F.exam||[]).find(x=>x.k===w.exam)||{}).n||'';
    const R=[['تعریف',rK.n+(t.n?' · '+t.n:'')],['نام',w.name||''],['توضیح',w.desc||''],['برگزارکننده',w.org||''],
      w.kind==='event'?['کی و کجا',[w.date,w.time?'از '+w.time:'',w.to?'تا '+w.to:'',w.place,w.link].filter(Boolean).join(' · ')]:null,
      w.kind==='event'?['ظرفیت',fa(w.cap||0)+' نفر'+(w.pre?' · پیش‌ثبت‌نام '+fa(w.pre):'')+(w.extra?' · مازاد '+fa(w.extra):'')+(w.wait?' · لیست انتظار':'')]:null,
      w.kind==='event'?['جلسات',fa(w.sessions||1)+' جلسه'+(w.dur?' · هر جلسه '+fa(w.dur)+' دقیقه':'')]:null,
      w.kind==='event'?['فرم‌ها',[regName,featOn('survey')?'نظرسنجی خودکار':'',examName&&w.exam!=='none'?examName:''].filter(Boolean).join(' · ')]:null,
      w.kind==='event'?['حضور و غیاب',((Z.att||[]).find(x=>x.k===w.att)||{}).n||'']:null,
      w.kind==='event'?['قابلیت‌ها',on.join(' · ')]:null,
      w.kind==='event'?['یادآوری',(Z.reminders||[]).filter(x=>remOn(x.k)).map(x=>x.n).join(' · ')]:null].filter(r=>r&&r[1]);
    inner=`<p class="cap">${esc((Z.hints||{}).review||'')}</p>
      <div class="admreview"><div class="revhead">
          <b>${esc(w.name||'بی‌نام')}</b>${tag(canPublish()?(Z.route||{}).self:(Z.route||{}).ask,canPublish()?'ok':'warn')}</div>
        ${R.map(r=>`<div class="revrow"><span class="cap">${esc(r[0])}</span><span>${esc(r[1])}</span></div>`).join('')}
        ${w.kind==='event'?`<div class="admchips"><span class="tag brand">${esc('کارت رویداد و لینک فرم')}</span>
          <span class="tag">${esc(w.wait?'لیست انتظار روشن':'لیست انتظار خاموش')}</span></div>`:''}</div>`;
  }
  const ready=sem===0?(isEv?!!(w.et&&String(w.name||'').trim()):!!String(w.name||'').trim())
    :sem===1?(!!w.edit||!!(w.date&&w.time&&w.to&&(w.mode==='online'?w.link:w.place)))
    :sem===2?!!(w.cap>0)
    :true;
  const last=stepsAll.length-1, wEdit=!!w.edit;
  return `<section class="card stack admwiz">
    <div class="row"><div class="head">${esc(Z.lead||'تعریف تازه')}</div><span class="sp"></span>
      <span class="cap">${esc(W.steps||'گام')} ${esc(fa(st+1))} ${esc(W.of||'از')} ${esc(fa(stepsAll.length))}</span></div>
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
  const f=EV.filters||[], cur=S.evF||'all';
  const all=evAll(), list=all.filter(evFilter(cur));
  const filt=f.map(x=>`<button class="tag ${cur===x.k?'on':''}" data-evF="${esc(x.k)}">${esc(x.n)}
      <b>${esc(fa(all.filter(evFilter(x.k)).length))}</b></button>`).join('');
  const rows=list.map(e=>{
    const st=(EV.states||{})[e.state]||['',''];
    const pct=Math.min(100,Math.round((+e.reg||0)/Math.max(1,+e.cap||1)*100));
    return rowLink({attrs:`data-ev="${esc(e.id)}"`, i:'i-calendar', chev:1,
      b:esc(e.n), s:`${esc(e.kind)} · ${esc(e.when)} · ${esc(e.time)} · ${esc(e.place)}`,
      right:`<span class="mini"><span class="cap">${esc(fa(e.reg))}/${esc(fa(e.cap))}</span>
        <span class="admbar-line ${pct>=100?'full':''}"><i style="width:${pct}%"></i></span>${tag(st[0],st[1])}</span>`});
  }).join('');
  return `<section class="card stack">
    <div class="row"><div class="head">${esc(EV.lead||'')}</div><span class="sp"></span>
      ${btn(secOf('newev').n,'data-sec="newev"','i-plus')}</div>
    <div class="admfilters">${filt}</div>
    <div class="admlist">${rows||emptyBox(T.empty)}</div>
  </section>`;
}

/* ── کاربران ───────────────────────────────────────────────────────────── */
function vUsers(){
  const q=norm(S.q), cur=S.uF||'all';
  const list=memList().filter(m=>{
    if(cur==='pending'&&m.st[1]!=='warn') return false;
    if(cur==='club'&&m.tags.indexOf('عضو باشگاه')<0) return false;
    if(cur==='blocked'&&m.st[1]!=='stop') return false;
    if(!q) return true;
    return norm(m.n+' '+m.code+' '+m.ph).indexOf(q)>-1;});
  const filt=UF.map(x=>`<button class="tag ${cur===x.k?'on':''}" data-uF="${x.k}">${esc(x.n)}
      <b>${esc(fa(ufCount(x.k)))}</b></button>`).join('');
  const tbody=list.map(m=>`<tr data-user="${esc(m.id)}">
      <td><b>${esc(m.n)}</b></td><td class="num">${esc(m.code)}</td><td class="num">${esc(fa(m.ph))}</td>
      <td>${tag(m.st[0],m.st[1])}</td><td>${esc(m.tags.filter(t=>isMoney()||!moneyTag(t)).join('، '))}</td>
      <td class="num">${esc(fa(m.ev))}</td><td class="num">${esc(fa(m.pt))}</td></tr>`).join('');
  const cards=list.map(m=>rowLink({attrs:`data-user="${esc(m.id)}"`, i:'i-users', chev:1,
      b:esc(m.n), s:`${esc(m.code)} · ${esc(fa(m.ph))}`, right:tag(m.st[0],m.st[1])})).join('');
  return `<section class="card stack">
    <div class="row"><div class="head">${esc(L.users)}</div>
      <span class="sp"></span><span class="cap">${esc(fa(list.length))} ${esc(W.people||'نفر')}</span>
      ${btn(T.export||'خروجی اکسل','data-uexport','i-download')}</div>
    <div class="admfilters">${filt}</div>
    ${list.length?`<div class="admmatrix"><table class="admtable">
      <thead><tr><th>نام</th><th>کد</th><th>موبایل</th><th>وضعیت</th><th>برچسب</th><th>رویداد</th><th>امتیاز</th></tr></thead>
      <tbody>${tbody}</tbody></table></div>
      <div class="admcard-user">${cards}</div>`:emptyBox(T.empty)}
    <p class="cap">${esc('پروفایل نیمه‌کاره را می‌شود تأیید یا برگرداند؛ هر کاری که کردی در پروندهٔ خودش می‌ماند.')}</p>
  </section>`;
}

/* ── فرم‌ها ────────────────────────────────────────────────────────────── */
function vForms(){
  const F=A.forms||{}, rows=F.rows||[];
  const list=rows.map((r,i)=>rowLink({attrs:`data-formrow="${i}"`, i:'i-doc',
      b:esc(r.n), s:`${esc(r.k)} · ${esc(fa(r.got))} پاسخ · ${esc(r.at)}`,
      right:`<span class="mini">${r.on?tag('باز','ok'):tag('بسته','')}
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
function vReports(){
  const periods=RP.periods||[], curP=S.rp||periods[2]||'';
  const per=periods.map(p=>`<button class="chip ${curP===p?'on':''}" data-rp="${esc(p)}">${esc(p)}</button>`).join('');
  const att=(RP.attention||[]).filter(a=>!a.own||isMoney()).map(a=>rowLink({attrs:`data-rep="${esc(a.k)}"`, i:'i-bell', chev:1, b:esc(a.t), right:tag(W.alert||'توجه','warn')})).join('');
  const list=RPLIST.filter(r=>!r.own||isMoney()).map(r=>rowLink({attrs:`data-rep="${esc(r.k)}"`, i:r.i, chev:1,
      b:esc(r.n), s:`${esc(r.v)} · ${esc(r.d)}`,
      right:`${r.up!==undefined?`<span class="tag ${r.up?'ok':'warn'}">${r.up?'▲':'▼'}</span>`:''}`})).join('');
  return `<div class="admgrid">
    <section class="card stack">
      <div class="row"><div class="head">${esc(RP.lead||'')}</div></div>
      <div class="admfilters">${per}</div>
      <div class="admlist">${list}</div>
    </section>
    <section class="card stack">
      <div class="head">${esc(W.alert||'نیاز به توجه')}</div>
      <div class="admlist">${att}</div>
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
  const C=S.cert||{}, st=Math.max(0,Math.min(4,+C.step||0));
  const steps=(CE.steps||[]).map((n,i)=>`<button class="${i===st?'on':i<st?'done':''}" data-cstep="${i}">
      <span class="n">${i<st?'✓':esc(fa(i+1))}</span><span>${esc(n)}</span></button>`).join('');
  let inner='';
  if(st===0){
    inner=`<p class="cap">${esc('قالب را بردار؛ بعد جاهای خالی و گیرنده‌ها.')}</p>
      <div class="admtpl">${(CE.templates||[]).map(t=>`<button class="t ${C.tpl===t.k?'on':''}" data-tpl="${esc(t.k)}">
        <span class="ic">${ico('i-medal')}</span><span class="tx"><b>${esc(t.n)}</b><small>${esc(t.s)}</small></span>
        ${t.on?tag('آماده','ok'):tag('پیش‌نویس','')}</button>`).join('')}</div>`;
  } else if(st===1){
    inner=`<p class="cap">${esc('هر جای خالی یکی از این سه حالت است: از پروفایل خودش می‌آید، تو می‌نویسی، یا خودش ساخته می‌شود.')}</p>
      <div class="admkindrow">${(CE.kinds||[]).map(k=>`<div class="admkindbox"><b>${ico(k.i)} ${esc(k.n)}</b>
        <small>${esc(k.s)}</small></div>`).join('')}</div>
      <div style="margin-top:var(--sp-3)">${CEP.map(p=>{
        const auto=p.type!=='fix';
        return `<div class="admparam"><span class="ic">${ico(p.type==='per'?'i-users':p.type==='sys'?'i-bolt':'i-pen')}</span>
          <span class="sp"><b>${esc(p.n)}</b><small>${esc(p.ph)}</small></span>
          ${auto?`<span class="tag ${p.type==='sys'?'brand':''}">${esc(p.type==='per'?'از پروفایل':'سیستمی')}</span>`
                :`<input class="input" data-cparam="${esc(p.k)}" value="${esc(cparam(p.k))}" placeholder="${esc(p.ph)}"/>`}</div>`}).join('')}</div>`;
  } else if(st===2){
    const kinds=(CE.audience||[]).map(a=>`<button class="admkind ${C.who===a.k?'on':''}" data-cwho="${esc(a.k)}">
      ${ico(a.i)}<b>${esc(a.n)}</b></button>`).join('');
    const sample=memList().filter(m=>m.st[1]!=='stop').slice(0,6);
    inner=`<p class="cap">${esc('شش راه برای رسیدن به گیرنده‌ها؛ هر راهی را که خواستی.')}</p>
      <div class="admkinds">${kinds}</div>
      <div class="admlist" style="margin-top:var(--sp-3)">${sample.map(m=>rowLink({i:'i-users',
        b:esc(m.n), s:`${esc(m.code)} · ${esc(m.tags.join('، '))}`, right:tag('انتخاب','brand')})).join('')}</div>
      <p class="cap">${esc('۶ نفر نمونه انتخاب شده؛ فهرست کامل با جست‌وجو و اکسل می‌آید.')}</p>`;
  } else if(st===3){
    const name=(memList()[0]||{n:'سارا محمدی'}).n;
    const svg=certSVG?certSVG({name:name, title:cparam('event')||L.sampleEvent,
      date:'مهر ۱۴۰۴', hours:cparam('hours')||'۱۲', serial:'NL-A1-2483'}):'';
    inner=`<p class="cap">${esc('پیش‌نمایش زنده؛ هر چه بالا نوشتی، همین‌جا می‌نشیند.')}</p>
      <div class="admsvgbox">${svg}</div>
      <div class="admchips"><span class="tag brand">سریال NL-A1-2483</span>
        <span class="tag">استعلام با کیوآرکد</span><span class="tag">اندازهٔ A4 افقی</span></div>`;
  } else {
    const pub=(CE.publish||[]).map(p=>`<button class="${C.pub===p.k?'on':''}" data-cpub="${esc(p.k)}">
      <span class="ic">${ico(p.i)}</span><span class="tx"><b>${esc(p.n)}</b><small>${esc(p.s)}</small></span></button>`).join('');
    const LZ=CE.lazy||{};
    inner=`<div class="admpub">${pub}</div>
      <div class="admsw" style="border:0;padding-inline:0">
        <span class="sp"><b>${esc(LZ.n||'')}</b><small>${esc(LZ.s||'')}</small></span>
        <span class="switch ${togDef('cert','lazy',true)?'on':''}" data-tog="cert" data-toglabel="${esc(LZ.n||'ساخت تنبل')}" data-togdef="1" role="switch" aria-checked="true" aria-label="${esc(LZ.n||'ساخت تنبل')}"></span></div>
      <div class="row"><span class="sp"></span>${btn('انتشار گواهی','data-certpub','i-send')}</div>`;
  }
  const jobs=(CE.jobs||[]).concat(S.jobs||[]);
  return `<section class="card stack admcert">
    <div class="row"><div class="head">${esc(CE.lead||'')}</div><span class="sp"></span>
      ${btn(sheetName('استعلام'),'data-verify-help','i-qr')}</div>
    <div class="admcertsteps">${steps}</div>
    ${inner}
    <div class="row"><span class="sp"></span>
      ${btn(W.prev||'گام پیش','data-cgo="'+Math.max(0,st-1)+'"'+(st===0?' disabled':''),"i-chev-right")}
      ${st<4?btn(W.next||'گام بعد','data-cgo="'+(st+1)+'"','i-chev-left'):''}</div>
    <hr class="hr"/>
    <div class="head">${esc(W.jobs||'کارهای صدور')}</div>
    <div class="admlist">${jobs.map(j=>rowLink({i:'i-medal', b:esc(j.n),
      s:`${esc(j.who)} · ${esc(j.way)} · ${esc(j.at)}`, right:tag(j.st==='wait'?'در نوبت':'منتشر شد',j.st==='wait'?'warn':'ok')})).join('')}</div>
  </section>`;
}
function sheetName(){return L.askCert}

/* ── تنظیمات ───────────────────────────────────────────────────────────── */
function vSettings(){
  const ST=A.settings||{}, own=isOwner();
  if(!own) S.setF=myField().k;
  let g=S.setG||'texts';
  if(!own&&g!=='access') g='access';
  const list=(ST.groups||[]).filter(x=>own||x.k==='access');
  const groups=list.map(x=>`<button class="chip ${g===x.k?'on':''}" data-setg="${esc(x.k)}">
      ${ico(x.i)}<span>${esc(x.n)}</span></button>`).join('');
  const group=(ST.groups||[]).find(x=>x.k===g)||{n:'',s:''};
  let inner='';
  if(g==='texts'){
    const TX=ST.texts||{};
    inner=`<div class="head">${esc(TX.title||'')}</div><p class="cap">${esc(TX.note||'')}</p>`+
      (TX.list||[]).map(t=>`<div class="admtext"><span class="lbl">${esc(t.n)}</span>
        <input class="input" data-text="${esc(t.k)}" value="${esc(txtDef(t.k,t.v))}"/></div>`).join('')+
      `<div class="row"><span class="sp"></span>${btn(T.save||W.save||'ذخیره شد','data-savetexts','i-check')}</div>`;
  } else if(g==='access'){
    const fk=(S.setF&&fieldOf(S.setF).k===S.setF)?S.setF:'edu', f=fieldOf(fk);
    const l=personOf(leadK(fk)), t=teamOf(fk);
    inner=`<div class="head">${esc(PERMS.title||'')}</div><p class="cap">${esc(PERMS.note||'')}</p>
      <div class="admfilters">${FIELDS.filter(x=>x.k!=='owner').map(x=>`<button class="tag ${fk===x.k?'on':''}"
        data-setF="${esc(x.k)}">${esc(x.n)}</button>`).join('')}</div>
      <div class="fslead">
        <span class="ic">${ico('i-shield')}</span>
        <span class="sp"><b>${esc(D.lead||'سرپرست')}: ${esc(l.n)}</b>
          <small>${esc(f.s)}</small></span>
        ${isOwner()?`<button class="btn sm quiet" data-setlead="${esc(fk)}">${esc(D.changeLead||'تعیین سرپرست')}</button>`:''}
      </div>
      <div class="row"><div class="head">${esc(D.specs||'کارشناسان')} (${esc(fa(t.length))} ${esc(D.specsWord||'نفر')})</div>
        <span class="sp"></span>
        ${isOwner()||isLead()?`<button class="btn sm tint" data-addspec="${esc(fk)}">${ico('i-plus')}${esc(D.addSpec||'افزودن کارشناس')}</button>`:''}</div>
      <div class="tlist">${t.map(pp=>`<div class="trow">
          <span class="va">${esc(String(pp.n||' ').slice(0,1))}</span>
          <div class="tt"><b>${esc(pp.n)}</b><small>${esc(fa(pp.open))} ${esc(D.qOpen||'')} · ${esc(fa(pp.done))} ${esc(D.qDone||'')}</small></div>
          <span class="tload"><i style="width:${pp.load}%"></i></span>
          <button class="btn sm quiet" data-specperm="${esc(pp.k)}">${esc(D.specPerms||'دسترسی‌ها')}</button></div>`).join('')||emptyBox(D.qEmpty||'')}</div>
      <hr class="hr"/>
      <div class="head">${esc('دسترسی‌های '+f.n)}</div>
      <p class="cap">${esc(PERMS.note||'')}</p>
      <div class="admmatrix"><table>
        <thead><tr><th>${esc('دسترسی')}</th><th>${esc(D.permLeadCol||'سرپرست حوزه')}</th><th>${esc(D.permSpecCol||'کارشناس')}</th></tr></thead>
        <tbody>${permRowsOf(fk).map(r=>{
          const on=specPermsOf(fk).indexOf(r[0])>-1;
          return `<tr><td>${esc(r[1])}</td>
            <td class="yn yes">✓</td>
            <td class="yn">${isOwner()||isLead()
              ?`<span class="switch ${on?'on':''}" data-fperm="${esc(r[0])}" role="switch" aria-checked="${on?'true':'false'}" aria-label="${esc(r[1])}"></span>`
              :tag(on?'دارد':'ندارد',on?'ok':'')}</td></tr>`}).join('')}</tbody></table></div>
      <hr class="hr"/>
      <div class="head">${esc(PERMS.ownerTitle||D.ownerPerms||'فقط مالک')}</div>
      <p class="cap">${esc(PERMS.ownerNote||'')}</p>
      <div class="admlist">${(OWNER_PERMS||[]).map(x=>`<div class="admsw">
        <span class="sp">${esc(x[1])}</span>${tag(D.ownerOnly||'فقط مالک','accent')}</div>`).join('')}</div>`;
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
        <div class="admlist">${(K.list||[]).map(k=>rowLink({i:'i-key', b:esc(k.n),
          s:`<span dir="ltr">${esc(k.v)}</span>`, right:tag(k.st==='ok'?'سالم':'بررسی',k.st==='ok'?'ok':'warn')})).join('')}</div>
        <div class="row">${btn('پشتیبان بگیر','data-backup','i-download')}
          ${btn('بازگردانی','data-restore','i-layers')}${btn('بازنشانی پنل','data-reset','i-trash')}</div>`;
    }
  }
  return `<section class="card stack">
    <div class="row"><div class="head">${esc(ST.lead||'')}</div><span class="sp"></span>
      <span class="cap">${esc(own?fa((ST.groups||[]).length)+' گروه':(D.fieldSettings||'حوزهٔ من'))}</span></div>
    <div class="admfilters">${groups}</div>
    <div class="admset">${inner}</div>
  </section>`;
}
/* ══ ورقه‌ها ═══════════════════════════════════════════════════════════ */
function sheetEv(id){
  const e=evOf(id); if(!e) return;
  const D=A.events||{}, st=(D.states||{})[e.state]||['',''];
  const tabs=(D.tabs||[]).filter(t=>!t.own||isMoney())
    .map(t=>`<button class="chip ${S.evTab===t.k?'on':''}" data-evtab="${esc(t.k)}">${esc(t.n)}</button>`).join('');
  let block='';
  if(S.evTab==='info'){
    block=`<div class="admmatrix"><table><tbody>
      <tr><td>${esc('نوع')}</td><td>${esc(e.kind)}</td></tr>
      <tr><td>${esc('زمان')}</td><td>${esc(e.when)} · ${esc(e.time)}</td></tr>
      <tr><td>${esc('جا')}</td><td>${esc(e.place)}</td></tr>
      <tr><td>${esc('ظرفیت')}</td><td class="num">${esc(fa(e.reg))} ${esc('از')} ${esc(fa(e.cap))}</td></tr>
      ${isMoney()?`<tr><td>${esc('هزینه')}</td><td class="num">${e.price?esc(fa(Number(e.price).toLocaleString('en-US'))+' ریال'):esc('آزاد')}</td></tr>`:''}
      <tr><td>${esc('وضعیت')}</td><td>${tag(st[0],st[1])}</td></tr></tbody></table></div>`;
  } else {
    let D2=D[{reg:'regd',att:'attd',money:'moneyd',cert:'certd',news:'newsd'}[S.evTab]]||{};
  /* وضعیت پرداخت فقط دست مالک است؛ برای بقیه «ثبت‌شده» می‌شود */
  if(!isMoney()&&D2.rows&&D2.mask) D2=Object.assign({},D2,{rows:D2.rows.map(r=>r.map((c,i)=>i===2?(D2.mask[c]||c):c))});
    block=`<div class="stack tight"><div class="head">${esc(D2.lead||'')}</div>${table(D2.rows||[],D2.cols)}</div>`;
  }
  sheetImpl('shAdm',`<div class="admsheet">
    <div class="row"><div class="tx" style="min-width:0"><div class="head">${esc(e.n)}</div>
      <div class="cap">${esc(e.kind)} · ${esc(e.when)} · ${esc(e.time)}</div></div>
      <span class="sp"></span>${tag(st[0],st[1])}</div>
    <div class="admfilters">${tabs}</div>
    ${block}
    <div class="row tight">${btn(tabName('reg'),'data-evtab="reg"','i-users')}
      ${btn(tabName('news'),'data-evtab="news"','i-send')}
      ${btn(tabName('cert'),'data-evtab="cert"','i-medal')}
      <button class="btn sm" data-evedit="${esc(e.id)}">${ico('i-pen')}${esc(W.edit||'ویرایش')}</button>
      <a class="btn sm" href="builder.html">${ico('i-doc')}${esc(D.formQueue||'کارتابل فرم')}</a></div>
    <div class="row"><span class="sp"></span>${btn(W.close||'بستن','data-close')}</div></div>`);
}
function sheetUser(id){
  const m=memOf(id); if(!m) return;
  sheetImpl('shAdm',`<div class="admsheet">
    <div class="row"><span class="ic" style="width:44px;height:44px;border-radius:14px;display:grid;place-items:center;background:var(--brand-tint);color:var(--brand-ink)">${ico('i-users')}</span>
      <span class="tx" style="min-width:0"><div class="head">${esc(m.n)}</div><div class="cap">${esc(m.code)} · ${esc(fa(m.ph))}</div></span>
      <span class="sp"></span>${tag(m.st[0],m.st[1])}</div>
    <div class="admkpi"><div class="k"><small>رویداد</small>${bits(fa(m.ev)+' رویداد')}</div>
      <div class="k"><small>امتیاز</small>${bits(fa(m.pt)+' از ۱۰۰')}</div></div>
    <div class="admchips">${m.tags.filter(t=>isMoney()||!moneyTag(t)).map(t=>tag(t,'brand')).join('')}${tag('عضویت '+m.reg,'')}</div>
    ${m.note?`<div class="admtext"><span class="lbl">یادداشت پرونده</span><span>${esc(m.note)}</span></div>`:''}
    <div class="row tight">${btn(W.approve||'تأیید پروفایل','data-uok="'+esc(m.id)+'"','i-check')}
      ${btn(W.block||'مسدود','data-ublock="'+esc(m.id)+'"','i-lock')}
      ${btn(W.note||'یادداشت','data-unote="'+esc(m.id)+'"','i-pen')}
      ${btn(W.tags||'برچسب','data-utags="'+esc(m.id)+'"','i-filter')}</div>
    <div class="admmatrix">${table([['آخرین ورود','امروز ۹:۱۴'],['وضعیت باشگاه',m.tags.indexOf('عضو باشگاه')>-1?'عضو':'عضو نیست'],
      ['فرم‌های پرکرده',fa(2)]].concat(isMoney()?[['بدهی','۰']]:[]))}</div>
    <div class="row tight"><a class="btn sm quiet" href="account.html">${ico('i-mobile')}${esc(W.view||'نمای کاربر')}</a>
      <span class="sp"></span>${btn(W.close||'بستن','data-close')}</div></div>`);
}
function sheetRep(k){
  const r=rpOf(k), d=RPD[k]||{}, rows=d.rows||[], bs=d.bars||[];
  const att=(RP.attention||[]).filter(a=>a.k===k);
  sheetImpl('shAdm',`<div class="admsheet">
    <div class="row"><span class="ic">${ico('i-chart')}</span>
      <span class="tx" style="min-width:0"><div class="head">${esc(r.n||'')}</div>
      <div class="cap">${esc(r.v||'')} · ${esc(r.d||'')}</div></span><span class="sp"></span>
      ${r.up!==undefined?`<span class="tag ${r.up?'ok':'warn'}">${r.up?'▲':'▼'}</span>`:''}</div>
    ${bs.length?bars(bs,true):''}
    ${table(rows,['',''])}
    ${att.length?`<div class="stack tight"><div class="head">${esc(W.alert||'')}</div>
      ${att.map(a=>`<div class="admlirow">${ico('i-bell')}<span class="sp">${esc(a.t)}</span></div>`).join('')}</div>`:''}
    <div class="admkpi">${(RP.periods||[]).slice(0,4).map(p=>`<div class="k"><small>${esc(p)}</small>
      ${bits(r.v||'')}</div>`).join('')}</div>
    <div class="row tight">
      <a class="btn sm" href="builder.html">${ico('i-chart')}${esc('نمودار کامل')}</a>
      ${btn(T.export||'خروجی اکسل','data-rexport','i-download')}
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
/* افزودن کارشناس: از میان کاربران همان سامانه */
function sheetAddSpec(fk){
  const f=fieldOf(fk);
  const used=allP().map(p=>p.n);
  const list=memList().filter(m=>used.indexOf(m.n)<0);
  sheetImpl('shAdm',`<div class="admsheet">
    <div class="row"><div class="head">${esc(D.addSpec||'افزودن کارشناس')}</div><span class="sp"></span>
      ${btn(W.close||'بستن','data-close')}</div>
    <p class="cap">${esc('حوزه: '+f.n+' · دسترسی‌های پیش‌فرض کارشناس‌های همین حوزه می‌نشیند.')}</p>
    <div class="admlist">${list.map(m=>`<button class="admrow2" data-newspec="${esc(m.id)}">
      <span class="va">${esc(m.n.slice(0,1))}</span>
      <span class="tx"><b>${esc(m.n)}</b><small>${esc(m.code)} · ${esc(m.tags.join('، '))}</small></span>
      ${tag('کارشناس','brand')}</button>`).join('')||emptyBox(D.qEmpty||'')}</div></div>`);
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

/* ══ رندر ══════════════════════════════════════════════════════════════ */
const VIEWS={dash:vDash, newev:vNewev, events:vEvents, users:vUsers, forms:vForms,
  reports:vReports, cert:vCert, settings:vSettings};
function body(){
  if(!canSec(S.sec)) return `<section class="card stack">${emptyBox(W.locked||'')}
    <p class="cap" style="text-align:center">${esc(W.lockedLead||'')}</p>
    <div class="row" style="justify-content:center">
      ${btn(W.view||'نمای کاربر','data-sec="dash"','i-grid')}
      ${btn(D.mine||'نمای من','data-who-sheet','i-shield')}</div></section>`;
  const v=VIEWS[S.sec];
  return v?v():emptyBox(T.none);
}
function renderBody(){$('#admBody').innerHTML=body()}
/* ── نگهبان حالت: حالت کهنه یا ناقص نباید داشبورد را خراب کند ─────────── */
function sanitize(){
  if(S.v!==SVER){ S=JSON.parse(JSON.stringify(BASE)); return; }
  if(!personOf(S.who)) S.who=BASE.who;
  if(fieldOf(S.setF).k!==S.setF) S.setF=BASE.setF;
  if(S.addF&&(!personOf(S.addF)||fieldOf(S.addF).k!==S.addF)) delete S.addF;
  if(['all','بالا','میان','معمولی'].indexOf(S.qf)<0) S.qf='all';
  if(['info','reg','att','money','cert','news'].indexOf(S.evTab)<0) S.evTab='info';
  if(!isMoney()&&S.evTab==='money') S.evTab='info';
  S.qMore=S.qMore?1:0;
}

function render(){ if(!canSec(S.sec)) S.sec='dash'; renderNav(); renderBar(); renderBody();
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
  const nsp=q('[data-newspec]'); if(nsp){const id=nsp.dataset.newspec, m=memList().find(x=>x.id===id); if(!m) return;
    const fk=isOwner()?((S.addF&&fieldOf(S.addF).k===S.addF)?S.addF:myField().k):myField().k;
    S.extra=(S.extra||[]).concat([{k:'x'+m.id, n:m.n, f:fk, lv:'کارشناس', open:0, done:0, late:0, avg:0, load:12, score:70, since:'مهر ۱۴۰۴'}]);
    save(); closeSheets(); renderBody(); toast((D.addedSpec||'کارشناس اضافه شد')+' · '+m.n); return}
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
    go(sec.dataset.sec); return}
  const evt=q('[data-evtab]'); if(evt){S.evTab=evt.dataset.evtab; save(); if(S.evId) sheetEv(S.evId); return}
  const ev=q('[data-ev]'); if(ev){S.evId=ev.dataset.ev; S.evTab=S.evTab||'info'; save(); sheetEv(S.evId); return}
  const ef=q('[data-evF]'); if(ef){S.evF=ef.dataset.evf; save(); renderBody(); return}
  const uf=q('[data-uF]'); if(uf){S.uF=uf.dataset.uf; save(); renderBody(); return}
  const us=q('[data-user]'); if(us){sheetUser(us.dataset.user); return}
  const rp=q('[data-rp]'); if(rp){S.rp=rp.dataset.rp; save(); renderBody(); toast('دوره: '+rp.dataset.rp); return}
  const rep=q('[data-rep]'); if(rep){sheetRep(rep.dataset.rep); return}
  const cs=q('[data-cstep]')||q('[data-cgo]');
  if(cs){S.cert.step=+(cs.dataset.cstep!=null?cs.dataset.cstep:cs.dataset.cgo); save(); renderBody(); return}
  const tp=q('[data-tpl]'); if(tp){S.cert.tpl=tp.dataset.tpl; save(); renderBody(); toast('قالب برداشته شد'); return}
  const cw=q('[data-cwho]'); if(cw){S.cert.who=cw.dataset.cwho; save(); renderBody(); return}
  const cp=q('[data-cpub]'); if(cp){S.cert.pub=cp.dataset.cpub; save(); renderBody(); return}
  const se=q('[data-setg]'); if(se){S.setG=se.dataset.setg; save(); renderBody(); return}
  const tg=q('[data-tog]'); if(tg){const key=tg.dataset.tog+'|'+tg.dataset.toglabel;
    const cur=togDef(tg.dataset.tog, tg.dataset.toglabel, tg.dataset.togdef==='1');
    const on=!cur; S.toggles[key]=on; save();
    tg.classList.toggle('on',on); tg.setAttribute('aria-checked',on?'true':'false');
    toast((tg.dataset.toglabel||'')+(on?' روشن شد':' خاموش شد')); return}
  const fs=q('[data-formsw]'); if(fs){const i=+fs.dataset.formsw, r=((A.forms||{}).rows||[])[i];
    if(r){r.on=!r.on; toast(r.on?'فرم باز شد':'فرم بسته شد'); renderBody()} return}
  const wk=q('[data-wkind]'); if(wk){S.wiz.kind=wk.dataset.wkind; S.wiz.step=0; save(); renderBody(); return}
  const wet=q('[data-wet]'); if(wet){S.wiz.et=wet.dataset.wet; S.wiz.feat=defaultFeat(wet.dataset.wet);
    save(); renderBody(); return}
  const wp=q('[data-wpick]'); if(wp){const key=wp.dataset.wpick, val=wp.dataset.wval, num=['cap','pre','extra','dur','sessions','points'];
    S.wiz[key]=num.indexOf(key)>-1?(key==='points'?+un(val):+un(val)):val; save(); renderBody(); return}
  const wf=q('[data-wfeat]'); if(wf){const k=wf.dataset.wfeat; S.wiz.feat[k]=featOn(k)?0:1;
    toast(neKind(S.wiz.et).n+' · '+(S.wiz.feat[k]?'روشن شد':'خاموش شد')); save(); renderBody(); return}
  const wr=q('[data-wrem]'); if(wr){const k=wr.dataset.wrem; S.wiz.rem[k]=remOn(k)?0:1; save(); renderBody(); return}
  const ww=q('[data-wwait]'); if(ww){S.wiz.wait=S.wiz.wait?0:1; save(); renderBody(); return}
  const wc=q('[data-wcancel]'); if(wc){S.wiz=Object.assign({},BASE.wiz); save(); renderBody(); return}
  const ws=q('[data-wstep]'); if(ws){const step=+ws.dataset.wstep;
    if(ws.dataset.wgo!=='1'){S.wiz.step=step; save(); renderBody(); return}
    const w=S.wiz, i=step-1;
    if(i===0&&!(w.kind&&(w.kind!=='event'||w.et)&&String(w.name||'').trim())){toast(W.fieldsReq||'این قلم را پر کن'); return}
    if(i===1&&!w.edit&&!(w.date&&w.time&&w.to&&(w.mode==='online'?w.link:w.place))){toast(W.fieldsReq||'این قلم را پر کن'); return}
    S.wiz.step=step; save(); renderBody(); return}
  const dOk=q('[data-defok]'); if(dOk){const id=dOk.dataset.defok, r=defsFor().find(x=>x.id===id)||{};
    S.defs=(S.defs||[]).map(x=>x.id===id?Object.assign({},x,{wait:0,st:'ok'}):x);
    if(r.kind==='event'&&!evAll().some(e=>e.id==='d-'+id)) S.added=[{id:'d-'+id, n:r.n, kind:'رویداد', when:'تاریخ در تعریف', time:'', place:r.f==='club'?'کتابخانهٔ نورا':'', cap:0, reg:0, state:'soon', price:0}].concat(S.added||[]);
    save(); renderBody(); toast((DEFD().route||{}).self||'تأیید شد'); return}
  const dNo=q('[data-defno]'); if(dNo){const id=dNo.dataset.defno;
    S.defs=(S.defs||[]).map(x=>x.id===id?Object.assign({},x,{wait:0,st:'no'}):x);
    save(); renderBody(); toast((DEFD().states||{}).no?DEFD().states.no[0]:'برگشت برای اصلاح'); return}
  const wsend=q('[data-wsend]'); if(wsend){const w=S.wiz, et=neKind(w.et), kk=defKind(w.kind);
    const kind=w.kind==='event'?(et.n||'رویداد'):kk.n;
    if(w.edit){  /* ویرایش: همان‌جا می‌ماند، نه پیش‌نویس می‌شود نه از فهرست می‌رود */
      S.evEdit=Object.assign({},S.evEdit||{},{}); S.evEdit[w.edit]={n:w.name||'', kind:kind,
        when:w.date||'', time:[w.time,w.to].filter(Boolean).join(' تا '), place:w.mode==='online'?(w.link||'آنلاین'):(w.place||''),
        cap:+w.cap||0};
      S.wiz=Object.assign({},BASE.wiz); save();
      toast((NE().again||'ویرایش شد')); go('events'); renderBody(); return}
    const route={id:'nx'+Date.now(), kind:w.kind, n:w.name||'بی‌نام', by:me().k, f:myField().k, at:'همین حالا'};
    if(canPublish()){
      S.added=[{id:route.id, n:route.n, kind:kind, when:w.date||'', time:[w.time,w.to].filter(Boolean).join(' تا '),
        place:w.mode==='online'?(w.link||'آنلاین'):(w.place||''), cap:+w.cap||0, reg:0, state:'soon', price:0}].concat(S.added||[]);
      S.wiz=Object.assign({},BASE.wiz); S.evF='all'; save();
      toast((NE().made||'منتشر شد')); go('events'); return}
    S.defs=[Object.assign({},route,{wait:1})].concat(S.defs||[]);
    S.wiz=Object.assign({},BASE.wiz); save(); renderBody();
    toast((NE().queued||'رفت برای تأیید')); go('dash'); return}
  const cpub=q('[data-certpub]'); if(cpub){
    const n=(memList()[0]||{}).n||'';
    S.jobs=[{n:'گواهی '+((A.cert||{}).templates||[]).filter(t=>t.k===S.cert.tpl).map(t=>t.n)[0]||'تازه',
      who:fa(6)+' نفر', way:((A.cert||{}).publish||[]).filter(p=>p.k===S.cert.pub).map(p=>p.n)[0]||'اعلان',
      at:'همین حالا', st:'wait'}].concat(S.jobs||[]);
    save(); renderBody(); toast(W.published||'منتشر شد'); return}
  const uok=q('[data-uok]'); if(uok){const id=uok.dataset.uok;
    S.uov[id]=Object.assign({},S.uov[id],{st:['تأییدشده','ok']}); save();
    toast('پروفایل تأیید شد'); sheetUser(id); renderBody(); return}
  const ed=q('[data-evedit]'); if(ed){const e=evOf(ed.dataset.evedit); if(e){
    const t=(NE().kinds||[]).find(x=>x.n===e.kind)||{};
    const half=String(e.time||'').split('تا').map(x=>x.trim()).filter(Boolean);
    S.wiz=Object.assign({},BASE.wiz,{edit:e.id,kind:'event',et:t.k||'custom',name:e.n||'',
      desc:e.d||'',date:e.when||'',time:half[0]||'',to:half[1]||'',place:(e.place||'')==='آنلاین'?'':(e.place||''),
      link:(e.place||'')==='آنلاین'?(NE().links||[])[0]:'',cap:+e.cap||45,
      mode:(e.place||'')==='آنلاین'?'online':'physical'});
    closeSheets(); save(); toast(W.editEvent||'در حال ویرایش'); go('newev'); return}}
  const ub=q('[data-ublock]'); if(ub){const id=ub.dataset.ublock;
    S.uov[id]=Object.assign({},S.uov[id],{st:['مسدود','stop']}); save();
    toast('دسترسی این کاربر بسته شد'); sheetUser(id); renderBody(); return}
  const un2=q('[data-unote]'); if(un2){toast('یادداشتت در پرونده نشست'); return}
  const ut=q('[data-utags]'); if(ut){toast('برچسب‌ها از همین‌جا می‌آید'); return}
  const fx=q('[data-uexport]'); if(fx){toast('خروجی اکسل ساخته می‌شود؛ لینکش پیام می‌آید'); return}
  const fl=q('[data-flink]'); if(fl){copy(location.href.split('#')[0]+'#forms?form=1',null,L.linkCopied); return}
  const rx=q('[data-rexport]'); if(rx){toast('خروجی اکسل با ۷ شیت ساخته می‌شود'); return}
  const vh=q('[data-verify-help]'); if(vh){toast('صفحهٔ استعلام: lifeline1.ir/c/<سریال>'); return}
  const bk=q('[data-backup]'); if(bk){toast('پشتیبان شبانه هست؛ پشتیبان دستی هم گرفته شد'); return}
  const rr=q('[data-restore]'); if(rr){toast('بازگردانی فقط با تأیید سوپرادمین'); return}
  const rs2=q('[data-reset]'); if(rs2){try{localStorage.removeItem(SKEY)}catch(e){} S=JSON.parse(JSON.stringify(BASE));
    toast('پنل به حالت اول برگشت'); go('dash'); return}
  const st2=q('[data-savetexts]'); if(st2){save(); toast(T.save||W.save||'ذخیره شد'); return}
});
document.addEventListener('change',e=>{
  const el=e.target; if(!el||!el.dataset) return;
  if(el.dataset.cparam){S.cert.params[el.dataset.cparam]=String(el.value||'').trim(); save(); return}
  if(el.dataset.text){S.texts[el.dataset.text]=String(el.value||''); save(); return}
});
document.addEventListener('input',e=>{
  const el=e.target; if(!el||!el.dataset) return;
  if(el.id==='admQ'){S.q=el.value; renderBody(); return}
  if(el.dataset.winput){S.wiz[el.dataset.winput]=el.value; save(); return}
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
  if(h&&secOf(h)) S.sec=h;
  if(!secOf(S.sec)) S.sec='dash';
  const th=$('#admTheme'); if(th) th.onclick=()=>{if(typeof themeToggle==='function') themeToggle()};
  const tb=$('#admTabs');
  if(tb) tb.addEventListener('click',e=>{const a=e.target.closest('a[data-sec]'); if(!a) return;
    e.preventDefault(); go(a.dataset.sec)});
  if(typeof initUI==='function'){try{initUI()}catch(e){}}
  bind();
  sanitize(); render();
})();
})();
