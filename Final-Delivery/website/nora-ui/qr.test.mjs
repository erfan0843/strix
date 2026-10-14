/* ══════════════════════════════════════════════════════════════════════════
   آزمون QR نمونه: محتوای کد از خودِ تصویرِ محلی خوانده می‌شود
   ──────────────────────────────────────────────────────────────────────────
   اجرا (از پوشهٔ همین فایل):
     npm i jsdom jsqr          # یک بار
     node qr.test.mjs
   ══════════════════════════════════════════════════════════════════════════ */
import {JSDOM} from 'jsdom';
import {fileURLToPath,pathToFileURL} from 'node:url';
import jsQR from 'jsqr';

/* ماتریس مدول‌های کیوآر را از خود SVG بیرون می‌کشد و با jsQR دیکود می‌کند */
export function decodeSVG(svg){
  if(!svg) return null;
  const g=svg.querySelector('.tkqr')||svg.querySelector('.qr g');
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

async function open(file,q,initial={},globals={}){
  const base=fileURLToPath(new URL(file,import.meta.url));
  const dom=await JSDOM.fromFile(base,{
    runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,
    ...(q?{url:pathToFileURL(base).href+q}:{}),
    beforeParse(w){
      w.__NORA_TEST_FIXTURE_MODE__=true;
      w.scrollTo=()=>{};
      if(!w.matchMedia) w.matchMedia=()=>({matches:false,addListener(){},removeListener(){}});
      Object.entries(globals).forEach(([key,value])=>{w[key]=value});
      const m=new Map(Object.entries(initial));
      Object.defineProperty(w,'localStorage',{configurable:true,value:{
        getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k)}});
    }});
  await new Promise(r=>setTimeout(r,900));
  return dom;
}

let checks=0, fails=0;
const ok=(c,t)=>{checks++; if(!c){fails++; console.log('   ✗',t);}};

/* ── ۱) فرم محلی نمونه فقط برای fixture آزمون است؛ داده یا پرداخت واقعی نساز ── */
const dom=await open('./form.html','?guests=1');
const {window}=dom, d=window.document;
const network=[];window.fetch=(...args)=>{network.push(args);return Promise.reject(new Error('offline QR test'))};
const click=s=>d.querySelector(s)?.dispatchEvent(new window.MouseEvent('click',{bubbles:true,cancelable:true}));
for(let i=0;i<7;i++) click('#next');
ok(d.querySelector('.screen.on')?.id==='u8','فرم نمونه تا مرحلهٔ انتخاب محلی پیش می‌رود');
ok(d.querySelectorAll('#u8 [data-method]:not([hidden])').length===0
  &&window.eval("selectedPaymentMethod===''"),'روش پرداختی بدون انتخاب صریح سازنده به کاربر نشان داده یا انتخاب نمی‌شود');
ok(d.querySelector('#serverTrackingRow').hidden&&d.querySelector('#serverReceiptUpload').hidden,
  'شمارهٔ بلیت و بارگذاری رسید تا پاسخ سروری پنهان می‌مانند');
click('#next');
ok(d.querySelector('.screen.on')?.id==='u8'&&!window.eval('S.submitted')&&network.length===0
  &&!window.localStorage.getItem('nora-regs')&&!window.localStorage.getItem('nora-receipts'),
  'فرم نمونه بدون روش منتخب ثبت نمی‌شود و پرداخت، پاسخ یا رسید واقعی نمی‌سازد');
ok(d.querySelector('#u13')===null&&d.querySelector('#tickets')===null
  &&d.querySelector('#serverTicketPreview').hidden&&d.querySelector('#serverTicketLink').hidden
  &&!d.querySelector('#serverTicketImage').getAttribute('src'),
  'پیش‌نمایش محلی بلیت یا صفحهٔ صدور جعلی ندارد');

const serverDom=await open('./form.html','',{}, {__REG:{formId:'sample-form',model:'registration',need:'reg',display:'all',after:'edit',q:[{id:'name',l:'نام و نام خانوادگی',t:'text'}]}});
const sw=serverDom.window,sd=sw.document;
sw.eval(`FORM_ROUTE.serverBacked=true;FORM_ROUTE.model='registration';S.submitted=true;S.serverResponse={status:'accepted',trackingCode:'NORA-123E4567E89B12D3A456',ticketDeliveryUrl:'https://ble.ir/nora?start=ft_${'A'.repeat(48)}',ticketMessage:''};renderEnd();show('u12')`);
ok(!sd.querySelector('#serverTicketPreview').hidden&&!sd.querySelector('#serverTicketLink').hidden,
  'پس از ثبت نهایی، پیش‌نمایش به لینک امن دریافت بلیت در بله وصل است');
ok(sd.querySelector('#endStatusTitle')?.textContent==='تکمیل شد!','پایان فرم عنوان کوتاه و هماهنگ دارد');
ok(!sd.querySelector('#serverTrackingRow').hidden&&sd.querySelector('#serverTrackingCode')?.textContent==='NORA-123E4567E89B12D3A456',
  'کد پیگیری سروری در صفحهٔ پایان نمایش داده می‌شود');
ok(sd.querySelector('#endStatusCaption')?.textContent.includes('پیوند دریافت بلیت در بله آماده است')
  &&sd.querySelector('#serverTicketLink')?.textContent.includes('دانلود بلیت در بله'),
  'صفحهٔ پایان، پیوند دریافت بلیت در بله را روشن و یک‌دست نشان می‌دهد');
ok(sd.querySelector('#regSumCard').hidden&&sd.querySelector('#endSampleMessageCard').hidden&&sd.querySelector('#endLinksCard').hidden,
  'پایان سروری از کارت‌های اضافه و شلوغ‌کننده خالی است');
ok(sd.querySelector('[data-after-mode="edit"]')?.hidden
  &&sd.querySelector('[data-after-mode="cancel"]')?.hidden&&sd.querySelector('#endLocalNotice').hidden,
  'پس از ثبت سروری، کنترل‌های پیش‌نمایش و پایان محلی پنهان‌اند');
sw.eval(`show('u8')`);
ok(sd.querySelector('.screen.on')?.id==='u12','بعد از ثبت، برگشت به صفحهٔ پرسش‌ها مسدود است');
sw.eval(`S.serverResponse.status='waitlisted';renderEnd()`);
ok(sd.querySelector('#serverTicketPreview').hidden,'فهرست انتظار کارت دریافت بلیت ندارد');
ok(sd.querySelector('#serverTrackingRow').hidden&&!sd.querySelector('#serverTicketLink').getAttribute('href'),
  'فهرست انتظار شماره یا پیوند بلیت نمی‌گیرد');

/* ── QR فرم‌ساز: فقط متن نمونه، بدون مسیر وب یا فرم عمومی ── */
const cd=await open('./create.html');
const cw=cd.window, cdoc=cw.document;
cw.eval('renderReview()');
const formQr=cdoc.querySelector('#revQR svg');
ok(formQr!==null,'فرم‌ساز QR متنی می‌سازد');
const formText=decodeSVG(formQr);
ok(formText&&formText.startsWith('SAMPLE-FORM:'),'QR فرم‌ساز فقط متن برچسب نمونه دارد: '+formText);
ok(!/^https?:\/\//i.test(formText||''),'QR فرم‌ساز URL عمومی نیست');
ok(cdoc.querySelector('#revQRNote').textContent.includes('نشانی وب')&&cdoc.querySelector('#revQRNote').textContent.includes('ندارد'),
  'متن همراه QR هم نبود مقصد عمومی را روشن می‌کند');

/* موتور تصویر (ui.js) یک SVG نمونه می‌سازد؛ هرگز سند رسمی نیست. */
const svg=window.eval("certificateSVG({name:'مریم احمدی',title:'کارگاه نمونه',kind:'طرح نمونهٔ غیررسمی',date:'۲۸ شهریور ۱۴۰۵',hours:'۲۴ ساعت',code:'SAMPLE-0217'})")
  && new window.DOMParser().parseFromString(window.eval("certificateSVG({name:'مریم احمدی',title:'کارگاه نمونه',kind:'طرح نمونهٔ غیررسمی',date:'۲۸ شهریور ۱۴۰۵',hours:'۲۴ ساعت',code:'SAMPLE-0217'})"),'image/svg+xml').documentElement;
ok(svg!==null&&svg.textContent.includes('پیش‌نمایش محلی')&&svg.textContent.includes('فاقد اعتبار رسمی'),'SVG فقط نشان نمونه و فاقد اعتبار رسمی دارد');
const text=decodeSVG(svg);
ok(text&&text.startsWith('SAMPLE-ONLY:'),'QR برگ گواهی فقط شناسهٔ نمونه دارد: '+text);
ok(svg.querySelectorAll('.tkqr').length===1,'فقط یک کیوآر روی برگ');
const hiddenCert=window.eval("certificateSVG({name:'نام پنهان',title:'عنوان پنهان',serial:'SERIAL-HIDDEN',include:{name:false,title:false,serial:false,qr:false}})");
const hiddenDoc=new window.DOMParser().parseFromString(hiddenCert,'image/svg+xml');
ok(!hiddenDoc.querySelector('.tkqr')&&!hiddenDoc.documentElement.textContent.includes('نام پنهان')
  &&!hiddenDoc.documentElement.textContent.includes('عنوان پنهان')&&!hiddenDoc.documentElement.textContent.includes('SERIAL-HIDDEN'),
  'گزینه‌های محتوای گواهی واقعاً از خروجی حذف می‌شوند');
const ticketSvg=window.NORA_UI.ticketSVG({title:'کارگاه نمونه',name:'سارا محمدی',serial:'TK-SAMPLE-1'});
const ticketDoc=new window.DOMParser().parseFromString(ticketSvg,'image/svg+xml');
const ticketText=decodeSVG(ticketDoc);
ok(ticketDoc.documentElement.tagName.toLowerCase()==='svg'&&ticketDoc.documentElement.textContent.includes('فاقد اعتبار ورود'),
  'موتور بلیت یک SVG واترمارک‌دار و غیرقابل‌ورود می‌سازد');
ok(ticketText==='SAMPLE-TICKET:TK-SAMPLE-1','QR بلیت فقط شناسهٔ نمونه دارد: '+ticketText);
ok(!/^https?:\/\//i.test(ticketText||''),'QR بلیت نشانی وب نیست');
const safeAttr=window.NORA_UI.ticketSVG({title:'عنوان" onload="alert(1)',name:'نمونه'});
ok(safeAttr.includes('&quot; onload=&quot;'),'متن کاربر در ویژگی SVG به‌درستی escape می‌شود');
const svgExport=await window.NORA_UI.exportSVG(ticketSvg,'svg');
ok(svgExport.extension==='svg'&&String(svgExport.blob.type).startsWith('image/svg+xml'),'خروجی SVG پیش‌نمایش در موتور بلیت در دسترس است');
ok(d.querySelector('#u13')===null && d.querySelector('#tickets')===null,'صفحهٔ بلیت‌ها کلاً برداشته شد');
console.log('   کیوآر:',text,'· بلیت:',ticketText);

/* ── ۲) پیش‌نمایش گواهینامه در پنل سازنده: همان موتور، همان کد ── */
const bd=await open('./builder.html','',{'nora-admin-session':JSON.stringify({role:'admin',u:'owner',personKey:'p1',at:Date.now()})});
const w2=bd.window, d2=w2.document;
w2.eval("openForm('f1'); go('fChanges')");
d2.querySelector('[data-change="cert"]')?.dispatchEvent(new w2.MouseEvent('click',{bubbles:true}));
const psvg=d2.querySelector('#chCertPrev svg');
ok(psvg!==null,'پیش‌نمایش گواهینامه در پنل ساخته شد');
ok(psvg.querySelector('.tkqr')===null,'QR در تصویر گواهیِ پنل خاموش است و مقصدی ندارد');
ok(d2.querySelector('#chTkPrev')===null,'پیش‌نمایش بلیت در پنل نیست');
ok(/پیش‌نمایش محلی|فاقد اعتبار رسمی/.test(d2.querySelector('#chCertPrev')?.textContent||''),'پیش‌نمایش گواهی در پنل نشانِ محلی و غیررسمی دارد');
ok(/QR در این پیش‌نمایش خاموش است/.test(d2.querySelector('#chCertPrev')?.textContent||''),'متن روی تصویر هم خاموش‌بودن QR را توضیح می‌دهد');

console.log('\nqr: '+checks+' بررسی، '+fails+' خطا');
process.exit(fails?1:0);
