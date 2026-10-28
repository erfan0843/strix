// Parametrised real-browser acceptance over EVERY addable field type of the Nora form builder (test DB, synthetic owner).
// Per type: picker search → editor → type-specific settings (+ one invalid attempt) → save → server record → reopen & compare
// (field + editor controls) → publish → public control + invalid browser answer → valid answer → submit → server rejects
// invalid value through the API (PATCH draft) → stored response → CSV column.
// Usage: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<deps> NORA_REPO_UI=<ui> node e2e-field-types.cjs <outdir>
// Owner requests go through the server-side-session preview proxy (:8000); the visitor uses the backend origin (:8001).
const fs = require('node:fs'), path = require('node:path');
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const O = process.env.NORA_E2E_OWNER || 'http://127.0.0.1:8000', B = process.env.NORA_E2E_BACKEND || 'http://127.0.0.1:8001';
const out = process.argv[2] || 'shots/field-types'; fs.mkdirSync(out, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms)); const lines = []; let pass = 0, fail = 0;
const L = (m, x) => { const t = m + (x === undefined ? '' : ': ' + (typeof x === 'string' ? x : JSON.stringify(x))); lines.push(t); console.log(t); };
const MATRIX = {}; // type → { step: true/false/'n/a' }
const mark = (k, step, ok, extra) => { (MATRIX[k] = MATRIX[k] || {})[step] = ok; check('[' + k + '] ' + step, ok, extra); };
const check = (n, ok, extra) => { ok ? pass++ : fail++; L((ok ? 'PASS ' : 'FAIL ') + n + (extra === undefined || ok ? '' : ' · ' + JSON.stringify(extra).slice(0, 300))); };
const stamp = Date.now().toString(36);
async function api(p, init) { const r = await fetch(O + p, Object.assign({ headers: { 'content-type': 'application/json' } }, init || {})); return { status: r.status, body: await r.json().catch(() => null) }; }
async function apiText(p) { const r = await fetch(O + p); return { status: r.status, text: await r.text(), type: r.headers.get('content-type') || '' }; }
const LONG = n => 'ن'.repeat(n);
const OPTS3 = ['اول', 'دوم', 'سوم'];
const EXPECTED_OPTS = {}; // type → option labels expected on the server / in the editor
const toLatin = v => String(v == null ? '' : v).replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
// ── one structured spec per type: builder actions, expected stored config, public filler, API probes ──
// builder: { ph, min, max, minSel, maxSel, opts(add+rename), req, col }
// valid/invalid: API values (strings) — the server contract is the same for the browser path.
const SPEC = {
  text: { builder: { ph: 'مثلاً علی', req: true }, valid: 'یک متن کوتاه', invalid: LONG(1001), fill: 'input' },
  area: { builder: { ph: 'هرچه می‌خواهی' }, valid: 'یک توضیح طولانی‌تر در چند خط', invalid: LONG(3001), fill: 'textarea' },
  number: { builder: { min: '۱۰', max: '۹۹' }, valid: '۲۵', invalid: '5', fill: 'input', fillValue: '25', badBrowser: '5', stored: '25' },
  amount: { builder: { min: '۱۰۰۰', max: '۹۰۰۰۰' }, valid: '2500', invalid: '-5', fill: 'input', fillValue: '2500', badBrowser: '5' },
  choice: { builder: { opts: true, req: true }, valid: 'سوم', invalid: 'ناموجود', fill: 'opt', fillValue: 'سوم' },
  dropdown: { builder: { opts: true }, valid: 'سوم', invalid: 'ناموجود', fill: 'select', fillValue: 'سوم' },
  multi: { builder: { opts: true, minSel: '۱', maxSel: '۲' }, valid: 'اول، سوم', invalid: 'اول، دوم، سوم', fill: 'multi', fillValue: ['اول', 'سوم'], stored: 'اول، سوم' },
  imgchoice: { builder: { opts: true }, valid: 'سوم', invalid: 'ناموجود', fill: 'opt', fillValue: 'سوم' },
  yesno: { builder: {}, valid: 'بله', invalid: 'ناموجود', fill: 'opt', fillValue: 'بله' },
  gender: { builder: { optsAppend: 'دیگر' }, valid: 'دیگر', invalid: 'ناموجود', fill: 'opt', fillValue: 'دیگر' },
  marital: { builder: {}, valid: 'مجرد', invalid: 'ناموجود', fill: 'opt', fillValue: 'مجرد' },
  fullname: { builder: { ph: 'نام و نام خانوادگی' }, valid: 'سارا محمدی', invalid: LONG(121), fill: 'input' },
  mobile: { builder: {}, valid: '۰۹۱۲۳۴۵۶۷۸۹', invalid: '12345', partialLenient: true, fill: 'input', fillValue: '09123456789', badBrowser: '12345', stored: '09123456789' },
  nid: { builder: {}, valid: '0012345678', invalid: '123', fill: 'input', badBrowser: '123' },
  email: { builder: {}, valid: 'test@example.com', invalid: 'nope', fill: 'input', badBrowser: 'nope' },
  address: { builder: {}, valid: 'تهران، خیابان آزادی، پلاک ۱', invalid: LONG(1001), fill: 'textarea' },
  location: { builder: { col: false }, valid: 'میدان آزادی', invalid: LONG(181), fill: 'input' },
  province: { builder: {}, valid: 'تهران · تهران', invalid: LONG(161), fill: 'geo', stored: 'تهران · تهران' },
  uni: { builder: {}, valid: 'تهران · دانشگاه آزمون', invalid: LONG(201), fill: 'uni' },
  edu: { builder: {}, valid: 'کارشناسی', invalid: LONG(201), fill: 'list' },
  job: { builder: {}, valid: 'دانشجو', invalid: LONG(201), fill: 'list' },
  date: { builder: {}, valid: '۱۳۷۰/۰۵/۱۲', invalid: '1400/13/45', fill: 'pick', badBrowser: null },
  time: { builder: {}, valid: '10:30', invalid: '25:99', fill: 'pick' },
  datetime: { builder: {}, valid: '1404/08/05 ساعت 10:30', invalid: 'فردا', fill: 'pick' },
  slot: { builder: {}, valid: '10:30', invalid: '99:99', fill: 'pick' },
  rating: { builder: { min: '۲', max: '۴' }, valid: '3', invalid: '5', fill: 'rate', fillValue: '3' },
  scale: { builder: { min: '۱', max: '۷' }, valid: '4', invalid: '11', fill: 'range', fillValue: '4' },
  bars: { builder: { min: '۰', max: '۵' }, valid: '2', invalid: '9', fill: 'range', fillValue: '2' },
  terms: { builder: { req: true }, valid: 'پذیرفتم', invalid: 'نه', fill: 'terms' },
};
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
  const switchState = s => page.$eval(s, el => el.classList.contains('on')).catch(() => null);
  const setSwitch = async (s, on) => { if ((await switchState(s)) !== on) await page.click(s); };

  // ── A. builder: one form, every addable type added through the picker ──
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('about:blank'); await page.goto(O + '/create.html?need=reg', { waitUntil: 'load' }); await sleep(1500);
  check('capability contract resolved from the server (state ready)', await waitFor(() => ev("FORM_CAPABILITY_STATE==='ready'"), 10000), await ev('FORM_CAPABILITY_STATE'));
  await typeInto('#fTitle', 'همهٔ انواع ' + stamp);
  await ev("go('s2')"); await sleep(300); await ev("applyPack('empty','replace')"); await sleep(300);
  await ev("S.display='all'");
  const catalog = await ev("CATALOG.filter(c=>!typeOf(c.t).hidden).map(c=>({k:c.k,t:c.t,n:c.n,cat:c.cat||''}))");
  const addable = await ev("CATALOG.filter(c=>!typeOf(c.t).hidden&&fieldSupport(c.t).addable).map(c=>c.k)");
  L('catalog (visible)', catalog.map(c => c.k + '/' + c.t).join(' '));
  const types = Object.keys(SPEC);
  const specType = {}; const presetFor = {};
  for (const c of catalog) if (SPEC[c.t] && !presetFor[c.t]) presetFor[c.t] = c; // first preset per type (birth-date for date)
  check('every server-supported type has a spec and an addable catalog entry', types.every(t => presetFor[t] && addable.includes(presetFor[t].k)), types.filter(t => !presetFor[t] || !addable.includes(presetFor[t].k)));
  const FID_BY_TYPE = {};
  for (const t of types) {
    const c = presetFor[t], s = SPEC[t], bl = s.builder;
    await openPicker(); await sleep(150);
    await typeInto('#catSearch', c.n); await sleep(250);
    const hits = await page.$$eval('#catList [data-add]', xs => xs.map(x => x.dataset.add));
    mark(t, 'picker: search by name finds it first', hits[0] === c.k, { q: c.n, hits: hits.slice(0, 4) });
    await clickSel('#catList [data-add="' + c.k + '"]'); await sleep(350);
    mark(t, 'editor opens with the type tag', (await sheetOn('shField')) && (await txt('#fdType')).length > 0, await txt('#fdType'));
    const boxesOk = await ev("(()=>{const f=FIELD_DRAFT;const vis=FIELD_SETTINGS.filter(d=>settingVisible(d,f.t,f));const shown=[...document.querySelectorAll('#shField [id$=\"Box\"]')].filter(b=>b.style.display!=='none'&&!b.hidden).map(b=>'#'+b.id);const want=vis.map(s=>s.box).filter(Boolean);return {ok:want.every(w=>shown.includes(w))&&shown.filter(x=>FIELD_SETTINGS.some(s=>s.box===x)).every(x=>want.includes(x)),want,shown}})()");
    mark(t, 'visible setting boxes == FIELD_SETTINGS registry', boxesOk.ok, boxesOk);
    await typeInto('#fdTitle', c.n + ' ' + stamp.slice(-3));
    await typeInto('#fdHelp', 'راهنمای ' + c.n);
    if (bl.req) await setSwitch('#fdReq', true); else await setSwitch('#fdReq', false);
    if (bl.ph !== undefined) await typeInto('#fdPlaceholder', bl.ph);
    if (bl.col === false) await setSwitch('#fdCol', false);
    // one invalid attempt per settings family
    if (bl.min !== undefined) {
      await typeInto('#fdMin', bl.max); await typeInto('#fdMax', bl.min);
      const rejected = !(await ev('saveField()')) && !(await page.$eval('#fdIssues', el => el.hidden));
      mark(t, 'editor rejects min > max and keeps the sheet open', rejected && await sheetOn('shField'), await txt('#fdIssues'));
      await typeInto('#fdMin', bl.min); await typeInto('#fdMax', bl.max);
    }
    if (bl.opts) {
      await clickSel('#fdAddOption'); await sleep(100);
      const n = await page.$$eval('#fdOptions [data-optl]', xs => xs.length);
      for (let i = 0; i < n; i++) await typeInto('[data-optl="' + i + '"]', i < OPTS3.length ? OPTS3[i] : 'گزینه ' + i);
      // duplicate option must be rejected
      await typeInto('[data-optl="' + (n - 1) + '"]', OPTS3[0]);
      const dup = !(await ev('saveField()')) && !(await page.$eval('#fdIssues', el => el.hidden));
      mark(t, 'editor rejects duplicate options', dup, await txt('#fdIssues'));
      await typeInto('[data-optl="' + (n - 1) + '"]', OPTS3[n - 1] || 'سوم');
      if (bl.minSel !== undefined) {
        await typeInto('#fdMinSelect', '۳'); await typeInto('#fdMaxSelect', '۲');
        const badSel = !(await ev('saveField()'));
        mark(t, 'editor rejects minSelect > maxSelect', badSel, await txt('#fdIssues'));
        await typeInto('#fdMinSelect', bl.minSel); await typeInto('#fdMaxSelect', bl.maxSel);
      }
    }
    if (bl.opts) EXPECTED_OPTS[t] = OPTS3.slice(0, await page.$$eval('#fdOptions [data-optl]', xs => xs.length));
    if (bl.optsAppend) {
      const defaults = await page.$$eval('#fdOptions [data-optl]', xs => xs.map(x => x.value));
      await clickSel('#fdAddOption'); await sleep(100);
      await typeInto('[data-optl="' + defaults.length + '"]', bl.optsAppend);
      EXPECTED_OPTS[t] = defaults.concat([bl.optsAppend]);
      mark(t, 'controlled list keeps its defaults and accepts an extra option', (await page.$$eval('#fdOptions [data-optl]', xs => xs.map(x => x.value))).join('|') === EXPECTED_OPTS[t].join('|'), defaults);
    }
    await clickSel('#fdSave'); await sleep(250);
    mark(t, 'valid settings save and close the editor', !(await sheetOn('shField')), await txt('#fdIssues'));
    if (await sheetOn('shField')) { await ev('closeSheets()'); await sleep(150); }
    FID_BY_TYPE[t] = await ev('String(S.fields[S.fields.length-1].id)');
    const f = await ev('JSON.stringify(S.fields[S.fields.length-1])');
    const fo = JSON.parse(f);
    mark(t, 'canvas field has the right type and preset', fo.t === t && (fo.preset || t) === c.k && fo.l === c.n + ' ' + stamp.slice(-3), { t: fo.t, preset: fo.preset, l: fo.l });
  }
  check('all types added once (' + types.length + ' fields)', (await ev('S.fields.length')) === types.length, await ev('S.fields.length'));
  await shot('01-canvas-all-types-1440', true);

  // ── B. save → server record ──
  await ev("go('s4')"); await sleep(300); await page.click('#publish');
  check('first save pinned the URL with fid= and state «ذخیره شد»', await waitFor(() => /[?&]fid=/.test(page.url()), 8000) && await waitFor(async () => (await state()) === 'saved', 8000), await state());
  const fid = (page.url().match(/[?&]fid=([^&]+)/) || [])[1]; L('form id', fid);
  const serverForm = await api('/api/forms/' + fid);
  check('server stored every field in order', serverForm.status === 200 && serverForm.body.fields.map(f => f.t).join(',') === types.join(','), serverForm.body && serverForm.body.fields.map(f => f.t).join(','));
  const sf = {}; for (const f of serverForm.body.fields) sf[f.t] = f;
  for (const t of types) {
    const f = sf[t], bl = SPEC[t].builder, c = presetFor[t]; if (!f) { mark(t, 'server record has the settings', false, 'missing'); continue; }
    const want = [];
    want.push(['preset', (f.preset || t) === c.k], ['help', f.help === 'راهنمای ' + c.n], ['req', !!f.req === !!bl.req]);
    if (bl.ph !== undefined) want.push(['placeholder', f.placeholder === bl.ph]);
    if (bl.min !== undefined) want.push(['min', String(f.min) === String(+bl.min.replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))], ['max', String(f.max) === String(+bl.max.replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))]);
    if (EXPECTED_OPTS[t]) want.push(['opts', JSON.stringify((f.opts || []).map(o => o.l || o)) === JSON.stringify(EXPECTED_OPTS[t])]);
    if (bl.minSel !== undefined) want.push(['minSelect', f.minSelect === 1], ['maxSelect', f.maxSelect === 2]);
    if (bl.col === false) want.push(['col', f.col === false]);
    mark(t, 'server record has the settings', want.every(w => w[1]), want.filter(w => !w[1]).map(w => w[0]).concat([JSON.stringify(f).slice(0, 160)]));
  }
  // ── C. reopen by fid: fields + editor controls must match ──
  await page.goto('about:blank'); await page.goto(O + '/create.html?fid=' + fid, { waitUntil: 'load' });
  await waitFor(() => /hydrated=1/.test(page.url()), 4000);
  check('reopened on the server version as «ذخیره شد»', await waitFor(async () => (await state()) === 'saved', 8000) && (await ev('ACTIVE_SERVER_FORM&&ACTIVE_SERVER_FORM.version')) === serverForm.body.version, await state());
  await ev("go('s2')"); await sleep(300);
  for (const t of types) {
    const bl = SPEC[t].builder, c = presetFor[t], id = FID_BY_TYPE[t];
    const local = await ev("JSON.stringify(S.fields.find(f=>String(f.id)==='" + id + "')||null)");
    const lf = JSON.parse(local), rf = sf[t];
    const same = lf && lf.t === rf.t && lf.l === rf.l && (lf.preset || t) === (rf.preset || t) && String(lf.min ?? '') === String(rf.min ?? '') && String(lf.max ?? '') === String(rf.max ?? '') && JSON.stringify((lf.opts || []).map(o => o.l || o)) === JSON.stringify((rf.opts || []).map(o => o.l || o)) && (lf.help || '') === (rf.help || '') && (lf.placeholder || '') === (rf.placeholder || '') && !!lf.req === !!rf.req && (lf.col !== false) === (rf.col !== false);
    mark(t, 'restored field equals the server record', same, { local: local && local.slice(0, 160) });
    await ev("editField('" + id + "')"); await sleep(200);
    const ctl = await ev("(()=>{const v=s=>{const e=document.querySelector(s);return e?e.value:null};const on=s=>{const e=document.querySelector(s);return e?e.classList.contains('on'):null};return {title:v('#fdTitle'),help:v('#fdHelp'),req:on('#fdReq'),col:on('#fdCol'),ph:v('#fdPlaceholder'),min:v('#fdMin'),max:v('#fdMax'),minSel:v('#fdMinSelect'),maxSel:v('#fdMaxSelect'),opts:[...document.querySelectorAll('#fdOptions [data-optl]')].map(i=>i.value),type:document.querySelector('#fdType').textContent.trim()}})()");
    const okCtl = ctl.title === c.n + ' ' + stamp.slice(-3) && ctl.help === 'راهنمای ' + c.n && ctl.req === !!bl.req && ctl.col === (bl.col !== false)
      && (bl.ph === undefined || ctl.ph === bl.ph)
      && (bl.min === undefined || (toLatin(ctl.min) === toLatin(bl.min) && toLatin(ctl.max) === toLatin(bl.max)))
      && (EXPECTED_OPTS[t] === undefined || JSON.stringify(ctl.opts) === JSON.stringify(EXPECTED_OPTS[t]))
      && (bl.minSel === undefined || (toLatin(ctl.minSel) === '1' && toLatin(ctl.maxSel) === '2'));
    mark(t, 'editor controls show the stored settings after reopen', okCtl, ctl);
    await clickSel('#fdCancel'); await sleep(120);
    if (await sheetOn('shField')) { await ev('closeSheets()'); mark(t, 'cancel on untouched editor closes without prompt', false); }
  }
  await page.setViewportSize({ width: 390, height: 844 }); await sleep(300);
  await ev("editField('" + FID_BY_TYPE.multi + "')"); await sleep(300); await shot('02-editor-multi-390', true); await clickSel('#fdCancel');
  await ev("editField('" + FID_BY_TYPE.rating + "')"); await sleep(300); await shot('03-editor-rating-390'); await clickSel('#fdCancel');
  await page.setViewportSize({ width: 1440, height: 900 });

  // ── D. publish ──
  const ready = await api('/api/forms/' + fid + '/readiness');
  check('readiness is clean for the all-types form', ready.body && ready.body.publishable === true, ready.body && ready.body.issues);
  await ev("go('s4')"); await sleep(600);
  const publishVisible = await page.$eval('#donePublish', el => el.style.display !== 'none' && !el.disabled).catch(() => false);
  if (publishVisible) { await page.click('#donePublish'); await sleep(1500); }
  else { const pub = await api('/api/forms/' + fid + '/publish', { method: 'POST', body: JSON.stringify({ expected_version: (await api('/api/forms/' + fid)).body.version }) }); L('publish via API (button hidden)', pub.status); }
  const published = await api('/api/forms/' + fid);
  check('form is published on the server', published.body && published.body.status === 'published', published.body && published.body.status);

  // ── E. server validation through the public API (draft PATCH = same validator, partial) ──
  const jar = {}; const cookieHeader = () => Object.entries(jar).map(([k, v]) => k + '=' + v).join('; ');
  const pub = async (p, init) => { const r = await fetch(B + p, Object.assign({}, init || {}, { headers: Object.assign({ 'content-type': 'application/json', origin: B, cookie: cookieHeader() }, (init && init.headers) || {}) })); const sc = r.headers.getSetCookie ? r.headers.getSetCookie() : [r.headers.get('set-cookie')].filter(Boolean); for (const c of sc) { const m = /^([^=]+)=([^;]*)/.exec(c); if (m) jar[m[1]] = m[2]; } return { status: r.status, body: await r.json().catch(() => null) }; };
  const draft = await pub('/api/public/forms/' + fid + '/draft');
  check('public draft opened via API (cookie session)', draft.status === 200 && Object.keys(jar).length > 0, draft.status);
  for (const t of types) {
    const id = FID_BY_TYPE[t], s = SPEC[t];
    const bad = await pub('/api/public/forms/' + fid + '/draft', { method: 'PATCH', body: JSON.stringify({ answers: { [id]: s.invalid } }) });
    const errs = bad.body && bad.body.detail && bad.body.detail.errors || [];
    if (s.partialLenient) mark(t, 'draft PATCH keeps an incomplete value while typing (partial, by design)', bad.status === 200, { status: bad.status, errs: errs.slice(0, 2) });
    else mark(t, 'server rejects an invalid value (422 with field_id)', bad.status === 422 && errs.some(e => String(e.field_id) === id), { status: bad.status, errs: errs.slice(0, 2) });
    const good = await pub('/api/public/forms/' + fid + '/draft', { method: 'PATCH', body: JSON.stringify({ answers: { [id]: s.valid } }) });
    mark(t, 'server accepts the valid value', good.status === 200, { status: good.status, body: good.body });
  }
  const allBad = {}; for (const t of types) allBad[FID_BY_TYPE[t]] = SPEC[t].invalid;
  const finalBad = await pub('/api/public/forms/' + fid + '/responses', { method: 'POST', body: JSON.stringify({ answers: allBad }) });
  const finalErrs = finalBad.body && finalBad.body.detail && finalBad.body.detail.errors || [];
  for (const t of types) mark(t, 'final submit rejects the invalid value (422, field_id, message)', finalBad.status === 422 && finalErrs.some(e => String(e.field_id) === FID_BY_TYPE[t] && e.message), { status: finalBad.status, errs: finalErrs.filter(e => String(e.field_id) === FID_BY_TYPE[t]) });
  const unknown = await pub('/api/public/forms/' + fid + '/draft', { method: 'PATCH', body: JSON.stringify({ answers: { ['nope-' + stamp]: 'x' } }) });
  check('unknown field id is rejected by the server', unknown.status === 422 || unknown.status === 400, unknown.status);

  // ── F. public form in the browser: every control renders, invalid browser answers are flagged, valid ones submit ──
  const url = B + '/form.html?fid=' + encodeURIComponent(fid) + '&kind=reg';
  await page.goto('about:blank'); await page.goto(url, { waitUntil: 'load' }); await sleep(2500);
  await page.evaluate(() => { const b = [...document.querySelectorAll('button:not([disabled]), a.btn')].find(e => e.offsetParent !== null && /شروع/.test(e.textContent)); if (b) b.click(); }); await sleep(1200);
  const qmap = await ev("(window.__REG&&window.__REG.q||[]).map((q,i)=>({i,id:String(q.id),t:q.t}))");
  check('public form renders all questions on one page (display=all)', qmap.length === types.length && (await page.$$('.qrow[data-qrow]')).length === types.length, { q: qmap.length, rows: (await page.$$('.qrow[data-qrow]')).length });
  const rowOf = t => qmap.find(q => q.id === FID_BY_TYPE[t]);
  const controlPresent = {
    input: 'input.input:not([type=hidden])', textarea: 'textarea.input', select: 'select[data-qdrop]', opt: '[data-qsel] .opt', multi: '[data-qmul] .opt', geo: '[data-qgeo] .gp', uni: '[data-qlist="uni"] .up', list: '[data-qlist] .lp', pick: '[data-qpick] select', rate: '[data-qrate] [data-qv]', range: 'input[type=range][data-qrange]', terms: '[data-qterm]'
  };
  for (const t of types) {
    const r = rowOf(t); if (!r) { mark(t, 'public control rendered', false, 'row missing'); continue; }
    const sel = '.qrow[data-qrow="' + r.i + '"] ' + controlPresent[SPEC[t].fill];
    const n = (await page.$$(sel)).length;
    const extra = await page.evaluate(([i, t]) => { const row = document.querySelector('.qrow[data-qrow="' + i + '"]'); const out = { help: /راهنمای/.test(row.textContent) }; if (t === 'rating') { const box = row.querySelector('[data-qrate]'); out.stars = box.querySelectorAll('[data-qv]').length; out.min = box.dataset.min; out.max = box.dataset.max; } if (t === 'scale' || t === 'bars') { const rg = row.querySelector('input[type=range]'); out.min = rg.min; out.max = rg.max; } if (t === 'multi') out.hint = /حداقل ۱ · حداکثر ۲/.test(row.textContent); out.ph = (row.querySelector('input.input:not([type=hidden]),textarea.input') || {}).placeholder; return out; }, [r.i, t]);
    let ok = n > 0 && extra.help;
    if (t === 'rating') ok = ok && extra.stars === 3 && extra.min === '2' && extra.max === '4';
    if (t === 'scale') ok = ok && extra.min === '1' && extra.max === '7';
    if (t === 'bars') ok = ok && extra.min === '0' && extra.max === '5';
    if (t === 'multi') ok = ok && extra.hint;
    if (SPEC[t].builder.ph) ok = ok && extra.ph === SPEC[t].builder.ph;
    mark(t, 'public control rendered with the configured settings', ok, { n, extra });
  }
  await shot('04-public-all-types-1440', true);
  // fill helper (runs in page)
  const fillInPage = async (i, kind, value) => page.evaluate(([i, kind, value]) => {
    const row = document.querySelector('.qrow[data-qrow="' + i + '"]'); if (!row) return 'norow';
    const fire = (el, ev) => el.dispatchEvent(new Event(ev, { bubbles: true }));
    const setSel = (sel, v) => { const e = row.querySelector(sel); if (!e) return false; const opt = [...e.options].find(o => o.value === v) || (typeof v === 'number' ? e.options[v] : null); if (!opt) return false; e.value = opt.value; fire(e, 'change'); return true; };
    if (kind === 'input' || kind === 'textarea') { const e = row.querySelector(kind === 'input' ? 'input.input:not([type=hidden])' : 'textarea.input'); e.focus(); e.value = value; fire(e, 'input'); fire(e, 'change'); e.blur(); return 'ok'; }
    if (kind === 'select') return setSel('select[data-qdrop]', value) ? 'ok' : 'noopt';
    if (kind === 'opt') { const o = [...row.querySelectorAll('[data-qsel] .opt')].find(x => x.textContent.trim() === value); if (!o) return 'noopt'; o.click(); return 'ok'; }
    if (kind === 'multi') { for (const v of value) { const o = [...row.querySelectorAll('[data-qmul] .opt')].find(x => x.textContent.trim() === v); if (!o) return 'noopt'; if (!o.classList.contains('on')) o.click(); } return 'ok'; }
    if (kind === 'pick') { const box = row.querySelector('[data-qpick]'); const kindp = box.dataset.qpick; if (kindp !== 'time') { if (!setSel('.pk1', 1)) return 'noyear'; if (!setSel('.pk2', 1)) return 'nomonth'; if (!setSel('.pk3', 12)) return 'noday'; } if (kindp !== 'date') { if (!setSel('.pk4', 11)) return 'nohour'; if (!setSel('.pk5', 31)) return 'nominute'; } return 'ok'; }
    if (kind === 'geo') { if (!setSel('.gp', 'تهران')) return 'noprov'; if (!setSel('.gc', 1)) return 'nocity'; return 'ok'; }
    if (kind === 'list') { const lp = row.querySelector('.lp'); if (!lp || lp.tagName !== 'SELECT') return 'nolist'; const opt = [...lp.options].find(o => o.value === value) || [...lp.options].find(o => o.value && o.value !== 'سایر'); lp.value = opt.value; fire(lp, 'change'); return 'ok'; }
    if (kind === 'rate') { const o = row.querySelector('[data-qrate] [data-qv="' + value + '"]'); if (!o) return 'nostar'; o.click(); return 'ok'; }
    if (kind === 'range') { const e = row.querySelector('input[type=range]'); e.value = value; fire(e, 'input'); fire(e, 'change'); return 'ok'; }
    if (kind === 'terms') { const o = row.querySelector('[data-qterm]'); if (o.dataset.val !== '1') o.click(); return 'ok'; }
    return 'unknown';
  }, [i, kind, value]);
  const fillUni = async (i) => {
    const row = '.qrow[data-qrow="' + i + '"] ';
    await page.selectOption(row + '.up', 'تهران'); await sleep(900);
    const hasOther = await page.$eval(row + '.lp', el => [...el.options].some(o => o.value === '__other__')).catch(() => false);
    if (!hasOther) return 'nolist';
    await page.selectOption(row + '.lp', '__other__'); await sleep(200);
    await page.fill(row + '.uni-other', 'دانشگاه آزمون'); await page.$eval(row + '.uni-other', el => { el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); });
    return 'ok';
  };
  const submitClick = async () => { await page.evaluate(() => { const b = [...document.querySelectorAll('button:not([disabled]), a.btn')].filter(e => e.offsetParent !== null && /ثبت/.test(e.textContent) && !/انصراف|بازگشت|کپی/.test(e.textContent)); if (b[0]) b[0].click(); }); await sleep(1200); };
  const visibleErrors = () => page.evaluate(() => [...document.querySelectorAll('.qrow[data-qrow]')].map(r => { const e = r.querySelector('.field-error'); return e && !e.hidden && e.textContent.trim() ? [r.dataset.qrow, e.textContent.trim().slice(0, 80)] : null; }).filter(Boolean));
  // F1: required questions block submission while empty (the form reports the first problem in order)
  const reqTypes = types.filter(t => SPEC[t].builder.req);
  for (const t of reqTypes) {
    const r = rowOf(t);
    // everything before this row must be valid, so fill earlier rows first
    for (const u of types) { if (u === t) break; const ru = rowOf(u), su = SPEC[u]; if (su.fill === 'uni') await fillUni(ru.i); else await fillInPage(ru.i, su.fill, su.fillValue !== undefined ? su.fillValue : su.valid); }
    await submitClick();
    const errs = await visibleErrors();
    mark(t, 'required question blocks submission when empty', errs.some(e => e[0] === String(r.i) && e[1].length > 3), errs);
    if (t === reqTypes[0]) await shot('05-public-required-error-1440');
    const s = SPEC[t]; if (s.fill === 'uni') await fillUni(r.i); else await fillInPage(r.i, s.fill, s.fillValue !== undefined ? s.fillValue : s.valid);
  }
  // F2: valid answers for everything
  for (const t of types) {
    const r = rowOf(t), s = SPEC[t];
    const res = s.fill === 'uni' ? await fillUni(r.i) : await fillInPage(r.i, s.fill, s.fillValue !== undefined ? s.fillValue : s.valid);
    mark(t, 'public control accepts a valid answer', res === 'ok', res);
  }
  // F3: one invalid browser value at a time (others valid) → error on that row with a message, then restore
  const badTypes = types.filter(t => SPEC[t].badBrowser);
  for (const t of badTypes) {
    const r = rowOf(t), s = SPEC[t];
    await fillInPage(r.i, s.fill, s.badBrowser); await submitClick();
    const errs = await visibleErrors();
    mark(t, 'public form flags an invalid browser answer with a how-to-fix message', errs.some(e => e[0] === String(r.i) && e[1].length > 3), errs);
    if (t === 'number') { await sleep(1200); const after = await visibleErrors(); mark(t, 'local how-to-fix message (with the bound) survives the draft 422 from the server', after.some(e => e[0] === String(r.i) && /۱۰|10/.test(e[1])), after); }
    if (t === badTypes[0]) await shot('06-public-invalid-answer-1440');
    await fillInPage(r.i, s.fill, s.fillValue !== undefined ? s.fillValue : s.valid);
  }
  await sleep(600);
  const stale = await page.$$eval('.field-invalid,[aria-invalid="true"]', xs => xs.map(x => (x.getAttribute('aria-label') || x.id || x.className).slice(0, 40)));
  check('no stale invalid markers remain once every answer is valid (radio groups included)', stale.length === 0, stale);
  const draftStatus = await txt('#draftStatus');
  check('draft status is not stuck on a failure once answers are valid', !/ذخیره نمی‌شود|انجام نشد/.test(draftStatus), draftStatus);
  await submitClick(); await sleep(1500);
  const errs2 = await visibleErrors();
  check('no field errors remain after valid answers', errs2.length === 0, errs2);
  const done = await page.evaluate(async fid => { const r = await fetch('/api/public/forms/' + fid + '/draft'); const j = await r.json(); return { status: r.status, submitted: j && j.submitted }; }, fid);
  check('public submission completed (server draft submitted=true)', done.status === 200 && done.submitted === true, done);
  await shot('07-public-done-1440');

  // ── G. owner: stored response per type + CSV ──
  const responses = await api('/api/forms/' + fid + '/responses?limit=20');
  const items = responses.body && responses.body.items || [];
  check('owner sees exactly one response', responses.status === 200 && items.length === 1, { status: responses.status, n: items.length });
  const answers = items[0] && (items[0].answers || items[0].data || {}) || {};
  const flat = JSON.stringify(items[0] || {});
  for (const t of types) {
    const s = SPEC[t], id = FID_BY_TYPE[t];
    const stored0 = answers[id] !== undefined ? answers[id] : null, stored = Array.isArray(stored0) ? stored0.join('، ') : stored0;
    let okStored;
    if (s.fill === 'pick' || s.fill === 'geo' || s.fill === 'list' || s.fill === 'uni') okStored = stored !== null && String(stored).length > 0;
    else if (s.stored) okStored = String(stored) === s.stored || String(stored).replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)) === s.stored;
    else okStored = String(stored).replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)) === String(s.fillValue !== undefined ? s.fillValue : s.valid).replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d));
    mark(t, 'stored answer matches what the visitor entered', okStored, { stored, want: s.stored || s.fillValue || s.valid });
  }
  const csv = await apiText('/api/forms/' + fid + '/responses?format=csv');
  const header = (csv.text.split(/\r?\n/)[0] || '');
  check('CSV export served through the real endpoint', csv.status === 200 && /csv/.test(csv.type), { status: csv.status, type: csv.type });
  for (const t of types) {
    const title = presetFor[t].n + ' ' + stamp.slice(-3);
    const present = header.includes(title);
    if (SPEC[t].builder.col === false) mark(t, 'CSV omits the column when «ستون در خروجی» is off', !present, header.slice(0, 200));
    else mark(t, 'CSV has the question column', present, header.slice(0, 200));
  }
  check('CSV row contains the stored answers (sample: text, choice, mobile)', csv.text.includes('یک متن کوتاه') && csv.text.includes('سوم') && csv.text.includes('09123456789'), csv.text.split(/\r?\n/)[1] && csv.text.split(/\r?\n/)[1].slice(0, 200));
  check('no page errors in the browser during the whole chain', errors.length === 0, errors.slice(0, 3));
  await b.close();
  // per-type matrix
  const steps = [...new Set(Object.values(MATRIX).flatMap(m => Object.keys(m)))];
  const md = ['| نوع | ' + steps.map((s, i) => 'م' + (i + 1)).join(' | ') + ' | نتیجه |', '|---|' + steps.map(() => '---').join('|') + '|---|'];
  for (const t of types) { const m = MATRIX[t] || {}; const vals = steps.map(s => m[s] === undefined ? '·' : m[s] ? '✓' : '✗'); md.push('| ' + t + ' | ' + vals.join(' | ') + ' | ' + (Object.values(m).every(Boolean) ? 'قبول' : 'خطا') + ' |'); }
  md.push('', ...steps.map((s, i) => 'م' + (i + 1) + ' = ' + s));
  fs.writeFileSync(path.join(out, 'matrix.md'), md.join('\n') + '\n');
  fs.writeFileSync(path.join(out, 'matrix.json'), JSON.stringify({ fid, types, matrix: MATRIX }, null, 1));
  fs.writeFileSync(path.join(out, 'log.txt'), lines.join('\n') + '\n');
  console.log('e2e-field-types: ' + pass + ' قبول، ' + fail + ' خطا');
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('CRASH', e); fs.writeFileSync(path.join(out, 'log.txt'), lines.join('\n') + '\nCRASH ' + (e && e.stack || e) + '\n'); process.exit(1); });
