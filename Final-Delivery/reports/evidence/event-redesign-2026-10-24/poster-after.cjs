// Poster A4 (210:297) audit: upload in the event editor → preview → save → event file → public list → event page → home; 1440 / 390 / 360.
// Usage: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<deps> NORA_REPO_UI=<nora-ui> NORA_E2E_IDS=<ids.json> node poster-after.cjs <outdir>
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const fs = require('fs'); const path = require('path');
const ids = JSON.parse(fs.readFileSync(process.env.NORA_E2E_IDS, 'utf8')); const O = 'http://127.0.0.1:8000'; const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = process.argv[2]; fs.mkdirSync(out, { recursive: true }); const R = []; const A4 = 210 / 297;
const check = (n, ok) => { R.push((ok ? 'PASS ' : 'FAIL ') + n); console.log((ok ? 'PASS ' : 'FAIL ') + n); };
const near = (a, b, tol) => Math.abs(a - b) <= tol;
// geometry of an <img>: box, natural ratio, computed object-fit, drawn (contained) rect, and whether any text pill overlaps the drawn rect
const imgInfo = (page, sel, pills) => page.evaluate(([sel, pills]) => {
  const img = document.querySelector(sel); if (!img) return null; const r = img.getBoundingClientRect();
  const nw = img.naturalWidth, nh = img.naturalHeight, fit = getComputedStyle(img).objectFit;
  const s = Math.min(r.width / nw, r.height / nh); const dw = nw * s, dh = nh * s; const dx = r.left + (r.width - dw) / 2, dy = r.top + (r.height - dh) / 2;
  const drawn = { left: dx, top: dy, right: dx + dw, bottom: dy + dh, w: Math.round(dw), h: Math.round(dh) };
  const overlaps = []; (pills || []).forEach(ps => document.querySelectorAll(ps).forEach(el => { const b = el.getBoundingClientRect(); if (!b.width) return; const hit = b.left < drawn.right - 1 && b.right > drawn.left + 1 && b.top < drawn.bottom - 1 && b.bottom > drawn.top + 1; if (hit) overlaps.push(ps + ':' + el.textContent.trim().slice(0, 20)); }));
  return { box: { w: Math.round(r.width), h: Math.round(r.height) }, natural: nw && nh ? +(nw / nh).toFixed(3) : null, fit, drawn, cropped: fit === 'cover' && Math.abs(r.width / r.height - nw / nh) > 0.02, overlaps, sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, complete: img.complete && nw > 0 };
}, [sel, pills]);
(async () => { const b = await launchBrowser(); const page = await b.newPage(); const errs = []; page.on('pageerror', e => errs.push(e.message)); page.on('dialog', d => d.accept());
  await page.setViewportSize({ width: 1440, height: 900 });
  // 1) editor: placeholder → upload → A4 frame → save
  await page.goto(O + '/admin.html#edit=' + ids.A + '&sec=main', { waitUntil: 'load' }); await sleep(3000);
  const ph = await page.$('[data-ct-poster-frame]'); const phState = ph ? await ph.getAttribute('data-ct-poster-frame') : null; const phTxt = ph ? await ph.evaluate(e => e.textContent.trim()) : '';
  console.log('placeholder:', phState, phTxt);
  check('editor shows an A4 poster frame; empty state is an explicit placeholder («پوستر عمودی A4»)', !!ph && (phState === 'image' || /A4/.test(phTxt)));
  const frame = await page.$eval('[data-ct-poster-frame]', e => { const r = e.getBoundingClientRect(); return { w: r.width, h: r.height }; });
  check('frame ratio is 210:297 (A4 portrait)', near(frame.w / frame.h, A4, 0.02));
  await page.setInputFiles('input[data-ct-image="poster"]', '<local>/poster-a4.png');
  let upOk = false; for (let i = 0; i < 40; i++) { await sleep(500); const st = await page.evaluate(() => ({ busy: !!document.querySelector('[data-ct-image-state="busy"]'), err: (document.querySelector('[data-ct-image-state="error"]') || {}).textContent || '', src: (document.querySelector('[data-ct-poster-frame] img') || {}).getAttribute ? (document.querySelector('[data-ct-poster-frame] img') || { getAttribute: () => '' }).getAttribute('src') : '' })); if (st.err) { console.log('upload error', st.err); break; } if (!st.busy && st.src && st.src.startsWith('/api/public/media/')) { upOk = true; break; } }
  check('poster upload goes to the server and the frame shows the stored media URL (no data: / temp URL)', upOk);
  await sleep(600); const ed = await imgInfo(page, '[data-ct-poster-frame] img', []); console.log('editor img:', JSON.stringify(ed));
  check('editor poster is object-fit: contain and drawn fully inside the frame (no crop)', !!ed && ed.fit === 'contain' && near(ed.natural, A4, 0.01) && ed.drawn.h <= ed.box.h + 1 && ed.drawn.w <= ed.box.w + 1 && near(ed.drawn.w / ed.drawn.h, A4, 0.02));
  await page.screenshot({ path: path.join(out, 'editor-poster-desktop.png') });
  await page.click('[data-ct-preview-toggle]'); await sleep(900);
  const pvOpen = await page.$('[data-ct-review-card]:not([hidden])'); if (!pvOpen) { const t = await page.$('[data-ct-preview-toggle]'); if (t) { await t.click(); await sleep(600); } }
  const pv = await imgInfo(page, '#ctPreview img', []); console.log('preview img:', JSON.stringify(pv));
  check('review-step card preview shows the poster fully (contain) before saving', !!pv && pv.fit === 'contain' && near(pv.drawn.w / pv.drawn.h, A4, 0.03));
  await page.screenshot({ path: path.join(out, 'editor-review-preview.png') });
  const verOf = () => page.evaluate(() => { const m = (document.querySelector('[data-ct-editor] .row') || {}).textContent || ''; const x = m.match(/نسخهٔ\s*([۰-۹0-9]+)/); return x ? x[1].replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)) : null; });
  const ver0 = await verOf();
  await page.click('[data-ct-save]'); let saved = false; for (let i = 0; i < 30; i++) { await sleep(500); const v = await verOf(); const busy = await page.evaluate(() => !!document.querySelector('[data-ct-save][disabled]')); const h = await page.evaluate(() => location.hash); if (!busy && ((v != null && v !== ver0) || !/^#edit=/.test(h))) { saved = true; console.log('after save hash:', h); break; } }
  console.log('version before/after:', ver0, await verOf());
  check('save succeeds (server version increments or editor closes to the list)', saved);
  await page.goto('about:blank'); await page.goto(O + '/admin.html#edit=' + ids.A + '&sec=main', { waitUntil: 'load' }); await sleep(3000);
  const re = await page.evaluate(() => (document.querySelector('[data-ct-poster-frame] img') || { getAttribute: () => '' }).getAttribute('src') || '');
  check('poster persists after reopening the editor (server-stored URL)', re.startsWith('/api/public/media/'));
  // 2) event file head
  await page.goto('about:blank'); await page.goto(O + '/admin.html#event=' + ids.A, { waitUntil: 'load' }); await sleep(3000);
  const ef = await imgInfo(page, '[data-ef-poster] img', []); console.log('event-file img:', JSON.stringify(ef));
  check('event file header thumbnail keeps the A4 ratio and is not cropped', !!ef && ef.fit === 'contain' && near(ef.box.w / ef.box.h, A4, 0.03));
  await page.screenshot({ path: path.join(out, 'event-file-poster.png') });
  // 3) public events list
  const PILLS = ['.event-list-cover .cover-kind', '.event-list-cover .cover-state', '.event-list-cover .cover-date'];
  for (const vp of [[1440, 900], [390, 844], [360, 800]]) {
    await page.goto('about:blank'); await page.setViewportSize({ width: vp[0], height: vp[1] }); await page.goto(O + '/events.html', { waitUntil: 'load' }); await sleep(3500);
    const sel = `[data-event-id="${ids.A}"] .event-list-cover.has-poster img`; await page.evaluate(s => { const el = document.querySelector(s); if (el) el.scrollIntoView({ block: 'center' }); }, sel); await sleep(300);
    const li = await imgInfo(page, sel, [`[data-event-id="${ids.A}"] .cover-kind`, `[data-event-id="${ids.A}"] .cover-state`, `[data-event-id="${ids.A}"] .cover-date`]); console.log('list ' + vp[0] + ':', JSON.stringify(li));
    check(`public events list @${vp[0]}: poster card uses contain, full poster visible, no text over the poster, no horizontal overflow`, !!li && li.complete && li.fit === 'contain' && near(li.drawn.w / li.drawn.h, A4, 0.03) && li.overlaps.length === 0 && li.sw <= li.cw + 2);
    const heights = await page.$$eval('.event-list-cover img', els => els.map(e => Math.round(e.getBoundingClientRect().height)));
    check(`public events list @${vp[0]}: every poster card has the same fixed image height (${heights.join(',')})`, heights.length > 0 && new Set(heights).size === 1);
    await page.screenshot({ path: path.join(out, `events-list-${vp[0]}.png`) });
    // 4) event page hero
    await page.goto('about:blank'); await page.goto(O + '/event.html?id=' + ids.A, { waitUntil: 'load' }); await sleep(3500);
    const hero = await imgInfo(page, '.event-cover-image', []); console.log('hero ' + vp[0] + ':', JSON.stringify(hero));
    check(`event page @${vp[0]}: hero poster is contained (full A4 visible) without overflow`, !!hero && hero.complete && hero.fit === 'contain' && near(hero.drawn.w / hero.drawn.h, A4, 0.03) && hero.sw <= hero.cw + 2);
    await page.screenshot({ path: path.join(out, `event-page-${vp[0]}.png`) });
    // 5) home cards
    await page.goto('about:blank'); await page.goto(O + '/home.html', { waitUntil: 'load' }); await sleep(4000);
    const hsel = `.evc-cov[data-ev="${ids.A}"] img, a.evc-cov[href*="${ids.A}"] img`;
    await page.evaluate(s => { const el = document.querySelector(s); if (el) el.scrollIntoView({ block: 'center' }); }, hsel); await sleep(300);
    const hm = await imgInfo(page, hsel, ['.evc-cov:has(>img) .evc-tag', '.evc-cov:has(>img) .evc-day']); console.log('home ' + vp[0] + ':', JSON.stringify(hm));
    check(`home @${vp[0]}: event card poster contained, tags not over the poster, no overflow`, !!hm && hm.complete && hm.fit === 'contain' && near(hm.drawn.w / hm.drawn.h, A4, 0.03) && hm.overlaps.length === 0 && hm.sw <= hm.cw + 2);
    await page.screenshot({ path: path.join(out, `home-${vp[0]}.png`) });
  }
  check('no page errors', errs.length === 0); console.log('errors', JSON.stringify(errs.slice(0, 5)));
  const fails = R.filter(x => x.startsWith('FAIL')).length; console.log('TOTAL PASS ' + (R.length - fails) + ' / FAIL ' + fails);
  fs.writeFileSync(path.join(out, 'log.txt'), R.join('\n') + '\n'); await b.close(); })().catch(e => { console.error('ERR', e.stack || e.message); process.exit(1) });
