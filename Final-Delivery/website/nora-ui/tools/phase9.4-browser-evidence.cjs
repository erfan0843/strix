/* Phase-9.4 browser evidence against the local preview (TEST DB only, synthetic accounts seeded by
   tools/phase9-preview-seed.py + tools/phase9.3-preview-seed.py; the server runs with
   NORA_PRIVATE_STORAGE_DIR set to a test directory outside the web root).
   Covers the 9.4 acceptance items that need a real browser + real HTTP:
   (1) owner panel: event tool «منابع» shows the real storage state per file row and the server storage
       notice (local disk configured); a NEW file resource is created and uploaded through the panel's own
       API client (owner-api.js, same CSRF rules), then published → the row shows «ذخیره‌سازی: آماده · دیسک»;
   (2) playback authz over real HTTP: access holder gets 206 for a valid Range and 416 for an unsatisfiable
       one; a member without access gets 403; a guest gets 401; URL never reveals a path;
   (3) notification: publishing the live resource queued ONE `recording_content` row for the active holder
       (none for the pending buyer); the holder's account shows it with an in-app link button that lands on
       the product page; the outbox endpoint is 403 for a member and 401 for a guest;
   (4) manager panel «گزارش سرور»: outbox card with real queue/no-Bale/retry states from the server.

   Usage (test server + test DB only; nothing is printed from the env):
     NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<node deps dir> NORA_QA_ORIGIN=http://127.0.0.1:8000 \
     NORA_QA_BALE_BOT_TOKEN=<test-only bot token> node tools/phase9.4-browser-evidence.cjs <output dir> */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { launchBrowser } = require('./browser-launch.cjs');
const ORIGIN = process.env.NORA_QA_ORIGIN || 'http://127.0.0.1:8000';
const OUT = process.argv[2] || path.join(process.cwd(), 'phase9.4-shots');
const BOT_TOKEN = process.env.NORA_QA_BALE_BOT_TOKEN || 'test-only-bale-token';
const creds = fs.readFileSync(path.join(__dirname, '..', 'PREVIEW-LOGIN.local.md'), 'utf8');
const pick = re => (creds.match(re) || [])[1];
const OWNER = { user: pick(/مالک: `([^`]+)`/), pass: pick(/مالک: `[^`]+` \/ `([^`]+)`/) };
const MANAGER = { user: pick(/مدیر: `([^`]+)`/), pass: pick(/مدیر: `[^`]+` \/ `([^`]+)`/) };
if (!OWNER.pass || !MANAGER.pass) throw new Error('credentials file not parsed');
const EV = pick(/paid=(ev-[0-9a-f]+)/);
const HOLDER = Number(pick(/buyer=(\d+)/)), PENDING = Number(pick(/pending=(\d+)/));
if (!EV || !HOLDER || !PENDING) throw new Error('phase 9 seed identifiers missing — run tools/phase9-preview-seed.py');
fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = [];
const RUN = crypto.randomBytes(3).toString('hex');

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
async function shot(page, url, name, { wait = 2500, hash = '', scrollTo = '' } = {}) {
  await page.goto(ORIGIN + url + hash, { waitUntil: 'load', timeout: 60000 });
  await sleep(wait);
  if (scrollTo) await page.evaluate(sel => { const el = document.querySelector(sel); if (el) el.scrollIntoView({ block: 'start' }); }, scrollTo).catch(() => {});
  await sleep(400);
  await page.screenshot({ path: path.join(OUT, name + '.png'), fullPage: false });
}
const snap = async (page, name) => page.screenshot({ path: path.join(OUT, name + '.png'), fullPage: false });
const flush = () => fs.writeFileSync(path.join(OUT, 'browser-checks.txt'), log.join('\n') + '\n');
const expect = (name, cond, note, dbg) => { log.push(`${cond ? '✓' : '✗'} ${name}: ${note}${!cond && dbg ? ' | ' + JSON.stringify(dbg).slice(0, 700) : ''}`); flush(); };
const record = (name, note) => { log.push(`• ${name}: ${note}`); flush(); };
const openEventTool = async (page, tab) => {
  await page.goto(ORIGIN + '/admin.html#events', { waitUntil: 'load', timeout: 60000 }); await page.reload({ waitUntil: 'load', timeout: 60000 }); await sleep(3500);
  const opened = await page.evaluate(ev => { const b = document.querySelector(`[data-ct-interaction="${ev}"]`); if (b) { b.click(); return true; } return false; }, EV);
  await sleep(2000);
  await page.evaluate(t => { const el = [...document.querySelectorAll('[data-ei-tab]')].find(x => x.dataset.eiTab === t); if (el) el.click(); }, tab);
  await sleep(3000);
  return opened;
};

(async () => {
  let resourceId = '';
  const title = `ویدیوی آزمون ۹.۴ (${RUN})`;
  for (const mobile of [false, true]) {
    const tag = mobile ? 'm' : 'd';

    /* ── owner: storage notice + create/upload/publish a disk-backed file through the panel's API client ── */
    let ctx = await context(mobile); let page = await ctx.newPage(); await staffLogin(page, OWNER);
    const opened = await openEventTool(page, 'resources');
    const before = await page.evaluate(() => {
      const notice = document.querySelector('[data-ei-storage]');
      const rows = [...document.querySelectorAll('[data-ei-res-storage]')].map(el => ({ s: el.getAttribute('data-ei-res-storage'), b: el.getAttribute('data-ei-res-backend') }));
      return { notice: notice ? notice.getAttribute('data-ei-storage') : '', noticeText: notice ? notice.innerText.replace(/\s+/g, ' ').slice(0, 160) : '', rows };
    });
    await page.evaluate(() => { const n = document.querySelector('[data-ei-storage]'); if (n) n.scrollIntoView({ block: 'center' }); });
    await sleep(400);
    await snap(page, `${tag}-01-owner-resources-storage-notice`);
    expect(`${tag} storage notice`, opened && before.notice === 'local_disk' && before.rows.length >= 1 && before.rows.every(r => r.s === 'ready'),
      `panel resources tab reads limits.storage from the server: data-ei-storage=${before.notice} «${before.noticeText}»; existing seeded rows: ${before.rows.map(r => r.s + '/' + r.b).join(', ')} (DB-inline files stay valid next to disk storage)`, before);

    if (!mobile) {
      const created = await page.evaluate(async ({ ev, title }) => {
        const api = window.NORA_SERVER_API;
        const rec = await api.getEventRecording(ev);
        const session = ((rec.recording || {}).sessions || []).find(s => s.status === 'published');
        if (!session) return { error: 'no published session' };
        const row = await api.createEventResource(ev, { kind: 'file', title, description: 'فایل آزمون ذخیره‌سازی خصوصی', access: 'purchased', delivery: 'view', session_id: session.id });
        const bytes = new Uint8Array(4096); bytes.set([0, 0, 0, 0x18, 0x66, 0x74, 0x79, 0x70, 0x6d, 0x70, 0x34, 0x32, 0, 0, 0, 0, 0x6d, 0x70, 0x34, 0x32, 0x69, 0x73, 0x6f, 0x6d]);
        for (let i = 32; i < bytes.length; i++) bytes[i] = i % 251;
        const up = await api.uploadEventResourceFile(ev, row.id, new Blob([bytes], { type: 'video/mp4' }), 'phase94.mp4');
        const pub = await api.updateEventResource(ev, row.id, { status: 'published' });
        return { id: row.id, session: session.id, size: up.size, storage: pub.storage, status: pub.status, live: pub.live, backend: pub.storage && pub.storage.backend };
      }, { ev: EV, title }).catch(e => ({ error: String(e && e.message || e) }));
      resourceId = created.id || '';
      expect('d owner upload via panel API', !!created.id && created.size === 4096 && created.storage && created.storage.state === 'ready' && created.backend === 'local_disk' && created.status === 'published' && created.live === true,
        created.id ? `resource ${created.id} (session ${created.session}) uploaded 4096 B → storage ${JSON.stringify(created.storage)}, published & live` : 'upload failed: ' + created.error, created);
      await openEventTool(page, 'resources');
      const row = await page.evaluate(rid => { const st = document.querySelector(`[data-ei-res-row="${rid}"] [data-ei-res-storage], [data-ei-res-row="${rid}"][data-ei-res-storage]`) || [...document.querySelectorAll('[data-ei-res-storage]')].find(el => (el.closest('[data-ei-res-row]') || {}).dataset && el.closest('[data-ei-res-row]').dataset.eiResRow === rid);
        if (st) st.scrollIntoView({ block: 'center' });
        return { s: st ? st.getAttribute('data-ei-res-storage') : '', b: st ? st.getAttribute('data-ei-res-backend') : '', text: st ? st.innerText : '' }; }, resourceId);
      await sleep(400);
      await snap(page, `d-02-owner-new-row-disk-ready`);
      expect('d owner new row', row.s === 'ready' && row.b === 'local_disk' && /دیسک/.test(row.text), `panel row for the new file: data-ei-res-storage=${row.s}, backend=${row.b} «${row.text}»`, row);
    }
    await ctx.close();

    /* ── access holder: Range 206/416 over real HTTP + notification with in-app link ── */
    ctx = await context(mobile); page = await ctx.newPage(); await memberLogin(page, HOLDER);
    const h = await page.evaluate(async ({ ev, rid, title }) => {
      const url = `/api/public/events/${ev}/resources/${rid}/download`;
      const r1 = await fetch(url, { headers: { Range: 'bytes=0-99' } });
      const r2 = await fetch(url, { headers: { Range: 'bytes=999999-' } });
      const r3 = await fetch(url, { headers: { Range: 'bytes=4000-' } });
      const full = await fetch(url);
      const notes = await (await fetch('/api/account/notifications?limit=50&offset=0')).json();
      const mine = (notes.items || []).filter(n => n.kind === 'recording_content' && (n.body || '').includes(title));
      return { s1: r1.status, cr1: r1.headers.get('content-range'), len1: (await r1.arrayBuffer()).byteLength, ar: r1.headers.get('accept-ranges'), cd: r1.headers.get('content-disposition') || '',
        s2: r2.status, cr2: r2.headers.get('content-range'), s3: r3.status, cr3: r3.headers.get('content-range'), sf: full.status, lenF: (await full.arrayBuffer()).byteLength,
        count: mine.length, link: mine[0] && mine[0].link, state: mine[0] && mine[0].delivery_state, err: mine[0] && mine[0].last_delivery_error, leaks: JSON.stringify(mine).includes('/api/') || /nora-preview|\/home\//.test(JSON.stringify(mine)) };
    }, { ev: EV, rid: resourceId, title });
    expect(`${tag} holder Range over HTTP`, h.s1 === 206 && h.cr1 === 'bytes 0-99/4096' && h.len1 === 100 && h.ar === 'bytes' && h.s2 === 416 && h.cr2 === 'bytes */4096' && h.s3 === 206 && h.cr3 === 'bytes 4000-4095/4096' && h.sf === 200 && h.lenF === 4096 && !/\/home\//.test(h.cd),
      `Range 0-99 → ${h.s1} ${h.cr1} (${h.len1} B, Accept-Ranges=${h.ar}); 999999- → ${h.s2} ${h.cr2}; 4000- → ${h.s3} ${h.cr3}; no Range → ${h.sf} ${h.lenF} B; no filesystem path in headers`, h);
    expect(`${tag} holder notification`, h.count === 1 && h.link === `/event.html?id=${EV}#recording` && (h.state === 'queued' || h.state === 'retrying') && !h.leaks,
      `exactly ONE recording_content row for the new live resource (both desktop+mobile runs re-check the same row: idempotent); link=${h.link}; delivery_state=${h.state} (recorded ≠ delivered: no live bot here); body has no API/file path`, h);
    await shot(page, '/account.html', `${tag}-03-holder-notification-link`, { hash: '#notifications', wait: 4000, scrollTo: 'a[data-account-notice-link="recording_content"]' });
    const linkDom = await page.evaluate(() => { const a = document.querySelector('a[data-account-notice-link="recording_content"]'); return { has: !!a, href: a ? a.getAttribute('href') : '', text: a ? a.innerText.trim() : '', apiLinks: document.querySelectorAll('#viewBox a[href*="/api/"]').length }; });
    expect(`${tag} holder account link`, linkDom.has && linkDom.href === `event.html?id=${EV}#recording` && /دیدن محتوای تازه/.test(linkDom.text) && linkDom.apiLinks === 0,
      `account «اعلان‌ها» renders the in-app button «${linkDom.text}» → ${linkDom.href}; zero /api/ links in the view`, linkDom);
    if (linkDom.has) {
      await page.evaluate(() => document.querySelector('a[data-account-notice-link="recording_content"]').click());
      await sleep(4000);
      const landed = await page.evaluate(() => ({ url: location.href, cta: (document.querySelector('[data-rec-cta]') || {}).getAttribute ? document.querySelector('[data-rec-cta]').getAttribute('data-rec-cta') : '' }));
      await snap(page, `${tag}-04-holder-landed-product-page`);
      expect(`${tag} holder link lands on product`, landed.url.includes(`event.html?id=${EV}`) && landed.cta === 'view', `clicked notification link → ${landed.url.replace(ORIGIN, '')} with CTA=${landed.cta}`, landed);
    }
    const authzMember = await page.evaluate(async () => (await fetch('/api/admin/notifications')).status);
    expect(`${tag} member outbox authz`, authzMember === 403, `GET /api/admin/notifications as a member → ${authzMember} (backend-enforced, no panel tab needed)`, authzMember);
    await ctx.close();

    /* ── pending buyer (no access): 403 + no notification ── */
    ctx = await context(mobile); page = await ctx.newPage(); await memberLogin(page, PENDING);
    const p = await page.evaluate(async ({ ev, rid, title }) => {
      const r = await fetch(`/api/public/events/${ev}/resources/${rid}/download`, { headers: { Range: 'bytes=0-99' } });
      const notes = await (await fetch('/api/account/notifications?limit=50&offset=0')).json();
      const api = await (await fetch(`/api/public/events/${ev}/recording`)).json();
      const res = ((api.recording || {}).sessions || []).flatMap(s => s.resources || []).find(x => x.id === rid);
      return { dl: r.status, body: (await r.text()).slice(0, 120), count: (notes.items || []).filter(n => n.kind === 'recording_content' && (n.body || '').includes(title)).length, listed: !!res, cta: api.recording && api.recording.viewer && api.recording.viewer.access_state };
    }, { ev: EV, rid: resourceId, title });
    await shot(page, `/event.html?id=${EV}`, `${tag}-05-pending-locked`, { hash: '#recording', wait: 4000, scrollTo: '[data-rec-cta]' });
    expect(`${tag} pending buyer`, p.dl === 403 && p.count === 0 && !/\/home\//.test(p.body), `Range download → ${p.dl}; zero recording_content notifications (fan-out only to ACTIVE holders); viewer access_state=${p.cta}`, p);
    await ctx.close();

    /* ── guest ── */
    ctx = await context(mobile); page = await ctx.newPage();
    await page.goto(ORIGIN + `/event.html?id=${EV}#recording`, { waitUntil: 'load', timeout: 60000 }); await sleep(2000);
    const g = await page.evaluate(async ({ ev, rid }) => ({ dl: (await fetch(`/api/public/events/${ev}/resources/${rid}/download`)).status, outbox: (await fetch('/api/admin/notifications')).status, notes: (await fetch('/api/account/notifications')).status }), { ev: EV, rid: resourceId });
    expect(`${tag} guest`, g.dl === 401 && g.outbox === 401 && g.notes === 401, `guest: download ${g.dl}, admin outbox ${g.outbox}, account notifications ${g.notes}`, g);
    await ctx.close();

    /* ── manager: outbox card in «گزارش سرور» ── */
    ctx = await context(mobile); page = await ctx.newPage(); await staffLogin(page, MANAGER);
    const apiOutbox = await page.evaluate(async () => { const r = await fetch('/api/admin/notifications?limit=100'); const j = await r.json().catch(() => ({})); return { status: r.status, counts: j.counts, n: (j.items || []).length, rawBale: JSON.stringify(j).includes('bale_user_id') }; });
    await page.goto(ORIGIN + '/admin.html#users', { waitUntil: 'load', timeout: 60000 }); await page.reload({ waitUntil: 'load', timeout: 60000 }); await sleep(3500);
    await page.evaluate(() => { const b = document.querySelector('[data-user-hub="reports"]'); if (b) b.click(); });
    await sleep(5000);
    const ob = await page.evaluate(() => {
      const card = document.querySelector('[data-server-outbox]'); if (card) card.scrollIntoView({ block: 'start' });
      const rows = [...document.querySelectorAll('[data-server-outbox-row]')].map(r => r.getAttribute('data-server-outbox-state-row'));
      const chips = [...document.querySelectorAll('[data-server-outbox-state]')].map(c => c.innerText.replace(/\s+/g, ' '));
      return { card: !!card, rows, chips, text: card ? card.innerText.replace(/\s+/g, ' ').slice(0, 300) : '' };
    });
    await sleep(500);
    await snap(page, `${tag}-06-manager-outbox-card`);
    expect(`${tag} manager outbox`, apiOutbox.status === 200 && !apiOutbox.rawBale && ob.card && ob.rows.length >= 1 && ob.rows.includes('queued') && ob.chips.length === 6,
      `API counts=${JSON.stringify(apiOutbox.counts)} (no raw bale_user_id); panel card rows=[${ob.rows.join(',')}] chips=[${ob.chips.join(' | ')}]`, { apiOutbox, ob });
    await page.evaluate(() => { const c = document.querySelector('[data-server-outbox-state="queued"]'); if (c) c.click(); });
    await sleep(3000);
    const filtered = await page.evaluate(() => [...document.querySelectorAll('[data-server-outbox-row]')].map(r => r.getAttribute('data-server-outbox-state-row')));
    await snap(page, `${tag}-07-manager-outbox-queued-filter`);
    expect(`${tag} manager outbox filter`, filtered.length >= 1 && filtered.every(s => s === 'queued'), `filter «در صف» → ${filtered.length} rows, all queued`, filtered);
    await ctx.close();
  }
  record('idempotency', 'the resource was created once (desktop run) and both runs observed the same single recording_content row for the holder');
  log.push('', `ARTIFACTS: ${fs.readdirSync(OUT).filter(f => f.endsWith('.png')).length} screenshots in ${path.basename(OUT)}`);
  flush();
  console.log(log.join('\n'));
})().catch(err => { console.error(err); process.exit(1); });
