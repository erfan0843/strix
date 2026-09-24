/* ══════════════════════════════════════════════════════════════════════════
   نورا — حساب من
   ──────────────────────────────────────────────────────────────────────────
   یک صفحه، سه چیز:
     ۱) سرِ پروفایل، شبیه صفحهٔ حساب اپلی‌ها: جلد رنگی، نام، نشان وضعیت، سطح،
        امتیاز و نوار تکمیل اطلاعات
     ۲) کارت نورا پی با رنگ و نشان خودش (فاز بعد)
     ۳) میان‌بُرها، رویداد نزدیک و سه ردیف: رویدادهای من، پروفایل من و
        باشگاه کتاب‌خوانی (باشگاه هم زیر پروفایل من باز می‌شود)

   پشتیبانی بخش نیست؛ نواری است که به نوار پایین چسبیده و از پایین باز می‌شود.
   مهمان یک کارت ورود روشن می‌بیند و روی هر ردیف که بزند، بعد از ورود همان
   بخش باز می‌شود.
   ══════════════════════════════════════════════════════════════════════════ */
(function(){
'use strict';

/* ── دادهٔ همین صفحه ─────────────────────────────────────────────── */
const N=window.NORA||{}, A=N.ACCOUNT||{}, POL=A.policy||{}, SUP=A.support||{};
const SECT=A.sections||[], PAY=SECT.find(s=>s.card)||null, ROWS=SECT.filter(s=>!s.card);
const EVENTS=N.EVENTS||[], PAST=N.PAST||[], FAQ=N.FAQ||[], CERTS=N.CERTS||{}, ARCHIVE=N.ARCHIVE||{};
const FIELDS=A.fields||[], FLOW=A.flow||[], LEVELS=A.levels||[], ACH=A.achievements||[], STORE=A.rewardStore||[];
const MON=A.months||{sh:'شهریور'};
const TRUST=N.TRUST||{}, TRUST_ROWS=TRUST.row||[];
const PF=A.profileForm||{}, DELFLOW=A.deleteFlow||{};
const MY=A.myEvents||{}, MY_UP=MY.up||[], MY_PAST=MY.past||[];
const myUp=()=>EVENTS.filter(e=>MY_UP.indexOf(e.id)>-1);
const myPast=()=>PAST.filter(e=>MY_PAST.indexOf(e.id)>-1);
/* شمارش روز و ساعت و دقیقه تا شروع رویداد؛ از ساعت خودِ دستگاه */
function untilTxt(e){
  const d=+String(e.dn||'').replace(/\D/g,'')||0; return d?faN(d)+' روز':'به‌زودی';
}
function cdParts(e){
  /* روز و ساعت و دقیقهٔ مانده؛ در پیش‌نمایش از شمارهٔ روز خود داده می‌آید */
  const days=+String(e.dn||'').replace(/\D/g,'')||0;
  const mins=((days*24+7)*60)+37;
  return {d:Math.floor(mins/1440), h:Math.floor(mins%1440/60), m:mins%60};
}
function cdLine(e){
  const t=cdParts(e);
  return `<span class="cdline">${ico('i-clock')}
    <b>${faN(t.d)}</b> روز و <b>${faN(t.h)}</b> ساعت و <b>${faN(t.m)}</b> دقیقه تا برگزاری</span>`;
}
/* هر پارامتر فرم پروفایل، یک خط از پروفایل تو می‌شود؛ عکس هم پارامتر است */
const PHOTO_SEED=['people/p5.svg','people/p2.svg','people/p7.svg'];
/* یک جملهٔ اطمینان، کوتاه: برای هر بخش از همین‌ها خوانده می‌شود */
function trustOf(w){
  const r=TRUST_ROWS.find(x=>String(x[0]).indexOf(w)>-1);
  return r?r[1]:'';
}
function trustLine(kind){
  const S2=TRUST.short||{};
  const t=(kind&&S2[kind])||trustOf('رمزنگاری اطلاعات')||'اطلاعاتت رمزنگاری‌شده است.';
  const head=(TRUST.head||'اطلاعاتت ایمن است');
  return `<p class="trustline" data-trust="${esc(kind||'secure')}" title="${esc(head)}">
    <svg class="i" aria-hidden="true"><use href="#i-shield"/></svg><span>${esc(t)}</span></p>`;
}
function trustCard(){
  return `<div class="trustcard anim">${ico('i-shield')}
    <span class="tx"><b>${esc(TRUST.head||'اطلاعاتت ایمن است')}</b>
      <small>${esc(trustOf('رمزنگاری گذرگاه')||'')}</small></span>
    <button class="btn sm quiet" data-trust-more>بیشتر</button></div>`;
}

/* ── کمکی‌ها ─────────────────────────────────────────────────────── */
const $=s=>document.querySelector(s);
const esc=t=>String(t==null?'':t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const faN=n=>String(n==null?'':n).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
const unFa=s=>String(s==null?'':s).replace(/[۰-۹]/g,d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/[٠-٩]/g,d=>'٠١٢٣٤٥٦٧٨٩'.indexOf(d));
const faNum=n=>faN(String(Math.round(+n||0)).replace(/\B(?=(\d{3})+(?!\d))/g,'٬'));
const faD=n=>faN(n);
const UI=()=>window.NORA_UI||{};
const uid=()=>UI().uid?UI().uid():'';
const login=()=>!!uid();
const sess=()=>UI().sessUser?UI().sessUser():{};
const prof=()=>UI().profile?UI().profile():{};
const phone=()=>UI().phoneOf?UI().phoneOf():'';
const pctOf=p=>UI().profilePercent?UI().profilePercent(p,!!phone()):0;
const missOf=p=>UI().profileMissing?UI().profileMissing(p,!!phone()):[];
const lvl=()=>UI().levelOf?UI().levelOf(+A.points||0):{cur:{},next:null};
const chip=(t,c)=>`<span class="tag ${c||''}">${esc(t)}</span>`;
const ico=(i,st)=>`<svg class="i" aria-hidden="true"${st?` style="${st}"`:''}><use href="#${i}"/></svg>`;
const card=(t,s,a,b)=>{
  const isIco=typeof a==='string'&&/^i-[a-z0-9-]+$/.test(a);
  const ic=isIco?a:'', body=isIco?b:a;
  return `<div class="card acct anim">${t?`<div class="head">${ic?ico(ic):''}${esc(t)}</div>`:''}${s?`<div class="cap" style="margin-top:5px">${esc(s)}</div>`:''}${body||''}</div>`};
const note=(t,i)=>`<p class="note">${ico(i||'i-sparkle')}<span>${esc(t)}</span></p>`;
const empty2=(t,s,i)=>`<div class="empty2">${ico(i||'i-archive')}<b>${esc(t)}</b><span>${esc(s)}</span></div>`;
const stOf=p=>({draft:['تکمیل نشده','warn'],pending:['در صف تأیید','brand'],
  approved:['تأیید شده','ok'],rejected:['رد شده','stop']})[ (p&&p.status)||'draft' ]||['تکمیل نشده','warn'];
const monOf=e=>(e&&e.dm&&MON[e.dm])||'';

/* ── حالت صفحه ───────────────────────────────────────────────────── */
const S={view:'',vtab:'up',ptab:'info',edit:false,errs:{},after:''};

/* ── رفتن به یک بخش: مهمان، ورقهٔ ورود؛ عضو، همان بخش ─────────────── */
function go(k){
  if(k==='support'){ goSupport(); return }
  if(!login()){ S.after=k; loginSheet(); return }
  location.hash='#'+k;
}
/* ورود، صفحهٔ خودش را دارد: login.html؛ بعد از ورود همین‌جا برمی‌گردد */
function goLogin(after){ location.href='login.html?next='+encodeURIComponent('account.html'+(after?'#'+after:'')) }
function loginSheet(){ const k=S.after; S.after=''; goLogin(k) }

/* ══ سرِ پروفایل ═════════════════════════════════════════════════════ */
function headGuest(){
  const SUPI=SUP.i||'i-headphone';
  return `<div class="card acct anim guestcard">
      <span class="gmark" aria-hidden="true">${ico('i-idcard-f')}</span>
      <div class="head">خوش آمدی</div>
      <p class="sub" style="margin:7px 0 0">اطلاعات حساب، رویدادها، بلیت و گواهی و امتیازت، همه مالِ
        حساب خودت است. با شمارهٔ موبایل و کد یک‌بارمصرف وارد شو؛ رمزی ندارد.</p>
      <div class="gl">
        <div class="row">${ico('i-check')}<span>بلیت و کارت ورود هر رویداد</span></div>
        <div class="row">${ico('i-check')}<span>گواهی و کارنامهٔ حضور</span></div>
        <div class="row">${ico('i-check')}<span>امتیاز، باشگاه کتاب و فرم‌ها</span></div>
      </div>
      <button class="btn primary" data-login>${ico('i-mobile')} ورود با شمارهٔ موبایل</button>
      <button class="btn quiet sm demo" type="button" data-demo>${ico('i-eye')} نمای نمونهٔ حساب را ببین</button>
      <p class="cap" style="margin:11px 2px 0">شماره را که بنویسی، به بله یا ایتا تحویل می‌شود و کد را از همان
        پیام می‌گیری. رمز و گذرواژه‌ای در کار نیست.</p>
      <p class="cap" style="margin:6px 2px 0">${esc(SUP.n||'پشتیبانی')} و راهنما هم صفحهٔ خودش را دارد و بدون ورود باز
        می‌شود؛ نشانش هم کنار اعلان‌ها بالای صفحه است.</p>
    </div>`;
}
function headMember(){
  const p=prof(), u=sess(), pc=pctOf(p), miss=missOf(p), st=stOf(p);
  const {cur,next}=lvl(), pts=+A.points||0;
  const name=p.fullName||u.name||'کاربر نورا';
  const initial=String(name).trim().slice(0,1)||'ن';
  const missTxt=miss.length?faN(miss.length)+' قلم مانده: '+miss.slice(0,2).map(f=>f.l).join('، '):'اطلاعات کامل است';
  return `<div class="phead anim">
      <div class="cover"><span class="blob b1" aria-hidden="true"></span>
        <span class="ctags">${chip(st[0],st[1])}${chip(faNum(pts)+' امتیاز')}</span></div>
      <div class="pbody">
        <div class="ptop">
          <span class="av">${p.photo?`<img src="${esc(p.photo)}" alt=""/>`:esc(initial)}<i class="pdot" aria-hidden="true"></i></span>
          <span class="who"><b>${esc(name)}</b>
            <small>${phone()?faN(phone())+' · ':''}عضو از ${esc(u.joined||A.joined||'۱۴۰۴')}</small>
            <span class="pmeta">${chip('سطح '+(cur.n||'—'))}${next?chip(faN(next.at-pts)+' تا '+next.n):chip('بالاترین سطح','ok')}</span></span>
          <button class="icon-btn edit" data-go="account" aria-label="ویرایش اطلاعات حساب">${ico('i-pen')}</button>
        </div>
        <div class="pstats">
          <button class="pstat" data-go="club"><b>${faNum(pts)}</b><small>امتیاز باشگاه</small></button>
          <button class="pstat" data-go="club"><b>${next?faNum(next.at-pts):'—'}</b><small>${next?'تا '+esc(next.n):'بالاترین سطح'}</small></button>
          <button class="pstat" data-go="events"><b>${faN(EVENTS.length)}</b><small>برنامهٔ پیش‌رو</small></button>
        </div>
        <div class="pfoot">
          <span class="meter" role="img" aria-label="اطلاعات حساب ٪${faN(pc)} کامل است"><i style="width:${pc}%"></i></span>
          <span class="cap">اطلاعات حساب: ٪${faN(pc)} کامل · ${esc(missTxt)}</span>
        </div>
        <div class="pacts">
          <button class="btn sm ${miss.length?'primary':'quiet'}" data-go="account">
            ${ico(miss.length?'i-pen':'i-check')} ${miss.length?'تکمیل اطلاعات':'ویرایش اطلاعات'}</button>
          <button class="btn sm quiet" data-ptab-go="auth">${ico('i-lock')} ورود و امنیت</button>
        </div>
      </div></div>`;
}

/* ══ نورا پی: کارت خودش، سرِ صفحه و جدا از ردیف‌ها ═══════════════════ */
function payBox(){
  const su=sess()||{};
  const bal=faNum(su.wallet||A.wallet||0);
  const tags=(PAY&&PAY.tags||['کیف پول','شارژ','صورت‌حساب']).slice(0,3);
  return `<div class="paybar anim" style="--i:1">
      <button class="pbmain" type="button" data-view="pay" aria-label="نورا پی">
        <span class="pwal" aria-hidden="true">${ico('i-wallet')}</span>
        <span class="ptx"><small>نورا پی · کیف پول</small>
          <b>${login()?bal+' تومان':'وارد شو و موجودی‌ات را ببین'}</b>
          <span class="pmeta">${tags.map(x=>chip(x)).join('')}</span></span>
        <svg class="i chev" aria-hidden="true"><use href="#i-chev-left"/></svg>
      </button>
      <div class="pbrow">
        <button class="pbtn" type="button" data-view="pay">${ico('i-plus')} شارژ</button>
        <button class="pbtn" type="button" data-view="pay">${ico('i-doc')} صورت‌حساب</button>
        <button class="pbtn" type="button" data-view="pay">${ico('i-split')} اقساط</button>
      </div>
      ${trustLine('pay')}
    </div>`;
}

/* ══ کارت رویداد نزدیک ═══════════════════════════════════════════════ */
function nextBox(){
  if(!login()||!EVENTS.length) return '';
  const e=EVENTS[0];
  return `<div class="qcard anim" style="--i:2">
      <span class="qc-date"><b>${faD(e.dn||'')}</b><small>${esc(monOf(e))}</small></span>
      <span class="qc-tx"><b>${esc(e.t)}</b>
        <span class="qmeta">${ico('i-clock')} ${esc(e.time||'')} ${ico('i-pin')} ${esc(e.place||'')}</span>
        <span class="qmeta">${ico('i-qr')} کارت ورودت آماده است</span></span>
      <button class="qc-go" data-ticket="${esc(e.id)}">کارت ورود</button>
    </div>`;
}

/* ══ ردیف‌های بخش‌ها ═════════════════════════════════════════════════ */
function subOf(k){
  const p=prof(), {cur}=lvl(), pts=+A.points||0;
  if(k==='events'){
    if(!login()) return EVENTS.length?faN(EVENTS.length)+' برنامهٔ پیش‌رو و '+faN(PAST.length)+' برگزارشده':'';
    return faN(EVENTS.length)+' ثبت‌نام · بلیت، گواهی و کارنامه';
  }
  if(k==='profile'){
    if(!login()) return (ROWS.find(r=>r.k===k)||{}).s||'';
    return 'اطلاعات ٪'+faN(pctOf(p))+' · ورود و امنیت · امتیاز و سطح';
  }
  if(k==='club'){
    if(!login()) return (ROWS.find(r=>r.k===k)||{}).s||'';
    return 'سطح '+(cur.n||'—')+' · '+faNum(pts)+' امتیاز · دعوت دوستان';
  }
  if(k==='book'){
    const C=N.CLUB||{}, bc=bookState();
    if(!login()) return (ROWS.find(r=>r.k===k)||{}).s||'';
    return 'کتاب ماه: '+esc(C.book||'—')+(bc.pages?' · '+faN(bc.pages)+' صفحه خوانده‌ای':'');
  }
  return (ROWS.find(r=>r.k===k)||{}).s||'';
}
function miniOf(k){
  if(!login()) return '';
  if(k==='events') return faN(EVENTS.length)+' مورد';
  if(k==='profile') return '٪'+faN(pctOf(prof()));
  if(k==='book') return login()?(N.CLUB&&N.CLUB.term?'ترم '+esc(N.CLUB.term):'عضو باشگاه'):'';
  return '';
}
function rowsBox(){
  return `<div class="mrows anim" style="--i:3">
      <div class="mhead">${ico('i-layers')}<b>بخش‌های من</b><span class="sp" style="flex:1"></span>
        <span class="cap">${faN(ROWS.length)} بخش</span></div>
      ${ROWS.map(r=>`<button class="mrow2" data-view="${r.k}">
      <span class="ic">${ico(r.i)}</span>
      <span class="tx"><b>${esc(r.n)}</b><small>${esc(subOf(r.k)||r.s)}</small></span>
      ${miniOf(r.k)?`<span class="mini">${ico('i-check')}${miniOf(r.k)}</span>`:''}
      <svg class="i chev" aria-hidden="true"><use href="#i-chev-left"/></svg>
      </button>`).join('')}</div>`;
}
/* ══ صفحهٔ پروفایل: سر، میان‌بُرها، رویداد نزدیک و چهار بخش ══════════ */
function profileHTML(){
  return (login()?headMember():headGuest())+payBox()+nextBox()+rowsBox();
}
function renderProfile(){
  const box=$('#profBox'); if(!box) return;
  box.innerHTML=profileHTML();
}

/* ══ سرِ هر نما ══════════════════════════════════════════════════════ */
function viewHead(t,sub,tabs,key){
  key=key||'vtab'; const cur=S[key];
  return `<div class="vhead"><div class="vrow"><button class="vback" data-back aria-label="بازگشت به حساب من">
      ${ico('i-chev-right')}</button>
      <span class="vh2">${esc(t.n)}</span></div>
    <p class="vhsub">${esc(sub||t.s||'')}</p>
    ${tabs?`<div class="vtabs" role="tablist" aria-label="بخش‌های ${esc(t.n)}">${tabs.map(t2=>`<button class="vtab${cur===t2.k?' on':''}" role="tab"
      aria-selected="${cur===t2.k}" tabindex="${cur===t2.k?'0':'-1'}" data-${key}="${t2.k}">
      ${t2.i?ico(t2.i):''} ${esc(t2.n)}</button>`).join('')}</div>`:''}`;
}
const gate=t=>`<div class="card acct gate">${ico('i-lock')}
  <div class="head">این بخش با حساب خودت باز می‌شود</div>
  <div class="cap">«${esc(t.n)}» مالِ حساب خودت است؛ با شمارهٔ موبایل و کد یک‌بارمصرف وارد شو.</div>
  <div class="gacts"><button class="btn primary" data-login>${ico('i-mobile')} ورود با شمارهٔ موبایل</button>
    <button class="btn quiet" data-go="support">پشتیبانی، بدون ورود</button></div></div>`;

/* ══ رویدادهای من ═══════════════════════════════════════════════════ */
const VTABS=[{k:'up',n:'پیش‌رو'},{k:'past',n:'برگزارشده'},{k:'tickets',n:'بلیت و گواهی'},
             {k:'attend',n:'کارنامهٔ حضور'},{k:'reviews',n:'نظرهای من'}];
function evRow(e){
  return `<div class="erow">
    <span class="when"><b>${faD(e.dn||'')}</b><small>${esc(monOf(e))}</small></span>
    <span class="tx"><b>${esc(e.t)}</b><small>${ico('i-clock')} ${esc([e.when,e.time,e.place].filter(Boolean).join(' · '))}</small>
      ${cdLine(e)}
      <span class="bt">
        <a class="btn sm quiet" href="event.html?id=${esc(e.id)}">${ico('i-chev-left')} صفحهٔ رویداد</a>
        <button class="btn sm quiet" data-ticket="${esc(e.id)}">${ico('i-qr')} کارت ورود</button>
        <button class="btn sm quiet" data-cancel="${esc(e.id)}">لغو</button></span></span></div>`;
}
function pastRowMine(h){
  return `<div class="erow">
    <span class="when"><b>${faD(h.dn||'')}</b><small>${esc(monOf(h))}</small></span>
    <span class="tx"><b>${esc(h.t)}</b><small>${ico('i-archive')} ${esc(h.d||'')} · ${faN(h.mediaCount||0)} رسانه</small>
      <span class="bt">
        <a class="btn sm quiet" href="event.html?id=${esc(h.id)}">${ico('i-play')} ضبط و رسانه‌ها</a>
        <button class="btn sm quiet" data-dl-cert="${esc((CERTS&&Object.keys(CERTS)[0])||'NL-T4K7M9X')}">${ico('i-medal')} گواهی</button>
      </span></span></div>`;
}
function pastRow(h){
  return `<div class="erow past">
    <span class="when"><b>${faD(h.dn||'')}</b><small>${esc(monOf(h))}</small></span>
    <span class="tx"><b>${esc(h.t)}</b><small>${ico('i-play-f')} ${esc(h.d)} · ${esc(h.rec||'')}</small>
      <span class="bt">
        <button class="btn sm quiet" data-open-past="${esc(h.id)}">${ico('i-play-f')} ضبط و جزوه</button>
        ${h.cert?`<button class="btn sm quiet" data-cert="${esc(h.id)}">${ico('i-medal')} گواهی</button>`:''}</span></span></div>`;
}
function panelUp(){
  const mine=myUp();
  if(!mine.length) return card('پیش‌روی من',MY.lead||'',empty2('هنوز ثبت‌نامی نداری',MY.empty||''))+
    note('فهرست همهٔ رویدادها صفحهٔ خودش را دارد؛ این‌جا فقط مالِ خودت است.','i-calendar');
  return card('پیش‌روی من',faN(mine.length)+' رویداد ثبت‌نام‌شده — '+esc(MY.lead||''),'i-calendar',
    mine.map(evRow).join(''))+
    note(MY.inEvent||'هر جزئیاتی در صفحهٔ خودِ رویداد است.','i-layers')+
    trustLine('secure');
}
function panelPast(){
  const mine=myPast();
  if(!mine.length) return card('برگزارشده‌ها','',empty2('هنوز رویداد برگزارشده‌ای نداری','بعد از هر رویداد، ضبط و گواهی همین‌جا می‌آید.'));
  return card('برگزارشده‌های من',faN(mine.length)+' رویداد؛ ضبط، رسانه و گواهی','i-archive',
    mine.map(pastRowMine).join(''))+
    note('هر رویداد، صفحهٔ خودش را دارد: ضبط، رسانه، گواهی و کارنامهٔ حضور همان‌جا است.','i-archive');
}
function panelTickets(){
  const p=prof(), u=sess(), mine=myUp();
  const certKey=(CERTS&&Object.keys(CERTS)[0])||'NL-T4K7M9X', test=CERTS[certKey]||{};
  const ticketRow=e=>{
    const code=String(e.id||'e1').toUpperCase()+'‑'+faN(4567);
    return `<div class="tk">${ico('i-qr','width:19px;height:19px;color:var(--brand)')}
      <span><b>${esc(e.t)}</b><small>${esc(e.when||'')} · ${esc(e.place||'')} · کد ورود ${esc(code)}</small>
        <span class="acts">${chip('بلیت فعال','ok')}
          <button class="btn sm quiet" data-dl-ticket="${esc(e.id)}">${ico('i-download')} دانلود بلیت</button>
          <button class="btn sm quiet" data-ticket="${esc(e.id)}">${ico('i-qr')} کارت ورود</button></span></span></div>`;
  };
  const certRow=`<div class="tk">${ico('i-medal','width:19px;height:19px;color:var(--brand)')}
        <span><b>${esc(test.c||'کارگاه عکاسی مقدماتی')}</b>
          <small>صادر ${esc(test.d||'۲۱ شهریور ۱۴۰۵')} · ${esc(test.h||'۲۴ ساعت')} · سریال ${esc(certKey)}</small>
          <span class="acts">${chip('آمادهٔ دانلود','ok')}
            <button class="btn sm quiet" data-dl-cert="${esc(certKey)}">${ico('i-send')} دانلود</button>
            <button class="btn sm quiet" data-verify="${esc(certKey)}">استعلام</button></span></span></div>`;
  const kinds=(POL.certKinds||[]).map(k=>{
    const b=k.k==='free'?'دریافت':'سفارش', cls=k.k==='free'?'quiet':'primary';
    return `<div class="kind">${ico('i-doc','width:19px;height:19px;color:var(--ink-4)')}
        <span class="tx"><b>${esc(k.n)}</b><small>${esc(k.s)}</small></span>
        <button class="btn sm ${cls}" data-certreq="${esc(k.k)}">${b}</button></div>`;
  }).join('');
  const certNote=note((POL.certNote||'شرط صدور هر رویداد جداست')+' · اعتبار پیش‌فرض هر گواهی '+
        faN(POL.certValidMonths||24)+' ماه است.','i-shield');
  return `<div class="idcard anim">
      <div class="idcover">${ico('i-idcard-f')}
        <b>${esc(p.fullName||u.name||'کاربر نورا')}</b>
        <small>کارت عضویت نورا · عضو از ${esc(u.joined||A.joined||'۱۴۰۴')}</small>
        <div class="bktags" style="display:flex;gap:6px;margin-top:9px">${chip('فعال','ok')}</div>
      </div>
      <div class="idbody">
        <div class="stat2">
          <span><b>NL-4567</b><small>کد عضویت</small></span>
          <span><b>${faN(mine.length)}</b><small>بلیت فعال</small></span>
        </div>
        <div class="brandline"><span class="mark" aria-hidden="true"></span> این کارت را در ورودی نشان بده</div>
      </div></div>
    ${card('بلیت‌های من','هر بلیت مالِ خودِ همان رویداد است؛ جزئیاتش در صفحهٔ آن رویداد','i-ticket',
      mine.length?mine.map(ticketRow).join(''):empty2('بلیتی نداری','از صفحهٔ رویدادها یکی را ثبت‌نام کن.'))}
    ${card('گواهی‌های من','هر گواهی سریال خودش را دارد؛ با همان می‌شود استعلام گرفت','i-medal',certRow)}
    ${card('گونه‌های گواهی','در نورا چهار گونه گواهی داریم','i-doc',`<div class="kinds">${kinds}</div>`+certNote)}
    ${trustLine('secure')}`;
}
function panelAttend(){
  const score=A.score||{}, months=[40,62,55,78,66,84,72,90,60,74,88,96];
  const sess5=[{d:'امروز شنبه',t:'حلقهٔ مطالعهٔ ادبیات',s:'حاضر'},{d:'شنبهٔ پیش',t:'جلسهٔ شعر و موسیقی',s:'حاضر'},
    {d:'۲۹ شهریور',t:'کارگاه عکاسی در طبیعت',s:'غایب'},{d:'۲۶ شهریور',t:'نشست مالی خانواده',s:'حاضر'},
    {d:'۲۱ شهریور',t:'کارگاه فن بیان',s:'حاضر'}];
  const mons=['فرو','ارد','خرد','تیر','مرد','شهر','مهر','آبا','آذر','دی','بهم','اسف'];
  return card('کارنامهٔ حضور من','حضور، غیبت و ساعت‌هایی که با نورا بودی','i-chart',
      `<div class="stat2">
        ${[['٪'+faN(score.attend||88),'نرخ حضور'],['۱۱','برنامهٔ پیش‌رو امسال'],
           [faN(ARCHIVE.hours||0),'ساعت کارگاه'],['٪'+faN(score.growth?Math.min(100,Math.round(score.growth/2)):90),'پیشرفت امسال']]
          .map(([v,l])=>`<span><b>${v}</b><small>${esc(l)}</small></span>`).join('')}</div>
      <div class="bars" role="img" aria-label="حضور دوازده ماه گذشته">
        ${months.map((v,i)=>`<span class="bar${i===2||i===4?' off':''}"><span class="bcol"><i class="bfill" style="height:${Math.max(8,Math.round(v*0.86))}%"></i></span><small>${esc(mons[i])}</small></span>`).join('')}</div>
      <div class="barscap"><span class="cap">دوازده ماه گذشته</span><span class="sp" style="flex:1"></span>
        <span class="cap">کم‌رنگ‌ها ماه‌های کم‌حضور</span></div>`)+
    card('جلسه‌های آخر',faN(sess5.length)+' جلسهٔ گذشته','i-clock',
      sess5.map(x=>`<div class="tk">${ico('i-calendar','width:19px;height:19px;color:var(--ink-4)')}
        <span><b>${esc(x.t)}</b><small>${esc(x.d)} · حضور و غیاب جلسه</small></span>
        ${chip(x.s,x.s==='حاضر'?'ok':'stop')}</div>`).join(''));
}
function panelReviews(){
  const R=[{e:'کارگاه فن بیان، ترم تیر',r:5,d:'۲۹ تیر',q:'تمرین‌های هفتگی باعث شد بالاخره جلوی جمع حرف بزنم.'},
           {e:'نشست مالی خانواده',r:4,d:'۱۲ تیر',q:'مثال‌های واقعی خوب بود؛ کاش یک جلسهٔ بیشتر داشت.'},
           {e:'حلقهٔ مطالعهٔ ادبیات',r:5,d:'۵ تیر',q:'یادداشت سرپرست باشگاه هر جلسه ارزشش را دارد.'}];
  return card('نظرهای من',faN(R.length)+' نظر نوشته‌ای؛ ممنون که راه را برای بقیه روشن می‌کنی','i-star',
      R.map(x=>`<div class="tk">${ico('i-star','width:19px;height:19px;color:#C9A96A')}
        <span><b>${esc(x.e)}</b><small>${esc(x.d)} · ${'★'.repeat(x.r)}</small>
          <p class="sub" style="margin:4px 0 0">${esc(x.q)}</p>
          <span class="acts"><button class="btn sm quiet" data-edit-review="${esc(x.e)}">ویرایش</button></span></span></div>`).join(''))+
    card('نظر تازه','بعد از هر رویداد می‌توانی امتیاز بدهی','i-pen',
      `<button class="btn primary" data-go="events">${ico('i-pen')} نوشتن نظر برای رویداد آخر</button>`);
}
const VS={};
VS.events=function(t){
  if(!login()) return viewHead(t,'',VTABS)+gate(t);
  const body={up:panelUp,past:panelPast,tickets:panelTickets,attend:panelAttend,reviews:panelReviews}[S.vtab];
  return viewHead(t,(VTABS.find(x=>x.k===S.vtab)||{}).n||'',VTABS)+(body?body():'');
};

/* ══ باشگاه و امتیاز من ═════════════════════════════════════════════ */
function invitePanel(){
  const code='NORA-4567', need=+POL.inviteNeed||2, done=1;
  return card('دعوت دوستان','هر دوست که با کد تو بیاید، هر دو امتیاز می‌گیرید','i-users',
    `<div class="srow">${ico('i-send')}
      <span class="sp">کد دعوت تو<b class="num" style="display:block;font-size:15px;margin-top:3px">${esc(code)}</b></span>
      <button class="btn sm quiet" data-copy="${esc(code)}">کپی</button></div>
     <div class="srow">${ico('i-users')}
      <span class="sp">تا حالا ${faN(done)} دوست آمده · ${faN(Math.max(0,need-done))} تا مانده به پاداش</span>
      <button class="btn sm quiet" data-invite>دعوت با پیوند</button></div>`);
}
function clubTab(){
  const pts=+A.points||0, {cur,next}=lvl(), cap=POL.pointsCap||{};
  return card('امتیاز و سطح من','هر ثبت‌نام، حضور و فرم امتیاز دارد','i-medal',
      `<div class="stat2">
        ${[['امتیاز من',faNum(pts)],['سطح',(cur.n||'—')],
           ['تا سطح بعدی',next?faNum(next.at-pts):'—'],['رتبه',faN((A.score||{}).rank||0)+' از '+faN((A.score||{}).of||0)]]
          .map(([l,v])=>`<span><b>${esc(v)}</b><small>${esc(l)}</small></span>`).join('')}</div>
      <div class="ladder">${LEVELS.map(l=>`<div class="lvrow ${l.k===cur.k?'cur':''}">
        <span class="gs">${ico('i-medal')}</span><span class="tx"><b>${esc(l.n)}</b><small>${esc(l.perks)}</small></span>
        <span class="lc">${faNum(l.at)} امتیاز</span></div>`).join('')}</div>
      ${note('سقف‌های محافظ: هر کار تا '+faN(cap.each||100)+'، روزانه تا '+faN(cap.day||50)+
        ' و ماهانه تا '+faN(cap.month||300)+' امتیاز.','i-shield')}`)+
    card('دستاوردها','هر قفل، یک کار می‌خواهد','i-medal',
      `<div class="kinds">${ACH.map(a=>`<div class="kind" style="${a.on?'':'opacity:.62'}">
        ${ico(a.i,'width:19px;height:19px;color:'+(a.on?'var(--accent-ink)':'var(--ink-4)'))}
        <span class="tx"><b>${esc(a.n)}</b><small>${a.on?esc(a.r||'گرفته‌ای'):faNum(a.at)+' امتیاز'}</small></span>
        ${a.on?chip('باز شد','ok'):chip('قفل','')}</div>`).join('')}</div>`)+
    card('فروشگاه پاداش','امتیازت را خرج کن','i-wallet',
      `<div class="kinds">${STORE.map(r=>{const can=pts>=r.cost; return `<div class="kind">
        ${ico('i-wallet','width:19px;height:19px;color:var(--ink-4)')}
        <span class="tx"><b>${esc(r.n)}</b><small>${esc(r.s)}</small></span>
        <button class="btn sm ${can?'primary':'quiet'}" ${can?'':'disabled'} data-reward="${esc(r.n)}">${faNum(r.cost)} امتیاز</button></div>`}).join('')}</div>`)+
    invitePanel();
}

/* ══ باشگاه کتاب‌خوانی خط زندگی ══════════════════════════════════════ */
const BC_KEY='nora-home-bookclub';
function bookState(){
  let v=null; try{v=JSON.parse(localStorage.getItem(BC_KEY)||'null')}catch(e){v=null}
  return Object.assign({joined:true,seat:false,pages:0,note:'',vote:''},v||{});
}
function bookSet(patch){ const v=Object.assign(bookState(),patch); try{localStorage.setItem(BC_KEY,JSON.stringify(v))}catch(e){} return v }
function bookPanel(){
  const C=N.CLUB||{}, bc=bookState(), sup=(N.PEOPLE||[]).find(p=>p.id===C.sup)||{};
  const pct=Math.max(0,Math.min(100,+C.progress||0)), plan=C.plan||[], shelf=C.shelf||[], log=C.log||[];
  const vote=bc.vote, VOTE=C.vote||[], tot=VOTE.reduce((a,b)=>a+(+b.n||0),0)+(vote?1:0);
  const mine=Math.round(Math.min(200,+bc.pages||0)/200*100);
  const hero=`<div class="bkhero anim">
      <div class="bkcover">
        ${ico('i-book','')}
        <span class="bkkind">کتاب ماه باشگاه خط زندگی · ${esc(C.term||'')}</span>
        <b>${esc(C.book||'')}</b>
        <small>${esc(C.bookBy||'')} · ${esc(C.session||'')}</small>
        <span class="bktags">${chip(faN(C.members||0)+' عضو')}${chip(faN(C.meetings||0)+' جلسه')}${chip(bc.joined?'عضو این ترم':'عضو نیستی',bc.joined?'ok':'warn')}</span>
        <div class="bkbar" role="img" aria-label="پیشرفت کتاب ماه ٪${faN(pct)}"><i style="width:${pct}%"></i></div>
        <div class="bkfoot">${ico('i-clock')} ٪${faN(pct)} خوانده شده · جلسهٔ بعد: ${esc(C.next||'جلسهٔ پیش‌رو')}</div>
      </div>
      <div class="bkbody">
        <div class="bkstats">
          ${[['اعضا',faN(C.members||0)+' از '+faN(C.cap||0)],['جلسه‌ها',faN(C.meetings||0)],
             ['صفحهٔ من',faN(bc.pages||0)],['قفسه',faN(shelf.length)]]
            .map(([l,v])=>`<span><b>${esc(v)}</b><small>${esc(l)}</small></span>`).join('')}
        </div>
        <div class="cap">${bc.joined?'عضویتت در ترم جاری فعال است؛ جلسه‌ها پنجشنبه‌ها ۱۸:۰۰ برپا می‌شود.':'عضو ترم نیستی؛ با یک پیام به سرپرست، جایت را رزرو کن.'}</div>
      </div></div>`;
  const tasks=`<div class="bktasks anim" style="--i:1">
      <div class="bktask ${bc.seat?'done':''}"><span class="bx">${ico('i-check')}</span>
        <span class="tx"><b>صندلی جلسهٔ پنجشنبه</b><small>${bc.seat?'رزرو شد؛ یک ساعت قبل یادآوری می‌کنیم':'جای محدود؛ از همین‌جا رزرو کن'}</small></span>
        ${bc.seat?chip('رزرو شد','ok'):`<button class="btn sm primary" data-seat>رزرو صندلی</button>`}</div>
      <div class="bktask ${bc.pages>=10?'done':''}"><span class="bx">${ico('i-check')}</span>
        <span class="tx"><b>ثبت پیشرفت مطالعه</b><small>${bc.pages?faN(bc.pages)+' صفحه از ۲۰۰ ثبت شده':'صفحه‌هایی که خوانده‌ای را خودت ثبت کن'}</small></span>
        <span class="bt" style="display:flex;gap:6px"><button class="btn sm quiet" data-pages="10">+۱۰</button>
          <button class="btn sm quiet" data-pages="25">+۲۵</button></span></div>
      <div class="bktask ${bc.note?'done':''}"><span class="bx">${ico('i-check')}</span>
        <span class="tx"><b>یادداشت یک‌صفحه‌ای جلسه</b><small>${bc.note?'ذخیره شده؛ سرپرست پیش از جلسه می‌خواند':'یک جمله هم کافی است'}</small></span>
        <span class="cap">${bc.note?'انجام شد':'مانده'}</span></div>
      <div class="bktask ${vote?'done':''}"><span class="bx">${ico('i-check')}</span>
        <span class="tx"><b>رأی به کتاب ماه بعد</b><small>${vote?'رأیت ثبت شد؛ نتیجه زنده به‌روز می‌شود':'از میان سه کتاب، یکی را انتخاب کن'}</small></span>
        <span class="cap">${vote?'انجام شد':'مانده'}</span></div>
    </div>`;
  return hero+tasks+
    card('پیشرفت مطالعهٔ من','صفحه‌هایی که خوانده‌ای را خودت ثبت کن','i-book',
      `<div class="meter" role="img" aria-label="پیشرفت من ٪${faN(mine)}"><i style="width:${mine}%"></i></div>
       <div class="row" style="margin-top:10px">
         <button class="btn sm quiet" data-pages="10">+۱۰ صفحه</button>
         <button class="btn sm quiet" data-pages="25">+۲۵ صفحه</button>
         <span class="sp" style="flex:1"></span>
         <span class="cap">٪${faN(mine)} از کتاب ماه</span></div>`)+
    card('یادداشت من برای جلسه','سرپرست باشگاه پیش از جلسه یادداشت‌ها را می‌خواند','i-pen',
      `<label class="lbl" for="bcNote" style="display:block;font-size:11.5px;color:var(--ink-3);font-weight:600">یادداشت یک‌صفحه‌ای</label>
       <textarea class="input" id="bcNote" rows="3" placeholder="مثلاً فصل ۴: راوی چه چیزی را پنهان می‌کند؟" style="margin-top:6px">${esc(bc.note)}</textarea>
       <div class="row" style="width:100%;margin-top:10px"><button class="btn sm primary" data-save-note>
         ${ico('i-check')} ذخیرهٔ یادداشت</button>
         <span class="sp" style="flex:1"></span>
         <span class="cap">${bc.note?'ذخیره شده، قابل ویرایش':'خالی'}</span></div>`)+
    card('جلسه‌های پیش‌رو',esc(C.session||'پنجشنبه‌ها ۱۸:۰۰')+' · کتابخانهٔ نورا، ونک','i-calendar',
      plan.map(p=>`<div class="tk">${ico('i-calendar','width:19px;height:19px;color:var(--brand)')}
        <span><b>${esc(p.c)}</b><small>${esc(p.d)} · ${esc(p.w)}</small></span></div>`).join(''))+
    card('کتاب ماه بعد را با هم انتخاب کنیم','رأی تو در فهرست ماه بعد حساب می‌شود','i-star',
      `<div class="votebox">${VOTE.map(v=>{const n=(+v.n||0)+(vote===v.k?1:0), pc2=tot?Math.round(n/tot*100):0;
        return `<button class="voteopt${vote===v.k?' on':''}" data-vote="${esc(v.k)}" aria-pressed="${vote===v.k}">
          <span class="vck">${ico('i-check')}</span>
          <span class="vbar"><span class="vtop"><b>${esc(v.t)}</b><small>${esc(v.by)}</small>
            <span class="num">${faN(n)} رأی</span></span>
            <span class="vtrack"><i style="width:${pc2}%"></i></span></span></button>`}).join('')}</div>
       <p class="cap" style="margin:8px 2px 0">${vote?'رأیت ثبت شد؛ نتیجه زنده به‌روز می‌شود.':'با زدن هر گزینه، رأیت ثبت می‌شود.'}</p>`)+
    card('جلسه‌های گذشته','ضبط هر جلسه هست','i-play-f',
      log.map(l=>`<div class="tk">${ico('i-play-f','width:19px;height:19px;color:var(--ink-4)')}
        <span><b>${esc(l.t)}</b><small>${esc(l.d)} · ${faN(l.n)} نفر حاضر</small>
          <span class="acts"><button class="btn sm quiet" data-watch="${esc(l.t)}">${ico('i-play-f')} تماشا</button></span></span></div>`).join(''))+
    card('قفسهٔ باشگاه','سه کتاب ماه گذشته','i-archive',
      `<div class="shelf">${shelf.map(b=>`<div class="book">
        <span class="bt2" aria-hidden="true"></span>
        <span class="btx"><b>${esc(b.t)}</b><small>${esc(b.by)} · ${esc(b.d)} · ${'★'.repeat(Math.round(+b.r||0))}</small></span></div>`).join('')}</div>`)+
    card('سرپرست باشگاه','جلسه‌ها را او می‌گرداند','i-users',
      `<div class="srow"><span class="qi" style="width:40px;height:40px;border-radius:13px;display:grid;place-items:center;background:var(--brand-tint);color:var(--brand-ink);font-weight:700">${esc(String(sup.n||'م').slice(0,1))}</span>
        <span class="sp">${esc(sup.n||'مریم داوودی')}<small>${esc(sup.r||'سرپرست باشگاه کتاب‌خوانی')}</small></span>
        <button class="btn sm quiet" data-go="support">پرسش</button></div>`+
      (C.rules||[]).map(r=>`<div class="srow">${ico('i-check')}<span class="sp">${esc(r)}</span></div>`).join(''));
}

/* ══ اطلاعات و تنظیمات حساب ═════════════════════════════════════════ */
function validNationalId(v){
  const d=unFa(v).replace(/\D/g,'');
  if(!/^\d{10}$/.test(d)) return false;
  if(/^(\d)\1{9}$/.test(d)) return false;
  const w=[10,9,8,7,6,5,4,3,2]; let s=0;
  for(let i=0;i<9;i++) s+=(+d[i])*w[i];
  const r=+d[9], m=s%11;
  return m<2 ? r===m : r===11-m;
}
function validBirth(v){
  const d=unFa(v).replace(/[^\d/]/g,'');
  const m=d.match(/^(1[23]\d{2})\/(\d{1,2})\/(\d{1,2})$/);
  if(!m) return false;
  return +m[1]>=1300&&+m[1]<=1420&&+m[2]>=1&&+m[2]<=12&&+m[3]>=1&&+m[3]<=31;
}
function validate(p){
  const e={};
  for(const f of FIELDS){
    const v=String(p[f.k]||'').trim();
    if(f.lock){ if(!v) e[f.k]='از نشست خودت خوانده می‌شود؛ دوباره وارد شو'; continue }
    if(f.req&&!v){ e[f.k]='این یکی اجباری است'; continue }
    if(!v) continue;
    if(f.k==='nationalId'&&!validNationalId(v)) e[f.k]='کد ملی ۱۰ رقمی درست نیست';
    if(f.k==='birthDate'&&!validBirth(v)) e[f.k]='تاریخ شمسی، مثل ۱۳۷۰/۰۱/۱۵';
    if(f.k==='email'&&!/^[^@\s]+@[^@\s.]+\.[^@\s]+$/.test(v)) e[f.k]='ایمیل کامل نیست';
    if((f.k==='province'||f.k==='city')&&v.length<2) e[f.k]='نام را کامل بنویس';
  }
  return e;
}
function tidy(p){
  const nat=unFa(p.nationalId||'').replace(/\D/g,''); if(nat) p.nationalId=nat;
  const b=unFa(p.birthDate||'').replace(/[^\d/]/g,'');
  const m=b.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/);
  if(m) p.birthDate=m[1]+'/'+String(+m[2]).padStart(2,'0')+'/'+String(+m[3]).padStart(2,'0');
  FIELDS.forEach(f=>{ if(f.lock) return; p[f.k]=unFa(p[f.k]||'') });
  return p;
}
function fieldView(f,p){
  const raw=String(p[f.k]||'').trim();
  const val=f.lock?faN(phone()):(!raw?'':(f.input==='numeric'||f.k==='birthDate'?faN(raw):raw));
  if(f.lock) return `<span class="v">${ico('i-check','width:15px;height:15px;color:var(--ok)')}
      <span class="tx">${esc(val||'—')}</span><span class="tag ok" style="height:20px;font-size:10px">تأییدشده</span></span>`;
  if(!val) return `<span class="v"><span class="tx miss">${f.req?'ثبت نشده':'اختیاری، خالی'}</span></span>`;
  return `<span class="v"><span class="tx">${esc(val)}</span></span>`;
}
function fieldEdit(f,p){
  const bad=S.errs[f.k], v=f.lock?phone():String(p[f.k]||'');
  return `<label class="lbl" for="f_${f.k}" style="margin:0">${esc(f.l)}${f.req?'':' <span class="cap">اختیاری</span>'}</label>
    <input class="input${f.input==='numeric'?' num':''}" id="f_${f.k}" name="${f.k}" type="${f.input==='email'?'email':'text'}"
      ${f.input==='numeric'?'inputmode="numeric"':''} ${f.max?`maxlength="${f.max}"`:''}
      value="${esc(v)}" placeholder="${esc(f.ph||'')}" ${f.lock?'readonly aria-readonly="true"':''}
      ${bad?`aria-invalid="true" aria-describedby="e_${f.k}"`:(f.hint?`aria-describedby="h_${f.k}"`:'')}/>
    ${bad?`<span class="err" id="e_${f.k}" role="alert">${esc(bad)}</span>`
        :(f.hint?`<span class="hint" id="h_${f.k}">${esc(f.hint)}${f.lock?': برای عوض‌کردنش با پشتیبانی حرف بزن':''}</span>`:'')}`;
}
function infoPanel(){
  const p=prof(), st=stOf(p), groups=[];
  FIELDS.forEach(f=>{ if(!groups.includes(f.g)) groups.push(f.g) });
  const body=groups.map(g=>`<div class="grp"><div class="gt cap">${esc(g)}</div>
    ${FIELDS.filter(f=>f.g===g).map(f=>f.k==='photo'?photoRow(p)
      :S.edit
        ? `<div class="fld${S.errs[f.k]?' bad':''}">${fieldEdit(f,p)}</div>`
        : `<div class="fld"><span class="hint">${esc(f.l)}<i class="prm">${esc(f.param||f.k)}</i></span>${fieldView(f,p)}</div>`).join('')}</div>`).join('');
  const acts=S.edit?`<div class="row" style="margin-top:14px">
      <button class="btn primary" id="sendBtn">${ico('i-check')} ذخیره و ارسال برای تأیید</button>
      <button class="btn quiet" id="draftBtn">فقط ذخیره</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" id="cancelBtn">انصراف</button></div>`
    :`<div class="row" style="margin-top:12px"><button class="btn ${missOf(p).length?'primary':'quiet'}" id="editBtn">
      ${ico('i-pen')} ${missOf(p).length?'تکمیل فرم پروفایل':'ویرایش فرم پروفایل'}</button></div>`;
  return pfCard()+
    card('اطلاعات من','پارامترهای فرمی که مدیر سامانه ساخته؛ تغییرات اول به کارشناس می‌رود','i-idcard',
    `<div class="row" style="align-items:center;gap:8px;margin-top:2px"><span class="cap">وضعیت</span>${chip(st[0],st[1])}
      <span class="sp" style="flex:1"></span><span class="cap">٪${faN(pctOf(p))} کامل</span></div>${body}${acts}`)+
    trustCard();
}
/* ── کارت فرم پروفایل: ساختهٔ مدیر سامانه، نه این‌جا ──────────────── */
function pfCard(){
  if(!PF.n) return '';
  return card('فرم پروفایل','ساختهٔ '+esc(PF.maker||'مدیر سامانه')+(PF.at?' · '+esc(PF.at):''),'i-layers',
    `<p class="cap" style="margin:0 3px 8px">${esc(PF.lead||'')}</p>
     <div class="srow">${ico('i-list')}
       <span class="sp">پارامترهای این فرم<small>${faN(FIELDS.length)} پارامتر از عکس تا کد ملی</small></span>
       <span class="tag">${esc(PF.cap||'')}</span></div>
     <div class="prms">${FIELDS.map(f=>`<span class="prm on">${esc(f.param||f.k)}</span>`).join('')}</div>
     <div class="row" style="margin-top:10px"><a class="btn sm quiet" href="${esc(PF.from||'builder.html')}">
       ${ico('i-chart')} ${esc(PF.fromN||'پنل فرم‌ها')}</a>
       <span class="sp" style="flex:1"></span><span class="cap">گونه‌ها: ${esc((PF.kinds||[]).join('، '))}</span></div>`);
}
/* پارامتر عکس: تنها پارامتری که با بارگذاری پر می‌شود */
function photoRow(p){
  const cur=p.photo||PHOTO_SEED[0];
  return `<div class="fld phrow"><span class="hint">${esc('عکس پروفایل')}<i class="prm">photo</i></span>
    <span class="v phv">
      <span class="phthumb"><img src="${esc(cur)}" alt="عکس پروفایل"/></span>
      ${S.edit?`<span class="tx"><label class="btn sm" for="phFile">${ico('i-image')} بارگذاری عکس</label>
        <input id="phFile" type="file" accept="image/*" hidden/>
        <button class="btn sm quiet" type="button" data-photo-demo>عکس نمونه</button></span>`
      :`<span class="tx"><span class="cap">همین عکس روی کارت ورود و گواهی می‌آید</span></span>`}
    </span></div>`;
}
function flowPanel(){
  const p=prof(), st=(p&&p.status)||'draft', hist={}; (p.history||[]).forEach(h=>{hist[h.k]=h.at});
  const hit={filled:['draft','pending','approved'],pending:['pending','approved'],approved:['approved']};
  const steps=FLOW.map(f=>{const on=(hit[f.k]||[]).includes(st), now=(st==='pending'&&f.k==='pending');
    return `<div class="step ${on?'done':''} ${now?'on':''}">
      <span class="dot">${ico('i-'+(on?'check':f.k==='pending'?'clock':'pen'),'width:13px;height:13px')}</span>
      <span class="tx"><b>${esc(f.n)}</b><small>${esc(f.s)}</small></span>
      <span class="lc cap" style="margin-inline-start:auto">${esc(hist[f.k]||(on?'':'—'))}</span></div>`}).join('');
  const tail = st==='rejected' ? `<span class="err" style="display:block;margin-top:8px">دلیل رد: ${esc(p.reason||'نامشخص')}</span>`
    : st==='pending' ? '<p class="cap" style="margin:10px 3px 0">معمولاً تا یک روز کاری بررسی می‌شود.</p>'
    : st==='approved' ? '<p class="cap" style="margin:10px 3px 0">پروفایلت تأیید شده است؛ اگر چیزی را عوض کنی، دوباره می‌رود صف تأیید.</p>'
    : '<p class="cap" style="margin:10px 3px 0">هر وقت اطلاعات را فرستادی، وضعیت همین‌جا عوض می‌شود.</p>';
  return card('تأیید پروفایل','کارشناس درخواستت را می‌بیند و نتیجه را خبر می‌دهد','i-shield',`<div class="steps">${steps}</div>${tail}`);
}
function formsPanel(){
  const F=[{t:'فرم پروفایل اعضا',k:'پروفایل',s:'pending',d:'۲ مهر',mine:true},
           {t:'پیش‌ثبت‌نام کارگاه خطاطی',k:'پیش‌ثبت‌نام',s:'draft',d:'۳ مهر'},
           {t:'رضایت‌سنجی کارگاه عکاسی',k:'رضایت‌سنجی کارگاه',s:'pending',d:'۲۱ تیر'},
           {t:'انتخاب مسیر ترم پاییز',k:'انتخاب مسیر',s:'approved',d:'۱۲ شهریور'}];
  const M={draft:['پیش‌نویس','warn'],pending:['در صف بررسی','brand'],approved:['تأییدشده','ok']};
  return card('فرم‌های من','فرم‌ها را مدیر سامانه می‌سازد و برایت می‌گذارد','i-doc',
    F.map(f=>`<div class="tk">${ico(f.mine?'i-idcard':'i-doc','width:19px;height:19px;color:var(--ink-4)')}
      <span><b>${esc(f.t)}</b><small>${esc(f.k)} · ${esc(f.d)}${f.mine?' · ساختهٔ مدیر سامانه':''}</small>
        <span class="acts">${chip(M[f.s][0],M[f.s][1])}
          <button class="btn sm quiet" data-form="${esc(f.t)}">${f.s==='draft'?'ادامهٔ تکمیل':'دیدن پاسخ‌ها'}</button></span></span></div>`).join('')+
    `<div class="row" style="margin-top:12px">
      <a class="btn sm quiet" href="${esc(PF.from||'builder.html')}">${ico('i-chart')} فرم‌ها در ${esc(PF.fromN||'پنل فرم‌ها')}</a>
      <span class="sp" style="flex:1"></span><span class="cap">${faN((POL.formKinds||[]).length)} گونه فرم</span></div>`+
    note('فرم تازه این‌جا ساخته نمی‌شود؛ مدیر سامانه فرم را در پنل می‌سازد و می‌گذارد، تو فقط پرش می‌کنی.','i-layers')+
    trustLine('privacy'));
}
function privacyPanel(){
  const p=prof(), asked=!!p.askedDelete;
  const steps=(DELFLOW.steps||[]).map((st,i)=>{
    const from=asked?(i===0?1:0):0;   /* بعد از درخواست، «درخواست تو» انجام شده */
    const on=asked&&i===0, now=asked&&i===1;
    return `<div class="step ${on?'done':''} ${now?'on':''}">
      <span class="dot">${ico('i-'+(on?'check':now?'clock':'shield'),'width:13px;height:13px')}</span>
      <span class="tx"><b>${esc(st.n)}</b><small>${esc(asked?st.s:'—')}</small></span>
      <span class="lc cap" style="margin-inline-start:auto">${esc(asked&&i===0?'همین حالا':now?'در انتظار':'—')}</span></div>`}).join('');
  return card('حریم خصوصی','اطلاعاتت را می‌توانی برداری؛ حساب را فقط کارشناس می‌بندد','i-lock',
    `<div class="srow">${ico('i-doc')}
      <span class="sp">دانلود اطلاعات من<small>فرم پروفایل، خریدها، اعلان‌ها و آمار، یک فایل</small></span>
      <button class="btn sm quiet" id="dlBtn">${ico('i-send')} دانلود</button></div>
     <div class="srow">${ico('i-shield','color:var(--stop)')}
      <span class="sp">درخواست حذف حساب<small>${esc(DELFLOW.lead||'با تأیید کارشناس انجام می‌شود')}</small></span>
      <button class="btn sm stop" id="delBtn" ${asked?'disabled':''}>${asked?'در انتظار تأیید':'درخواست حذف'}</button></div>
     <div class="steps" style="margin-top:10px">${steps}</div>
     <div class="cap" id="delNote" style="margin-top:8px">${asked?esc(DELFLOW.note||''):''}</div>`)+
    note('حذف حساب بی‌برگشت است؛ برای همین دو تأیید می‌گیریم: تایپ «حذف» و کد پیامکی. بعدش هم تا کارشناس تأیید نکند، چیزی پاک نمی‌شود.','i-lock')+
    card('چه چیزی نگه می‌داریم','شفاف و کوتاه','i-shield',
      `<div class="srow">${ico('i-check')}<span class="sp">اطلاعات پروفایل، برای بلیت و گواهی</span></div>
       <div class="srow">${ico('i-check')}<span class="sp">سابقهٔ خرید و حضور، برای کارنامهٔ تو</span></div>
       <div class="srow">${ico('i-lock')}<span class="sp">شمارهٔ موبایل، فقط برای ورود و یادآوری</span></div>`)+
    trustCard();
}
/* عکس پروفایل: پارامتر تصویری فرم — بارگذاری یا عکس نمونه */
function demoPhoto(){
  const p=prof(), cur=p.photo||PHOTO_SEED[0];
  const next=PHOTO_SEED[(PHOTO_SEED.indexOf(cur)+1)%PHOTO_SEED.length];
  p.photo=next; if(UI().saveProfile) UI().saveProfile(p);
  render(); toast('عکس پروفایل ثبت شد؛ روی کارت ورود می‌آید');
}
function pickPhoto(file){
  const p=prof();
  try{ if(file&&window.URL&&URL.createObjectURL) p.photo=URL.createObjectURL(file); else return }
  catch(e){ return }
  if(UI().saveProfile) UI().saveProfile(p);
  render(); toast('عکس پروفایل بارگذاری شد');
}
document.addEventListener('change',ev=>{
  const el=ev.target;
  if(el&&el.id==='phFile'&&el.files&&el.files[0]) pickPhoto(el.files[0]);
},false);

/* ورقهٔ «اطلاعاتت ایمن است»: همهٔ جمله‌های اطمینان یک‌جا */
function trustSheet(){
  const rows=(N.TRUST&&N.TRUST.row)||[];
  fillSheet('shTrust',`<div class="grabber"></div><div class="head">${esc((N.TRUST&&N.TRUST.head)||'اطلاعاتت ایمن است')}</div>
    <p class="sub" style="margin-top:8px">کوتاه و بی‌حاشیه؛ همین‌ها را رعایت می‌کنیم.</p>
    <div class="steps" style="margin-top:10px">${rows.map(r=>`<div class="step done">
      <span class="dot">${ico('i-shield','width:13px;height:13px')}</span>
      <span class="tx"><b>${esc(r[0])}</b><small>${esc(r[1])}</small></span></div>`).join('')}</div>
    <div class="row" style="margin-top:14px"><button class="btn quiet" data-close>بستن</button></div>`);
  openSheet('shTrust');
}

/* ورود و امنیت: شماره، دستگاه‌ها، پیام‌گیرها و خروج */
function authPanel(){
  const ph=phone(), ms=(A.login&&A.login.msgs)||[];
  const devs=[{k:'this', n:'همین دستگاه', d:'کروم · اندروید', i:'i-mobile', at:'همین حالا', now:true},
              {k:'phone', n:'گوشی اندروید', d:'اپلی نورا', i:'i-mobile', at:'دیروز، ۱۹:۱۲'},
              {k:'home', n:'رایانهٔ خانه', d:'سافاری · مک', i:'i-monitor', at:'۱۲ مهر، ۲۱:۴۰'}];
  return card('شمارهٔ ورود و رمز','همین شماره شناسهٔ توست؛ کد یک‌بارمصرف به آن می‌رسد','i-mobile',
      `<div class="srow">${ico('i-mobile')}
        <span class="sp">شمارهٔ ورود<small class="num">${ph?'۰۹'+faN(ph.slice(2,5))+'…'+faN(ph.slice(-4)):'—'}</small></span>
        <button class="btn sm quiet" data-relogin>تغییر شماره</button></div>
       <div class="srow">${ico('i-lock')}
        <span class="sp">رمز و گذرواژه<small>نداریم؛ هر ورود یک کد یک‌بارمصرف است</small></span>${chip('بی رمز','ok')}</div>
       <div class="srow">${ico('i-shield')}
        <span class="sp">دو دستگاه هم‌زمان<small>بیشتر از این، دستگاه تازه نشست قبلی را می‌بندد</small></span>${chip('روشن','ok')}</div>`) +
    card('راه‌های ورود','شماره به یکی از این پیام‌گیرها تحویل می‌شود و کد را از همان‌جا می‌گیری','i-chat',
      `<div class="kinds">${ms.map(m=>`<div class="kind">${ico('i-chat','width:19px;height:19px;color:var(--ink-4)')}
        <span class="tx"><b>${esc(m.n)}</b><small>${esc(m.s||'')}</small></span>
        <a class="btn sm quiet" href="${esc(m.href||'#')}" target="_blank" rel="noopener">باز کردن</a></div>`).join('')}</div>` +
      (devs.length?'':'')) +
    card('دستگاه‌های واردشده',faN(devs.length)+' دستگاه این حساب را باز کرده‌اند','i-users',
      devs.map(d=>`<div class="drow">${ico(d.i||'i-mobile')}
        <span class="tx"><b>${esc(d.n)}</b><small>${esc(d.d)} · ${esc(d.at)}</small></span>
        ${d.now?chip('این دستگاه','brand'):`<button class="btn sm quiet" data-enddev="${esc(d.k)}">بستن نشست</button>`}</div>`).join('')) +
    card('خروج از حساب','فقط نشست همین دستگاه بسته می‌شود','i-lock',
      `<button class="btn stop" id="logoutBtn">${ico('i-close')} خروج از حساب</button>
       <p class="cap" style="margin-top:9px">خروج، بلیت و گواهی و امتیازت را پاک نمی‌کند؛ فقط تا ورود تازه، حساب بسته است.</p>`);
}

/* پروفایل من: شش تب، هر چیزی که به خودِ عضو برمی‌گردد، یک‌جا */
const PTABS=A.profileTabs||[{k:'info',n:'اطلاعات من'}];
VS.profile=function(t){
  if(!login()) return viewHead(t,'',PTABS,'ptab')+gate(t);
  const body=S.ptab==='auth'?authPanel()
    : S.ptab==='club'?clubTab()
    : S.ptab==='book'?bookPanel()
    : S.ptab==='forms'?formsPanel()
    : S.ptab==='privacy'?privacyPanel()
    : infoPanel()+flowPanel();
  const sub=(PTABS.find(x=>x.k===S.ptab)||{}).s||'';
  return viewHead(t,sub,PTABS,'ptab')+`<div class="panel">${body}</div>`;
};
/* باشگاه کتاب‌خوانی خط زندگی: بخش خودش، با همان تنِ باشگاه */
VS.book=function(t){
  if(!login()) return viewHead(t,'',null)+gate(t);
  const C=N.CLUB||{};
  return viewHead(t,(C.term?'ترم '+C.term+' · ':'')+(C.book||''),null)+`<div class="panel">${bookPanel()}</div>`;
};
VS.pay=function(t){
  const bits=POL.payBits||['کیف پول','شارژ','صورت‌حساب','اقساط','بازگشت وجه','کد تخفیف'];
  return viewHead(t)+card('نورا پی','این بخش را در یک فاز جدا می‌سازیم','i-wallet',
    `<div class="gate">${ico('i-wallet')}
      <div class="head">فعلاً قفل است</div>
      <div class="cap">حساب، رویدادها و امتیاز کار می‌کند؛ کیف پول و پرداخت‌ها فاز بعد می‌آید تا
        شماره‌ها و صورت‌حساب‌ها از اول درست بنشینند.</div>
      <div class="chipsline" style="justify-content:center">${bits.map(b=>chip(b)).join('')}</div>
      <div class="gacts"><button class="btn primary" data-go="support">پیشنهادت را بگو</button>
        <button class="btn quiet" data-go="events">رویدادهای من</button></div></div>`);
};

/* ══ پشتیبانی: صفحهٔ جدای خودش ══════════════════════════════════════
   تیکت، پرسش‌های پرتکرار، راهنمای هر بخش و پیام‌رسان‌ها همه در support.html
   است؛ از این صفحه فقط می‌رویم آن طرف. */
function goSupport(){ location.href=(SUP.href||'support.html') }
function supportVisible(){
  const open=(SUP.open!==false);
  document.querySelectorAll('[data-open-support]').forEach(el=>{ if(!open) el.hidden=true });
  const sb=$('#supBar'); if(sb&&!open) sb.hidden=true;
  return open;
}

/* ══ ویرایش، ذخیره، حذف ═════════════════════════════════════════════ */
function startEdit(){ if(!login()){ S.after='account'; loginSheet(); return }
  S.edit=true; S.errs={}; renderView(); const el=$('#f_fullName'); if(el&&el.focus) el.focus() }
function cancelEdit(){ S.edit=false; S.errs={}; renderView() }
function collect(){
  const p=Object.assign({},prof());
  FIELDS.forEach(f=>{ if(f.lock) return; const el=$('#f_'+f.k); if(el) p[f.k]=el.value });
  if(!p.phone) p.phone=phone();
  return p;
}
function submit(send){
  const p=tidy(collect()), errs=validate(p);
  S.errs=errs;
  if(Object.keys(errs).length){ renderView(); toast('چند قلم را ببین و درست کن'); return }
  p.phone=phone();
  if(send) p.status='pending';
  p.history=(p.history||[]).filter(h=>h.k!==(send?'pending':'draft')).concat([{k:send?'pending':'draft',at:nowFa()}]);
  if(UI().saveProfile) UI().saveProfile(p);
  S.edit=false; render();
  toast(send?'ذخیره شد و برای تأیید رفت':'ذخیره شد؛ هر وقت خواستی برای تأیید بفرست');
}
function nowFa(){
  try{ return new Intl.DateTimeFormat('fa-IR-u-ca-persian',{day:'numeric',month:'long'}).format(new Date()) }
  catch(e){ return 'امروز' }
}
function askDelete(){
  fillSheet('shConfirm',`<div class="grabber"></div><div class="head">حذف حساب کاربری</div>
    <p class="sub" style="margin-top:8px">این کار بی‌برگشت است: بلیت‌ها، گواهی‌ها و سابقهٔ حضور هم پاک می‌شود.
      همین‌جا فقط <b>درخواست</b> ثبت می‌شود؛ کارشناس سامانه بررسی می‌کند و با تأیید او حساب بسته می‌شود.</p>
    <label class="lbl" for="delWord" style="margin-top:12px;display:block">کلمهٔ تأیید</label>
    <input class="input" id="delWord" placeholder="حذف" autocomplete="off" style="margin-top:6px"/>
    <label class="lbl" for="delCode" style="margin-top:10px;display:block">کد پیامکی</label>
    <input class="input num" id="delCode" inputmode="numeric" maxlength="5" placeholder="کد ۵ رقمی" style="margin-top:6px"/>
    <div class="cap" style="margin-top:6px">کد نمایشی: ۵۴۳۲۱</div>
    <div class="row" style="margin-top:14px"><button class="btn stop" id="delYes">درخواست حذف را بفرست</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" data-close>هنوز نه</button></div>`);
  openSheet('shConfirm');
}
function downloadInfo(){
  const p=prof();
  const data={
    'حساب':{'نام':p.fullName,'نام پدر':p.fatherName,'کد ملی':p.nationalId,'تاریخ تولد':p.birthDate,
            'تماس':phone(),'ایمیل':p.email,'نشانی':p.address},
    'وضعیت':p.status,'سابقه':p.history||[],
    'رویدادها':EVENTS.map(e=>({'عنوان':e.t,'زمان':e.when,'جا':e.place})),
    'بلیت‌ها':{'کد عضویت':'NL-4567'},
    'امتیاز':A.points||0,'گواهی‌ها':Object.keys(CERTS)};
  const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob), a=document.createElement('a');
  a.href=url; a.download='nora-account.json'; document.body.appendChild(a); a.click();
  setTimeout(()=>{ URL.revokeObjectURL(url); a.remove() },400);
  toast('فایل اطلاعات حساب آماده شد');
}
function saveFile(name,txt){
  const blob=new Blob([txt],{type:'text/plain;charset=utf-8'});
  const url=URL.createObjectURL(blob), a=document.createElement('a');
  a.href=url; a.download=name; document.body.appendChild(a); a.click();
  setTimeout(()=>{ URL.revokeObjectURL(url); a.remove() },400);
}
function certDownload(ser){
  const c=CERTS[ser]||{};
  saveFile('nora-cert-'+ser+'.txt',
    ['گواهی نورا - گروه فرهنگی خط زندگی','', 'نام: '+(c.n||prof().fullName||''), 'رویداد: '+(c.c||''),
     'تاریخ: '+(c.d||''), 'مدت: '+(c.h||''), 'سریال: '+ser, '', 'استعلام: lifeline1.ir/nora-ui/verify'].join('\n'));
  toast('گواهی دانلود شد؛ سریال '+faN(ser));
}
function certAsk(kind){
  const K=(POL.certKinds||[]).find(k=>k.k===kind)||{};
  fillSheet('shConfirm',`<div class="grabber"></div><div class="head">${esc(K.n||'گواهی')}</div>
    <p class="sub" style="margin-top:8px">${esc(K.s||'')} · صدور گواهی نیاز به تأیید سرپرست دارد؛ بعد از تأیید خبر می‌دهیم.</p>
    <div class="row" style="margin-top:14px"><button class="btn primary" data-cert-yes>
      ${ico('i-check')} بفرست برای تأیید سرپرست</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" data-close>نه</button></div>`);
  openSheet('shConfirm');
}

/* ══ رندر ════════════════════════════════════════════════════════════ */
function viewOf(k){ return k==='events'?VS.events : k==='profile'?VS.profile
  : k==='pay'?VS.pay : k==='book'?VS.book : null }
/* نشانی‌های کوتاه، همان تب پروفایل را باز می‌کنند */
const ALIAS={info:['profile','ptab','info'], account:['profile','ptab','info'],
  auth:['profile','ptab','auth'], login:['profile','ptab','auth'],
  forms:['profile','ptab','forms'], privacy:['profile','ptab','privacy'],
  club:['profile','ptab','club'], points:['profile','ptab','club'], points2:['profile','ptab','club']};
function renderView(){
  const box=$('#viewBox'), t=SECT.find(s=>s.k===S.view), fn=viewOf(S.view);
  if(!box||!t||!fn) return;
  box.innerHTML=`<section class="sec" aria-label="${esc(t.n)}">${fn(t)}</section>`;
  document.title='نورا · '+t.n;
}
function render(){
  renderProfile();
  const prof=$('#profBox'), box=$('#viewBox'), ok=!!viewOf(S.view), sb=$('#supBar');
  if(sb) sb.hidden=!supportVisible();          /* پشتیبانی می‌چسبد به نوار پایین */
  if(!ok){ S.view=''; if(box){ box.hidden=true; box.innerHTML='' }
    if(prof) prof.hidden=false; document.title='نورا · حساب من' }
  else { if(prof) prof.hidden=true; box.hidden=false; renderView() }
}
function route(){
  const raw=(location.hash||'').replace('#','');
  if(raw==='support'){ goSupport(); return }
  if(ALIAS[raw]){ const [v,f,val]=ALIAS[raw]; S.view=v; S[f]=val; S.edit=false; S.errs={}; render();
    try{window.scrollTo({top:0})}catch(e){}; return }
  if(!raw){ S.view=''; render(); try{window.scrollTo({top:0})}catch(e){}; return }
  if(viewOf(raw)){ S.view=raw; S.edit=false; S.errs={}; render(); try{window.scrollTo({top:0})}catch(e){}; return }
  S.view=''; render(); toast('این بخش را نداریم؛ برگشتیم سرِ حساب من');
  try{history.replaceState(null,'',location.pathname)}catch(e){}
}

/* ══ کنش‌ها ══════════════════════════════════════════════════════════ */
document.addEventListener('click',ev=>{
  const t=ev.target;
  if(t.closest('[data-back]')){ try{history.replaceState(null,'',location.pathname)}catch(e){}
    S.view=''; render(); try{window.scrollTo({top:0})}catch(e){}; return }
  const g=t.closest('[data-go]'); if(g){ go(g.dataset.go); return }
  const vw=t.closest('[data-view]');
  if(vw){ const k=vw.dataset.view;
    if(k==='pay'||login()){ location.hash='#'+k; return }
    S.after=k; loginSheet(); return }
  const pb=t.closest('[data-pay]'); if(pb){ location.hash='#pay'; return }
  const qt=t.closest('[data-qt]');
  if(qt){ const k=qt.dataset.qt;                     /* میان‌بُرهای کهنه، اگر جایی ماند */
    if(k==='support'){ goSupport(); return }
    if(!login()){ S.after=k==='tickets'?'events':'club'; loginSheet(); return }
    if(k==='tickets'){ S.view='events'; S.vtab='tickets'; location.hash='#events'; render(); return }
    S.view='profile'; S.ptab='club'; location.hash='#profile'; render(); return }
  const vt=t.closest('[data-vtab]'); if(vt){ S.vtab=vt.dataset.vtab; renderView(); return }
  const pt=t.closest('[data-ptab]'); if(pt){ S.ptab=pt.dataset.ptab; S.edit=false; S.errs={}; renderView(); return }
  if(t.closest('[data-photo-demo]')){ demoPhoto(); return }
  if(t.closest('[data-trust-more]')){ trustSheet(); return }
  if(t.closest('#editBtn')){ startEdit(); return }
  if(t.closest('#cancelBtn')){ cancelEdit(); return }
  if(t.closest('#draftBtn')){ submit(false); return }
  if(t.closest('#sendBtn')){ submit(true); return }
  if(t.closest('#dlBtn')){ login()?downloadInfo():loginSheet(); return }
  if(t.closest('#delBtn')){ login()?askDelete():loginSheet(); return }
  if(t.closest('#delYes')){
    const w=unFa(($('#delWord')||{}).value||'').replace(/[\s\u200c«»"]/g,'');
    const code=unFa(($('#delCode')||{}).value||'').replace(/\D/g,'');
    if(w!=='حذف'){ toast('برای تأیید، کلمهٔ «حذف» را بنویس'); const e=$('#delWord'); if(e&&e.focus) e.focus(); return }
    if(code!=='54321'){ toast('کد پیامکی را درست بنویس؛ کد نمایشی ۵۴۳۲۱ است'); const e=$('#delCode'); if(e&&e.focus) e.focus(); return }
    const p=Object.assign({},prof(),{askedDelete:true});
    p.history=(p.history||[]).filter(h=>h.k!=='delete').concat([{k:'delete',at:nowFa()}]);
    if(UI().saveProfile) UI().saveProfile(p);
    closeSheets(); render(); toast('درخواستت برای کارشناس رفت؛ تا تأیید او چیزی پاک نمی‌شود'); return }
  const dc=t.closest('[data-dl-cert]'); if(dc){ certDownload(dc.dataset.dlCert); return }
  const cr=t.closest('[data-certreq]'); if(cr){ certAsk(cr.dataset.certreq); return }
  if(t.closest('[data-cert-yes]')){ closeSheets(); toast('سفارش ثبت شد؛ بعد از تأیید سرپرست خبر می‌دهیم'); return }
  const cv=t.closest('[data-verify]'); if(cv){ toast('برای استعلام سریال '+faN(cv.dataset.verify)+' صفحهٔ استعلام باز می‌شود'); return }
  if(t.closest('[data-ticket]')){ toast('کارت ورود آماده است؛ در ورودی نشانش بده'); return }
  const cx=t.closest('[data-cancel]');
  if(cx){ const e=EVENTS.find(x=>x.id===cx.dataset.cancel)||{};
    fillSheet('shConfirm',`<div class="grabber"></div><div class="head">لغو ثبت‌نام</div>
      <p class="sub" style="margin-top:8px">«${esc(e.t||'این برنامه')}» را لغو کنم؟ شرایط بازگشت مبلغ همان چیزی است
        که در صفحهٔ رویداد نوشته شده.</p>
      <div class="row" style="margin-top:14px"><button class="btn stop" data-cancel-yes="${esc(cx.dataset.cancel)}">بله، لغو کن</button>
        <span class="sp" style="flex:1"></span><button class="btn quiet" data-close>نه</button></div>`);
    openSheet('shConfirm'); return }
  if(t.closest('[data-cancel-yes]')){ closeSheets(); toast('ثبت‌نام لغو شد؛ مبلغ طبق شرایط هم رویداد برمی‌گردد'); return }
  const op=t.closest('[data-open-past]');
  if(op){ const h=PAST.find(x=>x.id===op.dataset.openPast)||{}; toast('ضبط «'+h.t+'» با جزوه در پخش‌کننده باز می‌شود'); return }
  const cg=t.closest('[data-cert]'); if(cg){ certDownload('NL-T4K7M9X'); return }
  if(t.closest('[data-form-new]')){ toast('کارشناس فرم را برایت می‌فرستد؛ بعد از آن همین‌جا باز می‌شود'); return }
  const fm=t.closest('[data-form]'); if(fm){ toast('فرم «'+fm.dataset.form+'» در فاز بعد باز می‌شود'); return }
  const rw=t.closest('[data-reward]'); if(rw){ toast('«'+rw.dataset.reward+'» با امتیازت گرفته شد؛ در فروشگاه پاداش کامل می‌شود'); return }
  const cp=t.closest('[data-copy]'); if(cp){ copyText(cp.dataset.copy,'کد دعوت کپی شد'); return }
  if(t.closest('[data-invite]')){ toast('پیوند دعوت ساخته شد؛ برای دوستت بفرست'); return }
  const pg=t.closest('[data-ptab-go]');
  if(pg){ S.view='profile'; S.ptab=pg.dataset.ptabGo; location.hash='#profile'; render(); return }
  if(t.closest('[data-relogin]')){ goLogin('account'); return }
  const ed=t.closest('[data-enddev]');
  if(ed){ toast('نشست «'+(ed.closest('.drow')?ed.closest('.drow').querySelector('b').textContent:ed.dataset.enddev)+'» بسته شد'); return }
  if(t.closest('#logoutBtn')){
    fillSheet('shConfirm',`<div class="grabber"></div><div class="head">خروج از حساب</div>
      <p class="sub" style="margin-top:8px">از این دستگاه بیرون بیایم؟ بعداً با همان شماره و یک کد برمی‌گردی.</p>
      <div class="row" style="margin-top:14px"><button class="btn stop" data-logout-yes>بله، خارج شو</button>
        <span class="sp" style="flex:1"></span><button class="btn quiet" data-close>نه</button></div>`);
    openSheet('shConfirm'); return }
  if(t.closest('[data-logout-yes]')){
    try{ localStorage.removeItem('nora-home-user') }catch(e){}
    try{ document.dispatchEvent(new CustomEvent('nora:logout')) }catch(e){}
    closeSheets(); S.view=''; S.ptab='info';
    try{history.replaceState(null,'',location.pathname)}catch(e){}
    render(); toast('از حساب بیرون آمدی؛ هر وقت خواستی دوباره وارد شو'); return }
  if(t.closest('[data-demo]')){
    /* برای بازبینی: حساب نمونه را همان‌جا می‌نشانیم؛ خروجش هم در «ورود و امنیت» است */
    try{ localStorage.setItem('nora-home-user',JSON.stringify({name:(A.seed||{}).fullName||'سارا محمدی',
      mobile:'09121234567',joined:'شهریور ۱۴۰۴',certs:2,wallet:1250000,msgs:1})) }catch(e){}
    render(); toast('حساب نمونه نشست؛ هر وقت خواستی از «ورود و امنیت» بیرون بیا'); return }
  if(t.closest('[data-login]')){ S.after=''; loginSheet(); return }
  if(t.closest('[data-close]')){ closeSheets(); return }
  if(t.closest('[data-open-support]')){ goSupport(); return }
  if(t.closest('#supBar')){ goSupport(); return }
  if(t.closest('[data-menu]')){ if(UI().uiOpen) UI().uiOpen('shMenu'); return }
  const er=t.closest('[data-edit-review]'); if(er){ toast('ویرایش نظر «'+er.dataset.editReview+'» در فاز نظرها کامل می‌شود'); return }
  /* باشگاه کتاب‌خوانی */
  if(t.closest('[data-pages]')){ const add=+t.closest('[data-pages]').dataset.pages||0;
    const bc=bookState(); bookSet({pages:Math.max(0,Math.min(200,bc.pages+add))}); renderView(); return }
  if(t.closest('[data-seat]')){ bookSet({seat:true}); renderView(); toast('صندلی پنجشنبه رزرو شد'); return }
  if(t.closest('[data-save-note]')){
    const el=$('#bcNote'), v=el?String(el.value||'').trim():'';
    if(v.length<10){ toast('کمی بیشتر بنویس؛ یک جمله هم کافی است'); if(el&&el.focus) el.focus(); return }
    bookSet({note:v}); renderView(); toast('یادداشتت ذخیره شد؛ سرپرست پیش از جلسه می‌خواند'); return }
  const vo=t.closest('[data-vote]'); if(vo){ bookSet({vote:vo.dataset.vote}); renderView(); toast('رأیت ثبت شد'); return }
  const wt=t.closest('[data-watch]'); if(wt){ toast('ضبط «'+wt.dataset.watch+'» در پخش‌کننده باز می‌شود'); return }
});
document.addEventListener('change',e=>{
  const el=e.target; if(!el.id||el.id.indexOf('f_')!==0) return;
  const k=el.id.slice(2); if(!S.errs[k]) return; delete S.errs[k]; renderView();
});
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){ closeSheets(); return }
  /* پیمایش تب‌ها با کلید جهت‌دار، مطابق الگوی تب‌های ARIA */
  const tb=e.target&&e.target.closest?e.target.closest('[role="tab"]'):null;
  if(!tb) return;
  const list=tb.closest('[role="tablist"]'); if(!list) return;
  const items=[...list.querySelectorAll('[role="tab"]')], i=items.indexOf(tb); if(i<0) return;
  const rtl=document.documentElement.dir!=='ltr'; let j=null;
  if(e.key==='ArrowRight') j=i+(rtl?-1:1);
  else if(e.key==='ArrowLeft') j=i+(rtl?1:-1);
  else if(e.key==='Home') j=0;
  else if(e.key==='End') j=items.length-1;
  if(j===null) return;
  e.preventDefault();
  if(j<0) j=items.length-1; if(j>=items.length) j=0;
  items[j].focus(); items[j].click();
});
window.addEventListener('hashchange',route);

/* ══ بوت ═════════════════════════════════════════════════════════════ */
if(typeof initUI==='function') initUI();
route();
})();
