/* ══════════════════════════════════════════════════════════════════════════
   نورا — صفحهٔ ورود
   ──────────────────────────────────────────────────────────────────────────
   یک کار: شماره و کد امنیتی می‌گیری، بعد کد چهاررقمی می‌آید و حساب باز می‌شود.
   ورود اصلی همین است: کد را سفیر بله می‌فرستد.

   پله‌ها:  شماره → کد چهاررقمی ربات → پایان · و برای مدیران: پلهٔ خودش
   هیچ دکمه یا نشان پیام‌گیری این‌جا نیست؛ تنها یک پیوند متنی به ربات رمز
   یک‌بارمصرف هست تا اگر کد نیامد، خودِ کاربر سراغش برود.
   ══════════════════════════════════════════════════════════════════════════ */
(function(){
'use strict';

/* ── داده ─────────────────────────────────────────────────────────── */
const N=window.NORA||{}, A=N.ACCOUNT||{}, L=A.login||{};
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
/* قفل کد امنیتی از نشست پیشین هم خوانده می‌شود */
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

/* ── پیوند ربات رمز یکبارمصرف (سفیر بله) ───────────────────────────
   روی صفحه، هیچ نشان و دکمهٔ پیام‌گیری نیست؛ فقط همین یک لینک ساده
   می‌ماند که اگر کاربر خواست، ربات را در تب تازه باز کند. */
const OTP=(L.otp||{});
const OTP_NAME=OTP.n||'ربات رمز یک‌بارمصرف نورا';
const OTP_HREF=(OTP.href||'https://ble.ir/verification_code_bot')+'?start=login';

/* ── حالت ─────────────────────────────────────────────────────────── */
const CAP=L.cap||{}, CAP_CODES=(CAP.codes||[]).slice();
const CAP_TRIES=+(CAP.tries||3), CAP_LOCK=+(CAP.lockMin||5)*60000;
const LOCK_KEY='nora-home-caplock';
const S={step:'phone', mobile:'', err:'', wait:TTL, tries:0,
         cap:'', capTries:0, capLock:0};
(function(){ const t=+store.get(LOCK_KEY)||0; if(t>Date.now()) S.capLock=t })();

/* ── وضعیت ────────────────────────────────────────────────────────── */
function status(t){ const el=$('#lgStatus'); if(!el) return; el.hidden=!t; el.textContent=t||'' }
function err(t,sel){ S.err=t||'';
  const el=$(sel||'#lgErr'); if(el){ el.hidden=!t; el.textContent=t||'' }
  const hit=$(sel==='#lgErr2'?'#lgOtp':(sel||'#lgErr')==='#lgErr2'?'#lgOtp':'#lgTel');
  if(hit&&t){ hit.classList.add('bad'); setTimeout(()=>hit.classList.remove('bad'),460) }
}

/* ── جمله‌های اطمینان ────────────────────────────────────────────── */
const TRUST=((N.TRUST&&N.TRUST.row)||(L.trust&&L.trust.row)||[]);
const trustOf=w=>{ const r=TRUST.find(x=>String(x[0]).indexOf(w)>-1); return r?r[1]:'' };
function trustLine(){
  const a=trustOf('رمزنگاری گذرگاه')||'همهٔ رفت‌وآمد این صفحه رمزنگاری‌شده است.';
  const b=trustOf('کد یک‌بارمصرف')||'ورود با کد یک‌بارمصرف است.';
  return `<p class="lgtrust"><svg class="i" aria-hidden="true"><use href="#i-shield"/></svg>
    <span>${esc(a)} ${esc(b)}</span></p>`;
}

/* ── کد امنیتی تصویری ─────────────────────────────────────────────── */
function capPick(){ return CAP_CODES[Math.floor(Math.random()*CAP_CODES.length)]||'4173' }
function rndOf(seed,i){ const x=Math.sin(seed*127.1+i*311.7)*43758.5453; return x-Math.floor(x) }
/* تصویر عدد: چهار رقم با چرخش و جابه‌جایی و چند خط و نقطهٔ نویز */
function capSVG(code,seed){
  const cols=['#123A6B','#0E6E4E','#7A3E12','#4A2A7A','#0B5D7A','#6B1230'];
  const digits=String(code).split('');
  const parts=digits.map((d,i)=>{
    const r1=rndOf(seed,i*3+1), r2=rndOf(seed,i*3+2), r3=rndOf(seed,i*3+3);
    const x=14+i*21+(r1*7-3.5), y=33+(r2*9-4.5), rot=(r3*54-27).toFixed(1);
    const size=(25+r1*5).toFixed(1), col=cols[Math.floor(r3*cols.length)];
    return `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" fill="${col}" font-size="${size}"
      font-weight="800" font-family="inherit" text-anchor="middle"
      transform="rotate(${rot} ${x.toFixed(1)} ${y.toFixed(1)})">${faN(d)}</text>`;
  }).join('');
  const lines=[0,1,2].map(i=>{
    const a=rndOf(seed,i+41), b=rndOf(seed,i+47), c=rndOf(seed,i+53), e=rndOf(seed,i+59);
    return `<path d="M${(a*12).toFixed(1)} ${(b*52).toFixed(1)} Q ${(40+c*20).toFixed(1)} ${(e*52).toFixed(1)}
      ${(96-a*10).toFixed(1)} ${(c*52).toFixed(1)}" fill="none" stroke="${cols[Math.floor(a*cols.length)]}"
      stroke-width="1.1" opacity=".45"/>`;
  }).join('');
  const dots=Array.from({length:16},(_,i)=>{
    const a=rndOf(seed,i+71), b=rndOf(seed,i+79);
    return `<circle cx="${(a*100).toFixed(1)}" cy="${(b*50).toFixed(1)}" r="${(0.7+a*1.2).toFixed(1)}"
      fill="${cols[Math.floor(b*cols.length)]}" opacity=".35"/>`;
  }).join('');
  return `<svg viewBox="0 0 100 50" role="img" aria-label="${esc(CAP.alt||'تصویر کد امنیتی')}">
    <rect width="100" height="50" rx="9" fill="rgba(0,113,227,.06)"/>${parts}${lines}${dots}</svg>`;
}
function capLocked(){ return S.capLock>Date.now() }
function capLeft(){ return Math.max(0,Math.ceil((S.capLock-Date.now())/1000)) }
function capLockTxt(){ return String(CAP.lockLead||'چند بار اشتباه زدی؛ تا {t} صبر کن.')
  .replace('{t}',faN(capLeft())+' ثانیه') }
function capNew(fresh){
  if(capLocked()) return;
  if(fresh!==false) S.cap=capPick();
  const el=$('#lgCapImg'); if(el) el.innerHTML=capSVG(S.cap,Math.floor(Math.random()*9999));
  const f=$('#lgCap'); if(f){ f.value=''; if(fresh!==false){ try{f.focus()}catch(e){} } }
}
const lockClock={t:0};
function lockTick(){
  clearInterval(lockClock.t);
  const draw=()=>{
    const box=$('#lgCapBox'); if(!box) return;
    if(capLocked()){
      box.classList.add('lock');
      const note=$('#lgCapNote'); if(note){ note.hidden=false; note.textContent=capLockTxt() }
      const f=$('#lgCap'); if(f) f.disabled=true;
      const b=$('#lgCapNew'); if(b) b.disabled=true;
    } else {
      clearInterval(lockClock.t); S.capLock=0; store.del(LOCK_KEY);
      err(''); paint(); return;
    }
  };
  draw(); lockClock.t=setInterval(draw,1000);
}

/* ── پلهٔ ۱: شماره ────────────────────────────────────────────────── */
function stepPhone(){
  return `<form class="lgstep" id="lgForm" novalidate>
    <label class="lglbl" for="lgPhone">${esc(L.q||'تلفن همراه خود را وارد کنید:')}</label>
    <div class="lgtel" id="lgTel">
      <span class="pref" id="lgPref" aria-hidden="true">۰۹</span>
      <input class="lginp num" id="lgPhone" type="tel" inputmode="numeric" autocomplete="tel-national"
        maxlength="11" placeholder="--------" aria-describedby="lgHint" value=""/>
      <span class="fic" aria-hidden="true"><svg class="i"><use href="#i-mobile"/></svg></span>
    </div>
    <label class="lglbl" for="lgCap">${esc(CAP.l||'کد امنیتی تصویر را بنویس:')}</label>
    <div class="lgcapbox" id="lgCapBox">
      <span class="capimg" id="lgCapImg"></span>
      <input class="lginp num capinp" id="lgCap" type="text" inputmode="numeric" maxlength="4"
        autocomplete="off" placeholder="${esc(CAP.ph||'چهار رقم تصویر')}" aria-label="${esc(CAP.l||'کد امنیتی تصویر')}"/>
      <button class="capnew" type="button" id="lgCapNew" aria-label="${esc(CAP.newCap||'تصویر تازه')}"
        title="${esc(CAP.newCap||'تصویر تازه')}"><svg class="i"><use href="#i-refresh"/></svg></button>
    </div>
    <p class="caplock" id="lgCapNote" hidden></p>
    <p class="lghint" id="lgHint">${esc(L.hint||'')}</p>
    <p class="lgerr" id="lgErr" hidden></p>
    ${trustLine()}
    <button class="lgbtn" type="submit" id="lgGo">${esc(L.go||'ورود')}</button>
  </form>
  <button class="lgbtn quiet admin" type="button" id="lgAdminBtn"><svg class="i" aria-hidden="true"><use href="#i-shield"/></svg> ${esc(L.adminBtn||'ورود مدیران')}</button>`;
}

/* ── پلهٔ ۲: کد چهاررقمی ربات ─────────────────────────────────────── */
function stepCode(){
  const len=CODE_LEN;
  const boxes=Array.from({length:len},(_,i)=>
    `<input class="otpbox num" type="text" inputmode="numeric" autocomplete="${i===0?'one-time-code':'off'}"
      maxlength="1" aria-label="رقم ${faN(i+1)} از ${faN(len)}" data-otp="${i}"/>`).join('');
  const bot=`<a class="lgblink" id="lgBotLink" href="${esc(OTP_HREF)}" target="_blank" rel="noopener">${esc(OTP_NAME)}</a>`;
  const lead=esc(L.otpLead||'کد چهاررقمی را «{bot}» می‌فرستد.').replace('{bot}',bot);
  const line=S.mobile
    ? `<b class="num" dir="ltr">${phonePretty(S.mobile)}</b>
       <button class="lgedit" type="button" id="lgEditPhone" aria-label="${esc(L.otpEdit||'عوض کردن شماره')}">
         <svg class="i"><use href="#i-pen"/></svg></button>`
    : `<b class="lgnone">${esc(L.otpUnknown||'شماره‌ات را در ربات می‌فرستی')}</b>
       <button class="lgedit" type="button" id="lgEditPhone" aria-label="${esc(L.change||'تغییر شماره')}">
         <svg class="i"><use href="#i-pen"/></svg></button>`;
  return `<form class="lgstep lgotpstep" id="lgForm2" novalidate>
    <span class="lgbot plain" id="lgBot"><svg class="i" aria-hidden="true"><use href="#i-shield"/></svg></span>
    <div class="lgpline">${line}</div>
    <p class="lgotext" id="lgLead2">${lead}</p>
    <div class="lgotp" id="lgOtp" dir="ltr" role="group" aria-label="${esc(L.codeCap||'کد چهاررقمی ربات')}">${boxes}</div>
    <p class="lgcount" id="lgCountWrap">${esc(L.otpWait||'زمان باقی‌مانده:')} <b id="lgCount">${faN(TTL)}</b> ${esc(L.otpSec||'ثانیه')}</p>
    <p class="lgerr" id="lgErr2" hidden></p>
    <div class="lgbar">
      <button class="lgbtn" type="submit" id="lgOk">${esc(L.go||'ورود')}</button>
    </div>
    <button class="lgbtn quiet again" type="button" id="lgAgain" disabled aria-disabled="true">${esc(L.resend||'دوباره بفرست')}</button>
    ${trustLine()}
    <p class="lgcap">${esc(L.otpNote||'')}</p>
  </form>`;
}

/* ── پلهٔ ۴: ورود مدیران (نام کاربری و گذرواژه، بی رمز پویا) ──────── */
function stepAdmin(){
  return `<form class="lgstep lgadmin" id="lgAdminForm" novalidate>
    <span class="lgadm" aria-hidden="true"><svg class="i"><use href="#i-shield"/></svg></span>
    <b class="lgdtitle">${esc(L.adminTitle||'ورود مدیران')}</b>
    <p class="lgdle">${esc(L.adminLead||'')}</p>
    <label class="lglbl" for="lgUser">${esc(L.adminUser||'نام کاربری')}</label>
    <div class="lgtel" id="lgUserWrap">
      <span class="fic" aria-hidden="true"><svg class="i"><use href="#i-user"/></svg></span>
      <input class="lginp" id="lgUser" type="text" autocomplete="username" autocapitalize="off"
        spellcheck="false" value=""/>
    </div>
    <label class="lglbl" for="lgPass">${esc(L.adminPass||'گذرواژه')}</label>
    <div class="lgtel" id="lgPassWrap">
      <span class="fic" aria-hidden="true"><svg class="i"><use href="#i-lock"/></svg></span>
      <input class="lginp" id="lgPass" type="password" autocomplete="current-password" value=""/>
      <button class="lgedit" type="button" id="lgPassEye" aria-label="نمایش گذرواژه">
        <svg class="i"><use href="#i-eye"/></svg></button>
    </div>
    <p class="lghint">${esc(L.adminDemo||'')}</p>
    <p class="lgerr" id="lgErr3" hidden></p>
    <button class="lgbtn" type="submit" id="lgAdminGo">${esc(L.adminGo||'ورود به پنل مدیران')}</button>
    <p class="lgcap">${esc(L.adminNote||'')}</p>
    <button class="lgbtn quiet" type="button" id="lgAdminBack">${esc(L.change||'بازگشت')}</button>
  </form>`;
}

/* ── پلهٔ ۵: مدیر وارد شد ────────────────────────────────────────── */
function stepAdminDone(){
  return `<div class="lgstep lgdones" id="lgAdminDone">
    <span class="lgcheck ok" aria-hidden="true"><svg class="i"><use href="#i-shield"/></svg></span>
    <b class="lgdtitle">${esc(L.adminOk||'خوش آمدی مدیر سامانه')}</b>
    <p class="lgdle">${esc(L.adminOkLead||'')}</p>
    <a class="lgbtn" href="builder.html" id="lgAdminPanel">${esc(L.adminGo2||'رفتن به فرم‌ها و گزارش‌ها')}</a>
    <a class="lgbtn quiet" href="account.html">حساب من</a>
  </div>`;
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
  const map={phone:stepPhone,code:stepCode,done:stepDone,already:stepAlready,admin:stepAdmin,adminDone:stepAdminDone};
  box.innerHTML=(map[S.step]||stepPhone)();
  const leadEl=$('#lgLead');
  const bare=(S.step==='done'||S.step==='already'||S.step==='admin'||S.step==='adminDone');
  if(leadEl) leadEl.textContent = bare ? '' : (L.lead||'');
  status('');
  if(S.step==='phone'){
    const f=$('#lgPhone'); if(f){ f.value=faN(S.mobile); pref() }
    if(capLocked()){ capNew(false); lockTick() } else { capNew() }
  }
  if(S.step==='admin'){ const u=$('#lgUser'); if(u&&matchMedia('(min-width:520px)').matches) setTimeout(()=>{try{u.focus()}catch(e){}},140) }
  if(S.step==='code'){ tick(); const b=$('.otpbox'); if(b) setTimeout(()=>{ try{b.focus()}catch(e){} },140) }
  if(S.step==='done'){ clearInterval(clock.t); setTimeout(()=>{ if(S.step==='done') location.href=nextUrl() },2200) }
}
function pref(){ const f=$('#lgPhone'), p=$('#lgPref'); if(!f||!p) return;
  p.hidden=!!unFa(f.value).replace(/\D/g,'').length }

/* ── زمان اعتبار کد: ثانیه‌شماری، مثل خودِ پیام‌گیر ───────────────── */
const clock={t:0};
function tick(){
  clearInterval(clock.t); S.wait=TTL;
  const el=$('#lgCount'), again=$('#lgAgain');
  const draw=()=>{
    if(el) el.textContent=faN(Math.max(0,S.wait));
    if(again&&S.wait>0){ again.disabled=true; again.setAttribute('aria-disabled','true') }
    if(S.wait<=0){
      clearInterval(clock.t);
      const w=$('#lgCountWrap'); if(w) w.classList.add('over');
      /* تا شمارش تمام نشود، «دوباره بفرست» قفل است */
      if(again){ again.disabled=false; again.removeAttribute('aria-disabled') }
      const e2=$('#lgErr2');
      if(e2&&e2.hidden){ e2.hidden=false; e2.textContent=(L.otpOver||'زمان کد سر آمد')+' '+(L.otpTtlDone||'') }
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
/* رفتن به پلهٔ کد: کد را سفیر بله به همین شماره می‌فرستد */
function gotoCode(){
  store.set(PEND_KEY,{step:'code',mobile:S.mobile});
  S.step='code'; S.tries=0; paint();
  status('کد چهاررقمی به شماره‌ات فرستاده شد؛ تا '+faN(TTL)+' ثانیه معتبر است.');
}
/* پلهٔ ۱: شماره و کد امنیتی تصویر */
function capVal(){ const f=$('#lgCap'); return unFa(f?f.value:'').replace(/\D/g,'') }
function capWrong(){
  S.capTries=(S.capTries||0)+1;
  if(S.capTries>=CAP_TRIES){
    S.capLock=Date.now()+CAP_LOCK; store.set(LOCK_KEY,S.capLock); S.capTries=0;
    err(''); capNew(); lockTick();
    return;
  }
  err((CAP.wrong||'عدد تصویر درست نیست؛ دوباره بنویس.')+' ('+faN(CAP_TRIES-S.capTries)+' بار دیگر)');
  shake('#lgCapBox'); capNew();
}
function tryPhone(){
  if(capLocked()){ err(capLockTxt()); return false }
  const v=phoneVal();
  if(!isMob(v)){ err('شماره را کامل بنویس؛ یازده رقم، با ۰۹. نمونه: ۰۹۱۲۳۴۵۶۷۸۹'); shake('#lgTel'); return false }
  const c=capVal();
  if(!c){ err(CAP.empty||'عدد تصویر را بنویس.'); shake('#lgCapBox'); return false }
  if(c!==S.cap){ capWrong(); return false }
  S.mobile=v; err(''); S.capTries=0;
  gotoCode();
  return true;
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
  const boxes=$$('.otpbox'); boxes.forEach((b,i)=>{ b.value=''; if(i===0){ try{b.focus()}catch(e){} } });
  S.wait=TTL; const e2=$('#lgErr2'); if(e2) e2.hidden=true;
  const w=$('#lgCountWrap'); if(w) w.classList.remove('over');
  tick();
  status('کد تازه به شماره‌ات رفت.');
  toast2('کد تازه فرستاده شد؛ تا '+faN(TTL)+' ثانیه معتبر است');
}
function toPhone(){
  clearInterval(clock.t); S.step='phone'; S.err=''; paint();
  setTimeout(()=>{ const f=$('#lgPhone'); if(f){ try{f.focus()}catch(e){} } },140);
}

/* ── ورود مدیران: نام کاربری و گذرواژه، بی رمز پویا ─────────────── */
function toAdmin(){ clearInterval(clock.t); S.step='admin'; S.err=''; paint() }
function adminIn(){
  const u=($('#lgUser')||{}).value||'', p=($('#lgPass')||{}).value||'';
  const e3=$('#lgErr3');
  const say=t=>{ if(e3){ e3.hidden=false; e3.textContent=t } };
  if(!u.trim()||!p){ say('نام کاربری و گذرواژه را بنویس.'); return }
  if(u.trim().toLowerCase()!=='admin'||p!=='nora'){
    say('نام کاربری یا گذرواژه درست نیست. '+(L.adminDemo||''));
    const w=$('#lgPassWrap'); if(w){ w.classList.add('bad'); setTimeout(()=>w.classList.remove('bad'),460) }
    return
  }
  try{ localStorage.setItem('nora-home-user',JSON.stringify({name:'مدیر سامانه',role:'admin',
    mobile:'',joined:'۱۴۰۴',certs:0,wallet:0,msgs:0})) }catch(e){}
  try{ localStorage.setItem('nora-admin',JSON.stringify({u:u.trim(),role:'admin',at:Date.now()})) }catch(e){}
  S.step='adminDone'; paint(); toast2('خوش آمدی مدیر سامانه');
}
function togglePass(){
  const f=$('#lgPass'); if(!f) return;
  f.type = f.type==='password' ? 'text' : 'password';
  const b=$('#lgPassEye'); if(b) b.setAttribute('aria-label', f.type==='password'?'نمایش گذرواژه':'پنهان‌کردن گذرواژه');
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
  if(f&&f.id==='lgAdminForm'){ e.preventDefault(); adminIn() }
},false);

document.addEventListener('click',e=>{
  const t=e.target;
  if(t.closest('#rulesBtn')){ e.preventDefault(); rulesSheet(); return }
  if(t.closest('#lgCapNew')){ e.preventDefault(); capNew(); return }
  if(t.closest('#lgAdminBtn')){ e.preventDefault(); toAdmin(); return }
  if(t.closest('#lgAdminBack')){ e.preventDefault(); toPhone(); return }
  if(t.closest('#lgPassEye')){ e.preventDefault(); togglePass(); return }
  if(t.closest('[data-go-support]')){ location.href='support.html'; return }
  if(t.closest('#lgOutMost')){ signOut(); S.step='phone'; S.mobile=''; paint(); toast2('از حساب بیرون آمدی'); return }
  if(t.closest('#lgAgain')){ e.preventDefault(); again(); return }
  if(t.closest('#lgBack')){ e.preventDefault(); toPhone(); return }
  if(t.closest('#lgEditPhone')){ e.preventDefault(); toPhone(); return }
  if(t.closest('[data-close]')){ shut(); return }
  if(t.closest('#scrim')){ shut(); return }
},false);

document.addEventListener('input',e=>{
  const el=e.target; if(!el) return;
  if(el.id==='lgPhone'){
    const v=unFa(el.value).replace(/\D/g,'').slice(0,11);
    el.value=faN(v); pref();
    if(S.err) err('');
  }
  if(el.id==='lgCap'){
    const v=unFa(el.value).replace(/\D/g,'').slice(0,4);
    el.value=faN(v);
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
  else if(pend&&pend.step==='code'&&(pend.mobile&&isMob(pend.mobile))){ S.mobile=pend.mobile; S.step='code' }
  const eye=$('#lgEye'); if(eye) eye.textContent=L.eye||'گروه فرهنگی خط زندگی';
  paint();
  if(S.step==='phone'){ const f=$('#lgPhone'); if(f&&matchMedia('(min-width:520px)').matches){ try{f.focus()}catch(e){} } }
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot); else boot();

/* برای آزمون و صفحه‌های دیگر */
window.NORA_LOGIN={state:S,signIn:signIn,signOut:signOut,nextUrl:nextUrl,otpUrl:()=>OTP_HREF,otpVal:otpVal};
})();
