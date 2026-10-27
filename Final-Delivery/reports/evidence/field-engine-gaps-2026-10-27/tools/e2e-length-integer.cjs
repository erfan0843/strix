// Real-browser acceptance for the two new per-type settings: text min/max length and «فقط عدد صحیح» (integer) —
// builder controls → save → server record → reopen controls → publish → public form render/validation (browser) →
// API validation (draft PATCH partial, final POST) → stored response → readiness error jumps to the control.
// Usage: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<deps> NORA_REPO_UI=<ui> node e2e-length-integer.cjs <outdir>
const fs = require('node:fs'), path = require('node:path');
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const O = process.env.NORA_E2E_OWNER || 'http://127.0.0.1:8000', B = process.env.NORA_E2E_BACKEND || 'http://127.0.0.1:8001';
const out = process.argv[2] || 'shots/length-integer'; fs.mkdirSync(out, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms)); const lines = []; let pass = 0, fail = 0;
const L = (m, x) => { const t = m + (x === undefined ? '' : ': ' + (typeof x === 'string' ? x : JSON.stringify(x))); lines.push(t); console.log(t); };
const check = (n, ok, extra) => { ok ? pass++ : fail++; L((ok ? 'PASS ' : 'FAIL ') + n + (extra === undefined || ok ? '' : ' · ' + JSON.stringify(extra).slice(0, 300))); };
const stamp = Date.now().toString(36);
async function api(p, init) { const r = await fetch(O + p, Object.assign({ headers: { 'content-type': 'application/json' } }, init || {})); return { status: r.status, body: await r.json().catch(() => null) }; }
const toLatin = v => String(v == null ? '' : v).replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
(async () => {
  const b = await launchBrowser(); const page = await b.newPage(); const errors = [];
  page.on('pageerror', e => errors.push(e.message)); page.on('dialog', d => d.accept());
  const shot = async (n, full) => page.screenshot({ path: path.join(out, n + '.png'), fullPage: !!full });
  const waitFor = async (fn, ms = 8000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (await fn()) return true; } catch (e) { } await sleep(150); } return false; };
  const ev = code => page.evaluate(code);
  const txt = s => page.$eval(s, el => (el.textContent || '').replace(/\s+/g, ' ').trim()).catch(() => '');
  const state = () => page.$eval('#saveState', el => el.dataset.state).catch(() => '');
  const clickSel = async s => { await page.waitForSelector(s, { timeout: 8000 }); await page.click(s); };
  const typeInto = async (s, v) => { await page.fill(s, v); await page.$eval(s, el => { el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }); };
  const sheetOn = id => page.$eval('#' + id, el => el.classList.contains('on')).catch(() => false);
  const display = s => page.$eval(s, el => el.style.display).catch(() => 'missing');
  const switchState = s => page.$eval(s, el => el.classList.contains('on')).catch(() => null);
  const setSwitch = async (s, on) => { if ((await switchState(s)) !== on) await page.click(s); };
  const addViaPicker = async (k) => { if (!(await sheetOn('shAdd'))) { await clickSel('#addTop'); await sleep(250); } await clickSel('#catList [data-add="' + k + '"]'); await sleep(350); };

  // ── A. builder ──
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('about:blank'); await page.goto(O + '/create.html?need=reg', { waitUntil: 'load' }); await sleep(1500);
  check('capability contract ready', await waitFor(() => ev("FORM_CAPABILITY_STATE==='ready'"), 10000));
  const contract = await ev("JSON.stringify(FORM_CAPABILITIES.field_settings&&{length:FORM_CAPABILITIES.field_settings.length,integer:FORM_CAPABILITIES.field_settings.integer})");
  const fs_ = JSON.parse(contract || 'null');
  check('server contract publishes length + integer settings with types and caps', !!fs_ && fs_.length.status === 'server' && fs_.length.max_by_type.text === 1000 && fs_.integer.types.includes('number'), contract);
  await typeInto('#fTitle', 'طول و عدد صحیح ' + stamp);
  await ev("go('s2')"); await sleep(300); await ev("applyPack('empty','replace')"); await sleep(300); await ev("S.display='all'");

  // text with min 3 / max 8
  await addViaPicker('text');
  check('text: length box visible, integer row hidden, validation section shown', (await display('#fdLengthBox')) === 'block' && (await display('#fdIntegerBox')) === 'none' && (await display('#fdValidationBox')) !== 'none', { len: await display('#fdLengthBox'), int: await display('#fdIntegerBox') });
  check('text: note states the type cap (۱۰۰۰)', /۱۰۰۰|۱٬۰۰۰/.test(await txt('#fdLengthNote')), await txt('#fdLengthNote'));
  await typeInto('#fdTitle', 'نام مستعار ' + stamp.slice(-3)); await setSwitch('#fdReq', true);
  await typeInto('#fdMinLen', '۱۰'); await typeInto('#fdMaxLen', '۵');
  let rejected = !(await ev('saveField()'));
  check('text: min > max rejected, sheet stays open, focus on #fdMinLen', rejected && (await sheetOn('shField')) && (await ev("document.activeElement&&document.activeElement.id")) === 'fdMinLen', await txt('#fdIssues'));
  await typeInto('#fdMinLen', ''); await typeInto('#fdMaxLen', '۲۰۰۰');
  rejected = !(await ev('saveField()'));
  check('text: max above the type cap rejected with the cap in the message', rejected && /۱۰۰۰/.test(await txt('#fdIssues')), await txt('#fdIssues'));
  await typeInto('#fdMinLen', '۳'); await typeInto('#fdMaxLen', '۸');
  await shot('01-editor-text-length-1440');
  await clickSel('#fdSave'); await sleep(250);
  check('text: valid length saved and editor closed', !(await sheetOn('shField')));
  const textId = await ev('String(S.fields[S.fields.length-1].id)');
  check('text: canvas summary shows the length', (await txt('#fieldList')).includes('طول دست‌کم ۳ حداکثر ۸ نویسه'), (await txt('#fieldList')).slice(0, 200));

  // area with max 20 (no min)
  await addViaPicker('area'); await typeInto('#fdTitle', 'توضیح ' + stamp.slice(-3)); await typeInto('#fdMaxLen', '20'); await clickSel('#fdSave'); await sleep(200);
  const areaId = await ev('String(S.fields[S.fields.length-1].id)');

  // number: integer on + min 1
  await addViaPicker('number');
  check('number: integer row visible inside bounds, no length box', (await display('#fdIntegerBox')) !== 'none' && (await display('#fdBoundsBox')) === 'block' && (await display('#fdLengthBox')) === 'none');
  check('number: integer switch off by default and labelled', (await page.$eval('#fdInteger', el => el.getAttribute('aria-checked'))) === 'false' && /فقط عدد صحیح/.test(await txt('#fdIntegerBox')));
  await typeInto('#fdTitle', 'تعداد ' + stamp.slice(-3)); await typeInto('#fdMin', '۱'); await setSwitch('#fdInteger', true);
  check('number: toggling integer counts as an unsaved change', await ev('editorControlsChanged()') === true);
  await shot('02-editor-number-integer-1440');
  await clickSel('#fdSave'); await sleep(200);
  const numberId = await ev('String(S.fields[S.fields.length-1].id)');
  check('number: integer:true + min stored on the field', await ev("(f=>f.integer===true&&f.min===1)(S.fields[S.fields.length-1])"), await ev('JSON.stringify(S.fields[S.fields.length-1])'));

  // amount: integer left off
  await addViaPicker('amount'); await typeInto('#fdTitle', 'مبلغ ' + stamp.slice(-3)); await clickSel('#fdSave'); await sleep(200);
  const amountId = await ev('String(S.fields[S.fields.length-1].id)');
  check('amount: integer key absent when the switch is off', await ev("!('integer' in S.fields[S.fields.length-1])"));

  // ── B. save → server ──
  await ev("go('s4')"); await sleep(300); await page.click('#publish');
  check('first save pinned fid and «ذخیره شد»', await waitFor(() => /[?&]fid=/.test(page.url()), 8000) && await waitFor(async () => (await state()) === 'saved', 8000), await state());
  const fid = (page.url().match(/[?&]fid=([^&]+)/) || [])[1]; L('form id', fid);
  const server = await api('/api/forms/' + fid); const sf = {}; for (const f of (server.body && server.body.fields || [])) sf[String(f.id)] = f;
  check('server record: text minLen=3 maxLen=8, area maxLen=20, number integer=true, amount without integer',
    sf[textId] && sf[textId].minLen === 3 && sf[textId].maxLen === 8 && sf[areaId] && sf[areaId].maxLen === 20 && !('minLen' in sf[areaId]) && sf[numberId] && sf[numberId].integer === true && sf[amountId] && !('integer' in sf[amountId]),
    { text: sf[textId], area: sf[areaId], number: sf[numberId], amount: sf[amountId] });

  // ── C. reopen ──
  await page.goto('about:blank'); await page.goto(O + '/create.html?fid=' + fid, { waitUntil: 'load' });
  await waitFor(() => /hydrated=1/.test(page.url()), 4000);
  check('reopened as «ذخیره شد»', await waitFor(async () => (await state()) === 'saved', 8000), await state());
  await ev("go('s2')"); await sleep(300);
  await ev("editField('" + textId + "')"); await sleep(200);
  check('reopen text: controls show 3 / 8', toLatin(await page.$eval('#fdMinLen', el => el.value)) === '3' && toLatin(await page.$eval('#fdMaxLen', el => el.value)) === '8' && await ev('editorControlsChanged()') === false);
  await clickSel('#fdCancel'); await sleep(120);
  await ev("editField('" + numberId + "')"); await sleep(200);
  check('reopen number: integer switch on, min 1', (await page.$eval('#fdInteger', el => el.getAttribute('aria-checked'))) === 'true' && toLatin(await page.$eval('#fdMin', el => el.value)) === '1');
  const consequences = await ev("typeChangeConsequences(FIELD_DRAFT,'amount').join(' ')");
  check('type change number→amount keeps «فقط عدد صحیح» (no removal notice)', !/فقط عدد صحیح/.test(consequences), consequences);
  await clickSel('#fdCancel'); await sleep(120);
  await ev("editField('" + textId + "')"); await sleep(200);
  const textConsequences = await ev("typeChangeConsequences(FIELD_DRAFT,'email').join(' ')");
  check('type change text→email announces that the length limit is removed', /محدودیت طول پاسخ برداشته/.test(textConsequences), textConsequences);
  await clickSel('#fdCancel'); await sleep(120);
  await page.setViewportSize({ width: 390, height: 844 }); await sleep(200);
  await ev("editField('" + textId + "')"); await sleep(300); await shot('03-editor-text-length-390', true); await clickSel('#fdCancel');
  await page.setViewportSize({ width: 1440, height: 900 });

  // ── D. readiness: an invalid range set through the API blocks publish and the builder jumps to the control ──
  const current = await api('/api/forms/' + fid);
  const brokenFields = current.body.fields.map(f => String(f.id) === textId ? Object.assign({}, f, { minLen: 9, maxLen: 4 }) : f);
  const putBody = {}; for (const k of ['name', 'model', 'need', 'slug', 'ev', 'settings', 'purpose']) if (current.body[k] !== undefined) putBody[k] = current.body[k];
  const put = await api('/api/forms/' + fid, { method: 'PUT', body: JSON.stringify(Object.assign(putBody, { fields: brokenFields, expected_version: current.body.version })) });
  check('PUT with an inverted length range is stored (validation happens at publish)', put.status === 200, { status: put.status, body: put.body && JSON.stringify(put.body).slice(0, 200) });
  const readiness = await api('/api/forms/' + fid + '/readiness');
  const issue = (readiness.body && readiness.body.issues || []).find(i => i.code === 'invalid_length_range');
  check('readiness reports invalid_length_range with the field id', readiness.body && readiness.body.publishable === false && issue && String(issue.field_id) === textId, readiness.body && readiness.body.issues);
  await page.goto('about:blank'); await page.goto(O + '/create.html?fid=' + fid, { waitUntil: 'load' }); await waitFor(() => /hydrated=1/.test(page.url()), 4000); await sleep(800);
  await ev("go('s4')"); await sleep(1200);
  const jumpBtn = await page.$('[data-ready-field="' + textId + '"][data-ready-focus="#fdMinLen"]');
  check('publish step offers «بازکردن پرسش» for the length issue', !!jumpBtn, await txt('#readyBox'));
  if (jumpBtn) { await jumpBtn.click(); await sleep(600); }
  check('jump opens the editor on that field with focus on #fdMinLen', (await sheetOn('shField')) && (await ev("document.activeElement&&document.activeElement.id")) === 'fdMinLen' && toLatin(await page.$eval('#fdMinLen', el => el.value)) === '9');
  await shot('04-readiness-jump-length-1440');
  await typeInto('#fdMinLen', '۳'); await typeInto('#fdMaxLen', '۸'); await clickSel('#fdSave'); await sleep(300);
  await ev("go('s4')"); await sleep(300); await page.click('#publish'); await waitFor(async () => (await state()) === 'saved', 8000);
  const ready2 = await api('/api/forms/' + fid + '/readiness');
  check('after fixing in the builder, readiness is clean again', ready2.body && ready2.body.publishable === true, ready2.body && ready2.body.issues);
  const v = (await api('/api/forms/' + fid)).body.version;
  const pubRes = await api('/api/forms/' + fid + '/publish', { method: 'POST', body: JSON.stringify({ expected_version: v }) });
  check('form published', pubRes.status === 200 && pubRes.body && pubRes.body.status === 'published', pubRes.status);

  // ── E. API validation ──
  const jar = {}; const cookieHeader = () => Object.entries(jar).map(([k, v]) => k + '=' + v).join('; ');
  const pub = async (p, init) => { const r = await fetch(B + p, Object.assign({}, init || {}, { headers: Object.assign({ 'content-type': 'application/json', origin: B, cookie: cookieHeader() }, (init && init.headers) || {}) })); const sc = r.headers.getSetCookie ? r.headers.getSetCookie() : []; for (const c of sc) { const [kv] = c.split(';'); const [k, val] = kv.split('='); jar[k] = val; } return { status: r.status, body: await r.json().catch(() => null) }; };
  await pub('/api/public/forms/' + fid + '/draft');
  const patch = answers => pub('/api/public/forms/' + fid + '/draft', { method: 'PATCH', body: JSON.stringify({ answers }) });
  check('API: partial draft keeps a too-short text (minLen only at final submit)', (await patch({ [textId]: 'ab' })).status === 200);
  const tooLong = await patch({ [textId]: 'abcdefghi' });
  check('API: draft rejects text above maxLen with the field id', tooLong.status === 422 && (tooLong.body.detail.errors || []).some(e => String(e.field_id) === textId && /[8۸]/.test(e.message)), tooLong.body);
  check('API: area above maxLen rejected', (await patch({ [areaId]: 'ن'.repeat(21) })).status === 422);
  const dec = await patch({ [numberId]: '2.5' });
  check('API: decimal rejected for integer-only number', dec.status === 422 && (dec.body.detail.errors || []).some(e => String(e.field_id) === numberId && /صحیح/.test(e.message)), dec.body);
  check('API: integer accepted (Persian digits)', (await patch({ [numberId]: '۳' })).status === 200);
  check('API: amount without integer flag accepts a decimal', (await patch({ [amountId]: '2500.5' })).status === 200);
  const finalShort = await pub('/api/public/forms/' + fid + '/responses', { method: 'POST', body: JSON.stringify({ answers: { [textId]: 'ab', [numberId]: '3' } }) });
  check('API: final submit rejects text below minLen with «دست‌کم»', finalShort.status === 422 && (finalShort.body.detail.errors || []).some(e => String(e.field_id) === textId && /دست‌کم/.test(e.message)), finalShort.body);

  // ── F. public form in the browser ──
  const url = B + '/form.html?fid=' + encodeURIComponent(fid) + '&kind=reg';
  await page.goto('about:blank'); await page.goto(url, { waitUntil: 'load' }); await sleep(2500);
  await page.evaluate(() => { const b = [...document.querySelectorAll('button:not([disabled]), a.btn')].find(e => e.offsetParent !== null && /شروع/.test(e.textContent)); if (b) b.click(); }); await sleep(1200);
  const qmap = await ev("(window.__REG&&window.__REG.q||[]).map((q,i)=>({i,id:String(q.id),t:q.t,minLen:q.minLen,maxLen:q.maxLen,integer:q.integer}))");
  const row = id => qmap.find(q => q.id === id);
  check('public form received minLen/maxLen/integer in the question model', row(textId) && row(textId).minLen === 3 && row(textId).maxLen === 8 && row(areaId).maxLen === 20 && row(numberId).integer === true && !row(amountId).integer, qmap);
  const textRow = '.qrow[data-qrow="' + row(textId).i + '"] ', areaRow = '.qrow[data-qrow="' + row(areaId).i + '"] ', numRow = '.qrow[data-qrow="' + row(numberId).i + '"] ';
  check('public text input maxlength = owner max (8) and hint shows both limits', (await page.$eval(textRow + 'input.input:not([type=hidden])', el => el.getAttribute('maxlength'))) === '8' && /دست‌کم ۳ نویسه · حداکثر ۸ نویسه/.test(await txt(textRow)), await txt(textRow));
  check('public textarea maxlength = 20', (await page.$eval(areaRow + 'textarea.input', el => el.getAttribute('maxlength'))) === '20');
  check('public integer number uses inputmode=numeric with an integer placeholder and note', (await page.$eval(numRow + 'input.input:not([type=hidden])', el => el.getAttribute('inputmode') + '|' + el.getAttribute('placeholder'))) === 'numeric|مثلاً ۱۲' && /فقط عدد صحیح/.test(await txt(numRow)));
  await shot('05-public-length-integer-1440', true);
  const fill = async (sel, value) => page.$eval(sel, (e, v) => { e.focus(); e.value = v; e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); e.blur(); }, value);
  const submitClick = async () => { await page.evaluate(() => { const b = [...document.querySelectorAll('button:not([disabled]), a.btn')].filter(e => e.offsetParent !== null && /ثبت/.test(e.textContent) && !/انصراف|بازگشت|کپی/.test(e.textContent)).pop(); if (b) b.click(); }); await sleep(500); };
  const visibleErrors = () => page.evaluate(() => [...document.querySelectorAll('.qrow[data-qrow]')].map(r => { const e = r.querySelector('.field-error'); return e && !e.hidden && e.textContent.trim() ? [r.dataset.qrow, e.textContent.trim()] : null; }).filter(Boolean));
  await fill(textRow + 'input.input:not([type=hidden])', 'ab'); await fill(numRow + 'input.input:not([type=hidden])', '3');
  await submitClick(); let errs = await visibleErrors();
  check('browser: 2-char answer blocked with «دست‌کم ۳ نویسه»', errs.some(e => e[0] === String(row(textId).i) && /دست‌کم ۳ نویسه/.test(e[1])), errs);
  await shot('06-public-minlen-error-1440');
  await fill(textRow + 'input.input:not([type=hidden])', 'سارا'); await fill(numRow + 'input.input:not([type=hidden])', '2.5');
  await submitClick(); errs = await visibleErrors();
  check('browser: decimal blocked with «عدد صحیح»', errs.some(e => e[0] === String(row(numberId).i) && /عدد صحیح/.test(e[1])), errs);
  await fill(numRow + 'input.input:not([type=hidden])', '0'); await submitClick(); errs = await visibleErrors();
  check('browser: integer below min 1 still blocked by the bound', errs.some(e => e[0] === String(row(numberId).i)), errs);
  await fill(numRow + 'input.input:not([type=hidden])', '۷'); await fill(areaRow + 'textarea.input', 'خوب بود');
  await submitClick(); await sleep(1500); errs = await visibleErrors();
  check('browser: valid answers submit without field errors', errs.length === 0, errs);
  const done = await page.evaluate(async fid => { const r = await fetch('/api/public/forms/' + fid + '/draft'); const j = await r.json(); return { status: r.status, submitted: j && j.submitted }; }, fid);
  check('public submission completed', done.status === 200 && done.submitted === true, done);

  // ── G. stored response ──
  const responses = await api('/api/forms/' + fid + '/responses?limit=5'); const items = responses.body && responses.body.items || [];
  const answers = items[0] && (items[0].answers || items[0].data || {}) || {};
  check('owner sees the stored answers (text «سارا», number 7)', items.length === 1 && answers[textId] === 'سارا' && toLatin(answers[numberId]) === '7', answers);
  check('no page errors in the browser during the whole chain', errors.length === 0, errors.slice(0, 3));
  await b.close();
  fs.writeFileSync(path.join(out, 'log.txt'), lines.join('\n') + '\n');
  console.log('e2e-length-integer: ' + pass + ' قبول، ' + fail + ' خطا');
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('CRASH', e); fs.writeFileSync(path.join(out, 'log.txt'), lines.join('\n') + '\nCRASH ' + (e && e.stack || e) + '\n'); process.exit(1); });
