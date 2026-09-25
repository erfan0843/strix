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
const W=A.w||{}, T=A.t||{};
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
const BASE={sec:'dash', q:'', evF:'all', evId:null, evTab:'info', uF:'all',
  wiz:{step:0,kind:'',name:'',date:'',time:'',place:'',cap:45},
  cert:{step:0,tpl:'t1',kind:'per',params:{},who:'ev',whoVal:'',pub:'notify'},
  setG:'texts', role:'super', permRole:'', perms:{}, toggles:{}, texts:{}, jobs:[], added:[], uov:{}, rp:''};
let S=JSON.parse(JSON.stringify(BASE));
try{
  const v=JSON.parse(localStorage.getItem(SKEY)||'null');
  if(v&&typeof v==='object'){
    S=Object.assign(S,v);
    S.wiz=Object.assign({},BASE.wiz,v.wiz||{});
    S.cert=Object.assign({},BASE.cert,v.cert||{});
    ['jobs','added'].forEach(k=>{if(!Array.isArray(S[k])) S[k]=[]});
    delete S.custom;
    if(!S.perms||typeof S.perms!=='object') S.perms={};
    if(!S.uov||typeof S.uov!=='object') S.uov={};
    if(!S.toggles||typeof S.toggles!=='object') S.toggles={};
    if(!S.texts||typeof S.texts!=='object') S.texts={};
  }
}catch(e){}
const save=()=>{try{localStorage.setItem(SKEY,JSON.stringify(Object.assign({},S,{q:'',evId:null})))}catch(e){}};

/* خاموش و روشن‌های تنظیمات: پیش‌فرض از داده، بعد از آن از خود کاربر */
const togDef=(g,label,def)=>{const k=g+'|'+label; if(!(k in S.toggles)) S.toggles[k]=!!def; return S.toggles[k]};
const txtDef=(k,v)=>{if(!(k in S.texts)) S.texts[k]=v; return S.texts[k]};

/* ── نقش‌ها و دسترسی‌ها ────────────────────────────────────────────────── */
const ROLES=A.roles||[], PERMS=A.perms||{}, PROWS=PERMS.rows||[], SUPER=PERMS.superOnly||[];
const ALLP=PROWS.map(r=>r[0]);
const roleOf=k=>ROLES.find(r=>r.k===k)||ROLES[ROLES.length-1]||{k:'super',n:'سوپرادمین',perms:['all']};
function basePerms(k){
  const r=roleOf(k);
  if((r.perms||[]).indexOf('all')>-1) return ALLP.slice();
  if((r.perms||[]).indexOf('allExceptSuper')>-1) return ALLP.filter(p=>SUPER.indexOf(p)<0);
  return (r.perms||[]).slice();
}
/* دسترسی هر نقش: تا وقتی سوپرادمین دستی عوضش نکرده، از فهرست خودِ نقش می‌آید */
function permsOf(k){const o=(S.perms||{})[k]; return o?o.slice():basePerms(k)}
const GATE={newev:'ev_create', events:'ev_view_all', users:'us_view', forms:'fm_create',
  reports:'rp_view', cert:'certificate', settings:'sys_settings'};
const can=p=>!p||permsOf(S.role).indexOf(p)>-1;

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
  {id:'u10',n:'مجید رستمی',  code:'NL-1033', ph:'09121230000', st:['تأییدشده','ok'],   tags:['مدرس'], reg:'اردیبهشت ۱۴۰۳', ev:7, pt:2010, note:'مدرس فن بیان'}];
const memOf=id=>{const m=MEM.find(x=>x.id===id); if(!m) return null;
  const o=(S.uov||{})[id]; return o?Object.assign({},m,o):m};
const memList=()=>MEM.map(m=>memOf(m.id));
const UF=[{k:'all',n:'همه'},{k:'pending',n:'در صف تأیید'},{k:'club',n:'عضو باشگاه'},{k:'blocked',n:'مسدود'}];
const ufCount=k=>({all:MEM.length, pending:memList().filter(m=>m.st[1]==='warn').length,
  club:memList().filter(m=>m.tags.indexOf('عضو باشگاه')>-1).length,
  blocked:memList().filter(m=>m.st[1]==='stop').length}[k]);

/* ── رویدادها ──────────────────────────────────────────────────────────── */
const EV=A.events||{}, EVROWS=EV.rows||[];
const evAll=()=>(S.added||[]).concat(EVROWS);
const evOf=id=>evAll().find(e=>e.id===id)||null;
const fN=n=>fa(Number(n).toLocaleString?Number(n).toLocaleString('en-US'):n);
const evFilter=f=>f==='live'?e=>e.state==='live' : f==='soon'?e=>e.state==='soon'||e.state==='draft'
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
  $('#admNav').innerHTML=ALLSECS.map(s=>{
    const lock=!can(GATE[s.k]);
    return `<button class="btn quiet block ${S.sec===s.k?'on':''}" data-sec="${s.k}">
      ${ico(s.i)}<span>${esc(s.n)}</span>${s.badge?`<span class="tag warn bd">${esc(s.badge)}</span>`:(lock?`<span class="bd">${ico('i-lock')}</span>`:'')}</button>`;}).join('');
  $('#admTabs').innerHTML=TABS.map(t=>{const s=secOf(t.k);
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
    <button class="chip" data-rolesheet>${ico('i-shield')}<span>${esc(roleOf(S.role).n)}</span></button>`;
}

/* ══ بخش‌ها ═════════════════════════════════════════════════════════════ */

/* ── داشبورد ───────────────────────────────────────────────────────────── */
function vDash(){
  const D=A.dash||{};
  const stats=(A.status||[]).map(s=>`<button class="admstat" data-sec="${esc(s.k)}">
      <span class="ic" aria-hidden="true">${ico(s.i)}</span>
      <span class="tx"><small>${esc(s.n)}</small><b>${esc(s.v)}</b><small>${esc(s.d)}</small></span></button>`).join('');
  const tasks=(D.tasks||[]).map(t=>`<button class="admtask" data-sec="${esc(t.k)}">
      <span class="ic" aria-hidden="true">${ico(t.i)}</span>
      <span class="tx"><b>${esc(t.s)}</b><small>${esc(t.d)}</small></span>
      <span class="tag brand">${esc(t.b)}</span></button>`).join('');
  const kpi=(D.kpi||[]).map(k=>`<div class="k"><small>${esc(k.n)}</small><b>${esc(k.v)}</b>
      <small>${esc(k.d||'')}</small>${k.up?`<span class="up">▲ ${esc(W.trend||'روند')}</span>`:''}</div>`).join('');
  const li=(arr,kind)=>(arr||[]).map(x=>`<div class="admlirow">
      <span class="ic">${ico(kind)}</span><span class="sp"><b style="font-size:var(--fs-sub)">${esc(x.t)}</b>
      <small class="cap" style="display:block">${esc(x.d)}</small></span>
      ${x.k?`<button class="tag brand" data-sec="${esc(x.k)}">${esc(x.b)}</button>`:tag(x.b,'')}</div>`).join('');
  const tr=D.trend||{bars:[],days:[]};
  return `
  <div class="admstats">${stats}</div>
  <div class="admgrid">
    <section class="card stack">
      <div class="row"><div class="head">${esc(W.tasks||'کارهای نوبت تو')}</div><span class="sp"></span>
        <button class="btn sm quiet" data-sec="events">${ico('i-calendar')}${esc(secOf('events').n)}</button></div>
      <div class="admtasks">${tasks}</div>
      <hr class="hr"/>
      <div class="head">${esc(W.kpi||'عددهای امروز')}</div>
      <div class="admkpi">${kpi}</div>
    </section>
    <section class="card stack">
      <div class="head">${esc(tr.n||'')}</div>
      ${bars(tr.bars||[],true)}
      <div class="admbarsx">${(tr.days||[]).map(d=>`<span>${esc(d)}</span>`).join('')}</div>
      <hr class="hr"/>
      <div class="head">${esc(W.today||'برنامهٔ امروز')}</div>
      <div class="admli">${li(D.today,'i-clock')}</div>
      <hr class="hr"/>
      <div class="head">${esc(W.alert||'نیاز به توجه')}</div>
      <div class="admli">${li(D.alerts,'i-bell')}</div>
    </section>
  </div>`;
}

/* ── رویداد تازه: ویزارد سه‌گامی ───────────────────────────────────────── */
function vNewev(){
  const Z=A.wizard||{}, w=S.wiz||{}, st=Math.max(0,Math.min(2,+w.step||0));
  const steps=(Z.steps||[]).map((n,i)=>`<div class="st ${i<st?'done':i===st?'on':''}"><i></i>
      <small>${esc(fa(i+1))}. ${esc(n)}</small></div>`).join('');
  const chips=(arr,attr,cur)=> (arr||[]).map(v=>`<button class="chip ${String(cur)===String(v)?'on':''}"
      data-wpick="${attr}" data-wval="${esc(String(v))}">${esc(String(v))}</button>`).join('');
  const kinds=(Z.kinds||[]).map(k=>`<button class="admkind ${w.kind===k.k?'on':''}" data-wkind="${esc(k.k)}">
      ${ico(k.i)}<b>${esc(k.n)}</b></button>`).join('');
  let inner='';
  if(st===0) inner=`<p class="cap">${esc((Z.hints||{}).kind||'')}</p>
    <div class="admkinds">${kinds}</div>
    <label class="stack tight" style="margin-top:var(--sp-3)"><span class="lbl">نام رویداد</span>
      <input class="input" id="wzName" value="${esc(w.name||'')}" placeholder="مثلاً کارگاه روایت اول‌شخص"/></label>`;
  else if(st===1) inner=`<p class="cap">${esc((Z.hints||{}).when||'')}</p>
    <div class="stack"><div><span class="lbl">تاریخ</span><div class="row tight">${chips(Z.dates,'date',w.date)}</div></div>
    <div><span class="lbl">ساعت</span><div class="row tight">${chips(Z.times,'time',w.time)}</div></div>
    <div><span class="lbl">جا</span><div class="row tight">${chips(Z.places,'place',w.place)}</div></div>
    <div><span class="lbl">ظرفیت</span><div class="row tight">${chips(Z.caps,'cap',w.cap)}</div></div></div>`;
  else{
    const kind=(Z.kinds||[]).find(k=>k.k===w.kind)||{n:'رویداد'};
    inner=`<p class="cap">${esc((Z.hints||{}).review||'')}</p>
      <div class="admreview"><b>${esc(w.name||'رویداد بی‌نام')}</b>
        <span class="row">${esc(kind.n)}${w.date?` · ${esc(w.date)}`:''}${w.time?` · ${esc(w.time)}`:''}${w.place?` · ${esc(w.place)}`:''}</span>
        <span class="cap">ظرفیت ${esc(fa(w.cap||0))} نفر</span>
        <div class="admchips"><span class="tag brand">پیش‌نویس می‌ماند تا منتشرش کنی</span>
          <span class="tag">کارت ثبت‌نام آماده می‌شود</span></div></div>`;
  }
  const ready=(st===0&&w.kind&&String(w.name||'').trim())||(st===1&&w.date&&w.time&&w.place)||st===2;
  return `<section class="card stack admwiz">
    <div class="row"><div class="head">${esc((A.wizard||{}).lead||'')}</div><span class="sp"></span>
      <span class="cap">${esc(W.steps||'گام')} ${esc(fa(st+1))} ${esc(W.of||'از')} ${esc(fa(3))}</span></div>
    <div class="admsteps">${steps}</div>
    ${inner}
    <div class="row"><span class="sp"></span>
      ${btn(W.prev||'گام پیش','data-wstep="'+Math.max(0,st-1)+'"'+(st===0?' disabled':''),'i-chev-right')}
      ${st<2?btn(W.next||'گام بعد','data-wstep="'+(st+1)+'" data-wgo="1"'+(ready?'':' disabled'),'i-chev-left')
            :btn('ساخت رویداد','data-wbuild="1" '+(ready?'':' disabled'),'i-check')}</div>
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
      <td>${tag(m.st[0],m.st[1])}</td><td>${esc(m.tags.join('، '))}</td>
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
  const att=(RP.attention||[]).map(a=>rowLink({attrs:`data-rep="${esc(a.k)}"`, i:'i-bell', chev:1, b:esc(a.t), right:tag(W.alert||'توجه','warn')})).join('');
  const list=RPLIST.map(r=>rowLink({attrs:`data-rep="${esc(r.k)}"`, i:r.i, chev:1,
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
      <div class="head">خروجی</div>
      <div class="admlist">
        <a class="admrow2" href="builder.html"><span class="ic">${ico('i-chart')}</span>
          <span class="tx"><b>دیدن نمودار و کارتابل</b><small>همان نه گزارش، با جزئیات پاسخ‌ها</small></span>${ico('i-chev-left','chev')}</a>
        <a class="admrow2" href="account.html"><span class="ic">${ico('i-mobile')}</span>
          <span class="tx"><b>پنل کاربران</b><small>مطالبی که کاربر می‌بیند</small></span>${ico('i-chev-left','chev')}</a>
      </div>
      <p class="cap">${esc('هر گزارش هفت دورهٔ زمانی دارد و با دورهٔ پیش مقایسه می‌شود.')}</p>
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
  const ST=A.settings||{}, g=S.setG||'texts';
  const groups=(ST.groups||[]).map(x=>`<button class="chip ${g===x.k?'on':''}" data-setg="${esc(x.k)}">
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
    const pr=(S.permRole&&roleOf(S.permRole).k===S.permRole)?S.permRole:S.role;
    inner=`<div class="head">${esc(PERMS.title||'')}</div><p class="cap">${esc(PERMS.note||'')}</p>
      <div class="row tight"><span class="cap">${esc(W.role||'نقش من')}: ${esc(roleOf(S.role).n)}</span>
        <button class="chip" data-rolesheet>${ico('i-shield')}${esc(L.roleSwitch)}</button></div>
      <div class="admlist">${ROLES.map(r=>`<button class="admrole ${pr===r.k?'on':''}" data-permrole="${esc(r.k)}">
        <span class="ic">${ico(r.i)}</span><span class="tx"><b>${esc(r.n)}</b><small>${esc(r.s)}</small></span>
        ${r.k===S.role?tag(W.role||'نقش من',''):''}
        <span class="cap">${esc(fa(permsOf(r.k).length))}</span></button>`).join('')}</div>
      <hr class="hr"/>
      <div class="head">${esc('دسترسی‌های '+roleOf(pr).n)}</div>
      ${roleNote(pr)}`;
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
      <span class="cap">${esc(fa((ST.groups||[]).length))} ${esc('گروه')}</span></div>
    <div class="admfilters">${groups}</div>
    <div class="admset">${inner}</div>
  </section>`;
}
function roleNote(pr){
  const mine=permsOf(pr), editable=can('sys_admins');
  const cat=(PERMS.cats||[]).map(c=>{
    const rows=PROWS.filter(p=>p[2]===c);
    return `<div class="admsetgroup"><div class="gh"><span class="ic">${ico('i-shield')}</span>
      <span class="tx"><b>${esc(c)}</b><small>${esc(fa(rows.length))} ${esc('دسترسی')}</small></span></div>
      ${rows.map(p=>{const k=p[0], sup=SUPER.indexOf(k)>-1, on=mine.indexOf(k)>-1;
        /* سوپرادمین همه‌چیز را دارد و بسته نمی‌شود؛ چهار دسترسی ویژه هم
           به نقش دیگری داده نمی‌شود. بقیه تیک‌زدنی است. */
        const locked=!editable||sup||pr==='super';
        return `<div class="admsw"><span class="sp">${esc(p[1])}${sup?` <span class="tag accent">${esc(W.superOnly||'')}</span>`:''}
          ${sup&&pr!=='super'?`<small>${esc('فقط سوپرادمین')}</small>`:''}</span>
          ${locked?`<span class="tag ${on?'ok':''}">${esc(on?(W.yes||'دارد'):(W.no||'ندارد'))}</span>`
                 :`<span class="switch ${on?'on':''}" data-perm="${esc(k)}" role="switch" aria-checked="${on?'true':'false'}" aria-label="${esc(p[1])}"></span>`}</div>`}).join('')}
    </div>`}).join('');
  return `${cat}<p class="cap">${esc(pr==='super'?L.roleAll:editable?L.roleEdit:L.roleView)}</p>`;
}

/* ══ ورقه‌ها ═══════════════════════════════════════════════════════════ */
function sheetEv(id){
  const e=evOf(id); if(!e) return;
  const D=A.events||{}, st=(D.states||{})[e.state]||['',''];
  const tabs=(D.tabs||[]).map(t=>`<button class="chip ${S.evTab===t.k?'on':''}" data-evtab="${esc(t.k)}">${esc(t.n)}</button>`).join('');
  let block='';
  if(S.evTab==='info'){
    block=`<div class="admmatrix"><table><tbody>
      <tr><td>${esc('نوع')}</td><td>${esc(e.kind)}</td></tr>
      <tr><td>${esc('زمان')}</td><td>${esc(e.when)} · ${esc(e.time)}</td></tr>
      <tr><td>${esc('جا')}</td><td>${esc(e.place)}</td></tr>
      <tr><td>${esc('ظرفیت')}</td><td class="num">${esc(fa(e.reg))} ${esc('از')} ${esc(fa(e.cap))}</td></tr>
      <tr><td>${esc('هزینه')}</td><td class="num">${e.price?esc(fa(Number(e.price).toLocaleString('en-US'))+' ریال'):esc('آزاد')}</td></tr>
      <tr><td>${esc('وضعیت')}</td><td>${tag(st[0],st[1])}</td></tr></tbody></table></div>`;
  } else {
    const D2=D[{reg:'regd',att:'attd',money:'moneyd',cert:'certd',news:'newsd'}[S.evTab]]||{};
    block=`<div class="stack tight"><div class="head">${esc(D2.lead||'')}</div>${table(D2.rows||[],D2.cols)}</div>`;
  }
  sheetImpl('shAdm',`<div class="admsheet">
    <div class="row"><div class="tx" style="min-width:0"><div class="head">${esc(e.n)}</div>
      <div class="cap">${esc(e.kind)} · ${esc(e.when)} · ${esc(e.time)}</div></div>
      <span class="sp"></span>${tag(st[0],st[1])}</div>
    <div class="admfilters">${tabs}</div>
    ${block}
    <div class="row tight">${btn('ثبت‌نام‌ها','data-evtab="reg"','i-users')}
      ${btn('اطلاع‌رسانی','data-evtab="news"','i-send')}
      ${btn('گواهی‌ها','data-evtab="cert"','i-medal')}
      <a class="btn sm" href="builder.html">${ico('i-doc')}${esc('کارتابل فرم')}</a></div>
    <div class="row"><span class="sp"></span>${btn(W.close||'بستن','data-close')}</div></div>`);
}
function sheetUser(id){
  const m=memOf(id); if(!m) return;
  sheetImpl('shAdm',`<div class="admsheet">
    <div class="row"><span class="ic" style="width:44px;height:44px;border-radius:14px;display:grid;place-items:center;background:var(--brand-tint);color:var(--brand-ink)">${ico('i-users')}</span>
      <span class="tx" style="min-width:0"><div class="head">${esc(m.n)}</div><div class="cap">${esc(m.code)} · ${esc(fa(m.ph))}</div></span>
      <span class="sp"></span>${tag(m.st[0],m.st[1])}</div>
    <div class="admkpi"><div class="k"><small>رویداد</small><b>${esc(fa(m.ev))}</b></div>
      <div class="k"><small>امتیاز</small><b>${esc(fa(m.pt))}</b></div></div>
    <div class="admchips">${m.tags.map(t=>tag(t,'brand')).join('')}${tag('عضویت '+m.reg,'')}</div>
    ${m.note?`<div class="admtext"><span class="lbl">یادداشت پرونده</span><span>${esc(m.note)}</span></div>`:''}
    <div class="row tight">${btn(W.approve||'تأیید پروفایل','data-uok="'+esc(m.id)+'"','i-check')}
      ${btn(W.block||'مسدود','data-ublock="'+esc(m.id)+'"','i-lock')}
      ${btn(W.note||'یادداشت','data-unote="'+esc(m.id)+'"','i-pen')}
      ${btn(W.tags||'برچسب','data-utags="'+esc(m.id)+'"','i-filter')}</div>
    <div class="admmatrix">${table([['آخرین ورود','امروز ۹:۱۴'],['وضعیت باشگاه',m.tags.indexOf('عضو باشگاه')>-1?'عضو':'عضو نیست'],
      ['فرم‌های پرکرده',fa(2)],['بدهی','۰']])}</div>
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
      <b>${esc(r.v||'')}</b></div>`).join('')}</div>
    <div class="row tight">
      <a class="btn sm" href="builder.html">${ico('i-chart')}${esc('نمودار کامل')}</a>
      ${btn(T.export||'خروجی اکسل','data-rexport','i-download')}
      <span class="sp"></span>${btn(W.close||'بستن','data-close')}</div></div>`);
}
function sheetRole(){
  const list=ROLES.map(r=>`<button class="admrole ${S.role===r.k?'on':''}" data-role="${esc(r.k)}">
    <span class="ic">${ico(r.i)}</span><span class="tx"><b>${esc(r.n)}</b><small>${esc(r.s)}</small></span>
    <span class="cap">${esc(fa(permsOf(r.k).length))}</span></button>`).join('');
  sheetImpl('shAdm',`<div class="admsheet">
    <div class="row"><div class="head">${esc(W.role1||'نقش‌ها')}</div><span class="sp"></span>
      ${btn(W.close||'بستن','data-close')}</div>
    <p class="cap">${esc('هر نقش، چند دسترسی دارد. بخشی که نقش تو اجازه ندارد، قفل باز می‌شود.')}</p>
    <div class="admlist">${list}</div></div>`);
}

/* ══ رندر ══════════════════════════════════════════════════════════════ */
const VIEWS={dash:vDash, newev:vNewev, events:vEvents, users:vUsers, forms:vForms,
  reports:vReports, cert:vCert, settings:vSettings};
function body(){
  const need=GATE[S.sec];
  if(!can(need)) return `<section class="card stack">${emptyBox(W.locked||'')}
    <p class="cap" style="text-align:center">${esc(W.lockedLead||'')}</p>
    <div class="row" style="justify-content:center">${btn('نقش‌ها','data-rolesheet','i-shield')}</div></section>`;
  const v=VIEWS[S.sec];
  return v?v():emptyBox(T.none);
}
function renderBody(){$('#admBody').innerHTML=body()}
function render(){renderNav(); renderBar(); renderBody();
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

  const rs=q('[data-rolesheet]'); if(rs){sheetRole(); return}
  const sec=q('[data-sec]'); if(sec){go(sec.dataset.sec); return}
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
  const pml=q('[data-permrole]'); if(pml){S.permRole=pml.dataset.permrole; save(); renderBody(); return}
  const rl=q('[data-role]'); if(rl){S.role=rl.dataset.role; save(); render();
    toast('نقش: '+roleOf(S.role).n); if($('#shAdm').classList.contains('on')) sheetRole(); return}
  const pm=q('[data-perm]'); if(pm){
    if(!can('sys_admins')){toast(W.locked||''); return}
    const pr=(S.permRole&&roleOf(S.permRole).k===S.permRole)?S.permRole:S.role;
    const mine=permsOf(pr), k=pm.dataset.perm, i=mine.indexOf(k);
    const label=pm.getAttribute('aria-label')||'دسترسی';
    if(i>-1) mine.splice(i,1); else mine.push(k);
    S.perms[pr]=mine.slice(); save(); renderBody();
    toast(label+(i>-1?' برداشته شد':' داده شد')); return}
  const tg=q('[data-tog]'); if(tg){const key=tg.dataset.tog+'|'+tg.dataset.toglabel;
    const cur=togDef(tg.dataset.tog, tg.dataset.toglabel, tg.dataset.togdef==='1');
    const on=!cur; S.toggles[key]=on; save();
    tg.classList.toggle('on',on); tg.setAttribute('aria-checked',on?'true':'false');
    toast((tg.dataset.toglabel||'')+(on?' روشن شد':' خاموش شد')); return}
  const fs=q('[data-formsw]'); if(fs){const i=+fs.dataset.formsw, r=((A.forms||{}).rows||[])[i];
    if(r){r.on=!r.on; toast(r.on?'فرم باز شد':'فرم بسته شد'); renderBody()} return}
  const wk=q('[data-wkind]'); if(wk){S.wiz.kind=wk.dataset.wkind; save(); renderBody(); return}
  const wp=q('[data-wpick]'); if(wp){const key=wp.dataset.wpick, val=wp.dataset.wval;
    S.wiz[key]=key==='cap'?+un(val):val; save(); renderBody(); return}
  const ws=q('[data-wstep]'); if(ws){const step=+ws.dataset.wstep;
    if(ws.dataset.wgo!=='1'){S.wiz.step=step; save(); renderBody(); return}
    const w=S.wiz;
    if(step===1&&!(w.kind&&String(w.name||'').trim())){toast(W.fieldsReq||'این قلم را پر کن'); return}
    if(step===2&&!(w.date&&w.time&&w.place)){toast(W.fieldsReq||'این قلم را پر کن'); return}
    S.wiz.step=step; save(); renderBody(); return}
  const wb=q('[data-wbuild]'); if(wb){const w=S.wiz, kinds=(A.wizard||{}).kinds||[];
    const kind=(kinds.find(k=>k.k===w.kind)||{n:'رویداد'}).n;
    const id='nx'+Date.now();
    S.added=[{id:id, n:w.name||'رویداد بی‌نام', kind:kind, when:w.date||'', time:w.time||'',
      place:w.place||'', cap:+w.cap||0, reg:0, state:'draft', price:0}].concat(S.added||[]);
    S.wiz=Object.assign({},BASE.wiz); S.evF='all'; save();
    toast((A.wizard||{}).made||W.made||'ساخته شد');
    go('events'); return}
  const cpub=q('[data-certpub]'); if(cpub){
    const n=(memList()[0]||{}).n||'';
    S.jobs=[{n:'گواهی '+((A.cert||{}).templates||[]).filter(t=>t.k===S.cert.tpl).map(t=>t.n)[0]||'تازه',
      who:fa(6)+' نفر', way:((A.cert||{}).publish||[]).filter(p=>p.k===S.cert.pub).map(p=>p.n)[0]||'اعلان',
      at:'همین حالا', st:'wait'}].concat(S.jobs||[]);
    save(); renderBody(); toast(W.published||'منتشر شد'); return}
  const uok=q('[data-uok]'); if(uok){const id=uok.dataset.uok;
    S.uov[id]=Object.assign({},S.uov[id],{st:['تأییدشده','ok']}); save();
    toast('پروفایل تأیید شد'); sheetUser(id); renderBody(); return}
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
  if(el.id==='wzName'){S.wiz.name=el.value; save(); return}
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
  render();
})();
})();
