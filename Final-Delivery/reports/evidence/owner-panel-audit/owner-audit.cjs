// Owner-panel from-zero audit driver (development-only QA; test DB + test owner account only).
// Run: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<dir-with-node_modules> node owner-audit.cjs
// Writes: audit.json (per-step console errors, failed requests, overflow, dead-button probes) + PNG screenshots.
const path = require('node:path');
const fs = require('node:fs');
const uiRoot = path.resolve(__dirname, '../../../website/nora-ui');
const { launchBrowser } = require(path.join(uiRoot, 'tools/browser-launch.cjs'));
const BASE = process.env.NORA_QA_BASE || 'http://127.0.0.1:8000';
const OUT = __dirname;
const creds = (() => {
  const txt = fs.readFileSync(path.join(uiRoot, 'PREVIEW-LOGIN.local.md'), 'utf8');
  const m = txt.match(/مالک:\s*`([^`]+)`\s*\/\s*`([^`]+)`/);
  if (!m) throw new Error('owner credentials line not found');
  return { user: m[1], pass: m[2] };
})();
const steps = [];
let cur = null;
const DESKTOP = { width: 1280, height: 800 }, MOBILE = { width: 390, height: 844 };
function begin(name) { cur = { name, console: [], pageErrors: [], failed: [], notes: [], shots: [], requests: [] }; steps.push(cur); return cur; }
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function settle(page, ms = 700) { await sleep(ms); try { await page.waitForLoadState('networkidle', { timeout: 4000 }); } catch {} }
async function metrics(page) {
  return page.evaluate(() => ({
    overflowX: document.documentElement.scrollWidth > window.innerWidth + 1,
    scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth,
    buttons: document.querySelectorAll('#admBody button:not([disabled])').length,
    head: (document.querySelector('#admBody .head') || {}).textContent || '',
    text: (document.querySelector('#admBody') || document.body).innerText.slice(0, 400),
    apiUnavailable: [...document.querySelectorAll('#admBody .tag, #admBody span')].filter(e => /API متصل نیست/.test(e.textContent)).length
  }));
}
async function shot(page, tag, viewport) {
  const vp = viewport || DESKTOP;
  await page.setViewportSize(vp);
  await sleep(250);
  const file = `${tag}-${vp.width === 390 ? 'm' : 'd'}.png`;
  await page.screenshot({ path: path.join(OUT, file), fullPage: vp.width !== 390 });
  const m = await metrics(page);
  cur.shots.push({ file, viewport: `${vp.width}x${vp.height}`, ...m });
  if (vp !== DESKTOP) await page.setViewportSize(DESKTOP);
  return m;
}
async function setState(page, patch) {
  const write = () => page.evaluate(p => { const s = JSON.parse(localStorage.getItem('nora-admin') || '{}'); Object.assign(s, p); localStorage.setItem('nora-admin', JSON.stringify(s)); }, patch);
  for (let attempt = 0; attempt < 3; attempt++) {
    await write(); await sleep(400); await write();
    await page.goto(`${BASE}/admin.html?_=${Date.now()}`, { waitUntil: 'domcontentloaded' });
    await settle(page, 1200);
    const ok = await page.evaluate(p => { const s = JSON.parse(localStorage.getItem('nora-admin') || '{}'); return Object.keys(p).every(k => JSON.stringify(s[k]) === JSON.stringify(p[k])); }, patch);
    if (ok) return;
    cur.notes.push('setState retry ' + (attempt + 1) + ' for ' + JSON.stringify(patch));
  }
}
async function click(page, sel, wait = 900) {
  const el = page.locator(sel).first();
  if (!(await el.count())) { cur.notes.push(`MISSING selector ${sel}`); return false; }
  await el.click({ timeout: 5000 }).catch(e => cur.notes.push(`CLICK FAIL ${sel}: ${e.message.split('\n')[0]}`));
  await settle(page, wait);
  return true;
}
async function bodyText(page) { return page.evaluate(() => (document.querySelector('#admBody') || document.body).innerText); }
async function toastText(page) { return page.evaluate(() => { const t = document.getElementById('toast'); return t ? t.textContent.trim() : ''; }); }
// Dead-button probe: click every non-destructive control in #admBody once; record whether DOM, toast, URL hash or network changed.
const SKIP = /data-rec-refund|data-rec-decide|data-rec[a-z-]*(refund|cancel|grant|revoke)|data-(server-logout|ct-set|ct-save|ct-save-publish|ct-image-clear|ct-media-del|ei-res-del|ei-res-remove|ei-res-publish|rcok|rcno|certapprove|certreject|noticeapprove|noticereject|att-undo|att-checkin|role|mesave|svc-del|svc-save|svc-test|svc-reset|data-del|data-upload|ppartner-pub|ppartner-del|wf-decide|decision|approve|reject|reset)|type="file"|href="http/;
async function probeButtons(page, label, max = 40) {
  const total = (await page.$$('#admBody button:not([disabled]), #admBody a.btn')).length;
  const results = [];
  let n = 0;
  for (let i = 0; i < total && n < max; i++) {
    const handles = await page.$$('#admBody button:not([disabled]), #admBody a.btn');
    const h = handles[i]; if (!h) break;
    const info = await h.evaluate(el => ({ html: el.outerHTML.slice(0, 160), text: el.textContent.trim().slice(0, 40), visible: !!(el.offsetWidth || el.offsetHeight) })).catch(() => null);
    if (!info || !info.visible || SKIP.test(info.html)) continue;
    n++;
    const before = await page.evaluate(() => ({ html: document.querySelector('#admBody').innerHTML.length, toast: (document.getElementById('toast') || {}).textContent || '', url: location.href, open: document.querySelectorAll('.sheet.open, dialog[open], .modal.open').length }));
    let reqs = 0; const onReq = r => { if (r.url().startsWith(BASE + '/api/')) reqs++; };
    page.on('request', onReq);
    await h.click({ timeout: 2500 }).catch(() => {});
    await sleep(650);
    page.off('request', onReq);
    const after = await page.evaluate(() => ({ html: document.querySelector('#admBody').innerHTML.length, toast: (document.getElementById('toast') || {}).textContent || '', url: location.href, open: document.querySelectorAll('.sheet.open, dialog[open], .modal.open').length }));
    const effect = before.html !== after.html || before.toast !== after.toast || before.url !== after.url || before.open !== after.open || reqs > 0;
    results.push({ text: info.text, html: info.html.slice(0, 110), effect, reqs });
    if (!effect) cur.notes.push(`NO-EFFECT button [${label}] "${info.text}" ${info.html.slice(0, 90)}`);
    // return to the view under probe
    if (before.url !== after.url || before.open !== after.open) { await page.keyboard.press('Escape').catch(() => {}); }
  }
  cur.probe = { label, tested: results.length, noEffect: results.filter(r => !r.effect).length, items: results };
}
(async () => {
  const browser = await launchBrowser();
  const ctx = await browser.newContext({ viewport: DESKTOP, locale: 'fa-IR', timezoneId: 'Asia/Tehran' });
  const page = await ctx.newPage();
  page.on('console', m => { if (cur && ['error', 'warning'].includes(m.type())) cur.console.push(`${m.type()}: ${m.text().slice(0, 240)}`); });
  page.on('pageerror', e => { if (cur) cur.pageErrors.push(String(e.message || e).slice(0, 240)); });
  page.on('request', r => { if (cur && r.url().startsWith(BASE + '/api/')) { const k = r.method() + ' ' + r.url().replace(BASE, '').replace(/[0-9a-f]{8}-[0-9a-f-]{27}/g, '{uuid}').replace(/\?.*$/, ''); if (!cur.requests.includes(k)) cur.requests.push(k); } });
  page.on('dialog', d => { if (cur) cur.notes.push('dialog(' + d.type() + '): ' + d.message().slice(0, 140)); (d.type() === 'prompt' ? d.dismiss() : d.accept()).catch(() => {}); });
  page.on('response', r => { if (cur && r.status() >= 400) cur.failed.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, '')}`); });
  try {
    // 1. login
    begin('01-login');
    await page.goto(`${BASE}/login.html?mode=staff&next=admin.html`, { waitUntil: 'domcontentloaded' });
    await settle(page, 1200);
    await shot(page, '01-login');
    await shot(page, '01-login', MOBILE);
    await page.fill('#lgStaffUsername', creds.user);
    await page.fill('#lgStaffPassword', creds.pass);
    await page.click('#lgStaffSubmit');
    await settle(page, 2500);
    cur.notes.push('url after submit: ' + page.url() + ' | text=' + (await page.evaluate(() => document.body.innerText.slice(0, 200))).replace(/\n/g, ' / '));
    await shot(page, '01-login-confirmed');
    const go = page.getByText('رفتن به پنل مدیریت').first();
    if (await go.count()) { await go.click(); cur.notes.push('clicked "رفتن به پنل مدیریت"'); }
    await page.waitForURL(/admin\.html/, { timeout: 15000 }).catch(e => cur.notes.push('no redirect to admin: ' + e.message.split('\n')[0]));
    if (!/admin\.html/.test(page.url())) await page.goto(`${BASE}/admin.html`, { waitUntil: 'domcontentloaded' });
    await settle(page, 1500);
    cur.notes.push('url after login: ' + page.url());
    const me = await page.evaluate(() => fetch('/api/auth/me', { credentials: 'include' }).then(r => r.json()).catch(e => ({ error: String(e) })));
    cur.notes.push('auth/me role=' + (me && me.role) + ' perms=' + ((me && me.permissions) || []).length);

    // 2. dashboard
    begin('02-dash');
    await setState(page, { sec: 'dash' });
    await shot(page, '02-dash');
    await shot(page, '02-dash', MOBILE);
    await page.evaluate(() => localStorage.setItem('nora-theme', 'dark'));
    await page.reload({ waitUntil: 'domcontentloaded' }); await settle(page, 1200);
    await shot(page, '02-dash-dark');
    await shot(page, '02-dash-dark', MOBILE);
    await page.evaluate(() => localStorage.setItem('nora-theme', 'light'));
    await page.reload({ waitUntil: 'domcontentloaded' }); await settle(page, 1200);
    await probeButtons(page, 'dash', 30);
    // module map
    await setState(page, { sec: 'dash' });
    if (await click(page, '[data-dashx-map]')) { await shot(page, '02-dash-map'); await shot(page, '02-dash-map', MOBILE); }

    // 3. events list + editor + lifecycle
    begin('03-events-list');
    await setState(page, { sec: 'events' });
    await shot(page, '03-events-list');
    await shot(page, '03-events-list', MOBILE);
    await probeButtons(page, 'events-list', 25);
    await setState(page, { sec: 'events' });

    begin('04-event-new-validation');
    await click(page, '[data-ct-new]');
    await shot(page, '04-event-new');
    await shot(page, '04-event-new', MOBILE);
    await click(page, '[data-ct-save]', 1500);
    cur.notes.push('empty save → field errors: ' + await page.evaluate(() => [...document.querySelectorAll('[data-ct-err]')].filter(e => e.textContent && /لازم|معتبر|پذیرفته/.test(e.textContent)).map(e => e.dataset.ctErr + ':' + e.textContent.trim()).join(' | ')));
    cur.notes.push('formError: ' + await page.evaluate(() => (document.querySelector('[data-ct-editor] p[style*="stop"]') || {}).textContent || ''));
    await shot(page, '04-event-new-errors');
    // bad date
    await page.fill('[data-ct-field="t"]', 'رویداد ممیزی از صفر (آزمایشی)');
    await page.fill('[data-ct-field="on"]', '1405/13/40');
    await click(page, '[data-ct-save]', 1500);
    cur.notes.push('bad jalali → ' + await page.evaluate(() => (document.querySelector('[data-ct-err="on"]') || {}).textContent || ''));
    await page.fill('[data-ct-field="on"]', '1405/09/15');
    await page.fill('[data-ct-field="when"]', 'یکشنبه ۱۵ آذر');
    await page.fill('[data-ct-field="time"]', '۱۰ تا ۱۲');
    await page.fill('[data-ct-field="place"]', 'سالن آزمایشی');
    await page.fill('[data-ct-field="startsAt"]', '1405/09/15 10:00');
    await page.fill('[data-ct-field="endsAt"]', '1405/09/15 09:00');
    await click(page, '[data-ct-save]', 1500);
    cur.notes.push('end<start → ' + await page.evaluate(() => [...document.querySelectorAll('[data-ct-err]')].filter(e => e.textContent.trim()).map(e => e.dataset.ctErr + ':' + e.textContent.trim()).join(' | ')) + ' // formError=' + await page.evaluate(() => (document.querySelector('[data-ct-editor] p[style*="stop"]') || {}).textContent || ''));
    await page.fill('[data-ct-field="endsAt"]', '1405/09/15 12:00');
    await page.fill('[data-ct-field="d"]', 'شرح آزمایشی برای ممیزی پنل مالک.');
    await page.fill('[data-ct-field="cap"]', '12');
    await click(page, '[data-ct-save]', 2000);
    cur.notes.push('draft save msg: ' + await page.evaluate(() => (document.querySelector('#admBody [role="status"] p') || {}).textContent || ''));
    await shot(page, '04-event-saved');

    begin('05-event-lifecycle');
    const row = page.locator('[data-ct-row]', { hasText: 'رویداد ممیزی از صفر' }).first();
    const newId = await row.getAttribute('data-ct-row').catch(() => null) || await row.locator('[data-ct-id]').first().getAttribute('data-ct-id').catch(() => null);
    cur.notes.push('new id: ' + newId);
    for (const st of ['published', 'paused', 'published', 'archived', 'draft']) {
      const b = row.locator(`[data-ct-set="${st}"]`).first();
      if (await b.count()) { await b.click(); await settle(page, 1500); cur.notes.push(`set ${st} → ` + (await page.evaluate(() => (document.querySelector('#admBody [role="status"] p') || {}).textContent || '')).slice(0, 160)); }
      else cur.notes.push(`set ${st}: button absent (status=${await row.locator('.tag').first().textContent().catch(() => '?')})`);
    }
    await shot(page, '05-event-lifecycle');
    // edit + stale version 409
    await row.locator('[data-ct-edit]').first().click().catch(() => cur.notes.push('edit button missing'));
    await settle(page, 1500);
    await shot(page, '05-event-edit');
    await shot(page, '05-event-edit', MOBILE);
    const bump = await page.evaluate(async (id) => {
      const api = window.NORA_SERVER_API; const r = await api.getAdminContent('events', id); 
      const rec = { t: r.record.t + ' (تغییر موازی)' };
      try { const u = await api.updateAdminContent('events', id, rec, r.version, 'nora_csrf'); return 'parallel update ok v' + u.version; } catch (e) { return 'parallel update failed ' + (e && e.code); }
    }, newId);
    cur.notes.push(bump);
    await page.fill('[data-ct-field="place"]', 'سالن آزمایشی ۲');
    await click(page, '[data-ct-save]', 1500);
    cur.notes.push('stale save → formError=' + await page.evaluate(() => (document.querySelector('[data-ct-editor] p[style*="stop"]') || {}).textContent || '') + ' | version tag=' + await page.evaluate(() => [...document.querySelectorAll('[data-ct-editor] .tag')].map(t => t.textContent).join(',')));
    await shot(page, '05-event-409');
    await click(page, '[data-ct-save]', 1500);
    cur.notes.push('retry save → ' + await page.evaluate(() => ((document.querySelector('#admBody [role="status"] p') || {}).textContent || '') + ' // ' + ((document.querySelector('[data-ct-editor] p[style*="stop"]') || {}).textContent || '')));
    cur.notes.push('editor has teacher/instructor field: ' + await page.evaluate(() => !!document.querySelector('[data-ct-field="tchr"],[data-wtchr],[data-winput="tchr"]')));

    // 6. articles
    begin('06-articles');
    await setState(page, { sec: 'events' });
    await click(page, '[data-ct-kind="articles"]');
    await shot(page, '06-articles-list');
    await click(page, '[data-ct-new]');
    await shot(page, '06-article-new');
    await page.fill('[data-ct-field="t"]', 'مطلب آزمایشی ممیزی');
    await page.fill('[data-ct-field="body"]', 'بند نخست.\n\nبند دوم.');
    const pubBtn = page.locator('[data-ct-save-publish]');
    if (await pubBtn.count()) { await pubBtn.click(); await settle(page, 1800); } else { await click(page, '[data-ct-save]', 1800); cur.notes.push('no save-publish button'); }
    cur.notes.push('article result: ' + await page.evaluate(() => (document.querySelector('#admBody [role="status"] p') || {}).textContent || ''));
    await shot(page, '06-article-saved');

    // 7. media panel + event interaction panel
    begin('07-media');
    await setState(page, { sec: 'events' });
    await click(page, '[data-ct-media]');
    await shot(page, '07-media');
    await click(page, '[data-ct-media-close]');
    begin('08-event-interaction');
    const paid = page.locator('[data-ct-row]', { hasText: 'ev-4bc3cc6c5d' }).first();
    const anyRow = (await paid.count()) ? paid : page.locator('[data-ct-row]').first();
    await anyRow.locator('[data-ct-interaction]').first().click().catch(() => cur.notes.push('interaction button missing'));
    await settle(page, 1500);
    await shot(page, '08-ei-resources');
    await shot(page, '08-ei-resources', MOBILE);
    for (const tab of ['questions', 'reviews', 'reports', 'recordings', 'orders']) {
      const t = page.locator(`[data-ei-tab="${tab}"]`).first();
      if (await t.count()) { await t.click(); await settle(page, 1200); await shot(page, `08-ei-${tab}`); } else cur.notes.push('ei tab absent: ' + tab);
    }
    await probeButtons(page, 'event-interaction', 20);

    // 9. users
    begin('09-users');
    await setState(page, { sec: 'users', uV: '', uHub: 'users' });
    await shot(page, '09-users-index');
    await shot(page, '09-users-index', MOBILE);
    await probeButtons(page, 'users-index', 25);
    await setState(page, { sec: 'users', uV: '', uHub: 'users' });
    const search = page.locator('[data-us-search], input[data-us-q], #usQ').first();
    if (await search.count()) { await search.fill('qa'); await page.keyboard.press('Enter'); await settle(page, 1200); cur.notes.push('search done'); } else cur.notes.push('user search input not found');
    await shot(page, '09-users-search');
    const openUser = page.locator('[data-user-open]').first();
    if (await openUser.count()) { await openUser.click(); await settle(page, 1800); } else cur.notes.push('no data-user-open rows');
    await shot(page, '09-user-detail');
    await shot(page, '09-user-detail', MOBILE);
    cur.notes.push('user detail tabs: ' + await page.evaluate(() => [...document.querySelectorAll('#admBody [data-ud-tab],#admBody [data-user-tab],#admBody .hub-tabs .chip')].map(e => e.textContent.trim()).join(' | ')));
    cur.notes.push('user detail full text: ' + (await bodyText(page)).slice(0, 1500).replace(/\n/g, ' / '));
    cur.notes.push('U4 list element present=' + await page.evaluate(() => !!document.querySelector('[data-us-registrations],[data-user-registrations],[data-ureg]')) + ' | U5 element=' + await page.evaluate(() => !!document.querySelector('[data-us-notifications],[data-user-notifications],[data-unotif]')) + ' | api calls made: see failed/requests');
    await probeButtons(page, 'user-detail', 20);
    begin('09b-user-404');
    await setState(page, { sec: 'users', uV: 'user', uSel: '00000000-0000-4000-8000-000000000000' });
    await shot(page, '09-user-404');
    cur.notes.push('404 text: ' + (await bodyText(page)).slice(0, 300).replace(/\n/g, ' / '));

    // 10. attendance, cert, club
    for (const [v, tag] of [['att', '10-attendance'], ['cert', '10-cert'], ['club', '10-club']]) {
      begin(tag);
      await setState(page, { sec: 'users', uV: v, uHub: 'users' });
      await shot(page, tag);
      if (v === 'att') { const f = page.locator('[data-at-form]').first(); if (await f.count()) { await f.click(); await settle(page, 1500); await shot(page, '10-attendance-people'); await shot(page, '10-attendance-people', MOBILE); } }
      await probeButtons(page, tag, 15);
    }

    // 11. shared inbox
    begin('11-inbox');
    await setState(page, { sec: 'users', uV: 'shared-inbox', uHub: 'users', sharedWorkflowKind: 'all' });
    await shot(page, '11-inbox');
    await shot(page, '11-inbox', MOBILE);
    cur.notes.push('inbox kinds: ' + await page.evaluate(() => [...document.querySelectorAll('[data-wf-kind],[data-shared-kind]')].map(e => e.textContent.trim()).join(' | ')));
    const openTask = page.locator('[data-wf-open],[data-task-open],[data-rcopen]').first();
    if (await openTask.count()) { await openTask.click(); await settle(page, 1500); await shot(page, '11-inbox-task'); cur.notes.push('task detail text: ' + (await bodyText(page)).slice(0, 300).replace(/\n/g, ' / ')); }
    await probeButtons(page, 'inbox', 15);

    // 12. tools
    for (const tool of ['report', 'staff', 'inbox', 'log', 'perms', 'tags', 'blocked', 'par', 'add', 'imp']) {
      begin('12-tools-' + tool);
      await setState(page, { sec: 'users', uV: 'tools', uHub: 'users', uTool: tool });
      const m = await shot(page, '12-tools-' + tool);
      cur.notes.push(`tool ${tool}: apiUnavailable=${m.apiUnavailable} head="${m.head}"`);
      if (tool === 'staff' || tool === 'report') { await shot(page, '12-tools-' + tool, MOBILE); await probeButtons(page, 'tools-' + tool, 15); }
    }
    begin('12-reports-hub');
    await setState(page, { sec: 'users', uHub: 'reports', uV: '' });
    await shot(page, '12-reports-hub');
    await shot(page, '12-reports-hub', MOBILE);
    await probeButtons(page, 'reports-hub', 15);

    // 13. forms
    begin('13-forms');
    await setState(page, { sec: 'forms' });
    await shot(page, '13-forms');
    await shot(page, '13-forms', MOBILE);
    await probeButtons(page, 'forms', 15);

    // 14. settings groups
    for (const g of ['services', 'deploy', 'data', 'security', 'publishing', 'performance']) {
      begin('14-settings-' + g);
      await setState(page, { sec: 'settings', setG: g });
      await shot(page, '14-settings-' + g);
      if (g === 'services' || g === 'publishing') await shot(page, '14-settings-' + g, MOBILE);
      await probeButtons(page, 'settings-' + g, 20);
    }
    begin('14-settings-people');
    await setState(page, { sec: 'settings', setG: 'publishing' });
    cur.notes.push('people/teachers editor present: ' + await page.evaluate(() => /استاد|مدرس|دست‌اندرکار/.test(document.querySelector('#admBody').innerText)) + ' | partner editor present: ' + await page.evaluate(() => !!document.querySelector('[data-ppartner]')));
    cur.notes.push('publishing text: ' + (await bodyText(page)).slice(0, 500).replace(/\n/g, ' / '));

    // 15. cert section + newev
    begin('15-cert-newev');
    await setState(page, { sec: 'cert' });
    await shot(page, '15-cert');
    await setState(page, { sec: 'newev' });
    await shot(page, '15-newev');
    for (const sec of ['reports', 'money', 'club']) { await setState(page, { sec }); cur.notes.push(`sec=${sec}: ` + (await bodyText(page)).slice(0, 160).replace(/\n/g, ' / ')); }

    // 16. offline + 401
    begin('16-offline');
    await setState(page, { sec: 'events' });
    await ctx.setOffline(true);
    await click(page, '[data-ct-refresh]', 1500);
    cur.notes.push('offline refresh → ' + (await bodyText(page)).slice(0, 300).replace(/\n/g, ' / '));
    await shot(page, '16-offline');
    await ctx.setOffline(false);
    begin('17-session-lost');
    const cookies = await ctx.cookies();
    await ctx.clearCookies();
    await click(page, '[data-ct-refresh]', 1500);
    cur.notes.push('no-cookie refresh → ' + (await bodyText(page)).slice(0, 300).replace(/\n/g, ' / '));
    await shot(page, '17-session-lost');
    await page.reload({ waitUntil: 'domcontentloaded' }); await settle(page, 1500);
    cur.notes.push('reload without session → url=' + page.url() + ' text=' + (await page.evaluate(() => document.body.innerText.slice(0, 200))).replace(/\n/g, ' / '));
    await shot(page, '17-session-lost-reload');
    await ctx.addCookies(cookies);

    // 18. logout
    begin('18-logout');
    await page.goto(`${BASE}/admin.html`, { waitUntil: 'domcontentloaded' }); await settle(page, 1500);
    const lo = page.locator('[data-server-logout]').first();
    cur.notes.push('logout button present: ' + (await lo.count()));
    if (await lo.count()) { await lo.click(); await settle(page, 2000); cur.notes.push('after logout url=' + page.url()); }
    await shot(page, '18-after-logout');
    const me2 = await page.evaluate(() => fetch('/api/auth/me', { credentials: 'include' }).then(r => r.status));
    cur.notes.push('auth/me after logout status=' + me2);
    await page.goto(`${BASE}/admin.html`, { waitUntil: 'domcontentloaded' }); await settle(page, 1500);
    cur.notes.push('admin.html after logout → url=' + page.url() + ' text=' + (await page.evaluate(() => document.body.innerText.slice(0, 160))).replace(/\n/g, ' / '));
  } catch (e) {
    (cur || begin('fatal')).notes.push('FATAL: ' + (e.stack || e.message));
  } finally {
    fs.writeFileSync(path.join(OUT, 'audit.json'), JSON.stringify({ base: BASE, at: new Date().toISOString(), steps }, null, 1));
    await browser.close();
    const summary = steps.map(s => `${s.name}: console=${s.console.length} pageErr=${s.pageErrors.length} failed=${s.failed.length} probes=${s.probe ? s.probe.tested + '/' + s.probe.noEffect : '-'} overflow=${s.shots.filter(x => x.overflowX).map(x => x.file).join(',') || 'none'}`);
    console.log(summary.join('\n'));
  }
})();
