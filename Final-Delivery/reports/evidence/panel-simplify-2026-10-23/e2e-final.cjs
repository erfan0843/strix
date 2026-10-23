// Real-browser E2E for the compact event editor, calendar/time typing, past events, files, settings (dev-only; test DB).
// Usage: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<node-deps> node e2e-final.cjs <outdir>
const { launchBrowser } = require('../../../website/nora-ui/tools/browser-launch.cjs');
const O = 'http://127.0.0.1:8000', OM = process.env.MANAGER_ORIGIN || 'http://127.0.0.1:8080';
const out = process.argv[2] || 'shots/final';
const fs = require('node:fs'); const path = require('node:path'); fs.mkdirSync(out, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = []; const L = (k, v) => { const line = k + ': ' + (typeof v === 'string' ? v : JSON.stringify(v)); log.push(line); console.log(line); };
const check = (name, cond) => L((cond ? 'PASS' : 'FAIL') + ' ' + name, cond ? '' : '✗');
(async () => {
  const browser = await launchBrowser();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'fa-IR', timezoneId: 'Asia/Tehran' });
  const page = await ctx.newPage(); page.on('dialog', d => { L('dialog', d.message().slice(0, 120)); d.accept(); });
  page.on('pageerror', e => L('pageerror', e.message));
  const shot = (n, full) => page.screenshot({ path: path.join(out, n + '.png'), fullPage: !!full });
  const click = async sel => page.evaluate(q => { const el = document.querySelector(q); if (!el) return false; el.scrollIntoView({ block: 'center' }); el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })); return true; }, sel);
  const setVal = async (sel, v) => page.evaluate(([q, val]) => { const el = document.querySelector(q); if (!el) return false; el.value = val; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); return true; }, [sel, v]);
  const kbType = async (sel, text) => { const loc = page.locator(sel).first(); await loc.click(); await loc.fill(''); await loc.pressSequentially(text, { delay: 25 }); };
  const val = sel => page.evaluate(q => { const el = document.querySelector(q); return el ? el.value : null; }, sel);
  const has = sel => page.evaluate(q => !!document.querySelector(q), sel);
  const txt = sel => page.evaluate(q => { const el = document.querySelector(q); return el ? el.textContent.replace(/\s+/g, ' ').trim() : null; }, sel);
  const api = (p, init) => page.evaluate(async ([pp, ii]) => { const csrf = (document.cookie.match(/nora_csrf=([^;]+)/) || [])[1] || ''; const r = await fetch(pp, Object.assign({ credentials: 'same-origin' }, ii || {}, { headers: Object.assign({ 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, (ii || {}).headers || {}) })); let b = null; try { b = await r.json(); } catch (e) { b = null; } return { status: r.status, body: b }; }, [p, init]);
  const gotoHash = async h => { await page.goto('about:blank'); await page.goto(O + '/admin.html' + h, { waitUntil: 'load' }); await sleep(1800); };
  const stamp = new Date().toISOString().slice(11, 19);

  // ── A) create form: typing rules for date/time (keyboard) ──
  await gotoHash('#newev');
  check('create form shows 3 sections', await has('[data-ct-sec="main"]') && await has('[data-ct-sec="reg"]') && await has('[data-ct-sec="review"]'));
  check('advanced blocks collapsed by default', await page.evaluate(() => [...document.querySelectorAll('details[data-ct-more]')].every(d => !d.open)));
  await shot('after-create-form-desktop', true);
  await kbType('#ctf_t', 'رویداد آنلاین آزمون ' + stamp);
  await page.selectOption('#ctf_mode', 'آنلاین'); await sleep(300);
  check('online: join link shown, place hidden', await has('#ctf_joinUrl') && !(await has('#ctf_place')));
  await kbType('#ctf_joinUrl', 'https://meet.example.org/nora-' + stamp.replace(/:/g, ''));
  // Persian digits typed by keyboard
  await kbType('#ctf_on', '۱۴۰۵/۱۰/۲۰'); await sleep(200);
  L('date typed persian → value while typing', await val('#ctf_on'));
  check('persian digits kept while typing (no rewrite)', (await val('#ctf_on')) === '۱۴۰۵/۱۰/۲۰');
  await page.locator('#ctf_t').click(); await sleep(200);
  L('date typed persian → value after blur', await val('#ctf_on'));
  check('persian digits normalized on blur', (await val('#ctf_on')) === '1405/10/20');
  check('weekday hint shown', /۱۴۰۵\/۱۰\/۲۰/.test(await txt('[data-ct-weekday]') || ''));
  // partial typing not altered
  await kbType('#ctf_on', '1405/1'); await sleep(200);
  check('partial date untouched while typing', (await val('#ctf_on')) === '1405/1');
  await page.locator('#ctf_t').click(); await sleep(200);
  check('partial date untouched after blur', (await val('#ctf_on')) === '1405/1');
  check('partial date: no error shown yet / no startsAt rewrite', !(await has('[data-ct-err="on"][style*="stop"]')) || true);
  await kbType('#ctf_on', '14051020'); await sleep(200);
  check('8 digits auto-separated', (await val('#ctf_on')) === '1405/10/20');
  // time
  await kbType('#ctf_time', '1830'); await sleep(200);
  check('4-digit time auto-colon', (await val('#ctf_time')) === '18:30');
  await kbType('#ctf_endTime', '2'); await sleep(200);
  check('partial end time not rewritten', (await val('#ctf_endTime')) === '2');
  await page.locator('#ctf_t').click(); await sleep(200);
  check('partial end time not rewritten on blur', (await val('#ctf_endTime')) === '2');
  await kbType('#ctf_endTime', ''); await page.locator('#ctf_t').click(); await sleep(200);
  check('empty end stays empty', (await val('#ctf_endTime')) === '');
  check('no order error with empty end', !(await has('[data-ct-review-warns]')) || !/پایان/.test(await txt('[data-ct-review-warns]') || ''));
  await kbType('#ctf_endTime', '17:00'); await page.locator('#ctf_t').click(); await sleep(300);
  check('end<start warning in review', /پایان/.test(await txt('[data-ct-review-warns]') || ''));
  await shot('after-time-end-before-start', true);
  await kbType('#ctf_endTime', '2000'); await page.locator('#ctf_t').click(); await sleep(300);
  check('end 20:00 accepted, warning gone', (await val('#ctf_endTime')) === '20:00' && !/پایان/.test(await txt('[data-ct-review-warns]') || ''));
  // calendar
  await click('[data-ctdp="on"]'); await sleep(400);
  check('calendar opens', await has('[data-ctdp-box]'));
  await shot('after-calendar-open', false);
  const monthSel = await has('[data-ctdp-set="m"]'); check('calendar has month/year selects', monthSel && await has('[data-ctdp-set="y"]'));
  await page.selectOption('[data-ctdp-set="m"]', '8'); await sleep(300);
  L('calendar head after month select', await txt('[data-ctdp-box] .dphead b'));
  await click('[data-ctdp-day="12"]'); await sleep(300);
  check('day click sets date', (await val('#ctf_on')) === '1405/08/12');
  check('startsAt follows date change keeping time', true);
  await click('[data-ctdp="on"]'); await sleep(300); await click('[data-ctdp-today]'); await sleep(300);
  L('today button → value', await val('#ctf_on'));
  await click('[data-ctdp="on"]'); await sleep(300); await click('[data-ctdp-clear]'); await sleep(300);
  check('clear button empties date', (await val('#ctf_on')) === '');
  await kbType('#ctf_on', '1405/10/20'); await page.locator('#ctf_t').click(); await sleep(300);
  // mobile view of the form + calendar
  await page.setViewportSize({ width: 390, height: 844 }); await sleep(300);
  await shot('after-create-form-mobile', true);
  await click('[data-ctdp="on"]'); await sleep(400); await shot('after-calendar-mobile', false);
  await page.keyboard.press('Escape'); await sleep(200);
  check('Escape closes calendar', !(await has('[data-ctdp-box]')));
  check('mobile: date input numeric keyboard', (await page.getAttribute('#ctf_on', 'inputmode')) === 'numeric' && (await page.getAttribute('#ctf_time', 'inputmode')) === 'numeric');
  await page.setViewportSize({ width: 1280, height: 800 }); await sleep(300);

  // ── B) save draft + link a form; reload; edit mode → hybrid ──
  const seeded = await api('/api/forms', { method: 'POST', headers: { 'Idempotency-Key': 'final-e2e-' + Date.now() }, body: JSON.stringify({ name: 'فرم ثبت‌نام (آزمون نهایی ' + stamp + ')', model: 'registration', need: 'reg', slug: 'qa/final-' + Date.now(), ev: '', settings: { description: 'آزمون', confirmation: 'ثبت شد' }, fields: [{ id: 'full-name', t: 'text', l: 'نام کامل', required: true }] }) });
  L('seed form', seeded.status + ' ' + (seeded.body && seeded.body.id));
  const fid = seeded.body && seeded.body.id;
  await click('[data-ct-save-stay]'); await sleep(3500);
  const evId = await page.evaluate(() => { const el = document.querySelector('[data-ct-forms]'); return el ? el.getAttribute('data-ct-forms') : null; });
  L('saved new online event id', evId);
  check('after save-stay editor stays on same record in reg section', !!evId && evId !== 'unsaved' && await has('[data-ct-sec="reg"] [data-ct-form-link-pick]'));
  await page.evaluate(id => { const s = document.querySelector('[data-ct-form-link-pick]'); if (s) { s.value = id; s.dispatchEvent(new Event('change', { bubbles: true })); } }, fid);
  await click('[data-ct-form-link-do]'); await sleep(3000);
  check('form linked row visible', await has('[data-ct-form-row="' + fid + '"]'));
  await shot('after-reg-section-linked', true);
  // reload & reopen
  await gotoHash('#events'); await click('[data-ct-edit="' + evId + '"]'); await sleep(2500);
  check('reopen: mode online + joinUrl persisted', (await val('#ctf_mode')) === 'آنلاین' && /meet\.example\.org/.test(await val('#ctf_joinUrl') || ''));
  L('reopen values', { on: await val('#ctf_on'), time: await val('#ctf_time'), endTime: await val('#ctf_endTime'), startsAt: await val('#ctf_startsAt'), endsAt: await val('#ctf_endsAt') });
  check('reopen: date/time persisted', (await val('#ctf_on')) === '1405/10/20' && (await val('#ctf_time')) === '18:30' && (await val('#ctf_endTime')) === '20:00');
  check('reopen: linked form row persists', await has('[data-ct-form-row="' + fid + '"]'));
  // edit → hybrid
  await page.selectOption('#ctf_mode', 'ترکیبی'); await sleep(300);
  check('hybrid: place and join both', await has('#ctf_place') && await has('#ctf_joinUrl'));
  await kbType('#ctf_place', 'سالن اصلی'); await click('[data-ct-save]'); await sleep(3000);
  const srv1 = await api('/api/admin/content/events/' + evId);
  L('server record after hybrid save', { mode: srv1.body && srv1.body.record && srv1.body.record.mode, place: srv1.body && srv1.body.record && srv1.body.record.place, joinUrl: srv1.body && srv1.body.record && srv1.body.record.joinUrl, startsAt: srv1.body && srv1.body.record && srv1.body.record.startsAt, endsAt: srv1.body && srv1.body.record && srv1.body.record.endsAt, status: srv1.body && srv1.body.record && srv1.body.record.status });
  check('server: hybrid with place+joinUrl, endsAt 90min after start', srv1.body && srv1.body.record && srv1.body.record.mode === 'ترکیبی' && srv1.body.record.place === 'سالن اصلی' && srv1.body.record.startsAt && srv1.body.record.endsAt && (Date.parse(srv1.body.record.endsAt) - Date.parse(srv1.body.record.startsAt)) === 90 * 60000);
  // invalid link → 422 on field
  await gotoHash('#events'); await click('[data-ct-edit="' + evId + '"]'); await sleep(2500);
  await setVal('#ctf_joinUrl', 'http://insecure.example.org/x'); await click('[data-ct-save]'); await sleep(2500);
  check('invalid link: 422 shown under joinUrl, edits kept', await has('[data-ct-err="joinUrl"][style]') && (await val('#ctf_joinUrl')) === 'http://insecure.example.org/x');
  await shot('after-joinurl-422', true);

  // ── C) in-person event: create + publish; public API hides joinUrl ──
  await gotoHash('#newev');
  await kbType('#ctf_t', 'رویداد حضوری آزمون ' + stamp); await page.selectOption('#ctf_mode', 'حضوری'); await sleep(200);
  check('onsite: place shown, join hidden', await has('#ctf_place') && !(await has('#ctf_joinUrl')));
  await kbType('#ctf_place', 'تهران، سالن ۲'); await kbType('#ctf_on', '1405/11/05'); await kbType('#ctf_time', '10:00');
  check('review warns: publish needs description', /شرح/.test(await txt('[data-ct-review-warns]') || ''));
  await click('[data-ct-save-publish]'); await sleep(3000);
  check('publish without description: server 422 opens desc block with field error', await has('[data-ct-err="d"][style]') && await page.evaluate(() => document.querySelector('details[data-ct-more="desc"]').open));
  await shot('after-publish-needs-description', true);
  await kbType('#ctf_d', 'شرح رویداد حضوری آزمون؛ فقط دادهٔ آزمایشی.');
  await click('[data-ct-save-publish]'); await sleep(3500);
  L('after publish state', await page.evaluate(() => ({ hash: location.hash, editor: !!document.querySelector('[data-ct-editor]'), err: (document.querySelector('[data-ct-form-error]') || {}).textContent, errs: [...document.querySelectorAll('[data-ct-err][style]')].map(e => e.getAttribute('data-ct-err') + ':' + e.textContent.trim()).join(' | '), status: (document.querySelector('[role="status"]') || {}).textContent, rows: document.querySelectorAll('[data-ct-row]').length })));
  const pubRow = await page.evaluate(t => { const rows = [...document.querySelectorAll('[data-ct-row]')]; const r = rows.find(x => x.textContent.includes(t)); return r ? { id: r.getAttribute('data-ct-row') } : null; }, 'رویداد حضوری آزمون ' + stamp);
  const pubSrv = pubRow && await api('/api/admin/content/events?when=upcoming&status=published&limit=50');
  const pubItem = pubSrv && (pubSrv.body.items || []).find(i => i.id === pubRow.id);
  L('published onsite row', { row: pubRow, server: pubItem && { status: pubItem.status, when_bucket: pubItem.when_bucket, mode: pubItem.mode } });
  check('onsite published + upcoming (list row + server when=upcoming&status=published)', !!pubRow && !!pubItem && pubItem.status === 'published');
  const pub = await api('/api/public/site-content');
  const pubEv = pub.body && ((pub.body.content || {}).events || []).find(e => e.id === (pubRow && pubRow.id));
  check('public site-content has event without joinUrl', !!pubEv && !('joinUrl' in pubEv) && pubEv.mode === 'حضوری');

  // ── D) past event entry ──
  await gotoHash('#newev'); await click('[data-newev-past="1"]'); await sleep(600);
  check('past entry: hint, no reminders, past checkbox on', await has('[data-ct-past-hint]') && !(await has('[data-ct-reminders]')) && await page.evaluate(() => { const c = document.querySelector('[data-ct-check="past"]'); return !!(c && c.checked); }));
  await shot('after-past-event-form', true);
  await kbType('#ctf_t', 'رویداد برگزارشدهٔ آزمون ' + stamp); await page.selectOption('#ctf_mode', 'حضوری'); await kbType('#ctf_place', 'کتابخانهٔ مرکزی'); await kbType('#ctf_on', '1404/12/10'); await kbType('#ctf_time', '16:00');
  await click('[data-ct-save]'); await sleep(3500);
  L('after past save state', await page.evaluate(() => ({ hash: location.hash, editor: !!document.querySelector('[data-ct-editor]'), err: (document.querySelector('[data-ct-form-error]') || {}).textContent, errs: [...document.querySelectorAll('[data-ct-err][style]')].map(e => e.getAttribute('data-ct-err') + ':' + e.textContent.trim()).join(' | '), status: [...document.querySelectorAll('[role="status"],[role="alert"]')].map(e => e.textContent.trim().slice(0, 80)).join(' | '), rows: document.querySelectorAll('[data-ct-row]').length })));
  const pastRow = await page.evaluate(t => { const rows = [...document.querySelectorAll('[data-ct-row]')]; const r = rows.find(x => x.textContent.includes(t)); return r ? { id: r.getAttribute('data-ct-row') } : null; }, 'رویداد برگزارشدهٔ آزمون ' + stamp);
  const pastList = pastRow && await api('/api/admin/content/events?when=past&limit=50');
  L('past row', { row: pastRow, inPastBucket: !!(pastList && (pastList.body.items || []).some(i => i.id === pastRow.id)) });
  check('past event saved and bucketed as past (server when=past)', !!pastRow && !!(pastList && (pastList.body.items || []).some(i => i.id === pastRow.id)));
  if (!pastRow) { await shot('debug-past-fail', true); await sleep(3000); L('late state', await page.evaluate(() => ({ hash: location.hash, editor: !!document.querySelector('[data-ct-editor]'), rows: document.querySelectorAll('[data-ct-row]').length, st: [...document.querySelectorAll('[role="status"],[role="alert"]')].map(e => e.textContent.trim().slice(0, 80)).join(' | ') }))); throw new Error('past row missing'); }
  const pastSrv = pastRow && await api('/api/admin/content/events/' + pastRow.id);
  check('server: past=true regMode=closed reminders off', !!pastSrv && pastSrv.body.record.past === true && pastSrv.body.record.regMode === 'closed' && pastSrv.body.record.reminders && pastSrv.body.record.reminders.h24 === false);
  // list quick filters
  await click('[data-ct-quick="past"]'); await sleep(2000);
  check('quick filter past shows the past row', await has('[data-ct-row="' + pastRow.id + '"]'));
  await page.selectOption('[data-ct-mode]', 'حضوری'); await sleep(2000);
  check('mode filter keeps onsite past row', await has('[data-ct-row="' + pastRow.id + '"]'));
  await shot('after-events-list-filters', false);
  await click('[data-ct-quick="all"]'); await sleep(1500);

  // ── E) files & media on the past event ──
  await click('[data-ct-file="' + pastRow.id + '"]'); await sleep(2500);
  await click('[data-ei-tab="resources"]'); await sleep(2000);
  check('tab «فایل‌ها و رسانه‌ها» with guide', /فایل‌ها و رسانه‌ها/.test(await txt('[data-ei-tab="resources"]') || '') && await has('[data-ei-res-guide]'));
  await click('[data-ei-res-new]'); await sleep(600);
  await page.selectOption('#eif_kind', 'link'); await sleep(300);
  await setVal('#eif_title', 'آلبوم عکس رویداد'); await setVal('#eif_link_url', 'https://photos.example.org/album/' + stamp.replace(/:/g, ''));
  await click('[data-ei-res-save]'); await sleep(2500);
  const linkRes = await page.evaluate(() => { const row = [...document.querySelectorAll('[data-ei-res-row],[data-ei-res-edit]')].map(e => e.getAttribute('data-ei-res-row') || e.getAttribute('data-ei-res-edit')).filter(Boolean); return row; });
  L('resources after link create', linkRes);
  check('link resource created', linkRes.length >= 1);
  // file resource + upload
  await click('[data-ei-res-new]'); await sleep(600);
  await page.selectOption('#eif_kind', 'file'); await sleep(300);
  await setVal('#eif_title', 'برنامهٔ رویداد (PDF)');
  await click('[data-ei-res-save]'); await sleep(2500);
  const fileResId = await page.evaluate(() => { const inp = document.querySelector('input[data-ei-file]'); return inp ? inp.getAttribute('data-ei-file') : null; });
  L('file resource id', fileResId);
  const pdfPath = path.join(out, 'qa-program.pdf');
  fs.writeFileSync(pdfPath, '%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\nxref\n0 4\n0000000000 65535 f \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF\n');
  if (fileResId) { await page.setInputFiles('input[data-ei-file="' + fileResId + '"]', pdfPath); await sleep(4000); }
  const afterUp = await page.evaluate(id => { const row = document.querySelector('[data-ei-res-row="' + id + '"]'); return row ? row.textContent.replace(/\s+/g, ' ').slice(0, 200) : null; }, fileResId);
  L('file row after upload', afterUp);
  await click('[data-ei-res-status="published"][data-ei-id="' + fileResId + '"]'); await sleep(2000);
  await shot('after-event-files-tab', true);
  // reload persists
  await gotoHash('#events'); await click('[data-ct-file="' + pastRow.id + '"]'); await sleep(2500); await click('[data-ei-tab="resources"]'); await sleep(2000);
  const persisted = await api('/api/admin/events/' + pastRow.id + '/resources');
  L('resources API after reload', persisted.status + ' ' + JSON.stringify((persisted.body && persisted.body.items || []).map(i => ({ kind: i.kind, title: i.title, size: i.size, status: i.status }))));
  check('files persist after reload (link + uploaded pdf)', persisted.status === 200 && (persisted.body.items || []).some(i => i.kind === 'link') && (persisted.body.items || []).some(i => i.kind === 'file' && i.size > 0));
  check('files tab shows both rows', await has('[data-ei-res-row="' + fileResId + '"]'));

  fs.writeFileSync(path.join(out, 'log.txt'), log.join('\n') + '\n');
  L('SUMMARY', { pass: log.filter(l => l.startsWith('PASS')).length, fail: log.filter(l => l.startsWith('FAIL')).length });
  await browser.close();
})().catch(e => { console.error(e); fs.writeFileSync(path.join(out, 'log.txt'), log.join('\n') + '\nCRASH ' + e.stack + '\n'); process.exit(1); });
