/* Phase-9.2 browser evidence against the local preview (test DB, synthetic accounts).
   Covers: (1) «گواهینامه‌های من» in the account — only rows the bot mirrored for THIS account,
   the recorded-content completion kind shown apart from attendance kinds, files only via the Bale
   bot; (2) the managers' certificate registry filter for the new kind; (3) the external video
   players' real state in this sandbox (no route to youtube.com / aparat.com — recorded as observed,
   never claimed as "played").

   The certificates are mirrored through the REAL bot→server endpoint (/api/bot/certificates) with
   the service token the server runs with; nothing is written to the database directly.

   Usage (test server + test DB only; nothing is printed from the env):
     NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<node deps dir> NORA_QA_ORIGIN=http://127.0.0.1:8000 \
     NORA_QA_BALE_BOT_TOKEN=<test-only bot token> NORA_QA_SERVICE_TOKEN=<test-only service token> \
     node tools/phase9.2-browser-evidence.cjs <output dir> */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { launchBrowser } = require('./browser-launch.cjs');
const ORIGIN = process.env.NORA_QA_ORIGIN || 'http://127.0.0.1:8000';
const OUT = process.argv[2] || path.join(process.cwd(), 'phase9.2-shots');
const BOT_TOKEN = process.env.NORA_QA_BALE_BOT_TOKEN || 'test-only-bale-token';
const SERVICE_TOKEN = process.env.NORA_QA_SERVICE_TOKEN || '';
if (!SERVICE_TOKEN) throw new Error('NORA_QA_SERVICE_TOKEN (test-only) is required to mirror certificates through the bot API');
const creds = fs.readFileSync(path.join(__dirname, '..', 'PREVIEW-LOGIN.local.md'), 'utf8');
const pick = re => (creds.match(re) || [])[1];
const MANAGER = { user: pick(/مدیر: `([^`]+)`/), pass: pick(/مدیر: `[^`]+` \/ `([^`]+)`/) };
if (!MANAGER.pass) throw new Error('credentials file not parsed');
const EV = { paid: pick(/paid=(ev-[0-9a-f]+)/) };
fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = [];
const HOLDER = 91001, OTHER = 91003, NONE = 91002;
const RUN = Date.now() % 1000000; /* unique serials per run (test DB only) */
const SOURCE_ID = '0c7f7f5e-9c1e-4a7e-8a1c-2b3d4e5f6a7b';

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
  /* land on a page other than the one under test: a later goto that differs only by #hash would not reload */
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
const expect = (name, cond, note, dbg) => { log.push(`${cond ? '✓' : '✗'} ${name}: ${note}${!cond && dbg ? ' | ' + JSON.stringify(dbg).slice(0, 600) : ''}`); fs.writeFileSync(path.join(OUT, 'browser-checks.txt'), log.join('\n') + '\n'); if (!cond) process.exitCode = 1; };
const record = (name, note) => { log.push(`• ${name}: ${note}`); fs.writeFileSync(path.join(OUT, 'browser-checks.txt'), log.join('\n') + '\n'); };

/* Mirror a certificate exactly like shared_certificates.sync_certificate does (owner = Bale id → server identity). */
async function mirror(baleUserId, legacyId, certificate) {
  const r = await fetch(ORIGIN + '/api/bot/certificates', {
    method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + SERVICE_TOKEN },
    body: JSON.stringify({ bale_user_id: String(baleUserId), external_key: `${SOURCE_ID}:${legacyId}`, certificate }),
  });
  return [r.status, await r.json().catch(() => ({}))];
}
const base = extra => ({ status: 'issued', source: 'bot', source_id: SOURCE_ID, kind: 'event', serial: '', full_code: '', doc_no: '1421', person_code: '',
  event_ref: '', event_title: '', title: '', holder_name: 'عضو آزمایشی', issued_on: '1405/07/30', expires_on: '', issued_at: new Date().toISOString().replace(/\.\d{3}Z$/, '+00:00'),
  issued_by_bale_user_id: '70001', verify_count: 0, ...extra });

(async () => {
  /* ── seed through the real bot→server path ── */
  const seeds = [
    mirror(HOLDER, 920000 + RUN, base({ legacy_id: 920000 + RUN, kind: 'recording', serial: `1421/R${RUN}`, full_code: `1421/R${RUN}`, person_code: `R${RUN}`, title: 'پایان دورهٔ ضبط‌شدهٔ نجوم مقدماتی' })),
    mirror(HOLDER, 930000 + RUN, base({ legacy_id: 930000 + RUN, kind: 'event', serial: `NC-${RUN}`, full_code: `1421/A${RUN}`, person_code: `A${RUN}`, event_ref: '17', event_title: 'کارگاه نجوم', title: 'گواهی حضور' })),
    mirror(OTHER, 940000 + RUN, base({ legacy_id: 940000 + RUN, kind: 'recording', status: 'revoked', serial: `1421/X${RUN}`, full_code: `1421/X${RUN}`, person_code: `X${RUN}`, title: 'پایان محتوای تلسکوپ', revoked_at: new Date().toISOString().replace(/\.\d{3}Z$/, '+00:00') })),
    mirror(HOLDER, 950000 + RUN, base({ legacy_id: 950000 + RUN, kind: 'attendance_auto', serial: `BAD-${RUN}` })),
  ];
  const results = await Promise.all(seeds);
  expect('seed via /api/bot/certificates', results[0][0] === 200 && results[1][0] === 200 && results[2][0] === 200 && results[3][0] === 422 && results[3][1].detail === 'invalid_certificate_kind',
    `recording+event for holder, revoked recording for another member mirrored (200); unknown kind rejected 422 (${results.map(r => r[0]).join('/')})`);

  for (const mobile of [true, false]) {
    const tag = mobile ? 'm' : 'd';
    /* ── guest: no certificates, no leak ── */
    let ctx = await context(mobile); let page = await ctx.newPage();
    await page.goto(ORIGIN + '/account.html#library', { waitUntil: 'load', timeout: 60000 }); await sleep(1500);
    const guest = await page.evaluate(async () => { const r = await fetch('/api/account/certificates'); return [r.status, document.querySelectorAll('[data-account-certificate]').length]; });
    expect(`${tag} guest`, guest[0] === 401 && guest[1] === 0, 'GET /api/account/certificates → 401; nothing rendered');
    await ctx.close();

    /* ── holder: two own certificates, kinds apart, delivery via bot only ── */
    ctx = await context(mobile); page = await ctx.newPage(); await memberLogin(page, HOLDER);
    let t = await shot(page, '/account.html', `${tag}-01-holder-certificates`, { hash: '#library', wait: 3500, scrollTo: '[data-account-certificates]' });
    await page.evaluate(run => { window.__RUN = run; }, RUN);
    const h = await page.evaluate(async () => {
      const cards = [...document.querySelectorAll('[data-account-certificate]')];
      const api = await (await fetch('/api/account/certificates')).json();
      const rec = cards.find(c => c.dataset.certKind === 'recording' && c.innerText.includes('R' + window.__RUN)), ev = cards.find(c => c.dataset.certKind === 'event' && c.innerText.includes('A' + window.__RUN));
      const link = rec && rec.querySelector('a[data-account-cert-bot]');
      return { n: cards.length, kinds: cards.map(c => c.dataset.certKind).sort().join(','), statuses: cards.map(c => c.dataset.certStatus).join(','),
        recText: rec ? rec.innerText : '', evText: ev ? ev.innerText : '', href: link ? link.getAttribute('href') : '', rel: link ? link.getAttribute('rel') : '',
        apiTotal: api.total, apiKinds: (api.items || []).map(i => i.kind).sort().join(','), apiLeak: JSON.stringify(api).includes('issued_by') || JSON.stringify(api).includes('account_id'),
        download: !!document.querySelector('[data-account-certificates] a[href*="/api/account/"]'), html: document.querySelector('[data-account-certificates]').innerHTML };
    });
    expect(`${tag} holder sees own rows`, h.n >= 2 && h.n === h.apiTotal && h.kinds === h.apiKinds && h.kinds.includes('event') && h.kinds.includes('recording') && !h.apiLeak, `cards = API rows (${h.apiTotal}: event + recording; earlier runs of this script add rows); no issuer/account identifiers in the payload`, { n: h.n, kinds: h.kinds, apiTotal: h.apiTotal, apiKinds: h.apiKinds, apiLeak: h.apiLeak });
    expect(`${tag} holder kinds distinct`, h.recText.includes('پایان محتوای آموزشی ضبط‌شده') && h.recText.includes('پایان دورهٔ ضبط‌شدهٔ نجوم مقدماتی') && h.recText.includes(`1421/R${RUN}`) && h.recText.includes('گواهی حضور در رویداد نیست')
      && h.evText.includes('گواهی رویداد / حضور') && h.evText.includes('کارگاه نجوم') && !h.evText.includes('حضور در رویداد نیست'), 'completion certificate labelled, titled and numbered apart from the attendance certificate');
    expect(`${tag} holder delivery via bot`, /^https:\/\/ble\.ir\/[A-Za-z0-9_]+\?start=mycerts$/.test(h.href) && h.rel === 'noopener noreferrer' && !h.download && !/درخواست گواهی|ساخت گواهی|صدور گواهی/.test(t), 'file only through the Bale bot deep link; no account download route; no "request/issue" button', { href: h.href, rel: h.rel, download: h.download });
    expect(`${tag} holder no foreign rows`, !h.html.includes(`X${RUN}`) && !t.includes('پایان محتوای تلسکوپ'), 'the other member\'s certificate is not present anywhere on the page');
    await ctx.close();

    /* ── other member: only own revoked row ── */
    ctx = await context(mobile); page = await ctx.newPage(); await memberLogin(page, OTHER);
    t = await shot(page, '/account.html', `${tag}-02-other-revoked`, { hash: '#library', wait: 3500, scrollTo: '[data-account-certificates]' });
    const o = await page.evaluate(() => { const cards = [...document.querySelectorAll('[data-account-certificate]')]; return { n: cards.length, status: cards.map(c => c.dataset.certStatus).join(','), bot: !!document.querySelector('[data-account-certificates] a[data-account-cert-bot]'), text: document.querySelector('[data-account-certificates]').innerText }; });
    expect(`${tag} other member`, o.n >= 1 && o.status.split(',').every(x => x === 'revoked') && !o.bot && o.text.includes('باطل‌شده') && o.text.includes(`1421/X${RUN}`) && !o.text.includes(`R${RUN}`), 'only own revoked certificate(s); real status; no delivery button; nothing of the holder', { n: o.n, status: o.status, bot: o.bot, text: o.text.slice(0, 200) });
    await ctx.close();

    /* ── member without certificates: honest empty state ── */
    ctx = await context(mobile); page = await ctx.newPage(); await memberLogin(page, NONE);
    t = await shot(page, '/account.html', `${tag}-03-empty`, { hash: '#library', wait: 3500, scrollTo: '[data-account-certificates]' });
    const e = await page.evaluate(() => ({ n: document.querySelectorAll('[data-account-certificate]').length, text: document.querySelector('[data-account-certificates]').innerText }));
    expect(`${tag} empty state`, e.n === 0 && e.text.includes('هنوز گواهینامه‌ای در حساب ثبت نشده') && e.text.includes('خرید یا تماشای محتوا به‌تنهایی گواهی نمی‌سازد'), 'no synthetic certificate; purchase/viewing stated as not creating one');
    await ctx.close();

    /* ── manager: registry filter for the new kind ── */
    ctx = await context(mobile); page = await ctx.newPage(); await staffLogin(page, MANAGER);
    await page.goto(ORIGIN + '/admin.html#cert', { waitUntil: 'load', timeout: 60000 }); await page.reload({ waitUntil: 'load', timeout: 60000 }); /* #cert is resolved at boot, not on hashchange */ await sleep(3500);
    const chip = await page.$('[data-cert-kind="recording"]');
    if (chip) { await page.evaluate(el => el.click(), chip); await sleep(2500); }
    await snap(page, `${tag}-04-manager-registry-recording`);
    const mg = await page.evaluate(async () => { const api = await (await fetch('/api/admin/certificates?kind=recording')).json(); return { rows: document.querySelectorAll('[data-cert-open]').length, text: document.body.innerText, apiTotal: api.total, apiKinds: [...new Set((api.items || []).map(i => i.kind))].join(',') }; });
    expect(`${tag} manager registry`, !!chip && mg.apiTotal >= 2 && mg.apiKinds === 'recording' && mg.rows === mg.apiTotal && mg.text.includes('پایان محتوای ضبط‌شده'), `kind filter works end to end (${mg.apiTotal} recording rows, label shown)`, { chip: !!chip, rows: mg.rows, apiTotal: mg.apiTotal, apiKinds: mg.apiKinds, label: mg.text.includes('پایان محتوای ضبط‌شده') });
    await ctx.close();

    /* ── buyer: external players — observed state only ── */
    ctx = await context(mobile); page = await ctx.newPage(); await memberLogin(page, HOLDER);
    t = await shot(page, `/event.html?id=${EV.paid}`, `${tag}-05-buyer-players`, { hash: '#recording-sessions', wait: 4000, scrollTo: '.ei-embed' });
    const headers = await page.evaluate(async () => { const r = await fetch('/event.html', { cache: 'no-store' }); return { rp: r.headers.get('referrer-policy'), csp: r.headers.get('content-security-policy'), xfo: r.headers.get('x-frame-options') }; });
    const fr = await page.evaluate(() => [...document.querySelectorAll('iframe[data-rec-embed-frame]')].map(f => ({ src: f.getAttribute('src'), rp: f.getAttribute('referrerpolicy'), allow: f.getAttribute('allow'), fs: f.hasAttribute('allowfullscreen') })));
    expect(`${tag} embed attributes`, fr.length === 2 && fr.every(f => /^https:\/\/www\.(youtube-nocookie|aparat)\.com\//.test(f.src) && f.rp === 'strict-origin-when-cross-origin' && f.fs) && headers.rp === 'same-origin' && !headers.csp && headers.xfo === 'SAMEORIGIN' && t.includes('کد خطای'),
      `document Referrer-Policy=${headers.rp}; iframe referrerpolicy=strict-origin-when-cross-origin (origin reaches YouTube/Aparat → error-153 precondition met); no page CSP; new in-frame error guidance shown`);
    await sleep(13500);
    const states = await page.evaluate(() => [...document.querySelectorAll('.ei-embed')].map(e => e.getAttribute('data-embed-provider') + '=' + e.getAttribute('data-embed-state')));
    await snap(page, `${tag}-06-buyer-players-state`);
    record(`${tag} external playback (sandbox)`, states.join(', ') + ' — the sandbox has no route to youtube.com/aparat.com; "ready" only means the iframe fired load (Chromium fires it for its own error page). Real playback is NOT verified here.');
    await ctx.close();
  }
  log.push('', `ARTIFACTS: ${fs.readdirSync(OUT).filter(f => f.endsWith('.png')).length} screenshots in ${path.basename(OUT)}`);
  fs.writeFileSync(path.join(OUT, 'browser-checks.txt'), log.join('\n') + '\n');
  console.log(log.join('\n'));
})().catch(err => { console.error(err); process.exit(1); });
