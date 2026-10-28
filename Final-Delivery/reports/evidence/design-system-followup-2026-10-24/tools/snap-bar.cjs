const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => { const b = await launchBrowser(); const page = await b.newPage(); const [url,w,h]=process.argv.slice(2);
  await page.setViewportSize({ width:+w, height:+h });
  await page.addInitScript(() => { window.__s=[]; let last=''; const iv=setInterval(()=>{const e=document.querySelector('#admBar'); if(!e) return; const hh=Math.round(e.getBoundingClientRect().height); const html=e.innerHTML.replace(/\s+/g,' ').slice(0,700); const k=hh+html; if(k!==last){window.__s.push([Math.round(performance.now()),hh,html]); last=k;}},20); setTimeout(()=>clearInterval(iv),4000); });
  await page.goto(url,{waitUntil:'load'}); await sleep(3000);
  for (const [t,hh,html] of await page.evaluate(()=>window.__s)) console.log(`\n${t}ms h=${hh}\n${html}`);
  await b.close(); })().catch(e=>{console.error(e);process.exit(1)});
