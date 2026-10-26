// Real-browser acceptance: form builder ⇄ event definition round-trip (dev-only, test DB, synthetic accounts).
// Usage: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<deps> NORA_REPO_UI=<ui> NORA_E2E_IDS=<ids.json> node e2e-builder-return.cjs <outdir>
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const O = process.env.NORA_E2E_OWNER || 'http://127.0.0.1:8000', B = process.env.NORA_E2E_BACKEND || 'http://127.0.0.1:8001';
const fs = require('node:fs'), path = require('node:path'); const out = process.argv[2] || 'shots/builder-return'; fs.mkdirSync(out, { recursive: true });
const ids = JSON.parse(fs.readFileSync(process.env.NORA_E2E_IDS, 'utf8')); const A = ids.A;
const sleep = ms => new Promise(r => setTimeout(r, ms)); const lines = []; let pass = 0, fail = 0;
const L = (m, x) => { const t = m + (x === undefined ? '' : ': ' + (typeof x === 'string' ? x : JSON.stringify(x))); lines.push(t); console.log(t); };
const check = (n, ok) => { ok ? pass++ : fail++; L((ok ? 'PASS ' : 'FAIL ') + n); };
(async () => {
  const b = await launchBrowser(); const page = await b.newPage(); const errors = []; page.on('pageerror', e => errors.push(e.message)); page.on('dialog', d => d.accept());
  await page.setViewportSize({ width: 1440, height: 900 });
  const shot = async (n, full) => page.screenshot({ path: path.join(out, n + '.png'), fullPage: !!full });
  const has = s => page.$(s).then(x => !!x); const waitFor = async (fn, ms = 8000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (await fn()) return true; await sleep(200); } return false; };
  const txt = s => page.$eval(s, el => el.textContent || '').catch(() => '');
  const api = (p, init) => page.evaluate(async ([pp, ii]) => { const csrf = (document.cookie.match(/nora_csrf=([^;]+)/) || [])[1] || ''; const r = await fetch(pp, Object.assign({ credentials: 'same-origin' }, ii || {}, { headers: Object.assign({ 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, (ii && ii.headers) || {}) })); let body = null; try { body = await r.json(); } catch (e) { } return { status: r.status, body }; }, [p, init]);

  // ── 1. deep link to the editor, five-step rail, typed-but-unsaved change ──
  await page.goto('about:blank'); await page.goto(O + '/admin.html#edit=' + A + '&sec=reg', { waitUntil: 'load' }); await sleep(2500);
  check('#edit=<id> opens the compact editor of that event', await waitFor(() => has('[data-ct-editor]')) && await has('[data-ct-forms="' + A + '"]'));
  check('five-step rail is present (main/when/reg/notify/review)', (await page.$$eval('[data-ct-step]', xs => xs.map(x => x.dataset.ctStep).join(','))) === 'main,when,reg,notify,review');
  const countBefore = await page.$$eval('[data-ct-form-row]', xs => xs.length); L('linked forms before', countBefore);
  const marker = 'یادداشت آزمایشی ' + Date.now().toString(36);
  await page.click('[data-ct-step="main"]'); await sleep(300);
  await page.focus('#ctf_t'); await page.keyboard.press('End'); await page.keyboard.type(' ' + marker); await sleep(400);
  const titleTyped = await page.$eval('#ctf_t', el => el.value); check('title edited in the browser (unsaved)', titleTyped.includes(marker));
  await shot('01-editor-with-rail');
  const mk = await page.$eval('[data-ct-form-create="' + A + '"]', a => a.getAttribute('href'));
  L('create link', mk);
  check('create-form link carries ev, need=reg and a local back to the editor section', /^create\.html\?/.test(mk) && mk.includes('ev=' + A) && mk.includes('need=reg') && decodeURIComponent(mk).includes('back=admin.html#edit=' + A + '&sec=reg&from=builder'));
  // ── 2. builder opened from the editor ──
  await page.click('[data-ct-form-create="' + A + '"]'); await sleep(2500);
  check('builder opened in the same tab with the event context', /create\.html\?/.test(page.url()) && page.url().includes('ev=' + A));
  check('primary button reads «ذخیره و بازگشت به رویداد»', /ذخیره و بازگشت به رویداد/.test(await txt('#publish')));
  const chipHref = await page.$eval('#evChip', el => el.getAttribute('href')).catch(() => null);
  check('return chip points back to the editor (local href only)', !!chipHref && /^admin\.html#edit=/.test(chipHref));
  await shot('02-builder-from-editor');
  // save → verified by the server → auto-return
  await page.evaluate(() => go('s4')); await sleep(400);
  await page.evaluate(() => go('s1')); await sleep(200); const uniq = 'ثبت‌نام آزمایشی ' + Date.now().toString(36);
  await page.fill('#fTitle', uniq); await page.evaluate(() => document.getElementById('fTitle').dispatchEvent(new Event('input', { bubbles: true }))); await sleep(200);
  await page.evaluate(() => go('s4')); await sleep(400);
  const formName = await page.evaluate(() => (document.getElementById('fTitle') || {}).value || ''); L('form title', formName);
  await page.click('#publish');
  const returned = await waitFor(() => page.url().includes('admin.html#edit=' + A), 15000); await sleep(2500);
  check('after the server confirmed the save, the browser returned to admin.html#edit=<id> (hash then normalised to the editor route)', returned && /#edit=/.test(page.url()));
  check('editor reopened on the same event', await waitFor(() => has('[data-ct-editor]')) && await has('[data-ct-forms="' + A + '"]'));
  const countAfter = await page.$$eval('[data-ct-form-row]', xs => xs.length); L('linked forms after', countAfter);
  check('the new form is linked and listed under this event (count +1)', countAfter === countBefore + 1);
  const restoredTitle = await page.$eval('#ctf_t', el => el.value).catch(() => '');
  check('text typed before leaving was restored (not saved, visibly flagged)', restoredTitle.includes(marker) && /بازیابی شد/.test(await txt('[data-ct-editor]')));
  await shot('03-back-in-editor-form-linked');
  // server truth: the form exists with ev = A
  const forms = await api('/api/forms?limit=200'); const mine = (forms.body && forms.body.items || []).filter(f => String(f.ev || '') === String(A));
  L('server forms linked to A', mine.map(f => f.name + ':' + f.status));
  check('server lists the new draft form with ev=<A> (no duplicate created)', mine.length === countAfter && mine.filter(f => f.name === formName).length === 1);
  const newForm = mine.find(f => f.name === formName);
  // discard the restored (unsaved) title so the event record is untouched
  await page.click('[data-ct-cancel]'); await sleep(800);
  check('cancel leaves the editor and clears the #edit hash', !(await has('[data-ct-editor]')) && !/#edit=/.test(page.url()));
  // ── 3. edit the linked form → fid pinned → return ──
  await page.goto('about:blank'); await page.goto(O + '/admin.html#edit=' + A + '&sec=reg', { waitUntil: 'load' }); await sleep(2500);
  const editHref = await page.$eval('[data-ct-form-row="' + newForm.id + '"] a[href^="create.html?fid="]', a => a.getAttribute('href'));
  check('edit link of the linked form carries the same editor back-context', decodeURIComponent(editHref).includes('back=admin.html#edit=' + A));
  await page.click('[data-ct-form-row="' + newForm.id + '"] a[href^="create.html?fid="]'); await sleep(3000);
  check('builder opened on the linked form (fid in URL)', page.url().includes('fid=' + newForm.id));
  check('edit mode: primary button still «ذخیره و بازگشت به رویداد»', /ذخیره و بازگشت به رویداد/.test(await txt('#publish')));
  await page.evaluate(() => go('s4')); await sleep(300); await page.click('#publish');
  const returned2 = await waitFor(() => page.url().includes('admin.html#edit=' + A), 15000); await sleep(2000);
  check('editing the linked form and saving returns to the same editor section', returned2);
  const after2 = await api('/api/forms?limit=200'); const mine2 = (after2.body && after2.body.items || []).filter(f => String(f.ev || '') === String(A));
  check('no duplicate form after edit-save (same count, version bumped)', mine2.length === mine.length && (mine2.find(f => f.id === newForm.id) || {}).version > (newForm.version || 0));
  // ── 4. refresh in the builder keeps fid + context (no duplicate on re-save) ──
  await page.goto('about:blank'); await page.goto(O + '/create.html?ev=' + A + '&need=survey&name=x&back=' + encodeURIComponent('admin.html#edit=' + A + '&sec=reg&from=builder'), { waitUntil: 'load' }); await sleep(2500);
  await page.evaluate(() => go('s4')); await sleep(300);
  // intercept the redirect: pin check must happen before navigation → observe URL within the 700 ms window
  await page.click('#publish'); const pinned = await waitFor(() => /[?&]fid=/.test(page.url()) && /create\.html/.test(page.url()), 6000); const pinnedUrl = page.url(); L('url after first save', pinnedUrl.replace(/^https?:\/\/[^/]+/, ''));
  check('after the first save the builder URL is pinned with fid= (refresh reopens the same form)', pinned);
  await waitFor(() => page.url().includes('admin.html#edit='), 10000); await sleep(1500);
  await page.goto('about:blank'); await page.goto(pinnedUrl, { waitUntil: 'load' }); await sleep(3000);
  check('reloading the pinned URL opens the saved form again in the builder (same fid, not a new form)', page.url().includes('fid=') && /ذخیره و بازگشت به رویداد/.test(await txt('#publish')));
  await shot('04-builder-refresh-pinned');
  // ── 5. failure paths: published form (409) stays in builder; foreign back is ignored ──
  await page.goto('about:blank'); await page.goto(O + '/create.html?fid=' + ids.regA + '&back=' + encodeURIComponent('admin.html#edit=' + A + '&sec=reg&from=builder'), { waitUntil: 'load' }); await sleep(3000);
  await page.evaluate(() => go('s4')); await sleep(300); await page.click('#publish', { force: true, timeout: 5000 }).catch(() => {}); await sleep(600);  /* the lock bar now marks the button aria-disabled; the click must be a no-op */
  const pubToast = await txt('#toast'); await sleep(1900); L('published-form click toast', pubToast);
  const pubCur = await api('/api/forms/' + ids.regA); const pickF = o => { const r = {}; ['name', 'model', 'need', 'slug', 'ev', 'fields', 'settings', 'purpose'].forEach(k => { if (o[k] !== undefined && o[k] !== null) r[k] = o[k]; }); return r; };
  const pubApi = await api('/api/forms/' + ids.regA, { method: 'PUT', body: JSON.stringify(Object.assign(pickF(pubCur.body || {}), { name: 'x y z', expected_version: Number((pubCur.body || {}).version) || 1 })) }); L('published PUT', pubApi.status + ' ' + JSON.stringify(pubApi.body).slice(0, 160));
  check('server refuses editing a published form (PUT -> 409 published_form_read_only) regardless of the UI', pubApi.status === 409 && /published_form_read_only/.test(JSON.stringify(pubApi.body)));
  const pubState = await txt('#ownerApiState') + ' | ' + await txt('#ownerApiMessage'); const pubDisabled = await page.$eval('#publish', b => b.disabled || b.getAttribute('aria-disabled') === 'true').catch(() => false); L('published-form save state', pubState + ' | save disabled=' + pubDisabled);
  check('published form: save is not possible (button disabled or 409 published_form_read_only), user stays in the builder, no redirect', /create\.html/.test(page.url()) && !/#edit=/.test(page.url()) && (pubDisabled || /متوقف|منتشر|ذخیره نشد/.test(pubState) || /ابتدا|متوقف|منتشر/.test(pubToast)) && !/در حال بازگشت/.test(pubState));
  await shot('05-published-form-stays');
  await page.goto('about:blank'); await page.goto(O + '/create.html?ev=' + A + '&need=survey&name=x&back=' + encodeURIComponent('https://evil.example/x'), { waitUntil: 'load' }); await sleep(2000);
  const evilChip = await page.$eval('#evChip', el => el.getAttribute('href')).catch(() => null);
  check('foreign back= is ignored: no return href, plain save label', (evilChip == null || !/evil/.test(evilChip)) && !/بازگشت به رویداد/.test(await txt('#publish')));
  // ── 6. version conflict (409) while editing: builder stays with the message ──
  await page.goto('about:blank'); await page.goto(O + '/create.html?fid=' + newForm.id + '&back=' + encodeURIComponent('admin.html#edit=' + A + '&sec=reg&from=builder'), { waitUntil: 'load' }); await sleep(3000);
  const cur = await api('/api/forms/' + newForm.id); const v = cur.body && cur.body.version;
  const pick = o => { const r = {}; ['name', 'model', 'need', 'slug', 'ev', 'fields', 'settings', 'purpose'].forEach(k => { if (o[k] !== undefined && o[k] !== null) r[k] = o[k]; }); return r; };
  const bump = await api('/api/forms/' + newForm.id, { method: 'PUT', body: JSON.stringify(Object.assign(pick(cur.body), { name: cur.body.name + ' (ویرایش موازی)', expected_version: v })) });
  L('parallel edit via API', bump.status);
  await page.evaluate(() => go('s4')); await sleep(300); await page.click('#publish'); await sleep(2500);
  check('409 version conflict: the browser stays in the builder and shows the conflict (no silent overwrite, no redirect)', /create\.html/.test(page.url()) && /نسخه/.test(await txt('body')));
  await shot('06-version-conflict');
  L('page errors', errors.filter(e => !/Window's open|sitemap/.test(e)));
  L('TOTAL PASS ' + pass + ' / FAIL ' + fail); fs.writeFileSync(path.join(out, 'log.txt'), lines.join('\n') + '\n'); await b.close(); process.exit(fail ? 1 : 0);
})().catch(e => { console.error('crashed', e); process.exit(2); });
