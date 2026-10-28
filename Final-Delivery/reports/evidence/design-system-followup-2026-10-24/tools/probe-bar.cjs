const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => { const b = await launchBrowser(); const page = await b.newPage(); const [url,w,h]=process.argv.slice(2);
  await page.setViewportSize({ width:+w, height:+h }); await page.goto(url,{waitUntil:'load'}); await sleep(2500);
  console.log(await page.evaluate(()=>{ const r=s=>{const e=document.querySelector(s); if(!e) return null; const b=e.getBoundingClientRect(); const cs=getComputedStyle(e); return `${s}: ${Math.round(b.width)}x${Math.round(b.height)} @${Math.round(b.left)},${Math.round(b.top)} fs=${cs.fontSize} txt=${(e.textContent||'').trim().slice(0,40)}`};
    return ['#admBar','#admBar .nmark','#admBar .tt','#admBar .ph-title','#admBar .ph-sub','#admBar .ph-actions','#admBar .ph-meta','#admBar .ph-meta .tag','#admBar .navclock','#admBar .server-identity'].map(r).join('\n') + '\ngridcols=' + getComputedStyle(document.querySelector('#admBar')).gridTemplateColumns + ' rows=' + getComputedStyle(document.querySelector('#admBar')).gridTemplateRows; }));
  await b.close(); })().catch(e=>{console.error(e);process.exit(1)});
