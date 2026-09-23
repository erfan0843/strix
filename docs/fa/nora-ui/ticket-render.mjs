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
     node ticket-render.mjs --sheet preview-ticket.png (ورق پنج پوسته + رسید)
     node ticket-render.mjs --cert out.png           (برگ گواهینامه)

   پیش‌نیاز یک‌باره:
     pip install fonttools brotli resvg-py     (ورک‌اسپیس مجازی یا سیستمی)

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
const EXPORTS='ticketFile,receiptFile,certificateFile,shortCode,ticketPayload,TK_SKIN_NAMES,TK_GEO';

/* ui.js را در محیط نود می‌خوانیم: فقط موتور و ابزارها، بدون بخش مرورگر.
   بلیت با موتور خودِ ui.js کشیده می‌شود؛ نگاره‌های tickets/plates.js فقط برای رسید است.
   خوانده می‌شود؛ همان چیزی که صفحه‌ها هم در مرورگر لود می‌کنند. */
export async function loadEngine(){
  const src=fs.readFileSync(path.join(here,'ui.js'),'utf8');
  const plates=fs.readFileSync(path.join(here,'tickets','plates.js'),'utf8');
  const tmp=path.join(process.env.TMPDIR||'/tmp','nora-ticket-engine.mjs');
  const js=plates.replace(/if\(typeof module[\s\S]*$/,'')+'\n'+
    src.replace(/if\(typeof module[\s\S]*$/,'')+`\nexport {${EXPORTS}};\n`;
  fs.writeFileSync(tmp,js);
  return import('file://'+tmp+'?v='+Date.now());
}

/* پاک‌سازی ورودی: هر چه هست رشته شود و کاراکترهای کنترلی برود */
const clean=o=>Object.fromEntries(Object.entries(o||{}).map(([k,v])=>[k,
  typeof v==='string'?v.replace(/[\u0000-\u001f]/g,''):v]));

/* ── فونت‌ها: resvg فقط TTF می‌خواند؛ اگر نبود، از woff2 ریپو می‌سازیم ── */
function fontDir(pyExe){
  const cands=[process.env.NORA_FONT_DIR,'/tmp/fonts-ttf',path.join(here,'fonts-ttf')].filter(Boolean);
  const has=dir=>dir&&fs.existsSync(dir)&&fs.readdirSync(dir).some(f=>f.endsWith('.ttf'));
  for(const dir of cands) if(has(dir)) return dir;
  const out=path.join(process.env.TMPDIR||'/tmp','nora-fonts-ttf');
  const srcDir=path.join(here,'fonts');
  if(!fs.existsSync(srcDir)) return null;
  fs.mkdirSync(out,{recursive:true});
  const py=`
import sys, os
from fontTools.ttLib import TTFont
src,out=sys.argv[1],sys.argv[2]
for f in os.listdir(src):
    if not f.endswith('.woff2'): continue
    dst=os.path.join(out,f.replace('.woff2','.ttf'))
    if os.path.exists(dst): continue
    ft=TTFont(os.path.join(src,f)); ft.flavor=None; ft.save(dst)
`;
  try{
    execFileSync(pyExe,['-c',py,srcDir,out],{stdio:'pipe'});
    return fs.readdirSync(out).some(f=>f.endsWith('.ttf'))?out:null;
  }catch(err){return null;}
}

function pythonExe(){
  const cands=[process.env.NORA_PYTHON,'/tmp/qvenv/bin/python3',path.join(here,'.venv/bin/python3'),'python3'];
  for(const p of cands){
    if(p==='python3') return p;
    if(fs.existsSync(p)) return p;
  }
  return 'python3';
}

export async function ticketPNG(fields,{width=1100,skin,receipt=false}={}){
  const m=await loadEngine();
  const o=clean(fields);
  if(skin) o.skin=skin;
  const svg=receipt?m.receiptFile(o):m.ticketFile(o);
  const svgPath=path.join(process.env.TMPDIR||'/tmp','nora-ticket-'+Date.now()+'.svg');
  fs.writeFileSync(svgPath,svg);
  const pyExe=pythonExe();
  const fonts=fontDir(pyExe);
  const py=`
import sys, os, resvg_py
d=os.environ.get('NORA_FONT_DIR') or ''
fonts=[os.path.join(d,f) for f in sorted(os.listdir(d)) if f.endswith('.ttf')] if d else []
png=resvg_py.svg_to_bytes(svg_path=sys.argv[1], width=int(sys.argv[2]), font_files=fonts, background='#FFFFFF')
open(sys.argv[3],'wb').write(bytes(png))
`;
  const pngPath=svgPath.replace(/\.svg$/,'.png');
  try{
    execFileSync(pyExe,['-c',py,svgPath,String(width),pngPath],
      {stdio:'pipe',env:{...process.env,NORA_FONT_DIR:fonts||''}});
    return {png:fs.readFileSync(pngPath),svg,file:pngPath,fonts};
  }catch(err){
    return {png:null,svg,file:svgPath,fonts,why:String(err.stderr||err.message).split('\n').slice(-1)[0]};
  }
}

/* ── ورق پیش‌نمایش: پنج پوستهٔ بلیت + رسید، در یک تصویر ── */
export async function previewSheet({width=880, gap=14, bg='#E9EFEC'}={}){
  const m=await loadEngine();
  const tmp=process.env.TMPDIR||'/tmp';
  const files=[];
  const one=async(svg,name,w)=>{
    const svgPath=path.join(tmp,'nora-prev-'+name+'.svg'); fs.writeFileSync(svgPath,svg);
    const png=path.join(tmp,'nora-prev-'+name+'.png');
    const pyExe=pythonExe(), fonts=fontDir(pyExe);
    const py=`import sys, os, resvg_py
d=os.environ.get('NORA_FONT_DIR') or ''
fonts=[os.path.join(d,f) for f in sorted(os.listdir(d)) if f.endswith('.ttf')] if d else []
png=resvg_py.svg_to_bytes(svg_path=sys.argv[1], width=int(sys.argv[2]), font_files=fonts, background=sys.argv[4])
open(sys.argv[3],'wb').write(bytes(png))`;
    execFileSync(pyExe,['-c',py,svgPath,String(w),png,bg],
      {stdio:'pipe',env:{...process.env,NORA_FONT_DIR:fonts||''}});
    files.push(png);
  };
  const D={title:'کارگاه عکاسی مقدماتی',day:'جمعه',date:'۱۴۰۵/۰۶/۲۱',time:'۱۷:۰۰',venue:'فرهنگسرای نیاوران',
    name:'سارا محمدی',seat:'ردیف ۳ — صندلی ۱۷',no:'۱۲۴۵',code:'TL1307BVUC1981',short:'T4K7M9X'};
  for(const skin of ['clear','forest','gold','ocean','night'])
    await one(m.ticketFile({...D,skin,parts:['title','date','venue','name','seat','no','code','qr','logo']}),skin,width);
  await one(m.receiptFile({skin:'clear',amount:900000,discount:100000,program:'کارگاه عکاسی مقدماتی',
    when:'جمعه ۲۰ شهریور · ساعت ۱۷:۰۰',payer:'سارا محمدی',method:'درگاه رسمی بله',at:'جمعه ۲۰ شهریور',
    ticket:'T4K7M9X',track:'۱۷۳',state:'ok'}),'receipt',620);
  const out=path.join(tmp,'nora-preview-sheet.png');
  const pyExe=pythonExe();
  const py=`import sys
from PIL import Image
gap,bg=int(sys.argv[2]),sys.argv[-1]
ims=[Image.open(f).convert('RGB') for f in sys.argv[3:-1]]
W=max(i.width for i in ims); H=sum(i.height+gap for i in ims)+gap
sheet=Image.new('RGB',(W+gap*2,H),bg)
y=gap
for i in ims: sheet.paste(i,((W+gap*2-i.width)//2,y)); y+=i.height+gap
sheet.save(sys.argv[1])
print(sheet.size)`;
  execFileSync(pyExe,['-c',py,out,String(gap),...files,bg],{stdio:'pipe'});
  return fs.readFileSync(out);
}

/* نمونهٔ آماده: همان بلیت کارگاه، برای آزمون و نمایش */
export const SAMPLE={kind:'بلیت نفر اصلی',title:'کارگاه فن بیان مقدماتی',day:'چهارشنبه',
  date:'۱۴۰۵/۰۷/۰۸',time:'۱۶:۰۰',venue:'تهران، خیابان ولی‌عصر، پلاک ۱۲',name:'سارا محمدی',
  seat:'ردیف ۳ — صندلی ۱۷',no:'۱۲۴۵',code:'TL1307BVUC1981',skin:'forest',confirmed:true,seat:'ردیف ۳ — صندلی ۱۷',
  noteText:'ورود با همین بلیت؛ کارت شناسایی همراه باشد'};

if(process.argv[1]&&process.argv[1].endsWith('ticket-render.mjs')){
  const args=process.argv.slice(2);
  if(args[0]==='--cert'){
    const out=path.resolve(args[1]||'certificate.png');
    const m=await loadEngine();
    const svg=m.certificateFile({name:'سارا محمدی',title:'کارگاه عکاسی مقدماتی',kind:'گواهینامهٔ پایان دوره',
      date:'جمعه ۲۱ شهریور ۱۴۰۵',hours:'۲۴ ساعت',code:'TL1307BVUC1981',serial:'NL-T4K7M9X'});
    const svgPath=path.join(process.env.TMPDIR||'/tmp','nora-cert.svg');
    fs.writeFileSync(svgPath,svg);
    const pyExe=pythonExe(), fonts=fontDir(pyExe);
    const py=`import sys, os, resvg_py
d=os.environ.get('NORA_FONT_DIR') or ''
fonts=[os.path.join(d,f) for f in sorted(os.listdir(d)) if f.endswith('.ttf')] if d else []
png=resvg_py.svg_to_bytes(svg_path=sys.argv[1], width=int(sys.argv[2]), font_files=fonts, background='#E9EFEC')
open(sys.argv[3],'wb').write(bytes(png))`;
    try{
      execFileSync(pyExe,['-c',py,svgPath,'1240',out],{stdio:'pipe',env:{...process.env,NORA_FONT_DIR:fonts||''}});
      console.log('گواهینامه نوشته شد:',out,Math.round(fs.statSync(out).size/1024),'کیلوبایت');
    }catch(err){fs.writeFileSync(out.replace(/\.png$/,'.svg'),svg); console.log('resvg نبود — SVG نوشته شد');}
    process.exit(0);
  }
  if(args[0]==='--sheet'){
    const out=path.resolve(args[1]||'preview-ticket.png');
    const buf=await previewSheet();
    fs.writeFileSync(out,buf);
    console.log('ورق پیش‌نمایش نوشته شد:',out,Math.round(buf.length/1024),'کیلوبایت');
    process.exit(0);
  }
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
