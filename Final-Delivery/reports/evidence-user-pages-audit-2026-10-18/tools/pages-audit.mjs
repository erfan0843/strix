// Broad user-page audit in the isolated test env (real browser, real test server, test data only).
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const ORIGIN = 'http://127.0.0.1:8000';
const OUT = process.env.OUT || '/tmp/qa/pages-audit'; fs.mkdirSync(OUT, { recursive: true });
const FORM = process.env.FORM_ID || 'c885a821-2583-4716-a5d6-ab43f1fda5ac';
const PAGES = [
  ['home', '/home.html'], ['index', '/'], ['events', '/events.html'], ['events-past', '/events.html?status=past'],
  ['event', '/event.html?id=qa-ev-1'], ['event-missing', '/event.html?id=does-not-exist'],
  ['post', '/post.html?id=np-qa-1'], ['post-missing', '/post.html?id=nope'],
  ['person', '/person.html?id=qa-p1'], ['person-missing', '/person.html?id=nope'],
  ['partner', '/partner.html?id=qa-partner-1'], ['partner-missing', '/partner.html?id=nope'],
  ['login', '/login.html'], ['login-staff', '/login.html?mode=staff'], ['account', '/account.html'],
  ['form', `/form.html?fid=${FORM}`], ['form-missing', '/form.html?fid=missing-form'], ['form-none', '/form.html'],
  ['final-page-review', '/final-page-review.html'], ['support', '/support.html'], ['404', '/404.html'], ['not-found', '/no-such-page.html'],
  ['offline', '/offline.html'], ['create', '/create.html'], ['builder', '/builder.html'],
  ['loading-preview', '/loading-preview.html'], ['nora-pay-preview', '/nora-pay-preview.html'],
];
const ONLY = (process.env.ONLY||'').split(',').filter(Boolean); if (ONLY.length) PAGES.splice(0, PAGES.length, ...PAGES.filter(p => ONLY.includes(p[0])));
const VIEWPORTS = [[360, 800], [390, 844], [768, 1024], [1280, 800], [1440, 900]];
const SHOT_VIEWPORTS = new Set([390, 1280]);
const report = {};
const launch = async () => { for (let i = 0; i < 5; i++) { try { return await launchBrowser(); } catch (e) { if (i === 4) throw e; await new Promise(r => setTimeout(r, 1500)); } } };

const inspect = () => {
  const vis = el => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const name = el => (el.getAttribute('aria-label') || el.getAttribute('title') || (el.getAttribute('aria-labelledby') && document.getElementById(el.getAttribute('aria-labelledby'))?.textContent) || el.textContent || '').trim();
  const imgs = [...document.images].filter(vis);
  const noAlt = imgs.filter(i => !i.hasAttribute('alt')).map(i => i.getAttribute('src')?.slice(0, 80));
  const broken = imgs.filter(i => i.complete && i.naturalWidth === 0 && i.getAttribute('src')).map(i => i.getAttribute('src')?.slice(0, 80));
  const ctrls = [...document.querySelectorAll('a,button,[role=button],input,select,textarea')].filter(vis);
  const unnamed = ctrls.filter(el => !['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName) && !name(el) && !el.querySelector('img[alt]')).map(el => el.tagName + '.' + (el.className || '').toString().slice(0, 30));
  const inputs = [...document.querySelectorAll('input:not([type=hidden]),select,textarea')].filter(vis);
  const unlabeled = inputs.filter(el => !(el.labels && el.labels.length) && !el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby') && !el.getAttribute('title') && !(el.type === 'submit' || el.type === 'button')).map(el => el.tagName + '#' + (el.id || el.name || el.placeholder || ''));
  const small = ctrls.filter(el => { const r = el.getBoundingClientRect(); return (r.width < 32 || r.height < 32) && el.tagName !== 'INPUT'; }).map(el => el.tagName + '.' + (el.className || '').toString().slice(0, 25) + ':' + Math.round(el.getBoundingClientRect().width) + 'x' + Math.round(el.getBoundingClientRect().height));
  const meta = n => document.querySelector(`meta[name="${n}"]`)?.content || document.querySelector(`meta[property="${n}"]`)?.content || '';
  const hs = [...document.querySelectorAll('h1,h2,h3')].filter(vis).map(h => h.tagName + ':' + h.textContent.trim().slice(0, 40));
  const links = [...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href')).filter(h => h && !h.startsWith('#') && !h.startsWith('javascript'));
  const ld = [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => { try { return JSON.parse(s.textContent)['@type']; } catch { return 'INVALID'; } });
  return {
    title: document.title, lang: document.documentElement.lang, dir: document.documentElement.dir,
    description: meta('description'), robots: meta('robots'), canonical: document.querySelector('link[rel=canonical]')?.href || '',
    ogTitle: meta('og:title'), ogImage: meta('og:image'), ld, h1: hs.filter(h => h.startsWith('H1')).length, headings: hs.slice(0, 12),
    scrollW: document.documentElement.scrollWidth, innerW: innerWidth, bodyText: document.body.innerText.slice(0, 160).replace(/\s+/g, ' '),
    noAlt, broken, unnamed: [...new Set(unnamed)].slice(0, 15), unlabeled: [...new Set(unlabeled)].slice(0, 15), small: [...new Set(small)].slice(0, 15),
    links: [...new Set(links)], main: !!document.querySelector('main,[role=main]'), skip: !!document.querySelector('a[href^="#"].skip, .skip-link, a.skip'),
    focusable: ctrls.length, reducedMotion: !!document.querySelector('style, link[rel=stylesheet]'),
  };
};

for (const [name, path] of PAGES) {
  report[name] = { path, views: {} };
  for (const [w, h] of VIEWPORTS) {
    const browser = await launch();
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, locale: 'fa-IR', serviceWorkers: 'block', isMobile: w < 600, hasTouch: w < 600 });
    const page = await ctx.newPage();
    const errors = [], failed = [], apiCalls = [];
    page.on('pageerror', e => errors.push('pageerror: ' + String(e.message).slice(0, 160)));
    page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 160)); });
    page.on('response', r => { if (r.status() >= 400) failed.push(r.status() + ' ' + r.url().replace(ORIGIN, '').slice(0, 100)); });
    page.on('request', r => { if (r.url().includes('/api/')) apiCalls.push(r.method() + ' ' + r.url().replace(ORIGIN, '').split('?')[0]); });
    const t0 = Date.now();
    let status = 0;
    try { const resp = await page.goto(ORIGIN + path, { waitUntil: 'load', timeout: 20000 }); status = resp ? resp.status() : 0; } catch (e) { errors.push('goto: ' + e.message.slice(0, 100)); }
    const loadMs = Date.now() - t0;
    await page.waitForTimeout(1200);
    let info = {}; try { info = await page.evaluate(inspect); } catch (e) { info = { evalError: e.message.slice(0, 120) }; }
    const perf = await page.evaluate(() => { const n = performance.getEntriesByType('navigation')[0]; const res = performance.getEntriesByType('resource'); return { dcl: Math.round(n?.domContentLoadedEventEnd || 0), load: Math.round(n?.loadEventEnd || 0), resources: res.length, bytes: res.reduce((s, r) => s + (r.transferSize || 0), 0), big: res.filter(r => (r.transferSize || 0) > 150000).map(r => r.name.replace(location.origin, '') + ':' + Math.round(r.transferSize / 1024) + 'k') }; }).catch(() => ({}));
    const dup = apiCalls.filter((c, i) => apiCalls.indexOf(c) !== i);
    report[name].views[`${w}x${h}`] = { status, loadMs, perf, errors: [...new Set(errors)], failed: [...new Set(failed)], apiCalls: [...new Set(apiCalls)], dupApi: [...new Set(dup)], ...info };
    if (SHOT_VIEWPORTS.has(w)) await page.screenshot({ path: `${OUT}/${name}-${w}.png` }).catch(() => {});
    if (w === 390) {
      // dark theme shot
      await ctx.close(); await browser.close(); const browserD = await launch();
      const ctx2 = await browserD.newContext({ viewport: { width: w, height: h }, locale: 'fa-IR', serviceWorkers: 'block', isMobile: true, hasTouch: true, colorScheme: 'dark' });
      const p2 = await ctx2.newPage();
      await p2.addInitScript(() => { try { localStorage.setItem('nora-theme', 'dark'); } catch (e) {} });
      const derr = []; p2.on('pageerror', e => derr.push(String(e.message).slice(0, 120)));
      await p2.goto(ORIGIN + path, { waitUntil: 'load', timeout: 20000 }).catch(() => {});
      await p2.waitForTimeout(900);
      const dark = await p2.evaluate(() => ({ theme: document.documentElement.dataset.theme || document.documentElement.className, bg: getComputedStyle(document.body).backgroundColor, scrollW: document.documentElement.scrollWidth, innerW: innerWidth })).catch(() => ({}));
      report[name].views[`${w}x${h}`].dark = { ...dark, errors: derr };
      await p2.screenshot({ path: `${OUT}/${name}-${w}-dark.png` }).catch(() => {});
      await ctx2.close(); await browserD.close(); continue;
    }
    await ctx.close(); await browser.close();
  }
  const v = report[name].views['390x844'];
  console.log(`${name.padEnd(18)} ${v.status} load=${v.loadMs}ms err=${v.errors.length} failed=${v.failed.length} overflow=${Object.entries(report[name].views).filter(([, x]) => x.scrollW > x.innerW).map(([k]) => k).join(',') || '-'} unnamed=${v.unnamed?.length} unlabeled=${v.unlabeled?.length} small=${v.small?.length} noAlt=${v.noAlt?.length} h1=${v.h1} robots=${v.robots}`);
}
// link check: resolve each unique internal href against the server
const all = new Set();
for (const p of Object.values(report)) for (const v of Object.values(p.views)) for (const l of v.links || []) all.add(l);
const linkStatus = {};
const browserL = await launch(); const ctx = await browserL.newContext();
const pg = await ctx.newPage();
for (const l of all) {
  if (/^(mailto:|tel:|https?:\/\/(?!127\.0\.0\.1))/.test(l)) { linkStatus[l] = 'external'; continue; }
  try { const r = await pg.request.get(new URL(l, ORIGIN + '/home.html').href, { maxRedirects: 3 }); linkStatus[l] = r.status(); } catch (e) { linkStatus[l] = 'ERR ' + e.message.slice(0, 60); }
}
await ctx.close(); await browserL.close();
report.__links = linkStatus;
console.log('broken internal links:', Object.entries(linkStatus).filter(([, s]) => typeof s === 'number' ? s >= 400 : String(s).startsWith('ERR')));
fs.writeFileSync(`${OUT}/pages-audit.json`, JSON.stringify(report, null, 2));
