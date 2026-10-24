/* Phase-9.1 browser evidence against the local preview (test DB, synthetic accounts).
   Covers the form-centric purchase entry, the certificate policy statement and the external
   video sources.  Logs in through the real auth endpoints inside the browser context (no cookie
   forging).  Screenshots: mobile 390x844 + desktop 1280x800.  Credentials and ids come from the
   gitignored PREVIEW-LOGIN.local.md written by tools/phase9-preview-seed.py; nothing is printed.

   Usage (test server + test DB only):
     NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<node deps dir> \
     NORA_QA_ORIGIN=http://127.0.0.1:8000 NORA_QA_BALE_BOT_TOKEN=<the test-only token the server runs with> \
     node tools/phase9.1-browser-evidence.cjs <output dir>

   External playback: the sandbox has no route to youtube.com / aparat.com, so the iframe state is
   recorded as observed («slow»/«error» = network blocked), never claimed as "played". */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { launchBrowser } = require('./browser-launch.cjs');
const ORIGIN = process.env.NORA_QA_ORIGIN || 'http://127.0.0.1:8000';
const OUT = process.argv[2] || path.join(process.cwd(), 'phase9.1-shots');
const BOT_TOKEN = process.env.NORA_QA_BALE_BOT_TOKEN || 'test-only-bale-token';
const creds = fs.readFileSync(path.join(__dirname, '..', 'PREVIEW-LOGIN.local.md'), 'utf8');
const pick = re => (creds.match(re) || [])[1];
const OWNER = { user: pick(/مالک: `([^`]+)`/), pass: pick(/مالک: `[^`]+` \/ `([^`]+)`/) };
const MANAGER = { user: pick(/مدیر: `([^`]+)`/), pass: pick(/مدیر: `[^`]+` \/ `([^`]+)`/) };
if (!OWNER.pass || !MANAGER.pass) throw new Error('credentials file not parsed');
const EV = { paid: pick(/paid=(ev-[0-9a-f]+)/), free: pick(/free=(ev-[0-9a-f]+)/) };
const FORM = pick(/fid=([0-9a-f-]{36})/);
const REC = pick(/محصول: ([0-9a-f-]{36})/);
if (!FORM || !REC) throw new Error('purchase form / product id missing from the credentials file (re-run the seed)');
fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = [];
const YT_ID = 'jNQXAC9IVRw', AP_ID = 'IM5AJ';
const FRESH_MEMBER = 92000 + (Date.now() % 100000) * 2; /* even/odd pair per run (test DB only) */

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
  await page.goto(ORIGIN + '/account.html', { waitUntil: 'load', timeout: 60000 });
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
const text = page => page.evaluate(() => document.body.innerText.replace(/\s+/g, ' '));
const expect = (name, cond, note) => { log.push(`${cond ? '✓' : '✗'} ${name}: ${note}`); fs.writeFileSync(path.join(OUT, 'browser-checks.txt'), log.join('\n') + '\n'); if (!cond) process.exitCode = 1; };
const record = (name, note) => { log.push(`• ${name}: ${note}`); fs.writeFileSync(path.join(OUT, 'browser-checks.txt'), log.join('\n') + '\n'); };
const recordingApi = async (page, id) => page.evaluate(async eid => { const r = await fetch(`/api/public/events/${eid}/recording`); return [r.status, await r.json()]; }, id);

(async () => {
  for (const mobile of [true, false]) {
    const tag = mobile ? 'm' : 'd';
    /* ── guest ── */
    let ctx = await context(mobile); let page = await ctx.newPage();
    let t = await shot(page, `/event.html?id=${EV.paid}`, `${tag}-01-guest-event`, { hash: '#recording', wait: 3500, scrollTo: '#recording' });
    const g = await page.evaluate(() => ({ login: !!document.querySelector('[data-rec-cta="login"]'), order: !!document.querySelector('[data-rec-order]'), buy: !!document.querySelector('[data-rec-buy]'), frames: document.querySelectorAll('iframe').length, html: document.documentElement.outerHTML }));
    expect(`${tag} guest product`, g.login && !g.order && !g.buy && t.includes('گواهی پایان محتوا'), 'login CTA only; no direct order path; certificate policy stated');
    expect(`${tag} guest external ids hidden`, g.frames === 0 && !g.html.includes(YT_ID) && !g.html.includes(AP_ID) && t.includes('ویدیوی یوتیوب') && t.includes('میزبانی بیرونی'), 'external rows listed as locked; no iframe, no video id anywhere in the DOM');
    const [gs, gj] = await recordingApi(page, EV.paid);
    const gRows = gj.recording.sessions.flatMap(s => s.resources).filter(r => r.external);
    expect(`${tag} guest API`, gs === 200 && gRows.length === 2 && gRows.every(r => !r.allowed && !('video' in r) && !('link_url' in r)) && gj.recording.purchase.source === 'form' && gj.recording.purchase.form_id === FORM && gj.recording.certificate.automatic === false, 'API: external rows carry no playback info; commerce source = purchase form; certificate never automatic');
    t = await shot(page, `/form.html?fid=${FORM}&kind=reg`, `${tag}-02-guest-purchase-form`, { wait: 3500 });
    const gf = await page.evaluate(() => ({ header: !!document.querySelector('#purchaseHeader') && !document.querySelector('#purchaseHeader').hidden, login: !!document.querySelector('[data-purchase-login]'), price: (document.querySelector('[data-purchase-price]') || {}).textContent || '' }));
    expect(`${tag} guest purchase form`, gf.header && gf.login && gf.price.includes('۱٬۵۰۰٬۰۰۰') && t.includes('ثبت‌نام یا حضور در رویداد به شمار نمی‌آید'), 'form.html in PURCHASE mode: server price, login required, purchase ≠ registration');
    await ctx.close();

    /* ── member without access: buy CTA → form.html → real purchase → receipt step ── */
    ctx = await context(mobile); page = await ctx.newPage(); await memberLogin(page, FRESH_MEMBER + (mobile ? 0 : 1)); /* a never-seen synthetic member: no earlier order */
    t = await shot(page, `/event.html?id=${EV.paid}`, `${tag}-03-member-buy-cta`, { hash: '#recording', wait: 3500, scrollTo: '#recording' });
    const m = await page.evaluate(() => { const a = document.querySelector('[data-rec-cta="buy"] a[data-rec-buy]'); return { href: a ? a.getAttribute('href') : '', order: !!document.querySelector('[data-rec-order]'), receipt: !!document.querySelector('input[type=file]') }; });
    expect(`${tag} member buy CTA`, m.href === `form.html?fid=${FORM}&kind=reg` && !m.order && !m.receipt, 'only CTA is the purchase form of the product; no parallel order/receipt UI on the event page');
    await page.goto(ORIGIN + `/form.html?fid=${FORM}&kind=reg`, { waitUntil: 'load', timeout: 60000 }); await sleep(3500);
    const started = await page.evaluate(() => !document.querySelector('[data-purchase-login]'));
    let purchase = { ok: false, note: 'not attempted' };
    if (started) {
      try {
        await page.click('#next'); await sleep(600);
        await page.fill('#qa0', 'خریدار مرورگر ' + tag); await sleep(900);
        await page.click('#next'); await sleep(600);
        await page.evaluate(() => { const f = document.querySelector('[data-fin="0"]'); if (f) f.click(); const mth = document.querySelector('[data-method="card_transfer"]'); if (mth) mth.click(); });
        await page.click('#next'); await sleep(600);
        const pay = await page.evaluate(() => ({ card: (document.querySelector('#paymentBankCardNumber') || {}).textContent || '', amount: (document.querySelector('#payAmount') || {}).textContent || '' }));
        await snap(page, `${tag}-04-member-payment-step`);
        await page.click('#next'); await sleep(2500);
        const after = await page.evaluate(() => ({ screen: [...document.querySelectorAll('.screen.on')].map(e => e.id).join(), receipt: !!document.querySelector('#serverReceiptFile'), view: !!document.querySelector('[data-purchase-view]'), active: !!document.querySelector('[data-purchase-state="active"]') }));
        await snap(page, `${tag}-05-member-receipt-step`);
        purchase = { ok: pay.card.replace(/\s/g, '') === '6037997599999993' && pay.amount.includes('۱٬۵۰۰٬۰۰۰') && after.screen === 'u11' && after.receipt && !after.view && !after.active, note: `card/amount from server data, response stored → receipt step (${after.screen}); no access before approval` };
      } catch (e) { purchase = { ok: false, note: 'flow error: ' + (e && e.message || e).slice(0, 160) }; }
    }
    expect(`${tag} member real purchase`, purchase.ok, purchase.note);
    const [ms, mj] = await recordingApi(page, EV.paid);
    expect(`${tag} member after submit`, ms === 200 && mj.recording.viewer.cta.kind === 'order_open' && mj.recording.viewer.access.allowed === false, 'server CTA = order_open (ledger row tied to the form response), still no access');
    t = await shot(page, `/event.html?id=${EV.paid}`, `${tag}-06-member-order-open`, { hash: '#recording', wait: 3500, scrollTo: '#recording' });
    const mo = await page.evaluate(() => ({ via: !!document.querySelector('[data-rec-order-via-form]'), cont: (document.querySelector('a[data-rec-continue-form]') || {}).getAttribute ? document.querySelector('a[data-rec-continue-form]').getAttribute('href') : '', file: !!document.querySelector('#recording input[type=file]') }));
    expect(`${tag} member order open`, mo.via && mo.cont === `form.html?fid=${FORM}&kind=reg` && !mo.file, 'event page shows the open order honestly and sends back to the same form (no parallel receipt upload)');
    t = await shot(page, '/account.html', `${tag}-07-member-account-orders`, { hash: '#payments', wait: 3000 });
    const ma = await page.evaluate(() => ({ card: !!document.querySelector('[data-account-rec-order]'), via: !!document.querySelector('[data-account-rec-via-form]'), form: (document.querySelector('a[data-account-rec-form]') || { getAttribute: () => '' }).getAttribute('href'), file: !!document.querySelector('[data-account-rec-order] input[type=file]') }));
    expect(`${tag} member account orders`, ma.card && ma.via && ma.form === `form.html?fid=${FORM}&kind=reg` && !ma.file, 'order history from the server; form-backed order links to form.html, no receipt form in the account');
    await ctx.close();

    /* ── pending buyer (receipt waiting in the inbox) ── */
    ctx = await context(mobile); page = await ctx.newPage(); await memberLogin(page, 91002);
    const pendDl = await page.evaluate(async id => { const r = await fetch(`/api/public/events/${id}/recording`); const j = await r.json(); const v = j.recording.sessions.flatMap(s => s.resources).find(x => x.content_type === 'video/mp4'); const d = await fetch(`/api/public/events/${id}/resources/${v.id}/download`); return d.status; }, EV.paid);
    expect(`${tag} pending direct URL`, pendDl === 403, 'receipt submitted ≠ access: private video URL → 403');
    await ctx.close();

    /* ── buyer with access: private player + external players ── */
    ctx = await context(mobile); page = await ctx.newPage(); await memberLogin(page, 91001);
    t = await shot(page, `/event.html?id=${EV.paid}`, `${tag}-08-buyer-sessions`, { hash: '#recording-sessions', wait: 4000, scrollTo: '#recording-sessions' });
    const b = await page.evaluate(() => ({ view: !!document.querySelector('[data-rec-cta="view"] [data-rec-view]'), player: !!document.querySelector('video[data-rec-player]'), frames: [...document.querySelectorAll('iframe[data-rec-embed-frame]')].map(f => f.getAttribute('src')), states: [...document.querySelectorAll('.ei-embed')].map(e => e.getAttribute('data-embed-provider') + '=' + e.getAttribute('data-embed-state')), open: [...document.querySelectorAll('a[data-rec-embed-open]')].map(a => a.getAttribute('href')), download: document.querySelectorAll('[data-rec-resource] a[download]').length }));
    expect(`${tag} buyer players`, b.view && b.player && b.frames.length === 2 && b.frames.every(s => /^https:\/\/www\.(youtube-nocookie|aparat)\.com\//.test(s)) && b.frames.some(s => s.includes('/embed/' + YT_ID)) && b.frames.some(s => s.includes('/videohash/' + AP_ID + '/vt/frame')), 'private file player + two official embed frames (youtube-nocookie, aparat) built only from server-issued URLs');
    expect(`${tag} buyer fallback links`, b.open.includes(`https://www.youtube.com/watch?v=${YT_ID}`) && b.open.includes(`https://www.aparat.com/v/${AP_ID}`) && t.includes('DRM'), 'fallback «open in platform» links live on the server origin; honest «external hosting, no DRM» note');
    await page.evaluate(() => { const el = document.querySelector('.ei-embed'); if (el) el.scrollIntoView({ block: 'center' }); }); await sleep(13500);
    const states = await page.evaluate(() => [...document.querySelectorAll('.ei-embed')].map(e => e.getAttribute('data-embed-provider') + '=' + e.getAttribute('data-embed-state')));
    await snap(page, `${tag}-09-buyer-external-players`);
    record(`${tag} external playback state (sandbox)`, states.join(', ') + ' — "ready" only means the iframe fired its load event (Chromium fires it for its own network-error page too), so it is NOT proof that the platform was reached or that the video plays; this sandbox has no route to youtube.com/aparat.com (curl → SSL connect error). Real playback = untested here.');
    const [bs, bj] = await recordingApi(page, EV.paid);
    const bRows = bj.recording.sessions.flatMap(s => s.resources).filter(r => r.external);
    const extDl = await page.evaluate(async ({ eid, rid }) => (await fetch(`/api/public/events/${eid}/resources/${rid}/download`)).status, { eid: EV.paid, rid: bRows[0].id });
    expect(`${tag} buyer API`, bs === 200 && bRows.every(r => r.allowed && r.video && r.downloadable === false && r.delivery === 'view') && extDl === 404, 'playback info only for the access holder; external rows never downloadable through Nora');
    t = await shot(page, '/account.html', `${tag}-10-buyer-library`, { hash: '#library', wait: 3000 });
    const lib = await page.evaluate(() => ({ cert: (document.querySelector('[data-account-rec-certificate]') || {}).getAttribute ? document.querySelector('[data-account-rec-certificate]').getAttribute('data-account-rec-certificate') : '', btn: /دریافت گواهی|صدور گواهی/.test(document.body.innerText) }));
    expect(`${tag} buyer library certificate`, lib.cert === 'manual' && !lib.btn && t.includes('فقط با صدور دستی برگزارکننده') && !t.includes('ادامهٔ مشاهده'), 'library states the manual-only certificate policy; no issue button, no fake progress');
    await ctx.close();

    /* ── manager: inbox task + product tab (commerce from form) + external resource preview ── */
    ctx = await context(mobile); page = await ctx.newPage(); await staffLogin(page, MANAGER);
    await page.goto(ORIGIN + '/admin.html#inbox', { waitUntil: 'load', timeout: 60000 }); await sleep(3500);
    await snap(page, `${tag}-11-manager-inbox`);
    t = await text(page);
    expect(`${tag} manager inbox`, t.includes('فیش خرید محتوای ضبط‌شده') && t.includes('خرید دسترسی به محتوای ضبط‌شده (ثبت‌نام یا حضور به شمار نمی‌آید)') && t.includes('نسخهٔ ضبط‌شدهٔ کارگاه نجوم رصدی'), 'receipt review task of the purchase form sits in the shared inbox and reads as a PURCHASE (not a registration)');
    await page.goto(ORIGIN + '/admin.html#events', { waitUntil: 'load', timeout: 60000 }); await sleep(2500);
    const opened = await page.evaluate(id => { const b = document.querySelector(`[data-ct-interaction="${id}"]`); if (b) { b.click(); return true; } return false; }, EV.paid);
    await sleep(2000);
    await page.evaluate(() => { const tab = [...document.querySelectorAll('[data-ei-tab]')].find(x => x.dataset.eiTab === 'recording'); if (tab) tab.click(); });
    await sleep(3000);
    await page.evaluate(() => { const el = document.querySelector('[data-rec-commerce]'); if (el) el.scrollIntoView({ block: 'center' }); }); await sleep(300);
    await snap(page, `${tag}-12-manager-product-commerce`);
    const pc = await page.evaluate(() => ({ src: (document.querySelector('[data-rec-commerce]') || {}).getAttribute ? document.querySelector('[data-rec-commerce]').getAttribute('data-rec-commerce') : '', edit: (document.querySelector('a[data-rec-form-edit]') || { getAttribute: () => '' }).getAttribute('href'), pub: (document.querySelector('a[data-rec-form-public]') || { getAttribute: () => '' }).getAttribute('href'), card: !!document.querySelector('#recf_card_number'), text: document.body.innerText.replace(/\s+/g, ' ') }));
    expect(`${tag} manager product commerce`, opened && pc.src === 'form' && pc.edit.startsWith(`create.html?fid=${FORM}`) && pc.pub === `form.html?fid=${FORM}&kind=reg` && !pc.card && pc.text.includes('گواهی پایان محتوا: صدور دستی'), 'commerce box: source = purchase form, edit in builder, public form link; no card/wallet fields on the product; certificate policy visible');
    await page.evaluate(() => { const tab = [...document.querySelectorAll('[data-ei-tab]')].find(x => x.dataset.eiTab === 'resources'); if (tab) tab.click(); });
    await sleep(3000);
    const pv = await page.evaluate(() => { const b = [...document.querySelectorAll('[data-ei-res-preview]')][0]; if (b) { b.click(); return b.getAttribute('data-ei-res-preview'); } return ''; });
    await sleep(2500);
    await page.evaluate(id => { const el = document.querySelector(`[data-ei-video-preview="${id}"]`); if (el) el.scrollIntoView({ block: 'center' }); }, pv); await sleep(300);
    await snap(page, `${tag}-13-manager-resource-preview`);
    const pr = await page.evaluate(id => ({ frame: (document.querySelector(`[data-ei-video-preview="${id}"] iframe`) || { getAttribute: () => '' }).getAttribute('src'), kinds: [...document.querySelectorAll('[data-ei-res-row]')].map(r => r.textContent).filter(x => /ویدیوی (یوتیوب|آپارات)/.test(x)).length, text: document.body.innerText.replace(/\s+/g, ' ') }), pv);
    expect(`${tag} manager resource preview`, !!pv && /^https:\/\/www\.(youtube-nocookie|aparat)\.com\//.test(pr.frame) && pr.kinds === 2 && pr.text.includes('غیرقابل‌جاسازی'), 'real preview only on request, from the official embed URL the server stored; honest note that the platform decides embeddability');
    await ctx.close();

    /* ── owner: builder opened on the purchase form ── */
    ctx = await context(mobile); page = await ctx.newPage(); await staffLogin(page, OWNER);
    await page.goto(ORIGIN + `/create.html?fid=${FORM}&back=admin.html%23newev`, { waitUntil: 'load', timeout: 60000 }); await sleep(4000);
    /* cold local cache → the page hydrates the form once from the API and reloads itself */
    if (!/hydrated=1/.test(page.url())) await sleep(4000);
    if (/hydrated=1/.test(page.url())) await sleep(3000);
    record(`${tag} builder hydration`, /hydrated=1/.test(page.url()) ? 'form fetched from the API on a cold cache (one reload)' : 'no API hydration happened — see the state tag in the screenshot');
    await page.evaluate(() => { const el = document.querySelector('#purchaseFormBox'); if (el) el.scrollIntoView({ block: 'center' }); }); await sleep(300);
    await snap(page, `${tag}-14-owner-builder-purchase-form`);
    const ob = await page.evaluate(() => { const box = document.querySelector('#purchaseFormBox'); return { shown: !!box && !box.hidden, text: box ? box.innerText.replace(/\s+/g, ' ') : '', page: document.body.innerText.replace(/\s+/g, ' ') }; });
    expect(`${tag} owner builder purchase mode`, ob.shown && /ضبط‌شده|خرید/.test(ob.text) && ob.page.includes('نسخهٔ ضبط‌شدهٔ کارگاه نجوم رصدی'), 'builder shows the purpose «دسترسی به محتوای ضبط‌شده» and the linked product');
    await ctx.close();
  }
  fs.writeFileSync(path.join(OUT, 'browser-checks.txt'), log.join('\n') + '\n');
  console.log(log.join('\n'));
})().catch(e => { console.error('ERR', e && e.stack || e); process.exit(1); });
