/* ══════════════════════════════════════════════════════════════════════════
   نورا — پشتیبانی و راهنما
   ──────────────────────────────────────────────────────────────────────────
   یک صفحه، یک کتاب راهنما:
     ۱) سرِ صفحه: جست‌وجو و سه کنش زود (تیکت، پیام بی‌نام، فهرست بخش‌ها)
     ۲) راهنمای بخش به بخش: هر بخش ربات یک فصل، با هنر سرصفحه، گام‌های تصویری
        (صفحه‌های کوچک کشیده‌شده)، پرسش و پاسخ و نکتهٔ مدیر سامانه
     ۳) ویژهٔ تو: تیکت تازه، صندوق بی‌نام، تیکت‌های من، تازه‌ترین پاسخ
     ۴) ته صفحه: کارشناس‌ها، مدیران، فرم‌ها و تماس

   تیکت و پاسخ کارشناس هر دو پیوست می‌گیرند: صدا، تصویر، ویدیو، فایل و پیوند.
   بی‌ورود هم کار می‌کند. کلید حافظهٔ تیکت‌ها: nora-support-tickets
   ══════════════════════════════════════════════════════════════════════════ */
(function(){
'use strict';

/* ── داده و کمکی‌ها ────────────────────────────────────────────────────── */
const N=window.NORA||{}, SUP=N.SUPPORT||{}, AC=N.ACCOUNT||{}, POL=AC.policy||{};
const SECT=(SUP.sections||[]).slice();
const GRS=(SUP.grps||[]).slice();
const TONES=SUP.tones||{}, COVERS=SUP.covers||{};
const CATS=POL.ticketCats||[];
const MAXOPEN=Number(POL.ticketMaxOpen)||3;
const $=s=>document.querySelector(s), $$=s=>Array.from(document.querySelectorAll(s));
const esc=t=>String(t==null?'':t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const faN=n=>String(n==null?'':n).replace(/[0-9]/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
const ico=(i,cl)=>'<svg class="i'+(cl?' '+cl:'')+'" aria-hidden="true"><use href="#'+i+'"/></svg>';
const toast=m=>{const u=window.NORA_UI; if(u&&u.toast) u.toast(m);};
const toneOf=s=>(s&&TONES[s.grp])||'brand';
/* نقاشی سرصفحه: در داده نام پرونده است، پوشه‌اش از همین‌جا می‌آید */
const cov=src=>{ src=src||''; return src&&src.indexOf('/')<0?'posters/'+src:src };
const GEN={k:'general', n:'موضوع دیگر', s:'هر چیزی که در بخش‌ها نگنجد', i:'i-pen', cat:'پیشنهاد و انتقاد', grp:'team'};
const secOf=k=>SECT.find(x=>x.k===k)||(k==='general'?Object.assign({},GEN,SUP.gen||{}):null);
const KIND={image:{i:'i-image',n:'تصویر'},video:{i:'i-video',n:'ویدیو'},voice:{i:'i-mic',n:'پیام صوتی'},
  audio:{i:'i-wave',n:'صدا'},link:{i:'i-link',n:'پیوند'},file:{i:'i-file-up',n:'فایل'}};
const MESS={bale:'ble.ir/',tel:'t.me/',soroush:'splus.ir/',gap:'gap.im/'};
const TK_KEY='nora-support-tickets', SEED_KEY='nora-support-seeded';

function stamp(t){
  try{ return new Intl.DateTimeFormat('fa-IR-u-ca-persian',{day:'numeric',month:'long',hour:'2-digit',minute:'2-digit'}).format(new Date(t||Date.now())) }
  catch(e){ return 'امروز' }
}
function kb(n){
  if(!n) return '';
  return n>1048576 ? faN((n/1048576).toFixed(1))+' مگابایت' : faN(Math.max(1,Math.round(n/1024)))+' کیلوبایت';
}
/* شکل نوار صدا از خودِ متن ساخته می‌شود: همیشه یک‌شکل و بی‌تصادف */
function bars(seed,n){
  let out='',k=0; const src=String(seed||'نورا');
  for(let i=0;i<src.length;i++) k=(k*31+src.charCodeAt(i))%9973;
  for(let i=0;i<(n||20);i++){ k=(k*1103515245+12345)%2147483647;
    out+='<i style="height:'+(20+(Math.abs(k)%66))+'%"></i>'; }
  return out;
}

/* ── تیکت‌ها ──────────────────────────────────────────────────────────── */
/* حافظهٔ صفحه: اگر مرورگر جا نداد (حالت ناشناس و جز آن)، در همین تن می‌ماند */
const MEM={};
function lsGet(k){
  try{ const v=localStorage.getItem(k); return v==null?null:v }catch(e){ return MEM[k]!=null?MEM[k]:null }
}
function lsSet(k,v){ try{ localStorage.setItem(k,v) }catch(e){ MEM[k]=v } }
function readT(){
  let v=[]; try{ v=JSON.parse(lsGet(TK_KEY)||'[]') }catch(e){ v=[] }
  return Array.isArray(v)?v:[];
}
function writeT(v){ lsSet(TK_KEY,JSON.stringify(v.slice(0,14))) }
function newCode(){ let c=''; for(let i=0;i<5;i++) c+=String(Math.floor(Math.random()*10)); return c }
const ticketOf=id=>readT().find(t=>t.id===id)||null;
function stateOf(t){
  if(!t) return 'open';
  if(t.closed) return 'closed';
  const last=t.thread&&t.thread[t.thread.length-1];
  return last&&last.who==='agent' ? 'answered' : 'open';
}
const STATE={open:{n:'در انتظار پاسخ',c:''},answered:{n:'پاسخ داده شد',c:'ok'},closed:{n:'بسته‌شده',c:''}};
const openCount=()=>readT().filter(t=>!t.closed).length;
const lastOf=(t,k)=>{const a=[].concat(t.thread||[]).reverse().find(m=>m.who===k); return a?esc(a.text||'').slice(0,110):''};

/* تیکت نمونه، یک‌بار؛ تا کادر تیکت‌های من خالی نماند و شکل گفت‌وگو دیده شود */
function seed(){
  const done=lsGet(SEED_KEY)==='1';
  if(done||readT().length) return;
  const when=Date.now()-86400000*2;
  writeT([{id:'seed1', code:'20451', sec:'cert', cat:'گواهی', anon:false, name:'سارا محمدی',
    contact:'۰۹۱۲۳۴۵۶۷۸۹', at:when,
    thread:[{who:'me', at:when, text:'گواهی کارگاه عکاسی را چه وقت می‌شود دانلود کرد؟',
        atts:[{kind:'image',t:'برگ-گواهی.jpg',size:245760}]},
      {who:'agent', at:when+5400000, by:'مریم داوودی',
       text:'سلام. گواهی بعد از تأیید سرپرست صادر می‌شود و همان روز در «حساب من»، تب بلیت و گواهی می‌آید. سریال که گرفتی، از صفحهٔ استعلام هم می‌توانی بررسی کنی.',
       atts:[{kind:'link',t:'صفحهٔ استعلام گواهی',href:'account.html#cert'}]}]}]);
  lsSet(SEED_KEY,'1');
}

/* ── گام‌های تصویری: صفحه‌های کوچک، کشیده‌شده با CSS ──────────────────── */
function mock(k,tone){
  const L=['',''];
  const grid7=Array.from({length:28},(_,x)=>'<i'+(x===11?' class="on"':'')+'></i>').join('');
  const mrow='<span class="mrow"><i></i><span></span></span>';
  const B={
    phone:'<span class="mfield"></span><span class="mkeys">'+'<i></i>'.repeat(9)+'</span>',
    code:'<span class="mcode">'+['','on','','',''].map(c=>'<i'+(c?' class="on"':'')+'></i>').join('')+'</span><span class="mline s"></span>',
    check:'<span class="mcirc">'+ico('i-check')+'</span><span class="mline"></span><span class="mline s"></span>',
    form:'<span class="mfield"></span><span class="mfield"></span><span class="mline s"></span>',
    upload:'<span class="mcirc">'+ico('i-file-up')+'</span><span class="mline"></span><span class="mline s"></span>',
    ring:'<span class="mring"><span>۶۲٪</span></span><span class="mline s"></span>',
    split:'<span class="msplit"><i class="on"></i><i></i><i></i></span>',
    qr:'<span class="mqr">'+'<i></i>'.repeat(16)+'</span>',
    cert:'<span class="mdoc"><i></i><i></i><i></i><span class="seal"></span></span>',
    book:'<span class="mbooksim"><i></i><i></i></span><span class="mline s"></span>',
    mic:'<span class="mcirc">'+ico('i-mic')+'</span><span class="mwavesim">'+
      [10,20,30,38,24,32,16,22,12].map(h=>'<i style="height:'+h+'px"></i>').join('')+'</span>',
    bell:'<span class="mcirc mbell">'+ico('i-bell')+'<span class="dotp"></span></span><span class="mline s"></span>',
    lock:'<span class="mcirc mlock"><span class="shk"></span>'+ico('i-lock')+'</span><span class="mline s"></span>',
    chat:'<span class="mbubbles"><i></i><i></i><i></i></span>',
    list:'<span class="mrows">'+mrow.repeat(3)+'</span>',
    cal:'<span class="mgrid">'+grid7+'</span>',
    star:'<span class="mstars">'+ico('i-star')+ico('i-star')+ico('i-star')+ico('i-star')+ico('i-star','off')+'</span>'+
      '<span class="mline s"></span>',
    users:'<span class="mavs"><span class="av"></span><span class="av"></span><span class="av"></span></span><span class="mline s"></span>',
    search:'<span class="msearchbar"></span><span class="mrows">'+mrow.repeat(2)+'</span>',
    wallet:'<span class="mcirc">'+ico('i-wallet')+'</span><span class="msplit"><i class="on"></i><i></i></span>',
    bag:'<span class="mcirc">'+ico('i-bag')+'</span><span class="mline"></span><span class="mline s"></span>',
    bookopen:'<span class="mcirc">'+ico('i-book-open')+'</span><span class="mline s"></span>',
    flag:'<span class="mcirc">'+ico('i-flag')+'</span><span class="mbubbles"><i></i><i></i></span>',
    handshake:'<span class="mcirc">'+ico('i-handshake')+'</span><span class="mcircles"><span class="av"></span><span class="av"></span></span>',
    medal:'<span class="mcirc">'+ico('i-medal')+'</span><span class="mstars">'+ico('i-star')+ico('i-star')+ico('i-star')+ico('i-star','off')+'</span>',
    pin:'<span class="mcirc">'+ico('i-pin')+'</span><span class="mline"></span>',
    qricon:'<span class="mcirc">'+ico('i-qr')+'</span><span class="mcode"><i></i><i class="on"></i><i></i></span>',
    archive:'<span class="mcirc">'+ico('i-archive')+'</span><span class="mrows">'+mrow.repeat(2)+'</span>',
    user:'<span class="mcirc">'+ico('i-user')+'</span><span class="mfield"></span>',
    video:'<span class="mthumb"><span class="mplay">'+ico('i-play-f')+'</span></span><span class="mline s"></span>',
    link:'<span class="mcirc">'+ico('i-link')+'</span><span class="mfield"></span><span class="mline s"></span>',
    mobile:'<span class="mcirc">'+ico('i-mobile')+'</span><span class="mcode"><i class="on"></i><i></i><i class="on"></i><i></i></span>'
  };
  return '<span class="mk t-'+esc(tone||'brand')+'">'+(B[k]||'<span class="mline"></span>')+'</span>';
}
function stepHTML(st,i,tone){
  return '<div class="stp"><span class="num">'+faN(i+1)+'</span>'+mock(st[1],tone)+
    '<b>'+esc(st[0])+'</b>'+(st[2]?'<small>'+esc(st[2])+'</small>':'')+'</div>';
}

/* ── پرسش و پاسخ ──────────────────────────────────────────────────────── */
function hl(txt){
  const q=state.q.trim(), s=esc(txt);
  if(q.length<2) return s;
  const re=new RegExp('('+q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')','gi');
  return s.replace(re,'<span class="hitmark">$1</span>');
}
function faqRow(s,i,open,num,goto){
  const qa=s.faq[i]||['',''];
  return '<div class="qrow'+(open?' open':'')+'" data-qrow="'+s.k+':'+i+'">'+
    '<button class="qbtn" type="button" data-faq="'+s.k+':'+i+'" aria-expanded="'+(open?'true':'false')+'">'+
      (num?'<span class="qdot">'+faN(i+1)+'</span>':ico('i-q','go'))+
      '<span><b>'+hl(qa[0])+'</b><small>'+esc(s.n)+(s.cat?' · '+esc(s.cat):'')+'</small></span>'+
      '<svg class="i go" aria-hidden="true"><use href="#i-chev-down"/></svg>'+
    '</button>'+
    '<div class="qans">'+hl(qa[1])+
      '<div class="acl"><button class="abtn" type="button" data-ticket="'+s.k+'">'+ico('i-pen')+' تیکت از همین بخش</button>'+
      (goto?'<button class="abtn" type="button" data-goto="'+s.k+'">'+ico('i-book-open')+' راهنمای همین بخش</button>':'')+
      (s.form?'<a class="abtn" href="'+esc(s.form.href)+'">'+ico('i-doc')+' '+esc(s.form.t)+'</a>':'')+
      '</div></div></div>';
}

/* «پیش از شروع»: چه همراه داشته باشی و مهلت کار */
function prepHTML(s){
  const need=(s.need||[]).map(x=>'<li>'+ico('i-check')+esc(x)+'</li>').join('');
  return '<div class="prep">'+
    (need?'<div class="pcol"><span class="lab">پیش از شروع</span><ul class="needlist">'+need+'</ul></div>':'')+
    (s.time?'<div class="pcol"><span class="lab">مهلت و زمان</span><p class="ptime">'+ico('i-clock')+esc(s.time)+'</p></div>':'')+
  '</div>';
}
/* بخش‌های وابسته: راه میان‌بر را کوتاه می‌کند */
function relHTML(s){
  const items=(s.rel||[]).map(k=>{ const r=secOf(k);
    return r?'<button class="abtn" type="button" data-goto="'+k+'">'+ico(r.i||'i-q')+' '+esc(r.n)+'</button>':'' }).join('');
  return items?'<div class="cblk"><span class="lab">بخش‌های وابسته</span><div class="relrow">'+items+'</div></div>':'';
}

/* ── فصل‌ها و گروه‌ها ─────────────────────────────────────────────────── */
function chapterHTML(s,i){
  const tone=toneOf(s), cover=cov(s.cover);
  const media=(s.media||[]).map((m,j)=>{
    const k=KIND[m.kind]||KIND.video;
    const lab=m.t||(m.kind==='audio'?'راهنمای صوتی':m.kind==='image'?'تصویر گام‌به‌گام':'ویدیو');
    return '<button class="abtn" type="button" data-media="'+s.k+':'+j+'">'+ico(k.i)+' '+esc(lab)+(m.len?'<span class="len">'+esc(m.len)+'</span>':'')+'</button>';
  }).join('');
  return '<article class="chapter" id="ch-'+s.k+'" data-sec="'+s.k+'" style="--i:'+i+'">'+
    '<button class="chhead" type="button" data-open="'+s.k+'" aria-expanded="false" aria-controls="cb-'+s.k+'">'+
      '<span class="iw '+tone+'">'+ico(s.i||'i-q')+'</span>'+
      '<span class="chtx"><b>'+esc(s.n)+'</b><small>'+esc(s.s||'')+'</small>'+
        '<span class="chmeta"><span class="bd">'+faN((s.steps||[]).length)+' گام</span>'+
        '<span class="bd">'+faN((s.faq||[]).length)+' پرسش</span>'+
        (s.cat?'<span class="bd">'+esc(s.cat)+'</span>':'')+'</span></span>'+
      '<svg class="i chgo" aria-hidden="true"><use href="#i-chev-down"/></svg>'+
    '</button>'+
    '<div class="chbody" id="cb-'+s.k+'" hidden>'+
      '<div class="chcover"><img src="'+esc(cover)+'" alt="" loading="lazy" onerror="this.remove()"/>'+
        (s.time?'<span class="tag catg">'+ico('i-clock')+' '+esc(s.time)+'</span>':'')+'</div>'+
      prepHTML(s)+
      '<div class="cbody">'+
        '<div class="cblk"><span class="lab">گام‌های تصویری</span><div class="stprow">'+
          (s.steps||[]).map((st,j)=>stepHTML(st,j,tone)).join('')+'</div></div>'+
        '<div class="cblk"><span class="lab">پرسش و پاسخ</span>'+
          (s.faq||[]).map((_,j)=>faqRow(s,j,false,true)).join('')+'</div>'+
        ((s.tips||[]).length?'<div class="cblk"><span class="lab">نکتهٔ مدیر سامانه</span>'+
          s.tips.map(t=>'<div class="tipit"><span class="iw '+tone+'" style="width:32px;height:32px;border-radius:11px">'+
            ico('i-shield-check')+'</span><span class="tx">'+esc(t)+'</span></div>').join('')+'</div>':'')+
        relHTML(s)+
        '<div class="cha">'+
          '<button class="btn primary sm" type="button" data-ticket="'+s.k+'">'+ico('i-pen')+' تیکت از همین بخش</button>'+
          (s.form?'<a class="abtn" href="'+esc(s.form.href)+'">'+ico('i-doc')+' '+esc(s.form.t)+'</a>':'')+
          '<span class="sp"></span>'+media+
        '</div>'+
      '</div>'+
    '</div></article>';
}
/* باز و بسته کردن فصل، و هم‌گام‌کردن دکمهٔ «همه را باز کن» */
function toggleChapter(k,force){
  const art=document.getElementById('ch-'+k); if(!art) return false;
  const body=art.querySelector('.chbody'), head=art.querySelector('.chhead');
  const open=force==null?!art.classList.contains('open'):!!force;
  art.classList.toggle('open',open);
  if(body) body.hidden=!open;
  if(head) head.setAttribute('aria-expanded',open?'true':'false');
  syncOpenAll();
  return open;
}
function gotoChapter(k){
  const art=document.getElementById('ch-'+k); if(!art) return;
  const g=art.closest('.gsec'); if(g) g.hidden=false;
  art.hidden=false;
  toggleChapter(k,true);
  setTimeout(()=>{ try{ art.scrollIntoView({behavior:'smooth',block:'start'}) }catch(e){} },80);
}
function syncOpenAll(){
  const oa=$('#openAll'); if(!oa) return;
  const all=$$('#chapters .chapter');
  const allOpen=all.length>0&&all.every(a=>a.classList.contains('open'));
  oa.setAttribute('aria-pressed',allOpen?'true':'false');
  const tx=oa.querySelector('[data-oatx]');
  if(tx) tx.textContent=allOpen?'همه را ببند':'همه را باز کن';
  const use=oa.querySelector('use');
  if(use) use.setAttribute('href',allOpen?'#i-chev-down':'#i-layers');
}
function groupHTML(g,i){
  const list=SECT.filter(s=>s.grp===g.k);
  if(!list.length) return '';
  /* هنرِ نوار گروه از واپسین بخشِ گروه می‌آید، تا با فصلِ نخستِ زیرش یک‌شکل نباشد */
  const last=list[list.length-1]||{}, cover=COVERS[g.k]||cov(last.cover);
  return '<section class="gsec" id="g-'+esc(g.k)+'">'+
    '<div class="gband anim" style="--i:'+i+'"><img src="'+esc(cover)+'" alt="" loading="lazy" onerror="this.remove()"/>'+
      '<span class="gtx"><b>'+esc(g.n)+'</b><small>'+faN(list.length)+' بخش</small></span></div>'+
    list.map(chapterHTML).join('')+'</section>';
}
function renderReader(){
  const box=$('#chapters'); if(!box) return;
  box.innerHTML=GRS.map((g,i)=>g.k==='all'?'':groupHTML(g,i)).join('');
  const c=$('#readerCount');
  if(c) c.textContent=faN(SECT.length)+' بخش در '+faN(GRS.filter(g=>g.k!=='all').length)+' گروه';
  const toc=$('#toc');
  if(toc) toc.innerHTML=GRS.map(g=>{
    const n=g.k==='all'?SECT.length:SECT.filter(s=>s.grp===g.k).length;
    return '<button class="fchip" type="button" data-jump="'+(g.k==='all'?'reader':'g-'+g.k)+'">'+
      esc(g.n)+' <span class="n">'+faN(n)+'</span></button>';
  }).join('');
}
/* جست‌وجو: پاسخ‌ها را بالا می‌آورد و فصل‌های مربوط را نشان می‌دهد */
function renderResults(){
  const box=$('#results'); if(!box) return;
  const q=state.q.trim(), list=$('#resList'), miss=$('#resMiss'), cnt=$('#resCount'), cc=$('#readerCount');
  if(q.length<2){
    box.hidden=true; if(list) list.innerHTML='';
    $$('#chapters .chapter').forEach(el=>{ el.hidden=false });
    $$('#chapters .gsec').forEach(g=>{ g.hidden=false });
    if(cc) cc.textContent=faN(SECT.length)+' بخش در '+faN(GRS.filter(g=>g.k!=='all').length)+' گروه';
    return;
  }
  box.hidden=false;
  const hits=[];
  SECT.forEach(s=>(s.faq||[]).forEach((qa,j)=>{
    if((qa[0]+' '+qa[1]+' '+(s.tips||[]).join(' ')).toLowerCase().indexOf(q.toLowerCase())>-1) hits.push({s,j});
  }));
  if(cnt) cnt.textContent=faN(hits.length)+' پاسخ';
  if(list) list.innerHTML=hits.slice(0,10).map(h=>faqRow(h.s,h.j,false,false,true)).join('');
  if(miss) miss.hidden=hits.length>0;
  /* فصل‌ها هم با همان واژه صاف می‌شوند؛ نه شلوغی، نه گم‌شدن */
  const chs=SECT.filter(s=>[s.n,s.s,s.cat||'',(s.tips||[]).join(' '),(s.faq||[]).map(x=>x.join(' ')).join(' ')]
    .join(' ').toLowerCase().indexOf(q.toLowerCase())>-1);
  const keep={}; chs.forEach(s=>keep[s.k]=1);
  $$('#chapters .chapter').forEach(el=>{ el.hidden=!keep[el.id.replace('ch-','')] });
  $$('#chapters .gsec').forEach(g=>{ g.hidden=![...g.querySelectorAll('.chapter')].some(c=>!c.hidden) });
  if(cc) cc.textContent=faN(chs.length)+' بخش با این واژه';
}

/* ── بقیهٔ صفحه ───────────────────────────────────────────────────────── */
function renderHead(){
  const on=(SUP.experts||[]).filter(e=>e.on).length;
  const lv=$('#supLive'); if(lv) lv.textContent=on?'آنلاین':'خارج از ساعت';
  const hr=$('#supHours'); if(hr) hr.textContent=SUP.hours||'';
  const oc=$('#tkOpenCap');
  if(oc) oc.textContent=openCount()?faN(openCount())+' تیکت باز از '+faN(MAXOPEN):'می‌توانی تیکت بزنی';
}
function renderHowto(){
  const box=$('#howto'); if(!box) return;
  box.innerHTML=(SUP.howto||[]).map(r=>'<div class="adrow"><b>'+esc(r[0])+'</b><span class="bd">'+esc(r[1])+'</span></div>').join('');
  const nv=$('#neverText');
  if(nv) nv.innerHTML=ico('i-lock')+' '+esc(SUP.neverText||'');
}
function renderTeam(){
  const box=$('#exList');
  if(box){
    const L=SUP.lead||{}, rows=L.n?[L].concat(SUP.experts||[]):(SUP.experts||[]);
    box.innerHTML=rows.map(e=>{
      const ms=(e.m||[]).map(m=>'<a class="mchip" href="https://'+esc((MESS[m.k]||'')+m.h)+'" target="_blank" rel="noopener">'+ico('i-link')+esc(m.k)+'</a>').join('');
      return '<div class="ecard anim"><span class="eav">'+esc((e.n||'ن').trim().charAt(0))+'</span>'+
        '<b>'+esc(e.n||'')+'</b><small>'+esc(e.r||'')+'</small>'+
        '<span class="tag '+(e.on?'ok':'')+'">'+(e.on?'آنلاین':'بعداً')+'</span>'+
        (ms?'<div class="mlinks">'+ms+'</div>':'')+'</div>';
    }).join('');
    const c=$('#exCount'); if(c) c.textContent=faN(rows.filter(e=>e.on).length)+' نفر آنلاین';
  }
  const mg=$('#mgList');
  if(mg) mg.innerHTML=(SUP.managers||[]).map(m=>'<a class="drow" href="'+esc(m.href)+'">'+
    '<span class="dic gold">'+ico('i-users')+'</span>'+
    '<span class="dtx"><b>'+esc(m.n)+'</b><small>'+esc(m.r)+' · '+esc(m.why)+'</small></span>'+
    icochev()+'</a>').join('');
  const fm=$('#fmList');
  if(fm){
    const rows=SECT.filter(s=>s.form).map(s=>({t:s.form.t,href:s.form.href,who:s.n}));
    fm.innerHTML=rows.map(s=>'<a class="drow" href="'+esc(s.href)+'">'+
      '<span class="dic brand">'+ico('i-doc')+'</span>'+
      '<span class="dtx"><b>'+esc(s.t)+'</b><small>'+esc(s.who)+' · لینک‌شده از سوی مدیر سامانه</small></span>'+
      icochev()+'</a>').join('')||'<p class="fine">فرم تازه‌ای باز نیست.</p>';
  }
  const sla=$('#slaRows');
  if(sla) sla.innerHTML=(SUP.sla||[]).map(r=>'<div class="adrow"><b>'+esc(r[0])+'</b><span class="bd">'+esc(r[1])+'</span></div>').join('');
}
const icochev=()=>'<svg class="i go" aria-hidden="true"><use href="#i-chev-left"/></svg>';

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
        '<span class="tkmeta"><span class="tag '+(S2.c||'')+'">'+S2.n+'</span>'+
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
function paintBell(){
  try{ const u=window.NORA_UI; if(u&&u.syncBell) u.syncBell() }catch(e){}
  const b=document.querySelector('.help-btn');
  if(b) b.setAttribute('title','پشتیبانی و راهنما');
}
function renderAll(){ renderHead(); renderHowto(); renderTeam(); renderMine(); renderLatest(); paintBell(); }

/* ── پیوست‌ها ─────────────────────────────────────────────────────────── */
function draft(){ return {atts:[], rec:null, recOn:false, timer:0, t0:0} }
function pinHTML(a,i){
  const k=KIND[a.kind]||KIND.file;
  return '<span class="pin">'+ico(k.i)+'<span>'+esc(a.t||k.n)+'</span>'+
    (a.size?'<span class="fine">'+kb(a.size)+'</span>':'')+
    '<button type="button" data-unpin="'+i+'" aria-label="برداشتن پیوست">'+ico('i-close')+'</button></span>';
}
function paintPins(root,d){
  const box=root.querySelector('[data-pins]'); if(box) box.innerHTML=d.atts.map(pinHTML).join('');
}
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
    '<div class="pbox" data-lbox hidden><label>نشانی پیوند<input type="url" data-lurl inputmode="url" placeholder="https://" dir="ltr"/></label>'+
      '<div class="tbtop" style="margin-top:8px"><span class="fine">با «افزودن» به پیوست‌ها می‌چسبد.</span>'+
      '<span class="sp"></span><button class="btn sm" type="button" data-ladd>افزودن</button></div></div>'+
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
    const b=e.target.closest('[data-att]');
    if(b){
      const k=b.dataset.att;
      if(k==='link'){ const lb=root.querySelector('[data-lbox]'); lb.hidden=!lb.hidden;
        if(!lb.hidden) lb.querySelector('[data-lurl]').focus(); return }
      if(k==='voice'){ rec(); return }
      fin.setAttribute('accept',ACC[k]||'*/*'); fin.dataset.kind=k; fin.value=''; fin.click(); return;
    }
    const la=e.target.closest('[data-ladd]');
    if(la){
      const u=root.querySelector('[data-lurl]'), v=(u.value||'').trim();
      if(!/^https?:\/\/\S+/i.test(v)){ u.focus(); u.classList.add('flash');
        setTimeout(()=>u.classList.remove('flash'),600); toast('نشانی را با http بنویس'); return }
      add({kind:'link',t:v.replace(/^https?:\/\//,'').slice(0,60),href:v}); u.value='';
      root.querySelector('[data-lbox]').hidden=true; return;
    }
    const un=e.target.closest('[data-unpin]');
    if(un){ d.atts.splice(Number(un.dataset.unpin),1); paintPins(root,d); }
  });
  fin.addEventListener('change',()=>{
    const k=fin.dataset.kind||'file';
    Array.from(fin.files||[]).slice(0,3).forEach(f=>{
      const kind=/^video\//.test(f.type)?'video':/^audio\//.test(f.type)?'voice':/^image\//.test(f.type)?'image':k;
      add({kind:kind, t:f.name, size:f.size});
    });
  });
  function rec(){
    const btn=root.querySelector('[data-att="voice"]'); if(!btn) return;
    const tx=btn.querySelector('[data-rtx]'), bar=btn.querySelector('.pbar i');
    if(d.recOn){ stopRec(); return }
    d.t0=Date.now(); d.recOn=true;
    btn.classList.add('on'); btn.setAttribute('aria-pressed','true'); tx.textContent='بایست';
    d.timer=setInterval(()=>{
      const sec=Math.min(60,(Date.now()-d.t0)/1000);
      bar.style.width=(sec/60*100)+'%';
      if(sec>=60) stopRec();
    },120);
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
  d.stopRec=()=>stopRec(false);
  paintPins(root,d);
}

/* ── پاپ‌آپ: تیکت و گفت‌وگو ───────────────────────────────────────────── */
const state={q:'', threads:{}, open:'', thread:'', guide:'', draft:null, hideT:0};
function modal(v){
  const m=$('#modal'); if(!m) return;
  const mi=$('#mIco'), mt=$('#mTitle'), ms=$('#mSub'), mb=$('#mBody'), mf=$('#mFoot');
  mi.innerHTML='<span class="iw '+esc(v.tone||'brand')+'" style="width:44px;height:44px">'+ico(v.ico||'i-headphone')+'</span>';
  mt.textContent=v.title||''; ms.textContent=v.sub||'';
  mb.innerHTML=v.body||''; mf.innerHTML=v.foot||'';
  if(m.hidden){ m.hidden=false; document.body.classList.add('modal-open'); try{ m.querySelector('.mdlg').focus({preventScroll:true}) }catch(e){} }
  mb.scrollTop=0;
}
function closeModal(){
  const m=$('#modal'); if(!m||m.hidden) return;
  m.hidden=true; document.body.classList.remove('modal-open'); $('#mBody').innerHTML=''; state.thread='';
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
  const b=el.querySelector('.sbody'); if(b) b.scrollTop=0;
}
function ticketForm(s,anon){
  const cat=(CATS.indexOf(s.cat)>-1?s.cat:(CATS[0]||'پشتیبانی'));
  return '<div class="tkt">'+
    (anon?'<p class="fine">'+ico('i-eye')+' نام و شماره‌ات ثبت نمی‌شود؛ کد پیگیری فقط برای خودت است.</p>':
      '<label>نام و نشان<input id="fName" type="text" autocomplete="name" placeholder="مثلاً سارا محمدی"/></label>'+
      '<label>راه تماس (اختیاری)<input id="fContact" type="text" inputmode="tel" autocomplete="tel" placeholder="۰۹۱۲۳۴۵۶۷۸۹ یا رایانامه"/></label>')+
    '<label>موضوع<select id="fCat">'+CATS.map(c=>'<option'+(c===cat?' selected':'')+'>'+esc(c)+'</option>').join('')+'</select></label>'+
    '<label>متن پیام<textarea id="fBody" placeholder="چه شد، کِی شد و چه انتظاری داری؟"></textarea></label>'+
    '<div><span class="fine">پیوست‌ها</span><div data-tray></div></div>'+
    '<p class="fine">'+ico('i-shield')+' بدون ورود هم می‌شود؛ با ورود، پاسخ در «حساب من» می‌ماند.</p>'+
  '</div>';
}
function openTicket(k){
  const s=secOf(k)||{k:'general',n:'موضوع دیگر',s:'هر چیزی که در بخش‌ها نگنجد',i:'i-pen',cat:'پیشنهاد و انتقاد'};
  const anon=s.k==='anon';
  if(openCount()>=MAXOPEN){
    modal({ico:'i-clock', tone:toneOf(s), title:'تیکت‌های بازت زیاد است', sub:'تا '+faN(MAXOPEN)+' تیکت باز می‌شود',
      body:'<p class="cap" style="text-align:start">'+faN(openCount())+' تیکت باز داری. یکی را ببند یا پاسخ همان‌ها را ادامه بده، بعد تیکت تازه بزن.</p>',
      foot:'<button class="btn primary block" type="button" data-mclose>باشه</button>'});
    return;
  }
  state.open=s.k; state.draft=draft();
  modal({ico:s.i, tone:toneOf(s), title:(anon?'پیام بی‌نام':'تیکت تازه')+' · '+s.n,
    sub:anon?'بی‌رد و بی‌نام؛ کد پیگیری برای خودت است':'پیوست صدا، تصویر، ویدیو، فایل و پیوند هم می‌شود',
    body:ticketForm(s,anon),
    foot:'<button class="btn primary block" type="button" data-sendticket="'+s.k+'">'+ico('i-send')+
      (anon?'فرستادن پیام بی‌نام':'فرستادن تیکت')+'</button>'});
  const tr=$('[data-tray]'); if(tr) tray(tr,state.draft);
}
function submitTicket(k){
  const s=secOf(k)||{k:'general',n:'موضوع دیگر',i:'i-pen'};
  const anon=s.k==='anon', d=state.draft;
  const body=$('#fBody'), name=$('#fName'), cont=$('#fContact'), cat=$('#fCat');
  const text=(body.value||'').trim();
  if(text.length<10){ body.focus(); body.classList.add('flash'); setTimeout(()=>body.classList.remove('flash'),700);
    toast('کمی روشن‌تر بنویس (دست‌کم ده نویسه)'); return }
  if(!anon&&!(name.value||'').trim()){ name.focus(); name.classList.add('flash');
    setTimeout(()=>name.classList.remove('flash'),700); toast('نامت را بنویس یا «پیام بی‌نام» را بزن'); return }
  if(d&&d.stopRec) d.stopRec();
  const ats=d?d.atts.slice():[];
  const id='t'+Date.now();
  const t={id:id, code:newCode(), sec:s.k, cat:(cat.value||''), anon:anon,
    name:(name&&name.value.trim())||'', contact:(cont&&cont.value.trim())||'', at:Date.now(),
    thread:[{who:'me',at:Date.now(),text:text,atts:ats}]};
  const all=readT(); all.push(t); writeT(all);
  if(d) d.atts.length=0;
  renderAll();
  toast('تیکت ثبت شد · کد پیگیری '+faN(t.code));
  if(anon){
    state.threads[id]=draft();
    modal({ico:'i-eye', tone:toneOf(s), title:'پیامت در صندوق بی‌نام نشست', sub:'کد پیگیری '+faN(t.code),
      body:'<p class="cap" style="text-align:start">خوانده می‌شود و روی تصمیم‌ها اثر می‌گذارد؛ ولی چون نشانی‌ای از تو ثبت نشده، پاسخی به همین پیام نمی‌آید. کد پیگیری برای خودت است.</p>'+
        '<button class="btn block" type="button" data-ticket="complain">'+ico('i-pen')+' اگر پاسخ می‌خواهی، تیکت حساب‌دار بزن</button>',
      foot:'<button class="btn primary block" type="button" data-mclose>باشه</button>'});
    return;
  }
  openThread(id);
  setTimeout(()=>agentReply(id),1400);
}
function bubbleHTML(m){
  const mine=m.who==='me';
  return '<div class="frow'+(mine?' me':'')+'"><div class="fbubble">'+
    (mine?'':'<span class="fwho">'+esc(m.by||'کارشناس پشتیبانی')+'</span>')+
    esc(m.text||'').replace(/\n/g,'<br/>')+
    (m.atts||[]).map(a=>{
      const k=KIND[a.kind]||KIND.file;
      if(a.kind==='audio'||a.kind==='voice')
        return '<div class="fx">'+ico('i-wave')+'<span class="pbsim" aria-hidden="true">'+bars(a.t||a.len,18)+'</span>'+
          '<span class="fine">'+esc(a.len||a.t||k.n)+'</span></div>';
      if(a.kind==='link')
        return '<a class="fx" href="'+esc(a.href||'#')+'">'+ico('i-link')+'<b dir="ltr">'+esc(a.t||a.href||'پیوند')+'</b></a>';
      return '<div class="fx">'+ico(k.i)+'<b>'+esc(a.t||k.n)+'</b>'+(a.size?'<span class="fine">'+kb(a.size)+'</span>':'')+'</div>';
    }).join('')+
    '<span class="fmeta">'+stamp(m.at)+(m.anon?' · بی‌نام':'')+'</span></div></div>';
}
function openThread(id){
  const t=ticketOf(id); if(!t) return;
  const s=secOf(t.sec)||{n:'پشتیبانی',i:'i-headphone'};
  const st=stateOf(t), S2=STATE[st];
  if(!state.threads[id]) state.threads[id]=draft();
  state.open=t.sec; state.thread=id;
  const body='<div class="tkt-acc'+(st==='open'?'':' on')+'"><span class="tktx"><b>'+esc(s.n)+'</b>'+
      '<span class="s">'+S2.n+(t.cat?' · '+esc(t.cat):'')+'</span></span>'+
      '<span class="bd">کد '+faN(t.code)+'</span><span class="pb" aria-hidden="true"><i></i></span></div>'+
    '<div class="thread" data-thread-box>'+t.thread.map(bubbleHTML).join('')+'</div>'+
    (st==='closed'?'<p class="fine">این تیکت بسته شده. اگر ادامه دارد، تیکت تازه بزن.</p>':
      '<div data-ctray></div>'+
      '<div class="cinput"><button class="abtn" type="button" data-catt aria-label="پیوست">'+ico('i-clip')+'</button>'+
      '<input id="supReply" type="text" placeholder="پاسخ یا فایل تازه…" aria-label="متن پیام"/>'+
      '<button class="btn primary" type="button" data-csend>'+ico('i-send')+'</button></div>'+
      '<p class="fine">'+ico('i-clock')+' '+esc(SUP.reply||'پاسخ کارشناس تا پایان روز کاری')+'</p>');
  modal({ico:s.i, tone:toneOf(s), title:'گفت‌وگوی تیکت', sub:s.n+' · کد '+faN(t.code), body:body,
    foot:'<div class="btn-row"><button class="btn quiet" type="button" data-mclose>بستن</button>'+
      (st==='closed'?'':'<button class="btn block" type="button" data-closetk="'+t.id+'">'+ico('i-check')+' پایان تیکت</button>')+'</div>'});
  const mb=$('#mBody'); if(mb) mb.scrollTop=mb.scrollHeight;
}
function msgToThread(id,m){
  const all=readT(); const t=all.find(x=>x.id===id); if(!t) return;
  t.thread=t.thread||[]; t.thread.push(m); t.at=Date.now(); writeT(all);
}
function sendReply(){
  const id=state.thread, inp=$('#supReply'); if(!id||!inp) return;
  const v=(inp.value||'').trim(), d=state.threads[id];
  if(!v&&!(d&&d.atts.length)){ inp.focus(); return }
  if(d&&d.stopRec) d.stopRec();
  msgToThread(id,{who:'me',at:Date.now(),text:v,atts:(d?d.atts.slice():[])});
  if(d) d.atts.length=0;
  inp.value=''; openThread(id); renderAll();
  toast('پیامت رفت؛ پاسخ کارشناس همین‌جا می‌آید');
  if(stateOf(ticketOf(id))==='open') setTimeout(()=>agentReply(id),1400);
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

/* ── ورقهٔ راهنمای تصویری و صوتی ─────────────────────────────────────── */
function renderGuide(key){
  const box=$('#mdBody'); if(!box) return;
  const p=String(key).split(':'), s=secOf(p[0])||{}, m=(s.media||[])[+p[1]]||{};
  state.guide=s.k;
  const k=KIND[m.kind]||KIND.video, cover=cov(s.cover);
  box.innerHTML='<div class="shglow">'+ico(k.i)+'</div>'+
    '<div class="shtop"><span class="shtx"><b>'+esc(m.t||'راهنمای بخش')+'</b>'+
      '<small>'+esc(s.n||'')+' · '+k.n+(m.len?' · '+esc(m.len):'')+'</small></span></div>'+
    '<div class="gcard"><div class="gthumb"><img src="'+esc(cover)+'" alt="" onerror="this.remove()"/>'+
      '<button class="gplay" type="button" data-playmock aria-label="نمایش نمونه">'+ico('i-play-f')+'</button></div>'+
      '<div class="gbody"><b>در این راهنما چه می‌بینی</b>'+
      '<span class="fine">گام‌های همین بخش، یک‌به‌یک و با زبان ساده؛ هر جا گیر کردی، همان‌جا تیکت بزن.</span></div></div>'+
    '<div class="mpart"><div class="hd">'+ico('i-layers')+' گام‌به‌گام</div><div class="pbd">'+
      (s.steps||[]).map((st,j)=>'<div class="tipit"><span class="iw '+toneOf(s)+'" style="width:32px;height:32px;border-radius:11px">'+
        faN(j+1)+'</span><span class="tx"><b>'+esc(st[0])+'</b>'+esc(st[2]||'')+'</span></div>').join('')+
    '</div></div>'+
    '<div class="btn-row">'+
      '<button class="btn quiet" type="button" data-gstep="-1">'+ico('i-chev-right')+' بخش پیش</button>'+
      '<button class="btn quiet" type="button" data-gstep="1">بخش پس '+ico('i-chev-left')+'</button>'+
    '</div>'+
    '<button class="btn primary block" type="button" data-ticket="'+esc(s.k||'general')+'">'+ico('i-pen')+' اینجا گیر کردم؛ تیکت می‌زنم</button>'+
    '<button class="btn quiet block" type="button" data-close>بستن</button>';
}
function playMock(btn){
  const box=btn.closest('.gthumb'); if(!box) return;
  const on=box.dataset.play==='1';
  box.dataset.play=on?'0':'1';
  btn.innerHTML=ico(on?'i-play-f':'i-pause');
  toast(on?'نمونهٔ راهنمای رسانه‌ای':'نگه‌داشتن');
}

/* ── رویدادها ─────────────────────────────────────────────────────────── */
document.addEventListener('click',e=>{
  const t=e.target;
  const q=t.closest('[data-qrow] .qbtn');
  if(q){ e.preventDefault(); const row=q.closest('.qrow'), open=row.classList.toggle('open');
    q.setAttribute('aria-expanded',open?'true':'false'); return }
  const gl=t.closest('[data-goto]');
  if(gl){ e.preventDefault(); closeSheets(); closeModal(); gotoChapter(gl.dataset.goto); return }
  const op=t.closest('[data-open]');
  if(op){ e.preventDefault(); toggleChapter(op.dataset.open); return }
  const tk=t.closest('[data-ticket]');
  if(tk){ e.preventDefault(); closeSheets(); openTicket(tk.dataset.ticket); return }
  const th=t.closest('[data-thread]');
  if(th){ e.preventDefault(); openThread(th.dataset.thread); return }
  const md=t.closest('[data-media]');
  if(md){ e.preventDefault(); renderGuide(md.dataset.media); sheetOpen('shMedia'); return }
  const pm=t.closest('[data-playmock]');
  if(pm){ e.preventDefault(); playMock(pm); return }
  const gs=t.closest('[data-gstep]');
  if(gs){ e.preventDefault();
    const cur=SECT.findIndex(x=>x.k===state.guide);
    const nx=SECT[cur+(+gs.dataset.gstep)];
    if(nx&&nx.media&&nx.media.length){ state.guide=nx.k; renderGuide(nx.k+':0'); }
    else toast(gs.dataset.gstep<0?'بخش پیشین همین بود':'بخش واپسین همین بود');
    return }
  const sd=t.closest('[data-sendticket]');
  if(sd){ e.preventDefault(); submitTicket(sd.dataset.sendticket); return }
  const cs=t.closest('[data-csend]');
  if(cs){ e.preventDefault(); sendReply(); return }
  const ct=t.closest('[data-catt]');
  if(ct){ e.preventDefault(); const tr=$('[data-ctray]'); if(!tr) return;
    if(tr.dataset.on==='1'){ tr.dataset.on='0'; tr.innerHTML=''; return }
    tr.dataset.on='1'; tray(tr,state.threads[state.thread]||(state.threads[state.thread]=draft())); return }
  const cl=t.closest('[data-closetk]');
  if(cl){ e.preventDefault(); const all=readT(), x=all.find(y=>y.id===cl.dataset.closetk);
    if(x){ x.closed=true; writeT(all); renderAll(); openThread(x.id); toast('تیکت بسته شد') } return }
  const jp=t.closest('[data-jump]');
  if(jp){ e.preventDefault(); const el=$('#'+jp.dataset.jump);
    if(el) el.scrollIntoView({behavior:'smooth',block:'start'}); return }
  const mc=t.closest('[data-mclose]');
  if(mc){ e.preventDefault(); closeModal(); return }
  if(t.id==='modal'){ closeModal(); return }
  if(t.id==='scrim'){ closeModal(); closeSheets(); return }
  const cc=t.closest('[data-close]');
  if(cc){ e.preventDefault(); closeSheets(); return }
  const tm=t.closest('[data-theme-toggle]');
  if(tm){ e.preventDefault(); if(typeof themeToggle==='function') themeToggle(); return }
});
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){ const m=$('#modal'); if(m&&!m.hidden){ closeModal(); return } closeSheets(); return }
  if(e.key==='/'&&!/^(INPUT|TEXTAREA|SELECT)$/.test((e.target.tagName||''))){
    const q=$('#supQ'); if(q){ e.preventDefault(); q.focus() }
  }
  if(e.key==='Enter'&&e.target.id==='supReply'){ e.preventDefault(); sendReply() }
});

/* جست‌وجو */
const qEl=$('#supQ');
function runSearch(){
  state.q=qEl?qEl.value||'':'';
  const cl=$('#supQClear'); if(cl) cl.hidden=!state.q;
  clearTimeout(state.hideT);
  state.hideT=setTimeout(renderResults,160);
}
if(qEl){
  qEl.addEventListener('input',runSearch);
  qEl.addEventListener('keydown',e=>{
    if(e.key==='Escape'){ qEl.value=''; runSearch(); }
  });
}
const qc=$('#supQClear');
if(qc) qc.addEventListener('click',()=>{ if(qEl) qEl.value=''; runSearch(); if(qEl) qEl.focus(); });

/* نوار چسب گروه‌ها با چشمِ صفحه هم‌گام می‌شود */
function markChip(id){ $$('#toc .fchip').forEach(c=>c.classList.toggle('sel',c.dataset.jump===id)) }
if(typeof IntersectionObserver==='function'){
  const spy=new IntersectionObserver(es=>{
    es.forEach(en=>{ if(en.isIntersecting) markChip(en.target.id) });
  },{rootMargin:'-72px 0px -68% 0px'});
  $$('#chapters .gsec').forEach(g=>spy.observe(g));
}
/* اندازهٔ نوار بالا را به CSS می‌دهیم تا نوار چسب گروه‌ها درست بنشیند */
function measureTop(){
  const tb=document.querySelector('.topbar');
  const h=tb?Math.round(tb.getBoundingClientRect().height):56;
  document.documentElement.style.setProperty('--tb',(h||56)+'px');
}
measureTop(); addEventListener('resize',measureTop);
const oaBtn=$('#openAll');
if(oaBtn) oaBtn.addEventListener('click',()=>{
  const all=$$('#chapters .chapter');
  const anyClosed=all.some(a=>!a.classList.contains('open'));
  all.forEach(a=>toggleChapter(a.dataset.sec,anyClosed));
  toast(anyClosed?faN(all.length)+' بخش باز شد':'همه بسته شد');
});
addEventListener('scroll',()=>{
  const on=(window.scrollY||document.documentElement.scrollTop)>4;
  document.documentElement.classList.toggle('atscroll',on);
},{passive:true});

/* ── راه‌اندازی ───────────────────────────────────────────────────────── */
seed();
renderReader();
renderAll();
if(typeof initUI==='function'){ try{ initUI() }catch(e){} }
const h=location.hash.replace('#','');
if(h) setTimeout(()=>{
  const k=h.replace(/^ch-/,''), sec=secOf(k);
  if(sec&&document.getElementById('ch-'+k)){ gotoChapter(k); return }
  const el=document.getElementById(h);
  if(el&&el.scrollIntoView) el.scrollIntoView({block:'start'});
},160);
addEventListener('storage',ev=>{ if(ev.key===TK_KEY) renderAll() });
})();
