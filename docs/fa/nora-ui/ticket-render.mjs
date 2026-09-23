/* ══════════════════════════════════════════════════════════════════════════
   ساخت تصویر بلیت و رسید برای ربات و بله
   ──────────────────────────────────────────────────────────────────────────
   همان موتور تصویری صفحه‌ها (`ui.js`) را می‌خواند و SVG یا PNG می‌دهد.
   ربات با یک پیام تصویری این فایل را برای کاربر می‌فرستد؛ کاربر هم هر وقت
   خواست با کد پیگیری یا شمارهٔ موبایل، همین بلیت را دوباره می‌گیرد.

   اجرا:
     node ticket-render.mjs bilet.json out.png        (PNG اگر resvg باشد)
     node ticket-render.mjs bilet.json out.svg        (SVG، همیشه)
     node ticket-render.mjs --sample out.png          (نمونهٔ آماده)

   bilet.json نمونه:
     {"kind":"بلیت نفر اصلی","title":"کارگاه فن بیان مقدماتی",
      "day":"جمعه","date":"۱۴۰۵/۰۷/۰۸","time":"۱۶:۰۰","venue":"تهران، ولی‌عصر",
      "name":"سارا محمدی","seat":"ردیف ۳ — صندلی ۱۷","no":"۱۲۴۵",
      "code":"TL1307BVUC1981","skin":"clear","confirmed":true}
   ══════════════════════════════════════════════════════════════════════════ */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';

const here=path.dirname(fileURLToPath(import.meta.url));
const EXPORTS='ticketFile,receiptFile,shortCode,ticketPayload,TK_SKINS';

/* ui.js را در محیط نود می‌خوانیم: فقط موتور و ابزارها، بدون بخش مرورگر */
export async function loadEngine(){
  const src=fs.readFileSync(path.join(here,'ui.js'),'utf8');
  const tmp=path.join(process.env.TMPDIR||'/tmp','nora-ticket-engine.mjs');
  const js=src.replace(/if\(typeof module[\s\S]*$/,'')+`\nexport {${EXPORTS}};\n`;
  fs.writeFileSync(tmp,js);
  return import('file://'+tmp+'?v='+Date.now());
}

/* پاک‌سازی ورودی: هر چه هست رشته شود و کاراکترهای کنترلی برود */
const clean=o=>Object.fromEntries(Object.entries(o||{}).map(([k,v])=>[k,
  typeof v==='string'?v.replace(/[\u0000-\u001f]/g,''):v]));

export async function ticketPNG(fields,{width=1100,skin,receipt=false}={}){
  const m=await loadEngine();
  const o=clean(fields);
  if(skin) o.skin=skin;
  const svg=receipt?m.receiptFile(o):m.ticketFile(o);
  const svgPath=path.join(process.env.TMPDIR||'/tmp','nora-ticket-'+Date.now()+'.svg');
  fs.writeFileSync(svgPath,svg);
  const py=`
import sys, os, resvg_py
fonts=[f for f in [os.environ.get('NORA_FONT_DIR','')+'/Vazirmatn-%s.ttf'%w for w in ['Regular','Bold','SemiBold','Medium']] if os.path.exists(f)]
png=resvg_py.svg_to_bytes(svg_path=sys.argv[1], width=int(sys.argv[2]), font_files=fonts, background='#FFFFFF')
open(sys.argv[3],'wb').write(bytes(png))
`;
  const pngPath=svgPath.replace(/\.svg$/,'.png');
  const pyExe=process.env.NORA_PYTHON||(fs.existsSync('/tmp/qvenv/bin/python3')?'/tmp/qvenv/bin/python3':'python3');
  const fontDir=process.env.NORA_FONT_DIR||'/tmp/fonts-ttf';
  try{
    execFileSync(pyExe,['-c',py,svgPath,String(width),pngPath],{stdio:'pipe',env:{...process.env,NORA_FONT_DIR:fontDir}});
    return {png:fs.readFileSync(pngPath),svg,file:pngPath};
  }catch(err){
    return {png:null,svg,file:svgPath,why:String(err.stderr||err.message).split('\n').slice(-1)[0]};
  }
}

/* نمونهٔ آماده: همان بلیت کارگاه، برای آزمون و نمایش */
export const SAMPLE={kind:'بلیت نفر اصلی',title:'کارگاه فن بیان مقدماتی',day:'چهارشنبه',
  date:'۱۴۰۵/۰۷/۰۸',time:'۱۶:۰۰',venue:'تهران، خیابان ولی‌عصر، پلاک ۱۲',name:'سارا محمدی',
  seat:'ردیف ۳ — صندلی ۱۷',no:'۱۲۴۵',code:'TL1307BVUC1981',skin:'forest',confirmed:true,
  noteText:'ورود با همین بلیت؛ کارت شناسایی همراه باشد'};

if(process.argv[1]&&process.argv[1].endsWith('ticket-render.mjs')){
  const args=process.argv.slice(2);
  const sample=args[0]==='--sample';
  const srcPath=sample?null:args[0];
  const out=path.resolve(sample?args[1]:(args[1]||'ticket.png'));
  const fields=srcPath?clean(JSON.parse(fs.readFileSync(srcPath,'utf8'))):SAMPLE;
  const isReceipt=/resid|receipt/i.test(out);
  const r=await ticketPNG(fields,{receipt:isReceipt});
  if(out.endsWith('.svg')){fs.writeFileSync(out,r.svg); console.log('SVG نوشته شد:',out,r.svg.length,'بایت');}
  else if(r.png){fs.writeFileSync(out,r.png); console.log('PNG نوشته شد:',out,Math.round(r.png.length/1024),'کیلوبایت');}
  else{
    const alt=out.replace(/\.png$/,'.svg'); fs.writeFileSync(alt,r.svg);
    console.log('resvg نبود ('+r.why+') — SVG نوشته شد:',alt);
  }
}
