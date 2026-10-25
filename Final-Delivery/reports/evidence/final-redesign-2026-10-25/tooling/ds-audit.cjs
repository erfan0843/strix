// Design-system audit: real-browser shots + measured inventory (font sizes, button heights, radii, gaps, content widths, CLS)
// Usage: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<deps> NORA_REPO_UI=<nora-ui> NORA_E2E_IDS=<ids.json> node ds-audit.cjs <outdir> [pagesFilter]
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const fs = require('fs'); const path = require('path');
const ids = JSON.parse(fs.readFileSync(process.env.NORA_E2E_IDS, 'utf8')); const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = process.argv[2]; fs.mkdirSync(out, { recursive: true }); const filter = process.argv[3] || '';
const OWNER = 'http://127.0.0.1:8000', MGR = 'http://127.0.0.1:8080';
const pages = [
  ['home', OWNER + '/home.html'], ['events-public', OWNER + '/events.html'], ['event-public', OWNER + '/event.html?id=' + ids.A],
  ['admin-first', OWNER + '/admin.html'], ['admin-events', OWNER + '/admin.html#events'], ['admin-edit', OWNER + '/admin.html#edit=' + ids.A + '&sec=main'],
  ['admin-event-hub', OWNER + '/admin.html#event=' + ids.A], ['admin-regs', OWNER + '/admin.html#event=' + ids.A + '&tab=regs'],
  ['admin-person', OWNER + '/admin.html#event=' + ids.A + '&tab=regs', 'person'], ['admin-settings', OWNER + '/admin.html#settings'],
  ['admin-users', OWNER + '/admin.html#users'], ['admin-reports', OWNER + '/admin.html#reports'],
  ['builder', OWNER + '/builder.html?fid=' + ids.regA + '&ev=' + ids.A + '&need=reg&back=' + encodeURIComponent('/admin.html#edit=' + ids.A + '&sec=reg')],
  ['manager-first', MGR + '/admin.html'], ['manager-event-hub', MGR + '/admin.html#event=' + ids.A],
];
const inventory = page => page.evaluate(() => {
  const vis = el => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && !el.closest('details:not([open]) > :not(summary)'); };
  const count = (map, k) => { map[k] = (map[k] || 0) + 1; };
  const fs = {}, fw = {}, btnH = {}, inpH = {}, radii = {}, gaps = {}, pads = {}, colors = {}, fams = {};
  const all = [...document.querySelectorAll('body *')].filter(vis);
  for (const el of all) {
    const cs = getComputedStyle(el);
    if (el.childNodes.length && [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) { count(fs, cs.fontSize); count(fw, cs.fontWeight); count(colors, cs.color); count(fams, cs.fontFamily.split(',')[0].replace(/"/g, '')); }
    if (el.matches('button, a.btn, .btn, [role=button]')) count(btnH, Math.round(el.getBoundingClientRect().height) + 'px');
    if (el.matches('input:not([type=checkbox]):not([type=radio]):not([type=hidden]), select, textarea')) count(inpH, Math.round(el.getBoundingClientRect().height) + 'px');
    if (cs.borderRadius !== '0px' && (cs.backgroundColor !== 'rgba(0, 0, 0, 0)' || cs.borderTopWidth !== '0px')) count(radii, cs.borderRadius.split(' ')[0]);
    if ((cs.display.includes('flex') || cs.display.includes('grid')) && cs.gap !== 'normal' && cs.gap !== '0px') count(gaps, cs.gap.split(' ')[0]);
    if (el.matches('.card, section, .tile, .eftile, .kpi, .evcard, .pcard, .hit, article')) count(pads, cs.paddingTop + '/' + cs.paddingLeft);
  }
  const main = document.querySelector('main, .main, #admMain, .shell') || document.body; const mr = main.getBoundingClientRect();
  const firstCard = document.querySelector('.card, article, .evcard, .tile'); const fr = firstCard ? firstCard.getBoundingClientRect() : null;
  const h = [...document.querySelectorAll('h1,h2,h3,.head,.ttl,.sec-h,.hd')].filter(vis).slice(0, 8).map(e => e.tagName + '.' + String(e.className).split(' ')[0] + ' ' + getComputedStyle(e).fontSize + '/' + getComputedStyle(e).fontWeight + ' «' + e.textContent.trim().slice(0, 28) + '»');
  const top = (sel, n) => Object.entries(sel).sort((a, b) => b[1] - a[1]).slice(0, n).map(([k, v]) => k + '×' + v).join(' ');
  return { vw: innerWidth, sw: document.documentElement.scrollWidth, mainLeft: Math.round(mr.left), mainRight: Math.round(innerWidth - mr.right), mainWidth: Math.round(mr.width), firstCardLeft: fr ? Math.round(fr.left) : null, fontSizes: top(fs, 14), weights: top(fw, 6), families: top(fams, 3), btnHeights: top(btnH, 8), inputHeights: top(inpH, 6), radii: top(radii, 10), gaps: top(gaps, 10), cardPads: top(pads, 8), textColors: Object.keys(colors).length, headings: h, buttons: Object.values(btnH).reduce((a, b) => a + b, 0), cards: document.querySelectorAll('.card').length, primaryBtns: [...document.querySelectorAll('.btn.primary, button.primary')].filter(vis).length, cls: (window.__cls || 0).toFixed(3) };
});
(async () => { const b = await launchBrowser(); const page = await b.newPage(); page.on('dialog', d => d.accept());
  await page.addInitScript(() => { window.__cls = 0; try { new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true }); } catch (e) { } });
  const report = {};
  for (const [w, h] of [[1440, 900], [1024, 768], [390, 844], [360, 800]]) {
    await page.setViewportSize({ width: w, height: h });
    for (const [k, u, extra] of pages) { if (filter && !k.includes(filter)) continue;
      await page.goto('about:blank'); await page.goto(u, { waitUntil: 'load' }); await sleep(3200);
      if (extra === 'person') { const r = await page.$('[data-ef-person]'); if (r) { await r.click(); await sleep(1500); } }
      const inv = await inventory(page); report[`${k}@${w}`] = inv;
      await page.screenshot({ path: path.join(out, `${k}-${w}.png`) });
      if (w === 1440 || w === 390) await page.screenshot({ path: path.join(out, `${k}-${w}-full.png`), fullPage: true });
      console.log(`${k}@${w}: sw=${inv.sw} main=${inv.mainLeft}|${inv.mainWidth}|${inv.mainRight} fonts=${inv.fontSizes} | btnH=${inv.btnHeights} | radii=${inv.radii} | cls=${inv.cls}`);
    }
  }
  fs.writeFileSync(path.join(out, 'inventory.json'), JSON.stringify(report, null, 1)); await b.close(); })().catch(e => { console.error('ERR', e.stack || e.message); process.exit(1) });
