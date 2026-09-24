/* ══════════════════════════════════════════════════════════════════════════
   نورا — صفحهٔ ورود
   ──────────────────────────────────────────────────────────────────────────
   یک کار: شماره می‌گیری، بعد می‌سپاریش به ربات پیام‌گیر (بله، ایتا، تلگرام)،
   بعد کد چهاررقمی را می‌گیری و حساب باز می‌شود.

   پله‌ها:  شماره → کد چهاررقمی ربات → پایان
   دکمه‌های پیام‌گیر لینک مستقیم همان ربات‌اند: ربات باز می‌شود، شماره را
   می‌خواهد و کد را می‌فرستد؛ ادامه همین‌جا در چهار خانه نوشته می‌شود.
   ══════════════════════════════════════════════════════════════════════════ */
(function(){
'use strict';

/* ── داده ─────────────────────────────────────────────────────────── */
const N=window.NORA||{}, A=N.ACCOUNT||{}, L=A.login||{};
const MSGS=(L.msgs||[]).slice();
const CODE_DEMO=String(L.codeDemo||'5432'), CODE_LEN=+(L.codeLen||4);
const TTL=+(L.ttl||90);                       /* ثانیه، مثل خودِ پیام‌گیر */
const SESS_KEY='nora-home-user', PEND_KEY='nora-home-auth';

/* ── کمکی‌ها ─────────────────────────────────────────────────────── */
const $=s=>document.querySelector(s);
const $$=s=>[...document.querySelectorAll(s)];
const esc=t=>String(t==null?'':t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const faN=n=>String(n==null?'':n).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
const unFa=s=>String(s==null?'':s).replace(/[۰-۹]/g,d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/[٠-٩]/g,d=>'٠١٢٣٤٥٦٧٨٩'.indexOf(d));
const isMob=v=>/^09\d{9}$/.test(v);
/* ۰۹۱۲۳۴۵۶۷۸۹ ← +۹۸ ۹۱۲ ۱۲۳ ۴۵۶۷ */
const phonePretty=m=>m?'+۹۸ '+faN(m.slice(1,4))+' '+faN(m.slice(4,7))+' '+faN(m.slice(7)):'';
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

/* ── نگارهٔ ربات: حباب سبز با تیک، همان‌جور که در پیام‌گیر دیده می‌شود ── */
const TINT={bale:'#12A594', eitaa:'#F5821F', telegram:'#2AABEE'};
function botArt(k){
  const c=TINT[k]||TINT.bale;
  return `<svg viewBox="0 0 64 64" aria-hidden="true">
    <path d="M32 6c14.4 0 26 10 26 25S46.4 58 32 58 6 49 6 34 17.6 6 32 6z" fill="${c}"/>
    <path d="M18 12c-4.6 1.4-8.4 3.8-11 7 3.2.5 6.4.1 9.4-1.2z" fill="${c}"/>
    <path d="M21.6 33.6l7.2 7.4 14.4-15.6" fill="none" stroke="#fff" stroke-width="6.4"
      stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

/* ── نشان پیام‌گیرها ──────────────────────────────────────────────── */
const MARK={
  bale:'<svg viewBox="0 0 40 40" aria-hidden="true"><defs><linearGradient id="gb" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3FBD6D"/><stop offset="1" stop-color="#0E9B62"/></linearGradient></defs><circle cx="20" cy="20" r="20" fill="url(#gb)"/><path d="M11.6 20.8l5.1 5.3L28.4 14" fill="none" stroke="#fff" stroke-width="4.1" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  eitaa:'<svg viewBox="0 0 40 40" aria-hidden="true"><rect x="0" y="0" width="40" height="40" rx="11" fill="#26303B"/><path d="M13.4 20.2v-4.6a6.6 6.6 0 0 1 13.2 0v4.6" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/><rect x="12.2" y="19.4" width="15.6" height="11.4" rx="3.2" fill="#F5821F"/><circle cx="20" cy="25.1" r="1.9" fill="#26303B"/></svg>',
  telegram:'<svg viewBox="0 0 40 40" aria-hidden="true"><defs><linearGradient id="gt" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3FB0E8"/><stop offset="1" stop-color="#1E8BC4"/></linearGradient></defs><circle cx="20" cy="20" r="20" fill="url(#gt)"/><path d="M9.8 19.9l19-7.4-3 15.1-5.6-4.1-3 3.1-.6-4.6z" fill="#fff"/><path d="M16.6 22l11.2-8.6-8.2 12z" fill="#D6EBF7"/></svg>'
};
const markOf=k=>MARK[k]||MARK.bale;
const msgOf=k=>MSGS.find(m=>m.k===k)||MSGS[0]||{k:'bale',n:'بله',hand:'',href:'#'};
/* لینک مستقیم ربات، با پلهٔ ورود در پیام */
function botHref(m){ const u=(m&&m.botUrl)||''; if(!u) return '#'; return u+(u.indexOf('?')>-1?'&':'?')+'start='+((m&&m.start)||'login') }

/* ── حالت ─────────────────────────────────────────────────────────── */
const S={step:'phone', mobile:'', via:(MSGS[0]||{}).k||'bale', err:'', wait:TTL, fromBot:false, tries:0};

/* ── وضعیت ────────────────────────────────────────────────────────── */
function status(t){ const el=$('#lgStatus'); if(!el) return; el.hidden=!t; el.textContent=t||'' }
function err(t,sel){ S.err=t||'';
  const el=$(sel||'#lgErr'); if(el){ el.hidden=!t; el.textContent=t||'' }
  const hit=$(sel==='#lgErr2'?'#lgOtp':(sel||'#lgErr')==='#lgErr2'?'#lgOtp':'#lgTel');
  if(hit&&t){ hit.classList.add('bad'); setTimeout(()=>hit.classList.remove('bad'),460) }
}

/* ── پلهٔ ۱: شماره ────────────────────────────────────────────────── */
function stepPhone(){
  const rows=MSGS.map(m=>`<button class="lgmsg" type="button" data-via="${esc(m.k)}" title="${esc(m.hand||m.s||'')}" aria-label="ورود با ${esc(m.n)}">
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

/* ── پلهٔ ۲: کد چهاررقمی ربات ─────────────────────────────────────── */
function stepCode(){
  const m=msgOf(S.via), len=CODE_LEN;
  const boxes=Array.from({length:len},(_,i)=>
    `<input class="otpbox num" type="text" inputmode="numeric" autocomplete="${i===0?'one-time-code':'off'}"
      maxlength="1" aria-label="رقم ${faN(i+1)} از ${faN(len)}" data-otp="${i}"/>`).join('');
  const bot=`<a class="lgblink" id="lgBotLink" href="${esc(botHref(m))}" target="_blank" rel="noopener">${esc(m.botName||m.n)}</a>`;
  const lead=esc(L.otpLead||'کد ارسال‌شده در بازوی «{bot}» را وارد کنید.').replace('{bot}',bot);
  const line=S.mobile
    ? `<b class="num" dir="ltr">${phonePretty(S.mobile)}</b>
       <button class="lgedit" type="button" id="lgEditPhone" aria-label="${esc(L.otpEdit||'عوض کردن شماره')}">
         <svg class="i"><use href="#i-pen"/></svg></button>`
    : `<b class="lgnone">${esc(L.otpUnknown||'شماره‌ات را در ربات می‌فرستی')}</b>
       <button class="lgedit" type="button" id="lgEditPhone" aria-label="${esc(L.change||'تغییر شماره')}">
         <svg class="i"><use href="#i-pen"/></svg></button>`;
  return `<form class="lgstep lgotpstep" id="lgForm2" novalidate>
    <span class="lgbot${S.fromBot?' from':''}" id="lgBot">${botArt(S.via)}</span>
    <div class="lgpline">${line}</div>
    <p class="lgotext" id="lgLead2">${lead}</p>
    <div class="lgotp" id="lgOtp" dir="ltr" role="group" aria-label="${esc(L.codeCap||'کد چهاررقمی ربات')}">${boxes}</div>
    <p class="lgcount" id="lgCountWrap">${esc(L.otpWait||'زمان باقی‌مانده:')} <b id="lgCount">${faN(TTL)}</b> ${esc(L.otpSec||'ثانیه')}</p>
    <p class="lgerr" id="lgErr2" hidden></p>
    <div class="lgbar">
      <button class="lgbtn" type="submit" id="lgOk">${esc(L.go||'ورود')}</button>
    </div>
    <div class="lgacts">
      <button class="lgbtn quiet" type="button" id="lgAgain">${esc(L.resend||'دوباره بفرست')}</button>
      <a class="lgbtn quiet" id="lgOpen" href="${esc(botHref(m))}" target="_blank" rel="noopener">${esc(L.otpOpen||'باز کردن ربات')}</a>
    </div>
    <p class="lgcap">${esc(L.otpNote||'')}</p>
  </form>`;
}

/* ── پلهٔ ۳: پایان ────────────────────────────────────────────────── */
function stepDone(){
  const u=store.get(SESS_KEY)||{};
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
  const u=store.get(SESS_KEY)||{};
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
  const map={phone:stepPhone,code:stepCode,done:stepDone,already:stepAlready};
  box.innerHTML=(map[S.step]||stepPhone)();
  const leadEl=$('#lgLead');
  if(leadEl) leadEl.textContent = (S.step==='done'||S.step==='already') ? '' : (L.lead||'');
  status('');
  if(S.step==='phone'){ const f=$('#lgPhone'); if(f){ f.value=faN(S.mobile); pref() } }
  if(S.step==='code'){ tick(); const b=$('.otpbox'); if(b) setTimeout(()=>{ try{b.focus()}catch(e){} },140) }
  if(S.step==='done'){ clearInterval(clock.t); setTimeout(()=>{ if(S.step==='done') location.href=nextUrl() },2200) }
}
function pref(){ const f=$('#lgPhone'), p=$('#lgPref'); if(!f||!p) return;
  p.hidden=!!unFa(f.value).replace(/\D/g,'').length }

/* ── زمان اعتبار کد: ثانیه‌شماری، مثل خودِ پیام‌گیر ───────────────── */
const clock={t:0};
function tick(){
  clearInterval(clock.t); S.wait=TTL;
  const el=$('#lgCount');
  const draw=()=>{
    if(el) el.textContent=faN(Math.max(0,S.wait));
    if(S.wait<=0){
      clearInterval(clock.t);
      const w=$('#lgCountWrap'); if(w) w.classList.add('over');
      const e2=$('#lgErr2');
      if(e2&&e2.hidden){ e2.hidden=false; e2.textContent=(L.otpOver||'زمان کد سر آمد') + ' ' + (L.resend||'دوباره بفرست') }
    }
  };
  const w=$('#lgCountWrap'); if(w) w.classList.remove('over');
  draw();
  clock.t=setInterval(()=>{ S.wait--; draw() },1000);
}

/* ── ورود ─────────────────────────────────────────────────────────── */
function signIn(mobile){
  store.set(SESS_KEY,{name:(A.seed||{}).fullName||'سارا محمدی',mobile:mobile||'',joined:'شهریور ۱۴۰۴',
    certs:2,wallet:1250000,msgs:1});
  store.del(PEND_KEY);
  try{ document.dispatchEvent(new CustomEvent('nora:login',{detail:{mobile:mobile}})) }catch(e){}
}
function signOut(){
  store.del(SESS_KEY);
  try{ document.dispatchEvent(new CustomEvent('nora:logout')) }catch(e){}
}

/* ── کارها ────────────────────────────────────────────────────────── */
function phoneVal(){
  const f=$('#lgPhone'); const v=unFa(f?f.value:'').replace(/\D/g,'');
  if(/^9\d{9}$/.test(v)) return '0'+v;              /* بی صفر و ۰۹ هم می‌شود */
  return v;
}
/* رفتن به پلهٔ کد؛ اگر از دکمهٔ پیام‌گیر آمده باشیم، ربات هم باز می‌شود */
function gotoCode(via,openBot){
  if(via) S.via=via;
  const m=msgOf(S.via);
  S.fromBot=!!openBot;
  store.set(PEND_KEY,{step:'code',mobile:S.mobile,via:S.via});
  S.step='code'; S.tries=0; paint();
  if(openBot){
    try{ window.open(botHref(m),'_blank','noopener') }catch(e){}
    status('ربات '+(m.n)+' باز شد؛ شماره‌ات را همان‌جا بفرست تا کد برسد.');
  } else {
    status('کد چهاررقمی به '+(m.n)+' فرستاده شد.');
  }
}
/* پلهٔ ۱ با شماره */
function tryPhone(){
  const v=phoneVal();
  if(!isMob(v)){ err('شماره را کامل بنویس؛ یازده رقم، با ۰۹. نمونه: ۰۹۱۲۳۴۵۶۷۸۹'); return false }
  S.mobile=v; err('');
  gotoCode('',false);
  return true;
}
/* پلهٔ ۱ با دکمهٔ پیام‌گیر: شماره اگر هست، همراه می‌رود؛ اگر نیست، ربات می‌پرسد */
function withMessenger(k){
  const f=$('#lgPhone'); const v=phoneVal();
  S.mobile=isMob(v)?v:''; err('');
  gotoCode(k,true);
}
function otpVal(){ return $$('.otpbox').map(b=>unFa(b.value).replace(/\D/g,'')).join('') }
function shake(sel){ const el=$(sel); if(!el) return; el.classList.add('bad'); setTimeout(()=>el.classList.remove('bad'),460) }
function tryCode(){
  const v=otpVal(), e2=$('#lgErr2');
  if(v.length<CODE_LEN){ if(e2){e2.hidden=false; e2.textContent='کد '+faN(CODE_LEN)+' رقمی را کامل بنویس.'} shake('#lgOtp'); return }
  if(S.wait<=0){ if(e2){e2.hidden=false; e2.textContent=(L.otpOver||'زمان کد سر آمد')+' '+(L.resend||'دوباره بفرست')} return }
  if(v!==CODE_DEMO){ S.tries++;
    if(e2){ e2.hidden=false; e2.textContent='این کد درست نیست؛ کد نمونهٔ این پیش‌نمایش '+faN(CODE_DEMO)+' است.' }
    shake('#lgOtp'); return }
  clearInterval(clock.t);
  signIn(S.mobile||'');
  S.step='done'; paint();
}
function again(){
  if(S.wait<=0) S.wait=TTL;
  const boxes=$$('.otpbox'); boxes.forEach((b,i)=>{ b.value=''; if(i===0){ try{b.focus()}catch(e){} } });
  S.wait=TTL; const e2=$('#lgErr2'); if(e2) e2.hidden=true;
  const w=$('#lgCountWrap'); if(w) w.classList.remove('over');
  tick();
  const m=msgOf(S.via);
  try{ window.open(botHref(m),'_blank','noopener') }catch(e){}
  status('کد تازه به '+m.n+' رفت.');
}
function toPhone(){
  clearInterval(clock.t); S.step='phone'; S.err=''; paint();
  setTimeout(()=>{ const f=$('#lgPhone'); if(f){ try{f.focus()}catch(e){} } },140);
}

/* ── ورقهٔ قوانین ─────────────────────────────────────────────────── */
function rulesSheet(){
  const items=(L.rules||[]).map(([t,s])=>`<div class="srow rrow"><svg class="i" aria-hidden="true"><use href="#i-check"/></svg>
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

/* ── چهار خانهٔ کد: نوشتن، پس رفتن، چسباندن ─────────────────────── */
function boxes(){ return $$('.otpbox') }
function focusBox(i){ const b=boxes()[i]; if(b){ try{b.focus(); b.select&&b.select()}catch(e){} } }
function fillFrom(text,from){
  const d=unFa(text).replace(/\D/g,'').slice(0,CODE_LEN); if(!d) return;
  const all=boxes();
  d.split('').forEach((ch,i)=>{ const b=all[from+i]; if(b) b.value=faN(ch) });
  const next=Math.min(all.length-1,from+d.length);
  focusBox(next);
}

/* ── سیم‌کشی ──────────────────────────────────────────────────────── */
document.addEventListener('submit',e=>{
  const f=e.target;
  if(f&&f.id==='lgForm'){ e.preventDefault(); tryPhone() }
  if(f&&f.id==='lgForm2'){ e.preventDefault(); tryCode() }
},false);

document.addEventListener('click',e=>{
  const t=e.target;
  if(t.closest('#rulesBtn')){ e.preventDefault(); rulesSheet(); return }
  if(t.closest('[data-go-support]')){ location.href='support.html'; return }
  if(t.closest('#lgOutMost')){ signOut(); S.step='phone'; S.mobile=''; paint(); toast2('از حساب بیرون آمدی'); return }
  if(t.closest('#lgAgain')){ e.preventDefault(); again(); return }
  if(t.closest('#lgBack')){ e.preventDefault(); toPhone(); return }
  if(t.closest('#lgEditPhone')){ e.preventDefault(); toPhone(); return }
  if(t.closest('[data-close]')){ shut(); return }
  const vm=t.closest('[data-via]');
  if(vm){ e.preventDefault(); withMessenger(vm.dataset.via); return }
  if(t.closest('#scrim')){ shut(); return }
},false);

document.addEventListener('input',e=>{
  const el=e.target; if(!el) return;
  if(el.id==='lgPhone'){
    const v=unFa(el.value).replace(/\D/g,'').slice(0,11);
    el.value=faN(v); pref();
    if(S.err) err('');
  }
  if(el.classList&&el.classList.contains('otpbox')){
    const d=unFa(el.value).replace(/\D/g,'');
    el.value=d?faN(d.slice(-1)):'';
    const e2=$('#lgErr2'); if(e2) e2.hidden=true;
    const i=+el.dataset.otp;
    if(d.length>1){ fillFrom(d,i); return }
    if(d&&i<CODE_LEN-1) focusBox(i+1);
  }
},false);

document.addEventListener('paste',e=>{
  const el=e.target;
  if(!el||!el.classList||!el.classList.contains('otpbox')) return;
  const txt=(e.clipboardData&&e.clipboardData.getData('text'))||'';
  if(!/\d/.test(unFa(txt))) return;
  e.preventDefault(); fillFrom(txt,+el.dataset.otp);
},false);

document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){ shut(); return }
  const el=e.target;
  if(!el||!el.classList||!el.classList.contains('otpbox')){
    if(e.key==='Enter'&&S.step==='phone'&&document.activeElement&&document.activeElement.id==='lgPhone'){
      e.preventDefault(); tryPhone()
    }
    return;
  }
  const i=+el.dataset.otp;
  if(e.key==='Backspace'){
    if(!unFa(el.value)){
      e.preventDefault();
      const p=boxes()[i-1]; if(p){ p.value=''; focusBox(i-1) }
    }
    return;
  }
  if(e.key==='ArrowLeft'){ if(i>0){ e.preventDefault(); focusBox(i-1) } return }
  if(e.key==='ArrowRight'){ if(i<CODE_LEN-1){ e.preventDefault(); focusBox(i+1) } return }
  if(e.key==='Enter'){ e.preventDefault(); tryCode(); return }
},false);

/* ── آغاز ─────────────────────────────────────────────────────────── */
function boot(){
  const u=store.get(SESS_KEY);
  const pend=store.get(PEND_KEY);
  if(u&&u.name) S.step='already';
  else if(pend&&pend.step==='code'&&(pend.mobile&&isMob(pend.mobile))){ S.mobile=pend.mobile; S.via=pend.via||S.via; S.step='code' }
  else if(pend&&pend.step==='code'&&pend.via){ S.via=pend.via; S.fromBot=true; S.step='code' }
  const eye=$('#lgEye'); if(eye) eye.textContent=L.eye||'گروه فرهنگی خط زندگی';
  paint();
  if(S.step==='phone'){ const f=$('#lgPhone'); if(f&&matchMedia('(min-width:520px)').matches){ try{f.focus()}catch(e){} } }
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot); else boot();

/* برای آزمون و صفحه‌های دیگر */
window.NORA_LOGIN={state:S,signIn:signIn,signOut:signOut,nextUrl:nextUrl,botHref:botHref,otpVal:otpVal};
})();
