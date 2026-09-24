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
const FIELDS=A.fields||[], LEVELS=A.levels||[], ACH=A.achievements||[], STORE=A.rewardStore||[];
const MON=A.months||{sh:'شهریور'};
const TRUST=N.TRUST||{}, TRUST_ROWS=TRUST.row||[];
const PF=A.profileForm||{}, DELFLOW=A.deleteFlow||{};
const MY=A.myEvents||{}, MY_UP=MY.up||[], MY_PAST=MY.past||[];
const MY_INFO=MY.info||{}, TABS=MY.tabs||{}, GRP=MY.groups||{};
const PAYINFO=A.pay||{}, PAYM=PAYINFO.methods||[], PAY_EV=PAYINFO.eventModels||{},
      PAY_DEF=PAYINFO.defaultModels||['bale','wallet','card'];
const PAY_KEY='nora-home-pay';                 /* موجودی، بدهی و پرداخت‌های همین کاربر */
/* پروفایل: استان و شهر از فهرست، تاریخ از سه فهرست روز و ماه و سال */
const GEO=(A.geo||[]).map(r=>{ const t=String(r).split('|'); return {p:t[0], cities:(t[1]||'').split('،').filter(Boolean)} });
const MONF=A.monthsFa||[];
const LEAPJ=[1,5,9,13,17,22,26,30];
const leapJ=y=>LEAPJ.indexOf(((y%33)+33)%33)>-1;
const daysInJ=(y,m)=>m<=6?31:(m<=11?30:(leapJ(y)?30:29));
const geoCities=p=>{ const g=GEO.find(x=>x.p===p); return g?g.cities:[] };
function dtParts(v){
  const m=unFa(String(v||'')).replace(/[^\d/]/g,'').match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/);
  return m?{y:+m[1], m:+m[2], d:+m[3]}:null;
}
const dtTxt=t=>t?(t.y+'/'+String(t.m).padStart(2,'0')+'/'+String(t.d).padStart(2,'0')):'';
const dtFa=t=>t?(faN(t.y)+'/'+faN(String(t.m).padStart(2,'0'))+'/'+faN(String(t.d).padStart(2,'0'))):'—';
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
const S={view:'',vtab:'up',ptab:'info',ctab:'home',invF:'all',txAll:false,edit:false,errs:{},after:''};

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
      <p class="cap" style="margin:11px 2px 0">شماره را که بنویسی، کد چهاررقمی به بله می‌آید و همان‌جا
        می‌گیری. رمز و گذرواژه‌ای در کار نیست.</p>
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
        <span class="ctags">${chip(st[0],st[1])}${chip(faNum(pts)+' امتیاز')}
          ${clubIsMember()?`<span class="tag tag-club">${ico('i-medal')} ${esc(clubBadge().n)}</span>`:''}</span></div>
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
  const debt=login()?debtAmt():0;
  const bal=login()?money(walletBal()):'وارد شو و موجودی‌ات را ببین';
  const tags=debt?['بدهی '+money(debt),'پرداخت','قفل گواهی']:(PAY&&PAY.tags||['کیف پول','شارژ','صورت‌حساب']).slice(0,3);
  return `<div class="paybar anim" style="--i:1">
      <button class="pbmain" type="button" data-view="pay" aria-label="نورا پی">
        <span class="pwal" aria-hidden="true">${ico('i-wallet')}</span>
        <span class="ptx"><small>نورا پی · کیف پول${debt?' · بدهکار':''}</small>
          <b>${bal}</b>
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
      <span class="tx"><b>${esc(r.n)}${r.k==='book'&&clubIsMember()?` <span class="tag tag-club">${ico('i-medal')} عضو</span>`:''}</b>
        <small>${esc(subOf(r.k)||r.s)}</small></span>
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
const VTABS=[{k:'up',n:'پیش‌رو'},{k:'past',n:'برگزارشده'},{k:'notes',n:'نظر و نظرسنجی'}];

/* ══ باشگاه و امتیاز من ═════════════════════════════════════════════ */
/* ══ رویدادهای من: کارت‌های شخصی و جزئیات داخل خودشان ══════════════
   این‌جا فهرست رویدادهای رویدادها نیست؛ فقط چیزهای خودِ کاربر است و روی
   هر کارت که بزند، جزئیات همان رویداد (بلیت، گواهی، فایل آفلاین، نظر و
   نظرسنجی) در همان صفحه باز می‌شود، نه در صفحهٔ رویدادها. */
function myInfo(id){ return MY_INFO[id]||{} }
function noteState(id){
  const inf=myInfo(id), n=inf.note||{};
  const hasC=!!n.comment, hasS=!!(n.survey&&!n.survey.ask), askS=!!(n.survey&&n.survey.ask);
  return {hasC, hasS, askS, done:hasC&&!askS, pending:!hasC||askS, n};
}
function mineAll(){
  return [].concat(myUp().map(e=>({e,past:false})), myPast().map(e=>({e,past:true})));
}
function pendingNotes(){ return mineAll().filter(x=>{ const st=noteState(x.e.id); return !st.hasC||st.askS }) }
function chipsOf(id,past){
  const inf=myInfo(id), st=noteState(id), chips=[];
  if(inf.ticket&&inf.ticket.ok) chips.push(chip('بلیت فعال','ok'));
  if(inf.cert&&inf.cert.st==='ready') chips.push(chip(certLocked()?'گواهی · قفل بدهی':'گواهی آماده',certLocked()?'stop':'gold'));
  if(inf.cert&&inf.cert.st==='pending') chips.push(chip('گواهی در انتظار تأیید','warn'));
  if((inf.off||[]).length) chips.push(chip(faN(inf.off.length)+' فایل آفلاین'));
  if(past&&(inf.att||[]).length) chips.push(chip('کارنامهٔ حضور'));
  if(st.hasC) chips.push(chip(MY.noteDone||'نظر دادم','ok'));
  if(st.pending) chips.push(chip(st.askS?(MY.surveyAsk||'نظرسنجی'):(MY.noteAsk||'نظر'),'warn'));
  return chips.join('');
}
function evCard(e,past){
  const st=noteState(e.id);
  return `<button class="evcard" type="button" data-myev="${esc(e.id)}" aria-label="${esc(e.t)}، جزئیات">
    <span class="ec-cover" style="--g:${esc(e.g||'')}">
      ${e.poster?`<img src="${esc(e.poster)}" alt=""/>`:''}
      <span class="ec-when"><b>${faD(e.dn||'')}</b><small>${esc(monOf(e))}</small></span>
      <span class="ec-tag${past?'':' live'}">${past?'برگزار شد':esc(e.when||'')}</span>
    </span>
    <span class="ec-body">
      <b class="ec-t">${esc(e.t)}</b>
      <small class="ec-s">${esc([e.time,e.place].filter(Boolean).join(' · '))}</small>
      ${past?'':cdLine(e)}
      <span class="ec-chips">${chipsOf(e.id,past)}</span>
      <span class="ec-go">${ico('i-chev-left')} ${esc((MY.sheet||{}).open||'دیدن جزئیات')}
        ${st.pending?`<i class="ec-dot" aria-label="منتظر نظر"></i>`:''}</span>
    </span></button>`;
}
function cardsBox(cards){ return `<div class="evcards">${cards.map(x=>evCard(x.e,x.past)).join('')}</div>` }
function notesBar(){
  const p=pendingNotes();
  if(!p.length) return '';
  return `<div class="notebar anim">${ico('i-star')}
    <span class="tx"><b>${faN(p.length)} رویداد منتظر نظر توست</b>
      <small>نظر یا نظرسنجی‌ات را همان‌جا بنویس</small></span>
    <button class="btn sm primary" data-goto-notes>ببینم</button></div>`;
}
function panelUp(){
  const mine=myUp().map(e=>({e,past:false}));
  if(!mine.length) return card('پیش‌روی من',MY.lead||'',empty2('هنوز ثبت‌نامی نداری',MY.empty||''))+
    note('فهرست همهٔ رویدادها صفحهٔ خودش را دارد؛ این‌جا فقط مالِ خودت است.','i-calendar');
  return notesBar()+card('پیش‌روی من',faN(mine.length)+' رویداد ثبت‌نام‌شده — '+esc(MY.lead||''),'i-calendar',
    cardsBox(mine)+`<p class="cap" style="margin:10px 3px 0">${esc(MY.inEvent||'')}</p>`)+
    trustLine('secure');
}
function panelPast(){
  const mine=myPast().map(e=>({e,past:true}));
  if(!mine.length) return card('برگزارشده‌ها','',empty2('هنوز رویداد برگزارشده‌ای نداری','بعد از هر رویداد، ضبط و گواهی همین‌جا می‌آید.'));
  return notesBar()+card('برگزارشده‌های من',faN(mine.length)+' رویداد؛ بلیت، گواهی، ضبط و کارنامه','i-archive',
    cardsBox(mine)+`<p class="cap" style="margin:10px 3px 0">${esc(MY.inEvent||'')}</p>`)+
    trustLine('secure');
}
function panelNotes(){
  const all=mineAll();
  const pend=all.filter(x=>noteState(x.e.id).pending);
  /* یک رویداد یک ردیف دارد: یا چیزی داده‌ای، یا منتظر توست */
  const given=all.filter(x=>{ const st=noteState(x.e.id); return st.hasC&&!st.askS });
  const askRow=({e,past})=>{
    const st=noteState(e.id);
    return `<div class="tk">${ico('i-star','width:19px;height:19px;color:var(--accent-ink)')}
      <span><b>${esc(e.t)}</b>
        <small>${esc(past?'برگزار شد':'پیش‌رو')} · ${esc(e.when||e.d||'')}${st.askS?' · '+esc((st.n.survey||{}).n||'نظرسنجی'):''}</small>
        ${st.hasS?`<span class="cap">${esc((st.n.survey||{}).n||'نظرسنجی')} · ${esc(((st.n.survey||{}).answers||[]).join(' · '))}</span>`:''}
        <span class="acts">${st.hasS?chip(MY.surveyDone||'نظرسنجی پر شد','ok'):''}
          ${chip(st.askS?(MY.surveyAsk||'نظرسنجی'):(MY.noteAsk||'نظر'),'warn')}
          <button class="btn sm primary" data-myev="${esc(e.id)}" data-ask="${st.askS?'survey':'comment'}">
            ${st.askS?'شرکت در نظرسنجی':'نوشتن نظر'}</button></span></span></div>`;
  };
  const givenRow=({e})=>{
    const st=noteState(e.id), c=st.n.comment||{}, sv=st.n.survey||{};
    const body=[st.hasC?esc(c.text||'نظرت را نوشتی'):'', st.hasS?esc((sv.answers||[]).join(' · ')):''].filter(Boolean).join(' · ');
    const meta=[st.hasC?esc(c.at||'')+' · '+faN(c.stars||'۵')+' از ۵':'',
      st.hasS?esc(sv.n||'نظرسنجی'):''].filter(Boolean).join(' · ');
    return `<div class="tk">${ico('i-check','width:19px;height:19px;color:var(--ok)')}
      <span><b>${esc(e.t)}</b>
        <small>${body}</small>
        <span class="cap">${meta}</span>
        <span class="acts">${st.hasC?chip(MY.noteDone||'نظر دادم','ok'):''}${st.hasS?chip(MY.surveyDone||'نظرسنجی پر شد','ok'):''}
          <button class="btn sm quiet" data-myev="${esc(e.id)}">دیدن</button></span></span></div>`;
  };
  return card('نظر و نظرسنجی','نظر و نظرسنجی‌ات مالِ خودِ همان رویداد است؛ همین‌جا می‌بینی و می‌نویسی','i-star',
    (pend.length?`<div class="gt cap" style="margin:2px 3px 8px">منتظر نظر تو</div>`+pend.map(askRow).join(''):'')+
    (given.length?`<div class="gt cap" style="margin:14px 3px 8px">نظرها و نظرسنجی‌های تو</div>`+given.map(givenRow).join(''):'')+
    (!pend.length&&!given.length?empty2('چیزی نمانده','هر رویدادی که بگذرد، نظر و نظرسنجی‌اش همین‌جا می‌آید.'):''))+
    trustLine('privacy');
}
/* ── ورقهٔ «رویداد من»: بلیت، گواهی، آفلاین، حضور و نظر، همه در یک جا ── */
function offRow(o,id){
  const kd={pdf:'فایل', audio:'صدا', video:'ویدیو'}[o[0]]||'قلم';
  return `<div class="offrow">${ico(o[0]==='pdf'?'i-doc':o[0]==='audio'?'i-headphone':'i-play',
      'width:19px;height:19px;color:var(--ink-4)')}
    <span class="sp">${esc(o[1])}<small>${esc(kd)} · ${esc(o[2])}</small></span>
    <button class="btn sm quiet" data-off="1">${ico('i-download')} دانلود</button></div>`;
}
function myEventSheet(id){
  const e=EVENTS.find(x=>x.id===id)||PAST.find(x=>x.id===id)||{};
  const past=!EVENTS.find(x=>x.id===id), inf=myInfo(id), st=noteState(id);
  const c=(inf.cert||{}), cTxt=c.st==='ready'?'آمادهٔ دانلود':c.st==='pending'?'در انتظار تأیید سرپرست':'بعد از پایان برنامه';
  const t=(inf.ticket||{});
  const att=(inf.att||[]);
  const head=`<div class="grabber"></div>
    <div class="head">${esc(e.t||'رویداد من')}</div>
    <p class="sub" style="margin-top:6px">${esc([past?'برگزار شد':e.when,e.time,e.place].filter(Boolean).join(' · '))}</p>`;
  const countdown=past?'':cdLine(e);
  const info=`<div class="gt cap" style="margin:12px 3px 6px">${esc(GRP.info||'اطلاعات ثبت‌نام')}</div>
    <div class="stack tight">
      <div class="srow">${ico('i-ticket')}<span class="sp">کد ثبت‌نام</span><b class="num">${esc(inf.code||'—')}</b></div>
      <div class="srow">${ico('i-users')}<span class="sp">نوع شرکت</span><b>${esc(inf.kind||'حضوری')}</b></div>
      ${(inf.seat||inf.link)?`<div class="srow">${ico('i-pin')}<span class="sp">${esc(inf.seat?'جای نشستن':'راه ورود')}</span>
        <b>${esc(inf.seat||inf.link)}</b></div>`:''}
      <div class="srow">${ico('i-wallet')}<span class="sp">پرداخت‌شده</span><b>${esc(inf.pay||'رایگان')}</b></div>
    </div>`;
  const ticket=`<div class="gt cap" style="margin:12px 3px 6px">${esc(GRP.ticket||'بلیت و ورود')}</div>`+
    (t.ok===undefined
      ? `<div class="srow">${ico('i-ticket')}<span class="sp">بلیت جدا ندارد<small>با همین حساب باز می‌شود؛ کارت ورود لازم نیست</small></span></div>`
      : `<div class="row tight">
      <button class="btn sm primary" data-my-ticket="${esc(id)}">${ico('i-qr')} کارت ورود</button>
      <button class="btn sm quiet" data-my-ticket-dl="${esc(id)}">${ico('i-download')} دانلود بلیت</button>
      ${t.ok?chip('معتبر','ok'):(past?chip('بلیت مصرف شد'):chip('هنوز صادر نشده','warn'))}
    </div>`);
  const locked=certLocked();
  const cert=`<div class="gt cap" style="margin:12px 3px 6px">${esc(GRP.cert||'گواهینامه')}</div>
    <div class="srow">${ico(locked?'i-lock':'i-medal')}
      <span class="sp">${esc(locked?'قفل تا تسویهٔ نورا پی':cTxt)}
        <small>${esc(locked?(PAYINFO.debt||{}).lock||'بدهی نورا پی داری؛ گواهینامه تا تسویه دانلود نمی‌شود.'
          :(c.id?('سریال '+c.id):'با تأیید سرپرست صادر می‌شود'))}</small></span>
      ${locked?`<button class="btn sm primary" data-debtpay>${ico('i-wallet')} پرداخت بدهی</button>`
        :(c.st==='ready'?`<button class="btn sm quiet" data-my-cert="${esc(id)}">${ico('i-download')} دانلود</button>`:'')}</div>`;
  const off=`<div class="gt cap" style="margin:12px 3px 6px">${esc(GRP.off||'فایل‌های آفلاین')}</div>
    ${(inf.off||[]).map(o=>offRow(o,id)).join('')}
    <div class="row tight" style="margin-top:8px">
      <button class="btn sm quiet" data-off-all="${esc(id)}">${ico('i-download')} ${esc(MY.offAll||'دانلود همه')}</button>
      <span class="cap" style="flex:1">${esc(MY.offHint||'')}</span></div>`;
  const attBox=att.length?`<div class="gt cap" style="margin:12px 3px 6px">${esc(GRP.att||'کارنامهٔ حضور')}</div>
    <div class="steps">${att.map(r=>`<div class="step done">
      <span class="dot">${ico(r[1]==='حاضر'?'i-check':'i-close','width:13px;height:13px')}</span>
      <span class="tx"><b>${esc(r[0])}</b><small>${esc(r[1])}</small></span></div>`).join('')}</div>`:'';
  const note=st.hasC?`<div class="gt cap" style="margin:12px 3px 6px">${esc(GRP.note||'نظر و نظرسنجی')}</div>
      <div class="mycm">${ico('i-star')}<span class="tx"><b>${faN((st.n.comment||{}).stars||'۵')} از ۵ · نظر تو</b>
        <small>${esc((st.n.comment||{}).text||'')}</small>
        <span class="cap">${esc((st.n.comment||{}).at||'')}</span></span></div>
      ${st.hasS?`<div class="mycm ok">${ico('i-check')}<span class="tx"><b>${esc((st.n.survey||{}).n||'نظرسنجی')}</b>
        <small>${esc(((st.n.survey||{}).answers||[]).join(' · '))}</small></span></div>`:''}`
    :`<div class="gt cap" style="margin:12px 3px 6px">${esc(GRP.note||'نظر و نظرسنجی')}</div>
      <div class="notebar" style="margin:0">${ico('i-star')}
        <span class="tx"><b>${esc(st.askS?((st.n.survey||{}).n||'نظرسنجی')+' مانده':'نظرت را ننوشتی')}</b>
          <small>${st.askS?'یک دقیقه وقت می‌برد؛ بی‌خبر نگذار':'کوتاه بنویس؛ هر وقت خواستی'}</small></span>
        <button class="btn sm primary" data-ask="${st.askS?'survey':'comment'}" data-myev="${esc(id)}">
          ${st.askS?'شرکت در نظرسنجی':'نوشتن نظر'}</button></div>`;
  return `${head}${countdown}${info}${ticket}${cert}${attBox}${off}${note}
    ${trustLine('secure')}
    <div class="row" style="margin-top:14px"><button class="btn quiet" data-close>بستن</button></div>`;
}
function openMyEvent(id){
  if(!$('#shMyEvent')) return;
  fillSheet('shMyEvent',myEventSheet(id));
  openSheet('shMyEvent');
}

const VS={};
VS.events=function(t){
  if(!login()) return viewHead(t,'',VTABS)+gate(t);
  const body={up:panelUp,past:panelPast,notes:panelNotes}[S.vtab];
  return viewHead(t,(VTABS.find(x=>x.k===S.vtab)||{}).n||'',VTABS)+(body?body():'');
};

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
  return Object.assign({member:false, cstep:'form', form:{}, plan:'m', feeAt:'', feeNext:'',
    att:{}, voice:null, likes:{}, posts:[], chals:{}, entered:{}, seats:{}, tag:'پیشنهاد',
    joined:false, seat:false, pages:0, note:'', vote:''}, v||{});
}
function bookSet(patch){ const v=Object.assign(bookState(),patch); try{localStorage.setItem(BC_KEY,JSON.stringify(v))}catch(e){} return v }
/* ── باشگاه از خودِ داده می‌آید ───────────────────────────────────────── */
const CCLUB=N.CLUB||{}, CFEE=CCLUB.fee||{}, CGATE=CCLUB.gate||{}, CTABS=CCLUB.tabs||[];
const clubIsMember=()=>!!bookState().member;
const clubBadge=()=>(CCLUB.badge||{n:'عضو باشگاه کتاب‌خوانی',s:''});
const clubSup=()=>(N.PEOPLE||[]).find(x=>x.id===CCLUB.sup)||{};
const clubPlan=k=>{ const P=CFEE.plans||[]; return P.find(x=>x.k===k)||P[0]||{k:'m',n:'ماهانه',amount:0,s:''} };
const clubLevel=n=>{ const L=CCLUB.levels||[]; let cur=L[0]||{n:'—',at:0,perks:''}, nx=null;
  L.forEach((x,i)=>{ if(n>=x.at){cur=x; nx=L[i+1]||null} }); return {cur:cur,nx:nx} };
function clubMe(){
  const bc=bookState(), name=prof().fullName||'عضو تازه';
  return (CCLUB.board||[]).find(x=>x.me)||{n:name,l:'تازه‌وارهٔ باشگاه',s:+bc.sessions||0};
}
const clubPanelView=()=>S.ctab||(CTABS[0]||{}).k||'home';
function clubSet(patch,msg){ bookSet(patch); render(); if(msg) toast(msg) }

/* ── گام‌های ورود به باشگاه ─────────────────────────────────────────── */
function clubSteps(cur){
  const st=CGATE.steps||[], i=st.findIndex(x=>x.k===cur);
  return `<div class="clsteps anim">${st.map((x,n)=>`<span class="clst${n<i?' done':''}${n===i?' now':''}">
    <b class="n">${n<i?ico('i-check','width:12px;height:12px;'):faN(n+1)}</b>
    <span class="tx"><b>${esc(x.n)}</b><small>${esc(x.s)}</small></span></span>`).join('<i class="cllink"></i>')}</div>`;
}
function clubField(f){
  const v=(bookState().form||{})[f.k]||'';
  if(f.w==='pick')
    return `<div class="fld"><span class="hint">${esc(f.l)}</span>
      <div class="seg">${(f.opts||[]).map(o=>`<button class="segbtn${o===v?' on':''}" type="button"
        data-cf="${esc(f.k)}" data-cv="${esc(o)}" aria-pressed="${o===v}">${o===v?ico('i-check','width:13px;height:13px;'):''}${esc(o)}</button>`).join('')}</div></div>`;
  return `<div class="fld"><label class="hint" for="cf_${f.k}">${esc(f.l)}</label>
    <input class="input" id="cf_${f.k}" value="${esc(v)}" placeholder="${esc(f.ph||'')}" style="margin-top:6px"/></div>`;
}
/* درِ باشگاه: یک جلد گرافیکی، بعد فرم، بعد حق عضویت */
function clubJoin(t){
  const bc=bookState(), C=CCLUB, step=(bc.cstep==='fee'?'fee':'form');
  const req=(CGATE.fields||[]).filter(f=>f.req), have=req.filter(f=>bc.form[f.k]).length;
  const pct=req.length?Math.round(have/req.length*100):0;
  const cover=`<div class="clcover anim">
      <span class="clbadge">${ico('i-medal')} ${esc(clubBadge().n)}</span>
      <span class="clttl"><b>${esc(C.n||'باشگاه کتاب‌خوانی خط زندگی')}</b>
        <small>${esc(C.term||'')}${C.book?' · کتاب ماه: '+esc(C.book):''}</small></span>
      <span class="clstats">
        <span><b class="num">${faN(C.members||0)}</b><small>عضو</small></span>
        <span><b class="num">${faN(C.meetings||0)}</b><small>جلسه</small></span>
        <span><b class="num">${faN((CCLUB.podcast||{}).eps?CCLUB.podcast.eps.length:0)}</b><small>قسمت پادکست</small></span>
        <span><b class="num">${faN((CCLUB.workshops||[]).length)}</b><small>کارگاه</small></span></span>
      <span class="cllead">${esc(CGATE.lead||'')}</span></div>`;
  const formCard = step==='form'
    ? `<div class="card acct anim">${donut(pct,'٪'+faN(pct),'فرم عضویت','small')}
        <div class="head" style="margin-top:8px">${ico('i-idcard')} فرم عضویت</div>
        <p class="cap" style="margin-top:5px">ساختهٔ ${esc(CGATE.maker||'سرپرست باشگاه')}؛ همه‌اش انتخاب است، تایپ لازم نیست.</p>
        <div class="clsform">${(CGATE.fields||[]).map(clubField).join('')}</div>
        <button class="btn primary block" style="margin-top:12px" data-clubsend>
          ${ico('i-send')} فرم را برای سرپرست بفرست</button></div>`
    : `<div class="card acct anim"><div class="head">${ico('i-check')} فرم سرپرست</div>
        <p class="cap" style="margin-top:5px">فرستاده شد؛ <b>حالا حق عضویت</b></p>
        <div class="stack tight" style="margin-top:8px">${(CGATE.fields||[]).filter(f=>bc.form[f.k]).map(f=>
          `<div class="srow">${ico(f.w==='pick'?'i-check':'i-pen')}<span class="sp">${esc(f.l)}<small>${esc(bc.form[f.k])}</small></span></div>`).join('')}</div>
        <div class="row" style="margin-top:12px"><button class="btn quiet" data-clubedit>${ico('i-pen')} ویرایش فرم</button>
          <span class="sp" style="flex:1"></span><span class="tag ok">به دست سرپرست رسید</span></div></div>`;
  const feeCard = step==='fee'
    ? `<div class="card acct anim"><div class="head">${ico('i-wallet')} حق عضویت باشگاه</div>
        <p class="cap" style="margin-top:5px">${esc(CFEE.cycle||'ماهانه')} · ${esc(CFEE.note||'')}</p>
        <div class="clplans">${(CFEE.plans||[]).map(p=>`<button class="clplan${(bc.plan||'m')===p.k?' on':''}" type="button" data-clanplan="${esc(p.k)}">
          <b>${esc(p.n)}</b><small class="num">${money(p.amount)}</small>
          <span class="cap">${esc(p.s||'')}</span>${(bc.plan||'m')===p.k?`<span class="pmark">${ico('i-check','width:12px;height:12px;')}</span>`:''}</button>`).join('')}</div>
        <div class="npstats" style="margin-top:12px">
          <span><b class="num">${money(clubPlan(bc.plan).amount)}</b><small>پلن ${esc(clubPlan(bc.plan).n)}</small></span>
          <span><b>${esc(CFEE.due||'')}</b><small>سررسید هر ماه</small></span>
          <span><b class="num">${money(CFEE.student||0)}</b><small>سهم دانشجو</small></span></div>
        <button class="btn primary block" style="margin-top:12px" data-clubsend2>${ico('i-shield')} پرداخت با نورا پی و باز شدن پنل</button>
        <p class="cap" style="margin-top:8px">${esc(CFEE.studentNote||'')}</p></div>`
    : '';
  return viewHead(t,CGATE.n||'ورود به باشگاه',null)+`<div class="panel">
    ${cover}${clubSteps(step)}
    <div class="clgrid">${formCard}${feeCard}</div>
    ${clubSupervisor()}${trustLine('club')}</div>`;
}
/* ── ورقهٔ پرداخت حق عضویت ─────────────────────────────────────────── */
function clubFeeSheet(){
  const bc=bookState(), plan=clubPlan(bc.plan), ms=(CFEE.methods||['wallet','bale','card']);
  fillSheet('shClub',`<div class="grabber"></div>
    <div class="head">${ico('i-wallet')} حق عضویت باشگاه</div>
    <p class="cap" style="margin-top:5px">${esc(CFEE.note||'')}</p>
    <div class="clplans" style="margin-top:10px">${(CFEE.plans||[]).map(p=>`<button class="clplan${(bc.plan||'m')===p.k?' on':''}" type="button" data-clanplan="${esc(p.k)}">
      <b>${esc(p.n)}</b><small class="num">${money(p.amount)}</small><span class="cap">${esc(p.s||'')}</span></button>`).join('')}</div>
    <div class="payamt"><span>${esc(plan.n)}</span><b class="num">${money(plan.amount)}</b>
      <span class="cap">${esc(plan.s||'')}</span></div>
    <div class="payms" style="grid-template-columns:1fr">${ms.map(k=>{const m=methodOf(k);
      return `<button class="paym" data-clubm="${esc(k)}">
        <span class="pm-ic">${ico(m.i||'i-wallet')}</span>
        <span class="tx"><b>${esc(m.n||k)}</b><small>${esc(m.s||'')}</small></span>
        <span class="pm-go">${ico('i-chev-left')}</span></button>`}).join('')}</div>
    <div class="row" style="margin-top:12px"><span class="sp" style="flex:1"></span>
      <button class="btn quiet" data-close>بعداً</button></div>
    <p class="cap" style="margin-top:10px">${esc(CFEE.studentNote||'')}</p>`);
  openSheet('shClub');
}
/* ── سرپرست و قوانین ───────────────────────────────────────────────── */
function clubSupervisor(){
  const sup=clubSup(), g=CCLUB.group||{};
  return `<div class="clgrid">
    <div class="card acct anim"><div class="head">${ico('i-users')} سرپرست باشگاه</div>
      <div class="srow" style="margin-top:8px">
        <span class="qi" style="width:44px;height:44px;border-radius:15px;display:grid;place-items:center;background:linear-gradient(150deg,#7A5A2A,#123A7A);color:#fff;font-weight:700;font-size:17px">${esc(String(sup.n||'م').slice(0,1))}</span>
        <span class="sp">${esc(sup.n||'مریم داوودی')}<small>${esc(sup.r||'سرپرست باشگاه کتاب‌خوانی')}</small></span>
        <button class="btn sm quiet" data-go="support">پرسش</button></div>
      <details class="npmore2" style="margin-top:10px"><summary>${ico('i-doc')} قوانین باشگاه</summary>
        ${(CCLUB.rules||[]).map(r=>`<div class="srow">${ico('i-check')}<span class="sp">${esc(r)}</span></div>`).join('')}</details></div>
    <div class="card acct anim"><div class="head">${ico('i-link')} گروه و لینک اختصاصی</div>
      <p class="cap" style="margin-top:5px">${esc(g.lead||'')}</p>
      <div class="srow">${ico('i-users')}<span class="sp">${esc(g.n||'گروه اعضا')}
        <small class="num" dir="ltr">${esc(g.code||'')}</small></span>
        <button class="btn sm quiet" data-copy="${esc(g.link||'')}" data-copy-msg="لینک گروه رونوشت شد">${ico('i-link')} رونوشت</button></div>
      ${(g.rules||[]).map(r=>`<div class="srow">${ico('i-lock')}<span class="sp">${esc(r)}</span></div>`).join('')}</div>
  </div>`;
}
/* ── کارت عضویت: نشان باشگاه، سطح و حلقهٔ پیشرفت ───────────────────── */
function clubCard(){
  const bc=bookState(), me=clubMe(), L=clubLevel(+me.s||0), C=CCLUB;
  const next=L.nx?Math.max(0,L.nx.at-(+me.s||0)):0;
  const from=L.cur.at||0, to=L.nx?L.nx.at:from+1, pct=L.nx?Math.round(((+me.s||0)-from)/Math.max(1,to-from)*100):100;
  return `<div class="clubcard anim">
    ${donut(pct,faN(+me.s||0),'جلسه‌های باشگاه','gold')}
    <span class="ctx"><b>${esc(clubBadge().n)}</b>
      <small>${esc(me.n||'')} · سطح ${esc(L.cur.n||'')}${bc.voice?' · ضبط پادکست':''}</small>
      <span class="pmeta">${chip((C.term||'')+' فعال','ok')}${bc.feeAt?chip('حق عضویت پرداخت شد','ok'):chip('حق عضویت مانده','warn')}</span>
      <small class="cap">${L.nx?'تا «'+esc(L.nx.n)+'» '+faN(next)+' جلسه مانده · پاداش: '+esc(L.nx.perks||''):'بالاترین سطح باشگاه؛ حالا میزبانی هم دست توست.'}</small>
    </span></div>`;
}
/* ── خبرهای سرپرست ─────────────────────────────────────────────────── */
function clubNews(){
  return `<div class="clnews">${(CCLUB.news||[]).map(n=>`<span class="cn">
    <span class="ic">${ico(n.i||'i-sparkle')}</span>
    <span class="tx"><b>${esc(n.t)}</b><small>${esc(n.d||'')}</small></span></span>`).join('')}</div>`;
}
/* ── خانه: عضویت، جلسهٔ هفته، کارهای من ────────────────────────────── */
function clubTasks(){
  const bc=bookState(), VOTE=CCLUB.vote||[];
  return `<div class="bktasks">${[
    {on:bc.seat,  t:'صندلی جلسهٔ پنجشنبه', s:bc.seat?'رزرو شد؛ یک ساعت قبل یادآوری می‌کنیم':'جای محدود؛ از همین‌جا رزرو کن',
      act:bc.seat?'':`<button class="btn sm primary" data-seat>رزرو صندلی</button>`, i:'i-users'},
    {on:bc.pages>=10, t:'پیشرفت مطالعه', s:bc.pages?faN(bc.pages)+' صفحه از ۲۰۰ ثبت شده':'صفحه‌هایی که خوانده‌ای را ثبت کن',
      act:`<span class="bt" style="display:flex;gap:6px"><button class="btn sm quiet" data-pages="10">+۱۰</button>
        <button class="btn sm quiet" data-pages="25">+۲۵</button></span>`, i:'i-book'},
    {on:!!bc.note, t:'یادداشت جلسه', s:bc.note?'ذخیره شده؛ سرپرست پیش از جلسه می‌خواند':'یک جمله هم کافی است',
      act:bc.note?chip('انجام شد','ok'):'<span class="cap">مانده</span>', i:'i-pen'},
    {on:!!bc.vote, t:'رأی کتاب ماه بعد', s:bc.vote?'رأیت ثبت شد؛ نتیجه زنده به‌روز می‌شود':'از میان '+faN(VOTE.length)+' کتاب یکی را انتخاب کن',
      act:bc.vote?chip('انجام شد','ok'):'<span class="cap">مانده</span>', i:'i-star'}]
    .map(x=>`<div class="bktask ${x.on?'done':''}"><span class="bx">${ico(x.on?'i-check':x.i)}</span>
      <span class="tx"><b>${esc(x.t)}</b><small>${esc(x.s)}</small></span>${x.act}</div>`).join('')}</div>`;
}
function clubHome(){
  const bc=bookState(), C=CCLUB, meet=C.meet||[], plan=clubPlan(bc.plan);
  const m0=meet[0]||{}, m1=meet[1]||{};
  return clubCard()+
    card('جلسهٔ این هفته',(C.session||'')+' · میزبان '+(clubSup().n||'—'),'i-calendar',
      `<div class="clmeet">
        <span class="clm-date"><b>${esc(m0.w||'')}</b><small>${esc(m0.mode||'')}</small></span>
        <span class="tx"><b>${esc(m0.c||C.next||'جلسهٔ پیش‌رو')}</b>
          <small>${faN(m0.took||0)} نفر تا حالا ثبت کرده‌اند${m1.w?' · جلسهٔ بعد: '+esc(m1.w):''}</small>
          <span class="clatt">${['حاضر','آنلاین','نمی‌آیم'].map(st=>
            `<button class="tag${bc.att[m0.k]===st?' on':''}" type="button" data-att="${esc(m0.k||'')}" data-attst="${esc(st)}">${esc(st)}</button>`).join('')}
            ${bc.att[m0.k]?chip('ثبت شد','ok'):chip('ثبت حضور مانده','warn')}</span></span></div>`)+
    clubTasks()+
    card('کتاب ماه و پیشرفت من',esc(C.book||'')+' · '+esc(C.bookBy||''),'i-book',
      `<div class="clread">${donut(Math.round(Math.min(200,+bc.pages||0)/200*100),'٪'+faN(Math.round(Math.min(200,+bc.pages||0)/200*100)),'پیشرفت من')}
        <span class="tx"><b>${faN(bc.pages||0)} صفحه از ۲۰۰</b>
          <small>کتاب ماه: ٪${faN(C.progress||0)} خوانده شده · جلسهٔ بعد ${esc(C.next||'')}</small>
          <span class="bartrack"><i style="width:${Math.min(100,+C.progress||0)}%"></i></span></span>
        <span class="clacts"><button class="btn sm quiet" data-pages="10">+۱۰</button>
          <button class="btn sm quiet" data-pages="25">+۲۵</button></span></div>
      <label class="lbl" for="bcNote" style="display:block;margin-top:12px;font-size:11.5px;color:var(--ink-3);font-weight:600">یادداشت یک‌صفحه‌ای</label>
      <textarea class="input" id="bcNote" rows="3" placeholder="مثلاً فصل ۴: راوی چه چیزی را پنهان می‌کند؟" style="margin-top:6px">${esc(bc.note)}</textarea>
      <div class="row" style="width:100%;margin-top:10px"><button class="btn sm primary" data-save-note>
        ${ico('i-check')} ذخیرهٔ یادداشت</button><span class="sp" style="flex:1"></span>
        <span class="cap">${bc.note?'ذخیره شده، قابل ویرایش':'خالی'}</span></div>`)+
    `<div class="clgrid">
      ${card('حق عضویت باشگاه',(CFEE.cycle||'ماهانه')+' · سرپرست تعیین می‌کند','i-wallet',
        `<div class="npstats">
          <span><b class="num">${money(plan.amount)}</b><small>پلن ${esc(plan.n)}</small></span>
          <span><b>${esc(bc.feeNext||CFEE.due||'')}</b><small>سررسید بعدی</small></span>
          <span>${chip(bc.feeAt?'فعال':'مانده',bc.feeAt?'ok':'warn')}<small>وضعیت</small></span></div>
        <button class="btn primary block" style="margin-top:10px" data-clubpay>${ico('i-shield')} ${bc.feeAt?'تمدید حق عضویت':'پرداخت حق عضویت'}</button>`)}
      ${card('خبرهای سرپرست','',"i-bell",clubNews())}
    </div>`+
    card('گروه و لینک اختصاصی',esc((CCLUB.group||{}).lead||''),'i-users',
      `<div class="srow">${ico('i-users')}<span class="sp">${esc((CCLUB.group||{}).n||'گروه اعضا')}
          <small class="num" dir="ltr">${esc((CCLUB.group||{}).code||'')}</small></span>
        <button class="btn sm quiet" data-copy="${esc((CCLUB.group||{}).link||'')}" data-copy-msg="لینک گروه رونوشت شد">${ico('i-link')} رونوشت</button></div>`)+
    trustLine('club');
}
/* ── جلسه‌ها: هفتگی، ثبت حضور، سطح‌بندی ─────────────────────────────── */
function clubMeet(){
  const bc=bookState(), C=CCLUB, me=clubMe(), L=clubLevel(+me.s||0);
  const meet=(C.meet||[]).map((m,i)=>`<div class="clmeet${i===0?' now':''}">
      <span class="clm-n">${faN(i+1)}</span>
      <span class="tx"><b>${esc(m.c||'')}</b>
        <small>${esc(m.w||'')} · ${esc(m.mode||'')} · میزبان ${esc(m.host||'')}${m.took?' · '+faN(m.took)+' نفر حاضر':''}</small>
        <span class="clatt">${['حاضر','آنلاین','نمی‌آیم'].map(st=>
          `<button class="tag${bc.att[m.k]===st?' on':''}" type="button" data-att="${esc(m.k)}" data-attst="${esc(st)}">${esc(st)}</button>`).join('')}
          ${bc.att[m.k]?chip('ثبت شد','ok'):''}</span></span></div>`).join('');
  const levels=(C.levels||[]).map((x,i)=>`<div class="lvrow${x.k===L.cur.k?' cur':''}">
      <span class="lvn">${faN(i+1)}</span>
      <span class="tx"><b>${esc(x.n)}</b><small>از ${faN(x.at)} جلسه · ${esc(x.perks||'')}</small></span>
      ${x.k===L.cur.k?chip('سطح من','ok'):''}</div>`).join('');
  const board=(C.board||[]).map((b,i)=>`<span class="clmem">
      <span class="av">${esc(String(b.n||'ع').slice(0,1))}</span>
      <span class="tx"><b>${esc(b.n)}${b.me?' (تو)':''}</b><small>${esc(b.l)} · ${faN(b.s)} جلسه</small></span>
      ${i<3?`<span class="medal m${i+1}">${ico('i-medal')}</span>`:''}</span>`).join('');
  return `<div class="clgrid">
      ${card('جلسه‌های هفتگی',faN((C.meet||[]).length)+' جلسه پیش‌رو · '+(C.session||''),'i-calendar',meet)}
      ${card('سطح‌بندی اعضا','حضور هر جلسه یک پله جلو می‌برد','i-medal',levels)}
    </div>
    ${card('اعضای باشگاه',faN(C.members||0)+' عضو از '+faN(C.cap||0)+' جا','i-users',`<div class="clmems">${board}</div>`)}
    ${card('ثبت حضور من','حضور، آنلاین و غیبت با یادداشت','i-check',
      (C.att||[]).map(a=>`<div class="srow">${ico(a.st.indexOf('حاضر')===0?'i-check':'i-clock')}
        <span class="sp">${esc(a.c)}<small>${esc(a.d)}</small></span>${chip(a.st,a.st.indexOf('حاضر')===0?'ok':'warn')}</div>`).join(''))}
    ${trustLine('club')}`;
}
/* ── کتاب و پادکست ──────────────────────────────────────────────────── */
function clubVoiceForm(){
  const bc=bookState(), call=(CCLUB.podcast||{}).call||{};
  if(bc.voice)
    return `<div class="srow">${ico('i-check')}<span class="sp">فرم ضبط پادکست فرستاده شد
        <small>${esc(bc.voice.role||'')}${bc.voice.slot?' · '+esc(bc.voice.slot):''}</small></span>${chip('در نوبت سرپرست','ok')}</div>`;
  return `<div class="seg">${(call.roles||[]).map(r=>`<button class="segbtn${bc.voiceRole===r?' on':''}" type="button"
      data-cvoice="${esc(r)}" aria-pressed="${bc.voiceRole===r}">${bc.voiceRole===r?ico('i-check','width:13px;height:13px;'):''}${esc(r)}</button>`).join('')}</div>
    <div class="seg" style="margin-top:8px">${(call.slots||[]).map(s=>`<button class="segbtn${bc.voiceSlot===s?' on':''}" type="button"
      data-cslot="${esc(s)}" aria-pressed="${bc.voiceSlot===s}">${esc(s)}</button>`).join('')}</div>
    <div class="row" style="margin-top:12px"><button class="btn primary" data-cvoice-send>
      ${ico('i-send')} فرم را بفرست</button><span class="sp" style="flex:1"></span>
      <span class="cap">${esc(call.need?call.need[0]:'')}</span></div>`;
}
function clubMedia(){
  const bc=bookState(), C=CCLUB, P=C.podcast||{};
  const pct=Math.max(0,Math.min(100,+C.progress||0)), mine=Math.round(Math.min(200,+bc.pages||0)/200*100);
  const hero=`<div class="clbook anim">
      <span class="clbk-cover" style="--g:linear-gradient(150deg,#2E6B7A,#0B2447)">${ico('i-book')}
        <b>${esc(C.book||'')}</b><small>${esc(C.bookBy||'')}</small></span>
      <span class="tx"><span class="clbk-k">${ico('i-star')} کتاب ماه · ${esc(C.term||'')}</span>
        <b class="clbk-t">${esc(C.book||'')}</b>
        <small>${esc(C.bookBy||'')} · ${esc(C.session||'')}</small>
        ${donut(pct,'٪'+faN(pct),'پیشرفت کتاب ماه')}
        <span class="bartrack"><i style="width:${pct}%"></i></span>
        <span class="clbk-stats">
          <span><b class="num">${faN(C.members||0)}</b><small>عضو</small></span>
          <span><b class="num">${faN(C.meetings||0)}</b><small>جلسه</small></span>
          <span><b class="num">${faN(bc.pages||0)}</b><small>صفحهٔ من</small></span>
          <span><b class="num">${faN((C.shelf||[]).length)}</b><small>کتاب قفسه</small></span></span>
        <span class="clread2">${ico('i-book')} پیشرفت من ٪${faN(mine)}
          <button class="btn sm quiet" data-pages="10">+۱۰</button>
          <button class="btn sm quiet" data-pages="25">+۲۵</button></span></span></div>`;
  const books=(C.books||[]).map(b=>`<div class="clbkrow">
      <span class="bk-th">${ico(b.kind==='کتاب ماه'?'i-star':b.kind==='خلاصه'?'i-headphone':'i-book')}</span>
      <span class="tx"><b>${esc(b.t)}</b><small>${esc(b.by||'')}${b.min?' · '+faN(b.min)+' دقیقه':''}</small>
        <span class="cap">${esc(b.note||'')}</span></span>
      <span class="acts">${chip(b.kind||'','gold')}
        <button class="btn sm quiet" data-watch="${esc(b.t)}">${ico(b.kind==='خلاصه'?'i-headphone':'i-book')} ${b.kind==='خلاصه'?'شنیدن':'باز کردن'}</button></span></div>`).join('');
  const eps=(P.eps||[]).map((e,i)=>`<div class="pdcard${i===0?' now':''}">
      <button class="pdplay" type="button" data-watch="${esc(e.n)}" aria-label="پخش ${esc(e.n)}">${ico('i-play-f')}</button>
      <span class="tx"><b>${esc(e.n)}</b><small>${esc(e.at||'')} · ${faN(e.min||0)} دقیقه · ${esc(P.host||'')}</small>
        <span class="pddur"><i style="width:${Math.min(100,Math.round((e.min||0)/45*100))}%"></i></span></span>
      ${chip(e.st||'',e.st==='تازه'?'gold':'')}</div>`).join('');
  const vote=bc.vote, VOTE=C.vote||[], tot=VOTE.reduce((a,b)=>a+(+b.n||0),0)+(vote?1:0);
  return hero+
    `<div class="clgrid">
      ${card('معرفی و خلاصهٔ کتاب',faN((C.books||[]).length)+' کتاب باشگاه','i-book',`<div class="clbooks">${books}</div>`)}
      ${card('پادکست '+(P.n||'نبض ورق'),esc(P.lead||'')+' · '+esc(P.studio||''),'i-headphone',
        `<div class="clpod">${eps}</div>
         <div class="npfoot">${ico('i-play-f')} ضبط قسمت‌ها در استودیوی نورا انجام می‌شود؛ اعضا می‌توانند در ضبط شرکت کنند.</div>`)}
    </div>`+
    card('دعوت به ضبط پادکست','فرمی که سرپرست گذاشته؛ اسمت پای قسمت می‌آید','i-star',clubVoiceForm())+
    card('کتاب ماه بعد را با هم انتخاب کنیم','رأی تو در فهرست ماه بعد حساب می‌شود','i-star',
      `<div class="votebox">${VOTE.map(v=>{const n=(+v.n||0)+(vote===v.k?1:0), pc2=tot?Math.round(n/tot*100):0;
        return `<button class="voteopt${vote===v.k?' on':''}" data-vote="${esc(v.k)}" aria-pressed="${vote===v.k}">
          <span class="vck">${ico('i-check')}</span>
          <span class="vbar"><span class="vtop"><b>${esc(v.t)}</b><small>${esc(v.by)}</small>
            <span class="num">${faN(n)} رأی</span></span>
            <span class="vtrack"><i style="width:${pc2}%"></i></span></span></button>`}).join('')}</div>
       <p class="cap" style="margin:8px 2px 0">${vote?'رأیت ثبت شد؛ نتیجه زنده به‌روز می‌شود.':'با زدن هر گزینه، رأیت ثبت می‌شود.'}</p>`)+
    card('قفسهٔ باشگاه','کتاب‌های ماه گذشته','i-archive',
      `<div class="clshelf">${(C.shelf||[]).map(b=>`<span class="clbk" style="--g:linear-gradient(150deg,${esc(b.c||'#2E6B7A')},#0B2447)">
        <b>${esc(b.t)}</b><small>${esc(b.by)}</small><span class="st">${'★'.repeat(Math.round(+b.r||0))}</span>
        <span class="cap">${esc(b.d)}</span></span>`).join('')}</div>`)+
    card('جلسه‌های گذشته','ضبط هر جلسه هست؛ غایب هم عقب نمی‌ماند','i-play-f',
      `<div class="clpast">${(C.log||[]).map(l=>`<span class="tk">${ico('i-play-f','width:19px;height:19px;color:var(--ink-4)')}
        <span><b>${esc(l.t)}</b><small>${esc(l.d)} · ${faN(l.n)} نفر حاضر</small>
          <span class="acts"><button class="btn sm quiet" data-watch="${esc(l.t)}">${ico('i-play-f')} تماشا</button></span></span></span>`).join('')}</div>`)+
    trustLine('club');
}
/* ── مسابقه، چالش و کارگاه ─────────────────────────────────────────── */
function clubGame(){
  const bc=bookState(), C=CCLUB, me=clubMe();
  const contests=(C.contests||[]).map((c,i)=>`<div class="clcontest g${i+1}">
      <span class="cc-ttl">${ico('i-medal')} ${esc(c.n)}</span>
      <span class="cc-d">${esc(c.d)}</span>
      <span class="cc-meta">${chip('تا '+esc(c.until||''))}${chip(faN(c.entrants||0)+' نفر')}${chip(c.prize||'','gold')}</span>
      ${bc.entered[c.k]?chip('ثبت‌نام کردی','ok'):(c.state==='open'
        ?`<button class="btn sm primary" data-contest="${esc(c.k)}">شرکت می‌کنم</button>`:chip('به‌زودی','warn'))}</div>`).join('');
  const chals=(C.challenges||[]).map(ch=>{
    const mine=+bc.chals[ch.k]||0, pc=Math.min(100,Math.round(mine/ch.goal*100)), done=mine>=ch.goal;
    return `<div class="clchal${done?' done':''}">${donut(pc,faN(mine),ch.n,done?'ok':'')}
      <span class="tx"><b>${esc(ch.n)}</b><small>${esc(ch.d)}</small>
        <span class="cap">${faN(mine)} از ${faN(ch.goal)} ${esc(ch.unit||'')} · پاداش ${faN(ch.reward||0)} امتیاز</span></span>
      ${done?chip('تمام شد','ok'):`<button class="btn sm quiet" data-chal="${esc(ch.k)}">+ یک ${esc(ch.unit||'')}</button>`}</div>`}).join('');
  const ws=(C.workshops||[]).map(w=>`<div class="clws">
      <span class="ic">${ico('i-pen')}</span>
      <span class="tx"><b>${esc(w.t)}</b><small>${esc(w.d)} · میزبان ${esc(w.host)}</small>
        <span class="cap">${faN(w.left||0)} جا مانده از ${faN(w.seats||0)}</span></span>
      <span class="acts">${chip(w.price?money(w.price):'رایگان',w.price?'':'ok')}
        ${bc.seats[w.k]?chip('جا گرفتی','ok'):`<button class="btn sm primary" data-clubw="${esc(w.k)}">ثبت‌نام</button>`}</span></div>`).join('');
  return `<div class="clgrid">
      ${card('مسابقه‌های ماهانه',faN((C.contests||[]).length)+' مسابقه باز','i-medal',`<div class="clconts">${contests}</div>`)}
      ${card('چالش‌های باشگاه','کوتاه، روزانه و با امتیاز','i-star',`<div class="clchals">${chals}</div>`)}
    </div>
    ${card('کارگاه‌های باشگاه','کارگاه‌های ویژهٔ اعضا؛ پرداخت با نورا پی','i-pen',`<div class="clwss">${ws}</div>`)}
    ${card('جایگاه من',esc(me.l||'')+' · '+faN(+me.s||0)+' جلسه','i-chart',
      `<div class="bartrack"><i style="width:${Math.min(100,Math.round((+me.s||0)/20*100))}%"></i></div>
       <p class="cap" style="margin-top:8px">هر مسابقه و چالش، امتیاز باشگاه و یک گام به سطح بعدی است.</p>`)}
    ${trustLine('club')}`;
}
/* ── تریبون آزاد ───────────────────────────────────────────────────── */
function clubTalk(){
  const bc=bookState(), T=CCLUB.tribune||{}, mine=bc.posts||[];
  const all=mine.concat(T.posts||[]);
  const posts=all.map(p=>{const liked=bc.likes[p.k], n=(+p.likes||0)+(liked?1:0);
    return `<div class="trpost${p.mine?' mine':''}">
      <span class="tr-av">${esc(p.g||String(p.n||'ع').slice(0,1))}</span>
      <span class="tx"><b>${esc(p.n||'عضو باشگاه')} <span class="tag">${esc(p.tag||'نظر')}</span></b>
        <small>${esc(p.at||'')}</small>
        <span class="cap">${esc(p.t||'')}</span></span>
      <button class="likebtn${liked?' on':''}" data-like="${esc(p.k)}" aria-pressed="${!!liked}"
        aria-label="پسندیدن">${ico('i-star')}<b class="num">${faN(n)}</b></button></div>`}).join('');
  return card('تریبون آزاد',faN(all.length)+' نظر و پیشنهاد عضوها','i-chat',
      `<div class="trnew">
        <div class="seg">${(T.tags||[]).map(t=>`<button class="segbtn${bc.tag===t?' on':''}" type="button"
          data-ctag="${esc(t)}" aria-pressed="${bc.tag===t}">${esc(t)}</button>`).join('')}</div>
        <textarea class="input" id="trText" rows="3" maxlength="${faN(T.max||280)}" aria-label="نظر یا پیشنهادت"
          placeholder="کوتاه و روشن بنویس؛ سرپرست هر هفته می‌خواند" style="margin-top:10px;width:100%"></textarea>
        <div class="row" style="margin-top:10px"><button class="btn primary" data-post>${ico('i-send')} بفرست</button>
          <span class="sp" style="flex:1"></span><span class="cap">${esc(T.lead||'')}</span></div></div>
      <div class="gt cap" style="margin:14px 3px 6px">نظرهای اعضا</div>
      <div class="trposts">${posts}</div>
      <div class="srow" style="margin-top:10px">${ico('i-users')}<span class="sp">${esc(clubSup().n||'سرپرست باشگاه')}
        <small>سرپرست باشگاه؛ پیشنهادها را می‌خواند و هر هفته یکی را جلو می‌برد</small></span>
        <button class="btn sm quiet" data-go="support">پرسش</button></div>`)+
    trustLine('club');
}
/* ── خود پنل ───────────────────────────────────────────────────────── */
function clubPanel(t){
  const C=CCLUB, v=clubPanelView();
  const body = v==='meet'?clubMeet() : v==='media'?clubMedia() : v==='game'?clubGame() : v==='talk'?clubTalk() : clubHome();
  const sub=(C.term||'')+(C.book?' · '+C.book:'');
  return viewHead(t,sub,CTABS,'ctab')+`<div class="panel">${body}</div>`;
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
/* کادرهای انتخاب: هر جا فهرست هست، تایپ لازم نیست */
const selOpts=(cur,list,ph)=>{
  const C=String(cur===undefined||cur===null?'':cur);
  return `<option value=""${C?'':' selected'} disabled>${esc(ph||'انتخاب کن')}</option>`+
    list.map(o=>{ const v=String(o&&o.v!==undefined?o.v:o), l=(o&&o.l!==undefined)?o.l:o;
      return `<option value="${esc(v)}"${v===C?' selected':''}>${esc(l)}</option>` }).join('');
};
function pickEdit(f,p){
  const cur=String(p[f.k]||''), opts=f.opts||[];
  if(opts.length<=3)                 /* دو سه گزینه: دکمه، نه فهرست */
    return `<div class="seg" role="group" aria-label="${esc(f.l)}">
      ${opts.map(o=>`<button class="segbtn${o===cur?' on':''}" type="button" data-fpick="${esc(f.k)}" data-val="${esc(o)}">${esc(o)}</button>`).join('')}
      <input type="hidden" id="f_${f.k}" value="${esc(cur)}"/></div>`;
  return `<select class="input" id="f_${f.k}">${selOpts(cur,opts,'انتخاب کن')}</select>`;
}
function dateEdit(f,p){
  const pk=f.pick||{}, from=pk.from||1330, to=pk.to||1390;
  const t=dtParts(p[f.k])||{y:to-25,m:1,d:1};
  const years=[]; for(let y=to;y>=from;y--) years.push({v:y,l:faN(y)});
  const months=MONF.map((n,i)=>({v:i+1,l:n}));
  const days=[]; for(let d=1;d<=daysInJ(t.y,t.m);d++) days.push({v:d,l:faN(d)});
  return `<div class="datepick">
    <select class="input sm" id="f_${f.k}_d" aria-label="روز">${selOpts(t.d,days)}</select>
    <select class="input sm" id="f_${f.k}_m" aria-label="ماه">${selOpts(t.m,months)}</select>
    <select class="input sm" id="f_${f.k}_y" aria-label="سال">${selOpts(t.y,years)}</select>
    <input type="hidden" id="f_${f.k}" value="${esc(dtTxt(t))}"/></div>`;
}
function hintLine(f){
  const bits=[];
  if(f.lock) bits.push('تأییدشده؛ برای عوض‌کردنش با پشتیبانی حرف بزن');
  else if(f.w==='geo'||f.w==='city') bits.push('از فهرست انتخاب کن؛ تایپ لازم نیست');
  else if(f.w==='date') bits.push('از فهرست روز و ماه و سال بردار');
  else if(f.w==='pick') bits.push('');
  else if(f.hint) bits.push(f.hint);
  const t=bits.filter(Boolean);
  return t.length?`<span class="hint" id="h_${f.k}">${esc(t.join('؛ '))}</span>`:'';
}
function fieldEdit(f,p){
  const bad=S.errs[f.k], v=f.lock?phone():String(p[f.k]||'');
  let box;
  if(f.lock) box=`<input class="input num" id="f_${f.k}" value="${esc(faN(v))}" readonly aria-readonly="true"/>`;
  else if(f.w==='geo') box=`<select class="input" id="f_${f.k}">${selOpts(String(p[f.k]||''),GEO.map(g=>g.p),'استانت را انتخاب کن')}</select>`;
  else if(f.w==='city') box=`<select class="input" id="f_${f.k}">${selOpts(String(p[f.k]||''),geoCities(String(p.province||'')),'شهرت را انتخاب کن')}</select>`;
  else if(f.w==='date') box=dateEdit(f,p);
  else if(f.w==='pick') box=pickEdit(f,p);
  else box=`<input class="input${f.input==='numeric'||f.w==='num'?' num':''}" id="f_${f.k}" name="${f.k}" type="${f.input==='email'?'email':'text'}"
    ${f.w==='num'||f.input==='numeric'?'inputmode="numeric"':''} ${f.max?`maxlength="${f.max}"`:''}
    value="${esc(v)}" placeholder="${esc(f.ph||'')}" ${bad?`aria-invalid="true"`:(f.hint?`aria-describedby="h_${f.k}"`:'')}/>`;
  return `<label class="lbl" for="f_${f.k}" style="margin:0">${esc(f.l)}${f.req?'':' <span class="cap">اختیاری</span>'}</label>
    ${box}
    ${bad?`<span class="err" id="e_${f.k}" role="alert">${esc(bad)}</span>`:hintLine(f)}`;
}
/* شهرها با استان عوض می‌شوند و روزها با ماه و سال */
function syncCity(){
  const sel=$('#f_province'), box=$('#f_city'); if(!sel||!box) return;
  const list=geoCities(sel.value), cur=box.value;
  box.innerHTML=selOpts(list.indexOf(cur)>-1?cur:'',list,'شهرت را انتخاب کن');
}
function syncDate(k){
  const y=$('#f_'+k+'_y'), m=$('#f_'+k+'_m'), d=$('#f_'+k+'_d'), hid=$('#f_'+k);
  if(!y||!m||!d||!hid) return;
  const days=[]; for(let i=1;i<=daysInJ(+y.value,+m.value);i++) days.push({v:i,l:faN(i)});
  const keep=+d.value<=days.length?+d.value:days.length;
  d.innerHTML=selOpts(keep,days);
  hid.value=dtTxt({y:+y.value,m:+m.value,d:keep});
}
/* انتخاب‌های دکمه‌ای: جنسیت و مانندش */
function pickSet(k,val){
  const hid=$('#f_'+k); if(hid) hid.value=val;
  document.querySelectorAll('[data-fpick="'+k+'"]').forEach(b=>b.classList.toggle('on',b.dataset.val===val));
}
function infoPanel(){
  const p=prof(), groups=[];
  FIELDS.forEach(f=>{ if(!groups.includes(f.g)) groups.push(f.g) });
  const body=groups.map(g=>`<div class="grp"><div class="gt cap">${esc(g)}</div>
    ${FIELDS.filter(f=>f.g===g).map(f=>f.k==='photo'?photoRow(p)
      :S.edit
        ? `<div class="fld${S.errs[f.k]?' bad':''}">${fieldEdit(f,p)}</div>`
        : `<div class="fld"><span class="hint">${esc(f.l)}</span>${fieldView(f,p)}</div>`).join('')}</div>`).join('');
  const miss=missOf(p).length;
  const acts=S.edit?`<div class="row" style="margin-top:14px">
      <button class="btn primary" id="sendBtn">${ico('i-check')} ذخیره کن</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" id="cancelBtn">انصراف</button></div>`
    :`<div class="row" style="margin-top:12px"><button class="btn ${miss?'primary':'quiet'}" id="editBtn">
      ${ico('i-pen')} ${miss?'تکمیل اطلاعات':'ویرایش اطلاعات'}</button>
      ${inviteRow()}</div>`;
  return card('اطلاعات من','کم تایپ کن؛ هر چیزی که فهرست دارد از فهرست انتخاب می‌شود','i-idcard',
    `<div class="row" style="align-items:center;gap:8px;margin-top:2px">
      <span class="cap">٪${faN(pctOf(p))} کامل</span>
      ${miss?`<span class="tag">${faN(miss)} قلم مانده</span>`:chip('کامل','ok')}
      <span class="sp" style="flex:1"></span><span class="cap">همین‌جا ذخیره می‌شود</span></div>${body}${acts}`)+
    trustCard();
}
/* کد دعوت: اگر با کد آمده، همین‌جا معلوم می‌شود */
function inviteRow(){
  let inv={}; try{ inv=JSON.parse(localStorage.getItem('nora-home-invite')||'{}')||{} }catch(e){ inv={} }
  if(!inv.code) return '';
  return `<span class="tag ok" style="height:26px">${ico('i-users')} کد دعوت: <b class="num">${esc(inv.code)}</b>
    ${inv.by?' · دعوت '+esc(inv.by):''}</span>`;
}
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
/* نوشتن نظر و پر کردن نظرسنجی: همان رویداد، همان ورقه.
   نظرهای نوشته‌شده زیر کلید خودش می‌مانند تا بعد از بستن هم سرِ جایشان باشند. */
const NOTE_KEY='nora-home-mynotes';
function noteStore(){ try{ const v=JSON.parse(localStorage.getItem(NOTE_KEY)||'{}'); return v&&typeof v==='object'?v:{} }catch(e){ return {} } }
function notePick(text){ return String(text||'').replace(/[\u0000-\u001f<>]/g,'').trim().slice(0,300) }
function mergeNotes(){
  const st=noteStore();
  Object.keys(st).forEach(id=>{ const inf=MY_INFO[id]; if(!inf) return;
    inf.note=Object.assign({},inf.note||{},st[id]); });
}
function askNote(id,kind){
  const e=EVENTS.find(x=>x.id===id)||PAST.find(x=>x.id===id)||{};
  const survey=kind==='survey';
  S.myStars='۵';
  const stars=survey?'':`<div class="row tight" style="margin:10px 0 4px">${['۱','۲','۳','۴','۵'].map(n=>
    `<button class="chip${n==='۵'?' on':''}" data-star="${n}" type="button">${n}</button>`).join('')}</div>`;
  fillSheet('shMyNote',`<div class="grabber"></div>
    <div class="head">${survey?'نظرسنجی':'نظر تو'}</div>
    <p class="sub" style="margin-top:6px">${esc(e.t||'')}</p>
    <label class="lbl" for="myNoteText" style="margin-top:12px;display:block">
      ${survey?'پاسخ‌هایت را بنویس':'نظرت را بنویس'}</label>
    <textarea class="input" id="myNoteText" rows="3" placeholder="${survey?'مثلاً: محتوا خوب بود، صدا ضعیف بود':'کوتاه و صادقانه بنویس…'}"></textarea>
    ${stars}
    <div class="row" style="margin-top:14px">
      <button class="btn primary" id="myNoteGo">${survey?'فرستادن نظرسنجی':'ثبت نظر'}</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" data-close>بعداً</button></div>`);
  S.myNote=id; S.myKind=survey?'survey':'comment';
  openSheet('shMyNote');
}
function noteStoreAndSave(id,n){
  const st=noteStore(); const one={};
  if(n.comment) one.comment=n.comment;
  if(n.survey) one.survey=n.survey;
  st[id]=one; try{localStorage.setItem(NOTE_KEY,JSON.stringify(st))}catch(e){}
}
function saveNote(text,survey){
  const id=S.myNote||''; if(!id) return;
  const inf=myInfo(id), n=Object.assign({},inf.note||{});
  const body=notePick(text);
  if(survey) n.survey={n:((n.survey||{}).n)||'نظرسنجی این رویداد', at:nowFa(), answers:[body||'پاسخ ثبت شد']};
  else { const st=S.myStars||'۵'; n.comment={at:nowFa(), stars:st, text:body||'نظر ثبت شد'} }
  inf.note=n; MY_INFO[id]=inf;
  noteStoreAndSave(id,n);
  closeSheets(); render();
  toast(survey?'نظرسنجی ثبت شد؛ ممنون که وقت گذاشتی':'نظرت ثبت شد؛ همین‌جا می‌ماند');
  setTimeout(()=>openMyEvent(id),260);
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
  const ph=phone(), otp=(A.login&&A.login.otp)||{};
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
    card('راه ورود','کد یک‌بارمصرف را ربات نورا در بله می‌فرستد؛ رمزی نگه نمی‌داریم','i-chat',
      `<div class="srow">${ico('i-chat')}
        <span class="sp">${esc(otp.n||'ربات رمز یک‌بارمصرف')}<small>کد چهاررقمی، از همان‌جا</small></span>
        <a class="btn sm quiet" href="${esc(otp.href||'#')}" target="_blank" rel="noopener">باز کردن در بله</a></div>
       <div class="srow">${ico('i-refresh')}
        <span class="sp">اگر کد نیامد<small>در صفحهٔ ورود، «ارسال دوباره» بعد از پایان شمارشگر روشن می‌شود</small></span>
        <button class="btn sm quiet" data-relogin>صفحهٔ ورود</button></div>`) +
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
    : infoPanel();
  const sub=(PTABS.find(x=>x.k===S.ptab)||{}).s||'';
  return viewHead(t,sub,PTABS,'ptab')+`<div class="panel">${body}</div>`;
};
/* ══ باشگاه کتاب‌خوانی خط زندگی ══════════════════════════════════════════
   تا عضو نشوی، پنل بسته است: اول فرمی که سرپرست گذاشته، بعد حق عضویت،
   بعد امکانات باشگاه. هر چیزی که سرپرست می‌فرستد همین‌جا می‌نشیند. */
VS.book=function(t){
  if(!login()) return viewHead(t,'',null)+gate(t);
  if(!clubIsMember()) return clubJoin(t);
  return clubPanel(t);
};

/* ══ نورا پی: همهٔ پرداخت‌ها و خریدهای سامانه ══════════════════════════
   یک داشبورد: کیف پول بالا، کنش‌های سریع، بدهی اگر هست، بعد سه تکهٔ روشن —
   روش‌های پرداخت، صورت‌حساب‌ها و تراکنش‌ها. شش مدل روی یک لایه: کیف پول
   نورا پی، درگاه رسمی بله، کارت‌به‌کارت، حضوری، امتیاز و نصف‌ونصف. تا وقتی
   کاربر به نورا پی بدهکار است، گواهینامه‌اش دانلود نمی‌شود. */
function payState(){
  const d={bal:(PAYINFO.wallet||{}).bal||0, debt:((PAYINFO.debt||{}).amount)||0,
    paid:{}, part:{'NP-2417':true}, refunds:{}, txs:[], def:PAY_DEF[0]||'bale'};
  try{
    const v=JSON.parse(localStorage.getItem(PAY_KEY)||'{}')||{};
    return {bal:typeof v.bal==='number'?v.bal:d.bal, debt:typeof v.debt==='number'?v.debt:d.debt,
      paid:v.paid||{}, part:Object.assign({},d.part,v.part||{}), refunds:v.refunds||{},
      txs:v.txs||[], def:v.def||d.def};
  }catch(e){ return d }
}
function paySave(patch){
  const next=Object.assign({},payState(),patch||{});
  try{ localStorage.setItem(PAY_KEY,JSON.stringify(next)) }catch(e){}
  return next;
}
const walletBal=()=>payState().bal;
const debtAmt=()=>payState().debt;
const certLocked=()=>debtAmt()>0;
const methodOf=k=>PAYM.find(m=>m.k===k)||{};
const money=n=>faNum(n)+'  تومان';
const modelsOf=eid=>(PAY_EV&&PAY_EV[eid])||PAY_DEF;
function invState(v){ const st=payState();
  return st.paid[v.id]?'paid':(st.refunds[v.id]?'refunded':(st.part[v.id]?'partial':v.state)) }
function invTone(s){ return s==='paid'?'ok':(s==='refunded'||s==='failed'||s==='rejected')?'stop':s==='partial'?'gold':'brand' }
function invStateTxt(s){ return (PAYINFO.states||{})[s]||s }
function addTx(t){
  const st=payState(); paySave({txs:[Object.assign({at:nowFa()},t)].concat(st.txs).slice(0,12)});
}
/* ── گرافیک کوچک: نمودار خرج و حلقهٔ درصد ──────────────────────────── */
function payBars(){
  const w=PAYINFO.wallet||{}, t=w.trend||[], max=Math.max(1,...t), n=t.length;
  if(!n) return '';
  return `<span class="npbars" role="img" aria-label="${esc(w.trendNote||'خرج ماه‌های گذشته')}">
    ${t.map((v,i)=>`<i style="height:${Math.max(12,Math.round(v/max*100))}%" class="${i===n-1?'on':''}"></i>`).join('')}</span>`;
}
function donut(pct,inner,label,tone){
  const v=Math.min(100,Math.max(0,+pct||0)), r=26, c=2*Math.PI*r;
  return `<span class="donut${tone?' '+tone:''}" role="img" aria-label="${esc(label||'')}">
    <svg viewBox="0 0 64 64" aria-hidden="true"><circle class="dt" cx="32" cy="32" r="${r}"/>
      <circle class="dv" cx="32" cy="32" r="${r}" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${(c*(1-v/100)).toFixed(1)}"/></svg>
    <b>${inner}</b></span>`;
}
/* ── کیف پول، بالا و یک‌تکه ────────────────────────────────────────── */
function payHero(){
  const w=PAYINFO.wallet||{}, bal=walletBal(), cap=w.cap||0, debt=debtAmt();
  const pct=cap?Math.min(100,Math.round(bal/cap*100)):0, n=(PAYINFO.txs||[]).length;
  return `<div class="nphero anim">
    <div class="npcover">
      <span class="npk">${ico('i-wallet')} ${esc(w.n||'کیف پول نورا پی')}</span>
      <span class="npbal"><b class="num">${money(bal)}</b></span>
      <span class="npsub">
        ${w.auto?`<span class="nptag">${ico('i-check')} پرداخت خودکار</span>`:''}
        <span class="nptag">${ico('i-chart')} سقف ${money(cap)}</span>
        ${debt?`<span class="nptag stop">${ico('i-clock')} بدهی ${money(debt)}</span>`:''}
      </span>
      ${payBars()}
      <span class="npmeter"><i style="width:${pct}%"></i></span>
      <span class="npnote">${faN(pct)}٪ سقف پر شده · ${faN(n)} تراکنش در کارنامه</span>
    </div>
    <div class="npacts">
      <button class="npact" type="button" data-topup><span class="ic">${ico('i-plus')}</span><b>شارژ</b></button>
      <button class="npact" type="button" data-linkgo><span class="ic">${ico('i-link')}</span><b>لینک پرداخت</b></button>
      <button class="npact" type="button" data-debtpay><span class="ic">${ico('i-clock')}</span><b>${debt?'تسویهٔ بدهی':'بی بدهی'}</b></button>
      <button class="npact" type="button" data-paytx><span class="ic">${ico('i-refresh')}</span><b>تراکنش‌ها</b></button>
    </div></div>`;
}
/* ── بدهی و قفل گواهینامه ─────────────────────────────────────────── */
function debtBox(){
  const d=PAYINFO.debt||{}, amt=debtAmt();
  if(!amt)
    return `<div class="payclear npalert anim">${ico('i-check')}<span class="tx"><b>به نورا پی بدهکار نیستی</b>
      <small>گواهینامه‌ها باز است و هر وقت بخواهی دانلود می‌شوند.</small></span></div>`;
  return `<div class="paydebt npalert anim">${ico('i-lock')}<span class="tx">
      <b>${money(amt)} بدهی داری</b>
      <small>${esc(d.t||'')}${d.due?' · مهلت '+esc(d.due):''}${d.plan?' · '+esc(d.plan):''}</small>
      <span class="cap">${esc(d.lock||'تا تسویهٔ بدهی، گواهینامه قابل دانلود نیست.')}</span></span>
    <button class="btn sm primary" data-debtpay>پرداخت بدهی</button></div>`;
}
/* ── شش مدل پرداخت: کاشی‌های کوتاه، بی پاراگراف ────────────────────── */
function methodTile(m){
  const off=!m.on;
  return `<button class="paym${off?' off':''}" type="button" data-paym="${esc(m.k)}"${off?' disabled aria-disabled="true"':''}>
    <span class="pm-ic">${ico(m.i||'i-wallet')}</span>
    <span class="tx"><b>${esc(m.n)}</b><small>${esc(m.s)}</small></span>
    ${m.k===payState().def?chip('پیش‌فرض من','ok'):''}
    <span class="pm-go">${ico('i-chev-left')}</span></button>`;
}
function methodsBox(){
  return `<div class="payms">${PAYM.map(methodTile).join('')}</div>
    <p class="npfoot">مدل هر رویداد را مدیر یا سازندهٔ رویداد انتخاب می‌کند؛ روی هر روش بزنی شرط و مهلت خودش را می‌بینی.</p>`;
}
/* ── صورت‌حساب‌ها: صافی کوتاه و ردیف‌های جمع‌وجور ───────────────────── */
function invFilterBar(){
  const inv=PAYINFO.invoices||[];
  const count=k=>inv.filter(v=>k==='all'||invState(v)===k).length;
  const F=[['all','همه'],['paid','پرداخت‌شده'],['open','در انتظار'],['partial','نیمه‌پرداخت'],['refunded','برگشت وجه']];
  return `<div class="npfilters">${F.map(([k,n])=>`<button class="tag${(S.invF||'all')===k?' on':''}"
      type="button" data-invf="${k}">${esc(n)} <b class="num">${faN(count(k))}</b></button>`).join('')}</div>`;
}
function invRow(v){
  const st=invState(v), dow=v.paid<v.amount&&v.amount>0;
  return `<div class="ivrow st-${esc(invTone(st))}">
    <span class="iv-ic">${ico(v.amount?'i-doc':'i-star')}</span>
    <span class="tx"><b>${esc(v.t)}</b>
      <small>${esc(v.at)} · ${esc(methodOf(v.method).n||v.method||'')}${dow?' · پرداخت‌شده '+money(v.paid||0):''}</small>
      ${v.track&&v.track!=='—'?`<small class="cap">کد رهگیری <b class="num">${esc(v.track)}</b></small>`:''}</span>
    <span class="iv-end"><b class="num">${v.amount?money(v.amount):'رایگان'}</b>${chip(invStateTxt(st),invTone(st))}
      ${st==='paid'&&v.amount>0?`<button class="btn sm quiet" data-refund="${esc(v.id)}">برگشت</button>`
        :(st==='paid'||st==='refunded'?'':`<button class="btn sm primary" data-invpay="${esc(v.id)}">پرداخت</button>`)}</span></div>`;
}
function invoicesBox(){
  const inv=(PAYINFO.invoices||[]), f=S.invF||'all';
  const list=inv.filter(v=>f==='all'||invState(v)===f);
  return invFilterBar()+(list.length?list.map(invRow).join('')
    :empty2('در این حالت چیزی نیست','صافی را برگردان تا بقیهٔ صورت‌حساب‌ها را ببینی.'));
}
/* ── تراکنش‌ها: خط زمانی جمع‌وجور ──────────────────────────────────── */
function txRow(t){
  const up=(+t.amount||0)>0, pts=+t.pts||0;
  const amt=t.amount?`<b class="num ${up?'up':'down'}">${up?'+':'−'}${money(Math.abs(t.amount))}</b>`
    :(pts?`<b class="num up">+${faN(pts)} امتیاز</b>`:'<b class="num">—</b>');
  return `<div class="txrow"><span class="tx-ic">${ico(t.k==='top'?'i-plus':t.k==='refund'?'i-refresh':t.k==='bonus'?'i-star':'i-bag')}</span>
    <span class="tx"><b>${esc(t.t)}</b><small>${esc(t.at||'')}${t.by?' · '+esc(methodOf(t.by).n||t.by):''}</small></span>
    <span class="tx-end">${amt}${chip(pts?'امتیاز':invStateTxt(t.state),pts?'gold':invTone(t.state))}</span></div>`;
}
function txBox(){
  const all=payState().txs.concat(PAYINFO.txs||[]);
  const list=(S.txAll?all:all.slice(0,4));
  return list.length?list.map(txRow).join('')+
    (all.length>4&&!S.txAll?`<button class="npmore" type="button" data-paytx>${ico('i-plus')} همهٔ ${faN(all.length)} تراکنش</button>`:'')
    :empty2('تراکنشی نیست','اولین شارژ یا خریدت همین‌جا می‌نشیند.');
}
/* ── خلاصهٔ این ماه: سه عدد گرافیکی ────────────────────────────────── */
function payStats(){
  const st=payState(), inv=PAYINFO.invoices||[];
  const spent=inv.reduce((a,v)=>a+(+v.paid||0),0), left=inv.reduce((a,v)=>a+Math.max(0,(+v.amount||0)-(+v.paid||0)),0);
  return `<div class="npstats">
    <span><b class="num">${money(spent)}</b><small>پرداخت‌شده تا امروز</small></span>
    <span><b class="num">${money(left)}</b><small>ماندهٔ صورت‌حساب‌ها</small></span>
    <span><b class="num">${faN(+A.points||0)}</b><small>امتیاز من</small></span></div>`;
}
/* ── ورقه‌ها: پرداخت، شارژ، برگشت و لینک ─────────────────────────── */
function payTrace(){
  return `<div class="trace">${[['i-doc','فاکتور نورا پی'],['i-check','تأیید پرداخت'],['i-medal','رسید و کد رهگیری']]
    .map(([i,t])=>`<span class="tr">${ico(i)}${esc(t)}</span>`).join('<i class="tr-line"></i>')}</div>`;
}
function methodSheet(k,ctx){
  const m=methodOf(k); if(!m||!m.on) return;
  ctx=ctx||{};
  const amt=ctx.amount||0, bal=walletBal();
  const ev=(ctx&&ctx.eid)?((EVENTS.find(x=>x.id===ctx.eid)||PAST.find(x=>x.id===ctx.eid)||{}).t||''):'';
  let body='',act='';
  if(k==='bale'){
    body=`<p class="sub" style="margin-top:8px">فاکتور رسمی بله برای ${amt?money(amt):'این خرید'} ساخته می‌شود
      و از کیف پول بله خودت پرداخت می‌شود؛ همان لحظه قطعی است.</p>${payTrace()}
      <div class="srow">${ico('i-shield')}<span class="sp">درگاه<small>درگاه رسمی بله؛ برگشت وجه هم از همان درگاه</small></span>${chip('رسمی','ok')}</div>`;
    act=`<button class="btn primary" data-paynow="bale">پرداخت با درگاه بله</button>`;
  }else if(k==='wallet'){
    const enough=bal>=amt;
    body=`<p class="sub" style="margin-top:8px">از موجودی نورا پی خودت پرداخت می‌شود${amt?`؛ مبلغ ${money(amt)}`:''}.</p>
      <div class="srow">${ico('i-wallet')}<span class="sp">موجودی<b class="num">${money(bal)}</b></span>
        ${enough||!amt?chip('کافی','ok'):chip('کم است','warn')}</div>${payTrace()}`;
    act=`<button class="btn primary" data-paynow="wallet"${amt&&!enough?' disabled aria-disabled="true"':''}>پرداخت از کیف پول</button>
      ${amt&&!enough?`<button class="btn quiet" data-topup>شارژ کیف پول</button>`:''}`;
  }else if(k==='card'){
    const c=PAYINFO.card||{};
    body=`<p class="sub" style="margin-top:8px">مبلغ را کارت‌به‌کارت کن و رسید را همین‌جا بفرست؛
      تا تأیید کارشناس، جا تا ${esc(c.hold||'۳۰ دقیقه')} نگه داشته می‌شود.</p>
      <div class="stack tight">
        <div class="srow">${ico('i-card')}<span class="sp">شماره کارت<b class="num" dir="ltr">${esc(c.no||'')}</b></span>
          <button class="btn sm quiet" data-copy="${esc(c.no||'')}" data-copy-msg="شماره کارت رونوشت شد">رونوشت</button></div>
        <div class="srow">${ico('i-users')}<span class="sp">به نام<small>${esc(c.bank||'')} · ${esc(c.name||'')}</small></span></div>
        <div class="srow">${ico('i-pin')}<span class="sp">شناسه<small class="num" dir="ltr">${esc(c.sheba||'')}</small></span></div>
      </div>`;
    act=`<label class="btn primary" for="rcFile">${ico('i-image')} پیوست رسید</label>
      <input id="rcFile" type="file" accept="image/*,application/pdf" hidden/>
      <button class="btn quiet" data-paynow="card">رسید را فرستادم</button>`;
  }else if(k==='inperson'){
    body=`<p class="sub" style="margin-top:8px">پول را در ورودی یا دفتر بده؛ با کد رزرو تا ۴۸ ساعت جایت می‌ماند.</p>
      <div class="srow">${ico('i-ticket')}<span class="sp">کد رزرو<b class="num" dir="ltr">NP-${faN((ctx&&ctx.eid)||'e6')}</b></span>${chip('۴۸ ساعت','brand')}</div>`;
    act=`<button class="btn primary" data-paynow="inperson">کد رزرو را بگیر</button>`;
  }else if(k==='points'){
    const rate=m.rate||100, each=m.each||10000, cap=m.cap||30, have=+A.points||0;
    const maxByCap=Math.round(amt*cap/100), canPay=Math.min(have*each/rate,maxByCap);
    body=`<p class="sub" style="margin-top:8px">${faNum(rate)} امتیاز = ${money(each)}؛ تا ${faNum(cap)}٪ هر خرید.</p>
      <div class="srow">${ico('i-star')}<span class="sp">امتیاز تو<b class="num">${faNum(have)}</b></span>
        ${amt?chip('ارزش '+money(Math.round(have*each/rate)),''):chip('آماده','ok')}</div>
      ${amt?`<div class="srow">${ico('i-check')}<span class="sp">با امتیاز<small>سقف ${faNum(cap)}٪ این خرید: ${money(maxByCap)}</small></span>
        <b class="num">${money(Math.round(canPay))}</b></div>`:''}`;
    act=`<button class="btn primary" data-paynow="points"${amt&&canPay<=0?' disabled aria-disabled="true"':''}>با امتیاز پرداخت کن</button>`;
  }else if(k==='half'){
    const half=Math.round(amt/2);
    body=`<p class="sub" style="margin-top:8px">نصف الان، نصف تا اول تا پنجم ماه آینده.</p>
      <div class="steps">${[['نیمهٔ نخست',half,'همین حالا'],['نیمهٔ دوم',amt-half,(PAYINFO.debt||{}).due||'۱ تا ۵ ماه آینده']]
        .map(([n,v,at])=>`<div class="step done"><span class="dot">${ico('i-check','width:13px;height:13px')}</span>
          <span class="tx"><b>${esc(n)}</b><small>${money(v)} · ${esc(at)}</small></span></div>`).join('')}</div>
      <div class="paywarn">${ico('i-clock')}<span>تا تسویهٔ نیمهٔ دوم، گواهینامهٔ همین رویداد دانلود نمی‌شود؛
        خودِ گواهی سرِ جایش می‌ماند.</span></div>`;
    act=`<button class="btn primary" data-paynow="half">نیمهٔ نخست را بپرداز</button>`;
  }
  fillSheet('shPay',`<div class="grabber"></div>
    <div class="head">${ico(m.i||'i-wallet')} ${esc(m.n)}</div>
    <p class="cap" style="margin-top:5px">${ev?esc(ev)+' · ':''}${esc(m.rule||'')}</p>
    ${ctx.payDebt?`<p class="sub" style="margin-top:8px">تسویهٔ بدهی نورا پی؛ با پرداخت کامل،
      قفل گواهینامه‌ها باز می‌شود و پرونده‌ات پاک می‌شود.</p>`:''}
    ${amt?`<div class="payamt"><span>مبلغ</span><b class="num">${money(amt)}</b>${
      (PAYINFO.fee&&PAYINFO.fee.onUser&&PAYINFO.fee.pct&&k==='bale')?`<span class="cap">+ ${esc(PAYINFO.fee.title||'کارمزد درگاه')} ٪${faN(PAYINFO.fee.pct)} = ${money(Math.round(amt*PAYINFO.fee.pct/100))}</span>`:''}</div>`:''}
    ${body}
    <div class="row" style="margin-top:14px">${act}<span class="sp" style="flex:1"></span>
      <button class="btn quiet" data-close>بستن</button></div>
    <p class="cap" style="margin-top:10px">${esc(trustOf('پرداخت امن')||'پرداخت‌ها روی گذرگاه امن انجام می‌شود.')}</p>`);
  S.payCtx=ctx;
  openSheet('shPay');
}
function chooseSheet(eid,ctx){
  const keys=modelsOf(eid).filter(k=>methodOf(k).on);
  const e=(EVENTS.find(x=>x.id===eid)||PAST.find(x=>x.id===eid)||{});
  S.payCtx=Object.assign({},ctx||{},{eid:eid});
  fillSheet('shChoose',`<div class="grabber"></div>
    <div class="head">${ico('i-wallet')} مدل پرداخت این رویداد</div>
    <p class="cap" style="margin-top:5px">${e.t?esc(e.t)+' · ':''}این‌ها را مدیر یا سازندهٔ رویداد روشن کرده؛
      یکی را بردار${ctx&&ctx.payDebt?' تا بدهی تسویه شود':''}.</p>
    <div class="stack tight" style="margin-top:10px">${keys.map(k=>{const m=methodOf(k);
      return `<button class="opt" data-paym="${esc(k)}" data-in-choose="1">
        <span class="mk">${ico(m.i||'i-wallet','width:16px')}</span>
        <span style="flex:1;text-align:start"><b>${esc(m.n)}</b><br><span class="cap">${esc(m.s)}</span></span>
        ${ico('i-chev-left','color:var(--ink-4)')}</button>`}).join('')}</div>
    <div class="row" style="margin-top:12px"><span class="sp" style="flex:1"></span>
      <button class="btn quiet" data-close>بستن</button></div>`);
  openSheet('shChoose');
}
function topSheet(){
  const w=PAYINFO.wallet||{}, tiles=w.topTiles||[200000,500000,1000000,2000000];
  fillSheet('shTop',`<div class="grabber"></div>
    <div class="head">${ico('i-plus')} شارژ کیف پول نورا پی</div>
    <p class="cap" style="margin-top:5px">از درگاه رسمی بله؛ همان لحظه به موجودی‌ات می‌رسد.
      کف ${money(w.topMin||0)} و سقف ${money(w.topMax||0)}.</p>
    <div class="chipsline" style="margin-top:12px">${tiles.map(t=>
      `<button class="tag ${t===tiles[1]?'on':''}" type="button" data-topamt="${faN(t)}">${money(t)}</button>`).join('')}</div>
    <label class="lbl" for="topAmt" style="margin-top:12px;display:block">یا مبلغ دلخواه</label>
    <input class="input num" id="topAmt" inputmode="numeric" placeholder="مثلاً ۳۰۰۰۰۰" style="margin-top:6px"/>
    ${payTrace()}
    <div class="row" style="margin-top:14px"><button class="btn primary" data-topgo>${ico('i-shield')} شارژ از درگاه بله</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" data-close>بعداً</button></div>`);
  S.topAmt=(tiles[1]||0);
  openSheet('shTop');
}
function refundSheet(id){
  const v=(PAYINFO.invoices||[]).find(x=>x.id===id)||{};
  S.refundId=id;
  fillSheet('shRefund',`<div class="grabber"></div>
    <div class="head">${ico('i-refresh')} درخواست برگشت وجه</div>
    <p class="sub" style="margin-top:8px">${esc((PAYINFO.refund||{}).lead||'')}</p>
    <div class="steps">${((PAYINFO.refund||{}).steps||[]).map(([n,s2])=>`<div class="step">
      <span class="dot">${ico('i-clock','width:13px;height:13px')}</span>
      <span class="tx"><b>${esc(n)}</b><small>${esc(s2)}</small></span></div>`).join('')}</div>
    <label class="lbl" for="rfWhy" style="margin-top:12px;display:block">دلیل برگشت</label>
    <textarea class="input" id="rfWhy" rows="3" placeholder="کوتاه بنویس…" style="margin-top:6px"></textarea>
    <div class="row" style="margin-top:14px"><button class="btn primary" data-refundo="${esc(id)}">درخواست برگشت</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" data-close>بستن</button></div>`);
  openSheet('shRefund');
}
function linkSheet(){
  const l=PAYINFO.link||{};
  fillSheet('shLink',`<div class="grabber"></div>
    <div class="head">${ico('i-link')} ${esc(l.n||'لینک پرداخت')}</div>
    <p class="cap" style="margin-top:5px">${esc(l.hint||'')}</p>
    <label class="lbl" for="lkCode" style="margin-top:12px;display:block">کد لینک</label>
    <input class="input" id="lkCode" placeholder="${esc(l.ph||'')}" style="margin-top:6px"/>
    <div class="capex">نمونهٔ نمایشی: <b class="num" dir="ltr">${esc(l.demo||'')}</b></div>
    <div class="row" style="margin-top:14px"><button class="btn primary" data-linkok>باز کن</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" data-close>بستن</button></div>`);
  openSheet('shLink');
}
/* پرداخت: صورت‌حساب، کیف پول، بدهی و تراکنش‌ها را جلو می‌برد */
function doPay(kind,ctx){
  ctx=ctx||S.payCtx||{};
  const m=methodOf(kind), st=payState();
  const invId=ctx.inv||'', inv=(PAYINFO.invoices||[]).find(x=>x.id===invId)||{};
  const isDebt=!!ctx.payDebt, isHalf=!isDebt&&kind==='half';
  const total=isDebt?st.debt:(+ctx.amount||0);
  if(total<=0&&!isHalf){ toast('مبلغی برای پرداخت نیست'); return }
  let payNow=isHalf?Math.round(total/2):total;
  if(kind==='points'){
    const have=+A.points||0, rate=m.rate||100, each=m.each||10000, cap=(m.cap||30)/100;
    payNow=Math.min(Math.round(have*each/rate),Math.round(payNow*cap));
    if(payNow<=0){ toast('امتیازت برای این خرید کافی نیست'); return }
  }
  if(kind==='wallet'&&st.bal<payNow){ toast('موجودی کیف پول کم است؛ اول شارژ کن'); return }
  const paid=Object.assign({},st.paid), part=Object.assign({},st.part), refunds=Object.assign({},st.refunds);
  if(invId){ if(isHalf){ part[invId]=true } else { paid[invId]=true; delete part[invId] } }
  const debt=isDebt?0:Math.max(0,total-payNow);
  paySave({paid:paid, part:part, refunds:refunds, debt:debt, def:kind,
    bal:kind==='wallet'?st.bal-payNow:st.bal,
    txs:[{k:'buy', t:isDebt?('تسویهٔ بدهی'+(ctx.eid?' رویداد':'')):(inv.t||ctx.t||'پرداخت نورا پی'),
      amount:-payNow, by:kind, state:'paid', track:inv.track||'—', at:nowFa()}].concat(st.txs).slice(0,12)});
  closeSheets(); render();
  if(debt===0&&(isDebt||paid[invId])) toast(isDebt?'بدهی تسویه شد؛ گواهینامه‌ها باز شد':'پرداخت ثبت شد · '+money(payNow));
  else if(isHalf) toast('نیمهٔ نخست پرداخت شد؛ باقی‌اش تا اول ماه آینده');
  else toast('پرداخت ثبت شد · '+money(payNow));
}
function topup(amount){
  const w=PAYINFO.wallet||{}, amt=+amount||0;
  if(!amt){ toast('مبلغ شارژ را بنویس'); return }
  if(amt<(w.topMin||0)){ toast('کف شارژ '+money(w.topMin||0)+' است'); return }
  if(amt>(w.topMax||0)){ toast('بیشتر از سقف هر شارژ است'); return }
  const st=payState(), cap=w.cap||0;
  if(cap&&st.bal+amt>cap){ toast('بیشتر از سقف کیف پول می‌شود'); return }
  paySave({bal:st.bal+amt, txs:[{k:'top',t:'شارژ کیف پول',amount:amt,by:'bale',state:'paid',
    track:'BL-'+faN(Math.floor(10000+Math.random()*89999)),at:nowFa()}].concat(st.txs).slice(0,12)});
  closeSheets(); render(); toast(money(amt)+' به کیف پولت اضافه شد');
}
function refundDo(id){
  const refunds=Object.assign({},payState().refunds); refunds[id]=true;
  paySave({refunds:refunds, txs:[{k:'refund',t:'درخواست برگشت وجه '+(id||''),amount:0,by:'bale',
    state:'pending',track:id||'—',at:nowFa()}].concat(payState().txs).slice(0,12)});
  closeSheets(); render();
  toast((PAYINFO.refund||{}).ok||'درخواست برگشت ثبت شد');
}
function linkGo(){
  const l=PAYINFO.link||{}, v=String(($('#lkCode')||{}).value||'').trim().toUpperCase();
  if(!v||v!==String(l.demo||'').toUpperCase()){ toast(l.bad||'این لینک پرداخت پیدا نشد'); return }
  closeSheets();
  methodSheet('bale',{amount:250000,t:'لینک پرداخت '+v,inv:''});
  toast(l.ok||'لینک باز شد');
}
/* ── داشبورد نورا پی ───────────────────────────────────────────────── */
/* نما: مهمان درگاه ورود را می‌بیند، عضو داشبورد کامل را */
VS.pay=function(t){
  if(!login()) return viewHead(t,'',null)+gate(t);
  return viewHead(t)+payPanel();
};
function payPanel(){
  return payHero()+debtBox()+
    `<div class="npgrid">
      ${card('روش‌های پرداخت','شش مدل؛ هر رویداد مدل‌های خودش را دارد','i-list',methodsBox())}
      ${card('صورت‌حساب‌های من',faN((PAYINFO.invoices||[]).length)+' صورتحساب با کد رهگیری','i-doc',invoicesBox())}
      ${card('تراکنش‌ها','شارژ، خرید، امتیاز و برگشت وجه','i-chart',txBox())}
    </div>`+
    card('جمع و تفریق نورا پی','یک نگاه به حسابم','i-wallet',payStats())+
    `<details class="npmore2"><summary>${ico('i-shield')} شرط‌های نورا پی</summary>
      ${(PAYINFO.rules||[]).map(r=>`<div class="srow">${ico('i-check')}<span class="sp">${esc(r)}</span></div>`).join('')}
      <p class="cap">${esc((PAYINFO.fee||{}).note||'')}</p></details>`+
    trustLine('pay');
}

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
  if(p.birthDate) p.birthDate=dtTxt(dtParts(p.birthDate))||p.birthDate;
  if(!p.phone) p.phone=phone();
  return p;
}
function submit(send){
  const p=tidy(collect()), errs=validate(p);
  S.errs=errs;
  if(Object.keys(errs).length){ renderView(); toast('چند قلم را ببین و درست کن'); return }
  p.phone=phone();
  p.status='approved';                       /* پروفایل خودش ذخیره می‌شود؛ فرایند تأیید ندارد */
  p.history=(p.history||[]).filter(h=>h.k!=='filled').concat([{k:'filled',at:nowFa()}]);
  if(UI().saveProfile) UI().saveProfile(p);
  S.edit=false; render();
  toast('ذخیره شد');
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
document.addEventListener('change',ev=>{
  const el=ev.target; if(!el||!el.id) return;
  if(el.id==='f_province'){ syncCity(); return }
  if(/^f_birthDate_[dmy]$/.test(el.id)){ syncDate('birthDate'); return }
  if(el.id==='f_city'&&S.errs&&S.errs.city) S.errs.city='';
});
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
  const ct=t.closest('[data-ctab]'); if(ct){ S.ctab=ct.dataset.ctab; renderView(); return }
  const vt=t.closest('[data-vtab]'); if(vt){ S.vtab=vt.dataset.vtab; renderView(); return }
  const pt=t.closest('[data-ptab]'); if(pt){ S.ptab=pt.dataset.ptab; S.edit=false; S.errs={}; renderView(); return }
  if(t.closest('[data-photo-demo]')){ demoPhoto(); return }
  if(t.closest('[data-trust-more]')){ trustSheet(); return }
  const fp=t.closest('[data-fpick]'); if(fp){ pickSet(fp.dataset.fpick,fp.dataset.val); return }
  if(t.closest('#editBtn')){ startEdit(); return }
  if(t.closest('#cancelBtn')){ cancelEdit(); return }

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
  /* رویدادهای من: جزئیات همان رویداد، در همین صفحه */
  const me=t.closest('[data-myev]');
  if(me){ const ask=t.closest('[data-ask]');
    if(ask){ askNote(me.dataset.myev,ask.dataset.ask); return }
    openMyEvent(me.dataset.myev); return }
  if(t.closest('[data-goto-notes]')){ S.vtab='notes'; render(); return }
  if(t.closest('#myNoteGo')){ const v=($('#myNoteText')||{}).value||''; saveNote(v,S.myKind==='survey'); return }
  const stb=t.closest('[data-star]');
  if(stb){ S.myStars=stb.dataset.star;
    stb.parentElement.querySelectorAll('.chip').forEach(x=>{ x.classList.toggle('on',x===stb) }); return }
  /* باشگاه کتاب‌خوانی */
  const cf=t.closest('[data-cf]');
  if(cf){ const f={}; f[cf.dataset.cf]=cf.dataset.cv; bookSet({form:Object.assign({},bookState().form,f)});
    renderView(); return }
  const clp=t.closest('[data-clanplan]');
  if(clp){ bookSet({plan:clp.dataset.clanplan}); render(); return }
  if(t.closest('[data-clubsend]')){
    const req=(CGATE.fields||[]).filter(f=>f.req), missing=req.find(f=>!bookState().form[f.k]);
    if(missing){ toast('یک قلم مانده: '+missing.l); return }
    bookSet({cstep:'fee'}); render(); toast('فرم برای سرپرست رفت؛ حالا حق عضویت'); return }
  if(t.closest('[data-clubedit]')){ bookSet({cstep:'form'}); render(); return }
  if(t.closest('[data-clubsend2]')){ clubFeeSheet(); return }
  const cbm=t.closest('[data-clubm]');
  if(cbm){
    /* حق عضویت هم از نورا پی می‌گذرد؛ کیف پول اگر کم بیاید، اول شارژ */
    const plan=clubPlan(bookState().plan), kind=cbm.dataset.clubm, st=payState();
    if(kind==='wallet'&&st.bal<plan.amount){ toast('موجودی کیف پول کم است؛ اول شارژ کن'); return }
    paySave({bal:kind==='wallet'?st.bal-plan.amount:st.bal,
      txs:[{k:'buy', t:'حق عضویت باشگاه · '+plan.n, amount:-plan.amount, by:kind, state:'paid',
        track:'CL-'+faN(Math.floor(10000+Math.random()*89999)), at:nowFa()}].concat(st.txs).slice(0,12)});
    bookSet({member:true, cstep:'ok', joined:true, plan:plan.k, feeAt:nowFa(),
      feeNext:(CFEE.due||''), sessions:1}); closeSheets(); render();
    toast('عضو باشگاه شدی · پنل باز شد و نشانت روی پروفایل نشست'); return }
  if(t.closest('[data-clubpay]')){ clubFeeSheet(); return }
  const ca=t.closest('[data-att]');
  if(ca){ const att=Object.assign({},bookState().att); att[ca.dataset.att]=ca.dataset.attst;
    bookSet({att:att, sessions:(+bookState().sessions||0)+(ca.dataset.attst==='نمی‌آیم'?0:1)});
    renderView(); toast('ثبت شد: '+ca.dataset.attst); return }
  const cch=t.closest('[data-chal]');
  if(cch){ const ch=(CCLUB.challenges||[]).find(x=>x.k===cch.dataset.chal)||{};
    const chals=Object.assign({},bookState().chals);
    chals[cch.dataset.chal]=Math.min(ch.goal,(+chals[cch.dataset.chal]||0)+1);
    bookSet({chals:chals}); renderView();
    toast(chals[cch.dataset.chal]>=ch.goal?'چالش را تمام کردی · '+faN(ch.reward||0)+' امتیاز گرفتی':'یک گام جلوتر رفت؛ ادامه بده'); return }
  const con=t.closest('[data-contest]');
  if(con){ const entered=Object.assign({},bookState().entered); entered[con.dataset.contest]=true;
    bookSet({entered:entered}); renderView(); toast('ثبت‌نامت در مسابقه نشست؛ سرپرست خبر می‌دهد'); return }
  const cw=t.closest('[data-clubw]');
  if(cw){ const w=(CCLUB.workshops||[]).find(x=>x.k===cw.dataset.clubw)||{};
    const seats=Object.assign({},bookState().seats); seats[cw.dataset.clubw]=true;
    bookSet({seats:seats}); renderView();
    toast(w.price?('جا گرفتی؛ مبلغش را از نورا پی بپرداز · '+money(w.price)):'جا گرفتی؛ رایگان است'); return }
  const cvo=t.closest('[data-cvoice]'); if(cvo){ bookSet({voiceRole:cvo.dataset.cvoice}); renderView(); return }
  const csl=t.closest('[data-cslot]'); if(csl){ bookSet({voiceSlot:csl.dataset.cslot}); renderView(); return }
  if(t.closest('[data-cvoice-send]')){
    const bc2=bookState();
    if(!bc2.voiceRole){ toast('یکی از کارها را انتخاب کن'); return }
    bookSet({voice:{role:bc2.voiceRole, slot:bc2.voiceSlot||'', at:nowFa()}}); renderView();
    toast('فرمت برای سرپرست رفت؛ برای جلسهٔ آزمایشی خبر می‌دهد'); return }
  const ctg=t.closest('[data-ctag]'); if(ctg){ bookSet({tag:ctg.dataset.ctag}); renderView(); return }
  if(t.closest('[data-post]')){
    const el=$('#trText'), v=el?String(el.value||'').trim():'';
    if(v.length<8){ toast('کمی بیشتر بنویس؛ یک جمله هم کافی است'); if(el&&el.focus) el.focus(); return }
    const bc3=bookState(), nm=(prof().fullName||'عضو باشگاه');
    const p2={k:'tr'+Date.now(), n:nm, g:String(nm).slice(0,1), tag:bc3.tag||'پیشنهاد', likes:0, at:nowFa(), t:v, mine:true};
    bookSet({posts:[p2].concat(bc3.posts||[]).slice(0,10)}); renderView(); toast('نظرت روی تریبون نشست'); return }
  const lk=t.closest('[data-like]');
  if(lk){ const likes=Object.assign({},bookState().likes);
    if(likes[lk.dataset.like]) delete likes[lk.dataset.like]; else likes[lk.dataset.like]=true;
    bookSet({likes:likes}); renderView(); return }

  /* نورا پی */
  const pm=t.closest('[data-paym]');
  if(pm){ methodSheet(pm.dataset.paym, pm.dataset.inChoose?(S.payCtx||{}):{}); return }
  if(t.closest('[data-topup]')){ topSheet(); return }
  const ta=t.closest('[data-topamt]'); if(ta){ S.topAmt=unFa(ta.dataset.topamt).replace(/\D/g,'');
    document.querySelectorAll('[data-topamt]').forEach(b=>b.classList.toggle('on',b===ta)); return }
  if(t.closest('[data-topgo]')){
    const v=($('#topAmt')||{}).value||''; const amt=+unFa(v).replace(/\D/g,'')||S.topAmt||0; topup(amt); return }
  if(t.closest('[data-paytx]')){ S.txAll=!S.txAll; renderView(); return }
  const ivf=t.closest('[data-invf]'); if(ivf){ S.invF=ivf.dataset.invf; renderView(); return }
  const dp=t.closest('[data-debtpay]');
  if(dp){ chooseSheet((PAYINFO.debt||{}).e||'',{payDebt:true,amount:debtAmt(),t:'تسویهٔ بدهی نورا پی',
    inv:(PAYINFO.debt||{}).invoice||''}); return }
  const ip=t.closest('[data-invpay]');
  if(ip){ const v=(PAYINFO.invoices||[]).find(x=>x.id===ip.dataset.invpay)||{};
    chooseSheet(v.e,{inv:v.id,amount:Math.max(0,(v.amount||0)-(v.paid||0)),t:v.t}); return }
  if(t.closest('[data-linkgo]')){ linkSheet(); return }
  if(t.closest('[data-linkok]')){ linkGo(); return }
  const rf=t.closest('[data-refund]'); if(rf){ refundSheet(rf.dataset.refund); return }
  const rfb=t.closest('[data-refundo]');
  if(rfb){ if(!String(($('#rfWhy')||{}).value||'').trim()){ toast('کوتاه بنویس چرا برگشت می‌خواهی');
      const e=$('#rfWhy'); if(e&&e.focus) e.focus(); return }
    refundDo(rfb.dataset.refundo); return }
  const pn=t.closest('[data-paynow]'); if(pn){ doPay(pn.dataset.paynow,S.payCtx||{}); return }
  const mtk=t.closest('[data-my-ticket]'); if(mtk){ toast('کارت ورود همین رویداد آماده است؛ بارکد در ورودی خوانده می‌شود'); return }
  const mtd=t.closest('[data-my-ticket-dl]'); if(mtd){ toast('بلیت همین رویداد دانلود شد'); return }
  const mcr=t.closest('[data-my-cert]');
  if(mcr){ const cc=(myInfo(mcr.dataset.myCert).cert)||{};
    toast(cc.id?('گواهینامه با سریال '+cc.id+' دانلود شد'):'گواهینامه پس از تأیید سرپرست دانلود می‌شود'); return }
  const moff=t.closest('[data-off]'); if(moff){ toast('فایل آفلاین دانلود شد؛ بی اینترنت هم باز می‌شود'); return }
  const moffa=t.closest('[data-off-all]'); if(moffa){ toast('همهٔ فایل‌های آفلاین همین رویداد دانلود شد'); return }
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
  const cp=t.closest('[data-copy]');
  if(cp){ const msg=cp.dataset.copyMsg||''; copyText(cp.dataset.copy,msg?()=>toast(msg):null); return }
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
  /* خطای همان کادر پاک می‌شود، بی آن که بقیهٔ نوشته‌ها از دست برود */
  const k=el.id.slice(2).replace(/_[dmy]$/,''); if(!S.errs||!S.errs[k]) return;
  delete S.errs[k];
  const fld=el.closest?el.closest('.fld'):null;
  if(fld){ fld.classList.remove('bad'); const er=fld.querySelector('.err'); if(er) er.remove() }
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
mergeNotes();
route();
})();
