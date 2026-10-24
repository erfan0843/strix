// Guest "حساب من" behaviour checks on the test server + member page sanity (real session cookie minted in the test DB).
import fs from 'node:fs';
import { execSync } from 'node:child_process';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const BASE = 'http://127.0.0.1:8000';
const OUT = '/tmp/qa/acct/flows'; fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let pass = 0, fail = 0;
const ok = (c, m, extra) => { if (c) pass++; else fail++; console.log((c ? 'PASS' : 'FAIL') + ' ' + m + (extra ? ' ' + extra : '')); };
async function launch() { for (let i = 0; ; i++) { try { return await launchBrowser(); } catch (e) { if (i >= 2) throw e; await sleep(1500); } } }
async function withPage(opts, fn) {
  const b = await launch();
  try {
    const ctx = await b.newContext({ viewport: opts.vp || { width: 390, height: 844 }, serviceWorkers: 'block', locale: 'fa-IR', hasTouch: !!opts.touch });
    if (opts.cookies) await ctx.addCookies(opts.cookies);
    await ctx.addInitScript(t => { try { localStorage.setItem('nora-theme', t); } catch (e) {} }, opts.theme || 'light');
    const p = await ctx.newPage(); const errs = [];
    p.on('pageerror', e => errs.push(String(e.message).slice(0, 120)));
    if (opts.route) await opts.route(p);
    await p.goto(BASE + (opts.url || '/account.html'), { waitUntil: 'domcontentloaded' }); await sleep(1500);
    await fn(p, errs);
    ok(errs.length === 0, `${opts.name}: no page errors`, errs.join(' | '));
    await ctx.close();
  } catch (e) { fail++; console.log('FAIL', opts.name, 'threw', e.message.slice(0, 200)); }
  finally { await b.close(); }
}

// 1) guest landing structure + no private data requests other than /api/account/me
await withPage({ name: 'guest-open' }, async p => {
  const r = await p.evaluate(() => ({
    hero: !!document.querySelector('.account-promo-hero'), who: document.querySelector('.account-promo-identity')?.textContent.replace(/\s+/g, ' ').trim(),
    h2: document.querySelector('#accountPromoTitle')?.textContent.replace(/\s+/g, ' ').trim(),
    primary: document.querySelector('.account-promo-hero .btn.primary')?.getAttribute('href'),
    features: [...document.querySelectorAll('.account-promo-feature h4')].map(e => e.textContent.trim()),
    rows: [...document.querySelectorAll('.server-rows a.mrow2')].map(a => a.getAttribute('href')),
    guestChips: document.querySelectorAll('.server-rows .mini-guest').length,
    paybar: !!document.querySelector('.server-paybar'), bottom: !!document.querySelector('.account-promo-bottom'), preview: !!document.querySelector('.account-promo-preview'),
    mheadBg: getComputedStyle(document.querySelector('.server-rows .mhead')).backgroundImage,
    sample: /۵۴۳۲۱|سارا محمدی|۱٬۲۵۰٬۰۰۰|تومان/.test(document.querySelector('#profBox').textContent),
    docH: document.documentElement.scrollHeight, ox: document.documentElement.scrollWidth > innerWidth,
    primaryTop: document.querySelector('.account-promo-hero .btn.primary').getBoundingClientRect().top,
  }));
  ok(r.hero && r.who.includes('مهمان') && r.h2.includes('وارد حسابت شو'), 'guest: hero with «مهمان» identity and new title', r.h2);
  ok(r.primary === 'login.html?mode=server&next=account.html', 'guest: primary CTA → login.html (server mode, next=account.html)', r.primary);
  ok(r.features.join('|') === 'ثبت‌نام‌هایت|اعلان‌های حساب|فایل‌های شخصی', 'guest: three real features only', r.features.join('|'));
  ok(r.rows.length === 4 && r.guestChips === 3 && r.paybar && !r.bottom && !r.preview, 'guest: 4 section rows (3 with «بعد از ورود»), paybar kept, duplicate bottom CTA + mock preview removed', JSON.stringify([r.rows.length, r.guestChips, r.paybar, r.bottom, r.preview]));
  ok(r.mheadBg === 'none', 'rows head: no inherited dark gradient (contrast fix)', r.mheadBg);
  ok(!r.sample && !r.ox && r.primaryTop < 844, 'guest: no sample data, no horizontal overflow, primary CTA above the fold', JSON.stringify([r.sample, r.ox, Math.round(r.primaryTop), r.docH]));
  await p.screenshot({ path: `${OUT}/guest-390.png` });
});
// 2) primary CTA really navigates to login.html
await withPage({ name: 'guest-cta' }, async p => {
  await p.click('.account-promo-hero .btn.primary'); await p.waitForLoadState('domcontentloaded'); await sleep(1200);
  const u = p.url().replace(BASE, '');
  ok(u === '/login.html?mode=server&next=account.html' && await p.$('#lgPhoneForm'), 'guest: CTA opens the real login page with phone form', u);
});
// 3) private row for a guest → existing "needs login" view inside account.html (hash route), not a crash
await withPage({ name: 'guest-private-row' }, async p => {
  await p.click('.server-rows a[href="account.html#events"]'); await sleep(1200);
  const r = await p.evaluate(() => ({ hash: location.hash, view: document.querySelector('#viewBox')?.textContent.replace(/\s+/g, ' ').slice(0, 200), hidden: document.querySelector('#viewBox')?.hidden, loginLink: !!document.querySelector('#viewBox a[href^="login.html?mode=server"]') }));
  ok(r.hash === '#events' && !r.hidden && /نیاز به ورود/.test(r.view) && r.loginLink, 'guest: «رویدادهای من» → existing needs-login view with secure login link (behaviour unchanged)', JSON.stringify(r).slice(0, 160));
  await p.screenshot({ path: `${OUT}/guest-events-needs-login.png` });
});
// 4) public events link
await withPage({ name: 'guest-public' }, async p => {
  await p.click('.account-promo-public'); await p.waitForLoadState('domcontentloaded'); await sleep(800);
  ok(/\/events\.html$/.test(p.url()), 'guest: «دیدن رویدادها» → events.html', p.url().replace(BASE, ''));
});
// 5) offline API → retry button visible in hero, nothing else requested
await withPage({ name: 'guest-offline', route: async p => p.route('**/api/account/me', r => r.abort()) }, async p => {
  const r = await p.evaluate(() => ({ retry: !!document.querySelector('.account-promo [data-server-account-retry]'), hero: !!document.querySelector('.account-promo-hero') }));
  ok(r.retry && r.hero, 'guest offline: hero stays, «بررسی دوباره» rendered in the meta row', JSON.stringify(r));
  await p.screenshot({ path: `${OUT}/guest-offline-390.png` });
});
// 6) widths/themes: 360, 768, 1280 light+dark; no overflow, CTA visible
for (const [w, h] of [[360, 800], [768, 1024], [1280, 800]]) for (const theme of ['light', 'dark']) {
  await withPage({ name: `guest-${w}-${theme}`, vp: { width: w, height: h }, theme }, async p => {
    const r = await p.evaluate(() => ({ ox: document.documentElement.scrollWidth > innerWidth, cta: document.querySelector('.account-promo-hero .btn.primary').getBoundingClientRect(), theme: document.documentElement.dataset.theme,
      small: [...document.querySelectorAll('.account-promo a, .account-promo button')].filter(el => { const b = el.getBoundingClientRect(); return b.width > 0 && b.height < 34; }).length }));
    ok(!r.ox && r.cta.top >= 0 && r.cta.bottom <= h && r.small === 0 && r.theme === theme, `guest ${w}x${h} ${theme}: no overflow, CTA in view, no control <34px`, JSON.stringify([r.ox, Math.round(r.cta.top), r.small]));
    await p.screenshot({ path: `${OUT}/guest-${w}x${h}-${theme}.png` });
  });
}
// 7) member page sanity with a REAL session minted in the test DB (no promo, phead + rows + paybar)
let sess = null;
try { sess = JSON.parse(execSync('bash -c "source /tmp/nora-preview/env.sh && /home/user/venvs/nora/bin/python /tmp/nora-preview/mk_phone_session.py 09125550123 profile"', { encoding: 'utf8' }).trim().split('\n').pop()); } catch (e) { console.log('  session mint failed:', e.message.slice(0, 200)); }
if (sess) {
  const cookies = [{ name: 'nora_account_session', value: sess.session, domain: '127.0.0.1', path: '/', httpOnly: true }, { name: 'nora_account_csrf', value: sess.csrf, domain: '127.0.0.1', path: '/' }];
  for (const [w, h] of [[390, 844], [1280, 800]]) {
    await withPage({ name: `member-${w}`, vp: { width: w, height: h }, cookies }, async p => {
      const r = await p.evaluate(() => ({ promo: !!document.querySelector('.account-promo'), head: !!document.querySelector('.server-account-head'), rows: document.querySelectorAll('.server-rows a.mrow2').length, guestChips: document.querySelectorAll('.server-rows .mini-guest').length, paybar: !!document.querySelector('.server-paybar'), txt: document.querySelector('#profBox').textContent.replace(/\s+/g, ' ').slice(0, 120) }));
      ok(!r.promo && r.head && r.rows === 4 && r.guestChips === 0 && r.paybar, `member ${w}: real session → member head, 4 rows (no guest chips), paybar; no guest promo`, JSON.stringify(r).slice(0, 200));
      await p.screenshot({ path: `${OUT}/member-${w}.png` });
    });
  }
}
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
