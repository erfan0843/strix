// Real click path: home.html → tabbar person icon («ورود/ثبت‌نام» / «حساب من») → account.html guest view.
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const BASE = 'http://127.0.0.1:8000';
const TAG = process.env.TAG || 'acct';
const OUT = `/tmp/qa/acct/${TAG}`; fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function launch() { for (let i = 0; ; i++) { try { return await launchBrowser(); } catch (e) { if (i >= 2) throw e; await sleep(1500); } } }
async function trace(vp, label, theme) {
  const b = await launch();
  const ctx = await b.newContext({ viewport: vp, serviceWorkers: 'block', locale: 'fa-IR' });
  await ctx.addInitScript(t => { try { localStorage.setItem('nora-theme', t); } catch (e) {} }, theme);
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e.message).slice(0, 100)));
  console.log(`\n## ${label} ${vp.width}x${vp.height} ${theme}`);
  await p.goto(BASE + '/home.html', { waitUntil: 'domcontentloaded' }); await sleep(1500);
  const entry = await p.evaluate(() => {
    const el = document.querySelector('.tabbar a[href*="account.html"]');
    if (!el) return null; const r = el.getBoundingClientRect();
    return { href: el.getAttribute('href'), text: el.textContent.trim(), visible: r.width > 0 && r.height > 0, icon: (el.querySelector('use') || {}).getAttribute ? el.querySelector('use').getAttribute('href') : null };
  });
  console.log('1 home tabbar person entry:', JSON.stringify(entry));
  if (entry && entry.visible) { await p.click('.tabbar a[href*="account.html"]'); }
  else { const a = await p.$('a[href="account.html"]'); console.log('  (tabbar hidden at this width; using visible account.html link)'); await a.click(); }
  await p.waitForLoadState('domcontentloaded'); await sleep(1800);
  const info = await p.evaluate(() => ({
    url: location.pathname + location.search + location.hash, title: document.title,
    css: [...document.querySelectorAll('link[rel=stylesheet]')].map(l => l.getAttribute('href')),
    js: [...document.querySelectorAll('script[src]')].map(s => s.getAttribute('src')),
    guest: !!document.querySelector('.account-promo'), h2: document.querySelector('.account-promo h2, .acct-guest h1, .acct-guest h2')?.textContent.replace(/\s+/g, ' ').trim(),
    loginLink: (document.querySelector('a[href*="login.html"]') || {}).getAttribute?.('href'),
    sections: [...document.querySelectorAll('#app > *, main > *')].map(e => e.className || e.tagName).slice(0, 12),
    docH: document.documentElement.scrollHeight, ox: document.documentElement.scrollWidth > innerWidth,
  }));
  console.log('2 account page:', JSON.stringify(info));
  await p.screenshot({ path: `${OUT}/account-guest-${label}-${theme}.png` });
  await p.screenshot({ path: `${OUT}/account-guest-${label}-${theme}-full.png`, fullPage: true });
  console.log('  page errors:', errs.length ? errs.join(' | ') : 'none');
  await b.close();
}
await trace({ width: 390, height: 844 }, 'mobile', 'light');
await trace({ width: 390, height: 844 }, 'mobile', 'dark');
await trace({ width: 1280, height: 800 }, 'desktop', 'light');
await trace({ width: 1280, height: 800 }, 'desktop', 'dark');
