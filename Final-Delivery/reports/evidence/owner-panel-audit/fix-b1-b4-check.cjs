// Browser check for fixes B1 (unknown_reference) + B4 (event ↔ registration-form link from the editor).
// Run: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<dir-with-node_modules> node fix-b1-b4-check.cjs
const fs = require('fs'); const path = require('path');
const uiRoot = path.resolve(__dirname, '../../../website/nora-ui');
const { launchBrowser } = require(path.join(uiRoot, 'tools/browser-launch.cjs'));
const BASE = 'http://127.0.0.1:8000'; const EV = 'ev-42421ba4f7';
const creds = (() => { const t = fs.readFileSync(path.join(uiRoot, 'PREVIEW-LOGIN.local.md'), 'utf8'); const m = t.match(/مالک:\s*`([^`]+)`\s*\/\s*`([^`]+)`/); return { user: m[1], pass: m[2] }; })();
const out = { steps: [] }; const note = (s) => { out.steps.push(s); console.log(s); };
(async () => {
  const browser = await launchBrowser(); const page = await browser.newPage(); await page.setViewportSize({ width: 1280, height: 800 });
  page.on('pageerror', (e) => note('PAGEERROR ' + e.message));
  await page.goto(`${BASE}/login.html?mode=staff&next=admin.html`, { waitUntil: 'domcontentloaded' });
  await page.fill('#lgStaffUsername', creds.user); await page.fill('#lgStaffPassword', creds.pass); await page.click('#lgStaffSubmit');
  await page.waitForTimeout(2000); const go = page.getByText('رفتن به پنل مدیریت').first(); if (await go.count()) await go.click();
  await page.waitForURL(/admin\.html/, { timeout: 15000 }); await page.waitForTimeout(1500);
  // B1 via the real API from the owner session
  const b1 = await page.evaluate(async ({ ev }) => {
    const csrf = (document.cookie.match(/nora_csrf=([^;]+)/) || [])[1] || '';
    const h = { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf };
    const cur = await fetch(`/api/admin/content/events/${ev}`, { credentials: 'include' }).then(r => r.json());
    const bad = await fetch(`/api/admin/content/events/${ev}`, { method: 'PUT', credentials: 'include', headers: h, body: JSON.stringify({ record: { tchr: 'pp-ghost' }, expected_version: cur.version }) });
    const badBody = await bad.json();
    const after = await fetch(`/api/admin/content/events/${ev}`, { credentials: 'include' }).then(r => r.json());
    const clear = await fetch(`/api/admin/content/events/${ev}`, { method: 'PUT', credentials: 'include', headers: h, body: JSON.stringify({ record: { tchr: '' }, expected_version: after.version }) });
    const cleared = await fetch(`/api/admin/content/events/${ev}`, { credentials: 'include' }).then(r => r.json());
    return { status: bad.status, detail: badBody.detail, versionBefore: cur.version, versionAfter: after.version, tchrAfter: after.record.tchr || '', clearStatus: clear.status, tchrCleared: cleared.record.tchr || '' };
  }, { ev: EV });
  note('B1 PUT tchr=pp-ghost → ' + JSON.stringify(b1));
  // B4: open editor
  await page.evaluate(() => { const s = JSON.parse(localStorage.getItem('nora-admin') || '{}'); s.sec = 'events'; localStorage.setItem('nora-admin', JSON.stringify(s)); });
  await page.goto(`${BASE}/admin.html?_=${Date.now()}`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(1500);
  await page.fill('[data-ct-q]', EV).catch(() => {}); await page.click('[data-ct-search]').catch(() => {}); await page.waitForTimeout(800);
  await page.click(`[data-ct-edit="${EV}"]`); await page.waitForSelector(`[data-ct-forms="${EV}"]`, { timeout: 10000 }); await page.waitForTimeout(1200);
  const block = await page.$(`[data-ct-forms="${EV}"]`); await block.scrollIntoViewIfNeeded(); await page.waitForTimeout(300);
  note('B4 editor block: ' + (await block.innerText()).replace(/\n/g, ' / ').slice(0, 300));
  await block.screenshot({ path: path.join(__dirname, 'fix-b4-editor-forms-block.png') });
  await page.screenshot({ path: path.join(__dirname, 'fix-b4-editor-d.png'), fullPage: true });
  const href = await page.getAttribute(`[data-ct-form-create="${EV}"]`, 'href'); note('B4 create href: ' + href);
  await page.click(`[data-ct-form-create="${EV}"]`); await page.waitForURL(/create\.html/, { timeout: 10000 }); await page.waitForTimeout(2000);
  const st = await page.evaluate(() => ({ url: location.href, evId: (typeof S !== 'undefined' && S.evId) || '', title: (typeof S !== 'undefined' && S.title) || '', chip: (document.getElementById('evChip') || {}).textContent || '', chipHidden: (document.getElementById('evChip') || {}).hidden, meta: (document.getElementById('evMeta') || document.querySelector('[data-ev-meta]') || {}).textContent || '' }));
  note('B4 create.html state: ' + JSON.stringify(st));
  await page.screenshot({ path: path.join(__dirname, 'fix-b4-create-prefilled-d.png'), fullPage: false });
  // manager without fm_create? (skip: single owner session) — mobile shot of editor block
  await page.setViewportSize({ width: 390, height: 844 }); await page.goto(`${BASE}/admin.html?_=${Date.now()}`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(1500);
  await page.fill('[data-ct-q]', EV).catch(() => {}); await page.click('[data-ct-search]').catch(() => {}); await page.waitForTimeout(800);
  await page.click(`[data-ct-edit="${EV}"]`); await page.waitForSelector(`[data-ct-forms="${EV}"]`, { timeout: 10000 }); await page.waitForTimeout(1000);
  const ov = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1); note('mobile overflowX=' + ov);
  const blockM = await page.$(`[data-ct-forms="${EV}"]`); await blockM.scrollIntoViewIfNeeded(); await page.screenshot({ path: path.join(__dirname, 'fix-b4-editor-m.png') });
  fs.writeFileSync(path.join(__dirname, 'fix-b1-b4-check.json'), JSON.stringify(out, null, 2));
  await browser.close();
})().catch((e) => { note('FATAL ' + e.message); fs.writeFileSync(path.join(__dirname, 'fix-b1-b4-check.json'), JSON.stringify(out, null, 2)); process.exit(1); });
