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
/* مقدارها همیشه لاتین‌اند تا محاسبه دقیق بماند؛ نمایش، فارسی */
function opts(list,cur,label){return list.map(v=>`<option value="${unFa(v)}" ${String(unFa(v))===String(unFa(cur))?'selected':''}>${label?label(v):v}</option>`).join('');}
/* faDigits: فارسي‌سازی بدون دست‌خوردن صفر پیشتاز — faN برای عدد خالص */
const faDigits=s=>String(s).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);

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
  const v=unFa(el.dataset.val||'');
  const [datePart='',timePart='']=v.includes('—')?v.split('—').map(s=>s.trim()):[v.trim().split(' ')[0]||'',v.trim().split(' ')[1]||''];
  const dp=(datePart||'').split('/'), tp=(timePart||'').split(':');
  const y=NR(dp[0])||1405, m=NR(dp[1])||7, d=NR(dp[2])||1, hh=NR(tp[0])||0, mm=NR(tp[1])||0;
  const g=c=>el.querySelector(c);
  g('.pk1').innerHTML=opts(CAL.slice().reverse(),y,faN);
  g('.pk2').innerHTML=opts(Array.from({length:12},(_,i)=>i+1),m,i=>MONTHS[i-1]);
  g('.pk3').innerHTML=opts(Array.from({length:daysOf(y,m)},(_,i)=>i+1),Math.min(d,daysOf(y,m)),faN);
  g('.pk4').innerHTML=opts(Array.from({length:24},(_,i)=>i),hh,i=>faN(i));
  g('.pk5').innerHTML=opts([0,15,30,45],mm,i=>faDigits(String(i).padStart(2,'0')));
  const show={date:[1,1,1,0,0],time:[0,0,0,1,1],datetime:[1,1,1,1,1]}[kind]||[1,1,1,0,0];
  ['.pk1','.pk2','.pk3','.pk4','.pk5'].forEach((c,i)=>{g(c).style.display=show[i]?'':'none'});
  g('.pk1').addEventListener('change',()=>refillDays(el));
  g('.pk2').addEventListener('change',()=>refillDays(el));
}
/* با عوض شدن سال یا ماه، روزها دوباره ساخته می‌شوند (اسفند ۲۹/۳۰ روزه) */
function refillDays(el){
  const y=NR(unFa(el.querySelector('.pk1').value)), m=NR(unFa(el.querySelector('.pk2').value));
  const cur=NR(unFa(el.querySelector('.pk3').value))||1, dn=daysOf(y,m);
  el.querySelector('.pk3').innerHTML=opts(Array.from({length:dn},(_,i)=>i+1),Math.min(cur,dn),faN);
}
function pickVal(el){
  const g=c=>unFa(el.querySelector(c).value);
  const pad=n=>String(n).padStart(2,'0');
  const date=`${g('.pk1')}/${pad(g('.pk2'))}/${pad(g('.pk3'))}`;
  const time=`${pad(g('.pk4'))}:${pad(g('.pk5'))}`;
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

/* ── تقویم: جلالی ↔ میلادی ─────────────────────────────────────────────── */
const JAL_BREAKS=[-61,9,38,199,426,686,756,818,1111,1181,1210,1635,2060,2097,2192,2262,2324,2394,2456,3178];
const jdiv=(a,b)=>~~(a/b);
const jmod=(a,b)=>a-jdiv(a,b)*b;
function jalCal(jy){
  const bl=JAL_BREAKS.length, gy=jy+621;
  let leapJ=-14;
  let jp=JAL_BREAKS[0], jump=0;
  for(let i=1;i<bl;i++){const jm=JAL_BREAKS[i]; jump=jm-jp;
    if(jy<jm)break;
    leapJ+=jdiv(jump,33)*8+jdiv(jmod(jump,33),4); jp=jm;}
  let n=jy-jp, L=leapJ+jdiv(n,33)*8+jdiv(jmod(n,33)+3,4);
  if(jmod(jump,33)===4&&jump-n===4) L++;
  const leapG=jdiv(gy,4)-jdiv((jdiv(gy,100)+1)*3,4)-150;
  const march=20+L-leapG;
  if(jump-n<6) n=n-jump+jdiv(jump+4,33)*33;
  let leap=jmod(jmod(n+1,33)-1,4);
  if(leap===-1) leap=4;
  return {leap,march,gy};
}
const g2d=(gy,gm,gd)=>{let d=jdiv((gy+jdiv(gm-8,6)+100100)*1461,4)+jdiv(153*jmod(gm+9,12)+2,5)+gd-34840408;
  d=d-jdiv(jdiv(gy+100100+jdiv(gm-8,6),100)*3,4)+752; return d;};
const d2g=jdn=>{
  let j=4*jdn+139361631; j=j+jdiv(jdiv(4*jdn+183187720,146097)*3,4)*4-3908;
  const i=jdiv(jmod(j,1461),4)*5+308, gd=jdiv(jmod(i,153),5)+1, gm=jmod(jdiv(i,153),12)+1;
  return {gy:jdiv(j,1461)-100100+jdiv(8-gm,6),gm,gd};};
const j2d=(jy,jm,jd)=>{const r=jalCal(jy); return g2d(r.gy,3,r.march)+(jm-1)*31-jdiv(jm,7)*(jm-7)+jd-1;};
const d2j=jdn=>{
  const g=d2g(jdn), jy=g.gy-621, gy=g.gy;
  let r=jalCal(jy), jdn1f=g2d(gy,3,r.march), jm, jd, k=jdn-jdn1f;
  if(k>=0){if(k<=185){jm=1+jdiv(k,31); jd=jmod(k,31)+1; return {jy,jm,jd};} k-=186;}
  else{jy--; k+=179; if(r.leap===1)k++;}
  jm=7+jdiv(k,30); jd=jmod(k,30)+1; return {jy,jm,jd};};
const gregOf=(jy,jm,jd)=>d2g(j2d(jy,jm,jd));
const jalaliOf=(gy,gm,gd)=>d2j(g2d(gy,gm,gd));
const WD=['یکشنبه','دوشنبه','سه‌شنبه','چهارشنبه','پنجشنبه','جمعه','شنبه'];
const weekdayOf=(jy,jm,jd)=>{const g=gregOf(jy,jm,jd); return WD[new Date(Date.UTC(g.gy,g.gm-1,g.gd)).getUTCDay()];};
const isLeapJ=jy=>jalCal(jy).leap===0;
const daysInJ=(jy,jm)=>jm===12?(isLeapJ(jy)?30:29):(jm<=6?31:30);
/* تاریخ جلالی به شکل خواندنی: «جمعه ۸ مهر» */
const faJDate=(jy,jm,jd)=>`${weekdayOf(jy,jm,jd)} ${faN(jd)} ${MONTHS[jm-1]}`;
/* از رشتهٔ «۱۴۰۵/۰۷/۰۸ — ۱۶:۰۰» یا «1405/07/08 16:00» به اجزا */
function parseJ(s){
  const t=unFa(String(s||'')).replace(/[—–-]/g,' ');
  const d=(t.match(/(\d{4})\s*\/\s*(\d{1,2})\s*\/\s*(\d{1,2})/)||[]).slice(1).map(NR);
  const h=(t.match(/(\d{1,2})\s*:\s*(\d{2})/)||[]).slice(1).map(NR);
  if(d.length!==3) return null;
  return {jy:d[0],jm:d[1],jd:d[2],hh:h[0]||0,mm:h[1]||0};
}
const fmtClock=(hh,mm)=>faN(hh)+':'+faDigits(String(mm).padStart(2,'0'));
/* خط زیر عنوان بلیت: «جمعه ۸ مهر · ساعت ۱۶:۰۰ · تهران، ولی‌عصر» */
function ticketMeta(dateStr,venue){
  const p=parseJ(dateStr); const bits=[];
  if(p) bits.push(faJDate(p.jy,p.jm,p.jd));
  if(p&&(dateStr+'').match(/:/)) bits.push('ساعت '+fmtClock(p.hh,p.mm));
  if(venue) bits.push(venue);
  return bits.join(' · ');
}
const nowFa=()=>{const g=new Date(), j=jalaliOf(g.getFullYear(),g.getMonth()+1,g.getDate());
  return faJDate(j.jy,j.jm,j.jd)+' — '+fmtClock(g.getHours(),g.getMinutes());};
/* پوشاندن بخشی از شمارهٔ موبایل در فهرست‌ها (حریم خصوصی) */
const maskPhone=s=>{const d=unFa(String(s||'')); return d.length===11?d.replace(/^(\d{4})\d{3}(\d{4})$/,(m,a,b)=>faDigits(a)+'***'+faDigits(b)):d;};

/* ── کیوآرکد واقعی: حالت بایت، سطح M/L، نسخهٔ ۱ تا ۵ ───────────────────── */
const QRCODE=(function(){
  const EXP=new Array(512), LOG=new Array(256);
  (function(){let x=1;for(let i=0;i<255;i++){EXP[i]=x;LOG[x]=i;x<<=1;if(x&0x100)x^=0x11D;}
    for(let i=255;i<512;i++)EXP[i]=EXP[i-255];})();
  const mul=(a,b)=>(a===0||b===0)?0:EXP[LOG[a]+LOG[b]];
  function rsGen(n){let g=[1];
    for(let i=0;i<n;i++){const ng=new Array(g.length+1).fill(0);
      for(let k=0;k<g.length;k++){ng[k]^=g[k]; ng[k+1]^=mul(g[k],EXP[i]);}
      g=ng;}
    return g;}
  function rsEnc(data,n){
    const g=rsGen(n), res=new Array(n).fill(0);
    for(const byte of data){
      const f=byte^res[0];
      res.shift(); res.push(0);
      if(f) for(let i=0;i<n;i++) res[i]^=mul(g[i+1],f);
    }
    return res;}
  const CAP={M:{1:16,2:28,3:44},L:{1:19,2:34,3:55,4:80,5:108}};
  const ECW={M:{1:10,2:16,3:26},L:{1:7,2:10,3:15,4:20,5:26}};
  const LEVELBIT={L:1,M:0};
  function utf8(s){
    const out=[];
    for(const ch of String(s)){
      const c=ch.codePointAt(0);
      if(c<0x80) out.push(c);
      else if(c<0x800) out.push(0xC0|c>>6, 0x80|c&63);
      else if(c<0x10000) out.push(0xE0|c>>12, 0x80|(c>>6)&63, 0x80|c&63);
      else out.push(0xF0|c>>18, 0x80|(c>>12)&63, 0x80|(c>>6)&63, 0x80|c&63);
    }
    return out;}
  function choose(len){
    for(const v of [1,2,3,4,5]) for(const l of ['M','L'])
      if(CAP[l][v]&&len+2<=CAP[l][v]) return {v,l};
    return null;}
  function make(text){
    const bytes=utf8(text), pick=choose(bytes.length);
    if(!pick) return null;
    const {v,l}=pick, cap=CAP[l][v], total=cap*8;
    const bits=[];
    const put=(val,len)=>{for(let i=len-1;i>=0;i--) bits.push((val>>i)&1);};
    put(4,4); put(bytes.length,8); for(const b of bytes) put(b,8);
    for(let i=0;i<4&&bits.length<total;i++) bits.push(0);
    while(bits.length%8) bits.push(0);
    const data=[];
    for(let i=0;i<bits.length;i+=8){let val=0;for(let j=0;j<8;j++) val=(val<<1)|bits[i+j]; data.push(val);}
    let pad=0; while(data.length<cap) data.push([0xEC,0x11][pad++%2]);
    const all=data.concat(rsEnc(data,ECW[l][v]));
    const size=v*4+17;
    const m=Array.from({length:size},()=>new Array(size).fill(null));
    const set=(r,c,val)=>{if(r>=0&&c>=0&&r<size&&c<size) m[r][c]=val?1:0;};
    const finder=(r0,c0)=>{for(let r=-1;r<=7;r++)for(let c=-1;c<=7;c++){
      const rr=r0+r, cc=c0+c; if(rr<0||cc<0||rr>=size||cc>=size) continue;
      const inside=r>=0&&r<=6&&c>=0&&c<=6;
      const dark=inside&&(r===0||r===6||c===0||c===6||(r>=2&&r<=4&&c>=2&&c<=4));
      set(rr,cc,inside&&dark);}};
    finder(0,0); finder(size-7,0); finder(0,size-7);
    for(let i=8;i<size-8;i++){if(m[6][i]===null) set(6,i,i%2===0); if(m[i][6]===null) set(i,6,i%2===0);}
    if(v>1) for(const r of [6,size-7]) for(const c of [6,size-7]){
      if(m[r][c]!==null) continue;
      for(let dr=-2;dr<=2;dr++) for(let dc=-2;dc<=2;dc++)
        set(r+dr,c+dc,Math.max(Math.abs(dr),Math.abs(dc))!==1);}
    set(size-8,8,1);                                   /* ماژول تیره */
    for(let i=0;i<=8;i++){if(m[8][i]===null) m[8][i]=0; if(m[i][8]===null) m[i][8]=0;}
    for(let i=0;i<8;i++){if(m[8][size-1-i]===null) m[8][size-1-i]=0; if(m[size-1-i][8]===null) m[size-1-i][8]=0;}
    let bit=0; const totalBits=all.length*8;
    let row=size-1, dir=-1;
    for(let col=size-1;col>0;col-=2){
      if(col===6) col--;
      for(;;){
        for(let i=0;i<2;i++){
          const c=col-i;
          if(m[row][c]===null){
            let val=0;
            if(bit<totalBits){val=(all[bit>>3]>>(7-(bit&7)))&1; bit++;}
            if((row+c)%2===0) val^=1;                  /* ماسک ۰ */
            m[row][c]=val?1:0;
          }
        }
        row+=dir;
        if(row<0||row>=size){row-=dir; dir=-dir; break;}
      }
    }
    /* اطلاعات قالب: ۵ بیت + BCH(15,5)، سپس XOR با ۰x5412 */
    const fmt=(LEVELBIT[l]<<3)|0;
    let dv=fmt<<10;
    for(let i=14;i>=10;i--) if((dv>>i)&1) dv^=0x537<<(i-10);
    const code=(((fmt<<10)|dv)^0x5412)&0x7FFF;
    /* ترتیب بیت‌ها از پرارزش به کم‌ارزش روی همان خانه‌های استاندارد */
    const gb2=i=>(code>>(14-i))&1;
    for(let i=0;i<=5;i++) m[8][i]=gb2(i);
    m[8][7]=gb2(6); m[8][8]=gb2(7); m[7][8]=gb2(8);
    for(let i=9;i<=14;i++) m[14-i][8]=gb2(i);
    for(let i=0;i<=6;i++) m[size-1-i][8]=gb2(i);
    for(let i=7;i<=14;i++) m[8][size-15+i]=gb2(i);
    m[size-8][8]=1;
    return {matrix:m,size,version:v,level:l};
  }
  return {make,utf8};
})();
function qrMatrix(text){const r=QRCODE.make(text); return r?r.matrix:null;}
/* نقشهٔ کیوآر به تصویر؛ حاشیهٔ سفید چهار ماژول داخل خود تصویر می‌ماند */
function qrSVG(text,size,opts){
  size=size||132; opts=opts||{};
  const made=QRCODE.make(text);
  if(!made) return '';
  const {matrix,size:n}=made, quiet=4, total=n+quiet*2, unit=size/total;
  let cells='';
  for(let r=0;r<n;r++) for(let c=0;c<n;c++)
    if(matrix[r][c]) cells+=`<rect x="${((c+quiet)*unit).toFixed(2)}" y="${((r+quiet)*unit).toFixed(2)}" width="${unit.toFixed(2)}" height="${unit.toFixed(2)}"/>`;
  return `<svg class="qr" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" role="img" aria-label="کیوآرکد ${opts.label||''}">
    <rect width="${size}" height="${size}" rx="${(size*0.06).toFixed(1)}" fill="#fff"/>
    <g fill="#0B0B0B">${cells}</g></svg>`;
}

/* هر متن کاربر پیش از نشستن در HTML پاک می‌شود؛ نام و یادداشت را خودِ کاربر می‌نویسد */
const esc=s=>String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const escAttr=s=>String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
/* چاپ تک‌قطعه: بلیت یا رسید را به ناحیهٔ چاپ می‌برد و بقیهٔ صفحه را کنار می‌گذارد */
function printNode(el){
  if(!el) return;
  if(el.length&&el.length>1){                     /* چند بلیت با هم */
    let zone=document.getElementById('printzone');
    if(!zone){zone=document.createElement('div'); zone.id='printzone'; document.body.appendChild(zone);}
    zone.innerHTML='';
    [...el].forEach(n=>{const c=n.cloneNode(true); c.querySelectorAll('.tk-acts,.rc-acts').forEach(x=>x.remove()); zone.appendChild(c);});
    const done=()=>{zone.innerHTML=''; window.removeEventListener('afterprint',done);};
    window.addEventListener('afterprint',done);
    try{window.print();}catch(e){}
    setTimeout(done,1500);
    return;
  }
  let zone=document.getElementById('printzone');
  if(!zone){zone=document.createElement('div'); zone.id='printzone'; document.body.appendChild(zone);}
  zone.innerHTML='';
  const clone=el.cloneNode(true);
  clone.querySelectorAll('.tk-acts,.rc-acts').forEach(n=>n.remove());
  zone.appendChild(clone);
  const done=()=>{zone.innerHTML=''; window.removeEventListener('afterprint',done);};
  window.addEventListener('afterprint',done);
  try{window.print();}catch(e){}
  setTimeout(done,1200);
}
/* ── بلیت: یک خانواده، پنج پوسته ───────────────────────────────────────── */
const TICKET_STYLES={clear:'شفاف',forest:'جنگلی',gold:'طلایی',ocean:'اقیانوسی',night:'شب'};
const TICKET_PARTS={title:'عنوان رویداد',code:'کد بلیت',name:'نام دارنده',date:'تاریخ و ساعت',
  venue:'نشانی',seat:'ردیف و صندلی',no:'شمارهٔ بلیت',qr:'کیوآرکد',logo:'نشان خط زندگی',note:'یادداشت ورود'};
/* کد کوتاه بلیت به سبک «T4K7M9X» — از خودِ کد پیگیری ساخته می‌شود */
const TICKET_ALPHABET='23456789ACDEFGHJKLMNPQRSTUVWXYZ';
function shortCode(seed){
  let s=2166136261;
  for(const ch of String(seed)){s^=ch.charCodeAt(0); s=Math.imul(s,16777619)>>>0;}
  let out='';
  for(let i=0;i<7;i++){s=(Math.imul(s,1664525)+1013904223)>>>0; out+=TICKET_ALPHABET[s%TICKET_ALPHABET.length];}
  return out;
}
/* نشانی تأیید: در نسخهٔ واقعی امضا از سمت سرور می‌آید و یک‌بارمصرف است */
function ticketPayload(o){return `${o.verify||'https://lifeline1.ir/t'}/${o.short||shortCode(o.code||'')}`;}
function ticketHTML(o){
  const parts=o.parts||Object.keys(TICKET_PARTS);
  const has=k=>parts.includes(k);
  const skin=TICKET_STYLES[o.style]?o.style:'clear';
  const short=o.short||shortCode(o.code||o.name||'NORA');
  const meta=ticketMeta(o.date,o.venue);
  const side=[has('seat')?['ردیف و صندلی',o.seat]:null, has('no')?['شمارهٔ بلیت',o.no]:null].filter(Boolean);
  const stubInside=has('qr')?qrSVG(ticketPayload({...o,short}),122,{label:short}):'';
  return `<figure class="tk tk-${skin}" style="${o.color?`--tk-wash:${o.color};`:''}">
    <div class="tk-main">
      ${has('logo')?`<header class="tk-head"><span class="tk-brand"><svg viewBox="0 0 24 24" aria-hidden="true" class="tk-pulse"><path d="M2.6 12h3.2l2-5.2 3.2 10.4 2.6-5.2h7.8"/></svg> خط زندگی</span>
        <span class="tk-kind">${esc(o.kind||'بلیت ورود')}</span></header>`:''}
      ${has('title')?`<h3 class="tk-title">${esc(o.title||'کارگاه')}</h3>`:''}
      ${meta?`<p class="tk-meta">${esc(meta)}</p>`:''}
      <div class="tk-bottom">
        ${has('name')?`<div class="tk-who"><span class="k">شرکت‌کننده</span><b>${esc(o.name||'—')}</b></div>`:''}
        <span class="sp"></span>
        ${side.length?`<div class="tk-side">${side.map(([k,v])=>`<div><span class="k">${k}</span><b class="num">${esc(v||'—')}</b></div>`).join('')}</div>`:''}
      </div>
      ${has('note')?`<p class="tk-note">${esc(o.noteText||'ورود با همین بلیت؛ همراه داشتن کارت شناسایی لازم است.')}</p>`:''}
    </div>
    <div class="tk-perf" aria-hidden="true"><i class="cut top"></i><i class="dash"></i><i class="cut bottom"></i></div>
    <div class="tk-stub">
      ${stubInside}
      ${has('code')?`<div class="tk-code"><span class="k">کد بلیت</span><b>${esc(o.displayCode||short)}</b></div>`:''}
      <span class="tk-state ${o.confirmed?'ok':'wait'}">${o.confirmed?'قطعی':'موقت'}</span>
    </div>
    <div class="tk-acts no-print">
      <button class="btn sm" data-tkprint><svg class="i"><use href="#i-print"/></svg> چاپ</button>
      <button class="btn sm quiet" data-tkics="${escAttr(JSON.stringify({code:o.code||'',date:o.date||'',title:o.title||'',venue:o.venue||'',short:short}))}"><svg class="i"><use href="#i-calendar"/></svg> افزودن به تقویم</button>
      <button class="btn sm quiet" data-copy="${o.displayCode||short}"><svg class="i"><use href="#i-copy"/></svg> کپی کد</button>
      ${o.extra||''}
    </div>
  </figure>`;
}

/* ── رسید پرداخت: همان زبان، مبلغ قهرمان ──────────────────────────────── */
function receiptHTML(o){
  o=o||{};
  const rows=[
    ['برنامه',o.program],['زمان برنامه',o.when],['پرداخت‌کننده',o.payer],
    ['روش',o.method],['تاریخ',o.at],['بلیت',o.ticket]
  ].filter(([,v])=>v);
  const state=o.state||'ok';
  const pill={ok:'پرداخت شد',wait:'در انتظار تأیید',stop:'پرداخت نشد'}[state];
  return `<article class="rc">
    <header class="rc-head">
      <span class="rc-brand"><svg viewBox="0 0 24 24" aria-hidden="true" class="tk-pulse"><path d="M2.6 12h3.2l2-5.2 3.2 10.4 2.6-5.2h7.8"/></svg> خط زندگی</span>
      <span class="sp"></span>
      <span class="rc-pill rc-${state}"><span class="dot"></span> ${pill}</span>
    </header>
    <h3 class="rc-title">رسید پرداخت</h3>
    <div class="rc-amount">
      <span class="n num">${fa(o.amount||0)}</span><span class="u">ریال</span>
      ${o.discount?`<span class="rc-off">تخفیف ${rialTxt(o.discount)}</span>`:''}
    </div>
    <div class="rc-words">${tomanTxt(o.amount||0)}</div>
    <div class="rc-rows">
      ${rows.map(([k,v])=>`<div class="answer"><span class="k">${esc(k)}</span><span class="v ${/^[0-9۰-۹]/.test(v)?'num':''}">${esc(v)}</span></div>`).join('')}
    </div>
    <div class="rc-foot">
      <div class="rc-qr">${qrSVG(o.payload||('receipt:'+(o.track||''))||'receipt',116,{label:'رسید'})}</div>
      <div class="rc-track"><span class="k">کد پیگیری</span><b class="num">${esc(o.track||'—')}</b></div>
    </div>
    <p class="rc-note">صدور الکترونیکی؛ بدون مهر و امضا معتبر است.</p>
    <div class="rc-acts no-print">
      <button class="btn sm" data-tkprint><svg class="i"><use href="#i-print"/></svg> چاپ رسید</button>
      <button class="btn sm quiet" data-copy="${o.track||''}"><svg class="i"><use href="#i-copy"/></svg> کپی کد پیگیری</button>
      ${o.extra||''}
    </div>
  </article>`;
}

/* ── تقویم: فایل ics واقعی برای بلیت ──────────────────────────────────── */
function icsFor(o){
  const p=parseJ(o.date); if(!p) return '';
  const g=gregOf(p.jy,p.jm,p.jd);
  const pad=n=>String(n).padStart(2,'0');
  const stamp=`${g.gy}${pad(g.gm)}${pad(g.gd)}T${pad(p.hh)}${pad(p.mm)}00`;
  const end=new Date(Date.UTC(g.gy,g.gm-1,g.gd,p.hh,p.mm+120));
  const stampEnd=`${end.getUTCFullYear()}${pad(end.getUTCMonth()+1)}${pad(end.getUTCDate())}T${pad(end.getUTCHours())}${pad(end.getUTCMinutes())}00`;
  const esc=s=>String(s||'').replace(/([,;\\])/g,'\\$1').replace(/\n/g,'\\n');
  return ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Nora//Ticket//FA','CALSCALE:GREGORIAN','BEGIN:VEVENT',
    `UID:${o.code||'nora'}@lifeline1.ir`,`DTSTAMP:${stamp}Z`,`DTSTART;TZID=Asia/Tehran:${stamp}`,`DTEND;TZID=Asia/Tehran:${stampEnd}`,
    `SUMMARY:${esc(o.title||'رویداد')}`,`LOCATION:${esc(o.venue||'')}`,`DESCRIPTION:${esc('کد بلیت: '+(o.short||shortCode(o.code||'')))}`,
    'END:VEVENT','END:VCALENDAR'].join('\r\n');
}
function download(name,text,mime){
  try{
    const blob=new Blob([text],{type:mime||'text/plain;charset=utf-8'});
    const url=URL.createObjectURL(blob), a=document.createElement('a');
    a.href=url; a.download=name; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),3000);
    return true;
  }catch(e){toast('ساخت فایل ممکن نشد'); return false;}
}

/* با صفحه‌کلید هم باید کار کند: هر نقش دکمه‌ای با Enter و فاصله فعال می‌شود */
function initKeys(root){
  const host=root||document;
  if(host.__keys) return; host.__keys=1;
  host.addEventListener('keydown',e=>{
    if(e.key!=='Enter'&&e.key!==' ') return;
    const el=e.target.closest('[role="button"],[data-chip],[data-fin],[data-method],[data-color],[data-tk],[data-pick]');
    if(!el||el.tagName==='BUTTON'||el.tagName==='INPUT'||el.tagName==='SELECT') return;
    e.preventDefault(); el.click();
  });
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
  initKeys(document);
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
    const pa=e.target.closest('[data-printall]');
    if(pa){const nodes=document.querySelectorAll(pa.dataset.printall||'.tk');
      if(!nodes.length){toast('چیزی برای چاپ نیست');return}
      printNode(nodes); return}
    const pr=e.target.closest('[data-tkprint]');
    if(pr){printNode(pr.closest('.tk')||pr.closest('.rc'));return}
    const ic=e.target.closest('[data-tkics]');
    if(ic){let o={}; try{o=JSON.parse(ic.dataset.tkics||'{}')}catch(err){}
      const ics=icsFor(o); if(ics) download('nora-ticket.ics',ics,'text/calendar;charset=utf-8'); return}
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

/* برای آزمون در محیط نود؛ در مرورگر نادیده می‌ماند */
if(typeof module!=='undefined'&&module.exports) module.exports={esc,initKeys,escAttr,printNode,qrMatrix,qrSVG,QRCODE,ticketHTML,receiptHTML,
  shortCode,ticketMeta,icsFor,parseJ,jalaliOf,gregOf,isLeapJ,daysInJ,weekdayOf,maskPhone,words,money,faN,fa};
