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

// 1) guest landing structure: minimal block + real sections; no feature claims, no «فایل‌های شخصی», no sample data
await withPage({ name: 'guest-open' }, async p => {
  const r = await p.evaluate(() => {
    const txt = document.querySelector('#profBox').textContent.replace(/\s+/g, ' ');
    return {
      hero: !!document.querySelector('.account-promo-hero'), h2: document.querySelector('#accountPromoTitle')?.textContent.trim(), p: document.querySelector('.account-promo-copy>p')?.textContent.trim(),
      heroH: Math.round(document.querySelector('.account-promo-hero').getBoundingClientRect().height),
      primary: document.querySelector('.account-promo-hero .btn.primary')?.getAttribute('href'), primaries: document.querySelectorAll('#profBox .btn.primary').length,
      rows: [...document.querySelectorAll('.server-rows a.mrow2')].map(a => a.getAttribute('href')), rowSmall: document.querySelectorAll('.server-rows .mrow2 small').length,
      guestChips: document.querySelectorAll('.server-rows .mini-guest').length,
      paybarLink: document.querySelector('.server-paybar.is-guest a.pbmain')?.getAttribute('href'), pbrow: !!document.querySelector('.server-paybar .pbrow'),
      features: document.querySelectorAll('.account-promo-feature, .account-promo-features, .account-promo-preview, .account-promo-bottom, .account-promo-eyebrow').length,
      files: /فایل‌های شخصی/.test(txt), claims: /ثبت‌نام‌هایت|اعلان‌های حساب|همه یک‌جا|همه‌چیز همین‌جاست|مهمان/.test(txt),
      mheadBg: getComputedStyle(document.querySelector('.server-rows .mhead')).backgroundImage,
      sample: /۵۴۳۲۱|سارا محمدی|۱٬۲۵۰٬۰۰۰|تومان/.test(txt),
      docH: document.documentElement.scrollHeight, ox: document.documentElement.scrollWidth > innerWidth,
      primaryTop: Math.round(document.querySelector('.account-promo-hero .btn.primary').getBoundingClientRect().top),
      textLines: txt.trim().length,
    };
  });
  ok(r.hero && r.h2 === 'حساب من' && r.p === 'برای ادامه وارد حساب شو.' && r.heroH < 300, 'guest: short block — «حساب من», one sentence, height < 300px', JSON.stringify([r.h2, r.p, r.heroH]));
  ok(r.primary === 'login.html?mode=server&next=account.html' && r.primaries === 1 && r.primaryTop < 400, 'guest: exactly one primary CTA → server login, visible at first glance', JSON.stringify([r.primary, r.primaries, r.primaryTop]));
  ok(r.rows.length === 4 && r.rowSmall === 0 && r.guestChips === 3, 'guest: 4 real section rows, no descriptions, 3 «بعد از ورود» hints', JSON.stringify([r.rows, r.rowSmall, r.guestChips]));
  ok(r.paybarLink === 'account.html#payments' && !r.pbrow, 'guest: نورا پی is one row → account.html#payments (no button row)', JSON.stringify([r.paybarLink, r.pbrow]));
  ok(r.features === 0 && !r.files && !r.claims, 'guest: no feature cards / preview / eyebrow, no «فایل‌های شخصی», no promotional claims', JSON.stringify([r.features, r.files, r.claims]));
  ok(r.mheadBg === 'none' && !r.sample && !r.ox, 'guest: rows head without inherited gradient, no sample data, no horizontal overflow', JSON.stringify([r.mheadBg, r.sample, r.ox, r.docH]));
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
// 3b) guest نورا پی row → payments view (needs login) inside account.html
await withPage({ name: 'guest-pay-row' }, async p => {
  await p.click('.server-paybar.is-guest a.pbmain'); await sleep(1200);
  const r = await p.evaluate(() => ({ hash: location.hash, view: document.querySelector('#viewBox')?.textContent.replace(/\s+/g, ' ').slice(0, 160), loginLink: !!document.querySelector('#viewBox a[href^="login.html?mode=server"]') }));
  ok(r.hash === '#payments' && /نیاز به ورود/.test(r.view) && r.loginLink, 'guest: نورا پی row → existing payments needs-login view with secure login link', JSON.stringify(r).slice(0, 160));
});
// 4) public events link
await withPage({ name: 'guest-public' }, async p => {
  await p.click('.tabbar a[href="events.html"]'); await p.waitForLoadState('domcontentloaded'); await sleep(800);
  ok(/\/events\.html$/.test(p.url()), 'guest: public events reachable from the shared tabbar (no extra link on the page)', p.url().replace(BASE, ''));
});
// 5) offline API → retry button visible in hero, nothing else requested
await withPage({ name: 'guest-offline', route: async p => p.route('**/api/account/me', r => r.abort()) }, async p => {
  const r = await p.evaluate(() => ({ retry: !!document.querySelector('.account-promo [data-server-account-retry]'), hero: !!document.querySelector('.account-promo-hero') }));
  ok(r.retry && r.hero, 'guest offline: block stays, «بررسی دوباره» rendered under the CTA', JSON.stringify(r));
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
