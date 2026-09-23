/* ══════════════════════════════════════════════════════════════════════════
   نورا — موتور مشترک صفحه‌ها
   هر چیزی که در بیش از یک صفحه لازم است، همین‌جا نوشته می‌شود:
   اعداد و حروف، انتخاب‌گرها، داده‌های ایران، بلیت، کیوآرکد، و ابزارهای رابط.
   ══════════════════════════════════════════════════════════════════════════ */

/* ── عدد و حروف ───────────────────────────────────────────────────────── */
const NR=Number;
const fa=n=>NR(n).toLocaleString('fa-IR');
const faN=n=>String(NR(n)).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
const unFa=s=>String(s).replace(/[۰-۹]/g,d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d));
const YEK=['','یک','دو','سه','چهار','پنج','شش','هفت','هشت','نه'];
const DAH=['ده','یازده','دوازده','سیزده','چهارده','پانزده','شانزده','هفده','هجده','نوزده'];
const DAHGAN=['','','بیست','سی','چهل','پنجاه','شصت','هفتاد','هشتاد','نود'];
const SAD=['','صد','دویست','سیصد','چهارصد','پانصد','ششصد','هفتصد','هشتصد','نهصد'];
function w3(n){const o=[],h=Math.floor(n/100),r=n%100;if(h)o.push(SAD[h]);
  if(r>=10&&r<20)o.push(DAH[r-10]);else{const d=Math.floor(r/10),y=r%10;if(d>=2)o.push(DAHGAN[d]);if(y)o.push(YEK[y]);}
  return o.join(' و ');}
function words(n){n=Math.round(n);if(n<=0)return 'صفر';const p=[];
  const b=Math.floor(n/1e9),m=Math.floor(n%1e9/1e6),k=Math.floor(n%1e6/1000),r=n%1000;
  if(b)p.push(w3(b)+' میلیارد');if(m)p.push(w3(m)+' میلیون');
  if(k)p.push((k===1?'':w3(k)+' ')+'هزار');if(r)p.push(w3(r));return p.join(' و ');}
/* قاعده: عدد به ریال — تومان به حروف */
const rialTxt=n=>fa(n)+' ریال';
const tomanTxt=n=>words(n/10)+' تومان';
const money=n=>rialTxt(n)+' — '+tomanTxt(n);

/* ── داده‌های ایران ───────────────────────────────────────────────────── */
const PROVINCES={
 'تهران':['تهران','اسلامشهر','شهریار','قرچک','ورامین','پاکدشت','رباط‌کریم','پردیس','دماوند','فیروزکوه','لواسان','چهاردانگه'],
 'البرز':['کرج','فردیس','نظرآباد','هشتگرد','اشتهارد','طالقان','محمدشهر','ماهدشت'],
 'اصفهان':['اصفهان','کاشان','خمینی‌شهر','نجف‌آباد','شاهین‌شهر','شهرضا','فولادشهر','اردستان','نطنز','گلپایگان'],
 'فارس':['شیراز','مرودشت','کازرون','جهرم','فسا','داراب','لار','آباده','نی‌ریز','اقلید','سپیدان'],
 'خراسان رضوی':['مشهد','نیشابور','سبزوار','تربت حیدریه','قوچان','کاشمر','تربت جام','گناباد','چناران','خواف'],
 'آذربایجان شرقی':['تبریز','مراغه','مرند','اهر','بناب','میانه','سراب','آذرشهر','شبستر','جلفا'],
 'آذربایجان غربی':['ارومیه','خوی','میاندوآب','بوکان','مهاباد','سلماس','پیرانشهر','نقده','ماکو'],
 'خوزستان':['اهواز','آبادان','خرمشهر','دزفول','بندر ماهشهر','بهبهان','شوشتر','اندیمشک','ایذه','مسجد سلیمان'],
 'گیلان':['رشت','انزلی','لاهیجان','آستارا','تالش','رودسر','فومن','صومعه‌سرا','آستانه اشرفیه'],
 'مازندران':['ساری','بابل','آمل','قائم‌شهر','بهشهر','چالوس','نوشهر','تنکابن','رامسر','نکا'],
 'کرمان':['کرمان','سیرجان','رفسنجان','جیرفت','بم','زرند','کهنوج','بردسیر','شهربابک'],
 'سیستان و بلوچستان':['زاهدان','زابل','چابهار','ایرانشهر','خاش','سراوان','کنارک','نیک‌شهر'],
 'کرمانشاه':['کرمانشاه','اسلام‌آباد غرب','هرسین','سنقر','پاوه','کنگاور','جوانرود','صحنه'],
 'گلستان':['گرگان','گنبد کاووس','علی‌آباد','بندر ترکمن','آق‌قلا','کردکوی','مینودشت','آزادشهر'],
 'هرمزگان':['بندرعباس','قشم','میناب','بندر لنگه','رودان','بستک','پارسیان','حاجی‌آباد'],
 'لرستان':['خرم‌آباد','بروجرد','دورود','الیگودرز','کوهدشت','نورآباد','پل‌دختر','ازنا'],
 'همدان':['همدان','ملایر','نهاوند','تویسرکان','اسدآباد','بهار','کبودرآهنگ','رزن'],
 'مرکزی':['اراک','ساوه','خمین','محلات','دلیجان','شازند','تفرش','آشتیان'],
 'قزوین':['قزوین','الوند','تاکستان','آبیک','بوئین‌زهرا','شال','آوج'],
 'اردبیل':['اردبیل','پارس‌آباد','مشگین‌شهر','خلخال','گرمی','نمین','بیله‌سوار'],
 'بوشهر':['بوشهر','برازجان','گناوه','کنگان','دیر','جم','عسلویه','دیلم'],
 'زنجان':['زنجان','ابهر','خرمدره','قیدار','صائین‌قلعه','ماه‌نشان','هیدج'],
 'یزد':['یزد','میبد','اردکان','بافق','مهریز','ابرکوه','تفت','اشکذر'],
 'قم':['قم','قنوات','جعفریه','دستجرد','سلفچگان'],
 'سمنان':['سمنان','شاهرود','دامغان','گرمسار','مهدی‌شهر','میامی','بسطام'],
 'کردستان':['سنندج','سقز','مریوان','بانه','قروه','بیجار','کامیاران','دیواندره'],
 'چهارمحال و بختیاری':['شهرکرد','بروجن','فارسان','لردگان','سامان','فرخ‌شهر','هفشجان'],
 'خراسان شمالی':['بجنورد','شیروان','اسفراین','آشخانه','گرمه','جاجرم','فاروج'],
 'خراسان جنوبی':['بیرجند','قائن','فردوس','نهبندان','طبس','سربیشه','خوسف'],
 'ایلام':['ایلام','دهلران','آبدانان','مهران','ایوان','دره‌شهر','چرداول'],
 'کهگیلویه و بویراحمد':['یاسوج','دوگنبدان','دهدشت','سی‌سخت','لیکک','چرام','باشت']
};
const UNIS=['دانشگاه تهران','شهید بهشتی','صنعتی شریف','صنعتی امیرکبیر','علم و صنعت ایران','خواجه نصیرالدین طوسی','علامه طباطبایی','الزهرا','تربیت مدرس','فردوسی مشهد','اصفهان','صنعتی اصفهان','شیراز','تبریز','صنعتی سهند','ارومیه','گیلان','مازندران','بوعلی سینا','رازی کرمانشاه','شهید چمران اهواز','شهید باهنر کرمان','سیستان و بلوچستان','یزد','قزوین','آزاد اسلامی','پیام نور','علمی کاربردی','فنی و حرفه‌ای','شهید رجایی','صنعتی مالک اشتر','علوم پزشکی تهران','علوم پزشکی ایران','علوم پزشکی شهید بهشتی','علوم پزشکی مشهد','علوم پزشکی اصفهان','علوم پزشکی شیراز','البرز','صنعتی اراک','صنعتی خواجه نصیر'];
const JOBS=['کارمند دولت','کارمند شرکت خصوصی','آزاد و صاحب کسب‌وکار','مهندس','پزشک و پرستار','معلم و استاد','دانشجو','هنرمند و رسانه','نیروی نظامی و انتظامی','کشاورز','راننده','فروشنده و بازاریاب','برنامه‌نویس و فناوری اطلاعات','حسابدار و مالی','وکیل و کارشناس حقوقی','راهنما و گردشگری','خانه‌دار','بازنشسته','جویای کار','سایر'];
const EDU=['زیر دیپلم','دیپلم','کاردانی','کارشناسی','کارشناسی ارشد','دکترا','حوزوی','دانش‌آموز'];
const EVENTKIT={provinces:Object.keys(PROVINCES),uni:UNIS,jobs:JOBS,edu:EDU};

/* ── انتخاب‌گرها: هیچ‌جا تایپ نکنیم ─────────────────────────────────────── */
const CAL=[1400,1401,1402,1403,1404,1405,1406,1407,1408,1409,1410,1411,1412];
const MH=[31,31,31,31,31,31,30,30,30,30,30,29];
const leap=y=>[1403,1408,1412,1399].includes(NR(y));
const daysOf=(y,m)=>m===12?(leap(y)?30:29):MH[m-1];
const MONTHS=['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];

function sel(html){return html;}
function opts(list,cur){return list.map(v=>`<option value="${v}" ${String(v)===String(cur)?'selected':''}>${v}</option>`).join('');}

/* ساخت یک انتخاب‌گر تاریخ/ساعت/تاریخ‌وساعت */
function pickHTML(kind,value,id){
  return `<div class="pick" data-pick="${kind}" data-val="${value||''}" ${id?`id="${id}"`:''}>
    <select class="input pk1 hide-wheel" aria-label="سال"></select>
    <select class="input pk2" aria-label="ماه"></select>
    <select class="input pk3" aria-label="روز"></select>
    <select class="input pk4" aria-label="ساعت"></select>
    <select class="input pk5" aria-label="دقیقه"></select>
  </div>`;
}
function pickFill(el){
  const kind=el.dataset.pick;
  const v=(el.dataset.val||'').replace(/[۰-۹]/g,d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d));
  const [date='',time='']=v.split(' — ').length>1?v.split(' — '):[v.split(' ')[0]||'',v.split(' ')[1]||''];
  const dp=(date||'').split('/'), tp=(time||'').split(':');
  const y=dp[0]||1405, m=dp[1]||7, d=dp[2]||1, hh=tp[0]||'16', mm=tp[1]||'00';
  const P=el.querySelector.bind(el);
  P('.pk1').innerHTML=opts(CAL.reverse().map(faN),faN(y)); CAL.reverse();
  P('.pk2').innerHTML=MONTHS.map((n,i)=>`<option value="${i+1}" ${NR(m)===i+1?'selected':''}>${n}</option>`).join('');
  const dn=daysOf(y,m);
  P('.pk3').innerHTML=Array.from({length:dn},(_,i)=>`<option value="${i+1}" ${NR(d)===i+1?'selected':''}>${faN(i+1)}</option>`).join('');
  P('.pk4').innerHTML=Array.from({length:24},(_,i)=>`<option value="${String(i).padStart(2,'0')}" ${NR(hh)===i?'selected':''}>${faN(i)}</option>`).join('');
  P('.pk5').innerHTML=[0,15,30,45].map(i=>`<option value="${String(i).padStart(2,'0')}" ${NR(mm)===i?'selected':''}>${faN(i)}</option>`).join('');
  const kindShow={date:[1,1,1,0,0],time:[0,0,0,1,1],datetime:[1,1,1,1,1]}[kind]||[1,1,1,0,0];
  ['.pk1','.pk2','.pk3','.pk4','.pk5'].forEach((c,i)=>{el.querySelector(c).style.display=kindShow[i]?'':'none'});
  el.querySelector('.pk2').addEventListener('change',()=>{const yy=unFa(el.querySelector('.pk1').value);
    const mm=el.querySelector('.pk2').value, cur=unFa(el.querySelector('.pk3').value);
    if(NR(cur)>daysOf(yy,mm)) el.querySelector('.pk3').value=faN(daysOf(yy,mm)); pickFill(el.querySelector('.pk3')?el:el);});
}
function pickVal(el){
  const g=c=>el.querySelector(c).value;
  const date=`${g('.pk1')}/${g('.pk2').padStart(2,'0')}/${g('.pk3').padStart(2,'0')}`;
  const time=`${g('.pk4')}:${g('.pk5')}`;
  return {date,time,full:el.dataset.pick==='time'?time:(el.dataset.pick==='date'?date:date+' — '+time)};
}
function initPickers(root){
  /* فقط انتخاب‌گرهای تاریخ و ساعت؛ استان/شهر و فهرست‌ها ساز خودشان را دارند */
  (root||document).querySelectorAll('.pick[data-pick]').forEach(el=>{
    if(el.dataset.ready) return;
    el.dataset.ready='1';
    pickFill(el);
  });
}
/* اجزای مرکب: استان و شهر، دانشگاه، شغل، تحصیلات */
function geoHTML(idPrefix,val){
  const p=(val&&val.p)||'تهران', c=(val&&val.c)||'تهران';
  return `<div class="pick geo" data-geo="${idPrefix}" data-p="${p}" data-c="${c}">
    <select class="input gp" aria-label="استان">${opts(EVENTKIT.provinces,p)}</select>
    <select class="input gc" aria-label="شهر">${opts(PROVINCES[p]||[],c)}</select></div>`;
}
function geoFill(el){
  el.querySelector('.gp').addEventListener('change',()=>{
    const p=el.querySelector('.gp').value;
    el.querySelector('.gc').innerHTML=opts(PROVINCES[p]||[],(PROVINCES[p]||[])[0]);
  });
}
function initGeo(root){(root||document).querySelectorAll('.geo').forEach(el=>{if(el.dataset.ready)return;el.dataset.ready='1';geoFill(el)})}
function listHTML(kind,val){
  const list=kind==='uni'?UNIS:kind==='job'?JOBS:EDU;
  const other=val&&!list.includes(val);
  return `<div class="pick list-pick" data-list="${kind}" data-val="${val||list[0]}">
    <select class="input lp" aria-label="فهرست">${opts(list,other?'سایر':val)}</select>
    <input class="input other" placeholder="بنویسید…" style="display:${other?'':'none'}" value="${other?val:''}"/>
  </div>`;
}
function initListPicks(root){(root||document).querySelectorAll('.pick[data-list]').forEach(el=>{
  if(el.dataset.ready)return;el.dataset.ready='1';
  el.querySelector('.lp').addEventListener('change',()=>{
    const o=el.querySelector('.other'); o.style.display=el.querySelector('.lp').value==='سایر'?'':'none';
    if(o.style.display!=='none') o.focus();
  });
  if(el.querySelector('.lp').value==='سایر') el.querySelector('.other').style.display='';
})}
function initAll(root){initPickers(root);initGeo(root);initListPicks(root)}

/* ── کیوآرکد: نقشهٔ واقعی‌نما از یک بذر ─────────────────────────────────── */
function qrSVG(seed,size){
  size=size||120;
  let s=0; String(seed).split('').forEach(ch=>s=(s*31+ch.charCodeAt(0))>>>0);
  const rnd=()=>((s=(s*1664525+1013904223)>>>0)/4294967296);
  const N=25, m=size/N;
  let cells='';
  const finder=(x,y)=>{let o='';
    for(let i=0;i<7;i++)for(let j=0;j<7;j++){
      const edge=(i===0||i===6||j===0||j===6), core=(i>=2&&i<=4&&j>=2&&j<=4);
      if(edge||core) o+=`<rect x="${(x+j)*m}" y="${(y+i)*m}" width="${m}" height="${m}" rx="${m*0.22}"/>`;
    } return o;};
  for(let y=0;y<N;y++)for(let x=0;x<N;x++){
    const inF=(x<8&&y<8)||(x>N-9&&y<8)||(x<8&&y>N-9);
    if(inF) continue;
    if(rnd()>0.52) cells+=`<rect x="${x*m}" y="${y*m}" width="${m}" height="${m}" rx="${m*0.22}"/>`;
  }
  return `<svg class="qr" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" role="img" aria-label="کیوآرکد">
    <rect width="${size}" height="${size}" rx="${size*0.08}" fill="#fff"/>
    <g fill="currentColor" transform="translate(${m*1.2},${m*1.2}) scale(${(size-m*2.4)/size})">
      ${cells}${finder(0,0)}${finder(N-7,0)}${finder(0,N-7)}
    </g></svg>`;
}

/* ── بلیت: یک نسخه، همه‌جا ─────────────────────────────────────────────── */
const TICKET_STYLES={classic:'کلاسیک',glass:'شیشه‌ای',gold:'طلایی',minimal:'مینیمال'};
const TICKET_PARTS={title:'عنوان رویداد',code:'کد پیگیری',name:'نام دارنده',date:'تاریخ و ساعت',venue:'نشانی',seat:'ردیف و صندلی',no:'شمارهٔ بلیت',qr:'کیوآرکد',logo:'نشان رویداد',note:'یادداشت ورود'};
function ticketHTML(o){
  const parts=o.parts||Object.keys(TICKET_PARTS);
  const has=k=>parts.includes(k);
  return `<article class="tk tk-${o.style||'classic'}" style="--tk:${o.color||'#0F6FD1'}">
    <header class="tk-head">
      ${has('logo')?'<span class="tk-logo"><svg class="i"><use href="#i-layers"/></svg></span>':''}
      <div style="min-width:0">
        ${has('title')?`<div class="tk-title">${o.title||'کارگاه فن بیان'}</div>`:''}
        <div class="tk-sub">${o.kind||'بلیت ورود'}</div>
      </div>
      <span class="sp"></span>
      <span class="tag ${o.confirmed?'ok':'warn'}">${o.confirmed?'قطعی':'موقت'}</span>
    </header>
    <div class="tk-rip"><span class="cut"></span><span class="perf"></span><span class="cut"></span></div>
    <div class="tk-body">
      <div class="tk-rows">
        ${has('name')?`<div class="r"><span>دارنده</span><b>${o.name||'—'}</b></div>`:''}
        ${has('code')?`<div class="r"><span>کد پیگیری</span><b class="num">${o.code||'—'}</b></div>`:''}
        ${has('no')?`<div class="r"><span>شمارهٔ بلیت</span><b class="num">${o.no||'—'}</b></div>`:''}
        ${has('date')?`<div class="r"><span>تاریخ و ساعت</span><b class="num">${o.date||'—'}</b></div>`:''}
        ${has('venue')?`<div class="r"><span>نشانی</span><b>${o.venue||'—'}</b></div>`:''}
        ${has('seat')?`<div class="r"><span>ردیف و صندلی</span><b class="num">${o.seat||'—'}</b></div>`:''}
      </div>
      ${has('qr')?`<div class="tk-qr">${qrSVG(o.code||'NORA',116)}<span class="tk-qrn">این کد را در ورودی نشان دهید</span></div>`:''}
    </div>
    ${has('note')?`<footer class="tk-foot">${o.noteText||'ورود با همین بلیت؛ همراه داشتن کارت شناسایی لازم است.'}</footer>`:''}
    <footer class="tk-actions">
      <button class="btn sm"><svg class="i"><use href="#i-download"/></svg> دانلود تصویر</button>
      <button class="btn sm quiet"><svg class="i"><use href="#i-calendar"/></svg> افزودن به تقویم</button>
      ${o.extra||''}
    </footer>
  </article>`;
}

/* ── ابزارهای رابط ─────────────────────────────────────────────────────── */
function toast(msg){
  const t=document.getElementById('toast'); if(!t) return;
  const last=t.lastChild; if(last&&last.nodeType===3) last.textContent=' '+msg; else t.appendChild(document.createTextNode(' '+msg));
  t.classList.add('on'); clearTimeout(window.__tt); window.__tt=setTimeout(()=>t.classList.remove('on'),1700);
}
function copyText(txt,after){
  const done=()=>{toast('کپی شد'); if(after) after();};
  try{navigator.clipboard.writeText(txt).then(done).catch(fb)}catch(e){fb()}
  function fb(){const t=document.createElement('textarea');t.value=txt;document.body.appendChild(t);t.select();
    try{document.execCommand('copy')}catch(e){}t.remove();done()}
}
function openSheet(id){closeSheets(); const el=document.getElementById(id); if(!el)return;
  document.getElementById('scrim').classList.add('on'); el.classList.add('on');
  initAll(el); el.scrollTop=0;}
function closeSheets(){document.querySelectorAll('.sheet').forEach(s=>s.classList.remove('on'));
  const s=document.getElementById('scrim'); if(s)s.classList.remove('on');}
function initUI(){
  /* ورقه‌ها، سوییچ، سگمنت، چیپ، درخشش، کپی */
  document.addEventListener('click',e=>{
    const op=e.target.closest('[data-sheet]'); if(op){openSheet(op.dataset.sheet);return}
    if(e.target.closest('[data-close]')||e.target.closest('.scrim')){closeSheets();return}
    const cp=e.target.closest('[data-copy]');
    if(cp){const el=cp.dataset.copy.startsWith('#')?document.querySelector(cp.dataset.copy):null;
      copyText(el?el.textContent.trim():cp.dataset.copy);return}
    const sw=e.target.closest('.switch'); if(sw){sw.classList.toggle('on');sw.setAttribute('aria-checked',sw.classList.contains('on'));return}
    const sg=e.target.closest('.seg button'); if(sg){[...sg.parentElement.children].forEach(x=>x.classList.remove('on'));sg.classList.add('on');return}
    const ch=e.target.closest('.chip[data-chip]'); if(ch) ch.classList.toggle('on');
  });
  document.addEventListener('pointermove',e=>{
    const s=e.target.closest('.sheen'); if(!s)return; const r=s.getBoundingClientRect();
    s.style.setProperty('--mx',((e.clientX-r.left)/r.width*100).toFixed(1)+'%');
    s.style.setProperty('--my',((e.clientY-r.top)/r.height*100).toFixed(1)+'%');
  });
  /* شب و روز */
  try{const th=localStorage.getItem('nora-theme'); if(th) document.documentElement.dataset.theme=th;
      else if(matchMedia('(prefers-color-scheme:dark)').matches) document.documentElement.dataset.theme='dark'}catch(e){}
  const t=document.getElementById('theme');
  if(t) t.onclick=()=>{const v=document.documentElement.dataset.theme==='dark'?'light':'dark';
    document.documentElement.dataset.theme=v; try{localStorage.setItem('nora-theme',v)}catch(e){}};
  initAll(document);
}
