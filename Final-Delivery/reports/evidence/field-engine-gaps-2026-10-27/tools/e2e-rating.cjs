// Real-browser acceptance for the public star control (rating) of the Nora form: default 1..5, custom 2..4, single 3..3.
// Checks that stored value, aria-checked radio, number of lit stars, hidden answer, server draft and stored response agree
// for every star, after clear, after reload (server draft restore), after an out-of-range restored value and via keyboard.
// Usage: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<deps> NORA_REPO_UI=<ui> node e2e-rating.cjs <outdir>
const fs = require('node:fs'), path = require('node:path');
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const O = process.env.NORA_E2E_OWNER || 'http://127.0.0.1:8000', B = process.env.NORA_E2E_BACKEND || 'http://127.0.0.1:8001';
const out = process.argv[2] || 'shots/rating'; fs.mkdirSync(out, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms)); let pass = 0, fail = 0; const lines = [];
const L = (m, x) => { const t = m + (x === undefined ? '' : ': ' + (typeof x === 'string' ? x : JSON.stringify(x))); lines.push(t); console.log(t); };
const check = (n, ok, extra) => { ok ? pass++ : fail++; L((ok ? 'PASS ' : 'FAIL ') + n + (extra === undefined || ok ? '' : ' · ' + JSON.stringify(extra).slice(0, 400))); };
const stamp = Date.now().toString(36);
const fa = n => String(n).replace(/[0-9]/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
async function api(p, init) { const r = await fetch(O + p, Object.assign({ headers: { 'content-type': 'application/json' } }, init || {})); return { status: r.status, body: await r.json().catch(() => null) }; }
const CASES = [
  { key: 'default', title: 'ستارهٔ پیش‌فرض', min: '', max: '', lo: 1, hi: 5, req: false },
  { key: 'custom', title: 'ستارهٔ ۲ تا ۴', min: '۲', max: '۴', lo: 2, hi: 4, req: true },
  { key: 'single', title: 'ستارهٔ تک‌مقداری', min: '۳', max: '۳', lo: 3, hi: 3, req: false },
];
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
  const setSwitch = async (s, on) => { const cur = await page.$eval(s, el => el.classList.contains('on')).catch(() => null); if (cur !== on) await page.click(s); };

  // ── A. owner builds a form with three star questions ──
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('about:blank'); await page.goto(O + '/create.html?need=reg', { waitUntil: 'load' }); await sleep(1500);
  check('capability contract ready', await waitFor(() => ev("FORM_CAPABILITY_STATE==='ready'"), 10000));
  await typeInto('#fTitle', 'ستاره‌ها ' + stamp);
  await ev("go('s2')"); await sleep(300); await ev("applyPack('empty','replace')"); await sleep(300); await ev("S.display='all'");
  const FID = {};
  for (const c of CASES) {
    if (!(await sheetOn('shAdd'))) { await clickSel('#addBottom'); await sleep(250); }
    await typeInto('#catSearch', 'ستاره'); await sleep(250);
    await clickSel('#catList [data-add="rating"]'); await sleep(350);
    await typeInto('#fdTitle', c.title);
    await setSwitch('#fdReq', c.req);
    if (c.min !== '') await typeInto('#fdMin', c.min);
    if (c.max !== '') await typeInto('#fdMax', c.max);
    await clickSel('#fdSave'); await sleep(250);
    check('[' + c.key + '] editor saved the star range', !(await sheetOn('shField')), await txt('#fdIssues'));
    FID[c.key] = await ev('String(S.fields[S.fields.length-1].id)');
    const f = JSON.parse(await ev('JSON.stringify(S.fields[S.fields.length-1])'));
    check('[' + c.key + '] canvas field stores min/max as configured', f.t === 'rating' && String(f.min || '') === (c.min ? String(c.lo) : '') && String(f.max || '') === (c.max ? String(c.hi) : ''), { min: f.min, max: f.max });
  }
  await ev("go('s4')"); await sleep(300); await page.click('#publish');
  check('form saved on the server', await waitFor(() => /[?&]fid=/.test(page.url()), 8000) && await waitFor(async () => (await state()) === 'saved', 8000), await state());
  const fid = (page.url().match(/[?&]fid=([^&]+)/) || [])[1]; L('form id', fid);
  const ready = await api('/api/forms/' + fid + '/readiness');
  check('readiness clean (single-value star range accepted by the server contract)', ready.body && ready.body.publishable === true, ready.body && ready.body.issues);
  const pub = await api('/api/forms/' + fid + '/publish', { method: 'POST', body: JSON.stringify({ expected_version: (await api('/api/forms/' + fid)).body.version }) });
  check('published', pub.status === 200, pub.status);

  // ── B. public: every star, clear, reload, out-of-range, keyboard ──
  const url = B + '/form.html?fid=' + encodeURIComponent(fid) + '&kind=reg';
  await page.goto('about:blank'); await page.goto(url, { waitUntil: 'load' }); await sleep(2500);
  await page.evaluate(() => { const b = [...document.querySelectorAll('button:not([disabled]), a.btn')].find(e => e.offsetParent !== null && /شروع/.test(e.textContent)); if (b) b.click(); }); await sleep(1200);
  const qmap = await ev("(window.__REG&&window.__REG.q||[]).map((q,i)=>({i,id:String(q.id),t:q.t,min:q.min,max:q.max}))");
  L('public questions', qmap);
  const rowOf = key => qmap.find(q => q.id === FID[key]);
  // one explicit reading of the control state
  const readState = i => page.evaluate(i => {
    const box = document.querySelector('[data-qrate="' + i + '"]'); if (!box) return null;
    const radios = [...box.querySelectorAll('[role="radio"]')];
    const q = window.__REG.q[i], key = String(q.id == null ? (q.k || i) : q.id);
    const payload = window.__NORA_PUBLIC_FORM_COLLECT ? window.__NORA_PUBLIC_FORM_COLLECT().answers[key] : undefined;
    return { val: box.dataset.val, min: box.dataset.min, max: box.dataset.max, stars: radios.map(r => r.dataset.qv),
      checked: radios.filter(r => r.getAttribute('aria-checked') === 'true').map(r => r.dataset.qv),
      lit: radios.filter(r => r.classList.contains('on')).map(r => r.dataset.qv),
      tab0: radios.filter(r => r.tabIndex === 0).map(r => r.dataset.qv),
      clearHidden: (box.querySelector('[data-qrate-clear]') || {}).hidden, payload: payload === undefined ? '' : String(payload) };
  }, i);
  const expectConsistent = (label, s, value, lo) => {
    if (value == null) { check(label + ': cleared (no value, nothing checked, nothing lit, clear button hidden)', s.val === '' && s.checked.length === 0 && s.lit.length === 0 && s.clearHidden === true && s.tab0.join() === String(lo) && s.payload === '', s); return; }
    const wantLit = []; for (let v = lo; v <= value; v++) wantLit.push(String(v));
    check(label + ': value ' + value + ' ⇒ one aria-checked star, ' + wantLit.length + ' lit star(s) from the range start, clear visible', s.val === String(value) && s.checked.join() === String(value) && s.lit.join() === wantLit.join() && s.clearHidden === false && s.tab0.join() === String(value) && s.payload.replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)) === String(value), s);
  };
  for (const c of CASES) {
    const r = rowOf(c.key); if (!r) { check('[' + c.key + '] row rendered', false); continue; }
    const s0 = await readState(r.i);
    check('[' + c.key + '] public control renders exactly the configured stars ' + c.lo + '..' + c.hi, s0 && s0.stars.join() === Array.from({ length: c.hi - c.lo + 1 }, (_, k) => String(c.lo + k)).join() && s0.min === String(c.lo) && s0.max === String(c.hi), s0);
    expectConsistent('[' + c.key + '] initial', s0, null, c.lo);
    for (let v = c.lo; v <= c.hi; v++) {
      await page.click('[data-qrate="' + r.i + '"] [data-qv="' + v + '"]'); await sleep(120);
      expectConsistent('[' + c.key + '] click', await readState(r.i), v, c.lo);
    }
    // step down again (from hi to lo) — lit count must shrink, not stick
    await page.click('[data-qrate="' + r.i + '"] [data-qv="' + c.lo + '"]'); await sleep(120);
    expectConsistent('[' + c.key + '] back to the first star', await readState(r.i), c.lo, c.lo);
    await page.click('[data-qrate="' + r.i + '"] [data-qrate-clear]'); await sleep(120);
    expectConsistent('[' + c.key + '] after clear', await readState(r.i), null, c.lo);
  }
  await shot('01-public-stars-1440', true);
  // keyboard: arrows stay inside the configured range
  const rc = rowOf('custom');
  await page.focus('[data-qrate="' + rc.i + '"] [data-qv="2"]'); await page.keyboard.press('ArrowLeft'); await sleep(100);
  check('[custom] ArrowLeft from the first star wraps inside 2..4 (never a value outside the range)', (await readState(rc.i)).val === '4', await readState(rc.i));
  await page.keyboard.press('ArrowRight'); await sleep(100);
  check('[custom] ArrowRight wraps back to 2', (await readState(rc.i)).val === '2', await readState(rc.i));
  // pick values, let the server draft save, reload and compare
  const picks = { default: 4, custom: 3, single: 3 };
  for (const c of CASES) { const r = rowOf(c.key); await page.click('[data-qrate="' + r.i + '"] [data-qv="' + picks[c.key] + '"]'); await sleep(120); }
  await sleep(1500);
  const draft = await page.evaluate(async fid => { const r = await fetch('/api/public/forms/' + fid + '/draft'); return { status: r.status, body: await r.json() }; }, fid);
  const dAnswers = draft.body && draft.body.answers || {};
  check('server draft holds the picked stars (4 / 3 / 3)', CASES.every(c => String(dAnswers[FID[c.key]]).replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)) === String(picks[c.key])), dAnswers);
  await page.reload({ waitUntil: 'load' }); await sleep(2500);
  await page.evaluate(() => { const b = [...document.querySelectorAll('button:not([disabled]), a.btn')].find(e => e.offsetParent !== null && /شروع|ادامه/.test(e.textContent)); if (b) b.click(); }); await sleep(1200);
  for (const c of CASES) { const r = rowOf(c.key); expectConsistent('[' + c.key + '] restored from the server draft', await readState(r.i), picks[c.key], c.lo); }
  await shot('02-public-stars-restored-1440', true);
  // out-of-range restored value (e.g. a stale draft after the range changed): must not light a star it cannot represent
  const hasHook = await ev('typeof window.__NORA_PUBLIC_FORM_RESTORE==="function"');
  if (hasHook) {
    await page.evaluate(id => window.__NORA_PUBLIC_FORM_RESTORE({ answers: { [id]: '5' } }), FID.custom);
    const s = await readState(rc.i);
    check('[custom] restored value 5 (outside 2..4) is treated as empty: nothing checked, nothing lit, value empty', s.val === '' && s.checked.length === 0 && s.lit.length === 0, s);
    await page.evaluate(id => window.__NORA_PUBLIC_FORM_RESTORE({ answers: { [id]: '۳' } }), FID.custom);
    expectConsistent('[custom] restored Persian «۳»', await readState(rc.i), 3, 2);
  } else check('[custom] restore hook available (window.__NORA_PUBLIC_FORM_RESTORE)', false);
  // the API refuses an out-of-range star for the same form
  const bad = await page.evaluate(async ([fid, id]) => { const r = await fetch('/api/public/forms/' + fid + '/draft', { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ answers: { [id]: '5' } }) }); return { status: r.status, body: await r.json().catch(() => null) }; }, [fid, FID.custom]);
  check('API rejects 5 for the 2..4 star (422)', bad.status === 422, bad);
  const bad1 = await page.evaluate(async ([fid, id]) => { const r = await fetch('/api/public/forms/' + fid + '/draft', { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ answers: { [id]: '1' } }) }); return r.status; }, [fid, FID.custom]);
  check('API rejects 1 for the 2..4 star (422)', bad1 === 422, bad1);
  const bad2 = await page.evaluate(async ([fid, id]) => { const r = await fetch('/api/public/forms/' + fid + '/draft', { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ answers: { [id]: '2.5' } }) }); return r.status; }, [fid, FID.custom]);
  check('API rejects a fractional star 2.5 (422)', bad2 === 422, bad2);
  // submit and compare the stored response
  await page.evaluate(() => { const b = [...document.querySelectorAll('button:not([disabled])')].find(e => e.offsetParent !== null && /ثبت پاسخ|ثبت/.test(e.textContent)); if (b) b.click(); }); await sleep(1800);
  const done = await page.evaluate(async fid => { const r = await fetch('/api/public/forms/' + fid + '/draft'); const j = await r.json(); return { status: r.status, submitted: j && j.submitted }; }, fid);
  check('submitted', done.submitted === true, done);
  const responses = await api('/api/forms/' + fid + '/responses?limit=5');
  const items = responses.body && responses.body.items || []; const ans = items[0] && (items[0].answers || {}) || {};
  check('stored response equals the visible selection (4 / 3 / 3)', items.length === 1 && CASES.every(c => String(ans[FID[c.key]]).replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)) === String(picks[c.key])), ans);
  await shot('03-public-done-1440');
  check('no page errors', errors.length === 0, errors);
  fs.writeFileSync(path.join(out, 'log.txt'), lines.join('\n'));
  L('e2e-rating: ' + pass + ' قبول، ' + fail + ' خطا'); fs.appendFileSync(path.join(out, 'log.txt'), '\ne2e-rating: ' + pass + ' قبول، ' + fail + ' خطا\n');
  await b.close(); process.exit(fail ? 1 : 0);
})().catch(e => { console.error('FATAL', e); process.exit(2); });
