/* ══════════════════════════════════════════════════════════════════════════
   حساب من — نمای پروفایل اپلی، بخش‌های ادغام‌شده و ورقهٔ پشتیبانی
   ──────────────────────────────────────────────────────────────────────────
   سه بخش بیشتر نیست، به‌علاوهٔ نورا پی که بالای صفحه کارت خودش را دارد:

     نورا پی            کارت بالای پروفایل، رنگ و آیکون خودش (فاز بعد)
     رویدادهای من        ثبت‌نام، بلیت و گواهی، کارنامهٔ حضور، نظرها
     باشگاه و امتیاز من  سطح، دستاورد، فروشگاه پاداش، دعوت دوستان
     اطلاعات و تنظیمات   اطلاعات من، فرم‌ها، حریم خصوصی و حذف حساب

   پشتیبانی و راهنما یک جا است: نوار چسبیده به نوار پایین، و ورقه‌ای که از
   پایین باز می‌شود. هر عددی که این‌جا دیده می‌شود از data.js می‌آید.
   ══════════════════════════════════════════════════════════════════════════ */
(function(){
'use strict';
const N=window.NORA||{};
const ACCOUNT=N.ACCOUNT||{}, POL=ACCOUNT.policy||{}, SUP=ACCOUNT.support||{};
const SECT=ACCOUNT.sections||[], BASE=SECT.filter(x=>!x.card), PAY=SECT.find(x=>x.card)||null;
const EVENTS=N.EVENTS||[], PAST=N.PAST||[], CERTS=N.CERTS||{}, FAQ=N.FAQ||[], PEOPLE=N.PEOPLE||{};
const ACH=ACCOUNT.achievements||[], STORE=ACCOUNT.rewardStore||[], SCORE=ACCOUNT.score||{};
const FIELDS=ACCOUNT.fields||[], LEVELS=ACCOUNT.levels||[], FLOW=ACCOUNT.flow||[];

const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=t=>String(t==null?'':t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const UI=()=>window.NORA_UI||{};
const faN=n=>String(n==null?'':n).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
const unFa=s=>String(s==null?'':s).replace(/[۰-۹]/g,d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/[٠-٩]/g,d=>'٠١٢٣٤٥٦٧٨٩'.indexOf(d));
const faNum=n=>faN(String(Math.round(+n||0)).replace(/\B(?=(\d{3})+(?!\d))/g,'٬'));

const PTABS=ACCOUNT.profileTabs||[], PANEL=['info','club','forms','privacy'];
const S={view:'',tab:'up',edit:false,errs:{},after:'',ptab:'info'};
const uid=()=>UI().uid?UI().uid():'';
const login=()=>!!uid();
const sess=()=>UI().sessUser?UI().sessUser():{};
const prof=()=>UI().profile?UI().profile():{};
const phone=()=>UI().phoneOf?UI().phoneOf():'';
const pcOf=p=>UI().profilePercent?UI().profilePercent(p,!!phone()):0;
const missOf=p=>UI().profileMissing?UI().profileMissing(p,!!phone()):[];
const lvl=()=>UI().levelOf?UI().levelOf(+ACCOUNT.points||0):{cur:{},next:null};
const statusOf=p=>(p&&p.status)||'draft';
const ST={draft:['تکمیل نشده','warn'],pending:['در صف تأیید','brand'],approved:['تأیید شده','ok'],rejected:['رد شده','stop']};
const P_STATUS=['draft','pending','approved','rejected'];

/* ── تاریخ فارسی برای سابقهٔ پروفایل ── */
function nowFa(){
  try{
    const parts=new Intl.DateTimeFormat('fa-IR-u-ca-persian',{day:'numeric',month:'long',year:'numeric',hour:'2-digit',minute:'2-digit'}).formatToParts(new Date());
    const g=k=>(parts.find(x=>x.type===k)||{}).value||'';
    return (g('hour')?g('hour')+':'+g('minute')+' · ':'')+g('day')+' '+g('month')+' '+g('year');
  }catch(e){return 'همین حالا'}
}
const chip=(t,c)=>`<span class="tag ${c||''}">${esc(t)}</span>`;
const card=(t,s,body)=>`<div class="card acct"><div class="head">${esc(t)}</div>${s?`<div class="cap" style="margin-top:5px">${esc(s)}</div>`:''}${body||''}</div>`;
const note=(txt,i)=>`<p class="note"><svg class="i" aria-hidden="true"><use href="#${i||'i-sparkle'}"/></svg><span>${esc(txt)}</span></p>`;
const statT=(v,l)=>`<div class="stat2"><b>${v}</b><small>${esc(l)}</small></div>`;
const empty=(t,s)=>`<div class="gate"><svg class="i" aria-hidden="true"><use href="#i-archive"/></svg>
  <div class="gt">${esc(t)}</div><div class="gs">${esc(s)}</div></div>`;

/* ── فایل و کپی ── */
function saveFile(name,txt,msg){
  try{
    const url=URL.createObjectURL(new Blob([txt],{type:'text/plain;charset=utf-8'}));
    const a=document.createElement('a'); a.href=url; a.download=name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),4000); toast(msg);
  }catch(e){ toast('این مرورگر فایل نمی‌سازد؛ از پشتیبانی بخواه برایت بفرستند') }
}

/* ── منوی پروفایل: کد بخش، نشانی، و اگر مهمان بودی برو ورود ── */
function go(k){
  if(!login()&&k!=='support'){ S.after=k; loginSheet(); return }
  if(k==='support'){ openSupport(); return }
  location.hash='#'+k;
}

/* ══ سرِ پروفایل: نمای اپلی ═══════════════════════════════════════════ */
function hubHeader(){
  if(!login()){
    return `<div class="pcard">
      <div class="cover"></div>
      <div class="body">
        <div class="top">
          <span class="av" style="background:var(--surface-sunk);color:var(--ink-3)">؟</span>
          <span class="who"><b>خوش آمدی</b><small>تو حساب خودت را همین‌جا می‌بینی</small></span>
        </div>
        <p class="sub" style="margin:12px 0 0">اطلاعات حساب، رویدادها، بلیت و گواهی و امتیازت،
          همه مالِ حساب خودت است. با شمارهٔ موبایل و کد یک‌بارمصرف وارد شو؛ رمزی ندارد.</p>
        <button class="btn primary guestbtn" data-login><svg class="i" aria-hidden="true"><use href="#i-mobile"/></svg> ورود با شمارهٔ موبایل</button>
        <p class="cap" style="margin:9px 2px 0">بی ورود هم پشتیبانی و راهنما از پایین همین صفحه باز است.</p>
      </div></div>`;
  }
  const p=prof(), u=sess(), pc=pcOf(p), miss=missOf(p), st=ST[statusOf(p)]||ST.draft;
  const {cur,next}=lvl(), pts=+ACCOUNT.points||0;
  const initial=String(p.fullName||u.name||'ن').trim().slice(0,1)||'ن';
  const missTxt=miss.length?faN(miss.length)+' مورد مانده: '+miss.slice(0,2).map(f=>f.l).join('، '):'اطلاعات کامل است';
  return `<div class="pcard">
    <div class="cover"></div>
    <div class="body">
      <div class="top">
        <span class="av">${esc(initial)}</span>
        <span class="who"><b>${esc(p.fullName||u.name||'کاربر نورا')} ${chip(st[0],st[1])}</b>
          <small>عضو از ${esc(u.joined||ACCOUNT.joined||'—')} · سطح ${esc(cur.n||'—')}</small></span>
        <button class="icon-btn edit" data-go="account" aria-label="ویرایش اطلاعات حساب">
          <svg class="i"><use href="#i-pen"/></svg></button>
      </div>
      <div class="pstats">
        <button class="pstat" data-go="club"><b>${faNum(pts)}</b><small>امتیاز</small></button>
        <button class="pstat" data-go="club"><b>${esc(cur.n||'—')}</b><small>${next?('تا '+esc(next.n)+' '+faNum(next.at-pts)+' امتیاز'):'بالاترین سطح'}</small></button>
        <button class="pstat" data-go="events"><b>${faN(EVENTS.length)}</b><small>برنامهٔ پیش‌رو</small></button>
      </div>
      <div class="meter" role="img" aria-label="اطلاعات حساب ٪${faN(pc)} کامل است"><i style="width:${pc}%"></i></div>
      <div class="mfoot"><span class="cap">اطلاعات حساب: ٪${faN(pc)} کامل · ${esc(missTxt)}</span>
        <span class="sp" style="flex:1"></span>
        <button class="btn sm ${miss.length?'primary':'quiet'}" data-go="account">
          <svg class="i" aria-hidden="true"><use href="#i-${miss.length?'pen':'check'}"/></svg> ${miss.length?'تکمیل اطلاعات':'ویرایش'}</button></div>
    </div></div>`;
}

/* ══ نورا پی: کارت بالای پروفایل، رنگ و آیکون خودش ═══════════════════ */
function payCard(){
  if(!PAY) return '';
  const bits=(POL.payBits||['کیف پول','شارژ','صورت‌حساب','اقساط']).slice(0,4);
  return `<button class="paycard" data-go="pay" aria-label="${esc(PAY.n)} — ${esc(PAY.en||'')}">
    <span class="ptop">
      <span class="pico"><svg class="i" aria-hidden="true"><use href="#i-wallet"/></svg></span>
      <span class="pnames"><span class="pen">${esc(PAY.en||'nora pay')}</span><span class="pfa">${esc(PAY.n)}</span></span>
      <span class="pchip">فاز بعد</span>
    </span>
    <span class="prow">
      <span class="psum"><b>به‌زودی</b><small>${login()?'کیف پول و پرداخت‌ها هنوز فعال نشده':'با ورود، کیف پول خودت را می‌بینی'}</small></span>
      <span class="pgo">دیدن طرح<svg class="i" aria-hidden="true" style="width:14px;height:14px"><use href="#i-chev-left"/></svg></span>
    </span>
    <span class="pbits">${bits.map(b=>`<span>${esc(b)}</span>`).join('')}</span>
  </button>`;
}

/* ══ بخش‌ها: سه ردیف ══════════════════════════════════════════════════ */
function hubRows(){
  return `<div class="mrows">${BASE.map(x=>{
    const sub=subline(x.k);
    return `<button class="mrow2" data-go="${x.k}">
      <span class="ic"><svg class="i" aria-hidden="true"><use href="#${x.i}"/></svg></span>
      <span class="tx"><b>${esc(x.n)}</b><small>${esc(sub||x.s)}</small></span>
      <svg class="i chev" aria-hidden="true"><use href="#i-chev-left"/></svg></button>`}).join('')}</div>`;
}
function subline(k){
  if(!login()) return '';
  const p=prof();
  if(k==='events') return faN(EVENTS.length)+' برنامهٔ پیش‌رو · '+faN(PAST.length)+' برگزارشده';
  if(k==='profile') return 'اطلاعات ٪'+faN(pcOf(p))+' کامل · '+((lvl().cur||{}).n||'—')+
    ' با '+faNum(+ACCOUNT.points||0)+' امتیاز';
  return '';
}
function renderHub(){ $('#hubBox').innerHTML=hubHeader()+payCard()+hubRows(); }

/* ══ نما: سر، تب و قاب هر بخش ════════════════════════════════════════ */
function viewHead(x,action,sub){
  return `<div class="vhead">
      <button class="btn sm quiet" data-back><svg class="i" aria-hidden="true"><use href="#i-chev-left"/></svg> حساب من</button>
      <span class="sp" style="flex:1"></span>${action||''}</div>
    <h2 class="vh2">${esc(x.n)}</h2><p class="vhsub">${esc(sub||x.s)}</p>`;
}
const gate=(x)=>login()?'':
  card('این بخش با حساب خودت باز می‌شود','با شمارهٔ موبایل و کد یک‌بارمصرف وارد شو؛ «'+x.n+'» مالِ حساب خودت است.',
    `<div class="gate"><svg class="i" aria-hidden="true"><use href="#i-lock"/></svg>
      <div class="gacts"><button class="btn primary" data-login><svg class="i" aria-hidden="true"><use href="#i-mobile"/></svg> ورود با شمارهٔ موبایل</button>
        <button class="btn quiet" data-go="support">پشتیبانی، بی ورود</button></div></div>`);

const V={};

/* ── رویدادهای من: ثبت‌نام، بلیت و گواهی، کارنامهٔ حضور، نظرها ── */
const TABS=[{k:'up',n:'پیش‌رو'},{k:'past',n:'برگزارشده'},{k:'tickets',n:'بلیت و گواهی'},
            {k:'attend',n:'کارنامهٔ حضور'},{k:'reviews',n:'نظرهای من'}];
function evRow(e){
  return `<div class="erow">
    <span class="dbox" style="background:${esc(e.g||'var(--surface-2)')};color:#fff">
      <small>${esc(e.dm||'')}</small><b>${faN(e.dn||'')}</b></span>
    <span class="ex"><b>${esc(e.t)}</b><small>${esc([e.kind,e.when,e.time,e.place].filter(Boolean).join(' · '))}</small>
      <span class="acts">${chip('ثبت‌نام قطعی','ok')}${e.cert?chip('گواهی‌دار'):''}
        <button class="btn sm quiet" data-tab-go="tickets"><svg class="i" aria-hidden="true"><use href="#i-qr"/></svg> کارت ورود</button>
        <button class="btn sm quiet" data-goto="events.html?ev=${esc(e.id)}">صفحهٔ رویداد</button>
        <button class="btn sm quiet" data-cancel-ev="${esc(e.id)}">لغو ثبت‌نام</button></span></span></div>`;
}
function pastRow(h){
  return `<div class="erow">
    <span class="dbox" style="background:${esc(h.g||'var(--surface-2)')};color:#fff"><small>${esc(h.dm||'')}</small><b>${faN(h.dn||'')}</b></span>
    <span class="ex"><b>${esc(h.t)}</b><small>${esc([h.d,h.rec,h.place].filter(Boolean).join(' · '))}</small>
      <span class="acts">${h.cert?chip('گواهی‌دار'):''}${chip('حضور ثبت شد','ok')}
        <button class="btn sm quiet" data-tab-go="attend">کارنامهٔ حضور</button>
        <button class="btn sm quiet" data-goto="events.html?ev=${esc(h.id)}">ضبط و جزوه</button></span></span></div>`;
}
function certPanel(){
  const p=prof(), u=sess(), {cur}=lvl();
  const mine=Object.entries(CERTS).filter(([,v])=>v.n===(u.name||''));
  const card0=`<div class="idcard">
    <div class="c1"><span class="av2">${esc(String(p.fullName||u.name||'ن').slice(0,1))}</span>
      <span class="nm"><b>${esc(p.fullName||u.name||'کاربر نورا')}</b>
        <small>سطح ${esc(cur.n||'')} · عضو از ${esc(u.joined||ACCOUNT.joined||'')}</small></span></div>
    <div class="meta"><span><small>کد عضویت</small><span dir="ltr">NL-${esc(unFa(phone()).replace(/\D/g,'').slice(-4))}</span></span>
      <span><small>شمارهٔ تماس</small>${esc(faN(phone()||'—'))}</span></div>
    <div class="ser">NORA · LIFELINE</div>
    <div class="brandline"><svg class="i" aria-hidden="true" style="width:14px;height:14px"><use href="#i-idcard-f"/></svg>
      کارت ورود برنامه‌ها؛ در ورودی همین را نشان بده</div></div>`;
  const certs=mine.length?mine.map(([ser,v])=>`<div class="tk">
      <svg class="i" aria-hidden="true" style="width:20px;height:20px;color:var(--brand)"><use href="#i-medal"/></svg>
      <span class="tx"><b>${esc(v.c)}</b><small>${esc(v.d)} · ${esc(v.h)} · سریال <span dir="ltr">${esc(ser)}</span></small>
        <span class="acts"><button class="btn sm quiet" data-cert-dl="${esc(ser)}"><svg class="i" aria-hidden="true"><use href="#i-send"/></svg> دانلود</button>
          <button class="btn sm quiet" data-goto="home.html#verify">استعلام</button></span></span></div>`).join('')
    :empty('هنوز گواهی‌ای صادر نشده','بعد از هر رویداد، اگر شرط حضورش را داشته باشی، گواهی همین‌جا می‌آید.');
  return card0+card('گواهی‌های من','گواهی دیجیتال با سریال یکتا، آمادهٔ دانلود و استعلام',
    certs+note('اعتبار پیش‌فرض گواهی‌ها '+faN(POL.certValidMonths||24)+' ماه است و در تنظیمات رویداد قابل تغییر است.','i-clock'))+
    card('سفارش گواهی','رایگان، ویژه، چاپی و VIP؛ هر کدام شرایط خودش را دارد',`<div class="kinds">
      ${(POL.certKinds||[]).map(k=>`<div class="kind">
        <svg class="i" aria-hidden="true" style="width:19px;height:19px;color:var(--ink-4)"><use href="#i-medal"/></svg>
        <span class="tx"><b>${esc(k.n)}</b><small>${esc(k.s)}</small></span>
        <button class="btn sm ${k.k==='free'?'quiet':'primary'}" data-cert-req="${esc(k.k)}">${k.k==='free'?'دریافت':'سفارش'}</button></div>`).join('')}
      </div>${note('گواهی چاپی و VIP بعد از تأیید سرپرست صادر و ارسال می‌شود.','i-shield')}`);
}
function attendPanel(){
  const M=[62,74,80,58,90,55,72,84,78,88,92,70], pct=SCORE.attend||88;
  const rows=PAST.slice(0,5).map((h,i)=>`<div class="tk">
      <svg class="i" aria-hidden="true" style="width:19px;height:19px;color:${i===3?'var(--stop)':'var(--ok)'}"><use href="#i-${i===3?'close':'check'}"/></svg>
      <span class="tx"><b>${esc(h.t)}</b><small>${esc(h.d)} · ${esc(h.place||'')}</small></span>
      ${i===3?chip('غیبت','stop'):chip('حضور','ok')}</div>`).join('');
  return card('حال و روز حضور','درصد حضور و روند ماه‌به‌ماه',
      `<div class="stats">${statT('٪'+faN(pct),'درصد حضور')}${statT(faN(22),'جلسه')}${statT(faN(3),'غیبت')}${statT(faN(170),'دقیقهٔ میانگین')}</div>
      <div class="bars" role="img" aria-label="روند حضور در دوازده ماه گذشته">
        ${M.map(v=>`<i style="height:${v}%" class="${v<60?'off':''}"></i>`).join('')}</div>
      <div class="barscap"><span class="cap">۱۲ ماه گذشته</span><span class="sp" style="flex:1"></span>
        <span class="cap">نوار کم‌رنگ: ماه‌های زیر ٪۶۰</span></div>`)+
    card('جلسه‌به‌جلسه','پنج برنامهٔ آخر، با حضور و غیبت',rows+
      note('گواهی هر رویداد بر پایهٔ همان شرط حضوری صادر می‌شود که برای آن رویداد گذاشته شده است.','i-clock'));
}
function reviewPanel(){
  const revs=[{t:(PAST[0]||{}).t||'کارگاه عکاسی', d:'۲۲ مرداد', r:5, x:'ضبط‌ها و جزوهٔ تنظیمات خیلی کمک کرد؛ تمرین‌های هفتگی هم پیگیری می‌شد.'},
              {t:(PAST[1]||{}).t||'کارگاه فن بیان', d:'۹ مرداد', r:4, x:'جلسه‌ها منظم بود و وقت پرسش می‌گذاشتند؛ جای تمرین گروهی بیشتر خالی بود.'}];
  return card('نظرهایی که نوشتی','نظر هر برنامه، بعد از برگزاری باز می‌شود',
      revs.map(v=>`<div class="tk">
        <svg class="i" aria-hidden="true" style="width:19px;height:19px;color:var(--warn)"><use href="#i-star"/></svg>
        <span class="tx"><b>${esc(v.t)}</b><small>${esc(v.d)} · ${'★'.repeat(v.r)}${'☆'.repeat(5-v.r)}</small>
          <span class="cap" style="margin-top:4px;line-height:1.85">${esc(v.x)}</span></span></div>`).join('')+
      note('برای هر نظری که می‌نویسی امتیاز می‌گیری؛ جمعش در باشگاه من می‌آید.','i-star'));
}
V.events=function(x){
  const g=gate(x); if(g) return viewHead(x)+g;
  const body = S.tab==='up' ? EVENTS.slice(0,3).map(evRow).join('')
    : S.tab==='past' ? PAST.slice(0,2).map(pastRow).join('')
    : S.tab==='tickets' ? certPanel()
    : S.tab==='attend' ? attendPanel()
    : reviewPanel();
  const inner = S.tab==='tickets'||S.tab==='attend'||S.tab==='reviews' ? body
    : card(S.tab==='up'?'ثبت‌نام‌های پیش‌رو':'برگزارشده‌ها',
        S.tab==='up'?'کارت ورود، صفحهٔ رویداد و لغو، همه از همین‌جا':'ضبط، جزوه و گواهی هر برنامه',body);
  return viewHead(x,'','هر چه ثبت‌نام کرده‌ای: بلیت و گواهی، کارنامهٔ حضور و نظرها')+`
    <div class="vtabs" role="tablist">${TABS.map(t=>`<button class="vtab${S.tab===t.k?' on':''}" role="tab"
      aria-selected="${S.tab===t.k}" data-tab="${t.k}">${esc(t.n)}</button>`).join('')}</div>${inner}
    ${S.tab==='up'?note('شرایط لغو و بازگشت مبلغ، در صفحهٔ هر رویداد نوشته شده است.','i-shield'):''}`;
};

/* ── باشگاه و امتیاز من ── */
function invitePanel(){
  const code='NORA-'+unFa(phone()).replace(/\D/g,'').slice(-4), need=POL.inviteNeed||2, done=+SCORE.invites||0;
  return card('دعوت دوستان','هر دوست که با این کد بیاید، به حساب تو هم اعتبار می‌رسد',
    `<div class="srow" style="border:0;padding:6px 0">
      <span class="sp" style="font-size:20px;letter-spacing:2px" dir="ltr">${esc(code)}</span>
      <button class="btn sm quiet" data-copy="${esc(code)}"><svg class="i" aria-hidden="true"><use href="#i-link"/></svg> کپی</button></div>
    <div class="stats">${statT(faN(done)+' از '+faN(need),'دعوت ثبت‌شده')}${statT(faNum(0),'اعتبار گرفته')}</div>
    <div class="srow" style="margin-top:10px"><svg class="i" aria-hidden="true"><use href="#i-send"/></svg>
      <span class="sp">عضویت در کانال نورا</span>${chip('انجام شد','ok')}</div>
    <div class="srow"><svg class="i" aria-hidden="true" style="color:var(--ink-4)"><use href="#i-users"/></svg>
      <span class="sp">دعوت ${faN(need)} دوست</span>${chip(faN(done)+' از '+faN(need),done>=need?'ok':'warn')}</div>`);
}
function clubPanel(){
  const pts=+ACCOUNT.points||0, {cur,next}=lvl(), cap=POL.pointsCap||{};
  return card('امتیاز و سطح من','هر ثبت‌نام، حضور و فرم امتیاز دارد؛ دستاوردها هم جدا حساب می‌شوند',
      `<div class="stats">${statT(faNum(pts),'امتیاز')}${statT(esc(cur.n||''),'سطح')}
        ${statT(next?faNum(next.at-pts):'—','تا سطح بعدی')}
        ${statT(faN(SCORE.rank||'')+' از '+faNum(SCORE.of||0),'رتبهٔ '+(SCORE.month||'این ماه'))}</div>
      <div class="ladder" style="margin-top:12px">${LEVELS.map(l=>`<div class="lvrow ${l.k===cur.k?'on':''}">
        <span class="dot2"></span><span class="tx"><b>${esc(l.n)}</b><small>${esc(l.perks)}</small></span>
        <span class="at">${faNum(l.at)} امتیاز</span></div>`).join('')}</div>
      ${note('سقف‌های محافظ: هر امتیاز تا '+faN(cap.each||100)+'، روزانه تا '+faN(cap.day||50)+' و ماهانه تا '+faN(cap.month||300)+' واحد.','i-shield')}`)+
    card('دستاوردها','هر کدام که قفل است، کار خودش را می‌خواهد',`<div class="acks">
      ${ACH.map(a=>`<div class="ack${a.on?' on':''}"><svg class="i" aria-hidden="true"><use href="#${a.i}"/></svg>
        <b>${esc(a.n)}</b><small>${a.on?esc(a.r||'گرفته‌ای'):faNum(a.at)+' امتیاز'}</small></div>`).join('')}</div>`)+
    card('فروشگاه پاداش','هر چه امتیاز داری، خرجش کن','<div class="kinds">'+
      STORE.map(r=>{const can=pts>=r.cost; return `<div class="kind">
        <svg class="i" aria-hidden="true" style="width:19px;height:19px;color:var(--ink-4)"><use href="#i-wallet"/></svg>
        <span class="tx"><b>${esc(r.n)}</b><small>${esc(r.s)}</small></span>
        <button class="btn sm ${can?'primary':'quiet'}" ${can?'':'disabled'} data-reward="${esc(r.n)}">${faNum(r.cost)} امتیاز</button></div>`}).join('')+
      '</div>')+invitePanel();
}

/* ── اطلاعات و تنظیمات ── */
const ERR={};
function validNationalId(v){
  const d=unFa(v).replace(/\D/g,'');
  if(!/^\d{10}$/.test(d)) return false;
  if(/^(\d)\1{9}$/.test(d)) return false;
  const w=[10,9,8,7,6,5,4,3,2];
  let s=0; for(let i=0;i<9;i++) s+=(+d[i])*w[i];
  const r=+d[9], m=s%11;
  return m<2 ? r===m : r===11-m;
}
function validBirth(v){
  const d=unFa(v).replace(/[^\d/]/g,'');
  const m=d.match(/^(1[23]\d{2})\/(\d{1,2})\/(\d{1,2})$/);
  if(!m) return false;
  const y=+m[1], mo=+m[2], day=+m[3];
  return y>=1300&&y<=1420&&mo>=1&&mo<=12&&day>=1&&day<=31;
}
function validate(p){
  const e={};
  for(const f of FIELDS){
    const v=String(p[f.k]||'').trim();
    if(f.lock){ if(!v) e[f.k]='از حساب خودت خوانده می‌شود؛ یک بار بیرون بیا و دوباره وارد شو'; continue }
    if(f.req&&!v){e[f.k]='این یکی اجباری است'; continue}
    if(!v) continue;
    if(f.k==='nationalId'&&!validNationalId(v)) e[f.k]='کد ملی ۱۰ رقمی درست نیست';
    if(f.k==='birthDate'&&!validBirth(v)) e[f.k]='تاریخ را شمسی بنویس، مثل ۱۳۷۰/۰۱/۱۵';
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
    ${bad?`<span class="err" id="e_${f.k}" role="alert">${esc(bad)}</span>`:(f.hint?`<span class="hint" id="h_${f.k}">${esc(f.hint)}${f.lock?': برای عوض‌کردنش با پشتیبانی حرف بزن':''}</span>`:'')}`;
}
function infoPanel(){
  const p=prof(), filled=UI().profileFilled?UI().profileFilled(p,!!phone()):{}, st=ST[statusOf(p)]||ST.draft;
  const groups=[]; FIELDS.forEach(f=>{ if(!groups.includes(f.g)) groups.push(f.g) });
  const body=groups.map(g=>`<div class="grp"><div class="gt">${esc(g)}</div>
    ${FIELDS.filter(f=>f.g===g).map(f=>S.edit
      ? `<div class="fld${S.errs[f.k]?' bad':''}">${fieldEdit(f,p)}</div>`
      : `<div class="fld"><span class="hint">${esc(f.l)}</span>${fieldView(f,p)}</div>`).join('')}</div>`).join('');
  const acts=S.edit?`<div class="row" style="margin-top:14px">
      <button class="btn primary" id="sendBtn"><svg class="i" aria-hidden="true"><use href="#i-check"/></svg> ذخیره و ارسال برای تأیید</button>
      <button class="btn quiet" id="draftBtn">فقط ذخیره</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" id="cancelBtn">انصراف</button></div>`:
    `<div class="row" style="margin-top:12px"><button class="btn ${missOf(p).length?'primary':'quiet'}" id="editBtn">
      <svg class="i" aria-hidden="true"><use href="#i-pen"/></svg> ${missOf(p).length?'تکمیل اطلاعات':'ویرایش اطلاعات'}</button></div>`;
  return card('اطلاعات حساب من','همان چیزی که روی بلیت و گواهی می‌آید؛ تغییرات اول به کارشناس می‌رود',
      `<div class="row" style="align-items:center;gap:8px;margin-top:2px"><span class="cap">وضعیت</span>${chip(st[0],st[1])}
        <span class="sp" style="flex:1"></span><span class="cap">٪${faN(pcOf(p))} کامل</span></div>${body}${acts}`);
}
function flowPanel(){
  const p=prof(), st=statusOf(p), hist={}; (p.history||[]).forEach(h=>{hist[h.k]=h.at});
  const done={filled:['draft','pending','approved'],pending:['pending','approved'],approved:['approved']};
  const hit=k=>(done[k]||[]).includes(st);
  const steps=FLOW.map(f=>{
    const on=hit(f.k), now=(st==='pending'&&f.k==='pending');
    return `<div class="step ${on?'done':''} ${now?'now':''}">
      <span class="dot"><svg class="i" aria-hidden="true"><use href="#i-${on?'check':f.k==='pending'?'clock':'pen'}"/></svg></span>
      <span class="tt"><b>${esc(f.n)}</b><small>${esc(f.s)}</small></span>
      <span class="at">${esc(hist[f.k]||(on?'':'—'))}</span></div>`}).join('');
  const tail = st==='rejected' ? `<span class="err" style="display:block;margin-top:8px">دلیل رد: ${esc(p.reason||'نامشخص')}</span>`
    : st==='pending' ? '<p class="cap" style="margin:10px 3px 0">معمولاً تا یک روز کاری بررسی می‌شود.</p>'
    : st==='approved' ? '<p class="cap" style="margin:10px 3px 0">پروفایلت تأیید شده است؛ اگر چیزی را عوض کردی، دوباره می‌رود صف تأیید.</p>'
    : '<p class="cap" style="margin:10px 3px 0">هر وقت اطلاعات را فرستادی، وضعیتش همین‌جا عوض می‌شود.</p>';
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
  return card('حریم خصوصی','اطلاعاتت را می‌توانی برداری یا حساب را ببندی',`
      <div class="srow" style="border-bottom:.5px solid var(--hairline-2)">
        <svg class="i" aria-hidden="true"><use href="#i-doc"/></svg>
        <span class="sp">دانلود اطلاعات من<small class="cap" style="display:block">پروفایل، خریدها، اعلان‌ها و آمار، یک فایل</small></span>
        <button class="btn sm quiet" id="dlBtn"><svg class="i" aria-hidden="true"><use href="#i-send"/></svg> دانلود</button></div>
      <div class="srow" style="border-bottom:0">
        <svg class="i" aria-hidden="true" style="color:var(--stop)"><use href="#i-shield"/></svg>
        <span class="sp">حذف حساب کاربری<small class="cap" style="display:block">بلیت‌ها، گواهی‌ها و سابقهٔ حضور هم پاک می‌شود</small></span>
        <button class="btn sm stop" id="delBtn" ${asked?'disabled':''}>${asked?'ثبت شد':'درخواست حذف'}</button></div>
      <div class="cap" id="delNote" style="margin-top:10px">${asked?'درخواستت ثبت شده؛ کارشناس برای تأیید خبر می‌دهد.':''}</div>`)+
    note('حذف حساب بی‌برگشت است؛ برای همین سه تأیید می‌گیریم: تأیید، تایپ «حذف» و کد پیامکی.','i-lock')+
    card('چه چیزی نگه می‌داریم','شفاف و کوتاه',`<div class="stack tight">
      <div class="srow"><svg class="i" aria-hidden="true"><use href="#i-check"/></svg><span class="sp">اطلاعات پروفایل، برای بلیت و گواهی</span></div>
      <div class="srow"><svg class="i" aria-hidden="true"><use href="#i-check"/></svg><span class="sp">سابقهٔ خرید و حضور، برای کارنامهٔ تو</span></div>
      <div class="srow"><svg class="i" aria-hidden="true"><use href="#i-lock"/></svg><span class="sp">شمارهٔ موبایل، فقط برای ورود و یادآوری</span></div></div>`);
}
/* پروفایل من: چهار تب، همهٔ چیزهایی که به خودِ عضو برمی‌گردد */
V.profile=function(x){
  const g=gate(x); if(g) return viewHead(x)+g;
  const tabs=PTABS.length?PTABS:[{k:'info',n:'اطلاعات من'}];
  const body=S.ptab==='club' ? clubPanel()
    : S.ptab==='forms' ? formsPanel()
    : S.ptab==='privacy' ? privacyPanel()
    : infoPanel()+flowPanel();
  const sub=(tabs.find(t=>t.k===S.ptab)||{}).s||'';
  return viewHead(x,'',sub)+`
    <div class="vtabs" role="tablist">${tabs.map(t=>`<button class="vtab${S.ptab===t.k?' on':''}" role="tab"
      aria-selected="${S.ptab===t.k}" data-ptab="${t.k}">${esc(t.n)}</button>`).join('')}</div>${body}`;
};
V.pay=function(x){
  const bits=POL.payBits||['کیف پول و شارژ','صورت‌حساب','بازگشت وجه','اقساط و پیش‌پرداخت','کد تخفیف','تسویه با گروه'];
  return viewHead(x)+card('نورا پی','این بخش را در یک فاز جدا می‌سازیم',`
      <div class="gate"><svg class="i" aria-hidden="true"><use href="#i-wallet"/></svg>
        <div class="gt">فعلاً قفل است</div>
        <div class="gs">حساب، رویدادها و امتیاز کار می‌کند؛ کیف پول و پرداخت‌ها فاز بعد می‌آید
          تا شماره‌ها و صورت‌حساب‌ها از اول درست بنشینند.</div>
        <div class="chipsline" style="justify-content:center">${bits.map(b=>chip(b)).join('')}</div>
        <div class="gacts"><button class="btn primary" data-go="support">پیشنهادت را بگو</button>
          <button class="btn quiet" data-go="events">رویدادهای من</button></div></div>`);
};

/* ══ پشتیبانی و راهنما: یک ورقه، از پایین ════════════════════════════ */
function supportHTML(){
  const sup=(PEOPLE||[]).find(p=>p.id==='p6')||{}, cats=POL.ticketCats||[], maxOpen=+POL.ticketMaxOpen||3;
  const chans=[
    {i:'i-mobile',t:'تلفن پشتیبانی',v:'۰۲۱–۸۸۸۸۱۲۳۴',href:'tel:+982188881234',s:'۹ تا ۱۸، روزهای کاری'},
    {i:'i-mail',t:'رایانامه',v:'info@lifeline1.ir',href:'mailto:info@lifeline1.ir',s:'پاسخ در یک روز کاری'},
    {i:'i-send',t:'بله',v:'@nora_support',href:'https://ble.ir/nora_support',s:'گفت‌وگوی سریع'},
    {i:'i-link',t:'تلگرام',v:'@nora_support',href:'https://t.me/nora_support',s:'گفت‌وگوی سریع'}
  ];
  return `<div class="grabber"></div>
    <div class="row" style="align-items:center;margin-bottom:10px">
      <div><div class="head">${esc(SUP.n||'پشتیبانی و راهنما')}</div>
        <div class="cap">${esc(SUP.s||'')}</div></div>
      <span class="sp"></span><button class="icon-btn" data-close aria-label="بستن"><svg class="i"><use href="#i-close"/></svg></button></div>
    <div class="suphead"><span class="av3">${esc(String(sup.n||'حسن مقدم').slice(0,1))}</span>
      <span style="flex:1;min-width:0"><b class="sub">${esc(sup.n||'حسن مقدم')}</b>
        <div class="cap">کارشناس پشتیبانی نورا · پاسخ تا پایان روز کاری</div></span>
      ${chip('آنلاین','ok')}</div>
    ${chans.map(c=>`<a class="chan" href="${esc(c.href)}" ${c.href.startsWith('http')?'target="_blank" rel="noopener"':''}>
      <span class="chi"><svg class="i"><use href="#${c.i}"/></svg></span>
      <span class="cht"><b>${esc(c.t)}</b><span>${esc(c.v)}</span></span>
      <svg class="i" style="width:15px;height:15px;color:var(--ink-4)"><use href="#i-chev-left"/></svg></a>`).join('')}
    <hr class="hr"/>
    <div class="cap" style="margin-bottom:2px">تیکت‌های من — بیشتر از ${faN(maxOpen)} تیکت باز نمی‌ماند</div>
    <div class="chipsline">${cats.map(c=>chip(c)).join('')}</div>
    <div class="tk" style="margin-top:8px">
      <svg class="i" aria-hidden="true" style="width:19px;height:19px;color:var(--brand)"><use href="#i-headphone"/></svg>
      <span class="tx"><b>گواهی کارگاه عکاسی</b><small>دستهٔ گواهی · ۲ مهر</small>
        <span class="acts">${chip('در حال بررسی','brand')}<span class="cap">پاسخ‌دهنده: ${esc(sup.n||'حسن مقدم')}</span></span></span></div>
    <div class="row" style="margin-top:10px"><button class="btn sm primary" data-ticket-new>
      <svg class="i" aria-hidden="true"><use href="#i-pen"/></svg> تیکت تازه</button>
      <span class="sp" style="flex:1"></span><span class="cap">۱ از ${faN(maxOpen)} تیکت باز</span></div>
    <hr class="hr"/>
    <div class="cap" style="margin-bottom:4px">پرسش‌های پرتکرار</div>
    ${FAQ.map((f,i)=>`<details class="faq" ${i===0?'open':''}><summary>${esc(f[0])}</summary><p>${esc(f[1])}</p></details>`).join('')}
    <hr class="hr"/>
    <div class="cap" style="margin-bottom:4px">دربارهٔ نورا</div>
    <div class="abrow"><svg class="i" aria-hidden="true"><use href="#i-users"/></svg>
      <span class="sp">گروه فرهنگی خط زندگی<small>تهران، خیابان ولی‌عصر، پلاک ۱۲ · کتابخانهٔ نورا</small></span></div>
    <a class="abrow" href="https://lifeline1.ir" target="_blank" rel="noopener" style="color:inherit;text-decoration:none">
      <svg class="i" aria-hidden="true"><use href="#i-link"/></svg>
      <span class="sp">lifeline1.ir<small>پایگاه گروه و گزارش‌ها</small></span></a>
    <label class="lbl" for="msg" style="margin-top:12px">یا همین‌جا بنویس</label>
    <textarea class="input" id="msg" rows="3" placeholder="مثلاً دربارهٔ تأیید رسید کارت‌به‌کارت سؤال دارم"></textarea>
    <div class="row" style="margin-top:12px"><button class="btn primary" data-sup-send>
      <svg class="i" aria-hidden="true"><use href="#i-send"/></svg> فرستادن پیام</button>
      <span class="sp" style="flex:1"></span><span class="cap">بی ورود هم کار می‌کند</span></div>`;
}
function fillSupport(){ fillSheet('shSupport',supportHTML()) }
function openSupport(){
  const b=$('#supBody');
  if(!b||!b.children.length) fillSupport();
  openSheet('shSupport');
}

/* ══ ویرایش و تأیید اطلاعات ═════════════════════════════════════════ */
function startEdit(){ if(!login()){ S.after='account'; loginSheet(); return } S.edit=true; S.errs={}; renderView();
  const el=$('#f_fullName'); if(el&&el.focus) el.focus() }
function cancelEdit(){ S.edit=false; S.errs={}; renderView() }
function collect(){
  const p=Object.assign({},prof());
  FIELDS.forEach(f=>{ if(f.lock){ p[f.k]=phone(); return } const el=$('#f_'+f.k); if(el) p[f.k]=el.value.trim() });
  return p;
}
function submit(send){
  if(!login()){ loginSheet(); return }
  const p=tidy(collect());
  if(send){
    const e=validate(p);
    if(Object.keys(e).length){ S.errs=e; renderView(); toast('چند جا مانده یا درست نیست؛ همان‌ها را ببین');
      const first=$('#editBox .fld.bad .input')||$('.fld.bad .input'); if(first&&first.focus) first.focus(); return }
  }
  const before=statusOf(prof());
  p.status=send?'pending':(before==='draft'?'draft':before);
  p.history=(p.history||[]).filter(h=>h.k!==(send?'pending':'filled'))
    .concat([{k:send?'pending':'filled',at:nowFa()}]);
  const saved=UI().saveProfile?UI().saveProfile(p):p;
  S.edit=false; S.errs={}; renderHub(); renderView();
  const miss=missOf(saved).length;
  toast(send?(miss?('فرستادیم برای تأیید؛ '+faN(miss)+' مورد هنوز خالی است'):'فرستادیم برای تأیید؛ نتیجه را خبر می‌دهیم'):'ذخیره شد');
}
function loginSheet(){ if(UI().authSheet) UI().authSheet(()=>{ S.edit=false; render(); if(S.after){ const k=S.after; S.after=''; if(k==='support') openSupport(); else location.hash='#'+k } }) }
function askDelete(){
  fillSheet('shConfirm',`<div class="grabber"></div>
    <div class="head">حذف حساب کاربری</div>
    <p class="sub" style="margin-top:8px">با حذف حساب، بلیت‌ها، گواهی‌ها و سابقهٔ حضور پاک می‌شود. این کار برنمی‌گردد،
      پس دو تأیید می‌گیریم: کلمهٔ «حذف» و کد پیامکی.</p>
    <label class="lbl" for="delWord" style="margin-top:12px">برای تأیید، کلمهٔ «حذف» را بنویس</label>
    <input class="input" id="delWord" value="" placeholder="حذف" autocomplete="off"/>
    <label class="lbl" for="delCode" style="margin-top:12px">کد پیامکی</label>
    <input class="input num" id="delCode" inputmode="numeric" placeholder="•••••" autocomplete="one-time-code"/>
    <div class="cap" style="margin-top:7px">کد نمایشی این نمونه: ۵۴۳۲۱</div>
    <div class="row" style="margin-top:14px"><button class="btn stop" id="delYes">حذف حساب</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" data-close>هنوز نه</button></div>`);
  openSheet('shConfirm');
}
function downloadInfo(){
  const u=sess();
  const pack={
    ساخته:new Date().toISOString(),
    حساب:{نام:u.name||'',موبایل:u.mobile||'',عضویت:u.joined||ACCOUNT.joined||'',سطح:lvl().cur.n||''},
    پروفایل:prof(),
    کتابخانه:UI().library?UI().library():[],
    رویدادها:{پیش‌رو:EVENTS.length,برگزارشده:PAST.length,رسانه:(N.ARCHIVE||{}).media||0}
  };
  saveFile('nora-account.json',JSON.stringify(pack,null,2),'فایل اطلاعات حسابت آماده شد');
}
function certDownload(ser){
  const v=CERTS[ser]||{};
  saveFile('nora-cert-'+ser+'.txt',
    ['گواهینامهٔ گروه فرهنگی خط زندگی','سریال: '+ser,'نام: '+(v.n||''),'برنامه: '+(v.c||''),
     'تاریخ: '+(v.d||''),'مدت: '+(v.h||''),'اعتبار: '+faN(POL.certValidMonths||24)+' ماه',
     'استعلام: https://lifeline1.ir/c/'+ser].join('\n'),'فایل گواهی آماده شد');
}
function certRequest(kind){
  const k=(POL.certKinds||[]).find(x=>x.k===kind)||{};
  if(kind==='free'){ toast('گواهی رایگان همین‌جا دانلود می‌شود؛ از فهرست بالا بگیر'); return }
  fillSheet('shConfirm',`<div class="grabber"></div><div class="head">سفارش ${esc(k.n||'گواهی')}</div>
    <p class="sub" style="margin-top:8px">${esc(k.s||'')}. بعد از ثبت سفارش، سرپرست تأیید می‌کند و بعد از آن صادر و ارسال می‌شود.</p>
    <div class="row" style="margin-top:14px"><button class="btn primary" data-cert-yes="${esc(kind)}">ثبت سفارش</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" data-close>بعداً</button></div>`);
  openSheet('shConfirm');
}
function cancelEvent(id){
  const e=EVENTS.find(x=>x.id===id)||{};
  fillSheet('shConfirm',`<div class="grabber"></div><div class="head">لغو ثبت‌نام</div>
    <p class="sub" style="margin-top:8px">«${esc(e.t||'این برنامه')}» را لغو کنم؟ شرایط بازگشت مبلغ، همان چیزی است که در صفحهٔ رویداد نوشته شده.</p>
    <div class="row" style="margin-top:14px"><button class="btn stop" data-cancel-yes="${esc(id)}">بله، لغو کن</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" data-close>نه</button></div>`);
  openSheet('shConfirm');
}

/* ══ رندر و مسیرها ═══════════════════════════════════════════════════ */
function renderView(){
  const box=$('#viewBox'), sec=BASE.concat(PAY?[PAY]:[]).find(x=>x.k===S.view);
  if(!box||!sec) return;
  box.innerHTML=`<section class="sec" aria-label="${esc(sec.n)}">${(V[S.view]||(()=>''))(sec)}</section>`;
  document.title='نورا · '+sec.n;
}
function render(){
  renderHub();
  const box=$('#viewBox'), sup=$('#supBar'), known=BASE.some(x=>x.k===S.view)||S.view==='pay';
  if(sup) sup.hidden=false;                       /* پشتیبانی همیشه چسبیده به نوار پایین */
  if(!known){
    S.view=''; box.hidden=true; box.innerHTML=''; document.title='نورا · حساب من';
  }else{
    box.hidden=false; renderView();
  }
}
/* نشانی‌های کوتاه: #club و #forms و #privacy و #account تب همان پروفایل‌اند */
const ALIAS={club:'club', forms:'forms', privacy:'privacy', account:'info', info:'info'};
function renderRoute(){
  const raw=(location.hash||'').replace('#','');
  if(raw==='support'||raw===''){ if(raw==='support') setTimeout(openSupport,60); S.view=''; render(); try{window.scrollTo({top:0})}catch(e){}; return }
  const k=raw.replace(/^sec-/,'');
  if(ALIAS[k]){ S.view='profile'; S.ptab=ALIAS[k]; S.edit=false; S.errs={}; render(); try{window.scrollTo({top:0})}catch(e){}; return }
  if(!BASE.some(x=>x.k===k)&&k!=='pay'){
    S.view=''; render(); if(raw&&raw!=='me') toast('این بخش را نداریم؛ برگشتیم سرِ پروفایل');
    return;
  }
  S.view=k; S.edit=false; S.errs={}; if(k==='profile') S.ptab='info'; render();
  try{window.scrollTo({top:0})}catch(e){}
}

/* ══ کنش‌ها ══════════════════════════════════════════════════════════ */
document.addEventListener('click',ev=>{
  const t=ev.target;
  if(t.closest('[data-back]')){ location.hash=''; return }
  const g=t.closest('[data-go]'); if(g){ go(g.dataset.go); return }
  const tb=t.closest('[data-tab]'); if(tb){ S.tab=tb.dataset.tab; renderView(); return }
  const pb=t.closest('[data-ptab]'); if(pb){ S.ptab=pb.dataset.ptab; S.edit=false; S.errs={}; renderView(); return }
  const tg=t.closest('[data-tab-go]'); if(tg){ S.tab=tg.dataset.tabGo; S.after='events'; if(!login()){loginSheet();return} renderView(); return }
  if(t.closest('#editBtn')){ startEdit(); return }
  if(t.closest('#cancelBtn')){ cancelEdit(); return }
  if(t.closest('#draftBtn')){ submit(false); return }
  if(t.closest('#sendBtn')){ submit(true); return }
  if(t.closest('#dlBtn')){ if(!login()){loginSheet(); return} downloadInfo(); return }
  if(t.closest('#delBtn')){ if(!login()){loginSheet(); return} askDelete(); return }
  if(t.closest('#delYes')){
    const w=unFa((($('#delWord')||{}).value||'')).replace(/[\s\u200c«»"]/g,'');
    const code=unFa((($('#delCode')||{}).value||'')).replace(/\D/g,'');
    if(w!=='حذف'){ toast('برای تأیید، کلمهٔ «حذف» را بنویس'); const e=$('#delWord'); if(e&&e.focus) e.focus(); return }
    if(code!=='54321'){ toast('کد پیامکی را درست بنویس؛ کد نمایشی ۵۴۳۲۱ است'); const e=$('#delCode'); if(e&&e.focus) e.focus(); return }
    const p=Object.assign({},prof(),{askedDelete:true});
    p.history=(p.history||[]).filter(h=>h.k!=='delete').concat([{k:'delete',at:nowFa()}]);
    if(UI().saveProfile) UI().saveProfile(p);
    closeSheets(); render(); toast('درخواست حذف ثبت شد؛ کارشناس برای تأیید خبر می‌دهد'); return }
  const cs=t.closest('[data-cert-dl]'); if(cs){ certDownload(cs.dataset.certDl); return }
  const cr=t.closest('[data-cert-req]'); if(cr){ certRequest(cr.dataset.certReq); return }
  const cy=t.closest('[data-cert-yes]'); if(cy){ closeSheets(); toast('سفارش ثبت شد؛ بعد از تأیید سرپرست خبر می‌دهیم'); return }
  const ck=t.closest('[data-cancel-ev]'); if(ck){ cancelEvent(ck.dataset.cancelEv); return }
  const cy2=t.closest('[data-cancel-yes]'); if(cy2){ closeSheets(); toast('ثبت‌نام لغو شد؛ مبلغ طبق شرایط همان رویداد برمی‌گردد'); return }
  if(t.closest('[data-form-new]')){ toast('کارشناس فرم را برایت می‌فرستد؛ بعد از آن همین‌جا باز می‌شود'); return }
  const fm=t.closest('[data-form]'); if(fm){ toast('فرم «'+fm.dataset.form+'» در فاز بعد باز می‌شود'); return }
  if(t.closest('[data-ticket-new]')){ toast('تیکت تازه در فاز پشتیبانی کامل می‌شود؛ الان از راه‌های تماس بالا بنویس'); return }
  const rw=t.closest('[data-reward]'); if(rw){ toast('«'+rw.dataset.reward+'» را با امتیازت می‌گیریم؛ در فاز فروشگاه پاداش کامل می‌شود'); return }
  if(t.closest('[data-sup-send]')){
    const m=(($('#msg')||{}).value||'').trim();
    if(m.length<5){ toast('کمی بیشتر بنویس تا کارشناس بهتر کمک کند'); const e=$('#msg'); if(e&&e.focus) e.focus(); return }
    closeSheets(); toast('پیام ثبت شد؛ کارشناس در همان روز کاری پاسخ می‌دهد'); return }
});
document.addEventListener('change',e=>{
  const el=e.target; if(!el.id||!el.id.startsWith('f_')) return;
  const k=el.id.slice(2); if(!S.errs[k]) return; delete S.errs[k]; renderView();
});
document.addEventListener('keydown',e=>{ if(e.key==='Escape') closeSheets() });
window.addEventListener('hashchange',renderRoute);

/* ══ راه‌اندازی ═══════════════════════════════════════════════════════ */
if(SUP.n) $('#supBar').setAttribute('aria-label',SUP.n);
if(typeof initUI==='function') initUI();          /* ورقه‌ها، کپی، اسکرول و کلید شب و روز از یوآی مشترک */
fillSupport();                                   /* ورقهٔ پشتیبانی از پیش پر می‌شود تا از پایین بیاید */
renderRoute();
})();
