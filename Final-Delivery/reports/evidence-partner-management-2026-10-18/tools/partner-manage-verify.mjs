// Real-server verification of owner partner management (isolated test env, test data only).
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const ORIGIN = 'http://127.0.0.1:8000';
const OUT = process.env.OUT || '/tmp/qa/partner-manage'; fs.mkdirSync(OUT, { recursive: true });
const PY = '/home/user/venvs/nora/bin/python';
const OWNER_PW = fs.readFileSync('/tmp/nora-preview/owner-pw.txt', 'utf8').trim();
const results = []; let fails = 0;
const ok = (cond, name, detail = '') => { const d = typeof detail === 'string' ? detail : JSON.stringify(detail); results.push({ ok: !!cond, name, detail: d }); if (!cond) fails++; console.log((cond ? 'PASS ' : 'FAIL ') + name + (d ? ' — ' + d : '')); };
const pub = async () => (await (await fetch(ORIGIN + '/api/public/site-content')).json()).content;
const snapshotOthers = c => JSON.stringify({ events: c.events, people: c.people, articles: c.articles, banners: c.banners, library: c.library, cooperation: c.cooperation });
async function launch() { let b; for (let i = 0; i < 4; i++) { try { b = await launchBrowser(); break; } catch (e) { if (i === 3) throw e; await new Promise(r => setTimeout(r, 1500)); } } return b; }
async function session(w, h, theme) {
  const browser = await launch();
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, locale: 'fa-IR', serviceWorkers: 'block', isMobile: w < 600, hasTouch: w < 600 });
  const page = await ctx.newPage();
  const errors = [], dialogs = [], patches = [];
  page.on('pageerror', e => errors.push(String(e.message)));
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errors.push(m.text()); });
  page.on('dialog', d => { dialogs.push({ type: d.type(), message: d.message() }); d.accept(); });
  page.on('request', r => { if (r.method() === 'PATCH' && r.url().includes('/api/owner/site-content')) patches.push(r.postDataJSON()); });
  if (theme) await page.addInitScript(t => { try { localStorage.setItem('nora-theme', t); } catch (e) {} }, theme);
  return { browser, ctx, page, errors, dialogs, patches };
}
async function loginUI(page) {
  await page.goto(ORIGIN + '/login.html?mode=staff&next=admin.html%23partners', { waitUntil: 'load' });
  await page.waitForSelector('#lgStaffUsername', { timeout: 15000 });
  await page.fill('#lgStaffUsername', 'preview-owner'); await page.fill('#lgStaffPassword', OWNER_PW);
  await page.click('#lgStaffSubmit');
  await page.waitForSelector('#lgContinue', { timeout: 20000 });
  const target = await page.$eval('#lgContinue', a => a.getAttribute('href'));
  if (target !== 'admin.html#partners') throw new Error('unexpected login target ' + target);
  await page.click('#lgContinue');
  await page.waitForURL(/admin\.html#partners/, { timeout: 20000 });
}
const waitRows = (page, n) => page.waitForFunction(c => document.querySelectorAll('[data-ppartner-row]').length === c, n, { timeout: 15000 });
const state = page => page.evaluate(() => { const el = document.getElementById('ppPartnerSrvState'); return el ? { text: el.textContent, state: el.dataset.state || '' } : null; });
const waitState = (page, st, needle) => page.waitForFunction(([s, n]) => { const el = document.getElementById('ppPartnerSrvState'); return el && el.dataset.state === s && (!n || el.textContent.includes(n)); }, [st, needle], { timeout: 20000 });
const toastText = page => page.evaluate(() => (document.getElementById('toast') || {}).textContent || '');
const fill = async (page, field, value) => { const sel = `[data-ppartner-field="${field}"]`; await page.fill(sel, value); };

console.log(execFileSync(PY, ['/tmp/nora-preview/seed_partners.py'], { cwd: '/tmp/nora-preview' }).toString().trim().split('\n').slice(-2).join(' | '));
const baseline = await pub(); const othersBefore = snapshotOthers(baseline);
ok(baseline.partners.length === 4, 'baseline: 4 public test partners seeded', baseline.partners.map(p => p.id));

// ── 1) desktop light: list from server, add, edit, malicious, conflict, delete ──
let managedId = '';
{
  const { browser, page, errors, dialogs, patches } = await session(1280, 800, '');
  await loginUI(page);
  await page.waitForSelector('#ppPartnerManager', { timeout: 20000 });
  await waitRows(page, 4); await waitState(page, 'success');
  const s0 = await state(page);
  const listText = await page.evaluate(() => document.getElementById('ppPartnerList').textContent);
  ok(/۴ نهاد منتشرشده از سرور/.test(s0.text) && /نسخهٔ/.test(s0.text), '1. owner session: list of 4 server partners with server version', s0.text);
  ok(!/گروه آموزشی نمونه|فضای فرهنگی نمونه|انجمن کتاب‌خوانی/.test(listText) && /نهاد همکار آزمایشی \(دادهٔ تست\)/.test(listText), 'fixture data.js partners are not shown; server names are', '');
  const ui = await page.evaluate(() => ({ pub: !!document.querySelector('[data-ppartner-pub]'), hide: !!document.querySelector('[data-ppartner-hide]'), del: document.querySelectorAll('[data-ppartner-del]').length, pageLinks: [...document.querySelectorAll('[data-ppartner-row] a[href^="partner.html?id="]')].map(a => a.getAttribute('href')), scrollW: document.documentElement.scrollWidth, innerW: innerWidth }));
  ok(!ui.pub && !ui.hide && ui.del === 4 && ui.pageLinks.length === 4 && ui.scrollW === ui.innerW, 'no local publish/hide controls; delete + public page link per row; no horizontal scroll', ui);
  await page.screenshot({ path: `${OUT}/admin-partners-desktop-light.png` });

  // add with an invalid contact first (client validation blocks; no PATCH)
  await page.click('[data-ppartner-new]'); await page.waitForSelector('[data-ppartner-field="n"]');
  await fill(page, 'n', 'نهاد مدیریت‌شده از پنل (دادهٔ تست)'); await fill(page, 'type', 'خدماتی · آزمایشی'); await fill(page, 's', 'این نهاد از پنل مالک روی سرور تست ثبت شد.');
  await fill(page, 'collab', 'میزبانی (تست)'); await fill(page, 'since', 'آبان ۱۴۰۵'); await fill(page, 'focus', 'آموزش، رسانه'); await fill(page, 'href', 'example.org/managed'); await fill(page, 'd', 'شرح کامل نهاد مدیریت‌شده.\nخط دوم.');
  await page.click('[data-ppartner-link-add]'); await page.click('[data-ppartner-link-kind="0"][data-ppartner-kind="web"]'); await page.fill('[data-ppartner-link="0"]', 'javascript:alert(1)');
  await page.screenshot({ path: `${OUT}/admin-partner-editor-desktop-light.png` });
  const patchesBefore = patches.length; await page.click('[data-ppartner-save]'); await page.waitForTimeout(600);
  ok(patches.length === patchesBefore && /راه‌های تماس معتبر نیست/.test(await toastText(page)) && !!(await page.$('[data-ppartner-save]')), '2a. javascript: contact is rejected client-side before any request', await toastText(page));
  await page.click('[data-ppartner-link-kind="0"][data-ppartner-kind="mail"]'); await page.fill('[data-ppartner-link="0"]', 'managed@example.org');
  await page.click('[data-ppartner-save]'); await waitState(page, 'success', 'ذخیره شد'); await waitRows(page, 5);
  const added = patches[patches.length - 1];
  managedId = added.content.partners[4].id;
  ok(Object.keys(added.content).join() === 'partners' && Number.isInteger(added.expected_version) && added.content.partners.length === 5 && /^org\d+/.test(managedId), '2b. PATCH carries only partners + expected_version', { keys: Object.keys(added.content), id: managedId });
  const afterAdd = await pub(); const srvRow = afterAdd.partners.find(p => p.id === managedId);
  ok(!!srvRow && srvRow.n === 'نهاد مدیریت‌شده از پنل (دادهٔ تست)' && srvRow.href === 'https://example.org/managed' && srvRow.collab === 'میزبانی (تست)' && srvRow.focus.join() === 'آموزش,رسانه' && srvRow.links.length === 1 && srvRow.links[0].k === 'mail' && srvRow.links[0].v === 'mailto:managed@example.org', '2c. public API publishes the new partner with all fields', srvRow);
  ok(snapshotOthers(afterAdd) === othersBefore, '8. events/people/articles/banners/library/cooperation unchanged after add', '');
  const r1 = await fetch(`${ORIGIN}/partner.html?id=${encodeURIComponent(managedId)}`); const h1 = await r1.text();
  ok(r1.status === 200 && h1.includes('<meta name="robots" content="index,follow"/>') && h1.includes(`<link rel="canonical" href="/partner.html?id=${encodeURIComponent(managedId)}"/>`) && h1.includes('نهاد مدیریت‌شده از پنل (دادهٔ تست) | نهادهای همکار نورا'), '2d. dedicated page is live (200, index, canonical, title)', r1.status);

  // edit: protocol-relative logo rejected client-side; rename persists after reload
  await page.click(`[data-ppartner-edit="${managedId}"]`); await page.waitForSelector('[data-ppartner-field="n"]');
  await fill(page, 'logo', '//evil.example/x.png'); const pb = patches.length; await page.click('[data-ppartner-save]'); await page.waitForTimeout(500);
  ok(patches.length === pb && /لوگو معتبر نیست/.test(await toastText(page)), '9a. protocol-relative logo rejected client-side', await toastText(page));
  await fill(page, 'logo', '/icon-192.png'); await fill(page, 'n', 'نهاد مدیریت‌شده (ویرایش‌شده · دادهٔ تست)');
  await page.click('[data-ppartner-save]'); await waitState(page, 'success', 'ذخیره شد');
  await page.reload({ waitUntil: 'load' }); await page.waitForSelector('#ppPartnerManager', { timeout: 20000 }); await waitRows(page, 5);
  const rowText = await page.evaluate(id => document.querySelector(`[data-ppartner-row="${id}"]`).textContent, managedId);
  const afterEdit = await pub(); const edited = afterEdit.partners.find(p => p.id === managedId);
  const r2 = await fetch(`${ORIGIN}/partner.html?id=${encodeURIComponent(managedId)}`); const h2 = await r2.text();
  ok(/ویرایش‌شده/.test(rowText) && edited.n === 'نهاد مدیریت‌شده (ویرایش‌شده · دادهٔ تست)' && edited.logo === '/icon-192.png' && h2.includes('نهاد مدیریت‌شده (ویرایش‌شده · دادهٔ تست) | نهادهای همکار نورا') && h2.includes('<meta property="og:image" content="/icon-192.png"/>') && h2.includes(`<link rel="canonical" href="/partner.html?id=${encodeURIComponent(managedId)}"/>`), '3/10. edit persists after reload; public page keeps valid SEO/canonical/og:image', { rowText: rowText.slice(0, 60) });

  // malicious name/description/href via the panel
  await page.click(`[data-ppartner-edit="${managedId}"]`); await page.waitForSelector('[data-ppartner-field="n"]');
  await fill(page, 'n', '<img src=x onerror=alert(1)> نهاد مدیریت‌شده (دادهٔ تست)'); await fill(page, 'd', '<script>alert(1)</script> شرح'); await fill(page, 'href', 'https://user:pw@example.org/');
  const pb2 = patches.length; await page.click('[data-ppartner-save]'); await page.waitForTimeout(500);
  ok(patches.length === pb2 && /وبگاه را با نشانی معتبر/.test(await toastText(page)), '9b. credentialed website URL rejected client-side', await toastText(page));
  await fill(page, 'href', 'https://example.org/managed'); await page.click('[data-ppartner-save]'); await waitState(page, 'success', 'ذخیره شد');
  const mal = (await pub()).partners.find(p => p.id === managedId);
  const rowHtml = await page.evaluate(id => ({ imgs: document.querySelectorAll(`[data-ppartner-row="${id}"] img:not(.pp-mini img)`).length, text: document.querySelector(`[data-ppartner-row="${id}"] b`).textContent }), managedId);
  ok(mal.n.startsWith('<img src=x onerror=alert(1)>') && mal.d.startsWith('<script>') && dialogs.filter(d => d.type === 'alert').length === 0 && rowHtml.text.startsWith('<img') && errors.length === 0, '9c. malicious text stored as inert text; panel renders it escaped; no alert/JS error', { dialogs, errors });
  const { browser: b2, page: p2, dialogs: d2, errors: e2 } = await session(1280, 800, '');
  await p2.goto(`${ORIGIN}/partner.html?id=${encodeURIComponent(managedId)}`, { waitUntil: 'load' }); await p2.waitForFunction(() => window.NORA_PUBLIC_SOURCE, null, { timeout: 15000 }); await p2.waitForTimeout(400);
  const pageH1 = await p2.evaluate(() => ({ h1: document.querySelector('.partner-profile h1')?.textContent || '', imgs: document.querySelectorAll('.partner-profile img').length, scripts: document.querySelectorAll('.partner-profile script').length }));
  ok(pageH1.h1.startsWith('<img src=x') && pageH1.imgs === 1 && pageH1.scripts === 0 && d2.length === 0 && e2.length === 0, '9d. public page renders the malicious name as text (only the real logo img)', pageH1);
  await p2.screenshot({ path: `${OUT}/partner-managed-after-edit-desktop.png` }); await b2.close();
  // restore a clean name for the remaining steps
  await page.click(`[data-ppartner-edit="${managedId}"]`); await page.waitForSelector('[data-ppartner-field="n"]'); await fill(page, 'n', 'نهاد مدیریت‌شده (دادهٔ تست)'); await fill(page, 'd', 'شرح پاک.'); await page.click('[data-ppartner-save]'); await waitState(page, 'success', 'ذخیره شد');

  // concurrency: another session changes a different partner → stale expected_version → 409, nothing lost
  const external = await page.evaluate(async () => {
    const api = window.NORA_SERVER_API; const cur = await api.getOwnerSiteContent();
    const rows = cur.content.partners.map(r => Object.assign({}, r)); const other = rows.find(r => r.id === 'qa-partner-xss'); other.type = 'تغییر هم‌زمان شخص دیگر';
    const res = await api.updateSiteContent({ partners: rows }, cur.version); return { from: cur.version, to: res.version };
  });
  await page.click(`[data-ppartner-edit="${managedId}"]`); await page.waitForSelector('[data-ppartner-field="type"]'); await fill(page, 'type', 'نوع پس از تعارض');
  await page.click('[data-ppartner-save]'); await waitState(page, 'error', 'هم‌زمان');
  await page.waitForFunction(() => document.querySelector('[data-ppartner-save]') && !document.querySelector('[data-ppartner-save][disabled]'), null, { timeout: 15000 });
  const afterConflict = await pub();
  ok(afterConflict.partners.find(p => p.id === 'qa-partner-xss').type === 'تغییر هم‌زمان شخص دیگر' && afterConflict.partners.find(p => p.id === managedId).type !== 'نوع پس از تعارض' && (await page.$eval('[data-ppartner-field="type"]', e => e.value)) === 'نوع پس از تعارض', '7a. 409: other person\'s change kept, my change not applied, my draft still open', external);
  await page.screenshot({ path: `${OUT}/admin-partner-conflict-desktop.png` });
  await page.click('[data-ppartner-save]'); await waitState(page, 'success', 'ذخیره شد');
  const afterRetry = await pub();
  ok(afterRetry.partners.find(p => p.id === 'qa-partner-xss').type === 'تغییر هم‌زمان شخص دیگر' && afterRetry.partners.find(p => p.id === managedId).type === 'نوع پس از تعارض', '7b. retry on fresh version keeps both changes', '');

  // network failure on save → no false success
  await page.route('**/api/owner/site-content', r => r.request().method() === 'PATCH' ? r.abort() : r.continue());
  await page.click(`[data-ppartner-edit="${managedId}"]`); await page.waitForSelector('[data-ppartner-field="s"]'); await fill(page, 's', 'نباید ذخیره شود');
  await page.click('[data-ppartner-save]'); await waitState(page, 'error', 'دسترسی نیست');
  ok((await pub()).partners.find(p => p.id === managedId).s !== 'نباید ذخیره شود' && !!(await page.$('[data-ppartner-save]')) && !/ذخیره شد/.test((await state(page)).text), '12. network failure: error message, editor stays open, nothing published', (await state(page)).text);
  await page.unroute('**/api/owner/site-content'); await page.click('[data-ppartner-cancel]');

  // home shows the managed partner
  const { browser: b3, page: p3 } = await session(390, 844, '');
  await p3.goto(ORIGIN + '/home.html', { waitUntil: 'load' }); await p3.waitForFunction(() => window.NORA_PUBLIC_SOURCE === 'server', null, { timeout: 15000 });
  const homeHas = await p3.evaluate(id => !!document.querySelector(`#logoWall a[href="partner.html?id=${encodeURIComponent(id)}"]`), managedId);
  ok(homeHas, '2e. home partners section lists the managed partner', managedId); await b3.close();

  // delete with explicit confirm; related event untouched
  const evBefore = (await pub()).events.find(e => e.id === 'qa-ev-1');
  const dBefore = dialogs.length; await page.click(`[data-ppartner-del="${managedId}"]`); await waitState(page, 'success', 'حذف');
  ok(dialogs.length === dBefore + 1 && dialogs[dBefore].type === 'confirm' && /حذف شود/.test(dialogs[dBefore].message), '4a. delete asks for explicit confirmation', dialogs[dBefore]);
  await page.reload({ waitUntil: 'load' }); await page.waitForSelector('#ppPartnerManager', { timeout: 20000 }); await waitRows(page, 4);
  const afterDel = await pub(); const r404 = await fetch(`${ORIGIN}/partner.html?id=${encodeURIComponent(managedId)}`);
  const { browser: b4, page: p4 } = await session(1280, 800, '');
  await p4.goto(ORIGIN + '/home.html', { waitUntil: 'load' }); await p4.waitForFunction(() => window.NORA_PUBLIC_SOURCE === 'server', null, { timeout: 15000 });
  const homeGone = await p4.evaluate(id => !document.querySelector(`#logoWall a[href="partner.html?id=${encodeURIComponent(id)}"]`), managedId); await b4.close();
  ok(!afterDel.partners.some(p => p.id === managedId) && r404.status === 404 && homeGone && JSON.stringify(afterDel.events.find(e => e.id === 'qa-ev-1')) === JSON.stringify(evBefore) && snapshotOthers(afterDel) === othersBefore, '4b/8. after reload: gone from public API, home and page (404); events & other categories untouched', { status: r404.status });
  ok(errors.length === 0, 'no JS errors during the owner flow', errors);
  await browser.close();
}

// ── 5) publish boundary from the owner view ──
{
  const ownerView = execFileSync(PY, ['-c', `
import json; from owner_api import call, login; login()
st, cur = call("GET", "/api/owner/site-content"); print(json.dumps({"st": st, "ids": [p["id"] for p in cur["content"]["partners"]]}))`], { cwd: '/tmp/nora-preview' }).toString().trim();
  const ov = JSON.parse(ownerView.split('\n').pop());
  const publicIds = (await pub()).partners.map(p => p.id);
  ok(ov.st === 200 && !ov.ids.some(id => /unpublished|private|paused|pending/.test(id)) && !publicIds.some(id => /unpublished|private|paused|pending/.test(id)), '5. owner view and public API expose only published partners (non-public rows never reach the panel)', { owner: ov.ids, public: publicIds });
}

// ── 6) no valid session ──
{
  const { browser, page } = await session(1280, 800, '');
  await page.goto(ORIGIN + '/admin.html#partners', { waitUntil: 'load' }); await page.waitForTimeout(1500);
  const gate = await page.evaluate(() => ({ manager: !!document.getElementById('ppPartnerManager'), login: !!document.querySelector('a[href^="login.html?mode=staff"]'), text: document.getElementById('admBody').textContent.slice(0, 80) }));
  const g = await fetch(ORIGIN + '/api/owner/site-content'); const p = await fetch(ORIGIN + '/api/owner/site-content', { method: 'PATCH', headers: { 'Content-Type': 'application/json', Origin: ORIGIN }, body: JSON.stringify({ content: { partners: [] }, expected_version: 0 }) });
  ok(!gate.manager && gate.login && g.status === 401 && p.status === 401 && (await pub()).partners.length === 4, '6. without a session: login gate only; GET/PATCH owner API → 401; nothing changed', { gate, get: g.status, patch: p.status });
  await browser.close();
}

// ── 11) mobile dark: panel usable ──
{
  const { browser, page, errors } = await session(390, 844, 'dark');
  await loginUI(page); await page.waitForSelector('#ppPartnerManager', { timeout: 20000 }); await waitRows(page, 4); await waitState(page, 'success');
  await page.evaluate(() => document.getElementById('ppPartnerManager').scrollIntoView({ block: 'start' })); await page.waitForTimeout(300);
  const m = await page.evaluate(() => ({ scrollW: document.documentElement.scrollWidth, innerW: innerWidth, theme: document.documentElement.dataset.theme, btn: document.querySelector('[data-ppartner-new]').getBoundingClientRect().height }));
  await page.screenshot({ path: `${OUT}/admin-partners-mobile-dark.png` });
  await page.click('[data-ppartner-new]'); await page.waitForSelector('[data-ppartner-field="n"]'); await page.waitForTimeout(300);
  const m2 = await page.evaluate(() => ({ scrollW: document.documentElement.scrollWidth, innerW: innerWidth }));
  await page.screenshot({ path: `${OUT}/admin-partner-editor-mobile-dark.png` });
  await page.click('[data-ppartner-cancel]');
  ok(m.scrollW === m.innerW && m2.scrollW === m2.innerW && m.theme === 'dark' && m.btn >= 32 && errors.length === 0, '11. mobile 390×844 dark: list + editor without horizontal scroll, no JS errors', { m, m2, errors });
  await browser.close();
}
{
  const { browser, page } = await session(1280, 800, 'dark');
  await loginUI(page); await page.waitForSelector('#ppPartnerManager', { timeout: 20000 }); await waitRows(page, 4); await waitState(page, 'success');
  await page.evaluate(() => document.getElementById('ppPartnerManager').scrollIntoView({ block: 'start' })); await page.waitForTimeout(300);
  await page.screenshot({ path: `${OUT}/admin-partners-desktop-dark.png` });
  await browser.close();
}
const finalPub = await pub();
ok(finalPub.partners.length === 4 && snapshotOthers(finalPub) === othersBefore, 'final: test DB back to 4 seeded partners; other categories byte-identical', '');
fs.writeFileSync(`${OUT}/result.json`, JSON.stringify(results, null, 2));
console.log(`${results.length - fails} passed, ${fails} failed`);
process.exit(fails ? 1 : 0);
