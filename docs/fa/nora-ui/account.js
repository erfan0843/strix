/* ══════════════════════════════════════════════════════════════════════════
   حساب من — سرِ حساب، بخش‌ها و نمای هر بخش
   ──────────────────────────────────────────────────────────────────────────
   ساختار: یک منبع حقیقت (data.js)، رفتار مشترک (ui.js) و همین فایل که
   سرِ حساب و نشانی بخش‌ها را می‌سازد. بخش‌ها با #کد در نشانی باز می‌شوند.
   ══════════════════════════════════════════════════════════════════════════ */
(function(){
'use strict';
'use strict';
const {ACCOUNT={},NOTICES=[],TOTAL_MEDIA=0,ARCHIVE={},EVENTS=[],PAST=[],CERTS={}}=window.NORA||{};
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=t=>String(t==null?'':t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const UI=()=>window.NORA_UI||{};
const faN=n=>String(n==null?'':n).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
const unFa=s=>String(s==null?'':s).replace(/[۰-۹]/g,d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/[٠-٩]/g,d=>'٠١٢٣٤٥٦٧٨٩'.indexOf(d));
const faNum=n=>faN(String(Math.round(+n||0)).replace(/\B(?=(\d{3})+(?!\d))/g,'٬'));
const FIELDS=ACCOUNT.fields||[], LEVELS=ACCOUNT.levels||[], FLOW=ACCOUNT.flow||[];

let S={edit:false, errs:{}};
const uid=()=>UI().uid?UI().uid():'';
const login=()=>!!uid();
const statusOf=p=>p&&p.status||'draft';
const S_META={draft:{n:'تکمیل نشده',c:'warn'},pending:{n:'در صف تأیید',c:'brand'},
  approved:{n:'تأیید شده',c:'ok'},rejected:{n:'رد شده',c:'stop'}};

/* ── تاریخ و ساعت فارسی، برای سابقهٔ تأیید ── */
function nowFa(){
  try{
    const parts=new Intl.DateTimeFormat('fa-IR-u-ca-persian',{day:'numeric',month:'long',year:'numeric',hour:'2-digit',minute:'2-digit'}).formatToParts(new Date());
    const g=k=>(parts.find(x=>x.type===k)||{}).value||'';
    return (g('hour')?g('hour')+':'+g('minute')+' · ':'')+g('day')+' '+g('month')+' '+g('year');
  }catch(e){return 'همین حالا'}
}

/* ── پیش‌نمایش اطلاعات، بدون وابستگی به صفحه‌های دیگر ── */
function prof(){return UI().profile?UI().profile():{}}
function phone(){return UI().phoneOf?UI().phoneOf():''}
function filledMap(p){return UI().profileFilled?UI().profileFilled(p,!!phone()):{}}
function percentOf(p){return UI().profilePercent?UI().profilePercent(p,!!phone()):0}
function missingOf(p){return UI().profileMissing?UI().profileMissing(p,!!phone()):[]}
function levelInfo(){return UI().levelOf?UI().levelOf(+ACCOUNT.points||0):{cur:{},next:null}}

/* ── اعتبارسنجی: همان قواعد ربات ── */
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

/* ── سرِ حساب ── */
function renderHead(){
  const box=$('#headBox');
  if(!login()){
    box.innerHTML=`<div class="card acct">
      <div class="row" style="align-items:center;gap:11px">
        <span class="ava" style="width:46px;height:46px;border-radius:16px;background:var(--surface-sunk);color:var(--ink-3)">؟</span>
        <div class="nm"><b>وارد نشده‌ای</b><div class="cap">با شمارهٔ موبایل و کد یک‌بارمصرف وارد شو</div></div>
      </div>
      <p class="sub" style="margin:12px 0 0">اطلاعات حساب، بلیت‌ها و گواهی‌ها مالِ حساب خودت است. با ورود، همه‌شان همین‌جا می‌آید.</p>
      <div class="row" style="margin-top:12px">
        <button class="btn primary" data-login><svg class="i" aria-hidden="true"><use href="#i-mobile"/></svg> ورود با شمارهٔ موبایل</button>
        <span class="sp" style="flex:1"></span>
        <span class="cap">پشتیبانی و راهنما بی ورود باز است</span>
      </div></div>`;
    return;
  }
  const p=prof(), u=UI().sessUser?UI().sessUser():{}, pc=percentOf(p), miss=missingOf(p);
  const st=S_META[statusOf(p)]||S_META.draft;
  const {cur,next}=levelInfo(), pts=+ACCOUNT.points||0;
  const span=next?Math.max(1,next.at-cur.at):1;
  const inLevel=next?Math.max(0,Math.min(100,Math.round((pts-cur.at)/span*100))):100;
  const toNext=next?Math.max(0,next.at-pts):0;
  const initial=String(p.fullName||u.name||'ن').trim().slice(0,1)||'ن';
  const missTxt=miss.length?faN(miss.length)+' مورد مانده: '+miss.slice(0,3).map(f=>f.l).join('، '):'اطلاعات کامل است';
  box.innerHTML=`<div class="card acct">
    <div class="who">
      <span class="ava">${esc(initial)}</span>
      <div class="nm"><b>${esc(p.fullName||u.name||'کاربر نورا')}</b>
        <div class="cap">عضو از ${esc(u.joined||ACCOUNT.joined||'—')} · سطح ${esc(cur.n||'—')}</div></div>
      <span class="sp" style="flex:1"></span>
      <span class="tag ${st.c}">${esc(st.n)}</span>
    </div>
    <div class="lv">
      <span class="lvring" style="--p:${inLevel}" role="img" aria-label="پیشرفت تا سطح بعدی: ٪${faN(inLevel)}"><b>٪${faN(inLevel)}</b></span>
      <div class="lvt">
        <b>${faNum(pts)} امتیاز${next?' از '+faNum(next.at):''}</b>
        <div class="cap">${next?('تا سطح '+esc(next.n)+' '+faNum(toNext)+' امتیاز مانده'):'در بالاترین سطحی'}</div>
        <div class="cap">${esc(cur.perks||'')}</div>
      </div>
    </div>
    <div class="meter" role="img" aria-label="اطلاعات حساب ٪${faN(pc)} کامل است"><i style="width:${pc}%"></i></div>
    <div class="mfoot">
      <span class="cap">اطلاعات حساب: ٪${faN(pc)} کامل · ${esc(missTxt)}</span>
      <span class="sp" style="flex:1"></span>
      ${statusOf(p)==='rejected'&&p.reason?`<span class="tag stop">دلیل رد: ${esc(p.reason)}</span>`:''}
      <button class="btn sm ${miss.length?'primary':'quiet'}" data-edit="${miss.length?'1':'0'}">
        <svg class="i" aria-hidden="true"><use href="#i-${miss.length?'pen':'check'}"/></svg> ${miss.length?'تکمیل اطلاعات':'ویرایش'}</button>
    </div></div>`;
}

/* ── اطلاعات حساب: حالت نمایش و حالت ویرایش ── */
function fieldView(f,p,filled){
  const raw=String(p[f.k]||'').trim();
  /* عددها در نما فارسی می‌شوند، مثل بقیهٔ سامانه؛ در فرم لاتین می‌مانند */
  const val=f.lock?faN(phone()):(!raw?'':(f.input==='numeric'||f.k==='birthDate'?faN(raw):raw));
  if(f.lock) return `<span class="v"><svg class="i" aria-hidden="true" style="width:15px;height:15px;color:var(--ok)"><use href="#i-check"/></svg>
      <span class="tx">${esc(val||'—')}</span><span class="tag ok" style="height:20px;font-size:10px">تأییدشده</span></span>`;
  if(!val) return `<span class="v"><span class="tx miss">${f.req?'ثبت نشده':'اختیاری، خالی'}</span></span>`;
  return `<span class="v"><span class="tx">${esc(val)}</span>${f.req?'':''}</span>`;
}
function fieldEdit(f,p){
  const bad=S.errs[f.k];
  const v=f.lock?phone():String(p[f.k]||'');
  return `<label class="lbl" for="f_${f.k}" style="margin:0">${esc(f.l)}${f.req?'':' <span class="cap">اختیاری</span>'}</label>
    <input class="input${f.input==='numeric'?' num':''}" id="f_${f.k}" name="${f.k}" type="${f.input==='email'?'email':'text'}"
      ${f.input==='numeric'?'inputmode="numeric"':''} ${f.max?`maxlength="${f.max}"`:''}
      value="${esc(v)}" placeholder="${esc(f.ph||'')}" ${f.lock?'readonly aria-readonly="true"':''}
      ${bad?`aria-invalid="true" aria-describedby="e_${f.k}"`:(f.hint?`aria-describedby="h_${f.k}"`:'')}/>
    ${bad?`<span class="err" id="e_${f.k}" role="alert">${esc(bad)}</span>`:(f.hint?`<span class="hint" id="h_${f.k}">${esc(f.hint)}${f.lock?': برای عوض‌کردنش با پشتیبانی حرف بزن':''}</span>`:'')}`;
}
function renderInfo(){
  const box=$('#infoBody'), p=prof();
  if(!login()){ $('#secInfo').hidden=true; return }
  $('#secInfo').hidden=false;
  const filled=filledMap(p);
  const groups=[];
  FIELDS.forEach(f=>{ if(!groups.includes(f.g)) groups.push(f.g) });
  if(S.edit){
    box.innerHTML=groups.map(g=>`<div class="grp"><div class="gt">${esc(g)}</div>
      ${FIELDS.filter(f=>f.g===g).map(f=>`<div class="fld${S.errs[f.k]?' bad':''}">${fieldEdit(f,p)}</div>`).join('')}
      </div>`).join('');
  }else{
    box.innerHTML=groups.map(g=>`<div class="grp"><div class="gt">${esc(g)}</div>
      ${FIELDS.filter(f=>f.g===g).map(f=>`<div class="fld"><span class="hint">${esc(f.l)}</span>${fieldView(f,p,filled[f.k])}</div>`).join('')}
      </div>`).join('');
  }
  const st=S_META[statusOf(p)]||S_META.draft;
  $('#infoState').innerHTML=`<span class="tag ${st.c}">${esc(st.n)}</span>`;
  $('#editBtn').hidden=S.edit;
  $('#infoActs').hidden=!S.edit;
  $('#infoCard').classList.toggle('editing',S.edit);
}

/* ── مسیر تأیید ── */
function renderFlow(){
  const box=$('#flowSteps'); const p=prof();
  $('#secFlow').hidden=!login();
  if(!login()) return;
  const st=statusOf(p);
  const done={filled:['draft','pending','approved'],pending:['pending','approved'],approved:['approved']};
  const hit=k=>(done[k]||[]).includes(st);
  const hist={}; (p.history||[]).forEach(h=>{hist[h.k]=h.at});
  box.innerHTML=FLOW.map(f=>{
    const on=hit(f.k), now=(st==='pending'&&f.k==='pending');
    const cls=f.k==='pending'?'now':'done';
    const at=hist[f.k]||(on?'':'—');
    return `<div class="step ${on?'done':''} ${now?'now':''}">
      <span class="dot"><svg class="i" aria-hidden="true"><use href="#i-${on?'check':f.k==='pending'?'clock':'pen'}"/></svg></span>
      <span class="tt"><b>${esc(f.n)}</b><small>${esc(f.s)}</small></span>
      <span class="at">${esc(at)}</span></div>`}).join('');
  const note=$('#flowNote');
  if(st==='rejected') note.innerHTML=`<div class="fld bad" style="border:0;padding-top:10px">
    <span class="err">دلیل رد: ${esc(p.reason||'نامشخص')}</span>
    <span class="hint">اطلاعات را درست کن و دوباره بفرست.</span></div>`;
  else if(st==='pending') note.innerHTML=`<p class="cap" style="margin:10px 3px 0">معمولاً تا یک روز کاری بررسی می‌شود؛ تا آن موقع می‌توانی رویدادها را ببینی.</p>`;
  else if(st==='draft') note.innerHTML=`<p class="cap" style="margin:10px 3px 0">هر وقت اطلاعات را فرستادی، وضعیتش همین‌جا عوض می‌شود.</p>`;
  else note.innerHTML=`<p class="cap" style="margin:10px 3px 0">پروفایلت تأیید شده است؛ اگر چیزی را عوض کردی، دوباره می‌رود صف تأیید.</p>`;
}

/* ── نردبان سطح ── */
function renderLevel(){
  $('#secLevel').hidden=!login();
  if(!login()) return;
  const pts=+ACCOUNT.points||0, {cur,next}=levelInfo();
  $('#lvNote').textContent=next?('تا '+next.n+' '+faNum(Math.max(0,next.at-pts))+' امتیاز'):'بالاترین سطح';
  $('#ladder').innerHTML=LEVELS.map(l=>`<div class="lvrow ${l.k===cur.k?'on':''}">
    <span class="dot2"></span>
    <span class="tx"><b>${esc(l.n)}</b><small>${esc(l.perks)}</small></span>
    <span class="at">${faNum(l.at)} امتیاز</span></div>`).join('');
}

/* ── رندر کل ── */
function render(){
  renderHead(); renderInfo(); renderFlow(); renderLevel(); renderTiles();
  const dn=$('#delNote'); if(dn){                                   /* کارت حذف، در نمای حریم خصوصی است */
    const asked=!!prof().askedDelete;
    dn.textContent=asked?'درخواستت ثبت شده؛ کارشناس برای تأیید خبر می‌دهد.':''; }
  if(UI().syncBell) UI().syncBell();
}

/* ── ویرایش و ذخیره ── */
function startEdit(){ if(!login()){loginSheet(); return} S.edit=true; S.errs={}; renderInfo();
  const el=$('#f_fullName')||$('#infoCard input'); if(el) el.focus() }
function cancelEdit(){ S.edit=false; S.errs={}; renderInfo() }
function collect(){
  const p=Object.assign({},prof());
  FIELDS.forEach(f=>{ if(f.lock){ p[f.k]=phone(); return }   /* شمارهٔ تماس مالِ حساب است، نه دست کاربر */
    const el=$('#f_'+f.k); if(el) p[f.k]=el.value.trim() });
  return p;
}
/* مقدارها به شکل یکدست ذخیره می‌شوند: رقم لاتین، تاریخ با صفر پیش‌رو */
function tidy(p){
  const nat=unFa(p.nationalId||'').replace(/\D/g,''); if(nat) p.nationalId=nat;
  const b=unFa(p.birthDate||'').replace(/[^\d/]/g,'');
  const m=b.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/);
  if(m) p.birthDate=m[1]+'/'+String(+m[2]).padStart(2,'0')+'/'+String(+m[3]).padStart(2,'0');
  FIELDS.forEach(f=>{ if(f.lock) return; p[f.k]=unFa(p[f.k]||'') });
  return p;
}
function pushHist(p,k){ p.history=(p.history||[]).filter(h=>h.k!==k).concat([{k:k,at:nowFa()}]); return p }
function submit(send){
  if(!login()){loginSheet(); return}
  const p=tidy(collect());
  if(send){
    const e=validate(p);
    if(Object.keys(e).length){ S.errs=e; renderInfo(); toast('چند جا مانده یا درست نیست؛ همان‌ها را ببین'); 
      const first=$('#infoCard .fld.bad .input'); if(first&&first.focus) first.focus(); return }
  }
  p.status=send?'pending':(statusOf(p)==='draft'?'draft':statusOf(p));
  if(send) pushHist(p,'pending'); else if(statusOf(p)!=='draft') pushHist(p,'filled');
  const saved=UI().saveProfile?UI().saveProfile(p):p;
  S.edit=false; S.errs={}; render();
  const miss=missingOf(saved).length;
  toast(send?(miss?('فرستادیم برای تأیید؛ '+faN(miss)+' مورد هنوز خالی است'):'فرستادیم برای تأیید؛ نتیجه را از بله می‌گوییم'):'ذخیره شد');
  const flow=$('#secFlow'); if(flow&&flow.scrollIntoView) flow.scrollIntoView({behavior:'smooth',block:'start'});
}
function loginSheet(){ if(UI().authSheet) UI().authSheet(()=>{S.edit=false; render(); if(S.view) renderRoute()}); }
function openSheet(html){
  const el=$('#shConfirm'); if(!el) return;
  (el.querySelector('.sbody')||el).innerHTML=html;
  if(UI().uiOpen) UI().uiOpen('shConfirm'); else el.classList.add('on');
}
function closeSheet(){ const el=$('#shConfirm'); if(el) el.classList.remove('on'); const sc=$('#scrim'); if(sc) sc.classList.remove('on') }

function askDelete(){
  openSheet(`<div class="grabber"></div>
    <div class="head">حذف حساب کاربری</div>
    <p class="sub" style="margin-top:8px">با حذف حساب، بلیت‌ها، گواهی‌ها و سابقهٔ حضور پاک می‌شود. این کار برنمی‌گردد،
      پس دو تأیید می‌گیریم: کلمهٔ «حذف» و کد پیامکی.</p>
    <label class="lbl" for="delWord" style="margin-top:12px">برای تأیید، کلمهٔ «حذف» را بنویس</label>
    <input class="input" id="delWord" value="" placeholder="حذف" autocomplete="off"/>
    <label class="lbl" for="delCode" style="margin-top:12px">کد پیامکی</label>
    <input class="input num" id="delCode" inputmode="numeric" placeholder="•••••" autocomplete="one-time-code"/>
    <div class="cap" style="margin-top:7px">کد نمایشی این نمونه: ۵۴۳۲۱</div>
    <div class="row" style="margin-top:14px">
      <button class="btn stop" id="delYes">حذف حساب</button>
      <span class="sp" style="flex:1"></span>
      <button class="btn quiet" data-close>هنوز نه</button>
    </div>`);
}

/* ── دانلود اطلاعات من: یک فایل خوانا، بی هیچ داده‌ای بیرون از حساب خودت ── */
function downloadInfo(){
  const u=UI().sessUser?UI().sessUser():{};
  const pack={
    ساخته:new Date().toISOString(),
    حساب:{نام:u.name||'',موبایل:u.mobile||'',عضویت:u.joined||ACCOUNT.joined||'',سطح:levelInfo().cur.n||''},
    پروفایل:UI().profile?UI().profile():{},
    کتابخانه:UI().library?UI().library():[],
    اعلان‌ها:(NOTICES||[]).map(n=>({تیتر:n.t,تاریخ:n.d,خوانده:!n.unread})),
    رویدادها:{برگزارشده:(ARCHIVE.past||0),رسانه:(ARCHIVE.media||0),پیش‌رو:(ARCHIVE.upcoming||0)}
  };
  saveFile('nora-account.json',JSON.stringify(pack,null,2),'فایل اطلاعات حسابت آماده شد');
}

/* ── کنش‌ها ── */
document.addEventListener('click',ev=>{
  const t=ev.target;
  if(t.closest('[data-login]')){loginSheet(); return}
  const ed=t.closest('[data-edit]'); if(ed){ if(!login()){loginSheet(); return} startEdit(); return }
  if(t.closest('#editBtn')){startEdit(); return}
  if(t.closest('#cancelBtn')){cancelEdit(); return}
  if(t.closest('#draftBtn')){submit(false); return}
  if(t.closest('#sendBtn')){submit(true); return}
  if(t.closest('#dlBtn')){ if(!login()){loginSheet(); return} downloadInfo(); return }
  if(t.closest('#delBtn')){ if(!login()){loginSheet(); return} askDelete(); return }
  if(t.closest('#delYes')){
    const w=unFa((($('#delWord')||{}).value||'')).replace(/[\s\u200c«»"]/g,'');
    const code=unFa((($('#delCode')||{}).value||'')).replace(/\D/g,'');
    if(w!=='حذف'){ toast('برای تأیید، کلمهٔ «حذف» را بنویس'); if($('#delWord')) $('#delWord').focus(); return }
    if(code!=='54321'){ toast('کد پیامکی را درست بنویس؛ کد نمایشی ۵۴۳۲۱ است'); if($('#delCode')) $('#delCode').focus(); return }
    const p=Object.assign({},prof(),{askedDelete:true});
    p.history=(p.history||[]).filter(h=>h.k!=='delete').concat([{k:'delete',at:nowFa()}]);
    if(UI().saveProfile) UI().saveProfile(p);
    closeSheet(); render(); if(S.view) renderRoute(); toast('درخواست حذف ثبت شد؛ کارشناس برای تأیید خبر می‌دهد'); return }
  if(t.closest('[data-close]')){closeSheet(); return}
  const go=t.closest('[data-goto]'); if(go){location.href=go.dataset.goto; return}
  const op=t.closest('[data-open]'); if(op){ if(UI().uiOpen) UI().uiOpen(op.dataset.open==='notice'?'shNotice':'shMenu'); return }
});
$('#scrim').addEventListener('click',closeSheet);
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){closeSheet(); if(UI().authSheet){const s=document.getElementById('shAuth'); if(s&&s.classList.contains('on')) s.classList.remove('on')}}
});
document.addEventListener('change',e=>{
  const el=e.target; if(!el.id||!el.id.startsWith('f_')) return;
  const k=el.id.slice(2); if(!S.errs[k]) return;
  delete S.errs[k]; renderInfo();
});
/* ورود یا خروج از هر جای دیگر، همین صفحه را تازه می‌کند */
document.addEventListener('nora:library',()=>{render()});

/* ══════════════════════════════════════════════════════════════════════════
   بخش‌های «حساب من»: معماری و نماها
   ──────────────────────────────────────────────────────────────────────────
   هر بخش یک نشانی دارد: account.html#کد بخش. نوار پایین سه‌تایی می‌ماند و
   رفت‌وبرگشت داخل همین صفحه است. بخش‌های عضو با ورود باز می‌شوند و پشتیبانی
   و دربارهٔ نورا برای مهمان هم باز است. هیچ عددی اینجا از خودش ساخته نمی‌شود؛
   هرچه هست از data.js می‌آید و هرچه بعداً می‌آید، فاز بعد می‌نشیند.
   ══════════════════════════════════════════════════════════════════════════ */
const SECS=ACCOUNT.sections||[], POL=ACCOUNT.policy||{}, ACH=ACCOUNT.achievements||[],
      STORE=ACCOUNT.rewardStore||[], SCORE=ACCOUNT.score||{}, VS={};
S.view=''; S.vtab='up'; S.ncat='همه';
const CHAN_KEY='nora-account-notify';
const secBy=k=>SECS.find(x=>x.k===k)||null;
const cardBox=(t,s,body)=>`<div class="card acct"><div class="head">${esc(t)}</div>${s?`<div class="cap" style="margin-top:5px">${esc(s)}</div>`:''}${body||''}</div>`;
const noteBox=(txt,icon)=>`<p class="note"><svg class="i" aria-hidden="true"><use href="#${icon||'i-sparkle'}"/></svg><span>${txt}</span></p>`;
const chip=(t,cls)=>`<span class="tag ${cls||''}">${esc(t)}</span>`;
const statTile=(v,l)=>`<div class="stat2"><b>${v}</b><small>${esc(l)}</small></div>`;

function viewHead(sec,action){
  return `<div class="vhead">
      <button class="btn sm quiet" data-back><svg class="i" aria-hidden="true"><use href="#i-chev-left"/></svg> حساب من</button>
      <span class="sp" style="flex:1"></span>${action||''}</div>
    <h2 class="vh2">${esc(sec.n)}</h2><p class="vhsub">${esc(sec.s)}</p>`;
}
/* دروازهٔ ورود: بخش‌های عضو برای مهمان باز نمی‌شوند */
function gate(sec){
  if(login()||sec.open) return '';
  return cardBox('این بخش با حساب خودت باز می‌شود',
    'با شمارهٔ موبایل و کد یک‌بارمصرف وارد شو؛ «'+sec.n+'» مالِ حساب خودت است.',`
    <div class="gate"><svg class="i" aria-hidden="true"><use href="#i-lock"/></svg>
      <div class="gacts">
        <button class="btn primary" data-login><svg class="i" aria-hidden="true"><use href="#i-mobile"/></svg> ورود با شمارهٔ موبایل</button>
        <button class="btn quiet" data-view="support">پشتیبانی، بی ورود</button>
      </div></div>`);
}
/* نبودن چیز‌ها را هم صریح می‌گوید، نه با جای خالی */
const emptyBox=(t,s)=>`<div class="gate"><svg class="i" aria-hidden="true"><use href="#i-archive"/></svg>
  <div class="gt">${esc(t)}</div><div class="gs">${esc(s)}</div></div>`;

/* ── ۱) رویدادهای من ───────────────────────────────────────────────────── */
function evRow(e){
  const kind=e.cert?'گواهی‌دار':'';
  return `<div class="erow">
    <span class="dbox" style="background:${esc(e.g||'var(--surface-2)')};color:#fff">
      <small>${esc(e.dm||'')}</small><b>${faN(e.dn||'')}</b></span>
    <span class="ex"><b>${esc(e.t)}</b>
      <small>${esc([e.kind,e.when,e.time,e.place].filter(Boolean).join(' · '))}</small>
      <span class="acts">
        ${chip('ثبت‌نام قطعی','ok')}
        ${kind?chip(kind):''}
        <button class="btn sm quiet" data-view="tickets"><svg class="i" aria-hidden="true"><use href="#i-qr"/></svg> کارت ورود</button>
        <button class="btn sm quiet" data-goto="events.html?ev=${esc(e.id)}">صفحهٔ رویداد</button>
        ${login()?`<button class="btn sm quiet" data-cancel-ev="${esc(e.id)}">لغو ثبت‌نام</button>`:''}
      </span></span></div>`;
}
function pastRow(h){
  return `<div class="erow">
    <span class="dbox" style="background:${esc(h.g||'var(--surface-2)')};color:#fff"><small>${esc(h.dm||'')}</small><b>${faN(h.dn||'')}</b></span>
    <span class="ex"><b>${esc(h.t)}</b><small>${esc([h.d,h.rec,h.place].filter(Boolean).join(' · '))}</small>
      <span class="acts">${h.cert?chip('گواهی‌دار'):''}${chip('حضور ثبت شد','ok')}
        <button class="btn sm quiet" data-goto="events.html?ev=${esc(h.id)}">ضبط و جزوه</button>
        ${h.cert?`<button class="btn sm quiet" data-view="tickets">گواهی‌ام</button>`:''}</span></span></div>`;
}
VS.events=function(sec){
  const g=gate(sec); if(g) return viewHead(sec)+g;
  const tabs=[{k:'up',n:'پیشرو'},{k:'past',n:'برگزارشده'},{k:'cancel',n:'لغوشده'}];
  const up=EVENTS.slice(0,3), past=PAST.slice(0,2);
  const body = S.vtab==='up' ? up.map(evRow).join('')
    : S.vtab==='past' ? past.map(pastRow).join('')
    : emptyBox('لغوشده‌ای نداری','اگر جایی را لغو کنی، سابقه‌اش با شرایط همان رویداد همین‌جا می‌آید.');
  return viewHead(sec,`<span class="cap">${faN(up.length+past.length)} برنامه</span>`)+`
    <div class="vtabs" role="tablist">${tabs.map(t=>`<button class="vtab${S.vtab===t.k?' on':''}" role="tab"
      aria-selected="${S.vtab===t.k}" data-vtab="${t.k}">${esc(t.n)}</button>`).join('')}</div>
    ${cardBox(S.vtab==='up'?'ثبت‌نام‌های پیش‌رو':'برگزارشده‌ها',
      S.vtab==='up'?'کارت ورود، صفحهٔ رویداد و لغو، همه از همین‌جا':(S.vtab==='past'?'ضبط، جزوه و گواهی هر برنامه':''),body)}
    ${noteBox('شرایط لغو و بازگشت مبلغ، برای هر رویداد جدا نوشته می‌شود؛ در صفحهٔ همان رویداد پیدایش می‌کنی.')}`;
};

/* ── ۲) بلیت و گواهی ──────────────────────────────────────────────────── */
const memberCode=()=>'NL-'+unFa(phone()||'').replace(/\D/g,'').slice(-4);
function certRows(){
  const nm=(UI().sessUser?UI().sessUser():{}).name||'';
  return Object.entries(CERTS).filter(([,v])=>v.n===nm);
}
VS.tickets=function(sec){
  const g=gate(sec); if(g) return viewHead(sec)+g;
  const p=prof(), u=UI().sessUser?UI().sessUser():{}, {cur}=levelInfo(), mine=certRows();
  const card=`<div class="idcard">
    <div class="c1"><span class="ava" style="width:44px;height:44px;border-radius:14px;background:rgba(255,255,255,.18)">
      ${esc(String(p.fullName||u.name||'ن').slice(0,1))}</span>
      <span class="nm"><b>${esc(p.fullName||u.name||'کاربر نورا')}</b><small>سطح ${esc(cur.n||'')} · عضو از ${esc(u.joined||ACCOUNT.joined||'')}</small></span></div>
    <div class="meta">
      <span><small>کد عضویت</small><span dir="ltr">${esc(memberCode())}</span></span>
      <span><small>شمارهٔ تماس</small>${esc(faN(phone()||'—'))}</span></div>
    <div class="ser">NORA · LIFELINE</div>
    <div class="brandline"><svg class="i" aria-hidden="true" style="width:14px;height:14px"><use href="#i-idcard-f"/></svg>
      کارت ورود برنامه‌ها؛ در ورودی همین را نشان بده</div></div>`;
  const certs = mine.length ? mine.map(([ser,v])=>`<div class="tk">
      <svg class="i" aria-hidden="true" style="width:20px;height:20px;color:var(--brand)"><use href="#i-medal"/></svg>
      <span class="tx"><b>${esc(v.c)}</b><small>${esc(v.d)} · ${esc(v.h)} · سریال <span dir="ltr">${esc(ser)}</span></small>
        <span class="acts"><button class="btn sm quiet" data-cert-dl="${esc(ser)}"><svg class="i" aria-hidden="true"><use href="#i-send"/></svg> دانلود</button>
          <button class="btn sm quiet" data-goto="home.html#verify">استعلام</button></span></span></div>`).join('')
    : emptyBox('هنوز گواهی‌ای صادر نشده','بعد از هر رویداد، اگر شرط حضورش را داشته باشی، گواهی همین‌جا می‌آید.');
  const kinds=POL.certKinds||[];
  return viewHead(sec)+card+
    cardBox('گواهی‌های من','گواهی دیجیتال با سریال یکتا، آمادهٔ دانلود و استعلام',certs+
      noteBox('اعتبار پیش‌فرض گواهی‌ها '+faN(POL.certValidMonths||24)+' ماه است و در تنظیمات رویداد قابل تغییر است.','i-clock'))+
    cardBox('سفارش گواهی','رایگان، ویژه، چاپی و VIP؛ هر کدام شرایط خودش را دارد',`<div class="kinds">
      ${kinds.map(k=>`<div class="kind"><svg class="i" aria-hidden="true" style="width:19px;height:19px;color:var(--ink-4)"><use href="#i-medal"/></svg>
        <span class="tx"><b>${esc(k.n)}</b><small>${esc(k.s)}</small></span>
        <button class="btn sm ${k.k==='free'?'quiet':'primary'}" data-cert-req="${esc(k.k)}">${k.k==='free'?'دریافت':'سفارش'}</button></div>`).join('')}
      </div>${noteBox('گواهی چاپی و VIP بعد از تأیید سرپرست صادر و ارسال می‌شود.')}`);
};

/* ── ۳) باشگاه من ─────────────────────────────────────────────────────── */
function ladderHTML(){
  const pts=+ACCOUNT.points||0, {cur}=levelInfo();
  return (ACCOUNT.levels||[]).map(l=>`<div class="lvrow ${l.k===cur.k?'on':''}">
    <span class="dot2"></span><span class="tx"><b>${esc(l.n)}</b><small>${esc(l.perks)}</small></span>
    <span class="at">${faNum(l.at)} امتیاز</span></div>`).join('');
}
VS.club=function(sec){
  const g=gate(sec); if(g) return viewHead(sec)+g;
  const pts=+ACCOUNT.points||0, {cur,next}=levelInfo(), cap=POL.pointsCap||{};
  return viewHead(sec)+
    cardBox('امتیاز و سطح من','هر ثبت‌نام، حضور و فرم امتیاز دارد؛ دستاوردها هم جدا حساب می‌شوند',
      `<div class="stats">${statTile(faNum(pts),'امتیاز')}${statTile(esc(cur.n||''),'سطح')}
        ${statTile(next?faNum(next.at-pts):'—','تا سطح بعدی')}
        ${statTile(faN(SCORE.rank||'')+' از '+faNum(SCORE.of||0),'رتبهٔ '+(SCORE.month||'این ماه'))}</div>
      <div class="ladder" style="margin-top:12px">${ladderHTML()}</div>
      ${noteBox('سقف‌های محافظ: هر امتیاز تا '+faN(cap.each||100)+'، روزانه تا '+faN(cap.day||50)+' و ماهانه تا '+faN(cap.month||300)+' واحد.','i-shield')}`)+
    cardBox('دستاوردها','هر کدام که قفل است، کار خودش را می‌خواهد',`<div class="acks">
      ${ACH.map(a=>`<div class="ack${a.on?' on':''}"><svg class="i" aria-hidden="true"><use href="#${a.i}"/></svg>
        <b>${esc(a.n)}</b><small>${a.on?esc(a.r||'گرفته‌ای'):faNum(a.at)+' امتیاز'}</small></div>`).join('')}</div>`)+
    cardBox('فروشگاه پاداش','هر چه امتیاز داری، خرجش کن','<div class="kinds">'+
      STORE.map(r=>{const can=pts>=r.cost; return `<div class="kind">
        <svg class="i" aria-hidden="true" style="width:19px;height:19px;color:var(--ink-4)"><use href="#i-wallet"/></svg>
        <span class="tx"><b>${esc(r.n)}</b><small>${esc(r.s)}</small></span>
        <button class="btn sm ${can?'primary':'quiet'}" ${can?'':'disabled'} data-reward="${esc(r.n)}">${faNum(r.cost)} امتیاز</button></div>`}).join('')+
      '</div>');
};

/* ── ۴) کارنامهٔ حضور ─────────────────────────────────────────────────── */
VS.attend=function(sec){
  const g=gate(sec); if(g) return viewHead(sec)+g;
  const M=[62,74,80,58,90,55,72,84,78,88,92,70], pct=SCORE.attend||88;
  const rows=PAST.slice(0,5).map((h,i)=>`<div class="tk">
      <svg class="i" aria-hidden="true" style="width:19px;height:19px;color:${i===3?'var(--stop)':'var(--ok)'}"><use href="#i-${i===3?'close':'check'}"/></svg>
      <span class="tx"><b>${esc(h.t)}</b><small>${esc(h.d)} · ${esc(h.place||'')}</small></span>
      ${i===3?chip('غیبت','stop'):chip('حضور','ok')}</div>`).join('');
  return viewHead(sec)+
    cardBox('حال و روز حضور','درصد حضور و روند ماه‌به‌ماه',
      `<div class="stats">${statTile('٪'+faN(pct),'درصد حضور')}${statTile(faN(22),'جلسه')}${statTile(faN(3),'غیبت')}${statTile(faN(170),'دقیقهٔ میانگین')}</div>
      <div class="bars" role="img" aria-label="روند حضور در دوازده ماه گذشته">
        ${M.map(v=>`<i style="height:${v}%" class="${v<60?'off':''}"></i>`).join('')}</div>
      <div class="barscap"><span class="cap">۱۲ ماه گذشته</span><span class="sp" style="flex:1"></span>
        <span class="cap">نوار کم‌رنگ: ماه‌های زیر ٪۶۰</span></div>`)+
    cardBox('جلسه‌به‌جلسه','پنج برنامهٔ آخر',rows+
      noteBox('گواهی هر رویداد بر پایهٔ همان شرط حضوری صادر می‌شود که برای آن رویداد گذاشته شده است.','i-clock'));
};

/* ── ۵) دعوت دوستان ───────────────────────────────────────────────────── */
VS.invite=function(sec){
  const g=gate(sec); if(g) return viewHead(sec)+g;
  const code=(ACCOUNT.code||('NORA-'+unFa(phone()||'').replace(/\D/g,'').slice(-4))), need=POL.inviteNeed||2, done=+SCORE.invites||0;
  return viewHead(sec)+
    cardBox('کد دعوت من','هر دوست که با این کد بیاید، به حساب تو هم اعتبار می‌رسد',
      `<div class="srow" style="border:0;padding:6px 0">
        <span class="sp" style="font-size:20px;letter-spacing:2px" dir="ltr">${esc(code)}</span>
        <button class="btn sm quiet" data-copy="${esc(code)}"><svg class="i" aria-hidden="true"><use href="#i-link"/></svg> کپی</button></div>
      <div class="stats">${statTile(faN(done)+' از '+faN(need),'دعوت ثبت‌شده')}${statTile(faNum(0),'اعتبار گرفته')}</div>`)+
    cardBox('قفل عضویت','تا این دو کار انجام نشود، ثبت‌نام کامل نمی‌شود',
      `<div class="srow"><svg class="i" aria-hidden="true"><use href="#i-send"/></svg>
        <span class="sp">عضویت در کانال نورا</span>${chip('انجام شد','ok')}</div>
      <div class="srow"><svg class="i" aria-hidden="true" style="color:var(--ink-4)"><use href="#i-users"/></svg>
        <span class="sp">دعوت ${faN(need)} دوست</span>${chip(faN(done)+' از '+faN(need),done>=need?'ok':'warn')}</div>
      ${noteBox('کد دعوت را برای دوستت بفرست؛ وقتی وارد شد، هر دو در فهرست دعوت‌ها می‌بینید.')}`);
};

/* ── ۶) اعلان‌ها ──────────────────────────────────────────────────────── */
function chans(){ try{const v=JSON.parse(localStorage.getItem(CHAN_KEY)||'null'); if(Array.isArray(v)) return v}catch(e){} return (POL.channels||[]).slice() }
function saveChans(a){ try{localStorage.setItem(CHAN_KEY,JSON.stringify(a))}catch(e){} }
function noteCat(n){
  const s=(n.t||'')+(n.d||'');
  if(/پرداخت|رسید|بلیت|کارت ورود/.test(s)) return 'بلیت و پرداخت';
  if(/گواهی|سرپرست/.test(s)) return 'گواهی';
  if(/امتیاز|باشگاه|کتاب/.test(s)) return 'باشگاه و امتیاز';
  if(/پشتیبانی|کارشناس|پاسخ/.test(s)) return 'پشتیبانی';
  return 'رویداد';
}
VS.notices=function(sec){
  const g=gate(sec); if(g) return viewHead(sec)+g;
  const cats=['همه'].concat(POL.noticeCats||[]), act=chans();
  const list=NOTICES.filter(n=>S.ncat==='همه'||noteCat(n)===S.ncat);
  const on=NOTICES.filter(n=>n.unread).length;
  const rows=list.length?list.map(n=>`<div class="tk">
      <svg class="i" aria-hidden="true" style="width:19px;height:19px;color:${n.unread?'var(--brand)':'var(--ink-4)'}"><use href="#${n.i||'i-bell'}"/></svg>
      <span class="tx"><b>${esc(n.t)}</b><small>${esc(n.d||'')}</small>
        <span class="acts">${chip(noteCat(n))}${n.unread?chip('خوانده‌نشده','brand'):chip('خوانده','ok')}
          <span class="cap">${esc(n.w||'')}</span></span></span></div>`).join('')
    : emptyBox('در این دسته چیزی نیست','دستهٔ دیگری را ببین؛ اعلان‌های تازه همین‌جا می‌آیند.');
  return viewHead(sec, on?`<button class="btn sm quiet" data-vread><svg class="i" aria-hidden="true"><use href="#i-check"/></svg> خواندن همه</button>`:'')+`
    <div class="vtabs" role="tablist">${cats.map(c=>`<button class="vtab${S.ncat===c?' on':''}" role="tab"
      aria-selected="${S.ncat===c}" data-ncat="${esc(c)}">${esc(c)}</button>`).join('')}</div>`+
    cardBox('اعلان‌ها',on?faN(on)+' اعلان خوانده‌نشده':'همه خوانده شده',rows)+
    cardBox('کانال‌های اعلان','هر کدام را نخواستی، خاموشش کن',
      (POL.channels||[]).map(c=>`<div class="srow"><svg class="i" aria-hidden="true"><use href="#i-send"/></svg>
        <span class="sp">${esc(c)}</span>
        <button class="switch ${act.includes(c)?'on':''}" data-chan="${esc(c)}" role="switch"
          aria-checked="${act.includes(c)}" aria-label="اعلان از ${esc(c)}"></button></div>`).join(''));
};

/* ── ۷) فرم‌های من ────────────────────────────────────────────────────── */
const FORMS=[
  {t:'پیش‌ثبت‌نام کارگاه خطاطی', k:'پیش‌ثبت‌نام',          s:'draft',    d:'۳ مهر'},
  {t:'رضایت‌سنجی کارگاه عکاسی', k:'رضایت‌سنجی کارگاه',    s:'pending',  d:'۲۱ تیر'},
  {t:'انتخاب مسیر ترم پاییز',   k:'انتخاب مسیر',          s:'approved', d:'۱۲ شهریور'}
];
const F_ST={draft:{n:'پیش‌نویس',c:'warn'},pending:{n:'در صف بررسی',c:'brand'},approved:{n:'تأییدشده',c:'ok'}};
VS.forms=function(sec){
  const g=gate(sec); if(g) return viewHead(sec)+g;
  const rows=FORMS.map(f=>{const st=F_ST[f.s]||F_ST.draft; return `<div class="tk">
      <svg class="i" aria-hidden="true" style="width:19px;height:19px;color:var(--ink-4)"><use href="#i-doc"/></svg>
      <span class="tx"><b>${esc(f.t)}</b><small>${esc(f.k)} · ${esc(f.d)}</small>
        <span class="acts">${chip(st.n,st.c)}
          <button class="btn sm quiet" data-form="${esc(f.t)}">${f.s==='draft'?'ادامهٔ تکمیل':'دیدن پاسخ‌ها'}</button></span></span></div>`}).join('');
  return viewHead(sec,`<button class="btn sm primary" data-form-new><svg class="i" aria-hidden="true"><use href="#i-pen"/></svg> فرم تازه</button>`)+
    cardBox('فرم‌های من','پیش‌نویس، در صف و تأییدشده، همه یک‌جا',rows)+
    noteBox('فرم‌های نورا '+faN((POL.formKinds||[]).length)+' گونه‌اند: '+esc((POL.formKinds||[]).join('، '))+
      '؛ هر کدام را کارشناس می‌سازد و اینجا برایت می‌نشیند.','i-layers');
};

/* ── ۸) نظر و امتیاز من ───────────────────────────────────────────────── */
VS.reviews=function(sec){
  const g=gate(sec); if(g) return viewHead(sec)+g;
  const revs=[{t:PAST[0]?PAST[0].t:'کارگاه عکاسی', d:'۲۲ مرداد', r:5, x:'ضبط‌ها و جزوهٔ تنظیمات خیلی کمک کرد؛ تمرین‌های هفتگی هم پیگیری می‌شد.'},
              {t:PAST[1]?PAST[1].t:'کارگاه فن بیان', d:'۹ مرداد', r:4, x:'جلسه‌ها منظم بود و وقت پرسش می‌گذاشتند؛ جای تمرین گروهی بیشتر خالی بود.'}];
  const rows=revs.map(v=>`<div class="tk">
      <svg class="i" aria-hidden="true" style="width:19px;height:19px;color:var(--warn)"><use href="#i-star"/></svg>
      <span class="tx"><b>${esc(v.t)}</b><small>${esc(v.d)} · ${'★'.repeat(v.r)}${'☆'.repeat(5-v.r)}</small>
        <span class="cap" style="margin-top:4px;line-height:1.85">${esc(v.x)}</span></span></div>`).join('');
  return viewHead(sec)+
    cardBox('نظرهایی که نوشتی','نظر هر برنامه، بعد از برگزاری باز می‌شود',rows)+
    cardBox('نظر تازه','برای برنامه‌ای که رفته‌ای، چند خط بنویس',
      `<div class="row" style="margin-top:6px"><button class="btn sm primary" data-review-new>
        <svg class="i" aria-hidden="true"><use href="#i-pen"/></svg> نوشتن نظر</button>
        <span class="sp" style="flex:1"></span><span class="cap">به ازای هر نظر، امتیاز هم می‌گیری</span></div>`)+
    noteBox('رضایت از پشتیبانی را هم می‌توانی ستاره بدهی؛ همان‌جا در تیکت می‌آید.','i-star');
};

/* ── ۹) پشتیبانی و راهنما ─────────────────────────────────────────────── */
const SUPPORT_CH=[
  {i:'i-mobile', t:'تلفن پشتیبانی', v:'۰۲۱–۸۸۸۸۱۲۳۴', href:'tel:+982188881234', s:'۹ تا ۱۸، روزهای کاری'},
  {i:'i-mail',   t:'رایانامه',       v:'info@lifeline1.ir', href:'mailto:info@lifeline1.ir', s:'پاسخ در یک روز کاری'},
  {i:'i-send',   t:'بله',            v:'@nora_support', href:'https://ble.ir/nora_support', s:'گفت‌وگوی سریع'},
  {i:'i-link',   t:'تلگرام',         v:'@nora_support', href:'https://t.me/nora_support', s:'گفت‌وگوی سریع'}
];
VS.support=function(sec){
  const cats=(POL.ticketCats||[]).slice(), maxOpen=+POL.ticketMaxOpen||3;
  return viewHead(sec)+
    cardBox('راه‌های تماس','هر کدام راحت‌تر بود',SUPPORT_CH.map(c=>`<div class="srow">
        <svg class="i" aria-hidden="true"><use href="#${c.i}"/></svg>
        <span class="sp">${esc(c.t)}<small class="cap" style="display:block">${esc(c.s)}</small></span>
        <a class="btn sm quiet" href="${esc(c.href)}" ${c.href.startsWith('http')?'target="_blank" rel="noopener"':''} dir="ltr">${esc(c.v)}</a></div>`).join(''))+
    cardBox('تیکت‌های من','دسته را انتخاب کن؛ بیشتر از '+faN(maxOpen)+' تیکت باز نمی‌ماند',
      `<div class="chipsline">${cats.map(c=>chip(c)).join('')}</div>
      <div class="tk" style="margin-top:10px">
        <svg class="i" aria-hidden="true" style="width:19px;height:19px;color:var(--brand)"><use href="#i-headphone"/></svg>
        <span class="tx"><b>گواهی کارگاه عکاسی</b><small>دستهٔ گواهی · ۲ مهر</small>
          <span class="acts">${chip('در حال بررسی','brand')}<span class="cap">پاسخ کارشناس: حسن مقدم</span></span></span></div>
      <div class="row" style="margin-top:12px"><button class="btn sm primary" data-ticket-new>
        <svg class="i" aria-hidden="true"><use href="#i-pen"/></svg> تیکت تازه</button>
        <span class="sp" style="flex:1"></span><span class="cap">۱ از ${faN(maxOpen)} تیکت باز</span></div>`)+
    cardBox('راهنما و استعلام','چیزهایی که بی کارشناس هم جواب می‌گیرند',`<div class="stack tight">
        <button class="srow srowbtn" data-goto="home.html#faq"><svg class="i" aria-hidden="true"><use href="#i-doc"/></svg>
          <span class="sp">پرسش‌های پرتکرار</span><svg class="i" aria-hidden="true" style="width:15px;height:15px;color:var(--ink-4)"><use href="#i-chev-left"/></svg></button>
        <button class="srow srowbtn" data-goto="home.html#verify"><svg class="i" aria-hidden="true"><use href="#i-qr"/></svg>
          <span class="sp">استعلام گواهینامه با سریال</span><svg class="i" aria-hidden="true" style="width:15px;height:15px;color:var(--ink-4)"><use href="#i-chev-left"/></svg></button>
        <button class="srow srowbtn" data-goto="home.html#support"><svg class="i" aria-hidden="true"><use href="#i-headphone"/></svg>
          <span class="sp">گفت‌وگو با کارشناس در خانه</span><svg class="i" aria-hidden="true" style="width:15px;height:15px;color:var(--ink-4)"><use href="#i-chev-left"/></svg></button>
        <button class="srow srowbtn" data-goto="home.html#menu"><svg class="i" aria-hidden="true"><use href="#i-grid"/></svg>
          <span class="sp">منوی کامل نورا</span><svg class="i" aria-hidden="true" style="width:15px;height:15px;color:var(--ink-4)"><use href="#i-chev-left"/></svg></button></div>`);
};

/* ── ۱۰) دربارهٔ نورا ─────────────────────────────────────────────────── */
VS.about=function(sec){
  const rows=[
    {i:'i-users', t:'گروه فرهنگی خط زندگی', s:'نورا، سامانهٔ رویدادها و آموزش‌های گروه'},
    {i:'i-grid',  t:'تهران، خیابان ولی‌عصر، پلاک ۱۲', s:'کتابخانهٔ نورا، طبقهٔ همکف'},
    {i:'i-mobile',t:'۰۲۱–۸۸۸۸۱۲۳۴', s:'۹ تا ۱۸، روزهای کاری'},
    {i:'i-mail',  t:'info@lifeline1.ir', s:'برای همکاری و پیشنهاد'},
    {i:'i-link',  t:'lifeline1.ir', s:'پایگاه گروه'}
  ];
  return viewHead(sec)+
    cardBox('ما کی هستیم','گروه فرهنگی خط زندگی، رویداد و کارگاه برگزار می‌کند؛ نورا درِ ورود همهٔ برنامه‌هاست.',
      rows.map(r=>`<div class="abrow"><svg class="i" aria-hidden="true"><use href="#${r.i}"/></svg>
        <span class="sp">${esc(r.t)}<small>${esc(r.s)}</small></span></div>`).join(''))+
    cardBox('پیمان‌های ما','چیزهایی که همیشه سرجایش می‌ماند',`<div class="stack tight">
        <div class="srow"><svg class="i" aria-hidden="true"><use href="#i-shield"/></svg><span class="sp">اطلاعات حساب، مالِ خودت است</span></div>
        <div class="srow"><svg class="i" aria-hidden="true"><use href="#i-check"/></svg><span class="sp">قیمت‌ها شفاف، بی هزینهٔ پنهان</span></div>
        <div class="srow"><svg class="i" aria-hidden="true"><use href="#i-headphone"/></svg><span class="sp">پاسخ پشتیبانی در یک روز کاری</span></div>
      </div>`)+
    cardBox('راه‌های دیگر','',`<div class="row">
        <a class="btn sm quiet" href="home.html"><svg class="i" aria-hidden="true"><use href="#i-home"/></svg> خانهٔ نورا</a>
        <a class="btn sm quiet" href="events.html"><svg class="i" aria-hidden="true"><use href="#i-calendar"/></svg> رویدادها</a>
        <button class="btn sm quiet" data-view="support"><svg class="i" aria-hidden="true"><use href="#i-headphone"/></svg> پشتیبانی</button>
      </div>`);
};

/* ── ۱۱) حریم خصوصی و حساب ───────────────────────────────────────────── */
VS.privacy=function(sec){
  const g=gate(sec); if(g) return viewHead(sec)+g;
  const p=prof(), asked=!!p.askedDelete;
  return viewHead(sec)+
    cardBox('حریم خصوصی','اطلاعاتت را می‌توانی برداری یا حساب را ببندی',`
      <div class="srow" style="border-bottom:.5px solid var(--hairline-2)">
        <svg class="i" aria-hidden="true"><use href="#i-doc"/></svg>
        <span class="sp">دانلود اطلاعات من<small class="cap" style="display:block">پروفایل، خریدها، اعلان‌ها و آمار، یک فایل</small></span>
        <button class="btn sm quiet" id="dlBtn"><svg class="i" aria-hidden="true"><use href="#i-send"/></svg> دانلود</button></div>
      <div class="srow" style="border-bottom:0">
        <svg class="i" aria-hidden="true" style="color:var(--stop)"><use href="#i-shield"/></svg>
        <span class="sp">حذف حساب کاربری<small class="cap" style="display:block">بلیت‌ها، گواهی‌ها و سابقهٔ حضور هم پاک می‌شود</small></span>
        <button class="btn sm stop" id="delBtn" ${asked?'disabled':''}>${asked?'ثبت شد':'درخواست حذف'}</button></div>
      <div class="cap" id="delNote" style="margin-top:10px">${asked?'درخواستت ثبت شده؛ کارشناس برای تأیید خبر می‌دهد.':''}</div>`)+
    noteBox('حذف حساب بی‌برگشت است؛ برای همین سه تأیید می‌گیریم: تأیید، تایپ «حذف» و کد پیامکی.','i-lock')+
    cardBox('چه چیزی نگه می‌داریم','شفاف و کوتاه',`<div class="stack tight">
        <div class="srow"><svg class="i" aria-hidden="true"><use href="#i-check"/></svg><span class="sp">اطلاعات پروفایل، برای بلیت و گواهی</span></div>
        <div class="srow"><svg class="i" aria-hidden="true"><use href="#i-check"/></svg><span class="sp">سابقهٔ خرید و حضور، برای کارنامهٔ تو</span></div>
        <div class="srow"><svg class="i" aria-hidden="true"><use href="#i-lock"/></svg><span class="sp">شمارهٔ موبایل، فقط برای ورود و یادآوری</span></div>
      </div>`);
};

/* ── ۱۲) نورا پی: فاز جدا ─────────────────────────────────────────────── */
VS.pay=function(sec){
  const bits=['کیف پول و شارژ','صورت‌حساب','بازگشت وجه','اقساط و پیش‌پرداخت','کد تخفیف','تسویه با گروه'];
  return viewHead(sec)+
    cardBox('نورا پی','این بخش را در یک فاز جدا می‌سازیم',`
      <div class="gate"><svg class="i" aria-hidden="true"><use href="#i-wallet"/></svg>
        <div class="gt">فعلاً قفل است</div>
        <div class="gs">حساب و پروفایل کار می‌کند؛ کیف پول و پرداخت‌ها فاز بعد می‌آید
          تا شماره‌ها و صورت‌حساب‌ها از اول درست بنشینند.</div>
        <div class="chipsline" style="justify-content:center">${bits.map(b=>chip(b)).join('')}</div>
        <div class="gacts"><button class="btn primary" data-view="support">پیشنهادت را بگو</button>
          <button class="btn quiet" data-view="tickets">بلیت‌ها و گواهی‌ها</button></div>
      </div>`);
};

/* ── کاشی‌های بخش‌ها روی سرِ حساب ─────────────────────────────────────── */
function renderTiles(){
  const box=$('#tilesBox'); if(!box) return;
  box.innerHTML=SECS.map(x=>{
    const open=(login()||x.open);
    return `<button class="tile${x.phase?' next':''}" data-view="${x.k}">
      <span class="ic"><svg class="i" aria-hidden="true"><use href="#${x.i}"/></svg></span>
      <span class="tx"><b>${esc(x.n)}${x.phase?' <span class="tag" style="height:18px;font-size:9.5px">فاز بعد</span>':''}</b>
        <small>${esc(open?x.s:'با ورود باز می‌شود')}</small></span></button>`}).join('');
}

/* ── مسیرها: هر بخش یک نشانی ─────────────────────────────────────────── */
function renderRoute(){
  const hub=$('#hubBox'), view=$('#viewBox'); if(!hub||!view) return;
  const raw=(location.hash||'').replace('#',''), k=raw.replace(/^sec-/,''), sec=secBy(k);
  if(!sec){
    S.view=''; hub.hidden=false; view.hidden=true; view.innerHTML='';
    document.title='نورا · حساب من'; render();
    if(raw&&raw!=='me') toast('این بخش را نداریم؛ برگشتیم سرِ حساب');
    return;
  }
  S.view=k; hub.hidden=true; view.hidden=false;
  view.innerHTML=`<section class="sec" aria-label="${esc(sec.n)}">${(VS[k]||(()=>''))(sec)}</section>`;
  document.title='نورا · '+sec.n;
  try{window.scrollTo({top:0})}catch(e){}
  if(UI().syncBell) UI().syncBell();
}

/* ── فایل ساختن و کپی ─────────────────────────────────────────────────── */
function saveFile(name,txt,msg){
  try{
    const url=URL.createObjectURL(new Blob([txt],{type:'text/plain;charset=utf-8'}));
    const a=document.createElement('a'); a.href=url; a.download=name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),4000); toast(msg);
  }catch(e){ toast('این مرورگر فایل نمی‌سازد؛ از پشتیبانی بخواه برایت بفرستند') }
}
function copyTxt(t,msg){
  try{ navigator.clipboard.writeText(t).then(()=>toast(msg||'کپی شد'),()=>toast('مرورگر اجازهٔ کپی نداد؛ دستی بردار')) }
  catch(e){ toast('مرورگر اجازهٔ کپی نداد؛ دستی بردار') }
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
  openSheet(`<div class="grabber"></div><div class="head">سفارش ${esc(k.n||'گواهی')}</div>
    <p class="sub" style="margin-top:8px">${esc(k.s||'')}. بعد از ثبت سفارش، کارشناس سرپرست تأیید می‌کند و بعد از آن صادر و ارسال می‌شود.</p>
    <div class="row" style="margin-top:14px"><button class="btn primary" data-cert-yes="${esc(kind)}">ثبت سفارش</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" data-close>بعداً</button></div>`);
}
function cancelEvent(id){
  const e=EVENTS.find(x=>x.id===id)||{};
  openSheet(`<div class="grabber"></div><div class="head">لغو ثبت‌نام</div>
    <p class="sub" style="margin-top:8px">«${esc(e.t||'این برنامه')}» را لغو کنم؟ شرایط بازگشت مبلغ، همان چیزی است که در صفحهٔ رویداد نوشته شده.</p>
    <div class="row" style="margin-top:14px"><button class="btn stop" data-cancel-yes="${esc(id)}">بله، لغو کن</button>
      <span class="sp" style="flex:1"></span><button class="btn quiet" data-close>نه</button></div>`);
}

document.addEventListener('click',ev=>{
  const t=ev.target;
  if(t.closest('[data-back]')){ location.hash=''; return }
  const vw=t.closest('[data-view]'); if(vw){ location.hash='#'+vw.dataset.view; return }
  const vt=t.closest('[data-vtab]'); if(vt){ S.vtab=vt.dataset.vtab; renderRoute(); return }
  const nc=t.closest('[data-ncat]'); if(nc){ S.ncat=nc.dataset.ncat; renderRoute(); return }
  const ch=t.closest('[data-chan]'); if(ch){
    const k=ch.dataset.chan; let a=chans().slice();
    a=a.includes(k)?a.filter(x=>x!==k):a.concat(k); saveChans(a);
    toast(a.includes(k)?('اعلان '+k+' روشن شد'):('اعلان '+k+' خاموش شد')); renderRoute(); return }
  if(t.closest('[data-vread]')){
    NOTICES.forEach(n=>{n.unread=false; if(UI().markRead) UI().markRead(n.t)});
    toast('همهٔ اعلان‌ها خوانده شد'); renderRoute(); return }
  const cp=t.closest('[data-copy]'); if(cp){ copyTxt(cp.dataset.copy,'کد دعوت کپی شد'); return }
  const cdl=t.closest('[data-cert-dl]'); if(cdl){ certDownload(cdl.dataset.certDl); return }
  const crq=t.closest('[data-cert-req]'); if(crq){ certRequest(crq.dataset.certReq); return }
  const cy=t.closest('[data-cert-yes]'); if(cy){ closeSheet(); toast('سفارش ثبت شد؛ بعد از تأیید سرپرست خبر می‌دهیم'); return }
  const cn=t.closest('[data-cancel-ev]'); if(cn){ cancelEvent(cn.dataset.cancelEv); return }
  const cy2=t.closest('[data-cancel-yes]'); if(cy2){ closeSheet(); toast('ثبت‌نام لغو شد؛ مبلغ طبق شرایط همان رویداد برمی‌گردد'); return }
  const fw=t.closest('[data-form-new]'); if(fw){ toast('کارشناس فرم را برایت می‌فرستد؛ بعد از آن همین‌جا باز می‌شود'); return }
  const fm=t.closest('[data-form]'); if(fm){ toast('فرم «'+fm.dataset.form+'» در فاز بعد باز می‌شود'); return }
  const rv=t.closest('[data-review-new]'); if(rv){ toast('نظر برای برنامه‌های برگزارشده باز است؛ بعد از هر برنامه برایت می‌آید'); return }
  const tk=t.closest('[data-ticket-new]'); if(tk){ toast('تیکت تازه در فاز پشتیبانی کامل می‌شود؛ الان از راه‌های تماس بالا بنویس'); return }
  const rw=t.closest('[data-reward]'); if(rw){ toast('«'+rw.dataset.reward+'» را با امتیازت می‌گیریم؛ در فاز فروشگاه پاداش کامل می‌شود'); return }
});

window.addEventListener('hashchange',renderRoute);
renderRoute();

if(UI().syncBell) UI().syncBell();
render();
themeInit();
})();
