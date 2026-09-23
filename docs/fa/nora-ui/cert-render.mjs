/* ══════════════════════════════════════════════════════════════════════════
   ساخت تصویر گواهینامه برای ربات و بله
   ──────────────────────────────────────────────────────────────────────────
   همان موتور تصویری صفحه‌ها (`ui.js`) را می‌خواند و SVG یا PNG می‌دهد.
   ربات با یک پیام تصویری این فایل را برای کاربر می‌فرستد؛ خودِ کاربر هم
   می‌تواند برگش را از صفحهٔ گواهینامه ذخیره کند.

   اجرا:
     node cert-render.mjs --cert out.png     (PNG اگر resvg باشد، وگرنه SVG)
     node cert-render.mjs --cert out.svg     (SVG، همیشه)

   پیش‌نیاز یک‌باره:
     pip install fonttools brotli resvg-py     (ورک‌اسپیس مجازی یا سیستمی)
   ══════════════════════════════════════════════════════════════════════════ */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';

const here=path.dirname(fileURLToPath(import.meta.url));
const EXPORTS='certificateSVG,certificateFile,shortCode';

/* ui.js را در محیط نود می‌خوانیم: فقط موتور و ابزارها، بدون بخش مرورگر.
   برگ گواهینامه با موتور خودِ ui.js کشیده می‌شود؛ هیچ نگارهٔ بیرونی لازم نیست. */
export async function loadEngine(){
  const src=fs.readFileSync(path.join(here,'ui.js'),'utf8');
  const tmp=path.join(process.env.TMPDIR||'/tmp','nora-cert-engine.mjs');
  const js=src.replace(/if\(typeof module[\s\S]*$/,'')+`\nexport {${EXPORTS}};\n`;
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


/* برگ گواهینامه را می‌کشد و اگر resvg باشد، PNG هم می‌دهد */
export async function certPNG(fields,{width=1240,bg='#E9EFEC'}={}){
  const m=await loadEngine();
  const svg=m.certificateFile({name:'سارا محمدی',title:'',kind:'گواهینامهٔ پایان دوره',...fields});
  const svgPath=path.join(process.env.TMPDIR||'/tmp','nora-cert-'+Date.now()+'.svg');
  fs.writeFileSync(svgPath,svg);
  const pyExe=pythonExe(), fonts=fontDir(pyExe);
  const py=`import sys, os, resvg_py
d=os.environ.get('NORA_FONT_DIR') or ''
fonts=[os.path.join(d,f) for f in sorted(os.listdir(d)) if f.endswith('.ttf')] if d else []
png=resvg_py.svg_to_bytes(svg_path=sys.argv[1], width=int(sys.argv[2]), font_files=fonts, background=sys.argv[4])
open(sys.argv[3],'wb').write(bytes(png))`;
  const pngPath=svgPath.replace(/\.svg$/,'.png');
  try{
    execFileSync(pyExe,['-c',py,svgPath,String(width),pngPath,bg],
      {stdio:'pipe',env:{...process.env,NORA_FONT_DIR:fonts||''}});
    return {png:fs.readFileSync(pngPath),svg,file:pngPath,fonts};
  }catch(err){
    return {png:null,svg,file:svgPath,fonts,why:String(err.stderr||err.message).split('\n').slice(-1)[0]};
  }
}

if(process.argv[1]&&process.argv[1].endsWith('cert-render.mjs')){
  const args=process.argv.slice(2);
  const i=args.indexOf('--cert');
  const out=path.resolve(args[i+1]||'certificate.png');
  const r=await certPNG({title:'کارگاه عکاسی مقدماتی',date:'جمعه ۲۱ شهریور ۱۴۰۵',
    hours:'۲۴ ساعت',code:'TL1307BVUC1981',serial:'NL-T4K7M9X'});
  if(out.endsWith('.svg')){fs.writeFileSync(out,r.svg); console.log('SVG نوشته شد:',out,r.svg.length,'بایت');}
  else if(r.png){fs.writeFileSync(out,r.png); console.log('PNG نوشته شد:',out,Math.round(r.png.length/1024),'کیلوبایت');}
  else{
    const alt=out.replace(/\.png$/,'.svg'); fs.writeFileSync(alt,r.svg);
    console.log('resvg نبود ('+r.why+') — SVG نوشته شد:',alt);
  }
}
