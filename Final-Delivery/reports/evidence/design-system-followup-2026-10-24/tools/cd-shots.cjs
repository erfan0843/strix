// countdown evidence: event page (light/dark) + home hero at given widths; crops the first .nora-countdown and .reg-state
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => { const b = await launchBrowser(); const page = await b.newPage(); page.on('dialog', d => d.accept());
  const [base, out] = process.argv.slice(2); const ids = JSON.parse(process.env.CD_EVENTS || '[]');
  for (const [w, h] of [[1440, 900], [390, 844]]) {
    await page.setViewportSize({ width: w, height: h });
    for (const theme of ['light', 'dark']) {
      for (const id of ids) {
        await page.goto('about:blank'); await page.goto(`${base}/event.html?id=${id}`, { waitUntil: 'load' });
        await page.evaluate(t => { document.documentElement.setAttribute('data-theme', t); }, theme); await sleep(1500);
        const info = await page.evaluate(() => { const cd = document.querySelector('.nora-countdown'); const rs = document.querySelector('.reg-state');
          const cs = el => el ? getComputedStyle(el) : null; const n = cd && cd.querySelector('.cdb-n'); const u = cd && cd.querySelector('.cdb-u'); const bl = cd && cd.querySelector('.cdb');
          return { cd: cd ? cd.className : null, num: n ? cs(n).color : null, unit: u ? cs(u).color : null, block: bl ? cs(bl).backgroundColor : null, rs: rs ? rs.className : null, rsColor: rs ? cs(rs).color : null, rsBg: rs ? cs(rs).backgroundColor : null }; });
        console.log(`${w} ${theme} ${id}`, JSON.stringify(info));
        const el = await page.$('.nora-countdown'); if (el) await el.screenshot({ path: `${out}-cd-${id}-${theme}-${w}.png` });
        const rs = await page.$('.reg-state'); if (rs) await rs.screenshot({ path: `${out}-rs-${id}-${theme}-${w}.png` });
        await page.screenshot({ path: `${out}-event-${id}-${theme}-${w}.png` });
      }
      await page.goto('about:blank'); await page.goto(`${base}/home.html`, { waitUntil: 'load' });
      await page.evaluate(t => { document.documentElement.setAttribute('data-theme', t); }, theme); await sleep(1500);
      const hero = await page.$('.nora-countdown.is-hero'); if (hero) await hero.screenshot({ path: `${out}-hero-${theme}-${w}.png` });
      console.log(`${w} ${theme} home hero`, !!hero);
      await page.screenshot({ path: `${out}-home-${theme}-${w}.png` });
    }
  }
  await b.close(); })().catch(e => { console.error(e); process.exit(1) });
