/* ══════════════════════════════════════════════════════════════════════════
   نورا — حساب من
   ──────────────────────────────────────────────────────────────────────────
   یک صفحه، سه چیز:
     ۱) سرِ پروفایل، شبیه صفحهٔ حساب اپلی‌ها: نام، نشان وضعیت، سطح، امتیاز،
        نوار تکمیل اطلاعات
     ۲) کارت نورا پی با رنگ و نشان خودش (فاز بعد)
     ۳) دو ردیف: رویدادهای من (ثبت‌نام، بلیت و گواهی، کارنامهٔ حضور، نظرها)
        و پروفایل من (اطلاعات، باشگاه و امتیاز، فرم‌ها، حریم خصوصی)

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
const card=(t,s,body)=>`<div class="card acct"><div class="head">${esc(t)}</div>${s?`<div class="cap" style="margin-top:5px">${esc(s)}</div>`:''}${body||''}</div>`;
const note=(t,i)=>`<p class="note"><svg class="i" aria-hidden="true"><use href="#${i||'i-sparkle'}"/></svg><span>${esc(t)}</span></p>`;
const empty2=(t,s,i)=>`<div class="empty2"><svg class="i" aria-hidden="true"><use href="#${i||'i-archive'}"/></svg><b>${esc(t)}</b><span>${esc(s)}</span></div>`;
const stOf=p=>({draft:['تکمیل نشده','warn'],pending:['در صف تأیید','brand'],
  approved:['تأیید شده','ok'],rejected:['رد شده','stop']})[ (p&&p.status)||'draft' ]||['تکمیل نشده','warn'];
const monOf=e=>(e&&e.dm&&MON[e.dm])||'';

/* ── حالت صفحه ───────────────────────────────────────────────────── */
const S={view:'',vtab:'up',ptab:'info',edit:false,errs:{},after:'',ncat:''};

/* ── رفتن به یک بخش: مهمان، ورقهٔ ورود؛ عضو، همان بخش ─────────────── */
function go(k){
  if(k==='support'){ openSupport(); return }
  if(!login()){ S.after=k; loginSheet(); return }
  location.hash='#'+k;
}
function loginSheet(){ if(UI().authSheet) UI().authSheet(()=>{ const k=S.after; S.after=''; render(); if(k) location.hash='#'+k }) }

/* ══ سرِ پروفایل ═════════════════════════════════════════════════════ */
function headGuest(){
  const SUPI=SUP.i||'i-headphone';
  return `<div class="phead guestcard">
      <div class="cover"></div>
      <div class="pbody">
        <div class="ptop">
          <span class="av" style="background:var(--surface-sunk);color:var(--ink-3)">؟</span>
          <span class="who"><b>خوش آمدی</b><small>حساب خودت را همین‌جا می‌بینی</small></span>
        </div>
        <p class="sub" style="margin:12px 0 0">اطلاعات حساب، رویدادها، بلیت و گواهی و امتیازت، همه مالِ
          حساب خودت است. با شمارهٔ موبایل و کد یک‌بارمصرف وارد شو؛ رمزی ندارد.</p>
        <div class="gl">
          <div class="row"><svg class="i" aria-hidden="true"><use href="#i-check"/></svg><span>بلیت و کارت ورود هر رویداد</span></div>
          <div class="row"><svg class="i" aria-hidden="true"><use href="#i-check"/></svg><span>گواهی و کارنامهٔ حضور</span></div>
          <div class="row"><svg class="i" aria-hidden="true"><use href="#i-check"/></svg><span>امتیاز، باشگاه کتاب و فرم‌ها</span></div>
        </div>
        <div class="row" style="margin-top:13px">
          <button class="btn primary" style="flex:1;justify-content:center" data-login>
            <svg class="i" aria-hidden="true"><use href="#i-mobile"/></svg> ورود با شمارهٔ موبایل</button>
        </div>
        <p class="cap" style="margin:9px 2px 0">${esc(SUP.n||'پشتیبانی')} و راهنما هم بی‌ورود از پایین همین صفحه باز می‌شود؛
          سرِ نوار پایین، کنار خانه و رویدادها.</p>
      </div></div>`;
}
function headMember(){
  const p=prof(), u=sess(), pc=pctOf(p), miss=missOf(p), st=stOf(p);
  const {cur,next}=lvl(), pts=+A.points||0;
  const initial=String(p.fullName||u.name||'ن').trim().slice(0,1)||'ن';
  const missTxt=miss.length?faN(miss.length)+' مورد مانده: '+miss.slice(0,2).map(f=>f.l).join('، '):'اطلاعات کامل است';
  return `<div class="phead">
      <div class="cover"></div>
      <div class="pbody">
        <div class="ptop">
          <span class="av">${esc(initial)}</span>
          <span class="who"><b>${esc(p.fullName||u.name||'کاربر نورا')}</b>
            <small>عضو از ${esc(u.joined||A.joined||'۱۴۰۴')} · سطح ${esc(cur.n||'—')}</small></span>
          <button class="icon-btn edit" data-go="account" aria-label="ویرایش اطلاعات حساب">
            <svg class="i" aria-hidden="true"><use href="#i-pen"/></svg></button>
        </div>
        <div class="pmeta">${chip(st[0],st[1])}${miss.length?chip(faN(miss.length)+' قلم مانده',''):chip('پروفایل کامل','ok')}</div>
        <div class="pstats">
          <button class="pstat" data-go="club"><b>${faNum(pts)}</b><small>امتیاز</small></button>
          <button class="pstat" data-go="club"><b>${esc(cur.n||'—')}</b><small>${next?('تا '+esc(next.n)+' '+faNum(next.at-pts)):'بالاترین سطح'}</small></button>
          <button class="pstat" data-go="events"><b>${faN(EVENTS.length)}</b><small>برنامهٔ پیش‌رو</small></button>
        </div>
        <div class="meter" role="img" aria-label="اطلاعات حساب ٪${faN(pc)} کامل است"><i style="width:${pc}%"></i></div>
        <div class="mfoot"><span class="cap">اطلاعات حساب: ٪${faN(pc)} کامل · ${esc(missTxt)}</span>
          <span class="sp" style="flex:1"></span>
          <button class="btn sm ${miss.length?'primary':'quiet'}" data-go="account">
            <svg class="i" aria-hidden="true"><use href="#${miss.length?'i-pen':'i-check'}"/></svg> ${miss.length?'تکمیل اطلاعات':'ویرایش'}</button></div>
      </div></div>`;
}

/* ══ نورا پی: رنگ و نشان خودش ═══════════════════════════════════════ */
function payCard(){
  if(!PAY) return '';
  const bits=(POL.payBits||['کیف پول','شارژ','صورت‌حساب','اقساط']).slice(0,4);
  return `<button class="paycard" data-go="pay" aria-label="${esc(PAY.n)} — ${esc(PAY.en||'nora pay')}">
      <span class="ptop">
        <span class="pico" aria-hidden="true"><svg class="i"><use href="#i-wallet"/></svg></span>
        <span class="pnames"><span class="pen">${esc(PAY.en||'nora pay')}</span><span class="pfa">${esc(PAY.n)}</span></span>
        <span class="pchip">به‌زودی</span>
      </span>
      <span class="prow">
        <span class="psum"><b>${login()?'شارژ، صورت‌حساب و اقساط':'با ورود، کیف پول خودت را می‌بینی'}</b><small>${login()?'این بخش در فاز بعد فعال می‌شود؛ همین حالا طرحش را ببین':'همهٔ پرداخت‌های نورا، یک‌جا و بی‌کارت'}</small></span>
        <span class="pgo">دیدن طرح<svg class="i" aria-hidden="true"><use href="#i-chev-left"/></svg></span>
      </span>
      <span class="pbits">${bits.map(b=>`<span>${esc(b)}</span>`).join('')}</span>
      <span class="pstripe" aria-hidden="true"></span>
    </button>`;
}

/* ══ ردیف‌های بخش‌ها ═════════════════════════════════════════════════ */
function subOf(k){
  const p=prof();
  if(k==='events'){
    if(!login()) return EVENTS.length?faN(EVENTS.length)+' برنامهٔ پیش‌رو و '+faN(PAST.length)+' برگزارشده':'';
    return faN(EVENTS.length)+' ثبت‌نام · بلیت، گواهی و کارنامه';
  }
  if(k==='account'){
    if(!login()) return ROWS.find(r=>r.k===k)?.s||'';
    const bc=bookState();
    return 'اطلاعات ٪'+faN(pctOf(p))+' · باشگاه کتاب'+(bc.seat?' (صندلی رزرو)':'');
  }
  return '';
}
function rowsBox(){
  return `<div class="mrows">${ROWS.map(r=>`<button class="mrow2" data-go="${r.k}">
      <span class="ic"><svg class="i" aria-hidden="true"><use href="#${r.i}"/></svg></span>
      <span class="tx"><b>${esc(r.n)}</b><small>${esc(subOf(r.k)||r.s)}</small></span>
      ${login()?`<span class="mini"><svg class="i" aria-hidden="true"><use href="#i-check"/></svg>${r.k==='events'?faN(EVENTS.length)+' مورد':'٪'+faN(pctOf(prof()))}</span>`:''}
      <svg class="i chev" aria-hidden="true"><use href="#i-chev-left"/></svg></button>`).join('')}</div>`;
}
function renderHub(){
  const box=$('#hubBox'); if(!box) return;
  box.innerHTML=(login()?headMember():headGuest())+payCard()+rowsBox();
}

/* ══ سرِ هر نما ══════════════════════════════════════════════════════ */
function viewHead(t,sub,tabs,isProfile){
  const key=isProfile?'ptab':'vtab', cur=isProfile?S.ptab:S.vtab;
  return `<div class="vhead"><button class="btn sm quiet" data-back>
      <svg class="i" aria-hidden="true"><use href="#i-chev-left"/></svg> حساب من</button>
      <span class="sp" style="flex:1"></span></div>
    <h2 class="vh2">${esc(t.n)}</h2><p class="vhsub">${esc(sub||t.s||'')}</p>
    ${tabs?`<div class="vtabs" role="tablist" aria-label="بخش‌های ${esc(t)}">${tabs.map(t2=>`<button class="vtab${cur===t2.k?' on':''}" role="tab"
      aria-selected="${cur===t2.k}" tabindex="${cur===t2.k?'0':'-1'}" data-${key}="${t2.k}">
      ${t2.i?`<svg class="i" aria-hidden="true"><use href="#${t2.i}"/></svg>`:''} ${esc(t2.n)}</button>`).join('')}</div>`:''}`;
}
const gate=t=>`<div class="gate"><svg class="i" aria-hidden="true"><use href="#i-lock"/></svg>
  <div class="gt">این بخش با حساب خودت باز می‌شود</div>
  <div class="gs">«${esc(t.n)}» مالِ حساب خودت است؛ با شمارهٔ موبایل و کد یک‌بارمصرف وارد شو.</div>
  <div class="gacts"><button class="btn primary" data-login><svg class="i" aria-hidden="true"><use href="#i-mobile"/></svg> ورود با شمارهٔ موبایل</button>
    <button class="btn quiet" data-go="support">پشتیبانی، بی ورود</button></div></div>`;

/* ══ رویدادهای من ═══════════════════════════════════════════════════ */
const VTABS=[{k:'up',n:'پیش‌رو'},{k:'past',n:'برگزارشده'},{k:'tickets',n:'بلیت و گواهی'},
             {k:'attend',n:'کارنامهٔ حضور'},{k:'reviews',n:'نظرهای من'}];
function evRow(e){
  return `<div class="erow">
    <span class="dbox"><b>${faD(e.dn||'')}</b><small>${esc(monOf(e))}</small></span>
    <span class="ex"><b>${esc(e.t)}</b><small>${esc([e.when,e.time,e.place].filter(Boolean).join(' · '))}</small>
      <span class="acts">
        <button class="btn sm quiet" data-ticket="${esc(e.id)}"><svg class="i" aria-hidden="true"><use href="#i-qr"/></svg> کارت ورود</button>
        <button class="btn sm quiet" data-cancel="${esc(e.id)}">لغو</button></span></span></div>`;
}
function pastRow(h){
  return `<div class="erow">
    <span class="dbox"><b>${faD(h.dn||'')}</b><small>${esc(monOf(h))}</small></span>
    <span class="ex"><b>${esc(h.t)}</b><small>${esc(h.d)} · ${esc(h.rec||'')}</small>
      <span class="acts">
        <button class="btn sm quiet" data-open-past="${esc(h.id)}"><svg class="i" aria-hidden="true"><use href="#i-play-f"/></svg> ضبط و جزوه</button>
        ${h.cert?`<button class="btn sm quiet" data-cert="${esc(h.id)}"><svg class="i" aria-hidden="true"><use href="#i-medal"/></svg> گواهی</button>`:''}</span></span></div>`;
}
function panelUp(){
  if(!EVENTS.length) return card('رویدادهای من','',empty2('هنوز ثبت‌نامی نداری','از فهرست رویدادها یکی را انتخاب کن.'));
  return card('پیش‌روی من',faN(EVENTS.length)+' ثبت‌نام؛ کارت ورود هر رویداد این‌جاست',
    EVENTS.map(evRow).join(''))+
    note('لغو ثبت‌نام تا یک روز قبل، بی هزینه است؛ شرایط بازگشت مبلغ در صفحهٔ خود رویداد آمده.','i-clock');
}
function panelPast(){
  return card('برگزارشده‌ها',faN(PAST.length)+' رویداد؛ ضبط، جزوه و گواهی',
    PAST.map(pastRow).join(''))+
    note('فایل ضبط و جزوه از همین‌جا برای همیشه در دسترس است.','i-archive');
}
function panelTickets(){
  const p=prof(), u=sess(), test=CERTS['NL-T4K7M9X']||{};
  return `<div class="idcard">
      <div class="c1"><span class="av2">${esc(String(p.fullName||u.name||'ن').slice(0,1))}</span>
        <span class="nm"><b>${esc(p.fullName||u.name||'کاربر نورا')}</b>
          <small>کارت ورود · ${esc(PAY?'نورا':'نورا')} · عضو از ${esc(u.joined||A.joined||'۱۴۰۴')}</small></span>
        <span class="sp" style="flex:1"></span>${chip('فعال','ok')}</div>
      <div class="meta">
        <div><small>کد عضویت</small><b>NL-4567</b></div>
        <div><small>کارت ورود رویداد</small><b>${esc(EVENTS[0]?EVENTS[0].t:'—')}</b></div>
      </div>
      <div class="ser">${esc('NL-4567-1404')}</div>
      <div class="brandline"><span class="mark" aria-hidden="true"></span> این کارت را در ورودی نشان بده</div>
    </div>
    ${card('گواهی‌های من','هر گواهی سریال خودش را دارد؛ با همان می‌شود استعلام گرفت',
      `<div class="tk"><svg class="i" aria-hidden="true" style="width:19px;height:19px;color:var(--brand)"><use href="#i-medal"/></svg>
        <span class="tx"><b>${esc(test.c||'کارگاه عکاسی مقدماتی')}</b>
          <small>صادر ${esc(test.d||'۲۱ شهریور ۱۴۰۵')} · ${esc(test.h||'۲۴ ساعت')} · سریال NL-T4K7M9X</small>
          <span class="acts">${chip('آمادهٔ دانلود','ok')}
            <button class="btn sm quiet" data-dl-cert="NL-T4K7M9X"><svg class="i" aria-hidden="true"><use href="#i-send"/></svg> دانلود</button>
            <button class="btn sm quiet" data-verify="NL-T4K7M9X">استعلام</button></span></span></div>`)}
    ${card('گونه‌های گواهی','در نورا چهار گونه گواهی داریم',
      `<div class="kinds">${(POL.certKinds||[]).map(k=>`<div class="kind">
        <svg class="i" aria-hidden="true" style="width:19px;height:19px;color:var(--ink-4)"><use href="#i-doc"/></svg>
        <span class="tx"><b>${esc(k.n)}</b><small>${esc(k.s)}</small></span>
        <button class="btn sm ${k.k==='free'?'quiet':'primary'}" data-certreq="${esc(k.k)}">${k.k==='free'?'دریافت':'سفارش'}</button></div>`).join('')}</div>`+
      note((POL.certNote||'شرط صدور هر رویداد جداست')+' · اعتبار پیش‌فرض هر گواهی '+
        faN(POL.certValidMonths||24)+' ماه است.','i-shield'))}`;
}
function panelAttend(){
  const score=A.score||{}, months=[40,62,55,78,66,84,72,90,60,74,88,96];
  const sess5=[{d:'امروز شنبه',t:'حلقهٔ مطالعهٔ ادبیات',s:'حاضر'},{d:'شنبهٔ پیش',t:'جلسهٔ شعر و موسیقی',s:'حاضر'},
    {d:'۲۹ شهریور',t:'کارگاه عکاسی در طبیعت',s:'غایب'},{d:'۲۶ شهریور',t:'نشست مالی خانواده',s:'حاضر'},
    {d:'۲۱ شهریور',t:'کارگاه فن بیان',s:'حاضر'}];
  return card('کارنامهٔ حضور من','حضور، غیبت و ساعت‌هایی که با نورا بودی',
      `<div class="stats">
        ${[['٪'+faN(score.attend||88),'نرخ حضور'],['۱۱','برنامهٔ پیش‌رو امسال'],
           [faN(ARCHIVE.hours||0),'ساعت کارگاه'],['٪'+faN(score.growth?Math.min(100,Math.round(score.growth/2)):90),'پیشرفت امسال']]
          .map(([v,l])=>`<div class="stat2"><b>${v}</b><small>${esc(l)}</small></div>`).join('')}</div>
      <div class="bars" role="img" aria-label="حضور دوازده ماه">
        ${months.map((v,i)=>`<i class="${i===2||i===4?'off':''}" style="height:${Math.max(12,Math.round(v*0.86))}%" title="${esc(faD(i+1))}"></i>`).join('')}</div>
      <div class="barscap"><span class="cap">دوازده ماه گذشته</span><span class="sp" style="flex:1"></span>
        <span class="cap">کم‌رنگ‌ها ماه‌های کم‌حضور</span></div>`)+
    card('جلسه‌های آخر',faN(sess5.length)+' جلسهٔ گذشته',
      sess5.map(x=>`<div class="tk"><span class="when">${esc(x.d)}</span>
        <span class="tx"><b>${esc(x.t)}</b><small>حضور و غیاب جلسه</small></span>
        ${chip(x.s,x.s==='حاضر'?'ok':'stop')}</div>`).join(''));
}
function panelReviews(){
  const R=[{e:'کارگاه فن بیان، ترم تیر',r:5,d:'۲۹ تیر',q:'تمرین‌های هفتگی باعث شد بالاخره جلوی جمع حرف بزنم.'},
           {e:'نشست مالی خانواده',r:4,d:'۱۲ تیر',q:'مثال‌های واقعی خوب بود؛ کاش یک جلسهٔ بیشتر داشت.'},
           {e:'حلقهٔ مطالعهٔ ادبیات',r:5,d:'۵ تیر',q:'یادداشت سرپرست باشگاه هر جلسه ارزشش را دارد.'}];
  return card('نظرهای من',faN(R.length)+' نظر نوشته‌ای؛ ممنون که راه را برای بقیه روشن می‌کنی',
      R.map(x=>`<div class="tk">
        <svg class="i" aria-hidden="true" style="width:19px;height:19px;color:#C9A96A"><use href="#i-star"/></svg>
        <span class="tx"><b>${esc(x.e)}</b><small>${esc(x.d)} · ${'★'.repeat(x.r)}</small>
          <p class="sub" style="margin:4px 0 0">${esc(x.q)}</p>
          <span class="acts"><button class="btn sm quiet" data-edit-review="${esc(x.e)}">ویرایش</button></span></span></div>`).join(''))+
    card('نظر تازه','بعد از هر رویداد می‌توانی امتیاز بدهی',
      `<div class="row"><button class="btn primary" data-go="events">
        <svg class="i" aria-hidden="true"><use href="#i-pen"/></svg> نوشتن نظر برای رویداد آخر</button></div>`);
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
  return card('دعوت دوستان','هر دوست که با کد تو بیاید، هر دو امتیاز می‌گیرید',
    `<div class="srow"><svg class="i" aria-hidden="true"><use href="#i-send"/></svg>
      <span class="sp">کد دعوت تو<b class="num" style="display:block;font-size:15px;margin-top:3px">${esc(code)}</b></span>
      <button class="btn sm quiet" data-copy="${esc(code)}">کپی</button></div>
     <div class="srow"><svg class="i" aria-hidden="true"><use href="#i-users"/></svg>
      <span class="sp">تا حالا ${faN(done)} دوست آمده · ${faN(Math.max(0,need-done))} تا مانده به پاداش</span>
      <button class="btn sm quiet" data-invite>دعوت با پیوند</button></div>`);
}
function clubTab(){
  const pts=+A.points||0, {cur,next}=lvl(), cap=POL.pointsCap||{};
  return card('امتیاز و سطح من','هر ثبت‌نام، حضور و فرم امتیاز دارد',
      `<div class="stats">
        ${[['امتیاز من',faNum(pts)],['سطح',(cur.n||'—')],
           ['تا سطح بعدی',next?faNum(next.at-pts):'—'],['رتبه',faN((A.score||{}).rank||0)+' از '+faN((A.score||{}).of||0)]]
          .map(([l,v])=>`<div class="stat2"><b>${esc(v)}</b><small>${esc(l)}</small></div>`).join('')}</div>
      <div class="ladder" style="margin-top:12px">${LEVELS.map(l=>`<div class="lvrow ${l.k===cur.k?'on':''}">
        <span class="dot2"></span><span class="tx"><b>${esc(l.n)}</b><small>${esc(l.perks)}</small></span>
        <span class="at">${faNum(l.at)} امتیاز</span></div>`).join('')}</div>
      ${note('سقف‌های محافظ: هر کار تا '+faN(cap.each||100)+'، روزانه تا '+faN(cap.day||50)+
        ' و ماهانه تا '+faN(cap.month||300)+' امتیاز.','i-shield')}`)+
    card('دستاوردها','هر قفل، یک کار می‌خواهد',
      `<div class="acks">${ACH.map(a=>`<div class="ack${a.on?' on':''}">
        <svg class="i" aria-hidden="true"><use href="#${a.i}"/></svg>
        <b>${esc(a.n)}</b><small>${a.on?esc(a.r||'گرفته‌ای'):faNum(a.at)+' امتیاز'}</small></div>`).join('')}</div>`)+
    card('فروشگاه پاداش','امتیازت را خرج کن',
      `<div class="kinds">${STORE.map(r=>{const can=pts>=r.cost; return `<div class="kind">
        <svg class="i" aria-hidden="true" style="width:19px;height:19px;color:var(--ink-4)"><use href="#i-wallet"/></svg>
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
  const hero=`<div class="bchero">
      <div class="bt">${esc(C.book||'')}</div>
      <div class="bs">${esc(C.bookBy||'')} · ${esc(C.term||'')} · ${esc(C.session||'')}</div>
      <div class="bar" role="img" aria-label="پیشرفت کتاب ماه ٪${faN(pct)}"><i style="width:${pct}%"></i></div>
      <div class="bs" style="margin-top:7px">٪${faN(pct)} خوانده شده · جلسهٔ بعد: ${esc(C.next||'')}</div>
      <div class="chips">
        ${chip((C.members||0)+' عضو','')}${chip(faN(C.meetings||0)+' جلسه','')}${chip(bc.joined?'عضو این ترم':'عضو نیستی',bc.joined?'ok':'warn')}</div>
    </div>`;
  const stats=`<div class="stats">
      ${[['اعضا',faN(C.members||0)+' از '+faN(C.cap||0)],['جلسه‌ها',faN(C.meetings||0)],
         ['صفحهٔ من',faN(bc.pages||0)+' از ۲۰۰'],['قفسه',faN(shelf.length)]]
        .map(([l,v])=>`<div class="stat2"><b>${esc(v)}</b><small>${esc(l)}</small></div>`).join('')}</div>`;
  return hero+stats+
    card('پیشرفت مطالعهٔ من','صفحه‌هایی که خوانده‌ای را خودت ثبت کن',
      `<div class="meter"><i style="width:${Math.round((bc.pages||0)/200*100)}%"></i></div>
       <div class="row" style="margin-top:10px">
         <button class="btn sm quiet" data-pages="10">+۱۰ صفحه</button>
         <button class="btn sm quiet" data-pages="25">+۲۵ صفحه</button>
         <span class="sp" style="flex:1"></span>
         <span class="cap">٪${faN(Math.round((bc.pages||0)/200*100))} از کتاب ماه</span></div>`)+
    card('رزرو صندلی و یادداشت','صندلی جلسهٔ پنجشنبه و یادداشت یک‌صفحه‌ای',
      `<div class="srow"><svg class="i" aria-hidden="true"><use href="#i-calendar"/></svg>
         <span class="sp">صندلی پنجشنبه ۱۸:۰۰<b class="cap" style="display:block">${bc.seat?'رزرو شد؛ یک ساعت قبل یادآوری می‌کنیم':esc(C.session||'کتابخانهٔ نورا، ونک')}</b></span>
         ${bc.seat?chip('رزرو شد','ok'):`<button class="btn sm primary" data-seat>رزرو</button>`}</div>
       <div class="srow" style="align-items:flex-start;flex-direction:column;gap:7px">
         <span class="cap">یادداشت من برای جلسه</span>
         <textarea class="input" id="bcNote" rows="3" placeholder="مثلاً فصل ۴: راوی چه چیزی را پنهان می‌کند؟">${esc(bc.note)}</textarea>
         <div class="row" style="width:100%"><button class="btn sm primary" data-save-note>
           <svg class="i" aria-hidden="true"><use href="#i-check"/></svg> ذخیرهٔ یادداشت</button>
           <span class="sp" style="flex:1"></span>
           <span class="cap">${bc.note?'ذخیره شده، قابل ویرایش':'خالی'}</span></div></div>`)+
    card('جلسه‌های پیش‌رو','پنجشنبه‌ها ۱۸:۰۰ · کتابخانهٔ نورا، ونک',
      plan.map(p=>`<div class="tk"><span class="when">${esc(p.d)}</span>
        <span class="tx"><b>${esc(p.c)}</b><small>${esc(p.w)}</small></span></div>`).join(''))+
    card('کتاب ماه بعد را با هم انتخاب کنیم','رأی تو در فهرست ماه بعد حساب می‌شود',
      `<div class="votebox">${VOTE.map(v=>{const n=(+v.n||0)+(vote===v.k?1:0);
        return `<button class="voteopt${vote===v.k?' on':''}" data-vote="${esc(v.k)}">
          <span class="vt"><b>${esc(v.t)}</b><span>${esc(v.by)}</span></span>
          <span class="vbar"><i style="width:${tot?Math.round(n/tot*100):0}%"></i></span>
          <span class="cap">${faN(n)} رأی</span></button>`}).join('')}</div>
       <p class="cap" style="margin:8px 2px 0">${vote?'رأیت ثبت شد؛ نتیجه زنده به‌روز می‌شود.':'با زدن هر گزینه، رأیت ثبت می‌شود.'}</p>`)+
    card('جلسه‌های گذشته','ضبط هر جلسه هست',
      log.map(l=>`<div class="tk"><svg class="i" aria-hidden="true" style="width:19px;height:19px;color:var(--ink-4)"><use href="#i-play-f"/></svg>
        <span class="tx"><b>${esc(l.t)}</b><small>${esc(l.d)} · ${faN(l.n)} نفر حاضر</small>
          <span class="acts"><button class="btn sm quiet" data-watch="${esc(l.t)}">تماشا</button></span></span></div>`).join(''))+
    card('قفسهٔ باشگاه','سه کتاب ماه گذشته',
      `<div class="shelf">${shelf.map(b=>`<div class="book">
        <span class="bcover" style="--g:${esc(b.c||'#2E6B7A')}"></span>
        <span class="btx"><b>${esc(b.t)}</b><small>${esc(b.by)} · ${esc(b.d)} · ${'★'.repeat(Math.round(+b.r||0))}</small></span></div>`).join('')}</div>`)+
    card('سرپرست باشگاه','جلسه‌ها را او می‌گرداند',
      `<div class="srow"><span class="av2" style="width:40px;height:40px;border-radius:13px;display:grid;place-items:center;font-weight:700;background:var(--brand-tint);color:var(--brand-ink)">${esc(String(sup.n||'د').slice(0,1))}</span>
        <span class="sp">${esc(sup.n||'خانم مریم داوودی')}<small class="cap" style="display:block">${esc(sup.r||'سرپرست باشگاه کتاب‌خوانی')}</small></span>
        <button class="btn sm quiet" data-go="support">پرسش</button></div>`+
      (C.rules||[]).map(r=>`<div class="srow"><svg class="i" aria-hidden="true"><use href="#i-check"/></svg><span class="sp">${esc(r)}</span></div>`).join(''));
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
  if(f.lock) return `<span class="v"><svg class="i" aria-hidden="true" style="width:15px;height:15px;color:var(--ok)"><use href="#i-check"/></svg>
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
  const body=groups.map(g=>`<div class="grp"><div class="gt">${esc(g)}</div>
    ${FIELDS.filter(f=>f.g===g).map(f=>S.edit
      ? `<div class="fld${S.errs[f.k]?' bad':''}">${fieldEdit(f,p)}</div>`
      : `<div class="fld"><span class="hint">${esc(f.l)}</span>${fieldView(f,p)}</div>`).join('')}</div>`).join('');
  const acts=S.edit?`<div class="row" style="margin-top:14px">
      <button class="btn primary" id="sendBtn"><svg class="i" aria-hidden="true"><use href="#i-check"/></svg> ذخیره و ارسال برای تأیید</button>
      <button class="btn quiet" id="draftBtn">فقط ذخیره</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" id="cancelBtn">انصراف</button></div>`
    :`<div class="row" style="margin-top:12px"><button class="btn ${missOf(p).length?'primary':'quiet'}" id="editBtn">
      <svg class="i" aria-hidden="true"><use href="#i-pen"/></svg> ${missOf(p).length?'تکمیل اطلاعات':'ویرایش اطلاعات'}</button></div>`;
  return card('اطلاعات حساب من','همان چیزی که روی بلیت و گواهی می‌آید؛ تغییرات اول به کارشناس می‌رود',
    `<div class="row" style="align-items:center;gap:8px;margin-top:2px"><span class="cap">وضعیت</span>${chip(st[0],st[1])}
      <span class="sp" style="flex:1"></span><span class="cap">٪${faN(pctOf(p))} کامل</span></div>${body}${acts}`);
}
function flowPanel(){
  const p=prof(), st=(p&&p.status)||'draft', hist={}; (p.history||[]).forEach(h=>{hist[h.k]=h.at});
  const hit={filled:['draft','pending','approved'],pending:['pending','approved'],approved:['approved']};
  const steps=FLOW.map(f=>{const on=(hit[f.k]||[]).includes(st), now=(st==='pending'&&f.k==='pending');
    return `<div class="step ${on?'done':''} ${now?'now':''}">
      <span class="dot"><svg class="i" aria-hidden="true"><use href="#i-${on?'check':f.k==='pending'?'clock':'pen'}"/></svg></span>
      <span class="tt"><b>${esc(f.n)}</b><small>${esc(f.s)}</small></span>
      <span class="at">${esc(hist[f.k]||(on?'':'—'))}</span></div>`}).join('');
  const tail = st==='rejected' ? `<span class="err" style="display:block;margin-top:8px">دلیل رد: ${esc(p.reason||'نامشخص')}</span>`
    : st==='pending' ? '<p class="cap" style="margin:10px 3px 0">معمولاً تا یک روز کاری بررسی می‌شود.</p>'
    : st==='approved' ? '<p class="cap" style="margin:10px 3px 0">پروفایلت تأیید شده است؛ اگر چیزی را عوض کنی، دوباره می‌رود صف تأیید.</p>'
    : '<p class="cap" style="margin:10px 3px 0">هر وقت اطلاعات را فرستادی، وضعیت همین‌جا عوض می‌شود.</p>';
  return card('تأیید پروفایل','کارشناس درخواستت را می‌بیند و نتیجه را خبر می‌دهد',`<div class="steps">${steps}</div>${tail}`);
}
function formsPanel(){
  const F=[{t:'پیش‌ثبت‌نام کارگاه خطاطی',k:'پیش‌ثبت‌نام',s:'draft',d:'۳ مهر'},
           {t:'رضایت‌سنجی کارگاه عکاسی',k:'رضایت‌سنجی کارگاه',s:'pending',d:'۲۱ تیر'},
           {t:'انتخاب مسیر ترم پاییز',k:'انتخاب مسیر',s:'approved',d:'۱۲ شهریور'}];
  const M={draft:['پیش‌نویس','warn'],pending:['در صف بررسی','brand'],approved:['تأییدشده','ok']};
  return card('فرم‌های من','پیش‌نویس، در صف و تأییدشده، همه یک‌جا',
    F.map(f=>`<div class="tk">
      <svg class="i" aria-hidden="true" style="width:19px;height:19px;color:var(--ink-4)"><use href="#i-doc"/></svg>
      <span class="tx"><b>${esc(f.t)}</b><small>${esc(f.k)} · ${esc(f.d)}</small>
        <span class="acts">${chip(M[f.s][0],M[f.s][1])}
          <button class="btn sm quiet" data-form="${esc(f.t)}">${f.s==='draft'?'ادامهٔ تکمیل':'دیدن پاسخ‌ها'}</button></span></span></div>`).join('')+
    `<div class="row" style="margin-top:12px"><button class="btn sm primary" data-form-new>
      <svg class="i" aria-hidden="true"><use href="#i-pen"/></svg> فرم تازه</button>
      <span class="sp" style="flex:1"></span><span class="cap">${faN((POL.formKinds||[]).length)} گونه فرم</span></div>`+
    note('گونه‌ها: '+((POL.formKinds||[]).join('، ')),'i-layers'));
}
function privacyPanel(){
  const p=prof(), asked=!!p.askedDelete;
  return card('حریم خصوصی','اطلاعاتت را می‌توانی برداری یا حساب را ببندی',
    `<div class="srow"><svg class="i" aria-hidden="true"><use href="#i-doc"/></svg>
      <span class="sp">دانلود اطلاعات من<small>پروفایل، خریدها، اعلان‌ها و آمار، یک فایل</small></span>
      <button class="btn sm quiet" id="dlBtn"><svg class="i" aria-hidden="true"><use href="#i-send"/></svg> دانلود</button></div>
     <div class="srow"><svg class="i" aria-hidden="true" style="color:var(--stop)"><use href="#i-shield"/></svg>
      <span class="sp">حذف حساب کاربری<small>بلیت‌ها، گواهی‌ها و سابقهٔ حضور هم پاک می‌شود</small></span>
      <button class="btn sm stop" id="delBtn" ${asked?'disabled':''}>${asked?'ثبت شد':'درخواست حذف'}</button></div>
     <div class="cap" id="delNote" style="margin-top:10px">${asked?'درخواستت ثبت شده؛ کارشناس برای تأیید خبر می‌دهد.':''}</div>`)+
    note('حذف حساب بی‌برگشت است؛ برای همین دو تأیید می‌گیریم: تایپ «حذف» و کد پیامکی.','i-lock')+
    card('چه چیزی نگه می‌داریم','شفاف و کوتاه',
      `<div class="srow"><svg class="i" aria-hidden="true"><use href="#i-check"/></svg><span class="sp">اطلاعات پروفایل، برای بلیت و گواهی</span></div>
       <div class="srow"><svg class="i" aria-hidden="true"><use href="#i-check"/></svg><span class="sp">سابقهٔ خرید و حضور، برای کارنامهٔ تو</span></div>
       <div class="srow"><svg class="i" aria-hidden="true"><use href="#i-lock"/></svg><span class="sp">شمارهٔ موبایل، فقط برای ورود و یادآوری</span></div>`);
}
/* پروفایل من: پنج تب، هر چیزی که به خودِ عضو برمی‌گردد، یک‌جا */
const PTABS=A.profileTabs||[{k:'info',n:'اطلاعات من'}];
VS.profile=function(t){
  if(!login()) return viewHead(t,'',PTABS,true)+gate(t);
  const body=S.ptab==='club'?clubTab()
    : S.ptab==='book'?bookPanel()
    : S.ptab==='forms'?formsPanel()
    : S.ptab==='privacy'?privacyPanel()
    : infoPanel()+flowPanel();
  const sub=(PTABS.find(x=>x.k===S.ptab)||{}).s||'';
  return viewHead(t,sub,PTABS,true)+body;
};
VS.pay=function(t){
  const bits=POL.payBits||['کیف پول','شارژ','صورت‌حساب','اقساط','بازگشت وجه','کد تخفیف'];
  return viewHead(t)+card('نورا پی','این بخش را در یک فاز جدا می‌سازیم',
    `<div class="gate"><svg class="i" aria-hidden="true"><use href="#i-wallet"/></svg>
      <div class="gt">فعلاً قفل است</div>
      <div class="gs">حساب، رویدادها و امتیاز کار می‌کند؛ کیف پول و پرداخت‌ها فاز بعد می‌آید تا
        شماره‌ها و صورت‌حساب‌ها از اول درست بنشینند.</div>
      <div class="chipsline" style="justify-content:center">${bits.map(b=>chip(b)).join('')}</div>
      <div class="gacts"><button class="btn primary" data-go="support">پیشنهادت را بگو</button>
        <button class="btn quiet" data-go="events">رویدادهای من</button></div></div>`);
};

/* ══ ورقهٔ پشتیبانی: یک‌جا، از پایین ═════════════════════════════════ */
function supportHTML(){
  const sup=(N.PEOPLE||[]).find(p=>p.id==='p6')||{}, cats=POL.ticketCats||[];
  const chans=[
    {i:'i-mobile',t:'تلفن پشتیبانی',v:'۰۲۱–۸۸۸۸۱۲۳۴',href:'tel:+982188881234',s:'۹ تا ۱۸، روزهای کاری'},
    {i:'i-mail',t:'رایانامه',v:'info@lifeline1.ir',href:'mailto:info@lifeline1.ir',s:'پاسخ در یک روز کاری'},
    {i:'i-send',t:'بله',v:'@nora_support',href:'https://ble.ir/nora_support',s:'گفت‌وگوی سریع'},
    {i:'i-link',t:'تلگرام',v:'@nora_support',href:'https://t.me/nora_support',s:'گفت‌وگوی سریع'}
  ];
  return `<div class="grabber"></div>
    <div class="row" style="align-items:center;margin-bottom:10px">
      <div><div class="head">${esc(SUP.n||'پشتیبانی و راهنما')}</div><div class="cap">${esc(SUP.s||'')}</div></div>
      <span class="sp" style="flex:1"></span><button class="icon-btn" data-close aria-label="بستن"><svg class="i" aria-hidden="true"><use href="#i-close"/></svg></button></div>
    <div class="suphead"><span class="av3">${esc(String(sup.n||'حسن مقدم').slice(0,1))}</span>
      <span style="flex:1;min-width:0"><b class="sub">${esc(sup.n||'حسن مقدم')}</b>
        <div class="cap">${esc(sup.r||'کارشناس پشتیبانی نورا')} · پاسخ تا پایان روز کاری</div></span>
      ${chip('آنلاین','ok')}</div>
    ${chans.map(c=>`<a class="chan" href="${esc(c.href)}" ${c.href.startsWith('http')?'target="_blank" rel="noopener"':''}>
      <span class="chi"><svg class="i" aria-hidden="true"><use href="#${c.i}"/></svg></span>
      <span class="cht"><b>${esc(c.t)}</b><span>${esc(c.v)}</span></span>
      <svg class="i" aria-hidden="true" style="width:15px;height:15px;color:var(--ink-4)"><use href="#i-chev-left"/></svg></a>`).join('')}
    <hr class="hr"/>
    <div class="cap" style="margin-bottom:2px">تیکت تازه — دسته را انتخاب کن</div>
    <div class="chipsline">${cats.map(c=>`<button class="tag pickc${S.ncat===c?' on':''}" data-cat="${esc(c)}">${esc(c)}</button>`).join('')}</div>
    <div class="tk" style="margin-top:8px">
      <svg class="i" aria-hidden="true" style="width:19px;height:19px;color:var(--brand)"><use href="#i-headphone"/></svg>
      <span class="tx"><b>گواهی کارگاه عکاسی</b><small>دستهٔ گواهی · ۲ مهر</small>
        <span class="acts">${chip('در حال بررسی','brand')}<span class="cap">پاسخ‌دهنده: ${esc(sup.n||'حسن مقدم')}</span></span></span></div>
    <label class="lbl" for="msg" style="margin-top:12px">یا همین‌جا بنویس</label>
    <textarea class="input" id="msg" rows="3" placeholder="مثلاً دربارهٔ تأیید رسید کارت‌به‌کارت سؤال دارم"></textarea>
    <div class="row" style="margin-top:12px"><button class="btn primary" data-sup-send>
      <svg class="i" aria-hidden="true"><use href="#i-send"/></svg> فرستادن پیام</button>
      <span class="sp" style="flex:1"></span><span class="cap">بدون ورود هم کار می‌کند</span></div>
    <hr class="hr"/>
    <div class="cap" style="margin-bottom:4px">پرسش‌های پرتکرار</div>
    ${FAQ.map((f,i)=>`<details class="faq"${i===0?' open':''}><summary>${esc(f[0])}</summary><p>${esc(f[1])}</p></details>`).join('')}
    <hr class="hr"/>
    <div class="cap" style="margin-bottom:4px">دربارهٔ نورا</div>
    <div class="abrow"><svg class="i" aria-hidden="true"><use href="#i-users"/></svg>
      <span class="sp">گروه فرهنگی خط زندگی<small>تهران، خیابان ولی‌عصر، پلاک ۱۲ · کتابخانهٔ نورا</small></span></div>
    <a class="abrow" href="https://lifeline1.ir" target="_blank" rel="noopener" style="color:inherit;text-decoration:none">
      <svg class="i" aria-hidden="true"><use href="#i-link"/></svg>
      <span class="sp">lifeline1.ir<small>پایگاه گروه و گزارش‌ها</small></span></a>`;
}
function fillSupport(){ fillSheet('shSupport',supportHTML()) }
function openSupport(){ const b=$('#supBody'); if(b&&!b.children.length) fillSupport(); openSheet('shSupport') }

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
      برای اطمینان، کلمهٔ <b>حذف</b> را بنویس و کد پیامکی را وارد کن.</p>
    <label class="lbl" for="delWord" style="margin-top:12px">کلمهٔ تأیید</label>
    <input class="input" id="delWord" placeholder="حذف" autocomplete="off"/>
    <label class="lbl" for="delCode" style="margin-top:10px">کد پیامکی</label>
    <input class="input num" id="delCode" inputmode="numeric" maxlength="5" placeholder="کد ۵ رقمی"/>
    <div class="cap" style="margin-top:6px">کد نمایشی: ۵۴۳۲۱</div>
    <div class="row" style="margin-top:14px"><button class="btn stop" id="delYes">بله، حسابم را ببند</button>
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
    ['گواهی نورا — گروه فرهنگی خط زندگی','', 'نام: '+(c.n||prof().fullName||''), 'رویداد: '+(c.c||''),
     'تاریخ: '+(c.d||''), 'مدت: '+(c.h||''), 'سریال: '+ser, '', 'استعلام: lifeline1.ir/nora-ui/verify'].join('\n'));
  toast('گواهی دانلود شد؛ سریال '+faN(ser));
}
function certAsk(kind){
  const K=(POL.certKinds||[]).find(k=>k.k===kind)||{};
  fillSheet('shConfirm',`<div class="grabber"></div><div class="head">${esc(K.n||'گواهی')}</div>
    <p class="sub" style="margin-top:8px">${esc(K.s||'')} — صدور گواهی نیاز به تأیید سرپرست دارد؛ بعد از تأیید خبر می‌دهیم.</p>
    <div class="row" style="margin-top:14px"><button class="btn primary" data-cert-yes>
      <svg class="i" aria-hidden="true"><use href="#i-check"/></svg> بفرست برای تأیید سرپرست</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" data-close>نه</button></div>`);
  openSheet('shConfirm');
}

/* ══ رندر ════════════════════════════════════════════════════════════ */
function viewOf(k){ return k==='events'?VS.events : k==='profile'?VS.profile : k==='pay'?VS.pay : null }
/* نشانی‌های کوتاه، تب همان پروفایل را باز می‌کنند */
const ALIAS={club:'club', book:'book', forms:'forms', privacy:'privacy', account:'info', info:'info'};
function renderView(){
  const box=$('#viewBox'), t=SECT.find(s=>s.k===S.view), fn=viewOf(S.view);
  if(!box||!t||!fn) return;
  box.innerHTML=`<section class="sec" aria-label="${esc(t.n)}">${fn(t)}</section>`;
  document.title='نورا · '+t.n;
}
function render(){
  renderHub();
  const box=$('#viewBox'), sb=$('#supBar'), ok=!!viewOf(S.view);
  if(sb) sb.hidden=false;                       /* پشتیبانی همیشه چسبیده به نوار پایین */
  if(!ok){ S.view=''; if(box){ box.hidden=true; box.innerHTML='' } document.title='نورا · حساب من' }
  else { box.hidden=false; renderView() }
}
function route(){
  const raw=(location.hash||'').replace('#','');
  if(raw==='support'){ setTimeout(openSupport,60); S.view=''; render(); return }
  if(ALIAS[raw]){ S.view='profile'; S.ptab=ALIAS[raw]; S.edit=false; S.errs={}; render();
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
  const vt=t.closest('[data-vtab]'); if(vt){ S.vtab=vt.dataset.vtab; renderView(); return }
  const pt=t.closest('[data-ptab]'); if(pt){ S.ptab=pt.dataset.ptab; S.edit=false; S.errs={}; renderView(); return }
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
    closeSheets(); render(); toast('درخواست حذف ثبت شد؛ کارشناس برای تأیید خبر می‌دهد'); return }
  const ck=t.closest('[data-cat]'); if(ck){ S.ncat=ck.dataset.cat; fillSupport(); return }
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
  if(t.closest('[data-login]')){ S.after=''; loginSheet(); return }
  if(t.closest('[data-close]')){ closeSheets(); return }
  if(t.closest('#supBar')){ openSupport(); return }
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
  if(t.closest('[data-sup-send]')){
    const el=$('#msg'), m=el?String(el.value||'').trim():'';
    if(m.length<5){ toast('کمی بیشتر بنویس تا کارشناس بهتر کمک کند'); if(el&&el.focus) el.focus(); return }
    closeSheets(); toast('پیام ثبت شد؛ کارشناس در همان روز کاری پاسخ می‌دهد'); return }
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
fillSupport();
route();
})();
