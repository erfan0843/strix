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
const SVER=49;
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
  cert:{step:0,tpl:'t1',kind:'per',params:{},who:'ev',whoVal:'',pub:'notify'},
  setG:'texts', toggles:{}, texts:{}, jobs:[], added:[], uov:{}, rp:'',
  psec:'list', ped:null};
let S=JSON.parse(JSON.stringify(BASE));
try{
  const v=JSON.parse(localStorage.getItem(SKEY)||'null');
  if(v&&typeof v==='object'){
    S=Object.assign(S,v);
    S.wiz=Object.assign({},BASE.wiz,v.wiz||{});
    S.cert=Object.assign({},BASE.cert,v.cert||{});
    if(v.ped){ if(!Array.isArray(v.ped.blocks)) delete v.ped; }
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
    <div class="row"><div class="head">${esc(EV.lead||'')}</div><span class="sp"></span>
      ${btn('رویداد جدید','data-evnew','i-calendar')}</div>
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

/* ══ مطلبها: فهرست و ویرایشگر بلوکی ══════════════════════════════════════
   مطلب بلوکی است: پاراگراف، تیتر، عکس، ویدیو (آپارات، یوتیوب یا فایل)،
   صدا، نقل قول، فهرست، دکمهٔ لینک، جعبهٔ توجه، جمع‌شونده و جداکننده؛
   هر کدام هر چند تا. رویداد و فرم هم پیوند می‌خورند و پیش‌نمایش، پیش از
   انتشار در post.html دیده می‌شود. مالک و سرپرست منتشر می‌کنند؛ بقیه
   می‌فرستند برای تأیید. */
const PGRADS=['linear-gradient(135deg,#1E6FD0,#0A3A82)','linear-gradient(135deg,#3E5B84,#0B2447)',
  'linear-gradient(135deg,#0E7B61,#083D33)','linear-gradient(135deg,#8A5A2B,#3D2714)'];
const PTY={p:{n:'پاراگراف',i:'i-pen'},h:{n:'تیتر',i:'i-align'},img:{n:'عکس',i:'i-image'},
  vid:{n:'ویدیو',i:'i-play'},aud:{n:'صدا',i:'i-headphone'},q:{n:'نقل قول',i:'i-doc'},
  ul:{n:'فهرست',i:'i-list'},ol:{n:'شمارشی',i:'i-list'},btn:{n:'دکمهٔ لینک',i:'i-link'},
  box:{n:'جعبهٔ توجه',i:'i-bell'},tog:{n:'جمع‌شونده',i:'i-chev-down'},hr:{n:'جداکننده',i:'i-close'}};
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
      <label class="btn sm quiet">${ico('i-file-up')}آپلود عکس<input type="file" accept="image/*" data-bfile="${i}" hidden/></label>
      ${inp('src','یا لینک عکس',b.src)}
      ${inp('cap','زیرنویس عکس',b.cap)}${inp('alt','متن جایگزین (دسترس‌پذیری)',b.alt)}`; break;
    case 'vid': body=inp('src','لینک آپارات، یوتیوب یا فایل mp4',b.src)+inp('cap','زیرنویس ویدیو',b.cap)
      +`<small class="cap">لینک آپارات و یوتیوب خودش پخش‌شونده می‌شود.</small>`; break;
    case 'aud': body=inp('src','لینک مستقیم فایل صوتی (mp3)',b.src)+inp('cap','نام یا زیرنویس صدا',b.cap); break;
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
  const catList=(()=>{try{return (window.NORA&&NORA.ARTICLES||[]).map(a=>a.cat).concat(pedPosts().map(x=>x.cat||''))
    .filter((v,i,arr)=>v&&arr.indexOf(v)===i)}catch(e){return []}})();
  const evs=evAll(), mades=madeForms(), demos=demoForms();
  const cov=d.cover||{};
  return `<section class="card stack">
    <div class="row"><div class="head">${d.id?'ویرایش مطلب':'مطلب تازه'}</div><span class="sp"></span>
      ${btn(W.back||'بازگشت','data-pback','i-back')}</div>
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
        <datalist id="pcats">${catList.map(c=>`<option value="${esc(c)}"/>`).join('')}</datalist></div>
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
    <hr class="hr"/>
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
      <button class="btn quiet" data-pprev="1">${ico('i-eye')} پیش‌نمایش</button>
      ${isOwner()||isLead()
        ?`<button class="btn primary" data-ppub="1">${ico('i-check')} انتشار</button>`
        :`<button class="btn primary" data-psend="1">${ico('i-send')} فرستادن برای تأیید</button>`}
    </div>
    <p class="cap">پیش‌نمایش پیش از انتشار در post.html باز می‌شود؛ خواننده مطلب را با فهرست، رسانه و پیوند رویداد و فرم می‌بیند.</p>
  </section>`;
}
function vPosts(){
  if(S.psec==='edit') return postEditor();
  const u=U(), rows=pedPosts().filter(p=>p.pub||p.pend);
  const list=rows.map(p=>rowLink({attrs:`data-pedit="${esc(p.id)}"`, i:'i-article',
    b:esc(p.t||'بی نام'),
    s:`${esc(p.cat||'مطلب')} · ${faN(pedMin(p))} دقیقه · ${faN(+p.views||0)} بازدید${p.ev?' · پیوند رویداد':''}${p.fm?' · پیوند فرم':''}`,
    right:`${p.pend?tag('در انتظار تأیید','warn'):(p.pub?tag('منتشر شده','ok'):tag('پیش‌نویس',''))}
      <a class="btn sm quiet" href="post.html?id=${encodeURIComponent(p.id)}${p.pub?'':'&d=1'}" target="_blank" rel="noopener" aria-label="دیدن">${ico('i-eye')}</a>
      <button class="btn sm quiet" data-ppin="${esc(p.id)}" aria-label="پین">${ico('i-pin')}</button>
      <button class="btn sm quiet" data-pdel="${esc(p.id)}" aria-label="حذف">${ico('i-trash')}</button>`})).join('');
  const demo=((window.NORA&&NORA.ARTICLES)||[]).map(a=>rowLink({attrs:`data-pprevgo="${esc(a.id)}"`, i:'i-article',
    b:esc(a.t), s:`${esc(a.cat)} · ${faN(a.min)} دقیقه · نمونهٔ ثابت`, right:tag('نمونه','')})).join('');
  return `<section class="card stack">
    <div class="row"><div class="head">مطلب‌ها</div><span class="sp"></span>
      ${btn('مطلب تازه','data-pnew','i-plus')}</div>
    <div class="admlist">${list||emptyBox('هنوز مطلبی نساخته‌ای')}</div>
    <hr class="hr"/>
    <div class="head">نمونه‌های ثابت</div>
    <div class="admlist">${demo}</div>
    <p class="cap">مطلب منتشرشده در خانهٔ کاربران، بخش «مطالب» می‌نشیند و پیش‌نمایشش در post.html باز می‌شود.</p>
  </section>`;
}

/* تعریف جدید: همین‌جا فقط مطلب ساخته می‌شود؛ رویداد از بخش رویدادها باز می‌شود */
function vNewev(){
  if(!S.ped||S.ped.pub||S.ped.pend) S.ped=pedFresh();
  return postEditor();
}

/* ══ رندر ══════════════════════════════════════════════════════════════ */
const VIEWS={dash:vDash, newev:vNewev, events:vEvents, users:vUsers, forms:vForms, posts:vPosts,
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
function renderBody(){$('#admBody').innerHTML=body()}
/* ── نگهبان حالت: حالت کهنه یا ناقص نباید داشبورد را خراب کند ─────────── */
function sanitize(){
  if(S.v!==SVER){ S=JSON.parse(JSON.stringify(BASE)); return; }
  if(!personOf(S.who)) S.who=BASE.who;
  if(fieldOf(S.setF).k!==S.setF) S.setF=BASE.setF;
  if(S.addF&&(!personOf(S.addF)||fieldOf(S.addF).k!==S.addF)) delete S.addF;
  if(['all','بالا','میان','معمولی'].indexOf(S.qf)<0) S.qf='all';
  if(['info','reg','att','money','cert','news'].indexOf(S.evTab)<0) S.evTab='info';
  if(['list','edit'].indexOf(S.psec)<0) S.psec='list';
  if(S.ped&&(!Array.isArray(S.ped.blocks))) S.ped=null;
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
  /* ── مطلبها: فهرست و ویرایشگر بلوکی ── */
  const pnew=q('[data-pnew]'); if(pnew){
    S.ped=pedFresh();
    S.psec='edit'; save(); renderBody(); return}
  const pedit=q('[data-pedit]'); if(pedit){const pid=pedit.dataset.pedit, pp=pedPosts().find(x=>String(x.id)===String(pid));
    if(pp){S.ped=JSON.parse(JSON.stringify(pp)); S.ped.tags=(pp.tags||[]).join('، '); S.psec='edit'; save(); renderBody()} return}
  const pback=q('[data-pback]'); if(pback){S.ped=null; S.psec='list'; save(); renderBody(); return}
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
    S.ped=null; S.psec='list'; save(); renderBody(); toast('مطلب منتشر شد؛ خانهٔ کاربران هم می‌بیند'); return}
  const psend=q('[data-psend]'); if(psend&&S.ped){
    const d2=JSON.parse(JSON.stringify(S.ped));
    if(!String(d2.t||'').trim()){toast('عنوان مطلب را بنویس'); return}
    d2.tags=String(d2.tags||'').split(/[،,]/).map(x=>x.trim()).filter(Boolean);
    d2.min=pedMin(d2); d2.pub=0; d2.pend=1; d2.at=d2.at||Date.now(); pedSave(d2);
    S.ped=null; S.psec='list'; save(); renderBody(); toast('مطلب رفت در صف تأیید'); return}

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
  if(el.dataset.pev&&S.ped){S.ped.ev=el.value; save(); return}
  if(el.dataset.pfm&&S.ped){S.ped.fm=el.value; save(); return}
  if(el.dataset.pfile){const f=(el.files||[])[0]; if(!f||!S.ped) return;
    shrinkPoster(f,url=>{ if(!url){toast('این تصویر خوانده نشد'); return}
      S.ped.cover={up:url}; save(); renderBody(); toast('جلد خودم نشست');}); return}
  if(el.dataset.bfile&&S.ped){const i=+el.dataset.bfile, f=(el.files||[])[0]; if(!f) return;
    shrinkPoster(f,url=>{ if(!url){toast('این تصویر خوانده نشد'); return}
      const b=S.ped.blocks[i]; if(b){b.up=url; delete b.src; save(); renderBody()}}); return}
  if(el.dataset.cparam){S.cert.params[el.dataset.cparam]=String(el.value||'').trim(); save(); return}
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
      if(b.ty==='ul'||b.ty==='ol') b.x=el.value.split('\n');
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
  if(h&&secOf(h)) S.sec=h;
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
