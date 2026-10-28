// DOM complexity metrics for before/after comparison. argv: <ownerBase> <guestBase> <fid> <label> <outJson>
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const fs = require('fs');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const [ownerBase, guestBase, fid, label, outJson] = process.argv.slice(2);
const pages = [
  ['create-new', ownerBase + '/create.html', ''],
  ['create-edit', ownerBase + '/create.html?fid=' + fid, ''],
  ['create-s2', ownerBase + '/create.html?fid=' + fid, '#stepper button:nth-child(2)'],
  ['create-s3', ownerBase + '/create.html?fid=' + fid, '#stepper button:nth-child(3)'],
  ['create-s4', ownerBase + '/create.html?fid=' + fid, '#stepper button:nth-child(4)'],
  ['center', ownerBase + '/builder.html', ''],
  ['center-panel', ownerBase + '/builder.html', '#formCards [data-open-form], #formCards [data-form] button, #formCards [data-form]'],
  ['public', guestBase + '/form.html?fid=' + fid + '&kind=reg', ''],
];
const metric = () => {
  const vis = e => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const all = [...document.body.querySelectorAll('*')].filter(vis);
  const depth = el => { let d = 0; while (el && el !== document.body) { d++; el = el.parentElement; } return d; };
  const controls = all.filter(e => /^(BUTTON|A|INPUT|SELECT|TEXTAREA)$/.test(e.tagName) || e.getAttribute('role') === 'button');
  const unnamedIcon = controls.filter(e => !(e.textContent || '').trim() && !e.getAttribute('aria-label') && !e.getAttribute('title') && !(e.labels && e.labels.length));
  const small = all.filter(e => e.children.length === 0 && (e.textContent || '').trim() && parseFloat(getComputedStyle(e).fontSize) < 11 && e.tagName !== 'svg' && !e.closest('svg'));
  const shadows = all.filter(e => getComputedStyle(e).boxShadow !== 'none').length;
  const gradients = all.filter(e => /gradient/.test(getComputedStyle(e).backgroundImage)).length;
  const words = (document.body.innerText || '').split(/\s+/).filter(Boolean).length;
  const latinIds = ((document.body.innerText || '').match(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}\b|\bev-[0-9a-f]{10}\b/g) || []).length;
  const tech = ((document.body.innerText || '').match(/FastAPI|backend|localStorage|API|JSON|endpoint/g) || []).length;
  return { visibleElements: all.length, maxDepth: Math.max(...all.map(depth)), controls: controls.length, primaryButtons: all.filter(e => e.matches('button.primary, .btn.primary, button.brand, .btn.brand')).length,
    unnamedIconControls: unnamedIcon.length, textUnder11px: small.length, shadows, gradients, details: all.filter(e => e.tagName === 'DETAILS').length, chips: all.filter(e => e.matches('.tag, .chip, .pill')).length,
    words, latinIdsInText: latinIds, technicalTerms: tech, scrollHeight: document.documentElement.scrollHeight, scrollWidth: document.documentElement.scrollWidth };
};
(async () => {
  const b = await launchBrowser(); const page = await b.newPage(); page.on('dialog', d => d.accept());
  const out = {};
  for (const [name, url, click] of pages) {
    out[name] = {};
    for (const [w, h] of [[1440, 900], [390, 844]]) {
      await page.setViewportSize({ width: w, height: h }); await page.goto('about:blank'); await page.goto(url, { waitUntil: 'load' }); await sleep(3000);
      if (click) { await page.evaluate(sel => { const el = document.querySelector(sel); if (el) el.click(); }, click); await sleep(1500); }
      out[name][w] = await page.evaluate(metric);
      console.log(label, name, w, JSON.stringify(out[name][w]));
    }
  }
  fs.writeFileSync(outJson, JSON.stringify(out, null, 1));
  await b.close();
})().catch(e => { console.error(e); process.exit(1); });
