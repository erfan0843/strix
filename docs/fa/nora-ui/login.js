/* ══════════════════════════════════════════════════════════════════════════
   نورا — صفحهٔ ورود
   ──────────────────────────────────────────────────────────────────────────
   یک کار: شماره می‌گیری، بعد تحویلش می‌دهی به پیام‌گیر (بله، ایتا، تلگرام)،
   بعد کد پنج‌رقمی را می‌گیری و حساب باز می‌شود.

   پله‌ها:  شماره → تحویل به پیام‌گیر → کد → پایان
   رمزی در کار نیست؛ همان کد یک‌بارمصرفی که در حساب کاربری جا افتاده.
   ══════════════════════════════════════════════════════════════════════════ */
(function(){
'use strict';

/* ── داده ─────────────────────────────────────────────────────────── */
const N=window.NORA||{}, A=N.ACCOUNT||{}, L=A.login||{};
const MSGS=(L.msgs||[]).slice();
const CODE_DEMO='54321', CODE_LEN=+(L.codeLen||5), TTL=120;   /* ثانیه */

/* ── کمکی‌ها ─────────────────────────────────────────────────────── */
const $=s=>document.querySelector(s);
const esc=t=>String(t==null?'':t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const faN=n=>String(n==null?'':n).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
const unFa=s=>String(s==null?'':s).replace(/[۰-۹]/g,d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/[٠-٩]/g,d=>'٠١٢٣٤٥٦٧٨٩'.indexOf(d));
const msk=m=>m?('۰۹'+faN(m.slice(2,5))+'…'+faN(m.slice(-4))):'';
const isMob=v=>/^09\d{9}$/.test(v);
const store={
  get(k){ try{return JSON.parse(localStorage.getItem(k)||'null')}catch(e){return null} },
  set(k,v){ try{localStorage.setItem(k,JSON.stringify(v))}catch(e){} },
  del(k){ try{localStorage.removeItem(k)}catch(e){} }
};
const toast2=t=>{ const el=$('#toast'); if(!el) return;
  el.textContent=t; el.classList.add('on'); clearTimeout(toast2.t);
  toast2.t=setTimeout(()=>el.classList.remove('on'),2600) };
const sheet=(id,html)=>{
  if(typeof fillSheet==='function'&&typeof openSheet==='function'){ fillSheet(id,html); openSheet(id); return true }
  return false;
};
const shut=()=>{ if(typeof closeSheets==='function') closeSheets() };

/* ── حالت ─────────────────────────────────────────────────────────── */
const S={step:'phone', mobile:'', via:(MSGS[0]||{}).k||'bale', err:'', wait:TTL, done:false, tries:0};

/* ── نشان پیام‌گیرها: ساده و کم‌رنگ، به رنگ خودشان ────────────────── */
const MARK={
  bale:'<svg viewBox="0 0 40 40" aria-hidden="true"><defs><linearGradient id="gb" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3FBD6D"/><stop offset="1" stop-color="#0E9B62"/></linearGradient></defs><circle cx="20" cy="20" r="20" fill="url(#gb)"/><path d="M11.6 20.8l5.1 5.3L28.4 14" fill="none" stroke="#fff" stroke-width="4.1" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  eitaa:'<svg viewBox="0 0 40 40" aria-hidden="true"><rect x="0" y="0" width="40" height="40" rx="11" fill="#26303B"/><path d="M13.4 20.2v-4.6a6.6 6.6 0 0 1 13.2 0v4.6" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/><rect x="12.2" y="19.4" width="15.6" height="11.4" rx="3.2" fill="#F5821F"/><circle cx="20" cy="25.1" r="1.9" fill="#26303B"/></svg>',
  telegram:'<svg viewBox="0 0 40 40" aria-hidden="true"><defs><linearGradient id="gt" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3FB0E8"/><stop offset="1" stop-color="#1E8BC4"/></linearGradient></defs><circle cx="20" cy="20" r="20" fill="url(#gt)"/><path d="M9.8 19.9l19-7.4-3 15.1-5.6-4.1-3 3.1-.6-4.6z" fill="#fff"/><path d="M16.6 22l11.2-8.6-8.2 12z" fill="#D6EBF7"/></svg>'
};
const markOf=k=>MARK[k]||MARK.bale;
const msgOf=k=>MSGS.find(m=>m.k===k)||MSGS[0]||{k:'bale',n:'بله',hand:'',href:'#'};

/* ── وضعیت پیام ───────────────────────────────────────────────────── */
function status(t){ const el=$('#lgStatus'); if(!el) return;
  el.hidden=!t; el.textContent=t||'' }
function err(t){ S.err=t||''; const el=$('#lgErr'); if(el){ el.hidden=!t; el.textContent=t||'' }
  const hit=$('#lgTel'); if(hit&&t){ hit.classList.add('bad'); setTimeout(()=>hit.classList.remove('bad'),420) } }

/* ── پلهٔ ۱: شماره ────────────────────────────────────────────────── */
function stepPhone(){
  const rows=MSGS.map(m=>`<button class="lgmsg" type="button" data-via="${esc(m.k)}" title="${esc(m.s||'')}">
      <span class="lgmk">${markOf(m.k)}</span><small>${esc(m.n)}</small></button>`).join('');
  return `<form class="lgstep" id="lgForm" novalidate>
    <label class="lglbl" for="lgPhone">${esc(L.q||'تلفن همراه خود را وارد کنید:')}</label>
    <div class="lgtel" id="lgTel">
      <span class="pref" id="lgPref" aria-hidden="true">۰۹</span>
      <input class="lginp num" id="lgPhone" type="tel" inputmode="numeric" autocomplete="tel-national"
        maxlength="11" placeholder="---------" aria-describedby="lgHint" value=""/>
      <span class="fic" aria-hidden="true"><svg class="i"><use href="#i-mobile"/></svg></span>
    </div>
    <p class="lghint" id="lgHint">${esc(L.hint||'')}</p>
    <p class="lgerr" id="lgErr" hidden></p>
    <button class="lgbtn" type="submit" id="lgGo">${esc(L.go||'ورود')}</button>
    <div class="lgvia"><span>${esc(L.via||'ورود با')}</span></div>
    <div class="lgmsgs" role="group" aria-label="${esc(L.via||'ورود با')}">${rows}</div>
    <p class="lgcap">${esc(L.sms||'')}</p>
  </form>`;
}

/* ── پلهٔ ۲: تحویل به پیام‌گیر و کد ────────────────────────────────── */
function stepHand(){
  const m=msgOf(S.via);
  return `<form class="lgstep" id="lgForm2" novalidate>
    <div class="lghand">
      <span class="lgmk big">${markOf(m.k)}</span>
      <span class="tx"><b>شماره به ${esc(m.n)} تحویل شد</b><small class="num">${msk(S.mobile)}</small></span>
      <span class="lgwait" id="lgWait" title="${esc(L.wait||'')}"><i></i><i></i><i></i></span>
    </div>
    <p class="lghhelp">${esc(m.hand||'')}</p>
    <a class="lgbtn ghost" id="lgOpen" href="${esc(m.href||'#')}" target="_blank" rel="noopener">باز کردن ${esc(m.n)}</a>
    <label class="lglbl" for="lgCode">${esc(L.codeCap||'کد پنج‌رقمی پیام‌گیر')}</label>
    <div class="lgcode" id="lgCodeWrap">
      <input class="lginp code num" id="lgCode" type="text" inputmode="numeric" autocomplete="one-time-code"
        maxlength="${CODE_LEN}" placeholder="•••••" aria-describedby="lgCodeHint"/>
      <span class="fic" aria-hidden="true"><svg class="i"><use href="#i-lock"/></svg></span>
    </div>
    <p class="lghint" id="lgCodeHint"><span id="lgMsg">کد نمونهٔ این پیش‌نمایش: ${faN(CODE_DEMO)}</span> · تا <b id="lgTtl">${faN('2:00')}</b> دیگر</p>
    <p class="lgerr" id="lgErr2" hidden></p>
    <button class="lgbtn" type="submit" id="lgOk">تأیید و ورود</button>
    <div class="lgacts">
      <button class="lgbtn quiet" type="button" id="lgAgain">${esc(L.resend||'دوباره بفرست')}</button>
      <button class="lgbtn quiet" type="button" id="lgBack">${esc(L.change||'تغییر شماره')}</button>
    </div>
  </form>`;
}

/* ── پلهٔ ۳: پایان ────────────────────────────────────────────────── */
function stepDone(){
  const u=store.get('nora-home-user')||{};
  return `<div class="lgstep lgdones" id="lgDone">
    <span class="lgcheck" aria-hidden="true"><svg class="i"><use href="#i-check"/></svg></span>
    <b class="lgdtitle">${esc(L.okTitle||'خوش آمدی')}${u.name?'، '+esc(String(u.name).split(' ')[0]):''}</b>
    <p class="lgdle">${esc(L.okLead||'')}</p>
    <a class="lgbtn" id="lgNext" href="${esc(nextUrl())}">${esc(L.okGo||'رفتن به حساب من')}</a>
    <button class="lgbtn quiet" type="button" data-go-support>پشتیبانی و راهنما</button>
  </div>`;
}

/* ── پلهٔ ۰: کسی که همین حالا وارد شده ───────────────────────────── */
function stepAlready(){
  const u=store.get('nora-home-user')||{};
  return `<div class="lgstep lgdones">
    <span class="lgcheck ok" aria-hidden="true"><svg class="i"><use href="#i-user"/></svg></span>
    <b class="lgdtitle">همین حالا وارد شده‌ای</b>
    <p class="lgdle">حسابت باز است${u.mobile?' با شمارهٔ '+faN(u.mobile):''}. اگر می‌خواهی با حساب دیگری بیایی،
      اول از حساب بیرون بیا.</p>
    <a class="lgbtn" href="${esc(nextUrl())}">رفتن به حساب من</a>
    <button class="lgbtn quiet" type="button" id="lgOutMost">خروج از حساب در این دستگاه</button>
  </div>`;
}

/* ── نشانی بازگشت ─────────────────────────────────────────────────── */
function nextUrl(){
  const q=new URLSearchParams(location.search).get('next');
  if(!q) return 'account.html';
  return /^[a-z0-9-]+\.html([?#].*)?$/i.test(q)?q:'account.html';
}

/* ── نشستن پله‌ها ─────────────────────────────────────────────────── */
function paint(){
  const box=$('#lgBody'); if(!box) return;
  const map={phone:stepPhone,hand:stepHand,done:stepDone,already:stepAlready};
  box.innerHTML=(map[S.step]||stepPhone)();
  $('#lgLead').textContent = S.step==='done' ? '' : (L.lead||'');
  status('');
  if(S.step==='phone'){ const f=$('#lgPhone'); if(f){ f.value=faN(S.mobile); pref() } }
  if(S.step==='hand'){ tick(); const c=$('#lgCode'); if(c) setTimeout(()=>{ try{c.focus()}catch(e){} },120) }
  if(S.step==='done'){ clearInterval(clock.t); setTimeout(()=>{ if(S.step==='done') location.href=nextUrl() },2200) }
}
function pref(){ const f=$('#lgPhone'), p=$('#lgPref'); if(!f||!p) return;
  p.hidden=!!unFa(f.value).replace(/\D/g,'').length }

/* ── زمان اعتبار کد ───────────────────────────────────────────────── */
const clock={t:0};
function tick(){
  clearInterval(clock.t); S.wait=TTL;
  const el=$('#lgTtl'); const draw=()=>{ if(el){ const m=Math.floor(S.wait/60), s=S.wait%60;
      el.textContent=faN(m)+':'+faN(String(s).padStart(2,'0')) }
    const sm=$('#lgMsg'); if(sm&&S.wait<=0) sm.textContent='زمان کد سر آمد؛ «دوباره بفرست» را بزن.' };
  draw();
  clock.t=setInterval(()=>{ S.wait--; draw(); if(S.wait<=0) clearInterval(clock.t) },1000);
}

/* ── ورود: نوشتن نشست، همان کلیدهایی که بقیهٔ صفحه‌ها می‌خوانند ──── */
function signIn(mobile){
  store.set('nora-home-user',{name:(A.seed||{}).fullName||'سارا محمدی',mobile:mobile,joined:'شهریور ۱۴۰۴',
    certs:2,wallet:1250000,msgs:1});
  store.del('nora-home-auth');
  S.done=true;
  try{ document.dispatchEvent(new CustomEvent('nora:login',{detail:{mobile:mobile}})) }catch(e){}
}
function signOut(){
  store.del('nora-home-user');
  try{ document.dispatchEvent(new CustomEvent('nora:logout')) }catch(e){}
}

/* ── کارها ────────────────────────────────────────────────────────── */
function phoneVal(){
  const f=$('#lgPhone'); let v=unFa(f?f.value:'');
  v=v.replace(/\D/g,'');
  if(/^9\d{9}$/.test(v)) v='0'+v;                 /* بی صفر و ۰۹ هم می‌شود */
  if(/^09\d{9}$/.test(v)) return v;
  return v;
}
function tryPhone(via){
  const v=phoneVal();
  if(!isMob(v)){ err('شماره را کامل بنویس؛ یازده رقم، با ۰۹. نمونه: ۰۹۱۲۳۴۵۶۷۸۹'); return false }
  S.mobile=v; err('');
  if(via) S.via=via;
  store.set('nora-home-auth',{step:'code',mobile:v});
  S.step='hand'; paint();
  const m=msgOf(S.via);
  status('شماره به '+m.n+' رفت؛ کد پنج‌رقمی را از همان‌جا بردار.');
  return true;
}
function tryCode(){
  const f=$('#lgCode'); const v=unFa(f?f.value:'').replace(/\D/g,'');
  const e2=$('#lgErr2');
  if(v.length<CODE_LEN){ if(e2){e2.hidden=false; e2.textContent='کد پنج‌رقمی را کامل بنویس.'} return }
  if(v!==CODE_DEMO){ S.tries++; if(e2){e2.hidden=false;
      e2.textContent='این کد درست نیست؛ کد نمونهٔ این پیش‌نمایش '+faN(CODE_DEMO)+' است.'}
    if(f){ f.classList.add('bad'); setTimeout(()=>f.classList.remove('bad'),420) } return }
  if(S.wait<=0){ if(e2){e2.hidden=false; e2.textContent='زمان کد سر آمده؛ «دوباره بفرست» را بزن.'} return }
  clearInterval(clock.t);
  signIn(S.mobile);
  S.step='done'; paint();
}
function again(){
  S.wait=TTL; const f=$('#lgCode'); if(f) f.value='';
  const e2=$('#lgErr2'); if(e2) e2.hidden=true;
  tick(); const h=$('#lgMsg'); if(h) h.textContent='کد تازه به '+msgOf(S.via).n+' رفت';
  const w=$('#lgWait'); if(w){ w.classList.add('ping'); setTimeout(()=>w.classList.remove('ping'),900) }
  status('کد تازه رفت؛ همان پیام‌گیر را ببین.');
}
function toPhone(){
  clearInterval(clock.t); S.step='phone'; S.err=''; paint();
  setTimeout(()=>{ const f=$('#lgPhone'); if(f){ try{f.focus()}catch(e){} } },120);
}

/* ── ورقهٔ قوانین ─────────────────────────────────────────────────── */
function rulesSheet(){
  const items=(L.rules||[]).map(([t,s])=>`<div class="srow rrow">${'<svg class="i" aria-hidden="true"><use href="#i-check"/></svg>'}
      <span class="sp"><b>${esc(t)}</b><small>${esc(s)}</small></span></div>`).join('');
  const open=sheet('shRules',`<div class="grabber"></div>
    <div class="row" style="align-items:center;margin-bottom:8px">
      <span><span class="head">قوانین و شرایط استفاده</span>
        <span class="cap" style="display:block;margin-top:4px">${esc(L.rulesLead||'')}</span></span>
      <span class="sp" style="flex:1"></span>
      <button class="icon-btn" data-close aria-label="بستن"><svg class="i"><use href="#i-close"/></svg></button></div>
    <div class="lgrulebox">${items}</div>
    <p class="lgcap" style="margin:12px 2px 0">${esc(L.rulesFoot||'')}</p>
    <div class="row" style="margin-top:12px">
      <a class="btn primary" href="support.html">پشتیبانی و راهنما</a>
      <button class="btn quiet" data-close>بستم</button></div>`);
  if(!open) toast2('ورقهٔ قوانین باز نشد');
}

/* ── سیم‌کشی ──────────────────────────────────────────────────────── */
document.addEventListener('submit',e=>{
  const f=e.target;
  if(f&&f.id==='lgForm'){ e.preventDefault(); tryPhone('') }
  if(f&&f.id==='lgForm2'){ e.preventDefault(); tryCode() }
},false);

document.addEventListener('click',e=>{
  const t=e.target;
  if(t.closest('#rulesBtn')){ e.preventDefault(); rulesSheet(); return }
  if(t.closest('[data-go-support]')){ location.href='support.html'; return }
  if(t.closest('#lgOutMost')){ signOut(); S.step='phone'; S.mobile=''; paint(); toast2('از حساب بیرون آمدی'); return }
  if(t.closest('#lgAgain')){ e.preventDefault(); again(); return }
  if(t.closest('#lgBack')){ e.preventDefault(); toPhone(); return }
  if(t.closest('[data-close]')){ shut(); return }
  const vm=t.closest('[data-via]');
  if(vm){ e.preventDefault(); S.via=vm.dataset.via; tryPhone(vm.dataset.via); return }
  if(t.closest('#scrim')){ shut(); return }
},false);

document.addEventListener('input',e=>{
  const el=e.target;
  if(!el) return;
  if(el.id==='lgPhone'){
    const v=unFa(el.value).replace(/\D/g,'').slice(0,11);
    el.value=faN(v); pref();
    if(S.err) err('');
    const go=$('#lgGo'); if(go) go.disabled=false;
  }
  if(el.id==='lgCode'){
    const v=unFa(el.value).replace(/\D/g,'').slice(0,CODE_LEN);
    el.value=faN(v);
    const e2=$('#lgErr2'); if(e2) e2.hidden=true;
    const ok=$('#lgOk'); if(ok) ok.disabled=false;
  }
},false);

document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){ shut(); return }
  if(e.key==='Enter'&&S.step==='phone'&&document.activeElement&&document.activeElement.id==='lgPhone'){
    e.preventDefault(); tryPhone('')
  }
},false);

/* ── آغاز ─────────────────────────────────────────────────────────── */
function boot(){
  const u=store.get('nora-home-user');
  if(u&&u.name) S.step='already';
  else{
    const pend=store.get('nora-home-auth');
    if(pend&&pend.mobile&&isMob(pend.mobile)){ S.mobile=pend.mobile; S.step='hand' }
  }
  const eye=$('#lgEye'); if(eye) eye.textContent=L.eye||'گروه فرهنگی خط زندگی';
  document.title='نورا · ورود';
  paint();
  if(S.step==='phone'){ const f=$('#lgPhone'); if(f&&matchMedia('(min-width:520px)').matches){ try{f.focus()}catch(e){} } }
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot); else boot();

/* برای آزمون و صفحه‌های دیگر */
window.NORA_LOGIN={state:S,signIn:signIn,signOut:signOut,nextUrl:nextUrl};
})();
