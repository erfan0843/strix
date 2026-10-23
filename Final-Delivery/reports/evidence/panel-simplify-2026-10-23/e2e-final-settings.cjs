// Real-browser E2E for the compact event editor, calendar/time typing, past events, files, settings (dev-only; test DB).
// Usage: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<node-deps> node e2e-final.cjs <outdir>
const { launchBrowser } = require('../../../website/nora-ui/tools/browser-launch.cjs');
const O = 'http://127.0.0.1:8000', OM = process.env.MANAGER_ORIGIN || 'http://127.0.0.1:8080';
const out = process.argv[2] || 'shots/final-settings';
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
  // ── F) settings: owner save + reload ──
  await gotoHash('#settings'); await click('[data-setg="texts"]'); await sleep(2000);
  const before = await val('[data-sys-text="texts.reminder_head"]');
  const newText = 'یادآوری آزمون ' + stamp + ': «{رویداد}» {زمان}';
  await setVal('[data-sys-text="texts.reminder_head"]', newText); await sleep(300);
  check('dirty state enables save', !(await has('[data-sys-save][disabled]')));
  await click('[data-sys-save]'); await sleep(2500);
  check('save success message', await has('[data-sys-msg="ok"]'));
  await shot('after-settings-texts-saved', true);
  await gotoHash('#settings'); await click('[data-setg="texts"]'); await sleep(2000);
  check('settings persist after reload', (await val('[data-sys-text="texts.reminder_head"]')) === newText);
  const srvSet = await api('/api/owner/settings');
  check('server returns saved value', srvSet.status === 200 && (srvSet.body.items || []).some(i => i.key === 'texts.reminder_head' && i.value === newText));
  // restore
  await setVal('[data-sys-text="texts.reminder_head"]', before || ''); await click('[data-sys-save]'); await sleep(2000);
  for (const g of ['money', 'cert', 'ticket', 'notify', 'data']) { await gotoHash('#settings'); await click('[data-setg="' + g + '"]'); await sleep(1500); await shot('after-settings-' + g, true); }
  // notify group: reminders default switch round-trip
  await gotoHash('#settings'); await click('[data-setg="notify"]'); await sleep(1500);
  const sw = await page.evaluate(() => { const s = document.querySelector('[data-sys-switch="events.reminders_default"]'); return s ? { exists: true, checked: s.checked } : { exists: false }; });
  L('reminders default switch', sw);

  // ── G) manager: UI lock + API denial ──
  let managerOk = false;
  try {
    await page.goto('about:blank'); await page.goto(OM + '/admin.html#settings', { waitUntil: 'load' }); await sleep(2500);
    const m = await page.evaluate(async () => { const nav = document.querySelector('[data-sec="settings"]'); const locked = nav ? nav.hasAttribute('data-locked') : null; const csrf = (document.cookie.match(/nora_account_csrf=([^;]+)/) || [])[1] || ''; const r = await fetch('/api/owner/settings', { method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ changes: { 'texts.reminder_head': 'x' } }) }); const g = await fetch('/api/owner/settings', { credentials: 'same-origin' }); return { locked, put: r.status, get: g.status, sysInputs: document.querySelectorAll('[data-sys-text],[data-sys-switch]').length, body: document.body.textContent.replace(/\s+/g, ' ').slice(0, 200) }; });
    L('manager', m);
    managerOk = (m.put === 403 || m.put === 401) && (m.get === 403 || m.get === 401) && m.sysInputs === 0;
    await shot('after-manager-settings-denied', true);
    await page.goto('about:blank'); await page.goto(OM + '/admin.html#newev', { waitUntil: 'load' }); await sleep(2500);
    L('manager newev', await page.evaluate(() => ({ editor: !!document.querySelector('[data-ct-editor]'), publish: !!document.querySelector('[data-ct-save-publish]'), body: document.body.textContent.replace(/\s+/g, ' ').slice(0, 160) })));
  } catch (e) { L('manager error', e.message); }
  check('manager: settings denied in UI and API', managerOk);

  fs.writeFileSync(path.join(out, 'log.txt'), log.join('\n') + '\n');
  L('SUMMARY', { pass: log.filter(l => l.startsWith('PASS')).length, fail: log.filter(l => l.startsWith('FAIL')).length });
  await browser.close();
})().catch(e => { console.error(e); fs.writeFileSync(path.join(out, 'log.txt'), log.join('\n') + '\nCRASH ' + e.stack + '\n'); process.exit(1); });
