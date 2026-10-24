// Settings «تقویم» complaint + shared Jalali date components: real-browser checks (desktop 1440, mobile 390, dark theme).
// Usage: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<deps> NORA_REPO_UI=<nora-ui> NORA_E2E_IDS=<ids.json> node cal-after.cjs <outdir>
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const fs = require('fs'); const path = require('path');
const ids = JSON.parse(fs.readFileSync(process.env.NORA_E2E_IDS, 'utf8')); const O = 'http://127.0.0.1:8000'; const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = process.argv[2]; fs.mkdirSync(out, { recursive: true }); const R = [];
const check = (n, ok) => { R.push((ok ? 'PASS ' : 'FAIL ') + n); console.log((ok ? 'PASS ' : 'FAIL ') + n); };
const toEn = s => String(s).replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d));
(async () => { const b = await launchBrowser(); const page = await b.newPage(); const errs = []; page.on('pageerror', e => errs.push(e.message));
  const metrics = () => page.evaluate(() => { const sp = document.querySelector('[data-ct-row] .sp'); const row = document.querySelector('[data-ct-row]'); return { hash: location.hash, sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, spW: sp ? Math.round(sp.getBoundingClientRect().width) : null, rowH: row ? Math.round(row.getBoundingClientRect().height) : null, rows: document.querySelectorAll('[data-ct-row]').length }; });
  const dpBox = () => page.evaluate(() => { const d = document.querySelector('[data-ctdp-box]'); if (!d) return null; const r = d.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), right: Math.round(r.right), left: Math.round(r.left), days: d.querySelectorAll('[data-ctdp-day]').length, sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }; });
  // 1) settings tile → events list
  await page.setViewportSize({ width: 1440, height: 900 }); await page.goto(O + '/admin.html#settings', { waitUntil: 'load' }); await sleep(2500);
  await page.screenshot({ path: path.join(out, 'settings-desktop.png') });
  const tile = await page.$eval('[data-sset-tile="skdev"]', e => e.textContent.replace(/\s+/g, ' ').trim()); console.log('tile text:', tile);
  check('settings tile text no longer promises a separate «تقویم» page', !/تقویم،/.test(tile));
  await page.click('[data-sset-tile="skdev"]'); await sleep(2000); const m1 = await metrics(); console.log('after tile:', JSON.stringify(m1));
  check('settings tile «رویدادها و مطالب» lands on the events list (#events) without horizontal overflow', m1.hash === '#events' && m1.sw <= m1.cw + 2);
  check('events list row: title column is wide (≥ 220px), not squeezed under the action buttons', m1.spW != null && m1.spW >= 220);
  await page.screenshot({ path: path.join(out, 'events-list-desktop.png') });
  // 2) datepicker in the editor (desktop)
  await page.goto('about:blank'); await page.goto(O + '/admin.html#edit=' + ids.A + '&sec=main', { waitUntil: 'load' }); await sleep(3000);
  const m1b = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
  check('editor (desktop) has no horizontal overflow', m1b.sw <= m1b.cw + 2);
  const before = await page.$eval('#ctf_on', e => e.value);
  await page.click('[data-ctdp="on"]'); await sleep(500); const dp = await dpBox(); console.log('datepicker:', JSON.stringify(dp));
  check('editor Jalali datepicker opens with a month grid (≥ 28 days) and stays inside the viewport', !!dp && dp.days >= 28 && dp.left >= 0 && dp.right <= dp.cw && dp.sw <= dp.cw + 2);
  check('datepicker is compact on desktop (≤ 420px wide)', !!dp && dp.w <= 420);
  await page.screenshot({ path: path.join(out, 'editor-datepicker-desktop.png') });
  await page.click('[data-ctdp-day="15"]'); await sleep(400);
  const after = await page.$eval('#ctf_on', e => e.value); console.log('date before/after:', before, after);
  check('picking a day writes a Jalali YYYY/MM/DD into the start-date field and the weekday hint updates', /^\d{4}\/\d{2}\/\d{2}$/.test(toEn(after)) && /\/15$/.test(toEn(after)) && (await page.$eval('[data-ct-weekday="on"]', e => e.textContent.trim().length > 0)));
  check('datepicker closes after picking', !(await page.$('[data-ctdp-box]')));
  await page.click('[data-ctdp="on"]'); await sleep(300); await page.click('[data-ctdp-mv="1"]'); await sleep(300);
  const monthTxt = await page.$eval('[data-ctdp-box] .dphead b', e => e.textContent.trim()); console.log('after next month:', monthTxt);
  check('month navigation changes the header month', monthTxt.length > 0);
  await page.click('[data-ctdp-today]'); await sleep(300);
  const todayVal = toEn(await page.$eval('#ctf_on', e => e.value)); console.log('today value:', todayVal);
  check('«امروز» writes today’s Jalali date', /^\d{4}\/\d{2}\/\d{2}$/.test(todayVal));
  // 3) time field: 24h, no rewrite mid-typing
  await page.fill('#ctf_time', ''); await page.type('#ctf_time', '1', { delay: 40 }); const mid = await page.$eval('#ctf_time', e => e.value);
  await page.type('#ctf_time', '830', { delay: 40 }); await page.$eval('#ctf_time', e => e.blur()); await sleep(300); const tval = toEn(await page.$eval('#ctf_time', e => e.value));
  console.log('time typing mid/final:', mid, tval);
  check('time input is not rewritten mid-typing and normalises to HH:MM on blur', toEn(mid) === '1' && tval === '18:30');
  // 4) mobile
  await page.goto('about:blank'); await page.setViewportSize({ width: 390, height: 844 }); await page.goto(O + '/admin.html#events', { waitUntil: 'load' }); await sleep(2500);
  const m2 = await metrics(); console.log('mobile events:', JSON.stringify(m2));
  check('mobile events list: no horizontal overflow', m2.sw <= m2.cw + 2);
  await page.screenshot({ path: path.join(out, 'events-list-mobile-390.png') });
  await page.goto('about:blank'); await page.goto(O + '/admin.html#edit=' + ids.A + '&sec=main', { waitUntil: 'load' }); await sleep(3000);
  const m3 = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
  check('editor (390px) has no horizontal overflow before opening the calendar', m3.sw <= m3.cw + 2);
  await page.click('[data-ctdp="on"]'); await sleep(500); const dpm = await dpBox(); console.log('mobile datepicker:', JSON.stringify(dpm));
  check('mobile datepicker stays inside the 390px viewport', !!dpm && dpm.left >= 0 && dpm.right <= dpm.cw && dpm.sw <= dpm.cw + 2);
  check('mobile day cells are touch-sized (≥ 40px)', await page.$eval('[data-ctdp-day="15"]', e => e.getBoundingClientRect().height >= 40));
  await page.screenshot({ path: path.join(out, 'editor-datepicker-mobile-390.png') });
  await page.keyboard.press('Escape'); await sleep(300); check('Escape closes the datepicker', !(await page.$('[data-ctdp-box]')));
  await page.evaluate(() => { try { themeToggle() } catch (e) { } }); await sleep(600); await page.click('[data-ctdp="on"]'); await sleep(500);
  await page.screenshot({ path: path.join(out, 'editor-datepicker-mobile-dark.png') });
  const dark = await dpBox(); check('dark theme: datepicker still inside the viewport', !!dark && dark.right <= dark.cw && dark.sw <= dark.cw + 2);
  await page.goto('about:blank'); await page.setViewportSize({ width: 360, height: 800 }); await page.goto(O + '/admin.html#edit=' + ids.A + '&sec=main', { waitUntil: 'load' }); await sleep(3000);
  await page.click('[data-ctdp="on"]'); await sleep(500); const d360 = await dpBox(); console.log('360 datepicker:', JSON.stringify(d360));
  check('360px: editor + datepicker without horizontal overflow', !!d360 && d360.right <= d360.cw && d360.sw <= d360.cw + 2);
  await page.screenshot({ path: path.join(out, 'editor-datepicker-mobile-360.png') });
  check('no page errors', errs.length === 0); console.log('errors', JSON.stringify(errs));
  const fails = R.filter(x => x.startsWith('FAIL')).length; console.log('TOTAL PASS ' + (R.length - fails) + ' / FAIL ' + fails);
  fs.writeFileSync(path.join(out, 'log.txt'), R.join('\n') + '\n');
  await b.close(); })().catch(e => { console.error('ERR', e.message); process.exit(1) });
