/* Owner decision 1405/08/01 (B19) — browser evidence for event reminders against the local preview
   (TEST DB only; synthetic accounts from tools/phase9-preview-seed.py; nothing leaves the process).
   Flow (desktop 1280×800 then mobile 390×844):
   1. owner opens the seeded upcoming event: reminder switches default OFF, server read-model says «خاموش»;
   2. switches both on → save → reopen: «زمان‌بندی‌شده» + Jalali fire time from the server;
   3. a «soon» event (starts in ~20 h, both slots) + its registration form are created through the API;
      member A registers there (accepted), member B registers only on the far event;
   4. owner runs the scheduler from the panel card (confirm dialog) → exactly one reminder queued (member A);
      a second run queues nothing; outbox filter «یادآوری رویداد» shows the row «در صف»;
   5. editor read-model shows queued 1 for the 24 h slot;
   6. start time moves → run again → the pending row is withdrawn («باطل‌شده», no retry button);
   7. member A sees the in-app notification in account.html; member B has none; member/guest get 403/401 on the outbox.
   Usage:
     NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<deps> NORA_QA_ORIGIN=http://127.0.0.1:8000 \
     NORA_QA_BALE_BOT_TOKEN=<test-only token> node tools/panel-b19-reminders-evidence.cjs <out dir> */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { launchBrowser } = require('./browser-launch.cjs');
const ORIGIN = process.env.NORA_QA_ORIGIN || 'http://127.0.0.1:8000';
const OUT = process.argv[2] || path.join(process.cwd(), 'b19-shots');
const BOT_TOKEN = process.env.NORA_QA_BALE_BOT_TOKEN || 'test-only-bale-token';
const creds = fs.readFileSync(path.join(__dirname, '..', 'PREVIEW-LOGIN.local.md'), 'utf8');
const pick = re => (creds.match(re) || [])[1];
const OWNER = { user: pick(/مالک: `([^`]+)`/), pass: pick(/مالک: `[^`]+` \/ `([^`]+)`/) };
const MANAGER = { user: pick(/مدیر: `([^`]+)`/), pass: pick(/مدیر: `[^`]+` \/ `([^`]+)`/) };
if (!OWNER.pass || !MANAGER.pass) throw new Error('credentials file not parsed');
const FAR_EV = pick(/upcoming=(ev-[0-9a-f]+)/);
const MEMBER_A = Number(pick(/buyer=(\d+)/)), MEMBER_B = Number(pick(/pending=(\d+)/));
if (!FAR_EV || !MEMBER_A || !MEMBER_B) throw new Error('seed identifiers missing — run tools/phase9-preview-seed.py');
fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = [];
const RUN = crypto.randomBytes(3).toString('hex');
const results = { run: RUN, checks: [] };
const flush = () => { fs.writeFileSync(path.join(OUT, 'browser-checks.txt'), log.join('\n') + '\n'); fs.writeFileSync(path.join(OUT, 'stage-reminders-results.json'), JSON.stringify(results, null, 2)); };
const expect = (name, cond, note, dbg) => { log.push(`${cond ? '✓' : '✗'} ${name}: ${note}${!cond && dbg ? ' | ' + JSON.stringify(dbg).slice(0, 700) : ''}`); results.checks.push({ name, ok: !!cond, note }); flush(); };
const record = (name, note) => { log.push(`• ${name}: ${note}`); flush(); };

function initData(userId) {
  const fields = { auth_date: String(Math.floor(Date.now() / 1000)), query_id: 'b19-' + userId + '-' + RUN, user: JSON.stringify({ id: userId, first_name: 'آزمایش' }) };
  const check = Object.keys(fields).sort().map(k => `${k}=${fields[k]}`).join('\n');
  const secret = crypto.createHmac('sha256', 'WebAppData').update(BOT_TOKEN).digest();
  const hash = crypto.createHmac('sha256', secret).update(check).digest('hex');
  return new URLSearchParams({ ...fields, hash }).toString();
}
async function launchWithRetry() { let last; for (let i = 0; i < 4; i++) { try { return await launchBrowser(); } catch (e) { last = e; await sleep(1500); } } throw last; }
async function memberLogin(page, userId) {
  await page.goto(ORIGIN + '/events.html', { waitUntil: 'load', timeout: 60000 });
  const status = await page.evaluate(async data => (await fetch('/api/auth/bale-mini-app', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ init_data: data }), credentials: 'same-origin' })).status, initData(userId));
  if (status !== 200) throw new Error('member login failed ' + status);
}
async function staffLogin(page, who) {
  await page.goto(ORIGIN + '/login.html?mode=staff&next=admin.html%23dash', { waitUntil: 'load', timeout: 60000 });
  await page.evaluate(() => { try { localStorage.removeItem('nora-admin'); } catch (e) { /* ignore */ } });
  await page.waitForSelector('#lgStaffUsername', { timeout: 30000 });
  await page.fill('#lgStaffUsername', who.user);
  await page.fill('#lgStaffPassword', who.pass);
  await page.click('#lgStaffSubmit');
  await sleep(3000);
  const go = await page.$('text=رفتن به پنل مدیریت');
  if (go) { await page.evaluate(el => el.click(), go); await sleep(3000); }
  if (!/admin\.html/.test(page.url())) throw new Error('staff login did not reach the panel: ' + page.url());
  await page.waitForLoadState('load'); await sleep(800);
}
const snap = async (page, name) => page.screenshot({ path: path.join(OUT, name + '.png'), fullPage: false });
async function api(page, method, url, body) {
  return page.evaluate(async ({ method, url, body }) => {
    const token = document.cookie.split(';').map(s => s.trim()).find(s => s.startsWith('nora_csrf='))?.slice(10) || '';
    const r = await fetch(url, { method, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token, 'Idempotency-Key': 'b19-' + Math.random().toString(36).slice(2) + Date.now() }, body: body === undefined ? undefined : JSON.stringify(body), credentials: 'same-origin' });
    let json = null; try { json = await r.json(); } catch (e) { /* no body */ }
    return { status: r.status, json };
  }, { method, url, body });
}
async function openEventsList(page) {
  await page.goto('about:blank'); await page.goto(ORIGIN + '/admin.html#events', { waitUntil: 'load', timeout: 60000 }); await sleep(2500);
  await page.evaluate(() => { const b = document.querySelector('#admNav [data-sec="events"]'); if (b) b.click(); }); await sleep(1500);
}
async function openEditor(page, id) {
  await openEventsList(page);
  for (let i = 0; i < 20; i++) { if (await page.$(`[data-ct-edit="${id}"]`)) break; await sleep(500); }
  const ok = await page.evaluate(id => { const b = document.querySelector(`[data-ct-edit="${id}"]`); if (b) { b.click(); return true; } return false; }, id);
  if (!ok) throw new Error('editor button missing for ' + id);
  await page.waitForSelector('[data-ct-reminders]', { timeout: 20000 }); await sleep(800);
  return page.evaluate(() => ({
    h24: !!document.querySelector('[data-ct-check="remH24"]')?.checked, h1: !!document.querySelector('[data-ct-check="remH1"]')?.checked,
    slots: [...document.querySelectorAll('[data-ct-rem-slot]')].map(el => el.textContent.replace(/\s+/g, ' ').trim()),
    box: (document.querySelector('[data-ct-rem-state]')?.textContent || '').replace(/\s+/g, ' ').trim(),
  }));
}
async function openReports(page) {
  await page.goto('about:blank'); await page.goto(ORIGIN + '/admin.html#reports', { waitUntil: 'load', timeout: 60000 }); await sleep(2500);
  await page.evaluate(() => { const b = document.querySelector('#admNav [data-sec="reports"]'); if (b) b.click(); }); await sleep(3000);
}
const scrollTo = async (page, sel) => { await page.evaluate(sel => { const el = document.querySelector(sel); if (el) el.scrollIntoView({ block: 'center' }); }, sel); await sleep(400); };

(async () => {
  const browser = await launchWithRetry();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: 'reduce' });
  const page = await ctx.newPage();
  page.on('dialog', d => d.accept());
  let soonEv = '', soonForm = '', version = 0;
  try {
    /* ── 1. owner: defaults in the editor ── */
    await staffLogin(page, OWNER);
    /* re-runnable against the same preview DB: start from the default (both off) */
    const before = await api(page, 'GET', `/api/admin/content/events/${FAR_EV}`);
    if (before.json && before.json.record && before.json.record.reminders && (before.json.record.reminders.h24 || before.json.record.reminders.h1)) {
      await api(page, 'PUT', `/api/admin/content/events/${FAR_EV}`, { record: { reminders: { h24: false, h1: false } }, expected_version: before.json.version });
    }
    const d0 = await openEditor(page, FAR_EV);
    await scrollTo(page, '[data-ct-reminders]');
    await snap(page, 'REM-01-d-editor-default-off');
    expect('d editor default off', !d0.h24 && !d0.h1 && d0.slots.length === 2 && d0.slots.every(t => /خاموش/.test(t)) && /پیامک ندارد/.test(d0.box),
      `switches unchecked; server read-model: ${d0.slots.join(' | ')}`, d0);

    /* ── 2. switch both on, save, reopen ── */
    await page.evaluate(() => { document.querySelector('[data-ct-check="remH24"]').click(); });
    await sleep(300);
    await page.evaluate(() => { document.querySelector('[data-ct-check="remH1"]').click(); });
    await sleep(300);
    await page.evaluate(() => document.querySelector('[data-ct-save]').click());
    for (let i = 0; i < 30; i++) { if (await page.$(`[data-ct-edit="${FAR_EV}"]`)) break; await sleep(500); }
    const saved = await api(page, 'GET', `/api/admin/content/events/${FAR_EV}`);
    version = saved.json && saved.json.version;
    const d1 = await openEditor(page, FAR_EV);
    await scrollTo(page, '[data-ct-reminders]');
    await snap(page, 'REM-02-d-editor-both-on-scheduled');
    expect('d save + reopen', saved.status === 200 && saved.json.record.reminders.h24 === true && saved.json.record.reminders.h1 === true && d1.h24 && d1.h1 && d1.slots.every(t => /زمان‌بندی‌شده/.test(t) && /زمان ارسال: 1405\//.test(t)),
      `GET detail: reminders=${JSON.stringify(saved.json && saved.json.record.reminders)}; editor: ${d1.slots.join(' | ')}`, { saved: saved.json && saved.json.reminders, d1 });
    await page.evaluate(() => document.querySelector('[data-ct-cancel]')?.click());

    /* ── 3. «soon» event + form through the API (owner session, CSRF) ── */
    const startsAt = new Date(Date.now() + 20 * 3600 * 1000).toISOString().replace(/\.\d{3}Z$/, '+00:00');
    const created = await api(page, 'POST', '/api/admin/content/events', { record: { t: `کارگاه فردا (آزمون یادآور ${RUN})`, kind: 'کارگاه', d: 'رویداد آزمایشی برای یادآور ۲۴ ساعت قبل.', on: '۱۴۰۵/۰۸/۰۲', time: '۱۰ تا ۱۲', place: 'سالن آزمایشی', mode: 'حضوری', startsAt, reminders: { h24: true, h1: true } }, expected_version: version, status: 'published' });
    soonEv = created.json && created.json.record && created.json.record.id; version = created.json && created.json.version;
    const form = await api(page, 'POST', '/api/forms', { name: `فرم ثبت‌نام یادآور ${RUN}`, model: 'registration', need: 'reg', ev: soonEv, settings: {}, fields: [{ id: 'full-name', t: 'fullname', l: 'نام کامل', required: true }] });
    soonForm = form.json && form.json.id;
    const published = soonForm ? await api(page, 'POST', `/api/forms/${soonForm}/publish`, { expected_version: 1 }) : { status: 0 };
    expect('d soon event + form', created.status === 200 && !!soonEv && form.status === 201 && published.status === 200 && created.json.reminders.slots[0].state === 'due',
      `event ${soonEv} starts in 20 h (24 h slot already «due», 1 h slot «scheduled»); registration form ${soonForm} published`, { created: created.status, form: form.status, published: published.status, slots: created.json && created.json.reminders && created.json.reminders.slots.map(s => s.state) });

    /* member A → soon event (accepted); member B → far event only */
    await ctx.clearCookies();
    await memberLogin(page, MEMBER_A);
    const draftA = await api(page, 'GET', `/api/public/forms/${soonForm}/draft`);
    const regA = await api(page, 'POST', `/api/public/forms/${soonForm}/responses`, { answers: { 'full-name': 'عضو آزمایشی الف' } });
    await ctx.clearCookies();
    await memberLogin(page, MEMBER_B);
    const farForm = saved.json && saved.json.record && saved.json.record.registration && saved.json.record.registration.form_id; // A6 summary of the far event (owner detail fetched above)
    let regB = { status: 0, json: null };
    if (farForm) { await api(page, 'GET', `/api/public/forms/${farForm}/draft`); regB = await api(page, 'POST', `/api/public/forms/${farForm}/responses`, { answers: { 'full-name': 'عضو آزمایشی ب' } }); }
    expect('registrations', draftA.status === 200 && regA.status === 200 && regA.json.status === 'accepted', `member A accepted on the soon event (status=${regA.json && regA.json.status}); member B on the far event only (${regB.status || 'no public form id exposed — B simply has no registration on the soon event'})`, { regA: regA.json, farForm });

    /* ── 4. owner runs the scheduler from the panel card ── */
    await ctx.clearCookies();
    await staffLogin(page, OWNER);
    await openReports(page);
    await page.waitForSelector('[data-server-sched-run-now]', { timeout: 30000 });
    await page.evaluate(() => document.querySelector('[data-server-sched-run-now]').click());
    await sleep(3500);
    const sched1 = await page.evaluate(() => ({ manual: document.querySelector('[data-server-sched-manual]')?.textContent.replace(/\s+/g, ' ') || '', run: document.querySelector('[data-server-sched-reminders]')?.textContent.replace(/\s+/g, ' ') || '' }));
    await scrollTo(page, '[data-server-sched]');
    await snap(page, 'REM-03-d-scheduler-run-queued-1');
    const state1 = await api(page, 'GET', '/api/admin/scheduled-publish');
    const r1 = state1.json && state1.json.last_run && state1.json.last_run.reminders;
    expect('d scheduler run queued 1', !!r1 && r1.queued === 1 && r1.ok === true && /صف‌شده ۱/.test(sched1.manual + sched1.run),
      `manual run from the panel → reminders ${JSON.stringify(r1)}; card: «${sched1.manual}»`, { sched1, r1 });
    /* second run: idempotent */
    await page.evaluate(() => document.querySelector('[data-server-sched-run-now]').click());
    await sleep(3500);
    const state2 = await api(page, 'GET', '/api/admin/scheduled-publish');
    const r2 = state2.json && state2.json.last_run && state2.json.last_run.reminders;
    expect('d second run idempotent', !!r2 && r2.queued === 0 && r2.existing === 1, `re-run → queued ${r2 && r2.queued}, existing ${r2 && r2.existing} (dedupe key per event/slot/start/account)`, r2);

    /* outbox: kind filter */
    await page.evaluate(() => document.querySelector('[data-server-outbox-kind="event_reminder"]')?.click());
    await sleep(2500);
    const outbox1 = await page.evaluate(() => [...document.querySelectorAll('[data-server-outbox-row]')].map(el => ({ state: el.dataset.serverOutboxStateRow, text: el.textContent.replace(/\s+/g, ' ').trim().slice(0, 200), retry: !!el.querySelector('[data-server-outbox-retry]') })));
    await scrollTo(page, '[data-server-outbox]');
    await snap(page, 'REM-04-d-outbox-kind-filter-queued');
    const apiOutbox = await api(page, 'GET', '/api/admin/notifications?kind=event_reminder&limit=50');
    const mine = (apiOutbox.json && apiOutbox.json.items || []).filter(it => /آزمون یادآور/.test(it.title || '') && new RegExp(RUN).test(it.title || ''));
    expect('d outbox queued row', outbox1.length >= 1 && outbox1.some(r => r.state === 'queued' && /یادآوری رویداد/.test(r.text)) && mine.length === 1 && mine[0].delivery_status === 'pending' && !('bale_user_id' in mine[0]),
      `outbox filtered by kind=event_reminder shows the queued reminder («یادآوری رویداد», «در صف»); API row pending, raw Bale id not exposed`, { outbox1, mine: mine.map(m => ({ s: m.delivery_status, k: m.kind })) });

    /* ── 5. editor read-model: queued 1 ── */
    const d2 = await openEditor(page, soonEv);
    await scrollTo(page, '[data-ct-reminders]');
    await snap(page, 'REM-05-d-editor-queued-counter');
    expect('d editor queued counter', /در صف\/ارسال‌شده: ۱/.test(d2.slots[0]) && /در انتظار ۱/.test(d2.slots[0]) && /زمان‌بندی‌شده/.test(d2.slots[1]),
      `24 h slot: «${d2.slots[0]}»; 1 h slot: «${d2.slots[1]}»`, d2);
    await page.evaluate(() => document.querySelector('[data-ct-cancel]')?.click());

    /* ── 6. start time moves → pending reminder withdrawn ── */
    const detail = await api(page, 'GET', `/api/admin/content/events/${soonEv}`);
    const moved = await api(page, 'PUT', `/api/admin/content/events/${soonEv}`, { record: { startsAt: new Date(Date.now() + 5 * 86400 * 1000).toISOString().replace(/\.\d{3}Z$/, '+00:00') }, expected_version: detail.json.version });
    const run3 = await api(page, 'POST', '/api/admin/scheduled-publish/run', {});
    const r3 = run3.json && run3.json.reminders;
    await openReports(page); await sleep(500);
    await page.evaluate(() => document.querySelector('[data-server-outbox-kind="event_reminder"]')?.click());
    await sleep(2500);
    const outbox2 = await page.evaluate(() => [...document.querySelectorAll('[data-server-outbox-row]')].map(el => ({ state: el.dataset.serverOutboxStateRow, text: el.textContent.replace(/\s+/g, ' ').trim().slice(0, 220), retry: !!el.querySelector('[data-server-outbox-retry]') })));
    await scrollTo(page, '[data-server-outbox]');
    await snap(page, 'REM-06-d-outbox-superseded-after-time-change');
    const stale = outbox2.find(r => /باطل‌شده/.test(r.text));
    const retryStale = mine[0] ? await api(page, 'POST', `/api/admin/notifications/${mine[0].id}/retry`, {}) : { status: 0 };
    expect('d time change withdraws', moved.status === 200 && !!r3 && r3.withdrawn === 1 && r3.queued === 0 && !!stale && !stale.retry && retryStale.status === 409 && retryStale.json.detail.code === 'reminder_superseded',
      `PUT startsAt (+5 d) → run: withdrawn ${r3 && r3.withdrawn}, queued ${r3 && r3.queued}; outbox row «باطل‌شده (تغییر زمان/لغو)» without retry; manual retry → 409 reminder_superseded`, { moved: moved.status, r3, stale, retryStale: retryStale.status });
    const d3 = await openEditor(page, soonEv);
    expect('d editor after move', /زمان‌بندی‌شده/.test(d3.slots[0]) && /باطل‌شده پس از تغییر زمان\/لغو: ۱/.test(d3.slots[0]), `24 h slot after the move: «${d3.slots[0]}»`, d3);
    await page.evaluate(() => document.querySelector('[data-ct-cancel]')?.click());

    /* ── 7. member A in-app; member B nothing; member/guest outbox authz ── */
    await ctx.clearCookies();
    await memberLogin(page, MEMBER_A);
    await page.goto(ORIGIN + '/account.html', { waitUntil: 'load', timeout: 60000 }); await sleep(2500);
    await page.evaluate(() => document.querySelector('[data-server-data-open="notifications"]')?.click()); await sleep(2500);
    const inApp = await api(page, 'GET', '/api/account/notifications?limit=50&offset=0');
    const myRem = (inApp.json && inApp.json.items || []).filter(it => it.kind === 'event_reminder' && new RegExp(RUN).test(it.title || ''));
    const pageHas = await page.evaluate(run => new RegExp('یادآوری رویداد').test(document.body.innerText) && new RegExp(run).test(document.body.innerText), RUN);
    await snap(page, 'REM-07-d-member-in-app-notification');
    const memberOutbox = await api(page, 'GET', '/api/admin/notifications?kind=event_reminder');
    expect('d member A in-app', myRem.length === 1 && /فردا/.test(myRem[0].body) && /سالن آزمایشی/.test(myRem[0].body) && /دیگر معتبر نیست/.test(myRem[0].body) && pageHas && memberOutbox.status === 403,
      `account notifications: exactly 1 reminder row (title «${myRem[0] && myRem[0].title}»; original text with «فردا» + place + start time kept, now headed «دیگر معتبر نیست» because the start moved; link ${myRem[0] && myRem[0].link}); shown in account.html; member → outbox 403`, { myRem, pageHas, memberOutbox: memberOutbox.status });
    record('note', 'the withdrawn reminder is the same in-app row (nothing deleted); its Bale delivery is cancelled and the member reads the superseded head instead of a stale promise');
    await ctx.clearCookies();
    await memberLogin(page, MEMBER_B);
    const inAppB = await api(page, 'GET', '/api/account/notifications?limit=50&offset=0');
    const bRem = (inAppB.json && inAppB.json.items || []).filter(it => it.kind === 'event_reminder' && new RegExp(RUN).test(it.title || ''));
    await ctx.clearCookies();
    const guest = await (async () => { await page.goto(ORIGIN + '/events.html', { waitUntil: 'load', timeout: 60000 }); return api(page, 'GET', '/api/admin/notifications?kind=event_reminder'); })();
    expect('member B + guest', bRem.length === 0 && guest.status === 401, `member B (not registered on the soon event) has no reminder; guest → outbox 401`, { bRem: bRem.length, guest: guest.status });

    /* manager: outbox + editor read-only visibility per existing permissions */
    await staffLogin(page, MANAGER);
    const mgrOutbox = await api(page, 'GET', '/api/admin/notifications?kind=event_reminder&limit=5');
    const mgrSched = await api(page, 'GET', '/api/admin/scheduled-publish');
    record('manager', `GET outbox → ${mgrOutbox.status}, GET scheduled-publish → ${mgrSched.status} (both follow the existing rp_view permission of this seeded manager; no new permission was added)`);

    /* ── mobile 390×844: editor + outbox ── */
    await ctx.clearCookies();
    await page.setViewportSize({ width: 390, height: 844 });
    await staffLogin(page, OWNER);
    const m1 = await openEditor(page, soonEv);
    await scrollTo(page, '[data-ct-reminders]');
    await snap(page, 'REM-08-m-editor-reminders');
    expect('m editor', m1.h24 && m1.h1 && m1.slots.length === 2, `mobile editor shows both switches on and the two server states`, m1);
    await page.evaluate(() => document.querySelector('[data-ct-cancel]')?.click());
    await openReports(page);
    await page.evaluate(() => document.querySelector('[data-server-outbox-kind="event_reminder"]')?.click());
    await sleep(2500);
    const mOut = await page.evaluate(() => document.querySelectorAll('[data-server-outbox-row]').length);
    await scrollTo(page, '[data-server-outbox]');
    await snap(page, 'REM-09-m-outbox-reminders');
    expect('m outbox', mOut >= 1, `mobile outbox with kind filter shows ${mOut} reminder row(s)`, { mOut });
  } catch (error) {
    log.push('✗ fatal: ' + (error && error.stack || error));
    results.fatal = String(error && error.message || error);
    try { await snap(page, 'REM-fatal'); } catch (e) { /* ignore */ }
  } finally {
    results.soon_event = soonEv; results.form = soonForm;
    flush();
    await browser.close();
  }
})();
