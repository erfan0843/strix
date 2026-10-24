// Browser flow for H1 (server people editor on GET/PATCH /api/owner/site-content), test DB only.
// Run: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<dir-with-node_modules> node h1-people-editor-check.cjs
const fs = require('fs'); const path = require('path');
const uiRoot = path.resolve(__dirname, '../../../website/nora-ui');
const { launchBrowser } = require(path.join(uiRoot, 'tools/browser-launch.cjs'));
const BASE = 'http://127.0.0.1:8000'; const EV = 'ev-42421ba4f7'; const NAME = 'مدرس آزمایشی H1';
const creds = (() => { const t = fs.readFileSync(path.join(uiRoot, 'PREVIEW-LOGIN.local.md'), 'utf8');
  const o = t.match(/مالک:\s*`([^`]+)`\s*\/\s*`([^`]+)`/); const m = t.match(/مدیر:\s*`([^`]+)`\s*\/\s*`([^`]+)`/);
  return { owner: { user: o[1], pass: o[2] }, manager: { user: m[1], pass: m[2] } }; })();
const out = { steps: [] }; const note = (s) => { out.steps.push(s); console.log(s); };
const shot = (page, name, full) => page.screenshot({ path: path.join(__dirname, name), fullPage: !!full });
const api = (page, fn, arg) => page.evaluate(fn, arg);
const csrfHeaders = () => { const csrf = (document.cookie.match(/nora_csrf=([^;]+)/) || [])[1] || ''; return { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }; };
(async () => {
  const browser = await launchBrowser(); const page = await browser.newPage(); await page.setViewportSize({ width: 1280, height: 800 });
  page.on('pageerror', (e) => note('PAGEERROR ' + e.message));
  const dialogs = []; page.on('dialog', async (d) => { dialogs.push(d.message()); await d.accept(); });
  const login = async (c) => {
    await page.goto(`${BASE}/login.html?mode=staff&next=admin.html`, { waitUntil: 'domcontentloaded' });
    await page.fill('#lgStaffUsername', c.user); await page.fill('#lgStaffPassword', c.pass); await page.click('#lgStaffSubmit');
    await page.waitForTimeout(2000); const go = page.getByText('رفتن به پنل مدیریت').first(); if (await go.count()) await go.click();
    await page.waitForURL(/admin\.html/, { timeout: 15000 }); await page.waitForTimeout(1200);
  };
  const openPeople = async () => {
    await page.evaluate(() => { const s = JSON.parse(localStorage.getItem('nora-admin') || '{}'); s.sec = 'settings'; s.setG = 'people'; s.ppEd = ''; s.ppD = null; localStorage.setItem('nora-admin', JSON.stringify(s)); });
    await page.goto(`${BASE}/admin.html?_=${Date.now()}`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#peList', { timeout: 15000 }); await page.waitForTimeout(1500);
  };
  const state = () => page.$eval('#peSrvState', (el) => el.textContent);
  // Clean leftovers of previous runs (test DB only): unlink event + drop the test person via the real API.
  await login(creds.owner);
  const cleaned = await api(page, async ({ ev, name }) => {
    const h = (() => { const csrf = (document.cookie.match(/nora_csrf=([^;]+)/) || [])[1] || ''; return { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }; })();
    const cur = await fetch('/api/owner/site-content', { credentials: 'include' }).then(r => r.json());
    const stale = (cur.content.people || []).filter(p => p.n === name).map(p => p.id);
    if (!stale.length) return { stale: 0 };
    const e = await fetch(`/api/admin/content/events/${ev}`, { credentials: 'include' }).then(r => r.json());
    if (stale.includes(e.record.tchr)) await fetch(`/api/admin/content/events/${ev}`, { method: 'PUT', credentials: 'include', headers: h, body: JSON.stringify({ record: { tchr: '' }, expected_version: e.version }) });
    const cur2 = await fetch('/api/owner/site-content', { credentials: 'include' }).then(r => r.json());
    const r = await fetch('/api/owner/site-content', { method: 'PATCH', credentials: 'include', headers: h, body: JSON.stringify({ content: { people: cur2.content.people.filter(p => p.n !== name) }, expected_version: cur2.version }) });
    return { stale: stale.length, status: r.status };
  }, { ev: EV, name: NAME });
  note('cleanup: ' + JSON.stringify(cleaned));

  // 1) list from server
  await openPeople();
  const rows0 = await page.$$eval('[data-pe-row]', (els) => els.length);
  note('1 list: rows=' + rows0 + ' state=' + (await state()));
  await shot(page, 'h1-01-list-d.png', true);

  // 2) create a test teacher with explicit confirm
  await page.click('[data-pe-new]'); await page.waitForSelector('[data-pe-editor="new"]');
  await page.fill('[data-ppf="n"]', NAME); await page.fill('[data-ppf="r"]', 'مدرس نجوم (آزمایشی)'); await page.fill('[data-ppf="exp"]', 'نجوم، رصد');
  await page.fill('[data-ppf="bio"]', 'پروفایل آزمایشی برای بررسی ویرایشگر افراد؛ پس از آزمون حذف می‌شود.');
  await page.waitForTimeout(400);
  const prevText = await page.$eval('#ppPrev', (el) => el.textContent.replace(/\s+/g, ' ').slice(0, 200));
  note('2 live preview: ' + prevText);
  await page.$eval('[data-pe-editor]', (el) => el.scrollIntoView()); await shot(page, 'h1-02-new-editor-d.png', true);
  dialogs.length = 0; await page.click('[data-pe-save]');
  await page.waitForFunction(() => /ذخیره شد|نشد|خطا/.test(document.querySelector('#peSrvState')?.textContent || ''), null, { timeout: 15000 });
  note('2 confirm dialog: ' + JSON.stringify(dialogs)); note('2 after save: ' + (await state()));
  const pub = await api(page, async ({ name }) => { const r = await fetch('/api/public/site-content').then(r => r.json()); const p = (r.content ? r.content.people : r.people || []).find(x => x.n === name); return p ? { id: p.id, r: p.r, exp: p.exp, kind: p.kind } : null; }, { name: NAME });
  note('2 public site-content has person: ' + JSON.stringify(pub));
  if (!pub) throw new Error('person not published');
  const PID = pub.id;
  await shot(page, 'h1-03-created-list-d.png', true);

  // 3) public profile page
  await page.goto(`${BASE}/person.html?id=${encodeURIComponent(PID)}`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2500);
  const personTxt = await page.evaluate(() => document.body.innerText.replace(/\s+/g, ' '));
  note('3 person.html shows name=' + personTxt.includes(NAME) + ' role=' + personTxt.includes('مدرس نجوم (آزمایشی)'));
  await shot(page, 'h1-04-person-public-d.png', false);

  // 4) edit + persist after reload
  await openPeople(); await page.click(`[data-pe-edit="${PID}"]`); await page.waitForSelector(`[data-pe-editor="${PID}"]`);
  await page.fill('[data-ppf="r"]', 'مدرس ارشد نجوم (آزمایشی)'); await page.waitForTimeout(300);
  await page.click('[data-pe-save]');
  await page.waitForFunction(() => /ذخیره شد|نشد/.test(document.querySelector('#peSrvState')?.textContent || ''), null, { timeout: 15000 });
  note('4 edit: ' + (await state()));
  await openPeople();
  const rowTxt = await page.$eval(`[data-pe-row="${PID}"]`, (el) => el.textContent.replace(/\s+/g, ' '));
  note('4 after reload row: ' + rowTxt.slice(0, 160));

  // 5) 409 conflict: another writer changes the same person while the editor is open
  await page.click(`[data-pe-edit="${PID}"]`); await page.waitForSelector(`[data-pe-editor="${PID}"]`);
  await page.fill('[data-ppf="quote"]', 'جملهٔ من در ویرایشگر'); await page.waitForTimeout(300);
  const other = await api(page, async ({ id }) => {
    const h = (() => { const csrf = (document.cookie.match(/nora_csrf=([^;]+)/) || [])[1] || ''; return { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }; })();
    const cur = await fetch('/api/owner/site-content', { credentials: 'include' }).then(r => r.json());
    const people = cur.content.people.map(p => p.id === id ? Object.assign({}, p, { where: 'رصدخانهٔ آزمایشی' }) : p);
    const r = await fetch('/api/owner/site-content', { method: 'PATCH', credentials: 'include', headers: h, body: JSON.stringify({ content: { people }, expected_version: cur.version }) });
    return { status: r.status, version: (await r.json()).version };
  }, { id: PID });
  note('5 concurrent writer: ' + JSON.stringify(other));
  await page.click('[data-pe-save]');
  await page.waitForSelector('[data-pe-conflict]', { timeout: 15000 }); await page.waitForTimeout(500);
  const quoteKept = await page.$eval('[data-ppf="quote"]', (el) => el.value);
  const diffs = await page.$$eval('[data-pe-diff]', (els) => els.map(e => e.getAttribute('data-pe-diff')));
  note('5 conflict panel: quoteKept=' + JSON.stringify(quoteKept) + ' diffs=' + JSON.stringify(diffs) + ' state=' + (await state()));
  await page.$eval('[data-pe-conflict]', (el) => el.scrollIntoView()); await shot(page, 'h1-05-conflict-d.png', false);
  await page.click('[data-pe-take="where"]'); await page.waitForTimeout(300);
  await page.click('[data-pe-conflict] [data-pe-save]');
  await page.waitForFunction(() => /ذخیره شد/.test(document.querySelector('#peSrvState')?.textContent || ''), null, { timeout: 15000 });
  const merged = await api(page, async ({ id }) => { const r = await fetch('/api/owner/site-content', { credentials: 'include' }).then(r => r.json()); const p = r.content.people.find(x => x.id === id); return { where: p.where, quote: p.quote, version: r.version }; }, { id: PID });
  note('5 after re-save: ' + JSON.stringify(merged));

  // 6) delete guard: link the test event to this person, then try to delete from UI
  const linked = await api(page, async ({ ev, id }) => {
    const h = (() => { const csrf = (document.cookie.match(/nora_csrf=([^;]+)/) || [])[1] || ''; return { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }; })();
    const e = await fetch(`/api/admin/content/events/${ev}`, { credentials: 'include' }).then(r => r.json());
    const r = await fetch(`/api/admin/content/events/${ev}`, { method: 'PUT', credentials: 'include', headers: h, body: JSON.stringify({ record: { tchr: id }, expected_version: e.version }) });
    return r.status;
  }, { ev: EV, id: PID });
  note('6 link event tchr → ' + linked);
  await openPeople(); await page.click(`[data-pe-del="${PID}"]`);
  await page.waitForFunction(() => /حذف انجام نشد|حذف پروفایل/.test(document.querySelector('#peSrvState')?.textContent || ''), null, { timeout: 15000 }); await page.waitForTimeout(400);
  const stillThere = await page.$(`[data-pe-row="${PID}"]`);
  note('6 delete while linked: state=' + (await state()) + ' rowStill=' + !!stillThere);
  await shot(page, 'h1-06-delete-guard-d.png', false);

  // 7) unauthorized: manager session cannot read/write owner site-content; people tab shows no editor
  await page.context().clearCookies(); await login(creds.manager);
  const mgr = await api(page, async () => {
    const h = (() => { const csrf = (document.cookie.match(/nora_account_csrf=([^;]+)/) || [])[1] || ''; return { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }; })();
    const g = await fetch('/api/owner/site-content', { credentials: 'include' });
    const p = await fetch('/api/owner/site-content', { method: 'PATCH', credentials: 'include', headers: h, body: JSON.stringify({ content: { people: [] }, expected_version: 0 }) });
    return { get: g.status, patch: p.status };
  });
  await page.evaluate(() => { const s = JSON.parse(localStorage.getItem('nora-admin') || '{}'); s.sec = 'settings'; s.setG = 'people'; localStorage.setItem('nora-admin', JSON.stringify(s)); });
  await page.goto(`${BASE}/admin.html?_=${Date.now()}`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2000);
  const mgrUi = await page.evaluate(() => ({ peList: !!document.querySelector('#peList'), peNew: !!document.querySelector('[data-pe-new]'), sec: (JSON.parse(localStorage.getItem('nora-admin') || '{}')).sec }));
  note('7 manager: http=' + JSON.stringify(mgr) + ' ui=' + JSON.stringify(mgrUi));
  await shot(page, 'h1-07-manager-no-editor-d.png', false);

  // 8) mobile editor shot + cleanup (unlink, delete test person)
  await page.context().clearCookies(); await login(creds.owner);
  await page.setViewportSize({ width: 390, height: 844 }); await openPeople();
  await page.click(`[data-pe-edit="${PID}"]`); await page.waitForSelector(`[data-pe-editor="${PID}"]`); await page.waitForTimeout(500);
  const ov = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1); note('8 mobile overflowX=' + ov);
  await page.$eval('[data-pe-editor]', (el) => el.scrollIntoView()); await shot(page, 'h1-08-editor-m.png', false);
  const unlinked = await api(page, async ({ ev }) => {
    const h = (() => { const csrf = (document.cookie.match(/nora_csrf=([^;]+)/) || [])[1] || ''; return { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }; })();
    const e = await fetch(`/api/admin/content/events/${ev}`, { credentials: 'include' }).then(r => r.json());
    return (await fetch(`/api/admin/content/events/${ev}`, { method: 'PUT', credentials: 'include', headers: h, body: JSON.stringify({ record: { tchr: '' }, expected_version: e.version }) })).status;
  }, { ev: EV });
  note('8 unlink event → ' + unlinked);
  await page.setViewportSize({ width: 1280, height: 800 }); await openPeople(); await page.click(`[data-pe-del="${PID}"]`);
  await page.waitForFunction((id) => !document.querySelector(`[data-pe-row="${id}"]`) && /ذخیره شد/.test(document.querySelector('#peSrvState')?.textContent || ''), PID, { timeout: 15000 });
  const gone = await api(page, async ({ id }) => { const r = await fetch('/api/public/site-content').then(r => r.json()); return !(r.content ? r.content.people : r.people || []).some(x => x.id === id); }, { id: PID });
  note('8 deleted from server (public no longer lists it): ' + gone + ' state=' + (await state()));
  fs.writeFileSync(path.join(__dirname, 'h1-people-editor-check.json'), JSON.stringify(out, null, 2));
  await browser.close();
})().catch((e) => { note('FATAL ' + e.message); fs.writeFileSync(path.join(__dirname, 'h1-people-editor-check.json'), JSON.stringify(out, null, 2)); process.exit(1); });
