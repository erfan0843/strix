// Real-browser acceptance for the form-builder field engine (test DB, synthetic owner, public visitor on the backend origin).
// Chain: catalog search → build → customise (bounds, option order, conditional) → save → reload+compare → server error paths
// mapped to the right control → readiness → publish → public form (validation, conditional, submit) → responses/CSV → lock.
// Usage: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<deps> NORA_REPO_UI=<ui> node e2e-field-engine.cjs <outdir>
// Owner requests go through the server-side-session preview proxy (:8000); the visitor uses the backend origin (:8001).
const fs = require('node:fs'), path = require('node:path');
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const O = process.env.NORA_E2E_OWNER || 'http://127.0.0.1:8000', B = process.env.NORA_E2E_BACKEND || 'http://127.0.0.1:8001';
const out = process.argv[2] || 'shots/field-engine'; fs.mkdirSync(out, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms)); const lines = []; let pass = 0, fail = 0;
const L = (m, x) => { const t = m + (x === undefined ? '' : ': ' + (typeof x === 'string' ? x : JSON.stringify(x))); lines.push(t); console.log(t); };
const check = (n, ok, extra) => { ok ? pass++ : fail++; L((ok ? 'PASS ' : 'FAIL ') + n + (extra === undefined || ok ? '' : ' · ' + JSON.stringify(extra).slice(0, 300))); };
const stamp = Date.now().toString(36);
async function api(p, init) { const r = await fetch(O + p, Object.assign({ headers: { 'content-type': 'application/json' } }, init || {})); return { status: r.status, body: await r.json().catch(() => null) }; }
async function apiText(p) { const r = await fetch(O + p); return { status: r.status, text: await r.text(), type: r.headers.get('content-type') || '' }; }
(async () => {
  const b = await launchBrowser(); const page = await b.newPage(); const errors = [];
  page.on('pageerror', e => errors.push(e.message)); page.on('dialog', d => d.accept());
  const shot = async (n, full) => page.screenshot({ path: path.join(out, n + '.png'), fullPage: !!full });
  const waitFor = async (fn, ms = 8000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (await fn()) return true; } catch (e) { } await sleep(150); } return false; };
  const ev = (code) => page.evaluate(code);
  const txt = s => page.$eval(s, el => (el.textContent || '').replace(/\s+/g, ' ').trim()).catch(() => '');
  const state = () => page.$eval('#saveState', el => el.dataset.state).catch(() => '');
  const clickSel = async s => { await page.waitForSelector(s, { timeout: 8000 }); await page.click(s); };
  const typeInto = async (s, v) => { await page.fill(s, v); await page.$eval(s, el => { el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }); };
  const sheetOn = id => page.$eval('#' + id, el => el.classList.contains('on')).catch(() => false);
  const openPicker = async () => { if (!(await sheetOn('shAdd'))) { await clickSel('#addBottom'); await sleep(250); } };

  // ── A. build a registration form through the catalog ──
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('about:blank'); await page.goto(O + '/create.html?need=reg', { waitUntil: 'load' }); await sleep(1500);
  check('capability contract resolved from the server (state ready)', await waitFor(() => ev("FORM_CAPABILITY_STATE==='ready'"), 10000), await ev('FORM_CAPABILITY_STATE'));
  const title = 'موتور فیلد ' + stamp;
  await typeInto('#fTitle', title);
  await ev("go('s2')"); await sleep(300);
  await ev("applyPack('empty','replace')"); await sleep(300);
  check('empty canvas, save state idle (new form, nothing on the server yet)', (await ev('S.fields.length')) === 0 && (await state()) === 'idle');
  await openPicker(); await sleep(300);
  await typeInto('#catSearch', 'شماره همراه'); await sleep(250);
  const firstHit = await page.$eval('#catList [data-add]', el => el.dataset.add).catch(() => '');
  check('search «شماره همراه» ranks the mobile pattern first and shows a result count', firstHit === 'mobile' && /نتیجه/.test(await txt('#catCount')), { firstHit, count: await txt('#catCount') });
  await shot('01-picker-search-1440');
  await typeInto('#catSearch', ''); await sleep(250);
  const imageRow = await page.$eval('#catList [data-add="image"]', el => ({ disabled: el.disabled, text: el.textContent })).catch(() => null);
  check('upload row is disabled with the server reason inline (not addable)', !!imageRow && imageRow.disabled && /وصل نیست|غیرفعال/.test(imageRow.text), imageRow && imageRow.text.slice(0, 120));
  await page.click('#catChips [data-cat="contact"]'); await sleep(200);
  check('category button is a real toggle (aria-pressed) and keeps focus', (await page.$eval('#catChips [data-cat="contact"]', el => el.getAttribute('aria-pressed') + ':' + (document.activeElement === el))) === 'true:true');
  await page.click('#catChips [data-cat="all"]'); await sleep(200);
  const addViaCatalog = async (k) => { await openPicker(); await clickSel('#catList [data-add="' + k + '"]'); await sleep(350); return sheetOn('shField'); };
  check('adding «نام و نام خانوادگی» opens its editor', await addViaCatalog('fullname'));
  await clickSel('#fdReq'); await clickSel('#fdSave'); await sleep(200);
  check('adding «موبایل» works and the editor shows the honest verification state', await addViaCatalog('mobile') && /غیرفعال|قدیمی|اجرا نمی‌شود/.test(await txt('#fdVerifyStatus')));
  await clickSel('#fdSave'); await sleep(200);
  check('adding a number field opens bounds controls', await addViaCatalog('number') && (await page.$eval('#fdBoundsBox', el => el.style.display)) === 'block');
  await typeInto('#fdTitle', 'سن'); await typeInto('#fdMin', '۹۰'); await typeInto('#fdMax', '۱۰');
  await clickSel('#fdSave'); await sleep(200);
  check('invalid bounds (min > max) keep the editor open with the error inside the sheet', await sheetOn('shField') && !(await page.$eval('#fdIssues', el => el.hidden)));
  await shot('02-editor-invalid-bounds-1440');
  await typeInto('#fdMin', '۱۰'); await typeInto('#fdMax', '۹۰'); await clickSel('#fdSave'); await sleep(200);
  check('valid bounds saved as numbers (Persian digits accepted)', JSON.stringify(await ev("[S.fields[2].l,S.fields[2].min,S.fields[2].max]")) === JSON.stringify(['سن', 10, 90]));
  check('adding a single-choice field gives editable options', await addViaCatalog('choice') && (await page.$$eval('#fdOptions [data-optdown]', xs => xs.length)) >= 2);
  await typeInto('#fdTitle', 'رنگ');
  const optsBefore = await ev("optionRowsForField(FIELD_DRAFT).map(o=>o.l)");
  check('first option cannot move up, last cannot move down', (await page.$eval('[data-optup="0"]', el => el.disabled)) && (await page.$eval('[data-optdown="' + (optsBefore.length - 1) + '"]', el => el.disabled)));
  await page.click('[data-optdown="0"]'); await sleep(150);
  const optsAfter = await ev("optionRowsForField(FIELD_DRAFT).map(o=>o.l)");
  const activeAfterMove = await ev("document.activeElement?(document.activeElement.id||JSON.stringify(document.activeElement.dataset)):''");
  check('option moved down for real and focus stayed on the moved row', optsAfter[1] === optsBefore[0] && optsAfter[0] === optsBefore[1] && /opt(down|up)":"1"/.test(activeAfterMove), { optsBefore, optsAfter, activeAfterMove });
  await shot('03-editor-options-1440');
  await clickSel('#fdSave'); await sleep(200);
  const choiceId = await ev("String(S.fields[3].id)");
  check('adding a short text field for the conditional question', await addViaCatalog('text'));
  await typeInto('#fdTitle', 'چرا؟');
  await clickSel('#fdAddCondition'); await sleep(200);
  await page.selectOption('#fdCondField', choiceId); await sleep(200);
  await page.selectOption('#fdCondOp', 'eq'); await sleep(200);
  const valueTag = await page.$eval('[data-cond-value="0"]', el => el.tagName).catch(() => '');
  if (valueTag === 'SELECT') await page.selectOption('[data-cond-value="0"]', optsAfter[0]); else await typeInto('[data-cond-value="0"]', optsAfter[0]);
  await sleep(150);
  await page.evaluate(() => { const s = document.getElementById('shField'); s.scrollTop = s.scrollHeight; }); await sleep(200);
  await shot('04-editor-conditional-1440');
  await clickSel('#fdSave'); await sleep(250);
  const condSaved = await ev("JSON.stringify(S.fields[4].conditions)");
  check('conditional rule saved on the field (field/op/value)', condSaved.includes('"field":"' + choiceId + '"') && condSaved.includes('"op":"eq"') && condSaved.includes(optsAfter[0]), condSaved);
  check('canvas shows the conditional badge and the editor closed', /شرطی/.test(await txt('[data-block="' + (await ev("String(S.fields[4].id)")) + '"]')) && !(await sheetOn('shField')));
  check('save state is not «ذخیره شد» before the server confirmed anything', (await state()) === 'idle' || (await state()) === 'dirty', await state());
  await ev("go('s4')"); await sleep(300); await page.click('#publish');
  check('after the first save the URL is pinned with fid= and state becomes «ذخیره شد»', await waitFor(() => /[?&]fid=/.test(page.url()), 8000) && await waitFor(async () => (await state()) === 'saved', 6000), { url: page.url().replace(/^https?:\/\/[^/]+/, ''), state: await state() });
  const fid = (page.url().match(/[?&]fid=([^&]+)/) || [])[1]; L('form id', fid);
  const serverForm = await api('/api/forms/' + fid);
  check('server stored 5 fields in order with bounds, option order and the condition', serverForm.status === 200 && serverForm.body.fields.length === 5 && serverForm.body.fields[2].min === 10 && serverForm.body.fields[2].max === 90 && serverForm.body.fields[3].opts.map(o => o.l)[0] === optsAfter[0] && JSON.stringify(serverForm.body.fields[4].conditions || []).includes(choiceId), serverForm.body && serverForm.body.fields && serverForm.body.fields.map(f => f.t));
  await shot('05-saved-review-1440');

  // ── B. reload: builder state must equal the server record ──
  await page.goto('about:blank'); await page.goto(O + '/create.html?fid=' + fid, { waitUntil: 'load' });
  await waitFor(() => /hydrated=1/.test(page.url()), 4000);
  const reopened = await waitFor(async () => (await state()) === 'saved', 8000);
  const versionShown = await ev("ACTIVE_SERVER_FORM&&ACTIVE_SERVER_FORM.version");
  check('reopening by fid opens as «ذخیره شد» on the server version (mirror verified against the API, no stale copy)', reopened && versionShown === serverForm.body.version && /نسخهٔ/.test(await txt('#saveState')), { url: page.url().replace(/^https?:\/\/[^/]+/, ''), state: await state(), versionShown, server: serverForm.body.version });
  const local = await ev("JSON.stringify(S.fields.map(f=>({id:String(f.id),t:f.t,l:f.l,min:f.min,max:f.max,opts:(f.opts||[]).map(o=>o.l),cond:(f.conditions||[]).map(r=>r.field+':'+r.op+':'+r.value)})))");
  const remote = JSON.stringify(serverForm.body.fields.map(f => ({ id: String(f.id), t: f.t, l: f.l, min: f.min == null ? '' : f.min, max: f.max == null ? '' : f.max, opts: (f.opts || []).map(o => o.l), cond: (f.conditions || []).map(r => r.field + ':' + r.op + ':' + r.value) })));
  check('restored fields equal the server record (ids, types, titles, bounds, option order, conditions)', local === remote, { local: local.slice(0, 240), remote: remote.slice(0, 240) });
  await ev("go('s2')"); await sleep(300);
  await page.setViewportSize({ width: 390, height: 844 }); await sleep(300); await shot('06-canvas-390');
  await openPicker(); await sleep(300); await shot('07-picker-390'); await ev('closeSheets()');
  await ev("editField(S.fields[4].id)"); await sleep(300);
  await page.evaluate(() => { const s = document.getElementById('shField'); s.scrollTop = s.scrollHeight; }); await sleep(200);
  await shot('08-editor-conditional-390');
  await clickSel('#fdCancel'); await sleep(200);
  check('cancel on an untouched editor closes without a discard prompt', !(await sheetOn('shField')));
  await page.setViewportSize({ width: 1440, height: 900 });

  // ── C. server-side defects injected through the API → builder maps them to the right control ──
  const broken = JSON.parse(JSON.stringify(serverForm.body));
  broken.fields[2].min = 50; broken.fields[2].max = 10;
  broken.fields.push({ id: 'legacy-img', t: 'image', l: 'عکس پرسنلی', count: 1, accept: 'image/*', maxSize: 5 });
  const putBroken = await api('/api/forms/' + fid, { method: 'PUT', body: JSON.stringify({ name: broken.name, model: broken.model, need: broken.need, slug: broken.slug, ev: broken.ev, fields: broken.fields, settings: broken.settings, expected_version: broken.version }) });
  check('API accepted a draft with an invalid numeric range and a legacy upload field (draft stays editable)', putBroken.status === 200, putBroken.status);
  const readiness = await api('/api/forms/' + fid + '/readiness');
  const codes = (readiness.body && readiness.body.issues || []).map(i => i.code + (i.field_id ? '@' + i.field_id : ''));
  check('readiness reports both defects with field ids', codes.includes('invalid_numeric_range@' + broken.fields[2].id) && codes.includes('field_type_not_supported@legacy-img') && readiness.body.publishable === false, codes);
  await page.goto('about:blank'); await page.goto(O + '/create.html?fid=' + fid, { waitUntil: 'load' });
  check('builder detects the newer server version behind the local mirror and reloads on it (hydrated=1)', await waitFor(() => /hydrated=1/.test(page.url()), 10000) && await waitFor(async () => (await state()) === 'saved', 6000) && (await ev("ACTIVE_SERVER_FORM&&ACTIVE_SERVER_FORM.version")) === putBroken.body.version, { url: page.url().replace(/^https?:\/\/[^/]+/, ''), v: await ev("ACTIVE_SERVER_FORM&&ACTIVE_SERVER_FORM.version"), server: putBroken.body.version });
  await ev("go('s2')"); await sleep(300);
  check('legacy upload field is visible on the canvas, flagged «نیاز به اصلاح», not deleted', (await ev('S.fields.length')) === 6 && /نیاز به اصلاح/.test(await txt('[data-block="legacy-img"]')));
  await ev("go('s4')"); await sleep(300);
  check('readiness list renders a «بازکردن پرسش» button per field-level issue', await waitFor(async () => (await page.$$('[data-ready-field]')).length >= 2, 8000), await page.$$eval('[data-ready-field]', xs => xs.map(x => x.dataset.readyField)));
  await shot('09-readiness-field-issues-1440');
  await page.click('[data-ready-field="' + broken.fields[2].id + '"]'); await sleep(400);
  check('numeric-range issue opens that question with the minimum control focused', (await sheetOn('shField')) && (await ev("document.activeElement&&document.activeElement.id")) === 'fdMin' && (await page.$eval('#fdTitle', el => el.value)) === 'سن');
  await typeInto('#fdMin', '۱۰'); await typeInto('#fdMax', '۹۰'); await clickSel('#fdSave'); await sleep(200);
  await ev("go('s4')"); await sleep(200); await page.click('[data-ready-field="legacy-img"]'); await sleep(400);
  const typeTargets = await page.$$eval('#fdTypeChange option', xs => xs.map(x => x.value).filter(Boolean));
  check('legacy upload issue opens the type-change control with only safe targets', (await ev("document.activeElement&&document.activeElement.id")) === 'fdTypeChange' && typeTargets.includes('text') && !typeTargets.includes('file'), typeTargets);
  await page.selectOption('#fdTypeChange', 'text'); await clickSel('#fdTypeApply'); await sleep(200);
  check('type change asks for confirmation and lists the consequences', !(await page.$eval('#fdTypeConfirm', el => el.hidden)) && /فایل/.test(await txt('#fdTypeConsequences')));
  await shot('10-type-change-confirm-1440');
  await clickSel('#fdTypeConfirmGo'); await sleep(200); await clickSel('#fdSave'); await sleep(200);
  check('legacy field converted to text, title kept, no longer flagged', (await ev("S.fields[5].t==='text'&&S.fields[5].l==='عکس پرسنلی'")) && !/نیاز به اصلاح/.test(await txt('[data-block="legacy-img"]')));
  await openPicker(); await sleep(300);
  check('catalog still blocks upload types after the fix (no cosmetic enabling)', await page.$eval('#catList [data-add="image"]', el => el.disabled));
  await ev('closeSheets()');
  await ev("go('s4')"); await sleep(200); await page.click('#publish');
  check('re-save confirmed by the server (version bumped)', await waitFor(async () => (await state()) === 'saved', 8000) && (await api('/api/forms/' + fid)).body.version > putBroken.body.version);
  const ready2 = await api('/api/forms/' + fid + '/readiness');
  check('readiness is clean after fixing both issues from the mapped controls', ready2.body && ready2.body.publishable === true, ready2.body && ready2.body.issues);

  // ── D. publish from the builder ──
  await page.goto('about:blank'); await page.goto(O + '/create.html?fid=' + fid, { waitUntil: 'load' });
  await waitFor(async () => (await state()) === 'saved', 8000);
  await ev("go('s4')"); await sleep(600);
  const publishVisible = await page.$eval('#donePublish', el => el.style.display !== 'none' && !el.disabled).catch(() => false);
  if (publishVisible) { await page.click('#donePublish'); await sleep(1500); }
  else { const pub = await api('/api/forms/' + fid + '/publish', { method: 'POST', body: JSON.stringify({ expected_version: (await api('/api/forms/' + fid)).body.version }) }); L('publish via API (button hidden)', pub.status); }
  const published = await api('/api/forms/' + fid);
  check('form is published on the server' + (publishVisible ? ' (from the builder button)' : ''), published.body && published.body.status === 'published', published.body && published.body.status);
  await shot('11-published-1440');

  // ── E. public form: validation, conditional visibility, submit ──
  const url = B + '/form.html?fid=' + encodeURIComponent(fid) + '&kind=reg';
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('about:blank'); await page.goto(url, { waitUntil: 'load' }); await sleep(2500);
  await shot('12-public-start-390');
  await page.setViewportSize({ width: 1440, height: 900 }); await sleep(300);
  const answers = { 'نام و نام خانوادگی': 'آزمون نورا', 'نام کامل': 'آزمون نورا', 'موبایل': '09121234567', 'شماره موبایل': '09121234567', 'سن': '25', 'چرا؟': 'چون دوست دارم', 'عکس پرسنلی': 'بدون عکس' };
  let sawRangeError = false, condSeen = false, triedBadAge = false, shotsTaken = 0;
  for (let i = 0; i < 16; i++) {
    const done = await page.evaluate(async fid => { try { const r = await fetch('/api/public/forms/' + fid + '/draft'); const j = await r.json(); return r.status === 200 && j.submitted === true; } catch (e) { return false; } }, fid);
    if (done) break;
    const step = await page.evaluate(([answers, triedBadAge, target]) => {
      const vis = e => !!(e && e.offsetParent !== null);
      const res = { filled: [], clicked: null };
      [...document.querySelectorAll('input.input:not([type="hidden"])')].filter(vis).forEach(inp => {
        const label = inp.getAttribute('aria-label') || ''; const key = Object.keys(answers).find(k => label.includes(k)); if (!key) return;
        let v = answers[key]; if (key === 'سن' && !triedBadAge) v = '5';
        if (inp.value === v) return; inp.focus(); inp.value = v; inp.dispatchEvent(new Event('input', { bubbles: true })); inp.dispatchEvent(new Event('change', { bubbles: true })); inp.blur(); res.filled.push(key + '=' + v);
      });
      const group = [...document.querySelectorAll('[data-qsel]')].find(vis);
      if (group && !group.querySelector('.opt.on')) { const opt = [...group.querySelectorAll('.opt')].find(o => (o.textContent || '').includes(target)) || group.querySelector('.opt'); if (opt) { opt.click(); res.filled.push('choice=' + opt.textContent.trim()); } }
      const btns = [...document.querySelectorAll('button:not([disabled]), a.btn')].filter(e => vis(e) && /شروع|ادامه|ثبت|تأیید|بعدی/.test(e.textContent) && !/انصراف|بازگشت|کپی/.test(e.textContent));
      const btn = btns.find(x => /ثبت/.test(x.textContent)) || btns[0]; if (btn) { res.clicked = btn.textContent.trim().slice(0, 30); btn.click(); }
      return res;
    }, [answers, triedBadAge, optsAfter[0]]);
    if (step.filled.some(f => f === 'سن=5')) triedBadAge = true;
    if (step.filled.some(f => f.startsWith('چرا؟='))) condSeen = true;
    await sleep(900);
    const errs = await page.evaluate(() => [...document.querySelectorAll('.field-error')].filter(e => e.offsetParent !== null && e.textContent.trim()).map(e => e.textContent.trim().slice(0, 100)));
    if (errs.length) { sawRangeError = sawRangeError || errs.some(e => /۱۰|۹۰|بازه|بیشتر|کمتر|حداقل|حداکثر/.test(e)); if (shotsTaken < 1) { await shot('13-public-range-error-1440'); shotsTaken++; } }
    L('public step ' + i, { filled: step.filled, clicked: step.clicked, errors: errs });
    if (!step.clicked && !step.filled.length) break;
  }
  const draft = await page.evaluate(async fid => { const r = await fetch('/api/public/forms/' + fid + '/draft'); return { status: r.status, body: await r.json() }; }, fid);
  check('public visitor got a validation error for age=5 (bounds 10..90 enforced on the public form)', sawRangeError);
  check('the conditional question was shown (and answered) after its reference option was selected', condSeen);
  check('public submission completed (server draft submitted=true)', draft.status === 200 && draft.body && draft.body.submitted === true, draft);
  await shot('14-public-done-1440');

  // ── F. owner: the response is stored with the right answers and exportable; published form is locked ──
  const responses = await api('/api/forms/' + fid + '/responses?limit=20');
  const items = responses.body && responses.body.items || [];
  const flat = JSON.stringify(items);
  check('owner sees exactly one response for this form', responses.status === 200 && items.length === 1, { status: responses.status, n: items.length });
  check('stored answers contain age 25, the chosen option and the conditional text', /25|۲۵/.test(flat) && flat.includes(optsAfter[0]) && flat.includes('چون دوست دارم'), flat.slice(0, 400));
  const csv = await apiText('/api/forms/' + fid + '/responses?format=csv');
  check('CSV export served through the real endpoint with the question headers', csv.status === 200 && /csv/.test(csv.type) && csv.text.includes('سن') && csv.text.includes('چرا؟') && csv.text.includes('چون دوست دارم'), { status: csv.status, type: csv.type });
  const locked = await api('/api/forms/' + fid, { method: 'PUT', body: JSON.stringify({ name: published.body.name, model: published.body.model, need: published.body.need, slug: published.body.slug, ev: published.body.ev, fields: published.body.fields, settings: published.body.settings, expected_version: published.body.version }) });
  check('published form with responses rejects field edits (409), builder cannot bypass it', locked.status === 409, locked.status);
  check('no page errors in the browser during the whole chain', errors.length === 0, errors.slice(0, 3));
  await b.close();
  fs.writeFileSync(path.join(out, 'log.txt'), lines.join('\n') + '\n');
  console.log('e2e-field-engine: ' + pass + ' قبول، ' + fail + ' خطا');
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('CRASH', e); fs.writeFileSync(path.join(out, 'log.txt'), lines.join('\n') + '\nCRASH ' + (e && e.stack || e) + '\n'); process.exit(1); });
