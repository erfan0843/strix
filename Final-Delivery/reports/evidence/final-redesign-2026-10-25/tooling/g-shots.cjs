// G) Screenshots of every changed page at 1440×900, 390×844, 360×800 (owner session via preview proxy :8000).
// Usage: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<deps> NORA_REPO_UI=<nora-ui> NORA_E2E_IDS=<ids.json> node g-shots.cjs <outdir>
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const fs = require('fs'); const path = require('path');
const ids = JSON.parse(fs.readFileSync(process.env.NORA_E2E_IDS, 'utf8')); const O = 'http://127.0.0.1:8000'; const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = process.argv[2]; fs.mkdirSync(out, { recursive: true }); const rows = [];
const pages = [
  ['01-settings', '/admin.html#settings'], ['02-events-list', '/admin.html#events'],
  ['03-editor-1-main', '/admin.html#edit=' + ids.A + '&sec=main'], ['04-editor-2-when', '/admin.html#edit=' + ids.A + '&sec=when'],
  ['05-editor-3-reg', '/admin.html#edit=' + ids.A + '&sec=reg'], ['06-editor-4-notify', '/admin.html#edit=' + ids.A + '&sec=notify'], ['07-editor-5-review', '/admin.html#edit=' + ids.A + '&sec=review'],
  ['08-event-hub', '/admin.html#event=' + ids.A], ['09-hub-forms', '/admin.html#event=' + ids.A + '&tab=forms'], ['10-hub-regs', '/admin.html#event=' + ids.A + '&tab=regs'],
  ['11-hub-pay', '/admin.html#event=' + ids.A + '&tab=payments'], ['12-hub-comms', '/admin.html#event=' + ids.A + '&tab=resources'], ['13-hub-reports', '/admin.html#event=' + ids.A + '&tab=certs'],
  ['14-person-file', '/admin.html#event=' + ids.A + '&tab=regs', 'person'],
  ['15-builder-from-event', '/builder.html?fid=' + ids.regA + '&ev=' + ids.A + '&need=reg&back=' + encodeURIComponent('/admin.html#edit=' + ids.A + '&sec=reg')],
  ['16-public-events', '/events.html'], ['17-public-event', '/event.html?id=' + ids.A], ['18-home', '/home.html'],
];
(async () => { const b = await launchBrowser(); const page = await b.newPage(); page.on('dialog', d => d.accept());
  for (const [w, h] of [[1440, 900], [390, 844], [360, 800]]) {
    await page.setViewportSize({ width: w, height: h });
    for (const [k, u, extra] of pages) {
      await page.goto('about:blank'); await page.goto(O + u, { waitUntil: 'load' }); await sleep(k.startsWith('1[5678]') ? 3500 : 3000);
      if (extra === 'person') { const r = await page.$('[data-ef-person]'); if (r) { await r.click(); await sleep(1800); } }
      const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
      const f = `${k}-${w}.png`; await page.screenshot({ path: path.join(out, f), fullPage: false });
      rows.push(`${f}\t${u.replace(/\?.*$/, m => m.length > 60 ? m.slice(0, 60) + '…' : m)}\toverflow=${m.sw - m.cw}`); console.log(rows[rows.length - 1]);
    }
  }
  fs.writeFileSync(path.join(out, 'index.tsv'), rows.join('\n') + '\n'); await b.close(); })().catch(e => { console.error('ERR', e.stack || e.message); process.exit(1) });
