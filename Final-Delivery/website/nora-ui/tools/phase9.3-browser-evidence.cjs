/* Phase-9.3 browser evidence against the local preview (test DB, synthetic accounts seeded by
   tools/phase9-preview-seed.py + tools/phase9.3-preview-seed.py).
   Covers the acceptance path «in-person workshop held → recording attached to the SAME event →
   courtesy for checked-in attendees, purchase form for everyone else»:
   (1) checked-in attendee: event page CTA «مشاهدهٔ جلسات» (reason=attended), downloads 200, account
       «رویدادهای من» links the held event to its archive, «محتوای من» lists it as «دسترسی حاضران رویداد»
       with NO access row (library row source=attended);
   (2) registered-but-absent member: buy CTA, download 403, no archive link, empty library for that product;
   (3) guest: 401 on the account APIs, nothing rendered;
   (4) manager panel: the product's attendee-access toggle and the external-player warning are visible;
   (5) honest player note: iframe load ≠ playback (data-embed-playback="unverified").

   Usage (test server + test DB only; nothing is printed from the env):
     NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<node deps dir> NORA_QA_ORIGIN=http://127.0.0.1:8000 \
     NORA_QA_BALE_BOT_TOKEN=<test-only bot token> node tools/phase9.3-browser-evidence.cjs <output dir> */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { launchBrowser } = require('./browser-launch.cjs');
const ORIGIN = process.env.NORA_QA_ORIGIN || 'http://127.0.0.1:8000';
const OUT = process.argv[2] || path.join(process.cwd(), 'phase9.3-shots');
const BOT_TOKEN = process.env.NORA_QA_BALE_BOT_TOKEN || 'test-only-bale-token';
const creds = fs.readFileSync(path.join(__dirname, '..', 'PREVIEW-LOGIN.local.md'), 'utf8');
const pick = re => (creds.match(re) || [])[1];
const MANAGER = { user: pick(/مدیر: `([^`]+)`/), pass: pick(/مدیر: `[^`]+` \/ `([^`]+)`/) };
if (!MANAGER.pass) throw new Error('credentials file not parsed');
const EV = pick(/held93=(ev-[0-9a-f]+)/);
const REC = pick(/held93=ev-[0-9a-f]+ · محصول: ([0-9a-f-]{36})/);
const ATTENDEE = Number(pick(/attendee=(\d+)/)), ABSENT = Number(pick(/absent=(\d+)/));
if (!EV || !REC || !ATTENDEE || !ABSENT) throw new Error('phase 9.3 seed identifiers missing — run tools/phase9.3-preview-seed.py');
fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = [];

function initData(userId) {
  const fields = { auth_date: String(Math.floor(Date.now() / 1000)), query_id: 'preview-' + userId, user: JSON.stringify({ id: userId, first_name: 'آزمایش' }) };
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
  return page.evaluate(() => document.body.innerText.replace(/\s+/g, ' ').slice(0, 20000));
}
const snap = async (page, name) => page.screenshot({ path: path.join(OUT, name + '.png'), fullPage: false });
const flush = () => fs.writeFileSync(path.join(OUT, 'browser-checks.txt'), log.join('\n') + '\n');
const expect = (name, cond, note, dbg) => { log.push(`${cond ? '✓' : '✗'} ${name}: ${note}${!cond && dbg ? ' | ' + JSON.stringify(dbg).slice(0, 600) : ''}`); flush(); };
const record = (name, note) => { log.push(`• ${name}: ${note}`); flush(); };

(async () => {
  for (const mobile of [true, false]) {
    const tag = mobile ? 'm' : 'd';

    /* ── guest ── */
    let ctx = await context(mobile); let page = await ctx.newPage();
    await page.goto(ORIGIN + `/event.html?id=${EV}#recording`, { waitUntil: 'load', timeout: 60000 }); await sleep(3000);
    const g = await page.evaluate(async id => {
      const a = await fetch('/api/account/recordings'), b = await fetch('/api/account/registrations?limit=50&offset=0');
      const cta = document.querySelector('[data-rec-cta]');
      return { lib: a.status, regs: b.status, cta: cta ? cta.getAttribute('data-rec-cta') : '', frames: document.querySelectorAll('iframe[data-rec-embed-frame]').length };
    }, EV);
    await snap(page, `${tag}-00-guest-event`);
    expect(`${tag} guest`, g.lib === 401 && g.regs === 401 && g.cta === 'login' && g.frames === 0, `account APIs 401; event CTA=${g.cta}; no player frame for a guest`, g);
    await ctx.close();

    /* ── checked-in attendee ── */
    ctx = await context(mobile); page = await ctx.newPage(); await memberLogin(page, ATTENDEE);
    let t = await shot(page, `/event.html?id=${EV}`, `${tag}-01-attendee-event`, { hash: '#recording', wait: 4000, scrollTo: '[data-rec-cta]' });
    const a = await page.evaluate(async ev => {
      const api = await (await fetch(`/api/public/events/${ev}/recording`)).json();
      const inter = await (await fetch(`/api/public/events/${ev}/interaction`)).json();
      const v = api.recording && api.recording.viewer || {};
      const part = inter.viewer && inter.viewer.participation || null;
      const cta = document.querySelector('[data-rec-cta]');
      const res = (api.recording.sessions || []).flatMap(s => s.resources || []).concat(api.recording.resources || []);
      const locked = res.find(r => r.access === 'purchased' && r.id && r.kind !== 'youtube' && r.kind !== 'aparat') || res.find(r => r.access === 'purchased' && r.id);
      const dl = locked ? (await fetch(`/api/public/events/${ev}/resources/${locked.id}/download`)).status : null;
      return { cta: cta ? cta.getAttribute('data-rec-cta') : '', reason: v.access && v.access.reason, state: v.access_state, part, dl, lockedKind: locked && locked.kind,
        buy: !!document.querySelector('[data-rec-cta="buy"]'), text: cta ? cta.innerText.replace(/\s+/g, ' ') : '' };
    }, EV);
    expect(`${tag} attendee event page`, a.cta === 'view' && a.reason === 'attended' && !a.buy && a.dl === 200 && a.part && a.part.attended === true && a.part.registered === true,
      `CTA=${a.cta} («${a.text}»), server reason=${a.reason}, participation registered=${a.part && a.part.registered}/attended=${a.part && a.part.attended}, locked ${a.lockedKind} download → ${a.dl} (no buy CTA for a checked-in attendee)`, a);

    t = await shot(page, `/event.html?id=${EV}`, `${tag}-02-attendee-player`, { hash: '#recording-sessions', wait: 4000, scrollTo: '.ei-embed' });
    await sleep(9000);
    const pl = await page.evaluate(() => [...document.querySelectorAll('.ei-embed')].map(e => ({ p: e.getAttribute('data-embed-provider'), s: e.getAttribute('data-embed-state'), pb: e.getAttribute('data-embed-playback'),
      note: ((e.parentElement && e.parentElement.querySelector('[data-embed-playback-note]')) || {}).textContent || '', drm: /DRM/.test((e.parentElement || e).innerText) })));
    await snap(page, `${tag}-03-attendee-player-state`);
    expect(`${tag} player honesty`, pl.length >= 1 && pl.every(x => x.s !== 'ready' || (x.pb === 'unverified' && /بارگذاری شد/.test(x.note) && /تأیید نمی‌کند/.test(x.note))) && pl.every(x => x.drm),
      pl.map(x => `${x.p}=${x.s}${x.pb ? '/' + x.pb : ''} «${x.note}»`).join(', ') + ' — iframe load is never presented as playback; «بدون حفاظت یا DRM» stated; the sandbox has no route to youtube.com, so real playback is NOT claimed', pl);

    t = await shot(page, '/account.html', `${tag}-04-attendee-my-events`, { hash: '#events', wait: 4000, scrollTo: `[data-account-registration-event="${EV}"]` });
    const me = await page.evaluate(async ({ ev, rec }) => {
      const card = document.querySelector(`[data-account-registration-event="${ev}"]`);
      const arch = card && card.querySelector('[data-account-registration-archive]');
      const link = card && card.querySelector('a[data-account-registration-view]');
      const lib = await (await fetch('/api/account/recordings')).json();
      const row = (lib.items || []).find(i => i.recording_id === rec);
      return { card: !!card, checked: card ? card.innerText.includes('حضور ثبت شده') : false, arch: arch ? arch.getAttribute('data-archive-source') : '', archText: arch ? arch.innerText : '',
        href: link ? link.getAttribute('href') : '', buyBtn: card ? [...card.querySelectorAll('a,button')].some(b => /خرید/.test(b.innerText)) : null,
        row: row ? row.access : null, progress: row ? row.progress : undefined, total: lib.total };
    }, { ev: EV, rec: REC });
    expect(`${tag} attendee «رویدادهای من»`, me.card && me.checked && me.arch === 'attended' && me.href === `event.html?id=${EV}#recording-sessions` && me.buyBtn === false
      && me.row && me.row.state === 'active' && me.row.source === 'attended' && me.row.granted_at === null && me.progress === null,
      `held event card: «حضور ثبت شده» + «${me.archText.replace(/\s+/g, ' ')}» → ${me.href}; API row access=${JSON.stringify(me.row)} (derived, no grant row, no fake progress)`, me);

    t = await shot(page, '/events.html', `${tag}-05-attendee-library`, { wait: 1000 });
    t = await shot(page, '/account.html', `${tag}-05-attendee-library`, { hash: '#library', wait: 4000, scrollTo: `[data-account-rec-library="${REC}"]` });
    const lb = await page.evaluate(rec => { const c = document.querySelector(`[data-account-rec-library="${rec}"]`); return { has: !!c, text: c ? c.innerText.replace(/\s+/g, ' ') : '', view: !!(c && c.querySelector('a[data-account-rec-view]')), cont: /ادامهٔ مشاهده/.test(document.body.innerText) }; }, REC);
    expect(`${tag} attendee «محتوای من»`, lb.has && lb.text.includes('دسترسی حاضران رویداد') && lb.view && !lb.cont, `library card labelled «دسترسی حاضران رویداد» with «مشاهدهٔ جلسات»; no «ادامهٔ مشاهده» without real progress`, lb);
    await ctx.close();

    /* ── registered but absent ── */
    ctx = await context(mobile); page = await ctx.newPage(); await memberLogin(page, ABSENT);
    t = await shot(page, `/event.html?id=${EV}`, `${tag}-06-absent-event`, { hash: '#recording', wait: 4000, scrollTo: '[data-rec-cta]' });
    const b = await page.evaluate(async ({ ev, rec }) => {
      const api = await (await fetch(`/api/public/events/${ev}/recording`)).json();
      const inter = await (await fetch(`/api/public/events/${ev}/interaction`)).json();
      const v = api.recording && api.recording.viewer || {};
      v.participation = inter.viewer && inter.viewer.participation || null;
      const cta = document.querySelector('[data-rec-cta]');
      const res = (api.recording.sessions || []).flatMap(s => s.resources || []).concat(api.recording.resources || []);
      const locked = res.find(r => r.access === 'purchased' && r.id);
      const dl = locked ? (await fetch(`/api/public/events/${ev}/resources/${locked.id}/download`)).status : null;
      const lib = await (await fetch('/api/account/recordings')).json();
      return { cta: cta ? cta.getAttribute('data-rec-cta') : '', reason: v.access && v.access.reason, part: v.participation, dl, inLib: (lib.items || []).some(i => i.recording_id === rec), frames: document.querySelectorAll('iframe[data-rec-embed-frame]').length };
    }, { ev: EV, rec: REC });
    expect(`${tag} absent member event page`, b.cta === 'buy' && b.part && b.part.registered === true && b.part.attended === false && b.dl === 403 && !b.inLib && b.frames === 0,
      `CTA=${b.cta}; registered=${b.part && b.part.registered}, attended=${b.part && b.part.attended}; locked download → ${b.dl}; not in library; no player frame (registration ≠ attendance ≠ access)`, b);
    t = await shot(page, '/account.html', `${tag}-07-absent-my-events`, { hash: '#events', wait: 4000, scrollTo: `[data-account-registration-event="${EV}"]` });
    const bm = await page.evaluate(ev => { const c = document.querySelector(`[data-account-registration-event="${ev}"]`); return { card: !!c, checked: c ? c.innerText.includes('حضور ثبت شده') : null, link: !!(c && c.querySelector('[data-account-registration-archive]')) }; }, EV);
    expect(`${tag} absent «رویدادهای من»`, bm.card && bm.checked === false && !bm.link, 'registration card present, no «حضور ثبت شده», no archive link', bm);
    await ctx.close();

    /* ── manager panel: toggle + external warning ── */
    ctx = await context(mobile); page = await ctx.newPage(); await staffLogin(page, MANAGER);
    const found = await page.evaluate(async ev => {
      const r = await fetch(`/api/admin/events/${ev}/recording`); const j = await r.json().catch(() => ({}));
      return { status: r.status, attendee_access: j.recording ? j.recording.attendee_access : j.attendee_access, product: j.recording ? j.recording.status : j.status };
    }, EV);
    expect(`${tag} manager API`, found.status === 200 && found.attendee_access === true && found.product === 'published', `GET /api/admin/events/${EV}/recording → ${found.status}; attendee_access=${found.attendee_access}; status=${found.product}`, found);
    await page.goto(ORIGIN + `/admin.html#events`, { waitUntil: 'load', timeout: 60000 }); await page.reload({ waitUntil: 'load', timeout: 60000 }); await sleep(3500);
    const opened = await page.evaluate(ev => { const b = document.querySelector(`[data-ct-interaction="${ev}"]`); if (b) { b.click(); return true; } return false; }, EV);
    await sleep(2000);
    await page.evaluate(() => { const tab = [...document.querySelectorAll('[data-ei-tab]')].find(x => x.dataset.eiTab === 'recording'); if (tab) tab.click(); });
    await sleep(3000);
    await snap(page, `${tag}-08-manager-product-status`);
    const statusBox = await page.evaluate(() => { const box = document.querySelector('[data-rec-status-box]'); return box ? box.innerText.replace(/\s+/g, ' ').slice(0, 200) : ''; });
    await page.evaluate(() => { const b = document.querySelector('[data-rec-edit]'); if (b) b.click(); });
    await sleep(2500);
    const toggle = await page.evaluate(() => { const t = document.querySelector('input[data-rec-flag="attendee_access"]'); const box = document.querySelector('[data-rec-status-box]');
      return { toggle: t ? t.checked : null, label: t ? t.parentElement.innerText : '', status: box ? box.innerText.replace(/\s+/g, ' ').slice(0, 200) : '' }; });
    await page.evaluate(() => { const el = document.querySelector('input[data-rec-flag="attendee_access"]'); if (el) el.parentElement.scrollIntoView({ block: 'center' }); });
    await sleep(500);
    await snap(page, `${tag}-08-manager-product-edit`);
    expect(`${tag} manager product tab`, opened && toggle.toggle === true && /حاضران تأییدشده/.test(toggle.label) && /در حال فروش/.test(statusBox),
      `product tab inside the event tool: status «${statusBox.slice(0, 90)}»; editor flag «${toggle.label}» checked (server attendee_access=true)`, { toggle, statusBox });
    /* external-player warning: open the YouTube resource editor (resources tab) */
    await page.evaluate(() => { const tab = [...document.querySelectorAll('[data-ei-tab]')].find(x => x.dataset.eiTab === 'resources'); if (tab) tab.click(); });
    await sleep(2500);
    const edited = await page.evaluate(() => { const row = [...document.querySelectorAll('[data-ei-res-edit]')].find(b => /یوتیوب/.test((b.closest('[data-ei-res-row]') || {}).innerText || '')); if (row) { row.click(); return true; } return false; });
    await sleep(2500);
    const warn = await page.evaluate(() => { const w = document.querySelector('[data-ei-external-warning]'); return { kind: w ? w.getAttribute('data-ei-external-warning') : '', text: w ? w.innerText.replace(/\s+/g, ' ').slice(0, 200) : '' }; });
    if (warn.kind) { await page.evaluate(() => document.querySelector('[data-ei-external-warning]').scrollIntoView({ block: 'center' })); await sleep(400); }
    await snap(page, `${tag}-09-manager-external-warning`);
    expect(`${tag} external-player warning`, edited && warn.kind === 'paid' && /Unlisted/.test(warn.text) && /بیرون از نورا/.test(warn.text), edited ? `YouTube resource editor: data-ei-external-warning=${warn.kind}: ${warn.text}` : 'resource editor button not found', warn);
    await ctx.close();
  }
  log.push('', `ARTIFACTS: ${fs.readdirSync(OUT).filter(f => f.endsWith('.png')).length} screenshots in ${path.basename(OUT)}`);
  flush();
  console.log(log.join('\n'));
})().catch(err => { console.error(err); process.exit(1); });
