const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => { const b = await launchBrowser(); const page = await b.newPage();
  const [url, w, h, sels] = process.argv.slice(2);
  await page.setViewportSize({ width: +w, height: +h });
  await page.addInitScript(sel => { window.__m = []; const tick = () => { const o = {}; for (const s of sel.split(',')) { const el = document.querySelector(s); o[s] = el ? Math.round(el.getBoundingClientRect().height) + '@' + Math.round(el.getBoundingClientRect().top) : null; } window.__m.push([Math.round(performance.now()), JSON.stringify(o)]); }; const iv = setInterval(tick, 50); setTimeout(() => clearInterval(iv), 4000); }, sels);
  await page.goto(url, { waitUntil: 'load' }); await sleep(3500);
  const m = await page.evaluate(() => window.__m); let last = ''; for (const [t, o] of m) { if (o !== last) { console.log(t + 'ms ' + o); last = o; } }
  await b.close(); })().catch(e => { console.error(e); process.exit(1) });
