// Browser flow for stage 2 (id-based teacher/partner picker in the event editor, profile author in the article editor), test DB only.
// Run: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<dir-with-node_modules> NORA_QA_PYTHON=<venv python> NORA_QA_DB=<test sqlite db> node stage2-pickers-check.cjs
// Step 3 writes a stale id straight into the TEST database (the API refuses it) to reproduce legacy data; never point NORA_QA_DB at real data.
const fs = require('fs'); const path = require('path');
const uiRoot = path.resolve(__dirname, '../../../website/nora-ui');
const { launchBrowser } = require(path.join(uiRoot, 'tools/browser-launch.cjs'));
const BASE = 'http://127.0.0.1:8000'; const EV = 'ev-42421ba4f7'; const NAME = 'مدرس آزمایشی مرحله ۲';
const creds = (() => { const t = fs.readFileSync(path.join(uiRoot, 'PREVIEW-LOGIN.local.md'), 'utf8');
  const o = t.match(/مالک:\s*`([^`]+)`\s*\/\s*`([^`]+)`/); const m = t.match(/مدیر:\s*`([^`]+)`\s*\/\s*`([^`]+)`/);
  return { owner: { user: o[1], pass: o[2] }, manager: { user: m[1], pass: m[2] } }; })();
const out = { steps: [] }; const note = (s) => { out.steps.push(s); console.log(s); };
const shot = (page, name, full) => page.screenshot({ path: path.join(__dirname, name), fullPage: !!full });
const H = () => { const csrf = (document.cookie.match(/nora_csrf=([^;]+)/) || [])[1] || ''; return { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }; };
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
  const openSec = async (sec, extra) => {
    await page.evaluate(({ sec, extra }) => { const s = JSON.parse(localStorage.getItem('nora-admin') || '{}'); s.sec = sec; Object.assign(s, extra || {}); localStorage.setItem('nora-admin', JSON.stringify(s)); }, { sec, extra });
    await page.goto(`${BASE}/admin.html?_=${Date.now()}`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(1500);
  };
  const openEvent = async (id) => {
    await openSec('events'); await page.fill('#ctQuery', id).catch(() => {}); await page.click('[data-ct-search]').catch(() => {}); await page.waitForTimeout(800);
    await page.click(`[data-ct-edit="${id}"]`); await page.waitForSelector('[data-ct-pick="tchr"]', { timeout: 10000 }); await page.waitForTimeout(800);
  };
  await login(creds.owner);
  // cleanup from earlier runs + create the test teacher through the H1 editor (explicit confirm)
  await page.evaluate(async ({ ev, name }) => {
    const h = (() => { const csrf = (document.cookie.match(/nora_csrf=([^;]+)/) || [])[1] || ''; return { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }; })();
    const e = await fetch(`/api/admin/content/events/${ev}`, { credentials: 'include' }).then(r => r.json());
    if (e.record.tchr) await fetch(`/api/admin/content/events/${ev}`, { method: 'PUT', credentials: 'include', headers: h, body: JSON.stringify({ record: { tchr: '' }, expected_version: e.version }) });
    const cur = await fetch('/api/owner/site-content', { credentials: 'include' }).then(r => r.json());
    if ((cur.content.people || []).some(p => p.n === name)) await fetch('/api/owner/site-content', { method: 'PATCH', credentials: 'include', headers: h, body: JSON.stringify({ content: { people: cur.content.people.filter(p => p.n !== name) }, expected_version: cur.version }) });
  }, { ev: EV, name: NAME });
  await openSec('settings', { setG: 'people', ppEd: '', ppD: null }); await page.waitForSelector('#peList', { timeout: 15000 }); await page.waitForTimeout(800);
  await page.click('[data-pe-new]'); await page.waitForSelector('[data-pe-editor="new"]');
  await page.fill('[data-ppf="n"]', NAME); await page.fill('[data-ppf="r"]', 'مدرس رصد (آزمایشی)'); await page.fill('[data-ppf="exp"]', 'رصد، نجوم');
  dialogs.length = 0; await page.click('[data-pe-save]');
  await page.waitForFunction(() => /ذخیره شد|نشد/.test(document.querySelector('#peSrvState')?.textContent || ''), null, { timeout: 15000 });
  note('0 teacher created via H1: confirm=' + (dialogs.length === 1) + ' state=' + (await page.$eval('#peSrvState', el => el.textContent)));
  const PID = await page.evaluate(async ({ name }) => { const r = await fetch('/api/public/site-content').then(r => r.json()); return ((r.content || r).people || []).find(p => p.n === name)?.id || ''; }, { name: NAME });
  if (!PID) throw new Error('teacher missing in public content'); note('0 person id: ' + PID);

  // 1) event editor: picker search → select → save
  await openEvent(EV);
  const before = await page.evaluate(() => ({ empty: !!document.querySelector('[data-ct-pick-empty="tchr"]'), partner: !!document.querySelector('[data-ct-pick="partnerId"]') }));
  note('1 editor pickers: ' + JSON.stringify(before));
  await page.fill('[data-ct-pick-q="tchr"]', 'رصد'); await page.waitForTimeout(300);
  const hits = await page.$$eval('[data-ct-pick-set="tchr"]', els => els.map(e => e.getAttribute('data-ct-pick-id')));
  note('1 search "رصد" hits: ' + JSON.stringify(hits));
  await page.$eval('[data-ct-people]', el => el.scrollIntoView()); await shot(page, 'stage2-01-picker-search-d.png', false);
  await page.keyboard.press('Enter'); await page.waitForTimeout(400);
  const picked = await page.$eval('[data-ct-pick="tchr"]', el => (el.querySelector('[data-ct-pick-current]') || {}).getAttribute?.('data-ct-pick-current') || '');
  note('1 Enter picked: ' + picked + ' preview=' + (await page.$eval('#ctPreview', el => el.textContent.replace(/\s+/g, ' ').slice(0, 160))));
  await shot(page, 'stage2-02-picker-selected-d.png', false);
  await page.click('[data-ct-save]');
  await page.waitForFunction(() => !document.querySelector('[data-ct-editor]'), null, { timeout: 15000 }); await page.waitForTimeout(800);
  const row = await page.$eval(`[data-ct-row="${EV}"]`, el => el.textContent.replace(/\s+/g, ' '));
  note('1 list row after save: ' + row.slice(0, 220));
  // 2) reload → still linked; public event page shows the instructor
  await openEvent(EV);
  const persisted = await page.evaluate(() => (document.querySelector('[data-ct-pick="tchr"] [data-ct-pick-current]') || {}).getAttribute?.('data-ct-pick-current') || '');
  note('2 after reload linked id: ' + persisted + ' (expected ' + PID + ')');
  const srv = await page.evaluate(async ({ ev }) => (await fetch(`/api/admin/content/events/${ev}`, { credentials: 'include' }).then(r => r.json())).record.tchr, { ev: EV });
  note('2 server record tchr: ' + srv);
  // the audit event is a draft (never public); link the same person to the seeded PUBLISHED plain event for the public-page check, then unlink
  const PUB = 'ev-a565e1b030';
  const linkPub = async (val) => page.evaluate(async ({ ev, val }) => { const h = (() => { const csrf = (document.cookie.match(/nora_csrf=([^;]+)/) || [])[1] || ''; return { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }; })();
    const e = await fetch(`/api/admin/content/events/${ev}`, { credentials: 'include' }).then(r => r.json());
    return (await fetch(`/api/admin/content/events/${ev}`, { method: 'PUT', credentials: 'include', headers: h, body: JSON.stringify({ record: { tchr: val }, expected_version: e.version }) })).status; }, { ev: PUB, val });
  note('2 link published event ' + PUB + ' → PUT ' + (await linkPub(PID)));
  await page.goto(`${BASE}/event.html?id=${PUB}`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2500);
  const evTxt = await page.evaluate(() => document.body.innerText.replace(/\s+/g, ' '));
  note('2 public event page shows teacher name: ' + evTxt.includes(NAME) + ' role: ' + evTxt.includes('مدرس رصد (آزمایشی)'));
  await shot(page, 'stage2-03-event-public-d.png', false);
  await page.goto(`${BASE}/events.html`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2500);
  const cardHas = await page.evaluate(({ id, n }) => { const el = document.querySelector('[data-event-id="' + id + '"]'); return { card: !!el, teacherOnCard: !!el && el.textContent.includes(n) }; }, { id: PUB, n: NAME });
  note('2 events.html list card (events-page.js resolves tchr by id): ' + JSON.stringify(cardHas));
  if (cardHas.card) { await page.$eval('[data-event-id="' + PUB + '"]', el => el.scrollIntoView()); await shot(page, 'stage2-03b-event-card-d.png', false); }
  await page.goto(`${BASE}/home.html`, { waitUntil: 'domcontentloaded' }).catch(() => {}); await page.waitForTimeout(2500);
  const homeHas = await page.evaluate((n) => document.body.innerText.includes(n), NAME);
  note('2 home.html mentions the teacher (teacher rail): ' + homeHas);
  note('2 unlink published event → PUT ' + (await linkPub('')));
  // 3) nonexistent id: legacy/stale value written straight into the test DB (API refuses it) → warning, save blocked with no request; clear + pick again saves
  const { execSync } = require('child_process');
  execSync(`${process.env.NORA_QA_PYTHON || 'python3'} - <<'PY'
import sqlite3, json
c = sqlite3.connect('${process.env.NORA_QA_DB}')
row = c.execute("select content from site_content where id='public'").fetchone()
d = json.loads(row[0])
for e in d['events']:
    if e['id'] == '${EV}': e['tchr'] = 'pp-ghost'
c.execute("update site_content set content=? where id='public'", (json.dumps(d, ensure_ascii=False),)); c.commit()
PY`);
  await page.goto(`${BASE}/admin.html?_=${Date.now()}`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(1200);
  await openEvent(EV);
  await page.waitForSelector('[data-ct-pick-invalid]', { timeout: 5000 });
  const invalidTxt = await page.$eval('[data-ct-pick-invalid]', el => el.textContent.replace(/\s+/g, ' '));
  const putsBefore = await page.evaluate(() => performance.getEntriesByType('resource').filter(r => /\/api\/admin\/content\/events\//.test(r.name)).length);
  await page.click('[data-ct-save]'); await page.waitForTimeout(800);
  const putsAfter = await page.evaluate(() => performance.getEntriesByType('resource').filter(r => /\/api\/admin\/content\/events\//.test(r.name)).length);
  const errTxt = await page.$eval('[data-ct-err="tchr"]', el => el.textContent);
  note('3 ghost id: warning="' + invalidTxt + '" blocked client-side (requests unchanged=' + (putsBefore === putsAfter) + ') editorOpen=' + !!(await page.$('[data-ct-editor]')) + ' err="' + errTxt + '"');
  await page.$eval('[data-ct-people]', el => el.scrollIntoView()); await shot(page, 'stage2-04-ghost-id-d.png', false);
  const ghost = await page.evaluate(async ({ ev }) => { const h = (() => { const csrf = (document.cookie.match(/nora_csrf=([^;]+)/) || [])[1] || ''; return { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }; })();
    const e = await fetch(`/api/admin/content/events/${ev}`, { credentials: 'include' }).then(r => r.json());
    const r = await fetch(`/api/admin/content/events/${ev}`, { method: 'PUT', credentials: 'include', headers: h, body: JSON.stringify({ record: { tchr: 'pp-ghost' }, expected_version: e.version }) });
    return { status: r.status, detail: (await r.json()).detail }; }, { ev: EV });
  note('3 server PUT tchr=pp-ghost → ' + JSON.stringify(ghost));
  await page.click('[data-ct-pick-clear="tchr"]'); await page.waitForTimeout(300);
  await page.fill('[data-ct-pick-q="tchr"]', 'آزمایشی'); await page.waitForTimeout(300); await page.keyboard.press('Enter'); await page.waitForTimeout(300);
  await page.click('[data-ct-save]'); await page.waitForFunction(() => !document.querySelector('[data-ct-editor]'), null, { timeout: 15000 });
  note('3 after clear + pick again saved; server tchr=' + (await page.evaluate(async ({ ev }) => (await fetch(`/api/admin/content/events/${ev}`, { credentials: 'include' }).then(r => r.json())).record.tchr, { ev: EV })));
  // 4) 409 in the content editor: concurrent writer bumps the version
  await openEvent(EV);
  await page.evaluate(async ({ ev }) => { const h = (() => { const csrf = (document.cookie.match(/nora_csrf=([^;]+)/) || [])[1] || ''; return { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }; })();
    const e = await fetch(`/api/admin/content/events/${ev}`, { credentials: 'include' }).then(r => r.json());
    await fetch(`/api/admin/content/events/${ev}`, { method: 'PUT', credentials: 'include', headers: h, body: JSON.stringify({ record: { place: 'سالن آزمایشی ' + Date.now() }, expected_version: e.version }) }); }, { ev: EV });
  await page.click('[data-ct-save]'); await page.waitForTimeout(1500);
  const conflict = await page.evaluate(() => ({ editorOpen: !!document.querySelector('[data-ct-editor]'), msg: (document.querySelector('[data-ct-editor] .cap[style*="stop"]') || {}).textContent || '', tchr: (document.querySelector('[data-ct-pick="tchr"] [data-ct-pick-current]') || {}).getAttribute?.('data-ct-pick-current') || '' }));
  note('4 409 in editor: ' + JSON.stringify(conflict));
  await shot(page, 'stage2-05-editor-409-d.png', false);
  await page.click('[data-ct-save]'); await page.waitForFunction(() => !document.querySelector('[data-ct-editor]'), null, { timeout: 15000 });
  note('4 retry on fresh version saved; tchr still=' + (await page.evaluate(async ({ ev }) => (await fetch(`/api/admin/content/events/${ev}`, { credentials: 'include' }).then(r => r.json())).record.tchr, { ev: EV })));
  // 5) article: profile author via picker, free guest name kept as separate field
  await openSec('events'); await page.click('[data-ct-kind="articles"]'); await page.waitForTimeout(800);
  await page.click('[data-ct-new]'); await page.waitForSelector('[data-ct-pick="tchr"]', { timeout: 10000 }); await page.waitForTimeout(800);
  await page.fill('#ctf_t', 'مطلب آزمایشی مرحله ۲ (حذف‌شدنی)'); await page.fill('#ctf_lead', 'لید آزمایشی'); await page.fill('#ctf_body', 'بند آزمایشی برای بررسی نویسندهٔ پروفایلی.');
  const whoLabel = await page.evaluate(() => (document.querySelector('label[for="ctf_who"] .lbl') || {}).textContent || '');
  await page.fill('[data-ct-pick-q="tchr"]', NAME.split(' ')[0]); await page.waitForTimeout(300);
  await page.click(`[data-ct-pick-set="tchr"][data-ct-pick-id="${PID}"]`); await page.waitForTimeout(300);
  await page.$eval('[data-ct-people]', el => el.scrollIntoView()); await shot(page, 'stage2-06-article-author-d.png', false);
  await page.click('[data-ct-save]'); await page.waitForFunction(() => !document.querySelector('[data-ct-editor]'), null, { timeout: 15000 }); await page.waitForTimeout(800);
  const artRow = await page.evaluate(() => { const r = document.querySelector('[data-ct-row]'); return r ? { id: r.getAttribute('data-ct-row'), text: r.textContent.replace(/\s+/g, ' ').slice(0, 200) } : null; });
  note('5 article saved: whoLabel="' + whoLabel + '" row=' + JSON.stringify(artRow));
  const ART = artRow && artRow.id;
  // 6) manager with ev_create: picker available from public content; no owner API
  await page.context().clearCookies(); await login(creds.manager);
  await openEvent(EV);
  const mgr = await page.evaluate(() => ({ picker: !!document.querySelector('[data-ct-pick-set="tchr"]') || !!document.querySelector('[data-ct-pick-current]'), manage: !!document.querySelector('[data-ct-pick-manage]'),
    ownerCalls: performance.getEntriesByType('resource').filter(r => /\/api\/owner\/site-content/.test(r.name)).length, publicCalls: performance.getEntriesByType('resource').filter(r => /\/api\/public\/site-content/.test(r.name)).length }));
  note('6 manager editor: ' + JSON.stringify(mgr));
  await page.setViewportSize({ width: 390, height: 844 }); await openEvent(EV);
  await page.$eval('[data-ct-people]', el => el.scrollIntoView()); await page.waitForTimeout(300);
  note('6 mobile overflowX=' + (await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1)));
  await shot(page, 'stage2-07-picker-m.png', false);
  // 7) cleanup (test DB): unlink event, archive article, delete the test person
  await page.setViewportSize({ width: 1280, height: 800 }); await page.context().clearCookies(); await login(creds.owner);
  const clean = await page.evaluate(async ({ ev, art, id }) => { const h = (() => { const csrf = (document.cookie.match(/nora_csrf=([^;]+)/) || [])[1] || ''; return { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }; })();
    const e = await fetch(`/api/admin/content/events/${ev}`, { credentials: 'include' }).then(r => r.json());
    const u = await fetch(`/api/admin/content/events/${ev}`, { method: 'PUT', credentials: 'include', headers: h, body: JSON.stringify({ record: { tchr: '' }, expected_version: e.version }) });
    let a = null; if (art) { const cur = await fetch(`/api/admin/content/articles/${art}`, { credentials: 'include' }).then(r => r.json());
      a = (await fetch(`/api/admin/content/articles/${art}`, { method: 'PUT', credentials: 'include', headers: h, body: JSON.stringify({ record: { tchr: '' }, expected_version: cur.version }) })).status;
      const cur2 = await fetch(`/api/admin/content/articles/${art}`, { credentials: 'include' }).then(r => r.json());
      a = [a, (await fetch(`/api/admin/content/articles/${art}/status`, { method: 'POST', credentials: 'include', headers: h, body: JSON.stringify({ status: 'archived', expected_version: cur2.version }) })).status]; }
    const site = await fetch('/api/owner/site-content', { credentials: 'include' }).then(r => r.json());
    const d = await fetch('/api/owner/site-content', { method: 'PATCH', credentials: 'include', headers: h, body: JSON.stringify({ content: { people: site.content.people.filter(p => p.id !== id) }, expected_version: site.version }) });
    return { unlink: u.status, article: a, deletePerson: d.status }; }, { ev: EV, art: ART, id: PID });
  note('7 cleanup: ' + JSON.stringify(clean));
  fs.writeFileSync(path.join(__dirname, 'stage2-pickers-check.json'), JSON.stringify(out, null, 2));
  await browser.close();
})().catch((e) => { note('FATAL ' + e.message); fs.writeFileSync(path.join(__dirname, 'stage2-pickers-check.json'), JSON.stringify(out, null, 2)); process.exit(1); });
