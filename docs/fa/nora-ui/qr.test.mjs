/* ══════════════════════════════════════════════════════════════════════════
   آزمون کیوآر گواهینامه: کد را از دل تصویری که صفحه ساخته می‌خواند
   ──────────────────────────────────────────────────────────────────────────
   اجرا (از پوشهٔ همین فایل):
     npm i jsdom jsqr          # یک بار
     node qr.test.mjs
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

/* ── ۱) برگ گواهینامه در فرم: کیوآر باید واقعاً خوانده شود ── */
const dom=await open('./form.html','?guests=1');
const {window}=dom, d=window.document;
const click=s=>d.querySelector(s)?.dispatchEvent(new window.MouseEvent('click',{bubbles:true}));

for(let i=0;i<7;i++) click('#next');
d.querySelector('#fName').value='مریم احمدی'; d.querySelector('#fMobile').value='۰۹۱۲۳۴۵۶۷۸۹';
click('#addFriend'); click('#next'); click('#next');
click('[data-method="bale"]');
for(let i=0;i<3;i++) click('#next');        /* پرداخت → رسید → ثبт شد */
ok(!!d.querySelector('.screen.on'),'فرم تا انتها رفت: '+(d.querySelector('.screen.on')||{}).id);

window.eval("show('u16')");
const csvg=d.querySelector('#certSlot .tk-img svg')||d.querySelector('#certSlot svg');
ok(csvg!==null,'برگ گواهینامه ساخته شد');
const text=decodeSVG(csvg);
ok(text&&text.startsWith('https://lifeline1.ir/c/'),'کیوآر برگ گواهینامه خوانده شد: '+text);
ok(d.querySelector('#certSlot .tk-img svg text')!==null||d.querySelector('#certSlot svg text')!==null,'متن روی برگ هست (فونت درست نشسته)');
ok(d.querySelectorAll('#certSlot .tkqr').length===1,'فقط یک کیوآر روی برگ');
ok(d.querySelector('#u13')===null && d.querySelector('#tickets')===null,'صفحهٔ بلیت‌ها کلاً برداشته شد');
ok(d.querySelector('#receiptSlot')===null,'جای رسید تصویری هم نیست');
console.log('   کیوآر:',text);

/* ── ۲) پیش‌نمایش گواهینامه در پنل سازنده: همان موتور، همان کد ── */
const bd=await open('./builder.html');
const w2=bd.window, d2=w2.document;
w2.eval("openForm('f1'); go('fChanges')");
d2.querySelector('[data-change="cert"]')?.dispatchEvent(new w2.MouseEvent('click',{bubbles:true}));
const psvg=d2.querySelector('#chCertPrev svg');
ok(psvg!==null,'پیش‌نمایش گواهینامه در پنل ساخته شد');
const ptxt=decodeSVG(psvg);
ok(ptxt&&ptxt.startsWith('https://lifeline1.ir/c/'),'کیوآر پیش‌نمایش پنل هم خوانده شد: '+ptxt);
ok(d2.querySelector('#chTkPrev')===null,'پیش‌نمایش بلیت در پنل نیست');

console.log('\nqr: '+checks+' بررسی، '+fails+' خطا');
process.exit(fails?1:0);
