/* Phase-9.6 browser evidence against the local preview (TEST DB only; synthetic accounts seeded by
   tools/phase9-preview-seed.py + tools/phase9.3-preview-seed.py). Seven synthetic personas, each in a
   real Chromium (desktop 1280×800 and mobile 390×844) against the real backend; every claim is checked
   against the page DOM *and* the HTTP API from inside the page (same cookies), so what is screenshotted
   is what the server actually returned:
     guest           → home + intro banner, archive list, product page with the form-centric CTA, purchase
                       form entry, playback denial (download 401), Q&A read-only;
     registered-absent (91012) → «رویدادهای من» shows the registration, held event archive denied (403),
                       no certificate, no purchase row;
     checked-in (91011) → attended archive opens (download 200/206, access=attended), certificate section;
     holder (91001)  → paid product: library + «رویدادهای من», authorized playback (206), participation
                       stays registered=false/attended=false (purchase ≠ attendance), certs for the event = 0;
     pending buyer (91002) → order pending, playback denied (403 / access_pending), no second order row;
     manager         → archive/sessions admin, certificates admin, outbox + scheduler (buttons follow
                       server permissions; finance hidden);
     owner           → same areas + refund/finance controls, scheduler run button.
   Nothing from the credentials file or the env is printed.

   Usage (test server + test DB only):
     NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<node deps dir> NORA_QA_ORIGIN=http://127.0.0.1:8000 \
     NORA_QA_BALE_BOT_TOKEN=<test-only bot token> node tools/phase9.6-browser-evidence.cjs <output dir> */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { launchBrowser } = require('./browser-launch.cjs');
const ORIGIN = process.env.NORA_QA_ORIGIN || 'http://127.0.0.1:8000';
const OUT = process.argv[2] || path.join(process.cwd(), 'phase9.6-shots');
const BOT_TOKEN = process.env.NORA_QA_BALE_BOT_TOKEN || 'test-only-bale-token';
const creds = fs.readFileSync(path.join(__dirname, '..', 'PREVIEW-LOGIN.local.md'), 'utf8');
const pick = re => (creds.match(re) || [])[1];
const OWNER = { user: pick(/مالک: `([^`]+)`/), pass: pick(/مالک: `[^`]+` \/ `([^`]+)`/) };
const MANAGER = { user: pick(/مدیر: `([^`]+)`/), pass: pick(/مدیر: `[^`]+` \/ `([^`]+)`/) };
if (!OWNER.pass || !MANAGER.pass) throw new Error('credentials file not parsed');
const PAID = pick(/paid=(ev-[0-9a-f]+)/), HELD = pick(/held93=(ev-[0-9a-f]+)/);
const HOLDER = Number(pick(/buyer=(\d+)/)), PENDING = Number(pick(/pending=(\d+)/));
const ATTENDEE = Number(pick(/attendee=(\d+)/)), ABSENT = Number(pick(/absent=(\d+)/));
if (!PAID || !HELD || !HOLDER || !PENDING || !ATTENDEE || !ABSENT) throw new Error('seed identifiers missing — run tools/phase9-preview-seed.py + phase9.3-preview-seed.py');
fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = [];
const RUN = crypto.randomBytes(3).toString('hex');

function initData(userId, salt) {
  const fields = { auth_date: String(Math.floor(Date.now() / 1000)), query_id: 'preview-' + userId + '-' + RUN + '-' + salt, user: JSON.stringify({ id: userId, first_name: 'آزمایش' }) };
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
async function memberLogin(page, userId, salt) {
  await page.goto(ORIGIN + '/events.html', { waitUntil: 'load', timeout: 60000 });
  const status = await page.evaluate(async data => {
    const r = await fetch('/api/auth/bale-mini-app', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ init_data: data }), credentials: 'same-origin' });
    return r.status;
  }, initData(userId, salt));
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
const scrollTo = (page, sel) => page.evaluate(s => { const el = document.querySelector(s); if (el) el.scrollIntoView({ block: 'start' }); }, sel).catch(() => {});
const bodyHas = (page, re) => page.evaluate(src => new RegExp(src).test(document.body.innerText), re.source);

/* HTTP probes executed inside the page (same session cookies as the screenshots). */
const probe = (page, ev) => page.evaluate(async ev => {
  const j = async r => { try { return await r.json(); } catch (e) { return null; } };
  const rec = await fetch(`/api/public/events/${ev}/recording`); const recJ = await j(rec);
  const product = recJ && recJ.recording ? recJ.recording : {};
  const sessions = product.sessions || [];
  const files = sessions.flatMap(s => (s.resources || []).filter(r => r.kind === 'file'));
  const first = files[0] || sessions.flatMap(s => s.resources || [])[0];
  let download = null;
  if (first) {
    const d = await fetch(`/api/public/events/${ev}/resources/${first.id}/download`, { headers: { Range: 'bytes=0-15' } });
    download = { status: d.status, access: d.headers.get('x-nora-resource-access'), code: d.status >= 400 ? (((await j(d)) || {}).detail || {}).code || (((await j(d)) || {}).detail || {}).reason || null : null };
  }
  const inter = await j(await fetch(`/api/public/events/${ev}/interaction`));
  const viewer = inter && inter.viewer ? inter.viewer : {};
  const me = await fetch('/api/account/me');
  let orders = null, library = null, certs = null, regs = null;
  if (me.status === 200) {
    const o = await j(await fetch('/api/account/recording-orders?limit=50&offset=0')); orders = (o && o.items ? o.items : []).filter(x => x.recording_id === product.id).map(x => ({ status: x.status, method: x.method, paid: x.paid, open: x.open }));
    const l = await j(await fetch('/api/account/recordings?limit=50&offset=0')); library = (l && l.items ? l.items : []).filter(x => x.event_id === ev || x.recording_id === product.id).map(x => ({ access: x.access, status: x.status }));
    const c = await j(await fetch('/api/account/certificates?limit=50&offset=0')); const items = c && c.items ? c.items : Array.isArray(c) ? c : []; certs = { total: items.length, forEvent: items.filter(x => x.event_id === ev || (x.event || {}).id === ev).length };
    const g = await j(await fetch('/api/account/registrations?limit=50&offset=0')); regs = (g && g.items ? g.items : []).filter(x => x.event_id === ev).map(x => ({ status: x.status, checked_in: x.ticket_checked_in === true }));
  }
  const pv = product.viewer || {};
  return { recStatus: rec.status, cta: pv.cta ? pv.cta.kind : null, access: pv.access || null, formId: product.purchase ? product.purchase.form_id : '', sessions: sessions.length, resources: sessions.reduce((n, s) => n + (s.resources || []).length, 0), download, viewer: { buyer: viewer.buyer, participation: viewer.participation, canAsk: viewer.can_ask, canReview: viewer.can_review }, me: me.status, orders, library, certs, regs };
}, ev);

async function adminShots(page, who, tag, label) {
  const perms = await page.evaluate(async () => { const a = await fetch('/api/account/me'); if (a.status === 200) return (await a.json()).permissions || []; const o = await fetch('/api/auth/me'); return o.status === 200 ? ((await o.json()).permissions || []) : []; });
  /* archive/sessions admin */
  await page.goto(ORIGIN + '/admin.html#events', { waitUntil: 'load', timeout: 60000 }); await page.reload({ waitUntil: 'load', timeout: 60000 }); await sleep(3500);
  const opened = await page.evaluate(ev => { const b = document.querySelector(`[data-ct-interaction="${ev}"]`); if (b) { b.click(); return true; } return false; }, PAID);
  await sleep(2000);
  await page.evaluate(() => { const tab = [...document.querySelectorAll('[data-ei-tab]')].find(x => x.dataset.eiTab === 'recording'); if (tab) tab.click(); }); await sleep(3000);
  const rec = await page.evaluate(() => { const box = document.querySelector('[data-rec-status-box]'); return { status: box ? box.innerText.replace(/\s+/g, ' ').slice(0, 160) : '', sessions: document.querySelectorAll('[data-rec-sess-edit]').length, grant: !!document.querySelector('[data-rec-grant-open]'), orders: !!document.querySelector('[data-rec-open-orders]'), refund: !!document.querySelector('[data-rec-order-refund]') }; });
  await snap(page, `${tag}-${label}-admin-archive`);
  expect(`${tag} ${label} archive/sessions admin`, opened && rec.sessions >= 1 && rec.grant === perms.includes('ev_publish'), `product status «${rec.status.slice(0, 80)}»; sessions listed=${rec.sessions}; grant button=${rec.grant} (ev_publish=${perms.includes('ev_publish')}); orders tab=${rec.orders}`, rec);
  /* resources tab (sessions/files) */
  await page.evaluate(() => { const tab = [...document.querySelectorAll('[data-ei-tab]')].find(x => x.dataset.eiTab === 'resources'); if (tab) tab.click(); }); await sleep(2500);
  const res = await page.evaluate(() => ({ rows: document.querySelectorAll('[data-ei-res-row]').length, storage: (document.querySelector('[data-ei-storage]') || { innerText: '' }).innerText.replace(/\s+/g, ' ').slice(0, 140) }));
  await snap(page, `${tag}-${label}-admin-resources`);
  expect(`${tag} ${label} resources admin`, res.rows >= 1, `resource rows=${res.rows}; storage notice «${res.storage}»`, res);
  /* orders tab: refund button only with finance */
  await page.evaluate(() => { const tab = [...document.querySelectorAll('[data-ei-tab]')].find(x => x.dataset.eiTab === 'orders'); if (tab) tab.click(); }); await sleep(3000);
  const ord = await page.evaluate(() => ({ rows: document.querySelectorAll('[data-rec-order-detail]').length, refund: document.querySelectorAll('[data-rec-order-refund]').length, decide: document.querySelectorAll('[data-rec-order-decide]').length, text: document.body.innerText.replace(/\s+/g, ' ').slice(0, 40) }));
  await snap(page, `${tag}-${label}-admin-orders`);
  const finance = perms.includes('finance');
  expect(`${tag} ${label} orders admin`, ord.rows >= 1 && (finance ? true : ord.refund === 0), `order rows=${ord.rows}; refund buttons=${ord.refund} (finance=${finance}); decide buttons=${ord.decide}`, { ord, perms });
  /* certificates admin */
  await page.goto(ORIGIN + '/admin.html#cert', { waitUntil: 'load', timeout: 60000 }); await page.reload({ waitUntil: 'load', timeout: 60000 }); await sleep(4500);
  const cert = await page.evaluate(() => ({ rows: document.querySelectorAll('[data-cert-open]').length, text: document.body.innerText.replace(/\s+/g, ' ').includes('گواهی'), issue: document.querySelectorAll('[data-certapprove]').length, bot: /ربات|certcenter/.test(document.body.innerText) }));
  await snap(page, `${tag}-${label}-admin-certificates`);
  expect(`${tag} ${label} certificates admin`, cert.text, `certificate rows=${cert.rows}; approve controls=${cert.issue}; mentions bot path=${cert.bot}`, cert);
  /* outbox + scheduler */
  await page.goto(ORIGIN + '/admin.html#users', { waitUntil: 'load', timeout: 60000 }); await page.reload({ waitUntil: 'load', timeout: 60000 }); await sleep(3500);
  await page.evaluate(() => { const b = document.querySelector('[data-user-hub="reports"]'); if (b) b.click(); }); await sleep(5000);
  const sched = await page.evaluate(() => {
    const card = document.querySelector('[data-server-sched]'); if (card) card.scrollIntoView({ block: 'start' });
    const run = document.querySelector('[data-server-sched-run]'); const time = run ? run.querySelector('time') : null;
    return { present: !!card, state: card ? card.getAttribute('data-server-sched-state') : '', runButton: !!document.querySelector('[data-server-sched-run-now]'), runLine: run ? run.innerText.replace(/\s+/g, ' ') : '', datetime: time ? time.getAttribute('datetime') : '', outbox: !!document.querySelector('[data-server-outbox]'), outboxRows: document.querySelectorAll('[data-server-outbox-row]').length, retry: document.querySelectorAll('[data-server-outbox-retry]').length };
  });
  await snap(page, `${tag}-${label}-admin-scheduler`);
  await scrollTo(page, '[data-server-outbox]'); await sleep(400);
  await snap(page, `${tag}-${label}-admin-outbox`);
  expect(`${tag} ${label} scheduler + outbox`, sched.present && sched.outbox && sched.runButton === perms.includes('ev_publish') && /به وقت تهران/.test(sched.runLine) && /(Z|\+00:00)$/.test(sched.datetime),
    `scheduler state=${sched.state}; run button=${sched.runButton}; last-run line «${sched.runLine.slice(0, 120)}» (datetime=${sched.datetime}); outbox rows=${sched.outboxRows}, retry buttons=${sched.retry} (only failed rows)`, sched);
  return perms;
}

(async () => {
  for (const mobile of [false, true]) {
    const tag = mobile ? 'm' : 'd';

    /* ── 1. guest ── */
    {
      const ctx = await context(mobile); const page = await ctx.newPage();
      await page.goto(ORIGIN + '/', { waitUntil: 'load', timeout: 60000 }); await sleep(3500);
      const home = await page.evaluate(() => ({ banner: (() => { const b = document.querySelector('#bnr'); return !!b && !b.hidden && b.offsetHeight > 0; })(), events: document.querySelectorAll('a[href*="event.html?id="]').length, files: /فایل‌های شخصی/.test(document.body.innerText) }));
      await snap(page, `${tag}-1-guest-home`);
      expect(`${tag} guest home`, home.events >= 1 && home.banner && !home.files, `home.html renders ${home.events} event link(s); banner section #bnr visible=${home.banner}; «فایل‌های شخصی» absent for guests=${!home.files}`, home);
      await page.goto(ORIGIN + '/events.html', { waitUntil: 'load', timeout: 60000 }); await sleep(3500);
      const archive = await page.evaluate(() => ({ cards: document.querySelectorAll('a[href*="event.html?id="]').length }));
      await snap(page, `${tag}-1-guest-archive`);
      expect(`${tag} guest archive`, archive.cards >= 1, `events page lists ${archive.cards} event link(s)`, archive);
      await page.goto(ORIGIN + `/event.html?id=${PAID}#recording`, { waitUntil: 'load', timeout: 60000 }); await sleep(4500);
      await scrollTo(page, '[data-rec-cta]'); await sleep(400);
      const g = await page.evaluate(() => ({ cta: (document.querySelector('[data-rec-cta]') || { getAttribute: () => '' }).getAttribute('data-rec-cta'), buy: !!document.querySelector('[data-rec-buy]'), login: !!document.querySelector('[data-rec-login]'), player: !!document.querySelector('video[data-rec-player]'), frames: document.querySelectorAll('iframe').length, qa: !!document.querySelector('[data-event-interaction="qa"]'), askForm: !!document.querySelector('[data-ei-form="question"]'), reviewForm: !!document.querySelector('[data-ei-form="review"]') }));
      const gp = await probe(page, PAID);
      await snap(page, `${tag}-1-guest-product`);
      expect(`${tag} guest product page`, (g.cta === 'login' || g.login) && !g.player && g.frames === 0 && gp.me === 401 && gp.download && gp.download.status === 401 && g.qa && !g.askForm && !g.reviewForm,
        `CTA=${g.cta} (login required, no purchase without identity); no player/iframe; download → ${gp.download && gp.download.status}; /api/account/me → ${gp.me}; Q&A visible read-only (ask form=${g.askForm}, review form=${g.reviewForm})`, { g, gp });
      /* purchase form entry: the form link is derived from the product (form-centric) — open it as guest */
      await page.goto(ORIGIN + `/event.html?id=${PAID}#recording`, { waitUntil: 'load', timeout: 60000 }); await sleep(3000);
      const formHref = gp.formId;
      if (formHref) {
        await page.goto(ORIGIN + `/form.html?fid=${encodeURIComponent(formHref)}`, { waitUntil: 'load', timeout: 60000 }); await sleep(4000);
        const f = await page.evaluate(() => ({ text: document.body.innerText.replace(/\s+/g, ' ').slice(0, 200), needsLogin: /ورود|وارد شوید/.test(document.body.innerText), submit: !!document.querySelector('button[type="submit"], [data-form-submit]') }));
        await snap(page, `${tag}-1-guest-purchase-form`);
        expect(`${tag} guest purchase form`, f.needsLogin, `form.html for the product's purchase form: login required before purchase (text «${f.text.slice(0, 90)}»)`, f);
      } else record(`${tag} guest purchase form`, 'purchase form id not exposed to guests by the recording API (CTA=login) — form entry is only reachable after login');
      await ctx.close();
    }

    /* ── 2. registered-absent ── */
    {
      const ctx = await context(mobile); const page = await ctx.newPage(); await memberLogin(page, ABSENT, tag + 'a');
      await page.goto(ORIGIN + '/account.html#events', { waitUntil: 'load', timeout: 60000 }); await sleep(4500);
      const acc = await page.evaluate(ev => { const items = [...document.querySelectorAll('.server-registration')].map(c => ({ ev: c.getAttribute('data-account-registration-event'), lifecycle: (c.querySelector('[data-account-registration-lifecycle]') || { getAttribute: () => '' }).getAttribute('data-account-registration-lifecycle'), archive: !!c.querySelector('[data-account-registration-archive]'), text: c.innerText.replace(/\s+/g, ' ').slice(0, 120) })); return { items, held: items.find(i => i.ev === ev) }; }, HELD);
      await snap(page, `${tag}-2-absent-account-events`);
      const ap = await probe(page, HELD);
      await page.goto(ORIGIN + `/event.html?id=${HELD}#recording`, { waitUntil: 'load', timeout: 60000 }); await sleep(4500); await scrollTo(page, '[data-rec-cta]'); await sleep(400);
      const apage = await page.evaluate(() => ({ cta: (document.querySelector('[data-rec-cta]') || { getAttribute: () => '' }).getAttribute('data-rec-cta'), player: !!document.querySelector('video[data-rec-player]'), download: document.querySelectorAll('[data-rec-download]').length }));
      await snap(page, `${tag}-2-absent-held-denied`);
      expect(`${tag} registered-absent`, !!acc.held && ap.regs && ap.regs.length >= 1 && ap.regs.every(r => !r.checked_in) && ap.download && ap.download.status === 403 && !apage.player && apage.download === 0 && ap.certs && ap.certs.forEvent === 0 && ap.orders && ap.orders.length === 0 && ap.viewer.participation && ap.viewer.participation.registered === true && ap.viewer.participation.attended === false,
        `«رویدادهای من» shows the held registration «${acc.held ? acc.held.text.slice(0, 60) : ''}»; registration checked_in=false; event page CTA=${apage.cta}; attended-only archive download → ${ap.download && ap.download.status} ${ap.download && ap.download.code}; certs for event=${ap.certs && ap.certs.forEvent}; purchase rows=${ap.orders && ap.orders.length}; participation=${JSON.stringify(ap.viewer.participation)}`, { acc, ap, apage });
      await ctx.close();
    }

    /* ── 3. checked-in attendee ── */
    {
      const ctx = await context(mobile); const page = await ctx.newPage(); await memberLogin(page, ATTENDEE, tag + 'c');
      await page.goto(ORIGIN + `/event.html?id=${HELD}#recording-sessions`, { waitUntil: 'load', timeout: 60000 }); await sleep(4500); await scrollTo(page, '#recording-sessions'); await sleep(400);
      const cp = await probe(page, HELD);
      const cpage = await page.evaluate(() => ({ cta: (document.querySelector('[data-rec-cta]') || { getAttribute: () => '' }).getAttribute('data-rec-cta'), resources: document.querySelectorAll('[data-rec-resource]').length, badge: !!document.querySelector('[data-ei-badge="attendee"]'), askForm: !!document.querySelector('[data-ei-form="question"]'), reviewForm: !!document.querySelector('[data-ei-form="review"]') }));
      await snap(page, `${tag}-3-attendee-archive`);
      expect(`${tag} checked-in attendee archive`, cp.viewer.participation && cp.viewer.participation.attended === true && cp.download && [200, 206].includes(cp.download.status) && cp.download.access === 'attended' && cpage.resources >= 1 && cp.orders && cp.orders.length === 0,
        `participation=${JSON.stringify(cp.viewer.participation)}; download → ${cp.download && cp.download.status} x-nora-resource-access=${cp.download && cp.download.access}; ${cpage.resources} resource(s) rendered; attendee badge=${cpage.badge}; can ask=${cp.viewer.canAsk}, can review=${cp.viewer.canReview} (forms: ask=${cpage.askForm}, review=${cpage.reviewForm}); purchase rows=${cp.orders && cp.orders.length} (attendance ≠ purchase)`, { cp, cpage });
      await scrollTo(page, '[data-event-interaction="qa"]'); await sleep(400);
      await snap(page, `${tag}-3-attendee-qa-comments`);
      await page.goto(ORIGIN + '/account.html#library', { waitUntil: 'load', timeout: 60000 }); await sleep(4500);
      await scrollTo(page, '[data-account-certificates]'); await sleep(400);
      const certUi = await page.evaluate(() => ({ section: !!document.querySelector('[data-account-certificates]'), items: document.querySelectorAll('[data-account-certificate]').length, bot: !!document.querySelector('[data-account-cert-bot]'), text: (document.querySelector('[data-account-certificates]') || { innerText: '' }).innerText.replace(/\s+/g, ' ').slice(0, 160) }));
      await snap(page, `${tag}-3-attendee-certificates`);
      expect(`${tag} checked-in certificates section`, certUi.section && certUi.items === (cp.certs ? cp.certs.total : -1), `account certificates section present; rendered=${certUi.items}, API total=${cp.certs && cp.certs.total} (issued only through the bot certcenter / explicit staff path; bot link=${certUi.bot}) «${certUi.text.slice(0, 90)}»`, { certUi, cp });
      await ctx.close();
    }

    /* ── 4. holder (paid, approved) ── */
    {
      const ctx = await context(mobile); const page = await ctx.newPage(); await memberLogin(page, HOLDER, tag + 'h');
      await page.goto(ORIGIN + '/account.html#library', { waitUntil: 'load', timeout: 60000 }); await sleep(4500); await scrollTo(page, '[data-account-library]'); await sleep(400);
      const lib = await page.evaluate(ev => ({ section: !!document.querySelector('[data-account-library]'), rows: document.querySelectorAll('[data-account-rec-view], [data-account-rec-library]').length, hasEvent: !!document.querySelector(`[data-account-rec-view][href*="${ev}"], [data-account-rec-library][href*="${ev}"], a[href*="event.html?id=${ev}"]`) }), PAID);
      await snap(page, `${tag}-4-holder-library`);
      await page.goto(ORIGIN + '/account.html#events', { waitUntil: 'load', timeout: 60000 }); await sleep(4500);
      const myEv = await page.evaluate(() => ({ regs: document.querySelectorAll('.server-registration').length, text: document.body.innerText.replace(/\s+/g, ' ').slice(0, 60) }));
      await snap(page, `${tag}-4-holder-my-events`);
      await page.goto(ORIGIN + '/account.html#payments', { waitUntil: 'load', timeout: 60000 }); await sleep(4500); await scrollTo(page, '[data-account-rec-orders]'); await sleep(400);
      const ord = await page.evaluate(() => ({ orders: document.querySelectorAll('[data-account-rec-order]').length, invoice: document.querySelectorAll('[data-account-rec-invoice]').length, text: (document.querySelector('[data-account-rec-orders]') || { innerText: '' }).innerText.replace(/\s+/g, ' ').slice(0, 140) }));
      await snap(page, `${tag}-4-holder-orders`);
      await page.goto(ORIGIN + `/event.html?id=${PAID}#recording-sessions`, { waitUntil: 'load', timeout: 60000 }); await sleep(4500); await scrollTo(page, '#recording-sessions'); await sleep(400);
      const hp = await probe(page, PAID);
      const hpage = await page.evaluate(() => ({ cta: (document.querySelector('[data-rec-cta]') || { getAttribute: () => '' }).getAttribute('data-rec-cta'), player: !!document.querySelector('video[data-rec-player]'), resources: document.querySelectorAll('[data-rec-resource]').length, buy: !!document.querySelector('[data-rec-buy]'), apiHrefs: [...document.querySelectorAll('a[href]')].filter(a => /\/private\/|\/home\//.test(a.getAttribute('href'))).length, badge: !!document.querySelector('[data-ei-badge="buyer"]') }));
      await snap(page, `${tag}-4-holder-playback`);
      expect(`${tag} holder authorized playback`, hp.download && hp.download.status === 206 && hp.download.access === 'purchased' && hpage.resources >= 1 && !hpage.buy && hpage.apiHrefs === 0 && hp.library && hp.library.length >= 1 && hp.orders && hp.orders.length === 1 && lib.section && lib.rows >= 1 && ord.orders >= 1,
        `Range download → ${hp.download && hp.download.status} (x-nora-resource-access=${hp.download && hp.download.access}); CTA=${hpage.cta}; ${hpage.resources} resource(s); no buy button; no raw storage hrefs; library rows for event=${hp.library && hp.library.length}; ledger rows for event=${hp.orders && hp.orders.length} (${hp.orders && hp.orders[0] && hp.orders[0].status}); «محتوای من» library cards=${lib.rows}; «پرداخت‌ها» order cards=${ord.orders}; «رویدادهای من» registration cards=${myEv.regs} (purchase is not a registration)`, { hp, hpage, lib, ord });
      expect(`${tag} holder purchase ≠ attendance ≠ certificate`, hp.viewer.buyer === true && hp.viewer.participation && hp.viewer.participation.registered === false && hp.viewer.participation.attended === false && hp.certs && hp.certs.forEvent === 0 && hp.regs && hp.regs.length === 0,
        `viewer.buyer=${hp.viewer.buyer}; participation=${JSON.stringify(hp.viewer.participation)}; registrations for event=${hp.regs && hp.regs.length}; certificates for event=${hp.certs && hp.certs.forEvent}`, hp);
      await ctx.close();
    }

    /* ── 5. pending buyer ── */
    {
      const ctx = await context(mobile); const page = await ctx.newPage(); await memberLogin(page, PENDING, tag + 'p');
      await page.goto(ORIGIN + `/event.html?id=${PAID}#recording`, { waitUntil: 'load', timeout: 60000 }); await sleep(4500); await scrollTo(page, '[data-rec-cta]'); await sleep(400);
      const pp = await probe(page, PAID);
      const ppage = await page.evaluate(() => ({ cta: (document.querySelector('[data-rec-cta]') || { getAttribute: () => '' }).getAttribute('data-rec-cta'), player: !!document.querySelector('video[data-rec-player]'), locked: !!document.querySelector('[data-rec-locked]'), buy: !!document.querySelector('[data-rec-buy]'), text: (document.querySelector('[data-rec-cta]') || { innerText: '' }).innerText.replace(/\s+/g, ' ').slice(0, 140) }));
      await snap(page, `${tag}-5-pending-product`);
      await page.goto(ORIGIN + '/account.html#payments', { waitUntil: 'load', timeout: 60000 }); await sleep(4500); await scrollTo(page, '[data-account-rec-orders]'); await sleep(400);
      const pacc = await page.evaluate(() => ({ orders: document.querySelectorAll('[data-account-rec-order]').length, statuses: [...document.querySelectorAll('[data-account-rec-order]')].map(x => x.getAttribute('data-rec-order-status')), text: (document.querySelector('[data-account-rec-orders]') || { innerText: '' }).innerText.replace(/\s+/g, ' ').slice(0, 160) }));
      await snap(page, `${tag}-5-pending-account`);
      expect(`${tag} pending buyer`, pp.download && pp.download.status === 403 && !ppage.player && !ppage.buy && pp.orders && pp.orders.length === 1 && /pending|awaiting|receipt|review/.test(pp.orders[0].status) && pp.library && pp.library.length === 0 && pp.certs && pp.certs.forEvent === 0 && pp.viewer.participation && pp.viewer.participation.attended === false && pacc.orders >= 1,
        `download → ${pp.download && pp.download.status} ${pp.download && pp.download.code}; CTA=${ppage.cta} «${ppage.text.slice(0, 70)}»; ledger rows for event=${pp.orders && pp.orders.length} (${pp.orders && pp.orders[0] && pp.orders[0].status}); library rows=${pp.library && pp.library.length}; no second order from a revisit; «پرداخت‌ها» order cards=${pacc.orders} ${JSON.stringify(pacc.statuses)}`, { pp, ppage, pacc });
      await ctx.close();
    }

    /* ── 6. manager ── */
    {
      const ctx = await context(mobile); const page = await ctx.newPage(); await staffLogin(page, MANAGER);
      const perms = await adminShots(page, MANAGER, tag, '6-manager');
      expect(`${tag} manager permissions`, !perms.includes('finance') && perms.includes('ev_publish') && perms.includes('rp_view'), `manager permissions from server: ev_publish=${perms.includes('ev_publish')}, rp_view=${perms.includes('rp_view')}, finance=${perms.includes('finance')}`, perms);
      await ctx.close();
    }

    /* ── 7. owner ── */
    {
      const ctx = await context(mobile); const page = await ctx.newPage(); await staffLogin(page, OWNER);
      const perms = await adminShots(page, OWNER, tag, '7-owner');
      expect(`${tag} owner permissions`, perms.includes('finance') && perms.includes('ev_publish'), `owner permissions from server include finance=${perms.includes('finance')}, ev_publish=${perms.includes('ev_publish')}`, perms);
      await ctx.close();
    }
  }

  log.push('', `ARTIFACTS: ${fs.readdirSync(OUT).filter(f => f.endsWith('.png')).length} screenshots in ${path.basename(OUT)}`);
  flush();
  console.log(log.join('\n'));
})().catch(err => { console.error(err); process.exit(1); });
