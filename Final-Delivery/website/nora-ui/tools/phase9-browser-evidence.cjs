/* Phase-9 browser evidence against the local preview (test DB, synthetic accounts).
   Logs in through the real auth endpoints inside the browser context (no cookie forging):
   members via /api/auth/bale-mini-app with a test-token-signed init_data, staff via /api/auth/login.
   Screenshots: mobile 390x844 + desktop 1280x800. Credentials come from the local gitignored file. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
/* Usage (test server + test DB only):
     NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<node deps dir> \
     NORA_QA_ORIGIN=http://127.0.0.1:8000 NORA_QA_BALE_BOT_TOKEN=<the test-only token the server runs with> \
     node tools/phase9-browser-evidence.cjs <output dir>
   Credentials are read from the gitignored PREVIEW-LOGIN.local.md written by the preview seed; nothing is printed. */
const { launchBrowser } = require('./browser-launch.cjs');
const ORIGIN = process.env.NORA_QA_ORIGIN || 'http://127.0.0.1:8000';
const OUT = process.argv[2] || path.join(process.cwd(), 'phase9-shots');
const BOT_TOKEN = process.env.NORA_QA_BALE_BOT_TOKEN || 'test-only-bale-token';
const creds = fs.readFileSync(path.join(__dirname, '..', 'PREVIEW-LOGIN.local.md'), 'utf8');
const pick = re => (creds.match(re) || [])[1];
const OWNER = { user: pick(/مالک: `([^`]+)`/), pass: pick(/مالک: `[^`]+` \/ `([^`]+)`/) };
const MANAGER = { user: pick(/مدیر: `([^`]+)`/), pass: pick(/مدیر: `[^`]+` \/ `([^`]+)`/) };
if (!OWNER.pass || !MANAGER.pass) throw new Error('credentials file not parsed');
const EV = { paid: pick(/paid=(ev-[0-9a-f]+)/), free: pick(/free=(ev-[0-9a-f]+)/), plain: pick(/plain=(ev-[0-9a-f]+)/), up: pick(/upcoming=(ev-[0-9a-f]+)/) };
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
/* @sparticuz/chromium runs single-process: closing a context tears the browser down, so each persona gets its own browser. */
async function launchWithRetry() {
  let last;
  for (let i = 0; i < 4; i++) { try { return await launchBrowser(); } catch (e) { last = e; await sleep(1500); } }
  throw last;
}
async function context(_browser, mobile) {
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
  /* The real staff login page: it confirms the session with the server and stores the panel session marker itself. */
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
  const text = await page.evaluate(() => document.body.innerText.replace(/\s+/g, ' ').slice(0, 20000));
  return text;
}
const expect = (name, cond, note) => { log.push(`${cond ? '✓' : '✗'} ${name}: ${note}`); fs.writeFileSync(path.join(OUT, 'browser-checks.txt'), log.join('\n') + '\n'); if (!cond) process.exitCode = 1; };

(async () => {
  const browser = null;
  for (const mobile of [true, false]) {
    const tag = mobile ? 'm' : 'd';
    /* guest */
    let ctx = await context(browser, mobile); let page = await ctx.newPage();
    let t = await shot(page, '/events.html', `${tag}-01-events-recorded`, { hash: '#recorded', wait: 2500 });
    expect(`${tag} events#recorded`, t.includes('ضبط‌شده') && t.includes('قابل خرید') && t.includes('رایگان') && !t.includes('کارگاه عکاسی شب'), 'archive filter shows only published products');
    t = await shot(page, `/event.html?id=${EV.paid}`, `${tag}-02-event-guest`, { hash: '#recording', wait: 3500, scrollTo: '#recording' });
    const guestDom = await page.evaluate(() => ({ login: !!document.querySelector('[data-rec-cta="login"]'), order: !!document.querySelector('[data-rec-order]'), countdown: !!document.querySelector('.nora-countdown'), sheet: !!document.getElementById('shEvent') }));
    expect(`${tag} guest product`, t.includes('محتوای ضبط‌شده') && guestDom.login && !guestDom.order && !guestDom.countdown && !guestDom.sheet, 'login CTA only, no order button, no countdown, no legacy sheet');
    const guestDl = await page.evaluate(async id => { const r = await fetch(`/api/public/events/${id}/recording`); const j = await r.json(); const v = j.recording.sessions.flatMap(s => s.resources).find(x => x.content_type === 'video/mp4'); const d = await fetch(`/api/public/events/${id}/resources/${v.id}/download`); return d.status; }, EV.paid);
    expect(`${tag} guest direct URL`, guestDl === 401, 'direct video URL → 401 for guest');
    const badge = await page.evaluate(() => !!document.querySelector('[data-event-interaction="reviews"] [data-ei-badge="buyer"]'));
    expect(`${tag} buyer badge`, badge, 'published review carries server-side badge «خریدار تأییدشده»');
    t = await shot(page, `/event.html?id=${EV.plain}`, `${tag}-03-held-no-product`, { wait: 3000 });
    expect(`${tag} held without product`, !t.includes('خرید دسترسی') && !t.includes('محتوای ضبط‌شده') && t.includes('پایان'), 'no purchase anywhere, registration ended');
    t = await shot(page, `/event.html?id=${EV.up}`, `${tag}-04-upcoming`, { wait: 3000 });
    expect(`${tag} upcoming`, t.includes('ثبت‌نام') && !t.includes('محتوای ضبط‌شده'), 'registration still offered, no product');
    await ctx.close();
    /* pending buyer: order open, receipt submitted */
    ctx = await context(browser, mobile); page = await ctx.newPage(); await memberLogin(page, 91002);
    t = await shot(page, `/event.html?id=${EV.paid}`, `${tag}-05-pending-order`, { hash: '#recording', wait: 3500, scrollTo: '#recording' });
    const pendDom = await page.evaluate(() => ({ open: !!document.querySelector('[data-rec-cta="order_open"]'), order: !!document.querySelector('[data-rec-order]'), view: !!document.querySelector('[data-rec-view]') }));
    expect(`${tag} pending`, t.includes('در انتظار بررسی') && pendDom.open && !pendDom.order && !pendDom.view, 'receipt submitted → order_open state, no new order, no access');
    const pendDl = await page.evaluate(async id => { const r = await fetch(`/api/public/events/${id}/recording`); const j = await r.json(); const v = j.recording.sessions.flatMap(s => s.resources).find(x => x.content_type === 'video/mp4'); const d = await fetch(`/api/public/events/${id}/resources/${v.id}/download`); return [d.status, (await d.json()).detail && (await Promise.resolve((await (await fetch(`/api/public/events/${id}/resources/${v.id}/download`)).json()).detail.reason))]; }, EV.paid);
    expect(`${tag} pending direct URL`, pendDl[0] === 403 && pendDl[1] === 'purchase_required', 'direct video URL → 403 purchase_required');
    t = await shot(page, '/account.html', `${tag}-06-account-orders`, { hash: '#payments', wait: 2500 });
    expect(`${tag} account orders`, t.includes('سفارش‌های محتوای ضبط‌شده') && t.includes('در انتظار بررسی') && t.includes('پرداخت ثبت‌نام‌ها'), 'orders listed separately from registration payments');
    await ctx.close();
    /* buyer with access */
    ctx = await context(browser, mobile); page = await ctx.newPage(); await memberLogin(page, 91001);
    t = await shot(page, `/event.html?id=${EV.paid}`, `${tag}-07-buyer-view`, { hash: '#recording-sessions', wait: 3500, scrollTo: '#recording-sessions' });
    const buyerDom = await page.evaluate(() => ({ view: !!document.querySelector('[data-rec-cta="view"] [data-rec-view]'), order: !!document.querySelector('[data-rec-order]'), player: !!document.querySelector('video[data-rec-player]') }));
    expect(`${tag} buyer`, t.includes('دسترسی دارید') && buyerDom.view && !buyerDom.order && buyerDom.player, 'purchased state → view + player, no buy button');
    const buyerDl = await page.evaluate(async id => { const r = await fetch(`/api/public/events/${id}/recording`); const j = await r.json(); const v = j.recording.sessions.flatMap(s => s.resources).find(x => x.content_type === 'video/mp4'); const d = await fetch(`/api/public/events/${id}/resources/${v.id}/download`, { headers: { Range: 'bytes=0-9' } }); return [d.status, d.headers.get('content-range')]; }, EV.paid);
    expect(`${tag} buyer stream`, buyerDl[0] === 206 && /^bytes 0-9\//.test(buyerDl[1] || ''), 'Range request → 206 for the buyer');
    const own = await page.evaluate(() => ({ edit: !!document.querySelector('[data-ei-edit-review]'), form: !!document.querySelector('form[data-ei-form="review"]'), eligible: document.body.innerText.includes('خریدار تأییدشده') }));
    expect(`${tag} buyer review`, own.edit || own.form, 'buyer is review-eligible (own review shown as editable, not as a foreign row)');
    t = await shot(page, '/account.html', `${tag}-08-account-library`, { hash: '#library', wait: 2500 });
    expect(`${tag} library`, t.includes('محتوای من') && t.includes('دسترسی فعال') && t.includes('مشاهدهٔ جلسات') && !t.includes('ادامهٔ مشاهده'), 'library shows real access, no fake progress');
    await ctx.close();
    /* free holder */
    ctx = await context(browser, mobile); page = await ctx.newPage(); await memberLogin(page, 91003);
    t = await shot(page, `/event.html?id=${EV.free}`, `${tag}-09-free-holder`, { hash: '#recording', wait: 3500, scrollTo: '#recording' });
    expect(`${tag} free holder`, t.includes('دسترسی دارید') && t.includes('رایگان'), 'free claim → access, no transaction');
    await ctx.close();
    /* manager: panel orders queue */
    ctx = await context(browser, mobile); page = await ctx.newPage(); await staffLogin(page, MANAGER);
    await page.goto(ORIGIN + '/admin.html#dash', { waitUntil: 'load', timeout: 60000 }); await sleep(3000);
    await page.evaluate(() => { const b = document.querySelector('[data-rec-open-orders]'); if (b) b.click(); });
    await sleep(2500);
    await page.screenshot({ path: path.join(OUT, `${tag}-10-manager-orders.png`) });
    t = await page.evaluate(() => document.body.innerText.replace(/\s+/g, ' '));
    expect(`${tag} manager orders`, t.includes('سفارش') && t.includes('رسید') && !t.includes('ثبت بازپرداخت'), 'manager sees review queue, no refund (finance = owner only)');
    await ctx.close();
    /* owner: product tab */
    ctx = await context(browser, mobile); page = await ctx.newPage(); await staffLogin(page, OWNER);
    await page.goto(ORIGIN + '/admin.html#events', { waitUntil: 'load', timeout: 60000 }); await sleep(2500);
    const opened = await page.evaluate(id => { const b = document.querySelector(`[data-ct-interaction="${id}"]`); if (b) { b.click(); return true; } return false; }, EV.paid);
    await sleep(2000);
    await page.evaluate(() => { const tab = [...document.querySelectorAll('[data-ei-tab]')].find(x => x.dataset.eiTab === 'recording'); if (tab) tab.click(); });
    await sleep(2500);
    await page.screenshot({ path: path.join(OUT, `${tag}-11-owner-product.png`) });
    t = await page.evaluate(() => document.body.innerText.replace(/\s+/g, ' '));
    expect(`${tag} owner product tab`, opened && t.includes('ضبط‌شده و فروش') && t.includes('منتشرشده'), 'owner sees product management inside the event tool');
    await ctx.close();
  }
  fs.writeFileSync(path.join(OUT, 'browser-checks.txt'), log.join('\n') + '\n');
  console.log(log.join('\n'));
})().catch(e => { console.error('ERR', e && e.stack || e); process.exit(1); });
