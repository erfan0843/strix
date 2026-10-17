/* ══════════════════════════════════════════════════════════════════════════
   نورا، موتور مشترک صفحه‌ها
   هر چیزی که در بیش از یک صفحه لازم است، همین‌جا نوشته می‌شود:
   اعداد و حروف، انتخاب‌گرها، داده‌های ایران، کیوآرکد، و ابزارهای رابط.
   ══════════════════════════════════════════════════════════════════════════ */

/* ── عدد و حروف ───────────────────────────────────────────────────────── */
const NORA_TEST_FIXTURE_MODE=window.__NORA_TEST_FIXTURE_MODE__===true;
const NR=Number;
const fa=n=>NR(n).toLocaleString('fa-IR');
const faN=n=>String(NR(n)).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
const unFa=s=>String(s).normalize('NFKC').replace(/[۰-۹]/g,d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/[٠-٩]/g,d=>'٠١٢٣٤٥٦٧٨٩'.indexOf(d));
function parseLocalizedNumber(value){
  let normalized=String(value==null?'':value).normalize('NFKC')
    .replace(/[۰-۹]/g,d=>String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
    .replace(/[٠-٩]/g,d=>String('٠١٢٣٤٥٦٧٨٩'.indexOf(d))).trim();
  const decimal=normalized.split(/[٫.]/);if(decimal.length>2)return null;
  let integer=decimal[0],fraction=decimal.length===2?decimal[1]:undefined,sign='';
  if(/^[+-]/.test(integer)){sign=integer[0];integer=integer.slice(1)}
  if(/[+-]/.test(integer+(fraction||'')))return null;
  if(/[٬,]/.test(integer)){
    const separators=[...new Set(integer.match(/[٬,]/g))];if(separators.length!==1)return null;
    const groups=integer.split(separators[0]);
    if(!groups[0]||groups[0].length>3||!/^\d+$/.test(groups[0])||groups.slice(1).some(group=>!/^\d{3}$/.test(group)))return null;
    integer=groups.join('');
  }
  if(integer&&!/^\d+$/.test(integer))return null;
  if(fraction!==undefined&&fraction&&!/^\d+$/.test(fraction))return null;
  if(!integer&&!(fraction!==undefined&&fraction))return null;
  const number=Number(sign+(integer||'0')+(fraction!==undefined?'.'+fraction:''));
  return Number.isFinite(number)?number:null;
}
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
const UNIVERSITY_DATA_SRC='universities-data.js?v=2';
let UNIVERSITY_DATA_PROMISE=null;
const EMPTY_UNIVERSITY_DATA=Object.freeze({});
function universitiesLoaded(){
  const root=typeof window==='undefined'?globalThis:window, data=root.NORA_UNIVERSITIES_BY_PROVINCE;
  return !!data&&typeof data==='object'&&!Array.isArray(data)&&Object.keys(data).length>0;
}
function universitiesByProvince(){
  const root=typeof window==='undefined'?globalThis:window;
  return universitiesLoaded()?root.NORA_UNIVERSITIES_BY_PROVINCE:EMPTY_UNIVERSITY_DATA;
}
function loadUniversities(){
  const root=typeof window==='undefined'?globalThis:window;
  if(universitiesLoaded())return Promise.resolve(root.NORA_UNIVERSITIES_BY_PROVINCE);
  if(UNIVERSITY_DATA_PROMISE)return UNIVERSITY_DATA_PROMISE;
  if(!root.document||!root.document.createElement)return Promise.reject(new Error('University data requires a document'));
  UNIVERSITY_DATA_PROMISE=new Promise((resolve,reject)=>{
    const script=root.document.createElement('script');
    script.src=UNIVERSITY_DATA_SRC;script.async=true;script.dataset.noraUniversities='1';
    script.onload=()=>universitiesLoaded()?resolve(root.NORA_UNIVERSITIES_BY_PROVINCE):reject(new Error('University data is empty'));
    script.onerror=()=>{script.remove();reject(new Error('University data failed to load'))};
    (root.document.head||root.document.body||root.document.documentElement).appendChild(script);
  }).catch(error=>{UNIVERSITY_DATA_PROMISE=null;throw error});
  return UNIVERSITY_DATA_PROMISE;
}
const JOBS=['کارمند دولت','کارمند شرکت خصوصی','آزاد و صاحب کسب‌وکار','مهندس','پزشک و پرستار','معلم و استاد','دانشجو','هنرمند و رسانه','نیروی نظامی و انتظامی','کشاورز','راننده','فروشنده و بازاریاب','برنامه‌نویس و فناوری اطلاعات','حسابدار و مالی','وکیل و کارشناس حقوقی','راهنما و گردشگری','خانه‌دار','بازنشسته','جویای کار','سایر'];
const EDU=['زیر دیپلم','دیپلم','کاردانی','کارشناسی','کارشناسی ارشد','دکترا','حوزوی','دانش‌آموز'];
const EVENTKIT={provinces:Object.keys(PROVINCES),jobs:JOBS,edu:EDU};

/* ── انتخاب‌گرها: بدون تایپ اجباری و با تاریخ شمسی کامل ─────────────────── */
const JALALI_BREAKS=[-61,9,38,199,426,686,756,818,1111,1181,1210,1635,2060,2097,2192,2262,2324,2394,2456,3178];
const CURRENT_JY=(()=>{try{return Number(new Intl.DateTimeFormat('en-US-u-ca-persian-nu-latn',{year:'numeric'}).formatToParts(new Date()).find(part=>part.type==='year')?.value)||1405;}catch{return new Date().getFullYear()-621;}})();
/* تاریخ‌های معمولی (از جمله تولد) از امروز به گذشته مرتب‌اند؛ تاریخ‌وساعت آینده را زودتر می‌آورد. */
const CAL=[
  ...Array.from({length:126},(_,i)=>CURRENT_JY-i),
  ...Array.from({length:95},(_,i)=>CURRENT_JY+1+i)
];
const CAL_FUTURE_FIRST=[
  ...Array.from({length:96},(_,i)=>CURRENT_JY+i),
  ...Array.from({length:125},(_,i)=>CURRENT_JY-1-i)
];
const MH=[31,31,31,31,31,31,30,30,30,30,30,29];
function leap(y){
  y=NR(y);if(y<JALALI_BREAKS[0]||y>=JALALI_BREAKS[JALALI_BREAKS.length-1])return false;
  let jp=JALALI_BREAKS[0],jm=0,jump=0,leapJ=-14;
  for(let i=1;i<JALALI_BREAKS.length;i++){
    jm=JALALI_BREAKS[i];jump=jm-jp;if(y<jm)break;
    leapJ+=Math.floor(jump/33)*8+Math.floor((jump%33)/4);jp=jm;
  }
  let n=y-jp;leapJ+=Math.floor(n/33)*8+Math.floor((n%33+3)/4);
  if(jump%33===4&&jump-n===4)leapJ++;
  const gy=y+621,leapG=Math.floor(gy/4)-Math.floor((Math.floor(gy/100)+1)*3/4)-150;
  if(jump-n<6)n=n-jump+Math.floor((jump+4)/33)*33;
  let cycle=((n+1)%33-1)%4;if(cycle===-1)cycle=4;
  return cycle===0;
}
const daysOf=(y,m)=>m===12?(leap(y)?30:29):(Number.isInteger(Number(m))&&Number(m)>=1&&Number(m)<=11?MH[Number(m)-1]:0);
const MONTHS=['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];

function sel(html){return html;}
/* مقدارها همیشه لاتین‌اند تا محاسبه دقیق بماند؛ نمایش، فارسی */
function opts(list,cur,label){return list.map(v=>`<option value="${unFa(v)}" ${String(unFa(v))===String(unFa(cur))?'selected':''}>${label?label(v):v}</option>`).join('');}
const faDigits=s=>String(s).replace(/[0-9]/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
function withPlaceholder(list,cur,label,hint){
  const value=String(cur==null?'':cur),selected=value===''?' selected':'';
  return `<option value=""${selected}>${hint}</option>`+opts(list,value,label);
}

/* ساخت یک انتخاب‌گر تاریخ/ساعت/تاریخ‌وساعت */
function pickHTML(kind,value,id){
  return `<div class="pick" data-pick="${escAttr(kind)}" data-val="${escAttr(value||'')}" ${id?`id="${escAttr(id)}"`:''}>
    <select class="input pk1 hide-wheel" aria-label="سال"></select>
    <select class="input pk2" aria-label="ماه"></select>
    <select class="input pk3" aria-label="روز"></select>
    <select class="input pk4" aria-label="ساعت"></select>
    <select class="input pk5" aria-label="دقیقه"></select>
  </div>`;
}
function splitPickValue(kind,value){
  const text=unFa(value||'').trim();if(kind==='time')return {date:'',time:text};if(kind==='date')return {date:text,time:''};
  for(const marker of [' ساعت ','—'])if(text.includes(marker)){const i=text.indexOf(marker);return {date:text.slice(0,i).trim(),time:text.slice(i+marker.length).trim()};}
  const parts=text.split(' ');return parts.length>1?{date:parts[0],time:parts[parts.length-1]}:{date:text,time:''};
}
function pickFill(el){
  const kind=el.dataset.pick,{date:datePart,time:timePart}=splitPickValue(kind,el.dataset.val||'');
  const dp=(datePart||'').split(/[/.]/),tp=(timePart||'').split(':');
  const rawYear=NR(dp[0]),rawMonth=NR(dp[1]),rawDay=NR(dp[2]);
  const y=CAL.includes(rawYear)?rawYear:'',m=y&&rawMonth>=1&&rawMonth<=12?rawMonth:'',d=m&&rawDay>=1&&rawDay<=daysOf(y,m)?rawDay:'';
  const rawHour=NR(tp[0]),rawMinute=NR(tp[1]),completeTime=tp.length===2&&tp[0]!==''&&tp[1]!=='';
  const hh=rawHour>=0&&rawHour<=23&&completeTime?rawHour:'',mm=rawMinute>=0&&rawMinute<=59&&completeTime?rawMinute:'';
  const g=c=>el.querySelector(c);
  const years=kind==='datetime'?CAL_FUTURE_FIRST:CAL;
  g('.pk1').innerHTML=withPlaceholder(years,y,faN,'سال را انتخاب کنید');
  g('.pk2').innerHTML=withPlaceholder(Array.from({length:12},(_,i)=>i+1),m,i=>MONTHS[i-1],'ماه را انتخاب کنید');
  g('.pk3').innerHTML=withPlaceholder(y&&m?Array.from({length:daysOf(y,m)},(_,i)=>i+1):[],d,faN,'روز را انتخاب کنید');
  g('.pk4').innerHTML=withPlaceholder(Array.from({length:24},(_,i)=>i),hh,i=>faDigits(String(i).padStart(2,'0')),'ساعت را انتخاب کنید');
  g('.pk5').innerHTML=withPlaceholder(Array.from({length:60},(_,i)=>i),mm,i=>faDigits(String(i).padStart(2,'0')),'دقیقه را انتخاب کنید');
  g('.pk2').disabled=!y;g('.pk3').disabled=!(y&&m);g('.pk5').disabled=hh==='';
  const show={date:[1,1,1,0,0],time:[0,0,0,1,1],datetime:[1,1,1,1,1]}[kind]||[1,1,1,0,0];
  ['.pk1','.pk2','.pk3','.pk4','.pk5'].forEach((c,i)=>{g(c).style.display=show[i]?'':'none'});
  g('.pk1').addEventListener('change',()=>refillDays(el));
  g('.pk2').addEventListener('change',()=>refillDays(el));
  g('.pk4').addEventListener('change',()=>{const minute=g('.pk5');minute.disabled=!g('.pk4').value;if(minute.disabled)minute.value='';});
}
/* با عوض شدن سال یا ماه، روزهای معتبر همان تاریخ شمسی نمایش داده می‌شوند. */
function refillDays(el){
  const year=NR(unFa(el.querySelector('.pk1').value)),month=NR(unFa(el.querySelector('.pk2').value));
  const monthEl=el.querySelector('.pk2'),dayEl=el.querySelector('.pk3'),validYear=CAL.includes(year);
  monthEl.disabled=!validYear;if(!validYear)monthEl.value='';
  const validMonth=validYear&&month>=1&&month<=12;
  if(!validMonth){dayEl.innerHTML=withPlaceholder([],'',faN,'روز را انتخاب کنید');dayEl.value='';dayEl.disabled=true;return;}
  const max=daysOf(year,month),current=NR(unFa(dayEl.value)),selected=current>=1&&current<=max?current:'';
  dayEl.innerHTML=withPlaceholder(Array.from({length:max},(_,i)=>i+1),selected,faN,'روز را انتخاب کنید');dayEl.disabled=false;
}
function pickVal(el){
  const g=c=>unFa(el.querySelector(c).value),pad=n=>n===''?'':String(n).padStart(2,'0');
  const date=`${g('.pk1')}/${pad(g('.pk2'))}/${pad(g('.pk3'))}`,time=`${pad(g('.pk4'))}:${pad(g('.pk5'))}`;
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
function geoCityOptions(province,selected=''){
  const cities=PROVINCES[province]||[], known=cities.includes(selected), hint=province?'شهر را انتخاب کنید':'اول استان را انتخاب کنید';
  return `<option value="" ${known||selected?'':'selected'}>${hint}</option>${opts(cities,known?selected:'')}`+
    `<option value="__other__" ${selected&&!known?'selected':''}>شهرم در فهرست نیست</option>`;
}
function geoHTML(idPrefix,val){
  const empty=String(idPrefix||'')==='', rawProvince=val&&Object.prototype.hasOwnProperty.call(val,'p')
    ?String(val.p||''):(empty?'':'تهران'), rawCity=val&&Object.prototype.hasOwnProperty.call(val,'c')?String(val.c||''):(empty?'':'تهران');
  const p=EVENTKIT.provinces.includes(rawProvince)?rawProvince:'', cities=PROVINCES[p]||[], knownCity=cities.includes(rawCity);
  const cityChoice=knownCity?rawCity:p&&rawCity?'__other__':'', otherCity=cityChoice==='__other__'?rawCity:'';
  return `<div class="pick geo" role="group" aria-label="استان و شهر" data-geo="${escAttr(idPrefix)}" data-p="${escAttr(p)}" data-c="${escAttr(rawCity)}">
    <select class="input gp" aria-label="استان">${empty||!p?`<option value="" ${p?'':'selected'}>استان را انتخاب کنید</option>`:''}${opts(EVENTKIT.provinces,p)}</select>
    <select class="input gc" aria-label="شهر" ${p?'':'disabled'}>${geoCityOptions(p,knownCity?rawCity:cityChoice)}</select>
    <input class="input other geo-other" type="text" aria-label="نام شهر" maxlength="80" autocomplete="off"
      placeholder="نام شهرتان را بنویسید" style="display:${cityChoice==='__other__'?'':'none'}" value="${escAttr(otherCity)}"/></div>`;
}
function geoFill(el){
  const province=el.querySelector('.gp'),city=el.querySelector('.gc'),other=el.querySelector('.geo-other');
  const validProvince=()=>Object.prototype.hasOwnProperty.call(PROVINCES,province.value);
  const showOther=event=>{
    const visible=city.value==='__other__';other.style.display=visible?'':'none';
    if(visible&&event&&event.isTrusted)other.focus();else if(!visible)other.value='';
  };
  city.disabled=!validProvince();other.style.display=city.value==='__other__'?'':'none';
  province.addEventListener('change',()=>{
    const p=validProvince()?province.value:'';city.disabled=!p;
    city.innerHTML=geoCityOptions(p);other.value='';other.style.display='none';
  });
  city.addEventListener('change',showOther);
}
function initGeo(root){(root||document).querySelectorAll('.geo').forEach(el=>{if(el.dataset.ready)return;el.dataset.ready='1';geoFill(el)})}
function normalizeUniversityText(value){
  return String(value||'').normalize('NFKC').replace(/[يى]/g,'ی').replace(/ك/g,'ک')
    .replace(/\u200c/g,' ').toLocaleLowerCase().replace(/\s+/g,' ').trim();
}
function parseUniversityValue(value){
  const text=String(value||'').trim(),marker=' · ',at=text.indexOf(marker);
  if(at>=0){
    const province=text.slice(0,at).trim(),name=text.slice(at+marker.length).trim();
    if(Object.prototype.hasOwnProperty.call(PROVINCES,province))return {province,name};
    return {province:'',name:text};
  }
  const normalized=normalizeUniversityText(text);
  if(normalized){
    const data=universitiesByProvince();
    for(const province of EVENTKIT.provinces){
      if((data[province]||[]).some(name=>normalizeUniversityText(name)===normalized))return {province,name:text};
    }
  }
  return {province:'',name:text};
}
function universityPicker(el){
  if(!el)return null;
  return el.matches&&el.matches('.uni-pick')?el:el.querySelector('.uni-pick')||el;
}
function universityValue(el){
  const picker=universityPicker(el);if(!picker)return '';
  const province=picker.querySelector('.up')?.value||'',selected=String(picker.querySelector('.lp')?.value||'');
  const name=selected==='__other__'?String(picker.querySelector('.uni-other')?.value||'').trim():selected.trim();
  return province&&name?province+' · '+name:'';
}
function setUniversityValue(el,value){
  const picker=universityPicker(el);if(!picker)return;
  const province=picker.querySelector('.up'),input=picker.querySelector('.lp'),other=picker.querySelector('.uni-other');
  if(!province||!input||!other)return;
  const apply=()=>{
    const parsed=parseUniversityValue(value);
    province.value=Object.prototype.hasOwnProperty.call(PROVINCES,parsed.province)?parsed.province:'';
    picker.dataset.pendingName=parsed.name||'';
    picker.dataset.unresolved=parsed.name&&!province.value?'1':'';
    if(typeof picker._refreshUniversityList==='function')picker._refreshUniversityList();
  };
  if(universitiesLoaded()){apply();return Promise.resolve(true)}
  return loadUniversities().then(()=>{apply();return true},()=>{picker.dataset.universitiesFailed='1';apply();return false});
}
function listHTML(kind,val,index=null){
  if(kind==='uni'){
    const parsed=parseUniversityValue(val),province=parsed.province,name=parsed.name,
      known=(universitiesByProvince()[province]||[]).some(item=>normalizeUniversityText(item)===normalizeUniversityText(name));
    return `<div class="pick list-pick uni-pick" data-list="uni" data-province="${escAttr(province)}" data-pending-name="${escAttr(name)}" data-unresolved="${name&&!province?'1':''}">
      <select class="input up" aria-label="استان محل تحصیل"><option value="" ${province?'':'selected'}>استان محل تحصیل</option>${opts(EVENTKIT.provinces,province)}</select>
      <select class="input lp" aria-label="دانشگاه محل تحصیل" ${province?'':'disabled'}>
        <option value="">${province?'دانشگاه محل تحصیل را انتخاب کنید':'ابتدا استان را انتخاب کنید'}</option>
        <option value="__other__" ${name&&!known?'selected':''}>سایر</option>
      </select>
      <input class="input other uni-other" type="text" aria-label="نام دانشگاه دیگر" maxlength="160" autocomplete="off"
        placeholder="نام دانشگاه را بنویسید" value="${escAttr(name&&!known?name:'')}"
        style="display:${name&&!known?'':'none'}" ${province&&name&&!known?'':'disabled'}/>
      <p class="cap uni-coverage-note" style="flex-basis:100%;margin:3px 0 0">این فهرست جامعه‌ساخته است و کامل یا به‌روز بودنش تضمین نمی‌شود؛ اگر نامی نبود «سایر» را انتخاب کنید.</p>
    </div>`;
  }
  const list=kind==='job'?JOBS:EDU;
  const options=list.includes('سایر')?list:list.concat('سایر');
  const other=!!val&&!options.includes(val), empty=val==null||val==='';
  const label=kind==='job'?'شغل':'مقطع تحصیلی',otherLabel=kind==='job'?'شغل دلخواه':'مقطع تحصیلی دلخواه';
  return `<div class="pick list-pick" data-list="${escAttr(kind)}" data-val="${escAttr(val||'')}">
    <select class="input lp" aria-label="${label}">${empty?'<option value="" selected>انتخاب کنید</option>':''}${opts(options,other?'سایر':val)}</select>
    <input class="input other" aria-label="${otherLabel}" placeholder="${label} را بنویسید…" style="display:${other?'':'none'}" value="${escAttr(other?val:'')}"/>
  </div>`;
}
function initListPicks(root){(root||document).querySelectorAll('.pick[data-list]').forEach(el=>{
  if(el.dataset.ready)return;el.dataset.ready='1';
  if(el.dataset.list==='uni'){
    const select=el.querySelector('.lp'),province=el.querySelector('.up'),other=el.querySelector('.uni-other');
    const makeOption=(value,text)=>{const option=document.createElement('option');option.value=value;option.textContent=text;return option};
    const render=()=>{
      const hasProvince=Object.prototype.hasOwnProperty.call(PROVINCES,province.value),dataReady=universitiesLoaded(),
        names=hasProvince?(universitiesByProvince()[province.value]||[]):[],failed=el.dataset.universitiesFailed==='1',
        loading=hasProvince&&!dataReady&&!failed,
        pending=String(el.dataset.pendingName||'').trim(),current=select.value==='__other__'?String(other.value||'').trim():String(select.value||'').trim(),
        name=pending||current,known=names.find(item=>normalizeUniversityText(item)===normalizeUniversityText(name));
      const prompt=loading?'در حال دریافت فهرست دانشگاه‌ها…':failed?'فهرست در دسترس نیست':'دانشگاه محل تحصیل را انتخاب کنید';
      const options=[makeOption('',hasProvince?prompt:'ابتدا استان را انتخاب کنید')];
      if(hasProvince&&dataReady){names.forEach(item=>options.push(makeOption(item,item)));options.push(makeOption('__other__','سایر'))}
      else if(hasProvince&&failed)options.push(makeOption('__other__','سایر · نام را وارد کنید'));
      select.replaceChildren(...options);select.disabled=!hasProvince||loading;
      if(known){select.value=known;other.value='';other.style.display='none';other.disabled=true}
      else if(hasProvince&&name&&(dataReady||failed)){select.value='__other__';other.value=name;other.style.display='';other.disabled=false}
      else if(hasProvince&&loading&&name){select.value='';other.value=name;other.style.display='';other.disabled=true}
      else if(!hasProvince&&el.dataset.unresolved==='1'&&name){select.value='';other.value=name;other.style.display='';other.disabled=true}
      else{select.value='';other.value='';other.style.display='none';other.disabled=true}
      const note=el.querySelector('.uni-coverage-note');
      if(note)note.textContent=failed
        ?'فهرست دانشگاه بارگیری نشد؛ نام را با انتخاب «سایر» دستی وارد کنید.'
        :'این فهرست جامعه‌ساخته است و کامل یا به‌روز بودنش تضمین نمی‌شود؛ اگر نامی نبود «سایر» را انتخاب کنید.';
      el.dataset.province=hasProvince?province.value:'';
      delete el.dataset.pendingName;
    };
    const refresh=()=>{
      render();
      if(!Object.prototype.hasOwnProperty.call(PROVINCES,province.value)||universitiesLoaded()||el.dataset.universitiesFailed==='1')return;
      loadUniversities().then(()=>{delete el.dataset.universitiesFailed;render()})
        .catch(()=>{el.dataset.universitiesFailed='1';render()});
    };
    el._refreshUniversityList=refresh;
    province.addEventListener('change',()=>{
      const keepUnresolved=el.dataset.unresolved==='1'&&String(other.value||'').trim();
      if(keepUnresolved){el.dataset.pendingName=String(other.value).trim();el.dataset.unresolved=''}
      else{el.dataset.pendingName='';other.value='';el.dataset.unresolved=''}
      delete el.dataset.universitiesFailed;refresh();
    });
    select.addEventListener('change',event=>{
      delete el.dataset.pendingName;delete el.dataset.unresolved;
      if(select.value==='__other__'){
        other.style.display='';other.disabled=!Object.prototype.hasOwnProperty.call(PROVINCES,province.value);
        if(event.isTrusted)other.focus();
      }else{other.value='';other.style.display='none';other.disabled=true}
    });
    other.addEventListener('input',()=>{delete el.dataset.pendingName;delete el.dataset.unresolved});
    other.addEventListener('change',()=>{delete el.dataset.pendingName;delete el.dataset.unresolved});
    refresh();return;
  }
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
const tkEsc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\"/g, '&quot;').replace(/'/g, '&apos;');

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
  const approver=o.approver||'مالک سامانه';
  const include=Object.assign({},o.include||{}), show=(k,d=true)=>include[k]===undefined?d:!!include[k];
  const wantQR=o.qr===false?false:show('qr',true);
  const timeLine=[show('date')?date:'',show('hours')&&hours?('به مدت '+hours):''].filter(Boolean).join(' · ');
  const customRows=(Array.isArray(o.custom)?o.custom:Object.entries(o.custom||{}).map(([key,value])=>({key,value})))
    .filter(row=>row&&include['custom:'+String(row.key)]===true&&String(row.value||'').trim()).slice(0,2);
  /* QR deliberately contains plain text, never a URL: this preview has no public registry. */
  const verifyUrl='SAMPLE-ONLY:'+String(short||'LOCAL');
  const qrNote=wantQR?'QR متن نمونه است؛ نشانی یا استعلام واقعی ندارد':'QR در این پیش‌نمایش خاموش است؛ استعلام عمومی ندارد';
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
  <text x="${cx1-92}" y="${cy0+88}" text-anchor="end" font-size="17" font-weight="700" fill="${brand}"${RTL}>نورا · پیش‌نمایش</text>
  <text x="${cx1-92}" y="${cy0+112}" text-anchor="end" font-size="13.5" fill="${muted}"${RTL}>طرح نمونه · بدون وابستگی رسمی</text>
  ${show('kind')?`<text x="${(cx0+cx1)/2}" y="${cy0+176}" text-anchor="middle" font-size="15" font-weight="600" letter-spacing=".4" fill="${gold}"${RTL}>${tkEsc(kind)}</text>`:''}
  ${show('title')?`<text x="${(cx0+cx1)/2}" y="${cy0+248}" text-anchor="middle" font-size="${fit(title,40,860,24)}" font-weight="700" fill="${ink}" letter-spacing="-.3"${RTL}>${tkEsc(title)}</text>`:''}
  <rect x="${(cx0+cx1)/2-70}" y="${cy0+270}" width="140" height="3" rx="1.5" fill="url(#certline)"/>
  <text x="${(cx0+cx1)/2}" y="${cy0+322}" text-anchor="middle" font-size="16" fill="${muted}"${RTL}>پیش‌نمایش محلیِ طرح؛ این فایل گواهی رسمی صادر نمی‌کند</text>
  ${show('name')?`<text x="${(cx0+cx1)/2}" y="${cy0+408}" text-anchor="middle" font-size="${fit(name,52,760,30)}" font-weight="700" fill="${brand}"${RTL}>${tkEsc(name)}</text>`:''}
  ${timeLine?`<text x="${(cx0+cx1)/2}" y="${cy0+446}" text-anchor="middle" font-size="14.5" fill="${muted}"${RTL}>${tkEsc(timeLine)}</text>`:''}
  ${customRows.map((row,i)=>`<text x="${(cx0+cx1)/2}" y="${cy0+492+i*26}" text-anchor="middle" font-size="13.5" fill="${muted}"${RTL}>${tkEsc(row.key)}: ${tkEsc(row.value)}</text>`).join('')}
  <line x1="${cx0+120}" y1="${cy0+560}" x2="${cx0+400}" y2="${cy0+560}" stroke="${muted}" stroke-opacity=".45" stroke-width="1"/>
  <text x="${cx0+260}" y="${cy0+588}" text-anchor="middle" font-size="13.5" fill="${muted}"${RTL}>جای مهر و امضا · نمونه</text>
  <line x1="${cx1-400}" y1="${cy0+560}" x2="${cx1-120}" y2="${cy0+560}" stroke="${muted}" stroke-opacity=".45" stroke-width="1"/>
  <text x="${cx1-260}" y="${cy0+588}" text-anchor="middle" font-size="13.5" fill="${muted}"${RTL}>محل تأیید نهایی مالک · نمونه</text>
  ${wantQR?tkQR(null,verifyUrl,(cx0+cx1)/2-48,cy0+588,96,null,'cert-qr'):''}
  ${show('serial')?`<text x="${(cx0+cx1)/2}" y="${cy0+736}" text-anchor="middle" font-size="12.5" fill="${muted}"${RTL}>سریال نمونه ${tkEsc(serial)} · ${tkEsc(qrNote)}</text>`:''}
  <g transform="rotate(-20 ${W/2} ${H/2})" pointer-events="none">
    <text x="${W/2}" y="${H/2}" text-anchor="middle" font-size="48" font-weight="800" fill="#B42318" fill-opacity=".22"${RTL}>پیش‌نمایش محلی · فاقد اعتبار رسمی</text>
  </g>
</svg>`;
}
function certificateFile(o){return certificateSVG(o,{embed:true});}

const TICKET_G={size:[1200,640]};
function ticketSVG(o,opt){
  o=o||{}; opt=opt||{};
  const [W,H]=TICKET_G.size, RTL=' direction="rtl"';
  const include=Object.assign({event:true,name:true,date:true,time:true,place:true,seat:true,serial:true,qr:true},o.include||{});
  const show=k=>include[k]!==false;
  const name=o.name||'نام شرکت‌کننده';
  const title=o.title||o.eventTitle||'رویداد نمونه';
  const date=o.date||'', time=o.time||'', place=o.place||'', seat=o.seat||'';
  const serial=o.serial||('TK-'+shortCode(o.code||title||'nora-ticket-preview'));
  const payload='SAMPLE-TICKET:'+String(serial||'LOCAL');
  const detail=[show('date')?date:'',show('time')?time:'',show('place')?place:''].filter(Boolean).join(' · ');
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" style="font-family:${TK_FONTS}" aria-label="بلیت نمونهٔ ${tkEsc(title)} برای ${tkEsc(name)}">
  <defs>
    <linearGradient id="ticketbg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#F5F9F7"/><stop offset="1" stop-color="#E5EFEB"/></linearGradient>
    ${opt.embed?`<style>${TK_CSS}</style>`:''}
  </defs>
  <rect width="${W}" height="${H}" rx="32" fill="#DCE7E2"/>
  <rect x="20" y="20" width="1160" height="600" rx="28" fill="url(#ticketbg)" stroke="#93AEA2" stroke-width="2"/>
  <path d="M385 22v596" stroke="#82968D" stroke-width="2" stroke-dasharray="9 9" opacity=".55"/>
  <circle cx="1080" cy="85" r="26" fill="#0071E3" fill-opacity=".12"/>
  <text x="1080" y="92" text-anchor="middle" font-size="17" font-weight="700" fill="#0071E3"${RTL}>ن</text>
  <text x="1035" y="82" text-anchor="end" font-size="18" font-weight="700" fill="#0071E3"${RTL}>نورا · بلیت نمونه</text>
  <text x="1035" y="108" text-anchor="end" font-size="13" fill="#6E7A75"${RTL}>رزرو و اعتبار ورود متصل نیست</text>
  ${show('event')?`<text x="1035" y="205" text-anchor="end" font-size="${Math.max(24,Math.min(40,700/Math.max(1,title.length))).toFixed(1)}" font-weight="700" fill="#12201B"${RTL}>${tkEsc(title)}</text>`:''}
  ${show('name')?`<text x="1035" y="286" text-anchor="end" font-size="27" font-weight="700" fill="#0071E3"${RTL}>${tkEsc(name)}</text>`:''}
  ${detail?`<text x="1035" y="350" text-anchor="end" font-size="17" fill="#52615A"${RTL}>${tkEsc(detail)}</text>`:''}
  ${show('seat')&&seat?`<text x="1035" y="396" text-anchor="end" font-size="16" fill="#52615A"${RTL}>جای نمونه: ${tkEsc(seat)}</text>`:''}
  ${show('serial')?`<text x="1035" y="500" text-anchor="end" font-size="15" fill="#52615A"${RTL}>کد نمونه ${tkEsc(serial)}</text>`:''}
  ${show('qr')?`<rect x="98" y="196" width="210" height="210" rx="14" fill="#fff" stroke="#C9D8D1"/>${tkQR(null,payload,117,215,172,'#12201B','ticket-qr')}`:''}
  <text x="203" y="445" text-anchor="middle" font-size="13" fill="#52615A"${RTL}>${show('qr')?'QR متنیِ نمونه · بدون پیوند':'QR خاموش است'}</text>
  <text x="203" y="476" text-anchor="middle" font-size="12" fill="#79867F"${RTL}>اسکن، رزرو را تأیید نمی‌کند</text>
  <g transform="rotate(-17 ${W/2} ${H/2})" pointer-events="none"><text x="${W/2}" y="${H/2}" text-anchor="middle" font-size="46" font-weight="800" fill="#B42318" fill-opacity=".20"${RTL}>پیش‌نمایش محلی · فاقد اعتبار ورود</text></g>
</svg>`;
}
function ticketFile(o){return ticketSVG(o,{embed:true});}

function svgDimensions(svg){
  const match=String(svg||'').match(/viewBox=["']0\s+0\s+([\d.]+)\s+([\d.]+)["']/i);
  const w=match?Number(match[1]):1100, h=match?Number(match[2]):780;
  return {width:Math.max(1,Math.round(w)),height:Math.max(1,Math.round(h))};
}
function svgToJpeg(svg){
  if(typeof document==='undefined'||typeof Image==='undefined') return Promise.reject(new Error('image_export_unavailable'));
  const dims=svgDimensions(svg), scale=2, source=new Blob([String(svg)],{type:'image/svg+xml;charset=utf-8'}), url=URL.createObjectURL(source);
  return new Promise((resolve,reject)=>{
    const img=new Image();
    const cleanup=()=>URL.revokeObjectURL(url);
    img.onload=()=>{
      try{
        const canvas=document.createElement('canvas'); canvas.width=dims.width*scale; canvas.height=dims.height*scale;
        const ctx=canvas.getContext('2d'); if(!ctx) throw new Error('canvas_unavailable');
        ctx.fillStyle='#fff'; ctx.fillRect(0,0,canvas.width,canvas.height); ctx.drawImage(img,0,0,canvas.width,canvas.height);
        if(!canvas.toBlob) throw new Error('jpeg_export_unavailable');
        canvas.toBlob(blob=>{cleanup(); blob?resolve({blob,width:canvas.width,height:canvas.height}):reject(new Error('jpeg_export_failed'))},'image/jpeg',.94);
      }catch(err){cleanup(); reject(err)}
    };
    img.onerror=()=>{cleanup(); reject(new Error('svg_rasterize_failed'))};
    img.src=url;
  });
}
async function pdfFromJpeg(jpegBlob,width,height){
  const pageW=842, pageH=595, scale=Math.min(pageW/width,pageH/height), drawW=width*scale, drawH=height*scale,
    x=(pageW-drawW)/2, y=(pageH-drawH)/2, enc=new TextEncoder(), parts=[];
  let offset=0; const offsets=[0];
  const add=value=>{const bytes=typeof value==='string'?enc.encode(value):value; parts.push(bytes); offset+=bytes.length};
  const header=Uint8Array.from([37,80,68,70,45,49,46,52,10,37,226,227,207,211,10]); add(header);
  const obj=(id,body)=>{offsets[id]=offset; add(`${id} 0 obj\n${body}\nendobj\n`)};
  obj(1,'<< /Type /Catalog /Pages 2 0 R >>');
  obj(2,'<< /Type /Pages /Kids [3 0 R] /Count 1 >>');
  obj(3,`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageW} ${pageH}] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>`);
  const jpg=new Uint8Array(await jpegBlob.arrayBuffer());
  offsets[4]=offset; add(`4 0 obj\n<< /Type /XObject /Subtype /Image /Width ${width} /Height ${height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpg.length} >>\nstream\n`);
  add(jpg); add('\nendstream\nendobj\n');
  const content=enc.encode(`q\n${drawW.toFixed(2)} 0 0 ${drawH.toFixed(2)} ${x.toFixed(2)} ${y.toFixed(2)} cm\n/Im0 Do\nQ\n`);
  offsets[5]=offset; add(`5 0 obj\n<< /Length ${content.length} >>\nstream\n`); add(content); add('endstream\nendobj\n');
  const xref=offset; add('xref\n0 6\n0000000000 65535 f \n');
  for(let i=1;i<=5;i++) add(String(offsets[i]).padStart(10,'0')+' 00000 n \n');
  add(`trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`);
  return new Blob(parts,{type:'application/pdf'});
}
async function exportSVG(svg,format){
  const f=String(format||'pdf').toLowerCase();
  if(f==='svg') return {blob:new Blob([String(svg)],{type:'image/svg+xml;charset=utf-8'}),extension:'svg',mime:'image/svg+xml'};
  if(f!=='jpg'&&f!=='pdf') throw new Error('unsupported_export_format');
  const raster=await svgToJpeg(svg);
  if(f==='jpg') return {blob:raster.blob,extension:'jpg',mime:'image/jpeg'};
  return {blob:await pdfFromJpeg(raster.blob,raster.width,raster.height),extension:'pdf',mime:'application/pdf'};
}
function certificateExport(o,format){return exportSVG(certificateFile(o),format)}
function ticketExport(o,format){return exportSVG(ticketFile(o),format)}

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
  const value=String(txt==null?'':txt).trim();
  if(/^(?:https?:|mailto:|tel:|sms:|tg:|whatsapp:|javascript:|data:)/i.test(value)){
    toast(NORA_TEST_FIXTURE_MODE
      ?'رونوشت پیوند بیرونی در پیش‌نمایش محلی غیرفعال است؛ چیزی کپی نشد'
      :'رونوشت این پیوند بیرونیِ تأییدنشده انجام نشد'); return false;
  }
  const done=()=>{toast(msg||'کپی شد'); if(after) after();};
  try{navigator.clipboard.writeText(value).then(done).catch(fb)}catch(e){fb()}
  function fb(){const t=document.createElement('textarea');t.value=value;document.body.appendChild(t);t.select();
    try{document.execCommand('copy')}catch(e){}t.remove();done()}
  return true;
}
/* مقصدهای بیرونی در پیش‌نمایش محلی بی‌عمل می‌شوند؛ پیوندهای محتوای منتشرشده و حسابِ سروری زنده می‌مانند. */
function disableExternalLinks(root){
  const host=root||document, anchors=[];
  if(host.nodeType===1&&host.matches&&host.matches('a[href]')) anchors.push(host);
  if(host.querySelectorAll) anchors.push(...host.querySelectorAll('a[href]'));
  anchors.forEach(a=>{
    const href=String(a.getAttribute('href')||'').trim();
    if(!/^(?:https?:|mailto:|tel:|sms:|tg:|whatsapp:|ftp:|javascript:|data:|file:)/i.test(href)) return;
    const N=window.NORA||{}, serverContent=window.NORA_PUBLIC_SOURCE==='server'||window.NORA_ACCOUNT_SOURCE==='server';
    const liveBotBase=String(N.BALE_BOT_URL||'').trim();
    const localFilePreview=location.protocol==='file:';
    if(!localFilePreview&&serverContent&&/^(?:https?:|mailto:|tel:)/i.test(href)) return;
    if(!localFilePreview&&/^https:\/\/ble[.]ir\/[A-Za-z0-9_]{3,64}\?start=[A-Za-z0-9_-]{1,64}$/i.test(href)
        &&liveBotBase&&href.startsWith(liveBotBase+'?start=')) return;
    if(/^blob:/i.test(href)){
      try{if(new URL(href).origin===location.origin) return}catch(e){}
    }
    const label=(a.getAttribute('aria-label')||a.textContent||'').trim();
    const disabledMessage=NORA_TEST_FIXTURE_MODE
      ?'پیوند بیرونی در پیش‌نمایش محلی غیرفعال است'
      :'پیوند بیرونیِ تأییدنشده غیرفعال است';
    a.removeAttribute('href'); a.removeAttribute('target'); a.removeAttribute('download');
    a.setAttribute('aria-disabled','true'); a.setAttribute('tabindex','-1');
    a.setAttribute('title',disabledMessage);
    if(label) a.setAttribute('aria-label',label+'؛ '+disabledMessage);
    a.classList.add('local-disabled-link');
    if(!a.querySelector('.local-disabled-note')){
      const note=document.createElement('small'); note.className='local-disabled-note';
      note.textContent=NORA_TEST_FIXTURE_MODE?'پیوند بیرونی · غیرفعال':'پیوند بیرونیِ تأییدنشده · غیرفعال'; a.appendChild(note);
    }
  });
}
function installExternalLinkGuard(){
  const activate=()=>{
    disableExternalLinks(document);
    if(typeof MutationObserver==='undefined'||!document.body) return;
    const observer=new MutationObserver(records=>records.forEach(r=>r.addedNodes.forEach(n=>{
      if(n.nodeType===1) disableExternalLinks(n);
    })));
    observer.observe(document.body,{childList:true,subtree:true});
  };
  const start=()=>{
    const ready=window.NORA_PUBLIC_READY;
    if(ready&&typeof ready.then==='function') Promise.resolve(ready).then(activate,activate);
    else activate();
  };
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',start,{once:true});
  else start();
}
installExternalLinkGuard();
/* ── اشتراک بیرونی در پیش‌نمایش غیرفعال است؛ نه پیام می‌فرستیم، نه لینک کپی می‌کنیم. ── */
async function shareItem(){
  toast(NORA_TEST_FIXTURE_MODE
    ?'اشتراک‌گذاری بیرونی در این پیش‌نمایش غیرفعال است؛ هیچ پیامی ارسال یا پیوندی کپی نشد.'
    :'اشتراک‌گذاری بیرونی هنوز در این صفحه فعال نیست؛ پیامی ارسال یا پیوندی کپی نشد.');
  return false;
}

/* ── دسترس‌پذیری ورقه‌ها: مودال واقعی، فوکوس داخل، برگشت فوکوس ── */
const SHEET_FOCUSABLE='a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';
let _sheetLast=null, _sheetActive=null;
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
    document.querySelectorAll('.sheet').forEach(s=>{
      const visible=s.classList.contains('on');
      s.setAttribute('aria-modal',String(visible));s.setAttribute('aria-hidden',String(!visible));s.inert=!visible;
    });
    if(on&&on!==_sheetActive){
      if(!_sheetLast)_sheetLast=document.activeElement;
      const first=on.querySelector(SHEET_FOCUSABLE); if(first&&!on.contains(document.activeElement)) first.focus();
    }
    if(!on&&_sheetLast){try{if(_sheetLast.isConnected) _sheetLast.focus()}catch(e){} _sheetLast=null}
    _sheetActive=on;
  };
  new MutationObserver(sync).observe(document.documentElement,{subtree:true,childList:true,attributeFilter:['class']});
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
    const back=e.target.closest('[data-uiplayerback]');
    if(back){restorePlayerSheet(back.dataset.uiplayerback);e.preventDefault();return}
    const op=e.target.closest('[data-sheet]'); if(op){openSheet(op.dataset.sheet);return}
    if(e.target.closest('[data-close]')||e.target.closest('.scrim')){closeSheets();return}
    const cp=e.target.closest('[data-copy]');
    if(cp){if(cp.disabled||cp.getAttribute('aria-disabled')==='true')return;
      const el=cp.dataset.copy.startsWith('#')?document.querySelector(cp.dataset.copy):null;
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
  // Bubble at window after page-specific switch handlers, without double-toggling.
  window.addEventListener('keydown',e=>{
    if(e.defaultPrevented||e.repeat||!['Enter',' ','Spacebar'].includes(e.key))return;
    const sw=e.target.closest&&e.target.closest('.switch[role="switch"]');
    if(!sw||sw.matches('button,input,[aria-disabled="true"]')||sw.closest('[inert]'))return;
    e.preventDefault();sw.click();
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
/* کلید شب/روز در سرِ همهٔ صفحه‌ها (رویدادها، رویداد، شخص، مطلب، ورود، حساب…)
   یک‌جا همین‌جا وصل می‌شود، مستقل از این‌که صفحه initUI را صدا بزند یا نه؛
   صفحه‌ای که خودش آن را دست می‌گیرد، همین پرچم را روی رویداد می‌گذارد تا دوبار عوض نشود */
if(typeof document!=='undefined'&&document.addEventListener){
  document.addEventListener('click',e=>{
    const b=e.target&&e.target.closest&&e.target.closest('[data-theme-toggle]');
    if(!b||e.noraThemeHandled) return;
    e.noraThemeHandled=true; e.preventDefault(); themeToggle();
  });
}
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
function sessUser(){
  if(!NORA_TEST_FIXTURE_MODE) return null;
  try{const v=JSON.parse(localStorage.getItem(SESS_KEY)||'null');
    return v&&typeof v==='object'&&typeof v.name==='string'?v:null}catch(e){return null}
}
function accountFirstName(user){
  const name=String(user&&user.name||'').trim();
  return name?name.split(/\s+/u)[0]:'';
}
const ACCOUNT_NEXT_RE=/^account\.html(?:#(?:events|profile|pay|book|notifications|my-files|account-data|info|auth|login|forms|payments|privacy|club|points|invite))?$/;
function accountEntryHref(next='account.html'){
  next=String(next||'account.html');
  if(!ACCOUNT_NEXT_RE.test(next)) next='account.html';
  /* «ورود/ثبت‌نام» ابتدا نمای امن مهمان را باز می‌کند؛ فقط بخش شخصی، ورود واقعی می‌خواهد. */
  return next;
}
function updateAccountNavigation(){
  const user=sessUser(), first=accountFirstName(user), authenticated=!!user||window.NORA_ACCOUNT_SOURCE==='server';
  const label=first||(authenticated?'حساب من':'ورود/ثبت‌نام'), destination=accountEntryHref('account.html');
  document.querySelectorAll('[data-account-nav-label]').forEach(node=>{node.textContent=label});
  document.querySelectorAll('.tabbar [data-account-nav]').forEach(link=>{
    link.setAttribute('href',destination);
    link.setAttribute('aria-label',first?first+'، حساب کاربری':authenticated?'حساب من':'ورود/ثبت‌نام');
  });
  return label;
}
const TAB_ICON_PATHS=Object.freeze({
  home:'<path d="M3.8 10.6 12 4l8.2 6.6V20h-5.1v-5.5H8.9V20H3.8z"/>',
  events:'<rect x="3.8" y="5.5" width="16.4" height="14.8" rx="3"/><path d="M8 3.7v3.5M16 3.7v3.5M3.8 10.2h16.4"/>',
  account:'<circle cx="12" cy="8.2" r="3.6"/><path d="M4.8 20c.6-3.6 3.4-5.6 7.2-5.6s6.6 2 7.2 5.6"/>',
  article:'<path d="M6 3.8h8l4 4V20H6z"/><path d="M14 3.8v4h4M9 12h6M9 15.5h6"/>',
  book:'<path d="M4.4 5.2h5.2A2.4 2.4 0 0 1 12 7.6v11a2.1 2.1 0 0 0-2-1.6H4.4z"/><path d="M19.6 5.2h-5.2A2.4 2.4 0 0 0 12 7.6v11a2.1 2.1 0 0 1 2-1.6h5.6z"/>'
});
function normalizePrimaryNavigation(){
  document.querySelectorAll('.tabbar:not(#admTabs)').forEach(bar=>{
    const links=Array.from(bar.children).filter(node=>node.tagName==='A');
    links.forEach((link,index)=>{
      const previous=link.querySelector('small');
      let label=previous?previous.textContent.trim():link.textContent.replace(/[⌂▦]/g,'').trim();
      const href=link.getAttribute('href')||'';
      const accountLink=index===2&&(/^(?:\.\/)?account\.html(?:[?#].*)?$/.test(href)||
        /^(?:حساب من|پروفایل‌ها|ورود\/ثبت‌نام)$/.test(label));
      let kind=accountLink?'account':
        /کتابخانه/.test(label)||/#lib(?:$|[?&])/.test(href)?'book':
        /مطالب/.test(label)||/#articles(?:$|[?&])/.test(href)?'article':
        /رویداد/.test(label)||/^(?:\.\/)?events?\.html/.test(href)?'events':
        /خانه/.test(label)||/^(?:\.\/)?home\.html(?:$|[?#])/.test(href)?'home':
        (index===0?'home':index===1?'events':'account');
      if(accountLink){
        link.setAttribute('href','account.html');
        link.setAttribute('data-account-nav','');
        label='ورود/ثبت‌نام';
      }
      const icon=document.createElementNS('http://www.w3.org/2000/svg','svg');
      icon.setAttribute('class','i nav-icon');
      icon.setAttribute('viewBox','0 0 24 24');
      icon.setAttribute('fill','none');
      icon.setAttribute('stroke','currentColor');
      icon.setAttribute('stroke-width','1.7');
      icon.setAttribute('stroke-linecap','round');
      icon.setAttribute('stroke-linejoin','round');
      icon.setAttribute('aria-hidden','true');
      icon.innerHTML=TAB_ICON_PATHS[kind]||TAB_ICON_PATHS.home;
      const caption=previous||document.createElement('small');
      caption.textContent=label;
      if(accountLink) caption.setAttribute('data-account-nav-label','');
      link.replaceChildren(icon,caption);
    });
  });
  updateAccountNavigation();
}
function profile(){
  const server=window.NORA_ACCOUNT_SOURCE==='server';
  if(!NORA_TEST_FIXTURE_MODE && !server) return cleanProfile(null);
  let v=null; try{v=JSON.parse(localStorage.getItem(PROF_KEY)||'null')}catch(e){v=null}
  const A=(window.NORA&&window.NORA.ACCOUNT)||{};
  /* حساب واقعی: پروفایل از سرور می‌آید و نسخهٔ محلی فقط کش همان است؛ نمونه‌ی ساختگی نمی‌نشیند */
  if(!v && server) return cleanProfile(null);
  if(!v){
    /* Browser profiles are seeded only inside explicitly marked test fixtures. */
    return cleanProfile(uid()&&A.seed?Object.assign({},A.seed):null);
  }
  return cleanProfile(v);
}
function saveProfile(v){
  const p=cleanProfile(v), server=window.NORA_ACCOUNT_SOURCE==='server';
  if(NORA_TEST_FIXTURE_MODE||server) try{localStorage.setItem(PROF_KEY,JSON.stringify(p))}catch(e){}
  if(server&&window.NORA_SERVER_API&&typeof window.NORA_SERVER_API.saveAccountProfile==='function'){
    const fields={}; ['fullName','nationalId','birthDate','gender','province','city','address','email'].forEach(k=>{ fields[k]=p[k]||'' });
    window.NORA_SERVER_API.saveAccountProfile(fields).catch(()=>{ try{ toast('ذخیرهٔ پروفایل روی سرور انجام نشد؛ دوباره تلاش کن') }catch(e){} });
  }
  return p;
}
/* پروفایل حساب واقعی را از سرور می‌خواند و کش محلی را به‌روز می‌کند */
function syncServerProfile(){
  const api=window.NORA_SERVER_API;
  if(window.NORA_ACCOUNT_SOURCE!=='server'||!api||typeof api.accountProfile!=='function') return Promise.resolve(null);
  return api.accountProfile().then(d=>{
    if(!d||!d.fields||typeof d.fields!=='object') return null;
    const p=cleanProfile(d.fields);
    try{ localStorage.setItem(PROF_KEY,JSON.stringify(p)) }catch(e){}
    return p;
  }).catch(()=>null);
}
/* ══ تنظیمهای ظاهری سامانه: یک انبار مشترک، همهٔ صفحه‌ها از آن می‌خوانند ══ */
const UISET_KEY='nora-uiset';
const UISET_DEF={v:1,
  home:{bnr:1,stories:1,search:1,quick:1,pins:1,mine:1,events:1,past:1,club:1,teachers:1,staff:1,articles:1,partners:1,voices:1,act:1},
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

/* ── عملکرد: تنظیم‌های محلی، سنجش واقعی صفحه و تبدیل امن تصویر ───────── */
const PERF_SETTINGS_KEY='nora-performance-settings';
const IMAGE_STATS_KEY='nora-image-optimization-stats';
const PERF_DEFAULTS=Object.freeze({loaderEnabled:true,loaderDelayMs:200,imageQuality:82,maxImageEdge:1600});
const IMAGE_EDGE_CHOICES=[720,960,1200,1600,2048];
function normalizePerfSettings(value){
  const source=value&&typeof value==='object'?value:{};
  const delay=Number(source.loaderDelayMs);
  const quality=Number(source.imageQuality);
  const edge=Number(source.maxImageEdge);
  return {
    loaderEnabled:source.loaderEnabled!==false,
    loaderDelayMs:Number.isFinite(delay)?Math.max(100,Math.min(1000,Math.round(delay/50)*50)):PERF_DEFAULTS.loaderDelayMs,
    imageQuality:Number.isFinite(quality)?Math.max(50,Math.min(95,Math.round(quality))):PERF_DEFAULTS.imageQuality,
    maxImageEdge:IMAGE_EDGE_CHOICES.includes(edge)?edge:PERF_DEFAULTS.maxImageEdge
  };
}
function performanceSettings(){
  try{
    const saved=JSON.parse(localStorage.getItem(PERF_SETTINGS_KEY)||'null');
    return normalizePerfSettings(saved&&saved.version===1?saved.settings:saved);
  }catch(e){return Object.assign({},PERF_DEFAULTS)}
}
function savePerformanceSettings(value){
  const settings=normalizePerfSettings(Object.assign({},performanceSettings(),value||{}));
  try{localStorage.setItem(PERF_SETTINGS_KEY,JSON.stringify({version:1,settings}))}catch(e){}
  try{window.dispatchEvent(new CustomEvent('nora:performance-settings',{detail:settings}))}catch(e){}
  return settings;
}
function imageOptimizationStats(){
  try{
    const value=JSON.parse(localStorage.getItem(IMAGE_STATS_KEY)||'null');
    if(value&&typeof value==='object') return {
      count:Math.max(0,+value.count||0),inputBytes:Math.max(0,+value.inputBytes||0),
      outputBytes:Math.max(0,+value.outputBytes||0),lastAt:Math.max(0,+value.lastAt||0)
    };
  }catch(e){}
  return {count:0,inputBytes:0,outputBytes:0,lastAt:0};
}
function recordImageOptimization(inputBytes,outputBytes){
  const old=imageOptimizationStats(),input=Math.max(0,+inputBytes||0),output=Math.max(0,+outputBytes||0);
  const next={count:old.count+1,inputBytes:old.inputBytes+input,outputBytes:old.outputBytes+output,lastAt:Date.now()};
  try{localStorage.setItem(IMAGE_STATS_KEY,JSON.stringify(next))}catch(e){}
  return next;
}
function imageFailure(code){const error=new Error(code);error.code=code;return error}
function asciiAt(bytes,offset,text){
  if(offset<0||offset+text.length>bytes.length)return false;
  for(let i=0;i<text.length;i++) if(bytes[offset+i]!==text.charCodeAt(i))return false;
  return true;
}
function skipGifSubBlocks(bytes,index){
  while(index<bytes.length){const size=bytes[index++];if(!size)return index;if(index+size>bytes.length)return bytes.length;index+=size}
  return index;
}
function gifIsAnimated(bytes){
  if(bytes.length<13||!(asciiAt(bytes,0,'GIF87a')||asciiAt(bytes,0,'GIF89a')))return false;
  let index=10,frames=0;const packed=bytes[index++];index+=2;
  if(packed&0x80)index+=3*(1<<((packed&7)+1));
  while(index<bytes.length){
    const marker=bytes[index++];
    if(marker===0x3b)break;
    if(marker===0x21){if(index>=bytes.length)break;index++;index=skipGifSubBlocks(bytes,index);continue}
    if(marker!==0x2c||index+9>bytes.length)break;
    frames++;const flags=bytes[index+8];index+=9;
    if(flags&0x80)index+=3*(1<<((flags&7)+1));
    if(index>=bytes.length)break;
    index++;index=skipGifSubBlocks(bytes,index);
    if(frames>1)return true;
  }
  return false;
}
function fourCC(bytes,offset){
  if(offset<0||offset+4>bytes.length)return '';
  return String.fromCharCode(bytes[offset],bytes[offset+1],bytes[offset+2],bytes[offset+3]);
}
function isoBmffHasSequence(bytes){
  if(bytes.length<16||!asciiAt(bytes,4,'ftyp'))return false;
  const declared=(bytes[0]*0x1000000)+(bytes[1]<<16)+(bytes[2]<<8)+bytes[3],end=declared>=16?Math.min(bytes.length,declared):bytes.length;
  const sequenceBrands=new Set(['avis','hevc','hevx','msf1']);
  if(sequenceBrands.has(fourCC(bytes,8)))return true;
  for(let index=16;index+4<=end;index+=4)if(sequenceBrands.has(fourCC(bytes,index)))return true;
  return false;
}
function imageHasAnimation(bytes,type,name){
  const mime=String(type||'').toLowerCase(),fileName=String(name||'');
  if(mime==='image/gif'||asciiAt(bytes,0,'GIF87a')||asciiAt(bytes,0,'GIF89a'))return gifIsAnimated(bytes);
  if(mime==='image/svg+xml'||/\.svg$/i.test(fileName)){
    try{
      const text=new TextDecoder().decode(bytes);
      return /<(?:[\w.-]+:)?(?:animate|animateMotion|animateTransform|set)\b/i.test(text)
        ||/@(?:-webkit-)?keyframes\b|\banimation(?:-name)?\s*:\s*(?!none\b)[^;}\"']+/i.test(text);
    }catch(e){return false}
  }
  if(mime==='image/png'||(bytes.length>8&&bytes[0]===137&&asciiAt(bytes,1,'PNG'))){
    for(let index=8;index+12<=bytes.length;){
      const length=(bytes[index]*0x1000000)+(bytes[index+1]<<16)+(bytes[index+2]<<8)+bytes[index+3];
      if(asciiAt(bytes,index+4,'acTL'))return true;
      if(!Number.isFinite(length)||length<0||index+12+length>bytes.length)break;
      index+=12+length;
    }
  }
  if(mime==='image/webp'||(bytes.length>12&&asciiAt(bytes,0,'RIFF')&&asciiAt(bytes,8,'WEBP'))){
    for(let index=12;index+8<=bytes.length;){
      const length=bytes[index+4]+(bytes[index+5]<<8)+(bytes[index+6]<<16)+(bytes[index+7]*0x1000000);
      if(asciiAt(bytes,index,'ANIM')||asciiAt(bytes,index,'ANMF'))return true;
      if(asciiAt(bytes,index,'VP8X')&&index+8<bytes.length&&(bytes[index+8]&0x02))return true;
      if(!Number.isFinite(length)||length<0||index+8+length>bytes.length)break;
      index+=8+length+(length&1);
    }
  }
  if(isoBmffHasSequence(bytes))return true;
  if(mime==='image/jxl'||/\.jxl$/i.test(fileName)){
    for(let index=0;index+4<=bytes.length;index++)if(asciiAt(bytes,index,'jxli'))return true;
  }
  return false;
}
function imageBlobDataURL(blob){
  return new Promise((resolve,reject)=>{
    try{
      const reader=new FileReader();reader.onload=()=>resolve(String(reader.result||''));
      reader.onerror=()=>reject(imageFailure('image_read_failed'));reader.readAsDataURL(blob);
    }catch(e){reject(imageFailure('image_read_failed'))}
  });
}
function loadImageSource(file){
  return new Promise((resolve,reject)=>{
    let url='';
    try{url=URL.createObjectURL(file)}catch(e){reject(imageFailure('image_decode_failed'));return}
    const image=new Image();
    image.onload=()=>{try{URL.revokeObjectURL(url)}catch(e){};resolve(image)};
    image.onerror=()=>{try{URL.revokeObjectURL(url)}catch(e){};reject(imageFailure('image_decode_failed'))};
    image.src=url;
  });
}
async function imageToWebP(file,options){
  const opts=options&&typeof options==='object'?options:{};
  if(!file||typeof file.size!=='number'||typeof file.slice!=='function')throw imageFailure('image_file_required');
  const mime=String(file.type||'').toLowerCase(),name=String(file.name||'image');
  const knownImage=/^image\//.test(mime)||/\.(?:avif|bmp|gif|heic|heif|jpe?g|jxl|png|svg|tiff?|webp)$/i.test(name);
  if(!knownImage)throw imageFailure('image_file_required');
  const maxInputBytes=15*1024*1024;
  if(file.size>maxInputBytes)throw imageFailure('image_too_large');
  let bytes;
  try{bytes=new Uint8Array(await file.arrayBuffer())}catch(e){throw imageFailure('image_read_failed')}
  if(imageHasAnimation(bytes,mime,name))throw imageFailure('animated_image_not_supported');
  let bitmap=null,source=null;
  try{
    if(typeof createImageBitmap==='function'){
      try{bitmap=await createImageBitmap(file,{imageOrientation:'from-image'});source=bitmap}catch(e){}
    }
    if(!source)source=await loadImageSource(file);
  }catch(e){if(bitmap&&bitmap.close)bitmap.close();throw imageFailure('image_decode_failed')}
  const width=Number(source.width||source.naturalWidth||0),height=Number(source.height||source.naturalHeight||0);
  if(!width||!height||width*height>40_000_000){if(bitmap&&bitmap.close)bitmap.close();throw imageFailure(width&&height?'image_dimensions_too_large':'image_decode_failed')}
  const settings=performanceSettings();
  const requestedEdge=Number(opts.maxEdge)||settings.maxImageEdge;
  const maxEdge=Math.max(64,Math.min(4096,requestedEdge));
  const scale=Math.min(1,maxEdge/Math.max(width,height));
  const outputWidth=Math.max(1,Math.round(width*scale)),outputHeight=Math.max(1,Math.round(height*scale));
  const q=Number(opts.quality),quality=Math.max(.5,Math.min(.95,Number.isFinite(q)?(q>1?q/100:q):settings.imageQuality/100));
  let canvas=null,blob=null;
  try{
    canvas=document.createElement('canvas');canvas.width=outputWidth;canvas.height=outputHeight;
    const context=canvas.getContext('2d',{alpha:true,willReadFrequently:false});
    if(!context)throw imageFailure('image_canvas_unavailable');
    context.drawImage(source,0,0,outputWidth,outputHeight);
    if(typeof canvas.toBlob!=='function')throw imageFailure('webp_unsupported');
    blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/webp',quality));
  }catch(e){
    if(bitmap&&bitmap.close)bitmap.close();
    if(e&&e.code)throw e;
    throw imageFailure('image_conversion_failed');
  }finally{
    if(canvas){canvas.width=1;canvas.height=1}
    if(bitmap&&bitmap.close)try{bitmap.close()}catch(e){}
  }
  if(!blob||String(blob.type||'').toLowerCase()!=='image/webp')throw imageFailure('webp_unsupported');
  const base=name.replace(/\.[^.]*$/,'')||'image',webpName=base+'.webp';
  let outputFile=blob;
  try{if(typeof File==='function')outputFile=new File([blob],webpName,{type:'image/webp',lastModified:+file.lastModified||Date.now()})}catch(e){}
  const stats=recordImageOptimization(file.size,blob.size);
  return {file:outputFile,blob,name:webpName,type:'image/webp',width:outputWidth,height:outputHeight,
    originalWidth:width,originalHeight:height,inputBytes:file.size,outputBytes:blob.size,
    savedBytes:Math.max(0,file.size-blob.size),savedPercent:file.size?Math.round(Math.max(0,file.size-blob.size)/file.size*100):0,stats};
}
async function imageToWebPDataURL(file,options){
  const result=await imageToWebP(file,options);result.dataUrl=await imageBlobDataURL(result.blob);return result;
}
function imageErrorMessage(error){
  const code=String(error&&error.code||error&&error.message||'');
  if(code==='image_too_large')return 'حجم تصویر از ۱۵ مگابایت بیشتر است؛ تصویر کوچک‌تری انتخاب کنید.';
  if(code==='image_dimensions_too_large')return 'ابعاد تصویر برای تبدیل امن بیش از اندازه بزرگ است؛ آن را کوچک‌تر کنید.';
  if(code==='animated_image_not_supported')return 'این تصویر چندفریمی است؛ برای آن‌که فریم‌ها بی‌صدا از دست نروند، تصویر متحرک پذیرفته نمی‌شود. یک نسخهٔ ثابت انتخاب کنید.';
  if(code==='webp_unsupported')return 'تبدیل WebP در این مرورگر در دسترس نیست؛ مرورگر را به‌روز کنید و دوباره امتحان کنید.';
  if(code==='image_canvas_unavailable')return 'ابزار تبدیل تصویر در این مرورگر در دسترس نیست؛ نسخهٔ اصلی ذخیره نشد.';
  if(code==='image_file_required')return 'فقط یک فایل تصویر معتبر انتخاب کنید.';
  if(code==='image_read_failed')return 'فایل تصویر خوانده نشد؛ دوباره انتخابش کنید.';
  return 'تصویر تبدیل نشد؛ نسخهٔ اصلی ذخیره نشده است. دوباره امتحان کنید.';
}

/* شاخص‌های مرورگر فقط در همین صفحه و در همین دستگاه اندازه‌گیری می‌شوند. */
const PAGE_VITALS={lcp:null,cls:0,lcpSupported:false,clsSupported:false,inpSupported:false,longTaskSupported:false,interactions:new Map(),longTaskCount:0,longTaskMs:0,clientErrors:0};
const PAGE_LOADER_INERT=new Map();
let PAGE_LOADER_CONTROLLER=null,PAGE_LOADER_FOCUS=null;
function observePageVitals(){
  addEventListener('error',event=>{if(!event.target||event.target===window)PAGE_VITALS.clientErrors++});
  addEventListener('unhandledrejection',()=>{PAGE_VITALS.clientErrors++});
  if(typeof PerformanceObserver!=='function')return;
  const observe=(type,handler,options)=>{
    try{const observer=new PerformanceObserver(list=>handler(list.getEntries()));observer.observe(Object.assign({type,buffered:true},options||{}));return observer}catch(e){return null}
  };
  if(observe('largest-contentful-paint',entries=>entries.forEach(entry=>{PAGE_VITALS.lcp=Math.max(PAGE_VITALS.lcp||0,+entry.startTime||0)})))PAGE_VITALS.lcpSupported=true;
  if(observe('layout-shift',entries=>entries.forEach(entry=>{if(!entry.hadRecentInput)PAGE_VITALS.cls+=+entry.value||0})))PAGE_VITALS.clsSupported=true;
  if(observe('event',entries=>entries.forEach(entry=>{
    const id=+entry.interactionId||0;if(!id)return;
    PAGE_VITALS.interactions.set(id,Math.max(PAGE_VITALS.interactions.get(id)||0,+entry.duration||0));
    if(PAGE_VITALS.interactions.size>500)PAGE_VITALS.interactions.delete(PAGE_VITALS.interactions.keys().next().value);
  }),{durationThreshold:16}))PAGE_VITALS.inpSupported=true;
  if(observe('longtask',entries=>entries.forEach(entry=>{PAGE_VITALS.longTaskCount++;PAGE_VITALS.longTaskMs+=+entry.duration||0})))PAGE_VITALS.longTaskSupported=true;
}
function roundedMetric(value){return value!==null&&value!==undefined&&value!==''&&Number.isFinite(+value)&&+value>=0?Math.round(+value):null}
function performanceSnapshot(){
  const perf=window.performance||{},entries=(()=>{try{return perf.getEntriesByType('navigation')||[]}catch(e){return []}})(),nav=entries[0]||null;
  const resources=(()=>{try{return perf.getEntriesByType('resource')||[]}catch(e){return []}})();
  const transfer=resources.reduce((sum,item)=>sum+(+item.transferSize||0),0),decoded=resources.reduce((sum,item)=>sum+(+item.decodedBodySize||0),0);
  const interactions=[...PAGE_VITALS.interactions.values()].sort((a,b)=>a-b);
  const inp=interactions.length?interactions[Math.max(0,Math.ceil(interactions.length*.98)-1)]:null;
  const stats=imageOptimizationStats();
  return {
    ttfb:nav?roundedMetric(nav.responseStart-nav.startTime):null,
    domReady:nav?roundedMetric(nav.domContentLoadedEventEnd):null,
    load:nav&&+nav.loadEventEnd?roundedMetric(nav.loadEventEnd):null,
    lcp:PAGE_VITALS.lcpSupported?roundedMetric(PAGE_VITALS.lcp):null,
    cls:PAGE_VITALS.clsSupported?Math.round(PAGE_VITALS.cls*1000)/1000:null,
    inp:PAGE_VITALS.inpSupported?roundedMetric(inp):null,
    interactions:interactions.length,resources:resources.length,transferBytes:transfer||null,decodedBytes:decoded||null,
    longTaskCount:PAGE_VITALS.longTaskSupported?PAGE_VITALS.longTaskCount:null,
    longTaskMs:PAGE_VITALS.longTaskSupported?Math.round(PAGE_VITALS.longTaskMs):null,clientErrors:PAGE_VITALS.clientErrors,
    imageConversions:stats.count,imageInputBytes:stats.inputBytes,imageOutputBytes:stats.outputBytes,
    imageSavedBytes:Math.max(0,stats.inputBytes-stats.outputBytes)
  };
}
async function checkApiHealth(timeoutMs){
  const timeout=Math.max(1000,Math.min(15000,+timeoutMs||6000)),started=performance.now();
  if(typeof fetch!=='function')return {ok:false,reachable:false,status:0,mode:'unavailable',latencyMs:null,error:'fetch_unavailable'};
  const controller=typeof AbortController==='function'?new AbortController():null;
  let timer=0;
  try{
    const abort=()=>{if(controller)controller.abort()};
    if(controller)timer=setTimeout(abort,timeout);
    const response=await fetch('/api/health',{method:'GET',credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'},...(controller?{signal:controller.signal}:{})});
    const data=await response.json().catch(()=>({}));
    const latencyMs=Math.round(performance.now()-started);
    return {ok:!!response.ok&&data.ok!==false,reachable:true,status:+response.status||0,mode:String(data.mode||'unknown'),
      latencyMs,formsEnabled:data.formsEnabled===true,responsesEnabled:data.responsesEnabled===true,
      deliveryEnabled:data.deliveryEnabled===true};
  }catch(e){return {ok:false,reachable:false,status:0,mode:'unavailable',latencyMs:Math.round(performance.now()-started),
    error:e&&e.name==='AbortError'?'timeout':'network_error'}}
  finally{if(timer)clearTimeout(timer)}
}
function ensurePageLoader(){
  let root=document.getElementById('noraPageLoader');if(root||!document.body)return root;
  document.body.insertAdjacentHTML('beforeend',`<div id="noraPageLoader" class="nora-page-loader" hidden aria-hidden="true" role="dialog" aria-label="بارگذاری سامانه مدیریت آموزش نورا" tabindex="-1">
    <div class="nora-loader-card"><div class="nora-loader-head">
      <span class="nora-loader-mark" aria-hidden="true"><img src="nora-mark-mini.svg" alt=""/></span>
      <span class="nora-loader-copy" role="status" aria-live="polite"><b>در حال بارگذاری…</b><small>سامانه مدیریت آموزش نورا</small></span>
      </div><div class="nora-loader-clock" aria-label="زمان‌سنج" aria-live="off">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="13" r="8.2"/><path d="M12 8.5v4.8l3 1.8M9 2.8h6M12 2.8v2"/></svg>
        <span data-loader-seconds aria-hidden="true">۰۰:۰۰</span></div>
      <div class="nora-loader-warning" data-loader-warning hidden role="alert" aria-live="assertive">
        <span class="nora-loader-warning-copy"><b>۱۰ ثانیه و هنوز اینجایید</b><span>وضعیت اینترنت را بررسی کنید.</span></span>
        <button class="nora-loader-retry" type="button" data-loader-retry>تلاش دوباره</button>
      </div></div></div>`);
  return document.getElementById('noraPageLoader');
}
function showPageLoader(){
  const root=ensurePageLoader(),settings=performanceSettings();
  if(!root||!settings.loaderEnabled)return;
  const warning=root.querySelector('[data-loader-warning]'),retry=root.querySelector('[data-loader-retry]');
  if(root.hidden)PAGE_LOADER_FOCUS=document.activeElement&&document.activeElement!==document.body?document.activeElement:null;
  root.hidden=false;root.classList.add('is-visible');root.setAttribute('aria-hidden','false');root.setAttribute('aria-modal','true');
  Array.from(document.body.children).forEach(child=>{if(child===root)return;if(!PAGE_LOADER_INERT.has(child))PAGE_LOADER_INERT.set(child,child.hasAttribute('inert'));child.setAttribute('inert','')});
  document.body.setAttribute('aria-busy','true');
  if(warning)warning.hidden=true;
  try{root.focus({preventScroll:true})}catch(e){try{root.focus()}catch(_){}}
  if(retry&&retry.dataset.bound!=='1'){
    retry.dataset.bound='1';retry.addEventListener('click',()=>location.reload());
  }
}
function hidePageLoader(){
  const root=document.getElementById('noraPageLoader');if(!root)return;
  root.classList.remove('is-visible');root.setAttribute('aria-hidden','true');root.removeAttribute('aria-modal');
  root.hidden=true;document.body.removeAttribute('aria-busy');
  PAGE_LOADER_INERT.forEach((wasInert,child)=>{if(!child.isConnected)return;if(wasInert)child.setAttribute('inert','');else child.removeAttribute('inert')});PAGE_LOADER_INERT.clear();
  const focus=PAGE_LOADER_FOCUS;PAGE_LOADER_FOCUS=null;
  if(focus&&focus.isConnected&&typeof focus.focus==='function'&&!(focus.closest&&focus.closest('[inert]')))try{focus.focus({preventScroll:true})}catch(e){try{focus.focus()}catch(_){}}
}
function initPageLoader(){
  const root=ensurePageLoader();
  /* صفحهٔ ورود سبک است و نباید پشت رویداد load گیر کند؛ صفحه پیش از این بسته می‌شود */
  if(window.NORA_PAGE_LOADER_OFF){hidePageLoader();return}
  if(PAGE_LOADER_CONTROLLER)PAGE_LOADER_CONTROLLER.dispose();
  hidePageLoader();
  if(!root)return;
  let navigationDone=document.readyState==='complete',startedAt=performance.now(),delayTimer=0,warningTimer=0,tickTimer=0,loadBound=false;
  const nav=(()=>{try{return performance.getEntriesByType('navigation')[0]||null}catch(e){return null}})();
  if(nav&&Number.isFinite(+nav.startTime))startedAt=performance.now()-(performance.now()-Number(nav.startTime));
  const elapsed=()=>Math.max(0,performance.now()-startedAt);
  const clearTimers=()=>{clearTimeout(delayTimer);clearTimeout(warningTimer);clearInterval(tickTimer);delayTimer=warningTimer=tickTimer=0};
  const time=()=>{const node=root.querySelector('[data-loader-seconds]');if(!node)return;const seconds=Math.floor(elapsed()/1000),value=String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');node.textContent=value.replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d])};
  const finish=()=>{navigationDone=true;clearTimers();loadBound=false;hidePageLoader()};
  const onLoad=()=>finish();
  const bindLoad=()=>{if(!navigationDone&&!loadBound){loadBound=true;addEventListener('load',onLoad,{once:true})}};
  const warn=()=>{const box=root.querySelector('[data-loader-warning]');
    if(navigationDone||root.hidden||!box||!performanceSettings().loaderEnabled)return;box.hidden=false;time()};
  const start=()=>{if(navigationDone||!performanceSettings().loaderEnabled)return;showPageLoader();if(root.hidden)return;time();
    warningTimer=setTimeout(warn,Math.max(0,10_000-elapsed()));
    tickTimer=setInterval(time,250);
  };
  const onPageShow=event=>{if(event.persisted)finish()};
  const onPageHide=()=>finish();
  const onSettings=()=>{
    const settings=performanceSettings();
    if(!settings.loaderEnabled){clearTimers();hidePageLoader();return}
    if(navigationDone)return;
    bindLoad();
    if(!root.hidden)return;
    clearTimeout(delayTimer);delayTimer=setTimeout(start,Math.max(0,settings.loaderDelayMs-elapsed()));
  };
  const onClick=event=>{
    if(event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
    const anchor=event.target&&event.target.closest?event.target.closest('a[href]'):null;
    if(!anchor||anchor.hasAttribute('download')||anchor.target&&anchor.target!=='_self'||anchor.getAttribute('aria-disabled')==='true')return;
    let target;try{target=new URL(anchor.href,location.href)}catch(e){return}
    if(target.origin!==location.origin||(target.pathname===location.pathname&&target.search===location.search))return;
    if(target.hash&&target.pathname===location.pathname&&target.search===location.search)return;
    const settings=performanceSettings();if(!settings.loaderEnabled)return;
    navigationDone=false;startedAt=performance.now();clearTimers();
    delayTimer=setTimeout(start,settings.loaderDelayMs);
    Promise.resolve().then(()=>{if(event.defaultPrevented){navigationDone=true;clearTimers();hidePageLoader()}});
  };
  const dispose=()=>{
    clearTimers();if(loadBound)removeEventListener('load',onLoad);
    removeEventListener('pageshow',onPageShow);removeEventListener('pagehide',onPageHide);
    removeEventListener('click',onClick,true);removeEventListener('nora:performance-settings',onSettings);
  };
  PAGE_LOADER_CONTROLLER={dispose};
  bindLoad();
  if(!navigationDone&&performanceSettings().loaderEnabled)
    delayTimer=setTimeout(start,Math.max(0,performanceSettings().loaderDelayMs-elapsed()));
  addEventListener('pageshow',onPageShow);addEventListener('pagehide',onPageHide);
  addEventListener('click',onClick,true);addEventListener('nora:performance-settings',onSettings);
}
/* برچسبها و انتخابهای پنل: یک جا تا خانه و پنل یکی بمانند */
const UISET_META={
  home:[['bnr','بنرها'],['stories','استوریها'],['search','جستوجو'],['quick','منوی سریع'],['pins','سنجاقشدهها'],['mine','برای تو'],['events','برنامههای نزدیک'],['past','کارگاههای برگزارشده'],['club','باشگاه کتاب'],['teachers','اساتید'],['staff','دستاندرکاران'],['articles','مقالات'],['partners','نهادهای همکار'],['voices','نظر شرکتکنندهها'],['act','نمای فعالیت ماهانه']],
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
  return M.map(g=>{
    const rows=(g.rows||[]).filter(r=>!U.menu.includes(r.t)).map(row=>{
      const href=String(row&&row.href||'');
      return ACCOUNT_NEXT_RE.test(href)?{...row,href:accountEntryHref(href)}:row;
    });
    const accountGroup=/^(?:حساب من|حساب کاربری|ورود\/ثبت‌نام)/.test(String(g.g||''));
    if(rows.length&&accountGroup&&!rows.some(r=>/^(?:حساب من|ورود\/ثبت‌نام)/.test(String(r.t||'')))){
      rows.unshift({i:'i-idcard',t:'حساب من',s:'ورود به حساب نورا',href:accountEntryHref('account.html')});
    }
    return {g:g.g,i:g.i,rows};
  }).filter(g=>g.rows.length);
}
function menuGroupLabel(value){
  return /^(?:حساب من|ورود\/ثبت‌نام)(?:\s*·.*)?$/.test(String(value||'').trim())?'حساب کاربری':value;
}
function menuRowLabel(value){
  const text=String(value||'').trim();
  if(/^(?:حساب من|ورود\/ثبت‌نام)(?:\s*·.*)?$/.test(text))
    return accountFirstName(sessUser())||'ورود/ثبت‌نام';
  if(/^پروفایل من(?:\s*·.*)?$/.test(text)) return accountFirstName(sessUser())||'ورود/ثبت‌نام';
  if(/^پروفایل‌ها$/.test(text)) return accountFirstName(sessUser())||'ورود/ثبت‌نام';
  return value;
}
/* ══ خط اطمینان، هر [data-trust] را با جملهٔ کوتاه خودش پر می‌کند ═══ */
function trustPick(kind){
  const T=(window.NORA&&window.NORA.TRUST)||{}, rows=T.row||[], short=T.short||{};
  if(short[kind]) return short[kind];
  const hit=rows.find(r=>String(r[0]).indexOf(kind)>-1);
  return (hit&&hit[1])||(rows[0]&&rows[0][1])||'این نسخهٔ پیش‌نمایشی اطلاعات را فقط در همین مرورگر نگه می‌دارد.';
}
function fillTrust(root){
  const scope=root||document, U=uiSet();
  [...scope.querySelectorAll('[data-trust]')].forEach(el=>{
    if(!NORA_TEST_FIXTURE_MODE||!U.trust.on){el.hidden=true; return}
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
const playerIcon=name=>`<svg class="i" aria-hidden="true"><use href="#${escH(name)}"/></svg>`;
function evPosterCard(e,o){
  o=o||{};
  /* دو حالت: پیوند (خانه) یا دکمهٔ ورقهٔ جزئیات (صفحهٔ رویدادها) */
  const act=o.href?`href="${escH(o.href)}"`:`data-${o.key||'ev'}="${escH(e.id)}"`;
  const wrap=o.href?'a':'button';
  const p=o.person||null;
  const tags=(o.tags||[]).filter(Boolean).map(t=>`<span class="evc-tag${o.past&&t==='برگزار شد'?' dark':''}">${escH(t)}</span>`).join('');
  const metas=(o.meta||[]).filter(Boolean).map(m=>`<span class="mi"><svg class="i"><use href="#${m[0]}"/></svg>${escH(m[1])}</span>`).join('');
  const partnerMeta=o.partner&&o.partner.id?`<button class="mi mi-partner" type="button" data-partner="${escH(o.partner.id)}" aria-label="نهاد همکار: ${escH(o.partner.n||'')}"><svg class="i"><use href="#i-handshake"/></svg>${escH(o.partner.n||'')}</button>`:'';
  const cover=e.poster
    ? `<img src="${escH(e.poster)}" alt="پوستر ${escH(e.t)}" loading="lazy" decoding="async"/>`
    : `<span class="evc-grad" style="--g:${escH(e.g||'')}"><svg class="i"><use href="#${escH(e.icon||'i-calendar')}"/></svg></span>`;
  const ctaTag=o.ctaHref?'a':wrap;
  const ctaAct=o.ctaHref?`href="${escH(o.ctaHref)}"`:act;
  const cta=o.cta?`<${ctaTag} class="btn sm evc-cta ${o.ctaKind||'primary'}" ${ctaAct}>
      <svg class="i"><use href="#${o.ctaIcon||'i-pen'}"/></svg> ${escH(o.cta)}</${ctaTag}>`:'';
  return `<article class="evcard${o.past?' past':''}${o.cls?' '+o.cls:''}">
    <${wrap} class="evc-cov" ${act} aria-label="جزئیات ${escH(e.t)}">
      ${cover}
      ${tags?`<span class="evc-tags">${tags}</span>`:''}
      ${o.badge?`<span class="evc-day">${o.badge}</span>`:''}
    </${wrap}>
    <div class="evc-body">
      <div class="evc-ttl">${escH(e.t)}</div>
      ${metas||partnerMeta?`<div class="evc-meta">${metas}${partnerMeta}</div>`:''}
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
const PRE_KEY='nora-home-prereg';                 /* پیش‌ثبت‌نام محلی؛ پیامک و اعلان واقعی وصل نیست */
const jread=(k,d)=>{try{const v=JSON.parse(localStorage.getItem(k)||'null'); return v==null?d:v}catch(e){return d}};
const jwrite=(k,v)=>{try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}};
/* صف تأیید مالک و گواهینامه‌های صادرشده: انبار محلیِ پیش‌نمایش، نه مرجع امن */
const OWNER_APPROVAL_KEY='nora-owner-approvals', ISSUED_CERTS_KEY='nora-issued-certificates';
function ownerApprovals(){const v=jread(OWNER_APPROVAL_KEY,[]); return Array.isArray(v)?v:[]}
function ownerApprovalAdd(item){
  const row=Object.assign({id:'oa'+Date.now().toString(36)+Math.random().toString(36).slice(2,7),
    type:'notification',status:'pending',createdAt:Date.now()},item||{});
  const rows=ownerApprovals();
  if(row.dedupeKey){const old=rows.find(x=>x&&x.status==='pending'&&x.dedupeKey===row.dedupeKey);if(old)return old}
  rows.unshift(row); jwrite(OWNER_APPROVAL_KEY,rows.slice(0,500)); return row;
}
function ownerApprovalPatch(id,patch){
  let hit=null; const rows=ownerApprovals().map(x=>{
    if(x&&String(x.id)===String(id)){hit=Object.assign({},x,patch||{});return hit} return x;
  });
  if(hit) jwrite(OWNER_APPROVAL_KEY,rows); return hit;
}
function certApprovalFor(id){
  if(!id) return null;
  return ownerApprovals().find(x=>x&&String(x.id)===String(id)&&
    ['cert-request','cert-batch'].includes(x.type)&&x.status==='approved'&&
    !!x.approvedById&&!!x.approvedAt&&!x.testOnly)||null;
}
function certRecipientMatches(approval,cert){
  const recs=Array.isArray(approval&&approval.recipients)?approval.recipients:
    (approval&&approval.recipient?[approval.recipient]:[]);
  if(!recs.length||!cert) return false;
  const digits=v=>String(v||'').replace(/\D/g,'').slice(-10);
  const ids=x=>[x&&x.userId,x&&x.personId].map(v=>String(v||'')).filter(Boolean);
  const certIds=ids(cert), certMobile=digits(cert.mobile), certName=String(cert.name||cert.n||'').trim();
  return recs.some(r=>{
    if(!r||typeof r!=='object') return false;
    const re=String(r.eventId||approval.eventId||''), ce=String(cert.eventId||'');
    if(re&&ce&&re!==ce) return false;
    const rid=ids(r), rm=digits(r.mobile||r.ph), rn=String(r.name||r.n||'').trim();
    if(rid.length&&certIds.length) return rid.some(v=>certIds.includes(v));
    if(rm&&certMobile) return rm===certMobile;
    return !!rn&&!!certName&&rn===certName;
  });
}
function issuedCertApproved(cert){
  const approval=certApprovalFor(cert&&cert.ownerApprovalId);
  return !!approval&&certRecipientMatches(approval,cert)&&cert.state==='issued';
}
function issuedCertificates(){
  const v=jread(ISSUED_CERTS_KEY,[]);
  return Array.isArray(v)?v.filter(issuedCertApproved):[];
}
function addIssuedCertificate(cert,approvalId){
  if(!cert||!cert.serial) return null;
  const approval=certApprovalFor(approvalId);
  if(!approval||!certRecipientMatches(approval,cert)) return null;
  const row=Object.assign({},cert,{createdAt:cert.createdAt||Date.now(),state:'issued',
    ownerApprovalId:String(approval.id),approvedBy:approval.approvedBy||cert.approvedBy||'مالک سامانه',
    approvedById:approval.approvedById,approvedAt:approval.approvedAt,localOnly:true});
  const raw=jread(ISSUED_CERTS_KEY,[]), rows=Array.isArray(raw)?raw:[];
  const i=rows.findIndex(x=>x&&String(x.serial)===String(row.serial));
  if(i>-1) rows[i]=Object.assign({},rows[i],row); else rows.unshift(row);
  jwrite(ISSUED_CERTS_KEY,rows.slice(0,3000));
  return issuedCertificates().find(x=>x&&String(x.serial)===String(row.serial))||null;
}
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
function ownerNoticesForMe(){
  const s=sessUser()||{}, p=profile()||{}, phone=String(s.mobile||'').replace(/\D/g,''), name=String(p.fullName||s.name||'').trim();
  const rows=[];
  ownerApprovals().forEach(x=>{
    if(!x||x.status!=='approved'||!x.notification||x.testOnly) return;
    if(!['notification','cert-request','cert-batch'].includes(x.type)) return;
    if(x.notificationStatus!=='approved') return;
    const n=x.notification, recs=Array.isArray(x.recipients)?x.recipients:(x.recipient?[x.recipient]:[]);
    let targets=recs.filter(r=>{
      if(x.allRecipients) return true;
      const rp=String((r&&r.mobile)||'').replace(/\D/g,''), rn=String((r&&r.name)||'').trim();
      return (phone&&rp&&phone.slice(-10)===rp.slice(-10))||(name&&rn&&name===rn);
    });
    if(!recs.length&&x.allRecipients) targets=[{name:name||s.name||''}];
    targets.forEach((r,i)=>rows.push({t:'owner:'+x.id+':'+i,i:['cert-issue','cert-request','cert-batch'].includes(x.type)?'i-medal':'i-bell',
      title:n.title||x.title||'پیام نورا',d:String(n.body||'').replace(/\{نام\}/g,r.name||name||'دوست نورا')
        .replace(/\{رویداد\}/g,r.eventTitle||x.eventTitle||'' ).replace(/\{کد\}/g,r.serial||x.serial||''),
      w:'تأیید مالک · فقط در اعلان‌های محلی؛ ارسال نشده',unread:true,ev:r.eventId||x.eventId||''}));
  });
  return rows;
}
function userNotices(){
  const base=(window.NORA&&window.NORA.NOTICES)||[];
  return ownerNoticesForMe().concat(base);
}
function unreadCount(){
  const N=userNotices(), r=readNotices();
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
  const N=userNotices(), r=readNotices();
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
      <div class="cap" style="margin-top:4px">${escH(n.w)}${n.ev?' · <button class="lnk" data-uiev="'+escH(n.ev)+'">جزئیات رویداد</button>':''}</div></span></div>`).join('')}</div>
    <p class="cap" style="margin-top:12px">اعلان‌ها همین‌جا خوانده می‌شوند؛ هر جا باشی، از خود نوار بالا باز می‌شوند.</p>`;
}

/* ── منو: پنج گروه کامل، در هر صفحه ── */
function menuSheet(){
  const M=menuAllowed(), P=(window.NORA&&window.NORA.PARTNERS)||[];
  return `<div class="grabber"></div>
    <div class="row" style="align-items:center;margin-bottom:8px">
      <div><div class="head">منوی نورا</div><div class="cap">همهٔ بخش‌ها، یک‌جا</div></div>
      <span class="sp"></span><button class="icon-btn" data-close aria-label="بستن"><svg class="i"><use href="#i-close"/></svg></button></div>
    <div class="mhead">
      <div class="mt">نورا · گروه فرهنگی خط زندگی</div>
      <div class="ms">${faN(((window.NORA&&window.NORA.EVENTS)||[]).length)} رویداد منتشرشده · ${faN(((window.NORA&&window.NORA.PEOPLE)||[]).length)} پروفایل</div>
    </div>
    ${M.map(g=>`<div class="mgroup">
      <div class="gh"><svg class="i" style="width:14px;height:14px"><use href="#${g.i}"/></svg>${escH(menuGroupLabel(g.g))}</div>
      ${g.rows.map(r=>`<button class="mrow" ${r.href?`data-uihref="${escH(r.href)}"`:r.rel?`data-uiev="${escH(r.rel)}"`:r.f?`data-uif="${escH(r.f)}"`:`data-uijump="${escH(r.j||'')}"`}>
        <span class="mi"><svg class="i nav-icon"><use href="#${r.i}"/></svg></span>
        <span class="mtx"><b>${escH(menuRowLabel(r.t))}</b><span>${escH(r.s)}</span></span>
        <span class="sp" style="flex:1"></span>
        ${r.badge?`<span class="tag">${escH(r.badge)}</span>`:''}
        ${r.tag?`<span class="tag brand">${escH(r.tag)}</span>`:''}
        <svg class="i" style="width:15px;height:15px;color:var(--ink-4)"><use href="#i-chev-left"/></svg></button>`).join('')}
    </div>`).join('')}
    ${P.length?`<div class="mfoot">
      <div class="cap">نهادهای همکار</div>
      <div class="lrow">${P.slice(0,8).map(o=>`<span class="mon" style="--g:${escH(o.g||'')};width:26px;height:26px;border-radius:8px;font-size:10px;display:grid;place-items:center;color:#fff" title="${escH(o.n)}">${escH(o.mon||o.n.slice(0,1))}</span>`).join('')}</div>
    </div>`:''}`;
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
const PLAYER_CONTEXTS=Object.create(null);
function mediaList(past,o){
  o=o||{};
  let items=past.media||[];
  if(o.filter&&o.filter!=='all') items=items.filter(m=>m.k===o.filter);
  if(!items.length) return '<div class="empty"><svg class="i"><use href="#i-archive"/></svg><p>با این صافی چیزی در این بسته نیست.</p></div>';
  const contextAttr=o.contextId?` data-uimedia-context="${escH(o.contextId)}"`:'';
  return `<div class="stack tight player-list">${items.map(m=>{
    const kd=(((window.NORA||{}).MEDIA_KINDS)||{})[m.k]||{i:'i-play',n:'رسانه'},
      st=o.forceOpen?{k:'mine',t:'در دسترس',i:'i-play'}:libState(m,past);
    const pr=progressOf(m.id), pct=pr?Math.min(100,Math.round(pr/60/90*100)):0,
      locked=!o.forceOpen&&st.k==='lock', search=[m.t,m.k,m.d,m.mime].filter(Boolean).join(' '),
      needsBot=mediaNeedsBot(m), receiveHref=needsBot&&m.available&&m.delivery_id?baleStartHref('file_'+m.delivery_id):'';
    const playAttr=`data-uimedia="${escH(past.id)}:${escH(m.id)}"${contextAttr}`;
    return `<div class="mrow2 ${locked?'locked':''}" data-player-search="${escH(search)}">
      ${needsBot?`<span class="mthumb ${escH(m.k)}" aria-hidden="true">
        <svg class="i" style="width:19px;height:19px"><use href="#${locked?'i-lock':'i-doc'}"/></svg>
        ${pct?`<span class="mprog"><i style="width:${pct}%"></i></span>`:''}
      </span>`:`<button class="mthumb ${escH(m.k)}" ${playAttr} aria-label="${locked?'خرید':'پخش'} ${escH(m.t)}">
        <svg class="i" style="width:19px;height:19px"><use href="#${locked?'i-lock':kd.i}"/></svg>
        ${pct?`<span class="mprog"><i style="width:${pct}%"></i></span>`:''}
      </button>`}
      <span class="mtx"><b>${escH(m.t)}</b>
        <small>${escH(kd.n)} · ${escH(m.d)}${m.s?' · '+escH(m.s):''}${pr?' · نیمه‌کاره':''}</small></span>
      <span class="sp" style="flex:1"></span>
      ${locked
        ? `<button class="btn sm quiet" data-uibuy="${escH(past.id)}:${escH(m.id)}">${st.t}</button>`
        : needsBot
          ? receiveHref?`<a class="btn sm primary" href="${escH(receiveHref)}" target="_blank" rel="noopener noreferrer">${ico('i-send')} دریافت از بات بله</a>`:`<span class="tag warn">دریافت از بات در دسترس نیست</span>`
          : `<button class="btn sm ${st.k==='mine'?'quiet':'primary'}" ${playAttr}>
             <svg class="i"><use href="#${kd.i}"/></svg> ${st.k==='open'&&m.preview?'تماشای نمونه':kd.v}</button>`}
    </div>`}).join('')}</div>`;
}
/* کارت بستهٔ آرشیو (برگزارشده‌ها) */
function bundleCard(past,o){
  const p=((window.NORA&&window.NORA.PEOPLE)||[]).find(x=>x.id===past.tchr)||{n:'—',ini:'؟',r:'',g:''};
  const chips=Object.keys(past.counts||{}).map(k=>`<span class="tag">${faN(past.counts[k])} ${((((window.NORA||{}).MEDIA_KINDS)||{})[k]||{}).n||''}</span>`).join('');
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
        ${mine?'پخش و دریافت':past.price?'بررسی دسترسی':'بازکردن آرشیو رایگان'}</button>
    </div>
  </article>`;
}

/* ── پیش‌ثبت‌نام محلی: فقط در همین مرورگر ذخیره می‌شود و اعلان واقعی نمی‌فرستد ── */
function preList(){const a=jread(PRE_KEY,[]); return Array.isArray(a)?a:[]}
function isPre(id){return preList().indexOf(id)>-1}
function prereg(id,after){
  const N=window.NORA||{}, e=(N.EVENTS||[]).find(x=>x.id===id);
  if(!e) return;
  if(!NORA_TEST_FIXTURE_MODE){ location.href='event.html?id='+encodeURIComponent(id); return }   /* پیش‌ثبت‌نام محلی فقط در fixture آزمون */
  if(!walletUser()){ authSheet(()=>prereg(id,after)); return }
  const a=preList();
  if(a.indexOf(id)>-1){
    jwrite(PRE_KEY,a.filter(x=>x!==id));
    toast('پیش‌ثبت‌نامت برداشته شد');
  } else {
    a.push(id); jwrite(PRE_KEY,a);
    toast('پیش‌ثبت‌نام محلی ثبت شد؛ پیامک و اعلان واقعی به سامانه وصل نیست');
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
  const partner=(N.PARTNERS||[]).find(item=>String(item.id)===String(e.partnerId))||null;
  const past=PE?(!!PE.past):!!H, price1=e.price||0, full=e.cap&&(e.cap-e.taken)<=0;
  const tag=t=>`<span class="tag ${t[1]||''}">${escH(t[0])}</span>`;
  const when=past?e.d:(e.when+' · ساعت '+e.time);
  const room=e.mode&&e.mode.indexOf('حضوری')<0?'آنلاین':(e.mode==='حضوری و آنلاین'?'حضوری و آنلاین':'حضوری');
  const online=room!=='حضوری';
  const href='event.html?id='+encodeURIComponent(e.id);
  const hasFree=(e.media||[]).some(m=>!m.p||m.preview);
  const previewBtn=(past&&hasFree)?`<button class="btn quiet" data-uipreview="${escH(e.id)}"><svg class="i"><use href="#i-play-f"/></svg> پیش‌نمایش</button>`:'';
  const preOn=!past&&isPre(e.id);
  const preBtn=(past||!NORA_TEST_FIXTURE_MODE)?'':`<button class="btn ${preOn?'primary':'quiet'}" data-uipre="${escH(e.id)}"><svg class="i"><use href="#${preOn?'i-check':'i-bell'}"/></svg> ${preOn?'پیش‌ثبت‌نام شده':'پیش‌ثبت‌نام'}</button>`;
  const mediaHtml=past?`
    <div class="sec-hd" style="margin-top:14px"><span class="fw">رسانه‌های این رویداد</span><span class="sp"></span>
      <span class="cap">${faN(e.mediaCount||((e.media||[]).length))} فایل</span></div>
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
      ${partner?`<a class="srow" href="home.html#partner=${encodeURIComponent(partner.id)}"><svg class="i"><use href="#i-handshake"/></svg><span class="sp">نهاد همکار</span><b>${escH(partner.n)}</b><svg class="i"><use href="#i-chev-left"/></svg></a>`:''}
      ${past&&e.rec?`<div class="srow"><svg class="i"><use href="#i-layers"/></svg><span class="sp">جلسه‌ها</span><b>${escH(e.rec)}</b></div>`:''}
      ${past?`<div class="srow"><svg class="i"><use href="#i-play"/></svg><span class="sp">رسانه‌ها</span><b>${faN(e.mediaCount)} قلم · ${faN(e.sold)} خرید</b></div>`
           :`<div class="srow"><svg class="i"><use href="#i-users"/></svg><span class="sp">${e.cap?faN(e.taken)+' نفر ثبت‌نام کرده‌اند':'همه می‌توانند شرکت کنند'}</span><b>${price(price1)}</b></div>`}
      ${online?`<div class="srow"><svg class="i"><use href="#i-video"/></svg><span class="sp">${past?'این برنامه ضبط شده؛ آنلاین تماشا می‌کنی':'جلسه آنلاین؛ لینک ورود ۱۵ دقیقه قبل می‌آید'}</span><b>${escH(past?'ضبط شده':'زنده')}</b></div>`:''}
    </div>
    ${(!past&&e.cap)?`<div class="bar" style="margin-top:10px"><i style="width:${Math.round(e.taken/e.cap*100)}%"></i></div>
      <div class="cap" style="margin-top:6px">${full?'ظرفیت نمونه تکمیل است؛ صف انتظار واقعی وصل نیست':'شمار ظرفیت نمایشی: '+faN(e.cap-e.taken)+' جا از '+faN(e.cap)+' نفر'}</div>`:''}
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
const safeHttpsMediaUrl=value=>{
  const raw=String(value||'').trim();
  if(!raw||raw.length>2048||/[\u0000-\u0020\u007f]/.test(raw)) return '';
  try{
    const u=new URL(raw);
    if(u.protocol!=='https:'||u.username||u.password||(u.port&&u.port!=='443')) return '';
    const host=u.hostname.toLowerCase().replace(/\.$/,'');
    if(!host||host==='localhost'||host.endsWith('.localhost')||host.endsWith('.local')) return '';
    const ip=host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
    if(ip){const a=+ip[1],b=+ip[2],c=+ip[3];
      if(a>255||b>255||c>255||+ip[4]>255||a===0||a===10||a===127||a>=224||
        (a===100&&b>=64&&b<=127)||(a===169&&b===254)||(a===172&&b>=16&&b<=31)||
        (a===192&&(b===0||b===168))||(a===198&&(b===18||b===19||b===51&&c===100))||
        (a===203&&b===0&&c===113)) return '';
    }
    if(host.startsWith('[')&&host.endsWith(']')){
      const v6=host.slice(1,-1).toLowerCase(), halves=v6.split('::');
      if(halves.length>2)return '';
      const left=halves[0]?halves[0].split(':'):[], right=halves.length===2&&halves[1]?halves[1].split(':'):[];
      if(left.concat(right).some(x=>!/^\w{1,4}$/.test(x)||!/^[0-9a-f]{1,4}$/i.test(x)))return '';
      const words=left.map(x=>parseInt(x,16)).concat(Array(Math.max(0,8-left.length-right.length)).fill(0),right.map(x=>parseInt(x,16)));
      if(words.length!==8)return '';
      const first=words[0], zeroPrefix=words.slice(0,6).every(x=>x===0), mapped=words.slice(0,5).every(x=>x===0)&&words[5]===0xffff;
      const v4a=words[6]>>8,v4b=words[6]&255,v4c=words[7]>>8,v4d=words[7]&255;
      const mappedPrivate=mapped&&(v4a===0||v4a===10||v4a===127||v4a>=224||
        (v4a===100&&v4b>=64&&v4b<=127)||(v4a===169&&v4b===254)||(v4a===172&&v4b>=16&&v4b<=31)||
        (v4a===192&&(v4b===0||v4b===168))||(v4a===198&&(v4b===18||v4b===19||v4b===51&&v4c===100))||
        (v4a===203&&v4b===0&&v4c===113));
      if(first<0x2000||first>=0x4000||first===0x2001&&(words[1]===0||words[1]===0x0db8)||
        first===0x2002||zeroPrefix||mappedPrivate)return '';
    }
    return u.href;
  }catch(e){return ''}
};
const baleStartHref=payload=>{
  const N=window.NORA||{}, raw=String(N.BALE_BOT_URL||window.NORA_PUBLIC_BALE_BOT_URL||'').trim();
  let base='';
  if(/^https:\/\/ble[.]ir\/[A-Za-z0-9_]{3,64}$/i.test(raw)) base=raw;
  else if(location.protocol==='file:') {
    const username=String((N.ADMIN&&N.ADMIN.bale)||'').replace(/^@/,'').trim();
    if(/^[A-Za-z0-9_]{3,64}$/.test(username)) base='https://ble.ir/'+username;
  }
  const start=String(payload||'');
  return base&&/^[A-Za-z0-9_-]{1,64}$/.test(start)?base+'?start='+encodeURIComponent(start):'';
};
const mediaNeedsBot=m=>{
  const kind=String(m&&m.k||'').toLowerCase(), mime=String(m&&m.mime||m&&m.content_type||'').toLowerCase();
  const playable=['audio','video','aud','vid'].includes(kind)||mime.startsWith('audio/')||mime.startsWith('video/');
  return !playable&&(!!(m&&m.delivery_id)||['image','pdf','slide','file','document'].includes(kind)
    ||mime.startsWith('application/')||mime.startsWith('image/')
    ||/[.](pdf|zip|epub|docx|pptx|ppt|jpe?g|png|webp)(?:[?#]|$)/i.test(String(m&&m.t||m&&m.url||m&&m.src||'')));
};
const safeMediaUrl=m=>{
  if(mediaNeedsBot(m)) return '';
  const u=String((m&&m.src)||(m&&m.url)||'').trim();
  /* فقط پخشِ ویدیو/صدا و تصویرهای نمایشی؛ سند از بات دریافت می‌شود. */
  if(/^data:(?:image\/(?:png|jpe?g|gif|webp|avif)|audio\/[\w.+-]+|video\/[\w.+-]+);base64,/i.test(u)) return u;
  return safeHttpsMediaUrl(u);
};
const directMediaUrl=(m,u)=>{
  if(!u||m.k==='link') return false;
  if(u.indexOf('data:')===0) return true;
  let path=''; try{path=new URL(u).pathname.toLowerCase()}catch(e){return false}
  const mime=String(m.mime||'').toLowerCase();
  const ext={video:/\.(?:mp4|m4v|webm|ogv|mov)$/i,audio:/\.(?:mp3|m4a|wav|ogg|aac|flac|opus)$/i,
    image:/\.(?:png|jpe?g|gif|webp|avif)$/i,pdf:/\.pdf$/i};
  /* MIME به‌تنهایی برای تبدیل یک صفحهٔ ناشناس به منبع ویدیو کافی نیست؛
     مسیرِ مستقیم باید پسوند رسانه داشته باشد. */
  if(ext[m.k]&&ext[m.k].test(path)) return true;
  if(m.k==='pdf'&&mime==='application/pdf'&&safeHttpsMediaUrl(u)) return true;
  return false;
};
function videoEmbedInfo(value){
  const href=safeHttpsMediaUrl(value); if(!href) return null;
  let u; try{u=new URL(href)}catch(e){return null}
  const host=u.hostname.toLowerCase().replace(/^www\./,'').replace(/^m\./,''), path=u.pathname;
  let id='';
  if(host==='youtu.be') id=path.split('/').filter(Boolean)[0]||'';
  else if(host==='youtube.com'||host==='youtube-nocookie.com'){
    id=u.searchParams.get('v')||((path.match(/^\/(?:embed|shorts|live)\/([A-Za-z0-9_-]{11})(?:\/|$)/)||[])[1]||'');
  }
  if(/^(?:youtube\.com|youtube-nocookie\.com|youtu\.be)$/.test(host)&&/^[A-Za-z0-9_-]{11}$/.test(id))
    return {provider:'youtube',id:id,url:href,src:'https://www.youtube-nocookie.com/embed/'+id+'?rel=0'};
  if(host==='aparat.com'){
    const m=path.match(/^\/(?:video\/video\/embed\/videohash\/|v\/|embed\/)([A-Za-z0-9_-]{3,64})(?:\/|$)/i);
    if(m) return {provider:'aparat',id:m[1],url:href,src:'https://www.aparat.com/video/video/embed/videohash/'+encodeURIComponent(m[1])+'/vt/frame'};
  }
  if(host==='vimeo.com'||host==='player.vimeo.com'){
    const m=path.match(/^\/(?:video\/)?(\d{5,20})(?:\/|$)/);
    if(m) return {provider:'vimeo',id:m[1],url:href,src:'https://player.vimeo.com/video/'+m[1]+'?dnt=1'};
  }
  if(host==='dailymotion.com'||host==='dai.ly'){
    const m=path.match(host==='dai.ly'?/^\/([A-Za-z0-9]+)(?:\/|$)/:/^\/video\/([A-Za-z0-9]+)(?:\/|$)/i);
    if(m) return {provider:'dailymotion',id:m[1],url:href,src:'https://www.dailymotion.com/embed/video/'+encodeURIComponent(m[1])};
  }
  return null;
}
function mediaDurationLabel(m){
  const seconds=Number(m&&m.durationSec)||0;
  if(seconds>0) return faN(Math.floor(seconds/60))+':'+String(faN(Math.floor(seconds%60))).padStart(2,'۰');
  const raw=String((m&&m.d)||''), match=raw.match(/[0-9۰-۹]+/);
  if((m.k==='video'||m.k==='audio')&&match&&/دقیقه/.test(raw))
    return faN(Number(unFa(match[0])||0))+':۰۰';
  return raw||'—';
}
const PLAYER_BOOKMARK_KEY='nora-player-bookmarks';
function playerBookmarks(id){
  const all=jread(PLAYER_BOOKMARK_KEY,{}); return Array.isArray(all&&all[id])?all[id]:[];
}
function playerTimeText(sec){sec=Math.max(0,Math.floor(+sec||0));return faN(Math.floor(sec/60))+':'+String(faN(sec%60)).padStart(2,'۰')}
function playerBookmarkRows(id){
  const rows=playerBookmarks(id).slice(-24);
  return rows.length?rows.map((x,i)=>`<button class="chip" type="button" data-uibookmark-go="${Math.max(0,+x.sec||0)}" data-media-id="${escH(id)}" aria-label="رفتن به نشان ${faN(i+1)} در ${playerTimeText(x.sec)}">${faN(i+1)} · ${playerTimeText(x.sec)}</button>`).join('')
    :'<span class="cap">هنوز لحظه‌ای نشان‌گذاری نشده است.</span>';
}
function renderPlayerMarks(id){
  const el=[...document.querySelectorAll('#shPlay [data-player-marks]')].find(x=>x.dataset.playerMarks===String(id));
  if(el) el.innerHTML=playerBookmarkRows(id);
}
function restorePlayerSheet(id){
  const player=document.getElementById('shPlay'), parent=document.getElementById(String(id||''));
  if(player){player.classList.remove('on');player.setAttribute('aria-modal','false')}
  if(parent){parent.classList.add('on');parent.setAttribute('aria-modal','true')}
  document.querySelectorAll('.sheet').forEach(s=>{if(s!==parent&&s!==player)s.setAttribute('aria-modal','false')});
  const scrim=document.getElementById('scrim'); if(scrim)scrim.classList.toggle('on',!!parent||!!player);
  try{window.dispatchEvent(new CustomEvent('nora:player-return',{detail:{id:String(id||''),eventId:String(PLAY&&PLAY.past||'')}}))}catch(e){}
}
function player(pastId,mediaId,options){
  const N=window.NORA||{}, U=window.NORA_UI||{};
  let opts=options||{};
  if(opts.contextId) PLAYER_CONTEXTS[opts.contextId]=opts;
  const H=(opts.event&&typeof opts.event==='object'?opts.event:null)||
    (N.PAST||[]).find(x=>String(x.id)===String(pastId))||
    (U.pubEvents?U.pubEvents().find(x=>String(x.id)===String(pastId)&&x.past):null);
  const media=Array.isArray(opts.media)?opts.media:(H&&H.media);
  if(!H||!Array.isArray(media)) return;
  const listEvent=media===H.media?H:Object.assign({},H,{media:media});
  const i=media.findIndex(x=>String(x.id)===String(mediaId)); if(i<0) return;
  const m=media[i], kd=(N.MEDIA_KINDS||{})[m.k]||{n:'رسانه',v:'باز کردن'}, src=safeMediaUrl(m),
    direct=directMediaUrl(m,src), originalUrl=String(m.url||m.src||''), external=!!safeHttpsMediaUrl(originalUrl),
    embed=m.k==='video'?videoEmbedInfo(originalUrl):null, nx=media[i+1], pv=media[i-1],
    noDownload=!!opts.noDownload||['audio','video'].includes(String(m.k||'')), forceOpen=!!opts.forceOpen, contextId=String(opts.contextId||'');
  if(m.p&&!forceOpen&&!hasLib(m.id)&&!hasLib(H.id)){buySheet(pastId,mediaId); return}
  if(PLAY.timer) clearInterval(PLAY.timer);
  PLAY={id:m.id,past:pastId,item:m,sec:0,len:0,rate:1,playing:false,timer:null};
  let stage='';
  if(m.k==='video'&&embed) stage=`<div class="account-player-embed"><iframe title="${escH(m.t)}" src="${escH(embed.src)}" loading="lazy" referrerpolicy="strict-origin-when-cross-origin"
      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe></div>`;
  else if(m.k==='video'&&direct) stage=`<video controls playsinline preload="metadata" ${noDownload?'controlsList="nodownload"':''}
      style="width:100%;max-height:62vh;border-radius:16px;background:#000" src="${escH(src)}">مرورگرت ویدیو را پشتیبانی نمی‌کند.</video>`;
  else if(m.k==='audio'&&direct) stage=`<div class="pdoc"><svg class="i" style="width:34px;height:34px"><use href="#i-headphone"/></svg><b>${escH(m.t)}</b>
      <audio controls preload="metadata" ${noDownload?'controlsList="nodownload"':''} style="width:100%;margin-top:12px" src="${escH(src)}">مرورگرت صدا را پشتیبانی نمی‌کند.</audio></div>`;
  else if(m.k==='image'&&direct) stage=`<figure class="pdoc" style="padding:8px"><img src="${escH(src)}" alt="${escH(m.t)}" style="display:block;max-width:100%;max-height:65vh;object-fit:contain;border-radius:12px"/><figcaption class="cap" style="margin-top:8px">${escH(m.t)}</figcaption></figure>`;
  else if(m.k==='pdf'&&direct) stage=`<div class="pdoc" style="padding:8px"><iframe title="${escH(m.t)}" src="${escH(src)}" style="width:100%;height:65vh;border:0;border-radius:12px;background:white"></iframe></div>`;
  else if(m.k==='file'&&direct) stage=`<div class="pdoc"><svg class="i" style="width:34px;height:34px"><use href="#i-doc"/></svg><b>${escH(m.t)}</b>
      <p class="cap">این سند برای دریافت آماده است؛ فایل در صفحه اجرا نمی‌شود.</p></div>`;
  else if(m.k==='link'&&external) stage=`<div class="pdoc"><svg class="i" style="width:34px;height:34px"><use href="#i-link"/></svg><b>${escH(m.t)}</b>
      <p class="cap">این پیوند بیرونی در صفحهٔ اصلی باز می‌شود.</p><a class="btn primary" href="${escH(safeHttpsMediaUrl(originalUrl))}" target="_blank" rel="noopener noreferrer">باز کردن پیوند</a></div>`;
  else if(external) stage=`<div class="pdoc"><svg class="i" style="width:34px;height:34px"><use href="#${kd.i||'i-link'}"/></svg><b>${escH(m.t)}</b>
      <p class="cap">این سرویس در فهرست پخش درون‌صفحه‌ای نیست؛ نشانی ناشناس در قاب جاسازی نمی‌شود.</p>
      <a class="btn primary" href="${escH(safeHttpsMediaUrl(originalUrl))}" target="_blank" rel="noopener noreferrer">باز کردن امن در تب تازه</a></div>`;
  else stage=`<div class="pdoc"><svg class="i" style="width:34px;height:34px"><use href="#${kd.i||'i-archive'}"/></svg><b>${escH(m.t)}</b>
      <p class="cap">${m.heavy?'فایل سنگین بارگذاری شده، اما پیوند پخش عمومی ندارد؛ از مالک رویداد بخواهید نشانی مجاز اضافه کند.':'برای این رسانه هنوز پیوند پخش ثبت نشده است.'}</p></div>`;
  const action=noDownload?'':mediaNeedsBot(m)?'':src&&m.k==='link'?`<a class="btn quiet block" href="${escH(safeHttpsMediaUrl(originalUrl))}" target="_blank" rel="noopener noreferrer"><svg class="i"><use href="#i-link"/></svg> باز کردن پیوند</a>`:'';
  const hasRate=direct&&(m.k==='video'||m.k==='audio');
  const rateTools=hasRate?`<div class="row tight" role="group" aria-label="سرعت پخش" style="flex-wrap:wrap">
    <span class="cap">سرعت پخش</span><span class="sp"></span>
    ${[0.75,1,1.25,1.5,2].map(v=>`<button type="button" class="chip ${v===1?'on':''}" data-uirate="${v}" aria-pressed="${v===1?'true':'false'}">${faN(v).replace('.', '٫')}×</button>`).join('')}
    </div>`:'';
  const duration=mediaDurationLabel(m), chapterList=hasRate&&m.k==='video'&&Array.isArray(m.chapters)?m.chapters.map(c=>{
    const sec=Math.max(0,Math.floor(Number(c.sec!=null?c.sec:(c.seconds!=null?c.seconds:c.time))||0));
    return `<button class="chip" type="button" data-uichapter="${sec}" data-media-id="${escH(m.id)}">${escH(c.t||c.title||playerTimeText(sec))} · ${playerTimeText(sec)}</button>`}).join(''):'';
  const accountTools=noDownload&&hasRate&&m.k==='video'?`<div class="account-player-tools">
      <div class="row tight account-player-seek" role="group" aria-label="جابه‌جایی در ویدیو">
        <button class="btn sm quiet" type="button" data-uiseek-step="-10">۱۰ ثانیه عقب</button>
        <button class="btn sm quiet" type="button" data-uibookmark data-media-id="${escH(m.id)}">${playerIcon('i-pin')} نشان‌گذاری این لحظه</button>
        <button class="btn sm quiet" type="button" data-uiseek-step="10">۱۰ ثانیه جلو</button>
      </div>
      ${chapterList?`<div class="account-player-marks"><b>بخش‌ها</b><div>${chapterList}</div></div>`:''}
      <div class="account-player-marks"><b>نشان‌های ذخیره‌شده در همین دستگاه</b><div data-player-marks="${escH(m.id)}">${playerBookmarkRows(m.id)}</div></div>
    </div>`:'';
  const contextAttr=contextId?` data-uimedia-context="${escH(contextId)}"`:'';
  const jump=(item,icon,label)=>item?`<button class="btn sm quiet" type="button" data-uimedia="${escH(pastId)}:${escH(item.id)}"${contextAttr} aria-label="${label}: ${escH(item.t)}">${playerIcon(icon)} ${label}</button>`:'';
  const searchBox=noDownload?`<label class="account-player-search">${playerIcon('i-search')}<input type="search" data-uimedia-search placeholder="جست‌وجوی این فهرست" aria-label="جست‌وجو در فهرست رسانه‌ها"/></label>`:'';
  const returnButton=opts.returnTo?`<button class="btn sm quiet" type="button" data-uiplayerback="${escH(opts.returnTo)}">${playerIcon('i-chev-right')} بازگشت به رویداد</button>`:
    `<button class="icon-btn" data-close aria-label="بستن"><svg class="i"><use href="#i-close"/></svg></button>`;
  fillSheet('shPlay',`<div class="grabber"></div>
    <div class="row" style="align-items:center;gap:7px;margin-bottom:10px">
      <div style="min-width:0"><div class="head">${escH(kd.n)} · ${escH(H.t)}</div><div class="cap">${escH(m.t)}${m.sourceDemo?' · نمونهٔ پخش، نه ضبط اصلی':''}</div></div>
      <span class="sp"></span>${jump(pv,'i-chev-right','قبلی')}${jump(nx,'i-chev-left','بعدی')}${returnButton}</div>
    <div class="stack tight ${noDownload?'account-video-player':''}"><div class="player-stage">${stage}</div>${action}
      ${accountTools}
      <div class="srow"><svg class="i"><use href="#i-clock"/></svg><span class="sp">${m.k==='video'||m.k==='audio'?'مدت اعلام‌شده':'زمان یا تعداد'}</span><b>${escH(duration)}</b></div>
      <div class="srow"><svg class="i"><use href="#i-archive"/></svg><span class="sp">فرمت و حجم</span><b>${escH(m.mime||kd.n)}${m.size?' · '+faN(Math.ceil(+m.size/1024))+' کیلوبایت':''}</b></div>
      <div class="srow"><svg class="i"><use href="#i-users"/></svg><span class="sp">دسترسی</span><b>${escH(H.access||'آرشیو رویداد')}</b></div>
      ${rateTools}
    </div>
    <div class="sec-hd" style="margin-top:14px"><span class="fw">فهرست رسانه‌های همین رویداد</span><span class="sp"></span><span class="cap">${faN(media.length)} قلم</span></div>
    ${searchBox}${mediaList(listEvent,{forceOpen:forceOpen,noDownload:noDownload,contextId:contextId})}`);
  document.querySelectorAll('.sheet').forEach(s=>{if(s.id!=='shPlay'&&s.id!==String(opts.returnTo||'')) s.classList.remove('on')});
}

/* ── خرید: کیف پول یا درگاه ── */
function uid(){const u=walletUser(); return u?u.mobile||u.name:''}
function walletUser(){
  if(!NORA_TEST_FIXTURE_MODE) return null;
  const u=jread(SESS_KEY,null);
  return (u&&typeof u==='object'&&u.name)?u:null;
}
function saveWalletUser(u){if(NORA_TEST_FIXTURE_MODE) jwrite(SESS_KEY,u)}
function buySheet(pastId,mediaId){
  const N=window.NORA||{}, H=(N.PAST||[]).find(x=>x.id===pastId); if(!H) return;
  const m=mediaId?(H.media||[]).find(x=>x.id===mediaId):null;
  const amount=m?m.p:H.bundle, title=m?m.t:H.t+'، بستهٔ کامل';
  fillSheet('shBuy',`
    <div class="grabber"></div>
    <div class="row" style="align-items:center;margin-bottom:10px">
      <div><div class="head">پیش‌نمایش تهیه</div><div class="cap">${escH(H.t)}</div></div>
      <span class="sp"></span><button class="icon-btn" data-close aria-label="بستن"><svg class="i"><use href="#i-close"/></svg></button></div>
    <div class="stack tight">
      <div class="srow"><svg class="i"><use href="#${m?(((N.MEDIA_KINDS||{})[m.k]||{}).i||'i-play'):'i-archive'}"/></svg><span class="sp">${escH(title)}</span><b>${price(amount)} · نمونه</b></div>
      <div class="srow"><svg class="i"><use href="#i-users"/></svg><span class="sp">${m?'قطعهٔ انتخاب‌شده':'رسانه‌های بسته'}</span><b>دادهٔ نمایشی</b></div>
      <div class="srow"><svg class="i"><use href="#i-shield"/></svg><span class="sp">پرداخت و ضمانت</span><b>وصل نیست</b></div>
    </div>
    <div class="cap" style="margin:12px 0 4px">روش پرداخت در این نسخه فعال نیست</div>
    <div class="stack tight">
      <button class="opt" type="button" disabled aria-disabled="true">
        <span class="mk"></span><span class="sp">کیف پول · نمونهٔ محلی، برداشت واقعی ندارد</span></button>
      <button class="opt" type="button" disabled aria-disabled="true">
        <span class="mk"></span><span class="sp">درگاه بله · به سرور وصل نیست</span></button>
    </div>
    <div class="moneyline" style="margin-top:12px"><span>مبلغ نمایشی</span><span class="num">${price(amount)}</span></div>
    <button class="btn primary block" style="margin-top:10px" disabled aria-disabled="true">
      <svg class="i"><use href="#i-lock"/></svg> خرید واقعی در دسترس نیست</button>
    <p class="cap" style="margin-top:10px">هیچ مبلغی کسر نمی‌شود و محتوای پولی آزاد نمی‌شود؛ اطلاعات کارت وارد نکن.</p>`);
}
function doBuy(pastId,mediaId){
  toast('خرید و پرداخت واقعی به درگاه و سرور وصل نیست؛ هیچ مبلغی کسر یا محتوایی آزاد نشد');
}

/* ── ورود عضو فقط در صفحهٔ مستقل login.html انجام می‌شود؛ ورقهٔ درون‌صفحه‌ای OTP حذف شد ── */
async function serverAuthPost(path,body){
  const r=await fetch(path,{method:'POST',credentials:'same-origin',cache:'no-store',
    headers:{Accept:'application/json','Content-Type':'application/json'},body:JSON.stringify(body)});
  let data=null; try{data=await r.json()}catch(_){}
  if(!r.ok) throw new Error((data&&(data.detail||data.message))||('HTTP '+r.status));
  return data;
}
/* ── «مسیر پیوند حساب» صریح است، نه حدسی ─────────────────────────────
   پارامتر `?link=bale` تنها نشانهٔ این مسیر است و ربات آن را در نشانی دکمهٔ
   مینی‌اپ می‌گذارد. چرا لازم است: امضای `initData` بله یک‌بارمصرف است. اگر
   همین صفحه در مسیر پیوند هم ورود خودکار بزند، امضا خرجِ ساختن یک حساب
   تازه می‌شود و برای اثبات مالکیت در پیوند چیزی نمی‌ماند؛ بدتر آنکه هویت بله
   به همان حساب خودکار می‌چسبد و پیوند به حساب شماره‌ای با ۴۰۹ رد می‌شود.
   پس در این مسیر ورود خودکار انجام نمی‌شود و کاربر اول با شماره وارد می‌شود. */
function baleLinkMode(){
  try{
    return new URLSearchParams(location.search).get('link')==='bale';
  }catch(_){return false}
}
/* ── ورود مینی‌اپ بله ──────────────────────────────────────────────────
   وقتی همین صفحه داخل شیشهٔ بله باز می‌شود، `Bale.WebApp.initData` یک دادهٔ
   امضاشده و یک‌بارمصرف است. دو نکته مهم:
   ۱) پیش از فرستادن امضا، وضعیت نشست پرسیده می‌شود (مالک، بعد حساب)؛ وگرنه
      روی هر جابه‌جاییِ صفحه همان امضا دوباره فرستاده می‌شود و سرور آن را
      ۴۰۹ «تکرار» می‌کند و کاربر بی‌دلیل از ورود باز می‌ماند.
   ۲) هر خطایی بی‌سروصدا رد می‌شود؛ مسیر ورود معمولی (شماره/گذرواژه) دست‌نخورده
      می‌ماند و کاربر پشت خطای فنی نمی‌ماند. */
function baleMiniAppInitData(){
  try{
    const app=window.Bale&&window.Bale.WebApp;
    const raw=app&&typeof app.initData==='string'?app.initData:'';
    /* فقط رشتهٔ کاملی که امضا و زمان دارد؛ هم‌شکل با اعتبارسنجی سرور. */
    return /(?:^|&)hash=/.test(raw)&&/(?:^|&)auth_date=/.test(raw)?raw:'';
  }catch(_){return ''}
}
async function hasServerSession(){
  for(const path of ['/api/auth/me','/api/account/me']){
    try{
      const r=await fetch(path,{method:'GET',credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
      if(r.ok){
        const d=await r.json().catch(()=>null);
        if(d&&d.authenticated===true) return true;
      }
    }catch(_){/* شبکه/سرور نیست؛ مسیر معمولی ورود را نمی‌بندیم */}
  }
  return false;
}
async function baleMiniAppBoot(){
  if(NORA_TEST_FIXTURE_MODE) return false;
  /* مسیر پیوند حساب: امضای یک‌بارمصرف باید برای اثبات مالکیت بماند. */
  if(baleLinkMode()) return false;
  if(window.NORA_ACCOUNT_SOURCE==='server'||sessUser()) return false;
  const initData=baleMiniAppInitData();
  if(!initData) return false;
  if(await hasServerSession()){ if(typeof window.NORA_ACCOUNT_SOURCE!=='undefined') window.NORA_ACCOUNT_SOURCE='server'; return true; }
  try{
    const d=await serverAuthPost('/api/auth/bale-mini-app',{init_data:initData});
    if(!d||d.authenticated!==true) return false;
    if(typeof window.NORA_ACCOUNT_SOURCE!=='undefined') window.NORA_ACCOUNT_SOURCE='server';
    try{syncBell()}catch(_){}
    try{authDone()}catch(_){}
    return true;
  }catch(err){
    /* کد خطای سرور ممکن است این‌ها باشد: invalid_bale_init_data (۴۰۱)،
       bale_init_data_replayed (۴۰۹)، bale_auth_not_configured (۵۰۳). در همه
       حالت‌ها کاربر با ورود معمولی ادامه می‌دهد. خودِ امضا لاگ نمی‌شود. */
    if(typeof console!=='undefined'&&console.warn) console.warn('mini app login skipped:',String(err&&err.message||err).slice(0,80));
    return false;
  }
}
function authSheet(after){
  if(!NORA_TEST_FIXTURE_MODE){
    /* در نسخهٔ تولیدی هیچ ورقهٔ ورود درون‌صفحه‌ای وجود ندارد: ورود امن فقط در login.html
       (کپچای سرور، OTP، نشست سروری) انجام می‌شود و کاربر به صفحهٔ حساب برمی‌گردد. */
    authSheet.after=null;
    location.href='login.html?mode=server&next='+encodeURIComponent(accountEntryHref('account.html'));
    return;
  }
  const pend=jread('nora-home-auth',null)||null;
  const step=pend&&pend.step==='code'?'code':'phone', mob=(pend&&pend.mobile)||'';
  fillSheet('shAuth',`
    <div class="grabber"></div>
    <div class="row" style="align-items:center;margin-bottom:10px">
      <div><div class="head">${step==='code'?'کد تأیید':'ورود با شمارهٔ موبایل'}</div>
        <div class="cap">${step==='code'?'کد ثابت نمایشی ۵۴۳۲۱ برای '+(mob?'۰'+'۹…'+mob.slice(-4):'شمارهٔ نمونه')+'؛ پیامک نمی‌شود':'ورود نمونه برای کتابخانه؛ احراز هویت سروری وصل نیست'}</div></div>
      <span class="sp"></span><button class="icon-btn" data-close aria-label="بستن"><svg class="i"><use href="#i-close"/></svg></button></div>
    ${step==='code'
      ? `<label class="lbl" for="uicode">کد پنج‌رقمی</label>
         <input class="input num" id="uicode" inputmode="numeric" placeholder="•••••" autocomplete="one-time-code"/>
         <div class="cap" style="margin-top:7px">کد ثابت این نمونه: ۵۴۳۲۱؛ پیامک واقعی وصل نیست.</div>
         <div class="row" style="margin-top:12px"><button class="btn primary" data-uicode><svg class="i"><use href="#i-check"/></svg> ورود</button>
           <button class="btn quiet" data-uiback>تغییر شماره</button></div>`
      : `<label class="lbl" for="uimob">شمارهٔ موبایل</label>
         <input class="input num" id="uimob" inputmode="numeric" placeholder="۰۹۱۲۳۴۵۶۷۸۹" value="${escH(mob)}"/>
         <div class="row" style="margin-top:12px"><button class="btn primary" data-uiphone><svg class="i"><use href="#i-send"/></svg> ادامه با کد نمایشی</button>
           <button class="btn quiet" data-close>بعداً</button></div>`}
    <p class="cap" style="margin-top:10px">ورود فقط وضعیت محلی همین مرورگر را عوض می‌کند؛ خرید، همگام‌سازی بین دستگاه‌ها یا حساب سروری فعال نیست.</p>
    <p class="cap" style="margin-top:8px"><a href="login.html?mode=server" style="font-weight:700">ورود امن به حساب نورا</a></p>`);
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
  shareItem({title:(e?(e.t+' · نمونه'):'رویداد نمونهٔ نورا'),text:(e?((e.d||e.when||'')+' · پیش‌نمایش محلی'):'رویداد نمونهٔ گروه فرهنگی خط زندگی'),url:new URL('event.html?id='+encodeURIComponent(id),location.href).href});
}

/* ── جهت‌دهی منو بر پایهٔ صفحه ── */
function menuRoute(el){
  const N=window.NORA||{};
  if(el.dataset.uihref){
    const href=el.dataset.uihref;
    location.href=ACCOUNT_NEXT_RE.test(href)?accountEntryHref(href):href;
    return;
  }
  if(el.dataset.uiev){ eventSheet(el.dataset.uiev); return }
  const H=window.NORA_HOME;                          /* در خانه، خودِ صفحه صاحب ورقه‌هاست */
  const f=el.dataset.uif, j=el.dataset.uijump;
  if(f){
    if(f==='shAccount'){ location.href=accountEntryHref('account.html'); return }    /* حساب و ورود مسیر امن خود را دارند */
    if(f==='shSupport'||f==='shFaq'){ location.href='support.html'; return }  /* راهنما و پشتیبانی، صفحهٔ خودش */
    if(f==='shInvite'){ location.href=accountEntryHref('account.html#invite'); return }
    if(f==='shClub'){ location.href=accountEntryHref('account.html#book'); return }      /* باشگاه کتاب زیر پروفایل من است */
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
  const pd=t.closest('[data-uiperson]'); if(pd){location.href='person.html?id='+encodeURIComponent(pd.dataset.uiperson); return}
  const pin=t.closest('[data-uipin]'); if(pin){const [k,i]=pin.dataset.uipin.split(':');
    toast(sharedPin(k,i)?'سنجاق شد':'از سنجاق درآمد'); return}
  const sh=t.closest('[data-uishare]'); if(sh){sharedShare(sh.dataset.uishare); return}
  const rd=t.closest('[data-uireadall]'); if(rd){
    userNotices().forEach(n=>markRead(n.t)); uiOpen('shNotice'); toast('همه خوانده شد'); return}
  const pr=t.closest('[data-uipre]'); if(pr){prereg(pr.dataset.uipre); return}
  const pv=t.closest('[data-uipreview]'); if(pv){preview(pv.dataset.uipreview); return}
  const md=t.closest('[data-uimedia]'); if(md){const [h,m]=md.dataset.uimedia.split(':');
    const ctx=md.dataset.uimediaContext?PLAYER_CONTEXTS[md.dataset.uimediaContext]:null;
    player(h,m,ctx||undefined); return}
  const bookmark=t.closest('[data-uibookmark]');
  if(bookmark){
    const media=document.querySelector('#shPlay video,#shPlay audio'), id=bookmark.dataset.mediaId||PLAY.id;
    if(!media||!Number.isFinite(media.currentTime)){toast('نشان‌گذاری برای این رسانه در دسترس نیست');return}
    const sec=Math.max(0,Math.floor(media.currentTime)), all=jread(PLAYER_BOOKMARK_KEY,{})||{}, rows=Array.isArray(all[id])?all[id].slice():[];
    if(rows.some(x=>Math.abs((+x.sec||0)-sec)<2)){toast('این لحظه از قبل نشان‌گذاری شده است');return}
    rows.push({sec:sec,at:Date.now()}); all[id]=rows.slice(-100); jwrite(PLAYER_BOOKMARK_KEY,all);
    renderPlayerMarks(id); toast('لحظهٔ '+playerTimeText(sec)+' در همین دستگاه نشان‌گذاری شد'); return}
  const mark=t.closest('[data-uibookmark-go],[data-uichapter]');
  if(mark){
    const media=document.querySelector('#shPlay video,#shPlay audio'), sec=Math.max(0,Number(mark.dataset.uibookmarkGo!=null?mark.dataset.uibookmarkGo:mark.dataset.uichapter)||0);
    if(!media){toast('جابه‌جایی زمانی برای این رسانه در دسترس نیست');return}
    try{media.currentTime=Number.isFinite(media.duration)&&media.duration>0?Math.min(sec,media.duration):sec;media.focus()}catch(err){toast('مرورگر جابه‌جایی زمانی را نپذیرفت')} return}
  const seek=t.closest('[data-uiseek-step]');
  if(seek){
    const media=document.querySelector('#shPlay video,#shPlay audio');
    if(!media){toast('جابه‌جایی زمانی برای این رسانه در دسترس نیست');return}
    const next=(Number(media.currentTime)||0)+(Number(seek.dataset.uiseekStep)||0);
    try{media.currentTime=Number.isFinite(media.duration)&&media.duration>0?Math.max(0,Math.min(media.duration,next)):Math.max(0,next)}
    catch(err){toast('مرورگر جابه‌جایی زمانی را نپذیرفت')} return}
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
  const rt=t.closest('[data-uirate]'); if(rt){const rate=Number(rt.dataset.uirate), media=document.querySelector('#shPlay video,#shPlay audio');
    if(!media||!Number.isFinite(rate)){toast('کنترل سرعت برای این رسانه در دسترس نیست');return}
    try{media.playbackRate=rate}catch(err){toast('مرورگر سرعت دلخواه را نپذیرفت');return}
    PLAY.rate=rate;
    document.querySelectorAll('#shPlay [data-uirate]').forEach(b=>{const on=b===rt;b.classList.toggle('on',on);b.setAttribute('aria-pressed',on?'true':'false')});
    toast('سرعت پخش: '+faN(rate).replace('.', '٫')+' برابر'); return}
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
    jwrite('nora-home-auth',null); syncBell(); authDone(); toast('ورود نمایشی انجام شد؛ حساب فقط در همین مرورگر نگه‌داری می‌شود'); return}
  const bk=t.closest('[data-uiback]'); if(bk){jwrite('nora-home-auth',{step:'phone',mobile:''}); authSheet(); return}
},false);
document.addEventListener('input',e=>{
  const input=e.target&&e.target.closest('[data-uimedia-search]'); if(!input) return;
  const q=String(input.value||'').toLocaleLowerCase().replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/[\u200c\s]+/g,' ').trim();
  document.querySelectorAll('#shPlay [data-player-search]').forEach(row=>{
    const hay=String(row.dataset.playerSearch||'').toLocaleLowerCase().replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/[\u200c\s]+/g,' ').trim();
    row.hidden=!!q&&!hay.includes(q);
  });
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
/* اگر صفحه داخل مینی‌اپ بله باز شده باشد، هویت امضاشده همین‌جا نشست می‌سازد. */
try{baleMiniAppBoot()}catch(e){}
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

/* ── ساعت محلی نمونه: هیچ درخواست شبکه‌ای برای هم‌گام‌سازی زمان انجام نمی‌شود ──
   هر عنصری که data-clock داشته باشد از ساعت دستگاه پر می‌شود؛ این زمان مرجع عملیاتی نیست. */
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
  /* The preview intentionally has no external time service or network sync. */
  CLK.tried=true; CLK.diff=0; CLK.state='local'; CLK.at=clockHM();
  paintClocks(); return CLK.state;
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
function formsSave(list){
  try{
    localStorage.setItem(FORMS_KEY,JSON.stringify(list));
    formsAnnounce();
    return true;
  }catch(e){
    return false;
  }
}
function formById(id){return formsAll().find(f=>String(f.id)===String(id))||null}
function formPut(f){
  const list=formsAll(), i=list.findIndex(x=>String(x.id)===String(f.id));
  const row=Object.assign({}, i>=0?list[i]:{}, f, {at:Date.now()});
  if(i>=0) list[i]=row; else list.unshift(row);
  if(!formsSave(list)) return null;
  return row;
}
function formPatch(id,patch){
  const f=formById(id); if(!f) return null;
  return formPut(Object.assign({},f,patch,{sync:Object.assign({},f.sync||{},(patch||{}).sync||{})}));
}
function formDrop(id){return formsSave(formsAll().filter(f=>String(f.id)!==String(id)))}
function formsFor(evId){return formsAll().filter(f=>f.ev&&String(f.ev)===String(evId))}
/* نظرسنجی آمادهٔ نورا: پیشفرضِ هر رویداد؛ بی آنکه کسی چیزی بسازد،
   بعد از برنامه همین پرسشها از شرکتکننده میآید. فرم اختصاصی هم دست خود سازنده. */
const AUTO_SURVEY={id:'auto', name:'نظرسنجی آمادهٔ نورا', kind:'نظرسنجی',
  questions:['برنامهٔ امروز چطور بود؟','کیفیت محتوا را چند می‌دهی؟','کدام بخش بیشتر به دلت نشست؟','به دوستانت پیشنهادش می‌کنی؟','چه چیزی کم داشت؟'],
  fields:[
    {id:'as1',l:'برنامهٔ امروز چطور بود؟',t:'rating',req:true,help:'۱ کم، ۵ عالی؛ ستاره را بزن',weight:2,scoreOn:true},
    {id:'as2',l:'کیفیت محتوا را چند می‌دهی؟',t:'scale',req:true,help:'۰ تا ۱۰؛ وسط یعنی معمولی',weight:3,scoreOn:true},
    {id:'as3',l:'کدام بخش بیشتر به دلت نشست؟',t:'choice',req:true,weight:1,scoreOn:false,
      opts:[{l:'محتوا',score:0},{l:'مدرس',score:0},{l:'فضا و اجرا',score:0},{l:'هم‌صحبتی',score:0}]},
    {id:'as4',l:'به دوستانت پیشنهادش می‌کنی؟',t:'choice',req:true,help:'این پاسخ در امتیاز وزنی اثر دارد.',weight:2,scoreOn:true,
      opts:[{l:'حتماً',score:5},{l:'شاید',score:3},{l:'نه',score:0}]},
    {id:'as5',l:'چه چیزی کم داشت؟',t:'area',req:false,help:'یک جمله کافی است؛ بی‌نام می‌ماند',weight:1,scoreOn:false}
  ],
  intro:'نظرت بی‌نام ثبت شد؛ ستاره و بازه برای بهتر شدن برنامهٔ بعدی خوانده می‌شود.'};
/* استخر کارت و درگاه: کارت پیش‌فرض نداریم. اگر پنل چیزی منتشر کرده همان را
   می‌خوانیم، وگرنه استخرِ پیش‌فرضِ داده. چرخش یا با سقف تراکنش است یا با روز. */
const FIN_KEY='nora-finance', RC_KEY='nora-receipts';
/* نمایش نقش فقط برای پیش‌نمایش است؛ این بررسی مرورگری جای مجوز سمت سرور را نمی‌گیرد. */
const ADM_SESSION_KEY='nora-admin-session', ADM_SESSION_TTL=8*60*60*1000;
function adminActor(){
  let s=null; try{s=JSON.parse(localStorage.getItem(ADM_SESSION_KEY)||'null')}catch(e){}
  if(!s||s.role!=='admin'||!String(s.u||'').trim()||!String(s.personKey||'').trim()||!+s.at) return null;
  const age=Date.now()-(+s.at), people=(((window.NORA||{}).ADMIN||{}).people)||[];
  if(age<0||age>ADM_SESSION_TTL) return null;
  return people.find(p=>p&&p.k===s.personKey)||null;
}
const financeOwner=()=>{const p=adminActor(); return !!(p&&p.k==='p1'&&p.f==='owner')};
function finPublic(){
  const cleanGates=list=>(Array.isArray(list)?list:[]).filter(g=>g&&['bale','card','custom','wallet'].includes(g.k)).map(g=>{
    const v=Object.assign({},g); ['key','token','secret','apiKey'].forEach(k=>delete v[k]); return v;
  });
  try{
    const v=JSON.parse(localStorage.getItem(FIN_KEY)||'null');
    if(v&&typeof v==='object'&&(Array.isArray(v.cards)||Array.isArray(v.gates))){
      const F=((((window.NORA||{}).ADMIN||{}).settings)||{}).finance||{};
      const clean=Object.assign({},v,{gates:cleanGates(v.gates),cards:Array.isArray(v.cards)?v.cards:(F.cards||[])});
      try{localStorage.setItem(FIN_KEY,JSON.stringify(clean))}catch(e){}
      return clean;
    }
  }catch(e){}
  const F=((((window.NORA||{}).ADMIN||{}).settings)||{}).finance||{};
  return {gates:cleanGates(F.gates),cards:F.cards||[],wallet:F.wallet||{},
    rot:(F.rot&&F.rot.mode)||'cap',rotHours:+((F.rot||{}).hours)||24};
}
const finDayKey=()=>{const c=clockParts(); return c.jy+'/'+String(c.jm).padStart(2,'0')+'/'+String(c.jd).padStart(2,'0')};
function finUsage(c,today){
  return c&&c.usedAt===today?{count:+c.used||0,amount:+c.usedAmount||0}:{count:0,amount:0};
}
function finCardValid(card){
  const d=String(typeof card==='string'?card:((card&&card.no)||'')).replace(/\D/g,'');
  if(d.length!==16) return false;
  let sum=0;
  for(let i=0;i<d.length;i++){
    let n=+d[d.length-1-i];
    if(i%2){n*=2;if(n>9)n-=9}
    sum+=n;
  }
  return sum%10===0;
}
function finCanTake(c,today,amount){
  if(!c||c.on===false||c.active===false||!finCardValid(c)) return false;
  const u=finUsage(c,today), countCap=Math.max(1,+c.cap||1), amountCap=Math.max(0,+c.dailyMax||0), take=Math.max(0,+amount||0);
  return u.count<countCap&&(!amountCap||(take>0?u.amount+take<=amountCap:u.amount<amountCap));
}
function finActive(pub,amount){
  pub=pub||finPublic();
  const cards=pub.cards||[]; if(!cards.length) return null;
  const today=finDayKey(), open=cards.filter(c=>finCanTake(c,today,amount));
  if(!open.length) return null;
  const mode=pub.rot||'cap';
  if(mode==='time'){const h=Math.max(1,+pub.rotHours||24), slot=Math.floor(Date.now()/(h*3600000));
    return open[((slot%open.length)+open.length)%open.length]}
  return open.slice().sort((a,b)=>{
    const ua=finUsage(a,today), ub=finUsage(b,today);
    return ua.count-ub.count||ua.amount-ub.amount;
  })[0];
}
function finGateOn(k){
  const g=(finPublic().gates||[]).find(x=>x.k===k);
  return !!(g&&g.on);
}
/* هیچ تراکنش یا رسیدی در این پیش‌نمایش ثبت نمی‌شود، حتی اگر کلیدهای محلی تغییر کنند. */
function finBump(){return null}
function finAddReceipt(){return false}
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
  min:p.min||postMin(p), lead:p.lead||'', who:p.author||'', tchr:p.tchr||'', cov:(p.cover&&p.cover.up)||'',
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
/* ثبت‌نام‌ها: فرمِ وصلشده به رویداد، همین‌جا می‌نویسد؛ پنل و صفحهٔ رویداد می‌خوانند */
const REGS_KEY='nora-regs';
function regsAll(){try{const a=JSON.parse(localStorage.getItem(REGS_KEY)||'[]'); return Array.isArray(a)?a:[]}catch(e){return []}}
function regsOf(evId){return regsAll().filter(r=>String(r.ev)===String(evId))}
function regsPatch(code,patch){const list=regsAll(); const r=list.find(x=>x.code===code); if(!r) return null;
  Object.assign(r,patch); try{localStorage.setItem(REGS_KEY,JSON.stringify(list.slice(0,500)))}catch(e){}
  try{dispatchEvent(new CustomEvent('nora-regs-changed'))}catch(e){} return r}
function regsDrop(code){const list=regsAll().filter(x=>x.code!==code);
  try{localStorage.setItem(REGS_KEY,JSON.stringify(list.slice(0,500)))}catch(e){}
  try{dispatchEvent(new CustomEvent('nora-regs-changed'))}catch(e){}}
/* خروجی اکسلِ ثبت‌نام‌ها: ستون‌های مالی و پرسش‌های پولی فقط برای مالک */
function regsCsv(list,options){
  const rows=list||regsAll(), opts=Object.assign({money:true},options||{}), showMoney=opts.money!==false,
    labs=[], seen={};
  const moneyLabel=l=>/(بدهی|پرداخت|مالی|حق\s*عضویت|تسویه|مبلغ|قیمت|هزینه|شهریه|فروش|درآمد|تخفیف|کارمزد|قسط|اقساط|موجودی|واریز|ریال|تومان|تعرفه|حقوق|دستمزد|سود|سپرده|سرمایه|درگاه|فاکتور|رسید|روش\s*پرداخت|تراکنش|شماره\s*پیگیری|شبا|کارت\s*به\s*کارت|سهم\s*(?:پرداخت|مالی|درآمد)|شماره\s*(?:ی|ٔ)?\s*(?:کارت|حساب)|حساب\s*بانکی|کارت\s*بانکی|\b(?:price|payment|fee|income|revenue|discount|installment|balance|wallet|iban|salary|wage|amount|cost|tuition|transfer)\b)/i.test(String(l||''));
  rows.forEach(r=>(r.ans||[]).forEach(a=>{if(a&&a.l&&a.col!==false&&(showMoney||!moneyLabel(a.l))&&!seen[a.l]){seen[a.l]=1; labs.push(a.l)}}));
  const head=['نام','موبایل','کد'].concat(showMoney?['مبلغ ریال','روش']:[]).concat(['تاریخ','حاضر'],labs);
  const q=s=>'"'+String(s==null?'':s).replace(/"/g,'""')+'"';
  const pick=(r,re)=>{const a=(r.ans||[]).find(x=>x.col!==false&&re.test(x.l)); return a?String(a.v||''):''};
  const line=r=>[pick(r,/^نام/),pick(r,/موبایل|تلفن/),r.code||'']
    .concat(showMoney?[+r.sum||0,r.method||'']:[]).concat([r.atFa||'',r.att?'بله':'خیر'])
    .concat(labs.map(l=>{const a=(r.ans||[]).find(x=>x.l===l&&x.col!==false); return a?String(a.v||''):''}));
  return '\ufeff'+[head].concat(rows.map(line)).map(r=>r.map(q).join(',')).join('\n')}
/* ── پروندهٔ اشخاص (سی‌آر‌ام): هر پاسخِ فرم، یک پرونده را میسازد یا کامل میکند ──
   انبار واحد `nora-people`؛ کلیدِ یکتا موبایل است و بی موبایل، نام+فرم.
   هر بار پر شدنِ هر فرمی، همان پرونده را کامل‌تر میکند؛ پس رویداد و نظرسنجی و
   آزمون همه یک آدمِ واحد میبینند، نه سه غریبه. */
const PEOPLE_KEY='nora-people';
function peopleAll(){try{const a=JSON.parse(localStorage.getItem(PEOPLE_KEY)||'[]'); return Array.isArray(a)?a:[]}catch(e){return []}}
function peopleSave(list){try{localStorage.setItem(PEOPLE_KEY,JSON.stringify(list.slice(0,800)))}catch(e){}
  try{dispatchEvent(new CustomEvent('nora-people-changed'))}catch(e){}}
function personById(id){return peopleAll().find(p=>p.id===id)||null}
const normMob=s=>String(s||'').replace(/[^\d]/g,'');
function personKey(reg,form){
  const ans=(reg&&reg.ans)||[];
  const flds=(form&&form.fields)||[];
  const pick=t=>{const f=flds.find(x=>x.t===t); if(f){const a=ans.find(x=>x.l===f.l); if(a&&a.v) return a.v}
    const g=ans.find(x=>/موبایل|تلفن|شماره/.test(x.l)&&t==='mobile')||ans.find(x=>/ایمیل|رایانامه/.test(x.l)&&t==='email')
      ||ans.find(x=>/نام/.test(x.l)&&!/خانوادگی/.test(x.l)&&t==='first'); return g?g.v:''};
  const g2=ans.find(x=>/موبایل|تلفن/.test(x.l));
  const mob=normMob(pick('mobile')||(g2?g2.v:''));
  const name=ans.find(x=>/نام/.test(x.l))||{};
  return mob?('m:'+mob):('n:'+String(name.v||reg.code||'?').trim());
}
/* یک ثبت/پاسخ را به پروندهٔ شخص وصل میکند؛ پرونده نبود میسازد، بود کامل میکند */
function personFromReg(reg,form){
  const list=peopleAll(); const key=personKey(reg,form);
  let p=list.find(x=>x.key===key);
  const now=new Date(); const atFa=(typeof clockFull==='function')?clockFull():'';
  if(!p){p={id:'p'+String(reg.at||Date.now())+String(Math.floor(Math.random()*900+100)),key:key,
    name:'',mobile:'',email:'',city:'',at:reg.at||Date.now(),atFa:atFa,extra:{},subs:[]}; list.unshift(p)}
  const ans=(reg.ans||[]);
  const take=re=>{const a=ans.find(x=>re.test(x.l)); return a?String(a.v||'').trim():''};
  const nm=take(/^نام/); if(nm) p.name=nm;
  const mob=normMob(take(/موبایل|تلفن/)); if(mob){p.mobile=mob; if(key.indexOf('n:')===0&&!p.key2) p.key2='m:'+mob;}
  const em=take(/ایمیل|رایانامه/); if(em) p.email=em;
  const ct=take(/شهر|محل سکونت/); if(ct) p.city=ct;
  ans.forEach(a=>{if(a&&a.l&&a.v!=null&&a.v!=='') p.extra[a.l]=String(a.v)});
  const sub={ev:reg.ev||'',form:reg.form||'',need:(form&&form.need)||'reg',code:reg.code||'',
    at:reg.at||Date.now(),atFa:reg.atFa||atFa,sum:+reg.sum||0,method:reg.method||'',count:+reg.count||1};
  const oldSub=p.subs.findIndex(x=>x&&x.code&&x.code===sub.code);
  if(oldSub>=0)p.subs[oldSub]=sub;else p.subs.unshift(sub);
  p.subs=p.subs.slice(0,50); p.atLast=reg.at||Date.now();
  peopleSave(list); return p.id;
}
/* چند پرسشِ کلیدیِ پرونده پر است؟ برای پویشِ تکمیل پرونده */
function personPct(p){const keys=[['name','نام'],['mobile','موبایل'],['email','ایمیل'],['city','شهر']];
  const got=keys.filter(k=>String(p[k[0]]||'').trim()).length; return Math.round(got*100/keys.length)}
/* اطلاع‌رسانی و پویش رویدادها: دفتر واحد فرستاده‌ها */
const BR_KEY='nora-broadcasts';
function brAll(){try{const a=JSON.parse(localStorage.getItem(BR_KEY)||'[]'); return Array.isArray(a)?a:[]}catch(e){return []}}
function brOf(evId){return brAll().filter(b=>String(b.ev)===String(evId))}
function brSave(row,approvalId){
  if(!row||!row.id||!approvalId) return null;
  const approval=ownerApprovals().find(x=>x&&String(x.id)===String(approvalId)
    &&x.type==='notification'&&x.status==='approved'&&x.notificationStatus==='approved'
    &&!!x.approvedById&&!!x.approvedAt&&x.brRecord&&String(x.brRecord.id)===String(row.id));
  if(!approval||approval.testOnly) return null;
  const existing=brAll().find(x=>x&&String(x.ownerApprovalId)===String(approval.id));
  if(existing) return existing;
  const record=Object.assign({},approval.brRecord,{ownerApprovalId:approval.id,
    ownerApprovedBy:approval.approvedBy||'',ownerApprovedById:approval.approvedById,
    ownerApprovedAt:approval.approvedAt,localOnly:true,sent:false});
  const list=brAll(); list.unshift(record);
  try{localStorage.setItem(BR_KEY,JSON.stringify(list.slice(0,300)))}catch(e){return null}
  try{dispatchEvent(new CustomEvent('nora-broadcast-changed'))}catch(e){} return record;
}
const formsMoney=f=>{const fin=(f&&f.fin)||[]; if(!fin.length) return 0;
  return fin.reduce((n,o)=>n+(o.off?Math.round(+o.p*(100-+o.off)/100):(+o.p||0)),0)};
const JM_KEY=['','','','','','','sh','mehr','aban','','','',''];
const JM_NAME=['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
function pubEvents(){
  let added=null, edits={};
  try{const a=JSON.parse(localStorage.getItem('nora-admin')||'null');
    if(a&&Array.isArray(a.added)) added=a.added;
    if(a&&a.evEdit&&typeof a.evEdit==='object'&&!Array.isArray(a.evEdit)) edits=a.evEdit;
  }catch(e){}
  if(!added||!added.length) return [];
  const c=clockParts(), today=j2d(c.jy,c.jm,c.jd), nowMin=c.h*60+c.mi;
  const dOf=s=>{const p=parseJ(s); return p?j2d(p.jy,p.jm,p.jd):null};
  const tOf=s=>{const p=parseJ('1400/01/01، '+String(s||'')); return p?(p.hh*60+p.mm):null};
  let packs={}; try{const x=JSON.parse(localStorage.getItem('nora-evpack')||'{}'); if(x&&typeof x==='object') packs=x}catch(e){}
  return added.map(record=>{
    const ev=Object.assign({},record||{},record&&edits[String(record.id)]||{});
    if(!ev||!ev.id||ev.hidden===true||ev.status==='draft'||ev.pub===false
      ||(ev.privacy&&ev.privacy!=='public')) return null;
    const pack=packs[String(ev.id)]||{};
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
    const regF=lf.find(x=>(x.need||'reg')==='reg'&&x.status!=='draft'&&x.serverDraft!==true&&x.eventVisible!==false);
    const liveMoney=regF?formsMoney(regF):null;
    /* شمار ثبت‌نام فقط پاسخِ فرمِ ثبت‌نام است؛ نظرسنجی و آزمون جا نمیشوند ولی
       ثبت‌نام حساب نمیشوند، پس ظرفیت با پاسخِ نظرسنجی پر نمیشود */
    const regN=regsOf(String(ev.id)).filter(r=>{const f=r.form&&formById?formById(r.form):null;
      if(f&&(f.need||'reg')!=='reg') return false;
      if(r.state==='rejected'||r.state==='cancelled') return false;
      if(r.state==='pending'&&Date.now()-(+r.at||0)>30*60*1000) return false;
      return true}).length;
    const eventMedia=(pack.files||[]).map((f,i)=>{
      const ext=String(f.n||'').split('.').pop().toLowerCase(), mime=String(f.mime||'').toLowerCase(), raw=String(f.kind||'').toLowerCase(), label=String(f.k||'').toLowerCase();
      let mediaKind=raw;
      if(raw==='file'||!['video','audio','image','pdf','slide','link'].includes(mediaKind)){
        if(mime.startsWith('image/')||label==='عکس') mediaKind='image';
        else if(mime.startsWith('video/')||label==='ویدیو') mediaKind='video';
        else if(mime.startsWith('audio/')||label==='صدا') mediaKind='audio';
        else if(mime==='application/pdf'||ext==='pdf'||label==='pdf') mediaKind='pdf';
        else if(label==='اسلاید'||['ppt','pptx','key'].includes(ext)||/powerpoint/.test(mime)) mediaKind='slide';
        else if(label==='پیوند') mediaKind='link';
        else mediaKind='file';
      }
      return {id:f.id||('ep'+i),k:mediaKind,t:f.n||'رسانهٔ رویداد',d:f.at||'آرشیو رویداد',
        s:f.size?Math.max(1,Math.round(+f.size/1024))+' کیلوبایت':'',size:+f.size||0,mime:mime,
        p:0,preview:true,src:f.src||'',url:f.url||'',external:!!f.external,heavy:!!f.heavy};
    });
    const base={id:String(ev.id), t:ev.n||'برنامه', kind:ev.kind||'برنامه',
      when:ev.when||(fj?faJDate(fj.jy,fj.jm,fj.jd):''), time:ev.time||'',
      place:online?'آنلاین':place, mode:online?'آنلاین':'حضوری',
      price:(liveMoney!=null&&liveMoney>0)?liveMoney:(+ev.price||0), cap:+ev.cap||0,
      taken:(regN>+ev.reg)?regN:(+ev.reg||0), regs:regN, regForm:regF?String(regF.id):'', regName:regF?(regF.name||''):'',
      spots:Math.max(0,(+ev.cap||0)-(+ev.reg||0)),
      poster:ev.posterUp||(ev.poster?('posters/'+ev.poster):''), g:PUB_GRAD,
      d:pack.detail||ev.about||ev.rep||'', tags:Array.isArray(ev.tags)?ev.tags:[], club:false,
      code:ev.code||'', privacy:ev.privacy||'public',
      parts:ses.map(x=>({date:x.d||'',time:x.t||'',to:x.to||''})),
      sess:nSes, dm:JM_KEY[jm]||'mehr', dn:dn, mname:JM_NAME[jm-1]||'',
      ord:0, live:live, pub:true, pubPast:past, forms:ev.forms||[],
      tchr:ev.tchr||'', partnerId:String(ev.partnerId||''), partnerName:String(ev.partnerName||''), icon:'i-calendar', day:'', pre:false, pin:false, cert:ev.held?false:undefined};
    if(past){
      base.past=true; base.mediaCount=eventMedia.length; base.media=eventMedia; base.who=+ev.who||0;
      base.album=ev.media||'';
      base.rec=nSes>1?(faN(nSes)+' جلسه برگزار شد'):'برگزاری پایان یافت';
      base.d=pack.detail||ev.rep||base.d; base.sold=+ev.who||0; base.price=0; base.access='آرشیو رویداد';
      base.cert=pack.certOn===0?false:!!pack.certOn;
      base.certMin=+pack.certMin||0; base.certNote=pack.certNote||'';
    } else if(pack.certOn===0){base.cert=false}
    return base;
  }).filter(Boolean);
}

window.NORA_UI=Object.assign(window.NORA_UI||{}, {shareItem:shareItem,copyText:copyText,toast:toast,sheetA11y:sheetA11y,
  rialTxt:rialTxt,parseLocalizedNumber:parseLocalizedNumber,jalaliDaysInMonth:daysOf,isJalaliLeapYear:leap,toPersianDigits:faDigits,
  universityValue:universityValue,setUniversityValue:setUniversityValue,loadUniversities:loadUniversities,
  uiOpen:uiOpen,eventSheet:eventSheet,mediaList:mediaList,bundleCard:bundleCard,player:player,buySheet:buySheet,doBuy:doBuy,
  videoEmbedInfo:videoEmbedInfo,safeHttpsMediaUrl:safeHttpsMediaUrl,baleStartHref:baleStartHref,
  authSheet:authSheet,uid:uid,prereg:prereg,isPre:isPre,preview:preview,library:library,addLib:addLib,hasLib:hasLib,progressOf:progressOf,setProgress:setProgress,
  /* ورود خودکار مینی‌اپ و گامِ پیوند حساب هر دو باید یک قاعده برای شکل
     `initData` داشته باشند؛ این تابع تنها مرجع آن قاعده است. */
  baleMiniAppInitData:baleMiniAppInitData,hasServerSession:hasServerSession,baleLinkMode:baleLinkMode,
  unreadCount:unreadCount,markRead:markRead,syncBell:syncBell,menuSheet:menuSheet,noticesSheet:noticesSheet,LIB_KEY:LIB_KEY,
  profile:profile,saveProfile:saveProfile,profilePercent:profilePercent,profileMissing:profileMissing,
  syncServerProfile:syncServerProfile,
  fillTrust:fillTrust,trustPick:trustPick,
  uiSet:uiSet,uiSetSave:uiSetSave,UISET_META:UISET_META,menuAllowed:menuAllowed,uiSetDef:UISET_DEF,
  levelOf:levelOf,sessUser:sessUser,phoneOf:phoneOf,PROF_KEY:PROF_KEY,
  accountEntryHref:accountEntryHref,updateAccountNavigation:updateAccountNavigation,normalizePrimaryNavigation:normalizePrimaryNavigation,
  clockNow:clockNow,clockParts:clockParts,clockHM:clockHM,clockFull:clockFull,clockDay:clockDay,
  clockState:()=>CLK.state,clockAt:()=>CLK.at,netSyncClock:netSyncClock,
  FORMS_KEY:FORMS_KEY,formsAll:formsAll,formById:formById,formPut:formPut,formPatch:formPatch,
  formDrop:formDrop,formsFor:formsFor,pubEvents:pubEvents,autoSurvey:AUTO_SURVEY,
  finPublic:finPublic,finActive:finActive,finCardValid:finCardValid,finGateOn:finGateOn,finBump:finBump,finAddReceipt:finAddReceipt,
  adminActor:adminActor,financeOwner:financeOwner,
  certificateSVG:certificateSVG,certificateFile:certificateFile,certificateExport:certificateExport,
  ticketSVG:ticketSVG,ticketFile:ticketFile,ticketExport:ticketExport,exportSVG:exportSVG,shortCode:shortCode,
  OWNER_APPROVAL_KEY:OWNER_APPROVAL_KEY,ownerApprovals:ownerApprovals,ownerApprovalAdd:ownerApprovalAdd,
  ownerApprovalPatch:ownerApprovalPatch,ISSUED_CERTS_KEY:ISSUED_CERTS_KEY,issuedCertificates:issuedCertificates,
  addIssuedCertificate:addIssuedCertificate,
  REGS_KEY:REGS_KEY,regsAll:regsAll,regsOf:regsOf,regsPatch:regsPatch,regsDrop:regsDrop,regsCsv:regsCsv,
  PEOPLE_KEY:PEOPLE_KEY,peopleAll:peopleAll,peopleSave:peopleSave,personById:personById,
  personFromReg:personFromReg,personPct:personPct,
  BR_KEY:BR_KEY,brAll:brAll,brOf:brOf,brSave:brSave,
  POSTS_KEY:POSTS_KEY,postsAll:postsAll,postsPub:postsPub,postById:postById,postPut:postPut,
  postPatch:postPatch,postDrop:postDrop,postsFeed:postsFeed,postMin:postMin,postDate:postDate,postView:postView,postReads:postReads,
  performanceSettings:performanceSettings,savePerformanceSettings:savePerformanceSettings,performanceSnapshot:performanceSnapshot,
  checkApiHealth:checkApiHealth,imageOptimizationStats:imageOptimizationStats,imageToWebP:imageToWebP,
  imageToWebPDataURL:imageToWebPDataURL,imageErrorMessage:imageErrorMessage,showPageLoader:showPageLoader,hidePageLoader:hidePageLoader,initPageLoader:initPageLoader});
Object.defineProperty(window.NORA_UI,'universitiesByProvince',{configurable:true,enumerable:true,get:universitiesByProvince});
normalizePrimaryNavigation();
document.addEventListener('nora:login',updateAccountNavigation);
document.addEventListener('nora:logout',updateAccountNavigation);
addEventListener('storage',event=>{if(event.key===SESS_KEY) updateAccountNavigation()});
observePageVitals();
initPageLoader();

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
      if(window.caches&&caches.keys) caches.keys().then(ks=>ks.forEach(k=>{ if(k!=='nora-v95') caches.delete(k) })).catch(()=>{});
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
