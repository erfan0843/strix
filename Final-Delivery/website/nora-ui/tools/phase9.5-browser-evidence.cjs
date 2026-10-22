/* Phase-9.5 browser evidence against the local preview (TEST DB only; synthetic accounts seeded by
   tools/phase9-preview-seed.py + tools/phase9.3-preview-seed.py). Real browser + real HTTP for the
   9.5 items that unit tests cannot prove on their own:
   (1) scheduled publish end-to-end: the owner schedules a resource (publish_at = now+~45 s) through the
       panel's own API client → the holder does NOT see it before the time → the «زمان‌بند انتشار» card
       shows it as «future» → once due, the manual run from the panel announces it ONCE (a second run
       announces 0) → the holder sees the resource and ONE in-app notification;
   (2) outbox retry: a row put into the bot's final-failure state (synthetic injection on the test DB,
       see browser-checks.txt) shows the «تلاش دوبارهٔ ارسال» button only for ev_publish staff; clicking it
       re-queues the SAME row (attempts reset, no new row, no «تحویل» claim);
   (3) account «رویدادهای من»: a member who registers for the upcoming event sees the shared countdown
       (countdown.js/css now included in account.html) driven by event_schedule from the server;
   (4) authz over HTTP: scheduler monitor/run and retry are 401 for guests and 403 for members.

   Usage (test server + test DB only; nothing is printed from the env):
     NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<node deps dir> NORA_QA_ORIGIN=http://127.0.0.1:8000 \
     NORA_QA_BALE_BOT_TOKEN=<test-only bot token> NORA_QA_FAILED_NOTIFICATION=<uuid> node tools/phase9.5-browser-evidence.cjs <output dir> */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { launchBrowser } = require('./browser-launch.cjs');
const ORIGIN = process.env.NORA_QA_ORIGIN || 'http://127.0.0.1:8000';
const OUT = process.argv[2] || path.join(process.cwd(), 'phase9.5-shots');
const BOT_TOKEN = process.env.NORA_QA_BALE_BOT_TOKEN || 'test-only-bale-token';
const FAILED_ID = process.env.NORA_QA_FAILED_NOTIFICATION || '';
const creds = fs.readFileSync(path.join(__dirname, '..', 'PREVIEW-LOGIN.local.md'), 'utf8');
const pick = re => (creds.match(re) || [])[1];
const OWNER = { user: pick(/مالک: `([^`]+)`/), pass: pick(/مالک: `[^`]+` \/ `([^`]+)`/) };
const MANAGER = { user: pick(/مدیر: `([^`]+)`/), pass: pick(/مدیر: `[^`]+` \/ `([^`]+)`/) };
if (!OWNER.pass || !MANAGER.pass) throw new Error('credentials file not parsed');
const HELD = pick(/held93=(ev-[0-9a-f]+)/), UPCOMING = pick(/upcoming=(ev-[0-9a-f]+)/);
const ATTENDEE = Number(pick(/attendee=(\d+)/)), ABSENT = Number(pick(/absent=(\d+)/));
if (!HELD || !UPCOMING || !ATTENDEE || !ABSENT) throw new Error('phase 9.3 seed identifiers missing — run tools/phase9.3-preview-seed.py');
fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = [];
const RUN = crypto.randomBytes(3).toString('hex');
const SCHEDULE_MS = 45000;

function initData(userId) {
  const fields = { auth_date: String(Math.floor(Date.now() / 1000)), query_id: 'preview-' + userId + '-' + RUN, user: JSON.stringify({ id: userId, first_name: 'آزمایش' }) };
  const check = Object.keys(fields).sort().map(k => `${k}=${fields[k]}`).join('\n');
  const secret = crypto.createHmac('sha256', 'WebAppData').update(BOT_TOKEN).digest();
  const hash = crypto.createHmac('sha256', secret).update(check).digest('hex');
  return new URLSearchParams({ ...fields, hash }).toString();
}
async function launchWithRetry() {
  let last;
  for (let i = 0; i < 4; i++) { try { return await launchBrowser(); } catch (e) { last = e; await sleep(1500); } }
  throw last;
}
async function context(mobile) {
  const browser = await launchWithRetry();
  const ctx = await browser.newContext(mobile ? { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, reducedMotion: 'reduce' }
    : { viewport: { width: 1280, height: 800 }, reducedMotion: 'reduce' });
  ctx.close = async () => { await browser.close(); };
  return ctx;
}
async function memberLogin(page, userId) {
  await page.goto(ORIGIN + '/events.html', { waitUntil: 'load', timeout: 60000 });
  const status = await page.evaluate(async data => {
    const r = await fetch('/api/auth/bale-mini-app', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ init_data: data }), credentials: 'same-origin' });
    return r.status;
  }, initData(userId));
  if (status !== 200) throw new Error('member login failed ' + status);
}
async function staffLogin(page, who) {
  await page.goto(ORIGIN + '/login.html?mode=staff&next=admin.html%23dash', { waitUntil: 'load', timeout: 60000 });
  await page.waitForSelector('#lgStaffUsername', { timeout: 30000 });
  await page.fill('#lgStaffUsername', who.user);
  await page.fill('#lgStaffPassword', who.pass);
  await page.click('#lgStaffSubmit');
  await sleep(3000);
  const go = await page.$('text=رفتن به پنل مدیریت');
  if (go) { await page.evaluate(el => el.click(), go); await sleep(3000); }
  if (!/admin\.html/.test(page.url())) throw new Error('staff login did not reach the panel: ' + page.url());
}
const snap = async (page, name) => page.screenshot({ path: path.join(OUT, name + '.png'), fullPage: false });
const flush = () => fs.writeFileSync(path.join(OUT, 'browser-checks.txt'), log.join('\n') + '\n');
const expect = (name, cond, note, dbg) => { log.push(`${cond ? '✓' : '✗'} ${name}: ${note}${!cond && dbg ? ' | ' + JSON.stringify(dbg).slice(0, 700) : ''}`); flush(); };
const record = (name, note) => { log.push(`• ${name}: ${note}`); flush(); };
async function openReports(page) {
  await page.goto(ORIGIN + '/admin.html#users', { waitUntil: 'load', timeout: 60000 }); await page.reload({ waitUntil: 'load', timeout: 60000 }); await sleep(3500);
  await page.evaluate(() => { const b = document.querySelector('[data-user-hub="reports"]'); if (b) b.click(); });
  await sleep(5000);
}
const schedState = page => page.evaluate(() => {
  const card = document.querySelector('[data-server-sched]'); if (card) card.scrollIntoView({ block: 'start' });
  const line = sel => { const el = document.querySelector(sel); return el ? el.innerText.replace(/\s+/g, ' ') : ''; };
  return { present: !!card, state: card ? card.getAttribute('data-server-sched-state') : '', runButton: !!document.querySelector('[data-server-sched-run-now]'),
    text: card ? card.innerText.replace(/\s+/g, ' ').slice(0, 420) : '', lastRun: line('[data-server-sched-run]'), manual: line('[data-server-sched-manual]') };
});
const outboxState = page => page.evaluate(() => {
  const card = document.querySelector('[data-server-outbox]'); if (card) card.scrollIntoView({ block: 'start' });
  const rows = [...document.querySelectorAll('[data-server-outbox-row]')].map(r => ({ id: r.getAttribute('data-server-outbox-row'), state: r.getAttribute('data-server-outbox-state-row'), retry: !!r.querySelector('[data-server-outbox-retry]'), text: r.innerText.replace(/\s+/g, ' ').slice(0, 160) }));
  return { present: !!card, rows, notice: (card && card.querySelector('[role="status"]') ? card.querySelector('[role="status"]').innerText : '').replace(/\s+/g, ' ') };
});

(async () => {
  const title = `جزوهٔ زمان‌بندی‌شدهٔ ۹.۵ (${RUN})`;
  let resourceId = '', dueAt = 0;

  /* ── 0. authz over HTTP (guest + member) ── */
  {
    const ctx = await context(false); const page = await ctx.newPage();
    await page.goto(ORIGIN + '/events.html', { waitUntil: 'load', timeout: 60000 });
    const guest = await page.evaluate(async () => ({
      monitor: (await fetch('/api/admin/scheduled-publish')).status,
      run: (await fetch('/api/admin/scheduled-publish/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })).status,
      retry: (await fetch('/api/admin/notifications/00000000-0000-4000-8000-000000000001/retry', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })).status,
    }));
    await memberLogin(page, ATTENDEE);
    const member = await page.evaluate(async () => ({
      monitor: (await fetch('/api/admin/scheduled-publish')).status,
      run: (await fetch('/api/admin/scheduled-publish/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })).status,
      retry: (await fetch('/api/admin/notifications/00000000-0000-4000-8000-000000000001/retry', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })).status,
    }));
    expect('authz scheduler/retry', [guest.monitor, guest.run, guest.retry].every(s => s === 401) && [member.monitor, member.run, member.retry].every(s => s === 403),
      `guest → ${JSON.stringify(guest)}, signed-in member → ${JSON.stringify(member)} (server-side; no panel involved)`, { guest, member });
    await ctx.close();
  }

  /* ── 1. owner (desktop): schedule a resource through the panel API client, watch the monitor ── */
  let ownerCtx = await context(false); let owner = await ownerCtx.newPage(); await staffLogin(owner, OWNER);
  const scheduled = await owner.evaluate(async ({ ev, title, ms }) => {
    const api = window.NORA_SERVER_API;
    const rec = await api.getEventRecording(ev);
    const sessionId = rec && rec.recording && rec.recording.sessions && rec.recording.sessions[0] ? rec.recording.sessions[0].id : null;
    const created = await api.createEventResource(ev, { title, access: 'attended', session_id: sessionId, kind: 'link', link_url: 'https://example.org/phase95-notes' }, 'nora_csrf');
    const publishAt = new Date(Date.now() + ms).toISOString();
    const put = await api.updateEventResource(ev, created.id, { status: 'published', publish_at: publishAt }, 'nora_csrf');
    const monitor = await api.getScheduledPublish();
    return { id: created.id, status: put.status, publish_at: put.publish_at, announced_at: put.announced_at, pending: monitor.pending, last_run: monitor.last_run };
  }, { ev: HELD, title, ms: SCHEDULE_MS });
  resourceId = scheduled.id; dueAt = Date.parse(scheduled.publish_at);
  expect('owner schedules resource', !!resourceId && scheduled.status === 'published' && scheduled.pending.future >= 1 && !scheduled.announced_at,
    `resource ${resourceId.slice(0, 8)}… published with publish_at=${scheduled.publish_at}; monitor pending=${JSON.stringify(scheduled.pending)}; announced_at=${scheduled.announced_at}`, scheduled);
  await openReports(owner);
  const sched1 = await schedState(owner); await sleep(400);
  await snap(owner, 'd-01-owner-scheduler-future');
  expect('d scheduler card (future)', sched1.present && sched1.runButton && /زمان‌بندی‌شده برای آینده/.test(sched1.text), `state=${sched1.state} «${sched1.text.slice(0, 220)}»`, sched1);

  /* ── 2. holder: not visible before the time ── */
  let holderCtx = await context(false); let holder = await holderCtx.newPage(); await memberLogin(holder, ATTENDEE);
  const notesBefore = await holder.evaluate(async () => (await (await fetch('/api/account/notifications?limit=50&offset=0')).json()).items.length);
  await holder.goto(ORIGIN + `/event.html?id=${HELD}#recording-sessions`, { waitUntil: 'load', timeout: 60000 }); await sleep(4000);
  const before = await holder.evaluate(t => ({ visible: document.body.innerText.includes(t), api: null }), title);
  before.api = await holder.evaluate(async ({ ev, id }) => { const j = await (await fetch(`/api/public/events/${ev}/recording`)).json(); return j.recording.sessions.some(s => (s.resources || []).some(r => r.id === id)); }, { ev: HELD, id: resourceId });
  await holder.evaluate(() => { const el = document.querySelector('#recording-sessions'); if (el) el.scrollIntoView({ block: 'start' }); }); await sleep(400);
  await snap(holder, 'd-02-holder-before-due');
  expect('holder before due', !before.visible && before.api === false, `scheduled resource hidden on the event page and absent from /recording API before publish_at (server clock)`, before);

  /* ── 3. wait until due, manual run from the panel, idempotent second run ── */
  const wait = dueAt + 3000 - Date.now(); if (wait > 0) await sleep(wait);
  await openReports(owner);
  const stalled = await schedState(owner);
  await owner.evaluate(() => { const b = document.querySelector('[data-server-sched-run-now]'); if (b) b.click(); });
  await sleep(5000);
  const afterRun = await schedState(owner); await snap(owner, 'd-03-owner-manual-run');
  const second = await owner.evaluate(async () => { const api = window.NORA_SERVER_API; const run = await api.runScheduledPublish('nora_csrf'); const monitor = await api.getScheduledPublish(); return { run, pending: monitor.pending, actor: monitor.last_run && monitor.last_run.actor }; });
  expect('manual run announces once', /در موعد ولی اعلان‌نشده/.test(stalled.text) && stalled.state === 'stalled' && afterRun.state === 'ok' && /اعلان‌شده ۱/.test(afterRun.manual) && /اعلان‌های ساخته‌شده ۱/.test(afterRun.manual) && second.run.announced === 0 && second.pending.due_unannounced === 0,
    `before run: state=${stalled.state}; after run: state=${afterRun.state}; panel line «${afterRun.manual}» · «${afterRun.lastRun.slice(0, 200)}»; second run → announced=${second.run.announced}, due=${second.run.due}; last_run.actor=${second.actor}`, { stalled, afterRun, second });

  /* ── 4. holder sees it + exactly one notification ── */
  await holder.reload({ waitUntil: 'load', timeout: 60000 }); await sleep(4000);
  const after = await holder.evaluate(async ({ ev, id, t }) => { const j = await (await fetch(`/api/public/events/${ev}/recording`)).json(); const notes = (await (await fetch('/api/account/notifications?limit=50&offset=0')).json()).items; return { visible: document.body.innerText.includes(t), api: j.recording.sessions.some(s => (s.resources || []).some(r => r.id === id)), notes: notes.length, mine: notes.filter(n => n.kind === 'recording_content' && ((n.title || '') + ' ' + (n.body || '')).includes(t)).length, titles: notes.map(n => n.title) }; }, { ev: HELD, id: resourceId, t: title });
  await holder.evaluate(t => { const el = [...document.querySelectorAll('a,button,li,div')].find(x => x.children.length < 4 && x.innerText && x.innerText.includes(t)); if (el) el.scrollIntoView({ block: 'center' }); }, title); await sleep(400);
  await snap(holder, 'd-04-holder-after-due');
  await holder.goto(ORIGIN + '/account.html#notifications', { waitUntil: 'load', timeout: 60000 }); await sleep(4000);
  await snap(holder, 'd-05-holder-notification');
  expect('holder after due', after.visible && after.api && after.notes === notesBefore + 1 && after.mine >= 1,
    `resource visible after publish_at; notifications ${notesBefore} → ${after.notes} (exactly +1, recording_content for the scheduled resource); content became visible by server time, the run only announced`, { notesBefore, after });
  await holderCtx.close();

  /* ── 5. outbox retry (owner) ── */
  await openReports(owner);
  await owner.evaluate(() => { const c = document.querySelector('[data-server-outbox-state="failed"]'); if (c) c.click(); }); await sleep(3000);
  const failed = await outboxState(owner); await snap(owner, 'd-06-owner-outbox-failed');
  const target = failed.rows.find(r => r.id === FAILED_ID) || failed.rows.find(r => r.retry);
  expect('failed row offers retry', !!target && target.retry && target.state === 'failed' && failed.rows.filter(r => r.state !== 'failed').length === 0,
    `filter «ناموفق» → ${failed.rows.length} row(s); the injected final-failure row ${target ? target.id.slice(0, 8) : '?'}… shows the retry button (ev_publish); text «${target ? target.text : ''}»`, failed);
  if (target) {
    await owner.evaluate(id => { const b = document.querySelector(`[data-server-outbox-retry="${id}"]`); if (b) b.click(); }, target.id); await sleep(3500);
    const requeued = await outboxState(owner); await snap(owner, 'd-07-owner-outbox-requeued');
    const row = requeued.rows.find(r => r.id === target.id);
    const api = await owner.evaluate(async id => { const j = await (await fetch('/api/admin/notifications?limit=100')).json(); const r = j.items.find(x => x.id === id); return { total: j.items.length, state: r && r.delivery_state, attempts: r && r.delivery_attempts, error: r && r.last_delivery_error, counts: j.counts }; }, target.id);
    expect('retry re-queues the same row', !!row && row.state === 'queued' && !row.retry && /ردیف تازه‌ای ساخته نشد/.test(requeued.notice) && api.state === 'queued' && api.attempts === 0 && !api.error,
      `same row → state=${api.state}, attempts=${api.attempts}, last_error=${api.error}; outbox total=${api.total}; notice «${requeued.notice.slice(0, 160)}» (no delivery claim)`, { row, api, notice: requeued.notice });
    const again = await owner.evaluate(async id => { const r = await fetch(`/api/admin/notifications/${id}/retry`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': (document.cookie.match(/nora_csrf=([^;]+)/) || [])[1] || '' }, body: '{}' }); return { status: r.status, body: await r.json().catch(() => null) }; }, target.id);
    expect('second retry rejected', again.status === 409 && again.body && again.body.detail && again.body.detail.code === 'notification_not_failed', `POST retry on a queued row → ${again.status} ${JSON.stringify(again.body)}`, again);
  }
  await ownerCtx.close();

  /* ── 6. manager: same cards, buttons follow server permissions ── */
  {
    const ctx = await context(false); const page = await ctx.newPage(); await staffLogin(page, MANAGER);
    const perms = await page.evaluate(async () => (await (await fetch('/api/account/me')).json()).permissions || []);
    await openReports(page);
    const s = await schedState(page); await snap(page, 'd-08-manager-scheduler');
    const canPublish = perms.includes('ev_publish');
    expect('manager scheduler card', s.present && s.runButton === canPublish, `manager permissions include ev_publish=${canPublish}; run button shown=${s.runButton}; state=${s.state}`, { perms, s });
    await ctx.close();
  }

  /* ── 7. member registers for the upcoming event → account countdown (desktop + mobile) ── */
  const formId = await (async () => { const r = await fetch(ORIGIN + '/api/public/site-content'); const j = await r.json(); const ev = j.content.events.find(e => e.id === UPCOMING); return ev && ev.forms && ev.forms[0] ? ev.forms[0].id : ''; })().catch(() => '');
  for (const mobile of [false, true]) {
    const tag = mobile ? 'm' : 'd';
    const ctx = await context(mobile); const page = await ctx.newPage(); await memberLogin(page, ABSENT);
    const reg = await page.evaluate(async fid => {
      const mine = (await (await fetch('/api/account/registrations?limit=50&offset=0')).json()).items;
      if (mine.some(i => i.form_id === fid || (i.event_schedule && i.event_schedule.state !== 'ended'))) return { reused: true };
      const draft = await fetch(`/api/public/forms/${fid}/draft`);
      const post = await fetch(`/api/public/forms/${fid}/responses`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answers: { 'full-name': 'عضو آزمون ۹.۵' } }) });
      return { reused: false, draft: draft.status, post: post.status };
    }, formId);
    await page.goto(ORIGIN + '/account.html#events', { waitUntil: 'load', timeout: 60000 }); await sleep(4500);
    const cd = await page.evaluate(() => {
      const el = document.querySelector('[data-account-registration-countdown]'); if (el) el.scrollIntoView({ block: 'center' });
      const items = [...document.querySelectorAll('.server-registration')].map(c => ({ ev: c.getAttribute('data-account-registration-event'), countdown: !!c.querySelector('[data-countdown]'), lifecycle: c.querySelector('[data-account-registration-lifecycle]') ? c.querySelector('[data-account-registration-lifecycle]').getAttribute('data-account-registration-lifecycle') : '' }));
      return { loaded: !!window.NORA_COUNTDOWN, css: !!document.querySelector('link[href="countdown.css?v=2"]'), items, text: el ? el.innerText.replace(/\s+/g, ' ') : '' };
    });
    await sleep(400); await snap(page, `${tag}-09-member-account-countdown`);
    const upcomingRow = cd.items.find(i => i.ev === UPCOMING);
    expect(`${tag} account countdown`, cd.loaded && cd.css && !!upcomingRow && upcomingRow.countdown && /تا شروع رویداد/.test(cd.text) && cd.items.filter(i => i.ev === HELD).every(i => !i.countdown),
      `registration ${reg.reused ? 'already existed' : `created (draft ${reg.draft}, post ${reg.post})`}; account.html loads countdown.js/css; upcoming row has the shared countdown «${cd.text.slice(0, 80)}»; the held (ended) registration has none`, { reg, cd });
    await ctx.close();
  }

  log.push('', `ARTIFACTS: ${fs.readdirSync(OUT).filter(f => f.endsWith('.png')).length} screenshots in ${path.basename(OUT)}`);
  flush();
  console.log(log.join('\n'));
})().catch(err => { console.error(err); process.exit(1); });
