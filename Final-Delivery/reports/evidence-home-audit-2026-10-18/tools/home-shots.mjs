// Home page screenshots + basic audit (test env only).
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const ORIGIN = 'http://127.0.0.1:8000';
const OUT = process.env.OUT || '/tmp/qa/home-before';
const THEME = process.env.THEME || '';
fs.mkdirSync(OUT, { recursive: true });
const sizes = [['mobile', 390, 844], ['desktop', 1280, 800]];
const results = [];
for (const [name, w, h] of sizes) {
  const browser = await launchBrowser();
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, locale: 'fa-IR', serviceWorkers: 'block',
    deviceScaleFactor: 1, isMobile: name === 'mobile', hasTouch: name === 'mobile' });
  const page = await ctx.newPage();
  const errors = [], requests = [];
  page.on('pageerror', e => errors.push(String(e.message || e)));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  page.on('request', r => { const u = r.url(); if (u.includes('/api/')) requests.push(u.replace(ORIGIN, '')); });
  if (THEME) await page.addInitScript(t => { try { localStorage.setItem('nora-theme', t); } catch (e) {} }, THEME);
  await page.goto(ORIGIN + '/home.html', { waitUntil: 'load' }); await page.waitForFunction(() => window.NORA_PUBLIC_SOURCE, null, { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(800);
  const info = await page.evaluate(() => {
    const b = document.getElementById('bnr');
    const r = b ? b.getBoundingClientRect() : null;
    return {
      source: window.NORA_PUBLIC_SOURCE, banners: (window.NORA && window.NORA.BANNERS || []).length,
      bannerHidden: b ? b.hidden : null, bannerRect: r ? { x: r.x, y: r.y, w: r.width, h: r.height } : null,
      scrollW: document.documentElement.scrollWidth, innerW: innerWidth,
      pageH: document.documentElement.scrollHeight,
      theme: document.documentElement.dataset.theme || document.documentElement.getAttribute('data-theme'),
      sections: [...document.querySelectorAll('main section, main > div[id], main > *')].filter(s => !s.hidden && s.getBoundingClientRect().height > 0)
        .map(s => ({ id: s.id || s.className.split(' ')[0], top: Math.round(s.getBoundingClientRect().top + scrollY), h: Math.round(s.getBoundingClientRect().height) })).slice(0, 40),
      h1: (document.querySelector('h1') || {}).textContent,
    };
  });
  await page.screenshot({ path: path.join(OUT, `${name}-viewport.png`) });
  await page.screenshot({ path: path.join(OUT, `${name}-full.png`), fullPage: true });
  results.push({ name, w, h, info, errors, requests });
  await browser.close();
}
fs.writeFileSync(path.join(OUT, 'result.json'), JSON.stringify(results, null, 2));
for (const r of results) console.log(r.name, JSON.stringify({ ...r.info, sections: undefined }), 'errors:', r.errors.length, 'api:', r.requests.join(','));
console.log('sections mobile:', JSON.stringify(results[0].info.sections));
