/* ══════════════════════════════════════════════════════════════════════════
   نورا، موتور مشترک صفحه‌ها
   هر چیزی که در بیش از یک صفحه لازم است، همین‌جا نوشته می‌شود:
   اعداد و حروف، انتخاب‌گرها، داده‌های ایران، کیوآرکد، و ابزارهای رابط.
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
/* قاعده: عدد به ریال، تومان به حروف */
const rialTxt=n=>fa(n)+' ریال';
const tomanTxt=n=>words(n/10)+' تومان';
const money=n=>rialTxt(n)+' · '+tomanTxt(n);

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
/* faDigits: فارسي‌سازی بدون دست‌خوردن صفر پیشتاز، faN برای عدد خالص */
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
  return {date,time,full:el.dataset.pick==='time'?time:(el.dataset.pick==='date'?date:date+' ساعت '+time)};
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
/* از رشتهٔ «۱۴۰۵/۰۷/۰۸، ۱۶:۰۰» یا «1405/07/08 16:00» به اجزا */
function parseJ(s){
  const t=unFa(String(s||'')).replace(/[—–-]/g,' ');
  const d=(t.match(/(\d{4})\s*\/\s*(\d{1,2})\s*\/\s*(\d{1,2})/)||[]).slice(1).map(NR);
  const h=(t.match(/(\d{1,2})\s*:\s*(\d{2})/)||[]).slice(1).map(NR);
  if(d.length!==3) return null;
  return {jy:d[0],jm:d[1],jd:d[2],hh:h[0]||0,mm:h[1]||0};
}
const fmtClock=(hh,mm)=>faDigits(String(hh).padStart(2,'0'))+':'+faDigits(String(mm).padStart(2,'0'));
/* خط تاریخ و محل رویداد (روی برگ گواهینامه و جزئیات پنل) */
function ticketMeta(dateStr,venue){
  const p=parseJ(dateStr); const bits=[];
  if(p) bits.push(faJDate(p.jy,p.jm,p.jd));
  if(p&&(dateStr+'').match(/:/)) bits.push('ساعت '+fmtClock(p.hh,p.mm));
  if(venue) bits.push(venue);
  return bits.join(' · ');
}
const nowFa=()=>{const g=new Date(), j=jalaliOf(g.getFullYear(),g.getMonth()+1,g.getDate());
  return faJDate(j.jy,j.jm,j.jd)+'، ساعت '+fmtClock(g.getHours(),g.getMinutes());};
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
/* ── فونت گواهینامه: فقط در تصویر مستقل داخل خودش جاسازی می‌شود ── */
/* فونت گواهینامه اگر آمده باشد (cert-font.js) استفاده می‌شود؛ وگرنه پوستهٔ نازک */
var TK_FACE_R=(typeof window!=='undefined'&&window.TK_FACE_R)||'';
var TK_FACE_B=(typeof window!=='undefined'&&window.TK_FACE_B)||'';
var TK_FACE_LR=(typeof window!=='undefined'&&window.TK_FACE_LR)||'';
var TK_FACE_LB=(typeof window!=='undefined'&&window.TK_FACE_LB)||'';
/* فونت «FD» رقم‌ها را فارسی‌شکل می‌کند؛ برای شناسهٔ لاتین یک فونت جدا داریم */
const TK_CSS=[['Vazirmatn UI FD',400,TK_FACE_R],['Vazirmatn UI FD',700,TK_FACE_B],
  ['Nora Latin',400,TK_FACE_LR],['Nora Latin',700,TK_FACE_LB]]
  .filter(f=>f[2]).map(f=>`@font-face{font-family:'${f[0]}';font-weight:${f[1]};src:url(data:font/woff2;base64,${f[2]}) format('woff2')}`).join('\n');
const TK_FONTS="'Vazirmatn UI FD',Vazirmatn,system-ui,Tahoma,sans-serif";
const TK_FONTS_LAT="'Nora Latin','Vazirmatn UI FD',Vazirmatn,system-ui,Tahoma,sans-serif";

/* ══════════════════════════════════════════════════════════════════════════
   برگ گواهینامه، یک SVG مستقل، شیشه‌ای و آمادهٔ چاپ
   ══════════════════════════════════════════════════════════════════════════ */

/* پوسته‌ها: گرادیان کارت از چپ (ته‌برگ) به راست (متن)، نمونه‌برداری‌شده از مرجع */

/* اندازهٔ قلم را می‌رساند که متن از لبه بیرون نزند */
function tkFit(text, size, maxW, minSize) {
  const k = /^[A-Za-z0-9]/.test(String(text || '')) ? .58 : .54;
  let s = size;
  while (s > minSize && String(text || '').length * s * k > maxW) s -= .5;
  return s;
}
const tkEsc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/* ── کیوآرکد واقعی روی کارت سفید ───────────────────────────────────────── */

function tkQR(host, text, x, y, size, dark, uid) {
  const made = QRCODE.make(text);
  if(!made) return '';
  const m = made.matrix, n = made.size, cell = size / n;
  let cells = '';
  for (let r = 0; r < n; r++)
    for (let c = 0; c < n; c++)
      if (m[r][c])
        cells += `<rect x="${(x + c * cell).toFixed(2)}" y="${(y + r * cell).toFixed(2)}" width="${cell.toFixed(2)}" height="${cell.toFixed(2)}"/>`;
  return `<g class="tkqr"${uid ? ` id="${uid}"` : ''} fill="${dark || '#101D19'}">${cells}</g>`;
}

const TICKET_ALPHABET='23456789ACDEFGHJKLMNPQRSTUVWXYZ';
function shortCode(seed){
  let s=2166136261;
  for(const ch of String(seed)){s^=ch.charCodeAt(0); s=Math.imul(s,16777619)>>>0;}
  let out='';
  for(let i=0;i<7;i++){s=(Math.imul(s,1664525)+1013904223)>>>0; out+=TICKET_ALPHABET[s%TICKET_ALPHABET.length];}
  return out;
}


const CERT_G={size:[1100,780],card:[36,36,1064,744]};
function certificateSVG(o,opt){
  o=o||{}; opt=opt||{};
  const [W,H]=CERT_G.size, [cx0,cy0,cx1,cy1]=CERT_G.card;
  const RTL=' direction="rtl"';
  const ink='#12201B', muted='#6E7A75', brand='#0071E3', gold='#9C7C3C';   /* کنش آبی اپل، طلا برای مهر */
  const name=o.name||'نام و نام خانوادگی';
  const kind=o.kind||'گواهینامهٔ پایان دوره';
  const title=o.title||'کارگاه';
  const date=o.date||'';
  const code=o.code||'';
  const short=o.short||shortCode(code||'');
  const serial=o.serial||'NL-'+short;
  const hours=o.hours||'';
  const fit=(t,size,maxW,min)=>{let x=size; const k=/^[A-Za-z0-9]/.test(String(t))?.58:.54;
    while(x>min && String(t).length*x*k>maxW) x-=.5; return x.toFixed(1)};
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" style="font-family:${TK_FONTS}"
    aria-label="گواهینامهٔ ${tkEsc(title)} برای ${tkEsc(name)}">
  <defs>
    <linearGradient id="certbg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#F4F8F6"/><stop offset=".45" stop-color="#EAF1EE"/><stop offset="1" stop-color="#E3EDE9"/>
    </linearGradient>
    <linearGradient id="certline" x1="1" y1="0" x2="0" y2="0">
      <stop offset="0" stop-color="${brand}" stop-opacity=".55"/><stop offset=".5" stop-color="${gold}" stop-opacity=".45"/>
      <stop offset="1" stop-color="${brand}" stop-opacity=".55"/>
    </linearGradient>
    <radialGradient id="certhalo" cx=".5" cy=".3" r=".7">
      <stop offset="0" stop-color="#FFFFFF" stop-opacity=".85"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="certclip"><rect x="${cx0}" y="${cy0}" width="${cx1-cx0}" height="${cy1-cy0}" rx="40"/></clipPath>
    ${opt.embed?`<style>${TK_CSS}</style>`:''}
  </defs>
  <rect x="0" y="0" width="${W}" height="${H}" fill="#E9EFEC"/>
  <g clip-path="url(#certclip)">
    <rect x="${cx0}" y="${cy0}" width="${cx1-cx0}" height="${cy1-cy0}" fill="url(#certbg)"/>
    <rect x="${cx0}" y="${cy0}" width="${cx1-cx0}" height="${cy1-cy0}" fill="url(#certhalo)"/>
    <rect x="${cx0+22}" y="${cy0+22}" width="${cx1-cx0-44}" height="${cy1-cy0-44}" rx="26" fill="none" stroke="url(#certline)" stroke-width="2"/>
    <rect x="${cx0+34}" y="${cy0+34}" width="${cx1-cx0-68}" height="${cy1-cy0-68}" rx="20" fill="none" stroke="${brand}" stroke-opacity=".18" stroke-width="1"/>
  </g>
  <circle cx="${cx0+92}" cy="${cy0+92}" r="26" fill="${brand}" fill-opacity=".10"/>
  <text x="${cx0+92}" y="${cy0+100}" text-anchor="middle" font-size="19" font-weight="700" fill="${brand}"${RTL}>خ</text>
  <text x="${cx1-92}" y="${cy0+88}" text-anchor="end" font-size="17" font-weight="700" fill="${brand}"${RTL}>مؤسسهٔ خط زندگی</text>
  <text x="${cx1-92}" y="${cy0+112}" text-anchor="end" font-size="13.5" fill="${muted}"${RTL}>گروه فرهنگی و اجتماعی</text>
  <text x="${(cx0+cx1)/2}" y="${cy0+176}" text-anchor="middle" font-size="15" font-weight="600" letter-spacing=".4" fill="${gold}"${RTL}>${tkEsc(kind)}</text>
  <text x="${(cx0+cx1)/2}" y="${cy0+248}" text-anchor="middle" font-size="${fit(title,40,860,24)}" font-weight="700" fill="${ink}" letter-spacing="-.3"${RTL}>${tkEsc(title)}</text>
  <rect x="${(cx0+cx1)/2-70}" y="${cy0+270}" width="140" height="3" rx="1.5" fill="url(#certline)"/>
  <text x="${(cx0+cx1)/2}" y="${cy0+322}" text-anchor="middle" font-size="16" fill="${muted}"${RTL}>این گواهینامه به پاس شرکت و تکمیل دوره به نام زیر صادر شده است</text>
  <text x="${(cx0+cx1)/2}" y="${cy0+408}" text-anchor="middle" font-size="${fit(name,52,760,30)}" font-weight="700" fill="${brand}"${RTL}>${tkEsc(name)}</text>
  <text x="${(cx0+cx1)/2}" y="${cy0+446}" text-anchor="middle" font-size="14.5" fill="${muted}"${RTL}>${tkEsc([date,hours?('به مدت '+hours):''].filter(Boolean).join(' · '))}</text>
  <line x1="${cx0+120}" y1="${cy0+560}" x2="${cx0+400}" y2="${cy0+560}" stroke="${muted}" stroke-opacity=".45" stroke-width="1"/>
  <text x="${cx0+260}" y="${cy0+588}" text-anchor="middle" font-size="13.5" fill="${muted}"${RTL}>مهر و امضای مؤسسه</text>
  <line x1="${cx1-400}" y1="${cy0+560}" x2="${cx1-120}" y2="${cy0+560}" stroke="${muted}" stroke-opacity=".45" stroke-width="1"/>
  <text x="${cx1-260}" y="${cy0+588}" text-anchor="middle" font-size="13.5" fill="${muted}"${RTL}>کارشناس آموزش</text>
  ${o.qr===false?'':tkQR(null,o.payload||('https://lifeline1.ir/c/'+short),(cx0+cx1)/2-48,cy0+588,96,null,'cert-qr')}
  <text x="${(cx0+cx1)/2}" y="${cy0+736}" text-anchor="middle" font-size="12.5" fill="${muted}"${RTL}>صحت این گواهینامه با شمارهٔ ${tkEsc(serial)} در lifeline1.ir/c بررسی می‌شود</text>
</svg>`;
}
function certificateFile(o){return certificateSVG(o,{embed:true});}

function initKeys(root){
  const host=root||document;
  if(host.__keys) return; host.__keys=1;
  host.addEventListener('keydown',e=>{
    if(e.key!=='Enter'&&e.key!==' ') return;
    const el=e.target.closest('[role="button"],[data-chip],[data-fin],[data-method] ,[data-color],[data-pick]');
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
function copyText(txt,after,msg){
  const done=()=>{toast(msg||'کپی شد'); if(after) after();};
  try{navigator.clipboard.writeText(txt).then(done).catch(fb)}catch(e){fb()}
  function fb(){const t=document.createElement('textarea');t.value=txt;document.body.appendChild(t);t.select();
    try{document.execCommand('copy')}catch(e){}t.remove();done()}
}
/* ── اشتراک: پنجرهٔ خود سیستم (شیت iOS/اندروید) و جایگزین کپی لینک ── */
async function shareItem(o){
  o=o||{};
  const url=String(o.url||location.href);
  const title=String(o.title||document.title||'نورا').slice(0,80);
  const text=String(o.text||'').slice(0,200);
  if(navigator.share){
    try{await navigator.share({title:title,text:text,url:url}); return true}
    catch(e){
      if(e&&e.name==='AbortError') return false;   /* کاربر خودش بست؛ چیزی نمی‌گوییم */
    }
  }
  copyText((text?text+'\n':'')+url);
  return false;
}

/* ── دسترس‌پذیری ورقه‌ها: مودال واقعی، فوکوس داخل، برگشت فوکوس ── */
const SHEET_FOCUSABLE='a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';
let _sheetLast=null;
function sheetOnKey(e){
  if(e.key!=='Tab') return;
  const open=[...document.querySelectorAll('.sheet.on')];
  if(!open.length) return;
  const el=open[open.length-1];
  const items=[...el.querySelectorAll(SHEET_FOCUSABLE)].filter(x=>x.offsetParent!==null||x===document.activeElement);
  if(!items.length) return;
  const first=items[0], last=items[items.length-1];
  if(e.shiftKey&&(document.activeElement===first||!el.contains(document.activeElement))){e.preventDefault(); last.focus()}
  else if(!e.shiftKey&&(document.activeElement===last||!el.contains(document.activeElement))){e.preventDefault(); first.focus()}
}
function sheetA11y(){
  const sync=()=>{
    const on=document.querySelector('.sheet.on');
    document.querySelectorAll('.sheet').forEach(s=>s.setAttribute('aria-modal',s.classList.contains('on')?'true':'false'));
    if(on&&!_sheetLast){_sheetLast=document.activeElement;
      const first=on.querySelector(SHEET_FOCUSABLE); if(first&&!on.contains(document.activeElement)) first.focus();}
    if(!on&&_sheetLast){try{if(_sheetLast.isConnected) _sheetLast.focus()}catch(e){} _sheetLast=null}
  };
  new MutationObserver(sync).observe(document.documentElement,{subtree:true,attributeFilter:['class']});
  document.addEventListener('keydown',sheetOnKey);
  sync();
}

function openSheet(id){closeSheets(); const el=document.getElementById(id); if(!el)return;
  document.getElementById('scrim').classList.add('on'); el.classList.add('on');
  initAll(el); el.scrollTop=0;}
function closeSheets(){document.querySelectorAll('.sheet').forEach(s=>s.classList.remove('on'));
  const s=document.getElementById('scrim'); if(s)s.classList.remove('on');}
function initUI(){
  initKeys(document);
  fillTrust(document);
  /* ورقه‌ها، سوییچ، سگمنت، چیپ، درخشش، کپی */
  document.addEventListener('click',e=>{
    const op=e.target.closest('[data-sheet]'); if(op){openSheet(op.dataset.sheet);return}
    if(e.target.closest('[data-close]')||e.target.closest('.scrim')){closeSheets();return}
    const cp=e.target.closest('[data-copy]');
    if(cp){const el=cp.dataset.copy.startsWith('#')?document.querySelector(cp.dataset.copy):null;
      copyText(el?el.textContent.trim():cp.dataset.copy,null,cp.dataset.copyMsg);return}
    const sw=e.target.closest('.switch'); if(sw){sw.classList.toggle('on');sw.setAttribute('aria-checked',sw.classList.contains('on'));return}
    const sg=e.target.closest('.seg button'); if(sg){[...sg.parentElement.children].forEach(x=>x.classList.remove('on'));sg.classList.add('on');return}
    const ch=e.target.closest('.chip[data-chip]'); if(ch){
      /* چیپ‌های «یک از چند» (تعداد، رویداد، دلیل…) انتخاب را جابه‌جا می‌کنند،
         نه خاموش/روشن؛ وگرنه دو هندلر روی هم، انتخاب را برمی‌داشتند */
      if(ch.matches('.chip[data-n],.chip[data-x],.chip[data-st],.chip[data-ev]')){
        ch.parentElement.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));
        ch.classList.add('on');
      } else ch.classList.toggle('on');
    }
  });
  /* درخشش ملایم زیر انگشت/ماوس، با قاب‌بندی تا هر حرکت، چیدمان را نخواند */
  let sheenQ=null, sheenRaf=0;
  document.addEventListener('pointermove',e=>{
    if(!(e.target instanceof Element)) return;
    const s=e.target.closest('.sheen'); if(!s) return;
    sheenQ={el:s,x:e.clientX,y:e.clientY};
    if(sheenRaf) return;
    sheenRaf=requestAnimationFrame(()=>{
      sheenRaf=0; const q=sheenQ; sheenQ=null; if(!q||!q.el.isConnected) return;
      const r=q.el.getBoundingClientRect();
      q.el.style.setProperty('--mx',((q.x-r.left)/r.width*100).toFixed(1)+'%');
      q.el.style.setProperty('--my',((q.y-r.top)/r.height*100).toFixed(1)+'%');
    });
  },{passive:true});
  /* شب و روز */
  themeInit();
  const t=document.getElementById('theme');
  if(t) t.onclick=themeToggle;
  initAll(document);
}

/* برای آزمون در محیط نود؛ در مرورگر نادیده می‌ماند */
if(typeof module!=='undefined'&&module.exports) module.exports={esc,escAttr,initKeys,download,svgToPNG,
  certificateSVG,certificateFile,CERT_G,
  words,money,faN,fa,faDigits,tkQR,tkFit,ticketMeta};

/* ══════════════════════════════════════════════════════════════════════════
   تم روز و شب، یک منبع حقیقت برای همهٔ صفحه‌های نورا
   ──────────────────────────────────────────────────────────────────────────
   کلید حافظه: nora-theme · مقدارها: light | dark
   رنگ نوار وضعیت مرورگر (theme-color) هم با تم عوض می‌شود.
   هر عنصر [data-theme-toggle] یک کلید کشویی خورشید/ماه است که با وضعیت
   هم‌گام می‌ماند؛ خودِ نشانه‌گذاری‌اش را themeSwitchHTML می‌سازد.
   ══════════════════════════════════════════════════════════════════════════ */
const THEME_KEY='nora-theme';
const THEME_BAR={light:'#F5F3EE', dark:'#1B211E'};
function themeNow(){return document.documentElement.dataset.theme==='dark'?'dark':'light'}
function themeApply(v,save){
  v=(v==='dark')?'dark':'light';
  document.documentElement.dataset.theme=v;
  document.documentElement.style.colorScheme=v;
  if(save!==false){try{localStorage.setItem(THEME_KEY,v)}catch(e){}}
  const m=document.querySelector('meta[name="theme-color"]'); if(m) m.setAttribute('content',THEME_BAR[v]);
  document.querySelectorAll('[data-theme-toggle]').forEach(b=>{
    const on=v==='dark';
    b.setAttribute('aria-checked',on?'true':'false');
    b.dataset.state=v;
    const lab=b.dataset.labelDark;
    if(lab) b.setAttribute('aria-label',on?lab:(b.dataset.labelLight||lab));
  });
  return v;
}
function themeToggle(){return themeApply(themeNow()==='dark'?'light':'dark')}
function themeInit(){
  let v=null;
  try{v=localStorage.getItem(THEME_KEY)}catch(e){}
  if(v!=='dark'&&v!=='light'){
    /* اگر کاربر انتخاب نکرده، پیشفرض پنل میآید؛ «خودکار» یعنی دستگاه */
    const dm=(uiSet().theme||{}).mode;
    if(dm==='dark'||dm==='light') v=dm;
    else v=(typeof matchMedia==='function'&&matchMedia('(prefers-color-scheme:dark)').matches)?'dark':'light';
  }
  return themeApply(v,false);
}
/* نشانه‌گذاری کلید کشویی: خورشید در یک سر، ماه در سر دیگر، گرهٔ لغزان بین‌شان */
function themeSwitchHTML(o){
  o=o||{};
  return `<span class="tsw-trk" aria-hidden="true">
    <span class="tsw-ico tsw-sun"><svg class="i"><use href="#i-sun"/></svg></span>
    <span class="tsw-ico tsw-moon"><svg class="i"><use href="#i-moon"/></svg></span>
    <span class="tsw-knob"></span></span>`;
}

/* ── پروفایل حساب ─────────────────────────────────────────────────────────
   یک منبع حقیقت برای خانه و صفحهٔ حساب من. رشته‌ها پاک‌سازی می‌شوند و وضعیت
   فقط از میان چهار حالت خودش می‌آید، وگرنه دادهٔ خراب صفحه را به‌هم می‌زند. */
const P_STATUS=['draft','pending','approved','rejected'];
function cleanProfile(v){
  const A=(window.NORA&&window.NORA.ACCOUNT)||{}, out={};
  (A.fields||[]).forEach(f=>{
    const raw=v&&v[f.k];
    out[f.k]=typeof raw==='string'?raw.replace(/[\u0000-\u001f<>]/g,'').trim().slice(0,120):'';
  });
  out.status=P_STATUS.includes(v&&v.status)?v.status:'draft';
  out.reason=typeof (v&&v.reason)==='string'?(v.reason||'').replace(/[\u0000-\u001f<>]/g,'').slice(0,200):'';
  out.askedDelete=!!(v&&v.askedDelete);
  const h=(v&&Array.isArray(v.history))?v.history:[], H_KIND=P_STATUS.concat(['filled','delete']);
  out.history=h.filter(x=>x&&H_KIND.includes(x.k)&&typeof x.at==='string')
                .slice(-6).map(x=>({k:x.k,at:x.at.slice(0,20)}));
  return out;
}
function sessUser(){ try{const v=JSON.parse(localStorage.getItem(SESS_KEY)||'null');
  return v&&typeof v==='object'&&typeof v.name==='string'?v:null}catch(e){return null} }
function profile(){
  let v=null; try{v=JSON.parse(localStorage.getItem(PROF_KEY)||'null')}catch(e){v=null}
  const A=(window.NORA&&window.NORA.ACCOUNT)||{};
  if(!v){
    /* کاربر واردشده و پروفایل دست‌نخورده: نمونهٔ خودِ داده می‌نشیند */
    return cleanProfile(uid()&&A.seed?Object.assign({},A.seed):null);
  }
  return cleanProfile(v);
}
function saveProfile(v){
  const p=cleanProfile(v);
  try{localStorage.setItem(PROF_KEY,JSON.stringify(p))}catch(e){}
  return p;
}
/* ══ تنظیمهای ظاهری سامانه: یک انبار مشترک، همهٔ صفحه‌ها از آن می‌خوانند ══ */
const UISET_KEY='nora-uiset';
const UISET_DEF={v:1,
  home:{bnr:1,stories:1,search:1,quick:1,pins:1,mine:1,events:1,past:1,club:1,teachers:1,staff:1,articles:1,partners:1,voices:1,about:1,act:1},
  menu:[],quick:[],
  bnr:{on:1,auto:1,hide:[],speed:'mid'},bnrAdd:[],
  storyHide:[],storyAdd:[],
  cards:'mid',people:'card',
  type:{size:'mid',radius:'mid',width:'mid',density:'mid',motion:1,accent:''},
  chrome:{bell:1,themebtn:1,helpbtn:1,tabLabels:1,hot:1},
  theme:{mode:'auto',allowToggle:1},
  forms:{model:'registration',display:'one',after:'edit',guests:0,wait:1,limit:'event',
    dept:'edu',to:'کارتابل کارشناس',endText:'',
    tags:[{n:'بررسی شد',c:'ok'},{n:'پیگیری',c:'warn'},{n:'ویژه',c:'brand'}]},
  users:{regs:'free',dues:1,prune:'off',okOnly:0},
  ops:{cap:8,log:'on',auditTone:'brand'},
  trust:{on:1,text:''},foot:{on:1,text:''}};
function uiSet(){
  const base=JSON.parse(JSON.stringify(UISET_DEF));
  try{const v=JSON.parse(localStorage.getItem(UISET_KEY)||'null'); if(!v||v.v!==1) return base;
    Object.keys(v).forEach(k=>{
      const b=base[k];
      if(b&&typeof b==='object'&&!Array.isArray(b)&&v[k]&&typeof v[k]==='object'&&!Array.isArray(v[k])) Object.assign(b,v[k]);
      else base[k]=v[k];});
    return base;
  }catch(e){return base}
}
function uiSetSave(s){try{localStorage.setItem(UISET_KEY,JSON.stringify(s))}catch(e){}}
/* برچسبها و انتخابهای پنل: یک جا تا خانه و پنل یکی بمانند */
const UISET_META={
  home:[['bnr','بنرها'],['stories','استوریها'],['search','جستوجو'],['quick','منوی سریع'],['pins','سنجاقشدهها'],['mine','برای تو'],['events','برنامههای نزدیک'],['past','کارگاههای برگزارشده'],['club','باشگاه کتاب'],['teachers','اساتید'],['staff','دستاندرکاران'],['articles','مقالات'],['partners','نهادهای همکار'],['voices','نظر شرکتکنندهها'],['about','نورا در یک نگاه'],['act','نمای فعالیت ماهانه']],
  quick:[['events','رویدادها'],['past','برگزارشدهها'],['club','باشگاه کتاب'],['people','اساتید'],['articles','مطالب'],['partners','نهادهای همکار'],['verify','استعلام گواهی'],['support','پشتیبانی']],
  people:[['card','کارت کامل'],['row','ردیف فشرده'],['chip','فقط نامها']],
  cards:[['small','فشرده'],['mid','معمولی'],['big','بزرگ']],
  storyIco:[['i-image','تصویر'],['i-book','کتاب'],['i-user','کاربر'],['i-medal','مدال'],['i-handshake','همکاری'],['i-sparkle','درخشش'],['i-calendar','تقویم'],['i-star','ستاره']],
  storyGo:[['me','حساب من'],['club','باشگاه کتاب'],['partners','نهادهای همکار'],['pastSec','برگزارشدهها']],
  grads:[['linear-gradient(135deg,#0A56B8,#0B2447)','آبی نورا'],['linear-gradient(135deg,#2E6B7A,#0B2447)','سبزآبی'],['linear-gradient(135deg,#7A5A2A,#0A3A82)','کهربایی'],['linear-gradient(135deg,#3E5B84,#0B2447)','شبانه']],
  typeSize:[['small','کوچک'],['mid','معمولی'],['big','بزرگ']],
  typeRad:[['flat','تخت'],['mid','معمولی'],['round','گرد']],
  typeWidth:[['narrow','باریک'],['mid','معمولی'],['wide','گسترده']],
  typeDen:[['tight','دنج'],['mid','معمولی'],['airy','باز']],
  bnrSpeed:[['slow','آهسته'],['mid','معمولی'],['fast','تند']],
  accents:[['','آبی نورا'],['teal','سبز'],['plum','بنفش'],['amber','کهربایی'],['night','شبانه']],
  formsModel:[['registration','ثبتنام'],['questionnaire','پرسشنامه'],['survey','نظرسنجی'],['contest','مسابقه'],['exam','آزمون'],['attendance','حضور و غیاب'],['datacollect','ثبت اطلاعات'],['order','سفارش'],['election','رأیگیری']],
  formsDisplay:[['one','هر مرحله یک پرسش'],['all','همه در یک صفحه']],
  formsAfter:[['edit','بعد از ثبت: ویرایش'],['view','فقط مشاهده'],['cancel','انصراف']],
  formsLimit:[['none','آزاد برای همه'],['event','فقط ثبتنامکردههای رویداد'],['attended','حاضران جلسهٔ پیشین'],['invite','فهرست یا کد دعوت']],
  formsDept:[['edu','آموزش'],['data','پژوهش و نظرسنجی'],['media','رسانه و تولید محتوا'],['sup','پشتیبانی']],
  formsTo:[['کارتابل کارشناس','کارتابل کارشناس'],['کارتابل + پیام‌رسان بله','کارتابل + بله'],['کارتابل + ایمیل','کارتابل + ایمیل'],['پیام‌رسان بله','فقط بله']],
  tagColors:[['ok','سبز'],['warn','کهربایی'],['stop','سرخ'],['brand','آبی']],
  usersRegs:[['free','خوداظهاری'],['phone','تأیید موبایل'],['invite','فقط کد دعوت'],['closed','ثبتنام بسته']],
  usersPrune:[['off','خاموش'],['1m','پس از یک ماه'],['3m','پس از سه ماه'],['6m','پس از ششماه']],
  opsCap:[['5','۵ کار'],['8','۸ کار'],['12','۱۲ کار'],['20','همه']],
  opsLog:[['on','روشن'],['off','خاموش']],
  opsTone:[['brand','آبی'],['ok','سبز'],['warn','کهربایی'],['stop','سرخ']]};
/* منوی کاربر با ردیفهای پنهانشده؛ گروهی که همه ردیفهایش پنهان است نمیآید */
function menuAllowed(){
  const U=uiSet(), M=(window.NORA&&window.NORA.MENU)||[];
  return M.map(g=>({g:g.g,i:g.i,rows:(g.rows||[]).filter(r=>!U.menu.includes(r.t))}))
         .filter(g=>g.rows.length);
}
/* ══ خط اطمینان، هر [data-trust] را با جملهٔ کوتاه خودش پر می‌کند ═══ */
function trustPick(kind){
  const T=(window.NORA&&window.NORA.TRUST)||{}, rows=T.row||[], short=T.short||{};
  if(short[kind]) return short[kind];
  const hit=rows.find(r=>String(r[0]).indexOf(kind)>-1);
  return (hit&&hit[1])||(rows[0]&&rows[0][1])||'اطلاعاتت رمزنگاری‌شده است.';
}
function fillTrust(root){
  const scope=root||document, U=uiSet();
  [...scope.querySelectorAll('[data-trust]')].forEach(el=>{
    if(!U.trust.on){el.hidden=true; return}
    if(el.getAttribute('data-filled')) return;
    const kind=el.getAttribute('data-trust')||'secure';
    el.innerHTML='<svg class="i" aria-hidden="true"><use href="#i-shield"/></svg><span>'+
      esc(U.trust.text||trustPick(kind))+'</span>';
    el.setAttribute('data-filled','1');
  });
}
/* شمارهٔ تماس از خود نشست می‌آید و در پروفایل قفل است */
function phoneOf(){const u=sessUser(); return (u&&u.mobile)||''}
function profileFilled(p,withPhone){
  const A=(window.NORA&&window.NORA.ACCOUNT)||{}, out={};
  /* پارامتر تصویری، در شمارش درصد نمی‌آید */
  (A.fields||[]).forEach(f=>{ out[f.k]= f.lock ? !!withPhone : !!(p&&p[f.k]) });
  return out;
}
const softField=f=>f.input==='image'||!f.req;   /* عکس و پارامترهای اختیاری، درصد را پایین نمی‌آورند */
function hardMissing(p,withPhone){
  const A=(window.NORA&&window.NORA.ACCOUNT)||{}, f=profileFilled(p,withPhone);
  return (A.fields||[]).filter(x=>f[x.k]||softField(x));
}
function profilePercent(p,withPhone){
  const A=(window.NORA&&window.NORA.ACCOUNT)||{}, f=profileFilled(p,withPhone);
  /* همهٔ پارامترها جز عکس */
  const hard=(A.fields||[]).filter(x=>!softField(x));
  const all=hard.length?hard:Object.keys(f);
  return all.length?Math.round(all.filter(x=>f[x.k]).length/all.length*100):0;
}
function profileMissing(p,withPhone){
  const A=(window.NORA&&window.NORA.ACCOUNT)||{}, f=profileFilled(p,withPhone);
  return (A.fields||[]).filter(x=>!f[x.k]&&!softField(x));
}
/* سطح از جدول خودِ داده می‌آید؛ نه دستی در هر صفحه */
function levelOf(points){
  const L=((window.NORA&&window.NORA.ACCOUNT)||{}).levels||[];
  let cur=L[0]||{k:'-',n:'—',at:0,perks:''}, next=null;
  L.forEach((x,i)=>{ if(points>=x.at){cur=x; next=L[i+1]||null} });
  return {cur:cur, next:next};
}

/* ══════════════════════════════════════════════════════════════════════════
   کارت رویداد با پوستر، یک کارت، مشترک خانه و صفحهٔ رویدادها
   ──────────────────────────────────────────────────────────────────────────
   هر رویداد می‌تواند «پوستر» داشته باشد؛ اگر داشت همان نشان داده می‌شود وگرنه
   گرادیان و آیکون خودِ رویداد می‌آید. برگزارشده‌ها هم با همین کارت ساخته
   می‌شوند، فقط با نشان «برگزار شد» و دکمهٔ خرید بازپخش.
   ورودی دوم (o) ظاهر کارت را می‌سازد: attr، badge، meta، note، person،
   price، free، bar، cta، ctaKind، ctaIcon، past، cls.
   ══════════════════════════════════════════════════════════════════════════ */
const escH=t=>String(t==null?'':t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
function evPosterCard(e,o){
  o=o||{};
  /* دو حالت: پیوند (خانه) یا دکمهٔ ورقهٔ جزئیات (صفحهٔ رویدادها) */
  const act=o.href?`href="${escH(o.href)}"`:`data-${o.key||'ev'}="${escH(e.id)}"`;
  const wrap=o.href?'a':'button';
  const p=o.person||null;
  const tags=(o.tags||[]).filter(Boolean).map(t=>`<span class="evc-tag${o.past&&t==='برگزار شد'?' dark':''}">${escH(t)}</span>`).join('');
  const metas=(o.meta||[]).filter(Boolean).map(m=>`<span class="mi"><svg class="i"><use href="#${m[0]}"/></svg>${escH(m[1])}</span>`).join('');
  const cover=e.poster
    ? `<img src="${escH(e.poster)}" alt="پوستر ${escH(e.t)}" loading="lazy" decoding="async"/>`
    : `<span class="evc-grad" style="--g:${escH(e.g||'')}"><svg class="i"><use href="#${escH(e.icon||'i-calendar')}"/></svg></span>`;
  const cta=o.cta?`<${wrap} class="btn sm evc-cta ${o.ctaKind||'primary'}" ${act}>
      <svg class="i"><use href="#${o.ctaIcon||'i-pen'}"/></svg> ${escH(o.cta)}</${wrap}>`:'';
  return `<article class="evcard${o.past?' past':''}${o.cls?' '+o.cls:''}">
    <${wrap} class="evc-cov" ${act} aria-label="جزئیات ${escH(e.t)}">
      ${cover}
      ${tags?`<span class="evc-tags">${tags}</span>`:''}
      ${o.badge?`<span class="evc-day">${o.badge}</span>`:''}
    </${wrap}>
    <div class="evc-body">
      <div class="evc-ttl">${escH(e.t)}</div>
      ${metas?`<div class="evc-meta">${metas}</div>`:''}
      ${o.note?`<div class="evc-note">${escH(o.note)}</div>`:''}
      <div class="evc-foot">
        ${p?`<span class="evc-ava" style="--g:${escH(p.g||'')}">${p.photo?`<img src="${escH(p.photo)}" alt="${escH(p.n)}"/>`:escH(p.ini||'')}</span>
          <span class="evc-who"><b>${escH(p.n)}</b><small>${escH(p.r||'')}</small></span>`:''}
        <span class="sp"></span>
        <span class="evc-price${o.free?' free':''}">${o.price||''}</span>
      </div>
      ${o.bar?`<div class="evc-bar"><i style="width:${o.bar}%"></i></div>`:''}
      ${cta}
    </div>
  </article>`;
}

/* ══════════════════════════════════════════════════════════════════════════
   اجزای مشترک آرشیو و منو (v8)
   ──────────────────────────────────────────────────────────────────────────
   این‌ها را هر صفحه‌ای می‌تواند صدا بزند: منو، اعلان‌ها، کلیات رویداد،
   رسانه و پخش، خرید، و ورود. هیچ‌کدام به صفحهٔ خاصی وابسته نیستند و اگر
   صفحه ورقه‌شان را نداشته باشد، خودشان می‌سازند.
   ══════════════════════════════════════════════════════════════════════════ */
const LIB_KEY='nora-home-library', PROG_KEY='nora-home-progress', READ_KEY='nora-home-read', SESS_KEY='nora-home-user';
const PROF_KEY='nora-home-profile';   /* پروفایل حساب: هویت، نشانی، وضعیت تأیید */
const PRE_KEY='nora-home-prereg';                 /* پیش‌ثبت‌نام و یادآوری برنامه‌ها */
const jread=(k,d)=>{try{const v=JSON.parse(localStorage.getItem(k)||'null'); return v==null?d:v}catch(e){return d}};
const jwrite=(k,v)=>{try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}};
const price=n=>n?rialTxt(n):'رایگان';

/* ── کتابخانهٔ من: چه چیزی تهیه کرده‌ام ── */
function library(){const a=jread(LIB_KEY,[]); return Array.isArray(a)?a:[]}
function hasLib(id){return library().some(x=>x&&x.id===id)}
function addLib(id,meta){
  if(hasLib(id)) return false;
  const a=library(); a.unshift(Object.assign({id:id,at:Date.now()},meta||{})); jwrite(LIB_KEY,a.slice(0,60));
  return true;
}
function progressOf(id){const p=jread(PROG_KEY,{}); return p&&typeof p==='object'?(p[id]||0):0}
function setProgress(id,sec){const p=jread(PROG_KEY,{})||{}; p[id]=Math.max(0,Math.round(sec)); jwrite(PROG_KEY,p)}

/* ── اعلان‌ها: یک نسخه برای همهٔ صفحه‌ها ── */
function readNotices(){const a=jread(READ_KEY,[]); return Array.isArray(a)?a:[]}
function unreadCount(){
  const N=(window.NORA&&window.NORA.NOTICES)||[], r=readNotices();
  return N.filter(n=>!r.includes(n.t)).length;
}
function markRead(title){
  const r=readNotices(); if(title&&!r.includes(title)) r.push(title); jwrite(READ_KEY,r); syncBell();
}
function syncBell(){
  const b=document.getElementById('bellBadge'); if(!b) return;
  const n=unreadCount(); b.hidden=!n; b.textContent=faN(n);
}
function noticesSheet(){
  const N=(window.NORA&&window.NORA.NOTICES)||[], r=readNotices();
  return `<div class="grabber"></div>
    <div class="row" style="align-items:center;margin-bottom:8px">
      <div><div class="head">اعلان‌ها</div><div class="cap">${faN(unreadCount())} خوانده‌نشده از ${faN(N.length)}</div></div>
      <span class="sp"></span>
      <button class="btn sm quiet" data-uireadall><svg class="i"><use href="#i-check"/></svg> همه خوانده شد</button>
      <button class="icon-btn" data-close aria-label="بستن"><svg class="i"><use href="#i-close"/></svg></button>
    </div>
    <div class="stack tight">${N.map((n,i)=>`<div class="notif ${r.includes(n.t)?'':'unread'}">
      <span class="ni"><svg class="i" style="width:16px;height:16px"><use href="#${n.i}"/></svg></span>
      <span><span class="nt">${escH(n.t)}</span><div class="nd">${escH(n.d)}</div>
      <div class="cap" style="margin-top:4px">${escH(n.w)}${n.ev?' · <button class="lnk" data-uiev="'+escH(n.ev)+'">دیدن رویداد</button>':''}</div></span></div>`).join('')}</div>
    <p class="cap" style="margin-top:12px">اعلان‌ها همین‌جا خوانده می‌شوند؛ هر جا باشی، از خود نوار بالا باز می‌شوند.</p>`;
}

/* ── منو: همان پنج گروه و ۲۱ ردیف، در هر صفحه ── */
function menuSheet(){
  const M=menuAllowed(), P=(window.NORA&&window.NORA.PARTNERS)||[];
  return `<div class="grabber"></div>
    <div class="row" style="align-items:center;margin-bottom:8px">
      <div><div class="head">منوی نورا</div><div class="cap">همهٔ بخش‌ها، یک‌جا</div></div>
      <span class="sp"></span><button class="icon-btn" data-close aria-label="بستن"><svg class="i"><use href="#i-close"/></svg></button></div>
    <div class="mhead">
      <div class="mt">نورا · گروه فرهنگی خط زندگی</div>
      <div class="ms">${((window.NORA&&window.NORA.EVENTS)||[]).length?faN(window.NORA.EVENTS.length)+' رویداد پیش‌رو':''} · ${faN((window.NORA&&window.NORA.TOTAL_MEDIA)||0)} رسانه در فروشگاه</div>
    </div>
    ${M.map(g=>`<div class="mgroup">
      <div class="gh"><svg class="i" style="width:14px;height:14px"><use href="#${g.i}"/></svg>${escH(g.g)}</div>
      ${g.rows.map(r=>`<button class="mrow" ${r.href?`data-uihref="${escH(r.href)}"`:r.rel?`data-uiev="${escH(r.rel)}"`:r.f?`data-uif="${escH(r.f)}"`:`data-uijump="${escH(r.j||'')}"`}>
        <span class="mi"><svg class="i"><use href="#${r.i}"/></svg></span>
        <span class="mtx"><b>${escH(r.t)}</b><span>${escH(r.s)}</span></span>
        <span class="sp" style="flex:1"></span>
        ${r.badge?`<span class="tag">${escH(r.badge)}</span>`:''}
        ${r.tag?`<span class="tag brand">${escH(r.tag)}</span>`:''}
        <svg class="i" style="width:15px;height:15px;color:var(--ink-4)"><use href="#i-chev-left"/></svg></button>`).join('')}
    </div>`).join('')}
    <div class="mfoot">
      <div class="cap">نهادهای همکار</div>
      <div class="lrow">${P.slice(0,8).map(o=>`<span class="mon" style="--g:${escH(o.g)};width:26px;height:26px;border-radius:8px;font-size:10px;display:grid;place-items:center;color:#fff" title="${escH(o.n)}">${escH(o.mon)}</span>`).join('')}</div>
    </div>`;
}

/* ── ورقه‌ای که اگر نبود، ساخته می‌شود ── */
function ensureSheet(id,label,full){
  let el=document.getElementById(id);
  if(el){ if(full) el.classList.add('full'); return el }
  el=document.createElement('aside');
  el.className='sheet'+(full?' full':''); el.id=id;
  el.setAttribute('role','dialog'); el.setAttribute('aria-modal','false'); el.setAttribute('aria-label',label||'');
  el.innerHTML='<div class="sbody"></div>';
  document.body.appendChild(el);
  if(!document.getElementById('scrim')){
    const s=document.createElement('div'); s.className='scrim'; s.id='scrim'; document.body.appendChild(s);
    s.addEventListener('click',closeSheets);
  }
  return el;
}
function fillSheet(id,html,full){
  /* ورقهٔ تازه‌ساخته هم باید در همان لحظه سوار شود */
  const el=ensureSheet(id,'',full);
  const b=el.querySelector('.sbody')||el.querySelector('[id$="Body"]')||el;
  b.innerHTML=html; initAll(el);
  document.querySelectorAll('.sheet').forEach(s=>s.setAttribute('aria-modal','false'));
  el.classList.add('on'); el.setAttribute('aria-modal','true');
  const sc=document.getElementById('scrim'); if(sc) sc.classList.add('on');
  return el;
}

/* ══════════════════════════════════════════════════════════════════════════
   آرشیو رسانه
   ══════════════════════════════════════════════════════════════════════════ */
function libState(item,past){
  if(!item.p) return {k:'open', t:item.preview?'نمونهٔ رایگان':'باز', i:'i-play'};
  if(hasLib(item.id)||hasLib(past&&past.id)) return {k:'mine', t:'تهیه شده', i:'i-check'};
  return {k:'lock', t:price(item.p).replace(' ریال',''), i:'i-lock'};
}
/* فهرست رسانهٔ یک بسته: وضعیت هر قلم، دکمهٔ پخش/خرید، و نوار پیشرفت */
function mediaList(past,o){
  o=o||{};
  let items=past.media||[];
  if(o.filter&&o.filter!=='all') items=items.filter(m=>m.k===o.filter);
  if(!items.length) return '<div class="empty"><svg class="i"><use href="#i-archive"/></svg><p>با این صافی چیزی در این بسته نیست.</p></div>';
  return `<div class="stack tight">${items.map(m=>{
    const kd=(window.NORA.MEDIA_KINDS||{})[m.k]||{i:'i-play',n:'رسانه'}, st=libState(m,past);
    const pr=progressOf(m.id), pct=pr?Math.min(100,Math.round(pr/60/90*100)):0;
    const locked=st.k==='lock';
    return `<div class="mrow2 ${locked?'locked':''}">
      <button class="mthumb ${m.k}" data-uimedia="${escH(past.id)}:${escH(m.id)}" aria-label="${locked?'خرید':'پخش'} ${escH(m.t)}">
        <svg class="i" style="width:19px;height:19px"><use href="#${locked?'i-lock':kd.i}"/></svg>
        ${pct?`<span class="mprog"><i style="width:${pct}%"></i></span>`:''}
      </button>
      <span class="mtx"><b>${escH(m.t)}</b>
        <small>${kd.n} · ${escH(m.d)} · ${escH(m.s)}${pr?' · نیمه‌کاره':''}</small></span>
      <span class="sp" style="flex:1"></span>
      ${locked
        ? `<button class="btn sm quiet" data-uibuy="${escH(past.id)}:${escH(m.id)}">${st.t}</button>`
        : `<button class="btn sm ${st.k==='mine'?'quiet':'primary'}" data-uimedia="${escH(past.id)}:${escH(m.id)}">
             <svg class="i"><use href="#${kd.i}"/></svg> ${st.k==='open'&&m.preview?'تماشای نمونه':kd.v}</button>`}
    </div>`}).join('')}</div>`;
}
/* کارت بستهٔ آرشیو (برگزارشده‌ها) */
function bundleCard(past,o){
  const p=((window.NORA&&window.NORA.PEOPLE)||[]).find(x=>x.id===past.tchr)||{n:'—',ini:'؟',r:'',g:''};
  const chips=Object.keys(past.counts||{}).map(k=>`<span class="tag">${faN(past.counts[k])} ${((window.NORA.MEDIA_KINDS||{})[k]||{}).n||''}</span>`).join('');
  const mine=hasLib(past.id);
  return `<article class="evcard ${mine?'pinned':''}">
    <button class="evc-cov" data-past="${escH(past.id)}" aria-label="جزئیات ${escH(past.t)}">
      ${past.poster?`<img src="${escH(past.poster)}" alt="پوستر ${escH(past.t)}" loading="lazy" decoding="async"/>`
        :`<span class="evc-grad" style="--g:${escH(past.g||'')}"><svg class="i"><use href="#${escH(past.icon||'i-archive')}"/></svg></span>`}
      <span class="evc-tags"><span class="evc-tag dark">برگزار شد</span>${mine?'<span class="evc-tag dark">در کتابخانه‌ات</span>':''}</span>
      ${past.price?`<span class="evc-day">${escH(price(past.price))}</span>`:'<span class="evc-day">رایگان</span>'}
      <span class="mplay"><svg class="i" style="width:18px;height:18px"><use href="#i-play-f"/></svg></span>
    </button>
    <div class="evc-body">
      <div class="evc-ttl">${escH(past.t)}</div>
      <div class="evc-meta"><span class="mi"><svg class="i"><use href="#i-calendar"/></svg>${escH(past.d)}</span>
        <span class="mi"><svg class="i"><use href="#i-play"/></svg>${faN(past.mediaCount)} رسانه</span>
        <span class="mi"><svg class="i"><use href="#i-users"/></svg>${faN(past.sold)} خرید</span></div>
      <div class="row tight" style="margin:8px 0 2px">${chips}${past.cert?'<span class="tag accent">گواهی‌دار</span>':''}</div>
      <div class="evc-foot">
        <span class="evc-ava" style="--g:${escH(p.g||'')}">${p.photo?`<img src="${escH(p.photo)}" alt="${escH(p.n)}" loading="lazy"/>`:escH(p.ini||'')}</span>
        <span class="evc-who"><b>${escH(p.n)}</b><small>${escH(p.r||'')}</small></span>
        <span class="sp"></span><span class="evc-price${past.price?'':' free'}">${past.price?price(past.price):'رایگان'}</span>
      </div>
      <button class="btn ${past.price?'primary':'quiet'} block" data-past="${escH(past.id)}" style="margin-top:10px">
        <svg class="i"><use href="#${mine?'i-play':past.price?'i-bag':'i-download'}"/></svg>
        ${mine?'تماشا و دانلود':past.price?'دیدن جزئیات و تهیه':'دیدن و دریافت رایگان'}</button>
    </div>
  </article>`;
}

/* ── پیش‌ثبت‌نام: برای برنامه‌هایی که ثبت‌نامشان باز نشده ── */
function preList(){const a=jread(PRE_KEY,[]); return Array.isArray(a)?a:[]}
function isPre(id){return preList().indexOf(id)>-1}
function prereg(id,after){
  const N=window.NORA||{}, e=(N.EVENTS||[]).find(x=>x.id===id);
  if(!e) return;
  if(!walletUser()){ authSheet(()=>prereg(id,after)); return }
  const a=preList();
  if(a.indexOf(id)>-1){
    jwrite(PRE_KEY,a.filter(x=>x!==id));
    toast('پیش‌ثبت‌نامت برداشته شد');
  } else {
    a.push(id); jwrite(PRE_KEY,a);
    toast('پیش‌ثبت‌نام شد؛ باز شدن ثبت‌نام را همان روز خبر می‌دهیم');
  }
  document.dispatchEvent(new CustomEvent('nora:prereg',{detail:{id:id}}));
  if(typeof after==='function') after();
}
/* ── پیش‌نمایش: رایگان‌ترین قطعهٔ بسته را همان‌جا نشان می‌دهد ── */
function preview(id){
  const N=window.NORA||{}, H=(N.PAST||[]).find(x=>x.id===id); if(!H) return;
  const free=(H.media||[]).find(m=>!m.p||(m.preview&&!hasLib(m.id)));
  if(!free){ toast('برای این بسته نمونهٔ رایگان نگذاشته‌اند؛ جزئیاتش را ببین'); eventSheet(id); return }
  player(id,free.id);
  if(!hasLib(free.id) && free.p) toast('نمونهٔ رایگان؛ بستهٔ کامل در «جزئیات و تهیه»');
}

/* ══════════════════════════════════════════════════════════════════════════
   کلیات رویداد: ورقهٔ تمام‌صفحه‌ای که پیش از صفحهٔ اختصاصی می‌آید
   ══════════════════════════════════════════════════════════════════════════ */
function eventSheet(id){
  const N=window.NORA||{};
  /* رویدادهای منتشرشدهٔ پنل هم برگه دارند؛ برگزارشده‌ها در بخش خودشان */
  const PUB=pubEvents(), PE=PUB.find(x=>x.id===id);
  const E=PE&&!PE.past?PE:(N.EVENTS||[]).find(x=>x.id===id);
  const H=(PE&&PE.past)?null:(N.PAST||[]).find(x=>x.id===id);
  const e=PE||E||H; if(!e) return;
  const P=(N.PEOPLE||[]), p=P.find(x=>x.id===e.tchr)||{n:'—',ini:'؟',r:'',g:''};
  const past=PE?(!!PE.past):!!H, price1=e.price||0, full=e.cap&&(e.cap-e.taken)<=0;
  const tag=t=>`<span class="tag ${t[1]||''}">${escH(t[0])}</span>`;
  const when=past?e.d:(e.when+' · ساعت '+e.time);
  const room=e.mode&&e.mode.indexOf('حضوری')<0?'آنلاین':(e.mode==='حضوری و آنلاین'?'حضوری و آنلاین':'حضوری');
  const online=room!=='حضوری';
  const href='event.html?id='+encodeURIComponent(e.id);
  const hasFree=(e.media||[]).some(m=>!m.p||m.preview);
  const previewBtn=(past&&hasFree)?`<button class="btn quiet" data-uipreview="${escH(e.id)}"><svg class="i"><use href="#i-play-f"/></svg> پیش‌نمایش</button>`:'';
  const preOn=!past&&isPre(e.id);
  const preBtn=past?'':`<button class="btn ${preOn?'primary':'quiet'}" data-uipre="${escH(e.id)}"><svg class="i"><use href="#${preOn?'i-check':'i-bell'}"/></svg> ${preOn?'پیش‌ثبت‌نام شده':'پیش‌ثبت‌نام'}</button>`;
  const mediaHtml=(past&&!e.pubPast)?`
    <div class="sec-hd" style="margin-top:14px"><span class="fw">داخل این بسته</span><span class="sp"></span>
      <span class="cap">${faN(e.mediaCount)} رسانه · ${escH(e.access)}</span></div>
    ${mediaList(e)}`: '';
  fillSheet('shEvent',`
    <div class="esh">
      <button class="icon-btn" data-close aria-label="بستن"><svg class="i"><use href="#i-close"/></svg></button>
      <span class="esh-cover" style="--g:${escH(e.g||'')}">
        ${e.poster?`<img src="${escH(e.poster)}" alt="پوستر ${escH(e.t)}" loading="lazy"/>`:''}
        <span class="esh-veil"></span>
        <span class="esh-top">
          <span class="row tight">${tag([e.kind,'brand'])}${tag([room])}${past?tag(['برگزار شد','ok']):(e.live?tag(['همین حالا در حال برگزاری','stop']):'')}
            ${full?tag(['ظرفیت تکمیل','warn']):''}</span>
        </span>
      </span>
      <h2 class="esh-t">${escH(e.t)}</h2>
      <div class="cap">${escH(when)}${e.place?' · '+escH(e.place):''}</div>
    </div>
    <div class="row tight" style="margin:10px 0 4px">
      ${(e.tags||[]).map(t=>tag([t])).join('')}${online?tag(['آنلاین']):''}${past&&e.cert?tag(['گواهی‌دار','accent']):''}
    </div>
    <button class="suprow" data-uiperson="${escH(p.id)}" style="margin:10px 0">
      <span class="ava" style="--g:${escH(p.g||'')}">${p.photo?`<img src="${escH(p.photo)}" alt="${escH(p.n)}"/>`:escH(p.ini||'')}</span>
      <span style="flex:1;min-width:0"><b class="sub">${escH(p.n)}</b><div class="cap">${escH(p.r||'')}</div></span>
      <svg class="i" style="width:16px;height:16px;color:var(--ink-4)"><use href="#i-chev-left"/></svg></button>
    <div class="stack tight">
      <div class="srow"><svg class="i"><use href="#i-calendar"/></svg><span class="sp">${past?'برگزار شد':'زمان'}</span><b>${escH(when)}</b></div>
      ${past?`<div class="srow"><svg class="i"><use href="#i-clock"/></svg><span class="sp">حجم بسته</span><b>${escH(e.rec)}</b></div>`
           :`<div class="srow"><svg class="i"><use href="#i-pin"/></svg><span class="sp">${escH(e.place)}</span><b>${room}</b></div>`}
      ${!past&&e.sess>1?`<div class="srow"><svg class="i"><use href="#i-layers"/></svg><span class="sp">جلسه‌ها</span><b>${faN(e.sess)} جلسه</b></div>`:''}
      ${past&&e.rec?`<div class="srow"><svg class="i"><use href="#i-layers"/></svg><span class="sp">جلسه‌ها</span><b>${escH(e.rec)}</b></div>`:''}
      ${past?`<div class="srow"><svg class="i"><use href="#i-play"/></svg><span class="sp">رسانه‌ها</span><b>${faN(e.mediaCount)} قلم · ${faN(e.sold)} خرید</b></div>`
           :`<div class="srow"><svg class="i"><use href="#i-users"/></svg><span class="sp">${e.cap?faN(e.taken)+' نفر ثبت‌نام کرده‌اند':'همه می‌توانند شرکت کنند'}</span><b>${price(price1)}</b></div>`}
      ${online?`<div class="srow"><svg class="i"><use href="#i-video"/></svg><span class="sp">${past?'این برنامه ضبط شده؛ آنلاین تماشا می‌کنی':'جلسه آنلاین؛ لینک ورود ۱۵ دقیقه قبل می‌آید'}</span><b>${escH(past?'ضبط شده':'زنده')}</b></div>`:''}
    </div>
    ${(!past&&e.cap)?`<div class="bar" style="margin-top:10px"><i style="width:${Math.round(e.taken/e.cap*100)}%"></i></div>
      <div class="cap" style="margin-top:6px">${full?'ظرفیت تکمیل؛ ثبت‌نام به لیست انتظار می‌رود':'فقط '+faN(e.cap-e.taken)+' جا مانده از '+faN(e.cap)+' نفر'}</div>`:''}
    <p class="sub" style="margin-top:12px">${escH(e.d||'')}</p>
    ${(e.parts||[]).length?`<div class="stack tight" style="margin-top:10px">${e.parts.slice(0,3).map(x=>`<div class="srow"><svg class="i"><use href="#i-check"/></svg><span class="sp">${escH(x)}</span></div>`).join('')}</div>`:''}
    ${mediaHtml}
    <div class="moneyline" style="margin-top:14px">
      <span>${past?(price1?'بستهٔ کامل':'این بسته'):(price1?'مبلغ ثبت‌نام':'شرکت رایگان')}</span>
      <span class="num">${past?price(price1):priceTxt2(price1)}</span></div>
    <div class="row" style="margin-top:10px">
      <a class="btn primary" href="${href}"><svg class="i"><use href="#i-${past?'play':'pen'}"/></svg> جزئیات و ${past?'تهیه':'ثبت‌نام'}</a>
      ${previewBtn}${preBtn}
      <button class="btn quiet" data-uipin="${past?'pa':'ev'}:${escH(e.id)}"><svg class="i"><use href="#i-pin"/></svg> سنجاق</button>
      <button class="btn quiet" data-uishare="${escH(e.id)}"><svg class="i"><use href="#i-share"/></svg> اشتراک</button>
    </div>
    <p class="cap" style="margin-top:10px">صفحهٔ اختصاصی رویداد، جزئیات کامل و لینک ثبت‌نام را باز می‌کند.</p>`,true);
}
const priceTxt2=price;

/* ══════════════════════════════════════════════════════════════════════════
   پخش‌کنندهٔ ویدیو، صدا و فایل، همه آنلاین
   ══════════════════════════════════════════════════════════════════════════ */
let PLAY={id:null,past:null,item:null,sec:0,len:0,timer:null,rate:1,playing:false};
function playState(){
  const box=document.getElementById('playIn');
  if(!box||!PLAY.item) return;
  const len=PLAY.len, sec=PLAY.sec, pct=Math.min(100,sec/len*100);
  const t=box.querySelector('[data-uidx]');
  if(t){t.style.width=pct+'%';
    box.querySelector('[data-utime]').textContent=faN(Math.floor(sec/60))+':'+String(faN(Math.floor(sec%60))).padStart(2,'۰');
    box.querySelector('[data-ulen]').textContent=faN(Math.floor(len/60))+':'+String(faN(Math.floor(len%60))).padStart(2,'۰');}
  const b=box.querySelector('[data-uiplay]');
  if(b) b.innerHTML=`<svg class="i" style="width:22px;height:22px"><use href="#${PLAY.playing?'i-pause':'i-play-f'}"/></svg>`;
}
function playTick(){
  clearInterval(PLAY.timer);
  PLAY.timer=setInterval(()=>{
    if(!PLAY.playing) return;
    PLAY.sec+=1*PLAY.rate;
    if(PLAY.sec>=PLAY.len){PLAY.sec=PLAY.len; PLAY.playing=false; setProgress(PLAY.id,0); playState(); return}
    setProgress(PLAY.id,PLAY.sec); playState();
  },1000);
}
function player(pastId,mediaId){
  const N=window.NORA||{}, H=(N.PAST||[]).find(x=>x.id===pastId); if(!H) return;
  const i=(H.media||[]).findIndex(m=>m.id===mediaId); if(i<0) return;
  const m=H.media[i], kd=(N.MEDIA_KINDS||{})[m.k]||{n:'رسانه',v:'تماشا'};
  if(m.p&&!hasLib(m.id)&&!hasLib(H.id)){buySheet(pastId,mediaId); return}
  PLAY={id:m.id,past:pastId,item:m,sec:progressOf(m.id),len:m.k==='audio'?30*60:m.k==='video'?95*60:12*60,rate:1,playing:true,timer:null};
  const nx=H.media[i+1], pv=H.media[i-1];
  fillSheet('shPlay',`
    <div class="grabber"></div>
    <div class="row" style="align-items:center;margin-bottom:10px">
      <div><div class="head">${escH(kd.n)} · ${escH(H.t)}</div><div class="cap">${escH(m.t)}</div></div>
      <span class="sp"></span>
      <button class="btn sm quiet" data-uishare="${escH(H.id)}"><svg class="i"><use href="#i-share"/></svg> اشتراک</button>
      <button class="icon-btn" data-close aria-label="بستن"><svg class="i"><use href="#i-close"/></svg></button></div>
    <div id="playIn">
      ${m.k==='pdf'||m.k==='slide'?`
        <div class="pdoc"><svg class="i" style="width:34px;height:34px"><use href="#i-${m.k==='pdf'?'i-doc'.slice(2):'layers'}"/></svg>
          <b>${escH(m.t)}</b><div class="cap">${escH(m.d)} · ${escH(m.s)}</div></div>`
      :`<div class="pstage" style="--g:${escH(H.g||'')}">
          ${H.poster?`<img src="${escH(H.poster)}" alt="" loading="lazy"/>`:''}
          <span class="esh-veil"></span>
          ${m.k==='audio'?`<span class="pwaves">${Array.from({length:26},(_,k)=>`<i style="height:${18+((k*7)%46)}%"></i>`).join('')}</span>`:''}
          <button class="pbig" data-uiplay="${escH(m.id)}" aria-label="پخش"><svg class="i" style="width:22px;height:22px"><use href="#i-play-f"/></svg></button>
          <span class="cap pcap">${escH(H.t)}</span>
        </div>`}
      <div class="pbar">
        <div class="ptrack" data-uiseek><i data-uidx style="width:0%"></i></div>
        <div class="row" style="align-items:center;margin-top:6px">
          <span class="cap num" data-utime>۰:۰۰</span><span class="cap">/</span><span class="cap num" data-ulen>۰:۰۰</span>
          <span class="sp" style="flex:1"></span>
          ${pv?`<button class="icon-btn" data-uimedia="${escH(H.id)}:${escH(pv.id)}" aria-label="قبلی"><svg class="i"><use href="#i-back"/></svg></button>`:''}
          <button class="pbtn" data-uiplay="${escH(m.id)}" aria-label="پخش/توقف"></button>
          ${nx?`<button class="icon-btn" data-uimedia="${escH(H.id)}:${escH(nx.id)}" aria-label="بعدی"><svg class="i" style="transform:scaleX(-1)"><use href="#i-back"/></svg></button>`:''}
          <span class="sp" style="flex:1"></span>
          <span class="row tight">${[1,1.25,1.5,2].map(r=>`<button class="chip${r===1?' on':''}" data-uirate="${r}">${faN(r)}×</button>`).join('')}</span>
        </div>
      </div>
    </div>
    <div class="stack tight" style="margin-top:12px">
      ${(m.k==='pdf'||m.k==='slide')
        ? `<button class="btn primary block" data-uidl="${escH(m.id)}"><svg class="i"><use href="#i-download"/></svg> دانلود ${escH(m.s)}</button>
           <button class="btn quiet block" data-uiopen="${escH(H.id)}:${escH(m.id)}"><svg class="i"><use href="#i-link"/></svg> باز کردن در تب تازه</button>`
        : `<div class="srow"><svg class="i"><use href="#i-wifi"/></svg><span class="sp">کیفیت پخش</span><b>۷۲۰p · خودکار</b></div>
           <div class="srow"><svg class="i"><use href="#i-download"/></svg><span class="sp">دانلود برای تماشای بی‌آفلاین</span><b>${escH(m.s)}</b></div>`}
      <div class="srow"><svg class="i"><use href="#i-users"/></svg><span class="sp">دسترسی</span><b>${escH(H.access||'دسترسی همیشگی')}</b></div>
    </div>
    <div class="sec-hd" style="margin-top:14px"><span class="fw">ادامهٔ بسته</span><span class="sp"></span><span class="cap">${faN(H.media.length)} قلم</span></div>
    ${mediaList(H)}`);
  playState(); playTick();
  document.querySelectorAll('.sheet').forEach(s=>{if(s.id!=='shPlay') s.classList.remove('on')});
}

/* ── خرید: کیف پول یا درگاه ── */
function uid(){const u=walletUser(); return u?u.mobile||u.name:''}
function walletUser(){
  const u=jread(SESS_KEY,null);
  return (u&&typeof u==='object'&&u.name)?u:null;
}
function saveWalletUser(u){jwrite(SESS_KEY,u)}
function buySheet(pastId,mediaId){
  const N=window.NORA||{}, H=(N.PAST||[]).find(x=>x.id===pastId); if(!H) return;
  const m=mediaId?(H.media||[]).find(x=>x.id===mediaId):null;
  const amount=m?m.p:H.bundle, title=m?m.t:H.t+'، بستهٔ کامل';
  const u=walletUser();
  const method=jread('nora-home-pay',{k:'wallet'})||{k:'wallet'};
  fillSheet('shBuy',`
    <div class="grabber"></div>
    <div class="row" style="align-items:center;margin-bottom:10px">
      <div><div class="head">${m?'خرید تک‌قلم':'خرید بستهٔ کامل'}</div><div class="cap">${escH(H.t)}</div></div>
      <span class="sp"></span><button class="icon-btn" data-close aria-label="بستن"><svg class="i"><use href="#i-close"/></svg></button></div>
    <div class="stack tight">
      <div class="srow"><svg class="i"><use href="#${m?(((N.MEDIA_KINDS||{})[m.k]||{}).i||'i-play'):'i-archive'}"/></svg><span class="sp">${escH(title)}</span><b>${price(amount)}</b></div>
      <div class="srow"><svg class="i"><use href="#i-users"/></svg><span class="sp">${m?'قطعهٔ انتخاب‌شده':faN(H.mediaCount)+' رسانه، همهٔ قطعه‌ها'}</span><b>${escH(H.access||'همیشگی')}</b></div>
      <div class="srow"><svg class="i"><use href="#i-shield"/></svg><span class="sp">ضمانت</span><b>۷ روز بازگشت وجه</b></div>
    </div>
    <div class="cap" style="margin:12px 0 4px">راه پرداخت</div>
    <div class="stack tight">
      <button class="opt ${method.k==='wallet'?'on':''}" data-uipay="wallet">
        <span class="mk"></span><span class="sp">کیف پول نورا ${u?'· '+faN(u.wallet||0)+' ریال':''}</span>
        ${u&&(u.wallet||0)>=amount?'<span class="cap ok">موجود</span>':'<span class="cap warn">شارژ لازم است</span>'}</button>
      <button class="opt ${method.k==='gateway'?'on':''}" data-uipay="gateway">
        <span class="mk"></span><span class="sp">پرداخت آنلاین (درگاه بله)</span><span class="cap">کارت‌های شتاب</span></button>
    </div>
    <div class="moneyline" style="margin-top:12px"><span>مبلغ پرداخت</span><span class="num">${price(amount)}</span></div>
    <button class="btn primary block" style="margin-top:10px" data-uipayyes="${escH(pastId)}:${escH(mediaId||'')}">
      <svg class="i"><use href="#i-bag"/></svg> پرداخت و دسترسی فوری</button>
    <p class="cap" style="margin-top:10px">بعد از پرداخت، همین لحظه در «کتابخانهٔ من» می‌آید و بی‌آنکه جایی بروی، باز می‌شود.</p>`);
}
function doBuy(pastId,mediaId){
  const N=window.NORA||{}, H=(N.PAST||[]).find(x=>x.id===pastId); if(!H) return;
  const m=mediaId?(H.media||[]).find(x=>x.id===mediaId):null;
  const amount=m?m.p:H.bundle;
  let u=walletUser();
  if(!u){ authSheet(()=>doBuy(pastId,mediaId)); return }
  const method=(jread('nora-home-pay',{k:'wallet'})||{k:'wallet'}).k;
  if(method==='wallet'){
    if((u.wallet||0)<amount){toast('کیف پول کمتر از مبلغ است؛ درگاه را بزن یا کیف پول را شارژ کن'); return}
    u.wallet=(u.wallet||0)-amount; saveWalletUser(u);
  }
  if(m) addLib(m.id,{k:'past',past:pastId,t:m.t,kind:m.k});
  else (H.media||[]).forEach(x=>addLib(x.id,{k:'past',past:pastId,t:x.t,kind:x.k})), addLib(H.id,{k:'bundle',t:H.t});
  closeSheets(); toast('ثبت شد؛ «'+ (m?m.t:H.t) +'» در کتابخانهٔ تو نشست');
  document.dispatchEvent(new CustomEvent('nora:library'));
  if(m && (m.k==='video'||m.k==='audio')) player(pastId,m.id);
}

/* ── ورود: یک نسخهٔ کوچک برای خرید و کارهای نیازمند حساب ── */
function authSheet(after){
  const pend=jread('nora-home-auth',null)||null;
  const step=pend&&pend.step==='code'?'code':'phone', mob=(pend&&pend.mobile)||'';
  fillSheet('shAuth',`
    <div class="grabber"></div>
    <div class="row" style="align-items:center;margin-bottom:10px">
      <div><div class="head">${step==='code'?'کد تأیید':'ورود با شمارهٔ موبایل'}</div>
        <div class="cap">${step==='code'?'کد به '+(mob?'۰'+'۹…'+mob.slice(-4):'شماره‌ات')+' فرستادیم':'برای تهیه و کتابخانه لازم است؛ رمزی ندارد'}</div></div>
      <span class="sp"></span><button class="icon-btn" data-close aria-label="بستن"><svg class="i"><use href="#i-close"/></svg></button></div>
    ${step==='code'
      ? `<label class="lbl" for="uicode">کد پنج‌رقمی</label>
         <input class="input num" id="uicode" inputmode="numeric" placeholder="•••••" autocomplete="one-time-code"/>
         <div class="cap" style="margin-top:7px">کد نمایشی این نمونه: ۵۴۳۲۱</div>
         <div class="row" style="margin-top:12px"><button class="btn primary" data-uicode><svg class="i"><use href="#i-check"/></svg> ورود</button>
           <button class="btn quiet" data-uiback>تغییر شماره</button></div>`
      : `<label class="lbl" for="uimob">شمارهٔ موبایل</label>
         <input class="input num" id="uimob" inputmode="numeric" placeholder="۰۹۱۲۳۴۵۶۷۸۹" value="${escH(mob)}"/>
         <div class="row" style="margin-top:12px"><button class="btn primary" data-uiphone><svg class="i"><use href="#i-send"/></svg> فرستادن کد</button>
           <button class="btn quiet" data-close>بعداً</button></div>`}
    <p class="cap" style="margin-top:10px">بعد از ورود، خرید و کتابخانه‌ات همه‌جا هست؛ در خانه هم همان حساب را می‌بینی.</p>
    <p class="cap" style="margin-top:8px"><a href="login.html" style="font-weight:700">ورود با شمارهٔ موبایل و کد یک‌بارمصرف</a></p>`);
  if(typeof after==='function') authSheet.after=after;   /* از پله‌های ورود رد نشو */
  else if(authSheet.after===undefined) authSheet.after=null;
}
function authDone(){
  const after=authSheet.after; authSheet.after=null;
  closeSheets();
  if(typeof after==='function') setTimeout(after,60);
}

/* ── سنجاق و اشتراک مشترک ── */
function sharedPin(key,id){
  let a=jread('nora-home-pins',[]); if(!Array.isArray(a)) a=[];
  const k=key+':'+id;
  if(a.includes(k)) a=a.filter(x=>x!==k); else a.push(k);
  jwrite('nora-home-pins',a); return a.includes(k);
}
function sharedShare(id){
  const N=window.NORA||{};
  const e=(N.EVENTS||[]).find(x=>x.id===id)||(N.PAST||[]).find(x=>x.id===id);
  shareItem({title:(e?e.t:'رویداد نورا'),text:(e?(e.d||e.when||''):'رویداد گروه فرهنگی خط زندگی'),url:'https://lifeline1.ir/e/'+id});
}

/* ── جهت‌دهی منو بر پایهٔ صفحه ── */
function menuRoute(el){
  const N=window.NORA||{};
  if(el.dataset.uihref){ location.href=el.dataset.uihref; return }
  if(el.dataset.uiev){ eventSheet(el.dataset.uiev); return }
  const H=window.NORA_HOME;                          /* در خانه، خودِ صفحه صاحب ورقه‌هاست */
  const f=el.dataset.uif, j=el.dataset.uijump;
  if(f){
    if(f==='shAccount'){ location.href='account.html'; return }    /* حساب من صفحهٔ جدا دارد، نه ورقه */
    if(f==='shSupport'||f==='shFaq'){ location.href='support.html'; return }  /* راهنما و پشتیبانی، صفحهٔ خودش */
    if(f==='shInvite'){ location.href='account.html#invite'; return }
    if(f==='shClub'){ location.href='account.html#book'; return }      /* باشگاه کتاب زیر پروفایل من است */
    if(H&&H.openF){ H.openF(f); return }
    if(document.getElementById(f)){ uiOpen(f); return }
    const map={shClub:'club', shInvite:'me', shNotice:'notice', shVerify:'verify'};
    location.href='home.html#'+(map[f]||'menu'); return;
  }
  if(j){
    if(H){ closeSheets(); const t=document.getElementById(j); if(t){t.scrollIntoView({behavior:'smooth',block:'start'}); return} }
    else { const t=document.getElementById(j); if(t){closeSheets(); t.scrollIntoView({behavior:'smooth',block:'start'}); return} }
    const map={pastSec:'media', articles:'articles', teachers:'teachers', staff:'staff', partners:'partners'};
    location.href = (j==='pastSec') ? 'events.html?status=past' : 'home.html#'+j;
    return;
  }
  closeSheets();
}

/* ── باز کردن هر ورقهٔ مشترک ── */
function uiOpen(id){
  if(id==='shNotice'||id==='notice'){ fillSheet('shNotice',noticesSheet()); openSheet('shNotice'); return }
  if(id==='shMenu'||id==='menu'){ fillSheet('shMenu',menuSheet()); openSheet('shMenu'); return }
  if(id.sheet) return;
  openSheet(id);
}

/* ── رهگیری کلیک‌های مشترک: هر صفحه‌ای که ui.js را دارد ── */
document.addEventListener('click',e=>{
  const t=e.target;
  const nb=t.closest('[data-notice],[href$="#notice"]');
  if(nb){e.preventDefault(); uiOpen('shNotice'); return}
  const mb=t.closest('[data-menu],[href$="#menu"]');
  if(mb){e.preventDefault(); uiOpen('shMenu'); return}
  const mr=t.closest('[data-uihref],[data-uiev],[data-uif],[data-uijump]');
  if(mr){menuRoute(mr); return}
  const pd=t.closest('[data-uiperson]'); if(pd){location.href='home.html#p='+pd.dataset.uiperson; return}
  const pin=t.closest('[data-uipin]'); if(pin){const [k,i]=pin.dataset.uipin.split(':');
    toast(sharedPin(k,i)?'سنجاق شد':'از سنجاق درآمد'); return}
  const sh=t.closest('[data-uishare]'); if(sh){sharedShare(sh.dataset.uishare); return}
  const rd=t.closest('[data-uireadall]'); if(rd){
    ((window.NORA&&window.NORA.NOTICES)||[]).forEach(n=>markRead(n.t)); uiOpen('shNotice'); toast('همه خوانده شد'); return}
  const pr=t.closest('[data-uipre]'); if(pr){prereg(pr.dataset.uipre); return}
  const pv=t.closest('[data-uipreview]'); if(pv){preview(pv.dataset.uipreview); return}
  const md=t.closest('[data-uimedia]'); if(md){const [h,m]=md.dataset.uimedia.split(':'); player(h,m); return}
  const by=t.closest('[data-uibuy]'); if(by){const [h,m]=by.dataset.uibuy.split(':'); buySheet(h,m); return}
  const py=t.closest('[data-uipay]'); if(py){jwrite('nora-home-pay',{k:py.dataset.uipay});
    const [h,m]=((document.querySelector('[data-uipayyes]')||{}).dataset||{}).uipayyes.split(':'); buySheet(h,m); return}
  const pz=t.closest('[data-uipayyes]'); if(pz){const [h,m]=pz.dataset.uipayyes.split(':'); doBuy(h,m||null); return}
  const pl=t.closest('[data-uiplay]');
  if(pl){ if(pl.dataset.uiplay&&pl.dataset.uiplay!==PLAY.id){return}
    PLAY.playing=!PLAY.playing; playState(); playTick(); return }
  const sk=t.closest('[data-uiseek]');
  if(sk){const r=sk.getBoundingClientRect(); const x=(e.clientX-r.left)/r.width; PLAY.sec=Math.round(PLAY.len*(document.dir==='rtl'?1-x:x));
    setProgress(PLAY.id,PLAY.sec); playState(); return}
  const rt=t.closest('[data-uirate]'); if(rt){PLAY.rate=+rt.dataset.uirate;
    document.querySelectorAll('#shPlay [data-uirate]').forEach(b=>b.classList.toggle('on',b===rt)); toast('سرعت پخش: '+faN(PLAY.rate)+' برابر'); return}
  const dl=t.closest('[data-uidl]'); if(dl){toast('دانلود شروع شد؛ در پوشهٔ دانلود گوشی'); return}
  const op=t.closest('[data-uiopen]'); if(op){toast('فایل در تب تازه باز شد'); return}
  const ph=t.closest('[data-uiphone]'); if(ph){
    const v=unFa((document.getElementById('uimob')||{}).value||'').replace(/\D/g,'');
    if(!/^09\d{9}$/.test(v)){toast('شماره را کامل بنویس؛ ۱۱ رقم، با ۰۹'); return}
    jwrite('nora-home-auth',{step:'code',mobile:v}); authSheet(); return}
  const cd=t.closest('[data-uicode]'); if(cd){
    const v=unFa((document.getElementById('uicode')||{}).value||'').replace(/\D/g,'');
    if(v!=='54321'){toast('کد نمایشی ۵۴۳۲۱ است'); return}
    const pend=jread('nora-home-auth',null)||{};
    jwrite(SESS_KEY,{name:'سارا محمدی',mobile:pend.mobile||'',joined:'شهریور ۱۴۰۴',certs:2,wallet:1250000,msgs:1});
    jwrite('nora-home-auth',null); syncBell(); authDone(); toast('خوش آمدی؛ حالا خرید و کتابخانه در دسترس است'); return}
  const bk=t.closest('[data-uiback]'); if(bk){jwrite('nora-home-auth',{step:'phone',mobile:''}); authSheet(); return}
},false);

/* ── نشانی‌های مشترک: #notice · #menu · #media · #lib · ?ev=/id ── */
function uiHash(){
  const h=(location.hash||'').replace('#','');
  const P=new URLSearchParams(location.search);
  if(P.get('notice')||h==='notice') uiOpen('shNotice');
  if(P.get('menu')||h==='menu') uiOpen('shMenu');
  const eid=P.get('ev')||P.get('id');
  if(eid&&!document.getElementById('shEvent')) eventSheet(eid);
}
addEventListener('hashchange',uiHash);

/* ── راه‌اندازی پوستهٔ مشترک ── */
sheetA11y();
syncBell();
try{uiHash()}catch(e){}
/* ── نوار بالا: وقت اسکرول، شیشهٔ پررنگ‌تر می‌شود (همان حس نوار آی‌اواس) ──
   پیش‌تر فقط صفحهٔ خانه این کلاس را می‌گذاشت و نوار رویدادها همیشه مات
   می‌ماند؛ حالا هر صفحه‌ای که ui.js را دارد همین رفتار را دارد. */
(function(){
  let was=null;
  const sync=()=>{
    const on=(window.scrollY||window.pageYOffset||0)>10;
    if(on===was) return; was=on;
    document.documentElement.classList.toggle('atscroll',on);
  };
  addEventListener('scroll',sync,{passive:true});
  addEventListener('pageshow',sync);
  try{sync()}catch(e){}
})();

/* ── ساعت و تاریخ زنده: یک بار این‌جا، همهٔ صفحه‌ها از همین می‌خوانند ─────────
   هر عنصری که data-clock داشته باشد خودش پر می‌شود؛ «full» خط کامل با تاریخ
   و بقیه فقط ساعت. مرجع ساعت تهران است و اگر اینترنت بود انحرافش را می‌گیریم. */
const CLK={diff:0, state:'local', at:'', tried:false};
const clockNow=()=>Date.now()+(CLK.diff||0);
function clockParts(ms){
  const t=(ms==null)?clockNow():ms;
  let g=null,h=0,mi=0,s=0;
  try{
    const p=new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Tehran',hour12:false,
      hour:'2-digit',minute:'2-digit',second:'2-digit',year:'numeric',month:'2-digit',day:'2-digit'})
      .formatToParts(new Date(t)).reduce((o,x)=>(o[x.type]=x.value,o),{});
    h=NR(p.hour)%24; mi=NR(p.minute); s=NR(p.second);
    g={gy:NR(p.year), gm:NR(p.month), gd:NR(p.day)};
  }catch(e){
    const d=new Date(t);
    h=d.getHours(); mi=d.getMinutes(); s=d.getSeconds();
    g={gy:d.getFullYear(), gm:d.getMonth()+1, gd:d.getDate()};
  }
  const j=jalaliOf(g.gy,g.gm,g.gd);
  return {h:h, mi:mi, s:s, jy:j.jy, jm:j.jm, jd:j.jd};
}
const clockHM=()=>{const c=clockParts(); return fmtClock(c.h,c.mi)};
const clockFull=()=>{const c=clockParts(); return faJDate(c.jy,c.jm,c.jd)+' · '+fmtClock(c.h,c.mi)};
const clockDay=()=>{const c=clockParts(); return faJDate(c.jy,c.jm,c.jd)};
function paintClocks(){
  const list=document.querySelectorAll('[data-clock]');
  if(!list.length) return;
  const full=clockFull(), hm=clockHM();
  list.forEach(el=>{el.textContent=el.dataset.clock==='full'?full:hm});
}
async function netSyncClock(){
  if(CLK.tried||typeof fetch!=='function') return CLK.state;
  CLK.tried=true;
  const tries=[['https://worldtimeapi.org/api/timezone/Asia/Tehran',j=>NR(j.unixtime||0)*1000],
               ['https://timeapi.io/api/Time/current/zone?timeZone=Asia/Tehran',j=>NR(new Date(j.dateTime))]];
  for(const [u,pick] of tries){
    try{
      const r=await fetch(u,{cache:'no-store'}); if(!r.ok) continue;
      const j=await r.json(), t=pick(j);
      if(!t||Math.abs(t-Date.now())>31536000000) continue;
      CLK.diff=t-Date.now(); CLK.state='net'; CLK.at=clockHM(); paintClocks(); return CLK.state;
    }catch(e){}
  }
  CLK.state='local'; return CLK.state;
}
document.addEventListener('visibilitychange',()=>{if(!document.hidden) paintClocks()});
/* در محیط آزمایش تیک خودکار روشن نمی‌شود تا فرایند بسته شود؛ خود صفحه هم
   اگر عنصر ساعتی نداشت، تیک کنار می‌رود */
const NO_TICK=(typeof navigator!=='undefined'&&/jsdom/i.test(String(navigator.userAgent||'')));
let clkTimer=null;
function clockBeat(){
  if(!document.querySelector('[data-clock]')){ if(clkTimer){clearInterval(clkTimer); clkTimer=null} return }
  paintClocks();
}
paintClocks();
netSyncClock().then(paintClocks);
if(!NO_TICK) clkTimer=setInterval(clockBeat,1000);

/* ── انبار فرم‌ها: فرم‌ساز می‌نویسد، پنل رویداد و گزارش می‌خوانند ───────────
   هر فرم یک ردیف است با شناسه، نام، جای پیوند به رویداد (ev) و کلیدهای سینک. */
const FORMS_KEY='nora-forms';
function formsAll(){
  try{const a=JSON.parse(localStorage.getItem(FORMS_KEY)||'[]'); return Array.isArray(a)?a:[]}catch(e){return []}
}
function formsAnnounce(){try{dispatchEvent(new CustomEvent('nora-forms-changed'))}catch(e){}}
function formsSave(list){try{localStorage.setItem(FORMS_KEY,JSON.stringify(list))}catch(e){}; formsAnnounce()}
function formById(id){return formsAll().find(f=>String(f.id)===String(id))||null}
function formPut(f){
  const list=formsAll(), i=list.findIndex(x=>String(x.id)===String(f.id));
  const row=Object.assign({}, i>=0?list[i]:{}, f, {at:Date.now()});
  if(i>=0) list[i]=row; else list.unshift(row);
  formsSave(list); return row;
}
function formPatch(id,patch){
  const f=formById(id); if(!f) return null;
  return formPut(Object.assign({},f,patch,{sync:Object.assign({},f.sync||{},(patch||{}).sync||{})}));
}
function formDrop(id){formsSave(formsAll().filter(f=>String(f.id)!==String(id)))}
function formsFor(evId){return formsAll().filter(f=>f.ev&&String(f.ev)===String(evId))}
/* نظرسنجی آمادهٔ نورا: پیشفرضِ هر رویداد؛ بی آنکه کسی چیزی بسازد،
   بعد از برنامه همین پرسشها از شرکتکننده میآید. فرم اختصاصی هم دست خود سازنده. */
const AUTO_SURVEY={id:'auto', name:'نظرسنجی آمادهٔ نورا', kind:'نظرسنجی',
  questions:['برنامهٔ امروز چطور بود؟','کدام بخش بیشتر به دلت نشست؟','چه چیزی کم داشت؟','به دوستانت پیشنهادش می‌کنی؟'],
  intro:'نظرت بی‌نام ثبت شد؛ برای بهتر شدن برنامهٔ بعدی خوانده می‌شود.'};
addEventListener('storage',e=>{if(e.key===FORMS_KEY) formsAnnounce()});
addEventListener('nora-forms-changed',()=>{});

/* ── مطلب‌ها: انبار مشترکِ سازنده و خواننده ────────────────────────────────
   مطلب در پنل، بخش «مطلب‌ها» بلوکی ساخته می‌شود: پاراگراف، تیتر، عکس،
   ویدیو (آپارات، یوتیوب یا فایل)، صدا، نقل قول، فهرست، دکمهٔ لینک،
   جعبهٔ توجه، جمع‌شونده و جداکننده؛ هر کدام هر چند تا و به هر ترتیب.
   رویداد و فرم هم می‌توانند به مطلب پیوند بخورند. */
const POSTS_KEY='nora-posts';
function postsAll(){
  try{const a=JSON.parse(localStorage.getItem(POSTS_KEY)||'[]'); return Array.isArray(a)?a:[]}catch(e){return []}
}
function postsAnnounce(){try{dispatchEvent(new CustomEvent('nora-posts-changed'))}catch(e){}}
function postsSave(list){try{localStorage.setItem(POSTS_KEY,JSON.stringify(list))}catch(e){}; postsAnnounce()}
function postById(id){return postsAll().find(p=>String(p.id)===String(id))||null}
function postPut(p){
  const list=postsAll(), i=list.findIndex(x=>String(x.id)===String(p.id));
  const row=Object.assign({}, i>=0?list[i]:{}, p, {at:p.at||Date.now()});
  if(i>=0) list[i]=row; else list.unshift(row);
  postsSave(list); return row;
}
function postPatch(id,patch){const p=postById(id); if(!p) return null; return postPut(Object.assign({},p,patch))}
function postDrop(id){postsSave(postsAll().filter(p=>String(p.id)!==String(id)))}
function postsPub(){return postsAll().filter(p=>p.pub&&!p.pend)}
/* زمان خواندن: هر ۱۷۰ واژه فارسی یک دقیقه؛ ویدیو و صدا و عکس هم اضافه می‌کنند */
function postMin(p){
  const bs=(p&&p.blocks)||[];
  const words=(String(p&&p.lead||'')+' '+bs.map(b=>{if(!b) return '';
    return Array.isArray(b.x)?b.x.join(' '):(b.x||b.t||b.by||b.cap||'')}).join(' '))
    .trim().split(/\s+/).filter(Boolean).length;
  const heavy=bs.filter(b=>b&&['vid','aud'].indexOf(b.ty)>-1).length;
  const imgs=bs.filter(b=>b&&b.ty==='img').length;
  return Math.max(1,Math.round(words/170+heavy*1.5+imgs*0.15));
}
/* شکل کارت مطلب برای خانهٔ کاربر؛ همان‌قدر خودی که نمونه‌های ثابت‌اند */
function postsFeed(){return postsPub().map(p=>({id:p.id, t:p.t||'بی نام', cat:p.cat||'مطلب',
  min:p.min||postMin(p), lead:p.lead||'', who:p.author||'', cov:(p.cover&&p.cover.up)||'',
  g:(p.cover&&p.cover.g)||'linear-gradient(135deg,#1E6FD0,#0A3A82)',
  tags:(p.tags||[]).slice(0,2), pin:!!p.pin, club:!!p.club, views:faN(+p.views||0), mine:1}))}
/* تاریخ مطلب: «جمعه ۴ مهر» از زمان انتشار */
const postDate=at=>{try{const g=new Date(at||Date.now()), j=jalaliOf(g.getFullYear(),g.getMonth()+1,g.getDate());
  return faJDate(j.jy,j.jm,j.jd)}catch(e){return ''}};
/* شمار بازدید: در هر نشست یک بار برای هر مطلب */
function postView(id){
  let seen=false;
  try{seen=!!sessionStorage.getItem('nora-pv-'+id)}catch(e){}
  if(seen) return;
  const p=postById(id); if(!p) return;
  postPatch(id,{views:(+p.views||0)+1});
  try{sessionStorage.setItem('nora-pv-'+id,'1')}catch(e){}
  /* گزارش خواندن: در هر نشست، عنوان و مدتی که همین برگه باز ماند */
  const t0=Date.now();
  const rec=()=>{try{
    const a=JSON.parse(localStorage.getItem('nora-pvlog')||'[]');
    const min=Math.max(1,Math.round((Date.now()-t0)/60000));
    a.unshift({id:String(id), at:t0, min:min, t:(p.t||'')});
    localStorage.setItem('nora-pvlog',JSON.stringify(a.slice(0,60)));
  }catch(e){}};
  addEventListener('beforeunload',rec,{once:true});
  setTimeout(()=>{try{document.addEventListener('visibilitychange',()=>{if(document.hidden)rec()},{once:true})}catch(e){}},0);
  /* در محیط آزمایش هیچ ترکی نمیآید؛ همین حالا بنشین تا شمارش دودویی نماند */
  if(typeof navigator!=='undefined'&&/jsdom/i.test(String(navigator.userAgent||''))) rec();
}
function postReads(id){
  try{const a=JSON.parse(localStorage.getItem('nora-pvlog')||'[]');
    return a.filter(x=>String(x.id)===String(id))}catch(e){return []}
}

/* ── رویدادهای منتشرشدهٔ پنل: همان انبار مدیر، دست کاربر هم می‌آید ─────────
   ردیف پنل را به شکل صفحه‌های کاربر برمی‌گردانیم تا در فهرست رویدادها،
   برگهٔ رویداد و ورقهٔ کلیات همان‌قدر خودی باشند که نمونه‌های ثابت‌اند.
   وضعیت از خود تاریخ‌ها درمی‌آید: از روز جلسهٔ اول تا پایانِ آخرین جلسه
   «در حال برگزاری»، بعدش در برگزارشده‌ها. */
const PUB_GRAD='linear-gradient(135deg,#1E6FD0,#0A3A82)';
/* جمع مبالغ فرم با تخفیف: همان حساب پنل، تا مبلغ رویداد زنده عوض شود */
const formsMoney=f=>{const fin=(f&&f.fin)||[]; if(!fin.length) return 0;
  return fin.reduce((n,o)=>n+(o.off?Math.round(+o.p*(100-+o.off)/100):(+o.p||0)),0)};
const JM_KEY=['','','','','','','sh','mehr','aban','','','',''];
const JM_NAME=['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
function pubEvents(){
  let added=null;
  try{const a=JSON.parse(localStorage.getItem('nora-admin')||'null');
    if(a&&Array.isArray(a.added)) added=a.added;}catch(e){}
  if(!added||!added.length) return [];
  const c=clockParts(), today=j2d(c.jy,c.jm,c.jd), nowMin=c.h*60+c.mi;
  const dOf=s=>{const p=parseJ(s); return p?j2d(p.jy,p.jm,p.jd):null};
  const tOf=s=>{const p=parseJ('1400/01/01، '+String(s||'')); return p?(p.hh*60+p.mm):null};
  return added.map(ev=>{
    if(!ev||!ev.id) return null;
    const ses=(ev.sess||[]).filter(x=>x&&parseJ(x.d));
    const first=dOf(ses.length?ses[0].d:ev.on)||dOf(ev.on);
    const last=dOf(ses.length?ses[ses.length-1].d:(ev.end||ev.on))||first;
    const endMin=(ses.length?(tOf(ses[ses.length-1].to)||tOf(ses[ses.length-1].t)):null)
      ||tOf(ev.time)||1439;
    const past=ev.held?true:(last!=null&&(today>last||(today===last&&nowMin>=endMin)));
    const live=!past&&first!=null&&today>=first;
    const fj=parseJ(ses.length?ses[0].d:ev.on)||parseJ(ev.on)||null;
    const jm=fj?fj.jm:7, dn=fj?fj.jd:1;
    const nSes=Math.max(+ev.sessions||0,ses.length,1);
    const place=ev.place||'';
    const online=!place||place==='آنلاین'||/^https?:/i.test(place);
    /* فرمهای وصلشده زنده خوانده میشوند: فرمی که بعد از انتشار در فرمساز
       ساخته یا عوض شود، همین لحظه روی رویداد مینشیند؛ مبلغ هم از خود فرم */
    const lf=formsFor(String(ev.id));
    const regF=lf.find(x=>(x.need||'reg')==='reg');
    const liveMoney=regF?formsMoney(regF):null;
    const base={id:String(ev.id), t:ev.n||'برنامه', kind:ev.kind||'برنامه',
      when:ev.when||(fj?faJDate(fj.jy,fj.jm,fj.jd):''), time:ev.time||'',
      place:online?'آنلاین':place, mode:online?'آنلاین':'حضوری',
      price:(liveMoney!=null&&liveMoney>0)?liveMoney:(+ev.price||0), cap:+ev.cap||0, taken:+ev.reg||0,
      spots:Math.max(0,(+ev.cap||0)-(+ev.reg||0)),
      poster:ev.posterUp||(ev.poster?('posters/'+ev.poster):''), g:PUB_GRAD,
      d:ev.about||ev.rep||'', tags:ev.held?[]:['جدید'], club:false,
      sess:nSes, dm:JM_KEY[jm]||'mehr', dn:dn, mname:JM_NAME[jm-1]||'',
      ord:0, live:live, pub:true, pubPast:past, forms:ev.forms||[],
      tchr:'', icon:'i-calendar', day:'', pre:false, pin:false, cert:ev.held?false:undefined};
    if(past){
      base.past=true; base.mediaCount=0; base.media=[]; base.who=+ev.who||0;
      base.album=ev.media||'';
      base.rec=nSes>1?(faN(nSes)+' جلسه برگزار شد'):'برگزاری پایان یافت';
      base.d=ev.rep||base.d; base.sold=+ev.who||0; base.price=0; base.access='آرشیو رویداد';
    }
    return base;
  }).filter(Boolean);
}

window.NORA_UI=Object.assign(window.NORA_UI||{}, {shareItem:shareItem,copyText:copyText,toast:toast,sheetA11y:sheetA11y,
  rialTxt:rialTxt,
  uiOpen:uiOpen,eventSheet:eventSheet,mediaList:mediaList,bundleCard:bundleCard,player:player,buySheet:buySheet,doBuy:doBuy,
  authSheet:authSheet,uid:uid,prereg:prereg,isPre:isPre,preview:preview,library:library,addLib:addLib,hasLib:hasLib,progressOf:progressOf,setProgress:setProgress,
  unreadCount:unreadCount,markRead:markRead,syncBell:syncBell,menuSheet:menuSheet,noticesSheet:noticesSheet,LIB_KEY:LIB_KEY,
  profile:profile,saveProfile:saveProfile,profilePercent:profilePercent,profileMissing:profileMissing,
  fillTrust:fillTrust,trustPick:trustPick,
  uiSet:uiSet,uiSetSave:uiSetSave,UISET_META:UISET_META,menuAllowed:menuAllowed,uiSetDef:UISET_DEF,
  levelOf:levelOf,sessUser:sessUser,phoneOf:phoneOf,PROF_KEY:PROF_KEY,
  clockNow:clockNow,clockParts:clockParts,clockHM:clockHM,clockFull:clockFull,clockDay:clockDay,
  clockState:()=>CLK.state,clockAt:()=>CLK.at,netSyncClock:netSyncClock,
  FORMS_KEY:FORMS_KEY,formsAll:formsAll,formById:formById,formPut:formPut,formPatch:formPatch,
  formDrop:formDrop,formsFor:formsFor,pubEvents:pubEvents,autoSurvey:AUTO_SURVEY,
  POSTS_KEY:POSTS_KEY,postsAll:postsAll,postsPub:postsPub,postById:postById,postPut:postPut,
  postPatch:postPatch,postDrop:postDrop,postsFeed:postsFeed,postMin:postMin,postDate:postDate,postView:postView,postReads:postReads});

/* ── کارگر سرویس: نصب‌شدنی و کار در بی‌اتصالی ── */
if('serviceWorker' in navigator){
  addEventListener('load',()=>{
    /* نسخهٔ کش‌شدهٔ کهنه نماند: هر بار بارگذاری، تازه‌ترین کارگر سرویس را می‌خواهیم */
    navigator.serviceWorker.register('sw.js',{updateViaCache:'none'}).then(reg=>{
      try{reg.update()}catch(e){}
      const wake=w=>{ try{w.postMessage({k:'skip'})}catch(e){} };
      if(reg.waiting) wake(reg.waiting);
      reg.addEventListener('updatefound',()=>{
        const w=reg.installing; if(!w) return;
        w.addEventListener('statechange',()=>{
          if(w.state==='installed'&&navigator.serviceWorker.controller) wake(w);
        });
      });
      /* کش کهنه: هر کلیدی که با نسخهٔ کنونی نمی‌خواند، می‌رود */
      if(window.caches&&caches.keys) caches.keys().then(ks=>ks.forEach(k=>{ if(k!=='nora-v63') caches.delete(k) })).catch(()=>{});
    }).catch(()=>{});
  });
  const offlineBar=(on)=>{
    let el=document.getElementById('offBar');
    if(!on){if(el) el.remove(); return}
    if(el) return;
    el=document.createElement('div');
    el.id='offBar'; el.setAttribute('role','status');
    el.textContent='بی‌اتصالی؛ نسخهٔ ذخیره‌شده را می‌بینی';
    document.body.appendChild(el);
  };
  addEventListener('offline',()=>offlineBar(true));
  addEventListener('online',()=>offlineBar(false));
  if(!navigator.onLine) offlineBar(true);
}

/* ── کشیدن برای تازه‌سازی: فقط بالای صفحه و بیرون از ورقه‌ها ── */
(function pullToRefresh(){
  let y0=0,x0=0,dy=0,arm=false,busy=false,el=null;
  const coarse=matchMedia('(pointer:coarse)').matches;
  if(!coarse) return;
  const pill=()=>{
    if(!el){el=document.createElement('div'); el.id='ptr'; el.setAttribute('role','status');
      el.textContent='برای تازه‌سازی بکش'; document.body.appendChild(el)}
    return el;
  };
  addEventListener('touchstart',e=>{
    if(busy||document.querySelector('.sheet.on')) return;
    if((window.scrollY||document.documentElement.scrollTop)>0) return;
    if(e.touches.length!==1) return;
    y0=e.touches[0].clientY; x0=e.touches[0].clientX; arm=true; dy=0;
  },{passive:true});
  addEventListener('touchmove',e=>{
    if(!arm||e.touches.length!==1) return;
    const y=e.touches[0].clientY, x=e.touches[0].clientX;
    dy=y-y0;
    if(dy<=0||Math.abs(dy)<Math.abs(x-x0)*1.5){if(dy<0) arm=false; return}
    const d=Math.min(dy,110), p=pill();
    p.style.transform='translate(-50%,'+(-46+d*0.55)+'px)';
    p.style.opacity=String(Math.min(1,d/60));
    p.textContent=d>70?'ولش کن تا تازه شود':'برای تازه‌سازی بکش';
    if(e.cancelable) e.preventDefault();
  },{passive:false});
  addEventListener('touchend',()=>{
    if(!arm) return; arm=false;
    if(dy>70&&!busy){
      busy=true; const p=pill();
      p.textContent='دارد تازه می‌شود…'; p.style.transform='translate(-50%,10px)'; p.style.opacity='1';
      const done=()=>{p.textContent='تازه شد'; p.style.opacity='0';
        setTimeout(()=>{busy=false},300)};
      try{ (window.NORA_REFRESH||(()=>{}))(); }catch(err){}
      setTimeout(done,520);
    } else if(el){ el.style.opacity='0' }
    dy=0;
  },{passive:true});
})();
/* پوستهٔ کاربر: اندازه و چیدمان و رنگ، همه از تنظیمهای پنل؛ ui.js در
   همهٔ صفحهها هست و پیش از رندر نشانهها را روی <html> میگذارد. پنل
   مدیران مستثناست تا ابزار خودش همیشه یکدست بماند. */
(function(){try{
  if(document.getElementById('admNav')) return;
  const U=uiSet()||{}, de=document.documentElement, T=U.type||{};
  de.dataset.cards=U.cards||'mid';
  if(T.size&&T.size!=='mid') de.dataset.textsize=T.size;
  if(T.radius&&T.radius!=='mid') de.dataset.radius=T.radius;
  if(T.width&&T.width!=='mid') de.dataset.width=T.width;
  if(T.density&&T.density!=='mid') de.dataset.density=T.density;
  if(T.accent) de.dataset.accent=T.accent;
  if(T.motion===0) de.dataset.motion='off';
}catch(e){}})();
