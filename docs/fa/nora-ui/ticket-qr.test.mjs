/* ══════════════════════════════════════════════════════════════════════════
   آزمون بلیت تصویری: کیوآر را از دل تصویری که صفحه ساخته می‌خواند
   ──────────────────────────────────────────────────────────────────────────
   اجرا (از پوشهٔ همین فایل):
     npm i jsdom jsqr          # یک بار
     node ticket-qr.test.mjs
   ══════════════════════════════════════════════════════════════════════════ */
import {JSDOM} from 'jsdom';
import jsQR from 'jsqr';

/* ماتریس مدول‌های کیوآر را از خود SVG بیرون می‌کشد و با jsQR دیکود می‌کند */
export function decodeSVG(svg){
  const g=svg.querySelector('.tkqr');
  if(!g) return null;
  const rects=[...g.querySelectorAll('rect')];
  if(!rects.length) return null;
  const u=Number(rects[0].getAttribute('width'));
  const xs=rects.map(r=>Number(r.getAttribute('x'))/u), ys=rects.map(r=>Number(r.getAttribute('y'))/u);
  const x0=Math.round(Math.min(...xs)), y0=Math.round(Math.min(...ys));
  const n=Math.round(Math.max(...xs))-x0+1;
  const m=Array.from({length:n},()=>Array(n).fill(false));
  for(const r of rects){
    const c=Math.round(Number(r.getAttribute('x'))/u)-x0;
    const row=Math.round(Number(r.getAttribute('y'))/u)-y0;
    if(row>=0&&row<n&&c>=0&&c<n) m[row][c]=true;
  }
  const scale=5, quiet=4, side=(n+quiet*2)*scale;
  const data=new Uint8ClampedArray(side*side*4).fill(255);
  for(let r=0;r<n;r++) for(let c=0;c<n;c++){
    if(!m[r][c]) continue;
    for(let y=0;y<scale;y++) for(let x=0;x<scale;x++){
      const py=(r+quiet)*scale+y, px=(c+quiet)*scale+x, i=(py*side+px)*4;
      data[i]=data[i+1]=data[i+2]=0;
    }
  }
  const res=jsQR(data,side,side);
  return res?res.data:null;
}

async function open(file,q){
  const base=new URL(file,import.meta.url).pathname;
  const dom=await JSDOM.fromFile(base,{
    runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,
    ...(q?{url:'file://'+base+q}:{}),
    beforeParse(w){
      w.scrollTo=()=>{};
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      const m=new Map();
      Object.defineProperty(w,'localStorage',{configurable:true,value:{
        getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k)}});
    }});
  await new Promise(r=>setTimeout(r,900));
  return dom;
}

let checks=0, fails=0;
const ok=(c,t)=>{checks++; if(!c){fails++; console.log('   ✗',t);}};

const dom=await open('./form.html','?guests=1');
const {window}=dom, d=window.document;
const click=s=>d.querySelector(s)?.dispatchEvent(new window.MouseEvent('click',{bubbles:true}));
const set=(s,v)=>{d.querySelector(s).value=v};

/* تا آخر فرم برو تا بلیت نفر اصلی، بلیت دوست و رسید ساخته شوند */
for(let i=0;i<7;i++) click('#next');          /* …تا کارت «دوستاتم با خودت بیار» */
set('#fName','مریم احمدی'); set('#fMobile','۰۹۱۲۳۴۵۶۷۸۹');
click('#addFriend');
click('#next'); click('#next');               /* مالی → پرداخت */
click('[data-method="bale"]'); click('#next'); click('#next');

const svgs=[...d.querySelectorAll('#tickets .tk-img svg'), ...d.querySelectorAll('#receiptSlot .tk-img svg')];
const texts=[];
for(const svg of svgs){
  const txt=decodeSVG(svg);
  texts.push(txt);
  ok(txt&&txt.startsWith('https://lifeline1.ir/'),
     'کیوآر تصویر خوانده نشد: '+(svg.getAttribute('aria-label')||'').slice(0,34));
}
ok(svgs.length===3,'سه تصویر ساخته شد (دو بلیت و یک رسید)');
ok(new Set(texts).size===3,'هر سه کیوآر یکتا هستند');
ok(/\/t\//.test(texts[0]||'')&&/\/r\//.test(texts[2]||''),'بلیت و رسید نشانی جدا دارند');
ok(d.querySelector('#tickets .tk-img svg text')!==null,'متن روی تصویر هست (فونت درست نشسته)');

/* پوستهٔ خاموش/روشن هم روی همان صفحه */
window.eval('CFG.ticketOn=false; renderTickets();');
ok(d.querySelectorAll('#tickets .tk-img svg').length===0,'با خاموش بودن بلیت، تصویری ساخته نمی‌شود');
window.eval('CFG.ticketOn=true; renderTickets();');
ok(d.querySelectorAll('#tickets .tk-img svg').length===2,'با روشن کردن دوباره، هر دو بلیت برمی‌گردند');

for(const t of texts) console.log('   کیوآر:',t);
console.log('\nticket-qr: '+checks+' بررسی، '+fails+' خطا');
process.exit(fails?1:0);
