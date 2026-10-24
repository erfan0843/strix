// Trace the real "ورود/ثبت‌نام" click path from the home page to the rendered login page.
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const BASE = 'http://127.0.0.1:8000';
const TAG = process.env.TAG || 'path';
const OUT = `/tmp/qa/login/${TAG}`; fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function trace(vp, label, sw) {
  const b = await launchBrowser();
  const ctx = await b.newContext({ viewport: vp, serviceWorkers: sw ? 'allow' : 'block', locale: 'fa-IR' });
  await ctx.addInitScript(() => { try { localStorage.setItem('nora-theme', 'light'); } catch (e) {} });
  const p = await ctx.newPage();
  const loaded = [];
  p.on('response', r => { const u = r.url(); if (/login\.(css|js|html)|ui\.js|nora\.css|glass\.css|sw\.js/.test(u)) loaded.push(r.status() + ' ' + u.replace(BASE, '') + (r.fromServiceWorker() ? ' [SW]' : '')); });
  const errs = []; p.on('pageerror', e => errs.push(String(e.message).slice(0, 100)));
  console.log(`\n## ${label} ${vp.width}x${vp.height} sw=${sw ? 'on' : 'off'}`);
  await p.goto(BASE + '/home.html', { waitUntil: 'domcontentloaded' }); await sleep(1500);
  console.log('1 home:', p.url().replace(BASE, ''));
  // the visible entry control: tabbar on mobile, otherwise header/nav account link
  const entry = await p.evaluate(() => {
    const cands = [...document.querySelectorAll('a,button')].filter(el => /ورود\/ثبت‌نام|ورود \/ ثبت‌نام/.test(el.textContent) && el.getBoundingClientRect().width > 0);
    return cands.map(el => ({ tag: el.tagName, href: el.getAttribute('href'), cls: el.className, text: el.textContent.trim().slice(0, 30), in: el.closest('.tabbar') ? 'tabbar' : el.closest('.topbar') ? 'topbar' : el.closest('nav') ? 'nav' : el.closest('.rail') ? 'rail' : 'body' }));
  });
  console.log('  visible «ورود/ثبت‌نام» controls:', JSON.stringify(entry));
  await p.screenshot({ path: `${OUT}/1-home-${label}.png` });
  const sel = entry.find(e => e.in === 'tabbar') ? '.tabbar a[href="account.html"], .tabbar a[href*="account.html"]' : 'a[href="account.html"]';
  const clickable = await p.$(sel);
  if (!clickable) { console.log('  ! no clickable entry found for', sel); await b.close(); return; }
  await clickable.click(); await p.waitForLoadState('domcontentloaded'); await sleep(1500);
  console.log('2 after click:', p.url().replace(BASE, ''));
  const guest = await p.evaluate(() => { const a = [...document.querySelectorAll('a')].find(x => /login\.html/.test(x.getAttribute('href') || '') && x.getBoundingClientRect().width > 0); return a ? { href: a.getAttribute('href'), text: a.textContent.trim(), cls: a.className } : null; });
  console.log('  guest-view login link:', JSON.stringify(guest));
  await p.screenshot({ path: `${OUT}/2-account-guest-${label}.png` });
  if (guest) {
    await p.click(`a[href="${guest.href}"]`); await p.waitForLoadState('domcontentloaded'); await sleep(1500);
    console.log('3 login page:', p.url().replace(BASE, ''));
    const info = await p.evaluate(() => ({ title: document.title, h1: document.querySelector('#lgTitle')?.textContent, css: [...document.querySelectorAll('link[rel=stylesheet]')].map(l => l.getAttribute('href')), js: [...document.querySelectorAll('script[src]')].map(s => s.getAttribute('src')), form: !!document.querySelector('#lgPhoneForm'), captcha: !!document.querySelector('#lgCapImg img') }));
    console.log('  rendered:', JSON.stringify(info));
    await p.screenshot({ path: `${OUT}/3-login-${label}.png` });
  }
  console.log('  loaded assets:', loaded.join(' | '));
  console.log('  page errors:', errs.length ? errs.join(' | ') : 'none');
  await b.close();
}
await trace({ width: 390, height: 844 }, 'mobile', false);
await trace({ width: 1280, height: 800 }, 'desktop', false);
await trace({ width: 390, height: 844 }, 'mobile-sw', true);
