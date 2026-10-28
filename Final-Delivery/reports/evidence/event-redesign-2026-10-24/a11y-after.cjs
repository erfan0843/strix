// Accessibility/wording audit of the touched pages: controls without an accessible name, images without alt, unlabeled inputs,
// raw ids shown as text, tiny touch targets at 390px, heading per sub-page, focus visibility of primary actions.
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const fs = require('fs'); const path = require('path');
const ids = JSON.parse(fs.readFileSync(process.env.NORA_E2E_IDS, 'utf8')); const O = 'http://127.0.0.1:8000'; const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = process.argv[2]; fs.mkdirSync(out, { recursive: true }); const R = []; const details = {};
const check = (n, ok) => { R.push((ok ? 'PASS ' : 'FAIL ') + n); console.log((ok ? 'PASS ' : 'FAIL ') + n); };
const audit = page => page.evaluate(() => {
  const vis = el => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); if (el.closest('details:not([open]) > :not(summary)')) return false; return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const name = el => (el.getAttribute('aria-label') || (el.getAttribute('aria-labelledby') && (document.getElementById(el.getAttribute('aria-labelledby')) || {}).textContent) || el.getAttribute('title') || el.textContent || '').replace(/\s+/g, ' ').trim();
  const ctrls = [...document.querySelectorAll('button, a[href], [role="button"], [role="tab"]')].filter(vis);
  const unnamed = ctrls.filter(el => !name(el) && !el.querySelector('img[alt]:not([alt=""])')).map(el => el.outerHTML.slice(0, 90));
  const imgs = [...document.querySelectorAll('img')].filter(vis).filter(i => !i.hasAttribute('alt')).map(i => i.outerHTML.slice(0, 80));
  const inputs = [...document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=file]), select, textarea')].filter(vis).filter(el => { if (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.getAttribute('placeholder') || el.getAttribute('title')) return false; if (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)) return false; return !el.closest('label'); }).map(el => el.outerHTML.slice(0, 90));
  const small = ctrls.filter(el => { const r = el.getBoundingClientRect(); return (r.width < 32 || r.height < 32) && !el.closest('.ctsteps,.dpgrid,.dpweek'); }).map(el => Math.round(el.getBoundingClientRect().width) + 'x' + Math.round(el.getBoundingClientRect().height) + ' ' + (name(el) || el.outerHTML.slice(0, 40)));
  const main = document.querySelector('[data-ct-editor], [data-ef-hub], [data-ef-group], #admMain, main') || document.body;
  const txt = main.innerText || '';
  const rawIds = [...new Set((txt.match(/\b(?:ev|fm|frm|rsp)-[0-9a-f]{8,}\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi) || []))];
  const dashes = (txt.match(/ — /g) || []).length;
  const h = [...document.querySelectorAll('h1,h2,.head')].filter(vis).map(e => e.textContent.trim()).slice(0, 4);
  return { controls: ctrls.length, unnamed, imgs, inputs, small, rawIds, dashes, headings: h, overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth };
});
(async () => { const b = await launchBrowser(); const page = await b.newPage(); const errs = []; page.on('pageerror', e => errs.push(e.message));
  const pages = [
    ['events-list', '/admin.html#events'], ['editor-main', '/admin.html#edit=' + ids.A + '&sec=main'], ['editor-when', '/admin.html#edit=' + ids.A + '&sec=when'],
    ['editor-reg', '/admin.html#edit=' + ids.A + '&sec=reg'], ['editor-notify', '/admin.html#edit=' + ids.A + '&sec=notify'], ['editor-review', '/admin.html#edit=' + ids.A + '&sec=review'],
    ['event-hub', '/admin.html#event=' + ids.A], ['event-forms', '/admin.html#event=' + ids.A + '&tab=forms'], ['event-regs', '/admin.html#event=' + ids.A + '&tab=regs'],
    ['event-pay', '/admin.html#event=' + ids.A + '&tab=payments'], ['event-comms', '/admin.html#event=' + ids.A + '&tab=resources'], ['event-reports', '/admin.html#event=' + ids.A + '&tab=certs'],
    ['builder-from-event', '/builder.html?fid=' + ids.regA + '&ev=' + ids.A + '&need=reg&back=' + encodeURIComponent('/admin.html#edit=' + ids.A + '&sec=reg')],
    ['public-events', '/events.html'], ['public-event', '/event.html?id=' + ids.A],
  ];
  for (const vp of [[1440, 900], [390, 844]]) {
    await page.setViewportSize({ width: vp[0], height: vp[1] });
    for (const [k, u] of pages) {
      await page.goto('about:blank'); await page.goto(O + u, { waitUntil: 'load' }); await sleep(k.startsWith('public') || k.startsWith('builder') ? 3500 : 3000);
      if (k === 'event-regs') { const r = await page.$('[data-ef-person]'); if (r) { await r.click(); await sleep(1500); } }
      const a = await audit(page); details[k + '@' + vp[0]] = a;
      const okAll = a.unnamed.length === 0 && a.imgs.length === 0 && a.inputs.length === 0 && a.overflow <= 2 && a.dashes === 0;
      check(`${k} @${vp[0]}: ${a.controls} controls — ${a.unnamed.length} unnamed, ${a.imgs.length} img w/o alt, ${a.inputs.length} unlabeled inputs, overflow ${a.overflow}px, raw ids ${a.rawIds.length}, small targets ${a.small.length}`, okAll);
      if (!okAll || a.rawIds.length || a.small.length) console.log('   ', JSON.stringify({ unnamed: a.unnamed.slice(0, 6), imgs: a.imgs.slice(0, 3), inputs: a.inputs.slice(0, 4), rawIds: a.rawIds.slice(0, 5), small: a.small.slice(0, 8) }));
    }
  }
  check('no page errors', errs.length === 0); console.log('errors', JSON.stringify(errs.slice(0, 5)));
  const fails = R.filter(x => x.startsWith('FAIL')).length; console.log('TOTAL PASS ' + (R.length - fails) + ' / FAIL ' + fails);
  fs.writeFileSync(path.join(out, 'log.txt'), R.join('\n') + '\n'); fs.writeFileSync(path.join(out, 'details.json'), JSON.stringify(details, null, 1)); await b.close(); })().catch(e => { console.error('ERR', e.stack || e.message); process.exit(1) });
