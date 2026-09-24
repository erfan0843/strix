/* ══════════════════════════════════════════════════════════════════════════
   نورا — پشتیبانی و راهنما
   ──────────────────────────────────────────────────────────────────────────
   یک صفحه، سه کار: راهنما پیدا کن، با کارشناس حرف بزن، تیکت بگذار.
   هر بخش ربات یک کاشی است؛ کاشی که بزنی پاپ‌آپی باز می‌شود با پرسش‌های همان
   بخش، راهنمای مدیر سامانه، راهنمای تصویری و صوتی، فرم لینک‌شدهٔ مدیر و
   آخرش «ثبت تیکت از همین بخش». تیکت و پاسخ کارشناس، هر دو، پیوست می‌گیرند:
   صدا، تصویر، ویدیو، فایل و پیوند. بی‌ورود هم کار می‌کند.

   کلید حافظهٔ تیکت‌ها: nora-support-tickets
   ══════════════════════════════════════════════════════════════════════════ */
(function(){
'use strict';

/* ── داده و کمکی‌ها ────────────────────────────────────────────────────── */
const N=window.NORA||{}, SUP=N.SUPPORT||{}, AC=N.ACCOUNT||{}, POL=AC.policy||{};
const SECT=(SUP.sections||[]).slice();
const GRS=(SUP.grps||[]).slice();
const TONES=SUP.tones||{};
const CATS=POL.ticketCats||[];
const MAXOPEN=Number(POL.ticketMaxOpen)||3;
const $=s=>document.querySelector(s), $$=s=>Array.from(document.querySelectorAll(s));
const esc=t=>String(t==null?'':t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const faN=n=>String(n==null?'':n).replace(/[0-9]/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
const ico=(i,cl)=>'<svg class="i'+(cl?' '+cl:'')+'" aria-hidden="true"><use href="#'+i+'"/></svg>';
const toast=m=>{const u=window.NORA_UI; if(u&&u.toast) u.toast(m);};
const toneOf=s=>(s&&TONES[s.grp])||'plain';
const secOf=k=>SECT.find(x=>x.k===k)||null;
const KIND={image:{i:'i-image',n:'تصویر'},video:{i:'i-video',n:'ویدیو'},voice:{i:'i-mic',n:'پیام صوتی'},
  audio:{i:'i-wave',n:'صدا'},link:{i:'i-link',n:'پیوند'},file:{i:'i-file-up',n:'فایل'}};
const MESS={bale:'ble.ir/',tel:'t.me/',soroush:'splus.ir/',gap:'gap.im/'};
/* شکل نوار صدا: از خودِ نام ساخته می‌شود، پس همیشه یک‌شکل و بی‌تصادف می‌ماند */
function bars(seed,n){
  let out='',k=0; const src=String(seed||'نورا');
  for(let i=0;i<src.length;i++) k=(k*31+src.charCodeAt(i))%9973;
  for(let i=0;i<(n||20);i++){ k=(k*1103515245+12345)%2147483647;
    out+='<i style="height:'+(20+(Math.abs(k)%66))+'%"></i>'; }
  return out;
}

const TK_KEY='nora-support-tickets', SEED_KEY='nora-support-seeded';

function today(){
  try{ return new Intl.DateTimeFormat('fa-IR-u-ca-persian',{day:'numeric',month:'long'}).format(new Date()) }
  catch(e){ return 'امروز' }
}
function stamp(t){
  try{ return new Intl.DateTimeFormat('fa-IR-u-ca-persian',{day:'numeric',month:'long',hour:'2-digit',minute:'2-digit'}).format(new Date(t||Date.now())) }
  catch(e){ return today() }
}
function kb(n){
  if(!n) return '';
  return n>1048576 ? faN((n/1048576).toFixed(1))+' مگابایت' : faN(Math.max(1,Math.round(n/1024)))+' کیلوبایت';
}

/* ── تیکت‌ها: خواندن، نوشتن، کد پیگیری ────────────────────────────────── */
function readT(){
  let v=[]; try{ v=JSON.parse(localStorage.getItem(TK_KEY)||'[]') }catch(e){ v=[] }
  return Array.isArray(v)?v:[];
}
function writeT(v){ try{ localStorage.setItem(TK_KEY,JSON.stringify(v.slice(0,14))) }catch(e){} }
function newCode(){ let c=''; for(let i=0;i<5;i++) c+=String(Math.floor(Math.random()*10)); return c }
const ticketOf=id=>readT().find(t=>t.id===id)||null;
const secTickets=k=>readT().filter(t=>t.sec===k);
const openCount=()=>readT().filter(t=>!t.closed).length;
function stateOf(t){
  if(t.closed) return 'closed';
  const last=t.thread&&t.thread[t.thread.length-1];
  return last&&last.who==='agent' ? 'answered' : 'open';
}
const STATE={open:{n:'در انتظار پاسخ',c:''},answered:{n:'پاسخ داده شد',c:'ok'},closed:{n:'بسته‌شده',c:''}};
const lastOf=(t,k)=>{const a=[].concat(t.thread||[]).reverse().find(m=>m.who===k); return a?esc(a.text||'').slice(0,110):''};

/* تیکت نمونه، یک‌بار؛ تا کادر تیکت‌های من خالی نماند و شکل پاسخ دیده شود */
function seed(){
  let done=false; try{ done=localStorage.getItem(SEED_KEY)==='1' }catch(e){}
  if(done||readT().length) return;
  const files=[{kind:'image',t:'برگ-گواهی.jpg',size:245760}];
  const when=Date.now()-86400000*2;
  writeT([{id:'seed1', code:'20451', sec:'cert', cat:'گواهی', anon:false, name:'سارا محمدی',
    contact:'۰۹۱۲۳۴۵۶۷۸۹', at:when,
    thread:[{who:'me', at:when, text:'گواهی کارگاه عکاسی را چه وقت می‌شود دانلود کرد؟', atts:files},
      {who:'agent', at:when+5400000, by:'مریم داوودی',
       text:'سلام. گواهی بعد از تأیید سرپرست صادر می‌شود و همان روز در «حساب من»، تب بلیت و گواهی می‌آید. سریال که گرفتی، از صفحهٔ استعلام هم می‌توانی بررسی کنی.',
       atts:[{kind:'link',t:'صفحهٔ استعلام گواهی',href:'account.html#cert'}]}]}]);
  try{ localStorage.setItem(SEED_KEY,'1') }catch(e){}
}

/* ── پیش‌نویس پیوست‌ها ─────────────────────────────────────────────────── */
function draft(s){ return {sec:s, atts:[], rec:null, timer:0, t0:0} }

function pinHTML(a,i){
  const k=KIND[a.kind]||KIND.file;
  return '<span class="pin">'+ico(k.i)+'<span>'+esc(a.t||k.n)+'</span>'+
    (a.size?'<span class="fine">'+kb(a.size)+'</span>':'')+
    '<button type="button" data-unpin="'+i+'" aria-label="برداشتن پیوست">'+ico('i-close')+'</button></span>';
}
function paintPins(host,d){
  const box=host.querySelector('[data-pins]'); if(!box) return;
  box.innerHTML=d.atts.map(pinHTML).join('');
}

/* سینی پیوست: تصویر، ویدیو، ویس، پیوند و فایل — هم برای تیکت، هم برای پاسخ */
function tray(host,d){
  host.innerHTML='<div data-tw>'+
    '<div class="chipsline">'+
      '<button class="abtn" type="button" data-att="image">'+ico('i-image')+' تصویر</button>'+
      '<button class="abtn" type="button" data-att="video">'+ico('i-video')+' ویدیو</button>'+
      '<button class="abtn" type="button" data-att="file">'+ico('i-file-up')+' فایل</button>'+
      '<button class="abtn rec" type="button" data-att="voice" aria-pressed="false">'+ico('i-mic')+
        '<span data-rtx>ویس</span><span class="pbar" aria-hidden="true"><i></i></span></button>'+
      '<button class="abtn" type="button" data-att="link">'+ico('i-link')+' پیوند</button>'+
    '</div>'+
    '<div class="pbox" data-lbox hidden>'+
      '<label>نشانی پیوند<input type="url" data-lurl inputmode="url" placeholder="https://" dir="ltr"/></label>'+
      '<div class="tbtop" style="margin-top:8px"><span class="fine">با «افزودن» به پیوست‌ها می‌چسبد.</span>'+
      '<span class="sp"></span><button class="btn sm" type="button" data-ladd>افزودن</button></div>'+
    '</div>'+
    '<input type="file" data-finput hidden/>'+
    '<div class="linrow" data-pins></div>'+
    '<p class="fine">حجم هر پیوست تا ۲۵ مگابایت؛ صدا، تصویر و ویدیو را همین‌جا بگیری هم می‌شود.</p>'+
  '</div>';
  const root=host.querySelector('[data-tw]');
  const fin=root.querySelector('[data-finput]');
  const ACC={image:'image/*',video:'video/*',file:'.pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.zip,image/*,application/pdf'};

  function add(a){
    if(d.atts.length>=6){ toast('هر پیام تا شش پیوست'); return }
    d.atts.push(a); paintPins(root,d);
  }
  root.addEventListener('click',e=>{
    const b=e.target.closest('[data-att]'); if(b){
      const k=b.dataset.att;
      if(k==='link'){ const lb=root.querySelector('[data-lbox]'); lb.hidden=!lb.hidden;
        if(!lb.hidden){ const u=lb.querySelector('[data-lurl]'); u.focus(); } return }
      if(k==='voice'){ rec(); return }
      fin.setAttribute('accept',ACC[k]||'*/*'); fin.dataset.kind=k; fin.value=''; fin.click(); return;
    }
    const la=e.target.closest('[data-ladd]');
    if(la){
      const u=root.querySelector('[data-lurl]'); const v=(u.value||'').trim();
      if(!/^https?:\/\/\S+/i.test(v)){ u.focus(); u.classList.add('flash'); setTimeout(()=>u.classList.remove('flash'),600);
        toast('نشانی را با http بنویس'); return }
      add({kind:'link',t:v.replace(/^https?:\/\//,'').slice(0,60),href:v}); u.value='';
      const lb=root.querySelector('[data-lbox]'); if(lb) lb.hidden=true; return;
    }
    const un=e.target.closest('[data-unpin]');
    if(un){ d.atts.splice(Number(un.dataset.unpin),1); paintPins(root,d); return }
  });
  fin.addEventListener('change',()=>{
    const k=fin.dataset.kind||'file';
    Array.from(fin.files||[]).slice(0,3).forEach(f=>{
      const kind=/^video\//.test(f.type)?'video':/^audio\//.test(f.type)?'voice':/^image\//.test(f.type)?'image':k;
      add({kind, t:f.name, size:f.size});
    });
  });

  /* ضبط صدا: اگر مرورگر اجازه بدهد واقعی، وگرنه همان‌جا شبیه‌سازی می‌شود */
  function rec(){
    const btn=root.querySelector('[data-att="voice"]');
    if(!btn) return;
    const tx=btn.querySelector('[data-rtx]');
    const bar=btn.querySelector('.pbar i');
    if(d.recOn){ stopRec(); return }
    d.t0=Date.now(); d.recOn=true; d.timer=0;
    btn.classList.add('on'); btn.setAttribute('aria-pressed','true'); tx.textContent='بایست';
    d.timer=setInterval(()=>{
      const sec=Math.min(60,(Date.now()-d.t0)/1000);
      bar.style.width=(sec/60*100)+'%';
      if(sec>=60) stopRec();
    },120);
    /* صدای واقعی اگر مرورگر بدهد؛ بی آن هم ضبط نمونه کار می‌کند */
    try{
      if(navigator.mediaDevices&&window.MediaRecorder){
        navigator.mediaDevices.getUserMedia({audio:true}).then(st=>{
          if(!d.recOn){ st.getTracks().forEach(t=>t.stop()); return }
          d.rec=new MediaRecorder(st); d.rec.start();
        }).catch(()=>{});
      }
    }catch(e){}
  }
  function stopRec(keep){
    if(!d.recOn) return;
    clearInterval(d.timer); d.timer=0;
    const secs=Math.max(1,Math.round((Date.now()-d.t0)/1000));
    if(d.rec){ try{ d.rec.stop() }catch(e){}
      try{ d.rec.stream.getTracks().forEach(t=>t.stop()) }catch(e){} }
    d.rec=null; d.recOn=false;
    const btn=root.querySelector('[data-att="voice"]');
    if(btn){ btn.classList.remove('on'); btn.setAttribute('aria-pressed','false');
      const tx=btn.querySelector('[data-rtx]'); if(tx) tx.textContent='ویس';
      const bar=btn.querySelector('.pbar i'); if(bar) bar.style.width='0'; }
    if(keep!==false) add({kind:'voice',t:'پیام صوتی',len:faN(secs)+' ثانیه'});
  }
  /* ضبط را از بیرون هم می‌شود بست (مثلاً وقت فرستادن پیام) */
  paintPins(root,d);
  d.stopRec=()=>stopRec(false);
  return {stopRec:d.stopRec};
}

/* ── سرِ صفحه، کارشناس‌ها، صافی و کاشی‌ها ─────────────────────────────── */
function renderHead(){
  const on=(SUP.experts||[]).filter(e=>e.on).length;
  const lv=$('#supLive'); if(lv) lv.textContent=on?'آنلاین':'خارج از ساعت';
  const l=SUP.lead||{};
  const av=$('#leadAv'); if(av) av.textContent=(l.n||'ن').trim().charAt(0);
  const ln=$('#leadName'); if(ln) ln.textContent=l.n||'کارشناس پشتیبانی';
  const lr=$('#leadRole'); if(lr) lr.textContent=l.r||(SUP.n||'');
  const fc=$('#faqCount');
  if(fc) fc.textContent=faN(SECT.reduce((a,s)=>a+s.faq.length,0))+' پرسش پرتکرار و راهنمای هر بخش';
}
function renderExperts(){
  const box=$('#exList'); if(!box) return;
  const L=SUP.lead||{}, rows = L.n ? [L].concat(SUP.experts||[]) : (SUP.experts||[]);
  box.innerHTML=rows.map(e=>{
    const ms=(e.m||[]).map(m=>{
      const pre=MESS[m.k]||'';
      return '<a class="mchip" href="https://'+esc(pre+m.h)+'" target="_blank" rel="noopener">'+ico('i-link')+esc(m.k)+'</a>';
    }).join('');
    return '<div class="ecard anim">'+
      '<span class="eav">'+esc((e.n||'ن').trim().charAt(0))+'</span>'+
      '<b>'+esc(e.n||'')+'</b><small>'+esc(e.r||'')+'</small>'+
      '<span class="tag '+(e.on?'ok':'')+' xs">'+(e.on?'آنلاین':'بعداً')+'</span>'+
      (ms?'<div class="mlinks" style="justify-content:center">'+ms+'</div>':'')+
    '</div>';
  }).join('');
  const c=$('#exCount'); if(c) c.textContent=faN(rows.filter(e=>e.on).length)+' نفر آنلاین';
}
function renderGroups(){
  const box=$('#grpChips'); if(!box) return;
  box.innerHTML=GRS.map(g=>{
    const n=g.k==='all'?SECT.length:SECT.filter(s=>s.grp===g.k).length;
    return '<button class="fchip'+(state.grp===g.k?' sel':'')+'" type="button" data-grp="'+g.k+'">'+
      esc(g.n)+' <span class="fine">'+faN(n)+'</span></button>';
  }).join('');
}
function hits(s){
  const q=state.q.trim();
  if(!q) return true;
  const hay=[s.n,s.s,s.cat||'',...(s.faq||[]).map(f=>f[0]+' '+f[1]),...(s.tips||[]),
    ...(s.media||[]).map(m=>m.t),s.form?s.form.t:''].join(' ');
  return hay.toLowerCase().indexOf(q.toLowerCase())>-1;
}
function tileHTML(s,i){
  const T=secTickets(s.k), last=T[T.length-1];
  const st=last?stateOf(last):'';
  const bars=last?'<span class="sbars"><span class="sbar'+(st==='answered'?' on':'')+'"><i></i></span>'+
      '<span class="smic">'+ico(st==='answered'?'i-check':'i-clock')+' '+
      (st==='answered'?'پاسخ آمد':st==='closed'?'بسته شد':'در انتظار')+' · '+faN(T.length)+'</span></span>':'';
  return '<button class="stile anim" type="button" style="--i:'+i+'" data-sec="'+s.k+'">'+
    '<span class="iw '+toneOf(s)+'">'+ico(s.i||'i-q')+'</span>'+
    '<span><b>'+esc(s.n)+'</b><span class="sb">'+esc(s.s||'')+'</span>'+bars+'</span></button>';
}
function renderTiles(){
  const box=$('#stiles'); if(!box) return;
  const list=SECT.filter(s=>state.grp==='all'||s.grp===state.grp).filter(hits);
  box.innerHTML=list.map(tileHTML).join('');
  const em=$('#tilesEmpty'); if(em) em.hidden=list.length>0;
  const c=$('#tilesCount'); if(c) c.textContent=faN(list.length)+' موضوع';
  const t=$('#tilesTitle');
  if(t){ const g=GRS.find(x=>x.k===state.grp); t.textContent=(g&&g.k!=='all')?g.n:'موضوع‌ها'; }
}
/* نشانه‌گذاری واژهٔ جست‌وجو، پس از پاک‌سازی، تا تگ داخل متن نشکند */
function hl(txt){
  const q=state.q.trim();
  const s=esc(txt);
  if(q.length<2) return s;
  const re=new RegExp('('+q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')','gi');
  return s.replace(re,'<span class="hitmark">$1</span>');
}
function faqRow(s,i,open){
  const qa=s.faq[i]||['',''];
  return '<div class="qrow'+(open?' open':'')+'" data-qrow="'+s.k+':'+i+'">'+
    '<button class="qbtn" type="button" data-faq="'+s.k+':'+i+'" aria-expanded="'+(open?'true':'false')+'">'+
      '<span class="iw '+toneOf(s)+'" style="width:36px;height:36px;border-radius:13px">'+ico(s.i||'i-q')+'</span>'+
      '<span><b>'+hl(qa[0])+'</b><small>'+esc(s.n)+(s.cat?' · '+esc(s.cat):'')+'</small></span>'+
      '<svg class="i go" aria-hidden="true"><use href="#i-chev-left"/></svg>'+
    '</button>'+
    '<div class="qans">'+hl(qa[1])+
      '<div class="acl"><button class="abtn" type="button" data-ticket="'+s.k+'">'+ico('i-pen')+' تیکت از همین بخش</button>'+
      ((s.media||[]).length?'<button class="abtn" type="button" data-media="'+s.k+':0">'+ico('i-play-f')+' راهنمای تصویری</button>':'')+
      '</div></div></div>';
}
function renderFaq(){
  const box=$('#faqAll'); if(!box) return;
  const q=state.q.trim();
  let out='', n=0;
  SECT.forEach(s=>{
    (s.faq||[]).forEach((qa,i)=>{
      if(q.length>1){
        const hay=(qa[0]+' '+qa[1]).toLowerCase();
        if(hay.indexOf(q.toLowerCase())<0) return;
      }
      out+=faqRow(s,i,false); n++;
    });
  });
  box.innerHTML=out;
  const qc=$('#qres'), ql=$('#qlist');
  if(qc&&ql){
    const on=q.length>1;
    qc.hidden=!on;
    if(on){
      const rows=[];
      SECT.forEach(s=>(s.faq||[]).forEach((qa,i)=>{
        if((qa[0]+' '+qa[1]).toLowerCase().indexOf(q.toLowerCase())>-1) rows.push({s,i});
      }));
      ql.innerHTML=rows.length?rows.slice(0,8).map(r=>faqRow(r.s,r.i,false)).join('')
        :'<div class="sp-card"><b>پاسخی برای «'+esc(q)+'» پیدا نشد.</b>'+
          '<p class="cap" style="margin-top:6px">تیکت بگذار؛ کارشناس همان بخش جواب می‌دهد.</p>'+
          '<button class="btn primary block" type="button" data-ticket="'+SECT[0].k+'" style="margin-top:10px">'+ico('i-pen')+' ثبت تیکت</button></div>';
    }
  }
}
function renderSla(){
  const box=$('#slaRows'); if(!box) return;
  box.innerHTML=(SUP.sla||[]).map(r=>'<div class="adrow"><b>'+esc(r[0])+'</b><span class="bd">'+esc(r[1])+'</span></div>').join('');
  const nv=$('#neverText');
  if(nv) nv.innerHTML=ico('i-lock')+' '+esc(SUP.neverText||'');
}
function renderMine(){
  const box=$('#mine'), list=$('#tkList'), c=$('#tkCount'); if(!box||!list) return;
  const T=readT().slice().sort((a,b)=>(b.at||0)-(a.at||0));
  box.hidden=T.length===0;
  if(c) c.textContent=faN(T.length)+' تیکت';
  list.innerHTML=T.map(t=>{
    const s=secOf(t.sec)||{n:'پشتیبانی',i:'i-q'};
    const st=stateOf(t), S2=STATE[st];
    return '<button class="tkrow" type="button" data-thread="'+t.id+'">'+
      '<span class="tki">'+ico(s.i)+'</span>'+
      '<span class="tktx"><b>'+esc(s.n)+'</b>'+
        '<span class="s">'+(lastOf(t,'me')||'—')+'</span>'+
        '<span class="tkmeta"><span class="tag '+(S2.c||'')+' xs">'+S2.n+'</span>'+
          '<span class="bd">کد '+faN(t.code)+'</span><span class="fine">'+stamp(t.at)+'</span></span></span></button>';
  }).join('');
}
function renderLatest(){
  const box=$('#latest'); if(!box) return;
  const t=readT().filter(x=>stateOf(x)==='answered').sort((a,b)=>(b.at||0)-(a.at||0))[0];
  box.hidden=!t;
  if(!t){ box.innerHTML=''; return }
  const last=[].concat(t.thread).reverse().find(m=>m.who==='agent')||{};
  const s=secOf(t.sec)||{n:'پشتیبانی'};
  box.innerHTML='<div class="bubble"><span class="who">'+ico('i-send')+' تازه‌ترین پاسخ · '+esc(s.n)+'</span>'+
    '<p>'+esc((last.text||'').slice(0,190))+((last.text||'').length>190?'…':'')+'</p>'+
    '<div class="tkmeta" style="margin-top:8px"><button class="abtn" type="button" data-thread="'+t.id+'">'+
    ico('i-eye')+' دیدن گفت‌وگو</button><span class="fine">'+(last.by?esc(last.by)+' · ':'')+stamp(last.at)+'</span></div></div>';
}
function renderAll(){
  renderHead(); renderExperts(); renderGroups(); renderTiles(); renderFaq();
  renderSla(); renderMine(); renderLatest(); paintBell();
}
function paintBell(){
  try{ const u=window.NORA_UI; if(u&&u.syncBell) u.syncBell() }catch(e){}
  const n=openCount();
  const b=document.querySelector('.help-btn');
  if(b) b.setAttribute('title',n?'پشتیبانی · '+faN(n)+' تیکت باز':'پشتیبانی و راهنما');
}

/* ── پاپ‌آپ ────────────────────────────────────────────────────────────── */
function modal(v){
  const m=$('#modal'); if(!m) return;
  const mi=$('#mIco'), mt=$('#mTitle'), ms=$('#mSub'), mb=$('#mBody'), mf=$('#mFoot');
  mi.className='mico';
  mi.innerHTML='<span class="iw '+esc(v.tone||'brand')+'" style="width:44px;height:44px;border-radius:16px">'+
    ico(v.ico||'i-headphone')+'</span>';
  mt.textContent=v.title||'';
  ms.textContent=v.sub||'';
  mb.innerHTML=v.body||'';
  mf.innerHTML=v.foot||'';
  if(!m.hidden) { mb.scrollTop=0; return }
  m.hidden=false; document.body.classList.add('modal-open');
  try{ m.querySelector('.mdlg').focus({preventScroll:true}) }catch(e){}
  mb.scrollTop=0;
}
function closeModal(){
  const m=$('#modal'); if(!m||m.hidden) return;
  m.hidden=true; document.body.classList.remove('modal-open'); $('#mBody').innerHTML='';
  state.thread='';
}
function closeSheets(){
  $$('.sheet').forEach(s=>{s.classList.remove('on'); s.setAttribute('aria-modal','false')});
  const sc=$('#scrim'); if(sc) sc.classList.remove('on');
}
function sheetOpen(id){
  const el=$('#'+id); if(!el) return;
  closeModal(); closeSheets();
  el.classList.add('on'); el.setAttribute('aria-modal','true');
  const sc=$('#scrim'); if(sc) sc.classList.add('on');
  el.querySelector('.sbody').scrollTop=0;
}

/* ── دیدِ بخش: پرسش‌ها، راهنمای مدیر، رسانه، فرم، تیکت ────────────────── */
function mediaCard(s,m,i){
  const k=KIND[m.kind]||KIND.video;
  if(m.kind==='audio'||m.kind==='voice'){
    return '<div class="mcard"><div class="mcbody"><b>'+esc(m.t)+'</b>'+
      '<div class="psim"><button class="play" type="button" data-media="'+s.k+':'+i+'" aria-label="پخش نمونه">'+ico('i-play-f')+'</button>'+
      '<span class="pbsim" aria-hidden="true">'+bars(m.t,22)+'</span>'+
      '<span class="dur">'+esc(m.len||'۰:۳۰')+'</span></div>'+
      '<span class="fine">راهنمای شنیدنی · '+esc(k.n)+'</span></div></div>';
  }
  return '<div class="mcard"><div class="mthumb"><span class="mock">'+
    '<span class="mico-sm">'+ico(k.i)+'</span><b>'+(m.kind==='image'?'تصویر گام‌به‌گام':k.n)+'</b>'+
    '<small>'+(m.len?esc(m.len)+' · ':'')+'پیش‌نمایش راهنما</small></span>'+
    '<button class="mplay" type="button" data-media="'+s.k+':'+i+'" aria-label="نمایش راهنما">'+ico('i-play-f')+'</button></div>'+
    '<div class="mcbody"><b>'+esc(m.t)+'</b><span class="fine">'+k.n+(m.len?' · '+esc(m.len):'')+'، از راهنمای همین بخش</span></div></div>';
}
function secBody(s){
  const parts=[];
  parts.push('<div class="mpart"><div class="hd">'+ico('i-q')+' پرسش‌های پرتکرار «'+esc(s.n)+'»</div>'+
    '<div class="pbd">'+(s.faq||[]).map((_,i)=>faqRow(s,i,i===0)).join('')+'</div></div>');
  if((s.tips||[]).length){
    parts.push('<div class="mpart"><div class="hd">'+ico('i-shield')+' راهنمای مدیر سامانه</div><div class="pbd">'+
      s.tips.map(t=>'<div class="tipit"><span class="iw '+toneOf(s)+'" style="width:34px;height:34px;border-radius:12px">'+
        ico('i-check')+'</span><span>'+esc(t)+'</span></div>').join('')+
      '<p class="fine">این نکته‌ها را خودِ مدیر همین بخش نوشته و با هر تغییر سامانه به‌روز می‌شود.</p></div></div>');
  }
  if((s.media||[]).length){
    parts.push('<div class="mpart"><div class="hd">'+ico('i-play-f')+' راهنمای تصویری، صوتی و ویدیویی</div>'+
      '<div class="pbd"><div class="mcards">'+(s.media||[]).map((m,i)=>mediaCard(s,m,i)).join('')+'</div></div></div>');
  }
  if(s.form){
    parts.push('<a class="mlink" href="'+esc(s.form.href)+'"><span class="iw '+toneOf(s)+'">'+ico('i-doc')+'</span>'+
      '<span style="flex:1"><b>'+esc(s.form.t)+'</b><small>فرم لینک‌شدهٔ مدیر سامانه</small></span>'+
      '<svg class="i go" aria-hidden="true" style="width:17px;height:17px;color:var(--ink-4)"><use href="#i-chev-left"/></svg></a>');
  }
  parts.push('<p class="fine">'+ico('i-lock')+' تیکت بی‌ورود هم ثبت می‌شود؛ کد پیگیری همان لحظه ساخته می‌شود.</p>');
  return parts.join('');
}
function openSec(k,fi){
  const s=secOf(k); if(!s) return;
  state.open=k;
  modal({ico:s.i, tone:toneOf(s), title:s.n, sub:s.s||'',
    body:secBody(s),
    foot:'<button class="btn primary block" type="button" data-ticket="'+s.k+'">'+ico('i-pen')+' ثبت تیکت از همین بخش</button>'});
  if(fi!=null){ const row=$('[data-qrow="'+s.k+':0"]'); if(row) row.classList.add('open'); }
}

/* ── گفت‌وگو ──────────────────────────────────────────────────────────── */
function fxHTML(a){
  const k=KIND[a.kind]||KIND.file;
  if(a.kind==='audio'||a.kind==='voice'){
    return '<div class="fx">'+ico('i-wave')+'<span class="pbsim" aria-hidden="true">'+bars(a.t||a.len,18)+'</span>'+
      '<span class="fine">'+esc(a.len||a.t||k.n)+'</span></div>';
  }
  if(a.kind==='link'){
    return '<a class="fx" href="'+esc(a.href||'#')+'">'+ico('i-link')+'<b dir="ltr">'+esc(a.t||a.href||'پیوند')+'</b></a>';
  }
  return '<div class="fx">'+ico(k.i)+'<b>'+esc(a.t||k.n)+'</b>'+(a.size?'<span class="fine">'+kb(a.size)+'</span>':'')+'</div>';
}
function bubbleHTML(m){
  const mine=m.who==='me';
  return '<div class="frow'+(mine?' me':'')+'"><div class="fbubble">'+
    (mine?'':'<span class="fwho">'+esc(m.by||(SUP.experts&&SUP.experts[0]&&SUP.experts[0].n)||'کارشناس پشتیبانی')+'</span>')+
    esc(m.text||'').replace(/\n/g,'<br/>')+
    (m.atts||[]).map(fxHTML).join('')+
    '<span class="fmeta">'+stamp(m.at)+(m.anon?' · بی‌نام':'')+'</span></div></div>';
}
function threadBody(t){
  const s=secOf(t.sec)||{n:'پشتیبانی'};
  const st=stateOf(t), S2=STATE[st];
  return '<div class="tkt-acc'+(st==='answered'?' on':'')+'"><span class="tktx"><b>'+esc(s.n)+'</b>'+
      '<span class="s">'+S2.n+(t.cat?' · '+esc(t.cat):'')+'</span></span>'+
      '<span class="bd">کد '+faN(t.code)+'</span><span class="pb" aria-hidden="true"><i style="width:'+
      (st==='answered'?'100%':st==='closed'?'100%':'45%')+'"></i></span></div>'+
    '<div class="thread" data-thread-box>'+t.thread.map(bubbleHTML).join('')+'</div>'+
    (st==='closed'?'<p class="fine">این تیکت بسته شده. اگر ادامه دارد، تیکت تازه بزن.</p>':
      '<div data-ctray></div>'+
      '<div class="cinput"><button class="abtn" type="button" data-catt aria-label="پیوست">'+ico('i-clip')+'</button>'+
      '<input id="supReply" type="text" placeholder="پاسخ یا فایل تازه…" aria-label="متن پیام"/>'+
      '<button class="btn primary" type="button" data-csend>'+ico('i-send')+'</button></div>'+
      '<p class="fine" data-cfine>'+ico('i-clock')+' '+esc(SUP.reply||'پاسخ کارشناس تا پایان روز کاری')+'</p>');
}
function openThread(id){
  const t=ticketOf(id); if(!t) return;
  const s=secOf(t.sec)||{};
  modal({ico:s.i||'i-headphone', tone:toneOf(s), title:'گفت‌وگوی تیکت', sub:s.n+' · کد '+faN(t.code),
    body:threadBody(t),
    foot:'<div class="btn-row"><button class="btn quiet" type="button" data-mclose>بستن</button>'+
      (stateOf(t)==='closed'?'':'<button class="btn block" type="button" data-closetk="'+t.id+'">'+ico('i-check')+' پایان تیکت</button>')+'</div>'});
  state.open=t.sec; state.thread=id;
  const box=$('[data-thread-box]'), mb=$('#mBody');
  try{ if(mb) mb.scrollTop=mb.scrollHeight; else if(box&&box.scrollIntoView) box.scrollIntoView({block:'end'}); }catch(e){}
}
function msgToThread(id, m){
  const all=readT(); const t=all.find(x=>x.id===id); if(!t) return;
  t.thread=t.thread||[]; t.thread.push(m); t.at=Date.now(); writeT(all);
}
function sendReply(){
  const id=state.thread, inp=$('#supReply'); if(!id||!inp) return;
  const v=(inp.value||'').trim();
  const d=state.draft2;
  if(!v&&!(d&&d.atts.length)){ inp.focus(); return }
  if(d&&d.stopRec) d.stopRec();
  const ats=d?d.atts.slice():[];
  msgToThread(id,{who:'me',at:Date.now(),text:v,atts:ats});
  if(d){ d.atts.length=0; }
  inp.value=''; openThread(id); renderAll();
  toast('پیامت رفت؛ پاسخ کارشناس همین‌جا می‌آید');
  const t=ticketOf(id);
  if(t&&stateOf(t)==='open') setTimeout(()=>agentReply(id),1400);
}
function agentReply(id){
  const t=ticketOf(id); if(!t||t.closed) return;
  const s=secOf(t.sec)||{n:'پشتیبانی'};
  const ex=(SUP.experts||[]).filter(e=>e.on)[0]||(SUP.experts||[])[0]||{n:'کارشناس پشتیبانی'};
  const atts=[{kind:'link',t:'همین تیکت در حساب من',href:'support.html#mine'}];
  if(s.form) atts.push({kind:'link',t:s.form.t,href:s.form.href});
  msgToThread(id,{who:'agent',by:ex.n,at:Date.now(),atts:atts,
    text:'سلام، پیامت رسید. تیکت «'+(s.n||'پشتیبانی')+'» را دیدم و بررسی می‌کنم؛ نتیجه را همین‌جا می‌نویسم. اگر تصویر یا فایلی تازه داری، همین‌جا پیوست کن.'});
  renderAll();
  if(state.thread===id) openThread(id);
  toast('پاسخ کارشناس آمد');
}

/* ── فرم تیکت ─────────────────────────────────────────────────────────── */
function ticketForm(s){
  const anon=s.k==='anon';
  const cat=(CATS.indexOf(s.cat)>-1?s.cat:(CATS[0]||'پشتیبانی'));
  return '<div class="tkt">'+
    (anon?'<p class="fine">'+ico('i-eye')+' نام و شماره‌ات ثبت نمی‌شود؛ کد پیگیری فقط برای خودت است.</p>':
      '<label>نام و نشان<input id="fName" type="text" autocomplete="name" placeholder="مثلاً سارا محمدی"/></label>'+
      '<label>راه تماس (اختیاری)<input id="fContact" type="text" inputmode="tel" autocomplete="tel" placeholder="۰۹۱۲۳۴۵۶۷۸۹ یا رایانامه"/></label>')+
    '<label>موضوع<select id="fCat">'+CATS.map(c=>'<option'+(c===cat?' selected':'')+'>'+esc(c)+'</option>').join('')+'</select></label>'+
    '<label>متن پیام<textarea id="fBody" placeholder="چه شد، کِی شد و چه انتظاری داری؟"></textarea></label>'+
    '<div><span class="fine">پیوست‌ها</span><div data-tray></div></div>'+
    '<div class="tbtop"><span class="fine">'+ico('i-shield')+' بدون ورود هم می‌شود؛ با ورود، پاسخ در «حساب من» می‌ماند.</span></div>'+
  '</div>';
}
function openTicket(k){
  const s=secOf(k)||SECT[0]; if(!s) return;
  const anon=s.k==='anon';
  if(openCount()>=MAXOPEN){
    modal({ico:'i-clock', tone:toneOf(s), title:'تیکت‌های بازت زیاد است', sub:'تا '+faN(MAXOPEN)+' تیکت باز می‌شود',
      body:'<p class="cap" style="text-align:start">'+faN(openCount())+' تیکت باز داری. یکی را ببند یا پاسخ همان‌ها را ادامه بده، بعد تیکت تازه بزن.</p>',
      foot:'<button class="btn primary block" type="button" data-mclose>باشه</button>'});
    return;
  }
  state.open=s.k;
  const T=secTickets(s.k);
  const old=T.length?'<p class="fine">'+ico('i-archive')+' از این بخش '+faN(T.length)+' تیکت داری؛ '+
    'همان‌ها را در «تیکت‌های من» می‌بینی.</p>':'';
  modal({ico:s.i, tone:toneOf(s), title:(anon?'پیام بی‌نام':'تیکت تازه')+' · '+s.n,
    sub:anon?'بی‌رد و بی‌نام؛ کد پیگیری برای خودت است':'پیوست صدا، تصویر، ویدیو، فایل و پیوند هم می‌شود',
    body:ticketForm(s)+old,
    foot:'<button class="btn primary block" type="button" data-sendticket="'+s.k+'">'+ico('i-send')+
      (anon?'فرستادن پیام بی‌نام':'فرستادن تیکت')+'</button>'});
  const tr=$('[data-tray]');
  state.draft=draft(s);
  if(tr) tray(tr,state.draft);
  if(anon){
    try{ const P=window.NORA_UI.profile?window.NORA_UI.profile():null;
      if(P&&window.NORA_UI.sessUser&&window.NORA_UI.sessUser()){ /* بی‌نام می‌ماند؛ چیزی از حساب نمی‌بَریم */ }
    }catch(e){}
  }
}
function submitTicket(k){
  const s=secOf(k)||SECT[0]; const d=state.draft;
  const anon=s.k==='anon';
  const body=$('#fBody'), name=$('#fName'), cont=$('#fContact'), cat=$('#fCat');
  const text=(body.value||'').trim();
  if(text.length<10){ body.focus(); body.classList.add('flash'); setTimeout(()=>body.classList.remove('flash'),700);
    toast('کمی روشن‌تر بنویس (دست‌کم ده نویسه)'); return }
  if(!anon && !(name.value||'').trim()){ name.focus(); name.classList.add('flash');
    setTimeout(()=>name.classList.remove('flash'),700); toast('نامت را بنویس یا «بی‌نام» را از کاشی صندوق بزن'); return }
  if(d&&d.stopRec) d.stopRec();
  const ats=d?d.atts.slice():[];
  const id='t'+Date.now();
  const t={id:id, code:newCode(), sec:s.k, cat:(cat.value||''), anon:anon,
    name:(name&&name.value.trim())||'', contact:(cont&&cont.value.trim())||'', at:Date.now(),
    thread:[{who:'me',at:Date.now(),text:text,atts:ats,anon:anon}]};
  const all=readT(); all.push(t); writeT(all);
  if(d) d.atts.length=0;
  renderAll();
  toast('تیکت ثبت شد · کد پیگیری '+faN(t.code));
  if(anon){
    modal({ico:'i-eye', tone:toneOf(s), title:'پیامت در صندوق بی‌نام نشست', sub:'کد پیگیری '+faN(t.code),
      body:'<p class="cap" style="text-align:start">خوانده می‌شود و روی تصمیم‌ها اثر می‌گذارد؛ ولی چون نشانی‌ای از تو ثبت نشده، پاسخی به همین پیام نمی‌آید. کد پیگیری برای خودت است.</p>'+
        '<button class="btn block" type="button" data-ticket="complain">'+ico('i-pen')+' اگر پاسخ می‌خواهی، تیکت حساب‌دار بزن</button>'+
        '<button class="btn quiet block" type="button" data-thread="'+id+'">'+ico('i-eye')+' متن پیام بی‌نام خودم</button>',
      foot:'<button class="btn primary block" type="button" data-mclose>باشه</button>'});
    return;
  }
  openThread(id);
  setTimeout(()=>agentReply(id),1400);
}

/* ── ورقه‌ها: مدیریت و پیام‌رسان‌ها، راهنمای رسانه ─────────────────────── */
function renderContacts(){
  const box=$('#ctBody'); if(!box) return;
  const mg=(SUP.managers||[]).map(m=>'<a class="mlink" href="'+esc(m.href)+'"><span class="iw gold">'+ico('i-users')+'</span>'+
    '<span style="flex:1"><b>'+esc(m.n)+'</b><small>'+esc(m.r)+' · '+esc(m.why)+'</small></span>'+
    '<svg class="i go" aria-hidden="true" style="width:17px;height:17px;color:var(--ink-4)"><use href="#i-chev-left"/></svg></a>').join('');
  const forms=SECT.filter(s=>s.form).map(s=>'<a class="mlink" href="'+esc(s.form.href)+'"><span class="iw brand">'+ico('i-doc')+'</span>'+
    '<span style="flex:1"><b>'+esc(s.form.t)+'</b><small>'+esc(s.n)+' · لینک‌شده از سوی مدیر سامانه</small></span>'+
    '<svg class="i go" aria-hidden="true" style="width:17px;height:17px;color:var(--ink-4)"><use href="#i-chev-left"/></svg></a>').join('');
  const mes=(SUP.experts||[]).filter(e=>(e.m||[]).length).map(e=>'<div class="dtx"><span class="iw sky">'+ico('i-user')+'</span>'+
    '<span class="ml"><b>'+esc(e.n)+'</b><small>'+esc(e.r)+'</small>'+
    '<span class="mlinks">'+(e.m||[]).map(m=>'<a class="mchip" href="https://'+esc((MESS[m.k]||'')+m.h)+'" target="_blank" rel="noopener">'+ico('i-link')+esc(m.k)+'</a>').join('')+
    '</span></span></div>').join('');
  box.innerHTML='<div class="shglow">'+ico('i-users')+'</div>'+
    '<div class="shtop"><span class="shtx"><b>مدیریت، همکاری و فرم‌ها</b><small>خط مستقیم مدیران، پیام‌رسان‌ها و فرم‌های لینک‌شده</small></span></div>'+
    '<div class="mpart"><div class="hd">'+ico('i-users')+' مدیران</div><div class="pbd">'+mg+
      '<p class="fine">برای کارهای نهادی و تصمیم‌های مدیریتی؛ کارهای روزمره سریع‌تر از تیکت پیش می‌رود.</p></div></div>'+
    '<div class="mpart"><div class="hd">'+ico('i-link')+' پیام‌رسان‌ها</div><div class="pbd">'+mes+'</div></div>'+
    '<div class="mpart"><div class="hd">'+ico('i-doc')+' فرم‌های مدیر</div><div class="pbd">'+forms+
      '<p class="fine">در چند مورد، پیش از تیکت باید فرم مرتبط پر شود؛ همان‌ها این‌جاست.</p></div></div>'+
    '<button class="btn primary block" type="button" data-ticket="join">'+ico('i-handshake')+' پیشنهاد همکاری</button>'+
    '<button class="btn block" type="button" data-ticket="complain">'+ico('i-flag')+' انتقاد، پیشنهاد یا شکایت</button>'+
    '<button class="btn quiet block" type="button" data-close>بستن</button>';
}
function renderGuide(key){
  const box=$('#mdBody'); if(!box) return;
  const [k,i]=String(key).split(':'); const s=secOf(k)||{}; const m=(s.media||[])[+i]||{};
  const kd=KIND[m.kind]||KIND.video;
  box.innerHTML='<div class="shglow">'+ico(kd.i)+'</div>'+
    '<div class="shtop"><span class="shtx"><b>'+esc(m.t||'راهنمای بخش')+'</b><small>'+esc(s.n||'')+' · '+kd.n+(m.len?' · '+esc(m.len):'')+'</small></span></div>'+
    '<div class="mcard"><div class="mthumb"><span class="mock"><b>'+esc(m.t||'راهنما')+'</b>'+
      '<small>نمونهٔ راهنما برای پیش‌نمایش</small></span>'+
      '<button class="mplay" type="button" data-playmock>'+ico('i-play-f')+'</button></div>'+
      '<div class="mcbody"><b>در این راهنما چه می‌بینی</b>'+
      '<span class="fine">گام‌های همین بخش، یک‌به‌یک، با زبان ساده؛ هر جا گیر کردی همان‌جا تیکت بزن.</span></div></div>'+
    '<div class="mpart"><div class="hd">'+ico('i-layers')+' گام‌به‌گام</div><div class="pbd">'+
      (s.tips||[]).map((t,j)=>'<div class="tipit"><span class="iw '+toneOf(s)+'" style="width:34px;height:34px;border-radius:12px">'+
        ico('i-check')+'</span><span><b>گام '+faN(j+1)+'</b>'+esc(t)+'</span></div>').join('')+
      '</div></div>'+
    '<button class="btn primary block" type="button" data-ticket="'+esc(s.k||'login')+'">'+ico('i-pen')+' اینجا گیر کردم؛ تیکت می‌زنم</button>'+
    '<button class="btn quiet block" type="button" data-close>بستن</button>';
}
function playMock(btn){
  const box=btn.closest('.mthumb');
  if(!box) return;
  const on=box.dataset.play==='1';
  box.dataset.play=on?'0':'1';
  btn.innerHTML=ico(on?'i-play-f':'i-pause');
  btn.setAttribute('aria-label',on?'نمایش راهنما':'نگه‌داشتن');
  if(on) return;
  const mock=box.querySelector('.mock');
  if(mock) mock.classList.add('anim');
  toast('نمونهٔ راهنمای رسانه‌ای');
}

/* ── رویدادها ─────────────────────────────────────────────────────────── */
const state={q:'', grp:'all', open:'', thread:'', draft:null, draft2:null, hideT:0};

document.addEventListener('click',e=>{
  const t=e.target;
  const q=t.closest('[data-qrow] .qbtn');
  if(q){ e.preventDefault(); const row=q.closest('.qrow'); const open=row.classList.toggle('open');
    q.setAttribute('aria-expanded',open?'true':'false'); return }
  const tk=t.closest('[data-ticket]');
  if(tk){ e.preventDefault(); closeSheets(); openTicket(tk.dataset.ticket); return }
  const to=t.closest('[data-ticket-open]');
  if(to){ e.preventDefault(); openTicket(state.open||SECT[0].k); return }
  const sec=t.closest('[data-sec]');
  if(sec){ e.preventDefault(); openSec(sec.dataset.sec); return }
  const th=t.closest('[data-thread]');
  if(th){ e.preventDefault(); openThread(th.dataset.thread); return }
  const md=t.closest('[data-media]');
  if(md){ e.preventDefault(); renderGuide(md.dataset.media); sheetOpen('shMedia'); return }
  const pm=t.closest('[data-playmock]');
  if(pm){ e.preventDefault(); playMock(pm); return }
  const sd=t.closest('[data-sendticket]');
  if(sd){ e.preventDefault(); submitTicket(sd.dataset.sendticket); return }
  const cs=t.closest('[data-csend]');
  if(cs){ e.preventDefault(); sendReply(); return }
  const ct=t.closest('[data-catt]');
  if(ct){ e.preventDefault(); const tr=$('[data-ctray]'); if(!tr) return;
    if(tr.dataset.on==='1'){ tr.dataset.on='0'; tr.innerHTML=''; return }
    tr.dataset.on='1'; state.draft2=draft(state.open); tray(tr,state.draft2); return }
  const cl=t.closest('[data-closetk]');
  if(cl){ e.preventDefault(); const all=readT(); const x=all.find(y=>y.id===cl.dataset.closetk);
    if(x){ x.closed=true; writeT(all); renderAll(); openThread(x.id); toast('تیکت بسته شد؛ هر وقت خواستی تیکت تازه بزن') } return }
  const sh=t.closest('[data-sheet]');
  if(sh){ e.preventDefault(); if(sh.dataset.sheet==='shContacts') renderContacts(); sheetOpen(sh.dataset.sheet); return }
  const jp=t.closest('[data-jump]');
  if(jp){ e.preventDefault(); const el=$('#'+jp.dataset.jump);
    if(el) el.scrollIntoView({behavior:'smooth',block:'start'}); return }
  const tm=t.closest('[data-theme-toggle]');
  if(tm){ e.preventDefault(); if(typeof themeToggle==='function') themeToggle(); return }
  const gr=t.closest('[data-grp]');
  if(gr){ e.preventDefault(); state.grp=gr.dataset.grp; renderGroups(); renderTiles(); return }
  const mc=t.closest('[data-mclose]');
  if(mc){ e.preventDefault(); closeModal(); return }
  if(t.id==='modal'){ closeModal(); return }
  if(t.id==='scrim'){ closeModal(); closeSheets(); return }
  const qu=t.closest('[data-close]');
  if(qu){ e.preventDefault(); closeSheets(); return }
  const hb=t.closest('.help-btn');
  if(hb){ /* همین صفحه‌ایم؛ کاری لازم نیست */ }
});

document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){ const m=$('#modal'); if(m&&!m.hidden){ closeModal(); return } closeSheets(); return }
  if(e.key==='/'&&!/^(INPUT|TEXTAREA|SELECT)$/.test((e.target.tagName||''))){
    const q=$('#supQ'); if(q){ e.preventDefault(); q.focus() }
  }
  if(e.key==='Enter'&&e.target.id==='supReply'){ e.preventDefault(); sendReply() }
});

/* جست‌وجو: با هر واژه، کاشی‌ها و پرسش‌ها هم صاف می‌شوند */
const qEl=$('#supQ');
if(qEl){
  qEl.addEventListener('input',()=>{
    state.q=qEl.value||'';
    const cl=$('#supQClear'); if(cl) cl.hidden=!state.q;
    clearTimeout(state.hideT);
    state.hideT=setTimeout(()=>{ renderTiles(); renderFaq(); },150);
  });
  qEl.addEventListener('keydown',e=>{
    if(e.key==='Escape'){ qEl.value=''; state.q=''; const cl=$('#supQClear'); if(cl) cl.hidden=true; renderTiles(); renderFaq(); }
  });
}
const qc=$('#supQClear');
if(qc) qc.addEventListener('click',()=>{ const el=$('#supQ'); el.value=''; state.q=''; qc.hidden=true; renderTiles(); renderFaq(); el.focus(); });

/* نوار بالا: نشان تنگ‌ها */
addEventListener('scroll',()=>{
  const on=(window.scrollY||document.documentElement.scrollTop)>4;
  document.documentElement.classList.toggle('atscroll',on);
},{passive:true});

/* ── راه‌اندازی ───────────────────────────────────────────────────────── */
seed();
renderAll();
renderContacts();
if(typeof initUI==='function'){ try{ initUI() }catch(e){} }
const h=location.hash.replace('#','');
if(h){
  const S3=secOf(h); if(S3) setTimeout(()=>openSec(h),120);
  else if(h==='mine'||h==='faq'||h==='experts'||h==='topics'){
    const el=document.getElementById(h); if(el) setTimeout(()=>el.scrollIntoView({block:'start'}),120);
  }
}
/* پیگیری زندهٔ تیکت‌ها اگر از صفحهٔ دیگری برگشتی */
addEventListener('storage',ev=>{ if(ev.key===TK_KEY) renderAll() });
})();
