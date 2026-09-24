/* ══════════════════════════════════════════════════════════════════════════
   نورا — پشتیبانی و راهنما (صفحهٔ جدا)
   ──────────────────────────────────────────────────────────────────────────
   هر بخش ربات یک کاشی است. روی هر کاشی که بزنی، پاپ‌آپی باز می‌شود با:
     • پرسش‌های پرتکرار همان بخش
     • راهنمای مدیر سامانه
     • راهنمای تصویری و صوتی (پخش‌کنندهٔ نمونه)
     • فرم مرتبطی که مدیر لینک کرده (اگر باشد)
     • و آخرش «پیدا نکردی؟ تیکت بگذار» با صدا، تصویر، ویدیو، فایل و پیوند
   کارشناس هم در همان گفت‌وگو و با همان شکل پاسخ می‌دهد. بی‌ورود هم کار می‌کند.
   ══════════════════════════════════════════════════════════════════════════ */
(function(){
'use strict';

/* ── داده و کمکی‌ها ───────────────────────────────────────────────── */
const N=window.NORA||{}, SUP=N.SUPPORT||{}, SECT=SUP.sections||[], FAQ=(N.FAQ||[]);
const CATS=(N.ACCOUNT&&N.ACCOUNT.policy&&N.ACCOUNT.policy.ticketCats)||[];
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=t=>String(t==null?'':t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const faN=n=>String(n==null?'':n).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
const ico=(i,st)=>`<svg class="i" aria-hidden="true"${st?` style="${st}"`:''}><use href="#${i}"/></svg>`;
const chev=(st)=>`<svg class="i chev" aria-hidden="true"${st?` style="${st}"`:''}><use href="#i-chev-left"/></svg>`;
const UI=()=>window.NORA_UI||{};

const TK_KEY='nora-support-tickets', SEED_KEY='nora-support-seeded';
const MESS={bale:'ble.ir/', tel:'t.me/', soroush:'splus.ir/', gap:'gap.im/'};
const KIND={video:{i:'i-video',n:'ویدیو'}, audio:{i:'i-wave',n:'صدا'}, image:{i:'i-image',n:'تصویر'},
  link:{i:'i-link',n:'پیوند'}, file:{i:'i-file-up',n:'فایل'}, voice:{i:'i-mic',n:'پیام صوتی'}};

/* ── تیکت‌ها: خواندن، نوشتن، کد پیگیری ─────────────────────────────── */
function readTickets(){
  let v=[]; try{ v=JSON.parse(localStorage.getItem(TK_KEY)||'[]') }catch(e){ v=[] }
  return Array.isArray(v)?v:[];
}
function writeTickets(v){ try{ localStorage.setItem(TK_KEY,JSON.stringify(v.slice(0,12))) }catch(e){} }
function today(){
  try{ return new Intl.DateTimeFormat('fa-IR-u-ca-persian',{day:'numeric',month:'long'}).format(new Date()) }
  catch(e){ return 'امروز' }
}
function newCode(){ return String(Math.floor(10000+Math.random()*89999)) }
const mineOf=k=>readTickets().filter(t=>t.sec===k);
const ticketOf=id=>readTickets().find(t=>t.id===id)||null;
const secOf=k=>SECT.find(x=>x.k===k)||null;

/* تیکت نمونه، یک‌بار؛ تا کادر «تیکت‌های من» خالی نماند */
function seedTicket(){
  let done=false; try{ done=localStorage.getItem(SEED_KEY)==='1' }catch(e){}
  if(done||readTickets().length) return;
  const files=[{kind:'image',name:'برگ-گواهی.jpg',size:'۲۴۰ کیلوبایت'}];
  writeTickets([{id:'20451', sec:'cert', cat:'گواهی', text:'گواهی کارگاه عکاسی را چه وقت می‌شود دانلود کرد؟',
    at:'۲ مهر', status:'پاسخ داده شد', anon:false, files:files,
    thread:[{who:'me',at:'۲ مهر',text:'گواهی کارگاه عکاسی را چه وقت می‌شود دانلود کرد؟',files:files},
      {who:'agent',at:'۲ مهر',files:[{kind:'link',name:'lifeline1.ir/nora-ui/verify'}],
       text:'سلام. گواهی بعد از تأیید سرپرست صادر می‌شود و همان روز در حساب من، تب بلیت و گواهی می‌آید. سریال که گرفتی، از صفحهٔ استعلام هم می‌توانی بررسی کنی.'}]}]);
  try{ localStorage.setItem(SEED_KEY,'1') }catch(e){}
}

/* ── کاشی‌های بخش‌های ربات ────────────────────────────────────────── */
function matches(s,q){
  const hay=[s.n,s.s,s.cat||'',...s.faq.map(f=>f[0]+' '+f[1]),...(s.tips||[]),...(s.media||[]).map(m=>m.t)]
    .join(' ').toLowerCase();
  return hay.indexOf(q.toLowerCase())>=0;
}
function tileHTML(s,i){
  const n=mineOf(s.k).length;
  return `<button class="stile anim" style="--i:${Math.min(i,8)}" data-sec="${esc(s.k)}">
      <span class="sico">${ico(s.i)}</span>
      <b>${esc(s.n)}</b>
      <small>${esc(s.s)}</small>
      <span class="smeta">${faN(s.faq.length)} پرسش${s.form?' · فرم دارد':''}${n?` · ${faN(n)} تیکت`:''}</span>
      <span class="sbars" aria-hidden="true">${(s.media||[]).map(()=>'<i></i>').join('')}</span>
    </button>`;
}
function renderTiles(q){
  const box=$('#stiles'); if(!box) return;
  const key=String(q||'').trim();
  const hit=SECT.filter(s=>!key||matches(s,key));
  box.innerHTML=hit.map(tileHTML).join('');
  const c=$('#tilesCount'); if(c) c.textContent=faN(hit.length)+' از '+faN(SECT.length)+' بخش';
  const e=$('#tilesEmpty'); if(e) e.hidden=hit.length>0;
  const t=$('#tilesTitle'); if(t) t.textContent=key?('بخش‌های مرتبط با «'+key+'»'):'بخش‌های ربات';
}

/* ── جست‌وجو در پرسش‌ها ───────────────────────────────────────────── */
function renderQuery(q){
  const box=$('#qres'), list=$('#qlist'); if(!box||!list) return;
  const key=String(q||'').trim();
  if(key.length<2){ box.hidden=true; list.innerHTML=''; return }
  const k=key.toLowerCase(), rows=[];
  SECT.forEach(s=>s.faq.forEach(f=>{ if((f[0]+' '+f[1]).toLowerCase().indexOf(k)>=0) rows.push({s:s,f:f}) }));
  FAQ.forEach(f=>{ if((f[0]+' '+f[1]).toLowerCase().indexOf(k)>=0) rows.push({s:null,f:f}) });
  box.hidden=rows.length===0;
  list.innerHTML=rows.slice(0,8).map(r=>`<button class="qrow" data-sec="${esc(r.s?r.s.k:'login')}">
      ${ico('i-help','width:17px;height:17px')}
      <span class="qtx"><b>${esc(r.f[0])}</b><small>${esc(r.s?r.s.n:'پرسش‌های پرتکرار نورا')}</small>
        <span class="qans">${esc(r.f[1])}</span></span>
      ${chev('width:15px;height:15px')}</button>`).join('');
}

/* ── کارشناس‌ها، مدیریت، فرم‌های لینک‌شده ─────────────────────────── */
function expertHTML(e){
  const links=(e.m||[]).map(m=>`<a class="mchip" href="https://${esc(MESS[m.k]||'t.me/')}${esc(m.h)}"
      target="_blank" rel="noopener">${esc(m.k)}<span class="mh">@${esc(m.h)}</span></a>`).join('');
  return `<div class="erow2">
      <span class="eav" aria-hidden="true">${esc(String(e.n||'').trim().slice(0,1))}</span>
      <span class="etx"><b>${esc(e.n)}</b><small>${esc(e.r)}</small>
        <span class="mlinks">${links}</span></span>
      ${e.on?'<span class="tag ok xs">آنلاین</span>':'<span class="tag xs">بعداً</span>'}
    </div>`;
}
function renderExperts(){
  const box=$('#exList'); if(!box) return;
  box.innerHTML=(SUP.experts||[]).map(expertHTML).join('');
  const c=$('#exCount'); if(c) c.textContent=faN((SUP.experts||[]).filter(e=>e.on).length)+' نفر آنلاین';
  const lv=$('#supLive'); if(lv) lv.textContent=(SUP.experts||[]).some(e=>e.on)?'آنلاین':'خارج از ساعت';
}
function renderManagers(){
  const box=$('#mgList'); if(!box) return;
  box.innerHTML=(SUP.managers||[]).map(m=>`<a class="drow" href="${esc(m.href)}">
      <span class="dic gold">${ico('i-users')}</span>
      <span class="dtx"><b>${esc(m.n)}</b><small>${esc(m.r)} · ${esc(m.why)}</small></span>
      ${chev()}</a>`).join('');
}
function renderForms(){
  const box=$('#fmList'); if(!box) return;
  const rows=SECT.filter(s=>s.form);
  const extra=(SUP.managers||[]).filter(m=>m.href&&m.href.indexOf('form.html')===0)
    .map(m=>({form:{t:m.r,href:m.href},n:m.n}));
  box.innerHTML=rows.concat(extra).map(s=>`<a class="drow" href="${esc(s.form.href)}">
      <span class="dic brand">${ico('i-doc')}</span>
      <span class="dtx"><b>${esc(s.form.t)}</b><small>${esc(s.n)} · لینک‌شده از سوی مدیر سامانه</small></span>
      ${chev()}</a>`).join('')
    +`<p class="cap" style="margin:8px 3px 0">در چند مورد، پیش از تیکت باید فرم مرتبط پر شود؛ همان‌ها این‌جاست.</p>`;
}

/* ── تیکت‌های من ─────────────────────────────────────────────────── */
function renderMine(){
  const box=$('#mine'), list=$('#tkList'), c=$('#tkCount'); if(!box||!list) return;
  const T=readTickets();
  box.hidden=T.length===0;
  if(c) c.textContent=T.length?faN(T.length)+' تیکت':'';
  list.innerHTML=T.map(t=>{
    const s=secOf(t.sec)||{};
    const nf=(t.files||[]).length;
    return `<button class="tkrow" data-tk="${esc(t.id)}">
      <span class="tki ${t.status==='پاسخ داده شد'?'ok':''}">${ico(t.status==='پاسخ داده شد'?'i-check':'i-clock')}</span>
      <span class="tktx"><b>${esc(s.n||t.cat||'تیکت')}</b><small>${esc(String(t.text||'')).slice(0,64)}${String(t.text||'').length>64?'…':''}</small>
        <span class="tkmeta">${ico('i-clock')} ${esc(t.at||'')} · کد ${faN(t.id)}${t.anon?' · بی‌نام':''}${nf?' · '+faN(nf)+' پیوست':''}</span></span>
      <span class="tag xs ${t.status==='پاسخ داده شد'?'ok':'brand'}">${esc(t.status)}</span>
    </button>`}).join('');
}

/* ── پرسش‌های پرتکرار کلی ────────────────────────────────────────── */
function renderFaqAll(){
  const box=$('#faqAll'); if(!box) return;
  box.innerHTML=FAQ.map((f,i)=>`<details class="faq"${i===0?' open':''}>
      <summary>${esc(f[0])}</summary><p>${esc(f[1])}</p></details>`).join('');
}

/* ── پاپ‌آپ هر کاشی ──────────────────────────────────────────────── */
const M={sec:null, ticket:false, cat:'', files:[], attach:''};
function mediaCard(m,i){
  const k=KIND[m.kind]||KIND.file;
  const inner=m.src?`<img src="${esc(m.src)}" alt="${esc(m.t)}" loading="lazy"/>`
    :`<span class="mmock">${ico(m.kind==='audio'?'i-wave':'i-video')}</span>`;
  return `<button class="mcard" data-media="${i}">
      <span class="mthumb ${esc(m.kind)}">${inner}
        <span class="mplay">${ico(m.kind==='audio'?'i-wave':'i-play-f')}</span></span>
      <span class="mtx"><b>${esc(m.t)}</b><small>${esc(k.n)}${m.len?' · '+esc(m.len):''}</small></span>
      ${chev('width:15px;height:15px')}</button>`;
}
function fileChip(f,i){
  const k=KIND[f.kind]||KIND.file;
  return `<span class="fchip">${ico(k.i)}
    <span class="ftx"><b>${esc(f.name)}</b><small>${esc(k.n)}${f.size?' · '+esc(f.size):''}</small></span>
    <button type="button" class="fx" data-frm="${i}" aria-label="برداشتن ${esc(f.name)}">${ico('i-close')}</button></span>`;
}
const filesBox=()=>`<div class="fchips" id="fChips"${M.files.length?'':' hidden'}>${M.files.map(fileChip).join('')}</div>`;
function attachRow(){
  return `<div class="arow">
      <button type="button" class="abtn" data-rec>${ico('i-mic')} صدا</button>
      <button type="button" class="abtn" data-pick="image">${ico('i-image')} تصویر</button>
      <button type="button" class="abtn" data-pick="video">${ico('i-video')} ویدیو</button>
      <button type="button" class="abtn" data-pick="file">${ico('i-clip')} فایل</button>
      <button type="button" class="abtn" data-linkopen>${ico('i-link')} پیوند</button>
    </div>
    <div class="linrow" id="linRow" hidden>
      <label class="sr" for="linUrl">نشانی پیوند</label>
      <input class="input" id="linUrl" placeholder="https://…" inputmode="url" autocomplete="off"/>
      <button type="button" class="btn sm primary" data-linkadd>افزودن</button>
    </div>
    <input type="file" id="fImage" class="sr" accept="image/*" multiple/>
    <input type="file" id="fVideo" class="sr" accept="video/*" multiple/>
    <input type="file" id="fFile" class="sr" multiple/>
    <input type="file" id="fAudio" class="sr" accept="audio/*"/>
    <p class="cap" style="margin:7px 2px 0" id="recNote"></p>`;
}
function composerHTML(s){
  const anon=(M.cat==='بی‌نام')||s.k==='anon';
  return `<div class="ticketbox" id="ticketBox">
      <div class="tbtop">${ico('i-pen')}<b>پیدا نکردی؟ تیکت بگذار</b>
        <span class="sp"></span><span class="cap">${esc(SUP.reply||'')}</span></div>
      <div class="chipsline" role="group" aria-label="دستهٔ تیکت">
        ${CATS.map(c=>`<button type="button" class="pickc${(M.cat||s.cat||'')===c?' on':''}"
          data-tcat="${esc(c)}" aria-pressed="${(M.cat||s.cat||'')===c}">${esc(c)}</button>`).join('')}
        <button type="button" class="pickc${anon?' on':''}" data-tcat="بی‌نام" aria-pressed="${anon}">بی‌نام</button>
      </div>
      <label class="lbl" for="tkText" style="margin-top:9px;display:block">متن پیام</label>
      <textarea class="input" id="tkText" rows="3" style="margin-top:6px"
        placeholder="${esc(anon?'هر چه می‌خواهی بنویس؛ بی‌نام می‌ماند':'مشکل را کوتاه بنویس؛ اگر فایل یا صدا داری، همین‌جا بچسبان')}"></textarea>
      ${attachRow()}
      ${filesBox()}
      <div class="row" style="margin-top:10px">
        <button type="button" class="btn primary" data-tksend>${ico('i-send')} فرستادن تیکت</button>
        <span class="sp"></span>
        <span class="cap">${anon?'بی‌نام ثبت می‌شود':'کد پیگیری همان لحظه ساخته می‌شود'}</span>
      </div>
    </div>`;
}
function threadHTML(t){
  return `<div class="thread">
      <div class="thhead">${ico('i-headphone')}<b>گفت‌وگو · کد ${faN(t.id)}</b>
        <span class="sp"></span>
        <span class="tag xs ${t.status==='پاسخ داده شد'?'ok':'brand'}">${esc(t.status)}</span></div>
      ${(t.thread||[]).map(m=>`<div class="bubble ${m.who==='agent'?'ag':'me'}">
        <span class="who">${m.who==='agent'?'کارشناس پشتیبانی':'تو'}</span>
        <p>${esc(m.text)}</p>
        ${(m.files||[]).map(f=>{const k=KIND[f.kind]||KIND.file;
          return `<span class="fbubble">${ico(k.i)}<span>${esc(f.name)}</span></span>`}).join('')}
        <small>${esc(m.at||'')}</small></div>`).join('')}
      <p class="cap" style="margin:8px 3px 0">کارشناس هم می‌تواند صدا، تصویر، ویدیو و پیوند بفرستد؛ همه در همین گفت‌وگو می‌ماند.</p>
    </div>`;
}
function bodyFor(s){
  const own=mineOf(s.k);
  return `<div class="mpart">${ico('i-help')}<b>پرسش‌های پرتکرار این بخش</b></div>
    ${s.faq.map(f=>`<details class="faq"><summary>${esc(f[0])}</summary><p>${esc(f[1])}</p></details>`).join('')}
    <div class="mpart">${ico('i-sparkle')}<b>راهنمای مدیر سامانه</b></div>
    <ul class="tips">${(s.tips||[]).map(t=>`<li>${ico('i-check')}<span>${esc(t)}</span></li>`).join('')}</ul>
    <div class="mpart">${ico('i-video')}<b>راهنمای تصویری و صوتی</b></div>
    <div class="mcards">${(s.media||[]).map(mediaCard).join('')}</div>
    ${s.form?`<div class="mpart">${ico('i-doc')}<b>فرم مرتبط این بخش</b></div>
      <a class="drow" href="${esc(s.form.href)}">
        <span class="dic brand">${ico('i-doc')}</span>
        <span class="dtx"><b>${esc(s.form.t)}</b><small>مدیر سامانه این فرم را به همین بخش لینک کرده</small></span>
        ${chev()}</a>`:''}
    ${own.length?`<div class="mpart">${ico('i-headphone')}<b>تیکت‌های تو در این بخش</b></div>${own.map(threadHTML).join('')}`:''}
    <div id="tkSlot"${M.ticket?'':' hidden'}>${composerHTML(s)}</div>`;
}
function renderModal(s){
  const box=$('#modal'); if(!box||!s) return;
  $('#mIco').innerHTML=ico(s.i);
  $('#mTitle').textContent=s.n;
  $('#mSub').textContent=s.s;
  $('#mBody').innerHTML=bodyFor(s);
  box.hidden=false; document.body.classList.add('modal-open');
  const sc=$('#scrim'); if(sc) sc.classList.add('on');
  const close=$('#modal [data-mclose]'); if(close&&close.focus) close.focus();
}
function revealComposer(){
  const s=secOf(M.sec); if(!s) return;
  const slot=$('#tkSlot');
  if(slot){ slot.hidden=false; if(!slot.innerHTML.trim()) slot.innerHTML=composerHTML(s) }
  const el=$('#tkText'); if(el&&el.focus) el.focus();
  const b=$('#mBody'); if(b&&b.scrollTo) b.scrollTo({top:b.scrollHeight,behavior:'smooth'});
}
function openSec(k,opt){
  const s=secOf(k); if(!s) return;
  M.sec=k; M.ticket=!!(opt&&opt.ticket); M.files=[]; M.attach=(opt&&opt.attach)||'';
  M.cat=(opt&&opt.cat)||(k==='anon'?'بی‌نام':(s.cat||''));   /* صندوق بی‌نام، از پیش بی‌نام */
  renderModal(s);
  if(M.ticket) revealComposer();
  if(M.attach==='voice') startVoice();
  try{ history.replaceState(null,'','#'+k) }catch(e){}
}
function closeModal(){
  const box=$('#modal'); if(!box||box.hidden) return;
  box.hidden=true; document.body.classList.remove('modal-open');
  const sc=$('#scrim'); if(sc&&!$$('.sheet.on').length) sc.classList.remove('on');
  M.sec=null; M.ticket=false; M.files=[]; M.attach='';
  try{ history.replaceState(null,'',location.pathname) }catch(e){}
}

/* ── پخش‌کنندهٔ نمونهٔ راهنما ─────────────────────────────────────── */
const PL={on:false,sec:0,len:60,run:null,back:null,txt:''};
const lenToSec=len=>{ const m=String(len||'').match(/(\d+):(\d+)/); return m?(+m[1])*60+(+m[2]):60 };
const mmss=s=>faN(Math.floor(s/60))+':'+faN(String(s%60).padStart(2,'0'));
/* متن راهنمای نمونه؛ همان متن پرسش‌ها و نکته‌های همان بخش */
function guideText(s){
  const a=s.faq[0]||['',''], b=s.faq[1]||['',''];
  const tips=(s.tips||[]).slice(0,2).join(' ');
  return ['راهنمای بخش '+s.n+'.', a[0]+'. '+a[1], b[0]+'. '+b[1], tips,
    'اگر جایی گیر کردی، از همین بخش تیکت بگذار؛ کارشناس تا پایان روز کاری پاسخ می‌دهد.'].join(' ').trim();
}
function openMedia(s,i){
  const m=(s.media||[])[i]; if(!m) return;
  const k=KIND[m.kind]||KIND.file;
  PL.on=false; PL.sec=0; PL.len=lenToSec(m.len); PL.back=M.sec; PL.txt=guideText(s);
  const visual=m.src?`<img src="${esc(m.src)}" alt="${esc(m.t)}"/>`
    : `<span class="pbsim" aria-hidden="true">${'<i></i>'.repeat(8)}</span>`;
  $('#mdBody').innerHTML=`<div class="grabber" aria-hidden="true"></div>
    <div class="row" style="align-items:center">
      <div><div class="head">${esc(m.t)}</div>
        <div class="cap">${esc(k.n)}${m.len?' · '+esc(m.len):''} · بخش «${esc(s.n)}»</div></div>
      <span class="sp"></span>
      <button class="icon-btn" data-close aria-label="بستن راهنما">${ico('i-close')}</button></div>
    <div class="pbox ${esc(m.kind)}">${visual}</div>
    <div class="pbar" role="progressbar" aria-label="پیشرفت پخش" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><i id="pFill" style="width:0%"></i></div>
    <div class="row" style="margin-top:10px">
      <button class="btn primary" id="pToggle">${ico('i-play-f')} پخش</button>
      <span class="sp"></span>
      <span class="cap" id="pTime">۰:۰۰ / ${esc(m.len||'')}</span></div>
    <p class="cap" style="margin:10px 2px 0">این پخش‌کنندهٔ نمونه است؛ متن همین راهنما را می‌خواند. فایل اصلی هر راهنما را مدیر سامانه از همین‌جا می‌گذارد.</p>`;
  const box=$('#modal'); if(box&&!box.hidden) box.hidden=true;      /* راهنما روی پاپ‌آپ نمی‌نشیند */
  openSheet('shMedia');
  readAloud(PL.txt);
}
function readAloud(text){
  try{
    if(!window.speechSynthesis||!window.SpeechSynthesisUtterance) return;
    speechSynthesis.cancel();
    const u=new SpeechSynthesisUtterance(text);
    u.lang='fa-IR'; u.rate=.96;
    window.__noraGuide=u; speechSynthesis.speak(u);
  }catch(e){}
}
function togglePlay(){
  PL.on=!PL.on;
  const b=$('#pToggle');
  if(b) b.innerHTML=PL.on?(ico('i-pause')+' توقف'):(ico('i-play-f')+' پخش');
  try{ if(window.speechSynthesis) PL.on?speechSynthesis.resume():speechSynthesis.pause() }catch(e){}
  clearInterval(PL.run);
  if(!PL.on) return;
  PL.run=setInterval(()=>{
    PL.sec+=1;
    const f=$('#pFill'), t=$('#pTime'), pb=$('.pbar');
    const pct=Math.min(100,Math.round(PL.sec/PL.len*100));
    if(f) f.style.width=pct+'%';
    if(pb&&pb.setAttribute) pb.setAttribute('aria-valuenow',String(pct));
    if(t) t.textContent=mmss(Math.min(PL.sec,PL.len))+' / '+mmss(PL.len);
    if(PL.sec>=PL.len){
      clearInterval(PL.run); PL.on=false;
      if(b) b.innerHTML=ico('i-play-f')+' پخش';
      toast('راهنمای نمونه تا آخر پخش شد');
    }
  },600);
}

/* ── پیوست‌ها: صدا، تصویر، ویدیو، فایل، پیوند ────────────────────── */
function guessKind(t){
  if(t.indexOf('image')===0) return 'image';
  if(t.indexOf('video')===0) return 'video';
  if(t.indexOf('audio')===0) return 'audio';
  return 'file';
}
function human(n){
  if(n<1024) return faN(n)+' بایت';
  if(n<1024*1024) return faN(Math.round(n/1024))+' کیلوبایت';
  return faN((n/1024/1024).toFixed(1))+' مگابایت';
}
function addFiles(list,kind){
  [...(list||[])].forEach(f=>{
    let url=''; try{ url=URL.createObjectURL?URL.createObjectURL(f):'' }catch(e){}
    M.files.push({kind:kind||guessKind(f.type||''),name:f.name,
      size:f.size?human(f.size):'',url:url});
  });
  repaintFiles();
}
function repaintFiles(){
  const box=$('#fChips'); if(!box) return;
  box.innerHTML=M.files.map(fileChip).join('');
  box.hidden=!M.files.length;
}
function addLink(){
  const el=$('#linUrl'), v=el?String(el.value||'').trim():'';
  if(!/^(https?:\/\/)?[^\s.]+\.[^\s]{2,}$/.test(v)){ toast('نشانی پیوند را کامل بنویس'); if(el&&el.focus) el.focus(); return }
  M.files.push({kind:'link',name:/^https?:\/\//.test(v)?v:('https://'+v),size:''});
  repaintFiles();
  if(el) el.value='';
  const r=$('#linRow'); if(r) r.hidden=true;
  toast('پیوند پیوست شد');
}
async function startVoice(){
  const note=$('#recNote');
  const can=!!(navigator.mediaDevices&&navigator.mediaDevices.getUserMedia&&window.MediaRecorder);
  if(!can){
    if(note) note.textContent='ضبط در این مرورگر نیست؛ فایل صدا را از دستگاه انتخاب کن.';
    const f=$('#fAudio'); if(f&&f.click) f.click(); return;
  }
  try{
    const stream=await navigator.mediaDevices.getUserMedia({audio:true});
    const rec=new MediaRecorder(stream), parts=[], t0=Date.now();
    const tick=setInterval(()=>{ if(note) note.textContent='در حال ضبط… '+faN(Math.round((Date.now()-t0)/1000))+' ثانیه' },1000);
    rec.ondataavailable=e=>parts.push(e.data);
    rec.onstop=()=>{
      clearInterval(tick); stream.getTracks().forEach(t=>t.stop());
      const sec=Math.max(1,Math.round((Date.now()-t0)/1000));
      let blob=null; try{ blob=new Blob(parts,{type:'audio/webm'}) }catch(e){}
      M.files.push({kind:'voice',name:'پیام صوتی '+faN(sec)+' ثانیه',size:blob?human(blob.size):''});
      repaintFiles();
      if(note) note.textContent='پیام صوتی پیوست شد؛ می‌توانی بفرستی.';
      toast('پیام صوتی آماده است');
    };
    rec.start();
    if(note) note.textContent='در حال ضبط… برای پایان، جای دیگری از صفحه را بزن.';
    const stop=e=>{ if(e.target.closest&&e.target.closest('[data-rec]')) return;
      document.removeEventListener('click',stop,true); try{ rec.stop() }catch(err){} };
    setTimeout(()=>document.addEventListener('click',stop,true),250);
  }catch(e){
    if(note) note.textContent='دسترسی به میکروفون داده نشد؛ فایل صدا را انتخاب کن.';
    const f=$('#fAudio'); if(f&&f.click) f.click();
  }
}

/* ── فرستادن تیکت و پاسخ کارشناس ────────────────────────────────── */
function sendTicket(){
  const s=secOf(M.sec); if(!s) return;
  const el=$('#tkText'), txt=el?String(el.value||'').trim():'';
  if(txt.length<10&&!M.files.length){
    toast('کمی بیشتر بنویس یا یک فایل بچسبان'); if(el&&el.focus) el.focus(); return;
  }
  const anon=M.cat==='بی‌نام'||s.k==='anon';
  const files=M.files.map(f=>({kind:f.kind,name:f.name,size:f.size}));
  const body=txt||'(بدون متن، فقط پیوست)';
  const tk={id:newCode(), sec:s.k, cat:anon?'بی‌نام':(M.cat||s.cat||'عمومی'), text:body,
    at:today(), status:'در صف بررسی', anon:anon, files:files,
    thread:[{who:'me',text:body,at:today(),files:files}]};
  const all=readTickets(); all.unshift(tk); writeTickets(all);
  M.files=[]; M.ticket=true;
  renderModal(s); revealComposer();
  renderTiles($('#supQ')?$('#supQ').value:''); renderMine();
  toast(anon?'تیکت بی‌نام ثبت شد · کد '+faN(tk.id):'تیکت ثبت شد · کد پیگیری '+faN(tk.id));
  replyLater(tk.id);
}
/* پاسخ نمونهٔ کارشناس، همان شکل پیام‌رسان */
function replyLater(id){
  setTimeout(()=>{
    const all=readTickets(), t=all.find(x=>x.id===id); if(!t) return;
    const s=secOf(t.sec)||{};
    const extra=s.form?' فرم مرتبط همین بخش را هم پر کنی، سریع‌تر می‌رسد.':'';
    t.status='پاسخ داده شد';
    t.thread.push({who:'agent',at:today(),
      text:'سلام، تیکتت رسید. «'+s.n+'» را از همین بخش می‌شود جلو برد.'+extra+' اگر جایی گیر کردی همین‌جا بنویس.',
      files:[{kind:'link',name:'lifeline1.ir/nora-ui/'+(s.k||'support')+'.html'}]});
    writeTickets(all); renderMine();
    if(M.sec===t.sec) renderModal(secOf(t.sec));
    toast('کارشناس پاسخ داد · کد '+faN(t.id));
  },1400);
}
function openTicket(id){
  const T=ticketOf(id); if(!T) return;
  const s=secOf(T.sec)||{k:T.sec,n:T.cat||'تیکت',s:'',faq:[],media:[],tips:[]};
  M.sec=s.k; M.ticket=false; M.files=[];
  $('#mIco').innerHTML=ico('i-headphone');
  $('#mTitle').textContent=s.n||'تیکت';
  $('#mSub').textContent='کد پیگیری '+faN(T.id)+' · '+T.status;
  $('#mBody').innerHTML=threadHTML(T);
  $('#modal').hidden=false; document.body.classList.add('modal-open');
  const sc=$('#scrim'); if(sc) sc.classList.add('on');
}

/* ── کمکی‌های رابط ──────────────────────────────────────────────── */
function toast(t){
  if(UI().toast) return UI().toast(t);
  const el=$('#toast'); if(!el) return;
  el.textContent=t; el.classList.add('on');
  clearTimeout(toast._t); toast._t=setTimeout(()=>el.classList.remove('on'),2600);
}
function openSheet(id){
  const el=document.getElementById(id); if(!el) return;
  el.classList.add('on');
  const sc=$('#scrim'); if(sc) sc.classList.add('on');
  document.body.classList.add('modal-open');
}
function closeSheets(){
  const wasOpen=$$('.sheet.on').length>0;
  $$('.sheet.on').forEach(s=>s.classList.remove('on'));
  try{ if(window.speechSynthesis) speechSynthesis.cancel() }catch(e){}
  PL.on=false;
  const m=$('#modal');
  if(m&&!m.hidden){ const sc=$('#scrim'); if(sc) sc.classList.add('on'); return }
  document.body.classList.remove('modal-open');
  const sc=$('#scrim'); if(sc) sc.classList.remove('on');
  if(wasOpen&&PL.back){ const s=secOf(PL.back); PL.back=null; if(s) renderModal(s) }
}

/* ── کنش‌ها ─────────────────────────────────────────────────────── */
document.addEventListener('click',e=>{
  const t=e.target;
  if(t.closest('[data-mclose]')){ closeModal(); return }
  if(t.closest('[data-close]')){ closeSheets(); return }
  if(t.closest('#scrim')){ if($$('.sheet.on').length) closeSheets(); else closeModal(); return }
  const sec=t.closest('[data-sec]');
  if(sec&&!t.closest('[data-tksend]')){
    openSec(sec.dataset.sec,{ticket:sec.hasAttribute('data-ticket'),attach:sec.dataset.attach||''});
    return;
  }
  const md=t.closest('[data-media]');
  if(md&&M.sec){ openMedia(secOf(M.sec),+md.dataset.media); return }
  if(t.closest('[data-ticket-open]')){ M.ticket=true; revealComposer(); return }
  const tc=t.closest('[data-tcat]');
  if(tc){ M.cat=tc.dataset.tcat;
    $$('#tkSlot [data-tcat]').forEach(b=>{ const on=b.dataset.tcat===M.cat;
      b.classList.toggle('on',on); b.setAttribute('aria-pressed',String(on)) });
    const anon=M.cat==='بی‌نام', ta=$('#tkText');
    if(ta) ta.placeholder=anon?'هر چه می‌خواهی بنویس؛ بی‌نام می‌ماند':'مشکل را کوتاه بنویس؛ اگر فایل یا صدا داری، همین‌جا بچسبان';
    return }
  if(t.closest('[data-tksend]')){ sendTicket(); return }
  if(t.closest('[data-linkopen]')){ const r=$('#linRow'); if(r){ r.hidden=false; const i=$('#linUrl'); if(i&&i.focus) i.focus() } return }
  if(t.closest('[data-linkadd]')){ addLink(); return }
  const pk=t.closest('[data-pick]');
  if(pk){ const id={image:'fImage',video:'fVideo',file:'fFile'}[pk.dataset.pick];
    const f=document.getElementById(id); if(f&&f.click) f.click(); return }
  if(t.closest('[data-rec]')){ startVoice(); return }
  const rm=t.closest('[data-frm]'); if(rm){ M.files.splice(+rm.dataset.frm,1); repaintFiles(); return }
  if(t.closest('#pToggle')){ togglePlay(); return }
  const tk=t.closest('[data-tk]'); if(tk){ openTicket(tk.dataset.tk); return }
  if(t.closest('#supQClear')){
    const q=$('#supQ');
    if(q){ q.value=''; renderTiles(''); renderQuery(''); const c=$('#supQClear'); if(c) c.hidden=true; q.focus() }
    return;
  }
});
document.addEventListener('input',e=>{
  if(e.target&&e.target.id==='supQ'){
    const v=String(e.target.value||'');
    renderTiles(v); renderQuery(v);
    const c=$('#supQClear'); if(c) c.hidden=!v.trim();
  }
});
document.addEventListener('change',e=>{
  const el=e.target; if(!el||!el.id||!el.files) return;
  if(el.id==='fImage') addFiles(el.files,'image');
  else if(el.id==='fVideo') addFiles(el.files,'video');
  else if(el.id==='fAudio') addFiles(el.files,'audio');
  else if(el.id==='fFile') addFiles(el.files);
  el.value='';
});
document.addEventListener('keydown',e=>{
  if(e.key!=='Escape') return;
  const m=$('#modal');
  if(m&&!m.hidden) closeModal(); else closeSheets();
});
window.addEventListener('hashchange',()=>{
  const raw=String(location.hash||'').replace('#','');
  if(!raw){ closeModal(); return }
  if(secOf(raw)) openSec(raw);
});

/* ── بوت ─────────────────────────────────────────────────────────── */
if(typeof initUI==='function') initUI();
seedTicket();
const hrs=$('#supHours'); if(hrs&&SUP.hours) hrs.textContent=SUP.hours;
const rp=$('#supReply'); if(rp&&SUP.reply) rp.textContent=SUP.reply;
renderTiles(''); renderExperts(); renderManagers(); renderForms(); renderMine(); renderFaqAll();
const raw=String(location.hash||'').replace('#',''); if(secOf(raw)) openSec(raw);
})();
