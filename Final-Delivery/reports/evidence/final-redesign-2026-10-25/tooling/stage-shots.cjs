// Stage shots: argv = outdir, then "role:name:path" entries; sizes 1440x900 and 390x844 (viewport + full). Reuses one page.
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const O={guest:'http://127.0.0.1:8001',owner:'http://127.0.0.1:8000',manager:'http://127.0.0.1:8080',member:'http://127.0.0.1:8090'};
const SIZES=(process.env.SIZES||'1440x900,390x844').split(',').map(s=>s.split('x').map(Number));
(async()=>{const [out,...pages]=process.argv.slice(2); require('fs').mkdirSync(out,{recursive:true});
 const b=await launchBrowser(); const page=await b.newPage(); page.on('dialog',d=>d.accept());
 for(const spec of pages){const i=spec.indexOf(':'), j=spec.indexOf(':',i+1); const role=spec.slice(0,i), name=spec.slice(i+1,j), path=spec.slice(j+1);
  for(const [w,h] of SIZES){await page.setViewportSize({width:w,height:h}); await page.goto('about:blank'); await page.goto(O[role]+path,{waitUntil:'load'}); await sleep(2500);
   const sw=await page.evaluate(()=>document.documentElement.scrollWidth);
   await page.screenshot({path:`${out}/${name}-${w}.png`}); await page.screenshot({path:`${out}/${name}-${w}-full.png`,fullPage:true});
   console.log(role,name,w,'sw='+sw+(sw>w?' OVERFLOW':''));}}
 await b.close();})().catch(e=>{console.error(e);process.exit(1)});
