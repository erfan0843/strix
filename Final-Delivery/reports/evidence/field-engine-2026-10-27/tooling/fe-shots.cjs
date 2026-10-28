// Field-engine before/after shots on the same fixture. argv: <outdir> <ownerOrigin> <guestOrigin> <publicFid|->
// Views: picker (all / search), editors (jalali-date → type-change, fullname → profile control, rating → bounds, multi → limits),
// canvas summary, public form (all types) — at 1440 / 1024 / 390 / 360.
const fs = require('node:fs'), path = require('node:path');
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const [out, O, B, FID] = process.argv.slice(2); fs.mkdirSync(out, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const b = await launchBrowser(); const page = await b.newPage(); page.on('dialog', d => d.accept());
  const shot = (n, full) => page.screenshot({ path: path.join(out, n + '.png'), fullPage: !!full });
  const ev = c => page.evaluate(c);
  for (const [w, h] of [[1440, 900], [1024, 768], [390, 844], [360, 740]]) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto('about:blank'); await page.goto(O + '/create.html?need=reg', { waitUntil: 'load' }); await sleep(1500);
    await ev("go('s2');applyPack('empty','replace')"); await sleep(300);
    await ev("document.getElementById('shAdd').classList.contains('on')||document.getElementById('addTop').click()"); await sleep(400);
    await shot('picker-' + w);
    await page.fill('#catSearch', 'تاریخ تولد'); await page.$eval('#catSearch', el => el.dispatchEvent(new Event('input', { bubbles: true }))); await sleep(300);
    await shot('picker-search-' + w);
    await page.fill('#catSearch', ''); await page.$eval('#catSearch', el => el.dispatchEvent(new Event('input', { bubbles: true }))); await sleep(200);
    await ev('closeSheets()');
    for (const k of ['jalali-date', 'fullname', 'rating', 'multi']) {
      await ev("(()=>{const f=addField('" + k + "');})()"); await sleep(350);
      await page.evaluate(() => { const s = document.getElementById('shField'); s.scrollTop = 0; });
      await shot('editor-' + k + '-' + w, w >= 1024);
      if (k === 'jalali-date') { await page.evaluate(() => { const b = document.getElementById('fdTypeBox'); if (b) b.scrollIntoView({ block: 'center' }); }); await sleep(150); await shot('editor-' + k + '-typechange-' + w); }
      await page.click('#fdSave'); await sleep(200);
      if (await ev("document.getElementById('shField').classList.contains('on')")) await ev('closeSheets()');
    }
    await sleep(200); await shot('canvas-' + w, true);
    if (FID && FID !== '-') {
      await page.goto('about:blank'); await page.goto(B + '/form.html?fid=' + encodeURIComponent(FID) + '&kind=reg', { waitUntil: 'load' }); await sleep(2500);
      await shot('public-start-' + w);
      await page.evaluate(() => { const b = [...document.querySelectorAll('button:not([disabled]), a.btn')].find(e => e.offsetParent !== null && /شروع/.test(e.textContent)); if (b) b.click(); }); await sleep(1200);
      await shot('public-questions-' + w, true);
    }
  }
  await b.close();
  console.log('fe-shots done → ' + out);
})().catch(e => { console.error('CRASH', e); process.exit(1); });
