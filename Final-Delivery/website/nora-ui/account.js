/* ══════════════════════════════════════════════════════════════════════════
   نورا، حساب من
   ──────────────────────────────────────────────────────────────────────────
   یک صفحه، سه چیز:
     ۱) سرِ پروفایل، شبیه صفحهٔ حساب اپلی‌ها: جلد رنگی، نام، نشان وضعیت، سطح،
        امتیاز و نوار تکمیل اطلاعات
     ۲) خلاصهٔ پرداخت دو مرحله‌ای؛ بدون کیف پول، شارژ یا پرداخت عملیاتی
     ۳) میان‌بُرها، رویداد نزدیک و سه ردیف: رویدادهای من، پروفایل من و
        باشگاه کتاب‌خوانی (باشگاه هم زیر پروفایل من باز می‌شود)

   پشتیبانی بخش نیست؛ نواری است که به نوار پایین چسبیده و از پایین باز می‌شود.
   مهمان یک کارت معرفی و ورود محلی می‌بیند و روی هر ردیف که بزند، بعد از ورود
   همان بخش باز می‌شود.
   ══════════════════════════════════════════════════════════════════════════ */
(function(){
'use strict';

/* ── دادهٔ همین صفحه ─────────────────────────────────────────────── */
const TEST_FIXTURE_MODE=window.__NORA_TEST_FIXTURE_MODE__===true;
const N=window.NORA||{}, A=N.ACCOUNT||{}, POL=A.policy||{}, SUP=A.support||{};
// Production routing needs labels, not the unrelated prototype fixture dataset.
const SERVER_SECTIONS=[
  {k:'events',n:'رویدادهای من',s:'',i:'i-calendar'},
  {k:'pay',n:'پرداخت‌ها',s:'وضعیت پرداخت ثبت‌نام‌های پولی این حساب از سرور.',i:'i-wallet'},
  {k:'book',n:'باشگاه',s:'وضعیت اتصال اطلاعات باشگاه به حساب وب.',i:'i-users'}
];
const SECT=TEST_FIXTURE_MODE?(A.sections||[]):SERVER_SECTIONS, PAY=SECT.find(s=>s.card)||null;
const PROFILE_VIEW=TEST_FIXTURE_MODE
  ?A.profileView||{k:'profile',n:'پروفایل من',s:'اطلاعات و وضعیت نمونه؛ بدون احراز هویت سروری',i:'i-idcard'}
  :{k:'profile',n:'پروفایل من',s:'اطلاعات حساب وب و وضعیت اتصال پروفایل.',i:'i-idcard'};
/* حساب یک صفحه دارد: رویدادهای من، پروفایل شخصی و باشگاه. مقاله‌های راهنما در صفحهٔ پشتیبانی می‌مانند. */
const ROWS=['events','profile','book'].map(k=>k==='profile'?PROFILE_VIEW:SECT.find(s=>s.k===k)).filter(Boolean);
const EVENTS=N.EVENTS||[], PAST=N.PAST||[], FAQ=N.FAQ||[], CERTS=N.CERTS||{}, ARCHIVE=N.ARCHIVE||{};
const FIELDS=A.fields||[], LEVELS=A.levels||[], ACH=A.achievements||[], STORE=A.rewardStore||[];
const MON=A.months||{sh:'شهریور'};
const TRUST=N.TRUST||{}, TRUST_ROWS=TRUST.row||[];
const PF=A.profileForm||{}, DELFLOW=A.deleteFlow||{};
const MY=A.myEvents||{}, MY_UP=MY.up||[], MY_PAST=MY.past||[];
const MY_INFO=MY.info||{}, TABS=MY.tabs||{}, GRP=MY.groups||{};
const PAYINFO=A.pay||{}, PAYM=PAYINFO.methods||[], PAY_EV=PAYINFO.eventModels||{},
      PAY_DEF=PAYINFO.defaultModels||['bale','wallet','card'];
const PAY_KEY='nora-home-pay';                 /* کلید قدیمیِ دادهٔ نمونه؛ این پیش‌نمایش به‌عنوان پرداخت نمی‌خواند یا می‌نویسد */
const walletConfig=()=>{const base=Object.assign({},PAYINFO.wallet||{});
  try{const U=window.NORA_UI||{}, F=U.finPublic?U.finPublic():null; return Object.assign(base,(F&&F.wallet)||{})}catch(e){return base}};
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
const myUp=()=>EVENTS.filter(e=>MY_UP.indexOf(e.id)>-1);
const myPast=()=>PAST.filter(e=>MY_PAST.indexOf(e.id)>-1);
/* شمارش معکوس فقط با شمارشگر مشترک و زمان معتبر سرور (startsAt/registration)؛ هیچ عدد نمونه‌ای ساخته نمی‌شود */
function cdLine(e){
  const CD=window.NORA_COUNTDOWN;
  if(!CD||typeof CD.eventTarget!=='function'||typeof CD.markup!=='function') return '';
  const target=CD.eventTarget(e);
  return target?`<span class="cdline">${CD.markup(target)}</span>`:'';
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
  const t=(kind&&S2[kind])||trustOf('رمزنگاری اطلاعات')||'اطلاعات این پیش‌نمایش فقط در همین مرورگر می‌ماند.';
  const head=(TRUST.head||'پیش‌نمایش محلی نورا');
  return `<p class="trustline" data-trust="${esc(kind||'secure')}" title="${esc(head)}">
    <svg class="i" aria-hidden="true"><use href="#i-shield"/></svg><span>${esc(t)}</span></p>`;
}
function trustCard(){
  return `<div class="trustcard anim">${ico('i-shield')}
    <span class="tx"><b>${esc(TRUST.head||'پیش‌نمایش محلی نورا')}</b>
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
const login=()=>TEST_FIXTURE_MODE?!!uid():!!(typeof SERVER_ACCOUNT_STATE!=='undefined'&&SERVER_ACCOUNT_STATE.account);
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
const stOf=p=>{
  const status=(p&&p.status)||'draft';
  if(status==='draft') return ['پیش‌نویس محلی','warn'];
  if(status==='local') return ['ذخیرهٔ محلی','warn'];
  /* وضعیت‌های قدیمی هم در مرورگر، نشانهٔ تأیید/رد واقعی نیستند. */
  if(['pending','approved','rejected'].includes(status)) return ['وضعیت نمونه · بررسی‌نشده','warn'];
  return ['پیش‌نمایش محلی','warn'];
};
const monOf=e=>(e&&e.dm&&MON[e.dm])||'';

/* ── حالت صفحه ───────────────────────────────────────────────────── */
const S={view:'',vtab:'up',ptab:'info',ctab:'home',invF:'all',txAll:false,edit:false,errs:{},after:'',myEventId:null,refreshEventPending:false,serverdata:'notifications'};
const SERVER_ACCOUNT_STATE={account:null,checking:true,checked:false,error:'',
  registrations:[],registrationsTotal:0,registrationsLoaded:false,registrationsLoading:false,registrationsError:'',registrationsMore:false,
  notifications:[],notificationsLoaded:false,notificationsLoading:false,notificationsError:'',notificationsMore:false,
  files:[],filesLoaded:false,filesLoading:false,filesError:'',filesMore:false,
  /* فاز ۹: دسترسی‌های محتوای ضبط‌شده و سفارش‌های آن؛ فقط از سرور، هیچ‌جا محلی ساخته نمی‌شود. */
  library:[],libraryLoaded:false,libraryLoading:false,libraryError:'',
  /* فاز ۹.۲ — گواهینامه‌های من: فقط آینهٔ سرور از صدور واقعی ربات؛ مرورگر چیزی نمی‌سازد. */
  certificates:[],certsCounts:null,certsLoaded:false,certsLoading:false,certsError:'',
  recOrders:[],recOrdersTotal:0,recOrdersLoaded:false,recOrdersLoading:false,recOrdersError:'',recOrdersMore:false,recOrderBusy:''};
const SERVER_ACCOUNT_PAGE=50;
const SERVER_DATA_VIEW={k:'server-data',n:'اعلان‌ها و فایل‌های من',s:'داده‌های حساب تو از سرور خوانده می‌شود.'};
/* وضعیت پیوند هویت‌ها. جدا نگه داشته می‌شود چون هم بار خودش را دارد و هم
   باید در خروج/انقضای نشست یک‌جا پاک شود. `busy` جلوی ارسال مکرر و مصرف
   دوبارهٔ امضای یک‌بارمصرف را می‌گیرد. */
const IDENTITY_STATE={list:null,loaded:false,loading:false,error:'',busy:'',confirmUnlink:false,outcome:null};

/* ── رفتن به یک بخش: مهمان، ورقهٔ ورود؛ عضو، همان بخش ─────────────── */
function go(k){
  if(k==='support'){ goSupport(); return }
  if(!login()){ S.after=k; loginSheet(); return }
  location.hash='#'+k;
}
/* ورود نمونهٔ حساب در همان ورقهٔ محلی است؛ ورود امن سروری جداگانه در login.html می‌ماند. */
function goLogin(after){ location.href=serverLoginHref(after) }
function loginSheet(){
  const next=S.after; S.after='';
  const openDemoLogin=UI().authSheet;
  if(typeof openDemoLogin!=='function'){ goLogin(next); return }
  openDemoLogin(()=>{
    if(next){ location.hash='#'+next; route() }
    else render();
  });
}

/* ══ سرِ پروفایل ═════════════════════════════════════════════════════ */
function headGuest(){
  const SUPI=SUP.i||'i-headphone';
  return `<div class="card acct anim guestcard">
      <span class="gmark" aria-hidden="true">${ico('i-idcard-f')}</span>
      <div class="head">خوش آمدی</div>
      <p class="sub" style="margin:7px 0 0">این فقط پیش‌نمایش محلی حساب است؛ ثبت‌نام، بلیت، گواهی و امتیاز واقعی ایجاد نمی‌شود.
        شماره و کد در همین مرورگر آزمایش می‌شوند؛ پیامک یا احراز هویت سروری نداریم.</p>
      <div class="gl">
        <div class="row">${ico('i-check')}<span>جزئیات و پیوندهای هر رویداد در همان‌جا</span></div>
        <div class="row">${ico('i-check')}<span>گواهیِ صادرشده در رویداد دیده می‌شود؛ دریافت از ربات بله</span></div>
        <div class="row">${ico('i-check')}<span>امتیاز و فرم‌های نمونه، فقط در همین مرورگر</span></div>
      </div>
      <button class="btn primary" data-login>${ico('i-mobile')} ورود آزمایشی با شمارهٔ موبایل</button>
      <button class="btn quiet sm demo" type="button" data-demo>${ico('i-eye')} نمای نمونهٔ حساب را ببین</button>
      <p class="cap" style="margin:11px 2px 0">کد ۵۴۳۲۱ فقط برای آزمایش همین صفحه است؛ هیچ پیامکی فرستاده نمی‌شود و این ورود حساب واقعی نمی‌سازد.</p>
      <p class="cap" style="margin:6px 2px 0">راهنمای محلی در صفحهٔ پشتیبانی باز است؛ گفت‌وگو با کارشناس یا پاسخ بیرونی وصل نیست.</p>
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
            <small>${phone()?faN(phone())+' · ':''}حساب نمونه · تاریخ نمایشی ${esc(u.joined||A.joined||'۱۴۰۴')}</small>
            <span class="pmeta">${chip('سطح نمونه · '+(cur.n||'—'))}${next?chip(faN(next.at-pts)+' تا سطح نمونهٔ بعدی'):chip('بالاترین سطح نمونه','warn')}</span></span>
          <button class="icon-btn edit" data-go="account" aria-label="ویرایش اطلاعات حساب">${ico('i-pen')}</button>
        </div>
        <div class="pstats">
          <button class="pstat" data-go="club"><b>${faNum(pts)}</b><small>امتیاز نمونهٔ محلی</small></button>
          <button class="pstat" data-go="club"><b>${next?faNum(next.at-pts):'—'}</b><small>${next?'تا '+esc(next.n):'بالاترین سطح'}</small></button>
          <button class="pstat" data-go="events"><b>${faN(EVENTS.length)}</b><small>برنامهٔ پیش‌روی نمونه</small></button>
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
        <p class="cap" style="margin-top:9px">امتیاز، رویدادها و وضعیت پروفایل نمونه‌اند؛ ثبت‌نام، پرداخت یا احراز هویت واقعی انجام نشده است.</p>
      </div></div>`;
}

/* ══ نورا پی: یک مدل روشن، بدون کیف پول و شارژ ═════════════════════ */
function payBox(){
  const pending=typeof pendingFirstInstallments==='function'?pendingFirstInstallments():[];
  const due=pending[0];
  return `<div class="paybar paybar-installments anim" style="--i:1">
      <button class="pbmain" type="button" data-view="pay" aria-label="پرداخت دو مرحله‌ای نورا">
        <span class="pwal" aria-hidden="true">${ico('i-split')}</span>
        <span class="ptx"><small>پرداخت دو مرحله‌ای نورا</small>
          <b>نصف الان · نصف تا پنجم ماه بعد</b>
          <span class="pmeta">${due?chip('نیمهٔ اول '+money(due.first),'warn'):chip('بدون کیف پول','')}</span></span>
        <svg class="i chev" aria-hidden="true"><use href="#i-chev-left"/></svg>
      </button>
      ${trustLine('pay')}
    </div>`;
}

/* ══ کارت رویداد نزدیک ═══════════════════════════════════════════════ */
function nextBox(){
  if(!login()||!EVENTS.length) return '';
  const e=myUp()[0]||EVENTS.find(x=>MY_UP.indexOf(x.id)>-1)||EVENTS[0], info=myInfo(e.id), online=isOnlineEvent(e,info), join=eventJoinUrl(e,info);
  return `<div class="qcard anim event-next-card" style="--i:2">
      <span class="qc-date"><b>${faD(e.dn||'')}</b><small>${esc(monOf(e))}</small></span>
      <span class="qc-tx"><b>${esc(e.t)}</b>
        <span class="qmeta">${ico('i-clock')} ${esc(e.time||'')} ${ico('i-pin')} ${esc(e.place||'')}</span>
        <span class="qmeta">${ico(online?'i-video':'i-calendar')} ${online?(join?'پیوند ورود آماده است':'پیوند ورود در جزئیات رویداد می‌آید'):'جزئیات، گواهی و رسانه در صفحهٔ رویداد'}</span></span>
      <button class="qc-go" data-myev="${esc(e.id)}">${ico('i-chev-left')} جزئیات رویداد</button>
    </div>`;
}

/* ══ ردیف‌های بخش‌ها ═════════════════════════════════════════════════ */
function subOf(k){
  const p=prof(), {cur}=lvl(), pts=+A.points||0;
  if(k==='events'){
    if(!login()) return EVENTS.length?faN(EVENTS.length)+' برنامهٔ پیش‌رو و '+faN(PAST.length)+' برگزارشده':'';
    return faN(EVENTS.length)+' رویداد نمونه · بدون ثبت‌نام واقعی';
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
/* ══ صفحهٔ پروفایل: سر، میان‌بُرها، رویداد نزدیک و بخش‌ها ═══════════ */
function renderProfile(){
  const box=$('#profBox'); if(!box) return;
  box.innerHTML=profileHTML();
}
function serverAccountAccessCard(next='notifications'){
  const state=SERVER_ACCOUNT_STATE;
  if(state.account) return '';
  if(state.checking) return card('حساب امن','در حال بررسی وضعیت ورود…','i-shield',
    `<p class="cap">اطلاعات شخصی فقط پس از تأیید سرور نمایش داده می‌شود.</p>`);
  const destination=['events','notifications','my-files','forms','payments','profile','library'].includes(next)?next:'notifications';
  const loginHref=serverLoginHref(destination);
  const description=destination==='events'?'برای دیدن ثبت‌نام‌ها وارد حساب شو.':destination==='forms'?'برای دیدن فرم‌های خودت وارد حساب شو.'
    :destination==='payments'?'برای دیدن سفارش‌ها و وضعیت پرداخت‌هایت وارد حساب شو.'
    :destination==='library'?'برای دیدن محتوای ضبط‌شده‌ای که به آن دسترسی داری وارد حساب شو.':'برای دیدن اطلاعات حساب وارد شو.';
  const retry=state.error?`<button class="btn quiet" data-server-account-retry>${ico('i-refresh')} تلاش دوباره</button>`:'';
  return card('نیاز به ورود',description,'i-mobile',
    `<div class="row" style="flex-wrap:wrap">
       <a class="btn primary" href="${esc(loginHref)}">ورود/ثبت‌نام</a>${retry}
     </div>`);
}
function serverAccountProviderLabel(a){
  return a&&a.provider==='manager-password'?'ورود مدیر با نام کاربری':a&&a.provider==='phone'?'ورود با شمارهٔ موبایل':'حساب بله';
}
function serverAccountDisplayName(){
  const p=prof()||{}; const name=String(p.fullName||'').trim();
  return name;
}
/* سر صفحهٔ حساب با همان چیدمان تأییدشده (phead)؛ همهٔ اعداد از سرور می‌آیند و تا خوانده نشده‌اند «—» هستند. */
function serverAccountHead(){
  const state=SERVER_ACCOUNT_STATE;
  if(!state.account) return '';
  const providerLabel=serverAccountProviderLabel(state.account);
  const unread=state.notifications.filter(item=>item&&!item.read).length;
  const noticeCount=state.notificationsLoaded?faN(state.notifications.length):'—';
  const fileCount=state.filesLoaded?faN(state.files.length):'—';
  const regCount=state.registrationsLoaded&&!state.registrationsError?faN(state.registrationsTotal):'—';
  const name=serverAccountDisplayName(), initial=(name||'ن').slice(0,1);
  const role=state.account.role==='owner'?'مالک سامانه':state.account.role==='manager'?'مدیر':state.account.role==='club-supervisor'?'سرپرست باشگاه':'';
  return `<section class="phead anim server-account-head" aria-label="حساب من">
    <div class="cover"><span class="blob b1" aria-hidden="true"></span>
      <span class="ctags">${chip(providerLabel+' وصل است','ok')}${chip('حساب امن')}${role?chip(role,'brand'):''}</span></div>
    <div class="pbody">
      <div class="ptop">
        <span class="av">${esc(initial)}<i class="pdot" aria-hidden="true"></i></span>
        <span class="who"><b>${esc(name||'حساب نورا')}</b>
          <small>ورود و دسترسی از سرور تأیید شده‌اند.</small>
          <span class="pmeta">${chip(name?'نام از پروفایل حساب':'نام هنوز در پروفایل ثبت نشده')}</span></span>
        <button class="icon-btn edit" data-server-data-open="notifications" aria-label="اعلان‌های حساب">${ico('i-bell')}</button>
      </div>
      <div class="pstats">
        <button class="pstat" data-server-data-open="registrations"><b>${regCount}</b><small>ثبت‌نام</small></button>
        <button class="pstat" data-server-data-open="notifications"><b>${noticeCount}</b><small>اعلان${unread?` · ${faN(unread)} تازه`:''}</small></button>
        <button class="pstat" data-server-data-open="files"><b>${fileCount}</b><small>فایل حساب</small></button>
      </div>
      <div class="pacts">
        <button class="btn sm primary" data-server-data-open="registrations">${ico('i-calendar')} ثبت‌نام‌های من</button>
        <a class="btn sm quiet" href="account.html#forms">${ico('i-doc')} فرم‌های من</a>
        <button class="btn sm quiet" data-server-data-open="files">${ico('i-archive')} فایل‌ها</button>
        <span class="sp"></span><button class="btn sm quiet" data-server-account-logout>خروج</button>
      </div>
    </div>
  </section>`;
}
/* نوار فشردهٔ هویت برای زیرصفحه‌ها (فرم‌ها، پرداخت‌ها، بخش‌ها): سر صفحهٔ کامل فقط در «حساب من» تکرار می‌شود. */
function serverAccountStrip(){
  const state=SERVER_ACCOUNT_STATE;
  if(!state.account) return '';
  const name=serverAccountDisplayName(), initial=(name||'ن').slice(0,1);
  return `<div class="card acct server-account-strip server-account-head-mini">
    <span class="av sm">${esc(initial)}</span>
    <span class="who"><b>${esc(name||'حساب نورا')}</b><small>${esc(serverAccountProviderLabel(state.account))} وصل است · حساب امن</small></span>
    <a class="btn sm quiet" href="account.html">${ico('i-user')} حساب من</a>
    <button class="btn sm quiet" data-server-account-logout>خروج</button>
  </div>`;
}
/* نورا پی در حساب تولیدی: همان کارت تأییدشده، فقط با چیزی که سرور واقعاً دارد (وضعیت پرداخت ثبت‌نام‌ها). */
function serverPayBar(){
  const state=SERVER_ACCOUNT_STATE, guest=!state.account;
  const paid=state.registrations.filter(item=>item&&item.payment_status).length;
  const meta=guest?chip('وارد شو و وضعیت پرداخت‌هایت را ببین')
    :state.registrationsLoaded&&!state.registrationsError?chip(paid?faN(paid)+' ثبت‌نام دارای وضعیت پرداخت':'هنوز پرداختی ثبت نشده')
    :chip('وضعیت از سرور خوانده می‌شود');
  if(guest) return `<div class="paybar anim server-paybar is-guest" style="--i:1">
    <a class="pbmain" href="account.html#payments" aria-label="نورا پی · سفارش‌ها و پرداخت‌ها">
      <span class="pwal" aria-hidden="true">${ico('i-wallet')}</span>
      <span class="ptx"><small>نورا پی</small><b>سفارش‌ها و پرداخت‌ها</b></span>
      <span class="mini mini-guest">${ico('i-lock')}بعد از ورود</span>
      <svg class="i chev" aria-hidden="true"><use href="#i-chev-left"/></svg>
    </a>
  </div>`;
  return `<div class="paybar anim server-paybar" style="--i:1">
    <button class="pbmain" type="button" data-view="pay" aria-label="نورا پی · سفارش‌ها و پرداخت‌ها">
      <span class="pwal" aria-hidden="true">${ico('i-wallet')}</span>
      <span class="ptx"><small>نورا پی</small>
        <b>سفارش‌ها و پرداخت‌ها</b>
        <span class="pmeta">${meta}${chip('نسخهٔ اول · بدون موجودی','')}</span></span>
      <svg class="i chev" aria-hidden="true"><use href="#i-chev-left"/></svg>
    </button>
    <div class="pbrow">
      <a class="pbtn" href="account.html#payments">${ico('i-wallet')}پرداخت‌ها</a>
      <a class="pbtn" href="account.html#payments">${ico('i-doc')}رسیدها</a>
      <a class="pbtn" href="account.html#acc-20" title="خارج از نسخهٔ اول">${ico('i-split')}اقساط</a>
    </div>
    <p class="trustline" data-trust="pay"><svg class="i" aria-hidden="true"><use href="#i-shield"/></svg>
      <span>پرداخت هر ثبت‌نام از صفحهٔ همان فرم انجام می‌شود و وضعیت آن از سرور خوانده می‌شود؛ شمارهٔ کارت جایی ذخیره نمی‌شود.</span></p>
  </div>`;
}
/* «بخش‌های من» با همان ردیف‌های طراحی: رویدادهای من، فرم‌های من، پروفایل من، باشگاه کتاب‌خوانی. */
const SERVER_ROWS=[
  {k:'events',h:'account.html#events',n:'رویدادهای من',s:'ثبت‌نام‌ها، وضعیت و بلیت هر رویداد',i:'i-calendar'},
  {k:'forms',h:'account.html#forms',n:'فرم‌های من',s:'پاسخ‌های فرم و وضعیت بررسی',i:'i-doc'},
  {k:'library',h:'account.html#library',n:'محتوای من',s:'محتوای ضبط‌شده‌ای که به آن دسترسی داری',i:'i-play'},
  {k:'profile',h:'account.html#profile',n:'پروفایل من',s:'نوع ورود، دسترسی‌ها و پیوند حساب بله',i:'i-idcard'},
  {k:'book',h:'account.html#book',n:'باشگاه کتاب‌خوانی خط زندگی',s:'کتاب ماه، جلسه‌ها و تازه‌های باشگاه',i:'i-book'}
];
function serverRowsBox(){
  const state=SERVER_ACCOUNT_STATE, loaded=state.account&&state.registrationsLoaded&&!state.registrationsError;
  const guest=!state.account;
  /* مهمان: بخش‌های خصوصی با نشانهٔ «بعد از ورود» می‌آیند تا پیش از کلیک معلوم باشد چه انتظاری داشته باشد؛ مقصد و رفتار ورود همان قبلی است. */
  const mini=k=>k==='events'&&loaded?faN(state.registrationsTotal)+' ثبت‌نام':k==='forms'&&loaded?faN(state.registrationsTotal)+' پاسخ'
    :k==='library'&&state.account&&state.libraryLoaded&&!state.libraryError?faN(state.library.filter(x=>x.access&&x.access.state==='active').length)+' دسترسی فعال'
    :k==='book'?(guest?'':'تازه‌ها در خانه'):guest?'بعد از ورود':'';
  return `<div class="mrows anim server-rows${guest?' is-guest':''}" style="--i:3">
    <div class="mhead">${ico('i-layers')}<b>بخش‌های من</b><span class="sp" style="flex:1"></span>
      <span class="cap">${faN(SERVER_ROWS.length)} بخش</span></div>
    ${SERVER_ROWS.map(r=>`<a class="mrow2" href="${esc(r.h)}">
      <span class="ic">${ico(r.i)}</span>
      <span class="tx"><b>${esc(r.n)}</b>${guest?'':`<small>${esc(r.s)}</small>`}</span>
      ${mini(r.k)?`<span class="mini${guest&&r.k!=='book'?' mini-guest':''}">${ico(r.k==='book'?'i-book':guest?'i-lock':'i-check')}${esc(mini(r.k))}</span>`:''}
      <svg class="i chev" aria-hidden="true"><use href="#i-chev-left"/></svg>
    </a>`).join('')}</div>`;
}
function serverAccountGuestLanding(){
  const loginHref=serverLoginHref();
  /* «حساب من» برای مهمان، کمینه: یک بلوک کوتاه (آیکون، عنوان، یک جمله، یک کنش) و زیرش
     همان بخش‌های واقعی حساب. هیچ معرفی قابلیت، نمای ساختگی یا دادهٔ خصوصی ساخته نمی‌شود.
     مهمانِ مسیر پیوند باید بداند کجاست و چه باید بکند؛ کارت هویت‌ها برای کاربر بی‌نشست
     اصلاً ساخته نمی‌شود، پس توضیح همان‌جا می‌آید که چشمش است. */
  const linkNotice=linkModeRequested()?`<p class="cap ident-hint">${ico('i-lock')} این صفحه از
    <b>مسیر پیوند حساب</b> باز شده است. برای وصل‌کردن حساب بله، اول با شمارهٔ موبایلی که
    حسابت را با آن ساخته‌ای وارد شو؛ مالکیت حساب بله بعد از ورود و با امضای خودِ بله اثبات می‌شود.</p>`:'';
  const retry=SERVER_ACCOUNT_STATE.error?`<button class="btn account-promo-retry" data-server-account-retry aria-label="بررسی دوبارهٔ وضعیت ورود">${ico('i-refresh')} بررسی دوباره</button>`:'';
  return `<div class="account-promo">
    <section class="account-promo-hero" aria-labelledby="accountPromoTitle">
      <span class="account-promo-avatar" aria-hidden="true">${ico('i-user')}</span>
      <div class="account-promo-copy">
        <h2 id="accountPromoTitle">حساب من</h2>
        <p>برای ادامه وارد حساب شو.</p>
        ${linkNotice}
      </div>
      <div class="account-promo-actions">
        <a class="btn primary" href="${esc(loginHref)}">${ico('i-mobile')} ورود یا ساخت حساب</a>
        ${retry}
      </div>
    </section>
    ${serverRowsBox()}
    ${serverPayBar()}
  </div>`;
}
/* ══ همهٔ بخش‌های حساب (طبق طراحی تأییدشدهٔ prototype-34-user) ══
   دامنهٔ نسخهٔ اول (تصمیم ۲۶ مهر ۱۴۰۵):
   • h: مقصد واقعی موجود در وب (صفحه یا نمای حساب با endpoint)؛
   • st:'flow' مرحله‌ای از روند ثبت‌نام است که از صفحهٔ رویداد آغاز می‌شود؛
   • st:'bot' فعلاً فقط در ربات بله کار می‌کند؛ در وب وضعیتش گفته می‌شود و دادهٔ نمونه ندارد؛
   • st:'later' قابلیت مالی/محصولی خارج از نسخهٔ اول؛ هیچ رابط تراکنشی ساخته نمی‌شود. */
const ACCOUNT_SCREENS=[
  {n:'اطلاعات حساب',h:''},{n:'رویدادهای من',h:'account.html#events'},{n:'اعلان‌ها',h:'account.html#notifications'},
  {n:'تقویم رویدادها',h:'events.html#cal'},{n:'ثبت حضور رویداد',st:'bot'},{n:'کارنامهٔ حضور',st:'bot'},{n:'جزئیات گواهی',st:'bot'},{n:'استعلام گواهی',st:'bot'},{n:'آیدی‌کارت',st:'bot'},
  {n:'امتیاز و رتبه',st:'bot'},{n:'باشگاه من',st:'bot'},{n:'دعوت دوستان',st:'bot'},{n:'قرعه‌کشی',st:'bot'},{n:'هدایا و پاداش',st:'bot'},{n:'نظرسنجی',st:'bot'},
  {n:'برگزارشده‌ها و آفلاین',h:'events.html?status=past'},{n:'خرید آفلاین',st:'later'},{n:'فرم‌های من',h:'account.html#forms'},{n:'کانال‌ها',st:'bot'},{n:'کیف پول',st:'later'},{n:'اقساط من',st:'later'},
  {n:'اعتبار من',st:'later'},{n:'سررسید و صورت‌حساب',st:'later'},{n:'انتقال به دوست',st:'later'},{n:'کارت هدیه',st:'later'},{n:'افزایش و برداشت',st:'later'},
  {n:'امنیت و سقف‌ها',st:'later'},{n:'لینک پرداخت',st:'later'},{n:'لغو / انتقال',st:'bot'},{n:'پیگیری پستی',st:'bot'},{n:'سفارش چاپی / VIP',st:'bot'},
  {n:'همراه آوردن',st:'flow'},{n:'پیام ربات',h:'account.html#notifications'},{n:'پیام به کارشناس',h:'support.html'},{n:'تیکت',st:'bot'},{n:'نظر و پیشنهاد',st:'bot'},{n:'تأیید',st:'flow'},
  {n:'خانه',h:'home.html'},
  {n:'رویدادها',h:'events.html'},
  {n:'قواعد و شرایط',h:'support.html'},
  {n:'فرم',st:'flow'},
  {n:'پرداخت',h:'account.html#payments'},
  {n:'کارت‌به‌کارت',st:'flow'},
  {n:'رسید',h:'account.html#payments'},
  {n:'درگاه بله',st:'flow'},
  {n:'پایان',st:'flow'},
  {n:'حساب من',h:'account.html'},
  {n:'ورود',h:'login.html'},
  {n:'یک قدم مانده',st:'flow'},
  {n:'جزئیات رویداد',h:'events.html'},
  {n:'خانهٔ نورا پی',st:'later'},
  {n:'پشتیبانی',h:'support.html'},
  {n:'سؤالات',h:'support.html'},
  {n:'درباره ما',h:'support.html'}
];
const ACCOUNT_SCREEN_STATUS={
  bot:{tag:'فعلاً در ربات بله',cls:'tag',note:'این قابلیت در ربات بلهٔ نورا فعال است و هنوز در وب ارائه نمی‌شود.'},
  later:{tag:'خارج از نسخهٔ اول',cls:'tag warn',note:'این قابلیت مالی/محصولی در نسخهٔ اول وب ارائه نمی‌شود و رابط تراکنشی ندارد.'},
  flow:{tag:'از صفحهٔ رویداد',cls:'tag',note:'این مرحله بخشی از روند ثبت‌نام است و از صفحهٔ رویداد و فرم همان رویداد آغاز می‌شود.'}
};
function accountScreenAction(x,i){
  if(x.h!==undefined) return `<a class="btn sm quiet" href="${esc(x.h||'account.html#acc-0')}">باز کردن</a>`;
  const st=ACCOUNT_SCREEN_STATUS[x.st];
  if(x.st==='flow') return `<a class="btn sm quiet" href="events.html?status=upcoming">رویدادها</a> <span class="${st.cls}">${esc(st.tag)}</span>`;
  return `<a class="btn sm quiet" href="account.html#acc-${i}">وضعیت</a> <span class="${st?st.cls:'tag warn'}">${esc(st?st.tag:'در دست ساخت')}</span>`;
}
function accountScreensCard(){
  const rows=ACCOUNT_SCREENS.map((x,i)=>{ x.i=i;
    return `<div class="srow"><span class="sp"><b>${esc(x.n)}</b></span>${accountScreenAction(x,i)}</div>`;
  }).join('');
  return `<section class="card acct account-screens-index" aria-label="همهٔ بخش‌های حساب">
    <div class="head">همهٔ بخش‌های حساب</div>
    <p class="cap">بخش‌های بدون endpoint وب داده‌ی نمونه نمی‌گیرند؛ آنچه فعلاً در ربات بله است با همان برچسب و آنچه خارج از نسخهٔ اول است جدا نشان داده می‌شود.</p>
    <div class="stack" style="margin-top:8px">${rows}</div>
  </section>`;
}
/* ══ پیوند هویت: بله، شماره، آیندهٔ سکوهای دیگر ═════════════════════════
   قاعده‌ها:
   • مدرک اثبات مالکیت، فقط امضای `initData` خودِ بله است. در مرورگرِ بیرونِ
     بله چنین امضایی وجود ندارد، پس دکمهٔ بی‌اثر نشان نمی‌دهیم؛ راه درست را
     می‌گوییم.
   • تا وقتی سرور ۲۰۰ نداده، هیچ موفقیتی اعلام نمی‌شود و وضعیت «وصل شد» از
     پاسخ سرور خوانده می‌شود، نه از حدس.
   • دکمه در حال کار قفل می‌شود تا امضای یک‌بارمصرف دوباره فرستاده نشود.
   • می‌گوییم سرور چه گفته: `bale_link_available=false` یعنی این قابلیت روی
     این سرور پیکربندی نشده و همان را صادقانه نشان می‌دهیم. */
function identityProviders(){ return (IDENTITY_STATE.list&&IDENTITY_STATE.list.providers)||[] }
/* مسیر پیوند حساب را خودِ نشانی صفحه می‌گوید (`?link=bale`)، همان نشانه‌ای که
   ربات در دکمهٔ مینی‌اپ می‌گذارد و ui.js هم به‌خاطر آن ورود خودکار را کنار
   می‌گذارد. این‌جا فقط رابط با آن هم‌سو می‌شود؛ هیچ تشخیص حدسی‌ای نیست. */
function linkModeRequested(){
  const ui=UI();
  return !!(ui&&typeof ui.baleLinkMode==='function'&&ui.baleLinkMode());
}
function accountHasPhoneIdentity(){ return identityProviders().indexOf('phone')>-1 }
/* نشانی ورود با شماره، با حفظ نشانهٔ مسیر پیوند تا کاربر پس از ورود به همین
   مسیر برگردد و امضای بله همچنان دست‌نخورده بماند. */
function serverLoginHref(after){
  const next='account.html'+(linkModeRequested()?'?link=bale':'')+(after?'#'+after:'');
  return 'login.html?mode=server&next='+encodeURIComponent(next);
}
function isBaleLinked(){ return identityProviders().indexOf('bale')>-1 }
function identityLinkedAt(provider){
  const rows=(IDENTITY_STATE.list&&IDENTITY_STATE.list.rows)||[];
  const row=rows.find(x=>x.provider===provider);
  return row&&row.linked_at?accountServerDate(row.linked_at):'';
}
/* امضای آمادهٔ بله، از همان قاعدهٔ ui.js (یک مرجع، دو مصرف‌کننده). */
function baleInitDataReady(){
  const ui=UI();
  return !!(ui&&typeof ui.baleMiniAppInitData==='function'&&ui.baleMiniAppInitData());
}
/* نشان هر سطر، خودِ سکوست و وضعیت را «نشان» می‌گوید؛ پس وضعیت هم با رنگ و
   هم با متن بیان می‌شود، نه فقط با یک آیکون. */
function identityRow(icon,label,connected,detail){
  return `<div class="srow ident-row">
    ${ico(icon)}
    <span class="sp"><b>${esc(label)}</b><small class="cap">${esc(detail)}</small></span>
    ${chip(connected?'وصل است':'وصل نیست',connected?'ok':'warn')}</div>`;
}
function identityActionButton(){
  const state=IDENTITY_STATE, busy=state.busy==='link';
  if(isBaleLinked()) return '';
  if(!state.list||state.list.baleAvailable!==true) return '';
  /* در مسیر پیوند، نشستی که هویت شماره ندارد نمی‌تواند پیوند بزند: هویت بله
     از قبل به همان حساب خودکار تعلق دارد و سرور ۴۰۹ می‌دهد. به‌جای دکمهٔ
     بی‌سرانجام، راه درست (ورود با شماره) در یادآور همین کارت گفته می‌شود. */
  if(linkModeRequested()&&!accountHasPhoneIdentity()) return '';
  if(!baleInitDataReady()) return '';
  return `<button class="btn primary" data-identity-link ${busy||state.busy?'disabled':''}${busy?' aria-busy="true"':''}>
    ${busy?ico('i-refresh')+' در حال پیوند…':ico('i-link')+' پیوند حساب بله'}</button>`;
}
function identityOutsideBaleNote(){
  const ui=UI();
  const href=ui&&typeof ui.baleStartHref==='function'?ui.baleStartHref('link_account'):'';
  const action=href?`<a class="btn sm primary" href="${esc(href)}" target="_blank" rel="noopener noreferrer">${ico('i-send')} بازکردن بله</a>`:'';
  return `<p class="cap ident-hint">${ico('i-lock')} برای اثبات مالکیت، این صفحه باید از داخل خودِ بله باز شود؛
    آن‌جا امضای یک‌بارمصرف حسابت در دسترس است. پیوند با شماره یا نام انجام نمی‌شود.
    ${action}</p>`;
}
function identityUnlinkButton(){
  const state=IDENTITY_STATE;
  if(!isBaleLinked()) return '';
  if(state.busy==='unlink') return `<button class="btn quiet" disabled aria-busy="true">${ico('i-refresh')} در حال برداشتن…</button>`;
  /* اگر بله تنها هویت حساب باشد، سرور برداشتنش را رد می‌کند؛ از پیش توضیح می‌دهیم. */
  if(identityProviders().length<2)
    return `<span class="tag warn">تنها راه ورود حساب است؛ برداشتنش ممکن نیست.</span>`;
  if(state.confirmUnlink) return `<div class="row" style="flex-wrap:wrap">
      <button class="btn quiet" data-identity-unlink-confirm>${ico('i-check')} بله، پیوند برداشته شود</button>
      <button class="btn sm quiet" data-identity-unlink-cancel>انصراف</button></div>`;
  return `<button class="btn sm quiet" data-identity-unlink>${ico('i-close')} برداشتن پیوند بله</button>`;
}
function identityRowsBody(){
  const phoneLinked=identityProviders().indexOf('phone')>-1;
  const baleLinked=isBaleLinked();
  return `<div class="stack" style="margin-top:8px">
      ${identityRow('i-mobile','شمارهٔ موبایل',phoneLinked,
        phoneLinked?'ورود با پیامک یک‌بارمصرف انجام می‌شود.':'این حساب با شماره ساخته نشده است.')}
      ${identityRow('i-send','حساب بله',baleLinked,
        baleLinked?(identityLinkedAt('bale')?`پیوندشده در ${esc(identityLinkedAt('bale'))}`:'به همین حساب وصل است.')
          :'با پیوند بله، اعلان‌ها و فایل‌هایت در ربات هم به همین حساب می‌رسد.')}
    </div>`;
}
/* هدایت صریح مسیر پیوند: تا کاربر بداند اول باید با کدام حساب وارد شود. */
function identityLinkModeNotice(){
  const state=IDENTITY_STATE;
  if(!linkModeRequested()||state.error) return '';
  if(!SERVER_ACCOUNT_STATE.account)
    return `<p class="cap ident-hint">${ico('i-lock')} این صفحه از <b>مسیر پیوند حساب</b> باز شده است.
      برای وصل‌کردن، اول با شمارهٔ موبایلی که حسابت را با آن ساخته‌ای وارد شو؛ بعد مالکیت حساب بله با امضای خودِ بله اثبات می‌شود.</p>`;
  /* تا وضعیت هویت‌ها از سرور نیامده، هیچ ادعایی دربارهٔ نوع حساب نمی‌کنیم. */
  if(!state.list) return '';
  /* حسابی که هویت شماره دارد، مسیر عادی پیوند را می‌رود؛ این یادآور برای
     حسابی است که فقط بله دارد (زادهٔ ورود خودکار) و باید مالکش با شماره
     وارد شود. توجه: حساب «فقط بله» می‌تواند پیوندشده هم باشد؛ ولی همان حساب
     برای کاربرِ شماره‌ای او حساب دیگری است و هویت بله جابه‌جا نمی‌شود. */
  if(accountHasPhoneIdentity()) return '';
  const login=serverLoginHref();
  return `<p class="cap ident-hint">${ico('i-lock')} این نشست یک <b>حساب بله</b> است، نه حساب شماره‌ای‌ات.
    برای وصل‌کردن، اول با شمارهٔ موبایل وارد شو تا حساب شماره‌ای همان‌جا باز شود.
    <a class="btn sm primary" href="${esc(login)}">${ico('i-mobile')} ورود با شماره</a></p>`;
}
function identityHintLine(){
  /* دلیل نبودِ دکمه را می‌گوییم تا کاربر پشت دکمهٔ نبوده نماند. */
  const state=IDENTITY_STATE;
  if(isBaleLinked()||state.error) return '';
  if(state.list&&state.list.baleAvailable!==true)
    return `<p class="cap ident-hint">${ico('i-lock')} پیوند بله روی این سرور پیکربندی نشده است؛ اکنون فقط ورود با شماره فعال است.</p>`;
  if(!baleInitDataReady()) return identityOutsideBaleNote();
  return '';
}
function identityOutcomeLine(){
  const outcome=IDENTITY_STATE.outcome;
  if(!outcome||!outcome.text) return '';
  const good=outcome.kind==='ok';
  return `<p class="cap ${good?'ident-notice':'ident-error'}" role="${good?'status':'alert'}">
    ${ico(good?'i-check':'i-flag')} ${esc(outcome.text)}</p>`;
}
function identityOutcome(kind,text){ IDENTITY_STATE.outcome={kind,text} }
/* پیام خطای سرور از قبل فارسی و قابل‌اقدام است؛ اگر متن، «کد» خام بود
   (خطای داخلی کلاینت)، به‌جای کد، جملهٔ روشن نشان می‌دهیم. */
function identityErrorText(error,fallback){
  const message=error&&typeof error.message==='string'?error.message:'';
  return message&&!/^[a-z0-9_]+$/.test(message)?message:fallback;
}
function serverAccountIdentitiesCard(){
  const state=IDENTITY_STATE;
  if(!SERVER_ACCOUNT_STATE.account) return '';
  const body=state.loading&&!state.loaded
    ? `<div class="empty2"><b>در حال خواندن وضعیت پیوند…</b></div>`
    : state.error
      ? `<div class="empty2"><b>${esc(state.error)}</b><button class="btn quiet" data-identity-retry>${ico('i-refresh')} تلاش دوباره</button></div>`
      : identityRowsBody();
  /* نتیجهٔ عملیات جدا از خطای خواندن نشان داده می‌شود؛ موفقیتی که سرور تأیید
     کرده با شکستِ بازخوانیِ فهرست باطل نمی‌شود. نتیجهٔ ناموفق هم پایدار می‌ماند:
     تعارض حساب یا امضای نامعتبر چیزی است که کاربر باید بخواند و برایش تصمیم
     بگیرد، نه پیامی که با محو شدن اعلان از یاد برود. */
  const notice=identityOutcomeLine();
  const settled=state.loaded&&!state.error;
  return `<section class="card acct server-account-identities anim">
    <div class="row">${ico('i-shield')}<span class="sp"><b>راه‌های ورود و پیوند حساب</b>
      <small class="cap">پیوند فقط با اثبات مالکیت انجام می‌شود؛ سرور مرجع نهایی است.</small></span>
      ${settled?chip(isBaleLinked()?'بله وصل است':'فقط شماره',isBaleLinked()?'ok':''):''}</div>
    ${body}
    ${identityLinkModeNotice()}
    ${identityHintLine()}
    ${notice}
    <div class="row" style="margin-top:10px;flex-wrap:wrap">${identityActionButton()}${identityUnlinkButton()}</div>
  </section>`;
}
/* پیوند: مدرک از بله خوانده می‌شود، نه از ورودی کاربر. */
async function linkBaleIdentity(){
  const state=IDENTITY_STATE, api=window.NORA_SERVER_API;
  if(state.busy) return;
  if(!api||typeof api.linkBaleIdentity!=='function'){toast('رابط حساب سرور در دسترس نیست');return}
  const ui=UI();
  const initData=ui&&typeof ui.baleMiniAppInitData==='function'?ui.baleMiniAppInitData():'';
  if(!initData){toast('امضای بله در دسترس نیست؛ این صفحه را از داخل بله باز کن.');return}
  state.busy='link'; state.outcome=null; renderProfile();
  try{
    const result=await api.linkBaleIdentity(initData);
    if(!result||result.linked!==true) throw new Error('invalid_identity_link_response');
    state.busy='';
    const done=result.already_linked===true?'این حساب بله از قبل به همین حساب وصل بود.':'حساب بله به حسابت وصل شد.';
    identityOutcome('ok',done); toast(done);
    /* وضعیت را از سرور بازمی‌خوانیم تا «وصل شد» ادعای کلاینت نباشد. اگر این
       خواندن شکست خورد، موفقیتِ واقعیِ پاسخ سرور را انکار نمی‌کنیم و در کنارش
       خطای خواندن و دکمهٔ تلاش دوباره می‌ماند؛ فهرست جعلی نمی‌سازیم. */
    await loadAccountIdentities(true);
  }catch(error){
    state.busy='';
    if(error&&error.status===401&&error.code==='authentication_required'){serverAccountExpired();return}
    identityOutcome('error',identityErrorText(error,'پیوند انجام نشد؛ دوباره تلاش کن.'));
    renderProfile();
    return;
  }
  renderProfile();
}
async function unlinkBaleIdentity(){
  const state=IDENTITY_STATE, api=window.NORA_SERVER_API;
  if(state.busy) return;
  if(!api||typeof api.unlinkBaleIdentity!=='function'){toast('رابط حساب سرور در دسترس نیست');return}
  state.busy='unlink'; state.confirmUnlink=false; state.outcome=null; renderProfile();
  try{
    const result=await api.unlinkBaleIdentity();
    if(!result||result.linked!==false) throw new Error('invalid_identity_unlink_response');
    state.busy='';
    const done='پیوند بله برداشته شد؛ هیچ سابقه‌ای پاک نشد.';
    identityOutcome('ok',done); toast(done);
    await loadAccountIdentities(true);
  }catch(error){
    state.busy='';
    if(error&&error.status===401&&error.code==='authentication_required'){serverAccountExpired();return}
    identityOutcome('error',identityErrorText(error,'برداشتن پیوند انجام نشد؛ دوباره تلاش کن.'));
    renderProfile();
    return;
  }
  renderProfile();
}
function serverAccountModulesCard(){
  return accountScreensCard();
}
function serverAccountFeatureView(t,title,description){
  if(SERVER_ACCOUNT_STATE.checking) return viewHead(t,'',null)+serverAccountAccessCard();
  return viewHead(t,'',null)+serverAccountStrip()+serverAccountAccessCard()+card(title,description,'i-info',
    `<p class="cap">این بخش در API حساب وب موجود نیست؛ هیچ دادهٔ محلی یا نمونه‌ای نمایش داده نمی‌شود.</p>
     <a class="btn quiet" href="account.html">بازگشت به حساب من</a>`);
}
/* ══ صفحهٔ پروفایل: سر، میان‌بُرها، رویداد نزدیک و بخش‌ها ═══════════ */
function profileHTML(){
  const state=SERVER_ACCOUNT_STATE;
  if(!TEST_FIXTURE_MODE) return state.account
    ?serverAccountHead()+serverPayBar()+serverRowsBox()+serverAccountIdentitiesCard()+serverAccountModulesCard()
    :serverAccountGuestLanding();
  if(state.checking) return serverAccountAccessCard();
  const connected=!!state.account;
  const localHeader=connected?'':(login()?headMember():headGuest());
  const previewNote=connected?`<div class="card acct server-preview-note"><b>بخش‌های پیش‌نمایش</b>
    <p class="cap">رویدادها، پرداخت، امتیاز و فرم‌های این صفحه هنوز دادهٔ محلی‌اند و از حساب سرور خوانده نمی‌شوند.</p></div>`:'';
  return serverAccountHead()+serverAccountAccessCard()+localHeader+previewNote+payBox()+nextBox()+rowsBox();
}

function viewHead(t,sub,tabs,key){
  key=key||'vtab'; const cur=S[key];
  return `<div class="vhead"><div class="vrow"><button class="vback" data-back aria-label="بازگشت به حساب من">
      ${ico('i-chev-right')}</button>
      <span class="vh2">${esc(t.n)}</span></div>
    <p class="vhsub">${esc(sub||t.s||'')}</p>
    ${tabs?`<div class="vtabs" role="tablist" aria-label="بخش‌های ${esc(t.n)}">${tabs.map(t2=>`<button class="vtab${cur===t2.k?' on':''}" role="tab"
      aria-selected="${cur===t2.k}" tabindex="${cur===t2.k?'0':'-1'}" data-${key}="${t2.k}">
      ${t2.i?ico(t2.i):''} ${esc(t2.n)}</button>`).join('')}</div>`:''}</div>`;
}
function accountServerDate(value){
  if(!value) return '';
  try{return new Intl.DateTimeFormat('fa-IR',{dateStyle:'medium',timeStyle:'short'}).format(new Date(value))}
  catch(e){return String(value)}
}
function accountFileSize(bytes){
  const size=Math.max(0,+bytes||0);
  return size>=1024*1024?faN((size/1024/1024).toFixed(1))+' مگابایت':faN(Math.max(1,Math.round(size/1024)))+' کیلوبایت';
}
function accountBotDeliveryHref(payload){
  const ui=UI();
  return ui&&typeof ui.baleStartHref==='function'?ui.baleStartHref(payload):'';
}
function privateAccountDeliveryHref(id){
  const fileId=String(id||'');
  if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(fileId)) return '';
  return accountBotDeliveryHref('private_'+fileId);
}
function accountNotificationFiles(item){
  const refs=Array.isArray(item.file_refs)?item.file_refs.filter(id=>typeof id==='string'&&id):[];
  if(!refs.length) return '';
  return `<div class="server-notice-files">${refs.map(id=>{
    const href=privateAccountDeliveryHref(id);
    return href?`<a class="btn sm quiet" href="${esc(href)}" target="_blank" rel="noopener noreferrer">${ico('i-send')} دریافت پیوست از بات بله</a>`
      :`<span class="tag warn">پیوند دریافت بات در دسترس نیست</span>`;
  }).join('')}</div>`;
}
/* فاز ۹.۴: پیوند اعلان فقط وقتی رندر می‌شود که نسبی و به صفحهٔ داخل برنامه باشد (همان قاعدهٔ سرور؛ هرگز URL فایل/API). */
function accountNotificationHref(link){
  const raw=typeof link==='string'?link.trim():'';
  if(!raw||!/^\/(event|events|account|certificate)\.html(?:\?[A-Za-z0-9_\-=&.%]*)?(?:#[A-Za-z0-9_\-]*)?$/.test(raw)) return '';
  return raw.slice(1);
}
function accountNotificationLinkLabel(item,href){
  if(/^event\.html\?id=.*#qa$/.test(href)) return 'دیدن پاسخ در صفحهٔ رویداد';
  if(/^event\.html/.test(href)) return item.kind==='recording_content'?'دیدن محتوای تازه':'رفتن به صفحهٔ محصول';
  if(/#certificates$/.test(href)) return 'دیدن گواهی‌ها';
  if(/#orders$/.test(href)) return 'دیدن سفارش‌ها';
  if(/#events$/.test(href)) return 'دیدن رویدادهای من';
  return 'باز کردن';
}
function accountNotificationsContent(){
  const state=SERVER_ACCOUNT_STATE;
  const items=state.notifications.map(item=>{
    /* وضعیت ارسال از سرور: صف ≠ تحویل. حسابِ بدون هویت بلهٔ پیوندشده، اعلان را فقط همین‌جا می‌خواند و «خطای ارسال» نیست. */
    const delivery=item.delivery_status==='delivered'?'در ربات بله تحویل شد'
      :item.last_delivery_error==='no_bale_identity'?'حساب شما به بله پیوند نخورده؛ این اعلان فقط همین‌جا خوانده می‌شود'
      :item.delivery_status==='failed'?'ارسال در بله انجام نشد؛ از پیوند بات استفاده کن'
      :item.delivery_state==='retrying'?`ارسال از بات در حال تلاش دوباره است (${faN(item.delivery_attempts||0)} تلاش)`
      :'برای ارسال از بات در صف است؛ هنوز تحویل نشده';
    return `<article class="card acct server-notice ${item.read?'read':'unread'}">
      <div class="row"><b>${esc(item.title||'اعلان نورا')}</b><span class="sp"></span>${chip(item.read?'خوانده‌شده':'تازه',item.read?'':'warn')}</div>
      <p class="server-notice-body">${esc(item.body||'')}</p>
      <div class="cap">${esc(accountServerDate(item.created_at))} · ${esc(delivery)}</div>
      ${accountNotificationFiles(item)}
      ${(()=>{const href=accountNotificationHref(item.link); return href?`<div class="row" style="margin-top:8px"><a class="btn sm" href="${esc(href)}" data-account-notice-link="${esc(item.kind||'')}">${ico('i-link')} ${esc(accountNotificationLinkLabel(item,href))}</a></div>`:''})()}
      ${item.read?'':`<div class="row" style="margin-top:8px"><span class="sp"></span><button class="btn sm quiet" data-account-notice-read="${esc(item.id)}">${ico('i-check')} خواندم</button></div>`}
    </article>`;
  }).join('');
  const body=state.notificationsLoading&&!state.notificationsLoaded
    ?`<div class="empty2"><b>در حال خواندن اعلان‌ها…</b></div>`
    :state.notificationsError?`<div class="empty2"><b>${esc(state.notificationsError)}</b><button class="btn quiet" data-account-data-refresh>تلاش دوباره</button></div>`
    :items||empty2('اعلانی نیست','اگر بررسی پروفایل یا فیشی انجام شود، خبرش همین‌جا می‌آید.','i-bell');
  return `<div class="row" style="margin:0 0 8px"><span class="cap">اعلان‌های حساب مشترک با ربات بله</span><span class="sp"></span>
    <button class="btn sm quiet" data-account-data-refresh aria-label="بازخوانی اعلان‌ها">${ico('i-refresh')} بازخوانی</button></div>
    <div class="stack">${body}</div>
    ${state.notificationsMore?`<div class="row"><span class="sp"></span><button class="btn quiet" data-account-notices-more>اعلان‌های بیشتر</button></div>`:''}`;
}
function accountFilesContent(){
  const state=SERVER_ACCOUNT_STATE;
  const items=state.files.map(file=>{
    const href=privateAccountDeliveryHref(file.id);
    return `<article class="card acct server-account-file">
      <div class="row">${ico(String(file.content_type||'').startsWith('image/')?'i-image':'i-doc')}<span class="sp"><b>${esc(file.file_name||'فایل حساب')}</b>
        <small class="cap">${esc(file.content_type||'فایل')} · ${esc(accountFileSize(file.content_size))}</small></span></div>
      <div class="row"><small class="cap">${esc(accountServerDate(file.created_at))}</small><span class="sp"></span>
        ${href?`<a class="btn sm primary" href="${esc(href)}" target="_blank" rel="noopener noreferrer">${ico('i-send')} دریافت در بات بله</a>`:`<span class="tag warn">پیوند دریافت بات تنظیم نشده</span>`}</div>
    </article>`;
  }).join('');
  const body=state.filesLoading&&!state.filesLoaded
    ?`<div class="empty2"><b>در حال خواندن فایل‌ها…</b></div>`
    :state.filesError?`<div class="empty2"><b>${esc(state.filesError)}</b><button class="btn quiet" data-account-data-refresh>تلاش دوباره</button></div>`
    :items||empty2('فایلی ثبت نشده','عکس پروفایل و پیوست‌های درخواست پس از ثبت در این فهرست می‌آیند.','i-archive');
  return `<div class="row" style="margin:0 0 8px"><span class="cap">فایل‌های خصوصی همین حساب؛ دریافت فقط از بات بله</span><span class="sp"></span>
    <button class="btn sm quiet" data-account-data-refresh aria-label="بازخوانی فایل‌ها">${ico('i-refresh')} بازخوانی</button></div>
    <div class="stack">${body}</div>
    ${state.filesMore?`<div class="row"><span class="sp"></span><button class="btn quiet" data-account-files-more>فایل‌های بیشتر</button></div>`:''}`;
}
function accountRegistrationPayment(item){
  const labels={pending:'در انتظار پرداخت',paid:'پرداخت شد',paid_review:'پرداخت در حال بررسی',
    awaiting_receipt:'در انتظار رسید',receipt_submitted:'رسید ثبت شد',paid_manual:'پرداخت تأیید شد',
    rejected:'پرداخت رد شد',cancelled:'صورتحساب لغو شد',expired:'صورتحساب منقضی شد'};
  return labels[item.payment_status]||'';
}
/* فاز ۹.۳: پیوند «مشاهدهٔ جلسات» در «رویدادهای من» فقط از کتابخانهٔ سرور (/api/account/recordings) می‌آید؛
   ثبت‌نام یا حتی «حضور ثبت شده» به‌تنهایی پیوند نمی‌سازد — تصمیم دسترسی (خرید/رایگان/اعطا/حضور با سیاست محصول) با سرور است. */
function accountRegistrationArchive(item){
  const state=SERVER_ACCOUNT_STATE;
  if(!state.libraryLoaded||state.libraryError||!item||typeof item.event_id!=='string'||!item.event_id) return null;
  const found=state.library.find(x=>x&&x.event_id===item.event_id&&x.access&&x.access.state==='active'&&typeof x.recording_id==='string');
  return found||null;
}
function accountRegistrationsContent(mode){
  const state=SERVER_ACCOUNT_STATE;
  const source=mode==='payments'?state.registrations.filter(item=>!!item.payment_status):state.registrations;
  const items=source.map(item=>{
    const status=item.status==='waitlisted'?chip('فهرست انتظار','warn'):chip('ثبت شد','ok');
    const schedule=[item.event_date,item.event_time].filter(Boolean).join(' · ');
    const payment=accountRegistrationPayment(item);
    const ticketType=item.ticket_type&&typeof item.ticket_type.name==='string'?item.ticket_type.name:'';
    const archive=mode==='events'||!mode?accountRegistrationArchive(item):null;
    const archiveSource=archive?({attended:'آرشیو برای حاضران این رویداد',purchase:'آرشیو خریداری‌شده',free:'آرشیو رایگان',granted:'آرشیو اعطاشده'}[archive.access.source]||'آرشیو در دسترس'):'';
    return `<article class="card acct server-registration"${item.event_id?` data-account-registration-event="${esc(item.event_id)}"`:''}>
      <div class="row"><span class="sp"><b>${esc(item.event_title||item.form_name)}</b>
        <small class="cap">${esc(item.form_name)}${schedule?' · '+esc(schedule):''}</small></span>${status}</div>
      <div class="row" style="margin-top:7px;flex-wrap:wrap">
        <small class="cap">ثبت‌نام: ${esc(accountServerDate(item.created_at))}</small>
        ${payment?`<span class="tag warn">${esc(payment)}</span>`:''}
        ${ticketType?`<span class="tag">${esc(ticketType)}</span>`:''}
        ${item.ticket_checked_in?chip('حضور ثبت شده','ok'):''}
      </div>
      ${archive?`<div class="row" style="margin-top:8px;flex-wrap:wrap;gap:8px" data-account-registration-archive="${esc(archive.recording_id)}" data-archive-source="${esc(archive.access.source||'')}">
        <small class="cap">${esc(archiveSource)}${archive.session_count>0?' · '+faN(archive.session_count)+' جلسه':''}</small><span class="sp"></span>
        <a class="btn sm primary" href="${esc(recEventHref(archive,'#recording-sessions'))}" data-account-registration-view>${ico('i-play')} مشاهدهٔ جلسات</a></div>`:''}
    </article>`;
  }).join('');
  const loading=state.registrationsLoading&&!state.registrationsLoaded||!state.registrationsLoaded&&!state.registrationsError;
  const body=loading?`<div class="empty2"><b>در حال خواندن ثبت‌نام‌ها…</b></div>`
    :state.registrationsError?`<div class="empty2"><b>${esc(state.registrationsError)}</b><button class="btn quiet" data-account-registrations-refresh>تلاش دوباره</button></div>`
    :items||(mode==='payments'?empty2('پرداختی به حسابت وصل نیست','وضعیت پرداخت هر ثبت‌نام پولی همین‌جا می‌آید؛ رسید از صفحهٔ همان فرم دریافت می‌شود.','i-wallet')
      :mode==='forms'?empty2('پاسخ فرمی به حسابت وصل نیست','فرم بعدی که با این حساب پر کنی اینجا می‌آید.','i-doc')
      :empty2('ثبت‌نامی به حسابت وصل نیست','ثبت‌نام بعدی‌ات اینجا می‌آید.','i-calendar'));
  const counter=mode==='payments'?`${faN(source.length)} ثبت‌نام دارای وضعیت پرداخت از ${faN(state.registrationsTotal)}`
    :mode==='forms'?`${faN(state.registrationsTotal)} پاسخ فرم در این حساب`:`${faN(state.registrationsTotal)} ثبت‌نام در این حساب`;
  /* سفارش‌های محتوای ضبط‌شده جدا از پرداخت ثبت‌نام‌ها فهرست می‌شوند: خرید محتوا ≠ ثبت‌نام رویداد. */
  const orders=mode==='payments'&&!TEST_FIXTURE_MODE?`<h3 class="rec-h3">سفارش‌های محتوای ضبط‌شده</h3>${accountRecordingOrdersContent()}<h3 class="rec-h3" style="margin-top:14px">پرداخت ثبت‌نام‌ها</h3>`:'';
  return orders+`<div class="row" style="margin:0 0 8px"><span class="cap">${counter}</span><span class="sp"></span>
    <button class="btn sm quiet" data-account-registrations-refresh aria-label="بازخوانی ثبت‌نام‌ها">${ico('i-refresh')} بازخوانی</button></div>
    <div class="stack">${body}</div>
    ${state.registrationsMore?`<div class="row"><span class="sp"></span><button class="btn quiet" data-account-registrations-more>ثبت‌نام‌های بیشتر</button></div>`:''}`;
}
const ACCOUNT_REGISTRATION_VIEWS={
  forms:{k:'forms',n:'فرم‌های من',s:'پاسخ‌های فرم و ثبت‌نام‌های همین حساب از سرور',i:'i-doc'},
  payments:{k:'payments',n:'سفارش‌ها و پرداخت‌ها',s:'سفارش‌های محتوای ضبط‌شده و وضعیت پرداخت ثبت‌نام‌های پولی همین حساب از سرور',i:'i-wallet'}
};
const ACCOUNT_LIBRARY_VIEW={k:'library',n:'محتوای من',s:'محتوای ضبط‌شده‌ای که این حساب به آن دسترسی دارد؛ وضعیت و مهلت از سرور خوانده می‌شود.',i:'i-play'};
/* ── فاز ۹: سفارش‌های محتوای ضبط‌شده و کتابخانهٔ حساب ──
   خرید ≠ ثبت‌نام ≠ حضور: این بخش فقط دسترسی‌ها و سفارش‌های محتوای ضبط‌شده را نشان می‌دهد.
   فاز ۹.۱: خرید، رسید و پیگیری پرداخت فقط از فرم خریدِ فرم‌ساز (form.html) انجام می‌شود؛ این صفحه
   دفتر داخلی سفارش را فقط می‌خواند و به همان فرم پیوند می‌دهد. دسترسی تنها با تصمیم سرور/درگاه ساخته می‌شود. */
const REC_ORDER_STATUS={pending:['در انتظار پرداخت','warn'],awaiting_receipt:['در انتظار رسید','warn'],receipt_submitted:['رسید ثبت شد؛ در انتظار بررسی','warn'],
  paid:['پرداخت شد','ok'],paid_manual:['پرداخت تأیید شد','ok'],needs_review:['نیازمند بررسی','warn'],rejected:['رد شد','bad'],
  cancelled:['لغو شد',''],expired:['منقضی شد',''],refunded:['بازپرداخت شد','']};
const REC_ACCESS_STATE={active:['دسترسی فعال','ok'],expired:['منقضی‌شده',''],revoked:['لغوشده','bad']};
function recMoney(amount,currency){ const n=Math.max(0,Math.round(+amount||0)); return faN(n.toLocaleString('en-US'))+' '+(currency==='IRR'||!currency?'ریال':esc(String(currency))); }
function recDuration(minutes){ const m=Math.max(0,Math.round(+minutes||0)); if(!m) return ''; const h=Math.floor(m/60), r=m%60;
  return h?(faN(h)+' ساعت'+(r?' و '+faN(r)+' دقیقه':'')):faN(m)+' دقیقه'; }
function recEventHref(item,anchor){ return 'event.html?id='+encodeURIComponent(String(item.event_id||''))+(anchor||'#recording'); }
function recFormHref(item){ const id=String(item&&item.purchase_form_id||''); return /^[A-Za-z0-9_-]{1,100}$/.test(id)?'form.html?fid='+encodeURIComponent(id)+'&kind=reg':''; }
function recOrderCard(order){
  const state=SERVER_ACCOUNT_STATE, [label,tone]=REC_ORDER_STATUS[order.status]||[order.status,''];
  const busy=state.recOrderBusy===order.id;
  const title=order.title||order.event_title||'محتوای ضبط‌شده';
  const openCard=order.open&&order.method==='card_transfer'&&order.card&&['pending','awaiting_receipt'].includes(order.status);
  const cardNumber=openCard?String(order.card.number||'').replace(/\D/g,'').replace(/(\d{4})(?=\d)/g,'$1-'):'';
  const facts=[`ثبت: ${esc(accountServerDate(order.created_at))}`,
    order.paid_at?`پرداخت: ${esc(accountServerDate(order.paid_at))}`:'',
    order.receipt_submitted_at?`رسید: ${esc(accountServerDate(order.receipt_submitted_at))}`:'',
    order.decided_at?`تصمیم: ${esc(accountServerDate(order.decided_at))}`:'',
    order.refunded_at?`بازپرداخت: ${esc(accountServerDate(order.refunded_at))}`:'',
    order.open&&order.expires_at?`مهلت: ${esc(accountServerDate(order.expires_at))}`:''].filter(Boolean);
  let actions='';
  const formHref=recFormHref(order), viaForm=!!(order.form_payment_id||order.form_response_id);
  const formLink=formHref?`<a class="btn sm primary" href="${esc(formHref)}" data-account-rec-form>${ico('i-doc')} ادامه در فرم خرید</a>`
    :`<small class="cap" data-account-rec-form-missing>فرم خرید این محتوا فعلاً منتشر نیست؛ وضعیت را از صفحهٔ محصول پیگیری کن.</small>`;
  if(order.paid) actions=`<a class="btn sm primary" href="${esc(recEventHref(order,'#recording-sessions'))}" data-account-rec-view>${ico('i-play')} مشاهدهٔ جلسات</a>`;
  else if(order.open&&viaForm){
    /* سفارش فرم‌دار: پرداخت/رسید/پیگیری در همان فرم خرید؛ این‌جا فقط وضعیت خوانده می‌شود. */
    const note=order.status==='receipt_submitted'?'رسید در فرم خرید ثبت شده و در صف بررسی مدیران است؛ تا تصمیم، دسترسی فعال نمی‌شود.'
      :order.status==='needs_review'?'پرداخت نیازمند بررسی دستی است؛ نتیجه پس از تصمیم همین‌جا و در اعلان‌ها می‌آید.'
      :order.method==='bale_wallet'?'پرداخت کیف پول بله از همان فرم خرید ادامه می‌یابد؛ وضعیت فقط پس از تأیید وب‌هوک تغییر می‌کند.'
      :'واریز و بارگذاری رسید در همان فرم خرید انجام می‌شود؛ مبلغ و کارت مقصد را فرم از سرور نشان می‌دهد.';
    actions=`<small class="cap" data-account-rec-via-form>${esc(note)}</small>${['receipt_submitted','needs_review'].includes(order.status)?(formHref?`<a class="btn sm quiet" href="${esc(formHref)}" data-account-rec-form>${ico('i-doc')} مشاهدهٔ وضعیت در فرم خرید</a>`:''):formLink}`;
  }else if(order.open){
    /* سفارش قدیمی (پیش از ۹.۱) بدون فرم: مسیر رسید حساب بازنشسته است؛ فقط انصراف یا خرید از فرم. */
    const invoice=order.method==='bale_wallet'&&order.status==='pending'&&typeof order.invoice_url==='string'&&/^https:\/\//.test(order.invoice_url)
      ?`<a class="btn sm primary" href="${esc(order.invoice_url)}" target="_blank" rel="noopener" data-account-rec-invoice>${ico('i-wallet')} ادامهٔ پرداخت در بله</a>`:'';
    const cancel=['pending','awaiting_receipt'].includes(order.status)?`<button class="btn sm quiet" type="button" data-account-rec-cancel="${esc(order.id)}" ${busy?'disabled':''}>انصراف از سفارش</button>`:'';
    const waiting=order.status==='receipt_submitted'||order.status==='needs_review'?`<small class="cap">${order.status==='needs_review'?'پرداخت نیازمند بررسی دستی است؛ نتیجه پس از تصمیم همین‌جا می‌آید.':'رسید رسیده و در صف بررسی است؛ تا تصمیم، دسترسی فعال نمی‌شود.'}</small>`:'';
    const legacy=order.method==='card_transfer'&&['pending','awaiting_receipt'].includes(order.status)
      ?`<small class="cap" data-account-rec-legacy>این سفارش پیش از اتصال فروش به فرم‌ساز ثبت شده و بارگذاری رسید برای آن در این صفحه بسته است. اگر هنوز واریزی نکرده‌ای، انصراف بده و از فرم خرید اقدام کن؛ اگر واریز کرده‌ای، با برگزارکننده در تماس باش.</small>`:'';
    actions=`${openCard?`<div class="rec-card-dest"><b>کارت مقصد:</b> <span dir="ltr">${esc(cardNumber)}</span>${order.card.bank?' · '+esc(order.card.bank):''}${order.card.holder?' · '+esc(order.card.holder):''}<br><b>مبلغ:</b> ${recMoney(order.amount,order.currency)}</div>`:''}${legacy}${invoice}${waiting}<div class="row" style="flex-wrap:wrap;gap:8px">${cancel}${cancel&&formHref?`<a class="btn sm quiet" href="${esc(formHref)}" data-account-rec-form>${ico('i-doc')} خرید از فرم خرید</a>`:''}</div>`;
  }else if(order.status==='rejected'||order.status==='cancelled'||order.status==='expired') actions=formHref?`<a class="btn sm quiet" href="${esc(formHref)}" data-account-rec-retry>${ico('i-refresh')} خرید دوباره از فرم خرید</a>`
    :`<a class="btn sm quiet" href="${esc(recEventHref(order))}" data-account-rec-retry>${ico('i-refresh')} صفحهٔ محصول</a>`;
  else if(order.status==='refunded') actions=`<small class="cap">دسترسی این سفارش پس از بازپرداخت فعال نیست.</small>`;
  return `<article class="card acct server-registration rec-order" data-account-rec-order="${esc(order.id)}" data-rec-order-status="${esc(order.status)}">
    <div class="row"><span class="sp"><b>${esc(title)}</b>
      <small class="cap">${esc(order.event_title&&order.event_title!==title?order.event_title+' · ':'')}${order.method==='bale_wallet'?'کیف پول بله':'کارت‌به‌کارت'} · ${recMoney(order.amount,order.currency)}</small></span>${chip(label,tone)}</div>
    <div class="row" style="margin-top:7px;flex-wrap:wrap;gap:6px 12px">${facts.map(f=>`<small class="cap">${f}</small>`).join('')}
      ${order.decision_reason&&(order.status==='rejected'||order.status==='refunded')?`<small class="cap">دلیل: ${esc(order.decision_reason)}</small>`:''}</div>
    ${actions?`<div class="rec-actions" style="margin-top:8px;display:grid;gap:8px">${actions}</div>`:''}
  </article>`;
}
function accountRecordingOrdersContent(){
  const state=SERVER_ACCOUNT_STATE;
  const loading=!state.recOrdersLoaded&&!state.recOrdersError;
  const body=loading?`<div class="empty2"><b>در حال خواندن سفارش‌ها…</b></div>`
    :state.recOrdersError?`<div class="empty2"><b>${esc(state.recOrdersError)}</b><button class="btn quiet" data-account-rec-orders-refresh>تلاش دوباره</button></div>`
    :state.recOrders.length?state.recOrders.map(recOrderCard).join('')
    :empty2('سفارشی برای محتوای ضبط‌شده نداری','خرید دسترسی از فرم خریدِ هر محتوا (از صفحهٔ رویداد) انجام می‌شود و همین‌جا پیگیری می‌شود.','i-play');
  return `<div class="row" style="margin:0 0 8px"><span class="cap">${state.recOrdersLoaded&&!state.recOrdersError?faN(state.recOrdersTotal)+' سفارش محتوای ضبط‌شده':'سفارش‌های محتوای ضبط‌شده'}</span><span class="sp"></span>
    <button class="btn sm quiet" data-account-rec-orders-refresh aria-label="بازخوانی سفارش‌ها">${ico('i-refresh')} بازخوانی</button></div>
    <div class="stack" data-account-rec-orders>${body}</div>
    ${state.recOrdersMore?`<div class="row"><span class="sp"></span><button class="btn quiet" data-account-rec-orders-more>سفارش‌های بیشتر</button></div>`:''}`;
}
function recLibraryCard(item){
  const access=item.access||{}, [label,tone]=REC_ACCESS_STATE[access.state]||['نامشخص',''];
  const active=access.state==='active';
  const meta=[item.event_title&&item.event_title!==item.title?item.event_title:'',
    item.session_count>0?faN(item.session_count)+' جلسه':'', recDuration(item.total_minutes)].filter(Boolean).join(' · ');
  /* «attended»: دسترسی حاصل از حضور ثبت‌شده در خود رویداد (سیاست برگزارکننده)؛ خرید یا اعطا نیست و ردیف دسترسی ندارد. */
  const source={purchase:'خریداری‌شده',free:'دسترسی رایگان',granted:'اعطاشده توسط برگزارکننده',attended:'دسترسی حاضران رویداد'}[access.source]||'';
  const expiry=access.state==='revoked'?(access.revoked_at?'لغو در '+accountServerDate(access.revoked_at):'لغو شده')
    :access.expires_at?(active?'دسترسی تا ':'پایان‌یافته در ')+accountServerDate(access.expires_at):active?'دسترسی دائمی':'';
  /* صفحهٔ محصول برای دارندهٔ دسترسی فعال در «توقف فروش» و «بایگانی» هم باز می‌ماند؛ فقط پیش‌نویس/آماده از دید او بسته است. */
  const unpublished=!!item.status&&!['published','sales_paused','archived'].includes(item.status);
  /* گواهی پایان محتوا: فقط بیان سیاست سرور؛ هیچ دکمهٔ «دریافت گواهی» وجود ندارد چون صدور خودکار وجود ندارد. */
  const cert=item.certificate&&!item.certificate.automatic?(item.certificate.policy==='manual'
    ?'گواهی پایان محتوا: فقط با صدور دستی برگزارکننده؛ خرید یا تماشا به‌تنهایی گواهی نمی‌سازد. گواهی صادرشده در «گواهینامه‌های من» همین صفحه می‌آید'
    :'گواهی پایان محتوا: برای این محتوا صادر نمی‌شود'):'';
  return `<article class="card acct server-registration rec-library" data-account-rec-library="${esc(item.recording_id)}" data-rec-access-state="${esc(access.state||'')}">
    <div class="row"><span class="sp"><b>${esc(item.title||'محتوای ضبط‌شده')}</b>${meta?`<small class="cap">${esc(meta)}</small>`:''}</span>${chip(label,tone)}</div>
    <div class="row" style="margin-top:7px;flex-wrap:wrap;gap:6px 12px">
      ${source?`<small class="cap">${esc(source)}</small>`:''}${expiry?`<small class="cap">${esc(expiry)}</small>`:''}
      ${access.granted_at?`<small class="cap">از ${esc(accountServerDate(access.granted_at))}</small>`:''}</div>
    ${cert?`<small class="cap" data-account-rec-certificate="${esc(item.certificate.policy)}">${esc(cert)}</small>`:''}
    <div class="row" style="margin-top:8px;flex-wrap:wrap;gap:8px">
      ${active&&!unpublished?`<a class="btn sm primary" href="${esc(recEventHref(item,'#recording-sessions'))}" data-account-rec-view>${ico('i-play')} مشاهدهٔ جلسات</a>`
        :active&&unpublished?`<small class="cap">این محتوا فعلاً از سوی برگزارکننده در دسترس نیست.</small>`
        :`<a class="btn sm quiet" href="${esc(recEventHref(item))}">صفحهٔ محصول</a>`}
    </div>
  </article>`;
}
function accountLibraryContent(){
  const state=SERVER_ACCOUNT_STATE;
  const loading=!state.libraryLoaded&&!state.libraryError;
  const body=loading?`<div class="empty2"><b>در حال خواندن محتوای تو…</b></div>`
    :state.libraryError?`<div class="empty2"><b>${esc(state.libraryError)}</b><button class="btn quiet" data-account-library-refresh>تلاش دوباره</button></div>`
    :state.library.length?state.library.map(recLibraryCard).join('')
    :empty2('هنوز به محتوای ضبط‌شده‌ای دسترسی نداری','با خرید یا دریافت رایگان از صفحهٔ هر رویداد برگزارشده، محتوای آن اینجا می‌آید.','i-play');
  const active=state.library.filter(x=>x.access&&x.access.state==='active').length;
  return `<div class="row" style="margin:0 0 8px"><span class="cap">${state.libraryLoaded&&!state.libraryError?faN(active)+' دسترسی فعال از '+faN(state.library.length):'محتوای ضبط‌شدهٔ این حساب'}</span><span class="sp"></span>
    <button class="btn sm quiet" data-account-library-refresh aria-label="بازخوانی محتوای من">${ico('i-refresh')} بازخوانی</button></div>
    <div class="stack" data-account-library>${body}</div>
    <p class="trustline"><svg class="i" aria-hidden="true"><use href="#i-shield"/></svg><span>پیشرفت تماشا هنوز در سرور ثبت نمی‌شود؛ هر بار از فهرست جلسات شروع می‌کنی. مهلت‌ها زمان واقعی سرورند.</span></p>`;
}
/* ── گواهینامه‌های من (فاز ۹.۲) ──
   منبع: GET /api/account/certificates — آینهٔ سرور از گواهی‌هایی که ربات بله واقعاً صادر کرده است.
   «پایان محتوای آموزشی ضبط‌شده» (kind=recording) از گواهی حضور/رویداد جدا نمایش داده می‌شود.
   هیچ دکمهٔ «درخواست/ساخت گواهی» وجود ندارد؛ فایل از ربات بله دریافت می‌شود (همان سیاست فایل‌های خصوصی). */
const ACCT_CERT_KIND={event:'گواهی رویداد / حضور',batch:'گواهی فهرستی',form:'گواهی فرم',manual:'صدور دستی',center:'مرکز صدور',recording:'پایان محتوای آموزشی ضبط‌شده'};
const ACCT_CERT_STATUS={issued:['صادرشده','ok'],revoked:['باطل‌شده','stop'],expired:['منقضی','warn']};
function accountCertificateCard(cert){
  const st=cert.effective_status||cert.status||'issued', [label,tone]=ACCT_CERT_STATUS[st]||['نامشخص',''];
  const kind=ACCT_CERT_KIND[cert.kind]||'گواهینامه', title=cert.title||cert.event_title||kind;
  const code=cert.full_code||cert.serial||'', href=certBotHref();
  const facts=[cert.event_title&&cert.event_title!==title?cert.event_title:'', cert.issued_on?'صدور '+cert.issued_on:(cert.issued_at?'صدور '+accountServerDate(cert.issued_at):''),
    cert.expires_on?'اعتبار تا '+cert.expires_on:'', st==='revoked'&&cert.revoked_at?'ابطال در '+accountServerDate(cert.revoked_at):''].filter(Boolean);
  return `<article class="card acct server-registration acct-cert" data-account-certificate="${esc(cert.id)}" data-cert-kind="${esc(cert.kind||'')}" data-cert-status="${esc(st)}">
    <div class="row"><span class="sp"><b>${esc(title)}</b><small class="cap">${esc(kind)}</small></span>${chip(label,tone)}</div>
    <div class="row" style="margin-top:7px;flex-wrap:wrap;gap:6px 12px">
      ${code?`<small class="cap" dir="ltr">${esc(code)}</small>`:`<small class="cap">شماره در رکورد ثبت نشده</small>`}${facts.map(f=>`<small class="cap">${esc(f)}</small>`).join('')}</div>
    ${cert.kind==='recording'?`<small class="cap">این گواهی حضور در رویداد نیست؛ با تأیید دستی برگزارکننده برای محتوای ضبط‌شده صادر شده است.</small>`:''}
    <div class="row" style="margin-top:8px;flex-wrap:wrap;gap:8px">
      ${st==='issued'?(href?`<a class="btn sm primary" href="${esc(href)}" target="_blank" rel="noopener noreferrer" data-account-cert-bot>${ico('i-send')} دریافت فایل از ربات بله</a>`:`<span class="tag warn">پیوند ربات در دسترس نیست</span>`)
        :`<small class="cap">${st==='revoked'?'این گواهی باطل شده و در استعلام تأیید نمی‌شود.':'مهلت اعتبار این گواهی گذشته است.'}</small>`}
    </div>
  </article>`;
}
function accountCertificatesContent(){
  const state=SERVER_ACCOUNT_STATE;
  const loading=!state.certsLoaded&&!state.certsError;
  const body=loading?`<div class="empty2"><b>در حال خواندن گواهینامه‌ها…</b></div>`
    :state.certsError?`<div class="empty2"><b>${esc(state.certsError)}</b><button class="btn quiet" data-account-certs-refresh>تلاش دوباره</button></div>`
    :state.certificates.length?state.certificates.map(accountCertificateCard).join('')
    :empty2('هنوز گواهینامه‌ای در حساب ثبت نشده','گواهی فقط پس از صدور واقعی توسط برگزارکننده در ربات بله اینجا دیده می‌شود؛ خرید یا تماشای محتوا به‌تنهایی گواهی نمی‌سازد.','i-medal');
  const c=state.certsCounts||{};
  const summary=state.certsLoaded&&!state.certsError?[faN(c.issued||0)+' معتبر',c.revoked?faN(c.revoked)+' باطل‌شده':'',c.expired?faN(c.expired)+' منقضی':''].filter(Boolean).join(' · '):'';
  return `<div class="row" style="margin:14px 0 8px"><span class="sp"><b>${ico('i-medal')} گواهینامه‌های من</b>${summary?`<small class="cap">${esc(summary)}</small>`:''}</span>
    <button class="btn sm quiet" data-account-certs-refresh aria-label="بازخوانی گواهینامه‌ها">${ico('i-refresh')} بازخوانی</button></div>
    <div class="stack" data-account-certificates>${body}</div>`;
}
async function loadAccountCertificates(force=false){
  const state=SERVER_ACCOUNT_STATE, api=window.NORA_SERVER_API;
  if(!state.account||state.certsLoading||(!force&&state.certsLoaded)) return;
  state.certsLoading=true; state.certsError='';
  if(S.view==='library') renderView();
  try{
    if(!api||typeof api.getAccountCertificates!=='function') throw new Error('account_api_unavailable');
    const result=await api.getAccountCertificates();
    if(!state.account) return;
    const items=Array.isArray(result&&result.items)?result.items:[];
    if(items.some(item=>!item||typeof item.id!=='string'||typeof item.kind!=='string'||typeof item.effective_status!=='string'))
      throw new Error('invalid_account_certificates');
    state.certificates=items; state.certsCounts=result&&result.counts&&typeof result.counts==='object'?result.counts:null; state.certsLoaded=true;
  }catch(error){
    if(error&&error.status===401){accountLoadError(error,'');return}
    state.certsError=accountLoadError(error,'گواهینامه‌ها خوانده نشدند؛ دوباره تلاش کن.'); state.certsLoaded=true;
  }finally{
    state.certsLoading=false;
    if(S.view==='library') renderView();
  }
}
function serverAccountLibraryView(t){
  const state=SERVER_ACCOUNT_STATE;
  let content;
  if(state.checking) content=empty2('در حال بررسی حساب','وضعیت ورود از سرور بررسی می‌شود.','i-shield');
  else if(!state.account) content=serverAccountAccessCard('library');
  else content=accountLibraryContent()+accountCertificatesContent();
  return viewHead(t,state.account?'محتوای ضبط‌شدهٔ تو':'نیاز به ورود',null)+(state.account?serverAccountStrip():'')+`<div class="panel stack">${content}</div>`;
}
async function loadAccountLibrary(force=false){
  const state=SERVER_ACCOUNT_STATE, api=window.NORA_SERVER_API;
  if(!state.account||state.libraryLoading||(!force&&state.libraryLoaded)) return;
  state.libraryLoading=true; state.libraryError='';
  if(S.view==='library') renderView();
  try{
    if(!api||typeof api.getAccountRecordings!=='function') throw new Error('account_api_unavailable');
    const result=await api.getAccountRecordings();
    if(!state.account) return;
    const items=Array.isArray(result&&result.items)?result.items:[];
    if(items.some(item=>!item||typeof item.recording_id!=='string'||typeof item.event_id!=='string'||!item.access||typeof item.access.state!=='string'))
      throw new Error('invalid_account_library');
    state.library=items; state.libraryLoaded=true;
  }catch(error){
    if(error&&error.status===401){accountLoadError(error,'');return}
    state.libraryError=accountLoadError(error,'محتوای تو خوانده نشد؛ دوباره تلاش کن.'); state.libraryLoaded=true;
  }finally{
    state.libraryLoading=false;
    if(S.view==='library'||S.view==='events') renderView();
    if(!TEST_FIXTURE_MODE) renderProfile();
  }
}
async function loadAccountRecordingOrders(append=false,force=false){
  const state=SERVER_ACCOUNT_STATE, api=window.NORA_SERVER_API;
  if(!state.account||state.recOrdersLoading||(!force&&!append&&state.recOrdersLoaded)) return;
  state.recOrdersLoading=true; state.recOrdersError='';
  if(!append){state.recOrders=[];state.recOrdersTotal=0;state.recOrdersMore=false;state.recOrdersLoaded=false;}
  if(S.view==='payments') renderView();
  try{
    if(!api||typeof api.getAccountRecordingOrders!=='function') throw new Error('account_api_unavailable');
    const result=await api.getAccountRecordingOrders(SERVER_ACCOUNT_PAGE,append?state.recOrders.length:0);
    if(!state.account) return;
    const items=Array.isArray(result&&result.items)?result.items:[];
    if(items.some(item=>!item||typeof item.id!=='string'||typeof item.status!=='string'||typeof item.recording_id!=='string'))
      throw new Error('invalid_account_recording_orders');
    state.recOrders=append?state.recOrders.concat(items):items;
    state.recOrdersTotal=Number.isFinite(+result.total)?Math.max(0,+result.total):state.recOrders.length;
    state.recOrdersMore=state.recOrders.length<state.recOrdersTotal; state.recOrdersLoaded=true;
  }catch(error){
    if(error&&error.status===401){accountLoadError(error,'');return}
    state.recOrdersError=accountLoadError(error,'سفارش‌های محتوای ضبط‌شده خوانده نشدند؛ دوباره تلاش کن.'); state.recOrdersLoaded=true;
  }finally{
    state.recOrdersLoading=false;
    if(S.view==='payments') renderView();
    if(!TEST_FIXTURE_MODE) renderProfile();
  }
}
function recReplaceOrder(order){
  const state=SERVER_ACCOUNT_STATE, i=state.recOrders.findIndex(x=>x.id===order.id);
  if(i>-1) state.recOrders[i]=Object.assign({},state.recOrders[i],order); else state.recOrders.unshift(order);
}
async function cancelAccountRecordingOrder(id){
  const state=SERVER_ACCOUNT_STATE, api=window.NORA_SERVER_API;
  if(!api||typeof api.cancelAccountRecordingOrder!=='function'){toast('رابط حساب سرور در دسترس نیست');return}
  if(state.recOrderBusy) return;
  if(!window.confirm('از این سفارش انصراف می‌دهی؟ اگر مبلغی واریز کرده‌ای، انصراف نده و با برگزارکننده تماس بگیر.')) return;
  state.recOrderBusy=id; renderView();
  try{ const order=await api.cancelAccountRecordingOrder(id); if(order&&order.id) recReplaceOrder(order); toast('سفارش لغو شد.'); }
  catch(error){ toast(error&&error.status===409?'این سفارش دیگر قابل انصراف نیست؛ فهرست بازخوانی می‌شود.':accountLoadError(error,'انصراف انجام نشد؛ دوباره تلاش کن.')); if(error&&error.status===409) loadAccountRecordingOrders(false,true); }
  finally{ state.recOrderBusy=''; renderView(); }
}
function serverAccountRegistrationsView(t,mode){
  const state=SERVER_ACCOUNT_STATE;
  let content;
  if(state.checking) content=empty2('در حال بررسی حساب','وضعیت ورود از سرور بررسی می‌شود.','i-shield');
  else if(!state.account) content=serverAccountAccessCard(mode||'events');
  else content=accountRegistrationsContent(mode);
  return viewHead(t,state.account?(mode==='payments'?'سفارش‌ها و پرداخت‌های تو':mode==='forms'?'فرم‌های تو':'ثبت‌نام‌های تو'):'نیاز به ورود',null)+
    (state.account?serverAccountStrip():'')+`<div class="panel stack">${content}</div>`;
}
function serverAccountDataView(t){
  t=t||SERVER_DATA_VIEW;
  const tabs=[{k:'notifications',n:'اعلان‌ها',i:'i-bell'},{k:'files',n:'فایل‌ها',i:'i-archive'}];
  let content;
  if(SERVER_ACCOUNT_STATE.checking) content=empty2('در حال بررسی حساب','وضعیت ورود از سرور بررسی می‌شود.','i-shield');
  else if(SERVER_ACCOUNT_STATE.error) content=empty2('اطلاعات حساب در دسترس نیست',SERVER_ACCOUNT_STATE.error,'i-refresh')+
    `<button class="btn quiet" data-server-account-retry>${ico('i-refresh')} تلاش دوباره</button>`;
  else if(!SERVER_ACCOUNT_STATE.account) content=TEST_FIXTURE_MODE?`<div class="card acct gate">
    <div class="head">برای دسترسی به داده‌های خودت وارد شو</div><p class="cap">اعلان‌ها و فایل‌ها فقط پس از تأیید ورود از مسیر سرور دریافت می‌شوند.</p>
    <a class="btn primary" href="login.html?mode=server&next=account.html%23notifications">${ico('i-mobile')} ورود/ثبت‌نام</a></div>`
    :serverAccountAccessCard()+serverAccountModulesCard();
  else content=S.serverdata==='files'?accountFilesContent():accountNotificationsContent();
  return viewHead(t,'اعلان‌ها و فایل‌های خصوصی حساب',tabs,'serverdata')+`<div class="panel stack">${content}</div>`;
}
function updateAccountBanner(){
  /* نوار هشدار تکراری از رابط حساب برداشته شده است؛ کنترل نشست سرور فعال می‌ماند. */
}
function resetServerAccountData(){
  const state=SERVER_ACCOUNT_STATE;
  state.registrations=[]; state.registrationsTotal=0; state.registrationsLoaded=false;
  state.registrationsLoading=false; state.registrationsError=''; state.registrationsMore=false;
  state.notifications=[]; state.notificationsLoaded=false; state.notificationsLoading=false;
  state.notificationsError=''; state.notificationsMore=false;
  state.files=[]; state.filesLoaded=false; state.filesLoading=false; state.filesError=''; state.filesMore=false;
  state.library=[]; state.libraryLoaded=false; state.libraryLoading=false; state.libraryError='';
  state.certificates=[]; state.certsCounts=null; state.certsLoaded=false; state.certsLoading=false; state.certsError='';
  state.recOrders=[]; state.recOrdersTotal=0; state.recOrdersLoaded=false; state.recOrdersLoading=false; state.recOrdersError=''; state.recOrdersMore=false; state.recOrderBusy='';
  /* وضعیت پیوند هم به همین حساب گره خورده است؛ در خروج/انقضا پاک می‌شود تا
     اطلاعات حساب قبلی روی صفحه نماند. */
  IDENTITY_STATE.list=null; IDENTITY_STATE.loaded=false; IDENTITY_STATE.loading=false;
  IDENTITY_STATE.error=''; IDENTITY_STATE.busy=''; IDENTITY_STATE.confirmUnlink=false; IDENTITY_STATE.outcome=null;
}
function serverAccountExpired(){
  const state=SERVER_ACCOUNT_STATE;
  delete window.NORA_ACCOUNT_SOURCE;
  window.NORA_UI?.updateAccountNavigation?.();
  state.account=null; state.checking=false; state.checked=true; state.error=''; resetServerAccountData();
  if(UI().clearProfileCache) UI().clearProfileCache();
  updateAccountBanner(); render(); toast('ورود حساب پایان یافته؛ برای دسترسی به اطلاعاتت دوباره وارد شو.');
}
function accountLoadError(error,fallback){
  if(error&&error.status===401){serverAccountExpired(); return 'ورود حساب پایان یافته؛ دوباره وارد شو.'}
  if(error&&error.status===0) return 'سرور در دسترس نیست؛ اتصال را بررسی کن.';
  return fallback;
}
async function loadAccountRegistrations(append=false,force=false){
  const state=SERVER_ACCOUNT_STATE, api=window.NORA_SERVER_API;
  if(!state.account||state.registrationsLoading||(!force&&!append&&state.registrationsLoaded)) return;
  state.registrationsLoading=true; state.registrationsError='';
  if(!append){state.registrations=[];state.registrationsTotal=0;state.registrationsMore=false;}
  if(S.view==='events'||ACCOUNT_REGISTRATION_VIEWS[S.view]) renderView();
  try{
    if(!api||typeof api.getAccountRegistrations!=='function') throw new Error('account_api_unavailable');
    const result=await api.getAccountRegistrations(SERVER_ACCOUNT_PAGE,append?state.registrations.length:0);
    if(!state.account) return;
    const items=Array.isArray(result&&result.items)?result.items:[];
    if(items.some(item=>!item||typeof item.id!=='string'||typeof item.form_name!=='string'
      ||typeof item.event_title!=='string'||!['accepted','waitlisted'].includes(item.status)
      ||typeof item.created_at!=='string')) throw new Error('invalid_account_registrations');
    state.registrations=append?state.registrations.concat(items):items;
    state.registrationsTotal=Number.isFinite(+result.total)?Math.max(0,+result.total):state.registrations.length;
    state.registrationsMore=!!result.has_more; state.registrationsLoaded=true;
  }catch(error){
    if(error&&error.status===401){accountLoadError(error,'');return}
    state.registrationsError=accountLoadError(error,'ثبت‌نام‌ها خوانده نشدند؛ دوباره تلاش کن.');
    state.registrationsLoaded=true;
  }finally{
    state.registrationsLoading=false;
    if(S.view==='events'||ACCOUNT_REGISTRATION_VIEWS[S.view]) renderView();
    if(!TEST_FIXTURE_MODE) renderProfile();
  }
}
async function loadAccountNotifications(append=false,force=false){
  const state=SERVER_ACCOUNT_STATE, api=window.NORA_SERVER_API;
  if(!state.account||state.notificationsLoading||(!force&&state.notificationsLoaded&&!append)) return;
  state.notificationsLoading=true; state.notificationsError='';
  if(!append&&!force) state.notifications=[];
  if(S.view==='server-data') renderView();
  try{
    if(!api||typeof api.getAccountNotifications!=='function') throw new Error('account_api_unavailable');
    const result=await api.getAccountNotifications(SERVER_ACCOUNT_PAGE,append?state.notifications.length:0);
    if(!state.account) return;
    const items=Array.isArray(result&&result.items)?result.items:[];
    if(items.some(item=>!item||typeof item.id!=='string'||typeof item.title!=='string'||!Array.isArray(item.file_refs)))
      throw new Error('invalid_account_notifications');
    state.notifications=append?state.notifications.concat(items):items;
    state.notificationsMore=!!result.has_more; state.notificationsLoaded=true;
  }catch(error){
    if(error&&error.status===401){accountLoadError(error,'');return}
    state.notificationsError=accountLoadError(error,'اعلان‌ها خوانده نشدند؛ دوباره تلاش کن.');
    state.notificationsLoaded=true;
  }finally{
    state.notificationsLoading=false;
    if(S.view==='server-data') renderView();
    renderProfile();
  }
}
async function loadAccountFiles(append=false,force=false){
  const state=SERVER_ACCOUNT_STATE, api=window.NORA_SERVER_API;
  if(!state.account||state.filesLoading||(!force&&state.filesLoaded&&!append)) return;
  state.filesLoading=true; state.filesError='';
  if(!append&&!force) state.files=[];
  if(S.view==='server-data') renderView();
  try{
    if(!api||typeof api.getAccountFiles!=='function') throw new Error('account_api_unavailable');
    const result=await api.getAccountFiles(SERVER_ACCOUNT_PAGE,append?state.files.length:0);
    if(!state.account) return;
    const items=Array.isArray(result&&result.items)?result.items:[];
    if(items.some(file=>!file||typeof file.id!=='string'||typeof file.file_name!=='string'
      ||typeof file.content_type!=='string'||!Number.isFinite(+file.content_size))) throw new Error('invalid_account_files');
    state.files=append?state.files.concat(items):items;
    state.filesMore=!!result.has_more; state.filesLoaded=true;
  }catch(error){
    if(error&&error.status===401){accountLoadError(error,'');return}
    state.filesError=accountLoadError(error,'فایل‌ها خوانده نشدند؛ دوباره تلاش کن.');
    state.filesLoaded=true;
  }finally{
    state.filesLoading=false;
    if(S.view==='server-data') renderView();
    renderProfile();
  }
}
/* هویت‌های همین حساب را از سرور می‌خواند. سرور مرجع است؛ هیچ‌جا از روی
   ورود فعلی «حدس» نمی‌زنیم که کاربر بله وصل است یا نه. */
async function loadAccountIdentities(force=false){
  const state=IDENTITY_STATE, api=window.NORA_SERVER_API;
  if(!SERVER_ACCOUNT_STATE.account) return;
  if(state.loading||(!force&&state.loaded)) return;
  state.loading=true; state.error=''; renderProfile();
  try{
    if(!api||typeof api.getAccountIdentities!=='function') throw new Error('account_api_unavailable');
    const result=await api.getAccountIdentities();
    if(!SERVER_ACCOUNT_STATE.account) return;
    const rows=Array.isArray(result&&result.identities)?result.identities:[];
    if(rows.some(row=>!row||!['phone','bale'].includes(row.provider)
      ||(row.linked_at!=null&&typeof row.linked_at!=='string'))) throw new Error('invalid_account_identities');
    state.list={providers:rows.map(row=>row.provider),rows,
      available:Array.isArray(result.available_providers)?result.available_providers:[],
      baleAvailable:result.bale_link_available===true};
    state.loaded=true;
  }catch(error){
    if(error&&error.status===401){accountLoadError(error,'');return}
    state.error=accountLoadError(error,'وضعیت پیوند حساب خوانده نشد؛ دوباره تلاش کن.');
    state.loaded=true;
  }finally{
    state.loading=false;
    renderProfile();
  }
}
function loadServerAccountData(force=false){
  if(!SERVER_ACCOUNT_STATE.account) return;
  loadAccountNotifications(false,force); loadAccountFiles(false,force); loadAccountIdentities(force);
  loadAccountRegistrations(false,force);
}
async function checkServerAccount(){
  const state=SERVER_ACCOUNT_STATE, api=window.NORA_SERVER_API;
  state.checking=true; state.error=''; updateAccountBanner(); renderProfile();
  try{
    if(!api||typeof api.accountMe!=='function') throw new Error('account_api_unavailable');
    const identity=await api.accountMe();
    if(!identity||identity.authenticated!==true||!['bale','phone','manager-password'].includes(identity.provider)||typeof identity.account_id!=='string')
      throw new Error('invalid_account_session');
    if(typeof identity.delivery_bot_url==='string'&&/^https:\/\/ble[.]ir\/[A-Za-z0-9_]{3,64}$/i.test(identity.delivery_bot_url)){
      N.BALE_BOT_URL=identity.delivery_bot_url;
      /* فاز ۹.۲ — در حالت سرور data.js بارگذاری نمی‌شود و window.NORA وجود ندارد؛ ui.baleStartHref این
         مقدار را به‌عنوان جایگزین می‌خواند تا پیوند دریافت از ربات (فایل خصوصی/گواهی) واقعاً ساخته شود. */
      window.NORA_PUBLIC_BALE_BOT_URL=identity.delivery_bot_url;
    }
    window.NORA_ACCOUNT_SOURCE='server';
    state.account=identity; state.checked=true; state.checking=false; state.error='';
    window.NORA_UI?.updateAccountNavigation?.();
    resetServerAccountData(); updateAccountBanner(); render(); loadServerAccountData(false);
    if(window.NORA_UI&&window.NORA_UI.syncServerProfile) window.NORA_UI.syncServerProfile().then(()=>{ if(window.NORA_ACCOUNT_SOURCE==='server') render() });
    if(S.view==='events'||ACCOUNT_REGISTRATION_VIEWS[S.view]) loadAccountRegistrations();
    if(S.view==='events'&&!TEST_FIXTURE_MODE) loadAccountLibrary();
    if(S.view==='payments'&&!TEST_FIXTURE_MODE) loadAccountRecordingOrders();
    if(S.view==='library'){loadAccountLibrary();loadAccountCertificates();}
  }catch(error){
    delete window.NORA_ACCOUNT_SOURCE;
    window.NORA_UI?.updateAccountNavigation?.();
    state.account=null; state.checked=true; state.checking=false;
    state.error=error&&error.status===401?'':'اتصال به حساب برقرار نشد؛ دوباره تلاش کن.';
    updateAccountBanner(); render();
  }
}
async function logoutServerAccount(button){
  const api=window.NORA_SERVER_API;
  if(!SERVER_ACCOUNT_STATE.account||!api||typeof api.accountLogout!=='function') return;
  if(button) button.disabled=true;
  try{
    await api.accountLogout();
    delete window.NORA_ACCOUNT_SOURCE;
    window.NORA_UI?.updateAccountNavigation?.();
    SERVER_ACCOUNT_STATE.account=null; SERVER_ACCOUNT_STATE.checked=true; SERVER_ACCOUNT_STATE.checking=false;
    SERVER_ACCOUNT_STATE.error=''; resetServerAccountData();
    if(UI().clearProfileCache) UI().clearProfileCache();
    updateAccountBanner(); render();
    toast('از حساب خارج شدی.');
  }catch(error){
    if(button) button.disabled=false;
    if(error&&error.status===401){serverAccountExpired();return}
    toast(error&&error.status===403?'ورود امن پیدا نشد؛ صفحه را تازه کن.':'خروج انجام نشد؛ اتصال را بررسی کن.');
  }
}
const gate=t=>`<div class="card acct gate">${ico('i-lock')}
  <div class="head">این بخش با حساب خودت باز می‌شود</div>
  <div class="cap">«${esc(t.n)}» در این نمونه با کد ثابت محلی باز می‌شود؛ شماره یا هویت در سرور بررسی نمی‌شود.</div>
  <div class="gacts"><button class="btn primary" data-login>${ico('i-mobile')} ورود آزمایشی با شمارهٔ موبایل</button>
    <button class="btn quiet" data-go="support">پشتیبانی، بدون ورود</button></div></div>`;

/* ══ رویدادهای من ═══════════════════════════════════════════════════ */
const VTABS=[{k:'up',n:'پیش‌رو'},{k:'past',n:'برگزارشده'},{k:'notes',n:'نظر و نظرسنجی'}];

/* ══ باشگاه و امتیاز من ═════════════════════════════════════════════ */
/* ══ رویدادهای من: کارت‌های شخصی و جزئیات داخل خودشان ══════════════
   این‌جا فهرست همهٔ رویدادها نیست؛ فقط رویدادهای خودِ کاربر است و جزئیات،
   گواهی صادرشده، پیوندهای رسانه، کارنامهٔ حضور و نظر هر مورد یک‌جا می‌آیند. */
function myInfo(id){ return MY_INFO[id]||{} }
function splitInstallments(amount){
  const total=Math.max(0,Math.round(Number(amount)||0)),first=Math.ceil(total/2);
  return {total,first,second:total-first};
}
function installmentForEvent(id){
  const raw=myInfo(id).payment;
  if(!raw||typeof raw!=='object')return null;
  const amounts=splitInstallments(raw.total);
  if(!amounts.total)return null;
  return Object.assign({},amounts,{firstPaid:raw.firstPaid===true,secondPaid:raw.secondPaid===true,
    dueLabel:String(raw.dueLabel||'تا پنجم ماه آینده')});
}
function pendingFirstInstallments(){
  return myUp().map(event=>({event,payment:installmentForEvent(event.id)}))
    .filter(row=>row.payment&&!row.payment.firstPaid);
}
function outstandingInstallments(){
  return myUp().map(event=>({event,payment:installmentForEvent(event.id)}))
    .filter(row=>row.payment&&(!row.payment.firstPaid||!row.payment.secondPaid));
}
const EVENT_PACK_KEY='nora-evpack';
const certDigits=v=>unFa(String(v||'')).replace(/\D/g,'').slice(-10);
const cleanEventText=v=>String(v||'').normalize?String(v||'').normalize('NFKC').toLowerCase()
  .replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/[\u064b-\u065f]/g,'')
  .replace(/[\u200c\s]+/g,' ').replace(/[^\u0600-\u06ffa-z0-9 ]/gi,'').trim()
  :String(v||'').toLowerCase().replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/[\u200c\s]+/g,' ').trim();
function eventRecord(id){
  return EVENTS.find(x=>String(x.id)===String(id))||PAST.find(x=>String(x.id)===String(id))||
    (UI().pubEvents?UI().pubEvents().find(x=>String(x.id)===String(id)):null)||{};
}
function eventPack(id){
  try{const all=JSON.parse(localStorage.getItem(EVENT_PACK_KEY)||'{}');
    return all&&typeof all==='object'&&!Array.isArray(all)?(all[String(id)]||{}):{}
  }catch(e){return {}}
}
function safeEventHref(raw){
  try{return UI().safeHttpsMediaUrl?UI().safeHttpsMediaUrl(raw):(/^https:\/\//i.test(String(raw||''))?String(raw).trim():'')}
  catch(e){return ''}
}
function isOnlineEvent(e,inf){
  const text=cleanEventText([e&&e.mode,e&&e.place,e&&e.kind,inf&&inf.kind].filter(Boolean).join(' '));
  return /آنلاین|مجازی|وبینار|webinar/.test(text);
}
function isJoinLink(row){
  const label=cleanEventText([row&&row.n,row&&row.t,row&&row.title,row&&row.role,row&&row.purpose].filter(Boolean).join(' '));
  return /پیوند ورود|لینک ورود|ورود آنلاین|جلسه آنلاین|join|meeting/.test(label);
}
function eventJoinUrl(e,inf){
  const pack=eventPack(e&&e.id), candidates=[inf&&inf.joinUrl,inf&&inf.meetingUrl,inf&&inf.link,e&&e.joinUrl,e&&e.meetingUrl,pack.joinUrl,pack.meetingUrl];
  for(const value of candidates){const href=safeEventHref(value);if(href)return href}
  const links=[].concat(pack.files||[],Array.isArray(inf&&inf.links)?inf.links:[]);
  const item=links.find(x=>x&&isJoinLink(x));
  return item?safeEventHref(item.url||item.href||item.src):'';
}
function mediaKindOf(row){
  const raw=String(row&&((row.k)||(row.kind))||'').toLowerCase(), label=cleanEventText(row&&((row.k)||(row.kind)||(row.n)||(row.t)||'')),
    mime=String(row&&row.mime||'').toLowerCase(), name=String(row&&((row.n)||(row.t))||'').toLowerCase();
  if(['video','audio','image','pdf','slide'].includes(raw)) return raw;
  const url=String(row&&((row.url)||(row.src))||'');
  if(raw==='link'&&((UI().videoEmbedInfo&&UI().videoEmbedInfo(url))||/\.(mp4|m4v|webm|ogv|mov)(?:[?#].*)?$/i.test(url))) return 'video';
  if(/وید|فیلم|video/.test(label)||mime.startsWith('video/')||/\.(mp4|m4v|webm|ogv|mov)(?:[?#].*)?$/i.test(name)) return 'video';
  if(/صدا|صوت|audio/.test(label)||mime.startsWith('audio/')||/\.(mp3|m4a|wav|ogg|aac|flac)(?:[?#].*)?$/.test(name)) return 'audio';
  if(/عکس|تصویر|image/.test(label)||mime.startsWith('image/')) return 'image';
  if(/pdf/.test(label)||mime==='application/pdf'||/\.pdf(?:[?#].*)?$/.test(name)) return 'pdf';
  if(/اسلاید|slide/.test(label)) return 'slide';
  if(/پیوند|لینک|link/.test(label)||row&&row.url) return 'link';
  return 'file';
}
function accountMediaItem(raw,index,eventId,fromPack){
  const item=Array.isArray(raw)?{k:raw[0],t:raw[1],d:raw[2],mediaId:raw[3],url:raw[4],sourceDemo:raw[5]}:
    (raw&&typeof raw==='object'?raw:{});
  const ref=String(item.mediaId||item.ref||''), base=ref&&PAST.find(x=>String(x.id)===String(eventId)),
    linked=base&&(base.media||[]).find(x=>String(x.id)===ref)||{};
  const k=mediaKindOf(Object.assign({},linked,item));
  const url=String(item.url||item.href||linked.url||''), src=String(item.src||linked.src||'');
  const size=+item.size||+linked.size||0;
  return Object.assign({},linked,item,{id:String(item.id||ref||('event-'+String(eventId)+'-'+index)),k:k,
    t:String(item.t||item.n||linked.t||'رسانهٔ رویداد'),d:String(item.d||item.duration||linked.d||item.at||''),
    s:String(item.s||linked.s||(size?faN(Math.ceil(size/1024))+' کیلوبایت':'')),size:size,
    mime:String(item.mime||linked.mime||''),url:url,src:src,external:!!(item.external||url),
    p:0,preview:true,sourceDemo:!!item.sourceDemo,heavy:item.heavy?1:0,
    chapters:Array.isArray(item.chapters)?item.chapters:(Array.isArray(linked.chapters)?linked.chapters:[]),
    _fromPack:!!fromPack});
}
function eventMediaRows(id){
  const inf=myInfo(id), pack=eventPack(id), stored=Array.isArray(pack.files)?pack.files:[], e=eventRecord(id);
  const joinHref=isOnlineEvent(e,inf)?eventJoinUrl(e,inf):'';
  if(stored.length){
    const files=stored.filter(x=>!(joinHref&&safeEventHref(x.url||x.href||x.src)===joinHref));
    return files.map((x,i)=>accountMediaItem(x,i,id,true));
  }
  const base=(Array.isArray(inf.off)?inf.off:[]).map((x,i)=>accountMediaItem(x,i,id,false));
  const links=(Array.isArray(inf.links)?inf.links:[]).filter(x=>!(joinHref&&safeEventHref(x.url||x.href||x.src)===joinHref))
    .map((x,i)=>accountMediaItem(Object.assign({k:'link'},typeof x==='string'?{t:x,url:x}:x),base.length+i,id,false));
  return base.concat(links);
}
function accountMediaHasSource(item){
  if(!item)return false;
  if(safeEventHref(item.url)||safeEventHref(item.src))return true;
  const raw=String(item.src||'');
  return /^data:(?:image\/(?:png|jpe?g|gif|webp|avif)|audio\/[\w.+-]+|video\/[\w.+-]+|application\/(?:pdf|zip|x-zip-compressed|octet-stream|msword|vnd\.ms-(?:excel|powerpoint)|vnd\.openxmlformats-officedocument\.[\w.+-]+)|text\/(?:plain|csv));base64,/i.test(raw);
}
function accountMediaIcon(kind){return ({pdf:'i-doc',slide:'i-layers',audio:'i-headphone',video:'i-play',image:'i-image',link:'i-link',file:'i-doc'})[kind]||'i-archive'}
function issuedCerts(){try{return UI().issuedCertificates?UI().issuedCertificates():[]}catch(e){return []}}
function certBelongsToCurrentUser(c){
  if(!c)return false;
  const u=sess()||{}, p=prof()||{}, ids=[uid(),u.userId,u.personId,p.userId,p.personId,p.id].map(x=>String(x||'').trim()).filter(Boolean),
    certIds=[c.userId,c.personId,c.recipientId,c.memberId,c.accountId,c.user&&c.user.id,c.recipient&&c.recipient.userId,c.recipient&&c.recipient.personId].map(x=>String(x||'').trim()).filter(Boolean);
  if(ids.some(x=>certIds.includes(x)))return true;
  const phones=[phone(),u.mobile,u.phone,p.mobile,p.phone].map(certDigits).filter(Boolean),
    certPhones=[c.mobile,c.phone,c.ph,c.recipientMobile,c.recipient&&c.recipient.mobile,c.user&&c.user.mobile].map(certDigits).filter(Boolean);
  if(phones.some(x=>certPhones.includes(x)))return true;
  const names=[p.fullName,u.name,p.name].map(cleanEventText).filter(Boolean),
    certNames=[c.name,c.n,c.recipientName,c.personName,c.recipient&&c.recipient.name,c.user&&c.user.name].map(cleanEventText).filter(Boolean);
  return names.some(x=>certNames.includes(x));
}
function certMatchesEvent(c,id,e){
  if(!c)return false;
  const refValue=v=>v&&typeof v==='object'?(v.id||v.k||v.code||''):v,
    refs=['eventId','event_id','ev','courseId','course_id','formId','form_id','sourceEventId','purchaseEventId']
      .map(k=>String(refValue(c[k])||'').trim()).filter(Boolean);
  if(refs.some(x=>x===String(id)))return true;
  const eventNames=[e&&e.t,e&&e.title,e&&e.n,e&&e.eventTitle].map(cleanEventText).filter(Boolean),
    certNames=[c.eventTitle,c.courseTitle,c.programTitle,c.eventName,c.event,c.course,c.title,c.event_title]
      .map(v=>cleanEventText(typeof v==='object'?(v.title||v.t||v.n||''):v)).filter(Boolean);
  return eventNames.some(x=>x.length>=4&&certNames.includes(x));
}
function issuedForEventList(id){
  const e=eventRecord(id);
  return issuedCerts().filter(c=>c&&c.state==='issued'&&certBelongsToCurrentUser(c)&&certMatchesEvent(c,id,e))
    .sort((a,b)=>(+b.createdAt||+b.approvedAt||0)-(+a.createdAt||+a.approvedAt||0));
}
function issuedForEvent(id){return issuedForEventList(id)[0]||null}
/* `cert_<serial>` در سورس بات فقط استعلام است؛ دریافت فایل از «گواهینامه‌های من» انجام می‌شود. */
function certBotHref(){
  return accountBotDeliveryHref('mycerts');
}
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
  const inf=myInfo(id), e=eventRecord(id), st=noteState(id), chips=[], issued=issuedForEventList(id), requested=certReqOf(id), media=eventMediaRows(id);
  if(isOnlineEvent(e,inf)) chips.push(chip(eventJoinUrl(e,inf)?'آنلاین · پیوند ورود':'آنلاین','brand'));
  if(issued.length) chips.push(chip(faN(issued.length)+' گواهی صادرشده','ok'));
  else if(requested) chips.push(chip('گواهی · در انتظار صدور','warn'));
  else chips.push(chip(past?'گواهی هنوز صادر نشده':'گواهی پس از رویداد','warn'));
  const recordings=media.filter(x=>x.k==='video').length;
  if(recordings) chips.push(chip(faN(recordings)+' ضبط'));
  else if(media.length) chips.push(chip(faN(media.length)+' فایل و پیوند'));
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
      <span class="ec-go">${ico('i-chev-left')} ${esc((MY.sheet||{}).open||'جزئیات رویداد')}
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
  return notesBar()+card('پیش‌روی من',faN(mine.length)+' رویداد ثبت‌نام‌شده، '+esc(MY.lead||''),'i-calendar',
    cardsBox(mine)+`<p class="cap" style="margin:10px 3px 0">${esc(MY.inEvent||'')}</p>`)+
    trustLine('secure');
}
function panelPast(){
  const mine=myPast().map(e=>({e,past:true}));
  if(!mine.length) return card('برگزارشده‌ها','',empty2('هنوز رویداد برگزارشده‌ای نداری','بعد از هر رویداد، ضبط و گواهی همین‌جا می‌آید.'));
  return notesBar()+card('برگزارشده‌های من',faN(mine.length)+' رویداد؛ گواهی، ضبط، فایل‌ها و حضور','i-archive',
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
          <button class="btn sm quiet" data-myev="${esc(e.id)}">جزئیات رویداد</button></span></span></div>`;
  };
  return card('نظر و نظرسنجی','نظر و نظرسنجی‌ات مالِ خودِ همان رویداد است؛ همین‌جا می‌بینی و می‌نویسی','i-star',
    (pend.length?`<div class="gt cap" style="margin:2px 3px 8px">منتظر نظر تو</div>`+pend.map(askRow).join(''):'')+
    (given.length?`<div class="gt cap" style="margin:14px 3px 8px">نظرها و نظرسنجی‌های تو</div>`+given.map(givenRow).join(''):'')+
    (!pend.length&&!given.length?empty2('چیزی نمانده','هر رویدادی که بگذرد، نظر و نظرسنجی‌اش همین‌جا می‌آید.'):''))+
    trustLine('privacy');
}
/* ── ورقهٔ رویداد من: جزئیات، گواهی، آرشیو، حضور و نظر ── */
function offRow(item,id,index){
  const kind=item.k||'file', label={pdf:'PDF',audio:'صدا',video:'ویدیو',image:'عکس',slide:'اسلاید',link:'پیوند',file:'فایل'}[kind]||'رسانه',
    ready=accountMediaHasSource(item), href=safeEventHref(item.url||item.href||item.src||''), duration=item.d||item.s||'',
    meta=[label,duration,item.sourceDemo?'منبع آزمایشی':''].filter(Boolean).join(' · '), title=String(item.t||item.n||'رسانهٔ رویداد'),
    needsBot=['image','pdf','slide','file'].includes(kind)||String(item.mime||'').startsWith('application/'),
    receiveHref=needsBot&&item.available===true&&item.delivery_id?accountBotDeliveryHref('file_'+item.delivery_id):'';
  let action='';
  if(needsBot)
    action=receiveHref?`<a class="btn sm primary" href="${esc(receiveHref)}" target="_blank" rel="noopener noreferrer">${ico('i-send')} دریافت در بات بله</a>`
      :`<span class="tag warn">دریافت از بات منتشر نشده</span>`;
  else if(ready&&['video','audio'].includes(kind))
    action=`<button class="btn sm primary" type="button" data-my-media-event="${esc(id)}" data-my-media-id="${esc(item.id)}" aria-label="پخش ${esc(title)}">${ico(kind==='video'?'i-play':'i-headphone')} پخش</button>`;
  else if(ready&&href&&kind==='link')
    action=`<a class="btn sm quiet" href="${esc(href)}" target="_blank" rel="noopener noreferrer">${ico('i-link')} بازکردن امن</a>`;
  else action=`<span class="tag warn">${item.heavy?'پیوند پخش لازم است':ready?'پیش‌نمایش این نوع فایل در پلیر موجود نیست':'پیوند هنوز ثبت نشده'}</span>`;
  return `<div class="offrow" data-media-kind="${esc(kind)}" data-media-title="${esc(title)}">
    ${ico(accountMediaIcon(kind),'width:19px;height:19px;color:var(--brand-ink)')}
    <span class="sp">${esc(title)}<small>${esc(meta)}</small></span>${action}</div>`;
}
function eventMediaToolbar(media){
  const kinds=new Set(media.map(x=>x.k)), filters=[['all','همه'],['video','ویدیو'],['audio','صدا'],['docs','فایل‌ها'],['link','پیوندها']]
    .filter(([k])=>k==='all'||(k==='docs'?[...kinds].some(x=>['pdf','slide','image','file'].includes(x)):k==='link'?kinds.has('link'):kinds.has(k)));
  return `<div class="event-media-toolbar"><label class="event-media-search">${ico('i-search')}<input type="search" data-event-media-search placeholder="جست‌وجوی فایل یا عنوان" aria-label="جست‌وجوی فایل‌های رویداد"/></label>
    <div class="event-media-filters" role="group" aria-label="صافی فایل‌های رویداد">${filters.map(([k,n],i)=>`<button type="button" class="chip${i===0?' on':''}" data-media-filter="${k}" aria-pressed="${i===0?'true':'false'}">${n}</button>`).join('')}</div></div>`;
}
function myEventSheet(id){
  const e=eventRecord(id), past=!EVENTS.some(x=>String(x.id)===String(id)), inf=myInfo(id), st=noteState(id), pack=eventPack(id),
    issued=issuedForEventList(id), requested=certReqOf(id), online=isOnlineEvent(e,inf), join=eventJoinUrl(e,inf), att=inf.att||[], media=eventMediaRows(id);
  const head=`<div class="grabber"></div>
    <div class="event-sheet-head"><span class="event-kind-tag">${ico(past?'i-archive':'i-calendar')} ${past?'برگزار شد':'پیش‌رو'}</span>
      <div class="head">${esc(e.t||'رویداد من')}</div>
      <p class="sub">${esc([past?(e.d||'برگزار شد'):e.when,e.time,e.place].filter(Boolean).join(' · '))}</p></div>`;
  const countdown=past?'':cdLine(e);
  const info=`<section class="event-section event-facts" aria-label="اطلاعات رویداد">
      <div class="event-section-title"><span>${ico('i-info')} اطلاعات رویداد</span>${chip(inf.kind||e.mode||'رویداد',online?'brand':'')}</div>
      <div class="stack tight">
        <div class="srow">${ico('i-calendar')}<span class="sp">زمان</span><b>${esc([e.when||e.d,e.time].filter(Boolean).join(' · ')||'ثبت نشده')}</b></div>
        ${e.place?`<div class="srow">${ico('i-pin')}<span class="sp">مکان / شیوهٔ حضور</span><b>${esc(e.place)}</b></div>`:''}
        ${inf.seat?`<div class="srow">${ico('i-users')}<span class="sp">جایگاه</span><b>${esc(inf.seat)}</b></div>`:''}
        ${inf.pay?`<div class="srow">${ico('i-wallet')}<span class="sp">وضعیت مبلغ</span><b>${esc(inf.pay)}</b></div>`:''}
      </div>
      ${(pack.detail||e.rep||e.desc||e.d)?`<p class="event-description">${esc(pack.detail||e.rep||e.desc||e.d)}</p>`:''}
    </section>`;
  const joinBox=online&&(join||!past)?`<section class="event-join ${join?'ready':'pending'}" aria-label="پیوند ورود آنلاین">
      <span class="event-join-icon">${ico('i-video')}</span><span class="event-join-copy"><b>${join?'ورود به رویداد آنلاین':'پیوند ورود هنوز درج نشده'}</b>
        <small>${join?'پیوند امن در تب تازه باز می‌شود.':'به‌محض ثبت پیوند رسمی، همین‌جا نمایش داده می‌شود.'}</small></span>
      ${join?`<a class="btn sm primary" href="${esc(join)}" target="_blank" rel="noopener noreferrer">${ico('i-link')} ورود به جلسه</a>`:chip('در انتظار پیوند','warn')}</section>`:'';
  const certRows=issued.length?issued.map(cert=>{
    const certName=cert.eventTitle||cert.courseTitle||cert.title||e.t||'گواهینامه', serial=String(cert.serial||''), href=certBotHref();
    return `<div class="event-cert-row"><span class="event-cert-icon">${ico('i-medal')}</span><span class="sp"><b>${esc(certName)}</b>
      <small>${serial?'سریال · '+esc(serial):'سریال در رکورد ثبت نشده'}${cert.date||cert.issueDate?' · صادرشده در '+esc(cert.date||cert.issueDate):''}${cert.source==='offline'||cert.source==='offline-purchase'?' · خرید آفلاین':''} · برای دریافت فایل در بات، «گواهینامه‌های من» را باز کن.</small></span>
      ${href?`<a class="btn sm primary" href="${esc(href)}" target="_blank" rel="noopener noreferrer" data-cert-bot>${ico('i-send')} بازکردن بات برای دریافت</a>`:`<span class="tag warn">پیوند بات در دسترس نیست</span>`}</div>`;
  }).join(''):`<div class="event-cert-status ${requested?'pending':'not-issued'}">
      <span class="event-cert-icon">${ico(requested?'i-clock':'i-medal')}</span>
      <span class="sp"><b>${requested?'در انتظار تأیید و صدور':past?'هنوز صادر نشده':'پس از پایان رویداد'}</b>
        <small>${requested?'وقتی گواهی صادر شود، همین‌جا ظاهر می‌شود و دریافتش از ربات بله است.':past?'برای این رویداد هنوز گواهیِ صادرشده‌ای در حساب پیدا نشد؛ بعد از صدور، همین‌جا نمایش داده می‌شود.':'پس از پایان برنامه و صدور گواهی، رکورد آن خودکار همین‌جا می‌آید.'}</small></span>
      ${chip(requested?'در انتظار صدور':past?'صادر نشده':'بعداً','warn')}</div>`;
  const cert=`<section class="event-section event-certificates" aria-label="گواهینامه‌ها">
      <div class="event-section-title"><span>${ico('i-medal')} گواهینامه‌های این رویداد</span>${issued.length?chip(faN(issued.length)+' صادرشده','ok'):''}</div>
      <div class="event-cert-list">${certRows}</div>
      <p class="event-privacy-note">گواهی‌های ثبت‌شده برای این رویداد، از جمله سوابق خرید آفلاین، اینجا فهرست می‌شوند؛ فایل از داخل ربات بله دریافت می‌شود.</p>
    </section>`;
  const mediaSection=`<section class="event-section event-media-section" aria-label="رسانه‌ها و پیوندهای رویداد">
      <div class="event-section-title"><span>${ico('i-play')} رسانه‌ها و پیوندهای رویداد</span><span class="tag">${faN(media.length)} قلم</span></div>
      ${pack.detail?`<p class="event-media-detail">${esc(pack.detail)}</p>`:''}
      ${media.length?`${eventMediaToolbar(media)}<div class="event-media-list">${media.map((m,i)=>offRow(m,id,i)).join('')}</div>`:
        empty2('هنوز رسانه یا پیوندی ثبت نشده','بعد از بارگذاری ضبط یا ثبت لینک معتبر، فایل‌ها و پیوندهای همین رویداد اینجا مرتب می‌شوند.','i-play')}
      <p class="event-privacy-note">ویدیو و صدا در همین پلیر باز می‌شوند؛ این صفحه دکمهٔ دریافت رسانه ندارد. فقط دامنه‌های ویدیویی شناخته‌شده داخل قاب پلیر باز می‌شوند.</p>
    </section>`;
  const attBox=att.length?`<section class="event-section"><div class="event-section-title"><span>${ico('i-check')} کارنامهٔ حضور</span></div>
    <div class="steps">${att.map(r=>`<div class="step done"><span class="dot">${ico(r[1]==='حاضر'?'i-check':'i-close','width:13px;height:13px')}</span>
      <span class="tx"><b>${esc(r[0])}</b><small>${esc(r[1])}</small></span></div>`).join('')}</div></section>`:'';
  const note=st.hasC?`<section class="event-section"><div class="event-section-title"><span>${ico('i-star')} نظر و نظرسنجی</span></div>
      <div class="mycm">${ico('i-star')}<span class="tx"><b>${faN((st.n.comment||{}).stars||'۵')} از ۵ · نظر تو</b>
        <small>${esc((st.n.comment||{}).text||'')}</small><span class="cap">${esc((st.n.comment||{}).at||'')}</span></span></div>
      ${st.hasS?`<div class="mycm ok">${ico('i-check')}<span class="tx"><b>${esc((st.n.survey||{}).n||'نظرسنجی')}</b>
        <small>${esc(((st.n.survey||{}).answers||[]).join(' · '))}</small></span></div>`:''}</section>`
    :`<section class="event-section"><div class="event-section-title"><span>${ico('i-star')} نظر و نظرسنجی</span></div>
      <div class="notebar" style="margin:0">${ico('i-star')}<span class="tx"><b>${esc(st.askS?((st.n.survey||{}).n||'نظرسنجی')+' مانده':'نظرت را ننوشتی')}</b>
        <small>${st.askS?'یک دقیقه وقت می‌برد؛ بی‌خبر نگذار':'کوتاه بنویس؛ هر وقت خواستی'}</small></span>
        <button class="btn sm primary" data-ask="${st.askS?'survey':'comment'}" data-myev="${esc(id)}">${st.askS?'شرکت در نظرسنجی':'نوشتن نظر'}</button></div></section>`;
  return `${head}${countdown}${info}${joinBox}${cert}${mediaSection}${attBox}${note}
    ${trustLine('secure')}
    <div class="row" style="margin-top:14px"><button class="btn quiet" data-close>بستن</button></div>`;
}
function openMyEvent(id){
  if(!$('#shMyEvent')) return;
  S.myEventId=String(id||''); S.refreshEventPending=false;
  fillSheet('shMyEvent',myEventSheet(id));
  openSheet('shMyEvent');
}
function refreshMyEventFromStorage(){
  if(S.view==='events')renderView();
  const sheet=$('#shMyEvent'), player=$('#shPlay');
  if(!S.myEventId||!sheet||!sheet.classList.contains('on'))return;
  if(player&&player.classList.contains('on')){S.refreshEventPending=true;return}
  S.refreshEventPending=false; fillSheet('shMyEvent',myEventSheet(S.myEventId));
}
function refreshMyEventAfterPlayer(detail){
  const target=typeof detail==='string'?detail:String(detail&&detail.id||''),
    eventId=String(detail&&typeof detail==='object'&&detail.eventId||S.myEventId||'');
  if(target!=='shMyEvent'||!eventId)return false;
  const sheet=$('#shMyEvent'); if(!sheet||!sheet.classList.contains('on'))return false;
  S.myEventId=eventId; S.refreshEventPending=false; fillSheet('shMyEvent',myEventSheet(eventId)); return true;
}
function playMyEventMedia(eventId,mediaId){

  const player=UI().player, event=eventRecord(eventId), media=eventMediaRows(eventId);
  if(typeof player!=='function'){toast('پلیر رویداد در دسترس نیست');return}
  if(!media.some(x=>String(x.id)===String(mediaId))){toast('این رسانه دیگر در فهرست رویداد نیست');return}
  player(eventId,mediaId,{event:event,media:media,contextId:'account-event:'+String(eventId),
    forceOpen:true,noDownload:true,returnTo:'shMyEvent'});
}
function filterEventMedia(box){
  if(!box)return;
  const input=box.querySelector('[data-event-media-search]'), q=cleanEventText(input&&input.value||''),
    filter=box.dataset.mediaFilter||'all';
  box.querySelectorAll('.offrow').forEach(row=>{
    const kind=row.dataset.mediaKind||'', title=cleanEventText((row.dataset.mediaTitle||'')+' '+kind),
      kindMatch=filter==='all'||(filter==='docs'?['pdf','slide','image','file'].includes(kind):filter==='link'?kind==='link':kind===filter);
    row.hidden=!(kindMatch&&(!q||title.includes(q)));
  });
}

const VS={};
VS.events=function(t){
  if(!TEST_FIXTURE_MODE) return serverAccountRegistrationsView(t);
  if(!login()) return viewHead(t,'',VTABS)+gate(t);
  const body={up:panelUp,past:panelPast,notes:panelNotes}[S.vtab];
  return viewHead(t,(VTABS.find(x=>x.k===S.vtab)||{}).n||'',VTABS)+(body?body():'');
};

const IMINE=A.invite||{};
const inviteCode=()=>String(IMINE.code||'NL-7K2D');
/* دعوت فقط کارت نمونه است؛ کد، پیوند، امتیاز یا پیام بیرونی فعال نیست. */
function inviteTab(){
  const code=inviteCode();
  return card('کد دعوت · نمونه',IMINE.lead||'کد زیر فقط برای نمایش رابط است؛ دعوت یا ثبت‌نام دوست در این نسخه انجام نمی‌شود.','i-send',
      `<div class="invcode">${ico('i-send')}
        <span class="tx"><b class="num" dir="ltr">${esc(code)}</b><small>کد نمایشی · استفادهٔ واقعی ندارد</small></span>
        <button class="btn sm quiet" data-copy="${esc(code)}" data-copy-msg="کد نمونه در کلیپ‌بورد همین دستگاه کپی شد؛ دعوت واقعی فعال نیست">${ico('i-copy')} کپی کد نمونه</button></div>
       <p class="cap" style="margin-top:10px">پیوند دعوت، ثبت‌نام دوست، شمارش ارجاع، پاداش و ارسال پیام در این پیش‌نمایش غیرفعال‌اند. کپی‌کردن کد فقط کلیپ‌بورد همین دستگاه را تغییر می‌دهد.</p>
       <button class="btn quiet" type="button" disabled aria-disabled="true">${ico('i-lock')} اشتراک‌گذاری بیرونی غیرفعال است</button>`)+
    card('وضعیت دعوت','دادهٔ دعوتی از سرور دریافت یا برای مالک ارسال نمی‌شود.','i-users',
      empty2('ارجاع واقعی ثبت نمی‌شود','این بخش فقط پیش‌نمایش رابط است؛ هیچ دوست، امتیاز یا پاداشی ثبت نشده است.','i-info'));
}
/* کارت فشردهٔ دعوت: پیوند و پاداش واقعی ندارد. */
function invitePanel(){
  return card('دعوت · نمونه','ارجاع، ثبت‌نام دوست و پاداش واقعی فعال نیست.','i-users',
    `<div class="srow">${ico('i-send')}
      <span class="sp">کد نمونه<b class="num" style="display:block;font-size:15px;margin-top:3px" dir="ltr">${esc(inviteCode())}</b></span>
      <button class="btn sm quiet" data-copy="${esc(inviteCode())}" data-copy-msg="کد نمونه کپی شد؛ دعوت واقعی فعال نیست">کپی نمونه</button></div>
     <div class="srow">${ico('i-lock')}<span class="sp">اشتراک و ثبت ارجاع</span><span class="tag warn">غیرفعال · محلی</span></div>`);
}
function clubTab(){
  const pts=+A.points||0, {cur,next}=lvl(), cap=POL.pointsCap||{};
  return card('امتیاز و سطح نمونه','این عددها فقط در مرورگرند؛ امتیاز، رتبه، تخفیف یا پاداش واقعی نیستند.','i-medal',
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
      `<div class="kinds">${STORE.map(r=>{const can=pts>=r.cost, got=!!(bookState().rewards||{})[r.n];
        return `<div class="kind">
        ${ico(got?'i-check':'i-wallet','width:19px;height:19px;color:'+(got?'var(--ok)':'var(--ink-4)'))}
        <span class="tx"><b>${esc(r.n)}</b>${guest?'':`<small>${esc(r.s)}</small>`}</span>
        ${got?chip('گرفته شد','ok'):`<button class="btn sm ${can?'primary':'quiet'}" ${can?'':'disabled'} data-reward="${esc(r.n)}">${faNum(r.cost)} امتیاز</button>`}</div>`}).join('')}</div>`)+
    invitePanel();
}

/* ══ باشگاه کتاب‌خوانی خط زندگی ══════════════════════════════════════ */
const BC_KEY='nora-home-bookclub';
function bookState(){
  let v=null; try{v=JSON.parse(localStorage.getItem(BC_KEY)||'null')}catch(e){v=null}
  return Object.assign({member:false, cstep:'form', form:{}, plan:'m', feeAt:'', feeNext:'',
    att:{}, voice:null, likes:{}, posts:[], chals:{}, entered:{}, seats:{}, tag:'پیشنهاد',
    joined:false, seat:false, pages:0, note:'', vote:'',
    sessions:0, picks:{}, quizAns:{}, formFills:{}, formDel:[], qzDel:[],
    /* ابزارهای سرپرست: پین، مطلب در پنل‌گذاشته، آزمون */
    sup:false, supStep:'home', pins:[], sent:[], qz:[], qzDraft:null, qzOn:'', pinKind:'خبر'}, v||{});
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
function qzDraftSync(){
  const d=bookState().qzDraft; if(!d) return null;
  const qs=(d.qs||[]).map(q=>Object.assign({},q,{
    l:String(($('[data-qq-label="'+q.k+'"]')||{}).value||q.l||''),
    o:(q.o||[]).map((o,i)=>String(($('[data-qq-opt="'+q.k+'"][data-opt="'+i+'"]')||{}).value||o||''))}));
  return Object.assign({},d,{n:String(($('#qzName')||{}).value||d.n||''),
    min:+unFa(String(($('#qzMin')||{}).value||d.min||10)).replace(/\D/g,'')||10, qs:qs});
}

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
        <span><b class="num">${faN(C.members||0)}</b><small>عضو · نمونه</small></span>
        <span><b class="num">${faN(C.meetings||0)}</b><small>جلسه · نمونه</small></span>
        <span><b class="num">${faN((CCLUB.podcast||{}).eps?CCLUB.podcast.eps.length:0)}</b><small>قسمت پادکست</small></span>
        <span><b class="num">${faN((CCLUB.workshops||[]).length)}</b><small>کارگاه</small></span></span>
      <span class="cllead">${esc(CGATE.lead||'')}</span></div>`;
  const formCard = step==='form'
    ? `<div class="card acct anim">${donut(pct,'٪'+faN(pct),'فرم عضویت','small')}
        <div class="head" style="margin-top:8px">${ico('i-idcard')} فرم نمونهٔ باشگاه</div>
        <p class="cap" style="margin-top:5px">${esc(CGATE.maker||'فرم نمونه')}؛ پاسخ‌ها فقط در مرورگر همین دستگاه می‌مانند.</p>
        <div class="clsform">${(CGATE.fields||[]).map(clubField).join('')}</div>
        <button class="btn primary block" style="margin-top:12px" data-clubsend>
          ${ico('i-lock')} ذخیرهٔ محلیِ پاسخ‌ها</button></div>`
    : `<div class="card acct anim"><div class="head">${ico('i-check')} پاسخ‌های محلی</div>
        <p class="cap" style="margin-top:5px">در همین مرورگر ذخیره شد؛ به سرپرست ارسال نشده و عضویت واقعی فعال نیست.</p>
        <div class="stack tight" style="margin-top:8px">${(CGATE.fields||[]).filter(f=>bc.form[f.k]).map(f=>
          `<div class="srow">${ico(f.w==='pick'?'i-check':'i-pen')}<span class="sp">${esc(f.l)}<small>${esc(bc.form[f.k])}</small></span></div>`).join('')}</div>
        <div class="row" style="margin-top:12px"><button class="btn quiet" data-clubedit>${ico('i-pen')} ویرایش فرم</button>
          <span class="sp" style="flex:1"></span><span class="tag warn">در مرورگر ذخیره شد · ارسال نشده</span></div></div>`;
  const feeCard = step==='fee'
    ? `<div class="card acct anim"><div class="head">${ico('i-lock')} مرحلهٔ عضویت واقعی غیرفعال است</div>
        <p class="cap" style="margin-top:5px">${esc(CFEE.cycle||'نمونه')} · ${esc(CFEE.note||'')}</p>
        <div class="clplans">${(CFEE.plans||[]).map(p=>`<button class="clplan${(bc.plan||'m')===p.k?' on':''}" type="button" data-clanplan="${esc(p.k)}">
          <b>${esc(p.n)}</b><small class="num">${money(p.amount)}</small>
          <span class="cap">${esc(p.s||'')}</span>${(bc.plan||'m')===p.k?`<span class="pmark">${ico('i-check','width:12px;height:12px;')}</span>`:''}</button>`).join('')}</div>
        <div class="npstats" style="margin-top:12px">
          <span><b class="num">${money(clubPlan(bc.plan).amount)}</b><small>پلن ${esc(clubPlan(bc.plan).n)}</small></span>
          <span><b>${esc(CFEE.due||'')}</b><small>سررسید هر ماه</small></span>
          <span><b class="num">${money(CFEE.student||0)}</b><small>سهم دانشجو</small></span></div>
        <button class="btn quiet block" style="margin-top:12px" disabled aria-disabled="true">${ico('i-lock')} پرداخت و عضویت واقعی وصل نیست</button>
        <p class="cap" style="margin-top:8px">${esc(CFEE.studentNote||'')}</p></div>`
    : '';
  return viewHead(t,CGATE.n||'ورود به باشگاه',null)+`<div class="panel">
    ${cover}${clubSteps(step)}
    <div class="clgrid">${formCard}${feeCard}</div>
    ${clubSupervisor(true)}${trustLine('club')}</div>`;
}
/* ── ورقهٔ پرداخت حق عضویت ─────────────────────────────────────────── */
function clubFeeSheet(){
  const bc=bookState(), plan=clubPlan(bc.plan);
  fillSheet('shClub',`<div class="grabber"></div>
    <div class="head">${ico('i-lock')} پرداخت باشگاه غیرفعال است</div>
    <p class="cap" style="margin-top:5px">${esc(CFEE.note||'')}</p>
    <div class="payamt"><span>${esc(plan.n||'پلن نمونه')}</span><b class="num">${money(plan.amount||0)} · نمونه</b>
      <span class="cap">پرداخت یا عضویت واقعی ایجاد نمی‌شود.</span></div>
    <div class="paywarn" style="margin-top:12px">${ico('i-lock')}<span>درگاه و کیف پول وصل نیست؛ هیچ مبلغی کسر و هیچ عضویتی فعال نمی‌شود.</span></div>
    <div class="row" style="margin-top:12px"><span class="sp" style="flex:1"></span>
      <button class="btn quiet" data-close>بستن</button></div>
    <p class="cap" style="margin-top:10px">${esc(CFEE.studentNote||'')}</p>`);
  openSheet('shClub');
}
/* ── سرپرست و قوانین ───────────────────────────────────────────────── */
function clubSupervisor(locked){
  const sup=clubSup(), g=CCLUB.group||{};
  return `<div class="clgrid">
    <div class="card acct anim"><div class="head">${ico('i-users')} سرپرست باشگاه</div>
      <div class="srow" style="margin-top:8px">
        <span class="qi" style="width:44px;height:44px;border-radius:15px;display:grid;place-items:center;background:linear-gradient(150deg,#7A5A2A,#123A7A);color:#fff;font-weight:700;font-size:17px">${esc(String(sup.n||'م').slice(0,1))}</span>
        <span class="sp">${esc(sup.n||'مریم داوودی')}<small>${esc(sup.r||'سرپرست باشگاه کتاب‌خوانی')}</small></span>
        <button class="btn sm quiet" data-go="support">پرسش</button></div>
      ${bookState().sup
        ? `<button class="btn sm primary block" style="margin-top:10px" data-sup-tool="home">${ico('i-pin')} کارهای سرپرست</button>`
        : `<details class="npmore2" style="margin-top:10px"><summary>${ico('i-shield')} ابزارهای سرپرست</summary>
            <p class="cap">اگر سرپرست همین باشگاهی، از اینجا پنل اعضا را بچین: پین کن، مطلب بگذار، لینک فرم‌ها را بده و آزمون بگذار.</p>
            <button class="btn sm primary block" style="margin-top:8px" data-sup-on>${ico('i-key')} روشن کردن ابزار سرپرست</button>
            <small class="cap" style="display:block;margin-top:6px">این نسخهٔ نمایشی است؛ سرپرست واقعی را مدیر سامانه تعیین می‌کند.</small></details>`}
      <details class="npmore2" style="margin-top:10px"><summary>${ico('i-doc')} قوانین باشگاه</summary>
        ${(CCLUB.rules||[]).map(r=>`<div class="srow">${ico('i-check')}<span class="sp">${esc(r)}</span></div>`).join('')}</details></div>
    <div class="card acct anim"><div class="head">${ico('i-link')} گروه و لینک اختصاصی</div>
      <p class="cap" style="margin-top:5px">${esc(g.lead||'')}</p>
      ${locked?`<div class="srow">${ico('i-lock')}<span class="sp">گروه اعضا و لینک اختصاصی
          <small>پس از تکمیل عضویت، کد گروه و لینک ورود همین‌جا می‌آید</small></span>${chip('بسته','warn')}</div>`
      :`<div class="srow">${ico('i-users')}<span class="sp">${esc(g.n||'گروه اعضا')}
        <small class="num" dir="ltr">${esc(g.code||'')}</small></span>
        ${g.link?`<button class="btn sm quiet" data-copy="${esc(g.link)}" data-copy-msg="پیوند نمونه کپی شد">${ico('i-copy')} کپی نمونه</button>`:`<button class="btn sm quiet" type="button" disabled aria-disabled="true">${ico('i-lock')} پیوند گروه وصل نیست</button>`}</div>`}
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
    {on:bc.seat,  t:'صندلی جلسهٔ پنجشنبه', s:bc.seat?'رزرو محلی شد؛ یادآوری خودکار وصل نیست':'جای محدود؛ رزرو در همین نمونه محلی است',
      act:bc.seat?'':`<button class="btn sm primary" data-seat>رزرو صندلی</button>`, i:'i-users'},
    {on:bc.pages>=10, t:'پیشرفت مطالعه', s:bc.pages?faN(bc.pages)+' صفحه از ۲۰۰ ثبت شده':'صفحه‌هایی که خوانده‌ای را ثبت کن',
      act:`<span class="bt" style="display:flex;gap:6px"><button class="btn sm quiet" data-pages="10">+۱۰</button>
        <button class="btn sm quiet" data-pages="25">+۲۵</button></span>`, i:'i-book'},
    {on:!!bc.note, t:'یادداشت جلسه', s:bc.note?'ذخیرهٔ محلی؛ برای سرپرست ارسال نشده':'یک جمله هم کافی است؛ در این نمونه محلی می‌ماند',
      act:bc.note?chip('انجام شد','ok'):'<span class="cap">مانده</span>', i:'i-pen'},
    {on:!!bc.vote, t:'رأی کتاب ماه بعد', s:bc.vote?'رأیت ثبت شد؛ نتیجه زنده به‌روز می‌شود':'از میان '+faN(VOTE.length)+' کتاب یکی را انتخاب کن',
      act:bc.vote?chip('انجام شد','ok'):'<span class="cap">مانده</span>', i:'i-star'}]
    .map(x=>`<div class="bktask ${x.on?'done':''}"><span class="bx">${ico(x.on?'i-check':x.i)}</span>
      <span class="tx"><b>${esc(x.t)}</b><small>${esc(x.s)}</small></span>${x.act}</div>`).join('')}</div>`;
}
function clubHome(){
  const bc=bookState(), C=CCLUB, meet=C.meet||[], plan=clubPlan(bc.plan);
  const m0=meet[0]||{}, m1=meet[1]||{};
  return clubLead()+clubCard()+
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
        ${(CCLUB.group||{}).link?`<button class="btn sm quiet" data-copy="${esc(CCLUB.group.link)}" data-copy-msg="پیوند نمونه کپی شد">${ico('i-copy')} کپی نمونه</button>`:`<button class="btn sm quiet" type="button" disabled aria-disabled="true">${ico('i-lock')} پیوند گروه غیرفعال</button>`}</div>
      <div class="row" style="margin-top:9px"><button class="btn sm quiet" data-ptab-go="invite">${ico('i-info')} کد دعوت نمونه</button>
        <span class="cap" style="align-self:center">ارجاع، ارسال و پاداش واقعی غیرفعال است.</span></div>`) +
    clubSupEntry()+
    trustLine('club');
}
/* درِ ابزارهای سرپرست: سرپرست از همین‌جا پنل اعضا را می‌چیند */
function clubSupEntry(){
  if(bookState().sup)
    return card('کارهای سرپرست باشگاه','پین، مطلب، لینک فرم و آزمون؛ همه از یک جا','i-pin',
      `<div class="srow">${ico('i-pin')}<span class="sp">پنل اعضا دست توست
          <small>هر چیزی بسازی، همان لحظه در پنل عضوها می‌نشیند</small></span>
        <button class="btn sm primary" data-sup-tool="home">باز کن</button></div>`+
      `<div class="srow">${ico('i-article')}<span class="sp">فهرست کارها
          <small>پین‌ها، فرم‌ها، آزمون‌ها و مطلب‌های در پنل‌گذاشته</small></span>
        <button class="btn sm quiet" data-sup-tool="home">نگات کنم</button></div>`);
  return card('سرپرست همین باشگاهی؟','ابزارهای سرپرست را روشن کن','i-shield',
    `<p class="cap">با روشن‌کردن، دو لنگر در پنل باشگاه می‌آید: «پنل اعضا» و «کارهای سرپرست». آنجا می‌توانی پین کنی، مطلبی از سامانه در پنل بگذاری، لینک فرم‌های سامانه را بدهی، یا آزمون بگذاری و نتیجه ببینی.</p>
     <button class="btn primary block" style="margin-top:10px" data-sup-on>${ico('i-key')} روشن کردن ابزار سرپرست</button>
     <small class="cap" style="display:block;margin-top:6px">این نسخهٔ نمایشی است؛ سرپرست واقعی را مدیر سامانه تعیین می‌کند.</small>`);
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
      ${clubQuiz()}
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
/* ══ ابزارهای سرپرست باشگاه ══════════════════════════════════════════
   سرپرست از همین‌جا پنل اعضا را می‌چیند: چیزی را پین می‌کند، مطلبی که در
   سامانه منتشر شده در پنل می‌گذارد، لینک فرم‌های سامانه را می‌دهد و آزمون
   می‌سازد و نتیجهٔ اعضا را می‌بیند. هر چه بسازد زیر همان شماره‌ها ذخیره
   می‌شود و همان لحظه در پنل اعضا می‌نشیند. */
const CTOOLS=CCLUB.supTools||{}, CTQ=CTOOLS.quiz||{}, CTF=CTOOLS.forms||{}, CTP=CTOOLS.pin||{};
const clubPosts=()=>(bookState().posts||[]).concat(((CCLUB.tribune||{}).posts)||[]);
const allForms=()=>{ const del=bookState().formDel||[];
  return (bookState().forms||[]).concat(CTF.list||[]).filter(f=>del.indexOf(f.k)<0) };
const allQuiz=()=>{ const del=bookState().qzDel||[];
  return (bookState().qz||[]).concat(CTQ.list||[]).filter(q=>del.indexOf(q.k)<0) };
const cfOf=k=>allForms().find(x=>x.k===k)||{};
const qzOf=k=>allQuiz().find(x=>x.k===k)||{};
const quizQs=q=>(q.qs&&q.qs.length?q.qs:(CTQ.qFields||[]));
const supIs=()=>!!bookState().sup;
const artIn=id=>(N.ARTICLES||[]).find(a=>a.id===id)||{};
const pinIcon=k=>({'خبر':'i-bell','جلسه':'i-calendar','کتاب':'i-book','مطلب':'i-article',
  'مسابقه':'i-medal','فرم':'i-list','گروه':'i-users'})[k]||'i-pin';
const supUrl=u=>!!u && /^(https?:\/\/|[\w-]+\.html)/.test(String(u).trim());
const supCopyBtn=(u,cls)=>supUrl(u)?`<button class="btn sm quiet ${cls||''}" data-copy="${esc(String(u).trim())}"
  data-copy-msg="لینک رونوشت شد">${ico('i-link')} رونوشت لینک</button>`:'';

/* ── پین ───────────────────────────────────────────────────────────── */
function pinRow(p2){
  return `<div class="pinrow"><span class="pn-ic">${ico(pinIcon(p2.kind))}</span>
    <span class="tx"><b>${esc(p2.t)}</b><small>${esc([p2.kind,p2.d,p2.at].filter(Boolean).join(' · '))}</small></span>
    <button class="btn sm quiet" data-pin-del="${esc(p2.t)}" aria-label="برداشتن پین">${ico('i-trash')}</button></div>`;
}
function pinsBox(){
  const pins=bookState().pins||[], max=CTP.max||3, left=Math.max(0,max-pins.length);
  return `<div class="pinbox">
    ${pins.length?pins.map(pinRow).join(''):empty2('هنوز چیزی پین نشده','پین‌ها بالای پنل اعضا می‌نشینند.','i-pin')}
    <p class="cap" style="margin:8px 2px 0">${left?faN(left)+' جا مانده':'جا پر است؛ یکی را بردار یا جایش را عوض کن'}</p>
    <button class="btn sm quiet block" style="margin-top:8px" data-pin-add>${ico('i-plus')} پین تازه</button></div>`;
}
function clubPins(){
  const pins=bookState().pins||[];
  if(!pins.length) return '';
  return `<div class="pinsbar anim" aria-label="پین‌های سرپرست">${pins.map(p2=>`
    <span class="pin"><span class="pn-ic">${ico(pinIcon(p2.kind))}</span>
      <span class="tx"><b>${esc(p2.t)}</b>${p2.d?`<small>${esc(p2.d)}</small>`:''}</span>
      <span class="pin-k">${esc(p2.kind||'خبر')}</span></span>`).join('')}</div>`;
}
function pinPicker(){
  const items=(CTP.items||[]), kinds=CTP.kinds||['خبر'];
  return `<div class="picker">
    <label class="hint" for="pinName">پین تازه بساز</label>
    <input class="input" id="pinName" placeholder="مثلاً جلسهٔ پنجشنبه تعطیل شد"/>
    <div class="pinchips">${kinds.map(k=>`<button class="tag${(bookState().pinKind||'خبر')===k?' on':''}"
      type="button" data-pin-kind="${esc(k)}">${esc(k)}</button>`).join('')}</div>
    <div class="row" style="margin-top:8px"><button class="btn primary" data-pin-save>${ico('i-pin')} پین کن</button>
      <span class="cap">سه پین بیشتر جا نیست</span></div></div>`;
}
function pinIdeas(){
  const P=(CTP.items||[]), posts=clubPosts();
  return `<details class="npmore2" open><summary>${ico('i-pin')} چیزی که در سامانه هست</summary>
      ${P.length?P.map((x,j)=>`<div class="srow">${ico(pinIcon(x.kind))}
        <span class="sp">${esc(x.t)}<small>${esc([x.kind,x.d].filter(Boolean).join(' · '))}</small></span>
        <button class="btn sm primary" data-pin-add-id="${j}">پین کن</button></div>`).join('')
        :`<p class="cap">چیز آماده‌ای نمانده؛ پین تازه بساز.</p>`}
      ${(CCLUB.news||[]).map((n,j)=>`<div class="srow">${ico(n.i||'i-bell')}
        <span class="sp">${esc(n.t)}<small>${esc(n.d||'')} · خبر سرپرست</small></span>
        <button class="btn sm primary" data-pin-news="${j}">پین کن</button></div>`).join('')}
      ${posts.length?`<div class="subhead">پیشنهادهای اعضا در تریبون</div>
        ${posts.slice(0,3).map(t=>`<div class="srow">${ico('i-chat')}
          <span class="sp">${esc(t.t)}<small>${esc(t.n||'عضو باشگاه')} · ${esc(t.tag||'')}</small></span>
          <button class="btn sm primary" data-pin-post="${esc(t.k)}">پین کن</button></div>`).join('')}`:''}
    </details>`;
}
/* ── مطلبی از سامانه ──────────────────────────────────────────────── */
function sentBox(){
  const ids=bookState().sent||[];
  if(!ids.length) return empty2('مطلبی در پنل نگذاشتی','از فهرست بالا یکی را انتخاب کن.','i-article');
  return `<div class="sentbox">${ids.map(id=>{ const a=artIn(id);
    return `<div class="sentrow"><span class="th"><span class="ic">${ico('i-article')}</span></span>
      <span class="tx"><b>${esc(a.t||id)}</b><small>${esc(a.cat||'')} · در پنل اعضا دیده می‌شود</small></span>
      ${supCopyBtn('home.html')}
      <button class="btn sm quiet" data-sent-del="${esc(id)}" aria-label="برداشتن">${ico('i-trash')}</button></div>`}).join('')}</div>`;
}
function sentPicker(){
  return `<div class="artpick">${(N.ARTICLES||[]).map(a=>{
    const on=(bookState().sent||[]).indexOf(a.id)>=0;
    return `<button class="artopt${on?' on':''}" type="button" data-send-art="${esc(a.id)}" aria-pressed="${on}">
      ${on?ico('i-check'):ico('i-plus')}
      <span class="tx"><b>${esc(a.t)}</b><small>${esc(a.cat||'')}${a.min?' · '+faN(a.min)+' دقیقه':''}</small></span>
      ${a.club?chip('باشگاهی','gold'):''}</button>`}).join('')}</div>`;
}
function clubSent(){
  const ids=bookState().sent||[];
  if(!ids.length) return '';
  return card('از سامانه برایت گذاشته','مطلب‌هایی که سرپرست در پنل گذاشته','i-article',
    `<div class="clubread">${ids.map(id=>{const a=artIn(id);
      return `<div class="crrow"><span class="ic">${ico('i-article')}</span>
        <span class="tx"><b>${esc(a.t||id)}</b><small>${esc(a.cat||'')}${a.views?' · '+esc(a.views)+' بازدید':''}</small></span>
        <button class="btn sm quiet" data-go="support">پرسش</button></div>`}).join('')}</div>`);
}
/* ── فرم‌ها ───────────────────────────────────────────────────────── */
/* پرسش‌های هر فرم: یا فهرست خودش، یا کلیدهایی که به پارامترهای سامانه اشاره می‌کنند */
function formFields(f){
  f=f||{};
  if(f.fields&&f.fields.length) return f.fields;
  const bank=CTF.fields||[];
  return (f.keys||f.nOf&&[]||[]).map(k=>bank.find(x=>x.k===k)||{k:k}).filter(Boolean);
}
function formRow(f){
  const open=(f.state!=='closed');
  return `<div class="frow">
    <span class="fr-h"><b>${esc(f.n)}</b><small>${esc(f.d||'')}</small></span>
    <span class="fr-m">${chip(open?(CTF.status||{}).open||'باز':(CTF.status||{}).closed||'بسته',open?'ok':'')}
      <span class="cap">${faN(formFields(f).length)} پرسش</span>
      ${f.ends?`<span class="cap">تا ${esc(f.ends)}</span>`:''}
      <span class="cap">${faN(f.got||0)} پاسخ</span></span>
    <span class="acts"><button class="btn sm quiet" data-club-form="${esc(f.k)}">${ico('i-inbox')} پاسخ‌ها</button>
      ${supCopyBtn(f.link)}</span></div>`;
}
function formsBox(){
  const list=allForms();
  return `<div class="formsbox">
    ${list.length?list.map(formRow).join(''):empty2('فرمی نیست','مدیر سامانه فرم را می‌سازد و همین‌جا می‌آید.','i-list')}</div>`;
}
function formAnswers(id){
  const f=cfOf(id);
  const names=(CCLUB.board||[]).map(b=>b.n);
  const rows=Math.max(0,Math.min(8,Math.round((+f.got||0)/2)));
  return `<div class="fansbox"><div class="head">${ico('i-inbox')} پاسخ‌های «${esc(f.n||'')}»</div>
    <p class="cap" style="margin-top:5px">${esc(f.link||'')} · لینک را در گروه اعضا بگذار</p>
    ${rows?Array.from({length:rows}).map((_,i)=>`<div class="fanrow">
      <span class="av">${esc(String(names[i%names.length]||'ع').slice(0,1))}</span>
      <span class="tx"><b>${esc(names[i%names.length]||'عضو باشگاه')}</b>
        <small>پاسخ ${faN(i+1)}${f.ends?' · تا '+esc(f.ends):''}</small></span>${chip('رسید','ok')}</div>`).join('')
      :empty2('هنوز پاسخی نرسیده','لینک را برای اعضا بفرست.','i-archive')}
    <div class="row" style="margin-top:10px">${supCopyBtn(f.link)}
      <button class="btn sm quiet" data-form-csv="${esc(id)}">${ico('i-doc')} برون‌بری پاسخ‌ها</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" data-close>بستن</button></div></div>`;
}
function clubFill(id){
  const f=cfOf(id), ans=(bookState().formFills||{})[id]||{};
  return `<div class="grabber"></div><div class="head">${ico('i-pen')} ${esc(f.n||'فرم سرپرست')}</div>
    <p class="sub" style="margin-top:6px">${esc(f.d||'')}${f.ends?' · تا '+esc(f.ends):''}</p>
    <div class="clsform">${(f.fields||[]).map(x=>x.w==='pick'
      ? `<div class="fld"><span class="hint">${esc(x.l)}</span>
          <div class="seg">${(x.opts||[]).map(o=>`<button class="segbtn${ans[x.k]===o?' on':''}" type="button"
            data-ff-pick="${esc(x.k)}" data-ff-val="${esc(o)}" aria-pressed="${ans[x.k]===o}">${esc(o)}</button>`).join('')}</div>
          <input type="hidden" id="ff_${esc(x.k)}" value="${esc(ans[x.k]||'')}"/></div>`
      : `<div class="fld"><label class="hint" for="ff_${esc(x.k)}">${esc(x.l)}${x.req?' *':''}</label>
          <input class="input" id="ff_${esc(x.k)}" value="${esc(ans[x.k]||'')}" placeholder="${esc(x.ph||'')}" style="margin-top:6px"/></div>`).join('')}</div>
    <div class="row" style="margin-top:14px"><button class="btn primary" data-cf-send="${esc(f.k)}">${ico('i-send')} بفرست</button>
      <button class="btn quiet" data-close>بی‌خیال</button></div>`;
}
function quizSitting(id){
  const q=qzOf(id), qs=quizQs(q), ans=(bookState().quizAns||{})[id]||{};
  if(!qs.length) return `<div class="grabber"></div><div class="head">${ico('i-medal')} ${esc(q.n||'آزمون')}</div>
    <p class="sub" style="margin-top:8px">پرسش‌های این آزمون هنوز آماده نیست.</p>
    <div class="row" style="margin-top:12px"><button class="btn quiet" data-close>بستن</button></div>`;
  return `<div class="grabber"></div><div class="head">${ico('i-medal')} ${esc(q.n||'آزمون')}</div>
    <p class="sub" style="margin-top:6px">${faN(qs.length)} پرسش${q.min?' · '+faN(q.min)+' دقیقه':''}؛ هر پرسش یک گزینهٔ درست دارد.</p>
    <div class="qqs" style="margin-top:10px">${qs.map((x,i)=>`<div class="qq">
      <b style="font-size:12.5px">${faN(i+1)}. ${esc(x.l)}</b>
      <div class="qqopts">${(x.o||[]).map((o,j)=>`<div class="qqopt">
        <button class="btn sm quiet${ans[x.k]===j?' on':''}" data-qa="${esc(x.k)}" data-qi="${j}"
          aria-pressed="${ans[x.k]===j}">${ico('i-check')} ${esc(o)}</button></div>`).join('')}</div></div>`).join('')}</div>
    <div class="row" style="margin-top:14px"><button class="btn primary" data-qz-submit="${esc(id)}">${ico('i-send')} بفرست</button>
      <button class="btn quiet" data-close>بی‌خیال</button></div>`;
}
function clubQuiz(){
  const list=allQuiz().filter(q=>q.state==='open');
  if(!list.length) return '';
  const picks=bookState().picks||{};
  return card('آزمون‌های باشگاه',faN(list.length)+' آزمون باز؛ نتیجه‌اش را سرپرست می‌بیند','i-medal',
    `<div class="qzbox">${list.map(q=>{ const done=picks[q.k]!==undefined;
      return `<div class="qzrow"><span class="qz-ic">${ico('i-medal')}</span>
        <span class="tx"><b>${esc(q.n)}</b><small>${esc(q.q||'')}${q.min?' · '+faN(q.min)+' دقیقه':''}
          ${done?' · نمرهٔ تو: '+faN(+picks[q.k])+' از '+faN(quizQs(q).length):''}</small></span>
        <span class="acts">${done?chip('داده‌ای','ok'):chip('باز','brand')}
          <button class="btn sm ${done?'quiet':'primary'}" data-qz-take="${esc(q.k)}">${ico('i-pen')} ${done?'دوباره':'شرکت کن'}</button></span></div>`}).join('')}</div>`);
}
function clubForms(){
  const list=allForms().filter(f=>f.state!=='closed');
  if(!list.length) return '';
  return card('فرم‌های سرپرست',faN(list.length)+' فرم باز؛ انتخاب و فرستادن، بی تایپ','i-list',
    `<div class="cfrm">${list.map(f=>`<div class="frow">
      <span class="fr-h"><b>${esc(f.n)}</b><small>${esc(f.d||'')}</small></span>
      <span class="fr-m">${chip((CTF.status||{}).open||'باز','ok')}${f.ends?`<span class="cap">تا ${esc(f.ends)}</span>`:''}</span>
      <span class="acts"><button class="btn sm primary" data-cf-fill="${esc(f.k)}">${ico('i-pen')} پر کردن</button>
        <button class="btn sm quiet" data-cf-link="${esc(f.k)}">${ico('i-link')} لینک</button></span></div>`).join('')}</div>`);
}
/* ── آزمون‌ساز ────────────────────────────────────────────────────── */
function quizRow(q){
  const draft=(q.state==='draft'), open=(q.state==='open');
  return `<div class="qzrow"><span class="qz-ic">${ico('i-medal')}</span>
    <span class="tx"><b>${esc(q.n)}</b><small>${esc(q.q||'')}${q.min?' · '+faN(q.min)+' دقیقه':''} · ${faN(q.took||0)} نفر داده‌اند</small></span>
    <span class="acts">${chip(draft?'پیش‌نویس':open?'باز':'بسته',draft?'warn':open?'ok':'')}
      <button class="btn sm quiet" data-qz-res="${esc(q.k)}">نتیجه‌ها</button>
      ${draft?`<button class="btn sm primary" data-qz-open="${esc(q.k)}">منتشر کن</button>`
        :`<button class="btn sm quiet" data-qz-close="${esc(q.k)}">ببند</button>`}
      <button class="btn sm quiet" data-copy="account.html#book" data-copy-msg="لینک آزمون رونوشت شد" aria-label="لینک آزمون">${ico('i-link')}</button>
      <button class="btn sm quiet" data-qz-del="${esc(q.k)}" aria-label="برداشتن آزمون">${ico('i-trash')}</button></span></div>`;
}
function quizBox(){
  const list=allQuiz(), d=bookState().qzDraft;
  return `<div class="qzbox">
    <div class="fb-head"><b>آزمون‌های من</b>${list.length?`<span class="cap">${faN(list.length)} آزمون</span>`:''}
      ${d?'':`<button class="btn sm primary" style="margin-inline-start:auto" data-qz-new>${ico('i-plus')} آزمون تازه</button>`}</div>
    ${d?quizBuilder(d):''}
    ${list.length?list.map(quizRow).join(''):(d?'':empty2('آزمونی نساختی','یک آزمون کوتاه کافی است.','i-medal'))}
    <details class="npmore2"><summary>${ico('i-shield')} قاعده‌های آزمون</summary>
      <div class="srow">${ico('i-check')}<span class="sp">لینک آزمون فقط به گروه اعضا می‌رود</span></div>
      <div class="srow">${ico('i-check')}<span class="sp">نتیجه‌ها را سرپرست می‌بیند، بقیه نه</span></div></details></div>`;
}
function quizBuilder(d){
  return `<div class="qzbuild">
    <label class="hint" for="qzName">نام آزمون</label>
    <input class="input" id="qzName" value="${esc(d.n||'')}" placeholder="مثلاً آزمون کتاب ماه، فصل ۵"/>
    <div class="row" style="margin-top:8px;align-items:center"><label class="hint" for="qzMin">مدت (دقیقه)</label>
      <input class="input" id="qzMin" style="width:84px" inputmode="numeric" value="${esc(d.min||10)}"/>
      <span class="cap">پس از این مدت زمان‌سنج صفر می‌شود؛ لینک بسته نمی‌شود.</span></div>
    <span class="hint" style="margin-top:10px">پرسش‌ها</span>
    <div class="qqs">${(d.qs||[]).map(q=>`<div class="qq">
      <input class="input" value="${esc(q.l||'')}" placeholder="متن پرسش" data-qq-label="${esc(q.k)}"/>
      <div class="qqopts">${(q.o||['','','','']).map((o,i)=>
        `<div class="qqopt"><span class="num">${faN(i+1)}</span>
          <input class="input" value="${esc(o)}" placeholder="گزینه" data-qq-opt="${esc(q.k)}" data-opt="${i}"/>
          <button class="btn sm quiet${((q.a|0)===i)?' on':''}" data-qq-right="${esc(q.k)}" data-opt="${i}"
            aria-pressed="${((q.a|0)===i)}" aria-label="گزینهٔ درست">${ico('i-check')}</button></div>`).join('')}</div></div>`).join('')}</div>
    <div class="fadd"><button class="btn sm quiet" data-qq-add>${ico('i-plus')} پرسش تازه</button>
      <button class="btn sm quiet" data-qq-ready>${ico('i-star')} پرسش آماده</button></div>
    <div class="row" style="margin-top:12px"><button class="btn primary" data-qz-save>${ico('i-check')} ذخیرهٔ آزمون</button>
      <button class="btn quiet" data-qz-cancel>بی‌خیال</button></div></div>`;
}
function quizResults(id){
  const q=qzOf(id);
  const seed=((CTQ.results||{})[id])||[];
  const mine=(bookState().picks||{})[id]!==undefined?[id]:[];
  const total=quizQs(q).length||(+String(q.q||'').replace(/[^\d۰-۹]/g,'')||0);
  const rows=seed.concat(mine.map(()=>({n:(prof().fullName||'عضو')+' (تو)',
      s:faN(+((bookState().picks||{})[id]||0))+' از '+faN(total||0), at:'همین حالا'})))
    .map((r,i)=>`<div class="resrow"><span class="medal m${Math.min(3,i+1)}">${ico('i-medal')}</span>
      <span class="tx"><b>${esc(r.n)}</b><small>${esc(r.at||'')}</small></span><b class="num">${esc(r.s)}</b></div>`).join('');
  return `<div class="qzres anim"><div class="head">${ico('i-medal')} نتیجهٔ «${esc(q.n||'')}»</div>
      ${rows||empty2('نتیجه‌ای نیست','آزمون پیش‌نویس است یا کسی نداده.','i-archive')}
      <div class="npstats" style="margin-top:10px">
        <span><b class="num">${faN(q.took||seed.length)}</b><small>شرکت‌کننده</small></span>
        <span><b>${esc(q.avg||'—')}</b><small>میانگین</small></span>
        <span><b>${esc(q.pass||'—')}</b><small>قبولی</small></span>
        <span><b>${esc(q.top||'—')}</b><small>بهترین</small></span></div>
      <div class="row" style="margin-top:10px">
        <button class="btn sm quiet" data-qz-csv="${esc(id)}">${ico('i-doc')} برون‌بری نتیجه‌ها</button>
        <button class="btn sm quiet" data-qz-close="${esc(id)}">${ico('i-lock')} بستن آزمون</button>
        <span class="sp" style="flex:1"></span><button class="btn quiet" data-qz-res="${esc(id)}">بستن نتیجه</button></div></div>`;
}
/* ── کارتابل سرپرست: خانه، بخش‌ها و کنش‌ها ────────────────────────── */
function supShare(){
  const u=(CCLUB.group||{}).link||'';
  return card('گروه و لینک اختصاصی','لینک فرم و آزمون را همین‌جا برای اعضا بگذار','i-link',
    `<div class="srow">${ico('i-users')}<span class="sp">${esc((CCLUB.group||{}).n||'گروه اعضا')}
        <small class="num" dir="ltr">${esc((CCLUB.group||{}).code||'')}</small></span>${supCopyBtn(u)}</div>
     <div class="srow">${ico('i-book')}<span class="sp">کتاب ماه و ضبط&zwnj;های تازه
        <small>خبر هر ترم در گروه می‌آید</small></span>${supCopyBtn('account.html#book')}</div>`);
}
function supHome(){
  const T=CTOOLS, b=bookState(), pins=b.pins||[], forms=allForms();
  const openQ=allQuiz().filter(x=>x.state==='open').length;
  const cover = `<div class="supcover anim">${ico('i-medal')}
      <span class="tx"><b>پنل سرپرست باشگاه</b><small>${esc(T.lead||'')}</small></span>
      <div class="row" style="margin-top:12px;width:100%">
        <button class="btn primary" data-sup-member>${ico('i-users')} پنل اعضا</button>
        <button class="btn quiet" data-copy="account.html#book" data-copy-msg="لینک پنل باشگاه رونوشت شد">${ico('i-link')} لینک پنل</button></div></div>
    <div class="npstats" style="margin-top:10px">
      <span><b class="num">${faN(pins.length)}</b><small>پین فعال</small></span>
      <span><b class="num">${faN(forms.length)}</b><small>فرم</small></span>
      <span><b class="num">${faN(CCLUB.members||0)}</b><small>عضو</small></span>
      <span><b class="num">${faN(openQ)}</b><small>آزمون باز</small></span></div>`;
  const voice=b.voice?card('درخواست ضبط پادکست','عضوها می‌توانند در ضبط شرکت کنند','i-play-f',
      `<div class="srow">${ico('i-play-f')}<span class="sp">${esc(b.voice.role||'')}
        <small>${esc(b.voice.slot||'')}</small></span>${chip('در نوبت','warn')}</div>`):'';
  return cover+
    card('کارهای سرپرست','هر کار یک بخش جدا دارد','i-list',
      `<div class="toolsGrid">${[['pin','پین کردن','i-pin'],['send','فرستادن مطلب','i-article'],
        ['form','لینک فرم‌ها','i-list'],['quiz','آزمون‌ساز','i-medal']]
        .map(([k,n,ic])=>`<button class="tool" data-sup-tool="${k}"><span class="ic">${ico(ic)}</span><b>${esc(n)}</b></button>`).join('')}</div>`)+
    voice;
}
function supBody(sv){
  if(sv==='pin') return card('پین‌های باشگاه',esc(CTP.lead||''),'i-pin',pinsBox())+
    card('از خود سامانه','خبر، جلسه، کتاب، مطلب یا پیشنهاد عضو را پین کن','i-pin',pinIdeas())+
    card('پین تازه','چیزی که فقط سرپرست می‌داند','i-plus',pinPicker());
  if(sv==='send') return card('مطالبی که سامانه منتشر کرده',esc((CTOOLS.articles||{}).lead||''),'i-article',sentPicker())+
    card('در پنل اعضا گذاشته‌شده',faN((bookState().sent||[]).length)+' مطلب','i-check',sentBox())+supShare();
  if(sv==='form') return card('فرم‌های باشگاه',esc(CTF.lead||''),'i-list',formsBox())+
    card('پاسخ‌ها','پاسخ هر عضو همین‌جا می‌نشیند؛ لینک را در گروه بگذار','i-inbox',
      `<div class="row">${(allForms()[0]||{}).link?`<button class="btn sm quiet" data-club-form="${esc((allForms()[0]||{}).k)}">${ico('i-inbox')} بازکردن پاسخ‌ها</button>`:''}
        <span class="cap">فرم تازه را مدیر سامانه می‌سازد</span></div>`)+supShare();
  if(sv==='quiz'){ const on=bookState().qzOn;
    return (on?quizResults(on):'')+card('آزمون‌ساز',esc(CTQ.lead||''),'i-medal',quizBox()); }
  return '';
}
function supLane(cur){
  return `<div class="lanes anim" role="tablist" aria-label="لنگرهای باشگاه">
    <button class="lane${cur==='member'?' on':''}" data-sup-member aria-selected="${cur==='member'}">${ico('i-users')} پنل اعضا</button>
    <button class="lane${cur!=='member'?' on':''}" data-sup-tool="${cur==='member'?'home':cur}" aria-selected="${cur!=='member'}">${ico('i-pin')} کارهای سرپرست</button></div>`;
}
function supNav(cur){
  return `<div class="supnav anim">${[['pin','پین','i-pin'],['send','مطلب','i-article'],['form','فرم‌ها','i-list'],['quiz','آزمون','i-medal']]
    .map(([k,n,ic])=>`<button class="ctab${cur===k?' on':''}" data-sup-tool="${k}"
      aria-selected="${cur===k}">${ico(ic)} ${n}</button>`).join('')}</div>`;
}
/* ── خود پنل: دو لنگر، پنل اعضا و کارهای سرپرست ───────────────────── */
function clubPanel(t){
  const C=CCLUB, v=clubPanelView(), sup=supIs(), sst=bookState().supStep||'pin';
  if(sup && v==='sup'){
    const body = sst==='home'?supHome() : (supBody(sst)||supHome());
    const tabs = sst==='home'
      ? `<div class="clsub anim">${CTABS.filter(x=>x.k!=='sup').map(x=>`<button class="tag" data-ctab="${esc(x.k)}">${x.i?ico(x.i):''} ${esc(x.n)}</button>`).join('')}</div>`
      : supNav(sst);
    const sub=(C.term||'')+(sst==='home'?'':' · کارهای سرپرست');
    return viewHead(t,sub,null)+supLane(sst)+tabs+`<div class="panel">${body}</div>`;
  }
  const body = v==='meet'?clubMeet() : v==='media'?clubMedia() : v==='game'?clubGame() : v==='talk'?clubTalk() : clubHome();
  const tabs = sup ? CTABS.concat([{k:'sup',n:'سرپرست',i:'i-medal'}]) : CTABS;
  const sub=(C.term||'')+(C.book?' · '+C.book:'');
  return viewHead(t,sub,tabs,'ctab')+(supIs()?supLane('member'):'')+`<div class="panel">${body}</div>`;
}
/* پنل عضو: پین‌ها، مطلب‌های سرپرست و فرم‌هایش بالا می‌آیند */
function clubLead(){
  return clubPins()+clubSent()+clubForms();
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
    if(f.lock){ if(!v) e[f.k]='از حساب خودت خوانده می‌شود؛ دوباره وارد شو'; continue }
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
  if(f.lock) return `<span class="v">${ico('i-lock','width:15px;height:15px;color:var(--warn)')}
      <span class="tx">${esc(val||'—')}</span><span class="tag warn" style="height:20px;font-size:10px">محلی · تأییدنشده</span></span>`;
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
  if(f.lock) bits.push('شماره در این مرورگر قفل است؛ تأیید یا امکان تغییر سروری وجود ندارد');
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
      :`<span class="tx"><span class="cap">همین عکس روی پروفایل و گواهی نمایش داده می‌شود</span></span>`}
    </span></div>`;
}
function formsPanel(){
  const F=[{t:'فرم پروفایل اعضا',k:'پروفایل',s:'pending',d:'۲ مهر',mine:true},
           {t:'پیش‌ثبت‌نام کارگاه خطاطی',k:'پیش‌ثبت‌نام',s:'draft',d:'۳ مهر'},
           {t:'رضایت‌سنجی کارگاه عکاسی',k:'رضایت‌سنجی کارگاه',s:'pending',d:'۲۱ تیر'},
           {t:'انتخاب مسیر ترم پاییز',k:'انتخاب مسیر',s:'approved',d:'۱۲ شهریور'}];
  const M={draft:['پیش‌نویس نمونه','warn'],pending:['پاسخ نمونه · بررسی‌نشده','warn'],approved:['ذخیرهٔ محلی · تأییدنشده','warn']};
  return card('فرم‌های من','فهرست و وضعیت‌های نمایشی؛ بررسی، تأیید یا ارسال سروری انجام نمی‌شود','i-doc',
    F.map(f=>`<div class="tk">${ico(f.mine?'i-idcard':'i-doc','width:19px;height:19px;color:var(--ink-4)')}
      <span><b>${esc(f.t)}</b><small>${esc(f.k)} · تاریخ نمونه ${esc(f.d)}${f.mine?' · فرم نمایشی':''}</small>
        <span class="acts">${chip(M[f.s][0],M[f.s][1])}
          <button class="btn sm quiet" data-form="${esc(f.t)}" data-formst="${esc(f.s)}">${f.s==='draft'?'ادامهٔ نمونه':'بازکردن پاسخ نمونه'}</button></span></span></div>`).join('')+
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
      <span class="lc cap" style="margin-inline-start:auto">${esc(asked&&i===0?'ثبت محلی':now?'وصل نیست':'—')}</span></div>`}).join('');
  return card('داده‌های محلی','درخواست حذف و خروجی این نمونه به حساب سروری وصل نیست','i-lock',
    `<div class="srow">${ico('i-doc')}
      <span class="sp">خروجی دادهٔ محلی<small>فقط مقادیر نمونه و اطلاعات همین مرورگر؛ دادهٔ سروری در دسترس نیست.</small></span>
      <button class="btn sm quiet" id="dlBtn">${ico('i-download')} خروجی محلی</button></div>
     <div class="srow">${ico('i-shield','color:var(--stop)')}
      <span class="sp">درخواست حذف نمایشی<small>${esc(DELFLOW.lead||'این نسخه حساب واقعی را حذف نمی‌کند.')}</small></span>
      <button class="btn sm stop" id="delBtn" ${asked?'disabled':''}>${asked?'درخواست محلی ثبت شد':'آزمایش درخواست حذف'}</button></div>
     <div class="steps" style="margin-top:10px">${steps}</div>
     <div class="cap" id="delNote" style="margin-top:8px">${asked?esc(DELFLOW.note||''):''}</div>`)+
    note('این نسخه حساب واقعی را حذف نمی‌کند؛ فقط کلمهٔ «حذف» و کد ثابت ۵۴۳۲۱ را در یک درخواست محلی بررسی می‌کند. پیامک، بررسی کارشناس و پاک‌کردن سمت سرور وصل نیست.','i-lock')+
    card('ماندگاری دادهٔ نمونه','در همین مرورگر','i-shield',
      `<div class="srow">${ico('i-lock')}<span class="sp">درخواست حذف فقط یک نشان محلی است؛ حساب یا دادهٔ سروری حذف نمی‌شود.</span></div>
       <div class="srow">${ico('i-lock')}<span class="sp">خروجی شامل داده‌های نمونه و مقادیر محلی است؛ آن را پروندهٔ رسمی تلقی نکن.</span></div>
       <div class="srow">${ico('i-lock')}<span class="sp">پاک‌کردن دادهٔ مرورگر جدا از این درخواست است؛ یادآوری بیرونی وصل نیست.</span></div>`)+
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
/* عکس پروفایل: پارامتر تصویری فرم، بارگذاری یا عکس نمونه */
function demoPhoto(){
  const p=prof(), cur=p.photo||PHOTO_SEED[0];
  const next=PHOTO_SEED[(PHOTO_SEED.indexOf(cur)+1)%PHOTO_SEED.length];
  p.photo=next; if(UI().saveProfile) UI().saveProfile(p);
  render(); toast('عکس پروفایل ذخیره شد و در پروفایل نمایش داده می‌شود');
}
async function pickPhoto(file){
  if(!file)return;
  const api=UI();
  if(typeof api.imageToWebPDataURL!=='function'){toast('ابزار تبدیل تصویر در دسترس نیست؛ عکس ذخیره نشد');return}
  try{
    const image=await api.imageToWebPDataURL(file,{maxEdge:360});
    const p=prof();p.photo=image.dataUrl;
    if(api.saveProfile)api.saveProfile(p);
    render();toast('عکس پروفایل به WebP تبدیل و در همین مرورگر ذخیره شد');
  }catch(error){toast(api.imageErrorMessage?api.imageErrorMessage(error):'تصویر تبدیل نشد؛ ذخیره نشد')}
}
document.addEventListener('change',ev=>{
  const el=ev.target;
  if(el&&el.id==='phFile'&&el.files&&el.files[0]) pickPhoto(el.files[0]);
},false);

/* ورقهٔ «اطلاعاتت ایمن است»: همهٔ جمله‌های اطمینان یک‌جا */
function trustSheet(){
  const rows=(N.TRUST&&N.TRUST.row)||[];
  fillSheet('shTrust',`<div class="grabber"></div><div class="head">${esc((N.TRUST&&N.TRUST.head)||'پیش‌نمایش محلی نورا')}</div>
    <p class="sub" style="margin-top:8px">کوتاه و بی‌حاشیه؛ همین‌ها را رعایت می‌کنیم.</p>
    <div class="steps" style="margin-top:10px">${rows.map(r=>`<div class="step done">
      <span class="dot">${ico('i-shield','width:13px;height:13px')}</span>
      <span class="tx"><b>${esc(r[0])}</b><small>${esc(r[1])}</small></span></div>`).join('')}</div>
    <div class="row" style="margin-top:14px"><button class="btn quiet" data-close>بستن</button></div>`);
  openSheet('shTrust');
}

/* ورود و امنیت: شماره، دستگاه‌ها، پیام‌گیرها و خروج */
function authPanel(){
  const ph=phone();
  return card('ورود نمایشی','این نمونه فقط در همین مرورگر ذخیره می‌شود؛ احراز هویت سروری وصل نیست','i-mobile',
      `<div class="srow">${ico('i-mobile')}
        <span class="sp">شمارهٔ واردشده<small class="num">${ph?'۰۹'+faN(ph.slice(2,5))+'…'+faN(ph.slice(-4)):'—'}</small></span></div>
       <div class="srow">${ico('i-lock')}
        <span class="sp">کد ثابت آزمایشی<small>۵۴۳۲۱؛ پیامک یا ربات واقعی نمی‌فرستیم</small></span>${chip('نمونهٔ محلی','warn')}</div>
       <p class="cap" style="margin-top:8px">فهرست دستگاه‌ها، ورودها و تغییر شماره در این نسخه شبیه‌سازی شده و امنیت واقعی ایجاد نمی‌کند.</p>
       <a class="btn sm quiet" href="login.html" style="margin-top:8px">بازکردن صفحهٔ ورود آزمایشی</a>`)+
    card('ورود این مرورگر','خروج فقط دادهٔ ورود محلی را از همین مرورگر پاک می‌کند؛ حساب سروری وجود ندارد','i-lock',
      `<button class="btn stop" id="logoutBtn">${ico('i-close')} پاک‌کردن دادهٔ ورود محلی</button>
       <p class="cap" style="margin-top:9px">خروج، سابقهٔ نمونه را از سرویس بیرونی حذف نمی‌کند؛ داده‌ای به سرور فرستاده نشده است.</p>`)+
    trustLine('secure');
}

/* پروفایل من: شش تب، هر چیزی که به خودِ عضو برمی‌گردد، یک‌جا */
const PTABS=A.profileTabs||[{k:'info',n:'اطلاعات من'}];
VS.profile=function(t){
  if(!TEST_FIXTURE_MODE) return serverAccountProfileView(t);
  if(!login()) return viewHead(t,'',PTABS,'ptab')+gate(t);
  const body=S.ptab==='auth'?authPanel()
    : S.ptab==='invite'?inviteTab()
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
  if(!TEST_FIXTURE_MODE) return serverBookClubView(t);
  if(!login()) return viewHead(t,'',null)+gate(t);
  if(!clubIsMember()) return clubJoin(t);
  return clubPanel(t);
};

/* ══ نورا پی: برنامه، روش‌ها و سوابق فقط در حالت نمایشی ═══════════════
   صفحه، جزئیات روش‌های غیروالی، اقساط، صورت‌حساب‌ها و تراکنش‌های نمونه را
   نشان می‌دهد. کیف پول، شارژ، پرداخت و تأیید بانکی برای کاربر فعال نیستند؛
   دادهٔ قدیمیِ کیف پول هم به‌عنوان موجودی یا سابقهٔ معتبر خوانده نمی‌شود. */
function payState(){
  /* فقط مقادیر نمونه؛ localStorage قدیمی هرگز به‌عنوان پرداخت یا بدهی خوانده نمی‌شود. */
  return {bal:(PAYINFO.wallet||{}).bal||0, debt:0, paid:{}, part:{}, refunds:{}, txs:[], def:''};
}
function paySave(){
  /* تراکنش یا ماندهٔ قابل‌خرج در پیش‌نمایش ذخیره نمی‌شود. */
  return payState();
}
const walletBal=()=>payState().bal;
const debtAmt=()=>payState().debt;
const gateOf=k=>{try{const U=window.NORA_UI||{}, F=U.finPublic?U.finPublic():null;
  return (F&&F.gates||[]).find(g=>g.k===k)||null}catch(e){return null}};
const activeCard=amount=>{try{const U=window.NORA_UI||{}; return U.finActive?U.finActive(undefined,amount):null}catch(e){return null}};
const methodOf=(k,amount)=>{
  const base=PAYM.find(m=>m.k===k)||{}, U=window.NORA_UI||{}, gate=gateOf(k)||{};
  if(PAYINFO.demo) return Object.assign({},base,{on:false,s:'پرداخت واقعی به سرور یا درگاه وصل نیست'});
  if(k==='custom'){
    return Object.assign({},base,{on:false,n:gate.n||base.n,s:gate.s||'تا اتصال درگاه و راه‌اندازی سرور، پرداخت واقعی فعال نیست',
      i:gate.i||base.i,rule:base.rule,url:gate.url||'',pct:+gate.pct||0,fixed:+gate.fixed||0,who:gate.who||'org'});
  }
  if(k==='card'){
    const c=activeCard(amount), gateOn=U.finGateOn?U.finGateOn(k):false, ready=!!(gateOn&&c&&c.no);
    return Object.assign({},base,{on:base.on!==false&&ready,
      s:ready?'شمارهٔ کارتِ نوبت‌دار؛ تأیید رسید با مدیر':'کارت‌به‌کارت فعلاً در دسترس نیست؛ مالک باید کارت اضافه کند',
      cardId:c&&c.id||'',bank:c&&c.bank||'',no:c&&c.no||'',name:c&&c.name||'',
      hold:(PAYINFO.card||{}).hold||'۳۰ دقیقه'});
  }
  if(k==='bale'){
    const ready=!!(gate.on&&gate.live===true);
    return Object.assign({},base,{on:base.on!==false&&ready,
      s:ready?(gate.s||base.s):'درگاه واقعی به سرور وصل نیست؛ پرداختی انجام نمی‌شود',
      n:gate.n||base.n,rule:base.rule});
  }
  if(k==='wallet') return Object.assign({},base,{on:base.on!==false,s:'نمونهٔ محلی همین مرورگر؛ موجودی و پرداخت واقعی نیست'});
  const on=U.finGateOn?U.finGateOn(k):base.on!==false;
  return Object.assign({},base,{on:base.on!==false&&on});
};
const money=n=>faNum(n)+'  تومان';
const modelsOf=eid=>{
  const base=((PAY_EV&&PAY_EV[eid])||PAY_DEF).slice();
  ['custom'].forEach(k=>{const m=methodOf(k); if(m.on&&base.indexOf(k)<0) base.push(k)});
  return base.filter((k,i,a)=>a.indexOf(k)===i&&methodOf(k).on);
};
function invState(v){ const st=payState();
  return st.paid[v.id]?'paid':(st.refunds[v.id]?'refunded':(st.part[v.id]?'partial':v.state)) }
function invTone(s){ return s==='paid'?'ok':(s==='refunded'||s==='failed'||s==='rejected')?'stop':s==='partial'?'gold':'brand' }
function invStateTxt(s){ return (PAYINFO.states||{})[s]||s }
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
  const w=walletConfig(), bal=walletBal(), cap=w.cap||0, debt=debtAmt();
  const pct=cap?Math.min(100,Math.round(bal/cap*100)):0, n=(PAYINFO.txs||[]).length;
  return `<div class="nphero anim">
    <div class="npcover">
      <span class="npk">${ico('i-wallet')} ${esc(w.n||'کیف پول نورا پی')}</span>
      <span class="npbal"><b class="num">${money(bal)}</b><small>موجودی نمونهٔ محلی · اعتبار قابل‌مصرف نیست</small></span>
      <span class="npsub">
        ${w.auto?`<span class="nptag warn">${ico('i-clock')} شارژ خودکار · تنظیم نمایشی، خاموش</span>`:''}
        <span class="nptag">${ico('i-chart')} سقف ${money(cap)}</span>
        ${debt?`<span class="nptag stop">${ico('i-clock')} بدهی ${money(debt)}</span>`:''}
      </span>
      ${payBars()}
      <span class="npmeter"><i style="width:${pct}%"></i></span>
      <span class="npnote">${faN(pct)}٪ فقط شاخص نمایشی · ${faN(n)} ردیف نمونه، بدون تراکنش واقعی</span>
    </div>
    <div class="npacts">
      <button class="npact" type="button" data-topup><span class="ic">${ico('i-plus')}</span><b>پیش‌نمایش شارژ</b></button>
      <button class="npact" type="button" data-linkgo><span class="ic">${ico('i-link')}</span><b>کد پرداخت نمونه</b></button>
      <button class="npact" type="button" data-debtpay><span class="ic">${ico('i-clock')}</span><b>${debt?'تسویهٔ نمونه · غیرفعال':'بدهی نمونه · صفر'}</b></button>
      <button class="npact" type="button" data-paytx><span class="ic">${ico('i-refresh')}</span><b>ردیف‌های نمونه</b></button>
    </div></div>`;
}
/* ── بدهی و قفل گواهینامه ─────────────────────────────────────────── */
function debtBox(){
  const d=PAYINFO.debt||{}, amt=debtAmt();
  if(!amt)
    return `<div class="payclear npalert anim">${ico('i-info')}<span class="tx"><b>بدهی واقعی در این پیش‌نمایش ثبت نمی‌شود</b>
      <small>این نمونه بدهی، قفل گواهی یا پرداخت سروری را بررسی نمی‌کند.</small></span></div>`;
  return `<div class="paydebt npalert anim">${ico('i-lock')}<span class="tx">
      <b>${money(amt)} بدهی داری</b>
      <small>${esc(d.t||'')}${d.due?' · مهلت '+esc(d.due):''}${d.plan?' · '+esc(d.plan):''}</small>
      <span class="cap">${esc(d.lock||'تا تسویهٔ بدهی، گواهینامه قابل دانلود نیست.')}</span></span>
    <button class="btn sm primary" data-debtpay>پرداخت بدهی</button></div>`;
}
/* ── روش‌های پرداخت غیرفعال: جزئیات کوتاه، بدون کیف پول یا اقدام ──── */
function methodTile(m){
  const detail=m.rule?`<small class="paym-rule">${esc(m.rule)}</small>`:'';
  return `<button class="paym off" type="button" data-paym="${esc(m.k)}" disabled aria-disabled="true">
    <span class="pm-ic">${ico(m.i||'i-card')}</span>
    <span class="tx"><b>${esc(m.n)}</b><small>${esc(m.s)}</small>${detail}</span>
    <span class="pm-go" aria-hidden="true">${ico('i-chev-left')}</span></button>`;
}
function methodsBox(){
  const methods=PAYM.filter(m=>m&&m.k!=='wallet');
  return `<div class="payms">${methods.map(methodTile).join('')}</div>
    <p class="npfoot">درگاه بله، کارت‌به‌کارت و روش‌های دیگر در این صفحه به پرداخت یا تأیید واقعی وصل نیستند.</p>`;
}
/* ── صورت‌حساب‌ها: صافی کوتاه و ردیف‌های جمع‌وجور ───────────────────── */
function invFilterBar(){
  const inv=PAYINFO.invoices||[];
  const count=k=>inv.filter(v=>k==='all'||invState(v)===k).length;
  const F=[['all','همه'],['paid','پرداخت‌شده'],['open','در انتظار'],['partial','نیمه‌پرداخت'],['refunded','برگشت وجه']];
  return `<div class="npfilters">${F.map(([k,n])=>`<button class="tag${(S.invF||'all')===k?' on':''}"
      type="button" data-invf="${k}">${esc(n)} <b class="num">${faN(count(k))}</b></button>`).join('')}</div>`;
}
function paymentMethodName(key){
  if(!key||key==='wallet')return '';
  const method=PAYM.find(item=>item.k===key);
  return method&&method.n?method.n:String(key);
}
function invRow(v){
  const st=invState(v), dow=v.paid<v.amount&&v.amount>0,methodName=paymentMethodName(v.method);
  const status=PAYINFO.demo?'دادهٔ نمونه · پرداخت واقعی نشده':invStateTxt(st);
  return `<div class="ivrow st-${esc(PAYINFO.demo?'brand':invTone(st))}">
    <span class="iv-ic">${ico(v.amount?'i-doc':'i-star')}</span>
    <span class="tx"><b>${esc(v.t)}</b>
      <small>${esc(v.at)} · دادهٔ محلی${dow?' · مبلغ پرداخت‌شدهٔ نمونه '+money(v.paid||0):''}</small>
      ${methodName?`<small>روش نمونه: ${esc(methodName)}</small>`:''}
      ${v.due?`<small>سررسید نمونه: ${esc(v.due)}</small>`:''}
      ${v.track&&v.track!=='—'?`<small class="cap">شناسهٔ نمایشی <b class="num">${esc(v.track)}</b></small>`:''}</span>
    <span class="iv-end"><b class="num">${v.amount?money(v.amount)+' · نمونه':'رایگان · نمونه'}</b>${chip(status,'warn')}
      ${PAYINFO.demo?'':(st==='paid'&&v.amount>0?`<button class="btn sm quiet" data-refund="${esc(v.id)}">برگشت</button>`
        :(st==='paid'||st==='refunded'?'':`<button class="btn sm primary" data-invpay="${esc(v.id)}">پرداخت</button>`))}</span></div>`;
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
function safeSampleTransactions(){
  return (PAYINFO.txs||[]).filter(item=>item&&item.k!=='top'&&item.by!=='wallet'
    &&!/[کك]یف\s*پول|شارژ/u.test(String(item.t||'')));
}
function txBox(){
  const all=payState().txs.concat(safeSampleTransactions());
  const list=(S.txAll?all:all.slice(0,4));
  return list.length?list.map(txRow).join('')+
    (all.length>4&&!S.txAll?`<button class="npmore" type="button" data-paytx>${ico('i-plus')} همهٔ ${faN(all.length)} تراکنش</button>`:'')
    :empty2('تراکنشی نیست','در این پیش‌نمایش تراکنش مالی نمایش داده نمی‌شود.');
}
/* ── خلاصهٔ این ماه: سه عدد گرافیکی ────────────────────────────────── */
function payStats(){
  const st=payState(), inv=PAYINFO.invoices||[];
  const spent=inv.reduce((a,v)=>a+(+v.paid||0),0), left=inv.reduce((a,v)=>a+Math.max(0,(+v.amount||0)-(+v.paid||0)),0);
  return `<div class="npstats">
    <span><b class="num">${money(spent)}</b><small>جمع نمونهٔ پرداخت‌شده · پرداخت واقعی نیست</small></span>
    <span><b class="num">${money(left)}</b><small>ماندهٔ نمونه · بدهی واقعی نیست</small></span>
    <span><b class="num">${faN(+A.points||0)}</b><small>امتیاز نمونهٔ محلی</small></span></div>`;
}
/* ── ورقه‌ها: پرداخت، شارژ، برگشت و لینک ─────────────────────────── */
function payTrace(){
  return `<div class="trace">${[['i-doc','فاکتور نورا پی'],['i-check','تأیید پرداخت'],['i-medal','رسید و کد رهگیری']]
    .map(([i,t])=>`<span class="tr">${ico(i)}${esc(t)}</span>`).join('<i class="tr-line"></i>')}</div>`;
}
function methodSheet(k,ctx){
  ctx=Object.assign({},ctx||{});
  const m=methodOf(k,ctx.amount); if(!m||!m.on) return;
  if(ctx.payDebt&&k!=='card'&&k!=='bale'){toast('تسویهٔ بدهی فقط با کارت‌به‌کارت یا درگاه پرداخت انجام می‌شود'); return}
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
    const c=m; ctx.cardId=c.cardId; S.payReceipt=null;
    body=`<p class="sub" style="margin-top:8px">مبلغ را فقط به کارتِ همین نوبت واریز کن. شمارهٔ مقصد از استخر مدیر انتخاب شده؛ بعد از ارسال، فیش باید دستی تأیید شود.
      ${ctx.payDebt?'این روش برای تسویهٔ بدهی است و مبلغ کامل بدهی را نشان می‌دهد.':''}</p>
      <div class="stack tight">
        <div class="srow">${ico('i-card')}<span class="sp">شمارهٔ کارت<b class="num" dir="ltr">${esc(c.no||'')}</b></span>
          <button class="btn sm quiet" data-copy="${esc(c.no||'')}" data-copy-msg="شمارهٔ کارت رونوشت شد">رونوشت</button></div>
        <div class="srow">${ico('i-users')}<span class="sp">به نام<small>${esc(c.bank||'')} · ${esc(c.name||'')}</small></span></div>
      </div>
      <label class="fld" style="margin-top:10px"><span>کد پیگیری بانکی</span><input class="input" id="rcTrack" dir="ltr" autocomplete="off" placeholder="اگر فایل رسید نداری، کد را بنویس"/></label>
      <p class="cap">فایل رسید تا ۱۰۰ کیلوبایت در همین مرورگر می‌ماند؛ فایل بزرگ‌تر را این نسخه بارگذاری نمی‌کند. هیچ‌کدام جای تأیید بانکی را نمی‌گیرد.</p>`;
    act=`<label class="btn quiet" for="rcFile">${ico('i-image')} انتخاب رسید</label>
      <input id="rcFile" type="file" accept="image/*,application/pdf" hidden/>
      <button class="btn primary" data-paynow="card">ارسال برای تأیید</button>`;
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
    body=`<p class="sub" style="margin-top:8px">نصف الان، نصف دوم تا پنجم ماه آینده.</p>
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
    <p class="cap" style="margin-top:10px">اطلاعات این نمونه در مرورگر است؛ این صفحه جای درگاه امن یا رسید بانکی معتبر را نمی‌گیرد.</p>`);
  S.payCtx=ctx;
  openSheet('shPay');
}
function chooseSheet(eid,ctx){
  ctx=ctx||{};
  const amount=Math.max(0,+ctx.amount||0);
  const keys=(ctx.payDebt?['card','bale']:modelsOf(eid)).filter(k=>methodOf(k,amount).on);
  const e=(EVENTS.find(x=>x.id===eid)||PAST.find(x=>x.id===eid)||{});
  S.payCtx=Object.assign({},ctx,{eid:eid});
  const choices=keys.length?`<div class="stack tight" style="margin-top:10px">${keys.map(k=>{const m=methodOf(k,amount);
      return `<button class="opt" data-paym="${esc(k)}" data-in-choose="1">
        <span class="mk">${ico(m.i||'i-wallet','width:16px')}</span>
        <span style="flex:1;text-align:start"><b>${esc(m.n)}</b><br><span class="cap">${esc(m.s)}</span></span>
        ${ico('i-chev-left','color:var(--ink-4)')}</button>`}).join('')}</div>`:
      `<div class="paywarn" style="margin-top:12px">${ico('i-info')}<span>فعلاً کارتِ فعال یا درگاهِ متصل نداریم؛ در این نسخه تسویهٔ واقعی ممکن نیست. از کیف پول، امتیاز یا پرداخت حضوری برای بدهی استفاده نمی‌شود.</span></div>`;
  fillSheet('shChoose',`<div class="grabber"></div>
    <div class="head">${ico('i-wallet')} ${ctx.payDebt?'روش تسویهٔ بدهی':'مدل پرداخت این رویداد'}</div>
    <p class="cap" style="margin-top:5px">${e.t?esc(e.t)+' · ':''}${ctx.payDebt?'تسویهٔ بدهی فقط با کارت‌به‌کارت یا درگاه پرداخت ممکن است.':'مدیر یا سازندهٔ رویداد روش‌های مجاز را انتخاب کرده.'}</p>
    ${choices}
    <div class="row" style="margin-top:12px"><span class="sp" style="flex:1"></span>
      <button class="btn quiet" data-close>بستن</button></div>`);
  openSheet('shChoose');
}
function topSheet(){
  const w=walletConfig(), tiles=w.topTiles||[200000,500000,1000000,2000000];
  fillSheet('shTop',`<div class="grabber"></div>
    <div class="head">${ico('i-plus')} شارژ کیف پول نورا پی</div>
    <p class="cap" style="margin-top:5px">درگاه پرداخت در این نسخه وصل نیست؛ این فرم موجودی را زیاد نمی‌کند. محدودهٔ تنظیم‌شده: کف ${money(w.topMin||0)} و سقف ${money(w.topMax||0)}.</p>
    <div class="chipsline" style="margin-top:12px">${tiles.map(t=>
      `<button class="tag ${t===tiles[1]?'on':''}" type="button" data-topamt="${faN(t)}">${money(t)}</button>`).join('')}</div>
    <label class="lbl" for="topAmt" style="margin-top:12px;display:block">یا مبلغ دلخواه</label>
    <input class="input num" id="topAmt" inputmode="numeric" placeholder="مثلاً ۳۰۰۰۰۰" style="margin-top:6px"/>
    ${payTrace()}
    <div class="row" style="margin-top:14px"><button class="btn primary" data-topgo disabled aria-disabled="true">${ico('i-shield')} درگاه هنوز راه‌اندازی نشده</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" data-close>بعداً</button></div>`);
  S.topAmt=(tiles[1]||0);
  openSheet('shTop');
}
function refundSheet(id){
  if(PAYINFO.demo){toast('بازپرداخت واقعی در این پیش‌نمایش وجود ندارد'); return}
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
/* مسیرهای پرداخت و ارسال رسید در این پیش‌نمایش عمداً غیرفعال‌اند. */
function submitCardReceipt(){
  toast('ارسال رسید و بازبینی بانکی وصل نیست؛ هیچ رسیدی برای مدیر ثبت یا ارسال نشد');
  return false;
}
function doPay(){
  toast('درگاه و پرداخت واقعی وصل نیست؛ هیچ مبلغ، بدهی یا گواهی‌ای تغییر نکرد');
  return false;
}
function topup(){
  toast('شارژ واقعی تا اتصال امن درگاه و سرور فعال نیست؛ موجودی نمونه تغییر نکرد.');
}
function refundDo(){
  toast('درخواست بازپرداخت واقعی ثبت یا به کارشناس مالی ارسال نشد');
  return false;
}
function linkGo(){
  const l=PAYINFO.link||{}, v=String(($('#lkCode')||{}).value||'').trim().toUpperCase();
  if(!v||v!==String(l.demo||'').toUpperCase()){ toast(l.bad||'این لینک پرداخت پیدا نشد'); return }
  toast('این کد لینک نمونه است؛ صفحهٔ پرداخت واقعی هنوز راه‌اندازی نشده.');
}
/* ── داشبورد نورا پی ───────────────────────────────────────────────── */
/* نما: مهمان درگاه ورود را می‌بیند، عضو داشبورد کامل را */
VS.pay=function(t){
  if(!TEST_FIXTURE_MODE) return serverAccountRegistrationsView(t,'payments');
  if(!login()) return viewHead(t,'',null)+gate(t);
  return viewHead(t)+payPanel();
};
function installmentCard({event,payment}){
  const firstState=payment.firstPaid?'پرداخت‌شده':'پرداخت‌نشده';
  const secondState=payment.secondPaid?'پرداخت‌شده':payment.dueLabel+' به حساب نورا';
  return `<article class="installment-card">
    <header class="installment-card-head">
      <span class="installment-brand">${ico('i-split')} پرداخت دو مرحله‌ای نورا</span>
      <b class="installment-card-title">${esc(event.t)}</b>
      <span class="installment-total-label">جمع کل</span>
      <strong class="installment-total num">${money(payment.total)}</strong>
    </header>
    <div class="installment-steps">
      <div class="installment-step${payment.firstPaid?' done':' current'}">
        <span class="installment-step-index">${payment.firstPaid?ico('i-check'):faN(1)}</span>
        <span class="installment-step-copy"><b>نصف الان</b><small>${esc(firstState)}</small></span>
        <strong class="num">${money(payment.first)}</strong>
      </div>
      <div class="installment-step${payment.secondPaid?' done':''}">
        <span class="installment-step-index">${payment.secondPaid?ico('i-check'):faN(2)}</span>
        <span class="installment-step-copy"><b>نصف دوم</b><small>${esc(secondState)}</small></span>
        <strong class="num">${money(payment.second)}</strong>
      </div>
    </div>
    <div class="installment-preview-note">${ico('i-info')} فقط پیش‌نمایش؛ درگاه یا پرداخت بانکی وصل نیست و مبلغی کم نمی‌شود.</div>
    <button class="btn quiet block" type="button" disabled aria-disabled="true">${ico('i-lock')} پرداخت واقعی در دسترس نیست</button>
  </article>`;
}
function payPanel(){
  const plans=outstandingInstallments(),invoices=PAYINFO.invoices||[],transactions=safeSampleTransactions();
  const planBody=plans.length?plans.map(installmentCard).join(''):
    empty2('قسطِ باز نداری','برنامهٔ دو مرحله‌ای برای فرم‌های هزینه‌دار نمایش داده می‌شود.','i-check');
  return `<div class="installment-page payment-details-page">
      <div class="installment-page-intro">
        <span class="installment-page-icon">${ico('i-split')}</span>
        <span><b>نصف الان، نصف تا پنجم ماه بعد</b><small>کیف پول و شارژ در دسترس نیست</small></span>
      </div>
      <section class="payment-account-section" aria-labelledby="accountInstallmentsTitle">
        <div class="payment-account-section-head"><span class="payment-account-section-icon">${ico('i-clock')}</span>
          <b id="accountInstallmentsTitle">اقساط و برنامهٔ پرداخت</b></div>
        <div class="installment-page-list">${planBody}</div>
      </section>
      <section class="payment-account-section" aria-labelledby="accountPaymentMethodsTitle">
        <div class="payment-account-section-head"><span class="payment-account-section-icon">${ico('i-card')}</span>
          <b id="accountPaymentMethodsTitle">روش‌های پرداخت</b></div>
        ${methodsBox()}
      </section>
      <details class="npmore2 pay-account-disclosure">
        <summary>${ico('i-doc')} صورت‌حساب‌ها · ${faN(invoices.length)} مورد نمونه</summary>
        <div class="pay-account-disclosure-body">${invoicesBox()}</div>
      </details>
      <details class="npmore2 pay-account-disclosure">
        <summary>${ico('i-refresh')} تراکنش‌ها · ${faN(transactions.length)} ردیف نمونه</summary>
        <div class="pay-account-disclosure-body">${txBox()}</div>
      </details>
      <details class="npmore2 pay-account-disclosure">
        <summary>${ico('i-chart')} وضعیت مالی · دادهٔ نمونه</summary>
        <div class="pay-account-disclosure-body">${debtBox()}${payStats()}</div>
      </details>
      ${trustLine('pay')}
    </div>`;
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
  p.status='local';                          /* ذخیرهٔ مرورگر تأیید مالک یا بررسی هویت نیست */
  p.history=(p.history||[]).filter(h=>h.k!=='filled').concat([{k:'filled',at:nowFa()}]);
  if(UI().saveProfile) UI().saveProfile(p);
  S.edit=false; render();
  toast('فقط در همین مرورگر ذخیره شد؛ بررسی یا تأیید واقعی انجام نشد');
}
function nowFa(){
  try{ return new Intl.DateTimeFormat('fa-IR-u-ca-persian',{day:'numeric',month:'long'}).format(new Date()) }
  catch(e){ return 'امروز' }
}
function askDelete(){
  fillSheet('shConfirm',`<div class="grabber"></div><div class="head">حذف حساب کاربری</div>
    <p class="sub" style="margin-top:8px">این فقط یک آزمایش محلی است: حساب واقعی، بلیت، گواهی یا سابقه‌ای پاک نمی‌شود و درخواستی هم به کارشناس نمی‌رسد.</p>
    <label class="lbl" for="delWord" style="margin-top:12px;display:block">کلمهٔ تأیید</label>
    <input class="input" id="delWord" placeholder="حذف" autocomplete="off" style="margin-top:6px"/>
    <label class="lbl" for="delCode" style="margin-top:10px;display:block">کد ثابت نمایشی (بدون پیامک)</label>
    <input class="input num" id="delCode" inputmode="numeric" maxlength="5" placeholder="کد ۵ رقمی" style="margin-top:6px"/>
    <div class="cap" style="margin-top:6px">کد ثابت: ۵۴۳۲۱؛ درخواست و حذف واقعی به سرور وصل نیست.</div>
    <div class="row" style="margin-top:14px"><button class="btn stop" id="delYes">ثبت درخواست نمایشی</button>
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
  toast('خروجی نمونهٔ محلی آماده شد؛ پروندهٔ رسمی یا سروری نیست');
}
const certReqOf=id=>{
  if(issuedForEvent(id)) return false;
  try{
    return (UI().ownerApprovals?UI().ownerApprovals():[]).some(x=>{
      if(!x||!['cert-request','cert-batch'].includes(x.type)||x.status!=='pending') return false;
      const recipients=Array.isArray(x.recipients)?x.recipients:(x.recipient?[x.recipient]:[]), e=eventRecord(id);
      return recipients.some(r=>{
        if(!r||!certBelongsToCurrentUser(r))return false;
        const ref=String(r.eventId||x.eventId||'');
        return ref===String(id)||certMatchesEvent({eventTitle:r.eventTitle||x.eventTitle,title:r.title||x.title},id,e);
      });
    });
  }catch(e){return false}
};

/* ══ رندر ════════════════════════════════════════════════════════════ */
function accScreen(k){ const i=Number(String(k).slice(4)); return ACCOUNT_SCREENS[i]||null }
function accScreenView(t){
  if(t.k==='acc-0') return serverAccountInfoView(t);
  const x=accScreen(t.k)||{}, st=ACCOUNT_SCREEN_STATUS[x.st];
  if(x.st==='bot'){
    const a=SERVER_ACCOUNT_STATE.account||{};
    const bot=a.delivery_bot_url&&/^https:\/\//.test(a.delivery_bot_url)?`<a class="btn primary" href="${esc(a.delivery_bot_url)}" target="_blank" rel="noopener">${ico('i-send')} باز کردن ربات بله</a>`:'';
    return viewHead(t,'',null)+(SERVER_ACCOUNT_STATE.account?serverAccountStrip():'')+card(x.n,st.note,'i-send',
      `<p><span class="${st.cls}">${esc(st.tag)}</span></p><p class="cap">در وب هیچ دادهٔ محلی یا نمونه‌ای برای این بخش نمایش داده نمی‌شود؛ وقتی سرویس مشترک آن در وب فراهم شود، همین‌جا فعال خواهد شد.</p>
       <div class="row" style="flex-wrap:wrap">${bot}<a class="btn quiet" href="account.html">بازگشت به حساب من</a></div>`);
  }
  if(x.st==='later') return viewHead(t,'',null)+card(x.n,st.note,'i-info',
    `<p><span class="${st.cls}">${esc(st.tag)}</span></p><p class="cap">تصمیم محصول دربارهٔ این بخش هنوز گرفته نشده است؛ هیچ موجودی، اعتبار یا تراکنشی در وب نمایش داده یا ساخته نمی‌شود.</p>
     <a class="btn quiet" href="account.html">بازگشت به حساب من</a>`);
  return serverAccountFeatureView(t,t.n,'این بخش به سرویس واقعی حساب وصل نشده است؛ داده‌ی نمونه نمایش داده نمی‌شود.');
}
/* اطلاعات حساب: فقط آنچه /api/account/me می‌دهد (نوع ورود، نقش، بات تحویل). نام و موبایل در API نیست و نمایش داده نمی‌شود. */
function serverAccountInfoView(t){
  const state=SERVER_ACCOUNT_STATE;
  if(state.checking) return viewHead(t,'',null)+serverAccountAccessCard();
  if(!state.account) return viewHead(t,'',null)+serverAccountAccessCard('notifications');
  const a=state.account;
  const providerLabel=a.provider==='manager-password'?'ورود مدیر با نام کاربری':a.provider==='phone'?'ورود با شمارهٔ موبایل':'حساب بله';
  const bot=a.delivery_bot_url&&/^https:\/\//.test(a.delivery_bot_url)?`<a class="btn quiet" href="${esc(a.delivery_bot_url)}" target="_blank" rel="noopener">باز کردن بات تحویل</a>`:'';
  return viewHead(t,'',null)+card('اطلاعات حساب','نوع ورود و دسترسی‌های این حساب از سرور خوانده شده است.','i-idcard',
    `<div class="stack">
       <div class="srow"><span class="sp"><b>نوع ورود</b><small class="cap">${esc(providerLabel)}</small></span></div>
       <div class="srow"><span class="sp"><b>دسترسی‌ها</b><small class="cap">${esc(faN((a.permissions||[]).length))} مورد</small></span></div>
     </div>
     <p class="cap">نام، شمارهٔ موبایل و ویرایش اطلاعات در API حساب وب موجود نیست.</p>
     <div class="row" style="flex-wrap:wrap">${bot}<a class="btn quiet" href="account.html">بازگشت به حساب من</a></div>`);
}
function serverAccountProfileView(t){
  const state=SERVER_ACCOUNT_STATE;
  if(state.checking) return viewHead(t,'',null)+serverAccountAccessCard();
  if(!state.account) return viewHead(t,'',null)+serverAccountAccessCard('profile');
  const a=state.account, name=serverAccountDisplayName();
  return viewHead(t,'اطلاعات حساب وب و پیوند هویت از سرور',null)+card('اطلاعات من','آنچه سرور دربارهٔ این حساب تأیید کرده است.','i-idcard',
    `<div class="stack">
       <div class="srow"><span class="sp"><b>نام</b><small class="cap">${esc(name||'هنوز در پروفایل حساب ثبت نشده است')}</small></span></div>
       <div class="srow"><span class="sp"><b>نوع ورود</b><small class="cap">${esc(serverAccountProviderLabel(a))}</small></span></div>
       <div class="srow"><span class="sp"><b>دسترسی‌ها</b><small class="cap">${esc(faN((a.permissions||[]).length))} مورد</small></span></div>
     </div>
     <p class="cap">شمارهٔ موبایل و کد یک‌بارمصرف هیچ‌وقت در مرورگر ذخیره نمی‌شوند؛ ویرایش اطلاعات تکمیلی پروفایل در نسخهٔ اول وب فعال نیست.</p>`)
    +serverAccountIdentitiesCard();
}
function serverBookClubView(t){
  const state=SERVER_ACCOUNT_STATE, a=state.account||{};
  const bot=a.delivery_bot_url&&/^https:\/\//.test(a.delivery_bot_url)?`<a class="btn sm tint" href="${esc(a.delivery_bot_url)}" target="_blank" rel="noopener">${ico('i-send')} باشگاه من در ربات بله</a>`:'';
  return viewHead(t,'کتاب ماه، جلسه‌ها و تازه‌های باشگاه',null)+`<div class="club server-club">
    <div class="cl-hero" style="--g:linear-gradient(135deg,#2E6B7A,#0B2447)">
      <div class="btop" style="position:static;display:flex;gap:6px"><span class="tagg tag-g">باشگاه کتاب‌خوانی خط زندگی</span></div>
      <div class="bk"><span class="cv">${ico('i-book')}</span>
        <span style="min-width:0"><h3>کتاب ماه هنوز منتشر نشده است</h3>
          <div class="hrow" style="color:rgba(255,255,255,.9)">کتاب ماه، زمان جلسه و سرپرست باشگاه از پنل مدیریت منتشر می‌شوند و همین‌جا نمایش داده خواهند شد.</div></span></div>
    </div>
    <div class="cl-body">
      <div class="stack tight">
        <div class="memberline">${ico('i-clock')}<span class="sp" style="flex:1">زمان جلسهٔ بعدی پس از انتشار از پنل اعلام می‌شود.</span></div>
        <div class="memberline">${ico('i-book')}<span style="flex:1">تازه‌های منتشرشدهٔ باشگاه (کتاب، صدا، مسابقه) در صفحهٔ خانه، بخش باشگاه، در دسترس است.</span></div>
        <div class="memberline">${ico('i-users')}<span style="flex:1">عضویت، امتیاز و «باشگاه من» فعلاً در ربات بله انجام می‌شود؛ در وب موجودی یا امتیاز نمونه نشان داده نمی‌شود.</span></div>
      </div>
      <div class="row" style="flex-wrap:wrap">
        <a class="btn primary" href="home.html#club">${ico('i-book')} تازه‌های باشگاه</a>${bot}
        <span class="tag">فعلاً در ربات بله</span>
      </div>
    </div>
  </div>`;
}
function viewOf(k){ if(String(k||'').indexOf('acc-')===0) return accScreen(k)?accScreenView:null;
  if(ACCOUNT_REGISTRATION_VIEWS[k]) return t=>serverAccountRegistrationsView(t,k);
  if(k==='library') return serverAccountLibraryView;
  return k==='events'?VS.events : k==='profile'?VS.profile
  : k==='pay'?VS.pay : k==='book'?VS.book : k==='server-data'?serverAccountDataView : null }
/* نشانی‌های کوتاه، همان تب پروفایل را باز می‌کنند */
const ALIAS={info:['profile','ptab','info'], account:['profile','ptab','info'],
  auth:['profile','ptab','auth'], login:['profile','ptab','auth'],
  forms:['profile','ptab','forms'], privacy:['profile','ptab','privacy'],
  club:['profile','ptab','club'], points:['profile','ptab','club'], points2:['profile','ptab','club'],
  invite:['profile','ptab','invite'], invite2:['profile','ptab','invite']};
function renderView(){
  const box=$('#viewBox'), t=S.view==='profile'?PROFILE_VIEW:S.view==='server-data'?SERVER_DATA_VIEW:S.view==='library'?ACCOUNT_LIBRARY_VIEW:ACCOUNT_REGISTRATION_VIEWS[S.view]||(String(S.view).indexOf('acc-')===0?accScreenTitle(S.view):SECT.find(s=>s.k===S.view)), fn=viewOf(S.view);
  if(!box||!t||!fn) return;
  box.innerHTML=`<section class="sec" aria-label="${esc(t.n)}">${fn(t)}</section>`;
  document.title='نورا · '+t.n;
}
function accScreenTitle(k){ const x=accScreen(k); return x?{k,n:x.n,s:''}:null }
function render(){
  renderProfile();
  const prof=$('#profBox'), box=$('#viewBox'), ok=!!viewOf(S.view), sb=$('#supBar');
  if(sb) sb.hidden=!supportVisible();          /* پشتیبانی می‌چسبد به نوار پایین */
  if(!ok){ S.view=''; if(box){ box.hidden=true; box.innerHTML='' }
    if(prof) prof.hidden=false; document.title='نورا · حساب من' }
  else { if(prof) prof.hidden=true; box.hidden=false; renderView() }
}
function route(){
  let raw=(location.hash||'').replace('#','');
  if(raw==='pay'&&!TEST_FIXTURE_MODE) raw='payments';      /* #pay قدیمی در نسخهٔ سروری همان پرداخت‌های واقعی است */
  if(raw.indexOf('acc-')===0 && accScreen(raw)){ S.view=raw; render(); return; }
  if(raw.indexOf('fill=')===0){                       /* نشانی فرمی که سرپرست فرستاده */
    const id=raw.slice(5); S.view='book'; S.ctab='home'; render();
    const f=cfOf(id);
    if(!f.k) toast('این فرم را پیدا نکردم');
    else if(!clubIsMember()) toast('اول عضویت باشگاه را کامل کن؛ بعد فرم را پر کن');
    else { fillSheet('shClubFill',clubFill(id)); openSheet('shClubFill') }
    try{window.scrollTo({top:0})}catch(e){}; return }
  if(raw.indexOf('invite=')===0){
    S.view='profile'; S.ptab='invite'; render(); try{window.scrollTo({top:0})}catch(e){}
    toast('این پیوند فقط نمونه است؛ ثبت‌نام، دعوت، امتیاز یا ارسال بیرونی انجام نمی‌شود');
    return }
  if(raw==='events'||ACCOUNT_REGISTRATION_VIEWS[raw]){
    S.view=raw; S.edit=false; S.errs={}; render();
    if(SERVER_ACCOUNT_STATE.account) loadAccountRegistrations();
    if(raw==='events'&&SERVER_ACCOUNT_STATE.account&&!TEST_FIXTURE_MODE) loadAccountLibrary();
    if(raw==='payments'&&SERVER_ACCOUNT_STATE.account&&!TEST_FIXTURE_MODE) loadAccountRecordingOrders();
    try{window.scrollTo({top:0})}catch(e){}; return;
  }
  if(raw==='library'){
    S.view='library'; S.edit=false; S.errs={}; render();
    if(SERVER_ACCOUNT_STATE.account){loadAccountLibrary();loadAccountCertificates();}
    try{window.scrollTo({top:0})}catch(e){}; return;
  }
  if(raw==='notifications'||raw==='my-files'||raw==='account-data'){
    S.view='server-data'; S.serverdata=raw==='my-files'?'files':'notifications'; render();
    try{window.scrollTo({top:0})}catch(e){};
    if(SERVER_ACCOUNT_STATE.account){
      if(S.serverdata==='files'&&!SERVER_ACCOUNT_STATE.filesLoaded) loadAccountFiles();
      if(S.serverdata==='notifications'&&!SERVER_ACCOUNT_STATE.notificationsLoaded) loadAccountNotifications();
    }
    return;
  }
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
  const dataOpen=t.closest('[data-server-data-open]'); if(dataOpen){
    const target=dataOpen.dataset.serverDataOpen;
    location.hash=target==='files'?'#my-files':target==='registrations'?'#events':'#notifications'; return }
  const dataTab=t.closest('[data-serverdata]'); if(dataTab){
    S.serverdata=dataTab.dataset.serverdata==='files'?'files':'notifications'; renderView();
    if(S.serverdata==='files'&&!SERVER_ACCOUNT_STATE.filesLoaded) loadAccountFiles();
    if(S.serverdata==='notifications'&&!SERVER_ACCOUNT_STATE.notificationsLoaded) loadAccountNotifications();
    return }
  if(t.closest('[data-server-account-retry]')){checkServerAccount();return}
  if(t.closest('[data-identity-link]')){linkBaleIdentity();return}
  if(t.closest('[data-identity-retry]')){loadAccountIdentities(true);return}
  if(t.closest('[data-identity-unlink]')){IDENTITY_STATE.confirmUnlink=true;renderProfile();return}
  if(t.closest('[data-identity-unlink-cancel]')){IDENTITY_STATE.confirmUnlink=false;renderProfile();return}
  if(t.closest('[data-identity-unlink-confirm]')){unlinkBaleIdentity();return}
  const refreshData=t.closest('[data-account-data-refresh]'); if(refreshData){loadServerAccountData(true);return}
  if(t.closest('[data-account-registrations-refresh]')){loadAccountRegistrations(false,true);return}
  if(t.closest('[data-account-registrations-more]')){loadAccountRegistrations(true,true);return}
  if(t.closest('[data-account-rec-orders-refresh]')){loadAccountRecordingOrders(false,true);return}
  if(t.closest('[data-account-rec-orders-more]')){loadAccountRecordingOrders(true,true);return}
  if(t.closest('[data-account-library-refresh]')){loadAccountLibrary(true);return}
  if(t.closest('[data-account-certs-refresh]')){loadAccountCertificates(true);return}
  const recCancel=t.closest('[data-account-rec-cancel]'); if(recCancel){cancelAccountRecordingOrder(recCancel.dataset.accountRecCancel);return}
  if(t.closest('[data-account-notices-more]')){loadAccountNotifications(true,true);return}
  if(t.closest('[data-account-files-more]')){loadAccountFiles(true,true);return}
  const noticeRead=t.closest('[data-account-notice-read]'); if(noticeRead){
    const id=noticeRead.dataset.accountNoticeRead, api=window.NORA_SERVER_API;
    if(!api||typeof api.markAccountNotificationRead!=='function'){toast('رابط حساب سرور در دسترس نیست');return}
    noticeRead.disabled=true;
    api.markAccountNotificationRead(id,'nora_account_csrf').then(()=>{
      const item=SERVER_ACCOUNT_STATE.notifications.find(x=>x.id===id); if(item)item.read=true;
      renderView(); renderProfile(); toast('اعلان خوانده شد.');
    }).catch(error=>{
      noticeRead.disabled=false;
      if(error&&error.status===401){serverAccountExpired();return}
      toast(error&&error.status===404?'این اعلان پیدا نشد؛ فهرست را تازه کن.':'ثبت وضعیت اعلان انجام نشد؛ اتصال را بررسی کن.');
    }); return }
  const accountLogout=t.closest('[data-server-account-logout]'); if(accountLogout){logoutServerAccount(accountLogout);return}
  if(t.closest('[data-back]')){ try{history.replaceState(null,'',location.pathname)}catch(e){}
    S.view=''; render(); try{window.scrollTo({top:0})}catch(e){}; return }
  const g=t.closest('[data-go]'); if(g){ go(g.dataset.go); return }
  const vw=t.closest('[data-view]');
  if(vw){ const k=vw.dataset.view;
    if(k==='pay'||login()||!TEST_FIXTURE_MODE){ location.hash='#'+k; return }
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
    if(code!=='54321'){ toast('کد ثابت نمایشی را درست بنویس؛ پیامک واقعی وصل نیست'); const e=$('#delCode'); if(e&&e.focus) e.focus(); return }
    const p=Object.assign({},prof(),{askedDelete:true});
    p.history=(p.history||[]).filter(h=>h.k!=='delete').concat([{k:'delete',at:nowFa()}]);
    if(UI().saveProfile) UI().saveProfile(p);
    closeSheets(); render(); toast('درخواست نمایشی فقط در مرورگر ثبت شد؛ نه پیامکی رفت و نه دادهٔ واقعی پاک شد'); return }
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
    bookSet({cstep:'fee'}); render(); toast('پاسخ‌ها فقط محلی ذخیره شد؛ برای سرپرست فرستاده نشد'); return }
  if(t.closest('[data-clubedit]')){ bookSet({cstep:'form'}); render(); return }
  if(t.closest('[data-clubsend2]')){ clubFeeSheet(); return }
  const cbm=t.closest('[data-clubm]');
  if(cbm){toast('پرداخت و فعال‌سازی عضویت باشگاه به سامانه وصل نیست؛ هیچ تغییری انجام نشد'); return}
  if(t.closest('[data-clubpay]')){ clubFeeSheet(); return }
  const ca=t.closest('[data-att]');
  if(ca){ const att=Object.assign({},bookState().att); att[ca.dataset.att]=ca.dataset.attst;
    bookSet({att:att, sessions:(+bookState().sessions||0)+(ca.dataset.attst==='نمی‌آیم'?0:1)});
    renderView(); toast('وضعیت حضور نمونه فقط در مرورگر ذخیره شد؛ کارنامه یا گزارش واقعی تغییر نکرد'); return }
  const cch=t.closest('[data-chal]');
  if(cch){ const ch=(CCLUB.challenges||[]).find(x=>x.k===cch.dataset.chal)||{};
    const chals=Object.assign({},bookState().chals);
    chals[cch.dataset.chal]=Math.min(ch.goal,(+chals[cch.dataset.chal]||0)+1);
    bookSet({chals:chals}); renderView();
    toast(chals[cch.dataset.chal]>=ch.goal?'چالش را تمام کردی · '+faN(ch.reward||0)+' امتیاز گرفتی':'یک گام جلوتر رفت؛ ادامه بده'); return }
  const con=t.closest('[data-contest]');
  if(con){ const entered=Object.assign({},bookState().entered); entered[con.dataset.contest]=true;
    bookSet({entered:entered}); renderView(); toast('وضعیت مسابقه فقط در همین مرورگر ذخیره شد؛ پیام یا پیگیری واقعی نیست'); return }
  const cw=t.closest('[data-clubw]');
  if(cw){ const w=(CCLUB.workshops||[]).find(x=>x.k===cw.dataset.clubw)||{};
    const seats=Object.assign({},bookState().seats); seats[cw.dataset.clubw]=true;
    bookSet({seats:seats}); renderView();
    toast('وضعیت علاقه فقط در همین مرورگر ذخیره شد؛ رزرو، پرداخت یا ثبت‌نام واقعی انجام نشد'); return }
  const cvo=t.closest('[data-cvoice]'); if(cvo){ bookSet({voiceRole:cvo.dataset.cvoice}); renderView(); return }
  const csl=t.closest('[data-cslot]'); if(csl){ bookSet({voiceSlot:csl.dataset.cslot}); renderView(); return }
  if(t.closest('[data-cvoice-send]')){
    const bc2=bookState();
    if(!bc2.voiceRole){ toast('یکی از کارها را انتخاب کن'); return }
    bookSet({voice:{role:bc2.voiceRole, slot:bc2.voiceSlot||'', at:nowFa()}}); renderView();
    toast('فرم علاقه‌مندی فقط در همین مرورگر ذخیره شد؛ برای سرپرست یا جلسه پیام نمی‌رود'); return }
  const ctg=t.closest('[data-ctag]'); if(ctg){ bookSet({tag:ctg.dataset.ctag}); renderView(); return }
  if(t.closest('[data-post]')){
    const el=$('#trText'), v=el?String(el.value||'').trim():'';
    if(v.length<8){ toast('کمی بیشتر بنویس؛ یک جمله هم کافی است'); if(el&&el.focus) el.focus(); return }
    const bc3=bookState(), nm=(prof().fullName||'عضو باشگاه');
    const p2={k:'tr'+Date.now(), n:nm, g:String(nm).slice(0,1), tag:bc3.tag||'پیشنهاد', likes:0, at:nowFa(), t:v, mine:true};
    bookSet({posts:[p2].concat(bc3.posts||[]).slice(0,10)}); renderView(); toast('نظرت روی تریبون قرار گرفت'); return }
  const lk=t.closest('[data-like]');
  if(lk){ const likes=Object.assign({},bookState().likes);
    if(likes[lk.dataset.like]) delete likes[lk.dataset.like]; else likes[lk.dataset.like]=true;
    bookSet({likes:likes}); renderView(); return }

  /* ── ابزارهای سرپرست باشگاه ──────────────────────────────────────── */
  if(t.closest('[data-sup-on]')){
    bookSet({sup:true, supStep:'home'}); S.ctab='sup'; render();
    toast('ابزارهای سرپرست روشن شد؛ پنل اعضا دست توست'); return }
  if(t.closest('[data-sup-member]')){ bookSet({supStep:'home'}); S.ctab='home'; render(); return }
  const stl=t.closest('[data-sup-tool]');
  if(stl){ const k=stl.dataset.supTool;
    bookSet({supStep:k}); S.ctab='sup'; render(); try{window.scrollTo({top:0})}catch(e){} return }
  const pk=t.closest('[data-pin-kind]');
  if(pk){ bookSet({pinKind:pk.dataset.pinKind}); renderView(); return }
  if(t.closest('[data-pin-add]')){
    const e=$('#pinName'); if(e){ e.value=''; if(e.focus) e.focus() } return }
  if(t.closest('[data-pin-save]')){
    const v=String(($('#pinName')||{}).value||'').trim();
    if(!v){ toast('متن پین را بنویس'); const e=$('#pinName'); if(e&&e.focus) e.focus(); return }
    const pins=(bookState().pins||[]).slice(0,2);
    bookSet({pins:[{t:v, d:'از طرف سرپرست', kind:bookState().pinKind||'خبر', at:nowFa()}].concat(pins)});
    render(); toast('پین شد؛ بالای پنل اعضا قرار گرفت'); return }
  const pde=t.closest('[data-pin-del]');
  if(pde){ bookSet({pins:(bookState().pins||[]).filter(x=>x.t!==pde.dataset.pinDel)});
    render(); toast('پین برداشته شد'); return }
  const pai=t.closest('[data-pin-add-id]');
  if(pai){ const x=((CTP.items||[])[+pai.dataset.pinAddId])||{};
    const pins=(bookState().pins||[]).slice(0,2);
    if((bookState().pins||[]).some(y=>y.t===x.t)){ toast('این یکی از قبل پین است'); return }
    bookSet({pins:[{t:x.t, d:x.d||'', kind:x.kind||'خبر', at:nowFa()}].concat(pins)});
    render(); toast('پین شد'); return }
  const pnw=t.closest('[data-pin-news]');
  if(pnw){ const n=((CCLUB.news||[])[+pnw.dataset.pinNews])||{};
    const pins=(bookState().pins||[]).slice(0,2);
    bookSet({pins:[{t:n.t, d:n.d||'', kind:'خبر', at:nowFa()}].concat(pins)});
    render(); toast('خبر سرپرست پین شد'); return }
  const ppo=t.closest('[data-pin-post]');
  if(ppo){ const pr=clubPosts().find(x=>x.k===ppo.dataset.pinPost)||{};
    const pins=(bookState().pins||[]).slice(0,2);
    bookSet({pins:[{t:pr.t||'', d:(pr.n||'عضو باشگاه')+' · تریبون آزاد', kind:'خبر', at:nowFa()}].concat(pins)});
    render(); toast('پیشنهاد عضو پین شد'); return }
  const sar=t.closest('[data-send-art]');
  if(sar){ const id=sar.dataset.sendArt, sent=(bookState().sent||[]).slice();
    const at=sent.indexOf(id);
    if(at>=0){ sent.splice(at,1); bookSet({sent:sent}); renderView(); toast('از پنل اعضا برداشته شد'); return }
    sent.push(id); bookSet({sent:sent}); renderView(); toast('در پنل اعضا گذاشته شد'); return }
  const sdl=t.closest('[data-sent-del]');
  if(sdl){ bookSet({sent:(bookState().sent||[]).filter(x=>x!==sdl.dataset.sentDel)});
    render(); toast('برداشته شد'); return }
  const qde=t.closest('[data-qz-del]');
  if(qde){ const k=qde.dataset.qzDel;
    bookSet({qz:(bookState().qz||[]).filter(x=>x.k!==k), qzDel:(bookState().qzDel||[]).concat([k]), qzOn:''});
    render(); toast('آزمون برداشته شد'); return }
  const cfr=t.closest('[data-club-form]');
  if(cfr){ fillSheet('shClubForm',formAnswers(cfr.dataset.clubForm)); openSheet('shClubForm'); return }
  if(t.closest('[data-form-csv]')){ toast('پاسخ‌ها آماده شد؛ فایل برایت می‌آید'); return }
  const ffp=t.closest('[data-ff-pick]');
  if(ffp){ const k=ffp.dataset.ffPick, v=ffp.dataset.ffVal;
    const box=ffp.closest('.fld'); if(box){ box.querySelectorAll('[data-ff-pick]').forEach(b=>{
      const on=b===ffp; b.classList.toggle('on',on); b.setAttribute('aria-pressed',on) });
      const hid=box.querySelector('input[type=hidden]'); if(hid) hid.value=v }
    return }
  const cff=t.closest('[data-cf-fill]');
  if(cff){ fillSheet('shClubFill',clubFill(cff.dataset.cfFill)); openSheet('shClubFill'); return }
  const cfl=t.closest('[data-cf-link]');
  if(cfl){ const f=cfOf(cfl.dataset.cfLink);
    toast('پیوند فرم: '+(f.link||('account.html#fill='+f.k))); return }
  if(t.closest('[data-qz-new]')){
    bookSet({qzDraft:{n:'', min:10, qs:[{k:'q1', l:'', o:['','','',''], a:0}]}});
    render(); toast('آزمون تازه؛ پرسش‌ها را بنویس'); return }
  if(t.closest('[data-qz-cancel]')){ bookSet({qzDraft:null}); render(); return }
  if(t.closest('[data-qq-add]')){ const d=qzDraftSync(); if(!d) return;
    const qs=(d.qs||[]).concat([{k:'q'+(Date.now()%10000), l:'', o:['','','',''], a:0}]).slice(0,8);
    bookSet({qzDraft:Object.assign({},d,{qs:qs})}); render(); return }
  if(t.closest('[data-qq-ready]')){ const d=qzDraftSync(); if(!d) return;
    const src=(CTQ.qFields||[])[0]||{l:'',o:['','','',''],a:0};
    const qs=(d.qs||[]).concat([{k:'q'+(Date.now()%10000), l:src.l, o:src.o.slice(), a:src.a||0}]).slice(0,8);
    bookSet({qzDraft:Object.assign({},d,{qs:qs})}); render(); return }
  const qri=t.closest('[data-qq-right]');
  if(qri){ const d=qzDraftSync(); if(!d) return;
    const qs=(d.qs||[]).map(q=>q.k===qri.dataset.qqRight?Object.assign({},q,{a:+qri.dataset.opt}):q);
    bookSet({qzDraft:Object.assign({},d,{qs:qs})}); render(); return }
  if(t.closest('[data-qz-save]')){
    const d=qzDraftSync(); if(!d) return;
    const name=String(($('#qzName')||{}).value||'').trim();
    if(!name){ toast('نام آزمون را بنویس'); const e=$('#qzName'); if(e&&e.focus) e.focus(); return }
    const min=+unFa(String(($('#qzMin')||{}).value||'10')).replace(/\D/g,'')||10;
    const qs=(d.qs||[]).map(q=>Object.assign({},q,{l:String(q.l||'').trim(),o:(q.o||[]).map(o=>String(o||'').trim())}));
    if(!qs.length||qs.some(q=>!q.l||q.o.some(o=>!o))){ toast('هر پرسش یک متن و چهار گزینه لازم دارد'); return }
    const k='qz'+(Date.now()%100000);
    const q={k:k, n:name, q:faN(qs.length)+' پرسش', min:min, state:'draft', took:0,
      avg:'—', pass:'—', top:'—', by:(prof().fullName||'سرپرست'), qs:qs,
      link:'account.html#book'};
    bookSet({qz:[q].concat(bookState().qz||[]), qzDraft:null});
    render(); toast('آزمون ساخته شد؛ حالا منتشرش کن'); return }
  const qop=t.closest('[data-qz-open]');
  if(qop){ bookSet({qz:(bookState().qz||[]).map(x=>x.k===qop.dataset.qzOpen?Object.assign({},x,{state:'open'}):x)});
    render(); toast('آزمون منتشر شد؛ لینکش را برای اعضا بفرست'); return }
  const qcl=t.closest('[data-qz-close]');
  if(qcl){ bookSet({qz:(bookState().qz||[]).map(x=>x.k===qcl.dataset.qzClose?Object.assign({},x,{state:'closed'}):x)});
    render(); toast('آزمون بسته شد'); return }
  const qrs=t.closest('[data-qz-res]');
  if(qrs){ const k=qrs.dataset.qzRes, on=bookState().qzOn===k;
    bookSet({qzOn:on?'':k}); render(); try{window.scrollTo({top:0})}catch(e){} return }
  if(t.closest('[data-qz-csv]')){ toast('نتیجه‌ها آماده شد؛ فایل برایت می‌آید'); return }
  const qta=t.closest('[data-qz-take]');
  if(qta){ fillSheet('shQuiz',quizSitting(qta.dataset.qzTake)); openSheet('shQuiz'); return }
  const qa=t.closest('[data-qa]');
  if(qa){ const box=qa.closest('.qqopts');
    if(box) box.querySelectorAll('[data-qa]').forEach(b=>{ const on=b===qa;
      b.classList.toggle('on',on); b.setAttribute('aria-pressed',on) });
    return }
  const qsb=t.closest('[data-qz-submit]');
  if(qsb){ const id=qsb.dataset.qzSubmit, q=qzOf(id), qs=quizQs(q);
    const ans={}; let empty=0;
    qs.forEach(x=>{ const on=(document.querySelectorAll('[data-qa="'+x.k+'"]')) ;
      const pick=[...on].find(b=>b.classList.contains('on'));
      if(pick===undefined) empty++; else ans[x.k]=+pick.dataset.qi });
    if(empty){ toast('هر '+faN(qs.length)+' پرسش یک گزینه لازم دارد'); return }
    let right=0; qs.forEach(x=>{ if(+ans[x.k]===+(x.a|0)) right++ });
    const picks=Object.assign({},bookState().picks); picks[id]=right;
    bookSet({picks:picks, quizAns:Object.assign({},bookState().quizAns,{[id]:ans})});
    closeSheets(); render();
    toast('نمرهٔ تو: '+faN(right)+' از '+faN(qs.length)); return }
  const cfs=t.closest('[data-cf-send]');
  if(cfs){ const f=cfOf(cfs.dataset.cfSend), need=(f.fields||[]).filter(x=>x.req);
    const miss=need.find(x=>!String(($('#ff_'+x.k)||{}).value||'').trim());
    if(miss){ toast('«'+miss.l+'» را پر کن'); const e=$('#ff_'+miss.k); if(e&&e.focus) e.focus(); return }
    const ans={}; (f.fields||[]).forEach(x=>{ ans[x.k]=String(($('#ff_'+x.k)||{}).value||'').trim() });
    const fills=Object.assign({},bookState().formFills); fills[f.k]=ans;
    bookSet({formFills:fills}); closeSheets(); render();
    toast('پاسخت فقط در همین مرورگر ذخیره شد؛ برای سرپرست ارسال نشد'); return }
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
  const playMedia=t.closest('[data-my-media-event]');
  if(playMedia){playMyEventMedia(playMedia.dataset.myMediaEvent,playMedia.dataset.myMediaId);return}
  const mediaFilter=t.closest('[data-media-filter]');
  if(mediaFilter){
    const box=mediaFilter.closest('.event-media-section'); if(!box)return;
    box.dataset.mediaFilter=mediaFilter.dataset.mediaFilter||'all';
    box.querySelectorAll('[data-media-filter]').forEach(b=>{const on=b===mediaFilter;b.classList.toggle('on',on);b.setAttribute('aria-pressed',on?'true':'false')});
    filterEventMedia(box);return}
  const cv=t.closest('[data-verify]');
  if(cv){ const ser=cv.dataset.verify||'';
    copyText(ser,()=>{ location.href='home.html#verify' },'سریال رونوشت شد؛ در صفحهٔ استعلام بچسبانش'); return }
  const rw=t.closest('[data-reward]');
  if(rw){ const n=rw.dataset.reward||'';
    bookSet({rewards:Object.assign({},bookState().rewards,{[n]:nowFa()})}); render();
    toast('«'+n+'» فقط به‌عنوان نشان محلی نمونه ذخیره شد؛ کد یا هدیه‌ای در بله ارسال نمی‌شود'); return }
  const cp=t.closest('[data-copy]');
  if(cp){ const msg=cp.dataset.copyMsg||''; copyText(cp.dataset.copy,msg?()=>toast(msg):null); return }
  if(t.closest('[data-invite]')){ toast('دعوت بیرونی در این پیش‌نمایش غیرفعال است؛ هیچ پیامی ارسال نشد'); return }
  const pg=t.closest('[data-ptab-go]');
  if(pg){ S.view='profile'; S.ptab=pg.dataset.ptabGo; location.hash='#profile'; render(); return }
  if(t.closest('[data-relogin]')){ goLogin('account'); return }
  const ed=t.closest('[data-enddev]');
  if(ed){ toast('ورود «'+(ed.closest('.drow')?ed.closest('.drow').querySelector('b').textContent:ed.dataset.enddev)+'» پایان یافت'); return }
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
    if(UI().updateAccountNavigation) UI().updateAccountNavigation();
    render(); toast('حساب نمونه باز شد؛ هر وقت خواستی از «ورود و امنیت» بیرون بیا'); return }
  const fm=t.closest('[data-form]');
  if(fm){ const n=fm.dataset.form||'', st2=fm.dataset.formst||'';
    toast(st2==='draft'?('«'+n+'» فقط در این مرورگر نیمه‌کاره مانده؛ یادآوری واقعی وصل نیست')
      :st2==='approved'?('«'+n+'» وضعیت نمونهٔ محلی دارد؛ خروجی واقعی ساخته نشده')
      :('«'+n+'» وضعیت محلی است؛ برای کارشناس ارسال نشده و پاسخی نمی‌آید')); return }
  if(t.closest('[data-login]')){ S.after=''; loginSheet(); return }
  if(t.closest('[data-close]')){ if(t.closest('#shMyEvent')){S.myEventId=null;S.refreshEventPending=false} closeSheets(); return }
  if(t.closest('[data-open-support]')){ goSupport(); return }
  if(t.closest('#supBar')){ goSupport(); return }
  if(t.closest('[data-menu]')){ if(UI().uiOpen) UI().uiOpen('shMenu'); return }
  /* باشگاه کتاب‌خوانی */
  if(t.closest('[data-pages]')){ const add=+t.closest('[data-pages]').dataset.pages||0;
    const bc=bookState(); bookSet({pages:Math.max(0,Math.min(200,bc.pages+add))}); renderView(); return }
  if(t.closest('[data-seat]')){ bookSet({seat:true}); renderView(); toast('صندلی پنجشنبه رزرو شد'); return }
  if(t.closest('[data-save-note]')){
    const el=$('#bcNote'), v=el?String(el.value||'').trim():'';
    if(v.length<10){ toast('کمی بیشتر بنویس؛ یک جمله هم کافی است'); if(el&&el.focus) el.focus(); return }
    bookSet({note:v}); renderView(); toast('یادداشت فقط در همین مرورگر ذخیره شد؛ برای سرپرست فرستاده نشد'); return }
  const vo=t.closest('[data-vote]'); if(vo){ bookSet({vote:vo.dataset.vote}); renderView(); toast('رأیت ثبت شد'); return }
  const wt=t.closest('[data-watch]'); if(wt){ toast('ضبط «'+wt.dataset.watch+'» در پخش‌کننده باز می‌شود'); return }
});
document.addEventListener('input',e=>{
  const input=e.target&&e.target.closest?e.target.closest('[data-event-media-search]'):null;
  if(input){filterEventMedia(input.closest('.event-media-section'));return}
});
document.addEventListener('change',e=>{
  const el=e.target;
  if(el&&el.id==='rcFile'){
    const f=(el.files||[])[0]; if(!f) return;
    const mime=String(f.type||'').toLowerCase(),name=String(f.name||''),isImage=mime.indexOf('image/')===0||/\.(?:avif|bmp|gif|heic|heif|jpe?g|jxl|png|svg|tiff?|webp)$/i.test(name),
      isPdf=mime==='application/pdf'||/\.pdf$/i.test(name);
    if(!isImage&&!isPdf){toast('فقط عکس یا PDF رسید را انتخاب کن'); return}
    if(isImage){
      const api=UI();
      if(typeof api.imageToWebPDataURL!=='function'){toast('ابزار تبدیل WebP در دسترس نیست؛ رسید ذخیره نشد');return}
      api.imageToWebPDataURL(f,{maxEdge:1600}).then(image=>{
        if(image.outputBytes>100*1024){S.payReceipt={name:image.name,mime:'image/webp',heavy:1,data:''};toast('تصویر به WebP تبدیل شد، اما هنوز از ۱۰۰ کیلوبایت بزرگ‌تر است؛ کد پیگیری بانکی را بنویس');return}
        S.payReceipt={name:image.name,mime:'image/webp',heavy:0,data:image.dataUrl};toast('تصویر رسید به WebP تبدیل و در همین صفحه آماده شد');
      }).catch(error=>toast(api.imageErrorMessage?api.imageErrorMessage(error):'تصویر تبدیل نشد؛ ذخیره نشد'));
      return;
    }
    if(f.size>100*1024){S.payReceipt={name:f.name,heavy:1,data:''}; toast('PDF از ۱۰۰ کیلوبایت بزرگ‌تر است؛ کد پیگیری بانکی را بنویس'); return}
    const fr=new FileReader(); fr.onload=()=>{S.payReceipt={name:f.name,mime:'application/pdf',heavy:0,data:String(fr.result||'')}; toast('PDF رسید در همین صفحه آماده شد')};
    fr.onerror=()=>toast('رسید خوانده نشد؛ دوباره امتحان کن'); fr.readAsDataURL(f); return;
  }
  if(!el||!el.id||el.id.indexOf('f_')!==0) return;
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
window.addEventListener('storage',e=>{
  const ui=UI(), keys=[EVENT_PACK_KEY,ui.ISSUED_CERTS_KEY,ui.OWNER_APPROVAL_KEY].filter(Boolean);
  if(keys.includes(e.key))refreshMyEventFromStorage();
});
window.addEventListener('nora:player-return',e=>refreshMyEventAfterPlayer(e.detail));
window.addEventListener('hashchange',route);
if(window.NORA_PUBLIC_READY&&typeof window.NORA_PUBLIC_READY.then==='function')
  window.NORA_PUBLIC_READY.then(()=>{if(S.view==='server-data')renderView()}).catch(()=>{});

/* ══ بوت ═════════════════════════════════════════════════════════════ */
if(typeof initUI==='function') initUI();
mergeNotes();
updateAccountBanner();
route();
checkServerAccount();
})();
